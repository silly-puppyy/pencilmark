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
    draw,
    fingerprint,
    generate,
    rate,
    rate_many,
    solve,
    validate,
)

# the "pencilmark" logger is silent unless the application configures logging, or calls log() (docs: Logging)
logging.getLogger(__name__).addHandler(logging.NullHandler())
TRACE = 5  # below debug: every step of the card's route and every test of the technique-list search
logging.addLevelName(TRACE, "TRACE")


def log(level="info", stream=None):
    """Write pencilmark's log to stderr (or stream) at level "info", "debug" or "trace", each line with the
    milliseconds since the program started: info says what happened (pages read, limits reached, generator results),
    debug adds each stage's time (uniqueness, band route, card, technique list) and generator attempts, trace adds
    every route step and every technique-list test. A second call changes the level. None switches it off."""
    import sys

    lg = logging.getLogger(__name__)
    h = next((h for h in lg.handlers if getattr(h, "_pencilmark", False)), None)
    if level is None:
        if h:
            lg.removeHandler(h)
        lg.setLevel(logging.NOTSET)
        return
    if h is None:
        h = logging.StreamHandler(stream or sys.stderr)
        h._pencilmark = True
        h.setFormatter(logging.Formatter("%(relativeCreated)8.0f ms  %(name)s: %(message)s"))
        lg.addHandler(h)
    lg.setLevel(TRACE if str(level).lower() == "trace" else str(level).upper())
