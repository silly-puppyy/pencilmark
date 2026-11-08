"""Puzzle importers, offline (no network): link detection and payload translation."""

import json
import re
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
    with pytest.raises(sources.FormatError):
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
    assert pencilmark.rate(pencilmark.read._document(pj)) == pencilmark.rate(CLASSIC)


def test_fpuzzles_killer_cage():
    # a cage that agrees with the classic's solution: still unique, and the cage reaches the engine
    sol = pencilmark.solve(CLASSIC)
    cells = ["R1C1", "R1C2", "R2C1"]
    total = sol[0] + sol[1] + sol[9]
    pj = FP.to_puzzle(
        fpuzzles_url(fpuzzles_json(CLASSIC, [(total, cells)])), rules_text="Normal sudoku and killer rules apply."
    )
    p = pencilmark.api._load(pj)
    assert any(g.kind == "cage" and g.total == total for g in p.groups)
    assert pencilmark.solve(pj) == sol


def test_fpuzzles_lockout_written_back():
    """an imported lockout line exports as a lockout line with its value (it compiled to digit tables, which no format
    rule can carry, so to_export and fingerprint failed on every imported lockout puzzle)"""
    d = fpuzzles_json(CLASSIC)
    d["lockout"] = [{"lines": [["R1C1", "R2C1", "R3C1", "R4C1"]], "value": "5"}]
    doc = pencilmark.write.document(
        pencilmark.read._document(
            FP.to_puzzle(fpuzzles_url(d), rules_text="Lockout lines: ends differ by at least 5.")
        ),
        solution=True,
        describe=True,
    )
    assert {"type": "line", "kind": "lockout", "value": 5, "cells": ["r1c1", "r2c1", "r3c1", "r4c1"]} in doc["rules"]
    assert pencilmark.fingerprint(doc)


def test_fpuzzles_generic_line_from_rules_text():
    """generic f-puzzles lines take their meaning from the rules text as SudokuPad lines do: by color, or the one line
    rule a single-color puzzle's text describes; a line rule left unread stays refused"""
    from pencilmark.sources import _fpuz_translate as FT

    line = lambda col: {"lines": [["R1C1", "R1C2", "R1C3"]], "outlineC": col}
    fp = {"line": [line("#c060f0"), line("#67f067")]}
    fp["ruleset"] = (
        "A purple line holds a set of consecutive digits. Adjacent digits on a green line differ by at least 5."
    )
    assert FT.text_line_reading(fp) == {"#c060f0": "renban", "#67f067": "whisper"}
    one = {"line": [line("#a0a0a0")], "ruleset": "Digits on a line may not repeat and form a consecutive set."}
    assert FT.text_line_reading(one) == {"#a0a0a0": "renban"}
    one["ruleset"] = "Every triple of adjacent digits on a line has one digit the sum of the other two."
    assert FT.text_line_reading(one) is None


def test_user_agent_contact():
    assert "347531506+silly-puppyy@users.noreply.github.com" in sources.USER_AGENT


def test_links_accepted_everywhere():
    """rate / solve and the command line take a link directly (same result as sources.load first)"""
    url = fpuzzles_url(fpuzzles_json(CLASSIC))
    assert pencilmark.solve(url) == pencilmark.solve(CLASSIC)
    assert pencilmark.rate(url, fields=["band"])["band"] == pencilmark.rate(CLASSIC, fields=["band"])["band"]
    assert (
        pencilmark.write.document(url, solution=True, describe=True)["meta"]["source"] == url
    )  # the link's metadata is kept
    with pytest.raises(pencilmark.FormatError, match="unrecognised puzzle link"):
        pencilmark.solve("https://example.com/puzzle")


def test_malformed_fpuzzles_is_a_decode_error():
    """found by mutating f-puzzles payloads: a missing key or a value of the wrong type raised KeyError / TypeError /
    AttributeError / IndexError from the translator; the readers now say the data is malformed"""
    for broken in ({"killercage": [{"value": "10"}]}, {"thermometer": [{"lines": 5}]}, {"odd": ["R1C1"]}):
        d = dict(fpuzzles_json(CLASSIC), **broken)
        with pytest.raises(sources.FormatError, match="malformed f-puzzles"):
            FP.to_puzzle(fpuzzles_url(d), rules_text="Normal sudoku rules apply.")


def test_sudokupad_numbers_and_nulls_in_real_files():
    """found reading 19,194 stored SudokuPad puzzles: a color typed without "#" arrives as a number (777777), an
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
    except sources.NotSupportedError:  # the gray line may not be read; the point is that nothing crashes
        return
    assert pj["numbers"].startswith("1234")


def test_sudokupad_rules_text_readings():
    """found on the 500 most-solved LMD sudokus (2026-11-02): "equal digits must not touch diagonally" is anti-king;
    a mostly transparent black (#0003) is drawn gray, so "digits in gray cells are odd" finds the cells"""
    from pencilmark.sources import _sp_translate as SP

    assert SP.rule_flags("Equal digits must not touch each other diagonally.")["antiking"]
    assert SP.rule_flags("No Touch Sudoku: normal rules apply.")["antiking"]
    # typographic apostrophes (GMPuzzles: "a chess king’s move") and "increase or stay the same" (slow thermometers)
    assert SP.rule_flags("cells sharing a corner differ (a chess king\u2019s move)".translate(SP.TYPO_QUOTES))[
        "antiking"
    ]
    assert SP.SLOW_ALL.search("numbers must either increase or stay the same from the bulb")
    assert not SP.rule_flags("Digits on a diagonal must not repeat.")["antiking"]
    assert SP.color_name("#0003") == "grey" and SP.color_name("#000") == "black"
    assert SP.color_name("#000000cc") == "black"  # mostly opaque stays black
    # "the sum of the digits placed between 1 and 9" is a sandwich (the pattern wanted "the 1")
    from pencilmark.sources import _fpuz_translate as FT

    fp = {"size": 9, "ruleset": "Digits outside the board give the sum of the digits between 1 and 9 in that row.",
          "text": [{"cells": ["R0C2"], "value": "12"}]}  # fmt: skip
    assert FT.normalise(fp)["sandwichsum"] == [{"cell": "R0C2", "value": "12"}]


def test_sudokupad_uncoloured_dot_follows_the_rules():
    """a kropki dot drawn without a color is white when the rules mention only white dots (it read as black)"""
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
        ("congruent boxes: the two pairs of colored boxes are congruent", "congruent"),
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
    with pytest.raises(sources.NotSupportedError, match="clone"):
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
    solution): newer files' gray shorthand ("#F" white, "#0" black) and c2 fill (000Q6G); a same-parity line, which has
    no rule family, is a custom rule (000JCK, it read as alternating); gray thermometers beside gray palindromes are
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
    assert {"type": "line", "kind": "thermo", "cells": [0, 1]} in p.constraints  # the bulbed gray line: a thermometer
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


def test_default_line_colour_needs_the_rules_to_describe_it():
    """a line whose color the rules do not name takes SudokuPad's default meaning only when the rules describe that
    meaning: a cyan line under "adjacent digits on an N-cell line differ by at least N" read as a region sum (Quiet
    Room, 000TBF); "a pink line holds consecutive digits" is still a renban (000QJZ)"""
    from pencilmark.sources import _sp_translate as SP

    line = lambda col: [{"color": col, "thickness": 9.6, "wayPoints": [[0.5, 0.5], [1.5, 0.5], [2.5, 0.5]]}]
    p, why = SP.translate(
        _sp4(lines=line("#b8d1dcff")), "Along a line of N cells, adjacent digits differ by at least N."
    )
    assert p is None and "cyan line" in why
    p, info = SP.translate(_sp4(lines=line("#f067f0ff")), "Digits on a pink line form a consecutive set in any order.")
    assert info.get("renban")


def test_line_colour_from_described_rule():
    """CTC rules often describe a line without naming it (screen of 1,351 CTC puzzles, 2026-11-03): "a purple line
    contains a set of consecutive digits" is a renban, "box borders divide a blue line into segments with the same sum"
    a region sum; the same words about a cage color no line"""
    from pencilmark.sources import _sp_translate as SP

    got = SP.rules_color_map("A purple line contains a set of consecutive digits in any order.")
    assert got == {"purple": "renban"}
    assert SP.rules_color_map("Box borders divide a blue line into segments with the same sum.") == {
        "blue": "region_sum"
    }
    assert SP.rules_color_map("Digits in a cage form a consecutive set. Red circles are odd.") == {}
    assert SP.rules_color_map("The sum of any three consecutive digits along a red line is divisible by 3.") == {}
    assert (
        SP.rules_color_map("Digits on lines of the same color sum to the same total.") == {}
    )  # no boxes: not a region sum
    assert SP.unmodelled_rules("anti renban: digits on a purple line must not all be consecutive.")
    assert not SP.unmodelled_rules("exactly one cage is lying. multiplying the end digits gives the sum.")  # not "yin"
    assert SP.unmodelled_rules("yin yang: shade some cells so that the shaded cells are connected.")
    assert SP.unmodelled_rules("on a broken zipper, no pairs the same distance from the center have the same sum")


