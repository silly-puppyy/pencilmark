"""Regions to find (docs/formats/rules/houses-and-regions.mdx 6.3): read, written back, fingerprinted, described;
solved and counted by the engine's search (and CP-SAT, which agrees); graded with the region techniques."""

import pytest

import pencilmark
from pencilmark import cpsat_verify
from pencilmark.exchange import FormatError

# reserved for a later version of the format: the engine support is tested as internal tooling reads it
pytestmark = pytest.mark.usefixtures("reserved_ok")


def doc(rules, givens=None):
    return {"format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4,
            "givens": givens or [0] * 16, "rules": rules}  # fmt: skip


CHAOS = [{"type": "chaos"}, {"type": "region_border", "cells": ["r1c2", "r1c3"]},
         {"type": "same_region", "cells": ["r1c1", "r2c1", "r3c1"]}]  # fmt: skip


def test_read_write_fingerprint_describe():
    d = doc(CHAOS)
    pencilmark.validate(d)
    p = pencilmark.api._load(d)
    assert sorted({g.kind for g in p.groups}) == ["col", "row"]  # rows and columns; the regions are to be found
    out = pencilmark.write.document(p)
    assert out["rules"] == CHAOS
    assert pencilmark.fingerprint(out) == pencilmark.fingerprint(d)
    assert pencilmark.fingerprint(d) != pencilmark.fingerprint(doc([{"type": "grid"}]))
    rules = pencilmark.describe(d)["rules"]
    assert "orthogonally connected regions" in rules["Chaos Construction"]


@pytest.mark.parametrize(
    "rules,msg",
    [
        ([{"type": "chaos"}, {"type": "region_border", "cells": ["r1c1", "r2c2"]}], "orthogonal"),
        ([{"type": "grid"}, {"type": "same_region", "cells": ["r1c1", "r1c2"]}], "chaos area"),
        (
            [{"type": "chaos"}, {"type": "box_grid", "box": [2, 2], "count": [2, 2]}],
            "inside a chaos",
        ),
    ],
)
def test_validation(rules, msg):
    with pytest.raises(FormatError, match=msg):
        pencilmark.validate(doc(rules))


SOL = [1, 2, 3, 4, 3, 4, 1, 2, 2, 1, 4, 3, 4, 3, 2, 1]
QUADRANTS = [["r1c2", "r1c3"], ["r2c2", "r2c3"], ["r3c2", "r3c3"], ["r4c2", "r4c3"], ["r2c1", "r3c1"],
             ["r2c2", "r3c2"], ["r2c3", "r3c3"], ["r2c4", "r3c4"]]  # fmt: skip


@pytest.mark.parametrize(
    "keep,borders,count",
    [
        ((3, 5, 10, 15), QUADRANTS, 1),  # the borders fix the regions, 12 givens the digits
        ((0, 5), QUADRANTS, 24),  # the regions are boxes: the 4 x 4 sudokus with these two givens (CP-SAT: 24)
        ((3, 5, 10, 15), [], 1),
    ],
)
def test_engine_search(keep, borders, count):
    """the engine's search alone (no OR-Tools needed) counts regions-to-find puzzles"""
    givens = [v if (k not in keep if len(keep) == 4 else k in keep) else 0 for k, v in enumerate(SOL)]
    d = doc([{"type": "chaos"}] + [{"type": "region_border", "cells": b} for b in borders], givens)
    sols, complete = cpsat_verify._engine(pencilmark.api._load(d), 100, 10**6)
    assert complete and len(sols) == count
    assert SOL in sols


@pytest.mark.skipif(not cpsat_verify.have_ortools(), reason="needs OR-Tools")
def test_solve_and_count_with_cpsat():
    # 1 2 | 3 4 / 3 4 | 1 2 / ... with given borders that leave exactly one region layout and digit solution
    sol = [1, 2, 3, 4, 3, 4, 1, 2, 2, 1, 4, 3, 4, 3, 2, 1]
    givens = [v if k not in (3, 5, 10, 15) else 0 for k, v in enumerate(sol)]
    borders = [["r1c2", "r1c3"], ["r2c2", "r2c3"], ["r3c2", "r3c3"], ["r4c2", "r4c3"], ["r2c1", "r3c1"],
               ["r2c2", "r3c2"], ["r2c3", "r3c3"], ["r2c4", "r3c4"]]  # fmt: skip
    d = doc([{"type": "chaos"}] + [{"type": "region_border", "cells": b} for b in borders], givens)
    assert pencilmark.count_solutions(d, limit=3) == {"count": 1, "exact": True}
    assert list(pencilmark.solve(d)) == sol or pencilmark.solve(d)["solution"] == sol


