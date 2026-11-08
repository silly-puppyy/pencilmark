"""How an f-puzzles puzzle draws its rules, as the drawn elements _sp_style.apply turns into each rule's `style`
(docs/formats/puzzle-format.md section 7: cosmetic, never read for meaning). f-puzzles colors only its generic
elements: lines (outlineC, width), cages (outlineC), circles and rectangles (baseC, outlineC, size); the named
constraints (thermometers, whispers, killer cages, ...) use the site's own look, which a renderer's defaults give."""

import re

from ._sp_style import _colour

_RC = re.compile(r"R(\d+)C(\d+)", re.I)


def _cells(names):
    out = []
    for s in names or ():
        m = _RC.fullmatch(str(s))
        if m:
            out.append(f"r{m.group(1)}c{m.group(2)}")
    return out


def elements(fp):
    """[{"cells": [...], "style": {...}}] for the colored elements of a decoded f-puzzles dict"""
    if not isinstance(fp, dict):
        return []
    out = []

    def add(cells, style):
        style = {k: v for k, v in style.items() if v not in (None, False)}
        if cells and style:
            out.append({"cells": sorted(set(cells)), "style": style})

    for it in fp.get("line") or []:
        col, op = _colour(it.get("outlineC"))
        w = it.get("width")
        for ln in it.get("lines") or []:
            add(
                _cells(ln), {"color": col, "opacity": op, "width": w if isinstance(w, (int, float)) and w > 0 else None}
            )
    for it in fp.get("cage") or []:
        col, op = _colour(it.get("outlineC"))
        if op != 0:  # a transparent outline: an invisible cage (a region the rules name)
            add(_cells(it.get("cells")), {"color": col, "opacity": op})
    for kind, shape in (("circle", "circle"), ("rectangle", "square")):
        for it in fp.get(kind) or []:
            fill, op = _colour(it.get("baseC"))
            col, _ = _colour(it.get("outlineC"))
            w, h = it.get("width"), it.get("height")
            square = isinstance(w, (int, float)) and w == h
            add(_cells(it.get("cells")), {"fill": fill, "color": col, "opacity": op,
                                          "shape": shape if kind == "circle" or square else None,
                                          "size": w if square else None})  # fmt: skip
    return out
