"""Tests for the pencilmark-puzzle exchange format v1 (docs/formats/puzzle-format.md): round trips, strict reading, schema, fingerprint, interop
strings, ipuz, describe, pencilmark-spec.

    pytest tests/test_format.py        (synthetic puzzles only: tests/fixtures/variants.json, docs/formats/puzzle-format.md examples)
"""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pencilmark.inputs import to_puzzle_json  # noqa: E402

import pencilmark  # noqa: E402
from pencilmark import exchange as X  # noqa: E402
from pencilmark import interop as I  # noqa: E402
from pencilmark import puzzle_json as PJ  # noqa: E402
from pencilmark import spec_format as SF  # noqa: E402
from pencilmark import variants as VR  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "variants.json"
SCHEMA = ROOT / "docs" / "pencilmark-puzzle.schema.json"
CLASSIC = "79.214...8.67..............4.2..78....84.32....16..5.3..............97.2...826.39"
UNIFIED = {}
_pack = None


def pack():
    """synthetic puzzles: the variant fixtures, the docs/formats/puzzle-format.md example files, and generated variant boards"""
    global _pack
    if _pack is None:
        _pack = [v["puzzle"] for v in json.load(open(FIXTURES, encoding="utf-8"))]
        text = (ROOT / "docs" / "formats" / "puzzle-format.md").read_text(encoding="utf-8")
        _pack += [
            json.loads(b)
            for b in re.findall(r"```json\n(.*?)```", text, re.S)
            if b.startswith('{"format": "pencilmark-puzzle"') and "…" not in b
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
            d = json.loads(json.dumps(pencilmark.read.auto(CLASSIC)))
            d["rules"] += extra
            _pack.append(d)
    return _pack


def engine(entry):
    p = PJ.from_json(to_puzzle_json(entry))
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
        assert pencilmark.api._load(v["puzzle"]).N >= 16


# --------------------------------------------------------------------------------------------------------------- strict
def _classic_doc():
    return pencilmark.write.document(CLASSIC)


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
    bad["rules"].append({"type": "custom", "rule": "x"})  # custom rules exist since 1.2: a wrong key is refused as such
    _refuses(bad, "unknown key 'rule'")
    bad = copy.deepcopy(d)
    bad["rules"].append({"type": "custom", "holds": "sum(c) =="})
    _refuses(bad, "custom rule: unexpected")
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
    bad = dict(d, format="pencilmark-puzzle/2")
    _refuses(bad, "not a pencilmark-puzzle")
    bad = copy.deepcopy(d)
    bad["candidates"] = {"R1C3": [1, 2]}
    _refuses(bad, "bad cell name")
    bad = copy.deepcopy(d)
    del bad["rules"][0]["count"]  # box size and repetition count are both required
    _refuses(bad, "count")
    bad = copy.deepcopy(d)
    bad["rules"][0]["count"] = [3, 2]
    _refuses(bad, "does not tile")
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
    bad["ext"] = {"com.example": {}}  # vendor data goes in meta (docs/formats/puzzle-format.md 2.1)
    _refuses(bad, "ext")


def test_required_parameters_off_9x9():
    d = pencilmark.read.auto("1..." + "." * 12)  # 4x4
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
                "format": "pencilmark-puzzle",
                "format_version": 1,
                "board": {"rows": 1, "cols": 1},
                "digits": 1,
                "givens": [0],
                "rules": [{"type": "nope"}],
            }
        )
    )


def test_format_md_examples():
    """the complete example files in docs/formats/puzzle-format.md, the rule family pages and the guides are valid"""
    pages = [
        ROOT / "docs" / "formats" / "puzzle-format.md",
        *sorted((ROOT / "docs").glob("formats/rules/*.mdx")),
        *(ROOT / "docs").glob("guides/**/*.md*"),
    ]
    text = "\n".join(f.read_text(encoding="utf-8") for f in pages)
    n = 0
    for block in re.findall(r"```json\n(.*?)```", text, re.S):
        if not block.startswith('{"format": "pencilmark-puzzle"') or "…" in block:
            continue
        d = json.loads(block)
        X.validate(d)
        X.read(d)
        n += 1
    for f in sorted((ROOT / "docs" / "examples").glob("*.json")):  # the example files the pages draw
        d = json.loads(f.read_text(encoding="utf-8"))
        X.validate(d)
        X.read(d)
        n += 1
    assert n >= 3


