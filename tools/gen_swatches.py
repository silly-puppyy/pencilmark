"""Draw a small 3x3 example of every rule kind for the docs (light and dark), with tools/render_svg.py.

  python tools/gen_swatches.py [out_dir]      default: website/static/img/swatches

Each swatch is a 3x3 board holding one rule (and a few digits where they show the meaning). The docs build runs this
script; the images are not committed. swatches.json lists the names, so a page can check that a swatch exists.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_svg  # noqa: E402

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


def doc_for(rules, givens):
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
    for name, (rules, givens) in SWATCHES.items():
        try:
            for dark, suffix in ((False, ""), (True, "-dark")):
                (out / f"{name}{suffix}.svg").write_text(
                    render_svg.render(doc_for(rules, givens), dark=dark, cell=40), encoding="utf-8"
                )
            done.append(name)
        except Exception as e:  # a swatch the renderer cannot draw is reported, not fatal
            failed[name] = f"{type(e).__name__}: {e}"
    (out / "swatches.json").write_text(json.dumps({"swatches": done, "failed": failed}, indent=1), encoding="utf-8")
    print(f"{len(done)} swatches in {out}" + (f"; failed: {failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
