"""Chains, almost locked sets, death blossom, chains in the head. (split from explain.py)"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .. import registry as R
from .. import solver as S
from ..model import bit, digits_of, popcount
from .base import _J, CONCEPTS, _cap, _elim_digits, _elim_list, _generic, _result, _subj, fmt_elims, rel_label
from .catalog import CATALOG, SHAPE_NOTES, chain_shape
from .grid import _rule_dom, enum_rule, mental_view, rules


# ------------------------------------------------------------- chains -------
def _link_graph(p, st, allow_bivalue=True, allow_bilocal=True, digit=None, extra=True):
    """Strong links: bivalue cell, bilocal digit in a house, digit a rule must contain with two
    cells left, pair-relation forcing. -> (nodes, {node: [(node, source, unit)]})."""
    strong = defaultdict(list)
    nodes = [(c, d) for c in range(p.N) if not st.vals[c] for d in digits_of(st.cand[c]) if digit is None or d == digit]

    def add(x, y, src, unit):
        if x == y or any(n == y for n, _, _ in strong[x]):
            return
        strong[x].append((y, src, unit))
        strong[y].append((x, src, unit))

    if allow_bivalue and digit is None:
        for c in range(p.N):
            if not st.vals[c] and popcount(st.cand[c]) == 2:
                a, b = digits_of(st.cand[c])
                add((c, a), (c, b), "bivalue", None)
    if allow_bilocal:
        for hi in p.houses:
            for d in digits_of(p.full & ~st.placed_g(hi)):
                if digit is not None and d != digit:
                    continue
                cs = [c for c in p.groups[hi].cells if not st.vals[c] and st.cand[c] & bit(d)]
                if len(cs) == 2:
                    add((cs[0], d), (cs[1], d), "bilocal", hi)
    if extra and allow_bilocal:
        for key, rule in rules(p).items():
            if all(st.vals[c] for c in rule.cells):
                continue
            res = enum_rule(p, rule, _rule_dom(st, rule), node_limit=20000)
            if not res["complete"] or res["count"] is None or res["count"] > len(res["sols"]) or not res["sols"]:
                continue
            must = set(res["sols"][0])
            for sol in res["sols"][1:]:
                must &= set(sol)
            for d in must:
                if digit is not None and d != digit:
                    continue
                if any(st.vals[c] == d for c in rule.cells):
                    continue
                cs = [c for c in rule.cells if not st.vals[c] and st.cand[c] & bit(d)]
                if len(cs) == 2:
                    add((cs[0], d), (cs[1], d), "constraint", key)
    if extra and allow_bivalue and digit is None:
        for a in range(p.N):
            if st.vals[a]:
                continue
            for b in p.nonconsec_list[a]:
                if st.vals[b] or b not in p.rel_ex[a]:
                    continue
                for v in digits_of(st.cand[a]):
                    allowed = 0
                    for u in digits_of(st.cand[a] & ~bit(v)):
                        allowed |= st.cand[b] & ~p.rel_ex[a][b][u]
                    if popcount(allowed) == 1 and popcount(st.cand[a]) > 1:
                        add((a, v), (b, next(digits_of(allowed))), "relation", None)
    return nodes, strong


def _weak(p, st, a, b, same_digit_only=False):
    (c1, d1), (c2, d2) = a, b
    if a == b:
        return False
    if c1 == c2:
        return not same_digit_only
    if d1 == d2 and c2 in p.peers[c1]:
        return True
    if not same_digit_only and c2 in p.rel_ex[c1] and p.rel_ex[c1][c2][d1] & bit(d2):
        return True
    return False


def _weak_succ(p, st, n, digit_only=False, xy=False):
    c, d = n
    out = []
    if not digit_only and not xy:
        for e in digits_of(st.cand[c]):
            if e != d:
                out.append((c, e))
    if xy:
        pass
    for q in p.peer_list[c]:
        if not st.vals[q] and st.cand[q] & bit(d):
            out.append((q, d))
    if not digit_only:
        for q in p.nonconsec_list[c]:
            if st.vals[q]:
                continue
            for e in digits_of(st.cand[q] & p.rel_ex[c][q][d]):
                if (q, e) not in out:
                    out.append((q, e))
    return out


def _find_chain(p, st, target, kind, max_len=16, place=False, targets=None):
    """Shortest alternating chain (first and last links strong). Elimination: both ends weakly
    linked to every target. Placement (discontinuous nice loop): starts and ends at `target`.
    -> [(node, link source into node, unit)] or None."""
    from collections import deque

    targets = targets or [target]
    digit_only = kind == "x"
    xy = kind == "xy"
    graph = getattr(st, "_xgraph", {}).get(kind)
    if graph is None:
        graph = _link_graph(
            p,
            st,
            allow_bivalue=not digit_only,
            allow_bilocal=not xy,
            digit=target[1] if digit_only else None,
            extra=not xy,
        )
        if not digit_only:
            st.__dict__.setdefault("_xgraph", {})[kind] = graph
    nodes, strong = graph

    def weak_all(n):
        return all(t != n and _weak(p, st, n, t, same_digit_only=digit_only) for t in targets)

    starts = [target] if place else [n for n in nodes if weak_all(n)]
    best = None
    for s0 in starts:
        prev = {(s0, False): None}
        dq = deque([(s0, False, 0)])
        found = None
        while dq and found is None:
            n, was_strong, ln = dq.popleft()
            if ln >= max_len:
                continue
            if not was_strong:
                for m, src, unit in strong.get(n, ()):
                    if (m, True) in prev:
                        continue
                    prev[(m, True)] = (n, False, src, unit)
                    if place:
                        end_ok = m == target and ln + 1 >= 3
                    else:
                        end_ok = m != s0 and weak_all(m) and (not xy or m[1] == s0[1])
                    if end_ok:
                        found = (m, True)
                        break
                    dq.append((m, True, ln + 1))
            else:
                if xy:
                    succ = [
                        (q, n[1])
                        for q in p.peer_list[n[0]]
                        if not st.vals[q] and st.cand[q] & bit(n[1]) and popcount(st.cand[q]) == 2
                    ]
                else:
                    succ = _weak_succ(p, st, n, digit_only)
                for m in succ:
                    if (m, False) in prev or (m in targets and not place):
                        continue
                    prev[(m, False)] = (n, True, "weak", None)
                    dq.append((m, False, ln + 1))
        if found is None:
            continue
        path = []
        cur = found
        while prev[cur] is not None:
            pn, pstrong, psrc, punit = prev[cur]
            path.append((cur[0], psrc, punit))
            cur = (pn, pstrong)
        path.append((s0, None, None))
        path.reverse()
        if best is None or len(path) < len(best):
            best = path
        if len(best) <= 4:
            break
    return best


def _chain_text(nm, p, path, als_cells=None):
    """path: [(node, src_into, unit)] alternating, first link strong. ALS nodes: ('als', id, digit)."""
    out = []
    for i in range(1, len(path)):
        n0, n1 = path[i - 1][0], path[i][0]
        src, unit = path[i][1], path[i][2]
        strong = src != "weak" if src is not None else i % 2 == 1
        if src == "equal" and n0[0] != "als" and n1[0] != "als":
            out.append(f"so {nm.cell(n1[0])} is {n1[1]} as well ({rel_label(p, n0[0], n1[0]) or 'equal cells'})")
            continue
        if n0[0] == "als" or n1[0] == "als":
            cells = (als_cells or {}).get((n1 if n1[0] == "als" else n0)[1])
            nm_set = f"the almost locked set {nm.cells(cells)}" if cells else "an almost locked set"
            d1 = n1[-1]
            if n1[0] == "als" and not strong:
                out.append(f"which takes {d1} away from {nm_set}")
            elif n1[0] == "als":
                out.append(f"so {nm_set}, now one digit short, is locked and must contain a {d1}")
            elif strong:
                out.append(f"so {nm.cell(n1[0])} is {d1}")
            else:
                out.append(f"and every {n0[-1]} of that set sees {nm.cell(n1[0])}, so {nm.cell(n1[0])} isn't {d1}")
            continue
        (c0, d0), (c1, d1) = n0, n1
        if strong:
            if src == "bivalue":
                out.append(f"so {nm.cell(c1)} is {d1} (it only holds {d0} or {d1})")
            elif src == "bilocal":
                out.append(f"so {nm.cell(c1)} is {d1} (the only other {d1} in {nm.unit(unit)})")
            elif src == "constraint" and unit is not None:
                out.append(
                    f"so {nm.cell(c1)} is {d1} ({rules(p)[unit].label} must contain a {d1} and has only "
                    f"those two places for it)"
                )
            elif src == "relation":
                out.append(f"so {nm.cell(c1)} is {d1} (the {rel_label(p, c0, c1)} leaves it no other option)")
            elif src == "constraint" and unit is None:
                out.append(
                    f"so {nm.cell(c1)} is {d1} (a cage or line must contain a {d1} and has only those two "
                    f"places for it)"
                )
            else:
                out.append(f"so {nm.cell(c1)} is {d1}")
        else:
            if c0 == c1:
                out.append(f"which means {nm.cell(c1)} isn't {d1}")
            elif d0 == d1:
                out.append(f"which stops {nm.cell(c1)} being {d1}")
            else:
                out.append(f"which stops {nm.cell(c1)} being {d1} ({rel_label(p, c0, c1)})")
    return out


def _clash(nm, p, t, end):
    (c, d), (ec, ed) = t, end
    if c == ec:
        return f"it is itself the {ed} end" if d != ed else "it is an end"
    if d == ed:
        return f"it sees {nm.cell(ec)}"
    return f"{rel_label(p, ec, c)}-linked to {nm.cell(ec)}"


_PATTERN_NAMES = {p.engine_code: p.explain_name for p in R.patterns() if p.explain_name}  # data/patterns.csv


def _chain_links(path):
    return [
        {
            "a": path[i - 1][0],
            "b": path[i][0],
            "strong": path[i][1] != "weak",
            "source": path[i][1] or "strong",
            "unit": path[i][2],
        }
        for i in range(1, len(path))
    ]


def _chains_for(p, st, elims, kind):
    """Cover the eliminations with as few chains as possible. -> [(path, explained elims)]."""
    left = list(elims)
    out = []
    while left:
        path = None
        for kd in dict.fromkeys((kind, "aic")):
            path = _find_chain(p, st, left[0], kd, targets=left)
            if path:
                break
        if not path:
            for kd in dict.fromkeys((kind, "aic")):
                path = _find_chain(p, st, left[0], kd)
                if path:
                    break
        if not path:
            return out, left
        a, z = path[0][0], path[-1][0]
        done = [t for t in left if t not in (a, z) and _weak(p, st, a, t) and _weak(p, st, z, t)]
        if not done:
            return out, left
        out.append((path, done))
        left = [t for t in left if t not in done]
    return out, []


def _chain_conclusion(nm, p, path, done):
    (sc, sd), (ec, ed) = path[0][0], path[-1][0]
    tg = sorted({c for c, _ in done})
    ds = sorted({d for _, d in done})
    if sd == ed and ds == [sd]:
        return (
            f"{_subj(nm, tg)} {'sees' if len(tg) == 1 else 'see'} both ends, so "
            f"{'it' if len(tg) == 1 else 'they'} can't be {sd}."
        )
    return (
        "Each removed candidate clashes with both ends: "
        + "; ".join(
            f"{nm.cell(c)} can't be {d} ({_clash(nm, p, (c, d), (sc, sd))} and {_clash(nm, p, (c, d), (ec, ed))})"
            for c, d in done
        )
        + "."
    )


def _h_chain(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    kind = {S.X_CHAIN: "x", S.XY_CHAIN: "xy", S.EMPTY_RECT: "x", S.REMOTE_PAIRS: "xy"}.get(ctx.tech, "aic")
    if ctx.code in ("SKY", "2SK", "TUR", "XCH"):
        kind = "x"
    if ctx.code == "XYC":
        kind = "xy"
    pname = _PATTERN_NAMES.get(ctx.code or "", CONCEPTS[ctx.tech][0])
    alsc = {a.get("id"): a.get("cells") for a in ctx.engine.get("als") or ()}
    tip = (
        "Single-digit chains like this are found by following one digit's conjugate pairs."
        if kind == "x"
        else "Chains through two-candidate cells are easiest to find by following the bivalue cells."
        if kind == "xy"
        else "Build such chains from links you trust: two-candidate cells, digits with two spots in a house, "
        "and digits a cage or line must contain."
    )
    if ctx.place:
        path = _engine_path(ctx)
        for kd in [] if path else dict.fromkeys((kind, "aic")):
            path = _find_chain(p, st, ctx.place, kd, place=True)
            if path:
                break
        if not path:
            return _generic(ctx)
        c, v = ctx.place
        links = _chain_links(path)
        pname = "Discontinuous nice loop"
        tip = SHAPE_NOTES["nice_loop"] + " " + tip
        short = f"{nm.cell(c)} = {v}: {pname} -- assuming it isn't {v} forces it to be {v}"
        teach = (
            f"Suppose {nm.cell(c)} is NOT {v}: {', '.join(_chain_text(nm, p, path, alsc))}. The chain comes back and "
            f"demands that {nm.cell(c)} is {v} after all -- a contradiction, so {nm.cell(c)} is {v}. {tip}"
        )
        J = _J(
            ctx,
            digits=sorted({n[0][-1] for n in path}),
            links=links,
            base_cells=[n[0][0] for n in path if isinstance(n[0][0], int)],
            pattern="Discontinuous nice loop",
            pattern_type="strong-strong at the start: placement",
        )
        r = _result(
            ctx,
            J,
            short,
            teach,
            path[0][0] == ctx.place and path[-1][0] == ctx.place,
            chain=_chain_vis(nm, links),
            lines=_chain_lines(p, path),
        )
        r["pattern_key"] = "nice_loop"
        return r
    epath = None
    for trim in (True, False):
        cand_path = _engine_path(ctx, trim=trim)
        if cand_path and all(_ends_cover(p, st, cand_path, t) for t in ctx.elims):
            epath = cand_path
            break
    if epath:
        chains, left = [(epath, list(ctx.elims))], []
    else:
        chains, left = _chains_for(p, st, ctx.elims, kind)
    if not chains or not chains[0][1]:
        return _generic(ctx)
    links, cells, blocks, lines = [], [], [], []
    for k, (path, done) in enumerate(chains):
        (sc, sd), (ec, ed) = path[0][0], path[-1][0]
        both = f"{nm.cell(sc)} is {sd} or {nm.cell(ec)} is {ed}"
        lead = "Start from the idea that" if k == 0 else "A second chain does the rest: suppose"
        blocks.append(
            f"{lead} {nm.cell(sc)} is NOT {sd}: {', '.join(_chain_text(nm, p, path, alsc))}. So at least one "
            f"end is true: {both}. {_chain_conclusion(nm, p, path, done)}"
        )
        links += _chain_links(path)
        cells += [n[0][0] for n in path]
        lines += _chain_lines(p, path)
    (sc, sd), (ec, ed) = chains[0][0][0][0], chains[0][0][-1][0]
    key = chain_shape(p, st, chains[0][0])
    if key in ("aic", "x_chain", "xy_chain") and ctx.code in _CODE_KEY:
        key = _CODE_KEY[ctx.code] if _CODE_KEY[ctx.code] not in ("aic",) else key
    ptype = None
    if key in ("aic", "als_chain"):
        same_cell = any(t[0] in (sc, ec) for t in ctx.elims)
        ptype = (
            "type 2: the ends are different digits and the target shares a cell with one end"
            if same_cell or sd != ed
            else "type 1: both ends are the same digit"
        )
    pname = CATALOG[key][0] if key in CATALOG else pname
    note = SHAPE_NOTES.get(key, "")
    short = f"{fmt_elims(nm, ctx.elims)}: {pname} -- either {nm.cell(sc)} is {sd} or {nm.cell(ec)} is {ed}"
    teach = (
        " ".join(blocks)
        + (f" (Not shown: {fmt_elims(nm, left)}.)" if left else "")
        + " "
        + (note + " " if note else "")
        + tip
    )
    J = _J(
        ctx,
        digits=sorted({d for lk in links for d in (lk["a"][-1], lk["b"][-1])}),
        links=links,
        base_cells=[c for c in cells if isinstance(c, int)] + [c for a in alsc.values() for c in (a or ())],
        cover_cells=sorted({c for c, _ in ctx.elims}),
        als=[{"cells": list(v), "id": k} for k, v in alsc.items() if v],
    )
    J["pattern"], J["pattern_type"] = pname, ptype
    ok = not left and all(_path_valid(p, st, pth) for pth, _ in chains)
    r = _result(ctx, J, short, teach, ok, chain=_chain_vis(nm, links), lines=lines)
    r["pattern_key"] = key
    return r


_CODE_KEY = {p.engine_code: p.catalog_key for p in R.patterns() if p.catalog_key}  # engine code -> CATALOG key


_SRC = (
    ("bivalue", "bivalue"),
    ("only two places", "bilocal"),
    ("must contain", "constraint"),
    ("pair relation", "relation"),
    ("almost locked", "als"),
    ("equivalence", "equal"),
)


def _engine_path(ctx, trim=True):
    """Chain nodes from the engine -> [(node, link source, unit)]; ALS nodes are ('als', id, digit)."""
    nodes = ctx.engine.get("chain") or []
    if len(nodes) < 2:
        return None
    path = []
    for i, n in enumerate(nodes):
        node = (n["cell"], n["digit"]) if n.get("cell") is not None else ("als", n.get("als"), n["digit"])
        if i == 0:
            path.append((node, None, None))
            continue
        li = n.get("link_in", "")
        src = "weak" if li.startswith("weak") else next((v for k, v in _SRC if k in li), "strong")
        unit = ctx.nm.gidx.get(n.get("via")) if src == "bilocal" else None
        path.append((node, src, unit))
    # an AIC starts and ends with strong links: drop dangling weak ends (the target side of the record)
    while trim and len(path) > 2 and path[1][1] == "weak":
        path = [(path[1][0], None, None)] + path[2:]
    while trim and len(path) > 2 and path[-1][1] == "weak":
        path = path[:-1]
    if len(path) < 2 or path[0][0][0] == "als" or path[-1][0][0] == "als":
        return None
    ctx.used_engine = True
    return path


def _path_valid(p, st, path):
    """Every cell-to-cell link of a chain holds in the grid (ALS / rule links are taken on trust)."""
    for i in range(1, len(path)):
        a, b = path[i - 1][0], path[i][0]
        src = path[i][1]
        if a[0] == "als" or b[0] == "als" or src == "equal":
            continue
        if src == "weak":
            if not _weak(p, st, a, b):
                return False
        elif src == "bivalue":
            if a[0] != b[0] or st.cand[a[0]] != bit(a[1]) | bit(b[1]):
                return False
        elif src == "bilocal":
            if a[1] != b[1] or not any(
                a[0] in p.groups[h].cells
                and b[0] in p.groups[h].cells
                and [c for c in p.groups[h].cells if not st.vals[c] and st.cand[c] & bit(a[1])] == sorted((a[0], b[0]))
                for h in p.houses
            ):
                return False
    return True


def _ends_cover(p, st, path, t):
    a, z = path[0][0], path[-1][0]
    if a[0] == "als" or z[0] == "als":
        return True
    return t not in (a, z) and _weak(p, st, a, t) and _weak(p, st, z, t)


def _als_cells(ctx, als_id):
    for a in ctx.engine.get("als") or ():
        if a.get("id") == als_id:
            return a.get("cells")
    return None


def _chain_vis(nm, links):
    def nd(n):
        return nm.cell(n[0]) if isinstance(n[0], int) else f"ALS#{n[1]}"

    return [[nd(l["a"]), l["a"][-1], nd(l["b"]), l["b"][-1], "strong" if l["strong"] else "weak"] for l in links]


def _chain_lines(p, path):
    out = []
    for node, src, unit in path:
        if src == "constraint" and unit is not None:
            r = rules(p)[unit]
            out.append((r.line_kind or r.kind, r.cells))
    return out


# ----------------------------------------------------------------- ALS ------
def _als_list(p, st, max_cells=4):
    out = []
    seen = set()
    for gi in range(len(p.groups)):
        g = p.groups[gi]
        if not (g.complete or g.kind == "cage"):
            continue
        emp = [c for c in g.cells if not st.vals[c]]
        for k in range(1, min(max_cells, len(emp)) + 1):
            for combo in combinations(emp, k):
                u = 0
                for c in combo:
                    u |= st.cand[c]
                if popcount(u) == k + 1 and combo not in seen:
                    seen.add(combo)
                    out.append((combo, u, gi))
    return out


def _engine_als(ctx):
    """Engine ALS records -> [(cells tuple, digit mask, house)]."""
    p, st = ctx.p, ctx.st
    out = []
    for a in ctx.engine.get("als") or ():
        cs = tuple(sorted(a.get("cells") or ()))
        if not cs:
            return None
        m = 0
        for c in cs:
            m |= st.cand[c]
        common = set.intersection(*(set(p.groups_of[c]) for c in cs))
        gi = min(common, key=lambda g: (not p.groups[g].complete, g)) if common else -1
        out.append((cs, m, gi))
    return out


def _h_als_xz(ctx):
    _nm, p, st = ctx.nm, ctx.p, ctx.st
    tset = set(ctx.elims)
    zs = _elim_digits(ctx)
    ea = _engine_als(ctx)
    rcc = ctx.engine.get("rcc") or []
    if ea and len(ea) == 2:
        A, Bs = ea
        if len(rcc) >= 2 or ctx.code == "AXZ2":
            r = _als_xz_double(ctx, [A, Bs], pair=(A, Bs))
            if r["verified"]:
                ctx.used_engine = True
                return r
        elif rcc:
            x = rcc[0]
            el = set()
            for z in zs:
                za = [c for c in A[0] + Bs[0] if st.cand[c] & bit(z)]
                el |= {
                    (q, z)
                    for q in range(p.N)
                    if not st.vals[q]
                    and st.cand[q] & bit(z)
                    and q not in A[0] + Bs[0]
                    and all(q in p.peers[c] for c in za)
                }
            if tset <= el and _rcc(p, st, A, Bs, x) and x not in zs:
                ctx.used_engine = True
                return _alsxz_render(ctx, A, Bs, x, zs)
    als = _als_list(p, st)
    for z in zs:
        zb = bit(z)
        t0 = next(t for t in ctx.elims if t[1] == z)
        cand_als = [
            a
            for a in als
            if a[1] & zb and all(t0[0] in p.peers[c] for c in a[0] if st.cand[c] & zb) and t0[0] not in a[0]
        ]
        for A, Bs in combinations(cand_als, 2):
            ca, cb = A[0], Bs[0]
            if set(ca) & set(cb):
                continue
            for x in digits_of(A[1] & Bs[1]):
                if x == z:
                    continue
                xa = [c for c in ca if st.cand[c] & bit(x)]
                xb = [c for c in cb if st.cand[c] & bit(x)]
                if not all(q in p.peers[c] for c in xa for q in xb):
                    continue
                za = [c for c in ca if st.cand[c] & zb] + [c for c in cb if st.cand[c] & zb]
                el = {
                    (q, z)
                    for q in range(p.N)
                    if not st.vals[q] and st.cand[q] & zb and q not in ca + cb and all(q in p.peers[c] for c in za)
                }
                if {t for t in tset if t[1] == z} <= el:
                    return _alsxz_render(ctx, A, Bs, x, z)
    return _als_xz_double(ctx, als)


def _alsxz_render(ctx, A, Bs, x, z):
    nm = ctx.nm
    ca, cb = A[0], Bs[0]
    zs = list(z) if isinstance(z, (list, tuple)) else [z]

    def desc(a):
        return f"{nm.cells(a[0])} (digits {nm.digits(digits_of(a[1]), 'and')} in {nm.unit(a[2])})"

    tg = sorted({c for c, _ in ctx.elims})
    zt = nm.digits(zs, "and")
    short = f"{fmt_elims(nm, ctx.elims)}: ALS-XZ, X={x}, Z={zt}"
    teach = (
        f"Two almost-locked sets: A = {desc(A)} and B = {desc(Bs)} -- each has one more digit than cells. "
        f"Their {x}s all see each other, so at most one set holds {x}; the set without {x} is locked onto its "
        f"other digits, which include {zt}. So "
        + ("a " + str(zs[0]) + " is" if len(zs) == 1 else "each of " + zt + " is")
        + f" in A or B, and {nm.cells(tg)}, seeing every copy of {'it' if len(zs) == 1 else 'them'} in both "
        f"sets, lose{'s' if len(tg) == 1 else ''} {fmt_elims(nm, ctx.elims).split(' ≠ ')[-1] if len(tg) == 1 else zt}."
    )
    J = _J(
        ctx,
        digits=[x] + zs,
        als=[
            {"cells": list(ca), "digits": list(digits_of(A[1]))},
            {"cells": list(cb), "digits": list(digits_of(Bs[1]))},
        ],
        rcc=[x],
        z=zs[0],
        base_cells=list(ca) + list(cb),
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, all(d in zs for _, d in ctx.elims))


def _als_xz_double(ctx, als, pair=None):
    """Doubly linked ALS-XZ: two restricted common digits lock both sets completely."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    tset = set(ctx.elims)
    c0, d0 = ctx.elims[0]

    def sees_all(q, cells, d):
        cs = [c for c in cells if st.cand[c] & bit(d)]
        return cs and q not in cells and all(q in p.peers[c] for c in cs)

    first = [pair[0]] if pair else [a for a in als if a[1] & bit(d0) and sees_all(c0, a[0], d0)]
    for A in first:
        for B in [pair[1]] if pair else als:
            if B is A or set(A[0]) & set(B[0]):
                continue
            rcc = [x for x in digits_of(A[1] & B[1]) if _rcc(p, st, A, B, x)]
            if len(rcc) < 2:
                continue
            x1, x2 = rcc[:2]
            el = set()
            for q in range(p.N):
                if st.vals[q] or q in A[0] or q in B[0]:
                    continue
                for x in (x1, x2):
                    if st.cand[q] & bit(x) and sees_all(q, A[0] + B[0], x):
                        el.add((q, x))
                for S_ in (A, B):
                    for d in digits_of(S_[1] & ~bit(x1) & ~bit(x2)):
                        if st.cand[q] & bit(d) and sees_all(q, S_[0], d):
                            el.add((q, d))
            if tset <= el:
                short = f"{fmt_elims(nm, ctx.elims)}: doubly linked ALS-XZ ({x1} and {x2})"
                teach = (
                    f"Two almost-locked sets, A = {_als_desc(nm, A)} and B = {_als_desc(nm, B)}, share two "
                    f"restricted digits: their {x1}s all see each other and so do their {x2}s. Each digit can "
                    f"be in at most one set, yet both sets need one of them to avoid running out of digits -- "
                    f"so one set takes {x1}, the other {x2}, and both become fully locked. Every remaining digit "
                    f"is pinned inside its set, which clears {_elim_list(nm, ctx.elims)} from cells that see "
                    f"all of that digit's spots."
                )
                J = _J(
                    ctx,
                    digits=[x1, x2],
                    rcc=[x1, x2],
                    als=[
                        {"cells": list(A[0]), "digits": list(digits_of(A[1]))},
                        {"cells": list(B[0]), "digits": list(digits_of(B[1]))},
                    ],
                    base_cells=list(A[0]) + list(B[0]),
                    cover_cells=sorted({c for c, _ in ctx.elims}),
                )
                return _result(ctx, J, short, teach, True)
    return _generic(ctx)


