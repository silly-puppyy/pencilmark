"""Tests for the sudoku-puzzle exchange format v1 (docs/FORMAT.md): round trips, strict reading, schema, fingerprint, interop
strings, ipuz, describe, sudoku-spec.

    pytest tests/test_format.py        (synthetic puzzles only: tests/fixtures/variants.json, docs/FORMAT.md examples)
"""
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pencilmark                                     # noqa: E402
from pencilmark import exchange as X                  # noqa: E402
from pencilmark import interop as I                   # noqa: E402
from pencilmark import puzzle_json as PJ              # noqa: E402
from pencilmark import spec_format as SF              # noqa: E402
from pencilmark import variants as VR                 # noqa: E402
from pencilmark.__main__ import _to_puzzle_json       # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "variants.json"
SCHEMA = ROOT / "docs" / "sudoku-puzzle.schema.json"
CLASSIC = "79.214...8.67..............4.2..78....84.32....16..5.3..............97.2...826.39"
UNIFIED = {}
_pack = None


def pack():
    """synthetic puzzles: the variant fixtures, the FORMAT.md example files, and generated variant boards"""
    global _pack
    if _pack is None:
        _pack = [v["puzzle"] for v in json.load(open(FIXTURES))]
        text = (ROOT / "docs" / "FORMAT.md").read_text()
        _pack += [json.loads(b) for b in re.findall(r"```json\n(.*?)```", text, re.S)
                  if b.startswith('{"format": "sudoku-puzzle"') and "…" not in b]
        g9 = VR.Grid(9, (3, 3))
        for extra in (VR.x_sudoku(g9), VR.windoku(g9), VR.argyle(g9), VR.disjoint(g9),
                      [{"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2", "r1c3"]},
                       {"type": "arrow", "bulb": ["r5c5"], "lines": [["r6c6", "r7c7"]]},
                       {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r9c1", "r9c2"]},
                       {"type": "edge", "kind": "xv", "letter": "X", "cells": ["r8c1", "r8c2"]}, {"type": "negative", "of": "xv"},
                       {"type": "sandwich", "sum": 12, "side": "left", "cells": [f"r3c{c}" for c in range(1, 10)]},
                       {"type": "sum", "kind": "little_killer", "sum": 15, "side": "top", "cells": ["r1c4", "r2c5", "r3c6", "r4c7", "r5c8", "r6c9"]},
                       {"type": "neighbours", "kind": "antiknight", "within": "box"}]):
            d = json.loads(json.dumps(pencilmark.from_string(CLASSIC)))
            d["rules"] += extra
            _pack.append(d)
    return _pack


def engine(entry):
    p = PJ.from_json(_to_puzzle_json(entry))
    p.finalize()
    return p


def struct(p):
    q = copy.deepcopy(p)
    if not hasattr(q, "groups_of"):
        q.finalize()
    clean = lambda c: json.dumps({k: (list(map(list, v)) if k == "allowed" else v) for k, v in c.items() if not k.startswith("_")},
                                 sort_keys=True, default=list)
    return (list(map(tuple, q.coords)), sorted(q.givens.items()), list(q.domains),
            [(g.kind, tuple(g.cells), bool(g.complete), g.total) for g in q.groups], [repr(r) for r in q.relations],
            [clean(c) for c in q.constraints])


def doc_of(entry):
    return X.write(engine(entry))


# ------------------------------------------------------------------------------------------------------------ round trip
def test_pack_round_trip_structure():
    same = 0
    for n, e in enumerate(pack()):
        p = engine(e)
        back = X.read(json.loads(json.dumps(X.write(p))))
        if n in UNIFIED:
            continue
        assert struct(p) == struct(back), f"pack line {n} changed through the format"
        same += 1
    assert same == len(pack()) - len(UNIFIED)


def test_canonical_idempotent():
    """write(read(write(p))) == write(p) for every pack puzzle (one canonical representation)"""
    for n, e in enumerate(pack()):
        d1 = X.write(engine(e))
        d2 = X.write(X.read(d1))
        assert X.dumps(d1) == X.dumps(d2), f"pack line {n}: canonical form not stable"


def test_legacy_files_still_read():
    for v in json.load(open(FIXTURES)):            # the fixtures are older "sudoku-puzzle/2" files
        assert v["puzzle"]["format"] == "sudoku-puzzle/2"
        assert pencilmark.load(v["puzzle"]).N >= 16


