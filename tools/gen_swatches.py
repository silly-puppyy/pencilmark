"""Draw the docs' small pictures (light and dark): a 3x3 example of every rule kind, a 9x9 board of every placement
variant and of every puzzle in docs/examples (with tools/render_svg.py), and an outline of every named multi-grid
layout.

  python tools/gen_swatches.py [out_dir]      default: website/static/img/swatches

Each rule swatch is a 3x3 board holding one rule (and digits that satisfy it, where they show the meaning); every line
follows the same 7-cell path and edge clues are chained along the bottom row. <name>.json holds the rules drawn, for
the page's JSON panel. Layout outlines tint
each grid and let overlapping tints blend, so the shared boxes show. The docs build runs this script; the images are
not committed. swatches.json lists the names, so a page can check that a swatch exists.
"""

import functools
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_svg  # noqa: E402

RENDER = functools.partial(render_svg.render, background=False)  # transparent around the board: tables show through

from pencilmark import exchange, puzzle_json, variants  # noqa: E402

_ = 0
# every line runs along the same 7 cells, a U from the top-left corner, so the pictures read alike
PATH = ["r1c1", "r2c1", "r3c1", "r3c2", "r3c3", "r2c3", "r1c3"]
ROW3 = ["r3c1", "r3c2", "r3c3"]  # edge clues are chained along the bottom row


def along(cells, digits):
    """a 3x3 givens grid with digits on cells (None: left empty)"""
    g = [[0] * 3 for _row in range(3)]
    for c, d in zip(cells, digits):
        if d:
            g[int(c[1]) - 1][int(c[3]) - 1] = d
    return g


def line(kind, digits=None, **kw):
    """a line along PATH; with digits for every cell of the path, the two cells off it are filled too"""
    g = None
    if digits:
        g = along(PATH, digits)
        if None not in digits:
            free = [d for d in range(1, 10) if d not in digits]
            g[0][1], g[1][1] = free[0], free[1]
    return [dict({"type": "line", "kind": kind}, **kw, cells=PATH)], g


# swatches cut out of a larger board: no frame on these sides (the boxes go on beyond the picture)
OPEN_SIDES = {"line-region_sum": ("left", "right")}


def region_sum_swatch():
    """a box border between columns 2 and 3 (two `box` rules), so the line splits into two segments of equal sum"""
    rules, g = line("region_sum", [1, 2, 3, 6, 4, 5, 3])
    boxes = [{"type": "box", "cells": ["r1c1", "r1c2", "r2c1", "r2c2", "r3c1", "r3c2"]},
             {"type": "box", "cells": ["r1c3", "r2c3", "r3c3"]}]  # fmt: skip
    return boxes + rules, g


def chain(rule, digits=None):
    """an edge clue on each neighbouring pair of the bottom row"""
    return [dict(rule, cells=[a, b]) for a, b in zip(ROW3, ROW3[1:])], along(ROW3, digits) if digits else None


def nm(r, c):
    return f"r{r}c{c}"


def grid(*rows):
    """a 3x3 givens grid from three strings, '.' empty"""
    return [[0 if ch == "." else int(ch) for ch in row] for row in rows]


def fill(cells, digits):
    """digits along cells, then the other cells filled with the unused digits in reading order"""
    g = along(cells, digits)
    free = [d for d in range(1, 10) if d not in digits]
    for r in range(3):
        for c in range(3):
            if not g[r][c] and nm(r + 1, c + 1) not in cells[: len(digits)]:
                g[r][c] = free.pop(0)
    return g


def edges(g, kind, pairs, **params):
    """edge clues on the given cell pairs of grid g; params(fn(a, b)) give each clue's parameters"""
    out = []
    for (r1, c1), (r2, c2) in pairs:
        a, b = g[r1 - 1][c1 - 1], g[r2 - 1][c2 - 1]
        rule = {"type": "edge", "kind": kind, "cells": [nm(r1, c1), nm(r2, c2)]}
        for key, fn in params.items():
            rule[key] = fn(a, b)
        if kind == "greater" and a < b:
            rule["cells"].reverse()
        out.append(rule)
    return out


