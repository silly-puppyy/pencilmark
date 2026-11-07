"""Reading puzzles: one function per format, each returning a pencilmark-puzzle document (a dict,
docs/formats/puzzle-format.md). A reader reads its own format only and raises FormatError for anything else; `detect`
names the format of an input and `auto` reads any of them (what `rate`, `solve` and the command line do).

    pencilmark(x)          pencilmark JSON: a dict, JSON text or a .json path
    plain(text)            one string of D x D characters, maybe followed by a comment
    grid(text)             rows on lines, with or without | - + separators
    pencil_marks(text)     a pencil-mark grid, one token of candidates per cell
    candidates(text)       a 729-character candidate string
    hodoku(line)           a HoDoKu library line
    sudokuwiki(text)       a sudokuwiki.org packed string (S9B, J9B, ...)
    ipuz(x)                an ipuz sudoku: a dict, JSON text or a .ipuz path
    link(url)              a SudokuPad, f-puzzles, Penpa or Logic Masters link (the host names the format)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import interop
from .errors import FormatError

LINK_PREFIXES = ("lmd:", "sudokupad:", "penpa:", "scl", "ctc", "fpuzzles", "fpuz", "scv")


def _json(x):
    """a dict from a dict, JSON text or a path to a JSON file"""
    if isinstance(x, dict):
        return x
    if isinstance(x, Path) or (isinstance(x, str) and "\n" not in x and x.strip().endswith((".json", ".ipuz"))):
        try:
            return json.loads(Path(x).read_text(encoding="utf-8"))
        except OSError as e:
            raise FormatError(f"cannot read {x}: {e}") from e
    if isinstance(x, str) and x.lstrip().startswith("{"):
        try:
            return json.loads(x)
        except ValueError as e:
            raise FormatError(f"not JSON: {e}") from e
    raise FormatError("not a JSON document, JSON text or path")


def pencilmark(x: str | dict | Path) -> dict:
    """Read pencilmark JSON: a pencilmark-puzzle dict, its JSON text or a path to a .json file."""
    from .exchange import FORMAT, canonical

    d = _json(x)
    if d.get("format") != FORMAT:
        raise FormatError(f'not pencilmark JSON ("format": "{FORMAT}" missing)')
    return canonical(d)


def plain(text: str, *, symbols: str | None = None) -> dict:
    """Read a plain string: D x D characters ('.' or '0' empty, 1-9 then A-Z), maybe followed by a comment. symbols: the
    symbol of each digit in order (e.g. "ABCDEFGHI" reads A as 1)."""
    return interop.read_plain(text, symbols)


def grid(text: str) -> dict:
    """Read a text grid: one row per line, with or without | - + separators."""
    return interop.read_grid(text)


def pencil_marks(text: str) -> dict:
    """Read a pencil-mark grid: one token per cell, the cell's candidates (a single digit: a given)."""
    return interop.read_pencil_marks(text)


def candidates(text: str) -> dict:
    """Read a 729-character candidate string (9 characters per cell, the digit or 0)."""
    return interop.read_candidates(text)


def hodoku(line: str) -> dict:
    """Read a HoDoKu library line: the puzzle and its removed candidates."""
    return interop.read_hodoku(line)


def sudokuwiki(text: str) -> dict:
    """Read a sudokuwiki.org packed string (S9B, J9B, X9B, W9B, C9B, L9B, M9B, S6B, L6C)."""
    return interop.read_sudokuwiki(text)


def ipuz(x: str | dict | Path) -> dict:
    """Read an ipuz sudoku: a dict, its JSON text or a path to a .ipuz file."""
    return interop.from_ipuz(_json(x))


def link(url: str) -> dict:
    """Read a SudokuPad, f-puzzles, Penpa, Logic Masters or sudoku.coach link (or a short link to one; some need one
    request). A reading the setter's embedded solution contradicts raises ReadingMismatch."""
    from . import sources

    first = url.split()[0] if isinstance(url, str) and url.split() else url
    if not _is_link(first):
        raise FormatError(f"not a puzzle link: {str(url)[:80]!r}")
    if sources.detect(first) == "coach":  # read straight into the format, the setter's look kept
        return sources.coach.read(first)
    return _document(sources.load(first))


def _document(pj):
    """the engine's own JSON (what the site readers produce) -> pencilmark-puzzle dict, its metadata and drawing
    styles kept"""
    from . import puzzle_json as PJ
    from .export import export_puzzle, read_meta

    p = PJ.from_json(pj)
    p.finalize()
    doc = export_puzzle(p, meta=read_meta(pj), solution=None)
    if getattr(p, "drawn", None):
        from .sources._sp_style import apply

        doc = apply(doc, p.drawn)
    return doc


def _is_link(s):
    return isinstance(s, str) and ("://" in s or s.lower().startswith(LINK_PREFIXES))


READERS = {
    "pencilmark": pencilmark,
    "plain": plain,
    "grid": grid,
    "pencil_marks": pencil_marks,
    "candidates": candidates,
    "hodoku": hodoku,
    "sudokuwiki": sudokuwiki,
    "ipuz": ipuz,
    "link": link,
}


def detect(x) -> str | None:
    """Name the format of x (a key of READERS: "pencilmark", "plain", ..., "link"), or None; reads nothing but a file
    named by a path."""
    if isinstance(x, (dict, Path)) or (isinstance(x, str) and x.lstrip().startswith("{")):
        try:
            d = _json(x)
        except FormatError:
            return None
        if "ipuz.org" in str(d.get("version", "")):
            return "ipuz"
        from .exchange import FORMAT

        return "pencilmark" if d.get("format") == FORMAT else None
    if not isinstance(x, str):
        return None
    s = x.strip()
    if "\n" not in s and s.endswith((".json", ".ipuz")) and Path(s).is_file():
        return detect(Path(s))
    if _is_link(s.split()[0] if s.split() else ""):
        return "link"
    return interop.text_form(x)


def auto(x: str | dict | Path, *, format: str | None = None) -> dict:  # noqa: A002 (the format's name, as in rate(format=))
    """Read x in its format (detected, or named by format)."""
    name = format or detect(x)
    if name is None and isinstance(x, str):  # the closest reader says what is wrong
        t = x.strip()
        if t.startswith("{"):
            return pencilmark(t)
        if t and re.fullmatch(r"[0-9.]+", t):
            from . import puzzle_json as PJ

            raise FormatError(
                f"a plain string has {', '.join(map(str, sorted(PJ.SIZES)))} characters; this one has {len(t)}"
            )
    if name is None:
        raise FormatError(f"not a puzzle form pencilmark reads (tried {', '.join(READERS)}): {str(x)[:80]!r}")
    if name not in READERS:
        raise FormatError(f"unknown format {name!r}; known: {', '.join(READERS)}")
    return READERS[name](x)
