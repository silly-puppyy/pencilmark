"""Run the generator examples and keep what they produce in docs/examples/generated/<name>.json ({"title", "shows",
"spec", "puzzle", "card", "info"}); the Generator examples page shows each request, the drawn puzzle
(tools/gen_swatches.py), its card and how long the run took. Two groups: curiosities (each shows another side of the
generator spec), and larger requests: multi-grid layouts (a super samurai with a variant per row of grids, harder to
the right) and the requests kept in docs/examples/specs/. Generation takes a few hours in all and the same seed gives the same puzzle, so the results are committed;
run this again when the generator changes.
  python tools/gen_generator_examples.py [name ...] [--jobs N]     (--page: only rewrite the page)"""

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "examples" / "generated"
SPECS = ROOT / "docs" / "examples" / "specs"
BOX = {4: [2, 2], 6: [2, 3], 8: [2, 4], 9: [3, 3]}


def spec(size=9, rules=(), where=None, givens=None, symmetry=None, seed=1, time=180, quality=None):
    s = {"format": "sudoku-spec", "format_version": 1, "board": {"rows": size, "cols": size}, "digits": size,
         "rules": [{"type": "box_grid", "origin": "r1c1", "box": BOX[size]}, *rules]}  # fmt: skip
    if givens:
        s["givens"] = givens
    if symmetry:
        s["symmetry"] = [dict(symmetry, of="givens")]
    if where:
        s["where"] = where
    s["quality"] = quality if quality is not None else {}  # every example: the default publishing checks
    s["limits"] = {"time": time, "seed": seed}
    return s


def layout_spec(layout, rules=(), locked=(), where=None, givens=None, symmetry=None, seed=1, time=1800):
    """a request for a named layout of 9 x 9 grids (one box_grid rule per grid)"""
    from pencilmark import puzzle_json as PJ

    origins = PJ._layouts()[layout]
    s = {"format": "sudoku-spec", "format_version": 1,
         "board": {"rows": max(r for r, _ in origins) + 9, "cols": max(c for _, c in origins) + 9}, "digits": 9,
         "rules": [{"type": "box_grid", "origin": f"r{r + 1}c{c + 1}", "box": [3, 3]} for r, c in origins]
         + list(locked) + list(rules)}  # fmt: skip
    if givens:
        s["givens"] = givens
    if symmetry:
        s["symmetry"] = [dict(symmetry, of="givens")]
    if where:
        s["where"] = where
    s["quality"] = {}  # every example: the default publishing checks
    s["limits"] = {"time": time, "seed": seed}
    return s


def nm(r, c):
    return f"r{r + 1}c{c + 1}"


def diagonals(o):
    """X-sudoku diagonals of the 9 x 9 grid at origin o"""
    r0, c0 = o
    return [{"type": "region", "kind": "diagonal", "cells": [nm(r0 + i, c0 + i) for i in range(9)]},
            {"type": "region", "kind": "diagonal", "cells": [nm(r0 + i, c0 + 8 - i) for i in range(9)]}]  # fmt: skip


def windows(o):
    """windoku's four extra boxes of the grid at origin o"""
    r0, c0 = o
    return [{"type": "region", "kind": "window", "cells": [nm(r0 + a + i, c0 + b + j) for i in range(3) for j in range(3)]}
            for a in (1, 5) for b in (1, 5)]  # fmt: skip


def asterisk(o):
    """the asterisk's extra region of the grid at origin o"""
    r0, c0 = o
    cells = [(1, 4), (2, 1), (2, 7), (4, 0), (4, 4), (4, 8), (6, 1), (6, 7), (7, 4)]
    return [{"type": "region", "kind": "extra", "cells": [nm(r0 + r, c0 + c) for r, c in cells]}]


