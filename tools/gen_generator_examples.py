"""Run the generator examples and keep what they produce in docs/examples/generated/<name>.json ({"title", "shows",
"spec", "puzzle", "card", "info"}); the Generator examples page shows each request, the drawn puzzle
(tools/gen_swatches.py), its card and how long the run took. Three groups: curiosities (each shows another side of the
generator spec), the larger requests kept in docs/examples/specs/, and a sampler (a variant per row, harder to the
right). Generation takes up to an hour in all and the same seed gives the same puzzle, so the results are committed;
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


def spec(size=9, rules=(), where=None, givens=None, symmetry=None, seed=1, time=180):
    s = {"format": "sudoku-spec", "format_version": 1, "board": {"rows": size, "cols": size}, "digits": size,
         "rules": [{"type": "box_grid", "origin": "r1c1", "box": BOX[size]}, *rules]}  # fmt: skip
    if givens:
        s["givens"] = givens
    if symmetry:
        s["symmetry"] = [dict(symmetry, of="givens")]
    if where:
        s["where"] = where
    s["limits"] = {"time": time, "seed": seed}
    return s


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
        "One whisper, eighteen cells or more",
        "a line `length` with no upper bound, and 180° symmetry of the givens",
        spec(
            rules=[{"type": "line", "kind": "whisper", "length": [18, None], "count": 1}], symmetry={"kind": "rot180"}
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
    "dominoes": (
        "A killer of dominoes, no givens",
        "a cage `size`: every cage two cells, at least twelve of them",
        spec(rules=[{"type": "cage", "size": 2, "count": [12, None]}], time=300),
    ),
    "long-arrows": (
        "Arrows with long shafts",
        "an arrow `length` (the shaft): three arrows of three cells or more, whose shafts must hold small digits",
        spec(rules=[{"type": "arrow", "length": [3, None], "count": 3}]),
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
LARGER = {
    "killer-whispers": ("Killer with German whispers and two givens", "", from_file("killer_whispers_2givens.json")),
    "zero-clue-kropki": ("A 0-clue 6×6 kropki", "", from_file("zero_clue_6x6_kropki.json")),
    "nine-variants": ("Nine variants on one 9×9", "", from_file("nine_variants_9x9.json")),
}
# the sampler: a variant per row, difficulty rising from left to right (the super samurai of reserved/, as separate
# grids). Columns are difficulty ranges, not bands: a band says what you need to know, so a Hard puzzle can score lower
# than a Medium one
ROWS = {
    "killer": ("Killer", [{"type": "cage", "count": [4, None]}]),
    "thermo": ("Thermo", [{"type": "line", "kind": "thermo", "count": [3, None]}]),
    "kropki": ("Kropki", [{"type": "edge", "kind": "kropki", "count": [4, None]}]),
}
COLS = {"gentle": [5, 7.5], "steady": [8, 10], "tough": [10.5, 13]}
SAMPLER_TIME = {"killer-steady": 900, "killer-tough": 900}  # 300 s found only killers too hard for their range
SAMPLER_SEED = {"killer-tough": 4}  # seed 3 found none in 300 s
SAMPLER = {
    f"sampler-{r}-{c}": (
        f"{label}, difficulty {lo:g} to {hi:g}",
        "",
        spec(
            rules=rules,
            where={"difficulty": [lo, hi]},
            seed=SAMPLER_SEED.get(f"{r}-{c}", k + 1),
            time=SAMPLER_TIME.get(f"{r}-{c}", 300),
        ),
    )  # a seed per column: one seed would give a row the same grid and rules three times
    for r, (label, rules) in ROWS.items()
    for k, (c, (lo, hi)) in enumerate(COLS.items())
}
EXAMPLES = {**CURIOSITIES, **LARGER, **SAMPLER}


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
    info = {k: r["info"].get(k) for k in ("seconds", "attempts", "found", "givens", "elements")}
    info["seconds"] = round(time.time() - t, 1)  # the whole call, the final grading included
    d = {"title": title, "shows": shows, "spec": s, "puzzle": r["puzzle"], "card": card, "info": info}
    (OUT / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return name, f"{card['band']} {card['difficulty']} in {info['seconds']} s"


PAGE = ROOT / "docs" / "guides" / "generator" / "generator-examples.mdx"
HEAD = """---
title: Generator examples
description: "Generator requests and what they produced: curiosities, larger requests and a sampler, each with its card and how long the run took."
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