def test_region_sum_loop_and_per_box_wording():
    """a closed region-sum loop's last and first segments are one segment (CTC brC06xfMLyc read as no solution); a
    line re-entering a box under "the same total in each box the line visits" is refused (one total per box)"""
    from pencilmark.sources import _sp_translate as SP

    wp = [[0.5, 1.5], [0.5, 2.5], [1.5, 2.5], [1.5, 1.5], [0.5, 1.5]]  # r1c2 r1c3 r2c3 r2c2, back to r1c2
    sp = _sp4(lines=[{"color": "#34BBE6", "thickness": 9.6, "wayPoints": wp}])
    p, _ = SP.translate(sp, "Box borders divide a blue line into segments with the same sum.")
    assert [sorted(sg) for c in p.constraints if c["type"] == "equal_sum" for sg in c["segments"]] == [[1, 5], [2, 6]]
    wp = [[0.5, 0.5], [0.5, 2.5], [1.5, 1.5]]  # r1c1 r1c2 | r1c3 | r2c2: box 1 twice
    sp = _sp4(lines=[{"color": "#34BBE6", "thickness": 9.6, "wayPoints": wp}])
    p, why = SP.translate(sp, "Digits on a blue line sum to the same total in each box the line visits.")
    assert p is None and "re-entering a box" in why


def test_default_colours_need_a_positive_description():
    """SudokuPad's default line colors count only when a sentence about a line says the meaning positively (CTC
    misreads: "nor can it contain any consecutive digits" as renban, "increase from one end to the other" as a
    thermometer with a bulb, "digits along a line sum to the product of ..." as a region sum); rings drawn along grid
    lines around clues are not lines (eXAb7nRcveM), lines drawn offset inside their cells are (Overlap)"""
    from pencilmark.sources import _sp_translate as SP

    assert not SP.default_evidence(
        "renban", "A purple line cannot repeat a digit; nor can it contain any consecutive digits."
    )
    assert SP.default_evidence("renban", "Digits on a line form a consecutive set.")
    assert not SP.default_evidence("thermo", "The digits on a line must increase from one end to the other.")
    assert not SP.default_evidence("region_sum", "Digits along a line sum to the product of the digits at its ends.")
    assert SP.default_evidence(
        "region_sum", "Region borders divide blue lines into segments. Each segment of a line sums to one value."
    )
    ring = [
        [0.75, 2.5],
        [1, 2.75],
        [2, 2.75],
        [2.75, 2],
        [2.75, 1],
        [2, 0.25],
        [1, 0.25],
        [0.25, 1],
        [0.25, 2],
        [0.75, 2.5],
    ]
    offset = [[0.3, 0.3], [0.3, 2.7]]
    items = SP.line_items(
        {"lines": [{"color": "#2ecbff", "wayPoints": ring}, {"color": "#f067f0", "wayPoints": offset}]}, 4
    )
    assert [it[0] for it in items] == ["offcentre", "pink"]


def test_branching_arrow():
    """an arrow starting on another arrow's shaft is a branch: the circle sums the stem up to the fork plus the branch
    (CTC TrSwZ9PQ6k8, refused as an arrow without circle)"""
    from pencilmark.sources import _sp_translate as SP

    circle = [{"center": [0.5, 0.5], "width": 0.85, "height": 0.85, "rounded": True, "borderColor": "#CFCFCF"}]
    arrows = [
        {"wayPoints": [[0.8, 0.5], [2.5, 0.5]], "color": "#CFCFCF", "headLength": 0.3},  # r1c1: r2c1 r3c1
        {"wayPoints": [[1.5, 0.5], [1.5, 2.5]], "color": "#CFCFCF", "headLength": 0.3},
    ]  # fork at r2c1: r2c2 r2c3
    p, _ = SP.translate(_sp4(arrows=arrows, overlays=circle), "Digits along an arrow sum to the digit in its circle.")
    got = sorted(c["line"] for c in p.constraints if c["type"] == "arrow")
    assert got == [[4, 5, 6], [4, 8]]  # the branch keeps the stem's r2c1


def test_yin_yang_couplings_read():
    """yin-yang texts: the frame and the couplings setters repeat become the yin_yang rule and shaded() rules; any other
    sentence about the shading leaves the puzzle refused, and other shading genres are not read as yin-yang"""
    from pencilmark.sources import _sp_translate as SP

    frame = "Yin Yang: shade some cells so that shaded and unshaded cells are each connected; no 2x2 is one color. "
    got = SP.yin_yang_reading(frame + "Even digits in a cage are always shaded, odd digits are always unshaded.")
    assert got == [("cage", "even", True), ("cage", "odd", False)]
    assert SP.yin_yang_reading(frame + "Odd digits on a thermometer are shaded.") == [("thermo", "odd", True)]
    assert SP.yin_yang_reading(frame) == []
    assert SP.yin_yang_reading(frame + "A digit in a square counts the cells of the same color it sees.") is None
    assert SP.yin_yang_reading("Nurikabe: shade some cells; each island is connected; no 2x2 is shaded.") is None
    p, info = SP.translate(_sp4(), frame + "Shaded cells contain odd digits.")
    assert info.get("yin_yang") and any(c.get("type") == "yin_yang" for c in p.constraints)


def test_outside_clue_wordings_and_arrowheads():
    """GMPuzzles' GAS texts: skyscrapers stated as buildings seen, sum frames as the first three cells; little killer
    arrows drawn as a short line beside the clue"""
    from pencilmark.sources import _sp_translate as SP

    clue = lambda r, c, v: {"center": [r, c], "width": 0, "height": 0, "text": v}
    sp = _sp4(overlays=[clue(-0.36, 0.5, 4)])
    p, _ = SP.translate(sp, "Clues outside the grid indicate how many buildings can be seen; taller buildings block.")
    assert [c["type"] for c in p.constraints] == ["skyscraper"]
    p, _ = SP.translate(sp, "Clues outside give the sum of the values in the first two cells seen in that direction.")
    assert [(c["type"], len(c["cells"])) for c in p.constraints] == [("sum", 2)]
    head = {"color": "#0", "wayPoints": [[-0.28, 0.72], [-0.15, 0.85], [-0.12, 0.81]]}
    p, _ = SP.translate(_sp4(overlays=[clue(-0.36, 0.5, 4)], lines=[head]), "Numbers along diagonals sum to the clue.")
    assert [(c["type"], c["cells"]) for c in p.constraints] == [("little_killer", [1, 6, 11])]  # r1c2 r2c3 r3c4


def test_fortress_and_native_xsum():
    """fortress: gray cells exceed their white neighbors only (f-puzzles 'maximum' cells side by side read with no
    solution); SudokuPad gray squares are fortress cells when the text says so; f-puzzles' own xsum key is read"""
    from pencilmark.sources import _fpuz_translate as FT
    from pencilmark.sources import _sp_translate as SP

    fp = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)], "ruleset": "Fortress.",
          "maximum": [{"cell": "R1C1"}, {"cell": "R1C2"}]}  # fmt: skip
    p, _ = FT.translate(fp)
    assert ("lt", 0, 1) not in p.relations and ("lt", 1, 0) not in p.relations and ("lt", 4, 0) in p.relations
    grey = [{"center": [0.5, 0.5], "width": 1, "height": 1, "backgroundColor": "#cccccc"}]
    p, info = SP.translate(_sp4(underlays=grey), "A number in a gray cell must be larger than any adjacent white cell.")
    assert info.get("fortress") and {("lt", 1, 0), ("lt", 4, 0)} <= set(p.relations)
    fp = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)], "ruleset": "X-sums.",
          "xsum": [{"cell": "R0C1", "value": "4"}]}  # fmt: skip
    p, _ = FT.translate(fp)
    assert [c["type"] for c in p.constraints] == ["xsum"]


def test_clones_from_coloured_shapes():
    """clones drawn as colored shapes become clone rules: same-color shapes matched by translation, cells paired in
    reading order; shapes that differ stay refused; a payload whose clones use different colors is one class"""
    from pencilmark.sources import _sp_translate as SP

    two = {(0, 0): "red", (0, 1): "red", (2, 2): "red", (2, 3): "red"}
    assert SP.clone_groups(two) == [[[(0, 0), (0, 1)], [(2, 2), (2, 3)]]]
    assert SP.clone_groups({**two, (3, 3): "red"}) is None  # the second shape differs
    sq = lambda r, c, col: {"center": [r + 0.5, c + 0.5], "width": 1, "height": 1, "backgroundColor": col}
    sp = _sp4(underlays=[sq(0, 0, "#FFA3A3BF"), sq(0, 1, "#FFA3A3BF"), sq(2, 2, "#FFB3FFBF"), sq(2, 3, "#FFB3FFBF")])
    p, info = SP.translate(
        sp, "Each colored connected shape (clone) must contain the same numbers in the same positions."
    )
    assert info.get("clone") and [c["regions"] for c in p.constraints if c["type"] == "clone"] == [[[0, 1], [10, 11]]]


def test_rossini_and_battenburg():
    """Rossini arrows are short lines outside the grid (the shaft's direction says in / out); Battenburg markers are
    small squares on cell corners (the 4 cells around it); "all ... clues are given" adds the negatives unless the
    text says an absent clue means nothing"""
    from pencilmark.sources import _sp_translate as SP

    arrow = {"color": "#000000", "thickness": 2, "wayPoints": [[1.5, -0.88], [1.5, -0.29], [1.44, -0.29]]}
    p, info = SP.translate(
        _sp4(lines=[arrow]), "Rossini: the first three digits increase in the direction of the arrow."
    )
    assert info.get("rossini") and p is not None
    mark = {"center": [2, 2], "width": 0.6, "height": 0.6, "backgroundColor": "#CFCFCF"}
    text = "Battenburg: the four cells around a marker form a checkerboard of odd and even. All clues are given."
    p, info = SP.translate(_sp4(overlays=[mark]), text)
    tables = [c for c in p.constraints if c["type"] == "table"]
    assert info.get("battenburg") and len(tables) == 9 and [5, 6, 9, 10] in [t["cells"] for t in tables]
    p, _ = SP.translate(_sp4(overlays=[mark]), text + " The absence of a clue has no meaning.")
    assert [t["cells"] for t in p.constraints if t["type"] == "table"] == [[5, 6, 9, 10]]
    sum_ = {"text": 20, "center": [2.09, 2], "width": 0, "height": 0, "fontSize": 12}
    p, _ = SP.translate(_sp4(overlays=[mark, sum_]), text + " A number on a marking is the sum of its 4 cells.")
    assert {"type": "sum", "cells": [5, 6, 9, 10], "total": 20} in p.constraints and not p.relations


