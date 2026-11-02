"""Strict reading checks (docs/formats/puzzle-format.md section 4): validate(doc) raises FormatError."""

from __future__ import annotations

import re

from ..rules.cell import CELL
from ..rules.edge import EDGE, NEG_SELECTOR, edge_value_ok
from ..rules.line import LINE
from .board import Board, grid_area, grid_units
from .common import (
    DIRECTED_OPS,
    FORMAT,
    FORMAT_VERSION,
    NEIGHBOUR_STEPS,
    OP_KEY,
    OP_PARAM_KEYS,
    OPS,
    SIDES,
    FormatError,
    parse_cell,
)

# -------------------------------------------------------------------------------------------------------- validation
COMMON = {"type", "id", "label", "style"}
RULE_KEYS = {
    "grid": ({"origin"}, set()),
    "chaos": ({"origin"}, set()),
    "region_border": ({"cells"}, set()),
    "same_region": ({"cells"}, set()),
    "box_grid": ({"origin", "box"}, set()),
    "box": ({"cells"}, set()),
    "row": ({"cells"}, set()),
    "column": ({"cells"}, set()),
    "region": ({"kind", "cells"}, set()),
    "cage": ({"cells"}, {"sum"}),
    "line": ({"kind", "cells"}, {"closed", "value", "groups"}),
    "arrow": ({"bulb", "lines"}, set()),
    "edge": ({"kind", "cells"}, {"color", "letter", "value", "sum"}),
    "corner": ({"kind", "cells"}, {"op", "value"}),
    "sum": ({"kind", "sum", "cells"}, {"side"}),
    "sandwich": ({"sum", "side", "cells"}, set()),
    "xsum": ({"sum", "side", "cells"}, set()),
    "skyscraper": ({"value", "side", "cells"}, set()),
    "rossini": ({"arrow", "side", "cells"}, set()),
    "first_seen": ({"value", "digits", "side", "cells"}, set()),
    "neighbours": (set(), {"kind", "op", "value", "sum", "allowed", "any_of", "where", "within", "area", "except"}),
    "relation": ({"op", "pairs"}, {"value", "sum", "allowed", "any_of"}),
    "cell": ({"kind", "cells"}, {"split", "values"}),
    "contains": ({"digits", "cells"}, set()),
    "appears": ({"source", "cells"}, set()),
    "clone": ({"regions"}, set()),
    "isomorphic": ({"regions"}, set()),
    "count": ({"cells"}, {"kind", "each", "counts"}),
    "distinct_count": ({"value", "cells"}, {"side"}),
    "global_entropy": (set(), set()),
    "equal_sum": ({"segments"}, set()),
    "vudoku": ({"cells"}, set()),
    "table": ({"allowed"}, {"cells", "where"}),
    "negative": ({"of"}, {"color", "letter", "value", "sum", "kind", "split", "area"}),
}
KINDS = {
    "region": {"diagonal", "window", "disjoint", "colour", "extra", "region"},
    "line": set(LINE),  # rules/line.py
    "edge": set(EDGE),  # rules/edge.py
    "corner": {"battenburg", "mathrax", "exclude"},
    "sum": {"little_killer", "frame", "group", "corner"},
    "neighbours": {"antiknight", "antiking", "nonconsecutive"},
    "cell": set(CELL),  # rules/cell.py
    "count": {"circles"},
}
LINE_PARAMS = {k: set(v.params) for k, v in LINE.items() if v.params}
EDGE_PARAMS = {k: {v.param} if v.param else set() for k, v in EDGE.items()}
NEG_OF = set(NEG_SELECTOR) | {"rossini", "battenburg", "cell"}
TOP_KEYS = {
    "format",
    "format_version",
    "$schema",
    "meta",
    "board",
    "digits",
    "givens",
    "solution",
    "candidates",
    "rules",
    "decorations",
    "style",
}


def _int(x, what, lo=None):
    if not isinstance(x, int) or isinstance(x, bool) or (lo is not None and x < lo):
        raise FormatError(f"{what} must be an integer" + (f" >= {lo}" if lo is not None else ""))
    return x


