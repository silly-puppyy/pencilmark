"""The engine's listing caches (csrc/listing_cache.cpp: per strategy and state, per digit for single-digit techniques)
must not change any move list: contents() of a few golden puzzles lists exactly the same moves with the caches off and
on. The full check over the corpora is the golden gate."""

import json
from pathlib import Path

import pytest

import pencilmark
from pencilmark import _csolver as C
from pencilmark import api
from pencilmark import band_path as BP
from pencilmark import cbackend as CB

INPUTS = Path(__file__).parent / "golden" / "inputs.jsonl"
NAMES = ("fixture-vudoku-sudoku", "gen-9x9-kropki-medium", "gen-9x9-xv-medium")  # rule intersection, fish, chains


@pytest.mark.parametrize("name", NAMES)
def test_listing_cache_changes_nothing(name, monkeypatch):
    doc = next(
        r["puzzle"] for r in map(json.loads, INPUTS.read_text(encoding="utf-8").splitlines()) if r["name"] == name
    )
    P = api._params("human")
    orig = CB.state_moves
    logs = []
    try:
        for on in (False, True):
            C.listing_cache(on)
            log = []

            def listed(*a, **k):
                res = orig(*a, **k)
                log.append(json.dumps(res, sort_keys=True, default=repr))
                return res

            monkeypatch.setattr(CB, "state_moves", listed)
            BP.contents(pencilmark.load(doc), P)
            logs.append(log)
    finally:
        C.listing_cache(True)
    assert len(logs[0]) == len(logs[1])
    bad = [i for i, (a, b) in enumerate(zip(*logs)) if a != b]
    assert not bad, f"{len(bad)} listings differ, first at call {bad[0]}"
