"""The custom rule language (pencilmark.rules.custom, docs/formats/rules/custom.mdx): the language itself, then rules in
puzzle files (validation, reading, grading, writing back)."""

import json

import pytest

from pencilmark.rules.custom import ABSENT, Env, LangError, canonical, check, describe, evaluate, holds, parse

ROW = [f"r1c{c}" for c in range(1, 10)]


def grid_of(digits, cells=ROW):
    return dict(zip(cells, digits))


def test_design_examples():
    g = grid_of([5, 3, 2, 9, 1, 4, 6, 7, 8])
    cells = {"c": ROW[:3], "ray": ROW}
    assert holds("2*max(c) == sum(c)", cells, g)  # 2 * 5 == 5 + 3 + 2
    assert holds("count(x for x in c if odd(x)) == 2", cells, g)  # 5, 3
    assert holds("let s = sum(c); s in {10, 15, 20}", cells, g)
    assert holds("sum(upto(ray, x => x == 9)) == 19", cells, g)  # 5 + 3 + 2 + 9
    assert holds("len(seen(ray)) == 2", cells, g)  # 5, 9
    assert holds("ray[ray[2]] == 2", cells, g)  # ray[3]
    assert holds("sum(take(ray[1], ray)) == 20", cells, g)  # x-sum: the first 5 digits
    assert holds("len(take_while(ray, x => x <= 5)) == 3", cells, g)  # watchtower-style: 5, 3, 2 then 9 blocks


def test_single_cell_is_a_number_and_positions():
    g = grid_of([5, 3, 2, 9, 1, 4, 6, 7, 8])
    cells = {"o": ["r1c4"], "c": ROW}
    assert holds("o == 9 and o == max(c)", cells, g)  # no o[1]
    assert holds("count(x for x in c if x == col(x)) == 0", cells, g)
    assert holds("box(r1c4) == 2 and row(o) == 1", cells, g)
    assert evaluate(parse("box(r4c5)"), Env({}, {"r4c5": 1}, (2, 3))) == 4  # 6 x 6: boxes of 2 rows by 3 columns


def test_absent_values():
    g = grid_of([1, 2, 3])
    cells = {"L": ROW[:3]}
    assert not holds("L[4] == 3", cells, g)
    assert not holds("L[4] != 3", cells, g)  # a comparison with absent is false, != too
    assert holds("not defined(L[4]) and defined(L[3])", cells, g)
    assert holds("(L[4] ?? 0) == 0", cells, g)
    assert holds("count(i for i in {1..3} if abs(L[i] - (L[i + 1] ?? 99)) == 1) == 2", cells, g)
    assert not holds("1 / (L[1] - 1) > 0", cells, g)  # division by zero is absent
    assert not holds("sum(upto(L, x => x == 9)) == 6", cells, g)  # no 9: the clue cannot be read


def test_numbers_are_exact():
    g = grid_of([1, 2, 3, 4])
    cells = {"L": ROW[:4]}
    assert holds("median(L) * 2 == 5", cells, g)  # 2.5
    assert holds("7 div 2 == 3 and -7 mod 3 == 2 and 2 ** 3 == 8", cells, g)
    assert holds("prime(concat([L[1], L[3]]))", cells, g)  # 13
    assert holds("min(L[1], L[4]) == 1 and max(L) == 4", cells, g)


def test_booleans_are_values():
    g = grid_of([2, 4, 5])
    cells = {"L": ROW[:3]}
    assert holds("odd(L[1]) == odd(L[2])", cells, g)
    assert holds("num(odd(L[3])) + num(even(L[3])) == 1", cells, g)
    assert holds("(if L[1] < L[2] then L[2] else L[1]) == 4", cells, g)
    assert holds("count([odd(x) for x in L]) == 1", cells, g)  # a list of conditions counts the true ones


def test_several_bindings():
    g = grid_of([1, 6, 3, 8])
    assert holds("let a = L[1], b = a + L[2]; b == 7", {"L": ROW[:4]}, g)


