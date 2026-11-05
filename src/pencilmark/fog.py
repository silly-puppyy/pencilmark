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
    box_of = {}
    for n_, k in enumerate(rules):  # region-sum lines count segments per box
        if k["type"] == "box":
            for c in k["cells"]:
                box_of[c] = n_
        elif k["type"] == "box_grid" and k.get("origin") == "r1c1":
            bh, bw = k["box"]
            for r in range(D):
                for c in range(D):
                    box_of[_name(r, c)] = (r // bh, c // bw)
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
        elif t == "line" and k.get("kind") == "region_sum" and not all(c in L for c in cells):
            out += _partial_region_sum(cells, L, box_of)
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


def _partial_region_sum(line, L, box_of):
    """A region-sum line seen in part (CtC, Regions in the Fog: the dominoes around box 5). A fogged cell both of whose
    neighbours on the line are lit joins them (the drawn ends point at it; lines do not branch). In a seen stretch, a
    piece inside one box is complete when the line is seen crossing the box border at both ends (or ending there);
    the complete pieces of one stretch have equal sums."""
    if not box_of:
        return []
    seen = set(L) | {line[i] for i in range(1, len(line) - 1) if line[i - 1] in L and line[i + 1] in L}
    out, run = [], []
    for i, c in enumerate(line + [None]):
        if c is not None and c in seen:
            run.append(i)
            continue
        if len(run) > 1:
            pieces, cur = [], [run[0]]
            for j in run[1:]:
                if box_of.get(line[j]) == box_of.get(line[cur[-1]]):
                    cur.append(j)
                else:
                    pieces.append(cur)
                    cur = [j]
            pieces.append(cur)
            done = []
            for pc in pieces:
                a, b = pc[0], pc[-1]
                ok_a = a == 0 or a - 1 >= run[0] or box_of.get(line[a - 1]) != box_of.get(line[a])
                ok_b = b == len(line) - 1 or b + 1 <= run[-1] or box_of.get(line[b + 1]) != box_of.get(line[b])
                if ok_a and ok_b:
                    done.append([line[j] for j in pc])
            if len(done) > 1:
                out.append({"type": "equal_sum", "segments": done})
        run = []
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


_BH = [None]  # the box shape of a regular box grid (set per route); None: boxes not used in the bound
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


def arrow_cases(rules, lit, rows, cols, ortho=False, no_share=False, forced=None):
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

    D = rows
    box = (lambda c: (_rc(c)[0] // _BH[0][0], _rc(c)[1] // _BH[0][1])) if _BH[0] else None

    def least(cells):  # a lower bound on the cells' sum: cells sharing a house differ (1 + 2 + ... in one house)
        best = len(cells)
        keys = [lambda c: ("r", _rc(c)[0]), lambda c: ("c", _rc(c)[1])] + ([lambda c: ("b", box(c))] if box else [])
        for key in keys:
            g = {}
            for c in cells:
                g[key(c)] = g.get(key(c), 0) + 1
            n = max(g.values()) if g else 0
            best = max(best, n * (n + 1) // 2 + len(cells) - n)
        return best

    def paths(start, block, most, shaft0=(), circle_last=False):
        out, todo = [], [[start]]
        while todo:
            p = todo.pop()
            shaft = list(shaft0) + (p[:-1] if circle_last else p)
            if least(shaft) > D:
                continue  # even this much shaft outweighs the largest circle: longer is no better
            out.append(p)
            if len(out) > CASE_CAP:
                return None
            if len(p) < most:
                todo += [p + [y] for y in nbs(p[-1]) if y not in p and y not in block and y not in others and ok_step(p[-1], y)]
        return out

    seen_on = {}  # arrow -> its cells a solver sees (lit ones), and cells every surviving case of it uses (forced):
    for n_, k in enumerate(rules):  # with no_share, no other arrow's shaft enters them
        if k["type"] == "arrow":
            seen_on[n_] = {c for c in list(k.get("bulb") or []) + [x for ln in k.get("lines") or [] for x in ln] if c in L}
            seen_on[n_] |= (forced or {}).get(n_, set())
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
                ps = paths(line[len(seen)], set(seen) | {bulb}, rows - 1 - len(seen), seen)
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
                    cps = paths(ce, set(stretch) | set(te), rows - len(stretch), stretch, circle_last=True)
                    if cps is None:
                        cases = None
                        break
                    for cp in cps:
                        tps = [[]] if not te else (paths(te[0], set(stretch) | set(cp), rows - 1 - len(stretch) - len(cp) + 1, stretch + cp[:-1]) or [])
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
                        "lemma": {"id": 7000, **LEMMA}, "_arrow": n_})
    return out


CLUE_ALWAYS = _re.compile(r"clue is always given|all cages? (?:clues|totals) are given|every cage has a (?:clue|total)"
                         r"|cages?[^.]*sum to (?:the )?(?:total|clue|number|small)", _re.I)
SOME_UNCLUED = _re.compile(r"not all cages|some cages|cages? (?:without|with no) (?:a )?(?:total|clue|sum)|unclued cage", _re.I)


CAGE_SIZE = _re.compile(r"cages are (?:all )?(?:exactly )?(\d|one|two|three|four|five|six) cells", _re.I)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def cage_cases(rules, lit, rows, cols, clue_always, forced=None, size=None):
    """Case rules for cages seen in part (CtC, Corner Prison: "the clue is always in the top-left cell, so this cage
    must reach row 1 ... it can't be more than 9 cells"). A lit cell shows its walls: across an edge with a lit side,
    the two cells share a cage exactly when no wall is drawn. A shape is a connected set holding a lit stretch of the
    cage, at most D cells, agreeing with every edge seen from a lit cell, avoiding cells of fully lit cages and cells
    other cages' surviving shapes all use (cages never overlap); with clue_always its top-left cell holds the total, so
    a lit top-left shows one and a shown total is the top-left. Each shape is a case: all different, summing to the
    total when it is shown. Returned as engine constraints over cell indices."""
    L = {_name(r, c) for r, c in lit}
    D = rows
    cage_of = {}
    for n_, k in enumerate(rules):
        if k["type"] == "cage" and k.get("sum") is not None:
            for c in k["cells"]:
                cage_of[c] = n_
    taken = {c for n_, k in enumerate(rules) if k["type"] == "cage" and k.get("sum") is not None
             and all(c in L for c in k["cells"]) for c in k["cells"]}
    ix = lambda c: _rc(c)[0] * cols + _rc(c)[1]

    def nbs(c):
        r, q = _rc(c)
        return [_name(r + a, q + b) for a, b in ((-1, 0), (1, 0), (0, -1), (0, 1)) if 0 <= r + a < rows and 0 <= q + b < cols]

    same = lambda a, b: cage_of.get(a) is not None and cage_of.get(a) == cage_of.get(b)  # no wall drawn between them
    out = []
    for n_, k in enumerate(rules):
        if k["type"] != "cage" or k.get("sum") is None or all(c in L for c in k["cells"]):
            continue
        lit_cells = [c for c in k["cells"] if c in L]
        if not lit_cells:
            continue
        label = min(k["cells"], key=_rc)
        shown = label in L
        total = k["sum"] if shown else None
        closed = taken | {c for m, cs in (forced or {}).items() if m != n_ for c in cs}
        comp = [lit_cells[0]]  # one lit stretch (connected through lit cells of this cage) seeds the shapes
        todo = [lit_cells[0]]
        while todo:
            x = todo.pop()
            for y in nbs(x):
                if y in lit_cells and y not in comp:
                    comp.append(y)
                    todo.append(y)

        def agrees(sh):
            for x in sh:
                for y in nbs(x):
                    if (x in L or y in L) and same(x, y) != (y in sh):
                        return False
            tl = min(sh, key=_rc)
            if clue_always and ((shown and tl != label) or (not shown and tl in L)):
                return False
            if size and len(sh) != size:
                return False  # the rules give every cage's size
            if total is not None:
                n = len(sh)
                return n * (n + 1) // 2 <= total <= sum(range(D - n + 1, D + 1))
            return True

        shapes, seen, todo, too_many = [], set(), [frozenset(comp)], False
        while todo:
            sh = todo.pop()
            if agrees(sh):
                shapes.append(sh)
                if len(shapes) > CASE_CAP:
                    too_many = True
                    break
            if len(sh) >= (size or D):
                continue
            for x in sh:
                for y in nbs(x):
                    if y in sh or y in closed or ((x in L or y in L) and not same(x, y)):
                        continue
                    n2 = frozenset(sh | {y})
                    if n2 not in seen:
                        seen.add(n2)
                        todo.append(n2)
        if too_many or not shapes:
            continue
        cases = [{"cells": [ix(c) for c in sorted(sh, key=_rc)], "total": total, "distinct": True} for sh in shapes]
        out.append({"type": "cases", "cases": cases, "name": f"cage {label}: {len(cases)} possible shapes",
                    "lemma": {"id": 7100, **LEMMA}, "_cage": n_})
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
    clue_always = bool(CLUE_ALWAYS.search(rules_text or "")) and not SOME_UNCLUED.search(rules_text or "")
    m_ = CAGE_SIZE.search(rules_text or "")
    cage_size = (int(m_.group(1)) if m_.group(1).isdigit() else _WORDS[m_.group(1).lower()]) if m_ else None
    p = api.load(puzzle)
    fog = getattr(p, "fog", None)
    if not fog:
        raise ValueError("the puzzle has no fog rule")
    sol = api.solve(p)
    doc = write_doc(p)
    rows, cols = doc["board"]["rows"], doc["board"]["cols"]
    D = doc["digits"]
    grids = [k for k in doc["rules"] if k["type"] == "box_grid"]
    _BH[0] = tuple(grids[0]["box"]) if len(grids) == 1 and grids[0].get("origin") == "r1c1" else None
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
        for c in cage_cases(doc["rules"], lit, rows, cols, clue_always, None, cage_size):
            if len(c["cases"]) == 1 and c["cases"][0]["total"] is not None:  # one shape left: the cage is known, as a
                cs1 = c["cases"][0]["cells"]  # cage rule (set theory, combinations and the rest read it)
                vis["rules"].append({"type": "cage", "cells": [_name(i // cols, i % cols) for i in cs1], "sum": c["cases"][0]["total"]})
        q = api.load(vis)
        base = list(q.constraints)
        forced = {}  # ("arrow" | "cage", rule index) -> cells every surviving case uses: closed to the others
        for _ in range(6):  # hidden-content lemmas ("cases"), iterated while the closed cells grow
            fa = {n: cs for (t_, n), cs in forced.items() if t_ == "arrow"}
            fc = {n: cs for (t_, n), cs in forced.items() if t_ == "cage"}
            cs = arrow_cases(doc["rules"], lit, rows, cols, ortho, no_share, fa) + cage_cases(doc["rules"], lit, rows, cols, clue_always, fc, cage_size)
            q.constraints = base + cs
            if not cs:
                break
            alive = CB._C.cases_alive(CB.to_cpuzzle(q), [int(x) for x in cand])
            new_forced = dict(forced)
            for spec, ok in alive:
                k = q.constraints[spec]
                key = ("arrow", k["_arrow"]) if "_arrow" in k else ("cage", k["_cage"]) if "_cage" in k else None
                if ok and key and (key[0] == "cage" or no_share):
                    sets = [{_name(c // cols, c % cols) for c in k["cases"][i]["cells"]} for i in ok]
                    new_forced[key] = set.intersection(*sets)
            if new_forced == forced:
                break
            forced = new_forced
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
