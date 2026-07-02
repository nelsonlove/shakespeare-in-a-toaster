"""Constants recovered from Shakespeare v1.0 (c) 1989-1991 Bob Schumaker.

Every value here was extracted from the original 68k binary (CODE 1
disassembly and the THINK C %A5Init globals image) on 2026-07-01.
Sources and derivations are documented in the project's reverse-
engineering notes ("Sonnet engine internals", JD 92212).
"""

# Foot-pattern tables indexed by word class (WORD resource ID - 128).
# '1' = stressed syllable position, '0' = unstressed. The EVEN table is
# used when the current line position is even (off-beat), ODD on beats;
# they differ only at class 1 (stressed monosyllables), which at an even
# position must be preceded by an unstressed connective filler ("01").
FOOT_PATTERNS_EVEN = (
    "0", "01", "01", "10", "11", "10", "01",
    "010", "0101", "1010", "01010", "1010", "101", "10101",
)
FOOT_PATTERNS_ODD = (
    "0", "1", "01", "10", "11", "10", "01",
    "010", "0101", "1010", "01010", "1010", "101", "10101",
)

NUM_CLASSES = 14

CLASS_NAMES = (
    "FT_UNUSED", "FT_HF", "FT_IF", "FT_TF", "FT_UNUSED2", "FT_DF",
    "FT_AF", "FT_IFF", "FT_IIF", "FT_TTF", "FT_IIFF", "FT_TDF",
    "FT_HIF", "FT_EXTRA",
)

# 11-position stress templates. Line length is 10; the 11th position
# permits an 11-syllable feminine ending. The inverted template (trochaic
# first foot) shares the normal template's tail from position 3, so the
# inversion choice only matters for the word placed at position 0.
TEMPLATE_NORMAL = "01010101010"
TEMPLATE_INVERTED = "10010101010"

DEFAULT_SCHEME = "ABAB CDCD EFEF GG"
DEFAULT_LINE_LENGTH = 10

# Percent chance that a "connective + stressed monosyllable" construction
# is permitted at an even position, re-rolled once per word slot.
FILLER_PERMISSION_PCT = 32

# Percent chance of first-foot inversion, rolled at position 0 only:
# 9% on quatrain-initial lines (1-based verse lines 1, 5, 9, 13 under the
# default scheme — every line whose (verse_no - 1) % 4 == 0), 3% elsewhere.
INVERSION_PCT_QUATRAIN_INITIAL = 9
INVERSION_PCT_OTHER = 3

# Connective (filler) distribution, exact percentages from the threshold
# cascade in the original. Tuple entries are (consonant_form, vowel_form)
# pairs — the vowel form is used when the following word starts with a
# vowel letter. Percentages sum to 100.
CONNECTIVES = (
    (35, "the"),
    (21, "no"),
    (11, "and"),
    (8, ("a", "an")),
    (5, "of"),
    (5, ("in a", "in an")),
    (3, "with"),
    (2, "for"),
    (1, "to"),
    (1, ("for a", "for an")),
    (1, ("by a", "by an")),
    (1, ("to a", "to an")),
    (1, ("with a", "with an")),
    (1, "they"),
    (1, "we"),
    (1, "O"),
    (1, "but"),
    (1, "thou"),
)

# Per-slot rejection-sampling budget in the original was the total word
# count (2011). We scale it to the live lexicon at compose time; this is
# the floor so tiny custom lexicons still get a fair search.
MIN_PICK_BUDGET = 2011

# The original retried a failed line forever (strict, then loose rhyme).
# We cap restarts so a degenerate custom lexicon errors instead of hanging.
MAX_LINE_RESTARTS = 10_000
