"""The card route: difficulty and time effort on the written route, and the publishing notes, for export.grade.

card = grade_card(puzzle, P, band)      # band = (band name, required techniques) from the band path

Returns {"status", "score", "effort_l1", "notes"}: score is the card's difficulty (card_score.score_parts, with the
grader model), effort_l1 the log step-value sum the time model reads, notes the publishing checks
(publish_flags.notes). score and effort_l1 are None when the route cannot grade the puzzle.
"""

from . import metrics as MT
from . import registry as R
from . import solver as S

# technique name -> (code, display name); sudokuwiki codes where they exist (data/techniques.csv, data/codes.csv)
CODES = {t.name: R.chip(t) for t in R.techniques() if t.code}


def _code(name):
    if name in CODES:
        return CODES[name]
    return (("".join(ch for ch in name if ch.isalpha()).upper() + "XXX")[:3], name)


def grade_card(puzzle, P, band, check_rules=True):
    g = MT.grade_puzzle_checked(puzzle, P)
    if "steps" not in g:  # no solution / several
        return {"status": g["status"]}
    steps = g["steps"]
    tier, req = band  # band + techniques from the band path (export passes them)
    req = [S.TECH_NAMES.get(t, str(t)) if isinstance(t, int) else t for t in (req or [])]
    # the band path is the user-facing solve: when it finished without guessing, a guess in this route (its forcing budget
    # ran out) does not make the card Unknown -- band and score stay consistent
    if tier == "Unknown" and any(st.move.feat[0] == S.GUESS for st in steps):
        human = (P or {}).get("search") == "human"
        return {"status": "beyond human logic" if human else "beyond engine", "score": None, "effort_l1": None}
    from . import card_score as C3

    r = C3.score_parts(puzzle)  # difficulty and time effort on the written route; None if it cannot grade
    score, effort = r if r is not None else (None, None)
    from . import publish_flags as PF

    work_min = g["grade"]["work_time"] / 60 if g.get("grade") else None
    return {
        "status": g["status"],
        "score": round(score, 1) if score is not None else None,
        "effort_l1": round(effort, 3) if effort is not None else None,
        "notes": PF.notes(puzzle, P, steps, tier, req, work_min, check_rules=check_rules),
    }
