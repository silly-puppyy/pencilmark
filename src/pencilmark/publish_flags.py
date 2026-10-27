"""Common-sense publishing notes ('would not be chosen for publishing'), sudokuwiki-style. Bands never change.

Hand-coded rules (sudoku.coach likes are too sparse and its puzzles human-curated, so
common sense first; the coach analysis only informed the spike rule's direction):
  spike        a Medium+ puzzle whose 3 hardest steps carry more than `spike` (0.6 = 60%) of its effort (warning; enjoyment
               check on LMD ratings and sudoku.coach likes, controlling difficulty: -0.08 / -0.03)
  decorative   a variant rule class that is neither needed for uniqueness nor used by any solve step
  barely_used  a variant rule class used in fewer than `barely_used` (3) steps of the whole solve (a 'Sudoku X' should use its X)
  redundant    a variant rule class the puzzle is unique without, although the solve uses it (soft note)
  trivial      more than `trivial` (0.6 = 60%) of the cells are given (barely a puzzle)
  tedious      Very Easy / Easy but over `tedious` (60) minutes of work (long and routine)
  uniqueness   needs a uniqueness-based technique (UR, BUG, Gurth): relies on assuming a unique solution
  trial        needs trial / forcing chains: computer-strength logic, not a human-friendly finish
Each note is (code, severity, text); severity 'reject' = would not be published, 'note' = informational.
The limits are adjustable (quality_limits): a number replaces a check's limit, false turns the check off.
"""
from . import metrics as MT, solver as S

UNIQUENESS = {"UniqueRectangle", "BUG+1", "GurthSymmetry"}
TRIAL = {"Trial", "ShortTrial", "EitherWay", "WhatIf", "ForcingChains", "DynamicForcingChains",
         "NestedForcingChains", "NishioForcingNet", "PatternOverlay"}
BASE_UNITS = ("row", "col", "box", "column")
QUALITY = {"spike": 0.6, "trivial": 0.6, "tedious": 60, "barely_used": 3,      # numeric limits (GRADE.md 4)
           "decorative": True, "redundant": True, "uniqueness": True, "trial": True}


def quality_limits(q=None):
    """quality object -> every check's limit: a number for spike / trivial / tedious / barely_used (true = the default),
    true / false for the others; false = check off. Raises ValueError for unknown checks or bad values."""
    out = dict(QUALITY)
    for k, v in (q or {}).items():
        if k not in QUALITY:
            raise ValueError(f"unknown quality check {k!r}; known: {list(QUALITY)}")
        numeric = not isinstance(QUALITY[k], bool)
        if isinstance(v, bool):
            out[k] = QUALITY[k] if (v and numeric) else v
        elif numeric and isinstance(v, (int, float)) and v >= 0:
            out[k] = v
        else:
            raise ValueError(f"quality {k} must be " + ("a number >= 0 or true / false" if numeric else "true / false"))
    return out


def _top3_share(puzzle, steps):
    """share of the solve's effort in its 3 hardest steps; effort per step = price^beta x candidate density / moves
    offered, as the card's difficulty"""
    from . import _data
    beta = _data.load_json("card_score.json")["beta"]
    nd = puzzle.N * puzzle.D
    v = []
    for st in steps:
        c = st.n_cands if st.n_cands is not None else nd
        dens = c / 727 * 20 if nd <= 729 else c / nd * 20 * 729 / 727
        v.append(max(float(st.move.d), 1e-3) ** beta * dens / max(len(st.alts), 1))
    v.sort(reverse=True)
    return sum(v[:3]) / sum(v) if v and sum(v) > 0 else 0.0


def notes(puzzle, P, steps, tier, forced, required, work_min, check_rules=True):
    q = quality_limits(P.get("quality"))
    out = []
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    note_techs = getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,))
    mv = [st for st in steps if st.move.feat[0] not in note_techs]
    bi = MT.BANDS.index(tier) if tier in MT.BANDS else -1
    if bi >= 2 and q["spike"] is not False:
        share = _top3_share(puzzle, mv)
        if share > q["spike"]:
            out.append(("spike", "note", f"{share:.0%} of the effort is in the 3 hardest steps"))
    given_share = len(puzzle.givens) / max(puzzle.N, 1)
    if q["trivial"] is not False and given_share > q["trivial"]:
        out.append(("trivial", "reject", f"{given_share:.0%} of the cells are given"))
    if q["tedious"] is not False and bi in (0, 1) and work_min is not None and work_min > q["tedious"]:
        out.append(("tedious", "note", f"{tier} but about {work_min:.0f} min of routine work"))
    req = set(required or [])
    if q["uniqueness"] and req & UNIQUENESS:
        out.append(("uniqueness", "note", "relies on the uniqueness assumption (" + ", ".join(sorted(req & UNIQUENESS)) + ")"))
    if q["trial"] and req & TRIAL:
        out.append(("trial", "note", "needs trial / forcing chains (" + ", ".join(sorted(req & TRIAL)) + ")"))
    if check_rules and (q["decorative"] or q["redundant"] or q["barely_used"] is not False):
        out += [n for n in _rule_notes(puzzle, P, q) if q[n[0]] is not False]
    return out


def _rule_notes(puzzle, P, q=None):
    q = q or quality_limits()
    from . import usage as U
    out = []
    try:
        cls = [c for c in U.element_classes(puzzle) if not any(c.startswith(b) for b in BASE_UNITS)]
        if not cls:
            return out
        use = U.rule_usage(puzzle, P)["counts"]
        need = U.necessity(puzzle, time_limit=20.0)
    except Exception:  # never let the notes break a card
        return out
    # pair relations are often credited under derived labels (chains of signs become detected lines; bounds are
    # reported as "thermo / inequality") -- an x-sums + greater-than card said "lt relation used in only 0 steps" while 8 steps
    # used the signs as a detected line. Relation classes count those labels too.
    rel_aliases = ("line from pair relations", "pair relation", "thermo / inequality", "line / rule", "thermo line",
                   "slow_thermo line", "parity line")
    for c in cls:
        n_used = sum(v for k, v in use.items() if str(k) == c or str(k).startswith(c)
                     or (c.endswith(" relation") and str(k) in rel_aliases))
        needed = need.get(c)
        # (code, severity, text, element class, uses): the card names the rules of the class (export.grade "issues")
        if needed is False and n_used == 0:
            out.append(("decorative", "reject", f"decorative {c}: not needed for uniqueness and never used", c, n_used))
        elif needed is False:
            out.append(("redundant", "note", f"{c} used {n_used}x but the puzzle is unique without it", c, n_used))
        elif q["barely_used"] is not False and n_used < q["barely_used"]:
            out.append(("barely_used", "reject" if n_used == 0 else "note", f"{c} used in only {n_used} step{'s' if n_used != 1 else ''}", c, n_used))
    return out
