"""pencilmark: human-like sudoku difficulty grader for classic and variant sudoku. Public API: see pencilmark/api.py.

Example:
    import pencilmark
    card = pencilmark.rate("....4.8.3.6...8..2...")      # difficulty, minutes, band, contains
"""

__version__ = "1.0.0"

from .api import (
    FormatError,
    GenerationFailed,
    NoSolution,
    NotSupportedError,
    NotUnique,
    Undecided,
    __all__,  # noqa: F401
    count_solutions,
    describe,
    dumps,  # noqa: F401
    fingerprint,
    from_ipuz,
    from_string,
    generate,
    load,
    rate,
    rate_many,
    rules_text,
    solve,
    to_export,
    to_ipuz,
    to_string,
    validate,
)
