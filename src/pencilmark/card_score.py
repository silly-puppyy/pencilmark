"""Card difficulty score: step value = d^beta x F / avail x exp(delta_tech) on the written human route;
difficulty = mapped log of the average step effort per empty cell (+ a technique-free search-effort term).
Configuration: data/card_score.json; price weights: data/params.json (route) and data/price_params.json (difficulty).
"""
import json
import math

from . import _data
from . import cbackend as CB, solver as S
from .scoring import Scorer as _Scorer, complete_params

MENTAL = ("MentalChain(direct)", "MentalSingle(direct)", "MentalNotesSingle", "WhatIf", "EitherWay", "ShortTrial")
P = complete_params(_data.load_params("params.json"))
SC = _Scorer(P)

dis = {t for t, n in S.TECH_NAMES.items() if n in MENTAL}


_LAST_CELLS = []


def steps(p):
    from .band_path import variant_gate
    gate = variant_gate(p)          # variant techniques only for puzzles with the matching rules (as the card's bands)
    st, ok = CB.solve(p, P, disabled=dis | gate)
    if not ok or any(s.move.feat[0] == S.GUESS for s in st):
        st, ok = CB.solve(p, P, disabled=gate)
        if not ok or any(s.move.feat[0] == S.GUESS for s in st):
            # guessing off: where it would guess, prove by full search (Trial and error, priced as that guess)
            st, ok = CB.solve(p, dict(P, exhaust_fallback=1), disabled=gate | {S.GUESS})
            if not ok:
                return []                  # beyond engine: no score
    return _record(p, st)


def _record(p, st):
    out, cells_, xs_ = [], [], []
    for s in st:
        t = s.move.feat[0]
        nm = "notes" if t in S.NOTE_TECHS else S.TECH_NAMES[t]
        # ABSOLUTE candidate density, Andrew Stuart's C / 727 * 20 on every grid size: human times across sizes favour it
        # ... but only up to 9x9 size: beyond it no extra per-step difficulty is supported by data (sudokuleader
        # 12x12-25x25: partial Spearman +0.07), so bigger grids add TIME, not difficulty (relative density above 729 slots)
        C = s.n_cands if s.n_cands is not None else p.N * p.D
        F = C / 727 * 20 if p.N * p.D <= 729 else C / (p.N * p.D) * 20 * 729 / 727
        d = float(s.move.d)
        if p.D > 9:      # the engine price carries a grid-size factor ((D-1)/8)^alpha that d^beta would amplify:
            d /= SC.size(p.D) / SC.size(9)     # beyond 9x9 bigger grids add time, not per-step difficulty
        out.append((nm, max(d, 1e-3), F / max(len(s.alts), 1)))
        cells_.append(([s.move.place[0]] if s.move.place else []) + [c for c, _ in (s.move.elim or ())])
        xs_.append(_xvec(s.move.feat[-1]))
    global _LAST_CELLS, _LAST_X
    _LAST_CELLS = cells_
    _LAST_X = xs_
    return out


_LAST_X = None


def _xvec(meta):
    """the 21 numbers a step's price is linear in (18 = meta_vector + 8 descriptors, + 3 depth interactions); None without meta"""
    if meta is None or len(meta) < 18:
        return None
    from .scoring import meta_vector
    x = list(meta_vector(meta, desc=False)) + [float(t) for t in meta[10:18]]
    br, dp = x[10], x[11]
    return x + [dp * x[1], dp * x[4], dp * br]


_PP = {}
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
    pr = _CB._C.refute_profile(_CB.to_cpuzzle(p), list(p.givens.items()), SC.p, [int(x) for x in bs[0]], 400)
    _LAST_REFUTE = [tuple(x) for x in pr]
    s = sum((math.log(C / R) if R else math.log(max(C, 1)) + 2) for C, R, d, dp, rel in pr)
    return math.log1p(s / max(p.N - len(p.givens), 1))


def _price_params(name):
    if name not in _PP:
        _PP[name] = complete_params(_data.load_params(name))
    return _PP[name]


_TIME_W = None
_SC9_V = None


def _SC9():
    global _SC9_V
    if _SC9_V is None:
        _SC9_V = SC.size(9)
    return _SC9_V


