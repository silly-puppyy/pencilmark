"""Teachable explanations for grader moves.

    from pencilmark import cbackend as CB, explain as E
    steps, ok = CB.solve(p, P, solution=sol)
    for i, step, state in E.replay(p, steps):        # state = grid BEFORE the step
        ex = E.explain(step, p, state)
        print(ex["short"]); print(ex["teach"])

explain(step, puzzle, state) -> dict
    short       one line: "r4c7 = 3: the only place for a 3 in box 6"
    teach       2-5 sentences: where to look, why it works, what it achieves
    concept     {"family", "technique", "name", "lesson"} (reusable across puzzles)
    visual      cells / units / lines / chain links to highlight in a UI
    annotation  placeholders for human annotation
    justification   the structured reason the text was rendered from (schema below)
    derived     True when the justification was reconstructed here (not supplied by the engine)
    verified    True when the reconstructed pattern reproduces the move's placement / eliminations

Justification schema (the same keys are read from the engine's step.move.explain dict when the
engine exports one -- engine fields override derived ones, so richer data plugs straight in):
    technique, digits, placement (cell, digit), eliminations [(cell, digit)],
    base_units / cover_units [group index], base_cells / cover_cells / fins [cell],
    constraints [{"type", "index", "cells", "params"}], links [{"a": (c, d), "b": (c, d),
    "strong": bool, "source": "bivalue|bilocal|constraint|relation|cell|house", "unit": gi}],
    als [{"cells", "digits"}], rcc [digit], z digit, trial {"assume", "events", "contradiction"}.

The reconstruction works on the replayed grid (placed digits + candidates, the C++ engine's own
candidate maintenance), so it needs nothing but the step stream.
"""

from __future__ import annotations

import re
import zlib
from collections import defaultdict
from itertools import combinations

from . import registry as R
from . import solver as S
from .metrics import FAMILIES, family_of
from .model import bit, digits_of, popcount

ANNOTATION = {"human_text": None, "rating_clarity": None, "alt_explanation": None, "notes": None}

# ------------------------------------------------------------------ concepts --
CONCEPTS = {
    S.FULL_HOUSE: (
        "Full house",
        "When a row, column or box has a single empty cell, that cell takes the one digit "
        "the house is missing -- check for these after every placement.",
    ),
    S.NAKED_D: (
        "Naked single",
        "Pick one cell and collect every digit it can see in its row, column and box (and "
        "any extra rule); if all but one digit is ruled out, the last one goes in.",
    ),
    S.HIDDEN_D: (
        "Hidden single",
        "Pick a digit and a house and cross-hatch: if every cell but one is blocked for "
        "that digit, it must go in the remaining cell.",
    ),
    S.NAKED_DL: (
        "Single via pointing",
        "A digit that isn't placed yet can still block a line: if inside a box it is "
        "confined to one row or column, treat it as already there.",
    ),
    S.HIDDEN_DL: (
        "Hidden single via pointing",
        "Cross-hatch with 'virtual' digits too: a digit confined to one line "
        "of a box blocks that line elsewhere just like a placed digit.",
    ),
    S.TAKE_NOTES: (
        "Pencil marks",
        "When scanning dries up, write in the candidates; the next techniques work on those notes.",
    ),
    S.NAKED_N: ("Naked single (notes)", "A cell whose pencil marks are down to one candidate is solved."),
    S.HIDDEN_N: (
        "Hidden single (notes)",
        "If a digit appears in the notes of only one cell in a house, that cell is the digit.",
    ),
    S.LOCKED: (
        "Locked candidates (pointing / claiming)",
        "If inside one house a digit is confined to the overlap with "
        "a second house, the digit must be in the overlap -- remove it "
        "from the rest of the second house.",
    ),
    S.NPAIR: (
        "Naked pair",
        "Two cells of a house with the same two candidates own those two digits; nobody else "
        "in the house can have them.",
    ),
    S.HPAIR: (
        "Hidden pair",
        "If two digits can only go in the same two cells of a house, those cells are exactly "
        "those digits; clear their other notes.",
    ),
    S.NTRIPLE: (
        "Naked triple",
        "Three cells of a house whose notes use only three digits between them own those digits.",
    ),
    S.HTRIPLE: ("Hidden triple", "Three digits confined to the same three cells of a house fill those cells."),
    S.NQUAD: ("Naked quad", "Four cells with only four digits between them lock those digits in the house."),
    S.HQUAD: ("Hidden quad", "Four digits confined to the same four cells of a house fill those cells."),
    S.XWING: (
        "X-Wing",
        "If a digit's candidates in two rows sit in the same two columns, the digit takes one corner "
        "per row -- so it can't appear elsewhere in those columns (and vice versa).",
    ),
    S.SWORDFISH: (
        "Swordfish",
        "Three rows whose candidates for a digit fit inside three columns fill those columns' "
        "copies of the digit -- remove it from the rest of the columns.",
    ),
    S.JELLYFISH: ("Jellyfish", "The four-house version of the X-Wing / Swordfish idea."),
    S.FINNED_FISH: (
        "Finned fish",
        "A fish with an extra 'fin' candidate: either the fish works or the fin is true, "
        "so only cells that the fish would clear AND that see the fin lose the digit.",
    ),
    S.XYWING: (
        "XY-Wing",
        "A pivot XY sees wings XZ and YZ: whichever way the pivot goes, one wing becomes Z -- "
        "so any cell seeing both wings can't be Z.",
    ),
    S.XYZWING: (
        "XYZ-Wing",
        "Like an XY-Wing but the pivot also holds Z: one of the three cells is Z, so cells seeing all three lose Z.",
    ),
    S.COLORING: (
        "Simple colouring",
        "Follow one digit through houses where it has exactly two spots, alternating two "
        "colours; one colour is the truth. A cell seeing both colours can't hold the digit.",
    ),
    S.PAIRARC: (
        "Pair-rule pressure",
        "A rule between two cells (dot, whisper, non-consecutive, anti-knight...) can "
        "remove a candidate when every option of the partner clashes with it.",
    ),
    S.TRIAL: (
        "Trial and contradiction",
        "Assume a candidate and follow the forced consequences; if a rule breaks, "
        "the assumption was false. A last resort -- keep the chain short.",
    ),
    S.GUESS: (
        "Bifurcation (guess)",
        "When no logical step is found the solver commits to a value; good puzzles "
        "always have a reason, so treat this as a sign a technique is still missing.",
    ),
    S.INNIE_D: (
        "Innies and outies (rule of 45)",
        "A house sums to 45: subtract the cages lying fully inside it and "
        "what remains is the sum of the cells poking in or out.",
    ),
    S.CAGE_COMBO: (
        "Cage combinations",
        "List the digit sets that make the cage total with the notes available; "
        "a digit no surviving set can place in a cell is out.",
    ),
    S.INNIE_N: (
        "Innies and outies with notes",
        "The rule-of-45 leftover gives a small sum over a few cells; treat it as a virtual cage.",
    ),
    S.SUM_COMBO: ("Sum combinations", "A sum clue only allows certain digit sets; work out which still fit."),
    S.ARROW_COMBO: (
        "Arrow sums",
        "The digits on an arrow add up to its circle; bounds on either side squeeze the other.",
    ),
    S.SET_COMBO: (
        "Renban runs",
        "A renban holds a set of consecutive digits in any order; its length and its "
        "candidates fix which runs are possible.",
    ),
    S.EQSUM_COMBO: (
        "Equal sums",
        "Segments that must share a sum limit each other: a digit is out if its segment "
        "can't reach a sum the others can.",
    ),
    S.TABLE_COMBO: ("Allowed combinations", "Check each option against the list of combinations the rule allows."),
    S.COMBO_LOCK: (
        "Must-contain digits",
        "If every way to fill a cage or line uses a digit, that digit lives inside "
        "it -- and a house that can only put a digit inside it forces it in.",
    ),
    S.NARY_D: (
        "Completing a cage or line",
        "When a cage, arrow or line has one empty cell left, the arithmetic or the set rule often fixes it outright.",
    ),
    S.INNIE_X: (
        "Innies and outies (bigger regions)",
        "Rule-of-45 over several houses gives a derived sum over a handful of cells; solve it like a cage.",
    ),
    S.X_CHAIN: (
        "X-Chain",
        "A one-digit chain of alternating strong and weak links: one end must be the digit, so "
        "cells seeing both ends lose it.",
    ),
    S.XY_CHAIN: (
        "XY-Chain",
        "A chain through two-candidate cells: if the first cell isn't Z, the chain forces the last one to be Z.",
    ),
    S.AIC_CHAIN: (
        "Alternating inference chain",
        "Chain 'if not A then B' (strong) and 'if B then not C' (weak) links: the two ends can't both be false.",
    ),
    S.NICE_LOOP: (
        "Nice loop",
        "A chain that returns to its start: if assuming a candidate false forces it true, it is true.",
    ),
    S.SANDWICH_COMBO: ("Sandwich sums", "The clue is the sum of the digits between the 1 and the 9 of that line."),
    S.XSUM_COMBO: ("X-sums", "The first digit in from the clue says how many cells to add up."),
    S.SKYLINE_COMBO: ("Skyscrapers", "Digits are building heights; the clue counts the buildings you can see."),
    S.LOL_COMBO: (
        "Law of leftovers / set equivalence",
        "Take whole rows (or columns) and as many boxes covering "
        "most of them: the cells left over on each side contain "
        "exactly the same digits.",
    ),
    S.IMPLIED: ("Implied houses", "Some cell sets must hold every digit once even though they are not drawn."),
    S.UNIQUE_RECT: (
        "Unique rectangle",
        "Four cells in two rows, two columns and two boxes can't all be the same "
        "pair -- that would allow two solutions -- so avoid the deadly pattern.",
    ),
    S.BUG_PLUS1: (
        "BUG+1",
        "If every unsolved cell has two candidates except one, that cell takes the digit that "
        "would otherwise appear three times in a house.",
    ),
    S.ALS_XZ: (
        "ALS-XZ",
        "Two almost-locked sets joined by a shared digit X that can't be in both: the other "
        "shared digit Z must be in one of them, so cells seeing every Z lose it.",
    ),
    S.ALS_XYWING: ("ALS-XY-Wing", "Three almost-locked sets chained like an XY-Wing."),
    S.DEATH_BLOSSOM: (
        "Death blossom",
        "A stem cell whose every candidate locks a different almost-locked set; a "
        "digit common to all petals is forced into one of them.",
    ),
    S.ALS_AIC: ("ALS chain", "An alternating chain that uses almost-locked sets as links."),
    S.CANONICAL: ("Canonical enumeration", "Internal tie-breaking."),
    S.COUNT_COMBO: ("Counting rules", "Count how many times each digit must appear and where it still fits."),
    S.LINE_D: (
        "Line logic without notes",
        "Read thermo / whisper / dot logic straight off the grid: the line "
        "restricts a cell before you ever write a note.",
    ),
    S.LINE_RANGE: (
        "Line ranges",
        "Work out the range each cell of a line can take from its length, its neighbours and the digits already on it.",
    ),
    S.MENTAL_D: (
        "Pairs and triples in your head",
        "Spot pairs and triples in your head -- cells that can only be the same two "
        "or three digits -- and use them to unlock a single.",
    ),
    S.SHORT_TRIAL: (
        "Short contradiction",
        "Try one of a cell's two candidates; if a few forced steps break a rule, the other candidate is right.",
    ),
}

# techniques newer than metrics.FAMILIES (used only while FAMILIES doesn't list them)
EXTRA_FAMILY = {S.MENTAL_CHAIN: "chains", S.EITHER_WAY: "trial", S.LINE_CLASS: "intersections+combos"}

FAMILY_DISPLAY = {
    "singles": "Singles",
    "intersections+combos": "Intersections and combinations",
    "subsets": "Subsets",
    "fish+wings": "Fish and wings",
    "chains": "Chains",
    "ALS": "Almost locked sets",
    "trial": "Trial / contradiction",
}

LINE_NAMES = {
    "thermo": "thermometer",
    "slow_thermo": "slow thermometer",
    "whisper": "German whisper",
    "dutch_whisper": "Dutch whisper",
    "renban": "renban line",
    "palindrome": "palindrome line",
    "entropic": "entropic line",
    "kropki_chain": "chain of kropki dots",
    "region_sum": "region-sum line",
    "parity": "parity line",
    "between": "between line",
    "modular": "modular line",
    "zipper": "zipper line",
}


def _pick(options, *key):
    """Deterministic variation: the same move always gets the same phrasing."""
    return options[zlib.crc32(repr(key).encode()) % len(options)]


def _join(items, conj="and"):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return str(items[0])
    return ", ".join(str(x) for x in items[:-1]) + f" {conj} " + str(items[-1])


def _an(word):
    """Article for a technique name ('An Empty Rectangle', 'A Swordfish')."""
    return "An" if word[:1].lower() in "aeiou" else "A"


def _cap(s):
    if not s or re.match(r"r\d+c\d+", s):  # never 'R4c7'
        return s
    return s[:1].upper() + s[1:]


def _subj(nm, cs):
    """Sentence-initial cell list: 'Cell r1c1' / 'Cells r1c1 and r2c2'."""
    cs = list(cs)
    return ("Cell " if len(cs) == 1 else "Cells ") + nm.cells(cs)


# -------------------------------------------------------------------- naming --
class Namer:
    def __init__(self, p):
        self.p = p
        self.box_no, self.reg_no = {}, {}
        nb = nr = 0
        for gi, g in enumerate(p.groups):
            if g.kind == "box":
                nb += 1
                self.box_no[gi] = nb
            elif g.kind == "region":
                nr += 1
                self.reg_no[gi] = nr
        self.gidx = {g.name: gi for gi, g in enumerate(p.groups)}

    def cell(self, c):
        r, cc = self.p.coords[c]
        return f"r{r + 1}c{cc + 1}"

    def sort(self, cs):
        return sorted(set(cs), key=lambda c: self.p.coords[c])

    def cells(self, cs, conj="and"):
        return _join([self.cell(c) for c in self.sort(cs)], conj)

    def span(self, cs):
        """Ordered line cells: 'r1c1-r1c4' (first to last)."""
        cs = list(cs)
        return f"{self.cell(cs[0])}-{self.cell(cs[-1])}" if len(cs) > 1 else self.cell(cs[0])

    @staticmethod
    def digits(ds, conj="or"):
        return _join(sorted(set(ds)), conj)

    @staticmethod
    def cset(mask):
        return "{" + ",".join(str(d) for d in digits_of(mask)) + "}"

    def unit(self, gi, the=False):
        p = self.p
        if gi is None or gi < 0 or gi >= len(p.groups):
            return "an implied house"
        g = p.groups[gi]
        r0, c0 = p.coords[g.cells[0]]
        if g.kind == "row":
            return f"row {r0 + 1}"
        if g.kind == "col":
            return f"column {c0 + 1}"
        if g.kind == "box":
            return f"box {self.box_no[gi]}"
        if g.kind == "region":
            return f"region {self.reg_no[gi]}"
        if g.kind == "diag":
            return "the main diagonal" if g.name.endswith("d1") else "the anti-diagonal"
        if g.kind == "window":
            return f"the window at {self.cell(min(g.cells, key=lambda c: p.coords[c]))}"
        if g.kind == "cage":
            return self.cage(gi)
        if g.kind == "implied":
            lines, removed = getattr(g, "src", ((), ()))
            src = ""
            if lines:
                src = (
                    f" ({_union_name(self, lines)} minus "
                    f"{_join([self.unit(self.gidx[r]) if isinstance(r, str) else self.unit(r) for r in removed])})"
                )
            return f"the implied house{src}"
        if g.kind == "extra":
            return f"the extra region at {self.cell(min(g.cells, key=lambda c: p.coords[c]))}"
        return f"group {g.name}"

    def cage(self, gi, cells=True):
        g = self.p.groups[gi]
        head = f"the {g.total} cage" if g.total is not None else "the cage"
        if cells:
            return f"{head} ({self.cells(g.cells)})"
        return head


def _unit_tag(nm, gi):
    """Short unit tag for the visual list."""
    return (
        {"group": gi, "name": nm.unit(gi), "cells": list(nm.p.groups[gi].cells)}
        if 0 <= gi < len(nm.p.groups)
        else {"group": gi, "name": "implied house", "cells": []}
    )


# ------------------------------------------------------------- relations ----
def _rel_tables(p):
    if getattr(p, "_xrel", None) is not None:
        return p._xrel
    kinds = defaultdict(int)
    for rel in p.relations:
        kinds[rel[0]] += 1
    pair = defaultdict(list)
    for rel in p.relations:
        a, b = rel[1], rel[2]
        pair[(a, b)].append((rel[0], tuple(rel[3:]), True))
        pair[(b, a)].append((rel[0], tuple(rel[3:]), False))
    lines = {}
    linecons = []
    for i, con in enumerate(getattr(p, "constraints", ())):
        if con.get("type") == "line":
            linecons.append((i, con["kind"], list(con["cells"])))
    try:
        from .cbackend import detect_lines

        nc = len(p.constraints)
        for j, d in enumerate(detect_lines(p)):
            linecons.append((nc + j, d["kind"], list(d["cells"])))
    except Exception:  # pragma: no cover - C++ module missing
        pass
    for idx, kind, cells in linecons:
        for a, b in zip(cells, cells[1:]):
            lines.setdefault(frozenset((a, b)), (idx, kind, cells))
    p._xrel = (pair, dict(kinds), lines, linecons)
    return p._xrel


def rel_label(p, a, b):
    """Human name of the rule(s) linking cells a and b ('' if none)."""
    pair, kinds, lines, _ = _rel_tables(p)
    ln = lines.get(frozenset((a, b)))
    if ln:
        return LINE_NAMES.get(ln[1], ln[1] + " line")
    out = []
    for kind, args, fwd in pair.get((a, b), ()):
        out.append(_rel_kind_name(p, kind, args, a, b, kinds))
    if b in p.neq[a] and not out:
        out.append(_neq_name(p, a, b))
    return " / ".join(dict.fromkeys(x for x in out if x))


def _neq_name(p, a, b):
    (r1, c1), (r2, c2) = p.coords[a], p.coords[b]
    dr, dc = abs(r1 - r2), abs(c1 - c2)
    if {dr, dc} == {1, 2}:
        return "anti-knight"
    if dr == 1 and dc == 1:
        return "anti-king"
    return "must-differ rule"


def _rel_kind_name(p, kind, args, a, b, kinds):
    if kind == "neq":
        return _neq_name(p, a, b)
    if kind == "nonconsec":
        return "non-consecutive"
    if kind in ("lt", "le"):
        return "thermometer" if kind == "lt" else "slow thermometer"
    if kind == "diffge":
        k = args[0] if args else 5
        return "German whisper" if k == 5 else "Dutch whisper" if k == 4 else f"whisper (differ by {k}+)"
    if kind == "diff":
        return "white kropki dot" if args == (1,) else f"difference-{args[0]} dot"
    if kind == "ratio":
        return "black kropki dot" if args == (2,) else f"ratio-{args[0]} dot"
    if kind in ("notdiff", "notratio"):
        return "negative kropki rule (no dot: neither consecutive nor double)"
    if kind == "sum":
        s = args[0]
        return {5: "V (sum 5)", 10: "X (sum 10)"}.get(s, f"sum-{s} marker")
    if kind == "notsum":
        return "negative XV rule"
    if kind == "eq":
        return "palindrome"
    if kind in ("samegroup3", "diffgroup3"):
        return "entropic line"
    if kind == "parity":
        return "parity line"
    if kind in ("diffmod3", "samemod3"):
        return "modular line"
    if kind == "notpair":
        return "top-bottom path rule"
    if kind == "neqval":
        return "must-differ rule"
    return kind


def _rel_ex(p, a, b, v):
    """Digits excluded at b when a == v (pair relations + neq)."""
    m = p.rel_ex[a][b][v] if b in p.rel_ex[a] else 0
    if b in p.neq[a]:
        m |= bit(v)
    return m


# ---------------------------------------------------------- implied houses --
def implied_houses(p):
    """Derived houses exactly as the engine builds them (csolver model.cpp build_implied): unions of
    k = 2..4 parallel lines minus k-1 disjoint complete houses inside them that leave D cells.
    -> list of (cells, lines, removed group indices or 'implied#')."""
    if getattr(p, "_ximplied", None) is not None:
        return p._ximplied
    known = {frozenset(p.groups[gi].cells) for gi in p.houses}
    newh = []
    for orient in ("row", "col"):
        lines = [gi for gi in p.houses if p.groups[gi].kind == orient and len(p.groups[gi].cells) == p.D]
        if len(lines) > 30:
            continue
        for _ in range(2):
            rem = [(frozenset(p.groups[gi].cells), gi) for gi in p.houses if p.groups[gi].kind != orient]
            rem += [(h, f"implied{j + 1}") for j, (h, _, _) in enumerate(newh)]
            for k in range(2, min(4, len(lines)) + 1):
                for idx in combinations(lines, k):
                    U = frozenset().union(*(p.groups[g].cells for g in idx))
                    inside = [r for r in rem if r[0] <= U]
                    if len(inside) < k - 1:
                        continue

                    def sel(s0, d2, S, used):
                        if d2 == k - 1:
                            if len(S) == p.D and S not in known:
                                known.add(S)
                                newh.append((S, idx, tuple(used)))
                            return
                        for j in range(s0, len(inside)):
                            h, name = inside[j]
                            if h <= S:
                                sel(j + 1, d2 + 1, S - h, used + [name])

                    sel(0, 0, U, [])
    p._ximplied = newh
    return newh


def derived(p):
    """The puzzle the engine actually solves: p plus its implied houses (same group indices, the
    implied ones appended as 'implied1', 'implied2', ...)."""
    if getattr(p, "_xderived", None) is not None:
        return p._xderived
    if not hasattr(p, "groups_of"):
        p.finalize()
    imp = implied_houses(p)
    if not imp:
        p._xderived = p
        return p
    import copy

    from .model import Group

    q = copy.copy(p)
    q.groups = list(p.groups)
    for k, (cells, lines, removed) in enumerate(imp):
        g = Group(f"implied{k + 1}", tuple(sorted(cells)), "implied", True)
        g.src = (lines, removed)
        q.groups.append(g)
    q._xderived = q
    for attr in ("_xrel", "_xrules", "_xunions", "_xinnie4", "_xinnie9", "_xlol", "_xrects"):
        if hasattr(q, attr):
            delattr(q, attr) if attr in q.__dict__ else None
    q.finalize()
    q._xbase = p
    p._xderived = q
    return q


# ------------------------------------------------------------------- state --
class State:
    """Grid before a step: placed digits, candidates (the engine's own maintenance: peers + pair
    relations on every placement, eliminations applied), solving mode, and which step last
    removed each candidate (for 'it lost its last alternative to ...' remarks)."""

    def __init__(self, p, vals=None, cand=None, mode="direct"):
        self.p = p
        self.vals = list(vals) if vals is not None else [0] * p.N
        self.cand = list(cand) if cand is not None else list(p.domains)
        self.mode = mode
        self.idx = 0
        self.lost = {}  # (cell, digit) -> (step idx, technique code)

    @classmethod
    def initial(cls, p):
        st = cls(p)
        for c, v in p.givens.items():
            st.place(c, v)
        st.givens = set(p.givens)
        return st

    def copy(self):
        s = State(self.p, self.vals, self.cand, self.mode)
        s.idx, s.lost = self.idx, dict(self.lost)
        s.givens = getattr(self, "givens", set())
        return s

    def placed_g(self, gi):
        m = 0
        for c in self.p.groups[gi].cells:
            if self.vals[c]:
                m |= bit(self.vals[c])
        return m

    def place(self, c, v, tag=None):
        p = self.p
        self.vals[c] = v
        self.cand[c] = 0
        b = bit(v)
        for q in p.peer_list[c]:
            if self.cand[q] & b:
                self.cand[q] &= ~b
                if tag is not None:
                    self.lost[(q, v)] = tag
        for q in p.nonconsec_list[c]:
            nb = p.rel_ex[c][q][v]
            if self.cand[q] & nb:
                if tag is not None:
                    for d in digits_of(self.cand[q] & nb):
                        self.lost[(q, d)] = tag
                self.cand[q] &= ~nb

    def apply(self, step):
        m = step.move
        tag = (self.idx, m.feat[0])
        if m.feat[0] == S.TAKE_NOTES:
            self.mode = "notes"
        if m.place:
            self.place(*m.place, tag=tag)
        for c, v in m.elim:
            if self.cand[c] & bit(v):
                self.lost[(c, v)] = tag
            self.cand[c] &= ~bit(v)
        if step.mode == "notes":
            self.mode = "notes"
        self.idx += 1


def replay(p, steps, state=None):
    """Yield (index, step, state BEFORE the step); the state object is copied per step."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    p = derived(p)
    st = state.copy() if state is not None else State.initial(p)
    for i, step in enumerate(steps):
        st.idx = i
        yield i, step, st.copy()
        st.apply(step)


def _as_state(p, state):
    if isinstance(state, State):
        return state
    if isinstance(state, dict):
        return State(p, state.get("vals"), state.get("cand"), state.get("mode", "direct"))
    if isinstance(state, (tuple, list)) and len(state) == 2:
        return State(p, state[0], state[1])
    raise TypeError("state must be explain.State, {'vals','cand'} or (vals, cand)")


# ------------------------------------------------------------ n-ary rules ----
class Rule:
    """One multi-cell rule (cage, line, arrow, sum clue ...) as a checkable predicate."""

    def __init__(
        self,
        kind,
        cells,
        label,
        index=None,
        group=None,
        con=None,
        total=None,
        segs=None,
        line_kind=None,
        distinct=False,
    ):
        self.kind, self.cells, self.label, self.index, self.group = kind, list(cells), label, index, group
        self.con, self.total, self.segs, self.line_kind, self.distinct = con or {}, total, segs, line_kind, distinct

    def check(self, a):
        k, con = self.kind, self.con
        if k in ("sum", "cage", "little_killer", "innie"):
            return sum(a) == self.total
        if k == "arrow":
            nc = len(con["circle"])
            num = int("".join(str(x) for x in a[:nc])) if nc > 1 else a[0]
            return num == sum(a[nc:])
        if k == "equal_sum":
            s, pos = None, 0
            for seg in self.segs:
                t = sum(a[pos : pos + len(seg)])
                pos += len(seg)
                if s is None:
                    s = t
                elif t != s:
                    return False
            return True
        if k == "set":
            return len(set(a)) == len(a) and max(a) - min(a) == len(a) - 1
        if k == "between":
            lo, hi = sorted((a[0], a[-1]))
            return all(lo < x < hi for x in a[1:-1])
        if k == "table":
            return tuple(a) in {tuple(t) for t in con["allowed"]}
        if k == "sandwich":
            D = max(a)
            try:
                i, j = sorted((a.index(1), a.index(D)))
            except ValueError:
                return False
            return sum(a[i + 1 : j]) == self.total
        if k == "xsum":
            return a[0] <= len(a) and sum(a[: a[0]]) == self.total
        if k == "skyscraper":
            seen, top = 0, 0
            for x in a:
                if x > top:
                    seen, top = seen + 1, x
            return seen == con["count"]
        if k == "distinct_count":
            return len(set(a)) == con["count"]
        if k == "contains":
            return a[0] in a[1:]
        if k == "count":
            from collections import Counter

            cnt = Counter(a)
            if "each" in con:
                return all(v == con["each"] for v in cnt.values())
            return all(cnt.get(int(v), 0) == n for v, n in con["digits"].items())
        return True  # pairwise lines: the pair relations do the work

    def partial(self, a, i, dom):
        """Prune a prefix a[0..i]."""
        k = self.kind
        if k in ("sum", "cage", "little_killer", "innie"):
            s = sum(a[: i + 1])
            rest = dom[i + 1 :]
            lo = sum(min(digits_of(m)) for m in rest) if rest else 0
            hi = sum(max(digits_of(m)) for m in rest) if rest else 0
            return s + lo <= self.total <= s + hi
        if k == "set":
            pre = a[: i + 1]
            return len(set(pre)) == len(pre) and max(pre) - min(pre) <= len(self.cells) - 1
        return True


def _con_label(nm, con, idx):
    t = con.get("type")
    lk = con.get("line_kind") or (con.get("kind") if t == "line" else None)
    if lk:
        cells = con.get("cells") or [c for s in con.get("segments", []) for c in s]
        name = LINE_NAMES.get(lk, lk + " line")
        if lk == "thermo" or lk == "slow_thermo":
            return f"the {name} with its bulb at {nm.cell(cells[0])} (running {nm.span(cells)})"
        if lk == "between":
            return f"the between line from {nm.cell(cells[0])} to {nm.cell(cells[-1])}"
        if lk == "zipper":
            segs = con.get("segments")
            mid = segs[-1][0] if segs and len(segs[-1]) == 1 else None
            return f"the zipper line through {nm.cells(cells)}" + (
                f" (centre {nm.cell(mid)})" if mid is not None else ""
            )
        if lk == "region_sum":
            return f"the region-sum line through {nm.cells(cells)}"
        return f"the {name} {nm.span(cells)}"
    if t == "arrow":
        circ = con["circle"]
        cl = nm.cell(circ[0]) if len(circ) == 1 else "the pill " + nm.cells(circ)
        return f"the arrow from {cl} along {nm.cells(con['line'])}"
    if t == "sum":
        return f"the sum clue {con['total']} over {nm.cells(con['cells'])}"
    if t == "little_killer":
        return f"the little-killer clue {con['total']} along {nm.span(con['cells'])}"
    if t == "sandwich":
        return f"the sandwich clue {con['total']} (on {nm.span(con['cells'])})"
    if t == "xsum":
        return f"the X-sum clue {con['total']} (reading {nm.span(con['cells'])})"
    if t == "skyscraper":
        return f"the skyscraper clue {con['count']} (looking along {nm.span(con['cells'])})"
    if t == "equal_sum":
        return "the equal-sum rule over " + "; ".join(nm.cells(s) for s in con["segments"])
    if t == "count":
        return f"the counting rule over {nm.span(con['cells'])}"
    if t == "distinct_count":
        return f"the distinct-count clue {con['count']} (along {nm.span(con['cells'])})"
    if t == "contains":
        return f"the arrow in {nm.cell(con['cells'][0])} (its digit appears along {nm.span(con['cells'][1:])})"
    if t == "between":
        return f"the between line from {nm.cell(con['cells'][0])} to {nm.cell(con['cells'][-1])}"
    if t == "table":
        return f"the combination rule on {nm.cells(con['cells'])}"
    if t == "set":
        return f"the consecutive-set rule on {nm.cells(con['cells'])}"
    return f"rule {idx}"


def rules(p):
    """Every multi-cell rule of the puzzle, keyed like the engine: ('con', index into p.constraints
    then detected lines), ('cage', group index)."""
    if getattr(p, "_xrules", None) is not None:
        return p._xrules
    nm = Namer(p)
    out = {}
    nc = len(p.constraints)
    for i, con in enumerate(p.constraints):
        t = con.get("type")
        if t == "line":
            if con.get("kind") in ("renban", "between", "zipper", "region_sum"):
                continue  # carried by the compiled n-ary entry
            out[("con", i)] = Rule(
                "line", con["cells"], _con_label(nm, con, i), index=i, con=con, line_kind=con["kind"]
            )
            continue
        lk = con.get("line_kind")
        if t == "arrow":
            r = Rule("arrow", list(con["circle"]) + list(con["line"]), _con_label(nm, con, i), index=i, con=con)
        elif t in ("sum", "little_killer"):
            r = Rule(
                t,
                con["cells"],
                _con_label(nm, con, i),
                index=i,
                con=con,
                total=con["total"],
                distinct=bool(con.get("distinct")) and t == "sum",
            )
        elif t == "equal_sum":
            r = Rule(
                "equal_sum",
                [c for s in con["segments"] for c in s],
                _con_label(nm, con, i),
                index=i,
                con=con,
                segs=con["segments"],
                line_kind=lk,
            )
        elif t == "set":
            r = Rule("set", con["cells"], _con_label(nm, con, i), index=i, con=con, line_kind=lk, distinct=True)
        elif t in ("between", "table", "sandwich", "xsum", "skyscraper", "count", "distinct_count", "contains"):
            r = Rule(t, con["cells"], _con_label(nm, con, i), index=i, con=con, total=con.get("total"), line_kind=lk)
        else:
            continue
        out[("con", i)] = r
    _, _, _, linecons = _rel_tables(p)
    for idx, kind, cells in linecons:
        if idx >= nc:
            con = {"type": "line", "kind": kind, "cells": cells}
            out[("con", idx)] = Rule("line", cells, _con_label(nm, con, idx), index=idx, con=con, line_kind=kind)
    for gi, g in enumerate(p.groups):
        if g.total is not None:
            out[("cage", gi)] = Rule("cage", g.cells, nm.cage(gi), group=gi, total=g.total, distinct=True)
    p._xrules = out
    return out


_MENTAL_LINE_MAX = int(__import__("os").environ.get("CSOLVER_MENTAL_LINE_MAX", "50"))


def enum_rule(p, rule, dom, node_limit=150000, keep=400, max_count=None, support=True):
    """All assignments of rule.cells within masks `dom` that satisfy the rule, the pair relations
    and distinctness inside the scope. -> dict(sup, count, sols, complete).
    max_count: stop as soon as more fillings exist (-> complete False, count None); support=False: no witness search
    when the enumeration is incomplete (the direct-mode reading mirrors the engine's cap and skips such rules)."""
    cells = rule.cells
    n = len(cells)
    distinct_all = rule.distinct
    conflicts = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i):
            a, b = cells[j], cells[i]
            same = distinct_all or b in p.peers[a]
            tab = p.rel_ex[a].get(b) if b in p.rel_ex[a] else None
            if same or tab:
                conflicts[i].append((j, same, tab))
    sup = [0] * n
    sols = []
    asg = [0] * n
    st = {"count": 0, "nodes": 0, "complete": True}

    def rec(i):
        if st["nodes"] > node_limit:
            st["complete"] = False
            return
        if i == n:
            if rule.check(asg):
                st["count"] += 1
                if max_count is not None and st["count"] > max_count:
                    st["complete"] = False
                    st["nodes"] = node_limit + 1  # unwinds the recursion at the next node
                    return
                for k in range(n):
                    sup[k] |= bit(asg[k])
                if len(sols) < keep:
                    sols.append(tuple(asg))
            return
        for v in digits_of(dom[i]):
            st["nodes"] += 1
            ok = True
            for j, same, tab in conflicts[i]:
                if (same and asg[j] == v) or (tab and tab[asg[j]] & bit(v)):
                    ok = False
                    break
            if not ok:
                continue
            asg[i] = v
            if rule.partial(asg, i, dom):
                rec(i + 1)
        asg[i] = 0

    rec(0)
    if not st["complete"] and not support:
        return {"sup": sup, "count": None, "sols": sols, "complete": False}
    if not st["complete"]:
        sup2, exact = _support_search(p, rule, dom, conflicts)
        if not exact and n <= 9:
            sup2, exact = _support_search(p, rule, dom, conflicts, node_limit=80000)
        return {"sup": sup2, "count": None, "sols": sols, "complete": exact}
    return {"sup": sup, "count": st["count"], "sols": sols, "complete": st["complete"]}


def _feasible(rule, asg, dom):
    """Bounds check on a partial assignment (dict index -> value) for sum-like rules."""
    k = rule.kind
    if k in ("sum", "cage", "little_killer", "innie"):
        s = sum(asg.values())
        lo = hi = 0
        for i, m in enumerate(dom):
            if i not in asg:
                ds = list(digits_of(m))
                if not ds:
                    return False
                lo += ds[0]
                hi += ds[-1]
        return s + lo <= rule.total <= s + hi
    if k == "set":
        vs = list(asg.values())
        return len(set(vs)) == len(vs) and (not vs or max(vs) - min(vs) <= len(rule.cells) - 1)
    return True


def _support_search(p, rule, dom, conflicts, node_limit=8000):
    """GAC by one witness search per (cell, value): DFS with forward checking and smallest-domain
    ordering. Values whose search runs out of budget are kept (sound). -> (sup, exact)."""
    n = len(rule.cells)
    nbr = [[] for _ in range(n)]  # i -> [(j, same, tab_i_to_j)] both directions
    for i in range(n):
        for j, same, tab in conflicts[i]:
            a, b = rule.cells[j], rule.cells[i]
            nbr[i].append((j, same, p.rel_ex[b].get(a) if a in p.rel_ex[b] else None))
            nbr[j].append((i, same, tab))
    budget = {"n": 0, "hit": False}

    def dfs(d, asg):
        if budget["n"] > node_limit:
            budget["hit"] = True
            return None
        if len(asg) == n:
            return dict(asg) if rule.check([asg[i] for i in range(n)]) else None
        i = min((k for k in range(n) if k not in asg), key=lambda k: popcount(d[k]))
        for v in digits_of(d[i]):
            budget["n"] += 1
            nd = list(d)
            nd[i] = bit(v)
            ok = True
            for j, same, tab in nbr[i]:
                if j in asg:
                    continue
                m = nd[j]
                if same:
                    m &= ~bit(v)
                if tab:
                    m &= ~tab[v]
                if not m:
                    ok = False
                    break
                nd[j] = m
            if not ok:
                continue
            asg[i] = v
            if _feasible(rule, asg, nd):
                r = dfs(nd, asg)
                if r is not None:
                    del asg[i]
                    return r
            del asg[i]
        return None

    sup = [0] * n
    exact = True
    for i in range(n):
        for v in digits_of(dom[i]):
            if sup[i] & bit(v):
                continue
            budget["n"], budget["hit"] = 0, False
            d0 = list(dom)
            d0[i] = bit(v)
            ok = True
            for j, same, tab in nbr[i]:
                m = d0[j]
                if same:
                    m &= ~bit(v)
                if tab:
                    m &= ~tab[v]
                if not m:
                    ok = False
                d0[j] = m
            w = dfs(d0, {}) if ok else None
            if w is not None:
                for k, x in w.items():
                    sup[k] |= bit(x)
            elif budget["hit"]:
                sup[i] |= bit(v)
                exact = False
    return sup, exact


def _rule_dom(st, rule, mental=None):
    out = []
    for c in rule.cells:
        if st.vals[c]:
            out.append(bit(st.vals[c]))
        else:
            out.append(mental[c] if mental is not None else st.cand[c])
    return out


# ------------------------------------------------------- direct exclusions --
def direct_sources(p, st, c, digit=None):
    """Why each digit is excluded at empty cell c from placed digits alone.
    -> list of (kind, mask, info). kinds: 'house' (gi, {digit: cell}), 'neq' (cell, digit),
    'rel' (cell, digit), 'domain', 'cagesum' (gi)."""
    out = []
    for gi in p.groups_of[c]:
        g = p.groups[gi]
        where = {}
        for q in g.cells:
            if st.vals[q] and q != c:
                where[st.vals[q]] = q
        if where:
            m = 0
            for d in where:
                m |= bit(d)
            out.append(("house", m, (gi, where)))
    for q in p.neq[c]:
        if st.vals[q]:
            out.append(("neq", bit(st.vals[q]), (q, st.vals[q])))
    for q in p.nonconsec[c]:
        v = st.vals[q]
        if v:
            m = p.rel_ex[q][c][v]
            if m:
                out.append(("rel", m, (q, v)))
    dom_ex = p.full & ~p.domains[c]
    if dom_ex:
        out.append(("domain", dom_ex, None))
    for gi in p.groups_of[c]:
        g = p.groups[gi]
        if g.total is not None:
            allowed = _cage_direct(p, st, gi)
            m = p.full & ~allowed & ~st.placed_g(gi)
            if m:
                out.append(("cagesum", m, gi))
    return out