def validate(doc):
    """strict reading (docs/formats/puzzle-format.md section 4) of a format_version 1 dict; raises FormatError. Returns the Board."""
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise FormatError('not a sudoku-puzzle ("format" must be "sudoku-puzzle")')
    if "format_version" not in doc:
        raise FormatError("format_version missing")
    fv = _int(doc["format_version"], "format_version", 1)
    if fv > FORMAT_VERSION:
        raise FormatError(f"format_version {fv} is newer than this reader ({FORMAT_VERSION})")
    for k in doc:
        if k not in TOP_KEYS:
            raise FormatError(f"unknown top-level key {k!r}")
    for k in ("board", "digits", "givens", "rules"):
        if k not in doc:
            raise FormatError(f"{k!r} missing")
    g = doc["board"]
    if not isinstance(g, dict) or set(g) != {"rows", "cols"}:
        raise FormatError('"board" must be {"rows": R, "cols": C}')
    R, C = _int(g["rows"], "board.rows", 1), _int(g["cols"], "board.cols", 1)
    if isinstance(doc["digits"], dict):
        raise FormatError(
            '"digits" as an object (other digit sets, symbols) is reserved for a future version of the '
            "format; format_version 1 takes an integer D (digits 1..D)"
        )
    D = _int(doc["digits"], "digits", 1)
    giv = doc["givens"]
    if not isinstance(giv, list) or len(giv) != R * C:
        raise FormatError(f"givens must be a list of rows*cols = {R * C} entries")
    for v in giv:
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= D):
            raise FormatError(f"givens entry {v!r} is not null or 0..{D}")
    coords = [divmod(k, C) for k, v in enumerate(giv) if v is not None]
    if not coords:
        raise FormatError("the grid has no cells")
    B = Board(coords, D)
    if doc.get("solution") is not None:
        sol = doc["solution"]
        if not isinstance(sol, list) or len(sol) != R * C:
            raise FormatError("solution must have the shape of givens")
        for k, (v, w) in enumerate(zip(giv, sol)):
            bad = w is not None and (not isinstance(w, int) or isinstance(w, bool) or not 1 <= w <= D)
            if (v is None) != (w is None) or bad:
                raise FormatError(f"solution entry {k} does not match givens (null where givens is null, else 1..{D})")
    cands = doc.get("candidates")
    if cands is not None:
        if not isinstance(cands, dict):
            raise FormatError("candidates must be an object")
        for k, v in cands.items():
            B.idx(k)
            if not isinstance(v, list) or any(not isinstance(x, int) or not 1 <= x <= D for x in v):
                raise FormatError(f"candidates of {k} must be a list of digits 1..{D}")
    if doc.get("meta") is not None and not isinstance(doc["meta"], dict):
        raise FormatError("meta must be an object")
    if not isinstance(doc["rules"], list):
        raise FormatError("rules must be a list")
    B.grid_origins = {
        r["origin"]
        for r in doc["rules"]
        if isinstance(r, dict) and r.get("type") in ("grid", "box_grid", "chaos") and isinstance(r.get("origin"), str)
    }
    B.chaos_areas = [
        grid_area(B, *parse_cell(r["origin"]))
        for r in doc["rules"]
        if isinstance(r, dict)
        and r.get("type") == "chaos"
        and isinstance(r.get("origin"), str)
        and grid_units(B, *parse_cell(r["origin"])) is not None
    ]
    for r in doc["rules"]:  # a chaos area's boxes are what the solver finds: none may be given (6.3)
        if not isinstance(r, dict) or r.get("type") not in ("box", "box_grid"):
            continue
        cells = (
            grid_area(B, *parse_cell(r["origin"]))
            if r["type"] == "box_grid" and isinstance(r.get("origin"), str)
            else {B.idx(c) for c in r.get("cells", []) if isinstance(c, str)}
        )
        if cells and any(cells <= a for a in B.chaos_areas):
            raise FormatError(f"a {r['type']} rule inside a chaos area (its regions are to be found)")
    for i, r in enumerate(doc["rules"]):
        try:
            _validate_rule(r, B)
        except FormatError as e:
            raise FormatError(f"rule {i} ({r.get('type') if isinstance(r, dict) else r!r}): {e}") from None
    return B


