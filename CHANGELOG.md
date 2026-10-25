# Changelog

## 1.0.0 (2026-10-25)

First public release.

- `rate`, `rate_many`, `solve`, `to_export`, `load`: the "sudoku-grade" card (difficulty, time, band, contents, notes,
  optional steps and Sudoku Explainer-style ratings) for classic and variant sudoku.
- Command line: `pencilmark rate | solve | json` (also `python -m pencilmark`).
- `sudoku-puzzle` exchange format, read and written.
- Puzzle generator (`pencilmark.gen`) with band, difficulty, technique and rule-element targets.
- Puzzle importers (`pencilmark.sources`) for SudokuPad, f-puzzles, penpa-edit and Logic Masters links.
- C++ engine built with pybind11; OR-Tools is optional (`pencilmark[verify]`).
