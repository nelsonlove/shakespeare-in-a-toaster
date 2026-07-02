"""Rhyme-code model and the legends recovered from the Manage Words dialog.

A word's rhyme code is two ASCII characters: (vowel sound, final
consonant sound). Two words rhyme when the vowel matches; "strict" rhyme
additionally requires the consonant to match. Space as the consonant
means "no consonant sound".
"""

VOWEL_LEGEND = {
    "A": "long A (Cambridge)",
    "a": "short A (mad)",
    "E": "long E (MIT)",
    "e": "short E (deaf)",
    "I": "long I (bicep)",
    "i": "short I (big)",
    "O": "long O (bold)",
    "o": "short O (bomb)",
    "U": "long U (zoo)",
    "u": "short U (lunch)",
    "y": "OY (oil)",
    "w": "OW (ouch)",
    "r": "ER (purgative)",
}

CONSONANT_LEGEND = {
    " ": "no consonant sound",
    "A": "sh (awash, dish, flesh)",
    "B": "st (feast, burst, juiced)",
    "C": "ch (catch, stretch, grouch)",
    "D": "ld (soiled, boiled, behold)",
    "E": "rd (chord, hoard, buzzword)",
    "F": "nk (junk, pink, crank)",
    "G": "nt (grunt, insolent, paramount)",
    "H": "nd (refined, stained, sustained)",
    "I": "ng (wrong, long, song)",
    "J": "ns (dense, tense, bounce)",
    "K": "mp (champ, clamp, clomp)",
    "L": "th (south, mouth, rebirth)",
    "M": "ts (guts, nuts, reports)",
    "N": "rt (snort, sport, apart)",
    "O": "rk (work, beserk, arc)",
    "P": "kt (defunct, cataract, deject)",
    "Q": "rm (harm, alarm, chloroform)",
    "R": "ps (corpse, warps, elapse)",
    "S": "pt (flipped, equipped, flapped)",
    "T": "lt (insult, occult, salt)",
    "U": "sp (grasp, rasp, lisp)",
    "V": "nch (wrench, stench, brunch)",
    "W": "sk (risk, tasks, brusque)",
    "X": "rs (worse, hearse, coarse)",
    "Y": "nj (hinge, cringe, munge)",
    "Z": "ft (cleft, left, thrift)",
    "$": "rn (born, worn, porn)",
    **{c: f"{c} (single consonant)" for c in "bdfgjklmnprstvxz"},
    # Not in the original dialog's list, but used by 33 lexicon entries
    # (Bach, Coke, break, …) for the /k/ sound:
    "c": "k spelled c (Bach, Coke, break)",
}


def consonant_label(code: str) -> str:
    """Legend label, tolerating the original's stray codes (e.g. adamant='o')."""
    return CONSONANT_LEGEND.get(code, f"{code!r} (non-standard, as in 1989 data)")


def vowel_label(code: str) -> str:
    return VOWEL_LEGEND.get(code, f"{code!r} (non-standard, as in 1989 data)")

# Foot-class legend from the Manage Words dialog ("Scans like" field),
# keyed by class index. Classes 0 and 4 are unused and unlisted.
FOOT_LEGEND = {
    1: "ace (Single syllable)",
    2: "hurrah (Iambic)",
    3: "hollow (Trochaic)",
    5: "happily (Dactylic)",
    6: "ala mode (Anapestic)",
    7: "resemble",
    8: "establishing",
    9: "education",
    10: "administration",
    11: "BMW",
    12: "document",
    13: "opportunity",
}


def rhymes(code_a: str, code_b: str, strict: bool) -> bool:
    """True if two rhyme codes rhyme (vowel match; consonant too if strict)."""
    if code_a[0] != code_b[0]:
        return False
    return not strict or code_a[1] == code_b[1]