# ---------------------------------------------------------------------------------------------------------- fingerprint
def test_fingerprint_stable():
    d = _classic_doc()
    f = pencilmark.fingerprint(d)
    assert f == "68dd0def219928b968ccc31854b2c77dfeab6c0f469ae20466c4ba0735752116", f
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
    d3["rules"] = [{"type": "grid"}] + boxes
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
    t = pencilmark.write.pencilmark(_classic_doc())
    assert '"givens": [\n    7, 9, 0, 2, 1, 4, 0, 0, 0,\n' in t
    assert t.index('"format"') < t.index('"board"') < t.index('"givens"') < t.index('"rules"')
    assert json.loads(t) == X.canonical(_classic_doc())


# ---------------------------------------------------------------------------------------------------------------- interop
def test_plain_string_round_trip():
    d = pencilmark.read.auto(CLASSIC)
    assert pencilmark.write.plain(d) == CLASSIC
    assert d["rules"] == [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}]


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
        d = pencilmark.read.auto(giv)
        d["rules"] += extra
        kinds.setdefault(k, pencilmark.api._load(d))
    d = pencilmark.read.auto(giv)
    d["rules"] = [{"type": "grid"}] + boxes  # jigsaw
    kinds["jigsaw"] = pencilmark.api._load(d)
    d = copy.deepcopy(d)
    d["rules"].append(cage)
    kinds["killer_jigsaw"] = pencilmark.api._load(d)
    d = pencilmark.read.auto("1" + "." * 35)
    d["rules"].append({"type": "cage", "sum": 7, "cells": ["r2c2", "r2c3", "r3c2"]})
    kinds["killer6"] = pencilmark.api._load(d)
    gen4 = pencilmark.api._load(
        {
            "digits": 4,
            "box": "2x2",
            "numbers": "." * 16,
            "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}],
        }
    )
    for k, p in kinds.items():
        s = pencilmark.write.sudokuwiki(p)
        back = pencilmark.api._load(pencilmark.read.auto(s))
        assert I.analyse(back)[0] == k, (k, I.analyse(back))
        assert _semantic(back) == _semantic(p), f"{k}: {s[:12]}..."
        again = pencilmark.write.sudokuwiki(back)  # cage colours may differ; the puzzle may not
        assert again[:3] == s[:3] and _semantic(pencilmark.api._load(pencilmark.read.auto(again))) == _semantic(p)
    try:
        pencilmark.write.sudokuwiki(gen4)
    except pencilmark.NotSupportedError:
        pass
    else:
        raise AssertionError("a 4x4 killer has no sudokuwiki form")


def test_sudokuwiki_board_state():
    # Andrew Stuart's cell codes: given 5, placed 3 (3 + 9), candidates {1, 2} (mask 3 + 18), nothing stored (0)
    b = lambda n: I._b36(n, 2)
    s = "S9B" + b(5) + b(12) + b(21) + b(0) + b(511 + 18) * 77
    d = pencilmark.read.auto(s)
    assert d["givens"][:5] == [5, 3, 0, 0, 0] and d["candidates"] == {"r1c3": [1, 2]}
    again = pencilmark.write.sudokuwiki(d)
    assert again == "S9B" + b(5) + b(3) + b(21) + b(529) * 78  # placed digits come back as givens
    assert pencilmark.read.auto(again)["candidates"] == {"r1c3": [1, 2]}


def test_sudokuwiki_refusals():
    s = "S9B" + "zz" * 81  # beyond the largest candidate mask
    try:
        pencilmark.read.auto(s)
    except pencilmark.NotSupportedError:
        return
    raise AssertionError("cell values above the candidate masks must be refused")


