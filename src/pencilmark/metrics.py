"""Grading helpers over the engine's steps: the uniqueness-checked solve (grade_puzzle_checked), the pricing families
and the user-facing bands (Very Easy .. Extreme, data/techniques.csv)."""

import math

from . import _data
from . import registry as R
from . import solver as S
from .scoring import Scorer


def difficulty_grade(steps, P, tau=None, cap=True, head=True):
    """Soft-bottleneck grade on the DIFFICULTY head: each chosen move's race difficulty
    times exp(dtheta . meta) (absent -> the time-head grade).
    cap=False: no ceiling at the guess price (the card score stays open-ended above Extreme)."""
    from .scoring import meta_priced, meta_vector

    dth = P.get("difficulty_dtheta") if head else None  # head=False: no per-move difficulty-head multiplier
    cap = P["B"].get(S.GUESS, float("inf")) if cap else float("inf")
    ds = []
    for st in steps:
        d = min(st.move.d, cap)
        meta = st.move.feat[4] if len(st.move.feat) > 4 else None
        if dth and meta_priced(meta):
            d = min(d * math.exp(sum(a * b for a, b in zip(dth, meta_vector(meta, desc=False)))), cap)
        ds.append(d)
    if not ds:
        return 0.0
    tau = tau or P["tau"]
    dmax = max(ds)
    w = sum(math.exp((d - dmax) / tau) for d in ds)
    g = dmax + tau * math.log(max(w * P["ref_steps"] / len(ds), 1.0))
    # amount of hard reasoning: log(1 + summed excess over a Hidden Single), weighted by
    # the fitted difficulty_hard_w. Singles add nothing, so routine work (tediousness) stays out.
    hw = P.get("difficulty_hard_w", 0.0)
    if hw:
        d_ref = P["B"].get(S.HIDDEN_D, 1.0)
        g += hw * math.log1p(sum(max(0.0, d - d_ref) for d in ds))
    return g


FAMILY_TIERS = ["Beginner", "Easy", "Medium", "Hard", "Expert", "Master", "Extreme"]


# pricing families (the engine's structural groups for features and the family-ordered search), simplest first, from
# the technique registry (data/techniques.csv); inside a family, techniques in registry order
FAMILIES = [(f, [t.id for t in R.techniques() if t.family == f]) for f in R.FAMILIES]
_FAM_OF = {t: k for k, (_, ts) in enumerate(FAMILIES) for t in ts}


def family_of(tech):
    return _FAM_OF.get(tech, 0)


def grade_puzzle_checked(puzzle, P, explain=False, time_limit=60.0):
    """Uniqueness-checked grading entry point (use this for any external input).
    1. Independent CP-SAT check: 0 solutions -> {"status": "no solution"};
       2+ -> {"status": "multiple solutions", "solutions": [two examples]}.
    2. Unique -> solve and grade with uniqueness techniques allowed (assume_unique=True).
    3. Unknown (CP-SAT can't express a rule / timed out) -> grade with assume_unique=False,
       so no uniqueness reasoning (UR, BUG+1, ...) is applied to an unproven puzzle.
    Returns {"status", "unique", "grade", "steps"}."""
    from . import cbackend as CB
    from . import cpsat_verify as V
    from .scoring import grade

    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    known = getattr(puzzle, "_pm_solution", None)  # set by rate() once uniqueness is proven
    sols = [known] if known is not None else V.solutions(puzzle, limit=2, time_limit=time_limit)
    if sols is not None and len(sols) == 0:
        return {"status": "no solution", "unique": False}
    if sols is not None and len(sols) >= 2:
        return {"status": "multiple solutions", "unique": False, "solutions": sols[:2]}
    unique = sols is not None
    steps, solved = CB.solve(
        puzzle, P, solution=list(sols[0]) if unique else None, assume_unique=unique, explain=explain
    )
    g = grade(steps, puzzle, P, solved)
    return {
        "status": "ok" if unique else "uniqueness unverified (uniqueness techniques off)",
        "unique": unique,
        "grade": g,
        "steps": steps,
    }


