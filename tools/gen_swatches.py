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

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_svg  # noqa: E402

from pencilmark import puzzle_json, variants  # noqa: E402

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
    return [dict({"type": "line", "kind": kind}, **kw, cells=PATH)], along(PATH, digits) if digits else None


def chain(rule, digits=None):
    """an edge clue on each neighbouring pair of the bottom row"""
    return [dict(rule, cells=[a, b]) for a, b in zip(ROW3, ROW3[1:])], along(ROW3, digits) if digits else None


# name -> (rules, givens row by row), on a 3x3 board; digits are shown where they make the meaning clear
SWATCHES = {
    # 6.2 region
    "region-diagonal": ([{"type": "region", "kind": "diagonal", "cells": ["r1c1", "r2c2", "r3c3"]}], None),
    "region-extra": ([{"type": "region", "kind": "extra", "cells": ["r1c2", "r2c2", "r2c3"]}], None),
    # 6.3 cage
    "cage": ([{"type": "cage", "sum": 15, "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}], None),
    # 6.4 line: the same path; digits that satisfy the rule
    "line-thermo": line("thermo", [1, 2, 4, 5, 7, 8, 9]),
    "line-slow_thermo": line("slow_thermo", [1, 2, 2, 5, 7, 7, 9]),
    "line-whisper": line("whisper", [1, 7, 2, 8, 3, 9, 4]),
    "line-renban": line("renban", [4, 6, 5, 3, 7, 2, 8]),
    "line-region_sum": line("region_sum"),
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
        along(["r1c1", "r2c1", "r3c1", "r3c2"], [9, 2, 3, 4]),
    ),
    # 6.6 edge: chains along the bottom row
    "edge-kropki-white": chain({"type": "edge", "kind": "kropki", "color": "white"}, [4, 5, 6]),
    "edge-kropki-black": chain({"type": "edge", "kind": "kropki", "color": "black"}, [2, 4, 8]),
    "edge-xv-x": chain({"type": "edge", "kind": "xv", "letter": "X"}, [3, 7, 3]),
    "edge-xv-v": chain({"type": "edge", "kind": "xv", "letter": "V"}, [2, 3, 2]),
    "edge-difference": chain({"type": "edge", "kind": "difference", "value": 3}, [1, 4, 7]),
    "edge-sum": chain({"type": "edge", "kind": "sum", "sum": 12}, [5, 7, 5]),
    "edge-less": chain({"type": "edge", "kind": "less"}, [1, 2, 3]),
    # 6.7 corner
    "corner-battenburg": (
        [{"type": "corner", "kind": "battenburg", "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}],
        [[1, 2, _], [4, 3, _], [_, _, _]],
    ),
    "corner-exclude": (
        [{"type": "corner", "kind": "exclude", "value": 5, "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}],
        None,
    ),
    "contains-quadruple": (
        [{"type": "contains", "digits": [1, 2, 5], "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}],
        [[1, _, _], [5, 2, _], [_, _, _]],
    ),
    # 6.9 outside clues
    "sandwich": ([{"type": "sandwich", "side": "left", "sum": 7, "cells": ["r2c1", "r2c2", "r2c3"]}], None),
    "xsum": ([{"type": "xsum", "side": "top", "sum": 9, "cells": ["r1c2", "r2c2", "r3c2"]}], None),
    "skyscraper": ([{"type": "skyscraper", "side": "top", "value": 2, "cells": ["r1c2", "r2c2", "r3c2"]}], None),
    # 6.12 cell clues
    "cell-odd": ([{"type": "cell", "kind": "odd", "cells": ["r1c1", "r2c3", "r3c2"]}], None),
    "cell-even": ([{"type": "cell", "kind": "even", "cells": ["r1c1", "r2c3", "r3c2"]}], None),
}


BOXES = {"type": "box_grid", "origin": "r1c1", "box": [3, 3]}
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


def drawings():
    """name -> fn(dark) -> svg text, for every picture this script makes"""
    out = {}
    for name, (rules, givens) in SWATCHES.items():
        out[name] = lambda dark, name=name, rules=rules, givens=givens: render_svg.render(
            doc_for(name, rules, givens), dark=dark, cell=40
        )
    for v in PLACEMENT:
        doc = dict(
            doc_for("", [], None),
            board={"rows": 9, "cols": 9},
            givens=[0] * 81,
            rules=[BOXES] + variants.preset_rules(v),
        )
        out["variant-" + v.lower().replace(" ", "-")] = lambda dark, doc=doc: render_svg.render(doc, dark=dark, cell=24)
    for f in sorted((Path(__file__).resolve().parents[1] / "docs" / "examples").glob("*.json")):  # example puzzles
        doc = json.loads(f.read_text(encoding="utf-8"))
        out["example-" + f.stem] = lambda dark, doc=doc: render_svg.render(doc, dark=dark, cell=40)
    for key in variants.LAYOUT_NAMES:
        origins = [tuple(o) for o in puzzle_json._layouts()[key]]
        out["layout-" + key] = lambda dark, origins=origins: layout_svg(origins, dark)
    return out


def doc_for(name, rules, givens):
    flat = [v for row in (givens or [[0] * 3] * 3) for v in row]
    return {
        "format": "sudoku-puzzle",
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
    for name, (rules, _givens) in SWATCHES.items():  # the rules each picture draws, shown on click (Swatch.js)
        (out / f"{name}.json").write_text("\n".join(json.dumps(r) for r in rules), encoding="utf-8")
    (out / "swatches.json").write_text(json.dumps({"swatches": done, "failed": failed}, indent=1), encoding="utf-8")
    print(f"{len(done)} swatches in {out}" + (f"; failed: {failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
