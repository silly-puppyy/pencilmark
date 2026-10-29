"""Public API smoke tests and reference cards."""
import json

import pytest

import pencilmark
from conftest import CLASSIC

CLASSIC_SOLUTION = None


def test_classic_card():
    card = pencilmark.rate(CLASSIC)
    assert card["format"] == "sudoku-grade"
    assert (card["band"], card["band_index"], card["difficulty"], card["time"]) == ("Medium", 2, 5.9, 10.7)
    assert "time_p80" not in card and "issues" not in card and "reject" not in card     # publishing checks on request
    t = pencilmark.rate(CLASSIC, fields=["time", "time_p20", "time_p80", "time_mean"])
    assert t["time_p20"] < t["time"] < t["time_mean"] < t["time_p80"], t
    assert abs(t["time_p80"] / t["time"] - 1.94) < 0.05, t     # classic sigma_players 0.79
    d = pencilmark.rate(CLASSIC, fields=["time", "time_dist", "time_p50"])
    assert d["time_dist"]["type"] == "lognormal" and "median" not in d["time_dist"] and d["time"] == d["time_p50"], d
    assert d["time_dist"]["sigma_players"] == 0.79 and d["time_dist"]["sigma_model"] == 0.33, d
    chips = [c["chip"] for c in card["contains"] if c["band"] > 0]
    assert chips == ["NPR/PPR/HPR", "XWG/KTE/SCL"]


def test_deterministic_and_input_forms(tmp_path):
    a = pencilmark.rate(CLASSIC)
    assert pencilmark.rate(CLASSIC) == a
    exp = pencilmark.to_export(CLASSIC, title="t")
    assert exp["format"] == "sudoku-puzzle" and exp["givens"][4] == 4 and exp["givens"][0] == 0
    assert exp["meta"]["title"] == "t" and exp["meta"]["type"] == "Sudoku"      # empty type / rules_text filled by describe
    assert pencilmark.rate(exp) == a
    assert pencilmark.rate(json.dumps({"numbers": CLASSIC})) == a
    f = tmp_path / "p.json"
    f.write_text(json.dumps(exp), encoding="utf-8")
    assert pencilmark.rate(str(f)) == a
    assert pencilmark.rate({"puzzle": exp}) == a


def test_steps_and_se():
    card = pencilmark.rate(CLASSIC, steps=True, se=True)
    st = card["steps"]
    assert st[0]["n"] == 1 and set(st[0]["explanation"]) == {"short", "teach"}
    filled = sum(1 for s in st if "placement" in s)
    assert filled == 81 - sum(ch != "." for ch in CLASSIC)
    assert card["se"]["scale"] == "classic" and card["se"]["er"] >= card["se"]["ep"]


def test_solve():
    sol = pencilmark.solve(CLASSIC)
    assert len(sol) == 81
    assert all(sol[i] == int(ch) for i, ch in enumerate(CLASSIC) if ch != ".")
    rows = [sol[r * 9:(r + 1) * 9] for r in range(9)]
    assert all(sorted(r) == list(range(1, 10)) for r in rows)
    with pytest.raises(pencilmark.NotUnique):
        pencilmark.solve("." * 80 + "1")
    with pytest.raises(pencilmark.NoSolution):
        pencilmark.solve("11" + "." * 79)


EASTER_MONSTER = "1.......2.9.4...5...6...7...5.9.3.......7.......85..4.7.....6...3...9.8...2.....1"


def test_no_guessing_by_default():
    # guessing is off by default: where no technique applies the engine proves by full search (Extreme), never Unknown
    card = pencilmark.rate(EASTER_MONSTER, fields=["band", "band_index", "difficulty"])     # ~40 s: no technique list
    assert card["band"] == "Extreme" and card["band_index"] == 5 and card["difficulty"] is not None


def test_unknown_band_when_guessing():
    card = pencilmark.rate(EASTER_MONSTER, max_seconds=30, allow_guessing=True)
    assert card["band"] == "Unknown" and card["band_index"] is None and card["stopped_at_step"] >= 1


def test_variants_reference_cards(variants):
    for v in variants:
        card = pencilmark.rate(v["puzzle"])
        assert card == v["card"], v["name"]


def test_rate_many_keeps_order(variants):
    puzzles = [CLASSIC] + [v["puzzle"] for v in variants[:2]] + ["not a puzzle"]
    cards = pencilmark.rate_many(puzzles, jobs=2)
    assert cards[0] == pencilmark.rate(CLASSIC)
    assert [c.get("band") for c in cards[1:3]] == [v["card"]["band"] for v in variants[:2]]
    assert "error" in cards[3]


def test_solve_matches_cpsat(variants):
    pytest.importorskip("ortools")
    from pencilmark import cpsat_verify as V
    for pz in [CLASSIC] + [v["puzzle"] for v in variants]:
        p = pencilmark.load(pz)
        assert V.cpsat_solutions(p, limit=2) == [pencilmark.solve(pz)]


