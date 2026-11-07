"""Search procedures.

All functions take a Board, a random.Random and return (solution, givens {cell: digit}, elements) or None.
"""

from __future__ import annotations

import logging
import time

from . import elements as EL
from .checks import Oracle

_log = logging.getLogger(__name__)


def dig(
    b,
    kinds,
    rng,
    chk,
    sol=None,
    min_givens=0,
    grid_floors=None,
    seeds=None,
    max_els=10**6,
    symmetry=None,
    fixed=None,
    blocked=(),
    pool_tries=25,
    caps=None,
    dense=(),
    shape=None,
    most=(),
    deadline=None,
    keep=False,
):
    """givens-digging with elements added on demand.

    1. `seeds` {kind: count} elements are placed first (apart from elements of their own kind), then the `most` classes are packed; their cells, then
       their peers, are emptied first, so they tend to end up required;
    2. the remaining givens are removed in random order (whole symmetry orbits at a time) down to `min_givens`; when a
       removal breaks solvability (chk: band-capped logic), the most informative element of `kinds` through that cell
       that restores it is added (if any), else the givens stay;
    3. prune: every element the puzzle stays solvable without is dropped (no decorative elements).
    fixed {cell: True (stays given) / False (stays empty)}; blocked cells take no elements. kinds / seeds may name element
    classes (kropki_black, x, odd, ...); caps {class: max} limits how many of a class are added. dense: 2-cell / 1-cell
    classes seeded with EVERY instance true in the solution before digging (few-givens targets); pruning then removes the
    ones the puzzle doesn't need. shape {kind: limits}: the templates' length / sum limits (elements.fits). most: classes
    packed into the grid after the seeds, as many disjoint ones as a few random packings find, and never pruned.
    grid_floors [(cells, n)]: no grid of a layout goes below n givens.
    deadline (time.time()): when it passes, the attempt is given up (None), or with keep the digging stops and the givens
    still in place stay."""
    fixed = dict(fixed or {})
    seeds = dict(seeds or {})
    over = lambda: deadline is not None and time.time() > deadline
    planted = None
    wl = (shape or {}).get("whisper", {}).get("length", (None, None))[0]
    if sol is None and wl and wl > 16 and seeds.get("whisper"):  # longer than random grids hold: build around it
        got = EL.planted_whisper(b, wl, rng)
        sol = b.solution(rng, preset=got[1]) if got else None
        if sol is not None:
            planted = ("whisper", tuple(got[0]), None)
            seeds["whisper"] -= 1
    sol = sol or b.solution(rng)
    givens = {i: sol[i] for i in range(b.N) if fixed.get(i, True)}
    els = [planted] if planted else []
    caps = dict(caps or {})

    def taken(kind):
        """cells an element of `kind` may not use: blocked ones and those of elements of the same kind (cages and
        lines stay apart; a whisper may cross a cage, a dot sit on a cage's cell); edge markers may share cells, never
        the same edge"""
        bk = EL.base_kind(kind)
        if bk in EL.SHARED:
            return set(blocked)
        same = [x for x in els if x[0] == bk]  # and their diagonal steps, so a line of the kind does not cross one
        return set(blocked) | {c for x in same for c in x[1]} | {s for x in same for s in EL.diagonal_steps(b, x[1])}

    def fresh(e):
        return all(x[1] != e[1] for x in els)

    room = lambda e: all(
        sum(1 for x in els if EL.in_class(x, k)) < m for k, m in caps.items() if m is not None and EL.in_class(e, k)
    )
    for kind, cnt in (seeds or {}).items():
        for _ in range(cnt):
            for _try in range(40):
                t = taken(kind)
                g_ = [
                    e
                    for e in EL.grow(b, EL.base_kind(kind), sol, rng.randrange(b.N), t, rng, n=8, shape=shape)
                    if t.isdisjoint(e[1]) and EL.in_class(e, kind) and fresh(e)
                ]
                if g_:
                    els.append(g_[0])
                    break
    for kind in most:  # after the other classes' minimums, so they still find room
        best = []
        for _pack in range(12):
            got, u = [], taken(kind)
            edge = EL.base_kind(kind) in EL.SHARED
            for i in sorted(range(b.N), key=lambda _: rng.random()):
                if i in u:
                    continue
                g_ = [
                    e
                    for e in EL.grow(b, EL.base_kind(kind), sol, i, u, rng, n=40, shape=shape)
                    if u.isdisjoint(e[1]) and EL.in_class(e, kind) and fresh(e) and all(x[1] != e[1] for x in got)
                ]
                if g_:  # the smallest one leaves the most room for others
                    e = min(g_, key=lambda e: (len(e[1]), rng.random()))
                    got.append(e)
                    if not edge:
                        u |= set(e[1])
            if len(got) > len(best):
                best = got
        els += best
    for kind in dense:
        bk = EL.base_kind(kind)
        if bk not in ("kropki", "xv", "parity"):
            continue
        seen = {x[1] for x in els}
        for i in range(b.N):
            for e in EL.grow(b, bk, sol, i, set(blocked), rng, shape=shape):
                if EL.in_class(e, kind) and e[1] not in seen and (bk != "parity" or i not in taken("parity")):
                    els.append(e)
                    seen.add(e[1])
    # element cells are emptied first so the elements end up needed. When the request keeps many givens (a quarter of
    # the cells or more: a beginner's killer), cage cells are not: they may keep givens, so a cage's last cell is its
    # total minus the digits in it (user 2026-11-07); with few givens the cages carry the puzzle and go first as
    # before. A cage left fully given says nothing and the prune below drops it.
    cage_givens = min_givens >= b.N // 4
    el_cells = {c for x in els if not (cage_givens and x[0] == "cage") for c in x[1]} - set(blocked)
    peers = {j for c in el_cells for j in b.peers[c]} - el_cells
    rest = [i for i in range(b.N) if i not in el_cells and i not in peers]
    order = (
        sorted(el_cells, key=lambda _: rng.random())
        + sorted(peers, key=lambda _: rng.random())
        + sorted(rest, key=lambda _: rng.random())
    )
    order = [i for i in order if i not in fixed]
    if not chk.ok(givens, els):
        return None
    done = set()

    def removable(orb, also=()):  # the orbit's givens may go (with the cells `also` going too): the total and each of
        gone = set(orb) | set(also)  # the orbit's grids stay at or above their floors
        if not orb or len(givens) - len(gone) < min_givens:
            return False
        return not grid_floors or all(
            sum(1 for c in cs if c in givens and c not in gone) >= n for cs, n in grid_floors if cs & set(orb)
        )

    if b.N > 100:  # a big board (a layout): remove eight orbits at a time while that keeps working, then one by one
        pos, fails = 0, 0
        while pos < len(order) and fails < 2 and (deadline is None or time.time() < deadline):
            batch = []
            while len(batch) < 8 and pos < len(order):
                orb = [c for c in b.orbit(order[pos], symmetry) if c in givens and c not in fixed]
                pos += 1
                in_batch = {c for x in batch for c in x}
                if removable(orb, in_batch) and in_batch.isdisjoint(orb):
                    batch.append(orb)
            removed = {c: givens.pop(c) for orb in batch for c in orb}
            if batch and chk.ok(givens, els):
                done.update(c for orb in batch for x in orb for c in b.orbit(x, symmetry))
                fails = 0
            else:
                givens.update(removed)
                fails += 1
    for i in order:
        if len(givens) <= min_givens:
            break
        if deadline is not None and time.time() > deadline:
            if not keep:
                return None
            break
        if i in done:
            continue
        orb = [c for c in b.orbit(i, symmetry) if c in givens and c not in fixed]
        done.update(b.orbit(i, symmetry))
        if not removable(orb):
            continue
        removed = {c: givens.pop(c) for c in orb}
        if chk.ok(givens, els):
            continue
        restored = False
        if kinds and len(els) < max_els:
            cand = [
                e
                for k in kinds
                if i not in taken(k)
                for e in EL.grow(b, EL.base_kind(k), sol, i, taken(k), rng, shape=shape)
                if EL.in_class(e, k) and room(e) and fresh(e)
            ]
            cand.sort(key=lambda e: (EL.ncomb(b.n, len(e[1]), e[2]) if e[0] == "cage" else 0, rng.random()))
            for e in cand[:pool_tries]:
                if over():  # each check can take seconds (forcing chains on sparse variants)
                    break
                if chk.ok(givens, els + [e]):
                    els.append(e)
                    restored = True
                    break
        if not restored:
            givens.update(removed)
        if over() and not keep:
            return None
    mins = {k: n for k, n in (seeds or {}).items() if n}
    for e in list(els):  # prune decorative elements (never below a class's minimum, never one being maximized)
        if e == planted or any(EL.in_class(e, k) for k in most):
            continue
        rest_ = [x for x in els if x != e]
        if any(EL.in_class(e, k) and sum(1 for x in rest_ if EL.in_class(x, k)) < n for k, n in mins.items()):
            continue
        if over():
            if not keep:
                return None
            break  # keep: the elements left are those of a solvable puzzle, some maybe not needed
        if chk.ok(givens, rest_):
            els = rest_
    return sol, givens, els


