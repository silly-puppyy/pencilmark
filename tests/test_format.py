"""Tests for the sudoku-puzzle exchange format v1 (docs/FORMAT.md): round trips, strict reading, schema, fingerprint, interop
strings, ipuz, describe, sudoku-spec.

    pytest tests/test_format.py        (synthetic puzzles only: tests/fixtures/variants.json, docs/FORMAT.md examples)
"""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pencilmark  # noqa: E402
from pencilmark import exchange as X  # noqa: E402
from pencilmark import interop as I  # noqa: E402
from pencilmark import puzzle_json as PJ  # noqa: E402
from pencilmark import spec_format as SF  # noqa: E402
from pencilmark import variants as VR  # noqa: E402
from pencilmark.__main__ import _to_puzzle_json  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "variants.json"
SCHEMA = ROOT / "docs" / "sudoku-puzzle.schema.json"
CLASSIC = "79.214...8.67..............4.2..78....84.32....16..5.3..............97.2...826.39"
UNIFIED = {}
_pack = None


def pack():
    """synthetic puzzles: the variant fixtures, the FORMAT.md example files, and generated variant boards"""
    global _pack
    if _pack is None:
        _pack = [v["puzzle"] for v in json.load(open(FIXTURES, encoding="utf-8"))]
        text = (ROOT / "docs" / "FORMAT.md").read_text(encoding="utf-8")
        _pack += [
            json.loads(b)
            for b in re.findall(r"```json\n(.*?)```", text, re.S)
            if b.startswith('{"format": "sudoku-puzzle"') and "…" not in b
        ]
        g9 = VR.Grid(9, (3, 3))
        for extra in (
            VR.x_sudoku(g9),
            VR.windoku(g9),
            VR.argyle(g9),
            VR.disjoint(g9),
            [
                {"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2", "r1c3"]},
                {"type": "arrow", "bulb": ["r5c5"], "lines": [["r6c6", "r7c7"]]},
                {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r9c1", "r9c2"]},
                {"type": "edge", "kind": "xv", "letter": "X", "cells": ["r8c1", "r8c2"]},
                {"type": "negative", "of": "xv"},
                {"type": "sandwich", "sum": 12, "side": "left", "cells": [f"r3c{c}" for c in range(1, 10)]},
                {
                    "type": "sum",
                    "kind": "little_killer",
                    "sum": 15,
                    "side": "top",
                    "cells": ["r1c4", "r2c5", "r3c6", "r4c7", "r5c8", "r6c9"],
                },
                {"type": "neighbours", "kind": "antiknight", "within": "box"},
            ],
        ):
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
    clean = lambda c: json.dumps(
        {k: (list(map(list, v)) if k == "allowed" else v) for k, v in c.items() if not k.startswith("_")},
        sort_keys=True,
        default=list,
    )
    return (
        list(map(tuple, q.coords)),
        sorted(q.givens.items()),
        list(q.domains),
        [(g.kind, tuple(g.cells), bool(g.complete), g.total) for g in q.groups],
        [repr(r) for r in q.relations],
        [clean(c) for c in q.constraints],
    )


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


