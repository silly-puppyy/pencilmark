---
description: "One reader and one writer per format: pencilmark JSON, plain strings, text grids, HoDoKu, sudokuwiki.org strings, ipuz and site links."
---

# Readers and writers

pencilmark JSON ([Puzzle format](puzzle-format.md)) is all a tool needs. pencilmark also reads and writes a few other
formats, one function per format: `pencilmark.read.<format>` reads only its own format and raises `FormatError` for
anything else, `pencilmark.write.<format>` writes one and raises `NotSupportedError` for what the format cannot carry.
None of them is part of the format or required by it.

| Format | Reader | Writer |
|---|---|---|
| pencilmark JSON (a dict, JSON text or a `.json` path) | `read.pencilmark` | `write.pencilmark` (text), `write.document` (dict) |
| plain classic strings, also with a trailing comment | `read.plain` | `write.plain` |
| text grids with `\|`, `-`, `+` separators (Simple Sudoku, forums) | `read.grid` | `write.grid` |
| pencil-mark grids | `read.pencil_marks` | – |
| 729-character candidate strings | `read.candidates` | – |
| [HoDoKu](https://hodoku.sourceforge.net/) library lines | `read.hodoku` | – |
| [sudokuwiki.org](https://www.sudokuwiki.org/) packed strings | `read.sudokuwiki` | `write.sudokuwiki` |
| [ipuz](http://www.ipuz.org/) 1 and 2 sudoku | `read.ipuz` | `write.ipuz` (ipuz 2) |
| [f-puzzles](https://www.f-puzzles.com/), [SudokuPad](https://sudokupad.app/) (CSM / fpuz / ctc), [Penpa](https://swaroopg92.github.io/penpa-edit/)+, [Logic Masters](https://logic-masters.de/) links | `read.link` (the host names the site) | – |

Every reader returns a pencilmark JSON dict. `rate`, `solve`, `describe`, `fingerprint` and the command line take any
of these directly: `pencilmark.read.detect(x)` names the format (`read.auto(x)` reads it), and `format="sudokuwiki"`
names it instead of detecting it.

## Plain classic string

- D×D characters in reading order; whitespace and line breaks are ignored.
- Empty cell: `.`, `0`, `-` or `_`. Digits `1`–`9`, then `A`–`Z` for 10–35 (case-insensitive).
- D = √length for D in {4, 6, 8, 9, 10, 12, 14, 15, 16, 20, 25}; boxes are the standard shape (4: 2×2, 6: 2 rows ×
  3 columns, 8: 2×4, 9: 3×3, 10: 2×5, 12: 3×4, 14: 2×7, 15: 3×5, 16: 4×4, 20: 4×5, 25: 5×5).
- `write.plain` writes `.` for empty cells and refuses anything but a classic with standard boxes and no
  other rules.

## Text grids

The same classic puzzle laid out on lines, as Simple Sudoku (`.ss`), SadMan (`.sdk`) and forum posts write it:

```
. . . | . 4 . | 8 . 3          *-----------*
. 6 . | . . 8 | . . 2          |...|.4.|8.3|
9 . 8 | 6 . 5 | . . 1          |.6.|..8|..2|
------+-------+------          |9.8|6.5|..1|
2 3 5 | . . . | . . .          |---+---+---|
…                              …
```

- Lines made only of `-`, `+`, `=`, `|`, `*` and spaces, with at least one `-`, `+` or `=`, are separators and skipped; `|` and spaces inside a row are
  ignored; `*` is also an empty cell.
- Text after `#` or `;` on a line is a comment (`<81 characters>  # rating 5.9`).
- `write.grid` writes the left-hand form (refuses what a plain string cannot carry).

## Pencil marks

- **Pencil-mark grid**: one whitespace-separated token per cell in reading order (separators as above). A token with one
  digit is a given; several digits are that cell's candidates (`candidates` in the puzzle).
- **729-character candidate string** (Sukaku): 9 characters per cell, position k holds the digit k+1 when it is a
  candidate and `.` or `0` otherwise; a cell with a single candidate is a given.
- **HoDoKu library line** (`:0901:4:<81 characters>:<removed candidates>:…`): the puzzle and its removed candidates
  (tokens `drc` = digit d is not a candidate of rRcC); the fields describing the collected step are ignored.

These are read only. A multi-line grid is one puzzle: pass it to `read.pencil_marks` / `rate` as one string (the command line
reads one puzzle per line).

## sudokuwiki.org packed strings

These are the puzzle strings used by the solvers on [sudokuwiki.org](https://www.sudokuwiki.org), Andrew Stuart's site.
They are described on his [Sudoku String Definitions](https://www.sudokuwiki.org/Sudoku_String_Definitions) page; the
full encoding reference is the [puzzle-coding documentation](https://blueant1.github.io/puzzle-coding/documentation/puzzlecoding/encodingformats)
by Quintin May ([source](https://github.com/BlueAnt1/puzzle-coding)). A string is a 3-character header
(puzzle type, size, encoding version) followed by one base-36 value per cell.

pencilmark reads and writes these headers:

| Header | Puzzle | Read as |
|---|---|---|
| `S9B`, `S6B` | classic 9×9, 6×6 | one `box_grid` |
| `X9B` | Sudoku X | + both main diagonals (`region` kind `diagonal`) |
| `W9B` | Windoku | + the 4 windows (`region` kind `window`) |
| `C9B` | Colour Sudoku | + 9 groups at the same position in every box (`region` kind `disjoint`) |
| `J9B` | Jigsaw | `box` rules |
| `L9B`, `L6C` | Killer 9×9, 6×6 | + `cage` rules (L6C: `+` cages only) |
| `M9B` | Killer Jigsaw | `box` and `cage` rules |

In the non-killer forms each cell is Andrew Stuart's board-state code (as sudokuwiki.org writes it): a given digit d, a
placed digit d + 9 (d + 6 on 6×6; read as a given), the candidate mask + 18 (bit i is digit i + 1; read as that cell's
`candidates`), or 0 (nothing stored), so one string can carry a mid-solve board with its candidates; `write.sudokuwiki` writes
a puzzle's `candidates` the same way. Anything else (other puzzle types or versions, candidates or placed digits in the
killer forms, 6×6 killer operators other than `+`) is refused when read. `write.sudokuwiki` picks the header from the structure and refuses puzzles none of
these headers can express (a 6×6 jigsaw or X, killer-X, killer-windoku, anything above 9×9).

## ipuz

`write.ipuz(puzzle)` writes [ipuz](http://www.ipuz.org) 2 ([sudoku kinds](http://www.ipuz.org/sudoku)) for the subset that maps cleanly and refuses the rest:

| pencilmark | ipuz |
|---|---|
| one `box_grid` of the standard box shape | kind `http://ipuz.org/sudoku#1`, `boxes: true` |
| one `grid`, no boxes (Latin square) | `http://ipuz.org/sudoku/latinsquare#1`, `boxes: false` |
| + both main diagonals | `http://ipuz.org/sudoku/diagonalsudoku#1`, `zones` |
| + `region` window | `http://ipuz.org/sudoku/hypersudoku#1`, `zones` with `rect` |
| one `grid` + `box` rules (jigsaw) | `http://ipuz.org/sudoku/jigsawsudoku#1`, `boxes: false`, one zone per box |
| + `cage` | `http://ipuz.org/sudoku/killersudoku#1`, `cages` (`value`), `showoperators: false`, `cageborder: "dashed"` |

`puzzle` and `solution` are row arrays (0 = empty); ipuz coordinates are `[col, row]`, 1-based. `meta` title /
author / url / id / date map to `title`, `author`, `url`, `uniqueid`, `date` (`mm/dd/yyyy`). The complete pencilmark
object goes in `"io.github.silly-puppyy.pencilmark:puzzle"`, with
`"volatile": {"io.github.silly-puppyy.pencilmark": "puzzle,solution,zones,cages"}`. Given candidates (Sukaku) are
refused: ipuz has no field for them.

`read.ipuz(x)` (a dict, JSON text or a path) reads the same subset back: `puzzle` and `solution` (numbers, digit strings or
`{"cell": …}` objects; `empty` as declared), `boxes`, `zones` (on a jigsaw, zones of D cells are its boxes; both main
diagonals become `region` kind `diagonal`, `rect` zones `window`, any other zone `region`) and `cages` with a `value`.
A file written by `write.ipuz` returns its embedded puzzle as long as the grid was not edited. Other kinds, omitted or
block cells, and cages without a sum are refused.

## Site loaders

`pencilmark.read.link` reads [f-puzzles](https://www.f-puzzles.com), [SudokuPad](https://sudokupad.app) (CSM / fpuz /
ctc), [Penpa+](https://swaroopg92.github.io/penpa-edit/) and [Logic Masters](https://logic-masters.de) links into
pencilmark JSON; the link's host names the site. Writing those formats is not supported. Loaders that fetch pages identify
themselves, obey robots.txt and pause between requests.
