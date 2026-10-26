# Other formats

The `sudoku-puzzle` format ([FORMAT.md](FORMAT.md)) is all a tool needs. pencilmark can also read and write a few
other formats for convenience. None of them is part of the format or required by it.

| Function | Reads | Writes |
|---|---|---|
| `from_string(s)` / `to_string(puzzle, "plain")` | plain classic strings | plain classic strings |
| `from_string(s)` / `to_string(puzzle, "sudokuwiki")` | sudokuwiki.org packed strings | sudokuwiki.org packed strings |
| `to_ipuz(puzzle)` | – | ipuz 2 |
| `pencilmark.sources.load(url)` | f-puzzles, SudokuPad (SCL / fpuz / ctc), Penpa+, Logic Masters links | – |

`from_string` and the site loaders return a `sudoku-puzzle` dict; every entry point (`rate`, `solve`, `load`, the
command line) also accepts these strings directly.

## Plain classic string

- D×D characters in reading order; whitespace and line breaks are ignored.
- Empty cell: `.`, `0`, `-` or `_`. Digits `1`–`9`, then `A`–`Z` for 10–35 (case-insensitive).
- D = √length for D in {4, 6, 8, 9, 10, 12, 14, 15, 16, 20, 25}; boxes are the standard shape (4: 2×2, 6: 2 rows ×
  3 columns, 8: 2×4, 9: 3×3, 10: 2×5, 12: 3×4, 14: 2×7, 15: 3×5, 16: 4×4, 20: 4×5, 25: 5×5).
- `to_string(…, "plain")` writes `.` for empty cells and refuses anything but a classic with standard boxes and no
  other rules.

## sudokuwiki.org packed strings

The solvers on Andrew Stuart's [sudokuwiki.org](https://www.sudokuwiki.org) use packed strings ("Sudoku String
Definitions", version B): a 3-character header (type letter, size digit, version letter), then a fixed-width base-36
number per cell (`0-9a-z`, zero padded) in reading order. pencilmark reads and writes these forms:

| Header | Puzzle | Chars / cell | Cell value |
|---|---|---|---|
| `S9B` | classic 9×9 | 2 | given v → v; empty → 529 (= 511 + 18) |
| `S6B` | classic 6×6 (2×3 boxes) | 2 | given v → v; empty → 81 (= 63 + 18) |
| `X9B` | X-sudoku (both main diagonals) | 2 | as S9B |
| `W9B` | windoku | 2 | as S9B; read as the 4 windows (`region` kind `window`) |
| `C9B` | colour sudoku (9 groups: same position in every box) | 2 | as S9B; read as `region` kind `disjoint` |
| `J9B` | jigsaw 9×9 | 3 | `(box − 1) << 10 \| n`, n as S9B |
| `L9B` | killer 9×9 | 4 | `((colour − 1) << 6 \| clue) << 10 \| n`; given v → v + 9, empty → 529 |
| `M9B` | killer jigsaw 9×9 | 5 | `(((box − 1) << 3 \| colour − 1) << 6 \| clue) << 10 \| n` |
| `L6C` | killer 6×6 | 4 | `((colour − 1) << 11 \| clue_or_op) << 7 \| n`; given v → v + 6, empty → 75 |

- Killer cages: `colour` (1–8) is a colouring in which touching cages differ; cages are the orthogonally connected
  components of equal colour. `clue` is the cage sum, stored in the cage's first cell in reading order. A 1-cell cage
  with clue 0 is no cage (uncaged cells are written that way).
- L6C stores the operator `+` as 1 in the cage's second cell (right neighbour of the first cell, else the one below).
  Any other operator code is refused.
- Any other cell value (placed digits in the plain forms, candidate masks) is refused when read.
- `to_string(puzzle, "sudokuwiki")` picks the header from the structure and refuses anything else (no 6×6 jigsaw or
  X, no killer-X or killer-windoku, nothing above 9×9).

## ipuz export

`to_ipuz(puzzle)` writes [ipuz](http://www.ipuz.org) 2 for the subset that maps cleanly and refuses the rest:

| pencilmark | ipuz |
|---|---|
| one `box_grid` covering the board | kind `http://ipuz.org/sudoku#1`, `boxes: true` |
| no boxes, rows / columns only (Latin square) | `http://ipuz.org/sudoku/latinsquare#1`, `boxes: false` |
| + both main diagonals | `http://ipuz.org/sudoku/diagonalsudoku#1`, `zones` |
| + `region` window | `http://ipuz.org/sudoku/hypersudoku#1`, `zones` with `rect` |
| inferred rows / columns + `box` rules (jigsaw) | `http://ipuz.org/sudoku/jigsawsudoku#1`, `boxes: false`, one zone per box |
| + `cage` | `http://ipuz.org/sudoku/killersudoku#1`, `cages` (`value`), `showoperators: false`, `cageborder: "dashed"` |

`puzzle` and `solution` are row arrays (0 = empty); ipuz coordinates are `[col, row]`, 1-based. `meta` title /
author / url / id / date map to `title`, `author`, `url`, `uniqueid`, `date` (`mm/dd/yyyy`). The complete pencilmark
object goes in `"io.github.silly-puppyy.pencilmark:puzzle"`, with
`"volatile": {"io.github.silly-puppyy.pencilmark": "puzzle,solution,zones,cages"}`. There is no ipuz import.

## Site loaders

`pencilmark.sources` reads f-puzzles, SudokuPad (SCL / fpuz / ctc), Penpa+ and Logic Masters links, and `to_export`
turns the result into a `sudoku-puzzle` file. Writing those formats is not supported. Loaders that fetch pages identify
themselves, obey robots.txt and pause between requests.
