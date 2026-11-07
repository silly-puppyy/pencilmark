"""Generator tests: pencilmark.generate takes a pencilmark-spec request (docs/formats/generator-spec.md). Each case runs in a few seconds."""

import json
import os
import re
import subprocess
import sys
import time

import pytest

import pencilmark
from pencilmark import cpsat_verify as V
from pencilmark.gen import GenerationFailed
from pencilmark.gen import api as GA
from pencilmark.publish_flags import QUALITY


def spec(D=9, box=None, where=None, rules=(), givens=None, symmetry=None, seed=None, time_limit=300):
    """a pencilmark-spec for a D x D board with standard boxes plus the given templates / targets"""
    box = box or {4: [2, 2], 6: [2, 3], 9: [3, 3]}[D]
    d = {
        "format": "pencilmark-spec",
        "format_version": 1,
        "board": {"rows": D, "cols": D},
        "digits": D,
        "rules": [{"type": "box_grid", "box": box, "count": [box[1], box[0]]}, *rules],
    }
    if givens is not None:
        d["givens"] = givens
    if symmetry:
        d["symmetry"] = [{"kind": symmetry, "of": "givens"}]
    if where:
        d["where"] = where
    d["limits"] = {"time": time_limit, **({"seed": seed} if seed is not None else {})}
    return d


def unique(puzzle):
    p = pencilmark.api._load(puzzle)
    sols = V.solutions(p, limit=2, time_limit=30)
    assert sols is not None, "uniqueness undecided"
    return len(sols) == 1 and list(sols[0]) == [v for v in puzzle["solution"] if v is not None]


def run(doc, budget=150):  # a runaway guard; CI on Windows is about 2x slower than Linux
    t = time.time()
    if isinstance(doc, dict) and "quality" not in doc:  # these tests check generation, not the checks (preset off)
        doc = dict(doc, quality={k: {"severity": "off"} for k in QUALITY})
    r = pencilmark.generate(doc)
    assert time.time() - t < budget
    asked = (doc.get("meta") or {}) if isinstance(doc, dict) else {}
    meta = r["puzzle"].get("meta", {})
    assert r["puzzle"]["format"] == "pencilmark-puzzle" and ("generated_from" in meta) == ("generated_from" in asked)
    assert unique(r["puzzle"])
    assert r["info"]["unique_verified"] is True
    return r


def test_classic_4x4():
    r = run(spec(4, seed=1))
    assert r["puzzle"]["digits"] == 4 and r["card"]["band"] in GA.BANDS


def test_classic_6x6_symmetric():
    r = run(spec(6, symmetry="rot180", seed=2))
    g = r["puzzle"]["givens"]
    assert all((g[i] == 0) == (g[35 - i] == 0) for i in range(36))


def test_classic_9x9_difficulty_range():
    r = run(spec(9, where={"difficulty": [2, 4]}, seed=2))  # seed 2: 2 s (seed 1 took 28 s)
    assert 2 <= r["card"]["difficulty"] <= 4


def test_kropki_min():
    # 4x4: the same minimal-dots search in 0.2 s (6x6 took 11-25 s, mostly the uniqueness proofs)
    r = run(spec(4, rules=[{"type": "edge", "kind": "kropki", "count": "min"}], seed=1))
    rules = r["puzzle"]["rules"]
    assert any(x["type"] == "edge" and x["kind"] == "kropki" for x in rules) and set(r["puzzle"]["givens"]) == {0}


def test_deterministic():
    """same spec + seed -> same puzzle, also across processes with different string hashing (a variant spec: element
    candidates are sets, and their order once depended on PYTHONHASHSEED)"""
    doc = spec(
        6,
        rules=[{"type": "line", "kind": "thermo", "count": 2}, {"type": "edge", "kind": "kropki", "count": [1, 3]}],
        givens={"count": [4, 8]},
        where={"band": "Medium"},
        seed=3,
        time_limit=60,
    )
    code = "import json, sys, pencilmark; print(json.dumps(pencilmark.generate(json.loads(sys.argv[1]))['puzzle']))"
    out = [
        subprocess.run(
            [sys.executable, "-c", code, json.dumps(doc)],
            capture_output=True,
            text=True,
            timeout=150,
            env={**os.environ, "PYTHONHASHSEED": h},
        ).stdout
        for h in ("1", "2")
    ]
    assert out[0] and out[0] == out[1]


