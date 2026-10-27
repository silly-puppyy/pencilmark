"""Public Python API. Same inputs and outputs as the command line (`python -m pencilmark rate --json`).

    import pencilmark
    card  = pencilmark.rate("....4.8.3.6...8..2...")            # classic string, puzzle JSON dict / str, sudoku-puzzle dict,
    card  = pencilmark.rate(puzzle, steps=True)                 #   a sample-pack line {"puzzle": ...}, or a path to a .json file
    cards = pencilmark.rate_many(puzzles, jobs=4)               # parallel, input order kept
    sol   = pencilmark.solve(puzzle)                            # list of digits; raises NotUnique / NoSolution
    exp   = pencilmark.to_export(puzzle, title=..., author=..., date=...)  # -> "sudoku-puzzle" dict (docs/FORMAT.md)
    text  = pencilmark.dumps(exp); pencilmark.fingerprint(puzzle); pencilmark.describe(puzzle)
    pencilmark.to_ipuz(puzzle); pencilmark.from_string("S9B..."); pencilmark.to_string(puzzle, "sudokuwiki")  # -> "sudoku-puzzle" dict, metadata under "meta"

`rate` returns the "sudoku-grade" card: difficulty, time (minutes), band, band_index, contains (+ issues / reject,
time_pNN, ... with fields=[...], + steps with steps=True, + "se": {er, ep, ed, scale} with se=True / se="diuf").
mode="human" (default) is the human route; mode="computer" also allows forcing chains / trial.
Guessing is off by default: where no technique applies, the engine refutes a candidate by full search (Trial and error,
band Extreme), so every unique puzzle gets a band. allow_guessing=True lets it guess there instead (faster); the card
then says band "Unknown".
"""
from __future__ import annotations

import json
from pathlib import Path

__all__ = ["rate", "rate_many", "solve", "to_export", "load", "NotUnique", "NoSolution", "Undecided", "dumps", "fingerprint",
           "validate", "describe", "rules_text", "to_ipuz", "from_string", "to_string", "spec_from_gen", "spec_to_gen",
           "FormatError", "NotSupportedError"]

from .exchange import FormatError, NotSupportedError  # noqa: E402


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
        from .interop import _PACKED
        tok = puzzle.split()[0]
        obj = _from_string_doc(tok) if _PACKED.fullmatch(tok) else {"numbers": tok}
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


def rate(puzzle, steps=False, max_seconds=None, mode="human", se=False, fields=None, allow_guessing=False, explain=None,
         quality=None, alternatives=True):
    """the "sudoku-grade" card of one puzzle (docs/GRADE.md) with the requested top-level fields only. Default fields:
    difficulty, time, band, band_index, contains (format, format_version, grader always). Optional: issues, reject
    (publishing checks), time_mean / time_pNN (any percentile 1-99, e.g. time_p80), se, se_diuf, steps, describe, symmetry. explain="short" /
    "teach" / True (both) adds explanations to the steps. steps=True is shorthand for the steps field with both explanation
    levels; se=True / se="diuf" for se / se_diuf.
    Raises NotUnique / NoSolution / Undecided for a puzzle without exactly one solution. allow_guessing=True: guess
    where no technique applies (band "Unknown") instead of proving by full search (Trial and error, Extreme).
    quality: the issue checks' limits, e.g. {"trivial": 0.5, "trial": False} (docs/GRADE.md 4). alternatives=False skips
    the search for interchangeable techniques (each chip in contains lists one code); band, difficulty and time are the
    same either way, and the card comes much faster."""
    from .export import grade, card_fields
    from .publish_flags import quality_limits
    from . import cpsat_verify as V
    want = card_fields(fields, steps=steps, se=se)
    quality_limits(quality)
    p = load(puzzle)
    sols, decided = V.decide(p, limit=2)
    if len(sols) > 1:
        raise NotUnique("more than one solution")
    if not decided:
        raise Undecided("search limit reached without a verdict; install OR-Tools (pip install \"pencilmark[verify]\") "
                        "for the CP-SAT fallback")
    if not sols:
        raise NoSolution("no solution")
    p._pm_solution = list(sols[0])      # proven unique: later stages reuse it instead of searching again
    P = dict(_params(mode), allow_guess=bool(allow_guessing), quality=quality or {})
    return grade(p, P, max_seconds=max_seconds, fields=sorted(want), with_steps=steps, explain=explain,
                 alternatives=alternatives)


