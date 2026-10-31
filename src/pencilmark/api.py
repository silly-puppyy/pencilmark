"""Public Python API. Same inputs and outputs as the command line (`python -m pencilmark rate --json`).

    import pencilmark
    card  = pencilmark.rate("....4.8.3.6...8..2...")            # classic string, puzzle JSON dict / str, sudoku-puzzle dict,
    card  = pencilmark.rate(puzzle, steps=True)                 #   a sample-pack line {"puzzle": ...}, or a path to a .json file
    cards = pencilmark.rate_many(puzzles, jobs=4)               # parallel, input order kept
    sol   = pencilmark.solve(puzzle)                            # list of digits; raises NotUnique / NoSolution
    exp   = pencilmark.to_export(puzzle, title=..., author=..., date=...)  # -> "sudoku-puzzle" dict (docs/FORMAT.md)
    text  = pencilmark.dumps(exp); pencilmark.fingerprint(puzzle); pencilmark.describe(puzzle)
    pencilmark.to_ipuz(puzzle); pencilmark.from_string("S9B..."); pencilmark.to_string(puzzle, "sudokuwiki")  # -> "sudoku-puzzle" dict, metadata under "meta"

`rate` returns the "sudoku-grade" card: difficulty, time (minutes), band, contains (+ issues / reject,
time_pNN, ... with fields=[...], + steps with steps=True, + "se": {er, ep, ed, scale} with se=True).
mode="human" (default) is the human route; mode="computer" also allows forcing chains / trial.
Guessing is off by default: where no technique applies, the engine refutes a candidate by full search (Trial and error,
band Extreme), so every unique puzzle gets a band. allow_guessing=True lets it guess there instead (faster); the card
then says band "Unknown".
"""

from __future__ import annotations

__all__ = [
    "rate",
    "rate_many",
    "solve",
    "count_solutions",
    "to_export",
    "load",
    "NotUnique",
    "NoSolution",
    "Undecided",
    "dumps",
    "fingerprint",
    "validate",
    "describe",
    "rules_text",
    "to_ipuz",
    "from_ipuz",
    "from_string",
    "to_string",
    "generate",
    "GenerationFailed",
    "FormatError",
    "NotSupportedError",
]

from .exchange import FormatError, NotSupportedError  # noqa: E402


class NotUnique(ValueError):
    """the puzzle has more than one solution"""


class NoSolution(ValueError):
    """the puzzle has no solution"""


class GenerationFailed(RuntimeError):
    """no puzzle met the spec within the time limit (or the spec is infeasible); str(e) says why."""

    def __init__(self, reason, stats=None):
        super().__init__(reason)
        self.reason, self.stats = reason, stats or {}


_PARAMS = (None, None)  # (grader model, its engine params)


def _params(mode):
    global _PARAMS
    from . import grader_model as GM

    if mode not in ("human", "computer"):
        raise ValueError(f"unknown mode {mode!r}; known: 'human', 'computer'")

    if _PARAMS[0] is not GM.default():  # the shipped model, or the one grader_model.use() put in place
        from .__main__ import _params as load_params

        _PARAMS = (GM.default(), load_params())
    return dict(_PARAMS[1], search="computer" if mode == "computer" else "human")


def load(puzzle):
    """Any accepted input -> a finalized engine Puzzle.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        A classic string (81 characters, with or without a trailing comment), a text or pencil-mark grid, a sudokuwiki
        packed string, a sudoku-puzzle dict or JSON text, an ipuz file, a .json path, a SudokuPad / f-puzzles / Penpa /
        Logic Masters link, or an engine Puzzle (returned as it is).

    Returns
    -------
    Puzzle
        The engine's puzzle.

    Raises
    ------
    FormatError
        A sudoku-puzzle document that breaks the format.
    TypeError
        An input of no known form.
    """
    from . import inputs
    from . import puzzle_json as PJ

    if hasattr(puzzle, "groups") and hasattr(puzzle, "coords"):  # already an engine Puzzle
        if not hasattr(puzzle, "groups_of"):
            puzzle.finalize()
        return puzzle
    obj = inputs.read(puzzle)
    p = PJ.from_json(inputs.to_puzzle_json(obj))
    p.finalize()
    src = obj.get("puzzle") if isinstance(obj.get("puzzle"), dict) else obj
    if src.get("format") == "sudoku-puzzle" and isinstance(src.get("rules"), list):
        p._pm_input_rules = src["rules"]  # written back and counted (issues) in the file's own order
    return p