def test_helper_functions_and_lambdas():
    g = grid_of([1, 6, 3, 8])
    cells = {"L": ROW[:4]}
    assert holds("let close(a, b) = abs(a - b) <= 2; close(L[1], L[3]) and not close(L[1], L[2])", cells, g)
    assert holds("all([(x mod 2 == 0) or x < 4 for x in L])", cells, g)
    assert holds("position(L, x => x > 5) == 2", cells, g)


def test_survey_rules():
    """rules from the 1,000-puzzle validation, in the revised syntax"""
    g = grid_of([2, 1, 3, 4])  # the first digit (2) says where the 1 is
    # 000OZL: one digit equals the sum of the other three
    assert holds("any(2 * x == sum(c) for x in c)", {"c": ROW[:4]}, grid_of([6, 1, 2, 3]))
    # distinct cage sums
    cells = {"cages": [ROW[:2], ROW[2:4]]}
    assert holds("count_distinct([sum(k) for k in cages]) == len(cages)", cells, grid_of([1, 2, 4, 5]))
    # look-and-say little killer: "25" = two 5s on the diagonal
    assert holds("count(x for x in d if x == 5) == 2", {"d": ROW[:4]}, grid_of([5, 1, 5, 2]))
    # 159 indexing: the digit in column 1 gives the position of the 1 in its row
    assert holds("row1[row1[1]] == 1", {"row1": ROW[:4]}, g)
    # parity stripe: alternating parity for the first n cells, n = the first digit
    stripe = "let n = ray[1]; all(odd(ray[i]) != odd(ray[i + 1]) for i in {1..n - 1})"
    assert holds(stripe, {"ray": ROW[:4]}, grid_of([3, 2, 5, 6]))


def test_canonical_form_round_trips():
    for src in [
        "2*max(c)==sum(c)",
        "count(x for x in c if odd(x))  ==  2",
        "let s = sum(c); s in {10, 15, 20}",
        "a - (b - c) == (a - b) - c",
        "-x ** 2 == 0 - (x ** 2)",
        "not (a == b) or c in {1..4}",
        "sum(take(ray[1], ray)) == 20",
        "(a, b) => abs(a - b) != 4",
        "if a then b else c",
    ]:
        once = canonical(src)
        assert canonical(once) == once and parse(once) == parse(src), (src, once)
    assert canonical("2*max(c)==sum(c)") == "2 * max(c) == sum(c)"
    assert canonical("(a-b)-c") == "a - b - c" and canonical("a-(b-c)") == "a - (b - c)"


def test_check_refuses_malformed_rules():
    names = {"c", "ray"}
    assert check(parse("sum(c) == 10"), names) == "bool"
    for bad, why in [
        ("sum(d) == 1", "unknown name"),
        ("total(c) == 1", "unknown function"),
        ("sum(c, 2) == 1", "argument"),
        ("odd(c[1]) + 1 == 2", r"num\(b\)"),
        ("sum(c) and true", "conditions"),
        ("all(x for x in c if odd(x))", "condition per element"),
    ]:
        with pytest.raises(LangError, match=why):
            check(parse(bad), names)
    for bad in ("1 < 2 < 3", "sum(c == ", "c[1..]", "let x = 1 x"):
        with pytest.raises(LangError):
            parse(bad)


def test_describe_reads_the_rule():
    assert describe("2 * max(c) == sum(c)") == "2 times the largest of c equals the sum of c"
    assert describe("count(x for x in c if odd(x)) == 2") == "the number of the x in c with x is odd equals 2"
    assert describe("abs(a - b) >= 5") == "the difference between a and b is at least 5"
    assert describe("all(odd(x) for x in c)") == "for every x in c: x is odd"
    assert describe("(a + b) * c == 9") == "(a plus b) times c equals 9"
    assert describe("L[i + 1] == 3") == "cell (i plus 1) of L equals 3"
    assert "up to the first cell where" in describe("sum(upto(ray, x => x == 9)) == 15")


def test_absent_is_a_singleton():
    assert repr(ABSENT) == "ABSENT"


