"""Common-sense publishing notes ('would not be chosen for publishing'), sudokuwiki-style. Bands never change.

Hand-coded rules, each checked against published puzzles (docs/research/quality_metrics.md):
  thin         a Medium+ puzzle whose candidate (non-single) steps carry less than `thin` (0.25 = 25%) of its effort: the
               hard step changes little and the rest is singles (Andrew Stuart's "too few candidates removed using
               candidate strategies"); published Hard puzzles: 10th percentile 0.26 (fed / coach), 0.28 (Stuart); our
               generator's puzzles sit well below unbiased ones (warning)
  decorative   a variant rule class that is neither needed for uniqueness nor used by any solve step
  barely_used  a variant rule class used in fewer than `barely_used` (3) steps of the whole solve (a 'Sudoku X' should use its X)
  redundant    a variant rule class the puzzle is unique without, although the solve uses it (soft note)
  trivial      more than `trivial` (0.6 = 60%) of the cells are given (barely a puzzle)
  tedious      Very Easy / Easy but over `tedious` (60) minutes of work (long and routine)
  uniqueness   needs a uniqueness-based technique (UR, BUG, Gurth): relies on assuming a unique solution
  trial        needs trial / forcing chains: computer-strength logic, not a human-friendly finish
  unusual      a difficulty outside the middle 80% of published puzzles of the same band (classic 9x9 and variants
               apart, TYPICAL; Very Easy has no floor, Extreme no ceiling): a Very Easy puzzle that scans like an Easy
               one, a Medium that plays like a Very Hard (reject)
Opt-in checks (off unless the quality object sets their severity or limit; limits near the edge of published Medium+
puzzles, 1,221 from LMD, sudoku.coach, Puzzle Duel, fed and others, quality study 2026-11-06; share of 165 published
Medium+ dev puzzles flagged: monotone 27%, asymmetric 25%, desert 8%, others 1-4%):
  asymmetric   the givens pattern has no symmetry (62% of published Medium+ classics have one)
  no_interplay a variant with two or more rule families that share fewer than `no_interplay` (1) cells
  winding      lines turn at more than `winding` (0.9) of their inner cells on average (published p90 0.91)
  short_lines  lines average fewer than `short_lines` (3) cells (published p10 3.0)
  repetitive   one technique makes more than `repetitive` (0.75) of a Medium+ solve's candidate steps (at least 4)
  monotone     a Medium+ solve's candidate steps come from fewer than `monotone` (2) technique families
  desert       after the first candidate step, a run of singles longer than `desert` (0.8) of the solve
  late_break   a Medium+ solve's first candidate step comes after `late_break` (0.6) of the solve
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
    "thin": 0.25,
    "trivial": 0.6,
    "tedious": 60,
    "barely_used": 3,  # default limits (docs/formats/grade-card.md 4); None: no limit
    "decorative": None,
    "redundant": None,
    "uniqueness": None,
    "trial": None,
    "unusual": None,
    "asymmetric": None,
    "no_interplay": 1,
    "winding": 0.9,
    "short_lines": 3,
    "repetitive": 0.75,
    "monotone": 2,
    "desert": 0.8,
    "late_break": 0.6,
}
OPT_IN = ("asymmetric", "no_interplay", "winding", "short_lines", "repetitive", "monotone", "desert", "late_break")
# difficulty of published puzzles per band: (10th, 90th percentile), classic 9x9 and variants apart. Measured
# 2026-11-06 (1.2 engine: coloring on, round counting) on the v12 development set (7,253 puzzles with human data from
# seven sources, 7,155 graded; never the frozen benchmark); a band with fewer than 20 puzzles has no range.
# docs/guides/generator/generate.md shows the middle halves.
# Very Easy has no floor and Extreme no ceiling (nothing is too easy or too hard for them)
TYPICAL = {
    "classic": {"Very Easy": (None, 4.6), "Easy": (4.4, 6.4), "Medium": (6.0, 7.2),
                "Hard": (5.2, 7.0), "Very Hard": (6.6, 8.2), "Expert": (7.3, 11.3)},
    "variant": {"Very Easy": (None, 5.9), "Easy": (4.7, 8.5), "Medium": (6.5, 10.9),
                "Hard": (5.2, 9.8), "Very Hard": (8.3, 13.8), "Expert": (8.5, 14.1)},
}  # fmt: skip
# where a band request without a difficulty aims (the generator, gen/api.py band_aim): (mean, sd, low, high) of
# difficulty, a normal draw clipped to [low, high]. Classic: fed-sudoku.eu, sudoku.coach classics and Wang 2024 on the
# v12 development set (1.2 engine, 2026-11-07), except Very Easy: there the curated sources sit at 4.1, the top of the
# band, while generated sites' easy tiers sit lower (sudoku.com easy / medium / hard 2.5 / 3.1 / 3.6, 300 each) and
# the user's reference for other sites' Very Easy is 2.7-3.9: centered 3.3 in that range. 9x9 variants: the development
# set's variant9 groups. Bands with fewer than 20 puzzles have none (the generator then digs as far as the band allows).
AIM = {
    "classic": {"Very Easy": (3.3, 0.45, 2.7, 3.9), "Easy": (5.41, 0.73, 4.4, 6.4), "Medium": (6.68, 0.43, 6.1, 7.2),
                "Hard": (6.15, 0.72, 5.3, 7.1), "Very Hard": (7.29, 0.85, 6.6, 7.8), "Expert": (9.23, 1.53, 7.5, 11.5)},
    "variant": {"Very Easy": (5.58, 0.69, 5.0, 6.2), "Easy": (7.51, 1.29, 5.7, 8.8), "Medium": (9.32, 1.39, 7.6, 11.2),
                "Hard": (7.90, 1.41, 6.2, 9.3), "Very Hard": (10.95, 2.26, 7.8, 13.9), "Expert": (10.88, 1.56, 9.2, 13.0)},
}  # fmt: skip
SEVERITIES = ("reject", "warning", "off")
# presets (quality {"preset": name}): only these checks are on, at these severities (None: the check's own);
# everything else is off; any check named next to the preset overrides it. standard = a few common-sense rules
# (decorative, trivial, trial) and two supported by published puzzles (thin: published Hard rarely below 0.26;
# unusual: outside the published range). relaxed = the same five, thin and unusual as warnings. default = every check that is not opt in, at its own severity: what rate()
# runs when asked for issues without a quality object
PRESETS = {
    "standard": {"decorative": "reject", "trivial": "reject", "trial": "reject", "thin": "reject", "unusual": "reject"},
    # relaxed: the common-sense rejects only; the two checks measured on published puzzles (thin, unusual) warn. On
    # published development puzzles (2026-11-08) standard rejects 19% of classics (unusual 17%, thin 2%) and 12% of
    # variants; relaxed rejects under 1% of classics and 4% of variants
    "relaxed": {"decorative": "reject", "trivial": "reject", "trial": "reject", "thin": "warning", "unusual": "warning"},
    "default": {k: None for k in QUALITY if k not in OPT_IN},
}


def quality_limits(q=None):
    """quality object -> {check: {"limit": number or None, "severity": "reject" | "warning" | "off" | None}} for every check.
    One meaning everywhere (docs/formats/grade-card.md 4): None = the "default" preset (rate() asked for issues without
    a quality object); {} = no checks; a preset turns on its checks; without a preset only the checks named run. Each
    entry is an object with "limit" (checks with a limit: a number >= 0) and / or "severity"; severity None = the
    check's own. Raises ValueError for unknown checks, keys or values."""
    out = {k: {"limit": v, "severity": "off"} for k, v in QUALITY.items()}
    if q is not None and not isinstance(q, dict):
        raise ValueError(f'quality must be an object of checks, e.g. {{"trivial": {{"severity": "off"}}}}, got {q!r}')
    q = {"preset": "default"} if q is None else dict(q)
    if "preset" in q:
        name = q.pop("preset")
        if name not in PRESETS:
            raise ValueError(f"unknown quality preset {name!r}; known: {list(PRESETS)}")
        for k in out:
            out[k]["severity"] = PRESETS[name].get(k, "off")
    for k, v in q.items():
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
        if "severity" not in v and out[k]["severity"] == "off":
            out[k]["severity"] = None  # naming a check turns it on, at its own severity
        if "severity" in v:
            if v["severity"] not in SEVERITIES:
                raise ValueError(f"quality {k} severity must be one of {list(SEVERITIES)}")
            out[k]["severity"] = v["severity"]
    return out


