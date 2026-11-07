"""params neq_peers (experiment, off by default): relation pointing also counts house peers, so a cell that sees every
place of a digit in a box -- one by a knight's move, one by its column -- loses the digit (the anti-knight pointing
sheet). Off, only forcing techniques find it."""

import pencilmark
from pencilmark import api
from pencilmark import cbackend as CB

DOC = {
    "format": "pencilmark-puzzle",
    "format_version": 1,
    "board": {"rows": 9, "cols": 9},
    "digits": 9,
    "givens": [0] * 81,
    "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}, {"type": "neighbors", "kind": "antiknight"}],
}
BOX5 = [r * 9 + c for r in range(3, 6) for c in range(3, 6)]


def _pointing(on):
    p = pencilmark.api._load(DOC)
    cand = [0x1FF] * 81
    for c in BOX5:
        if c not in (30, 31):  # 1 only in r4c4, r4c5
            cand[c] &= ~1
    P = dict(api._params("human"), neq_peers=on)
    return {
        c
        for m in CB.state_moves(p, P, cand=cand)
        if m["name"].startswith("PairwiseConstraint")
        for c, v in m["elim"]
        if v == 1
    }


def test_neq_peers_points_through_knight_and_column():
    # r2c4 sees r4c4 by column 4 and r4c5 by a knight's move; r2c5 the other way round
    assert {12, 13} <= _pointing(1)
    assert not ({12, 13} & _pointing(0))