def _cage_limits(lim):
    """(within_max(cells, total), below_min(cage)) for a cage template's limits {"length": (lo, hi), "sum": (lo, hi)}:
    pairing and merging never build a cage over a maximum, and cages under a minimum are merged first"""
    llo, lhi = (lim or {}).get("length", (None, None))
    slo, shi = (lim or {}).get("sum", (None, None))

    def within_max(n, total):
        return (lhi is None or n <= lhi) and (shi is None or total <= shi)

    def below_min(e):
        return (llo is not None and len(e[1]) < llo) or (slo is not None and e[2] < slo)

    return within_max, below_min


def _lift_minima(b, sol, els, rng, within_max, below):
    """merge every cage under its template's minimum into a neighboring cage (distinct digits, within the maxima),
    smallest neighbor first; None when one cannot grow"""
    els = list(els)
    while True:
        under = [e for e in els if below(e)]
        if not under:
            return els
        e = min(under, key=lambda x: (len(x[1]), rng.random()))
        own = {c: k for k, x in enumerate(els) for c in x[1]}
        hosts = [
            els[k]
            for k in sorted({own[j] for c in e[1] for j in b.nb[c] if j in own} - {els.index(e)})
            if not {sol[x] for x in e[1]} & {sol[x] for x in els[k][1]}
            and within_max(len(e[1]) + len(els[k][1]), e[2] + els[k][2])
        ]
        if not hosts:
            return None
        h = min(hosts, key=lambda x: (len(x[1]), rng.random()))
        els = [x for x in els if x is not e and x is not h] + [("cage", tuple(sorted(e[1] + h[1])), e[2] + h[2])]


