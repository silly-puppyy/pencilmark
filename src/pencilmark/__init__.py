"""pencilmark: human-like sudoku difficulty grader for classic and variant sudoku. Public API: see pencilmark/api.py.

    import pencilmark
    card = pencilmark.rate("....4.8.3.6...8..2...")      # difficulty, minutes, band, contains
"""
__version__ = "1.0.0rc2"

from .api import (rate, rate_many, solve, to_export, load, NotUnique, NoSolution, Undecided, dumps,  # noqa: F401
                  fingerprint, validate, describe, rules_text, to_ipuz, from_string, to_string, spec_from_gen, spec_to_gen,
                  FormatError, NotSupportedError)
from .api import __all__  # noqa: F401
