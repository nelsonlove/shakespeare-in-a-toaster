"""Engine tests: fidelity to the decoded 1989 algorithm."""

import random
from collections import Counter

import pytest

from toaster.engine import (
    Composer, Lexicon, Options, Sonnet, load_sonnet, save_sonnet,
)
from toaster.engine import constants as k
from toaster.engine.rhyme import rhymes


@pytest.fixture(scope="module")
def lexicon():
    return Lexicon.load_pristine()


def composer(lexicon, seed=0, **opts):
    return Composer(lexicon, random.Random(seed), Options(**opts))


# -- lexicon ------------------------------------------------------------------

def test_pristine_lexicon_shape(lexicon):
    assert lexicon.total_words == 2011
    assert len(lexicon.classes[1]) == 428   # FT_HF
    assert len(lexicon.classes[3]) == 739   # FT_TF
    assert len(lexicon.classes[11]) == 1    # FT_TDF: BMW
    assert lexicon.classes[11][0].text == "BMW"


def test_lexicon_lookup_index(lexicon):
    assert lexicon.lookup("zoo") is not None
    cls_id, idx = lexicon.lookup("zoo")
    assert lexicon.word_at(cls_id, idx).rhyme_code == "U "
    assert lexicon.lookup("Objective C") is not None  # multi-word entry
    assert lexicon.lookup("notaword") is None


def test_rhyme_codes(lexicon):
    zoo = lexicon.word_at(*lexicon.lookup("zoo"))
    blue = lexicon.word_at(*lexicon.lookup("blue"))
    zapped = lexicon.word_at(*lexicon.lookup("zapped"))
    assert rhymes(zoo.rhyme_code, blue.rhyme_code, strict=True)
    assert not rhymes(zoo.rhyme_code, zapped.rhyme_code, strict=False)


# -- structure ----------------------------------------------------------------

def test_scheme_structure():
    sonnet = Sonnet()
    assert len(sonnet.verse_lines) == 14
    assert [ln.blank for ln in sonnet.lines].count(True) == 3
    assert sonnet.verse_lines[0].verse_no == 1
    assert sonnet.verse_lines[-1].verse_no == 14


def test_compose_fills_every_line(lexicon):
    sonnet = composer(lexicon, seed=7).new_sonnet()
    for ln in sonnet.verse_lines:
        assert ln.tokens, f"line {ln.verse_no} empty"
        assert ln.text[0].isupper() or not ln.text[0].isalpha()
        assert ln.end_word is not None


def test_seed_determinism(lexicon):
    a = composer(lexicon, seed=42).new_sonnet().text
    b = composer(lexicon, seed=42).new_sonnet().text
    c = composer(lexicon, seed=43).new_sonnet().text
    assert a == b
    assert a != c


# -- metrical fidelity --------------------------------------------------------

def line_positions(lexicon, line):
    """Recompute the metrical positions a composed line consumes."""
    from toaster.engine.composer import connective_words
    connectives = connective_words()
    pos, i = 0, 0
    toks = line.tokens
    while i < len(toks):
        hit = None
        for span in (3, 2, 1):
            cand = " ".join(toks[i:i + span])
            if lexicon.lookup(cand):
                hit = (lexicon.lookup(cand), span)
                break
        if hit is None:
            assert toks[i].lower() in connectives, toks[i]
            pos += 1
            i += 1
            continue
        (cls_id, _), span = hit
        pattern = (k.FOOT_PATTERNS_ODD if pos & 1 else k.FOOT_PATTERNS_EVEN)[cls_id]
        pos += len(pattern) - (1 if pos % 2 == 0 and cls_id == 1 else 0)
        i += span
    return pos


def test_lines_reach_line_length(lexicon):
    sonnet = composer(lexicon, seed=99).new_sonnet()
    for ln in sonnet.verse_lines:
        assert line_positions(lexicon, ln) >= k.DEFAULT_LINE_LENGTH


def test_masculine_endings(lexicon):
    """Even verse lines and line 13 must end on a stressed position."""
    for seed in range(20):
        sonnet = composer(lexicon, seed=seed).new_sonnet()
        for ln in sonnet.verse_lines:
            if ln.verse_no % 2 == 0 or ln.verse_no == 13:
                cls_id, _ = lexicon.lookup(ln.end_word.text)
                pattern = k.FOOT_PATTERNS_ODD[cls_id]
                assert not pattern.endswith("0"), (
                    f"seed {seed} line {ln.verse_no} feminine: {ln.text}")


def test_rhyme_groups_agree(lexicon):
    """All lines in a rhyme group share at least the vowel sound."""
    for seed in range(20):
        sonnet = composer(lexicon, seed=seed).new_sonnet()
        by_letter = {}
        for ln in sonnet.verse_lines:
            by_letter.setdefault(ln.letter, []).append(ln.end_word)
        for letter, words in by_letter.items():
            vowels = {w.vowel for w in words}
            assert len(vowels) == 1, f"seed {seed} group {letter}: {words}"
            ends = [w.text.lower() for w in words]
            assert len(set(ends)) == len(ends), f"self-rhyme in group {letter}"


# -- connective distribution --------------------------------------------------

