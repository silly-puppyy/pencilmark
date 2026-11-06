"""Card difficulty score: step value = d^beta x F / avail x exp(delta_tech) on the written human route;
difficulty = mapped log of the average step effort per empty cell (+ a technique-free search-effort term).
Parameters: the grader model (grader_model.py): price (difficulty), route (time effort, search effort), score.
"""

import math
import os

from . import cbackend as CB
from . import grader_model as GM
from . import solver as S
from .scoring import MENTAL
from .scoring import Scorer as _Scorer

dis = set(MENTAL)  # the first solve leaves out the moves worked out in the head
# score route_samples: the sampled routes run on threads (the engine releases the GIL; its listing caches are per
# thread); None = min(routes, CPU count). rate_many's worker processes set 1: there the processes already fill the cores.
ROUTE_THREADS = None


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
    fx = [getattr(s.move, "idfx", None) for s in st]
    held = (  # identity layer: identity-only steps no later step relied on cost nothing (cbackend.id_held)
        CB.id_held(p.N, p.givens, [(s.move.place, s.move.elim, f) for s, f in zip(st, fx)]) if any(fx) else ()
    )
    for i, s in enumerate(st):
        if held and held[i]:
            continue
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


def refute_lr_cell(p):
    """technique-free search effort of the puzzle: the engine's generic refutation profile (singles + pair
    relations + n-ary consistency; when stuck, every candidate trialled, shortest refutations applied) -> log1p(sum over stuck points of
    log(candidates / shortest refutations) per empty cell). Puzzle-only: no technique catalogue, no prices."""
    from . import cbackend as _CB
    from . import cpsat_verify as V

    known = getattr(p, "_pm_solution", None)  # set by rate(); otherwise the uniqueness search's solution, not a capped
    bs = [known] if known is not None else V.decide(p, limit=1)[0]  # brute_solve that gave up (2026-11-01: 0.0)
    if not bs:
        return 0.0
    model = GM.default()
    # rounds: independent of cell order
    route = dict(
        model.route,
        **(model.score.get("card_notes") or {}),
        **(model.score.get("card_route") or {}),
        refute_rounds=int(model.score.get("refute_rounds", 0)),
    )
    pr = _CB._C.refute_profile(_CB.to_cpuzzle(p), list(p.givens.items()), route, [int(x) for x in bs[0]], 400)
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


def _spot_params(P, cfg):
    """score route_samples: the price params for each sampled spotting route (seeds 1..K): route choice by the spotting
    score fitted on casual replays (price, technique, same box / row / column / digit as the previous placement,
    distance), sampled with probability ~ exp(score). The engine params' own spot_w / spot_fam unless the score config
    gives route_spot (w, fam by technique name, other)."""
    sp = cfg.get("route_spot")
    base = dict(P)
    if sp:
        fam = dict(sp.get("fam") or {}, other=sp.get("other", 0.0))
        base.update(
            locality=0.0,
            digit_cont=0.0,
            spot_w=list(sp.get("w") or []),
            spot_fam=_Scorer(dict(P, spot_fam=fam)).p["spot_fam"],
        )  # by name -> by technique code
    return [dict(base, spot_seed=k) for k in range(1, int(cfg["route_samples"]) + 1)]


# score route_rollouts: the steps that are singles (or note taking); every other step is a bottleneck
_SINGLE_NAMES = {
    "FullHouse",
    "HiddenSingle(direct)",
    "NakedSingle(direct)",
    "HiddenSingle(notes)",
    "NakedSingle(notes)",
    "LineSingle(direct)",
    "ConstraintSingle(direct)",
    "notes",
    "MentalSingle(direct)",
    "MentalNotesSingle",
}


