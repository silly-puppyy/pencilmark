# Changelog

## 1.0.0 (2026-10-25)

First public release.

- `rate`, `rate_many`, `solve`, `to_export`, `load`: the "sudoku-grade" card (difficulty, time, band, contents, notes,
  optional steps and Sudoku Explainer-style ratings) for classic and variant sudoku.
- Command line: `pencilmark rate | solve | json | export | fingerprint | describe` (also `python -m pencilmark`).
- Exchange format: `sudoku-puzzle` format_version 1, read and written, specified in `docs/FORMAT.md` with a JSON Schema (`docs/sudoku-puzzle.schema.json`):
  every constraint is a rule (houses as `subgrid` / `box_grid` / `box`; nothing implied), cells named `r1c1`, a rule
  vocabulary of families and kinds with exact semantics and default drawings, outside clues anchored by `side`,
  explicit `negative` rules, strict reading (unknown keys or rule types are refused). Older files are still read.
- Format functions: `dumps` (canonical text), `fingerprint` (content hash), `validate`, `describe` / `rules_text` (variant
  name and rules from a registry of placement variants and rule families), `to_ipuz`, `from_string` / `to_string`
  (plain and sudokuwiki.org strings), `spec_from_gen` / `spec_to_gen` (the `sudoku-spec` generator request).
- Cards carry `"format_version": 1` and `"grader": {"name": "pencilmark", "version": ...}`.
- One engine form per mechanic: renban / between / zipper / region-sum constraints as lines, jigsaw pieces as boxes,
  edge-clue tables as pair relations, duplicated houses merged, global entropy and quadruple clues as named rules for
  every importer (docs/FORMAT.md section 15).
- Puzzle generator (`pencilmark.gen`) with band, difficulty, technique and rule-element targets.
- Puzzle importers (`pencilmark.sources`) for SudokuPad, f-puzzles, penpa-edit and Logic Masters links.
- C++ engine built with pybind11; OR-Tools is optional (`pencilmark[verify]`).