def test_whole_rules_with_scopes():
    from pencilmark.rules.custom import rule_holds

    g = {f"r{r}c{c}": v for r, row in enumerate([[1, 2], [3, 4]], 1) for c, v in enumerate(row, 1)}
    # no two orthogonal neighbors differ by 2: 1-3 (r1c1, r2c1) and 2-4 do -> false; excepting those pairs -> true
    rule = {"type": "custom", "holds": "(a, b) => abs(a - b) != 2", "scope": {"pairs": "orthogonal"}}
    assert not rule_holds(rule, g, (2, 2))
    rule["scope"]["except"] = [["r1c1", "r2c1"], ["r1c2", "r2c2"]]
    assert rule_holds(rule, g, (2, 2))
    # every 2 x 2 window holds two odd and two even digits
    win = {"type": "custom", "holds": "w => count(x for x in w if odd(x)) == 2", "scope": {"windows": [2, 2]}}
    assert rule_holds(win, g, (2, 2))
    # each cell with its king neighbors: the 4 sees 1, 2, 3 (all smaller)
    nb = {"type": "custom", "cells": {"t": ["r2c2"]}, "holds": "(x, N) => all(y < x for y in N)",
          "scope": {"cells": "t", "neighbors": "king"}}  # fmt: skip
    assert rule_holds(nb, g, (2, 2))
    # "each": distinct sums over every cage of a list
    each = {
        "type": "custom",
        "cells": {"cg": [["r1c1", "r1c2"], ["r2c1", "r2c2"]]},
        "each": "cg",
        "holds": "sum(cg) >= 3",
    }
    assert rule_holds(each, g, (2, 2))


def test_describe_rule():
    from pencilmark.rules.custom import describe_rule

    pair = {"holds": "(a, b) => abs(a - b) != 4", "scope": {"pairs": "orthogonal"}}
    assert (
        describe_rule(pair)
        == "For every pair of orthogonal neighbors a, b: the difference between a and b differs from 4."
    )
    nb = {"holds": "(x, N) => any(abs(x - y) == 1 for y in N)", "scope": {"cells": "u", "neighbors": "orthogonal"}}
    assert describe_rule(nb).startswith("For every cell x of u, with N its orthogonal neighbors: for some y in N")
    assert describe_rule({"cells": {"c": ["r1c1"]}, "holds": "c == 5"}) == "C equals 5."


# ---------------------------------------------------------------------------------------------------- in puzzle files
import copy  # noqa: E402

import pencilmark  # noqa: E402

GRID = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."


def _doc_with(*rules):
    doc = pencilmark.write.document(GRID, solution=True, describe=True)
    doc["rules"] += [copy.deepcopy(r) for r in rules]
    return doc


def test_custom_rules_read_grade_and_round_trip():
    sol = pencilmark.write.document(GRID, solution=True, describe=True)["solution"]
    total = sol[0] + sol[1] + sol[9]  # r1c1, r1c2, r2c1
    cage = {"type": "custom", "cells": {"c": ["r1c1", "r1c2", "r2c1"]}, "holds": f"sum(c)=={total}", "label": "sum"}
    pairs = {"type": "custom", "holds": "(a, b) => a != b", "scope": {"pairs": "orthogonal"}}
    doc = _doc_with(cage, pairs)
    pencilmark.validate(doc)
    card = pencilmark.rate(doc)
    assert card["band"] in ("Hard", "Medium", "Easy") and card["difficulty"] > 0
    out = pencilmark.write.document(doc, solution=True, describe=True)
    rules = [r for r in out["rules"] if r["type"] == "custom"]
    assert rules[0]["holds"] == f"sum(c) == {total}" and rules[0]["label"] == "sum"  # canonical spelling, label kept
    assert rules[1]["scope"] == {"pairs": "orthogonal"}
    assert pencilmark.fingerprint(doc) == pencilmark.fingerprint(out)
    respelled = _doc_with(dict(cage, holds=f"sum( c ) == {total}"), pairs)
    assert pencilmark.fingerprint(respelled) == pencilmark.fingerprint(doc)  # spelling does not change the puzzle


def test_custom_rule_that_contradicts_the_solution_has_none():
    doc = _doc_with({"type": "custom", "cells": {"c": ["r1c1", "r1c2"]}, "holds": "sum(c) == 99"})
    with pytest.raises(pencilmark.NoSolution):
        pencilmark.solve(doc)