def test_fixtures_are_valid():
    for v in json.load(open(FIXTURES, encoding="utf-8")):
        X.validate(v["puzzle"])
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
    bad = dict(d, extra=1)
    _refuses(bad, "unknown top-level key")
    bad = dict(d, format_version=2)
    _refuses(bad, "newer")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "thermo", "cells": ["r1c1", "r1c2"]})
    _refuses(bad, "unknown rule type")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "custom", "rule": "x"})
    _refuses(bad, "reserved")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "com.example:foo"})
    _refuses(bad, "vendor")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2"], "colour": "red"})
    _refuses(bad, "unknown key")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "line", "kind": "wiggle", "cells": ["r1c1", "r1c2"]})
    _refuses(bad, "unknown kind")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r2c2"]})
    _refuses(bad, "orthogonally adjacent")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r1c10"]})
    _refuses(bad, "does not exist")
    bad = copy.deepcopy(d)
    bad["board"]["implied_houses"] = False
    _refuses(bad, "board")
    bad = copy.deepcopy(d)
    bad["grid"] = bad.pop("board")
    _refuses(bad, "unknown top-level key")
    bad = dict(d, format="sudoku-puzzle/2")
    _refuses(bad, "not a sudoku-puzzle")
    bad = copy.deepcopy(d)
    bad["candidates"] = {"R1C3": [1, 2]}
    _refuses(bad, "bad cell name")
    bad = copy.deepcopy(d)
    bad["rules"][0]["count"] = [3, 3]
    _refuses(bad, "unknown key")
    bad = copy.deepcopy(d)
    bad["rules"][0]["box"] = [2, 3]
    _refuses(bad, "does not hold")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "grid", "origin": "r2c1"})
    _refuses(bad, "missing cell")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "subgrid", "size": 9, "origin": "r1c1"})
    _refuses(bad, "unknown rule type")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "sandwich", "sum": 5, "side": "top", "cells": ["r2c1", "r3c1"]})
    _refuses(bad, "is a cell")
    # ignorable containers and rule id / label / style are accepted
    ok = copy.deepcopy(d)
    ok["meta"] = {"anything": [1, 2]}
    ok["style"] = {"x": 1}
    ok["meta"]["com.example"] = {"x": 1}
    ok["rules"][0]["label"] = "board"
    ok["rules"][0]["id"] = "b"
    ok["rules"][0]["style"] = {"color": "#000000"}
    X.validate(ok)
    bad = copy.deepcopy(d)
    bad["ext"] = {"com.example": {}}  # vendor data goes in meta (FORMAT.md 2.1)
    _refuses(bad, "ext")


def test_required_parameters_off_9x9():
    d = pencilmark.from_string("1..." + "." * 12)  # 4x4
    d = copy.deepcopy(d)
    d["rules"].append({"type": "line", "kind": "whisper", "cells": ["r1c1", "r1c2"]})
    _refuses(d, "requires")
    d["rules"][-1]["value"] = 2
    X.validate(d)


