"""Card difficulty score: step value = d^beta x F / avail x exp(delta_tech) on the written human route;
difficulty = mapped log of the average step effort per empty cell (+ a technique-free search-effort term).
Parameters: the grader model (grader_model.py): price (difficulty), route (time effort, search effort), score.
"""

import math

from . import cbackend as CB
from . import grader_model as GM
from . import solver as S
from .scoring import MENTAL
from .scoring import Scorer as _Scorer

dis = set(MENTAL)  # the first solve leaves out the moves worked out in the head


def steps(p, P):
    """the written route under params P -> ([(technique name, price, F)], cells each step touches)"""
    from .band_path import variant_gate

    gate = variant_gate(p)  # variant techniques only for puzzles with the matching rules (as the card's bands)
    st, ok = CB.solve(p, P, disabled=dis | gate)
    if not ok or any(s.move.feat[0] == S.GUESS for s in st):
        st, ok = CB.solve(p, P, disabled=gate)
        if not ok or any(s.move.feat[0] == S.GUESS for s in st):
            # guessing off: where it would guess, prove by full search (Trial and error, priced as that guess)
            st, ok = CB.solve(p, dict(P, exhaust_fallback=1), disabled=gate | {S.GUESS})
            if not ok:
                return [], []  # beyond engine: no score
    return _record(p, st)


def _record(p, st):
    sc = _Scorer(
        GM.default().route
    )  # grid-size factor of the shipped engine params (the same alpha in both price sets)
    out, cells_ = [], []
    for s in st:
        t = s.move.feat[0]
        nm = "notes" if t in S.NOTE_TECHS else S.TECH_NAMES[t]
        # ABSOLUTE candidate density, Andrew Stuart's C / 727 * 20 on every grid size: human times across sizes favour it
        # ... but only up to 9x9 size: beyond it no extra per-step difficulty is supported by data (sudokuleader
        # 12x12-25x25: partial Spearman +0.07), so bigger grids add TIME, not difficulty (relative density above 729 slots)
        C = s.n_cands if s.n_cands is not None else p.N * p.D
        F = C / 727 * 20 if p.N * p.D <= 729 else C / (p.N * p.D) * 20 * 729 / 727
        d = float(s.move.d)
        if p.D > 9:  # the engine price carries a grid-size factor ((D-1)/8)^alpha that d^beta would amplify:
            d /= sc.size(p.D) / sc.size(9)  # beyond 9x9 bigger grids add time, not per-step difficulty
        out.append((nm, max(d, 1e-3), F / max(len(s.alts), 1)))
        cells_.append(([s.move.place[0]] if s.move.place else []) + [c for c, _ in (s.move.elim or ())])
    return out, cells_


_LAST_REFUTE = None


def refute_lr_cell(p):
    """technique-free search effort of the puzzle: the engine's generic refutation profile (singles + pair
    relations + n-ary consistency; when stuck, every candidate trialled, shortest refutations applied) -> log1p(sum over stuck points of
    log(candidates / shortest refutations) per empty cell). Puzzle-only: no technique catalogue, no prices."""
    global _LAST_REFUTE
    from . import cbackend as _CB

    known = getattr(p, "_pm_solution", None)
    bs = [known] if known is not None else _CB.brute_solve(p, limit=1)
    if not bs:
        _LAST_REFUTE = None
        return 0.0
    pr = _CB._C.refute_profile(
        _CB.to_cpuzzle(p), list(p.givens.items()), GM.default().route, [int(x) for x in bs[0]], 400
    )
    _LAST_REFUTE = [tuple(x) for x in pr]
    s = sum((math.log(C / R) if R else math.log(max(C, 1)) + 2) for C, R, d, dp, rel in pr)
    return math.log1p(s / max(p.N - len(p.givens), 1))


def _cage_enum(p):
    """cell -> max log(number of digit combinations) over the sum cages containing it (distinct digits, size k, total s);
    measured from the rule instance itself -- any summed cage has a combination count, no variant label."""
    import itertools

    out = {}
    for g in getattr(p, "groups", ()):
        if getattr(g, "kind", "") == "cage" and getattr(g, "total", None):
            k, s_ = len(g.cells), int(g.total)
            key = (k, s_, p.D)
            if key not in _ENUM_CACHE:
                _ENUM_CACHE[key] = math.log(
                    max(1, sum(1 for c in itertools.combinations(range(1, p.D + 1), k) if sum(c) == s_))
                )
            for c in g.cells:
                out[c] = max(out.get(c, 0.0), _ENUM_CACHE[key])
    return out


_ENUM_CACHE = {}