def _rcc(p, st, A, B, x):
    xa = [c for c in A[0] if st.cand[c] & bit(x)]
    xb = [c for c in B[0] if st.cand[c] & bit(x)]
    return xa and xb and all(q in p.peers[c] for c in xa for q in xb)


def _als_desc(nm, a):
    return f"{nm.cells(a[0])} (digits {nm.digits(digits_of(a[1]), 'and')})"


def _alsxy_render(ctx, A, B, C, x, y, z):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    zl = list(z) if isinstance(z, (list, tuple)) else [z]
    ok = True
    for zz in zl:
        zc = [c for c in A[0] + B[0] if st.cand[c] & bit(zz)]
        ok &= all(q in p.peers[c] for q, d in ctx.elims if d == zz for c in zc)
    if len(zl) > 1:
        z = nm.digits(zl, "and")
    tz = {t for t in ctx.elims if t[1] in zl}
    tg = sorted({c for c, _ in tz})
    short = f"{fmt_elims(nm, ctx.elims)}: ALS-XY-Wing (X={x}, Y={y}, Z={z})"
    teach = (
        f"Three almost-locked sets (one more digit than cells): A = {_als_desc(nm, A)}, B = {_als_desc(nm, B)} "
        f"and the hinge C = {_als_desc(nm, C)}. A and C can't both hold {x} (their {x}s see each other); B and "
        f"C can't both hold {y}. If neither A nor B contained {z}, both would lock up, putting {x} in A and {y} "
        f"in B -- and C would lose two digits it can't spare. So {z} is in A or B, and {nm.cells(tg)}, seeing "
        f"all those {z}s, can't be {z}."
    )
    J = _J(
        ctx,
        digits=[x, y, z],
        z=z,
        rcc=[x, y],
        als=[{"cells": list(a[0]), "digits": list(digits_of(a[1]))} for a in (A, B, C)],
        base_cells=list(A[0] + B[0] + C[0]),
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, ok and tz == set(ctx.elims))