# --------------------------------------------------------------------------------------------------------------- schema
def test_schema_validates_pack():
    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.load(open(SCHEMA, encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    for n, e in enumerate(pack()):
        errs = list(v.iter_errors(doc_of(e)))
        assert not errs, f"pack line {n}: {errs[0].message}"
    assert list(
        v.iter_errors(
            {
                "format": "sudoku-puzzle",
                "format_version": 1,
                "board": {"rows": 1, "cols": 1},
                "digits": 1,
                "givens": [0],
                "rules": [{"type": "nope"}],
            }
        )
    )


def test_format_md_examples():
    """the complete example files in docs/FORMAT.md, the rule family pages and the guides are valid"""
    pages = [
        ROOT / "docs" / "FORMAT.md",
        *sorted((ROOT / "docs").glob("rules/*.mdx")),
        *(ROOT / "docs").glob("guides/*"),
    ]
    text = "\n".join(f.read_text(encoding="utf-8") for f in pages)
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
    assert f == "sha256:a96eb0bb99b3f4a588d8d3f97dd28eaf321a4f453de36e60b4bab8f5eac239a6", f
    # metadata, style and solution do not matter; another spelling of the same houses does not matter
    d2 = copy.deepcopy(d)
    d2["meta"] = {"title": "x"}
    d2["style"] = {"a": 1}
    assert pencilmark.fingerprint(d2) == f
    boxes = [
        {"type": "box", "cells": [X.cell_name(br + i, bc + j) for i in range(3) for j in range(3)]}
        for br in (0, 3, 6)
        for bc in (0, 3, 6)
    ]
    d3 = copy.deepcopy(d)  # a grid plus boxes as single rules
    d3["rules"] = [{"type": "grid", "origin": "r1c1"}] + boxes
    assert pencilmark.fingerprint(d3) == f
    d5 = copy.deepcopy(d)  # explicit rows / columns and boxes
    d5["rules"] = (
        [{"type": "row", "cells": [X.cell_name(r, c) for c in range(9)]} for r in range(9)]
        + [{"type": "column", "cells": [X.cell_name(r, c) for r in range(9)]} for c in range(9)]
        + boxes
    )
    assert pencilmark.fingerprint(d5) == f
    d4 = copy.deepcopy(d)
    d4["givens"][2] = 5
    assert pencilmark.fingerprint(d4) != f


def test_dumps_layout():
    t = pencilmark.dumps(_classic_doc())
    assert '"givens": [\n    7, 9, 0, 2, 1, 4, 0, 0, 0,\n' in t
    assert t.index('"format"') < t.index('"board"') < t.index('"givens"') < t.index('"rules"')
    assert json.loads(t) == X.canonical(_classic_doc())


# ---------------------------------------------------------------------------------------------------------------- interop
def test_plain_string_round_trip():
    d = pencilmark.from_string(CLASSIC)
    assert pencilmark.to_string(d, "plain") == CLASSIC
    assert d["rules"] == [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}]


def _semantic(p):
    D = p.D
    idx = lambda c: p.coords[c][0] * D + p.coords[c][1]
    houses = sorted(sorted(idx(c) for c in g.cells) for g in p.groups if g.total is None and g.kind != "cage")
    cages = sorted(
        (g.total, sorted(idx(c) for c in g.cells)) for g in p.groups if g.total is not None or g.kind == "cage"
    )
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
    boxes = [
        {"type": "box", "cells": [X.cell_name(*divmod(i, 9)) for i in range(81) if jig[i] == ch]} for ch in "123456789"
    ]
    cage = {"type": "cage", "sum": 10, "cells": ["r1c1", "r1c2", "r2c1"]}
    giv = "1" + "." * 79 + "9"
    synth = {"x": VR.x_sudoku(g9), "windoku": VR.windoku(g9), "colour": VR.disjoint(g9), "killer": [cage]}
    for k, extra in synth.items():
        d = pencilmark.from_string(giv)
        d["rules"] += extra
        kinds.setdefault(k, pencilmark.load(d))
    d = pencilmark.from_string(giv)
    d["rules"] = [{"type": "grid", "origin": "r1c1"}] + boxes  # jigsaw
    kinds["jigsaw"] = pencilmark.load(d)
    d = copy.deepcopy(d)
    d["rules"].append(cage)
    kinds["killer_jigsaw"] = pencilmark.load(d)
    d = pencilmark.from_string("1" + "." * 35)
    d["rules"].append({"type": "cage", "sum": 7, "cells": ["r2c2", "r2c3", "r3c2"]})
    kinds["killer6"] = pencilmark.load(d)
    gen4 = pencilmark.load(
        {
            "digits": 4,
            "box": "2x2",
            "numbers": "." * 16,
            "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}],
        }
    )
    for k, p in kinds.items():
        s = pencilmark.to_string(p, "sudokuwiki")
        back = pencilmark.load(pencilmark.from_string(s))
        assert I.analyse(back)[0] == k, (k, I.analyse(back))
        assert _semantic(back) == _semantic(p), f"{k}: {s[:12]}..."
        again = pencilmark.to_string(back, "sudokuwiki")  # cage colours may differ; the puzzle may not
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
    killer = pencilmark.load(
        {
            "digits": 4,
            "box": "2x2",
            "numbers": "." * 16,
            "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}],
        }
    )
    ip = pencilmark.to_ipuz(killer)
    assert "http://ipuz.org/sudoku/killersudoku#1" in ip["kind"] and ip["cages"] == [
        {"cells": [[1, 1], [2, 1]], "value": 3}
    ]
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
    nxv = _with(
        [{"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r1c2"]}, {"type": "negative", "of": "xv"}]
    )
    dsc = pencilmark.describe(nxv)
    assert dsc["type"] == "XV Sudoku" and "All X's and V's are given." in dsc["rules"]["XV"]
    ak = _with([{"type": "neighbours", "kind": "antiknight", "within": "box"}])
    assert "within the same box" in pencilmark.describe(ak)["rules"]["Anti-Knight"]
    assert pencilmark.describe(pencilmark.load({"layout": "samurai", "numbers": ""}))["type"] == "Samurai Sudoku"
    assert pencilmark.describe(pencilmark.load({"layout": "butterfly", "numbers": ""}))["type"] == "Butterfly Sudoku"
    assert (
        pencilmark.describe(
            pencilmark.load(
                {
                    "digits": 4,
                    "box": "2x2",
                    "numbers": "." * 16,
                    "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}],
                }
            )
        )["type"]
        == "Tiny Killer Sudoku"
    )