def test_malformed_custom_rules_are_format_errors():
    for rule, why in [
        ({"type": "custom", "holds": "sum(c) == 3"}, "unknown name"),
        ({"type": "custom", "cells": {"c": ["r1c1", "r10c1"]}, "holds": "sum(c) == 3"}, "does not exist"),
        ({"type": "custom", "cells": {"c": ["r1c1"]}, "holds": "c + 1"}, "condition"),
        ({"type": "custom", "holds": "abs(1) == 1", "scope": {"pairs": "orthogonal"}}, "predicate"),
        ({"type": "custom", "holds": "(a, b) => a != b", "scope": {"pairs": "sideways"}}, "scope pairs"),
        ({"type": "custom", "cells": {"c": ["r1c1"]}, "holds": "c == 1", "each": "c"}, "each"),
    ]:
        with pytest.raises(pencilmark.FormatError, match=why):
            pencilmark.validate(_doc_with(rule))


def test_custom_rule_over_many_cells_uses_the_engine_evaluator():
    """more than 5 cells: an expression constraint the engine checks (csrc/expr.cpp), not a digit table"""
    doc = pencilmark.write.document(GRID, solution=True, describe=True)
    sol, row = doc["solution"], [f"r1c{c}" for c in range(1, 10)]
    doc["rules"].append({"type": "custom", "cells": {"r": row}, "holds": f"sum(take(r[1], r)) == {sum(sol[: sol[0]])}"})
    assert pencilmark.solve(doc) == sol and pencilmark.rate(doc)["difficulty"] > 0
    doc["rules"][-1]["holds"] = f"sum(take(r[1], r)) == {sum(sol[: sol[0]]) + 1}"
    with pytest.raises(pencilmark.NoSolution):
        pencilmark.solve(doc)


def test_compile_matches_known_families():
    """a custom rule compiles to the same allowed digits as the family it imitates"""
    from pencilmark.exchange.board import Board
    from pencilmark.rules.custom import compile_rule

    B = Board([(r, c) for r in range(9) for c in range(9)], 9)
    [x] = compile_rule({"cells": {"p": ["r1c1", "r1c2"]}, "holds": "sum(p) == 10"}, B, 9)
    assert sorted(map(tuple, x["allowed"])) == [(a, 10 - a) for a in range(1, 10)]
    [cage] = compile_rule({"cells": {"c": ["r1c1", "r2c1", "r3c1"]}, "holds": "sum(c) == 7 and all_different(c)"}, B, 9)
    assert {tuple(sorted(a)) for a in cage["allowed"]} == {(1, 2, 4)} and len(cage["allowed"]) == 6
    rel = compile_rule({"holds": "(a, b) => abs(a - b) != 1", "scope": {"pairs": "orthogonal"}}, B, 9)
    assert len(rel) == 1 and rel[0]["rel"] == "allowed" and len(rel[0]["cells"]) == 144  # one shared relation


def test_constant_index_reads_narrow_the_rule():
    """a rule reading its list only at constant indices compiles over those cells (GAS Serbian Frame: "ray[3] + ray[4]
    == 3" over a 9-cell ray is a 2-cell table, not a 9-cell expression); a whole-list use keeps every cell"""
    from pencilmark.exchange.board import Board
    from pencilmark.rules.custom import compile_rule

    B = Board([(r, c) for r in range(9) for c in range(9)], 9)
    ray = [f"r1c{c}" for c in range(1, 10)]
    [x] = compile_rule({"cells": {"ray": ray}, "holds": "ray[3] + ray[4] == 3"}, B, 9)
    assert x["type"] == "table" and x["cells"] == ["r1c3", "r1c4"]
    assert sorted(map(tuple, x["allowed"])) == [(1, 2), (2, 1)]
    [y] = compile_rule({"cells": {"ray": ray}, "holds": "ray[1] == 1 and sum(ray) == 45"}, B, 9)
    assert len(y["cells"]) == 9  # sum(ray) reads the whole list