def test_only_specs():
    """the generator takes pencilmark-spec requests only; unsupported parts are refused, not ignored"""
    with pytest.raises(TypeError):
        pencilmark.generate({"size": 9, "target_band": "Hard"})
    with pytest.raises(pencilmark.NotSupportedError):
        pencilmark.generate(dict(spec(9), limits={"results": 3}))


def test_feasibility_fails_fast():
    t = time.time()
    with pytest.raises(GenerationFailed, match="information budget"):
        pencilmark.generate(
            spec(
                9,
                givens={"count": 0},
                rules=[{"type": "edge", "kind": "kropki", "count": [5, None]}],
                where={"elements": {"max": 5}},
            )
        )
    with pytest.raises(GenerationFailed, match="at least 17 givens"):
        pencilmark.generate(spec(9, givens={"count": [0, 12]}))
    assert any("Hard technique" in p for p in GA.feasibility({"size": 9, "target_band": "Easy", "require": ["SWF"]}))
    assert any("unknown element kind" in p for p in GA.feasibility({"elements": {"yin_yang": 2}}))
    assert time.time() - t < 2


def test_uniquify():
    d = {"v": 1, "digits": 6, "box": "2x3", "numbers": "." * 36}
    out = GA.uniquify(d, seed=1)
    assert GA.is_unique(out) and sum(ch != "." for ch in out["numbers"]) >= 8


def test_capped_classes_budget():
    """when every element class has a maximum, the caps bound the information budget"""
    probs = GA.feasibility(
        GA.Spec.from_any({"size": 9, "max_givens": 0, "elements": {"kropki_black": [0, 2], "kropki_white": [0, 3]}})
    )
    assert any("information budget" in p for p in probs), probs


def test_element_classes_and_ranges():
    """per-class counts: 6 givens, exactly 2 black kropki, any number of white (the dense-seeding path)"""
    r = run(
        spec(
            9,
            where={"band": "Easy"},
            givens={"count": 6},
            seed=1,
            rules=[
                {"type": "edge", "kind": "kropki", "color": "black", "count": 2},
                {"type": "edge", "kind": "kropki", "color": "white", "count": "auto"},
            ],
        )
    )
    els = r["info"]["elements"]
    assert r["info"]["givens"] == 6 and els.get("kropki_black") == 2 and els.get("kropki_white", 0) >= 1, r["info"]


def test_spec_examples():
    """docs/formats/generator-spec.md's example and docs/examples/specs run (spec_to_gen accepts them); reserved/ examples are refused"""
    import json
    import re
    from pathlib import Path

    from pencilmark import spec_format as SF

    docs = Path(__file__).resolve().parents[1] / "docs"
    text = (docs / "formats" / "generator-spec.md").read_text(encoding="utf-8")
    example = json.loads(re.search(r"```json\n(.*?)```", text, re.S).group(1))
    SF.spec_to_gen(example)
    for f in sorted((docs / "examples" / "specs").glob("*.json")):
        SF.spec_to_gen(json.loads(f.read_text(encoding="utf-8")))
    for f in sorted((docs / "examples" / "specs" / "reserved").glob("*.json")):
        with pytest.raises((pencilmark.NotSupportedError, pencilmark.FormatError)):
            SF.spec_to_gen(json.loads(f.read_text(encoding="utf-8")))


def test_parity_templates():
    """docs/formats/generator-spec.md 2: odd, even and parity cell templates are accepted and written back as given"""
    from pencilmark import spec_format as SF

    for kind in ("odd", "even", "parity"):
        spec = {
            "format": "pencilmark-spec",
            "format_version": 1,
            "board": {"rows": 9, "cols": 9},
            "digits": 9,
            "rules": [
                {"type": "box_grid", "box": [3, 3], "count": [3, 3]},
                {"type": "cell", "kind": kind, "count": 6},
            ],
        }
        SF.validate_spec(spec)
        back = SF.spec_from_gen(SF.spec_to_gen(spec))
        assert [r for r in back["rules"] if r["type"] == "cell"] == [{"type": "cell", "kind": kind, "count": 6}]