SUPER = [(0, 0), (0, 12), (0, 24), (6, 6), (6, 18), (12, 0), (12, 12), (12, 24)]  # super-samurai origins
# a variant per row of grids: X on top, windoku in the middle, asterisk at the bottom
SUPER_LOCKED = (
    [x for o in SUPER[:3] for x in diagonals(o)]
    + [x for o in SUPER[3:5] for x in windows(o)]
    + [x for o in SUPER[5:] for x in asterisk(o)]
)
# harder to the right: more givens kept in the grids on the left (floors per grid, origins in reading order)
SUPER_FLOOR = {0: 38, 6: 32, 12: 27, 18: 23, 24: 0}


def from_file(name):
    return json.loads((SPECS / name).read_text(encoding="utf-8"))


# name -> (title, what it shows, spec)
CURIOSITIES = {
    "tens": (
        "As many 10-cages as fit",
        'a cage `sum` and the count `"max"`: the run uses its whole time and keeps the result with the most cages',
        spec(rules=[{"type": "cage", "sum": 10, "count": "max"}], time=300),
    ),
    "long-whisper": (
        "One whisper, 25 cells or more",
        "a line `length` with no upper bound, and 180° symmetry of the givens",
        spec(
            rules=[{"type": "line", "kind": "whisper", "length": [25, None], "count": 1}],
            symmetry={"kind": "rot180"},
            time=300,
        ),
    ),
    "long-lines": (
        "Long whispers and renbans",
        'lengths on two templates at once: whispers of 7 cells or more, renbans of at least 5 ("auto": as many as needed)',
        spec(
            rules=[
                {"type": "line", "kind": "whisper", "length": [7, None], "count": 2},
                {"type": "line", "kind": "renban", "length": [5, None], "count": "auto"},
            ],
            time=600,
        ),
    ),
    "tall-thermos": (
        "Three tall thermometers",
        "an exact count with a length range: three thermos of 7 to 9 cells",
        spec(rules=[{"type": "line", "kind": "thermo", "length": [7, 9], "count": 3}]),
    ),
    "gentlest-xwing": (
        "The gentlest X-Wing",
        'difficulty `"min"` with a required technique: the easiest puzzle found in the time that still needs an X-Wing',
        spec(where={"difficulty": "min", "contains": {"codes": ["XWG"], "strict": True}}, time=300),
    ),
    "hardest-kropki": (
        "The hardest 0-clue 6×6 kropki",
        'difficulty `"max"`: no givens, a minimal set of dots (count `"min"`), the hardest found in the time',
        from_file("hardest_0clue_6x6_kropki.json"),
    ),
    "evens": (
        "Every even cell shaded",
        'the count `"max"` on a cell template: every even cell is marked, and the run keeps the result with the fewest givens',
        spec(rules=[{"type": "cell", "kind": "even", "count": "max"}], time=300),
    ),
    "x-only": (
        "Only X, no V",
        "an exact count of 0 forbids a letter: as many X clues as fit and no V",
        spec(
            rules=[
                {"type": "edge", "kind": "xv", "letter": "X", "count": "max"},
                {"type": "edge", "kind": "xv", "letter": "V", "count": 0},
            ],
            time=300,
        ),
    ),
    "tiled-6x6": (
        "A 6×6 killer tiled by cages",
        'the count `"tile"`: cages cover the whole board',
        spec(6, [{"type": "cage", "count": "tile"}]),
    ),
    "tiny-4x4-rot90": (
        "A 4×4 with quarter-turn symmetry",
        "the smallest board; 90° symmetry (it needs square boxes)",
        spec(4, symmetry={"kind": "rot90"}),
    ),
    "kropki-8x8-capped": (
        "An 8×8 with at most six dots",
        "an 8×8 board and the element cap (`where.elements`)",
        spec(8, [{"type": "edge", "kind": "kropki", "count": "auto"}], where={"elements": {"max": 6}}),
    ),
}
MULTI = {
    "super-samurai": (
        "A super samurai: a variant per row, harder to the right",
        "eight overlapping grids (box_grid rules at the super-samurai origins), locked rules per row of grids (X "
        "diagonals on top, windoku windows in the middle, an asterisk at the bottom) and a given floor per grid "
        "(`givens.grids`) that thins out from left to right",
        layout_spec(
            "super-samurai",
            locked=SUPER_LOCKED,
            givens={"grids": [[SUPER_FLOOR[c], None] for _r, c in sorted(SUPER)]},
            time=3600,
        ),  # fmt: skip
    ),
    "samurai": (
        "A samurai",
        "a named layout: five grids sharing their corner boxes, 180° symmetry of the givens",
        layout_spec("samurai", symmetry={"kind": "rot180"}, time=1800),
    ),
    "twodoku": (
        "Twodoku, Hard",
        "two grids sharing a box, with a band target",
        layout_spec("twodoku", where={"band": "Hard"}, time=900),
    ),
    "butterfly": (
        "A butterfly killer",
        "four grids overlapping on a 12 × 12 board, with cages",
        layout_spec("butterfly", rules=[{"type": "cage", "count": [6, None]}], time=1800),
    ),
}
LARGER = {
    "killer-whispers": ("Killer with German whispers and two givens", "", from_file("killer_whispers_2givens.json")),
    "zero-clue-kropki": ("A 0-clue 6×6 kropki", "", from_file("zero_clue_6x6_kropki.json")),
    "nine-variants": ("Nine variants on one 9×9", "", from_file("nine_variants_9x9.json")),
}
EXAMPLES = {**CURIOSITIES, **MULTI, **LARGER}


