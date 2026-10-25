"""Group-agnostic, two-phase logical solver that records every step's
specifics plus every alternative move available at that moment.

Phase 1 (direct): no pencil marks. Only placed digits (and, at a second tier,
a pointing/claiming deduction made in your head) are used to find singles.
Phase 2 (notes): entered the first time phase 1 is blocked, via a TakeNotes
event (writing every candidate). Then candidate-based techniques.

Each move carries a compact feature tuple consumed by scoring.Scorer:
    (tech, base_shape, cover, extra)
cover = tuple of (kind, shape, uncovered_before) -- the set-cover sequence
used to find a single (naked: covering digits with groups; hidden: covering
cells with crosshatch sources), in the order a human would plausibly add them.
"""
from __future__ import annotations

from itertools import combinations

from .model import Puzzle, bit, popcount, digits_of

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
SHORT_TRIAL = 61   # bounded case split on a bivalue cell (contradiction within <= 4 direct rounds)
MENTAL_CHAIN = 62  # short chain (<= 5 links) reasoned without notes, ending in a single
EITHER_WAY = 63    # both options of a two-way choice agree on a placement / elimination
LINE_CLASS = 64    # line reasoning on digit classes (high/low, parity, thirds, mod 3)
DIGIT_COUNT = 65   # positional set logic for one digit (must-contain units vs at-most-once groups)
EQUAL_DIGITS = 66  # abstract colouring: two cells forced to hold the same unknown digit
LINE_SCAN = 67     # line consistency on 3-cell windows (local scan of a long line)
# forcing chains (k-way cell / unit case analysis; C++ only)
FORCING = 68         # basic propagation in the branches (singles, relations, rules)
DYN_FORCING = 69     # dynamic: the engine's techniques up to a ceiling in the branches
NESTED_FORCING = 70  # nested II: forcing chains inside the branches
MEDUSA = 71          # 3D Medusa (multi-digit colouring)
SUM_BOUND = 72       # min / max (triangular number) bounds of sum rules
CLASS_COUNT = 73     # odd / even, low / middle / high counting; sum parity
DOMINO = 74          # relation dominoes (kropki, XV, difference): must-contain digit, 2-domino locks
COLOUR_ALGEBRA = 75  # abstract-digit colour classes (cells that hold the same unknown digit)
N_WING = 76          # WXYZ / VWXYZ wings (bent sets)
SUE_DE_COQ = 77
APE = 78             # aligned pair exclusion
CHUTE_RP = 79        # chute remote pairs
POM = 80             # pattern overlay method
GURTH = 81           # Gurth's symmetrical placement theorem (assumes a unique solution)
NISHIO = 82          # single-digit forcing net
WHAT_IF = 83         # human "what if": two-way case split followed with light logic (bounded)
MENTAL_NOTES = 84    # single after notes logic done in the head (on the no-notes mental view)
MULTI_COLOR = 85     # multi-colouring: two single-digit colour clusters interacting
REMOTE_PAIRS = 86    # XY-chain of identical bivalue pairs (own code: priced apart from XY-Chain)
EMPTY_RECT = 87      # empty rectangle (grouped X-chain through a box; own code)
RULE_INTERSECT = 88  # two rules / houses taken together (joint digit combinations over their cells)
SUM_ALGEBRA = 89     # interval algebra over unit sums in a band / stack (house totals, cages, segments)
SNYDER_MARKS = 90    # writing Snyder marks (params notes_mode = "snyder"), priced per mark like TakeNotes
SNYDER_D = 91        # a placement read from Snyder marks (hidden pair / box-line X-wing from Snyder pairs)
BAND_LOGIC = 92      # a band's lines + boxes + the rules inside taken together (C++ only; sub-puzzle consistency)
FIREWORKS = 93       # Stuart's Fireworks (C++ only): three digits confined to a cell + one row cell + one column cell
HUMAN_CASE = 94      # bounded human case analysis (C++ only): refutation / cell / house forcing with rule rounds
COMBO_POS = 95       # combination-aware positions (C++ only): a cage's fillings cap a digit set inside a house
CLIQUE_HOUSE = 96    # clique house (C++ only): pairwise-different cells (houses, anti-knight, relations) as a house
LINE_SETS = 97       # line digit sets across lines (C++ only): renbans meeting a house choose disjoint digit sets there
LINE_CLUES = 98      # outside clues together (C++ only): a line with >= 2 sandwich / x-sum / skyscraper clues as one unit
WEIGHTED_SUMS = 99   # weighted multi-house sums (C++ only): integer combinations of sum facts down to 1-3 cells
NOTE_TECHS = (TAKE_NOTES, SNYDER_MARKS)  # writing steps: time = t_mark x marks written
NEW_TECHS = {SUM_COMBO, ARROW_COMBO, SET_COMBO, EQSUM_COMBO, TABLE_COMBO, COMBO_LOCK, NARY_D, INNIE_X,
             FINNED_FISH, JELLYFISH, X_CHAIN, XY_CHAIN, AIC_CHAIN, NICE_LOOP,
             SANDWICH_COMBO, XSUM_COMBO, SKYLINE_COMBO, LOL_COMBO, IMPLIED,
             UNIQUE_RECT, BUG_PLUS1, ALS_XZ, ALS_XYWING, DEATH_BLOSSOM, ALS_AIC, CANONICAL, COUNT_COMBO,
             LINE_D, LINE_RANGE, MENTAL_D, SHORT_TRIAL, MENTAL_CHAIN, EITHER_WAY, LINE_CLASS,
             DIGIT_COUNT, EQUAL_DIGITS, LINE_SCAN, FORCING, DYN_FORCING, NESTED_FORCING,
             MEDUSA, SUM_BOUND, CLASS_COUNT, DOMINO, COLOUR_ALGEBRA, N_WING, SUE_DE_COQ, APE, CHUTE_RP,
             POM, GURTH, NISHIO, WHAT_IF, MENTAL_NOTES, MULTI_COLOR, REMOTE_PAIRS, EMPTY_RECT, RULE_INTERSECT, SUM_ALGEBRA, SNYDER_MARKS, SNYDER_D, BAND_LOGIC, FIREWORKS, HUMAN_CASE, COMBO_POS, CLIQUE_HOUSE, LINE_SETS, LINE_CLUES, WEIGHTED_SUMS}

