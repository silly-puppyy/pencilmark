"""Rules that read the shading (format 6.19, beside yin_yang): the recurring couplings of shading puzzles as named rule
types, each compiled to custom rules over shaded() (rules/custom.py), which the engine reasons with (ShadeRule). Found
by frequency in the logic-masters.de yin-yang rules texts (2026-11-08).

shading_sight      a clue cell's digit (or `value`) counts the cells of its own colour it sees in the given
                   `directions` (default all four), sight stopping at the first cell of the other colour or the edge;
                   `self` (default true) counts the clue cell too. Setters' names: sight lines, "digits in caged cells
                   show how many cells of the same colour they see".
shaded_count       a clue cell's digit (or `value`) counts the shaded cells in each of its `directions` up to the edge
                   (each direction alone; `total` true: all of them together). Setters' names: arrows counting shaded
                   cells.
same_shading       the cells all have one colour.
different_shading  the two cells have different colours (setters: dots on the border between the colours)."""

from __future__ import annotations

from .region import DIRECTIONS, sight_lines


def shading_sight_custom(rule, coords):
    """a shading_sight rule -> one custom rule per clue cell"""
    dirs = list(rule.get("directions") or DIRECTIONS)
    out = []
    for cell in rule["cells"]:
        rays = {d: ray for d, ray in sight_lines(cell, coords, dirs).items() if ray}
        terms = [f"len(take_while({d}, y => shaded(y) == shaded(x)))" for d in rays]
        if rule.get("self", True):
            terms.insert(0, "1")
        target = str(rule["value"]) if "value" in rule else "x"
        out.append({"type": "custom", "cells": {"x": [cell.lower()], **rays},
                    "holds": f"{' + '.join(terms) or '0'} == {target}"})  # fmt: skip
    return out


def shaded_count_custom(rule, coords):
    """a shaded_count rule -> one custom rule per clue cell"""
    dirs = list(rule.get("directions") or DIRECTIONS)
    out = []
    for cell in rule["cells"]:
        rays = {d: ray for d, ray in sight_lines(cell, coords, dirs).items()}
        counts = {d: (f"count(y for y in {d} if shaded(y))" if ray else "0") for d, ray in rays.items()}
        target = str(rule["value"]) if "value" in rule else "x"
        if rule.get("total"):
            holds = f"{' + '.join(counts.values())} == {target}"
        else:
            holds = " and ".join(f"{c} == {target}" for c in counts.values())
        out.append({"type": "custom", "cells": {"x": [cell.lower()], **{d: r for d, r in rays.items() if r}},
                    "holds": holds})  # fmt: skip
    return out


def same_shading_custom(rule, coords=None):
    """same_shading -> one custom rule per neighbouring pair of the list (all one colour)"""
    cs = [c.lower() for c in rule["cells"]]
    return [
        {"type": "custom", "cells": {"a": [a], "b": [b]}, "holds": "shaded(a) == shaded(b)"} for a, b in zip(cs, cs[1:])
    ]


def different_shading_custom(rule, coords=None):
    """different_shading -> one custom rule (the two cells differ)"""
    a, b = (c.lower() for c in rule["cells"])
    return [{"type": "custom", "cells": {"a": [a], "b": [b]}, "holds": "shaded(a) != shaded(b)"}]


# the named rules over the shading: type -> its custom-rule form (puzzle_json compiles them, exchange reads / validates
# / writes them by name)
SHADING_RULES = {
    "shading_sight": shading_sight_custom,
    "shaded_count": shaded_count_custom,
    "same_shading": same_shading_custom,
    "different_shading": different_shading_custom,
}
