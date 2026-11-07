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
    r = _result(ctx, J, short, teach, ok)
    if ok:
        where = f"inside {nm.cage(ai, cells=False)}" if A.kind == "cage" else f"in {ua}"
        why = (
            f"A cage can't repeat a digit, so the cage's other cells can't be {v}."
            if A.kind == "cage"
            else f"{_cap(ua)} holds one {v}, and {ub}'s {v} is going to be it."
        )
        r["substeps"] = _simple_substeps(
            nm,
            f"In {ub}, the {v} can only go in {nm.cells(poss, 'or')}.",
            [(c, v) for c in poss],
            f"All of them lie {where}.",
            why,
            ctx.elims,
        )
    return r


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
    r = _result(ctx, J, short, teach, sub_ok)
    if sub_ok:
        marks = [(c, d) for c in nm.sort(cells) for d in ds if st.cand[c] & bit(d)]
        if naked:
            first, second = f"In {U}, the cells {cl} hold only {nm.digits(ds, 'and')} between them.", None
            why = f"{_KW[k]} cells with only {_KW[k].lower()} digits: those digits fill exactly these cells, so no other cell of {U} has them."
        else:
            first = f"In {U}, the digits {nm.digits(ds, 'and')} can only go in {nm.cells(cells)}."
            second = None
            why = f"{_KW[k]} digits with only {_KW[k].lower()} places: these cells hold exactly these digits, so their other candidates go."
        r["substeps"] = _simple_substeps(nm, first, marks, second, why, ctx.elims)
    return r


_KW = {2: "Two", 3: "Three", 4: "Four"}


def _simple_substeps(nm, first, marks, second, why, elims):
    """a short pattern as sub-steps: where the digits can go (blue candidates), the consequence with its reason, the
    removals in red"""
    ids = iter(range(1, 10**6))
    out = [
        {
            "text": first,
            "annotations": [{"id": next(ids), "candidate": f"{nm.cell(c)}#{d}", "colour": "blue"} for c, d in marks],
        }
    ]
    if second:
        out.append({"text": second, "why": why})
    else:
        out[0]["why"] = why
    out.append(
        {
            "text": f"So {fmt_elims(nm, elims)}.",
            "annotations": [
                {"id": next(ids), "candidate": f"{nm.cell(c)}#{d}", "colour": "red"} for c, d in sorted(elims)
            ],
        }
    )
    return out


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
    r["substeps"] = _fish_substeps(nm, v, base, cov, U, fins, ctx.elims)
    if "Franken" in name or adj == "Mutant":  # the shape, before the removals
        r["substeps"].insert(
            -1,
            {
                "text": "A box takes the place of a row or column (Franken fish)."
                if "Franken" in name
                else "Rows and columns are mixed in the base or cover houses (Mutant fish)."
            },
        )
    return r


def _fish_substeps(nm, v, base, cov, U, fins, elims):
    """a fish as sub-steps: the digit's places in the base houses (blue), all inside the cover houses, the fins
    (orange) if any, the removals (red)"""
    ids = iter(range(1, 10**6))
    bn, cn = _join([nm.unit(h) for h in base]), _join([nm.unit(h) for h in cov])
    corner = "; ".join(f"{nm.unit(h)}: {nm.cells([c for c in U if c in nm.p.groups[h].cells], 'or')}" for h in base)
    out = [
        {
            "text": f"Look at the {v}s in {bn}: {corner}.",
            "annotations": [
                {"id": next(ids), "candidate": f"{nm.cell(c)}#{v}", "colour": "blue"}
                for c in sorted(U)
                if c not in fins
            ],
        },
        {
            "text": f"Apart from {'the fins' if len(fins) > 1 else 'the fin'}, they all lie in {cn}."
            if fins
            else f"They all lie in {cn}.",
            "why": f"Each of {bn} needs a {v}, and those {v}s can only go in {cn}; so they are the {v}s of {cn}, "
            f"and no other cell there can be {v}.",
        },
    ]
    if fins:
        out.append(
            {
                "text": f"Either {'a fin' if len(fins) > 1 else 'the fin'} ({nm.cells(sorted(fins))}) is the {v}, or the "
                f"fish works; only cells that the fish clears and that see {'every fin' if len(fins) > 1 else 'the fin'} "
                f"lose {v} either way.",
                "annotations": [
                    {"id": next(ids), "candidate": f"{nm.cell(c)}#{v}", "colour": "orange"} for c in sorted(fins)
                ],
            }
        )
    out.append(
        {
            "text": f"So {fmt_elims(nm, elims)}.",
            "annotations": [
                {"id": next(ids), "candidate": f"{nm.cell(c)}#{d}", "colour": "red"} for c, d in sorted(elims)
            ],
        }
    )
    return out


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
                r = _result(ctx, J, short, teach, True)
                r["substeps"] = _wing_substeps(nm, st, piv, w1, w2, x, y, z, xyz, ctx.elims)
                return r
    return _generic(ctx)


