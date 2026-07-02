"""Lexicon model: the 2,011-word 1989 wordlist plus user edits.

The on-disk format matches the JSON extracted from the original WORD
resources: a mapping of class name -> {resource_id, count, words:
[{word, rhyme}]}. The bundled copy is pristine; user edits are saved to
an XDG data path and loaded in preference to the bundle.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .constants import CLASS_NAMES, NUM_CLASSES
from .rhyme import CONSONANT_LEGEND, FOOT_LEGEND, VOWEL_LEGEND


class LexiconError(ValueError):
    """Raised when a lexicon file or entry is invalid."""


@dataclass(frozen=True)
class Word:
    text: str
    vowel: str
    consonant: str

    @property
    def rhyme_code(self) -> str:
        return self.vowel + self.consonant


def user_lexicon_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME", "~/.local/share")
    return Path(base).expanduser() / "shakespeare-in-a-toaster" / "lexicon.json"


class Lexicon:
    """Words grouped by foot class, with an index for parsing saved sonnets."""

    def __init__(self, classes: dict[int, list[Word]]):
        self.classes = {c: list(classes.get(c, [])) for c in range(NUM_CLASSES)}
        self._index: dict[str, tuple[int, int]] | None = None

    # -- loading / saving ------------------------------------------------

    @classmethod
    def from_json(cls, data: dict) -> "Lexicon":
        classes: dict[int, list[Word]] = {}
        try:
            for entry in data.values():
                cls_id = int(entry["resource_id"]) - 128
                classes[cls_id] = [
                    Word(w["word"], w["rhyme"][0], w["rhyme"][1])
                    for w in entry["words"]
                ]
        except (KeyError, TypeError, IndexError) as exc:
            raise LexiconError(f"malformed lexicon data: {exc}") from exc
        return cls(classes)

    @classmethod
    def load_pristine(cls) -> "Lexicon":
        text = resources.files("toaster.data").joinpath("lexicon.json").read_text()
        return cls.from_json(json.loads(text))

    @classmethod
    def load(cls, pristine_only: bool = False) -> "Lexicon":
        """Load the user lexicon if present (and valid), else the bundle."""
        path = user_lexicon_path()
        if not pristine_only and path.exists():
            try:
                return cls.from_json(json.loads(path.read_text()))
            except (json.JSONDecodeError, LexiconError):
                pass  # fall back to pristine; caller may notify the user
        return cls.load_pristine()

    def to_json(self) -> dict:
        out = {}
        for cls_id, words in self.classes.items():
            if not words and cls_id not in (0, 4):
                # keep empty non-reserved classes so structure round-trips
                pass
            name = CLASS_NAMES[cls_id]
            out[name] = {
                "resource_id": cls_id + 128,
                "count": len(words),
                "words": [{"word": w.text, "rhyme": w.rhyme_code} for w in words],
            }
        return out

    def save_user_copy(self) -> Path:
        path = user_lexicon_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False))
        return path

    # -- editing ----------------------------------------------------------

    def validate_entry(self, text: str, cls_id: int, vowel: str, consonant: str):
        if not text.strip():
            raise LexiconError("word must not be empty")
        if cls_id not in FOOT_LEGEND:
            raise LexiconError(f"invalid foot class {cls_id}")
        if vowel not in VOWEL_LEGEND:
            raise LexiconError(f"invalid vowel code {vowel!r}")
        if consonant not in CONSONANT_LEGEND:
            raise LexiconError(f"invalid consonant code {consonant!r}")

    def add_word(self, text: str, cls_id: int, vowel: str, consonant: str) -> Word:
        self.validate_entry(text, cls_id, vowel, consonant)
        word = Word(text.strip(), vowel, consonant)
        self.classes[cls_id].append(word)
        self._index = None
        return word

    def delete_word(self, cls_id: int, index: int):
        del self.classes[cls_id][index]
        self._index = None

    def change_word(self, cls_id: int, index: int,
                    text: str, new_cls: int, vowel: str, consonant: str) -> Word:
        self.validate_entry(text, new_cls, vowel, consonant)
        self.delete_word(cls_id, index)
        return self.add_word(text, new_cls, vowel, consonant)

    # -- queries ----------------------------------------------------------

    @property
    def total_words(self) -> int:
        return sum(len(v) for v in self.classes.values())

    def class_weights(self) -> list[int]:
        return [len(self.classes[c]) for c in range(NUM_CLASSES)]

    def lookup(self, text: str) -> tuple[int, int] | None:
        """Word text -> (class, index), the runtime equivalent of INDX."""
        if self._index is None:
            self._index = {}
            for cls_id, words in self.classes.items():
                for i, w in enumerate(words):
                    self._index.setdefault(w.text.lower(), (cls_id, i))
        return self._index.get(text.lower())

    def word_at(self, cls_id: int, index: int) -> Word:
        return self.classes[cls_id][index]
