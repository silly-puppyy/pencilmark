"""Public Python API. Same inputs and outputs as the command line (`python -m pencilmark rate --json`).

    import pencilmark
    card  = pencilmark.rate("....4.8.3.6...8..2...")            # classic string, puzzle JSON dict / str, sudoku-puzzle dict,
    card  = pencilmark.rate(puzzle, steps=True)                 #   a sample-pack line {"puzzle": ...}, or a path to a .json file
    cards = pencilmark.rate_many(puzzles, jobs=4)               # parallel, input order kept
    sol   = pencilmark.solve(puzzle)                            # list of digits; raises NotUnique / NoSolution
    exp   = pencilmark.to_export(puzzle, title=..., author=..., date=...)  # -> "sudoku-puzzle" dict, metadata under "meta"

`rate` returns the "sudoku-grade" card: difficulty, time (minutes), time_p80, band, band_index, contains, notes (+ steps with
steps=True, + "se": {er, ep, ed, scale} with se=True / se="diuf").
mode="human" (default) is the human route; mode="computer" also allows forcing chains / trial.
"""
from __future__ import annotations

import json
from pathlib import Path

__all__ = ["rate", "rate_many", "solve", "to_export", "load", "NotUnique", "NoSolution", "Undecided"]


class NotUnique(ValueError):
    """the puzzle has more than one solution"""


class NoSolution(ValueError):
    """the puzzle has no solution"""


_PARAMS = None


def _params(mode):
    global _PARAMS
    if _PARAMS is None:
        from .__main__ import _params as load_params
        _PARAMS = load_params()
    return dict(_PARAMS, search="computer" if mode == "computer" else "human")


def load(puzzle):
    """any accepted input -> a finalized engine Puzzle."""
    from . import puzzle_json as PJ
    from .__main__ import _to_puzzle_json
    if isinstance(puzzle, Path) or (isinstance(puzzle, str) and puzzle.endswith(".json") and Path(puzzle).exists()):
        obj = json.loads(Path(puzzle).read_text(encoding="utf-8"))
    elif isinstance(puzzle, str) and puzzle.lstrip().startswith("{"):
        obj = json.loads(puzzle)
    elif isinstance(puzzle, str):
        obj = {"numbers": puzzle.split()[0]}
    elif isinstance(puzzle, dict):
        obj = puzzle
    elif hasattr(puzzle, "groups") and hasattr(puzzle, "coords"):    # already an engine Puzzle
        if not hasattr(puzzle, "groups_of"):
            puzzle.finalize()
        return puzzle
    else:
        raise TypeError(f"unsupported puzzle input: {type(puzzle).__name__}")
    p = PJ.from_json(_to_puzzle_json(obj))
    p.finalize()
    return p


def rate(puzzle, steps=False, max_seconds=None, mode="human", se=False):
    """the "sudoku-grade" card of one puzzle (a dict). steps=True adds the step-by-step solve; se=True (or se="diuf") adds
    Sudoku Explainer-style ER / EP / ED from our route (pencilmark/se.py; meaningful for classic sudoku)."""
    from .export import grade
    p = load(puzzle)
    P = _params(mode)
    card = grade(p, P, with_steps=steps, max_seconds=max_seconds)
    if se:
        from . import band_path as BP, se as SE
        bp = BP.band_path(load(puzzle), P)
        card["se"] = SE.ratings(bp["steps"], scale=se if isinstance(se, str) else "classic") if bp["solved"] else None
    return card


def _mp_context():
    """fork where the platform has it (fast start, shared loaded engine), else spawn (Windows, and macOS-safe)."""
    import multiprocessing as mp
    return mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")


def _rate_job(args):
    puzzle, steps, max_seconds, mode, se = args
    try:
        return rate(puzzle, steps=steps, max_seconds=max_seconds, mode=mode, se=se)
    except Exception as e:                       # one bad puzzle must not sink the batch
        return {"error": f"{type(e).__name__}: {e}"}


def rate_many(puzzles, jobs=1, steps=False, max_seconds=None, mode="human", se=False):
    """cards for many puzzles, in input order; jobs > 1 uses worker processes. A failing puzzle gives {"error": ...}."""
    items = [(p, steps, max_seconds, mode, se) for p in puzzles]
    if jobs <= 1:
        return [_rate_job(it) for it in items]
    with _mp_context().Pool(jobs) as pool:
        return pool.map(_rate_job, items, chunksize=1)


class Undecided(RuntimeError):
    """the exhaustive search hit its node limit and OR-Tools (pip install "pencilmark[verify]") is not available"""


def solve(puzzle):
    """the unique solution as a list of digits (cell order of the puzzle); NotUnique / NoSolution otherwise.
    Uses the engine's exhaustive C++ search; CP-SAT (optional OR-Tools) only if that search hits its node limit."""
    from . import cpsat_verify as V
    sols, decided = V.decide(load(puzzle), limit=2)
    if len(sols) > 1:
        raise NotUnique("more than one solution")
    if not decided:
        raise Undecided("search limit reached without a verdict; install OR-Tools (pip install \"pencilmark[verify]\") "
                        "for the CP-SAT fallback")
    if not sols:
        raise NoSolution("no solution")
    return list(sols[0])


def to_export(puzzle, meta=None, with_solution=True, **meta_kw):
    """the "sudoku-puzzle" exchange dict (flat cell indices). Metadata goes in its own optional "meta" object: pass a dict
    (meta={"title": ..., "author": ..., "date": ...}) and / or keywords (title=..., author=..., source=..., id=..., url=...,
    date=..., rules_text=...); metadata already in a JSON input is kept."""
    from .export import export_puzzle, read_meta
    p = load(puzzle)
    sol = None
    if with_solution:
        try:
            sol = solve(p)
        except ValueError:
            sol = None
    m = {}
    if isinstance(puzzle, dict):
        m.update(read_meta(puzzle))
    m.update(meta or {})
    m.update({k: v for k, v in meta_kw.items() if v not in (None, "")})
    return export_puzzle(p, meta=m, solution=sol)
