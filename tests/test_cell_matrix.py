"""Every cell kind, read, written and described exactly as recorded in tests/fixtures/cell_matrix.jsonl (the safety net
for moving the cell rules into their own module; see test_line_matrix.py). Each case: kind x board size x parameter x
one or two cells x with or without the matching negative rule ("every cell of the kind is marked").
Regenerate (only when a change is meant to alter it):
    python tests/test_cell_matrix.py --write
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_line_matrix import BOX, record  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "cell_matrix.jsonl"
PARAMS = {
    "odd": [None, ("split", 2)],
    "even": [None],
    "low": [("split", 2), ("split", 3), None, ("values", [1])],
    "high": [("split", 2), ("split", 0)],
    "set": [("values", [1, 2]), ("values", [4]), ("values", [9]), ("values", []), None],
    "exclude": [("values", [3]), ("values", [1, 2]), ("values", [7]), ("split", 2)],
}
CELLS = (["r1c1"], ["r1c1", "r2c3"])


def cases():
    from pencilmark import exchange as X

    for kind in sorted(X.KINDS["cell"]):
        for D in (4, 6, 9):
            for param in PARAMS[kind]:
                for cells in CELLS:
                    for negative in (False, True) if kind in ("odd", "even", "low", "high") else (False,):
                        rule = {"type": "cell", "kind": kind}
                        if param:
                            rule[param[0]] = param[1]
                        rule["cells"] = cells
                        rules = [{"type": "box_grid", "origin": "r1c1", "box": BOX[D]}, rule]
                        if negative:
                            neg = {"type": "negative", "of": "cell", "kind": kind}
                            if param and param[0] == "split":
                                neg["split"] = param[1]
                            rules.append(neg)
                        yield {
                            "format": "sudoku-puzzle",
                            "format_version": 1,
                            "board": {"rows": D, "cols": D},
                            "digits": D,
                            "givens": [0] * (D * D),
                            "rules": rules,
                        }


def test_cell_matrix():
    expected = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line]
    got = [json.loads(json.dumps(record(d), sort_keys=True)) for d in cases()]
    assert len(got) == len(expected)
    bad = [(e["rule"], e["D"]) for e, g in zip(expected, got) if e != g]
    assert not bad, f"{len(bad)} cell cases differ, first: {bad[:3]}"


if __name__ == "__main__" and "--write" in sys.argv:
    rows = [json.dumps(record(d), sort_keys=True) for d in cases()]
    FIXTURE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} cases to {FIXTURE}")
