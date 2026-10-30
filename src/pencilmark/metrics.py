"""Interpretable scores on top of grade().

level   logic difficulty in points: +1 point = the puzzle's bottleneck takes
        2x longer to spot. Under the race model a lone move of difficulty d
        among n empty cells is found after ~c*n*exp(beta*d) seconds, so
        log2(time) = beta*d/ln2 + const. Size-normalized (difficulty divided by
        the size factor), so a 16x16 needing only singles scores like a 9x9
        needing only singles; size shows up in `time` instead. 0 = a full house.
tier    name of the band the level falls in, with the techniques expected at
        that tier (data/tiers.json, fitted from the
        calibrated per-technique levels).
time    predicted solve time in minutes for the reference solver (the median
        fed-sudoku solver).
"""

import math

from . import _data
from . import registry as R
from . import solver as S
from .scoring import Scorer

TIERS_FILE = "tiers.json"  # in pencilmark/data
_TIERS = None


def ref_difficulty(P):
    """Difficulty of a full house on a 9x9 (the zero point)."""
    sc = Scorer(P)
    # full house meta as the solver emits it: house of 9 cells, 1 group, 1 digit
    feat = (S.FULL_HOUSE, 1.0, (), 0, (9, 1, 1, 0, 0, 0, 0, 0, 1.0))
    return sc.difficulty(feat, 9)


def level(G, D, P):
    """Grade difficulty G on a D-digit puzzle -> points (0 = a full house).
    With P["level_slope"]: +1 point = the odds that a solver gives up double
    (logit(abandon) = a + slope * G, fitted on real abandonment). Otherwise +1 point =
    the bottleneck takes 2x longer to spot (race model)."""
    sc = Scorer(P)
    g = G / max(sc.size(D), 1e-9) * sc.size(9)
    k = P.get("level_slope") or P["beta"]
    return k * (g - ref_difficulty(P)) / math.log(2)


def tiers():
    global _TIERS
    if _TIERS is None:
        _TIERS = _data.load_json(TIERS_FILE) if _data.exists(TIERS_FILE) else None
    return _TIERS


def tier_of(points):
    T = tiers()
    if T is None:
        return None
    for t in T["tiers"]:
        if points < t["max"]:
            return t
    return T["tiers"][-1]


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
TIER_MEANING = {
    "Beginner": "singles only (full house, hidden/naked singles, constraint singles)",
    "Easy": "intersections and simple combinations (pointing, box-line, cage/arrow/line combos, law of leftovers)",
    "Medium": "subsets (pairs, triples, quads, incl. done mentally)",
    "Hard": "fish and wings (X-Wing, Swordfish, XY-Wing, finned fish, uniqueness)",
    "Expert": "chains (X-Chain, XY-Chain, colouring, AIC, nice loops)",
    "Master": "almost locked sets (ALS-XZ, ALS-XY-Wing, death blossom)",
    "Extreme": "logic runs out: trial / bifurcation needed",
}


def family_tier(puzzle, P):
    """Tier = hardest strategy family the puzzle REQUIRES (family-ordered search)."""
    req, _ = required_techniques(puzzle, P)
    if req is None:
        return "Extreme", []
    fam = max((family_of(t) for t in req), default=0)
    return FAMILY_TIERS[min(fam, len(FAMILY_TIERS) - 1)], [S.TECH_NAMES[t] for t in req]


def report(g, puzzle, P, steps=None, tier_by_family=True):
    """Interpretable summary of a grade() dict (pass steps to grade on the difficulty head)."""
    pts = level(difficulty_grade(steps, P) if steps is not None else g["difficulty"], puzzle.D, P)
    if tier_by_family:
        name, req = family_tier(puzzle, P)
        return {
            "level": round(pts, 1),
            "tier": name,
            "tier_meaning": TIER_MEANING[name],
            "required": req,
            "time_min": round(g["time"] / 60.0, 1),
            "notes_needed": g.get("notes_needed"),
            "hardest": g.get("hardest"),
        }
    t = tier_of(pts)
    required = {name: round(level(d, puzzle.D, P), 1) for name, d in g.get("required", {}).items()}
    return {
        "level": round(pts, 1),
        "tier": t["name"] if t else None,
        "tier_techniques": t["techniques"] if t else None,
        "time_min": round(g["time"] / 60.0, 1),
        "notes_needed": g.get("notes_needed"),
        "hardest": g.get("hardest"),
        "required_levels": required,
    }


