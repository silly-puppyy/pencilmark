"""How a SudokuPad puzzle draws its rules, kept as the pencilmark-puzzle `style` of each rule (docs/formats/puzzle-format.md
section 7: cosmetic, never read for meaning). Each drawn element gives its cells and its look; on export a rule takes
the look of the element whose cells are exactly the rule's cells (a purple renban line stays purple), and none when
no element, or elements that disagree, match it."""

import json
import math
import re

from ._sp_translate import line_cells

_CELL = re.compile(r"r(\d+)c(\d+)")


def _colour(c):
    """SudokuPad colour ('#rgb', '#rgba', '#rrggbb', '#rrggbbaa') -> ('#rrggbb', opacity below 1 or None)"""
    h = c.strip().lstrip("#") if isinstance(c, str) else ""
    if re.fullmatch(r"[0-9a-fA-F]{1,2}", h):  # newer files' grey shorthand: "#F" white, "#0" black, a 2nd digit = alpha
        h = h[0] * 6 + (h[1] * 2 if len(h) == 2 else "")
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

    def add(cells, style, geom=None):
        style = {k: v for k, v in style.items() if v not in (None, False)}
        if cells and style:
            out.append(
                {"cells": sorted({_name(rc) for rc in cells}), "style": style, **({"geom": geom} if geom else {})}
            )

    for kind in ("lines", "arrows"):
        for ln in P.get(kind) or []:
            wp = ln.get("wayPoints") if isinstance(ln, dict) else None
            if not wp or len(wp) < 2:
                continue
            cells = [rc for rc in line_cells(wp) if 0 <= rc[0] < n and 0 <= rc[1] < n]
            col, op = _colour(ln.get("color") or ln.get("stroke"))
            w = ln.get("thickness")
            add(cells, {"color": col, "opacity": op, "width": round(w / size, 3) if isinstance(w, (int, float)) and w > 0 else None,
                        "dash": bool(ln.get("stroke-dasharray"))},
                {"kind": "arrow" if kind == "arrows" else "line", "points": [list(p) for p in wp]})  # fmt: skip
    for cage in P.get("cages") or []:
        cells = (
            [rc for rc in (cage.get("cells") or []) if isinstance(rc, (list, tuple))] if isinstance(cage, dict) else []
        )
        if cells and not cage.get("hidden"):  # metadata cages carry `cells: [null]`
            col, op = _colour(cage.get("outlineC"))
            add([tuple(rc) for rc in cells], {"color": col, "opacity": op})
    for kind in ("underlays", "overlays"):
        for sh in P.get(kind) or []:
            if not isinstance(sh, dict) or "center" not in sh:
                continue
            text = str(sh.get("text", "")).strip()
            if text:  # words (a legend, a title): artwork; digits are clue labels, drawn by their rules
                if re.search(r"[A-Za-z]", text):
                    col, _ = _colour(sh.get("color"))
                    fs = sh.get("fontSize")
                    deco = {"kind": "text", "center": list(sh["center"]), "text": text,
                            "style": {k: v for k, v in {"color": col, "size": round(fs / size, 3) if isinstance(fs, (int, float)) and fs > 0 else None}.items() if v}}  # fmt: skip
                    out.append({"cells": [_name(rc) for rc in _shape_cells(*sh["center"], n)], "text_decoration": deco})
                continue
            fill, op = _colour(sh.get("backgroundColor"))
            col, _ = _colour(sh.get("borderColor"))
            h, w = sh.get("height") or sh.get("width") or 0, sh.get("width") or 0
            if min(h, w) >= n - 0.5:  # a board-sized fill: the background (artwork, section 7 decorations)
                if fill and op != 0:
                    style = {k: v for k, v in {"fill": fill, "opacity": op}.items() if v is not None}
                    out.append(
                        {"decoration": {"kind": "rect", "center": list(sh["center"]), "size": [h, w], "style": style}}
                    )
                continue
            square = abs((sh.get("width") or 0) - (sh.get("height") or 0)) < 0.01
            shape = (
                "circle"
                if sh.get("rounded")
                else ("diamond" if square and sh.get("angle") == 45 else "square" if square else None)
            )
            ang = sh.get("angle") if isinstance(sh.get("angle"), (int, float)) and sh.get("angle") % 90 else None
            sz = round(max(h, w), 3) if square and (h or w) else None
            geom = {"kind": "circle" if sh.get("rounded") else "rect", "center": list(sh["center"]), "size": [h or w, w or h],
                    "angle": sh.get("angle") or 0}  # fmt: skip
            add(_shape_cells(*sh["center"], n), {"fill": fill, "color": col, "opacity": op, "shape": shape, "size": sz,
                                                 "angle": ang if shape not in ("diamond", "circle") else None}, geom)  # fmt: skip
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