def rate(
    puzzle,
    steps=False,
    max_seconds=None,
    mode="human",
    se=False,
    fields=None,
    allow_guessing=False,
    explain=None,
    quality=None,
    alternatives=True,
):
    """The "sudoku-grade" card of one puzzle (docs/GRADE.md), with only the fields you ask for.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts: an 81-character string, a sudoku-puzzle dict or JSON text, a .json file, an ipuz file, a
        SudokuPad / f-puzzles / Penpa / Logic Masters link.
    steps : bool
        Shorthand for the `steps` field with every explanation level.
    max_seconds : float, optional
        One wall-clock limit for the whole call. When it passes, the card says band "Unknown", difficulty and time are
        null and `completed` is false.
    mode : str
        "human" (default): human techniques only, a proof by full search where they stop; "computer": also forcing chains
        and nets, Nishio and trial.
    se : bool
        Shorthand for the `se` field (Sudoku Explainer-style ratings; classic sudoku only).
    fields : list of str, optional
        The top-level fields to return. Default: difficulty, time, band, contains. Optional: band_index, issues, reject,
        warning (publishing checks), time_mean, time_pNN (any percentile 1-99, e.g. time_p80), time_dist, elapsed (wall
        seconds of the call), se, steps, describe, symmetry. format, format_version and grader are always present.
    allow_guessing : bool
        Guess where no technique applies (band "Unknown") instead of proving by full search (Trial and error, Extreme).
    explain : str, list of str or bool, optional
        Explanation levels for the steps: "notation", "short", "teach", or True for all of them.
    quality : dict, optional
        Settings of the issue checks, e.g. {"trivial": {"limit": 0.5}, "trial": {"severity": "off"}} (docs/GRADE.md 4).
    alternatives : bool
        False skips the search for interchangeable techniques (each chip in contains lists one code). Band, difficulty
        and time are the same either way, and the card comes much faster.

    Returns
    -------
    dict
        The card. Its steps walk the shortest technique list's route when the card asks for contains (or issues, reject
        or warning), else the full first route (docs/GRADE.md 5).

    Raises
    ------
    NotUnique
        The puzzle has more than one solution.
    NoSolution
        The puzzle has no solution.
    Undecided
        The uniqueness search hit its limit without OR-Tools installed, or max_seconds passed first.
    """
    from . import cpsat_verify as V
    from .export import card_fields, grade
    from .publish_flags import quality_limits

    want = card_fields(fields, steps=steps, se=se)
    quality_limits(quality)
    p = load(puzzle)
    import time

    from . import cbackend as CB
    from . import export as EX

    t_call = time.perf_counter()
    timed = max_seconds is not None and hasattr(CB._C, "set_deadline")
    if timed:  # ONE wall-clock limit for the whole call: uniqueness proof, card, technique list
        CB._C.set_deadline(float(max_seconds))
        EX._OUTER_END[0] = time.time() + float(max_seconds)
    try:
        sols, decided = V.decide(
            p, limit=2, time_limit=60.0 if max_seconds is None else max(1.0, min(60.0, float(max_seconds)))
        )
        if len(sols) > 1:
            raise NotUnique("more than one solution")
        if not decided:
            if timed and CB._C.deadline_hit():
                raise Undecided(f"max_seconds ({max_seconds}) passed before uniqueness was proven")
            raise Undecided(
                'search limit reached without a verdict; install OR-Tools (pip install "pencilmark[verify]") '
                "for the CP-SAT fallback"
            )
        if not sols:
            raise NoSolution("no solution")
        p._pm_solution = list(sols[0])  # proven unique: later stages reuse it instead of searching again
        P = dict(_params(mode), allow_guess=bool(allow_guessing), quality=quality or {})
        g = grade(
            p,
            P,
            max_seconds=max_seconds,
            fields=sorted(want),
            with_steps=steps,
            explain=explain,
            alternatives=alternatives,
        )
        if "elapsed" in g:  # the whole call: uniqueness proof + card
            g["elapsed"] = round(time.perf_counter() - t_call, 3)
        return g
    finally:
        if timed:
            CB._C.set_deadline(0.0)
            EX._OUTER_END[0] = None


