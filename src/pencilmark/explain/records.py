"""Techniques that explain from the engine's records (68-82 and later), empty rectangles. (split from explain.py)"""

from __future__ import annotations

from collections import defaultdict

from .. import solver as S
from .base import _J, CONCEPTS, _cap, _generic, _join, _result, fmt_elims
from .chains import _h_chain

# ================================================== techniques 68-82 (engine records) ==
# Forcing chains, 3D Medusa, colour classes, sum bounds, class counting, dominoes and the sudokuwiki set.
# Built from the engine's explanation records (cbackend.solve(..., explain=True)): each handler states
# the move exactly in the short line and names only cells / houses that it also highlights.


def _x_units(ctx, names):
    out = []
    for n in names:
        gi = ctx.gi(n) if isinstance(n, str) else n
        if gi is not None and gi not in out:
            out.append(gi)
    return out


def _x_head(ctx):
    nm = ctx.nm
    if ctx.place:
        c, v = ctx.place
        return f"{nm.cell(c)} = {v}", f"{nm.cell(c)} must be {v}"
    by = defaultdict(list)
    for c, d in ctx.elims:
        by[c].append(d)
    goal = _join(
        [f"{nm.cell(c)} cannot be {nm.digits(ds)}" for c, ds in sorted(by.items(), key=lambda kv: nm.p.coords[kv[0]])]
    )
    return fmt_elims(nm, ctx.elims), goal


_FC_LEVEL = {
    0: "following only singles and the basic rules",
    1: "using ordinary techniques inside each case",
    -1: "following each case with simple logic for a few steps",
    -2: "following each case for a few steps with singles and the rules",
    2: "using further case splits inside each case",
}


