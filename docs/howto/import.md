---
title: Import puzzles from other apps
description: Grade puzzles written as text grids, sudokuwiki.org strings, ipuz files or SudokuPad, f-puzzles, Penpa and Logic Masters links, and save them in the puzzle format.
---

# Import puzzles from other apps

pencilmark reads the common ways puzzles are shared. Pass any of them to `pencilmark.rate`, `solve` or `describe`, or
put them one per line in a file for the command line; [Other formats](../INTEROP.md) gives the exact rules of each.

## Text grids

Grids copied from Simple Sudoku, SadMan or a forum post work as they are, separators and all:

```python
import pencilmark

grid = """
. . . | . 4 . | 8 . 3
. 6 . | . . 8 | . . 2
9 . 8 | 6 . 5 | . . 1
------+-------+------
2 3 5 | . . . | . . .
. . . | 7 . . | 2 . .
. . . | . . . | . 9 6
------+-------+------
. . 2 | . . . | . . .
8 . 1 | 2 . . | 7 . .
. 9 . | . . . | . . .
"""
pencilmark.rate(grid)["band"]       # 'Hard'
```

The command line reads one puzzle per line, so give it the 81-character form there:
`pencilmark.to_string(grid, "plain")`.

## sudokuwiki.org strings

The packed strings of [sudokuwiki.org](https://www.sudokuwiki.org)'s solvers (`S9B…` for classics, `L9B…` for killers,
and others) are read directly, in Python and on the command line:

```
$ echo 'S9Bepepepep04ep08ep03ep06epepep08epep0209ep0806ep05epep01020305epepepepepepepepep07epep02epepepepepepepepep0906epep02epepepepepep08ep0102epep07epepep09epepepepepepep' | pencilmark rate -
Hard	5.9	10.7	X-Wing
```

`pencilmark.to_string(puzzle, "sudokuwiki")` writes one, to open a puzzle in their solver.

## Links

SudokuPad, f-puzzles, Penpa and Logic Masters links are read directly:

```
$ pencilmark rate links.txt          # one link per line
Hard	5.9	10.7	X-Wing
```

```python
card = pencilmark.rate("https://f-puzzles.com/?load=N4IgzglgXgpiBcAC…")
```

f-puzzles `?load=` links, Penpa links and bare SudokuPad payloads are decoded offline. SudokuPad short links, f-puzzles
`?id=` links, short-link services and Logic Masters pages are fetched: one request each, identified as pencilmark, with
robots.txt obeyed and a pause between requests to the same site.

A rule pencilmark cannot map exactly is refused with the list of what it could not read; nothing is dropped silently.

## ipuz files

```
$ pencilmark rate killer.ipuz
Hard	5.9	10.7	X-Wing
```

`pencilmark.from_ipuz` and `to_ipuz` convert in both directions for classic, diagonal, windoku, jigsaw and killer
puzzles.

## Save in the puzzle format

`to_export` turns any of these inputs into a `sudoku-puzzle` file, with the variant name and rules filled in, its
solution, and the title and source a link carries:

```python
exp = pencilmark.to_export("https://f-puzzles.com/?load=N4IgzglgXgpiBcAC…", title="Imported killer")
open("killer.json", "w").write(pencilmark.dumps(exp))
```

On the command line, `pencilmark export links.txt --pretty` does the same for every line.
