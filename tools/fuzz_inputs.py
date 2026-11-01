"""Input fuzzer: valid puzzle files and generator requests from docs/examples, mutated at random (keys dropped, values
replaced by other types, list entries dropped or doubled). Reading a broken file must fail with a FormatError,
NotSupportedError or ValueError that says what is wrong, never another exception; a request must do the same (or
GenerationFailed), within its two-second limit. Prints counts per outcome and the seeds of anything else.
An f-puzzles document with most of its features is broken the same way (--fpuzzles): the reader must translate it or
raise a SourceError.
  python tools/fuzz_inputs.py N [--jobs J] [--specs | --fpuzzles]"""

import collections
import copy
import json
import random
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALUES = [None, True, 0, -1, 1, 99, 2.5, "", "x", "r0c0", "r99c1", [], [1], ["r1c1"], [["r1c1"]], {}, {"a": 1}]
NOT_A_SPEC = 'generate takes a "sudoku-spec"'  # generate's own TypeError for anything that is no request at all
CLASSIC = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."


def puzzles():
    out = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "docs/examples").glob("*.json"))]
    gen = sorted((ROOT / "docs/examples/generated").glob("*.json"))
    return out + [json.loads(p.read_text(encoding="utf-8"))["puzzle"] for p in gen]


def specs():
    gen = sorted((ROOT / "docs/examples/generated").glob("*.json"))
    out = [json.loads(p.read_text(encoding="utf-8"))["spec"] for p in gen]
    return out + [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "docs/examples/specs").glob("*.json"))
    ]


def mutate(rng, d):
    """one to three random edits somewhere in the document"""
    d = copy.deepcopy(d)
    for _ in range(rng.randint(1, 3)):
        node, path = d, []
        for _depth in range(rng.randint(0, 4)):
            if isinstance(node, dict) and node:
                k = rng.choice(list(node))
            elif isinstance(node, list) and node:
                k = rng.randrange(len(node))
            else:
                break
            path.append(k)
            node = node[k]
        if not path:
            continue
        parent = d
        for k in path[:-1]:
            parent = parent[k]
        k, op = path[-1], rng.random()
        if op < 0.3 and isinstance(parent, dict):
            parent.pop(k, None)
        elif op < 0.4 and isinstance(parent, list):
            parent.pop(k)
        elif op < 0.5 and isinstance(parent, list):
            parent.append(copy.deepcopy(parent[k]))
        else:
            parent[k] = copy.deepcopy(rng.choice(VALUES))
    return d


def where(e):
    tb = traceback.extract_tb(e.__traceback__)[-1]
    return f"{str(e)[:120]} @{Path(tb.filename).name}:{tb.lineno}"


def puzzle_case(seed):
    import pencilmark as pm

    rng = random.Random(seed)
    d = mutate(rng, rng.choice(puzzles()))
    calls = (
        ("validate", pm.validate),
        ("load", pm.load),
        ("rate", lambda x: pm.rate(x, max_seconds=5, fields=["band", "difficulty"])),
    )
    for name, fn in calls:
        try:
            fn(d)
        except (pm.FormatError, pm.NotSupportedError, ValueError):
            return seed, "clear error", None
        except pm.Undecided:  # a broken puzzle can have too many solutions to settle in max_seconds: documented
            return seed, "undecided", None
        except Exception as e:  # noqa: BLE001
            return seed, f"{name}: {type(e).__name__}", where(e)
    return seed, "accepted", None


def spec_case(seed):
    import pencilmark as pm

    rng = random.Random(seed)
    d = mutate(rng, rng.choice(specs()))
    if isinstance(d, dict):
        d["limits"] = {"time": 2, "seed": 1}
    try:
        pm.generate(d)
        return seed, "generated", None
    except (pm.FormatError, pm.NotSupportedError, pm.GenerationFailed, ValueError):
        return seed, "clear error", None
    except TypeError as e:
        if str(e).startswith(NOT_A_SPEC):
            return seed, "not a request", None
        return seed, "TypeError", where(e)
    except Exception as e:  # noqa: BLE001
        return seed, type(e).__name__, where(e)


def fpuzzles_base():
    """an f-puzzles document with most of its features, on a classic"""
    grid = [
        [({"value": int(CLASSIC[r * 9 + c]), "given": True} if CLASSIC[r * 9 + c] != "." else {}) for c in range(9)]
        for r in range(9)
    ]
    return {
        "size": 9,
        "grid": grid,
        "killercage": [{"cells": ["R1C1", "R1C2"], "value": "10"}],
        "thermometer": [{"lines": [["R2C2", "R2C3", "R2C4"]]}],
        "arrow": [{"cells": ["R5C5"], "lines": [["R5C5", "R5C6", "R5C7"]]}],
        "littlekillersum": [{"cell": "R0C1", "cells": ["R1C2", "R2C3"], "direction": "DR", "value": "9"}],
        "sandwichsum": [{"cell": "R0C3", "value": "15"}],
        "difference": [{"cells": ["R7C7", "R7C8"]}],
        "ratio": [{"cells": ["R8C8", "R8C9"]}],
        "xv": [{"cells": ["R9C1", "R9C2"], "value": "X"}],
        "odd": [{"cell": "R3C3"}],
        "even": [{"cell": "R4C4"}],
        "renban": [{"lines": [["R6C1", "R6C2"]]}],
        "whispers": [{"lines": [["R6C4", "R6C5"]]}],
        "betweenline": [{"lines": [["R8C1", "R8C2", "R8C3"]]}],
        "palindrome": [{"lines": [["R3C7", "R3C8"]]}],
        "lockout": [{"lines": [["R4C7", "R4C8", "R4C9"]], "value": "5"}],
        "diagonal+": True,
        "antiknight": False,
        "extraregion": [{"cells": ["R1C9", "R2C9"]}],
        "quadruple": [{"cells": ["R5C1", "R5C2", "R6C1", "R6C2"], "values": [1, 2]}],
        "minimum": [{"cell": "R9C9"}],
    }


def fpuzzles_case(seed):
    import urllib.parse

    import lzstring

    import pencilmark as pm
    from pencilmark.sources import SourceError
    from pencilmark.sources import fpuzzles as FP

    d = mutate(random.Random(seed), fpuzzles_base())
    url = "https://f-puzzles.com/?load=" + urllib.parse.quote(
        lzstring.LZString().compressToBase64(json.dumps(d)), safe=""
    )
    try:
        pm.load(FP.to_puzzle(url, rules_text="Normal sudoku rules apply.", fetch=False))
        return seed, "accepted", None
    except (SourceError, pm.FormatError, pm.NotSupportedError, ValueError):
        return seed, "clear error", None
    except Exception as e:  # noqa: BLE001
        return seed, type(e).__name__, where(e)


def main(argv):
    n = int(argv[0])
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8
    case = spec_case if "--specs" in argv else fpuzzles_case if "--fpuzzles" in argv else puzzle_case
    by = collections.defaultdict(list)
    with ProcessPoolExecutor(jobs) as ex:
        for seed, what, detail in ex.map(case, range(n), chunksize=4):
            by[what].append((seed, detail))
    bad = 0
    for what, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(xs):5d}  {what}")
        if what not in ("clear error", "accepted", "undecided", "generated", "not a request"):
            bad += len(xs)
            for s, d in xs[:4]:
                print(f"         seed {s}: {d}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
