"""Shading (yin-yang, docs/formats/rules/whole-board-rules.mdx 6.19): validated, read, written, fingerprinted and
described; solve / count check it with CP-SAT (the C++ search has no shading layer yet: undecided); rate refuses it."""

import json

import pytest

import pencilmark

BASE = {
    "format": "sudoku-puzzle",
    "format_version": 1,
    "board": {"rows": 4, "cols": 4},
    "digits": 4,
    "givens": [1, 0, 0, 0, 0, 0, 3, 0, 0, 4, 0, 0, 0, 0, 0, 2],
    "rules": [{"type": "box_grid", "origin": "r1c1", "box": [2, 2]}],
}


def with_rule(rule):
    doc = json.loads(json.dumps(BASE))
    doc["rules"].append(rule)
    return doc


def test_read_write_describe():
    doc = with_rule({"type": "yin_yang", "shaded": ["r1c1"], "unshaded": ["r4c4"]})
    out = pencilmark.to_export(doc)
    assert {"type": "yin_yang", "shaded": ["r1c1"], "unshaded": ["r4c4"]} in out["rules"]
    assert pencilmark.fingerprint(doc) != pencilmark.fingerprint(BASE)
    assert pencilmark.describe(doc)["type"] == "Tiny Yin Yang Sudoku"
    with pytest.raises(pencilmark.FormatError, match="overlap"):
        pencilmark.load(with_rule({"type": "yin_yang", "shaded": ["r1c1"], "unshaded": ["r1c1"]}))
    two = with_rule({"type": "yin_yang"})
    two["rules"].append({"type": "yin_yang"})
    with pytest.raises(pencilmark.FormatError, match="at most one"):
        pencilmark.load(two)


def test_count_with_cpsat_and_rate_refused():
    pytest.importorskip("ortools")
    assert pencilmark.count_solutions(with_rule({"type": "yin_yang", "shaded": ["r1c1"]}))["count"] == 1
    checker = {"type": "yin_yang", "shaded": ["r1c1", "r2c2"], "unshaded": ["r1c2", "r2c1"]}  # disconnects a colour
    assert pencilmark.count_solutions(with_rule(checker))["count"] == 0
    with pytest.raises(pencilmark.NotSupportedError, match="shading"):
        pencilmark.rate(with_rule({"type": "yin_yang"}))
