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
    rows = [
        [{"value": v} if v else {} for v in row] for row in ([1, 2, 3, 4], [3, 4, 1, 2], [2, 1, 4, 3], [4, 3, 2, 0])
    ]
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


def test_sudokupad_rules_text_readings():
    """found on the 500 most-solved LMD sudokus (2026-11-02): "equal digits must not touch diagonally" is anti-king;
    a mostly transparent black (#0003) is drawn grey, so "digits in grey cells are odd" finds the cells"""
    from pencilmark.sources import _sp_translate as SP

    assert SP.rule_flags("Equal digits must not touch each other diagonally.")["antiking"]
    assert SP.rule_flags("No Touch Sudoku: normal rules apply.")["antiking"]
    assert not SP.rule_flags("Digits on a diagonal must not repeat.")["antiking"]
    assert SP.color_name("#0003") == "grey" and SP.color_name("#000") == "black"
    assert SP.color_name("#000000cc") == "black"  # mostly opaque stays black
    # "the sum of the digits placed between 1 and 9" is a sandwich (the pattern wanted "the 1")
    from pencilmark.sources import _fpuz_translate as FT

    fp = {"size": 9, "ruleset": "Digits outside the board give the sum of the digits between 1 and 9 in that row.",
          "text": [{"cells": ["R0C2"], "value": "12"}]}  # fmt: skip
    assert FT.normalise(fp)["sandwichsum"] == [{"cell": "R0C2", "value": "12"}]


