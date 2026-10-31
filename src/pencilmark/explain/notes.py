"""Pencil-mark techniques: locked candidates, subsets, fish, wings, colouring; uniqueness. (split from explain.py)"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .. import solver as S
from ..model import bit, digits_of, popcount
from .base import _J, _cap, _elim_digits, _generic, _join, _rel_ex, _result, _subj, fmt_elims, rel_label
from .catalog import fish_shape


# ------------------------------------------------------------ notes: locked --
def _h_locked(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    name = ctx.m.name or ""
    v = _elim_digits(ctx)[0] if ctx.elims else None
    bi = ai = None
    eb, ec = ctx.engine.get("base_units") or [], ctx.engine.get("cover_units") or []
    if len(eb) == 1 and len(ec) == 1:
        bi, ai = eb[0], ec[0]
        ctx.used_engine = True
    elif "->" in name:
        bname, aname = name.split("->")
        bi, ai = ctx.gi(bname), ctx.gi(aname)
    if bi is None or ai is None:
        for b in p.houses:
            poss = [c for c in p.groups[b].cells if not st.vals[c] and st.cand[c] & bit(v)]
            for a in range(len(p.groups)):
                if (
                    a != b
                    and poss
                    and all(c in p.groups[a].cells for c in poss)
                    and all(c in p.groups[a].cells and c not in p.groups[b].cells for c, _ in ctx.elims)
                ):
                    bi, ai = b, a
                    break
            if bi is not None:
                break
    if bi is None:
        return _generic(ctx)
    B, A = p.groups[bi], p.groups[ai]
    poss = [c for c in B.cells if not st.vals[c] and st.cand[c] & bit(v)]
    ok = all(c in A.cells for c in poss) and all(c in A.cells and c not in B.cells for c, _ in ctx.elims)
    ub, ua = nm.unit(bi), nm.unit(ai)
    tg = sorted({c for c, _ in ctx.elims})
    if A.kind == "cage":
        short = f"{fmt_elims(nm, ctx.elims)}: the {v} of {ub} must sit inside {nm.cage(ai, cells=False)}"
        teach = (
            f"In {ub} the {v} can only go in {nm.cells(poss, 'or')}, and all of them are inside "
            f"{nm.cage(ai)}. So that cage contains the {v}, and since a cage can't repeat a digit, "
            f"{nm.cells(tg)} can't be {v}."
        )
    elif B.kind in ("row", "col") and A.kind not in ("row", "col"):
        short = f"{fmt_elims(nm, ctx.elims)}: claiming -- the {v} of {ub} is confined to {ua}"
        teach = ctx.pick(
            [
                f"Look at the {v}s in {ub}: they only appear in {nm.cells(poss)}, all inside {ua}. Whichever one is "
                f"right, {ua}'s {v} is on {ub}, so the other cells of {ua} -- {nm.cells(tg)} -- can't be {v}. "
                f"This 'claiming' (box-line) pattern is worth checking whenever a line's candidates for a digit "
                f"bunch up in one box.",
                f"{_cap(ub)} can only place its {v} in {nm.cells(poss, 'or')} -- all in {ua}. That {v} is therefore "
                f"{ua}'s {v} as well, which clears {v} from {nm.cells(tg)}.",
            ]
        )
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: pointing -- the {v}s of {ub} are locked into {ua}"
        teach = ctx.pick(
            [
                f"In {ub} the {v} can only go in {nm.cells(poss, 'or')}, which all lie in {ua}. So {ub}'s {v} is "
                f"also {ua}'s {v}, and nothing else in {ua} can be {v}: remove it from {nm.cells(tg)}. "
                f"Look for boxes where a digit's notes line up in a single row or column.",
                f"The {v}s of {ub} line up: {nm.cells(poss)}, all on {ua}. Whichever is true, it supplies "
                f"{ua}'s {v} -- so {nm.cells(tg)} lose their {v}.",
            ]
        )
    J = _J(ctx, digits=[v], base_units=[bi], cover_units=[ai], base_cells=poss, cover_cells=tg)
    return _result(ctx, J, short, teach, ok)


# ----------------------------------------------------------- notes: subsets --
def _h_subset(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    k = {S.NPAIR: 2, S.HPAIR: 2, S.NTRIPLE: 3, S.HTRIPLE: 3, S.NQUAD: 4, S.HQUAD: 4}[ctx.tech]
    naked = ctx.tech in (S.NPAIR, S.NTRIPLE, S.NQUAD)
    gi = ctx.gi(ctx.m.name)
    houses = [gi] if gi is not None else p.houses
    found = None
    eb, pc = ctx.engine.get("base_units") or [], ctx.engine.get("pattern_cells") or []
    if len(eb) == 1 and len(pc) == k:
        u = 0
        for c in pc:
            u |= st.cand[c]
        if naked and popcount(u) == k:
            found = (eb[0], tuple(sorted(pc)), u)
        elif not naked:
            emp = [c for c in p.groups[eb[0]].cells if not st.vals[c]]
            keep = 0
            for d in digits_of(p.full & ~st.placed_g(eb[0])):
                cs = {c for c in emp if st.cand[c] & bit(d)}
                if cs and cs <= set(pc):
                    keep |= bit(d)
            if popcount(keep) == k:
                found = (eb[0], tuple(sorted(pc)), keep)
        if found:
            ctx.used_engine = True
            houses = []
    for hi in houses:
        emp = [c for c in p.groups[hi].cells if not st.vals[c]]
        if naked:
            small = [c for c in emp if 2 <= popcount(st.cand[c]) <= k]
            for combo in combinations(small, k):
                u = 0
                for c in combo:
                    u |= st.cand[c]
                if popcount(u) != k:
                    continue
                el = {(c, d) for c in emp if c not in combo for d in digits_of(st.cand[c] & u)}
                if set(ctx.elims) <= el and el:
                    found = (hi, combo, u)
                    break
        else:
            missing = list(digits_of(p.full & ~st.placed_g(hi)))
            pos = {d: frozenset(c for c in emp if st.cand[c] & bit(d)) for d in missing}
            cands = [d for d in missing if 2 <= len(pos[d]) <= k]
            for combo in combinations(cands, k):
                cells = frozenset().union(*(pos[d] for d in combo))
                if len(cells) != k:
                    continue
                keep = sum(bit(d) for d in combo)
                el = {(c, d) for c in cells for d in digits_of(st.cand[c] & ~keep)}
                if set(ctx.elims) <= el and el:
                    found = (hi, tuple(sorted(cells)), keep)
                    break
        if found:
            break
    if not found:
        return _generic(ctx)
    hi, cells, u = found
    if naked:
        okset = {
            (c, d) for c in p.groups[hi].cells if not st.vals[c] and c not in cells for d in digits_of(st.cand[c] & u)
        }
    else:
        okset = {(c, d) for c in cells for d in digits_of(st.cand[c] & ~u)}
    sub_ok = set(ctx.elims) <= okset
    word = {2: "pair", 3: "triple", 4: "quad"}[k]
    U = nm.unit(hi)
    ds = list(digits_of(u))
    cl = ", ".join(f"{nm.cell(c)} {nm.cset(st.cand[c])}" for c in nm.sort(cells))
    tg = sorted({c for c, _ in ctx.elims})
    if naked:
        short = f"{fmt_elims(nm, ctx.elims)}: naked {word} {'/'.join(map(str, ds))} in {U}"
        teach = ctx.pick(
            [
                f"In {U}, the cells {cl} use only the digits {nm.digits(ds, 'and')} between them. {k} cells, {k} digits: "
                f"those digits must fill exactly those cells, so no other cell of {U} can have them -- clear them from "
                f"{nm.cells(tg)}.",
                f"Spot the {word}: {cl} in {U}. However they are arranged, {nm.digits(ds, 'and')} are used up there, "
                f"which removes them from {nm.cells(tg)}.",
            ]
        )
        J = _J(ctx, digits=ds, base_units=[hi], base_cells=list(cells), cover_cells=tg)
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: hidden {word} {'/'.join(map(str, ds))} in {U}"
        teach = ctx.pick(
            [
                f"In {U}, the digits {nm.digits(ds, 'and')} can only go in {nm.cells(cells)} ({cl}). {k} digits squeezed "
                f"into {k} cells means those cells are exactly these digits, so their other candidates go. Hidden "
                f"subsets are found by scanning digits, not cells: look for digits with only two or three spots.",
                f"Track where {nm.digits(ds, 'and')} can go in {U}: only {nm.cells(cells)}. They take those cells "
                f"between them, so everything else pencilled there is wrong.",
            ]
        )
        J = _J(ctx, digits=ds, base_units=[hi], base_cells=list(cells), cover_cells=list(cells))
    return _result(ctx, J, short, teach, sub_ok)


# -------------------------------------------------------------- fish --------
def _fish_search(p, st, v, k, elims, finned=False, max_fins=3, lines_only=False):
    b = bit(v)
    hs = [h for h in p.houses if p.groups[h].kind in ("row", "col")] if lines_only else p.houses
    pos = {h: frozenset(c for c in p.groups[h].cells if not st.vals[c] and st.cand[c] & b) for h in hs}
    hc = {h: frozenset(p.groups[h].cells) for h in hs}
    tset = set(elims)
    bases = [h for h in hs if 2 <= len(pos[h]) <= (k + max_fins if finned else k)]
    for combo in combinations(bases, k):
        if any(hc[a] & hc[c] for a, c in combinations(combo, 2)):
            continue
        U = frozenset().union(*(pos[h] for h in combo))
        covers = [h for h in hs if h not in combo and pos[h] & U]
        for cov in combinations(covers, k):
            if any(hc[a] & hc[c] for a, c in combinations(cov, 2)):
                continue
            CU = frozenset().union(*(hc[h] for h in cov))
            fins = U - CU
            if not finned and fins:
                continue
            if finned and not (1 <= len(fins) <= max_fins):
                continue
            el = set()
            for h in cov:
                for c in pos[h]:
                    if c in U:
                        continue
                    if fins and not all(c in p.peers[f] for f in fins):
                        continue
                    el.add((c, v))
            if tset <= el:
                return combo, cov, U, fins
    return None


def _h_fish(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    v = _elim_digits(ctx)[0]
    k = {S.XWING: 2, S.SWORDFISH: 3, S.JELLYFISH: 4}.get(ctx.tech) or ctx.xm.get("size") or 2
    finned = ctx.tech == S.FINNED_FISH
    res = _engine_fish(ctx, v)
    if res:
        k = len(res[0])
    for kk in [] if res else [k] if not finned else [k, 2, 3, 4]:
        res = _fish_search(p, st, v, kk, ctx.elims, finned=finned)
        if res:
            k = kk
            break
    if not res:
        return _generic(ctx)
    base, cov, U, fins = res
    fkey, adj = fish_shape(p, base, cov, fins, U)
    plain = False
    if adj in (
        "Franken",
        "Mutant",
    ):  # a box in base / cover, or mixed lines: prefer the same eliminations from a plain row / column fish
        for kk, fn in [(x, False) for x in range(2, len(base) + 1)] + [(x, True) for x in range(2, len(base) + 1)]:
            alt = _fish_search(p, st, v, kk, ctx.elims, finned=fn, lines_only=True)
            if alt and len({p.groups[h].kind for h in alt[0]}) == 1 and len({p.groups[h].kind for h in alt[1]}) == 1:
                base, cov, U, fins = alt
                k = kk
                fkey, adj = fish_shape(p, base, cov, fins, U)
                plain = True
                break
    size_name = {2: "X-Wing", 3: "Swordfish", 4: "Jellyfish"}.get(len(base), "Jellyfish")
    built = " ".join(
        x
        for x in (
            ("Sashimi" if adj == "Sashimi" else "Finned") if fins else "",
            adj if adj in ("Franken", "Mutant") else "",
            size_name,
        )
        if x
    )
    name = ctx.code if ctx.code and not ctx.code.startswith("Mutant") and len(ctx.code) > 3 and not plain else built
    name = name.replace("Sashimi Sashimi", "Sashimi")
    bn = _join([nm.unit(h) for h in base])
    cn = _join([nm.unit(h) for h in cov])
    tg = sorted({c for c, _ in ctx.elims})
    corner = "; ".join(f"{nm.unit(h)}: {nm.cells([c for c in U if c in p.groups[h].cells], 'or')}" for h in base)
    if not fins:
        short = f"{fmt_elims(nm, ctx.elims)}: {name} on {v} ({bn} / {cn})"
        if k == 2:
            teach = (
                f"Follow the {v}s in {bn}: each has exactly two spots ({corner}), and those spots line up in "
                f"{cn}. The two {v}s must sit on opposite corners of the rectangle, so they use up {cn}'s {v}s "
                f"-- {nm.cells(tg)} can't be {v}. X-Wings show up when a digit has only two places in two "
                f"parallel lines."
            )
        else:
            kw = {3: "three", 4: "four"}.get(k, str(k))
            teach = (
                f"Look at the {v}s in {bn} ({corner}). All of them fall inside {kw} houses: {cn}. Those {kw} "
                f"houses must each hold one {v}, and the {kw} {v}s of {bn} are exactly them -- so {v} disappears "
                f"from the rest of {cn}: {nm.cells(tg)}. Fish are found digit by digit: list where one digit can "
                f"go in every row (or column) and look for {kw} that share {kw} columns (or rows)."
            )
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: {name} on {v} with fin{'s' if len(fins) > 1 else ''} at {nm.cells(fins)}"
        teach = (
            f"The {v}s of {bn} ({corner}) almost form a {name.split()[-1]} over {cn} -- except for the "
            f"fin{'s' if len(fins) > 1 else ''} {nm.cells(fins)}. Either "
            f"{'a fin' if len(fins) > 1 else 'the fin'} is the {v} or the fish works; cells that the fish would "
            f"clear AND that see {'every fin' if len(fins) > 1 else 'the fin'} lose {v} either way: "
            f"{nm.cells(tg)}."
        )
    if adj == "Sashimi" or "Sashimi" in name:
        teach += (
            " It is a sashimi fish: one base house has only the fin and a single other candidate, so the "
            "pattern isn't even a complete fish without the fin."
        )
    if "Franken" in name:
        teach += " It is a Franken fish: a box takes the place of one of the rows or columns."
    elif adj == "Mutant":
        teach += " It is a mutant fish: rows and columns are mixed within the base (or cover) houses."
    J = _J(
        ctx,
        digits=[v],
        base_units=list(base),
        cover_units=list(cov),
        base_cells=sorted(U),
        fins=sorted(fins),
        cover_cells=tg,
        pattern=name,
    )
    r = _result(ctx, J, short, teach, True)
    if fins and "Franken" in name:
        fkey = "franken_fish"
    r["pattern_key"] = fkey
    return r


def _engine_fish(ctx, v):
    """Fish from the engine's base / cover units (step.move.explain)."""
    e = ctx.engine
    bu, cu = e.get("base_units") or [], e.get("cover_units") or []
    if not bu or not cu or len(bu) != len(cu):
        return None
    p, st = ctx.p, ctx.st
    U = {c for h in bu for c in p.groups[h].cells if not st.vals[c] and st.cand[c] & bit(v)}
    CU = {c for h in cu for c in p.groups[h].cells}
    ctx.used_engine = True
    return tuple(bu), tuple(cu), U, U - CU


