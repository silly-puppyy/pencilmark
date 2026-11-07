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


# the pair and cell rules the fingerprint replaces by what they allow (docs/formats/puzzle-format.md 8.2): every edge
# clue, relation, neighbors rule and cell clue, the negatives of those families, the lines made of pairs, and the
# corner clues that are pair or cell clues
PAIR_LINES = {"thermo", "slow_thermo", "whisper", "palindrome", "parity"}


def _by_meaning(r):
    """True when the fingerprint states rule r through the pair tables and cell sets rather than as written"""
    from .rules.edge import EDGE

    t = r["type"]
    if t == "neighbors":
        return r.get("within") != "region"  # regions to find (chaos) are not known when the pairs are listed
    if t in ("edge", "relation", "cell"):
        return True
    if t == "negative":
        return r.get("of") in EDGE or r.get("of") == "cell"
    if t == "line":
        return r.get("kind") in PAIR_LINES
    if t == "corner":
        return r.get("kind") == "exclude" or (r.get("kind") == "mathrax" and r.get("op") not in ("even", "odd"))
    return False


def _rebuilt(x):
    """the fingerprint's input (docs/formats/puzzle-format.md 8.2): the document of x as the engine writes it back,
    with the pair and cell rules replaced by what they allow: one {"type": "pair_table", "cells": [a, b], "allowed":
    [[digit a, digit b], ...]} per cell pair the rules restrict (every constraint on the pair together; digits of
    two cells in one house already differ) and one {"type": "cell_set", "cells": [c], "allowed": [...]} per cell
    whose digits they restrict"""
    from .api import _load
    from .export import export_puzzle, read_meta
    from .model import RELATIONS

    src = _source(x)
    p = _load(src)
    doc = export_puzzle(p, meta=read_meta(src))
    D, name = p.D, (lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}")
    full = {(v, w) for v in range(1, D + 1) for w in range(1, D + 1)}
    tables = {}

    def restrict(a, b, ok):
        if p.coords[a] > p.coords[b]:
            a, b, ok = b, a, {(w, v) for v, w in ok}
        tables[(a, b)] = tables.get((a, b), full) & ok

    ok_of = dict(RELATIONS, neq=lambda v, w: v != w)  # neq: the engine's plain "different" pair
    for kind, a, b, *args in p.relations:
        restrict(a, b, {(v, w) for v, w in full if ok_of[kind](v, w, *args)})
    for c in p.constraints:
        if c.get("type") == "table" and len(c["cells"]) == 2:
            restrict(*c["cells"], {tuple(x) for x in c["allowed"]})
    house = {frozenset((a, b)) for g in p.groups for a in g.cells for b in g.cells if a != b}
    same = {(v, v) for v in range(1, D + 1)}
    extra = []
    for (a, b), ok in sorted(tables.items(), key=lambda x: (p.coords[x[0][0]], p.coords[x[0][1]])):
        free = full - same if frozenset((a, b)) in house else full
        if ok & free != free:
            extra.append({"type": "pair_table", "cells": [name(a), name(b)], "allowed": sorted(map(list, ok & free))})
    for i, dom in enumerate(p.domains):
        allowed = [v for v in range(1, D + 1) if dom >> (v - 1) & 1]
        if len(allowed) < D:
            extra.append({"type": "cell_set", "cells": [name(i)], "allowed": allowed})
    return dict(doc, rules=[r for r in doc["rules"] if not _by_meaning(r)]), extra


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
