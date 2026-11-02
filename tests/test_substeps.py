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
    sub = next(s["explanation"]["substeps"] for s in card["steps"] if s["code"] == "SCL")
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
        "400500060000008300025700080003000000000213000000000500070002410009800000010007005",
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
    assert sub[0]["text"].startswith("Read ") and sub[0]["why"] in RULE_FACTS.values()
    assert {a["colour"] for a in sub[-1]["annotations"]} == {"red"}
