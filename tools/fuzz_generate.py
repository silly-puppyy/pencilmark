"""Generator fuzzer: random requests (one to three templates with counts, shape limits and "max", sometimes a given
range and a target) on 4x4 to 9x9 boards, 25 s each. A run that fails says why, which is fine; a puzzle it returns must
meet its request: validate() accepts it, it is unique, every template's count, length, size and sum hold, the givens
are in range and the band / difficulty target is met. Failures print the seed and the request.
  python tools/fuzz_generate.py N [--jobs J]"""

import collections
import json
import random
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor

BOX = {4: [2, 2], 6: [2, 3], 8: [2, 4], 9: [3, 3]}
OUTSIDE = [{"type": "sandwich"}, {"type": "xsum"}, {"type": "skyscraper"}, {"type": "sum", "kind": "little_killer"}]
LINES = None  # every line kind the generator places (rules/line.py), read in request()


LAYOUTS = ["samurai", "twodoku", "butterfly", "sohei", "windmill"]


def request(rng):
    global LINES
    if LINES is None:
        from pencilmark.rules.line import LINE

        LINES = [k for k, lk in LINE.items() if lk.generated]
    D = rng.choice([4, 6, 6, 8, 9, 9, 9])
    rules = [{"type": "box_grid", "origin": "r1c1", "box": BOX[D]}]
    layout = rng.choice(LAYOUTS) if rng.random() < 0.25 else None
    if layout:  # a multi-grid layout, maybe with diagonals on one grid and floors per grid
        from pencilmark import puzzle_json as PJ

        D, origins = 9, PJ._layouts()[layout]
        rules = [{"type": "box_grid", "origin": f"r{r + 1}c{c + 1}", "box": [3, 3]} for r, c in origins]
        if rng.random() < 0.4:
            r0, c0 = rng.choice(origins)
            rules.append(
                {"type": "region", "kind": "diagonal", "cells": [f"r{r0 + i + 1}c{c0 + i + 1}" for i in range(9)]}
            )
    used = set()
    for _ in range(rng.randint(1, 3)):
        k = rng.choice(["cage", "line", "arrow", "kropki", "xv", "cell", "outside"])
        t = {
            "cage": {"type": "cage"},
            "arrow": {"type": "arrow"},
            "kropki": {"type": "edge", "kind": "kropki"},
            "xv": {"type": "edge", "kind": "xv"},
            "cell": {"type": "cell", "kind": rng.choice(["odd", "even", "parity"])},
            "line": {"type": "line", "kind": rng.choice(LINES)},
            "outside": dict(rng.choice(OUTSIDE)),
        }[k]
        key = (t["type"], t.get("kind"))
        if key in used:
            continue
        used.add(key)
        t["count"] = rng.choice([1, 2, [1, None], [0, 3], "auto", "max"])
        if k == "cage" and rng.random() < 0.6:
            if rng.random() < 0.5:
                t["size"] = rng.choice([2, [2, 3], [3, None]])
            if rng.random() < 0.5:
                t["sum"] = rng.choice([D + 1, [5, 12], [10, None]])
        if k in ("line", "arrow") and rng.random() < 0.6:
            t["length"] = rng.choice([[4, None], [3, 5], 6]) if k == "line" else rng.choice([2, [1, 3]])
        if k == "line" and t["kind"] == "whisper" and D != 9:
            t["value"] = (D + 1) // 2
        rules.append(t)
    s = {
        "format": "sudoku-spec",
        "format_version": 1,
        "board": {"rows": D, "cols": D},
        "digits": D,
        "rules": rules,
        "limits": {"time": 25, "seed": rng.randint(1, 99)},
    }
    if layout:
        s["board"] = {"rows": max(r for r, _ in origins) + 9, "cols": max(c for _, c in origins) + 9}
        if rng.random() < 0.5:
            s["givens"] = {"grids": [[rng.randint(0, 30), None] for _ in origins]}
    elif rng.random() < 0.3:
        s["givens"] = {"count": rng.choice([[0, 10], [5, None]])}
    if rng.random() < 0.3:
        s["where"] = rng.choice([{"band": "Easy"}, {"difficulty": "min"}, {"difficulty": [3, 8]}])
    return s