NO_ORTOOLS = r'''
import json, sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name == "ortools" or name.startswith("ortools."):
            raise ImportError("blocked for the test")
sys.meta_path.insert(0, Block())
import pencilmark
from pencilmark import cpsat_verify as V
assert not V.have_ortools()
cards = [pencilmark.rate(p) for p in json.loads(sys.stdin.read())]
print(json.dumps(cards))
'''


def test_rate_without_ortools(variants):
    """the core install has no OR-Tools: rate() must give the same cards without it."""
    import subprocess
    import sys
    puzzles = [CLASSIC] + [v["puzzle"] for v in variants]
    r = subprocess.run([sys.executable, "-c", NO_ORTOOLS], input=json.dumps(puzzles), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    assert r.returncode == 0, r.stderr
    cards = json.loads(r.stdout)
    assert cards[0] == pencilmark.rate(CLASSIC)
    assert cards[1:] == [v["card"] for v in variants]


def test_meta_kept_and_ignored_for_rating():
    exp = pencilmark.to_export(CLASSIC, meta={"author": "someone", "x-custom": 1}, title="T", date="2026-10-25", describe=False)
    assert exp["meta"] == {"title": "T", "author": "someone", "date": "2026-10-25", "x-custom": 1}
    assert exp["format_version"] == 1 and exp["rules"] == [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}]
    again = pencilmark.to_export(exp, describe=False)       # metadata already in the input is kept
    assert again["meta"] == exp["meta"] and again["givens"] == exp["givens"]
    filled = pencilmark.to_export(exp)                      # an empty meta.type / rules_text is filled, nothing overwritten
    assert filled["meta"]["type"] == "Sudoku" and filled["meta"]["author"] == "someone"
    assert pencilmark.rate(exp) == pencilmark.rate(CLASSIC)


def test_whole_grid_pair_rule():
    from pencilmark import puzzle_json as PJ
    pj = {"numbers": CLASSIC, "rules": [{"type": "nonconsecutive"}]}
    p = PJ.from_json(pj)
    p.finalize()
    out = PJ.to_json(p)
    assert {"type": "nonconsecutive"} in out["rules"] or any(r.get("where") == "orthogonal" for r in out["rules"])
    q = PJ.from_json(out)
    q.finalize()
    assert sorted(map(tuple, p.relations)) == sorted(map(tuple, q.relations))


def test_rate_needs_one_solution():
    import pytest
    with pytest.raises(pencilmark.NotUnique):
        pencilmark.rate("." * 81)
    assert "error" in pencilmark.rate_many(["." * 81])[0]


def test_max_seconds_unknown_when_time_runs_out():
    """a card that runs out of max_seconds in the difficulty route: band Unknown, difficulty null, completed false, on time"""
    import time
    t = time.time()
    card = pencilmark.rate(EASTER_MONSTER, max_seconds=5)
    assert time.time() - t < 8, time.time() - t
    assert card["band"] == "Unknown" and card["difficulty"] is None and card["completed"] is False, card


def test_max_seconds_bounds_the_call():
    """max_seconds bounds the whole rate() call; a card that ran out of time says so (completed false)"""
    import time
    t = time.time()
    c = pencilmark.rate(CLASSIC, max_seconds=30)
    assert c["completed"] is True and c["band"] != "Unknown" and time.time() - t < 30, c
    assert "completed" not in pencilmark.rate(CLASSIC)         # no limit: grading always finishes, the field is left out


def test_timing_fields():
    c = pencilmark.rate(CLASSIC, fields=["difficulty", "elapsed"])
    assert isinstance(c["elapsed"], float) and 0 <= c["elapsed"] < 30, c
    assert "elapsed" not in pencilmark.rate(CLASSIC)                     # optional
    s = pencilmark.solve(CLASSIC, info=True)
    assert s["solution"] == pencilmark.solve(CLASSIC) and s["seconds"] >= 0, s


def test_text_grids_and_pencilmarks():
    """INTEROP.md: text grids with separators, trailing comments, pencil-mark grids, 729-character candidate strings"""
    s = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."
    grid = pencilmark.to_string(s, "grid")
    assert grid.count("\n") == 10 and "|" in grid
    framed = "*-----------*\n" + "\n".join("|" + "|".join(s[r * 9 + c:r * 9 + c + 3] for c in (0, 3, 6)) + "|"
                                          + ("\n|---+---+---|" if r in (2, 5) else "") for r in range(9)) + "\n*-----------*"
    for text in (grid, framed, s + "  # rated 5.9", s + ";5.9"):
        assert pencilmark.to_string(pencilmark.from_string(text)) == s, text
    assert pencilmark.rate(framed)["band"] == pencilmark.rate(s)["band"]
    d = pencilmark.from_string(" ".join(["5", "1234", "6789"] + ["123456789"] * 78))
    assert d["givens"][:3] == [5, 0, 0] and d["candidates"] == {"r1c2": [1, 2, 3, 4], "r1c3": [6, 7, 8, 9]}
    body = "".join("." * (i % 9) + str(i % 9 + 1) + "." * (8 - i % 9) if i % 2 == 0 else "123456789" for i in range(81))
    d = pencilmark.from_string(body)
    assert d["givens"][:4] == [1, 0, 3, 0] and "candidates" not in d
