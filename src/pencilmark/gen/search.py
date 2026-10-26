"""Search procedures.

All functions take a Board, a random.Random and return (solution, givens {cell: digit}, elements) or None.
"""
from __future__ import annotations

from . import elements as EL
from .checks import Oracle


def dig(b, kinds, rng, chk, sol=None, min_givens=0, seeds=None, max_els=10 ** 6, symmetry=None, fixed=None, blocked=(),
        pool_tries=25, caps=None, dense=()):
    """givens-digging with elements added on demand.

    1. `seeds` {kind: count} elements are placed first (disjoint) and their cells, then their peers, are emptied first,
       so they tend to end up required;
    2. the remaining givens are removed in random order (whole symmetry orbits at a time) down to `min_givens`; when a
       removal breaks solvability (chk: band-capped logic), the most informative element of `kinds` through that cell
       that restores it is added (if any), else the givens stay;
    3. prune: every element the puzzle stays solvable without is dropped (no decorative elements).
    fixed {cell: True (stays given) / False (stays empty)}; blocked cells take no elements. kinds / seeds may name element
    classes (kropki_black, x, odd, ...); caps {class: max} limits how many of a class are added. dense: 2-cell / 1-cell
    classes seeded with EVERY instance true in the solution before digging (few-givens targets); pruning then removes the
    ones the puzzle doesn't need."""
    fixed = dict(fixed or {})
    sol = sol or b.solution(rng)
    givens = {i: sol[i] for i in range(b.N) if fixed.get(i, True)}
    els, used = [], set(blocked)
    caps = dict(caps or {})
    room = lambda e: all(sum(1 for x in els if EL.in_class(x, k)) < m for k, m in caps.items() if m is not None and EL.in_class(e, k))
    for kind, cnt in (seeds or {}).items():
        for _ in range(cnt):
            for _try in range(40):
                g_ = [e for e in EL.grow(b, EL.base_kind(kind), sol, rng.randrange(b.N), used, rng, n=8)
                      if used.isdisjoint(e[1]) and EL.in_class(e, kind)]
                if g_:
                    els.append(g_[0])
                    used |= set(g_[0][1])
                    break
    for kind in dense:
        bk = EL.base_kind(kind)
        if bk not in ("kropki", "xv", "parity"):
            continue
        seen = {x[1] for x in els}
        for i in range(b.N):
            for e in EL.grow(b, bk, sol, i, set(blocked), rng):
                if EL.in_class(e, kind) and e[1] not in seen and (bk != "parity" or i not in used):
                    els.append(e); seen.add(e[1])
    el_cells = used - set(blocked)
    peers = {j for c in el_cells for j in b.peers[c]} - el_cells
    rest = [i for i in range(b.N) if i not in el_cells and i not in peers]
    order = sorted(el_cells, key=lambda _: rng.random()) + sorted(peers, key=lambda _: rng.random()) + \
        sorted(rest, key=lambda _: rng.random())
    order = [i for i in order if i not in fixed]
    if not chk.ok(givens, els):
        return None
    done = set()
    for i in order:
        if len(givens) <= min_givens:
            break
        if i in done:
            continue
        orb = [c for c in b.orbit(i, symmetry) if c in givens and c not in fixed]
        done.update(b.orbit(i, symmetry))
        if not orb or len(givens) - len(orb) < min_givens:
            continue
        removed = {c: givens.pop(c) for c in orb}
        if chk.ok(givens, els):
            continue
        restored = False
        if kinds and len(els) < max_els:
            taken = {c for x in els for c in x[1]} | set(blocked)      # elements never share cells
            cand = [] if i in taken else [e for k in kinds for e in EL.grow(b, EL.base_kind(k), sol, i, taken, rng)
                                          if EL.in_class(e, k) and room(e)]
            cand.sort(key=lambda e: (EL.ncomb(b.n, len(e[1]), e[2]) if e[0] == "cage" else 0, rng.random()))
            for e in cand[:pool_tries]:
                if chk.ok(givens, els + [e]):
                    els.append(e)
                    restored = True
                    break
        if not restored:
            givens.update(removed)
    mins = {k: n for k, n in (seeds or {}).items() if n}
    for e in list(els):                                 # prune decorative elements (never below a class's minimum)
        rest_ = [x for x in els if x != e]
        if any(EL.in_class(e, k) and sum(1 for x in rest_ if EL.in_class(x, k)) < n for k, n in mins.items()):
            continue
        if chk.ok(givens, rest_):
            els = rest_
    return sol, givens, els


