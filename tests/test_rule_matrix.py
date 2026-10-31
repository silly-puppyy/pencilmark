"""The rule families with no table of their own (corner, sum, neighbours, region, outside clues, count and the rest),
read, written and described exactly as recorded in tests/fixtures/rule_matrix.jsonl (see test_line_matrix.py). Each case
is one rule (sometimes with its negative) on a 4 x 4, 6 x 6 and 9 x 9 board; invalid ones record their error.
Regenerate (only when a change is meant to alter it):
    python tests/test_rule_matrix.py --write
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_line_matrix import BOX, record  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "rule_matrix.jsonl"
BLOCK = ["r1c1", "r1c2", "r2c1", "r2c2"]
RULES = [
    # corner
    [{"type": "corner", "kind": "battenburg", "cells": BLOCK}],
    [{"type": "corner", "kind": "battenburg", "cells": BLOCK}, {"type": "negative", "of": "battenburg"}],
    [{"type": "corner", "kind": "battenburg", "value": 1, "cells": BLOCK}],
    [{"type": "corner", "kind": "battenburg", "cells": ["r1c1", "r1c2", "r2c2", "r2c1"]}],
    [{"type": "corner", "kind": "exclude", "value": 3, "cells": BLOCK}],
    [{"type": "corner", "kind": "exclude", "cells": BLOCK}],
    *[
        [{"type": "corner", "kind": "mathrax", "op": op, "value": v, "cells": BLOCK}]
        for op, v in (("+", 7), ("-", 1), ("x", 6), ("/", 2), ("+", 30))
    ],
    [{"type": "corner", "kind": "mathrax", "op": "even", "cells": BLOCK}],
    [{"type": "corner", "kind": "mathrax", "op": "odd", "value": 1, "cells": BLOCK}],
    [{"type": "corner", "kind": "mathrax", "op": "%", "value": 1, "cells": BLOCK}],
    # sum
    [{"type": "sum", "kind": "little_killer", "sum": 5, "side": "top", "cells": ["r1c2", "r2c3", "r3c4"]}],
    [{"type": "sum", "kind": "little_killer", "sum": 5, "cells": ["r1c2", "r2c3", "r3c4"]}],
    [{"type": "sum", "kind": "frame", "sum": 6, "side": "left", "cells": ["r1c1", "r1c2", "r1c3"]}],
    [{"type": "sum", "kind": "group", "sum": 7, "cells": ["r1c1", "r3c3"]}],
    [{"type": "sum", "kind": "corner", "sum": 10, "cells": BLOCK}],
    [{"type": "sum", "kind": "corner", "sum": 10, "cells": ["r1c1", "r1c2", "r1c3", "r1c4"]}],
    [{"type": "cage", "sum": 3, "cells": ["r1c1", "r1c2"]}],
    [{"type": "cage", "cells": ["r1c1", "r1c2", "r2c2"]}],
    # outside
    [{"type": "sandwich", "sum": 0, "side": "left", "cells": ["r1c1", "r1c2", "r1c3", "r1c4"]}],
    [{"type": "xsum", "sum": 10, "side": "top", "cells": ["r1c1", "r2c1", "r3c1", "r4c1"]}],
    [{"type": "skyscraper", "value": 2, "side": "right", "cells": ["r1c4", "r1c3", "r1c2", "r1c1"]}],
    [{"type": "rossini", "arrow": "in", "side": "top", "cells": ["r1c1", "r2c1", "r3c1"]}],
    [
        {"type": "rossini", "arrow": "in", "side": "top", "cells": ["r1c1", "r2c1", "r3c1"]},
        {"type": "negative", "of": "rossini"},
    ],
    [
        {
            "type": "first_seen",
            "value": 1,
            "digits": [1, 2, 3],
            "side": "left",
            "cells": ["r1c1", "r1c2", "r1c3", "r1c4"],
        }
    ],
    [{"type": "distinct_count", "value": 2, "side": "top", "cells": ["r1c2", "r2c3"]}],
    # neighbours
    *[[{"type": "neighbours", "kind": k}] for k in ("antiknight", "antiking", "nonconsecutive", "antiqueen")],
    [{"type": "neighbours", "op": "difference", "value": 1, "within": 1}],
    # region
    [{"type": "region", "kind": "diagonal", "cells": ["r1c1", "r2c2", "r3c3", "r4c4"]}],
    [{"type": "region", "kind": "window", "cells": BLOCK}],
    [{"type": "region", "kind": "extra", "cells": ["r1c1", "r2c3"]}],
    [{"type": "region", "kind": "disjoint", "cells": ["r1c1", "r1c3"]}],
    [{"type": "region", "kind": "colour", "cells": ["r1c1", "r4c4"]}],
    # sets and the rest
    [{"type": "contains", "digits": [1, 2], "cells": BLOCK}],
    [{"type": "appears", "source": "r1c1", "cells": ["r1c2", "r1c3"]}],
    [{"type": "clone", "regions": [["r1c1", "r1c2"], ["r3c3", "r3c4"]]}],
    [{"type": "count", "kind": "circles", "cells": ["r1c1", "r2c3"]}],
    [{"type": "global_entropy"}],
]


def cases():
    for rules in RULES:
        for D in (4, 6, 9):
            yield {
                "format": "sudoku-puzzle",
                "format_version": 1,
                "board": {"rows": D, "cols": D},
                "digits": D,
                "givens": [0] * (D * D),
                "rules": [{"type": "box_grid", "origin": "r1c1", "box": BOX[D]}, *rules],
            }


def test_rule_matrix():
    expected = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line]
    got = [json.loads(json.dumps(record(d), sort_keys=True)) for d in cases()]
    assert len(got) == len(expected)
    bad = [(e["rule"], e["D"]) for e, g in zip(expected, got) if e != g]
    assert not bad, f"{len(bad)} rule cases differ, first: {bad[:3]}"


if __name__ == "__main__" and "--write" in sys.argv:
    rows = [json.dumps(record(d), sort_keys=True) for d in cases()]
    FIXTURE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} cases to {FIXTURE}")