def _cells(B, x, what="cells", n=None, minlen=1):
    if not isinstance(x, list) or len(x) < minlen or (n is not None and len(x) != n):
        raise FormatError(f"{what} must be a list of " + (f"{n}" if n is not None else f">= {minlen}") + " cell names")
    out = [B.idx(c) for c in x]
    return out


def _merge_negatives(rules, prov):
    """adjacent negatives of both kropki colours (white, black) or both XV letters (X, V) with the same scope -> one negative
    without a selector, which expands to the same relations in the same order"""
    out, op = [], []
    for r, pr in zip(rules, prov):
        if (
            out
            and r.get("type") == "negative"
            and out[-1].get("type") == "negative"
            and r["of"] == out[-1]["of"] in ("kropki", "xv")
        ):
            key = NEG_SELECTOR[r["of"]]
            first, second = ("white", "black") if r["of"] == "kropki" else ("X", "V")
            strip = lambda x: {k: v for k, v in x.items() if k != key}
            if out[-1].get(key) == first and r.get(key) == second and strip(out[-1]) == strip(r):
                out[-1] = strip(r)
                op[-1] = {k: set(op[-1].get(k, ())) | set(pr.get(k, ())) for k in set(op[-1]) | set(pr)}
                continue
        out.append(r)
        op.append(pr)
    return out, op


def area_cells(B, a):
    """an area (docs/formats/puzzle-format.md 5): the origin of a grid / box_grid rule -> that grid's D x D cells in reading order, or a list of
    cell names -> those cells; as engine cell ids"""
    if isinstance(a, str):
        if a not in getattr(B, "grid_origins", ()):
            raise FormatError(f"area {a!r} is not the origin of a grid / box_grid rule")
        r0, c0 = parse_cell(a)
        return [B.cid[(r, c)] for r in range(r0, r0 + B.D) for c in range(c0, c0 + B.D)]
    return _cells(B, a, "area")


# Reserved for a planned custom rule type (docs/formats/rules/other.mdx, 6.17): explicit digit tables. Tables make files huge and no renderer
# can draw them, so format_version 1 readers refuse them and the writer never produces them. The engine still builds
# tables internally (edge clues, lockout, entropy, ...); _reserved_ok() lets internal tooling read old files that hold them.
RESERVED_MSG = (
    "is reserved: digit tables are replaced by a custom rule type planned for a later version of the format; "
    "use a rule family (docs/formats/puzzle-format.md 6)"
)
_RESERVED_OK = [False]


class _reserved_ok:
    """internal tooling only (not part of the format): read and write table rules / the allowed operator"""

    def __enter__(self):
        self.old = _RESERVED_OK[0]
        _RESERVED_OK[0] = True

    def __exit__(self, *a):
        _RESERVED_OK[0] = self.old


def resolve_areas(B, rules):
    """rules with every "area" replaced by its cell list ("cells"), as the engine expansion reads them"""
    return [
        dict({k: v for k, v in r.items() if k != "area"}, cells=[B.name(c) for c in area_cells(B, r["area"])])
        if isinstance(r, dict) and "area" in r
        else r
        for r in rules
    ]