# ---------------------------------------------------------------------------------------------------------- sudoku-spec
def test_card_fields():
    """field mask = top-level keys, explanation levels, the issues / reject shape (GRADE.md)"""
    c = pencilmark.rate(CLASSIC)
    assert list(c) == ["format", "format_version", "grader", "difficulty", "time", "band", "contains"], list(c)
    assert c["grader"] == {"name": "pencilmark", "version": pencilmark.__version__} and "reject" not in c
    m = pencilmark.rate(CLASSIC, fields=["difficulty", "time_p80", "steps", "symmetry", "se"], explain="short")
    assert set(m) == {"format", "format_version", "grader", "difficulty", "time_p80", "steps", "symmetry", "se"}
    assert m["difficulty"] == c["difficulty"] and set(m["steps"][0]["explanation"]) == {"short"}
    assert m["se"]["scale"] == "classic"
    assert "explanation" not in pencilmark.rate(CLASSIC, fields=["steps"])["steps"][0]
    assert {"kind": "rot180", "of": "givens"} in m["symmetry"]
    try:
        pencilmark.rate(CLASSIC, fields=["nope"])
    except ValueError:
        pass
    else:
        raise AssertionError("unknown field accepted")
    d = pencilmark.from_string(CLASSIC)
    d["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c5", "r1c4"]})  # true, but never needed
    i = pencilmark.rate(d, fields=["issues", "reject"])
    assert i["reject"] is True and i["issues"][0]["rules"] == [1] and "rule 1" in i["issues"][0]["text"], i


def _houses(doc):
    p = X.read(doc)
    return [(g.kind, g.cells) for g in p.groups]


def test_houses():
    """grid gives rows and columns, box_grid adds regular boxes, box / row / column are explicit, nothing is inferred;
    the writer finds grids in any house order (FORMAT.md 6.1)"""
    classic = pencilmark.from_string(CLASSIC)
    h = _houses(classic)
    assert [k for k, _ in h] == ["row"] * 9 + ["col"] * 9 + ["box"] * 9
    boxes = [
        {"type": "box", "cells": [X.cell_name(br + i, bc + j) for i in range(3) for j in range(3)]}
        for br in (0, 3, 6)
        for bc in (0, 3, 6)
    ]
    jig = copy.deepcopy(classic)
    jig["rules"] = [{"type": "grid", "origin": "r1c1"}] + boxes
    assert _houses(jig) == h
    only_boxes = copy.deepcopy(classic)
    only_boxes["rules"] = boxes
    assert [k for k, _ in _houses(only_boxes)] == ["box"] * 9  # no rows / columns without a grid
    latin = copy.deepcopy(classic)
    latin["rules"] = [{"type": "grid", "origin": "r1c1"}]
    assert [k for k, _ in _houses(latin)] == ["row"] * 9 + ["col"] * 9
    # a jigsaw written from the engine: one grid plus its pieces
    pieces = copy.deepcopy(boxes)
    pieces[0]["cells"][8], pieces[1]["cells"][6] = pieces[1]["cells"][6], pieces[0]["cells"][8]
    jig2 = copy.deepcopy(classic)
    jig2["rules"] = [{"type": "grid", "origin": "r1c1"}] + pieces
    assert [r["type"] for r in X.write(X.read(jig2))["rules"]] == ["grid"] + ["box"] * 9
    # explicit houses whose rows / columns make a grid are written as one
    expl = copy.deepcopy(classic)
    expl["rules"] = (
        [{"type": "column", "cells": [X.cell_name(r, c) for r in range(9)]} for c in range(9)]
        + boxes
        + [{"type": "row", "cells": [X.cell_name(r, c) for c in range(9)]} for r in range(9)]
    )
    assert X.write(X.read(expl))["rules"] == [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}]
    sam = pencilmark.load({"layout": "samurai", "numbers": ""})
    d = X.write(sam)
    assert [r["type"] for r in d["rules"]] == ["box_grid"] * 5
    assert len(X.read(d).groups) == len(sam.groups)


