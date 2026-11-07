"""usage.rule_usage credits: relations a line generated count for the line; different-digit links (anti-knight) count
where they erase notes without a step naming them (note-taking, placements)."""

from types import SimpleNamespace as NS

from pencilmark import api
from pencilmark import usage as U

DOC = {
    "format": "pencilmark-puzzle",
    "format_version": 1,
    "board": {"rows": 9, "cols": 9},
    "digits": 9,
    "givens": [0] * 81,
    "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}, {"type": "neighbours", "kind": "antiknight"}],
}


def _step(technique, cell=None, digit=None):
    explain = {"technique": technique, "placement": {"cell": cell, "digit": digit} if cell is not None else None}
    return NS(move=NS(explain=explain), mode="notes")


def _credited(givens, steps):
    p = api._load(dict(DOC, givens=givens))
    per = [set() for _ in steps]
    U._implicit_links(p, steps, per)
    return ["neq relation" in s for s in per]


def test_note_taking_and_placement_credit_the_link():
    g = [0] * 81
    g[2] = 5  # r1c3 = 5: its knight cells r2c5, r3c4 (outside its houses) lose the note 5
    assert _credited(g, [_step("TakeNotes"), _step("NakedSingle", 40, 1)]) == [True, True]


def test_no_credit_when_the_linked_cells_cannot_hold_the_digit():
    g = [0] * 81
    g[13], g[21] = 1, 2  # r1c3's knight cells outside its box (r2c5, r3c4) filled
    assert _credited(g, [_step("NakedSingle", 2, 5)]) == [False]
    g = [0] * 81
    g[13] = 1  # r2c5 filled; r3c4 empty, but column 4 holds 5 (r9c4)
    g[75] = 5
    assert _credited(g, [_step("NakedSingle", 2, 5)]) == [False]
    g[75] = 0  # r3c4 can hold 5 again
    assert _credited(g, [_step("NakedSingle", 2, 5)]) == [True]


def test_line_relations_are_credited_to_the_line():
    p = api._load(
        dict(
            DOC,
            rules=[
                {"type": "box_grid", "box": [3, 3], "count": [3, 3]},
                {"type": "line", "kind": "palindrome", "cells": ["r1c1", "r1c2", "r1c3", "r1c4"]},
            ],
        )
    )
    rl = U._relation_lines(p)
    assert set(rl.values()) == {"palindrome line"}
    assert rl[(None, "r1c1", "r1c4")] == rl[("eq", "r1c4", "r1c1")] == "palindrome line"
