"""Run the generator examples (one seeded request per feature of docs/formats/generator-spec.md) and keep what they
produce in docs/examples/generated/<name>.json ({"title", "shows", "spec", "puzzle", "card"}); the Generator
examples page shows each request, the drawn puzzle (tools/gen_swatches.py) and its card. Generation takes minutes and
the same seed gives the same puzzle, so the results are committed; run this again when the generator changes.
  python tools/gen_generator_examples.py [name ...] [--jobs N]     (--page: only rewrite the page)"""

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "examples" / "generated"
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


# name -> (title, what it shows, spec)
EXAMPLES = {
    "classic-hard-xwing": (
        "A Hard classic with an X-Wing",
        "a band target, a required technique (strict), 180° symmetry",
        spec(where={"band": "Hard", "contains": {"codes": ["XWG"], "strict": True}}, symmetry={"kind": "rot180"}),
    ),
    "classic-easy-30": (
        "An Easy classic with 30 givens",
        "an exact given count, mirror symmetry",
        spec(where={"band": "Easy"}, givens={"count": 30}, symmetry={"kind": "mirror", "axis": "vertical"}),
    ),
    "classic-difficulty": (
        "A classic of difficulty 3 to 4",
        "a difficulty range instead of a band",
        spec(where={"difficulty": [3, 4]}),
    ),
    "mini-6x6": (
        "A 6×6 with 10 to 16 givens",
        "another board size, a given range, 180° symmetry",
        spec(6, givens={"count": [10, 16]}, symmetry={"kind": "rot180"}),
    ),
    "tiny-4x4-rot90": (
        "A 4×4 with quarter-turn symmetry",
        "the smallest board; 90° symmetry (it needs square boxes)",
        spec(4, symmetry={"kind": "rot90"}),
    ),
    "killer-6x6-tiled": (
        "A 6×6 killer tiled by cages",
        'the cage template with count "tile"',
        spec(6, [{"type": "cage", "count": "tile"}]),
    ),
    "killer-medium": (
        "A Medium killer",
        "the cage template with a minimum count and a band target",
        spec(rules=[{"type": "cage", "count": [4, None]}], where={"band": "Medium"}),
    ),
    "thermo-3": (
        "Exactly three thermometers",
        "an exact count of a line template",
        spec(rules=[{"type": "line", "kind": "thermo", "count": 3}]),
    ),
    "whisper-renban": (
        "Whispers and renbans together",
        'two templates, a count range and "auto"',
        spec(
            rules=[
                {"type": "line", "kind": "whisper", "count": [2, 4]},
                {"type": "line", "kind": "renban", "count": "auto"},
            ]
        ),
    ),
    "arrow-between": (
        "Arrows and between lines",
        "the arrow template and a second line kind",
        spec(rules=[{"type": "arrow", "count": 2}, {"type": "line", "kind": "between", "count": "auto"}]),
    ),
    "kropki-colours": (
        "White and black dots",
        'kropki by colour: an exact count of one, "auto" for the other',
        spec(
            rules=[
                {"type": "edge", "kind": "kropki", "color": "white", "count": 4},
                {"type": "edge", "kind": "kropki", "color": "black", "count": "auto"},
            ]
        ),
    ),
    "xv-letters": (
        "X and V",
        "XV by letter",
        spec(
            rules=[
                {"type": "edge", "kind": "xv", "letter": "X", "count": 3},
                {"type": "edge", "kind": "xv", "letter": "V", "count": "auto"},
            ]
        ),
    ),
    "parity-cells": (
        "Odd and even cells",
        "the parity template (odd or even cells, either kind)",
        spec(rules=[{"type": "cell", "kind": "parity", "count": 4}]),
    ),
    "kropki-8x8-capped": (
        "An 8×8 with at most six dots",
        "an 8×8 board and the element cap (where.elements)",
        spec(8, [{"type": "edge", "kind": "kropki", "count": "auto"}], where={"elements": {"max": 6}}),
    ),
}


def run(name):
    import pencilmark

    title, shows, s = EXAMPLES[name]
    try:
        r = pencilmark.generate(s)
    except pencilmark.GenerationFailed as e:
        return name, f"failed: {e}"
    card = {k: r["card"].get(k) for k in ("band", "difficulty", "time", "contains")}
    (OUT / f"{name}.json").write_text(
        json.dumps({"title": title, "shows": shows, "spec": s, "puzzle": r["puzzle"], "card": card}, ensure_ascii=False,
                   indent=1) + "\n", encoding="utf-8")  # fmt: skip
    return name, f"{card['band']} {card['difficulty']}"


PAGE = ROOT / "docs" / "guides" / "generator-examples.mdx"


def write_page():
    """the Generator examples page, from the kept results: request, drawn puzzle, card"""
    L = ["---", "title: Generator examples",
         'description: "One generator request per feature (templates, counts, targets, symmetry, board sizes), each with '
         'the puzzle it produced and its card."', "---", "", "import Swatch from '@site/src/components/Swatch';", "",
         "# Generator examples", "",
         "One request per feature of the [generator spec](../formats/generator-spec.md), each with the puzzle it produced "
         "and its card. The seed fixes the result: the same request on the same version gives the same puzzle. Written by "
         "`tools/gen_generator_examples.py`.", ""]  # fmt: skip
    for name in EXAMPLES:
        f = OUT / f"{name}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        c = d["card"]
        chips = ", ".join(x.get("name") or x.get("code") for x in c.get("contains") or []) or "singles only"
        spec_text = "{" + ",\n ".join(f'"{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in d["spec"].items()) + "}"
        L += [f"## {d['title']}", "", f"Shows {d['shows']}.", "", "```json", spec_text, "```", "", f'<Swatch name="generated-{name}" />', "",
              f"**{c['band']}**, difficulty {c['difficulty']}, about {c['time']} min. Contains: {chips}.", ""]  # fmt: skip
    PAGE.write_text("\n".join(L), encoding="utf-8")


def main(argv):
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 4
    if "--page" in argv:  # only rewrite the page from the kept results
        return write_page()
    names = [a for a in argv if a in EXAMPLES] or list(EXAMPLES)
    OUT.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(jobs) as ex:
        for name, result in ex.map(run, names):
            print(f"{name:20s} {result}", flush=True)
    write_page()


if __name__ == "__main__":
    main(sys.argv[1:])
