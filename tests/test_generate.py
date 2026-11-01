"""Generator tests: pencilmark.generate takes a sudoku-spec request (docs/formats/generator-spec.md). Each case runs in a few seconds."""

import json
import os
import subprocess
import sys
import time

import pytest

import pencilmark
from pencilmark import cpsat_verify as V
from pencilmark.gen import GenerationFailed
from pencilmark.gen import api as GA


def spec(D=9, box=None, where=None, rules=(), givens=None, symmetry=None, seed=None, time_limit=300):
    """a sudoku-spec for a D x D board with standard boxes plus the given templates / targets"""
    box = box or {4: [2, 2], 6: [2, 3], 9: [3, 3]}[D]
    d = {
        "format": "sudoku-spec",
        "format_version": 1,
        "board": {"rows": D, "cols": D},
        "digits": D,
        "rules": [{"type": "box_grid", "origin": "r1c1", "box": box}, *rules],
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
    p = pencilmark.load(puzzle)
    sols = V.solutions(p, limit=2, time_limit=30)
    assert sols is not None, "uniqueness undecided"
    return len(sols) == 1 and list(sols[0]) == [v for v in puzzle["solution"] if v is not None]


def run(doc, budget=150):  # a runaway guard; CI on Windows is about 2x slower than Linux
    t = time.time()
    r = pencilmark.generate(doc)
    assert time.time() - t < budget
    assert r["puzzle"]["format"] == "sudoku-puzzle" and r["puzzle"]["meta"]["generated_from"].startswith("sha256:")
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
    """the generator takes sudoku-spec requests only; unsupported parts are refused, not ignored"""
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
    assert any("unknown element kind" in p for p in GA.feasibility({"elements": {"sandwich": 2}}))
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
            "format": "sudoku-spec",
            "format_version": 1,
            "board": {"rows": 9, "cols": 9},
            "digits": 9,
            "rules": [
                {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
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
