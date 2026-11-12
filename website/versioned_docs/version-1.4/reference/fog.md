---
title: "Fog of war"
description: "The experimental route a solver can take under the fog (what is lit, reveals, no guessing); not yet used by rate."
toc_max_heading_level: 2
---

# Fog of war

The experimental route a solver can take under the fog (what is lit, reveals, no guessing); not yet used by rate. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.fog {#pencilmark.fog}

[src/pencilmark/fog.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/fog.py)

Fog of war: the route a solver can take under the fog ([other](../formats/rules/other.mdx) 6.20).

The puzzle is solved from what the fog shows. A round runs the engine on the rules a solver sees (candidates carried from earlier rounds, no guessing) up to the first placement that lights a new cell; a round that only eliminates is repeated. Every rule given to the engine holds in the real puzzle, so every placement is correct.

What a solver sees (docs/research/fog_mechanics.md, read from SudokuPad's own drawing), on top of the `lit` cells and what correct digits reveal:

- a rule on cells, once all its cells are lit; - an edge or corner clue (dot, X / V, inequality, quadruple), from any lit cell it touches; - a line, stretch by stretch: the lit cells of a whisper / thermo / entropic line and the fogged cell the drawn line enters at each end; - a cage, by its lit stretches (different digits; the stretch holding the total sums below it); - "all dots are given" negatives, between lit cells only; - outside clues, main diagonals and rules stated for the whole board, always.

Hidden-content reasoning (a partly seen arrow's possible shafts, cage shapes from walls) is not here yet: it moves into the engine (docs/research/fog_engine_port.md). Until then a route can stall where a host reasons about what the fog hides.

```
    route(puzzle) -> {"solved", "rounds", "reveals", "steps": [{"technique", "difficulty", "round", "place"}], "stuck"}
```

| Name | What it does |
|---|---|
| def [`lit_cells`](#pencilmark.fog.lit_cells) | the cells a solver sees: the `lit` cells (what the puzzle shows at the start, givens included as the source… |
| def [`above_fog`](#pencilmark.fog.above_fog) | clue kinds the rules say are drawn above the fog ("ALL V clues are given and visible from the outset") |
| def [`visible_rules`](#pencilmark.fog.visible_rules) | the rules a solver sees with these cells lit (module docstring); `above`: clue kinds drawn above the fog;… |
| def [`arrow_cases`](#pencilmark.fog.arrow_cases) | Case rules for arrows seen in part (CtC hosts: "this arrow can't stop here ... |
| def [`cage_cases`](#pencilmark.fog.cage_cases) | Case rules for cages seen in part (CtC, Corner Prison: "the clue is always in the top-left cell, so this… |
| def [`route`](#pencilmark.fog.route) | the fog route of a unique fog puzzle (module docstring): the human band route, round by round on what the… |

### `def lit_cells(fog, givens, placed, rows, cols)` {#pencilmark.fog.lit_cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/fog.py#L43)

the cells a solver sees: the `lit` cells (what the puzzle shows at the start, givens included as the source shows them); without triggers each correctly entered digit lights its 3x3; with triggers an effect lights once every cell of its `when` holds a digit (givens count as held)

### `def above_fog(rules_text)` {#pencilmark.fog.above_fog}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/fog.py#L83)

clue kinds the rules say are drawn above the fog ("ALL V clues are given and visible from the outset")

### `def visible_rules(rules, lit, D, above=(), line_len=None)` {#pencilmark.fog.visible_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/fog.py#L143)

the rules a solver sees with these cells lit (module docstring); `above`: clue kinds drawn above the fog; line_len: every line's length, when the rules give it

### `def arrow_cases(rules, lit, rows, cols, ortho=False, no_share=False, forced=None, single=False, cand=None)` {#pencilmark.fog.arrow_cases}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/fog.py#L340)

Case rules for arrows seen in part (CtC hosts: "this arrow can't stop here ... it must go down"). A lit cell shows its drawn segments, so a hidden part of a shaft runs through fogged cells, stepping into or out of a lit cell only along a drawn segment. Seen: the lit cells of the arrow, the fogged cells its drawn lines enter. - circle lit: the shaft from the circle up to the first fogged cell, then every continuation (a case each); - circle fogged: each lit stretch of the shaft; one end leads to the circle (a case per path), the other on to the tip (unless the stretch holds the tip, whose arrowhead shows). Each case: its cells with the circle = the sum of the others; the engine checks the cases against the live candidates (rule kind "cases"). Returned as engine constraints over cell indices.

### `def cage_cases(rules, lit, rows, cols, clue_always, forced=None, size=None)` {#pencilmark.fog.cage_cases}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/fog.py#L505)

Case rules for cages seen in part (CtC, Corner Prison: "the clue is always in the top-left cell, so this cage must reach row 1 ... it can't be more than 9 cells"). A lit cell shows its walls: across an edge with a lit side, the two cells share a cage exactly when no wall is drawn. A shape is a connected set holding a lit stretch of the cage, at most D cells, agreeing with every edge seen from a lit cell, avoiding cells of fully lit cages and cells other cages' surviving shapes all use (cages never overlap); with clue_always its top-left cell holds the total, so a lit top-left shows one and a shown total is the top-left. Each shape is a case: all different, summing to the total when it is shown. Returned as engine constraints over cell indices.

### `def route(puzzle, max_rounds=400, rules_text=None, overrides=None)` {#pencilmark.fog.route}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/fog.py#L763)

the fog route of a unique fog puzzle (module docstring): the human band route, round by round on what the fog shows. Raises ValueError when the puzzle has no fog rule. rules_text: the puzzle's rules (read from the input's metadata when not given): statements such as "arrows move orthogonally" and "arrows don't share cells" narrow the hidden shapes.