def test_spec_round_trip():
    from pencilmark.gen.api import Spec

    specs = [
        {"size": 9, "target_band": "Hard", "seed": 3},
        {"size": 6, "elements": {"kropki": "min"}, "symmetry": "rot180"},
        {"size": 9, "elements": {"cage": "partition"}, "require": ["XWG"], "strict_require": True, "time_limit": 30},
        {
            "size": 9,
            "kinds": ["thermo", "arrow"],
            "max_elements": 6,
            "target_difficulty": [4, 6],
            "min_givens": 20,
            "max_givens": 30,
        },
        {"size": 4, "elements": {"cage": 5}, "max_givens": 0, "solver": "cpsat"},
    ]
    for s in specs:
        doc = SF.spec_from_gen(s)
        assert doc["format"] == "sudoku-spec"
        back = SF.spec_to_gen(json.loads(json.dumps(doc)))
        norm = lambda x: _plan_of(Spec.from_any(x))
        assert norm(back) == norm(s), (s, back)
    bad = SF.spec_from_gen(specs[0])
    bad["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2"]})
    for extra in (
        {"rules": bad["rules"]},
        {"quality": {"trivial": {"limit": 0.4}}},
        {"givens": {"mask": [1] * 81}},
        {"where": {"difficulty": "max"}},
        {"limits": {"results": 3}},
    ):
        d = dict(SF.spec_from_gen(specs[0]), **extra)
        try:
            SF.spec_to_gen(d)
        except pencilmark.NotSupportedError:
            continue
        raise AssertionError(f"must be refused: {extra}")
    from pencilmark import spec_format as SF2

    try:
        SF2.validate_spec(dict(SF.spec_from_gen(specs[0]), target={"band": "Hard"}))
    except pencilmark.FormatError:
        pass
    else:
        raise AssertionError("round-2 'target' must be refused")


def _plan_of(s):
    """what the generator does with a Spec (kinds is shorthand for elements {k: 1})"""
    from pencilmark.gen import api as GA

    d = {
        f: getattr(s, f)
        for f in (
            "size",
            "target_band",
            "target_difficulty",
            "require",
            "strict_require",
            "symmetry",
            "min_givens",
            "max_givens",
            "max_elements",
            "solver",
            "seed",
            "time_limit",
            "grade_seconds",
        )
    }
    d["target_difficulty"] = list(d["target_difficulty"]) if d["target_difficulty"] else None
    d["plan"] = GA._plan(s)
    return d


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


def test_multigrid_written_compact():
    """a samurai whose houses the engine lists out of grid order is still written as five box_grids"""
    R = 21
    giv = [
        0 if (r < 9 or r >= 12 or 6 <= c < 15) and (c < 9 or c >= 12 or 6 <= r < 15) else None
        for r in range(R)
        for c in range(R)
    ]
    grids = [(0, 0), (0, 12), (6, 6), (12, 0), (12, 12)]
    doc = {
        "format": "sudoku-puzzle",
        "format_version": 1,
        "board": {"rows": R, "cols": R},
        "digits": 9,
        "givens": giv,
        "rules": [{"type": "box_grid", "origin": X.cell_name(r, c), "box": [3, 3]} for r, c in grids],
    }
    p = X.read(doc)
    p.groups.sort(key=lambda g: (g.kind != "box", g.kind != "row", g.cells))  # boxes first, then rows, then columns
    p.finalize()
    out = X.write(p)
    assert [r for r in out["rules"] if r["type"] in ("box_grid", "box", "row", "column")] == doc["rules"]
    assert pencilmark.fingerprint(out) == pencilmark.fingerprint(doc)


