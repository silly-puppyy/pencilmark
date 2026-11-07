"""Public Python API. Same inputs and outputs as the command line (`python -m pencilmark rate --json`).

    import pencilmark
    card  = pencilmark.rate("....4.8.3.6...8..2...")            # any format pencilmark reads (pencilmark.read), detected
    card  = pencilmark.rate(text, format="sudokuwiki")           #   or named
    cards = pencilmark.rate_many(puzzles, jobs=4)               # parallel, input order kept
    sol   = pencilmark.solve(puzzle)                            # list of digits; raises NotUnique / NoSolution
    doc   = pencilmark.read.plain("....4.8.3.6...8..2...")      # -> pencilmark-puzzle dict (docs/formats/puzzle-format.md)
    text  = pencilmark.write.pencilmark(doc, solution=True)     # pencilmark JSON; write.sudokuwiki / plain / grid / ipuz

`rate` returns the "pencilmark-grade" card: difficulty, time (minutes), band, contains (+ issues / reject,
time_pNN, steps, "se": {er, ep, ed, scale}, ... with fields=[...]; explain= for the steps' explanations).
mode="human" (default) is the human route; mode="computer" also allows forcing chains / trial.
Guessing is off by default: where no technique applies, the engine refutes a candidate by full search (Trial and error,
band Extreme), so every unique puzzle gets a band. allow_guessing=True lets it guess there instead (faster); the card
then says band "Unknown".
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "rate",
    "rate_many",
    "solve",
    "count_solutions",
    "describe",
    "fingerprint",
    "validate",
    "generate",
    "Error",
    "FormatError",
    "NotSupportedError",
    "FetchError",
    "ReadingMismatch",
    "NotUnique",
    "NoSolution",
    "Undecided",
    "GenerationFailed",
]

from .errors import (  # noqa: E402
    Error,
    FetchError,
    FormatError,
    GenerationFailed,
    NoSolution,
    NotSupportedError,
    NotUnique,
    ReadingMismatch,
    Undecided,
)

_PARAMS = (None, None)  # ((grader model, its settings), its engine params)


def _model_key(m):
    """the model and its current settings: an in-place change to its route / price params (an experiment's arm) is a
    new key, so the engine params are rebuilt instead of reused from the previous arm"""
    return (
        m,
        repr(sorted((getattr(m, "route", None) or {}).items())),
        repr(sorted((getattr(m, "price", None) or {}).items())),
    )


def _params(mode):
    global _PARAMS
    from . import grader_model as GM

    if mode not in ("human", "computer"):
        raise ValueError(f"unknown mode {mode!r}; known: 'human', 'computer'")

    key = _model_key(GM.default())
    if _PARAMS[0] is None or _PARAMS[0][0] is not key[0] or _PARAMS[0][1:] != key[1:]:  # the shipped model, the one
        _PARAMS = (key, GM.engine_params())  # grader_model.use() put in place, or changed settings
    return dict(_PARAMS[1], search="computer" if mode == "computer" else "human")


def _load(puzzle, format=None):  # noqa: A002
    """any input pencilmark.read reads (detected, or named by format), or an engine Puzzle -> a finalized engine
    Puzzle; the input's rules are kept in the file's order (written back and counted in that order)"""
    from . import puzzle_json as PJ
    from .export import import_puzzle
    from .read import auto

    if hasattr(puzzle, "groups") and hasattr(puzzle, "coords"):  # already an engine Puzzle
        if not hasattr(puzzle, "groups_of"):
            puzzle.finalize()
        return puzzle
    if (
        isinstance(puzzle, dict)
        and format is None
        and "format" not in puzzle
        and ("numbers" in puzzle or "layout" in puzzle)
    ):
        # the engine's own JSON (internal callers; not a public format: rate reads through pencilmark.read first)
        p = PJ.from_json(puzzle)
        p.finalize()
        return p
    doc = auto(puzzle, format=format)
    p = PJ.from_json(import_puzzle(doc))
    p.finalize()
    if isinstance(doc.get("rules"), list):
        from .exchange.common import with_definitions

        p._pm_input_rules = with_definitions(doc)["rules"]  # named custom rules expanded, one per input rule
    return p


def known_techniques(codes):
    """engine technique ids a solver knowing these technique codes uses: every technique of a listed code or found by a
    listed pattern code, and the singles (always known). Raises ValueError for an unknown code."""
    from . import registry as R
    from .export import SINGLE_CODES

    codes = set(codes)
    bad = sorted(codes - set(R.codes()))
    if bad:
        raise ValueError(f"unknown technique code(s) {bad} (docs/grades/techniques.md lists them)")
    from .export import chip_of

    by_name = R.by_name()
    known = codes | SINGLE_CODES  # as the card lists them: a technique counts under its chip (a single helped by a
    out = {t.id for t in R.techniques() if t.family == "singles" or chip_of(t.id)[0] in known}  # pointing is a single)
    return out | {by_name[p.technique].id for p in R.patterns() if p.code in codes and p.technique in by_name}


def _rate_known(puzzle, techniques, kw):
    """rate(techniques=...): the grader model with every other technique switched off (route and prices alike) and no
    fallback to trial and error, so a puzzle needing more stops: band Unknown, with that reason"""
    import copy

    from . import grader_model as GM
    from . import registry as R
    from . import solver as S

    off = {t.id for t in R.techniques()} - known_techniques(techniques) - set(S.NOTE_TECHS)
    m = copy.deepcopy(GM.default())
    for part in (m.route, m.price):
        part["disabled_techniques"] = sorted(set(part.get("disabled_techniques") or ()) | off | {S.TRIAL})
    global _PARAMS
    with GM.use(m):
        _PARAMS = (None, None)  # the cached engine params belong to the shipped model
        try:
            card = rate(puzzle, allow_guessing=True, **kw)
        finally:
            _PARAMS = (None, None)
    if card.get("band") == "Unknown" and card.get("completed") is not False:
        card["reason"] = "needs a technique outside the techniques given"
        card.update({k: None for k in ("difficulty", "time", "band_index") if k in card})  # as every Unknown card
    return card


def rate(
    puzzle: str | dict | Path,
    *,
    max_seconds: float | None = None,
    mode: str = "human",
    fields: list[str] | None = None,
    allow_guessing: bool = False,
    explain: bool | str | list[str] | None = None,
    quality: dict | None = None,
    alternatives: bool = True,
    coloring: bool = False,
    techniques: list[str] | None = None,
    format: str | None = None,  # noqa: A002
) -> dict:
    """The "pencilmark-grade" card of one puzzle (docs/formats/grade-card.md), with only the fields you ask for.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Any format pencilmark.read reads, detected (an 81-character string, a text grid, a sudokuwiki string, pencilmark
        JSON as a dict, text or .json path, an ipuz file, a SudokuPad / f-puzzles / Penpa / Logic Masters link).
    max_seconds : float, optional
        One wall-clock limit for the whole call. When it passes, the card says band "Unknown", difficulty and time are
        null and `completed` is false.
    mode : str
        "human" (default): human techniques only, a proof by full search where they stop; "computer": also forcing chains
        and nets, Nishio and trial.
    fields : list of str, optional
        The top-level fields to return. Default: difficulty, time, band, contains. Optional: band_index, issues, reject,
        warning (publishing checks), time_mean, time_pNN (any percentile 1-99, e.g. time_p80), time_dist, elapsed (wall
        seconds of the call), se (Sudoku Explainer-style ratings; classic sudoku only), steps (with `explain` for
        their explanations), trace (the board before and after each step), describe, symmetry. format,
        format_version and grader are always present.
    allow_guessing : bool
        Guess where no technique applies (band "Unknown") instead of proving by full search (Trial and error, Extreme).
    explain : str, list of str or bool, optional
        Explanation levels for the steps: "notation", "short", "teach", or True for all three; "substeps" (only by
        name) tells each step as sub-steps with reasons and drawing annotations (docs/formats/grade-card.md 5).
    quality : dict, optional
        Which issue checks run and how (docs/formats/grade-card.md 4): None = every check that is not opt in, at its own
        severity (the "default" preset); {} = none; {"preset": "standard"}; without a preset only the checks named run,
        e.g. {"trivial": {"limit": 0.5}, "trial": {"severity": "reject"}}.
    alternatives : bool
        False skips the search for interchangeable techniques (each chip in contains lists one code). Band, difficulty
        and time are the same either way, and the card comes much faster.
    coloring : bool
        Opt in to coloring as a solving method: colors kept through the solve (Color Fill, Color Single, Color
        Pair, ...; docs/grades/techniques.md, Coloring). Off by default: most solvers do not color, and with it
        the hardest puzzles take much longer to grade.
    techniques : list of str, optional
        Grade for a solver who knows only these techniques: a whitelist of technique codes (docs/grades/techniques.md),
        singles always included. A puzzle that needs more gets band "Unknown" with the reason. A code found by a wider
        engine search (Skyscraper by the X-Chain search) allows that search.

    format : str, optional
        The input's format (a pencilmark.read reader: "plain", "sudokuwiki", "pencilmark", "link", ...) instead of
        detecting it.

    Returns
    -------
    dict
        The card. Its steps walk the shortest technique list's route when the card asks for contains (or issues, reject
        or warning), else the full first route (docs/formats/grade-card.md 5).

    Raises
    ------
    NotUnique
        The puzzle has more than one solution.
    NoSolution
        The puzzle has no solution.

    A puzzle whose uniqueness the engine cannot settle (max_seconds passed first, or the search hit its limit without
    OR-Tools) is not an error: its card has band "Unknown" and a `reason`.
    """
    from . import cpsat_verify as V
    from .export import card_fields, grade
    from .publish_flags import quality_limits

    if techniques is not None:  # the same grading with a model that knows only these techniques
        return _rate_known(puzzle, techniques, dict(max_seconds=max_seconds, mode=mode, fields=fields, explain=explain,
                           quality=quality, alternatives=alternatives, coloring=coloring, format=format))  # fmt: skip
    want = card_fields(fields)
    quality_limits(quality)
    if not hasattr(puzzle, "coords"):  # read once: the fog view reads the document too
        from .read import auto

        puzzle = auto(puzzle, format=format)
    p = _load(puzzle)
    # rules no human technique reasons with yet: the puzzle is still proven unique (or refused as a wrong input), then
    # its card is band Unknown with the reason (user 2026-11-06: "Unknown if unknown, error if a reader mistake")
    no_route = (
        "shading (yin-yang): no human technique for shading yet"
        if V.has_shading(p)
        else "unknowns / layers (custom rules): no human technique for them yet"
        if getattr(p, "aux", None)
        else None
    )
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
        if not decided:  # the engine cannot tell whether the puzzle is unique: Unknown, not an error
            hit = timed and CB._C.deadline_hit()
            g = EX.unknown_card(
                want,
                f"max_seconds ({max_seconds}) passed before uniqueness was proven"
                if hit
                else 'uniqueness search limit reached; OR-Tools (pip install "pencilmark[verify]") settles most',
            )
            if max_seconds is not None:
                g["completed"] = False
            return g
        if not sols:
            raise NoSolution("no solution")
        p._pm_solution = list(sols[0])  # proven unique: later stages reuse it instead of searching again
        P = dict(_params(mode), allow_guess=bool(allow_guessing), quality=quality, colouring=int(bool(coloring)))
        if no_route:
            g = EX.unknown_card(want, no_route)
            if "elapsed" in want:
                g["elapsed"] = round(time.perf_counter() - t_call, 3)
            return g
        if getattr(p, "fog", None):  # a fog rule is part of the puzzle: graded under the fog (export.grade_fog)
            g = EX.grade_fog(p, puzzle, P, fields=sorted(want))
            if max_seconds is not None:  # the fog route stops at the engine deadline: Unknown, not completed
                g["completed"] = not (timed and CB._C.deadline_hit())
                if not g["completed"]:
                    g.update(
                        {k: None for k in ("difficulty", "time") if k in g},
                        **({"band": "Unknown"} if "band" in g else {}),
                    )
            if "elapsed" in want:
                g["elapsed"] = round(time.perf_counter() - t_call, 3)
            return g
        g = grade(
            p,
            P,
            max_seconds=max_seconds,
            fields=sorted(want),
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


def _one_route_thread():
    """worker processes of rate_many: the card's sampled routes run one after another (the processes fill the cores)"""
    from . import card_score

    card_score.ROUTE_THREADS = 1