def _mp_context():
    """fork where the platform has it (fast start, shared loaded engine), else spawn (Windows, and macOS-safe)."""
    import multiprocessing as mp
    return mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")


def _rate_job(args):
    puzzle, steps, max_seconds, mode, se, fields, allow_guessing, explain, quality = args
    try:
        return rate(puzzle, steps=steps, max_seconds=max_seconds, mode=mode, se=se, fields=fields,
                    allow_guessing=allow_guessing, explain=explain, quality=quality)
    except Exception as e:                       # one bad puzzle must not sink the batch
        return {"error": f"{type(e).__name__}: {e}"}


def rate_many(puzzles, jobs=1, steps=False, max_seconds=None, mode="human", se=False, fields=None, allow_guessing=False,
              explain=None, quality=None):
    """cards for many puzzles, in input order; jobs > 1 uses worker processes. A puzzle that cannot be rated (not unique,
    no solution, unreadable) gives {"error": "..."}."""
    items = [(p, steps, max_seconds, mode, se, fields, allow_guessing, explain, quality) for p in puzzles]
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


def to_export(puzzle, meta=None, with_solution=True, describe=True, **meta_kw):
    """the "sudoku-puzzle" exchange dict (format_version 1, docs/FORMAT.md): canonical, houses and rules with "r1c1" cells.
    Metadata goes in its own optional "meta" object: pass a dict (meta={"title": ..., "author": ..., "date": ...}) and / or
    keywords (title=..., author=..., source=..., id=..., url=..., date=..., rules_text=...); metadata already in a JSON input is
    kept. describe=True fills an EMPTY meta.type / meta.rules_text from describe(); it never overwrites them."""
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
        m.update(read_meta(puzzle.get("puzzle") if isinstance(puzzle.get("puzzle"), dict) else puzzle))
    m.update(meta or {})
    m.update({k: v for k, v in meta_kw.items() if v not in (None, "")})
    doc = export_puzzle(p, meta=m, solution=sol)
    if describe and not (m.get("type") and m.get("rules_text")):
        from .variants import describe as _describe, rules_text as _rt
        dsc = _describe(doc)
        meta2 = dict(doc.get("meta") or {})
        meta2.setdefault("type", dsc["type"])
        meta2.setdefault("rules_text", _rt(dsc))
        from .export import read_meta as _rm
        doc = dict(doc)
        doc["meta"] = _rm({"meta": meta2})
        from .exchange import canonical
        doc = canonical(doc)
    return doc


def _from_string_doc(s):
    from .interop import from_string as fs
    return fs(s)


def dumps(doc, pretty=True):
    """canonical JSON text of a sudoku-puzzle dict (fixed key order; pretty: one grid row per line, one rule per line)"""
    from .exchange import dumps as d
    return d(doc, pretty=pretty)


def fingerprint(puzzle):
    """content fingerprint "sha256:<hex>" of the canonical form (rules, grid, givens, candidates; no meta / style / solution)"""
    from .exchange import fingerprint_of_doc
    return fingerprint_of_doc(to_export(puzzle, with_solution=False, describe=False))


def validate(doc):
    """strict reading checks of a format_version 1 dict (docs/FORMAT.md section 4); raises FormatError"""
    from .exchange import validate as v
    v(doc)
    return True


def describe(puzzle):
    """{"type": variant name, "rules": {short name: one-sentence rule, ...}} from the rules alone (pencilmark/variants.py)"""
    from .variants import describe as d
    return d(puzzle)


def rules_text(described):
    from .variants import rules_text as r
    return r(described)


def to_ipuz(puzzle):
    from .interop import to_ipuz as t
    return t(puzzle)


def from_string(s, symbols=None):
    from .interop import from_string as f
    return f(s, symbols=symbols)


def to_string(puzzle, form="plain"):
    from .interop import to_string as t
    return t(puzzle, form)


def spec_from_gen(spec):
    from .spec_format import spec_from_gen as f
    return f(spec)


def spec_to_gen(doc):
    from .spec_format import spec_to_gen as f
    return f(doc)