def _validate_rule(r, B):
    D = B.D
    if not isinstance(r, dict) or "type" not in r:
        raise FormatError("a rule must be an object with a type")
    t = r["type"]
    if not isinstance(t, str):
        raise FormatError(f"a rule type must be a string, not {t!r}")
    if t == "custom":
        return _validate_custom(r, B)
    if t == "table" and not _RESERVED_OK[0]:
        raise FormatError('"type": "table" ' + RESERVED_MSG)
    if isinstance(t, str) and ":" in t:
        raise FormatError(f"vendor rule type {t!r} is not implemented by this reader")
    if t not in RULE_KEYS:
        raise FormatError(f"unknown rule type {t!r}")
    req, opt = RULE_KEYS[t]
    for k in r:
        if k not in req | opt | COMMON:
            raise FormatError(f"unknown key {k!r}")
    for k in req:
        if k not in r:
            raise FormatError(f"missing key {k!r}")
    kind = r.get("kind")
    if kind is not None and not isinstance(kind, str):
        raise FormatError(f"a rule kind must be a string, not {kind!r}")
    if t in KINDS and (kind is not None or t not in ("neighbours", "count")) and kind not in KINDS[t]:
        raise FormatError(f"unknown kind {kind!r}")
    if t in ("region_border", "same_region"):  # 6.3: relations between the regions of a chaos area
        cs = _cells(B, r["cells"], n=2 if t == "region_border" else None, minlen=2)
        if len(set(cs)) != len(cs):
            raise FormatError("cells repeat")
        if not any(set(cs) <= a for a in getattr(B, "chaos_areas", [])):
            raise FormatError(f"{t} cells must lie in one chaos area")
        if t == "region_border":
            (r1, c1), (r2, c2) = (B.coords[x] for x in cs)
            if abs(r1 - r2) + abs(c1 - c2) != 1:
                raise FormatError("a region_border separates two orthogonal neighbours")
        return
    if t in ("grid", "box_grid", "chaos"):
        if t == "box_grid":
            bx = r["box"]
            if not (
                isinstance(bx, list)
                and len(bx) == 2
                and all(isinstance(x, int) and not isinstance(x, bool) and x >= 1 for x in bx)
            ):
                raise FormatError("box must be [rows, cols] of positive integers")
            if bx[0] * bx[1] != D:
                raise FormatError(f"box {bx} does not hold {D} cells")
        r0, c0 = parse_cell(r["origin"])
        if grid_units(B, r0, c0) is None:
            raise FormatError(f"{t} covers a missing cell (its area is {D} x {D} from origin)")
    elif t in ("box", "row", "column", "region", "contains", "appears", "cell", "count", "vudoku"):
        cs = _cells(B, r["cells"])
        if t == "vudoku" and len(cs) != 3:
            raise FormatError("vudoku takes 3 cells (vertex, arm, arm)")
        if t == "appears":
            B.idx(r["source"])
        if t == "contains" and (
            not isinstance(r["digits"], list)
            or not r["digits"]
            or any(not isinstance(x, int) or not 1 <= x <= D for x in r["digits"])
        ):
            raise FormatError(f"digits must be a list of digits 1..{D}")
        if t == "cell":
            if CELL[kind].param == "split":
                if "split" not in r or "values" in r:
                    raise FormatError(f"cell {kind} takes split (and no values)")
                _int(r["split"], "split", 1)
            elif CELL[kind].param == "values":
                if "values" not in r or "split" in r:
                    raise FormatError(f"cell {kind} takes values")
                if (
                    not isinstance(r["values"], list)
                    or not r["values"]
                    or any(not isinstance(x, int) or not 1 <= x <= D for x in r["values"])
                ):
                    raise FormatError(f"values must be digits 1..{D}")
            elif "split" in r or "values" in r:
                raise FormatError(f"cell {kind} takes no split / values")
        if t == "count":
            modes = [k for k in ("kind", "each", "counts") if k in r]
            if len(modes) != 1:
                raise FormatError("count takes exactly one of kind / each / counts")
    elif t == "cage":
        _cells(B, r["cells"])
        if "sum" in r:
            _int(r["sum"], "sum", 0)
    elif t == "line":
        cs = _cells(B, r["cells"], minlen=2)
        for a, b in zip(cs, cs[1:]):
            if not B.touching(a, b):
                raise FormatError(f"line cells {B.name(a)} and {B.name(b)} do not touch")
        allowed = LINE_PARAMS.get(kind, set())
        for k in ("value", "groups"):
            if k in r and k not in allowed:
                raise FormatError(f"line {kind} takes no {k!r}")
        if D != 9 and allowed and not (allowed <= set(r)):
            raise FormatError(f"line {kind} requires {sorted(allowed)} when digits != 9")
        if "value" in r:  # whisper / lockout: a difference between digits; modular: the modulus
            _int(r["value"], "value", 2 if kind == "modular" else 1)
            if kind != "modular" and r["value"] > D - 1:
                raise FormatError(f"line {kind} value must be at most {D - 1} (a difference between digits 1..{D})")
        if "groups" in r:  # entropic: low / middle / high
            g = r["groups"]
            flat = [v for x in g for v in x] if isinstance(g, list) and all(isinstance(x, list) for x in g) else None
            # an empty group is allowed: sudoku.coach's fixed thirds {1-3} {4-6} {7-9} on a 4x4 leave {} for high
            if flat is None or len(g) != 3 or sorted(flat) != list(range(1, D + 1)):
                raise FormatError(f"groups must be three groups that split the digits 1..{D}")
        if r.get("closed") and not LINE[kind].closable:
            raise FormatError(f"line {kind} cannot be closed")
        if "closed" in r and not isinstance(r["closed"], bool):
            raise FormatError("closed must be true / false")
    elif t == "arrow":
        bulb = _cells(B, r["bulb"], "bulb")
        if not isinstance(r["lines"], list) or not r["lines"]:
            raise FormatError("lines must be a list of shafts")
        for sh in r["lines"]:
            cs = _cells(B, sh, "shaft")
            if not any(B.touching(cs[0], b) for b in bulb):
                raise FormatError("a shaft must start next to a bulb cell")
    elif t == "edge":
        cs = _cells(B, r["cells"], n=2)
        if not B.adjacent(*cs):
            raise FormatError("edge cells must be orthogonally adjacent")
        need = EDGE_PARAMS[kind]
        if set(r) & {v.param for v in EDGE.values()} != need:
            raise FormatError(f"edge {kind} takes exactly {sorted(need) or 'no parameters'}")
        ek = EDGE[kind]
        if ek.choices and r[ek.param] not in ek.choices:
            raise FormatError(f"{ek.param} must be {' or '.join(ek.choices)}")
        if ek.param in ("value", "sum"):
            _int(r[ek.param], ek.param, 0)
            if not edge_value_ok(kind, r[ek.param], D):
                raise FormatError(f"no two different digits 1..{D} make edge {kind} {r[ek.param]}")
    elif t == "corner":
        cs = _cells(B, r["cells"], n=4)
        if not B.is_block(cs):
            raise FormatError("corner cells must be a 2x2 block written TL, TR, BL, BR")
        if kind == "battenburg" and set(r) & {"op", "value"}:
            raise FormatError("battenburg takes no parameters")
        if kind == "exclude" and ("value" not in r or "op" in r):
            raise FormatError("corner exclude takes value")
        if kind == "mathrax":
            op = r.get("op")
            if op in ("even", "odd"):
                if "value" in r:
                    raise FormatError("mathrax even / odd takes no value")
            elif op in ("+", "-", "x", "/"):
                v = _int(r.get("value"), "value", 0)
                hit = {"+": lambda x, y: x + y == v, "-": lambda x, y: abs(x - y) == v, "x": lambda x, y: x * y == v,
                       "/": lambda x, y: x == v * y or y == v * x}[op]  # fmt: skip
                if not any(hit(x, y) for x in range(1, D + 1) for y in range(1, D + 1)):  # diagonal digits may repeat
                    raise FormatError(f"no two digits 1..{D} make mathrax {op} {v}")
            else:
                raise FormatError("mathrax op must be + - x / even odd")
    elif t == "sum":
        cs = _cells(B, r["cells"])
        _int(r["sum"], "sum", 0)
        if kind in ("little_killer", "frame"):
            if "side" not in r:
                raise FormatError(f"sum {kind} needs side")
            B.check_outside(r["side"], cs, diagonal_ok=(kind == "little_killer"), what=f"sum {kind}")
        elif "side" in r:
            raise FormatError(f"sum {kind} takes no side")
        if kind == "corner" and not B.is_block(cs):
            raise FormatError("sum corner cells must be a 2x2 block")
    elif t in ("sandwich", "xsum", "skyscraper", "rossini", "first_seen"):
        if r["side"] not in SIDES:
            raise FormatError("side must be top / bottom / left / right")
        cs = _cells(B, r["cells"])
        B.check_outside(r["side"], cs, diagonal_ok=False, what=t)
        if t == "rossini" and (r["arrow"] not in ("in", "out") or len(cs) != 3):
            raise FormatError("rossini takes arrow in / out and 3 cells")
    elif t == "distinct_count":
        cs = _cells(B, r["cells"])
        if "side" in r:
            B.check_outside(r["side"], cs, what="distinct_count")
    elif t == "neighbours":
        if "kind" in r:
            if set(r) & ({"op", "where"} | OP_PARAM_KEYS):
                raise FormatError("neighbours takes a kind or op / where, not both")
        else:
            if not {"op", "where"} <= set(r):
                raise FormatError("neighbours needs a kind, or op + where")
            _check_op(r)
            if r["op"] in DIRECTED_OPS - {"allowed", "any_of"} or r["where"] not in NEIGHBOUR_STEPS:
                raise FormatError("neighbours needs a symmetric op and where orthogonal / diagonal / king / knight")
        if "within" in r and r["within"] not in ("box", "region"):
            raise FormatError("within must be box or region")
        if "area" in r:
            area_cells(B, r["area"])
        for p in r.get("except") or []:
            _cells(B, p, "except pair", n=2)
    elif t == "relation":
        _check_op(r)
        if not isinstance(r["pairs"], list) or not r["pairs"]:
            raise FormatError("pairs must be a non-empty list")
        for p in r["pairs"]:
            _cells(B, p, "pair", n=2)
    elif t in ("clone", "isomorphic"):
        regs = r["regions"]
        if not isinstance(regs, list) or len(regs) < 2 or (t == "isomorphic" and len(regs) != 2):
            raise FormatError(f"{t} takes " + ("2" if t == "isomorphic" else ">= 2") + " regions")
        n = None
        for reg in regs:
            cs = _cells(B, reg, "region")
            if n is not None and len(cs) != n:
                raise FormatError("regions must have equal sizes")
            n = len(cs)
    elif t == "equal_sum":
        if not isinstance(r["segments"], list) or len(r["segments"]) < 2:
            raise FormatError("equal_sum takes >= 2 segments")
        for s in r["segments"]:
            _cells(B, s, "segment")
    elif t == "table":
        if ("cells" in r) == ("where" in r):
            raise FormatError("table takes exactly one of cells / where")
        n = len(_cells(B, r["cells"])) if "cells" in r else len(r["where"])
        if not isinstance(r["allowed"], list) or any(not isinstance(x, list) or len(x) != n for x in r["allowed"]):
            raise FormatError("allowed must be a list of digit tuples of the table's width")
    elif t == "negative":
        of = r["of"]
        if of not in NEG_OF:
            raise FormatError(f"negative of {of!r} is not defined")
        sel = set(r) & {"color", "letter", "value", "sum", "kind", "split"}
        if of in ("kropki", "xv"):
            key = NEG_SELECTOR[of]
            if sel - {key}:
                raise FormatError(f"negative {of} takes only {key}")
        elif of in ("difference", "ratio", "product", "sum"):
            if sel != {NEG_SELECTOR[of]}:
                raise FormatError(f"negative {of} requires {NEG_SELECTOR[of]}")
        elif of in ("rossini", "battenburg"):
            if sel:
                raise FormatError(f"negative {of} takes no selector")
        elif of == "cell":
            ck = CELL.get(r["kind"]) if isinstance(r.get("kind"), str) else None
            if not ck or not ck.negative:
                raise FormatError("negative cell needs kind odd / even / low / high")
            if (ck.param == "split") != ("split" in r) or sel - {"kind", "split"}:
                raise FormatError("negative cell low / high need split (others take none)")
        if "area" in r:
            area_cells(B, r["area"])


