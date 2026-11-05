"""Fog of war: the route a solver can take under the fog (docs/formats/rules/other.mdx 6.19).

The puzzle is solved from what the fog shows. A round runs the engine on the rules a solver sees (candidates carried
from earlier rounds, no guessing) up to the first placement that lights a new cell; a round that only eliminates is
repeated. Every rule given to the engine holds in the real puzzle, so every placement is correct.

What a solver sees (docs/research/fog_mechanics.md, read from SudokuPad's own drawing), on top of the `lit` cells and
what correct digits reveal:

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
    """the cells a solver sees: the `lit` cells (what the puzzle shows at the start, givens included as the source
    shows them); without triggers each correctly entered digit lights its 3x3; with triggers an effect lights once
    every cell of its `when` holds a digit (givens count as held)"""
    lit = {_rc(c) for c in fog.get("lit", [])}
    filled = set(placed) | {(i // cols, i % cols) for i, g in enumerate(givens) if g}
    if fog.get("triggers"):
        for t in fog["triggers"]:
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


CASE_CAP = 300  # an arrow with more possible hidden shapes than this gets no case rule (nothing claimed: sound)
LEMMA = {"setup": 1.0, "use": 0.5}  # placeholder prices (coach fit: case lemmas are nearly free; to be fitted)


def _segments(rules):
    """drawn segments: consecutive cells of every arrow (circle to shaft) and line, seen from a lit end"""
    seg = set()
    for k in rules:
        if k["type"] == "arrow":
            for ln in k.get("lines") or []:
                ch = list(k.get("bulb") or [])[:1] + ln
                seg |= {frozenset(p) for p in zip(ch, ch[1:])}
        elif k["type"] == "line":
            seg |= {frozenset(p) for p in zip(k["cells"], k["cells"][1:])}
    return seg


import re as _re

ORTHO = _re.compile(r"arrows?[^.]*orthogonal", _re.I)
NO_SHARE = _re.compile(r"arrows?[^.]*(?:don.t|do not|may not|cannot|never) (?:share|overlap|cross)", _re.I)


def arrow_cases(rules, lit, rows, cols, ortho=False, no_share=False):
    """Case rules for arrows seen in part (CtC hosts: "this arrow can't stop here ... it must go down"). A lit cell
    shows its drawn segments, so a hidden part of a shaft runs through fogged cells, stepping into or out of a lit cell
    only along a drawn segment. Seen: the lit cells of the arrow, the fogged cells its drawn lines enter.
    - circle lit: the shaft from the circle up to the first fogged cell, then every continuation (a case each);
    - circle fogged: each lit stretch of the shaft; one end leads to the circle (a case per path), the other on
      to the tip (unless the stretch holds the tip, whose arrowhead shows).
    Each case: its cells with the circle = the sum of the others; the engine checks the cases against the live
    candidates (rule kind "cases"). Returned as engine constraints over cell indices."""
    L = {_name(r, c) for r, c in lit}
    seg = _segments(rules)
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)] + ([] if ortho else [(-1, -1), (-1, 1), (1, -1), (1, 1)])
    ix = lambda c: _rc(c)[0] * cols + _rc(c)[1]

    def nbs(x):
        r, c = _rc(x)
        return [_name(r + a, c + b) for a, b in steps if 0 <= r + a < rows and 0 <= c + b < cols]

    def ok_step(x, y):
        return frozenset((x, y)) in seg if (x in L or y in L) else True

    others = set()

    def paths(start, block, most):
        out, todo = [], [[start]]
        while todo:
            p = todo.pop()
            out.append(p)
            if len(out) > CASE_CAP:
                return None
            if len(p) < most:
                todo += [p + [y] for y in nbs(p[-1]) if y not in p and y not in block and y not in others and ok_step(p[-1], y)]
        return out

    seen_on = {}  # arrow -> its cells a solver sees (lit ones): with no_share, no other arrow's shaft enters them
    for n_, k in enumerate(rules):
        if k["type"] == "arrow":
            seen_on[n_] = {c for c in list(k.get("bulb") or []) + [x for ln in k.get("lines") or [] for x in ln] if c in L}
    out = []
    for n_, k in enumerate(rules):
        if k["type"] != "arrow" or len(k.get("bulb") or []) != 1:
            continue
        bulb = k["bulb"][0]
        others.clear()
        if no_share:
            others.update(c for m, cs in seen_on.items() if m != n_ for c in cs)
        for line in k.get("lines") or []:
            if all(c in L for c in [bulb] + line):
                continue  # seen whole: the arrow rule itself
            cases = []
            if bulb in L:
                seen = []
                for c in line:
                    if c not in L:
                        break
                    seen.append(c)
                if len(seen) == len(line):
                    continue
                ps = paths(line[len(seen)], set(seen) | {bulb}, rows - 1 - len(seen))
                if ps is None:
                    continue
                cases = [{"cells": [ix(bulb)] + [ix(c) for c in seen + p], "circle": ix(bulb)} for p in ps]
            else:
                run = [i for i, c in enumerate(line) if c in L]
                if not run:
                    continue
                a, b = run[0], run[-1]
                if any(line[i] not in L for i in range(a, b + 1)):
                    continue  # several stretches: not one known piece
                stretch = line[a : b + 1]
                ends = [line[a - 1] if a > 0 else bulb] + ([line[b + 1]] if b + 1 < len(line) else [])
                for ce in ends:
                    te = [e for e in ends if e != ce]
                    cps = paths(ce, set(stretch) | set(te), rows - len(stretch))
                    if cps is None:
                        cases = None
                        break
                    for cp in cps:
                        tps = [[]] if not te else (paths(te[0], set(stretch) | set(cp), rows - 1 - len(stretch) - len(cp) + 1) or [])
                        for tp in tps:
                            cells = cp + stretch + tp
                            cases.append({"cells": [ix(c) for c in cells], "circle": ix(cp[-1])})
                            if len(cases) > CASE_CAP:
                                cases = None
                                break
                        if cases is None:
                            break
                    if cases is None:
                        break
                if not cases:
                    continue
            out.append({"type": "cases", "cases": cases, "name": f"arrow {bulb}: {len(cases)} possible shafts",
                        "lemma": {"id": 7000, **LEMMA}})
    return out


def route(puzzle, max_rounds=400, rules_text=None):
    """the fog route of a unique fog puzzle (module docstring). Raises ValueError when the puzzle has no fog rule.
    rules_text: the puzzle's rules (read from the input's metadata when not given): statements such as "arrows move
    orthogonally" and "arrows don't share cells" narrow the hidden shapes."""
    from . import api, cbackend as CB, inputs, solver as SV
    from .exchange.write import write as write_doc

    if rules_text is None and not hasattr(puzzle, "coords"):
        try:
            obj = inputs.read(puzzle)
            obj = obj.get("puzzle", obj) if isinstance(obj.get("puzzle"), dict) else obj
            rules_text = (obj.get("meta") or {}).get("rules_text") or ""
        except Exception:  # noqa: BLE001 -- the load below reports a bad input
            rules_text = ""
    ortho, no_share = bool(ORTHO.search(rules_text or "")), bool(NO_SHARE.search(rules_text or ""))
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
        q.constraints += arrow_cases(doc["rules"], lit, rows, cols, ortho, no_share)  # hidden-content lemmas ("cases")
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