def _wing_substeps(nm, st, piv, w1, w2, x, y, z, xyz, elims):
    """XY-Wing / XYZ-Wing as sub-steps: pivot (cyan) and wings (green), what each pivot digit forces, the removals"""
    ids = iter(range(1, 10**6))
    cell = lambda c, col: {"id": next(ids), "cell": nm.cell(c), "colour": col}
    wx = w1 if st.cand[w1] & bit(x) else w2
    wy = w2 if wx == w1 else w1
    out = [
        {
            "text": f"{_cap(nm.cell(piv))} {nm.cset(st.cand[piv])} sees {nm.cell(wx)} {nm.cset(st.cand[wx])} and "
            f"{nm.cell(wy)} {nm.cset(st.cand[wy])}.",
            "annotations": [cell(piv, "cyan"), cell(wx, "green"), cell(wy, "green")],
        }
    ]
    arrow = lambda a, da, b, db: {
        "id": next(ids),
        "arrow": [f"{nm.cell(a)}#{da}", f"{nm.cell(b)}#{db}"],
        "line": "plain",
    }
    why = "A cell holds one digit, and cells that see each other can't share one."
    out.append(
        {
            "text": f"If {nm.cell(piv)} is {x}, then {nm.cell(wx)} is {z}.",
            "why": why,
            "annotations": [arrow(piv, x, wx, z)],
        }
    )
    out.append({"text": f"If {nm.cell(piv)} is {y}, then {nm.cell(wy)} is {z}.", "annotations": [arrow(piv, y, wy, z)]})
    tg = sorted({c for c, _ in elims})
    if xyz:
        last = (
            f"If {nm.cell(piv)} is {z}, it is the {z} itself: so one of the three cells is {z}, and "
            f"{nm.cells(tg)}, which see{'s' if len(tg) == 1 else ''} all three, can't be {z}."
        )
    else:
        last = (
            f"Either way one wing is {z}, and {nm.cells(tg)} see{'s' if len(tg) == 1 else ''} both wings, so "
            f"{'it' if len(tg) == 1 else 'they'} can't be {z}."
        )
    out.append(
        {
            "text": last,
            "annotations": [
                {"id": next(ids), "candidate": f"{nm.cell(c)}#{d}", "colour": "red"} for c, d in sorted(elims)
            ],
        }
    )
    return out


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
        if not wrap:  # unit wrap: a colour seeing every v of a house (none of them its own) would empty it
            for side in (0, 1):
                for hi in p.houses:
                    hc = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & b]
                    if hc and all(
                        comp.get(c) == 1 - side if c in comp else bool(p.peers[c] & set(g[side])) for c in hc
                    ):
                        wrap = (side, None, hi)
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
        if wrap and wrap[1] is None:
            teach = (
                f"Colour the {v}s that form conjugate pairs (houses with exactly two {v}s): one colour is "
                f"{A}, the other {Bc}. Exactly one colour is the truth. But if {nm.cells(g[wrap[0]])} were {v}, "
                f"{nm.unit(wrap[2])} would have no place left for {v}, so that whole colour is false: remove {v} "
                f"from {nm.cells(tg)}."
            )
        elif wrap:
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
        res = _result(ctx, J, short, teach, True, chain=chain)
        res["substeps"] = _colouring_substeps(nm, v, comp, adj, via, wrap, tg, ctx.elims)
        return res
    return _generic(ctx)


