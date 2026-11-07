"""Identity layer (params coloring, experiment): the Python mirror of the class state, the held-step accounting and
the two-color moves on a hand-made position."""

import json
from pathlib import Path

import pytest

import pencilmark
from pencilmark import api
from pencilmark import cbackend as CB
from pencilmark import solver as S

J, NEQ, USE = CB.AE_ID_JOIN, CB.AE_ID_NEQ, CB.AE_ID_USE


def test_id_state_mirror():
    vals = [0] * 81
    idc = [0] * 81
    CB.id_apply(idc, vals, [(NEQ, 5, 3)])  # one-member classes live through their difference
    assert idc[3] == 4 and idc[5] == 6 and idc[81:] == [4, 6]
    CB.id_apply(idc, vals, [(J, 9, 5)])  # a join keeps the difference, under the class's anchor
    assert idc[9] == 6 and idc[81:] == [4, 6]
    CB.id_apply(idc, vals, [(J, 1, 5)])  # a new first member renames the class and its difference
    assert idc[1] == idc[5] == idc[9] == 2 and idc[81:] == [2, 4]
    vals[3] = 7  # a placed one-member class lives on while its partner is open ...
    CB.id_apply(idc, vals, [])
    assert idc[3] == 4 and idc[81:] == [2, 4]
    for c in (1, 5, 9):  # ... and both go once everything is placed
        vals[c] = 2
    CB.id_apply(idc, vals, [])
    assert idc == [0] * 81


def test_id_held_accounting():
    steps = [
        (None, [], [(J, 10, 0)]),  # join 0 = 10, used by step 3
        (None, [], [(J, 30, 20)]),  # join 20 = 30, never used: held
        (None, [], [(NEQ, 40, 0)]),  # difference, used by step 4's trap
        (None, [(10, 5)], [(USE, 0, 0)]),  # propagation in class 0
        (None, [(50, 1)], [(USE, 0, 0), (USE, 40, 0)]),  # sees both colors
    ]
    assert CB.id_held(81, {}, steps) == [False, True, False, False, False]


def test_class_pair_and_trap_listed():
    p = pencilmark.api._load("." * 81)
    P = dict(api._params("human"), colouring=1)
    on = {S.CLASS_PAIR, S.CLASS_TRAP}
    off = set(S.TECH_NAMES) - on
    full = (1 << 9) - 1
    cand = [full] * 81
    cand[0] = cand[1] = (1 << 2) | (1 << 5)  # r1c1, r1c2: 3 / 6
    ms = CB.state_moves(p, P, cand=cand, disabled=off, labels=(None, None, [0] * 81))
    assert [m.get("idfx") for m in ms if m["tech"] == S.CLASS_PAIR] == [[(NEQ, 1, 0)]]
    idc = [1, 2] + [0] * 79 + [1, 2]  # after it: two colors
    ms = CB.state_moves(p, P, cand=cand, disabled=off, labels=(None, None, idc))
    trap = [m for m in ms if m["tech"] == S.CLASS_TRAP]
    assert len(trap) == 1 and {c for c, _ in trap[0]["elim"]} == set(range(2, 9)) | {9, 10, 11, 18, 19, 20}
    assert {d for _, d in trap[0]["elim"]} == {3, 6}


def test_colour_legend_kept_for_the_solve():
    """coloring sub-steps: each color class keeps one color name for the whole solve, with a legend (its possible
    digits) the first time; a cell joining an existing color says so, without a new legend"""
    from pencilmark import band_path as BP

    p = pencilmark.api._load("." * 81)
    vals, cand, idc, colours = [0] * 81, [(1 << 9) - 1] * 81, [0] * 81, {}
    cand[0] = cand[30] = cand[40] = 0b110000  # 5 / 6
    ex = {"short": "r1c1 and r4c4 must hold the same digit"}
    out = BP._class_substeps(p, {"idfx": [(J, 30, 0)], "elims": [], "place": None}, ex, idc, vals, cand, colours)
    assert out[0]["text"].startswith("r1c1 and r4c4") and out[0]["legend"] == {"orange": "an unknown digit (5 or 6)"}
    assert {a["cell"] for a in out[0]["annotations"]} == {"r1c1", "r4c4"}
    assert out[-1]["text"] == "So r4c4 and r1c1 are orange."
    out = BP._class_substeps(p, {"idfx": [(J, 40, 0)], "elims": [], "place": None}, ex, idc, vals, cand, colours)
    assert "legend" not in out[0] and out[-1]["text"] == "So r5c5 joins orange."
    out = BP._class_substeps(p, {"idfx": [(J, 70, 60)], "elims": [], "place": None}, ex, idc, vals, cand, colours)
    assert out[0]["legend"] == {"green": "an unknown digit (1, 2, 3, 4, 5, 6, 7, 8 or 9)"}
    assert BP._class_substeps(p, {"idfx": [], "elims": [], "place": None}, ex, idc, vals, cand, colours) is None