EXPRESSIONS = [
    "2 * max(c) == sum(c)",
    "count(x for x in c if odd(x)) == 2",
    "let s = sum(c); s in {10, 15, 20}",
    "sum(upto(c, x => x == 9)) == 12",
    "len(seen(c)) == 3",
    "c[c[1]] == 5",
    "sum(take(c[1], c)) > 10",
    "len(take_while(c, x => x <= 5)) == 2",
    "median(c) * 2 == 9",
    "7 div 2 == 3 and -7 mod 3 == 2 and 2 ** 3 == 8",
    "prime(concat([c[1], c[2]]))",
    "min(c[1], c[4]) == 1 or max(c) == 9",
    "odd(c[1]) == odd(c[2])",
    "num(odd(c[3])) + num(even(c[3])) == 1",
    "(if c[1] < c[2] then c[2] else c[1]) == 4",
    "count([odd(x) for x in c]) == 3",
    "let close(a, b) = abs(a - b) <= 2; close(c[1], c[3]) and not close(c[1], c[2])",
    "all([(x mod 2 == 0) or x < 4 for x in c])",
    "position(c, x => x > 5) == 2",
    "c[7] != 3",
    "not defined(c[7]) and defined(c[3])",
    "(c[7] ?? 0) == 0",
    "count(i for i in {1..len(c)} if abs(c[i] - (c[i + 1] ?? 99)) == 1) >= 1",
    "1 / (c[1] - c[2]) > 0",
    "sum(c[2..4]) == 15",
    "all_different(c)",
    "count_distinct(c) == 4",
    "sort(c)[1] == min(c)",
    "reverse(c)[1] == c[len(c)]",
    "any(2 * x == sum(c) for x in c)",
    "product(c) mod 7 == 0",
    "sum(x * x for x in c) > 100",
    "let a = c[1], b = a + c[2]; b == 10",
    "abs(sum(c[1..2]) - sum(c[3..4])) <= 1",
    "c[1] / c[2] == 2 or c[2] / c[1] == 2",
    "let f(n) = if n <= 1 then 1 else n * f(n - 1); f(c[1]) > 100",
    "row(c[2]) + col(c[2]) == 3 and box(c[5]) == 2",
    "sum(upto(c, x => x == 10)) == 1 or true",
    "median([c[1], c[2]]) == (c[1] + c[2]) / 2",
    "c[0] == 1 or c[3 / 2] == 1 or len(c[3..2]) == 0",
]


def test_cpp_evaluator_matches_the_reference():
    """the engine's evaluator (csrc/expr.cpp) gives the Python reference's answer on every expression and filling"""
    import random

    from pencilmark import cbackend as CB
    from pencilmark.exchange.board import Board
    from pencilmark.rules.custom import _expr, holds

    B = Board([(r, c) for r in range(9) for c in range(9)], 9)
    names = ["r1c1", "r1c2", "r1c3", "r1c4", "r1c5"]
    rng = random.Random(1)
    for src in EXPRESSIONS:
        rule = {"cells": {"c": names}, "holds": src}
        spec = _expr(rule, B)
        assert spec["cells"] == names, src
        spec["cells"] = list(range(len(names)))  # engine indices, as the puzzle reader passes them
        for _ in range(200):
            digits = [rng.randint(1, 9) for _ in names]
            want = holds(src, {"c": names}, dict(zip(names, digits)))
            assert CB._C.expr_holds(spec, digits) == want, (src, digits)


