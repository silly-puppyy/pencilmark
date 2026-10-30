# pencilmark

[![PyPI](https://img.shields.io/pypi/v/pencilmark?include_prereleases)](https://pypi.org/project/pencilmark/)
[![Python](https://img.shields.io/badge/python-3.10%E2%80%933.14-blue)](https://pypi.org/project/pencilmark/)
[![Wheels](https://github.com/silly-puppyy/pencilmark/actions/workflows/wheels.yml/badge.svg)](https://github.com/silly-puppyy/pencilmark/actions/workflows/wheels.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/silly-puppyy/pencilmark/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-silly--puppyy.github.io-blue)](https://silly-puppyy.github.io/pencilmark/)

pencilmark rates sudoku puzzles the way a human solver experiences them. It solves a puzzle step by step with human
techniques, easiest first, and reports how hard it is, how long it takes, which band it belongs to and which techniques
you need. It works for classic sudoku of any standard size and for many variants (killer, thermo, arrow, kropki, XV,
sandwich, multi-grid boards and more). It also solves puzzles, checks uniqueness, imports puzzles from [SudokuPad](https://sudokupad.app/),
[f-puzzles](https://www.f-puzzles.com/), [penpa-edit](https://swaroopg92.github.io/penpa-edit/) and [Logic Masters](https://logic-masters.de/) links, and generates new puzzles to a target band or difficulty.

The engine is written in C++ ([pybind11](https://github.com/pybind/pybind11)). Results are deterministic: the same puzzle always gets the same card.

> **Written with AI.** Almost all of pencilmark's code, data analysis and documentation was written by an AI model
> ([Claude](https://claude.ai)), directed and reviewed by its maintainer. If you object to AI-written software, take that
> into account before you use it or contribute.

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
card["band"], card["difficulty"], card["time"]          # ('Hard', 5.9, 10.7)

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
#1  Hard  -  difficulty 5.9  -  time 10.7 min
   contains: Naked Pair (or Hidden Pair), X-Wing (or 2-String Kite / Simple Colouring / Short chain in the head)

pencilmark rate puzzles.txt --json        # full card per line (python -m pencilmark works too)
pencilmark solve puzzles.txt              # the solution, or 'not unique' / 'no solution'
```

More in [docs/USAGE.md](https://github.com/silly-puppyy/pencilmark/blob/main/docs/USAGE.md).

## The card

`rate` returns a dict (format `"sudoku-grade"`) with these fields by default (`grader`, `format`, `format_version` are
always there); `rate(puzzle, fields=[...])` / `--fields` asks for others by their key names, and only requested fields
are computed ([docs/GRADE.md](https://github.com/silly-puppyy/pencilmark/blob/main/docs/GRADE.md)):

| Field | Meaning |
|---|---|
| `difficulty` | how hard each step feels, continuous, above 0 (a nearly finished grid is about 0.2), no ceiling; a typical newspaper medium is about 5 |
| `time` | expected minutes for the median player (on request `time_mean` or any percentile `time_pNN`, e.g. `time_p80`: 80% of players finish within it) |
| `band` | Very Easy, Easy, Medium, Hard, Very Hard, Expert, Extreme; `"Unknown"` when guessing was allowed and used, or `max_seconds` passed (on request `band_index` 0..6) |
| `contains` | techniques met going easy to hard: `code`, `chip`, `name`, `band`, `uses`, `alternatives`; with `stopped_at_step` when human logic ran out |
| on request | `issues` / `reject` (publishing checks, below), `time_mean` / `time_pNN`, `steps` (technique, placement `r2c8=3` or eliminations `r4c5#7`; `explain="notation"` / `"short"` / `"teach"` adds explanations, from `X-Wing: 3 r58 c68 => r679c6<>3` to a short lesson), `se`, `band_index`, `describe`, `symmetry` |

A chip like `XWG/KTE/SCL` means any one of those techniques gets you through at that point.

Publishing checks are off unless you ask for them. They flag puzzles a publisher would usually not pick: a difficulty
spike, a rule that is never used, too many givens, ... (`code`, `severity` reject / warning, `text`, and `rules`: the
offending rules' indices in the exported puzzle); `reject` is true when any issue is a reject. Each check's limit is
adjustable:

```python
card = pencilmark.rate(puzzle, fields=["difficulty", "band", "issues", "reject"], quality={"trivial": {"limit": 0.4}, "trial": {"severity": "off"}})
```

Guessing is off by default: where no technique applies, the engine proves an elimination by full search (Trial and
error, band Extreme), so every uniquely solvable puzzle gets a band. `allow_guessing=True` (CLI `--allow-guessing`) lets it
guess there instead, which is faster on the hardest puzzles; the card then says Unknown, with
`stopped_at_step`. With `max_seconds` set, the whole call is capped and the card
says `completed: false` if the limit passed. A puzzle without exactly one solution has no card: `rate` raises `NotUnique` /
`NoSolution`.

## Exchange format

`to_export` writes, and every entry point reads, the `"sudoku-puzzle"` format, **format_version 1**, specified in
[docs/FORMAT.md](https://github.com/silly-puppyy/pencilmark/blob/main/docs/FORMAT.md) (JSON Schema: [docs/sudoku-puzzle.schema.json](https://github.com/silly-puppyy/pencilmark/blob/main/docs/sudoku-puzzle.schema.json)):

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

For convenience pencilmark also reads and writes [sudokuwiki.org](https://www.sudokuwiki.org/) packed strings, text grids and [ipuz](http://www.ipuz.org/), reads pencil-mark grids, and loads SudokuPad,
f-puzzles, [Penpa](https://swaroopg92.github.io/penpa-edit/)+ and Logic Masters links. None of these is needed to use the `sudoku-puzzle` format; see
[docs/INTEROP.md](https://github.com/silly-puppyy/pencilmark/blob/main/docs/INTEROP.md). How rules map onto the engine, and how to add one, is in
[docs/ENGINE.md](https://github.com/silly-puppyy/pencilmark/blob/main/docs/ENGINE.md).

## Supported rules

Classic sudoku from 4x4 to 25x25, irregular (jigsaw) regions, diagonals and extra regions, multi-grid layouts (samurai,
twodoku, butterfly, windmill and more), killer cages, little killers, sandwich, X-sums, skyscrapers, frame sums,
arrows, thermometers (normal and slow), German and Dutch whispers, renban, region-sum, palindrome, zipper, between,
entropic, modular and parity lines, kropki, XV, greater-than, difference / ratio dots, anti-knight, anti-king,
non-consecutive, odd / even, low / high, Rossini, Vudoku, equal sums, counting rules, and given candidates (Sukaku).
Rules that cannot be translated exactly are refused, never dropped silently.

## Generator

```python
r = pencilmark.generate({"format": "sudoku-spec", "format_version": 1,
                         "board": {"rows": 9, "cols": 9}, "digits": 9,
                         "rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}],
                         "where": {"band": "Hard"}})
r["puzzle"], r["card"], r["info"]       # sudoku-puzzle, its card, run details
```

The request is a `sudoku-spec` ([docs/SPEC.md](https://github.com/silly-puppyy/pencilmark/blob/main/docs/SPEC.md)).

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

- Bands and difficulty measure different things. The band is the hardest technique a puzzle needs; difficulty is how
  hard it is overall. A puzzle that needs one X-Wing (Hard) is often easier than a long Medium one, and solvers agree
  (docs/PHILOSOPHY.md). This is by design, not an error.
- Difficulty and time are models fitted to human solving data. Differences under one point of difficulty are not
  meaningful, and a single solve can vary a lot from the predicted time.
- Bands depend on the technique catalogue; a puzzle that needs a technique the engine does not have is solved with
  Trial and error at that point and rated Extreme.
- Very hard puzzles with many-cell rules (killers, arrows, palindromes, thermos) can take minutes while the contents list
  is minimised; use `max_seconds` to cap it (the card then says `completed: false`).
- The Sudoku Explainer-style ratings (`se=True`) are approximate and meaningful for classic sudoku only.

## Benchmark

On a frozen held-out set of 7,623 puzzles with real human solve data from seven sources, pencilmark's difficulty ranks
puzzles by human solve time at Spearman 0.61 to 0.80 within each group, closer than four established graders on the same
classics. Details: [docs/BENCHMARK.md](https://github.com/silly-puppyy/pencilmark/blob/main/docs/BENCHMARK.md).

## Known issues

Being worked on after 1.0:

- **Speed.** Grading takes a median 0.5 s per puzzle, but the slowest few percent take 10 s to minutes. On the
  benchmark's classics: pencilmark 0.04 s, Rangsk's solver 0.09 s, Sudoku Explainer and HoDoKu under a millisecond (they do
  not model human solving); on variants: pencilmark 0.49 s, Rangsk's solver 0.13 s. Use `max_seconds` to bound a call.
- **Generator speed and range.** About 20-70 s per puzzle that meets a spec (HoDoKu: 0.05-1 s), and classic Extreme puzzles
  are not reached within the default 120 s. A maximum on the givens count is not always enforced.
- **Variants on one scale.** On classics, difficulty matches established ratings of the same puzzles; across variant
  types the same difficulty does not yet mean the same experience (puzzle types differ by about 2 points on average, and
  variants often score above the classic range of their band). Time is most off for the same reason (about 1.4x per
  puzzle type).
- **The ends of the scale.** Between about 2 and 8, each point of difficulty means about 20-40% more solving time per
  cell. Above about 8 a point is worth less time (5-15% on three sources). Below 2 the scale is gentler (about the square root of
  effort, so it never goes negative); there it predicts solve times about 1.5% worse than a pure log scale would.
- **Uniqueness on some killers.** A few large killers can raise `Undecided` without OR-Tools (`pip install
  "pencilmark[verify]"`) although human logic solves them.

## License

MIT, see [LICENSE](https://github.com/silly-puppyy/pencilmark/blob/main/LICENSE).
