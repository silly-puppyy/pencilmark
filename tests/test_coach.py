"""sudoku.coach reader, offline (no network): synthetic SCv7 payloads built here (zlib + base32), never site puzzles."""

import json
import zlib

import pytest

import pencilmark
from pencilmark import sources
from pencilmark.errors import FormatError, NotSupportedError, ReadingMismatch
from pencilmark.sources import coach

# a 4x4 solution with 2x2 boxes
SOLUTION = "1234341221434321"


def payload(d, version=7):
    """JSON -> 'SCv7_32_<base32>' as the app writes it (5 bits per character, most significant first)"""
    raw = zlib.compress(json.dumps(d).encode())
    bits = "".join(f"{b:08b}" for b in raw)
    bits += "0" * (-len(bits) % 5)
    body = "".join(coach.ALPHABET[int(bits[i : i + 5], 2)] for i in range(0, len(bits), 5))
    return f"SCv{version}_32_{body}"


def puzzle(*constraints, givens="0" * 16, **extra):
    """a 4x4 coach puzzle JSON with these givenConstraints"""
    cons = [dict({"id": 10 + k, "settings": {}}, **c) for k, c in enumerate(constraints)]
    return dict({"gridSize": 4, "givenDigits": givens, "givenConstraints": cons}, **extra)


def seg(cells, **parameters):
    return {"cells": cells, "parameters": parameters}


def record(d, solution=SOLUTION, **extra):
    return dict(
        {"sudoku_id": "T3st", "sudoku": payload(d), "solution": solution, "name": "Test", "author": "Me"}, **extra
    )


def rules_of(doc, t):
    return [r for r in doc["rules"] if r["type"] == t]


def test_decode_round_trip():
    d = puzzle({"type": "antiKing", "segments": []}, givens="1000000000000004")
    got = coach.decode(payload(d))
    assert got["format"] == "SCv7" and got["puzzle"] == d


def test_older_versions_and_other_text_are_refused():
    with pytest.raises(NotSupportedError, match="SCv6"):
        coach.decode(payload({"gridSize": 4}, version=6))
    with pytest.raises(FormatError):
        coach.decode("not a payload")


def test_document_envelope_meta_and_houses():
    doc = coach.to_document(record(puzzle(givens="1000000000000001"), description="Normal sudoku rules."))
    assert doc["format"] == "pencilmark-puzzle" and doc["format_version"] == 1
    assert doc["board"] == {"rows": 4, "cols": 4} and doc["digits"] == 4
    assert doc["givens"][0] == 1 and doc["givens"][15] == 1 and doc["solution"][:4] == [1, 2, 3, 4]
    assert doc["rules"] == [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}]
    assert doc["meta"] == {
        "title": "Test",
        "author": "Me",
        "source": "sudoku.coach",
        "id": "T3st",
        "url": "https://sudoku.coach/en/s/T3st",
        "rules_text": "Normal sudoku rules.",
    }


def test_regions_empty_is_a_latin_square_and_irregular_is_a_jigsaw():
    assert coach.to_document(puzzle(regions=[]))["rules"] == [{"type": "grid"}]
    jig = [1, 1, 1, 2, 3, 1, 2, 2, 3, 4, 4, 2, 3, 3, 4, 4]
    rules = coach.to_document(puzzle(regions=jig))["rules"]
    assert rules[0] == {"type": "grid"} and [r["cells"][:2] for r in rules[1:]][0] == ["r1c1", "r1c2"]
    assert len(rules_of({"rules": rules}, "box")) == 4