def test_sudokupad_uncoloured_dot_follows_the_rules():
    """a kropki dot drawn without a colour is white when the rules mention only white dots (it read as black)"""
    from pencilmark.sources import _sp_translate as SP

    ov = [{"center": [1.0, 0.5], "width": 0.3, "height": 0.3, "rounded": True}]
    sp = {"format": "scl", "meta": {}, "puzzle": {"cells": [[{} for _ in range(4)] for _ in range(4)], "overlays": ov,
                                                   "regions": [[[r, c] for r in range(i // 2 * 2, i // 2 * 2 + 2)
                                                                for c in range(i % 2 * 2, i % 2 * 2 + 2)] for i in range(4)]}}  # fmt: skip
    for text, want in (
        ("Digits separated by a white dot are consecutive.", "diff"),
        ("Black dots: ratio 1:2.", "ratio"),
    ):
        p, _ = SP.translate(sp, text)
        assert any(r[0] == want for r in p.relations), (text, p.relations)


def test_fpuzzles_outside_text_clues():
    """numbers written as plain text outside an f-puzzles grid are the outside clue family the rules name (an x-sums
    puzzle read as a classic without clues: not unique)"""
    from pencilmark.sources import _fpuz_translate as FT

    fp = {"size": 9, "ruleset": "X-Sums: numbers outside the grid give the sum of the first X digits.",
          "text": [{"cells": ["R0C2"], "value": "24"}, {"cells": ["R5C10"], "value": "11"}, {"cells": ["R5C5"], "value": "3"}]}  # fmt: skip
    out = FT.normalise(fp)
    assert out["_xsum"] == [{"cell": "R0C2", "value": "24"}, {"cell": "R5C10", "value": "11"}]
    assert [t["cells"] for t in out["text"]] == [["R5C5"]]  # inside the grid: left alone
    two = FT.normalise(dict(fp, ruleset="Sandwich sums and skyscrapers"))
    assert not two.get("_xsum") and not two.get("sandwichsum")  # two families named: ambiguous, left alone


def test_unmodelled_rules_refused():
    """a mechanic the engine does not model, defined in the rules, refuses the puzzle (its cages or arrows would read as
    killer cages or sums); the same words in a list of the author's series or the solvers' names do not"""
    from pencilmark.sources._sp_translate import unmodelled_rules

    for text, label in (
        ("equality cages: cages must have an equal number of low and high digits", "equality cage"),
        ("look-and-say cages: read the clue out loud", "look-and-say"),
        ("cells a camel move apart may not contain the same digit", "camel"),
        ("cold arrows: a blue arrow points toward a cell n distance away", "cold / hot arrow"),
        ("congruent boxes: the two pairs of coloured boxes are congruent", "congruent"),
    ):
        assert unmodelled_rules(text) == [f"rule '{label}'"], text
    for text in (
        "all my series: equality cages, equalite cages, shifter lines",
        "solved by mobiustrip, camellia, ...",
        "the previous puzzle in the series: shifter lines 118: hot arrows",
        "white dots: one digit is congruent to one more than the other modulo 9",
    ):
        assert unmodelled_rules(text) == [], text
    fp = fpuzzles_json(CLASSIC)
    fp["ruleset"] = "Normal sudoku rules apply. Clones: boxes 1 and 5 are clones of each other."
    with pytest.raises(sources.UnsupportedPuzzle, match="clone"):
        FP.to_puzzle(fpuzzles_url(fp))


def _sp4(**puzzle):
    """a 4x4 SudokuPad puzzle dict (2x2 boxes) with these elements"""
    regions = [
        [[r, c] for r in range(i // 2 * 2, i // 2 * 2 + 2) for c in range(i % 2 * 2, i % 2 * 2 + 2)] for i in range(4)
    ]
    return {
        "format": "scl",
        "meta": {},
        "puzzle": dict(cells=[[{} for _ in range(4)] for _ in range(4)], regions=regions, **puzzle),
    }


def test_sudokupad_misreads_fixed():
    """misreads found on the 500 most-solved LMD sudokus (2026-11-02, each puzzle now unique and matching its embedded
    solution): newer files' grey shorthand ("#F" white, "#0" black) and c2 fill (000Q6G); a same-parity line, which has
    no rule family, is a custom rule (000JCK, it read as alternating); grey thermometers beside grey palindromes are
    told apart by the bulb (000JH3); "all X and V are given" on a grid without one forbids sums of 5 and 10 (000STV)"""
    from pencilmark.sources import _sp_translate as SP
    from pencilmark.sources import sudokupad

    assert [SP.color_name(c) for c in ("#F", "#0", "#999")] == ["white", "black", "grey"]
    for quads in ("quads: the digits inside a circle must appear in the cells touching the circle",
                  "a digit in a circle must appear in one of the four cells the circle touches"):  # fmt: skip
        assert SP.QUAD_TEXT.search(quads), quads  # 000RL6, 000QJZ: the circle quadruples were not read
    dots = [{"center": [1.0, 0.5], "width": 0.33, "rounded": True, "c2": "#F", "c1": "#0"},
            {"center": [1.0, 2.5], "width": 0.33, "rounded": True, "c2": "#0", "color": "#F"}]  # fmt: skip
    p, _ = SP.translate(sudokupad.decode(_sp4(overlays=dots)), "White dots: consecutive. Black dots: ratio 1:2.")
    assert sorted(r[0] for r in p.relations if r[0] in ("diff", "ratio")) == ["diff", "ratio"]

    red = [{"color": "#e6261fff", "thickness": 9.6, "wayPoints": [[0.5, 0.5], [1.5, 0.5], [2.5, 0.5]]}]
    pj = sudokupad.to_puzzle(_sp4(lines=red), page_text="Parity line: digits on the red line all have the same parity.")
    assert {"type": "custom", "label": "Same-parity line", "each": "pair",
            "cells": {"pair": [["r1c1", "r2c1"], ["r2c1", "r3c1"]]}, "holds": "pair[1] mod 2 == pair[2] mod 2"} in pj["rules"]  # fmt: skip

    grey = [{"color": "#cccf", "thickness": 19, "wayPoints": [[0.5, 0.5], [0.5, 1.5]]},
            {"color": "#aaaf", "thickness": 10, "wayPoints": [[2.5, 0.5], [2.5, 1.5], [3.5, 1.5]]}]  # fmt: skip
    bulb = [{"center": [0.5, 0.5], "width": 0.8, "height": 0.8, "rounded": True, "backgroundColor": "#cccf"}]
    p, _ = SP.translate(
        _sp4(lines=grey, underlays=bulb), "Thermometers increase from the bulb. A gray line is a palindrome."
    )
    assert ("lt", 0, 1) in p.relations  # the bulbed grey line: a thermometer
    assert any(r[0] == "eq" for r in p.relations)  # the other: a palindrome

    p, info = SP.translate(
        _sp4(overlays=dots[:1]), "Digits separated by a V sum to 5. All X and V are given. White dots: consecutive."
    )
    assert info.get("negative_xv") and any(r[0] == "notsum" for r in p.relations)


def test_fpuzzles_negative_only_the_named_letter():
    """ "all Vs are given; not all Xs are given" forbids unmarked pairs summing to 5, not to 10 (Stitched Rainbow,
    0007UV, had no solution)"""
    from pencilmark.sources import _fpuz_translate as FT

    fp = fpuzzles_json(CLASSIC)
    fp["xv"] = [{"cells": ["R1C1", "R1C2"], "value": "X"}]
    fp["ruleset"] = "X: sum to 10; V: sum to 5. All Vs are given; not all Xs are given."
    p, _ = FT.translate(fp)
    notsum = {r[3] for r in p.relations if r[0] == "notsum"}
    assert notsum == {5}
