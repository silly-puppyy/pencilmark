"""pencilmark: human-like sudoku difficulty grader for classic and variant sudoku. Public API: see pencilmark/api.py.

    import pencilmark
    card = pencilmark.rate("....4.8.3.6...8..2...")      # difficulty, minutes, band, contains
"""
__version__ = "1.0.0"

from .api import rate, rate_many, solve, to_export, load, NotUnique, NoSolution, Undecided  # noqa: F401

__all__ = ["rate", "rate_many", "solve", "to_export", "load", "NotUnique", "NoSolution", "Undecided"]
