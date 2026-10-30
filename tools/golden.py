"""Golden corpus: every output pencilmark produces for a fixed set of puzzles, so that a restructure can prove it
changed nothing.

  python tools/golden.py write [--corpus tests/golden] [-j 8]   record expected.jsonl from inputs.jsonl
  python tools/golden.py check [--corpus tests/golden] [-j 8]   compare; exit 1 and print the differences

inputs.jsonl: one {"name": ..., "puzzle": <anything rate() accepts>, "fields": [...] (optional)} per line.
For each puzzle the record holds the full card (every field except elapsed, with steps at all three explanation
levels), describe(), the canonical export and the engine's structural input (the arguments of the C++ puzzle), or the
error a puzzle raises.
"""

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

FIELDS = [
    "difficulty",
    "time",
    "band",
    "contains",
    "band_index",
    "time_p80",
    "time_p20",
    "time_mean",
    "time_dist",
    "issues",
    "reject",
    "warning",
    "se",
    "steps",
    "describe",
    "symmetry",
]


_LIMIT = 600  # far above every corpus puzzle's time; only a hang reaches it


class LimitReached(RuntimeError):
    """A card stopped at the time limit: its record would depend on machine speed."""


def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def record(item):
    """Every output for one corpus item (runs in a worker process)."""
    import pencilmark
    from pencilmark import cbackend

    name, puzzle = item["name"], item["puzzle"]
    out = {"name": name}
    try:
        fields = item.get(
            "fields", FIELDS
        )  # a very hard puzzle records a smaller card: the technique list takes minutes
        out["card"] = pencilmark.rate(puzzle, fields=fields, explain="steps" in fields or None, max_seconds=_LIMIT)
        if out["card"].get("completed") is False:
            raise LimitReached(f"{name}: stopped at the {_LIMIT} s limit; give it fewer fields")
        if "steps" in fields:
            out["notation"] = [
                s.get("explanation", {}).get("notation")
                for s in pencilmark.rate(puzzle, fields=["steps"], explain="notation")["steps"]
            ]
        out["describe"] = pencilmark.describe(puzzle)
        out["export"] = pencilmark.dumps(pencilmark.to_export(puzzle))
        out["engine_input"] = _digest(cbackend._cpuzzle_args(pencilmark.load(puzzle)))
    except LimitReached as e:
        return {"name": name, "limit_reached": str(e)}
    except Exception as e:  # an error is an output too (NotUnique, NoSolution, FormatError, ...)
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def run(corpus, jobs):
    items = [json.loads(line) for line in (corpus / "inputs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    with ProcessPoolExecutor(jobs) as ex:
        return list(ex.map(record, items))


def diff(a, b, path=""):
    """Paths where two records differ (first few per record)."""
    if type(a) is not type(b):
        return [f"{path}: {a!r} -> {b!r}"]
    if isinstance(a, dict):
        return [d for k in sorted(set(a) | set(b)) for d in diff(a.get(k), b.get(k), f"{path}.{k}")]
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: {len(a)} items -> {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} -> {b!r}"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=["write", "check"])
    ap.add_argument("--corpus", type=Path, default=Path(__file__).resolve().parents[1] / "tests/golden")
    ap.add_argument("-j", "--jobs", type=int, default=8)
    a = ap.parse_args(argv)
    got = run(a.corpus, a.jobs)
    slow = [r["limit_reached"] for r in got if "limit_reached" in r]
    if slow:
        print("\n".join(slow))
        print(f"{len(slow)} record(s) reached the time limit; nothing written or compared")
        return 2
    exp_path = a.corpus / "expected.jsonl"
    if a.action == "write":
        exp_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in got), encoding="utf-8")
        print(f"wrote {len(got)} records to {exp_path}")
        return 0
    expected = {r["name"]: r for r in map(json.loads, exp_path.read_text(encoding="utf-8").splitlines())}
    bad = 0
    for r in got:
        e = expected.get(r["name"])
        d = ["not in expected.jsonl"] if e is None else diff(e, r)
        if d:
            bad += 1
            print(f"{r['name']}:")
            for line in d[:8]:
                print(f"  {line[:300]}")
    print(f"{len(got) - bad} of {len(got)} identical")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