def check(s, r):
    """problems with the result against the request"""
    import pencilmark as pm

    p, out = r["puzzle"], []
    pm.validate(p)
    giv = sum(1 for v in p["givens"] if v)
    gc = (s.get("givens") or {}).get("count")
    if isinstance(gc, list) and (giv < (gc[0] or 0) or (gc[1] is not None and giv > gc[1])):
        out.append(f"givens {giv} outside {gc}")
    if r["info"].get("unique_verified") is False:
        out.append("not unique")
    C = p["board"]["cols"]
    grids = sorted(tuple(int(x) - 1 for x in t["origin"][1:].split("c")) for t in s["rules"] if t["type"] == "box_grid")
    for (r0, c0), lim in zip(grids, (s.get("givens") or {}).get("grids") or []):
        lo, hi = (lim, lim) if isinstance(lim, int) else lim
        n = sum(1 for r in range(9) for c in range(9) if p["givens"][(r0 + r) * C + c0 + c])
        if n < (lo or 0) or (hi is not None and n > hi):
            out.append(f"grid at r{r0 + 1}c{c0 + 1}: {n} givens outside {lim}")
    for t in s["rules"]:
        if "cells" in t and t["type"] != "box_grid" and t not in p["rules"]:
            out.append(f"locked {t['type']} {t.get('kind')} missing from the result")
    for t in [x for x in s["rules"] if "count" in x]:

        def mine(x):
            if t["type"] == "cell":
                return x["type"] == "cell" and (t["kind"] == "parity" or x.get("kind") == t["kind"])
            return x["type"] == t["type"] and (t.get("kind") is None or x.get("kind") == t.get("kind"))

        els = [x for x in p["rules"] if mine(x)]
        n = sum(len(x["cells"]) if t["type"] == "cell" else 1 for x in els)
        c = t["count"]
        if isinstance(c, int) and n != c:
            out.append(f"{t['type']}/{t.get('kind')}: {n} placed, asked {c}")
        if isinstance(c, list) and (n < (c[0] or 0) or (c[1] is not None and n > c[1])):
            out.append(f"{t['type']}/{t.get('kind')}: {n} placed, asked {c}")
        for x in els:
            ln = len(x["lines"][0]) if t["type"] == "arrow" else len(x.get("cells", []))
            lim = t.get("size") or t.get("length")
            if lim is not None:
                lo, hi = (lim, lim) if isinstance(lim, int) else lim
                if ln < lo or (hi is not None and ln > hi):
                    out.append(f"{t['type']}/{t.get('kind')} length {ln} outside {lim}")
            if "sum" in t and t["type"] == "cage":
                lo, hi = (t["sum"], t["sum"]) if isinstance(t["sum"], int) else t["sum"]
                if x.get("sum") is None or x["sum"] < lo or (hi is not None and x["sum"] > hi):
                    out.append(f"cage sum {x.get('sum')} outside {t['sum']}")
    w = s.get("where") or {}
    if "band" in w and r["card"]["band"] != w["band"]:
        out.append(f"band {r['card']['band']} != {w['band']}")
    if isinstance(w.get("difficulty"), list):
        lo, hi = w["difficulty"]
        if not lo <= r["card"]["difficulty"] <= hi:
            out.append(f"difficulty {r['card']['difficulty']} outside {w['difficulty']}")
    return out


def case(seed):
    import pencilmark as pm

    s = request(random.Random(seed))
    try:
        r = pm.generate(s)
    except pm.GenerationFailed as e:
        return seed, "failed (fine)", str(e)[:80]
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)[-1]
        return (
            seed,
            f"CRASH {type(e).__name__}",
            f"{str(e)[:150]} @{tb.filename.split('/')[-1]}:{tb.lineno} {json.dumps(s['rules'][1:])}",
        )
    try:
        prob = check(s, r)
    except Exception as e:  # noqa: BLE001
        return seed, f"CHECK CRASH {type(e).__name__}", str(e)[:200]
    return (
        (seed, "BAD RESULT", "; ".join(prob) + " " + json.dumps(s["rules"][1:]) + json.dumps(s.get("where")))
        if prob
        else (seed, "ok", None)
    )


if __name__ == "__main__":
    n = int(sys.argv[1])
    j = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 8
    by = collections.defaultdict(list)
    with ProcessPoolExecutor(j) as ex:
        for seed, what, d in ex.map(case, range(n)):
            by[what].append((seed, d))
    for what, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(len(xs), what)
        if what not in ("ok",):
            for s_, d in xs[:6]:
                print("   ", s_, d)
