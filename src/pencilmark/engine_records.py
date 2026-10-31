"""Decoding the engine's explanation records: the structured justification of one move (solve(explain=True),
cbackend.explain_record) from the integer records the C++ engine writes (csrc/solver.hpp EX_* tags): its pattern, base
and cover units, chains, almost locked sets, the cases tried, the rules used. The explainer (pencilmark/explain) reads
these instead of finding the pattern again."""

from __future__ import annotations

from . import solver as S

# how the engine names a move's subject (Move::nk): nothing, a group, a lock, an innie / outie set, an n-ary rule
_NM_NONE, _NM_GROUP, _NM_LOCK, _NM_INNIE, _NM_OUTIE, _NM_NARY = range(6)
_LINK = {
    0: "weak",
    1: "strong (bivalue cell)",
    2: "strong (only two places in a group)",
    3: "strong (constraint must contain the digit)",
    4: "strong (pair relation)",
    5: "strong (inside an almost locked set)",
    6: "equivalence (equality relation)",
}
_TRIAL_VIEW = {
    0: "candidates",
    1: "no notes (mental view)",
    2: "candidates, singles only",
    10: "candidates, basic propagation",
    11: "candidates, dynamic (techniques in the branches)",
    12: "candidates, nested (forcing chains in the branches)",
    13: "candidates, light logic (what if)",
    14: "no notes, light logic (what if)",
}
_EVENTS = {
    1: "naked single",
    2: "hidden single",
    3: "relation",
    4: "rule",
    5: "empty cell",
    6: "house missing digit",
    7: "rule unsatisfiable",
    8: "conflicting singles",
    9: "technique",
}


_STEP_EVENTS = ("naked single", "hidden single", "relation", "rule", "technique")


def _rc(p, c):
    r, k = p.coords[c]
    return f"r{r + 1}c{k + 1}"


def _digits(mask):
    return [d for d in range(1, 33) if mask >> (d - 1) & 1]


def _group(p, gi, info=None):
    if gi is None or gi < 0:
        return None
    if gi < len(p.groups):
        g = p.groups[gi]
        d = {"name": g.name, "kind": g.kind, "cells": list(g.cells)}
        if g.total is not None:
            d["sum"] = g.total
        return d
    for idx, name, cells in (info or {}).get("implied_groups", ()):
        if idx == gi:
            return {"name": name, "kind": "implied house", "cells": list(cells)}
    return {"name": f"implied{gi - len(p.groups) + 1}", "kind": "implied house", "cells": []}


def _gname(p, gi, info=None):
    g = _group(p, gi, info)
    return g["name"] if g else None


def _constraint(p, idx, info=None):
    cons = getattr(p, "constraints", [])
    if 0 <= idx < len(cons):
        return {k: v for k, v in cons[idx].items() if not k.startswith("_")}
    ex = getattr(p, "_cextra", [])
    if 0 <= idx - len(cons) < len(ex):
        return {"type": "line (detected from pair relations)", "description": ex[idx - len(cons)]}
    for lo in (info or {}).get("leftovers", ()):
        if lo["index"] == idx:
            return {
                "type": "leftovers",
                "kind": lo["kind"],
                "index": idx,
                "a": list(lo["a"]),
                "b": list(lo["b"]),
                "a_rc": [_rc(p, c) for c in lo["a"]],
                "b_rc": [_rc(p, c) for c in lo["b"]],
                "lines": [_group(p, g, info) for g in lo["lines"]],
                "regions": [_group(p, g, info) for g in lo["regions"]],
            }
    return {"type": "leftovers (derived set equivalence)", "index": idx}


def _cref(p, ref, info=None):
    """constraint ref from the engine: >= 0 constraint index, <= -2 cage group -2-ref"""
    if ref is None or ref == -1:
        return None
    if ref >= 0:
        return _constraint(p, ref, info)
    return _group(p, -2 - ref, info)


def _cref_name(p, ref, info=None):
    c = _cref(p, ref, info)
    if c is None:
        return None
    if "name" in c:
        return f"cage {c['name']}" if c.get("sum") is not None else c["name"]
    if c.get("type") == "line":
        return f"{c.get('kind', 'line')} line"
    return c.get("description") or c.get("kind") or c.get("type")