# ------------------------------------------------------------------------------------------------------------------- ipuz
def test_ipuz_export():
    ip = pencilmark.write.ipuz(_classic_doc())
    assert ip["version"] == "http://ipuz.org/v2" and ip["kind"] == ["http://ipuz.org/sudoku#1"]
    assert ip["puzzle"][0][:3] == [7, 9, 0] and ip["boxes"] is True
    assert ip[f"{I.IPUZ_NS}:puzzle"]["format"] == "pencilmark-puzzle"
    killer = pencilmark.api._load(
        {
            "digits": 4,
            "box": "2x2",
            "numbers": "." * 16,
            "regions": [{"kind": "cage", "cells": ["r1c1", "r1c2"], "sum": 3}],
        }
    )
    ip = pencilmark.write.ipuz(killer)
    assert "http://ipuz.org/sudoku/killersudoku#1" in ip["kind"] and ip["cages"] == [
        {"cells": [[1, 1], [2, 1]], "value": 3}
    ]
    d = _classic_doc()
    d["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c3", "r2c3"]})
    try:
        pencilmark.write.ipuz(d)
    except pencilmark.NotSupportedError as e:
        assert "line" in str(e)
    else:
        raise AssertionError("ipuz cannot carry a thermo")


# --------------------------------------------------------------------------------------------------------------- describe
def _with(rules, D=9):
    d = pencilmark.read.auto("." * D * D)
    d["rules"] += rules
    return d


def test_describe_names():
    assert pencilmark.describe(_classic_doc())["type"] == "Sudoku"
    assert pencilmark.describe(pencilmark.read.auto("." * 36))["type"] == "Mini Sudoku"
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
    assert pencilmark.describe(pencilmark.api._load({"layout": "samurai", "numbers": ""}))["type"] == "Samurai Sudoku"
    assert (
        pencilmark.describe(pencilmark.api._load({"layout": "butterfly", "numbers": ""}))["type"] == "Butterfly Sudoku"
    )
    assert (
        pencilmark.describe(
            pencilmark.api._load(
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


# ---------------------------------------------------------------------------------------------------------- pencilmark-spec
def test_card_fields():
    """field mask = top-level keys, explanation levels, the issues / reject shape (docs/formats/grade-card.md)"""
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
    d = pencilmark.read.auto(CLASSIC)
    d["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c5", "r1c4"]})  # true, but never needed
    i = pencilmark.rate(d, fields=["issues", "reject"])
    dec = next(x for x in i["issues"] if x["code"] == "decorative")
    assert i["reject"] is True and dec["rules"] == [1] and "rule 1" in dec["text"], i


def _houses(doc):
    p = X.read(doc)
    return [(g.kind, g.cells) for g in p.groups]


def test_houses():
    """grid gives rows and columns, box_grid adds regular boxes, box / row / column are explicit, nothing is inferred;
    the writer finds grids in any house order (docs/formats/puzzle-format.md 6.1)"""
    classic = pencilmark.read.auto(CLASSIC)
    h = _houses(classic)
    assert [k for k, _ in h] == ["row"] * 9 + ["col"] * 9 + ["box"] * 9
    boxes = [
        {"type": "box", "cells": [X.cell_name(br + i, bc + j) for i in range(3) for j in range(3)]}
        for br in (0, 3, 6)
        for bc in (0, 3, 6)
    ]
    jig = copy.deepcopy(classic)
    jig["rules"] = [{"type": "grid"}] + boxes
    assert _houses(jig) == h
    only_boxes = copy.deepcopy(classic)
    only_boxes["rules"] = boxes
    assert [k for k, _ in _houses(only_boxes)] == ["box"] * 9  # no rows / columns without a grid
    latin = copy.deepcopy(classic)
    latin["rules"] = [{"type": "grid"}]
    assert [k for k, _ in _houses(latin)] == ["row"] * 9 + ["col"] * 9
    # a jigsaw written from the engine: one grid plus its pieces
    pieces = copy.deepcopy(boxes)
    pieces[0]["cells"][8], pieces[1]["cells"][6] = pieces[1]["cells"][6], pieces[0]["cells"][8]
    jig2 = copy.deepcopy(classic)
    jig2["rules"] = [{"type": "grid"}] + pieces
    assert [r["type"] for r in X.write(X.read(jig2))["rules"]] == ["grid"] + ["box"] * 9
    # explicit houses whose rows / columns make a grid are written as one
    expl = copy.deepcopy(classic)
    expl["rules"] = (
        [{"type": "column", "cells": [X.cell_name(r, c) for r in range(9)]} for c in range(9)]
        + boxes
        + [{"type": "row", "cells": [X.cell_name(r, c) for c in range(9)]} for r in range(9)]
    )
    assert X.write(X.read(expl))["rules"] == [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}]
    sam = pencilmark.api._load({"layout": "samurai", "numbers": ""})
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
        assert doc["format"] == "pencilmark-spec"
        back = SF.spec_to_gen(json.loads(json.dumps(doc)))
        norm = lambda x: _plan_of(Spec.from_any(x))
        assert norm(back) == norm(s), (s, back)
    bad = SF.spec_from_gen(specs[0])
    bad["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2"]})
    for extra in (
        {"rules": bad["rules"]},
        {"givens": {"mask": [1] * 81}},
        {"where": {"time": [5, 20]}},
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
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": R, "cols": R},
        "digits": 9,
        "givens": giv,
        "rules": [
            dict(
                {"type": "box_grid"},
                **({"origin": X.cell_name(r, c)} if (r, c) != (0, 0) else {}),
                box=[3, 3],
                count=[3, 3],
            )
            for r, c in grids
        ],
    }
    p = X.read(doc)
    p.groups.sort(key=lambda g: (g.kind != "box", g.kind != "row", g.cells))  # boxes first, then rows, then columns
    p.finalize()
    out = X.write(p)
    assert [r for r in out["rules"] if r["type"] in ("box_grid", "box", "row", "column")] == doc["rules"]
    assert pencilmark.fingerprint(out) == pencilmark.fingerprint(doc)