# -------------------------------------------------------------- wings -------
def _h_wing(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    xyz = ctx.tech == S.XYZWING
    z = _elim_digits(ctx)[0]
    zb = bit(z)
    tset = set(ctx.elims)
    for piv in range(p.N):
        if st.vals[piv] or popcount(st.cand[piv]) != (3 if xyz else 2):
            continue
        pc = st.cand[piv]
        if xyz and not pc & zb:
            continue
        wings = [q for q in p.peer_list[piv] if not st.vals[q] and popcount(st.cand[q]) == 2 and st.cand[q] & zb]
        for w1, w2 in combinations(wings, 2):
            a, b2 = st.cand[w1], st.cand[w2]
            if xyz:
                if (a | b2) != pc or a == b2 or a & ~pc or b2 & ~pc or a & b2 != zb:
                    continue
                tg = p.peers[piv] & p.peers[w1] & p.peers[w2]
            else:
                if a == b2 or a & b2 != zb or (a | b2) & ~zb != pc or pc & zb:
                    continue
                tg = p.peers[w1] & p.peers[w2]
            el = {(c, z) for c in tg if c not in (piv, w1, w2) and not st.vals[c] and st.cand[c] & zb}
            if tset <= el:
                x, y = [d for d in digits_of(pc) if d != z][:2]
                tgc = sorted({c for c, _ in ctx.elims})
                name = "XYZ-Wing" if xyz else "XY-Wing"
                short = f"{fmt_elims(nm, ctx.elims)}: {name} with pivot {nm.cell(piv)}"
                if xyz:
                    teach = (
                        f"The pivot {nm.cell(piv)} {nm.cset(pc)} sees {nm.cell(w1)} {nm.cset(a)} and "
                        f"{nm.cell(w2)} {nm.cset(b2)}. If the pivot isn't {z}, it is {x} or {y}, which turns "
                        f"one of the wings into {z}; so one of the three cells is {z}. {_subj(nm, tgc)} "
                        f"see{'s' if len(tgc) == 1 else ''} all three and can't be {z}."
                    )
                else:
                    wx = w1 if st.cand[w1] & bit(x) else w2
                    wy = w2 if wx == w1 else w1
                    teach = ctx.pick(
                        [
                            f"Find a two-candidate pivot with two two-candidate wings: {nm.cell(piv)} {nm.cset(pc)} sees "
                            f"{nm.cell(wx)} {nm.cset(st.cand[wx])} and {nm.cell(wy)} {nm.cset(st.cand[wy])}. If the pivot "
                            f"is {x}, {nm.cell(wx)} becomes {z}; if it is {y}, {nm.cell(wy)} becomes {z}. Either way one "
                            f"wing is {z}, so {nm.cells(tgc)}, which see{'s' if len(tgc) == 1 else ''} both wings, "
                            f"can't be {z}.",
                            f"Pivot {nm.cell(piv)} {nm.cset(pc)}, wings {nm.cell(wx)} {nm.cset(st.cand[wx])} and "
                            f"{nm.cell(wy)} {nm.cset(st.cand[wy])}: whatever the pivot is, a wing ends up {z}. "
                            f"Remove {z} from every cell that sees both wings: {nm.cells(tgc)}.",
                        ]
                    )
                J = _J(ctx, digits=[z], base_cells=[piv, w1, w2], z=z, cover_cells=tgc)
                return _result(ctx, J, short, teach, True)
    return _generic(ctx)


# ------------------------------------------------------------- colouring ----
def _h_coloring(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    v = _elim_digits(ctx)[0]
    b = bit(v)
    adj, via = {}, {}
    for hi in p.houses:
        cs = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & b]
        if len(cs) == 2:
            x, y = cs
            adj.setdefault(x, set()).add(y)
            adj.setdefault(y, set()).add(x)
            via.setdefault(frozenset(cs), hi)
    color = {}
    for start in sorted(adj):
        if start in color:
            continue
        comp = {start: 0}
        stack = [start]
        while stack:
            x = stack.pop()
            for y in sorted(adj[x]):
                if y not in comp:
                    comp[y] = 1 - comp[x]
                    stack.append(y)
        color.update(comp)
        if len(comp) < 4:
            continue
        g = ([c for c in comp if comp[c] == 0], [c for c in comp if comp[c] == 1])
        wrap = None
        for side in (0, 1):
            for x, q in combinations(g[side], 2):
                if q in p.peers[x]:
                    wrap = (side, x, q)
                    break
            if wrap:
                break
        if wrap:
            el = {(c, v) for c in g[wrap[0]]}
        else:
            el = {
                (c, v)
                for c in range(p.N)
                if not st.vals[c]
                and c not in comp
                and st.cand[c] & b
                and p.peers[c] & set(g[0])
                and p.peers[c] & set(g[1])
            }
        if not set(ctx.elims) <= el:
            continue
        links = [
            {"a": (x, v), "b": (y, v), "strong": True, "source": "bilocal", "unit": via.get(frozenset((x, y)))}
            for x in comp
            for y in adj[x]
            if x < y
        ]
        tg = sorted({c for c, _ in ctx.elims})
        A, Bc = nm.cells(g[0]), nm.cells(g[1])
        short = f"{fmt_elims(nm, ctx.elims)}: colouring on {v}"
        if wrap:
            teach = (
                f"Colour the {v}s that form conjugate pairs (houses with exactly two {v}s): one colour is "
                f"{A}, the other {Bc}. Exactly one colour is the truth. But {nm.cell(wrap[1])} and "
                f"{nm.cell(wrap[2])} share a colour and see each other -- they can't both be {v}, so that "
                f"whole colour is false: remove {v} from {nm.cells(tg)}."
            )
        else:
            teach = (
                f"Chain the {v}s through houses where {v} has only two spots, alternating two colours: "
                f"{A} versus {Bc}. One colour holds all the real {v}s. {_subj(nm, tg)} "
                f"see{'s' if len(tg) == 1 else ''} a cell of each colour, so whichever colour wins, "
                f"{'it sees' if len(tg) == 1 else 'they see'} a {v} -- no {v} there."
            )
        J = _J(ctx, digits=[v], base_cells=g[0], cover_cells=g[1], links=links)
        chain = [[nm.cell(lk["a"][0]), nm.cell(lk["b"][0]), v, "strong"] for lk in links]
        return _result(ctx, J, short, teach, True, chain=chain)
    return _generic(ctx)


# ----------------------------------------------------------- pair relations --
def _h_pairarc(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    parts, base_cells, units = [], [], []
    ok = True
    by_cell = defaultdict(list)
    for c, d in ctx.elims:
        by_cell[c].append(d)
    gi = ctx.gi(ctx.m.name) if ctx.m.name else None
    for x, ds in sorted(by_cell.items()):
        done = False
        if gi is not None:  # relation pointing
            for v in digits_of(p.full & ~st.placed_g(gi)):
                poss = [c for c in p.groups[gi].cells if not st.vals[c] and st.cand[c] & bit(v)]
                if len(poss) < 2 or x in poss:
                    continue
                rm = p.full
                for c in poss:
                    rm &= _rel_ex(p, c, x, v)
                if all(rm & bit(d) for d in ds):
                    lab = rel_label(p, poss[0], x)
                    parts.append(
                        f"the {v} of {nm.unit(gi)} must be in {nm.cells(poss, 'or')}, and every one of "
                        f"those is {lab}-linked to {nm.cell(x)}, so {nm.cell(x)} can't be "
                        f"{nm.digits(ds)}"
                    )
                    base_cells += poss
                    units.append(gi)
                    done = True
                    break
        if not done:
            for a in sorted(set(p.nonconsec[x]) | set(p.neq[x])):
                if st.vals[a] or not st.cand[a]:
                    continue
                if all(all(_rel_ex(p, a, x, w) & bit(d) for w in digits_of(st.cand[a])) for d in ds):
                    lab = rel_label(p, a, x)
                    parts.append(
                        f"{nm.cell(x)} can't be {nm.digits(ds)}: its {lab} partner {nm.cell(a)} "
                        f"{nm.cset(st.cand[a])} would have no option left"
                    )
                    base_cells.append(a)
                    done = True
                    break
        ok &= done
        if not done:
            parts.append(f"{nm.cell(x)} loses {nm.digits(ds, 'and')}")
    short = (
        f"{fmt_elims(nm, ctx.elims)}: "
        + (rel_label(p, *(_first_rel(p, base_cells, by_cell))) or "pair rule")
        + " logic"
    )
    teach = (
        f"{_cap('; '.join(parts))}. Rules between neighbouring cells work both ways: every candidate needs "
        f"at least one partner value that is still possible. Check the cells along dots and lines whose "
        f"partners have few candidates."
    )
    J = _J(ctx, digits=_elim_digits(ctx), base_cells=base_cells, base_units=units)
    return _result(ctx, J, short, teach, ok)


def _first_rel(p, base_cells, by_cell):
    x = next(iter(by_cell))
    for a in base_cells:
        if rel_label(p, a, x):
            return a, x
    return x, x


# --------------------------------------------------------- uniqueness -------
def _rects(p):
    if getattr(p, "_xrects", None) is not None:
        return p._xrects
    out = []
    rows = [gi for gi in p.houses if p.groups[gi].kind == "row"]
    cols = [gi for gi in p.houses if p.groups[gi].kind == "col"]
    cell_at = {xy: i for i, xy in enumerate(p.coords)}
    boxes_of = {c: {gi for gi in p.groups_of[c] if p.groups[gi].kind in ("box", "region")} for c in range(p.N)}
    rr = sorted({p.coords[p.groups[g].cells[0]][0] for g in rows})
    cc = sorted({p.coords[p.groups[g].cells[0]][1] for g in cols})
    for r1, r2 in combinations(rr, 2):
        for c1, c2 in combinations(cc, 2):
            cs = [cell_at.get((r1, c1)), cell_at.get((r1, c2)), cell_at.get((r2, c1)), cell_at.get((r2, c2))]
            if None in cs:
                continue
            bx = set().union(*(boxes_of[c] for c in cs))
            if len(bx) == 2:
                out.append(cs)
    p._xrects = out
    return out


def _h_ur(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    x, y = ctx.xm.get("x"), ctx.xm.get("y")
    typ = ctx.xm.get("type") or 1
    tcells = {c for c, _ in ctx.elims}
    if ctx.code in ("AR1", "AR2"):
        pc = (ctx.raw_engine or {}).get("pattern_cells") or []
        if ctx.code == "AR1":
            short = f"{fmt_elims(nm, ctx.elims)}: avoidable rectangle {x}/{y}"
            teach = (
                f"{nm.cells(pc)} form a rectangle over two rows, two columns and two boxes; three corners were "
                f"solved (none is a given) as {x}/{y}. If the last corner were {x}, the {x}s and {y}s could be "
                f"swapped -- two solutions, which a setter must have prevented with a clue. So it is not {x}."
            )
        else:
            short = f"{fmt_elims(nm, ctx.elims)}: avoidable rectangle type 2 ({x}/{y})"
            teach = (
                f"{nm.cells(pc)} form a rectangle over two rows, two columns and two boxes; two corners were "
                f"solved (not givens) as {x} and {y}, and the other two each hold the digit that would complete "
                f"an interchangeable {x}/{y} rectangle plus one common extra digit. One of them must take the "
                f"extra, so it leaves every cell seeing both: {fmt_elims(nm, ctx.elims)}."
            )
        teach += " Uniqueness techniques rely on the puzzle having exactly one solution."
        J = _J(ctx, digits=[x, y], base_cells=pc, cover_cells=sorted(tcells))
        return _result(ctx, J, short, teach, bool(pc))
    for cs in _rects(p):
        if any(st.vals[c] for c in cs):
            continue
        common = st.cand[cs[0]] & st.cand[cs[1]] & st.cand[cs[2]] & st.cand[cs[3]]
        pairs = [(x, y)] if x and y else [(a, b) for a, b in combinations(digits_of(common), 2)]
        for a, b in pairs:
            xy = bit(a) | bit(b)
            if common & xy != xy:
                continue
            floor = [c for c in cs if st.cand[c] == xy]
            roof = [c for c in cs if c not in floor]
            if typ == 1 and not (len(floor) == 3 and tcells <= set(roof)):
                continue
            if typ in (2, 3, 4) and len(floor) != 2:
                continue
            if typ == 4 and not tcells <= set(roof):
                continue
            if typ == 5 and not len(floor) >= 1:
                continue
            if typ == 1:
                t = roof[0]
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle {a}/{b}"
                teach = (
                    f"{nm.cells(floor)} all hold just {{{a},{b}}}, and with {nm.cell(t)} they form a rectangle "
                    f"over two rows, two columns and two boxes. If {nm.cell(t)} were also {a} or {b}, the "
                    f"{a}s and {b}s could be swapped and the puzzle would have two solutions. A proper puzzle "
                    f"has one, so {nm.cell(t)} must be one of its other candidates: remove {a} and {b}."
                )
            elif typ == 2:
                extra = (st.cand[roof[0]] | st.cand[roof[1]]) & ~xy
                z = next(digits_of(extra))
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 2 ({a}/{b}, extra {z})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}}; the other corners {nm.cells(roof)} are "
                    f"{{{a},{b},{z}}}. To avoid the deadly {a}/{b} rectangle one of those two must be {z}, so "
                    f"any cell seeing both of them -- {nm.cells(sorted(tcells))} -- can't be {z}."
                )
            elif typ == 3:
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 3 ({a}/{b})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}}. The roof {nm.cells(roof)} must use one of its "
                    f"extra candidates to avoid a two-solution rectangle, so together they act like a single "
                    f"cell of those extras -- which forms a naked subset with other cells of their house and "
                    f"clears {fmt_elims(nm, ctx.elims)}."
                )
            elif typ == 4:
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 4 ({a}/{b})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}}. In the roof {nm.cells(roof)} one of the two "
                    f"digits is forced (it has no other place in their shared house), so the roof can't also "
                    f"use the other one -- that would complete the deadly rectangle. Remove it: "
                    f"{fmt_elims(nm, ctx.elims)}."
                )
            else:
                short = f"{fmt_elims(nm, ctx.elims)}: hidden unique rectangle ({a}/{b})"
                teach = (
                    f"The cells {nm.cells(cs)} form a rectangle on {a}/{b} across two boxes. Strong links on "
                    f"the far corner mean that placing {fmt_elims(nm, ctx.elims).split(' ≠ ')[-1]} there "
                    f"would complete an interchangeable {a}/{b} pattern -- two solutions -- so it goes."
                )
            teach += " Uniqueness techniques rely on the puzzle having exactly one solution."
            J = _J(ctx, digits=[a, b], base_cells=cs, cover_cells=sorted(tcells))
            return _result(ctx, J, short, teach, True)
    return _generic(ctx)


