"""Input fuzzer: valid puzzle files and generator requests from docs/examples, mutated at random (keys dropped, values
replaced by other types, list entries dropped or doubled). Reading a broken file must fail with a FormatError,
NotSupportedError or ValueError that says what is wrong, never another exception; a request must do the same (or
GenerationFailed), within its two-second limit. Prints counts per outcome and the seeds of anything else.
  python tools/fuzz_inputs.py N [--jobs J] [--specs]"""

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


def main(argv):
    n = int(argv[0])
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8
    case = spec_case if "--specs" in argv else puzzle_case
    by = collections.defaultdict(list)
    with ProcessPoolExecutor(jobs) as ex:
        for seed, what, detail in ex.map(case, range(n), chunksize=4):
            by[what].append((seed, detail))
    bad = 0
    for what, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(xs):5d}  {what}")
        if what not in ("clear error", "accepted", "generated", "not a request"):
            bad += len(xs)
            for s, d in xs[:4]:
                print(f"         seed {s}: {d}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
