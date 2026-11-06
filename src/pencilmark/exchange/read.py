"""Reading: a sudoku-puzzle dict -> puzzle JSON / engine Puzzle (to_internal, read)."""

from __future__ import annotations

from .. import puzzle_json as PJ
from ..rules.edge import NEG_SELECTOR, edge_relation, negative_relation
from ..rules.line import line_to_engine
from .board import _MATHRAX_OK, _NUMBERED_OK, battenburg_table, grid_area, product_pairs, read_houses
from .common import (
    KING_DIAG,
    KNIGHT,
    NEIGHBOUR_STEPS,
    NUMBERED_PAIR_FORM,
    OPS,
    ORTHO,
    FormatError,
    NotSupportedError,
    _op_params_to_engine,
    cell_name,
    op_params,
    parse_cell,
    with_origins,
)
from .validate import resolve_areas, validate


# ----------------------------------------------------------------------------------------------------------- reading
def to_internal(doc):
    """sudoku-puzzle (format_version 1) -> puzzle JSON (pencilmark.puzzle_json) that builds the engine Puzzle."""
    doc = with_origins(doc)
    B = validate(doc)
    D = B.D
    R, C = doc["board"]["rows"], doc["board"]["cols"]
    giv = doc["givens"]
    sym = lambda v: "." if not v else PJ._sym(v)
    out = {"digits": D, "numbers": "".join("#" if v is None else sym(v) for v in giv)}
    plain = R == C == D and None not in giv
    if not plain:
        out["shape"] = ["".join("." if giv[r * C + c] is None else "#" for c in range(C)) for r in range(R)]
    if doc.get("solution"):
        out["solution"] = "".join("#" if v is None else sym(v) for v in doc["solution"])
    rules = resolve_areas(B, doc["rules"])
    # houses (docs/formats/rules/houses-and-regions.mdx 6.1; a house equal to an earlier one is the same house)
    houses, areas = read_houses(rules, B)
    regions = [dict({"kind": k, "cells": [B.name(c) for c in cells]}, **kw) for k, cells, kw in houses]
    boxes = [set(cells) for k, cells, kw in houses if k == "box"]
    out["regions"] = regions
    ctx = _ReadCtx(B, rules, areas, boxes, regions)
    internal = []
    done = set()
    for i, r in enumerate(rules):
        if i in done:
            continue
        if r["type"] == "fog":  # how the puzzle is played, not a constraint: kept beside the rules (puzzle_json "fog")
            if not doc.get("solution"):
                raise FormatError("a fog puzzle needs its solution: a correct digit is what lights the fog")
            out["fog"] = {k: r[k] for k in ("lit", "triggers") if k in r}
            continue
        internal += ctx.rule(i, r, done)
    if internal:
        out["rules"] = internal
    if doc.get("candidates"):
        out["candidates"] = {
            k.lower(): "".join(PJ._sym(v) for v in sorted(set(vs))) for k, vs in doc["candidates"].items()
        }
    if doc.get("meta"):
        out["meta"] = dict(doc["meta"])
    if B.unknowns or B.layers:  # the file's unknowns and layers (the engine's aux variables)
        out["unknowns"] = {n: list(v) for n, v in B.unknowns.items()}
        out["layers"] = {n: {"values": list(v["values"]), "given": dict(v["given"])} for n, v in B.layers.items()}
    return out


def read(doc):
    """sudoku-puzzle dict -> engine Puzzle (not finalized)"""
    return PJ.from_json(to_internal(doc))