ALL_PAIRS = [((r, c), (r, c + 1)) for r in (1, 2, 3) for c in (1, 2)] + [
    ((r, c), (r + 1, c)) for r in (1, 2) for c in (1, 2, 3)
]


def true_pairs(g, ok):
    return [p for p in ALL_PAIRS if ok(g[p[0][0] - 1][p[0][1] - 1], g[p[1][0] - 1][p[1][1] - 1])]


def block(r, c):
    return [nm(r, c), nm(r, c + 1), nm(r + 1, c), nm(r + 1, c + 1)]


G_WHITE = grid("123", "654", "789")
G_BLACK = grid("124", "538", "769")
G_X = grid("195", "382", "467")
G_V = grid("146", "278", "395")
G_ARITH = grid("152", "837", "496")
G_RATIO = grid("248", "631", "597")
G_GREATER = grid("528", "194", "637")
G_MATH = grid("124", "365", "789")
G_VUD = grid("648", "195", "237")
G_CAGE = grid("159", "274", "386")
G_XSUM = grid("273", "159", "846")


def sky(vals):
    seen, top = 0, 0
    for v in vals:
        if v > top:
            seen, top = seen + 1, v
    return seen


def lines_of(g):
    """(side, cells, digits) of every row / column read from each side"""
    out = []
    for i in range(1, 4):
        row = [nm(i, c) for c in (1, 2, 3)]
        col = [nm(r, i) for r in (1, 2, 3)]
        out += [("left", row), ("right", row[::-1]), ("top", col), ("bottom", col[::-1])]
    return [(side, cells, [g[int(x[1]) - 1][int(x[3]) - 1] for x in cells]) for side, cells in out]


