"""Grading helpers over the engine's steps: the uniqueness-checked solve (grade_puzzle_checked), the pricing families
and the user-facing bands (Very Easy .. Extreme, data/techniques.csv)."""

from . import registry as R
from . import solver as S

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
