# pencilmark

pencilmark rates sudoku puzzles the way a human solver experiences them. It solves a puzzle step by step with human
techniques, easiest first, and reports how hard it is, how long it takes, which band it belongs to and which techniques
you need. It works for classic sudoku of any standard size and for many variants (killer, thermo, arrow, kropki, XV,
sandwich, multi-grid boards and more). It also solves puzzles, checks uniqueness, imports puzzles from SudokuPad,
f-puzzles, penpa-edit and Logic Masters links, and generates new puzzles to a target band or difficulty.

The engine is written in C++ (pybind11). Results are deterministic: the same puzzle always gets the same card.

## Install

```
pip install pencilmark
pip install "pencilmark[verify]"      # optional: OR-Tools CP-SAT as a fallback uniqueness checker
```

Python 3.10 or newer. Building from source needs a C++17 compiler.

## Quick start

```python
import pencilmark

card = pencilmark.rate("....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......")
card["band"], card["difficulty"], card["time"]          # ('Medium', 5.9, 10.7)

card  = pencilmark.rate(puzzle, steps=True)             # add the step-by-step solve with explanations
cards = pencilmark.rate_many(puzzles, jobs=4)           # several puzzles in parallel, input order kept
sol   = pencilmark.solve(puzzle)                        # list of digits; raises NotUnique / NoSolution
exp   = pencilmark.to_export(puzzle, title="My puzzle") # "sudoku-puzzle" exchange format, metadata under "meta"
```

A puzzle can be a classic string (`.` or `0` for blanks), a puzzle JSON dict or string, a `sudoku-puzzle` dict, or a
path to a `.json` file.

Command line:

```
$ echo '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......' | pencilmark rate - --report
#1  Medium  -  difficulty 5.9  -  time 10.7 min (80% of players within 16.4 min)
   contains: Naked Pair (or PPR/HPR), X-Wing (or KTE/SCL)

pencilmark rate puzzles.txt --json        # full card per line (python -m pencilmark works too)
pencilmark solve puzzles.txt              # the solution, or 'not unique' / 'no solution'
```

More in [docs/USAGE.md](docs/USAGE.md).

## The card

`rate` returns a dict (format `"sudoku-grade"`):

| Field | Meaning |
|---|---|
| `difficulty` | how hard each step feels, continuous from 0 (one empty cell) with no ceiling; a typical newspaper medium is about 5 |
| `time`, `time_p80` | expected minutes for an average player; 80% of players finish within `time_p80` |
| `band`, `band_index` | Very Easy (0), Easy, Medium, Hard, Very Hard, Extreme (5), or `"Unknown"` (null) when human logic runs out |
| `contains` | techniques met going easy to hard: `code`, `chip`, `name`, `band`, `uses`, `alternatives` |
| `notes` | publishing notes such as a difficulty spike or an unused rule (`code`, `severity`, `text`) |
| `steps` | with `steps=True`: technique, placement (`r2c8=3`) or eliminations (`r4c5#7`), explanation |

A chip like `XWG/KTE/SCL` means any one of those techniques gets you through at that point. Unknown puzzles carry
`contains_complete: false` and `stopped_at_step`. With `max_seconds` set, the contents search is capped and the card
may say `contents_truncated`.

## Exchange format

`to_export` writes, and every entry point reads, the `"sudoku-puzzle"` format:

```json
{"format": "sudoku-puzzle",
 "meta": {"title": "Heartstring", "author": "...", "source": "example.org", "date": "2026-10-25"},
 "grid": {"rows": 9, "cols": 9}, "digits": 9,
 "givens":   [0, 0, 5, 4, 0, ...],
 "solution": [6, 1, 5, 4, 2, ...],
 "boxes": [[0, 1, 2, 9, 10, 11, 18, 19, 20], ...],
 "regions": [{"kind": "cage", "cells": [3, 4, 12], "sum": 15}],
 "rules": [{"type": "kropki", "color": "white", "cells": [40, 41]}]}
```

- `meta` is optional, like EXIF: information about the puzzle that never changes how it is solved or rated. All keys
  are optional and free-form, and tools keep keys they don't know. Common keys: `title`, `author`, `source` (website
  domain), `id`, `url`, `date` (ISO 8601), `rules_text`, `type`, `license`, `tags`. Older files with these keys at the
  top level are still read.
- Cells are flat indices in reading order: `index = row * cols + col`.
- `givens`: `0` = empty cell, `null` = no cell at that position (the gaps of multi-grid boards such as samurai).
- `boxes` are always listed. `units` (rows / columns per sub-grid) appear only when the board is not one plain grid.
- `regions` holds other no-repeat groups: diagonals, extra regions, killer cages with `sum`.
- `rules` holds everything else with cell indices; `candidates` holds given pencil marks (Sukaku).
- A pair rule that covers the whole grid is written compactly: `{"type": "pairs", "rel": "notsum", "params": [10],
  "where": "orthogonal", "except": [[0, 1]]}` means every orthogonal neighbour pair except those listed (`where` is
  `orthogonal`, `diagonal`, `king` or `knight`). Full-grid non-consecutive is written `{"type": "nonconsecutive"}`.

The richer input format (`pencilmark.puzzle_json`, with `r1c1` cell names) is described in that module.

## Supported rules

Classic sudoku from 4x4 to 25x25, irregular (jigsaw) regions, diagonals and extra regions, multi-grid layouts (samurai,
twodoku, butterfly, windmill and more), killer cages, little killers, sandwich, X-sums, skyscrapers, frame sums,
arrows, thermometers (normal and slow), German and Dutch whispers, renban, region-sum, palindrome, zipper, between,
entropic, modular and parity lines, kropki, XV, greater-than, difference / ratio dots, anti-knight, anti-king,
non-consecutive, odd / even, low / high, Rossini, Vudoku, equal sums, counting rules, and given candidates (Sukaku).
Rules that cannot be translated exactly are refused, never dropped silently.

## Generator

```python
from pencilmark.gen import generate
r = generate({"size": 9, "target_band": "Hard", "seed": 1})
r["puzzle"], r["card"], r["info"]
```

Targets: band, difficulty range, required techniques, symmetry, given counts, and rule elements (cages, thermos,
whispers, renban, between lines, arrows, kropki, XV, parity). Every result is checked for uniqueness. Multi-grid boards
are not generated.

## Puzzle sources

```python
from pencilmark import sources
pj = sources.load("https://sudokupad.app/...")      # SudokuPad, f-puzzles, penpa-edit, Logic Masters, short links
card = pencilmark.rate(pj)
```

Loaders that fetch pages identify themselves, obey robots.txt and pause between requests. Override the user agent with
the `PENCILMARK_UA` environment variable.

## Limitations

- Difficulty and time are models fitted to human solving data. Differences under one point of difficulty are not
  meaningful, and a single solve can vary a lot from the predicted time.
- Bands depend on the technique catalogue; puzzles that need techniques the engine does not have are rated Unknown.
- A few very hard killers can take many minutes while the contents list is minimised; use `max_seconds` to cap it.
- The Sudoku Explainer-style ratings (`se=True`) are approximate and meaningful for classic sudoku only.

## Benchmark

See BENCHMARK.md (not yet published).

## License

MIT, see [LICENSE](LICENSE).