# --------------------------------------------------------------------------------------------------------------- strict
def _classic_doc():
    return pencilmark.to_export(CLASSIC, with_solution=False, describe=False)


def _refuses(doc, needle):
    try:
        X.validate(doc)
    except X.FormatError as e:
        assert needle in str(e), f"wrong message: {e}"
        return
    raise AssertionError(f"accepted a file that must be refused ({needle})")


def test_strict_refusal():
    d = _classic_doc()
    X.validate(d)
    bad = dict(d, extra=1); _refuses(bad, "unknown top-level key")
    bad = dict(d, format_version=2); _refuses(bad, "newer")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "thermo", "cells": ["r1c1", "r1c2"]}); _refuses(bad, "unknown rule type")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "custom", "rule": "x"}); _refuses(bad, "reserved")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "com.example:foo"}); _refuses(bad, "vendor")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2"], "colour": "red"})
    _refuses(bad, "unknown key")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "line", "kind": "wiggle", "cells": ["r1c1", "r1c2"]}); _refuses(bad, "unknown kind")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r2c2"]})
    _refuses(bad, "orthogonally adjacent")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r1c10"]})
    _refuses(bad, "does not exist")
    bad = copy.deepcopy(d); bad["grid"]["implied_houses"] = False; _refuses(bad, "grid")
    bad = copy.deepcopy(d); bad["rules"].append({"type": "sandwich", "sum": 5, "side": "top", "cells": ["r2c1", "r3c1"]})
    _refuses(bad, "is a cell")
    # ignorable containers and rule id / label / style are accepted
    ok = copy.deepcopy(d); ok["meta"] = {"anything": [1, 2]}; ok["style"] = {"x": 1}; ok["ext"] = {"com.example": {}}
    ok["rules"][0]["label"] = "board"; ok["rules"][0]["id"] = "b"; ok["rules"][0]["style"] = {"color": "#000000"}
    X.validate(ok)


def test_required_parameters_off_9x9():
    d = pencilmark.from_string("1..." + "." * 12)          # 4x4
    d = copy.deepcopy(d)
    d["rules"].append({"type": "line", "kind": "whisper", "cells": ["r1c1", "r1c2"]})
    _refuses(d, "requires")
    d["rules"][-1]["value"] = 2
    X.validate(d)


# --------------------------------------------------------------------------------------------------------------- schema
def test_schema_validates_pack():
    import pytest
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.load(open(SCHEMA))
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    for n, e in enumerate(pack()):
        errs = list(v.iter_errors(doc_of(e)))
        assert not errs, f"pack line {n}: {errs[0].message}"
    assert list(v.iter_errors({"format": "sudoku-puzzle", "format_version": 1, "grid": {"rows": 1, "cols": 1}, "digits": 1,
                               "givens": [0], "rules": [{"type": "nope"}]}))


def test_format_md_examples():
    """the complete example files in docs/FORMAT.md are valid"""
    text = (ROOT / "docs" / "FORMAT.md").read_text()
    n = 0
    for block in re.findall(r"```json\n(.*?)```", text, re.S):
        if not block.startswith('{"format": "sudoku-puzzle"') or "…" in block:
            continue
        d = json.loads(block)
        X.validate(d)
        X.read(d)
        n += 1
    assert n >= 3


# ---------------------------------------------------------------------------------------------------------- fingerprint
def test_fingerprint_stable():
    d = _classic_doc()
    f = pencilmark.fingerprint(d)
    assert f == "sha256:f722943e0e36b27a6e339b59614840aac472c45635bc733152c2d1e13e174e32", f
    # metadata, style and solution do not matter; another spelling of the same houses does not matter
    d2 = copy.deepcopy(d); d2["meta"] = {"title": "x"}; d2["style"] = {"a": 1}
    assert pencilmark.fingerprint(d2) == f
    d3 = copy.deepcopy(d)
    d3["rules"] = [{"type": "subgrid", "size": 9, "origin": "r1c1"},
                   {"type": "box_grid", "size": [3, 3], "repeat": [3, 3], "origin": "r1c1"}]
    assert pencilmark.fingerprint(d3) == f
    d4 = copy.deepcopy(d); d4["givens"][2] = 5
    assert pencilmark.fingerprint(d4) != f


