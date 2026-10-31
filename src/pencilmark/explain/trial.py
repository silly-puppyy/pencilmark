"""Trial, forcing and case splits; the remaining variant handlers. (split from explain.py)"""

from __future__ import annotations

from collections import defaultdict

from .. import solver as S
from ..model import bit, digits_of, popcount
from .base import _J, LINE_NAMES, _cant, _cap, _elim_digits, _elim_list, _generic, _join, _result, fmt_elims, rel_label
from .combos import _line_reasons, _line_tip, _must_contain
from .grid import Rule, _rule_dom, enum_rule, mental_view, rules
from .singles import _con_json, _rule_from_move

# ---------------------------------------------------------------- trial ------


def _propagate(p, st, c0, v0, max_rounds=8, use_rules=True, out=None):
    """Assume c0 = v0 and follow forced placements with dependency tracking.
    -> (events, contradiction) ; events: list of dicts {cell, digit, why, deps}."""
    vals, cand = list(st.vals), list(st.cand)
    removed_by = {}  # (cell, digit) -> event index that removed it
    events = []
    R = list(rules(p).values()) if use_rules else []
    if out is not None:
        out.update(vals=vals, cand=cand, removed_by=removed_by)
    seen_dom = {}

    def place(c, v, why, deps):
        events.append({"cell": c, "digit": v, "why": why, "deps": deps})
        e = len(events) - 1
        vals[c] = v
        cand[c] = 0
        for q in p.peer_list[c]:
            if cand[q] & bit(v):
                cand[q] &= ~bit(v)
                removed_by[(q, v)] = e
        for q in p.nonconsec_list[c]:
            nb = p.rel_ex[c][q][v]
            for d in digits_of(cand[q] & nb):
                removed_by[(q, d)] = e
            cand[q] &= ~nb
        return e

    place(c0, v0, "assume", [])
    for rnd in range(max_rounds):
        prog = False
        for x in range(p.N):
            if vals[x]:
                continue
            if not cand[x]:
                deps = sorted({removed_by.get((x, d)) for d in digits_of(st.cand[x]) if (x, d) in removed_by})
                return events, {"kind": "empty", "cell": x, "deps": deps}
            if popcount(cand[x]) == 1:
                v = next(digits_of(cand[x]))
                deps = sorted({removed_by[(x, d)] for d in digits_of(st.cand[x]) if d != v and (x, d) in removed_by})
                place(x, v, ("naked", None), deps)
                prog = True
        for hi in p.houses:
            have = 0
            for q in p.groups[hi].cells:
                if vals[q]:
                    have |= bit(vals[q])
            for d in digits_of(p.full & ~have):
                poss = [q for q in p.groups[hi].cells if not vals[q] and cand[q] & bit(d)]
                orig = [q for q in p.groups[hi].cells if not st.vals[q] and st.cand[q] & bit(d)]
                if not poss:
                    deps = sorted({removed_by[(q, d)] for q in orig if (q, d) in removed_by})
                    return events, {"kind": "house", "house": hi, "digit": d, "deps": deps}
                if len(poss) == 1:
                    deps = sorted({removed_by[(q, d)] for q in orig if q != poss[0] and (q, d) in removed_by})
                    place(poss[0], d, ("hidden", hi), deps)
                    prog = True
        for x in range(p.N):
            if vals[x]:
                continue
            for q in p.nonconsec_list[x]:
                dq = bit(vals[q]) if vals[q] else cand[q]
                allowed = 0
                for w in digits_of(dq):
                    allowed |= p.full & ~p.rel_ex[q][x][w]
                lost = cand[x] & ~allowed
                if lost:
                    e = len(events)
                    events.append(
                        {
                            "cell": x,
                            "digit": None,
                            "removed": list(digits_of(lost)),
                            "why": ("arc", q),
                            "deps": [removed_by.get((q, d)) for d in digits_of(st.cand[q]) if (q, d) in removed_by]
                            + ([i for i, ev in enumerate(events[:-1]) if ev["cell"] == q and ev.get("digit")]),
                        }
                    )
                    for d in digits_of(lost):
                        removed_by[(x, d)] = e
                    cand[x] &= allowed
                    prog = True
        for rule in R:
            dom = [bit(vals[c]) if vals[c] else cand[c] for c in rule.cells]
            key = id(rule)
            if seen_dom.get(key) == dom:
                continue
            seen_dom[key] = dom
            if all(vals[c] for c in rule.cells) and rule.check([vals[c] for c in rule.cells]):
                continue
            if any(d == 0 for d in dom):
                continue
            res = enum_rule(p, rule, dom, node_limit=20000)  # memoised on the rule
            if not res["complete"]:
                continue
            deps = sorted({i for i, ev in enumerate(events) if ev["cell"] in rule.cells and ev.get("digit")})
            if res["count"] == 0:
                return events, {"kind": "rule", "rule": rule, "deps": deps}
            for i, c in enumerate(rule.cells):
                if vals[c]:
                    continue
                lost = cand[c] & ~res["sup"][i]
                if lost:
                    e = len(events)
                    events.append(
                        {
                            "cell": c,
                            "digit": None,
                            "removed": list(digits_of(lost)),
                            "why": ("rule", rule),
                            "deps": deps,
                        }
                    )
                    for d in digits_of(lost):
                        removed_by[(c, d)] = e
                    cand[c] &= res["sup"][i]
                    prog = True
        if not prog:
            break
    return events, None


