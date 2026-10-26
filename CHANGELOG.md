# Changelog

## 1.0.0 (2026-10-25)

First public release.

- `rate`, `rate_many`, `solve`, `to_export`, `load`: the "sudoku-grade" card (difficulty, time, band, contents, issues /
  reject; on request time.p80, steps with two explanation levels, Sudoku Explainer-style ratings, describe, symmetry;
  `fields=[...]` computes only the requested fields) for classic and variant sudoku.
- Command line: `pencilmark rate | solve | json | export | fingerprint | describe` (also `python -m pencilmark`).
- Exchange format: `sudoku-puzzle` format_version 1, read and written, specified in `docs/FORMAT.md` with a JSON Schema (`docs/sudoku-puzzle.schema.json`):
  every constraint is a rule (houses as `box_grid` / `box`, rows and columns of other cells inferred from the board
  shape, explicit `row` / `column` for bent ones), cells named `r1c1`, a rule
  vocabulary of families and kinds with exact semantics and default drawings, outside clues anchored by `side`,
  explicit `negative` rules, strict reading (unknown keys or rule types are refused). Older files are still read.
- `sudoku-spec` generator requests (givens, locked rules and templates, symmetry, `where` card targets, quality,
  limits); `spec_to_gen` runs what the generator supports and refuses the rest with the reason; showcase specs in
  `docs/examples/specs/`.
- Format functions: `dumps` (canonical text), `fingerprint` (content hash), `validate`, `describe` / `rules_text` (variant
  name and rules from a registry of placement variants and rule families), `to_ipuz`, `from_string` / `to_string`
  (plain and sudokuwiki.org strings), `spec_from_gen` / `spec_to_gen` (the `sudoku-spec` generator request).
- Cards carry `"format_version": 1` and `"grader": {"name": "pencilmark", "version": ...}`.
- One engine form per mechanic: renban / between / zipper / region-sum constraints as lines, jigsaw pieces as boxes,
  numbered pair clues (difference / sum / product / ratio, mathrax) as 2-cell tables, duplicated houses merged, global entropy and quadruple clues as named rules for
  every importer (docs/FORMAT.md section 15).
- Puzzle generator (`pencilmark.gen`) with band, difficulty, technique and rule-element targets.
- Puzzle importers (`pencilmark.sources`) for SudokuPad, f-puzzles, penpa-edit and Logic Masters links.
- C++ engine built with pybind11; OR-Tools is optional (`pencilmark[verify]`).
- No guessing by default: where no technique applies, the engine proves an elimination by full search (Trial and error,
  band Extreme), so every uniquely solvable puzzle gets a band; `allow_guessing=True` / `--allow-guessing` guesses there
  instead (band Unknown).
- Bands: forcing chains / nets, Nishio, pattern overlay and trial and error are Extreme; bounded case splits (either
  way, what if, short trial) and ALS chains / Death Blossom are Very Hard.