def _rate_job(args):
    puzzle, max_seconds, mode, fields, allow_guessing, explain, quality, alternatives, coloring, techniques = args
    try:
        return rate(
            puzzle,
            max_seconds=max_seconds,
            mode=mode,
            fields=fields,
            allow_guessing=allow_guessing,
            explain=explain,
            quality=quality,
            alternatives=alternatives,
            coloring=coloring,
            techniques=techniques,
        )
    except Exception as e:  # one bad puzzle must not sink the batch
        return {"error": f"{type(e).__name__}: {e}"}


def rate_many(
    puzzles: list,
    *,
    jobs: int = 1,
    max_seconds: float | None = None,
    mode: str = "human",
    fields: list[str] | None = None,
    allow_guessing: bool = False,
    explain: bool | str | list[str] | None = None,
    quality: dict | None = None,
    alternatives: bool = True,
    coloring: bool = False,
    techniques: list[str] | None = None,
) -> list[dict]:
    """Cards for many puzzles, in input order.

    Parameters
    ----------
    puzzles : iterable
        Puzzles in any form `rate` accepts.
    jobs : int
        Worker processes; 1 rates in this process.
    max_seconds, mode, fields, allow_guessing, explain, quality, alternatives, coloring, techniques
        As for `rate`.

    Returns
    -------
    list of dict
        One card per puzzle. A puzzle that cannot be rated (not unique, no solution, unreadable) gives
        {"error": "..."} instead of raising.
    """
    items = [
        (p, max_seconds, mode, fields, allow_guessing, explain, quality, alternatives, coloring, techniques)
        for p in puzzles
    ]
    if jobs <= 1:
        return [_rate_job(it) for it in items]
    with _mp_context().Pool(jobs, initializer=_one_route_thread) as pool:
        return pool.map(_rate_job, items, chunksize=1)


