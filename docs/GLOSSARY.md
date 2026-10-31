---
title: Glossary
description: The words these pages use, in one place.
---

# Glossary

**Alternatives.** Techniques that would each do the same job at a point of the solve. On the card they share a chip:
`XWG/KTE/SCL` means an X-Wing, a 2-String Kite or simple colouring works there.

**Band.** What you need to know to solve the puzzle: Very Easy, Easy, Medium, Hard, Very Hard, Expert or Extreme. It
is the band of the hardest technique on the route. See [Philosophy](PHILOSOPHY.md).

**Box.** A block of cells that must hold every digit once, 3×3 on a classic. Boxes of other shapes are jigsaw boxes.

**Candidate.** A digit a cell can still hold. Writing candidates in the cells is taking pencil marks (notes).

**Card.** The result of grading a puzzle: band, difficulty, time, contains, and any fields asked for. Format:
[Grade card](GRADE.md).

**Chip.** One entry of `contains`: a technique code, or several joined by `/` when they are alternatives.

**Contains.** The techniques a solver meets beyond singles, easiest first; the shortest list that still solves the
puzzle.

**Difficulty.** How hard the steps are to find, on a scale from 0 with no ceiling; it does not grow with the size of
the puzzle. See [How a card is computed](MODEL.mdx).

**Given.** A digit printed in the puzzle at the start.

**Golden corpus.** A fixed set of puzzles whose every output is recorded (`tests/golden`), so a change to the code can
show exactly which outputs it moves. For contributors.

**Grid.** A square of cells with its own rows and columns; a multi-grid puzzle has several that overlap.

**House.** A set of cells that must hold different digits, usually every digit once: a row, a column, a box or an extra
region.

**Issues.** Publishing checks on the card: a rule nobody needs, too many givens, most of the effort in a few steps.
See [Check a puzzle before publishing](guides/publish-checks.md).

**Layout.** The arrangement of the grids of a multi-grid puzzle (Samurai, Twodoku, ...). See [Variants](VARIANTS.mdx).

**Placement variant.** A variant that adds fixed regions to a grid: X diagonals, Windoku windows, Argyle lines.

**Region.** A set of cells a rule talks about; an extra region is an extra house.

**Route.** The order of steps a person would take: at each point the easiest available technique. The band route sets
the band and `contains`; the written route, without the steps people do in their head, is priced for difficulty and
time.

**Rule.** One entry of a puzzle file's `rules`: the grid, a cage, a thermometer, a dot. A **rule family** is a kind of
rule (all cages, all thermometers). See [Rule families](/rule-families/).

**Single.** The simplest placements: a hidden single (the only place for a digit in a house) or a naked single (the
only digit left for a cell).

**Spec.** A request to the generator (`sudoku-spec`): the board, rule templates, and what the card must show. See
[Generator spec](SPEC.md).

**Step.** One move of the route: a placement or some eliminations, made by one technique.

**Technique.** A named way of finding a step, such as X-Wing or Naked Pair. Each has a three-letter code, Andrew
Stuart's where he has the strategy.

**Template.** A rule in a spec with a `count` and no cells: the generator places rules of that family.

**Time.** The predicted median solve time in minutes for the people who solve puzzles like it.

**Variant.** A sudoku with rules beyond rows, columns and boxes.
