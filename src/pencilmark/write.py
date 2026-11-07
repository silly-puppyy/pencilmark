"""Writing puzzles: one function per format. Each takes anything `pencilmark.read.auto` reads (pencilmark JSON, a
plain string, a link, ...) and raises NotSupportedError when the format cannot carry the puzzle.

    pencilmark(x)    pencilmark JSON text (canonical); solution= and describe= fill those fields
    document(x)      the same as a dict
    plain(x)         one string of D x D characters (classic sudoku)
    grid(x)          rows on lines with | and -+- separators (classic sudoku)
    sudokuwiki(x)    a sudokuwiki.org packed string
    ipuz(x)          an ipuz 2 dict
"""

from __future__ import annotations

from pathlib import Path


def document(x: str | dict | Path, *, solution: bool = False, describe: bool = False, style: bool = True) -> dict:
    """The pencilmark-puzzle dict of x, canonical. solution: add the solution (when the puzzle has exactly one);
    describe: fill an empty meta.type / meta.rules_text / meta.variants (never overwritten); style=False: leave out
    the drawing (the rules' style, the top-level style and decorations)."""
    from .api import _load
    from .exchange import canonical
    from .export import read_meta

    doc = canonical(_source(x))
    if not style:
        doc = {k: v for k, v in doc.items() if k not in ("style", "decorations")}
        doc["rules"] = [{k: v for k, v in r.items() if k != "style"} for r in doc.get("rules") or []]
    if solution and not doc.get("solution"):
        from .api import solve
        from .errors import Undecided
        from .exchange import write

        p = x if hasattr(x, "coords") else _load(doc)
        try:
            sol = getattr(p, "_pm_solution", None) or solve(p)
        except (ValueError, Undecided):  # no solution, several, or none found in the search limit: left out
            sol = None
        if sol is not None:
            doc = canonical(dict(doc, solution=write(p, solution=sol)["solution"]))
    meta = doc.get("meta") or {}
    if describe and not (meta.get("type") and meta.get("rules_text") and meta.get("variants")):
        from .variants import describe as _describe
        from .variants import public

        dsc = public(_describe(doc))
        m2 = dict(meta)
        for k in ("type", "rules_text", "variants"):
            if not m2.get(k):
                m2[k] = dsc[k]
        doc = canonical(dict(doc, meta=read_meta({"meta": m2})))
    return doc


def _source(x):
    """x as a pencilmark-puzzle dict: a document as it is, an engine Puzzle written out, anything else read"""
    from .exchange import FORMAT
    from .read import auto

    if hasattr(x, "coords"):
        from .export import export_puzzle

        return export_puzzle(x, solution=getattr(x, "_pm_solution", None))
    return x if isinstance(x, dict) and x.get("format") == FORMAT else auto(x)


def _rebuilt(x):
    """the document of x as the engine writes it back (the fingerprint's input: every spelling of a puzzle the same)"""
    from .api import _load
    from .export import export_puzzle, read_meta

    src = _source(x)
    return export_puzzle(_load(src), meta=read_meta(src))


def pencilmark(
    x: str | dict | Path, *, solution: bool = False, describe: bool = False, style: bool = True, pretty: bool = True
) -> str:
    """pencilmark JSON text of x: canonical key order, one line per rule (pretty) or one line."""
    from .exchange import dumps

    return dumps(document(x, solution=solution, describe=describe, style=style), pretty=pretty)


def plain(x: str | dict | Path) -> str:
    """One string of D x D characters, '.' for an empty cell (classic sudoku with standard boxes only)."""
    from .api import _load
    from .interop import to_string

    return to_string(_load(x), "plain")


def grid(x: str | dict | Path) -> str:
    """Rows on lines, boxes separated by | and -+- lines (classic sudoku with standard boxes only)."""
    from .api import _load
    from .interop import to_string

    return to_string(_load(x), "grid")


def sudokuwiki(x: str | dict | Path) -> str:
    """A sudokuwiki.org packed string (classic, jigsaw, X, windoku, killer and the other forms sudokuwiki has)."""
    from .api import _load
    from .interop import to_string

    return to_string(_load(x), "sudokuwiki")


def ipuz(x: str | dict | Path) -> dict:
    """An ipuz 2 dict (classic, Latin square, diagonal, windoku, jigsaw and killer sudoku)."""
    from .interop import to_ipuz

    return to_ipuz(x)
