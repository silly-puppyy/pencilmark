"""Common-sense publishing notes ('would not be chosen for publishing'), Stuart-style. Bands never change.

Hand-coded rules (user decision 2026-10-11: sudoku.coach likes are too sparse and its puzzles human-curated, so
common sense first; the coach analysis only informed the spike rule's direction):
  spike        a Hard+ puzzle that rests on 1-2 band-level moves with an otherwise all-singles solve
  decorative   a variant rule class that is neither needed for uniqueness nor used by any solve step
  barely used  a variant rule class used in fewer than 3 steps of the whole solve (a 'Sudoku X' should use its X)
  redundant    a variant rule class the puzzle is unique without, although the solve uses it (soft note)
  trivial      more than 60% of the cells are given (barely a puzzle)
  tedious      Very Easy / Easy but over an hour of work (long and routine)
  uniqueness   needs a uniqueness-based technique (UR, BUG, Gurth): relies on assuming a unique solution
  trial        needs trial / forcing chains: computer-strength logic, not a human-friendly finish
Each note is (code, severity, text); severity 'reject' = would not be published, 'note' = informational.
"""
from . import metrics as MT, solver as S

UNIQUENESS = {"UniqueRectangle", "BUG+1", "GurthSymmetry"}
TRIAL = {"Trial", "ShortTrial", "EitherWay", "WhatIf", "ForcingChains", "DynamicForcingChains",
         "NestedForcingChains", "NishioForcingNet", "PatternOverlay"}
BASE_UNITS = ("row", "col", "box", "column")


def notes(puzzle, P, steps, tier, forced, required, work_min, check_rules=True):
    out = []
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    note_techs = getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,))
    mv = [st for st in steps if st.move.feat[0] not in note_techs]
    ss = sum(1 for st in mv if MT.family_of(st.move.feat[0]) == 0) / max(len(mv), 1)
    bi = MT.BANDS.index(tier) if tier in MT.BANDS else -1
    if bi >= 3:
        at_band = sum(v for n, v in forced.items() if MT.band_of(rev[n]) == bi)
        if ss >= 0.95 and at_band <= 2:
            out.append(("spike", "reject", f"{tier} rests on {at_band} {tier.lower()} move{'s' if at_band != 1 else ''}, "
                                           f"otherwise {ss:.0%} singles"))
    given_share = len(puzzle.givens) / max(puzzle.N, 1)
    if given_share > 0.60:
        out.append(("trivial", "reject", f"{given_share:.0%} of the cells are given"))
    if bi in (0, 1) and work_min is not None and work_min > 60:
        out.append(("tedious", "note", f"{tier} but about {work_min:.0f} min of routine work"))
    req = set(required or [])
    if req & UNIQUENESS:
        out.append(("uniqueness", "note", "relies on the uniqueness assumption (" + ", ".join(sorted(req & UNIQUENESS)) + ")"))
    if req & TRIAL:
        out.append(("trial", "note", "needs trial / forcing chains (" + ", ".join(sorted(req & TRIAL)) + ")"))
    if check_rules:
        out += _rule_notes(puzzle, P)
    return out


def _rule_notes(puzzle, P):
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
    # 2026-10-25: pair relations are often credited under derived labels (chains of signs become detected lines; bounds are
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
        elif n_used < 3:
            out.append(("barely used", "reject" if n_used == 0 else "note", f"{c} used in only {n_used} step{'s' if n_used != 1 else ''}", c, n_used))
    return out
