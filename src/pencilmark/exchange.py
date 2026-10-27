"""The "sudoku-puzzle" exchange format, format_version 1 (docs/FORMAT.md): engine Puzzle <-> exchange dict.

    write(p, meta=None, solution=None) -> dict          engine Puzzle -> canonical sudoku-puzzle dict
    to_internal(doc) -> dict                            sudoku-puzzle dict -> puzzle JSON (pencilmark.puzzle_json)
    read(doc) -> Puzzle                                 sudoku-puzzle dict -> engine Puzzle (not finalized)
    validate(doc)                                       strict reading checks (FORMAT.md section 4); raises FormatError
    dumps(doc, pretty=True) -> str                      canonical JSON text (FORMAT.md 8.1)
    fingerprint(doc) -> "sha256:..."                    content fingerprint (FORMAT.md 8.2)

The format is a transport layer: read(write(p)) builds the same engine structure as p (groups in order, relations and
constraints in order, domains, givens, coordinates), except for the normalisations listed in docs/ENGINE.md (each
mechanic gets ONE engine expansion). The writer therefore works from the engine structure directly and keeps the order of
relations and constraints (the order changes cards).
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections import Counter

from . import model as M, puzzle_json as PJ

FORMAT = "sudoku-puzzle"
FORMAT_VERSION = 1
SCHEMA_URL = "https://silly-puppyy.github.io/pencilmark/schema/sudoku-puzzle-1.json"


# normalisation 8 (ENGINE.md): 2-cell tables that are an edge clue (differences / sums / products / quotients) and mathrax
# corner tables are written as edge / corner rules. False keeps such tables as "table" rules.
UNIFY_TABLE_EDGES = True
# Engine form of NUMBERED pair clues (edge difference / sum / product / ratio, mathrax corners) -- one form for every source.
# "table": 2-cell tables of the allowed digit pairs, the form whose pricing fits players' times; kropki, XV and less stay
# pair relations (their calibrated path). "relation" = generic pair relations.
NUMBERED_PAIR_FORM = "table"


class FormatError(ValueError):
    """the file breaks the format (unknown key / rule type, bad cell, failed structural check)."""


class NotSupportedError(ValueError):
    """the file is valid, but uses something the pencilmark engine cannot build (or an engine puzzle the format cannot
    express)."""


# ---------------------------------------------------------------------------------------------------------------- cells
_CELL = re.compile(r"r([1-9]\d*)c([1-9]\d*)")


def cell_name(r, c):
    """0-based (row, col) -> 'r1c1'"""
    return f"r{r + 1}c{c + 1}"


def parse_cell(s):
    """'r1c1' -> 0-based (row, col)"""
    m = _CELL.fullmatch(s) if isinstance(s, str) else None
    if not m or int(m.group(1)) < 1 or int(m.group(2)) < 1:
        raise FormatError(f"bad cell name {s!r}")
    return int(m.group(1)) - 1, int(m.group(2)) - 1


SIDES = {"top": (-1, 0), "bottom": (1, 0), "left": (0, -1), "right": (0, 1)}

# pair operators (FORMAT.md 5.1) <-> engine relation kinds
OPS = {"different": "neq", "equal": "eq", "less": "lt", "less_equal": "le", "difference": "diff",
       "not_difference": "notdiff", "not_consecutive": "nonconsec", "difference_at_least": "diffge",
       "difference_at_most": "diffle", "ratio": "ratio", "not_ratio": "notratio", "sum": "sum", "not_sum": "notsum",
       "parity_differs": "parity", "same_third": "samegroup3", "different_third": "diffgroup3", "same_mod3": "samemod3",
       "different_mod3": "diffmod3", "allowed": "allowed", "any_of": "anyof"}
REL_OP = {v: k for k, v in OPS.items()}
OP_NPARAMS = {"difference": 1, "not_difference": 1, "difference_at_least": 1, "difference_at_most": 1, "ratio": 1,
              "not_ratio": 1, "sum": 1, "not_sum": 1, "allowed": 1}
DIRECTED_OPS = {"less", "less_equal", "allowed", "any_of"}
NEIGHBOUR_STEPS = PJ.NEIGHBOURS
KNIGHT = [(1, 2), (2, 1), (1, -2), (2, -1)]
KING_DIAG = [(1, 1), (1, -1)]
ORTHO = [(0, 1), (1, 0)]


def _op_params_to_engine(op, params):
    if op == "any_of":
        return tuple((OPS[o], *p) for o, p in params)
    if op == "allowed":
        return ([list(x) for x in params[0]],)
    return tuple(params)


def _engine_params_to_op(kind, args):
    if kind == "anyof":
        return [[REL_OP[a[0]], list(a[1:])] for a in args]
    if kind == "allowed":
        return [[list(x) for x in args[0]]]
    return list(args)


# --------------------------------------------------------------------------------------------------------------- board
class Board:
    """coordinates of the existing cells (0-based) and helpers shared by the reader and the writer."""

    def __init__(self, coords, D):
        self.coords = [tuple(x) for x in coords]
        self.D = D
        self.cid = {rc: i for i, rc in enumerate(self.coords)}
        self.R = max(r for r, _ in self.coords) + 1
        self.C = max(c for _, c in self.coords) + 1

    def name(self, i):
        return cell_name(*self.coords[i])

    def idx(self, name):
        rc = parse_cell(name)
        if rc not in self.cid:
            raise FormatError(f"cell {name} does not exist (null in givens or outside the grid)")
        return self.cid[rc]

    def adjacent(self, a, b):
        (r1, c1), (r2, c2) = self.coords[a], self.coords[b]
        return abs(r1 - r2) + abs(c1 - c2) == 1

    def touching(self, a, b):
        (r1, c1), (r2, c2) = self.coords[a], self.coords[b]
        return max(abs(r1 - r2), abs(c1 - c2)) == 1

    def pairs(self, steps, cells=None):
        """forward neighbour pairs in the engine's order (puzzle_json._pairs): by cell, then by step."""
        out = []
        for (r, c), a in self.cid.items():
            for dr, dc in steps:
                b = self.cid.get((r + dr, c + dc))
                if b is not None:
                    out.append((a, b))
        if cells is not None:
            cs = set(cells)
            out = [(a, b) for a, b in out if a in cs and b in cs]
        return out

    def windows2x2(self):
        """2x2 blocks of existing cells (TL, TR, BL, BR) in puzzle_json's global-entropy order (sorted by top-left)."""
        out = []
        for (r, c) in sorted(self.cid):
            w = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
            if all(x in self.cid for x in w):
                out.append([self.cid[x] for x in w])
        return out

    def is_block(self, cells):
        if len(cells) != 4:
            return False
        (r, c) = self.coords[cells[0]]
        return [self.coords[x] for x in cells] == [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]

    def outside_side(self, cells):
        """side of an outside clue whose ordered cells start next to it, or None"""
        r, c = self.coords[cells[0]]
        if len(cells) == 1:
            cand = list(SIDES.items())
        else:
            r2, c2 = self.coords[cells[1]]
            dr, dc = r2 - r, c2 - c
            if any((self.coords[b][0] - self.coords[a][0], self.coords[b][1] - self.coords[a][1]) != (dr, dc)
                   for a, b in zip(cells, cells[1:])):
                return None
            cand = []
            if dc == 0 and abs(dr) == 1:
                cand = [("top" if dr == 1 else "bottom", (-dr, 0))]
            elif dr == 0 and abs(dc) == 1:
                cand = [("left" if dc == 1 else "right", (0, -dc))]
            elif abs(dr) == 1 and abs(dc) == 1:
                cand = [("top" if dr == 1 else "bottom", (-dr, 0)), ("left" if dc == 1 else "right", (0, -dc))]
        for side, (sr, sc) in cand:
            if (r + sr, c + sc) not in self.cid:
                return side
        return None

    def outside_ok(self, side, cells, diagonal_ok=True):
        try:
            self.check_outside(side, cells, diagonal_ok)
            return True
        except FormatError:
            return False

    def check_outside(self, side, cells, diagonal_ok=True, what="outside clue"):
        r, c = self.coords[cells[0]]
        sr, sc = SIDES[side]
        if (r + sr, c + sc) in self.cid:
            raise FormatError(f"{what}: the position on the {side} of {self.name(cells[0])} is a cell")
        if len(cells) > 1:
            r2, c2 = self.coords[cells[1]]
            dr, dc = r2 - r, c2 - c
            straight = (dr, dc) == (-sr, -sc)
            diag = diagonal_ok and abs(dr) == 1 and abs(dc) == 1 and ((sr and dr == -sr) or (sc and dc == -sc))
            if not (straight or diag):
                raise FormatError(f"{what}: cells must run away from the {side} side")
            for a, b in zip(cells, cells[1:]):
                if (self.coords[b][0] - self.coords[a][0], self.coords[b][1] - self.coords[a][1]) != (dr, dc):
                    raise FormatError(f"{what}: cells are not collinear and contiguous")


