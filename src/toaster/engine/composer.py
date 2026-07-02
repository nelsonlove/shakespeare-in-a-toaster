"""The sonnet composer — a faithful port of the decoded 1989 algorithm.

Lines are filled left to right against an 11-position stress template.
Candidate words are rejection-sampled from the lexicon (class-weighted)
and accepted only when their foot pattern string-matches the template at
the current position. Line-ending words must satisfy the rhyme scheme;
if a line cannot be completed under strict rhyme (vowel + consonant),
it restarts with assonance-only rhyme, exactly as the original did.

Frozen lines are never touched: they contribute their rhyme sound and
ending word to their rhyme group, and rewrites compose around them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import constants as k
from .lexicon import Lexicon, Word
from .rhyme import rhymes


class ComposeError(RuntimeError):
    """Raised when composition cannot terminate (degenerate lexicon/scheme)."""


def connective_words() -> set[str]:
    """Every single word a connective can contribute, lowercased."""
    words: set[str] = set()
    for _, entry in k.CONNECTIVES:
        for form in (entry if isinstance(entry, tuple) else (entry,)):
            words.update(w.lower() for w in form.split())
    return words


def match_end_word(lexicon: Lexicon, tokens: list[str]) -> Word | None:
    """The lexicon entry ending a token list (multi-word entries first)."""
    for span in (3, 2, 1):
        if len(tokens) >= span:
            hit = lexicon.lookup(" ".join(tokens[-span:]))
            if hit:
                return lexicon.word_at(*hit)
    return None


@dataclass
class Line:
    letter: str | None            # rhyme-group letter; None for blank lines
    verse_no: int = 0             # 1-based, blank lines excluded
    tokens: list[str] = field(default_factory=list)  # display tokens in order
    end_word: Word | None = None  # the rhyme-bearing final word
    frozen: bool = False
    literal: str | None = None    # set when loaded text couldn't be parsed

    @property
    def blank(self) -> bool:
        return self.letter is None

    @property
    def text(self) -> str:
        if self.blank:
            return ""
        if self.literal is not None:
            return self.literal
        joined = " ".join(self.tokens)
        return joined[:1].upper() + joined[1:] if joined else ""


@dataclass
class Options:
    scheme: str = k.DEFAULT_SCHEME
    line_length: int = k.DEFAULT_LINE_LENGTH
    no_repeats: bool = False      # modern toggle; 1989 behavior is False


class Sonnet:
    def __init__(self, scheme: str = k.DEFAULT_SCHEME):
        self.scheme = scheme
        self.lines: list[Line] = []
        verse_no = 0
        for ch in scheme:
            if ch == " ":
                self.lines.append(Line(letter=None))
            else:
                verse_no += 1
                self.lines.append(Line(letter=ch, verse_no=verse_no))

    @property
    def verse_lines(self) -> list[Line]:
        return [ln for ln in self.lines if not ln.blank]

    @property
    def text(self) -> str:
        return "\n".join(ln.text for ln in self.lines)

    def group(self, letter: str) -> list[Line]:
        return [ln for ln in self.lines if ln.letter == letter]

    def clear(self):
        for ln in self.lines:
            ln.tokens, ln.end_word, ln.frozen, ln.literal = [], None, False, None


class Composer:
    def __init__(self, lexicon: Lexicon, rng: random.Random | None = None,
                 options: Options | None = None):
        self.lexicon = lexicon
        self.rng = rng or random.Random()
        self.options = options or Options()

    # -- public API --------------------------------------------------------

    def new_sonnet(self) -> Sonnet:
        sonnet = Sonnet(self.options.scheme)
        self.compose(sonnet)
        return sonnet

    def compose(self, sonnet: Sonnet):
        """Compose (or recompose) every unfrozen verse line in place."""
        # Clear unfrozen lines first so rhyme groups pick fresh sounds:
        # only frozen lines (and lines filled this pass) constrain rhyme.
        for ln in sonnet.verse_lines:
            if not ln.frozen:
                ln.tokens, ln.end_word, ln.literal = [], None, None
        used_words = set()
        if self.options.no_repeats:
            for ln in sonnet.verse_lines:
                if ln.frozen:
                    used_words.update(t.lower() for t in ln.tokens)
                    if ln.literal is not None:
                        used_words.update(t.lower() for t in ln.literal.split())
        for line in sonnet.verse_lines:
            if line.frozen:
                continue
            self._compose_line(sonnet, line, used_words)

    # -- rhyme-group state --------------------------------------------------

    def _group_rhyme(self, sonnet: Sonnet, line: Line) -> tuple[str | None, list[str]]:
        """(established rhyme code or None, end words already used in group).

        The original propagated the rhyme sound from the group leader, or
        from an already-composed partner when the leader itself was being
        recomposed. Composed = frozen or already filled this pass.
        """
        code, taken = None, []
        if line.letter is None:
            return code, taken
        for other in sonnet.group(line.letter):
            if other is line:
                continue
            if other.end_word is not None:
                if code is None:
                    code = other.end_word.rhyme_code
                taken.append(other.end_word.text.lower())
            elif other.literal is not None:
                # frozen literal line: derive rhyme from its ending words
                # (multi-word lexicon entries included)
                toks = other.literal.split()
                end = match_end_word(self.lexicon, toks)
                if end is not None:
                    if code is None:
                        code = end.rhyme_code
                    taken.append(end.text.lower())
                elif toks:
                    taken.append(toks[-1].lower())
        return code, taken

    # -- line composition ----------------------------------------------------

    def _compose_line(self, sonnet: Sonnet, line: Line, used_words: set[str]):
        weights = self.lexicon.class_weights()
        class_ids = [c for c in range(k.NUM_CLASSES) if weights[c] > 0]
        if not class_ids:
            raise ComposeError("lexicon is empty")
        class_wts = [weights[c] for c in class_ids]
        budget = max(self.lexicon.total_words, k.MIN_PICK_BUDGET)
        length = self.options.line_length
        group_code, taken_ends = self._group_rhyme(sonnet, line)

        strict = True
        for _restart in range(k.MAX_LINE_RESTARTS):
            tokens: list[str] = []
            line_words: list[Word] = []
            pos = 0
            failed = False
            end_word: Word | None = None

            while pos < length:
                invert = pos == 0 and self.rng.randrange(100) < (
                    k.INVERSION_PCT_QUATRAIN_INITIAL
                    if (line.verse_no - 1) % 4 == 0 else k.INVERSION_PCT_OTHER)
                allow_filler = self.rng.randrange(100) < k.FILLER_PERMISSION_PCT
                tried: set[tuple[int, int]] = set()

                for _ in range(budget):
                    cls_id = self.rng.choices(class_ids, weights=class_wts)[0]
                    idx = self.rng.randrange(weights[cls_id])
                    if (cls_id, idx) in tried:
                        continue
                    tried.add((cls_id, idx))
                    word = self.lexicon.word_at(cls_id, idx)
                    if self.options.no_repeats and word.text.lower() in used_words:
                        continue
                    pattern = (k.FOOT_PATTERNS_ODD if pos & 1
                               else k.FOOT_PATTERNS_EVEN)[cls_id]
                    template = (k.TEMPLATE_INVERTED if invert and cls_id != 5
                                else k.TEMPLATE_NORMAL)
                    if not template[pos:].startswith(pattern):
                        continue
                    needs_filler = (pos & 1) == 0 and cls_id == 1
                    if needs_filler and not allow_filler:
                        continue
                    if pos + len(pattern) >= length:  # line-ending word
                        # Masculine ending required on even verse lines and 13.
                        if ((line.verse_no % 2 == 0 or line.verse_no == 13)
                                and pattern.endswith("0")):
                            continue
                        if group_code is not None:
                            if not rhymes(word.rhyme_code, group_code, strict):
                                continue
                            if word.text.lower() in taken_ends:
                                continue
                        end_word = word
                    if needs_filler:
                        tokens.append(self._connective(word.text))
                    tokens.append(word.text)
                    line_words.append(word)
                    pos += len(pattern)
                    break
                else:
                    failed = True
                    break

            if not failed:
                line.tokens = tokens
                line.end_word = end_word
                line.literal = None
                if self.options.no_repeats:
                    used_words.update(w.text.lower() for w in line_words)
                return
            strict = False  # assonance-only fallback, then keep trying

        raise ComposeError(
            f"could not compose line {line.verse_no} after "
            f"{k.MAX_LINE_RESTARTS} restarts — lexicon too constrained")

    def _connective(self, next_word: str) -> str:
        roll = self.rng.randrange(100)
        acc = 0
        for pct, entry in k.CONNECTIVES:
            acc += pct
            if roll < acc:
                if isinstance(entry, tuple):
                    vowel_start = next_word[:1].lower() in "aeiou"
                    return entry[1] if vowel_start else entry[0]
                return entry
        return "the"  # unreachable; percentages sum to 100


# -- plain-text save / load ---------------------------------------------------


def save_sonnet(sonnet: Sonnet, path) -> None:
    from pathlib import Path
    Path(path).write_text(sonnet.text + "\n")


def load_sonnet(text: str, lexicon: Lexicon,
                scheme: str = k.DEFAULT_SCHEME) -> Sonnet:
    """Re-parse saved text into a Sonnet, the way the original used INDX.

    Each non-blank line is tokenized and matched against the lexicon
    (longest multi-word match first, then connectives). Fully parsed
    lines are restored as normal lines; anything else is kept verbatim
    as a frozen literal line so no text is ever dropped.
    """
    connectives = connective_words()

    sonnet = Sonnet(scheme)
    verse_iter = iter(sonnet.verse_lines)
    overflow_no = len(sonnet.verse_lines)
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            line = next(verse_iter)
        except StopIteration:
            # More lines than the scheme has slots: keep every one as a
            # frozen literal on its own rhyme letter (never drop text).
            overflow_no += 1
            line = Line(letter=f"\x00{overflow_no}", verse_no=overflow_no,
                        literal=raw, frozen=True)
            sonnet.lines.append(line)
            continue
        tokens = raw.split()
        parsed: list[str] = []
        words: list[Word] = []
        i, ok = 0, True
        while i < len(tokens):
            hit = None
            for span in (3, 2, 1):  # lexicon has multi-word entries
                cand = " ".join(tokens[i:i + span])
                found = lexicon.lookup(cand)
                if found:
                    hit = (found, cand, span)
                    break
            if hit:
                (cls_id, idx), cand, span = hit
                words.append(lexicon.word_at(cls_id, idx))
                parsed.append(cand)
                i += span
            elif tokens[i].lower() in connectives:
                parsed.append(tokens[i])
                i += 1
            else:
                ok = False
                break
        if ok and words:
            line.tokens = parsed
            line.end_word = words[-1]
            line.frozen = False
            line.literal = None
        else:
            line.literal = raw
            line.frozen = True
    return sonnet