# ---- user-facing difficulty BANDS (labels), separate from the pricing FAMILIES ----------------
# The label is the band of the hardest REQUIRED technique; variant techniques are placed by what they
# demand of a human (the pricing families lump all variant logic with pointing pairs).
BANDS = R.BANDS
BAND_MEANING = {
    "Very Easy": "the entry point: scanning without candidates (full house, hidden singles) and the obvious consequences "
    "of a rule ('a 6 in a cage of 11')",
    "Easy": "one step further: naked singles, pointing / claiming, reading one rule's combinations",
    "Medium": "subsets (naked and hidden pairs, triples, quads) and the implications of each variant rule",
    "Hard": "the first learned patterns: X-Wing, Skyscraper, 2-String Kite, Turbot Fish, simple colouring, the "
    "Phistomefel ring",
    "Very Hard": "the big study band: Empty Rectangle, finned fish, Swordfish and Jellyfish, wings, uniqueness, longer "
    "X-Chains, advanced variant logic (sum algebra, band logic)",
    "Expert": "chains and almost locked sets: XY-Chains, AIC, nice loops, Medusa, multi-colouring, case analysis",
    "Extreme": "the limit of human solving: forcing chains / nets, Nishio, pattern overlay, trial and error",
}
# technique -> band (data/techniques.csv). FAMILIES above stay the engine's structural groups (pricing / features).
# X-Chain, X-Wing, FinnedFish and LawOfLeftovers sit at their lowest shape's band here; band_path / export rate long
# X-Chains, Franken fish and Phistomefel-type set theory by the shape found (data/codes.csv shape_band).
_BAND_BY_NAME = {t.name: t.band for t in R.techniques() if t.band is not None}


def band_of(tech):
    """Band index (0 Very Easy .. 6 Extreme) of a technique code; unknown codes fall back to the family."""
    name = S.TECH_NAMES.get(tech, "")
    if name in _BAND_BY_NAME:
        return _BAND_BY_NAME[name]
    return min(family_of(tech), 6)


# card score (sudokuwiki-like, one scale for every variant and size). Bands are purely move-based; the
# score is ONE global monotone curve over the uncapped difficulty grade G (logarithmic, like Andrew Stuart's),
# aligned so a typical puzzle of each band falls inside that band's range (Andrew Stuart's classic-sudoku ranges:
# Very Easy < 3, Easy 3-4, Medium 4-5, Hard 5-7, Very Hard 7-9, Extreme 9+) -- but NOT clipped to it:
# a score outside its band's range is information (promotion / demotion: 'Hard, 4.6' = a light Hard).
# Anchors from the reference corpus (data/card_calibration.json, sorted G per band): score 0 at the
# easiest reference puzzle (a 4x4), each boundary score at the geometric mean of the neighbouring bands'
# median G, isotonic; above the Very Hard / Extreme boundary +1 per doubling of G (open-ended).
_ANCHOR_RANGES = [(0.0, 3.0), (3.0, 4.0), (4.0, 5.0), (5.0, 7.0), (7.0, 9.0), (9.0, float("inf"))]  # the six bands the
# calibration file (card_calibration.json) is keyed by: they fix the score curve, so difficulty did not move when the bands
# became seven (2026-10-30)
# readability ranges of the seven bands (score_fit notes): where a typical classic of each band lies (frozen benchmark)
SCORE_RANGES = [(0.0, 4.5), (4.5, 6.0), (6.0, 7.0), (6.0, 7.5), (6.5, 8.5), (8.0, 11.0), (11.0, float("inf"))]
_CALIB = None
_ANCHORS = None


def card_calibration():
    global _CALIB
    if _CALIB is None:
        f = "card_calibration.json"
        _CALIB = {int(k): v for k, v in _data.load_json(f).items()} if _data.exists(f) else {}
    return _CALIB


def score_anchors(calib=None):
    """[(log G, score), ...] increasing; None without a calibration."""
    global _ANCHORS
    if calib is None and _ANCHORS is not None:
        return _ANCHORS
    c = calib if calib is not None else card_calibration()
    med = {b: v[len(v) // 2] for b, v in c.items() if len(v) >= 10}
    if len(med) < 2:
        return None
    lo = min(v[0] for v in c.values() if v)
    pts = [(math.log(max(lo, 1e-6)), 0.0)]
    bands = sorted(med)
    for a, b in zip(bands, bands[1:]):
        x = 0.5 * (math.log(max(med[a], 1e-6)) + math.log(max(med[b], 1e-6)))
        pts.append((max(x, pts[-1][0] + 1e-3), _ANCHOR_RANGES[b][0]))
    if calib is None:
        _ANCHORS = pts
    return pts


def size_normalised(G, D, P):
    """Grade per grid size (as level() does): the same technique counts the same on 4x4 .. 25x25 --
    a bigger grid adds TIME (work), not difficulty."""
    sc = Scorer(P)
    return G / max(sc.size(D), 1e-9) * sc.size(9)


def card_score(G, calib=None):
    """Size-normalised uncapped difficulty grade -> score on the variant-agnostic 0..11+ scale (band-independent)."""
    pts = score_anchors(calib)
    if not pts:
        return None
    x = math.log(max(G, 1e-6))
    if x <= pts[0][0]:
        return 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1] + (x - pts[-1][0]) / math.log(2)


def score_fit(band_i, score):
    """Promotion / demotion note: the score lies above / below its move-set band's range."""
    lo, hi = SCORE_RANGES[band_i]
    return "heavy for its band" if score >= hi else ("light for its band" if score < lo else "")