# pricing families (the engine's structural groups for features and the family-ordered search), simplest first, from
# the technique registry (data/techniques.csv); inside a family, techniques in registry order
FAMILIES = [(f, [t.id for t in R.techniques() if t.family == f]) for f in R.FAMILIES]
_FAM_OF = {t: k for k, (_, ts) in enumerate(FAMILIES) for t in ts}


def family_of(tech):
    return _FAM_OF.get(tech, 0)


# within-family order for the required-technique search: pattern size / textbook order, so the minimal
# set names the technique a teacher would (Y-Wing, not WXYZ-Wing, when both work); unlisted = 50
SIMPLICITY = {t.name: t.simplicity for t in R.techniques() if t.simplicity is not None}


def required_techniques(puzzle, P):
    """Strategies a solver must know, searched in family order (sudokuwiki-style):
    allow families one at a time (techniques within a family by calibrated level),
    stop at the first set that solves, then drop any technique the solve can do
    without. Returns (sorted technique codes, steps) or (None, [])."""
    from . import cbackend as CB

    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    cp = CB.to_cpuzzle(puzzle)
    T = tiers()
    lv = (T or {}).get("technique_levels", {})
    always = {S.TAKE_NOTES, S.CANONICAL}
    order = []
    for _, ts in FAMILIES:  # simplest pattern first (textbook order), fitted level only breaks ties
        order += sorted(
            (t for t in ts if t in S.TECH_NAMES),
            key=lambda t: (SIMPLICITY.get(S.TECH_NAMES[t], 50), lv.get(S.TECH_NAMES[t], 0.0)),
        )

    def attempt(allowed):
        return CB.solve(puzzle, P, disabled=set(S.TECH_NAMES) - allowed, cpuzzle=cp)

    # whole families first (<= 7 solves), then a binary search for the shortest solving prefix
    # within the first family that solves (solvability is monotone in the allowed set); same
    # result as adding techniques one by one, ~15 solves instead of ~80
    allowed, steps, solved = set(always), [], False
    for k, (_, ts) in enumerate(FAMILIES):
        fam = [t for t in order if family_of(t) == k]
        steps, solved = attempt(allowed | set(fam))
        if solved:
            if k > 0:  # singles always come as a block
                lo, hi = 0, len(fam) - 1  # fam[:hi+1] solves; find the smallest such prefix
                best = steps
                while lo < hi:
                    mid = (lo + hi) // 2
                    st_m, ok = attempt(allowed | set(fam[: mid + 1]))
                    if ok:
                        hi, best = mid, st_m
                    else:
                        lo = mid + 1
                fam, steps = fam[: hi + 1], best
            allowed |= set(fam)
            break
        allowed |= set(fam)
    if not solved:
        return None, []
    disabled = set(S.TECH_NAMES) - allowed
    used = sorted(
        {st.move.feat[0] for st in steps} - always, key=lambda t: (-family_of(t), -lv.get(S.TECH_NAMES[t], 0.0))
    )
    for t in used:
        st2, ok = CB.solve(puzzle, P, disabled=disabled | {t}, cpuzzle=cp)
        if ok:
            disabled |= {t}
            steps = st2
    req = sorted({st.move.feat[0] for st in steps} - always, key=lambda t: (family_of(t), lv.get(S.TECH_NAMES[t], 0.0)))
    return req, steps


def grade_puzzle_checked(puzzle, P, explain=False, time_limit=60.0, tier_by_family=True):
    """Uniqueness-checked grading entry point (use this for any external input).
    1. Independent CP-SAT check: 0 solutions -> {"status": "no solution"};
       2+ -> {"status": "multiple solutions", "solutions": [two examples]}.
    2. Unique -> solve and grade with uniqueness techniques allowed (assume_unique=True).
    3. Unknown (CP-SAT can't express a rule / timed out) -> grade with assume_unique=False,
       so no uniqueness reasoning (UR, BUG+1, ...) is applied to an unproven puzzle.
    Returns {"status", "unique", "grade", "report", "steps"}."""
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
        "report": report(g, puzzle, P, steps=steps, tier_by_family=tier_by_family),
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


def band_label(puzzle, P):
    """(band name, required techniques). The band comes from the band-by-band solve (pencilmark/band_path: Very Easy moves
    until stuck, then Easy, ...; most specific shapes, e.g. a Franken X-Wing is Hard). The technique list is the
    family-ordered minimal set, used for publishing notes."""
    from . import band_path as BP

    bp = BP.band_path(puzzle, P)
    if not bp["solved"]:
        return "beyond engine", None
    req, _ = required_techniques(puzzle, P)
    return bp["band"], (req or [])
