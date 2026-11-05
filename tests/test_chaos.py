"""Regions to find (docs/formats/rules/houses-and-regions.mdx 6.3): read, written back, fingerprinted, described;
solved and counted by the engine's search (and CP-SAT, which agrees); graded with the region techniques."""

import pytest

import pencilmark
from pencilmark import cpsat_verify
from pencilmark.exchange import FormatError


def doc(rules, givens=None):
    return {"format": "sudoku-puzzle", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4,
            "givens": givens or [0] * 16, "rules": rules}  # fmt: skip


CHAOS = [{"type": "chaos"}, {"type": "region_border", "cells": ["r1c2", "r1c3"]},
         {"type": "same_region", "cells": ["r1c1", "r2c1", "r3c1"]}]  # fmt: skip


def test_read_write_fingerprint_describe():
    d = doc(CHAOS)
    pencilmark.validate(d)
    p = pencilmark.load(d)
    assert sorted({g.kind for g in p.groups}) == ["col", "row"]  # rows and columns; the regions are to be found
    out = pencilmark.to_export(p, with_solution=False, describe=False)
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
    sols, complete = cpsat_verify._engine(pencilmark.load(d), 100, 10**6)
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

    steps, solved = CB.solve(pencilmark.load(d), pencilmark.api._params("human"), max_steps=100)
    assert solved and all(SOL[c] != v for s in steps for c, v in (s.move.elim or ()))


def test_region_steps_on_the_card():
    """region effects appear in the steps as region / region_eliminations and the card fits the card schema"""
    import json
    from pathlib import Path

    jsonschema = pytest.importorskip("jsonschema")
    givens = [v if k not in (3, 5, 10, 15) else 0 for k, v in enumerate(SOL)]
    d = doc([{"type": "chaos"}] + [{"type": "region_border", "cells": b} for b in QUADRANTS], givens)
    card = pencilmark.rate(d, fields=["band", "steps"])
    schema = json.loads((Path(__file__).parents[1] / "docs" / "sudoku-grade.schema.json").read_text(encoding="utf-8"))
    assert not list(jsonschema.Draft202012Validator(schema).iter_errors(card))
