"""The board: cells, houses, areas, and the digit tables some rules expand to."""

from __future__ import annotations

import itertools

from .. import model as M
from .. import puzzle_json as PJ
from .common import SIDES, FormatError, cell_name, parse_cell


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
        """cell index i -> its name (r1c1)"""
        return cell_name(*self.coords[i])

    def idx(self, name):
        """cell name -> index; FormatError if it is not a cell of the board"""
        rc = parse_cell(name)
        if rc not in self.cid:
            raise FormatError(f"cell {name} does not exist (null in givens or outside the grid)")
        return self.cid[rc]

    def adjacent(self, a, b):
        """True if cells a and b share an edge"""
        (r1, c1), (r2, c2) = self.coords[a], self.coords[b]
        return abs(r1 - r2) + abs(c1 - c2) == 1

    def touching(self, a, b):
        """True if cells a and b touch by an edge or a corner"""
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
        for r, c in sorted(self.cid):
            w = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
            if all(x in self.cid for x in w):
                out.append([self.cid[x] for x in w])
        return out

    def is_block(self, cells):
        """True if the four cells are a 2x2 block written TL, TR, BL, BR"""
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
            if any(
                (self.coords[b][0] - self.coords[a][0], self.coords[b][1] - self.coords[a][1]) != (dr, dc)
                for a, b in zip(cells, cells[1:])
            ):
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
        """True if check_outside accepts cells on that side"""
        try:
            self.check_outside(side, cells, diagonal_ok)
            return True
        except FormatError:
            return False

    def check_outside(self, side, cells, diagonal_ok=True, what="outside clue"):
        """raise FormatError unless cells start just outside the grid on side and run away from it
        (diagonally too when diagonal_ok)"""
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
    units = [("row", tuple(grid[i * n : (i + 1) * n])) for i in range(n)]
    units += [("col", tuple(grid[j::n])) for j in range(n)]
    if box:
        bh, bw = box
        units += [
            ("box", tuple(grid[(br + a) * n + bc + b] for a in range(bh) for b in range(bw)))
            for br in range(0, n, bh)
            for bc in range(0, n, bw)
        ]
    return units


def window(B, r0, c0, n):
    """indices of the n x n cells with top-left corner (r0, c0); None if one is missing"""
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
    out = [("row", tuple(grid[i * D : (i + 1) * D])) for i in range(D)]
    out += [("col", tuple(grid[j::D])) for j in range(D)]
    if box:
        bh, bw = box
        out += [
            ("box", tuple(grid[(br + a) * D + bc + b_] for a in range(bh) for b_ in range(bw)))
            for br in range(0, D, bh)
            for bc in range(0, D, bw)
        ]
    return out


def grid_area(B, r0, c0):
    """set of the cell indices in the D x D square with top-left corner (r0, c0)"""
    return {B.cid[(r, c)] for r in range(r0, r0 + B.D) for c in range(c0, c0 + B.D)}


def read_houses(rules, B):
    """the house groups a rule list states, in engine order -> (houses [(kind, cells, extra)], areas [cell sets])
    (docs/rules/houses-and-regions.mdx, 6.1): grid / box_grid / box / row / column rules in file order, a house equal to an earlier one skipped;
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
    """allowed 2x2 digit tuples (TL, TR, BL, BR) of a battenburg window, marked or unmarked"""
    return [
        list(t)
        for t in itertools.product(range(1, D + 1), repeat=4)
        if _cb(t) == marked and t[0] != t[1] and t[0] != t[2] and t[1] != t[3] and t[2] != t[3]
    ]


def vudoku_table(D):
    """allowed (x, y, z) triples: x is y + z or |y - z|"""
    return [(x, y, z) for y in range(1, D + 1) for z in range(1, D + 1) for x in {y + z, abs(y - z)} if 1 <= x <= D]


def product_pairs(D, p):
    """digit pairs [u, v] in 1..D with u * v == p"""
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
        _CACHE[("bat", D)] = (
            [tuple(x) for x in battenburg_table(D, True)],
            [tuple(x) for x in battenburg_table(D, False)],
        )
    return _CACHE[("bat", D)]


_MATHRAX_OK = {
    "+": lambda v: lambda x, y: x + y == v,
    "-": lambda v: lambda x, y: abs(x - y) == v,
    "/": lambda v: lambda x, y: max(x, y) == v * min(x, y),
    "x": lambda v: lambda x, y: x * y == v,
}
_NUMBERED_OK = {
    "difference": lambda r: _MATHRAX_OK["-"](r["value"]),
    "sum": lambda r: _MATHRAX_OK["+"](r["sum"]),
    "ratio": lambda r: _MATHRAX_OK["/"](r["value"]),
    "product": lambda r: _MATHRAX_OK["x"](r["value"]),
}