def test_one_off_line_rules():
    """one-off line rules described in the text are custom rules (sequence, alternating, one-digit lines) or difference
    pairs (neighbors differ by 1); "along each line" gives every line the rule; "a difference of 4 or more" is a
    Dutch whisper; an f-puzzles payload's own ruleset falls back to the page's wording for its lines"""
    from pencilmark.sources import _fpuz_translate as FT
    from pencilmark.sources import _sp_translate as SP

    line = lambda col: {"color": col, "thickness": 9.6, "wayPoints": [[0.5, 0.5], [0.5, 1.5], [0.5, 2.5]]}
    seq = "An arithmetic series must be formed along each line."
    p, _ = SP.translate(_sp4(lines=[line("#AAAAAA"), line("#FF6666")]), seq)
    custom = [r for r, _ in p.named_rules if r["type"] == "custom"]
    assert len(custom) == 2 and custom[0]["cells"] == {"t": [["r1c1", "r1c2", "r1c3"]]}
    p, _ = SP.translate(
        _sp4(lines=[line("#AAAAAA")]), "Numbers must alternate between increasing and decreasing along the gray lines."
    )
    assert [r["label"] for r, _ in p.named_rules if r["type"] == "custom"] == ["Alternating line"]
    p, _ = SP.translate(
        _sp4(lines=[line("#AAAAAA")]), "Numbers adjacent to each other along the gray lines must differ by 1."
    )
    assert ("diff", 0, 1, 1) in p.relations
    assert SP.diff_rule("adjoining digits must have a difference of 4 or more") == "dutch"
    fp = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)], "ruleset": "Lines.",
          "_page_rules": "Each line contains exactly one distinct number.",
          "line": [{"lines": [["R1C1", "R2C2"]], "outlineC": "#CCCCCC"}]}  # fmt: skip
    assert FT.text_line_reading(fp) == {"#cccccc": "same_digit"}  # a custom-rule line
    fp["_page_rules"] = "Along each gray line, adjoining digits must have a difference of 4 or more."
    assert FT.text_line_reading(fp) == {"#cccccc": "dutch_whisper"}


def test_drawn_styles():
    """a SudokuPad puzzle's look goes to its rules' cosmetic style on export (a purple renban stays purple), not with
    style=False, and never changes the fingerprint"""
    import pencilmark as pm
    from pencilmark.sources import sudokupad as SP

    line = {"color": "#C060C0FF", "thickness": 12.8, "wayPoints": [[0.5, 0.5], [0.5, 1.5], [0.5, 2.5]]}
    dot = {
        "center": [1, 0.5],
        "width": 0.3,
        "height": 0.3,
        "rounded": True,
        "backgroundColor": "#FFFFFF",
        "borderColor": "#000",
    }
    sp = _sp4(lines=[line], overlays=[dot])
    sp["meta"]["rules"] = (
        "Digits on the line form a set of consecutive digits. Digits separated by a white dot are consecutive."
    )
    pj = SP.to_puzzle(sp, fetch=False)
    doc = pm.write.document(pm.read._document(pj), describe=True)
    style = {r.get("kind"): r.get("style") for r in doc["rules"]}
    assert style["renban"] == {"color": "#c060c0", "width": 0.2}
    assert style["kropki"] == {
        "fill": "#ffffff",
        "color": "#000000",
        "shape": "circle",
        "size": 0.3,
    }  # the dot is 0.3 cells
    plain = dict(doc, rules=[{k: v for k, v in r.items() if k != "style"} for r in doc["rules"]])
    assert pm.fingerprint(doc) == pm.fingerprint(plain)  # styles are cosmetic
    # a SudokuPad thermometer stays a thermo line (with its color), a board-sized fill is the background decoration
    thermo = {"color": "#a29b65ff", "thickness": 16, "wayPoints": [[0.5, 0.5], [1.5, 1.5], [1.5, 2.5]]}
    bulb = {"center": [0.5, 0.5], "width": 0.7, "height": 0.7, "rounded": True, "backgroundColor": "#a29b65ff"}
    bg = {"center": [2, 2], "width": 4, "height": 4, "backgroundColor": "#d3f2844f"}
    sp = _sp4(lines=[thermo], underlays=[bg, bulb])
    sp["meta"]["rules"] = "Along a thermometer, digits increase from the bulb."
    doc = pm.write.document(pm.read._document(SP.to_puzzle(sp, fetch=False)), describe=True)
    assert {
        "type": "line",
        "kind": "thermo",
        "cells": ["r1c1", "r2c2", "r2c3"],
        "style": {"color": "#a29b65", "width": 0.25},
    } in doc["rules"]
    assert doc["decorations"] == [
        {"kind": "rect", "center": [2, 2], "size": [4, 4], "style": {"fill": "#d3f284", "opacity": 0.31}}
    ]
    pm.validate(doc)


def test_one_off_outside_clues():
    """one-off outside clues are custom rules over the cells seen from the clue: a digit string is several digits where
    the rule takes digits ("12": 1 and 2 in the first three cells), else one number; a clue 0 stored as a number is
    read, not dropped"""
    from pencilmark.sources import _sp_translate as SP

    clue = lambda y, x, t: {"center": [y, x], "text": t, "width": 0, "height": 0, "fontSize": 30}
    p, _ = SP.translate(_sp4(overlays=[clue(-0.5, 0.5, "12")]), "These numbers must appear in the first three cells.")
    holds = [r["holds"] for r, _ in p.named_rules if r["type"] == "custom"]
    assert holds == ["any(x == 1 for x in take(3, ray))", "any(x == 2 for x in take(3, ray))"]
    p, _ = SP.translate(_sp4(overlays=[clue(1.5, 4.5, 2)]), "Each clue is the median of the first three cells.")
    rule = next(r for r, _ in p.named_rules if r["type"] == "custom")
    assert rule["cells"]["ray"][0] == "r2c4" and rule["holds"] == "median(take(3, ray)) == 2"
    text = "Clues outside the grid indicate the number of pairs of adjacent consecutive numbers in that row."
    p, _ = SP.translate(_sp4(overlays=[clue(0.5, -0.5, 0)]), text)
    assert [r["holds"] for r, _ in p.named_rules] == ["count(i for i in {1..3} if abs(ray[i + 1] - ray[i]) == 1) == 0"]


def test_one_off_global_rules():
    """whole-grid rules stated only in the text become scoped custom rules (encaged digits, no three of a parity in a
    row, anti-XV, no checkerboard, box triples divisible by three); the reader's puzzle JSON writes them"""
    from pencilmark.sources import _sp_translate as SP
    from pencilmark.sources import sudokupad

    kinds = lambda text: SP.global_custom(9, SP.M.standard(9, 3, 3), text)
    assert kinds("All fours are encaged by odd numbers.") == ["encaged"]
    assert kinds("There may not exist a run of three or more cells horizontally or vertically in the grid that all "
                 "contain numbers of the same parity.") == ["no_three_parity", "no_three_parity"]  # fmt: skip
    assert kinds("No two numbers in adjacent cells can sum to exactly 10 or 5.") == ["anti_xv"]
    assert kinds("There can be no four cell intersections where the numbers form a checkerboard pattern.") == [
        "anti_battenburg"
    ]
    assert kinds("Each of the three sets of three horizontally adjacent cells must have a sum divisible by three.") == [
        "box_triples_mod3"
    ]
    sp = _sp4()
    sp["meta"]["rules"] = "No two numbers in adjacent cells can sum to exactly 10 or 5."
    pj = sudokupad.to_puzzle(sp, fetch=False)
    assert [r["scope"] for r in pj["rules"] if r["type"] == "custom"] == [{"pairs": "orthogonal"}]


def test_shape_digit_sets_and_unread_drawings():
    """shapes with digit sets by color ("orange circles contain numbers from {1, 2, 3}, blue squares ... {4, 5, 6}");
    a puzzle that reads as plain sudoku while it draws shapes or lines in the grid is refused, not misread"""
    from pencilmark.sources import _sp_translate as SP

    shape = lambda r, c, col, rounded: {"center": [r + 0.5, c + 0.5], "width": 0.8, "height": 0.8,
                                        "rounded": rounded, "backgroundColor": col}  # fmt: skip
    sp = _sp4(underlays=[shape(0, 0, "#FFA500", True), shape(1, 1, "#4A90E2", False)])
    p, _ = SP.translate(sp, "Orange circles contain numbers from {1, 2}, and blue squares contain numbers from {3, 4}.")
    assert p.domains[0] == 0b0011 and p.domains[5] == 0b1100
    sp = _sp4(underlays=[shape(0, c, "#FFA500", True) for c in range(3)])
    p, why = SP.translate(sp, "Normal sudoku rules apply.")
    assert p is None and "drawn elements no rule reads" in why