def _validate_custom(r, B):
    """a custom rule (docs/formats/rules/custom.mdx, since pencilmark 1.2): known keys, existing cells, a well-formed
    scope, and an expression that parses and type-checks (a predicate when scoped, a condition otherwise)"""
    from ..rules import custom as CU

    for k in r:
        if k not in {"type", "holds", "cells", "scope", "each"} | COMMON:
            raise FormatError(f"unknown key {k!r}")
    if not isinstance(r.get("holds"), str):
        raise FormatError('custom rule: "holds" must be an expression (text)')
    cells = r.get("cells", {})
    if not isinstance(cells, dict):
        raise FormatError('custom rule: "cells" must be an object of named cell lists')
    for name, v in cells.items():
        if not re.fullmatch(r"[A-Za-z_]\w*", name) or name in CU.KEYWORDS:
            raise FormatError(f"custom rule: {name!r} is not a usable name")
        items = v if isinstance(v, list) else None
        if items is None or not items:
            raise FormatError(f"custom rule: cells {name!r} must be a non-empty list")
        for x in items:
            for c in x if isinstance(x, list) else [x]:
                if not isinstance(c, str):
                    raise FormatError(f"custom rule: cells {name!r} holds {c!r}, not a cell name")
                B.idx(c)
    each = r.get("each")
    if each is not None and not (isinstance(cells.get(each), list) and all(isinstance(x, list) for x in cells[each])):
        raise FormatError(f'custom rule: "each" must name a list of cell lists in "cells", got {each!r}')
    scope = r.get("scope")
    if scope is not None:
        kinds = [k for k in ("pairs", "windows", "neighbours") if k in (scope if isinstance(scope, dict) else {})]
        if not isinstance(scope, dict) or len(kinds) != 1 or set(scope) - {"pairs", "windows", "neighbours", "cells",
                                                                            "within", "except"}:  # fmt: skip
            raise FormatError(
                'custom rule: "scope" takes one of pairs / windows / neighbours (+ cells, within, except)'
            )
        kind = kinds[0]
        if kind in ("pairs", "neighbours") and scope[kind] not in CU.STEPS:
            raise FormatError(f"custom rule: scope {kind} {scope[kind]!r}; known: {sorted(CU.STEPS)}")
        if kind == "windows" and not (isinstance(scope["windows"], list) and len(scope["windows"]) == 2
                                      and all(isinstance(x, int) and x >= 1 for x in scope["windows"])):  # fmt: skip
            raise FormatError("custom rule: scope windows takes [height, width]")
        if "cells" in scope and scope["cells"] not in cells:
            raise FormatError(f"custom rule: scope cells {scope['cells']!r} is not a name in cells")
        if scope.get("within") not in (None, "box"):
            raise FormatError('custom rule: scope within takes "box"')
        for x in scope.get("except", []):
            for c in x if isinstance(x, list) else [x]:
                B.idx(c)
    try:
        top = CU.check(CU.parse(r["holds"]), set(cells))
    except CU.LangError as e:
        raise FormatError(f"custom rule: {e}") from None
    if scope is not None and top not in ("fn", "any"):
        raise FormatError("custom rule: a scoped rule's holds is a predicate, e.g. (a, b) => abs(a - b) != 4")
    if scope is None and top not in ("bool", "any"):
        raise FormatError("custom rule: holds must be a condition (true / false)")


