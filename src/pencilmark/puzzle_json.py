"""Puzzle <-> JSON: the storage / exchange format for any sudoku the engine supports.

Minimal (classic, any standard size; boxes implied):
    {"numbers": "..3.2.6..9..3.5..1..18.64...."}          # '.' or '0' blank, 1-9 then A-Z above 9
Full form (every field optional except what the puzzle needs):
    {
     "digits": 9,                                          # D: digits 1..D
     "shape": ["#########.....", ...],                     # cells on the bounding grid: '#' cell, '.' void
                                                           #   (omit for a full D x D board)
     "box": "3x3",                                         # implied rows / columns / boxes of a D x D board
     "layout": "samurai",                                  # implied regions of a named multi-grid layout
     "numbers": "...",                                     # givens, row-major over the bounding grid ('#' = void)
     "solution": "...",
     "regions": [{"kind": "row|col|box|region|diag|window|cage|extra", "cells": ["r1c1", ...],
                  "sum": 15, "unique": true}, ...],       # explicit no-repeat groups (when not implied)
     "rules": [{"type": "kropki", "color": "white", "cells": ["r1c1", "r1c2"]},
               {"type": "line", "kind": "thermo", "cells": [...]},     # any engine line kind, bulb first
               {"type": "antiknight"}, {"type": "antiking"}, {"type": "nonconsecutive"},
               {"type": "frame", "side": "top", "index": 3, "sum": 12},              # first 3 cells from that edge
               {"type": "rossini", "arrows": [{"side": "left", "index": 2, "towards": "in"}], "all_given": true},
               {"type": "vudoku", "cells": ["r2c2", "r3c1", "r3c3"]},   # vertex = sum or difference of the arms
               {"type": "lowhigh", "high": ["r1c1", ...], "split": 5},  # marked 6..9, the rest 1..5
               {"type": "parity", "parity": "odd", "cells": [...]},    # shaded odd / even cells (graphical)
               {"type": "digit_class", "digits": "123", "cells": [...]},  # cells marked as holding one of these digits
               {"type": "exclude", "digit": 5, "cells": [...]},         # a circle: its digit is in none of these cells
               {"type": "increasing", "cells": [...]},
               (Bold X / Snowflake / Argyle / Asterisk ...: their lines or cells as extra "regions")
               {"type": "pairs", "rel": "notdiff", "params": [1], "cells": [["r1c1", "r1c2"], ...]},
               {"type": "pairs", "rel": "notsum", "params": [10], "where": "orthogonal", "except": [["r1c1", "r1c2"]]},
                                                          # whole-grid pair rule: every orthogonal / diagonal / king / knight
                                                          # neighbour pair except those listed (e.g. "no X where not marked")
               {"type": "<engine constraint>", ...}, ...],               # arrow, sum, little_killer, sandwich ...
     "candidates": {"r1c1": "137"},                       # given pencil marks (Sukaku); shaded clues are rules above
     "meta": {"title": "...", "author": "...", "rules_text": "...", "source": "...", "id": "..."}}
                                                          # optional metadata, never used for solving (older files: top level)
Cells are 'r{row}c{col}', 1-based on the bounding grid. Regions are the no-repeat groups (for each sub-grid its rows,
columns and boxes); boxes are what a renderer draws with thick lines. Rows / columns / boxes of a D x D board (or a
named layout) are implied unless "regions" overrides them.
  from_json(obj or str) -> Puzzle (not finalized)      to_json(Puzzle) -> dict      canonical_hash(obj) -> md5
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter

from . import model as M

BOXES = {4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3), 10: (2, 5), 12: (3, 4), 14: (2, 7), 15: (3, 5), 16: (4, 4),
         20: (4, 5), 25: (5, 5)}
SIZES = {n * n: n for n in BOXES}
CELL_KEYS = ("cells", "line", "circle")          # constraint keys holding a cell list
NESTED_KEYS = ("segments", "regions", "houses")  # ... a list of cell lists
SYMBOLS = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _sym(v):
    return SYMBOLS[v - 1]


def _val(ch):
    return None if ch in ".0-_#" else SYMBOLS.index(ch.upper()) + 1


# ---------------------------------------------------------------- layouts
LAYOUT_FILE = None


def _layouts():
    """name -> 9x9 sub-grid origins. Exact geometries extracted from sudoku.one solutions plus a few aliases."""
    global LAYOUT_FILE
    if LAYOUT_FILE is None:
        import os
        from . import _data
        f = "layouts_sudoku_one.json"
        LAYOUT_FILE = {k: [tuple(o) for o in v["origins"]] for k, v in _data.load_json(f).items()} if _data.exists(f) else {}
        LAYOUT_FILE.setdefault("samurai", [(0, 0), (0, 12), (6, 6), (12, 0), (12, 12)])
        LAYOUT_FILE.setdefault("twodoku", [(0, 0), (6, 6)])
        for alias, name in (("gattai-3", "wing-3"), ("kazaguruma", "windmill"), ("flower", "flower-4"), ("tripledoku", "tridoku"),
                            ("gattai-5", "samurai"), ("supersamurai", "super-samurai"), ("clueless", "clueless-1")):
            if name in LAYOUT_FILE:
                LAYOUT_FILE.setdefault(alias, LAYOUT_FILE[name])
    return LAYOUT_FILE


def _layout_origins(name):
    return _layouts().get(name.lower())


def _layout_extra(name, coords):
    """Grids that are not contiguous 9x9 windows (from the layouts' rules): Clueless 1 = the centre CELL of every box
    of the 9 grids forms a 10th grid; Clueless 2 = the centre BOX of each grid forms a 10th grid. -> list of
    [(row, col) * 81] in reading order of the extra grid."""
    n = name.lower()
    if n in ("clueless-1", "clueless"):
        return [[(3 * R + 1, 3 * C + 1) for R in range(9) for C in range(9)]]
    if n == "clueless-2":
        return [[(9 * (R // 3) + 3 + R % 3, 9 * (C // 3) + 3 + C % 3) for R in range(9) for C in range(9)]]
    return []


def _layout_regions(origins, D=9, bh=3, bw=3):
    """rows / columns / boxes of D x D sub-grids at origins -> (coords, groups) with shared cells merged."""
    cid, coords = {}, []
    for (o_r, o_c) in origins:
        for r in range(D):
            for c in range(D):
                if (o_r + r, o_c + c) not in cid:
                    cid[(o_r + r, o_c + c)] = len(coords)
                    coords.append((o_r + r, o_c + c))
    groups, seen = [], set()
    for k, (o_r, o_c) in enumerate(origins):
        units = [("row", [(o_r + r, o_c + c) for c in range(D)]) for r in range(D)]
        units += [("col", [(o_r + r, o_c + c) for r in range(D)]) for c in range(D)]
        units += [("box", [(o_r + br + i, o_c + bc + j) for i in range(bh) for j in range(bw)])
                  for br in range(0, D, bh) for bc in range(0, D, bw)]
        for kind, cells in units:
            ids = tuple(cid[x] for x in cells)
            if frozenset(ids) not in seen:
                seen.add(frozenset(ids))
                groups.append(M.Group(f"g{k}{kind}{len(groups)}", ids, kind, True))
    return coords, groups


# ---------------------------------------------------------------- decode
def from_json(obj) -> M.Puzzle:
    d = json.loads(obj) if isinstance(obj, str) else dict(obj)
    nums = re.sub(r"\s+", "", d.get("numbers", "") or "")
    layout = d.get("layout")
    if layout:
        origins = _layout_origins(layout)
        if origins is None:
            raise ValueError(f"unknown layout {layout!r}")
        D = int(d.get("digits", 9))
        bh, bw = BOXES[D]
        coords, groups = _layout_regions(origins, D, bh, bw)
        cid_ = {rc: k for k, rc in enumerate(coords)}
        for g10 in _layout_extra(layout, coords):
            ids = [cid_[rc] for rc in g10]
            units = [("row", ids[r * 9:(r + 1) * 9]) for r in range(9)] + [("col", ids[c::9]) for c in range(9)] + \
                    [("box", [ids[(br + a) * 9 + bc + b] for a in range(3) for b in range(3)]) for br in (0, 3, 6) for bc in (0, 3, 6)]
            seen_ = {frozenset(x.cells) for x in groups}
            for kind, cells in units:
                if frozenset(cells) not in seen_:
                    groups.append(M.Group(f"x10{kind}{len(groups)}", tuple(cells), kind, True))
    elif d.get("shape"):
        rows = [str(r) for r in d["shape"]]
        coords = [(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch not in ". "]
        D = int(d["digits"])
        groups = []
    else:
        D = int(d.get("digits") or SIZES.get(len(nums)) or 9)
        coords = M._grid_coords(D)
        groups = []
    p = M.Puzzle(D=D, coords=coords, name=(d.get("meta") or {}).get("title") or d.get("title", "") or "")
    cid = {rc: i for i, rc in enumerate(coords)}
    width = max(c for _, c in coords) + 1
    height = max(r for r, _ in coords) + 1

    def ci(tok):
        if isinstance(tok, int):
            return tok
        m = re.fullmatch(r"r(\d+)c(\d+)", tok, re.I)
        if not m or (int(m.group(1)) - 1, int(m.group(2)) - 1) not in cid:
            raise ValueError(f"bad cell {tok!r}")
        return cid[(int(m.group(1)) - 1, int(m.group(2)) - 1)]

    # implied regions (a named layout, or 'box' / a plain D x D board without explicit regions), then explicit ones
    if groups:
        p.groups = list(groups)
    elif not d.get("shape") and (d.get("box") or not d.get("regions")):
        bh, bw = (tuple(int(x) for x in d["box"].lower().split("x")) if d.get("box") else BOXES.get(D, (0, 0)))
        for r in range(D):
            p.groups.append(M.Group(f"r{r+1}", tuple(r * D + c for c in range(D)), "row", True))
        for c in range(D):
            p.groups.append(M.Group(f"c{c+1}", tuple(r * D + c for r in range(D)), "col", True))
        if bh:
            for br in range(0, D, bh):
                for bc in range(0, D, bw):
                    p.groups.append(M.Group(f"b{len(p.groups)}", tuple((br + i) * D + bc + j for i in range(bh) for j in range(bw)),
                                            "box", True))
    for k, g in enumerate(d.get("regions") or []):
        cells = tuple(ci(x) for x in g["cells"])
        kind = g.get("kind", "region")
        complete = g.get("complete", len(cells) == D and g.get("unique", True))
        p.groups.append(M.Group(g.get("name") or f"{kind}{k}", cells, "region" if kind == "extra" else kind,
                                complete, g.get("sum")))
    # givens: row-major over the bounding grid ('#' or '.' at voids), or over existing cells only
    if nums:
        if len(nums) == width * height:
            for k, ch in enumerate(nums):
                rc = divmod(k, width)
                if rc in cid and _val(ch):
                    p.givens[cid[rc]] = _val(ch)
        elif len(nums) == len(coords):
            for k, ch in enumerate(nums):
                if _val(ch):
                    p.givens[k] = _val(ch)
        else:
            raise ValueError(f"numbers has {len(nums)} symbols; expected {width * height} or {len(coords)}")
    for cell, s in (d.get("candidates") or {}).items():
        m = 0
        for ch in s:
            m |= 1 << (_val(ch) - 1)
        p.domains[ci(cell)] = m
    marks = []                                       # (rule, relations / constraints before it): named rules are remembered
    for r in d.get("rules") or []:
        t = r["type"]
        marks.append((r, len(p.relations), len(p.constraints)))
        if t == "kropki":
            a, b = (ci(x) for x in r["cells"])
            p.relations.append(("diff", a, b, 1) if r.get("color", "white") == "white" else ("ratio", a, b, 2))
        elif t == "xv":
            a, b = (ci(x) for x in r["cells"])
            p.relations.append(("sum", a, b, 10 if r.get("letter", "X").upper() == "X" else 5))
        elif t == "less":                               # cells[0] < cells[1]
            a, b = (ci(x) for x in r["cells"])
            p.relations.append(("lt", a, b))
        elif t == "frame":                              # outside clue: sum of the first `count` cells from that edge
            cells = _edge_line(d, D, r["side"], r["index"])[:r.get("count", 3)]
            p.constraints.append({"type": "sum", "cells": cells, "total": int(r["sum"])})
        elif t == "increasing":                         # cells[0] < cells[1] < ...
            cs = [ci(x) for x in r["cells"]]
            p.relations += [("lt", a, b) for a, b in zip(cs, cs[1:])]
        elif t == "rossini":                            # edge arrows: the first 3 cells ascend in the arrow's direction;
            marked = set()                              # with all_given, every other edge's first 3 are not monotone
            for a_ in r.get("arrows", []):
                cs = _edge_line(d, D, a_["side"], a_["index"])[:3]
                if a_.get("towards", "in") == "out":
                    cs = cs[::-1]
                p.relations += [("lt", x, y) for x, y in zip(cs, cs[1:])]
                marked.add((a_["side"], int(a_["index"])))
            if r.get("all_given", True):
                mono = lambda t_: t_[0] < t_[1] < t_[2] or t_[0] > t_[1] > t_[2]
                allowed = [(x, y, z) for x in range(1, D + 1) for y in range(1, D + 1) for z in range(1, D + 1)
                           if len({x, y, z}) == 3 and not mono((x, y, z))]
                for side in ("top", "bottom", "left", "right"):
                    for k in range(1, D + 1):
                        if (side, k) not in marked:
                            p.constraints.append({"type": "table", "cells": _edge_line(d, D, side, k)[:3], "allowed": allowed})
        elif t == "vudoku":                             # V corner [vertex, arm, arm]: vertex = sum or difference of the arms
            v, a1, a2 = (ci(x) for x in r["cells"])
            p.constraints.append({"type": "table", "cells": [v, a1, a2],
                                  "allowed": [(x, y, z) for y in range(1, D + 1) for z in range(1, D + 1)
                                              for x in {y + z, abs(y - z)} if 1 <= x <= D]})
        elif t == "lowhigh":                            # marked cells hold split+1..D, every other cell 1..split
            split = int(r.get("split", (D + 1) // 2))
            hi = sum(1 << (v - 1) for v in range(split + 1, D + 1)); lo = ((1 << D) - 1) & ~hi
            high = {ci(x) for x in r.get("high", [])}
            for c in range(len(coords)):
                p.domains[c] &= hi if c in high else lo
            p.cell_clues = getattr(p, "cell_clues", []) + [(dict(r, high=sorted(high)), {c: (hi if c in high else lo) for c in range(len(coords))})]
        elif t == "isomorphic":
            # two grids whose digits correspond through an unknown fixed relabelling (Twins). Human model: an explicit
            # digit KEY -- D key cells (key[x] = the right digit that left digit x maps to; a no-repeat group, the
            # relabelling is a bijection) placed as an extra row beside the board, linked by 3-cell tables
            # (left_i, right_i, key[x]): left_i == x -> right_i == key[x]. Engine techniques then read key entries off
            # known pairs, transfer placements / candidates through known entries, and find singles in the key row.
            pairs = [(ci(a), ci(b)) for a, b in r["pairs"]] if "pairs" in r else None
            if pairs is None:                            # two grids given by their origins: corresponding cells in order
                (r1, c1), (r2, c2) = r["origins"]
                cid0 = {rc: i for i, rc in enumerate(p.coords)}
                pairs = [(cid0[(r1 + a, c1 + b)], cid0[(r2 + a, c2 + b)]) for a in range(D) for b in range(D)]
            kr = max(rc[0] for rc in p.coords) + 2
            key = []
            for x in range(D):
                p.coords.append((kr, x)); p.domains.append((1 << D) - 1); key.append(len(p.coords) - 1)
            p.N = len(p.coords)
            p.iso_key = list(getattr(p, "iso_key", [])) + key       # 2026-10-25: the exchange writer leaves these out
            p.groups.append(M.Group("digit key", tuple(key), "region", True))
            for a, b in pairs:
                for x in range(1, D + 1):
                    p.constraints.append({"type": "table", "cells": [a, b, key[x - 1]],
                                          "allowed": [(u, v, w) for u in range(1, D + 1) for v in range(1, D + 1) for w in range(1, D + 1)
                                                      if u != x or v == w]})
        elif t in ("parity", "digit_class", "exclude"):   # graphical cell clues (2026-10-25: no longer "candidates")
            if t == "parity":
                ok = {v for v in range(1, D + 1) if v % 2 == (1 if r["parity"] == "odd" else 0)}
            elif t == "digit_class":
                ok = {_val(ch) for ch in str(r["digits"])}
            else:
                ok = set(range(1, D + 1)) - {int(r["digit"])}
            m = sum(1 << (v - 1) for v in ok if 1 <= v <= D)
            cells_ = [ci(x) for x in r["cells"]]
            for c_ in cells_:
                p.domains[c_] &= m
            p.cell_clues = getattr(p, "cell_clues", []) + [(dict(r, cells=cells_), {c_: m for c_ in cells_})]
        elif t == "pairs" and "where" in r:      # a whole-grid pair rule: every neighbour pair of that kind, minus "except"
            skip = {frozenset((ci(a), ci(b))) for a, b in r.get("except") or []}
            for a, b in _pairs(list(cid), NEIGHBOURS[r["where"]]):
                if frozenset((a, b)) not in skip:
                    p.relations.append((r["rel"], a, b, *r.get("params", [])))
        elif t == "pairs":
            for a, b in r["cells"]:
                p.relations.append((r["rel"], ci(a), ci(b), *r.get("params", [])))
        elif t == "antiknight":
            M.add_antiknight(p, D) if not d.get("shape") and not layout else _neighbour_neq(p, cid, [(1, 2), (2, 1), (1, -2), (2, -1)])
        elif t == "antiking":
            _neighbour_neq(p, cid, [(1, 1), (1, -1)])
        elif t == "nonconsecutive":
            for (r_, c_), a in cid.items():
                for dr, dc in ((0, 1), (1, 0)):
                    if (r_ + dr, c_ + dc) in cid:
                        p.relations.append(("nonconsec", a, cid[(r_ + dr, c_ + dc)]))
        elif t == "global_entropy":                     # every 2x2 window holds a low, a middle and a high digit (thirds)
            allowed = entropy_table(D)
            for (r_, c_) in sorted(cid):
                win = [(r_, c_), (r_, c_ + 1), (r_ + 1, c_), (r_ + 1, c_ + 1)]
                if all(x in cid for x in win):
                    p.constraints.append({"type": "table", "cells": [cid[x] for x in win], "allowed": allowed})
        elif t == "quadruple":                          # the listed digits (repeats allowed) all appear in these cells
            cs = [ci(x) for x in r["cells"]]
            need = [int(v) for v in r["digits"]]
            p.constraints.append({"type": "table", "cells": cs, "allowed": quadruple_table(D, len(cs), need)})
        else:
            con = {k: v for k, v in r.items()}
            for k in CELL_KEYS:
                if k in con:
                    con[k] = [ci(x) for x in con[k]]
            for k in NESTED_KEYS:
                if k in con:
                    con[k] = [[ci(x) for x in seg] for seg in con[k]]
            if "allowed" in con:
                con["allowed"] = [tuple(x) for x in con["allowed"]]
            p.constraints.append(con)
    ends = [(m[1], m[2]) for m in marks[1:]] + [(len(p.relations), len(p.constraints))]
    for (r, a, b), (a2, b2) in zip(marks, ends):
        if r["type"] in NAMED_RULES:
            _remember(p, r, p.relations[a:a2], p.constraints[b:b2])
    return p


# well-known rules that expand into engine relations / tables when read; the puzzle remembers them so they are written back
# by name, not as their expansion (2026-10-25: a global-entropy puzzle was 64 copies of a 2,916-row table). One-off rules
# belong to the planned custom rule language, not here.
NAMED_RULES = {"global_entropy", "quadruple", "rossini", "vudoku", "increasing", "isomorphic"}


def _remember(p, rule, rels, cons):
    for c in cons:
        c["_named"] = True              # expansion of a named rule: written back as the rule (underscore keys never reach C++)
    p.named_rules = getattr(p, "named_rules", []) + [(dict(rule), list(rels))]


def entropy_table(D):
    """2x2 window (TL, TR, BL, BR) with a low, a middle and a high digit, classes = thirds of 1..D (sudoku.coach's rule)."""
    import itertools
    third = lambda v: (v - 1) * 3 // D
    return [t for t in itertools.product(range(1, D + 1), repeat=4) if len({third(v) for v in t}) == 3]


def quadruple_table(D, n, need):
    import itertools
    return [t for t in itertools.product(range(1, D + 1), repeat=n) if all(t.count(v) >= need.count(v) for v in set(need))]


def add_named(p, rule):
    """apply a named rule (cells as engine indices or "r1c1" names) to an engine Puzzle and remember it (for importers that
    build Puzzles directly)."""
    coords = list(p.coords)
    cname = lambda i: f"r{coords[i][0] + 1}c{coords[i][1] + 1}" if isinstance(i, int) else i
    r = {k: ([cname(x) for x in v] if k in CELL_KEYS else v) for k, v in rule.items()}
    width = max(c for _, c in coords) + 1; height = max(rr for rr, _ in coords) + 1
    shape = ["".join("#" if (y, x) in set(coords) else "." for x in range(width)) for y in range(height)]
    q = from_json({"digits": p.D, "shape": shape, "regions": [], "rules": [r]})
    a, b = len(p.relations), len(p.constraints)
    p.relations += q.relations
    p.constraints += q.constraints
    if getattr(q, "domains", None) and p.domains:
        p.domains = [x & y for x, y in zip(p.domains, q.domains)]
    _remember(p, r, p.relations[a:], p.constraints[b:])
    return p


def _edge_line(d, D, side, index):
    """cell ids of row / column `index` (1-based) read inward from `side` of a plain D x D board"""
    k = int(index) - 1
    if side == "top":
        return [r * D + k for r in range(D)]
    if side == "bottom":
        return [r * D + k for r in range(D - 1, -1, -1)]
    if side == "left":
        return [k * D + c for c in range(D)]
    if side == "right":
        return [k * D + c for c in range(D - 1, -1, -1)]
    raise ValueError(f"bad side {side!r}")


def _neighbour_neq(p, cid, steps):
    for (r_, c_), a in cid.items():
        for dr, dc in steps:
            if (r_ + dr, c_ + dc) in cid:
                p.relations.append(("neq", a, cid[(r_ + dr, c_ + dc)]))


# ---------------------------------------------------------------- encode
def _compiled_extras(p):
    """Relations / constraints that finalize() derived from line and clone constraints (not part of the definition)."""
    q = M.Puzzle(D=p.D, coords=p.coords)
    q.groups = list(p.groups)                       # region-sum lines segment by the puzzle's boxes
    q.constraints = [{k: v for k, v in c.items() if k != "_compiled"} for c in p.constraints]
    q._compile_clones(); q._compile_lines()
    base = [c for c in q.constraints if c.get("type") in ("line", "clone")]
    extra_cons = q.constraints[len(p.constraints):] if len(q.constraints) > len(p.constraints) else []
    return Counter(q.relations), [json.dumps(c, sort_keys=True, default=list) for c in extra_cons], base


def to_json(p: M.Puzzle, solution=None, meta=None) -> dict:
    D, coords = p.D, list(p.coords)
    cname = lambda i: f"r{coords[i][0] + 1}c{coords[i][1] + 1}"
    width = max(c for _, c in coords) + 1
    height = max(r for r, _ in coords) + 1
    out = {"digits": D}
    full_square = width == height == D and len(coords) == D * D and coords == M._grid_coords(D)
    if not full_square:
        have = set(coords)
        out["shape"] = ["".join("#" if (r, c) in have else "." for c in range(width)) for r in range(height)]
    # regions: implied standard rows / cols / boxes?
    implied = False
    if full_square:
        bh, bw = BOXES.get(D, (0, 0))
        std = M.standard(D, bh, bw) if bh else None
        if std and {frozenset(g.cells) for g in p.groups if g.complete and g.total is None and g.kind in ("row", "col", "box")} == \
                {frozenset(g.cells) for g in std.groups}:
            implied = True
            out["box"] = f"{bh}x{bw}"
    regs = []
    for g in p.groups:
        if implied and g.kind in ("row", "col", "box") and g.complete and g.total is None:
            continue
        r = {"kind": g.kind, "cells": [cname(c) for c in g.cells]}
        if g.total is not None:
            r["sum"] = g.total
        if not g.complete and len(g.cells) == D:
            r["complete"] = False
        if not g.complete and len(g.cells) < D and g.kind == "cage":
            pass                                         # cages: digits never repeat (engine convention)
        regs.append(r)
    if regs or not implied:
        out["regions"] = regs if not implied else regs
    # givens over the bounding grid
    cid = {rc: i for i, rc in enumerate(coords)}
    out["numbers"] = "".join((_sym(p.givens[cid[(r, c)]]) if cid[(r, c)] in p.givens else ".") if (r, c) in cid else "#"
                             for r in range(height) for c in range(width))
    if solution is not None:
        out["solution"] = "".join(_sym(v) for v in solution)
    # graphical cell clues (parity / digit_class / exclude / lowhigh) go back out as rules; "candidates" keeps only what no clue
    # explains (Sukaku pencil marks) -- 2026-10-25
    implied = [(1 << D) - 1] * len(p.domains)
    clue_rules = []
    for r_, masks in getattr(p, "cell_clues", []):
        for c_, m_ in masks.items():
            implied[c_] &= m_
        r_ = dict(r_)
        for k in ("cells", "high"):
            if k in r_:
                r_[k] = [cname(x) for x in r_[k]]
        clue_rules.append(r_)
    cands = {cname(i): "".join(_sym(v) for v in range(1, D + 1) if m >> (v - 1) & 1)
             for i, m in enumerate(p.domains) if m != implied[i]}
    if cands:
        out["candidates"] = cands
    # rules: relations minus those compiled from lines / clones
    comp, comp_cons, _ = _compiled_extras(p)
    named = getattr(p, "named_rules", [])
    named_rels = Counter(x for _, rels_ in named for x in rels_)
    rels = Counter(p.relations) - comp - named_rels
    rules = list(clue_rules) + [dict(r_) for r_, _ in named]
    ak = {("neq", a, b) for a, b in _pairs(coords, [(1, 2), (2, 1), (1, -2), (2, -1)])}
    akg = {("neq", a, b) for a, b in _pairs(coords, [(1, 1), (1, -1)])}
    for name, S in (("antiknight", ak), ("antiking", akg)):
        Sx = S | {(k, b, a) for k, a, b in S}
        if S and all(rels[x] > 0 or rels[(x[0], x[2], x[1])] > 0 for x in S):
            rules.append({"type": name})
            for x in list(rels):
                if x in Sx:
                    del rels[x]
    groups_ = {}
    for rel, n in sorted(rels.items(), key=lambda kv: str(kv[0])):
        kind, a, b, params = rel[0], rel[1], rel[2], list(rel[3:])
        for _ in range(n):
            if kind == "diff" and params == [1]:
                rules.append({"type": "kropki", "color": "white", "cells": [cname(a), cname(b)]})
            elif kind == "ratio" and params == [2]:
                rules.append({"type": "kropki", "color": "black", "cells": [cname(a), cname(b)]})
            elif kind == "sum" and params in ([10], [5]):
                rules.append({"type": "xv", "letter": "X" if params == [10] else "V", "cells": [cname(a), cname(b)]})
            elif kind == "lt":
                rules.append({"type": "less", "cells": [cname(a), cname(b)]})
            else:
                key = (kind, json.dumps(params, default=list))
                groups_.setdefault(key, []).append([cname(a), cname(b)])
    for (kind, params), cells in groups_.items():
        rules.append(_compact_pairs(kind, json.loads(params), cells, coords, cname))
    comp_set = Counter(comp_cons)
    for c in p.constraints:
        if c.get("_named"):
            continue
        key = json.dumps({k: v for k, v in c.items() if not k.startswith("_")}, sort_keys=True, default=list)
        if comp_set[key] > 0:
            comp_set[key] -= 1
            continue
        r = {k: v for k, v in c.items() if not k.startswith("_")}
        for k in CELL_KEYS:
            if k in r:
                r[k] = [cname(x) for x in r[k]]
        for k in NESTED_KEYS:
            if k in r:
                r[k] = [[cname(x) for x in seg] for seg in r[k]]
        if "allowed" in r:
            r["allowed"] = [list(x) for x in r["allowed"]]
        rules.append(r)
    if rules:
        out["rules"] = rules
    m = {"title": p.name} if p.name else {}
    m.update({k: v for k, v in (meta or {}).items() if v not in (None, "")})
    if m:
        out["meta"] = m                  # 2026-10-25: metadata in its own object (was top level)
    return out


# neighbourhoods a whole-grid pair rule can cover ("where"); forward steps, so each pair appears once
NEIGHBOURS = {"orthogonal": [(0, 1), (1, 0)], "diagonal": [(1, 1), (1, -1)],
              "king": [(0, 1), (1, 0), (1, 1), (1, -1)], "knight": [(1, 2), (2, 1), (1, -2), (2, -1)]}


def _symmetric(kind, params, D=9):
    f = M.RELATIONS.get(kind)
    try:
        return f is not None and all(bool(f(v, w, *params)) == bool(f(w, v, *params))
                                     for v in range(1, D + 1) for w in range(1, D + 1))
    except Exception:
        return False


def _compact_pairs(kind, params, cells, coords, cname):
    """a "pairs" rule; when its pairs are (almost) every neighbour pair of one kind, write it as a whole-grid rule
    {"where": "orthogonal", "except": [...]} instead of listing every pair (2026-10-25: a non-consecutive sudoku was 144
    pairs). Only for symmetric relations, where the pair's order carries no meaning."""
    plain = {"type": "pairs", "rel": kind, "params": params, "cells": cells}
    if len(cells) < 12 or not _symmetric(kind, params):
        return plain
    have = {frozenset(c) for c in cells}
    for where, steps in NEIGHBOURS.items():
        alln = {frozenset((cname(a), cname(b))) for a, b in _pairs(coords, steps)}
        if have <= alln and len(have) * 2 > len(alln):
            missing = sorted((sorted(x) for x in alln - have), key=lambda x: (_rc(x[0]), _rc(x[1])))
            if kind == "nonconsec" and not params and where == "orthogonal" and not missing:
                return {"type": "nonconsecutive"}
            out = {"type": "pairs", "rel": kind, "params": params, "where": where}
            if missing:
                out["except"] = missing
            return out
    return plain


def _rc(name):
    r, c = name[1:].split("c")
    return int(r), int(c)


def _pairs(coords, steps):
    cid = {rc: i for i, rc in enumerate(coords)}
    for (r, c), a in cid.items():
        for dr, dc in steps:
            if (r + dr, c + dc) in cid:
                yield a, cid[(r + dr, c + dc)]


def canonical_hash(obj) -> str:
    """md5 of the canonical puzzle definition (sorted keys, no metadata) -- the same puzzle from two sources dedupes."""
    d = json.loads(obj) if isinstance(obj, str) else dict(obj)
    core = {k: d[k] for k in ("digits", "shape", "box", "layout", "numbers", "regions", "rules", "candidates") if k in d}
    return hashlib.md5(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