def spec_quality(q):
    """a generator spec's quality block -> the quality object its candidates are graded with, or None (no checks).
    Quality is opt in: no block or {} runs nothing; otherwise the object means what it means in rate()
    (quality_limits; docs/formats/generator-spec.md 4)"""
    return dict(q) if q else None


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


def _thin_share(puzzle, steps):
    """share of the solve's effort in its candidate (non-single) steps; effort per step = price^beta x candidate
    density / moves offered, as the card's difficulty"""

    from . import grader_model as GM

    beta = GM.default().score["beta"]
    nd = puzzle.N * puzzle.D
    v = []
    for st in steps:
        c = st.n_cands if st.n_cands is not None else nd
        dens = c / 727 * 20 if nd <= 729 else c / nd * 20 * 729 / 727
        name = S.TECH_NAMES.get(st.move.feat[0], "")
        single = "Single" in name or name == "FullHouse"
        v.append((max(float(st.move.d), 1e-3) ** beta * dens / max(len(st.alts), 1), single))
    tot = sum(x for x, _ in v)
    return sum(x for x, s in v if not s) / tot if tot > 0 else 0.0


class _Ctx:
    """what the checks read: the puzzle, its steps (pencil-mark steps left out), band, required techniques, routine
    work in minutes, and the quality object (limits and severities)"""

    def __init__(self, puzzle, P, steps, tier, required, work_min, q, difficulty=None):
        self.puzzle, self.P, self.tier, self.work_min, self.q = puzzle, P, tier, work_min, q
        self.difficulty = difficulty
        self.moves = [st for st in steps if st.move.feat[0] not in S.NOTE_TECHS]
        self.band_i = MT.BANDS.index(tier) if tier in MT.BANDS else -1
        self.required = set(required or [])

    def lim(self, k):
        return self.q[k]["limit"]