def test_marked_cell_clues():
    """one-off clues on marked cells: a circled cell against its neighbors, a small arrow inside a cell against the
    cells in its direction (an open arrowhead or a closed outline), as custom rules"""
    from pencilmark.sources import _sp_translate as SP

    circle = {"center": [1.5, 1.5], "width": 0.886, "rounded": 1, "backgroundColor": "#F", "borderColor": "#0"}
    p, _ = SP.translate(
        _sp4(underlays=[circle]), "A circled number in a cell must equal the sum of all orthogonally adjacent numbers."
    )
    rule = next(r for r, _ in p.named_rules)
    assert rule["holds"] == "x == sum(N)" and rule["cells"] == {"x": ["r2c2"], "N": ["r2c3", "r3c2", "r2c1", "r1c2"]}
    head = {"color": "#0", "thickness": 4, "wayPoints": [[0.72, 0.72], [0.85, 0.85], [0.88, 0.81], [0.89, 0.89]]}
    p, _ = SP.translate(
        _sp4(lines=[head]), "Numbers in gray arrows must appear at least once in the indicated direction."
    )
    assert next(r for r, _ in p.named_rules)["cells"]["N"] == ["r2c2", "r3c3", "r4c4"]
    outline = [[0.23, 0.23], [0.37, 0.09], [0.64, 0.36], [0.78, 0.22], [0.78, 0.78], [0.22, 0.78], [0.36, 0.64],
               [0.09, 0.37], [0.23, 0.23]]  # fmt: skip
    marks = SP._cell_markers({"lines": [{"wayPoints": outline}]}, 4, lambda rc: 0 <= min(rc) and max(rc) < 4)
    assert marks["arrow"] == [((0, 0), (1, 1))]


def test_arrow_variants():
    """arrows whose text changes the rule become custom rules over the circle c and the line L (the sum rule dropped);
    a text that adds a condition keeps the sum rule beside it"""
    from pencilmark.sources import _sp_translate as SP

    circle = {"center": [0.5, 0.5], "width": 0.8, "height": 0.8, "rounded": True, "borderColor": "#000000"}
    arrow = {"color": "#000000", "thickness": 2, "wayPoints": [[0.5, 0.5], [0.5, 2.5]], "headLength": 0.3}
    text = "The number in the circled cell is equal to the average of all numbers along the arrow."
    p, info = SP.translate(_sp4(underlays=[circle], arrows=[arrow]), text)
    assert info.get("average_arrow") and not any(c["type"] == "arrow" for c in p.constraints)
    assert next(r for r, _ in p.named_rules)["holds"] == "c * len(L) == sum(L)"
    text = "Arrow sums apply. At least one of the numbers along the path in each arrow must be repeated."
    p, _ = SP.translate(_sp4(underlays=[circle], arrows=[arrow]), text)
    assert any(c["type"] == "arrow" for c in p.constraints) and p.named_rules


def test_in_cell_arrows_cages_and_line_colours():
    """an arrow drawn inside one cell points along a ray (the closest 5, arrow X-sums); f-puzzles cages: factor cages,
    x + k cages (x forced by the cage sizes gives the totals), blank cages the text gives a meaning, equal sums of the
    cages without a total; line colors called by a neighboring word, a dull orange called brown, the one unnamed
    color, "all other lines", a gray cell that is no line color"""
    from pencilmark.sources import _fpuz_translate as FT
    from pencilmark.sources import _sp_translate as SP

    arrow = {"color": "#000000", "thickness": 2, "wayPoints": [[0.3, 0.5], [0.7, 0.5]], "headLength": 0.2}
    p, _ = SP.translate(_sp4(arrows=[arrow]), "Each arrow points to the closest 5.")
    rule = next(r for r, _ in p.named_rules)
    assert rule["cells"] == {"x": ["r1c1"], "N": ["r2c1", "r3c1", "r4c1"]}  # tail at the top, tip below: downwards
    with pytest.raises(Exception):
        SP.to_puzzle(_sp4(arrows=[arrow]), page_text="Normal sudoku rules apply.", fetch=False)
    base = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)]}
    cage = lambda cells, v=None: {"cells": cells, "value": v, "outlineC": "#000000"} if v else {"cells": cells}
    p, _ = FT.translate(dict(base, ruleset="Numbers in dashed regions MULTIPLY to the number in the top left corner of the region.",
                             cage=[cage(["R1C1", "R1C2"], "12")]))  # fmt: skip
    assert [r["holds"] for r, _ in p.named_rules] == ["product(K) == 12"] and any(g.kind == "cage" for g in p.groups)
    p, _ = FT.translate(dict(base, ruleset="Digits in cages sum to the number in the top left corner. X is the same for all cages.",
                             cage=[cage(["R1C1", "R1C2"], "x"), cage(["R3C3", "R3C4"], "x+4")]))  # fmt: skip
    assert sorted(g.total for g in p.groups if g.kind == "cage") == [3, 7]  # 1 + 2 = x, x + 4 <= 7 (4 + 3): x = 3
    p, _ = FT.translate(dict(base, ruleset="Digits in cages do not repeat.", cage=[cage(["R1C1", "R2C2"])]))
    assert [g.cells for g in p.groups if g.kind == "cage"] == [(0, 5)]
    p, _ = FT.translate(dict(base, ruleset="Digits in cages sum to 6 or 7.", cage=[cage(["R1C1", "R2C2"])]))
    assert p is None
    p, _ = FT.translate(dict(base, ruleset="Numbers in cages sum to the number in the top left corner of the cage. "
                             "The cages with no sum given, have the same sum as one another.",
                             cage=[cage(["R1C1", "R1C2"]), cage(["R3C3", "R3C4"]), cage(["R2C1", "R2C2"], "3")]))  # fmt: skip
    assert [r["holds"] for r, _ in p.named_rules] == ["count_distinct(sum(k) for k in K) == 1"]
    cmap = SP.rules_color_map("Numbers on purple lines are each a set of consecutive numbers. Numbers on brown lines "
                              "are palindromes. The gray cell with arrows pointing outward is a maximum.")  # fmt: skip
    assert "grey" not in cmap and SP.line_rule_from_text("#FF99D6", cmap) == "renban"
    assert SP.line_rule_from_text("#A87A47", cmap) == "palindrome"
    line = lambda col: {"lines": [["R1C1", "R1C2"]], "outlineC": col}
    reading = FT._text_line_reading({"line": [line("#FF4444"), line("#FFF888")]},
                                    "Red lines alternate in parity (odd/even). Gray lines are palindromes.")  # fmt: skip
    assert reading == {"#ff4444": "parity", "#fff888": "palindrome"}
    reading = FT._text_line_reading({"line": [line("#75ED68"), line("#C77EFA")]},
                                    "Numbers on green lines are at least 5 apart. Numbers on all other lines are each "
                                    "a set of non-repeating, consecutive numbers.")  # fmt: skip
    assert reading["#c77efa"] == "renban"
    cmap = SP.rules_color_map("Adjacent digits along a red line alternate in parity.")
    assert SP.line_rule_from_text("#F067F0", cmap, {"red", "pink"}) is None  # red's rule belongs to the red lines
    assert SP.join_branches([("p", [1, 2, 3]), ("p", [2, 4, 5]), ("p", [5, 6]), ("q", [3, 7])]) == [
        [1, 2, 3, 4, 5],
        [5, 6],
        [3, 7],
    ]
    dot = lambda cells, col: {"cells": cells, "baseC": col, "width": 0.3, "height": 0.3}
    p, _ = FT.translate(dict(base, ruleset="Cells joined by white dots are consecutive. All white dots are given. "
                             "Cells joined by green dots have a value ratio of 3:1. Not all green/orange dots are given.",
                             circle=[dot(["R1C1", "R1C2"], "#00FF00")]))  # fmt: skip
    assert ("ratio", 0, 1, 3) in p.relations and ("notdiff", 4, 5, 1) in p.relations
    assert FT._dot_meaning("green", "a pair can only appear once. green dots have a ratio of 3:1.") is None
    assert FT._dot_meaning("green", "all green dots are given. green dots have a ratio of 3:1.") is None
    assert FT._dot_meaning("grey", "digits separated by a gray dot are either consecutive or have a 1:2 ratio.") is None
    assert FT._dot_meaning(
        "red", "digits separated by a red dot are not consecutive. digits without a dot may or may not be consecutive."
    ) == ("notdiff", 1)
    halo = {"center": [0.5, 1], "width": 0.22, "height": 0.22, "rounded": True, "backgroundColor": "#fff5"}
    black = {"center": [0.5, 1], "width": 0.2, "height": 0.2, "rounded": True, "backgroundColor": "#000000"}
    p, _ = SP.translate(_sp4(overlays=[black, halo]), "Black dots: a 1:2 ratio.")
    assert [r[0] for r in p.relations if r[1:3] == (0, 1)] == ["ratio"]  # the translucent halo is no white dot
    assert SP.negative_markers("All possible dots fully inside odd numbered boxes are given.") == set()
    p, _ = SP.translate(
        _sp4(overlays=[black]), "KROPKI: cells separated by a black dot are a 1:2 ratio. ALL dots are given!"
    )
    assert not any(r[0] == "notdiff" for r in p.relations) and any(r[0] == "notratio" for r in p.relations)
    assert SP.LINE_CUSTOM["entropic2"][1] == "count_distinct((x + 1) div 2 for x in t) == 5"
    assert SP.QUAD_TEXT.search("every digit in a circle has to be assigned to one of the surrounding cells")
    sq = "A dot means that the digits in the two neighboring cells form a double digit square number in the reading direction. All dots are in the grid."
    p, _ = SP.translate(_sp4(overlays=[black]), sq)
    rules = [r for r, _ in p.named_rules]
    assert (
        rules[0]["cells"] == {"P": [["r1c1", "r1c2"]]} and "10 * a + b in {16, 25, 36, 49, 64, 81}" in rules[0]["holds"]
    )
    assert rules[1]["scope"] == {"pairs": "orthogonal", "except": [["r1c1", "r1c2"]]}
    found = SP.global_custom(
        9, SP.M.standard(9, 3, 3), "Cells that are 180° symmetric to each other cannot have the same digits."
    )
    assert found == ["rotational_neq"]
    t = "In all cases where two neighboring cells contain consecutive digits, a circle is placed between those cells."
    assert SP.negative_markers(t) == {"white"}
    assert SP.rule_flags("Cells that are orthogonally adjacent cannot contain consecutive digits.")["nonconsec"]
    with pytest.raises(Exception):
        SP.to_puzzle(_sp4(), page_text="All clues are equally true or false.", fetch=False)