def _rollout_sum(p, P, cfg, w, seed, n_play):
    """expected step-value sum of a human-like solver, from ONE human route plus cheap playthroughs (score
    route_rollouts): singles are confluent (every order of them reaches the same next bottleneck), so the route's
    bottleneck steps are kept and each stretch of singles between bottlenecks is replayed n_play times from the state
    the route reached, in random human order, same settings and note mode, cut at the stretch's length. None if the
    route is not the plain card route (guessing / full-search fallback)."""
    import copy

    from .band_path import variant_gate

    gate = variant_gate(p)
    st, ok = CB.solve(p, dict(P, spot_seed=seed), disabled=dis | gate)
    if not ok or any(s.move.feat[0] == S.GUESS for s in st):
        return None
    beta, delta = cfg["beta"], cfg.get("delta", {})
    cage_of = _cage_enum(p) if w and getattr(p, "has_cages", False) else {}

    def value(nm, d, f, cs):
        e = max((cage_of.get(c, 0.0) for c in cs), default=0.0)
        return math.exp(beta * math.log(d) + delta.get(nm, 0.0) + w * e) * f

    rec, cells = _record(p, st)
    N, D = p.N, p.D
    vals = [p.givens.get(c, 0) for c in range(N)]
    dom = getattr(p, "domains", None)
    cand = [0 if vals[c] else (dom[c] if dom else (1 << D) - 1) for c in range(N)]
    for c in range(N):
        if vals[c]:
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (vals[c] - 1))
    starts, run, n_run, bott = [(list(vals), list(cand), st[0].mode if st else "direct")], [], 0, 0.0
    for (nm, d, f), cs, s in zip(rec, cells, st):
        if nm in _SINGLE_NAMES:
            n_run += 1
        else:
            bott += value(nm, d, f, cs)
            run.append(n_run)
            n_run = 0
        if s.move.place:
            c, dg = s.move.place
            vals[c], cand[c] = dg, 0
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (dg - 1))
        for c, dg in s.move.elim or ():
            cand[c] &= ~(1 << (dg - 1))
        if nm not in _SINGLE_NAMES:
            starts.append((list(vals), list(cand), s.mode))
    run.append(n_run)
    cp = CB.to_cpuzzle(p)
    total = bott
    for (vs, cs_, mode), n in zip(starts, run):
        if not n:
            continue
        q = copy.copy(p)
        q.givens = {c: v for c, v in enumerate(vs) if v}
        mask = [cs_[c] if not vs[c] else 1 << (vs[c] - 1) for c in range(N)]
        acc = 0.0
        for k in range(n_play):
            st2, _ = CB.solve(
                q,
                dict(P, spot_seed=1000 * seed + k + 1),
                disabled=dis | gate,
                cpuzzle=cp,
                cand=mask,
                max_steps=n,
                assume_unique=False,
                allow_direct=mode != "notes",
            )
            r2, c2 = _record(q, st2)
            acc += sum(value(nm, d, f, cc) for (nm, d, f), cc in zip(r2, c2) if nm in _SINGLE_NAMES)
        total += acc / n_play
    return total


def score_parts(p, model=None):
    """(card score, L1 = log of the step-value sum) for one puzzle; None if the engine must guess. The score is priced
    with the model's difficulty prices, L1 (the effort the time model reads) with its route prices; both on the
    written route each price set produces."""
    model = model or GM.default()
    cfg = model.score
    w = cfg.get("enum_w", 0.0)
    # score card_route: the card's difficulty and time read the price-first route (one route: the cheapest move each
    # step); the human closeness route (engine params spot_*) is the trace's. route_samples > 0 averages sampled routes.
    cn = cfg.get("card_notes") or {}  # the card prices full candidate notes; the note model is the trace's
    cr = dict(cn, **(cfg.get("card_route") or {}))
    P_route, P_price = dict(model.route, **cr), dict(model.price, **cr)
    P_human = dict(model.price, **cn)  # human routes for rollouts / samples, with the card's notes
    pth_time = _route(p, P_route, w)
    if not pth_time:
        return None
    pth = _route(p, P_price, w) or pth_time

    def values(path):
        return sorted(
            (
                math.exp(cfg["beta"] * math.log(d) + cfg.get("delta", {}).get(nm, 0.0) + w * e) * f
                for nm, d, f, e in path
            ),
            reverse=True,
        )

    v = values(pth)
    tot = sum(v)
    ro = cfg.get("route_rollouts")
    if ro:  # expected effort of a human-like solver: human routes' bottlenecks + playthroughs of the singles between
        sums = [
            _rollout_sum(p, P_human, cfg, w, k, int(ro.get("playthroughs", 4)))
            for k in range(1, int(ro.get("routes", 2)) + 1)
        ]
        sums = [x for x in sums if x is not None]
        if sums:
            tot = sum(sums) / len(sums)
    elif cfg.get("route_samples"):  # expected effort of a human-like solver: mean step sum over sampled spotting routes
        Ps = _spot_params(P_human, cfg)
        nt = min(len(Ps), ROUTE_THREADS or os.cpu_count() or 1)
        if nt > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(nt) as ex:
                paths = list(ex.map(lambda P_k: _route(p, P_k, w), Ps))
        else:
            paths = [_route(p, P_k, w) for P_k in Ps]
        sums = [sum(values(x or pth)) for x in paths]
        tot = sum(sums) / len(sums)
    return _finish(p, cfg, tot, v, pth_time, w)


def _finish(p, cfg, tot, v, pth_time, w):
    """(card score, L1) from a route's step-value sum tot (v: its values, hardest first) and the route the time reads"""
    if cfg.get("stat") == "per_cell":  # average effort to discover one cell = step sum / empty cells
        empty = max(p.N - len(p.givens), 1)
        lpc = math.log(max(tot / empty, 1e-9))
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


def score_path(p, path, model=None):
    """(card score, L1) for a route given as [(technique name, price, F)] (F = density / alternatives, as _record):
    the fog route's steps (rate under fog), priced with the card's value function, refutation term and map. None for
    an empty route."""
    model = model or GM.default()
    cfg = model.score
    if not path:
        return None
    v = sorted(
        (math.exp(cfg["beta"] * math.log(max(d, 1e-3)) + cfg.get("delta", {}).get(nm, 0.0)) * f for nm, d, f in path),
        reverse=True,
    )
    return _finish(p, cfg, sum(v), v, [(nm, max(d, 1e-3), f, 0.0) for nm, d, f in path], 0.0)