def _factor_shapes(D):
    out = []
    if D in PJ.BOXES:
        bh, bw = PJ.BOXES[D]
        out += [(bh, bw), (bw, bh)]
    for h in range(2, D):
        if D % h == 0 and (h, D // h) not in out:
            out.append((h, D // h))
    return out


def subgrid_units(grid, n, box):
    """rows, columns, boxes of an n x n sub-grid given as n*n engine cells in its reading order (puzzle_json's
    _layout_regions / standard order)."""
    units = [("row", tuple(grid[i * n:(i + 1) * n])) for i in range(n)]
    units += [("col", tuple(grid[j::n])) for j in range(n)]
    if box:
        bh, bw = box
        units += [("box", tuple(grid[(br + a) * n + bc + b] for a in range(bh) for b in range(bw)))
                  for br in range(0, n, bh) for bc in range(0, n, bw)]
    return units


def window(B, r0, c0, n):
    out = []
    for r in range(r0, r0 + n):
        for c in range(c0, c0 + n):
            if (r, c) not in B.cid:
                return None
            out.append(B.cid[(r, c)])
    return out


def grid_units(B, r0, c0, box=None):
    """houses of a grid at (r0, c0): its D rows (top to bottom), D columns (left to right) and, for a box_grid with
    box [bh, bw], its D boxes (reading order of their top-left cells). None if a cell of the D x D area is missing."""
    D = B.D
    grid = []
    for r in range(r0, r0 + D):
        for c in range(c0, c0 + D):
            if (r, c) not in B.cid:
                return None
            grid.append(B.cid[(r, c)])
    out = [("row", tuple(grid[i * D:(i + 1) * D])) for i in range(D)]
    out += [("col", tuple(grid[j::D])) for j in range(D)]
    if box:
        bh, bw = box
        out += [("box", tuple(grid[(br + a) * D + bc + b_] for a in range(bh) for b_ in range(bw)))
                for br in range(0, D, bh) for bc in range(0, D, bw)]
    return out


def grid_area(B, r0, c0):
    return {B.cid[(r, c)] for r in range(r0, r0 + B.D) for c in range(c0, c0 + B.D)}


def read_houses(rules, B):
    """the house groups a rule list states, in engine order -> (houses [(kind, cells, extra)], areas [cell sets])
    (FORMAT.md 6.1): grid / box_grid / box / row / column rules in file order, a house equal to an earlier one skipped;
    areas = the grid / box_grid areas."""
    out, seen, areas = [], set(), []
    def add(kind, cells, **kw):
        fs = frozenset(cells)
        if kind in ("row", "col", "box"):
            if fs in seen:
                return
            seen.add(fs)
        out.append((kind, tuple(cells), kw))
    for r in rules:
        t = r["type"]
        if t in ("grid", "box_grid"):
            r0, c0 = parse_cell(r["origin"])
            areas.append(grid_area(B, r0, c0))
            for kind, cells in grid_units(B, r0, c0, r.get("box")):
                add(kind, cells)
        elif t in ("row", "column"):
            add({"column": "col"}.get(t, t), [B.idx(c) for c in r["cells"]])
        elif t in ("box", "region", "cage"):
            cells = [B.idx(c) for c in r["cells"]]
            if t == "box":
                add("box", cells)
            elif t == "region":
                add({"diagonal": "diag", "window": "window"}.get(r["kind"], "region"), cells)
            else:
                add("cage", cells, **({"sum": r["sum"]} if "sum" in r else {}))
    return out, areas


# battenburg tables (TL != TR, TL != BL, TR != BR, BL != BR included)
def _cb(t):
    p = [x % 2 for x in t]
    return p[0] == p[3] and p[1] == p[2] and p[0] != p[1]


def battenburg_table(D, marked):
    return [list(t) for t in itertools.product(range(1, D + 1), repeat=4) if _cb(t) == marked
            and t[0] != t[1] and t[0] != t[2] and t[1] != t[3] and t[2] != t[3]]


def lockout_table(D, k):
    return [(x, y, z) for x in range(1, D + 1) for y in range(1, D + 1) if abs(x - y) >= k
            for z in range(1, D + 1) if z < min(x, y) or z > max(x, y)]


def vudoku_table(D):
    return [(x, y, z) for y in range(1, D + 1) for z in range(1, D + 1) for x in {y + z, abs(y - z)} if 1 <= x <= D]


def product_pairs(D, p):
    return [[u, v] for u in range(1, D + 1) for v in range(1, D + 1) if u * v == p]


def _rel_pairs(D, kind, args):
    f = M.RELATIONS[kind]
    return {(u, v) for u in range(1, D + 1) for v in range(1, D + 1) if f(u, v, *args)}


def _same_set(A, rel, D):
    """allowed pair set A (of a 2-cell table) equals the relation's pairs, or those pairs without equal digits"""
    return A == rel or A == {x for x in rel if x[0] != x[1]}


_CACHE = {}


def _pair_clue(D, allowed):
    """("+" | "-" | "/" | "x", value) when a 2-cell allowed list is exactly one pair clue (with or without equal digits)"""
    key = ("pc", D)
    if key not in _CACHE:
        idx = {}
        for op, kind in (("-", "diff"), ("+", "sum"), ("/", "ratio")):
            for v in range(1, 2 * D + 1):
                S = frozenset(_rel_pairs(D, kind, (v,)))
                for T in (S, frozenset(x for x in S if x[0] != x[1])):
                    if T:
                        idx.setdefault(T, (op, v))
        for v in range(1, D * D + 1):
            S = frozenset(tuple(x) for x in product_pairs(D, v))
            for T in (S, frozenset(x for x in S if x[0] != x[1])):
                if T:
                    idx.setdefault(T, ("x", v))
        _CACHE[key] = idx
    return _CACHE[key].get(frozenset(tuple(x) for x in allowed))


def _bat(D):
    if ("bat", D) not in _CACHE:
        _CACHE[("bat", D)] = ([tuple(x) for x in battenburg_table(D, True)], [tuple(x) for x in battenburg_table(D, False)])
    return _CACHE[("bat", D)]


# edge kinds -> engine relation of one pair
def edge_relation(rule, D):
    k = rule["kind"]
    if k == "kropki":
        return ("diff", 1) if rule["color"] == "white" else ("ratio", 2)
    if k == "xv":
        return ("sum", 10) if rule["letter"] == "X" else ("sum", 5)
    if k == "difference":
        return ("diff", rule["value"])
    if k == "sum":
        return ("sum", rule["sum"])
    if k == "ratio":
        return ("ratio", rule["value"])
    if k == "product":
        return ("allowed", product_pairs(D, rule["value"]))
    if k == "less":
        return ("lt",)
    raise FormatError(f"unknown edge kind {k!r}")


_MATHRAX_OK = {"+": lambda v: (lambda x, y: x + y == v), "-": lambda v: (lambda x, y: abs(x - y) == v),
               "/": lambda v: (lambda x, y: max(x, y) == v * min(x, y)), "x": lambda v: (lambda x, y: x * y == v)}
_NUMBERED_OK = {"difference": lambda r: _MATHRAX_OK["-"](r["value"]), "sum": lambda r: _MATHRAX_OK["+"](r["sum"]),
                "ratio": lambda r: _MATHRAX_OK["/"](r["value"]), "product": lambda r: _MATHRAX_OK["x"](r["value"])}


def edge_family(kind, args, D):
    """(family, value) a pair relation is written as when it is an edge clue, or None"""
    if kind == "diff" and args == (1,):
        return ("kropki", "white")
    if kind == "ratio" and args == (2,):
        return ("kropki", "black")
    if kind == "anyof" and set(args) == {("diff", 1), ("ratio", 2)}:
        return None
    if kind == "sum" and args in ((10,), (5,)):
        return ("xv", "X" if args == (10,) else "V")
    if kind == "diff" and len(args) == 1:
        return ("difference", args[0])
    if kind == "sum" and len(args) == 1:
        return ("sum", args[0])
    if kind == "ratio" and len(args) == 1:
        return ("ratio", args[0])
    if kind == "lt" and not args:
        return ("less", None)
    if kind == "allowed" and len(args) == 1:
        A = {tuple(x) for x in args[0]}
        for p in range(1, D * D + 1):
            if A == {tuple(x) for x in product_pairs(D, p)}:
                return ("product", p)
    return None


def edge_rule(family, value, a, b, B):
    r = {"type": "edge", "kind": family}
    if family == "kropki":
        r["color"] = value
    elif family == "xv":
        r["letter"] = value
    elif family == "sum":
        r["sum"] = value
    elif family in ("difference", "ratio", "product"):
        r["value"] = value
    r["cells"] = [B.name(a), B.name(b)]
    return r


# negative families: which engine relation an uncovered pair gets
def negative_relation(of, sel, D):
    """-> list of (kind, args) for an uncovered pair, in expansion order"""
    if of == "kropki":
        cols = [sel] if sel else ["white", "black"]
        return [("nonconsec", ()) if c == "white" else ("notratio", (2,)) for c in cols]
    if of == "xv":
        lets = [sel] if sel else ["X", "V"]
        return [("notsum", (10,)) if l == "X" else ("notsum", (5,)) for l in lets]
    if of == "difference":
        return [("notdiff", (sel,))]
    if of == "sum":
        return [("notsum", (sel,))]
    if of == "ratio":
        return [("notratio", (sel,))]
    if of == "product":
        return [("allowed", ([[u, v] for u in range(1, D + 1) for v in range(1, D + 1) if u * v != sel],))]
    raise FormatError(f"negative of {of!r} has no pair relation")


NEG_SELECTOR = {"kropki": "color", "xv": "letter", "difference": "value", "sum": "sum", "ratio": "value",
                "product": "value"}


# -------------------------------------------------------------------------------------------------------- validation
COMMON = {"type", "id", "label", "style"}
RULE_KEYS = {
    "grid": ({"origin"}, set()), "box_grid": ({"origin", "box"}, set()),
    "box": ({"cells"}, set()), "row": ({"cells"}, set()), "column": ({"cells"}, set()),
    "region": ({"kind", "cells"}, set()),
    "cage": ({"cells"}, {"sum"}),
    "line": ({"kind", "cells"}, {"closed", "value", "groups"}),
    "arrow": ({"bulb", "lines"}, set()),
    "edge": ({"kind", "cells"}, {"color", "letter", "value", "sum"}),
    "corner": ({"kind", "cells"}, {"op", "value"}),
    "sum": ({"kind", "sum", "cells"}, {"side"}),
    "sandwich": ({"sum", "side", "cells"}, set()),
    "xsum": ({"sum", "side", "cells"}, set()),
    "skyscraper": ({"value", "side", "cells"}, set()),
    "rossini": ({"arrow", "side", "cells"}, set()),
    "first_seen": ({"value", "digits", "side", "cells"}, set()),
    "neighbours": (set(), {"kind", "op", "params", "where", "within", "area", "except"}),
    "relation": ({"op", "params", "pairs"}, set()),
    "cell": ({"kind", "cells"}, {"split", "values"}),
    "contains": ({"digits", "cells"}, set()),
    "appears": ({"source", "cells"}, set()),
    "clone": ({"regions"}, set()),
    "isomorphic": ({"regions"}, set()),
    "count": ({"cells"}, {"kind", "each", "counts"}),
    "distinct_count": ({"value", "cells"}, {"side"}),
    "global_entropy": (set(), set()),
    "equal_sum": ({"segments"}, set()),
    "vudoku": ({"cells"}, set()),
    "table": ({"allowed"}, {"cells", "where"}),
    "negative": ({"of"}, {"color", "letter", "value", "sum", "kind", "split", "area"}),
}
KINDS = {
    "region": {"diagonal", "window", "disjoint", "colour", "extra", "region"},
    "line": {"thermo", "slow_thermo", "whisper", "renban", "region_sum", "palindrome", "entropic", "modular", "parity",
             "zipper", "between", "lockout", "double_arrow"},
    "edge": {"kropki", "xv", "difference", "sum", "product", "ratio", "less"},
    "corner": {"battenburg", "mathrax", "exclude"},
    "sum": {"little_killer", "frame", "group", "corner"},
    "neighbours": {"antiknight", "antiking", "nonconsecutive"},
    "cell": {"odd", "even", "low", "high", "set", "exclude"},
    "count": {"circles"},
}
LINE_PARAMS = {"whisper": {"value"}, "modular": {"value"}, "lockout": {"value"}, "entropic": {"groups"}}
EDGE_PARAMS = {"kropki": {"color"}, "xv": {"letter"}, "difference": {"value"}, "sum": {"sum"}, "product": {"value"},
               "ratio": {"value"}, "less": set()}
NEG_OF = {"kropki", "xv", "difference", "sum", "ratio", "product", "rossini", "battenburg", "cell"}
TOP_KEYS = {"format", "format_version", "$schema", "meta", "board", "digits", "givens", "solution", "candidates", "rules",
            "decorations", "style", "ext"}


def _int(x, what, lo=None):
    if not isinstance(x, int) or isinstance(x, bool) or (lo is not None and x < lo):
        raise FormatError(f"{what} must be an integer" + (f" >= {lo}" if lo is not None else ""))
    return x


def validate(doc):
    """strict reading (FORMAT.md section 4) of a format_version 1 dict; raises FormatError. Returns the Board."""
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise FormatError('not a sudoku-puzzle ("format" must be "sudoku-puzzle")')
    if "format_version" not in doc:
        raise FormatError("format_version missing")
    fv = _int(doc["format_version"], "format_version", 1)
    if fv > FORMAT_VERSION:
        raise FormatError(f"format_version {fv} is newer than this reader ({FORMAT_VERSION})")
    for k in doc:
        if k not in TOP_KEYS:
            raise FormatError(f"unknown top-level key {k!r}")
    for k in ("board", "digits", "givens", "rules"):
        if k not in doc:
            raise FormatError(f"{k!r} missing")
    g = doc["board"]
    if not isinstance(g, dict) or set(g) != {"rows", "cols"}:
        raise FormatError('"board" must be {"rows": R, "cols": C}')
    R, C = _int(g["rows"], "grid.rows", 1), _int(g["cols"], "grid.cols", 1)
    D = _int(doc["digits"], "digits", 1)
    giv = doc["givens"]
    if not isinstance(giv, list) or len(giv) != R * C:
        raise FormatError(f"givens must be a list of rows*cols = {R * C} entries")
    for v in giv:
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= D):
            raise FormatError(f"givens entry {v!r} is not null or 0..{D}")
    coords = [divmod(k, C) for k, v in enumerate(giv) if v is not None]
    if not coords:
        raise FormatError("the grid has no cells")
    B = Board(coords, D)
    if doc.get("solution") is not None:
        sol = doc["solution"]
        if not isinstance(sol, list) or len(sol) != R * C:
            raise FormatError("solution must have the shape of givens")
        for k, (v, w) in enumerate(zip(giv, sol)):
            if (v is None) != (w is None) or (w is not None and (not isinstance(w, int) or not 1 <= w <= D)):
                raise FormatError(f"solution entry {k} does not match givens (null where givens is null, else 1..{D})")
    cands = doc.get("candidates")
    if cands is not None:
        if not isinstance(cands, dict):
            raise FormatError("candidates must be an object")
        for k, v in cands.items():
            B.idx(k)
            if not isinstance(v, list) or any(not isinstance(x, int) or not 1 <= x <= D for x in v):
                raise FormatError(f"candidates of {k} must be a list of digits 1..{D}")
    if not isinstance(doc["rules"], list):
        raise FormatError("rules must be a list")
    B.grid_origins = {r["origin"] for r in doc["rules"] if isinstance(r, dict) and r.get("type") in ("grid", "box_grid")
                      and isinstance(r.get("origin"), str)}
    for i, r in enumerate(doc["rules"]):
        try:
            _validate_rule(r, B)
        except FormatError as e:
            raise FormatError(f"rule {i} ({r.get('type') if isinstance(r, dict) else r!r}): {e}") from None
    return B


def _cells(B, x, what="cells", n=None, minlen=1):
    if not isinstance(x, list) or len(x) < minlen or (n is not None and len(x) != n):
        raise FormatError(f"{what} must be a list of " + (f"{n}" if n is not None else f">= {minlen}") + " cell names")
    out = [B.idx(c) for c in x]
    return out


def _merge_negatives(rules, prov):
    """adjacent negatives of both kropki colours (white, black) or both XV letters (X, V) with the same scope -> one negative
    without a selector, which expands to the same relations in the same order"""
    out, op = [], []
    for r, pr in zip(rules, prov):
        if out and r.get("type") == "negative" and out[-1].get("type") == "negative" and r["of"] == out[-1]["of"] in ("kropki", "xv"):
            key = NEG_SELECTOR[r["of"]]
            first, second = ("white", "black") if r["of"] == "kropki" else ("X", "V")
            strip = lambda x: {k: v for k, v in x.items() if k != key}
            if out[-1].get(key) == first and r.get(key) == second and strip(out[-1]) == strip(r):
                out[-1] = strip(r)
                op[-1] = {k: set(op[-1].get(k, ())) | set(pr.get(k, ())) for k in set(op[-1]) | set(pr)}
                continue
        out.append(r); op.append(pr)
    return out, op


def area_cells(B, a):
    """an area (FORMAT.md 5): the origin of a grid / box_grid rule -> that grid's D x D cells in reading order, or a list of
    cell names -> those cells; as engine cell ids"""
    if isinstance(a, str):
        if a not in getattr(B, "grid_origins", ()):
            raise FormatError(f"area {a!r} is not the origin of a grid / box_grid rule")
        r0, c0 = parse_cell(a)
        return [B.cid[(r, c)] for r in range(r0, r0 + B.D) for c in range(c0, c0 + B.D)]
    return _cells(B, a, "area")


def resolve_areas(B, rules):
    """rules with every "area" replaced by its cell list ("cells"), as the engine expansion reads them"""
    return [dict({k: v for k, v in r.items() if k != "area"}, cells=[B.name(c) for c in area_cells(B, r["area"])])
            if isinstance(r, dict) and "area" in r else r for r in rules]


def _validate_rule(r, B):
    D = B.D
    if not isinstance(r, dict) or "type" not in r:
        raise FormatError("a rule must be an object with a type")
    t = r["type"]
    if t == "custom":
        raise FormatError('"custom" is reserved for a later rule language and refused by format_version 1 readers')
    if isinstance(t, str) and ":" in t:
        raise FormatError(f"vendor rule type {t!r} is not implemented by this reader")
    if t not in RULE_KEYS:
        raise FormatError(f"unknown rule type {t!r}")
    req, opt = RULE_KEYS[t]
    for k in r:
        if k not in req | opt | COMMON:
            raise FormatError(f"unknown key {k!r}")
    for k in req:
        if k not in r:
            raise FormatError(f"missing key {k!r}")
    kind = r.get("kind")
    if t in KINDS and (kind is not None or t not in ("neighbours", "count")) and kind not in KINDS[t]:
        raise FormatError(f"unknown kind {kind!r}")
    if t in ("grid", "box_grid"):
        if t == "box_grid":
            bx = r["box"]
            if not (isinstance(bx, list) and len(bx) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and x >= 1
                                                                  for x in bx)):
                raise FormatError("box must be [rows, cols] of positive integers")
            if bx[0] * bx[1] != D:
                raise FormatError(f"box {bx} does not hold {D} cells")
        r0, c0 = parse_cell(r["origin"])
        if grid_units(B, r0, c0) is None:
            raise FormatError(f"{t} covers a missing cell (its area is {D} x {D} from origin)")
    elif t in ("box", "row", "column", "region", "contains", "appears", "cell", "count", "vudoku"):
        cs = _cells(B, r["cells"])
        if t == "vudoku" and len(cs) != 3:
            raise FormatError("vudoku takes 3 cells (vertex, arm, arm)")
        if t == "appears":
            B.idx(r["source"])
        if t == "contains" and (not isinstance(r["digits"], list) or not r["digits"]
                                or any(not isinstance(x, int) or not 1 <= x <= D for x in r["digits"])):
            raise FormatError(f"digits must be a list of digits 1..{D}")
        if t == "cell":
            if kind in ("low", "high"):
                if "split" not in r or "values" in r:
                    raise FormatError(f"digits {kind} takes split (and no values)")
                _int(r["split"], "split", 1)
            elif kind in ("set", "exclude"):
                if "values" not in r or "split" in r:
                    raise FormatError(f"digits {kind} takes values")
                if not isinstance(r["values"], list) or not r["values"] or any(not isinstance(x, int) or not 1 <= x <= D for x in r["values"]):
                    raise FormatError(f"values must be digits 1..{D}")
            elif "split" in r or "values" in r:
                raise FormatError(f"digits {kind} takes no split / values")
        if t == "count":
            modes = [k for k in ("kind", "each", "counts") if k in r]
            if len(modes) != 1:
                raise FormatError("count takes exactly one of kind / each / counts")
    elif t == "cage":
        _cells(B, r["cells"])
        if "sum" in r:
            _int(r["sum"], "sum", 0)
    elif t == "line":
        cs = _cells(B, r["cells"], minlen=2)
        for a, b in zip(cs, cs[1:]):
            if not B.touching(a, b):
                raise FormatError(f"line cells {B.name(a)} and {B.name(b)} do not touch")
        allowed = LINE_PARAMS.get(kind, set())
        for k in ("value", "groups"):
            if k in r and k not in allowed:
                raise FormatError(f"line {kind} takes no {k!r}")
        if D != 9 and allowed and not (allowed <= set(r)):
            raise FormatError(f"line {kind} requires {sorted(allowed)} when digits != 9")
        if r.get("closed") and kind not in ("whisper", "renban", "parity"):
            raise FormatError(f"line {kind} cannot be closed")
        if "closed" in r and not isinstance(r["closed"], bool):
            raise FormatError("closed must be true / false")
    elif t == "arrow":
        bulb = _cells(B, r["bulb"], "bulb")
        if not isinstance(r["lines"], list) or not r["lines"]:
            raise FormatError("lines must be a list of shafts")
        for sh in r["lines"]:
            cs = _cells(B, sh, "shaft")
            if not any(B.touching(cs[0], b) for b in bulb):
                raise FormatError("a shaft must start next to a bulb cell")
    elif t == "edge":
        cs = _cells(B, r["cells"], n=2)
        if not B.adjacent(*cs):
            raise FormatError("edge cells must be orthogonally adjacent")
        need = EDGE_PARAMS[kind]
        if set(r) & {"color", "letter", "value", "sum"} != need:
            raise FormatError(f"edge {kind} takes exactly {sorted(need) or 'no parameters'}")
        if kind == "kropki" and r["color"] not in ("white", "black"):
            raise FormatError("color must be white or black")
        if kind == "xv" and r["letter"] not in ("X", "V"):
            raise FormatError("letter must be X or V")
    elif t == "corner":
        cs = _cells(B, r["cells"], n=4)
        if not B.is_block(cs):
            raise FormatError("corner cells must be a 2x2 block written TL, TR, BL, BR")
        if kind == "battenburg" and set(r) & {"op", "value"}:
            raise FormatError("battenburg takes no parameters")
        if kind == "exclude" and ("value" not in r or "op" in r):
            raise FormatError("corner exclude takes value")
        if kind == "mathrax":
            op = r.get("op")
            if op in ("even", "odd"):
                if "value" in r:
                    raise FormatError("mathrax even / odd takes no value")
            elif op in ("+", "-", "x", "/"):
                _int(r.get("value"), "value", 0)
            else:
                raise FormatError("mathrax op must be + - x / even odd")
    elif t == "sum":
        cs = _cells(B, r["cells"])
        _int(r["sum"], "sum", 0)
        if kind in ("little_killer", "frame"):
            if "side" not in r:
                raise FormatError(f"sum {kind} needs side")
            B.check_outside(r["side"], cs, diagonal_ok=(kind == "little_killer"), what=f"sum {kind}")
        elif "side" in r:
            raise FormatError(f"sum {kind} takes no side")
        if kind == "corner" and not B.is_block(cs):
            raise FormatError("sum corner cells must be a 2x2 block")
    elif t in ("sandwich", "xsum", "skyscraper", "rossini", "first_seen"):
        if r["side"] not in SIDES:
            raise FormatError("side must be top / bottom / left / right")
        cs = _cells(B, r["cells"])
        B.check_outside(r["side"], cs, diagonal_ok=False, what=t)
        if t == "rossini" and (r["arrow"] not in ("in", "out") or len(cs) != 3):
            raise FormatError("rossini takes arrow in / out and 3 cells")
    elif t == "distinct_count":
        cs = _cells(B, r["cells"])
        if "side" in r:
            B.check_outside(r["side"], cs, what="distinct_count")
    elif t == "neighbours":
        if "kind" in r:
            if set(r) & {"op", "params", "where"}:
                raise FormatError("neighbours takes a kind or op / params / where, not both")
        else:
            if not {"op", "params", "where"} <= set(r):
                raise FormatError("neighbours needs a kind, or op + params + where")
            _check_op(r["op"], r["params"])
            if r["op"] in DIRECTED_OPS - {"allowed", "any_of"} or r["where"] not in NEIGHBOUR_STEPS:
                raise FormatError("neighbours needs a symmetric op and where orthogonal / diagonal / king / knight")
        if "within" in r and r["within"] not in ("box", "region"):
            raise FormatError("within must be box or region")
        if "area" in r:
            area_cells(B, r["area"])
        for p in r.get("except") or []:
            _cells(B, p, "except pair", n=2)
    elif t == "relation":
        _check_op(r["op"], r["params"])
        if not isinstance(r["pairs"], list) or not r["pairs"]:
            raise FormatError("pairs must be a non-empty list")
        for p in r["pairs"]:
            _cells(B, p, "pair", n=2)
    elif t in ("clone", "isomorphic"):
        regs = r["regions"]
        if not isinstance(regs, list) or len(regs) < 2 or (t == "isomorphic" and len(regs) != 2):
            raise FormatError(f"{t} takes " + ("2" if t == "isomorphic" else ">= 2") + " regions")
        n = None
        for reg in regs:
            cs = _cells(B, reg, "region")
            if n is not None and len(cs) != n:
                raise FormatError("regions must have equal sizes")
            n = len(cs)
    elif t == "equal_sum":
        if not isinstance(r["segments"], list) or len(r["segments"]) < 2:
            raise FormatError("equal_sum takes >= 2 segments")
        for s in r["segments"]:
            _cells(B, s, "segment")
    elif t == "table":
        if ("cells" in r) == ("where" in r):
            raise FormatError("table takes exactly one of cells / where")
        n = len(_cells(B, r["cells"])) if "cells" in r else len(r["where"])
        if not isinstance(r["allowed"], list) or any(not isinstance(x, list) or len(x) != n for x in r["allowed"]):
            raise FormatError("allowed must be a list of digit tuples of the table's width")
    elif t == "negative":
        of = r["of"]
        if of not in NEG_OF:
            raise FormatError(f"negative of {of!r} is not defined")
        sel = set(r) & {"color", "letter", "value", "sum", "kind", "split"}
        if of in ("kropki", "xv"):
            key = NEG_SELECTOR[of]
            if sel - {key}:
                raise FormatError(f"negative {of} takes only {key}")
        elif of in ("difference", "ratio", "product", "sum"):
            if sel != {NEG_SELECTOR[of]}:
                raise FormatError(f"negative {of} requires {NEG_SELECTOR[of]}")
        elif of in ("rossini", "battenburg"):
            if sel:
                raise FormatError(f"negative {of} takes no selector")
        elif of == "cell":
            if r.get("kind") not in ("odd", "even", "low", "high"):
                raise FormatError("negative cell needs kind odd / even / low / high")
            if (r["kind"] in ("low", "high")) != ("split" in r) or sel - {"kind", "split"}:
                raise FormatError("negative cell low / high need split (others take none)")
        if "area" in r:
            area_cells(B, r["area"])


def _check_op(op, params):
    if op not in OPS:
        raise FormatError(f"unknown operator {op!r}")
    if not isinstance(params, list) or len(params) != OP_NPARAMS.get(op, 0) and op != "any_of":
        raise FormatError(f"operator {op} takes {OP_NPARAMS.get(op, 0)} parameter(s)")
    if op == "any_of":
        for x in params:
            if not (isinstance(x, list) and len(x) == 2):
                raise FormatError("any_of takes [[op, params], ...]")
            _check_op(x[0], x[1])


# ----------------------------------------------------------------------------------------------------------- reading
def to_internal(doc):
    """sudoku-puzzle (format_version 1) -> puzzle JSON (pencilmark.puzzle_json) that builds the engine Puzzle."""
    B = validate(doc)
    D = B.D
    R, C = doc["board"]["rows"], doc["board"]["cols"]
    giv = doc["givens"]
    sym = lambda v: "." if not v else PJ._sym(v)
    out = {"digits": D, "numbers": "".join("#" if v is None else sym(v) for v in giv)}
    plain = R == C == D and None not in giv
    if not plain:
        out["shape"] = ["".join("." if giv[r * C + c] is None else "#" for c in range(C)) for r in range(R)]
    if doc.get("solution"):
        out["solution"] = "".join("#" if v is None else sym(v) for v in doc["solution"])
    rules = resolve_areas(B, doc["rules"])
    # houses (FORMAT.md 6.1; a house equal to an earlier one is the same house)
    houses, areas = read_houses(rules, B)
    regions = [dict({"kind": k, "cells": [B.name(c) for c in cells]}, **kw) for k, cells, kw in houses]
    boxes = [set(cells) for k, cells, kw in houses if k == "box"]
    out["regions"] = regions
    ctx = _ReadCtx(B, rules, areas, boxes, regions)
    internal = []
    done = set()
    for i, r in enumerate(rules):
        if i in done:
            continue
        internal += ctx.rule(i, r, done)
    if internal:
        out["rules"] = internal
    if doc.get("candidates"):
        out["candidates"] = {k.lower(): "".join(PJ._sym(v) for v in sorted(set(vs))) for k, vs in doc["candidates"].items()}
    if doc.get("meta"):
        out["meta"] = dict(doc["meta"])
    return out


def read(doc):
    """sudoku-puzzle dict -> engine Puzzle (not finalized)"""
    return PJ.from_json(to_internal(doc))


class _ReadCtx:
    def __init__(self, B, rules, subgrids, boxes, regions):
        """subgrids: the grid / box_grid areas (negative adjacency and battenburg windows stay inside one area)"""
        self.B, self.rules, self.D = B, rules, B.D
        self.subgrids = subgrids
        self.boxes = boxes
        self.regions = [set(B.idx(c) for c in g["cells"]) for g in regions if g["kind"] in ("diag", "window", "region")]
        self.sub_of = {}
        for k, s in enumerate(subgrids):
            for c in s:
                self.sub_of.setdefault(c, set()).add(k)
        fam = {}
        for r in rules:
            if r["type"] == "edge":
                a, b = (B.idx(c) for c in r["cells"])
                fam.setdefault(r["kind"], set()).add(frozenset((a, b)))
        self.family = fam
        self.houses = [set(B.idx(c) for c in g["cells"]) for g in regions
                       if g["kind"] in ("row", "col", "box", "diag", "window", "region")]

    def share_house(self, a, b):
        return any(a in h and b in h for h in self.houses)

    def pair_table(self, a, b, ok):
        """numbered pair clue as a 2-cell table (product order, equal digits only when the cells
        share no house)"""
        same = self.share_house(a, b)
        D = self.D
        allowed = [[u, v] for u in range(1, D + 1) for v in range(1, D + 1) if (u != v or not same) and ok(u, v)]
        return {"type": "table", "cells": [self.B.name(a), self.B.name(b)], "allowed": allowed}

    def n(self, cells):
        return [self.B.name(c) for c in cells]

    def pairs_rule(self, kind, args, prs):
        return {"type": "pairs", "rel": kind, "params": _engine_params_json(kind, args),
                "cells": [[self.B.name(a), self.B.name(b)] for a, b in prs]}

    def ortho_pairs(self, cells=None):
        prs = self.B.pairs(ORTHO, cells)
        if self.subgrids:
            prs = [(a, b) for a, b in prs if self.sub_of.get(a, set()) & self.sub_of.get(b, set())]
        return prs

    def negative_pairs(self, of, sel_cells=None):
        exempt = self.family.get(of, set())
        return [(a, b) for a, b in self.ortho_pairs(sel_cells) if frozenset((a, b)) not in exempt]

    def rule(self, i, r, done):
        B, D, t = self.B, self.D, r["type"]
        idx = lambda xs: [B.idx(c) for c in xs]
        if t in ("grid", "box_grid", "box", "row", "column", "region", "cage"):
            return []
        if t == "line":
            k = r["kind"]
            cs = r["cells"]
            if k == "double_arrow":
                return [{"type": "equal_sum", "segments": [[cs[0], cs[-1]], cs[1:-1]]}]
            if k == "lockout":
                kk = r.get("value", 4)
                a, b = idx([cs[0], cs[-1]])
                out = [self.pairs_rule("diffge", (kk,), [(a, b)])]
                tab = [list(x) for x in lockout_table(D, kk)]
                out += [{"type": "table", "cells": [cs[0], cs[-1], c], "allowed": tab} for c in cs[1:-1]]
                return out
            con = {"type": "line", "kind": k, "cells": list(cs) + ([cs[0]] if r.get("closed") and k != "renban" else [])}
            if k == "whisper" and "value" in r:
                con["k"] = r["value"]
            if k == "modular" and r.get("value", 3) != 3:
                raise NotSupportedError("modular lines with a modulus other than 3 are not supported by the engine")
            if k == "entropic" and "groups" in r:
                third = lambda v: (v - 1) * 3 // D if D % 3 == 0 else (v - 1) // 3
                want = [[v for v in range(1, D + 1) if third(v) == g] for g in range(3)]
                if sorted(sorted(x) for x in r["groups"]) != want:
                    raise NotSupportedError(f"entropic groups {r['groups']} are not supported (engine: {want})")
            return [con]
        if t == "arrow":
            return [{"type": "arrow", "circle": list(r["bulb"]), "line": list(sh)} for sh in r["lines"]]
        if t == "edge":
            a, b = idx(r["cells"])
            k = r["kind"]
            if k == "kropki":
                return [{"type": "kropki", "color": r["color"], "cells": list(r["cells"])}]
            if k == "xv":
                return [{"type": "xv", "letter": r["letter"], "cells": list(r["cells"])}]
            if k == "less":
                return [{"type": "less", "cells": list(r["cells"])}]
            if NUMBERED_PAIR_FORM == "table":
                return [self.pair_table(a, b, _NUMBERED_OK[k](r))]
            rel = edge_relation(r, D)
            return [self.pairs_rule(rel[0], tuple(rel[1:]), [(a, b)])]
        if t == "corner":
            k = r["kind"]
            tl, tr, bl, br = idx(r["cells"])
            if k == "exclude":
                return [{"type": "exclude", "digit": r["value"], "cells": list(r["cells"])}]
            if k == "mathrax":
                op = r["op"]
                if op in ("even", "odd"):
                    return [{"type": "parity", "parity": op, "cells": list(r["cells"])}]
                v = r["value"]
                if NUMBERED_PAIR_FORM == "table":
                    ok = _MATHRAX_OK[op](v)
                    return [self.pair_table(tl, br, ok), self.pair_table(tr, bl, ok)]
                rel = {"+": ("sum", v), "-": ("diff", v), "/": ("ratio", v),
                       "x": ("allowed", product_pairs(D, v))}[op]
                return [self.pairs_rule(rel[0], tuple(rel[1:]), [(tl, br)]), self.pairs_rule(rel[0], tuple(rel[1:]), [(tr, bl)])]
            # battenburg corners (+ negative): one block in window order
            return self.battenburg(i, done)
        if t == "sum":
            con = {"type": "little_killer" if r["kind"] == "little_killer" else "sum", "cells": list(r["cells"]), "total": r["sum"]}
            return [con]
        if t in ("sandwich", "xsum"):
            return [{"type": t, "cells": list(r["cells"]), "total": r["sum"]}]
        if t == "skyscraper":
            return [{"type": t, "cells": list(r["cells"]), "count": r["value"]}]
        if t == "first_seen":
            return [{"type": t, "cells": list(r["cells"]), "value": r["value"], "digits": list(r["digits"])}]
        if t == "rossini":
            return self.rossini(i, done)
        if t == "neighbours":
            return self.neighbours(r)
        if t == "relation":
            kind = OPS[r["op"]]
            args = _op_params_to_engine(r["op"], r["params"])
            return [self.pairs_rule(kind, args, [tuple(idx(p)) for p in r["pairs"]])]
        if t == "cell":
            k = r["kind"]
            if k in ("odd", "even"):
                return [{"type": "parity", "parity": k, "cells": list(r["cells"])}]
            if k == "set":
                return [{"type": "digit_class", "digits": "".join(PJ._sym(v) for v in r["values"]), "cells": list(r["cells"])}]
            if k == "exclude":
                return [{"type": "exclude", "digit": v, "cells": list(r["cells"])} for v in r["values"]]
            return self.lowhigh(i, r, done)
        if t == "contains":
            return [{"type": "quadruple", "cells": list(r["cells"]), "digits": list(r["digits"])}]
        if t == "appears":
            return [{"type": "contains", "cells": [r["source"]] + list(r["cells"])}]
        if t == "clone":
            return [{"type": "clone", "regions": [list(x) for x in r["regions"]]}]
        if t == "isomorphic":
            return [{"type": "isomorphic", "pairs": [[a, b] for a, b in zip(*r["regions"])]}]
        if t == "count":
            if r.get("kind") == "circles":
                return [{"type": "counting_circles", "cells": list(r["cells"])}]
            con = {"type": "count", "cells": list(r["cells"])}
            if "each" in r:
                con["each"] = r["each"]
            else:
                con["digits"] = {str(d): k for d, k in r["counts"]}
            return [con]
        if t == "distinct_count":
            return [{"type": "distinct_count", "cells": list(r["cells"]), "count": r["value"]}]
        if t == "global_entropy":
            if D % 3:
                raise NotSupportedError("global entropy needs digits divisible by 3")
            return [{"type": "global_entropy"}]
        if t == "equal_sum":
            return [{"type": "equal_sum", "segments": [list(s) for s in r["segments"]]}]
        if t == "vudoku":
            return [{"type": "vudoku", "cells": list(r["cells"])}]
        if t == "table":
            allowed = [list(x) for x in r["allowed"]]
            if "cells" in r:
                return [{"type": "table", "cells": list(r["cells"]), "allowed": allowed}]
            out = []
            for (rr, cc) in sorted(B.cid):
                w = [(rr + dr, cc + dc) for dr, dc in r["where"]]
                if all(x in B.cid for x in w):
                    out.append({"type": "table", "cells": [cell_name(*x) for x in w], "allowed": allowed})
            return out
        if t == "negative":
            of = r["of"]
            if of == "rossini":
                return self.rossini(i, done)
            if of == "battenburg":
                return self.battenburg(i, done)
            if of == "cell":
                if r["kind"] in ("low", "high"):
                    return self.lowhigh(i, r, done)
                marked = {B.idx(c) for x in self.rules if x["type"] == "cell" and x["kind"] == r["kind"] for c in x["cells"]}
                scope = set(idx(r["cells"])) if "cells" in r else set(range(len(B.coords)))
                rest = [c for c in range(len(B.coords)) if c in scope and c not in marked]
                other = "even" if r["kind"] == "odd" else "odd"
                return [{"type": "parity", "parity": other, "cells": self.n(rest)}] if rest else []
            sel = r.get(NEG_SELECTOR[of])
            prs = self.negative_pairs(of, idx(r["cells"]) if "cells" in r else None)
            return [self.pairs_rule(kind, args, prs) for kind, args in negative_relation(of, sel, D) if prs]
        raise FormatError(f"unknown rule type {t!r}")

    def neighbours(self, r):
        B = self.B
        k = r.get("kind")
        scoped = "within" in r or "cells" in r or "except" in r
        if k and not scoped:
            return [{"type": k}]
        steps = {"antiknight": KNIGHT, "antiking": KING_DIAG, "nonconsecutive": ORTHO}.get(k) or NEIGHBOUR_STEPS[r["where"]]
        if k == "antiknight":
            steps = KNIGHT
        if not k and not ("within" in r or "cells" in r):
            out = {"type": "pairs", "rel": OPS[r["op"]], "params": _engine_params_json(OPS[r["op"]], _op_params_to_engine(r["op"], r["params"])),
                   "where": r["where"]}
            if r.get("except"):
                out["except"] = [list(p) for p in r["except"]]
            return [out]
        prs = B.pairs(steps, [B.idx(c) for c in r["cells"]] if "cells" in r else None)
        if r.get("within"):
            groups = self.boxes if r["within"] == "box" else self.regions
            prs = [(a, b) for a, b in prs if any(a in g and b in g for g in groups)]
        skip = {frozenset(B.idx(c) for c in p) for p in r.get("except") or []}
        prs = [(a, b) for a, b in prs if frozenset((a, b)) not in skip]
        if k:
            kind, args = ("nonconsec", ()) if k == "nonconsecutive" else ("neq", ())
        else:
            kind, args = OPS[r["op"]], _op_params_to_engine(r["op"], r["params"])
        return [self.pairs_rule(kind, args, prs)] if prs else []

    def rossini(self, i, done):
        B = self.B
        arrows, all_given = [], False
        for j, x in enumerate(self.rules):
            if x["type"] == "rossini":
                (r0, c0) = B.coords[B.idx(x["cells"][0])]
                side = x["side"]
                index = c0 + 1 if side in ("top", "bottom") else r0 + 1
                arrows.append({"side": side, "index": index, "towards": x["arrow"]})
                done.add(j)
            elif x["type"] == "negative" and x["of"] == "rossini":
                all_given = True
                done.add(j)
        if not (B.R == B.C == self.D and len(B.coords) == self.D ** 2):
            raise NotSupportedError("rossini is supported on a plain D x D board only")
        return [{"type": "rossini", "arrows": arrows, "all_given": all_given}]

    def battenburg(self, i, done):
        B, D = self.B, self.D
        marked, neg, scope = [], False, None
        for j, x in enumerate(self.rules):
            if x["type"] == "corner" and x["kind"] == "battenburg":
                marked.append([B.idx(c) for c in x["cells"]])
                done.add(j)
            elif x["type"] == "negative" and x["of"] == "battenburg":
                neg = True
                scope = set(B.idx(c) for c in x["cells"]) if "cells" in x else None
                done.add(j)
        T, F = battenburg_table(D, True), battenburg_table(D, False)
        if not neg:
            return [{"type": "table", "cells": self.n(w), "allowed": T} for w in marked]
        mk = {tuple(w) for w in marked}
        out = []
        for w in B.windows2x2():
            if self.subgrids and not any(set(w) <= s for s in self.subgrids):
                continue
            if scope is not None and not set(w) <= scope:
                continue
            out.append({"type": "table", "cells": self.n(w), "allowed": T if tuple(w) in mk else F})
        return out

    def lowhigh(self, i, r, done):
        B, D = self.B, self.D
        split = r["split"]
        hi_rules = [j for j, x in enumerate(self.rules) if x["type"] == "cell" and x["kind"] in ("low", "high") and x["split"] == split]
        negs = [j for j, x in enumerate(self.rules) if x["type"] == "negative" and x["of"] == "cell"
                and x.get("kind") in ("low", "high") and x.get("split") == split]
        if not negs:            # marked cells only: a digit-class clue
            k = r["kind"]
            vals = range(1, split + 1) if k == "low" else range(split + 1, D + 1)
            return [{"type": "digit_class", "digits": "".join(PJ._sym(v) for v in vals), "cells": list(r["cells"])}]
        neg = self.rules[negs[0]]
        done.update(hi_rules + negs)
        marked = {B.idx(c) for j in hi_rules for c in self.rules[j]["cells"] if self.rules[j]["kind"] == neg["kind"]}
        high = sorted(marked) if neg["kind"] == "high" else sorted(set(range(len(B.coords))) - marked)
        return [{"type": "lowhigh", "high": self.n(high), "split": split}]


def _engine_params_json(kind, args):
    if kind == "anyof":
        return [list(a) for a in args]
    if kind == "allowed":
        return [[list(x) for x in args[0]]]
    return list(args)


# ----------------------------------------------------------------------------------------------------------- writing
def write(p, meta=None, solution=None, provenance=False):
    """engine Puzzle -> sudoku-puzzle dict (format_version 1). Raises NotSupportedError for engine structures the format
    cannot express. provenance=True returns (doc, prov): prov[i] = the engine objects rule i was written from
    ({"groups", "relations", "constraints", "clues"}: indices into p.groups / p.relations / p.constraints / p.cell_clues)."""
    w = _Writer(p)
    doc = w.run(meta, solution)
    return (doc, w.prov) if provenance else doc


class _Writer:
    def __init__(self, p):
        self.p = p
        key = set(getattr(p, "iso_key", []) or [])
        self.key = key
        coords = [rc for i, rc in enumerate(p.coords) if i not in key]
        if key and sorted(key) != list(range(len(coords), len(p.coords))):
            raise NotSupportedError("twin digit-key cells must come last")
        self.B = Board(coords, p.D)
        self.D = p.D

    # ---------------------------------------------------------------- groups
    def eff_groups(self):
        """(kind, cells, total) per engine group, with the normalised kinds (ENGINE.md: jigsaw pieces stored as regions ->
        box; SudokuPad explicit houses -> row / column / box / region)."""
        p, B, D = self.p, self.B, self.D
        gs = [g for g in p.groups if not (self.key and set(g.cells) & self.key)]
        self.gidx = [k for k, g in enumerate(p.groups) if not (self.key and set(g.cells) & self.key)]
        out = []
        boxes = [g for g in gs if g.kind == "box"]
        cand = [g for g in gs if g.kind in ("region", "jigsaw") and g.complete and g.total is None and len(g.cells) == D
                and not self.straight(g.cells)]
        piece = set()
        if cand:
            allb = boxes + cand
            cover = [c for g in allb for c in g.cells]
            if len(cover) == len(set(cover)) == len(B.coords):
                piece = {id(g) for g in cand}
        for g in gs:
            kind = g.kind
            if id(g) in piece:
                kind = "box"
            elif kind in ("house", "partial"):
                st = self.straight(g.cells)
                kind = st if (st and len(g.cells) == D and g.complete) else ("box" if g.complete and len(g.cells) == D else "region")
            if g.total is not None and kind != "cage":
                kind = "cage"
            if len(g.cells) == D and not g.complete and kind != "cage":
                raise NotSupportedError("houses that need not hold every digit (digit-selection puzzles) are reserved")
            if g.complete and len(g.cells) != D:
                raise NotSupportedError(f"complete group of {len(g.cells)} cells on a {D}-digit board")
            out.append((kind, tuple(g.cells), g.total, g.complete))
        return out

    def straight(self, cells):
        co = [self.B.coords[c] for c in cells]
        if all(r == co[0][0] for r, _ in co) and [c for _, c in co] == list(range(co[0][1], co[0][1] + len(co))):
            return "row"
        if all(c == co[0][1] for _, c in co) and [r for r, _ in co] == list(range(co[0][0], co[0][0] + len(co))):
            return "col"
        return None

    def write_groups(self):
        """engine groups -> house / region / cage rules (FORMAT.md 6.1): every D x D area whose rows and columns are all
        houses is a box_grid (its boxes a regular tiling) or a grid, placed where its first own house was; the remaining
        rows / columns / boxes are explicit rules; regions and cages keep their place."""
        B, D = self.B, self.D
        gs = self.eff_groups()
        where = {}
        for k, (kind, cells, total, complete) in enumerate(gs):
            if kind in ("row", "col", "box") and total is None and complete and len(cells) == D:
                where.setdefault((kind, frozenset(cells)), []).append(k)
        cands = set()
        for (kind, fs) in where:
            if kind == "row":
                r, c = min(B.coords[x] for x in fs)
                cands |= {(r - k, c) for k in range(D)}
        grids = []
        for r0, c0 in cands:
            units = grid_units(B, r0, c0)
            if not units or not all((u[0], frozenset(u[1])) in where for u in units):
                continue
            box = None
            for shape in _factor_shapes(D):
                bu = grid_units(B, r0, c0, shape)[2 * D:]
                if all(("box", frozenset(u[1])) in where for u in bu):
                    box, units = shape, units + bu
                    break
            grids.append([None, r0, c0, box, units])
        share = Counter(frozenset(u[1]) for g in grids for u in g[4])
        for g in grids:         # order: first house that belongs to this grid only (overlapping grids share boxes)
            own = [u for u in g[4] if share[frozenset(u[1])] == 1] or g[4]
            g[0] = min(where[(u[0], frozenset(u[1]))][0] for u in own)
        grids.sort(key=lambda g: (g[0], g[1], g[2]))
        items, covered, used = [], set(), set()
        for first, r0, c0, box, units in grids:
            if all(frozenset(u[1]) in covered for u in units):
                continue
            covered |= {frozenset(u[1]) for u in units}
            gi = sorted(k for u in units for k in where[(u[0], frozenset(u[1]))] if k not in used)
            used |= set(gi)
            rule = {"type": "box_grid" if box else "grid", "origin": cell_name(r0, c0)}
            if box:
                rule["box"] = list(box)
            items.append((first, {"rule": rule, "area": grid_area(B, r0, c0), "units": units, "gi": gi}))
        seen = set(covered)
        self.merged_duplicates = len(used) - len(covered)
        for k, g in enumerate(gs):
            if k in used:
                continue
            kind, cells, total, _ = g
            if kind in ("row", "col", "box"):
                if frozenset(cells) in seen:
                    self.merged_duplicates += 1            # normalisation: a house listed twice is one house
                    continue
                seen.add(frozenset(cells))
            items.append((k, {"g": g, "gi": [k]}))
        items.sort(key=lambda kv: kv[0])
        rules = []
        self.group_prov = []
        self.subgrids = [it["area"] for _, it in items if "rule" in it]
        self.grid_areas = [(it["rule"]["origin"], it["area"]) for _, it in items if "rule" in it]
        self.box_sets = []
        for _, it in items:
            prov = {"groups": {self.gidx[k] for k in it["gi"]}}
            if "rule" in it:
                rules.append(it["rule"])
                self.box_sets += [set(u[1]) for u in it["units"] if u[0] == "box"]
            else:
                kind, cells, total, _ = it["g"]
                if kind == "box":
                    self.box_sets.append(set(cells))
                rules.append(self.group_rule(kind, cells, total))
            self.group_prov.append(prov)
        return rules

    def group_rule(self, kind, cells, total):
        B = self.B
        names = [B.name(c) for c in cells]
        if kind == "cage":
            r = {"type": "cage"}
            if total is not None:
                r["sum"] = total
            r["cells"] = names
            return r
        if kind in ("row", "col", "box"):
            return {"type": {"col": "column"}.get(kind, kind), "cells": names}
        if kind == "diag":
            return {"type": "region", "kind": "diagonal", "cells": names}
        if kind == "window":
            return {"type": "region", "kind": "window", "cells": names}
        return {"type": "region", "kind": "disjoint" if self.is_disjoint(cells) else "extra", "cells": names}

    def is_disjoint(self, cells):
        D = self.D
        if D not in PJ.BOXES or len(cells) != D or not (self.B.R == self.B.C == D):
            return False
        bh, bw = PJ.BOXES[D]
        co = [self.B.coords[c] for c in cells]
        return len({(r % bh, c % bw) for r, c in co}) == 1 and len({(r // bh, c // bw) for r, c in co}) == D

    # ---------------------------------------------------------------- run
    def run(self, meta, solution):
        p, B, D = self.p, self.B, self.D
        R, C = B.R, B.C
        flat = {i: rc[0] * C + rc[1] for i, rc in enumerate(B.coords)}
        givens = [None] * (R * C)
        for i in range(len(B.coords)):
            givens[flat[i]] = p.givens.get(i, 0)
        d = {"format": FORMAT, "format_version": FORMAT_VERSION}
        from .export import read_meta
        m = read_meta({"meta": meta or {}})
        if m:
            d["meta"] = m
        d.update({"board": {"rows": R, "cols": C}, "digits": D, "givens": givens})
        if solution is not None:
            sol = [None] * (R * C)
            for i, v in enumerate(list(solution)[:len(B.coords)]):
                sol[flat[i]] = int(v)
            d["solution"] = sol
        rules = self.write_groups()
        prov = list(self.group_prov)
        cands, clue_rules = self.cell_clues()
        rules += [r for r, _ in clue_rules]
        prov += [pr for _, pr in clue_rules]
        rest = self.write_rules()
        rules += [r for r, _ in rest]
        prov += [pr for _, pr in rest]
        rules, prov = _merge_negatives(rules, prov)
        if cands:
            d["candidates"] = cands
        d["rules"] = rules
        self.prov = prov
        return d

    def cell_clues(self):
        p, B, D = self.p, self.B, self.D
        n = len(B.coords)
        implied = [(1 << D) - 1] * len(p.domains)
        out = []
        for k, (r_, masks) in enumerate(getattr(p, "cell_clues", [])):
            for c_, m_ in masks.items():
                implied[c_] &= m_
            out += [(x, {"clues": {k}}) for x in self.clue_rule(r_)]
        cands = {}
        for i, m in enumerate(p.domains[:n]):
            if m != implied[i]:
                cands[B.name(i)] = [v for v in range(1, D + 1) if m >> (v - 1) & 1]
        return cands, out

    def clue_rule(self, r):
        B, D = self.B, self.D
        nm = lambda xs: [B.name(x) if isinstance(x, int) else x.lower() for x in xs]
        t = r["type"]
        if t == "parity":
            cells = nm(r["cells"])
            idx = [B.idx(c) for c in cells]
            if B.is_block(idx):
                return [{"type": "corner", "kind": "mathrax", "op": r["parity"], "cells": cells}]
            return [{"type": "cell", "kind": r["parity"], "cells": cells}]
        if t == "digit_class":
            return [{"type": "cell", "kind": "set", "values": [PJ._val(ch) for ch in str(r["digits"])], "cells": nm(r["cells"])}]
        if t == "exclude":
            cells = nm(r["cells"])
            if B.is_block([B.idx(c) for c in cells]):
                return [{"type": "corner", "kind": "exclude", "value": int(r["digit"]), "cells": cells}]
            return [{"type": "cell", "kind": "exclude", "values": [int(r["digit"])], "cells": cells}]
        if t == "lowhigh":
            split = int(r.get("split", (D + 1) // 2))
            return [{"type": "cell", "kind": "high", "split": split, "cells": nm(r.get("high", []))},
                    {"type": "negative", "of": "cell", "kind": "high", "split": split}]
        raise NotSupportedError(f"cell clue {t!r}")

    # ---------------------------------------------------------------- relations / constraints
    def write_rules(self):
        p, B, D = self.p, self.B, self.D
        rels = list(p.relations)
        cons = list(p.constraints)
        compiled = any(c.get("_compiled") for c in cons if c.get("type") in ("line", "clone"))
        drop_rel = [False] * len(rels)
        drop_con = [False] * len(cons)
        if compiled:
            comp, comp_cons, _ = PJ._compiled_extras(p)
            for k in range(len(rels) - 1, -1, -1):          # compiled relations come last (finalize appends them)
                if comp[rels[k]] > 0:
                    comp[rels[k]] -= 1
                    drop_rel[k] = True
            cc = Counter(comp_cons)
            for k in range(len(cons) - 1, -1, -1):
                key = json.dumps({a: b for a, b in cons[k].items() if not a.startswith("_")}, sort_keys=True, default=list)
                if cc[key] > 0:
                    cc[key] -= 1
                    drop_con[k] = True
        for k, c in enumerate(cons):
            if c.get("line_kind"):
                drop_con[k] = True
        # named rules (puzzle_json.add_named / from_json): their relations and constraints
        named_items = []
        used = [False] * len(rels)
        for rule, nrels in getattr(p, "named_rules", []):
            pos = None
            if nrels:
                L = len(nrels)
                for s in range(len(rels) - L + 1):
                    if not any(used[s:s + L]) and not any(drop_rel[s:s + L]) and rels[s:s + L] == list(nrels):
                        pos = s
                        break
                if pos is None:
                    raise NotSupportedError(f"named rule {rule.get('type')} relations not found")
                for s in range(pos, pos + len(nrels)):
                    used[s] = True
            named_items.append({"rule": rule, "rel": pos, "con": None, "nrel": len(nrels),
                                "prov": {"relations": set(range(pos, pos + len(nrels))) if nrels else set()}})
        nk = 0
        named_cons = [k for k, c in enumerate(cons) if c.get("_named") and not drop_con[k]]
        # assign named constraints to named rules in order (each named rule's constraints are contiguous)
        cursor = 0
        for it in named_items:
            n_c = self.named_cons_count(it["rule"])
            if n_c:
                if cursor + n_c > len(named_cons):
                    raise NotSupportedError(f"named rule {it['rule'].get('type')} constraints not found")
                it["con"] = named_cons[cursor]
                it["prov"]["constraints"] = set(named_cons[cursor:cursor + n_c])
                cursor += n_c
        self.family = self.family_positions(rels, [u or d for u, d in zip(used, drop_rel)], cons, drop_con)
        rel_items = self.relation_items(rels, [u or d for u, d in zip(used, drop_rel)])
        con_items = self.constraint_items(cons, drop_con)
        # merge the relation stream and the constraint stream; named rules with both link them
        sr = sorted([(x["pos"], "r", x) for x in rel_items] + [(it["rel"], "n", it) for it in named_items if it["rel"] is not None],
                    key=lambda z: z[0])
        sc = sorted([(x["pos"], "c", x) for x in con_items] + [(it["con"], "n", it) for it in named_items if it["con"] is not None],
                    key=lambda z: z[0])
        out = [(r, it["prov"]) for it in named_items if it["rel"] is None and it["con"] is None for r in self.named_rule(it["rule"])]
        emitted = set()
        i = j = 0
        def emit(kind, x):
            if kind == "n":
                if id(x) in emitted:
                    return
                emitted.add(id(x))
                out.extend((r, x["prov"]) for r in self.named_rule(x["rule"]))
            else:
                pr = {"relations": set(x.get("rel") or ()), "constraints": set(x.get("con") or ())}
                out.extend((r, pr) for r in x["rules"])
        while i < len(sr) or j < len(sc):
            while i < len(sr) and (sr[i][1] == "r" or id(sr[i][2]) in emitted):
                emit(sr[i][1], sr[i][2]); i += 1
            while j < len(sc) and (sc[j][1] == "c" or id(sc[j][2]) in emitted
                                   or sc[j][2]["rel"] is None):
                emit(sc[j][1], sc[j][2]); j += 1
            if i < len(sr):                       # a named rule with relations: its constraints (if any) are next in sc
                emit("n", sr[i][2]); i += 1
            elif j < len(sc):
                emit(sc[j][1], sc[j][2]); j += 1
        return out

    def named_cons_count(self, rule):
        t = rule.get("type")
        D, B = self.D, self.B
        if t == "global_entropy":
            return len(B.windows2x2())
        if t in ("quadruple", "vudoku"):
            return 1
        if t == "rossini":
            if not rule.get("all_given", True):
                return 0
            return 4 * D - len(rule.get("arrows", []))
        if t == "isomorphic":
            n = len(rule["pairs"]) if "pairs" in rule else D * D
            return n * D
        return 0

    def named_rule(self, rule):
        B, D = self.B, self.D
        t = rule["type"]
        nm = lambda xs: [B.name(x) if isinstance(x, int) else x.lower() for x in xs]
        if t == "global_entropy":
            return [{"type": "global_entropy"}]
        if t == "quadruple":
            return [{"type": "contains", "digits": [int(v) for v in rule["digits"]], "cells": nm(rule["cells"])}]
        if t == "vudoku":
            return [{"type": "vudoku", "cells": nm(rule["cells"])}]
        if t == "increasing":
            return [{"type": "line", "kind": "thermo", "cells": nm(rule["cells"])}]
        if t == "rossini":
            out = []
            for a in rule.get("arrows", []):
                cells = PJ._edge_line(None, D, a["side"], a["index"])[:3]
                out.append({"type": "rossini", "arrow": a.get("towards", "in"), "side": a["side"], "cells": [B.name(c) for c in cells]})
            if rule.get("all_given", True):
                out.append({"type": "negative", "of": "rossini"})
            return out
        if t == "isomorphic":
            if "pairs" in rule:
                prs = [(x.lower(), y.lower()) for x, y in rule["pairs"]]
            else:
                (r1, c1), (r2, c2) = rule["origins"]
                prs = [(cell_name(r1 + a, c1 + b), cell_name(r2 + a, c2 + b)) for a in range(D) for b in range(D)]
            return [{"type": "isomorphic", "regions": [[x for x, _ in prs], [y for _, y in prs]]}]
        raise NotSupportedError(f"named rule {t!r}")

    # ------------------------------------------------ relations
    def family_positions(self, rels, skip, cons, drop_con):
        """adjacent pairs carrying an edge clue, per family (for the negative exemptions)"""
        B, D = self.B, self.D
        fam = {}
        for k, rel in enumerate(rels):
            if skip[k]:
                continue
            kind, a, b, args = rel[0], rel[1], rel[2], tuple(rel[3:])
            if a in self.key or b in self.key or not B.adjacent(a, b):
                continue
            f = edge_family(kind, args, D)
            if f:
                fam.setdefault(f[0], set()).add(frozenset((a, b)))
        for k, c in enumerate(cons):
            if drop_con[k] or c.get("_named"):
                continue
            if c.get("type") == "table" and len(c["cells"]) == 2 and B.adjacent(*c["cells"]) and UNIFY_TABLE_EDGES:
                f = self.table_edge(c)
                if f:
                    fam.setdefault(f[0], set()).add(frozenset(c["cells"]))
        return fam

    def table_edge(self, c):
        """(family, value) of a 2-cell table that is an edge clue, or None"""
        m = _pair_clue(self.D, c["allowed"])
        if m is None:
            return None
        op, v = m
        # a table is a NUMBERED clue: never re-read as a kropki dot / XV letter
        return ({"x": "product", "+": "sum", "-": "difference", "/": "ratio"}[op], v)

    def relation_items(self, rels, skip):
        """runs of engine relations -> v1 rule items {"pos", "rules"} keeping the relation order"""
        B, D = self.B, self.D
        live = [k for k in range(len(rels)) if not skip[k]]
        for k in live:
            if rels[k][1] in self.key or rels[k][2] in self.key:
                raise NotSupportedError("relation on a twin digit-key cell")
        items = []
        # runs of identical (kind, args)
        runs, cur = [], []
        for k in live:
            sig = (rels[k][0], tuple(rels[k][3:]))
            if cur and (rels[cur[-1]][0], tuple(rels[cur[-1]][3:])) == sig:
                cur.append(k)
            else:
                if cur:
                    runs.append(cur)
                cur = [k]
        if cur:
            runs.append(cur)
        for run in runs:
            kind, args = rels[run[0]][0], tuple(rels[run[0]][3:])
            if kind not in REL_OP:
                raise NotSupportedError(f"engine relation {kind!r} has no format_version 1 operator")
            prs = [(rels[k][1], rels[k][2]) for k in run]
            pos = 0
            while pos < len(prs):
                hit = self.whole_rule(kind, args, prs, pos)
                if hit:
                    rule, n = hit
                    items.append({"pos": run[pos], "rules": [rule], "rel": run[pos:pos + n]})
                    pos += n
                    continue
                a, b = prs[pos]
                f = edge_family(kind, args, D) if B.adjacent(a, b) else None
                if f:
                    items.append({"pos": run[pos], "rules": [edge_rule(f[0], f[1], a, b, B)], "rel": [run[pos]]})
                else:
                    op = REL_OP[kind]
                    params = _engine_params_to_op(kind, args)
                    last = items[-1]["rules"][-1] if items else None
                    if last and last.get("type") == "relation" and last["op"] == op and last["params"] == params:
                        last["pairs"].append([B.name(a), B.name(b)])
                        items[-1]["rel"].append(run[pos])
                    else:
                        items.append({"pos": run[pos], "rel": [run[pos]],
                                      "rules": [{"type": "relation", "op": op, "params": params, "pairs": [[B.name(a), B.name(b)]]}]})
                pos += 1
        return items

    def ortho_in_subgrids(self):
        prs = self.B.pairs(ORTHO)
        if self.subgrids:
            sub_of = {}
            for k, s in enumerate(self.subgrids):
                for c in s:
                    sub_of.setdefault(c, set()).add(k)
            prs = [(a, b) for a, b in prs if sub_of.get(a, set()) & sub_of.get(b, set())]
        return prs

    def whole_rule(self, kind, args, prs, pos):
        """a neighbours / negative rule whose expansion is prs[pos:pos+n] (as a set) -> (rule, n) or None"""
        B, D = self.B, self.D
        rest = prs[pos:]
        fs = lambda L: {frozenset(x) for x in L}
        first = frozenset(rest[0])
        cands = []
        if kind == "neq" and not args:
            kn = B.pairs(KNIGHT)
            cands.append(({"type": "neighbours", "kind": "antiknight"}, kn))
            cands.append(({"type": "neighbours", "kind": "antiking"}, B.pairs(KING_DIAG)))
            if self.box_sets:
                cands.append(({"type": "neighbours", "kind": "antiknight", "within": "box"},
                              [(a, b) for a, b in kn if any(a in g and b in g for g in self.box_sets)]))
                cands.append(({"type": "neighbours", "kind": "antiking", "within": "box"},
                              [(a, b) for a, b in B.pairs(KING_DIAG) if any(a in g and b in g for g in self.box_sets)]))
        if kind == "nonconsec" and not args:
            cands.append(({"type": "neighbours", "kind": "nonconsecutive"}, B.pairs(ORTHO)))
        if len(self.grid_areas) > 1 and kind in ("neq", "nonconsec") and not args:     # the same rule on one grid only
            for nk, steps in (("antiknight", KNIGHT), ("antiking", KING_DIAG)) if kind == "neq" else (("nonconsecutive", ORTHO),):
                for org, area in self.grid_areas:
                    cands.append(({"type": "neighbours", "kind": nk, "area": org}, B.pairs(steps, sorted(area))))
        neg = {("nonconsec", ()): ("kropki", "white"), ("notdiff", (1,)): ("kropki", "white"),
               ("notratio", (2,)): ("kropki", "black"), ("notsum", (10,)): ("xv", "X"), ("notsum", (5,)): ("xv", "V")}
        key = (kind, args)
        nf = neg.get(key)
        if nf is None and len(args) == 1 and kind in ("notdiff", "notsum", "notratio"):
            nf = ({"notdiff": "difference", "notsum": "sum", "notratio": "ratio"}[kind], args[0])
        if nf:
            of, sel = nf
            exempt = self.family.get(of, set())
            exp = [(a, b) for a, b in self.ortho_in_subgrids() if frozenset((a, b)) not in exempt]
            rule = {"type": "negative", "of": of, NEG_SELECTOR[of]: sel}
            if kind == "nonconsec" and not exempt and fs(exp) == fs(B.pairs(ORTHO)):
                pass                      # plain non-consecutive: the neighbours rule above
            else:
                cands.append((rule, exp))
            if len(self.grid_areas) > 1:  # the negative on one grid only
                for org, area in self.grid_areas:
                    cands.append((dict(rule, area=org), [(a, b) for a, b in exp if a in area and b in area]))
        for rule, exp in cands:
            n = len(exp)
            if n and n <= len(rest) and first in fs(exp) and fs(rest[:n]) == fs(exp):
                return rule, n
        # generic whole-grid rule with exceptions (the old "pairs where" form), symmetric relations only
        if pos == 0 and len(prs) >= 12 and PJ._symmetric(kind, list(args), D) and kind not in ("anyof",):
            have = fs(prs)
            if len(have) == len(prs):
                for where, steps in NEIGHBOUR_STEPS.items():
                    alln = B.pairs(steps)
                    if have <= fs(alln) and len(have) * 2 > len(alln):
                        # must expand in the same order: the where-form expands in board order minus the exceptions
                        missing = [x for x in alln if frozenset(x) not in have]
                        exp = [x for x in alln if frozenset(x) in have]
                        if [frozenset(x) for x in exp] == [frozenset(x) for x in prs]:
                            rule = {"type": "neighbours", "op": REL_OP[kind], "params": _engine_params_to_op(kind, args), "where": where}
                            if missing:
                                rule["except"] = [[B.name(a), B.name(b)] for a, b in missing]
                            return rule, len(prs)
        return None

    # ------------------------------------------------ constraints
    def constraint_items(self, cons, drop):
        B, D = self.B, self.D
        items = []
        k = 0
        live = [i for i in range(len(cons)) if not drop[i] and not cons[i].get("_named")]
        # tables: battenburg blocks / global entropy blocks are detected over runs
        i = 0
        while i < len(live):
            c = cons[live[i]]
            t = c.get("type")
            if any(x in self.key for x in self.con_cells(c)):
                raise NotSupportedError("constraint on a twin digit-key cell")
            if "offset" in c:
                raise NotSupportedError("shifted digit sets (digit-selection puzzles) are reserved")
            if t == "table":
                blk = self.table_block(cons, live, i)
                if blk:
                    rules, n = blk
                    items.append({"pos": live[i], "rules": rules, "con": live[i:i + n]})
                    i += n
                    continue
            if t == "arrow":
                j = i
                lines = []
                while j < len(live) and cons[live[j]].get("type") == "arrow" and cons[live[j]]["circle"] == c["circle"]:
                    lines.append([B.name(x) for x in cons[live[j]]["line"]])
                    j += 1
                items.append({"pos": live[i], "rules": [{"type": "arrow", "bulb": [B.name(x) for x in c["circle"]], "lines": lines}],
                              "con": live[i:j]})
                i = j
                continue
            items.append({"pos": live[i], "rules": self.constraint_rule(c), "con": [live[i]]})
            i += 1
        return items

    def con_cells(self, c):
        out = list(c.get("cells") or []) + list(c.get("circle") or []) + list(c.get("line") or [])
        for k in ("segments", "regions", "houses"):
            for s in c.get(k) or []:
                out += list(s)
        return [x for x in out if isinstance(x, int)]

    def table_block(self, cons, live, i):
        """global entropy (all 2x2 windows, exact table) or battenburg (every window of the subgrids marked / unmarked) at
        live[i:], or a single table that is a known mechanic -> (rules, n) or None"""
        B, D = self.B, self.D
        c = cons[live[i]]
        cells = list(c["cells"])
        A = [tuple(x) for x in c["allowed"]]
        wins = B.windows2x2()
        if len(cells) == 4 and D % 3 == 0 and wins and cells == wins[0]:
            ent = [tuple(x) for x in PJ.entropy_table(D)]
            n = len(wins)
            if i + n <= len(live) and all(cons[live[i + k]].get("type") == "table" and list(cons[live[i + k]]["cells"]) == wins[k]
                                          and [tuple(x) for x in cons[live[i + k]]["allowed"]] == ent for k in range(n)):
                return [{"type": "global_entropy"}], n
        if len(cells) == 4 and B.is_block(cells):
            T, F = _bat(D)
            if A in (T, F):
                ws = [w for w in wins if not self.subgrids or any(set(w) <= s for s in self.subgrids)]
                n = len(ws)
                if cells == ws[0] and i + n <= len(live):
                    blk = [cons[live[i + k]] for k in range(n)]
                    if all(x.get("type") == "table" and list(x["cells"]) == ws[k] and [tuple(y) for y in x["allowed"]] in (T, F)
                           for k, x in enumerate(blk)):
                        rules = [{"type": "corner", "kind": "battenburg", "cells": [B.name(y) for y in ws[k]]}
                                 for k, x in enumerate(blk) if [tuple(y) for y in x["allowed"]] == T]
                        return rules + [{"type": "negative", "of": "battenburg"}], n
                if A == T:
                    return [{"type": "corner", "kind": "battenburg", "cells": [B.name(y) for y in cells]}], 1
        if len(cells) == 2 and B.adjacent(*cells) and UNIFY_TABLE_EDGES:
            f = self.table_edge(c)
            if f:                               # normalisation 8: a 2-cell table edge clue -> pair relation
                return [edge_rule(f[0], f[1], cells[0], cells[1], B)], 1
        # mathrax corner: tables on (TL, BR) then (TR, BL) of a 2x2 block with the same clue
        if len(cells) == 2 and i + 1 < len(live) and cons[live[i + 1]].get("type") == "table" and UNIFY_TABLE_EDGES:
            c2 = cons[live[i + 1]]
            if len(c2["cells"]) == 2:
                tl, br = cells
                tr, bl = c2["cells"]
                blk = [tl, tr, bl, br]
                if B.is_block(blk):
                    m1, m2 = self.mathrax_clue(c), self.mathrax_clue(c2)
                    if m1 and m1 == m2:
                        return [{"type": "corner", "kind": "mathrax", "op": m1[0], "value": m1[1], "cells": [B.name(x) for x in blk]}], 2
        if len(cells) == 3 and A == [tuple(x) for x in vudoku_table(D)]:
            return [{"type": "vudoku", "cells": [B.name(x) for x in cells]}], 1
        if len(cells) == 4 and B.is_block(cells):        # the quadruple clue (other tables that happen to match stay tables)
            need = self.quadruple_need(A, len(cells))
            if need is not None:
                return [{"type": "contains", "digits": need, "cells": [B.name(x) for x in cells]}], 1
        return None

    def mathrax_clue(self, c):
        return _pair_clue(self.D, c["allowed"])

    def quadruple_need(self, A, n):
        D = self.D
        if not A or len(A) == D ** n:
            return None
        need = []
        for v in range(1, D + 1):
            k = min(t.count(v) for t in A)
            need += [v] * k
        if not need or len(need) > n:
            return None
        if [tuple(x) for x in PJ.quadruple_table(D, n, need)] == A:
            return need
        return None

    def constraint_rule(self, c):
        B, D = self.B, self.D
        t = c.get("type")
        nm = lambda xs: [B.name(x) for x in xs]
        if t == "line":
            kind = c["kind"]
            cells = list(c["cells"])
            if kind == "kropki_chain":                  # normalisation 4: kropki edges
                dots = c.get("dots") or ["white"] * (len(cells) - 1)
                return [edge_rule("kropki", d_, a, b, B) for (a, b), d_ in zip(zip(cells, cells[1:]), dots)]
            r = {"type": "line", "kind": "whisper" if kind == "dutch_whisper" else kind}
            if kind in ("whisper", "dutch_whisper"):
                if "k" in c or kind == "dutch_whisper" or D != 9:
                    r["value"] = c.get("k", 5 if kind == "whisper" else 4)
            if kind == "modular" and D != 9:
                r["value"] = 3
            if kind == "entropic" and D != 9:
                third = lambda v: (v - 1) * 3 // D if D % 3 == 0 else (v - 1) // 3
                r["groups"] = [[v for v in range(1, D + 1) if third(v) == g] for g in range(3)]
            if len(cells) > 2 and cells[0] == cells[-1] and kind in ("whisper", "dutch_whisper", "parity"):
                r["closed"] = True
                cells = cells[:-1]
            r["cells"] = nm(cells)
            return [r]
        if t == "sum":
            cells = list(c["cells"])
            common = self.common_group(cells)
            if c.get("distinct") and not common:        # normalisation 9: a no-repeat sum is a cage
                return [{"type": "cage", "sum": c["total"], "cells": nm(cells)}]
            side = B.outside_side(cells) if len(cells) >= 2 else None
            if side and len(cells) < D and B.outside_ok(side, cells, False):
                return [{"type": "sum", "kind": "frame", "sum": c["total"], "side": side, "cells": nm(cells)}]
            if B.is_block(cells):
                return [{"type": "sum", "kind": "corner", "sum": c["total"], "cells": nm(cells)}]
            return [{"type": "sum", "kind": "group", "sum": c["total"], "cells": nm(cells)}]
        if t == "little_killer":
            cells = list(c["cells"])
            side = B.outside_side(cells)
            if side is None:
                raise NotSupportedError("little killer whose diagonal does not start at the edge of the board")
            return [{"type": "sum", "kind": "little_killer", "sum": c["total"], "side": side, "cells": nm(cells)}]
        if t in ("sandwich", "xsum", "skyscraper", "first_seen"):
            cells = list(c["cells"])
            side = B.outside_side(cells)
            if side is None or not B.outside_ok(side, cells, False):
                raise NotSupportedError(f"{t} clue whose cells do not start at the edge of the board")
            r = {"type": t}
            if t in ("sandwich", "xsum"):
                r["sum"] = c["total"]
            elif t == "skyscraper":
                r["value"] = c["count"]
            else:
                r["value"] = c["value"]
                r["digits"] = list(c.get("digits") or [1, 2, 3])
            r["side"] = side
            r["cells"] = nm(cells)
            return [r]
        if t == "set":
            if c.get("kind") != "consecutive":
                raise NotSupportedError(f"set constraint of kind {c.get('kind')!r}")
            cells = list(c["cells"])
            if all(B.touching(a, b) for a, b in zip(cells, cells[1:])):
                return [{"type": "line", "kind": "renban", "cells": nm(cells)}]          # normalisation 1
            raise NotSupportedError("a consecutive set whose cells are not a line")
        if t == "between":
            cells = list(c["cells"])
            if all(B.touching(a, b) for a, b in zip(cells, cells[1:])):
                return [{"type": "line", "kind": "between", "cells": nm(cells)}]         # normalisation 2
            raise NotSupportedError("a between constraint whose cells are not a line")
        if t == "equal_sum":
            return [self.equal_sum_rule(c)]
        if t == "table":
            return [{"type": "table", "cells": nm(c["cells"]), "allowed": [list(x) for x in c["allowed"]]}]
        if t == "count":
            r = {"type": "count"}
            if "each" in c:
                r["each"] = c["each"]
            else:
                r["counts"] = sorted([int(k), v] for k, v in c["digits"].items())
            r["cells"] = nm(c["cells"])
            return [r]
        if t == "counting_circles":
            return [{"type": "count", "kind": "circles", "cells": nm(c["cells"])}]
        if t == "distinct_count":
            cells = list(c["cells"])
            r = {"type": "distinct_count", "value": c["count"]}
            side = B.outside_side(cells) if len(cells) >= 2 else None
            if side:
                r["side"] = side
            r["cells"] = nm(cells)
            return [r]
        if t == "contains":
            return [{"type": "appears", "source": B.name(c["cells"][0]), "cells": nm(c["cells"][1:])}]
        if t == "clone":
            return [{"type": "clone", "regions": [nm(x) for x in c["regions"]]}]
        raise NotSupportedError(f"engine constraint {t!r} has no format_version 1 rule")

    def common_group(self, cells):
        s = set(cells)
        return any(s <= set(g.cells) for g in self.p.groups)

    def equal_sum_rule(self, c):
        B = self.B
        segs = [list(s) for s in c["segments"]]
        flat = [x for s in segs for x in s]
        path = lambda xs: all(B.touching(a, b) for a, b in zip(xs, xs[1:]))
        nm = lambda xs: [B.name(x) for x in xs]
        # zipper: pairs (ids[k], ids[n-1-k]) then the middle cell
        n = len(flat)
        pairs = [s for s in segs if len(s) == 2]
        mid = [s for s in segs if len(s) == 1]
        if len(pairs) == n // 2 and len(mid) == n % 2 and segs == pairs + mid and len(set(flat)) == n:
            ids = [None] * n
            for k, (a, b) in enumerate(pairs):
                ids[k], ids[n - 1 - k] = a, b
            if mid:
                ids[n // 2] = mid[0][0]
            if path(ids):
                return {"type": "line", "kind": "zipper", "cells": nm(ids)}                 # normalisation 3
        # double arrow: [[a, b], middle]
        if len(segs) == 2 and len(segs[0]) == 2 and segs[1]:
            ids = [segs[0][0]] + segs[1] + [segs[0][1]]
            if path(ids):
                return {"type": "line", "kind": "double_arrow", "cells": nm(ids)}
        # region sum: the segments are the line cut at box borders
        if path(flat) and len(set(flat)) == n:
            box = {cc: gi for gi, g in enumerate(self.p.groups) if g.complete and g.kind in ("box", "region", "jigsaw") for cc in g.cells}
            cut, cur = [], [flat[0]]
            for x in flat[1:]:
                if box.get(x) == box.get(cur[-1]):
                    cur.append(x)
                else:
                    cut.append(cur)
                    cur = [x]
            cut.append(cur)
            if cut == segs:
                return {"type": "line", "kind": "region_sum", "cells": nm(flat)}            # normalisation 3
        return {"type": "equal_sum", "segments": [nm(s) for s in segs]}


# --------------------------------------------------------------------------------------------- canonical text + hash
KEY_ORDER = ["format", "format_version", "$schema", "meta", "board", "digits", "givens", "solution", "candidates", "rules",
             "decorations", "style", "ext"]
RULE_ORDER = ["type", "kind", "of", "op", "params", "color", "letter", "value", "sum", "split", "values", "digits", "groups",
              "each", "counts", "arrow", "size", "repeat", "box", "where", "within", "area", "closed", "side", "origin", "source",
              "bulb", "lines", "cells", "regions", "segments", "pairs", "except", "allowed", "id", "label", "style"]


def _order(d, order):
    pos = {k: i for i, k in enumerate(order)}
    return {k: d[k] for k in sorted(d, key=lambda k: (pos.get(k, len(pos)), k))}


def canonical(doc):
    """key order of FORMAT.md 8.1 (content unchanged)"""
    out = _order(doc, KEY_ORDER)
    if "rules" in out:
        out["rules"] = [_order(r, RULE_ORDER) for r in out["rules"]]
    if "candidates" in out:
        def rc(k):
            r, c = parse_cell(k)
            return (r, c)
        out["candidates"] = {k: sorted(v) for k, v in sorted(out["candidates"].items(), key=lambda kv: rc(kv[0]))}
    return out


def dumps(doc, pretty=True):
    """canonical JSON text: fixed key order; pretty: givens / solution one grid row per line, one rule per line."""
    d = canonical(doc)
    if not pretty:
        return json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    C = d.get("board", {}).get("cols") or 1
    j = lambda x: json.dumps(x, ensure_ascii=False, separators=(", ", ": "))
    lines = []
    keys = list(d)
    for n, k in enumerate(keys):
        v = d[k]
        end = "," if n < len(keys) - 1 else "}"
        pre = "{" if n == 0 else " "
        if k in ("givens", "solution") and isinstance(v, list):
            rows = [", ".join("null" if x is None else str(x) for x in v[i:i + C]) for i in range(0, len(v), C)]
            lines.append(f'{pre}"{k}": [\n' + ",\n".join("    " + r for r in rows) + "]" + end)
        elif k == "rules" and isinstance(v, list):
            lines.append(f'{pre}"{k}": [' + ("\n" + ",\n".join("  " + j(r) for r in v) if v else "") + "]" + end)
        else:
            lines.append(f"{pre}{j(k)}: {j(v)}{end}")
    return "\n".join(lines) + "\n"


def jcs(x):
    """RFC 8785 JSON canonicalization for the values the fingerprint covers (integers, strings, lists, objects with ASCII
    keys, booleans, null): sorted keys, no whitespace, UTF-8."""
    if isinstance(x, float):
        if x != int(x):
            raise ValueError("non-integer numbers are not part of a fingerprint")
        x = int(x)
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


SET_TYPES = {"region", "cage", "cell", "contains", "appears", "count", "box", "row", "column", "negative", "neighbours"}


def _rc(name):
    return parse_cell(name)


def _norm_rule(r, D):
    """spelling-free form of one rule for the fingerprint: cell sets sorted, symmetric pairs sorted"""
    r = {k: v for k, v in r.items() if k not in ("id", "label", "style")}
    srt = lambda xs: sorted((x.lower() for x in xs), key=_rc)
    t = r["type"]
    if t in SET_TYPES or (t == "sum" and r.get("kind") in ("group", "corner")) or (t == "distinct_count" and "side" not in r) \
            or (t == "edge" and r.get("kind") != "less"):
        if "cells" in r:
            r["cells"] = srt(r["cells"])
    if t == "equal_sum":
        r["segments"] = sorted((srt(x) for x in r["segments"]), key=lambda x: [_rc(c) for c in x])
    if "except" in r:
        r["except"] = sorted((srt(p) for p in r["except"]), key=lambda x: [_rc(c) for c in x])
    if t == "relation" and r["op"] not in DIRECTED_OPS:
        r["pairs"] = sorted((srt(p) for p in r["pairs"]), key=lambda x: [_rc(c) for c in x])
    return r


def semantic_subset(doc):
    """the fingerprinted content: board, digits, givens, candidates and rules, with the houses replaced by the houses they
    state (grid, box_grid, box / row / column rules), so every spelling of the same houses gives
    the same result, and set-like cell lists sorted"""
    keep = {k: doc[k] for k in ("format", "format_version", "digits", "givens", "candidates") if k in doc}
    keep["board"] = {"rows": doc["board"]["rows"], "cols": doc["board"]["cols"]}
    D = doc.get("digits")
    B = Board([divmod(k, doc["board"]["cols"]) for k, v in enumerate(doc["givens"]) if v is not None], D)
    HT = ("grid", "box_grid", "box", "row", "column")
    houses, _ = read_houses([r for r in doc.get("rules", []) if r["type"] in HT], B)
    B.grid_origins = {r["origin"] for r in doc.get("rules", []) if r["type"] in ("grid", "box_grid")}
    rules = [_norm_rule(r, D) for r in resolve_areas(B, doc.get("rules", [])) if r["type"] not in HT]
    hs = {(k, tuple(sorted((B.name(c) for c in cells), key=_rc))) for k, cells, _ in houses}
    rules += [{"type": {"col": "column"}.get(k, k), "cells": list(c)} for k, c in hs]
    keep["rules"] = sorted(rules, key=lambda r: jcs(r))
    return keep


def fingerprint_of_doc(doc):
    """SHA-256 of the JCS form of the semantic subset of an already canonical sudoku-puzzle dict"""
    return "sha256:" + hashlib.sha256(jcs(semantic_subset(doc)).encode("utf-8")).hexdigest()
