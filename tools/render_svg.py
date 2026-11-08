"""Draw a puzzle file as SVG with pencilmark.render (the docs build's pictures; pencilmark.draw from Python).
  python tools/render_svg.py puzzle.json out.svg [--dark] [--cell 48] [--card card.json --position N]
The tools import this module as `render_svg` and use render / trace_position / THEMES from it."""

import json
import sys
from pathlib import Path

try:  # an installed pencilmark (with its engine) if there is one, else the source tree
    from pencilmark.render import THEMES, render, svg, trace_position  # noqa: F401
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from pencilmark.render import THEMES, render, svg, trace_position  # noqa: E402, F401

if __name__ == "__main__":
    a = sys.argv
    card = json.load(open(a[a.index("--card") + 1], encoding="utf-8")) if "--card" in a else None
    out = svg(
        json.load(open(a[1], encoding="utf-8")),
        dark="--dark" in a,
        cell=int(a[a.index("--cell") + 1]) if "--cell" in a else 48,
        card=card,
        position=int(a[a.index("--position") + 1]) if "--position" in a else 0,
    )
    Path(a[2]).write_text(out, encoding="utf-8")
