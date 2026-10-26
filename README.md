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
exp   = pencilmark.to_export(puzzle, title="My puzzle") # "sudoku-puzzle" exchange format (docs/FORMAT.md)
```

A puzzle can be a classic string (`.` or `0` for blanks), a `sudoku-puzzle` dict, a puzzle JSON dict or string, or a
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

`rate` returns a dict (format `"sudoku-grade"`) with these fields by default (`grader`, `format`, `format_version` are
always there); `rate(puzzle, fields=[...])` / `--fields` asks for others, and only requested fields are computed
([docs/FORMAT.md](docs/FORMAT.md) 11.1):

| Field | Meaning |
|---|---|
| `difficulty` | how hard each step feels, continuous from 0 (one empty cell) with no ceiling; a typical newspaper medium is about 5 |
| `time` | expected minutes for an average player (`time.p80` on request: 80% of players finish within it) |
| `band`, `band_index` | Very Easy (0), Easy, Medium, Hard, Very Hard, Extreme (5); `"Unknown"` (null) only with `allow_guessing=True`, when the engine had to guess |
| `contains` | techniques met going easy to hard: `code`, `chip`, `name`, `band`, `uses`, `alternatives` |
| `issues`, `reject` | publishing checks such as a difficulty spike or an unused rule (`code`, `severity` reject / warning, `text`, and `rules`: the offending rules' indices in the exported puzzle); `reject` is true when any issue is a reject |
| on request | `steps` (technique, placement `r2c8=3` or eliminations `r4c5#7`) with `steps.explanation.short` / `.teach`, `se` / `se.diuf`, `describe`, `symmetry` |

A chip like `XWG/KTE/SCL` means any one of those techniques gets you through at that point.

Guessing is off by default: where no technique applies, the engine proves an elimination by full search (Trial and
error, band Extreme), so every uniquely solvable puzzle gets a band. `allow_guessing=True` (CLI `--allow-guessing`) lets it
guess there instead, which is faster on the hardest puzzles; the card then says Unknown, with `contains_complete: false`
and `stopped_at_step`. With `max_seconds` set, the contents search is capped and the card
may say `contents_truncated`.

## Exchange format

`to_export` writes, and every entry point reads, the `"sudoku-puzzle"` format, **format_version 1**, specified in
[docs/FORMAT.md](docs/FORMAT.md) (JSON Schema: [docs/sudoku-puzzle.schema.json](docs/sudoku-puzzle.schema.json)):

```json
{"format": "sudoku-puzzle", "format_version": 1,
 "meta": {"title": "Heartstring", "author": "...", "source": "example.org", "type": "Killer Sudoku"},
 "board": {"rows": 9, "cols": 9},
 "digits": 9,
 "givens":   [0, 0, 5, 4, 0, ...],
 "solution": [6, 1, 5, 4, 2, ...],
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "cage", "sum": 15, "cells": ["r1c4", "r1c5", "r2c4"]},
  {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r5c5", "r5c6"]}]}
```

- Every constraint is a rule, houses included: a `grid` gives a sudoku grid's rows and columns, a `box_grid` adds its
  regular boxes, so a classic is one `box_grid` and a jigsaw is a `grid` plus `box` rules. Nothing is implied. Cells are
  named `r{row}c{col}`, 1-based.
  `givens`: `0` = empty, `null` = no cell (multi-grid gaps).
- Each rule has one exact meaning and a default drawing, so a renderer needs nothing else; `style` and `decorations`
  are cosmetic only. `meta` is free-form information that never changes solving.
- Strict reading: an unknown key or rule type makes the reader refuse the file (`FormatError`) instead of dropping a
  rule.
- `pencilmark.dumps` writes the canonical text (one grid row per line, one rule per line); `pencilmark.fingerprint`
  gives a content hash that ignores metadata and styling; `pencilmark.describe` names the variant and lists its rules.

### Other formats

For convenience pencilmark also reads and writes sudokuwiki.org packed strings, exports ipuz, and loads SudokuPad,
f-puzzles, Penpa+ and Logic Masters links. None of these is needed to use the `sudoku-puzzle` format; see
[docs/INTEROP.md](docs/INTEROP.md). How rules map onto the engine, and how to add one, is in
[docs/ENGINE.md](docs/ENGINE.md).

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
- Bands depend on the technique catalogue; a puzzle that needs a technique the engine does not have is solved with
  Trial and error at that point and rated Extreme.
- Very hard puzzles with many-cell rules (killers, arrows, palindromes, thermos) can take minutes while the contents list
  is minimised; use `max_seconds` to cap it (the card then says `contents_truncated`).
- The Sudoku Explainer-style ratings (`se=True`) are approximate and meaningful for classic sudoku only.

## Benchmark

See BENCHMARK.md (not yet published).

## License

MIT, see [LICENSE](LICENSE).

pencilmark was written with [Claude](https://claude.ai).