def test_graded_with_region_steps():
    """a regions-to-find puzzle gets a card; its route uses the region techniques and every elimination keeps the
    solution"""
    givens = [v if k not in (3, 5, 10, 15) else 0 for k, v in enumerate(SOL)]
    d = doc([{"type": "chaos"}] + [{"type": "region_border", "cells": b} for b in QUADRANTS], givens)
    card = pencilmark.rate(d, fields=["band", "difficulty", "steps"])
    assert card["band"] != "Unknown" and card["difficulty"] is not None
    from pencilmark import cbackend as CB

    steps, solved = CB.solve(pencilmark.api._load(d), pencilmark.api._params("human"), max_steps=100)
    assert solved and all(SOL[c] != v for s in steps for c, v in (s.move.elim or ()))


def test_region_steps_on_the_card():
    """region effects appear in the steps as region / region_eliminations and the card fits the card schema"""
    import json
    from pathlib import Path

    jsonschema = pytest.importorskip("jsonschema")
    givens = [v if k not in (3, 5, 10, 15) else 0 for k, v in enumerate(SOL)]
    d = doc([{"type": "chaos"}] + [{"type": "region_border", "cells": b} for b in QUADRANTS], givens)
    card = pencilmark.rate(d, fields=["band", "steps"])
    schema = json.loads(
        (Path(__file__).parents[1] / "docs" / "pencilmark-grade.schema.json").read_text(encoding="utf-8")
    )
    assert not list(jsonschema.Draft202012Validator(schema).iter_errors(card))


def test_region_sentences():
    """the chaos reading of a rules text: the construction and placement rule in their usual phrasings are understood,
    same / different statements name their elements, any other sentence about regions is a mechanic of its own (the
    reader refuses the puzzle rather than drop it)"""
    from pencilmark.sources._sp_translate import region_statements

    known = (
        "The grid is divided into nine hidden regions, each consisting of orthogonally connected cells. "
        "Digits may not repeat in any row, column, or region. Place the digits 1-9 once in each row, column and "
        "9-cell region. It is up to the solver to determine where these regions are."
    )
    assert region_statements(known) == ({}, [])
    kinds, unknown = region_statements(
        "Arrows do not cross region borders (i.e. a circle and its arrow are part of the same region). "
        "Digits on a thermometer belong to the same region. Cells joined by a white dot are in different regions."
    )
    assert kinds == {"arrow": True, "thermo": True, "white": False} and unknown == []
    _, unknown = region_statements("Region borders block vision. Cages within the same region have the same total.")
    assert len(unknown) == 2


def test_region_rule_reads_custom_rules():
    """a custom rule reading region() is read on its own (RegionRule): the 4x4 example of houses-and-regions.mdx with
    its given border and same-region set written as custom rules grades like the version with the given clues"""
    import json
    import re
    from pathlib import Path

    text = (Path(__file__).parents[1] / "docs/formats/rules/houses-and-regions.mdx").read_text(encoding="utf-8")
    doc = json.loads(re.search(r"A complete 4×4 chaos construction.*?```json\n(.*?)```", text, re.S).group(1))
    custom = dict(
        doc,
        rules=[
            {"type": "chaos"},
            {"type": "custom", "cells": {"a": ["r1c2"], "b": ["r1c3"]}, "holds": "region(a) != region(b)"},
            {
                "type": "custom",
                "cells": {"a": ["r3c1"], "b": ["r4c1"], "c": ["r4c2"]},
                "holds": "region(a) == region(b) and region(b) == region(c)",
            },
        ],
    )
    from pencilmark import exchange as X

    with X._reserved_ok():
        a = pencilmark.rate(doc, fields=["band", "difficulty", "steps"])
        b = pencilmark.rate(custom, fields=["band", "difficulty", "steps"])
        assert pencilmark.solve(custom) == pencilmark.solve(doc)
    assert "RRU" in {s["code"] for s in b["steps"]}
    assert (a["band"], a["difficulty"]) == (b["band"], b["difficulty"])


