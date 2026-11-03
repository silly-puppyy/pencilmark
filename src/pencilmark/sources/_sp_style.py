"""How a SudokuPad puzzle draws its rules, kept as the sudoku-puzzle `style` of each rule (docs/formats/puzzle-format.md
section 7: cosmetic, never read for meaning). Each drawn element gives its cells and its look; on export a rule takes
the look of the element whose cells are exactly the rule's cells (a purple renban line stays purple), and none when
no element, or elements that disagree, match it."""

import json
import re

from ._sp_translate import line_cells

_CELL = re.compile(r"r(\d+)c(\d+)")


def _colour(c):
    """SudokuPad colour ('#rgb', '#rgba', '#rrggbb', '#rrggbbaa') -> ('#rrggbb', opacity below 1 or None)"""
    h = c.strip().lstrip("#") if isinstance(c, str) else ""
    if not re.fullmatch(r"[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8}", h):
        return None, None
    if len(h) <= 4:
        h = "".join(ch * 2 for ch in h)
    alpha = int(h[6:8], 16) / 255 if len(h) == 8 else 1
    return "#" + h[:6].lower(), (round(alpha, 2) if alpha < 1 else None)


def _name(rc):
    return f"r{rc[0] + 1}c{rc[1] + 1}"


def _shape_cells(y, x, n):
    """the cells a shape centred at (y, x) marks: its cell, the two cells of an edge, the four of a corner"""
    near = lambda v: abs(v - round(v)) < 0.1
    mid = lambda v: abs(v - int(v) - 0.5) < 0.1
    if mid(y) and mid(x):
        out = [(int(y), int(x))]
    elif near(y) and mid(x):
        out = [(round(y) - 1, int(x)), (round(y), int(x))]
    elif mid(y) and near(x):
        out = [(int(y), round(x) - 1), (int(y), round(x))]
    elif near(y) and near(x):
        out = [(round(y) + dy, round(x) + dx) for dy in (-1, 0) for dx in (-1, 0)]
    else:
        return []
    return out if all(0 <= r < n and 0 <= c < n for r, c in out) else []


def elements(sp):
    """[{"cells": [...], "style": {...}}] for the drawn elements of a decoded SudokuPad puzzle with a look"""
    P = (sp or {}).get("puzzle") if isinstance(sp, dict) else None
    if not isinstance(P, dict) or not isinstance(P.get("cells"), list):
        return []
    n, size = len(P["cells"]), P.get("cellSize") or 64
    out = []

    def add(cells, style):
        style = {k: v for k, v in style.items() if v not in (None, False)}
        if cells and style:
            out.append({"cells": sorted({_name(rc) for rc in cells}), "style": style})

    for kind in ("lines", "arrows"):
        for ln in P.get(kind) or []:
            wp = ln.get("wayPoints") if isinstance(ln, dict) else None
            if not wp or len(wp) < 2:
                continue
            cells = [rc for rc in line_cells(wp) if 0 <= rc[0] < n and 0 <= rc[1] < n]
            col, op = _colour(ln.get("color") or ln.get("stroke"))
            w = ln.get("thickness")
            add(cells, {"color": col, "opacity": op, "width": round(w / size, 3) if isinstance(w, (int, float)) and w > 0 else None,
                        "dash": bool(ln.get("stroke-dasharray"))})  # fmt: skip
    for cage in P.get("cages") or []:
        if isinstance(cage, dict) and not cage.get("hidden") and cage.get("cells"):
            col, op = _colour(cage.get("outlineC"))
            add([tuple(rc) for rc in cage["cells"]], {"color": col, "opacity": op})
    for kind in ("underlays", "overlays"):
        for sh in P.get(kind) or []:
            if not isinstance(sh, dict) or "center" not in sh or str(sh.get("text", "")).strip():
                continue
            fill, op = _colour(sh.get("backgroundColor"))
            col, _ = _colour(sh.get("borderColor"))
            square = abs((sh.get("width") or 0) - (sh.get("height") or 0)) < 0.01
            shape = (
                "circle"
                if sh.get("rounded")
                else ("diamond" if square and sh.get("angle") == 45 else "square" if square else None)
            )
            add(_shape_cells(*sh["center"], n), {"fill": fill, "color": col, "opacity": op, "shape": shape})
    return out


def _rule_cells(v, acc):
    if isinstance(v, str):
        if _CELL.fullmatch(v):
            acc.add(v)
    elif isinstance(v, dict):
        for k, x in v.items():
            if k not in ("style", "label", "id"):
                _rule_cells(x, acc)
    elif isinstance(v, list):
        for x in v:
            _rule_cells(x, acc)
    return acc


def apply(doc, drawn):
    """the sudoku-puzzle document with `style` on each rule whose cells one drawn look matches"""
    looks = {}
    for el in drawn or []:
        looks.setdefault(frozenset(el["cells"]), set()).add(json.dumps(el["style"], sort_keys=True))
    rules = []
    for r in doc.get("rules") or []:
        cells = _rule_cells(r, set())
        got = looks.get(frozenset(cells)) if "style" not in r else None
        if got is None and "style" not in r and len(cells) > 1 and r.get("type") == "cell":
            # a clue drawn as one shape per cell (circles of a parity clue): the look they all share
            each = [looks.get(frozenset([c])) for c in cells]
            if all(x and len(x) == 1 for x in each) and len({next(iter(x)) for x in each}) == 1:
                got = each[0]
        rules.append({**r, "style": json.loads(next(iter(got)))} if got and len(got) == 1 else r)
    return {**doc, "rules": rules} if rules else doc
