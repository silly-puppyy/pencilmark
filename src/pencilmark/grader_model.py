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
"""

from . import _data
from .scoring import complete_params


class GraderModel:
    def __init__(self, route_raw, score, time):
        self.route = complete_params(route_raw)
        self.price = complete_params(dict(route_raw, **_data._int_keys(score.get("price_weights") or {})))
        self.score = score
        self.time = time

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
