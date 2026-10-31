"""Puzzle importers, offline (no network): link detection and payload translation."""

import json
import urllib.parse

import lzstring
import pytest
from conftest import CLASSIC

import pencilmark
from pencilmark import sources
from pencilmark.sources import fpuzzles as FP
from pencilmark.sources import sudokupad as SP


def fpuzzles_json(numbers, cages=()):
    grid = [
        [({"value": int(numbers[r * 9 + c]), "given": True} if numbers[r * 9 + c] != "." else {}) for c in range(9)]
        for r in range(9)
    ]
    d = {"size": 9, "grid": grid}
    if cages:
        d["killercage"] = [{"cells": cells, "value": str(total)} for total, cells in cages]
    return d


def payload(d):
    return "fpuzzles" + lzstring.LZString().compressToBase64(json.dumps(d))


def fpuzzles_url(d):
    return "https://f-puzzles.com/?load=" + urllib.parse.quote(
        lzstring.LZString().compressToBase64(json.dumps(d)), safe=""
    )


def test_detect():
    assert sources.detect("https://sudokupad.app/wjgxgaji9a") == "sudokupad"
    assert sources.detect("https://app.crackingthecryptic.com/sudoku/abc123") == "sudokupad"
    assert sources.detect("https://f-puzzles.com/?id=256hyua6") == "fpuzzles"
    assert sources.detect("https://swaroopg92.github.io/penpa-edit/?m=solve&p=abc") == "penpa"
    assert sources.detect("https://logic-masters.de/Raetselportal/Raetsel/zeigen.php?id=000VEC") == "lmd"
    assert sources.detect("lmd:000VEC") == "lmd"
    assert sources.detect("https://tinyurl.com/22zwurtg") == "short"
    assert sources.detect({"numbers": "." * 81}) == "puzzle_json"
    assert sources.detect("https://example.com/") is None
    with pytest.raises(sources.DecodeError):
        sources.load("https://sudokupad.app/wjgxgaji9a", fetch=False)


def test_sudokupad_decodes_fpuzzles_payload_offline():
    pl = payload({"size": 4, "grid": [[{}] * 4] * 4})
    for x in (
        pl,
        "https://sudokupad.app/" + pl,
        "https://app.crackingthecryptic.com/sudoku/" + pl,
        "https://sudokupad.app/?puzzleid=" + pl,
    ):
        d = SP.decode(x)
        assert d["format"] == "fpuzzles" and d["puzzle"]["size"] == 4


def test_fpuzzles_classic_roundtrip():
    url = fpuzzles_url(fpuzzles_json(CLASSIC))
    pj = FP.to_puzzle(url, rules_text="Normal sudoku rules apply.")
    assert pj["numbers"].replace("0", ".") == CLASSIC
    assert sources.load(url, rules_text="Normal sudoku rules apply.", verify=True)["numbers"] == pj["numbers"]
    assert pencilmark.rate(pj) == pencilmark.rate(CLASSIC)


def test_fpuzzles_killer_cage():
    # a cage that agrees with the classic's solution: still unique, and the cage reaches the engine
    sol = pencilmark.solve(CLASSIC)
    cells = ["R1C1", "R1C2", "R2C1"]
    total = sol[0] + sol[1] + sol[9]
    pj = FP.to_puzzle(
        fpuzzles_url(fpuzzles_json(CLASSIC, [(total, cells)])), rules_text="Normal sudoku and killer rules apply."
    )
    p = pencilmark.load(pj)
    assert any(g.kind == "cage" and g.total == total for g in p.groups)
    assert pencilmark.solve(pj) == sol


def test_user_agent_contact():
    assert "347531506+silly-puppyy@users.noreply.github.com" in sources.USER_AGENT


def test_links_accepted_everywhere():
    """rate / solve and the command line take a link directly (same result as sources.load first)"""
    url = fpuzzles_url(fpuzzles_json(CLASSIC))
    assert pencilmark.solve(url) == pencilmark.solve(CLASSIC)
    assert pencilmark.rate(url, fields=["band"])["band"] == pencilmark.rate(CLASSIC, fields=["band"])["band"]
    assert pencilmark.to_export(url)["meta"]["source"] == url  # the link's metadata is kept
    with pytest.raises(ValueError, match="not a puzzle link"):
        pencilmark.solve("https://example.com/puzzle")