def test_shape_limits_and_max():
    """docs/formats/generator-spec.md 2: a cage `sum` with the count "max" (every cage sums to 7, as many as fit) and a
    line `length` (one whisper of at least 8 cells)"""
    r = run(spec(6, rules=[{"type": "cage", "sum": 7, "count": "max"}], seed=1, time_limit=5))
    cages = [x for x in r["puzzle"]["rules"] if x["type"] == "cage"]
    assert len(cages) >= 4 and all(c["sum"] == 7 for c in cages), cages
    assert r["info"]["found"] >= 1
    r = run(spec(rules=[{"type": "line", "kind": "whisper", "length": [8, None], "count": 1}], seed=1, time_limit=60))
    lines = [x for x in r["puzzle"]["rules"] if x["type"] == "line"]
    assert len(lines) == 1 and len(lines[0]["cells"]) >= 8, lines


def test_difficulty_min():
    """where.difficulty "min": the easiest result found in the time is returned"""
    r = run(spec(4, where={"difficulty": "min"}, seed=1, time_limit=3))
    assert r["info"]["found"] >= 1


def test_shape_round_trip_and_refusals():
    from pencilmark import spec_format as SF

    rules = [
        {"type": "cage", "count": "max", "size": [2, 3], "sum": 10},
        {"type": "line", "kind": "thermo", "count": 2, "length": [7, 9]},
        {"type": "arrow", "count": 1, "length": 3},
    ]
    doc = spec(rules=rules, where={"difficulty": "max"})
    back = SF.spec_from_gen(SF.spec_to_gen(doc))
    assert back["rules"][1:] == rules and back["where"] == {"difficulty": "max"}
    for bad in (
        {"type": "line", "kind": "thermo", "count": 1, "sum": 10},  # sum is for cages
        {"type": "cage", "count": 1, "length": 3},  # a cage has a size
    ):
        with pytest.raises(pencilmark.NotSupportedError):
            SF.spec_to_gen(spec(rules=[bad]))
    assert GA.feasibility(SF.spec_to_gen(spec(rules=[{"type": "cage", "count": 2, "size": [12, None]}])))


def test_max_leaves_room_for_required_classes():
    """a "max" class is packed after the other classes' minimums: every cell marked odd or even would leave no room for
    the two whispers asked for (every attempt was pruned before)"""
    rules = [
        {"type": "cell", "kind": "parity", "count": "max"},
        {"type": "line", "kind": "whisper", "count": 2, "value": 3},
    ]
    r = run(spec(6, rules=rules, givens={"count": [0, 10]}, seed=41, time_limit=6))
    assert sum(1 for x in r["puzzle"]["rules"] if x["type"] == "line") == 2


def test_malformed_request_parts_are_format_errors():
    """found by mutating requests (tools/fuzz_inputs.py --specs): parts of the wrong type raised TypeError, KeyError or
    AttributeError"""
    for extra in ({"where": 5}, {"limits": "x"}, {"meta": 3}, {"rules": 5}, {"symmetry": 5}):
        with pytest.raises(pencilmark.FormatError):
            pencilmark.generate(dict(spec(4), **extra))
    # and a quality that is not an object, or a box_grid with a bad origin or no count (2026-11-01, KeyError / TypeError)
    for extra in ({"quality": 0}, {"quality": ["x"]}, {"quality": "x"}):
        with pytest.raises(pencilmark.FormatError):
            pencilmark.generate(dict(spec(4), **extra))
    with pytest.raises(pencilmark.FormatError):  # a field that is not a name
        pencilmark.generate(dict(spec(4), fields=[["band"]]))
    with pytest.raises(pencilmark.FormatError):  # a locked rule's kind that is not a string
        pencilmark.generate(dict(spec(4), rules=spec(4)["rules"] + [{"type": "region", "kind": ["diagonal"]}]))
    for bad in ({"origin": 0, "count": [2, 2]}, {"origin": "a1", "count": [2, 2]}, {}):  # a bad origin; no count
        with pytest.raises(pencilmark.FormatError):
            pencilmark.generate(dict(spec(4), rules=[{"type": "box_grid", "box": [2, 2], **bad}]))