def _h_forcing(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    p = nm.p
    tr = eng.get("trial") or {}
    opts = tr.get("options") or []
    level = -1 if ctx.tech == S.WHAT_IF else -2 if ctx.tech == S.HUMAN_CASE else ctx.tech - S.FORCING
    head, goal = _x_head(ctx)
    cells, units = set(), []
    for o in opts:
        cells.add(o["cell"])
    same_cell = len({o["cell"] for o in opts}) == 1
    same_digit = len({o["digit"] for o in opts}) == 1
    if opts and same_cell:
        intro = f"{nm.cell(opts[0]['cell'])} can only be " + nm.digits([o["digit"] for o in opts], "or")
    elif opts and same_digit:
        intro = f"the digit {opts[0]['digit']} has {len(opts)} possible places in a house: " + nm.cells(
            [o["cell"] for o in opts], "or"
        )
    elif opts:
        intro = "one of these must be true: " + _join([f"{o['rc']} is {o['digit']}" for o in opts], "or")
    else:
        intro = "a small set of cases"
    plural = lambda n, w: f"{n} {w}" + ("" if n == 1 else "s")  # noqa: E731
    targets = [ctx.place] if ctx.place else list(ctx.elims)

    def outcome(a, steps):
        """Why this surviving case leads to the conclusion (one clause)."""
        placed = {e["cell"]: e["digit"] for e in steps if e.get("cell") is not None and e.get("digit")}
        placed[a["cell"]] = a["digit"]
        if ctx.place:
            c, v = ctx.place
            if placed.get(c) == v:
                return "" if a["cell"] == c else f"{nm.cell(c)} becomes {v}"
            return goal
        why = []
        for c, d in targets:
            if c in placed and placed[c] != d:
                why.append(
                    f"{nm.cell(c)} holds {placed[c]}, not "
                    + nm.digits(sorted({dd for cc, dd in targets if cc == c}), "or")
                )
                continue
            q = next((x for x, v in placed.items() if v == d and x != c and x in p.peers[c]), None)
            if q is not None:
                why.append(f"{nm.cell(c)} sees the {d} in {nm.cell(q)}")
            else:
                why.append(f"{nm.cell(c)} loses {d}")
        return _join(list(dict.fromkeys(why)))

    parts = []
    for b in tr.get("branches") or []:
        a = b["assume"]
        steps = b.get("steps") or []
        con = b.get("contradiction")
        shown = [e for e in steps if e.get("event") in ("naked single", "hidden single") and e.get("cell") is not None][
            :3
        ]
        for e in shown:
            cells.add(e["cell"])
        seq = ", ".join(f"{e['rc']} becomes {e['digit']}" for e in shown)
        more = len(steps) - len(shown)
        chain = seq + (
            f" (then {plural(more, 'more deduction')})"
            if more > 0 and seq
            else plural(more, "deduction")
            if more > 0
            else ""
        )
        lead = f"if {a['rc']} is {a['digit']}"
        if con:
            where = ""
            if con.get("cell") is not None:
                cells.add(con["cell"])
                where = f" at {con['rc']}"
            if con.get("house"):
                units += _x_units(ctx, [con["house"]])
                gi = ctx.gi(con["house"])
                where = f" in {nm.unit(gi)}" if gi is not None else where
            what = {
                "empty cell": "a cell runs out of candidates",
                "house missing digit": "a house loses its last place for a digit",
                "rule unsatisfiable": "a rule can no longer be satisfied",
                "conflicting singles": "two forced digits clash",
            }.get(con["event"], con["event"])
            parts.append(f"{lead}: {chain + ', ' if chain else ''}then {what}{where}, so this case is impossible")
        else:
            res = outcome(a, steps)
            parts.append(
                f"{lead}: " + (f"{chain}, so {res}" if chain and res else chain or res or "nothing else is needed")
            )
    if parts:
        teach = (
            f"Case analysis ({_FC_LEVEL.get(level, '')}): {intro}. One of these cases must be true, so follow "
            f"each:\n"
            + "\n".join("- " + _cap(x) + "." for x in parts)
            + f"\nEvery case that can happen gives the same result: {goal}."
        )
    else:
        teach = f"Case analysis ({_FC_LEVEL.get(level, '')}): {intro}. Following each case shows that {goal}."
    J = _J(ctx, digits=sorted({o["digit"] for o in opts}), base_units=units, trial={"options": opts, "level": level})
    return _result(ctx, J, f"{head}: every possible case agrees", teach, bool(opts), extra_cells=cells)


def _h_nishio(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    head, goal = _x_head(ctx)
    c, v = ctx.elims[0] if ctx.elims else (None, None)
    bu = [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u]
    units = _x_units(ctx, bu)
    where = f"{nm.unit(units[0])} has no place left for it" if units else "two of its forced copies clash"
    teach = (
        f"Follow just the digit {v}: put it in {nm.cell(c)}, cross {v} out of every cell that sees it, and keep "
        f"placing {v} wherever a house has only one spot left. Then {where}, so {nm.cell(c)} cannot be {v}."
    )
    J = _J(ctx, digits=[v], base_units=units)
    return _result(
        ctx,
        J,
        f"{head}: assuming it, the {v}s run out of room",
        teach,
        True,
        extra_cells=eng.get("pattern_cells") or (),
    )


def _h_medusa(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    head, goal = _x_head(ctx)
    col = eng.get("coloring") or {}
    cs = col.get("colors") or [[], []]
    cells = {e["cell"] for c in cs for e in c}
    fmt = lambda c: ", ".join(f"{nm.cell(e['cell'])} as {e['digit']}" for e in c)  # noqa: E731
    if col.get("type") == "wrap":
        why = "one colour contradicts itself (twice in a cell or house, or it empties a cell), so all of it is false"
    else:
        why = "whichever colour is true, these candidates cannot survive (they see both colours, or share a cell with one)"
    teach = (
        f"Colour candidates in two colours along strong links (a cell with two candidates, or a digit with two "
        f"places in a house), switching colour at every link and across digits; one colour is entirely true. "
        f"Blue: {fmt(cs[0])}. Green: {fmt(cs[1])}. Here {why}: {goal}."
    )
    J = _J(ctx, digits=sorted({e["digit"] for c in cs for e in c}))
    return _result(ctx, J, f"{head}: two-colour chain over several digits", teach, bool(cells), extra_cells=cells)


def _h_colour_classes(ctx):
    nm, eng = ctx.nm, ctx.raw_engine
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    same = (
        f"Colour {nm.cells(pc)} purple: they must {'both' if len(pc) == 2 else 'all'} hold the same digit (each "
        f"was shown to equal the next: an equality rule, or the only cell of a house that can take the other's "
        f"digit)"
    )
    units = _x_units(ctx, [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u])
    seed = (ctx.xm or {}).get("seed", 0)
    if seed in (2, 3):
        same = same + (
            " -- this colouring came from you" + (" (not checked against the solution)" if seed == 3 else "")
        )
    if ctx.code == "colour class (odd/even/low/high)":
        k = (ctx.xm or {}).get("class_kinds", 0)
        names = [
            n for b, n in ((1, "odd"), (2, "even"), (4, "low (1-3)"), (8, "middle (4-6)"), (16, "high (7-9)")) if k & b
        ]
        teach = f"Your colouring marks {nm.cells(pc)} as {' and '.join(names) or 'one class'} digits. So {goal}."
        J = _J(ctx)
        return _result(ctx, J, f"{head}: coloured as {' and '.join(names) or 'a class'}", teach, True, extra_cells=pc)
    if ctx.code == "label break-in (abstract digits)":
        teach = (
            f"Give every cell an abstract label for its digit (A, B, C ...): this assumes nothing. A label that "
            f"must appear in a house but has only one cell there that does not see it lands on that cell, so "
            f"cells end up sharing labels; the rules then act on whole labels (a relation between two labelled "
            f"cells relates the labels, and each house's labels are all nine digits). Following this, "
            f"{nm.cells(pc)} hold labels that cannot be some of their candidates. So {goal}."
        )
        J = _J(ctx)
        return _result(ctx, J, f"{head}: abstract-digit labels", teach, bool(pc), extra_cells=pc)
    if ctx.code == "colour bounds (order / min-max)":
        teach = (
            f"{same}. Ordering rules between colours (thermometers, inequalities) bound each colour's digit "
            f"from below and above. So {goal}."
        )
        J = _J(ctx)
        return _result(ctx, J, f"{head}: colour bounds", teach, bool(pc), extra_cells=pc)
    if ctx.code == "coloured like a solved cell":
        c, v = ctx.place
        short = f"{head}: same colour as a solved {v}"
        teach = (
            f"{nm.cell(c)} has the same colour as a cell that is already {v} -- the colouring came from you"
            + (" (not checked against the solution)" if seed == 3 else "")
            + f". Same colour, same digit: {goal}."
        )
        J = _J(ctx)
        return _result(ctx, J, short, teach, True, extra_cells=pc)
    if ctx.code in ("colour must fit every house", "colour resolved") and units:
        hu = nm.unit(units[0])
        why = (
            f"{same}. A colour appears once in every house, so {hu} needs that digit in a cell that sees none of "
            f"the coloured cells; for some digits {hu} has no such cell, so the colour cannot be them"
        )
        short = f"{head}: the colour is resolved" if ctx.place else f"{head}: the colour has no place in {hu}"
        teach = f"{why}. So {goal}."
    else:
        short = f"{head}: cells forced to be equal"
        st = ctx.st
        why = []
        for d in sorted({d for _, d in ctx.elims}):
            w = next((c for c in pc if not st.vals[c] and not (st.cand[c] >> (d - 1)) & 1), None)
            if w is None:
                w = next((c for c in pc if st.vals[c] and st.vals[c] != d), None)
            if w is not None:
                why.append(f"{nm.cell(w)} can't be {d}, so purple isn't {d}")
        teach = (
            f"{same}. Purple's digit must fit every purple cell"
            + (": " + "; ".join(why) if why else "")
            + f". So {goal}."
        )
    J = _J(ctx, base_units=units)
    return _result(ctx, J, short, teach, bool(pc), extra_cells=pc)


def _h_sum_bound(ctx):
    nm, eng, xm = ctx.nm, ctx.raw_engine, ctx.xm
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    lo, hi = xm.get("lo"), xm.get("hi")
    if ctx.code == "renban span":
        why = (
            f"a renban's digits are consecutive, so they span at most {xm.get('positions', 0) - 1}: "
            f"every digit must lie between {lo} and {hi}"
        )
    else:
        tri = (
            " (counting distinct digits: the smallest possible sum of different digits)" if xm.get("triangular") else ""
        )
        why = (
            f"the other cells of the rule add up to at least / at most what their candidates allow{tri}, so this "
            f"cell can only be {lo} to {hi}"
        )
    teach = f"Min/max bounds on {nm.cells(pc)}: {why}. So {goal}."
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: the sum bounds leave no room", teach, True, extra_cells=pc)


def _h_class_count(ctx):
    nm, eng, xm = ctx.nm, ctx.raw_engine, ctx.xm
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    units = _x_units(ctx, [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u])
    kind = xm.get("kind")
    if kind in (2, 3):
        why = (
            "the parities of a sum's digits must add up to its total's parity; every other cell's parity is "
            "already known, which fixes this one"
        )
    else:
        cls = "odd / even" if kind == 0 else "low / middle / high"
        why = (
            f"count digits by class ({cls}): {nm.unit(units[0]) if units else 'the house'} needs a fixed number of "
            f"each class, and {nm.cells(pc)} already take all of this class"
        )
    teach = f"Class counting: {why}. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: digit-class count", teach, True, extra_cells=pc)


def _h_domino(ctx):
    eng = ctx.raw_engine
    head, goal = _x_head(ctx)
    doms = eng.get("dominoes") or []
    cells = {c for d in doms for c in d["cells"]}
    units = _x_units(ctx, [u["name"] for u in (eng.get("base") or {}).get("units") or [] if u])
    desc = "; ".join(f"{d['rc'][0]}-{d['rc'][1]} ({d['relation']})" for d in doms)
    code = ctx.code or ""
    if "black chain" in code:
        why = "the middle cell of a black-dot run needs both half and double its digit, so it must be even and small"
    elif "squeeze" in code:
        why = (
            "the middle cell's two neighbours see each other, so they need two different digits that both fit "
            "the rule with it"
        )
    elif "pair lock" in code:
        why = "the two dominoes can only be filled with the same four digits, which they lock in their house"
    else:
        why = "every allowed filling of the domino uses this digit, so it goes from the cells seeing both ends"
    teach = f"Domino logic on {desc}: {why}. So {goal}."
    J = _J(ctx, base_units=units)
    return _result(ctx, J, f"{head}: domino pairs", teach, bool(cells), extra_cells=cells)


def _h_pattern_named(name_text, lesson):
    def h(ctx):
        nm, eng = ctx.nm, ctx.raw_engine
        head, goal = _x_head(ctx)
        pc = eng.get("pattern_cells") or []
        teach = f"{lesson} Pattern cells: {nm.cells(pc)}. So {goal}."
        J = _J(ctx, base_cells=pc)
        return _result(ctx, J, f"{head}: {name_text}", teach, bool(pc), extra_cells=pc)

    return h


def _h_mental_notes(ctx):
    nm, eng, xm = ctx.nm, ctx.raw_engine, ctx.xm
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    via = S.TECH_NAMES.get(xm.get("via_technique"), "a notes technique")
    via_name = CONCEPTS.get(xm.get("via_technique"), (via, ""))[0]
    teach = (
        f"Without writing notes: keep in mind which digits each cell can still take, apply a {via_name.lower()} "
        f"on those mental candidates (cells {nm.cells(pc)}), and the result is a single: {goal}."
    )
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: a single after notes logic in the head", teach, True, extra_cells=pc)


def _h_rule_intersect(ctx):
    eng = ctx.raw_engine
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    base = eng.get("base") or {}
    names = [u["name"] for u in base.get("units") or [] if u and u.get("name")]
    for r in base.get("rules") or []:
        nm_ = r.get("name") or (f"{r.get('kind')} line" if r.get("type") == "line" else r.get("type"))
        names.append(str(nm_))
    what = " and ".join(names) if names else "two rules"
    units = _x_units(ctx, [u["name"] for u in base.get("units") or [] if u])
    if ctx.code == "two houses with their dots":
        why = (
            f"{what} overlap, and the pair rules (dots, lines) between their cells leave only a few ways to fill "
            f"the shared cells"
        )
    else:
        why = (
            f"take {what} together: list the digit combinations that satisfy both at once over their {len(pc)} "
            f"open cells (digits that see each other differ, a house still needs its missing digits)"
        )
    teach = f"{_cap(why)}. Some candidates appear in none of them. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: {what} together", teach, bool(pc), extra_cells=pc)


def _h_sum_algebra(ctx):
    eng, xm = ctx.raw_engine, ctx.xm or {}
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    base = eng.get("base") or {}
    hn = [u["name"] for u in base.get("units") or [] if u and u.get("name")]
    units = _x_units(ctx, hn)
    k = len(hn) or xm.get("houses", 1)
    tot = 45 * k if ctx.p.D == 9 else None
    region = " and ".join(hn) if hn else "these houses"
    why = (
        f"{region} add up to {tot if tot else 'a known total'} together. The rules inside them (cages, line "
        f"segments, arrows) account for part of that total, and the other cells can only add up to what their "
        f"smallest / largest different digits allow. Comparing the two bounds pins down the sums"
        + (f" (after {xm.get('rounds')} rounds of bounds)" if (xm.get("rounds") or 0) > 1 else "")
    )
    teach = f"{why}. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: the maths of {region}", teach, bool(pc), extra_cells=pc)


