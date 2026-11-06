"""Shading (yin-yang, docs/formats/rules/whole-board-rules.mdx 6.19): validated, read, written, fingerprinted and
described; solve / count check it (the C++ search carries a colour per cell, agreeing with CP-SAT on 700 random small
puzzles); custom rules read it with shaded(); rate refuses it."""

import json

import pytest

import pencilmark

BASE = {
    "format": "pencilmark-puzzle",
    "format_version": 1,
    "board": {"rows": 4, "cols": 4},
    "digits": 4,
    "givens": [1, 0, 0, 0, 0, 0, 3, 0, 0, 4, 0, 0, 0, 0, 0, 2],
    "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}],
}


def with_rule(rule):
    doc = json.loads(json.dumps(BASE))
    doc["rules"].append(rule)
    return doc


def test_read_write_describe():
    doc = with_rule({"type": "yin_yang", "shaded": ["r1c1"], "unshaded": ["r4c4"]})
    out = pencilmark.write.document(doc, solution=True, describe=True)
    assert {"type": "yin_yang", "shaded": ["r1c1"], "unshaded": ["r4c4"]} in out["rules"]
    assert pencilmark.fingerprint(doc) != pencilmark.fingerprint(BASE)
    assert pencilmark.describe(doc)["type"] == "Tiny Yin Yang Sudoku"
    with pytest.raises(pencilmark.FormatError, match="overlap"):
        pencilmark.api._load(with_rule({"type": "yin_yang", "shaded": ["r1c1"], "unshaded": ["r1c1"]}))
    two = with_rule({"type": "yin_yang"})
    two["rules"].append({"type": "yin_yang"})
    with pytest.raises(pencilmark.FormatError, match="at most one"):
        pencilmark.api._load(two)


def test_count_couplings_and_rate_unknown():
    assert pencilmark.count_solutions(with_rule({"type": "yin_yang", "shaded": ["r1c1"]}))["count"] == 1
    checker = {"type": "yin_yang", "shaded": ["r1c1", "r2c2"], "unshaded": ["r1c2", "r2c1"]}  # disconnects a colour
    assert pencilmark.count_solutions(with_rule(checker))["count"] == 0
    card = pencilmark.rate(with_rule({"type": "yin_yang", "shaded": ["r1c1"]}))  # no human route: Unknown, with why
    assert card["band"] == "Unknown" and card["difficulty"] is None and card["contains"] == []
    assert "shading" in card["reason"]
    with pytest.raises(pencilmark.NoSolution):  # a wrong input is still an error
        pencilmark.rate(with_rule(checker))


def test_shaded_in_custom_rules():
    """shaded(c) needs the shading layer; with it the search checks the rule on each solution (r1c1 holds 1: "shaded
    exactly when odd" and "shaded exactly when even, and unshaded" each leave the one solution)"""
    rule = lambda h: {"type": "custom", "cells": {"a": ["r1c1"]}, "holds": h}
    doc = with_rule({"type": "yin_yang"})
    doc["rules"].append(rule("shaded(a) == odd(a)"))
    assert pencilmark.count_solutions(doc)["count"] == 1
    doc["rules"][-1] = rule("shaded(a) == even(a)")
    doc["rules"].append({"type": "custom", "cells": {"a": ["r1c1"]}, "holds": "not shaded(a)"})
    assert pencilmark.count_solutions(doc)["count"] == 1  # r1c1 = 1: unshaded either way
    with pytest.raises(pencilmark.NotSupportedError, match="shading"):
        pencilmark.api._load(dict(BASE, rules=BASE["rules"] + [rule("shaded(a)")]))
