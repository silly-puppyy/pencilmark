"""Every edge kind, read, written and described exactly as recorded in tests/fixtures/edge_matrix.jsonl (the safety net
for moving the edge rules into their own module; see test_line_matrix.py). Each case: kind x board size x parameter x
neighbouring or not x with or without the matching negative rule ("all clues shown", carrying the same selector).
Regenerate (only when a change is meant to alter it):
    python tests/test_edge_matrix.py --write
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_line_matrix import BOX, record  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "edge_matrix.jsonl"
PARAMS = {
    "kropki": [("color", "white"), ("color", "black"), ("color", "grey"), None],
    "xv": [("letter", "X"), ("letter", "V"), ("letter", "Z"), None],
    "difference": [("value", 1), ("value", 3), ("value", 0), None],
    "sum": [("sum", 5), ("sum", 11), ("sum", 40), None],
    "product": [("value", 6), ("value", 7), None],
    "ratio": [("value", 2), ("value", 3), ("value", 1), None],
    "less": [None, ("value", 2)],
}
PAIRS = (["r1c1", "r1c2"], ["r1c1", "r2c1"], ["r1c1", "r2c2"])  # across, down, diagonal (not an edge)


def cases():
    from pencilmark import exchange as X

    for kind in sorted(X.KINDS["edge"]):
        for D in (4, 6, 9):
            for param in PARAMS[kind]:
                for cells in PAIRS:
                    for negative in (False, True) if cells != PAIRS[2] else (False,):
                        rule = {"type": "edge", "kind": kind}
                        if param:
                            rule[param[0]] = param[1]
                        rule["cells"] = cells
                        rules = [{"type": "box_grid", "origin": "r1c1", "box": BOX[D]}, rule]
                        if negative:
                            neg = {"type": "negative", "of": kind}
                            if param and param[0] == X.NEG_SELECTOR.get(kind):
                                neg[param[0]] = param[1]
                            rules.append(neg)
                        yield {
                            "format": "sudoku-puzzle",
                            "format_version": 1,
                            "board": {"rows": D, "cols": D},
                            "digits": D,
                            "givens": [0] * (D * D),
                            "rules": rules,
                        }


def test_edge_matrix():
    expected = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line]
    got = [json.loads(json.dumps(record(d), sort_keys=True)) for d in cases()]
    assert len(got) == len(expected)
    bad = [(e["rule"], e["D"]) for e, g in zip(expected, got) if e != g]
    assert not bad, f"{len(bad)} edge cases differ, first: {bad[:3]}"


if __name__ == "__main__" and "--write" in sys.argv:
    rows = [json.dumps(record(d), sort_keys=True) for d in cases()]
    FIXTURE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} cases to {FIXTURE}")
