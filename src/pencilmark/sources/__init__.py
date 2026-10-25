"""Puzzle sources: links / payloads from SudokuPad, f-puzzles, penpa-edit and Logic Masters -> puzzle JSON.

    from pencilmark import sources
    pj = sources.load("https://sudokupad.app/wjgxgaji9a")              # -> puzzle JSON dict (pencilmark.puzzle_json)
    p = pencilmark.puzzle_json.from_json(pj)

load() recognises
    SudokuPad    sudokupad.app/... , app.crackingthecryptic.com/... (short ids are fetched: one API request),
                 bare 'scl...' / 'ctc...' / 'fpuzzles...' payloads, 'sudokupad:<shortid>'
    f-puzzles    f-puzzles.com/?load=... (offline), ?id=<alias> (one TinyURL HEAD request)
    penpa        any .../penpa-edit/?m=..&p=... (penpa-edit, penpa+, mirrors; offline), 'penpa:<p value>'
    LMD          logic-masters.de/Raetselportal/Raetsel/zeigen.php?id=XXXXXX or 'lmd:XXXXXX' (page fetch, robots.txt
                 obeyed, >= 2.5 s between requests), converting the first linked puzzle that translates
    shorteners   tinyurl / bit.ly / git.io / is.gd links are resolved (one HEAD request) and dispatched
    puzzle JSON  a dict / JSON text already in pencilmark.puzzle_json format is returned as is
Modules: sudokupad, fpuzzles, penpa, lmd (each with decode / to_puzzle; see their docstrings for coverage).
Errors: SourceError > DecodeError (unrecognised / undecodable), FetchError (network, robots.txt), UnsupportedPuzzle
(.elements = what could not be mapped exactly; nothing is silently dropped), VerificationError (verify=True).
"""
from __future__ import annotations

import json
import re

from ._common import USER_AGENT, DecodeError, FetchError, SourceError, UnsupportedPuzzle


class VerificationError(SourceError):
    """verify=True: the translated puzzle is not unique, or contradicts its embedded solution."""


def detect(x):
    """-> 'puzzle_json' | 'sudokupad' | 'fpuzzles' | 'penpa' | 'lmd' | 'short' | None."""
    from . import fpuzzles, lmd, penpa, sudokupad
    if isinstance(x, dict):
        if x.get("format") == "penpa":
            return "penpa"
        if x.get("format") == "fpuzzles" or ("grid" in x and "size" in x):
            return "fpuzzles"
        if "puzzle" in x and "format" in x:
            return "sudokupad"
        if "numbers" in x or "digits" in x:
            return "puzzle_json"
        if "cells" in x:
            return "sudokupad"
        return None
    if not isinstance(x, str):
        return None
    s = x.strip()
    lo = s.lower()
    if lo.startswith("lmd:") or lmd.lmd_id_of(s):
        return "lmd"
    if lo.startswith("sudokupad:"):
        return "sudokupad"
    if lo.startswith("penpa:"):
        return "penpa"
    if s.startswith("{"):
        try:
            return detect(json.loads(s))
        except ValueError:
            return None
    if "://" in s:
        if sudokupad.is_sudokupad_url(s):
            return "sudokupad"
        if fpuzzles.is_fpuzzles_url(s):
            return "fpuzzles"
        if penpa.is_penpa_url(s):
            return "penpa"
        if re.match(r"https?://(?:www\.)?(?:%s)/" % "|".join(map(re.escape, lmd.SHORTENERS)), lo):
            return "short"
        return None
    if s.startswith(sudokupad.PAYLOAD_PREFIXES):
        return "sudokupad"
    return None


def load(x, rules_text=None, infer=False, fetch=True, verify=False, time_limit=30.0):
    """Link / payload / decoded dict -> puzzle JSON dict. rules_text: the rules from the page that links the puzzle
    (used where the puzzle file has none, and for penpa's rule screening). infer=True lets SudokuPad / f-puzzles
    search line readings with the solver (slow). fetch=False refuses anything that needs a network request.
    verify=True checks uniqueness (and the embedded solution) with CP-SAT and raises VerificationError otherwise."""
    from . import fpuzzles, lmd, penpa, sudokupad
    kind = detect(x)
    s = x.strip() if isinstance(x, str) else x
    if kind is None:
        raise DecodeError(f"unrecognised puzzle link / payload: {str(x)[:80]!r}")
    if kind == "puzzle_json":
        pj = json.loads(s) if isinstance(s, str) else dict(s)
    elif kind == "short":
        if not fetch:
            raise DecodeError(f"{s} is a shortened link; resolving it needs a request (fetch=True)")
        target = lmd.resolve_short(s)
        if not target or detect(target) in (None, "short"):
            raise DecodeError(f"{s} does not resolve to a supported puzzle link ({str(target)[:80]})")
        pj = load(target, rules_text=rules_text, infer=infer, fetch=fetch)
    elif kind == "lmd":
        if not fetch:
            raise DecodeError("an LMD puzzle needs a page request (fetch=True)")
        pid = s[4:].strip() if s.lower().startswith("lmd:") else lmd.lmd_id_of(s)
        pj = lmd.to_puzzle(pid, infer=infer)
    elif kind == "sudokupad":
        if isinstance(s, str) and s.lower().startswith("sudokupad:"):
            s = s[len("sudokupad:"):]
        pj = sudokupad.to_puzzle(s, page_text=rules_text, infer=infer, fetch=fetch)
    elif kind == "fpuzzles":
        pj = fpuzzles.to_puzzle(s, rules_text=rules_text, infer=infer, fetch=fetch)
    else:
        if isinstance(s, str) and s.lower().startswith("penpa:"):
            s = s[len("penpa:"):]
        pj = penpa.to_puzzle(s, rules_text=rules_text)
    if verify:
        check(pj, time_limit=time_limit)
    return pj


def check(pj, time_limit=30.0):
    """Unique solution (and equal to pj['solution'] when present) or VerificationError. Returns the solution string."""
    from .. import cpsat_verify, puzzle_json
    p = puzzle_json.from_json(pj)
    p.finalize()
    sols = cpsat_verify.solutions(p, limit=2, time_limit=time_limit)
    if sols is None:
        raise VerificationError("uniqueness could not be decided (unsupported constraint or search limit)"
                                + ("" if cpsat_verify.have_ortools() else "; " + cpsat_verify.VERIFY_HINT))
    if len(sols) != 1:
        raise VerificationError(f"{len(sols)} solutions")
    got = "".join(puzzle_json._sym(v) for v in sols[0])
    if pj.get("solution") and pj["solution"] != got:
        raise VerificationError("unique solution differs from the embedded solution")
    return got


__all__ = ["load", "detect", "check", "SourceError", "DecodeError", "FetchError", "UnsupportedPuzzle",
           "VerificationError", "USER_AGENT", "sudokupad", "fpuzzles", "penpa", "lmd"]


def __getattr__(name):                     # lazy submodule access: sources.sudokupad, sources.penpa, ...
    if name in ("sudokupad", "fpuzzles", "penpa", "lmd"):
        import importlib
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(name)