def test_layout_requests():
    """a named layout is one box_grid per grid at its origins; locked rules of different digits and givens per grid
    are read and written back; locked rules the grid fill cannot respect and unknown origins are refused"""
    from pencilmark import puzzle_json as PJ
    from pencilmark import spec_format as SF

    origins = PJ._layouts()["samurai"]
    grids = [{"type": "box_grid", "origin": f"r{r + 1}c{c + 1}", "box": [3, 3], "count": [3, 3]} for r, c in origins]
    diag = {"type": "region", "kind": "diagonal", "cells": [f"r{i + 1}c{i + 1}" for i in range(9)]}
    doc = dict(spec(), board={"rows": 21, "cols": 21}, rules=grids + [diag], givens={"grids": [30, 25, [0, 40], 20, 0]})
    g = SF.spec_to_gen(doc)
    assert g["layout"] == "samurai" and g["locked"] == [diag] and g["grid_givens"][2] == [0, 40]
    back = SF.spec_from_gen(g)
    assert back["board"] == {"rows": 21, "cols": 21} and diag in back["rules"] and back["givens"]["grids"][0] == 30
    b = GA.board_of(GA.Spec.from_any(g))
    assert b.N == 369 and len(b.grid_cells) == 5 and b.extra_json["regions"][0]["kind"] == "diag"
    for bad in (
        dict(doc, rules=grids + [{"type": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}]),  # a locked rule it can't fill
        dict(doc, rules=grids[:4]),  # origins of no named layout
        dict(doc, board={"rows": 21, "cols": 22}),  # not the layout's extent
    ):
        with pytest.raises(pencilmark.NotSupportedError):
            SF.spec_to_gen(bad)


def test_layout_generation():
    """a butterfly fills its 12 x 12 bounding box, so its numbers string is read row by row: the generator writes it so
    (written in the layout's cell order, every candidate came back not unique); a twodoku has gaps"""
    from pencilmark import puzzle_json as PJ

    for layout in ("butterfly", "twodoku"):
        origins = PJ._layouts()[layout]
        rows, cols = max(r for r, _ in origins) + 9, max(c for _, c in origins) + 9
        grids = [
            {"type": "box_grid", "origin": f"r{r + 1}c{c + 1}", "box": [3, 3], "count": [3, 3]} for r, c in origins
        ]
        r = run(dict(spec(), board={"rows": rows, "cols": cols}, rules=grids, limits={"time": 60, "seed": 1}))
        assert r["info"]["givens"] == sum(1 for v in r["puzzle"]["givens"] if v)
        # the card is the one rate() gives the returned file: the generator numbers layout cells as the reader does
        # (row by row) and the refutation profile no longer falls to 0 when a capped search gave up (2026-11-01:
        # a butterfly killer's card said 7.9, rate() 8.9)
        card = pencilmark.rate(r["puzzle"])
        assert (r["card"]["difficulty"], r["card"]["band"]) == (card["difficulty"], card["band"])
        assert PJ.from_json({"layout": layout}).coords == pencilmark.api._load(r["puzzle"]).coords


@pytest.mark.slow  # about 20 s
def test_more_line_kinds():
    """slow thermos, entropic, modular and parity lines are placed true in the solution; entropic lines need three
    digit groups (no 4 x 4)"""
    from pencilmark.gen import elements as EL

    for kind in ("slow_thermo", "entropic", "modular", "parity"):
        r = run(spec(6, rules=[{"type": "line", "kind": kind, "count": [2, None]}], seed=1, time_limit=60))
        lines = [x for x in r["puzzle"]["rules"] if x["type"] == "line" and x["kind"] == kind]
        assert len(lines) >= 2
        sol, cid = r["puzzle"]["solution"], lambda n: (int(n[1]) - 1) * 6 + int(n[3]) - 1
        for x in lines:
            ds = [sol[cid(c)] for c in x["cells"]]
            if kind == "slow_thermo":
                assert ds == sorted(ds)
            elif kind == "parity":
                assert all(a % 2 != b % 2 for a, b in zip(ds, ds[1:]))
            else:
                cls = [EL.digit_third(d, 6) if kind == "entropic" else d % 3 for d in ds]
                assert all(len(set(cls[i : i + 3])) == len(cls[i : i + 3]) for i in range(len(cls) - 1))
    with pytest.raises(GenerationFailed, match="entropic"):
        pencilmark.generate(spec(4, rules=[{"type": "line", "kind": "entropic", "count": 1}], seed=1, time_limit=5))


