"""Writing: an engine Puzzle -> a canonical pencilmark-puzzle dict (write)."""

from __future__ import annotations

import json
from collections import Counter

from .. import puzzle_json as PJ
from ..rules.edge import NEG_SELECTOR, edge_family, edge_rule
from ..rules.line import line_from_engine
from .board import Board, _bat, _factor_shapes, _pair_clue, grid_area, grid_units, vudoku_table
from .canonical import _norm_rule
from .common import (
    FORMAT,
    FORMAT_VERSION,
    KING_DIAG,
    KNIGHT,
    NEIGHBOUR_STEPS,
    ORTHO,
    REL_OP,
    UNIFY_TABLE_EDGES,
    NotSupportedError,
    _engine_params_to_op,
    cell_name,
    op_named,
    op_params,
)
from .validate import _RESERVED_OK, _merge_negatives


# ----------------------------------------------------------------------------------------------------------- writing
def write(p, meta=None, solution=None, provenance=False):
    """engine Puzzle -> pencilmark-puzzle dict (format_version 1). Raises NotSupportedError for engine structures the format
    cannot express. provenance=True returns (doc, prov): prov[i] = the engine objects rule i was written from
    ({"groups", "relations", "constraints", "clues"}: indices into p.groups / p.relations / p.constraints / p.cell_clues)."""
    w = _Writer(p)
    doc = w.run(meta, solution)
    aux = getattr(p, "aux", None)
    if aux:  # the file's unknowns and layers: custom rules read them, so they are written with the rules
        name = lambda c: f"r{p.coords[c][0] + 1}c{p.coords[c][1] + 1}"
        if aux["unknowns"]:
            doc["unknowns"] = {u["name"]: {"values": list(u["values"])} for u in aux["unknowns"]}
        if aux["layers"]:
            doc["layers"] = {
                L["name"]: dict(
                    {"values": list(L["values"])},
                    **({"given": {name(int(c)): v for c, v in L["given"].items()}} if L["given"] else {}),
                )
                for L in aux["layers"]
            }
    fog = getattr(p, "fog", None)
    if fog:  # fog of war: a rule of play, written after the constraints (not an engine constraint)
        doc["rules"].append({"type": "fog", **{k: fog[k] for k in ("lit", "triggers") if k in fog}})
        w.prov.append({"groups": [], "relations": [], "constraints": [], "clues": []})
    prov = w.prov
    src = getattr(p, "_pm_input_rules", None)
    if src:
        doc, prov = _input_order(doc, prov, src)
    return (doc, prov) if provenance else doc


def _input_order(doc, prov, src):
    """the rules of a puzzle read from a pencilmark-puzzle file back in the file's order, with their id / label / style
    (docs/formats/puzzle-format.md 8.1: rules in the order given). Only when the written rules are exactly the file's rules up to spelling;
    otherwise the written order stays."""
    D = doc.get("digits")
    key = lambda r: json.dumps(_norm_rule(r, D), sort_keys=True)
    try:
        want = [key(r) for r in src]
        have = [key(r) for r in doc["rules"]]
    except Exception:
        return doc, prov
    if sorted(want) != sorted(have):
        return doc, prov
    free = {}
    for i, k in enumerate(have):
        free.setdefault(k, []).append(i)
    order = [free[k].pop(0) for k in want]
    rules = []
    for j, i in enumerate(order):
        r = dict(doc["rules"][i])
        for extra in ("id", "label", "style", "draw"):
            if extra in src[j]:
                r[extra] = src[j][extra]
        rules.append(r)
    doc = dict(doc)
    doc["rules"] = rules
    return doc, [prov[i] for i in order] if prov is not None else prov


