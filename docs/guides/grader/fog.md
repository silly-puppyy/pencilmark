---
title: Fog of war
description: What pencilmark reads and does with fog-of-war puzzles today, and what it does not do yet.
---

# Fog of war

A fog puzzle starts mostly hidden: only some cells are lit, and entering a correct digit lights more (the 3×3 block
around it, or the setter's own reveal pattern). pencilmark reads fog as a rule of the puzzle
([format 6.20](../../formats/rules/other.mdx#620-fog-of-war)) and never grades the revealed grid instead: a fog
puzzle is solved from what the fog shows. `rate` grades it that way; where the route the fog allows stops, the band is
`Unknown`, never the grade of the revealed grid.

Fog support is new and partial. This page says what works and what does not.

## What works

| | |
|---|---|
| Reading | SudokuPad lit cells (FOGLIGHT cages, "foglight:" cage values, the puzzle's foglight list), the setter's reveal triggers; f-puzzles fog of war (foglight cells, fogofwar cells and FOW / FOGLIGHT cages); sudoku.coach fog |
| Load, validate, solve, count solutions, export | yes: fog changes no solution |
| `rate` | grades the puzzle under the fog: the band, difficulty and time of the fog route, plus a `fog` field; band `Unknown` where the fog stops the route |
| `pencilmark.fog.route(puzzle)` | experimental: the route a solver can take under the fog, step by step |

`fog.route` reads what a solver sees: the lit cells, clues on the edge of a lit cell, outside clues, the parts of
lines and cages that cross lit cells, and rules stated for the whole board. Hidden content is reasoned about the way
hosts do it ("this arrow's circle is somewhere along here, so its total is at least ..."): cage shapes from the visible
walls, arrows whose circle is still fogged, thermometer and renban bounds. Each round takes the easiest step first, as
`rate`'s route does, then lights what the new digits reveal.

## What does not work yet

- **Grading details.** A fog card is computed by the same algorithm as any card: the band route for the band and
  techniques, the same steps that set difficulty and time for any puzzle for difficulty and time, each run round by
  round on what the fog shows. A fog rule that lights every cell gives exactly the card of the same puzzle without
  fog. No cost per reveal is added (the data showed no gain from one). Publishing checks (`issues`), `steps`, `trace`
  and `se` are null on a fog card for now.
- **Stalls.** On the 24 Cracking the Cryptic fog puzzles pencilmark reads, the route solves 10 under the fog and stalls
  on 13, 8 of them before the first placement (one more ran out of time). A stall is a deduction the engine does not
  make yet; found so far: coloring steps a host makes (Restricted Access) and two hidden arrows checked together.
- **Reading.** Fog puzzles use unusual rules more than most: of 114 fog puzzles from Cracking the Cryptic, readers
  refuse about half for a rule or drawing they do not model. A file whose rules mention fog without marking the lit
  cells is refused.
- **Speed.** A route can take minutes on variant puzzles with many cages (500 s for one; another ran over 15 minutes).