def test_redefined_clues():
    """clues whose text changes their meaning: quadruple digits that must NOT appear, cage numbers listing digits in the
    cage (zone), dots that are consecutive or double (faded), diagonals with a count of distinct digits"""
    from pencilmark.sources import _sp_translate as SP

    quad = {"center": [2, 2], "text": "12", "width": 0.5, "height": 0.5, "rounded": True}
    p, _ = SP.translate(
        _sp4(overlays=[quad]), "Numbers in white circles must not appear in any of the four surrounding cells."
    )
    assert next(r for r, _ in p.named_rules)["holds"] == "all(x != 1 for x in Q) and all(x != 2 for x in Q)"
    cage = {"cells": [[0, 0], [0, 1]], "value": "12"}
    p, _ = SP.translate(_sp4(cages=[cage]), "Numbers in the top left of each cage must appear in those cages.")
    assert next(r for r, _ in p.named_rules)["cells"] == {"K": ["r1c1", "r1c2"]}
    assert not any(g.total for g in p.groups)
    dot = {"center": [0.5, 1], "width": 0.32, "rounded": True, "backgroundColor": "#FFFFFF"}
    text = (
        "If a circle is given between two cells, it either means that they differ by 1, or that they have a ratio of 2."
    )
    p, _ = SP.translate(_sp4(overlays=[dot]), text)
    assert not p.relations and next(r for r, _ in p.named_rules)["label"] == "Faded dot"
    num = lambda bg, t: {"center": [0.5, 1], "width": 0.33, "text": t, "rounded": True, "backgroundColor": bg}
    text = (
        "If a white circle is given, the numbers have a difference equal to it. If a black circle is given, the ratio."
    )
    p, _ = SP.translate(_sp4(overlays=[num("#000000", 3)]), text)
    assert p.relations == [("ratio", 0, 1, 3)]


def test_numbers_beside_edge_circles():
    """a number drawn just off an edge circle is that circle's number (one numbered dot, not a dot and a stray text);
    "the greater number" between two cells is max(a, b)"""
    from pencilmark.sources import _sp_translate as SP

    dot = {"center": [1, 0.5], "width": 0.5, "rounded": True, "backgroundColor": "#F"}
    num = {"center": [1.14, 0.5], "text": 3, "width": 0, "height": 0}
    text = "Number clues given between pairs of cells indicate the greater number in those two cells."
    p, _ = SP.translate(_sp4(overlays=[dot, num]), text)
    assert not p.relations and next(r for r, _ in p.named_rules)["holds"] == "max(a, b) == 3"
    p, _ = SP.translate(_sp4(overlays=[dot, num]), "Numbers between two cells give the difference of the values.")
    assert p.relations == [("diff", 0, 4, 3)]


def test_more_redefined_clues():
    """palindromes with one mismatched pair or consecutive partners, zones listing two of three digits, cages that are
    all even / all odd / half and half (areas where digits may repeat)"""
    from pencilmark.sources import _sp_translate as SP

    line = {"color": "#AAAAAA", "thickness": 9.6, "wayPoints": [[0.5, 0.5], [0.5, 3.5]]}
    p, _ = SP.translate(
        _sp4(lines=[line]),
        "The numbers along each gray line form a palindrome, except for a single pair of non-matching numbers.",
    )
    assert next(r for r, _ in p.named_rules)["holds"] == "count(i for i in {1..2} if t[i] != t[5 - i]) == 1"
    cage = {"cells": [[0, 0], [0, 1]], "value": "123"}
    p, _ = SP.translate(
        _sp4(cages=[cage]), "Each cage must contain two of the three numbers given in the upper-left corner."
    )
    assert "== 2" in next(r for r, _ in p.named_rules)["holds"]
    big = {"cells": [[0, c] for c in range(4)] + [[1, 0]]}
    text = "Cages must contain either all even numbers, all odd numbers, or exactly half even and half odd numbers."
    p, _ = SP.translate(_sp4(cages=[big]), text)
    assert not [g for g in p.groups if g.kind == "cage"] and len(p.named_rules) == 1


def test_given_pencilmarks():
    """given pencil marks as the only candidates of their cells (the text says so); the same digits drawn as a one-cell
    cage's number are a label, not a cage sum"""
    from pencilmark.sources import _sp_translate as SP

    sp = _sp4(cages=[{"cells": [[0, 0]], "value": "12"}])
    sp["puzzle"]["cells"][0][0] = {"centremarks": [1, 2]}
    p, _ = SP.translate(sp, "The given pencilmarks represent the only numbers that can appear in those cells.")
    assert p.domains[0] == 0b0011 and not [g for g in p.groups if g.kind == "cage"]


def test_sudokupad_author_slug_links():
    """SudokuPad links of the form sudokupad.app/<author>/<slug> are fetched through the API with the slash kept"""
    from pencilmark.sources import sudokupad

    asked = []

    class FakeHttp:
        def get_text(self, url):
            asked.append(url)
            raise sudokupad.FetchError("offline")

    with pytest.raises(sudokupad.FetchError):
        sudokupad.fetch("https://sudokupad.app/clover/dec-4-2023-equal-sudoku", http=FakeHttp())
    assert asked == [sudokupad.API + "clover/dec-4-2023-equal-sudoku"]


def test_shape_clues_are_written_as_cell_rules():
    """parity / digit-set shapes are written as cell rules (with the shapes' shared look), not as given candidates; the
    same for f-puzzles odd / even cells"""
    import pencilmark as pm
    from pencilmark.sources import sudokupad

    sq = lambda r, c: {"center": [r + 0.5, c + 0.5], "width": 0.8, "height": 0.8, "backgroundColor": "#0003"}
    sp = _sp4(underlays=[sq(0, 0), sq(1, 1)])
    sp["meta"]["rules"] = "Cells with a square contain an even number."
    doc = pm.write.document(pm.read._document(sudokupad.to_puzzle(sp, fetch=False)), describe=True)
    cell = [r for r in doc["rules"] if r["type"] == "cell"]
    assert "candidates" not in doc and cell[0]["kind"] == "even" and cell[0]["cells"] == ["r1c1", "r2c2"]
    assert cell[0]["style"]["shape"] == "square"
    fp = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)], "odd": [{"cell": "R1C1"}]}
    doc = pm.write.document(pm.read._document(FP.to_puzzle(fp, fetch=False)), describe=True)
    assert "candidates" not in doc and any(r.get("kind") == "odd" for r in doc["rules"])


def test_fpuzzles_outside_text_and_numbered_rooms():
    """numbers written as f-puzzles text outside the grid are read like SudokuPad outside clues (the payload's wording,
    else the page's) and refused when nothing reads them; a numbered room is the custom rule ray[ray[1]] == X"""
    from pencilmark.sources import _fpuz_translate as FT
    from pencilmark.sources import _sp_translate as SP

    grid = [[{} for _ in range(4)] for _ in range(4)]
    fp = {"size": 4, "grid": grid, "ruleset": "Clues give the median of the first three cells.",
          "text": [{"cells": ["R0C2"], "value": "2"}]}  # fmt: skip
    p, _ = FT.translate(fp)
    assert [r["holds"] for r, _ in p.named_rules] == ["median(take(3, ray)) == 2"]
    p, why = FT.translate(dict(fp, ruleset="Normal sudoku rules apply."))
    assert p is None and "outside clue text" in why
    clue = {"center": [0.5, -0.5], "text": 3, "width": 0, "height": 0}
    p, _ = SP.translate(_sp4(overlays=[clue]), "Numbered rooms: a clue X says the digit X is in the N-th cell.")
    assert next(r for r, _ in p.named_rules)["holds"] == "ray[ray[1]] == 3"


def test_fpuzzles_circles_and_squares_as_shape_clues():
    """f-puzzles one-cell circles and squares (rectangles) are read by the shape-clue reader: "1s, 2s, and 3s are marked
    with circles" is a digit set for the circled cells; squares are no longer dropped as decoration"""
    from pencilmark.sources import _fpuz_translate as FT

    one = lambda c: {"cells": [c], "baseC": "#FFFFFF", "outlineC": "#000000", "width": 0.85, "height": 0.85}
    fp = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)],
          "ruleset": "1s and 2s are marked with circles. 3s and 4s are marked with squares.",
          "circle": [one("R1C1")], "rectangle": [one("R2C2")]}  # fmt: skip
    p, _ = FT.translate(fp)
    assert p.domains[0] == 0b0011 and p.domains[5] == 0b1100