class _ReadCtx:
    def __init__(self, B, rules, subgrids, boxes, regions):
        """subgrids: the grid / box_grid areas (negative adjacency and battenburg windows stay inside one area)"""
        self.B, self.rules, self.D = B, rules, B.D
        self.subgrids = subgrids
        self.boxes = boxes
        self.regions = [set(B.idx(c) for c in g["cells"]) for g in regions if g["kind"] in ("diag", "window", "region")]
        self.sub_of = {}
        for k, s in enumerate(subgrids):
            for c in s:
                self.sub_of.setdefault(c, set()).add(k)
        fam = {}
        for r in rules:
            if r["type"] == "edge":
                a, b = (B.idx(c) for c in r["cells"])
                fam.setdefault(r["kind"], set()).add(frozenset((a, b)))
        self.family = fam
        self.houses = [
            set(B.idx(c) for c in g["cells"])
            for g in regions
            if g["kind"] in ("row", "col", "box", "diag", "window", "region")
        ]

    def share_house(self, a, b):
        """True if cells a and b lie in one house"""
        return any(a in h and b in h for h in self.houses)

    def pair_table(self, a, b, ok):
        """numbered pair clue as a 2-cell table (product order, equal digits only when the cells
        share no house)"""
        same = self.share_house(a, b)
        D = self.D
        allowed = [[u, v] for u in range(1, D + 1) for v in range(1, D + 1) if (u != v or not same) and ok(u, v)]
        return {"type": "table", "cells": [self.B.name(a), self.B.name(b)], "allowed": allowed}

    def n(self, cells):
        """cell indices -> their names"""
        return [self.B.name(c) for c in cells]

    def pairs_rule(self, kind, args, prs):
        """pairs rule dict (relation kind, its params, cell names) for the cell index pairs prs"""
        return {
            "type": "pairs",
            "rel": kind,
            "params": _engine_params_json(kind, args),
            "cells": [[self.B.name(a), self.B.name(b)] for a, b in prs],
        }

    def ortho_pairs(self, cells=None):
        """orthogonal pairs (of cells, or the whole board), kept within one subgrid when there are subgrids"""
        prs = self.B.pairs(ORTHO, cells)
        if self.subgrids:
            prs = [(a, b) for a, b in prs if self.sub_of.get(a, set()) & self.sub_of.get(b, set())]
        return prs

    def negative_pairs(self, of, sel_cells=None):
        """orthogonal pairs (of sel_cells, or the whole board) that have no edge clue of kind of"""
        exempt = self.family.get(of, set())
        return [(a, b) for a, b in self.ortho_pairs(sel_cells) if frozenset((a, b)) not in exempt]

    def rule(self, i, r, done):
        """engine rules for file rule r at index i; rules consumed with it are added to done"""
        B, D, t = self.B, self.D, r["type"]
        idx = lambda xs: [B.idx(c) for c in xs]
        if t in ("grid", "box_grid", "box", "row", "column", "region", "cage"):
            return []
        if t == "chaos":  # the rows / columns are houses (read_houses); the regions to find are a constraint
            r0, c0 = parse_cell(r["origin"])
            return [{"type": "chaos", "cells": [B.name(x) for x in sorted(grid_area(B, r0, c0))]}]
        if t == "yin_yang":  # shading: a constraint over the board (cpsat_verify; the engine refuses grading it)
            return [{"type": "yin_yang", "shaded": list(r.get("shaded", [])), "unshaded": list(r.get("unshaded", []))}]
        if t in ("region_border", "same_region"):
            return [{"type": t, "cells": list(r["cells"])}]
        if t == "line":  # rules/line.py
            return line_to_engine(r, D, B, self.pairs_rule)
        if t == "arrow":
            return [{"type": "arrow", "circle": list(r["bulb"]), "line": list(sh)} for sh in r["lines"]]
        if t == "edge":
            a, b = idx(r["cells"])
            k = r["kind"]
            if k == "kropki":
                return [{"type": "kropki", "color": r["color"], "cells": list(r["cells"])}]
            if k == "xv":
                return [{"type": "xv", "letter": r["letter"], "cells": list(r["cells"])}]
            if k == "greater":  # cells[0] > cells[1]: the engine's less-than of the reversed pair
                return [{"type": "less", "cells": [r["cells"][1], r["cells"][0]]}]
            if NUMBERED_PAIR_FORM == "table":
                return [self.pair_table(a, b, _NUMBERED_OK[k](r))]
            rel = edge_relation(r, D)
            return [self.pairs_rule(rel[0], tuple(rel[1:]), [(a, b)])]
        if t == "corner":
            k = r["kind"]
            tl, tr, bl, br = idx(r["cells"])
            if k == "exclude":
                return [{"type": "exclude", "digit": r["value"], "cells": list(r["cells"])}]
            if k == "mathrax":
                op = r["op"]
                if op in ("even", "odd"):
                    return [{"type": "parity", "parity": op, "cells": list(r["cells"])}]
                v = r["value"]
                if NUMBERED_PAIR_FORM == "table":
                    ok = _MATHRAX_OK[op](v)
                    return [self.pair_table(tl, br, ok), self.pair_table(tr, bl, ok)]
                rel = {"+": ("sum", v), "-": ("diff", v), "/": ("ratio", v), "x": ("allowed", product_pairs(D, v))}[op]
                return [
                    self.pairs_rule(rel[0], tuple(rel[1:]), [(tl, br)]),
                    self.pairs_rule(rel[0], tuple(rel[1:]), [(tr, bl)]),
                ]
            # battenburg corners (+ negative): one block in window order
            return self.battenburg(i, done)
        if t == "sum":
            con = {
                "type": "little_killer" if r["kind"] == "little_killer" else "sum",
                "cells": list(r["cells"]),
                "total": r["sum"],
            }
            return [con]
        if t in ("sandwich", "xsum"):
            return [{"type": t, "cells": list(r["cells"]), "total": r["sum"]}]
        if t == "skyscraper":
            return [{"type": t, "cells": list(r["cells"]), "count": r["value"]}]
        if t == "first_seen":
            return [{"type": t, "cells": list(r["cells"]), "value": r["value"], "digits": list(r["digits"])}]
        if t == "rossini":
            return self.rossini(i, done)
        if t == "neighbours":
            return self.neighbours(r)
        if t == "relation":
            kind = OPS[r["op"]]
            args = _op_params_to_engine(r["op"], op_params(r))
            return [self.pairs_rule(kind, args, [tuple(idx(p)) for p in r["pairs"]])]
        if t == "cell":
            k = r["kind"]
            if k in ("odd", "even"):
                return [{"type": "parity", "parity": k, "cells": list(r["cells"])}]
            if k == "set":
                return [
                    {
                        "type": "digit_class",
                        "digits": "".join(PJ._sym(v) for v in r["values"]),
                        "cells": list(r["cells"]),
                    }
                ]
            if k == "exclude":
                return [{"type": "exclude", "digit": v, "cells": list(r["cells"])} for v in r["values"]]
            return self.lowhigh(i, r, done)
        if t == "custom":  # the rule language: compiled where the puzzle is built (puzzle_json), kept by name
            from ..rules import custom as CU

            try:
                layers = tuple(
                    k
                    for k, t in (("region", "chaos"), ("shaded", "yin_yang"))
                    if any(x.get("type") == t for x in self.rules)
                )
                CU.compile_rule(r, self.B, self.D, layers)  # too large for a table: refused here, with its reason
            except CU.LangError as e:
                raise NotSupportedError(f"custom rule: {e}") from None
            return [{k: v for k, v in r.items() if k not in ("id", "label", "style")}]
        if t == "contains":
            return [{"type": "quadruple", "cells": list(r["cells"]), "digits": list(r["digits"])}]
        if t == "appears":
            return [{"type": "contains", "cells": [r["source"]] + list(r["cells"])}]
        if t == "clone":
            return [{"type": "clone", "regions": [list(x) for x in r["regions"]]}]
        if t == "isomorphic":
            return [{"type": "isomorphic", "pairs": [[a, b] for a, b in zip(*r["regions"])]}]
        if t == "count":
            if r.get("kind") == "circles":
                return [{"type": "counting_circles", "cells": list(r["cells"])}]
            con = {"type": "count", "cells": list(r["cells"])}
            if "each" in r:
                con["each"] = r["each"]
            else:
                con["digits"] = {str(d): k for d, k in r["counts"]}
            return [con]
        if t == "distinct_count":
            return [{"type": "distinct_count", "cells": list(r["cells"]), "count": r["value"]}]
        if t == "global_entropy":
            if D % 3:
                raise NotSupportedError("global entropy needs digits divisible by 3")
            return [{"type": "global_entropy"}]
        if t == "equal_sum":
            return [{"type": "equal_sum", "segments": [list(s) for s in r["segments"]]}]
        if t == "vudoku":
            return [{"type": "vudoku", "cells": list(r["cells"])}]
        if t == "table":
            allowed = [list(x) for x in r["allowed"]]
            if "cells" in r:
                return [{"type": "table", "cells": list(r["cells"]), "allowed": allowed}]
            out = []
            for rr, cc in sorted(B.cid):
                w = [(rr + dr, cc + dc) for dr, dc in r["where"]]
                if all(x in B.cid for x in w):
                    out.append({"type": "table", "cells": [cell_name(*x) for x in w], "allowed": allowed})
            return out
        if t == "negative":
            of = r["of"]
            if of == "rossini":
                return self.rossini(i, done)
            if of == "battenburg":
                return self.battenburg(i, done)
            if of == "cell":
                if r["kind"] in ("low", "high"):
                    return self.lowhigh(i, r, done)
                marked = {
                    B.idx(c) for x in self.rules if x["type"] == "cell" and x["kind"] == r["kind"] for c in x["cells"]
                }
                scope = set(idx(r["cells"])) if "cells" in r else set(range(len(B.coords)))
                rest = [c for c in range(len(B.coords)) if c in scope and c not in marked]
                other = "even" if r["kind"] == "odd" else "odd"
                return [{"type": "parity", "parity": other, "cells": self.n(rest)}] if rest else []
            sel = r.get(NEG_SELECTOR[of])
            prs = self.negative_pairs(of, idx(r["cells"]) if "cells" in r else None)
            return [self.pairs_rule(kind, args, prs) for kind, args in negative_relation(of, sel, D) if prs]
        raise FormatError(f"unknown rule type {t!r}")

    def neighbours(self, r):
        """engine rules for a neighbours rule: a whole-board kind, or the scoped cell pairs"""
        B = self.B
        k = r.get("kind")
        scoped = "within" in r or "cells" in r or "except" in r
        if k and not scoped:
            return [{"type": k}]
        steps = {"antiknight": KNIGHT, "antiking": KING_DIAG, "nonconsecutive": ORTHO}.get(k) or NEIGHBOUR_STEPS[
            r["where"]
        ]
        if k == "antiknight":
            steps = KNIGHT
        if not k and not ("within" in r or "cells" in r):
            out = {
                "type": "pairs",
                "rel": OPS[r["op"]],
                "params": _engine_params_json(OPS[r["op"]], _op_params_to_engine(r["op"], op_params(r))),
                "where": r["where"],
            }
            if r.get("except"):
                out["except"] = [list(p) for p in r["except"]]
            return [out]
        prs = B.pairs(steps, [B.idx(c) for c in r["cells"]] if "cells" in r else None)
        if r.get("within"):
            groups = self.boxes if r["within"] == "box" else self.regions
            prs = [(a, b) for a, b in prs if any(a in g and b in g for g in groups)]
        skip = {frozenset(B.idx(c) for c in p) for p in r.get("except") or []}
        prs = [(a, b) for a, b in prs if frozenset((a, b)) not in skip]
        if k:
            kind, args = ("nonconsec", ()) if k == "nonconsecutive" else ("neq", ())
        else:
            kind, args = OPS[r["op"]], _op_params_to_engine(r["op"], op_params(r))
        return [self.pairs_rule(kind, args, prs)] if prs else []

    def rossini(self, i, done):
        """engine rossini rule from all the rossini rules and their negative (plain D x D board only);
        marks them done"""
        B = self.B
        arrows, all_given = [], False
        for j, x in enumerate(self.rules):
            if x["type"] == "rossini":
                (r0, c0) = B.coords[B.idx(x["cells"][0])]
                side = x["side"]
                index = c0 + 1 if side in ("top", "bottom") else r0 + 1
                arrows.append({"side": side, "index": index, "towards": x["arrow"]})
                done.add(j)
            elif x["type"] == "negative" and x["of"] == "rossini":
                all_given = True
                done.add(j)
        if not (B.R == B.C == self.D and len(B.coords) == self.D**2):
            raise NotSupportedError("rossini is supported on a plain D x D board only")
        return [{"type": "rossini", "arrows": arrows, "all_given": all_given}]

    def battenburg(self, i, done):
        """engine table rules for the battenburg corners (every window when a negative is present);
        marks them done"""
        B, D = self.B, self.D
        marked, neg, scope = [], False, None
        for j, x in enumerate(self.rules):
            if x["type"] == "corner" and x["kind"] == "battenburg":
                marked.append([B.idx(c) for c in x["cells"]])
                done.add(j)
            elif x["type"] == "negative" and x["of"] == "battenburg":
                neg = True
                scope = set(B.idx(c) for c in x["cells"]) if "cells" in x else None
                done.add(j)
        T, F = battenburg_table(D, True), battenburg_table(D, False)
        if not neg:
            return [{"type": "table", "cells": self.n(w), "allowed": T} for w in marked]
        mk = {tuple(w) for w in marked}
        out = []
        for w in B.windows2x2():
            if self.subgrids and not any(set(w) <= s for s in self.subgrids):
                continue
            if scope is not None and not set(w) <= scope:
                continue
            out.append({"type": "table", "cells": self.n(w), "allowed": T if tuple(w) in mk else F})
        return out

    def lowhigh(self, i, r, done):
        """engine rule for a low / high cell rule: digit_class for marked cells only, lowhigh with a negative;
        marks the rules it consumes done"""
        B, D = self.B, self.D
        split = r["split"]
        hi_rules = [
            j
            for j, x in enumerate(self.rules)
            if x["type"] == "cell" and x["kind"] in ("low", "high") and x["split"] == split
        ]
        negs = [
            j
            for j, x in enumerate(self.rules)
            if x["type"] == "negative"
            and x["of"] == "cell"
            and x.get("kind") in ("low", "high")
            and x.get("split") == split
        ]
        if not negs:  # marked cells only: a digit-class clue
            k = r["kind"]
            vals = range(1, split + 1) if k == "low" else range(split + 1, D + 1)
            return [{"type": "digit_class", "digits": "".join(PJ._sym(v) for v in vals), "cells": list(r["cells"])}]
        neg = self.rules[negs[0]]
        done.update(hi_rules + negs)
        marked = {B.idx(c) for j in hi_rules for c in self.rules[j]["cells"] if self.rules[j]["kind"] == neg["kind"]}
        high = sorted(marked) if neg["kind"] == "high" else sorted(set(range(len(B.coords))) - marked)
        return [{"type": "lowhigh", "high": self.n(high), "split": split}]


def _engine_params_json(kind, args):
    if kind == "anyof":
        return [list(a) for a in args]
    if kind == "allowed":
        return [[list(x) for x in args[0]]]
    return list(args)