def test_area_scope():
    """area = a grid's origin or a cell list (docs/formats/puzzle-format.md 5); one grid of a samurai with anti-knight round-trips compactly"""
    R = 21
    giv = [
        0 if (r < 9 or r >= 12 or 6 <= c < 15) and (c < 9 or c >= 12 or 6 <= r < 15) else None
        for r in range(R)
        for c in range(R)
    ]
    grids = [X.cell_name(r, c) for r, c in [(0, 0), (0, 12), (6, 6), (12, 0), (12, 12)]]
    doc = {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": R, "cols": R},
        "digits": 9,
        "givens": giv,
        "rules": [{"type": "box_grid", "origin": o, "box": [3, 3], "count": [3, 3]} for o in grids]
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
    schema = json.load(open(ROOT / "docs" / "pencilmark-grade.schema.json", encoding="utf-8"))
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
    """quality = one object per check keyed by issue code (docs/formats/grade-card.md 4): limit and / or severity (reject / warning / off)"""
    assert pencilmark.rate(CLASSIC, fields=["issues"])["issues"] == []
    low = pencilmark.rate(CLASSIC, fields=["issues", "reject", "warning"], quality={"trivial": {"limit": 0.2}})
    assert [i["code"] for i in low["issues"]] == ["trivial"] and low["reject"] is True and low["warning"] is False
    soft = pencilmark.rate(
        CLASSIC, fields=["issues", "reject", "warning"], quality={"trivial": {"limit": 0.2, "severity": "warning"}}
    )
    assert soft["issues"][0]["severity"] == "warning" and soft["reject"] is False and soft["warning"] is True
    d = pencilmark.read.auto(CLASSIC)
    d["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c5", "r1c4"]})
    assert (
        pencilmark.rate(
            d, fields=["issues"], quality={"decorative": {"severity": "off"}, "unusual": {"severity": "off"}}
        )["issues"]
        == []
    )
    import pytest

    for bad in (
        {"nope": {"severity": "off"}},
        {"trial": {"limit": 0.5}},
        {"trivial": 0.5},
        {"trial": False},
        {"trial": {"severity": "maybe"}},
        {"thin": {"limit": -1}},
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
    rules = [
        {"type": "box_grid", "origin": o, "box": [3, 3], "count": [3, 3]}
        for o in ("r1c1", "r1c13", "r7c7", "r13c1", "r13c13")
    ]
    rules += [
        {"type": "region", "kind": "diagonal", "cells": [X.cell_name(i, i) for i in range(9)]},
        {"type": "region", "kind": "diagonal", "cells": [X.cell_name(i, 8 - i) for i in range(9)]},
        {"type": "cage", "sum": 10, "cells": ["r13c1", "r13c2", "r14c1"]},
        {"type": "neighbours", "kind": "antiknight", "area": "r13c13"},
    ]
    doc = {
        "format": "pencilmark-puzzle",
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
    """docs/formats/puzzle-format.md 5.1: an operator's parameter has its own key (value / sum / allowed / any_of); positional params are refused"""
    s = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."
    sol = pencilmark.solve(s)
    v = lambda c: sol[(int(c[1]) - 1) * 9 + int(c[3]) - 1]
    a, b, c = "r1c1", "r3c3", "r5c9"
    doc = pencilmark.write.document(s, solution=True, describe=True)
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
    out = pencilmark.write.document(doc, solution=True, describe=True)["rules"]
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
    """docs/formats/puzzle-format.md 6.17: digit tables and the allowed operator are reserved for the planned custom rule type"""
    d = pencilmark.read.auto(CLASSIC)
    for rule in (
        {"type": "table", "cells": ["r1c1", "r1c2"], "allowed": [[1, 2], [2, 1]]},
        {"type": "relation", "op": "allowed", "allowed": [[1, 2]], "pairs": [["r1c1", "r3c3"]]},
    ):
        bad = copy.deepcopy(d)
        bad["rules"].append(rule)
        _refuses(bad, "reserved")


def test_canonical_board_key_order():
    """the canonical text does not depend on how board was written (docs/formats/puzzle-format.md 8.1)"""
    d = _classic_doc()
    a = pencilmark.write.pencilmark(dict(d, board={"rows": 9, "cols": 9}), pretty=False)
    b = pencilmark.write.pencilmark(dict(d, board={"cols": 9, "rows": 9}), pretty=False)
    assert a == b and '"board":{"rows":9,"cols":9}' in a


def test_card_field_registry_matches_grade_md():
    """every default / optional key of docs/formats/grade-card.md section 1 is built by the card-field registry (export.FIELDS), is
    accepted by card_fields(), and the registry builds nothing the page does not list"""
    from pencilmark import export as E2

    text = (ROOT / "docs" / "formats" / "grade-card.md").read_text(encoding="utf-8")
    keys = set()
    for row in re.findall(r"^\| (`[^|]+`) \| (default|optional)", text, re.M):
        keys |= set(re.findall(r"`(\w+)`", row[0]))
    built = {n for n, _ in E2.FIELDS} | {"reject", "warning"}  # issues builds reject / warning
    outside = {"elapsed", "time_mean", "time_pNN"}  # set by rate() / the time_* entry
    assert keys - outside <= built, keys - outside - built
    assert {n for n, _ in E2.FIELDS} - {"time_*"} <= keys, {n for n, _ in E2.FIELDS} - keys
    E2.card_fields(sorted(keys - {"time_pNN"}) + ["time_p80"])  # every documented field is accepted


def test_check_registry_matches_quality_and_grade_md():
    """every quality code has a check, and docs/formats/grade-card.md section 4 lists exactly these codes"""
    from pencilmark import publish_flags as PF

    codes = {k for _, ks in PF.CHECKS for k in ks} | set(PF.RULE_CODES)
    assert codes == set(PF.QUALITY)
    text = (ROOT / "docs" / "formats" / "grade-card.md").read_text(encoding="utf-8")
    table = set(re.findall(r"^\| `(\w+)` \| (?:reject|warning)", text, re.M))
    assert table == codes, table ^ codes


def test_line_registry_matches_schema_palette_docs():
    """rules/line.py is the one list of line kinds: the JSON Schema, the default colours and the rule page agree"""
    from pencilmark.rules import LINE

    schema = json.loads((ROOT / "docs" / "pencilmark-puzzle.schema.json").read_text(encoding="utf-8"))
    rl = schema["$defs"]["rule_line"]
    assert set(rl["properties"]["kind"]["enum"]) == set(LINE)
    assert {p for k in LINE.values() for p in k.params} <= set(rl["properties"])
    palette = json.loads((ROOT / "docs" / "palette.json").read_text(encoding="utf-8"))["lines"]
    assert set(LINE) <= set(palette), set(LINE) - set(palette)
    page = (ROOT / "docs" / "formats" / "rules" / "lines-and-arrows.mdx").read_text(encoding="utf-8")
    assert all(f"| `{k}` |" in page for k in LINE), [k for k in LINE if f"| `{k}` |" not in page]


def test_style_line_widths_match_registry():
    """docs/library/drawing-style.md states the width of every line drawn with a number width in rules/line.py"""
    from pencilmark.rules import LINE

    text = (ROOT / "docs" / "library" / "drawing-style.md").read_text(encoding="utf-8")
    for k in LINE.values():
        if isinstance(k.width, (int, float)):
            row = re.search(rf"^\| `line` `{k.kind}` \|[^\n]*", text, re.M)
            assert row and f"width {k.width}" in row.group(0), (k.kind, k.width, row and row.group(0))


def test_edge_registry_matches_schema_docs():
    """rules/edge.py is the one list of edge kinds: the JSON Schema and the rule page agree"""
    from pencilmark.rules import EDGE

    schema = json.loads((ROOT / "docs" / "pencilmark-puzzle.schema.json").read_text(encoding="utf-8"))
    re_ = schema["$defs"]["rule_edge"]["properties"]
    assert set(re_["kind"]["enum"]) == set(EDGE)
    for k in EDGE.values():
        if k.param:
            assert k.param in re_, k.kind
        if k.choices:
            assert set(re_[k.param]["enum"]) == set(k.choices), k.kind
    neg = schema["$defs"]["rule_negative"]["properties"]["of"]["enum"]
    assert {k for k, v in EDGE.items() if v.negative} <= set(neg)
    assert not {k for k, v in EDGE.items() if not v.negative} & set(neg)
    page = (ROOT / "docs" / "formats" / "rules" / "edges-and-corners.mdx").read_text(encoding="utf-8")
    assert all(f"| `{k}` |" in page for k in EDGE), [k for k in EDGE if f"| `{k}` |" not in page]


def test_cell_registry_matches_schema_docs():
    """rules/cell.py is the one list of cell kinds: the JSON Schema and the rule page agree"""
    from pencilmark.rules import CELL

    schema = json.loads((ROOT / "docs" / "pencilmark-puzzle.schema.json").read_text(encoding="utf-8"))
    rc = schema["$defs"]["rule_cell"]["properties"]
    assert set(rc["kind"]["enum"]) == set(CELL)
    assert {k.param for k in CELL.values() if k.param} <= set(rc)
    neg = schema["$defs"]["rule_negative"]["properties"]["kind"]["enum"]
    assert set(neg) == {k for k, v in CELL.items() if v.negative}
    page = (ROOT / "docs" / "formats" / "rules" / "cell-clues.mdx").read_text(encoding="utf-8")
    assert all(f"`{k}`" in page for k in CELL), [k for k in CELL if f"`{k}`" not in page]


def test_region_sum_breaks_only_at_boxes():
    """an extra region overlapping a box does not split a region-sum line inside that box (it used to: the cell -> box
    map took the extra region for cells in both, imposing a sum equality the rule does not state)"""
    d = pencilmark.write.document(CLASSIC, solution=True, describe=True)
    d["rules"].append({"type": "region", "kind": "extra", "cells": [f"r{r}c{c}" for r in (2, 3, 4) for c in (2, 3, 4)]})
    d["rules"].append({"type": "line", "kind": "region_sum", "cells": ["r1c1", "r2c2", "r3c3"]})
    assert not [c for c in pencilmark.api._load(d).constraints if c.get("line_kind") == "region_sum"]


def test_lockout_puzzle_grades():
    """a lockout line reaches the engine and grades (the line matrix only reads and writes: a build of the engine without
    the lockout line kind passed every other test)"""
    d = pencilmark.write.document(CLASSIC, solution=True, describe=True)
    d["rules"].append({"type": "line", "kind": "lockout", "cells": ["r2c7", "r2c8", "r2c9"]})  # 9 . 4 in the solution
    card = pencilmark.rate(d)
    assert card["band"] and card["difficulty"] is not None


def test_entropic_groups_with_an_empty_third_round_trip():
    """sudoku.coach's fixed thirds on a 4x4 ({1,2,3}, {4}, {}) read and write back: the reader compared the sorted groups
    with the engine's unsorted ones, so an empty group (sorted first) never matched"""
    d = {"format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4, "givens": [0] * 16,
         "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]},
                   {"type": "line", "kind": "entropic", "groups": [[1, 2, 3], [4], []], "cells": ["r1c1", "r1c2"]}]}  # fmt: skip
    doc = pencilmark.write.document(d, solution=True, describe=True)
    assert (
        doc["rules"][1]["groups"] == [[1, 2, 3], [4], []]
        and pencilmark.write.document(doc, solution=True, describe=True) == doc
    )


def test_malformed_values_are_format_errors():
    """found by mutating valid files: a rule type or kind that is not a string, a meta that is not an object and a
    true in the solution raised TypeError (or crashed load) instead of a FormatError"""
    base = json.loads((ROOT / "docs" / "examples" / "classic.json").read_text(encoding="utf-8"))
    rule = {"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2"]}
    sol = list(base.get("solution") or [])
    bads = [
        dict(base, rules=base["rules"] + [dict(rule, type={"a": 1})]),
        dict(base, rules=base["rules"] + [dict(rule, kind=["thermo"])]),
        dict(base, meta=-1),
    ]
    if sol:
        bads.append(dict(base, solution=[True if i == 0 else v for i, v in enumerate(sol)]))
    for bad in bads:
        with pytest.raises(pencilmark.FormatError):
            pencilmark.validate(bad)