def test_dumps_layout():
    t = pencilmark.dumps(_classic_doc())
    assert '"givens": [\n    7, 9, 0, 2, 1, 4, 0, 0, 0,\n' in t
    assert t.index('"format"') < t.index('"grid"') < t.index('"givens"') < t.index('"rules"')
    assert json.loads(t) == X.canonical(_classic_doc())


# ---------------------------------------------------------------------------------------------------------------- interop
def test_plain_string_round_trip():
    d = pencilmark.from_string(CLASSIC)
    assert pencilmark.to_string(d, "plain") == CLASSIC
    assert d["rules"] == [{"type": "subgrid", "size": 9, "box": [3, 3], "origin": "r1c1"}]


def _semantic(p):
    D = p.D
    idx = lambda c: p.coords[c][0] * D + p.coords[c][1]
    houses = sorted(sorted(idx(c) for c in g.cells) for g in p.groups if g.total is None and g.kind != "cage")
    cages = sorted((g.total, sorted(idx(c) for c in g.cells)) for g in p.groups if g.total is not None or g.kind == "cage")
    return houses, cages, sorted((idx(c), v) for c, v in p.givens.items())


def test_sudokuwiki_round_trip():
    kinds = {}
    for e in pack():
        p = engine(e)
        k, _ = I.analyse(p)
        if k and k not in kinds:
            kinds[k] = p
    g9 = VR.Grid(9, (3, 3))
    jig = "111222233111222233114452333144455633444555666774556669777856699778888999778888999"
    boxes = [{"type": "box", "cells": [X.cell_name(*divmod(i, 9)) for i in range(81) if jig[i] == ch]} for ch in "123456789"]
    cage = {"type": "cage", "sum": 10, "cells": ["r1c1", "r1c2", "r2c1"]}
    giv = "1" + "." * 79 + "9"
    synth = {"x": VR.x_sudoku(g9), "windoku": VR.windoku(g9), "colour": VR.disjoint(g9), "killer": [cage]}
    for k, extra in synth.items():
        d = pencilmark.from_string(giv)
        d["rules"] += extra
        kinds.setdefault(k, pencilmark.load(d))
    d = pencilmark.from_string(giv); d["rules"] = [{"type": "subgrid", "size": 9, "origin": "r1c1"}] + boxes
    kinds["jigsaw"] = pencilmark.load(d)
    d = copy.deepcopy(d); d["rules"].append(cage)
    kinds["killer_jigsaw"] = pencilmark.load(d)
    d = pencilmark.from_string("1" + "." * 35); d["rules"].append({"type": "cage", "sum": 7, "cells": ["r2c2", "r2c3", "r3c2"]})
    kinds["killer6"] = pencilmark.load(d)
    gen4 = pencilmark.load({"digits": 4, "box": "2x2", "numbers": "." * 16,
                        "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}]})
    for k, p in kinds.items():
        s = pencilmark.to_string(p, "sudokuwiki")
        back = pencilmark.load(pencilmark.from_string(s))
        assert I.analyse(back)[0] == k, (k, I.analyse(back))
        assert _semantic(back) == _semantic(p), f"{k}: {s[:12]}..."
        again = pencilmark.to_string(back, "sudokuwiki")      # cage colours may differ; the puzzle may not
        assert again[:3] == s[:3] and _semantic(pencilmark.load(pencilmark.from_string(again))) == _semantic(p)
    try:
        pencilmark.to_string(gen4, "sudokuwiki")
    except pencilmark.NotSupportedError:
        pass
    else:
        raise AssertionError("a 4x4 killer has no sudokuwiki form")


def test_sudokuwiki_refusals():
    s = "S9B" + "zz" * 81
    try:
        pencilmark.from_string(s)
    except pencilmark.NotSupportedError:
        return
    raise AssertionError("candidate masks must be refused")


# ------------------------------------------------------------------------------------------------------------------- ipuz
def test_ipuz_export():
    ip = pencilmark.to_ipuz(_classic_doc())
    assert ip["version"] == "http://ipuz.org/v2" and ip["kind"] == ["http://ipuz.org/sudoku#1"]
    assert ip["puzzle"][0][:3] == [7, 9, 0] and ip["boxes"] is True
    assert ip[f"{I.IPUZ_NS}:puzzle"]["format"] == "sudoku-puzzle"
    killer = pencilmark.load({"digits": 4, "box": "2x2", "numbers": "." * 16,
                          "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}]})
    ip = pencilmark.to_ipuz(killer)
    assert "http://ipuz.org/sudoku/killersudoku#1" in ip["kind"] and ip["cages"] == [{"cells": [[1, 1], [2, 1]], "value": 3}]
    d = _classic_doc()
    d["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c3", "r2c3"]})
    try:
        pencilmark.to_ipuz(d)
    except pencilmark.NotSupportedError as e:
        assert "line" in str(e)
    else:
        raise AssertionError("ipuz cannot carry a thermo")


# --------------------------------------------------------------------------------------------------------------- describe
def _with(rules, D=9):
    d = pencilmark.from_string("." * D * D)
    d["rules"] += rules
    return d


def test_describe_names():
    assert pencilmark.describe(_classic_doc())["type"] == "Sudoku"
    assert pencilmark.describe(pencilmark.from_string("." * 36))["type"] == "Mini Sudoku"
    g9 = VR.Grid(9, (3, 3))
    assert pencilmark.describe(_with(VR.x_sudoku(g9)))["type"] == "X Sudoku"
    assert pencilmark.describe(_with(VR.windoku(g9)))["type"] == "Windoku Sudoku"
    assert pencilmark.describe(_with(VR.argyle(g9)))["type"] == "Argyle Sudoku"
    g16 = VR.Grid(16, (4, 4))
    w16 = VR.windoku(g16)
    assert len(w16) == 9
    assert pencilmark.describe(_with(w16, 16))["type"] == "16x16 Windoku Sudoku"
    assert VR.argyle(g16) is None
    killer_x = _with(VR.x_sudoku(g9) + [{"type": "cage", "sum": 3, "cells": ["r1c1", "r1c2"]}])
    dsc = pencilmark.describe(killer_x)
    assert dsc["type"] == "Variant Sudoku" and list(dsc["rules"]) == ["Sudoku", "X", "Killer"]
    nxv = _with([{"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r1c2"]}, {"type": "negative", "of": "xv"}])
    dsc = pencilmark.describe(nxv)
    assert dsc["type"] == "XV Sudoku" and "All X's and V's are given." in dsc["rules"]["XV"]
    ak = _with([{"type": "neighbours", "kind": "antiknight", "within": "box"}])
    assert "within the same box" in pencilmark.describe(ak)["rules"]["Anti-Knight"]
    assert pencilmark.describe(pencilmark.load({"layout": "samurai", "numbers": ""}))["type"] == "Samurai Sudoku"
    assert pencilmark.describe(pencilmark.load({"layout": "butterfly", "numbers": ""}))["type"] == "Butterfly Sudoku"
    assert pencilmark.describe(pencilmark.load({"digits": 4, "box": "2x2", "numbers": "." * 16,
                                        "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}]}))["type"] == "Tiny Killer Sudoku"


# ---------------------------------------------------------------------------------------------------------- sudoku-spec
def test_spec_round_trip():
    from pencilmark.gen.api import Spec
    specs = [{"size": 9, "target_band": "Hard", "seed": 3},
             {"size": 6, "elements": {"kropki": "min"}, "symmetry": "rot180"},
             {"size": 9, "elements": {"cage": "partition"}, "require": ["XWG"], "strict_require": True, "time_limit": 30},
             {"size": 9, "kinds": ["thermo", "arrow"], "max_elements": 6, "target_difficulty": [4, 6], "min_givens": 20, "max_givens": 30},
             {"size": 4, "elements": {"cage": 5}, "max_givens": 0, "solver": "cpsat"}]
    for s in specs:
        doc = pencilmark.spec_from_gen(s)
        assert doc["format"] == "sudoku-spec"
        back = pencilmark.spec_to_gen(json.loads(json.dumps(doc)))
        assert Spec.from_any(back) == Spec.from_any(s), (s, back)
    bad = pencilmark.spec_from_gen(specs[0])
    bad["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2"]})
    try:
        pencilmark.spec_to_gen(bad)
    except pencilmark.NotSupportedError:
        pass
    else:
        raise AssertionError("fixed rules are not supported yet")


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                import traceback
                traceback.print_exc()
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
