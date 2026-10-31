"""Draw the docs' small pictures (light and dark): a 3x3 example of every rule kind, a 9x9 board of every placement
variant and of every puzzle in docs/examples (with tools/render_svg.py), and an outline of every named multi-grid
layout.

  python tools/gen_swatches.py [out_dir]      default: website/static/img/swatches

Each rule swatch is a 3x3 board holding one rule (and a few digits where they show the meaning). Layout outlines tint
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
# name -> (rules, givens row by row). Cells r1c1..r3c3; outside clues use a side.
SWATCHES = {
    # 6.2 region
    "region-diagonal": ([{"type": "region", "kind": "diagonal", "cells": ["r1c1", "r2c2", "r3c3"]}], None),
    "region-extra": ([{"type": "region", "kind": "extra", "cells": ["r1c2", "r2c2", "r2c3"]}], None),
    # 6.3 cage
    "cage": ([{"type": "cage", "sum": 15, "cells": ["r1c1", "r1c2", "r2c1"]}], None),
    # 6.4 line
    "line-thermo": ([{"type": "line", "kind": "thermo", "cells": ["r3c1", "r2c2", "r1c3"]}], None),
    "line-slow_thermo": ([{"type": "line", "kind": "slow_thermo", "cells": ["r3c1", "r2c2", "r1c3"]}], None),
    "line-whisper": (
        [{"type": "line", "kind": "whisper", "cells": ["r1c1", "r2c2", "r3c3"]}],
        [[1, _, _], [_, 7, _], [_, _, 2]],
    ),
    "line-renban": (
        [{"type": "line", "kind": "renban", "cells": ["r1c1", "r1c2", "r1c3"]}],
        [[4, 6, 5], [_, _, _], [_, _, _]],
    ),
    "line-region_sum": ([{"type": "line", "kind": "region_sum", "cells": ["r1c1", "r2c1", "r2c2", "r2c3"]}], None),
    "line-palindrome": (
        [{"type": "line", "kind": "palindrome", "cells": ["r1c1", "r2c2", "r3c3"]}],
        [[3, _, _], [_, _, _], [_, _, 3]],
    ),
    "line-entropic": ([{"type": "line", "kind": "entropic", "cells": ["r1c1", "r1c2", "r1c3", "r2c3"]}], None),
    "line-modular": ([{"type": "line", "kind": "modular", "cells": ["r1c1", "r1c2", "r1c3", "r2c3"]}], None),
    "line-parity": (
        [{"type": "line", "kind": "parity", "cells": ["r1c1", "r1c2", "r1c3"]}],
        [[2, 7, 4], [_, _, _], [_, _, _]],
    ),
    "line-zipper": (
        [{"type": "line", "kind": "zipper", "cells": ["r1c1", "r1c2", "r1c3"]}],
        [[3, 8, 5], [_, _, _], [_, _, _]],
    ),
    "line-between": (
        [{"type": "line", "kind": "between", "cells": ["r1c1", "r2c2", "r3c3"]}],
        [[2, 5, _], [_, _, _], [_, _, 8]],
    ),
    "line-lockout": (
        [{"type": "line", "kind": "lockout", "cells": ["r1c1", "r2c2", "r3c3"]}],
        [[2, _, _], [_, 9, _], [_, _, 7]],
    ),
    "line-double_arrow": ([{"type": "line", "kind": "double_arrow", "cells": ["r1c1", "r2c2", "r3c3"]}], None),
    # 6.5 arrow
    "arrow": ([{"type": "arrow", "bulb": ["r1c1"], "lines": [["r2c2", "r3c3"]]}], [[9, _, _], [_, 4, _], [_, _, 5]]),
    # 6.6 edge
    "edge-kropki-white": (
        [{"type": "edge", "kind": "kropki", "color": "white", "cells": ["r2c1", "r2c2"]}],
        [[_, _, _], [4, 5, _], [_, _, _]],
    ),
    "edge-kropki-black": (
        [{"type": "edge", "kind": "kropki", "color": "black", "cells": ["r2c1", "r2c2"]}],
        [[_, _, _], [3, 6, _], [_, _, _]],
    ),
    "edge-xv-x": (
        [{"type": "edge", "kind": "xv", "letter": "X", "cells": ["r2c1", "r2c2"]}],
        [[_, _, _], [3, 7, _], [_, _, _]],
    ),
    "edge-xv-v": (
        [{"type": "edge", "kind": "xv", "letter": "V", "cells": ["r2c1", "r2c2"]}],
        [[_, _, _], [1, 4, _], [_, _, _]],
    ),
    "edge-difference": ([{"type": "edge", "kind": "difference", "value": 3, "cells": ["r2c1", "r2c2"]}], None),
    "edge-sum": ([{"type": "edge", "kind": "sum", "sum": 12, "cells": ["r2c1", "r2c2"]}], None),
    "edge-less": ([{"type": "edge", "kind": "less", "cells": ["r2c1", "r2c2"]}], None),
    # 6.7 corner
    "corner-battenburg": ([{"type": "corner", "kind": "battenburg", "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}], None),
    "corner-exclude": (
        [{"type": "corner", "kind": "exclude", "value": 5, "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}],
        None,
    ),
    "contains-quadruple": (
        [{"type": "contains", "digits": [1, 2, 5], "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}],
        None,
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


SMALL = ("edge-", "corner-", "contains-")  # two-cell and corner clues read better on a 2x2 board (markers 1.5x larger)


def doc_for(name, rules, givens):
    n = 3
    if name.startswith(SMALL):  # move a clue drawn on row 2 up to row 1, keep the first two rows and columns
        rows = [r[:2] for r in (givens or [[0] * 3] * 3)]
        if all(c.startswith("r2") for rule in rules for c in rule["cells"]):
            rules = [dict(rule, cells=[c.replace("r2", "r1", 1) for c in rule["cells"]]) for rule in rules]
            rows = rows[1:]
        n, givens = 2, rows[:2]
    flat = [v for row in (givens or [[0] * n] * n) for v in row]
    return {
        "format": "sudoku-puzzle",
        "format_version": 1,
        "board": {"rows": n, "cols": n},
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
    (out / "swatches.json").write_text(json.dumps({"swatches": done, "failed": failed}, indent=1), encoding="utf-8")
    print(f"{len(done)} swatches in {out}" + (f"; failed: {failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