def test_fpuzzles_generic_lines_as_custom_rules():
    """f-puzzles generic lines take the line rules the SudokuPad reader knows from their descriptions, also when drawn
    in several shades: increasing-or-decreasing, same parity, center sum, three distinct digits on a diagonal"""
    from pencilmark.sources import _fpuz_translate as FT

    line = lambda cells, col="#CCCCCC": {"lines": [cells], "outlineC": col, "width": 0.4}
    base = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)]}
    p, _ = FT.translate(dict(base, ruleset="Along each line, digits either strictly increase or strictly decrease.",
                             line=[line(["R1C1", "R1C2", "R1C3"])]))  # fmt: skip
    assert next(r for r, _ in p.named_rules)["label"] == "Increasing or decreasing line"
    p, _ = FT.translate(dict(base, ruleset="Digits on the same line have the same parity.",
                             line=[line(["R1C1", "R2C1"]), line(["R3C3", "R4C3"], "#999999")]))  # fmt: skip
    assert [r["label"] for r, _ in p.named_rules] == ["Same-parity line", "Same-parity line"]
    p, _ = FT.translate(dict(base, ruleset="On each line, the digit in the center position is the sum of the other two digits.",
                             line=[line(["R1C1", "R1C2", "R1C3"])]))  # fmt: skip
    assert next(r for r, _ in p.named_rules)["holds"] == "2 * t[2] == sum(t)"
    p, _ = FT.translate(dict(base, ruleset="Each marked diagonal contains only three distinct digits.",
                             line=[line(["R1C1", "R2C2", "R3C3", "R4C4"])]))  # fmt: skip
    assert next(r for r, _ in p.named_rules)["holds"] == "count_distinct(t) == 3"


def test_lmd_wording_fixes():
    """LMD top-500 misreads: "[no negative constraints]" adds none; "If not, they don't" makes the marker negative;
    "at least 5 apart" is a whisper; equal-parity lines are same-parity lines; thermos of a single parity; f-puzzles
    colored cells "greater than 5" """
    from pencilmark.sources import _fpuz_translate as FT
    from pencilmark.sources import _sp_translate as SP

    assert SP.negative_markers("Standard kropki and XV rules apply [no negative constraints].") == set()
    assert SP.negative_markers("If two digits have an X between them, they sum to 10. If not, they don't.") == {"x"}
    # "all possible dots are given" in a black-dot-only text: no white negative
    assert SP.negative_markers("cells separated by a black dot have a 1:2 ratio. all possible dots are given.") == {
        "black"
    }
    assert SP.diff_rule("adjacent digits on a green line are at least 5 apart") == "whisper"
    fp = {"size": 4, "grid": [[{"c": "#FFA0A0"} if (r, c) == (0, 0) else {} for c in range(4)] for r in range(4)],
          "ruleset": "Red cells are greater than 2."}  # fmt: skip
    p, _ = FT.translate(fp)
    assert p.domains[0] == 0b1100
    assert {"maze path", "digit subset", "exclusive", "cage sums to find"} <= {k for k, _ in SP.UNMODELLED_RULES}
    assert "rule 'maze path'" in SP.unmodelled_rules("Both rats must find a path through the maze to the cheese.")
    fp2 = {"size": 4, "grid": [[{"c": "#FFE060"} if (r, c) in ((0, 0), (3, 3)) else {} for c in range(4)] for r in range(4)],
           "ruleset": "The cells shaded orange are the same number as one another."}  # fmt: skip
    p, _ = FT.translate(fp2)
    assert next(r for r, _ in p.named_rules)["holds"] == "count_distinct(S) == 1"
    cmap = SP.rules_color_map("Green lines are German whispers. Blue lines have no effect on the puzzle.")
    assert cmap == {"green": "whisper", "blue": "ignore"}
    assert SP.described_line_rules("Digits on lines are consecutive and non-repeating but in any order.") == {"renban"}


def test_fpuzzles_line_totals_whisper_thresholds_and_segments():
    """f-puzzles generic lines: whispers with their own threshold, fixed line totals, renban segments drawn in pieces
    joined into one line (unless the separate reading is the one with the setter's solution); a difference with an
    upper bound is no whisper; "chess knight jump" is anti-knight"""
    from pencilmark.sources import _fpuz_translate as FT
    from pencilmark.sources import _sp_translate as SP

    line = lambda cells, col="#CCCCCC": {"lines": [cells], "outlineC": col, "width": 0.4}
    base = {"size": 4, "grid": [[{} for _ in range(4)] for _ in range(4)]}
    p, _ = FT.translate(dict(base, ruleset="Whisper: adjacent digits along the gray line must differ by at least 2.",
                             line=[line(["R1C1", "R1C2"])]))  # fmt: skip
    assert [c.get("k") for c in p.constraints if c.get("kind") == "whisper"] == [2]
    p, info = FT.translate(dict(base, ruleset="Numbers on blue lines sum to 7.",
                                line=[line(["R1C1", "R1C2"], "#87A1FF"), line(["R1C2", "R2C2"], "#87A1FF")]))  # fmt: skip
    assert info.get("_joined") and [r["holds"] for r, _ in p.named_rules] == ["sum(t) == 7"]
    assert next(r for r, _ in p.named_rules)["cells"]["t"] == [["r1c1", "r1c2", "r2c2"]]
    assert SP.diff_rule("digits along each line have a difference of at least 1, and at most 2") is None
    assert SP.rule_flags("Cells separated by a chess knight jump cannot contain the same digit.")["antiknight"]
    assert (
        SP.diff_rule("digits along a pink line must differ in value from their neighbors on the line by at least 6")
        == "whisper6"
    )
    assert SP.QUAD_TEXT.search("digits in circles must appear in a cell touching the circle")
    cages = [{"cells": [[0, 0], [0, 1]], "value": 5}, {"cells": [[1, 0], [1, 1]]}]
    p, _ = SP.translate(_sp4(cages=cages), "Every cage has the same sum.")
    assert [g.total for g in p.groups if g.kind == "cage"] == [5, 5]


def test_more_global_text_rules():
    """whole-grid rules from the text: 180-degree pair sums, 159 indexing, caged digits not next to a consecutive
    digit, no repeats around a digit; Dutch flat mates across a ';'"""
    from pencilmark.sources import _sp_translate as SP

    std = lambda: SP.M.standard(9, 3, 3)
    assert SP.global_custom(9, std(), "Cells 180 degree rotation apart sum to 10.") == ["rotational_sum"]
    assert SP.global_custom(9, std(), "159: digits in columns 1, 5 and 9 index the columns of 1, 5 and 9.") == ["159"]
    assert SP.global_custom(9, std(), "159: digits in red cells index columns.") == []  # other indexer cells: not this
    assert SP.global_custom(9, std(), "Digits may not repeat in any 3x3 area centered on a 9.") == ["no_repeat_around"]
    p = std()
    p.groups.append(SP.M.Group("k", (0, 1), "cage", False, None))
    SP.global_custom(9, p, "Digits inside a cage can not be orthogonally adjacent with a consecutive digit.")
    assert ("nonconsec", 0, 1) in p.relations and ("nonconsec", 0, 9) in p.relations
    p = std()
    from collections import Counter

    u = Counter()
    SP.global_rules(
        9, p, "Dutch flat mates: all 5's must have EITHER; a '1' directly above it AND/OR a '9' directly below it.", u
    )
    assert u["dutch_flats"] == 1
    # anti-knight from a marked cell only, not every cell; from markers no reading knows: refused
    assert not SP.rule_flags("The digit in the yellow cell may not repeat in any cell that is a knight's move away")[
        "antiknight"
    ]
    p = std()
    assert SP.text_cell_rules(p, 9, "The digit in the yellow cell may not repeat in any cell a knight's move away.",
                              {"yellow": [40]}, Counter()) == []  # fmt: skip
    assert ("neq", 21, 40) in p.relations and len(p.relations) == 8
    assert SP.text_cell_rules(std(), 9, "No cell a chess knight's move away from a Black Rider can contain the same digit.",
                              {}, Counter()) == ["anti-knight from marked cells"]  # fmt: skip


def test_oil_and_water_and_unmodelled_refusals():
    """oil and water cages: each cage row one parity, even rows above odd rows (custom rule per cage); mechanics that
    place or identify unknown objects are refused (pick-up sticks, a magic square somewhere, every domino once)"""
    from pencilmark.sources import _sp_translate as SP

    cage = {"cells": [[0, 0], [0, 1], [1, 0], [1, 1]]}
    text = 'Each cage is either full of "oil" (even digits), full of "water" (odd digits), or a mix of both.'
    p, _ = SP.translate(_sp4(cages=[cage]), text)
    rule = next(r for r, _ in p.named_rules)
    assert rule["label"] == "Oil and water" and "R[i][1] mod 2 <= R[i + 1][1] mod 2" in rule["holds"]
    for words, kind in (("A stick always has a lower total than any stick which lies on top of it.", "pick-up sticks"),
                        ("There is a 3x3 magic square somewhere in the grid.", "magic square"),
                        ("Every possible domino appears exactly once in the cages.", "unique dominoes")):  # fmt: skip
        assert f"rule '{kind}'" in SP.unmodelled_rules(words.lower())