TECH_NAMES = {
    FULL_HOUSE: "FullHouse", NAKED_D: "NakedSingle(direct)", HIDDEN_D: "HiddenSingle(direct)",
    NAKED_DL: "NakedSingle+Pointing(direct)", HIDDEN_DL: "HiddenSingle+Pointing(direct)",
    TAKE_NOTES: "TakeNotes", NAKED_N: "NakedSingle(notes)", HIDDEN_N: "HiddenSingle(notes)",
    LOCKED: "LockedCandidates", NPAIR: "NakedPair", HPAIR: "HiddenPair", NTRIPLE: "NakedTriple",
    HTRIPLE: "HiddenTriple", NQUAD: "NakedQuad", HQUAD: "HiddenQuad", XWING: "X-Wing",
    SWORDFISH: "Swordfish", XYWING: "XY-Wing", XYZWING: "XYZ-Wing", COLORING: "Coloring",
    PAIRARC: "PairwiseConstraint", TRIAL: "Trial", GUESS: "Guess",
    INNIE_D: "Innie/Outie(direct)", CAGE_COMBO: "CageCombination", INNIE_N: "Innie/Outie(notes)",
    SUM_COMBO: "SumCombination", ARROW_COMBO: "ArrowCombination", SET_COMBO: "SetCombination",
    EQSUM_COMBO: "EqualSumCombination", TABLE_COMBO: "TableCombination", COMBO_LOCK: "ComboLock",
    NARY_D: "ConstraintSingle(direct)", INNIE_X: "Innie/Outie(sum)",
    FINNED_FISH: "FinnedFish", JELLYFISH: "Jellyfish", X_CHAIN: "X-Chain", XY_CHAIN: "XY-Chain",
    AIC_CHAIN: "AIC", NICE_LOOP: "NiceLoop(discontinuous)",
    SANDWICH_COMBO: "SandwichCombination", XSUM_COMBO: "XSumCombination", SKYLINE_COMBO: "SkyscraperCombination",
    LOL_COMBO: "LawOfLeftovers", IMPLIED: "ImpliedHouses", UNIQUE_RECT: "UniqueRectangle", BUG_PLUS1: "BUG+1",
    ALS_XZ: "ALS-XZ", ALS_XYWING: "ALS-XY-Wing", DEATH_BLOSSOM: "DeathBlossom", ALS_AIC: "ALS-AIC",
    CANONICAL: "CanonicalEnumeration", COUNT_COMBO: "CountCombination",
    LINE_D: "LineSingle(direct)", LINE_RANGE: "LineRange", MENTAL_D: "MentalSingle(direct)",
    SHORT_TRIAL: "ShortTrial", MENTAL_CHAIN: "MentalChain(direct)", EITHER_WAY: "EitherWay", LINE_CLASS: "LineClass",
    DIGIT_COUNT: "DigitCount", EQUAL_DIGITS: "EqualDigits", LINE_SCAN: "LineScan",
    FORCING: "ForcingChains", DYN_FORCING: "DynamicForcingChains", NESTED_FORCING: "NestedForcingChains",
    MEDUSA: "3DMedusa", SUM_BOUND: "SumBound", CLASS_COUNT: "ClassCount", DOMINO: "Domino",
    COLOUR_ALGEBRA: "ColourAlgebra", N_WING: "WXYZ-Wing", SUE_DE_COQ: "SueDeCoq", APE: "AlignedPairExclusion",
    CHUTE_RP: "ChuteRemotePairs", POM: "PatternOverlay", GURTH: "GurthSymmetry", NISHIO: "NishioForcingNet",
    WHAT_IF: "WhatIf", MENTAL_NOTES: "MentalNotesSingle", MULTI_COLOR: "MultiColouring",
    REMOTE_PAIRS: "RemotePairs", EMPTY_RECT: "EmptyRectangle", RULE_INTERSECT: "RuleIntersection", SUM_ALGEBRA: "SumAlgebra", SNYDER_MARKS: "SnyderMarks", SNYDER_D: "SnyderSingle", BAND_LOGIC: "BandLogic", FIREWORKS: "Fireworks", HUMAN_CASE: "CaseAnalysis", COMBO_POS: "ComboPositions", CLIQUE_HOUSE: "CliqueHouse", LINE_SETS: "LineSets", LINE_CLUES: "LineClues", WEIGHTED_SUMS: "WeightedSums",
}
DIRECT_TECHS = {FULL_HOUSE, NAKED_D, HIDDEN_D, NAKED_DL, HIDDEN_DL, INNIE_D, NARY_D, LINE_D, MENTAL_D, MENTAL_CHAIN}

# cover-source kinds
K_HOUSE, K_CAGE, K_NEQ, K_NONCONSEC, K_DOMAIN, K_LOCK, K_CAGESUM = 0, 1, 2, 3, 4, 5, 6
K_LINE, K_MENTAL = 7, 8   # C++ only: relation/line inference, mental subset (direct mode)

# notes-mode tiers, cheapest first; within the first non-empty tier every
# instance is enumerated (needed for the race model), cheapest is taken
NOTES_TIERS = [
    ("singles",),
    ("cagecombo",),
    ("locked", "pairarc", "innie"),
    ("pairs",),
    ("triples", "xwing", "xywing", "coloring"),
    ("quads", "swordfish", "xyzwing"),
    ("trial",),
]


class Move:
    __slots__ = ("feat", "place", "elim", "name", "d")

    def __init__(self, feat, place=None, elim=None, name="", meta=None):
        # meta: structural description for the meta-grader --
        # (cells, groups, digits, links, hidden, arith, relation, notes, spread)
        self.feat = feat + (meta,)  # (tech, base_shape, cover, extra, meta)
        self.place = place        # (cell, digit) or None
        self.elim = elim or ()    # ((cell, digit), ...)
        self.name = name
        self.d = None


def choice_key(m):
    """Canonical move choice: min difficulty rounded to 1e-9 (float noise must
    not decide ties -- it differs between CPython, PyPy and C++), then
    technique, placement, smallest elimination. Mirrored in csolver."""
    emin = min((c * 32 + v for c, v in m.elim), default=0xFFFFFFFF)
    pc, pv = m.place if m.place else (1 << 30, 0)
    return (round(m.d * 1e9), m.feat[0], pc, pv, emin, len(m.elim))


class Step:
    __slots__ = ("move", "alts", "mode", "n_empty", "erasures", "notes_written", "n_cands")

    def __init__(self, move, alts, mode, n_empty, erasures=0, notes_written=0, n_cands=None):
        self.n_cands = n_cands    # candidates left in the empty cells before the step (C++ solves; None otherwise)
        self.move = move
        self.alts = alts          # list of feature tuples for all moves in the tier (incl. chosen)
        self.mode = mode
        self.n_empty = n_empty
        self.erasures = erasures
        self.notes_written = notes_written