def _mp_context():
    """fork where the platform has it (fast start, shared loaded engine), else spawn (Windows, and macOS-safe)."""
    import multiprocessing as mp

    return mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")


def _rate_job(args):
    puzzle, steps, max_seconds, mode, se, fields, allow_guessing, explain, quality, alternatives = args
    try:
        return rate(
            puzzle,
            steps=steps,
            max_seconds=max_seconds,
            mode=mode,
            se=se,
            fields=fields,
            allow_guessing=allow_guessing,
            explain=explain,
            quality=quality,
            alternatives=alternatives,
        )
    except Exception as e:  # one bad puzzle must not sink the batch
        return {"error": f"{type(e).__name__}: {e}"}


def rate_many(
    puzzles,
    jobs=1,
    steps=False,
    max_seconds=None,
    mode="human",
    se=False,
    fields=None,
    allow_guessing=False,
    explain=None,
    quality=None,
    alternatives=True,
):
    """Cards for many puzzles, in input order.

    Parameters
    ----------
    puzzles : iterable
        Puzzles in any form `rate` accepts.
    jobs : int
        Worker processes; 1 rates in this process.
    steps, max_seconds, mode, se, fields, allow_guessing, explain, quality, alternatives
        As for `rate`.

    Returns
    -------
    list of dict
        One card per puzzle. A puzzle that cannot be rated (not unique, no solution, unreadable) gives
        {"error": "..."} instead of raising.
    """
    items = [(p, steps, max_seconds, mode, se, fields, allow_guessing, explain, quality, alternatives) for p in puzzles]
    if jobs <= 1:
        return [_rate_job(it) for it in items]
    with _mp_context().Pool(jobs) as pool:
        return pool.map(_rate_job, items, chunksize=1)


class Undecided(RuntimeError):
    """the exhaustive search hit its node limit and OR-Tools (pip install "pencilmark[verify]") is not available"""


def solve(puzzle, info=False):
    """The unique solution of a puzzle.

    Uses the engine's exhaustive C++ search; CP-SAT (OR-Tools, optional) only when that search hits its node limit.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts.
    info : bool
        Return {"solution": [...], "seconds": wall-clock seconds of the search} instead of the bare list.

    Returns
    -------
    list of int
        The digits in the puzzle's cell order.

    Raises
    ------
    NotUnique
        More than one solution.
    NoSolution
        No solution.
    Undecided
        The search hit its node limit and OR-Tools is not installed.
    """
    import time

    from . import cpsat_verify as V

    t0 = time.perf_counter()
    sols, decided = V.decide(load(puzzle), limit=2)
    if len(sols) > 1:
        raise NotUnique("more than one solution")
    if not decided:
        raise Undecided(
            'search limit reached without a verdict; install OR-Tools (pip install "pencilmark[verify]") '
            "for the CP-SAT fallback"
        )
    if not sols:
        raise NoSolution("no solution")
    if info:
        return {"solution": list(sols[0]), "seconds": round(time.perf_counter() - t0, 4)}
    return list(sols[0])


def count_solutions(puzzle, limit=1000):
    """How many solutions a puzzle has, counting up to a limit.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts.
    limit : int
        Stop counting here.

    Returns
    -------
    dict
        {"count": n, "exact": bool}. exact is false when there are at least n: the count reached `limit`, or the search
        hit its node limit without OR-Tools installed.
    """
    from . import cpsat_verify as V

    if limit < 1:
        raise ValueError("limit must be at least 1")
    sols, decided = V.decide(load(puzzle), limit=limit)
    return {"count": len(sols), "exact": decided and len(sols) < limit}


def to_export(puzzle, meta=None, with_solution=True, describe=True, **meta_kw):
    """The "sudoku-puzzle" exchange dict of a puzzle (format_version 1, docs/FORMAT.md).

    Canonical: houses and rules with "r1c1" cells, keys in a fixed order. Metadata already in a JSON input is kept.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts.
    meta : dict, optional
        Metadata for the "meta" object, e.g. {"title": ..., "author": ..., "date": ...}.
    with_solution : bool
        Include the solution.
    describe : bool
        Fill an empty meta.type / meta.rules_text from `describe`; never overwrites them.
    **meta_kw
        Metadata as keywords: title, author, source, id, url, date, rules_text.

    Returns
    -------
    dict
        The sudoku-puzzle document.
    """
    from . import inputs
    from .export import export_puzzle, read_meta

    if isinstance(puzzle, str):  # read once, keeping the title / source a link or JSON text carries
        puzzle = inputs.read(puzzle)
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
        from .variants import describe as _describe
        from .variants import rules_text as _rt

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