def _c_thin(c):
    if c.band_i >= 2:
        share = _thin_share(c.puzzle, c.moves)
        if share < c.lim("thin"):
            return [("thin", "note", f"candidate steps carry only {share:.0%} of the effort; the rest is singles")]
    return []


def _c_trivial(c):
    given_share = (len(c.puzzle.givens) - len(getattr(c.puzzle, "placed", None) or ())) / max(c.puzzle.N, 1)
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


def _c_unusual(c):
    if c.difficulty is None:
        return []
    from .interop import is_classic9

    if c.puzzle.D != 9 or c.puzzle.N != 81:  # the ranges were measured on 9x9 puzzles: no range for other sizes
        return []
    kind = "classic" if is_classic9(c.puzzle) else "variant"
    lo_hi = TYPICAL[kind].get(c.tier)
    if lo_hi is None:
        return []
    lo, hi = lo_hi
    if (lo is None or c.difficulty >= lo) and (hi is None or c.difficulty <= hi):
        return []
    what = "classics" if kind == "classic" else "variants"
    rng = f"up to {hi:g}" if lo is None else f"{lo:g} and above" if hi is None else f"{lo:g} to {hi:g}"
    return [("unusual", "reject", f"{c.tier} at difficulty {c.difficulty:g}: most published {c.tier} {what} are {rng}")]


def _c_trial(c):
    hit = c.required & TRIAL
    return [("trial", "note", "needs trial / forcing chains (" + ", ".join(sorted(hit)) + ")")] if hit else []


def _candidate_steps(c):
    """technique names of the solve's non-single steps, and the position of each step (0..1) along the solve"""
    names = [S.TECH_NAMES.get(st.move.feat[0], "") for st in c.moves]
    single = ["Single" in k or k == "FullHouse" for k in names]
    return names, single


def _c_asymmetric(c):
    from .export import symmetry_of

    return [] if symmetry_of(c.puzzle) else [("asymmetric", "note", "the givens pattern has no symmetry")]


def _families_cells(p):
    """rule family -> the cells its rules cover (lines, cages, dots, ...; the n-ary parts of lines count with their line)"""
    fam = {}
    for k in getattr(p, "constraints", ()) or ():
        if k.get("line_kind") or not k.get("cells"):
            continue
        fam.setdefault(f"{k.get('type')}:{k.get('kind') or ''}", set()).update(k["cells"])
    return fam


def _c_no_interplay(c):
    fam = list(_families_cells(c.puzzle).values())
    if len(fam) < 2:
        return []
    shared = set()
    for i, a in enumerate(fam):
        for b in fam[i + 1 :]:
            shared |= a & b
    if len(shared) < c.lim("no_interplay"):
        return [("no_interplay", "note", f"{len(fam)} rule families share only {len(shared)} cells")]
    return []


