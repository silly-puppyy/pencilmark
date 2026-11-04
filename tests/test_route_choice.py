"""Human route choice (params digit_cont, spot_w / spot_fam / spot_seed, experiment): off by default, the
recorded step prices never change, sampling is reproducible per seed."""

from pencilmark import cbackend as CB
from pencilmark import grader_model as GM
from pencilmark import solver as S
from pencilmark import api

from conftest import CLASSIC as GIVENS


def _route(**ovr):
    p = api.load(api.from_string(GIVENS))
    steps, ok = CB.solve(p, dict(GM.default().price, **ovr))
    assert ok
    return [(s.move.place, round(s.move.d, 9)) for s in steps]


def _spot(seed):
    fam = [-0.37] * (max(S.TECH_NAMES) + 1)
    fam[S.NAKED_D] = 1.36
    return {"locality": 0, "digit_cont": 0, "spot_w": [-1.2, 0.89, 0.85, 0.74, 1.64, -0.88], "spot_fam": fam,
            "spot_seed": seed}


def test_defaults_leave_the_route_alone():
    assert _route() == _route(digit_cont=0.0, spot_w=[])


def test_digit_cont_chains_the_digit():
    def chained(r):
        return sum(a[0][1] == b[0][1] for a, b in zip(r, r[1:]) if a[0] and b[0])

    assert chained(_route(locality=0, digit_cont=0.5)) > chained(_route(locality=0))


def test_spot_sampling_is_reproducible():
    a, b, c = _route(**_spot(1)), _route(**_spot(1)), _route(**_spot(2))
    assert a == b
    assert [x[0] for x in a] != [x[0] for x in c]
    assert sorted(x[0] for x in a if x[0]) == sorted(x[0] for x in c if x[0])  # same placements, other order