def _time_weights():
    """Time and difficulty use separate price weights on the same route. Difficulty = the card-fit weights (installed
    params); time = data/time_model.json "price_weights" (the refit's time-trained weights). None -> time uses the card prices."""
    global _TIME_W
    if _TIME_W is None:
        try:
            tm = _data.load_json("time_model.json")
            _TIME_W = tm.get("price_weights") or False
        except Exception:
            _TIME_W = False
    return _TIME_W or None




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
                _ENUM_CACHE[key] = math.log(max(1, sum(1 for c in itertools.combinations(range(1, p.D + 1), k) if sum(c) == s_)))
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


def steps_enum(p):
    """steps(p) plus, per step, the enumeration size of the cages its cells touch (0 without cages)."""
    pth = steps(p)
    if not pth or not getattr(p, "has_cages", False):
        return [(nm, d, f, 0.0) for nm, d, f in pth]
    cage_of = _cage_enum(p)
    cells = _LAST_CELLS
    return [(nm, d, f, max((cage_of.get(c, 0.0) for c in cs), default=0.0)) for (nm, d, f), cs in zip(pth, cells)]


def score_parts(p, cfg):
    """(card score, L1 = log of the step-value sum) for one puzzle; None if the engine must guess. L1 is the effort
    the time model reads (data/time_model.json)."""
    w = cfg.get("enum_w", 0.0)
    pth = steps_enum(p) if w else [(nm, d, f, 0.0) for nm, d, f in steps(p)]
    if not pth:
        return None
    pth_time, x_time = pth, _LAST_X
    if cfg.get("price_params"):   # difficulty from the card-fit price weights on THEIR route; time (L1) from the
        global P
        P_old = P                 # production route above (time / bands / everything else unchanged)
        P = _price_params(cfg["price_params"])
        try:
            pth_d = steps_enum(p) if w else [(nm, d, f, 0.0) for nm, d, f in steps(p)]
        finally:
            P = P_old
        if pth_d:
            pth = pth_d
    v = sorted((math.exp(cfg["beta"] * math.log(d) + cfg["delta"].get(nm, 0.0) + w * e) * f for nm, d, f, e in pth), reverse=True)
    if cfg.get("stat") == "per_cell":   # average effort to discover one cell = step sum / empty cells
        empty = max(p.N - len(p.givens), 1)
        lpc = math.log(max(sum(v) / empty, 1e-9))
        if cfg.get("refute_w"):          # technique-free search effort (refute.cpp): + w * log1p(sum log(C/R) / empty cells)
            lpc += cfg["refute_w"] * refute_lr_cell(p)
        r = 2 * lpc / math.log(5)
    else:                               # mean of the hardest quarter of steps
        top = v[:max(1, len(v) // 4)]
        r = 2 * math.log(max(sum(top) / len(top), 1e-9)) / math.log(5)
    if cfg.get("map"):            # one continuous formula, floor 0, no ceiling: A * w * softplus((r - r0) / w)
        mp = cfg["map"]; x = (r - mp["r0"]) / mp["w"]
        score = mp["A"] * mp["w"] * (math.log1p(math.exp(-abs(x))) + max(x, 0.0))
    else:
        score = cfg["a"] + cfg["b"] * r + cfg.get("c", 0.0) * r * r     # map refitted on fed + sudokuwiki-rated hard puzzles
    if cfg.get("price_params"):   # time effort from the production route
        return score, math.log(max(sum(math.exp(cfg.get("beta_time", cfg["beta"]) * math.log(d) + cfg["delta"].get(nm, 0.0) + w * e) * f
                                       for nm, d, f, e in pth_time), 1e-9))
    tw = _time_weights()
    if tw and _LAST_X is not None and len(_LAST_X) == len(pth):   # time effort: same route, time price weights (log-price delta)
        P_ = P
        wc = list(P_.get("meta_theta_full") or [])[:18] + list(P_.get("meta_theta_interact") or [0.0, 0.0, 0.0])[:3]
        dw = [a_ - b_ for a_, b_ in zip(tw, wc)]
        vt = 0.0
        for (nm, d, f, e), x in zip(pth, _LAST_X):
            ld = min(math.log(d) + (sum(a_ * b_ for a_, b_ in zip(dw, x)) if x is not None else 0.0),
                     6.907755278982137 + math.log(_SC9()))        # the engine's log-price cap (log 1000) on the time price too
            vt += math.exp(cfg["beta"] * ld + cfg["delta"].get(nm, 0.0) + w * e) * f
        return score, math.log(max(vt, 1e-9))
    return score, math.log(max(sum(v), 1e-9))


def score_puzzle(p, cfg):
    """Card score from data/card_score.json (version 3) for one puzzle; None if the engine must guess."""
    r = score_parts(p, cfg)
    return None if r is None else r[0]