Requests kept as files in `docs/examples/specs/`; run one with `pencilmark generate FILE`.
"""
SAMPLER_HEAD = """
## A sampler

A variant per row, difficulty rising to the right: nine requests that differ only in the template and
`where.difficulty` (5 to 7.5, 8 to 10, 10.5 to 13). Under each board: its band, difficulty and how long the run took.

```json
{"rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "cage", "count": [4, null]}],
 "where": {"difficulty": [8, 10]},
 "limits": {"time": 300, "seed": 2}}
```
"""
LATER = """
## Not possible yet

`docs/examples/specs/reserved/` holds requests that use parts reserved for later versions of the spec
([Generator spec](../../formats/generator-spec.md), section 7); the generator refuses them today. Among them, a super
samurai with a variant per row of grids that get harder from left to right (the sampler above is the same idea on
separate grids), a classic with exactly one X-Wing, givens in the shape of a heart and a displaced jigsaw. A 16×16
killer with exactly 32 cages and no givens is also out of reach: the uniqueness search does not finish.
"""


def load(name):
    f = OUT / f"{name}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def took(d):
    """how the run went, in words"""
    i, lim = d.get("info") or {}, d["spec"].get("limits", {}).get("time", 120)
    if i.get("found"):
        return f"{i['seconds']:.0f} s, the best of {i['found']} found (time limit {lim:g} s)"
    return f"{i.get('seconds', 0):.0f} s, {i.get('attempts', 1)} attempt{'s' if i.get('attempts', 1) != 1 else ''} (time limit {lim:g} s)"


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
    names = {"cage": "cage", "thermo": "thermo", "whisper": "whisper", "renban": "renban", "between": "between line",
             "arrow": "arrow", "kropki_white": "white dot", "kropki_black": "black dot", "x": "X", "v": "V",
             "odd": "odd cell", "even": "even cell"}  # fmt: skip
    made = [plural(n, names.get(k, k)) for k, n in sorted((i.get("elements") or {}).items(), key=lambda kv: -kv[1])]
    made = ", ".join(made + [plural(i["givens"], "given")]) + ". " if "givens" in i else ""
    return [f"### {d['title']}", "", *shows, "```json", spec_text, "```", "", f'<Swatch name="generated-{name}" />', "",
            f"{made}**{c['band']}**, difficulty {c['difficulty']}{minutes}. Contains: {chips(c)}. "
            f"Generated in {took(d)}.", ""]  # fmt: skip


def sampler_table():
    L = ["| | " + " | ".join(f"{lo:g} to {hi:g}" for lo, hi in COLS.values()) + " |", "|---|" + "---|" * len(COLS)]
    for r, (label, _rules) in ROWS.items():
        cells = []
        for b in COLS:
            d = load(f"sampler-{r}-{b}")
            if d is None:
                cells.append("–")
                continue
            c = d["card"]
            cells.append(f'<Swatch name="generated-sampler-{r}-{b}" /><br/>{c["band"]}, {c["difficulty"]}, '
                         f'{d["info"]["seconds"]:.0f} s')  # fmt: skip
        L.append(f"| **{label}** | " + " | ".join(cells) + " |")
    return L + [""]


def write_page():
    """the Generator examples page, from the kept results: request, drawn puzzle, card, time taken"""
    L = [HEAD]
    for name in CURIOSITIES:
        L += section(name)
    L.append(LARGER_HEAD)
    for name in LARGER:
        L += section(name)
    L.append(SAMPLER_HEAD)
    L += sampler_table()
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