# name -> (rules, givens row by row), on a 3x3 board: most cells filled, several clues and values per picture
SWATCHES = {
    # 6.2 region
    "region-diagonal": ([{"type": "region", "kind": "diagonal", "cells": ["r1c1", "r2c2", "r3c3"]}], None),
    "region-extra": ([{"type": "region", "kind": "extra", "cells": ["r1c2", "r2c2", "r2c3"]}], None),
    # 6.3 cage: three cages, three sums
    "cage": (
        [
            {"type": "cage", "sum": 15, "cells": block(1, 1)},
            {"type": "cage", "sum": 10, "cells": ["r2c3", "r3c3"]},
            {"type": "cage", "sum": 11, "cells": ["r3c1", "r3c2"]},
        ],
        G_CAGE,
    ),
    # 6.4 line: the same path; digits that satisfy the rule, the two cells off the line filled too
    "line-thermo": line("thermo", [1, 2, 4, 5, 7, 8, 9]),
    "line-slow_thermo": line("slow_thermo", [1, 2, 2, 5, 7, 7, 9]),
    "line-whisper": line("whisper", [1, 7, 2, 8, 3, 9, 4]),
    "line-renban": line("renban", [4, 6, 5, 3, 7, 2, 8]),
    "line-region_sum": region_sum_swatch(),
    "line-palindrome": line("palindrome", [3, 5, 8, 1, 8, 5, 3]),
    "line-entropic": line("entropic", [1, 5, 9, 2, 4, 7, 3]),
    "line-modular": line("modular", [1, 2, 3, 4, 5, 6, 7]),
    "line-parity": line("parity", [2, 7, 4, 1, 6, 3, 8]),
    "line-zipper": line("zipper", [1, 2, 3, 9, 6, 7, 8]),
    "line-between": line("between", [1, 3, 5, 4, 6, 7, 9]),
    "line-lockout": line("lockout", [2, None, None, 9, None, None, 7]),
    "line-double_arrow": line("double_arrow", [8, 1, 2, 3, 4, 7, 9]),
    # 6.5 arrow
    "arrow": (
        [{"type": "arrow", "bulb": ["r1c1"], "lines": [["r2c1", "r3c1", "r3c2"]]}],
        fill(["r1c1", "r2c1", "r3c1", "r3c2"], [9, 2, 3, 4]),
    ),
    # 6.6 edge: every pair that holds the relation, or several values on chosen pairs
    "edge-kropki-white": (
        edges(G_WHITE, "kropki", true_pairs(G_WHITE, lambda a, b: abs(a - b) == 1), color=lambda a, b: "white"),
        G_WHITE,
    ),
    "edge-kropki-black": (
        edges(
            G_BLACK, "kropki", true_pairs(G_BLACK, lambda a, b: a == 2 * b or b == 2 * a), color=lambda a, b: "black"
        ),
        G_BLACK,
    ),
    "edge-xv-x": (edges(G_X, "xv", true_pairs(G_X, lambda a, b: a + b == 10), letter=lambda a, b: "X"), G_X),
    "edge-xv-v": (edges(G_V, "xv", true_pairs(G_V, lambda a, b: a + b == 5), letter=lambda a, b: "V"), G_V),
    "edge-difference": (
        edges(
            G_ARITH,
            "difference",
            [((1, 1), (1, 2)), ((2, 2), (2, 3)), ((1, 1), (2, 1)), ((2, 3), (3, 3)), ((3, 1), (3, 2))],
            value=lambda a, b: abs(a - b),
        ),
        G_ARITH,
    ),
    "edge-sum": (
        edges(
            G_ARITH,
            "sum",
            [((1, 2), (1, 3)), ((1, 2), (2, 2)), ((2, 1), (2, 2)), ((1, 3), (2, 3)), ((3, 2), (3, 3))],
            sum=lambda a, b: a + b,
        ),
        G_ARITH,
    ),
    "edge-product": (
        edges(
            G_ARITH,
            "product",
            [((1, 1), (1, 2)), ((2, 2), (2, 3)), ((2, 1), (3, 1)), ((3, 2), (3, 3)), ((2, 2), (3, 2))],
            value=lambda a, b: a * b,
        ),
        G_ARITH,
    ),
    "edge-ratio": (
        edges(
            G_RATIO,
            "ratio",
            [
                ((1, 1), (1, 2)),
                ((2, 1), (2, 2)),
                ((2, 2), (2, 3)),
                ((1, 1), (2, 1)),
                ((2, 2), (3, 2)),
                ((1, 3), (2, 3)),
            ],
            value=lambda a, b: max(a, b) // min(a, b),
        ),
        G_RATIO,
    ),
    "edge-greater": (edges(G_GREATER, "greater", ALL_PAIRS), G_GREATER),
    # 6.7 corner: two clues per picture where two fit
    "corner-battenburg": (
        [
            {"type": "corner", "kind": "battenburg", "cells": block(1, 1)},
            {"type": "corner", "kind": "battenburg", "cells": block(2, 2)},
        ],
        grid("123", "456", "789"),
    ),
    "corner-exclude": (
        [
            {"type": "corner", "kind": "exclude", "value": 5, "cells": block(1, 1)},
            {"type": "corner", "kind": "exclude", "value": 3, "cells": block(2, 2)},
        ],
        grid("123", "467", "895"),
    ),
    "corner-mathrax": (
        [
            {"type": "corner", "kind": "mathrax", "op": "x", "value": 6, "cells": block(1, 1)},
            {"type": "corner", "kind": "mathrax", "op": "-", "value": 3, "cells": block(2, 2)},
        ],
        G_MATH,
    ),
    "contains-quadruple": (
        [
            {"type": "contains", "digits": [1, 2, 5], "cells": block(1, 1)},
            {"type": "contains", "digits": [4, 9], "cells": block(2, 2)},
        ],
        grid("136", "524", "798"),
    ),
    "vudoku": (
        [{"type": "vudoku", "cells": ["r2c2", "r1c2", "r2c3"]}, {"type": "vudoku", "cells": ["r3c1", "r2c1", "r3c2"]}],
        G_VUD,
    ),
    # 6.9 outside clues: several sides, the box filled
    "sandwich": (
        [{"type": "sandwich", "side": "left", "sum": 5, "cells": ["r1c1", "r1c2", "r1c3"]}],
        grid("159", "274", "386"),
    ),
    "xsum": (
        [
            {"type": "xsum", "side": side, "sum": sum(v[: v[0]]), "cells": cells}
            for side, cells, v in lines_of(G_XSUM)
            if v[0] <= 3
        ],
        G_XSUM,
    ),
    "skyscraper": (
        [
            {"type": "skyscraper", "side": side, "value": sky(v), "cells": cells}
            for side, cells, v in lines_of(G_XSUM)[::3]
        ],
        G_XSUM,
    ),
    # 6.12 cell clues
    "cell-odd": ([{"type": "cell", "kind": "odd", "cells": ["r1c1", "r2c3", "r3c2"]}], grid("1.4", "263", "897")),
    "cell-even": ([{"type": "cell", "kind": "even", "cells": ["r1c1", "r2c3", "r3c2"]}], grid("215", "934", "786")),
}