def _via(p, a, b, digit_a, digit_b, info=None):
    """which unit / rule links two chain nodes"""
    if a == b:
        return "same cell"
    for gi in p.groups_of[a]:
        if b in p.groups[gi].cells:
            return p.groups[gi].name
    for _, name, cells in (info or {}).get("implied_groups", ()):
        if a in cells and b in cells:
            return name
    if b in p.neq[a]:
        return "neq relation"
    if b in p.nonconsec[a]:
        return "relation " + _relkinds(p, a, b)
    return None


def _relkinds(p, a, b):
    kinds = sorted({r[0] for r in p.relations if {r[1], r[2]} == {a, b}})
    return "/".join(kinds) if kinds else "pair"


def _reason(p, c, v, kind, a, b, info):
    r = {"cell": c, "rc": _rc(p, c), "digit": v}
    if kind == 0:
        r.update(kind="already in group", group=_gname(p, a, info), by=_rc(p, b) if b >= 0 else None)
    elif kind == 1:
        r.update(kind="neq cell", by=_rc(p, a))
    elif kind == 2:
        r.update(kind="relation", by=_rc(p, a), by_digit=b, relation=_relkinds(p, c, a))
    elif kind == 3:
        r.update(kind="domain")
    elif kind == 4:
        g = _group(p, a, info)
        r.update(kind="cage sum", group=g["name"] if g else None, sum=g.get("sum") if g else None)
    elif kind == 5:
        if b >= 0:
            r.update(kind="pointing", house=_gname(p, a, info), group=_gname(p, b, info))
        else:
            r.update(kind="relation lock" if b == -2 else "neq lock", house=_gname(p, a, info))
    elif kind == 6:
        r.update(kind="relation arc", by=_rc(p, a) if a >= 0 else None, depth=b)
    elif kind == 7:
        r.update(kind="inequality bound", by=_rc(p, a) if a >= 0 else None, depth=b)
    elif kind == 8:
        r.update(kind="line / rule", constraint=_cref_name(p, a, info), depth=b)
    elif kind == 9:
        r.update(kind="mental subset", house=_gname(p, a, info) if a >= 0 else None, size=b)
    elif kind == 11:
        r.update(kind="mental pointing", house=_gname(p, a, info) if a >= 0 else None, size=b)
    else:
        r.update(kind=str(kind))
    return r


def _event(p, t, rnd, c, dm, src, info):
    e = {"event": _EVENTS.get(t, str(t)), "round": rnd}
    if c >= 0:
        e.update(cell=c, rc=_rc(p, c))
    if t in (1, 2, 8):
        e["digit"] = dm
        if t == 2:
            e["house"] = _gname(p, src, info)
    elif t in (3, 4):
        e["digits"] = _digits(dm)
        if t == 3:
            e.update(by=_rc(p, src), relation=_relkinds(p, c, src))
        else:
            e["constraint"] = _cref_name(p, src, info)
    elif t == 6:
        e.update(digit=dm, house=_gname(p, src, info))
    elif t == 7:
        e["constraint"] = _cref_name(p, src, info)
        if dm:
            e["digit"] = dm
    elif t == 9:
        e.update(technique=S.TECH_NAMES.get(dm, str(dm)), eliminations=src)
    return e


def _records(exs):
    i = 0
    while i + 1 < len(exs):
        tag, n = exs[i], exs[i + 1]
        yield tag, list(exs[i + 2 : i + 2 + n])
        i += 2 + n