def test_area_scope():
    """area = a grid's origin or a cell list (FORMAT.md 5); one grid of a samurai with anti-knight round-trips compactly"""
    R = 21
    giv = [
        0 if (r < 9 or r >= 12 or 6 <= c < 15) and (c < 9 or c >= 12 or 6 <= r < 15) else None
        for r in range(R)
        for c in range(R)
    ]
    grids = [X.cell_name(r, c) for r, c in [(0, 0), (0, 12), (6, 6), (12, 0), (12, 12)]]
    doc = {
        "format": "sudoku-puzzle",
        "format_version": 1,
        "board": {"rows": R, "cols": R},
        "digits": 9,
        "givens": giv,
        "rules": [{"type": "box_grid", "origin": o, "box": [3, 3]} for o in grids]
        + [
            {"type": "neighbours", "kind": "antiknight", "area": "r13c13"},
            {"type": "negative", "of": "xv", "area": "r1c13"},
        ],
    }
    X.validate(doc)
    assert X.write(X.read(doc))["rules"][5:] == doc["rules"][5:]
    as_cells = copy.deepcopy(doc)
    as_cells["rules"][5]["area"] = [X.cell_name(r, c) for r in range(12, 21) for c in range(12, 21)]
    assert pencilmark.fingerprint(as_cells) == pencilmark.fingerprint(doc)
    bad = copy.deepcopy(doc)
    bad["rules"][5]["area"] = "r2c2"
    _refuses(bad, "not the origin")
    bad = copy.deepcopy(doc)
    bad["rules"][5]["cells"] = ["r1c1"]
    _refuses(bad, "unknown key")


def test_card_schema():
    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.load(open(ROOT / "docs" / "sudoku-grade.schema.json", encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    cards = [
        pencilmark.rate(CLASSIC),
        pencilmark.rate(
            CLASSIC,
            fields=list(pencilmark.export.DEFAULT_FIELDS) + list(pencilmark.export.OPTIONAL_FIELDS),
            explain=True,
        ),
    ]
    cards += [x["card"] for x in json.load(open(FIXTURES, encoding="utf-8"))]
    for c in cards:
        errs = list(v.iter_errors(c))
        assert not errs, errs[0].message


def test_quality_limits():
    """quality = one object per check keyed by issue code (GRADE.md 4): limit and / or severity (reject / warning / off)"""
    assert pencilmark.rate(CLASSIC, fields=["issues"])["issues"] == []
    low = pencilmark.rate(CLASSIC, fields=["issues", "reject", "warning"], quality={"trivial": {"limit": 0.2}})
    assert [i["code"] for i in low["issues"]] == ["trivial"] and low["reject"] is True and low["warning"] is False
    soft = pencilmark.rate(
        CLASSIC, fields=["issues", "reject", "warning"], quality={"trivial": {"limit": 0.2, "severity": "warning"}}
    )
    assert soft["issues"][0]["severity"] == "warning" and soft["reject"] is False and soft["warning"] is True
    d = pencilmark.from_string(CLASSIC)
    d["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c5", "r1c4"]})
    assert pencilmark.rate(d, fields=["issues"], quality={"decorative": {"severity": "off"}})["issues"] == []
    import pytest

    for bad in (
        {"nope": {"severity": "off"}},
        {"trial": {"limit": 0.5}},
        {"trivial": 0.5},
        {"trial": False},
        {"trial": {"severity": "maybe"}},
        {"spike": {"limit": -1}},
    ):
        with pytest.raises(ValueError):
            pencilmark.rate(CLASSIC, quality=bad)


def test_spec_fields_are_card_keys():
    doc = SF.spec_from_gen({"size": 9, "target_band": "Hard"})
    SF.validate_spec(dict(doc, fields=["difficulty", "time_p80"]))
    import pytest

    with pytest.raises(X.FormatError):
        SF.validate_spec(dict(doc, fields=["time.p80"]))