@pytest.mark.slow  # about 40 s
def test_whole_line_kinds():
    """palindrome, zipper, region-sum, lockout and double-arrow lines are true in the solution and come back as the
    kind requested (a double arrow is 5+ cells: a shorter one is a zipper and is written as one)"""
    from pencilmark.gen import elements as EL
    from pencilmark.gen.board import Board

    b = Board(6)
    for kind in ("palindrome", "zipper", "region_sum", "lockout", "double_arrow"):
        r = run(spec(6, rules=[{"type": "line", "kind": kind, "count": [2, None]}], seed=1, time_limit=60))
        lines = [x for x in r["puzzle"]["rules"] if x["type"] == "line" and x["kind"] == kind]
        assert len(lines) >= 2, kind
        sol = r["puzzle"]["solution"]
        for x in lines:
            cells = [(int(c[1]) - 1) * 6 + int(c[3]) - 1 for c in x["cells"]]
            assert EL.line_holds(b, kind, cells, [sol[c] for c in cells]), (kind, x)
    with pytest.raises(GenerationFailed, match="double_arrow"):
        pencilmark.generate(spec(6, rules=[{"type": "line", "kind": "double_arrow", "count": 1, "length": 4}], seed=1))


@pytest.mark.slow  # about 25 s
def test_outside_clues():
    """sandwich, skyscraper and little killer clues are true in the solution, read from the side the file names;
    layouts refuse them (the little killer on 4 x 4: a 6 x 6 one digs for about a minute)"""
    from pencilmark.gen import elements as EL

    for t, D in (({"type": "sandwich"}, 6), ({"type": "skyscraper"}, 6), ({"type": "sum", "kind": "little_killer"}, 4)):
        # 120 s: one attempt took about 20 s on Linux and ran out of 60 s on the Windows runner (about 2-3x slower)
        r = run(spec(D, rules=[dict(t, count=[2, None])], seed=1, time_limit=120), budget=300)
        clues = [x for x in r["puzzle"]["rules"] if x["type"] == t["type"] and x.get("kind") == t.get("kind")]
        assert len(clues) >= 2, t
        sol = r["puzzle"]["solution"]
        for x in clues:
            ds = [sol[(int(c[1]) - 1) * D + int(c[3]) - 1] for c in x["cells"]]
            kind = t.get("kind") or t["type"]
            assert EL.outside_value(kind, ds) == x.get("sum", x.get("value")), x
    origins = [(0, 0), (6, 6)]  # twodoku
    grids = [{"type": "box_grid", "origin": f"r{r + 1}c{c + 1}", "box": [3, 3], "count": [3, 3]} for r, c in origins]
    with pytest.raises(GenerationFailed, match="outside clues"):
        pencilmark.generate(
            dict(spec(), board={"rows": 15, "cols": 15}, rules=grids + [{"type": "sandwich", "count": 2}])
        )


@pytest.mark.slow  # about 10 s
def test_corner_clues():
    """quadruples (corner circles) and mathrax clues are true in the solution and are written as `contains` and
    `corner` rules (the generator's pair tables per diagonal read back as one mathrax corner)"""
    from pencilmark.gen import elements as EL

    for t in ({"type": "quadruple"}, {"type": "corner", "kind": "mathrax"}):
        r = run(spec(6, rules=[dict(t, count=[2, None])], seed=1, time_limit=60))
        clues = [x for x in r["puzzle"]["rules"] if x["type"] == t["type"]]
        assert len(clues) >= 2 and not [x for x in r["puzzle"]["rules"] if x["type"] == "table"], t
        sol = r["puzzle"]["solution"]
        for x in clues:
            ds = [sol[(int(c[1]) - 1) * 6 + int(c[3]) - 1] for c in x["cells"]]
            if t["type"] == "contains":
                assert EL.corner_holds("quadruple", ds, x["digits"])
            else:
                assert (x["op"], x.get("value")) in EL.mathrax_clues(ds)


