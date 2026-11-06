"""Every offline input form, read exactly as recorded in tests/fixtures/input_matrix.jsonl: the safety net for moving
the input readers into one registry (step 6 of the restructure). Each case records what pencilmark.api._load() and the CLI's
line reader make of one input (the canonical pencilmark-puzzle text, or the error). Nothing is fetched or solved.
Regenerate (only when a change is meant to alter it):
    python tests/test_input_matrix.py --write
"""

import json
import sys
import urllib.parse
from pathlib import Path

import lzstring

FIXTURE = Path(__file__).parent / "fixtures" / "input_matrix.jsonl"
CLASSIC = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."
SIX = "1.....3....1.5..2...6..4....1.2.....5."[:36]


def _fp(numbers, cages=()):
    grid = [
        [({"value": int(numbers[r * 9 + c]), "given": True} if numbers[r * 9 + c] != "." else {}) for c in range(9)]
        for r in range(9)
    ]
    d = {"size": 9, "grid": grid}
    if cages:
        d["killercage"] = [{"cells": cells, "value": str(total)} for total, cells in cages]
    return d


def inputs():
    """(name, input) pairs; built here so the fixture holds names, not payloads"""
    import pencilmark

    doc = pencilmark.read.auto(CLASSIC)
    lz = lzstring.LZString().compressToBase64(json.dumps(_fp(CLASSIC, [(10, ["R1C1", "R1C2"])])))
    grid = "\n".join(" ".join(CLASSIC[r * 9 : r * 9 + 9]) for r in range(9))
    return [
        ("plain dots", CLASSIC),
        ("plain zeros", CLASSIC.replace(".", "0")),
        ("plain comment", CLASSIC + " # a comment"),
        ("plain 6x6", SIX),
        ("plain short", CLASSIC[:80]),
        ("plain letters", "abc"),
        ("empty", ""),
        ("text grid", grid),
        ("packed", pencilmark.write.sudokuwiki(CLASSIC)),
        ("pencilmark-puzzle dict", doc),
        ("pencilmark-puzzle text", json.dumps(doc)),
        ("sample-pack line", {"puzzle": doc, "grade": {"difficulty": 1.0}}),
        ("puzzle json numbers", {"numbers": CLASSIC}),
        ("ipuz dict", pencilmark.write.ipuz(CLASSIC)),
        ("ipuz text", json.dumps(pencilmark.write.ipuz(CLASSIC))),
        ("fpuzzles link", "https://f-puzzles.com/?load=" + urllib.parse.quote(lz, safe="")),
        ("fpuzzles payload", "fpuzzles" + lz),
        ("sudokupad fpuzzles link", "https://sudokupad.app/fpuzzles" + lz),
        ("unknown link", "https://example.com/"),
        ("number", 5),
        ("none", None),
    ]


def record(name, x):
    import pencilmark
    from pencilmark import exchange as X

    out = {"input": name}

    def canon(fn):
        try:
            p = fn()
            return X.dumps(X.write(p), pretty=False)
        except Exception as e:
            return f"{type(e).__name__}: {e}"[:300]

    out["read"] = canon(lambda: pencilmark.api._load(pencilmark.read.auto(x)))  # what rate and the command line read
    return out


def test_input_matrix(monkeypatch):
    import socket

    def no_net(*a, **k):
        raise OSError("network disabled in test_input_matrix")

    monkeypatch.setattr(socket, "create_connection", no_net)
    expected = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line]
    got = [json.loads(json.dumps(record(n, x), sort_keys=True)) for n, x in inputs()]
    assert len(got) == len(expected)
    bad = [e["input"] for e, g in zip(expected, got) if e != g]
    assert not bad, f"{len(bad)} input cases differ: {bad}"


if __name__ == "__main__" and "--write" in sys.argv:
    import socket

    socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("network disabled in test_input_matrix"))
    rows = [json.dumps(record(n, x), sort_keys=True) for n, x in inputs()]
    FIXTURE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} cases to {FIXTURE}")