def test_describe_names_grids():
    """on a multi-grid board, rules confined to some grids say which"""
    R = 21
    giv = [
        0 if (r < 9 or r >= 12 or 6 <= c < 15) and (c < 9 or c >= 12 or 6 <= r < 15) else None
        for r in range(R)
        for c in range(R)
    ]
    rules = [{"type": "box_grid", "origin": o, "box": [3, 3]} for o in ("r1c1", "r1c13", "r7c7", "r13c1", "r13c13")]
    rules += [
        {"type": "region", "kind": "diagonal", "cells": [X.cell_name(i, i) for i in range(9)]},
        {"type": "region", "kind": "diagonal", "cells": [X.cell_name(i, 8 - i) for i in range(9)]},
        {"type": "cage", "sum": 10, "cells": ["r13c1", "r13c2", "r14c1"]},
        {"type": "neighbours", "kind": "antiknight", "area": "r13c13"},
    ]
    doc = {
        "format": "sudoku-puzzle",
        "format_version": 1,
        "board": {"rows": R, "cols": R},
        "digits": 9,
        "givens": giv,
        "rules": rules,
    }
    d = pencilmark.describe(doc)
    assert d["type"] == "Variant Samurai Sudoku"
    assert d["rules"]["X"].endswith("Only in the top-left grid.")
    assert d["rules"]["Killer"].endswith("Only in the bottom-left grid.")
    assert d["rules"]["Anti-Knight"].endswith("Only in the bottom-right grid.")


def test_operators_named_parameters():
    """FORMAT.md 5.1: an operator's parameter has its own key (value / sum / allowed / any_of); positional params are refused"""
    s = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."
    sol = pencilmark.solve(s)
    v = lambda c: sol[(int(c[1]) - 1) * 9 + int(c[3]) - 1]
    a, b, c = "r1c1", "r3c3", "r5c9"
    doc = pencilmark.to_export(s)
    doc["rules"] += [
        {"type": "relation", "op": "difference", "value": abs(v(a) - v(b)), "pairs": [[a, b]]},
        {
            "type": "relation",
            "op": "any_of",
            "any_of": [{"op": "sum", "sum": v(a) + v(c)}, {"op": "equal"}],
            "pairs": [[a, c]],
        },
    ]
    X.validate(doc)
    out = pencilmark.to_export(doc)["rules"]
    assert {"type": "relation", "op": "difference", "value": abs(v(a) - v(b)), "pairs": [[a, b]]} in out, out
    assert pencilmark.rate(doc)["band"]
    for bad_rule in (
        {"type": "relation", "op": "difference", "params": [2], "pairs": [[a, b]]},
        {"type": "relation", "op": "difference", "sum": 2, "pairs": [[a, b]]},
        {"type": "relation", "op": "different", "value": 1, "pairs": [[a, b]]},
    ):
        bad = copy.deepcopy(doc)
        bad["rules"].append(bad_rule)
        with pytest.raises(pencilmark.FormatError):
            X.validate(bad)


def test_tables_reserved():
    """FORMAT.md 6.17: digit tables and the allowed operator are reserved for the planned custom rule type"""
    d = pencilmark.from_string(CLASSIC)
    for rule in (
        {"type": "table", "cells": ["r1c1", "r1c2"], "allowed": [[1, 2], [2, 1]]},
        {"type": "relation", "op": "allowed", "allowed": [[1, 2]], "pairs": [["r1c1", "r3c3"]]},
    ):
        bad = copy.deepcopy(d)
        bad["rules"].append(rule)
        _refuses(bad, "reserved")


def test_canonical_board_key_order():
    """the canonical text does not depend on how board was written (FORMAT.md 8.1)"""
    d = _classic_doc()
    a = pencilmark.dumps(dict(d, board={"rows": 9, "cols": 9}), pretty=False)
    b = pencilmark.dumps(dict(d, board={"cols": 9, "rows": 9}), pretty=False)
    assert a == b and '"board":{"rows":9,"cols":9}' in a
