"""Rules that read the regions of a chaos construction (format 6.3): the recurring mechanics of chaos puzzles as named
rule types, each compiled to custom rules over region() (rules/custom.py), which the engine reasons with (RegionRule).

region_sight  a clue cell's digit (or the rule's `value`) counts the cells of the clue's own region it sees in the
              given `directions` (default all four), sight stopping at the first cell of another region or the edge of
              the board; `self` (default true) counts the clue cell too. Setters' names: circles, cave, sightlines,
              sightline arrows, internal x-sums, arrows (one direction, without the clue cell)."""

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
