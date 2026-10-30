"""Technique codes, names and the Move / Step records shared by the C++ solver's decoder, the scorer and the
explainer. (The solver itself lives in csrc/solver.cpp.)

Each move carries a compact feature tuple consumed by scoring.Scorer:
    (tech, base_shape, cover, extra)
cover = tuple of (kind, shape, uncovered_before) -- the set-cover sequence
used to find a single (naked: covering digits with groups; hidden: covering
cells with crosshatch sources), in the order a human would plausibly add them.
"""

from __future__ import annotations

from . import registry as _R

# technique codes
FULL_HOUSE, NAKED_D, HIDDEN_D, NAKED_DL, HIDDEN_DL = 0, 1, 2, 3, 4
TAKE_NOTES = 10
NAKED_N, HIDDEN_N, LOCKED = 11, 12, 13
NPAIR, HPAIR, NTRIPLE, HTRIPLE, NQUAD, HQUAD = 14, 15, 16, 17, 18, 19
XWING, SWORDFISH, XYWING, XYZWING, COLORING, PAIRARC, TRIAL, GUESS = 20, 21, 22, 23, 24, 25, 26, 27
INNIE_D, CAGE_COMBO, INNIE_N = 28, 29, 30
# n-ary constraint techniques (implemented in the C++ core only, see csolver/)
SUM_COMBO, ARROW_COMBO, SET_COMBO, EQSUM_COMBO, TABLE_COMBO, COMBO_LOCK, NARY_D = 31, 32, 33, 34, 35, 36, 37
INNIE_X = 38
# generalized fish and chains (C++ only)
FINNED_FISH, JELLYFISH, X_CHAIN, XY_CHAIN, AIC_CHAIN, NICE_LOOP = 39, 40, 41, 42, 43, 44
# line clues, leftovers, implied houses (pseudo code: disabling it ignores implied
# houses / leftovers), uniqueness, almost locked sets (C++ only)
SANDWICH_COMBO, XSUM_COMBO, SKYLINE_COMBO, LOL_COMBO, IMPLIED = 45, 46, 47, 48, 49
UNIQUE_RECT, BUG_PLUS1, ALS_XZ, ALS_XYWING, DEATH_BLOSSOM, ALS_AIC = 50, 51, 52, 53, 54, 55
# CANONICAL (pseudo code): symmetry-invariant enumeration / tie-breaking in the C++ core;
# disabling it restores the Python-reference enumeration. COUNT_COMBO: count (GCC) constraints.
CANONICAL, COUNT_COMBO = 56, 57
# item 6: line/relation reasoning without notes, whole-line moves with notes, mental subsets
LINE_D, LINE_RANGE, MENTAL_D = 58, 59, 60
SHORT_TRIAL = 61  # bounded case split on a bivalue cell (contradiction within <= 4 direct rounds)
MENTAL_CHAIN = 62  # short chain (<= 5 links) reasoned without notes, ending in a single
EITHER_WAY = 63  # both options of a two-way choice agree on a placement / elimination
LINE_CLASS = 64  # line reasoning on digit classes (high/low, parity, thirds, mod 3)
DIGIT_COUNT = 65  # positional set logic for one digit (must-contain units vs at-most-once groups)
EQUAL_DIGITS = 66  # abstract colouring: two cells forced to hold the same unknown digit
LINE_SCAN = 67  # line consistency on 3-cell windows (local scan of a long line)
# forcing chains (k-way cell / unit case analysis; C++ only)
FORCING = 68  # basic propagation in the branches (singles, relations, rules)
DYN_FORCING = 69  # dynamic: the engine's techniques up to a ceiling in the branches
NESTED_FORCING = 70  # nested II: forcing chains inside the branches
MEDUSA = 71  # 3D Medusa (multi-digit colouring)
SUM_BOUND = 72  # min / max (triangular number) bounds of sum rules
CLASS_COUNT = 73  # odd / even, low / middle / high counting; sum parity
DOMINO = 74  # relation dominoes (kropki, XV, difference): must-contain digit, 2-domino locks
COLOUR_ALGEBRA = 75  # abstract-digit colour classes (cells that hold the same unknown digit)
N_WING = 76  # WXYZ / VWXYZ wings (bent sets)
SUE_DE_COQ = 77
APE = 78  # aligned pair exclusion
CHUTE_RP = 79  # chute remote pairs
POM = 80  # pattern overlay method
GURTH = 81  # Gurth's symmetrical placement theorem (assumes a unique solution)
NISHIO = 82  # single-digit forcing net
WHAT_IF = 83  # human "what if": two-way case split followed with light logic (bounded)
MENTAL_NOTES = 84  # single after notes logic done in the head (on the no-notes mental view)
MULTI_COLOR = 85  # multi-colouring: two single-digit colour clusters interacting
REMOTE_PAIRS = 86  # XY-chain of identical bivalue pairs (own code: priced apart from XY-Chain)
EMPTY_RECT = 87  # empty rectangle (grouped X-chain through a box; own code)
RULE_INTERSECT = 88  # two rules / houses taken together (joint digit combinations over their cells)
SUM_ALGEBRA = 89  # interval algebra over unit sums in a band / stack (house totals, cages, segments)
SNYDER_MARKS = 90  # writing Snyder marks (params notes_mode = "snyder"), priced per mark like TakeNotes
SNYDER_D = 91  # a placement read from Snyder marks (hidden pair / box-line X-wing from Snyder pairs)
BAND_LOGIC = 92  # a band's lines + boxes + the rules inside taken together (C++ only; sub-puzzle consistency)
FIREWORKS = 93  # Andrew Stuart's Fireworks (C++ only): three digits confined to a cell + one row cell + one column cell
HUMAN_CASE = 94  # bounded human case analysis (C++ only): refutation / cell / house forcing with rule rounds
COMBO_POS = 95  # combination-aware positions (C++ only): a cage's fillings cap a digit set inside a house
CLIQUE_HOUSE = 96  # clique house (C++ only): pairwise-different cells (houses, anti-knight, relations) as a house
LINE_SETS = 97  # line digit sets across lines (C++ only): renbans meeting a house choose disjoint digit sets there
LINE_CLUES = 98  # outside clues together (C++ only): a line with >= 2 sandwich / x-sum / skyscraper clues as one unit
WEIGHTED_SUMS = 99  # weighted multi-house sums (C++ only): integer combinations of sum facts down to 1-3 cells
CLUE_FACTS = (
    101  # facts read off the clues alone (C++ only): relations on an empty grid (no 5 on a whisper, thermo ranges)
)
CLUE_SHAPE = 102  # clue facts with the line shape (C++ only): partners in one house needing more digits than allowed
CLASS_COLOUR = 100  # class colouring (C++ only): low / high or odd / even links between cells, sides fixed by known cells / house counts
# names and flags: the technique registry (data/techniques.csv); the constants above mirror csrc/solver.hpp enum Tech,
# and tests/test_registry.py checks all three agree
TECH_NAMES = {t.id: t.name for t in sorted(_R.techniques(), key=lambda t: t.id)}
NOTE_TECHS = tuple(t for t, n in TECH_NAMES.items() if _R.by_name()[n].role == "notes")  # time = t_mark x marks
DIRECT_TECHS = {t.id for t in _R.techniques() if t.direct}


class Move:
    __slots__ = ("feat", "place", "elim", "name", "d")

    def __init__(self, feat, place=None, elim=None, name="", meta=None):
        # meta: structural description for the meta-grader --
        # (cells, groups, digits, links, hidden, arith, relation, notes, spread)
        self.feat = feat + (meta,)  # (tech, base_shape, cover, extra, meta)
        self.place = place  # (cell, digit) or None
        self.elim = elim or ()  # ((cell, digit), ...)
        self.name = name
        self.d = None


class Step:
    __slots__ = ("move", "alts", "mode", "n_empty", "erasures", "notes_written", "n_cands")

    def __init__(self, move, alts, mode, n_empty, erasures=0, notes_written=0, n_cands=None):
        self.n_cands = n_cands  # candidates left in the empty cells before the step (C++ solves; None otherwise)
        self.move = move
        self.alts = alts  # list of feature tuples for all moves in the tier (incl. chosen)
        self.mode = mode
        self.n_empty = n_empty
        self.erasures = erasures
        self.notes_written = notes_written
