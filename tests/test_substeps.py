"""The `substeps` explanation level (docs/formats/grade-card.md 5): only on request, and the class-colouring builder
tells a colouring as standalone sentences with a legend, one reason per rule and annotations that fit the schema."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import pencilmark
from pencilmark import export
from pencilmark.explain import records as R
from pencilmark.explain.base import Namer

SCHEMA = Path(__file__).parents[1] / "docs" / "sudoku-grade.schema.json"


def test_levels_on_request_only():
    assert "substeps" not in export.explain_levels(True)
    assert export.explain_levels(["short", "substeps"]) == ["short", "substeps"]


def _whisper_row():
    d = pencilmark.from_string("." * 81)
    d["rules"].append({"type": "line", "kind": "whisper", "cells": ["r1c3", "r1c4", "r1c5", "r1c6", "r1c7"]})
    p = pencilmark.load(d)
    p.finalize()
    return p


def test_class_colouring_substeps():
    p = _whisper_row()
    nm = Namer(p)
    cells = [2, 3, 4, 5, 6]  # r1c3 .. r1c7, alternating along the whisper
    row1 = next(g.name for g in p.groups if set(cells) <= set(g.cells) and len(g.cells) == 9)
    cc = {
        "sides": {c: i % 2 for i, c in enumerate(cells)},
        "orientation": 0,  # side 0 holds the low digits
        "anchor": None,
        "houses": [{"name": row1}],
        "links": [{"cells": [a, b], "opposite": True} for a, b in zip(cells, cells[1:])],
    }
    ctx = SimpleNamespace(nm=nm, p=p, gi=lambda name: nm.gidx.get(name), elims=[(2, 6), (3, 1)])
    sub = R._class_substeps(ctx, cc, "low (1–4)", "high (6–9)", 0)
    assert sub[0]["legend"] == {"blue": "low (1–4)", "yellow": "high (6–9)"}
    follow = [s for s in sub if s["text"].startswith("Follow the German whisper")]
    assert len(follow) == 1 and len(follow[0]["annotations"]) == 4  # the run along the line is one sub-step
    assert sum("German whisper differ" in s.get("why", "") for s in sub) == 1  # each reason once
    assert sub[-1]["text"].startswith("So ") and {a["colour"] for a in sub[-1]["annotations"]} == {"red"}
    ids = [a["id"] for s in sub for a in s.get("annotations", [])]
    assert ids == sorted(set(ids))  # unique, increasing
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    item = schema["properties"]["steps"]["items"]["properties"]["explanation"]["properties"]["substeps"]
    jsonschema.Draft202012Validator(item).validate(sub)


def test_chain_substeps_end_to_end():
    card = pencilmark.rate(
        "000000450000301006000020000030800960002030070010005800500907000600580010040000000",
        fields=["steps"],
        explain=["short", "substeps"],
    )
    chains = {"XCL", "KTE", "SKY", "XYC", "AIC", "TUR"}  # X-Chain, 2-String Kite, Skyscraper, XY-Chain, AIC, Turbot
    told = [s for s in card["steps"] if s["code"] in chains and s.get("explanation", {}).get("substeps")]
    assert told, "the X-Chains of this route are told as sub-steps"
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(card)
    for s in told:
        sub = s["explanation"]["substeps"]
        lines = [a["line"] for x in sub for a in x.get("annotations", []) if "arrow" in a]
        assert lines and lines[0] == "strong" and all(x != y for x, y in zip(lines, lines[1:]))  # alternating
        assert {a["colour"] for a in sub[-1]["annotations"]} == {"red"}


def test_simple_colouring_substeps():
    card = pencilmark.rate(
        "030020006009006020000050100060400900300000001001007050007090000040800200200040030",
        fields=["steps"],
        explain=["substeps"],
    )
    sub = next(s["explanation"]["substeps"] for s in card["steps"] if s["code"] == "CSM")
    assert set(sub[0]["legend"]) == {"blue", "yellow"}
    cols = [a["colour"] for x in sub[1:-1] for a in x["annotations"] if "candidate" in a]
    assert set(cols) <= {"blue", "yellow"} and {a["colour"] for a in sub[-1]["annotations"]} == {"red"}


def test_killer_combination_substeps():
    doc = json.loads(
        (Path(__file__).parents[1] / "docs/examples/learning/killer-3-combinations.json").read_text("utf-8")
    )
    card = pencilmark.rate(doc.get("puzzle", doc), fields=["steps"], explain=["substeps"])
    told = [
        s["explanation"]["substeps"]
        for s in card["steps"]
        if s["code"] == "CGC" and "substeps" in s.get("explanation", {})
    ]
    assert told
    for sub in told:
        assert {a["colour"] for a in sub[-1]["annotations"]} == {"red"} and sub[-1]["text"].startswith("So ")


def test_fish_substeps():
    card = pencilmark.rate(
        "030020006009006020000050100060400900300000001001007050007090000040800200200040030",
        fields=["steps"],
        explain=["substeps"],
    )
    sub = next(s["explanation"]["substeps"] for s in card["steps"] if s["code"] == "XWG")
    assert sub[0]["text"].startswith("Look at the") and {a["colour"] for a in sub[0]["annotations"]} == {"blue"}
    assert "why" in sub[1] and {a["colour"] for a in sub[-1]["annotations"]} == {"red"}


def test_locked_and_subset_substeps():
    card = pencilmark.rate(
        "7......2..3....6..9.5..2..465.4....8...1.8...1....5.475..3..1.6..9....3..4......2",  # a pointing pair, a hidden pair and a naked triple on the trace
        fields=["steps"],
        explain=["substeps"],
    )
    got = {s["code"]: s["explanation"]["substeps"] for s in card["steps"] if "substeps" in s.get("explanation", {})}
    for code in ("PPR", "HPR", "NTR"):
        sub = got[code]
        assert {a["colour"] for a in sub[0]["annotations"]} == {"blue"}
        assert {a["colour"] for a in sub[-1]["annotations"]} == {"red"} and any("why" in x for x in sub)


def test_line_rule_substeps_and_facts():
    from pencilmark.explain.facts import RULE_FACTS

    doc = json.loads((Path(__file__).parents[1] / "docs/examples/generated/hardest-kropki.json").read_text("utf-8"))
    card = pencilmark.rate(doc.get("puzzle", doc), fields=["steps"], explain=["substeps"])
    sub = next(
        s["explanation"]["substeps"]
        for s in card["steps"]
        if s["code"] == "LNR" and "substeps" in s.get("explanation", {})
    )
    assert sub[0]["text"].startswith("Read ") and any(sub[0]["why"].startswith(f) for f in RULE_FACTS.values())
    assert {a["colour"] for a in sub[-1]["annotations"]} == {"red"}


def test_wing_substeps():
    card = pencilmark.rate(
        "053070008000000003001300000060800009040090060200007010000004600500000000700050290",
        fields=["steps"],
        explain=["substeps"],
    )
    sub = next(s["explanation"]["substeps"] for s in card["steps"] if s["code"] == "YWG")
    assert [a["colour"] for a in sub[0]["annotations"]] == ["cyan", "green", "green"]
    assert all(a["line"] == "plain" for x in sub[1:3] for a in x["annotations"])
    assert {a["colour"] for a in sub[-1]["annotations"]} == {"red"}


CHAOS_DEMO = {
    "format": "sudoku-puzzle",
    "format_version": 1,
    "board": {"rows": 5, "cols": 5},
    "digits": 5,
    "givens": [0, 0, 3, 0, 0, 0, 0, 4, 3, 2, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 4, 0, 5, 0],
    "rules": [
        {"type": "chaos"},
        {"type": "region_border", "cells": ["r2c2", "r3c2"]},
        {"type": "region_border", "cells": ["r2c5", "r3c5"]},
        {"type": "region_border", "cells": ["r4c3", "r4c4"]},
        {"type": "region_border", "cells": ["r1c4", "r2c4"]},
        {"type": "region_border", "cells": ["r1c1", "r1c2"]},
        {"type": "region_border", "cells": ["r2c2", "r2c3"]},
        {"type": "region_border", "cells": ["r1c3", "r2c3"]},
        {"type": "region_border", "cells": ["r2c1", "r2c2"]},
        {"type": "region_border", "cells": ["r5c3", "r5c4"]},
        {"type": "region_border", "cells": ["r4c1", "r4c2"]},
        {"type": "region_border", "cells": ["r3c4", "r3c5"]},
    ],
}  # a unique 5x5 / 6x6 regions-to-find puzzle from a random layout (generated for this test)


def test_region_substeps_keep_their_colours():
    jsonschema = pytest.importorskip("jsonschema")
    only = pencilmark.rate(
        CHAOS_DEMO, fields=["steps"], explain=["substeps"]
    )  # steps without sub-steps: no explanation
    jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(only)
    card = pencilmark.rate(CHAOS_DEMO, fields=["steps"], explain=["short", "substeps"])
    colour_of = {}
    joins = 0
    for s in card["steps"]:
        if "region" not in s:
            continue
        sub = s["explanation"]["substeps"]
        k = int(s["region"].split("@")[1])
        cols = {a["colour"] for a in sub[0]["annotations"]}
        assert len(cols) == 1
        assert colour_of.setdefault(k, cols.pop()) == next(iter({a["colour"] for a in sub[0]["annotations"]}))
        joins += any(x["text"].startswith("So ") and "joins" in x["text"] for x in sub)
    assert colour_of and joins
    first = next(s["explanation"]["substeps"][0] for s in card["steps"] if s.get("region", "").endswith("@1"))
    assert "r1c1" in {a["cell"] for a in first["annotations"]}  # region 1 holds the first cell from the start


def test_rule_facts_follow_the_digit_range():
    """rule facts are worked out for the puzzle's digits, not written for 9x9: on 16x16 a whisper of difference 5 has
    no impossible digit and no low / high alternation; a 6x6 whisper of 3 alternates 1-3 / 4-6"""
    from pencilmark.explain.facts import derived

    assert derived("whisper", 9) == (
        "With digits 1-9, 5 can never be on the line and neighbours alternate between low (1-4) and high (6-9) digits."
    )
    assert derived("whisper", 16) == ""
    assert (
        derived("whisper", 6, k=3) == "With digits 1-6, neighbours alternate between low (1-3) and high (4-6) digits."
    )
    assert derived("arrow", 9, 2).startswith("With digits 1-9, 9 cannot sit on its 2-cell shaft")
    assert derived("renban", 6, 4) == "A 4-cell renban with digits 1-6 always holds 3 and 4."
    assert derived("kropki_chain", 6) == "With digits 1-6, 5 never sits on a black dot."
