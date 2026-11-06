"""Fuzzer: random puzzles built true of a random solution, with tools/spec_check.py (written from the docs, not the
engine) as the referee. Each case: a random board (4x4 to 9x9) and one to five random rules true in the solution and
accepted by the referee, then
  - validate() accepts the file the referee accepts;
  - with every cell given, the engine finds exactly one solution (else it over-constrains a rule);
  - with some givens, if unique, the solution is the true one (else it under-constrains);
  - a unique case is graded: every placement and elimination agrees with the solution;
  - write.document / write.pencilmark / fingerprint round trips hold;
  - the transposed puzzle (rows <-> columns, sides swapped) gets the same band and nearly the same difficulty (ties
    between equally priced steps are broken in reading order, so its route can differ: 0.3 or 5% allowed).
Failures are grouped by symptom with the seed that reproduces them; `--seed S` reruns one case and prints its file.
  python tools/fuzz.py N [--jobs J] [--start S] [--sizes 12,16]       python tools/fuzz.py --seed S"""

import collections
import json
import random
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec_check as SC  # noqa: E402

BOXES = {4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3), 12: (3, 4), 16: (4, 4)}
SIZES = [4, 6, 8, 9, 9, 9]  # --sizes 12,16 for the big boards
NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
NB4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def solution(rng, D):
    bh, bw = BOXES[D]
    g = [[(bw * (r % bh) + r // bh + c) % D + 1 for c in range(D)] for r in range(D)]
    perm = list(range(1, D + 1))
    rng.shuffle(perm)
    g = [[perm[v - 1] for v in row] for row in g]
    bands = list(range(D // bh))
    rng.shuffle(bands)
    rows = [b * bh + i for b in bands for i in rng.sample(range(bh), bh)]
    stacks = list(range(D // bw))
    rng.shuffle(stacks)
    cols = [s * bw + j for s in stacks for j in rng.sample(range(bw), bw)]
    return [[g[r][c] for c in cols] for r in rows]


def nm(r, c):
    return f"r{r + 1}c{c + 1}"


def walk(rng, D, n, ok, nb=NB8):
    """a random self-avoiding path of n cells; ok(path, next) filters steps"""
    for _ in range(30):
        p = [(rng.randrange(D), rng.randrange(D))]
        while len(p) < n:
            r, c = p[-1]
            opts = [(r + a, c + b) for a, b in nb if 0 <= r + a < D and 0 <= c + b < D and (r + a, c + b) not in p]
            opts = [x for x in opts if ok(p, x)]
            if not opts:
                break
            p.append(rng.choice(opts))
        if len(p) == n:
            return p
    return None


def propose(rng, S, D):
    """one random rule, parameters computed from the solution S where that is easy"""
    v = lambda x: S[x[0]][x[1]]
    k = rng.choice(["cage", "thermo", "slow_thermo", "whisper", "renban", "parity", "between", "lockout", "arrow",
                    "double_arrow", "palindrome", "entropic", "modular", "zipper", "region_sum",
                    "kropki", "xv", "greater", "difference", "sum", "product", "ratio", "kropki_all", "xv_all",
                    "odd", "even", "low", "set", "exclude", "corner_exclude", "mathrax", "battenburg",
                    "little_killer", "frame", "sum_corner", "sum_group", "sandwich", "xsum", "skyscraper",
                    "contains", "extra", "window"])  # fmt: skip
    L = lambda kind, p, **kw: [dict({"type": "line", "kind": kind}, **kw, cells=[nm(*x) for x in p])]
    n = rng.randint(2, 6)
    if k == "cage":
        p = walk(rng, D, rng.randint(2, 5), lambda p, x: v(x) not in {v(y) for y in p}, NB4)
        return p and [
            dict(
                {"type": "cage", "cells": [nm(*x) for x in p]},
                **({"sum": sum(map(v, p))} if rng.random() < 0.8 else {}),
            )
        ]
    if k in ("thermo", "slow_thermo"):
        p = walk(rng, D, n, lambda p, x: v(x) > v(p[-1]))
        return p and L(k, p)
    if k == "whisper":
        kk = rng.randint(1, D - 1)
        p = walk(rng, D, n, lambda p, x: abs(v(x) - v(p[-1])) >= kk)
        return p and L(k, p, value=kk)
    if k == "renban":
        p = walk(rng, D, rng.randint(2, 5), lambda p, x: v(x) not in {v(y) for y in p})
        return p and L(k, p)
    if k == "parity":
        p = walk(rng, D, n, lambda p, x: (v(x) - v(p[-1])) % 2 == 1)
        return p and L(k, p)
    if k in ("between", "lockout", "double_arrow", "palindrome", "zipper", "region_sum"):
        p = walk(rng, D, rng.randint(3, 6), lambda p, x: True)
        if not p:
            return None
        if k == "lockout":
            return L(k, p, value=max(1, abs(v(p[0]) - v(p[-1]))))
        return L(k, p)
    if k == "entropic" and D % 3 == 0:
        third = lambda d: (d - 1) * 3 // D
        p = walk(rng, D, n, lambda p, x: third(v(x)) not in {third(v(y)) for y in p[-2:]})
        grp = [[d for d in range(1, D + 1) if third(d) == t] for t in range(3)]
        return p and (L(k, p) if D == 9 else L(k, p, groups=grp))
    if k == "modular":
        p = walk(rng, D, n, lambda p, x: v(x) % 3 not in {v(y) % 3 for y in p[-2:]})
        return p and (L(k, p) if D == 9 else L(k, p, value=3))
    if k == "arrow":
        b = (rng.randrange(D), rng.randrange(D))
        sh = walk(rng, D, rng.randint(1, 3), lambda p, x: x != b)
        if not sh or max(abs(sh[0][0] - b[0]), abs(sh[0][1] - b[1])) != 1:
            return None
        return [{"type": "arrow", "bulb": [nm(*b)], "lines": [[nm(*x) for x in sh]]}]
    if k in ("kropki", "xv", "greater", "difference", "sum", "product", "ratio"):
        r, c = rng.randrange(D), rng.randrange(D)
        a, b = rng.choice(NB4)
        if not (0 <= r + a < D and 0 <= c + b < D):
            return None
        x, y = (r, c), (r + a, c + b)
        e = {"type": "edge", "kind": k, "cells": [nm(*x), nm(*y)]}
        X, Y = v(x), v(y)
        if k == "kropki":
            e["color"] = "white" if abs(X - Y) == 1 else "black"
        elif k == "xv":
            e["letter"] = "X" if X + Y == 10 else "V"
        elif k == "greater":
            e["cells"] = [nm(*x), nm(*y)] if X > Y else [nm(*y), nm(*x)]
        elif k == "difference":
            e["value"] = abs(X - Y)
        elif k == "sum":
            e["sum"] = X + Y
        elif k == "product":
            e["value"] = X * Y
        else:
            e["value"] = max(X, Y) // min(X, Y)
        return [e]
    if k in ("kropki_all", "xv_all"):
        fam = k.split("_")[0]
        out = []
        for r in range(D):
            for c in range(D):
                for a, b in ((0, 1), (1, 0)):
                    if r + a < D and c + b < D:
                        X, Y = S[r][c], S[r + a][c + b]
                        cs = [nm(r, c), nm(r + a, c + b)]
                        if fam == "kropki" and abs(X - Y) == 1:
                            out.append({"type": "edge", "kind": "kropki", "color": "white", "cells": cs})
                        elif fam == "kropki" and (X == 2 * Y or Y == 2 * X):
                            out.append({"type": "edge", "kind": "kropki", "color": "black", "cells": cs})
                        elif fam == "xv" and X + Y in (5, 10):
                            out.append(
                                {"type": "edge", "kind": "xv", "letter": "X" if X + Y == 10 else "V", "cells": cs}
                            )
        return out + [{"type": "negative", "of": fam}]
    if k in ("odd", "even"):
        cs = [(r, c) for r in range(D) for c in range(D) if v((r, c)) % 2 == (k == "odd")]
        return [{"type": "cell", "kind": k, "cells": [nm(*x) for x in rng.sample(cs, min(len(cs), rng.randint(1, 4)))]}]
    if k == "low":
        sp = rng.randint(1, D - 1)
        cs = [(r, c) for r in range(D) for c in range(D) if v((r, c)) <= sp]
        return [
            {"type": "cell", "kind": "low", "split": sp, "cells": [nm(*x) for x in rng.sample(cs, min(len(cs), 3))]}
        ]
    if k in ("set", "exclude"):
        x = (rng.randrange(D), rng.randrange(D))
        vals = sorted(rng.sample([d for d in range(1, D + 1) if d != v(x)], rng.randint(1, 3)))
        vals = sorted(set(vals[:-1]) | {v(x)}) if k == "set" else vals
        return [{"type": "cell", "kind": k, "values": vals, "cells": [nm(*x)]}]
    if k in ("corner_exclude", "mathrax", "battenburg", "sum_corner"):
        r, c = rng.randrange(D - 1), rng.randrange(D - 1)
        blk = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
        cells = [nm(*x) for x in blk]
        if k == "corner_exclude":
            return [
                {
                    "type": "corner",
                    "kind": "exclude",
                    "value": rng.choice([d for d in range(1, D + 1) if d not in map(v, blk)] or [1]),
                    "cells": cells,
                }
            ]
        if k == "battenburg":
            return [{"type": "corner", "kind": "battenburg", "cells": cells}]
        if k == "sum_corner":
            return [{"type": "sum", "kind": "corner", "sum": sum(map(v, blk)), "cells": cells}]
        tl, tr, bl, br = map(v, blk)
        for op, f in (("+", lambda a, b: a + b), ("-", lambda a, b: abs(a - b)), ("x", lambda a, b: a * b),
                      ("/", lambda a, b: max(a, b) // min(a, b) if max(a, b) % min(a, b) == 0 else None)):  # fmt: skip
            if f(tl, br) is not None and f(tl, br) == f(tr, bl):
                return [{"type": "corner", "kind": "mathrax", "op": op, "value": f(tl, br), "cells": cells}]
        if all(x % 2 == 0 for x in (tl, tr, bl, br)):
            return [{"type": "corner", "kind": "mathrax", "op": "even", "cells": cells}]
        return None
    side = rng.choice(["top", "bottom", "left", "right"])
    i = rng.randrange(D)
    line = {"top": [(r, i) for r in range(D)], "bottom": [(r, i) for r in range(D - 1, -1, -1)],
            "left": [(i, c) for c in range(D)], "right": [(i, c) for c in range(D - 1, -1, -1)]}[side]  # fmt: skip
    if k == "frame":
        m = rng.randint(1, 3)
        return [
            {
                "type": "sum",
                "kind": "frame",
                "sum": sum(map(v, line[:m])),
                "side": side,
                "cells": [nm(*x) for x in line[:m]],
            }
        ]
    if k == "sandwich":
        vals = list(map(v, line))
        a, b = sorted((vals.index(1), vals.index(D)))
        return [{"type": "sandwich", "sum": sum(vals[a + 1 : b]), "side": side, "cells": [nm(*x) for x in line]}]
    if k == "xsum":
        X = v(line[0])
        return [{"type": "xsum", "sum": sum(map(v, line[:X])), "side": side, "cells": [nm(*x) for x in line]}]
    if k == "skyscraper":
        vals, seen, top = list(map(v, line)), 0, 0
        for x in vals:
            if x > top:
                seen, top = seen + 1, x
        return [{"type": "skyscraper", "value": seen, "side": side, "cells": [nm(*x) for x in line]}]
    if k == "little_killer":
        dr = {"top": (1, 0), "bottom": (-1, 0), "left": (0, 1), "right": (0, -1)}[side]
        r0, c0 = line[0]
        dd = (dr[0] or rng.choice([-1, 1]), dr[1] or rng.choice([-1, 1]))
        cells = []
        r, c = r0, c0
        while 0 <= r < D and 0 <= c < D:
            cells.append((r, c))
            r, c = r + dd[0], c + dd[1]
        if len(cells) < 2:
            return None
        return [
            {
                "type": "sum",
                "kind": "little_killer",
                "sum": sum(map(v, cells)),
                "side": side,
                "cells": [nm(*x) for x in cells],
            }
        ]
    if k == "sum_group":
        cs = rng.sample([(r, c) for r in range(D) for c in range(D)], rng.randint(2, 4))
        return [{"type": "sum", "kind": "group", "sum": sum(map(v, cs)), "cells": [nm(*x) for x in cs]}]
    if k == "contains":
        cs = walk(rng, D, 4, lambda p, x: True, NB4)
        return cs and [
            {
                "type": "contains",
                "digits": sorted(rng.sample(sorted(set(map(v, cs))), 2)),
                "cells": [nm(*x) for x in cs],
            }
        ]
    if k in ("extra", "window"):
        r, c = rng.randrange(D - 1), rng.randrange(D - 1)
        blk = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
        return [{"type": "region", "kind": k, "cells": [nm(*x) for x in blk]}]
    return None


def spec_ok(doc):
    rep = SC.Report()
    try:
        SC.check_doc(SC.Doc(doc), rep)
    except Exception:  # noqa: BLE001
        return False
    return not any(rep.viol.values())


def case(seed):
    import pencilmark as pm

    rng = random.Random(seed)
    D = rng.choice(SIZES)
    S = solution(rng, D)
    flat = [x for row in S for x in row]
    base = {"format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": D, "cols": D}, "digits": D,
            "givens": [0] * (D * D), "rules": [{"type": "box_grid", "box": list(BOXES[D]), "count": [BOXES[D][1], BOXES[D][0]]}]}  # fmt: skip
    rules = []
    for _ in range(rng.randint(1, 5)):
        r = propose(rng, S, D)
        if not r:
            continue
        trial = dict(base, rules=base["rules"] + rules + r, solution=flat)
        if spec_ok(trial):
            rules += r
    if not rules:
        return seed, "skip", None
    doc = dict(base, rules=base["rules"] + rules)
    kinds = sorted({x["type"] + ("/" + x["kind"] if "kind" in x else "") for x in rules})
    fail = lambda what, detail="": (seed, what, f"D={D} {kinds} {detail}"[:300])
    try:
        pm.validate(doc)
    except Exception as e:  # noqa: BLE001
        return fail("VALID BY SPEC CHECKER, REFUSED BY validate", f"{type(e).__name__}: {e}")
    try:
        full = dict(doc, givens=flat)
        n = pm.count_solutions(full, limit=2)["count"]
        if n != 1:
            return fail("engine rejects the true solution (over-constrains)", f"count={n}")
        g = [x if rng.random() < (0.55 if D >= 8 else 0.4) else 0 for x in flat]
        part = dict(doc, givens=g)
        n = pm.count_solutions(part, limit=2)["count"]
        if n != 1:
            return seed, "not unique (fine)", None
        sol = pm.solve(part)
        if sol != flat:
            return fail("unique solution differs from the true one (under-constrains)")
        card = pm.rate(part, steps=True, alternatives=False, max_seconds=30)
        for s in card.get("steps") or []:
            for p in (s.get("placement") or "").split(","):
                if p.strip():
                    c_, val = p.strip().split("=")
                    r_, cc = map(int, c_[1:].split("c"))
                    if flat[(r_ - 1) * D + cc - 1] != int(val):
                        return fail("WRONG PLACEMENT", f"{s['code']} {p}")
            for e in s.get("eliminations") or []:
                c_, val = e.split("#")
                r_, cc = map(int, c_[1:].split("c"))
                if flat[(r_ - 1) * D + cc - 1] == int(val):
                    return fail("ELIMINATES THE SOLUTION", f"{s['code']} {e}")
        ex = pm.write.document(part, solution=True, describe=True)
        if pm.write.document(ex, solution=True, describe=True) != ex or pm.fingerprint(ex) != pm.fingerprint(
            json.loads(pm.write.pencilmark(ex))
        ):
            return fail("round trip")
        return seed, "ok", part
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)[-1]
        return fail(f"CRASH {type(e).__name__}", f"{str(e)[:120]} @{tb.filename.split('/')[-1]}:{tb.lineno}")


def transpose(doc):
    """the puzzle mirrored in the main diagonal: every cell rXcY becomes rYcX, outside clues change sides"""
    D = doc["digits"]
    side = {"top": "left", "left": "top", "bottom": "right", "right": "bottom"}

    def walk_(x):
        if isinstance(x, str) and x[:1] == "r" and "c" in x:
            r, c = x[1:].split("c")
            return f"r{c}c{r}" if r.isdigit() and c.isdigit() else x
        if isinstance(x, list):
            return [walk_(y) for y in x]
        if isinstance(x, dict):
            out = {k: walk_(v) for k, v in x.items()}
            if "side" in out:
                out["side"] = side[out["side"]]
            if out.get("type") == "box_grid":  # boxes and their repetition count swap with rows and columns
                out["box"] = out["box"][::-1]
                if "count" in out:
                    out["count"] = out["count"][::-1]
            if out.get("type") == "corner" or (out.get("type") == "sum" and out.get("kind") == "corner"):
                a, b, c, d = out["cells"]  # TL, TR, BL, BR: the old top right is now the bottom left
                out["cells"] = [a, c, b, d]
            return out
        return x

    t = walk_({k: v for k, v in doc.items() if k != "givens"})
    g = doc["givens"]
    t["givens"] = [g[c * D + r] for r in range(D) for c in range(D)]
    return t


def case_full(seed):
    """case() plus the transposition check (kept apart so a crash in it is reported as such)"""
    import pencilmark as pm

    res = case(seed)
    if res[1] != "ok":
        return res
    part = res[2]
    try:
        a = pm.rate(part, alternatives=False, max_seconds=30, fields=["band", "difficulty"])
        b = pm.rate(transpose(part), alternatives=False, max_seconds=30, fields=["band", "difficulty"])
    except Exception as e:  # noqa: BLE001
        return seed, f"CRASH (transposed) {type(e).__name__}", str(e)[:200]
    if a.get("completed", True) and b.get("completed", True):
        da, db = a["difficulty"], b["difficulty"]
        # ties between equally priced steps are broken in reading order, so the transposed route may differ a little
        if a["band"] != b["band"] or abs(da - db) > max(0.3, 0.05 * max(da, db)):
            return seed, "transposed puzzle grades differently", f"{a['band']} {da} vs {b['band']} {db}"
    return seed, "ok", None


def main(argv):
    if "--sizes" in argv:  # global, read by the workers (fork)
        SIZES[:] = [int(x) for x in argv[argv.index("--sizes") + 1].split(",")]
    if "--seed" in argv:
        s = int(argv[argv.index("--seed") + 1])
        print(case_full(s)[:2])
        doc = case(s)[2]
        print(json.dumps(doc) if isinstance(doc, dict) else doc)
        return 0
    n = int(argv[0])
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8
    start = int(argv[argv.index("--start") + 1]) if "--start" in argv else 0
    by = collections.defaultdict(list)
    with ProcessPoolExecutor(jobs) as ex:
        for seed, what, detail in ex.map(case_full, range(start, start + n), chunksize=4):
            by[what].append((seed, detail))
    bad = 0
    for what, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(xs):5d}  {what}")
        if what not in ("ok", "skip", "not unique (fine)"):
            bad += len(xs)
            for s, d in xs[:4]:
                print(f"         seed {s}: {d}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