def _cage_direct(p, st, gi):
    g = p.groups[gi]
    emp = [c for c in g.cells if not st.vals[c]]
    rem = g.total - sum(st.vals[c] for c in g.cells)
    used = st.placed_g(gi)
    allowed = 0
    pool = [d for d in range(1, p.D + 1) if not used & bit(d)]
    for combo in combinations(pool, len(emp)):
        if sum(combo) == rem:
            for d in combo:
                allowed |= bit(d)
    return allowed


def direct_excl(p, st, c):
    m = 0
    for _, mm, _ in direct_sources(p, st, c):
        m |= mm
    return m


def _source_text(nm, kind, info, digits, c=None):
    """One exclusion source as a phrase."""
    p = nm.p
    ds = sorted(digits)
    if kind == "house":
        gi, where = info
        ds = [d for d in ds if d in where]
        return f"{nm.unit(gi)} already has {nm.digits(ds, 'and')}"
    if kind == "neq":
        q, v = info
        return f"it is a {rel_label(p, q, c) or 'linked'} step from the {v} in {nm.cell(q)}"
    if kind == "rel":
        q, v = info
        lab = rel_label(p, q, c)
        return f"the {v} in {nm.cell(q)} rules out {nm.digits(ds)} via the {lab}"
    if kind == "domain":
        odd = all(d % 2 == 0 for d in ds)
        even = all(d % 2 == 1 for d in ds)
        return (
            "it is an odd (shaded) cell"
            if odd
            else "it is an even (shaded) cell"
            if even
            else f"its cell rule forbids {nm.digits(ds)}"
        )
    if kind == "cagesum":
        gi = info
        return f"{nm.cage(gi, cells=False)} can't use {nm.digits(ds)} with what's left of its total"
    if kind == "lock":
        return info["text"]
    return ""


# -------------------------------------------------------- direct pointing ----
def direct_locks(p, st):
    """Pointing / claiming done in the head (no notes): digit v's directly-possible cells in house
    B all lie in group A -> v excluded from A minus B. -> list of dicts."""
    empties = [c for c in range(p.N) if not st.vals[c]]
    ex = {c: direct_excl(p, st, c) for c in empties}
    out = []
    for bi in p.houses:
        B = p.groups[bi]
        emp = [c for c in B.cells if not st.vals[c]]
        if len(emp) < 3:
            continue
        for v in digits_of(p.full & ~st.placed_g(bi)):
            b = bit(v)
            poss = [c for c in emp if not ex[c] & b]
            if len(poss) < 2:
                continue
            common = set(p.groups_of[poss[0]])
            for c in poss[1:]:
                common &= set(p.groups_of[c])
            common.discard(bi)
            for ai in common:
                tg = [c for c in p.groups[ai].cells if not st.vals[c] and c not in B.cells and not ex[c] & b]
                if tg:
                    out.append({"B": bi, "A": ai, "v": v, "poss": poss, "targets": tg, "rel": False})
            for rel, generic in ((p.nonconsec, True), (p.neq, False)):
                if not rel[poss[0]]:
                    continue
                cr = set(rel[poss[0]])
                for c in poss[1:]:
                    cr &= set(rel[c])
                for x in cr:
                    if st.vals[x] or x in poss:
                        continue
                    rm = p.full
                    if generic:
                        for c in poss:
                            rm &= p.rel_ex[c][x][v]
                    else:
                        rm = b
                    if rm & ~ex[x]:
                        out.append({"B": bi, "A": None, "v": v, "poss": poss, "targets": [x], "rel": True, "mask": rm})
    return out, ex


def _lock_text(nm, lk):
    p = nm.p
    if lk["rel"]:
        x = lk["targets"][0]
        return (
            f"the {lk['v']} of {nm.unit(lk['B'])} must be in {nm.cells(lk['poss'], 'or')}, all of which are "
            f"{rel_label(p, lk['poss'][0], x)}-linked to {nm.cell(x)}"
        )
    return (
        f"the {lk['v']} of {nm.unit(lk['B'])} isn't placed yet but can only go in {nm.cells(lk['poss'], 'or')}, "
        f"so it already occupies {nm.unit(lk['A'])} there"
    )


# ----------------------------------------------------------- mental view -----
def mental_view(p, st, level=3):
    """Direct-mode reasoning without notes: placed-digit exclusions, then relation arcs and
    whole-rule consistency (two rounds), mental pairs/triples and pointing, one more round.
    -> (md masks, reasons {(cell, digit): reason})."""
    N = p.N
    R = rules(p)
    md = [0] * N
    reasons = {}
    empties = [c for c in range(N) if not st.vals[c]]
    for c in range(N):
        md[c] = bit(st.vals[c]) if st.vals[c] else p.full & ~direct_excl(p, st, c)

    def drop(c, keep, why):
        lost = md[c] & ~keep
        if not lost or not md[c] & keep:
            return False
        for d in digits_of(lost):
            reasons.setdefault((c, d), why(d))
        md[c] &= keep
        return True

    def relation_round(depth):
        md0 = list(md)
        changed = False
        for key, rule in R.items():
            if not any(not st.vals[c] for c in rule.cells):
                continue
            dom = [md0[c] for c in rule.cells]
            if any(d == 0 for d in dom):
                continue
            # mirror the engine's direct-mode cap (csolver mental.cpp, CSOLVER_MENTAL_LINE_MAX, default 50): a rule with more
            # consistent fillings (or an unknown number) is not read without notes
            res = enum_rule(p, rule, dom, node_limit=40000, max_count=_MENTAL_LINE_MAX or None, support=False)
            if not res["complete"] or res["count"] == 0:
                continue
            for k, c in enumerate(rule.cells):
                if not st.vals[c]:
                    snap = {q: md0[q] for q in rule.cells if not st.vals[q] and q != c}
                    changed |= drop(
                        c,
                        res["sup"][k],
                        lambda d, rule=rule, snap=snap, res=res: (
                            "rule",
                            key,
                            snap,
                            res["count"],
                            res["sols"][:8],
                            depth,
                        ),
                    )
        for c in empties:
            for q in set(p.nonconsec[c]) | set(p.neq[c]):
                if q == c:
                    continue
                dq = md0[q]
                allowed = 0
                for w in digits_of(dq):
                    allowed |= p.full & ~_rel_ex(p, q, c, w)
                changed |= drop(c, allowed, lambda d, q=q, dq=dq: ("arc", q, dq, depth))
        return changed

    for rnd in range(1, 7):  # the engine does two rounds plus inequality fixpoints; iterate to be safe
        if not relation_round(rnd):
            break
    if level >= 3:
        snap = list(md)
        for hi in p.houses:
            emp = [c for c in p.groups[hi].cells if not st.vals[c] and popcount(snap[c]) <= 3]
            for k in (2, 3):
                for combo in combinations(emp, k):
                    u = 0
                    for c in combo:
                        u |= snap[c]
                    if popcount(u) != k:
                        continue
                    for q in p.groups[hi].cells:
                        if not st.vals[q] and q not in combo:
                            drop(q, p.full & ~u, lambda d, hi=hi, combo=combo, u=u: ("subset", hi, combo, u))
        for bi in p.houses:
            for v in digits_of(p.full & ~st.placed_g(bi)):
                poss = [c for c in p.groups[bi].cells if not st.vals[c] and snap[c] & bit(v)]
                if not 2 <= len(poss) <= 3:
                    continue
                for ai in p.groups_of[poss[0]]:
                    if ai == bi or not all(c in p.groups[ai].cells for c in poss):
                        continue
                    for q in p.groups[ai].cells:
                        if not st.vals[q] and q not in p.groups[bi].cells:
                            drop(
                                q, p.full & ~bit(v), lambda d, bi=bi, ai=ai, poss=poss, v=v: ("point", bi, ai, v, poss)
                            )
        for rnd in range(7, 12):
            if not relation_round(rnd):
                break
    return md, reasons


def _mental_reason_text(nm, c, d, why, st):
    p = nm.p
    kind = why[0]
    if kind == "arc":
        _, q, dq, _ = why
        lab = rel_label(p, q, c) or "linked"
        if not st.vals[q]:
            opts = nm.digits(digits_of(dq))
            return f"its {lab} partner {nm.cell(q)} can only be {opts} at this point, and none of those allows a {d}"
        return f"the {st.vals[q]} in {nm.cell(q)} rules it out through the {lab}"
    if kind == "rule":
        _, key, snap, count, sols, _ = why
        rule = rules(p)[key]
        lk = rule.line_kind or rule.kind
        if lk in ("thermo", "slow_thermo") and c in rule.cells:
            i = rule.cells.index(c)
            strict = lk == "thermo"
            dm = lambda q: bit(st.vals[q]) if st.vals[q] else snap.get(q, p.full)
            if i > 0:
                q = rule.cells[i - 1]
                lo = min(digits_of(dm(q)))
                if d < lo + strict:
                    return (
                        f"it sits above {nm.cell(q)} on the thermometer, which is at least {lo}"
                        if not st.vals[q]
                        else f"it sits above the {st.vals[q]} in {nm.cell(q)} on the thermometer"
                    )
            if i + 1 < len(rule.cells):
                q = rule.cells[i + 1]
                hi = max(digits_of(dm(q)))
                if d > hi - strict:
                    return (
                        f"it sits below {nm.cell(q)} on the thermometer, which is at most {hi}"
                        if not st.vals[q]
                        else f"it sits below the {st.vals[q]} in {nm.cell(q)} on the thermometer"
                    )
        if lk == "cage" and len(rule.cells) == 2:
            o = rule.cells[0] if rule.cells[1] == c else rule.cells[1]
            need = rule.total - d
            return f"{rule.label} would then need {need} in {nm.cell(o)}, which isn't possible there"
        if count and sols and count <= 3 and len(rule.cells) <= 6:
            fills = "; ".join("-".join(map(str, x)) for x in sols[:3])
            return f"{rule.label} can only be filled as {fills} (in order {nm.span(rule.cells)})"
        return f"no valid way to fill {rule.label} puts a {d} there"
    if kind == "subset":
        _, hi, combo, u = why
        return (
            f"{nm.cells(combo)} can only hold {nm.digits(digits_of(u), 'and')} between them, so the "
            f"{d} of {nm.unit(hi)} is already spoken for"
        )
    if kind == "point":
        _, bi, ai, v, poss = why
        return f"the {v} of {nm.unit(bi)} is stuck in {nm.cells(poss, 'or')}, inside {nm.unit(ai)}"
    return "it is ruled out"


# -------------------------------------------------------------- context ----
def _adapt_engine(nm, raw):
    """Engine justification (cbackend.solve(..., explain=True)) -> the fields this module reads."""
    if not raw:
        return {}

    def units(side):
        return [nm.gidx[u["name"]] for u in (raw.get(side) or {}).get("units", []) if u and u.get("name") in nm.gidx]

    return {
        "base_units": units("base"),
        "cover_units": units("cover"),
        "chain": raw.get("chain") or [],
        "als": raw.get("als") or [],
        "rcc": raw.get("restricted_common") or [],
        "pattern_cells": raw.get("pattern_cells") or [],
        "constraints": raw.get("constraints") or [],
        "digits": raw.get("digits") or [],
    }


class Ctx:
    def __init__(self, step, p, st):
        self.step, self.p, self.st = step, p, st
        self.m = step.move
        self.tech = self.m.feat[0]
        self.nm = Namer(p)
        self.raw_engine = getattr(self.m, "explain", None) or {}
        self.engine = _adapt_engine(self.nm, self.raw_engine)
        self.used_engine = False
        self.xm = getattr(self.m, "xmeta", None) or {}
        self.code = getattr(self.m, "code", None)
        self.elims = sorted(set(self.m.elim))
        self.place = tuple(self.m.place) if self.m.place else None
        self.key = (self.place, tuple(self.elims), self.tech)

    def pick(self, options, salt=""):
        return _pick(options, self.key, salt)

    def gi(self, name):
        return self.nm.gidx.get(name)


def _elim_digits(ctx):
    return sorted({d for _, d in ctx.elims})


def fmt_elims(nm, elims):
    """'r4c1, r4c2 ≠ 3; r5c5 ≠ 1,2'."""
    by_cell = defaultdict(set)
    for c, d in elims:
        by_cell[c].add(d)
    by_set = defaultdict(list)
    for c, ds in by_cell.items():
        by_set[tuple(sorted(ds))].append(c)
    parts = []
    for ds, cs in sorted(by_set.items(), key=lambda kv: nm.p.coords[min(kv[1], key=lambda c: nm.p.coords[c])]):
        parts.append(f"{', '.join(nm.cell(c) for c in nm.sort(cs))} ≠ {','.join(map(str, ds))}")
    return "; ".join(parts)


def _J(ctx, **kw):
    J = {
        "technique": S.TECH_NAMES.get(ctx.tech, str(ctx.tech)),
        "digits": [],
        "placement": ctx.place,
        "eliminations": ctx.elims,
        "base_units": [],
        "cover_units": [],
        "base_cells": [],
        "cover_cells": [],
        "fins": [],
        "constraints": [],
        "links": [],
        "als": [],
        "rcc": [],
        "z": None,
        "trial": None,
    }
    J.update(kw)
    return J


def _result(ctx, J, short, teach, verified, lines=(), chain=None, extra_cells=()):
    nm = ctx.nm
    cells = (
        set(extra_cells) | set(J.get("base_cells") or ()) | set(J.get("cover_cells") or ()) | set(J.get("fins") or ())
    )
    if ctx.place:
        cells.add(ctx.place[0])
    cells |= {c for c, _ in ctx.elims}
    for lk in J.get("links") or ():
        for end in (lk["a"], lk["b"]):
            if isinstance(end[0], int):
                cells.add(end[0])
    for a in J.get("als") or ():
        cells |= set(a["cells"])
    units = [
        _unit_tag(nm, gi) for gi in dict.fromkeys(list(J.get("base_units") or []) + list(J.get("cover_units") or []))
    ]
    visual = {
        "cells": [nm.cell(c) for c in nm.sort(cells)],
        "cell_ids": nm.sort(cells),
        "units": units,
        "lines": [{"kind": k, "cells": [nm.cell(c) for c in cs], "cell_ids": list(cs)} for k, cs in lines],
        "place": [nm.cell(ctx.place[0]), ctx.place[1]] if ctx.place else None,
        "eliminations": [[nm.cell(c), d] for c, d in ctx.elims],
        "base": [nm.cell(c) for c in nm.sort(J.get("base_cells") or ())],
        "cover": [nm.cell(c) for c in nm.sort(J.get("cover_cells") or ())],
        "fins": [nm.cell(c) for c in nm.sort(J.get("fins") or ())],
        "chain": chain or [],
    }
    return {"J": J, "short": short, "teach": teach, "visual": visual, "verified": verified}


