"""Golden corpus: every output pencilmark produces for a fixed set of puzzles, so that a restructure can prove it
changed nothing.

  python tools/golden.py write [--corpus tests/golden] [-j N]   record expected.jsonl from inputs.jsonl
  python tools/golden.py check [--corpus tests/golden] [-j N]   compare; exit 1 and print the differences

-j defaults to the number of CPUs. The slowest records of the last run (timings kept in ~/.cache/pencilmark-golden)
start first.

inputs.jsonl: one {"name": ..., "puzzle": <anything rate() accepts>, "fields": [...] (optional)} per line.
For each puzzle the record holds the full card (every field except elapsed and the grader's version, with steps at
all three explanation levels), describe(), the canonical export and the engine's structural input (the arguments of the C++ puzzle), or the
error a puzzle raises.
"""

import argparse
import hashlib
import json
import os
import sys
import time
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


def record(item, reserved_ok=False):
    """Every output for one corpus item (runs in a worker process)."""
    import contextlib

    import pencilmark
    from pencilmark import cbackend, exchange

    with exchange._reserved_ok() if reserved_ok else contextlib.nullcontext():
        return _record(pencilmark, cbackend, item)


def _record(pencilmark, cbackend, item):
    name, puzzle = item["name"], item["puzzle"]
    out = {"name": name}
    try:
        fields = item.get(
            "fields", FIELDS
        )  # a very hard puzzle records a smaller card: the technique list takes minutes
        out["card"] = pencilmark.rate(puzzle, fields=fields, explain="steps" in fields or None, max_seconds=_LIMIT)
        if out["card"].get("completed") is False:
            raise LimitReached(f"{name}: stopped at the {_LIMIT} s limit; give it fewer fields")
        out["card"].get("grader", {}).pop("version", None)  # a release changes it; the corpus records behaviour
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


def _timed(item, reserved_ok):
    t = time.perf_counter()
    return record(item, reserved_ok), time.perf_counter() - t


def _timings_file(corpus):
    """seconds per record from the last run, kept outside the repository (it differs per machine)"""
    key = hashlib.sha256(str(corpus.resolve()).encode()).hexdigest()[:12]
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "pencilmark-golden" / f"{key}.json"


def run(corpus, jobs, reserved_ok=False):
    """records in input order; the slowest records of the last run start first, so the run ends with short ones"""
    items = [json.loads(line) for line in (corpus / "inputs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    tf = _timings_file(corpus)
    try:
        last = json.loads(tf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last = {}
    order = sorted(range(len(items)), key=lambda i: -last.get(items[i]["name"], 0.0))
    with ProcessPoolExecutor(jobs) as ex:
        futs = {i: ex.submit(_timed, items[i], reserved_ok) for i in order}
        done = {i: f.result() for i, f in futs.items()}
    try:
        tf.parent.mkdir(parents=True, exist_ok=True)
        tf.write_text(json.dumps({items[i]["name"]: round(t, 2) for i, (_, t) in done.items()}), encoding="utf-8")
    except OSError:
        pass
    return [done[i][0] for i in range(len(items))]


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
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 8)
    ap.add_argument(
        "--reserved-ok", action="store_true", help="accept reserved format parts (digit tables), as the benchmark does"
    )
    a = ap.parse_args(argv)
    got = run(a.corpus, a.jobs, a.reserved_ok)
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