def test_rule_types():
    doc = coach.to_document(
        record(
            puzzle(
                {"type": "thermometer", "segments": [seg([0, 1, 2, 3])]},
                {"type": "whisper", "segments": [seg([8, 12])], "settings": {"difference": 2}},
                {"type": "ratio", "segments": [seg([1, 5], ratio=2), seg([13, 9], ratio=3)]},
                {"type": "twoCellSum", "segments": [seg([14, 15], sum=3)]},
                {"type": "difference", "segments": [seg([6, 7], difference=1)]},
                {"type": "littleKiller", "segments": [seg([[2, -1]], positive=True, value=5)]},
                {"type": "quadruple", "segments": [seg([0], digits="13")]},
                {"type": "greaterLess", "segments": [seg([0, 4])]},
            )
        )
    )
    lines = rules_of(doc, "line")
    assert lines[0] == {"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2", "r1c3", "r1c4"]}
    assert lines[1] == {"type": "line", "kind": "whisper", "value": 2, "cells": ["r3c1", "r4c1"]}  # value: a setting
    edges = rules_of(doc, "edge")
    assert {"type": "edge", "kind": "kropki", "color": "black", "cells": ["r1c2", "r2c2"]} in edges
    assert {"type": "edge", "kind": "ratio", "value": 3, "cells": ["r4c2", "r3c2"]} in edges
    assert {"type": "edge", "kind": "sum", "sum": 3, "cells": ["r4c3", "r4c4"]} in edges
    assert {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r2c3", "r2c4"]} in edges
    assert {"type": "edge", "kind": "greater", "cells": ["r2c1", "r1c1"]} in edges  # the app's first cell is smaller
    assert rules_of(doc, "sum") == [
        {"type": "sum", "kind": "little_killer", "sum": 5, "side": "top", "cells": ["r1c2", "r2c1"]}
    ]
    assert rules_of(doc, "quadruple") == [
        {"type": "quadruple", "digits": [1, 3], "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}
    ]


def test_touching_segments_are_one_renban():
    doc = coach.to_document(record(puzzle({"type": "renban", "segments": [seg([1, 0]), seg([4, 0])]})))
    assert rules_of(doc, "line") == [{"type": "line", "kind": "renban", "cells": ["r1c2", "r1c1", "r2c1"]}]


def test_negatives_exempt_their_own_clues():
    doc = coach.to_document(
        record(
            puzzle(
                {"type": "nonconsecutive", "segments": []},
                {"type": "difference", "segments": [seg([0, 1], difference=1)]},
                {"type": "ratio", "segments": [seg([0, 4], ratio=2)], "settings": {"negativeConstraint": True}},
            ),
            solution=None,
        )
    )
    neigh = rules_of(doc, "neighbours")
    assert {"type": "neighbours", "kind": "nonconsecutive", "except": [["r1c1", "r1c2"]]} in neigh
    assert {
        "type": "neighbours",
        "op": "not_ratio",
        "value": 2,
        "step": "orthogonal",
        "except": [["r1c1", "r2c1"]],
    } in neigh


def test_adjacent_maxima_are_not_compared():
    doc = coach.to_document(puzzle({"type": "maximum", "segments": [seg([0]), seg([1])]}))
    assert rules_of(doc, "relation")[0] == {"type": "relation", "op": "less", "pairs": [["r2c1", "r1c1"]]}


def test_style_is_cosmetic_and_settings_values_are_rules():
    settings = {
        "difference": 2,
        "colour": "#FF0000",
        "lineThickness": 30,
        "borderColour": "#000000",
        "borderThickness": 10,
        "opacity": 255,
    }
    doc = coach.to_document(puzzle({"type": "whisper", "segments": [seg([0, 1])], "settings": settings}))
    (line,) = rules_of(doc, "line")
    assert line["value"] == 2
    assert line["style"] == {
        "color": "#ff0000",
        "width": 0.2,
        "outline": "#000000",
        "outline_width": 0.05,
        "opacity": 1.0,
    }
    odd = coach.to_document(
        puzzle(
            {
                "type": "odd",
                "segments": [seg([5])],
                "settings": {"colour": "grey", "shapeSize": 80, "shapeRotation": 45},
            }
        )
    )
    assert rules_of(odd, "cell")[0]["style"] == {"fill": "#e2e2e2", "size": 0.8, "angle": 45}


def test_cell_colours_are_one_fill_decoration():
    cols = ",".join(["01", "1", ""] + [""] * 13)
    doc = coach.to_document(puzzle(colours=["lime", "#123456"], givenColours=cols))
    assert doc["decorations"] == [
        {"kind": "fill", "cells": {"r1c1": ["#def7c5", "#123456"], "r1c2": ["#123456"]}, "style": {"opacity": 1}}
    ]


def test_cosmetic_shapes_become_decorations():
    shape = {"type": "cosmeticShape", "segments": [seg([[0.5, 0.5]], shape="polygon-3"), seg([[1, 1]], shape="circle")]}
    doc = coach.to_document(puzzle(shape))
    tri, circle = doc["decorations"]
    assert tri["kind"] == "polygon" and len(tri["points"]) == 3 and tri["points"][0] == [0.185, 0.5]
    assert circle == {"kind": "circle", "center": [1, 1], "size": [0.63, 0.63], "style": {"fill": "#d5e2ff"}}
    assert doc["rules"] == [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}]  # artwork carries no rule


def test_unknown_type_is_refused_by_name():
    with pytest.raises(NotSupportedError) as e:
        coach.to_document(puzzle({"type": "teleporter", "segments": [seg([0, 5])]}))
    assert e.value.elements == ["teleporter"]


def test_custom_constraints_in_the_description_are_refused():
    with pytest.raises(NotSupportedError, match="custom constraints"):
        coach.to_document(record(puzzle(), custom_constraints=True))


def test_reading_that_breaks_the_solution_is_refused():
    falling = puzzle({"type": "thermometer", "segments": [seg([1, 0])]})  # 2 then 1: not increasing
    with pytest.raises(ReadingMismatch):
        coach.to_document(record(falling))
    assert coach.to_document(record(falling), check_solution=False)["rules"][1]["kind"] == "thermo"


def test_fog_needs_and_uses_the_solution():
    fog = puzzle({"type": "fog", "segments": [seg([15])]}, givens="1" + "0" * 15)
    with pytest.raises(NotSupportedError, match="solution"):
        coach.to_document(fog)
    (rule,) = rules_of(coach.to_document(record(fog)), "fog")
    assert rule == {"type": "fog", "lit": ["r1c1", "r1c2", "r2c1", "r2c2", "r4c4"]}  # the 3x3 around each given


def test_link_reader_takes_a_payload():
    p = payload(puzzle({"type": "antiKnight", "segments": []}))
    assert sources.detect(p) == "coach" and sources.detect("https://sudoku.coach/en/s/LW4k") == "coach"
    assert coach.puzzle_id("https://sudoku.coach/en/s/LW4k") == "LW4k"
    doc = pencilmark.read.link(p)
    assert {"type": "neighbours", "kind": "antiknight"} in doc["rules"]


def test_page_record_is_read_from_the_html():
    rec = {"specificSudoku": {"sudoku_id": "T3st", "sudoku": payload(puzzle()), "solution": SOLUTION}}
    page = f"<script>let mainInitData = {json.dumps(rec)}</script>"
    assert coach.record_of_page(page)["sudoku_id"] == "T3st"