def _band_equation(ctx, house_names, cage_names):
    """The derived sum that best summarises a band move: a union of disjoint houses (parallel lines, or
    boxes) minus the sum cages inside it -> what the remaining cells add up to (fewest remaining cells)."""
    p = ctx.p
    groups = {}
    for n in house_names + cage_names:
        gi = ctx.gi(n)
        if gi is not None:
            groups[n] = p.groups[gi]
    houses = [n for n in house_names if n in groups and groups[n].complete]
    cages = [(n, groups[n]) for n in cage_names if n in groups and groups[n].total is not None]
    if not cages or not houses:
        return None
    ht = p.D * (p.D + 1) // 2
    best = None
    from itertools import combinations

    for k in range(1, min(3, len(houses)) + 1):
        for hs in combinations(houses, k):
            cells = [c for h in hs for c in groups[h].cells]
            if len(set(cells)) != len(cells):
                continue  # overlapping houses
            u = set(cells)
            inside = [(n, g) for n, g in cages if set(g.cells) <= u]
            if not inside:
                continue
            rest = u - {c for _, g in inside for c in g.cells}
            tot = ht * k - sum(g.total for _, g in inside)
            key = (len(rest), k)
            if rest and (best is None or key < best[0]):
                best = (key, hs, inside, rest, tot)
    if best is None:
        return None
    _, hs, inside, rest, tot = best
    hn = " and ".join(hs)
    cn = " + ".join(f"{n} ({g.total})" for n, g in inside)
    return (
        f"{hn} add up to {ht * len(hs)}; the cages inside, {cn}, take {sum(g.total for _, g in inside)}, so the "
        f"other {len(rest)} cells add up to {tot}"
    )