def solve(puzzle: str | dict | Path, *, format: str | None = None) -> list[int]:  # noqa: A002
    """The unique solution of a puzzle.

    Uses the engine's exhaustive C++ search; CP-SAT (OR-Tools, optional) only when that search hits its node or time limit.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Any format pencilmark.read reads (detected), or its document.
    format : str, optional
        The input's format instead of detecting it.

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
        The search hit its node or time limit and OR-Tools is not installed.
    """
    from . import cpsat_verify as V

    sols, decided = V.decide(_load(puzzle, format=format), limit=2)
    if len(sols) > 1:
        raise NotUnique("more than one solution")
    if not decided:
        raise Undecided(
            'search limit reached without a verdict; install OR-Tools (pip install "pencilmark[verify]") '
            "for the CP-SAT fallback"
        )
    if not sols:
        raise NoSolution("no solution")
    return list(sols[0])


def count_solutions(puzzle: str | dict | Path, *, limit: int = 1000, format: str | None = None) -> dict:  # noqa: A002
    """How many solutions a puzzle has, counting up to a limit.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Any format pencilmark.read reads (detected), or its document.
    limit : int
        Stop counting here.

    Returns
    -------
    dict
        {"count": n, "exact": bool}. exact is false when there are at least n: the count reached `limit`, or the search
        hit its node or time limit without OR-Tools installed.
    """
    from . import cpsat_verify as V

    if limit < 1:
        raise ValueError("limit must be at least 1")
    sols, decided = V.decide(_load(puzzle, format=format), limit=limit)
    return {"count": len(sols), "exact": decided and len(sols) < limit}