def test_equality_cages():
    """equality cages (as many low as high and as many even as odd digits per cage) are custom rules per cage, with the
    low / high split of the digit range (6: 1-3 / 4-6; 9: 1-4 / 6-9, never 5); the unmodelled refusal is lifted"""
    from pencilmark.sources import _sp_translate as SP

    text = ("Equality cages: Cages must have an equal number of low (1,2) and high (3,4) digits AND an equal number of "
            "even (2,4) and odd (1,3) digits.")  # fmt: skip
    p, info = SP.translate(_sp4(cages=[{"cells": [[0, 0], [0, 1]]}]), text)
    assert p is not None and info.get("equality_cage") == 1
    assert next(r for r, _ in p.named_rules)["holds"].startswith(
        "count(x for x in K if x <= 2) == count(x for x in K if x >= 3)"
    )


def test_shifter_lines_and_dots():
    """shifter lines: within a box neighbors share parity and polarity, across a box border exactly one changes, never
    the middle digit; shifter dots: exactly one shared; a dot of another color that no reading takes is refused; the
    rule needs its definition ("Shifter lines: ..."), not a mention in a list of series"""
    from pencilmark.sources import _sp_translate as SP

    line = {"color": "#F5D000", "thickness": 9.6, "wayPoints": [[0.5, 0.5], [0.5, 1.5], [0.5, 2.5]]}
    text = "Shifter lines: adjacent digits within the same box share parity and polarity."
    p, _ = SP.translate(_sp4(lines=[line]), text)
    holds = [r["holds"] for r, _ in p.named_rules]
    assert holds[0].startswith("a mod 2 == b mod 2") and holds[1].startswith("num(a mod 2 == b mod 2) +")
    dot = {"center": [1, 0.5], "width": 0.3, "rounded": True, "backgroundColor": "#FFD700"}
    p, _ = SP.translate(_sp4(overlays=[dot]), "Shifter dots: digits on either side share parity or polarity, not both.")
    assert next(r for r, _ in p.named_rules)["label"] == "Shifter dot"
    p, why = SP.translate(_sp4(overlays=[dot]), "Normal sudoku rules apply.")
    assert p is None and "yellow dot" in why
    assert "shifter" not in SP.rule_flags("All my series: Equality Cages, Shifter Lines, Shifter Dots.")


def test_fpuzzles_circle_meanings():
    """f-puzzles circles with a meaning in the text: a pink circle under a quadruple makes it an anti-quadruple;
    decorative circles are dropped; counting circles worded "how many circles" """
    from pencilmark.sources import _fpuz_translate as FT

    grid = [[{} for _ in range(4)] for _ in range(4)]
    cells = ["R1C1", "R1C2", "R2C1", "R2C2"]
    fp = {"size": 4, "grid": grid, "quadruple": [{"cells": cells, "values": ["1"]}],
          "circle": [{"cells": cells, "baseC": "#FF000D"}],
          "ruleset": "Quadruples: digits in the white circle appear in the four surrounding cells. Anti-Quadruples: "
                     "digits in the small PINK circle cannot appear in one of the four surrounding cells."}  # fmt: skip
    p, _ = FT.translate(fp)
    assert next(r for r, _ in p.named_rules)["label"] == "Anti-quadruple"
    p, _ = FT.translate(dict(fp, quadruple=[], ruleset="The circles have no effect on the puzzle."))
    assert p is not None
    assert re.search(FT.COUNTING_CIRCLES, "for a digit in a circle, it indicates exactly how many circles contain it")


def test_rule_for_every_line():
    """ "all lines are region sum lines" gives every line that rule; a line whose color also names another rule has two
    rules and is refused (CTC zkz5Qw2BWx4: orange lines are also Dutch whispers)"""
    from pencilmark.sources import _sp_translate as SP

    assert SP.every_line_rule("Numbers can repeat on a line. All lines are region sum lines.") == "region_sum"
    line = lambda col: {"color": col, "thickness": 9.6, "wayPoints": [[0.5, 0.5], [0.5, 2.5]]}
    p, _ = SP.translate(_sp4(lines=[line("#34BBE6")]), "All lines are region sum lines.")
    assert any(c["type"] == "equal_sum" for c in p.constraints)
    p, why = SP.translate(
        _sp4(lines=[line("#F5A623")]), "All lines are region sum lines. Orange lines are Dutch whisper lines."
    )
    assert p is None and "two rules" in why


def test_between_line_through_several_circles():
    """a between line passing through more than two circles is one between line per stretch from circle to circle
    (CTC k90bwDVb3bw: 28 stretches; read from its end circles only it had several solutions)"""
    from pencilmark.sources import _sp_translate as SP

    line = [{"color": "#CFCFCF", "thickness": 9.6, "wayPoints": [[0.5, 0.5], [0.5, 3.5], [1.5, 3.5], [1.5, 0.5]]}]
    circ = lambda r, c: {"center": [r, c], "width": 0.8, "height": 0.8, "rounded": True, "borderColor": "#000"}
    sp = _sp4(lines=line, overlays=[circ(0.5, 0.5), circ(0.5, 3.5), circ(1.5, 0.5)])
    p, _ = SP.translate(sp, "Digits on a line must be strictly between the digits in the connected circles.")
    assert [c["cells"] for c in p.constraints if c.get("kind") == "between"] == [[0, 1, 2, 3], [3, 7, 6, 5, 4]]


def test_whole_grid_region_means_no_boxes():
    """a SudokuPad region over the whole grid draws no boxes: rows and columns only (Spiraling Circles, 000O94, read
    it as one 81-cell region and had no solution); describe reads the rules without searching for the solution"""
    from pencilmark.sources import _sp_translate as SP

    sp = _sp4()
    sp["puzzle"]["regions"] = [[[r, c] for r in range(4) for c in range(4)]]
    p, _ = SP.translate(sp, "Place the digits 1-4 once each into every row and column.")
    assert sorted({g.kind for g in p.groups}) == ["col", "row"]


def test_off_centre_cell_text_is_refused():
    """small text in a cell's corner is a clue no reading handles (run sums, 000V90, read as nothing at all): refused,
    not dropped; text centered in a cell, and a digit by a cell corner when the rules speak of quadruples, are not"""
    from pencilmark.sources import _sp_translate as SP

    corner = [{"center": [1.83, 1.83], "width": 0, "height": 0.46, "rounded": True, "text": "44"}]
    p, why = SP.translate(_sp4(overlays=corner), "Normal sudoku rules apply.")
    assert p is None and "cell text '44'" in why
    centred = [{"center": [1.5, 1.5], "width": 0, "height": 0.46, "text": "4"}]
    p, _ = SP.translate(_sp4(overlays=centred), "Normal sudoku rules apply.")
    assert p is not None


def test_reading_that_breaks_the_embedded_solution_is_refused():
    """a reading the setter's embedded solution breaks is refused by default (one-off rules worded like standard
    ones); check_solution=False skips the check"""
    import pytest

    from pencilmark import sources

    sol = "123456789456789123789123456214365897365897214897214365531642978642978531978531642"
    pj = {
        "numbers": "." * 81,
        "solution": sol,
        "rules": [{"type": "kropki", "color": "white", "cells": ["r1c1", "r1c3"]}],
    }
    assert sources.contradicts_solution(pj)  # 1 and 3 are not consecutive
    assert not sources.contradicts_solution(
        dict(pj, rules=[{"type": "kropki", "color": "white", "cells": ["r1c1", "r1c2"]}])
    )
    assert not sources.contradicts_solution({"numbers": "." * 81})  # no solution: nothing to check
    assert sources.contradicts_solution(dict(pj, solution="0" + sol[1:]))  # the setter's digits include 0
    with pytest.raises(sources.ReadingMismatch):
        sources.load(pj)
    assert sources.load(pj, check_solution=False)["solution"] == sol


def test_fog_payloads_keep_their_fog():
    """SudokuPad FOGLIGHT cages / triggers and f-puzzles foglight are read as the fog rule, not refused"""
    from pencilmark import model as M
    from pencilmark.sources import _sp_translate as ST

    p = M.Puzzle(D=9, coords=M._grid_coords(9))
    idx = lambda rc: rc[0] * 9 + rc[1]
    inside = lambda rc: 0 <= rc[0] < 9 and 0 <= rc[1] < 9
    P = {
        "cages": [{"cells": [[0, 0], [0, 1]], "value": "FOGLIGHT"}, {"value": "foglight: r5c5"}],
        "triggereffect": [
            {"trigger": {"type": "cellvalue", "cell": "r1c1r1c2"}, "effect": {"type": "foglight", "cells": "r9c9"}}
        ],
    }
    fog = ST.fog_of(P, p, idx, inside)
    assert fog == {"lit": ["r1c1", "r1c2", "r5c5"], "triggers": [{"when": ["r1c1", "r1c2"], "light": ["r9c9"]}]}
    assert ST.fog_of({"cages": [{"cells": [[0, 0]], "value": 12}]}, p, idx, inside) is None


def test_fpuzzles_fog_cages():
    """f-puzzles fog written as generic cages, as SudokuPad imports them: a one-cell FOW cage lights its 3x3 (drawn
    invisible, which the cage normalizer drops), a FOGLIGHT cage lights its cells; neither is read as a clue. A rule
    described without its name ("indicate the column in which") is refused, not dropped."""
    from pencilmark.sources import _fpuz_translate as FT

    grid = [[{} for _ in range(9)] for _ in range(9)]
    fp = {
        "size": 9,
        "grid": grid,
        "ruleset": "Normal sudoku rules apply. The grid is covered with fog.",
        "cage": [
            {"value": "FOW", "cells": ["R8C8"], "outlineC": "#00000000"},
            {"value": "foglight", "cells": ["R1C1", "R1C2"], "outlineC": "#000000"},
        ],
    }
    p, info = FT.translate(fp)
    assert p is not None, info
    assert (
        p.fog["lit"][:2] == ["r1c1", "r1c2"]
        and {"r7c7", "r8c8", "r9c9"} <= set(p.fog["lit"])
        and len(p.fog["lit"]) == 11
    )
    fp["ruleset"] += " Digits in column 1 indicate the column in which the digit 1 appears in that row."
    p, info = FT.translate(fp)
    assert p is None and "indexing" in info