def test_locked_nonconsecutive():
    """a locked nonconsecutive rule: the grid fill respects pair rules (no relabelling), every result carries it"""
    r = run(spec(6, rules=[{"type": "neighbours", "kind": "nonconsecutive"}], seed=1, time_limit=30))
    assert {"type": "neighbours", "kind": "nonconsecutive"} in r["puzzle"]["rules"]
    sol = r["puzzle"]["solution"]
    pairs = [(i, i + 1) for i in range(36) if i % 6 < 5] + [(i, i + 6) for i in range(30)]
    assert all(abs(sol[i] - sol[j]) != 1 for i, j in pairs)
    # any op on neighbours: no orthogonal pair sums to 7, written back as the negative rule of the matching edge
    rule = {"type": "neighbours", "op": "not_sum", "sum": 7, "where": "orthogonal"}
    r = run(spec(6, rules=[rule], seed=1, time_limit=30))
    sol = r["puzzle"]["solution"]
    assert all(sol[i] + sol[j] != 7 for i, j in pairs)


def test_untargeted_request_warns():
    """no band / difficulty target: the broadest search, with a hint to aim it (user, 2026-11-02)"""
    r = run(spec(4, seed=1, time_limit=10))
    assert "where.band" in r["info"]["warnings"][0]
    r = run(spec(4, where={"band": "Very Easy"}, seed=1, time_limit=10))
    assert "warnings" not in r["info"]


def test_fingerprints_asked_for_in_the_spec():
    """a fingerprint / generated_from key in the spec's meta is filled in on the puzzle; without it, neither"""
    doc = {
        "format": "pencilmark-spec",
        "format_version": 1,
        "board": {"rows": 6, "cols": 6},
        "digits": 6,
        "rules": [{"type": "box_grid", "box": [2, 3], "count": [3, 2]}],
        "where": {"band": "Easy"},
        "limits": {"seed": 1},
        "meta": {"title": "t", "fingerprint": True, "generated_from": True},
    }
    meta = run(doc)["puzzle"]["meta"]
    assert meta["fingerprint"] == pencilmark.fingerprint(run(doc)["puzzle"]) and re.fullmatch(
        r"[0-9a-f]{64}", meta["generated_from"]
    )
    assert meta["fingerprint"] != meta["generated_from"]


