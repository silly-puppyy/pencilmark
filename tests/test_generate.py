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


def run(spec, budget=60):
    t = time.time()
    r = generate(spec)
    assert time.time() - t < budget
    assert unique(r["puzzle"])
    assert r["info"]["unique_verified"] is True
    return r


def test_classic_4x4():
    r = run({"size": 4, "seed": 1, "time_limit": 30})
    assert r["puzzle"]["digits"] == 4 and r["card"]["band"] in BANDS


def test_classic_6x6_symmetric():
    r = run({"size": 6, "symmetry": "rot180", "seed": 2, "time_limit": 30})
    nums = r["puzzle"]["numbers"]
    assert all((nums[i] == ".") == (nums[35 - i] == ".") for i in range(36))


def test_classic_9x9_difficulty_range():
    r = run({"size": 9, "target_difficulty": [2, 4], "seed": 1, "time_limit": 50})
    assert 2 <= r["card"]["difficulty"] <= 4


def test_kropki_6x6_min():
    r = run({"size": 6, "elements": {"kropki": "min"}, "seed": 1, "time_limit": 50})
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
