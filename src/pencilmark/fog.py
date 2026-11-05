"""Fog of war: the route a solver can take under the fog (docs/formats/rules/other.mdx 6.19).

The puzzle is solved from what the fog shows. A round runs the engine on the rules a solver sees (candidates carried
from earlier rounds, no guessing) up to the first placement that lights a new cell; a round that only eliminates is
repeated. Every rule given to the engine holds in the real puzzle, so every placement is correct.

What a solver sees (docs/research/fog_mechanics.md, read from SudokuPad's own drawing):

- a rule on cells, once all its cells are lit;
- an edge or corner clue (dot, X / V, inequality, quadruple), from any lit cell it touches;
- a line, stretch by stretch: the lit cells of a whisper / thermo / entropic line and the fogged cell the drawn line
  enters at each end;
- a cage, by its lit stretches (different digits; the stretch holding the total sums below it);
- "all dots are given" negatives, between lit cells only;
- outside clues, main diagonals and rules stated for the whole board, always.

Hidden-content reasoning (a partly seen arrow's possible shafts, cage shapes from walls) is not here yet: it moves
into the engine (docs/research/fog_engine_port.md). Until then a route can stall where a host reasons about what the
fog hides.

    route(puzzle) -> {"solved", "rounds", "reveals", "steps": [{"technique", "difficulty", "round", "place"}], "stuck"}
"""

from __future__ import annotations

OUTSIDE = {"sandwich", "xsum", "skyscraper", "rossini", "first_seen"}
STATED = {"box_grid", "grid", "box", "row", "column", "region", "global_entropy"}
LINE_STRETCH = {"whisper", "thermo", "entropic"}  # every stretch of these lines obeys the rule


def _rc(c):
    return int(c[1 : c.index("c")]) - 1, int(c[c.index("c") + 1 :]) - 1


def _name(r, c):
    return f"r{r + 1}c{c + 1}"