def run(name):
    import time

    import pencilmark

    title, shows, s = EXAMPLES[name]
    t = time.time()
    try:
        r = pencilmark.generate(s)
    except pencilmark.GenerationFailed as e:
        return name, f"failed after {time.time() - t:.0f} s: {e}"
    card = {k: r["card"].get(k) for k in ("band", "difficulty", "time", "contains")}
    info = {k: r["info"].get(k) for k in ("seconds", "attempts", "found", "givens", "elements", "rejected")}
    info["seconds"] = round(time.time() - t, 1)  # the whole call, the final grading included
    d = {"title": title, "shows": shows, "spec": s, "puzzle": r["puzzle"], "card": card, "info": info}
    (OUT / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return name, f"{card['band']} {card['difficulty']} in {info['seconds']} s"


PAGE = ROOT / "docs" / "guides" / "generator" / "generator-examples.mdx"
HEAD = """---
title: Generator examples
description: "Generator requests and what they produced: curiosities and larger requests (multi-grid layouts among them), each with its card and how long the run took."
---

import Swatch from '@site/src/components/Swatch';

# Generator examples

Requests in the [generator spec](../../formats/generator-spec.md) language, each with the puzzle it produced, its card and
how long the run took on one core of a desktop machine. The seed fixes the result: the same request on the same version
gives the same puzzle. A run that searches for the most of something, or the hardest or easiest puzzle, always uses
its whole `limits.time` and returns the best it found. The times include grading the result in full, which for a hard
variant can take longer than the search itself. Written by `tools/gen_generator_examples.py`; the request files
are in [`docs/examples/specs/`](https://github.com/silly-puppyy/pencilmark/tree/main/docs/examples/specs).

## Curiosities

Each shows another side of the spec.
"""
LARGER_HEAD = """
## Larger requests

Multi-grid layouts, a request is a puzzle file with blanks: one `box_grid` rule per grid (the origins of a named
layout: samurai, super-samurai, twodoku, butterfly, ...), locked rules every result carries (diagonals, extra regions,
windoku windows, anti-knight, anti-king: rules of different digits), and givens per grid (`givens.grids`, the grids in
reading order of their origins). Then requests kept as files in `docs/examples/specs/`; run one with
`pencilmark generate FILE`.
"""
LATER = """
## Not possible yet

`docs/examples/specs/reserved/` holds requests that use parts reserved for later versions of the spec
([Generator spec](../../formats/generator-spec.md), section 7); the generator refuses them today: a classic with
exactly one X-Wing, givens in the shape of a heart and a displaced jigsaw. A 16×16 killer with exactly 32 cages and no
givens is also out of reach: the uniqueness search does not finish.
"""


def load(name):
    f = OUT / f"{name}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def took(d):
    """how the run went, in words (with the candidates the publishing checks refused, if any)"""
    i, lim = d.get("info") or {}, d["spec"].get("limits", {}).get("time", 120)
    checks = {k.split(": ", 1)[1]: v for k, v in (i.get("rejected") or {}).items() if k.startswith("publishing check")}
    refused = (
        f"; the publishing checks refused {sum(checks.values())} other candidates ({', '.join(sorted(checks))})"
        if checks
        else ""
    )
    if i.get("found"):
        return f"{i['seconds']:.0f} s, the best of {i['found']} found (time limit {lim:g} s){refused}"
    return f"{i.get('seconds', 0):.0f} s, {i.get('attempts', 1)} attempt{'s' if i.get('attempts', 1) != 1 else ''} (time limit {lim:g} s){refused}"


def chips(c):
    return ", ".join(x.get("name") or x.get("code") for x in c.get("contains") or []) or "singles only"


def section(name):
    d = load(name)
    if d is None:
        return []
    c = d["card"]
    body = {k: v for k, v in d["spec"].items() if k not in ("format", "format_version", "meta")}
    j = lambda v: json.dumps(v, ensure_ascii=False)
    spec_text = (
        "{"
        + ",\n ".join(  # one rule per line: the templates are the point of each request
            f'"{k}": [' + ",\n  ".join(j(r) for r in v) + "]" if k == "rules" else f'"{k}": {j(v)}'
            for k, v in body.items()
        )
        + "}"
    )
    shows = [f"Shows {d['shows']}.", ""] if d["shows"] else []
    if not d["shows"] and d["spec"].get("meta", {}).get("description"):
        shows = [d["spec"]["meta"]["description"], ""]
    minutes = f", about {c['time']} min" if c.get("time") is not None else ""  # the request's fields may leave it out
    i = d.get("info") or {}
    plural = lambda n, w: f"{n} {w}" + ("" if n == 1 else "es" if w.endswith("x") else "s")
    names = {"cage": "cage", "thermo": "thermo", "slow_thermo": "slow thermo", "whisper": "whisper", "renban": "renban",
             "between": "between line", "entropic": "entropic line", "modular": "modular line", "parity_line": "parity line",
             "arrow": "arrow", "kropki_white": "white dot", "kropki_black": "black dot", "x": "X", "v": "V",
             "odd": "odd cell", "even": "even cell"}  # fmt: skip
    made = [plural(n, names.get(k, k)) for k, n in sorted((i.get("elements") or {}).items(), key=lambda kv: -kv[1])]
    made = ", ".join(made + [plural(i["givens"], "given")]) + ". " if "givens" in i else ""
    return [f"### {d['title']}", "", *shows, "```json", spec_text, "```", "", f'<Swatch name="generated-{name}" />', "",
            f"{made}**{c['band']}**, difficulty {c['difficulty']}{minutes}. Contains: {chips(c)}. "
            f"Generated in {took(d)}.", ""]  # fmt: skip


def write_page():
    """the Generator examples page, from the kept results: request, drawn puzzle, card, time taken"""
    L = [HEAD]
    for name in CURIOSITIES:
        L += section(name)
    L.append(LARGER_HEAD)
    for name in [*MULTI, *LARGER]:
        L += section(name)
    L.append(LATER)
    PAGE.write_text("\n".join(L), encoding="utf-8")


def main(argv):
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 4
    if "--page" in argv:  # only rewrite the page from the kept results
        return write_page()
    names = [a for a in argv if a in EXAMPLES] or list(EXAMPLES)
    OUT.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(jobs) as ex:
        for name, result in ex.map(run, names):
            print(f"{name:24s} {result}", flush=True)
    write_page()


if __name__ == "__main__":
    main(sys.argv[1:])
