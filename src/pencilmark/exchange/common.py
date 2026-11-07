"""The format's constants, errors, cell names and operator parameters."""

from __future__ import annotations

import re

from .. import puzzle_json as PJ

FORMAT = "pencilmark-puzzle"
FORMAT_VERSION = 1
SCHEMA_URL = "https://silly-puppyy.github.io/pencilmark/schema/pencilmark-puzzle-1.json"


# normalisation 8 (docs/guides/development/engine-mapping.md): 2-cell tables that are an edge clue (differences / sums / products / quotients) and mathrax
# corner tables are written as edge / corner rules. False keeps such tables as "table" rules.
UNIFY_TABLE_EDGES = True
# Engine form of NUMBERED pair clues (edge difference / sum / product / ratio, mathrax corners) -- one form for every source.
# "table": 2-cell tables of the allowed digit pairs, the form whose pricing fits players' times; kropki, XV and less stay
# pair relations (their calibrated path). "relation" = generic pair relations.
NUMBERED_PAIR_FORM = "table"


from ..errors import FormatError, NotSupportedError  # noqa: E402,F401

# ---------------------------------------------------------------------------------------------------------------- cells
_CELL = re.compile(r"r([1-9]\d*)c([1-9]\d*)")


def cell_name(r, c):
    """0-based (row, col) -> 'r1c1'"""
    return f"r{r + 1}c{c + 1}"


def parse_cell(s):
    """'r1c1' -> 0-based (row, col)"""
    m = _CELL.fullmatch(s) if isinstance(s, str) else None
    if not m or int(m.group(1)) < 1 or int(m.group(2)) < 1:
        raise FormatError(f"bad cell name {s!r}")
    return int(m.group(1)) - 1, int(m.group(2)) - 1


SIDES = {"top": (-1, 0), "bottom": (1, 0), "left": (0, -1), "right": (0, 1)}

# pair operators (docs/formats/puzzle-format.md 5.1) <-> engine relation kinds
OPS = {
    "different": "neq",
    "equal": "eq",
    "less": "lt",
    "less_equal": "le",
    "difference": "diff",
    "not_difference": "notdiff",
    "not_consecutive": "nonconsec",
    "difference_at_least": "diffge",
    "difference_at_most": "diffle",
    "ratio": "ratio",
    "not_ratio": "notratio",
    "sum": "sum",
    "not_sum": "notsum",
    "parity_differs": "parity",
    "same_third": "samegroup3",
    "different_third": "diffgroup3",
    "same_mod3": "samemod3",
    "different_mod3": "diffmod3",
    "allowed": "allowed",
    "any_of": "anyof",
}
REL_OP = {v: k for k, v in OPS.items()}
DIRECTED_OPS = {"less", "less_equal", "allowed", "any_of"}
NEIGHBOUR_STEPS = PJ.NEIGHBOURS
KNIGHT = [(1, 2), (2, 1), (1, -2), (2, -1)]
KING_DIAG = [(1, 1), (1, -1)]
ORTHO = [(0, 1), (1, 0)]


OP_KEY = {
    "difference": "value",
    "not_difference": "value",
    "difference_at_least": "value",
    "difference_at_most": "value",
    "ratio": "value",
    "not_ratio": "value",
    "sum": "sum",
    "not_sum": "sum",
    "allowed": "allowed",
    "any_of": "any_of",
}
OP_PARAM_KEYS = {
    "value",
    "sum",
    "allowed",
    "any_of",
}  # the operator's named parameter (docs/formats/puzzle-format.md 5.1)


def op_params(r):
    """an operator's named parameter in a rule or an any_of entry -> the positional params list"""
    op = r["op"]
    if op == "any_of":
        return [[x["op"], op_params(x)] for x in r["any_of"]]
    k = OP_KEY.get(op)
    return [r[k]] if k else []


def op_named(op, params):
    """positional params -> the named parameter key(s) of a rule or any_of entry"""
    if op == "any_of":
        return {"any_of": [dict({"op": o}, **op_named(o, p)) for o, p in params]}
    k = OP_KEY.get(op)
    return {k: params[0]} if k else {}


def _op_params_to_engine(op, params):
    if op == "any_of":
        return tuple((OPS[o], *p) for o, p in params)
    if op == "allowed":
        return ([list(x) for x in params[0]],)
    return tuple(params)


def _engine_params_to_op(kind, args):
    if kind == "anyof":
        return [[REL_OP[a[0]], list(a[1:])] for a in args]
    if kind == "allowed":
        return [[list(x) for x in args[0]]]
    return list(args)


GRID_TYPES = ("grid", "box_grid", "chaos")


def with_origins(doc):
    """the doc with every grid / box_grid / chaos rule's origin filled in: r1c1 when it is left out (6.1)"""
    rules = doc.get("rules") if isinstance(doc, dict) else None
    if not isinstance(rules, list):
        return doc
    return dict(
        doc,
        rules=[
            dict(r, origin="r1c1") if isinstance(r, dict) and r.get("type") in GRID_TYPES and "origin" not in r else r
            for r in rules
        ],
    )