def _trial_story(nm, p, events, contra):
    parts, need_cells, used_rules = _dep_story(nm, p, events, contra["deps"])
    if contra["kind"] == "empty":
        end = f"{nm.cell(contra['cell'])} has no candidate left"
    elif contra["kind"] == "house":
        end = f"{nm.unit(contra['house'])} has nowhere left for a {contra['digit']}"
    else:
        end = f"{contra['rule'].label} can't be completed"
        used_rules.append(contra["rule"])
    return parts, end, need_cells, used_rules


def _dep_story(nm, p, events, deps):
    """Only the forced steps the conclusion depends on, in order. -> (phrases, cells, rules)."""
    need = set()
    stack = list(deps)
    while stack:
        e = stack.pop()
        if e is None or e in need:
            continue
        need.add(e)
        stack.extend(x for x in events[e]["deps"] if x is not None)
    need.add(0)
    order = sorted(need)
    parts = []
    used_rules = [
        events[e]["why"][1] for e in order[1:] if isinstance(events[e]["why"], tuple) and events[e]["why"][0] == "rule"
    ]
    for e in order[1:]:
        ev = events[e]
        c = ev["cell"]
        kind = ev["why"][0] if isinstance(ev["why"], tuple) else ev["why"]
        if ev.get("digit"):
            if kind == "naked":
                parts.append(f"{nm.cell(c)} is left with only {ev['digit']}")
            elif kind == "hidden":
                parts.append(f"{nm.cell(c)} becomes the only spot for {ev['digit']} in {nm.unit(ev['why'][1])}")
        else:
            if kind == "arc":
                parts.append(f"{nm.cell(c)} loses {nm.digits(ev['removed'], 'and')} ({rel_label(p, ev['why'][1], c)})")
            elif kind == "rule":
                parts.append(f"{ev['why'][1].label} can no longer have {nm.digits(ev['removed'])} in {nm.cell(c)}")
    return parts, [events[e]["cell"] for e in order], used_rules


