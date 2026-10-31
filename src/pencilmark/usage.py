"""Variant usage and balance (card concepts).

rule_usage(puzzle, params): solve with explanations and record, per step, which rule ELEMENTS justified it --
a diagonal, a cage, a dot / pair relation, a line (by kind), an arrow, extra regions, shading -- so a card can
say "X-diagonals used 4x". Classic houses (rows, columns, boxes) are not elements.

necessity(puzzle): for each element class, drop every rule of that class and ask CP-SAT whether the puzzle is
still unique; a class whose removal keeps the solution unique is not needed for uniqueness (it may still be
needed for the logical path).

Both are read-only views over cbackend.solve(explain=True) / pencilmark.cpsat_verify; nothing here changes grading.
"""

import copy
from collections import Counter, defaultdict

CLASSIC = {"row", "col", "box", "implied"}


def _group_kinds(p):
    return {g.name: g.kind for g in p.groups}


def _con_element(c):
    """Element class of a constraint dict from an explanation (or from Puzzle.constraints)."""
    if not isinstance(c, dict):
        return None
    t = c.get("type")
    if t == "leftovers":
        return None  # derived from the houses
    if "detected" in str(t):  # a line recognised in pair relations (thermo / whisper / dot chain)
        return f"{c['kind']} line" if c.get("kind") else "line from pair relations"
    if c.get("line_kind"):
        return f"{c['line_kind']} line"
    if t == "line":
        return f"{c.get('kind')} line"
    if t in ("sum",) and c.get("kind") == "cage":
        return "cage"
    return {
        "sum": "sum clue",
        "little_killer": "little killer",
        "arrow": "arrow",
        "equal_sum": "equal sums",
        "set": "set / renban",
        "between": "between line",
        "table": "table rule",
        "sandwich": "sandwich",
        "xsum": "x-sum",
        "skyscraper": "skyscraper",
        "count": "count rule",
        "clone": "clone",
        "first_seen": "123 clue",
        "counting_circles": "counting circles",
        "digit_set": "digit set",
        "distinct_count": "distinct count",
        "contains": "contains rule",
    }.get(t, t)


def _unit_element(kind):
    if kind in CLASSIC or kind is None:
        return None
    return {
        "diag": "diagonal",
        "window": "window",
        "center": "centre cells",
        "extra": "extra region",
        "cage": "cage",
        "region": "irregular region",
    }.get(kind, kind)


def step_elements(p, step, gk=None):
    """Set of element classes one explained step uses."""
    gk = gk if gk is not None else _group_kinds(p)
    e = getattr(step.move, "explain", None) or {}
    out = set()
    for c in e.get("constraints") or []:
        x = _con_element(c)
        if x:
            out.add(x)
    for side in ("base", "cover"):
        blk = e.get(side) or {}
        for u in blk.get("units") or []:
            x = _unit_element((u or {}).get("kind"))
            if x:
                out.add(x)
        for r in blk.get("rules") or []:
            x = _con_element(r)
            if x:
                out.add(x)
    for r in e.get("reasons") or []:
        k = r.get("kind")
        if k == "already in group":
            x = _unit_element(gk.get(r.get("group")))
            if x:
                out.add(x)
        elif k in ("relation", "relation arc", "relation lock"):
            rel = r.get("relation")
            out.add(f"{rel} relation" if rel else "pair relation")
        elif k in ("neq cell", "neq lock"):
            out.add("different-digit link (anti-knight / anti-king ...)")
        elif k == "domain":
            out.add("shading (odd / even ...)")
        elif k == "cage sum":
            out.add("cage")
        elif k == "inequality bound":
            out.add("thermo / inequality")
        elif k == "line / rule":  # credited to the rule it names ("thermo line", "cage 3"), else to the generic label
            out.add(r.get("constraint") or "line / rule")
    for node in e.get("chain") or []:
        vc = node.get("via_constraint")
        if vc:
            x = _con_element(vc)
            if x:
                out.add(x)
        via = str(node.get("via") or "")
        if via.startswith("relation"):
            out.add(via.replace("relation ", "") + " relation")
    return out


