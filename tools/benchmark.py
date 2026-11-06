"""The benchmark of docs/grades/benchmark.mdx, on your own data: grade puzzles that have a human target, then report how well
the card follows the target. Standard library only (plus pencilmark).

  python tools/benchmark.py grade puzzles.jsonl -o grades.jsonl [--jobs 8] [--max-seconds 300]
  python tools/benchmark.py report grades.jsonl

Input, one JSON object per line:
  puzzle       anything pencilmark.load reads (a sudoku-puzzle document, a classic string, a link, ...)
  source       where the target comes from ("fed-sudoku.eu", "my club", ...): the report has one row per source
  group        puzzles that are comparable (a difficulty tab, a variant type, a board size): correlations are
               computed within each group and averaged, as in the published benchmark
  target       the human measure, higher = harder (solve time, a skill-corrected effect, a rating)
  target_kind  optional: "log minutes", "minutes", "log seconds" or "seconds" make the report also give the time error;
               anything else is used only for the correlations
  key          optional: an identifier, kept in the output (default: the line number)

grade writes one line per puzzle (the input fields without the puzzle, plus difficulty, time, band, secs, or error) and
resumes: puzzles already in the output file are skipped. report prints, per source: puzzles graded, groups used,
mean within-group Spearman of difficulty and of time with the target, the median |log(real / predicted time)| (raw and
after one per-source scale) where the target is a time, and seconds per card (median / 90th percentile).
"""

import argparse
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

MIN_GROUP = 15  # groups with fewer graded puzzles are left out of the correlations, as in the published benchmark


def _grade(row):
    import pencilmark

    out = {k: v for k, v in row.items() if k != "puzzle"}
    t = time.perf_counter()
    try:
        # only the fields the report reads: the technique list (contains) costs several times the card itself
        card = pencilmark.rate(
            row["puzzle"], fields=["difficulty", "time", "band"], max_seconds=row.pop("_max_seconds", None)
        )
        out.update(difficulty=card.get("difficulty"), time=card.get("time"), band=card.get("band"))
    except Exception as e:  # noqa: BLE001 -- recorded per puzzle, as rate_many does
        out["error"] = f"{type(e).__name__}: {e}"
    out["secs"] = round(time.perf_counter() - t, 3)
    out.pop("_max_seconds", None)
    return out


def grade(src, dst, jobs, max_seconds):
    rows = []
    for k, line in enumerate(Path(src).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            r = json.loads(line)
            r.setdefault("key", k)
            rows.append(r)
    done = set()
    if Path(dst).exists():
        done = {
            (r["source"], str(r["key"])) for r in map(json.loads, Path(dst).read_text(encoding="utf-8").splitlines())
        }
    todo = [dict(r, _max_seconds=max_seconds) for r in rows if (r["source"], str(r["key"])) not in done]
    print(f"{len(rows)} puzzles, {len(todo)} to grade", file=sys.stderr)
    # workers are replaced every 20 puzzles: the engine's caches grow with each puzzle (a 6-worker run of the 7,623
    # frozen puzzles reached 12 GB without this)
    with open(dst, "a", encoding="utf-8") as fh, Pool(jobs, maxtasksperchild=20) as pool:
        for k, out in enumerate(pool.imap_unordered(_grade, todo), 1):
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")
            fh.flush()
            if k % 100 == 0:
                print(f"{k} / {len(todo)}", file=sys.stderr)


def _ranks(xs):
    """ranks 1..n, ties averaged"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(xs, ys):
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else float("nan")


def within(rows, field):
    """(mean within-group Spearman of field with the target, groups used)"""
    groups = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(r)
    rs = [
        spearman([r[field] for r in g], [r["target"] for r in g])
        for g in groups.values()
        if len(g) >= MIN_GROUP and len({r[field] for r in g}) > 2
    ]
    return (sum(rs) / len(rs), len(rs)) if rs else (float("nan"), 0)


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] + xs[(n - 1) // 2]) / 2 if xs else float("nan")


def _quantile(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def _log_minutes(target, kind):
    return {
        "log minutes": lambda t: t,
        "minutes": lambda t: math.log(t),
        "log seconds": lambda t: t - math.log(60),
        "seconds": lambda t: math.log(t / 60),
    }[kind](target)


def report(path):
    G = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ok = [r for r in G if "error" not in r and r.get("difficulty") is not None]
    print(f"{len(G)} puzzles, {len(ok)} graded ({len(ok) / max(len(G), 1):.1%})")
    errs = {}
    for r in G:
        if "error" in r:
            errs[r["error"].split(":")[0]] = errs.get(r["error"].split(":")[0], 0) + 1
    if errs:
        print("not graded:", ", ".join(f"{k} {v}" for k, v in sorted(errs.items(), key=lambda kv: -kv[1])))
    head = f"{'source':16s} {'n':>6s} {'groups':>6s} {'difficulty rho':>14s} {'time rho':>9s} {'time |log err|':>15s}"
    print("\n" + head + f" {'secs med/p90':>13s}")
    for src in sorted({r["source"] for r in G}):
        h = [r for r in ok if r["source"] == src]
        d, ng = within(h, "difficulty")
        t, _ = within(h, "time")
        err = ""
        timed = [
            r for r in h if r.get("target_kind") in ("log minutes", "minutes", "log seconds", "seconds") and r["time"]
        ]
        if timed:
            e = [_log_minutes(r["target"], r["target_kind"]) - math.log(max(r["time"], 0.01)) for r in timed]
            m = _median(e)
            err = f"{_median([abs(x) for x in e]):.2f} / {_median([abs(x - m) for x in e]):.2f}"
        secs = [r["secs"] for r in G if r["source"] == src]
        print(
            f"{src:16s} {len(h):6d} {ng:6d} {d:14.3f} {t:9.3f} {err:>15s} {_median(secs):6.2f}/{_quantile(secs, 0.9):.2f}"
        )
    print(
        f"\nrho: mean Spearman within groups of at least {MIN_GROUP} graded puzzles. time |log err|: median "
        "|log(real / predicted)|, then after one scale per source."
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grade", help="grade the puzzles of a JSONL file")
    g.add_argument("input")
    g.add_argument("-o", "--output", required=True)
    g.add_argument("--jobs", type=int, default=8)
    g.add_argument("--max-seconds", type=float, default=300, help="per card (the published run used 300)")
    r = sub.add_parser("report", help="aggregate numbers from a grades file")
    r.add_argument("grades")
    a = ap.parse_args(argv)
    if a.cmd == "grade":
        grade(a.input, a.output, a.jobs, a.max_seconds)
    else:
        report(a.grades)


if __name__ == "__main__":
    main()
