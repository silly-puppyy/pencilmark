---
title: Write a variant puzzle file
description: Write a 6×6 thermo and Kropki puzzle in the sudoku-puzzle format, check it and grade it.
---

# Write a variant puzzle file

A variant puzzle does not fit in one line of digits, so pencilmark reads it as a JSON file in the
[puzzle format](../FORMAT.md). In this tutorial you write a small 6×6 puzzle with two thermometers and three Kropki
dots, check it and grade it. It assumes you have done [Grade your first puzzle](first-puzzle.md).

## 1. The board and the givens

Start a file called `mini.json` (the finished file is also in the repository as `docs/examples/mini-thermo-kropki.json`):

```json
{"format": "sudoku-puzzle", "format_version": 1,
 "board": {"rows": 6, "cols": 6},
 "digits": 6,
 "givens": [
    0, 0, 0, 0, 0, 0,
    0, 1, 0, 0, 0, 0,
    0, 0, 0, 0, 3, 0,
    0, 2, 0, 0, 0, 0,
    0, 0, 0, 5, 0, 0,
    0, 0, 0, 0, 0, 0],
 "rules": []}
```

- `format` and `format_version` say which format this is; every puzzle file starts with them.
- `board` is the size of the grid and `digits` the digits it uses (1 to 6).
- `givens` lists every cell row by row, with `0` for an empty cell.
- `rules` is empty for now, so nothing says digits can't repeat yet.

## 2. Rows, columns and boxes

The usual sudoku rule is a rule like any other. A `box_grid` says "rows, columns and boxes each hold every digit once";
a 6×6 board has boxes 2 cells high and 3 wide:

```json
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [2, 3]}]
```

Cells are named by row and column: `r1c1` is the top-left cell, `r6c6` the bottom-right. `origin` is the top-left cell
of the grid.

## 3. Thermometers and dots

Add the variant rules after the `box_grid`:

```json
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [2, 3]},
  {"type": "line", "kind": "thermo", "cells": ["r4c4", "r3c4", "r2c4", "r2c3"]},
  {"type": "line", "kind": "thermo", "cells": ["r6c3", "r5c3", "r4c3", "r3c3", "r3c2"]},
  {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r1c3", "r1c4"]},
  {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r1c5", "r1c6"]},
  {"type": "edge", "kind": "kropki", "color": "black", "cells": ["r5c5", "r6c5"]}]
```

- A **thermometer** lists its cells from the bulb to the tip; digits increase along it.
- A **Kropki dot** sits between two cells. White means the digits are consecutive; black means one is double the
  other.

[Lines and arrows](../rules/lines-and-arrows.mdx) and [Edges and corners](../rules/edges-and-corners.mdx) list every
option of these rules. The complete file is now:

```json
{"format": "sudoku-puzzle", "format_version": 1,
 "board": {"rows": 6, "cols": 6},
 "digits": 6,
 "givens": [
    0, 0, 0, 0, 0, 0,
    0, 1, 0, 0, 0, 0,
    0, 0, 0, 0, 3, 0,
    0, 2, 0, 0, 0, 0,
    0, 0, 0, 5, 0, 0,
    0, 0, 0, 0, 0, 0],
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [2, 3]},
  {"type": "line", "kind": "thermo", "cells": ["r4c4", "r3c4", "r2c4", "r2c3"]},
  {"type": "line", "kind": "thermo", "cells": ["r6c3", "r5c3", "r4c3", "r3c3", "r3c2"]},
  {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r1c3", "r1c4"]},
  {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r1c5", "r1c6"]},
  {"type": "edge", "kind": "kropki", "color": "black", "cells": ["r5c5", "r6c5"]}]}
```

## 4. Check it

`pencilmark describe` reads the file and names the variant from its rules:

```
$ pencilmark describe mini.json
{"type": "Mini Variant Sudoku", "rules": {"Mini Sudoku": "Place 1–6 in every row, column and 2×3 box.", "Thermo": "Digits strictly increase along a thermometer from the bulb.", "Kropki": "Digits separated by a white dot are consecutive; digits separated by a black dot are in a 1:2 ratio."}}
```

"Mini" is the size word for 6×6, and "Variant" means more than one variant is present. `pencilmark solve` proves the
puzzle has exactly one solution and prints it:

```
$ pencilmark solve mini.json
345612216453164235523164632541451326
```

pencilmark is strict about the format, so a typing mistake is reported, never ignored. With `"colour"` instead of
`"color"` in the black dot:

```
$ pencilmark solve mini.json
error	1	FormatError: rule 5 ('edge'): unknown key 'colour'
```

Rules are counted from 0, so rule 5 is the sixth rule, the black dot.

## 5. Grade it

```
$ pencilmark rate mini.json --report
#1  Medium  -  difficulty 6.1  -  time 9.8 min
   contains: Clue facts (no 5 on a whisper), Pair rules (dots, whispers, anti-knight...) x3, Two rules together (or Domino pairs (dots / XV))
```

The puzzle is Medium: it needs no learned pattern, only reading the dots and the thermometers together. Its difficulty
(6.1) is higher than you might expect for a 6×6, because difficulty measures how hard the steps are to find, not how
many there are. The variant rules make the steps harder to see.

## 6. Every clue matters

Remove the black dot (the last rule) and solve again:

```
$ pencilmark solve mini.json
not unique
```

Without it the puzzle has more than one solution, so pencilmark will not grade it. The
[generator](../USAGE.md#generator) can find a set of clues like this one for you.