def _h_als_xywing(ctx):
    nm, p, st = ctx.nm, ctx.p, ctx.st
    zs = _elim_digits(ctx)
    ea = _engine_als(ctx)
    if ea and len(ea) == 3:
        zm = sum(bit(z) for z in zs)
        for C in ea:
            A, B = [a for a in ea if a is not C]
            for x in digits_of(A[1] & C[1] & ~zm):
                for y in digits_of(B[1] & C[1] & ~zm & ~bit(x)):
                    if _rcc(p, st, A, C, x) and _rcc(p, st, B, C, y):
                        ctx.used_engine = True
                        return _alsxy_render(ctx, A, B, C, x, y, zs if len(zs) > 1 else zs[0])
    als = _als_list(p, st)
    for z in zs:
        zb = bit(z)
        tz = {t for t in ctx.elims if t[1] == z}
        t0 = next(iter(tz))
        cand = [
            a
            for a in als
            if a[1] & zb and t0[0] not in a[0] and all(t0[0] in p.peers[c] for c in a[0] if st.cand[c] & zb)
        ]
        for A, B in combinations(cand, 2):
            if set(A[0]) & set(B[0]):
                continue
            zc = [c for c in A[0] + B[0] if st.cand[c] & zb]
            el = {
                (q, z)
                for q in range(p.N)
                if not st.vals[q] and st.cand[q] & zb and q not in A[0] + B[0] and all(q in p.peers[c] for c in zc)
            }
            if not tz <= el:
                continue
            for C in als:
                if set(C[0]) & (set(A[0]) | set(B[0])):
                    continue
                for x in digits_of(A[1] & C[1] & ~zb):
                    if not _rcc(p, st, A, C, x):
                        continue
                    for y in digits_of(B[1] & C[1] & ~zb & ~bit(x)):
                        if not _rcc(p, st, B, C, y):
                            continue
                        tg = sorted({c for c, _ in tz})
                        short = f"{fmt_elims(nm, ctx.elims)}: ALS-XY-Wing (X={x}, Y={y}, Z={z})"
                        teach = (
                            f"Three almost-locked sets (one more digit than cells): A = {_als_desc(nm, A)}, "
                            f"B = {_als_desc(nm, B)} and the hinge C = {_als_desc(nm, C)}. A and C can't both "
                            f"hold {x} (their {x}s see each other); B and C can't both hold {y}. If neither A "
                            f"nor B contained {z}, both would lock up, putting {x} in A and {y} in B -- and C "
                            f"would lose two digits it can't spare. So {z} is in A or B, and {nm.cells(tg)}, "
                            f"seeing all those {z}s, can't be {z}."
                        )
                        J = _J(
                            ctx,
                            digits=[x, y, z],
                            z=z,
                            rcc=[x, y],
                            als=[{"cells": list(a[0]), "digits": list(digits_of(a[1]))} for a in (A, B, C)],
                            base_cells=list(A[0] + B[0] + C[0]),
                            cover_cells=tg,
                        )
                        return _result(ctx, J, short, teach, tz == set(ctx.elims))
    return _generic(ctx)