def dumps(doc, pretty=True):
    """Canonical JSON text of a sudoku-puzzle dict: fixed key order; pretty: one grid row per line, one rule per line.

    Parameters
    ----------
    doc : dict
        A sudoku-puzzle document.
    pretty : bool
        Readable layout (True) or one line (False).

    Returns
    -------
    str
        The text.
    """
    from .exchange import dumps as d

    return d(doc, pretty=pretty)


def fingerprint(puzzle):
    """Content fingerprint of a puzzle: "sha256:<hex>" of its canonical form.

    Covers the rules, grid, givens and candidates; not meta, style or the solution. Two files of the same puzzle get the
    same fingerprint.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts.

    Returns
    -------
    str
        "sha256:" followed by 64 hex digits.
    """
    from .exchange import fingerprint_of_doc

    return fingerprint_of_doc(to_export(puzzle, with_solution=False, describe=False))


def validate(doc):
    """Strict reading checks of a format_version 1 dict (docs/FORMAT.md section 4).

    Parameters
    ----------
    doc : dict
        A sudoku-puzzle document.

    Returns
    -------
    bool
        True.

    Raises
    ------
    FormatError
        The document breaks the format; the message names the rule and the problem.
    """
    from .exchange import validate as v

    v(doc)
    return True


def describe(puzzle):
    """The variant name and its rules in words, from the rules alone (pencilmark/variants.py).

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts.

    Returns
    -------
    dict
        {"type": variant name, "rules": {short name: one-sentence rule, ...}}.
    """
    from .variants import describe as d

    return d(puzzle)


def rules_text(described):
    from .variants import rules_text as r

    return r(described)


def to_ipuz(puzzle):
    """A puzzle as an ipuz 2 dict (docs/INTEROP.md).

    ipuz expresses classic, Latin square, diagonal, windoku, jigsaw and killer sudoku.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts.

    Returns
    -------
    dict
        The ipuz document.

    Raises
    ------
    NotSupportedError
        The puzzle uses rules ipuz cannot express.
    """
    from .interop import to_ipuz as t

    return t(puzzle)


def from_ipuz(ipuz):
    """An ipuz sudoku -> sudoku-puzzle dict (docs/INTEROP.md).

    Parameters
    ----------
    ipuz : dict or str
        The ipuz document, or its JSON text.

    Returns
    -------
    dict
        The sudoku-puzzle document.
    """
    from .interop import from_ipuz as f

    return f(ipuz)


def from_string(s, symbols=None):
    """A puzzle as text -> sudoku-puzzle dict (docs/INTEROP.md).

    Reads plain classic strings (with or without a trailing comment), text grids with separators, pencil-mark grids,
    729-character candidate strings, HoDoKu library lines and sudokuwiki.org packed strings.

    Parameters
    ----------
    s : str
        The text.
    symbols : str, optional
        For a plain string, the symbol of each digit in order (e.g. "ABCDEFGHI" reads A as 1); default 1-9, then A-Z.

    Returns
    -------
    dict
        The sudoku-puzzle document.
    """
    from .interop import from_string as f

    return f(s, symbols=symbols)


def to_string(puzzle, form="plain"):
    """A puzzle as text (docs/INTEROP.md).

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Anything `load` accepts.
    form : str
        "plain" (81 characters), "grid" (rows with separators) or "sudokuwiki" (packed string).

    Returns
    -------
    str
        The text.

    Raises
    ------
    NotSupportedError
        The form cannot carry the puzzle (e.g. a variant in "plain").
    """
    from .interop import to_string as t

    return t(puzzle, form)


def generate(spec):
    """One puzzle for a "sudoku-spec" request (docs/SPEC.md).

    Parameters
    ----------
    spec : dict, str or Path
        The request: a dict, JSON text or a path to a .json file.

    Returns
    -------
    dict
        {"puzzle": sudoku-puzzle dict, "card": its sudoku-grade card, "info": {...}}.

    Raises
    ------
    GenerationFailed
        No puzzle met the request in the time it allows.
    """
    from .gen.api import generate as g

    return g(spec)
