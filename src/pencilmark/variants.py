"""Variant registry: names, rule text and recognition (docs/NAMING.md). Not part of the file format: variant
names appear only in meta.type and in describe() output.

    describe(puzzle) -> {"type": "Killer Sudoku", "rules": {"Sudoku": "...", "Killer": "...", ...}}
    rules_text(described) -> "Sudoku: ...\\nKiller: ..."

Two kinds of entries:
  @variant(name, aliases=..., text=...)   a PLACEMENT variant: fn(g) -> the rules it adds to ONE grid area g, or None where the
                                          variant is not defined for that area (size / box shape). Works for any size:
                                          windoku(g) on a 16x16 grid places its 9 windows.
  @family(name, match=..., text=...)      a RULE-FAMILY variant (killer, thermo, kropki, ...): recognised by rule type / kind;
                                          text(rules, ctx) writes its sentence.
Recognition: for each grid area, every placement variant's rules are compared with the puzzle's rules as sets of (type, kind,
cell set) -- region kinds are drawing hints and are ignored; if all are present the variant applies and those rules are
explained. Remaining rules get their family names; anything unknown falls back to a generic name.
Generator presets: the placement functions are also the presets a generator can use (preset_rules(name, size)); the current
generator (pencilmark.gen) places only its own element kinds, so preset generation of placement variants is a next step.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import puzzle_json as PJ
from .exchange import cell_name
from .rules.cell import CELL, VARIANT_TEXT
from .rules.edge import EDGE
from .rules.line import LINE


# ---------------------------------------------------------------------------------------------------------- subgrid view
class Grid:
    """one grid area (a grid / box_grid, or the whole board): n x n cells, box bh x bw (None for a jigsaw / Latin square). Local coordinates are 0-based."""

    def __init__(self, n, box=None, origin=(0, 0), cells=None):
        self.n = n
        self.bh, self.bw = box if box else (None, None)
        self.box = tuple(box) if box else None
        self.r0, self.c0 = origin
        self._cells = cells  # explicit cell names in the subgrid's reading order (cells-form subgrid)

    def cell(self, r, c):
        if self._cells is not None:
            return self._cells[r * self.n + c]
        return cell_name(self.r0 + r, self.c0 + c)

    def block(self, r, c, h, w):
        return [self.cell(r + a, c + b) for a in range(h) for b in range(w)]

    def cells_set(self):
        return self.block(0, 0, self.n, self.n)

    def diagonal(self):
        return [self.cell(i, i) for i in range(self.n)]

    def antidiagonal(self):
        return [self.cell(i, self.n - 1 - i) for i in range(self.n)]

    def boxes(self):
        if not self.box:
            return []
        return [(br, bc) for br in range(0, self.n, self.bh) for bc in range(0, self.n, self.bw)]

    def window_starts(self):
        """top-left corners of the windoku windows: box-sized windows one cell in from each box border, spaced one cell
        apart (9x9: r2c2, r2c6, r6c2, r6c6)"""
        if not self.box:
            return []
        out = [
            (1 + i * (self.bh + 1), 1 + j * (self.bw + 1))
            for i in range(self.n // self.bh - 1)
            for j in range(self.n // self.bw - 1)
        ]
        return [(r, c) for r, c in out if r + self.bh <= self.n - 1 and c + self.bw <= self.n - 1]

    def line(self, r, c, dr, dc, length):
        return [self.cell(r + k * dr, c + k * dc) for k in range(length)]


@dataclass
class Variant:
    name: str
    fn: object
    text: object
    aliases: tuple = ()
    kind: str = "placement"  # placement | family
    match: object = None
    order: int = 0


REGISTRY: list[Variant] = []


def variant(name, aliases=(), text=""):
    def deco(fn):
        REGISTRY.append(Variant(name, fn, text, tuple(aliases), "placement", order=len(REGISTRY)))
        return fn

    return deco


def family(name, match, text, aliases=()):
    REGISTRY.append(Variant(name, None, text, tuple(aliases), "family", match, order=len(REGISTRY)))


def region(cells, kind="extra"):
    return {"type": "region", "kind": kind, "cells": cells}


# --------------------------------------------------------------------------------------------------- placement variants
@variant("X", aliases=["Diagonal Sudoku", "Sudoku X"], text="Digits don't repeat on either of the two main diagonals.")
def x_sudoku(g):
    return [region(g.diagonal(), "diagonal"), region(g.antidiagonal(), "diagonal")]


@variant("Windoku", aliases=["Hyper", "NRC"], text="Digits don't repeat in any of the shaded {bh}×{bw} windows.")
def windoku(g):
    starts = g.window_starts()
    if not starts:
        return None
    return [region(g.block(r, c, g.bh, g.bw), "window") for r, c in starts]


@variant("Argyle", text="Digits don't repeat on any of the eight marked diagonals.")
def argyle(g):
    if g.n != 9:
        return None
    return [
        region(g.line(0, 1, 1, 1, 8), "diagonal"),
        region(g.line(1, 0, 1, 1, 8), "diagonal"),
        region(g.line(0, 7, 1, -1, 8), "diagonal"),
        region(g.line(1, 8, 1, -1, 8), "diagonal"),
        region(g.line(0, 4, 1, -1, 5), "diagonal"),
        region(g.line(0, 4, 1, 1, 5), "diagonal"),
        region(g.line(4, 0, 1, 1, 5), "diagonal"),
        region(g.line(4, 8, 1, -1, 5), "diagonal"),
    ]


@variant("Asterisk", text="Digits don't repeat in the nine shaded cells forming an asterisk.")
def asterisk(g):
    if g.n != 9:
        return None
    return [region([g.cell(r, c) for r, c in ((1, 4), (2, 2), (2, 6), (4, 1), (4, 4), (4, 7), (6, 2), (6, 6), (7, 4))])]


@variant("Centre-dot", aliases=["Center dot"], text="Digits don't repeat among the centre cells of the boxes.")
def centre_dot(g):
    if not g.box or g.bh % 2 == 0 or g.bw % 2 == 0:
        return None
    return [region([g.cell(br + g.bh // 2, bc + g.bw // 2) for br, bc in g.boxes()])]


@variant("Girandola", text="Digits don't repeat in the nine shaded cells of the girandola pattern.")
def girandola(g):
    if g.n != 9:
        return None
    return [region([g.cell(r, c) for r, c in ((0, 0), (0, 8), (1, 4), (4, 1), (4, 4), (4, 7), (7, 4), (8, 0), (8, 8))])]


@variant(
    "Disjoint Groups",
    aliases=["Colour", "Color"],
    text="Cells in the same position in each {bh}×{bw} box contain different digits.",
)
def disjoint(g):
    if not g.box:
        return None
    return [
        region([g.cell(br + a, bc + b) for br, bc in g.boxes()], "disjoint") for a in range(g.bh) for b in range(g.bw)
    ]


# -------------------------------------------------------------------------------------------------------- rule families
def _t(t, kind=None):
    return lambda r: r["type"] == t and (kind is None or r.get("kind") == kind)


def _scope(r):
    s = {"box": " within the same box", "region": " within the same region"}.get(r.get("within"), "")
    if "cells" in r:
        s += " inside the shaded area"
    if r.get("except"):
        s += ", except where marked"
    return s


def _vals(rules, key):
    return sorted({r[key] for r in rules if key in r})


family(
    "Killer",
    _t("cage"),
    lambda rs, c: (
        "Digits in a cage sum to its small clue and don't repeat within the cage."
        if all("sum" in r for r in rs)
        else "Digits don't repeat within a cage; a small clue gives the cage's sum."
    ),
)
family(
    "Little Killer",
    _t("sum", "little_killer"),
    "Clues outside the grid give the sum of the digits along the indicated diagonal; digits may repeat.",
)
family(
    "Sum Frame",
    _t("sum", "frame"),
    lambda rs, c: f"Clues outside the grid give the sum of the first {len(rs[0]['cells'])} digits in that direction.",
)
family(
    "Sum",
    lambda r: r["type"] == "sum" and r["kind"] in ("group", "corner"),
    "A number gives the sum of the cells it marks; digits may repeat.",
)
family(
    "Sandwich",
    _t("sandwich"),
    lambda rs, c: (
        f"Clues outside the grid give the sum of the digits between the 1 and the {c['D']} in that row or column."
    ),
)
family(
    "X-Sums",
    _t("xsum"),
    "Clues outside the grid give the sum of the first X digits in that direction, where X is the first of those digits.",
)
family(
    "Skyscrapers",
    _t("skyscraper"),
    "Clues outside the grid count the digits visible from that side; larger digits hide smaller ones.",
)
family(
    "Rossini",
    lambda r: r["type"] == "rossini" or (r["type"] == "negative" and r["of"] == "rossini"),
    lambda rs, c: (
        "An arrow outside the grid means the first three digits from that side increase in its direction"
        + (
            "; where there is no arrow they neither increase nor decrease."
            if any(r["type"] == "negative" for r in rs)
            else "."
        )
    ),
)
family("123", _t("first_seen"), "A clue outside the grid is the first of the digits 1, 2, 3 met from that side.")
family(
    "Count Different",
    lambda r: r["type"] == "distinct_count" and "side" in r,
    "A clue outside the grid counts the different digits on the indicated diagonal.",
)
family("Arrow", _t("arrow"), "Digits along an arrow sum to the number in its circle.")
for _k in LINE.values():  # the line families, in the registry's order (rules/line.py)
    family(_k.name, _t("line", _k.kind), (lambda f: lambda rs, c: f(rs))(_k.text) if callable(_k.text) else _k.text)
for _k in EDGE.values():  # the edge families (rules/edge.py)
    family(
        _k.name,
        (lambda k: lambda r: (r["type"] == "edge" and r["kind"] == k) or (r["type"] == "negative" and r["of"] == k))(
            _k.kind
        ),
        (lambda f: lambda rs, c: f(rs))(_k.text) if callable(_k.text) else _k.text,
    )
family(
    "Battenburg",
    lambda r: (
        (r["type"] == "corner" and r["kind"] == "battenburg") or (r["type"] == "negative" and r["of"] == "battenburg")
    ),
    lambda rs, c: (
        "A battenburg mark means the four cells around it form an odd / even checkerboard"
        + ("; no other 2×2 area does." if any(r["type"] == "negative" for r in rs) else ".")
    ),
)
family(
    "Mathrax",
    _t("corner", "mathrax"),
    "A corner clue applies to both diagonal pairs around it (10+: sum, 2−: difference, 12×: product, 2÷: quotient; E / O: all even / odd).",
)
family(
    "Exclusion",
    lambda r: (r["type"] == "corner" and r["kind"] == "exclude") or (r["type"] == "cell" and r["kind"] == "exclude"),
    "A circled digit does not appear in the cells it touches.",
)
family("Quadruple", _t("contains"), "Digits in a circle appear at least once among the cells around it.")
family("Cupid", _t("appears"), "The digit in a cell with an arrow appears again in the direction of the arrow.")
family("Clone", _t("clone"), "Shaded shapes of the same colour hold the same digits in corresponding cells.")
family("Twin", _t("isomorphic"), "The two grids are the same solution with the digits relabelled.")
for _v, _txt in VARIANT_TEXT.items():  # the cell families (rules/cell.py)
    _ks = {k for k, ck in CELL.items() if ck.variant == _v}
    _neg = {k for k in _ks if CELL[k].negative}
    family(
        _v,
        (
            lambda ks, neg: (
                lambda r: (
                    (r["type"] == "cell" and r["kind"] in ks)
                    or (r["type"] == "negative" and r["of"] == "cell" and r.get("kind") in neg)
                )
            )
        )(_ks, _neg),
        _txt,
    )
family(
    "Double",
    lambda r: r["type"] == "count" and "each" in r,
    lambda rs, c: f"Each digit appears exactly {rs[0]['each']} times in every marked group.",
)
family(
    "Counting Circles",
    lambda r: r["type"] == "count" and r.get("kind") == "circles",
    "A digit in a circle appears in exactly as many circles as its value.",
)
family(
    "Count",
    lambda r: r["type"] == "count" and "counts" in r,
    "The marked cells hold the listed digits the listed number of times.",
)
family(
    "Distinct Count",
    lambda r: r["type"] == "distinct_count" and "side" not in r,
    "The marked cells hold exactly the given number of different digits.",
)
family("Equal Sums", _t("equal_sum"), "The marked groups of cells all have the same sum.")
family("Vudoku", _t("vudoku"), "The digit at the point of a V is the sum or difference of the digits at its arms.")
family("Entropy", _t("global_entropy"), "Every 2×2 area holds a low, a middle and a high digit.")
family(
    "Anti-Knight",
    _t("neighbours", "antiknight"),
    lambda rs, c: f"Cells a knight's move apart don't contain the same digit{_scope(rs[0])}.",
)
family(
    "Anti-King",
    _t("neighbours", "antiking"),
    lambda rs, c: f"Cells a king's move apart don't contain the same digit{_scope(rs[0])}.",
)
family(
    "Non-Consecutive",
    _t("neighbours", "nonconsecutive"),
    lambda rs, c: f"Orthogonally adjacent cells don't contain consecutive digits{_scope(rs[0])}.",
)
family(
    "Neighbours",
    lambda r: r["type"] == "neighbours" and "kind" not in r,
    lambda rs, c: "Neighbouring cells follow the marked pair rule" + _scope(rs[0]) + ".",
)
family("Relation", _t("relation"), "Linked pairs of cells follow the marked pair rule.")
family(
    "Custom",
    lambda r: r["type"] == "table" or ":" in r["type"],
    lambda rs, c: (rs[0].get("label") or "Custom rule") + ": see the setter's rules.",
)
GENERIC_REGION = {
    "diagonal": ("Diagonals", "Digits don't repeat along a marked diagonal."),
    "window": ("Windows", "Digits don't repeat in a shaded window."),
    "disjoint": ("Disjoint Groups", "Digits don't repeat in a group of cells in the same box position."),
    "colour": ("Colour Groups", "Cells of the same colour contain different digits."),
    "extra": ("Extra Regions", "Digits don't repeat in a shaded region."),
    "region": ("Extra Regions", "Digits don't repeat in a shaded region."),
}


# ------------------------------------------------------------------------------------------------------------- layouts
def _layout_table():
    """layout name -> sub-grid origins (puzzle_json's table: sudoku.one geometries plus aliases)"""
    return dict(PJ._layouts())


LAYOUT_NAMES = {
    "twodoku": "Twodoku",
    "doubledoku": "Doubledoku",
    "twins": "Twin",
    "tridoku": "Tridoku",
    "wing-3": "Gattai-3",
    "butterfly": "Butterfly",
    "flower-4": "Flower",
    "sohei": "Sohei",
    "samurai": "Samurai",
    "windmill": "Windmill",
    "super-samurai": "Super Samurai",
    "clueless-1": "Clueless",
    "clueless-2": "Clueless 2",
    "shogun": "Shogun",
    "sumo": "Sumo",
    "sensei": "Sensei",
}


def layout_name(subgrids, extra=0):
    """name of a multi-grid layout from its subgrid origins (0-based), or None"""
    if len(subgrids) < 2:
        return None
    os_ = sorted(subgrids)
    r0 = min(r for r, _ in os_)
    c0 = min(c for _, c in os_)
    norm = sorted((r - r0, c - c0) for r, c in os_)
    hits = sorted(
        (k for k, v in _layout_table().items() if sorted(v) == norm), key=lambda k: (k not in LAYOUT_NAMES, k)
    )
    if not hits:
        return None
    if set(hits) >= {"clueless-1", "clueless-2"}:
        hits = ["clueless-1"]
    k = hits[0]
    return LAYOUT_NAMES.get(k, k.replace("-", " ").title())


def size_word(D):
    return {4: "Tiny", 6: "Mini", 9: ""}.get(D, f"{D}x{D}")


# ------------------------------------------------------------------------------------------------------------ describe
def _sig(r):
    t = r["type"]
    if t == "region":
        return ("region", frozenset(r["cells"]))
    cells = r.get("cells")
    return (
        t,
        r.get("kind"),
        frozenset(cells)
        if isinstance(cells, list) and cells and isinstance(cells[0], str)
        else json.dumps({k: v for k, v in r.items() if k not in ("id", "label", "style")}, sort_keys=True),
    )


def describe(puzzle):
    """variant name and rules (an ordered key -> sentence map, like Logic Masters rule headers) from the rules alone."""
    from .api import to_export

    doc = (
        puzzle
        if isinstance(puzzle, dict) and puzzle.get("format") == "sudoku-puzzle" and puzzle.get("format_version") == 1
        else to_export(puzzle, describe=False)
    )
    D = doc["digits"]
    rules = [r for r in doc["rules"]]
    # grid areas from the houses the rules state (any spelling): every D x D area whose D rows and D columns are houses,
    # with a box shape when its regular boxes are houses too
    from .exchange import Board, read_houses

    B = Board([divmod(k, doc["board"]["cols"]) for k, v in enumerate(doc["givens"]) if v is not None], D)
    houses, _ = read_houses([r for r in rules if r["type"] in ("grid", "box_grid", "box", "row", "column")], B)
    hset = {(k, frozenset(B.name(c) for c in cells)) for k, cells, _ in houses}
    origins = []
    for k, cells, _ in houses:
        if k != "row" or len(cells) != D:
            continue
        r, c0 = B.coords[cells[0]]
        if [B.coords[x] for x in cells] != [(r, c0 + j) for j in range(D)]:
            continue
        for r0 in range(r - D + 1, r + 1):
            if (r0, c0) in origins:
                continue
            g = Grid(D, None, (r0, c0))
            try:
                ok = all(("row", frozenset(g.block(i, 0, 1, D))) in hset for i in range(D)) and all(
                    ("col", frozenset(g.block(0, j, D, 1))) in hset for j in range(D)
                )
            except Exception:
                ok = False
            if ok:
                origins.append((r0, c0))
    grids = []
    tiled = set()
    for r0, c0 in sorted(origins):
        g = Grid(D, None, (r0, c0))
        for shape in ([tuple(PJ.BOXES[D])] if D in PJ.BOXES else []) + [(h, D // h) for h in range(2, D) if D % h == 0]:
            gg = Grid(D, shape, (r0, c0))
            tiles = [frozenset(gg.block(br, bc, gg.bh, gg.bw)) for br, bc in gg.boxes()]
            if all(("box", t) in hset for t in tiles):
                g = gg
                tiled |= set(tiles)
                break
        grids.append(g)
    explained = [
        r["type"] in ("grid", "box_grid", "row", "column") or (r["type"] == "box" and frozenset(r["cells"]) in tiled)
        for r in rules
    ]
    subs = grids
    sigs = {}
    for i, r in enumerate(rules):
        sigs.setdefault(_sig(r), []).append(i)
    found = []  # (name, text, n_rules)
    for v in sorted((v for v in REGISTRY if v.kind == "placement"), key=lambda v: v.order):
        hit = False
        hit_grids = []
        for gi_, g in enumerate(grids):
            rs = v.fn(g)
            if not rs:
                continue
            idx = []
            for r in rs:
                cand = [i for i in sigs.get(_sig(r), []) if not explained[i]]
                if not cand:
                    break
                idx.append(cand[0])
            else:
                for i in idx:
                    explained[i] = True
                if not hit:
                    found.append([v.name, v.text.format(bh=g.bh, bw=g.bw, n=g.n, D=D)])
                hit = True
                hit_grids.append(gi_)
        if hit:
            found[-1][1] += _where(hit_grids, grids)
    # jigsaw: box rules
    boxes = [i for i, r in enumerate(rules) if r["type"] == "box" and not explained[i]]
    loose = [h for h in hset if h[0] == "box" and h[1] not in tiled]
    if boxes or loose:
        for i in boxes:
            explained[i] = True
        found.append(("Jigsaw", f"Digits 1–{D} appear once in every bold-outlined region."))
    ctx = {"D": D}
    for v in sorted((v for v in REGISTRY if v.kind == "family"), key=lambda v: v.order):
        rs = [r for i, r in enumerate(rules) if not explained[i] and v.match(r)]
        if not rs:
            continue
        for i, r in enumerate(rules):
            if not explained[i] and v.match(r):
                explained[i] = True
        name = v.name
        fam = LINE if rs[0]["type"] == "line" else EDGE if rs[0]["type"] in ("edge", "negative") else {}
        k = rs[0].get("kind") if rs[0]["type"] != "negative" else rs[0]["of"]
        if v.kind == "family" and k in fam and fam[k].name_fn:
            name = fam[k].name_fn(rs)
        txt = v.text(rs, ctx) if callable(v.text) else v.text
        if len(grids) > 1:
            areas = [set(g.cells_set()) for g in grids]
            by_origin = {cell_name(g.r0, g.c0): set(g.cells_set()) for g in grids}
            cells = [
                by_origin.get(r["area"], set()) if isinstance(r.get("area"), str) else set(_rule_cells(r)) for r in rs
            ]
            gi = {k for k, a in enumerate(areas) if any(c and c <= a for c in cells)}
            if cells and all(c and any(c <= areas[k] for k in gi) for c in cells):
                txt += _where(gi, grids)
        found.append((name, txt))
    for i, r in enumerate(rules):  # leftovers: generic family names
        if explained[i]:
            continue
        if r["type"] in ("region",):
            nm, txt = GENERIC_REGION.get(r["kind"], GENERIC_REGION["region"])
        elif r["type"] in ("row", "column"):
            continue
        else:
            nm, txt = r["type"].replace("_", " ").title(), "See the setter's rules."
        if nm not in [f[0] for f in found]:
            found.append((nm, txt))
        explained[i] = True
    if doc.get("candidates"):
        found.append(("Sukaku", "The small digits in a cell are all the digits that cell may contain."))
    sw = size_word(D)
    layout = layout_name([(g.r0, g.c0) for g in grids]) if len(grids) > 1 else None
    if len(subs) > 1:
        base_key = layout or "Multi-Grid"
        base = f"Each {D}×{D} grid follows normal sudoku rules: place 1–{D} in every row, column and box; shared cells belong to both grids."
    elif len(subs) == 1:
        g = grids[0]
        base_key = (sw + " Sudoku").strip()
        if g.box:
            base = f"Place 1–{D} in every row, column and {g.bh}×{g.bw} box."
        else:
            base = f"Place 1–{D} in every row and column."
    else:
        base_key = (sw + " Sudoku").strip()
        base = f"Place 1–{D} in every outlined region."
    out = {base_key: base}
    for nm, txt in found:
        out[nm] = txt
    names = [f[0] for f in found]
    if len(subs) == 1 and not grids[0].box and not boxes and not loose and not names:
        typ = (sw + " Latin Square").strip()
    elif layout or len(subs) > 1:
        lay = layout or "Multi-Grid"
        lay = lay if lay.lower().endswith("doku") else lay + " Sudoku"
        typ = (("Variant " if len(names) > 1 else names[0] + " " if names else "") + lay).strip()
    else:
        typ = " ".join(x for x in (sw, "Variant" if len(names) > 1 else (names[0] if names else ""), "Sudoku") if x)
    return {"type": typ, "rules": out}


def _rule_cells(r):
    """every cell name a rule mentions (empty for whole-board rules)"""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, list):
            for y in x:
                walk(y)

    for k in ("cells", "bulb", "lines", "pairs", "regions", "segments", "source"):
        if k in r:
            walk(r[k])
    if isinstance(r.get("area"), list):
        walk(r["area"])
    return out


def grid_names(grids):
    """position names of the grids of a multi-grid board ("top-left", "centre", …), or "grid at r7c7" where positions
    would be ambiguous"""
    rs = sorted({g.r0 for g in grids})
    cs = sorted({g.c0 for g in grids})

    def pos(g):
        v = "top" if g.r0 == rs[0] else "bottom" if g.r0 == rs[-1] else "middle"
        h = "left" if g.c0 == cs[0] else "right" if g.c0 == cs[-1] else "centre"
        return {
            ("middle", "centre"): "centre",
            ("middle", "left"): "left",
            ("middle", "right"): "right",
            ("top", "centre"): "top",
            ("bottom", "centre"): "bottom",
        }.get((v, h), f"{v}-{h}")

    names = [pos(g) for g in grids]
    if len(set(names)) < len(names):
        names = [f"grid at r{g.r0 + 1}c{g.c0 + 1}" for g in grids]
    else:
        names = [n + " grid" for n in names]
    return names


def _where(gi, grids):
    """' Only in the top-left grid.' for a rule set confined to some, not all, grids of a multi-grid board"""
    if len(grids) < 2 or not gi or len(gi) == len(grids):
        return ""
    names = grid_names(grids)
    ns = [names[i] for i in sorted(gi)]
    if all(n.endswith(" grid") for n in ns) and len(ns) > 1:
        ns = [n[:-5] for n in ns]
        return " Only in the " + ", ".join(ns[:-1]) + " and " + ns[-1] + " grids."
    return " Only in the " + (", ".join(ns[:-1]) + " and " + ns[-1] if len(ns) > 1 else ns[0]) + "."


def rules_text(described):
    """'Key: sentence' lines (used only to fill an empty meta.rules_text)"""
    return "\n".join(f"{k}: {v}" for k, v in described["rules"].items())


def preset_rules(name, size=9, box=None):
    """the rules a placement variant adds to a size x size board with standard boxes (a generator preset); None where the
    variant is not defined for that size"""
    box = box or PJ.BOXES.get(size)
    for v in REGISTRY:
        if v.kind == "placement" and (v.name.lower() == name.lower() or name.lower() in (a.lower() for a in v.aliases)):
            return v.fn(Grid(size, box))
    raise KeyError(f"unknown placement variant {name!r}")