class Solver:
    def __init__(self, puzzle: Puzzle, scorer, max_steps=5000, allow_direct=True, disabled=(), solution=None):
        self.p = puzzle if hasattr(puzzle, "groups_of") else puzzle.finalize()
        self.sc = scorer
        self.max_steps = max_steps
        self.allow_direct = allow_direct
        self.disabled = set(disabled)
        self.solution = solution

    def _allowed(self, moves):
        return [m for m in moves if m.feat[0] not in self.disabled] if self.disabled else moves

    # ------------------------------------------------------------- state --
    def _init_state(self):
        p = self.p
        self.vals = [0] * p.N
        self.cand = list(p.domains)
        self.placed_g = [0] * len(p.groups)
        for c, v in p.givens.items():
            self._place(c, v, record=False)

    def _place(self, c, v, record=True):
        """Place v at c; basic candidate maintenance. Returns number of
        pencil-mark erasures a note-taker would make."""
        p = self.p
        self.vals[c] = v
        self.cand[c] = 0
        b = bit(v)
        erased = 0
        for gi in p.groups_of[c]:
            self.placed_g[gi] |= b
        for q in p.peer_list[c]:
            if self.cand[q] & b:
                self.cand[q] &= ~b
                erased += 1
        if p.nonconsec_list[c]:
            rex = p.rel_ex[c]
            for q in p.nonconsec_list[c]:
                nb = rex[q][v]
                if self.cand[q] & nb:
                    erased += popcount(self.cand[q] & nb)
                    self.cand[q] &= ~nb
        return erased

    def _empty_cells(self):
        return [c for c in range(self.p.N) if self.vals[c] == 0]

    # ------------------------------------------- direct (no-notes) view --
    def _direct_sources(self, c):
        """Exclusion sources visible at empty cell c without notes:
        list of (kind, shape, mask, ident)."""
        p = self.p
        out = []
        for gi in p.groups_of[c]:
            m = self.placed_g[gi]
            if m:
                g = p.groups[gi]
                out.append((K_HOUSE if g.complete else K_CAGE, g.shape, m, ("g", gi)))
        if p.neq[c]:
            m = 0
            for q in p.neq[c]:
                if self.vals[q]:
                    m |= bit(self.vals[q])
            if m:
                out.append((K_NEQ, 1.0, m, ("neq", c)))
        if p.nonconsec[c]:
            m = 0
            for q in p.nonconsec[c]:
                v = self.vals[q]
                if v:
                    m |= p.rel_ex[q][c][v]
            if m:
                out.append((K_NONCONSEC, 1.0, m, ("nc", c)))
        dom_ex = p.full & ~p.domains[c]
        if dom_ex:
            out.append((K_DOMAIN, 1.0, dom_ex, ("dom", c)))
        if p.has_cages:
            for gi in p.groups_of[c]:
                g = p.groups[gi]
                if g.total is not None:
                    m = p.full & ~self._cagesum_direct(gi) & ~self.placed_g[gi]
                    if m:
                        out.append((K_CAGESUM, g.shape, m, ("cs", gi)))
        return out

    def _direct_excl(self, empties):
        p = self.p
        ex = {}
        for c in empties:
            m = p.full & ~p.domains[c]
            for gi in p.groups_of[c]:
                m |= self.placed_g[gi]
            for q in p.neq[c]:
                if self.vals[q]:
                    m |= bit(self.vals[q])
            for q in p.nonconsec[c]:
                v = self.vals[q]
                if v:
                    m |= p.rel_ex[q][c][v]
            if p.has_cages:
                for gi in p.groups_of[c]:
                    if p.groups[gi].total is not None:
                        m |= p.full & ~self._cagesum_direct(gi)
            ex[c] = m
        return ex

    def _naked_cover(self, c, sources, D):
        """Minimal group combination leaving one digit (the C# Gosper search),
        then ordered most-solved-first; returns (base_shape, cover)."""
        target = popcount(self.p.full) - 1
        srcs = sources
        found = None
        for k in range(1, len(srcs) + 1):
            for combo in combinations(srcs, k):
                m = 0
                for s in combo:
                    m |= s[2]
                if popcount(m) >= target:
                    found = combo
                    break
            if found:
                break
        if not found:
            return None
        order = sorted(found, key=lambda s: -popcount(s[2]))
        cover = []
        m = order[0][2]
        for s in order[1:]:
            remaining = D - popcount(m)
            cover.append((s[0], s[1], remaining))
            m |= s[2]
        return order[0][1], tuple(cover)

    def _hidden_cover(self, target_cells, sources):
        """Cover the other empty cells of the house with crosshatch sources;
        sources: dict ident -> (kind, shape, frozenset(cells covered))."""
        items = set(target_cells)
        if not items:
            return ()
        srcs = [s for s in sources.values() if s[2] & items]
        chosen = None
        if len(srcs) <= 12:
            for k in range(1, len(srcs) + 1):
                for combo in combinations(srcs, k):
                    u = set()
                    for s in combo:
                        u |= s[2]
                    if items <= u:
                        chosen = combo
                        break
                if chosen:
                    break
        if chosen is None:  # greedy for big boards
            left, chosen = set(items), []
            while left:
                best = max(srcs, key=lambda s: len(s[2] & left))
                if not best[2] & left:
                    return None
                chosen.append(best)
                left -= best[2]
        order = sorted(chosen, key=lambda s: -len(s[2] & items))
        cover, left = [], set(items)
        for s in order:
            cover.append((s[0], s[1], len(left)))
            left -= s[2]
        return tuple(cover)

    def _direct_moves(self, locks=None):
        """All direct singles. If locks is given (cell -> (mask, list of lock
        idents)), virtual pointing/claiming exclusions are included and only
        moves that NEED them are returned."""
        p, D = self.p, self.p.D
        empties = self._empty_cells()
        ex = self._direct_excl(empties)
        if locks:
            ex2 = {c: ex[c] | locks.get(c, (0, None))[0] for c in empties}
        else:
            ex2 = ex
        moves = []
        seen = set()
        # full house
        if not locks:
            for hi in p.houses:
                g = p.groups[hi]
                emp = [c for c in g.cells if self.vals[c] == 0]
                if len(emp) == 1:
                    c = emp[0]
                    v = next(digits_of(p.full & ~self.placed_g[hi]))
                    if (c, v) in seen:
                        continue
                    seen.add((c, v))
                    moves.append(Move((FULL_HOUSE, g.shape, (), 0), (c, v), name=f"{g.name}",
                                      meta=(len(g.cells), 1, 1, 0, 0, 0, 0, 0, g.shape)))
        # naked singles
        for c in empties:
            rem = p.full & ~ex2[c]
            if popcount(rem) != 1:
                continue
            if locks and popcount(p.full & ~ex[c]) == 1:
                continue
            v = next(digits_of(rem))
            if (c, v) in seen:
                continue
            srcs = self._direct_sources(c)
            if locks and c in locks:
                for lk in locks[c][1]:
                    srcs.append((K_LOCK, lk[1], lk[2], lk[0]))
            cov = self._naked_cover(c, srcs, D)
            if cov is None:
                continue
            seen.add((c, v))
            kinds = {k for k, _, _ in cov[1]}
            moves.append(Move((NAKED_DL if locks else NAKED_D, cov[0], cov[1], 0), (c, v),
                              meta=(1, len(cov[1]) + 1, 1, 1 if locks else 0, 0, int(K_CAGESUM in kinds),
                                    int(bool(kinds & {K_NEQ, K_NONCONSEC})), 0, cov[0])))
        # hidden singles
        for hi in p.houses:
            g = p.groups[hi]
            emp = [c for c in g.cells if self.vals[c] == 0]
            if len(emp) < 2:
                continue
            for v in digits_of(p.full & ~self.placed_g[hi]):
                b = bit(v)
                poss = [c for c in emp if not ex2[c] & b]
                if len(poss) != 1:
                    continue
                c = poss[0]
                if locks and len([x for x in emp if not ex[x] & b]) == 1:
                    continue
                if (c, v) in seen:
                    continue
                others = [x for x in emp if x != c]
                srcs = self._hidden_sources(others, v, g, locks)
                cov = self._hidden_cover(others, srcs)
                if cov is None:
                    continue
                seen.add((c, v))
                kinds = {k for k, _, _ in cov}
                moves.append(Move((HIDDEN_DL if locks else HIDDEN_D, g.shape, cov, len(others)), (c, v),
                                  name=g.name,
                                  meta=(1 + len(others), 1 + len(cov), 1, 1 if locks else 0, 1,
                                        int(K_CAGESUM in kinds), int(bool(kinds & {K_NEQ, K_NONCONSEC})),
                                        0, g.shape)))
        return moves

    def _hidden_sources(self, cells, v, house, locks):
        p = self.p
        b = bit(v)
        srcs = {}
        for y in cells:
            for gi in p.groups_of[y]:
                gg = p.groups[gi]
                if gg is house or not self.placed_g[gi] & b:
                    continue
                key = ("g", gi)
                if key not in srcs:
                    srcs[key] = (K_HOUSE if gg.complete else K_CAGE, gg.shape,
                                 frozenset(gg.cells))
            for q in p.neq[y]:
                if self.vals[q] == v:
                    srcs[("neq", q)] = (K_NEQ, 1.0, frozenset(p.neq[q]))
            for q in p.nonconsec[y]:
                if self.vals[q] and p.rel_ex[q][y][self.vals[q]] & b:
                    srcs[("nc", q)] = (K_NONCONSEC, 1.0, frozenset(p.nonconsec[q]))
            if not p.domains[y] & b:
                srcs[("dom", y)] = (K_DOMAIN, 1.0, frozenset([y]))
            if p.has_cages:
                for gi in p.groups_of[y]:
                    gg = p.groups[gi]
                    if gg.total is not None and not self._cagesum_direct(gi) & b:
                        srcs[("cs", gi)] = (K_CAGESUM, gg.shape, frozenset(gg.cells))
            if locks and y in locks:
                for lk in locks[y][1]:
                    if lk[2] & b:
                        srcs.setdefault(lk[0], (K_LOCK, lk[1], frozenset(lk[3])))
        return srcs

    def _direct_locks(self):
        """Pointing/claiming done in your head: digit v's directly-possible
        cells in group B all lie in group A -> v excluded from A minus B."""
        p = self.p
        empties = self._empty_cells()
        ex = self._direct_excl(empties)
        locks = {}
        for bi in p.houses:
            B = p.groups[bi]
            emp = [c for c in B.cells if self.vals[c] == 0]
            if len(emp) < 3:
                continue
            for v in digits_of(p.full & ~self.placed_g[bi]):
                b = bit(v)
                poss = [c for c in emp if not ex[c] & b]
                if len(poss) < 2:
                    continue
                common = set(p.groups_of[poss[0]])
                for c in poss[1:]:
                    common &= set(p.groups_of[c])
                common.discard(bi)
                for ai in common:
                    A = p.groups[ai]
                    targets = [c for c in A.cells if self.vals[c] == 0 and c not in B.cells and not ex[c] & b]
                    if not targets:
                        continue
                    ident = ("lock", bi, ai, v)
                    for c in targets:
                        m, lst = locks.get(c, (0, []))
                        lst.append((ident, B.shape, b, targets))
                        locks[c] = (m | b, lst)
                # relation pointing: every possible spot for v relates to X
                for rel, generic in ((p.nonconsec, True), (p.neq, False)):
                    if not rel[poss[0]]:
                        continue
                    common_r = set(rel[poss[0]])
                    for c in poss[1:]:
                        common_r &= rel[c]
                    rms = {}
                    for x in common_r:
                        if self.vals[x] or x in poss:
                            continue
                        rm = p.full
                        if generic:
                            for c in poss:
                                rm &= p.rel_ex[c][x][v]
                        else:
                            rm = b
                        if rm & ~ex[x]:
                            rms[x] = rm
                    if not rms:
                        continue
                    targets = list(rms)
                    ident = ("rlock", bi, v, generic)
                    for x, rm in rms.items():
                        m, lst = locks.get(x, (0, []))
                        lst.append((ident, B.shape, rm, targets))
                        locks[x] = (m | rm, lst)
        return locks

    def _consec_mask(self, v):
        return (bit(v - 1) if v > 1 else 0) | (bit(v + 1) if v < self.p.D else 0)

    # ------------------------------------------------------- notes view --
    def _notes_singles(self):
        p = self.p
        moves, seen = [], set()
        for c in range(p.N):
            if self.vals[c] == 0 and popcount(self.cand[c]) == 1:
                v = next(digits_of(self.cand[c]))
                seen.add((c, v))
                moves.append(Move((NAKED_N, 1.0, (), 0), (c, v), meta=(1, 1, 1, 0, 0, 0, 0, 1, 1.0)))
        for hi in p.houses:
            g = p.groups[hi]
            emp = [c for c in g.cells if self.vals[c] == 0]
            for v in digits_of(p.full & ~self.placed_g[hi]):
                b = bit(v)
                poss = [c for c in emp if self.cand[c] & b]
                if len(poss) == 1 and (poss[0], v) not in seen:
                    seen.add((poss[0], v))
                    moves.append(Move((HIDDEN_N, g.shape, (), len(emp)), (poss[0], v), name=g.name,
                                      meta=(len(emp), 1, 1, 0, 1, 0, 0, 1, g.shape)))
        return moves

    def _locked(self):
        p = self.p
        moves = []
        for bi in p.houses:
            B = p.groups[bi]
            for v in digits_of(p.full & ~self.placed_g[bi]):
                b = bit(v)
                poss = [c for c in B.cells if self.vals[c] == 0 and self.cand[c] & b]
                if len(poss) < 2:
                    continue
                common = set(p.groups_of[poss[0]])
                for c in poss[1:]:
                    common &= set(p.groups_of[c])
                common.discard(bi)
                for ai in common:
                    A = p.groups[ai]
                    el = tuple((c, v) for c in A.cells if c not in B.cells and self.cand[c] & b)
                    if el:
                        moves.append(Move((LOCKED, (B.shape * A.shape) ** 0.5, (), len(poss)), None, el,
                                          name=f"{B.name}->{A.name}",
                                          meta=(len(poss), 2, 1, 0, 1, int(A.total is not None), 0, 1,
                                                (B.shape * A.shape) ** 0.5)))
        return moves

    def _subsets(self, k):
        p = self.p
        moves = []
        nt, ht = {2: (NPAIR, HPAIR), 3: (NTRIPLE, HTRIPLE), 4: (NQUAD, HQUAD)}[k]
        for hi in p.houses:
            g = p.groups[hi]
            emp = [c for c in g.cells if self.vals[c] == 0]
            if len(emp) <= k:
                continue
            small = [c for c in emp if 2 <= popcount(self.cand[c]) <= k]
            for combo in combinations(small, k):
                u = 0
                for c in combo:
                    u |= self.cand[c]
                if popcount(u) == k:
                    el = tuple((c, d) for c in emp if c not in combo for d in digits_of(self.cand[c] & u))
                    if el:
                        moves.append(Move((nt, g.shape, (), len(emp)), None, el, name=g.name,
                                          meta=(k, 1, k, 0, 0, 0, 0, 1, g.shape)))
            missing = list(digits_of(p.full & ~self.placed_g[hi]))
            pos = {d: frozenset(c for c in emp if self.cand[c] & bit(d)) for d in missing}
            cands = [d for d in missing if 2 <= len(pos[d]) <= k]
            for combo in combinations(cands, k):
                cells = frozenset().union(*(pos[d] for d in combo))
                if len(cells) == k:
                    keep = 0
                    for d in combo:
                        keep |= bit(d)
                    el = tuple((c, d) for c in cells for d in digits_of(self.cand[c] & ~keep))
                    if el:
                        moves.append(Move((ht, g.shape, (), len(emp)), None, el, name=g.name,
                                          meta=(k, 1, k, 0, 1, 0, 0, 1, g.shape)))
        return moves

    def _fish(self, k):
        p = self.p
        tech = XWING if k == 2 else SWORDFISH
        moves = []
        houses = p.houses
        hcells = {hi: frozenset(p.groups[hi].cells) for hi in houses}
        for v in range(1, p.D + 1):
            b = bit(v)
            pos = {hi: frozenset(c for c in hcells[hi] if self.vals[c] == 0 and self.cand[c] & b) for hi in houses}
            bases = [hi for hi in houses if 2 <= len(pos[hi]) <= k]
            for combo in combinations(bases, k):
                if any(hcells[a] & hcells[b2] for a, b2 in combinations(combo, 2)):
                    continue
                U = frozenset().union(*(pos[h] for h in combo))
                covers = [hi for hi in houses if hi not in combo and pos[hi] & U]
                for cov in combinations(covers, k):
                    if any(hcells[a] & hcells[b2] for a, b2 in combinations(cov, 2)):
                        continue
                    CU = frozenset().union(*(hcells[h] for h in cov))
                    if not U <= CU:
                        continue
                    el = tuple((c, v) for h in cov for c in pos[h] if c not in U)
                    if el:
                        shp = sum(p.groups[h].shape for h in combo + cov) / (2 * k)
                        moves.append(Move((tech, shp, (), k), None, tuple(set(el)),
                                          meta=(len(U), 2 * k, 1, 0, 1, 0, 0, 1, shp)))
        return moves

    def _xywing(self, xyz=False):
        p = self.p
        from .model import shape_ratio
        moves = []
        need = 3 if xyz else 2
        for piv in range(p.N):
            if self.vals[piv] or popcount(self.cand[piv]) != need:
                continue
            pc = self.cand[piv]
            wings = [q for q in p.peer_list[piv] if self.vals[q] == 0 and popcount(self.cand[q]) == 2]
            for w1, w2 in combinations(wings, 2):
                a, b2 = self.cand[w1], self.cand[w2]
                if xyz:
                    if not (a | b2) == pc or a == b2 or not (a & pc) == a or not (b2 & pc) == b2:
                        continue
                    z = a & b2
                    if popcount(z) != 1:
                        continue
                    targets = p.peers[piv] & p.peers[w1] & p.peers[w2]
                else:
                    if a == b2 or popcount(a & b2) != 1:
                        continue
                    z = a & b2
                    if (a | b2) & ~z != pc or pc & z:
                        continue
                    targets = p.peers[w1] & p.peers[w2]
                el = tuple((c, next(digits_of(z))) for c in targets
                           if c not in (piv, w1, w2) and self.vals[c] == 0 and self.cand[c] & z)
                if el:
                    shp = shape_ratio([p.coords[c] for c in (piv, w1, w2)])
                    moves.append(Move((XYZWING if xyz else XYWING, shp, (), 0), None, el,
                                      meta=(3, 3 if xyz else 2, 3, 2, 0, 0, 0, 1, shp)))
        return moves

    def _coloring(self):
        """Single-digit coloring over strong links (houses with exactly two
        candidate cells): color trap + color wrap."""
        p = self.p
        moves = []
        for v in range(1, p.D + 1):
            b = bit(v)
            adj = {}
            for hi in p.houses:
                cells = [c for c in p.groups[hi].cells if self.vals[c] == 0 and self.cand[c] & b]
                if len(cells) == 2:
                    x, y = cells
                    adj.setdefault(x, set()).add(y)
                    adj.setdefault(y, set()).add(x)
            color = {}
            for start in adj:
                if start in color:
                    continue
                comp = {start: 0}
                stack = [start]
                while stack:
                    x = stack.pop()
                    for y in adj[x]:
                        if y not in comp:
                            comp[y] = 1 - comp[x]
                            stack.append(y)
                color.update(comp)
                if len(comp) < 4:
                    continue
                groups = ([c for c in comp if comp[c] == 0], [c for c in comp if comp[c] == 1])
                el = []
                for side in (0, 1):  # wrap: two same-colored cells see each other
                    s = groups[side]
                    if any(q in p.peers[x] for x, q in combinations(s, 2)):
                        el = [(c, v) for c in s]
                        break
                if not el:  # trap
                    for c in range(p.N):
                        if self.vals[c] or c in comp or not self.cand[c] & b:
                            continue
                        if p.peers[c] & set(groups[0]) and p.peers[c] & set(groups[1]):
                            el.append((c, v))
                if el:
                    from .model import shape_ratio as _sr
                    moves.append(Move((COLORING, 1.0, (), len(comp)), None, tuple(el),
                                      meta=(len(comp), len(comp) - 1, 1, len(comp) - 1, 1, 0, 0, 1,
                                            _sr([p.coords[c] for c in comp]))))
        return moves

    def _relation_pointing(self):
        """Notes version: all candidate spots of v in house B relate (non-
        consecutive / anti-knight) to cell X -> apply the relation to X."""
        p = self.p
        moves = []
        for bi in p.houses:
            B = p.groups[bi]
            for v in digits_of(p.full & ~self.placed_g[bi]):
                b = bit(v)
                poss = [c for c in B.cells if self.vals[c] == 0 and self.cand[c] & b]
                if len(poss) < 2:
                    continue
                for rel, generic in ((p.nonconsec, True), (p.neq, False)):
                    if not rel[poss[0]]:
                        continue
                    common = set(rel[poss[0]])
                    for c in poss[1:]:
                        common &= rel[c]
                    el = []
                    for x in common:
                        if self.vals[x] or x in poss:
                            continue
                        rm = b
                        if generic:
                            rm = p.full
                            for c in poss:
                                rm &= p.rel_ex[c][x][v]
                        el.extend((x, d) for d in digits_of(self.cand[x] & rm))
                    el = tuple(el)
                    if el:
                        moves.append(Move((PAIRARC, B.shape, (), len(poss)), None, el, name=B.name,
                                          meta=(len(poss) + 1, 2, 1, 0, 1, 0, 1, 1, B.shape)))
        return moves

    def _pairarc(self):
        """Pairwise-relation pressure (non-consecutive): v can't go in b if
        every candidate of neighbour a is consecutive to v."""
        p = self.p
        moves = self._relation_pointing()
        for a in range(p.N):
            if self.vals[a] or not p.nonconsec[a]:
                continue
            ca = self.cand[a]
            for b_ in p.nonconsec[a]:
                if self.vals[b_]:
                    continue
                el = []
                for v in digits_of(self.cand[b_]):
                    nb = p.rel_ex[b_][a][v]
                    if ca and ca & ~nb == 0:
                        el.append((b_, v))
                if el:
                    moves.append(Move((PAIRARC, 1.0, (), popcount(ca)), None, tuple(el),
                                      meta=(2, 1, min(popcount(ca) + 1, p.D), 0, 0, 0, 1, 1, 1.0)))
        return moves

    # ------------------------------------------------------ killer cages --
    def _sum_cages(self):
        if not hasattr(self, "_sc_list"):
            self._sc_list = [gi for gi, g in enumerate(self.p.groups) if g.total is not None]
        return self._sc_list

    def _combo_allowed(self, cells, total, distinct=True, cell_masks=None, forbid=0):
        """Per-cell allowed digits for `cells` summing to `total`.
        cell_masks: per-cell candidate masks (notes); None = any digit."""
        p = self.p
        k = len(cells)
        masks = cell_masks or [p.full & ~forbid] * k
        allowed = [0] * k
        if distinct:
            pool = [d for d in range(1, p.D + 1) if not forbid & bit(d)]
            for combo in combinations(pool, k):
                if sum(combo) != total:
                    continue
                # assignment check: permutations restricted by masks (k small)
                self._assign(combo, masks, allowed)
        else:
            # non-distinct: DP over cells
            reach = [{0}]
            for m in masks:
                reach.append({s + d for s in reach[-1] for d in digits_of(m) if s + d <= total})
            back = {total}
            for i in range(k - 1, -1, -1):
                ok = set()
                for d in digits_of(masks[i]):
                    for s in back:
                        if s - d in reach[i]:
                            allowed[i] |= bit(d)
                            ok.add(s - d)
                back = ok
        return allowed

    def _assign(self, combo, masks, allowed):
        k = len(combo)
        used = [False] * k
        partial = [0] * k

        def rec(i):
            if i == k:
                for j in range(k):
                    allowed[j] |= bit(partial[j])
                return True
            found = False
            for t in range(k):
                if not used[t] and masks[i] & bit(combo[t]):
                    used[t] = True
                    partial[i] = combo[t]
                    found |= rec(i + 1)
                    used[t] = False
            return found

        rec(0)

    def _cagesum_direct(self, gi):
        """Digits a cage's empty cells can hold given only its total and its
        placed digits (what a no-notes killer solver reads off the cage)."""
        cache = self.__dict__.setdefault("_cs_cache", {})
        key = (gi, self.placed_g[gi])
        if key in cache:
            return cache[key]
        g = self.p.groups[gi]
        emp = [c for c in g.cells if self.vals[c] == 0]
        rem = g.total - sum(self.vals[c] for c in g.cells)
        allowed = 0
        if emp:
            for m in self._combo_allowed(emp, rem, forbid=self.placed_g[gi]):
                allowed |= m
        cache[key] = allowed
        return allowed

    def _innie_sets(self):
        """Rule-of-45 sets per house: (house, cells, sum, cages_used, kind)."""
        p = self.p
        tri = p.D * (p.D + 1) // 2
        out = []
        sums = self._sum_cages()
        if not sums:
            return out
        for union in self._house_unions():
            H = set().union(*(p.groups[h].cells for h in union))
            hi = union[0]
            tri_u = tri * len(union)
            inside, touching = [], []
            for gi in sums:
                cs = set(p.groups[gi].cells)
                if cs <= H:
                    inside.append(gi)
                elif cs & H:
                    touching.append(gi)
            covered = set().union(*(p.groups[gi].cells for gi in inside)) if inside else set()
            R = sorted(c for c in H if c not in covered)
            if R and len(R) <= 4 and inside:
                total = tri_u - sum(p.groups[gi].total for gi in inside)
                out.append((hi, R, total, inside, "innie"))
            allc = inside + touching
            cov_all = set().union(*(p.groups[gi].cells for gi in allc)) if allc else set()
            if H <= cov_all and touching:
                O = sorted(cov_all - H)
                if len(O) <= 4:
                    total = sum(p.groups[gi].total for gi in allc) - tri_u
                    out.append((hi, O, total, allc, "outie"))
        return out

    def _house_unions(self, max_k=3):
        """Connected sets of up to max_k pairwise-disjoint, orthogonally
        adjacent houses (two/three adjacent rows, boxes in a band, adjacent
        jigsaw regions...) -- group-agnostic rule-of-45 regions."""
        p = self.p
        hs = p.houses
        cellsets = {h: set(p.groups[h].cells) for h in hs}
        pos = {xy: i for i, xy in enumerate(p.coords)}
        nb = {}
        for h in hs:
            border = set()
            for c in cellsets[h]:
                r, cc = p.coords[c]
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = pos.get((r + dr, cc + dc))
                    if q is not None and q not in cellsets[h]:
                        border.add(q)
            nb[h] = {h2 for h2 in hs if h2 != h and not cellsets[h] & cellsets[h2] and cellsets[h2] & border}
        out = {(h,) for h in hs}
        frontier = set(out)
        for _ in range(max_k - 1):
            nxt = set()
            for u in frontier:
                for h in u:
                    for h2 in nb[h]:
                        if h2 in u or any(cellsets[h2] & cellsets[x] for x in u):
                            continue
                        nxt.add(tuple(sorted(u + (h2,))))
            out |= nxt
            frontier = nxt
        return sorted(out, key=len)

    def _innies(self, notes=False):
        p = self.p
        moves = []
        if not hasattr(self, "_innie_cache"):
            self._innie_cache = self._innie_sets()
        for hi, cells, total, cages, kind in self._innie_cache:
            emp = [c for c in cells if self.vals[c] == 0]
            if not emp:
                continue
            rem = total - sum(self.vals[c] for c in cells)
            cover = tuple((K_CAGESUM, p.groups[gi].shape, i + 1) for i, gi in enumerate(cages))
            H = p.groups[hi]
            if not notes:
                if len(emp) == 1 and 1 <= rem <= p.D:
                    moves.append(Move((INNIE_D, H.shape, cover, len(cages)), (emp[0], rem), name=f"{kind} {H.name}",
                                      meta=(sum(len(p.groups[gi].cells) for gi in cages), len(cages) + 1, 1, 0, 0,
                                            1, 0, 0, H.shape)))
                continue
            common = set(p.groups_of[emp[0]])
            for c in emp[1:]:
                common &= set(p.groups_of[c])
            distinct = bool(common)
            masks = [self.cand[c] for c in emp]
            allowed = self._combo_allowed(emp, rem, distinct=distinct, cell_masks=masks)
            el = tuple((c, d) for c, a in zip(emp, allowed) for d in digits_of(self.cand[c] & ~a))
            if el:
                moves.append(Move((INNIE_N, H.shape, (), len(cages)), None, el, name=f"{kind} {H.name}",
                                  meta=(sum(len(p.groups[gi].cells) for gi in cages), len(cages) + 1, len(emp),
                                        0, 0, 1, 0, 1, H.shape)))
        return moves

    def _cage_combo(self):
        p = self.p
        moves = []
        for gi in self._sum_cages():
            g = p.groups[gi]
            emp = [c for c in g.cells if self.vals[c] == 0]
            if not emp:
                continue
            rem = g.total - sum(self.vals[c] for c in g.cells)
            allowed = self._combo_allowed(emp, rem, cell_masks=[self.cand[c] for c in emp],
                                          forbid=self.placed_g[gi])
            el = tuple((c, d) for c, a in zip(emp, allowed) for d in digits_of(self.cand[c] & ~a))
            if el:
                moves.append(Move((CAGE_COMBO, g.shape, (), len(emp)), None, el, name=g.name,
                                  meta=(len(emp), 1, len(emp), 0, 0, 1, 0, 1, g.shape)))
        return moves

    def _trial(self):
        """Depth-1 trial on bivalue cells: assume a value, propagate singles;
        contradiction eliminates it."""
        p = self.p
        moves = []
        for c in range(p.N):
            if self.vals[c] or popcount(self.cand[c]) != 2:
                continue
            for v in digits_of(self.cand[c]):
                if self._contradicts(c, v):
                    moves.append(Move((TRIAL, 1.0, (), 0), None, ((c, v),)))
                    return moves
        return moves

    def _contradicts(self, c, v, max_iter=200):
        p = self.p
        vals, cand, placed_g = self.vals[:], self.cand[:], self.placed_g[:]
        sv = (self.vals, self.cand, self.placed_g)
        self.vals, self.cand, self.placed_g = vals, cand, placed_g
        try:
            self._place(c, v, record=False)
            for _ in range(max_iter):
                progress = False
                for x in range(p.N):
                    if self.vals[x] == 0:
                        if self.cand[x] == 0:
                            return True
                        if popcount(self.cand[x]) == 1:
                            self._place(x, next(digits_of(self.cand[x])), False)
                            progress = True
                for hi in p.houses:
                    for d in digits_of(p.full & ~self.placed_g[hi]):
                        poss = [x for x in p.groups[hi].cells if self.vals[x] == 0 and self.cand[x] & bit(d)]
                        if not poss:
                            return True
                if not progress:
                    return False
            return False
        finally:
            self.vals, self.cand, self.placed_g = sv

    def _notes_tier(self, tier):
        out = []
        for name in tier:
            if name == "singles":
                out += self._notes_singles()
            elif name == "locked":
                out += self._locked()
            elif name == "cagecombo":
                out += self._cage_combo()
            elif name == "innie":
                out += self._innies(notes=True)
            elif name == "pairarc":
                out += self._pairarc()
            elif name == "pairs":
                out += self._subsets(2)
            elif name == "triples":
                out += self._subsets(3)
            elif name == "quads":
                out += self._subsets(4)
            elif name == "xwing":
                out += self._fish(2)
            elif name == "swordfish":
                out += self._fish(3)
            elif name == "xywing":
                out += self._xywing(False)
            elif name == "xyzwing":
                out += self._xywing(True)
            elif name == "coloring":
                out += self._coloring()
            elif name == "trial":
                out += self._trial()
        return out

    # --------------------------------------------------------------- run --
    def solve(self):
        p = self.p
        self._init_state()
        steps = []
        mode = "direct" if self.allow_direct else "notes"
        if mode == "notes":
            steps.append(self._take_notes())
        for _ in range(self.max_steps):
            empties = self._empty_cells()
            if not empties:
                break
            n_empty = len(empties)
            if mode == "direct":
                moves = self._allowed(self._direct_moves())
                if not moves and p.has_cages:
                    moves = self._allowed(self._innies(notes=False))
                if not moves:
                    locks = self._direct_locks()
                    if locks:
                        moves = self._allowed(self._direct_moves(locks))
                if not moves:
                    if TAKE_NOTES in self.disabled:
                        break
                    mode = "notes"
                    steps.append(self._take_notes())
                    continue
            else:
                moves = []
                for tier in NOTES_TIERS:
                    moves = self._allowed(self._notes_tier(tier))
                    if moves:
                        break
                if not moves:
                    if GUESS in self.disabled:
                        break
                    moves = [self._guess()]
                    if moves[0] is None:
                        break
            for m in moves:
                m.d = self.sc.difficulty(m.feat, p.D)
            best = min(moves, key=choice_key)
            erasures = 0
            if best.place:
                erasures = self._place(*best.place)
            for c, v in best.elim:
                self.cand[c] &= ~bit(v)
            steps.append(Step(best, [m.feat for m in moves], mode, n_empty,
                              erasures if mode == "notes" else 0))
        self.solved = all(self.vals)
        return steps

    def _take_notes(self):
        written = sum(popcount(self.cand[c]) for c in range(self.p.N) if self.vals[c] == 0)
        m = Move((TAKE_NOTES, 1.0, (), written), None)
        m.d = self.sc.difficulty(m.feat, self.p.D)
        return Step(m, [m.feat], "notes", len(self._empty_cells()), notes_written=written)

    def _guess(self):
        if self.solution is not None:
            sol = [self.solution]
        else:
            sol = brute_solve(self.p, limit=1, start=(self.vals, self.cand))
        if not sol:
            return None
        c = min((x for x in range(self.p.N) if self.vals[x] == 0), key=lambda x: popcount(self.cand[x]))
        return Move((GUESS, 1.0, (), popcount(self.cand[c])), (c, sol[0][c]))