@pytest.mark.usefixtures("reserved_ok")  # region() / shaded(): reserved
def test_board_layers():
    """region(c) and shaded(c) read the board's layers; without the layer the rule is refused. On a regions-to-find
    board the search checks region() once digits and region labels are known; shaded() is refused (no shading layer
    yet), never read without the rule"""
    cells, grid = {"a": "r1c1", "b": "r1c2"}, {"r1c1": 3, "r1c2": 5}
    assert holds("region(a) != region(b)", cells, grid, layers={"region": {"r1c1": 1, "r1c2": 2}})
    assert holds("not shaded(a) or odd(a)", cells, grid, layers={"shaded": {"r1c1": True, "r1c2": False}})
    assert check(parse("region(a) == region(b) and shaded(b)"), {"a", "b"}) == "bool"
    with pytest.raises(LangError, match="regions to find"):
        holds("region(a) == 1", cells, grid)
    import json
    import sys
    from pathlib import Path

    import pencilmark

    sys.path.insert(0, str(Path(__file__).parent))
    from test_substeps import CHAOS_DEMO

    rule = lambda holds: {"type": "custom", "cells": {"a": ["r1c1"], "b": ["r5c5"]}, "holds": holds}
    doc = json.loads(json.dumps(CHAOS_DEMO))  # regions to find: the search checks region() with the labels
    assert pencilmark.count_solutions(dict(doc, rules=doc["rules"] + [rule("region(a) != region(b)")]))["count"] == 1
    assert pencilmark.count_solutions(dict(doc, rules=doc["rules"] + [rule("region(a) == region(b)")]))["count"] == 0
    plain = {"format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": 9, "cols": 9}, "digits": 9,
             "givens": [0] * 81, "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]},
                       rule("region(a) != region(b)")]}  # fmt: skip
    with pytest.raises(pencilmark.NotSupportedError, match="regions to find"):
        pencilmark.api._load(plain)
    doc["rules"] = doc["rules"] + [dict(rule("x"), holds="not shaded(a) or odd(a)")]
    with pytest.raises(pencilmark.NotSupportedError, match="shading"):
        pencilmark.api._load(doc)


def _hidden_doc(**extra):
    base = {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": 4, "cols": 4},
        "digits": 4,
        "givens": [0] * 16,
        "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}],
    }
    base.update(extra)
    return base


def test_unknowns_and_layers_read_check_write():
    import importlib
    import json

    import pytest

    import pencilmark
    from pencilmark.exchange import FormatError
    from pencilmark.rules import custom as CU

    V = importlib.import_module("pencilmark.exchange.validate")
    rule = {"type": "custom", "cells": {"c": ["r1c1", "r1c2"]}, "holds": "sum(c)+shift(r1c1)==X"}
    doc = _hidden_doc(
        unknowns={"X": {"range": [1, 4]}, "T": {"values": [0, 1]}},
        layers={"shift": {"values": [-1, 0, 1], "given": {"r1c1": 0}}},
        rules=_hidden_doc()["rules"] + [rule],
    )
    V.validate(doc)
    out = json.loads(pencilmark.write.pencilmark(doc))  # writers keep them, the rule in canonical spelling
    assert out["unknowns"] == doc["unknowns"] and out["layers"] == doc["layers"]
    assert out["rules"][-1]["holds"] == "sum(c) + shift(r1c1) == X"
    env = dict(box=(2, 2), layers={"shift": {"r1c1": 1}})
    assert CU.holds("sum(c) + shift(r1c1) == X", rule["cells"], {"r1c1": 1, "r1c2": 2}, unknowns={"X": 4}, **env)
    assert not CU.holds("sum(c) + shift(r1c1) == X", rule["cells"], {"r1c1": 1, "r1c2": 2}, unknowns={"X": 3}, **env)
    for bad in (
        _hidden_doc(unknowns={"sum": {"range": [1, 2]}}),  # a built-in's name
        _hidden_doc(layers={"mod": {"values": [0, 1]}}),  # a keyword
        _hidden_doc(unknowns={"X": {"range": [3, 1]}}),
        _hidden_doc(layers={"s": {"values": [1, 2], "given": {"r1c1": 5}}}),
        _hidden_doc(unknowns={"X": {"range": [1, 2]}}, layers={"X": {"values": [0, 1]}}),
        _hidden_doc(
            rules=_hidden_doc()["rules"] + [{"type": "custom", "cells": {"c": ["r1c1"]}, "holds": "sum(c) == Y"}]
        ),
    ):
        with pytest.raises(FormatError):
            V.validate(bad)
    p = pencilmark.api._load(doc)  # the exhaustive search carries unknowns and layers (aux variables)
    assert pencilmark.count_solutions(p, limit=2)["count"] >= 1
    with pytest.raises(pencilmark.NotUnique):  # a wrong input is an error (this one has several solutions); a valid one
        pencilmark.rate(doc)  # is band Unknown with its reason (test_rate_unknowns_is_unknown_with_reason)