def _check_op(r, where="rule"):
    """an operator and exactly its named parameter (docs/formats/puzzle-format.md 5.1), in a rule or an any_of entry"""
    op = r.get("op")
    if op not in OPS:
        raise FormatError(f"unknown operator {op!r}")
    if op == "allowed" and not _RESERVED_OK[0]:
        raise FormatError('operator "allowed" ' + RESERVED_MSG)
    want = OP_KEY.get(op)
    have = set(r) & OP_PARAM_KEYS
    if have != ({want} if want else set()):
        raise FormatError(
            f"operator {op} takes "
            + (f'"{want}"' if want else "no parameter")
            + (f", not {sorted(have - {want})}" if have - {want} else "")
        )
    if want in ("value", "sum") and (isinstance(r[want], bool) or not isinstance(r[want], int)):
        raise FormatError(f"operator {op}: {want} must be an integer")
    if op == "allowed" and not (
        isinstance(r["allowed"], list)
        and r["allowed"]
        and all(isinstance(x, list) and len(x) == 2 for x in r["allowed"])
    ):
        raise FormatError("operator allowed takes a non-empty list of digit pairs [[a, b], ...]")
    if op == "any_of":
        if not isinstance(r["any_of"], list) or not r["any_of"]:
            raise FormatError("any_of takes a non-empty list of {op, ...} entries")
        for x in r["any_of"]:
            if not isinstance(x, dict) or set(x) - {"op"} - OP_PARAM_KEYS:
                raise FormatError("any_of entries are objects with op and its parameter")
            _check_op(x, "any_of entry")
