"""Techniques against independent reference finders written from the textbook definitions (sudokuwiki.org, HoDoKu):
XY-Chain, Simple Colouring, Unique Rectangle (types 1, 2, 4, hidden 1, 2), Aligned Pair Exclusion, 3D Medusa, Pattern
Overlay (rules 1, 2) and ALS-XZ;
on mid-solve positions of generated puzzles (fixtures/technique_positions.json), the engine's XY-Chain and Simple
Colouring eliminations equal the reference's, and each added rule (colour unit wrap, hidden UR type 2, extended UR
type 2, APE with a 2-cell set) is found where it applies and removes only candidates the solution does not use."""

import collections
import copy
import itertools
import json
from collections import defaultdict
from pathlib import Path

import pytest

import pencilmark
from pencilmark import api
from pencilmark import cbackend as CB
from pencilmark import solver as S

POS = json.loads((Path(__file__).parent / "fixtures" / "technique_positions.json").read_text("utf-8"))
HOUSES = [[r * 9 + c for c in range(9)] for r in range(9)] + [[r * 9 + c for r in range(9)] for c in range(9)]
HOUSES += [[(br + i // 3) * 9 + bc + i % 3 for i in range(9)] for br in (0, 3, 6) for bc in (0, 3, 6)]
PEERS = [set().union(*[set(h) for h in HOUSES if c in h]) - {c} for c in range(81)]


def _xy_chains(cand, max_cells=8):
    """eliminations of XY-chains of up to max_cells bivalue cells (the engine's 15-link limit)"""
    out, bi = set(), [c for c in range(81) if len(cand[c]) == 2]
    for c0 in bi:
        for x in cand[c0]:
            stack = [(c0, (set(cand[c0]) - {x}).pop(), (c0,))]
            while stack:
                c, on, path = stack.pop()
                if len(path) > 1 and on == x:
                    out |= {(t, x) for t in PEERS[c0] & PEERS[c] if x in cand[t] and t not in (c0, c)}
                if len(path) < max_cells:
                    stack += [
                        (n, (set(cand[n]) - {on}).pop(), path + (n,))
                        for n in bi
                        if n not in path and n in PEERS[c] and on in cand[n]
                    ]
    return out


def _simple_colouring(cand):
    """wrap (two same-colour cells see each other), unit wrap (a colour sees every place of the digit in a house) and
    trap (an uncoloured candidate sees both colours), per digit and conjugate-pair cluster of 4+ cells"""
    out = set()
    for d in range(1, 10):
        adj = defaultdict(set)
        for h in HOUSES:
            hc = [c for c in h if d in cand[c]]
            if len(hc) == 2:
                adj[hc[0]].add(hc[1])
                adj[hc[1]].add(hc[0])
        seen = set()
        for s in sorted(adj):
            if s in seen:
                continue
            col, todo = {s: 0}, [s]
            while todo:
                u = todo.pop()
                for v in adj[u]:
                    if v not in col:
                        col[v] = 1 - col[u]
                        todo.append(v)
            seen |= set(col)
            if len(col) < 4:
                continue
            false = None
            for k in (0, 1):
                ks = [c for c in col if col[c] == k]
                if any(b in PEERS[a] for a in ks for b in ks):
                    false = k
            for k in (0, 1):
                for h in HOUSES:
                    hc = [c for c in h if d in cand[c]]
                    if (
                        false is None
                        and hc
                        and all(col[c] == 1 - k if c in col else any(col.get(q) == k for q in PEERS[c]) for c in hc)
                    ):
                        false = k
            if false is not None:
                out |= {(c, d) for c in col if col[c] == false}
                continue
            for t in range(81):
                if t not in col and d in cand[t] and len(cand[t]) > 1:
                    seen_cols = {col[q] for q in PEERS[t] if q in col}
                    if seen_cols == {0, 1}:
                        out.add((t, d))
    return out


def _state(pos):
    p = pencilmark.api._load(pos["puzzle"])
    p.finalize()
    filled = {int(c): d for c, d in pos["givens"].items()}
    q = copy.copy(p)
    q.givens = filled
    cand = {c: [d for d in range(1, 10) if pos["mask"][c] >> (d - 1) & 1] for c in range(81)}
    return p, q, pos["mask"], cand, filled


def _moves(pos, techs):
    p, q, mask, cand, filled = _state(pos)
    keep = {k for k, v in S.TECH_NAMES.items() if v in techs}
    mv = CB.state_moves(
        q,
        api._params("computer"),
        cpuzzle=CB.to_cpuzzle(p),
        cand=mask,
        limit_per_tech=0,
        details=True,
        assume_unique=True,
        disabled=list(set(S.TECH_NAMES) - keep),
    )
    return [m for m in mv if m["tech"] in keep], cand, filled


@pytest.mark.parametrize("pos", [x for x in POS if x["kind"] in ("xy", "colour_unit")], ids=lambda x: x["id"])
def test_reference_finders_agree(pos):
    techs, ref = ({"XY-Chain", "RemotePairs"}, _xy_chains) if pos["kind"] == "xy" else ({"Coloring"}, _simple_colouring)
    mv, cand, filled = _moves(pos, techs)
    ours = {tuple(e) for m in mv for e in m["elim"]}
    want = {e for e in ref({c: ([filled[c]] if c in filled else cand[c]) for c in range(81)}) if e[0] not in filled}
    assert ours >= want and (pos["kind"] == "xy" or ours == want)


KINDS = {
    "colour_unit": "Coloring",
    "medusa_unit": "3DMedusa",
    "hur2": "UniqueRectangle",
    "xur2": "UniqueRectangle",
    "ape_als": "AlignedPairExclusion",
}


@pytest.mark.parametrize("pos", [x for x in POS if x["kind"] in KINDS], ids=lambda x: x["id"])
def test_added_rules_fire_and_are_sound(pos):
    mv, _, _ = _moves(pos, {KINDS[pos["kind"]]})
    assert mv
    sol = [int(x) for x in pencilmark.solve(pos["puzzle"])]
    assert all(sol[c] != d for m in mv for c, d in m["elim"])


BOX = lambda c: (c // 27) * 3 + (c % 9) // 3  # noqa: E731
box = BOX


def _ur(cd):
    out = set()
    for r1, r2 in itertools.combinations(range(9), 2):
        for c1, c2 in itertools.combinations(range(9), 2):
            cells = [r1 * 9 + c1, r1 * 9 + c2, r2 * 9 + c1, r2 * 9 + c2]
            if len({box(c) for c in cells}) != 2 or any(len(cd[c]) < 2 for c in cells):
                continue
            # corners may miss one of the pair (HoDoKu's missing candidates): a floor holds only digits of {x, y}
            union = set().union(*[set(cd[c]) for c in cells])
            for x, y in itertools.combinations(sorted(union), 2):
                xy = {x, y}
                if any(not set(cd[c]) & xy for c in cells):
                    continue
                bi = [c for c in cells if set(cd[c]) <= xy]
                if len(bi) == 3:  # type 1
                    t = next(c for c in cells if c not in bi)
                    out |= {(t, d) for d in set(cd[t]) & xy}
                if len(bi) == 2 and (bi[0] // 9 == bi[1] // 9 or bi[0] % 9 == bi[1] % 9):
                    roof = [c for c in cells if c not in bi]
                    e0, e1 = set(cd[roof[0]]) - xy, set(cd[roof[1]]) - xy
                    if len(e0 | e1) == 1 and e0 and e1:  # type 2
                        z = next(iter(e0))
                        out |= {(t, z) for t in PEERS[roof[0]] & PEERS[roof[1]] if z in cd[t] and len(cd[t]) > 1}
                    for h in HOUSES:  # type 4: x (or y) only in the roof within a house holding both
                        if roof[0] in h and roof[1] in h:
                            for a, b in ((x, y), (y, x)):
                                if all(a not in cd[q] or q in roof for q in h):
                                    out |= {(q, b) for q in roof if b in cd[q]}
                    # hidden type 2: a strong on f-rf (their shared house) -> b leaves rg
                    for f in bi:
                        rf = next(q for q in roof if q // 9 == f // 9 or q % 9 == f % 9)
                        rg = next(q for q in roof if q != rf)
                        for a, b in ((x, y), (y, x)):
                            h = next(hh for hh in HOUSES[:18] if f in hh and rf in hh)
                            if {q for q in h if a in cd[q]} == {f, rf} and b in cd[rg]:
                                out.add((rg, b))
                if len(bi) == 2 and bi[0] // 9 != bi[1] // 9 and bi[0] % 9 != bi[1] % 9:  # type 6: an x-wing on a
                    roof = [c for c in cells if c not in bi]
                    for a in xy:
                        rows = all(
                            {q for q in HOUSES[r] if a in cd[q]} == {cells[2 * i], cells[2 * i + 1]}
                            for i, r in enumerate((r1, r2))
                        )
                        cols = all(
                            {q for q in HOUSES[9 + k] if a in cd[q]} == {cells[i], cells[i + 2]}
                            for i, k in enumerate((c1, c2))
                        )
                        if rows or cols:
                            out |= {(q, a) for q in roof if a in cd[q]}
                for a_ in bi:  # hidden type 1: bivalue corner, opposite corner o with a strong on both its sides
                    o = next(c for c in cells if c // 9 != a_ // 9 and c % 9 != a_ % 9)
                    s1 = next(c for c in cells if c // 9 == o // 9 and c != o)
                    s2 = next(c for c in cells if c % 9 == o % 9 and c != o)
                    for a, b in ((x, y), (y, x)):
                        row = {q for q in HOUSES[o // 9] if a in cd[q]}
                        col = {q for q in HOUSES[9 + o % 9] if a in cd[q]}
                        if row == {o, s1} and col == {o, s2} and b in cd[o]:
                            out.add((o, b))
    return out


def _ape(cd, filled):
    """aligned pair exclusion (sudokuwiki): two cells, aligned or not (then the pair may repeat a digit); a value pair
    dies when a cell seeing both has no other candidate, or an almost locked set whose cells all see both holds both
    digits (n cells left with n - 1 digits)"""
    out = set()
    sets = [(cs, ds) for cs, ds in _alss(cd, filled)]
    un = [c for c in range(81) if c not in filled and len(cd[c]) > 1]
    for X, Y in itertools.combinations(un, 2):
        aligned = Y in PEERS[X]
        single = [set(cd[q]) for q in PEERS[X] & PEERS[Y] if q not in filled and len(cd[q]) == 1]
        witnesses = [
            ds for cs, ds in sets if X not in cs and Y not in cs and all(X in PEERS[q] and Y in PEERS[q] for q in cs)
        ]
        if not single and not witnesses:
            continue
        okX, okY = set(), set()
        for x in cd[X]:
            for y in cd[Y]:
                if x == y and aligned:
                    continue
                dead = any(w <= {x, y} for w in single) or (x != y and any({x, y} <= w for w in witnesses))
                if not dead:
                    okX.add(x), okY.add(y)
        if okX and okY:
            out |= {(X, x) for x in cd[X] if x not in okX} | {(Y, y) for y in cd[Y] if y not in okY}
    return out


def _medusa(cd, filled):
    out = set()
    nodes = [(c, d) for c in range(81) if c not in filled for d in cd[c]]
    adj = collections.defaultdict(set)
    for c in range(81):
        if len(cd[c]) == 2:
            a, b = cd[c]
            adj[(c, a)].add((c, b)), adj[(c, b)].add((c, a))
    for h in HOUSES:
        for d in range(1, 10):
            cs = [c for c in h if c not in filled and d in cd[c]]
            if len(cs) == 2:
                adj[(cs[0], d)].add((cs[1], d)), adj[(cs[1], d)].add((cs[0], d))
    seen = set()
    for s in nodes:
        if s in seen or s not in adj:
            continue
        col, todo = {s: 0}, [s]
        while todo:
            u = todo.pop()
            for v in adj[u]:
                if v not in col:
                    col[v] = 1 - col[u]
                    todo.append(v)
        seen |= set(col)
        if len({d for _, d in col}) < 2 or len(col) < 4:
            continue
        cm = [collections.defaultdict(set), collections.defaultdict(set)]
        for (c, d), k in col.items():
            cm[k][c].add(d)
        sees = lambda c, d, k: any(d in cm[k].get(q, ()) for q in PEERS[c])
        false = None
        for k in (0, 1):
            if any(len(ds) > 1 for ds in cm[k].values()):
                false = k
            if any(d in cm[k].get(q, ()) for (c, d), kk in col.items() if kk == k for q in PEERS[c]):
                false = k
            for c in range(81):
                if c not in filled and c not in cm[0] and c not in cm[1] and all(sees(c, d, k) for d in cd[c]):
                    false = k
            for h in HOUSES:
                for d in range(1, 10):
                    hc = [c for c in h if c not in filled and d in cd[c]]
                    if hc and all(
                        d not in cm[k].get(c, ())
                        and (d in cm[1 - k].get(c, ()) or (cm[k].get(c, set()) - {d}) or sees(c, d, k))
                        for c in hc
                    ):
                        false = k
            if false is not None:
                break
        if false is not None:
            out |= {(c, d) for (c, d), k in col.items() if k == false}
            continue
        for c in range(81):
            if c in filled:
                continue
            for d in cd[c]:
                if (c, d) in col:
                    continue
                if (
                    (cm[0].get(c) and cm[1].get(c))
                    or (sees(c, d, 0) and sees(c, d, 1))
                    or ((cm[1].get(c) and sees(c, d, 0)) or (cm[0].get(c) and sees(c, d, 1)))
                ):
                    out.add((c, d))
    return out


def _templates(cd, d):
    rows = [[c for c in range(r * 9, r * 9 + 9) if d in cd[c]] for r in range(9)]
    res = []

    def rec(r, used_c, used_b, acc):
        if r == 9:
            res.append(frozenset(acc))
            return
        for c in rows[r]:
            if c % 9 not in used_c and box(c) not in used_b:
                rec(r + 1, used_c | {c % 9}, used_b | {box(c)}, acc + [c])

    rec(0, frozenset(), frozenset(), [])
    return res


def _pom(cd):
    out1, out2 = set(), set()
    T = {d: _templates(cd, d) for d in range(1, 10)}
    for d in range(1, 10):
        cover = set().union(*T[d]) if T[d] else set()
        out1 |= {(c, d) for c in range(81) if len(cd[c]) > 1 and d in cd[c] and c not in cover}
    if all(len(t) <= 1000 for t in T.values()):
        for d in range(1, 10):
            alive = [t for t in T[d] if all(any(not (t & u) for u in T[w]) for w in range(1, 10) if w != d)]
            if alive:
                cover = set().union(*alive)
                out2 |= {(c, d) for c in range(81) if len(cd[c]) > 1 and d in cd[c] and c not in cover}
    return out1, out2


def _alss(cd, filled):
    out = set()
    for h in HOUSES:
        un = [c for c in h if c not in filled]
        for n in range(1, len(un)):
            for cs in itertools.combinations(un, n):
                ds = set().union(*[set(cd[c]) for c in cs])
                if len(ds) == n + 1:
                    out.add((frozenset(cs), frozenset(ds)))
    return list(out)


def _als_xz(cd, filled):
    out = set()
    A = _alss(cd, filled)
    for (ca, da), (cb, db) in itertools.combinations(A, 2):
        common = da & db
        for x in common:
            xs = [c for c in ca | cb if x in cd[c]]
            if any(x in cd[c] for c in ca & cb):  # overlapping sets: the restricted common has no place in the overlap
                continue
            if not all(b in PEERS[a] for a, b in itertools.combinations(xs, 2)):
                continue
            for z in common - {x}:
                zs = [c for c in ca | cb if z in cd[c]]
                for t in set.intersection(*[PEERS[c] for c in zs]) - (ca | cb):
                    if len(cd[t]) > 1 and z in cd[t]:
                        out.add((t, z))
    return out


def _er(cd, filled):
    out = set()
    rowc = lambda r: [r * 9 + c for c in range(9)]
    colc = lambda c: [r * 9 + c for r in range(9)]
    for d in range(1, 10):
        has = lambda x: x not in filled and d in cd[x]
        for br in (0, 3, 6):
            for bc in (0, 3, 6):
                box = [(br + i) * 9 + bc + j for i in range(3) for j in range(3) if has((br + i) * 9 + bc + j)]
                if len(box) < 2:
                    continue
                for r in range(br, br + 3):
                    for c in range(bc, bc + 3):
                        if not all(x // 9 == r or x % 9 == c for x in box):
                            continue
                        if all(x // 9 == r for x in box) or all(x % 9 == c for x in box):
                            continue  # pointing
                        # conjugate pair in a column c2 outside the stack, one end in row r
                        for c2 in range(9):
                            if bc <= c2 < bc + 3:
                                continue
                            cs = [x for x in colc(c2) if has(x)]
                            if len(cs) == 2 and r * 9 + c2 in cs:
                                other = cs[0] if cs[1] == r * 9 + c2 else cs[1]
                                z = (other // 9) * 9 + c
                                if has(z) and not (br <= z // 9 < br + 3):
                                    out.add((z, d))
                        for r2 in range(9):
                            if br <= r2 < br + 3:
                                continue
                            rs = [x for x in rowc(r2) if has(x)]
                            if len(rs) == 2 and r2 * 9 + c in rs:
                                other = rs[0] if rs[1] == r2 * 9 + c else rs[1]
                                z = r * 9 + other % 9
                                if has(z) and not (bc <= z % 9 < bc + 3):
                                    out.add((z, d))
    return out


# reference == engine (or the engine a superset: it has forms the reference leaves out, every one sound)
REFS = [
    ("UniqueRectangle", lambda cd, filled: _ur(cd), "superset"),
    ("AlignedPairExclusion", _ape, "equal"),
    ("3DMedusa", _medusa, "equal"),
    ("PatternOverlay", lambda cd, filled: set().union(*_pom(cd)), "equal"),
    ("ALS-XZ", _als_xz, "superset"),
    ("EmptyRectangle", _er, "equal"),
]


@pytest.mark.parametrize("pos", POS, ids=lambda x: x["id"])
def test_more_reference_finders(pos):
    p, q, mask, cand, filled = _state(pos)
    cd = {c: ([filled[c]] if c in filled else cand[c]) for c in range(81)}
    sol = [int(x) for x in pencilmark.solve(pos["puzzle"])]
    for tech, ref_fn, rel in REFS + [("EmptyRectangle", _er, "equal-canonical")]:
        mv, _, _ = _moves(pos, {tech, "CanonicalEnumeration"} if rel == "equal-canonical" else {tech})
        mv = [m for m in mv if S.TECH_NAMES[m["tech"]] == tech]
        ours = {tuple(e) for m in mv for e in m["elim"]}
        ref = {e for e in ref_fn(cd, filled) if e[0] not in filled}
        assert ours >= ref if rel == "superset" else ours == ref, (tech, sorted(ref - ours)[:3], sorted(ours - ref)[:3])
        assert all(sol[c] != d for c, d in ours), tech


# kind -> (technique, which listed move, words its explanation must use)
EXPLAINED = {
    "hur2": ("UniqueRectangle", lambda m: m["code"] == "HUR", "hidden unique rectangle"),
    "xur2": ("UniqueRectangle", lambda m: m["code"] == "XUR2", "extended unique rectangle type 2"),
    "ape_als": ("AlignedPairExclusion", lambda m: True, "aligned pair exclusion"),
    "colour_unit": ("Coloring", lambda m: True, "colouring"),
    "medusa_unit": ("3DMedusa", lambda m: m["code"] == "medusa wrap (emptied house)", "no place for"),
    "xy": ("XY-Chain", lambda m: True, "XY-Chain"),
    "wxyz2": ("WXYZ-Wing", lambda m: m["code"] in ("WXYZ-Wing (type 2)", "VWXYZ-Wing (type 2)"), "type 2"),
    "pom2": ("PatternOverlay", lambda m: m["code"] == "pattern overlay (rule 2)", "rule 2"),
    "er": ("EmptyRectangle", lambda m: True, "empty rectangle"),
    "db": ("DeathBlossom", lambda m: True, "death blossom"),
    "finned": ("FinnedFish", lambda m: not any(w in str(m["code"]) for w in ("Franken", "Mutant")), "finned|sashimi"),
    # a Franken spelling's eliminations: the explainer may name the plainer fish that makes them (preferred)
    "franken": (
        "FinnedFish",
        lambda m: any(w in str(m["code"]) for w in ("Franken", "Mutant")),
        "x-wing|swordfish|jellyfish",
    ),
    "alsxz2": ("ALS-XZ", lambda m: m["code"] == "AXZ2", "doubly linked"),
    "alsxy": ("ALS-XY-Wing", lambda m: True, "ALS-XY-Wing"),
}


@pytest.mark.parametrize("pos", POS, ids=lambda x: x["id"])
def test_explanation_names_the_pattern(pos):
    """the English explanation of the rule's move at the position: verified, the pattern's own wording (not another
    type's or the generic fallback), every eliminated cell named"""
    from types import SimpleNamespace as NS

    from pencilmark.explain import explain
    from pencilmark.explain.grid import State

    tech, which, words = EXPLAINED[pos["kind"]]
    p, q, mask, cand, filled = _state(pos)
    cp = CB.to_cpuzzle(p)
    keep = {k for k, v in S.TECH_NAMES.items() if v == tech}
    mv = CB.state_moves(q, api._params("computer"), cpuzzle=cp, cand=mask, limit_per_tech=0, details=True,
                        assume_unique=True, disabled=list(set(S.TECH_NAMES) - keep))  # fmt: skip
    m = next(m for m in mv if m["tech"] in keep and which(m))
    vals = [filled.get(c, 0) for c in range(81)]
    st0 = State(p, vals, [0 if vals[c] else x for c, x in enumerate(mask)], "notes")
    st0.givens = set(p.givens)
    move = NS(feat=(m["tech"],), place=tuple(m["place"]) if m["place"] else None, elim=tuple(map(tuple, m["elim"])),
              code=m["code"], xmeta=m["xmeta"], explain=CB.explain_record(p, m, cp))  # fmt: skip
    e = explain(NS(move=move, mode="notes"), p, st0)
    assert e["verified"] and "error" not in e, e
    text = (e["short"] + " " + e["teach"]).lower()
    assert any(w.lower() in text for w in words.split("|")), (e["short"], e["teach"])
    names = {f"r{c // 9 + 1}c{c % 9 + 1}" for c, _ in m["elim"]}
    assert all(n in e["teach"] or n in e["short"] for n in names), (names, e["teach"])
    if pos["kind"] in SUBSTEPS:  # the last sub-step marks every removed candidate in red
        last = e["substeps"][-1]
        red = {a["candidate"] for a in last.get("annotations", []) if a.get("colour") == "red"}
        assert red == {f"r{c // 9 + 1}c{c % 9 + 1}#{d}" for c, d in m["elim"]}, e["substeps"]


# rules whose explanation has sub-steps
SUBSTEPS = {"wxyz2", "colour_unit", "finned", "franken"}
