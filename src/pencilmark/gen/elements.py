"""Rule elements a generated puzzle can carry, true in a given solution grid.

An element is a tuple (kind, cells, extra):
  ("cage", sorted cells, total)          killer cage, distinct digits
  ("thermo", path, None)                 strictly increasing from the bulb (path[0])
  ("slow_thermo", path, None)            non-decreasing from the bulb (path[0])
  ("whisper", path, None)                German whisper, neighbors differ by >= whisper_gap(n)
  ("renban", path, None)                 a set of consecutive digits, any order
  ("between", path, None)                interior digits strictly between the two end circles
  ("entropic", path, None)               every 3 consecutive cells: a low, a middle and a high digit (digit_third)
  ("modular", path, None)                every 3 consecutive cells: three different remainders mod 3
  ("parity_line", path, None)            neighbors on the line alternate odd / even (the format's line kind parity)
  ("palindrome", path, None)             reads the same from both ends (odd length, built from its center)
  ("zipper", path, None)                 cells equally far from the center sum to the center digit (odd length)
  ("region_sum", path, None)             the same sum in each box it passes through (two boxes or more)
  ("lockout", path, None)                ends differ by >= lockout_gap(n), the other digits outside their range
  ("double_arrow", path, None)           the two ends sum to the digits between them (5+ cells: shorter is a zipper)
  ("sandwich", row / column from the clue, total)    digits between the 1 and the n sum to total
  ("xsum", row / column from the clue, total)        the first X cells sum to total, X = the first digit
  ("skyscraper", row / column from the clue, count)  cells higher than every earlier one
  ("little_killer", diagonal from the clue, total)   the diagonal's digits sum to total (they may repeat)
  ("quadruple", (TL, TR, BL, BR), digits)            the 2 x 2 block holds these digits (a corner circle)
  ("mathrax", (TL, TR, BL, BR), (op, value))         both diagonals combine to value by op (+ - x /), or op even / odd
  ("arrow", (circle,) + shaft, None)     shaft digits sum to the circle digit
  ("kropki", (i, j), "white" | "black")  consecutive / 1:2 ratio
  ("xv", (i, j), "X" | "V")              sum 10 / sum 5
  ("parity", (i,), 1 | 0)                odd / even cell (graphical rule, not candidates)
"""

from __future__ import annotations

import math
from itertools import combinations

from .. import puzzle_json as PJ

KINDS = ("cage", "thermo", "slow_thermo", "whisper", "renban", "between", "entropic", "modular", "parity_line",
         "palindrome", "zipper", "region_sum", "lockout", "double_arrow", "arrow", "kropki", "xv", "parity", "sandwich",
         "xsum", "skyscraper", "little_killer", "quadruple", "mathrax")  # fmt: skip
OUTSIDE = ("sandwich", "xsum", "skyscraper", "little_killer")  # clues outside the grid on a whole row, column, diagonal
CORNER = ("quadruple", "mathrax")  # clues on a corner: a 2 x 2 block
# elements that may share cells with their own kind (never the same edge, line or block)
SHARED = ("kropki", "xv", *OUTSIDE, *CORNER)
ALIASES = {
    "killer": "cage",
    "cages": "cage",
    "evenodd": "parity",
    "odd_even": "parity",
    "oddeven": "parity",
    "german_whisper": "whisper",
    "whispers": "whisper",
    "thermometer": "thermo",
    "thermos": "thermo",
    "arrows": "arrow",
    "dots": "kropki",
}


# element classes: a kind, or one color / letter / parity of it (counted separately in Spec.elements)
CLASSES = {
    "kropki_white": ("kropki", "white"),
    "kropki_black": ("kropki", "black"),
    "x": ("xv", "X"),
    "v": ("xv", "V"),
    "odd": ("parity", 1),
    "even": ("parity", 0),
}
CLASS_ALIASES = {
    "white_kropki": "kropki_white",
    "black_kropki": "kropki_black",
    "white": "kropki_white",
    "black": "kropki_black",
}


def norm_kind(k):
    """a kind or an element class name -> its canonical name"""
    k = str(k).strip().lower()
    k = ALIASES.get(k, CLASS_ALIASES.get(k, k))
    if k not in KINDS and k not in CLASSES:
        raise ValueError(f"unknown element kind {k!r} (known: {', '.join(KINDS + tuple(CLASSES))})")
    return k


def base_kind(k):
    return CLASSES[k][0] if k in CLASSES else k