def fingerprint(puzzle: str | dict | Path) -> str:
    """Content fingerprint of a puzzle: the SHA-256 of its canonical form, 64 hex digits.

    Covers the rules, grid, givens and candidates; not meta, style or the solution. Two files of the same puzzle get the
    same fingerprint.

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Any format pencilmark.read reads (detected), or its document.

    Returns
    -------
    str
        64 lowercase hex digits (SHA-256).
    """
    from .exchange import fingerprint_of_doc
    from .write import _rebuilt

    return fingerprint_of_doc(*_rebuilt(puzzle))


def validate(doc: dict) -> bool:
    """Strict reading checks of a format_version 1 dict (docs/formats/puzzle-format.md section 4).

    Parameters
    ----------
    doc : dict
        A pencilmark-puzzle document.

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


def describe(puzzle: str | dict | Path) -> dict:
    """The variant name and its rules in words, from the rules alone (pencilmark/variants.py).

    Parameters
    ----------
    puzzle : str, dict, Path or Puzzle
        Any format pencilmark.read reads (detected), or its document.

    Returns
    -------
    dict
        {"type": variant name, "rules": {short name: one-sentence rule, ...}, "rules_text": the rules as one text,
        "variants": the variants as snake_case ids, like tags (["killer", "german_whispers"])}.
    """
    from .variants import describe as d
    from .variants import public

    return public(d(puzzle))


def generate(spec: str | dict | Path) -> dict:
    """One puzzle for a "pencilmark-spec" request (docs/formats/generator-spec.md).

    Parameters
    ----------
    spec : dict, str or Path
        The request: a dict, JSON text or a path to a .json file.

    Returns
    -------
    dict
        {"puzzle": pencilmark-puzzle dict, "card": its pencilmark-grade card, "info": {...}}.

    Raises
    ------
    GenerationFailed
        No puzzle met the request in the time it allows.
    """
    from .gen.api import generate as g

    return g(spec)