def test_unknowns_solve_a_small_cipher():
    """a 4x4 whose cage totals are one unknown X, told apart by a second rule on X: solved by the search alone"""
    import pencilmark

    doc = _hidden_doc(
        givens=[1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1],
        unknowns={"X": {"range": [1, 20]}},
        rules=_hidden_doc()["rules"]
        + [
            {"type": "custom", "cells": {"c": ["r1c2", "r1c3"]}, "holds": "sum(c) == X"},
            {"type": "custom", "cells": {"c": ["r2c1", "r2c2"]}, "holds": "sum(c) == X"},
            {"type": "custom", "cells": {}, "holds": "X == 5"},
        ],
    )
    p = pencilmark.api._load(doc)
    n = pencilmark.count_solutions(p, limit=3)
    sol = "".join(map(str, pencilmark.solve(p))) if n["count"] == 1 else None
    plain = _hidden_doc(
        givens=doc["givens"],
        rules=_hidden_doc()["rules"]
        + [
            {"type": "custom", "cells": {"c": ["r1c2", "r1c3"]}, "holds": "sum(c) == 5"},
            {"type": "custom", "cells": {"c": ["r2c1", "r2c2"]}, "holds": "sum(c) == 5"},
        ],
    )
    q = pencilmark.api._load(plain)  # the same puzzle with X written in: the same answer
    assert n == pencilmark.count_solutions(q, limit=3)
    if sol is not None:
        assert sol == "".join(map(str, pencilmark.solve(q)))


def test_unknowns_and_layers_survive_export():
    import importlib

    import pencilmark

    V = importlib.import_module("pencilmark.exchange.validate")
    doc = _hidden_doc(
        unknowns={"X": {"range": [1, 8]}},
        layers={"shift": {"values": [-1, 0, 1], "given": {"r1c1": 0}}},
        rules=_hidden_doc()["rules"]
        + [
            {"type": "custom", "cells": {"c": ["r1c1", "r1c2"]}, "holds": "sum(c) + shift(r1c2) == X"},
            {
                "type": "custom",
                "cells": {},
                "scope": {"pairs": "orthogonal"},
                "holds": "(a, b) => shift(a) * shift(b) == 0",
            },
        ],
    )
    out = pencilmark.write.document(pencilmark.api._load(doc))
    V.validate(out)
    assert out["unknowns"] == {"X": {"values": list(range(1, 9))}}
    assert out["layers"]["shift"] == {"values": [-1, 0, 1], "given": {"r1c1": 0}}


def test_cases_rule_checks_each_case_against_the_candidates():
    """engine rule kind "cases" (one of several cases holds; docs fog lemmas): an arrow whose shaft is either r1c2 or
    r1c2 + r2c2. One cell would repeat the circle digit in its row, so the second case holds: the circle is at least
    1 + 2, and neither shaft cell can be 9 (the circle is at most 9)"""
    import pencilmark as pm
    from pencilmark import cbackend as cb

    p = pm.api._load("." * 81)
    p.constraints.append(
        {"type": "cases", "cases": [{"cells": [0, 1], "circle": 0}, {"cells": [0, 1, 10], "circle": 0}]}
    )
    elim = {e for m in cb.state_moves(p, assume_unique=False) for e in (m.get("elim") or [])}
    assert {(0, 1), (0, 2), (1, 9), (10, 9)} <= elim


def test_literal_set_membership_is_fast():
    """concat(c) in {...} over a 2x2 (global entropy as a custom rule): the literal set is built once, not per tuple
    (64 such rules took 27 min to compile)"""
    import itertools
    import time

    lo = lambda d: (d - 1) // 3
    ok = sorted(
        int("".join(map(str, t))) for t in itertools.permutations(range(1, 10), 4) if len({lo(d) for d in t}) == 3
    )
    src = "concat(c) in {" + ", ".join(map(str, ok)) + "}"
    tree = parse(src)
    grid = {"r1c1": 1, "r1c2": 4, "r2c1": 7, "r2c2": 2}
    t = time.time()
    for _ in range(2000):
        assert holds(tree, {"c": ["r1c1", "r1c2", "r2c1", "r2c2"]}, grid) is True
    assert time.time() - t < 2.0
    assert holds(tree, {"c": ["r1c1", "r1c2", "r2c1", "r2c2"]}, {"r1c1": 1, "r1c2": 2, "r2c1": 3, "r2c2": 4}) is False