def test_connective_distribution(lexicon):
    comp = composer(lexicon, seed=5)
    counts = Counter(comp._connective("xylophone") for _ in range(20_000))
    assert abs(counts["the"] / 20_000 - 0.35) < 0.02
    assert abs(counts["no"] / 20_000 - 0.21) < 0.02
    assert abs(counts["and"] / 20_000 - 0.11) < 0.02
    assert counts["a"] > 0 and counts["an"] == 0  # consonant-start next word
    counts_v = Counter(comp._connective("apple") for _ in range(5_000))
    assert counts_v["an"] > 0 and counts_v["a"] == 0


# -- freeze semantics ---------------------------------------------------------

def test_freeze_preserves_lines_and_rhymes(lexicon):
    comp = composer(lexicon, seed=11)
    sonnet = comp.new_sonnet()
    frozen_line = sonnet.verse_lines[0]       # 'A' leader
    partner = sonnet.verse_lines[2]           # other 'A' line
    frozen_line.frozen = True
    before = frozen_line.text
    comp.compose(sonnet)
    assert frozen_line.text == before
    assert partner.end_word.vowel == frozen_line.end_word.vowel
    assert partner.end_word.text.lower() != frozen_line.end_word.text.lower()


def test_no_repeats_toggle(lexicon):
    comp = composer(lexicon, seed=3, no_repeats=True)
    sonnet = comp.new_sonnet()
    words = []
    for ln in sonnet.verse_lines:
        for tok in ln.tokens:
            if lexicon.lookup(tok):
                words.append(tok.lower())
    assert len(words) == len(set(words))


# -- custom schemes -----------------------------------------------------------

def test_custom_scheme(lexicon):
    comp = Composer(lexicon, random.Random(1), Options(scheme="AABB A"))
    sonnet = comp.new_sonnet()
    assert len(sonnet.verse_lines) == 5
    a_words = [ln.end_word for ln in sonnet.verse_lines if ln.letter == "A"]
    assert len({w.vowel for w in a_words}) == 1


# -- save / load --------------------------------------------------------------

def test_save_load_roundtrip(tmp_path, lexicon):
    comp = composer(lexicon, seed=8)
    sonnet = comp.new_sonnet()
    path = tmp_path / "sonnet.out"
    save_sonnet(sonnet, path)
    loaded = load_sonnet(path.read_text(), lexicon)
    assert loaded.text == sonnet.text
    # parsed lines carry rhyme info again
    for orig, new in zip(sonnet.verse_lines, loaded.verse_lines):
        assert new.end_word is not None
        assert new.end_word.vowel == orig.end_word.vowel


def test_load_unparseable_line_kept_frozen(lexicon):
    text = "This has words nowhere in the wordlist certainly\n"
    loaded = load_sonnet(text, lexicon)
    first = loaded.verse_lines[0]
    assert first.frozen
    assert first.text == text.strip()


# -- regression tests for the review findings ---------------------------------

def test_rewrite_gets_fresh_rhyme_sounds(lexicon):
    """compose() must clear unfrozen lines so rhyme groups aren't locked."""
    comp = composer(lexicon, seed=2)
    sonnet = comp.new_sonnet()
    vowels = set()
    for _ in range(6):
        comp.compose(sonnet)
        vowels.add(sonnet.verse_lines[0].end_word.vowel)
    assert len(vowels) > 1, "rhyme group A locked to one vowel across rewrites"


def test_load_overflow_lines_kept(lexicon):
    comp = composer(lexicon, seed=8)
    text = comp.new_sonnet().text + "\nExtra line one xyzzy\nExtra line two xyzzy\n"
    loaded = load_sonnet(text, lexicon)
    non_blank = [ln for ln in loaded.lines if not ln.blank]
    assert len(non_blank) == 16
    assert non_blank[-1].frozen and non_blank[-1].text == "Extra line two xyzzy"
    assert "Extra line one xyzzy" in loaded.text


def test_load_connective_O_parses(lexicon):
    loaded = load_sonnet("O zoo\n", lexicon)
    first = loaded.verse_lines[0]
    assert not first.frozen, "'O' connective should parse, not demote to literal"
    assert first.end_word.text == "zoo"


def test_frozen_literal_multiword_end_rhymes(lexicon):
    """A frozen literal ending in a multi-word entry constrains partners."""
    comp = composer(lexicon, seed=4)
    sonnet = Sonnet()
    leader = sonnet.verse_lines[0]
    leader.literal = "xyzzy unknown Objective C"
    leader.frozen = True
    comp.compose(sonnet)
    objc = lexicon.word_at(*lexicon.lookup("Objective C"))
    partner = sonnet.verse_lines[2]  # other 'A' line
    assert partner.end_word.vowel == objc.vowel
    assert partner.end_word.text.lower() != "objective c"


def test_no_repeats_sees_frozen_literals(lexicon):
    comp = composer(lexicon, seed=6, no_repeats=True)
    sonnet = Sonnet()
    leader = sonnet.verse_lines[0]
    leader.literal = "the zoo enthralled a windbag"
    leader.frozen = True
    comp.compose(sonnet)
    used = [t.lower() for ln in sonnet.verse_lines if not ln.frozen
            for t in ln.tokens if lexicon.lookup(t)]
    assert "zoo" not in used and "windbag" not in used