def _h_bug(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    if ctx.code == "BUG+2" or not ctx.place:
        tri = [q for q in range(p.N) if not st.vals[q] and popcount(st.cand[q]) == 3]
        others = [q for q in range(p.N) if not st.vals[q] and q not in tri]
        ok = len(tri) == 2 and all(popcount(st.cand[q]) == 2 for q in others)
        a, b = (tri + [None, None])[:2]
        short = f"{fmt_elims(nm, ctx.elims)}: BUG+2"
        teach = (
            f"Every unsolved cell has exactly two candidates except {nm.cell(a)} and {nm.cell(b)}. If both lost "
            f"their extra digit (the one appearing three times in their houses) the grid would be a 'bivalue "
            f"universal grave' -- every digit twice per house -- which never has exactly one solution. So at "
            f"least one extra digit is true, and whatever both cases rule out goes: "
            f"{fmt_elims(nm, ctx.elims)}."
        )
        J = _J(ctx, digits=_elim_digits(ctx), base_cells=[q for q in (a, b) if q is not None])
        return _result(ctx, J, short, teach, ok)
    c, v = ctx.place
    others = [q for q in range(p.N) if not st.vals[q] and q != c]
    ok = popcount(st.cand[c]) == 3 and all(popcount(st.cand[q]) == 2 for q in others)
    short = f"{nm.cell(c)} = {v}: BUG+1"
    teach = (
        f"Every unsolved cell has exactly two candidates except {nm.cell(c)} {nm.cset(st.cand[c])}. If "
        f"{nm.cell(c)} lost its extra digit the grid would be a 'bivalue universal grave' -- every digit "
        f"twice per house -- which always allows two solutions. So {nm.cell(c)} takes the digit that appears "
        f"three times in its houses: {v}."
    )
    J = _J(ctx, digits=[v], base_cells=[c])
    return _result(ctx, J, short, teach, ok)