def test_fog_rule_reads_writes_and_is_graded_under_the_fog():
    """fog of war (6.19): validated, carried through load / export, solved and counted as usual (fog changes no
    solution), and graded under the fog by rate: a route the fog stops is band Unknown, never the revealed grade"""
    import pytest

    import pencilmark as pm
    from pencilmark.exchange import FormatError

    giv = [
        int(c) if c != "." else 0
        for c in "4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......"
    ]
    fog = {"type": "fog", "lit": ["r1c1", "r5c5"], "triggers": [{"when": ["r1c1"], "light": ["r9c9"]}]}
    doc = {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": 9, "cols": 9},
        "digits": 9,
        "givens": giv,
        "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}, fog],
    }
    doc["solution"] = pm.solve(dict(doc, rules=doc["rules"][:1]))  # the same puzzle without its fog
    with pytest.raises(Exception, match="needs its solution"):
        pm.api._load(dict(doc, solution=None))
    pm.validate(doc)
    p = pm.api._load(doc)
    assert p.fog["lit"] == ["r1c1", "r5c5"] and len(pm.solve(p)) == 81
    out = pm.write.document(p, solution=True, describe=True)
    out = out.get("puzzle", out)
    assert [r for r in out["rules"] if r["type"] == "fog"] == [fog]
    card = pm.rate(doc, fields=["band", "difficulty", "contains"])
    assert card["fog"]["lit_start"] == 2 and "solved" in card["fog"]
    if not card["fog"]["solved"]:  # stopped by the fog: Unknown, never the revealed grade
        assert card["band"] == "Unknown" and card["difficulty"] is None and card["stopped_at_step"] >= 1
    for bad in (
        {"type": "fog", "lit": ["r1c1"], "reveal": "3x3"},
        {"type": "fog", "lit": "r1c1"},
        {"type": "fog", "lit": ["r1c1"], "triggers": [{"when": ["r1c1"]}]},
    ):
        with pytest.raises(FormatError):
            pm.validate(dict(doc, rules=[doc["rules"][0], bad]))