def partition(b, rng, chk, n_givens=0, min_els=0, cover=True, lim=None):
    """killer covering the board: keep `n_givens` random givens, tile the other cells with 2-cell informative cages,
    then merge neighboring cages (distinct digits, <= 6 cells) -- or delete cages if cover=False -- while the puzzle
    stays solvable within the checker's cap. A cell left alone becomes a given (a 1-cell cage is a given in disguise)
    when there are givens; with none it joins a neighboring cage. lim: the cage template's length / sum limits (the
    pairing and the merges keep under the maxima, cages under a minimum merge first; a result missing one is None)."""
    within_max, below = _cage_limits(lim)
    cap = max(6, (lim or {}).get("length", (None, None))[0] or 0)
    sol = b.solution(rng)
    NB = b.nb
    givens = {i: sol[i] for i in sorted(range(b.N), key=lambda _: rng.random())[:n_givens]}
    owner, els = dict.fromkeys(givens, 0), []
    cells = list(range(b.N))
    rng.shuffle(cells)
    for c in cells:
        if c in owner:
            continue
        opts = [j for j in NB[c] if j not in owner and sol[j] != sol[c] and within_max(2, sol[c] + sol[j])]
        if not opts:
            els.append(("cage", (c,), sol[c]))
            owner[c] = 1
            continue
        pair = lambda j: ("cage", (c, j), sol[c] + sol[j])  # noqa: E731
        j = min(opts, key=lambda j: (below(pair(j)), EL.ncomb(b.n, 2, sol[c] + sol[j]), rng.random()))
        els.append(("cage", tuple(sorted((c, j))), sol[c] + sol[j]))
        owner[c] = owner[j] = 1
    for e in [e for e in els if len(e[1]) == 1]:  # a single cell: a given, or absorbed into a neighboring cage
        c = e[1][0]
        if n_givens:
            givens[c] = sol[c]
            els.remove(e)
            continue
        hosts = [
            x
            for x in els
            if x is not e
            and len(x[1]) < max(4, cap)
            and any(j in x[1] for j in NB[c])
            and sol[c] not in {sol[y] for y in x[1]}
            and within_max(len(x[1]) + 1, x[2] + sol[c])
        ]
        if not hosts:
            if lim:  # the minima pass below merges it, or the tiling is drawn again
                continue
            return None
        h = min(hosts, key=lambda x: (EL.ncomb(b.n, len(x[1]) + 1, x[2] + sol[c]), rng.random()))
        els[els.index(h)] = ("cage", tuple(sorted(h[1] + (c,))), h[2] + sol[c])
        els.remove(e)
    if not chk.ok(givens, els):
        return None
    for _ in range(400):
        changed = False
        order = list(range(len(els)))
        rng.shuffle(order)
        order.sort(key=lambda i: not below(els[i]))  # cages under a minimum merge first
        for a in order:
            if a >= len(els):
                continue
            ea = els[a]
            own = {c: k for k, e in enumerate(els) for c in e[1]}  # givens belong to no cage
            nbrs = {own[j] for c in ea[1] for j in NB[c] if j in own} - {a}
            moves = []
            for k in sorted(nbrs):
                eb = els[k]
                if {sol[x] for x in ea[1]} & {sol[x] for x in eb[1]} or len(ea[1]) + len(eb[1]) > min(cap, b.n):
                    continue
                if not within_max(len(ea[1]) + len(eb[1]), ea[2] + eb[2]):
                    continue
                m = ("cage", tuple(sorted(ea[1] + eb[1])), ea[2] + eb[2])
                moves.append([e for i_, e in enumerate(els) if i_ not in (a, k)] + [m])
            if not cover and not below(ea):
                moves.append([e for i_, e in enumerate(els) if i_ != a])
            rng.shuffle(moves)
            for cand in moves if below(ea) else moves[:4]:  # a cage under its minimum tries every merge
                if chk.ok(givens, cand):
                    els = cand
                    changed = True
                    break
        if not changed:
            break
    if any(len(e[1]) == 1 for e in els) or len(els) < min_els:  # a 1-cell cage is a given in disguise
        return None
    if any(below(e) for e in els):  # the merges kept it solvable; what is still under a minimum is merged now
        els = _lift_minima(b, sol, els, rng, within_max, below)
        if els is None or not chk.ok(givens, els):
            return None
    return sol, givens, els