def _pair_enum(p):
    """cell -> max log(ordered digit pairs a pairwise rule allows, distinct digits) over the CONSTRAINING relations at the
    cell (allowed share of pairs <= 1/2: kropki, XV, difference, ratio, whisper, thermo ...; global negatives such as
    non-consecutive allow most pairs and are skipped by that measured share, not by name) -- the pairwise twin of
    _cage_enum."""
    from .model import RELATIONS

    out, D = {}, p.D
    for rel in getattr(p, "relations", ()):
        kind, a, b, args = rel[0], rel[1], rel[2], tuple(rel[3:])
        f = RELATIONS.get(kind)
        if f is None:
            continue
        key = ("pair", kind, args, D)
        if key not in _ENUM_CACHE:
            try:
                k = sum(1 for v in range(1, D + 1) for w in range(1, D + 1) if v != w and f(v, w, *args))
            except Exception:
                k = 0
            _ENUM_CACHE[key] = math.log(k) if 0 < k <= D * (D - 1) / 2 else None
        e = _ENUM_CACHE[key]
        if e is not None:
            for c in (a, b):
                out[c] = max(out.get(c, 0.0), e)
    return out


def steps_enum(p, P):
    """steps(p, P) plus, per step, the enumeration size of the cages its cells touch (0 without cages)."""
    pth, cells = steps(p, P)
    if not pth or not getattr(p, "has_cages", False):
        return [(nm, d, f, 0.0) for nm, d, f in pth]
    cage_of = _cage_enum(p)
    return [(nm, d, f, max((cage_of.get(c, 0.0) for c in cs), default=0.0)) for (nm, d, f), cs in zip(pth, cells)]


def _route(p, P, w):
    """the written route under P with the enumeration term (or 0 when its weight is 0)"""
    return steps_enum(p, P) if w else [(nm, d, f, 0.0) for nm, d, f in steps(p, P)[0]]


def _softplus_map(mp, r):
    x = (r - mp["r0"]) / mp["w"]
    return mp["A"] * mp["w"] * (math.log1p(math.exp(-abs(x))) + max(x, 0.0))


_R_AT = {}


def _r_at(mp, score):
    """r where the softplus map reaches `score` (bisection; cached per map)."""
    key = (mp["A"], mp["r0"], mp["w"], score)
    if key not in _R_AT:
        lo, hi = mp["r0"] - 50.0, mp["r0"] + 50.0
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if _softplus_map(mp, mid) < score else (lo, mid)
        _R_AT[key] = 0.5 * (lo + hi)
    return _R_AT[key]


def score_parts(p, model=None):
    """(card score, L1 = log of the step-value sum) for one puzzle; None if the engine must guess. The score is priced
    with the model's difficulty prices, L1 (the effort the time model reads) with its route prices; both on the
    written route each price set produces."""
    model = model or GM.default()
    cfg = model.score
    w = cfg.get("enum_w", 0.0)
    pth_time = _route(p, model.route, w)
    if not pth_time:
        return None
    pth = _route(p, model.price, w) or pth_time
    v = sorted(
        (math.exp(cfg["beta"] * math.log(d) + cfg.get("delta", {}).get(nm, 0.0) + w * e) * f for nm, d, f, e in pth),
        reverse=True,
    )
    if cfg.get("stat") == "per_cell":  # average effort to discover one cell = step sum / empty cells
        empty = max(p.N - len(p.givens), 1)
        lpc = math.log(max(sum(v) / empty, 1e-9))
        if cfg.get("refute_w"):  # technique-free search effort (refute.cpp): + w * log1p(sum log(C/R) / empty cells)
            lpc += cfg["refute_w"] * refute_lr_cell(p)
        r = 2 * lpc / math.log(5)
    else:  # mean of the hardest quarter of steps
        top = v[: max(1, len(v) // 4)]
        r = 2 * math.log(max(sum(top) / len(top), 1e-9)) / math.log(5)
    # one continuous formula, no ceiling: A * w * softplus((r - r0) / w) from score 2 up; below 2,
    # 2 * exp(A * (r - r2) / 2) (same value and slope at 2, about the square root of effort, never negative; human times
    # keep rising there, 2026-10-30)
    mp = cfg["map"]
    score = _softplus_map(mp, r)
    if score < 2.0:
        score = 2.0 * math.exp(mp["A"] * (r - _r_at(mp, 2.0)) / 2.0)
    return score, math.log(
        max(
            sum(
                math.exp(cfg.get("beta_time", cfg["beta"]) * math.log(d) + cfg.get("delta", {}).get(nm, 0.0) + w * e)
                * f
                for nm, d, f, e in pth_time
            ),
            1e-9,
        )
    )