def _h_death_blossom(ctx):
    _nm, p, st = ctx.nm, ctx.p, ctx.st
    zs = _elim_digits(ctx)
    ea = _engine_als(ctx)
    pc = ctx.engine.get("pattern_cells") or []
    if ea and pc and len(zs) == 1:
        inals = {c for a in ea for c in a[0]}
        stems = [c for c in pc if c not in inals and not st.vals[c]]
        if len(stems) == 1:
            stem, z = stems[0], zs[0]
            sds = [d for d in digits_of(st.cand[stem]) if d != z]
            petals = []
            for d in sds:
                pt = next(
                    (
                        a
                        for a in ea
                        if a[1] & bit(d)
                        and a not in petals
                        and all(stem in p.peers[c] for c in a[0] if st.cand[c] & bit(d))
                    ),
                    None,
                )
                petals.append(pt)
            if None not in petals:
                ctx.used_engine = True
                return _db_render(ctx, stem, sds, petals, z)
    als = _als_list(p, st)
    for z in zs:
        zb = bit(z)
        tz = {t for t in ctx.elims if t[1] == z}
        t0 = next(iter(tz))
        for stem in range(p.N):
            if st.vals[stem] or not 2 <= popcount(st.cand[stem]) <= 3 or stem == t0[0]:
                continue
            sds = [d for d in digits_of(st.cand[stem]) if d != z]
            if st.cand[stem] & zb and t0[0] not in p.peers[stem]:
                continue
            options = []
            for d in sds:
                opts = [
                    a
                    for a in als
                    if stem not in a[0]
                    and a[1] & bit(d)
                    and a[1] & zb
                    and all(stem in p.peers[c] for c in a[0] if st.cand[c] & bit(d))
                    and all(t0[0] in p.peers[c] for c in a[0] if st.cand[c] & zb)
                    and t0[0] not in a[0]
                ]
                options.append(opts[:40])
            if any(not o for o in options):
                continue

            def rec(i, chosen):
                if i == len(sds):
                    return list(chosen)
                for a in options[i]:
                    if any(set(a[0]) & set(b[0]) for b in chosen):
                        continue
                    r = rec(i + 1, chosen + [a])
                    if r:
                        return r
                return None

            petals = rec(0, [])
            if not petals:
                continue
            zc = [c for a in petals for c in a[0] if st.cand[c] & zb] + ([stem] if st.cand[stem] & zb else [])
            el = {
                (q, z)
                for q in range(p.N)
                if not st.vals[q]
                and st.cand[q] & zb
                and q != stem
                and all(q in p.peers[c] for c in zc)
                and all(q not in a[0] for a in petals)
            }
            if not tz <= el:
                continue
            return _db_render(ctx, stem, sds, petals, z)
    return _generic(ctx)


