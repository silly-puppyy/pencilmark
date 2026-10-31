"""Reading a puzzle: every input form pencilmark accepts, in the order they are tried. load(), to_export() and the
command line all read through here.

    read(x)              -> a puzzle dict: puzzle JSON, a sudoku-puzzle document, an ipuz file or a sample-pack line
    to_puzzle_json(obj)  -> puzzle JSON (pencilmark.puzzle_json), whatever read() returned
"""

from __future__ import annotations

import json
from pathlib import Path

LINK_PREFIXES = ("lmd:", "sudokupad:", "penpa:", "scl", "ctc", "fpuzzles", "fpuz")  # pencilmark.sources forms


def link(s):
    """puzzle JSON for a site link or payload (pencilmark.sources: SudokuPad, f-puzzles, Penpa, Logic Masters, short
    links; some fetch one page), or None when s is not one"""
    if "://" not in s and not s.lower().startswith(LINK_PREFIXES):
        return None
    from . import sources

    if sources.detect(s):
        return sources.load(s)
    if "://" in s:
        raise ValueError(f"not a puzzle link pencilmark reads (SudokuPad, f-puzzles, Penpa, Logic Masters): {s[:80]}")
    return None


def _text(s):
    """a classic string, text grid, pencil-mark grid, candidate string, HoDoKu line or sudokuwiki packed string; with
    more than one word, the whole text first, then its first word (a trailing comment or rating column)"""
    from .interop import _PACKED, from_string

    words = s.split()
    if len(words) > 1:
        try:
            return from_string(s)
        except ValueError:
            pass
    tok = words[0] if words else ""
    return from_string(tok) if _PACKED.fullmatch(tok) else {"numbers": tok}


def _first_word(s):
    return s.split()[0] if s.split() else ""


# (form, read): tried in order; read returns None when the input is not of its form. JSON text comes before links,
# since a JSON document may hold a URL (an ipuz version, a source in meta).
READERS = (
    (
        "JSON file",
        lambda x: (
            json.loads(Path(x).read_text(encoding="utf-8"))
            if isinstance(x, Path) or (isinstance(x, str) and x.endswith(".json") and Path(x).exists())
            else None
        ),
    ),
    ("JSON text", lambda x: json.loads(x) if isinstance(x, str) and x.lstrip().startswith("{") else None),
    ("puzzle dict", lambda x: x if isinstance(x, dict) else None),
    ("link", lambda x: link(_first_word(x)) if isinstance(x, str) else None),
    ("text", lambda x: _text(x) if isinstance(x, str) else None),
)


def read(x):
    """any accepted input -> a puzzle dict (see the module docstring); TypeError for an input of no known form"""
    for _form, fn in READERS:
        obj = fn(x)
        if obj is not None:
            return obj
    raise TypeError(f"unsupported puzzle input: {type(x).__name__}")


def to_puzzle_json(obj):
    """accept puzzle JSON, the sudoku-puzzle exchange format, an ipuz sudoku, or a
    sample-pack line {"puzzle": ..., "grade": ...}."""
    if "puzzle" in obj and isinstance(obj["puzzle"], dict):
        obj = obj["puzzle"]
    if "ipuz.org" in str(obj.get("version", "")):  # an ipuz file (docs/INTEROP.md)
        from .interop import from_ipuz

        obj = from_ipuz(obj)
    if obj.get("format") == "sudoku-puzzle":
        from .export import import_puzzle

        return import_puzzle(obj)
    return obj
