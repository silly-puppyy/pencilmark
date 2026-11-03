"""Identity layer (params id_layer, experiment): the Python mirror of the class state, the held-step accounting and
the two-colour moves on a hand-made position."""

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
        (None, [(50, 1)], [(USE, 0, 0), (USE, 40, 0)]),  # sees both colours
    ]
    assert CB.id_held(81, {}, steps) == [False, True, False, False, False]


def test_class_pair_and_trap_listed():
    p = pencilmark.load("." * 81)
    P = dict(api._params("human"), id_layer=1)
    on = {S.CLASS_PAIR, S.CLASS_TRAP}
    off = set(S.TECH_NAMES) - on
    full = (1 << 9) - 1
    cand = [full] * 81
    cand[0] = cand[1] = (1 << 2) | (1 << 5)  # r1c1, r1c2: 3 / 6
    ms = CB.state_moves(p, P, cand=cand, disabled=off, labels=(None, None, [0] * 81))
    assert [m.get("idfx") for m in ms if m["tech"] == S.CLASS_PAIR] == [[(NEQ, 1, 0)]]
    idc = [1, 2] + [0] * 79 + [1, 2]  # after it: two colours
    ms = CB.state_moves(p, P, cand=cand, disabled=off, labels=(None, None, idc))
    trap = [m for m in ms if m["tech"] == S.CLASS_TRAP]
    assert len(trap) == 1 and {c for c, _ in trap[0]["elim"]} == set(range(2, 9)) | {9, 10, 11, 18, 19, 20}
    assert {d for _, d in trap[0]["elim"]} == {3, 6}
