"""Command-line front end (SE-style).

  python -m pencilmark rate [FILE|-] [--print FMT] [--json] [--steps]
      One puzzle per line, in any format pencilmark reads (pencilmark.read: a plain string, a sudokuwiki packed string,
      a HoDoKu line, pencilmark JSON, an ipuz object, a site link), detected per line. A FILE ending in .json or .ipuz
      that holds one JSON value (a puzzle, or a list of puzzles) is read whole; --from FORMAT names the format instead
      (every command takes it). Prints one
      result line per puzzle. Card "pencilmark-grade": FMT fields %d difficulty (continuous, above 0, no ceiling; ~5 = typical medium),
      %m predicted median solve time in minutes, %p 80th-percentile minutes, %b band, %h hardest technique met,
      %c contents chips (band > 0, with uses), %n issue codes, %s status ("ok" or the error), %u unique?, %i line number.
      Default: "%b\t%d\t%m\t%h". --json prints the full card (add --steps for the step list, --explain for its
      explanations, --fields to choose fields); --report a readable summary. A puzzle without exactly one solution
      prints its error ({"line", "error"} with --json).
  python -m pencilmark solve [FILE|-]      the solution (or 'not unique' / 'no solution' / 'undecided') per puzzle
  python -m pencilmark count [FILE|-] [--limit N]   how many solutions per puzzle (">=N" when it stops at N)
  python -m pencilmark generate [SPEC|-] [--result]
                                       a puzzle for a "pencilmark-spec" request (docs/formats/generator-spec.md), as a pencilmark-puzzle file
  python -m pencilmark convert [FILE|-] [--to pencilmark|plain|grid|sudokuwiki|ipuz] [--pretty] [--no-solution] [--no-style]
                                       each puzzle in another format; pencilmark JSON (docs/formats/puzzle-format.md) by default, canonical
  python -m pencilmark fingerprint [FILE|-]  the content fingerprint (64 hex digits) per puzzle
  python -m pencilmark describe [FILE|-]     variant name and rules per puzzle (JSON)

Every command takes --log info (pages fetched, what a reader read, time limits reached, the generator's result) or
--log debug (also stage timings, the uniqueness check, each generator attempt and each reading a reader tried), written
to standard error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import puzzle_json as PJ
from .read import auto


def _whole_json(src):
    """the puzzles of a .json / .ipuz file that holds ONE JSON value (a puzzle, or a list of puzzles), or None when the file is
    one puzzle per line"""
    if src in (None, "-") or not src.endswith((".json", ".ipuz")):
        return None
    try:
        obj = json.loads(Path(src).read_text(encoding="utf-8"))
    except ValueError:
        return None
    return obj if isinstance(obj, list) else [obj]


def _inputs(src, fmt=None):
    """(number, pencilmark-puzzle dict) per input, each read in its own format (detected, or fmt: --from); an input
    that cannot be read gives (number, the exception), so the command reports it in place and goes on"""
    whole = _whole_json(src)
    if whole is not None:
        for k, obj in enumerate(whole, 1):
            yield k, _read(lambda: auto(obj, format=fmt))
        return
    fh = sys.stdin if src in (None, "-") else open(src, encoding="utf-8")
    for k, line in enumerate(fh, 1):
        line = line.strip()
        if line and not line.startswith("#"):
            yield k, _read(lambda: auto(line, format=fmt))


def _read(fn):
    try:
        return fn()
    except Exception as e:
        return e


def _ok(obj):
    """the document of an input, raising the error of one that could not be read"""
    if isinstance(obj, Exception):
        raise obj
    return obj


def _each(a, fn):
    """fn(k, document) for every input; a failing input prints "error<TAB>k<TAB>message" and the rest go on"""
    for k, obj in _inputs(a.file, a.input_format):
        try:
            fn(k, _ok(obj))
        except Exception as e:
            print(f"error\t{k}\t{type(e).__name__}: {e}", flush=True)


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
    """Readable summary of the pencilmark-grade card."""
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
    """--quality "preset=standard,trivial.limit=0.5" -> {"preset": "standard", "trivial": {"limit": 0.5}}"""
    if not text:
        return {}
    from .publish_flags import quality_limits

    out = {}
    for part in text.split(","):
        k, _, v = part.partition("=")
        if k.strip() == "preset":
            out["preset"] = v.strip().lower()
            continue
        check, dot, key = k.strip().partition(".")
        if not dot or key not in ("limit", "severity"):
            raise ValueError(f"{part!r}: expected check.limit=N or check.severity=reject|warning|off")
        out.setdefault(check, {})[key] = float(v) if key == "limit" else v.strip().lower()
    quality_limits(out)
    return out


def _log_to_stderr(level):
    """--log: the "pencilmark" logger to standard error at this level (once per process: -j workers call it too)"""
    import logging

    log = logging.getLogger("pencilmark")
    if level and not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        log.addHandler(h)
        log.setLevel(level.upper())


def _rate_one(args):
    """one input line -> its output text (runs in a worker process with -j). The card is api.rate's (fog under the fog,
    Unknown with a reason where no route exists or uniqueness is not settled); a puzzle that is not unique or has no
    solution prints that instead."""
    k, obj, a = args
    _log_to_stderr(a.log)
    from . import api
    from .export import card_fields

    fmt = a.print or "%b\\t%d\\t%m\\t%h"
    try:
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
        try:
            g = api.rate(
                _ok(obj),
                max_seconds=a.max_seconds,
                mode="computer" if a.computer else "human",
                fields=sorted(want),
                allow_guessing=bool(a.allow_guessing),
                explain=explain,
                quality=_quality_arg(a.quality),
                alternatives=not a.no_alternatives,
                colouring=bool(getattr(a, "colouring", False)),
            )
        except (api.NotUnique, api.NoSolution) as e:
            st = "not unique" if isinstance(e, api.NotUnique) else "no solution"
            return _fmt2(fmt, {"error": st}, k, False) if not a.json else json.dumps({"line": k, "error": st})
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
    """`rate` command: print one grading line per input puzzle (a worker pool when --jobs > 1)"""
    try:
        _quality_arg(a.quality)
    except ValueError as e:
        raise SystemExit(f"--quality: {e}")
    items = ((k, obj, a) for k, obj in _inputs(a.file, a.input_format))
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
    """`solve` command: print each input puzzle's solution, or not unique / undecided / no solution"""
    from . import api
    from . import cpsat_verify as V

    def one(k, obj):
        p = api._load(obj)
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