def partition(b, rng, chk, n_givens=0, min_els=0, cover=True):
    """killer with few / no givens: tile the grid with 2-cell informative cages, keep `n_givens` random givens, then merge
    neighbouring cages (distinct digits, <= 6 cells) -- or delete cages if cover=False -- while the puzzle stays solvable
    within the checker's cap."""
    sol = b.solution(rng)
    NB = b.nb
    owner, els = {}, []
    cells = list(range(b.N))
    rng.shuffle(cells)
    for c in cells:
        if c in owner:
            continue
        opts = [j for j in NB[c] if j not in owner and sol[j] != sol[c]]
        if not opts:
            els.append(("cage", (c,), sol[c]))
            owner[c] = 1
            continue
        j = min(opts, key=lambda j: (EL.ncomb(b.n, 2, sol[c] + sol[j]), rng.random()))
        els.append(("cage", tuple(sorted((c, j))), sol[c] + sol[j]))
        owner[c] = owner[j] = 1
    for e in [e for e in els if len(e[1]) == 1]:      # absorb single cells into a neighbouring cage
        c = e[1][0]
        hosts = [x for x in els if x is not e and len(x[1]) < 4 and any(j in x[1] for j in NB[c])
                 and sol[c] not in {sol[y] for y in x[1]}]
        if not hosts:
            return None
        h = min(hosts, key=lambda x: (EL.ncomb(b.n, len(x[1]) + 1, x[2] + sol[c]), rng.random()))
        els[els.index(h)] = ("cage", tuple(sorted(h[1] + (c,))), h[2] + sol[c])
        els.remove(e)
    givens = {i: sol[i] for i in sorted(range(b.N), key=lambda _: rng.random())[:n_givens]}
    if not chk.ok(givens, els):
        return None
    for _ in range(400):
        changed = False
        order = list(range(len(els)))
        rng.shuffle(order)
        for a in order:
            if a >= len(els):
                continue
            ea = els[a]
            nbrs = {next(k for k, e in enumerate(els) if j in e[1]) for c in ea[1] for j in NB[c]} - {a}
            moves = []
            for k in sorted(nbrs):
                eb = els[k]
                if {sol[x] for x in ea[1]} & {sol[x] for x in eb[1]} or len(ea[1]) + len(eb[1]) > min(6, b.n):
                    continue
                m = ("cage", tuple(sorted(ea[1] + eb[1])), ea[2] + eb[2])
                moves.append([e for i_, e in enumerate(els) if i_ not in (a, k)] + [m])
            if not cover:
                moves.append([e for i_, e in enumerate(els) if i_ != a])
            rng.shuffle(moves)
            for cand in moves[:4]:
                if chk.ok(givens, cand):
                    els = cand
                    changed = True
                    break
        if not changed:
            break
    if any(len(e[1]) == 1 for e in els) or len(els) < min_els:     # a 1-cell cage is a given in disguise
        return None
    return sol, givens, els


def cage_count(b, n_cages, rng, time_limit=30.0, deadline=None, log=None):
    """killer with EXACTLY n_cages cages and no givens: tile with 2-cell cages, then merge neighbouring cages (distinct
    digits) in batches while the puzzle stays UNIQUE (CP-SAT oracle with a counterexample cache; a failed batch is
    bisected). No human-solvability cap: the card grades whatever results."""
    import time as _t
    sol = b.solution(rng)
    NB = b.nb
    owner, els = {}, []
    cells = list(range(b.N))
    rng.shuffle(cells)
    for c in cells:
        if c in owner:
            continue
        opts = [j for j in NB[c] if j not in owner and sol[j] != sol[c]]
        if not opts:
            els.append(("cage", (c,), sol[c]))
            owner[c] = 1
            continue
        j = min(opts, key=lambda j: (EL.ncomb(b.n, 2, sol[c] + sol[j]), rng.random()))
        els.append(("cage", tuple(sorted((c, j))), sol[c] + sol[j]))
        owner[c] = owner[j] = 1
    orc = Oracle(b, sol, time_limit=time_limit)
    unique = lambda e: orc.unique({}, e)
    if not unique(els):
        return None

    def pick_merges(els, k):
        own = {c: i for i, e in enumerate(els) for c in e[1]}
        order = sorted(range(len(els)), key=lambda i: (len(els[i][1]), rng.random()))
        used, out = set(), []
        for i in order:
            if len(out) >= k:
                break
            if i in used:
                continue
            ea = els[i]
            nb = sorted({own[j] for c in ea[1] for j in NB[c]} - {i} - used, key=lambda j: (len(els[j][1]), rng.random()))
            for j in nb:
                eb = els[j]
                if {sol[x] for x in ea[1]} & {sol[x] for x in eb[1]}:
                    continue
                out.append((i, j))
                used |= {i, j}
                break
        return out

    def apply(els, ms):
        drop = {x for m in ms for x in m}
        return [e for i, e in enumerate(els) if i not in drop] + \
               [("cage", tuple(sorted(els[i][1] + els[j][1])), els[i][2] + els[j][2]) for i, j in ms]

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
        return try_batch(els, ms[h:]) if els2 is els else els2    # indices shift once the first half applied

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
        if log:
            log(f"  {len(els)} cages (CP-SAT calls {orc.calls}, cache rejections {orc.hits})")
    if len(els) != n_cages or any(len(e[1]) == 1 for e in els):
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

