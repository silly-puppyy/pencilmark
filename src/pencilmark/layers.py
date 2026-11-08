"""Board layers: what a puzzle states besides its digits, in one table.

A layer is a second fact per cell that some rules add and others read: regions to find (a chaos construction) give each
cell a region, shading (yin-yang) gives each cell shaded or not. The custom rule language reads a layer with a
function of the same name (`region(c)`, `shaded(c)`, docs/formats/rules/custom.mdx).

Adding a layer: one LAYERS row here (the reader, the custom rule language and the puzzle builder find it through
`layers_of`); the engine, the card and the renderer then say what they do with it.

The identity colors a card draws (regions found, digit classes, pair coloring) are named here too, so every module
picks them from one list (data/palette.json gives each name its shade)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Layer:
    key: str  # the custom-language function that reads it: region(c), shaded(c)
    rule: str  # the rule type that adds it to a puzzle
    name: str  # what it is called in messages ("needs a puzzle with regions to find (chaos)")


LAYERS = (
    Layer("region", "chaos", "regions to find (chaos)"),
    Layer("shaded", "yin_yang", "shading"),
)
BY_KEY = {x.key: x for x in LAYERS}


def layers_of(rules):
    """the keys of the layers a puzzle's rules add (rule dicts with a "type"), in LAYERS order"""
    types = {r.get("type") for r in rules or () if isinstance(r, dict)}
    return tuple(x.key for x in LAYERS if x.rule in types)


# identity colors of the card's trace and sub-steps, in the order they are handed out (docs/formats/grade-card.md 6)
REGION_COLORS = ("yellow", "green", "blue", "purple", "orange", "pink", "cyan", "gray", "brown")  # regions found
CLASS_COLORS = ("orange", "green", "purple", "cyan", "pink", "brown", "gray", "yellow", "blue")  # digit classes
COLOR_PAIRS = (("green", "purple"), ("blue", "yellow"), ("orange", "cyan"), ("pink", "gray"), ("red", "brown"))
