"""Generator tests: pencilmark.generate takes a sudoku-spec request (docs/SPEC.md). Each case runs in a few seconds."""
import time

import pytest

import pencilmark
from pencilmark import cpsat_verify as V
from pencilmark.gen import GenerationFailed
from pencilmark.gen import api as GA


def spec(D=9, box=None, where=None, rules=(), givens=None, symmetry=None, seed=None, time_limit=300):
    """a sudoku-spec for a D x D board with standard boxes plus the given templates / targets"""
    box = box or {4: [2, 2], 6: [2, 3], 9: [3, 3]}[D]
    d = {"format": "sudoku-spec", "format_version": 1, "board": {"rows": D, "cols": D}, "digits": D,
         "rules": [{"type": "box_grid", "origin": "r1c1", "box": box}, *rules]}
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


def run(doc, budget=150):          # a runaway guard; CI on Windows is about 2x slower than Linux
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
    r = run(spec(9, where={"difficulty": [2, 4]}, seed=1))
    assert 2 <= r["card"]["difficulty"] <= 4


def test_kropki_6x6_min():
    r = run(spec(6, rules=[{"type": "edge", "kind": "kropki", "count": "min"}], seed=1))
    rules = r["puzzle"]["rules"]
    assert any(x["type"] == "edge" and x["kind"] == "kropki" for x in rules) and set(r["puzzle"]["givens"]) == {0}


def test_deterministic():
    a = pencilmark.generate(spec(6, seed=7, time_limit=30))
    b = pencilmark.generate(spec(6, seed=7, time_limit=30))
    assert a["puzzle"] == b["puzzle"]


def test_only_specs():
    """the generator takes sudoku-spec requests only; unsupported parts are refused, not ignored"""
    with pytest.raises(TypeError):
        pencilmark.generate({"size": 9, "target_band": "Hard"})
    with pytest.raises(pencilmark.NotSupportedError):
        pencilmark.generate(dict(spec(9), limits={"results": 3}))


def test_feasibility_fails_fast():
    t = time.time()
    with pytest.raises(GenerationFailed, match="information budget"):
        pencilmark.generate(spec(9, givens={"count": 0}, rules=[{"type": "edge", "kind": "kropki", "count": [5, None]}],
                                 where={"elements": {"max": 5}}))
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
    probs = GA.feasibility(GA.Spec.from_any({"size": 9, "max_givens": 0,
                                             "elements": {"kropki_black": [0, 2], "kropki_white": [0, 3]}}))
    assert any("information budget" in p for p in probs), probs


def test_element_classes_and_ranges():
    """per-class counts: 6 givens, exactly 2 black kropki, any number of white (the dense-seeding path)"""
    r = run(spec(9, where={"band": "Easy"}, givens={"count": 6}, seed=1,
                 rules=[{"type": "edge", "kind": "kropki", "color": "black", "count": 2},
                        {"type": "edge", "kind": "kropki", "color": "white", "count": "auto"}]))
    els = r["info"]["elements"]
    assert r["info"]["givens"] == 6 and els.get("kropki_black") == 2 and els.get("kropki_white", 0) >= 1, r["info"]


def test_spec_examples():
    """SPEC.md's example and docs/examples/specs run (spec_to_gen accepts them); reserved/ examples are refused"""
    import json, re
    from pathlib import Path
    from pencilmark import spec_format as SF
    docs = Path(__file__).resolve().parents[1] / "docs"
    text = (docs / "SPEC.md").read_text(encoding="utf-8")
    example = json.loads(re.search(r"```json\n(.*?)```", text, re.S).group(1))
    SF.spec_to_gen(example)
    for f in sorted((docs / "examples" / "specs").glob("*.json")):
        SF.spec_to_gen(json.loads(f.read_text(encoding="utf-8")))
    for f in sorted((docs / "examples" / "specs" / "reserved").glob("*.json")):
        with pytest.raises((pencilmark.NotSupportedError, pencilmark.FormatError)):
            SF.spec_to_gen(json.loads(f.read_text(encoding="utf-8")))