def _db_render(ctx, stem, sds, petals, z):
    nm, st = ctx.nm, ctx.st
    tz = {t for t in ctx.elims if t[1] == z}
    tg = sorted({c for c, _ in tz})
    pt = "; ".join(f"if it is {d}, petal {_als_desc(nm, a)} loses its {d} and is locked" for d, a in zip(sds, petals))
    short = f"{fmt_elims(nm, ctx.elims)}: death blossom on stem {nm.cell(stem)}"
    teach = (
        f"The stem {nm.cell(stem)} {nm.cset(st.cand[stem])} decides everything: {pt}. A locked petal must use "
        f"all its remaining digits, and every petal contains {z}"
        + (f" (or the stem itself is {z})" if st.cand[stem] & bit(z) else "")
        + f" -- so whatever the stem is, some {z} ends up in a cell that {nm.cells(tg)} "
        f"{'sees' if len(tg) == 1 else 'see'}. No {z} there."
    )
    J = _J(
        ctx,
        digits=sds + [z],
        z=z,
        base_cells=[stem] + [c for a in petals for c in a[0]],
        als=[{"cells": list(a[0]), "digits": list(digits_of(a[1]))} for a in petals],
        cover_cells=tg,
    )
    return _result(ctx, J, short, teach, tz == set(ctx.elims))