def test_fog_route_reveals_and_places_only_what_is_seen():
    """pencilmark.fog.route: a classic with everything lit solves like the classic; with one box lit it still solves,
    revealing as digits land, and every placement is correct (route raises otherwise)"""
    import pencilmark as pm
    from pencilmark import fog

    giv = [
        int(c) if c != "." else 0
        for c in "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79"
    ]
    base = {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": 9, "cols": 9},
        "digits": 9,
        "givens": giv,
        "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}],
    }
    base["solution"] = pm.solve(base)
    every = [f"r{r}c{c}" for r in range(1, 10) for c in range(1, 10)]
    res = fog.route(dict(base, rules=base["rules"] + [{"type": "fog", "lit": every}]))
    assert res["solved"] and res["reveals"] == 0
    res = fog.route(dict(base, rules=base["rules"] + [{"type": "fog", "lit": ["r1c1", "r1c2", "r1c3"]}]))
    assert res["solved"] and res["reveals"] > 0
    assert all(s["place"] is None or s["place"][0] for s in res["steps"])


def test_quality_preset():
    """quality {"preset": "standard"}: only its checks, at reject; a check named next to it overrides it"""
    from pencilmark.publish_flags import quality_limits

    q = quality_limits({"preset": "standard"})
    assert {k for k, v in q.items() if v["severity"] != "off"} == {"decorative", "trivial", "trial", "thin", "unusual"}
    assert q["thin"]["severity"] == "reject" and q["tedious"]["severity"] == "off"
    q = quality_limits(
        {"preset": "standard", "thin": {"limit": 0.2, "severity": "warning"}, "tedious": {"severity": "warning"}}
    )
    assert q["thin"] == {"limit": 0.2, "severity": "warning"} and q["tedious"]["severity"] == "warning"
    with pytest.raises(ValueError):
        quality_limits({"preset": "lenient"})


