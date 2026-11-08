"""Shading (yin-yang) in the human solver (1.4 L1): the colour layer, its techniques and soundness."""

import copy
import json
from pathlib import Path

import pencilmark as pm
from pencilmark import api
from pencilmark import band_path as BP
from pencilmark import exchange as X
from pencilmark.cbackend import AE_SHADE

FIX = Path(__file__).parent / "fixtures" / "yin_yang_6x6_parity.json"


def _doc():
    # a synthetic 6x6 yin-yang (runs/shading/make_yy.py, seed 3): twelve cells are shaded exactly when odd
    return json.loads(FIX.read_text())


def test_yin_yang_graded_by_logic_with_shading_steps():
    with X._reserved_ok():
        card = pm.rate(_doc(), fields=["band", "steps"], max_seconds=60)
    codes = {s["code"] for s in card["steps"]}
    assert card["band"] == "Medium"
    assert {"SHL", "SHC", "SHR"} <= codes  # 2x2 / connectivity / the coupling rule all used
    assert "TRL" not in codes


def test_shading_steps_are_sound():
    doc = _doc()
    with X._reserved_ok():
        p = api._load(doc)
        bp = BP.band_path(p, api._params("human"))
    effects = [(c, col) for st in bp["steps"] for k, c, col in st.get("rfx") or () if k == AE_SHADE]
    assert effects
    for c, col in effects[:12]:  # the opposite colour given: no solution
        d2 = copy.deepcopy(doc)
        yy = next(r for r in d2["rules"] if r["type"] == "yin_yang")
        yy.setdefault("unshaded" if col == 1 else "shaded", []).append(f"r{c // 6 + 1}c{c % 6 + 1}")
        with X._reserved_ok():
            assert pm.count_solutions(d2, limit=1)["count"] == 0


def test_named_shading_rules_compile_to_shaded():
    """shading_sight / shaded_count / same_shading / different_shading (rules/shading.py) need the yin_yang rule and
    compile to custom rules over shaded()"""
    import pytest

    from pencilmark.rules.shading import SHADING_RULES

    coords = {(r, c) for r in range(4) for c in range(4)}
    sight = SHADING_RULES["shading_sight"]({"cells": ["r1c1"], "directions": ["right"]}, coords)[0]
    assert sight["holds"] == "1 + len(take_while(right, y => shaded(y) == shaded(x))) == x"
    count = SHADING_RULES["shaded_count"]({"cells": ["r1c1"], "directions": ["down"], "value": 2}, coords)[0]
    assert count["holds"] == "count(y for y in down if shaded(y)) == 2"
    assert SHADING_RULES["different_shading"]({"cells": ["r1c1", "r1c2"]})[0]["holds"] == "shaded(a) != shaded(b)"
    doc = _doc()
    doc["rules"] = [r for r in doc["rules"] if r["type"] != "yin_yang"] + [
        {"type": "different_shading", "cells": ["r1c1", "r1c2"]}
    ]
    with X._reserved_ok(), pytest.raises(pm.FormatError, match="yin_yang"):
        pm.count_solutions(doc)
