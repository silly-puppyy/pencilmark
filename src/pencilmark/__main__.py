"""Command-line front end (SE-style).

  python -m pencilmark rate [FILE|-] [--format FMT] [--json] [--steps]
      One puzzle per line: a classic string ('.'/'0' blanks; 16 / 36 / 81 / 256 / 625 symbols), a JSON object in the
      pencilmark.puzzle_json format or the sudoku-puzzle exchange format (pencilmark.export), or a path to a .json file. A
      FILE ending in .json that holds one JSON value (a puzzle, or a list of puzzles) is read whole. Prints one
      result line per puzzle. Card "sudoku-grade": FMT fields %d difficulty (continuous, above 0, no ceiling; ~5 = typical medium),
      %m time in minutes for today's average player, %p 80th-percentile minutes, %b band, %h hardest technique met,
      %c contents chips (band > 0, with uses), %n issue codes, %s status ("ok" or the error), %u unique?, %i line number.
      Default: "%b\t%d\t%m\t%h". --json prints the full card (add --steps for the step list, --explain for its
      explanations, --fields to choose fields); --report a readable summary. A puzzle without exactly one solution
      prints its error ({"line", "error"} with --json).
  python -m pencilmark solve [FILE|-]      the solution (or 'not unique' / 'no solution') per puzzle
  python -m pencilmark json  [FILE|-]      validate + normalise to canonical JSON (adds "hash")
  python -m pencilmark export [FILE|-] [--pretty] [--no-solution]
                                       each puzzle as a "sudoku-puzzle" file (format_version 1, docs/FORMAT.md), canonical
  python -m pencilmark fingerprint [FILE|-]  the content fingerprint ("sha256:...") per puzzle
  python -m pencilmark describe [FILE|-]     variant name and rules per puzzle (JSON)
Inputs may also be sudokuwiki.org packed strings (S9B..., L9B..., J9B...).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import puzzle_json as PJ


def _params():
    """the engine parameters shipped with the package (data/params.json), completed with defaults."""
    from . import _data
    from .scoring import complete_params

    return complete_params(_data.load_params("params.json"))


def _whole_json(src):
    """the puzzles of a .json file that holds ONE JSON value (a puzzle, or a list of puzzles), or None when the file is
    one puzzle per line"""
    if src in (None, "-") or not src.endswith(".json"):
        return None
    try:
        obj = json.loads(Path(src).read_text(encoding="utf-8"))
    except ValueError:
        return None
    return obj if isinstance(obj, list) else [obj]


def _inputs(src):
    """(number, puzzle JSON) per input; an input that cannot be read gives (number, the exception), so the command
    reports it in place and goes on"""
    whole = _whole_json(src)
    if whole is not None:
        for k, obj in enumerate(whole, 1):
            yield k, _read(lambda: _to_puzzle_json(obj))
        return
    fh = sys.stdin if src in (None, "-") else open(src, encoding="utf-8")
    for k, line in enumerate(fh, 1):
        line = line.strip()
        if line and not line.startswith("#"):
            yield k, _read(lambda: _line_puzzle(line))


def _read(fn):
    try:
        return fn()
    except Exception as e:
        return e


def _line_puzzle(line):
    if line.startswith("{"):
        return _to_puzzle_json(json.loads(line))
    if line.endswith(".json") and Path(line).exists():
        return _to_puzzle_json(json.load(open(line, encoding="utf-8")))
    tok = line.split()[0]
    from .interop import _PACKED, from_string

    return _to_puzzle_json(from_string(tok)) if _PACKED.fullmatch(tok) else {"numbers": tok}


def _ok(obj):
    """the puzzle JSON of an input, raising the error of one that could not be read"""
    if isinstance(obj, Exception):
        raise obj
    return obj


def _each(a, fn):
    """fn(k, puzzle JSON) for every input; a failing input prints "error<TAB>k<TAB>message" and the rest go on"""
    for k, obj in _inputs(a.file):
        try:
            fn(k, _ok(obj))
        except Exception as e:
            print(f"error\t{k}\t{type(e).__name__}: {e}", flush=True)


def _to_puzzle_json(obj):
    """accept puzzle JSON, the sudoku-puzzle exchange format, or a
    sample-pack line {"puzzle": ..., "grade": ...}."""
    if "puzzle" in obj and isinstance(obj["puzzle"], dict):
        obj = obj["puzzle"]
    if obj.get("format") == "sudoku-puzzle":
        from .export import import_puzzle

        return import_puzzle(obj)
    return obj


def _fmt2(fmt, g, k, unique):
    cont = g.get("contains") or []
    hard = [c for c in cont if c.get("band", 0) > 0]
    vals = {
        "d": "" if g.get("difficulty") is None else f"{g['difficulty']:.1f}",
        "m": "" if g.get("time") is None else f"{g['time']:.1f}",
        "p": "" if g.get("time_p80") is None else f"{g['time_p80']:.1f}",
        "b": g.get("band", g.get("error", "")),
        "h": hard[-1]["name"] if hard else (cont[-1]["name"] if cont else ""),
        "c": " ".join(c["chip"] + (f"x{c['uses']}" if c.get("uses", 0) > 1 else "") for c in hard),
        "n": ";".join(n.get("code") or n["text"] for n in g.get("issues") or []),
        "s": g.get("error", "ok"),
        "u": str(unique),
        "i": str(k),
    }
    return _subst(fmt, vals)


def _subst(fmt, vals):
    out, i = [], 0
    while i < len(fmt):
        if fmt[i] == "%" and i + 1 < len(fmt):
            out.append(vals.get(fmt[i + 1], "%" + fmt[i + 1]))
            i += 2
        elif fmt[i] == "\\" and fmt[i + 1 : i + 2] == "t":
            out.append("\t")
            i += 2
        else:
            out.append(fmt[i])
            i += 1
    return "".join(out)


def report2(g, k=None):
    """Readable summary of the sudoku-grade card."""
    if "band" not in g:
        return f"[{k}] {g.get('error')}"
    L = [
        f"{'#' + str(k) + '  ' if k else ''}{g['band']}  -  difficulty {g.get('difficulty')}  -  time {g.get('time')} min"
        + "".join(
            f" (mean {v} min)" if k == "time_mean" else f" ({k[6:]}% of players within {v} min)"
            for k, v in g.items()
            if k.startswith("time_") and v is not None
        )
    ]
    from .export import SINGLE_CODES, code_names

    names = code_names()
    hard = [c for c in g.get("contains") or [] if c["code"] not in SINGLE_CODES]
    L.append(
        "   contains: "
        + (
            ", ".join(
                f"{c['name']}{' x' + str(c['uses']) if c.get('uses', 0) > 1 else ''}"
                f"{' (or ' + ' / '.join(names.get(a, a) for a in c['alternatives']) + ')' if c.get('alternatives') else ''}"
                for c in hard
            )
            if hard
            else "singles only"
        )
    )
    if g.get("completed") is False and g.get("band") != "Unknown":
        L.append("   (time cap hit: contents not minimised; joint alternatives may be missing)")
    if g.get("stopped_at_step"):
        L.append(f"   human logic ran out at step {g.get('stopped_at_step')}; contents incomplete")
    for st in g.get("steps") or []:
        ex = st.get("explanation") or {}
        text = ex.get("teach") or ex.get("short") or ex.get("notation")
        if text and (st["code"] not in SINGLE_CODES or ex.get("teach") or ex.get("short")):  # -v: singles stay silent
            L.append(f"   {st['n']:>3}. " + text.replace("\n", "\n        "))
    for n in g.get("issues") or []:
        L.append(f"   {'reject' if n['severity'] == 'reject' else 'note'}: {n['text']}")
    return "\n".join(L)


def _quality_arg(text):
    """--quality "trivial.limit=0.5,trial.severity=reject" -> {"trivial": {"limit": 0.5}, "trial": {"severity": "reject"}}"""
    if not text:
        return {}
    from .publish_flags import quality_limits

    out = {}
    for part in text.split(","):
        k, _, v = part.partition("=")
        check, dot, key = k.strip().partition(".")
        if not dot or key not in ("limit", "severity"):
            raise ValueError(f"{part!r}: expected check.limit=N or check.severity=reject|warning|off")
        out.setdefault(check, {})[key] = float(v) if key == "limit" else v.strip().lower()
    quality_limits(out)
    return out


def _rate_one(args):
    """one input line -> its output text (runs in a worker process with -j)."""
    k, obj, a = args
    from . import cpsat_verify as V
    from .export import grade

    P = dict(
        _params(),
        search="computer" if a.computer else "human",
        allow_guess=bool(a.allow_guessing),
        quality=_quality_arg(a.quality),
    )
    fmt = a.format or "%b\\t%d\\t%m\\t%h"
    try:
        p = PJ.from_json(_ok(obj))
        p.finalize()
        sols, decided = V.decide(p, limit=2)
        if len(sols) != 1 or not decided:
            st = (
                "not unique" if len(sols) > 1 else "undecided (" + V.VERIFY_HINT + ")" if not decided else "no solution"
            )
            return _fmt2(fmt, {"error": st}, k, False) if not a.json else json.dumps({"line": k, "error": st})
        p._pm_solution = list(sols[0])  # proven unique: later stages reuse it
        from .export import card_fields

        fl = a.fields.split(",") if a.fields else None
        if fl is None and "%p" in fmt:  # the %p placeholder asks for time_p80; the report shows pNN only on request
            fl = list(card_fields(None)) + ["time_p80"]
        if "%n" in fmt:
            fl = list(fl or card_fields(None)) + ["issues"]
        verbose = getattr(a, "verbose", 0) if a.report else 0
        want = card_fields(fl, steps=a.steps or verbose > 0)
        explain = (
            a.explain.split(",")
            if a.explain
            else (["notation", "short", "teach"][min(verbose, 3) - 1] if verbose else True if a.steps else None)
        )
        g = grade(
            p, P, max_seconds=a.max_seconds, fields=sorted(want), explain=explain, alternatives=not a.no_alternatives
        )
        return (
            json.dumps({"line": k, **g}, default=str)
            if a.json
            else report2(g, k)
            if a.report
            else _fmt2(fmt, g, k, True)
        )
    except Exception as e:
        if a.json:
            return json.dumps({"line": k, "error": f"{type(e).__name__}: {e}"})
        return f"error\t{k}\t{type(e).__name__}: {e}"


def cmd_rate(a):
    try:
        _quality_arg(a.quality)
    except ValueError as e:
        raise SystemExit(f"--quality: {e}")
    items = ((k, obj, a) for k, obj in _inputs(a.file))
    if a.jobs <= 1:
        for it in items:
            print(_rate_one(it), flush=True)
        return
    import importlib

    from .api import _mp_context

    # spawn (Windows, macOS) does not re-import a package's __main__ in the workers, so the worker function and the options
    # must come from the importable module, and the options must not carry cmd_rate (a function of this __main__)
    worker = importlib.import_module("pencilmark.__main__")._rate_one
    opts = argparse.Namespace(**{k: v for k, v in vars(a).items() if k != "fn"})
    items = [(k, obj, opts) for k, obj, _ in items]  # all input read first (a pending stdin read blocks spawning)
    with _mp_context().Pool(a.jobs, maxtasksperchild=50) as pool:  # output stays in input order
        for out in pool.imap(worker, items, chunksize=1):
            print(out, flush=True)


def cmd_solve(a):
    from . import cpsat_verify as V

    def one(k, obj):
        p = PJ.from_json(obj)
        p.finalize()
        sols, decided = V.decide(p, limit=2)
        print(
            "not unique"
            if len(sols) > 1
            else "undecided"
            if not decided
            else "".join(PJ._sym(v) for v in sols[0])
            if sols
            else "no solution",
            flush=True,
        )

    _each(a, one)


def cmd_json(a):
    from .export import read_meta

    def one(k, obj):
        d = PJ.to_json(PJ.from_json(obj), meta=read_meta(obj))
        d["hash"] = PJ.canonical_hash(d)
        print(json.dumps(d, separators=(",", ":")), flush=True)

    _each(a, one)


def cmd_export(a):
    from .api import dumps, to_export

    def one(k, obj):
        d = to_export(obj, with_solution=not a.no_solution)
        print(dumps(d, pretty=a.pretty), end="" if a.pretty else "\n", flush=True)

    _each(a, one)


def cmd_fingerprint(a):
    from .api import fingerprint

    _each(a, lambda k, obj: print(fingerprint(obj), flush=True))


def cmd_describe(a):
    from .api import describe, to_export

    _each(
        a,
        lambda k, obj: print(
            json.dumps(describe(to_export(obj, with_solution=False, describe=False)), ensure_ascii=False), flush=True
        ),
    )


def main(argv=None):
    for f in (sys.stdin, sys.stdout):  # UTF-8 on every platform (Windows pipes default to the ANSI code page)
        try:
            f.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        prog="python -m pencilmark", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rate")
    r.add_argument("file", nargs="?")
    r.add_argument("--format", default=None)
    r.add_argument("--json", action="store_true")
    r.add_argument("--report", action="store_true")
    r.add_argument(
        "--computer",
        action="store_true",
        help="allow pure computer search (forcing chains / nets, trial); default: human mode",
    )
    r.add_argument(
        "--no-alternatives",
        action="store_true",
        help="skip the search for interchangeable techniques "
        "(one code per contents chip; same band, difficulty and time, much faster)",
    )
    r.add_argument(
        "--allow-guessing",
        action="store_true",
        help="guess where no technique applies (faster; band Unknown) "
        "instead of proving by full search (Trial and error, band Extreme)",
    )
    r.add_argument(
        "--steps",
        action="store_true",
        help="with --json: include the step-by-step solve (with both explanation levels)",
    )
    r.add_argument(
        "--quality",
        default=None,
        help='issue checks, e.g. "trivial.limit=0.5,trial.severity=reject,tedious.severity=off" (docs/GRADE.md 4)',
    )
    r.add_argument("--explain", default=None, help="step explanation levels, comma-separated: notation, short, teach")
    r.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="with --report: list the steps; -v in solvers' "
        "notation (X-Wing: 3 r58 c68 => r679c6<>3), -vv as plain sentences, -vvv as short lessons",
    )
    r.add_argument(
        "--fields",
        default=None,
        help="card fields, comma-separated (docs/GRADE.md 2), e.g. difficulty,band,time_p80,steps",
    )
    r.add_argument(
        "-j", "--jobs", type=int, default=1, help="rate puzzles in N parallel processes (output in input order)"
    )
    r.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="cap the whole call (opt-in; the card then says completed and may differ run to run)",
    )
    r.set_defaults(fn=cmd_rate)
    s = sub.add_parser("solve")
    s.add_argument("file", nargs="?")
    s.set_defaults(fn=cmd_solve)
    j = sub.add_parser("json")
    j.add_argument("file", nargs="?")
    j.set_defaults(fn=cmd_json)
    e = sub.add_parser("export")
    e.add_argument("file", nargs="?")
    e.add_argument("--pretty", action="store_true")
    e.add_argument("--no-solution", action="store_true", help="do not solve to add the solution")
    e.set_defaults(fn=cmd_export)
    f = sub.add_parser("fingerprint")
    f.add_argument("file", nargs="?")
    f.set_defaults(fn=cmd_fingerprint)
    ds = sub.add_parser("describe")
    ds.add_argument("file", nargs="?")
    ds.set_defaults(fn=cmd_describe)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