def _mental_chain_single(ctx, ps, path):
    """Engine elimination chain on the mental view, after which the target is a single."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    a, z = path[0][0], path[-1][0]
    gone = [
        (q, d)
        for q in range(p.N)
        if not st.vals[q]
        for d in digits_of(ps.cand[q])
        if (q, d) not in (a, z) and _weak(p, ps, a, (q, d)) and _weak(p, ps, z, (q, d))
    ]
    md2 = list(ps.cand)
    for q, d in gone:
        md2[q] &= ~bit(d)
    how = None
    if md2[c] == bit(v):
        how = f"{nm.cell(c)} is left with only {v}"
    else:
        for gi in p.groups_of[c]:
            if p.groups[gi].complete and all(
                not md2[q] & bit(v) for q in p.groups[gi].cells if q != c and not st.vals[q]
            ):
                how = f"{nm.cell(c)} is the only place left for {v} in {nm.unit(gi)}"
                break
    if not how:
        return None
    rel = [t for t in gone if t[0] == c or t[1] == v]
    alsc = {x.get("id"): x.get("cells") for x in ctx.engine.get("als") or ()}
    links = _chain_links(path)
    short = f"{nm.cell(c)} = {v}: a short chain in the head clears the way"
    teach = (
        f"Without pencil marks, think about what the cells can still be. Suppose {nm.cell(a[0])} is NOT {a[1]}: "
        f"{', '.join(_chain_text(nm, p, path, alsc))}. So "
        + (
            f"{nm.cell(a[0])} must be {a[1]} or {z[1]}"
            if a[0] == z[0]
            else f"{nm.cell(a[0])} is {a[1]} or {nm.cell(z[0])} is {z[1]}"
        )
        + f", and anything clashing with both is impossible -- in particular "
        f"{fmt_elims(nm, rel[:6]) if rel else 'the candidates in the way'}. Now {how}."
    )
    J = _J(ctx, digits=[v], links=links, base_cells=[n[0][0] for n in path if isinstance(n[0][0], int)])
    return _result(
        ctx,
        J,
        short,
        teach,
        bool(rel) and _path_valid(p, ps, path),
        chain=_chain_vis(nm, links),
        lines=_chain_lines(p, path),
        extra_cells=[t[0] for t in rel[:6]],
    )


def _h_mental_chain(ctx):
    """Short chain reasoned without notes (on the mental view), ending in a single."""
    nm, p, st = ctx.nm, ctx.p, ctx.st
    c, v = ctx.place
    md, _ = mental_view(p, st, level=3)
    ps = st.copy()
    ps.cand = [0 if st.vals[q] else md[q] for q in range(p.N)]
    ep = _engine_path(ctx)
    if ep and ep[0][0] != (c, v):
        r = _mental_chain_single(ctx, ps, ep)
        if r:
            return r
    path = ep if ep and ep[0][0] == (c, v) else _find_chain(p, ps, (c, v), "aic", max_len=8, place=True)
    if path:
        steps = _chain_text(nm, p, path)
        links = [
            {
                "a": path[i - 1][0],
                "b": path[i][0],
                "strong": i % 2 == 1,
                "source": path[i][1] if i % 2 == 1 else "weak",
                "unit": path[i][2],
            }
            for i in range(1, len(path))
        ]
        short = f"{nm.cell(c)} = {v}: a short chain without notes -- if it weren't {v}, it would have to be {v}"
        teach = (
            f"No pencil marks needed, just a few 'if-then' steps on what each cell can still be. Suppose "
            f"{nm.cell(c)} is not {v}: {', '.join(steps)}. The chain comes back and forces {nm.cell(c)} to be "
            f"{v} after all, so it is {v}."
        )
        J = _J(ctx, digits=[v], links=links, base_cells=[n[0][0] for n in path])
        chain = [
            [nm.cell(l["a"][0]), l["a"][1], nm.cell(l["b"][0]), l["b"][1], "strong" if l["strong"] else "weak"]
            for l in links
        ]
        return _result(ctx, J, short, teach, True, chain=chain, lines=_chain_lines(p, path))
    others = [d for d in digits_of(md[c]) if d != v]
    found = []
    for d in others:
        pth = _find_chain(p, ps, (c, d), "aic", max_len=8)
        if not pth:
            break
        found.append((d, pth))
    if others and len(found) == len(others):
        parts, cells, links = [], [], []
        for d, pth in found:
            (sc, sd), (ec, ed) = pth[0][0], pth[-1][0]
            parts.append(
                f"{d} goes because either {nm.cell(sc)} is {sd} or {nm.cell(ec)} is {ed} "
                f"(if {nm.cell(sc)} isn't {sd}: {', '.join(_chain_text(nm, p, pth))}), and both clash with it"
            )
            cells += [n[0][0] for n in pth]
            links += [
                {
                    "a": pth[i - 1][0],
                    "b": pth[i][0],
                    "strong": i % 2 == 1,
                    "source": pth[i][1] if i % 2 else "weak",
                    "unit": pth[i][2],
                }
                for i in range(1, len(pth))
            ]
        short = f"{nm.cell(c)} = {v}: a short chain rules out its other options"
        teach = (
            f"Reason without notes about what {nm.cell(c)} can be: {nm.digits(digits_of(md[c]))}. "
            f"{_cap('; '.join(parts))}. That leaves {v}."
        )
        J = _J(ctx, digits=[v], links=links, base_cells=cells)
        return _result(ctx, J, short, teach, True, lines=[ln for _, pth in found for ln in _chain_lines(p, pth)])
    return _generic(ctx)
