"""Human-readable grade card: a label, two numbers, and a row of technique chips.

card = grade_card(puzzle, P)        # uniqueness-checked (metrics.grade_puzzle_checked)

label        family tier of the REQUIRED strategies (metrics.family_tier), with its meaning
difficulty   level of the hardest insight (+ amount of hard reasoning), the difficulty head
tediousness  routine work in minutes (scoring.work_time: every move priced as a Hidden Single)
chips        3-letter technique codes, Andrew Stuart's (sudokuwiki.org solver) where he has the strategy and
             consistent new codes otherwise; shade = family (darker = harder); "x2" = forced
             twice (steps where nothing from an easier family was available)
"""

from collections import Counter

from . import metrics as MT
from . import registry as R
from . import solver as S

# technique name -> (code, display name); sudokuwiki codes where they exist (data/techniques.csv, data/codes.csv)
CODES = {t.name: R.chip(t) for t in R.techniques() if t.code}


def _code(name):
    if name in CODES:
        return CODES[name]
    return (("".join(ch for ch in name if ch.isalpha()).upper() + "XXX")[:3], name)


def forced_counts(steps):
    """technique name -> number of steps where it was chosen and nothing from an easier family was available."""
    out = Counter()
    for st in steps:
        t = st.move.feat[0]
        if t in S.NOTE_TECHS:
            continue
        fam = MT.family_of(t)
        avail = [MT.family_of(f[0]) for f in st.alts if f[0] != S.TAKE_NOTES]
        if fam > 0 and avail and min(avail) >= fam:
            out[S.TECH_NAMES[t]] += 1
    return out


_V2 = None


_LAST_EFFORT = None


def _score_v2(puzzle):
    """Card score (pencilmark/card_score.py, configured by data/card_score.json); None if unavailable. Also leaves the
    effort L1 (log step-value sum, read by the time model) in _LAST_EFFORT."""
    global _V2, _LAST_EFFORT
    from . import _data

    if _V2 is None:
        _V2 = _data.load_json("card_score.json") if _data.exists("card_score.json") else {}
    if not _V2 or _V2.get("version") != 3:
        return None
    from . import card_score as C3

    r = C3.score_parts(puzzle, _V2)
    _LAST_EFFORT = None if r is None else r[1]
    return None if r is None else r[0]


def specific_names(puzzle, steps):
    """engine technique name -> Counter of the explainer's most specific pattern names on its steps
    (only where that name is more specific than the technique's own display name)."""
    from . import explain as E

    out = {}
    hard = {i for i, st in enumerate(steps) if MT.family_of(st.move.feat[0]) > 0 and st.move.feat[0] != S.GUESS}
    if not hard:
        return out
    for i, step, state in E.replay(puzzle, steps):
        if i not in hard:
            continue
        try:
            nm = E.explain(step, puzzle, state)["technique"]["name"]
        except Exception:
            continue
        tn = S.TECH_NAMES[step.move.feat[0]]
        if nm and nm != _code(tn)[1]:
            out.setdefault(tn, Counter())[nm] += 1
    return out


