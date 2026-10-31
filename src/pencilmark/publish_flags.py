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
Every check is adjustable with an object (quality_limits): {"limit": n} replaces its limit (checks with one), {"severity":
"reject" | "warning" | "off"} overrides its severity or turns it off.
"""

from . import metrics as MT
from . import solver as S

UNIQUENESS = {"UniqueRectangle", "BUG+1", "GurthSymmetry"}
TRIAL = {
    "Trial",
    "ShortTrial",
    "EitherWay",
    "WhatIf",
    "ForcingChains",
    "DynamicForcingChains",
    "NestedForcingChains",
    "NishioForcingNet",
    "PatternOverlay",
}
BASE_UNITS = ("row", "col", "box", "column")
QUALITY = {
    "spike": 0.6,
    "trivial": 0.6,
    "tedious": 60,
    "barely_used": 3,  # default limits (GRADE.md 4); None: no limit
    "decorative": None,
    "redundant": None,
    "uniqueness": None,
    "trial": None,
}
SEVERITIES = ("reject", "warning", "off")


def quality_limits(q=None):
    """quality object -> {check: {"limit": number or None, "severity": "reject" | "warning" | "off" | None}} for every check.
    Each entry of q is an object with "limit" (checks with a limit: a number >= 0) and / or "severity"; severity None =
    the check's own (GRADE.md 4). Raises ValueError for unknown checks, keys or values."""
    out = {k: {"limit": v, "severity": None} for k, v in QUALITY.items()}
    for k, v in (q or {}).items():
        if k not in QUALITY:
            raise ValueError(f"unknown quality check {k!r}; known: {list(QUALITY)}")
        if not isinstance(v, dict) or not v or set(v) - {"limit", "severity"}:
            raise ValueError(
                f'quality {k} must be an object with "limit" and / or "severity", e.g. {{"severity": "off"}}'
            )
        if "limit" in v:
            lim = v["limit"]
            if QUALITY[k] is None:
                raise ValueError(f'quality {k} has no limit; it takes only "severity"')
            if isinstance(lim, bool) or not isinstance(lim, (int, float)) or lim < 0:
                raise ValueError(f"quality {k} limit must be a number >= 0")
            out[k]["limit"] = lim
        if "severity" in v:
            if v["severity"] not in SEVERITIES:
                raise ValueError(f"quality {k} severity must be one of {list(SEVERITIES)}")
            out[k]["severity"] = v["severity"]
    return out


def _apply_severity(notes, q):
    """the user's severity per check: "off" drops the note, "reject" / "warning" replace the check's own"""
    out = []
    for n in notes:
        sev = q[n[0]]["severity"]
        if sev == "off":
            continue
        if sev is not None:
            n = (n[0], "reject" if sev == "reject" else "note") + tuple(n[2:])
        out.append(n)
    return out


def _top3_share(puzzle, steps):
    """share of the solve's effort in its 3 hardest steps; effort per step = price^beta x candidate density / moves
    offered, as the card's difficulty"""

    from . import grader_model as GM

    beta = GM.default().score["beta"]
    nd = puzzle.N * puzzle.D
    v = []
    for st in steps:
        c = st.n_cands if st.n_cands is not None else nd
        dens = c / 727 * 20 if nd <= 729 else c / nd * 20 * 729 / 727
        v.append(max(float(st.move.d), 1e-3) ** beta * dens / max(len(st.alts), 1))
    v.sort(reverse=True)
    return sum(v[:3]) / sum(v) if v and sum(v) > 0 else 0.0


class _Ctx:
    """what the checks read: the puzzle, its steps (pencil-mark steps left out), band, required techniques, routine
    work in minutes, and the quality object (limits and severities)"""

    def __init__(self, puzzle, P, steps, tier, required, work_min, q):
        self.puzzle, self.P, self.tier, self.work_min, self.q = puzzle, P, tier, work_min, q
        self.moves = [st for st in steps if st.move.feat[0] not in S.NOTE_TECHS]
        self.band_i = MT.BANDS.index(tier) if tier in MT.BANDS else -1
        self.required = set(required or [])

    def lim(self, k):
        return self.q[k]["limit"]


def _c_spike(c):
    if c.band_i >= 2:
        share = _top3_share(c.puzzle, c.moves)
        if share > c.lim("spike"):
            return [("spike", "note", f"{share:.0%} of the effort is in the 3 hardest steps")]
    return []


def _c_trivial(c):
    given_share = len(c.puzzle.givens) / max(c.puzzle.N, 1)
    return (
        [("trivial", "reject", f"{given_share:.0%} of the cells are given")] if given_share > c.lim("trivial") else []
    )


def _c_tedious(c):
    if c.band_i in (0, 1) and c.work_min is not None and c.work_min > c.lim("tedious"):
        return [("tedious", "note", f"{c.tier} but about {c.work_min:.0f} min of routine work")]
    return []


def _c_uniqueness(c):
    hit = c.required & UNIQUENESS
    return (
        [("uniqueness", "note", "relies on the uniqueness assumption (" + ", ".join(sorted(hit)) + ")")] if hit else []
    )


def _c_trial(c):
    hit = c.required & TRIAL
    return [("trial", "note", "needs trial / forcing chains (" + ", ".join(sorted(hit)) + ")")] if hit else []


# the check registry (GRADE.md 4), in the order notes are reported: check -> the quality codes it can raise. The rule
# checks (decorative, redundant, barely_used) share one pass over the rule families (_rule_notes) and come last.
CHECKS = [
    (_c_spike, ("spike",)),
    (_c_trivial, ("trivial",)),
    (_c_tedious, ("tedious",)),
    (_c_uniqueness, ("uniqueness",)),
    (_c_trial, ("trial",)),
]
RULE_CODES = ("decorative", "redundant", "barely_used")


def notes(puzzle, P, steps, tier, required, work_min, check_rules=True):
    """the publishing notes [(code, severity, text, ...)] of a graded puzzle, as the quality object asks"""
    q = quality_limits(P.get("quality"))
    on = lambda codes: any(q[k]["severity"] != "off" for k in codes)
    c = _Ctx(puzzle, P, steps, tier, required, work_min, q)
    out = [n for check, codes in CHECKS if on(codes) for n in check(c)]
    if check_rules and on(RULE_CODES):
        out += _rule_notes(puzzle, P, q)
    return _apply_severity(out, q)


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
    rel_aliases = (
        "line from pair relations",
        "pair relation",
        "thermo / inequality",
        "line / rule",
        "thermo line",
        "slow_thermo line",
        "parity line",
    )
    for c in cls:
        n_used = sum(
            v
            for k, v in use.items()
            if str(k) == c or str(k).startswith(c) or (c.endswith(" relation") and str(k) in rel_aliases)
        )
        needed = need.get(c)
        # (code, severity, text, element class, uses): the card names the rules of the class (export.grade "issues")
        if needed is False and n_used == 0:
            out.append(("decorative", "reject", f"decorative {c}: not needed for uniqueness and never used", c, n_used))
        elif needed is False:
            out.append(("redundant", "note", f"{c} used {n_used}x but the puzzle is unique without it", c, n_used))
        elif q["barely_used"]["severity"] != "off" and n_used < q["barely_used"]["limit"]:
            out.append(
                (
                    "barely_used",
                    "reject" if n_used == 0 else "note",
                    f"{c} used in only {n_used} step{'s' if n_used != 1 else ''}",
                    c,
                    n_used,
                )
            )
    return out