def rule_usage(puzzle, params, solution=None):
    """-> {"steps": [set of elements per step], "counts": Counter(element -> steps using it),
    "first_use": {element: step index}, "solved": bool}"""
    from . import cbackend as CB

    steps, solved = CB.solve(puzzle, params, solution=solution, explain=True)
    gk = _group_kinds(puzzle)
    per = [step_elements(puzzle, st, gk) for st in steps]
    counts, first = Counter(), {}
    for i, s in enumerate(per):
        for x in s:
            counts[x] += 1
            first.setdefault(x, i)
    return {"steps": per, "counts": counts, "first_use": first, "solved": bool(solved), "n_steps": len(steps)}


def element_classes(p):
    """Element class -> how to remove it from a copy of the puzzle (constraint indices, group names, relations)."""
    cls = defaultdict(lambda: {"constraints": [], "groups": [], "relations": []})
    for i, c in enumerate(getattr(p, "constraints", ()) or ()):
        if c.get("type") == "line":
            cls[f"{c.get('kind')} line"]["constraints"].append(i)
            continue
        if c.get("line_kind"):  # the n-ary part finalize appended for a line: removed with its line
            continue
        x = _con_element(c)
        if x:
            cls[x]["constraints"].append(i)
    for g in p.groups:
        x = _unit_element(g.kind)
        if x:
            cls[x]["groups"].append(g.name)
    gen = _line_relations(p)
    for r in p.relations:
        t = tuple(r)
        if gen[t] > 0:
            gen[t] -= 1
            continue
        cls[f"{r[0]} relation"]["relations"].append(t)
    for c in getattr(p, "constraints", ()) or ():  # n-ary parts of lines belong to their line
        if c.get("line_kind") and c.get("type") != "line":
            cls.pop(_con_element(c), None) if not cls.get(_con_element(c), {}).get("constraints") else None
    return dict(cls)


def _line_relations(p):
    """Pair relations that finalize() generated from the line / clone constraints (multiset)."""
    from . import model as M

    cons = []
    for c in getattr(p, "constraints", ()) or ():
        if c.get("type") in ("line", "clone"):
            d = copy.deepcopy(c)
            d.pop("_compiled", None)
            cons.append(d)
    if not cons:
        return Counter()
    q = M.Puzzle(
        D=p.D,
        coords=list(p.coords),
        groups=[M.Group(g.name, tuple(g.cells), g.kind, g.complete, g.total) for g in p.groups],
        relations=[],
        constraints=cons,
    )
    q.finalize()
    return Counter(tuple(r) for r in q.relations)


def necessity(puzzle, time_limit=30.0):
    """-> {element class: True (needed: the puzzle is not unique without it) / False / None (unknown)}.
    The puzzle is rebuilt from its uncompiled definition: relations generated from lines are dropped and
    regenerated by finalize, so removing a line class removes its relations too."""
    from . import cpsat_verify as V
    from . import model as M

    p = puzzle
    gen = _line_relations(p)
    orig = []
    left = Counter(gen)
    for r in p.relations:
        t = tuple(r)
        if left[t] > 0:
            left[t] -= 1
        else:
            orig.append(r)
    out = {}
    for name, what in element_classes(p).items():
        drop_c, drop_g = set(what["constraints"]), set(what["groups"])
        cons = []
        for i, c in enumerate(p.constraints):
            if i in drop_c or c.get("_derived"):
                continue
            d = copy.deepcopy(c)
            d.pop("_compiled", None)
            cons.append(d)
        # n-ary parts appended by finalize (renban -> set, zipper / region_sum -> equal_sum, between) carry
        # line_kind: drop them, the line itself is re-compiled
        cons = [c for c in cons if not (c.get("line_kind") and c.get("type") != "line")]
        rel_class = name.endswith(" relation")
        rels = [r for r in orig if not (rel_class and f"{r[0]} relation" == name)]
        groups = [
            M.Group(g.name, tuple(g.cells), g.kind, g.complete, g.total) for g in p.groups if g.name not in drop_g
        ]
        q = M.Puzzle(
            D=p.D,
            coords=list(p.coords),
            groups=groups,
            relations=rels,
            domains=list(p.domains),
            givens=dict(p.givens),
            constraints=cons,
        )
        q.finalize()
        n = V.count(q, limit=2, time_limit=time_limit)
        out[name] = None if n is None else n != 1
    return out