def grade_card(puzzle, P, band, specific=True, check_rules=True):
    g = MT.grade_puzzle_checked(puzzle, P)
    if "steps" not in g:  # no solution / several
        return {"status": g["status"]}
    steps = g["steps"]
    tier, req = band  # band + techniques from the band path (export passes them)
    req = [S.TECH_NAMES.get(t, str(t)) if isinstance(t, int) else t for t in (req or [])]
    forced = forced_counts(steps)
    notes = S.NOTE_TECHS
    used = Counter(S.TECH_NAMES[st.move.feat[0]] for st in steps if st.move.feat[0] not in notes)
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    singles = [n for n in used if MT.family_of(rev[n]) == 0]  # the base everyone uses
    names = list(dict.fromkeys((req or []) + singles))
    chips, seen = [], {}
    for n in names:
        code, disp = _code(n)
        fam = MT.band_of(rev.get(n, 0))
        k = (code, fam)
        if k in seen:
            seen[k]["forced"] += forced.get(n, 0)
            continue
        chip = {
            "code": code,
            "name": disp,
            "family": MT.BANDS[fam],
            "family_i": fam,
            "shade": round(fam / (len(MT.BANDS) - 1), 2),
            "forced": forced.get(n, 0),
            "required": n in (req or []),
        }
        seen[k] = chip
        chips.append(chip)
    chips.sort(key=lambda c: (c["family_i"], c["code"]))
    if specific:  # most specific name of what was actually seen (Skyscraper, W-Wing, Sashimi Swordfish, ...)
        for n, names_ in specific_names(puzzle, steps).items():
            code, _ = _code(n)
            for c in chips:
                if c["code"] == code and names_:
                    c["specific"] = [k for k, _ in names_.most_common()]
    gi = [i for i, st in enumerate(steps) if st.move.feat[0] == S.GUESS]
    # the band path is the user-facing solve: when it finished without guessing, a guess in this route (its forcing budget
    # ran out) does not make the card Unknown -- band and score stay consistent
    if gi and band[0] == "Unknown":  # a guess is not a grade: report where logic ran out
        pre = steps[: gi[0]]
        band = max((MT.band_of(st.move.feat[0]) for st in pre if st.move.feat[0] not in S.NOTE_TECHS), default=0)
        human = (P or {}).get("search") == "human"
        # no available technique can continue: we can't grade it (rated unknown)
        return {
            "status": "beyond human logic" if human else "beyond engine",
            "label": "Unknown",
            "meaning": f"no {'human' if human else 'logical'} step found after {len(pre)} of {len(steps)} steps "
            f"({100 * len(pre) // max(len(steps), 1)}% of the solve); grade unknown",
            "difficulty": None,
            "tediousness_min": None,
            "think_min": None,
            "chips": [c for c in chips if c["code"] != "GSS"],
            "guess_at": len(pre),
        }
    global _LAST_EFFORT
    _LAST_EFFORT = None
    sc_ = _score_v2(puzzle)  # sudokuwiki-form score on the written route (data/card_score.json)
    effort_ = _LAST_EFFORT
    if sc_ is None:
        sc_ = MT.card_score(MT.size_normalised(MT.difficulty_grade(steps, P, cap=False, head=False), puzzle.D, P))
    sc_ = round(sc_, 1) if sc_ is not None else None
    nf = sum(forced.values())
    # sudokuwiki-style publishing notes, hand-coded common sense (pencilmark/publish_flags.py); bands stay fixed
    from . import publish_flags as PF

    wm = g["grade"]["work_time"] / 60 if g.get("grade") else None
    pnotes = PF.notes(puzzle, P, steps, tier, forced, req, wm, check_rules=check_rules)
    flags = [
        ("would not be chosen for publishing: " if sev == "reject" else "note: ") + txt for code, sev, txt, *_ in pnotes
    ]
    shape = (
        "singles only" if nf == 0 else ("spike" if nf <= 2 else "sustained")
    )  # balance: label resting on 1-2 forced steps
    from .scoring import time_grade

    tg = time_grade(steps, puzzle, P)
    real = [st for st in steps if st.move.feat[0] not in notes]
    hardest = [
        {
            "technique": S.TECH_NAMES[st.move.feat[0]],
            "price": round(st.move.d, 2),
            "step": i + 1,
            "place": (
                f"r{puzzle.coords[st.move.place[0]][0] + 1}c{puzzle.coords[st.move.place[0]][1] + 1}={st.move.place[1]}"
                if st.move.place
                else None
            ),
        }
        for i, st in sorted(enumerate(real), key=lambda x: -x[1].move.d)[:3]
    ]
    return {
        "status": g["status"],
        "label": tier,
        "meaning": MT.BAND_MEANING.get(tier, ""),
        "balance": shape,
        "forced_total": nf,
        "time_grade": tg,
        "techniques": dict(used.most_common()),
        "hardest_steps": hardest,
        "n_steps": len(real),
        "score": sc_,
        "effort_l1": round(effort_, 3) if effort_ is not None else None,
        "score_fit": MT.score_fit(MT.BANDS.index(tier), sc_) if (sc_ is not None and tier in MT.BANDS) else "",
        "flags": flags,
        "tediousness_min": round(g["grade"]["work_time"] / 60, 1),
        "think_min": round(g["grade"]["think_time"] / 60, 1),
        "chips": chips,
        "_notes_raw": pnotes,
    }
