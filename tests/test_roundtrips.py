"""Every puzzle we ship (the golden inputs, docs/examples, the sudoku-puzzle examples in the docs) survives the format
round trips: to_export is idempotent, and the fingerprint is the same after re-export, dumps and load. Lockout lines
failed this for months because no test wrote every rule kind back. Slow (about 10 s): run with `pytest -m slow`.
"""

import json
import re
from pathlib import Path

import pytest

import pencilmark

ROOT = Path(__file__).resolve().parents[1]


def puzzles():
    out = []
    for line in (ROOT / "tests" / "golden" / "inputs.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if not d["name"].startswith("error-"):
            out.append((d["name"], d["puzzle"]))
    out += [
        (f.stem, json.loads(f.read_text(encoding="utf-8"))) for f in sorted((ROOT / "docs" / "examples").glob("*.json"))
    ]
    for f in sorted((ROOT / "docs").rglob("*.md*")):
        for k, block in enumerate(re.findall(r"```json[^\n]*\n(.*?)```", f.read_text(encoding="utf-8"), re.S)):
            try:
                d = json.loads(block)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("format") == "sudoku-puzzle":
                out.append((f"{f.name}#{k}", d))
    return out


@pytest.mark.slow
@pytest.mark.parametrize("name,puzzle", puzzles(), ids=[n for n, _ in puzzles()])
def test_round_trips(name, puzzle):
    try:
        doc = pencilmark.to_export(puzzle)
    except pencilmark.exchange.FormatError:
        return  # inputs that are invalid on purpose (the golden corpus records their errors)
    fp = pencilmark.fingerprint(doc)
    again = pencilmark.to_export(doc)
    assert again == doc, "to_export is not idempotent"
    assert pencilmark.fingerprint(again) == fp
    text = pencilmark.dumps(doc)
    assert pencilmark.fingerprint(json.loads(text)) == fp, "dumps changes the fingerprint"
    assert pencilmark.fingerprint(pencilmark.to_export(pencilmark.load(text))) == fp, "load(dumps) changes it"