def cmd_count(a):
    """`count` command: print each input puzzle's number of solutions (>=N when cut off at --limit)"""
    from .api import count_solutions

    def one(k, obj):
        r = count_solutions(obj, limit=a.limit)
        print(r["count"] if r["exact"] else f">={r['count']}", flush=True)

    _each(a, one)


def cmd_generate(a):
    """`generate` command: generate a puzzle from a spec (file or stdin); --result prints the whole result"""
    from .api import generate
    from .exchange import dumps

    spec = json.load(sys.stdin) if a.spec in (None, "-") else json.loads(Path(a.spec).read_text(encoding="utf-8"))
    r = generate(spec)
    if a.result:
        print(json.dumps(r, ensure_ascii=False, default=str))
    else:
        print(dumps(r["puzzle"], pretty=True), end="")
        c = r["card"]
        print(f"{c.get('band')}  difficulty {c.get('difficulty')}  time {c.get('time')} min", file=sys.stderr)
    for w in r["info"].get("warnings") or []:
        print(f"note: {w}", file=sys.stderr)


def cmd_convert(a):
    """`convert` command: print each input puzzle in the --to format (pencilmark JSON by default: with its solution
    unless --no-solution, the rules' drawing styles unless --no-style, one line unless --pretty)"""
    from . import write
    from .exchange import dumps

    def one(k, obj):
        if a.to == "pencilmark":
            d = write.document(obj, solution=not a.no_solution)
            if a.no_style:
                d = dict(d, rules=[{k2: v for k2, v in r.items() if k2 != "style"} for r in d["rules"]])
            print(dumps(d, pretty=a.pretty), end="" if a.pretty else "\n", flush=True)
        elif a.to == "ipuz":
            print(json.dumps(write.ipuz(obj), ensure_ascii=False), flush=True)
        else:
            print(getattr(write, a.to)(obj), flush=True)

    _each(a, one)


