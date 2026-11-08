"""Rules that read the regions of a chaos construction (format 6.3): the recurring mechanics of chaos puzzles as named
rule types, each compiled to custom rules over region() (rules/custom.py), which the engine reasons with (RegionRule).

region_sight  a clue cell's digit (or the rule's `value`) counts the cells of the clue's own region it sees in the
              given `directions` (default all four), sight stopping at the first cell of another region or the edge of
              the board; `self` (default true) counts the clue cell too. Setters' names: circles, cave, sightlines,
              sightline arrows, internal x-sums, arrows (one direction, without the clue cell).
border_count  a clue cell's digit (or `value`) counts the region borders crossed going from the clue to the edge of the
              board in each of its `directions` (each direction alone; `total` true: all of them together). Setters'
              names: arrows (borders in that direction), passport arrows."""

from __future__ import annotations

DIRECTIONS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def _name(r, c):
    return f"r{r + 1}c{c + 1}"


def sight_lines(cell, coords, directions):
    """the cells a clue sees in each direction, nearest first, up to the edge of the board (coords: (row, col) set)"""
    from ..exchange.common import parse_cell

    r0, c0 = parse_cell(cell)
    out = {}
    for d in directions:
        dr, dc = DIRECTIONS[d]
        ray, (r, c) = [], (r0 + dr, c0 + dc)
        while (r, c) in coords:
            ray.append(_name(r, c))
            r, c = r + dr, c + dc
        out[d] = ray
    return out


def region_sight_custom(rule, coords):
    """a region_sight rule -> one custom rule per clue cell (the engine form)"""
    dirs = list(rule.get("directions") or DIRECTIONS)
    out = []
    for cell in rule["cells"]:
        rays = {d: ray for d, ray in sight_lines(cell, coords, dirs).items() if ray}
        terms = [f"len(take_while({d}, y => region(y) == region(x)))" for d in rays]
        if rule.get("self", True):
            terms.insert(0, "1")
        target = str(rule["value"]) if "value" in rule else "x"
        out.append({"type": "custom", "cells": {"x": [cell.lower()], **rays},
                    "holds": f"{' + '.join(terms) or '0'} == {target}"})  # fmt: skip
    return out


def border_count_custom(rule, coords):
    """a border_count rule -> one custom rule per clue cell: per direction, a border between each pair of consecutive
    cells from the clue to the edge"""
    dirs = list(rule.get("directions") or DIRECTIONS)
    out = []
    for cell in rule["cells"]:
        names, counts = {"x": [cell.lower()]}, []
        for d, ray in sight_lines(cell, coords, dirs).items():
            seq = ["x"]
            for i, c in enumerate(ray):
                names[f"{d}{i}"] = [c]
                seq.append(f"{d}{i}")
            counts.append(" + ".join(f"num(region({a}) != region({b}))" for a, b in zip(seq, seq[1:])) or "0")
        target = str(rule["value"]) if "value" in rule else "x"
        if rule.get("total"):
            holds = f"{' + '.join(f'({c})' for c in counts)} == {target}"
        else:
            holds = " and ".join(f"({c}) == {target}" for c in counts)
        out.append({"type": "custom", "cells": names, "holds": holds})
    return out


# the named rules over regions to find: type -> its custom-rule form (puzzle_json compiles them, exchange reads /
# validates / writes them by name)
REGION_RULES = {"region_sight": region_sight_custom, "border_count": border_count_custom}