def test_concat_table_matches_enumeration():
    """the direct concat(c) in {...} table equals the enumerated one (rows, order), and other shapes enumerate"""
    from pencilmark.rules.custom import _concat_table, _table

    names = ["r1c1", "r1c2", "r2c1"]
    cells = {"c": list(names)}
    tree = parse("concat(c) in {123, 312, 999, 12, 1234, 102, 213}")
    direct = _concat_table(tree, cells, names, 9)
    assert direct == _table(lambda g: holds(tree, cells, g), names, 9)
    assert direct == [[1, 2, 3], [2, 1, 3], [3, 1, 2], [9, 9, 9]]
    assert _concat_table(tree, cells, names, 4) == _table(lambda g: holds(tree, cells, g), names, 4)
    assert _concat_table(parse("concat(c) in {123} or true"), cells, names, 9) is None
    assert _concat_table(tree, {"c": names[::-1]}, names, 9) is None


def test_rate_unknowns_is_unknown_with_reason():
    """a puzzle with unknowns: no human technique reasons with them yet, so its card is band Unknown with the reason"""
    doc = {
        "format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4,
        "givens": [0, 0, 0, 1, 0, 0, 0, 0, 0, 2, 0, 0, 4, 0, 0, 0], "unknowns": {"X": {"range": [3, 7]}},
        "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]},
                  {"type": "custom", "cells": {"a": ["r1c1", "r1c2"]}, "holds": "sum(a) == X"},
                  {"type": "custom", "cells": {"b": ["r4c3", "r4c4"]}, "holds": "sum(b) == X"},
                  {"type": "custom", "cells": {"c": ["r2c3", "r3c2"]}, "holds": "sum(c) == X"}],
    }  # fmt: skip
    card = pencilmark.rate(doc, fields=["band", "difficulty", "time", "band_index"])
    assert card["band"] == "Unknown" and card["band_index"] is None and card["time"] is None
    assert "unknowns" in card["reason"]


def test_definitions_place_one_rule_many_times():
    """6.18 definitions: a named custom rule placed with use (its own style wins); a placement is the rule it spells
    out (same fingerprint, names and drawing aside); bad definitions or placements are refused (user 2026-11-07, K2)"""
    base = {"format": "pencilmark-puzzle", "format_version": 1, "board": {"rows": 4, "cols": 4}, "digits": 4,
            "givens": [0] * 16, "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}]}  # fmt: skip
    rule = {"holds": "a + b != 5", "label": "No fives"}
    defs = {"no_five": dict(rule, draw="dot", style={"color": "#ff0000"})}
    cells = [{"a": ["r1c1"], "b": ["r1c2"]}, {"a": ["r3c3"], "b": ["r4c3"]}]
    placed = dict(
        base, definitions=defs, rules=base["rules"] + [{"type": "custom", "use": "no_five", "cells": c} for c in cells]
    )
    inline = dict(base, rules=base["rules"] + [dict(rule, type="custom", cells=c) for c in cells])
    renamed = json.loads(json.dumps(placed).replace("no_five", "fives"))
    assert pencilmark.fingerprint(placed) == pencilmark.fingerprint(inline) == pencilmark.fingerprint(renamed)
    assert pencilmark.describe(placed)["rules_text"].count("No fives") == 1
    text = pencilmark.write.pencilmark(placed)
    assert '"definitions"' in text and '"use": "no_five"' in text  # kept as written
    for bad in ({"definitions": {"x": {"label": "no holds"}}},
                dict(definitions=defs, rules=base["rules"] + [{"type": "custom", "use": "nope", "cells": cells[0]}]),
                dict(definitions=defs, rules=base["rules"] + [{"type": "custom", "use": "no_five", "holds": "a == 1"}])):  # fmt: skip
        with pytest.raises(pencilmark.FormatError):
            pencilmark.validate(dict(base, **bad))
