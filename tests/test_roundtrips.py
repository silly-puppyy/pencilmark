"""Every puzzle we ship (the golden inputs, docs/examples, the pencilmark-puzzle examples in the docs) survives the format
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
            if isinstance(d, dict) and d.get("format") == "pencilmark-puzzle":
                out.append((f"{f.name}#{k}", d))
    return out


@pytest.mark.slow
@pytest.mark.parametrize("name,puzzle", puzzles(), ids=[n for n, _ in puzzles()])
@pytest.mark.usefixtures("reserved_ok")  # the docs' examples include rules reserved for a later version
def test_round_trips(name, puzzle):
    try:
        doc = pencilmark.write.document(puzzle, solution=True, describe=True)
    except pencilmark.FormatError:
        return  # inputs that are invalid on purpose (the golden corpus records their errors)
    fp = pencilmark.fingerprint(doc)
    again = pencilmark.write.document(doc, solution=True, describe=True)
    assert again == doc, "write.document is not idempotent"
    assert pencilmark.fingerprint(again) == fp
    text = pencilmark.write.pencilmark(doc)
    assert pencilmark.fingerprint(json.loads(text)) == fp, "write.pencilmark changes the fingerprint"
    assert (
        pencilmark.fingerprint(pencilmark.write.document(pencilmark.api._load(text), solution=True, describe=True))
        == fp
    ), "reading write.pencilmark back changes it"