def _h_trial(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.elims[0]
    events, contra = _propagate(p, st, c, v, max_rounds=12 if ctx.tech == S.TRIAL else 6)
    if contra is None:
        events, contra = _propagate(p, st, c, v, max_rounds=40)
    other = [d for d in digits_of(st.cand[c]) if d != v]
    if contra is None:
        short = f"{fmt_elims(nm, ctx.elims)}: assuming {v} there leads to a contradiction"
        teach = (
            f"{nm.cell(c)} {nm.cset(st.cand[c])} has two candidates. If it were {v}, the forced consequences "
            f"eventually break a rule, so it isn't {v}. (The full chain is long; the solver found it by trial.)"
        )
        J = _J(ctx, digits=[v], base_cells=[c], trial={"assume": (c, v), "events": [], "contradiction": None})
        return _result(ctx, J, short, teach, False)
    parts, end, cells, used_rules = _trial_story(nm, p, events, contra)
    steps_txt = "; ".join(parts) if parts else "nothing else is needed"
    short = f"{fmt_elims(nm, ctx.elims)}: if it were {v}, {end}"
    teach = (
        f"{nm.cell(c)} has just two candidates, {nm.cset(st.cand[c])}. Assume it were {v}: {steps_txt}; "
        f"and then {end}. That's impossible, so {nm.cell(c)} isn't {v}"
        + (f" -- it must be {other[0]}" if len(other) == 1 else "")
        + ". "
        + (
            "A short forcing argument like this is how many solvers settle a bivalue cell: try one option and "
            "see whether it collapses within a few moves."
            if ctx.tech == S.SHORT_TRIAL
            else "This is trial-and-error territory: it is valid logic, but look for a pattern that explains the same "
            "contradiction before reaching for it."
        )
    )
    trial = {
        "assume": (c, v),
        "events": [
            {"cell": events[e]["cell"], "digit": events[e].get("digit"), "removed": events[e].get("removed")}
            for e in range(len(events))
        ][:60],
        "contradiction": {k: (vv.label if isinstance(vv, Rule) else vv) for k, vv in contra.items()},
    }
    J = _J(ctx, digits=[v], base_cells=cells, trial=trial)
    ex_cells = cells + ([contra["cell"]] if contra["kind"] == "empty" else [])
    J["base_units"] = [contra["house"]] if contra["kind"] == "house" else []
    lines = [(r.line_kind or r.kind, r.cells) for r in dict.fromkeys(used_rules)]
    return _result(ctx, J, short, teach, True, extra_cells=ex_cells, lines=lines)


def _either_choices(p, st):
    out = []
    for c in range(p.N):
        if not st.vals[c] and popcount(st.cand[c]) == 2:
            a, b = digits_of(st.cand[c])
            out.append(((c, a), (c, b), ("cell", c)))
    for hi in p.houses:
        for v in digits_of(p.full & ~st.placed_g(hi)):
            cs = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(v)]
            if len(cs) == 2:
                out.append(((cs[0], v), (cs[1], v), ("house", hi, v)))
    return out


def _branch_check(events, out, target, place):
    vals, cand, rb = out["vals"], out["cand"], out["removed_by"]
    x, d = target
    if place:
        if vals[x] != d:
            return None
        return [next(i for i, ev in enumerate(events) if ev["cell"] == x and ev.get("digit") == d)]
    if vals[x] == d or (not vals[x] and cand[x] & bit(d)):
        return None
    if vals[x]:
        return [next(i for i, ev in enumerate(events) if ev["cell"] == x and ev.get("digit"))]
    return [rb[(x, d)]] if (x, d) in rb else None


