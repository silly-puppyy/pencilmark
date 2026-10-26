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

Anything else (other puzzle types or versions, placed digits or candidates, 6×6 killer operators other than `+`) is
refused when read. `to_string(puzzle, "sudokuwiki")` picks the header from the structure and refuses puzzles none of
these headers can express (a 6×6 jigsaw or X, killer-X, killer-windoku, anything above 9×9).

## ipuz export

`to_ipuz(puzzle)` writes [ipuz](http://www.ipuz.org) 2 ([sudoku kinds](http://www.ipuz.org/sudoku)) for the subset that maps cleanly and refuses the rest:

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

`pencilmark.sources` reads [f-puzzles](https://www.f-puzzles.com), [SudokuPad](https://sudokupad.app) (SCL / fpuz /
ctc), [Penpa+](https://swaroopg92.github.io/penpa-edit/) and [Logic Masters](https://logic-masters.de) links, and `to_export`
turns the result into a `sudoku-puzzle` file. Writing those formats is not supported. Loaders that fetch pages identify
themselves, obey robots.txt and pause between requests.