def _lines(p):
    co = p.coords
    return [[tuple(co[i]) for i in k["cells"]] for k in getattr(p, "constraints", ()) or () if k.get("type") == "line"]


def _c_winding(c):
    t = []
    for rc in _lines(c.puzzle):
        if len(rc) >= 3:
            d = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(rc, rc[1:])]
            t.append(sum(x != y for x, y in zip(d, d[1:])) / (len(rc) - 2))
    if t and sum(t) / len(t) > c.lim("winding"):
        return [("winding", "note", f"lines turn at {sum(t) / len(t):.0%} of their inner cells")]
    return []


def _c_short_lines(c):
    L = [len(rc) for rc in _lines(c.puzzle)]
    if L and sum(L) / len(L) < c.lim("short_lines"):
        return [("short_lines", "note", f"lines average {sum(L) / len(L):.1f} cells")]
    return []


def _c_repetitive(c):
    names, single = _candidate_steps(c)
    ns = [k for k, s in zip(names, single) if not s]
    if c.band_i >= 2 and len(ns) >= 4:
        top = max(set(ns), key=ns.count)
        if ns.count(top) / len(ns) > c.lim("repetitive"):
            return [("repetitive", "note", f"{top} makes {ns.count(top) / len(ns):.0%} of the candidate steps")]
    return []


def _c_monotone(c):
    from . import registry as R

    names, single = _candidate_steps(c)
    fam = {t.name: t.family for t in R.techniques()}
    fams = {fam.get(k) or k for k, s in zip(names, single) if not s}
    if c.band_i >= 2 and fams and len(fams) < c.lim("monotone"):
        return [
            ("monotone", "note", f"candidate steps from {len(fams)} technique famil{'y' if len(fams) == 1 else 'ies'}")
        ]
    return []


def _c_desert(c):
    names, single = _candidate_steps(c)
    first = next((i for i, s in enumerate(single) if not s), None)
    if first is None:
        return []
    run = best = 0
    for s in single[first + 1 :]:
        run = run + 1 if s else 0
        best = max(best, run)
    if best / max(len(single), 1) > c.lim("desert"):
        return [
            (
                "desert",
                "note",
                f"{best} singles in a row ({best / len(single):.0%} of the solve) after the first candidate step",
            )
        ]
    return []


def _c_late_break(c):
    names, single = _candidate_steps(c)
    first = next((i for i, s in enumerate(single) if not s), None)
    if c.band_i >= 2 and first is not None and first / max(len(single) - 1, 1) > c.lim("late_break"):
        return [
            (
                "late_break",
                "note",
                f"the first candidate step comes at {first / max(len(single) - 1, 1):.0%} of the solve",
            )
        ]
    return []


# the check registry (docs/formats/grade-card.md 4), in the order notes are reported: check -> the quality codes it can raise. The rule
# checks (decorative, redundant, barely_used) share one pass over the rule families (_rule_notes) and come last.
CHECKS = [
    (_c_thin, ("thin",)),
    (_c_trivial, ("trivial",)),
    (_c_tedious, ("tedious",)),
    (_c_uniqueness, ("uniqueness",)),
    (_c_trial, ("trial",)),
    (_c_unusual, ("unusual",)),
    (_c_asymmetric, ("asymmetric",)),
    (_c_no_interplay, ("no_interplay",)),
    (_c_winding, ("winding",)),
    (_c_short_lines, ("short_lines",)),
    (_c_repetitive, ("repetitive",)),
    (_c_monotone, ("monotone",)),
    (_c_desert, ("desert",)),
    (_c_late_break, ("late_break",)),
]
RULE_CODES = ("decorative", "redundant", "barely_used")


def notes(puzzle, P, steps, tier, required, work_min, check_rules=True, difficulty=None):
    """the publishing notes [(code, severity, text, ...)] of a graded puzzle, as the quality object asks"""
    q = quality_limits(P.get("quality"))
    on = lambda codes: any(q[k]["severity"] != "off" for k in codes)
    c = _Ctx(puzzle, P, steps, tier, required, work_min, q, difficulty)
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
    # used the signs as a detected line. Relation classes count those labels too, except different-digit links
    # (anti-knight ...), which no line stands for.
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
            if str(k) == c
            or str(k).startswith(c)
            or (c.endswith(" relation") and c != "neq relation" and str(k) in rel_aliases)
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
