"""Explanations of singles, the no-notes layer and n-ary rule steps. (split from explain.py)"""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations

from .. import solver as S
from ..model import bit, digits_of, popcount
from .base import _J, CONCEPTS, _cap, _generic, _join, _result, _union_name, rel_label
from .grid import (
    _cage_direct,
    _lock_text,
    _mental_reason_text,
    _source_text,
    direct_excl,
    direct_locks,
    direct_sources,
    enum_rule,
    mental_view,
    rules,
)


# ============================================================ singles ========
def _h_full_house(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    gi = ctx.gi(ctx.m.name)
    if gi is None:
        gi = next(
            h for h in p.houses if c in p.groups[h].cells and sum(1 for q in p.groups[h].cells if not st.vals[q]) == 1
        )
    u = nm.unit(gi)
    ok = sum(1 for q in p.groups[gi].cells if not st.vals[q]) == 1 and not st.placed_g(gi) & bit(v)
    short = f"{nm.cell(c)} = {v}: last empty cell of {u}"
    teach = ctx.pick(
        [
            f"{_cap(u)} has only one empty cell left, {nm.cell(c)}, and the only digit {u} is still missing is {v}. "
            f"Full houses are free -- after each placement, glance along its row, column and box for a house that "
            f"is one short.",
            f"Count what's missing in {u}: every digit except {v} is already there, and {nm.cell(c)} is the one gap. "
            f"Nothing else to check -- {nm.cell(c)} is {v}.",
            f"{_cap(u)} is down to a single gap at {nm.cell(c)}. The digit it lacks is {v}, so that's the answer -- "
            f"a full house is always the first thing to look for once a house fills up.",
        ]
    )
    g = p.groups[gi]
    if g.kind == "implied" and getattr(g, "src", None):
        lines, removed = g.src
        rem = [nm.gidx[r] if isinstance(r, str) else r for r in removed]
        k = len(lines)
        short = f"{nm.cell(c)} = {v}: last empty cell of an implied house"
        teach = (
            f"{_cap(_union_name(nm, lines))} together contain every digit {k} times. "
            f"{_cap(_join([nm.unit(r) for r in rem]))} lie{'s' if len(rem) == 1 else ''} entirely inside them, "
            f"so the {p.D} cells left over ({nm.cells(g.cells)}) must contain every digit exactly once -- an "
            f"invisible extra house. Only {nm.cell(c)} is empty there, and the digit missing from it is {v}. "
            f"Look for these in jigsaws and puzzles with extra regions."
        )
        J = _J(ctx, digits=[v], base_units=[gi] + list(lines) + rem, base_cells=list(g.cells))
        return _result(ctx, J, short, teach, ok)
    J = _J(ctx, digits=[v], base_units=[gi], base_cells=[q for q in p.groups[gi].cells])
    return _result(ctx, J, short, teach, ok)


def _naked_cover(p, st, c, v, srcs):
    target = p.full & ~bit(v)
    for k in range(1, len(srcs) + 1):
        for combo in combinations(srcs, k):
            m = 0
            for s in combo:
                m |= s[1]
            if m & target == target:
                return sorted(combo, key=lambda s: -popcount(s[1]))
    return None


def _cover_phrases(nm, c, chosen, v):
    """Ordered exclusion sources -> phrases that add NEW digits each time."""
    seen = 0
    phrases = []
    for i, (kind, m, info) in enumerate(chosen):
        new = m & ~seen & ~bit(v)
        if not new:
            continue
        ds = list(digits_of(new))
        if kind == "house":
            gi, where = info
            txt = f"{nm.unit(gi)} {'already has' if i == 0 else 'adds'} {nm.digits(ds, 'and')}"
        else:
            txt = _source_text(nm, kind, info, ds, c)
        phrases.append(txt)
        seen |= m
    return phrases


def _h_naked_direct(ctx, locks=None):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    srcs = direct_sources(p, st, c)
    lock_used = []
    if locks is not None:
        for lk in locks:
            if c in lk["targets"]:
                m = lk.get("mask", bit(lk["v"])) if lk["rel"] else bit(lk["v"])
                srcs.append(("lock", m, {"text": _lock_text(nm, lk), "lk": lk}))
    chosen = _naked_cover(p, st, c, v, srcs)
    ok = chosen is not None
    if not ok:
        chosen = sorted(srcs, key=lambda s: -popcount(s[1]))
    for s in chosen:
        if s[0] == "lock":
            lock_used.append(s[2]["lk"])
    phrases = _cover_phrases(nm, c, [x for x in chosen if x[0] != "lock"], v)
    excluded = 0
    for s in chosen:
        excluded |= s[1]
    n_out = popcount(excluded & ~bit(v))
    base_units = [s[2][0] for s in chosen if s[0] == "house"]
    base_cells = [q for s in chosen if s[0] == "house" for q in s[2][1].values()]
    base_cells += [s[2][0] for s in chosen if s[0] in ("neq", "rel")]
    for lk in lock_used:
        base_cells += lk["poss"]
        base_units += [lk["B"]] + ([lk["A"]] if lk["A"] is not None else [])
    seen_txt = "; ".join(phrases)
    if locks is not None and lock_used:
        lk = lock_used[0]
        short = f"{nm.cell(c)} = {v}: naked single once the pointing {lk['v']} in {nm.unit(lk['B'])} is counted"
        teach = (
            f"Collect what {nm.cell(c)} can see: {seen_txt}. The trick is the digit that isn't written yet -- "
            f"{_lock_text(nm, lk)}, which removes {lk['v']} from {nm.cell(c)} too. That leaves only {v}. "
            f"When a cell is one digit short of a single, look for a box where the missing digit is confined "
            f"to one line."
        )
    else:
        short = (
            f"{nm.cell(c)} = {v}: every other digit is already in its row, column or box"
            if all(s[0] == "house" for s in chosen)
            else f"{nm.cell(c)} = {v}: naked single, all other digits ruled out"
        )
        teach = ctx.pick(
            [
                f"Look at {nm.cell(c)} and collect what it sees: {seen_txt}. That rules out {n_out} different digits, "
                f"so {v} is the only one left. Naked singles hide in cells whose row, column and box are each fairly "
                f"full -- scan the busiest crossings.",
                f"Count the digits around {nm.cell(c)}: {seen_txt}. Between them every digit except {v} is taken, so "
                f"{nm.cell(c)} must be {v}.",
                f"{nm.cell(c)} sits where several busy houses cross: {seen_txt}. Only {v} survives -- a naked single. "
                f"Cells at the intersection of crowded houses are the best place to hunt for these.",
            ]
        )
    J = _J(ctx, digits=[v], base_units=list(dict.fromkeys(base_units)), base_cells=base_cells)
    return _result(ctx, J, short, teach, ok)


def _hidden_cover(p, st, house_gi, c, v, extra_srcs=()):
    """Cover the other empty cells of the house for digit v. -> (chosen sources, uncovered)."""
    others = [q for q in p.groups[house_gi].cells if not st.vals[q] and q != c]
    srcs = {}
    b = bit(v)
    for y in others:
        for gi in p.groups_of[y]:
            if gi == house_gi:
                continue
            for q in p.groups[gi].cells:
                if st.vals[q] == v:
                    key = ("house", gi, q)
                    srcs.setdefault(key, set()).update(x for x in others if x in p.groups[gi].cells)
        for q in p.neq[y]:
            if st.vals[q] == v:
                srcs.setdefault(("neq", q), set()).update(x for x in others if x in p.neq[q])
        for q in p.nonconsec[y]:
            if st.vals[q] and p.rel_ex[q][y][st.vals[q]] & b:
                srcs.setdefault(("rel", q), set()).update(
                    x for x in others if x in p.rel_ex[q] and p.rel_ex[q][x][st.vals[q]] & b
                )
        if not p.domains[y] & b:
            srcs.setdefault(("domain", y), set()).add(y)
        for gi in p.groups_of[y]:
            g = p.groups[gi]
            if g.total is not None and not _cage_direct(p, st, gi) & b and not st.placed_g(gi) & b:
                srcs.setdefault(("cagesum", gi), set()).update(x for x in others if x in g.cells)
    for key, cov in extra_srcs:
        srcs.setdefault(key, set()).update(x for x in others if x in cov)
    left = set(others)
    chosen = []
    items = sorted(srcs.items(), key=lambda kv: (kv[0][0] != "house", repr(kv[0])))
    while left:
        best = max(items, key=lambda kv: (len(kv[1] & left), kv[0][0] == "house"), default=None)
        if best is None or not best[1] & left:
            break
        chosen.append((best[0], sorted(best[1] & left)))
        left -= best[1]
    return chosen, sorted(left), others


def _hidden_phrase(nm, key, cov, v, house_gi, st=None, lock_by_key=None):
    p = nm.p
    kind = key[0]
    if kind == "house":
        _, gi, q = key
        return f"the {v} in {nm.cell(q)} covers {nm.unit(gi)}"
    if kind == "neq":
        q = key[1]
        return f"the {v} in {nm.cell(q)} blocks {nm.cells(cov)} ({rel_label(p, q, cov[0])})"
    if kind == "rel":
        q = key[1]
        return f"the {st.vals[q]} in {nm.cell(q)} rules out {v} at {nm.cells(cov)} via the {rel_label(p, q, cov[0])}"
    if kind == "domain":
        return f"{nm.cell(key[1])} is a shaded {'even' if v % 2 else 'odd'} cell"
    if kind == "cagesum":
        return f"{nm.cage(key[1], cells=False)} can't fit a {v} at {nm.cells(cov)}"
    if kind == "lock":
        return lock_by_key[key]
    return ""


def _h_hidden_direct(ctx, locks=None):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    gi = ctx.gi(ctx.m.name)
    if gi is None:
        gi = next(h for h in p.houses if c in p.groups[h].cells)
    extra, lock_txt = [], {}
    if locks is not None:
        for k, lk in enumerate(locks):
            if lk["v"] == v and not lk["rel"] and lk["B"] != gi:
                key = ("lock", k)
                extra.append((key, lk["targets"]))
                lock_txt[key] = _lock_text(nm, lk) + ", blocking {cells}"
            elif lk["rel"] and lk.get("mask", 0) & bit(v):
                key = ("lock", k)
                extra.append((key, lk["targets"]))
                lock_txt[key] = _lock_text(nm, lk) + " (so it can't be " + str(v) + ")"
    chosen, left, others = _hidden_cover(p, st, gi, c, v, extra)
    ok = not left
    phrases = []
    base_cells, base_units, _lines = [], [gi], []
    for key, cov in chosen:
        if key[0] == "lock":
            phrases.append(lock_txt[key].replace("{cells}", nm.cells(cov)))
            lk = locks[key[1]]
            base_cells += lk["poss"]
            base_units += [lk["B"]] + ([lk["A"]] if lk["A"] is not None else [])
        else:
            phrases.append(_hidden_phrase(nm, key, cov, v, gi, st))
            if key[0] == "house":
                base_units.append(key[1])
                base_cells.append(key[2])
            elif key[0] in ("neq", "rel"):
                base_cells.append(key[1])
    u = nm.unit(gi)
    n_emp = len(others) + 1
    if locks is not None and any(k[0] == "lock" for k, _ in chosen):
        short = f"{nm.cell(c)} = {v}: only place for {v} in {u} once a pointing {v} is used"
        teach = (
            f"Where can {v} go in {u}? {_cap('; '.join(phrases))}. That leaves {nm.cell(c)} as the only spot. "
            f"The key step is using a {v} that isn't written yet but is already pinned to one line of a box -- "
            f"it blocks that line just like a real {v}."
        )
    else:
        hint = (
            "This is cross-hatching, the fastest scan: pick a digit and sweep its rows and columns through the box."
            if p.groups[gi].kind == "box"
            else f"Lines with few empty cells are good places to ask 'where does the {v} go?'"
        )
        short = ctx.pick(
            [f"{nm.cell(c)} = {v}: the only place for a {v} in {u}", f"{nm.cell(c)} = {v}: hidden single, {v} in {u}"]
        )
        if not others:
            teach = f"{nm.cell(c)} is the only empty cell of {u} and {v} is missing there."
        else:
            teach = ctx.pick(
                [
                    f"Ask where the {v} goes in {u} ({n_emp} empty cells). {_cap('; '.join(phrases))}. That leaves only "
                    f"{nm.cell(c)}. {hint}",
                    f"Focus on the {v}s around {u}: {'; '.join(phrases)}. Every other empty cell of {u} is blocked, so "
                    f"{nm.cell(c)} must be the {v}. {hint}",
                    f"{_cap(u)} still needs a {v}. {_cap('; '.join(phrases))} -- so the {v} has nowhere to go except "
                    f"{nm.cell(c)}.",
                ]
            )
    J = _J(ctx, digits=[v], base_units=list(dict.fromkeys(base_units)), base_cells=base_cells, cover_cells=others)
    return _result(ctx, J, short, teach, ok)


def _h_pointing_direct(ctx):
    locks, _ = direct_locks(ctx.p, ctx.st)
    if ctx.tech == S.NAKED_DL:
        return _h_naked_direct(ctx, locks)
    return _h_hidden_direct(ctx, locks)


def _since(ctx, c, d):
    """'(it lost 5 to the X-Wing two moves ago)'."""
    t = ctx.st.lost.get((c, d))
    if not t:
        return ""
    idx, tech = t
    ago = ctx.st.idx - idx
    if ago <= 0 or tech in (S.TAKE_NOTES,):
        return ""
    name = CONCEPTS[tech][0] if tech in CONCEPTS else _pretty_tech(tech)
    when = "on the previous move" if ago == 1 else f"{ago} moves ago"
    return f"its {d} went {when} ({name[0].lower() + name[1:] if name[:2] != name[:2].upper() else name})"


def _pretty_tech(tech):
    """Readable name for an engine code without a CONCEPTS entry: '3DMedusa' -> '3D Medusa'."""
    raw = re.sub(r"\((?:direct|notes)\)", "", S.TECH_NAMES.get(tech, "a technique")).strip()
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", raw)


def _h_naked_notes(ctx):
    nm, st = ctx.nm, ctx.st
    c, v = ctx.place
    ok = st.cand[c] == bit(v)
    lost = sorted(((t[0], d) for (q, d), t in st.lost.items() if q == c and d != v), reverse=True)
    recent = _since(ctx, c, lost[0][1]) if lost else ""
    short = f"{nm.cell(c)} = {v}: its only remaining candidate"
    teach = (
        f"{nm.cell(c)}'s pencil marks are down to {nm.cset(st.cand[c])}."
        + (f" The last alternative disappeared recently -- {recent}." if recent else "")
        + f" A cell with one candidate is solved: write {v}, then clean {v} out of its row, column and box."
    )
    J = _J(ctx, digits=[v], base_cells=[c])
    return _result(ctx, J, short, teach, ok)


def _h_hidden_notes(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    gi = ctx.gi(ctx.m.name)
    if gi is None:
        gi = next(h for h in p.houses if c in p.groups[h].cells)
    others = [q for q in p.groups[gi].cells if not st.vals[q] and q != c]
    ok = all(not st.cand[q] & bit(v) for q in others) and st.cand[c] & bit(v)
    u = nm.unit(gi)
    short = f"{nm.cell(c)} = {v}: the only {v} left in the notes of {u}"
    teach = ctx.pick(
        [
            f"Scan the notes of {u} for the digit {v}: it appears only in {nm.cell(c)} {nm.cset(st.cand[c])}. "
            f"Even though that cell has other candidates, {u} needs a {v} somewhere, so {nm.cell(c)} is it.",
            f"In {u}, {v} has been squeezed down to a single cell, {nm.cell(c)}. A hidden single in the notes is easy "
            f"to miss because the cell still shows several candidates -- scan one digit at a time across a house.",
        ]
    )
    J = _J(ctx, digits=[v], base_units=[gi], base_cells=[c], cover_cells=others)
    return _result(ctx, J, short, teach, ok)


# ----------------------------------------------- direct line / mental singles --
def _h_mental(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    md, reasons = mental_view(p, st, level=3)
    hidden = bool(ctx.xm.get("hidden"))
    lines = []
    base_units, base_cells = [], []
    parts = []
    ok = False
    used_rules = set()

    def why(q, d):
        if direct_excl(p, st, q) & bit(d):
            srcs = [s for s in direct_sources(p, st, q) if s[1] & bit(d)]
            s = srcs[0]
            if s[0] == "house":
                gi, where = s[2]
                base_cells.append(where[d])
                return f"the {d} in {nm.cell(where[d])} sees it"
            return _source_text(nm, s[0], s[2], [d], q)
        r = reasons.get((q, d))
        if r is None:
            return None
        if r[0] == "rule":
            used_rules.add(r[1])
        if r[0] == "arc":
            base_cells.append(r[1])
        if r[0] in ("subset",):
            base_units.append(r[1])
            base_cells.extend(r[2])
        if r[0] == "point":
            base_units.extend([r[1], r[2]])
            base_cells.extend(r[4])
        return _mental_reason_text(nm, q, d, r, st)

    house = None
    if hidden:
        for gi in p.groups_of[c]:
            if not p.groups[gi].complete:
                continue
            others = [q for q in p.groups[gi].cells if not st.vals[q] and q != c]
            if all(not md[q] & bit(v) for q in others) and not st.placed_g(gi) & bit(v):
                house = gi
                break
    if house is not None:
        others = [q for q in p.groups[house].cells if not st.vals[q] and q != c]
        direct_blocked = [q for q in others if direct_excl(p, st, q) & bit(v)]
        tricky = [q for q in others if q not in direct_blocked]
        for q in tricky:
            w = why(q, v)
            parts.append(f"{nm.cell(q)} can't be {v} because {w}" if w else f"{nm.cell(q)} is ruled out")
        ok = all(why(q, v) for q in tricky)
        base_units.append(house)
        u = nm.unit(house)
        short = (
            f"{nm.cell(c)} = {v}: the only place for {v} in {u} once the line logic is applied"
            if used_rules
            else f"{nm.cell(c)} = {v}: the only place for {v} in {u}, with a little reasoning in your head"
        )
        scan = (
            f"Ordinary scanning blocks {len(direct_blocked)} of the {len(others) + 1} empty cells "
            f"({nm.cells(direct_blocked)})"
            if direct_blocked
            else "Ordinary scanning doesn't settle it"
        )
        teach = (
            f"Where does the {v} go in {u}? {scan}. "
            f"The rest need a little thought: {'; '.join(parts)}. So {nm.cell(c)} is the {v}."
        )
    else:
        ex = direct_excl(p, st, c)
        rest = [d for d in digits_of(p.full & ~ex) if d != v]
        srcs = direct_sources(p, st, c)
        seen = _cover_phrases(nm, c, sorted(srcs, key=lambda s: -popcount(s[1])), v)
        for kd, _, info in srcs:
            if kd == "house":
                base_units.append(info[0])
            elif kd in ("neq", "rel"):
                base_cells.append(info[0])
        grouped = defaultdict(list)
        for d in rest:
            w = why(c, d)
            if w is None:
                grouped["is ruled out"].append(d)
                continue
            w = w.replace(f" puts a {d} there", " puts it there").replace(f" puts an {d} there", " puts it there")
            grouped[w].append(d)
        for w, ds in grouped.items():
            if w == "is ruled out":
                parts.append(f"{nm.digits(ds, 'and')} {'is' if len(ds) == 1 else 'are'} ruled out")
            elif len(ds) == 1:
                parts.append(f"{ds[0]} fails because {w}")
            else:
                parts.append(
                    f"{nm.digits(ds, 'and')} all fail because " + w.replace(" puts it there", " puts any of them there")
                )
        ok = all(why(c, d) for d in rest)
        short = (
            f"{nm.cell(c)} = {v}: every other digit is excluded by the grid and the line rules"
            if used_rules
            else f"{nm.cell(c)} = {v}: every other digit is excluded, with a little reasoning in your head"
        )
        teach = (
            f"Start with what {nm.cell(c)} sees directly: {'; '.join(seen) if seen else 'very little'}, "
            f"leaving {nm.digits([v] + rest)}. Now use the rules in your head: {'; '.join(parts)}. "
            f"Only {v} survives -- no pencil marks needed."
        )
    for key in used_rules:
        r = rules(p)[key]
        lines.append((r.line_kind or r.kind, r.cells))
    if ctx.tech == S.MENTAL_D and ctx.xm.get("subset"):
        teach += (
            f" The key was a mental {['', '', 'pair', 'triple'][min(ctx.xm['subset'], 3)]}: cells that can only "
            f"hold the same digits lock those digits out of the rest of the house."
        )
    J = _J(
        ctx,
        digits=[v],
        base_units=list(dict.fromkeys(base_units)),
        base_cells=base_cells,
        constraints=[_con_json(rules(p)[k]) for k in used_rules],
    )
    return _result(ctx, J, short, teach, ok, lines=lines)


def _con_json(rule):
    return {
        "type": rule.line_kind or rule.kind,
        "index": rule.index if rule.index is not None else rule.group,
        "cells": list(rule.cells),
        "params": {k: v for k, v in rule.con.items() if k in ("total", "count", "k", "dots", "each")}
        | ({"total": rule.total} if rule.total is not None else {}),
    }


# ---------------------------------------------------- constraint single ------
def _rule_from_move(ctx):
    p = ctx.p
    R = rules(p)
    idx = ctx.xm.get("constraint")
    if idx is not None and idx >= 0 and ("con", idx) in R:
        return R[("con", idx)]
    name = ctx.m.name or ""
    mm = re.search(r"#(\d+)$", name)
    if mm and not name.startswith("leftovers") and ("con", int(mm.group(1))) in R:
        return R[("con", int(mm.group(1)))]
    mm = re.match(r"cage (\S+)", name)
    if mm and ctx.gi(mm.group(1)) is not None:
        return R.get(("cage", ctx.gi(mm.group(1))))
    gi = ctx.xm.get("cage_group")
    if gi is not None and ("cage", gi) in R:
        return R[("cage", gi)]
    if ctx.gi(name) is not None and ("cage", ctx.gi(name)) in R:
        return R[("cage", ctx.gi(name))]
    return None


def _h_nary_direct(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    rule = _rule_from_move(ctx)
    if rule is None:
        return _generic(ctx)
    known = [(q, st.vals[q]) for q in rule.cells if st.vals[q]]
    dom = [bit(st.vals[q]) if st.vals[q] else p.domains[q] for q in rule.cells]
    res = enum_rule(p, rule, dom)
    k = rule.cells.index(c)
    ok = res["sup"][k] == bit(v)
    ks = ", ".join(f"{nm.cell(q)}={d}" for q, d in known)
    kind = rule.line_kind or rule.kind
    if kind in ("sum", "cage", "little_killer"):
        s = sum(d for _, d in known)
        how = f"the digits already in it add to {s}, so the last cell must be {rule.total} - {s} = {v}"
    elif kind == "arrow":
        circ = rule.con["circle"]
        line = rule.con["line"]
        if c in circ:
            how = f"the arrow's digits add up to {sum(st.vals[q] for q in line)}, so the circle is {v}"
        else:
            tot = int("".join(str(st.vals[q]) for q in circ))
            s = sum(st.vals[q] for q in line if st.vals[q])
            how = f"the circle says {tot} and the rest of the arrow already adds to {s}, so {nm.cell(c)} is {tot - s}"
    elif kind == "set" or kind == "renban":
        how = (
            f"its digits so far ({nm.digits([d for _, d in known], 'and')}) leave exactly one way to complete a "
            f"run of {len(rule.cells)} consecutive digits"
        )
    else:
        how = "only one digit completes it"
    short = f"{nm.cell(c)} = {v}: completes {rule.label}"
    teach = (
        f"{_cap(rule.label)} has one empty cell left, {nm.cell(c)} ({ks}). {_cap(how)}. "
        f"Whenever a cage, arrow or line is nearly full, do the arithmetic -- the last cell is often forced "
        f"before any scanning."
    )
    J = _J(ctx, digits=[v], constraints=[_con_json(rule)], base_cells=list(rule.cells))
    return _result(ctx, J, short, teach, ok, lines=[(kind, rule.cells)])