def _h_band_logic(ctx):
    eng, xm = ctx.raw_engine, ctx.xm or {}
    head, goal = _x_head(ctx)
    pc = eng.get("pattern_cells") or []
    base, cover = eng.get("base") or {}, eng.get("cover") or {}
    hn = [u["name"] for u in base.get("units") or [] if u and u.get("name")]
    cn = [u["name"] for u in cover.get("units") or [] if u and u.get("name")]
    rn = []
    for r in base.get("rules") or []:
        rn.append(str(r.get("name") or (f"{r.get('kind')} line" if r.get("type") == "line" else r.get("type"))))
    units = _x_units(ctx, hn + cn)
    region = " and ".join(hn) if hn else "this band"
    rules = cn + rn
    what = (" with " + ", ".join(rules[:6]) + (" ..." if len(rules) > 6 else "")) if rules else ""
    eq = _band_equation(ctx, hn, cn)
    lv, cases = xm.get("level"), xm.get("cases")
    if lv == 0:
        how = "this follows directly, without trying cases"
    elif lv == 1:
        how = f"trying the {cases} options of one cell, every one breaks a rule"
    elif lv == 2:
        how = f"it takes a longer case analysis ({cases} cases) to see it"
    else:
        how = None
    why = (
        f"take {region}{what} together"
        + (f": {eq}" if eq else ": the house totals and the rules inside fix what the other cells can add up to")
        + f". Together with the digits each house still needs, some candidates fit no filling of these {len(pc)} "
        f"open cells" + (f" -- {how}" if how else "")
    )
    teach = f"{_cap(why)}. So {goal}."
    J = _J(ctx, base_units=units, base_cells=pc)
    return _result(ctx, J, f"{head}: {region}{what} together", teach, bool(pc), extra_cells=pc)


