"""Sudoku Explainer-style ratings from our route. Opt-in on the card: pencilmark.rate(puzzle, se=True).

  ER = the hardest step on our easiest human route (SE's "rating"); EP = hardest before the first placement ("pearl");
  ED = the first step's value ("diamond", hardest before the first elimination / placement).
Values per technique from Sudoku Explainer's table:
  scale="classic" (default): the table expert solvers quote (Juillerat's SE / serate): hidden single 1.2 (box), naked single 2.3,
                             pointing 2.6, naked pair 3.0, X-Wing 3.2, hidden pair 3.4, naked triple 3.6, swordfish 3.8, ...
  scale="diuf":              the DiufSudoku fork's table: singles 1.2 / 1.3, pointing 2.5, naked pair 3.0, hidden pair 3.1,
                             naked triple 3.2, hidden triple 3.3.
The card uses the classic scale. Measured on the 747 classics of the frozen benchmark against the DiufSudoku fork's own
rating (2026-10-31): ER within 0.3 for 81%, median gap 0.1; the largest gaps are routes that use a naked single where SE
finds a hidden one (1.2-1.3 against 2.3).
Approximate by construction: our route is not SE's route. A technique SE has no value for takes the value of the
technique it is a special case of (codes.csv subset_of); with none (variant logic), it falls back to 7.0. Classic sudoku
only is meaningful.
"""

from __future__ import annotations

from . import registry as R


def _value(code, field, seen=()):
    """SE's value for a code, else the value of the nearest technique it is a special case of (codes.csv subset_of:
    Simple Colouring is a case of X-Chain, which SE finds it as); None when no generalisation has one either"""
    c = R.codes()[code]
    v = getattr(c, field) if field == "se_classic" else (c.se_diuf if c.se_diuf is not None else c.se_classic)
    if v is not None:
        return v
    for s in c.subset_of or ():
        if s in R.codes() and s not in seen:
            v = _value(s, field, seen + (code,))
            if v is not None:
                return v
    return None


# chip code -> rating (data/codes.csv se_classic / se_diuf); codes with no value, own or inherited, are left out (7.0)
CLASSIC = {c: v for c in R.codes() if (v := _value(c, "se_classic")) is not None}
DIUF = {c: v for c in R.codes() if (v := _value(c, "se_diuf")) is not None}
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
