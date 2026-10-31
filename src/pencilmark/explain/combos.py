"""Innies / outies, combinations, lines, combination locks and leftovers. (split from explain.py)"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .. import solver as S
from ..model import bit, digits_of
from .base import (
    _J,
    CONCEPTS,
    LINE_NAMES,
    _cap,
    _elim_digits,
    _elim_list,
    _generic,
    _join,
    _rel_ex,
    _result,
    _union_name,
    fmt_elims,
    rel_label,
)
from .grid import Rule, _rule_dom, enum_rule
from .singles import _con_json, _rule_from_move


# --------------------------------------------------------------- innies -----
def _house_unions(p, max_k=3):
    if getattr(p, "_xunions", None) is not None:
        return p._xunions
    hs = p.houses
    cs = {h: set(p.groups[h].cells) for h in hs}
    pos = {xy: i for i, xy in enumerate(p.coords)}
    nb = {}
    for h in hs:
        border = set()
        for c in cs[h]:
            r, cc = p.coords[c]
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = pos.get((r + dr, cc + dc))
                if q is not None and q not in cs[h]:
                    border.add(q)
        nb[h] = {h2 for h2 in hs if h2 != h and not cs[h] & cs[h2] and cs[h2] & border}
    out = {(h,) for h in hs}
    frontier = set(out)
    for _ in range(max_k - 1):
        nxt = set()
        for u in frontier:
            for h in u:
                for h2 in nb[h]:
                    if h2 in u or any(cs[h2] & cs[x] for x in u):
                        continue
                    nxt.add(tuple(sorted(u + (h2,))))
        out |= nxt
        frontier = nxt
    p._xunions = sorted(out, key=len)
    return p._xunions


def _innie_sets(p, max_cells=4):
    key = f"_xinnie{max_cells}"
    if getattr(p, key, None) is not None:
        return getattr(p, key)
    tri = p.D * (p.D + 1) // 2
    sums = [gi for gi, g in enumerate(p.groups) if g.total is not None]
    out = []
    for union in _house_unions(p):
        H = set().union(*(p.groups[h].cells for h in union))
        inside, touching = [], []
        for gi in sums:
            cs = set(p.groups[gi].cells)
            if cs <= H:
                inside.append(gi)
            elif cs & H:
                touching.append(gi)
        covered = set().union(*(p.groups[gi].cells for gi in inside)) if inside else set()
        Rr = sorted(c for c in H if c not in covered)
        if Rr and len(Rr) <= max_cells and inside:
            out.append(
                {
                    "union": union,
                    "cells": Rr,
                    "total": tri * len(union) - sum(p.groups[g].total for g in inside),
                    "cages": inside,
                    "kind": "innie",
                }
            )
        allc = inside + touching
        cov = set().union(*(p.groups[gi].cells for gi in allc)) if allc else set()
        if touching and H <= cov:
            O = sorted(cov - H)
            if len(O) <= max_cells:
                out.append(
                    {
                        "union": union,
                        "cells": O,
                        "total": sum(p.groups[g].total for g in allc) - tri * len(union),
                        "cages": allc,
                        "kind": "outie",
                    }
                )
    setattr(p, key, out)
    return out


def _find_innie(ctx, cells_needed, kind=None, max_cells=4):
    """Candidate rule-of-45 sets containing the needed cells, smallest first."""
    p = ctx.p
    hname = (ctx.m.name or "").split()[-1] if ctx.m.name else None
    hgi = ctx.gi(hname) if hname else ctx.xm.get("house")
    out = []
    for s in _innie_sets(p, max_cells):
        if kind and s["kind"] != kind:
            continue
        if hgi is not None and s["union"][0] != hgi and hgi not in s["union"]:
            continue
        if not set(cells_needed) <= set(s["cells"]):
            continue
        out.append(s)
    out.sort(key=lambda s: (len(s["union"]), len(s["cells"])))
    return out


def _h_innie(ctx):
    _nm, _p, _st = ctx.nm, ctx.p, ctx.st
    kind = "outie" if (ctx.m.name or "").startswith("outie") or ctx.xm.get("outie") else "innie"
    need = [ctx.place[0]] if ctx.place else sorted({c for c, _ in ctx.elims})
    cands = _find_innie(ctx, need, kind, max_cells=4 if ctx.tech != S.INNIE_X else 9)
    if not cands:
        return _generic(ctx)
    first = None
    for s in cands[:12]:
        r = _innie_render(ctx, s, kind)
        if r["verified"]:
            return r
        first = first or r
    return first


def _innie_render(ctx, s, kind):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    tri = p.D * (p.D + 1) // 2
    U = _union_name(nm, s["union"])
    cage_txt = " + ".join(str(p.groups[g].total) for g in s["cages"])
    cage_sum = sum(p.groups[g].total for g in s["cages"])
    house_sum = tri * len(s["union"])
    emp = [c for c in s["cells"] if not st.vals[c]]
    known = [(c, st.vals[c]) for c in s["cells"] if st.vals[c]]
    rem = s["total"] - sum(d for _, d in known)
    lines = [("cage", p.groups[g].cells) for g in s["cages"]]
    if kind == "innie":
        arith = (
            f"{_cap(U)} must total {house_sum}. The cages lying completely inside add up to "
            f"{cage_txt} = {cage_sum}, so the uncovered cell{'s' if len(s['cells']) > 1 else ''} "
            f"{nm.cells(s['cells'])} must total {house_sum} - {cage_sum} = {s['total']}"
        )
    else:
        arith = (
            f"The cages touching {U} add up to {cage_txt} = {cage_sum}; {U} itself is {house_sum}, so the "
            f"cell{'s' if len(s['cells']) > 1 else ''} poking out, {nm.cells(s['cells'])}, must total "
            f"{cage_sum} - {house_sum} = {s['total']}"
        )
    if known:
        arith += f" ({', '.join(f'{nm.cell(c)} is already {d}' for c, d in known)}, leaving {rem} for the rest)"
    ok = True
    if ctx.place:
        c, v = ctx.place
        ok = len(emp) == 1 and emp[0] == c and rem == v
        short = f"{nm.cell(c)} = {v}: rule of 45 -- the {kind} of {U}"
        teach = (
            f"{arith}. With only {nm.cell(c)} open, it must be {v}. Hunt for innies and outies by looking for "
            f"a house (or a band of houses) that cages almost cover exactly."
        )
    else:
        dom = [st.cand[c] for c in emp]
        distinct = bool(set.intersection(*(set(p.groups_of[c]) for c in emp))) if emp else False
        rule = Rule("innie", emp, f"the {kind} sum", total=rem, distinct=distinct)
        res = enum_rule(p, rule, dom)
        targets = {(emp[i], d) for i in range(len(emp)) for d in digits_of(st.cand[emp[i]] & ~res["sup"][i])}
        ok = set(ctx.elims) <= targets
        combos = _combo_sets(res, len(emp))
        short = f"{fmt_elims(nm, ctx.elims)}: rule of 45 -- the {kind} cells of {U} total {rem}"
        why = _sum_elim_reasons(ctx, rule, emp, res, rem)
        teach = (
            f"{arith}. Treat {nm.cells(emp)} as a virtual cage of {rem}"
            f"{'' if distinct else ' (digits may repeat: the cells are not all in one house)'}: "
            f"{_combo_phrase(combos, distinct)}. {why} "
            f"Rule-of-45 sums turn any nearly-covered house into an extra cage."
        )
    J = _J(
        ctx,
        digits=[ctx.place[1]] if ctx.place else _elim_digits(ctx),
        base_units=list(s["union"]),
        base_cells=s["cells"],
        constraints=[
            {"type": kind, "index": None, "cells": s["cells"], "params": {"total": s["total"], "cages": s["cages"]}}
        ],
    )
    return _result(ctx, J, short, teach, ok, lines=lines)


def _combo_sets(res, n):
    if not res["complete"] or res["count"] is None or res["count"] > len(res["sols"]):
        return [None]
    sets = []
    for sol in res["sols"]:
        k = tuple(sorted(sol))
        if k not in sets:
            sets.append(k)
    return sets


_SUMLIKE = ("sum", "cage", "little_killer", "innie", "arrow", "equal_sum")


def _combo_phrase(combos, distinct=True, limit=6, sets=False):
    if not combos:
        return "no combination fits"
    if None in combos:
        return "many digit sets still fit"
    if len(combos) > limit:
        return f"{len(combos)} different digit sets still fit"
    txt = _join([("{" + ",".join(map(str, k)) + "}") if sets else "+".join(map(str, k)) for k in combos], "or")
    return f"the only fillings left are {txt}" if len(combos) > 1 else f"the only filling left is {txt}"


# ---------------------------------------------------- combinations / lines --
def _h_combo(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    rule = _rule_from_move(ctx)
    if rule is None:
        if ctx.tech == S.LOL_COMBO:
            return _h_lol(ctx)
        return _generic(ctx)
    dom = _rule_dom(st, rule)
    res = enum_rule(p, rule, dom)
    computed = {
        (c, d) for i, c in enumerate(rule.cells) if not st.vals[c] for d in digits_of(st.cand[c] & ~res["sup"][i])
    }
    ok = set(ctx.elims) <= computed
    kind = rule.line_kind or rule.kind
    emp = [c for c in rule.cells if not st.vals[c]]
    known = [(c, st.vals[c]) for c in rule.cells if st.vals[c]]
    tg = sorted({c for c, _ in ctx.elims})
    lines = [(kind, rule.cells)]
    J = _J(ctx, digits=_elim_digits(ctx), constraints=[_con_json(rule)], base_cells=emp, cover_cells=tg)
    if ctx.tech == S.LINE_RANGE or (rule.kind == "line"):
        why = _line_reasons(ctx, rule, res)
        short = f"{fmt_elims(nm, ctx.elims)}: {LINE_NAMES.get(kind, kind)} logic"
        if kind == "whisper" and all(d == (p.D + 1) // 2 for _, d in ctx.elims) and p.D % 2:
            short = f"{fmt_elims(nm, ctx.elims)}: German whispers -- {(p.D + 1) // 2} can never appear"
        elif kind in ("thermo", "slow_thermo") and any(c == rule.cells[0] for c, _ in ctx.elims):
            short = f"{fmt_elims(nm, ctx.elims)}: thermo bulb logic"
        elif kind in ("thermo", "slow_thermo"):
            short = f"{fmt_elims(nm, ctx.elims)}: thermo counting"
        teach = f"Read {rule.label}. {why} " + _line_tip(kind)
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind in ("cage", "sum", "little_killer") and len(emp) == 1:
        total = rule.total - sum(d for _, d in known)
        c = emp[0]
        short = f"{fmt_elims(nm, ctx.elims)}: {rule.label.split(' (')[0]} needs exactly {total} there"
        teach = (
            f"{_cap(rule.label)} already holds {nm.digits([d for _, d in known], 'and')}, so its last cell "
            f"{nm.cell(c)} must be {rule.total} - {sum(d for _, d in known)} = {total}. Every other "
            f"candidate in {nm.cell(c)} goes: {nm.digits(sorted(d for _, d in ctx.elims))}."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind in ("cage", "sum", "little_killer"):
        total = rule.total - sum(d for _, d in known)
        combos = _combo_sets(res, len(rule.cells))
        n = len(emp)
        head = f"{_cap(rule.label)} has {n} empty cell{'s' if n > 1 else ''} needing {total}" + (
            f" (after the {nm.digits([d for _, d in known], 'and')} already placed)" if known else ""
        )
        reasons = _sum_elim_reasons(ctx, rule, emp, res, total)
        short = f"{fmt_elims(nm, ctx.elims)}: killer combinations for {rule.label.split(' (')[0]}"
        teach = (
            f"{head}. With the notes available, {_combo_phrase(combos)}. {reasons} "
            f"Always list a cage's possible digit sets first -- small and large totals have very few."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind == "arrow":
        circ, line = rule.con["circle"], rule.con["line"]
        lo = sum(min(digits_of(dom[rule.cells.index(c)])) for c in line)
        hi = sum(max(digits_of(dom[rule.cells.index(c)])) for c in line)
        circ_txt = nm.cells(circ)
        short = f"{fmt_elims(nm, ctx.elims)}: arrow sum bounds"
        teach = (
            f"On {rule.label}, the circle {circ_txt} equals the sum along the arrow. With the current notes "
            f"the arrow can total anywhere from {lo} to {hi}, and the circle has to match. "
            f"{_generic_rule_reason(ctx, rule, res, emp)} Bound the arrow from both ends: the smallest and "
            f"largest possible arrow sums limit the circle, and vice versa."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    if kind in ("set", "renban"):
        runs = sorted({(min(s), max(s)) for s in res["sols"]})
        rtxt = _join([f"{a}-{b}" for a, b in runs], "or")
        short = f"{fmt_elims(nm, ctx.elims)}: renban run"
        teach = (
            f"{_cap(rule.label)} needs {len(rule.cells)} consecutive digits in any order. With the candidates "
            f"available the run can only be {rtxt}, so remove {_elim_list(nm, ctx.elims)}. "
            f"On renbans, think about which runs fit before thinking about cells."
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    short = f"{fmt_elims(nm, ctx.elims)}: {rule.label.split(' (')[0]}"
    teach = f"Check {rule.label} against the notes. {_generic_rule_reason(ctx, rule, res, emp)} {CONCEPTS[ctx.tech][1]}"
    return _result(ctx, J, short, teach, ok, lines=lines)


def _rest_sums(p, st, rule, emp, c, d):
    """Sums the other empty cells of a sum rule can make when c holds d."""
    rest = [q for q in emp if q != c]
    if not rest:
        return {0}
    dom = []
    for q in rest:
        m = st.cand[q]
        if rule.distinct or q in p.peers[c]:
            m &= ~bit(d)
        dom.append(m)
    sums = set()

    def rec(i, s, used):
        if len(sums) > 60:
            return
        if i == len(rest):
            sums.add(s)
            return
        for v in digits_of(dom[i]):
            if any(v == used[j] and (rule.distinct or rest[j] in p.peers[rest[i]]) for j in range(i)):
                continue
            used.append(v)
            rec(i + 1, s + v, used)
            used.pop()

    rec(0, 0, [])
    return sums


def _sum_elim_reasons(ctx, rule, emp, res, total):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    anywhere = 0
    for i, c in enumerate(rule.cells):
        if not st.vals[c]:
            anywhere |= res["sup"][i]
    parts, never = [], []
    grouped = defaultdict(list)
    for c, d in ctx.elims:
        if res["complete"] and not anywhere & bit(d):
            never.append(d)
            continue
        need = total - d
        if len(emp) == 2:
            o = emp[0] if c == emp[1] else emp[1]
            if need == d and rule.distinct:
                parts.append(f"a {d} in {nm.cell(c)} would need a second {d} next to it")
            elif not 1 <= need <= p.D:
                parts.append(f"a {d} in {nm.cell(c)} would leave {need} for {nm.cell(o)}, which no digit can be")
            elif not st.cand[o] & bit(need):
                parts.append(
                    f"a {d} in {nm.cell(c)} would need a {need} in {nm.cell(o)}, which isn't among its "
                    f"notes {nm.cset(st.cand[o])}"
                )
            else:
                parts.append(
                    f"a {d} in {nm.cell(c)} would need a {need} in {nm.cell(o)}, which the rest of the grid forbids"
                )
            continue
        sums = _rest_sums(p, st, rule, emp, c, d)
        if sums and need > max(sums):
            grouped[(d, "max", need, max(sums))].append(c)
        elif sums and need < min(sums):
            grouped[(d, "min", need, min(sums))].append(c)
        else:
            grouped[(d, "gap", need, 0)].append(c)
    for (d, kind, need, bound), cs in grouped.items():
        where = nm.cells(cs, "or")
        if kind == "max":
            parts.append(f"a {d} in {where} leaves {need} for the other cells, but they can make at most {bound}")
        elif kind == "min":
            parts.append(f"a {d} in {where} leaves {need} for the other cells, but they add up to at least {bound}")
        else:
            parts.append(
                f"a {d} in {where} leaves {need} for the other cells, which their notes can't make with "
                f"{'different ' if rule.distinct else ''}digits"
            )
    txt = []
    if never:
        txt.append(f"no surviving combination uses {nm.digits(sorted(set(never)))} at all")
    txt += list(dict.fromkeys(parts))
    return _cap("; ".join(txt)) + "." if txt else ""


def _generic_rule_reason(ctx, rule, res, emp):
    nm = ctx.nm
    sols = res["sols"]
    if res["complete"] and 0 < len(sols) <= 4:
        fill = "; ".join(", ".join(f"{nm.cell(c)}={v}" for c, v in zip(rule.cells, s) if c in emp) for s in sols)
        return (
            f"Only {len(sols)} filling{'s' if len(sols) > 1 else ''} survive{'s' if len(sols) == 1 else ''} ({fill}), so "
            f"remove {_elim_list(nm, ctx.elims)}."
        )
    return f"Trying each candidate shows that no valid filling of the rule can use them: remove {_elim_list(nm, ctx.elims)}."


def _line_tip(kind):
    return {
        "thermo": "On a thermometer, count cells: a cell n steps from the bulb is at least n+1, and one with m cells "
        "above it is at most 9-m.",
        "slow_thermo": "On a slow thermometer digits never decrease, so neighbours bound each other.",
        "whisper": "On German whispers 5 is impossible and 4/6 are tight -- they need a 9 or a 1 next door.",
        "dutch_whisper": "On Dutch whispers neighbours differ by at least 4; 5 needs a 1 or 9 neighbour.",
        "renban": "On renbans, think about which runs fit before thinking about cells.",
        "palindrome": "A palindrome reads the same both ways: mirrored cells share their candidates.",
        "kropki_chain": "White dots need consecutive digits, black dots a 1:2 ratio -- chains of dots are very "
        "restrictive.",
        "between": "Cells on a between line lie strictly between the two circles' digits.",
        "entropic": "Every three consecutive cells on an entropic line hold one low, one middle and one high digit.",
        "modular": "Every three consecutive cells on a modular line hold one digit from each of {1,4,7}, {2,5,8}, "
        "{3,6,9}.",
        "parity": "Neighbours on a parity line alternate odd and even.",
        "region_sum": "Each box segment of a region-sum line has the same total.",
        "zipper": "Pairs equidistant from the zipper's centre add up to the same total.",
    }.get(kind, "")


def _line_reasons(ctx, rule, res):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    kind = rule.line_kind or rule.kind
    cells = rule.cells
    dom = _rule_dom(st, rule)
    parts = []
    generic = defaultdict(list)
    by_cell = defaultdict(list)
    for c, d in ctx.elims:
        by_cell[c].append(d)
    for c in nm.sort(by_cell) if kind not in ("thermo", "slow_thermo") else [x for x in cells if x in by_cell]:
        ds = sorted(by_cell[c])
        i = cells.index(c) if c in cells else -1
        txt = None
        if kind in ("thermo", "slow_thermo") and i >= 0:
            strict = kind == "thermo"
            lo_prev = min(digits_of(dom[i - 1])) if i > 0 else 0
            hi_next = max(digits_of(dom[i + 1])) if i + 1 < len(cells) else p.D + 1
            low = [d for d in ds if d < lo_prev + strict]
            high = [d for d in ds if d > hi_next - strict]
            seg = []
            if low:
                seg.append(
                    f"{nm.cell(cells[i - 1])} below it is at least {lo_prev}, so {nm.cell(c)} can't be {nm.digits(low)}"
                )
            if high:
                seg.append(
                    f"{nm.cell(cells[i + 1])} above it is at most {hi_next}, so {nm.cell(c)} can't be {nm.digits(high)}"
                )
            if i == 0 and not low and high and len(cells) > 1:
                pass
            if seg and len(low) + len(high) == len(ds):
                pos = f"{nm.cell(c)} is cell {i + 1} of {len(cells)} on the thermo: "
                txt = pos + "; ".join(seg)
        elif kind in ("whisper", "dutch_whisper") and i >= 0:
            k = rule.con.get("k", 5 if kind == "whisper" else 4)
            nbs = [cells[j] for j in (i - 1, i + 1) if 0 <= j < len(cells)]
            seg = []
            for d in ds:
                if all(abs(w - d) < k for w in range(1, p.D + 1)):
                    seg.append(f"{d} has no partner {k} or more away on a 1-{p.D} grid")
                    continue
                for q in nbs:
                    dq = dom[cells.index(q)]
                    if not any(abs(w - d) >= k for w in digits_of(dq)):
                        seg.append(
                            f"{d} would need a neighbour {k}+ away, but {nm.cell(q)} can only be "
                            f"{nm.digits(digits_of(dq))}"
                        )
                        break
                else:
                    if len(nbs) == 2 and nbs[1] in p.peers[nbs[0]]:
                        far = [w for w in range(1, p.D + 1) if abs(w - d) >= k]
                        if len(far) == 1:
                            seg.append(
                                f"{d} would force both neighbours {nm.cell(nbs[0])} and {nm.cell(nbs[1])} to "
                                f"be {far[0]}, but they see each other"
                            )
            if len(seg) == len(ds):
                txt = f"At {nm.cell(c)}: " + "; ".join(seg)
        elif kind == "palindrome" and i >= 0:
            j = len(cells) - 1 - i
            q = cells[j]
            if q != c:
                txt = (
                    f"{nm.cell(c)} mirrors {nm.cell(q)}, which can only be {nm.digits(digits_of(dom[j]))}, "
                    f"so {nm.cell(c)} can't be {nm.digits(ds)}"
                )
        elif kind == "kropki_chain" and i >= 0:
            nbs = [j for j in (i - 1, i + 1) if 0 <= j < len(cells)]
            for j in nbs:
                q = cells[j]
                bad = [d for d in ds if not any(not _rel_ex(p, c, q, d) & bit(w) for w in digits_of(dom[j]))]
                if len(bad) == len(ds):
                    txt = (
                        f"{nm.cell(c)} is dotted to {nm.cell(q)} ({rel_label(p, c, q)}), which can only be "
                        f"{nm.digits(digits_of(dom[j]))} -- none pairs with {nm.digits(ds)}"
                    )
                    break
        if txt is None:
            generic[tuple(ds)].append(c)
            continue
        parts.append(txt)
    for ds, cs in generic.items():
        parts.append(f"no valid filling of the line can put {nm.digits(ds)} in {nm.cells(cs)}")
    if rule.segs and kind in ("region_sum", "zipper", "equal_sum"):
        seg_txt = _segment_sums(nm, p, st, rule, dom)
        if seg_txt:
            parts.insert(0, seg_txt)
    if kind in ("renban",):
        runs = sorted({(min(s), max(s)) for s in res["sols"]})
        return f"The run can only be {_join([f'{a}-{b}' for a, b in runs], 'or')}; {'; '.join(parts)}."
    fills = ""
    if res["complete"] and 0 < len(res["sols"]) <= 3 and any(t.startswith("no valid") for t in parts):
        fills = (
            " The fillings that still work: "
            + "; ".join("-".join(str(v) for v in s) for s in res["sols"])
            + f" (reading {nm.span(cells)})."
        )
    return _cap("; ".join(parts)) + "." + fills


def _segment_sums(nm, p, st, rule, dom):
    """'each segment must total the same: r1c1 alone can make 3-5, r2c2+r2c3 can make 4-11 ...'."""
    pos = {c: i for i, c in enumerate(rule.cells)}
    seg_sums = []
    for seg in rule.segs:
        sums = set()

        def rec(i, tot, used):
            if len(sums) > 40:
                return
            if i == len(seg):
                sums.add(tot)
                return
            for v in digits_of(dom[pos[seg[i]]]):
                if any(u == v and seg[j] in p.peers[seg[i]] for j, u in enumerate(used)):
                    continue
                rec(i + 1, tot + v, used + [v])

        rec(0, 0, [])
        seg_sums.append(sums)
    if not all(seg_sums):
        return ""
    common = set.intersection(*seg_sums)
    if not common:
        return ""

    def rng(xs):
        xs = sorted(xs)
        runs, start = [], xs[0]
        for a, b in zip(xs, xs[1:] + [None]):
            if b != a + 1:
                runs.append(f"{start}" if start == a else f"{start}-{a}")
                start = b
        return ", ".join(runs)

    tight = sorted(range(len(rule.segs)), key=lambda i: len(seg_sums[i]))[:2]
    seg_desc = "; ".join(f"{nm.cells(rule.segs[i])} can only total {rng(seg_sums[i])}" for i in tight)
    return f"every segment must have the same total; {seg_desc} -- so the common total is {rng(common)}"


# ---------------------------------------------------------- combo lock ------
def _must_contain(p, st, rule, v):
    """Every valid filling of the rule (with the current notes) uses digit v."""
    if any(st.vals[c] == v for c in rule.cells):
        return True
    dom = [m if st.vals[c] else m for c, m in zip(rule.cells, _rule_dom(st, rule))]
    dom = [m if st.vals[c] else m & ~bit(v) for c, m in zip(rule.cells, dom)]
    if any(m == 0 for m in dom):
        return True
    res = enum_rule(p, rule, dom)
    return res["complete"] and not any(res["sup"])


class _ReqRule(Rule):
    def __init__(self, base, v, idx):
        super().__init__(
            base.kind,
            base.cells,
            base.label,
            base.index,
            base.group,
            base.con,
            base.total,
            base.segs,
            base.line_kind,
            base.distinct,
        )
        self.v, self.idx = v, idx

    def check(self, a):
        return any(a[i] == self.v for i in self.idx) and super().check(a)


def _required_elims(p, st, rule, v, poss, res=None):
    """Eliminations when the rule must place v in one of `poss`."""
    res = res or enum_rule(p, rule, _rule_dom(st, rule))
    rr = _ReqRule(rule, v, [rule.cells.index(c) for c in poss if c in rule.cells])
    r2 = enum_rule(p, rr, _rule_dom(st, rule))  # inexact support only over-keeps -> still sound
    return {
        (c, d)
        for i, c in enumerate(rule.cells)
        if not st.vals[c]
        for d in digits_of(st.cand[c] & res["sup"][i] & ~r2["sup"][i])
    }


def _innie_rule(nm, p, s):
    common = set.intersection(*(set(p.groups_of[c]) for c in s["cells"]))
    lab = (
        f"the {s['kind']} region of {_union_name(nm, s['union'])} ({nm.cells(s['cells'])}, "
        f"which must total {s['total']} by the rule of 45)"
    )
    r = Rule("innie", s["cells"], lab, total=s["total"], distinct=bool(common))
    r.union = s["union"]
    return r


def _lock_region(ctx, v, mode):
    """Must-contain lock on a solver-derived rule-of-45 region: find the region."""
    p, st, nm = ctx.p, ctx.st, ctx.nm
    gi = ctx.xm.get("group")
    tcells = {c for c, _ in ctx.elims}
    for s in _innie_sets(p, max_cells=9):
        cells = set(s["cells"])
        if mode == 0:
            if tcells & cells or gi is None or gi < 0:
                continue
            U = [c for c in s["cells"] if not st.vals[c] and st.cand[c] & bit(v)]
            if not U or not all(c in p.groups[gi].cells for c in U):
                continue
            span = set()
            for g in p.groups_of[U[0]]:
                if all(c in p.groups[g].cells for c in U):
                    span |= set(p.groups[g].cells)
            if not tcells <= span:
                continue
        else:
            hi = ctx.xm.get("group")
            if hi is None or hi < 0 or not tcells <= cells:
                continue
            poss = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(v)]
            if not poss or not set(poss) <= cells:
                continue
        rule = _innie_rule(nm, p, s)
        res = enum_rule(p, rule, _rule_dom(st, rule))
        if not res["complete"] or not res["count"]:
            continue
        if mode == 0 and not _must_contain(p, st, rule, v):
            continue
        if mode == 1 and not set(ctx.elims) <= _required_elims(p, st, rule, v, poss, res):
            continue
        return rule, res
    return None, None


def _h_combo_lock(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    rule = _rule_from_move(ctx)
    v = ctx.xm.get("digit") or (_elim_digits(ctx)[0] if ctx.elims else None)
    mode = ctx.xm.get("mode", 0)
    res = None
    if rule is None:
        rule, res = _lock_region(ctx, v, mode)
    if rule is None:
        return _generic(ctx)
    if res is None:
        res = enum_rule(p, rule, _rule_dom(st, rule))
    combos = _combo_sets(res, len(rule.cells))
    tg = sorted({c for c, _ in ctx.elims})
    lines = [(rule.line_kind or rule.kind, rule.cells)]
    union_units = list(getattr(rule, "union", ()))
    if mode == 0:
        U = [c for c in rule.cells if not st.vals[c] and st.cand[c] & bit(v)]
        own = rule.group
        gs = [g for g in (p.groups_of[U[0]] if U else ()) if g != own and all(c in p.groups[g].cells for c in U)]
        gs = [g for g in gs if any(c in p.groups[g].cells for c in tg)] or gs
        uniq = {}
        for g in sorted(gs, key=lambda g: (p.groups[g].kind == "cage", g)):
            uniq.setdefault(frozenset(p.groups[g].cells), g)
        gs = list(uniq.values())
        must = _must_contain(p, st, rule, v)
        ok = must and bool(gs) and all(any(c in p.groups[g].cells for g in gs) for c in tg)
        ctext = f" ({_combo_phrase(combos, sets=rule.kind not in _SUMLIKE)})" if combos and len(combos) <= 5 else ""
        gn = _join([nm.unit(g) for g in gs])
        short = f"{fmt_elims(nm, ctx.elims)}: {rule.label.split(' (')[0]} must contain a {v}"
        if rule.line_kind == "renban":
            short = f"{fmt_elims(nm, ctx.elims)}: renban -- the line {nm.span(rule.cells)} must contain a {v}"
        what = (
            "cage"
            if rule.kind == "cage"
            else "region"
            if rule.kind == "innie"
            else "line"
            if rule.line_kind
            else "rule"
        )
        teach = (
            f"Every way to fill {rule.label} uses a {v}{ctext}. Inside it, the {v} can only go in "
            f"{nm.cells(U, 'or')}, all in {gn} -- so that {v} is also {gn}'s {v}, and "
            f"{nm.cells(tg)} can't be {v}. Digits that every combination needs behave like pointing "
            f"candidates: find them by listing the {what}'s possible digit sets."
        )
        J = _J(
            ctx, digits=[v], constraints=[_con_json(rule)], base_cells=U, base_units=gs + union_units, cover_cells=tg
        )
        return _result(ctx, J, short, teach, ok, lines=lines)
    hi = ctx.xm.get("group")
    poss = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(v)] if hi is not None else []
    ok = (
        bool(poss)
        and all(c in rule.cells for c in poss)
        and set(ctx.elims) <= _required_elims(p, st, rule, v, poss, res)
    )
    with_v = [s for s in combos if s and v in s]
    short = f"{fmt_elims(nm, ctx.elims)}: {nm.unit(hi)} forces a {v} into {rule.label.split(' (')[0]}"
    teach = (
        f"{_cap(nm.unit(hi))} can only place its {v} in {nm.cells(poss, 'or')}, all inside {rule.label}. So "
        f"that rule must contain a {v}"
        + (f": {_combo_phrase(with_v, sets=rule.kind not in _SUMLIKE)}" if with_v and len(with_v) <= 5 else "")
        + f". Combinations without a {v} are out, which removes {_elim_list(nm, ctx.elims)}."
    )
    J = _J(
        ctx,
        digits=[v],
        constraints=[_con_json(rule)],
        base_cells=poss,
        base_units=([hi] if hi is not None else []) + union_units,
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, ok, lines=lines)


# ---------------------------------------------------------- leftovers -------
def _lol_candidates(p):
    if getattr(p, "_xlol", None) is not None:
        return p._xlol
    out = []
    seen = set()
    for orient in ("row", "col"):
        lines = [gi for gi in p.houses if p.groups[gi].kind == orient and len(p.groups[gi].cells) == p.D]
        lines.sort(key=lambda gi: p.coords[p.groups[gi].cells[0]][0 if orient == "row" else 1])
        regs = [
            gi
            for gi in p.houses
            if p.groups[gi].kind not in ("row", "col", "implied") and len(p.groups[gi].cells) == p.D
        ]
        for k in range(1, min(4, len(lines)) + 1):
            for ls in combinations(lines, k):
                U = set().union(*(p.groups[g].cells for g in ls))
                touch = [r for r in regs if len(U & set(p.groups[r].cells)) >= p.D - 6]
                for ch in combinations(touch, k):
                    if any(set(p.groups[a].cells) & set(p.groups[b].cells) for a, b in combinations(ch, 2)):
                        continue
                    V = set().union(*(p.groups[g].cells for g in ch))
                    A, B = sorted(U - V), sorted(V - U)
                    if not A or len(A) > 6 or len(A) != len(B):
                        continue
                    key = (tuple(A), tuple(B))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"lines": ls, "regs": ch, "A": A, "B": B})
    p._xlol = out
    return out


def _sameset_elims(p, st, A, B):
    d = {c: (bit(st.vals[c]) if st.vals[c] else st.cand[c]) for c in A + B}
    orig = dict(d)
    for _ in range(8):
        ch = False
        for side, other in ((A, B), (B, A)):
            om = 0
            for c in other:
                om |= d[c]
            for c in side:
                if d[c] & ~om:
                    d[c] &= om
                    ch = True
        if not ch:
            break
    return {(c, v) for c in A + B if not st.vals[c] for v in digits_of(orig[c] & ~d[c])}


def _h_lol(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    if ctx.code in ("PHI", "Phistomefel variant"):
        pc = (ctx.raw_engine or {}).get("pattern_cells") or []
        ring = ctx.code == "PHI"
        what = (
            "the four 2x2 corner blocks hold exactly the same digits as the 16-cell ring around the centre box"
            if ring
            else "a Phistomefel-style set equality: rows and columns mirrored about the centre, minus "
            "the boxes they cover, leave two groups of cells with exactly the same digits"
        )
        teach = (
            f"Phistomefel{' ring' if ring else ' variant'}: {what} (count rows, columns and boxes: every digit "
            f"appears equally often on both sides). Among {nm.cells(pc)}, a digit that cannot appear on one "
            f"side cannot appear on the other. So {fmt_elims(nm, ctx.elims)}."
        )
        J = _J(ctx, digits=_elim_digits(ctx), base_cells=pc)
        return _result(
            ctx, J, f"{fmt_elims(nm, ctx.elims)}: Phistomefel{' ring' if ring else ' variant'}", teach, bool(pc)
        )
    tset = set(ctx.elims)
    best = None
    for s in _lol_candidates(p):
        cells = set(s["A"]) | set(s["B"])
        if not {c for c, _ in tset} <= cells:
            continue
        if tset <= _sameset_elims(p, st, s["A"], s["B"]):
            if best is None or len(s["lines"]) < len(best["lines"]):
                best = s
    if best is None:
        return _generic(ctx)
    A, B = best["A"], best["B"]
    ln = _union_name(nm, best["lines"])
    rg = _union_name(nm, best["regs"])
    parts = []
    by_d = defaultdict(list)
    for c, d in ctx.elims:
        by_d[d].append(c)
    for d, cs in sorted(by_d.items()):
        other = B if cs[0] in A else A
        parts.append(f"{d} can't appear among {nm.cells(other)}, so it can't be in {nm.cells(cs)} either")
    short = f"{fmt_elims(nm, ctx.elims)}: law of leftovers ({ln} vs {rg})"
    times = {1: "once", 2: "twice"}.get(len(best["lines"]), f"{len(best['lines'])} times")
    teach = (
        f"Compare {ln} with {rg}: both contain every digit {times}, and they share all cells except the leftovers -- "
        f"{nm.cells(A)} on one side and {nm.cells(B)} on the other. Removing the common cells from both, the "
        f"leftovers must hold exactly the same digits. {_cap('; '.join(parts))}. "
        f"Set equivalence is powerful in jigsaws and anywhere boxes stick out of a band of lines."
    )
    J = _J(
        ctx,
        digits=_elim_digits(ctx),
        base_units=list(best["lines"]),
        cover_units=list(best["regs"]),
        base_cells=A,
        cover_cells=B,
    )
    return _result(ctx, J, short, teach, True)
