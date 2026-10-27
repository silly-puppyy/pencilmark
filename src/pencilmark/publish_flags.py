"""Common-sense publishing notes ('would not be chosen for publishing'), sudokuwiki-style. Bands never change.

Hand-coded rules (sudoku.coach likes are too sparse and its puzzles human-curated, so
common sense first; the coach analysis only informed the spike rule's direction):
  spike        a Hard+ puzzle that rests on at most `spike` (2) band-level moves with an otherwise all-singles solve
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
QUALITY = {"spike": 2, "trivial": 0.6, "tedious": 60, "barely_used": 3,      # numeric limits (GRADE.md 4)
           "decorative": True, "redundant": True, "uniqueness": True, "trial": True}
SPIKE_SINGLES = 0.95        # a spike's solve is otherwise at least this share singles


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


def notes(puzzle, P, steps, tier, forced, required, work_min, check_rules=True):
    q = quality_limits(P.get("quality"))
    out = []
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    note_techs = getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,))
    mv = [st for st in steps if st.move.feat[0] not in note_techs]
    ss = sum(1 for st in mv if MT.family_of(st.move.feat[0]) == 0) / max(len(mv), 1)
    bi = MT.BANDS.index(tier) if tier in MT.BANDS else -1
    if bi >= 3 and q["spike"] is not False:
        at_band = sum(v for n, v in forced.items() if MT.band_of(rev[n]) == bi)
        if ss >= SPIKE_SINGLES and at_band <= q["spike"]:
            out.append(("spike", "reject", f"{tier} rests on {at_band} {tier.lower()} move{'s' if at_band != 1 else ''}, "
                                           f"otherwise {ss:.0%} singles"))
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