class _Writer:
    def __init__(self, p):
        self.p = p
        key = set(getattr(p, "iso_key", []) or [])
        self.key = key
        coords = [rc for i, rc in enumerate(p.coords) if i not in key]
        if key and sorted(key) != list(range(len(coords), len(p.coords))):
            raise NotSupportedError("twin digit-key cells must come last")
        self.B = Board(coords, p.D)
        self.D = p.D

    # ---------------------------------------------------------------- groups
    def eff_groups(self):
        """(kind, cells, total) per engine group, with the normalized kinds (docs/guides/development/engine-mapping.md: jigsaw pieces stored as regions ->
        box; SudokuPad explicit houses -> row / column / box / region)."""
        p, B, D = self.p, self.B, self.D
        gs = [g for g in p.groups if not (self.key and set(g.cells) & self.key)]
        self.gidx = [k for k, g in enumerate(p.groups) if not (self.key and set(g.cells) & self.key)]
        out = []
        boxes = [g for g in gs if g.kind == "box"]
        cand = [
            g
            for g in gs
            if g.kind in ("region", "jigsaw")
            and g.complete
            and g.total is None
            and len(g.cells) == D
            and not self.straight(g.cells)
        ]
        piece = set()
        if cand:
            allb = boxes + cand
            cover = [c for g in allb for c in g.cells]
            if len(cover) == len(set(cover)) == len(B.coords):
                piece = {id(g) for g in cand}
        for g in gs:
            kind = g.kind
            if id(g) in piece:
                kind = "box"
            elif kind in ("house", "partial"):
                st = self.straight(g.cells)
                kind = (
                    st
                    if (st and len(g.cells) == D and g.complete)
                    else ("box" if g.complete and len(g.cells) == D else "region")
                )
            if g.total is not None and kind != "cage":
                kind = "cage"
            if len(g.cells) == D and not g.complete and kind != "cage":
                raise NotSupportedError("houses that need not hold every digit (digit-selection puzzles) are reserved")
            if g.complete and len(g.cells) != D:
                raise NotSupportedError(f"complete group of {len(g.cells)} cells on a {D}-digit board")
            out.append((kind, tuple(g.cells), g.total, g.complete))
        return out

    def straight(self, cells):
        """'row' or 'col' if cells are consecutive along one row or column, else None"""
        co = [self.B.coords[c] for c in cells]
        if all(r == co[0][0] for r, _ in co) and [c for _, c in co] == list(range(co[0][1], co[0][1] + len(co))):
            return "row"
        if all(c == co[0][1] for _, c in co) and [r for r, _ in co] == list(range(co[0][0], co[0][0] + len(co))):
            return "col"
        return None

    def write_groups(self):
        """engine groups -> house / region / cage rules (docs/formats/rules/houses-and-regions.mdx, 6.1): every D x D area whose rows and columns are all
        houses is a box_grid (its boxes a regular tiling) or a grid, placed where its first own house was; the remaining
        rows / columns / boxes are explicit rules; regions and cages keep their place."""
        B, D = self.B, self.D
        gs = self.eff_groups()
        where = {}
        for k, (kind, cells, total, complete) in enumerate(gs):
            if kind in ("row", "col", "box") and total is None and complete and len(cells) == D:
                where.setdefault((kind, frozenset(cells)), []).append(k)
        cands = set()
        for kind, fs in where:
            if kind == "row":
                r, c = min(B.coords[x] for x in fs)
                cands |= {(r - k, c) for k in range(D)}
        grids = []
        for r0, c0 in cands:
            units = grid_units(B, r0, c0)
            if not units or not all((u[0], frozenset(u[1])) in where for u in units):
                continue
            box = None
            for shape in _factor_shapes(D):
                bu = grid_units(B, r0, c0, shape)[2 * D :]
                if all(("box", frozenset(u[1])) in where for u in bu):
                    box, units = shape, units + bu
                    break
            grids.append([None, r0, c0, box, units])
        share = Counter(frozenset(u[1]) for g in grids for u in g[4])
        for g in grids:  # order: first house that belongs to this grid only (overlapping grids share boxes)
            own = [u for u in g[4] if share[frozenset(u[1])] == 1] or g[4]
            g[0] = min(where[(u[0], frozenset(u[1]))][0] for u in own)
        grids.sort(key=lambda g: (g[0], g[1], g[2]))
        items, covered, used = [], set(), set()
        for first, r0, c0, box, units in grids:
            if all(frozenset(u[1]) in covered for u in units):
                continue
            covered |= {frozenset(u[1]) for u in units}
            gi = sorted(k for u in units for k in where[(u[0], frozenset(u[1]))] if k not in used)
            used |= set(gi)
            rule = {"type": "box_grid" if box else "grid"}
            if (r0, c0) != (0, 0):  # the origin defaults to r1c1 (6.1)
                rule["origin"] = cell_name(r0, c0)
            chaos = [set(c["cells"]) for c in self.p.constraints if c.get("type") == "chaos"]
            if not box and grid_area(B, r0, c0) in chaos:  # its regions are to be found (6.3)
                rule["type"] = "chaos"
                no2 = [r_ for r_, _ in getattr(self.p, "named_rules", []) if r_.get("type") == "chaos_no_2x2"]
                if any({B.idx(x) for x in r_["cells"]} == grid_area(B, r0, c0) for r_ in no2):
                    rule["no_2x2"] = True
            if box:
                rule["box"] = list(box)
                rule["count"] = [B.D // box[0], B.D // box[1]]
            items.append((first, {"rule": rule, "area": grid_area(B, r0, c0), "units": units, "gi": gi}))
        seen = set(covered)
        self.merged_duplicates = len(used) - len(covered)
        for k, g in enumerate(gs):
            if k in used:
                continue
            kind, cells, total, _ = g
            if kind in ("row", "col", "box"):
                if frozenset(cells) in seen:
                    self.merged_duplicates += 1  # normalization: a house listed twice is one house
                    continue
                seen.add(frozenset(cells))
            items.append((k, {"g": g, "gi": [k]}))
        items.sort(key=lambda kv: kv[0])
        rules = []
        self.group_prov = []
        self.subgrids = [it["area"] for _, it in items if "rule" in it]
        self.grid_areas = [(it["rule"].get("origin", "r1c1"), it["area"]) for _, it in items if "rule" in it]
        self.box_sets = []
        for _, it in items:
            prov = {"groups": {self.gidx[k] for k in it["gi"]}}
            if "rule" in it:
                rules.append(it["rule"])
                self.box_sets += [set(u[1]) for u in it["units"] if u[0] == "box"]
            else:
                kind, cells, total, _ = it["g"]
                if kind == "box":
                    self.box_sets.append(set(cells))
                rules.append(self.group_rule(kind, cells, total))
            self.group_prov.append(prov)
        return rules

    def group_rule(self, kind, cells, total):
        """pencilmark-puzzle rule dict for an engine group of this kind, cells and total"""
        B = self.B
        names = [B.name(c) for c in cells]
        if kind == "cage":
            r = {"type": "cage"}
            if total is not None:
                r["sum"] = total
            r["cells"] = names
            return r
        if kind in ("row", "col", "box"):
            return {"type": {"col": "column"}.get(kind, kind), "cells": names}
        if kind == "diag":
            return {"type": "region", "kind": "diagonal", "cells": names}
        if kind == "window":
            return {"type": "region", "kind": "window", "cells": names}
        return {"type": "region", "kind": "disjoint" if self.is_disjoint(cells) else "extra", "cells": names}

    def is_disjoint(self, cells):
        """True if cells are the same position in each box (a disjoint-groups region)"""
        D = self.D
        if D not in PJ.BOXES or len(cells) != D or not (self.B.R == self.B.C == D):
            return False
        bh, bw = PJ.BOXES[D]
        co = [self.B.coords[c] for c in cells]
        return len({(r % bh, c % bw) for r, c in co}) == 1 and len({(r // bh, c // bw) for r, c in co}) == D

    # ---------------------------------------------------------------- run
    def run(self, meta, solution):
        """engine puzzle -> pencilmark-puzzle dict (givens, solution, meta, candidates, rules); sets self.prov"""
        p, B, D = self.p, self.B, self.D
        R, C = B.R, B.C
        flat = {i: rc[0] * C + rc[1] for i, rc in enumerate(B.coords)}
        givens = [None] * (R * C)
        for i in range(len(B.coords)):
            givens[flat[i]] = p.givens.get(i, 0)
        d = {"format": FORMAT, "format_version": FORMAT_VERSION}
        from ..export import read_meta

        m = read_meta({"meta": meta or {}})
        if m:
            d["meta"] = m
        placed = getattr(p, "placed", None) or ()
        for i in placed:  # digits filled in after the start: written apart from the givens
            givens[flat[i]] = 0
        d.update({"board": {"rows": R, "cols": C}, "digits": D, "givens": givens})
        if placed:
            d["placed"] = {B.name(i): p.givens[i] for i in sorted(placed, key=lambda i: B.coords[i])}
        if solution is not None:
            sol = [None] * (R * C)
            for i, v in enumerate(list(solution)[: len(B.coords)]):
                sol[flat[i]] = int(v)
            d["solution"] = sol
        rules = self.write_groups()
        prov = list(self.group_prov)
        cands, clue_rules = self.cell_clues()
        rules += [r for r, _ in clue_rules]
        prov += [pr for _, pr in clue_rules]
        rest = self.write_rules()
        rules += [r for r, _ in rest]
        prov += [pr for _, pr in rest]
        rules, prov = _merge_negatives(rules, prov)
        if cands:
            d["candidates"] = cands
        d["rules"] = rules
        self.prov = prov
        return d

    def cell_clues(self):
        """-> (candidates, [(rule, provenance)]): the cell clues as rules; candidates only where no clue explains
        the domain"""
        p, B, D = self.p, self.B, self.D
        n = len(B.coords)
        implied = [(1 << D) - 1] * len(p.domains)
        out = []
        for k, (r_, masks) in enumerate(getattr(p, "cell_clues", [])):
            for c_, m_ in masks.items():
                implied[c_] &= m_
            out += [(x, {"clues": {k}}) for x in self.clue_rule(r_)]
        cands = {}
        for i, m in enumerate(p.domains[:n]):
            if m != implied[i]:
                cands[B.name(i)] = [v for v in range(1, D + 1) if m >> (v - 1) & 1]
        return cands, out

    def clue_rule(self, r):
        """pencilmark-puzzle rules for one engine cell clue (parity, digit_class, exclude, lowhigh)"""
        B, D = self.B, self.D
        nm = lambda xs: [B.name(x) if isinstance(x, int) else x.lower() for x in xs]
        t = r["type"]
        if t == "parity":
            cells = nm(r["cells"])
            idx = [B.idx(c) for c in cells]
            if B.is_block(idx):
                return [{"type": "corner", "kind": "mathrax", "op": r["parity"], "cells": cells}]
            return [{"type": "cell", "kind": r["parity"], "cells": cells}]
        if t == "digit_class":
            return [
                {
                    "type": "cell",
                    "kind": "set",
                    "values": [PJ._val(ch) for ch in str(r["digits"])],
                    "cells": nm(r["cells"]),
                }
            ]
        if t == "exclude":
            cells = nm(r["cells"])
            if B.is_block([B.idx(c) for c in cells]):
                return [{"type": "corner", "kind": "exclude", "value": int(r["digit"]), "cells": cells}]
            return [{"type": "cell", "kind": "exclude", "values": [int(r["digit"])], "cells": cells}]
        if t == "lowhigh":
            split = int(r.get("split", (D + 1) // 2))
            return [
                {"type": "cell", "kind": "high", "split": split, "cells": nm(r.get("high", []))},
                {"type": "negative", "of": "cell", "kind": "high", "split": split},
            ]
        raise NotSupportedError(f"cell clue {t!r}")

    # ---------------------------------------------------------------- relations / constraints
    def write_rules(self):
        """[(rule, provenance)] for the relations, constraints and named rules, in engine order"""
        p = self.p
        rels = list(p.relations)
        cons = list(p.constraints)
        compiled = any(c.get("_compiled") for c in cons if c.get("type") in ("line", "clone"))
        drop_rel = [False] * len(rels)
        drop_con = [False] * len(cons)
        if compiled:
            comp, comp_cons, _ = PJ._compiled_extras(p)
            for k in range(len(rels) - 1, -1, -1):  # compiled relations come last (finalize appends them)
                if comp[rels[k]] > 0:
                    comp[rels[k]] -= 1
                    drop_rel[k] = True
            cc = Counter(comp_cons)
            for k in range(len(cons) - 1, -1, -1):
                key = json.dumps(
                    {a: b for a, b in cons[k].items() if not a.startswith("_")}, sort_keys=True, default=list
                )
                if cc[key] > 0:
                    cc[key] -= 1
                    drop_con[k] = True
        # the compiled parts of a line (finalize appends them, tagged line_kind) are written with their line; one whose
        # line is missing (a reader that built only the part) is kept and written on its own, never dropped
        line_cells = [set(c.get("cells") or ()) for c in cons if c.get("type") == "line"]
        for k, c in enumerate(cons):
            if c.get("line_kind"):
                own = set(c.get("cells") or ()) | {x for s_ in c.get("segments") or () for x in s_}
                if any(own <= L for L in line_cells):
                    drop_con[k] = True
        # named rules (puzzle_json.add_named / from_json): their relations and constraints
        named_items = []
        used = [False] * len(rels)
        for rule, nrels in getattr(p, "named_rules", []):
            pos = None
            if nrels:
                L = len(nrels)
                for s in range(len(rels) - L + 1):
                    if not any(used[s : s + L]) and not any(drop_rel[s : s + L]) and rels[s : s + L] == list(nrels):
                        pos = s
                        break
                if pos is None:
                    raise NotSupportedError(f"named rule {rule.get('type')} relations not found")
                for s in range(pos, pos + len(nrels)):
                    used[s] = True
            named_items.append(
                {
                    "rule": rule,
                    "rel": pos,
                    "con": None,
                    "nrel": len(nrels),
                    "prov": {"relations": set(range(pos, pos + len(nrels))) if nrels else set()},
                }
            )
        named_cons = [k for k, c in enumerate(cons) if c.get("_named") and not drop_con[k]]
        # assign named constraints to named rules in order (each named rule's constraints are contiguous)
        cursor = 0
        for it in named_items:
            n_c = self.named_cons_count(it["rule"])
            if n_c:
                if cursor + n_c > len(named_cons):
                    raise NotSupportedError(f"named rule {it['rule'].get('type')} constraints not found")
                it["con"] = named_cons[cursor]
                it["prov"]["constraints"] = set(named_cons[cursor : cursor + n_c])
                cursor += n_c
        self.family = self.family_positions(rels, [u or d for u, d in zip(used, drop_rel)], cons, drop_con)
        rel_items = self.relation_items(rels, [u or d for u, d in zip(used, drop_rel)])
        con_items = self.constraint_items(cons, drop_con)
        # merge the relation stream and the constraint stream; named rules with both link them
        sr = sorted(
            [(x["pos"], "r", x) for x in rel_items]
            + [(it["rel"], "n", it) for it in named_items if it["rel"] is not None],
            key=lambda z: z[0],
        )
        sc = sorted(
            [(x["pos"], "c", x) for x in con_items]
            + [(it["con"], "n", it) for it in named_items if it["con"] is not None],
            key=lambda z: z[0],
        )
        out = [
            (r, it["prov"])
            for it in named_items
            if it["rel"] is None and it["con"] is None
            for r in self.named_rule(it["rule"])
        ]
        emitted = set()
        i = j = 0

        def emit(kind, x):
            if kind == "n":
                if id(x) in emitted:
                    return
                emitted.add(id(x))
                out.extend((r, x["prov"]) for r in self.named_rule(x["rule"]))
            else:
                pr = {"relations": set(x.get("rel") or ()), "constraints": set(x.get("con") or ())}
                out.extend((r, pr) for r in x["rules"])

        while i < len(sr) or j < len(sc):
            while i < len(sr) and (sr[i][1] == "r" or id(sr[i][2]) in emitted):
                emit(sr[i][1], sr[i][2])
                i += 1
            while j < len(sc) and (sc[j][1] == "c" or id(sc[j][2]) in emitted or sc[j][2]["rel"] is None):
                emit(sc[j][1], sc[j][2])
                j += 1
            if i < len(sr):  # a named rule with relations: its constraints (if any) are next in sc
                emit("n", sr[i][2])
                i += 1
            elif j < len(sc):
                emit(sc[j][1], sc[j][2])
                j += 1
        return out

    def named_cons_count(self, rule):
        """number of engine constraints the named rule compiled to"""
        t = rule.get("type")
        D, B = self.D, self.B
        if t == "global_entropy":
            return len(B.windows2x2())
        if t in ("quadruple", "vudoku"):
            return 1
        if t == "rossini":
            if not rule.get("all_given", True):
                return 0
            return 4 * D - len(rule.get("arrows", []))
        if t == "isomorphic":
            n = len(rule["pairs"]) if "pairs" in rule else D * D
            return n * D
        return 0

    def named_rule(self, rule):
        """pencilmark-puzzle rules for a named engine rule (global entropy, quadruple, vudoku, ...)"""
        B, D = self.B, self.D
        t = rule["type"]
        nm = lambda xs: [B.name(x) if isinstance(x, int) else x.lower() for x in xs]
        if t == "global_entropy":
            return [{"type": "global_entropy"}]
        if t == "custom":  # written back as read, the expression in its canonical spelling
            from .canonical import _holds

            return [dict(rule, holds=_holds(rule["holds"]))]
        if t == "quadruple":
            return [{"type": "quadruple", "digits": [int(v) for v in rule["digits"]], "cells": nm(rule["cells"])}]
        if t in ("region_sight", "border_count", "other_region_sum"):
            return [dict(rule, cells=nm(rule["cells"]))]
        if t == "chaos_no_2x2":  # written as the chaos rule's option (write_groups)
            return []
        if t == "region_sum_line":  # a region-sum line on a board with regions to find
            return [{"type": "line", "kind": "region_sum", "cells": nm(rule["cells"])}]
        if t == "vudoku":
            return [{"type": "vudoku", "cells": nm(rule["cells"])}]
        if t == "increasing":
            return [{"type": "line", "kind": "thermo", "cells": nm(rule["cells"])}]
        if t == "rossini":
            out = []
            for a in rule.get("arrows", []):
                cells = PJ._edge_line(None, D, a["side"], a["index"])[:3]
                out.append(
                    {
                        "type": "rossini",
                        "arrow": a.get("towards", "in"),
                        "side": a["side"],
                        "cells": [B.name(c) for c in cells],
                    }
                )
            if rule.get("all_given", True):
                out.append({"type": "negative", "of": "rossini"})
            return out
        if t == "isomorphic":
            if "pairs" in rule:
                prs = [(x.lower(), y.lower()) for x, y in rule["pairs"]]
            else:
                (r1, c1), (r2, c2) = rule["origins"]
                prs = [(cell_name(r1 + a, c1 + b), cell_name(r2 + a, c2 + b)) for a in range(D) for b in range(D)]
            return [{"type": "isomorphic", "regions": [[x for x, _ in prs], [y for _, y in prs]]}]
        raise NotSupportedError(f"named rule {t!r}")

    # ------------------------------------------------ relations
    def family_positions(self, rels, skip, cons, drop_con):
        """adjacent pairs carrying an edge clue, per family (for the negative exemptions)"""
        B, D = self.B, self.D
        fam = {}
        for k, rel in enumerate(rels):
            if skip[k]:
                continue
            kind, a, b, args = rel[0], rel[1], rel[2], tuple(rel[3:])
            if a in self.key or b in self.key or not B.adjacent(a, b):
                continue
            f = edge_family(kind, args, D)
            if f:
                fam.setdefault(f[0], set()).add(frozenset((a, b)))
        for k, c in enumerate(cons):
            if drop_con[k] or c.get("_named"):
                continue
            if c.get("type") == "table" and len(c["cells"]) == 2 and B.adjacent(*c["cells"]) and UNIFY_TABLE_EDGES:
                f = self.table_edge(c)
                if f:
                    fam.setdefault(f[0], set()).add(frozenset(c["cells"]))
        return fam

    def table_edge(self, c):
        """(family, value) of a 2-cell table that is an edge clue, or None"""
        m = _pair_clue(self.D, c["allowed"])
        if m is None:
            return None
        op, v = m
        # a table is a NUMBERED clue: never re-read as a kropki dot / XV letter
        return ({"x": "product", "+": "sum", "-": "difference", "/": "ratio"}[op], v)

    def relation_items(self, rels, skip):
        """runs of engine relations -> v1 rule items {"pos", "rules"} keeping the relation order"""
        B, D = self.B, self.D
        live = [k for k in range(len(rels)) if not skip[k]]
        for k in live:
            if rels[k][1] in self.key or rels[k][2] in self.key:
                raise NotSupportedError("relation on a twin digit-key cell")
        items = []
        # runs of identical (kind, args)
        runs, cur = [], []
        for k in live:
            sig = (rels[k][0], tuple(rels[k][3:]))
            if cur and (rels[cur[-1]][0], tuple(rels[cur[-1]][3:])) == sig:
                cur.append(k)
            else:
                if cur:
                    runs.append(cur)
                cur = [k]
        if cur:
            runs.append(cur)
        for run in runs:
            kind, args = rels[run[0]][0], tuple(rels[run[0]][3:])
            if kind not in REL_OP:
                raise NotSupportedError(f"engine relation {kind!r} has no format_version 1 operator")
            prs = [(rels[k][1], rels[k][2]) for k in run]
            pos = 0
            while pos < len(prs):
                hit = self.whole_rule(kind, args, prs, pos)
                if hit:
                    rule, n = hit
                    items.append({"pos": run[pos], "rules": [rule], "rel": run[pos : pos + n]})
                    pos += n
                    continue
                a, b = prs[pos]
                f = edge_family(kind, args, D) if B.adjacent(a, b) else None
                if f:
                    items.append({"pos": run[pos], "rules": [edge_rule(f[0], f[1], a, b, B)], "rel": [run[pos]]})
                else:
                    op = REL_OP[kind]
                    if op == "allowed" and not _RESERVED_OK[0]:
                        raise NotSupportedError(
                            "a pair clue with no rule family (an explicit digit-pair list); the allowed "
                            "operator is reserved in format_version 1 (a custom rule can express it, 6.18)"
                        )
                    params = _engine_params_to_op(kind, args)
                    last = items[-1]["rules"][-1] if items else None
                    if last and last.get("type") == "relation" and last["op"] == op and op_params(last) == params:
                        last["pairs"].append([B.name(a), B.name(b)])
                        items[-1]["rel"].append(run[pos])
                    else:
                        items.append(
                            {
                                "pos": run[pos],
                                "rel": [run[pos]],
                                "rules": [
                                    dict(
                                        {"type": "relation", "op": op},
                                        **op_named(op, params),
                                        pairs=[[B.name(a), B.name(b)]],
                                    )
                                ],
                            }
                        )
                pos += 1
        return items

    def ortho_in_subgrids(self):
        """orthogonal cell pairs, kept within one subgrid when there are subgrids"""
        prs = self.B.pairs(ORTHO)
        if self.subgrids:
            sub_of = {}
            for k, s in enumerate(self.subgrids):
                for c in s:
                    sub_of.setdefault(c, set()).add(k)
            prs = [(a, b) for a, b in prs if sub_of.get(a, set()) & sub_of.get(b, set())]
        return prs

    def whole_rule(self, kind, args, prs, pos):
        """a neighbors / negative rule whose expansion is prs[pos:pos+n] (as a set) -> (rule, n) or None"""
        B, D = self.B, self.D
        rest = prs[pos:]
        fs = lambda L: {frozenset(x) for x in L}
        first = frozenset(rest[0])
        cands = []
        if kind == "neq" and not args:
            kn = B.pairs(KNIGHT)
            cands.append(({"type": "neighbors", "kind": "antiknight"}, kn))
            cands.append(({"type": "neighbors", "kind": "antiking"}, B.pairs(KING_DIAG)))
            if self.box_sets:
                cands.append(
                    (
                        {"type": "neighbors", "kind": "antiknight", "within": "box"},
                        [(a, b) for a, b in kn if any(a in g and b in g for g in self.box_sets)],
                    )
                )
                cands.append(
                    (
                        {"type": "neighbors", "kind": "antiking", "within": "box"},
                        [(a, b) for a, b in B.pairs(KING_DIAG) if any(a in g and b in g for g in self.box_sets)],
                    )
                )
        if kind == "nonconsec" and not args:
            cands.append(({"type": "neighbors", "kind": "nonconsecutive"}, B.pairs(ORTHO)))
        if len(self.grid_areas) > 1 and kind in ("neq", "nonconsec") and not args:  # the same rule on one grid only
            for nk, steps in (
                (("antiknight", KNIGHT), ("antiking", KING_DIAG)) if kind == "neq" else (("nonconsecutive", ORTHO),)
            ):
                for org, area in self.grid_areas:
                    cands.append(({"type": "neighbors", "kind": nk, "area": org}, B.pairs(steps, sorted(area))))
        neg = {
            ("nonconsec", ()): ("kropki", "white"),
            ("notdiff", (1,)): ("kropki", "white"),
            ("notratio", (2,)): ("kropki", "black"),
            ("notsum", (10,)): ("xv", "X"),
            ("notsum", (5,)): ("xv", "V"),
        }
        frozen = lambda x: tuple(frozen(y) for y in x) if isinstance(x, (list, tuple)) else x
        key = (kind, frozen(args))  # any_of / allowed parameters hold lists
        nf = neg.get(key)
        if nf is None and len(args) == 1 and kind in ("notdiff", "notsum", "notratio"):
            nf = ({"notdiff": "difference", "notsum": "sum", "notratio": "ratio"}[kind], args[0])
        if nf:
            of, sel = nf
            exempt = self.family.get(of, set())
            exp = [(a, b) for a, b in self.ortho_in_subgrids() if frozenset((a, b)) not in exempt]
            rule = {"type": "negative", "of": of, NEG_SELECTOR[of]: sel}
            if kind == "nonconsec" and not exempt and fs(exp) == fs(B.pairs(ORTHO)):
                pass  # plain non-consecutive: the neighbors rule above
            else:
                cands.append((rule, exp))
            if len(self.grid_areas) > 1:  # the negative on one grid only
                for org, area in self.grid_areas:
                    cands.append((dict(rule, area=org), [(a, b) for a, b in exp if a in area and b in area]))
        for rule, exp in cands:
            n = len(exp)
            if n and n <= len(rest) and first in fs(exp) and fs(rest[:n]) == fs(exp):
                return rule, n
        # generic whole-grid rule with exceptions (the old "pairs where" form), symmetric relations only
        if pos == 0 and len(prs) >= 12 and PJ._symmetric(kind, list(args), D) and kind not in ("anyof",):
            have = fs(prs)
            if len(have) == len(prs):
                for where, steps in NEIGHBOUR_STEPS.items():
                    alln = B.pairs(steps)
                    if have <= fs(alln) and len(have) * 2 > len(alln):
                        # must expand in the same order: the where-form expands in board order minus the exceptions
                        missing = [x for x in alln if frozenset(x) not in have]
                        exp = [x for x in alln if frozenset(x) in have]
                        if [frozenset(x) for x in exp] == [frozenset(x) for x in prs]:
                            rule = dict(
                                {"type": "neighbors", "op": REL_OP[kind]},
                                **op_named(REL_OP[kind], _engine_params_to_op(kind, args)),
                                step=where,
                            )
                            if missing:
                                rule["except"] = [[B.name(a), B.name(b)] for a, b in missing]
                            return rule, len(prs)
        return None

    # ------------------------------------------------ constraints
    def constraint_items(self, cons, drop):
        """items {pos, rules, con} for the live constraints, with table blocks and arrow lines merged"""
        B = self.B
        items = []
        live = [i for i in range(len(cons)) if not drop[i] and not cons[i].get("_named")]
        # tables: battenburg blocks / global entropy blocks are detected over runs
        i = 0
        while i < len(live):
            c = cons[live[i]]
            t = c.get("type")
            if any(x in self.key for x in self.con_cells(c)):
                raise NotSupportedError("constraint on a twin digit-key cell")
            if "offset" in c:
                raise NotSupportedError("shifted digit sets (digit-selection puzzles) are reserved")
            if t == "table":
                blk = self.table_block(cons, live, i)
                if blk:
                    rules, n = blk
                    items.append({"pos": live[i], "rules": rules, "con": live[i : i + n]})
                    i += n
                    continue
            if t == "arrow":
                j = i
                lines = []
                while j < len(live) and cons[live[j]].get("type") == "arrow" and cons[live[j]]["circle"] == c["circle"]:
                    lines.append([B.name(x) for x in cons[live[j]]["line"]])
                    j += 1
                items.append(
                    {
                        "pos": live[i],
                        "rules": [{"type": "arrow", "bulb": [B.name(x) for x in c["circle"]], "lines": lines}],
                        "con": live[i:j],
                    }
                )
                i = j
                continue
            items.append({"pos": live[i], "rules": self.constraint_rule(c), "con": [live[i]]})
            i += 1
        return items

    def con_cells(self, c):
        """cell indices a constraint refers to"""
        out = list(c.get("cells") or []) + list(c.get("circle") or []) + list(c.get("line") or [])
        for k in ("segments", "regions", "houses"):
            for s in c.get(k) or []:
                out += list(s)
        return [x for x in out if isinstance(x, int)]

    def table_block(self, cons, live, i):
        """global entropy (all 2x2 windows, exact table) or battenburg (every window of the subgrids marked / unmarked) at
        live[i:], or a single table that is a known mechanic -> (rules, n) or None"""
        B, D = self.B, self.D
        c = cons[live[i]]
        cells = list(c["cells"])
        A = [tuple(x) for x in c["allowed"]]
        wins = B.windows2x2()
        if len(cells) == 4 and D % 3 == 0 and wins and cells == wins[0]:
            ent = [tuple(x) for x in PJ.entropy_table(D)]
            n = len(wins)
            if i + n <= len(live) and all(
                cons[live[i + k]].get("type") == "table"
                and list(cons[live[i + k]]["cells"]) == wins[k]
                and [tuple(x) for x in cons[live[i + k]]["allowed"]] == ent
                for k in range(n)
            ):
                return [{"type": "global_entropy"}], n
        if len(cells) == 4 and B.is_block(cells):
            T, F = _bat(D)
            if A in (T, F):
                ws = [w for w in wins if not self.subgrids or any(set(w) <= s for s in self.subgrids)]
                n = len(ws)
                if cells == ws[0] and i + n <= len(live):
                    blk = [cons[live[i + k]] for k in range(n)]
                    if all(
                        x.get("type") == "table"
                        and list(x["cells"]) == ws[k]
                        and [tuple(y) for y in x["allowed"]] in (T, F)
                        for k, x in enumerate(blk)
                    ):
                        rules = [
                            {"type": "corner", "kind": "battenburg", "cells": [B.name(y) for y in ws[k]]}
                            for k, x in enumerate(blk)
                            if [tuple(y) for y in x["allowed"]] == T
                        ]
                        return rules + [{"type": "negative", "of": "battenburg"}], n
                if A == T:
                    return [{"type": "corner", "kind": "battenburg", "cells": [B.name(y) for y in cells]}], 1
        if len(cells) == 2 and B.adjacent(*cells) and UNIFY_TABLE_EDGES:
            f = self.table_edge(c)
            if f:  # normalization 8: a 2-cell table edge clue -> pair relation
                return [edge_rule(f[0], f[1], cells[0], cells[1], B)], 1
        # mathrax corner: tables on (TL, BR) then (TR, BL) of a 2x2 block with the same clue
        if len(cells) == 2 and i + 1 < len(live) and cons[live[i + 1]].get("type") == "table" and UNIFY_TABLE_EDGES:
            c2 = cons[live[i + 1]]
            if len(c2["cells"]) == 2:
                tl, br = cells
                tr, bl = c2["cells"]
                blk = [tl, tr, bl, br]
                if B.is_block(blk):
                    m1, m2 = self.mathrax_clue(c), self.mathrax_clue(c2)
                    if m1 and m1 == m2:
                        op = {"x": "product", "+": "sum", "-": "difference", "/": "ratio"}[m1[0]]
                        key = "sum" if op == "sum" else "value"
                        return [
                            {
                                "type": "corner",
                                "kind": "mathrax",
                                "op": op,
                                key: m1[1],
                                "cells": [B.name(x) for x in blk],
                            }
                        ], 2
        if len(cells) == 3 and A == [tuple(x) for x in vudoku_table(D)]:
            return [{"type": "vudoku", "cells": [B.name(x) for x in cells]}], 1
        if len(cells) == 4 and B.is_block(cells):  # the quadruple clue (other tables that happen to match stay tables)
            need = self.quadruple_need(A, len(cells))
            if need is not None:
                return [{"type": "quadruple", "digits": need, "cells": [B.name(x) for x in cells]}], 1
        return None

    def mathrax_clue(self, c):
        """(op, value) when a 2-cell table is exactly one numbered pair clue, else None"""
        return _pair_clue(self.D, c["allowed"])

    def quadruple_need(self, A, n):
        """digits every tuple of the table A holds when A is exactly that 'contains' rule over n cells,
        else None"""
        D = self.D
        if not A or len(A) == D**n:
            return None
        need = []
        for v in range(1, D + 1):
            k = min(t.count(v) for t in A)
            need += [v] * k
        if not need or len(need) > n:
            return None
        if [tuple(x) for x in PJ.quadruple_table(D, n, need)] == A:
            return need
        return None

    def constraint_rule(self, c):
        """pencilmark-puzzle rules for one engine constraint"""
        B, D = self.B, self.D
        t = c.get("type")
        nm = lambda xs: [B.name(x) for x in xs]
        if t == "line":  # rules/line.py
            return line_from_engine(c, B, D)
        if t == "sum":
            cells = list(c["cells"])
            common = self.common_group(cells)
            if c.get("distinct") and not common:  # normalization 9: a no-repeat sum is a cage
                return [{"type": "cage", "sum": c["total"], "cells": nm(cells)}]
            side = B.outside_side(cells) if len(cells) >= 2 else None
            if side and len(cells) < D and B.outside_ok(side, cells, False):
                return [{"type": "sum", "kind": "frame", "sum": c["total"], "side": side, "cells": nm(cells)}]
            if B.is_block(cells):
                return [{"type": "sum", "kind": "corner", "sum": c["total"], "cells": nm(cells)}]
            return [{"type": "sum", "kind": "group", "sum": c["total"], "cells": nm(cells)}]
        if t == "little_killer":
            cells = list(c["cells"])
            side = B.outside_side(cells)
            if side is None:
                raise NotSupportedError("little killer whose diagonal does not start at the edge of the board")
            return [{"type": "sum", "kind": "little_killer", "sum": c["total"], "side": side, "cells": nm(cells)}]
        if t in ("sandwich", "xsum", "skyscraper", "first_seen"):
            cells = list(c["cells"])
            side = B.outside_side(cells)
            if side is None or not B.outside_ok(side, cells, False):
                raise NotSupportedError(f"{t} clue whose cells do not start at the edge of the board")
            r = {"type": t}
            if t in ("sandwich", "xsum"):
                r["sum"] = c["total"]
            elif t == "skyscraper":
                r["value"] = c["count"]
            else:
                r["value"] = c["value"]
                r["digits"] = list(c.get("digits") or [1, 2, 3])
            r["side"] = side
            r["cells"] = nm(cells)
            return [r]
        if t == "set":
            if c.get("kind") != "consecutive":
                raise NotSupportedError(f"set constraint of kind {c.get('kind')!r}")
            cells = list(c["cells"])
            if all(B.touching(a, b) for a, b in zip(cells, cells[1:])):
                return [{"type": "line", "kind": "renban", "cells": nm(cells)}]  # normalization 1
            raise NotSupportedError("a consecutive set whose cells are not a line")
        if t == "between":
            cells = list(c["cells"])
            if all(B.touching(a, b) for a, b in zip(cells, cells[1:])):
                return [{"type": "line", "kind": "between", "cells": nm(cells)}]  # normalization 2
            raise NotSupportedError("a between constraint whose cells are not a line")
        if t == "equal_sum":
            return [self.equal_sum_rule(c)]
        if t == "table":
            if not _RESERVED_OK[0]:
                raise NotSupportedError(
                    "a digit table with no rule family (reserved in format_version 1; a custom rule can express it, "
                    "6.18)"
                )
            return [{"type": "table", "cells": nm(c["cells"]), "allowed": [list(x) for x in c["allowed"]]}]
        if t == "count":
            r = {"type": "count"}
            if "each" in c:
                r["each"] = c["each"]
            else:
                r["counts"] = sorted([int(k), v] for k, v in c["digits"].items())
            r["cells"] = nm(c["cells"])
            return [r]
        if t == "counting_circles":
            return [{"type": "count", "kind": "circles", "cells": nm(c["cells"])}]
        if t == "distinct_count":
            cells = list(c["cells"])
            r = {"type": "distinct_count", "value": c["count"]}
            side = B.outside_side(cells) if len(cells) >= 2 else None
            if side:
                r["side"] = side
            r["cells"] = nm(cells)
            return [r]
        if t == "contains":
            return [{"type": "appears", "source": B.name(c["cells"][0]), "cells": nm(c["cells"][1:])}]
        if t == "clone":
            return [{"type": "clone", "regions": [nm(x) for x in c["regions"]]}]
        if t == "chaos":  # written as the grid rule of its area (write_groups)
            return []
        if t in ("region_border", "same_region"):
            return [{"type": t, "cells": nm(c["cells"])}]
        if t == "yin_yang":
            out = {"type": "yin_yang"}
            for k in ("shaded", "unshaded"):
                if c.get(k):
                    out[k] = nm(sorted(c[k], key=lambda x: B.coords[x]))
            return [out]
        raise NotSupportedError(f"engine constraint {t!r} has no format_version 1 rule")

    def common_group(self, cells):
        """True if cells all lie in one group"""
        s = set(cells)
        return any(s <= set(g.cells) for g in self.p.groups)

    def equal_sum_rule(self, c):
        """pencilmark-puzzle rule for an equal_sum constraint: a zipper, double arrow or region-sum line when it is one,
        else equal_sum"""
        B = self.B
        segs = [list(s) for s in c["segments"]]
        flat = [x for s in segs for x in s]
        path = lambda xs: all(B.touching(a, b) for a, b in zip(xs, xs[1:]))
        nm = lambda xs: [B.name(x) for x in xs]
        # zipper: pairs (ids[k], ids[n-1-k]) then the middle cell
        n = len(flat)
        pairs = [s for s in segs if len(s) == 2]
        mid = [s for s in segs if len(s) == 1]
        if len(pairs) == n // 2 and len(mid) == n % 2 and segs == pairs + mid and len(set(flat)) == n:
            ids = [None] * n
            for k, (a, b) in enumerate(pairs):
                ids[k], ids[n - 1 - k] = a, b
            if mid:
                ids[n // 2] = mid[0][0]
            if path(ids):
                return {"type": "line", "kind": "zipper", "cells": nm(ids)}  # normalization 3
        # double arrow: [[a, b], middle]
        if len(segs) == 2 and len(segs[0]) == 2 and segs[1]:
            ids = [segs[0][0]] + segs[1] + [segs[0][1]]
            if path(ids):
                return {"type": "line", "kind": "double_arrow", "cells": nm(ids)}
        # region sum: the segments are the line cut at box borders
        if path(flat) and len(set(flat)) == n:
            box = {
                cc: gi
                for gi, g in enumerate(self.p.groups)
                if g.complete and g.kind in ("box", "region", "jigsaw")
                for cc in g.cells
            }
            cut, cur = [], [flat[0]]
            for x in flat[1:]:
                if box.get(x) == box.get(cur[-1]):
                    cur.append(x)
                else:
                    cut.append(cur)
                    cur = [x]
            cut.append(cur)
            if cut == segs:
                return {"type": "line", "kind": "region_sum", "cells": nm(flat)}  # normalization 3
        return {"type": "equal_sum", "segments": [nm(s) for s in segs]}