# ============================================================ singles ========
def _h_full_house(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    gi = ctx.gi(ctx.m.name)
    if gi is None:
        gi = next(
            h for h in p.houses if c in p.groups[h].cells and sum(1 for q in p.groups[h].cells if not st.vals[q]) == 1
        )
    u = nm.unit(gi)
    ok = sum(1 for q in p.groups[gi].cells if not st.vals[q]) == 1 and not st.placed_g(gi) & bit(v)
    short = f"{nm.cell(c)} = {v}: last empty cell of {u}"
    teach = ctx.pick(
        [
            f"{_cap(u)} has only one empty cell left, {nm.cell(c)}, and the only digit {u} is still missing is {v}. "
            f"Full houses are free -- after each placement, glance along its row, column and box for a house that "
            f"is one short.",
            f"Count what's missing in {u}: every digit except {v} is already there, and {nm.cell(c)} is the one gap. "
            f"Nothing else to check -- {nm.cell(c)} is {v}.",
            f"{_cap(u)} is down to a single gap at {nm.cell(c)}. The digit it lacks is {v}, so that's the answer -- "
            f"a full house is always the first thing to look for once a house fills up.",
        ]
    )
    g = p.groups[gi]
    if g.kind == "implied" and getattr(g, "src", None):
        lines, removed = g.src
        rem = [nm.gidx[r] if isinstance(r, str) else r for r in removed]
        k = len(lines)
        short = f"{nm.cell(c)} = {v}: last empty cell of an implied house"
        teach = (
            f"{_cap(_union_name(nm, lines))} together contain every digit {k} times. "
            f"{_cap(_join([nm.unit(r) for r in rem]))} lie{'s' if len(rem) == 1 else ''} entirely inside them, "
            f"so the {p.D} cells left over ({nm.cells(g.cells)}) must contain every digit exactly once -- an "
            f"invisible extra house. Only {nm.cell(c)} is empty there, and the digit missing from it is {v}. "
            f"Look for these in jigsaws and puzzles with extra regions."
        )
        J = _J(ctx, digits=[v], base_units=[gi] + list(lines) + rem, base_cells=list(g.cells))
        return _result(ctx, J, short, teach, ok)
    J = _J(ctx, digits=[v], base_units=[gi], base_cells=[q for q in p.groups[gi].cells])
    return _result(ctx, J, short, teach, ok)


def _naked_cover(p, st, c, v, srcs):
    target = p.full & ~bit(v)
    for k in range(1, len(srcs) + 1):
        for combo in combinations(srcs, k):
            m = 0
            for s in combo:
                m |= s[1]
            if m & target == target:
                return sorted(combo, key=lambda s: -popcount(s[1]))
    return None


def _cover_phrases(nm, c, chosen, v):
    """Ordered exclusion sources -> phrases that add NEW digits each time."""
    seen = 0
    phrases = []
    for i, (kind, m, info) in enumerate(chosen):
        new = m & ~seen & ~bit(v)
        if not new:
            continue
        ds = list(digits_of(new))
        if kind == "house":
            gi, where = info
            txt = f"{nm.unit(gi)} {'already has' if i == 0 else 'adds'} {nm.digits(ds, 'and')}"
        else:
            txt = _source_text(nm, kind, info, ds, c)
        phrases.append(txt)
        seen |= m
    return phrases


def _h_naked_direct(ctx, locks=None):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    srcs = direct_sources(p, st, c)
    lock_used = []
    if locks is not None:
        for lk in locks:
            if c in lk["targets"]:
                m = lk.get("mask", bit(lk["v"])) if lk["rel"] else bit(lk["v"])
                srcs.append(("lock", m, {"text": _lock_text(nm, lk), "lk": lk}))
    chosen = _naked_cover(p, st, c, v, srcs)
    ok = chosen is not None
    if not ok:
        chosen = sorted(srcs, key=lambda s: -popcount(s[1]))
    for s in chosen:
        if s[0] == "lock":
            lock_used.append(s[2]["lk"])
    phrases = _cover_phrases(nm, c, [x for x in chosen if x[0] != "lock"], v)
    excluded = 0
    for s in chosen:
        excluded |= s[1]
    n_out = popcount(excluded & ~bit(v))
    base_units = [s[2][0] for s in chosen if s[0] == "house"]
    base_cells = [q for s in chosen if s[0] == "house" for q in s[2][1].values()]
    base_cells += [s[2][0] for s in chosen if s[0] in ("neq", "rel")]
    for lk in lock_used:
        base_cells += lk["poss"]
        base_units += [lk["B"]] + ([lk["A"]] if lk["A"] is not None else [])
    seen_txt = "; ".join(phrases)
    if locks is not None and lock_used:
        lk = lock_used[0]
        short = f"{nm.cell(c)} = {v}: naked single once the pointing {lk['v']} in {nm.unit(lk['B'])} is counted"
        teach = (
            f"Collect what {nm.cell(c)} can see: {seen_txt}. The trick is the digit that isn't written yet -- "
            f"{_lock_text(nm, lk)}, which removes {lk['v']} from {nm.cell(c)} too. That leaves only {v}. "
            f"When a cell is one digit short of a single, look for a box where the missing digit is confined "
            f"to one line."
        )
    else:
        short = (
            f"{nm.cell(c)} = {v}: every other digit is already in its row, column or box"
            if all(s[0] == "house" for s in chosen)
            else f"{nm.cell(c)} = {v}: naked single, all other digits ruled out"
        )
        teach = ctx.pick(
            [
                f"Look at {nm.cell(c)} and collect what it sees: {seen_txt}. That rules out {n_out} different digits, "
                f"so {v} is the only one left. Naked singles hide in cells whose row, column and box are each fairly "
                f"full -- scan the busiest crossings.",
                f"Count the digits around {nm.cell(c)}: {seen_txt}. Between them every digit except {v} is taken, so "
                f"{nm.cell(c)} must be {v}.",
                f"{nm.cell(c)} sits where several busy houses cross: {seen_txt}. Only {v} survives -- a naked single. "
                f"Cells at the intersection of crowded houses are the best place to hunt for these.",
            ]
        )
    J = _J(ctx, digits=[v], base_units=list(dict.fromkeys(base_units)), base_cells=base_cells)
    return _result(ctx, J, short, teach, ok)


def _hidden_cover(p, st, house_gi, c, v, extra_srcs=()):
    """Cover the other empty cells of the house for digit v. -> (chosen sources, uncovered)."""
    others = [q for q in p.groups[house_gi].cells if not st.vals[q] and q != c]
    srcs = {}
    b = bit(v)
    for y in others:
        for gi in p.groups_of[y]:
            if gi == house_gi:
                continue
            for q in p.groups[gi].cells:
                if st.vals[q] == v:
                    key = ("house", gi, q)
                    srcs.setdefault(key, set()).update(x for x in others if x in p.groups[gi].cells)
        for q in p.neq[y]:
            if st.vals[q] == v:
                srcs.setdefault(("neq", q), set()).update(x for x in others if x in p.neq[q])
        for q in p.nonconsec[y]:
            if st.vals[q] and p.rel_ex[q][y][st.vals[q]] & b:
                srcs.setdefault(("rel", q), set()).update(
                    x for x in others if x in p.rel_ex[q] and p.rel_ex[q][x][st.vals[q]] & b
                )
        if not p.domains[y] & b:
            srcs.setdefault(("domain", y), set()).add(y)
        for gi in p.groups_of[y]:
            g = p.groups[gi]
            if g.total is not None and not _cage_direct(p, st, gi) & b and not st.placed_g(gi) & b:
                srcs.setdefault(("cagesum", gi), set()).update(x for x in others if x in g.cells)
    for key, cov in extra_srcs:
        srcs.setdefault(key, set()).update(x for x in others if x in cov)
    left = set(others)
    chosen = []
    items = sorted(srcs.items(), key=lambda kv: (kv[0][0] != "house", repr(kv[0])))
    while left:
        best = max(items, key=lambda kv: (len(kv[1] & left), kv[0][0] == "house"), default=None)
        if best is None or not best[1] & left:
            break
        chosen.append((best[0], sorted(best[1] & left)))
        left -= best[1]
    return chosen, sorted(left), others


def _hidden_phrase(nm, key, cov, v, house_gi, st=None, lock_by_key=None):
    p = nm.p
    kind = key[0]
    if kind == "house":
        _, gi, q = key
        return f"the {v} in {nm.cell(q)} covers {nm.unit(gi)}"
    if kind == "neq":
        q = key[1]
        return f"the {v} in {nm.cell(q)} blocks {nm.cells(cov)} ({rel_label(p, q, cov[0])})"
    if kind == "rel":
        q = key[1]
        return f"the {st.vals[q]} in {nm.cell(q)} rules out {v} at {nm.cells(cov)} via the {rel_label(p, q, cov[0])}"
    if kind == "domain":
        return f"{nm.cell(key[1])} is a shaded {'even' if v % 2 else 'odd'} cell"
    if kind == "cagesum":
        return f"{nm.cage(key[1], cells=False)} can't fit a {v} at {nm.cells(cov)}"
    if kind == "lock":
        return lock_by_key[key]
    return ""


def _h_hidden_direct(ctx, locks=None):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    gi = ctx.gi(ctx.m.name)
    if gi is None:
        gi = next(h for h in p.houses if c in p.groups[h].cells)
    extra, lock_txt = [], {}
    if locks is not None:
        for k, lk in enumerate(locks):
            if lk["v"] == v and not lk["rel"] and lk["B"] != gi:
                key = ("lock", k)
                extra.append((key, lk["targets"]))
                lock_txt[key] = _lock_text(nm, lk) + ", blocking {cells}"
            elif lk["rel"] and lk.get("mask", 0) & bit(v):
                key = ("lock", k)
                extra.append((key, lk["targets"]))
                lock_txt[key] = _lock_text(nm, lk) + " (so it can't be " + str(v) + ")"
    chosen, left, others = _hidden_cover(p, st, gi, c, v, extra)
    ok = not left
    phrases = []
    base_cells, base_units, _lines = [], [gi], []
    for key, cov in chosen:
        if key[0] == "lock":
            phrases.append(lock_txt[key].replace("{cells}", nm.cells(cov)))
            lk = locks[key[1]]
            base_cells += lk["poss"]
            base_units += [lk["B"]] + ([lk["A"]] if lk["A"] is not None else [])
        else:
            phrases.append(_hidden_phrase(nm, key, cov, v, gi, st))
            if key[0] == "house":
                base_units.append(key[1])
                base_cells.append(key[2])
            elif key[0] in ("neq", "rel"):
                base_cells.append(key[1])
    u = nm.unit(gi)
    n_emp = len(others) + 1
    if locks is not None and any(k[0] == "lock" for k, _ in chosen):
        short = f"{nm.cell(c)} = {v}: only place for {v} in {u} once a pointing {v} is used"
        teach = (
            f"Where can {v} go in {u}? {_cap('; '.join(phrases))}. That leaves {nm.cell(c)} as the only spot. "
            f"The key step is using a {v} that isn't written yet but is already pinned to one line of a box -- "
            f"it blocks that line just like a real {v}."
        )
    else:
        hint = (
            "This is cross-hatching, the fastest scan: pick a digit and sweep its rows and columns through the box."
            if p.groups[gi].kind == "box"
            else f"Lines with few empty cells are good places to ask 'where does the {v} go?'"
        )
        short = ctx.pick(
            [f"{nm.cell(c)} = {v}: the only place for a {v} in {u}", f"{nm.cell(c)} = {v}: hidden single, {v} in {u}"]
        )
        if not others:
            teach = f"{nm.cell(c)} is the only empty cell of {u} and {v} is missing there."
        else:
            teach = ctx.pick(
                [
                    f"Ask where the {v} goes in {u} ({n_emp} empty cells). {_cap('; '.join(phrases))}. That leaves only "
                    f"{nm.cell(c)}. {hint}",
                    f"Focus on the {v}s around {u}: {'; '.join(phrases)}. Every other empty cell of {u} is blocked, so "
                    f"{nm.cell(c)} must be the {v}. {hint}",
                    f"{_cap(u)} still needs a {v}. {_cap('; '.join(phrases))} -- so the {v} has nowhere to go except "
                    f"{nm.cell(c)}.",
                ]
            )
    J = _J(ctx, digits=[v], base_units=list(dict.fromkeys(base_units)), base_cells=base_cells, cover_cells=others)
    return _result(ctx, J, short, teach, ok)


def _h_pointing_direct(ctx):
    locks, _ = direct_locks(ctx.p, ctx.st)
    if ctx.tech == S.NAKED_DL:
        return _h_naked_direct(ctx, locks)
    return _h_hidden_direct(ctx, locks)


def _since(ctx, c, d):
    """'(it lost 5 to the X-Wing two moves ago)'."""
    t = ctx.st.lost.get((c, d))
    if not t:
        return ""
    idx, tech = t
    ago = ctx.st.idx - idx
    if ago <= 0 or tech in (S.TAKE_NOTES,):
        return ""
    name = CONCEPTS[tech][0] if tech in CONCEPTS else _pretty_tech(tech)
    when = "on the previous move" if ago == 1 else f"{ago} moves ago"
    return f"its {d} went {when} ({name[0].lower() + name[1:] if name[:2] != name[:2].upper() else name})"


def _pretty_tech(tech):
    """Readable name for an engine code without a CONCEPTS entry: '3DMedusa' -> '3D Medusa'."""
    raw = re.sub(r"\((?:direct|notes)\)", "", S.TECH_NAMES.get(tech, "a technique")).strip()
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", raw)


def _h_naked_notes(ctx):
    nm, st = ctx.nm, ctx.st
    c, v = ctx.place
    ok = st.cand[c] == bit(v)
    lost = sorted(((t[0], d) for (q, d), t in st.lost.items() if q == c and d != v), reverse=True)
    recent = _since(ctx, c, lost[0][1]) if lost else ""
    short = f"{nm.cell(c)} = {v}: its only remaining candidate"
    teach = (
        f"{nm.cell(c)}'s pencil marks are down to {nm.cset(st.cand[c])}."
        + (f" The last alternative disappeared recently -- {recent}." if recent else "")
        + f" A cell with one candidate is solved: write {v}, then clean {v} out of its row, column and box."
    )
    J = _J(ctx, digits=[v], base_cells=[c])
    return _result(ctx, J, short, teach, ok)


def _h_hidden_notes(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    gi = ctx.gi(ctx.m.name)
    if gi is None:
        gi = next(h for h in p.houses if c in p.groups[h].cells)
    others = [q for q in p.groups[gi].cells if not st.vals[q] and q != c]
    ok = all(not st.cand[q] & bit(v) for q in others) and st.cand[c] & bit(v)
    u = nm.unit(gi)
    short = f"{nm.cell(c)} = {v}: the only {v} left in the notes of {u}"
    teach = ctx.pick(
        [
            f"Scan the notes of {u} for the digit {v}: it appears only in {nm.cell(c)} {nm.cset(st.cand[c])}. "
            f"Even though that cell has other candidates, {u} needs a {v} somewhere, so {nm.cell(c)} is it.",
            f"In {u}, {v} has been squeezed down to a single cell, {nm.cell(c)}. A hidden single in the notes is easy "
            f"to miss because the cell still shows several candidates -- scan one digit at a time across a house.",
        ]
    )
    J = _J(ctx, digits=[v], base_units=[gi], base_cells=[c], cover_cells=others)
    return _result(ctx, J, short, teach, ok)


# ----------------------------------------------- direct line / mental singles --
def _h_mental(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    md, reasons = mental_view(p, st, level=3)
    hidden = bool(ctx.xm.get("hidden"))
    lines = []
    base_units, base_cells = [], []
    parts = []
    ok = False
    used_rules = set()

    def why(q, d):
        if direct_excl(p, st, q) & bit(d):
            srcs = [s for s in direct_sources(p, st, q) if s[1] & bit(d)]
            s = srcs[0]
            if s[0] == "house":
                gi, where = s[2]
                base_cells.append(where[d])
                return f"the {d} in {nm.cell(where[d])} sees it"
            return _source_text(nm, s[0], s[2], [d], q)
        r = reasons.get((q, d))
        if r is None:
            return None
        if r[0] == "rule":
            used_rules.add(r[1])
        if r[0] == "arc":
            base_cells.append(r[1])
        if r[0] in ("subset",):
            base_units.append(r[1])
            base_cells.extend(r[2])
        if r[0] == "point":
            base_units.extend([r[1], r[2]])
            base_cells.extend(r[4])
        return _mental_reason_text(nm, q, d, r, st)

    house = None
    if hidden:
        for gi in p.groups_of[c]:
            if not p.groups[gi].complete:
                continue
            others = [q for q in p.groups[gi].cells if not st.vals[q] and q != c]
            if all(not md[q] & bit(v) for q in others) and not st.placed_g(gi) & bit(v):
                house = gi
                break
    if house is not None:
        others = [q for q in p.groups[house].cells if not st.vals[q] and q != c]
        direct_blocked = [q for q in others if direct_excl(p, st, q) & bit(v)]
        tricky = [q for q in others if q not in direct_blocked]
        for q in tricky:
            w = why(q, v)
            parts.append(f"{nm.cell(q)} can't be {v} because {w}" if w else f"{nm.cell(q)} is ruled out")
        ok = all(why(q, v) for q in tricky)
        base_units.append(house)
        u = nm.unit(house)
        short = (
            f"{nm.cell(c)} = {v}: the only place for {v} in {u} once the line logic is applied"
            if used_rules
            else f"{nm.cell(c)} = {v}: the only place for {v} in {u}, with a little reasoning in your head"
        )
        scan = (
            f"Ordinary scanning blocks {len(direct_blocked)} of the {len(others) + 1} empty cells "
            f"({nm.cells(direct_blocked)})"
            if direct_blocked
            else "Ordinary scanning doesn't settle it"
        )
        teach = (
            f"Where does the {v} go in {u}? {scan}. "
            f"The rest need a little thought: {'; '.join(parts)}. So {nm.cell(c)} is the {v}."
        )
    else:
        ex = direct_excl(p, st, c)
        rest = [d for d in digits_of(p.full & ~ex) if d != v]
        srcs = direct_sources(p, st, c)
        seen = _cover_phrases(nm, c, sorted(srcs, key=lambda s: -popcount(s[1])), v)
        for kd, _, info in srcs:
            if kd == "house":
                base_units.append(info[0])
            elif kd in ("neq", "rel"):
                base_cells.append(info[0])
        grouped = defaultdict(list)
        for d in rest:
            w = why(c, d)
            if w is None:
                grouped["is ruled out"].append(d)
                continue
            w = w.replace(f" puts a {d} there", " puts it there").replace(f" puts an {d} there", " puts it there")
            grouped[w].append(d)
        for w, ds in grouped.items():
            if w == "is ruled out":
                parts.append(f"{nm.digits(ds, 'and')} {'is' if len(ds) == 1 else 'are'} ruled out")
            elif len(ds) == 1:
                parts.append(f"{ds[0]} fails because {w}")
            else:
                parts.append(
                    f"{nm.digits(ds, 'and')} all fail because " + w.replace(" puts it there", " puts any of them there")
                )
        ok = all(why(c, d) for d in rest)
        short = (
            f"{nm.cell(c)} = {v}: every other digit is excluded by the grid and the line rules"
            if used_rules
            else f"{nm.cell(c)} = {v}: every other digit is excluded, with a little reasoning in your head"
        )
        teach = (
            f"Start with what {nm.cell(c)} sees directly: {'; '.join(seen) if seen else 'very little'}, "
            f"leaving {nm.digits([v] + rest)}. Now use the rules in your head: {'; '.join(parts)}. "
            f"Only {v} survives -- no pencil marks needed."
        )
    for key in used_rules:
        r = rules(p)[key]
        lines.append((r.line_kind or r.kind, r.cells))
    if ctx.tech == S.MENTAL_D and ctx.xm.get("subset"):
        teach += (
            f" The key was a mental {['', '', 'pair', 'triple'][min(ctx.xm['subset'], 3)]}: cells that can only "
            f"hold the same digits lock those digits out of the rest of the house."
        )
    J = _J(
        ctx,
        digits=[v],
        base_units=list(dict.fromkeys(base_units)),
        base_cells=base_cells,
        constraints=[_con_json(rules(p)[k]) for k in used_rules],
    )
    return _result(ctx, J, short, teach, ok, lines=lines)


def _con_json(rule):
    return {
        "type": rule.line_kind or rule.kind,
        "index": rule.index if rule.index is not None else rule.group,
        "cells": list(rule.cells),
        "params": {k: v for k, v in rule.con.items() if k in ("total", "count", "k", "dots", "each")}
        | ({"total": rule.total} if rule.total is not None else {}),
    }


# ---------------------------------------------------- constraint single ------
def _rule_from_move(ctx):
    p = ctx.p
    R = rules(p)
    idx = ctx.xm.get("constraint")
    if idx is not None and idx >= 0 and ("con", idx) in R:
        return R[("con", idx)]
    name = ctx.m.name or ""
    mm = re.search(r"#(\d+)$", name)
    if mm and not name.startswith("leftovers") and ("con", int(mm.group(1))) in R:
        return R[("con", int(mm.group(1)))]
    mm = re.match(r"cage (\S+)", name)
    if mm and ctx.gi(mm.group(1)) is not None:
        return R.get(("cage", ctx.gi(mm.group(1))))
    gi = ctx.xm.get("cage_group")
    if gi is not None and ("cage", gi) in R:
        return R[("cage", gi)]
    if ctx.gi(name) is not None and ("cage", ctx.gi(name)) in R:
        return R[("cage", ctx.gi(name))]
    return None


def _h_nary_direct(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    rule = _rule_from_move(ctx)
    if rule is None:
        return _generic(ctx)
    known = [(q, st.vals[q]) for q in rule.cells if st.vals[q]]
    dom = [bit(st.vals[q]) if st.vals[q] else p.domains[q] for q in rule.cells]
    res = enum_rule(p, rule, dom)
    k = rule.cells.index(c)
    ok = res["sup"][k] == bit(v)
    ks = ", ".join(f"{nm.cell(q)}={d}" for q, d in known)
    kind = rule.line_kind or rule.kind
    if kind in ("sum", "cage", "little_killer"):
        s = sum(d for _, d in known)
        how = f"the digits already in it add to {s}, so the last cell must be {rule.total} - {s} = {v}"
    elif kind == "arrow":
        circ = rule.con["circle"]
        line = rule.con["line"]
        if c in circ:
            how = f"the arrow's digits add up to {sum(st.vals[q] for q in line)}, so the circle is {v}"
        else:
            tot = int("".join(str(st.vals[q]) for q in circ))
            s = sum(st.vals[q] for q in line if st.vals[q])
            how = f"the circle says {tot} and the rest of the arrow already adds to {s}, so {nm.cell(c)} is {tot - s}"
    elif kind == "set" or kind == "renban":
        how = (
            f"its digits so far ({nm.digits([d for _, d in known], 'and')}) leave exactly one way to complete a "
            f"run of {len(rule.cells)} consecutive digits"
        )
    else:
        how = "only one digit completes it"
    short = f"{nm.cell(c)} = {v}: completes {rule.label}"
    teach = (
        f"{_cap(rule.label)} has one empty cell left, {nm.cell(c)} ({ks}). {_cap(how)}. "
        f"Whenever a cage, arrow or line is nearly full, do the arithmetic -- the last cell is often forced "
        f"before any scanning."
    )
    J = _J(ctx, digits=[v], constraints=[_con_json(rule)], base_cells=list(rule.cells))
    return _result(ctx, J, short, teach, ok, lines=[(kind, rule.cells)])


# --------------------------------------------------------------- innies -----
def _house_unions(p, max_k=3):
    if getattr(p, "_xunions", None) is not None:
        return p._xunions
    hs = p.houses
    cs = {h: set(p.groups[h].cells) for h in hs}
    pos = {xy: i for i, xy in enumerate(p.coords)}
    nb = {}
    for h in hs:
        border = set()
        for c in cs[h]:
            r, cc = p.coords[c]
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = pos.get((r + dr, cc + dc))
                if q is not None and q not in cs[h]:
                    border.add(q)
        nb[h] = {h2 for h2 in hs if h2 != h and not cs[h] & cs[h2] and cs[h2] & border}
    out = {(h,) for h in hs}
    frontier = set(out)
    for _ in range(max_k - 1):
        nxt = set()
        for u in frontier:
            for h in u:
                for h2 in nb[h]:
                    if h2 in u or any(cs[h2] & cs[x] for x in u):
                        continue
                    nxt.add(tuple(sorted(u + (h2,))))
        out |= nxt
        frontier = nxt
    p._xunions = sorted(out, key=len)
    return p._xunions


def _innie_sets(p, max_cells=4):
    key = f"_xinnie{max_cells}"
    if getattr(p, key, None) is not None:
        return getattr(p, key)
    tri = p.D * (p.D + 1) // 2
    sums = [gi for gi, g in enumerate(p.groups) if g.total is not None]
    out = []
    for union in _house_unions(p):
        H = set().union(*(p.groups[h].cells for h in union))
        inside, touching = [], []
        for gi in sums:
            cs = set(p.groups[gi].cells)
            if cs <= H:
                inside.append(gi)
            elif cs & H:
                touching.append(gi)
        covered = set().union(*(p.groups[gi].cells for gi in inside)) if inside else set()
        Rr = sorted(c for c in H if c not in covered)
        if Rr and len(Rr) <= max_cells and inside:
            out.append(
                {
                    "union": union,
                    "cells": Rr,
                    "total": tri * len(union) - sum(p.groups[g].total for g in inside),
                    "cages": inside,
                    "kind": "innie",
                }
            )
        allc = inside + touching
        cov = set().union(*(p.groups[gi].cells for gi in allc)) if allc else set()
        if touching and H <= cov:
            O = sorted(cov - H)
            if len(O) <= max_cells:
                out.append(
                    {
                        "union": union,
                        "cells": O,
                        "total": sum(p.groups[g].total for g in allc) - tri * len(union),
                        "cages": allc,
                        "kind": "outie",
                    }
                )
    setattr(p, key, out)
    return out


def _union_name(nm, union):
    names = [nm.unit(h) for h in union]
    if len(names) == 1:
        return names[0]
    kinds = {nm.p.groups[h].kind for h in union}
    if kinds == {"row"}:
        return "rows " + _join([n.split()[1] for n in names])
    if kinds == {"col"}:
        return "columns " + _join([n.split()[1] for n in names])
    if kinds == {"box"}:
        return "boxes " + _join([n.split()[1] for n in names])
    return _join(names)


def _find_innie(ctx, cells_needed, kind=None, max_cells=4):
    """Candidate rule-of-45 sets containing the needed cells, smallest first."""
    p = ctx.p
    hname = (ctx.m.name or "").split()[-1] if ctx.m.name else None
    hgi = ctx.gi(hname) if hname else ctx.xm.get("house")
    out = []
    for s in _innie_sets(p, max_cells):
        if kind and s["kind"] != kind:
            continue
        if hgi is not None and s["union"][0] != hgi and hgi not in s["union"]:
            continue
        if not set(cells_needed) <= set(s["cells"]):
            continue
        out.append(s)
    out.sort(key=lambda s: (len(s["union"]), len(s["cells"])))
    return out


def _h_innie(ctx):
    _nm, _p, _st = ctx.nm, ctx.p, ctx.st
    kind = "outie" if (ctx.m.name or "").startswith("outie") or ctx.xm.get("outie") else "innie"
    need = [ctx.place[0]] if ctx.place else sorted({c for c, _ in ctx.elims})
    cands = _find_innie(ctx, need, kind, max_cells=4 if ctx.tech != S.INNIE_X else 9)
    if not cands:
        return _generic(ctx)
    first = None
    for s in cands[:12]:
        r = _innie_render(ctx, s, kind)
        if r["verified"]:
            return r
        first = first or r
    return first


def _innie_render(ctx, s, kind):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    tri = p.D * (p.D + 1) // 2
    U = _union_name(nm, s["union"])
    cage_txt = " + ".join(str(p.groups[g].total) for g in s["cages"])
    cage_sum = sum(p.groups[g].total for g in s["cages"])
    house_sum = tri * len(s["union"])
    emp = [c for c in s["cells"] if not st.vals[c]]
    known = [(c, st.vals[c]) for c in s["cells"] if st.vals[c]]
    rem = s["total"] - sum(d for _, d in known)
    lines = [("cage", p.groups[g].cells) for g in s["cages"]]
    if kind == "innie":
        arith = (
            f"{_cap(U)} must total {house_sum}. The cages lying completely inside add up to "
            f"{cage_txt} = {cage_sum}, so the uncovered cell{'s' if len(s['cells']) > 1 else ''} "
            f"{nm.cells(s['cells'])} must total {house_sum} - {cage_sum} = {s['total']}"
        )
    else:
        arith = (
            f"The cages touching {U} add up to {cage_txt} = {cage_sum}; {U} itself is {house_sum}, so the "
            f"cell{'s' if len(s['cells']) > 1 else ''} poking out, {nm.cells(s['cells'])}, must total "
            f"{cage_sum} - {house_sum} = {s['total']}"
        )
    if known:
        arith += f" ({', '.join(f'{nm.cell(c)} is already {d}' for c, d in known)}, leaving {rem} for the rest)"
    ok = True
    if ctx.place:
        c, v = ctx.place
        ok = len(emp) == 1 and emp[0] == c and rem == v
        short = f"{nm.cell(c)} = {v}: rule of 45 -- the {kind} of {U}"
        teach = (
            f"{arith}. With only {nm.cell(c)} open, it must be {v}. Hunt for innies and outies by looking for "
            f"a house (or a band of houses) that cages almost cover exactly."
        )
    else:
        dom = [st.cand[c] for c in emp]
        distinct = bool(set.intersection(*(set(p.groups_of[c]) for c in emp))) if emp else False
        rule = Rule("innie", emp, f"the {kind} sum", total=rem, distinct=distinct)
        res = enum_rule(p, rule, dom)
        targets = {(emp[i], d) for i in range(len(emp)) for d in digits_of(st.cand[emp[i]] & ~res["sup"][i])}
        ok = set(ctx.elims) <= targets
        combos = _combo_sets(res, len(emp))
        short = f"{fmt_elims(nm, ctx.elims)}: rule of 45 -- the {kind} cells of {U} total {rem}"
        why = _sum_elim_reasons(ctx, rule, emp, res, rem)
        teach = (
            f"{arith}. Treat {nm.cells(emp)} as a virtual cage of {rem}"
            f"{'' if distinct else ' (digits may repeat: the cells are not all in one house)'}: "
            f"{_combo_phrase(combos, distinct)}. {why} "
            f"Rule-of-45 sums turn any nearly-covered house into an extra cage."
        )
    J = _J(
        ctx,
        digits=[ctx.place[1]] if ctx.place else _elim_digits(ctx),
        base_units=list(s["union"]),
        base_cells=s["cells"],
        constraints=[
            {"type": kind, "index": None, "cells": s["cells"], "params": {"total": s["total"], "cages": s["cages"]}}
        ],
    )
    return _result(ctx, J, short, teach, ok, lines=lines)


def _combo_sets(res, n):
    if not res["complete"] or res["count"] is None or res["count"] > len(res["sols"]):
        return [None]
    sets = []
    for sol in res["sols"]:
        k = tuple(sorted(sol))
        if k not in sets:
            sets.append(k)
    return sets


_SUMLIKE = ("sum", "cage", "little_killer", "innie", "arrow", "equal_sum")


def _combo_phrase(combos, distinct=True, limit=6, sets=False):
    if not combos:
        return "no combination fits"
    if None in combos:
        return "many digit sets still fit"
    if len(combos) > limit:
        return f"{len(combos)} different digit sets still fit"
    txt = _join([("{" + ",".join(map(str, k)) + "}") if sets else "+".join(map(str, k)) for k in combos], "or")
    return f"the only fillings left are {txt}" if len(combos) > 1 else f"the only filling left is {txt}"


def _cant(nm, elims):
    """'r1c4 can't be 9; r2c2 can't be 1 or 3'."""
    by_cell = defaultdict(list)
    for c, d in elims:
        by_cell[c].append(d)
    return "; ".join(f"{nm.cell(c)} can't be {nm.digits(ds)}" for c, ds in sorted(by_cell.items()))


def _elim_list(nm, elims):
    by_d = defaultdict(list)
    for c, d in elims:
        by_d[d].append(c)
    by_c = defaultdict(list)
    for c, d in elims:
        by_c[c].append(d)
    if len(by_c) < len(by_d):
        return _join([f"{nm.digits(ds, 'and')} from {nm.cell(c)}" for c, ds in sorted(by_c.items())])
    parts = [f"{d} from {nm.cells(cs)}" for d, cs in sorted(by_d.items())]
    return _join(parts)


# ------------------------------------------------------------ notes: locked --
def _h_locked(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    name = ctx.m.name or ""
    v = _elim_digits(ctx)[0] if ctx.elims else None
    bi = ai = None
    eb, ec = ctx.engine.get("base_units") or [], ctx.engine.get("cover_units") or []
    if len(eb) == 1 and len(ec) == 1:
        bi, ai = eb[0], ec[0]
        ctx.used_engine = True
    elif "->" in name:
        bname, aname = name.split("->")
        bi, ai = ctx.gi(bname), ctx.gi(aname)
    if bi is None or ai is None:
        for b in p.houses:
            poss = [c for c in p.groups[b].cells if not st.vals[c] and st.cand[c] & bit(v)]
            for a in range(len(p.groups)):
                if (
                    a != b
                    and poss
                    and all(c in p.groups[a].cells for c in poss)
                    and all(c in p.groups[a].cells and c not in p.groups[b].cells for c, _ in ctx.elims)
                ):
                    bi, ai = b, a
                    break
            if bi is not None:
                break
    if bi is None:
        return _generic(ctx)
    B, A = p.groups[bi], p.groups[ai]
    poss = [c for c in B.cells if not st.vals[c] and st.cand[c] & bit(v)]
    ok = all(c in A.cells for c in poss) and all(c in A.cells and c not in B.cells for c, _ in ctx.elims)
    ub, ua = nm.unit(bi), nm.unit(ai)
    tg = sorted({c for c, _ in ctx.elims})
    if A.kind == "cage":
        short = f"{fmt_elims(nm, ctx.elims)}: the {v} of {ub} must sit inside {nm.cage(ai, cells=False)}"
        teach = (
            f"In {ub} the {v} can only go in {nm.cells(poss, 'or')}, and all of them are inside "
            f"{nm.cage(ai)}. So that cage contains the {v}, and since a cage can't repeat a digit, "
            f"{nm.cells(tg)} can't be {v}."
        )
    elif B.kind in ("row", "col") and A.kind not in ("row", "col"):
        short = f"{fmt_elims(nm, ctx.elims)}: claiming -- the {v} of {ub} is confined to {ua}"
        teach = ctx.pick(
            [
                f"Look at the {v}s in {ub}: they only appear in {nm.cells(poss)}, all inside {ua}. Whichever one is "
                f"right, {ua}'s {v} is on {ub}, so the other cells of {ua} -- {nm.cells(tg)} -- can't be {v}. "
                f"This 'claiming' (box-line) pattern is worth checking whenever a line's candidates for a digit "
                f"bunch up in one box.",
                f"{_cap(ub)} can only place its {v} in {nm.cells(poss, 'or')} -- all in {ua}. That {v} is therefore "
                f"{ua}'s {v} as well, which clears {v} from {nm.cells(tg)}.",
            ]
        )
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: pointing -- the {v}s of {ub} are locked into {ua}"
        teach = ctx.pick(
            [
                f"In {ub} the {v} can only go in {nm.cells(poss, 'or')}, which all lie in {ua}. So {ub}'s {v} is "
                f"also {ua}'s {v}, and nothing else in {ua} can be {v}: remove it from {nm.cells(tg)}. "
                f"Look for boxes where a digit's notes line up in a single row or column.",
                f"The {v}s of {ub} line up: {nm.cells(poss)}, all on {ua}. Whichever is true, it supplies "
                f"{ua}'s {v} -- so {nm.cells(tg)} lose their {v}.",
            ]
        )
    J = _J(ctx, digits=[v], base_units=[bi], cover_units=[ai], base_cells=poss, cover_cells=tg)
    return _result(ctx, J, short, teach, ok)


# ----------------------------------------------------------- notes: subsets --
def _h_subset(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    k = {S.NPAIR: 2, S.HPAIR: 2, S.NTRIPLE: 3, S.HTRIPLE: 3, S.NQUAD: 4, S.HQUAD: 4}[ctx.tech]
    naked = ctx.tech in (S.NPAIR, S.NTRIPLE, S.NQUAD)
    gi = ctx.gi(ctx.m.name)
    houses = [gi] if gi is not None else p.houses
    found = None
    eb, pc = ctx.engine.get("base_units") or [], ctx.engine.get("pattern_cells") or []
    if len(eb) == 1 and len(pc) == k:
        u = 0
        for c in pc:
            u |= st.cand[c]
        if naked and popcount(u) == k:
            found = (eb[0], tuple(sorted(pc)), u)
        elif not naked:
            emp = [c for c in p.groups[eb[0]].cells if not st.vals[c]]
            keep = 0
            for d in digits_of(p.full & ~st.placed_g(eb[0])):
                cs = {c for c in emp if st.cand[c] & bit(d)}
                if cs and cs <= set(pc):
                    keep |= bit(d)
            if popcount(keep) == k:
                found = (eb[0], tuple(sorted(pc)), keep)
        if found:
            ctx.used_engine = True
            houses = []
    for hi in houses:
        emp = [c for c in p.groups[hi].cells if not st.vals[c]]
        if naked:
            small = [c for c in emp if 2 <= popcount(st.cand[c]) <= k]
            for combo in combinations(small, k):
                u = 0
                for c in combo:
                    u |= st.cand[c]
                if popcount(u) != k:
                    continue
                el = {(c, d) for c in emp if c not in combo for d in digits_of(st.cand[c] & u)}
                if set(ctx.elims) <= el and el:
                    found = (hi, combo, u)
                    break
        else:
            missing = list(digits_of(p.full & ~st.placed_g(hi)))
            pos = {d: frozenset(c for c in emp if st.cand[c] & bit(d)) for d in missing}
            cands = [d for d in missing if 2 <= len(pos[d]) <= k]
            for combo in combinations(cands, k):
                cells = frozenset().union(*(pos[d] for d in combo))
                if len(cells) != k:
                    continue
                keep = sum(bit(d) for d in combo)
                el = {(c, d) for c in cells for d in digits_of(st.cand[c] & ~keep)}
                if set(ctx.elims) <= el and el:
                    found = (hi, tuple(sorted(cells)), keep)
                    break
        if found:
            break
    if not found:
        return _generic(ctx)
    hi, cells, u = found
    if naked:
        okset = {
            (c, d) for c in p.groups[hi].cells if not st.vals[c] and c not in cells for d in digits_of(st.cand[c] & u)
        }
    else:
        okset = {(c, d) for c in cells for d in digits_of(st.cand[c] & ~u)}
    sub_ok = set(ctx.elims) <= okset
    word = {2: "pair", 3: "triple", 4: "quad"}[k]
    U = nm.unit(hi)
    ds = list(digits_of(u))
    cl = ", ".join(f"{nm.cell(c)} {nm.cset(st.cand[c])}" for c in nm.sort(cells))
    tg = sorted({c for c, _ in ctx.elims})
    if naked:
        short = f"{fmt_elims(nm, ctx.elims)}: naked {word} {'/'.join(map(str, ds))} in {U}"
        teach = ctx.pick(
            [
                f"In {U}, the cells {cl} use only the digits {nm.digits(ds, 'and')} between them. {k} cells, {k} digits: "
                f"those digits must fill exactly those cells, so no other cell of {U} can have them -- clear them from "
                f"{nm.cells(tg)}.",
                f"Spot the {word}: {cl} in {U}. However they are arranged, {nm.digits(ds, 'and')} are used up there, "
                f"which removes them from {nm.cells(tg)}.",
            ]
        )
        J = _J(ctx, digits=ds, base_units=[hi], base_cells=list(cells), cover_cells=tg)
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: hidden {word} {'/'.join(map(str, ds))} in {U}"
        teach = ctx.pick(
            [
                f"In {U}, the digits {nm.digits(ds, 'and')} can only go in {nm.cells(cells)} ({cl}). {k} digits squeezed "
                f"into {k} cells means those cells are exactly these digits, so their other candidates go. Hidden "
                f"subsets are found by scanning digits, not cells: look for digits with only two or three spots.",
                f"Track where {nm.digits(ds, 'and')} can go in {U}: only {nm.cells(cells)}. They take those cells "
                f"between them, so everything else pencilled there is wrong.",
            ]
        )
        J = _J(ctx, digits=ds, base_units=[hi], base_cells=list(cells), cover_cells=list(cells))
    return _result(ctx, J, short, teach, sub_ok)


# -------------------------------------------------------------- fish --------
def _fish_search(p, st, v, k, elims, finned=False, max_fins=3, lines_only=False):
    b = bit(v)
    hs = [h for h in p.houses if p.groups[h].kind in ("row", "col")] if lines_only else p.houses
    pos = {h: frozenset(c for c in p.groups[h].cells if not st.vals[c] and st.cand[c] & b) for h in hs}
    hc = {h: frozenset(p.groups[h].cells) for h in hs}
    tset = set(elims)
    bases = [h for h in hs if 2 <= len(pos[h]) <= (k + max_fins if finned else k)]
    for combo in combinations(bases, k):
        if any(hc[a] & hc[c] for a, c in combinations(combo, 2)):
            continue
        U = frozenset().union(*(pos[h] for h in combo))
        covers = [h for h in hs if h not in combo and pos[h] & U]
        for cov in combinations(covers, k):
            if any(hc[a] & hc[c] for a, c in combinations(cov, 2)):
                continue
            CU = frozenset().union(*(hc[h] for h in cov))
            fins = U - CU
            if not finned and fins:
                continue
            if finned and not (1 <= len(fins) <= max_fins):
                continue
            el = set()
            for h in cov:
                for c in pos[h]:
                    if c in U:
                        continue
                    if fins and not all(c in p.peers[f] for f in fins):
                        continue
                    el.add((c, v))
            if tset <= el:
                return combo, cov, U, fins
    return None


def _h_fish(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    v = _elim_digits(ctx)[0]
    k = {S.XWING: 2, S.SWORDFISH: 3, S.JELLYFISH: 4}.get(ctx.tech) or ctx.xm.get("size") or 2
    finned = ctx.tech == S.FINNED_FISH
    res = _engine_fish(ctx, v)
    if res:
        k = len(res[0])
    for kk in [] if res else [k] if not finned else [k, 2, 3, 4]:
        res = _fish_search(p, st, v, kk, ctx.elims, finned=finned)
        if res:
            k = kk
            break
    if not res:
        return _generic(ctx)
    base, cov, U, fins = res
    fkey, adj = fish_shape(p, base, cov, fins, U)
    plain = False
    if adj in (
        "Franken",
        "Mutant",
    ):  # a box in base / cover, or mixed lines: prefer the same eliminations from a plain row / column fish
        for kk, fn in [(x, False) for x in range(2, len(base) + 1)] + [(x, True) for x in range(2, len(base) + 1)]:
            alt = _fish_search(p, st, v, kk, ctx.elims, finned=fn, lines_only=True)
            if alt and len({p.groups[h].kind for h in alt[0]}) == 1 and len({p.groups[h].kind for h in alt[1]}) == 1:
                base, cov, U, fins = alt
                k = kk
                fkey, adj = fish_shape(p, base, cov, fins, U)
                plain = True
                break
    size_name = {2: "X-Wing", 3: "Swordfish", 4: "Jellyfish"}.get(len(base), "Jellyfish")
    built = " ".join(
        x
        for x in (
            ("Sashimi" if adj == "Sashimi" else "Finned") if fins else "",
            adj if adj in ("Franken", "Mutant") else "",
            size_name,
        )
        if x
    )
    name = ctx.code if ctx.code and not ctx.code.startswith("Mutant") and len(ctx.code) > 3 and not plain else built
    name = name.replace("Sashimi Sashimi", "Sashimi")
    bn = _join([nm.unit(h) for h in base])
    cn = _join([nm.unit(h) for h in cov])
    tg = sorted({c for c, _ in ctx.elims})
    corner = "; ".join(f"{nm.unit(h)}: {nm.cells([c for c in U if c in p.groups[h].cells], 'or')}" for h in base)
    if not fins:
        short = f"{fmt_elims(nm, ctx.elims)}: {name} on {v} ({bn} / {cn})"
        if k == 2:
            teach = (
                f"Follow the {v}s in {bn}: each has exactly two spots ({corner}), and those spots line up in "
                f"{cn}. The two {v}s must sit on opposite corners of the rectangle, so they use up {cn}'s {v}s "
                f"-- {nm.cells(tg)} can't be {v}. X-Wings show up when a digit has only two places in two "
                f"parallel lines."
            )
        else:
            kw = {3: "three", 4: "four"}.get(k, str(k))
            teach = (
                f"Look at the {v}s in {bn} ({corner}). All of them fall inside {kw} houses: {cn}. Those {kw} "
                f"houses must each hold one {v}, and the {kw} {v}s of {bn} are exactly them -- so {v} disappears "
                f"from the rest of {cn}: {nm.cells(tg)}. Fish are found digit by digit: list where one digit can "
                f"go in every row (or column) and look for {kw} that share {kw} columns (or rows)."
            )
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: {name} on {v} with fin{'s' if len(fins) > 1 else ''} at {nm.cells(fins)}"
        teach = (
            f"The {v}s of {bn} ({corner}) almost form a {name.split()[-1]} over {cn} -- except for the "
            f"fin{'s' if len(fins) > 1 else ''} {nm.cells(fins)}. Either "
            f"{'a fin' if len(fins) > 1 else 'the fin'} is the {v} or the fish works; cells that the fish would "
            f"clear AND that see {'every fin' if len(fins) > 1 else 'the fin'} lose {v} either way: "
            f"{nm.cells(tg)}."
        )
    if adj == "Sashimi" or "Sashimi" in name:
        teach += (
            " It is a sashimi fish: one base house has only the fin and a single other candidate, so the "
            "pattern isn't even a complete fish without the fin."
        )
    if "Franken" in name:
        teach += " It is a Franken fish: a box takes the place of one of the rows or columns."
    elif adj == "Mutant":
        teach += " It is a mutant fish: rows and columns are mixed within the base (or cover) houses."
    J = _J(
        ctx,
        digits=[v],
        base_units=list(base),
        cover_units=list(cov),
        base_cells=sorted(U),
        fins=sorted(fins),
        cover_cells=tg,
        pattern=name,
    )
    r = _result(ctx, J, short, teach, True)
    if fins and "Franken" in name:
        fkey = "franken_fish"
    r["pattern_key"] = fkey
    return r


def _engine_fish(ctx, v):
    """Fish from the engine's base / cover units (step.move.explain)."""
    e = ctx.engine
    bu, cu = e.get("base_units") or [], e.get("cover_units") or []
    if not bu or not cu or len(bu) != len(cu):
        return None
    p, st = ctx.p, ctx.st
    U = {c for h in bu for c in p.groups[h].cells if not st.vals[c] and st.cand[c] & bit(v)}
    CU = {c for h in cu for c in p.groups[h].cells}
    ctx.used_engine = True
    return tuple(bu), tuple(cu), U, U - CU


# -------------------------------------------------------------- wings -------
def _h_wing(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    xyz = ctx.tech == S.XYZWING
    z = _elim_digits(ctx)[0]
    zb = bit(z)
    tset = set(ctx.elims)
    for piv in range(p.N):
        if st.vals[piv] or popcount(st.cand[piv]) != (3 if xyz else 2):
            continue
        pc = st.cand[piv]
        if xyz and not pc & zb:
            continue
        wings = [q for q in p.peer_list[piv] if not st.vals[q] and popcount(st.cand[q]) == 2 and st.cand[q] & zb]
        for w1, w2 in combinations(wings, 2):
            a, b2 = st.cand[w1], st.cand[w2]
            if xyz:
                if (a | b2) != pc or a == b2 or a & ~pc or b2 & ~pc or a & b2 != zb:
                    continue
                tg = p.peers[piv] & p.peers[w1] & p.peers[w2]
            else:
                if a == b2 or a & b2 != zb or (a | b2) & ~zb != pc or pc & zb:
                    continue
                tg = p.peers[w1] & p.peers[w2]
            el = {(c, z) for c in tg if c not in (piv, w1, w2) and not st.vals[c] and st.cand[c] & zb}
            if tset <= el:
                x, y = [d for d in digits_of(pc) if d != z][:2]
                tgc = sorted({c for c, _ in ctx.elims})
                name = "XYZ-Wing" if xyz else "XY-Wing"
                short = f"{fmt_elims(nm, ctx.elims)}: {name} with pivot {nm.cell(piv)}"
                if xyz:
                    teach = (
                        f"The pivot {nm.cell(piv)} {nm.cset(pc)} sees {nm.cell(w1)} {nm.cset(a)} and "
                        f"{nm.cell(w2)} {nm.cset(b2)}. If the pivot isn't {z}, it is {x} or {y}, which turns "
                        f"one of the wings into {z}; so one of the three cells is {z}. {_subj(nm, tgc)} "
                        f"see{'s' if len(tgc) == 1 else ''} all three and can't be {z}."
                    )
                else:
                    wx = w1 if st.cand[w1] & bit(x) else w2
                    wy = w2 if wx == w1 else w1
                    teach = ctx.pick(
                        [
                            f"Find a two-candidate pivot with two two-candidate wings: {nm.cell(piv)} {nm.cset(pc)} sees "
                            f"{nm.cell(wx)} {nm.cset(st.cand[wx])} and {nm.cell(wy)} {nm.cset(st.cand[wy])}. If the pivot "
                            f"is {x}, {nm.cell(wx)} becomes {z}; if it is {y}, {nm.cell(wy)} becomes {z}. Either way one "
                            f"wing is {z}, so {nm.cells(tgc)}, which see{'s' if len(tgc) == 1 else ''} both wings, "
                            f"can't be {z}.",
                            f"Pivot {nm.cell(piv)} {nm.cset(pc)}, wings {nm.cell(wx)} {nm.cset(st.cand[wx])} and "
                            f"{nm.cell(wy)} {nm.cset(st.cand[wy])}: whatever the pivot is, a wing ends up {z}. "
                            f"Remove {z} from every cell that sees both wings: {nm.cells(tgc)}.",
                        ]
                    )
                J = _J(ctx, digits=[z], base_cells=[piv, w1, w2], z=z, cover_cells=tgc)
                return _result(ctx, J, short, teach, True)
    return _generic(ctx)


# ------------------------------------------------------------- colouring ----
def _h_coloring(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    v = _elim_digits(ctx)[0]
    b = bit(v)
    adj, via = {}, {}
    for hi in p.houses:
        cs = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & b]
        if len(cs) == 2:
            x, y = cs
            adj.setdefault(x, set()).add(y)
            adj.setdefault(y, set()).add(x)
            via.setdefault(frozenset(cs), hi)
    color = {}
    for start in sorted(adj):
        if start in color:
            continue
        comp = {start: 0}
        stack = [start]
        while stack:
            x = stack.pop()
            for y in sorted(adj[x]):
                if y not in comp:
                    comp[y] = 1 - comp[x]
                    stack.append(y)
        color.update(comp)
        if len(comp) < 4:
            continue
        g = ([c for c in comp if comp[c] == 0], [c for c in comp if comp[c] == 1])
        wrap = None
        for side in (0, 1):
            for x, q in combinations(g[side], 2):
                if q in p.peers[x]:
                    wrap = (side, x, q)
                    break
            if wrap:
                break
        if wrap:
            el = {(c, v) for c in g[wrap[0]]}
        else:
            el = {
                (c, v)
                for c in range(p.N)
                if not st.vals[c]
                and c not in comp
                and st.cand[c] & b
                and p.peers[c] & set(g[0])
                and p.peers[c] & set(g[1])
            }
        if not set(ctx.elims) <= el:
            continue
        links = [
            {"a": (x, v), "b": (y, v), "strong": True, "source": "bilocal", "unit": via.get(frozenset((x, y)))}
            for x in comp
            for y in adj[x]
            if x < y
        ]
        tg = sorted({c for c, _ in ctx.elims})
        A, Bc = nm.cells(g[0]), nm.cells(g[1])
        short = f"{fmt_elims(nm, ctx.elims)}: colouring on {v}"
        if wrap:
            teach = (
                f"Colour the {v}s that form conjugate pairs (houses with exactly two {v}s): one colour is "
                f"{A}, the other {Bc}. Exactly one colour is the truth. But {nm.cell(wrap[1])} and "
                f"{nm.cell(wrap[2])} share a colour and see each other -- they can't both be {v}, so that "
                f"whole colour is false: remove {v} from {nm.cells(tg)}."
            )
        else:
            teach = (
                f"Chain the {v}s through houses where {v} has only two spots, alternating two colours: "
                f"{A} versus {Bc}. One colour holds all the real {v}s. {_subj(nm, tg)} "
                f"see{'s' if len(tg) == 1 else ''} a cell of each colour, so whichever colour wins, "
                f"{'it sees' if len(tg) == 1 else 'they see'} a {v} -- no {v} there."
            )
        J = _J(ctx, digits=[v], base_cells=g[0], cover_cells=g[1], links=links)
        chain = [[nm.cell(lk["a"][0]), nm.cell(lk["b"][0]), v, "strong"] for lk in links]
        return _result(ctx, J, short, teach, True, chain=chain)
    return _generic(ctx)


# ----------------------------------------------------------- pair relations --
def _h_pairarc(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    parts, base_cells, units = [], [], []
    ok = True
    by_cell = defaultdict(list)
    for c, d in ctx.elims:
        by_cell[c].append(d)
    gi = ctx.gi(ctx.m.name) if ctx.m.name else None
    for x, ds in sorted(by_cell.items()):
        done = False
        if gi is not None:  # relation pointing
            for v in digits_of(p.full & ~st.placed_g(gi)):
                poss = [c for c in p.groups[gi].cells if not st.vals[c] and st.cand[c] & bit(v)]
                if len(poss) < 2 or x in poss:
                    continue
                rm = p.full
                for c in poss:
                    rm &= _rel_ex(p, c, x, v)
                if all(rm & bit(d) for d in ds):
                    lab = rel_label(p, poss[0], x)
                    parts.append(
                        f"the {v} of {nm.unit(gi)} must be in {nm.cells(poss, 'or')}, and every one of "
                        f"those is {lab}-linked to {nm.cell(x)}, so {nm.cell(x)} can't be "
                        f"{nm.digits(ds)}"
                    )
                    base_cells += poss
                    units.append(gi)
                    done = True
                    break
        if not done:
            for a in sorted(set(p.nonconsec[x]) | set(p.neq[x])):
                if st.vals[a] or not st.cand[a]:
                    continue
                if all(all(_rel_ex(p, a, x, w) & bit(d) for w in digits_of(st.cand[a])) for d in ds):
                    lab = rel_label(p, a, x)
                    parts.append(
                        f"{nm.cell(x)} can't be {nm.digits(ds)}: its {lab} partner {nm.cell(a)} "
                        f"{nm.cset(st.cand[a])} would have no option left"
                    )
                    base_cells.append(a)
                    done = True
                    break
        ok &= done
        if not done:
            parts.append(f"{nm.cell(x)} loses {nm.digits(ds, 'and')}")
    short = (
        f"{fmt_elims(nm, ctx.elims)}: "
        + (rel_label(p, *(_first_rel(p, base_cells, by_cell))) or "pair rule")
        + " logic"
    )
    teach = (
        f"{_cap('; '.join(parts))}. Rules between neighbouring cells work both ways: every candidate needs "
        f"at least one partner value that is still possible. Check the cells along dots and lines whose "
        f"partners have few candidates."
    )
    J = _J(ctx, digits=_elim_digits(ctx), base_cells=base_cells, base_units=units)
    return _result(ctx, J, short, teach, ok)


def _first_rel(p, base_cells, by_cell):
    x = next(iter(by_cell))
    for a in base_cells:
        if rel_label(p, a, x):
            return a, x
    return x, x


# ---------------------------------------------------- combinations / lines --
def _h_combo(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    rule = _rule_from_move(ctx)
    if rule is None:
        if ctx.tech == S.LOL_COMBO:
            return _h_lol(ctx)
        return _generic(ctx)
    dom = _rule_dom(st, rule)
    res = enum_rule(p, rule, dom)
    computed = {
        (c, d) for i, c in enumerate(rule.cells) if not st.vals[c] for d in digits_of(st.cand[c] & ~res["sup"][i])
    }
    ok = set(ctx.elims) <= computed
    kind = rule.line_kind or rule.kind
    emp = [c for c in rule.cells if not st.vals[c]]
    known = [(c, st.vals[c]) for c in rule.cells if st.vals[c]]
    tg = sorted({c for c, _ in ctx.elims})
    lines = [(kind, rule.cells)]
    J = _J(ctx, digits=_elim_digits(ctx), constraints=[_con_json(rule)], base_cells=emp, cover_cells=tg)
    if ctx.tech == S.LINE_RANGE or (rule.kind == "line"):
        why = _line_reasons(ctx, rule, res)
        short = f"{fmt_elims(nm, ctx.elims)}: {LINE_NAMES.get(kind, kind)} logic"
        if kind == "whisper" and all(d == (p.D + 1) // 2 for _, d in ctx.elims) and p.D % 2:
            short = f"{fmt_elims(nm, ctx.elims)}: German whispers -- {(p.D + 1) // 2} can never appear"
        elif kind in ("thermo", "slow_thermo") and any(c == rule.cells[0] for c, _ in ctx.elims):
            short = f"{fmt_elims(nm, ctx.elims)}: thermo bulb logic"
        elif kind in ("thermo", "slow_thermo"):
            short = f"{fmt_elims(nm, ctx.elims)}: thermo counting"
        teach = f"Read {rule.label}. {why} " + _line_tip(kind)
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind in ("cage", "sum", "little_killer") and len(emp) == 1:
        total = rule.total - sum(d for _, d in known)
        c = emp[0]
        short = f"{fmt_elims(nm, ctx.elims)}: {rule.label.split(' (')[0]} needs exactly {total} there"
        teach = (
            f"{_cap(rule.label)} already holds {nm.digits([d for _, d in known], 'and')}, so its last cell "
            f"{nm.cell(c)} must be {rule.total} - {sum(d for _, d in known)} = {total}. Every other "
            f"candidate in {nm.cell(c)} goes: {nm.digits(sorted(d for _, d in ctx.elims))}."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind in ("cage", "sum", "little_killer"):
        total = rule.total - sum(d for _, d in known)
        combos = _combo_sets(res, len(rule.cells))
        n = len(emp)
        head = f"{_cap(rule.label)} has {n} empty cell{'s' if n > 1 else ''} needing {total}" + (
            f" (after the {nm.digits([d for _, d in known], 'and')} already placed)" if known else ""
        )
        reasons = _sum_elim_reasons(ctx, rule, emp, res, total)
        short = f"{fmt_elims(nm, ctx.elims)}: killer combinations for {rule.label.split(' (')[0]}"
        teach = (
            f"{head}. With the notes available, {_combo_phrase(combos)}. {reasons} "
            f"Always list a cage's possible digit sets first -- small and large totals have very few."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind == "arrow":
        circ, line = rule.con["circle"], rule.con["line"]
        lo = sum(min(digits_of(dom[rule.cells.index(c)])) for c in line)
        hi = sum(max(digits_of(dom[rule.cells.index(c)])) for c in line)
        circ_txt = nm.cells(circ)
        short = f"{fmt_elims(nm, ctx.elims)}: arrow sum bounds"
        teach = (
            f"On {rule.label}, the circle {circ_txt} equals the sum along the arrow. With the current notes "
            f"the arrow can total anywhere from {lo} to {hi}, and the circle has to match. "
            f"{_generic_rule_reason(ctx, rule, res, emp)} Bound the arrow from both ends: the smallest and "
            f"largest possible arrow sums limit the circle, and vice versa."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind in ("set", "renban"):
        runs = sorted({(min(s), max(s)) for s in res["sols"]})
        rtxt = _join([f"{a}-{b}" for a, b in runs], "or")
        short = f"{fmt_elims(nm, ctx.elims)}: renban run"
        teach = (
            f"{_cap(rule.label)} needs {len(rule.cells)} consecutive digits in any order. With the candidates "
            f"available the run can only be {rtxt}, so remove {_elim_list(nm, ctx.elims)}. "
            f"On renbans, think about which runs fit before thinking about cells."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    short = f"{fmt_elims(nm, ctx.elims)}: {rule.label.split(' (')[0]}"
    teach = f"Check {rule.label} against the notes. {_generic_rule_reason(ctx, rule, res, emp)} {CONCEPTS[ctx.tech][1]}"
    return _result(ctx, J, short, teach, ok, lines=lines)


def _rest_sums(p, st, rule, emp, c, d):
    """Sums the other empty cells of a sum rule can make when c holds d."""
    rest = [q for q in emp if q != c]
    if not rest:
        return {0}
    dom = []
    for q in rest:
        m = st.cand[q]
        if rule.distinct or q in p.peers[c]:
            m &= ~bit(d)
        dom.append(m)
    sums = set()

    def rec(i, s, used):
        if len(sums) > 60:
            return
        if i == len(rest):
            sums.add(s)
            return
        for v in digits_of(dom[i]):
            if any(v == used[j] and (rule.distinct or rest[j] in p.peers[rest[i]]) for j in range(i)):
                continue
            used.append(v)
            rec(i + 1, s + v, used)
            used.pop()

    rec(0, 0, [])
    return sums


def _sum_elim_reasons(ctx, rule, emp, res, total):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    anywhere = 0
    for i, c in enumerate(rule.cells):
        if not st.vals[c]:
            anywhere |= res["sup"][i]
    parts, never = [], []
    grouped = defaultdict(list)
    for c, d in ctx.elims:
        if res["complete"] and not anywhere & bit(d):
            never.append(d)
            continue
        need = total - d
        if len(emp) == 2:
            o = emp[0] if c == emp[1] else emp[1]
            if need == d and rule.distinct:
                parts.append(f"a {d} in {nm.cell(c)} would need a second {d} next to it")
            elif not 1 <= need <= p.D:
                parts.append(f"a {d} in {nm.cell(c)} would leave {need} for {nm.cell(o)}, which no digit can be")
            elif not st.cand[o] & bit(need):
                parts.append(
                    f"a {d} in {nm.cell(c)} would need a {need} in {nm.cell(o)}, which isn't among its "
                    f"notes {nm.cset(st.cand[o])}"
                )
            else:
                parts.append(
                    f"a {d} in {nm.cell(c)} would need a {need} in {nm.cell(o)}, which the rest of the grid forbids"
                )
            continue
        sums = _rest_sums(p, st, rule, emp, c, d)
        if sums and need > max(sums):
            grouped[(d, "max", need, max(sums))].append(c)
        elif sums and need < min(sums):
            grouped[(d, "min", need, min(sums))].append(c)
        else:
            grouped[(d, "gap", need, 0)].append(c)
    for (d, kind, need, bound), cs in grouped.items():
        where = nm.cells(cs, "or")
        if kind == "max":
            parts.append(f"a {d} in {where} leaves {need} for the other cells, but they can make at most {bound}")
        elif kind == "min":
            parts.append(f"a {d} in {where} leaves {need} for the other cells, but they add up to at least {bound}")
        else:
            parts.append(
                f"a {d} in {where} leaves {need} for the other cells, which their notes can't make with "
                f"{'different ' if rule.distinct else ''}digits"
            )
    txt = []
    if never:
        txt.append(f"no surviving combination uses {nm.digits(sorted(set(never)))} at all")
    txt += list(dict.fromkeys(parts))
    return _cap("; ".join(txt)) + "." if txt else ""


def _generic_rule_reason(ctx, rule, res, emp):
    nm = ctx.nm
    sols = res["sols"]
    if res["complete"] and 0 < len(sols) <= 4:
        fill = "; ".join(", ".join(f"{nm.cell(c)}={v}" for c, v in zip(rule.cells, s) if c in emp) for s in sols)
        return (
            f"Only {len(sols)} filling{'s' if len(sols) > 1 else ''} survive{'s' if len(sols) == 1 else ''} ({fill}), so "
            f"remove {_elim_list(nm, ctx.elims)}."
        )
    return f"Trying each candidate shows that no valid filling of the rule can use them: remove {_elim_list(nm, ctx.elims)}."


def _line_tip(kind):
    return {
        "thermo": "On a thermometer, count cells: a cell n steps from the bulb is at least n+1, and one with m cells "
        "above it is at most 9-m.",
        "slow_thermo": "On a slow thermometer digits never decrease, so neighbours bound each other.",
        "whisper": "On German whispers 5 is impossible and 4/6 are tight -- they need a 9 or a 1 next door.",
        "dutch_whisper": "On Dutch whispers neighbours differ by at least 4; 5 needs a 1 or 9 neighbour.",
        "renban": "On renbans, think about which runs fit before thinking about cells.",
        "palindrome": "A palindrome reads the same both ways: mirrored cells share their candidates.",
        "kropki_chain": "White dots need consecutive digits, black dots a 1:2 ratio -- chains of dots are very "
        "restrictive.",
        "between": "Cells on a between line lie strictly between the two circles' digits.",
        "entropic": "Every three consecutive cells on an entropic line hold one low, one middle and one high digit.",
        "modular": "Every three consecutive cells on a modular line hold one digit from each of {1,4,7}, {2,5,8}, "
        "{3,6,9}.",
        "parity": "Neighbours on a parity line alternate odd and even.",
        "region_sum": "Each box segment of a region-sum line has the same total.",
        "zipper": "Pairs equidistant from the zipper's centre add up to the same total.",
    }.get(kind, "")


def _line_reasons(ctx, rule, res):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    kind = rule.line_kind or rule.kind
    cells = rule.cells
    dom = _rule_dom(st, rule)
    parts = []
    generic = defaultdict(list)
    by_cell = defaultdict(list)
    for c, d in ctx.elims:
        by_cell[c].append(d)
    for c in nm.sort(by_cell) if kind not in ("thermo", "slow_thermo") else [x for x in cells if x in by_cell]:
        ds = sorted(by_cell[c])
        i = cells.index(c) if c in cells else -1
        txt = None
        if kind in ("thermo", "slow_thermo") and i >= 0:
            strict = kind == "thermo"
            lo_prev = min(digits_of(dom[i - 1])) if i > 0 else 0
            hi_next = max(digits_of(dom[i + 1])) if i + 1 < len(cells) else p.D + 1
            low = [d for d in ds if d < lo_prev + strict]
            high = [d for d in ds if d > hi_next - strict]
            seg = []
            if low:
                seg.append(
                    f"{nm.cell(cells[i - 1])} below it is at least {lo_prev}, so {nm.cell(c)} can't be {nm.digits(low)}"
                )
            if high:
                seg.append(
                    f"{nm.cell(cells[i + 1])} above it is at most {hi_next}, so {nm.cell(c)} can't be {nm.digits(high)}"
                )
            if i == 0 and not low and high and len(cells) > 1:
                pass
            if seg and len(low) + len(high) == len(ds):
                pos = f"{nm.cell(c)} is cell {i + 1} of {len(cells)} on the thermo: "
                txt = pos + "; ".join(seg)
        elif kind in ("whisper", "dutch_whisper") and i >= 0:
            k = rule.con.get("k", 5 if kind == "whisper" else 4)
            nbs = [cells[j] for j in (i - 1, i + 1) if 0 <= j < len(cells)]
            seg = []
            for d in ds:
                if all(abs(w - d) < k for w in range(1, p.D + 1)):
                    seg.append(f"{d} has no partner {k} or more away on a 1-{p.D} grid")
                    continue
                for q in nbs:
                    dq = dom[cells.index(q)]
                    if not any(abs(w - d) >= k for w in digits_of(dq)):
                        seg.append(
                            f"{d} would need a neighbour {k}+ away, but {nm.cell(q)} can only be "
                            f"{nm.digits(digits_of(dq))}"
                        )
                        break
                else:
                    if len(nbs) == 2 and nbs[1] in p.peers[nbs[0]]:
                        far = [w for w in range(1, p.D + 1) if abs(w - d) >= k]
                        if len(far) == 1:
                            seg.append(
                                f"{d} would force both neighbours {nm.cell(nbs[0])} and {nm.cell(nbs[1])} to "
                                f"be {far[0]}, but they see each other"
                            )
            if len(seg) == len(ds):
                txt = f"At {nm.cell(c)}: " + "; ".join(seg)
        elif kind == "palindrome" and i >= 0:
            j = len(cells) - 1 - i
            q = cells[j]
            if q != c:
                txt = (
                    f"{nm.cell(c)} mirrors {nm.cell(q)}, which can only be {nm.digits(digits_of(dom[j]))}, "
                    f"so {nm.cell(c)} can't be {nm.digits(ds)}"
                )
        elif kind == "kropki_chain" and i >= 0:
            nbs = [j for j in (i - 1, i + 1) if 0 <= j < len(cells)]
            for j in nbs:
                q = cells[j]
                bad = [d for d in ds if not any(not _rel_ex(p, c, q, d) & bit(w) for w in digits_of(dom[j]))]
                if len(bad) == len(ds):
                    txt = (
                        f"{nm.cell(c)} is dotted to {nm.cell(q)} ({rel_label(p, c, q)}), which can only be "
                        f"{nm.digits(digits_of(dom[j]))} -- none pairs with {nm.digits(ds)}"
                    )
                    break
        if txt is None:
            generic[tuple(ds)].append(c)
            continue
        parts.append(txt)
    for ds, cs in generic.items():
        parts.append(f"no valid filling of the line can put {nm.digits(ds)} in {nm.cells(cs)}")
    if rule.segs and kind in ("region_sum", "zipper", "equal_sum"):
        seg_txt = _segment_sums(nm, p, st, rule, dom)
        if seg_txt:
            parts.insert(0, seg_txt)
    if kind in ("renban",):
        runs = sorted({(min(s), max(s)) for s in res["sols"]})
        return f"The run can only be {_join([f'{a}-{b}' for a, b in runs], 'or')}; {'; '.join(parts)}."
    fills = ""
    if res["complete"] and 0 < len(res["sols"]) <= 3 and any(t.startswith("no valid") for t in parts):
        fills = (
            " The fillings that still work: "
            + "; ".join("-".join(str(v) for v in s) for s in res["sols"])
            + f" (reading {nm.span(cells)})."
        )
    return _cap("; ".join(parts)) + "." + fills


def _segment_sums(nm, p, st, rule, dom):
    """'each segment must total the same: r1c1 alone can make 3-5, r2c2+r2c3 can make 4-11 ...'."""
    pos = {c: i for i, c in enumerate(rule.cells)}
    seg_sums = []
    for seg in rule.segs:
        sums = set()

        def rec(i, tot, used):
            if len(sums) > 40:
                return
            if i == len(seg):
                sums.add(tot)
                return
            for v in digits_of(dom[pos[seg[i]]]):
                if any(u == v and seg[j] in p.peers[seg[i]] for j, u in enumerate(used)):
                    continue
                rec(i + 1, tot + v, used + [v])

        rec(0, 0, [])
        seg_sums.append(sums)
    if not all(seg_sums):
        return ""
    common = set.intersection(*seg_sums)
    if not common:
        return ""

    def rng(xs):
        xs = sorted(xs)
        runs, start = [], xs[0]
        for a, b in zip(xs, xs[1:] + [None]):
            if b != a + 1:
                runs.append(f"{start}" if start == a else f"{start}-{a}")
                start = b
        return ", ".join(runs)

    tight = sorted(range(len(rule.segs)), key=lambda i: len(seg_sums[i]))[:2]
    seg_desc = "; ".join(f"{nm.cells(rule.segs[i])} can only total {rng(seg_sums[i])}" for i in tight)
    return f"every segment must have the same total; {seg_desc} -- so the common total is {rng(common)}"


# ---------------------------------------------------------- combo lock ------
def _must_contain(p, st, rule, v):
    """Every valid filling of the rule (with the current notes) uses digit v."""
    if any(st.vals[c] == v for c in rule.cells):
        return True
    dom = [m if st.vals[c] else m for c, m in zip(rule.cells, _rule_dom(st, rule))]
    dom = [m if st.vals[c] else m & ~bit(v) for c, m in zip(rule.cells, dom)]
    if any(m == 0 for m in dom):
        return True
    res = enum_rule(p, rule, dom)
    return res["complete"] and not any(res["sup"])


class _ReqRule(Rule):
    def __init__(self, base, v, idx):
        super().__init__(
            base.kind,
            base.cells,
            base.label,
            base.index,
            base.group,
            base.con,
            base.total,
            base.segs,
            base.line_kind,
            base.distinct,
        )
        self.v, self.idx = v, idx

    def check(self, a):
        return any(a[i] == self.v for i in self.idx) and super().check(a)


def _required_elims(p, st, rule, v, poss, res=None):
    """Eliminations when the rule must place v in one of `poss`."""
    res = res or enum_rule(p, rule, _rule_dom(st, rule))
    rr = _ReqRule(rule, v, [rule.cells.index(c) for c in poss if c in rule.cells])
    r2 = enum_rule(p, rr, _rule_dom(st, rule))  # inexact support only over-keeps -> still sound
    return {
        (c, d)
        for i, c in enumerate(rule.cells)
        if not st.vals[c]
        for d in digits_of(st.cand[c] & res["sup"][i] & ~r2["sup"][i])
    }


def _innie_rule(nm, p, s):
    common = set.intersection(*(set(p.groups_of[c]) for c in s["cells"]))
    lab = (
        f"the {s['kind']} region of {_union_name(nm, s['union'])} ({nm.cells(s['cells'])}, "
        f"which must total {s['total']} by the rule of 45)"
    )
    r = Rule("innie", s["cells"], lab, total=s["total"], distinct=bool(common))
    r.union = s["union"]
    return r


def _lock_region(ctx, v, mode):
    """Must-contain lock on a solver-derived rule-of-45 region: find the region."""
    p, st, nm = ctx.p, ctx.st, ctx.nm
    gi = ctx.xm.get("group")
    tcells = {c for c, _ in ctx.elims}
    for s in _innie_sets(p, max_cells=9):
        cells = set(s["cells"])
        if mode == 0:
            if tcells & cells or gi is None or gi < 0:
                continue
            U = [c for c in s["cells"] if not st.vals[c] and st.cand[c] & bit(v)]
            if not U or not all(c in p.groups[gi].cells for c in U):
                continue
            span = set()
            for g in p.groups_of[U[0]]:
                if all(c in p.groups[g].cells for c in U):
                    span |= set(p.groups[g].cells)
            if not tcells <= span:
                continue
        else:
            hi = ctx.xm.get("group")
            if hi is None or hi < 0 or not tcells <= cells:
                continue
            poss = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(v)]
            if not poss or not set(poss) <= cells:
                continue
        rule = _innie_rule(nm, p, s)
        res = enum_rule(p, rule, _rule_dom(st, rule))
        if not res["complete"] or not res["count"]:
            continue
        if mode == 0 and not _must_contain(p, st, rule, v):
            continue
        if mode == 1 and not set(ctx.elims) <= _required_elims(p, st, rule, v, poss, res):
            continue
        return rule, res
    return None, None


def _h_combo_lock(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    rule = _rule_from_move(ctx)
    v = ctx.xm.get("digit") or (_elim_digits(ctx)[0] if ctx.elims else None)
    mode = ctx.xm.get("mode", 0)
    res = None
    if rule is None:
        rule, res = _lock_region(ctx, v, mode)
    if rule is None:
        return _generic(ctx)
    if res is None:
        res = enum_rule(p, rule, _rule_dom(st, rule))
    combos = _combo_sets(res, len(rule.cells))
    tg = sorted({c for c, _ in ctx.elims})
    lines = [(rule.line_kind or rule.kind, rule.cells)]
    union_units = list(getattr(rule, "union", ()))
    if mode == 0:
        U = [c for c in rule.cells if not st.vals[c] and st.cand[c] & bit(v)]
        own = rule.group
        gs = [g for g in (p.groups_of[U[0]] if U else ()) if g != own and all(c in p.groups[g].cells for c in U)]
        gs = [g for g in gs if any(c in p.groups[g].cells for c in tg)] or gs
        uniq = {}
        for g in sorted(gs, key=lambda g: (p.groups[g].kind == "cage", g)):
            uniq.setdefault(frozenset(p.groups[g].cells), g)
        gs = list(uniq.values())
        must = _must_contain(p, st, rule, v)
        ok = must and bool(gs) and all(any(c in p.groups[g].cells for g in gs) for c in tg)
        ctext = f" ({_combo_phrase(combos, sets=rule.kind not in _SUMLIKE)})" if combos and len(combos) <= 5 else ""
        gn = _join([nm.unit(g) for g in gs])
        short = f"{fmt_elims(nm, ctx.elims)}: {rule.label.split(' (')[0]} must contain a {v}"
        if rule.line_kind == "renban":
            short = f"{fmt_elims(nm, ctx.elims)}: renban -- the line {nm.span(rule.cells)} must contain a {v}"
        what = (
            "cage"
            if rule.kind == "cage"
            else "region"
            if rule.kind == "innie"
            else "line"
            if rule.line_kind
            else "rule"
        )
        teach = (
            f"Every way to fill {rule.label} uses a {v}{ctext}. Inside it, the {v} can only go in "
            f"{nm.cells(U, 'or')}, all in {gn} -- so that {v} is also {gn}'s {v}, and "
            f"{nm.cells(tg)} can't be {v}. Digits that every combination needs behave like pointing "
            f"candidates: find them by listing the {what}'s possible digit sets."
        )
        J = _J(
            ctx, digits=[v], constraints=[_con_json(rule)], base_cells=U, base_units=gs + union_units, cover_cells=tg
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    hi = ctx.xm.get("group")
    poss = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(v)] if hi is not None else []
    ok = (
        bool(poss)
        and all(c in rule.cells for c in poss)
        and set(ctx.elims) <= _required_elims(p, st, rule, v, poss, res)
    )
    with_v = [s for s in combos if s and v in s]
    short = f"{fmt_elims(nm, ctx.elims)}: {nm.unit(hi)} forces a {v} into {rule.label.split(' (')[0]}"
    teach = (
        f"{_cap(nm.unit(hi))} can only place its {v} in {nm.cells(poss, 'or')}, all inside {rule.label}. So "
        f"that rule must contain a {v}"
        + (f": {_combo_phrase(with_v, sets=rule.kind not in _SUMLIKE)}" if with_v and len(with_v) <= 5 else "")
        + f". Combinations without a {v} are out, which removes {_elim_list(nm, ctx.elims)}."
    )
    J = _J(
        ctx,
        digits=[v],
        constraints=[_con_json(rule)],
        base_cells=poss,
        base_units=([hi] if hi is not None else []) + union_units,
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, ok, lines=lines)


# ---------------------------------------------------------- leftovers -------
def _lol_candidates(p):
    if getattr(p, "_xlol", None) is not None:
        return p._xlol
    out = []
    seen = set()
    for orient in ("row", "col"):
        lines = [gi for gi in p.houses if p.groups[gi].kind == orient and len(p.groups[gi].cells) == p.D]
        lines.sort(key=lambda gi: p.coords[p.groups[gi].cells[0]][0 if orient == "row" else 1])
        regs = [
            gi
            for gi in p.houses
            if p.groups[gi].kind not in ("row", "col", "implied") and len(p.groups[gi].cells) == p.D
        ]
        for k in range(1, min(4, len(lines)) + 1):
            for ls in combinations(lines, k):
                U = set().union(*(p.groups[g].cells for g in ls))
                touch = [r for r in regs if len(U & set(p.groups[r].cells)) >= p.D - 6]
                for ch in combinations(touch, k):
                    if any(set(p.groups[a].cells) & set(p.groups[b].cells) for a, b in combinations(ch, 2)):
                        continue
                    V = set().union(*(p.groups[g].cells for g in ch))
                    A, B = sorted(U - V), sorted(V - U)
                    if not A or len(A) > 6 or len(A) != len(B):
                        continue
                    key = (tuple(A), tuple(B))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"lines": ls, "regs": ch, "A": A, "B": B})
    p._xlol = out
    return out


def _sameset_elims(p, st, A, B):
    d = {c: (bit(st.vals[c]) if st.vals[c] else st.cand[c]) for c in A + B}
    orig = dict(d)
    for _ in range(8):
        ch = False
        for side, other in ((A, B), (B, A)):
            om = 0
            for c in other:
                om |= d[c]
            for c in side:
                if d[c] & ~om:
                    d[c] &= om
                    ch = True
        if not ch:
            break
    return {(c, v) for c in A + B if not st.vals[c] for v in digits_of(orig[c] & ~d[c])}


def _h_lol(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    if ctx.code in ("PHI", "Phistomefel variant"):
        pc = (ctx.raw_engine or {}).get("pattern_cells") or []
        ring = ctx.code == "PHI"
        what = (
            "the four 2x2 corner blocks hold exactly the same digits as the 16-cell ring around the centre box"
            if ring
            else "a Phistomefel-style set equality: rows and columns mirrored about the centre, minus "
            "the boxes they cover, leave two groups of cells with exactly the same digits"
        )
        teach = (
            f"Phistomefel{' ring' if ring else ' variant'}: {what} (count rows, columns and boxes: every digit "
            f"appears equally often on both sides). Among {nm.cells(pc)}, a digit that cannot appear on one "
            f"side cannot appear on the other. So {fmt_elims(nm, ctx.elims)}."
        )
        J = _J(ctx, digits=_elim_digits(ctx), base_cells=pc)
        return _result(
            ctx, J, f"{fmt_elims(nm, ctx.elims)}: Phistomefel{' ring' if ring else ' variant'}", teach, bool(pc)
        )
    tset = set(ctx.elims)
    best = None
    for s in _lol_candidates(p):
        cells = set(s["A"]) | set(s["B"])
        if not {c for c, _ in tset} <= cells:
            continue
        if tset <= _sameset_elims(p, st, s["A"], s["B"]):
            if best is None or len(s["lines"]) < len(best["lines"]):
                best = s
    if best is None:
        return _generic(ctx)
    A, B = best["A"], best["B"]
    ln = _union_name(nm, best["lines"])
    rg = _union_name(nm, best["regs"])
    parts = []
    by_d = defaultdict(list)
    for c, d in ctx.elims:
        by_d[d].append(c)
    for d, cs in sorted(by_d.items()):
        other = B if cs[0] in A else A
        parts.append(f"{d} can't appear among {nm.cells(other)}, so it can't be in {nm.cells(cs)} either")
    short = f"{fmt_elims(nm, ctx.elims)}: law of leftovers ({ln} vs {rg})"
    times = {1: "once", 2: "twice"}.get(len(best["lines"]), f"{len(best['lines'])} times")
    teach = (
        f"Compare {ln} with {rg}: both contain every digit {times}, and they share all cells except the leftovers -- "
        f"{nm.cells(A)} on one side and {nm.cells(B)} on the other. Removing the common cells from both, the "
        f"leftovers must hold exactly the same digits. {_cap('; '.join(parts))}. "
        f"Set equivalence is powerful in jigsaws and anywhere boxes stick out of a band of lines."
    )
    J = _J(
        ctx,
        digits=_elim_digits(ctx),
        base_units=list(best["lines"]),
        cover_units=list(best["regs"]),
        base_cells=A,
        cover_cells=B,
    )
    return _result(ctx, J, short, teach, True)


# ------------------------------------------------------------- chains -------
def _link_graph(p, st, allow_bivalue=True, allow_bilocal=True, digit=None, extra=True):
    """Strong links: bivalue cell, bilocal digit in a house, digit a rule must contain with two
    cells left, pair-relation forcing. -> (nodes, {node: [(node, source, unit)]})."""
    strong = defaultdict(list)
    nodes = [(c, d) for c in range(p.N) if not st.vals[c] for d in digits_of(st.cand[c]) if digit is None or d == digit]

    def add(x, y, src, unit):
        if x == y or any(n == y for n, _, _ in strong[x]):
            return
        strong[x].append((y, src, unit))
        strong[y].append((x, src, unit))

    if allow_bivalue and digit is None:
        for c in range(p.N):
            if not st.vals[c] and popcount(st.cand[c]) == 2:
                a, b = digits_of(st.cand[c])
                add((c, a), (c, b), "bivalue", None)
    if allow_bilocal:
        for hi in p.houses:
            for d in digits_of(p.full & ~st.placed_g(hi)):
                if digit is not None and d != digit:
                    continue
                cs = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(d)]
                if len(cs) == 2:
                    add((cs[0], d), (cs[1], d), "bilocal", hi)
    if extra and allow_bilocal:
        for key, rule in rules(p).items():
            if all(st.vals[c] for c in rule.cells):
                continue
            res = enum_rule(p, rule, _rule_dom(st, rule), node_limit=20000)
            if not res["complete"] or res["count"] is None or res["count"] > len(res["sols"]) or not res["sols"]:
                continue
            must = set(res["sols"][0])
            for sol in res["sols"][1:]:
                must &= set(sol)
            for d in must:
                if digit is not None and d != digit:
                    continue
                if any(st.vals[c] == d for c in rule.cells):
                    continue
                cs = [c for c in rule.cells if not st.vals[c] and st.cand[c] & bit(d)]
                if len(cs) == 2:
                    add((cs[0], d), (cs[1], d), "constraint", key)
    if extra and allow_bivalue and digit is None:
        for a in range(p.N):
            if st.vals[a]:
                continue
            for b in p.nonconsec_list[a]:
                if st.vals[b] or b not in p.rel_ex[a]:
                    continue
                for v in digits_of(st.cand[a]):
                    allowed = 0
                    for u in digits_of(st.cand[a] & ~bit(v)):
                        allowed |= st.cand[b] & ~p.rel_ex[a][b][u]
                    if popcount(allowed) == 1 and popcount(st.cand[a]) > 1:
                        add((a, v), (b, next(digits_of(allowed))), "relation", None)
    return nodes, strong


def _weak(p, st, a, b, same_digit_only=False):
    (c1, d1), (c2, d2) = a, b
    if a == b:
        return False
    if c1 == c2:
        return not same_digit_only
    if d1 == d2 and c2 in p.peers[c1]:
        return True
    if not same_digit_only and c2 in p.rel_ex[c1] and p.rel_ex[c1][c2][d1] & bit(d2):
        return True
    return False


def _weak_succ(p, st, n, digit_only=False, xy=False):
    c, d = n
    out = []
    if not digit_only and not xy:
        for e in digits_of(st.cand[c]):
            if e != d:
                out.append((c, e))
    if xy:
        pass
    for q in p.peer_list[c]:
        if not st.vals[q] and st.cand[q] & bit(d):
            out.append((q, d))
    if not digit_only:
        for q in p.nonconsec_list[c]:
            if st.vals[q]:
                continue
            for e in digits_of(st.cand[q] & p.rel_ex[c][q][d]):
                if (q, e) not in out:
                    out.append((q, e))
    return out


def _find_chain(p, st, target, kind, max_len=16, place=False, targets=None):
    """Shortest alternating chain (first and last links strong). Elimination: both ends weakly
    linked to every target. Placement (discontinuous nice loop): starts and ends at `target`.
    -> [(node, link source into node, unit)] or None."""
    from collections import deque

    targets = targets or [target]
    digit_only = kind == "x"
    xy = kind == "xy"
    graph = getattr(st, "_xgraph", {}).get(kind)
    if graph is None:
        graph = _link_graph(
            p,
            st,
            allow_bivalue=not digit_only,
            allow_bilocal=not xy,
            digit=target[1] if digit_only else None,
            extra=not xy,
        )
        if not digit_only:
            st.__dict__.setdefault("_xgraph", {})[kind] = graph
    nodes, strong = graph

    def weak_all(n):
        return all(t != n and _weak(p, st, n, t, same_digit_only=digit_only) for t in targets)

    starts = [target] if place else [n for n in nodes if weak_all(n)]
    best = None
    for s0 in starts:
        prev = {(s0, False): None}
        dq = deque([(s0, False, 0)])
        found = None
        while dq and found is None:
            n, was_strong, ln = dq.popleft()
            if ln >= max_len:
                continue
            if not was_strong:
                for m, src, unit in strong.get(n, ()):
                    if (m, True) in prev:
                        continue
                    prev[(m, True)] = (n, False, src, unit)
                    if place:
                        end_ok = m == target and ln + 1 >= 3
                    else:
                        end_ok = m != s0 and weak_all(m) and (not xy or m[1] == s0[1])
                    if end_ok:
                        found = (m, True)
                        break
                    dq.append((m, True, ln + 1))
            else:
                if xy:
                    succ = [
                        (q, n[1])
                        for q in p.peer_list[n[0]]
                        if not st.vals[q] and st.cand[q] & bit(n[1]) and popcount(st.cand[q]) == 2
                    ]
                else:
                    succ = _weak_succ(p, st, n, digit_only)
                for m in succ:
                    if (m, False) in prev or (m in targets and not place):
                        continue
                    prev[(m, False)] = (n, True, "weak", None)
                    dq.append((m, False, ln + 1))
        if found is None:
            continue
        path = []
        cur = found
        while prev[cur] is not None:
            pn, pstrong, psrc, punit = prev[cur]
            path.append((cur[0], psrc, punit))
            cur = (pn, pstrong)
        path.append((s0, None, None))
        path.reverse()
        if best is None or len(path) < len(best):
            best = path
        if len(best) <= 4:
            break
    return best


def _chain_text(nm, p, path, als_cells=None):
    """path: [(node, src_into, unit)] alternating, first link strong. ALS nodes: ('als', id, digit)."""
    out = []
    for i in range(1, len(path)):
        n0, n1 = path[i - 1][0], path[i][0]
        src, unit = path[i][1], path[i][2]
        strong = src != "weak" if src is not None else i % 2 == 1
        if src == "equal" and n0[0] != "als" and n1[0] != "als":
            out.append(f"so {nm.cell(n1[0])} is {n1[1]} as well ({rel_label(p, n0[0], n1[0]) or 'equal cells'})")
            continue
        if n0[0] == "als" or n1[0] == "als":
            cells = (als_cells or {}).get((n1 if n1[0] == "als" else n0)[1])
            nm_set = f"the almost locked set {nm.cells(cells)}" if cells else "an almost locked set"
            d1 = n1[-1]
            if n1[0] == "als" and not strong:
                out.append(f"which takes {d1} away from {nm_set}")
            elif n1[0] == "als":
                out.append(f"so {nm_set}, now one digit short, is locked and must contain a {d1}")
            elif strong:
                out.append(f"so {nm.cell(n1[0])} is {d1}")
            else:
                out.append(f"and every {n0[-1]} of that set sees {nm.cell(n1[0])}, so {nm.cell(n1[0])} isn't {d1}")
            continue
        (c0, d0), (c1, d1) = n0, n1
        if strong:
            if src == "bivalue":
                out.append(f"so {nm.cell(c1)} is {d1} (it only holds {d0} or {d1})")
            elif src == "bilocal":
                out.append(f"so {nm.cell(c1)} is {d1} (the only other {d1} in {nm.unit(unit)})")
            elif src == "constraint" and unit is not None:
                out.append(
                    f"so {nm.cell(c1)} is {d1} ({rules(p)[unit].label} must contain a {d1} and has only "
                    f"those two places for it)"
                )
            elif src == "relation":
                out.append(f"so {nm.cell(c1)} is {d1} (the {rel_label(p, c0, c1)} leaves it no other option)")
            elif src == "constraint" and unit is None:
                out.append(
                    f"so {nm.cell(c1)} is {d1} (a cage or line must contain a {d1} and has only those two "
                    f"places for it)"
                )
            else:
                out.append(f"so {nm.cell(c1)} is {d1}")
        else:
            if c0 == c1:
                out.append(f"which means {nm.cell(c1)} isn't {d1}")
            elif d0 == d1:
                out.append(f"which stops {nm.cell(c1)} being {d1}")
            else:
                out.append(f"which stops {nm.cell(c1)} being {d1} ({rel_label(p, c0, c1)})")
    return out


def _clash(nm, p, t, end):
    (c, d), (ec, ed) = t, end
    if c == ec:
        return f"it is itself the {ed} end" if d != ed else "it is an end"
    if d == ed:
        return f"it sees {nm.cell(ec)}"
    return f"{rel_label(p, ec, c)}-linked to {nm.cell(ec)}"


_PATTERN_NAMES = {p.engine_code: p.explain_name for p in R.patterns() if p.explain_name}  # data/patterns.csv


def _chain_links(path):
    return [
        {
            "a": path[i - 1][0],
            "b": path[i][0],
            "strong": path[i][1] != "weak",
            "source": path[i][1] or "strong",
            "unit": path[i][2],
        }
        for i in range(1, len(path))
    ]


def _chains_for(p, st, elims, kind):
    """Cover the eliminations with as few chains as possible. -> [(path, explained elims)]."""
    left = list(elims)
    out = []
    while left:
        path = None
        for kd in dict.fromkeys((kind, "aic")):
            path = _find_chain(p, st, left[0], kd, targets=left)
            if path:
                break
        if not path:
            for kd in dict.fromkeys((kind, "aic")):
                path = _find_chain(p, st, left[0], kd)
                if path:
                    break
        if not path:
            return out, left
        a, z = path[0][0], path[-1][0]
        done = [t for t in left if t not in (a, z) and _weak(p, st, a, t) and _weak(p, st, z, t)]
        if not done:
            return out, left
        out.append((path, done))
        left = [t for t in left if t not in done]
    return out, []


def _chain_conclusion(nm, p, path, done):
    (sc, sd), (ec, ed) = path[0][0], path[-1][0]
    tg = sorted({c for c, _ in done})
    ds = sorted({d for _, d in done})
    if sd == ed and ds == [sd]:
        return (
            f"{_subj(nm, tg)} {'sees' if len(tg) == 1 else 'see'} both ends, so "
            f"{'it' if len(tg) == 1 else 'they'} can't be {sd}."
        )
    return (
        "Each removed candidate clashes with both ends: "
        + "; ".join(
            f"{nm.cell(c)} can't be {d} ({_clash(nm, p, (c, d), (sc, sd))} and {_clash(nm, p, (c, d), (ec, ed))})"
            for c, d in done
        )
        + "."
    )


def _h_chain(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    kind = {S.X_CHAIN: "x", S.XY_CHAIN: "xy", S.EMPTY_RECT: "x", S.REMOTE_PAIRS: "xy"}.get(ctx.tech, "aic")
    if ctx.code in ("SKY", "2SK", "TUR", "XCH"):
        kind = "x"
    if ctx.code == "XYC":
        kind = "xy"
    pname = _PATTERN_NAMES.get(ctx.code or "", CONCEPTS[ctx.tech][0])
    alsc = {a.get("id"): a.get("cells") for a in ctx.engine.get("als") or ()}
    tip = (
        "Single-digit chains like this are found by following one digit's conjugate pairs."
        if kind == "x"
        else "Chains through two-candidate cells are easiest to find by following the bivalue cells."
        if kind == "xy"
        else "Build such chains from links you trust: two-candidate cells, digits with two spots in a house, "
        "and digits a cage or line must contain."
    )
    if ctx.place:
        path = _engine_path(ctx)
        for kd in [] if path else dict.fromkeys((kind, "aic")):
            path = _find_chain(p, st, ctx.place, kd, place=True)
            if path:
                break
        if not path:
            return _generic(ctx)
        c, v = ctx.place
        links = _chain_links(path)
        pname = "Discontinuous nice loop"
        tip = SHAPE_NOTES["nice_loop"] + " " + tip
        short = f"{nm.cell(c)} = {v}: {pname} -- assuming it isn't {v} forces it to be {v}"
        teach = (
            f"Suppose {nm.cell(c)} is NOT {v}: {', '.join(_chain_text(nm, p, path, alsc))}. The chain comes back and "
            f"demands that {nm.cell(c)} is {v} after all -- a contradiction, so {nm.cell(c)} is {v}. {tip}"
        )
        J = _J(
            ctx,
            digits=sorted({n[0][-1] for n in path}),
            links=links,
            base_cells=[n[0][0] for n in path if isinstance(n[0][0], int)],
            pattern="Discontinuous nice loop",
            pattern_type="strong-strong at the start: placement",
        )
        r = _result(
            ctx,
            J,
            short,
            teach,
            path[0][0] == ctx.place and path[-1][0] == ctx.place,
            chain=_chain_vis(nm, links),
            lines=_chain_lines(p, path),
        )
        r["pattern_key"] = "nice_loop"
        return r
    epath = None
    for trim in (True, False):
        cand_path = _engine_path(ctx, trim=trim)
        if cand_path and all(_ends_cover(p, st, cand_path, t) for t in ctx.elims):
            epath = cand_path
            break
    if epath:
        chains, left = [(epath, list(ctx.elims))], []
    else:
        chains, left = _chains_for(p, st, ctx.elims, kind)
    if not chains or not chains[0][1]:
        return _generic(ctx)
    links, cells, blocks, lines = [], [], [], []
    for k, (path, done) in enumerate(chains):
        (sc, sd), (ec, ed) = path[0][0], path[-1][0]
        both = f"{nm.cell(sc)} is {sd} or {nm.cell(ec)} is {ed}"
        lead = "Start from the idea that" if k == 0 else "A second chain does the rest: suppose"
        blocks.append(
            f"{lead} {nm.cell(sc)} is NOT {sd}: {', '.join(_chain_text(nm, p, path, alsc))}. So at least one "
            f"end is true: {both}. {_chain_conclusion(nm, p, path, done)}"
        )
        links += _chain_links(path)
        cells += [n[0][0] for n in path]
        lines += _chain_lines(p, path)
    (sc, sd), (ec, ed) = chains[0][0][0][0], chains[0][0][-1][0]
    key = chain_shape(p, st, chains[0][0])
    if key in ("aic", "x_chain", "xy_chain") and ctx.code in _CODE_KEY:
        key = _CODE_KEY[ctx.code] if _CODE_KEY[ctx.code] not in ("aic",) else key
    ptype = None
    if key in ("aic", "als_chain"):
        same_cell = any(t[0] in (sc, ec) for t in ctx.elims)
        ptype = (
            "type 2: the ends are different digits and the target shares a cell with one end"
            if same_cell or sd != ed
            else "type 1: both ends are the same digit"
        )
    pname = CATALOG[key][0] if key in CATALOG else pname
    note = SHAPE_NOTES.get(key, "")
    short = f"{fmt_elims(nm, ctx.elims)}: {pname} -- either {nm.cell(sc)} is {sd} or {nm.cell(ec)} is {ed}"
    teach = (
        " ".join(blocks)
        + (f" (Not shown: {fmt_elims(nm, left)}.)" if left else "")
        + " "
        + (note + " " if note else "")
        + tip
    )
    J = _J(
        ctx,
        digits=sorted({d for lk in links for d in (lk["a"][-1], lk["b"][-1])}),
        links=links,
        base_cells=[c for c in cells if isinstance(c, int)] + [c for a in alsc.values() for c in (a or ())],
        cover_cells=sorted({c for c, _ in ctx.elims}),
        als=[{"cells": list(v), "id": k} for k, v in alsc.items() if v],
    )
    J["pattern"], J["pattern_type"] = pname, ptype
    ok = not left and all(_path_valid(p, st, pth) for pth, _ in chains)
    r = _result(ctx, J, short, teach, ok, chain=_chain_vis(nm, links), lines=lines)
    r["pattern_key"] = key
    return r


_CODE_KEY = {p.engine_code: p.catalog_key for p in R.patterns() if p.catalog_key}  # engine code -> CATALOG key


_SRC = (
    ("bivalue", "bivalue"),
    ("only two places", "bilocal"),
    ("must contain", "constraint"),
    ("pair relation", "relation"),
    ("almost locked", "als"),
    ("equivalence", "equal"),
)


def _engine_path(ctx, trim=True):
    """Chain nodes from the engine -> [(node, link source, unit)]; ALS nodes are ('als', id, digit)."""
    nodes = ctx.engine.get("chain") or []
    if len(nodes) < 2:
        return None
    path = []
    for i, n in enumerate(nodes):
        node = (n["cell"], n["digit"]) if n.get("cell") is not None else ("als", n.get("als"), n["digit"])
        if i == 0:
            path.append((node, None, None))
            continue
        li = n.get("link_in", "")
        src = "weak" if li.startswith("weak") else next((v for k, v in _SRC if k in li), "strong")
        unit = ctx.nm.gidx.get(n.get("via")) if src == "bilocal" else None
        path.append((node, src, unit))
    # an AIC starts and ends with strong links: drop dangling weak ends (the target side of the record)
    while trim and len(path) > 2 and path[1][1] == "weak":
        path = [(path[1][0], None, None)] + path[2:]
    while trim and len(path) > 2 and path[-1][1] == "weak":
        path = path[:-1]
    if len(path) < 2 or path[0][0][0] == "als" or path[-1][0][0] == "als":
        return None
    ctx.used_engine = True
    return path


def _path_valid(p, st, path):
    """Every cell-to-cell link of a chain holds in the grid (ALS / rule links are taken on trust)."""
    for i in range(1, len(path)):
        a, b = path[i - 1][0], path[i][0]
        src = path[i][1]
        if a[0] == "als" or b[0] == "als" or src == "equal":
            continue
        if src == "weak":
            if not _weak(p, st, a, b):
                return False
        elif src == "bivalue":
            if a[0] != b[0] or st.cand[a[0]] != bit(a[1]) | bit(b[1]):
                return False
        elif src == "bilocal":
            if a[1] != b[1] or not any(
                a[0] in p.groups[h].cells
                and b[0] in p.groups[h].cells
                and [c for c in p.groups[h].cells if not st.vals[c] and st.cand[c] & bit(a[1])] == sorted((a[0], b[0]))
                for h in p.houses
            ):
                return False
    return True


def _ends_cover(p, st, path, t):
    a, z = path[0][0], path[-1][0]
    if a[0] == "als" or z[0] == "als":
        return True
    return t not in (a, z) and _weak(p, st, a, t) and _weak(p, st, z, t)


def _als_cells(ctx, als_id):
    for a in ctx.engine.get("als") or ():
        if a.get("id") == als_id:
            return a.get("cells")
    return None


def _chain_vis(nm, links):
    def nd(n):
        return nm.cell(n[0]) if isinstance(n[0], int) else f"ALS#{n[1]}"

    return [[nd(l["a"]), l["a"][-1], nd(l["b"]), l["b"][-1], "strong" if l["strong"] else "weak"] for l in links]


def _chain_lines(p, path):
    out = []
    for node, src, unit in path:
        if src == "constraint" and unit is not None:
            r = rules(p)[unit]
            out.append((r.line_kind or r.kind, r.cells))
    return out


# --------------------------------------------------------- uniqueness -------
def _rects(p):
    if getattr(p, "_xrects", None) is not None:
        return p._xrects
    out = []
    rows = [gi for gi in p.houses if p.groups[gi].kind == "row"]
    cols = [gi for gi in p.houses if p.groups[gi].kind == "col"]
    cell_at = {xy: i for i, xy in enumerate(p.coords)}
    boxes_of = {c: {gi for gi in p.groups_of[c] if p.groups[gi].kind in ("box", "region")} for c in range(p.N)}
    rr = sorted({p.coords[p.groups[g].cells[0]][0] for g in rows})
    cc = sorted({p.coords[p.groups[g].cells[0]][1] for g in cols})
    for r1, r2 in combinations(rr, 2):
        for c1, c2 in combinations(cc, 2):
            cs = [cell_at.get((r1, c1)), cell_at.get((r1, c2)), cell_at.get((r2, c1)), cell_at.get((r2, c2))]
            if None in cs:
                continue
            bx = set().union(*(boxes_of[c] for c in cs))
            if len(bx) == 2:
                out.append(cs)
    p._xrects = out
    return out


def _h_ur(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    x, y = ctx.xm.get("x"), ctx.xm.get("y")
    typ = ctx.xm.get("type") or 1
    tcells = {c for c, _ in ctx.elims}
    if ctx.code in ("AR1", "AR2"):
        pc = (ctx.raw_engine or {}).get("pattern_cells") or []
        if ctx.code == "AR1":
            short = f"{fmt_elims(nm, ctx.elims)}: avoidable rectangle {x}/{y}"
            teach = (
                f"{nm.cells(pc)} form a rectangle over two rows, two columns and two boxes; three corners were "
                f"solved (none is a given) as {x}/{y}. If the last corner were {x}, the {x}s and {y}s could be "
                f"swapped -- two solutions, which a setter must have prevented with a clue. So it is not {x}."
            )
        else:
            short = f"{fmt_elims(nm, ctx.elims)}: avoidable rectangle type 2 ({x}/{y})"
            teach = (
                f"{nm.cells(pc)} form a rectangle over two rows, two columns and two boxes; two corners were "
                f"solved (not givens) as {x} and {y}, and the other two each hold the digit that would complete "
                f"an interchangeable {x}/{y} rectangle plus one common extra digit. One of them must take the "
                f"extra, so it leaves every cell seeing both: {fmt_elims(nm, ctx.elims)}."
            )
        teach += " Uniqueness techniques rely on the puzzle having exactly one solution."
        J = _J(ctx, digits=[x, y], base_cells=pc, cover_cells=sorted(tcells))
        return _result(ctx, J, short, teach, bool(pc))
    for cs in _rects(p):
        if any(st.vals[c] for c in cs):
            continue
        common = st.cand[cs[0]] & st.cand[cs[1]] & st.cand[cs[2]] & st.cand[cs[3]]
        pairs = [(x, y)] if x and y else [(a, b) for a, b in combinations(digits_of(common), 2)]
        for a, b in pairs:
            xy = bit(a) | bit(b)
            if common & xy != xy:
                continue
            floor = [c for c in cs if st.cand[c] == xy]
            roof = [c for c in cs if c not in floor]
            if typ == 1 and not (len(floor) == 3 and tcells <= set(roof)):
                continue
            if typ in (2, 3, 4) and len(floor) != 2:
                continue
            if typ == 4 and not tcells <= set(roof):
                continue
            if typ == 5 and not len(floor) >= 1:
                continue
            if typ == 1:
                t = roof[0]
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle {a}/{b}"
                teach = (
                    f"{nm.cells(floor)} all hold just {{{a},{b}}}, and with {nm.cell(t)} they form a rectangle "
                    f"over two rows, two columns and two boxes. If {nm.cell(t)} were also {a} or {b}, the "
                    f"{a}s and {b}s could be swapped and the puzzle would have two solutions. A proper puzzle "
                    f"has one, so {nm.cell(t)} must be one of its other candidates: remove {a} and {b}."
                )
            elif typ == 2:
                extra = (st.cand[roof[0]] | st.cand[roof[1]]) & ~xy
                z = next(digits_of(extra))
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 2 ({a}/{b}, extra {z})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}}; the other corners {nm.cells(roof)} are "
                    f"{{{a},{b},{z}}}. To avoid the deadly {a}/{b} rectangle one of those two must be {z}, so "
                    f"any cell seeing both of them -- {nm.cells(sorted(tcells))} -- can't be {z}."
                )
            elif typ == 3:
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 3 ({a}/{b})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}}. The roof {nm.cells(roof)} must use one of its "
                    f"extra candidates to avoid a two-solution rectangle, so together they act like a single "
                    f"cell of those extras -- which forms a naked subset with other cells of their house and "
                    f"clears {fmt_elims(nm, ctx.elims)}."
                )
            elif typ == 4:
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 4 ({a}/{b})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}}. In the roof {nm.cells(roof)} one of the two "
                    f"digits is forced (it has no other place in their shared house), so the roof can't also "
                    f"use the other one -- that would complete the deadly rectangle. Remove it: "
                    f"{fmt_elims(nm, ctx.elims)}."
                )
            else:
                short = f"{fmt_elims(nm, ctx.elims)}: hidden unique rectangle ({a}/{b})"
                teach = (
                    f"The cells {nm.cells(cs)} form a rectangle on {a}/{b} across two boxes. Strong links on "
                    f"the far corner mean that placing {fmt_elims(nm, ctx.elims).split(' ≠ ')[-1]} there "
                    f"would complete an interchangeable {a}/{b} pattern -- two solutions -- so it goes."
                )
            teach += " Uniqueness techniques rely on the puzzle having exactly one solution."
            J = _J(ctx, digits=[a, b], base_cells=cs, cover_cells=sorted(tcells))
            return _result(ctx, J, short, teach, True)
    return _generic(ctx)


def _h_bug(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    if ctx.code == "BUG+2" or not ctx.place:
        tri = [q for q in range(p.N) if not st.vals[q] and popcount(st.cand[q]) == 3]
        others = [q for q in range(p.N) if not st.vals[q] and q not in tri]
        ok = len(tri) == 2 and all(popcount(st.cand[q]) == 2 for q in others)
        a, b = (tri + [None, None])[:2]
        short = f"{fmt_elims(nm, ctx.elims)}: BUG+2"
        teach = (
            f"Every unsolved cell has exactly two candidates except {nm.cell(a)} and {nm.cell(b)}. If both lost "
            f"their extra digit (the one appearing three times in their houses) the grid would be a 'bivalue "
            f"universal grave' -- every digit twice per house -- which never has exactly one solution. So at "
            f"least one extra digit is true, and whatever both cases rule out goes: "
            f"{fmt_elims(nm, ctx.elims)}."
        )
        J = _J(ctx, digits=_elim_digits(ctx), base_cells=[q for q in (a, b) if q is not None])
        return _result(ctx, J, short, teach, ok)
    c, v = ctx.place
    others = [q for q in range(p.N) if not st.vals[q] and q != c]
    ok = popcount(st.cand[c]) == 3 and all(popcount(st.cand[q]) == 2 for q in others)
    short = f"{nm.cell(c)} = {v}: BUG+1"
    teach = (
        f"Every unsolved cell has exactly two candidates except {nm.cell(c)} {nm.cset(st.cand[c])}. If "
        f"{nm.cell(c)} lost its extra digit the grid would be a 'bivalue universal grave' -- every digit "
        f"twice per house -- which always allows two solutions. So {nm.cell(c)} takes the digit that appears "
        f"three times in its houses: {v}."
    )
    J = _J(ctx, digits=[v], base_cells=[c])
    return _result(ctx, J, short, teach, ok)


# ----------------------------------------------------------------- ALS ------
def _als_list(p, st, max_cells=4):
    out = []
    seen = set()
    for gi in range(len(p.groups)):
        g = p.groups[gi]
        if not (g.complete or g.kind == "cage"):
            continue
        emp = [c for c in g.cells if not st.vals[c]]
        for k in range(1, min(max_cells, len(emp)) + 1):
            for combo in combinations(emp, k):
                u = 0
                for c in combo:
                    u |= st.cand[c]
                if popcount(u) == k + 1 and combo not in seen:
                    seen.add(combo)
                    out.append((combo, u, gi))
    return out


def _engine_als(ctx):
    """Engine ALS records -> [(cells tuple, digit mask, house)]."""
    p, st = ctx.p, ctx.st
    out = []
    for a in ctx.engine.get("als") or ():
        cs = tuple(sorted(a.get("cells") or ()))
        if not cs:
            return None
        m = 0
        for c in cs:
            m |= st.cand[c]
        common = set.intersection(*(set(p.groups_of[c]) for c in cs))
        gi = min(common, key=lambda g: (not p.groups[g].complete, g)) if common else -1
        out.append((cs, m, gi))
    return out


def _h_als_xz(ctx):
    _nm, p, st = ctx.nm, ctx.p, ctx.st
    tset = set(ctx.elims)
    zs = _elim_digits(ctx)
    ea = _engine_als(ctx)
    rcc = ctx.engine.get("rcc") or []
    if ea and len(ea) == 2:
        A, Bs = ea
        if len(rcc) >= 2 or ctx.code == "AXZ2":
            r = _als_xz_double(ctx, [A, Bs], pair=(A, Bs))
            if r["verified"]:
                ctx.used_engine = True
                return r
        elif rcc:
            x = rcc[0]
            el = set()
            for z in zs:
                za = [c for c in A[0] + Bs[0] if st.cand[c] & bit(z)]
                el |= {
                    (q, z)
                    for q in range(p.N)
                    if not st.vals[q]
                    and st.cand[q] & bit(z)
                    and q not in A[0] + Bs[0]
                    and all(q in p.peers[c] for c in za)
                }
            if tset <= el and _rcc(p, st, A, Bs, x) and x not in zs:
                ctx.used_engine = True
                return _alsxz_render(ctx, A, Bs, x, zs)
    als = _als_list(p, st)
    for z in zs:
        zb = bit(z)
        t0 = next(t for t in ctx.elims if t[1] == z)
        cand_als = [
            a
            for a in als
            if a[1] & zb and all(t0[0] in p.peers[c] for c in a[0] if st.cand[c] & zb) and t0[0] not in a[0]
        ]
        for A, Bs in combinations(cand_als, 2):
            ca, cb = A[0], Bs[0]
            if set(ca) & set(cb):
                continue
            for x in digits_of(A[1] & Bs[1]):
                if x == z:
                    continue
                xa = [c for c in ca if st.cand[c] & bit(x)]
                xb = [c for c in cb if st.cand[c] & bit(x)]
                if not all(q in p.peers[c] for c in xa for q in xb):
                    continue
                za = [c for c in ca if st.cand[c] & zb] + [c for c in cb if st.cand[c] & zb]
                el = {
                    (q, z)
                    for q in range(p.N)
                    if not st.vals[q] and st.cand[q] & zb and q not in ca + cb and all(q in p.peers[c] for c in za)
                }
                if {t for t in tset if t[1] == z} <= el:
                    return _alsxz_render(ctx, A, Bs, x, z)
    return _als_xz_double(ctx, als)


def _alsxz_render(ctx, A, Bs, x, z):
    nm = ctx.nm
    ca, cb = A[0], Bs[0]
    zs = list(z) if isinstance(z, (list, tuple)) else [z]

    def desc(a):
        return f"{nm.cells(a[0])} (digits {nm.digits(digits_of(a[1]), 'and')} in {nm.unit(a[2])})"

    tg = sorted({c for c, _ in ctx.elims})
    zt = nm.digits(zs, "and")
    short = f"{fmt_elims(nm, ctx.elims)}: ALS-XZ, X={x}, Z={zt}"
    teach = (
        f"Two almost-locked sets: A = {desc(A)} and B = {desc(Bs)} -- each has one more digit than cells. "
        f"Their {x}s all see each other, so at most one set holds {x}; the set without {x} is locked onto its "
        f"other digits, which include {zt}. So "
        + ("a " + str(zs[0]) + " is" if len(zs) == 1 else "each of " + zt + " is")
        + f" in A or B, and {nm.cells(tg)}, seeing every copy of {'it' if len(zs) == 1 else 'them'} in both "
        f"sets, lose{'s' if len(tg) == 1 else ''} {fmt_elims(nm, ctx.elims).split(' ≠ ')[-1] if len(tg) == 1 else zt}."
    )
    J = _J(
        ctx,
        digits=[x] + zs,
        als=[
            {"cells": list(ca), "digits": list(digits_of(A[1]))},
            {"cells": list(cb), "digits": list(digits_of(Bs[1]))},
        ],
        rcc=[x],
        z=zs[0],
        base_cells=list(ca) + list(cb),
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, all(d in zs for _, d in ctx.elims))


def _als_xz_double(ctx, als, pair=None):
    """Doubly linked ALS-XZ: two restricted common digits lock both sets completely."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    tset = set(ctx.elims)
    c0, d0 = ctx.elims[0]

    def sees_all(q, cells, d):
        cs = [c for c in cells if st.cand[c] & bit(d)]
        return cs and q not in cells and all(q in p.peers[c] for c in cs)

    first = [pair[0]] if pair else [a for a in als if a[1] & bit(d0) and sees_all(c0, a[0], d0)]
    for A in first:
        for B in [pair[1]] if pair else als:
            if B is A or set(A[0]) & set(B[0]):
                continue
            rcc = [x for x in digits_of(A[1] & B[1]) if _rcc(p, st, A, B, x)]
            if len(rcc) < 2:
                continue
            x1, x2 = rcc[:2]
            el = set()
            for q in range(p.N):
                if st.vals[q] or q in A[0] or q in B[0]:
                    continue
                for x in (x1, x2):
                    if st.cand[q] & bit(x) and sees_all(q, A[0] + B[0], x):
                        el.add((q, x))
                for S_ in (A, B):
                    for d in digits_of(S_[1] & ~bit(x1) & ~bit(x2)):
                        if st.cand[q] & bit(d) and sees_all(q, S_[0], d):
                            el.add((q, d))
            if tset <= el:
                short = f"{fmt_elims(nm, ctx.elims)}: doubly linked ALS-XZ ({x1} and {x2})"
                teach = (
                    f"Two almost-locked sets, A = {_als_desc(nm, A)} and B = {_als_desc(nm, B)}, share two "
                    f"restricted digits: their {x1}s all see each other and so do their {x2}s. Each digit can "
                    f"be in at most one set, yet both sets need one of them to avoid running out of digits -- "
                    f"so one set takes {x1}, the other {x2}, and both become fully locked. Every remaining digit "
                    f"is pinned inside its set, which clears {_elim_list(nm, ctx.elims)} from cells that see "
                    f"all of that digit's spots."
                )
                J = _J(
                    ctx,
                    digits=[x1, x2],
                    rcc=[x1, x2],
                    als=[
                        {"cells": list(A[0]), "digits": list(digits_of(A[1]))},
                        {"cells": list(B[0]), "digits": list(digits_of(B[1]))},
                    ],
                    base_cells=list(A[0]) + list(B[0]),
                    cover_cells=sorted({c for c, _ in ctx.elims}),
                )
                return _result(ctx, J, short, teach, True)
    return _generic(ctx)


def _rcc(p, st, A, B, x):
    xa = [c for c in A[0] if st.cand[c] & bit(x)]
    xb = [c for c in B[0] if st.cand[c] & bit(x)]
    return xa and xb and all(q in p.peers[c] for c in xa for q in xb)


def _als_desc(nm, a):
    return f"{nm.cells(a[0])} (digits {nm.digits(digits_of(a[1]), 'and')})"


def _alsxy_render(ctx, A, B, C, x, y, z):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    zl = list(z) if isinstance(z, (list, tuple)) else [z]
    ok = True
    for zz in zl:
        zc = [c for c in A[0] + B[0] if st.cand[c] & bit(zz)]
        ok &= all(q in p.peers[c] for q, d in ctx.elims if d == zz for c in zc)
    if len(zl) > 1:
        z = nm.digits(zl, "and")
    tz = {t for t in ctx.elims if t[1] in zl}
    tg = sorted({c for c, _ in tz})
    short = f"{fmt_elims(nm, ctx.elims)}: ALS-XY-Wing (X={x}, Y={y}, Z={z})"
    teach = (
        f"Three almost-locked sets (one more digit than cells): A = {_als_desc(nm, A)}, B = {_als_desc(nm, B)} "
        f"and the hinge C = {_als_desc(nm, C)}. A and C can't both hold {x} (their {x}s see each other); B and "
        f"C can't both hold {y}. If neither A nor B contained {z}, both would lock up, putting {x} in A and {y} "
        f"in B -- and C would lose two digits it can't spare. So {z} is in A or B, and {nm.cells(tg)}, seeing "
        f"all those {z}s, can't be {z}."
    )
    J = _J(
        ctx,
        digits=[x, y, z],
        z=z,
        rcc=[x, y],
        als=[{"cells": list(a[0]), "digits": list(digits_of(a[1]))} for a in (A, B, C)],
        base_cells=list(A[0] + B[0] + C[0]),
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, ok and tz == set(ctx.elims))


def _h_als_xywing(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    zs = _elim_digits(ctx)
    ea = _engine_als(ctx)
    if ea and len(ea) == 3:
        zm = sum(bit(z) for z in zs)
        for C in ea:
            A, B = [a for a in ea if a is not C]
            for x in digits_of(A[1] & C[1] & ~zm):
                for y in digits_of(B[1] & C[1] & ~zm & ~bit(x)):
                    if _rcc(p, st, A, C, x) and _rcc(p, st, B, C, y):
                        ctx.used_engine = True
                        return _alsxy_render(ctx, A, B, C, x, y, zs if len(zs) > 1 else zs[0])
    als = _als_list(p, st)
    for z in zs:
        zb = bit(z)
        tz = {t for t in ctx.elims if t[1] == z}
        t0 = next(iter(tz))
        cand = [
            a
            for a in als
            if a[1] & zb and t0[0] not in a[0] and all(t0[0] in p.peers[c] for c in a[0] if st.cand[c] & zb)
        ]
        for A, B in combinations(cand, 2):
            if set(A[0]) & set(B[0]):
                continue
            zc = [c for c in A[0] + B[0] if st.cand[c] & zb]
            el = {
                (q, z)
                for q in range(p.N)
                if not st.vals[q] and st.cand[q] & zb and q not in A[0] + B[0] and all(q in p.peers[c] for c in zc)
            }
            if not tz <= el:
                continue
            for C in als:
                if set(C[0]) & (set(A[0]) | set(B[0])):
                    continue
                for x in digits_of(A[1] & C[1] & ~zb):
                    if not _rcc(p, st, A, C, x):
                        continue
                    for y in digits_of(B[1] & C[1] & ~zb & ~bit(x)):
                        if not _rcc(p, st, B, C, y):
                            continue
                        tg = sorted({c for c, _ in tz})
                        short = f"{fmt_elims(nm, ctx.elims)}: ALS-XY-Wing (X={x}, Y={y}, Z={z})"
                        teach = (
                            f"Three almost-locked sets (one more digit than cells): A = {_als_desc(nm, A)}, "
                            f"B = {_als_desc(nm, B)} and the hinge C = {_als_desc(nm, C)}. A and C can't both "
                            f"hold {x} (their {x}s see each other); B and C can't both hold {y}. If neither A "
                            f"nor B contained {z}, both would lock up, putting {x} in A and {y} in B -- and C "
                            f"would lose two digits it can't spare. So {z} is in A or B, and {nm.cells(tg)}, "
                            f"seeing all those {z}s, can't be {z}."
                        )
                        J = _J(
                            ctx,
                            digits=[x, y, z],
                            z=z,
                            rcc=[x, y],
                            als=[{"cells": list(a[0]), "digits": list(digits_of(a[1]))} for a in (A, B, C)],
                            base_cells=list(A[0] + B[0] + C[0]),
                            cover_cells=tg,
                        )
                        return _result(ctx, J, short, teach, tz == set(ctx.elims))
    return _generic(ctx)


def _h_death_blossom(ctx):
    _nm, p, st = ctx.nm, ctx.p, ctx.st
    zs = _elim_digits(ctx)
    ea = _engine_als(ctx)
    pc = ctx.engine.get("pattern_cells") or []
    if ea and pc and len(zs) == 1:
        inals = {c for a in ea for c in a[0]}
        stems = [c for c in pc if c not in inals and not st.vals[c]]
        if len(stems) == 1:
            stem, z = stems[0], zs[0]
            sds = [d for d in digits_of(st.cand[stem]) if d != z]
            petals = []
            for d in sds:
                pt = next(
                    (
                        a
                        for a in ea
                        if a[1] & bit(d)
                        and a not in petals
                        and all(stem in p.peers[c] for c in a[0] if st.cand[c] & bit(d))
                    ),
                    None,
                )
                petals.append(pt)
            if None not in petals:
                ctx.used_engine = True
                return _db_render(ctx, stem, sds, petals, z)
    als = _als_list(p, st)
    for z in zs:
        zb = bit(z)
        tz = {t for t in ctx.elims if t[1] == z}
        t0 = next(iter(tz))
        for stem in range(p.N):
            if st.vals[stem] or not 2 <= popcount(st.cand[stem]) <= 3 or stem == t0[0]:
                continue
            sds = [d for d in digits_of(st.cand[stem]) if d != z]
            if st.cand[stem] & zb and t0[0] not in p.peers[stem]:
                continue
            options = []
            for d in sds:
                opts = [
                    a
                    for a in als
                    if stem not in a[0]
                    and a[1] & bit(d)
                    and a[1] & zb
                    and all(stem in p.peers[c] for c in a[0] if st.cand[c] & bit(d))
                    and all(t0[0] in p.peers[c] for c in a[0] if st.cand[c] & zb)
                    and t0[0] not in a[0]
                ]
                options.append(opts[:40])
            if any(not o for o in options):
                continue

            def rec(i, chosen):
                if i == len(sds):
                    return list(chosen)
                for a in options[i]:
                    if any(set(a[0]) & set(b[0]) for b in chosen):
                        continue
                    r = rec(i + 1, chosen + [a])
                    if r:
                        return r
                return None

            petals = rec(0, [])
            if not petals:
                continue
            zc = [c for a in petals for c in a[0] if st.cand[c] & zb] + ([stem] if st.cand[stem] & zb else [])
            el = {
                (q, z)
                for q in range(p.N)
                if not st.vals[q]
                and st.cand[q] & zb
                and q != stem
                and all(q in p.peers[c] for c in zc)
                and all(q not in a[0] for a in petals)
            }
            if not tz <= el:
                continue
            return _db_render(ctx, stem, sds, petals, z)
    return _generic(ctx)


def _db_render(ctx, stem, sds, petals, z):
    nm, st = ctx.nm, ctx.st
    tz = {t for t in ctx.elims if t[1] == z}
    tg = sorted({c for c, _ in tz})
    pt = "; ".join(f"if it is {d}, petal {_als_desc(nm, a)} loses its {d} and is locked" for d, a in zip(sds, petals))
    short = f"{fmt_elims(nm, ctx.elims)}: death blossom on stem {nm.cell(stem)}"
    teach = (
        f"The stem {nm.cell(stem)} {nm.cset(st.cand[stem])} decides everything: {pt}. A locked petal must use "
        f"all its remaining digits, and every petal contains {z}"
        + (f" (or the stem itself is {z})" if st.cand[stem] & bit(z) else "")
        + f" -- so whatever the stem is, some {z} ends up in a cell that {nm.cells(tg)} "
        f"{'sees' if len(tg) == 1 else 'see'}. No {z} there."
    )
    J = _J(
        ctx,
        digits=sds + [z],
        z=z,
        base_cells=[stem] + [c for a in petals for c in a[0]],
        als=[{"cells": list(a[0]), "digits": list(digits_of(a[1]))} for a in petals],
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, tz == set(ctx.elims))


def _mental_chain_single(ctx, ps, path):
    """Engine elimination chain on the mental view, after which the target is a single."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    a, z = path[0][0], path[-1][0]
    gone = [
        (q, d)
        for q in range(p.N)
        if not st.vals[q]
        for d in digits_of(ps.cand[q])
        if (q, d) not in (a, z) and _weak(p, ps, a, (q, d)) and _weak(p, ps, z, (q, d))
    ]
    md2 = list(ps.cand)
    for q, d in gone:
        md2[q] &= ~bit(d)
    how = None
    if md2[c] == bit(v):
        how = f"{nm.cell(c)} is left with only {v}"
    else:
        for gi in p.groups_of[c]:
            if p.groups[gi].complete and all(
                not md2[q] & bit(v) for q in p.groups[gi].cells if q != c and not st.vals[q]
            ):
                how = f"{nm.cell(c)} is the only place left for {v} in {nm.unit(gi)}"
                break
    if not how:
        return None
    rel = [t for t in gone if t[0] == c or t[1] == v]
    alsc = {x.get("id"): x.get("cells") for x in ctx.engine.get("als") or ()}
    links = _chain_links(path)
    short = f"{nm.cell(c)} = {v}: a short chain in the head clears the way"
    teach = (
        f"Without pencil marks, think about what the cells can still be. Suppose {nm.cell(a[0])} is NOT {a[1]}: "
        f"{', '.join(_chain_text(nm, p, path, alsc))}. So "
        + (
            f"{nm.cell(a[0])} must be {a[1]} or {z[1]}"
            if a[0] == z[0]
            else f"{nm.cell(a[0])} is {a[1]} or {nm.cell(z[0])} is {z[1]}"
        )
        + f", and anything clashing with both is impossible -- in particular "
        f"{fmt_elims(nm, rel[:6]) if rel else 'the candidates in the way'}. Now {how}."
    )
    J = _J(ctx, digits=[v], links=links, base_cells=[n[0][0] for n in path if isinstance(n[0][0], int)])
    return _result(
        ctx,
        J,
        short,
        teach,
        bool(rel) and _path_valid(p, ps, path),
        chain=_chain_vis(nm, links),
        lines=_chain_lines(p, path),
        extra_cells=[t[0] for t in rel[:6]],
    )


def _h_mental_chain(ctx):
    """Short chain reasoned without notes (on the mental view), ending in a single."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    md, _ = mental_view(p, st, level=3)
    ps = st.copy()
    ps.cand = [0 if st.vals[q] else md[q] for q in range(p.N)]
    ep = _engine_path(ctx)
    if ep and ep[0][0] != (c, v):
        r = _mental_chain_single(ctx, ps, ep)
        if r:
            return r
    path = ep if ep and ep[0][0] == (c, v) else _find_chain(p, ps, (c, v), "aic", max_len=8, place=True)
    if path:
        steps = _chain_text(nm, p, path)
        links = [
            {
                "a": path[i - 1][0],
                "b": path[i][0],
                "strong": i % 2 == 1,
                "source": path[i][1] if i % 2 == 1 else "weak",
                "unit": path[i][2],
            }
            for i in range(1, len(path))
        ]
        short = f"{nm.cell(c)} = {v}: a short chain without notes -- if it weren't {v}, it would have to be {v}"
        teach = (
            f"No pencil marks needed, just a few 'if-then' steps on what each cell can still be. Suppose "
            f"{nm.cell(c)} is not {v}: {', '.join(steps)}. The chain comes back and forces {nm.cell(c)} to be "
            f"{v} after all, so it is {v}."
        )
        J = _J(ctx, digits=[v], links=links, base_cells=[n[0][0] for n in path])
        chain = [
            [nm.cell(l["a"][0]), l["a"][1], nm.cell(l["b"][0]), l["b"][1], "strong" if l["strong"] else "weak"]
            for l in links
        ]
        return _result(ctx, J, short, teach, True, chain=chain, lines=_chain_lines(p, path))
    others = [d for d in digits_of(md[c]) if d != v]
    found = []
    for d in others:
        pth = _find_chain(p, ps, (c, d), "aic", max_len=8)
        if not pth:
            break
        found.append((d, pth))
    if others and len(found) == len(others):
        parts, cells, links = [], [], []
        for d, pth in found:
            (sc, sd), (ec, ed) = pth[0][0], pth[-1][0]
            parts.append(
                f"{d} goes because either {nm.cell(sc)} is {sd} or {nm.cell(ec)} is {ed} "
                f"(if {nm.cell(sc)} isn't {sd}: {', '.join(_chain_text(nm, p, pth))}), and both clash with it"
            )
            cells += [n[0][0] for n in pth]
            links += [
                {
                    "a": pth[i - 1][0],
                    "b": pth[i][0],
                    "strong": i % 2 == 1,
                    "source": pth[i][1] if i % 2 else "weak",
                    "unit": pth[i][2],
                }
                for i in range(1, len(pth))
            ]
        short = f"{nm.cell(c)} = {v}: a short chain rules out its other options"
        teach = (
            f"Reason without notes about what {nm.cell(c)} can be: {nm.digits(digits_of(md[c]))}. "
            f"{_cap('; '.join(parts))}. That leaves {v}."
        )
        J = _J(ctx, digits=[v], links=links, base_cells=cells)
        return _result(ctx, J, short, teach, True, lines=[ln for _, pth in found for ln in _chain_lines(p, pth)])
    return _generic(ctx)


# ---------------------------------------------------------------- trial ------
_ENUM_CACHE = {}


def _propagate(p, st, c0, v0, max_rounds=8, use_rules=True, out=None):
    """Assume c0 = v0 and follow forced placements with dependency tracking.
    -> (events, contradiction) ; events: list of dicts {cell, digit, why, deps}."""
    vals, cand = list(st.vals), list(st.cand)
    removed_by = {}  # (cell, digit) -> event index that removed it
    events = []
    R = list(rules(p).values()) if use_rules else []
    if out is not None:
        out.update(vals=vals, cand=cand, removed_by=removed_by)
    seen_dom = {}

    def place(c, v, why, deps):
        events.append({"cell": c, "digit": v, "why": why, "deps": deps})
        e = len(events) - 1
        vals[c] = v
        cand[c] = 0
        for q in p.peer_list[c]:
            if cand[q] & bit(v):
                cand[q] &= ~bit(v)
                removed_by[(q, v)] = e
        for q in p.nonconsec_list[c]:
            nb = p.rel_ex[c][q][v]
            for d in digits_of(cand[q] & nb):
                removed_by[(q, d)] = e
            cand[q] &= ~nb
        return e

    place(c0, v0, "assume", [])
    for rnd in range(max_rounds):
        prog = False
        for x in range(p.N):
            if vals[x]:
                continue
            if not cand[x]:
                deps = sorted({removed_by.get((x, d)) for d in digits_of(st.cand[x]) if (x, d) in removed_by})
                return events, {"kind": "empty", "cell": x, "deps": deps}
            if popcount(cand[x]) == 1:
                v = next(digits_of(cand[x]))
                deps = sorted({removed_by[(x, d)] for d in digits_of(st.cand[x]) if d != v and (x, d) in removed_by})
                place(x, v, ("naked", None), deps)
                prog = True
        for hi in p.houses:
            have = 0
            for q in p.groups[hi].cells:
                if vals[q]:
                    have |= bit(vals[q])
            for d in digits_of(p.full & ~have):
                poss = [q for q in p.groups[hi].cells if not vals[q] and cand[q] & bit(d)]
                orig = [q for q in p.groups[hi].cells if not st.vals[q] and st.cand[q] & bit(d)]
                if not poss:
                    deps = sorted({removed_by[(q, d)] for q in orig if (q, d) in removed_by})
                    return events, {"kind": "house", "house": hi, "digit": d, "deps": deps}
                if len(poss) == 1:
                    deps = sorted({removed_by[(q, d)] for q in orig if q != poss[0] and (q, d) in removed_by})
                    place(poss[0], d, ("hidden", hi), deps)
                    prog = True
        for x in range(p.N):
            if vals[x]:
                continue
            for q in p.nonconsec_list[x]:
                dq = bit(vals[q]) if vals[q] else cand[q]
                allowed = 0
                for w in digits_of(dq):
                    allowed |= p.full & ~p.rel_ex[q][x][w]
                lost = cand[x] & ~allowed
                if lost:
                    e = len(events)
                    events.append(
                        {
                            "cell": x,
                            "digit": None,
                            "removed": list(digits_of(lost)),
                            "why": ("arc", q),
                            "deps": [removed_by.get((q, d)) for d in digits_of(st.cand[q]) if (q, d) in removed_by]
                            + ([i for i, ev in enumerate(events[:-1]) if ev["cell"] == q and ev.get("digit")]),
                        }
                    )
                    for d in digits_of(lost):
                        removed_by[(x, d)] = e
                    cand[x] &= allowed
                    prog = True
        for rule in R:
            dom = [bit(vals[c]) if vals[c] else cand[c] for c in rule.cells]
            key = id(rule)
            if seen_dom.get(key) == dom:
                continue
            seen_dom[key] = dom
            if all(vals[c] for c in rule.cells) and rule.check([vals[c] for c in rule.cells]):
                continue
            if any(d == 0 for d in dom):
                continue
            ck = (id(p), key, tuple(dom))
            res = _ENUM_CACHE.get(ck)
            if res is None:
                if len(_ENUM_CACHE) > 50000:
                    _ENUM_CACHE.clear()
                res = _ENUM_CACHE[ck] = enum_rule(p, rule, dom, node_limit=20000)
            if not res["complete"]:
                continue
            deps = sorted({i for i, ev in enumerate(events) if ev["cell"] in rule.cells and ev.get("digit")})
            if res["count"] == 0:
                return events, {"kind": "rule", "rule": rule, "deps": deps}
            for i, c in enumerate(rule.cells):
                if vals[c]:
                    continue
                lost = cand[c] & ~res["sup"][i]
                if lost:
                    e = len(events)
                    events.append(
                        {
                            "cell": c,
                            "digit": None,
                            "removed": list(digits_of(lost)),
                            "why": ("rule", rule),
                            "deps": deps,
                        }
                    )
                    for d in digits_of(lost):
                        removed_by[(c, d)] = e
                    cand[c] &= res["sup"][i]
                    prog = True
        if not prog:
            break
    return events, None


def _trial_story(nm, p, events, contra):
    parts, need_cells, used_rules = _dep_story(nm, p, events, contra["deps"])
    if contra["kind"] == "empty":
        end = f"{nm.cell(contra['cell'])} has no candidate left"
    elif contra["kind"] == "house":
        end = f"{nm.unit(contra['house'])} has nowhere left for a {contra['digit']}"
    else:
        end = f"{contra['rule'].label} can't be completed"
        used_rules.append(contra["rule"])
    return parts, end, need_cells, used_rules


def _dep_story(nm, p, events, deps):
    """Only the forced steps the conclusion depends on, in order. -> (phrases, cells, rules)."""
    need = set()
    stack = list(deps)
    while stack:
        e = stack.pop()
        if e is None or e in need:
            continue
        need.add(e)
        stack.extend(x for x in events[e]["deps"] if x is not None)
    need.add(0)
    order = sorted(need)
    parts = []
    used_rules = [
        events[e]["why"][1] for e in order[1:] if isinstance(events[e]["why"], tuple) and events[e]["why"][0] == "rule"
    ]
    for e in order[1:]:
        ev = events[e]
        c = ev["cell"]
        kind = ev["why"][0] if isinstance(ev["why"], tuple) else ev["why"]
        if ev.get("digit"):
            if kind == "naked":
                parts.append(f"{nm.cell(c)} is left with only {ev['digit']}")
            elif kind == "hidden":
                parts.append(f"{nm.cell(c)} becomes the only spot for {ev['digit']} in {nm.unit(ev['why'][1])}")
        else:
            if kind == "arc":
                parts.append(f"{nm.cell(c)} loses {nm.digits(ev['removed'], 'and')} ({rel_label(p, ev['why'][1], c)})")
            elif kind == "rule":
                parts.append(f"{ev['why'][1].label} can no longer have {nm.digits(ev['removed'])} in {nm.cell(c)}")
    return parts, [events[e]["cell"] for e in order], used_rules


def _h_trial(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.elims[0]
    events, contra = _propagate(p, st, c, v, max_rounds=12 if ctx.tech == S.TRIAL else 6)
    if contra is None:
        events, contra = _propagate(p, st, c, v, max_rounds=40)
    other = [d for d in digits_of(st.cand[c]) if d != v]
    if contra is None:
        short = f"{fmt_elims(nm, ctx.elims)}: assuming {v} there leads to a contradiction"
        teach = (
            f"{nm.cell(c)} {nm.cset(st.cand[c])} has two candidates. If it were {v}, the forced consequences "
            f"eventually break a rule, so it isn't {v}. (The full chain is long; the solver found it by trial.)"
        )
        J = _J(ctx, digits=[v], base_cells=[c], trial={"assume": (c, v), "events": [], "contradiction": None})
        return _result(ctx, J, short, teach, False)
    parts, end, cells, used_rules = _trial_story(nm, p, events, contra)
    steps_txt = "; ".join(parts) if parts else "nothing else is needed"
    short = f"{fmt_elims(nm, ctx.elims)}: if it were {v}, {end}"
    teach = (
        f"{nm.cell(c)} has just two candidates, {nm.cset(st.cand[c])}. Assume it were {v}: {steps_txt}; "
        f"and then {end}. That's impossible, so {nm.cell(c)} isn't {v}"
        + (f" -- it must be {other[0]}" if len(other) == 1 else "")
        + ". "
        + (
            "A short forcing argument like this is how many solvers settle a bivalue cell: try one option and "
            "see whether it collapses within a few moves."
            if ctx.tech == S.SHORT_TRIAL
            else "This is trial-and-error territory: it is valid logic, but look for a pattern that explains the same "
            "contradiction before reaching for it."
        )
    )
    trial = {
        "assume": (c, v),
        "events": [
            {"cell": events[e]["cell"], "digit": events[e].get("digit"), "removed": events[e].get("removed")}
            for e in range(len(events))
        ][:60],
        "contradiction": {k: (vv.label if isinstance(vv, Rule) else vv) for k, vv in contra.items()},
    }
    J = _J(ctx, digits=[v], base_cells=cells, trial=trial)
    ex_cells = cells + ([contra["cell"]] if contra["kind"] == "empty" else [])
    J["base_units"] = [contra["house"]] if contra["kind"] == "house" else []
    lines = [(r.line_kind or r.kind, r.cells) for r in dict.fromkeys(used_rules)]
    return _result(ctx, J, short, teach, True, extra_cells=ex_cells, lines=lines)


def _either_choices(p, st):
    out = []
    for c in range(p.N):
        if not st.vals[c] and popcount(st.cand[c]) == 2:
            a, b = digits_of(st.cand[c])
            out.append(((c, a), (c, b), ("cell", c)))
    for hi in p.houses:
        for v in digits_of(p.full & ~st.placed_g(hi)):
            cs = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(v)]
            if len(cs) == 2:
                out.append(((cs[0], v), (cs[1], v), ("house", hi, v)))
    return out


def _branch_check(events, out, target, place):
    vals, cand, rb = out["vals"], out["cand"], out["removed_by"]
    x, d = target
    if place:
        if vals[x] != d:
            return None
        return [next(i for i, ev in enumerate(events) if ev["cell"] == x and ev.get("digit") == d)]
    if vals[x] == d or (not vals[x] and cand[x] & bit(d)):
        return None
    if vals[x]:
        return [next(i for i, ev in enumerate(events) if ev["cell"] == x and ev.get("digit"))]
    return [rb[(x, d)]] if (x, d) in rb else None


def _h_either_way(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    direct = bool(ctx.xm.get("no_notes")) or ctx.step.mode == "direct"
    ps = st
    if direct:
        md, _ = mental_view(p, st, level=3)
        ps = st.copy()
        ps.cand = [0 if st.vals[q] else md[q] for q in range(p.N)]
    targets = [ctx.place] if ctx.place else ctx.elims
    place = ctx.place is not None
    cache = {}
    choices = _either_choices(p, ps)
    pc = ctx.engine.get("pattern_cells") or []
    if len(pc) >= 2:
        pref = {pc[0], pc[1]}
        choices.sort(key=lambda ch: {ch[0][0], ch[1][0]} != pref)
    for use_rules, rounds in ((False, 4), (True, 4), (True, 6)):
        for A, B, why in choices:
            stories = []
            contra_units = []
            for opt in (A, B):
                key = (opt, use_rules, rounds)
                if key not in cache:
                    out = {}
                    ev, contra = _propagate(p, ps, opt[0], opt[1], max_rounds=rounds, use_rules=use_rules, out=out)
                    cache[key] = (ev, out, contra)
                ev, out, contra = cache[key]
                if contra is not None:  # this option breaks a rule: the other one must hold anyway
                    parts, end, cells_, rules_ = _trial_story(nm, p, ev, contra)
                    if contra["kind"] == "house":
                        contra_units.append(contra["house"])
                    elif contra["kind"] == "empty":
                        cells_ = cells_ + [contra["cell"]]
                    stories.append((parts + [f"then {end} -- impossible, so this option is out"], cells_, rules_))
                    continue
                deps = []
                for t in targets:
                    r = _branch_check(ev, out, t, place)
                    if r is None:
                        break
                    deps += r
                else:
                    stories.append(_dep_story(nm, p, ev, deps))
                    continue
                break
            if len(stories) != 2 or all(cache[(o, use_rules, rounds)][2] is not None for o in (A, B)):
                continue
            if why[0] == "cell":
                intro = f"{nm.cell(why[1])} can only be {A[1]} or {B[1]}"
            else:
                intro = f"the {why[2]} of {nm.unit(why[1])} must go in {nm.cell(A[0])} or {nm.cell(B[0])}"

            def branch(opt, story):
                direct_hit = "that alone settles it"
                steps = "; ".join(story[0]) if story[0] else direct_hit
                lead = f"if {nm.cell(opt[0])} is {opt[1]}"
                tail = "" if place else f" -- which removes {_elim_list(nm, ctx.elims)}"
                return f"{lead}: {steps}{tail}"

            if place:
                c, v = ctx.place
                short = f"{nm.cell(c)} = {v}: both options of a two-way choice lead here"
            else:
                short = f"{fmt_elims(nm, ctx.elims)}: both options of a two-way choice agree"
            teach = (
                f"Look at a simple either/or: {intro}. Follow both: {branch(A, stories[0])}. And "
                f"{branch(B, stories[1])}. Both roads lead to the same place, so "
                + (f"{nm.cell(ctx.place[0])} is {ctx.place[1]}" if place else _cant(nm, ctx.elims))
                + " -- no matter which option is true. 'Either way' reasoning is a gentle alternative to "
                "trial and error: you never need to know which branch is right."
            )
            cells = [A[0], B[0]] + stories[0][1] + stories[1][1]
            lines = [(r.line_kind or r.kind, r.cells) for r in dict.fromkeys(stories[0][2] + stories[1][2])]
            J = _J(
                ctx,
                digits=sorted({A[1], B[1]}),
                base_cells=cells,
                trial={"assume": [A, B], "events": [], "contradiction": None},
            )
            units = ([why[1]] if why[0] == "house" else []) + contra_units
            J["base_units"] = units
            return _result(ctx, J, short, teach, True, extra_cells=cells, lines=lines)
    return _generic(ctx)


def _line_classes(p, rule):
    """Digit classes of a line kind (as the engine's LineClass): -> (cls per digit, class names)."""
    kind = rule.line_kind
    D = p.D
    if kind in ("entropic", "modular"):
        if kind == "entropic":
            cls = {d: (d - 1) * 3 // D for d in range(1, D + 1)}
        else:
            cls = {d: (d - 1) % 3 for d in range(1, D + 1)}
    elif kind in ("parity", "kropki_chain"):
        cls = {d: d % 2 for d in range(1, D + 1)}
    elif kind in ("whisper", "dutch_whisper"):
        a, b = rule.cells[0], rule.cells[1]
        cls = {}
        for d in range(1, D + 1):
            ok = p.full & ~p.rel_ex[a][b][d] if b in p.rel_ex[a] else p.full
            up = any(w > d for w in digits_of(ok))
            dn = any(w < d for w in digits_of(ok))
            cls[d] = 0 if up and not dn else 1 if dn and not up else 2 if up and dn else 3
    else:
        return None, None
    names = {}
    for c in sorted(set(cls.values())):
        ds = [d for d in cls if cls[d] == c]
        if kind in ("whisper", "dutch_whisper"):
            label = ["low", "high", "middle", "impossible"][c]
        elif kind == "entropic":
            label = ["low", "middle", "high"][c]
        elif kind in ("parity", "kropki_chain"):
            label = ["even", "odd"][c]
        else:
            label = "{" + ",".join(map(str, ds)) + "}"
        names[c] = (
            f"{label} ({_join(ds, 'or') if len(ds) < 4 else f'{ds[0]}-{ds[-1]}'})" if kind != "modular" else label
        )
    return cls, names


def _h_line_class(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    rule = _rule_from_move(ctx)
    if rule is None or not rule.line_kind:
        return _generic(ctx)
    cls, names = _line_classes(p, rule)
    if cls is None:
        return _generic(ctx)
    cells = rule.cells
    n = len(cells)
    ncls = max(cls.values()) + 1
    cmask = [sum(bit(d) for d in cls if cls[d] == q) for q in range(ncls)]
    dom = [bit(st.vals[c]) if st.vals[c] else st.cand[c] for c in cells]
    cd = [sum(1 << q for q in range(ncls) if dom[i] & cmask[q]) for i in range(n)]
    cause = {}
    for _ in range(2 * n):
        changed = False
        for i in range(n):
            for j in range(n):
                a, b = cells[i], cells[j]
                if i == j or b not in p.rel_ex[a]:
                    continue
                keep = 0
                for qa in range(ncls):
                    if not cd[i] >> qa & 1:
                        continue
                    for qb in range(ncls):
                        if cd[j] >> qb & 1 and any(cmask[qb] & ~p.rel_ex[a][b][d] for d in digits_of(cmask[qa])):
                            keep |= 1 << qa
                            break
                if cd[i] & ~keep:
                    cd[i] &= keep
                    cause.setdefault(i, j)
                    changed = True
        if not changed:
            break
    comp = set()
    for i, c in enumerate(cells):
        if st.vals[c]:
            continue
        allowed = sum(cmask[q] for q in range(ncls) if cd[i] >> q & 1)
        comp |= {(c, d) for d in digits_of(st.cand[c] & ~allowed)}
    ok = set(ctx.elims) <= comp
    lname = LINE_NAMES.get(rule.line_kind, rule.line_kind)
    parts = []
    never = [q for q in range(ncls) if names.get(q, "").startswith("impossible")]
    by_cell = defaultdict(list)
    for c, d in ctx.elims:
        by_cell[c].append(d)
    for c in nm.sort(by_cell):
        i = cells.index(c)
        ds = by_cell[c]
        if never and all(cls[d] in never for d in ds):
            continue
        left = [names[q].split(" (")[0] for q in range(ncls) if cd[i] >> q & 1 and q in names]
        j = cause.get(i)
        why = ""
        if j is not None:
            jl = [names[q].split(" (")[0] for q in range(ncls) if cd[j] >> q & 1 and q in names]
            why = f" because {nm.cell(cells[j])} next to it can only be {_join(jl, 'or')}"
        parts.append(f"{nm.cell(c)} must be {_join(left, 'or')}{why}, so not {nm.digits(ds)}")
    nev_txt = ""
    if never:
        nd = [d for d in cls if cls[d] in never]
        nev_cells = [c for c, d in ctx.elims if cls[d] in never]
        if nev_cells:
            nev_txt = (
                f"{nm.digits(nd)} has no possible neighbour on a {lname}, so it can't appear anywhere on it "
                f"-- remove it from {nm.cells(nev_cells)}. "
            )
    classes = "; ".join(names[q] for q in sorted(names))
    short = f"{fmt_elims(nm, ctx.elims)}: {lname} classes"
    if never and all(cls[d] in never for _, d in ctx.elims):
        short = (
            f"{fmt_elims(nm, ctx.elims)}: {lname}s -- {nm.digits([d for d in cls if cls[d] in never])} can never appear"
        )
    elif rule.line_kind in ("whisper", "dutch_whisper"):
        short = f"{fmt_elims(nm, ctx.elims)}: {lname} high/low logic"
    teach = (
        f"Don't track exact digits on {rule.label} -- track classes: {classes}. "
        + nev_txt
        + (_cap("; ".join(parts)) + ". " if parts else "")
        + {
            "whisper": "Whispers alternate low and high, so one fixed cell decides the pattern along the line.",
            "dutch_whisper": "Dutch whispers alternate low and high too (5 only next to 1 or 9).",
            "entropic": "Any three cells in a row on an entropic line use one low, one middle and one high digit.",
            "modular": "Any three cells in a row on a modular line use one digit from each residue class.",
            "parity": "Parity lines alternate odd and even.",
            "kropki_chain": "Parity helps along dots: consecutive (white) pairs mix odd and even.",
        }.get(rule.line_kind, "")
    )
    J = _J(
        ctx,
        digits=_elim_digits(ctx),
        constraints=[_con_json(rule)],
        base_cells=list(cells),
        cover_cells=sorted(by_cell),
    )
    return _result(ctx, J, short, teach, ok, lines=[(rule.line_kind, cells)])


def _h_digit_count(ctx):
    """Positional set logic for one digit: k units that must contain v, k at-most-once covers."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    v = ctx.xm.get("digit") or (_elim_digits(ctx)[0] if ctx.elims else None)
    bu, cu = ctx.engine.get("base_units") or [], ctx.engine.get("cover_units") or []
    U = sorted(c for c in ctx.engine.get("pattern_cells") or () if isinstance(c, int))
    if not cu or not U or v is None:
        return _generic(ctx)
    ctx.used_engine = True
    CU = {c for g in cu for c in p.groups[g].cells}
    el = {(c, v) for c in CU if c not in U and not st.vals[c] and st.cand[c] & bit(v)}
    ok = set(ctx.elims) <= el and set(U) <= CU and len(cu) == ctx.xm.get("units", len(cu))
    covered = {c for g in bu for c in p.groups[g].cells}
    extra = []
    left = [c for c in U if c not in covered]
    if left:
        for key, rule in rules(p).items():
            if key[0] == "cage" and key[1] in bu:
                continue
            cs = [c for c in rule.cells if not st.vals[c] and st.cand[c] & bit(v)]
            if cs and set(cs) <= set(left) and _must_contain(p, st, rule, v):
                extra.append(rule)
                left = [c for c in left if c not in cs]
    k = len(cu)
    kw = {1: "one", 2: "two", 3: "three"}.get(k, str(k))

    def unit_txt(g):
        g_ = p.groups[g]
        return nm.unit(g) if g_.complete else f"{nm.cage(g, cells=False)} (every combination needs a {v})"

    bases = [unit_txt(g) for g in bu] + [f"{r.label} (every filling needs a {v})" for r in extra]
    short = f"{fmt_elims(nm, ctx.elims)}: counting the {v}s ({kw} must-have units vs {kw} houses)"
    teach = (
        f"Count {v}s. {_cap(_join(bases))} each must contain a {v}, and they don't overlap, so there are "
        f"{kw} {v}{'s' if k > 1 else ''} somewhere in {nm.cells(U, 'or')}. All of those cells lie in "
        f"{_join([nm.unit(g) for g in cu])}, which can hold only {kw} {v}{'s' if k > 1 else ''} between them. "
        f"So the covers' {v}s are exactly the ones in the pattern, and {nm.cells(sorted(c for c, _ in ctx.elims))} "
        f"can't be {v}. This is fish logic with cages or rules playing the part of rows."
    )
    J = _J(
        ctx,
        digits=[v],
        base_units=list(bu),
        cover_units=list(cu),
        base_cells=U,
        constraints=[_con_json(r) for r in extra],
        cover_cells=sorted(c for c, _ in ctx.elims),
    )
    return _result(ctx, J, short, teach, ok, lines=[(r.line_kind or r.kind, r.cells) for r in extra])


def _h_equal_digits(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    A, B, hi = ctx.xm.get("cell_a"), ctx.xm.get("cell_b"), ctx.xm.get("house")
    if A is None or B is None or hi is None:
        return _generic(ctx)
    H = p.groups[hi]
    ok = True
    for d in digits_of(st.cand[A]):
        cs = [c for c in H.cells if not st.vals[c] and st.cand[c] & bit(d) and c not in p.peers[A]]
        ok &= cs == [B]
    el = {(A, d) for d in digits_of(st.cand[A] & ~st.cand[B])} | {(B, d) for d in digits_of(st.cand[B] & ~st.cand[A])}
    ok &= set(ctx.elims) <= el
    short = f"{fmt_elims(nm, ctx.elims)}: {nm.cell(A)} and {nm.cell(B)} must hold the same digit"
    teach = (
        f"{nm.cell(A)} {nm.cset(st.cand[A])} sits outside {nm.unit(hi)}. Take any of its candidates: if "
        f"{nm.cell(A)} were that digit, {nm.unit(hi)} would still need one, and every spot for it in "
        f"{nm.unit(hi)} sees {nm.cell(A)} except {nm.cell(B)} {nm.cset(st.cand[B])}. So whatever {nm.cell(A)} "
        f"is, {nm.cell(B)} is the same digit -- and each cell can only keep candidates the other one has: "
        f"{_cant(nm, ctx.elims)}. Spotting 'these two cells are equal' is a powerful idea even before you "
        f"know the digit."
    )
    J = _J(ctx, digits=sorted(digits_of(st.cand[A] | st.cand[B])), base_units=[hi], base_cells=[A, B])
    return _result(ctx, J, short, teach, ok, extra_cells=[A, B])


def _h_line_scan(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    parent = _rule_from_move(ctx)
    pc = [c for c in ctx.engine.get("pattern_cells") or () if isinstance(c, int)]
    if parent is None or not parent.line_kind:
        return _generic(ctx)
    cells = parent.cells
    tg = {c for c, _ in ctx.elims}
    win = None
    for i in range(len(cells) - 2):
        w = cells[i : i + 3]
        if tg <= set(w) and set(pc) <= set(w):
            win = w
            break
    if win is None:
        return _generic(ctx)
    rule = Rule(
        "line", win, f"the three cells {nm.cells(win)} of {parent.label}", line_kind=parent.line_kind, con=parent.con
    )
    res = enum_rule(p, rule, _rule_dom(st, rule))
    comp = {(c, d) for i, c in enumerate(win) if not st.vals[c] for d in digits_of(st.cand[c] & ~res["sup"][i])}
    ok = set(ctx.elims) <= comp
    why = _line_reasons(ctx, rule, res)
    short = f"{fmt_elims(nm, ctx.elims)}: a three-cell stretch of the {LINE_NAMES.get(parent.line_kind, 'line')}"
    teach = (
        f"You don't need the whole of {parent.label} -- scan it three cells at a time. Look at "
        f"{nm.cells(win)}: {why} {_line_tip(parent.line_kind)}"
    )
    J = _J(ctx, digits=_elim_digits(ctx), constraints=[_con_json(parent)], base_cells=list(win))
    return _result(ctx, J, short, teach, ok, lines=[(parent.line_kind, win), (parent.line_kind, parent.cells)])


def _h_guess(ctx):
    nm, st = ctx.nm, ctx.st
    c, v = ctx.place
    short = f"{nm.cell(c)} = {v}: no logical step found -- the solver commits to a value"
    teach = (
        f"At this point none of the solver's techniques applies. It picks the cell with the fewest candidates, "
        f"{nm.cell(c)} {nm.cset(st.cand[c])}, and commits to {v} (the value in the known solution). A human "
        f"would either find a deeper pattern here or try a value and be ready to backtrack."
    )
    J = _J(ctx, digits=[v], base_cells=[c])
    return _result(ctx, J, short, teach, True)


def _h_take_notes(ctx):
    n = sum(1 for c in range(ctx.p.N) if not ctx.st.vals[c])
    short = "Pencil-mark the grid: scanning alone has run out"
    teach = (
        f"No more singles can be found by looking at the placed digits alone, so it's time to write the "
        f"candidates into the {n} empty cells. From here the solve works on notes: subsets, intersections and "
        f"patterns all read off the pencil marks."
    )
    J = _J(ctx)
    return _result(ctx, J, short, teach, True)


def _h_snyder_marks(ctx):
    short = "Snyder marks: corner-mark digits confined to two cells of a box"
    teach = (
        "Scanning has run out. Instead of full candidates, mark in each box only the digits that can go in just "
        "two of its cells (Snyder notation). Pairs that coincide or line up then give placements."
    )
    J = _J(ctx)
    return _result(ctx, J, short, teach, True)


def _generic(ctx):
    nm, _p = ctx.nm, ctx.p
    name, lesson = CONCEPTS.get(ctx.tech, (S.TECH_NAMES.get(ctx.tech, "?"), ""))
    if ctx.code:
        name = f"{name} ({ctx.code})"
    if ctx.place:
        c, v = ctx.place
        short = f"{nm.cell(c)} = {v}: {name}"
        teach = f"{_an(name)} {name} pattern forces {nm.cell(c)} to be {v}. {lesson}"
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: {name}"
        teach = f"{_an(name)} {name} pattern removes {_elim_list(nm, ctx.elims)}. {lesson}"
    J = _J(ctx, digits=sorted({d for _, d in ctx.elims}) or ([ctx.place[1]] if ctx.place else []))
    return _result(ctx, J, short, teach, False)


HANDLERS = {
    S.FULL_HOUSE: _h_full_house,
    S.NAKED_D: _h_naked_direct,
    S.HIDDEN_D: _h_hidden_direct,
    S.NAKED_DL: _h_pointing_direct,
    S.HIDDEN_DL: _h_pointing_direct,
    S.TAKE_NOTES: _h_take_notes,
    S.SNYDER_MARKS: _h_snyder_marks,
    S.NAKED_N: _h_naked_notes,
    S.HIDDEN_N: _h_hidden_notes,
    S.LOCKED: _h_locked,
    S.NPAIR: _h_subset,
    S.HPAIR: _h_subset,
    S.NTRIPLE: _h_subset,
    S.HTRIPLE: _h_subset,
    S.NQUAD: _h_subset,
    S.HQUAD: _h_subset,
    S.XWING: _h_fish,
    S.SWORDFISH: _h_fish,
    S.JELLYFISH: _h_fish,
    S.FINNED_FISH: _h_fish,
    S.XYWING: _h_wing,
    S.XYZWING: _h_wing,
    S.COLORING: _h_coloring,
    S.PAIRARC: _h_pairarc,
    S.TRIAL: _h_trial,
    S.SHORT_TRIAL: _h_trial,
    S.GUESS: _h_guess,
    S.INNIE_D: _h_innie,
    S.INNIE_N: _h_innie,
    S.INNIE_X: _h_innie,
    S.CAGE_COMBO: _h_combo,
    S.SUM_COMBO: _h_combo,
    S.ARROW_COMBO: _h_combo,
    S.SET_COMBO: _h_combo,
    S.EQSUM_COMBO: _h_combo,
    S.TABLE_COMBO: _h_combo,
    S.SANDWICH_COMBO: _h_combo,
    S.XSUM_COMBO: _h_combo,
    S.SKYLINE_COMBO: _h_combo,
    S.COUNT_COMBO: _h_combo,
    S.LINE_RANGE: _h_combo,
    S.LOL_COMBO: _h_lol,
    S.COMBO_LOCK: _h_combo_lock,
    S.NARY_D: _h_nary_direct,
    S.LINE_D: _h_mental,
    S.MENTAL_D: _h_mental,
    S.X_CHAIN: _h_chain,
    S.XY_CHAIN: _h_chain,
    S.AIC_CHAIN: _h_chain,
    S.NICE_LOOP: _h_chain,
    S.ALS_AIC: _h_chain,
    S.UNIQUE_RECT: _h_ur,
    S.BUG_PLUS1: _h_bug,
    S.ALS_XZ: _h_als_xz,
    S.ALS_XYWING: _h_als_xywing,
    S.DEATH_BLOSSOM: _h_death_blossom,
}


for _code, _h, _name, _lesson in (
    (
        "DIGIT_COUNT",
        _h_digit_count,
        "Digit counting",
        "Count how many copies of a digit some units must hold and how many the houses covering them can take; "
        "when the numbers match, the digit is pinned to the pattern.",
    ),
    (
        "EQUAL_DIGITS",
        _h_equal_digits,
        "Equal cells",
        "Two cells can be forced to hold the same unknown digit; then each keeps only the candidates both share.",
    ),
    (
        "LINE_SCAN",
        _h_line_scan,
        "Local line scan",
        "On long lines, look at a few consecutive cells at a time; local windows often carry the whole logic.",
    ),
):
    HANDLERS[getattr(S, _code)] = _h
    CONCEPTS.setdefault(getattr(S, _code), (_name, _lesson))
    EXTRA_FAMILY.setdefault(getattr(S, _code), "fish+wings" if _code == "DIGIT_COUNT" else "intersections+combos")
HANDLERS[S.LINE_CLASS] = _h_line_class
CONCEPTS.setdefault(
    S.LINE_CLASS,
    (
        "Line classes",
        "Group digits into classes (low/high, odd/even, thirds) "
        "and reason about the pattern of classes along a line before exact digits.",
    ),
)
HANDLERS[S.EITHER_WAY] = _h_either_way
CONCEPTS.setdefault(
    S.EITHER_WAY,
    (
        "Either way (two-case check)",
        "When something must be one of two things, follow both "
        "options a few steps; whatever happens in both branches is true.",
    ),
)
HANDLERS[S.MENTAL_CHAIN] = _h_mental_chain
CONCEPTS.setdefault(
    S.MENTAL_CHAIN,
    (
        "Chain without notes",
        "A couple of 'if this, then that' steps can "
        "be held in the head: follow what each cell can still be until the "
        "chain forces a digit.",
    ),
)


def _engine_override(ctx, out):
    """Attach the engine's justification; its structure fills whatever the reconstruction lacks."""
    if not ctx.raw_engine:
        return out
    J = out["J"]
    J["engine"] = ctx.raw_engine
    if not out["verified"]:
        for k in ("base_units", "cover_units", "als", "rcc", "constraints"):
            if ctx.engine.get(k) and not J.get(k):
                J[k] = ctx.engine[k]
    pc = [c for c in ctx.engine.get("pattern_cells") or () if isinstance(c, int)]
    if pc:
        vis = out["visual"]
        vis["pattern"] = [ctx.nm.cell(c) for c in ctx.nm.sort(pc)]
    out["derived"] = not ctx.used_engine
    return out


def explain(step, puzzle, state):
    """Explanation dict for one solver step (state = grid before the step; see replay())."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    puzzle = derived(puzzle)
    st = _as_state(puzzle, state)
    if st.p is not puzzle:
        st = State(puzzle, st.vals, st.cand, st.mode)
        st.idx, st.lost = getattr(state, "idx", 0), getattr(state, "lost", {})
    ctx = Ctx(step, puzzle, st)
    h = HANDLERS.get(ctx.tech, _generic)
    try:
        out = h(ctx)
    except Exception as e:  # never let a reconstruction bug break the stream
        out = _generic(ctx)
        out["error"] = f"{type(e).__name__}: {e}"
    out.setdefault("derived", True)
    out = _engine_override(ctx, out)
    name, lesson = CONCEPTS.get(ctx.tech, (S.TECH_NAMES.get(ctx.tech, "?"), ""))
    fam = (
        FAMILIES[family_of(ctx.tech)][0]
        if ctx.tech not in (S.TAKE_NOTES, S.GUESS, S.SNYDER_MARKS)
        else ("trial" if ctx.tech == S.GUESS else "setup")
    )
    if not any(ctx.tech in ts for _, ts in FAMILIES) and ctx.tech in EXTRA_FAMILY:
        fam = EXTRA_FAMILY[ctx.tech]
    try:
        tkey = _technique_key(ctx, out)
    except Exception:
        tkey = "rule_logic"
    tinfo = technique_info(tkey)
    if out["J"].get("pattern"):
        tinfo["pattern"] = out["J"]["pattern"]
        if out["J"].get("pattern_type"):
            tinfo["pattern_type"] = out["J"]["pattern_type"]
    name = tinfo["name"]
    out["short"], out["teach"] = _an(out["short"]), _an(out["teach"])
    res = {
        "step": st.idx,
        "technique": tinfo,
        "engine_technique": S.TECH_NAMES.get(ctx.tech, str(ctx.tech)),
        "mode": step.mode,
        "short": out["short"],
        "teach": out["teach"],
        "concept": {
            "family": fam,
            "family_name": FAMILY_DISPLAY.get(fam, fam),
            "technique": name,
            "lesson": lesson if tkey not in _VARIANT_LESSONS else _VARIANT_LESSONS[tkey],
        },
        "visual": out["visual"],
        "annotation": dict(ANNOTATION),
        "justification": _jsonable(out["J"]),
        "derived": out.get("derived", True),
        "verified": bool(out["verified"]),
    }
    if "error" in out:
        res["error"] = out["error"]
    return res


def _an(text):
    """'a 8' -> 'an 8' (also 11, 18)."""
    text = re.sub(r"\b([Aa]) (8|11|18)\b", lambda m: m.group(1) + "n " + m.group(2), text)
    return re.sub(r"\b([Aa]) (X-|XY-|XYZ-|ALS|AIC|X=)", lambda m: m.group(1) + "n " + m.group(2), text)


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in x]
    if isinstance(x, Rule):
        return x.label
    return x


def explain_all(puzzle, steps):
    return [explain(step, puzzle, st) for _, step, st in replay(puzzle, steps)]


# ================================================================ technique names ==
SW, HD, SN = "https://www.sudokuwiki.org/", "https://hodoku.sourceforge.net/en/", "https://www.sudokusnake.com/"
_LINKS_FILE = "explain_links.json"  # in pencilmark/data

# key -> (primary name, {source: [aliases]}, family index (metrics.FAMILIES), [urls], [prerequisite keys])
# sources: sudokuwiki (Andrew Stuart), HoDoKu, Sudoku Explainer (SE), Sudoku Snake, other (common usage)
CATALOG = {
    "full_house": (
        "Full House",
        {"other": ["Last empty cell", "Last digit"], "HoDoKu": ["Full House"], "SE": ["Full House"]},
        0,
        [HD + "tech_singles.php#fh"],
        [],
    ),
    "cross_hatching": (
        "Hidden Single",
        {
            "other": ["Cross-hatching", "Hidden single in a box", "Slicing and dicing"],
            "sudokuwiki": ["Hidden Single"],
            "HoDoKu": ["Hidden Single"],
            "SE": ["Hidden Single"],
            "Sudoku Snake": ["Hidden Singles by Box"],
        },
        0,
        [SN + "hiddensinglesbybox.php", SW + "Getting_Started", HD + "tech_singles.php#h1"],
        [],
    ),
    "hidden_single": (
        "Hidden Single",
        {
            "other": ["Only place in the row/column", "Pinned digit"],
            "sudokubliss": ["Last Possible Number"],
            "sudokuwiki": ["Hidden Single"],
            "HoDoKu": ["Hidden Single"],
            "SE": ["Hidden Single"],
            "Sudoku Snake": ["Hidden Singles"],
        },
        0,
        [SN + "hiddensingles.php", SW + "Getting_Started", HD + "tech_singles.php#h1"],
        ["cross_hatching"],
    ),
    "naked_single": (
        "Naked Single",
        {
            "other": ["Sole candidate", "Last remaining digit"],
            "sudokuwiki": ["Naked Single"],
            "HoDoKu": ["Naked Single"],
            "SE": ["Naked Single"],
            "Sudoku Snake": ["Naked Singles"],
        },
        0,
        [SN + "nakedsingles.php", SW + "Getting_Started", HD + "tech_singles.php#n1"],
        ["full_house"],
    ),
    "single_after_pointing": (
        "Single with Locked Candidates",
        {"other": ["Single using a pointing digit", "Virtual digit"], "SE": ["Hidden Single (with Pointing)"]},
        1,
        [SN + "pointing.php", HD + "tech_intersections.php#lc1"],
        ["hidden_single", "pointing"],
    ),
    "pointing": (
        "Locked Candidates (Pointing)",
        {
            "sudokuwiki": ["Pointing Pairs", "Pointing Triples", "Intersection Removal"],
            "HoDoKu": ["Locked Candidates Type 1 (Pointing)"],
            "SE": ["Pointing"],
            "Sudoku Snake": ["Pointing"],
            "other": ["Pointing pair/triple"],
        },
        1,
        [SW + "Intersection_Removal", HD + "tech_intersections.php#lc1", SN + "pointing.php"],
        ["hidden_single"],
    ),
    "claiming": (
        "Locked Candidates (Claiming)",
        {
            "other": ["Claiming", "Box/line reduction"],
            "sudokuwiki": ["Box/Line Reduction", "Intersection Removal"],
            "HoDoKu": ["Locked Candidates Type 2 (Claiming)"],
            "SE": ["Claiming"],
            "Sudoku Snake": ["Claiming"],
        },
        1,
        [SW + "Intersection_Removal#LBR", HD + "tech_intersections.php#lc2", SN + "claiming.php"],
        ["hidden_single"],
    ),
    "naked_pair": (
        "Naked Pair",
        {
            "sudokuwiki": ["Naked Pair"],
            "HoDoKu": ["Naked Pair", "Locked Pair"],
            "SE": ["Naked Pair"],
            "Sudoku Snake": ["Naked Subsets"],
        },
        2,
        [SW + "Naked_Candidates#NP", HD + "tech_naked.php#n2", SN + "nakedsubsets.php"],
        ["naked_single"],
    ),
    "naked_triple": (
        "Naked Triple",
        {
            "sudokuwiki": ["Naked Triple"],
            "HoDoKu": ["Naked Triple", "Locked Triple"],
            "SE": ["Naked Triplet"],
            "Sudoku Snake": ["Naked Subsets"],
        },
        2,
        [SW + "Naked_Candidates#NT", HD + "tech_naked.php#n3", SN + "nakedsubsets.php"],
        ["naked_pair"],
    ),
    "naked_quad": (
        "Naked Quad",
        {
            "sudokuwiki": ["Naked Quad"],
            "HoDoKu": ["Naked Quadruple"],
            "SE": ["Naked Quad"],
            "Sudoku Snake": ["Naked Subsets"],
        },
        2,
        [SW + "Naked_Candidates#NQ", HD + "tech_naked.php#n4", SN + "nakedsubsets.php"],
        ["naked_triple"],
    ),
    "hidden_pair": (
        "Hidden Pair",
        {
            "sudokuwiki": ["Hidden Pair"],
            "HoDoKu": ["Hidden Pair"],
            "SE": ["Hidden Pair"],
            "Sudoku Snake": ["Hidden Subsets"],
        },
        2,
        [SW + "Hidden_Candidates#HP", HD + "tech_hidden.php#h2", SN + "hiddensubsets.php"],
        ["naked_pair"],
    ),
    "hidden_triple": (
        "Hidden Triple",
        {
            "sudokuwiki": ["Hidden Triple"],
            "HoDoKu": ["Hidden Triple"],
            "SE": ["Hidden Triplet"],
            "Sudoku Snake": ["Hidden Subsets"],
        },
        2,
        [SW + "Hidden_Candidates#HT", HD + "tech_hidden.php#h3", SN + "hiddensubsets.php"],
        ["hidden_pair"],
    ),
    "hidden_quad": (
        "Hidden Quad",
        {
            "sudokuwiki": ["Hidden Quad"],
            "HoDoKu": ["Hidden Quadruple"],
            "SE": ["Hidden Quad"],
            "Sudoku Snake": ["Hidden Subsets"],
        },
        2,
        [SW + "Hidden_Candidates#HQ", HD + "tech_hidden.php#h4", SN + "hiddensubsets.php"],
        ["hidden_triple"],
    ),
    "x_wing": (
        "X-Wing",
        {"sudokuwiki": ["X-Wing"], "HoDoKu": ["X-Wing"], "SE": ["X-Wing"], "Sudoku Snake": ["X-Wings"]},
        3,
        [SW + "X_Wing_Strategy", HD + "tech_fishb.php#bf2", SN + "xwings.php"],
        ["pointing", "claiming"],
    ),
    "swordfish": (
        "Swordfish",
        {"sudokuwiki": ["Swordfish"], "HoDoKu": ["Swordfish"], "SE": ["Swordfish"], "Sudoku Snake": ["Swordfish"]},
        3,
        [SW + "Sword_Fish_Strategy", HD + "tech_fishb.php#bf3", SN + "swordfish.php"],
        ["x_wing"],
    ),
    "jellyfish": (
        "Jellyfish",
        {"sudokuwiki": ["Jellyfish"], "HoDoKu": ["Jellyfish"], "SE": ["Jellyfish"], "Sudoku Snake": ["Jellyfish"]},
        3,
        [SW + "Jelly_Fish_Strategy", HD + "tech_fishb.php#bf4", SN + "jellyfish.php"],
        ["swordfish"],
    ),
    "finned_x_wing": (
        "Finned X-Wing",
        {
            "sudokuwiki": ["Finned X-Wing"],
            "HoDoKu": ["Finned X-Wing", "Sashimi X-Wing"],
            "SE": ["Finned X-Wing"],
            "Sudoku Snake": ["Finned X-Wings"],
        },
        3,
        [SW + "Finned_X_Wing", HD + "tech_fishfs.php#fbf2", SN + "finnedxwings.php"],
        ["x_wing"],
    ),
    "finned_swordfish": (
        "Finned Swordfish",
        {
            "sudokuwiki": ["Finned Swordfish"],
            "HoDoKu": ["Finned Swordfish", "Sashimi Swordfish"],
            "Sudoku Snake": ["Finned Swordfish"],
        },
        3,
        [SW + "Finned_Swordfish", HD + "tech_fishfs.php#fbf3", SN + "finnedswordfish.php"],
        ["swordfish", "finned_x_wing"],
    ),
    "finned_jellyfish": (
        "Finned Jellyfish",
        {"HoDoKu": ["Finned Jellyfish", "Sashimi Jellyfish"], "Sudoku Snake": ["Finned Jellyfish"]},
        3,
        [HD + "tech_fishfs.php#fbf4", SN + "finnedjellyfish.php"],
        ["jellyfish", "finned_swordfish"],
    ),
    "franken_fish": (
        "Franken Fish",
        {
            "sudokuwiki": ["Franken Swordfish"],
            "HoDoKu": ["Franken Fish"],
            "Sudoku Snake": ["Mutant Swordfish", "Mutant Jellyfish"],
        },
        3,
        [SW + "Franken_Sword_Fish", HD + "tech_fishc.php#ff", SN + "mutantswordfish.php"],
        ["swordfish"],
    ),
    "xy_wing": (
        "XY-Wing",
        {
            "sudokuwiki": ["Y-Wing"],
            "HoDoKu": ["XY-Wing"],
            "SE": ["XY-Wing"],
            "Sudoku Snake": ["XY-Wings"],
            "other": ["Y-Wing", "Bent triple"],
        },
        3,
        [SW + "Y_Wing_Strategy", HD + "tech_wings.php#xy", SN + "xywings.php"],
        ["naked_pair"],
    ),
    "xyz_wing": (
        "XYZ-Wing",
        {"sudokuwiki": ["XYZ-Wing"], "HoDoKu": ["XYZ-Wing"], "SE": ["XYZ-Wing"], "Sudoku Snake": ["XYZ-Wings"]},
        3,
        [SW + "XYZ_Wing", HD + "tech_wings.php#xyz", SN + "xyzwings.php"],
        ["xy_wing"],
    ),
    "w_wing": (
        "W-Wing",
        {"sudokuwiki": ["W-Wing"], "HoDoKu": ["W-Wing"]},
        3,
        [SW + "W_Wing_Strategy", HD + "tech_wings.php#w"],
        ["xy_wing"],
    ),
    "simple_colouring": (
        "Simple Coloring",
        {
            "sudokuwiki": ["Simple Colouring", "Singles Chains"],
            "HoDoKu": ["Simple Colors"],
            "Sudoku Snake": ["Coloring"],
            "other": ["Single-digit coloring", "Color wrap", "Color trap"],
        },
        3,
        [SW + "Simple_Colouring", HD + "tech_col.php#sc", SN + "coloring.php"],
        ["x_wing"],
    ),
    "skyscraper": (
        "Skyscraper",
        {
            "HoDoKu": ["Skyscraper"],
            "sudokuwiki": ["Rectangle Elimination"],
            "SE": ["Turbot Fish"],
            "other": ["Single-digit pattern"],
        },
        3,
        [HD + "tech_sdp.php#sk", SW + "Rectangle_Elimination"],
        ["x_wing"],
    ),
    "two_string_kite": (
        "2-String Kite",
        {"HoDoKu": ["2-String Kite"], "sudokuwiki": ["Rectangle Elimination"], "SE": ["Turbot Fish"]},
        3,
        [HD + "tech_sdp.php#t2sk", SW + "Rectangle_Elimination"],
        ["skyscraper"],
    ),
    "turbot_fish": (
        "Turbot Fish",
        {"HoDoKu": ["Turbot Fish"], "SE": ["Turbot Fish"], "other": ["Single-digit chain of length 4"]},
        3,
        [HD + "tech_sdp.php#tf"],
        ["skyscraper", "two_string_kite"],
    ),
    "empty_rectangle": (
        "Empty Rectangle",
        {"HoDoKu": ["Empty Rectangle"], "sudokuwiki": ["Empty Rectangles"]},
        3,
        [HD + "tech_sdp.php#er", SW + "Empty_Rectangles"],
        ["pointing", "skyscraper"],
    ),
    "unique_rectangle": (
        "Unique Rectangle",
        {
            "sudokuwiki": ["Unique Rectangles", "Hidden Unique Rectangles"],
            "HoDoKu": ["Uniqueness Test 1-6", "Hidden Rectangle"],
            "SE": ["Unique Rectangle"],
            "other": ["Deadly pattern"],
        },
        3,
        [SW + "Unique_Rectangles", HD + "tech_ur.php", SW + "Hidden_Unique_Rectangles"],
        ["naked_pair"],
    ),
    "bug_plus_1": (
        "BUG+1",
        {"sudokuwiki": ["BUG"], "HoDoKu": ["Bivalue Universal Grave + 1"], "SE": ["Bivalue Universal Grave"]},
        3,
        [SW + "BUG", HD + "tech_ur.php#bug1"],
        ["unique_rectangle"],
    ),
    "x_chain": (
        "X-Chain",
        {"sudokuwiki": ["X-Cycles"], "HoDoKu": ["X-Chain"], "SE": ["X-Chain"], "other": ["Single-digit chain"]},
        4,
        [SW + "X_Cycles", HD + "tech_chains.php#x"],
        ["simple_colouring", "skyscraper"],
    ),
    "xy_chain": (
        "XY-Chain",
        {"sudokuwiki": ["XY-Chain"], "HoDoKu": ["XY-Chain"], "SE": ["XY-Chain"], "Sudoku Snake": ["Naked XY-Chains"]},
        4,
        [SW + "XY_Chains", HD + "tech_chains.php#xyc", SN + "nakedxychains.php"],
        ["xy_wing"],
    ),
    "remote_pair": (
        "Remote Pair",
        {"sudokuwiki": ["Remote Pairs"], "HoDoKu": ["Remote Pair"], "Sudoku Snake": ["Remote Pairs"]},
        4,
        [SW + "Remote_Pairs", HD + "tech_chains.php#rp", SN + "remotepairs.php"],
        ["xy_chain"],
    ),
    "aic": (
        "Alternating Inference Chain",
        {"other": ["AIC"], "sudokuwiki": ["Alternating Inference Chains"], "HoDoKu": ["AIC"], "SE": ["Forcing Chain"]},
        4,
        [SW + "Alternating_Inference_Chains", HD + "tech_chains.php#in"],
        ["x_chain", "xy_chain"],
    ),
    "nice_loop": (
        "Nice Loop",
        {
            "HoDoKu": ["Discontinuous Nice Loop", "Continuous Nice Loop"],
            "sudokuwiki": ["X-Cycles", "Alternating Inference Chains"],
            "SE": ["Cell/Region Forcing Chains"],
        },
        4,
        [HD + "tech_chains.php#nl", SW + "X_Cycles"],
        ["aic"],
    ),
    "als_xz": (
        "ALS-XZ",
        {
            "sudokuwiki": ["Almost Locked Sets"],
            "HoDoKu": ["Almost Locked Set XZ-Rule"],
            "SE": ["Aligned Pair Exclusion (related)"],
        },
        5,
        [SW + "Almost_Locked_Sets", HD + "tech_als.php#axz"],
        ["naked_triple", "aic"],
    ),
    "als_xy_wing": (
        "ALS-XY-Wing",
        {"HoDoKu": ["Almost Locked Set XY-Wing"], "sudokuwiki": ["Almost Locked Sets"]},
        5,
        [HD + "tech_als.php#axy", SW + "Almost_Locked_Sets"],
        ["als_xz"],
    ),
    "death_blossom": (
        "Death Blossom",
        {"sudokuwiki": ["Death Blossom"], "HoDoKu": ["Death Blossom"], "Sudoku Snake": ["Death Blossom"]},
        5,
        [SW + "Death_Blossom", HD + "tech_als.php#db", SN + "deathblossom.php"],
        ["als_xz"],
    ),
    "als_chain": (
        "ALS-Chain",
        {"sudokuwiki": ["AIC with ALSs"], "HoDoKu": ["ALS-Chain"]},
        5,
        [SW + "AIC_with_ALSs", HD + "tech_als.php#ach"],
        ["als_xz", "aic"],
    ),
    "trial": (
        "Trial and Error",
        {
            "sudokuwiki": ["Nishio Forcing Chains", "Bowman's Bingo"],
            "HoDoKu": ["Trial and Error"],
            "SE": ["Nishio Forcing Chain"],
            "other": ["Contradiction", "Bifurcation"],
        },
        6,
        [SW + "Nishio_Forcing_Chains", HD + "tech_last.php#ts", SW + "Bowmans_Bingo"],
        ["aic"],
    ),
    "short_contradiction": (
        "Nishio Forcing Chain",
        {
            "sudokuwiki": ["Nishio Forcing Chains"],
            "SE": ["Nishio Forcing Chain"],
            "other": ["Short contradiction", "Bivalue test"],
        },
        6,
        [SW + "Nishio_Forcing_Chains"],
        ["naked_single", "hidden_single"],
    ),
    "either_way": (
        "Either Way (two-case check)",
        {
            "other": ["Forcing chain"],
            "sudokuwiki": ["Cell Forcing Chains", "Unit Forcing Chains"],
            "HoDoKu": ["Forcing Chain"],
            "SE": ["Cell Forcing Chains"],
            "Sudoku Snake": ["Forcing Chains", "Unit Forcing Chains"],
        },
        6,
        [SW + "Cell_Forcing_Chains", SW + "Unit_Forcing_Chains", HD + "tech_last.php#fc", SN + "forcingchains.php"],
        ["naked_single", "hidden_single"],
    ),
    "guess": (
        "Brute Force",
        {"HoDoKu": ["Brute Force"], "other": ["Guess", "Bifurcation", "Backtracking"]},
        6,
        [HD + "tech_last.php#bf", SW + "Brute_Force_vs_Logical_Strategies"],
        [],
    ),
    "pencil_marks": ("Pencil marks", {"other": ["Candidates", "Notes", "Snyder notation"]}, 0, [], []),
    "pair_in_head": (
        "Pair in your head",
        {"other": ["Mental naked pair", "Hidden pair without notes"]},
        2,
        [SW + "Naked_Candidates#NP"],
        ["naked_pair"],
    ),
    "triple_in_head": (
        "Triple in your head",
        {"other": ["Mental naked triple"]},
        2,
        [SW + "Naked_Candidates#NT"],
        ["naked_triple"],
    ),
    "pointing_in_head": (
        "Pointing in your head",
        {"other": ["Mental locked candidates"]},
        1,
        [SW + "Intersection_Removal"],
        ["pointing"],
    ),
    "chain_without_notes": (
        "Chain without notes",
        {"other": ["Mental chain", "Short forcing chain"]},
        4,
        [SW + "Alternating_Inference_Chains"],
        ["x_chain", "xy_chain"],
    ),
    "equal_cells": (
        "Two cells with the same digit",
        {"other": ["Abstract colouring", "Equivalent cells"]},
        3,
        [],
        ["hidden_single"],
    ),
    "digit_counting": (
        "Digit counting",
        {"other": ["Generalised fish", "Cage fish"], "HoDoKu": ["Generalized Fish"]},
        3,
        [HD + "tech_fishg.php", SW + "Cage_Unit_Overlap"],
        ["x_wing", "killer_combinations"],
    ),
    "law_of_leftovers": (
        "Law of Leftovers",
        {"sudokuwiki": ["Law of Leftovers"], "other": ["Set equivalence", "Phistomefel ring (special case)"]},
        1,
        [SW + "Law_of_Leftovers"],
        ["claiming"],
    ),
    "phistomefel_ring": (
        "Phistomefel ring",
        {"other": ["Phistomefel's theorem", "Set equivalence"]},
        3,
        [SW + "Law_of_Leftovers"],
        ["law_of_leftovers"],
    ),
    "phistomefel_variant": (
        "Phistomefel variant",
        {"other": ["Set equivalence"]},
        3,
        [SW + "Law_of_Leftovers"],
        ["phistomefel_ring"],
    ),
    "implied_house": (
        "Implied House",
        {"other": ["Hidden window", "Law of leftovers"], "sudokuwiki": ["Windoku Strategy"]},
        1,
        [SW + "Windoku_Strategy", SW + "Law_of_Leftovers"],
        ["full_house"],
    ),
    # variants
    "killer_combinations": (
        "Killer Combinations",
        {"sudokuwiki": ["Killer Combinations"], "other": ["Cage combinations", "Sum combinations"]},
        1,
        [
            SW + "Killer_Combinations",
            SW + "Killer_Cage_Combination_Example",
            "https://en.wikipedia.org/wiki/Killer_sudoku",
        ],
        ["naked_single"],
    ),
    "cage_must_contain": (
        "Cage Unit Overlap",
        {"sudokuwiki": ["Cage/Unit Overlap"], "other": ["Cage must-contain digit", "Killer pointing"]},
        1,
        [SW + "Cage_Unit_Overlap", SW + "Killer_Combinations"],
        ["killer_combinations", "pointing"],
    ),
    "rule_of_45": (
        "Innies and Outies",
        {"sudokuwiki": ["Innies and Outies"], "other": ["Rule of 45", "Secret of 45"]},
        1,
        [SW + "Innies_and_Outies", "https://en.wikipedia.org/wiki/Killer_sudoku"],
        ["killer_combinations"],
    ),
    "cage_arithmetic": (
        "Cage arithmetic",
        {"other": ["Last cell of a cage"]},
        0,
        [SW + "Killer_Combinations"],
        ["full_house"],
    ),
    "thermo": ("Thermo logic", {"other": ["Thermometer counting", "Thermo bulb logic"]}, 1, [], ["naked_single"]),
    "german_whispers": (
        "German whispers",
        {"other": ["Whisper high/low logic", "No 5s on a whisper"]},
        1,
        [],
        ["naked_single"],
    ),
    "dutch_whispers": ("Dutch whispers", {"other": ["Whisper high/low logic"]}, 1, [], ["german_whispers"]),
    "renban": ("Renban runs", {"other": ["Consecutive set line", "Purple line"]}, 1, [], ["naked_single"]),
    "arrow": ("Arrow sums", {"other": ["Arrow arithmetic"]}, 1, [], ["killer_combinations"]),
    "kropki": ("Kropki dots", {"other": ["Consecutive / ratio dots", "White and black dots"]}, 1, [], ["naked_single"]),
    "palindrome": ("Palindrome lines", {"other": ["Mirror line"]}, 1, [], ["naked_single"]),
    "between": ("Between lines", {"other": ["Between-circle logic"]}, 1, [], ["thermo"]),
    "entropic": ("Entropic lines", {"other": ["Low/middle/high triples"]}, 1, [], ["naked_single"]),
    "modular": ("Modular lines", {"other": ["Mod-3 classes"]}, 1, [], ["naked_single"]),
    "parity": ("Parity lines", {"other": ["Odd/even alternation"]}, 1, [], ["naked_single"]),
    "region_sum": ("Region-sum lines", {"other": ["Equal box segments"]}, 1, [], ["killer_combinations"]),
    "zipper": ("Zipper lines", {"other": ["Equal pair sums"]}, 1, [], ["killer_combinations"]),
    "nonconsecutive": (
        "Non-consecutive logic",
        {"other": ["Neighbours can't be consecutive"]},
        1,
        [],
        ["naked_single"],
    ),
    "anti_knight": ("Anti-knight logic", {"other": ["Chess-move constraint"]}, 1, [], ["cross_hatching"]),
    "xv": ("XV sums", {"other": ["X (10) and V (5) pairs"]}, 1, [], ["killer_combinations"]),
    "sandwich": ("Sandwich sums", {"other": ["Sum between 1 and 9"]}, 1, [], ["killer_combinations"]),
    "x_sum": ("X-sums", {"other": ["First-digit count sums"]}, 1, [], ["killer_combinations"]),
    "skyscraper_clue": ("Skyscraper clues", {"other": ["Visible buildings"]}, 1, [], ["naked_single"]),
    "little_killer": ("Little killer sums", {"other": ["Diagonal sums"]}, 1, [], ["killer_combinations"]),
    "line_window": ("Local line scan", {"other": ["Three cells at a time"]}, 1, [], ["naked_single"]),
    "rule_logic": (
        "Rule combinations",
        {"other": ["Checking a rule's possible fillings"]},
        1,
        [],
        ["killer_combinations"],
    ),
    "pair_rule": ("Neighbour-rule logic", {"other": ["Pair constraints"]}, 1, [], ["naked_single"]),
}

_LINE_KEY = {
    "thermo": "thermo",
    "slow_thermo": "thermo",
    "whisper": "german_whispers",
    "dutch_whisper": "dutch_whispers",
    "renban": "renban",
    "palindrome": "palindrome",
    "kropki_chain": "kropki",
    "between": "between",
    "entropic": "entropic",
    "modular": "modular",
    "parity": "parity",
    "region_sum": "region_sum",
    "zipper": "zipper",
    "arrow": "arrow",
    "cage": "killer_combinations",
    "sum": "killer_combinations",
    "little_killer": "little_killer",
    "sandwich": "sandwich",
    "xsum": "x_sum",
    "skyscraper": "skyscraper_clue",
    "set": "renban",
    "innie": "rule_of_45",
    "equal_sum": "zipper",
    "table": "rule_logic",
    "count": "rule_logic",
}
_REL_KEY = {
    "non-consecutive": "nonconsecutive",
    "anti-knight": "anti_knight",
    "anti-king": "anti_knight",
    "thermometer": "thermo",
    "slow thermometer": "thermo",
    "German whisper": "german_whispers",
    "Dutch whisper": "dutch_whispers",
    "white kropki dot": "kropki",
    "black kropki dot": "kropki",
    "palindrome": "palindrome",
    "entropic line": "entropic",
    "parity line": "parity",
    "modular line": "modular",
    "V (sum 5)": "xv",
    "X (sum 10)": "xv",
}

_CONFIRMED = None


def _confirmed():
    """Reference pages confirmed reachable (status 200) when the link table was built."""
    global _CONFIRMED
    if _CONFIRMED is None:
        try:
            from . import _data

            data = _data.load_json(_LINKS_FILE)
            _CONFIRMED = {u for u, v in data.items() if v.get("status") == 200}
        except Exception:
            _CONFIRMED = set()
    return _CONFIRMED


def candidate_urls():
    return {u for v in CATALOG.values() for u in v[3]}


def technique_info(key):
    from .metrics import FAMILY_TIERS

    name, aliases, fam, urls, pre = CATALOG.get(key) or (key, {}, 0, [], [])
    ok = _confirmed()
    flat = []
    for src in ("other", "sudokuwiki", "HoDoKu", "SE", "Sudoku Snake"):
        for a in aliases.get(src, ()):
            if a.lower().rstrip("s") != name.lower().rstrip("s") and a not in flat:
                flat.append(a)
    return {
        "key": key,
        "name": name,
        "aliases": flat,
        "aliases_by_source": aliases,
        "family": FAMILY_DISPLAY.get(FAMILIES[fam][0], FAMILIES[fam][0]),
        "tier": FAMILY_TIERS[min(fam, len(FAMILY_TIERS) - 1)],
        "learn_more": [u for u in urls if u.split("#")[0] in ok],
        "prerequisites": [CATALOG[k][0] for k in pre if k in CATALOG],
    }


def _rule_key(rule):
    if rule is None:
        return "rule_logic"
    return _LINE_KEY.get(rule.line_kind or rule.kind, "rule_logic")


def _technique_key(ctx, out):
    """Which named technique this explanation teaches (sub-pattern / variant aware)."""
    t, p, J = ctx.tech, ctx.p, out["J"]
    if t == S.FULL_HOUSE:
        gi = ctx.gi(ctx.m.name)
        return "implied_house" if gi is not None and p.groups[gi].kind == "implied" else "full_house"
    if t in (S.HIDDEN_D, S.HIDDEN_N):
        gi = ctx.gi(ctx.m.name)
        if gi is not None and p.groups[gi].kind == "implied":
            return "implied_house"
        return (
            "cross_hatching" if t == S.HIDDEN_D and gi is not None and p.groups[gi].kind == "box" else "hidden_single"
        )
    if t in (S.NAKED_D, S.NAKED_N):
        return "naked_single"
    if t in (S.NAKED_DL, S.HIDDEN_DL):
        return "single_after_pointing"
    if t == S.TAKE_NOTES:
        return "pencil_marks"
    if t == S.SNYDER_MARKS:
        return "snyder_marks"
    if t == S.LOCKED:
        bu, cu = J.get("base_units") or [], J.get("cover_units") or []
        if bu and cu and p.groups[cu[0]].kind == "cage":
            return "cage_must_contain"
        if bu and p.groups[bu[0]].kind in ("row", "col"):
            return "claiming"
        return "pointing"
    simple = {
        S.NPAIR: "naked_pair",
        S.NTRIPLE: "naked_triple",
        S.NQUAD: "naked_quad",
        S.HPAIR: "hidden_pair",
        S.HTRIPLE: "hidden_triple",
        S.HQUAD: "hidden_quad",
        S.XYWING: "xy_wing",
        S.XYZWING: "xyz_wing",
        S.COLORING: "simple_colouring",
        S.UNIQUE_RECT: "unique_rectangle",
        S.BUG_PLUS1: "bug_plus_1",
        S.ALS_XZ: "als_xz",
        S.ALS_XYWING: "als_xy_wing",
        S.DEATH_BLOSSOM: "death_blossom",
        S.ALS_AIC: "als_chain",
        S.TRIAL: "trial",
        S.SHORT_TRIAL: "short_contradiction",
        S.GUESS: "guess",
        S.LOL_COMBO: "law_of_leftovers",
        S.INNIE_D: "rule_of_45",
        S.INNIE_N: "rule_of_45",
        S.INNIE_X: "rule_of_45",
        S.CAGE_COMBO: "killer_combinations",
    }
    if t in simple:
        return simple[t]
    if t in (S.XWING, S.SWORDFISH, S.JELLYFISH, S.FINNED_FISH):
        return out.get("pattern_key") or {S.XWING: "x_wing", S.SWORDFISH: "swordfish", S.JELLYFISH: "jellyfish"}.get(
            t, "finned_x_wing"
        )
    if t in (S.X_CHAIN, S.XY_CHAIN, S.AIC_CHAIN, S.NICE_LOOP):
        return out.get("pattern_key") or {S.X_CHAIN: "x_chain", S.XY_CHAIN: "xy_chain", S.NICE_LOOP: "nice_loop"}.get(
            t, "aic"
        )
    if t == S.MENTAL_D:
        sub = ctx.xm.get("subset") or 0
        return "pair_in_head" if sub == 2 else "triple_in_head" if sub == 3 else "pointing_in_head"
    if t in (
        S.LINE_D,
        S.NARY_D,
        S.SUM_COMBO,
        S.ARROW_COMBO,
        S.SET_COMBO,
        S.EQSUM_COMBO,
        S.TABLE_COMBO,
        S.SANDWICH_COMBO,
        S.XSUM_COMBO,
        S.SKYLINE_COMBO,
        S.COUNT_COMBO,
        S.LINE_RANGE,
        S.COMBO_LOCK,
    ):
        if t == S.NARY_D:
            r = _rule_from_move(ctx)
            return "cage_arithmetic" if r is not None and r.kind in ("cage", "sum") else _rule_key(r)
        if t == S.COMBO_LOCK:
            r = _rule_from_move(ctx)
            return "cage_must_contain" if r is None or r.kind in ("cage", "sum", "innie") else _rule_key(r)
        if t == S.LINE_D:
            cons = J.get("constraints") or []
            kinds = [c.get("type") for c in cons if isinstance(c, dict)]
            return _LINE_KEY.get(kinds[0], "rule_logic") if kinds else "pair_rule"
        return _rule_key(_rule_from_move(ctx))
    if t == S.PAIRARC:
        bc = J.get("base_cells") or []
        tg = [c for c, _ in ctx.elims]
        lab = rel_label(p, bc[0], tg[0]) if bc and tg else ""
        return _REL_KEY.get(lab.split(" / ")[0], "pair_rule")
    if t == S.MENTAL_CHAIN:
        return "chain_without_notes"
    if t == S.EITHER_WAY:
        return "either_way"
    if t == S.LINE_CLASS:
        return _rule_key(_rule_from_move(ctx))
    if t == S.DIGIT_COUNT:
        return "digit_counting"
    if t == S.EQUAL_DIGITS:
        return "equal_cells"
    if t == S.LINE_SCAN:
        return _rule_key(_rule_from_move(ctx))
    return "rule_logic"


# ----------------------------------------------------------- named sub-patterns --
def chain_shape(p, st, path, place=False):
    """Name the shape of a chain: Skyscraper, 2-String Kite, Turbot fish, Remote pair, W-Wing,
    X-Chain / XY-Chain / AIC. -> catalog key."""
    if any(n[0][0] == "als" for n in path):
        return "als_chain"
    if place:
        return "nice_loop"
    links = [(path[i - 1][0], path[i][0], path[i][1], path[i][2]) for i in range(1, len(path))]
    if any(lk[2] == "equal" for lk in links):
        return "x_chain" if len({n[0][1] for n in path}) == 1 else "aic"
    strong = links[0::2]
    digits = {n[0][1] for n in path}
    srcs = {s for _, _, s, _ in strong}
    if len(digits) == 1 and srcs <= {"bilocal"}:
        if len(strong) == 2:
            kinds = []
            for a, b, _, u in strong:
                ks = [p.groups[g].kind for g in p.houses if a[0] in p.groups[g].cells and b[0] in p.groups[g].cells]
                kinds.append(
                    "box"
                    if "box" in ks and not {"row", "col"} & set(ks)
                    else "row"
                    if "row" in ks
                    else "col"
                    if "col" in ks
                    else "other"
                )
            if kinds[0] == kinds[1] and kinds[0] in ("row", "col"):
                return "skyscraper"
            if {kinds[0], kinds[1]} == {"row", "col"}:
                wa, wb = links[1][0][0], links[1][1][0]
                same_box = any(
                    p.groups[g].kind == "box" and wa in p.groups[g].cells and wb in p.groups[g].cells for g in p.houses
                )
                return "two_string_kite" if same_box else "turbot_fish"
            return "turbot_fish"
        return "x_chain"
    if srcs <= {"bivalue"}:
        cells = [n[0][0] for n in path]
        pairs = {st.cand[c] for c in cells}
        if len(pairs) == 1 and len(strong) >= 3:
            return "remote_pair"
        return "xy_chain"
    if len(strong) == 3 and [s for _, _, s, _ in strong] == ["bivalue", "bilocal", "bivalue"]:
        a, z = path[0][0][0], path[-1][0][0]
        if st.cand[a] == st.cand[z] and path[0][0][1] == path[-1][0][1]:
            return "w_wing"
    return "aic"


def fish_shape(p, base, cover, fins, U):
    k = len(base)
    size = {2: "x_wing", 3: "swordfish", 4: "jellyfish"}.get(k, "jellyfish")
    lines = lambda hs: {p.groups[h].kind for h in hs}
    franken = not (
        lines(base) <= {"row"} and lines(cover) <= {"col"} or lines(base) <= {"col"} and lines(cover) <= {"row"}
    )
    if franken:  # mutant: rows and columns mixed inside the base or the cover set
        if {"row", "col"} <= lines(base) or {"row", "col"} <= lines(cover):
            return "franken_fish", "Mutant"
        return "franken_fish", "Franken"
    if not fins:
        return size, ""
    sashimi = any(len([c for c in U if c in p.groups[h].cells and c not in fins]) <= 1 for h in base)
    return {"x_wing": "finned_x_wing", "swordfish": "finned_swordfish", "jellyfish": "finned_jellyfish"}[size], (
        "Sashimi" if sashimi else "Finned"
    )


_VARIANT_LESSONS = {
    "german_whispers": "On a German whisper neighbours differ by at least 5: 5 can never appear, and digits "
    "alternate between low (1-4) and high (6-9) along the line.",
    "dutch_whispers": "Dutch whisper neighbours differ by at least 4; 5 can only sit next to 1 or 9.",
    "thermo": "Digits rise from the bulb: a cell n steps along is at least n+1, and one with m cells after it is "
    "at most 9-m. Bulbs are low, tips are high.",
    "renban": "A renban line holds a run of consecutive digits in any order: no repeats, and the length decides "
    "which runs fit.",
    "killer_combinations": "Learn the unique cage sums (3 = 1+2, 4 = 1+3, 16 = 7+9, 17 = 8+9 ...) and list a "
    "cage's possible digit sets before placing anything.",
    "rule_of_45": "Every row, column and box adds to 45: compare it with the cages inside it to find the cells "
    "poking in or out.",
    "cage_must_contain": "If every combination of a cage uses a digit and its spots in the cage share a house, the "
    "digit leaves the rest of that house.",
    "arrow": "The digits on an arrow sum to its circle: bound the circle by the smallest and largest possible "
    "arrow totals.",
    "kropki": "White dots join consecutive digits, black dots a digit and its double; a cell between two dots is "
    "very restricted.",
    "palindrome": "A palindrome line reads the same from both ends: mirrored cells hold the same digit.",
    "between": "Digits on a between line lie strictly between the two circle digits.",
    "nonconsecutive": "Orthogonal neighbours can't be consecutive, so every placed digit removes two candidates "
    "from each neighbour.",
}

SHAPE_NOTES = {
    "skyscraper": "This shape is a Skyscraper: two parallel strong links on the same digit whose ends share a "
    "line, so one of the two 'roof' cells must be the digit.",
    "two_string_kite": "This shape is a 2-String Kite: a strong link in a row and one in a column, tied together "
    "inside a box -- one of the two free ends must be the digit.",
    "turbot_fish": "This shape is a Turbot fish: a four-cell single-digit chain (strong-weak-strong).",
    "remote_pair": "This shape is a Remote pair: a chain of cells all holding the same two candidates, which "
    "alternate along the chain.",
    "w_wing": "This shape is a W-Wing: two identical two-candidate cells joined by a strong link on one of their "
    "digits, so one of them must be the other digit.",
    "xy_chain": "This is an XY-Chain: every link runs through a two-candidate cell.",
    "x_chain": "This is an X-Chain: a single digit followed through houses where it has only two places.",
    "nice_loop": "This is a discontinuous Nice Loop: the chain returns to its start with two strong links.",
}


# ------------------------------------------------------------- self-check ---
_CELL = re.compile(r"\br(\d+)c(\d+)\b")


def check(ex, step, puzzle, state):
    """Factual consistency of an explanation with the move and the grid. -> (ok, problems)."""
    p = derived(puzzle)
    st = _as_state(p, state)
    nm = Namer(p)
    probs = []
    cell_of = {nm.cell(c): c for c in range(p.N)}
    m = step.move
    text = ex["short"] + " " + ex["teach"]
    # 1. placement stated exactly in the short line
    if m.place:
        c, v = m.place
        if f"{nm.cell(c)} = {v}" not in ex["short"]:
            probs.append("placement missing from short line")
    for mm in re.finditer(r"\b(r\d+c\d+) = (\d+)", text):
        if not m.place or (cell_of.get(mm.group(1)), int(mm.group(2))) != tuple(m.place):
            if (
                not text[max(0, mm.start() - 40) : mm.start()].count("would")
                and "assum" not in text[max(0, mm.start() - 30) : mm.start()].lower()
            ):
                probs.append(f"stray placement claim {mm.group(0)}")
    # 2. eliminations: '≠' claims in the short line == the move's eliminations
    claimed = set()
    for seg in ex["short"].split(":")[0].split(";"):
        if "≠" in seg:
            cs, ds = seg.split("≠")
            for cn in _CELL.findall(cs):
                for d in ds.strip().split(","):
                    claimed.add((cell_of.get(f"r{cn[0]}c{cn[1]}"), int(d)))
    if set(m.elim) != claimed and m.elim:
        probs.append(f"elimination claims differ ({len(claimed)} vs {len(set(m.elim))})")
    # 3. 'the D in rXcY' -> placed digit claims
    for mm in re.finditer(r"\bthe (\d+) in (r\d+c\d+)", text):
        c = cell_of.get(mm.group(2))
        if c is None or st.vals[c] != int(mm.group(1)):
            probs.append(f"false placed-digit claim '{mm.group(0)}'")
    # 4. 'rXcY {a,b}' -> candidate claims (notes)
    for mm in re.finditer(r"\b(r\d+c\d+) \{([\d,]+)\}", text):
        c = cell_of.get(mm.group(1))
        ds = sum(bit(int(d)) for d in mm.group(2).split(","))
        if c is None or st.cand[c] != ds:
            probs.append(f"false candidate claim '{mm.group(0)}'")
    # 5. every cell mentioned is highlighted (target / pattern / unit cells)
    vis = set(ex["visual"]["cell_ids"])
    for u in ex["visual"]["units"]:
        vis |= set(u["cells"])
    for ln in ex["visual"]["lines"]:
        vis |= set(ln["cell_ids"])
    for gi, g in enumerate(p.groups):
        if g.kind in ("cage", "implied", "extra") and nm.unit(gi) in text:
            vis |= set(g.cells)
    for cn in set(_CELL.findall(text)):
        c = cell_of.get(f"r{cn[0]}c{cn[1]}")
        if c is None:
            probs.append(f"unknown cell r{cn[0]}c{cn[1]}")
        elif c not in vis:
            probs.append(f"cell {nm.cell(c)} mentioned but not in the visual")
    # 6. house names mentioned exist and are in the visual / contain a mentioned cell
    vis_units = {u["name"] for u in ex["visual"]["units"]}
    mentioned_cells = {cell_of.get(f"r{a}c{b}") for a, b in _CELL.findall(text)}
    for mm in re.finditer(r"\b(row|column|box) (\d+)\b", text):
        nmu = f"{mm.group(1)} {mm.group(2)}"
        gi = next((gi for gi in range(len(p.groups)) if nm.unit(gi) == nmu), None)
        if gi is None:
            probs.append(f"unknown unit {nmu}")
        elif nmu not in vis_units and not set(p.groups[gi].cells) & mentioned_cells:
            probs.append(f"unit {nmu} unrelated to the move")
    # 7. technique naming: plain name, confirmed links only, no internal codes in the text
    tinfo = ex.get("technique") or {}
    if not isinstance(tinfo, dict) or not tinfo.get("name"):
        probs.append("technique name missing")
    else:
        bad = [u for u in tinfo.get("learn_more", ()) if u.split("#")[0] not in _confirmed()]
        if bad:
            probs.append(f"unconfirmed links {bad}")
        for code in S.TECH_NAMES.values():
            if re.search(r"[a-z][A-Z(]", code) and code in text:
                probs.append(f"internal technique code '{code}' in the text")
    # 8. all targets named
    tg = {c for c, _ in m.elim} | ({m.place[0]} if m.place else set())
    for c in tg:
        if nm.cell(c) not in text:
            probs.append(f"target {nm.cell(c)} not named")
    return (not probs), probs


# ================================================== techniques 68-82 (engine records) ==
# Forcing chains, 3D Medusa, colour classes, sum bounds, class counting, dominoes and the sudokuwiki set.
# Built from the engine's explanation records (cbackend.solve(..., explain=True)): each handler states
# the move exactly in the short line and names only cells / houses that it also highlights.


def _x_units(ctx, names):
    out = []
    for n in names:
        gi = ctx.gi(n) if isinstance(n, str) else n
        if gi is not None and gi not in out:
            out.append(gi)
    return out


def _x_head(ctx):
    nm = ctx.nm
    if ctx.place:
        c, v = ctx.place
        return f"{nm.cell(c)} = {v}", f"{nm.cell(c)} must be {v}"
    by = defaultdict(list)
    for c, d in ctx.elims:
        by[c].append(d)
    goal = _join(
        [f"{nm.cell(c)} cannot be {nm.digits(ds)}" for c, ds in sorted(by.items(), key=lambda kv: nm.p.coords[kv[0]])]
    )
    return fmt_elims(nm, ctx.elims), goal


_FC_LEVEL = {
    0: "following only singles and the basic rules",
    1: "using ordinary techniques inside each case",
    -1: "following each case with simple logic for a few steps",
    -2: "following each case for a few steps with singles and the rules",
    2: "using further case splits inside each case",
}


def _h_forcing(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    p = nm.p
    tr = eng.get("trial") or {}
    opts = tr.get("options") or []
    level = -1 if ctx.tech == S.WHAT_IF else -2 if ctx.tech == S.HUMAN_CASE else ctx.tech - S.FORCING
    head, goal = _x_head(ctx)
    cells, units = set(), []
    for o in opts:
        cells.add(o["cell"])
    same_cell = len({o["cell"] for o in opts}) == 1
    same_digit = len({o["digit"] for o in opts}) == 1
    if opts and same_cell:
        intro = f"{nm.cell(opts[0]['cell'])} can only be " + nm.digits([o["digit"] for o in opts], "or")
    elif opts and same_digit:
        intro = f"the digit {opts[0]['digit']} has {len(opts)} possible places in a house: " + nm.cells(
            [o["cell"] for o in opts], "or"
        )
    elif opts:
        intro = "one of these must be true: " + _join([f"{o['rc']} is {o['digit']}" for o in opts], "or")
    else:
        intro = "a small set of cases"
    plural = lambda n, w: f"{n} {w}" + ("" if n == 1 else "s")  # noqa: E731
    targets = [ctx.place] if ctx.place else list(ctx.elims)

    def outcome(a, steps):
        """Why this surviving case leads to the conclusion (one clause)."""
        placed = {e["cell"]: e["digit"] for e in steps if e.get("cell") is not None and e.get("digit")}
        placed[a["cell"]] = a["digit"]
        if ctx.place:
            c, v = ctx.place
            if placed.get(c) == v:
                return "" if a["cell"] == c else f"{nm.cell(c)} becomes {v}"
            return goal
        why = []
        for c, d in targets:
            if c in placed and placed[c] != d:
                why.append(
                    f"{nm.cell(c)} holds {placed[c]}, not "
                    + nm.digits(sorted({dd for cc, dd in targets if cc == c}), "or")
                )
                continue
            q = next((x for x, v in placed.items() if v == d and x != c and x in p.peers[c]), None)
            if q is not None:
                why.append(f"{nm.cell(c)} sees the {d} in {nm.cell(q)}")
            else:
                why.append(f"{nm.cell(c)} loses {d}")
        return _join(list(dict.fromkeys(why)))

    parts = []
    for b in tr.get("branches") or []:
        a = b["assume"]
        steps = b.get("steps") or []
        con = b.get("contradiction")
        shown = [e for e in steps if e.get("event") in ("naked single", "hidden single") and e.get("cell") is not None][
            :3
        ]
        for e in shown:
            cells.add(e["cell"])
        seq = ", ".join(f"{e['rc']} becomes {e['digit']}" for e in shown)
        more = len(steps) - len(shown)
        chain = seq + (
            f" (then {plural(more, 'more deduction')})"
            if more > 0 and seq
            else plural(more, "deduction")
            if more > 0
            else ""
        )
        lead = f"if {a['rc']} is {a['digit']}"
        if con:
            where = ""
            if con.get("cell") is not None:
                cells.add(con["cell"])
                where = f" at {con['rc']}"
            if con.get("house"):
                units += _x_units(ctx, [con["house"]])
                gi = ctx.gi(con["house"])
                where = f" in {nm.unit(gi)}" if gi is not None else where
            what = {
                "empty cell": "a cell runs out of candidates",
                "house missing digit": "a house loses its last place for a digit",
                "rule unsatisfiable": "a rule can no longer be satisfied",
                "conflicting singles": "two forced digits clash",
            }.get(con["event"], con["event"])
            parts.append(f"{lead}: {chain + ', ' if chain else ''}then {what}{where}, so this case is impossible")
        else:
            res = outcome(a, steps)
            parts.append(
                f"{lead}: " + (f"{chain}, so {res}" if chain and res else chain or res or "nothing else is needed")
            )
    if parts:
        teach = (
            f"Case analysis ({_FC_LEVEL.get(level, '')}): {intro}. One of these cases must be true, so follow "
            f"each:\n"
            + "\n".join("- " + _cap(x) + "." for x in parts)
            + f"\nEvery case that can happen gives the same result: {goal}."
        )
    else:
        teach = f"Case analysis ({_FC_LEVEL.get(level, '')}): {intro}. Following each case shows that {goal}."
    J = _J(ctx, digits=sorted({o["digit"] for o in opts}), base_units=units, trial={"options": opts, "level": level})
    return _result(ctx, J, f"{head}: every possible case agrees", teach, bool(opts), extra_cells=cells)


def _h_nishio(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    head, goal = _x_head(ctx)
    c, v = ctx.elims[0] if ctx.elims else (None, None)
    bu = [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u]
    units = _x_units(ctx, bu)
    where = f"{nm.unit(units[0])} has no place left for it" if units else "two of its forced copies clash"
    teach = (
        f"Follow just the digit {v}: put it in {nm.cell(c)}, cross {v} out of every cell that sees it, and keep "
        f"placing {v} wherever a house has only one spot left. Then {where}, so {nm.cell(c)} cannot be {v}."
    )
    J = _J(ctx, digits=[v], base_units=units)
    return _result(
        ctx,
        J,
        f"{head}: assuming it, the {v}s run out of room",
        teach,
        True,
        extra_cells=eng.get("pattern_cells") or (),
    )


def _h_medusa(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    head, goal = _x_head(ctx)
    col = eng.get("coloring") or {}
    cs = col.get("colors") or [[], []]
    cells = {e["cell"] for c in cs for e in c}
    fmt = lambda c: ", ".join(f"{nm.cell(e['cell'])} as {e['digit']}" for e in c)  # noqa: E731
    if col.get("type") == "wrap":
        why = "one colour contradicts itself (twice in a cell or house, or it empties a cell), so all of it is false"
    else:
        why = "whichever colour is true, these candidates cannot survive (they see both colours, or share a cell with one)"
    teach = (
        f"Colour candidates in two colours along strong links (a cell with two candidates, or a digit with two "
        f"places in a house), switching colour at every link and across digits; one colour is entirely true. "
        f"Blue: {fmt(cs[0])}. Green: {fmt(cs[1])}. Here {why}: {goal}."
    )
    J = _J(ctx, digits=sorted({e["digit"] for c in cs for e in c}))
    return _result(ctx, J, f"{head}: two-colour chain over several digits", teach, bool(cells), extra_cells=cells)


def _h_colour_classes(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    same = (
        f"Colour {nm.cells(pc)} purple: they must {'both' if len(pc) == 2 else 'all'} hold the same digit (each "
        f"was shown to equal the next: an equality rule, or the only cell of a house that can take the other's "
        f"digit)"
    )
    units = _x_units(ctx, [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u])
    seed = (ctx.xm or {}).get("seed", 0)
    if seed in (2, 3):
        same = same + (
            " -- this colouring came from you" + (" (not checked against the solution)" if seed == 3 else "")
        )
    if ctx.code == "colour class (odd/even/low/high)":
        k = (ctx.xm or {}).get("class_kinds", 0)
        names = [
            n for b, n in ((1, "odd"), (2, "even"), (4, "low (1-3)"), (8, "middle (4-6)"), (16, "high (7-9)")) if k & b
        ]
        teach = f"Your colouring marks {nm.cells(pc)} as {' and '.join(names) or 'one class'} digits. So {goal}."
        J = _J(ctx)
        return _result(ctx, J, f"{head}: coloured as {' and '.join(names) or 'a class'}", teach, True, extra_cells=pc)
    if ctx.code == "label break-in (abstract digits)":
        teach = (
            f"Give every cell an abstract label for its digit (A, B, C ...): this assumes nothing. A label that "
            f"must appear in a house but has only one cell there that does not see it lands on that cell, so "
            f"cells end up sharing labels; the rules then act on whole labels (a relation between two labelled "
            f"cells relates the labels, and each house's labels are all nine digits). Following this, "
            f"{nm.cells(pc)} hold labels that cannot be some of their candidates. So {goal}."
        )
        J = _J(ctx)
        return _result(ctx, J, f"{head}: abstract-digit labels", teach, bool(pc), extra_cells=pc)
    if ctx.code == "colour bounds (order / min-max)":
        teach = (
            f"{same}. Ordering rules between colours (thermometers, inequalities) bound each colour's digit "
            f"from below and above. So {goal}."
        )
        J = _J(ctx)
        return _result(ctx, J, f"{head}: colour bounds", teach, bool(pc), extra_cells=pc)
    if ctx.code == "coloured like a solved cell":
        c, v = ctx.place
        short = f"{head}: same colour as a solved {v}"
        teach = (
            f"{nm.cell(c)} has the same colour as a cell that is already {v} -- the colouring came from you"
            + (" (not checked against the solution)" if seed == 3 else "")
            + f". Same colour, same digit: {goal}."
        )
        J = _J(ctx)
        return _result(ctx, J, short, teach, True, extra_cells=pc)
    if ctx.code in ("colour must fit every house", "colour resolved") and units:
        hu = nm.unit(units[0])
        why = (
            f"{same}. A colour appears once in every house, so {hu} needs that digit in a cell that sees none of "
            f"the coloured cells; for some digits {hu} has no such cell, so the colour cannot be them"
        )
        short = f"{head}: the colour is resolved" if ctx.place else f"{head}: the colour has no place in {hu}"
        teach = f"{why}. So {goal}."
    else:
        short = f"{head}: cells forced to be equal"
        st = ctx.st
        why = []
        for d in sorted({d for _, d in ctx.elims}):
            w = next((c for c in pc if not st.vals[c] and not (st.cand[c] >> (d - 1)) & 1), None)
            if w is None:
                w = next((c for c in pc if st.vals[c] and st.vals[c] != d), None)
            if w is not None:
                why.append(f"{nm.cell(w)} can't be {d}, so purple isn't {d}")
        teach = (
            f"{same}. Purple's digit must fit every purple cell"
            + (": " + "; ".join(why) if why else "")
            + f". So {goal}."
        )
    J = _J(ctx, base_units=units)
    return _result(ctx, J, short, teach, bool(pc), extra_cells=pc)


def _h_sum_bound(ctx):
    nm, eng, xm = ctx.nm, ctx.raw_engine, ctx.xm
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    lo, hi = xm.get("lo"), xm.get("hi")
    if ctx.code == "renban span":
        why = (
            f"a renban's digits are consecutive, so they span at most {xm.get('positions', 0) - 1}: "
            f"every digit must lie between {lo} and {hi}"
        )
    else:
        tri = (
            " (counting distinct digits: the smallest possible sum of different digits)" if xm.get("triangular") else ""
        )
        why = (
            f"the other cells of the rule add up to at least / at most what their candidates allow{tri}, so this "
            f"cell can only be {lo} to {hi}"
        )
    teach = f"Min/max bounds on {nm.cells(pc)}: {why}. So {goal}."
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: the sum bounds leave no room", teach, True, extra_cells=pc)


def _h_class_count(ctx):
    nm, eng, xm = ctx.nm, ctx.raw_engine, ctx.xm
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    units = _x_units(ctx, [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u])
    kind = xm.get("kind")
    if kind in (2, 3):
        why = (
            "the parities of a sum's digits must add up to its total's parity; every other cell's parity is "
            "already known, which fixes this one"
        )
    else:
        cls = "odd / even" if kind == 0 else "low / middle / high"
        why = (
            f"count digits by class ({cls}): {nm.unit(units[0]) if units else 'the house'} needs a fixed number of "
            f"each class, and {nm.cells(pc)} already take all of this class"
        )
    teach = f"Class counting: {why}. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: digit-class count", teach, True, extra_cells=pc)


def _h_domino(ctx):
    eng = ctx.raw_engine
    head, goal = _x_head(ctx)
    doms = eng.get("dominoes") or []
    cells = {c for d in doms for c in d["cells"]}
    units = _x_units(ctx, [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u])
    desc = "; ".join(f"{d['rc'][0]}-{d['rc'][1]} ({d['relation']})" for d in doms)
    code = ctx.code or ""
    if "black chain" in code:
        why = "the middle cell of a black-dot run needs both half and double its digit, so it must be even and small"
    elif "squeeze" in code:
        why = (
            "the middle cell's two neighbours see each other, so they need two different digits that both fit "
            "the rule with it"
        )
    elif "pair lock" in code:
        why = "the two dominoes can only be filled with the same four digits, which they lock in their house"
    else:
        why = "every allowed filling of the domino uses this digit, so it goes from the cells seeing both ends"
    teach = f"Domino logic on {desc}: {why}. So {goal}."
    J = _J(ctx, base_units=units)
    return _result(ctx, J, f"{head}: domino pairs", teach, bool(cells), extra_cells=cells)


def _h_pattern_named(name_text, lesson):
    def h(ctx):
        nm, eng = ctx.nm, ctx.raw_engine
        head, goal = _x_head(ctx)
        pc = eng.get("pattern_cells") or []
        teach = f"{lesson} Pattern cells: {nm.cells(pc)}. So {goal}."
        J = _J(ctx, base_cells=pc)
        return _result(ctx, J, f"{head}: {name_text}", teach, bool(pc), extra_cells=pc)

    return h


def _h_mental_notes(ctx):
    nm, eng, xm = ctx.nm, ctx.raw_engine, ctx.xm
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    via = S.TECH_NAMES.get(xm.get("via_technique"), "a notes technique")
    via_name = CONCEPTS.get(xm.get("via_technique"), (via, ""))[0]
    teach = (
        f"Without writing notes: keep in mind which digits each cell can still take, apply a {via_name.lower()} "
        f"on those mental candidates (cells {nm.cells(pc)}), and the result is a single: {goal}."
    )
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: a single after notes logic in the head", teach, True, extra_cells=pc)


def _h_rule_intersect(ctx):
    eng = ctx.raw_engine
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    base = eng.get("base") or {}
    names = [u["name"] for u in base.get("units") or [] if u and u.get("name")]
    for r in base.get("rules") or []:
        nm_ = r.get("name") or (f"{r.get('kind')} line" if r.get("type") == "line" else r.get("type"))
        names.append(str(nm_))
    what = " and ".join(names) if names else "two rules"
    units = _x_units(ctx, [u["name"] for u in base.get("units") or [] if u])
    if ctx.code == "two houses with their dots":
        why = (
            f"{what} overlap, and the pair rules (dots, lines) between their cells leave only a few ways to fill "
            f"the shared cells"
        )
    else:
        why = (
            f"take {what} together: list the digit combinations that satisfy both at once over their {len(pc)} "
            f"open cells (digits that see each other differ, a house still needs its missing digits)"
        )
    teach = f"{_cap(why)}. Some candidates appear in none of them. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: {what} together", teach, bool(pc), extra_cells=pc)


def _h_sum_algebra(ctx):
    eng, xm = ctx.raw_engine, ctx.xm or {}
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    base = eng.get("base") or {}
    hn = [u["name"] for u in base.get("units") or [] if u and u.get("name")]
    units = _x_units(ctx, hn)
    k = len(hn) or xm.get("houses", 1)
    tot = 45 * k if ctx.p.D == 9 else None
    region = " and ".join(hn) if hn else "these houses"
    why = (
        f"{region} add up to {tot if tot else 'a known total'} together. The rules inside them (cages, line "
        f"segments, arrows) account for part of that total, and the other cells can only add up to what their "
        f"smallest / largest different digits allow. Comparing the two bounds pins down the sums"
        + (f" (after {xm.get('rounds')} rounds of bounds)" if (xm.get("rounds") or 0) > 1 else "")
    )
    teach = f"{why}. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: the maths of {region}", teach, bool(pc), extra_cells=pc)


def _band_equation(ctx, house_names, cage_names):
    """The derived sum that best summarises a band move: a union of disjoint houses (parallel lines, or
    boxes) minus the sum cages inside it -> what the remaining cells add up to (fewest remaining cells)."""
    p = ctx.p
    groups = {}
    for n in house_names + cage_names:
        gi = ctx.gi(n)
        if gi is not None:
            groups[n] = p.groups[gi]
    houses = [n for n in house_names if n in groups and groups[n].complete]
    cages = [(n, groups[n]) for n in cage_names if n in groups and groups[n].total is not None]
    if not cages or not houses:
        return None
    ht = p.D * (p.D + 1) // 2
    best = None
    from itertools import combinations

    for k in range(1, min(3, len(houses)) + 1):
        for hs in combinations(houses, k):
            cells = [c for h in hs for c in groups[h].cells]
            if len(set(cells)) != len(cells):
                continue  # overlapping houses
            u = set(cells)
            inside = [(n, g) for n, g in cages if set(g.cells) <= u]
            if not inside:
                continue
            rest = u - {c for _, g in inside for c in g.cells}
            tot = ht * k - sum(g.total for _, g in inside)
            key = (len(rest), k)
            if rest and (best is None or key < best[0]):
                best = (key, hs, inside, rest, tot)
    if best is None:
        return None
    _, hs, inside, rest, tot = best
    hn = " and ".join(hs)
    cn = " + ".join(f"{n} ({g.total})" for n, g in inside)
    return (
        f"{hn} add up to {ht * len(hs)}; the cages inside, {cn}, take {sum(g.total for _, g in inside)}, so the "
        f"other {len(rest)} cells add up to {tot}"
    )


def _h_band_logic(ctx):
    eng, xm = ctx.raw_engine, ctx.xm or {}
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    base, cover = eng.get("base") or {}, eng.get("cover") or {}
    hn = [u["name"] for u in base.get("units") or [] if u and u.get("name")]
    cn = [u["name"] for u in cover.get("units") or [] if u and u.get("name")]
    rn = []
    for r in base.get("rules") or []:
        rn.append(str(r.get("name") or (f"{r.get('kind')} line" if r.get("type") == "line" else r.get("type"))))
    units = _x_units(ctx, hn + cn)
    region = " and ".join(hn) if hn else "this band"
    rules = cn + rn
    what = (" with " + ", ".join(rules[:6]) + (" ..." if len(rules) > 6 else "")) if rules else ""
    eq = _band_equation(ctx, hn, cn)
    lv, cases = xm.get("level"), xm.get("cases")
    if lv == 0:
        how = "this follows directly, without trying cases"
    elif lv == 1:
        how = f"trying the {cases} options of one cell, every one breaks a rule"
    elif lv == 2:
        how = f"it takes a longer case analysis ({cases} cases) to see it"
    else:
        how = None
    why = (
        f"take {region}{what} together"
        + (f": {eq}" if eq else ": the house totals and the rules inside fix what the other cells can add up to")
        + f". Together with the digits each house still needs, some candidates fit no filling of these {len(pc)} "
        f"open cells" + (f" -- {how}" if how else "")
    )
    teach = f"{_cap(why)}. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: {region}{what} together", teach, bool(pc), extra_cells=pc)


def _h_snyder(ctx):
    nm = ctx.nm
    head, goal = _x_head(ctx)
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    if ctx.code == "Snyder X-wing":
        why = (
            f"the Snyder marks of one digit sit in two boxes on the same two lines ({nm.cells(pc)}): the digit's "
            f"two places in those lines are used up there, so it leaves those lines in the third box"
        )
    elif ctx.code == "Snyder hidden triple":
        why = (
            f"three digits have all their Snyder marks inside the same three cells of a box ({nm.cells(pc)}): those "
            f"cells hold just these three digits"
        )
    else:
        why = (
            f"two digits have their Snyder marks on the same two cells of a box ({nm.cells(pc)}): those cells hold "
            f"just that pair"
        )
    teach = (
        f"With Snyder marks (corner marks for digits confined to two{' or three' if ctx.code == 'Snyder hidden triple' else ''} "
        f"cells of a box), {why}. So {goal}."
    )
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: from Snyder marks", teach, bool(pc), extra_cells=pc)


def _h_combo_positions(ctx):
    """ComboPositions: a cage's valid fillings put at most m digits of a set Q into the part of the cage inside a
    house, so the rest of Q lies in the house outside the cage -- where only that many cells can take them."""
    nm, p = ctx.nm, ctx.p
    xm = ctx.xm or {}
    kg, hi, mask, mq, need = (
        xm.get("cage"),
        xm.get("house"),
        xm.get("digit_mask", 0),
        xm.get("max_in_cage"),
        xm.get("need_outside"),
    )
    if kg is None or hi is None or not mask:
        return _generic(ctx)
    Q = [d for d in range(1, p.D + 1) if mask >> (d - 1) & 1]
    g = p.groups[kg]
    tot = getattr(g, "total", None)
    qs = nm.digits(Q, "and")
    cells = sorted({c for c, _ in ctx.elims})
    most = {0: "none of", 1: "at most one of", 2: "at most two of"}.get(mq, f"at most {mq} of")
    teach = (
        f"The {tot} cage ({nm.cells(sorted(g.cells))}) can be filled only in a few ways, and every way puts {most} "
        f"{qs} into its cells in {nm.unit(hi)}. So {nm.unit(hi)} needs {'that digit' if need == 1 else f'{need} of them'} "
        f"outside the cage, and only {nm.cells(cells)} can take {'it' if need == 1 else 'them'}: "
        f"{'it holds' if len(cells) == 1 else 'they hold'} only {qs}. So {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(ctx, digits=Q, base_units=[hi], base_cells=sorted(g.cells), cover_cells=cells)
    return _result(
        ctx, J, f"{fmt_elims(nm, ctx.elims)}: the {tot} cage holds {most} {qs} in {nm.unit(hi)}", teach, True
    )


def _h_clique_house(ctx):
    """CliqueHouse: cells that pairwise must differ act as a house; |K| cells with |K| candidates hold each once."""
    nm, p = ctx.nm, ctx.p
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    mask = (ctx.xm or {}).get("digit_mask", 0)
    U = [d for d in range(1, p.D + 1) if mask >> (d - 1) & 1]
    head, goal = _x_head(ctx)
    why = (
        f"{_cap(nm.cells(pc))} all have to be different from each other -- each pair shares a house or a rule "
        f"that forbids equal digits -- so together they work like a house. Between them they can only hold "
        f"{nm.digits(U, 'and')}: {len(pc)} cells, {len(U)} digits, so each of these digits is in them exactly once"
    )
    tail = (
        f". {_cap(goal)}."
        if ctx.place
        else f", and any cell that has to differ from all of them loses those digits. So {goal}."
    )
    J = _J(ctx, digits=U, base_cells=pc)
    return _result(
        ctx, J, f"{head}: a virtual house of {len(pc)} different cells", why + tail, bool(pc), extra_cells=pc
    )


def _h_line_sets(ctx):
    """LineSets: renbans meeting one house must use different digits there; their consecutive runs, chosen
    jointly, leave some digits impossible."""
    nm = ctx.nm
    hi = (ctx.xm or {}).get("house")
    nl = (ctx.xm or {}).get("lines", 2)
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    head, goal = _x_head(ctx)
    hn = nm.unit(hi) if hi is not None else "a house"
    teach = (
        f"{nl} renban lines pass through {hn}. Each holds a run of consecutive digits, and inside {hn} the lines "
        f"must use different digits. Trying the runs each line can still take, together, no combination puts "
        f"these digits where they are pencilled. So {goal}."
    )
    J = _J(ctx, base_units=[hi] if hi is not None else [], base_cells=pc)
    return _result(ctx, J, f"{head}: renban digit sets in {hn}", teach, bool(pc), extra_cells=pc)


def _h_line_clues(ctx):
    """LineClues: a row / column with several outside clues, its possible fillings checked against all of them."""
    nm = ctx.nm
    hi = (ctx.xm or {}).get("house")
    nclue = (ctx.xm or {}).get("clues", 2)
    head, goal = _x_head(ctx)
    hn = nm.unit(hi) if hi is not None else "this line"
    teach = (
        f"{_cap(hn)} has {nclue} clues outside the grid. Take them together: every way to fill {hn} that fits one "
        f"clue must fit the others too (overlapping or touching segments share their digits). No filling that "
        f"satisfies all of them puts these digits where they are pencilled. So {goal}."
    )
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    J = _J(ctx, base_units=[hi] if hi is not None else [], base_cells=pc)
    return _result(ctx, J, f"{head}: the clues of {hn} together", teach, bool(pc), extra_cells=pc)


def _h_weighted_sums(ctx):
    """WeightedSums: sum facts (houses, cages, sum rules, arrows, equal sums) added / subtracted with small
    multiples until only a few cells remain, some counted more than once."""
    xm = ctx.xm or {}
    head, goal = _x_head(ctx)
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    k, nf, mw = xm.get("total"), xm.get("facts", 2), xm.get("max_weight", 1)
    times = {2: "twice", 3: "three times"}.get(mw, f"{mw} times") if mw and mw > 1 else None
    teach = (
        f"Add up {nf} sum facts (whole houses add to 45; cages, sum lines and arrows give their totals), some of "
        f"them more than once or subtracted, so that almost every cell cancels"
        + (f" and the cells left are counted up to {times}" if times else "")
        + f". What remains is a short sum equal to {k} (after the placed digits), and only some digits fit it. "
        f"So {goal}."
    )
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: weighted sum of {nf} facts", teach, bool(pc), extra_cells=pc)


def _h_fireworks(ctx):
    """Fireworks (sudokuwiki): three digits each confined to a cell X, one cell A of X's row outside X's box and one
    cell B of X's column outside it -> A, B, X hold exactly those digits."""
    nm, p = ctx.nm, ctx.p
    xm = ctx.xm or {}
    x, a, b, mask, bx = xm.get("cell_x"), xm.get("cell_a"), xm.get("cell_b"), xm.get("digit_mask", 0), xm.get("region")
    if x is None or a is None or b is None:
        return _generic(ctx)
    ds = [d for d in range(1, p.D + 1) if mask >> (d - 1) & 1]
    row = next((g for g in p.groups_of[x] if p.groups[g].kind == "row"), None)
    col = next((g for g in p.groups_of[x] if p.groups[g].kind == "col"), None)
    box = nm.unit(bx) if bx is not None else "its box"
    dl = nm.digits(ds, "and")
    teach = (
        f"Look at {nm.unit(row)} and {nm.unit(col)}, which cross at {nm.cell(x)} in {box}. Outside {box}, "
        f"{dl} can go only in {nm.cell(a)} in the row and only in {nm.cell(b)} in the column. So each of these "
        f"digits is in {nm.cell(a)}, in {nm.cell(b)} or in {nm.cell(x)}: if it is in neither {nm.cell(a)} nor "
        f"{nm.cell(b)}, the row's copy and the column's copy are both inside {box}, which holds only one, so "
        f"it is where they cross, {nm.cell(x)}. Three digits for three cells: {nm.cells([a, b, x])} hold exactly "
        f"{dl}, so {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(
        ctx,
        digits=ds,
        base_units=[g for g in (row, col) if g is not None],
        cover_units=[bx] if bx is not None else [],
        base_cells=[a, b, x],
    )
    return _result(ctx, J, f"{fmt_elims(nm, ctx.elims)}: fireworks on {dl} ({nm.cells([a, b, x])})", teach, True)


def _h_chute_rp(ctx):
    """Chute Remote Pairs: bivalue cells A, B = {x, y} in one band / stack, different boxes and lines; the third
    box's cells on the remaining line hold no x -> A or B is y -> y leaves the cells that see both."""
    nm, xm = ctx.nm, ctx.xm or {}
    a, b, absent = xm.get("cell_a"), xm.get("cell_b"), xm.get("absent")
    if a is None or b is None or not absent:
        return _h_pattern_named(
            "chute remote pairs",
            "Two identical pairs in one band, in different boxes and lines: "
            "if the third box's segment has no x, one of them is y.",
        )(ctx)
    st = ctx.st
    pair = [d for d in range(1, nm.p.D + 1) if (st.cand[a] >> (d - 1)) & 1]
    y = next((d for d in pair if d != absent), None)
    pc = [c for c in (ctx.raw_engine.get("pattern_cells") or []) if c not in (a, b)]
    (ra, ca), (rb, cb_) = nm.p.coords[a], nm.p.coords[b]
    chute = ("band" if ra // 3 == rb // 3 else "stack" if ca // 3 == cb_ // 3 else "chute") if nm.p.D == 9 else "chute"
    teach = (
        f"{nm.cell(a)} and {nm.cell(b)} both hold {nm.digits(pair, 'or')} and sit in the same {chute}, in different "
        f"boxes and different lines. If neither were {y}, both would be {absent}, and the third box of the {chute} would "
        f"need its {absent} on the one remaining line" + (f" ({nm.cells(pc)})" if pc else "") + f" -- but {absent} "
        f"can't go there. So at least one of them is {y}, and cells seeing both lose {y}: {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(ctx, digits=pair, base_cells=[a, b], cover_cells=pc)
    return _result(
        ctx,
        J,
        f"{fmt_elims(nm, ctx.elims)}: chute remote pairs {nm.cell(a)}-{nm.cell(b)}",
        teach,
        True,
        extra_cells=set(pc) | {a, b},
    )


def _changed_cells(ctx):
    """the cells a move places or eliminates in, in grid order (when the engine names no pattern cells)"""
    cells = {c for c, _ in ctx.elims} | ({ctx.place[0]} if ctx.place else set())
    return sorted(cells, key=lambda c: ctx.nm.p.coords[c])


def _h_clue_facts(ctx):
    """ClueFacts / ClueShape: digits ruled out by the clues alone, before any digit of the grid is used (a thermometer
    cell's range, no 5 on a German whisper, a dot pair's digits; the shape form adds partners on one rule in one house)."""
    nm = ctx.nm
    pc = (ctx.raw_engine or {}).get("pattern_cells") or _changed_cells(ctx)
    head, goal = _x_head(ctx)
    if ctx.tech == S.CLUE_SHAPE:
        why = (
            f"Read the rules on {nm.cells(pc)} with the houses they cross: cells of one rule that share a house must hold "
            "different digits, and the rule leaves too few digits for that"
        )
        title = "the clues' shape"
    else:
        why = (
            f"Look at the rules on {nm.cells(pc)} alone, before any digit is placed: where a cell sits on its rule limits "
            "what it can hold (a thermometer cell needs room for the cells above and below it, a German whisper cell "
            "cannot be 5, a dot pair only takes certain digits)"
        )
        title = "the clues alone"
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: {title}", f"{why}. So {goal}.", bool(pc), extra_cells=pc)


def _h_class_colour(ctx):
    """ClassColouring: rule links that always join a low and a high digit (or an odd and an even one) colour cells in
    two classes; a known cell or a house's count of each class fixes the colours."""
    nm = ctx.nm
    xm = ctx.xm or {}
    pc = (ctx.raw_engine or {}).get("pattern_cells") or _changed_cells(ctx)
    D = nm.p.D
    if xm.get("kind", 0) == 0:
        a, b = (
            f"low (1–{D // 2})",
            f"high ({D - D // 2 + 1}–{D})",
        )
    else:
        a, b = "odd", "even"
    head, goal = _x_head(ctx)
    base = (
        f"The rules linking {nm.cells(pc)} always join a {a.split()[0]} digit to a {b.split()[0]} one (or always two of "
        f"the same kind), so these cells split into two colours: one colour is {a}, the other {b}"
    )
    why = {
        0: ", and a cell whose digit is already known says which colour is which",
        1: ", and counting fixes which is which: a house holds only so many digits of each kind",
        2: "; either way round, the coloured cells fill a house's share of one kind, so the house's other cells cannot "
        "have it",
    }.get(xm.get("why"), "")
    J = _J(ctx, base_cells=pc)
    return _result(
        ctx,
        J,
        f"{head}: {a.split()[0]} / {b.split()[0]} colouring",
        f"{base}{why}. So {goal}.",
        bool(pc),
        extra_cells=pc,
    )


_X_HANDLERS = {
    "CLUE_FACTS": (
        _h_clue_facts,
        "clue_facts",
        "intersections+combos",
        ("Clue facts", "Some digits are ruled out by the clues alone, before any digit of the grid is used."),
    ),
    "CLUE_SHAPE": (
        _h_clue_facts,
        "clue_shape",
        "intersections+combos",
        (
            "Clue shape",
            "Cells of one rule that share a house need different digits; when the rule leaves too few, some go.",
        ),
    ),
    "CLASS_COLOUR": (
        _h_class_colour,
        "class_colouring",
        "chains",
        (
            "Low / high and odd / even colouring",
            "Rules that always join a low and a high digit (or an odd and an even one) colour cells in two classes; a "
            "known cell or a house's count fixes which colour is which.",
        ),
    ),
    "WEIGHTED_SUMS": (
        _h_weighted_sums,
        "weighted_sums",
        "intersections+combos",
        (
            "Weighted sums",
            "Add and "
            "subtract whole houses and rule totals, counting some cells more than once, until a short sum "
            "remains.",
        ),
    ),
    "LINE_CLUES": (
        _h_line_clues,
        "outside_clues_together",
        "subsets",
        ("Outside clues together", "A line with clues at both ends: its fillings must satisfy every clue at once."),
    ),
    "LINE_SETS": (
        _h_line_sets,
        "renban_sets",
        "subsets",
        (
            "Renban sets",
            "Renbans meeting in a house use different "
            "digits there; their possible runs, taken together, rule digits out.",
        ),
    ),
    "CLIQUE_HOUSE": (
        _h_clique_house,
        "clique_house",
        "subsets",
        (
            "Clique house",
            "Cells that must all differ from "
            "each other act like a house: as many cells as digits means each digit once.",
        ),
    ),
    "COMBO_POS": (
        _h_combo_positions,
        "combo_positions",
        "subsets",
        (
            "Cage combination positions",
            "A cage's possible "
            "combinations limit how many digits of a small set it can hold in a house; the rest must go elsewhere.",
        ),
    ),
    "HUMAN_CASE": (
        _h_forcing,
        "case_analysis",
        "chains",
        (
            "Case analysis",
            "Try a digit (or each option of a cell or "
            "of a digit in a house) and follow it a few steps with singles and the rules; a case that breaks is "
            "false, and what every surviving case agrees on is true.",
        ),
    ),
    "FIREWORKS": (
        _h_fireworks,
        "fireworks",
        "fish+wings",
        (
            "Fireworks",
            "A digit with one spot in a row and one in a "
            "column outside the box where they cross must be in one of those spots or the crossing cell; three "
            "such digits fill the three cells.",
        ),
    ),
    "BAND_LOGIC": (
        _h_band_logic,
        "band_logic",
        "chains",
        (
            "Band logic",
            "Take a band's rows (or columns), its "
            "boxes and the rules inside together: house totals minus the cages fix sums of the other cells, "
            "and only fillings consistent with all of them remain.",
        ),
    ),
    "SNYDER_D": (
        _h_snyder,
        "snyder_single",
        "intersections+combos",
        (
            "Snyder marks",
            "Mark only digits confined "
            "to two cells of a box; coinciding pairs and aligned pairs give placements without full notes.",
        ),
    ),
    "SUM_ALGEBRA": (
        _h_sum_algebra,
        "sum_algebra",
        "intersections+combos",
        (
            "Sum algebra",
            "Add up whole houses (45 each) and compare with the totals of the rules inside them; the "
            "difference bounds the remaining cells or the rules' sums.",
        ),
    ),
    "RULE_INTERSECT": (
        _h_rule_intersect,
        "rule_intersection",
        "intersections+combos",
        (
            "Rules together",
            "Take two overlapping rules (or a rule and a house) together: only digit combinations that "
            "satisfy both remain.",
        ),
    ),
    "MULTI_COLOR": (
        _h_pattern_named(
            "multi-colouring",
            "Two separate colourings of the same digit (each along "
            "conjugate pairs) touch: one colour of the first sees one colour of the second, so they are not both "
            "true and one of their opposites is; cells seeing both opposites lose the digit.",
        ),
        "multi_colouring",
        "chains",
        (
            "Multi-Colouring",
            "Colour two separate conjugate-pair networks of a digit and use how their colours see each other.",
        ),
    ),
    "WHAT_IF": (
        _h_forcing,
        "what_if",
        "trial",
        (
            "What if",
            "Try both options of a two-way choice with simple logic "
            "(singles, rule arithmetic, intersections); a case that breaks drops, a conclusion both share holds.",
        ),
    ),
    "MENTAL_NOTES": (
        _h_mental_notes,
        "notes_in_head",
        "subsets",
        (
            "Notes in your head",
            "Do a pair, pointing or "
            "combination step on the candidates you keep in mind, then place the single it leaves.",
        ),
    ),
    "FORCING": (
        _h_forcing,
        "forcing_chain",
        "trial",
        (
            "Forcing Chain",
            "Try every option of a cell or every place of "
            "a digit in a house; whatever all surviving options agree on is true.",
        ),
    ),
    "DYN_FORCING": (
        _h_forcing,
        "dynamic_forcing_chain",
        "trial",
        (
            "Dynamic Forcing Chain",
            "Case analysis where each case is followed with ordinary techniques, not only singles.",
        ),
    ),
    "NESTED_FORCING": (
        _h_forcing,
        "nested_forcing_chain",
        "trial",
        (
            "Nested Forcing Chain",
            "Case analysis whose cases use further case analyses inside them -- a computer-strength technique.",
        ),
    ),
    "NISHIO": (
        _h_nishio,
        "nishio_forcing_net",
        "trial",
        (
            "Nishio Forcing Net",
            "Assume one digit in a cell and follow "
            "only that digit; if it runs out of places, the assumption was false.",
        ),
    ),
    "MEDUSA": (
        _h_medusa,
        "3d_medusa",
        "chains",
        (
            "3D Medusa",
            "Colouring across several digits: bivalue cells and two-place digits form one two-coloured network.",
        ),
    ),
    "COLOUR_ALGEBRA": (
        _h_colour_classes,
        "colour_algebra",
        "chains",
        (
            "Equal-digit colouring",
            "Cells forced to be equal share one colour; the colour's possible digits are what all its cells allow.",
        ),
    ),
    "SUM_BOUND": (
        _h_sum_bound,
        "sum_bounds",
        "intersections+combos",
        (
            "Min/max bounds",
            "Smallest and largest "
            "possible sums (triangular numbers for different digits) bound each cell of a sum rule.",
        ),
    ),
    "CLASS_COUNT": (
        _h_class_count,
        "class_counting",
        "intersections+combos",
        ("Odd/even counting", "Count digits by class (odd/even, low/high): houses need fixed numbers of each."),
    ),
    "DOMINO": (
        _h_domino,
        "domino_logic",
        "intersections+combos",
        (
            "Domino logic",
            "Reason about pairs of cells "
            "joined by a dot or sum clue: which digit pairs fit, and what they force nearby.",
        ),
    ),
    "N_WING": (
        _h_pattern_named(
            "bent set wing",
            "A wing of several cells holding exactly as many digits: all digits "
            "but one are confined to cells that see each other, so the last one is forced into the wing.",
        ),
        "wxyz_wing",
        "fish+wings",
        ("WXYZ-Wing", "Bent sets of 4+ cells generalising XY- and XYZ-Wings."),
    ),
    "SUE_DE_COQ": (
        _h_pattern_named(
            "Sue de Coq",
            "Box-line intersection cells plus a line group and a box group "
            "with disjoint digits lock as many digits as cells.",
        ),
        "sue_de_coq",
        "fish+wings",
        ("Sue de Coq", "Two-sector disjoint subsets around a box-line intersection."),
    ),
    "APE": (
        _h_pattern_named(
            "aligned pair exclusion",
            "Every combination of the two cells' digits is checked; a "
            "digit with no combination that leaves the cells seeing both alive goes.",
        ),
        "aligned_pair_exclusion",
        "fish+wings",
        ("Aligned Pair Exclusion", "Test the value pairs of two cells against the cells they both see."),
    ),
    "CHUTE_RP": (
        _h_chute_rp,
        "chute_remote_pairs",
        "chains",
        ("Chute Remote Pairs", "Remote pairs inside a band or stack."),
    ),
    "POM": (
        _h_pattern_named(
            "pattern overlay",
            "Every placement pattern of this digit (one per row, column and box) "
            "consistent with the candidates was listed; these candidates are in none of them.",
        ),
        "pattern_overlay",
        "trial",
        ("Pattern Overlay", "List all templates of a digit and keep only cells some template uses."),
    ),
    "GURTH": (
        _h_pattern_named(
            "symmetry",
            "The givens are symmetric under a grid symmetry with a digit swap, so the "
            "unique solution is too; candidates breaking the symmetry go.",
        ),
        "gurth",
        "fish+wings",
        ("Gurth's Theorem", "Symmetric placement: a symmetric puzzle has a symmetric solution."),
    ),
}

for _code, (_h, _key, _fam, _concept) in _X_HANDLERS.items():
    HANDLERS[getattr(S, _code)] = _h
    CONCEPTS.setdefault(getattr(S, _code), _concept)
    EXTRA_FAMILY.setdefault(getattr(S, _code), _fam)

_FAM_IDX = {"singles": 0, "intersections+combos": 1, "subsets": 2, "fish+wings": 3, "chains": 4, "ALS": 5, "trial": 6}
for _code, (_h, _key, _fam, _concept) in _X_HANDLERS.items():
    CATALOG.setdefault(_key, (_concept[0], {"other": []}, _FAM_IDX[_fam], [], []))
CATALOG["forcing_chain"][1]["sudokuwiki"] = ["Cell Forcing Chains", "Unit Forcing Chains"]
CATALOG["forcing_chain"][3].extend([SW + "Cell_Forcing_Chains", SW + "Unit_Forcing_Chains"])
CATALOG["dynamic_forcing_chain"][1]["HoDoKu"] = ["Dynamic Forcing Chain"]
CATALOG["nested_forcing_chain"][1]["Sudoku Snake"] = ["Dynamic Unit Nested Forcing Chains II"]
CATALOG["nishio_forcing_net"][3].append(SW + "Nishio_Forcing_Chains")
CATALOG["3d_medusa"][1]["sudokuwiki"] = ["3D Medusa"]
CATALOG["3d_medusa"][3].append(SW + "3D_Medusa")
CATALOG["sue_de_coq"][3].append(SW + "Sue_de_Coq")
CATALOG["fireworks"][1]["sudokuwiki"] = ["Fireworks"]
CATALOG["fireworks"][3].append(SW + "Fireworks")
CATALOG["aligned_pair_exclusion"][3].append(SW + "Aligned_Pair_Exclusion")
CATALOG["wxyz_wing"][3].append(SW + "WXYZ_Wing")
CATALOG["pattern_overlay"][3].append(SW + "Pattern_Overlay")
CATALOG["chute_remote_pairs"][3].append(SW + "Chute_Remote_Pairs")
CATALOG["gurth"][3].append(SW + "Gurths_Theorem")
CATALOG["multi_colouring"][1]["sudokuwiki"] = ["Multi-Colouring"]
CATALOG["multi_colouring"][3].append(SW + "Multi_Colouring")


def _h_empty_rect(ctx):
    """Empty Rectangle: a box whose candidates for d lie on one row + one column of it, a conjugate pair on a
    line through the box's column (or row), and the cell where the pair's other end and the box's row meet."""
    nm = ctx.nm
    ch = (ctx.raw_engine or {}).get("chain") or []
    if len(ch) != 4 or not ctx.elims or "group" not in ch[1] or "cell" not in ch[0] or "cell" not in ch[3]:
        return _h_chain(ctx)
    d = ch[0]["digit"]
    a, grp, c, e = ch[0]["cell"], ch[1]["group"], ch[2].get("cell"), ch[3]["cell"]
    box_g, line_g = ctx.gi(ch[1].get("via")), ctx.gi(ch[3].get("via"))
    if box_g is None or line_g is None or c is None:
        return _h_chain(ctx)
    box, pair_line = nm.unit(box_g), nm.unit(line_g)
    tgt = sorted({x for x, _ in ctx.elims})
    in_box = sorted([a] + list(grp), key=lambda x: nm.p.coords[x])
    teach = (
        f"In {box}, the {d}s can only go in {nm.cells(in_box, 'or')}: all on one row and one column of the box "
        f"(the rest of the box is an 'empty rectangle'). {_cap(pair_line)} has only two places for {d}: "
        f"{nm.cell(c)} and {nm.cell(e)}. If {nm.cell(e)} is not {d}, then {nm.cell(c)} is, which removes {d} from "
        f"{nm.cells(sorted(grp))} (they see {nm.cell(c)}), so {box}'s {d} must be {nm.cell(a)}. "
        f"Either {nm.cell(e)} or {nm.cell(a)} holds {d}, and {nm.cells(tgt)} "
        f"{'sees' if len(tgt) == 1 else 'see'} both, so {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(ctx, digits=[d], base_units=[box_g], cover_units=[line_g], base_cells=in_box, cover_cells=[c, e])
    return _result(
        ctx,
        J,
        f"{fmt_elims(nm, ctx.elims)}: empty rectangle in {box} with the pair {nm.cell(c)}-{nm.cell(e)}",
        teach,
        True,
        extra_cells=set(in_box) | {c, e},
    )


HANDLERS[S.REMOTE_PAIRS] = _h_chain
HANDLERS[S.EMPTY_RECT] = _h_empty_rect
CONCEPTS.setdefault(
    S.REMOTE_PAIRS,
    (
        "Remote Pairs",
        "A chain of cells holding the same pair: alternate cells "
        "take alternate digits, so a cell seeing both ends of an odd-length run "
        "loses both digits.",
    ),
)
CONCEPTS.setdefault(
    S.EMPTY_RECT,
    (
        "Empty Rectangle",
        "A box whose candidates for a digit form a cross works "
        "as one end of a strong link; with a conjugate pair it removes the digit "
        "where the two meet.",
    ),
)
EXTRA_FAMILY.setdefault(S.REMOTE_PAIRS, "chains")
EXTRA_FAMILY.setdefault(S.EMPTY_RECT, "chains")

_technique_key_base = _technique_key


def _technique_key(ctx, out):  # noqa: F811 -- extended for 68-82 and the new codes
    for _code, (_h, _key, _fam, _concept) in _X_HANDLERS.items():
        if ctx.tech == getattr(S, _code, -99):
            return _key
    if ctx.tech == S.EMPTY_RECT or (ctx.tech == S.X_CHAIN and ctx.code == "ER"):
        return "empty_rectangle"
    if ctx.tech == S.REMOTE_PAIRS:
        return "remote_pair"
    if ctx.tech == S.X_CHAIN and ctx.code == "TUR":
        return "turbot_fish"
    if ctx.tech == S.LOL_COMBO and ctx.code in ("PHI", "Phistomefel variant"):
        return "phistomefel_ring" if ctx.code == "PHI" else "phistomefel_variant"
    return _technique_key_base(ctx, out)