def test_cpsat_models_region_rules():
    """CP-SAT encodes region() (the label Booleans) and take_while with a lambda, and agrees with the C++ search"""
    import json
    import re
    from pathlib import Path

    pytest.importorskip("ortools")
    from pencilmark import api
    from pencilmark import exchange as X

    text = (Path(__file__).parents[1] / "docs/formats/rules/houses-and-regions.mdx").read_text(encoding="utf-8")
    doc = json.loads(re.search(r"A complete 4×4 chaos construction.*?```json\n(.*?)```", text, re.S).group(1))
    sight = {
        "type": "custom",
        "cells": {"x": ["r1c1"], "r": ["r1c2", "r1c3", "r1c4"]},
        "holds": "len(take_while(r, y => region(y) == region(x))) <= 1",  # the given border after r1c2
    }
    puzzle = dict(doc, rules=doc["rules"][:1] + [doc["rules"][2], sight])  # chaos, the same-region set, the sight rule
    with X._reserved_ok():
        p = api._load(puzzle)
        assert cpsat_verify.build_model(p)[0] is not None  # modelled, not left to the C++ search
        by_cpsat = cpsat_verify.cpsat_solutions(p, limit=2)
        by_search = cpsat_verify._engine(p, 2, 2_000_000, 60)[0]
    assert sorted(map(list, by_cpsat)) == sorted(map(list, by_search))


def test_region_sight():
    """region_sight (6.3): clues counting the cells of their own region they see; validated, written back by name,
    described, and solved (a 4x4 whose regions to find are its 2x2 boxes, every sight clue true for them)"""
    from pencilmark import exchange as X

    sol = [1, 2, 3, 4, 3, 4, 1, 2, 2, 1, 4, 3, 4, 3, 2, 1]
    doc = {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": 4, "cols": 4},
        "digits": 4,
        "givens": [1, 0, 0, 0, 0, 4, 0, 0, 0, 0, 4, 0, 0, 0, 0, 1],
        "rules": [{"type": "chaos"}, {"type": "region_sight", "cells": ["r1c3", "r2c1", "r3c4", "r4c2"]}],
    }
    with X._reserved_ok():
        pencilmark.validate(doc)
        assert pencilmark.write.document(doc)["rules"][1] == doc["rules"][1]
        assert pencilmark.count_solutions(doc, limit=2)["count"] == 1
        assert pencilmark.solve(doc) == sol
        assert "sees" in pencilmark.describe(doc)["rules_text"]
        arrow = {"type": "region_sight", "cells": ["r1c1"], "directions": ["right"], "self": False, "value": 1}
        pencilmark.validate(dict(doc, rules=[{"type": "chaos"}, arrow]))
        for bad in ({"directions": ["north"]}, {"directions": []}, {"self": 1}, {"value": -1}):
            with pytest.raises(FormatError):
                pencilmark.validate(dict(doc, rules=[{"type": "chaos"}, dict(arrow, **bad)]))


def test_region_rule_learns_borders():
    """a rule comparing regions only (region_sight) teaches which cells share a region while every label is open: a
    sight clue that sees only itself lies in a different region from each of its four neighbors"""
    from pencilmark import api
    from pencilmark import cbackend as CB
    from pencilmark import exchange as X

    doc = {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": 4, "cols": 4},
        "digits": 4,
        "givens": [0] * 16,
        "rules": [{"type": "chaos"}, {"type": "region_sight", "cells": ["r2c2"], "value": 1}],
    }
    with X._reserved_ok():
        p = api._load(doc)
        moves = CB.state_moves(p, api._params("human"), limit_per_tech=8, details=True)
    rfx = next(m["rfx"] for m in moves if m["name"] == "RegionRule")
    assert sorted((c, a) for k, c, a in rfx if k == CB.AE_REG_NEQ) == [(5, 1), (5, 4), (5, 6), (5, 9)]
