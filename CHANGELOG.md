# Changelog

## Unreleased

- Grade card simplified (one meaning per key, docs/PHILOSOPHY.md): `contains_complete` removed (it was band != Unknown;
  `stopped_at_step` still marks where human logic ran out); `time_dist.median` removed (it repeated `time`); steps use
  the same keys as `contains` (`code`, `name`, `band`; `technique` renamed `name`); `alternatives` is `null` when the
  search was skipped (`alternatives=False`) and omitted only when there are none.
- Docs: philosophy page (goals, exact meaning of band / difficulty / time, format rules); README known issues.

## 1.0.0rc2

- `max_seconds` bounds the whole `rate()` call (uniqueness proof, card, technique list). The band and difficulty route
  runs first, the technique list in the time left. If the limit passes in the route, the card says band `Unknown` with
  `difficulty` / `time` null and the techniques found so far; if uniqueness is not proven in time, `rate` raises
  `Undecided`. New `completed` field whenever `max_seconds` is set.
- `contains_truncated` removed: `completed: false` already says the limit passed (when it passed only while the technique
  list was being minimised, the grade stands and the list may not be minimal).
- Optional `elapsed` field (wall-clock seconds for the call); `solve(puzzle, info=True)` returns the solution with its
  seconds; the generator's `info` has `seconds` and `attempts`.
- Optional `time_dist` field (`{"type": "lognormal", "median", "sigma_players", "sigma_model"}`); `time_p50` accepted.
- Three variant techniques from how people solve on video: clue facts (`CFX`, Very Easy: what a clue rules out on an
  empty grid, e.g. no 5 on a whisper), clue shape (`CSH`, Easy: a line's shape inside one house, e.g. a whisper 4
  between two 9s) and high/low & odd/even colouring (`CCL`, Medium). Accuracy on human data is unchanged on average
  (kropki ranks better); solving routes are shorter and closer to human ones.
- Time spread: `time_mean` and any percentile `time_pNN` (e.g. `time_p20`, `time_p80`) on request, over today's players
  (log-normal; sigma 0.79 for classics and multi-grid layouts, 0.62 with any other rule, from two sources' per-player times). `time_p80` was a one-player spread (1.53x) and is now
  the population one (about 1.85x). `time` is the median player.
- Generator: element varieties (kropki colour, XV letter, odd/even) with counts, ranges and caps; the information-budget
  check uses per-class maximums.
- `spike` check: a Medium+ puzzle whose 3 hardest steps carry more than 60% of its effort (adjustable, `quality`), as a
  warning; replaces the old "few band moves in an all-singles solve" rule.
- Cards without `contains` / `issues` skip the technique-list search: about 3x faster for the same band, difficulty and
  time; the generator screens candidates this way.
- `alternatives=False` / `--no-alternatives`: skip the search for interchangeable techniques (faster; band, difficulty and
  time unchanged). The generator screens candidates this way.
- Faster cards: the search-effort profile stops trials past the shortest refutation and skips unchanged rules; the
  solution is found once per card.
- Publishing checks (`issues`, `reject`) are no longer default card fields; ask for them with `fields=[...]`.
- Docs: the puzzle format (`FORMAT.md`), grade card (`GRADE.md`) and generator spec (`SPEC.md`) are separate
  documents, each saying how to implement a subset; drawing conventions moved out of the format into `STYLE.md`, variant
  naming into `NAMING.md`.
- Drawing: `docs/palette.json` with the default sizes, light and dark themes and the community line colours; reference
  SVG renderer `tools/render_svg.py`.

## 1.0.0rc1

First public release.

- `rate`, `rate_many`, `solve`, `to_export`, `load`: the "sudoku-grade" card (difficulty, time, band, contents, issues /
  reject; on request time_p80, steps with two explanation levels, Sudoku Explainer-style ratings, describe, symmetry;
  `fields=[...]` computes only the requested fields) for classic and variant sudoku.
- Publishing checks (`issues`) with adjustable limits: `quality={"trivial": 0.5, "trial": False}` / `--quality`, the same
  object the generator spec's `quality` takes.
- Command line: `pencilmark rate | solve | json | export | fingerprint | describe` (also `python -m pencilmark`).
- Exchange format: `sudoku-puzzle` format_version 1, read and written, specified in `docs/FORMAT.md` with a JSON Schema (`docs/sudoku-puzzle.schema.json`):
  every constraint is a rule (houses as `grid` / `box_grid` / `box`, explicit `row` / `column` for bent ones; nothing
  implied), cells named `r1c1`, a rule
  vocabulary of families and kinds with exact semantics and default drawings, outside clues anchored by `side`,
  explicit `negative` rules, strict reading (unknown keys or rule types are refused).
- `sudoku-spec` generator requests (givens, locked rules and templates, symmetry, `where` card targets, quality,
  limits); `spec_to_gen` runs what the generator supports and refuses the rest with the reason; showcase specs in
  `docs/examples/specs/`.
- Format functions: `dumps` (canonical text), `fingerprint` (content hash), `validate`, `describe` / `rules_text` (variant
  name and rules from a registry of placement variants and rule families), optional `to_ipuz`, `from_string` / `to_string`
  (plain and sudokuwiki.org strings), `spec_from_gen` / `spec_to_gen` (the `sudoku-spec` generator request).
- Cards carry `"format_version": 1` and `"grader": {"name": "pencilmark", "version": ...}`.
- One engine form per mechanic: renban / between / zipper / region-sum constraints as lines, jigsaw pieces as boxes,
  numbered pair clues (difference / sum / product / ratio, mathrax) as 2-cell tables, duplicated houses merged, global entropy and quadruple clues as named rules for
  every importer (docs/ENGINE.md).
- Puzzle generator (`pencilmark.gen`) with band, difficulty, technique and rule-element targets.
- Puzzle importers (`pencilmark.sources`) for SudokuPad, f-puzzles, penpa-edit and Logic Masters links.
- C++ engine built with pybind11; OR-Tools is optional (`pencilmark[verify]`).
- No guessing by default: where no technique applies, the engine proves an elimination by full search (Trial and error,
  band Extreme), so every uniquely solvable puzzle gets a band; `allow_guessing=True` / `--allow-guessing` guesses there
  instead (band Unknown).
- Bands: forcing chains / nets, Nishio, pattern overlay and trial and error are Extreme; bounded case splits (either
  way, what if, short trial) and ALS chains / Death Blossom are Very Hard.