def _halo(styles):
    """several line looks on the same cells (a wide pale line under a narrow coloured one): the narrowest is the line, the
    widest its outline"""
    lines = [json.loads(x) for x in styles]
    if len(lines) < 2 or not all(isinstance(x.get("width"), (int, float)) for x in lines):
        return styles
    lines.sort(key=lambda x: x["width"])
    thin, wide = lines[0], lines[-1]
    if wide["width"] <= thin["width"] or "color" not in wide:
        return styles
    merged = dict(thin, outline=wide["color"], outline_width=round((wide["width"] - thin["width"]) / 2, 3))
    return {json.dumps(merged, sort_keys=True)}


def _decoration(el):
    """a drawn element no rule uses, as a section 7 decoration (cell units, [row, col] from the board's corner)"""
    g, st = el.get("geom") or {}, el["style"]
    style = {k: st[k] for k in ("color", "fill", "opacity", "width", "outline", "outline_width") if k in st}
    if g.get("kind") in ("line", "arrow"):
        return {"kind": g["kind"], "points": g["points"], "style": style}
    if g.get("kind") in ("rect", "circle"):
        (y, x), (h, w), a = g["center"], g["size"], g.get("angle") or 0
        if g["kind"] == "rect" and a % 90:  # a rotated rectangle: its corners
            t = math.radians(a)
            pts = [[round(y + dy * math.cos(t) + dx * math.sin(t), 3), round(x + dx * math.cos(t) - dy * math.sin(t), 3)]
                   for dy, dx in ((-h / 2, -w / 2), (-h / 2, w / 2), (h / 2, w / 2), (h / 2, -w / 2))]  # fmt: skip
            return {"kind": "polygon", "points": pts, "style": style}
        return {"kind": g["kind"], "center": [y, x], "size": [h, w], "style": style}
    return None


def apply(doc, drawn):
    """the pencilmark-puzzle document with `style` on each rule whose cells one drawn look matches (two looks on the same
    cells, wide and narrow, are a line and its outline); drawn elements on cells no rule touches become decorations
    (lines, shapes, words), so the artwork survives without ever being read as a rule"""
    looks, decorations = {}, [el["decoration"] for el in drawn or [] if "decoration" in el]
    for el in drawn or []:
        if "cells" not in el or "style" not in el:
            continue
        looks.setdefault(frozenset(el["cells"]), set()).add(json.dumps(el["style"], sort_keys=True))
    looks = {k: _halo(v) for k, v in looks.items()}
    ruled = set()
    for r in doc.get("rules") or []:
        ruled |= _rule_cells(r, set())
    for el in drawn or []:
        cells = set(el.get("cells") or ())
        if not cells or cells & ruled:  # a rule's own drawing, or touching one: never duplicated as artwork
            continue
        deco = el.get("text_decoration") or (_decoration(el) if "style" in el else None)
        if deco and deco not in decorations:
            decorations.append(deco)
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
    doc = {**doc, "rules": rules} if rules else doc
    return {**doc, "decorations": (doc.get("decorations") or []) + decorations} if decorations else doc
