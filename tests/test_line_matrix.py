"""Every line kind, read, written and described exactly as recorded in tests/fixtures/line_matrix.jsonl.

A safety net for moving the line rules into their own modules: each case (kind x board size x value x closed x touching
cells) records the validation error, or the engine's constraints, the rules written back, describe(), the fingerprint and
the canonical text. Nothing is solved, so it is fast. Regenerate (only when a change is meant to alter it):
    python tests/test_line_matrix.py --write
"""

import json
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "line_matrix.jsonl"
BOX = {4: [2, 2], 6: [2, 3], 9: [3, 3]}
PATH = ["r1c1", "r2c1", "r3c1", "r3c2"]  # touching, 4 cells (fits every board size)
GAPPED = ["r1c1", "r1c3", "r1c4"]  # r1c1 and r1c3 do not touch
VALUES = {"whisper": [None, 5, 4, 2], "modular": [None, 3, 2], "lockout": [None, 4, 2], "entropic": [None, "groups"]}


def cases():
    from pencilmark import exchange as X

    for kind in sorted(X.KINDS["line"]):
        for D in (4, 6, 9):
            for value in VALUES.get(kind, [None]):
                for closed in (None, True, False):
                    for cells in (PATH, GAPPED) if kind in ("whisper", "thermo") else (PATH,):
                        rule = {"type": "line", "kind": kind}
                        if value == "groups":
                            rule["groups"] = (
                                [[1, 2], [3, 4]]
                                if D == 4
                                else [[1, 2], [3, 4], [5, 6]]
                                if D == 6
                                else [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
                            )
                        elif value is not None:
                            rule["value"] = value
                        if closed is not None:
                            rule["closed"] = closed
                        rule["cells"] = cells
                        yield {
                            "format": "sudoku-puzzle",
                            "format_version": 1,
                            "board": {"rows": D, "cols": D},
                            "digits": D,
                            "givens": [0] * (D * D),
                            "rules": [{"type": "box_grid", "origin": "r1c1", "box": BOX[D]}, rule],
                        }


def record(doc):
    import pencilmark
    from pencilmark import exchange as X

    out = {"rule": doc["rules"][1], "D": doc["digits"]}
    try:
        X.validate(doc)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    try:
        p = pencilmark.load(doc)
        out["constraints"] = json.loads(json.dumps(getattr(p, "constraints", []), default=repr, sort_keys=True))
        out["relations"] = len(getattr(p, "relations", []) or [])
        out["written"] = X.write(p)["rules"]
        out["describe"] = pencilmark.describe(doc)
        out["fingerprint"] = pencilmark.fingerprint(doc)
        out["dumps"] = pencilmark.dumps(doc, pretty=False)
    except Exception as e:
        out["read_error"] = f"{type(e).__name__}: {e}"
    return out


def test_line_matrix():
    expected = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line]
    got = [json.loads(json.dumps(record(d), sort_keys=True)) for d in cases()]
    assert len(got) == len(expected)
    bad = [(e["rule"], e["D"]) for e, g in zip(expected, got) if e != g]
    assert not bad, f"{len(bad)} line cases differ, first: {bad[:3]}"


if __name__ == "__main__" and "--write" in sys.argv:
    rows = [json.dumps(record(d), sort_keys=True) for d in cases()]
    FIXTURE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} cases to {FIXTURE}")