def _explain(p, m, nm, pats, exs, info=None):
    """Structured justification of a move (schema in csolver/README.md)."""
    nk, na, nb = nm
    tech = m.feat[0]
    out = {
        "technique": S.TECH_NAMES[tech],
        "code": m.code,
        "difficulty": m.d,
        "placement": None,
        "eliminations": [],
        "digits": [],
        "targets": [],
        "pattern_cells": [int(c) for c in pats],
        "base": {"units": [], "cells": []},
        "cover": {"units": [], "cells": []},
        "constraints": [],
        "chain": [],
        "als": [],
        "xmeta": m.xmeta,
    }
    digits = set()
    if m.place:
        c, v = m.place
        out["placement"] = {"cell": c, "rc": _rc(p, c), "digit": v}
        out["targets"] = [c]
        digits.add(v)
    for c, v in m.elim:
        out["eliminations"].append({"cell": c, "rc": _rc(p, c), "digit": v})
        digits.add(v)
    if not m.place:
        out["targets"] = sorted({c for c, _ in m.elim})
    # units by name kind: group (single / subset / pointing house), lock (base -> cover)
    if nk in (_NM_GROUP, _NM_INNIE, _NM_OUTIE) and na >= 0:
        out["base"]["units"].append(_group(p, na, info))
    if nk == _NM_LOCK:
        out["base"]["units"].append(_group(p, na, info))
        out["cover"]["units"].append(_group(p, nb, info))
    if nk == _NM_NARY:
        if na >= 0:
            out["constraints"].append(_constraint(p, na, info))
        if nb >= 0:
            out["constraints"].append(_group(p, nb, info))
    recs = list(_records(exs))
    als, gnodes = {}, {}
    for tag, data in recs:  # grouped chain nodes: id -> cells
        if tag == 14 and len(data) >= 3:
            gnodes[data[0]] = data[2:]
    for tag, data in recs:  # ALS first: chain nodes refer to them
        if tag == 4 and len(data) >= 2:
            aid = -1 - data[0]
            if aid in als:
                continue
            als[aid] = {"id": aid, "digits": _digits(data[1]), "cells": data[2:], "rc": [_rc(p, c) for c in data[2:]]}
            out["als"].append(als[aid])
    for tag, data in recs:
        n = len(data)
        if tag == 1:
            out["base"]["units"] += [_group(p, g, info) for g in data]
        elif tag == 2:
            out["cover"]["units"] += [_group(p, g, info) for g in data]
        elif tag == 3 and n == 1:
            out["restricted_common"] = _digits(data[0])
        elif tag == 5 and n % 4 == 0:
            prev = None
            for k in range(0, n, 4):
                c, v, t, src = data[k : k + 4]
                node = {"digit": v}
                if c >= 0:
                    node.update(cell=c, rc=_rc(p, c))
                elif c <= -1000000:  # grouped node: the digit in one of 2-3 cells of a box-line segment
                    g = gnodes.get(c, [])
                    node.update(group=g, group_rc=[_rc(p, x) for x in g])
                else:
                    a = als.get(-1 - c, {})
                    node.update(
                        als=-1 - c, als_cells=a.get("cells", []), als_rc=a.get("rc", []), als_digits=a.get("digits", [])
                    )
                if prev is not None:
                    node["link_in"] = _LINK.get(t, str(t))
                    via = None
                    if t == 2 and src >= 0:
                        via = _gname(p, src, info)
                    elif t == 3:
                        via = _cref_name(p, src, info)
                        node["via_constraint"] = _cref(p, src, info)
                    elif t == 5:
                        via = f"almost locked set {-1 - c if c < 0 else src}"
                    elif t == 6:
                        via = "equality relation"
                    elif "group" in node or "group" in prev:
                        via = "sees every cell of the group"
                    elif c < 0 or prev.get("cell") is None:
                        via = "sees every ALS cell holding the digit"
                    if via is None and c >= 0 and prev.get("cell") is not None:
                        via = _via(p, prev["cell"], c, prev["digit"], v, info)
                    node["via"] = via
                out["chain"].append(node)
                prev = node
                digits.add(v)
        elif tag == 6 and n % 5 == 0:
            out["reasons"] = [_reason(p, *data[k : k + 5], info) for k in range(0, n, 5)]
        elif tag == 7 and n >= 2:
            view, nopt = data[0], data[1]
            out["trial"] = {
                "view": _TRIAL_VIEW.get(view, str(view)),
                "options": [
                    {"cell": data[2 + 2 * i], "rc": _rc(p, data[2 + 2 * i]), "digit": data[3 + 2 * i]}
                    for i in range(nopt)
                ],
                "branches": [],
            }
        elif tag == 8 and n >= 3:
            c, v, rnd = data[:3]
            evs = [_event(p, *data[k : k + 5], info) for k in range(3, n - 4, 5)]
            br = {
                "assume": {"cell": c, "rc": _rc(p, c), "digit": v},
                "contradiction_round": rnd or None,
                "steps": [e for e in evs if e["event"] in _STEP_EVENTS],
                "contradiction": next((e for e in evs if e["event"] not in _STEP_EVENTS), None),
            }
            out.setdefault("trial", {"view": None, "options": [], "branches": []})["branches"].append(br)
        elif tag == 9 and n >= 6 and data[0] == 0:  # multi-digit (3D Medusa): entries cell*32+digit
            _, wrap, side, ca, cb, n0 = data[:6]
            cols = [data[6 : 6 + n0], data[6 + n0 :]]
            out["coloring"] = {
                "digit": None,
                "type": "wrap" if wrap else "trap",
                "colors": [[{"cell": e // 32, "rc": _rc(p, e // 32), "digit": e % 32} for e in col] for col in cols],
                "eliminated_color": side if wrap else None,
                "clash": [ca, cb] if wrap else None,
            }
        elif tag == 9 and n >= 6:
            v, wrap, side, ca, cb, n0 = data[:6]
            cols = [data[6 : 6 + n0], data[6 + n0 :]]
            out["coloring"] = {
                "digit": v,
                "type": "wrap" if wrap else "trap",
                "colors": cols,
                "rc": [[_rc(p, c) for c in col] for col in cols],
                "eliminated_color": side if wrap else None,
                "clash": [ca, cb] if wrap else None,
            }
        elif tag == 10 and n >= 4:
            total, outie, nh = data[:3]
            houses = data[3 : 3 + nh]
            ncg = data[3 + nh]
            cages = data[4 + nh : 4 + nh + ncg]
            cells = data[4 + nh + ncg :]
            out["region"] = {
                "type": "outie" if outie else "innie",
                "total": total,
                "cells": cells,
                "rc": [_rc(p, c) for c in cells],
                "houses": [_group(p, g, info) for g in houses],
                "cages": [_group(p, g, info) for g in cages],
            }
            hu = [_group(p, g, info) for g in houses]
            names = {h["name"] for h in hu}
            out["base"]["units"] = hu + [u for u in out["base"]["units"] if u and u["name"] not in names]
            out["cover"]["units"] += [_group(p, g, info) for g in cages]
        elif tag == 11 and n >= 1:
            if tech == S.ALS_XYWING and n == 4:
                a = als.get(-1 - data[0], {})
                out["hinge"] = {
                    "als": -1 - data[0],
                    "cells": a.get("cells", []),
                    "rc": a.get("rc", []),
                    "x": data[1],
                    "y": data[2],
                    "z": _digits(data[3]),
                }
            elif tech == S.DEATH_BLOSSOM:
                out["stem"] = {
                    "cell": data[0],
                    "rc": _rc(p, data[0]),
                    "petals": [
                        {
                            "digit": data[k],
                            "als": -1 - data[k + 1],
                            "cells": als.get(-1 - data[k + 1], {}).get("cells", []),
                        }
                        for k in range(1, n - 1, 2)
                    ],
                }
        elif tag == 12:
            rules = [_constraint(p, i, info) for i in data]
            out["base"]["rules"] = rules
            out["constraints"] += rules
        elif tag == 15 and n >= 2:
            out["dominoes"] = [
                {
                    "cells": [data[k], data[k + 1]],
                    "rc": [_rc(p, data[k]), _rc(p, data[k + 1])],
                    "relation": _relkinds(p, data[k], data[k + 1]),
                }
                for k in range(0, n - 1, 2)
            ]
        elif tag == 13 and n >= 2:
            mode, v = data[:2]
            hs = [_group(p, g, info) for g in data[2:]]
            out["lock"] = {
                "mode": "must contain" if mode == 0 else "house forces the digit into the rule",
                "digit": v,
                "houses": hs,
            }
            out["cover" if mode == 0 else "base"]["units"] += hs
    for side in ("base", "cover"):
        cells = set()
        for u in out[side]["units"]:
            if u:
                cells.update(u["cells"])
        out[side]["cells"] = sorted(cells)
    if nk == _NM_NONE and m.place and not out["base"]["units"]:  # naked single: the cell's houses
        c = m.place[0]
        out["cover"]["units"] = [_group(p, gi, info) for gi in p.groups_of[c] if p.groups[gi].complete]
        out["cover"]["cells"] = sorted({x for u in out["cover"]["units"] for x in u["cells"]})
    out["digits"] = sorted(digits)
    return out


def _name(p, nk, na, nb):
    if nk == _NM_GROUP:
        return _gname(p, na)
    if nk == _NM_LOCK:
        return f"{_gname(p, na)}->{_gname(p, nb)}"
    if nk == _NM_INNIE:
        return f"innie {_gname(p, na)}"
    if nk == _NM_OUTIE:
        return f"outie {_gname(p, na)}"
    if nk == _NM_NARY:
        if na >= 0:
            nc = len(getattr(p, "constraints", ()))
            if na < nc:
                c = p.constraints[na]
                return f"{c.get('kind', c['type']) if c['type'] == 'line' else c['type']}#{na}"
            ex = getattr(p, "_cextra", [])
            if na < nc + len(ex):
                return ex[na - nc]
            return f"leftovers#{na - nc - len(ex)}"
        return f"cage {p.groups[nb].name}" if 0 <= nb < len(p.groups) else ""
    return ""
