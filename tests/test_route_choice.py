"""Human route choice (params digit_cont, spot_w / spot_fam / spot_seed): the spotting chooser (closeness model) is the
default route (the trace); the card's numbers read the single price-first route (score card_route); the recorded step
prices never change; sampling is reproducible per seed; route_samples (opt-in) averages sampled routes."""

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


def test_closeness_model_is_the_default_route():
    assert GM.default().route.get("spot_w") and GM.default().route.get("spot_seed") == 1
    assert _route() == _route(spot_seed=1)
    assert [x[0] for x in _route()] != [x[0] for x in _route(spot_w=[], locality=0.4)]  # the old price-first route


def test_digit_cont_chains_the_digit():
    def chained(r):
        return sum(a[0][1] == b[0][1] for a, b in zip(r, r[1:]) if a[0] and b[0])

    assert chained(_route(spot_w=[], locality=0, digit_cont=0.5)) > chained(_route(spot_w=[], locality=0))


def test_spot_sampling_is_reproducible():
    a, b, c = _route(**_spot(1)), _route(**_spot(1)), _route(**_spot(2))
    assert a == b
    assert [x[0] for x in a] != [x[0] for x in c]
    assert sorted(x[0] for x in a if x[0]) == sorted(x[0] for x in c if x[0])  # same placements, other order


def test_card_difficulty_from_bottleneck_rollouts():
    from pencilmark import card_score as CS

    p = api.load(api.from_string(GIVENS))
    m = GM.default()
    saved = dict(m.score)
    try:
        assert m.score["route_rollouts"] == {"routes": 2, "playthroughs": 4}
        base = CS.score_parts(p, m)
        assert CS.score_parts(p, m) == base  # reproducible
        m.score.pop("route_rollouts")
        one = CS.score_parts(p, m)  # off: the single price-first route
        assert one[0] != base[0] and one[1] == base[1]  # the difficulty moves, the time model's effort does not
    finally:
        m.score.clear()
        m.score.update(saved)


def test_card_reads_one_price_first_route():
    from pencilmark import card_score as CS

    p = api.load(api.from_string(GIVENS))
    m = GM.default()
    saved = dict(m.score)
    try:
        m.score.pop("route_rollouts", None)  # the price-first route alone (rollouts tested above)
        assert not m.score.get("route_samples") and m.score["card_route"] == {"spot_w": [], "locality": 0.4}
        base = CS.score_parts(p, m)
        m.score["card_route"] = {}
        assert CS.score_parts(p, m) != base  # without card_route the card would read the human route
        m.score.update(card_route=saved["card_route"], route_samples=3)
        a, b = CS.score_parts(p, m), CS.score_parts(p, m)
        assert a == b and a[0] != base[0] and a[1] == base[1]  # opt-in average: reproducible, difficulty only
    finally:
        m.score.clear()
        m.score.update(saved)


def test_notes_live_writes_position_notes_only():
    p = api.load(api.from_string(GIVENS))
    P = dict(GM.default().price, snyder_max=3)
    assert P.get("notes_live")  # the trace's note model includes them
    a, _ = CB.solve(p, dict(P, notes_live=False))
    b, _ = CB.solve(p, dict(P, notes_live=True))
    assert [(s.move.place, s.move.d) for s in a] == [(s.move.place, s.move.d) for s in b]  # same route and prices
    assert sum(s.notes_written for s in b) > sum(s.notes_written for s in a)  # notes written along the way


def test_trace_marks_layer():
    import pencilmark

    card = pencilmark.rate(GIVENS, fields=["steps", "trace"])
    tr = card["trace"]
    assert all("marks" in t for t in tr) and tr[0]["marks"]  # position notes from the start
    for t in tr:
        for cell, m in t["marks"].items():
            assert set(m.get("corner", [])) | set(m.get("centre", [])) <= set(t["candidates"][cell])