def test_quality_opt_in_checks():
    """opt-in checks are off by default; a severity or a limit turns one on"""
    import pencilmark as pm
    from pencilmark.publish_flags import OPT_IN, quality_limits

    q = quality_limits()
    assert all(q[k]["severity"] == "off" for k in OPT_IN)
    q = quality_limits({"winding": {"limit": 0.5}, "asymmetric": {"severity": "warning"}})
    assert q["winding"] == {"limit": 0.5, "severity": None} and q["asymmetric"]["severity"] == "warning"
    grid = "4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......"
    c = pm.rate(grid, fields=["issues"], quality={"asymmetric": {"severity": "warning"}})
    assert [i["code"] for i in c["issues"]] == ["asymmetric"]  # its givens have no symmetry
    c = pm.rate(grid, fields=["issues"])
    assert not any(i["code"] in OPT_IN for i in c["issues"])


def test_line_part_without_its_line_is_written():
    """a constraint tagged line_kind whose line is missing (a reader that built only the compiled part) is written as a
    rule, not dropped as the line's part"""
    p = pencilmark.api._load(_classic_doc())
    p.constraints.append({"type": "equal_sum", "segments": [[2], [3, 4]], "line_kind": "region_sum"})
    out = pencilmark.write.document(p)
    assert {"type": "line", "kind": "region_sum", "cells": ["r1c3", "r1c4", "r1c5"]} in out["rules"]