def cmd_fingerprint(a):
    """`fingerprint` command: print the fingerprint of each input puzzle"""
    from .api import fingerprint

    _each(a, lambda k, obj: print(fingerprint(obj), flush=True))


def cmd_describe(a):
    """`describe` command: print the description of each input puzzle as one line of JSON"""
    from .api import describe

    _each(a, lambda k, obj: print(json.dumps(describe(obj), ensure_ascii=False), flush=True))


def main(argv=None):
    """command-line entry point: parse argv, set UTF-8 on stdin and stdout, run the chosen command"""
    for f in (sys.stdin, sys.stdout):  # UTF-8 on every platform (Windows pipes default to the ANSI code page)
        try:
            f.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        prog="python -m pencilmark", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--log", choices=("info", "debug"), help="write the pencilmark log to standard error at this level"
    )
    from .read import READERS

    common.add_argument(
        "--from",
        dest="input_format",
        choices=list(READERS),
        default=None,
        help="the inputs' format (pencilmark.read); default: detected per line",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rate", parents=[common])
    r.add_argument("file", nargs="?")
    r.add_argument("--print", default=None, help="the output line template (%%b band, %%d difficulty, ...)")
    r.add_argument("--json", action="store_true")
    r.add_argument("--report", action="store_true")
    r.add_argument(
        "--computer",
        action="store_true",
        help="allow pure computer search (forcing chains / nets, trial); default: human mode",
    )
    r.add_argument(
        "--colouring",
        action="store_true",
        help="opt in to colouring as a solving method (colours kept through the solve); off by default",
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
        help='issue checks, e.g. "trivial.limit=0.5,trial.severity=reject,tedious.severity=off" (docs/formats/grade-card.md 4)',
    )
    r.add_argument(
        "--explain", default=None, help="step explanation levels, comma-separated: notation, short, teach, substeps"
    )
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
        help="card fields, comma-separated (docs/formats/grade-card.md 2), e.g. difficulty,band,time_p80,steps",
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
    s = sub.add_parser("solve", parents=[common])
    s.add_argument("file", nargs="?")
    s.set_defaults(fn=cmd_solve)
    c = sub.add_parser("count", parents=[common])
    c.add_argument("file", nargs="?")
    c.add_argument("--limit", type=int, default=1000, help="stop counting here (prints >=N)")
    c.set_defaults(fn=cmd_count)
    g = sub.add_parser("generate", parents=[common])
    g.add_argument(
        "spec", nargs="?", help="a pencilmark-spec file (docs/formats/generator-spec.md), or - for standard input"
    )
    g.add_argument("--result", action="store_true", help='print {"puzzle", "card", "info"} as one JSON line')
    g.set_defaults(fn=cmd_generate)
    e = sub.add_parser("convert", parents=[common])
    e.add_argument("file", nargs="?")
    e.add_argument(
        "--to",
        choices=("pencilmark", "plain", "grid", "sudokuwiki", "ipuz"),
        default="pencilmark",
        help="output format",
    )
    e.add_argument("--pretty", action="store_true")
    e.add_argument("--no-solution", action="store_true", help="do not solve to add the solution")
    e.add_argument("--no-style", action="store_true", help="leave out how the source drew the rules (colours, shapes)")
    e.set_defaults(fn=cmd_convert)
    f = sub.add_parser("fingerprint", parents=[common])
    f.add_argument("file", nargs="?")
    f.set_defaults(fn=cmd_fingerprint)
    ds = sub.add_parser("describe", parents=[common])
    ds.add_argument("file", nargs="?")
    ds.set_defaults(fn=cmd_describe)
    a = ap.parse_args(argv)
    _log_to_stderr(a.log)
    from .api import GenerationFailed
    from .exchange import FormatError, NotSupportedError

    try:
        a.fn(a)
    except BrokenPipeError:  # the reader stopped early (`| head`): end quietly, as other command-line tools do
        import os

        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)
    except (OSError, json.JSONDecodeError, GenerationFailed, FormatError, NotSupportedError) as e:
        # a file that cannot be read, a spec that is not JSON or cannot be met: one line, not a traceback
        print(f"pencilmark {a.cmd}: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
