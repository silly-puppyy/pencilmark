"""Every error pencilmark raises: one family under `Error`. Input mistakes are ValueErrors (the input is wrong as given),
a network problem an OSError, the engine giving up a RuntimeError."""


class Error(Exception):
    """Base class of every pencilmark error."""


class FormatError(Error, ValueError):
    """The input is not valid in its format: unknown key or rule type, bad cell, failed structural check, an unreadable
    link or payload."""


class NotSupportedError(Error, ValueError):
    """The input is valid in its format, but uses something pencilmark cannot build or write. `elements` lists what
    (nothing is dropped silently)."""

    def __init__(self, message, elements=()):
        super().__init__(message)
        self.elements = list(elements)


class FetchError(Error, OSError):
    """A network request failed, or robots.txt forbids it."""


class ReadingMismatch(Error, ValueError):
    """A site puzzle read this way contradicts the setter's embedded solution."""


class NotUnique(Error, ValueError):
    """The puzzle has more than one solution."""


class NoSolution(Error, ValueError):
    """The puzzle has no solution."""


class Undecided(Error, RuntimeError):
    """The exhaustive search hit its node or time limit and OR-Tools (pip install "pencilmark[verify]") is not
    available."""


class GenerationFailed(Error, RuntimeError):
    """No puzzle met the spec within the time limit (or the spec is infeasible); str(e) says why."""

    def __init__(self, reason, stats=None):
        super().__init__(reason)
        self.reason, self.stats = reason, stats or {}


def unsupported(elements, source=""):
    """A NotSupportedError for elements a reader cannot model exactly."""
    els = [elements] if isinstance(elements, str) else list(elements)
    return NotSupportedError((f"{source}: " if source else "") + "unsupported: " + ", ".join(els), els)
