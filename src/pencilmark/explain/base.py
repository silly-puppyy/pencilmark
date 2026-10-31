"""Shared vocabulary of the explainer: tables, naming (Namer), contexts (Ctx), result helpers. (split from explain.py)"""

from __future__ import annotations

import re
import zlib
from collections import defaultdict

from .. import solver as S
from ..model import bit, digits_of

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
        from ..cbackend import detect_lines

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


def _an(text):
    """'a 8' -> 'an 8' (also 11, 18)."""
    text = re.sub(r"\b([Aa]) (8|11|18)\b", lambda m: m.group(1) + "n " + m.group(2), text)
    return re.sub(r"\b([Aa]) (X-|XY-|XYZ-|ALS|AIC|X=)", lambda m: m.group(1) + "n " + m.group(2), text)


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
