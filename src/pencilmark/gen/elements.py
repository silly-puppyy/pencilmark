"""Rule elements a generated puzzle can carry, true in a given solution grid.

An element is a tuple (kind, cells, extra):
  ("cage", sorted cells, total)          killer cage, distinct digits
  ("thermo", path, None)                 strictly increasing from the bulb (path[0])
  ("whisper", path, None)                German whisper, neighbours differ by >= whisper_gap(n)
  ("renban", path, None)                 a set of consecutive digits, any order
  ("between", path, None)                interior digits strictly between the two end circles
  ("arrow", (circle,) + shaft, None)     shaft digits sum to the circle digit
  ("kropki", (i, j), "white" | "black")  consecutive / 1:2 ratio
  ("xv", (i, j), "X" | "V")              sum 10 / sum 5
  ("parity", (i,), 1 | 0)                odd / even cell (graphical rule, not candidates)
"""

from __future__ import annotations

import math
from itertools import combinations

from .. import puzzle_json as PJ

KINDS = ("cage", "thermo", "whisper", "renban", "between", "arrow", "kropki", "xv", "parity")
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


# element classes: a kind, or one colour / letter / parity of it (counted separately in Spec.elements)
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
    """the class of an element: its colour / letter / parity class where one exists, else its kind"""
    for name, (kind, extra) in CLASSES.items():
        if e[0] == kind and e[2] == extra:
            return name
    return e[0]


def in_class(e, k):
    return e[0] == k or element_class(e) == k


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


LENGTHS = {"cage": (2, 5), "thermo": (2, 6), "whisper": (2, 7), "renban": (2, 5), "between": (3, 6), "arrow": (1, 4)}


def length_of(e):
    """an element's length as a template counts it: cells of a cage or line, the shaft of an arrow"""
    return len(e[1]) - 1 if e[0] == "arrow" else len(e[1])


def fits(e, shape):
    """does the element meet its template's shape limits? shape {kind: {"length": (lo, hi), "sum": (lo, hi)}}"""
    lim = (shape or {}).get(e[0])
    if not lim:
        return True
    lo, hi = lim.get("length", (None, None))
    if (lo is not None and length_of(e) < lo) or (hi is not None and length_of(e) > hi):
        return False
    slo, shi = lim.get("sum", (None, None))
    return e[0] != "cage" or ((slo is None or e[2] >= slo) and (shi is None or e[2] <= shi))


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
                nxt = [j for j in NB[path[-1]] if j not in path and j not in taken]
                if not nxt:
                    break
                path.append(rng.choice(nxt))
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
        if want_lo is not None and kind in ("thermo", "whisper", "renban"):  # long lines: a backtracking walk
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
                for j in NB[e_]:
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
            j, back = rng.choice(opts)
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
        return (-len(e[1]),)

    return sorted(_stable(e for e in out if fits(e, shape)), key=lambda e: (info(e), rng.random()))


def _walk(b, kind, sol, start, taken, rng, target, budget=None):
    """a line of `kind` from `start` (its bulb for a thermo), true in the solution, by randomised depth-first search:
    the first path of `target` cells, else the longest found within `budget` steps"""
    gap = whisper_gap(b.n)
    budget = budget or 40 * target * target  # a long line needs a deeper search (25 cells: 25,000 steps)
    best, steps = [start], 0

    def ok(path, j):
        a, c = sol[path[-1]], sol[j]
        if kind == "thermo":
            return c > a
        if kind == "whisper":
            return abs(c - a) >= gap
        ds = [sol[x] for x in path] + [c]  # renban: distinct digits that can still close up to a run of `target`
        return c not in ds[:-1] and max(ds) - min(ds) < target

    def dfs(path):
        nonlocal best, steps
        if len(path) > len(best):
            best = list(path)
        if len(path) >= target or steps > budget:
            return len(path) >= target
        steps += 1
        nxt = [j for j in b.nb[path[-1]] if j not in path and j not in taken and ok(path, j)]
        # fewest onward steps first (Warnsdorff's rule): long paths use up the cramped cells before they are cut off
        onward = lambda j: sum(1 for k in b.nb[j] if k not in path and k != j and k not in taken and ok(path + [j], k))
        nxt.sort(key=lambda j: (onward(j), rng.random()))
        return any(dfs(path + [j]) for j in nxt)

    if kind == "whisper" and not any(abs(sol[start] - sol[j]) >= gap for j in b.nb[start]):
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
    if getattr(b, "layout", None):  # a multi-grid layout: its grids imply the houses (numbers in its cell order)
        del d["box"]
        d["layout"] = b.layout
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
        elif kind in ("thermo", "renban", "between"):
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
    if kind == "parity":
        return lg(N) + 1
    if kind == "cage":  # up to n cells: placement (start + 3 directions per step) + sum
        return lg(N) + (n - 1) * lg(3) + lg(n * (n + 1) // 2)
    return lg(N) + (n - 1) * lg(3) + 1  # lines: start + path; (thermo direction etc.)