def cage_count(b, n_cages, rng, time_limit=30.0, deadline=None, lim=None):
    """killer with EXACTLY n_cages cages and no givens: tile with 2-cell cages, then merge neighboring cages (distinct
    digits) in batches while the puzzle stays UNIQUE (CP-SAT oracle with a counterexample cache; a failed batch is
    bisected). No human-solvability cap: the card grades whatever results. lim: the cage template's length / sum
    limits, as in partition."""
    import time as _t

    within_max, below = _cage_limits(lim)
    sol = b.solution(rng)
    NB = b.nb
    owner, els = {}, []
    cells = list(range(b.N))
    rng.shuffle(cells)
    for c in cells:
        if c in owner:
            continue
        opts = [j for j in NB[c] if j not in owner and sol[j] != sol[c] and within_max(2, sol[c] + sol[j])]
        if not opts:
            els.append(("cage", (c,), sol[c]))
            owner[c] = 1
            continue
        pair = lambda j: ("cage", (c, j), sol[c] + sol[j])  # noqa: E731
        j = min(opts, key=lambda j: (below(pair(j)), EL.ncomb(b.n, 2, sol[c] + sol[j]), rng.random()))
        els.append(("cage", tuple(sorted((c, j))), sol[c] + sol[j]))
        owner[c] = owner[j] = 1
    els = _lift_minima(b, sol, els, rng, within_max, below)
    if els is None:
        return None
    orc = Oracle(b, sol, time_limit=time_limit)
    unique = lambda e: orc.unique({}, e)
    if not unique(els):
        return None

    def pick_merges(els, k):
        own = {c: i for i, e in enumerate(els) for c in e[1]}
        order = sorted(range(len(els)), key=lambda i: (not below(els[i]), len(els[i][1]), rng.random()))
        used, out = set(), []
        for i in order:
            if len(out) >= k:
                break
            if i in used:
                continue
            ea = els[i]
            nb = sorted(
                {own[j] for c in ea[1] for j in NB[c]} - {i} - used, key=lambda j: (len(els[j][1]), rng.random())
            )
            for j in nb:
                eb = els[j]
                if {sol[x] for x in ea[1]} & {sol[x] for x in eb[1]}:
                    continue
                if not within_max(len(ea[1]) + len(eb[1]), ea[2] + eb[2]):
                    continue
                out.append((i, j))
                used |= {i, j}
                break
        return out

    def apply(els, ms):
        drop = {x for m in ms for x in m}
        return [e for i, e in enumerate(els) if i not in drop] + [
            ("cage", tuple(sorted(els[i][1] + els[j][1])), els[i][2] + els[j][2]) for i, j in ms
        ]

    def try_batch(els, ms):
        if not ms:
            return els
        trial = apply(els, ms)
        if unique(trial):
            return trial
        if len(ms) == 1:
            return els
        h = len(ms) // 2
        els2 = try_batch(els, ms[:h])
        return try_batch(els, ms[h:]) if els2 is els else els2  # indices shift once the first half applied

    batch, stall = 8, 0
    while len(els) > n_cages and stall < 30:
        if deadline and _t.time() > deadline:
            return None
        k = min(batch, len(els) - n_cages)
        ms = pick_merges(els, 3 * k)
        ms = [m for m in ms if not orc.refuted({}, apply(els, [m]))][:k]
        if not ms:
            stall += 1
            continue
        new_ = try_batch(els, ms)
        if new_ is els:
            stall += 1
            batch = max(1, batch // 2)
        else:
            stall, els = 0, new_
            batch = min(16, batch * 2)
        _log.debug("%d cages (CP-SAT calls %d, cache rejections %d)", len(els), orc.calls, orc.hits)
    if len(els) != n_cages or any(len(e[1]) == 1 or below(e) for e in els):
        return None
    return sol, {}, els


def full_kropki(b, rng, time_limit=20.0):
    """zero-given full kropki (every consecutive pair has a white dot, every 1:2 pair a black one, no dot = neither):
    the grid fixes the whole puzzle, so draw grids until the dot set is unique."""
    sol = b.solution(rng)
    dots, none_ = EL.all_dots(b, sol)
    els = dots + [("notdots", p, None) for p in none_]
    orc = Oracle(b, sol, time_limit=time_limit)
    return (sol, {}, els) if orc.unique({}, els) else None


def min_kropki(b, rng, time_limit=20.0, chk=None):
    """zero-given kropki without the negative rule: all true dots, then remove dots while the puzzle stays unique
    (CP-SAT oracle; with `chk`, while it stays solvable within the checker's cap) -> a minimal dot set."""
    sol = b.solution(rng)
    els, _ = EL.all_dots(b, sol)
    orc = Oracle(b, sol, time_limit=time_limit)
    ok = (lambda e: chk.ok({}, e)) if chk is not None else (lambda e: orc.unique({}, e))
    if not ok(els):
        return None
    for e in sorted(els, key=lambda _: rng.random()):
        trial = [x for x in els if x != e]
        if chk is None and orc.refuted({}, trial):
            continue
        if ok(trial):
            els = trial
    return sol, {}, els


def pull(b, sol, givens, els, chk, low, rng, symmetry=None, max_givens=None):
    """approach the band boundary from above: start from a puzzle the lower-band solve (`low`) can't finish (e.g. dug
    with every technique allowed), then put givens back (random order, whole symmetry orbits), skipping any that would let
    `low` finish, until the capped solve (`chk`) finishes. The result needs the cap's techniques (by the engine) and
    solves within the cap. Elements that became unnecessary are dropped. Returns (givens, els) or None."""
    givens = dict(givens)
    if low.ok(givens, els):
        return None
    seen, orbits = set(), []
    for i in sorted((c for c in range(b.N) if c not in givens), key=lambda _: rng.random()):
        if i not in seen:
            o = b.orbit(i, symmetry)
            seen.update(o)
            orbits.append(o)
    for o in orbits:
        if chk.ok(givens, els):
            break
        g2 = dict(givens)
        g2.update({c: sol[c] for c in o})
        if max_givens is not None and len(g2) > max_givens:
            return None
        if not low.ok(g2, els):
            givens = g2
    else:
        if not chk.ok(givens, els):
            return None
    for e in list(els):
        rest_ = [x for x in els if x != e]
        if chk.ok(givens, rest_) and not low.ok(givens, rest_):
            els = rest_
    return givens, els