def test_quality_is_opt_in():
    """no quality or {} = no checks ({} is dropped, same fingerprint); a preset turns on its checks; without a preset
    only the checks named run (generator-spec.md 4.1)"""
    from pencilmark import spec_format as SF
    from pencilmark.publish_flags import PRESETS, QUALITY, quality_limits, spec_quality

    base = {"format": "pencilmark-spec", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4,
            "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}]}  # fmt: skip
    assert SF.spec_to_gen(base)["quality"] is None and SF.spec_to_gen(dict(base, quality={}))["quality"] is None
    assert SF.spec_fingerprint(base) == SF.spec_fingerprint(dict(base, quality={}))
    assert spec_quality(None) is None and spec_quality({}) is None
    on = lambda q: {k for k, v in quality_limits(spec_quality(q)).items() if v["severity"] != "off"}  # noqa: E731
    assert on({"preset": "standard"}) == set(PRESETS["standard"])
    assert on({"preset": "standard", "trivial": {"severity": "off"}}) == set(PRESETS["standard"]) - {"trivial"}
    assert on({"trial": {"severity": "reject"}}) == {"trial"} and on({"trivial": {"limit": 0.5}}) == {"trivial"}
    assert set(PRESETS["standard"]) <= set(QUALITY)


def test_meta_requests():
    """the spec's meta is copied; title / subtitle templates, type (name / list scheme), variants, rules_text and the
    fingerprints are filled only when asked (generator-spec.md 5.1); a bad request fails before the run"""
    from pencilmark.errors import NotSupportedError
    from pencilmark.gen.api import meta_requests

    doc = {"format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4,
           "givens": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
           "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]},
                     {"type": "cage", "sum": 3, "cells": ["r2c1", "r2c2"]},
                     {"type": "line", "kind": "thermo", "cells": ["r3c1", "r3c2", "r3c3"]}]}  # fmt: skip
    res = {"puzzle": doc, "spec_fingerprint": "f" * 64, "band": "Easy", "difficulty": 4.2, "time": 3.1, "seed": 7}
    assert meta_requests({"author": "A", "title": "Plain"}, res) == {"author": "A", "title": "Plain"}
    m = meta_requests(
        {"title": "{type} #{seed}", "subtitle": "{type:list}, {band} {difficulty} ({size}, {givens} given, {{x}})",
         "type": {"scheme": "list"}, "variants": True, "rules_text": True, "generated_from": True},
        res,
    )  # fmt: skip
    assert m["title"] == "Tiny Variant Sudoku #7" and m["type"] == "Tiny Killer Thermo Sudoku"
    assert m["subtitle"] == "Tiny Killer Thermo Sudoku, Easy 4.2 (4x4, 1 given, {x})"
    assert m["variants"] == ["killer", "thermo"] and m["rules_text"].startswith("Tiny Sudoku: ")
    assert m["generated_from"] == "f" * 64
    assert meta_requests({"type": True, "rules_text": "Mine."}, res) == {
        "type": "Tiny Variant Sudoku",
        "rules_text": "Mine.",
    }
    for bad in ({"title": "{nope}"}, {"type": {"scheme": "fancy"}}, {"title": 3}):
        with pytest.raises(NotSupportedError):
            meta_requests(bad, None)


def test_typical_difficulty_aims_where_published_puzzles_lie():
    """difficulty "typical" with a band: a window drawn from the band's spread (publish_flags.AIM), the same for the
    same seed, reported as info.aimed_at; classic Very Easy within 2.7-3.9 (+-0.4); opt in: a band alone digs deepest"""
    from pencilmark.gen.api import Spec, band_aim

    wins = [band_aim(Spec(size=9, target_band="Very Easy", seed=k), "classic") for k in range(1, 30)]
    assert all(2.3 <= lo < hi <= 4.3 for lo, hi in wins) and len(set(wins)) > 5
    assert band_aim(Spec(size=9, target_band="Very Easy", seed=3), "classic") == wins[2]
    assert band_aim(Spec(size=6, target_band="Very Easy", seed=3), "classic") is None
    s = spec(9, where={"band": "Very Easy", "difficulty": "typical"}, seed=2, time_limit=60)
    s["quality"] = {"preset": "standard"}
    r = run(s)
    lo, hi = r["info"]["aimed_at"]
    assert lo <= r["card"]["difficulty"] <= hi and r["card"]["band"] == "Very Easy"
    assert "aimed_at" not in run(spec(9, where={"band": "Very Easy", "difficulty": [3.5, 4.5]}, seed=2))["info"]
    deep = run(spec(9, where={"band": "Very Easy"}, seed=2))  # not asked for: the deepest dig
    assert "aimed_at" not in deep["info"] and deep["info"]["givens"] < r["info"]["givens"]


def test_no_seed_draws_a_fresh_one():
    """without limits.seed each run draws its own seed (info.seed), and that seed reproduces the puzzle"""
    s = spec(4)
    a, b = run(s), run(s)
    assert a["info"]["seed"] != b["info"]["seed"]
    again = run(dict(s, limits=dict(s["limits"], seed=a["info"]["seed"])))
    assert again["puzzle"]["givens"] == a["puzzle"]["givens"]


def test_aim_relaxes_at_half_time(monkeypatch):
    """an aim nothing can meet does not fail the request: after half the time any difficulty in the band will do"""
    from pencilmark.gen import api as GA

    monkeypatch.setattr(GA, "band_aim", lambda s, mode: (0.0, 0.1))  # no puzzle is this easy
    s = spec(9, where={"band": "Very Easy", "difficulty": "typical"}, seed=2, time_limit=8)
    r = run(s)
    assert r["info"]["aim_relaxed"] and r["card"]["band"] == "Very Easy"