COLOUR_CODES = {"CFL", "CEQ", "CCH", "CSG", "CPT", "CPR", "CFS", "CCM", "CCL", "CTR", "CCX", "CSM", "CAL", "CMU", "CMD"}
GOLDEN = Path(__file__).parent / "golden"


def test_colouring_never_below_medium():
    """coloring is a concept to learn (user 2026-11-05): every coloring code is Medium or harder, and no Very Easy /
    Easy golden card lists one"""
    from pencilmark import registry as R

    codes = R.codes()
    tech = {t.code: t for t in R.techniques() if t.code}
    assert {k: R.BANDS[tech[k].band] for k in COLOUR_CODES if tech[k].band < 2} == {}
    easy = [json.loads(line).get("card") or {} for line in (GOLDEN / "expected.jsonl").open(encoding="utf-8")]
    easy = [c for c in easy if c.get("band_index", 9) <= 1]
    assert easy and not [c for c in easy if COLOUR_CODES & {x["code"] for x in c.get("contains") or ()}]
    assert set(codes) >= COLOUR_CODES


@pytest.mark.slow
def test_colouring_switch_leaves_easy_cards_alone():
    """the solve path stays easiest-first: with coloring switched (on, since it is opt in), Very Easy / Easy
    golden cards keep their band and list"""
    from pencilmark import grader_model as GM

    inputs = {json.loads(line)["name"]: json.loads(line) for line in (GOLDEN / "inputs.jsonl").open(encoding="utf-8")}
    easy = [json.loads(line) for line in (GOLDEN / "expected.jsonl").open(encoding="utf-8")]
    easy = [r for r in easy if (r.get("card") or {}).get("band_index", 9) <= 1 and "contains" in r["card"]]
    m = GM.default()
    old = m.route.get("colouring", 0)
    try:
        m.route["colouring"] = 1 - old
        api._PARAMS = (None, None)
        for r in easy:
            c = pencilmark.rate(inputs[r["name"]]["puzzle"], fields=["band", "contains"], max_seconds=60)
            assert (c["band"], [x["code"] for x in c["contains"]]) == (
                r["card"]["band"],
                [x["code"] for x in r["card"]["contains"]],
            ), r["name"]
    finally:
        m.route["colouring"] = old
        api._PARAMS = (None, None)


def test_colour_pointing():
    """a color's places in box 1 all lie in column 1 (CtC, Restricted Access: "orange is in one of these two
    positions"): the color's other places in column 1 are not that color"""
    p = pencilmark.api._load("." * 81)
    P = dict(api._params("human"), colouring=1)
    full = (1 << 9) - 1
    cand = [full] * 81
    m1, m2 = 1 * 9 + 3, 3 * 9 + 1  # r2c4, r4c2: one color, digits 1 / 2
    cand[m1] = cand[m2] = 0b11
    for c in (0 * 9 + 2, 2 * 9 + 2):  # r1c3, r3c3 can't hold it: box 1's places are r1c1, r3c1
        cand[c] = full & ~0b11
    idc = [0] * 81
    idc[m1] = idc[m2] = m1 + 1
    off = set(S.TECH_NAMES) - {S.CLASS_POINTING}
    ms = [
        m
        for m in CB.state_moves(p, P, cand=cand, disabled=off, labels=(None, None, idc))
        if m["tech"] == S.CLASS_POINTING
    ]
    assert len(ms) == 1 and ms[0]["idfx"] == [(NEQ, 54, 12), (NEQ, 63, 12), (NEQ, 72, 12), (USE, 12, 0)]