def _colouring_substeps(nm, v, comp, adj, via, wrap, tg, elims):
    """simple colouring as sub-steps: the legend, each conjugate pair in turn (the next cell takes the other colour),
    then the clash (wrap) or the cells that see both colours (trap), the removals in red"""
    names = ("blue", "yellow")
    ids = iter(range(1, 10**6))
    ann = lambda c: {"id": next(ids), "candidate": f"{nm.cell(c)}#{v}", "colour": names[comp[c]]}
    start = min(comp, key=lambda c: nm.p.coords[c])
    out = [
        {
            "text": f"Colour the {v}s that are one of only two places in a house, alternating blue and yellow, "
            f"starting with {nm.cell(start)}.",
            "legend": {
                "blue": f"all of these are {v}, or none are",
                "yellow": f"the other colour: one colour holds the {v}s",
            },
            "annotations": [ann(start)],
        }
    ]
    seen, queue = {start}, [start]
    why = f"If one of a house's only two places for {v} isn't {v}, the other is; so the two take different colours."
    while queue:
        x = queue.pop(0)
        for y in sorted(adj[x], key=lambda c: nm.p.coords[c]):
            if y in seen:
                continue
            seen.add(y)
            queue.append(y)
            hi = via.get(frozenset((x, y)))
            where = nm.unit(hi) if hi is not None else "a house"
            stp = {
                "text": f"{v} has only two places in {where}: {nm.cell(x)} and {nm.cell(y)}, so {nm.cell(y)} is "
                f"{names[comp[y]]}.",
                "annotations": [
                    ann(y),
                    {"id": next(ids), "arrow": [f"{nm.cell(x)}#{v}", f"{nm.cell(y)}#{v}"], "line": "strong"},
                ],
            }
            if len(out) == 1:
                stp["why"] = why
            out.append(stp)
    red = [{"id": next(ids), "candidate": f"{nm.cell(c)}#{d}", "colour": "red"} for c, d in sorted(elims)]
    if wrap and wrap[1] is None:
        side, _, hi = wrap
        out.append(
            {
                "text": f"Every place for {v} in {nm.unit(hi)} is {names[1 - side]} or sees a {names[side]} {v}, so "
                f"{names[side]} would leave it no {v}: {names[side]} is false, no {names[side]} cell is {v}.",
                "why": f"Every house needs a {v}.",
                "annotations": red,
            }
        )
    elif wrap:
        side, a, b = wrap
        out.append(
            {
                "text": f"{_cap(nm.cell(a))} and {nm.cell(b)} are both {names[side]} and see each other, so {names[side]} "
                f"is false: no {names[side]} cell is {v}.",
                "why": f"Two cells that see each other can't both be {v}.",
                "annotations": red,
            }
        )
    else:
        out.append(
            {
                "text": f"{_subj(nm, tg)} {'sees' if len(tg) == 1 else 'see'} a blue {v} and a yellow {v}; one of them "
                f"is a {v}, so {fmt_elims(nm, elims)}.",
                "annotations": red,
            }
        )
    return out


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
    pc = list((ctx.raw_engine or {}).get("pattern_cells") or [])
    if ctx.code in ("XUR1", "XUR2") and len(pc) == 6:
        ds = list(digits_of(ctx.xm.get("x") or 0))
        trio = "/".join(map(str, ds))
        if ctx.code == "XUR1":
            t = next(iter(tcells))
            short = f"{fmt_elims(nm, ctx.elims)}: extended unique rectangle ({trio})"
            teach = (
                f"{nm.cells(pc)} lie in two rows (or columns) and three boxes; all but {nm.cell(t)} hold only "
                f"{trio}. If {nm.cell(t)} took one of them too, the six cells could swap their digits within each "
                f"column -- two solutions. So {fmt_elims(nm, ctx.elims)}."
            )
        else:
            w = next(iter({d for _, d in ctx.elims}))
            two = [c for c in pc if st.cand[c] & bit(w)]
            short = f"{fmt_elims(nm, ctx.elims)}: extended unique rectangle type 2 ({trio}, extra {w})"
            teach = (
                f"{nm.cells(pc)} lie in two rows (or columns) and three boxes and hold only {trio}, except that "
                f"{nm.cells(two)} also hold {w}. Without {w} the six cells could swap their digits -- two solutions -- "
                f"so one of {nm.cells(two)} is {w}, and every cell seeing both loses it: {fmt_elims(nm, ctx.elims)}."
            )
        teach += " Uniqueness techniques rely on the puzzle having exactly one solution."
        J = _J(ctx, digits=ds, base_cells=pc, cover_cells=sorted(tcells))
        return _result(ctx, J, short, teach, True)
    if ctx.code == "HUR" and len(pc) == 4 and x and y:
        xy = bit(x) | bit(y)
        floor = [c for c in pc if st.cand[c] == xy]
        t, b = next(iter(ctx.elims))
        a = x if b == y else y
        side = len(floor) == 2 and (
            p.coords[floor[0]][0] == p.coords[floor[1]][0] or p.coords[floor[0]][1] == p.coords[floor[1]][1]
        )
        if side and t not in floor:  # type 2: a strong link from the floor to the roof corner beside it
            rf = next(c for c in pc if c not in floor and c != t)
            f = next(c for c in floor if p.coords[c][0] == p.coords[rf][0] or p.coords[c][1] == p.coords[rf][1])
            g = next(c for c in floor if c != f)
            short = f"{fmt_elims(nm, ctx.elims)}: hidden unique rectangle type 2 ({x}/{y})"
            teach = (
                f"{nm.cells(pc)} form a rectangle over two rows, two columns and two boxes; {nm.cells(floor)} hold "
                f"just {{{x},{y}}}. {a} has only two places in the house of {nm.cell(f)} and {nm.cell(rf)}. If "
                f"{nm.cell(t)} were {b}, {nm.cell(g)} would be {a}, {nm.cell(f)} {b}, so {nm.cell(rf)} {a}: the "
                f"{x}s and {y}s could be swapped -- two solutions. So {nm.cell(t)} is not {b}."
            )
        else:  # type 1: a bivalue corner, and the far corner with strong links on both its sides
            corner = next(
                (c for c in floor if p.coords[c][0] != p.coords[t][0] and p.coords[c][1] != p.coords[t][1]), None
            )
            short = f"{fmt_elims(nm, ctx.elims)}: hidden unique rectangle ({x}/{y})"
            teach = (
                f"{nm.cells(pc)} form a rectangle over two rows, two columns and two boxes"
                + (f"; {nm.cell(corner)} holds just {{{x},{y}}}" if corner is not None else "")
                + f". In the row and the column of {nm.cell(t)}, {a} has only its two rectangle places. If "
                f"{nm.cell(t)} were {b}, both of those places would take {a}, and the corners would form an "
                f"interchangeable {x}/{y} rectangle -- two solutions. So {nm.cell(t)} is not {b}."
            )
        teach += " Uniqueness techniques rely on the puzzle having exactly one solution."
        J = _J(ctx, digits=[x, y], base_cells=pc, cover_cells=sorted(tcells))
        return _result(ctx, J, short, teach, True)
    for cs in _rects(p):
        if any(st.vals[c] for c in cs):
            continue
        if pc and sorted(cs) != sorted(pc):  # the engine's rectangle, not another one on the same digits
            continue
        union = st.cand[cs[0]] | st.cand[cs[1]] | st.cand[cs[2]] | st.cand[cs[3]]
        pairs = [(x, y)] if x and y else [(a, b) for a, b in combinations(digits_of(union), 2)]
        for a, b in pairs:
            xy = bit(a) | bit(b)
            if any(not st.cand[c] & xy for c in cs):
                continue
            floor = [c for c in cs if not st.cand[c] & ~xy]  # a corner may miss one of the pair
            roof = [c for c in cs if c not in floor]
            if typ == 1 and not (len(floor) == 3 and tcells <= set(roof)):
                continue
            if typ in (2, 3, 4) and len(floor) != 2:
                continue
            if typ == 4 and not tcells <= set(roof):
                continue
            if typ == 7 and not 1 <= len(floor) <= 2:
                continue
            if typ == 12 and not (len(floor) == 2 and tcells <= set(roof)):
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
                    f"{nm.cells(floor)} hold just {{{a},{b}}}; the other corners {nm.cells(roof)} hold "
                    f"{a}/{b} plus {z}. To avoid the deadly {a}/{b} rectangle one of those two must be {z}, so "
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
            elif typ == 7:
                z = next(iter({d for _, d in ctx.elims}))
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 5 ({a}/{b}, extra {z})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}}; the other corners {nm.cells(roof)} hold {a}/{b} plus "
                    f"{z}. Without {z} the four corners could swap their {a}s and {b}s -- two solutions -- so one "
                    f"of {nm.cells(roof)} is {z}, and every cell seeing all of them loses it: "
                    f"{fmt_elims(nm, ctx.elims)}."
                )
            elif typ == 12:
                d = next(iter({d for _, d in ctx.elims}))
                o = b if d == a else a
                short = f"{fmt_elims(nm, ctx.elims)}: unique rectangle type 6 ({a}/{b})"
                teach = (
                    f"{nm.cells(floor)} hold just {{{a},{b}}} on one diagonal of the rectangle {nm.cells(cs)}, and "
                    f"{d} has only its two rectangle places in both of its rows (or both columns) -- an X-Wing. If "
                    f"a roof corner {nm.cells(roof)} were {d}, the floor would be {o} and the other roof {d}: an "
                    f"interchangeable {a}/{b} rectangle, two solutions. So {fmt_elims(nm, ctx.elims)}."
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
    odd = [q for q in range(p.N) if not st.vals[q] and popcount(st.cand[q]) != 2]
    if not ctx.place and len(odd) == 1 and popcount(st.cand[odd[0]]) >= 4:  # BUG+1 with a 4+ candidate cell
        c = odd[0]
        pair = sorted({d for _, d in ctx.elims})
        short = f"{fmt_elims(nm, ctx.elims)}: BUG+1"
        teach = (
            f"Every unsolved cell has exactly two candidates except {nm.cell(c)} {nm.cset(st.cand[c])}. In its "
            f"houses {' and '.join(map(str, pair))} appear twice and its other digits three times. If {nm.cell(c)} "
            f"held {pair[0]} or {pair[1] if len(pair) > 1 else pair[0]}, the grid would be a 'bivalue universal "
            f"grave' -- every digit twice per house -- which never has exactly one solution. So "
            f"{fmt_elims(nm, ctx.elims)}."
        )
        J = _J(ctx, digits=pair, base_cells=[c])
        return _result(ctx, J, short, teach, True)
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


def _h_ape(ctx):
    """Aligned Pair Exclusion: every value pair of the two base cells, each ruled out by a witness that would be left
    short of digits (a cell with no other candidate, or an almost locked set holding both digits)"""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    X, Y = ctx.xm.get("cell_a"), ctx.xm.get("cell_b")
    if X is None or Y is None:
        return _generic(ctx)
    aligned = Y in p.peers[X]
    common = [q for q in p.peers[X] & p.peers[Y] if not st.vals[q]]
    sets = []  # (cells, digit mask) of the almost locked sets among the common cells, one house each
    for gi in {g for q in common for g in p.groups_of[q] if p.groups[g].complete}:
        cs = [q for q in common if q in p.groups[gi].cells]
        for k in range(1, len(cs) + 1):
            for sub in combinations(cs, k):
                m = 0
                for q in sub:
                    m |= st.cand[q]
                if popcount(m) == k + 1 and (sub, m) not in sets:
                    sets.append((sub, m))

    def killer(x, y):
        for q in common:
            if st.cand[q] & ~(bit(x) | bit(y)) == 0:
                return f"{nm.cell(q)} would have no digit left"
        if x != y:
            for sub, m in sorted(sets, key=lambda s: len(s[0])):
                if m & (bit(x) | bit(y)) == bit(x) | bit(y):
                    return f"{nm.cells(list(sub))} would have {len(sub)} cells for {len(sub) - 1} digits"
        return None

    lines = []
    for c, d in ctx.elims:
        other = Y if c == X else X
        by = defaultdict(list)  # witness text -> partner values it rules out
        for e in digits_of(st.cand[other]):
            if e == d and aligned:
                continue
            k = killer(d, e) if c == X else killer(e, d)
            if k is None:
                return _generic(ctx)
            by[k].append(str(e))
        why = [f"with {nm.cell(other)} = {_join(vs, 'or')}, {k}" for k, vs in by.items()]
        lines.append(f"If {nm.cell(c)} were {d}: " + "; ".join(why) + ".")
    short = f"{fmt_elims(nm, ctx.elims)}: aligned pair exclusion"
    teach = (
        f"Test every pair of values for {nm.cell(X)} and {nm.cell(Y)}"
        + (" (they see each other, so the values differ)" if aligned else " (they do not see each other)")
        + " against the cells both of them see. "
        + " ".join(lines)
        + f" No value of the partner survives, so {fmt_elims(nm, ctx.elims)}."
    )
    J = _J(ctx, digits=sorted({d for _, d in ctx.elims}), base_cells=[X, Y], cover_cells=common)
    return _result(ctx, J, short, teach, True)


def _h_nwing(ctx):
    """WXYZ / VWXYZ-Wing: n cells holding n digits; one unrestricted digit Z is in the wing (type 1), or none and every
    digit is there once (type 2)"""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    cells = list((ctx.raw_engine or {}).get("pattern_cells") or [])
    if not cells:
        return _generic(ctx)
    U = 0
    for c in cells:
        U |= st.cand[c]
    ds = list(digits_of(U))
    n = len(cells)
    name = {4: "WXYZ-Wing", 5: "VWXYZ-Wing"}.get(n, f"{n}-cell wing")
    restricted = [
        d for d in ds if all(b in p.peers[a] for a, b in combinations([c for c in cells if st.cand[c] & bit(d)], 2))
    ]
    free = [d for d in ds if d not in restricted]
    gone = sorted({d for _, d in ctx.elims})
    lead = f"{nm.cells(cells)} hold only {_join(ds)}: {n} cells, {n} digits."
    if not free:
        short = f"{fmt_elims(nm, ctx.elims)}: {name} type 2"
        teach = (
            f"{lead} Every digit's cells in the wing see each other, so each digit is there at most once; with {n} "
            f"cells and {n} digits each is there exactly once. A cell that sees every place of a digit in the wing "
            f"loses it: {fmt_elims(nm, ctx.elims)}."
        )
    else:
        z = free[0]
        zc = [c for c in cells if st.cand[c] & bit(z)]
        short = f"{fmt_elims(nm, ctx.elims)}: {name} (Z = {z})"
        teach = (
            f"{lead} Every digit but {z} has its cells in the wing seeing each other, so it is there at most once; "
            f"those {n - 1} digits fill at most {n - 1} cells, so {z} is in the wing, in {nm.cells(zc, 'or')}. "
            f"{_subj(nm, sorted({c for c, _ in ctx.elims}))} "
            f"{'sees' if len({c for c, _ in ctx.elims}) == 1 else 'see'} all of them: no {z} there."
        )
    if free and gone != [free[0]]:
        return _generic(ctx)
    J = _J(ctx, digits=gone, base_cells=cells, cover_cells=sorted({c for c, _ in ctx.elims}))
    r = _result(ctx, J, short, teach, True)
    r["substeps"] = _nwing_substeps(nm, st, cells, ds, restricted, free[0] if free else None, ctx.elims)
    return r


def _nwing_substeps(nm, st, cells, ds, restricted, z, elims):
    """WXYZ-type wing as sub-steps: the cells (green) and their digits, the digits held at most once, then Z's places
    (orange; type 1) or every digit exactly once (type 2), the removals (red)"""
    ids = iter(range(1, 10**6))
    n = len(cells)
    out = [
        {
            "text": f"{_cap(nm.cells(cells))} hold only {_join(ds)}: {n} cells, {n} digits.",
            "annotations": [{"id": next(ids), "cell": nm.cell(c), "colour": "green"} for c in cells],
        },
        {
            "text": f"{_cap(_join(restricted))} {'is' if len(restricted) == 1 else 'are'} there at most once: "
            + ("its places see each other." if len(restricted) == 1 else "each digit's places see each other."),
            "why": "Cells that see each other can't share a digit.",
        },
    ]
    tg = sorted({c for c, _ in elims})
    red = [{"id": next(ids), "candidate": f"{nm.cell(c)}#{d}", "colour": "red"} for c, d in sorted(elims)]
    if z is not None:
        zc = [c for c in cells if st.cand[c] & bit(z)]
        out.append(
            {
                "text": f"Those {n - 1} digits fill at most {n - 1} cells, so {z} is in the wing: in {nm.cells(zc, 'or')}.",
                "annotations": [{"id": next(ids), "candidate": f"{nm.cell(c)}#{z}", "colour": "orange"} for c in zc],
            }
        )
        out.append(
            {
                "text": f"{_subj(nm, tg)} {'sees' if len(tg) == 1 else 'see'} all of them, so {fmt_elims(nm, elims)}.",
                "annotations": red,
            }
        )
    else:
        out.append({"text": f"With {n} cells and {n} digits, each digit is there exactly once."})
        out.append(
            {
                "text": f"A cell that sees every place of a digit in the wing loses it: {fmt_elims(nm, elims)}.",
                "annotations": red,
            }
        )
    return out


def _h_pom(ctx):
    """Pattern Overlay: a digit's templates (one cell per row, column and box); rule 1 drops candidates no template
    uses, rule 2 (code 'pattern overlay (rule 2)') first drops templates that meet every template of another digit"""
    nm = ctx.nm
    d = ctx.xm.get("digit") or next(iter({v for _, v in ctx.elims}))
    k = ctx.xm.get("templates")
    tg = sorted({c for c, _ in ctx.elims})
    if ctx.code == "pattern overlay (rule 2)":
        w = ctx.xm.get("blocker")
        short = f"{fmt_elims(nm, ctx.elims)}: pattern overlay (rule 2) on {d}"
        teach = (
            f"List every way to place the {d}s (one per row, column and box) that the candidates allow. The digits' "
            f"placements share no cell, so a placement of {d} that collides with every possible placement of another "
            f"digit cannot be the solution's"
            + (f" (here {w} blocks some)" if w else "")
            + f". In the {k} placements left, {nm.cells(tg)} never hold {d}: {fmt_elims(nm, ctx.elims)}."
        )
    else:
        short = f"{fmt_elims(nm, ctx.elims)}: pattern overlay on {d}"
        teach = (
            f"List every way to place the {d}s (one per row, column and box) that the candidates allow"
            + (f": {k} placements" if k else "")
            + f". None of them uses {nm.cells(tg)}, so {fmt_elims(nm, ctx.elims)}."
        )
    J = _J(ctx, digits=[d], cover_cells=tg)
    return _result(ctx, J, short, teach, True)
