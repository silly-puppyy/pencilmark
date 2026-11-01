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


def test_fpuzzles_lockout_written_back():
    """an imported lockout line exports as a lockout line with its value (it compiled to digit tables, which no format
    rule can carry, so to_export and fingerprint failed on every imported lockout puzzle)"""
    d = fpuzzles_json(CLASSIC)
    d["lockout"] = [{"lines": [["R1C1", "R2C1", "R3C1", "R4C1"]], "value": "5"}]
    doc = pencilmark.to_export(FP.to_puzzle(fpuzzles_url(d), rules_text="Lockout lines: ends differ by at least 5."))
    assert {"type": "line", "kind": "lockout", "value": 5, "cells": ["r1c1", "r2c1", "r3c1", "r4c1"]} in doc["rules"]
    assert pencilmark.fingerprint(doc)


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


def test_malformed_fpuzzles_is_a_decode_error():
    """found by mutating f-puzzles payloads: a missing key or a value of the wrong type raised KeyError / TypeError /
    AttributeError / IndexError from the translator; the readers now say the data is malformed"""
    for broken in ({"killercage": [{"value": "10"}]}, {"thermometer": [{"lines": 5}]}, {"odd": ["R1C1"]}):
        d = dict(fpuzzles_json(CLASSIC), **broken)
        with pytest.raises(sources.DecodeError, match="malformed f-puzzles"):
            FP.to_puzzle(fpuzzles_url(d), rules_text="Normal sudoku rules apply.")


def test_sudokupad_numbers_and_nulls_in_real_files():
    """found reading 19,194 stored SudokuPad puzzles: a colour typed without "#" arrives as a number (777777), an
    all-digit solution as a number, and element lists can hold nulls (SudokuPad skips them); each crashed the reader"""
    rows = [[{"value": v} if v else {} for v in row] for row in ([1, 2, 3, 4], [3, 4, 1, 2], [2, 1, 4, 3], [4, 3, 2, 0])]
    sp = {
        "format": "scl",
        "meta": {"rules": "Normal sudoku rules apply.", "solution": 1234341221434321},
        "puzzle": {
            "cells": rows,
            "regions": [[[r, c] for r in range(a, a + 2) for c in range(b, b + 2)] for a in (0, 2) for b in (0, 2)],
            "lines": [None, {"color": 777777, "thickness": 2, "wayPoints": [[0.5, 0.5], None, [1.5, 0.5]]}],
            "arrows": [None],
            "overlays": [None],
            "cages": [{"cells": [[0, 0], None, [0, 1]], "value": 3}],
        },
    }
    try:
        pj = SP.to_puzzle(sp, fetch=False)
    except sources.UnsupportedPuzzle:  # the grey line may not be read; the point is that nothing crashes
        return
    assert pj["numbers"].startswith("1234")