BOXES = {"type": "box_grid", "box": [3, 3], "count": [3, 3]}
PLACEMENT = ("X", "Windoku", "Argyle", "Asterisk", "Centre-dot", "Girandola", "Disjoint Groups")

# grid tints for layout outlines, per theme; overlapping grids never share a tint, so a shared box shows a blend
TINTS = {
    False: ("#3b82c4", "#d9822b", "#3a9e6a", "#a35bc0", "#c8463f"),
    True: ("#5aa2e0", "#e89a4a", "#55b884", "#b97ad6", "#e0625a"),
}


def layout_svg(origins, dark=False, cell=7, n=9):
    """outline of a multi-grid layout: one tinted 9x9 square per grid (box lines on top); overlaps blend"""
    theme = render_svg.THEMES[bool(dark)]
    ink, board = theme["ink"], theme["board"]
    tint = {}
    for i, (r, c) in enumerate(origins):  # greedy colouring of the overlap graph
        near = {tint[j] for j, (r2, c2) in enumerate(origins[:i]) if abs(r - r2) < n and abs(c - c2) < n}
        tint[i] = next(k for k in range(len(TINTS[dark])) if k not in near)
    h = (max(r for r, _ in origins) + n) * cell
    w = (max(c for _, c in origins) + n) * cell
    pad = 2
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {w + 2 * pad} {h + 2 * pad}" '
        f'width="{w + 2 * pad}" height="{h + 2 * pad}">'
    ]
    for r, c in origins:
        out.append(f'<rect x="{c * cell}" y="{r * cell}" width="{n * cell}" height="{n * cell}" fill="{board}"/>')
    for i, (r, c) in enumerate(origins):
        colour = TINTS[dark][tint[i]]
        out.append(
            f'<rect x="{c * cell}" y="{r * cell}" width="{n * cell}" height="{n * cell}" fill="{colour}" '
            f'fill-opacity="{0.5 if dark else 0.32}"/>'
        )
    for r, c in origins:
        x, y, s = c * cell, r * cell, n * cell
        for k in (3, 6):
            out.append(
                f'<line x1="{x + k * cell}" y1="{y}" x2="{x + k * cell}" y2="{y + s}" stroke="{ink}" '
                f'stroke-width="0.5" stroke-opacity="0.45"/>'
            )
            out.append(
                f'<line x1="{x}" y1="{y + k * cell}" x2="{x + s}" y2="{y + k * cell}" stroke="{ink}" '
                f'stroke-width="0.5" stroke-opacity="0.45"/>'
            )
        out.append(f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="none" stroke="{ink}" stroke-width="1.2"/>')
    out.append("</svg>")
    return "".join(out)


EXAMPLES = sorted((Path(__file__).resolve().parents[1] / "docs" / "examples").glob("*.json"))


def drawings():
    """name -> fn(dark) -> svg text, for every picture this script makes"""
    out = {}
    for name, (rules, givens) in SWATCHES.items():
        out[name] = lambda dark, name=name, rules=rules, givens=givens: RENDER(
            doc_for(name, rules, givens), dark=dark, cell=40, open_sides=OPEN_SIDES.get(name, ())
        )
    for v in PLACEMENT:
        doc = dict(
            doc_for("", [], None),
            board={"rows": 9, "cols": 9},
            givens=[0] * 81,
            rules=[BOXES] + variants.preset_rules(v),
        )
        out["variant-" + v.lower().replace(" ", "-")] = lambda dark, doc=doc: RENDER(doc, dark=dark, cell=24)
    for kind in (
        "generated",
        "learning",
    ):  # the generator examples and the learning guide's puzzles (gen_*_examples.py)
        for f in sorted((Path(__file__).resolve().parents[1] / "docs" / "examples" / kind).glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))["puzzle"]
            cell = min(40, 720 // doc["board"]["cols"])  # a multi-grid layout fits the page width
            out[f"{kind}-{f.stem}"] = lambda dark, doc=doc, cell=cell: RENDER(doc, dark=dark, cell=cell)
    for f in EXAMPLES:  # example puzzles: plain, and annotated with row / column numbers for the board + JSON view
        doc = json.loads(f.read_text(encoding="utf-8"))
        out["example-" + f.stem] = lambda dark, doc=doc: RENDER(doc, dark=dark, cell=40)
        out["example-" + f.stem + "-board"] = lambda dark, doc=doc: RENDER(
            doc, dark=dark, cell=44, annotate=True, labels=True
        )
    for key in variants.LAYOUT_NAMES:
        origins = [tuple(o) for o in puzzle_json._layouts()[key]]
        out["layout-" + key] = lambda dark, origins=origins: layout_svg(origins, dark)
    return out


def doc_for(name, rules, givens):
    flat = [v for row in (givens or [[0] * 3] * 3) for v in row]
    return {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": 3, "cols": 3},
        "digits": 9,
        "givens": flat,
        "rules": rules,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else Path(__file__).resolve().parents[1] / "website/static/img/swatches"
    out.mkdir(parents=True, exist_ok=True)
    done, failed = [], {}
    for name, draw in drawings().items():
        try:
            for dark, suffix in ((False, ""), (True, "-dark")):
                (out / f"{name}{suffix}.svg").write_text(draw(dark), encoding="utf-8")
            done.append(name)
        except Exception as e:  # a swatch the renderer cannot draw is reported, not fatal
            failed[name] = f"{type(e).__name__}: {e}"
    for f in EXAMPLES:  # the canonical text next to the board (PuzzleJson.js): its rules line up with data-rule
        (out / f"example-{f.stem}.json").write_text(
            exchange.dumps(json.loads(f.read_text(encoding="utf-8"))), encoding="utf-8"
        )
    for name, (rules, _givens) in SWATCHES.items():  # the rules each picture draws, shown on click (Swatch.js)
        (out / f"{name}.json").write_text("\n".join(json.dumps(r) for r in rules), encoding="utf-8")
    widths = {
        n: float(re.search(r'width="([\d.]+)"', (out / f"{n}.svg").read_text(encoding="utf-8")).group(1)) for n in done
    }
    (out / "swatches.json").write_text(
        json.dumps({"swatches": done, "widths": widths, "failed": failed}, indent=1), encoding="utf-8"
    )  # widths: Swatch.js shows every picture at one scale, so a cell is the same size in all of them
    print(f"{len(done)} swatches in {out}" + (f"; failed: {failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