def _h_either_way(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    direct = bool(ctx.xm.get("no_notes")) or ctx.step.mode == "direct"
    ps = st
    if direct:
        md, _ = mental_view(p, st, level=3)
        ps = st.copy()
        ps.cand = [0 if st.vals[q] else md[q] for q in range(p.N)]
    targets = [ctx.place] if ctx.place else ctx.elims
    place = ctx.place is not None
    cache = {}
    choices = _either_choices(p, ps)
    pc = ctx.engine.get("pattern_cells") or []
    if len(pc) >= 2:
        pref = {pc[0], pc[1]}
        choices.sort(key=lambda ch: {ch[0][0], ch[1][0]} != pref)
    for use_rules, rounds in ((False, 4), (True, 4), (True, 6)):
        for A, B, why in choices:
            stories = []
            contra_units = []
            for opt in (A, B):
                key = (opt, use_rules, rounds)
                if key not in cache:
                    out = {}
                    ev, contra = _propagate(p, ps, opt[0], opt[1], max_rounds=rounds, use_rules=use_rules, out=out)
                    cache[key] = (ev, out, contra)
                ev, out, contra = cache[key]
                if contra is not None:  # this option breaks a rule: the other one must hold anyway
                    parts, end, cells_, rules_ = _trial_story(nm, p, ev, contra)
                    if contra["kind"] == "house":
                        contra_units.append(contra["house"])
                    elif contra["kind"] == "empty":
                        cells_ = cells_ + [contra["cell"]]
                    stories.append((parts + [f"then {end} -- impossible, so this option is out"], cells_, rules_))
                    continue
                deps = []
                for t in targets:
                    r = _branch_check(ev, out, t, place)
                    if r is None:
                        break
                    deps += r
                else:
                    stories.append(_dep_story(nm, p, ev, deps))
                    continue
                break
            if len(stories) != 2 or all(cache[(o, use_rules, rounds)][2] is not None for o in (A, B)):
                continue
            if why[0] == "cell":
                intro = f"{nm.cell(why[1])} can only be {A[1]} or {B[1]}"
            else:
                intro = f"the {why[2]} of {nm.unit(why[1])} must go in {nm.cell(A[0])} or {nm.cell(B[0])}"

            def branch(opt, story):
                direct_hit = "that alone settles it"
                steps = "; ".join(story[0]) if story[0] else direct_hit
                lead = f"if {nm.cell(opt[0])} is {opt[1]}"
                tail = "" if place else f" -- which removes {_elim_list(nm, ctx.elims)}"
                return f"{lead}: {steps}{tail}"

            if place:
                c, v = ctx.place
                short = f"{nm.cell(c)} = {v}: both options of a two-way choice lead here"
            else:
                short = f"{fmt_elims(nm, ctx.elims)}: both options of a two-way choice agree"
            teach = (
                f"Look at a simple either/or: {intro}. Follow both: {branch(A, stories[0])}. And "
                f"{branch(B, stories[1])}. Both roads lead to the same place, so "
                + (f"{nm.cell(ctx.place[0])} is {ctx.place[1]}" if place else _cant(nm, ctx.elims))
                + " -- no matter which option is true. 'Either way' reasoning is a gentle alternative to "
                "trial and error: you never need to know which branch is right."
            )
            cells = [A[0], B[0]] + stories[0][1] + stories[1][1]
            lines = [(r.line_kind or r.kind, r.cells) for r in dict.fromkeys(stories[0][2] + stories[1][2])]
            J = _J(
                ctx,
                digits=sorted({A[1], B[1]}),
                base_cells=cells,
                trial={"assume": [A, B], "events": [], "contradiction": None},
            )
            units = ([why[1]] if why[0] == "house" else []) + contra_units
            J["base_units"] = units
            return _result(ctx, J, short, teach, True, extra_cells=cells, lines=lines)
    return _generic(ctx)


def _line_classes(p, rule):
    """Digit classes of a line kind (as the engine's LineClass): -> (cls per digit, class names)."""
    kind = rule.line_kind
    D = p.D
    if kind in ("entropic", "modular"):
        if kind == "entropic":
            cls = {d: (d - 1) * 3 // D for d in range(1, D + 1)}
        else:
            cls = {d: (d - 1) % 3 for d in range(1, D + 1)}
    elif kind in ("parity", "kropki_chain"):
        cls = {d: d % 2 for d in range(1, D + 1)}
    elif kind in ("whisper", "dutch_whisper"):
        a, b = rule.cells[0], rule.cells[1]
        cls = {}
        for d in range(1, D + 1):
            ok = p.full & ~p.rel_ex[a][b][d] if b in p.rel_ex[a] else p.full
            up = any(w > d for w in digits_of(ok))
            dn = any(w < d for w in digits_of(ok))
            cls[d] = 0 if up and not dn else 1 if dn and not up else 2 if up and dn else 3
    else:
        return None, None
    names = {}
    for c in sorted(set(cls.values())):
        ds = [d for d in cls if cls[d] == c]
        if kind in ("whisper", "dutch_whisper"):
            label = ["low", "high", "middle", "impossible"][c]
        elif kind == "entropic":
            label = ["low", "middle", "high"][c]
        elif kind in ("parity", "kropki_chain"):
            label = ["even", "odd"][c]
        else:
            label = "{" + ",".join(map(str, ds)) + "}"
        names[c] = (
            f"{label} ({_join(ds, 'or') if len(ds) < 4 else f'{ds[0]}-{ds[-1]}'})" if kind != "modular" else label
        )
    return cls, names


def _h_line_class(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    rule = _rule_from_move(ctx)
    if rule is None or not rule.line_kind:
        return _generic(ctx)
    cls, names = _line_classes(p, rule)
    if cls is None:
        return _generic(ctx)
    cells = rule.cells
    n = len(cells)
    ncls = max(cls.values()) + 1
    cmask = [sum(bit(d) for d in cls if cls[d] == q) for q in range(ncls)]
    dom = [bit(st.vals[c]) if st.vals[c] else st.cand[c] for c in cells]
    cd = [sum(1 << q for q in range(ncls) if dom[i] & cmask[q]) for i in range(n)]
    cause = {}
    for _ in range(2 * n):
        changed = False
        for i in range(n):
            for j in range(n):
                a, b = cells[i], cells[j]
                if i == j or b not in p.rel_ex[a]:
                    continue
                keep = 0
                for qa in range(ncls):
                    if not cd[i] >> qa & 1:
                        continue
                    for qb in range(ncls):
                        if cd[j] >> qb & 1 and any(cmask[qb] & ~p.rel_ex[a][b][d] for d in digits_of(cmask[qa])):
                            keep |= 1 << qa
                            break
                if cd[i] & ~keep:
                    cd[i] &= keep
                    cause.setdefault(i, j)
                    changed = True
        if not changed:
            break
    comp = set()
    for i, c in enumerate(cells):
        if st.vals[c]:
            continue
        allowed = sum(cmask[q] for q in range(ncls) if cd[i] >> q & 1)
        comp |= {(c, d) for d in digits_of(st.cand[c] & ~allowed)}
    ok = set(ctx.elims) <= comp
    lname = LINE_NAMES.get(rule.line_kind, rule.line_kind)
    parts = []
    never = [q for q in range(ncls) if names.get(q, "").startswith("impossible")]
    by_cell = defaultdict(list)
    for c, d in ctx.elims:
        by_cell[c].append(d)
    for c in nm.sort(by_cell):
        i = cells.index(c)
        ds = by_cell[c]
        if never and all(cls[d] in never for d in ds):
            continue
        left = [names[q].split(" (")[0] for q in range(ncls) if cd[i] >> q & 1 and q in names]
        j = cause.get(i)
        why = ""
        if j is not None:
            jl = [names[q].split(" (")[0] for q in range(ncls) if cd[j] >> q & 1 and q in names]
            why = f" because {nm.cell(cells[j])} next to it can only be {_join(jl, 'or')}"
        parts.append(f"{nm.cell(c)} must be {_join(left, 'or')}{why}, so not {nm.digits(ds)}")
    nev_txt = ""
    if never:
        nd = [d for d in cls if cls[d] in never]
        nev_cells = [c for c, d in ctx.elims if cls[d] in never]
        if nev_cells:
            nev_txt = (
                f"{nm.digits(nd)} has no possible neighbour on a {lname}, so it can't appear anywhere on it "
                f"-- remove it from {nm.cells(nev_cells)}. "
            )
    classes = "; ".join(names[q] for q in sorted(names))
    short = f"{fmt_elims(nm, ctx.elims)}: {lname} classes"
    if never and all(cls[d] in never for _, d in ctx.elims):
        short = (
            f"{fmt_elims(nm, ctx.elims)}: {lname}s -- {nm.digits([d for d in cls if cls[d] in never])} can never appear"
        )
    elif rule.line_kind in ("whisper", "dutch_whisper"):
        short = f"{fmt_elims(nm, ctx.elims)}: {lname} high/low logic"
    teach = (
        f"Don't track exact digits on {rule.label} -- track classes: {classes}. "
        + nev_txt
        + (_cap("; ".join(parts)) + ". " if parts else "")
        + {
            "whisper": "Whispers alternate low and high, so one fixed cell decides the pattern along the line.",
            "dutch_whisper": "Dutch whispers alternate low and high too (5 only next to 1 or 9).",
            "entropic": "Any three cells in a row on an entropic line use one low, one middle and one high digit.",
            "modular": "Any three cells in a row on a modular line use one digit from each residue class.",
            "parity": "Parity lines alternate odd and even.",
            "kropki_chain": "Parity helps along dots: consecutive (white) pairs mix odd and even.",
        }.get(rule.line_kind, "")
    )
    J = _J(
        ctx,
        digits=_elim_digits(ctx),
        constraints=[_con_json(rule)],
        base_cells=list(cells),
        cover_cells=sorted(by_cell),
    )
    return _result(ctx, J, short, teach, ok, lines=[(rule.line_kind, cells)])


def _h_digit_count(ctx):
    """Positional set logic for one digit: k units that must contain v, k at-most-once covers."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    v = ctx.xm.get("digit") or (_elim_digits(ctx)[0] if ctx.elims else None)
    bu, cu = ctx.engine.get("base_units") or [], ctx.engine.get("cover_units") or []
    U = sorted(c for c in ctx.engine.get("pattern_cells") or () if isinstance(c, int))
    if not cu or not U or v is None:
        return _generic(ctx)
    ctx.used_engine = True
    CU = {c for g in cu for c in p.groups[g].cells}
    el = {(c, v) for c in CU if c not in U and not st.vals[c] and st.cand[c] & bit(v)}
    ok = set(ctx.elims) <= el and set(U) <= CU and len(cu) == ctx.xm.get("units", len(cu))
    covered = {c for g in bu for c in p.groups[g].cells}
    extra = []
    left = [c for c in U if c not in covered]
    if left:
        for key, rule in rules(p).items():
            if key[0] == "cage" and key[1] in bu:
                continue
            cs = [c for c in rule.cells if not st.vals[c] and st.cand[c] & bit(v)]
            if cs and set(cs) <= set(left) and _must_contain(p, st, rule, v):
                extra.append(rule)
                left = [c for c in left if c not in cs]
    k = len(cu)
    kw = {1: "one", 2: "two", 3: "three"}.get(k, str(k))

    def unit_txt(g):
        g_ = p.groups[g]
        return nm.unit(g) if g_.complete else f"{nm.cage(g, cells=False)} (every combination needs a {v})"

    bases = [unit_txt(g) for g in bu] + [f"{r.label} (every filling needs a {v})" for r in extra]
    short = f"{fmt_elims(nm, ctx.elims)}: counting the {v}s ({kw} must-have units vs {kw} houses)"
    teach = (
        f"Count {v}s. {_cap(_join(bases))} each must contain a {v}, and they don't overlap, so there are "
        f"{kw} {v}{'s' if k > 1 else ''} somewhere in {nm.cells(U, 'or')}. All of those cells lie in "
        f"{_join([nm.unit(g) for g in cu])}, which can hold only {kw} {v}{'s' if k > 1 else ''} between them. "
        f"So the covers' {v}s are exactly the ones in the pattern, and {nm.cells(sorted(c for c, _ in ctx.elims))} "
        f"can't be {v}. This is fish logic with cages or rules playing the part of rows."
    )
    J = _J(
        ctx,
        digits=[v],
        base_units=list(bu),
        cover_units=list(cu),
        base_cells=U,
        constraints=[_con_json(r) for r in extra],
        cover_cells=sorted(c for c, _ in ctx.elims),
    )
    return _result(ctx, J, short, teach, ok, lines=[(r.line_kind or r.kind, r.cells) for r in extra])


def _h_equal_digits(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    A, B, hi = ctx.xm.get("cell_a"), ctx.xm.get("cell_b"), ctx.xm.get("house")
    if A is None or B is None or hi is None:
        return _generic(ctx)
    H = p.groups[hi]
    ok = True
    for d in digits_of(st.cand[A]):
        cs = [c for c in H.cells if not st.vals[c] and st.cand[c] & bit(d) and c not in p.peers[A]]
        ok &= cs == [B]
    el = {(A, d) for d in digits_of(st.cand[A] & ~st.cand[B])} | {(B, d) for d in digits_of(st.cand[B] & ~st.cand[A])}
    ok &= set(ctx.elims) <= el
    short = f"{fmt_elims(nm, ctx.elims)}: {nm.cell(A)} and {nm.cell(B)} must hold the same digit"
    teach = (
        f"{nm.cell(A)} {nm.cset(st.cand[A])} sits outside {nm.unit(hi)}. Take any of its candidates: if "
        f"{nm.cell(A)} were that digit, {nm.unit(hi)} would still need one, and every spot for it in "
        f"{nm.unit(hi)} sees {nm.cell(A)} except {nm.cell(B)} {nm.cset(st.cand[B])}. So whatever {nm.cell(A)} "
        f"is, {nm.cell(B)} is the same digit -- and each cell can only keep candidates the other one has: "
        f"{_cant(nm, ctx.elims)}. Spotting 'these two cells are equal' is a powerful idea even before you "
        f"know the digit."
    )
    J = _J(ctx, digits=sorted(digits_of(st.cand[A] | st.cand[B])), base_units=[hi], base_cells=[A, B])
    return _result(ctx, J, short, teach, ok, extra_cells=[A, B])


def _h_line_scan(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    parent = _rule_from_move(ctx)
    pc = [c for c in ctx.engine.get("pattern_cells") or () if isinstance(c, int)]
    if parent is None or not parent.line_kind:
        return _generic(ctx)
    cells = parent.cells
    tg = {c for c, _ in ctx.elims}
    win = None
    for i in range(len(cells) - 2):
        w = cells[i : i + 3]
        if tg <= set(w) and set(pc) <= set(w):
            win = w
            break
    if win is None:
        return _generic(ctx)
    rule = Rule(
        "line", win, f"the three cells {nm.cells(win)} of {parent.label}", line_kind=parent.line_kind, con=parent.con
    )
    res = enum_rule(p, rule, _rule_dom(st, rule))
    comp = {(c, d) for i, c in enumerate(win) if not st.vals[c] for d in digits_of(st.cand[c] & ~res["sup"][i])}
    ok = set(ctx.elims) <= comp
    why = _line_reasons(ctx, rule, res)
    short = f"{fmt_elims(nm, ctx.elims)}: a three-cell stretch of the {LINE_NAMES.get(parent.line_kind, 'line')}"
    teach = (
        f"You don't need the whole of {parent.label} -- scan it three cells at a time. Look at "
        f"{nm.cells(win)}: {why} {_line_tip(parent.line_kind)}"
    )
    J = _J(ctx, digits=_elim_digits(ctx), constraints=[_con_json(parent)], base_cells=list(win))
    return _result(ctx, J, short, teach, ok, lines=[(parent.line_kind, win), (parent.line_kind, parent.cells)])


def _h_guess(ctx):
    nm, st = ctx.nm, ctx.st
    c, v = ctx.place
    short = f"{nm.cell(c)} = {v}: no logical step found -- the solver commits to a value"
    teach = (
        f"At this point none of the solver's techniques applies. It picks the cell with the fewest candidates, "
        f"{nm.cell(c)} {nm.cset(st.cand[c])}, and commits to {v} (the value in the known solution). A human "
        f"would either find a deeper pattern here or try a value and be ready to backtrack."
    )
    J = _J(ctx, digits=[v], base_cells=[c])
    return _result(ctx, J, short, teach, True)


def _h_take_notes(ctx):
    n = sum(1 for c in range(ctx.p.N) if not ctx.st.vals[c])
    short = "Pencil-mark the grid: scanning alone has run out"
    teach = (
        f"No more singles can be found by looking at the placed digits alone, so it's time to write the "
        f"candidates into the {n} empty cells. From here the solve works on notes: subsets, intersections and "
        f"patterns all read off the pencil marks."
    )
    J = _J(ctx)
    return _result(ctx, J, short, teach, True)


def _h_snyder_marks(ctx):
    short = "Snyder marks: corner-mark digits confined to two cells of a box"
    teach = (
        "Scanning has run out. Instead of full candidates, mark in each box only the digits that can go in just "
        "two of its cells (Snyder notation). Pairs that coincide or line up then give placements."
    )
    J = _J(ctx)
    return _result(ctx, J, short, teach, True)
