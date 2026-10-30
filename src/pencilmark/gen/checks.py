"""Solvability / uniqueness checks used while generating.

Checker  -- band-capped human solve (the engine with only techniques of band <= cap, or an explicit technique set):
            "solvable" means every cell is placed by logic, which implies a unique solution, so digging needs no
            separate uniqueness search.
Oracle   -- CP-SAT uniqueness with a counterexample cache (CEGAR): every alternative solution CP-SAT finds is kept and
            refutes later candidates in pure Python; only candidates that refute the whole cache reach CP-SAT.
"""
from __future__ import annotations

from .. import puzzle_json as PJ, cbackend as CB, solver as S, export as E2, band_path as BP
from .. import _data
from ..scoring import complete_params
from .elements import to_json, satisfies

_PARAMS = None


def params(path=None):
    """the engine's params with search='human' (loaded once); path: a JSON params file of the same shape instead."""
    global _PARAMS
    if path is not None:
        import json
        from pathlib import Path
        return dict(complete_params(_data._int_keys(json.loads(Path(path).read_text(encoding="utf-8")))), search="human")
    if _PARAMS is None:
        _PARAMS = dict(complete_params(_data.load_params("params.json")), search="human")
    return _PARAMS


NOTES = set(getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,)))


def logic_techs(P):
    """engine techniques usable by a human route (no computer search, no guessing, no note-taking pseudo moves)."""
    comp = set(CB.search_disabled(P)) | {S.GUESS}
    return {t for t in S.TECH_NAMES if t not in comp and t not in NOTES}


def band_techs(P, cap):
    return {t for t in logic_techs(P) if E2.tech_band(t) <= cap}


def code_techs(P, code):
    """engine techniques whose chip is `code` (shape-split techniques included, e.g. X-Wing for XWG)."""
    return {t for t in logic_techs(P) if E2.chip_of(t)[0] == code}


class Checker:
    """solvable by logic with techniques in `allowed` (default: band <= cap) -> unique by construction."""

    def __init__(self, board, cap=6, allowed=None, P=None, max_steps=None):
        self.b = board
        self.P = P or params()
        self.allowed = set(allowed) if allowed is not None else band_techs(self.P, cap)
        self.max_steps = max_steps or max(400, 6 * board.N)
        self.calls = 0

    def left(self, givens, els):
        """cells the capped solve leaves unplaced (0 = solvable within the cap)."""
        self.calls += 1
        p = PJ.from_json(to_json(self.b, givens, els))
        p.finalize()
        allowed = self.allowed - BP.variant_gate(p)
        st, _ = CB.solve(p, self.P, disabled=set(S.TECH_NAMES) - allowed - NOTES, max_steps=self.max_steps,
                         assume_unique=False)
        placed = sum(1 for s in st if s.move.place and s.move.feat[0] != S.GUESS)
        return p.N - len(p.givens) - placed

    def ok(self, givens, els):
        return self.left(givens, els) == 0


class Oracle:
    """CP-SAT uniqueness with a cache of alternative solutions (single worker: deterministic, light on the machine)."""

    def __init__(self, board, sol, time_limit=30.0, max_pool=400, workers=1):
        self.b, self.sol, self.tl, self.max_pool, self.workers = board, list(sol), time_limit, max_pool, workers
        self.pool, self.calls, self.hits = [], 0, 0

    def unique(self, givens, els):
        for alt in self.pool:
            if satisfies(self.b, alt, givens, els):
                self.hits += 1
                return False
        from .. import cpsat_verify as V
        self.calls += 1
        p = PJ.from_json(to_json(self.b, givens, els))
        p.finalize()
        sols = V.solutions(p, limit=2, time_limit=self.tl, workers=self.workers)
        if sols is None:
            return False                       # timeout / not expressible: not proven unique
        alts = [list(x) for x in sols if list(x) != self.sol]
        if alts:
            self.pool.insert(0, alts[0])
            del self.pool[self.max_pool:]
            return False
        return len(sols) == 1

    def refuted(self, givens, els):
        """True if a cached alternative still satisfies the candidate (it cannot be unique)."""
        return any(satisfies(self.b, alt, givens, els) for alt in self.pool)