def lit_cells(fog, givens, placed, rows, cols):
    """the cells a solver sees: the start cells; a given lights only itself; without triggers each correctly entered
    digit lights its 3x3; with triggers an effect lights once every cell of its `when` holds a digit"""
    lit = {_rc(c) for c in fog.get("lit", [])}
    filled = set(placed)
    for i, g in enumerate(givens):
        if g:
            lit.add((i // cols, i % cols))
            filled.add((i // cols, i % cols))
    if fog.get("reveal", "3x3") == "triggers":
        for t in fog.get("triggers", []):
            if all(_rc(c) in filled for c in t["when"]):
                lit |= {_rc(c) for c in t["light"]}
    else:
        for r, c in placed:
            lit |= {(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if 0 <= r + a < rows and 0 <= c + b < cols}
    return lit


def _diagonal(rule, D):
    cs = rule.get("cells") or []
    if rule["type"] not in ("cage", "region") or rule.get("sum") is not None or len(cs) != D:
        return False
    rc = {_rc(c) for c in cs}
    return rc in ({(i, i) for i in range(D)}, {(i, D - 1 - i) for i in range(D)})


def visible_rules(rules, lit, D):
    """the rules a solver sees with these cells lit (module docstring)"""
    L = {_name(r, c) for r, c in lit}
    out = []
    for k in rules:
        t = k["type"]
        if t == "fog":
            continue
        cells = list(k.get("cells") or [])
        if t in STATED or t in OUTSIDE or _diagonal(k, D) or (t == "neighbours" and "except" not in k):
            out.append(k)
        elif t in ("neighbours", "negative"):  # "all dots are given": only where both cells are seen
            area = sorted(set(k["area"]) & L) if isinstance(k.get("area"), list) else sorted(L)
            if len(area) > 1:
                out.append(dict(k, area=area))
        elif t in ("edge", "corner") or (t == "contains" and len(cells) == 4):
            if any(c in L for c in cells):
                out.append(k)
        elif t == "line" and k.get("kind") in LINE_STRETCH and not k.get("closed"):
            run = []
            for i, c in enumerate(cells + [None]):
                if c is not None and c in L:
                    run.append(i)
                    continue
                if run:
                    a, b = run[0], run[-1]
                    seen = cells[max(a - 1, 0) : min(b + 2, len(cells))]  # the drawn line enters the next cells
                    if len(seen) >= 2:
                        out.append(dict(k, cells=seen))
                run = []
        elif t == "cage" and not all(c in L for c in cells):
            out += _partial_cage(k, L)
        elif t == "cell":
            cs = [c for c in cells if c in L]
            if cs:
                out.append(dict(k, cells=cs))
        else:
            every = cells + [c for x in (k.get("bulb") or []) for c in ([x] if isinstance(x, str) else x)]
            every += [c for ln in (k.get("lines") or []) for c in ln]
            if every and all(c in L for c in every):
                out.append(k)
    return out


def _partial_cage(k, L):
    """a cage seen in part: each lit stretch (connected through lit cells) is inside one cage: different digits; the
    stretch holding the total (its top-left cell) sums below it, fogged cells remaining"""
    lit = [c for c in k["cells"] if c in L]
    comps, seen = [], set()
    for c in lit:
        if c in seen:
            continue
        comp, todo = [], [c]
        seen.add(c)
        while todo:
            x = todo.pop()
            comp.append(x)
            for y in lit:
                if y not in seen and sum(abs(a - b) for a, b in zip(_rc(x), _rc(y))) == 1:
                    seen.add(y)
                    todo.append(y)
        comps.append(comp)
    label = min(k["cells"], key=_rc)
    out = []
    for comp in comps:
        if len(comp) > 1:
            out.append({"type": "cage", "cells": comp})
        if k.get("sum") is not None and label in comp and len(comp) <= 4:
            out.append({"type": "custom", "cells": {"Q": comp}, "holds": f"sum(Q) <= {k['sum'] - 1}"})
    return out


def route(puzzle, max_rounds=400):
    """the fog route of a unique fog puzzle (module docstring). Raises ValueError when the puzzle has no fog rule."""
    from . import api, cbackend as CB, solver as SV
    from .exchange.write import write as write_doc

    p = api.load(puzzle)
    fog = getattr(p, "fog", None)
    if not fog:
        raise ValueError("the puzzle has no fog rule")
    sol = api.solve(p)
    doc = write_doc(p)
    rows, cols = doc["board"]["rows"], doc["board"]["cols"]
    D = doc["digits"]
    givens = list(doc["givens"])
    givens0 = list(givens)
    placed = set()
    lit = lit_cells(fog, givens0, placed, rows, cols)
    full = (1 << D) - 1
    cand = [full if not g else 1 << (g - 1) for g in givens]
    steps, reveals = [], 0
    for rounds in range(1, max_rounds + 1):
        if all(g or g is None for g in givens):
            return {"solved": True, "rounds": rounds - 1, "reveals": reveals, "steps": steps, "stuck": 0}
        before = list(cand)
        vis = dict(doc, givens=givens, rules=visible_rules(doc["rules"], lit, D))
        q = api.load(vis)
        st, _ = CB.solve(q, assume_unique=False, cand=cand, disabled=(SV.GUESS, SV.TRIAL))
        progressed = False
        for s in st:
            m = s.move
            if m.family == "Guess":
                break
            steps.append({"technique": m.family, "difficulty": round(m.d, 3), "round": rounds,
                          "place": None if not m.place else [_name(m.place[0] // cols, m.place[0] % cols), m.place[1]]})
            for ci, dg in m.elim or ():
                cand[ci] &= ~(1 << (dg - 1))
            if m.place:
                ci, dg = m.place
                if int(sol[ci]) != dg:  # cannot happen: every rule given holds in the puzzle
                    raise AssertionError(f"fog route placed a wrong digit at {ci}")
                cand[ci] = 1 << (dg - 1)
                givens[ci] = dg
                placed.add((ci // cols, ci % cols))
                progressed = True
                new = lit_cells(fog, givens0, placed, rows, cols)
                if new - lit:
                    lit = new
                    reveals += 1
                    break
        if not progressed and cand != before:
            continue  # eliminations only: the next round reads them
        if not progressed:
            return {"solved": False, "rounds": rounds, "reveals": reveals, "steps": steps,
                    "stuck": sum(1 for g in givens if g == 0)}
    return {"solved": False, "rounds": max_rounds, "reveals": reveals, "steps": steps,
            "stuck": sum(1 for g in givens if g == 0)}
