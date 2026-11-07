"""pencilmark: human-like sudoku difficulty grader for classic and variant sudoku. Public API: see pencilmark/api.py.

Example:
    import pencilmark
    card = pencilmark.rate("....4.8.3.6...8..2...")      # difficulty, minutes, band, contains
"""

__version__ = "1.2.0"

import logging

from . import read, write  # noqa: F401  (pencilmark.read.<format>, pencilmark.write.<format>)
from .api import (
    Error,
    FetchError,
    FormatError,
    GenerationFailed,
    NoSolution,
    NotSupportedError,
    NotUnique,
    ReadingMismatch,
    Undecided,
    __all__,  # noqa: F401
    count_solutions,
    describe,
    fingerprint,
    generate,
    rate,
    rate_many,
    solve,
    validate,
)

# the "pencilmark" logger is silent unless the application configures logging (docs: Logging)
logging.getLogger(__name__).addHandler(logging.NullHandler())