def test_renban_cells_in_path_order():
    """f-puzzles renban segments joined into one line keep a path order (each cell touches the next); a set no path
    covers is None (the reader then keeps it as a consecutive set, never an invalid line)"""
    from pencilmark.sources._fpuz_translate import _path_through

    n = 9
    cell = lambda r, c: (r - 1) * n + c - 1
    snake = [cell(6, 4), cell(7, 3), cell(8, 3), cell(9, 3), cell(9, 2), cell(8, 2), cell(8, 1), cell(7, 1), cell(7, 2)]
    path = _path_through(set(snake), n)
    assert sorted(path) == sorted(snake)
    assert all(abs(a // n - b // n) <= 1 and abs(a % n - b % n) <= 1 for a, b in zip(path, path[1:]))
    star = {cell(5, 5), cell(4, 5), cell(6, 5), cell(5, 4), cell(5, 6), cell(3, 5), cell(7, 5), cell(5, 3), cell(5, 7)}
    assert _path_through(star, n) is None  # a plus with four long arms: no single path


def test_sudokupad_metadata_cages_and_encoded_payloads():
    """found by the style survey (2026-11-07): a metadata cage with `cells: [null]` (000VVN) crashed the translator and
    the style capture; an API response may come percent-encoded (000VS2: %2B / %2F / %3D)"""
    import urllib.parse

    from pencilmark.sources import _sp_style, sudokupad
    from pencilmark.sources import _sp_translate as SP

    meta_cage = {"cells": [None], "value": "title: A puzzle"}
    killer = {"cells": [[0, 0], [0, 1]], "value": "3"}
    sp = sudokupad.decode(_sp4(cages=[meta_cage, killer]))
    p, _ = SP.translate(sp, "Normal sudoku rules apply. Digits in a cage sum to the small clue.")
    assert p is not None and _sp_style.elements(sp) is not None

    class Fake:
        def __init__(self, text):
            self.text = text

        def get_text(self, url):
            return self.text

    fpz = {"size": 4, "title": "t", "grid": [[{} for _ in range(4)] for _ in range(4)]}
    raw = "fpuzzles" + sudokupad._lz().compressToBase64(json.dumps(fpz))
    quoted = urllib.parse.quote(raw, safe="")
    assert "%" in quoted
    assert sudokupad.fetch("abcdef", http=Fake(quoted)) == sudokupad.fetch("abcdef", http=Fake(raw))


def test_sudokupad_style_halos_and_leftover_artwork():
    """two looks on a rule's cells, wide and narrow, are a line and its outline; drawn elements on cells no rule
    touches become decorations (a line, a rotated square as a polygon, a word); nothing on a rule's cells is copied"""
    from pencilmark.sources import _sp_style as SS

    path = [[0.5, 0.5], [0.5, 1.5], [0.5, 2.5]]
    sp = {"puzzle": {"cells": [[{}] * 4] * 4, "cellSize": 64,
                     "lines": [{"wayPoints": path, "color": "#ffffff", "thickness": 20},
                               {"wayPoints": path, "color": "#cc3333", "thickness": 8},
                               {"wayPoints": [[3.5, 0.5], [3.5, 3.5]], "color": "#2266cc", "thickness": 4}],
                     "underlays": [{"center": [2.5, 2.5], "width": 0.6, "height": 0.6, "angle": 30, "backgroundColor": "#88cc88"},
                                   {"center": [0.5, 0.5], "width": 0.8, "height": 0.8, "rounded": True, "backgroundColor": "#dddddd"}],
                     "overlays": [{"center": [1.5, 3.5], "text": "Bonus", "fontSize": 16}]}}  # fmt: skip
    doc = {"rules": [{"type": "line", "kind": "renban", "cells": ["r1c1", "r1c2", "r1c3"]}]}
    out = SS.apply(doc, SS.elements(sp))
    st = out["rules"][0]["style"]
    wide, thin = round(20 / 64, 3), round(8 / 64, 3)  # widths in cell units, as stored
    assert (
        st["color"] == "#cc3333" and st["outline"] == "#ffffff" and st["outline_width"] == round((wide - thin) / 2, 3)
    )
    kinds = sorted(d["kind"] for d in out["decorations"])
    assert kinds == ["line", "polygon", "text"], kinds  # the bulb-like circle on r1c1 belongs to the rule: not copied
    poly = next(d for d in out["decorations"] if d["kind"] == "polygon")
    assert len(poly["points"]) == 4 and poly["style"]["fill"] == "#88cc88"


def test_sudokupad_screen_fixes():
    """reader fixes from the CtC screen (2026-11-07): bare all-digit hex colors are strings (JSON numbers have no
    leading zero), a [null] region is no region, a 0 digit is refused (the format's digits start at 1)"""
    assert json.loads(SP.compact_to_json("{c:020202,d:004dd1,w:.5,x:-.25,n:10}")) == {
        "c": "020202",
        "d": "004dd1",
        "w": 0.5,
        "x": -0.25,
        "n": 10,
    }
    sp = _sp4()
    sp["puzzle"]["regions"].append([None])
    doc = pencilmark.read._document(SP.to_puzzle(sp, page_text="Normal sudoku rules apply.", fetch=False))
    assert sum(1 for r in doc["rules"] if r["type"] in ("box", "box_grid")) >= 1
    sp = _sp4()
    sp["puzzle"]["cells"][0][0] = {"value": 0, "given": True}
    with pytest.raises(pencilmark.NotSupportedError, match="digits 1..4"):
        SP.to_puzzle(sp, page_text="Normal sudoku rules apply.", fetch=False)


def test_fpuzzles_style_capture():
    """f-puzzles colors its generic elements (M4): a line's outlineC and width, a cage's outline (a transparent one is
    no style), a circle's fill / outline and size become the drawn elements apply() turns into rule styles"""
    from pencilmark.sources._fpuz_style import elements

    fp = {"line": [{"lines": [["R1C1", "R1C2", "R2C2"]], "outlineC": "#67F067", "width": 0.3}],
          "cage": [{"cells": ["R5C5", "R5C6"], "outlineC": "#ffffff00"}, {"cells": ["R6C6"], "outlineC": "#FF0000"}],
          "circle": [{"cells": ["R9C9"], "baseC": "#FFFFFF", "outlineC": "#000000", "width": 0.5, "height": 0.5}]}  # fmt: skip
    got = {tuple(e["cells"]): e["style"] for e in elements(fp)}
    assert got[("r1c1", "r1c2", "r2c2")] == {"color": "#67f067", "width": 0.3}
    assert ("r5c5", "r5c6") not in got and got[("r6c6",)] == {"color": "#ff0000"}
    assert got[("r9c9",)] == {"fill": "#ffffff", "color": "#000000", "shape": "circle", "size": 0.5}


def test_coloured_dots_read_from_their_clause():
    from pencilmark.sources._sp_translate import dot_color_rules

    one = ("Digits joined by a black dot are in 1:2 ratio, digits joined by a white dot are consecutive, and digits "
           "joined by a yellow dot are both low {123}, medium {456}, or high {789}.")  # fmt: skip
    assert dot_color_rules(one) == {"yellow": ("(a - 1) div 3 == (b - 1) div 3", "Same-third dot", False)}
    assert (
        dot_color_rules("Digits joined by a purple dot are in a 1:3 ratio.")["purple"][0] == "a == 3 * b or b == 3 * a"
    )
    assert dot_color_rules("Digits in cells joined by a yellow dot cannot sum to 7.")["yellow"][0] == "a + b != 7"
    tien = dot_color_rules("Digits separated by an orange Tien dot must sum to 10, AND must also differ by at least 4.")
    assert tien["orange"][0] == "(abs(a - b) >= 4) and (a + b == 10)"
    neg = dot_color_rules("Yellow dots separate digits that differ by more than 2. All possible yellow dots are given.")
    assert neg == {"yellow": ("abs(a - b) >= 3", "Difference dot", True)}
    # grey kropki: consecutive or 1:2 (or both); "not both": exactly one; other alternatives are left unread
    either = dot_color_rules("Digits connected by a gray dot are either consecutive or in a 1:2 ratio (or both).")
    assert either["grey"][0] == "abs(a - b) == 1 or a == 2 * b or b == 2 * a"
    xor = dot_color_rules("Grey dots: digits are EITHER one apart OR in the ratio of 1:2 but NOT both.")
    assert xor["grey"][0] == "(abs(a - b) == 1) != (a == 2 * b or b == 2 * a)"
    assert dot_color_rules("The grey dot is either a white dot or a black dot, to be determined by the solver.") == {}


def test_knight_move_wording():
    from pencilmark.sources._sp_translate import rule_flags

    assert rule_flags("Cells one chess knight move apart may not contain the same digit.")["antiknight"]
    both = rule_flags(
        "Cells that are either a Knight move (in chess), or a King move apart cannot contain the same digit."
    )
    assert both["antiknight"] and both["antiking"]
    for other in (
        "The knight moves like knight in chess.",  # a piece, not a rule
        "Cells one chess knight's move apart may not contain digits in 1:2 ratio.",  # another relation
        "Digits in cells a knight move away from any caged cell must differ from it by more than 1.",
    ):  # local
        assert not rule_flags(other)["antiknight"], other
