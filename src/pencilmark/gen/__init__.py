"""Puzzle generator: one puzzle for a "sudoku-spec" request (docs/SPEC.md) -- difficulty / band / technique targets,
classic and variants, any standard board size.

    from pencilmark import generate          # or pencilmark.gen.generate
    r = generate({"format": "sudoku-spec", "format_version": 1, "board": {"rows": 9, "cols": 9}, "digits": 9,
                  "rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}], "where": {"band": "Hard"}})
    r["puzzle"]   # sudoku-puzzle (with solution)
    r["card"]     # sudoku-grade card (difficulty, time, band, contains)
    r["info"]     # mode, givens, element counts, attempts, seconds, rejection reasons, unique_verified

The parts of the spec the generator runs are listed in docs/SPEC.md; anything else raises NotSupportedError. Every result
is unique (re-checked with CP-SAT when OR-Tools is installed). Multi-grid boards are not supported by the generator.
"""
from .api import GenerationFailed, generate

__all__ = ["GenerationFailed", "generate"]