def _h_snyder(ctx):
    nm = ctx.nm
    head, goal = _x_head(ctx)
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    if ctx.code == "Snyder X-wing":
        why = (
            f"the Snyder marks of one digit sit in two boxes on the same two lines ({nm.cells(pc)}): the digit's "
            f"two places in those lines are used up there, so it leaves those lines in the third box"
        )
    elif ctx.code == "Snyder hidden triple":
        why = (
            f"three digits have all their Snyder marks inside the same three cells of a box ({nm.cells(pc)}): those "
            f"cells hold just these three digits"
        )
    else:
        why = (
            f"two digits have their Snyder marks on the same two cells of a box ({nm.cells(pc)}): those cells hold "
            f"just that pair"
        )
    teach = (
        f"With Snyder marks (corner marks for digits confined to two{' or three' if ctx.code == 'Snyder hidden triple' else ''} "
        f"cells of a box), {why}. So {goal}."
    )
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: from Snyder marks", teach, bool(pc), extra_cells=pc)


def _h_combo_positions(ctx):
    """ComboPositions: a cage's valid fillings put at most m digits of a set Q into the part of the cage inside a
    house, so the rest of Q lies in the house outside the cage -- where only that many cells can take them."""
    nm, p = ctx.nm, ctx.p
    xm = ctx.xm or {}
    kg, hi, mask, mq, need = (
        xm.get("cage"),
        xm.get("house"),
        xm.get("digit_mask", 0),
        xm.get("max_in_cage"),
        xm.get("need_outside"),
    )
    if kg is None or hi is None or not mask:
        return _generic(ctx)
    Q = [d for d in range(1, p.D + 1) if mask >> (d - 1) & 1]
    g = p.groups[kg]
    tot = getattr(g, "total", None)
    qs = nm.digits(Q, "and")
    cells = sorted({c for c, _ in ctx.elims})
    most = {0: "none of", 1: "at most one of", 2: "at most two of"}.get(mq, f"at most {mq} of")
    teach = (
        f"The {tot} cage ({nm.cells(sorted(g.cells))}) can be filled only in a few ways, and every way puts {most} "
        f"{qs} into its cells in {nm.unit(hi)}. So {nm.unit(hi)} needs {'that digit' if need == 1 else f'{need} of them'} "
        f"outside the cage, and only {nm.cells(cells)} can take {'it' if need == 1 else 'them'}: "
        f"{'it holds' if len(cells) == 1 else 'they hold'} only {qs}. So {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(ctx, digits=Q, base_units=[hi], base_cells=sorted(g.cells), cover_cells=cells)
    return _result(
        ctx, J, f"{fmt_elims(nm, ctx.elims)}: the {tot} cage holds {most} {qs} in {nm.unit(hi)}", teach, True
    )


def _h_clique_house(ctx):
    """CliqueHouse: cells that pairwise must differ act as a house; |K| cells with |K| candidates hold each once."""
    nm, p = ctx.nm, ctx.p
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    mask = (ctx.xm or {}).get("digit_mask", 0)
    U = [d for d in range(1, p.D + 1) if mask >> (d - 1) & 1]
    head, goal = _x_head(ctx)
    why = (
        f"{_cap(nm.cells(pc))} all have to be different from each other -- each pair shares a house or a rule "
        f"that forbids equal digits -- so together they work like a house. Between them they can only hold "
        f"{nm.digits(U, 'and')}: {len(pc)} cells, {len(U)} digits, so each of these digits is in them exactly once"
    )
    tail = (
        f". {_cap(goal)}."
        if ctx.place
        else f", and any cell that has to differ from all of them loses those digits. So {goal}."
    )
    J = _J(ctx, digits=U, base_cells=pc)
    return _result(
        ctx, J, f"{head}: a virtual house of {len(pc)} different cells", why + tail, bool(pc), extra_cells=pc
    )


def _h_line_sets(ctx):
    """LineSets: renbans meeting one house must use different digits there; their consecutive runs, chosen
    jointly, leave some digits impossible."""
    nm = ctx.nm
    hi = (ctx.xm or {}).get("house")
    nl = (ctx.xm or {}).get("lines", 2)
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    head, goal = _x_head(ctx)
    hn = nm.unit(hi) if hi is not None else "a house"
    teach = (
        f"{nl} renban lines pass through {hn}. Each holds a run of consecutive digits, and inside {hn} the lines "
        f"must use different digits. Trying the runs each line can still take, together, no combination puts "
        f"these digits where they are pencilled. So {goal}."
    )
    J = _J(ctx, base_units=[hi] if hi is not None else [], base_cells=pc)
    return _result(ctx, J, f"{head}: renban digit sets in {hn}", teach, bool(pc), extra_cells=pc)


def _h_line_clues(ctx):
    """LineClues: a row / column with several outside clues, its possible fillings checked against all of them."""
    nm = ctx.nm
    hi = (ctx.xm or {}).get("house")
    nclue = (ctx.xm or {}).get("clues", 2)
    head, goal = _x_head(ctx)
    hn = nm.unit(hi) if hi is not None else "this line"
    teach = (
        f"{_cap(hn)} has {nclue} clues outside the grid. Take them together: every way to fill {hn} that fits one "
        f"clue must fit the others too (overlapping or touching segments share their digits). No filling that "
        f"satisfies all of them puts these digits where they are pencilled. So {goal}."
    )
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    J = _J(ctx, base_units=[hi] if hi is not None else [], base_cells=pc)
    return _result(ctx, J, f"{head}: the clues of {hn} together", teach, bool(pc), extra_cells=pc)


def _h_weighted_sums(ctx):
    """WeightedSums: sum facts (houses, cages, sum rules, arrows, equal sums) added / subtracted with small
    multiples until only a few cells remain, some counted more than once."""
    xm = ctx.xm or {}
    head, goal = _x_head(ctx)
    pc = (ctx.raw_engine or {}).get("pattern_cells") or []
    k, nf, mw = xm.get("total"), xm.get("facts", 2), xm.get("max_weight", 1)
    times = {2: "twice", 3: "three times"}.get(mw, f"{mw} times") if mw and mw > 1 else None
    teach = (
        f"Add up {nf} sum facts (whole houses add to 45; cages, sum lines and arrows give their totals), some of "
        f"them more than once or subtracted, so that almost every cell cancels"
        + (f" and the cells left are counted up to {times}" if times else "")
        + f". What remains is a short sum equal to {k} (after the placed digits), and only some digits fit it. "
        f"So {goal}."
    )
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: weighted sum of {nf} facts", teach, bool(pc), extra_cells=pc)


def _h_fireworks(ctx):
    """Fireworks (sudokuwiki): three digits each confined to a cell X, one cell A of X's row outside X's box and one
    cell B of X's column outside it -> A, B, X hold exactly those digits."""
    nm, p = ctx.nm, ctx.p
    xm = ctx.xm or {}
    x, a, b, mask, bx = xm.get("cell_x"), xm.get("cell_a"), xm.get("cell_b"), xm.get("digit_mask", 0), xm.get("region")
    if x is None or a is None or b is None:
        return _generic(ctx)
    ds = [d for d in range(1, p.D + 1) if mask >> (d - 1) & 1]
    row = next((g for g in p.groups_of[x] if p.groups[g].kind == "row"), None)
    col = next((g for g in p.groups_of[x] if p.groups[g].kind == "col"), None)
    box = nm.unit(bx) if bx is not None else "its box"
    dl = nm.digits(ds, "and")
    teach = (
        f"Look at {nm.unit(row)} and {nm.unit(col)}, which cross at {nm.cell(x)} in {box}. Outside {box}, "
        f"{dl} can go only in {nm.cell(a)} in the row and only in {nm.cell(b)} in the column. So each of these "
        f"digits is in {nm.cell(a)}, in {nm.cell(b)} or in {nm.cell(x)}: if it is in neither {nm.cell(a)} nor "
        f"{nm.cell(b)}, the row's copy and the column's copy are both inside {box}, which holds only one, so "
        f"it is where they cross, {nm.cell(x)}. Three digits for three cells: {nm.cells([a, b, x])} hold exactly "
        f"{dl}, so {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(
        ctx,
        digits=ds,
        base_units=[g for g in (row, col) if g is not None],
        cover_units=[bx] if bx is not None else [],
        base_cells=[a, b, x],
    )
    return _result(ctx, J, f"{fmt_elims(nm, ctx.elims)}: fireworks on {dl} ({nm.cells([a, b, x])})", teach, True)


def _h_chute_rp(ctx):
    """Chute Remote Pairs: bivalue cells A, B = {x, y} in one band / stack, different boxes and lines; the third
    box's cells on the remaining line hold no x -> A or B is y -> y leaves the cells that see both."""
    nm, xm = ctx.nm, ctx.xm or {}
    a, b, absent = xm.get("cell_a"), xm.get("cell_b"), xm.get("absent")
    if a is None or b is None or not absent:
        return _h_pattern_named(
            "chute remote pairs",
            "Two identical pairs in one band, in different boxes and lines: "
            "if the third box's segment has no x, one of them is y.",
        )(ctx)
    st = ctx.st
    pair = [d for d in range(1, nm.p.D + 1) if (st.cand[a] >> (d - 1)) & 1]
    y = next((d for d in pair if d != absent), None)
    pc = [c for c in (ctx.raw_engine.get("pattern_cells") or []) if c not in (a, b)]
    (ra, ca), (rb, cb_) = nm.p.coords[a], nm.p.coords[b]
    chute = ("band" if ra // 3 == rb // 3 else "stack" if ca // 3 == cb_ // 3 else "chute") if nm.p.D == 9 else "chute"
    teach = (
        f"{nm.cell(a)} and {nm.cell(b)} both hold {nm.digits(pair, 'or')} and sit in the same {chute}, in different "
        f"boxes and different lines. If neither were {y}, both would be {absent}, and the third box of the {chute} would "
        f"need its {absent} on the one remaining line" + (f" ({nm.cells(pc)})" if pc else "") + f" -- but {absent} "
        f"can't go there. So at least one of them is {y}, and cells seeing both lose {y}: {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(ctx, digits=pair, base_cells=[a, b], cover_cells=pc)
    return _result(
        ctx,
        J,
        f"{fmt_elims(nm, ctx.elims)}: chute remote pairs {nm.cell(a)}-{nm.cell(b)}",
        teach,
        True,
        extra_cells=set(pc) | {a, b},
    )


def _changed_cells(ctx):
    """the cells a move places or eliminates in, in grid order (when the engine names no pattern cells)"""
    cells = {c for c, _ in ctx.elims} | ({ctx.place[0]} if ctx.place else set())
    return sorted(cells, key=lambda c: ctx.nm.p.coords[c])


def _h_clue_facts(ctx):
    """ClueFacts / ClueShape: digits ruled out by the clues alone, before any digit of the grid is used (a thermometer
    cell's range, no 5 on a German whisper, a dot pair's digits; the shape form adds partners on one rule in one house)."""
    nm = ctx.nm
    pc = (ctx.raw_engine or {}).get("pattern_cells") or _changed_cells(ctx)
    head, goal = _x_head(ctx)
    if ctx.tech == S.CLUE_SHAPE:
        why = (
            f"Read the rules on {nm.cells(pc)} with the houses they cross: cells of one rule that share a house must hold "
            "different digits, and the rule leaves too few digits for that"
        )
        title = "the clues' shape"
    else:
        why = (
            f"Look at the rules on {nm.cells(pc)} alone, before any digit is placed: where a cell sits on its rule limits "
            "what it can hold (a thermometer cell needs room for the cells above and below it, a German whisper cell "
            "cannot be 5, a dot pair only takes certain digits)"
        )
        title = "the clues alone"
    J = _J(ctx, base_cells=pc)
    return _result(ctx, J, f"{head}: {title}", f"{why}. So {goal}.", bool(pc), extra_cells=pc)


def _h_class_colour(ctx):
    """ClassColouring: rule links that always join a low and a high digit (or an odd and an even one) colour cells in
    two classes; a known cell or a house's count of each class fixes the colours."""
    nm = ctx.nm
    xm = ctx.xm or {}
    pc = (ctx.raw_engine or {}).get("pattern_cells") or _changed_cells(ctx)
    D = nm.p.D
    if xm.get("kind", 0) == 0:
        a, b = (
            f"low (1–{D // 2})",
            f"high ({D - D // 2 + 1}–{D})",
        )
    else:
        a, b = "odd", "even"
    head, goal = _x_head(ctx)
    base = (
        f"The rules linking {nm.cells(pc)} always join a {a.split()[0]} digit to a {b.split()[0]} one (or always two of "
        f"the same kind), so these cells split into two colours: one colour is {a}, the other {b}"
    )
    why = {
        0: ", and a cell whose digit is already known says which colour is which",
        1: ", and counting fixes which is which: a house holds only so many digits of each kind",
        2: "; either way round, the coloured cells fill a house's share of one kind, so the house's other cells cannot "
        "have it",
    }.get(xm.get("why"), "")
    J = _J(ctx, base_cells=pc)
    return _result(
        ctx,
        J,
        f"{head}: {a.split()[0]} / {b.split()[0]} colouring",
        f"{base}{why}. So {goal}.",
        bool(pc),
        extra_cells=pc,
    )


def _h_empty_rect(ctx):
    """Empty Rectangle: a box whose candidates for d lie on one row + one column of it, a conjugate pair on a
    line through the box's column (or row), and the cell where the pair's other end and the box's row meet."""
    nm = ctx.nm
    ch = (ctx.raw_engine or {}).get("chain") or []
    if len(ch) != 4 or not ctx.elims or "group" not in ch[1] or "cell" not in ch[0] or "cell" not in ch[3]:
        return _h_chain(ctx)
    d = ch[0]["digit"]
    a, grp, c, e = ch[0]["cell"], ch[1]["group"], ch[2].get("cell"), ch[3]["cell"]
    box_g, line_g = ctx.gi(ch[1].get("via")), ctx.gi(ch[3].get("via"))
    if box_g is None or line_g is None or c is None:
        return _h_chain(ctx)
    box, pair_line = nm.unit(box_g), nm.unit(line_g)
    tgt = sorted({x for x, _ in ctx.elims})
    in_box = sorted([a] + list(grp), key=lambda x: nm.p.coords[x])
    teach = (
        f"In {box}, the {d}s can only go in {nm.cells(in_box, 'or')}: all on one row and one column of the box "
        f"(the rest of the box is an 'empty rectangle'). {_cap(pair_line)} has only two places for {d}: "
        f"{nm.cell(c)} and {nm.cell(e)}. If {nm.cell(e)} is not {d}, then {nm.cell(c)} is, which removes {d} from "
        f"{nm.cells(sorted(grp))} (they see {nm.cell(c)}), so {box}'s {d} must be {nm.cell(a)}. "
        f"Either {nm.cell(e)} or {nm.cell(a)} holds {d}, and {nm.cells(tgt)} "
        f"{'sees' if len(tgt) == 1 else 'see'} both, so {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(ctx, digits=[d], base_units=[box_g], cover_units=[line_g], base_cells=in_box, cover_cells=[c, e])
    return _result(
        ctx,
        J,
        f"{fmt_elims(nm, ctx.elims)}: empty rectangle in {box} with the pair {nm.cell(c)}-{nm.cell(e)}",
        teach,
        True,
        extra_cells=set(in_box) | {c, e},
    )