def test_fog_card():
    """a fog puzzle the route solves under the fog: its band, a difficulty and time, and what the fog did"""
    import pencilmark as pm

    doc = {
        "format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4,
        "givens": [0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 0, 3, 0, 3, 0, 0],
        "solution": [2, 1, 3, 4, 3, 4, 1, 2, 1, 2, 4, 3, 4, 3, 2, 1],
        "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]},
                  {"type": "fog", "lit": ["r2c3", "r3c2", "r3c4", "r4c2"], "triggers": [{"when": ["r1c1"], "light": ["r1c2", "r2c1"]}]}],
    }  # fmt: skip
    card = pm.rate(doc, fields=["band", "difficulty", "time", "contains", "issues"])
    assert card["band"] == "Very Easy" and card["difficulty"] > 0 and card["time"] > 0
    assert card["fog"] == {"lit_start": 4, "reveals": 1, "rounds": 2, "solved": True}
    assert card["issues"] is None  # publishing checks are not run under the fog yet


def test_fog_lighting_everything_is_the_plain_card():
    """one algorithm for every card: a fog rule that lights every cell grades exactly like the puzzle without fog"""
    import pencilmark as pm

    doc = pm.read.auto(CLASSIC)
    lit = [f"r{r}c{c}" for r in range(1, 10) for c in range(1, 10)]
    fogged = dict(
        doc, solution=[int(x) for x in pm.solve(doc)], rules=list(doc["rules"]) + [{"type": "fog", "lit": lit}]
    )
    a = pm.rate(doc, fields=["band", "difficulty", "time"])
    b = pm.rate(fogged, fields=["band", "difficulty", "time"])
    assert (a["band"], a["difficulty"], a["time"]) == (b["band"], b["difficulty"], b["time"])
    assert b["fog"]["solved"] and b["fog"]["reveals"] == 0
