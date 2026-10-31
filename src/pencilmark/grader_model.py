"""The grader model: every fitted parameter the card uses, loaded once (internal; the public API has no model argument).

route   engine parameters for the band route, the written route's time prices and the search-effort term
        (data/params.json, completed with scoring defaults)
price   the difficulty prices: route with card_score.json "price_weights" in place of its structural weights (the
        card-fit weights, fitted on human times; everything else is shared with route)
score   the card-score configuration: step-value exponents, enumeration and search-effort weights, difficulty map
        (data/card_score.json)
time    the time model (data/time_model.json)

default() is what ships; the golden corpus (tools/golden.py) is pinned to it. Callers that change parameters take a
copy (scoring.copy_params) and never edit these dicts.

Research: parameters have names, and a changed model grades through use():

    m = default().with_overrides({"score.map.A": "x1.2", "time.k_effort": 0.3})
    with use(m):
        card = pencilmark.rate(puzzle)

Names: "<set>.<key>" for a top-level value of route / price / score / time, "<set>.<key>.<subkey>" inside a mapping
("score.map.A"), "route.price.<Technique>" / "price.price.<Technique>" for a technique's base price (B, by engine name;
used only for techniques the structural model does not price).
A value is a number, or "x<factor>" to scale the current one. names() lists every name with its value.
"""

import contextlib
import copy

from . import _data
from . import solver as S
from .scoring import complete_params

_SETS = ("route", "price", "score", "time")


class GraderModel:
    def __init__(self, route_raw, score, time):
        self.route = complete_params(route_raw)
        self.price = complete_params(dict(route_raw, **_data._int_keys(score.get("price_weights") or {})))
        self.score = score
        self.time = time

    def names(self):
        """{name: value} for every scalar parameter (lists are named as a whole)"""
        out = {}
        for k in _SETS:
            for key, v in getattr(self, k).items():
                if k == "score" and key == "price_weights":  # built into price at load: named there, not here
                    continue
                if key == "B":
                    for t, b in v.items():
                        out[f"{k}.price.{S.TECH_NAMES.get(t, t)}"] = b
                elif isinstance(v, dict):
                    for sub, w in v.items():
                        out[f"{k}.{key}.{sub}"] = w
                else:
                    out[f"{k}.{key}"] = v
        return out

    def get(self, name):
        return self.names()[name]

    def with_overrides(self, overrides):
        """a copy with the named parameters changed (number, or "x<factor>" to scale); unknown names are an error"""
        m = copy.deepcopy(self)
        by_name = {v: t for t, v in S.TECH_NAMES.items()}
        known = self.names()
        for name, value in overrides.items():
            if name not in known:
                raise KeyError(f"unknown grader-model parameter {name!r}")
            old = known[name]
            new = old * float(value[1:]) if isinstance(value, str) and value.startswith("x") else value
            parts = name.split(".")
            target = getattr(m, parts[0])
            if len(parts) == 3 and parts[1] == "price":
                target["B"][by_name[parts[2]]] = new
            elif len(parts) == 3:
                target[parts[1]][parts[2]] = new
            else:
                target[parts[1]] = new
        return m

    @classmethod
    def load(cls):
        """the shipped model from pencilmark/data"""
        time = _data.load_json("time_model.json") if _data.exists("time_model.json") else {}
        return cls(_data.load_params("params.json"), _data.load_json("card_score.json"), time)


_DEFAULT = None


def default():
    """the shipped model, loaded on first use"""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = GraderModel.load()
    return _DEFAULT


@contextlib.contextmanager
def use(model):
    """grade with `model` instead of the shipped one inside the block (research; not thread-safe)"""
    global _DEFAULT
    old = default()
    _DEFAULT = model
    try:
        yield model
    finally:
        _DEFAULT = old
