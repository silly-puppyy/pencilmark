"""Public API smoke tests and reference cards."""
import json

import pytest

import pencilmark
from conftest import CLASSIC

CLASSIC_SOLUTION = None


def test_classic_card():
    card = pencilmark.rate(CLASSIC)
    assert card["format"] == "sudoku-grade"
    assert (card["band"], card["band_index"], card["difficulty"], card["time"], card["time_p80"]) == ("Medium", 2, 5.9, 10.7, 16.4)
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
    assert st[0]["n"] == 1 and st[0]["explanation"]
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


def test_unknown_band():
    easter_monster = "1.......2.9.4...5...6...7...5.9.3.......7.......85..4.7.....6...3...9.8...2.....1"
    card = pencilmark.rate(easter_monster, max_seconds=30)
    assert card["band"] == "Unknown" and card["band_index"] is None and card["contains_complete"] is False


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
    assert exp["format_version"] == 1 and exp["rules"] == [{"type": "subgrid", "size": 9, "box": [3, 3], "origin": "r1c1"}]
    again = pencilmark.to_export(exp, describe=False)       # metadata already in the input is kept
    assert again["meta"] == exp["meta"] and again["givens"] == exp["givens"]
    filled = pencilmark.to_export(exp)                      # an empty meta.type / rules_text is filled, nothing overwritten
    assert filled["meta"]["type"] == "Sudoku" and filled["meta"]["author"] == "someone"
    boxes = [[(br + i) * 9 + bc + j for i in range(3) for j in range(3)] for br in (0, 3, 6) for bc in (0, 3, 6)]
    legacy = {"format": "sudoku-puzzle/2", "grid": exp["grid"], "digits": 9, "givens": exp["givens"], "boxes": boxes,
              "title": "T", "source": {"site": "example.org", "id": "7"}}      # an older file: top-level metadata
    assert pencilmark.to_export(legacy, describe=False)["meta"] == {"title": "T", "source": "example.org", "id": "7"}
    assert pencilmark.rate(exp) == pencilmark.rate(legacy) == pencilmark.rate(CLASSIC)


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