def element_class(e):
    """the class of an element: its color / letter / parity class where one exists, else its kind"""
    for name, (kind, extra) in CLASSES.items():
        if e[0] == kind and e[2] == extra:
            return name
    return e[0]


def in_class(e, k):
    return e[0] == k or element_class(e) == k


def digit_third(v, n):
    """the entropic group of digit v on an n-digit board (0 low, 1 middle, 2 high), as the engine splits them"""
    return (v - 1) * 3 // n if n % 3 == 0 else (v - 1) // 3


def lockout_gap(n):
    """lockout: how far apart the ends must be (4 on 9 x 9, the format's default; about half the range otherwise)"""
    return 4 if n == 9 else max(1, (n - 1) // 2)


def line_holds(b, kind, cells, ds):
    """does a line of a kind checked as a whole (CENTERED, WHOLE) hold for these digits?"""
    if kind == "palindrome":
        return ds == ds[::-1]
    if kind == "zipper":
        m = len(ds) // 2
        return len(ds) % 2 == 1 and all(ds[i] + ds[-1 - i] == ds[m] for i in range(m))
    if kind == "region_sum":
        sums, prev = [], None
        for c, d in zip(cells, ds):
            if b.box_of[c] != prev:
                sums.append(0)
                prev = b.box_of[c]
            sums[-1] += d
        return len(sums) >= 2 and len(set(sums)) == 1
    if kind == "lockout":
        lo, hi = sorted((ds[0], ds[-1]))
        return hi - lo >= lockout_gap(b.n) and all(d < lo or d > hi for d in ds[1:-1])
    if kind == "double_arrow":
        return ds[0] + ds[-1] == sum(ds[1:-1])
    raise ValueError(kind)


def outside_value(kind, ds):
    """the clue an outside element shows for its digits, read from the clue inwards"""
    if kind == "sandwich":
        i, j = sorted((ds.index(1), ds.index(max(ds))))
        return sum(ds[i + 1 : j])
    if kind == "xsum":
        return sum(ds[: ds[0]])
    if kind == "skyscraper":
        return sum(1 for i, d in enumerate(ds) if all(d > e for e in ds[:i]))
    return sum(ds)  # little killer


def blocks(b, start):
    """the 2 x 2 blocks (TL, TR, BL, BR) holding `start`"""
    r0, c0 = b.coords[start]
    out = []
    for r, c in ((r0 - 1, c0 - 1), (r0 - 1, c0), (r0, c0 - 1), (r0, c0)):
        blk = [b.cid.get(x) for x in ((r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1))]
        if None not in blk:
            out.append(tuple(blk))
    return out


def mathrax_clues(ds):
    """the mathrax clues true of a block's digits (TL, TR, BL, BR): both diagonals combine to the same value"""
    a, b_, c, d = ds
    out = []
    if a + d == b_ + c:
        out.append(("+", a + d))
    if abs(a - d) == abs(b_ - c):
        out.append(("-", abs(a - d)))
    if a * d == b_ * c:
        out.append(("x", a * d))
    lo1, hi1, lo2, hi2 = min(a, d), max(a, d), min(b_, c), max(b_, c)
    if hi1 % lo1 == 0 and hi2 % lo2 == 0 and hi1 // lo1 == hi2 // lo2:
        out.append(("/", hi1 // lo1))
    if len({x % 2 for x in ds}) == 1:
        out.append(("odd" if a % 2 else "even", None))
    return out


def corner_holds(kind, ds, x):
    if kind == "quadruple":
        return all(ds.count(v) >= list(x).count(v) for v in set(x))
    return x in mathrax_clues(ds)


def outside_lines(b, kind, start):
    """the lines through `start` an outside clue of `kind` reads, each from the clue inwards: the row and column from
    both ends, or for a little killer the two diagonals from both ends (2 cells or more)"""
    r0, c0 = b.coords[start]
    steps = ((1, 1), (1, -1)) if kind == "little_killer" else ((0, 1), (1, 0))
    out = []
    for dr, dc in steps:
        r, c = r0, c0
        while (r - dr, c - dc) in b.cid:
            r, c = r - dr, c - dc
        line = []
        while (r, c) in b.cid:
            line.append(b.cid[(r, c)])
            r, c = r + dr, c + dc
        if len(line) >= 2:
            out += [tuple(line), tuple(reversed(line))]
    return out


def whisper_gap(n):
    """German-whisper gap: 5 on 9x9 (standard); about half the digit range otherwise."""
    return 5 if n == 9 else (n + 1) // 2


_NCOMB = {}


def ncomb(n, size, total):
    """number of digit sets of `size` from 1..n summing to `total` (1 = the cage's digit set is fully determined)."""
    key = (n, size, total)
    if key not in _NCOMB:
        _NCOMB[key] = sum(1 for c in combinations(range(1, n + 1), size) if sum(c) == total)
    return _NCOMB[key]


LENGTHS = {"cage": (2, 5), "thermo": (2, 6), "slow_thermo": (2, 6), "whisper": (2, 7), "renban": (2, 5), "between": (3, 6),
           "entropic": (3, 7), "modular": (3, 7), "parity_line": (2, 7), "palindrome": (3, 7), "zipper": (3, 7),
           "region_sum": (3, 8), "lockout": (3, 6), "double_arrow": (5, 7), "arrow": (1, 4)}  # fmt: skip
# lines always grown by _walk (each step checks the cells before it)
WALKED = ("slow_thermo", "entropic", "modular", "parity_line")
CENTRED = ("palindrome", "zipper")  # grown from the center cell, one cell at each end per step
WHOLE = ("region_sum", "lockout", "double_arrow")  # a random walk, kept at its longest prefix that holds


def length_of(e):
    """an element's length as a template counts it: cells of a cage or line, the shaft of an arrow"""
    return len(e[1]) - 1 if e[0] == "arrow" else len(e[1])


def turns(b, cells):
    """direction changes along a line's cells (a diagonal step after an orthogonal one is a turn)"""
    rc = [b.coords[c] for c in cells]
    steps = [(y[0] - x[0], y[1] - x[1]) for x, y in zip(rc, rc[1:])]
    return sum(1 for s, t in zip(steps, steps[1:]) if s != t)


def fits(e, shape, b=None):
    """does the element meet its template's shape limits? shape {kind: {"length": (lo, hi), "sum": (lo, hi), "turns":
    (lo, hi)}}; turns are checked when the board b is given"""
    lim = (shape or {}).get(e[0])
    if not lim:
        return True
    lo, hi = lim.get("length", (None, None))
    if (lo is not None and length_of(e) < lo) or (hi is not None and length_of(e) > hi):
        return False
    tlo, thi = lim.get("turns", (None, None))
    if b is not None and (tlo is not None or thi is not None):
        t = turns(b, e[1])
        if (tlo is not None and t < tlo) or (thi is not None and t > thi):
            return False
    slo, shi = lim.get("sum", (None, None))
    return e[0] != "cage" or ((slo is None or e[2] >= slo) and (shi is None or e[2] <= shi))


# how a generated line chooses its next cell (king steps): human lines (development set, 17,838 inner cells) turn at
# 54% of their inner cells and take 31% of their steps diagonally; 1.2 drew orthogonal steps only and turned at about
# 67%. An orthogonal step weighs ORTHO, a diagonal one 1, and going straight on is STRAIGHT times as likely; on free
# random walks these give 55% turns and 32% diagonal steps
ORTHO, STRAIGHT = 1.5, 5.0
# lines whose digits the solution fixes first bend to fit them (a thermo must climb): of the candidates through a
# cell, a turn counts as TURN_COST cells less length and a diagonal step as DIAG_COST
TURN_COST, DIAG_COST = 1.5, 0.3


def _step_weight(b, prev, cur, nxt):
    """the weight of drawing a line on from cur to nxt (prev: the cell before cur, or None)"""
    (r1, c1), (r2, c2) = b.coords[cur], b.coords[nxt]
    w = ORTHO if r1 == r2 or c1 == c2 else 1.0
    if prev is not None:
        r0, c0 = b.coords[prev]
        if (r2 - r1, c2 - c1) == (r1 - r0, c1 - c0):
            w *= STRAIGHT
    return w


def _by_hand(rng, items, weight):
    """items in a random order drawn by weight (heavier first more often): Efraimidis-Spirakis keys, largest first"""
    return sorted(items, key=lambda x: math.log(1.0 - rng.random()) / weight(x), reverse=True)


def diagonal_steps(b, cells):
    """the diagonal steps of a line, as ("x", a, b) markers (a < b): a line that would cross one is refused"""
    out = set()
    for a, c in zip(cells, cells[1:]):
        (r1, c1), (r2, c2) = b.coords[a], b.coords[c]
        if r1 != r2 and c1 != c2:
            out.add(("x", min(a, c), max(a, c)))
    return out


def _free_steps(b, path, cur, taken):
    """cells a line through `path` may step to from its end `cur`: king steps, not on the line or taken, and a
    diagonal step never crossing a diagonal step of the line itself or of a line of the same kind (in taken)"""
    out = []
    for j in b.nb8[cur]:
        if j in path or j in taken:
            continue
        (r1, c1), (r2, c2) = b.coords[cur], b.coords[j]
        if r1 != r2 and c1 != c2:
            u, v = b.cid.get((r1, c2)), b.cid.get((r2, c1))
            if u is not None and v is not None:
                x = ("x", min(u, v), max(u, v))
                if x in taken or x in diagonal_steps(b, path) or x in diagonal_steps(b, path[::-1]):
                    continue
        out.append(j)
    return out


def _line_step(b, rng, path, cands):
    """the next cell of a line growing at its end (cands: free cells next to path[-1])"""
    prev = path[-2] if len(path) > 1 else None
    return _by_hand(rng, cands, lambda j: _step_weight(b, prev, path[-1], j))[0]


def grow(b, kind, sol, start, taken, rng, n=40, shape=None):
    """elements of `kind` through cell `start`, disjoint from `taken`, true in the solution and within the template's
    shape limits (`fits`); most informative first."""
    NB = b.nb
    out = set()
    lim = (shape or {}).get(kind) or {}
    lo, hi = LENGTHS.get(kind, (1, 1))
    want_lo, want_hi = lim.get("length", (None, None))
    if want_lo is not None:  # at least this long; without a maximum, aim a little beyond it
        lo, hi = want_lo, max(hi, want_lo + 4)
    if want_hi is not None:
        hi = want_hi
    if kind == "cage":
        hi = min(hi, b.n)
    smax = lim.get("sum", (None, None))[1]
    if kind == "parity":
        return [("parity", (start,), sol[start] % 2)] if start not in taken else []
    if kind in OUTSIDE:  # the clue's value is read off the solution; the line must not reach a blocked cell
        lines = [ln for ln in outside_lines(b, kind, start) if taken.isdisjoint(ln)]
        return sorted(_stable((kind, ln, outside_value(kind, [sol[c] for c in ln])) for ln in lines),
                      key=lambda e: (rng.random(),))  # fmt: skip
    if kind in CORNER:  # every true clue on each block through `start` (a quadruple: all four digits, or three)
        for blk in blocks(b, start):
            if not taken.isdisjoint(blk):
                continue
            ds = [sol[c] for c in blk]
            if kind == "quadruple":
                out.add(("quadruple", blk, tuple(sorted(ds))))
                out.add(("quadruple", blk, tuple(sorted(rng.sample(ds, 3)))))
            else:
                out.update(("mathrax", blk, m) for m in mathrax_clues(ds))
        return sorted(_stable(out), key=lambda e: (rng.random(),))
    if kind in ("kropki", "xv"):  # 2-cell markers true in the solution
        for j in NB[start]:
            if j in taken:
                continue
            a_, b_ = sol[start], sol[j]
            pair = tuple(sorted((start, j)))
            if kind == "kropki" and abs(a_ - b_) == 1:
                out.add(("kropki", pair, "white"))
            if kind == "kropki" and (a_ == 2 * b_ or b_ == 2 * a_):
                out.add(("kropki", pair, "black"))
            if kind == "xv" and a_ + b_ in (5, 10):
                out.add(("xv", pair, "X" if a_ + b_ == 10 else "V"))
        return sorted(_stable(out), key=lambda e: (rng.random(),))
    for _ in range(n * 4):
        if len(out) >= n:
            break
        if kind == "between":
            path = [start]
            for _s in range(rng.randint(lo, hi) - 1):
                nxt = _free_steps(b, path, path[-1], taken)
                if not nxt:
                    break
                path.append(_line_step(b, rng, path, nxt))
            if len(path) < max(3, lo):
                continue
            a_, z_ = sorted((sol[path[0]], sol[path[-1]]))
            if all(a_ < sol[c] < z_ for c in path[1:-1]):
                out.add(("between", tuple(path), None))
            continue
        if kind == "arrow":
            circ = start if rng.random() < 0.5 else rng.choice([j for j in NB[start] if j not in taken] or [start])
            shaft, tot, cur = [], 0, circ
            while tot < sol[circ] and len(shaft) < hi:
                nxt = [
                    j for j in NB[cur] if j not in taken and j != circ and j not in shaft and tot + sol[j] <= sol[circ]
                ]
                if not nxt:
                    break
                cur = rng.choice(nxt)
                shaft.append(cur)
                tot += sol[cur]
            if (
                lo <= len(shaft)
                and shaft
                and tot == sol[circ]
                and (start == circ or start in shaft)
                and circ not in taken
            ):
                out.add(("arrow", (circ,) + tuple(shaft), None))
            continue
        if kind in CENTRED:
            path = _centred(b, kind, sol, start, taken, rng, rng.randint(lo, hi))
            if path and len(path) >= lo:
                out.add((kind, tuple(path), None))
            continue
        if kind in WHOLE:
            path = [start]
            for _s in range(rng.randint(lo, hi) - 1):
                nxt = _free_steps(b, path, path[-1], taken)
                if not nxt:
                    break
                path.append(_line_step(b, rng, path, nxt))
            while len(path) >= lo and not line_holds(b, kind, path, [sol[c] for c in path]):
                path.pop()
            if len(path) >= lo:
                out.add((kind, tuple(path), None))
            continue
        if kind in WALKED or (want_lo is not None and kind in ("thermo", "whisper", "renban")):  # a backtracking walk
            path = _walk(b, kind, sol, start, taken, rng, rng.randint(lo, hi))
            if path and len(path) >= lo:
                out.add((kind, tuple(path), None))
            continue
        path = [start]
        target = hi if smax is not None else rng.randint(lo, hi)  # a cage with a sum grows until it reaches it
        while len(path) < target:
            if smax is not None and len(path) >= lo and fits(("cage", path, sum(sol[c] for c in path)), shape):
                break
            ends = [path[0], path[-1]] if kind != "cage" else path
            opts = []
            for e_ in ends:
                for j in NB[e_] if kind == "cage" else _free_steps(b, path, e_, taken):
                    if j in path or j in taken:
                        continue
                    if kind in ("cage", "renban") and sol[j] in {sol[x] for x in path}:
                        continue
                    if kind == "cage" and smax is not None and sum(sol[x] for x in path) + sol[j] > smax:
                        continue
                    if kind == "thermo":
                        if e_ == path[-1] and sol[j] > sol[path[-1]]:
                            opts.append((j, 1))
                        elif e_ == path[0] and sol[j] < sol[path[0]]:
                            opts.append((j, 0))
                        continue
                    if kind == "whisper":
                        if abs(sol[j] - sol[e_]) >= whisper_gap(b.n):
                            opts.append((j, 1 if e_ == path[-1] else 0))
                        continue
                    opts.append((j, 1 if e_ == path[-1] else 0))  # grow at the end it touches (a renban is a line)
            if not opts:
                break
            if kind == "cage":
                j, back = rng.choice(opts)
            else:  # a line grows at either end, drawn as a hand would (_step_weight)
                end = lambda o: (path[-2] if o[1] else path[1]) if len(path) > 1 else None  # noqa: E731
                j, back = _by_hand(rng, opts, lambda o: _step_weight(b, end(o), path[-1] if o[1] else path[0], o[0]))[0]
            path = path + [j] if back else [j] + path
        if len(path) < lo:
            continue
        if kind == "renban":
            ds = sorted(sol[c] for c in path)
            if ds[-1] - ds[0] != len(ds) - 1:
                continue
        if kind == "cage":
            out.add(("cage", tuple(sorted(path)), sum(sol[c] for c in path)))
        else:
            out.add((kind, tuple(path), None))

    def info(e):
        if e[0] == "cage":
            return (ncomb(b.n, len(e[1]), e[2]), len(e[1]))
        return (TURN_COST * turns(b, e[1]) + DIAG_COST * len(diagonal_steps(b, e[1])) - len(e[1]),)  # longer first

    return sorted(_stable(e for e in out if fits(e, shape, b)), key=lambda e: (info(e), rng.random()))


def _centred(b, kind, sol, start, taken, rng, target):
    """a palindrome or zipper around `start`: each step adds a cell at both ends that keep it true in the solution"""
    path = [start]
    while len(path) + 2 <= target:
        pairs = [
            (j, k)
            for j in _free_steps(b, path, path[0], taken)
            for k in _free_steps(b, path, path[-1], taken)
            if j != k and j not in path and k not in path and j not in taken and k not in taken
            and (sol[j] == sol[k] if kind == "palindrome" else sol[j] + sol[k] == sol[start])
        ]  # fmt: skip
        if not pairs:
            break
        p0, p1 = (path[1], path[-2]) if len(path) > 1 else (None, None)

        def both(x, p0=p0, p1=p1, path=path):  # the two ends are drawn on together
            return _step_weight(b, p0, path[0], x[0]) * _step_weight(b, p1, path[-1], x[1])

        j, k = _by_hand(rng, pairs, both)[0]
        path = [j] + path + [k]
    return path


def _walk(b, kind, sol, start, taken, rng, target, budget=None):
    """a line of `kind` from `start` (its bulb for a thermo), true in the solution, by randomized depth-first search:
    the first path of `target` cells, else the longest found within `budget` steps"""
    gap = whisper_gap(b.n)
    budget = budget or 40 * target * target  # a long line needs a deeper search (25 cells: 25,000 steps)
    best, steps = [start], 0

    def ok(path, j):
        a, c = sol[path[-1]], sol[j]
        if kind == "thermo":
            return c > a
        if kind == "slow_thermo":
            return c >= a
        if kind == "parity_line":
            return c % 2 != a % 2
        if kind == "whisper":
            return abs(c - a) >= gap
        if kind in ("entropic", "modular"):  # the new cell and the two before it: three classes
            cls = (lambda v: digit_third(v, b.n)) if kind == "entropic" else (lambda v: v % 3)
            last = [cls(sol[x]) for x in path[-2:]] + [cls(c)]
            return len(set(last)) == len(last)
        ds = [sol[x] for x in path] + [c]  # renban: distinct digits that can still close up to a run of `target`
        return c not in ds[:-1] and max(ds) - min(ds) < target

    def dfs(path):
        nonlocal best, steps
        if len(path) > len(best):
            best = list(path)
        if len(path) >= target or steps > budget:
            return len(path) >= target
        steps += 1
        nxt = [j for j in _free_steps(b, path, path[-1], taken) if ok(path, j)]
        prev = path[-2] if len(path) > 1 else None
        nxt = _by_hand(rng, nxt, lambda j: _step_weight(b, prev, path[-1], j))  # tried as a hand would draw on
        return any(dfs(path + [j]) for j in nxt)

    if kind == "whisper" and not any(abs(sol[start] - sol[j]) >= gap for j in b.nb8[start]):
        return None
    dfs([start])
    if kind == "renban":  # the digits must form a run
        while len(best) > 1 and max(sol[x] for x in best) - min(sol[x] for x in best) != len(best) - 1:
            best.pop()
    return best


def planted_whisper(b, length, rng, tries=200):
    """(path, {cell: digit}) of a German whisper of `length` cells to build a grid around: a random self-avoiding path
    (fewest onward cells first) and digits alternating low / high, the gap kept, different within each house. Random
    grids rarely hold a whisper of more than about 20 cells (22 at most in 1,500 9 x 9 grids); a longer one is planted
    first and the grid completed around it. None if no path or digits were found."""
    gap = whisper_gap(b.n)
    for _ in range(tries):
        path = [rng.randrange(b.N)]
        while len(path) < length:
            nxt = [j for j in b.nb[path[-1]] if j not in path]
            if not nxt:
                break
            onward = lambda j: sum(1 for k in b.nb[j] if k not in path and k != j)
            nxt.sort(key=lambda j: (onward(j), rng.random()))
            path.append(nxt[0] if rng.random() < 0.8 else rng.choice(nxt))
        if len(path) < length:
            continue
        digits = {}

        def assign(k):
            if k == len(path):
                return True
            c = path[k]
            opts = [d for d in range(1, b.n + 1)
                    if (k == 0 or abs(d - digits[path[k - 1]]) >= gap)
                    and all(digits.get(j) != d for j in b.peers[c])]  # fmt: skip
            rng.shuffle(opts)
            for d in opts:
                digits[c] = d
                if assign(k + 1):
                    return True
                del digits[c]
            return False

        if assign(0):
            return path, digits
    return None


def _stable(out):
    """a set of elements in a fixed order, so the random keys drawn for them do not depend on string hashing"""
    return sorted(out, key=lambda e: (e[0], e[1], str(e[2])))


def satisfies(b, g, givens, els):
    """does the full grid g satisfy the givens and every element? (cheap check used against cached alternative
    solutions; houses always hold because alternatives are valid grids of the same board)."""
    for i, v in givens.items():
        if g[i] != v:
            return False
    wk = whisper_gap(b.n)
    for kind, cells, x in els:
        ds = [g[c] for c in cells]
        if kind == "cage":
            if sum(ds) != x or len(set(ds)) != len(ds):
                return False
        elif kind == "thermo":
            if any(a >= c for a, c in zip(ds, ds[1:])):
                return False
        elif kind == "slow_thermo":
            if any(a > c for a, c in zip(ds, ds[1:])):
                return False
        elif kind == "parity_line":
            if any(a % 2 == c % 2 for a, c in zip(ds, ds[1:])):
                return False
        elif kind in CENTRED or kind in WHOLE:
            if not line_holds(b, kind, cells, ds):
                return False
        elif kind in OUTSIDE:
            if outside_value(kind, ds) != x:
                return False
        elif kind in CORNER:
            if not corner_holds(kind, ds, x):
                return False
        elif kind in ("entropic", "modular"):
            cls = [digit_third(d, b.n) if kind == "entropic" else d % 3 for d in ds]
            if any(len(set(cls[i : i + 3])) < len(cls[i : i + 3]) for i in range(len(cls) - 1)):
                return False
        elif kind == "whisper":
            if any(abs(a - c) < wk for a, c in zip(ds, ds[1:])):
                return False
        elif kind == "renban":
            if len(set(ds)) != len(ds) or max(ds) - min(ds) != len(ds) - 1:
                return False
        elif kind == "kropki":
            a, c = ds
            if (x == "white" and abs(a - c) != 1) or (x == "black" and a != 2 * c and c != 2 * a):
                return False
        elif kind == "xv":
            if sum(ds) != (10 if x == "X" else 5):
                return False
        elif kind == "arrow":
            if sum(ds[1:]) != ds[0]:
                return False
        elif kind == "parity":
            if ds[0] % 2 != x:
                return False
        elif kind == "between":
            lo, hi = sorted((ds[0], ds[-1]))
            if not all(lo < d < hi for d in ds[1:-1]):
                return False
        elif kind == "notdots":  # full kropki's negative rule over the listed pairs
            a, c = ds
            if abs(a - c) == 1 or a == 2 * c or c == 2 * a:
                return False
    return True


def to_json(b, givens, els, sol=None, title=None):
    """puzzle JSON (pencilmark/puzzle_json format) for givens {cell: digit} and elements."""
    rc = b.rc
    d = {
        "digits": b.n,
        "box": f"{b.bh}x{b.bw}",
        "numbers": "".join(PJ._sym(givens[i]) if i in givens else "." for i in range(b.N)),
        "rules": [],
        "regions": [],
    }
    if getattr(b, "layout", None):  # a multi-grid layout: its grids imply the houses
        del d["box"]
        d["layout"] = b.layout
        # numbers row by row over the whole board, "." at gaps too: a layout that fills its bounding box (butterfly)
        # would otherwise be read row by row while written in the layout's cell order
        d["numbers"] = "".join(
            PJ._sym(givens[b.cid[(r, c)]]) if b.cid.get((r, c)) in givens else "."
            for r in range(b.rows)
            for c in range(b.cols)
        )
    extra = getattr(b, "extra_json", None)  # the request's locked rules
    if extra:
        d["regions"] += [dict(g) for g in extra["regions"]]
        d["rules"] += [dict(r) for r in extra["rules"]]
    none_pairs = []
    for kind, cells, x in els:
        if kind == "cage":
            d["regions"].append({"kind": "cage", "cells": [rc(c) for c in cells], "sum": x, "unique": True})
        elif kind == "whisper":
            d["rules"].append({"type": "line", "kind": kind, "k": whisper_gap(b.n), "cells": [rc(c) for c in cells]})
        elif kind == "parity_line":
            d["rules"].append({"type": "line", "kind": "parity", "cells": [rc(c) for c in cells]})
        elif kind == "lockout":
            d["rules"].append({"type": "line", "kind": kind, "k": lockout_gap(b.n), "cells": [rc(c) for c in cells]})
        elif kind in OUTSIDE:  # engine constraints, cells from the clue inwards (the writer reads the side off them)
            key = "count" if kind == "skyscraper" else "total"
            d["rules"].append({"type": kind, "cells": [rc(c) for c in cells], key: x})
        elif kind == "quadruple":
            d["rules"].append({"type": "quadruple", "cells": [rc(c) for c in cells], "digits": list(x)})
        elif kind == "mathrax":  # as the reader builds it: parity, or a pair table per diagonal (TL-BR, then TR-BL)
            op, v = x
            if v is None:
                d["rules"].append({"type": "parity", "parity": op, "cells": [rc(c) for c in cells]})
            else:
                ok = {"+": lambda p, q: p + q == v, "-": lambda p, q: abs(p - q) == v, "x": lambda p, q: p * q == v,
                      "/": lambda p, q: max(p, q) == v * min(p, q)}[op]  # fmt: skip
                for i, j in ((cells[0], cells[3]), (cells[1], cells[2])):
                    same = j in b.peers[i]
                    digits = range(1, b.n + 1)
                    allowed = [[p, q] for p in digits for q in digits if (p != q or not same) and ok(p, q)]
                    d["rules"].append({"type": "table", "cells": [rc(i), rc(j)], "allowed": allowed})
        elif kind == "double_arrow":  # the engine's equal sum: ends against the cells between (written as the line)
            ends, mid = [rc(cells[0]), rc(cells[-1])], [rc(c) for c in cells[1:-1]]
            d["rules"].append({"type": "equal_sum", "segments": [ends, mid]})
        elif kind in ("thermo", "renban", "between", *WALKED, *CENTRED, "region_sum"):
            d["rules"].append({"type": "line", "kind": kind, "cells": [rc(c) for c in cells]})
        elif kind == "parity":  # graphical rule, not candidates
            d["rules"].append({"type": "parity", "parity": "odd" if x else "even", "cells": [rc(cells[0])]})
        elif kind == "kropki":
            d["rules"].append({"type": "kropki", "color": x, "cells": [rc(c) for c in cells]})
        elif kind == "xv":
            d["rules"].append({"type": "xv", "letter": x, "cells": [rc(c) for c in cells]})
        elif kind == "arrow":
            d["rules"].append({"type": "arrow", "circle": [rc(cells[0])], "line": [rc(c) for c in cells[1:]]})
        elif kind == "notdots":
            none_pairs.append(cells)
        else:
            raise ValueError(f"unknown element kind {kind!r}")
    if none_pairs:  # no dot = neither consecutive nor 1:2 (full kropki)
        cl = [[rc(i), rc(j)] for i, j in none_pairs]
        d["rules"].append({"type": "pairs", "rel": "notdiff", "params": [1], "cells": cl})
        d["rules"].append({"type": "pairs", "rel": "notratio", "params": [2], "cells": cl})
    if not d["regions"]:
        del d["regions"]
    if not d["rules"]:
        del d["rules"]
    if sol:
        d["solution"] = "".join(PJ._sym(v) for v in sol)
    if title:
        d["meta"] = {"title": title}
    return d


def all_dots(b, sol):
    """every kropki dot true in the solution, and the dot-free pairs (for the full-kropki negative rule)."""
    dots, none_ = [], []
    for i, j in b.edges:
        u, v = sol[i], sol[j]
        if abs(u - v) == 1:
            dots.append(("kropki", (i, j), "white"))
        elif u == 2 * v or v == 2 * u:
            dots.append(("kropki", (i, j), "black"))
        else:
            none_.append((i, j))
    return dots, none_


def element_bits(b, kind):
    """upper bound (bits) on what one element of `kind` can tell: log2(placements) + log2(values). Loose on purpose:
    it only rejects specs that cannot possibly be unique."""
    n, N = b.n, b.N
    E = len(b.edges)
    lg = math.log2
    if kind in ("kropki", "xv"):
        return lg(E) + 1
    if kind in CORNER:  # a block and a clue (four digits / an operator and value)
        return lg(N) + lg(4 * n * n)
    if kind in OUTSIDE:  # 4 sides x n lines (diagonals: about as many) and a clue up to the digits' total
        return lg(4 * n) + lg(n * (n + 1) // 2)
    if kind == "parity":
        return lg(N) + 1
    if kind == "cage":  # up to n cells: placement (start + 3 directions per step) + sum
        return lg(N) + (n - 1) * lg(3) + lg(n * (n + 1) // 2)
    return lg(N) + (n - 1) * lg(3) + 1  # lines: start + path; (thermo direction etc.)
