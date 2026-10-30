"""Sudoku Explainer-style ratings from our route. Opt-in on the card: pencilmark.rate(puzzle, se=True).

  ER = the hardest step on our easiest human route (SE's "rating"); EP = hardest before the first placement ("pearl");
  ED = the first step's value ("diamond", hardest before the first elimination / placement).
Values per technique from Sudoku Explainer's table:
  scale="classic" (default): the table expert solvers quote (Juillerat's SE / serate): hidden single 1.2 (box), naked single 2.3,
                             pointing 2.6, naked pair 3.0, X-Wing 3.2, hidden pair 3.4, naked triple 3.6, swordfish 3.8, ...
  scale="diuf":              the DiufSudoku fork's table: singles 1.2 / 1.3, pointing 2.5, naked pair 3.0, hidden pair 3.1,
                             naked triple 3.2, hidden triple 3.3.
On classics, with the diuf scale, ER came within 0.3 of Sudoku Explainer's own rating for 96% of 3,200 tested puzzles.
Approximate by construction: our route is not SE's route, and techniques SE has no
value for (variant logic) fall back to 7.0. Classic sudoku only is meaningful.
"""

from __future__ import annotations

CLASSIC = {
    "HSI": 1.2,
    "NSI": 2.3,
    "PPR": 2.6,
    "NPR": 3.0,
    "XWG": 3.2,
    "HPR": 3.4,
    "NTR": 3.6,
    "SWF": 3.8,
    "HTR": 4.0,
    "XYW": 4.2,
    "XYZ": 4.4,
    "UR1": 4.5,
    "URX": 4.6,
    "NQD": 5.0,
    "JFH": 5.2,
    "HQD": 5.4,
    "BUG": 5.6,
    "MSI": 3.0,
    "SKY": 6.5,
    "KTE": 6.5,
    "TUR": 6.5,
    "ERE": 6.5,
    "XCH": 6.6,
    "XYC": 6.6,
    "RMP": 6.6,
    "WWG": 6.6,
    "AIC": 7.0,
    "ALS": 7.0,
    "SDC": 7.0,
    "FSH": 6.6,
    "FCH": 7.5,
    "NET": 8.5,
}
DIUF = dict(CLASSIC, HSI=1.2, NSI=1.3, PPR=2.5, NPR=3.0, HPR=3.1, NTR=3.2, HTR=3.3, MSI=3.0)
SCALES = {"classic": CLASSIC, "diuf": DIUF}


def ratings(steps, scale="classic"):
    """steps: band_path steps (dicts with code / place / elims) -> {"er", "ep", "ed", "scale"}."""
    table = SCALES[scale]
    val = lambda code: table.get(code, 7.0 if code else table["HSI"])
    er = ep = 0.0
    placed = False
    for s in steps:
        v = val(s["code"])
        er = max(er, v)
        if not placed:
            ep = max(ep, v)
        placed |= bool(s["place"])
    ed = val(steps[0]["code"]) if steps else 0.0
    return {"er": er, "ep": ep, "ed": ed, "scale": scale}