# ---------------------------------------------------------- brute force --

def brute_solve(p: Puzzle, limit=2, start=None, node_limit=2_000_000):
    """Count/collect solutions (up to `limit`) with MRV + singles propagation.
    Works on any group structure (houses/cages/relations/domains)."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    if start is None:
        s = Solver(p, None)
        s._init_state()
        vals, cand = s.vals[:], s.cand[:]
    else:
        vals, cand = start[0][:], start[1][:]
    sols = []
    nodes = [0]
    cage_groups = [g for g in p.groups if g.total is not None]

    def place(vals, cand, c, v):
        vals[c] = v
        cand[c] = 0
        b = bit(v)
        for q in p.peer_list[c]:
            cand[q] &= ~b
        if p.nonconsec_list[c]:
            rex = p.rel_ex[c]
            for q in p.nonconsec_list[c]:
                nb = rex[q][v]
                cand[q] &= ~nb

    def cages_ok(vals):
        for g in cage_groups:
            s = sum(vals[c] for c in g.cells)
            full = all(vals[c] for c in g.cells)
            if (full and s != g.total) or (not full and s >= g.total):
                return False
        return True

    def rec(vals, cand):
        nodes[0] += 1
        if nodes[0] > node_limit or len(sols) >= limit:
            return
        # propagate naked/hidden singles
        changed = True
        while changed:
            changed = False
            for c in range(p.N):
                if vals[c] == 0:
                    if cand[c] == 0:
                        return
                    if cand[c] & (cand[c] - 1) == 0:
                        place(vals, cand, c, cand[c].bit_length())
                        changed = True
            for hi in p.houses:
                g = p.groups[hi]
                seen = 0
                for c in g.cells:
                    seen |= cand[c] if vals[c] == 0 else bit(vals[c])
                if seen != p.full:
                    return
                for d in range(1, p.D + 1):
                    b = bit(d)
                    pos = [c for c in g.cells if (vals[c] == 0 and cand[c] & b) or vals[c] == d]
                    if len(pos) == 1 and vals[pos[0]] == 0:
                        place(vals, cand, pos[0], d)
                        changed = True
        if cage_groups:
            if not cages_ok(vals):
                return
            for g in cage_groups:  # sum bounds: prune digits that can't fit
                emp = [c for c in g.cells if vals[c] == 0]
                if not emp:
                    continue
                rem = g.total - sum(vals[c] for c in g.cells)
                k = len(emp)
                used = 0
                for c in g.cells:
                    if vals[c]:
                        used |= bit(vals[c])
                avail = [d for d in range(1, p.D + 1) if not used & bit(d)]
                if len(avail) < k:
                    return
                for c in emp:
                    keep = 0
                    for d in digits_of(cand[c]):
                        others = [x for x in avail if x != d]
                        lo = sum(others[:k - 1])
                        hi = sum(others[-(k - 1):]) if k > 1 else 0
                        if lo <= rem - d <= hi:
                            keep |= bit(d)
                    if keep == 0:
                        return
                    cand[c] = keep
        empties = [c for c in range(p.N) if vals[c] == 0]
        if not empties:
            sols.append(vals[:])
            return
        c = min(empties, key=lambda x: popcount(cand[x]))
        for v in list(digits_of(cand[c])):
            v2, c2 = vals[:], cand[:]
            place(v2, c2, c, v)
            rec(v2, c2)
            if len(sols) >= limit:
                return

    rec(vals, cand)
    return sols


def required_techniques(puzzle, scorer):
    """What you must know: the lowest technique ceiling (by fitted base
    difficulty, TakeNotes included as a gate) that still solves the puzzle
    without guessing -- SE's "hardest required technique", generalized --
    then within that ceiling drop techniques hardest-first while it stays
    solvable. Returns (tech codes used, steps of that solve)."""
    B = scorer.p["B"]
    techs = sorted((t for t in TECH_NAMES if t != GUESS), key=lambda t: (t == TRIAL, B.get(t, 99)))  # trial = last resort
    for k in range(1, len(techs) + 1):
        allowed = set(techs[:k])
        s = Solver(puzzle, scorer, disabled=set(TECH_NAMES) - allowed)
        steps = s.solve()
        if s.solved:
            break
    else:
        return None, []
    disabled = set(TECH_NAMES) - allowed
    used = sorted({st.move.feat[0] for st in steps}, key=lambda t: -B.get(t, 0))
    for t in used:
        if t == techs[k - 1]:
            continue  # the ceiling technique is needed by construction
        s2 = Solver(puzzle, scorer, disabled=disabled | {t})
        st2 = s2.solve()
        if s2.solved:
            disabled |= {t}
            steps = st2
    return sorted({st.move.feat[0] for st in steps}, key=lambda t: B.get(t, 0)), steps
