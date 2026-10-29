"""Generator tests (pencilmark.gen). Each case runs in a few seconds."""
import time

import pytest

from pencilmark import puzzle_json as PJ, cpsat_verify as V
from pencilmark.gen import generate, feasibility, uniquify, is_unique, GenerationFailed, BANDS


def unique(puzzle):
    p = PJ.from_json(puzzle)
    p.finalize()
    sols = V.solutions(p, limit=2, time_limit=30)
    assert sols is not None, "uniqueness undecided"
    return len(sols) == 1 and "".join(PJ._sym(v) for v in sols[0]) == puzzle["solution"]


def run(spec, budget=150):          # a runaway guard; CI on Windows is about 2x slower than Linux
    t = time.time()
    r = generate(spec)
    assert time.time() - t < budget
    assert unique(r["puzzle"])
    assert r["info"]["unique_verified"] is True
    return r


def test_classic_4x4():
    r = run({"size": 4, "seed": 1, "time_limit": 300})
    assert r["puzzle"]["digits"] == 4 and r["card"]["band"] in BANDS


def test_classic_6x6_symmetric():
    r = run({"size": 6, "symmetry": "rot180", "seed": 2, "time_limit": 300})
    nums = r["puzzle"]["numbers"]
    assert all((nums[i] == ".") == (nums[35 - i] == ".") for i in range(36))


def test_classic_9x9_difficulty_range():
    r = run({"size": 9, "target_difficulty": [2, 4], "seed": 1, "time_limit": 300})
    assert 2 <= r["card"]["difficulty"] <= 4


def test_kropki_6x6_min():
    r = run({"size": 6, "elements": {"kropki": "min"}, "seed": 1, "time_limit": 300})
    rules = r["puzzle"]["rules"]
    assert rules and all(x["type"] == "kropki" for x in rules) and set(r["puzzle"]["numbers"]) == {"."}


def test_deterministic():
    a = generate({"size": 6, "seed": 7, "time_limit": 30})
    b = generate({"size": 6, "seed": 7, "time_limit": 30})
    assert a["puzzle"] == b["puzzle"]


def test_feasibility_fails_fast():
    t = time.time()
    with pytest.raises(GenerationFailed, match="information budget"):
        generate({"size": 9, "elements": {"kropki": 5}, "max_givens": 0, "max_elements": 5})
    with pytest.raises(GenerationFailed, match="at least 17 givens"):
        generate({"size": 9, "max_givens": 12})
    assert any("Hard technique" in p for p in feasibility({"size": 9, "target_band": "Easy", "require": ["SWF"]}))
    assert any("unknown element kind" in p for p in feasibility({"elements": {"sandwich": 2}}))
    assert time.time() - t < 2


def test_uniquify():
    d = {"v": 1, "digits": 6, "box": "2x3", "numbers": "." * 36}
    out = uniquify(d, seed=1)
    assert is_unique(out) and sum(ch != "." for ch in out["numbers"]) >= 8


def test_capped_classes_budget():
    """when every element class has a maximum, the caps bound the information budget"""
    from pencilmark.gen import api as GA
    probs = GA.feasibility(GA.Spec.from_any({"size": 9, "max_givens": 0,
                                             "elements": {"kropki_black": [0, 2], "kropki_white": [0, 3]}}))
    assert any("information budget" in p for p in probs), probs


def test_element_classes_and_ranges():
    """per-class counts: 6 givens, exactly 2 black kropki, any number of white (the dense-seeding path)"""
    r = run({"size": 9, "target_band": "Easy", "min_givens": 6, "max_givens": 6,
             "elements": {"kropki_black": [2, 2], "kropki_white": "auto"}, "seed": 1, "time_limit": 300})
    els = r["info"]["elements"]
    assert r["info"]["givens"] == 6 and els.get("kropki_black") == 2 and els.get("kropki_white", 0) >= 1, r["info"]
    from pencilmark import spec_format as SF
    doc = SF.spec_from_gen({"size": 9, "elements": {"kropki_black": [2, 2], "kropki_white": "auto"}})
    assert {"type": "edge", "kind": "kropki", "color": "black", "count": 2} in doc["rules"]
    assert SF.spec_to_gen(doc)["elements"] == {"kropki_black": [2, 2], "kropki_white": 0}
