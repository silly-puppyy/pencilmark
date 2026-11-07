---
title: Import puzzles from other apps
description: Grade puzzles written as text grids, sudokuwiki.org strings, ipuz files or SudokuPad, f-puzzles, Penpa and Logic Masters links, and save them in the puzzle format.
---

# Import puzzles from other apps

pencilmark reads the common ways puzzles are shared. Pass any of them to `pencilmark.rate`, `solve` or `describe`, or
put them one per line in a file for the command line; [Other formats](../../formats/other-formats.md) gives the exact rules of each.

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
`pencilmark.write.plain(grid)`.

## sudokuwiki.org strings

The packed strings of [sudokuwiki.org](https://www.sudokuwiki.org)'s solvers (`S9B…` for classics, `L9B…` for killers,
and others) are read directly, in Python and on the command line:

```
$ echo 'S9Bepepepep04ep08ep03ep06epepep08epep0209ep0806ep05epep01020305epepepepepepepepep07epep02epepepepepepepepep0906epep02epepepepepep08ep0102epep07epepep09epepepepepepep' | pencilmark rate -
Hard	5.8	10.7	X-Wing
```

`pencilmark.write.sudokuwiki(puzzle)` writes one, to open a puzzle in their solver.

## Links

SudokuPad, f-puzzles, Penpa+ and Logic Masters links are read directly. Here `links.txt` holds one line, the README's
classic as an f-puzzles link, so the card is the classic's:

```
$ pencilmark rate links.txt          # one link per line
Hard	5.8	10.7	X-Wing
```

```python
card = pencilmark.rate("https://f-puzzles.com/?load=N4IgzglgXgpiBcAC…")
```

f-puzzles `?load=` links, Penpa+ links and bare SudokuPad payloads are decoded offline. SudokuPad short links, f-puzzles
`?id=` links, short-link services and Logic Masters pages are fetched: one request each, identified as pencilmark, with
robots.txt obeyed and a pause between requests to the same site.

Lines take their meaning from their colour and the rules text: "adjacent digits on a green line differ by at least 5"
makes green lines German whispers, whether the text names the rule or only describes it ("a purple line contains a set
of consecutive digits"). In a puzzle with lines of one colour, a rules text that describes one line rule without naming
a colour gives that rule to every line.

A rule pencilmark cannot map exactly is refused with the list of what it could not read; nothing is dropped silently.
The error is `pencilmark.NotSupportedError`, and its message names each element, for example "pink line" or
"generic line (meaning in rules text)": a line whose meaning only the rules text gives. A puzzle whose rules define a
mechanic pencilmark does not model, such as equality cages or clones, is refused by name ("rule 'equality
cage'") even when its elements look like familiar ones, so its cages never grade as killer cages.

When the link embeds the setter's solution (most SudokuPad and f-puzzles links do), the reading is checked against it.
A reading that the solution breaks is refused with `pencilmark.ReadingMismatch` ("the reading contradicts the
setter's embedded solution"). The usual cause is a one-off rule worded like a standard one: the reader takes the
familiar meaning and the puzzle comes out different. `sources.load(link, check_solution=False)` skips the check.

### What links read, and what they don't

Measured on the 1,351 SudokuPad puzzles from Cracking the Cryptic videos (2026-11):

| Outcome | Puzzles |
|---|---|
| Read without `infer`, matching the setter's solution | 345 |
| Misread, now refused by the solution check | 107 |
| Misread, not caught (no usable embedded solution, or the check could not decide) | 5 |
| Refused before reading (a rule or element pencilmark does not model) | the rest |

Reads well:

- the standard rule families and their many wordings;
- line meanings given by colour in the rules text;
- killer cages, arrows, thermos, dots, X/V, whispers, renbans, region-sum lines, quadruples, sandwiches and the other
  families on the [puzzle format](../../formats/puzzle-format.md) pages.

Not read:

- **One-off rules worded like standard ones**, for example:
  - digits that may repeat in a cage;
  - cage sums rounded to a multiple;
  - letters standing for numbers;
  - "exactly k of these hold";
  - hot and cold cells.

  With an embedded solution these are refused. Without one they can load as a different puzzle, which usually shows
  when grading: `NoSolution` or `NotUnique`.
- **Digit sets other than 1 to D** (0 to 8, 1 to 5 twice): refused when the embedded solution shows them. Some links
  drop the solution, and then the check cannot see it.
- **Fog of war**: read as the puzzle's [fog rule](../../formats/rules/other.mdx#620-fog-of-war) (SudokuPad lit cells
  and setter triggers, f-puzzles fog). The puzzle loads, solves and exports, and `rate` grades it under the fog ([what works under
  fog](fog.md)).
- **Several grids on one canvas**, unless the setter drew the houses explicitly.
- **Shading, loop and path genres.**

Hard variants from these sites sometimes get band Unknown with the reason that uniqueness was not settled (`solve`
raises `pencilmark.Undecided` instead): the engine's search could not prove the puzzle unique within its limits. Installing the `verify` extra (`pip install "pencilmark[verify]"`) adds OR-Tools,
which settles most of them.

## ipuz files

```
$ pencilmark rate killer.ipuz        # docs/examples/killer-4x4.json written with write.ipuz
Very Easy	0.3	0.8	Hidden Single
```

`pencilmark.read.ipuz` and `pencilmark.write.ipuz` convert in both directions for classic, diagonal, windoku,
jigsaw and killer puzzles.

## Save in the puzzle format

`pencilmark.write.pencilmark` turns any of these inputs into pencilmark JSON, here with the variant name and rules
filled in, its solution, and the title and source a link carries:

```python
text = pencilmark.write.pencilmark("https://f-puzzles.com/?load=N4IgzglgXgpiBcAC…", solution=True, describe=True)
open("killer.json", "w").write(text)
```

On the command line, `pencilmark convert links.txt --pretty` does the same for every line.

A SudokuPad puzzle's look comes along: each rule takes the colour, width or shape of the element that draws it (a
purple renban line stays purple) as its `style` ([Puzzle format](../../formats/puzzle-format.md) section 7), which
renderers may use and solvers ignore. `pencilmark convert --no-style` leaves it out.
