#!/usr/bin/env python3
"""Independent checker: does a solution satisfy every rule of a pencilmark-puzzle document?

Written only from the docs (docs/formats/puzzle-format.md and the rule family pages, docs/formats/rules/*.mdx), not from
the engine, so it can arbitrate: tools/fuzz.py builds puzzles it accepts. Standard library only.
Usage: python3 -I spec_check.py file.jsonl [file.jsonl ...]
Prints per-rule-type counts and every violation (record name + rule description; never grids).
"""

import json
import re
import sys
from collections import Counter, defaultdict

CELL_RE = re.compile(r"^r([1-9][0-9]*)c([1-9][0-9]*)$")

# Keys allowed in a rule: 8.1 key order list + per-family keys named on the rule pages.
KNOWN_RULE_KEYS = {
    "type",
    "kind",
    "op",
    "any_of",
    "color",
    "letter",
    "value",
    "sum",
    "split",
    "values",
    "digits",
    "groups",
    "each",
    "counts",
    "arrow",
    "size",
    "repeat",
    "box",
    "step",
    "within",
    "closed",
    "side",
    "origin",
    "source",
    "bulb",
    "lines",
    "cells",
    "regions",
    "segments",
    "pairs",
    "except",
    "id",
    "label",
    "style",
    "of",
    "area",  # used on the negative / neighbors pages, not in the 8.1 list
}


class Doc:
    def __init__(self, d):
        self.d = d
        self.R = d["board"]["rows"]
        self.C = d["board"]["cols"]
        self.D = d["digits"]
        self.givens = d["givens"]
        self.sol = d.get("solution")

    def idx(self, name):
        m = CELL_RE.match(name)
        if not m:
            raise KeyError("bad cell name %r" % name)
        r, c = int(m.group(1)), int(m.group(2))
        if not (1 <= r <= self.R and 1 <= c <= self.C) or self.givens[(r - 1) * self.C + c - 1] is None:
            raise KeyError("missing cell %r" % name)
        return r, c

    def exists(self, r, c):
        return 1 <= r <= self.R and 1 <= c <= self.C and self.givens[(r - 1) * self.C + c - 1] is not None

    def v(self, rc):
        if isinstance(rc, str):
            rc = self.idx(rc)
        return self.sol[(rc[0] - 1) * self.C + rc[1] - 1]

    def all_cells(self):
        return [(r, c) for r in range(1, self.R + 1) for c in range(1, self.C + 1) if self.exists(r, c)]


def name(rc):
    return "r%dc%d" % rc


# ---------------------------------------------------------------- pair operators (5.1)
def pair_op(op, a, b, rule):
    if op == "different":
        return a != b
    if op == "equal":
        return a == b
    if op == "less":
        return a < b
    if op == "less_equal":
        return a <= b
    if op == "difference":
        return abs(a - b) == rule["value"]
    if op == "not_difference":
        return abs(a - b) != rule["value"]
    if op == "not_consecutive":
        return abs(a - b) != 1
    if op == "difference_at_least":
        return abs(a - b) >= rule["value"]
    if op == "difference_at_most":
        return abs(a - b) <= rule["value"]
    if op == "ratio":
        k = rule["value"]
        return a == k * b or b == k * a
    if op == "not_ratio":
        k = rule["value"]
        return not (a == k * b or b == k * a)
    if op == "sum":
        return a + b == rule["sum"]
    if op == "not_sum":
        return a + b != rule["sum"]
    if op == "parity_differs":
        return (a - b) % 2 == 1
    if op in ("same_third", "different_third"):
        same = (a - 1) // 3 == (b - 1) // 3
        return same if op == "same_third" else not same
    if op in ("same_mod3", "different_mod3"):
        same = a % 3 == b % 3
        return same if op == "same_mod3" else not same
    if op == "any_of":
        return any(pair_op(sub["op"], a, b, sub) for sub in rule["any_of"])
    raise NotImplementedError("op " + op)


# ---------------------------------------------------------------- houses (6.1)
def grid_area(doc, origin):
    r0, c0 = doc.idx(origin)
    D = doc.D
    cells = [(r, c) for r in range(r0, r0 + D) for c in range(c0, c0 + D)]
    for rc in cells:
        if not doc.exists(*rc):
            raise ValueError("grid area at %s has a missing cell %s" % (origin, name(rc)))
    return r0, c0, cells


def houses_of(doc, rule):
    """Return list of (kind, cells) houses stated by a house rule."""
    t = rule["type"]
    D = doc.D
    if t in ("grid", "box_grid"):
        r0, c0, _ = grid_area(doc, rule.get("origin", "r1c1"))
        hs = [("row", [(r0 + i, c0 + j) for j in range(D)]) for i in range(D)]
        hs += [("column", [(r0 + i, c0 + j) for i in range(D)]) for j in range(D)]
        if t == "box_grid":
            bh, bw = rule["box"]
            if bh * bw != D:
                raise ValueError("box_grid box %r does not hold D cells" % (rule["box"],))
            cd, ca = rule["count"]
            if bh * cd != D or bw * ca != D:
                raise ValueError("box_grid box %r x count %r does not tile the grid" % (rule["box"], rule["count"]))
            for bi in range(0, D, bh):
                for bj in range(0, D, bw):
                    hs.append(("box", [(r0 + bi + i, c0 + bj + j) for i in range(bh) for j in range(bw)]))
        return hs
    return [(t, [doc.idx(n) for n in rule["cells"]])]


def grid_areas(doc):
    out = []
    for rule in doc.d["rules"]:
        if rule["type"] in ("grid", "box_grid"):
            out.append(set(grid_area(doc, rule.get("origin", "r1c1"))[2]))
    return out


def resolve_area(doc, area):
    if area is None:
        return None
    if isinstance(area, str):
        return set(grid_area(doc, area)[2])
    return {doc.idx(n) for n in area}


# ---------------------------------------------------------------- geometry checks (3.2 / 3.4)
SIDE_DIR = {"top": (-1, 0), "bottom": (1, 0), "left": (0, -1), "right": (0, 1)}


def check_outside(doc, rule, diagonal_ok):
    cells = [doc.idx(n) for n in rule["cells"]]
    side = rule["side"]
    dr, dc = SIDE_DIR[side]
    r0, c0 = cells[0]
    if doc.exists(r0 + dr, c0 + dc):
        return "position next to cells[0] on side %s is an existing cell" % side
    if len(cells) >= 2:
        sr, sc = cells[1][0] - r0, cells[1][1] - c0
        if (sr, sc) not in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            return "cells not contiguous"
        for a, b in zip(cells, cells[1:]):
            if (b[0] - a[0], b[1] - a[1]) != (sr, sc):
                return "cells not collinear/contiguous"
        if sr != 0 and sc != 0:
            if not diagonal_ok:
                return "row/column clue runs diagonally"
            if (sr, sc) == (-dr, -dc) or (dr != 0 and sr != -dr) or (dc != 0 and sc != -dc):
                # diagonal must move away from the side
                return "diagonal does not run away from side %s" % side
        else:
            if (sr, sc) != (-dr, -dc):
                return "cells do not run straight away from side %s" % side
    return None


def touch(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1


def ortho(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def corner_positions(doc, cells):
    """Return (TL, TR, BL, BR) or raise if not a 2x2 block."""
    rcs = sorted(doc.idx(n) for n in cells)
    if len(rcs) != 4:
        raise ValueError("corner set does not have 4 cells")
    r, c = rcs[0]
    if rcs != [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]:
        raise ValueError("corner set is not a 2x2 block")
    return rcs


# ---------------------------------------------------------------- rule checks
class Fail(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def check_edge(doc, rule):
    cells = [doc.idx(n) for n in rule["cells"]]
    need(len(cells) == 2 and ortho(*cells), "STRUCT: edge cells not orthogonally adjacent")
    a, b = doc.v(cells[0]), doc.v(cells[1])
    k = rule["kind"]
    if k == "kropki":
        if rule["color"] == "white":
            need(abs(a - b) == 1, "white kropki not consecutive")
        else:
            need(a == 2 * b or b == 2 * a, "black kropki not 1:2")
    elif k == "xv":
        need(a + b == (10 if rule["letter"] == "X" else 5), "XV sum wrong")
    elif k == "difference":
        need(abs(a - b) == rule["value"], "difference wrong")
    elif k == "sum":
        need(a + b == rule["sum"], "sum wrong")
    elif k == "product":
        need(a * b == rule["value"], "product wrong")
    elif k == "ratio":
        kk = rule["value"]
        need(a == kk * b or b == kk * a, "ratio wrong")
    elif k == "greater":
        need(a > b, "cells[0] not > cells[1]")
    else:
        raise NotImplementedError


def check_corner(doc, rule):
    try:
        tl, tr, bl, br = corner_positions(doc, rule["cells"])
    except ValueError as e:
        raise Fail("STRUCT: " + str(e))
    A, B, Cc, Dd = (doc.v(x) for x in (tl, tr, bl, br))
    k = rule["kind"]
    if k == "battenburg":
        need(A % 2 == Dd % 2 and B % 2 == Cc % 2 and A % 2 != B % 2, "not a parity checkerboard")
    elif k == "exclude":
        need(rule["value"] not in (A, B, Cc, Dd), "excluded digit present")
    elif k == "mathrax":
        op = rule["op"]
        if op in ("even", "odd"):
            p = 0 if op == "even" else 1
            need(all(x % 2 == p for x in (A, B, Cc, Dd)), "not all " + op)
        else:
            val = rule["sum"] if op == "sum" else rule["value"]
            for x, y in ((A, Dd), (B, Cc)):
                hi, lo = max(x, y), min(x, y)
                if op == "sum":
                    ok = x + y == val
                elif op == "difference":
                    ok = hi - lo == val
                elif op == "product":
                    ok = x * y == val
                elif op == "ratio":
                    ok = hi == val * lo
                else:
                    raise NotImplementedError
                need(ok, "mathrax %s %s diagonal fails" % (op, val))
    else:
        raise NotImplementedError


def boxes_by_cell(doc):
    m = defaultdict(set)
    for i, rule in enumerate(doc.d["rules"]):
        if rule["type"] in ("box_grid", "box"):
            for kind, cells in houses_of(doc, rule):
                if kind == "box":
                    key = frozenset(cells)
                    for rc in cells:
                        m[rc].add(key)
    return m


def check_line(doc, rule):
    cells = [doc.idx(n) for n in rule["cells"]]
    need(len(cells) >= 2, "STRUCT: line with < 2 cells")
    for a, b in zip(cells, cells[1:]):
        need(touch(a, b), "STRUCT: consecutive line cells do not touch")
    vals = [doc.v(x) for x in cells]
    k = rule["kind"]
    closed = rule.get("closed", False)
    need(not closed or k in ("whisper", "renban", "parity"), "STRUCT: closed on kind %s" % k)
    adj = list(zip(vals, vals[1:])) + ([(vals[-1], vals[0])] if closed else [])
    D = doc.D
    if k == "thermo":
        need(all(a < b for a, b in zip(vals, vals[1:])), "not strictly increasing")
    elif k == "slow_thermo":
        need(all(a <= b for a, b in zip(vals, vals[1:])), "decreasing step")
    elif k == "whisper":
        kk = rule.get("value", 5 if D == 9 else None)
        need(kk is not None, "STRUCT: whisper without value when D != 9")
        need(all(abs(a - b) >= kk for a, b in adj), "adjacent difference < %d" % kk)
    elif k == "renban":
        need(len(set(vals)) == len(vals), "renban repeat")
        need(max(vals) - min(vals) == len(vals) - 1, "renban not consecutive")
    elif k == "parity":
        need(all((a - b) % 2 == 1 for a, b in adj), "adjacent same parity")
    elif k == "palindrome":
        need(vals == vals[::-1], "not a palindrome")
    elif k == "entropic":
        groups = rule.get("groups", [[1, 2, 3], [4, 5, 6], [7, 8, 9]] if D == 9 else None)
        need(groups is not None, "STRUCT: entropic without groups when D != 9")
        gi = {d: i for i, g in enumerate(groups) for d in g}
        for i in range(len(vals) - 2):
            need(
                sorted(gi.get(x, -1) for x in vals[i : i + 3]) == list(range(len(groups)))[:3] and len(groups) == 3,
                "run of 3 not one per group",
            )
    elif k == "modular":
        m = rule.get("value", 3 if D == 9 else None)
        need(m is not None, "STRUCT: modular without value when D != 9")
        for i in range(len(vals) - m + 1):
            need(sorted(x % m for x in vals[i : i + m]) == list(range(m)), "run of %d not one per residue" % m)
    elif k == "zipper":
        n = len(vals)
        tots = {vals[i] + vals[n - 1 - i] for i in range(n // 2)}
        if n % 2:
            tots.add(vals[n // 2])
        need(len(tots) <= 1, "zipper totals differ")
    elif k == "between":
        lo, hi = sorted((vals[0], vals[-1]))
        need(all(lo < x < hi for x in vals[1:-1]), "interior not strictly between ends")
    elif k == "lockout":
        kk = rule.get("value", 4 if D == 9 else None)
        need(kk is not None, "STRUCT: lockout without value")
        lo, hi = sorted((vals[0], vals[-1]))
        need(hi - lo >= kk, "lockout ends differ by < %d" % kk)
        need(all(x < lo or x > hi for x in vals[1:-1]), "lockout interior inside the range")
    elif k == "double_arrow":
        need(vals[0] + vals[-1] == sum(vals[1:-1]), "double arrow sum wrong")
    elif k == "region_sum":
        bm = boxes_by_cell(doc)
        segs, cur = [], [vals[0]]
        for i in range(1, len(cells)):
            if bm[cells[i]] != bm[cells[i - 1]]:
                segs.append(cur)
                cur = []
            cur.append(vals[i])
        segs.append(cur)
        need(len({sum(s) for s in segs}) == 1, "segment sums differ")
    else:
        raise NotImplementedError


def check_arrow(doc, rule):
    bulb = [doc.idx(n) for n in rule["bulb"]]
    num = 0
    for rc in bulb:
        num = num * 10 + doc.v(rc)
    for shaft in rule["lines"]:
        sc = [doc.idx(n) for n in shaft]
        need(any(touch(sc[0], b) for b in bulb), "STRUCT: shaft does not start next to bulb")
        for a, b in zip(sc, sc[1:]):
            need(touch(a, b), "STRUCT: shaft cells do not touch")
        need(sum(doc.v(x) for x in sc) == num, "shaft sum != bulb")


def check_cell(doc, rule):
    k = rule["kind"]
    D = doc.D
    for n in rule["cells"]:
        x = doc.v(n)
        if k == "odd":
            need(x % 2 == 1, "not odd")
        elif k == "even":
            need(x % 2 == 0, "not even")
        elif k == "low":
            need(1 <= x <= rule["split"], "not low")
        elif k == "high":
            need(rule["split"] < x <= D, "not high")
        elif k == "set":
            need(x in rule["values"], "not in set")
        elif k == "exclude":
            need(x not in rule["values"], "excluded value")
        else:
            raise NotImplementedError


def check_neighbours(doc, rule):
    k = rule.get("kind")
    if k == "antiknight":
        op, where = "different", "knight"
    elif k == "antiking":
        op, where = "different", "diagonal"
    elif k == "nonconsecutive":
        op, where = "not_consecutive", "orthogonal"
    elif k is None:
        op, where = rule["op"], rule["step"]
    else:
        raise NotImplementedError
    deltas = {
        "orthogonal": [(0, 1), (1, 0)],
        "diagonal": [(1, 1), (1, -1)],
        "king": [(0, 1), (1, 0), (1, 1), (1, -1)],
        "knight": [(1, 2), (2, 1), (1, -2), (2, -1)],
    }[where]
    area = resolve_area(doc, rule.get("area"))
    within = rule.get("within")
    groups = None
    if within == "box":
        groups = list(boxes_by_cell(doc).items())
        cellsets = defaultdict(set)
        for rc, keys in groups:
            cellsets[rc] = keys
        groups = cellsets
    elif within == "region":
        cellsets = defaultdict(set)
        for i, rr in enumerate(doc.d["rules"]):
            if rr["type"] == "region":
                for n in rr["cells"]:
                    cellsets[doc.idx(n)].add(i)
        groups = cellsets
    exc = {frozenset(doc.idx(n) for n in p) for p in rule.get("except", [])}
    bad = []
    for a in doc.all_cells():
        for dr, dc in deltas:
            b = (a[0] + dr, a[1] + dc)
            if not doc.exists(*b):
                continue
            if area is not None and not (a in area and b in area):
                continue
            if groups is not None and not (groups[a] & groups[b]):
                continue
            if frozenset((a, b)) in exc:
                continue
            if not pair_op(op, doc.v(a), doc.v(b), rule):
                bad.append("%s-%s" % (name(a), name(b)))
    need(not bad, "pairs fail: " + ",".join(bad[:6]))


def check_relation(doc, rule):
    bad = []
    for p in rule["pairs"]:
        a, b = doc.v(p[0]), doc.v(p[1])
        if not pair_op(rule["op"], a, b, rule):
            bad.append("%s-%s" % tuple(p))
    need(not bad, "pairs fail: " + ",".join(bad[:6]))


def ortho_positions(doc):
    """Orthogonal pairs within one grid (6.14)."""
    areas = grid_areas(doc)
    out = []
    for a in doc.all_cells():
        for dr, dc in ((0, 1), (1, 0)):
            b = (a[0] + dr, a[1] + dc)
            if not doc.exists(*b):
                continue
            if areas and not any(a in s and b in s for s in areas):
                continue
            out.append((a, b))
    return out


def check_negative(doc, rule):
    of = rule["of"]
    area = resolve_area(doc, rule.get("area"))
    rules = doc.d["rules"]
    bad = []

    def in_area(cells):
        return area is None or all(c in area for c in cells)

    if of in ("kropki", "xv", "difference", "ratio", "product", "sum"):
        exempt = {
            frozenset(doc.idx(n) for n in r["cells"]) for r in rules if r["type"] == "edge" and r.get("kind") == of
        }
        for a, b in ortho_positions(doc):
            if not in_area((a, b)) or frozenset((a, b)) in exempt:
                continue
            x, y = doc.v(a), doc.v(b)
            if of == "kropki":
                col = rule.get("color")
                ok = True
                if col in (None, "white") and abs(x - y) == 1:
                    ok = False
                if col in (None, "black") and (x == 2 * y or y == 2 * x):
                    ok = False
            elif of == "xv":
                let = rule.get("letter")
                ok = not ((let in (None, "X") and x + y == 10) or (let in (None, "V") and x + y == 5))
            elif of == "difference":
                ok = abs(x - y) != rule["value"]
            elif of == "ratio":
                k = rule["value"]
                ok = not (x == k * y or y == k * x)
            elif of == "product":
                ok = x * y != rule["value"]
            else:
                ok = x + y != rule["sum"]
            if not ok:
                bad.append("%s-%s" % (name(a), name(b)))
    elif of == "rossini":
        D = doc.D
        full = []
        for rr in rules:
            if rr["type"] in ("grid", "box_grid", "row", "column"):
                for kind, cells in houses_of(doc, rr):
                    if kind in ("row", "column") and len(cells) == D:
                        full.append(cells)
        exempt = set()
        for rr in rules:
            if rr["type"] == "rossini":
                cs = [doc.idx(n) for n in rr["cells"]]
                exempt.add(tuple(cs[:3]))
        seen = set()
        for cells in full:
            cells = sorted(cells)
            for trip in (tuple(cells[:3]), tuple(cells[::-1][:3])):
                if trip in seen:
                    continue
                seen.add(trip)
                if not in_area(trip) or trip in exempt:
                    continue
                v = [doc.v(c) for c in trip]
                mono = (v[0] < v[1] < v[2]) or (v[0] > v[1] > v[2])
                if mono:
                    bad.append("%s..%s" % (name(trip[0]), name(trip[2])))
    elif of == "battenburg":
        areas = grid_areas(doc)
        exempt = {
            frozenset(doc.idx(n) for n in r["cells"])
            for r in rules
            if r["type"] == "corner" and r.get("kind") == "battenburg"
        }
        for r, c in doc.all_cells():
            blk = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
            if not all(doc.exists(*x) for x in blk):
                continue
            if areas and not any(all(x in s for x in blk) for s in areas):
                continue
            if not in_area(blk) or frozenset(blk) in exempt:
                continue
            A, B, Cc, Dd = (doc.v(x) for x in blk)
            if A % 2 == Dd % 2 and B % 2 == Cc % 2 and A % 2 != B % 2:
                bad.append(name(blk[0]))
    elif of == "cell":
        kind = rule["kind"]
        exempt = set()
        for r in rules:
            if r["type"] == "cell" and r.get("kind") == kind:
                exempt |= {doc.idx(n) for n in r["cells"]}
        for rc in doc.all_cells():
            if rc in exempt or not in_area((rc,)):
                continue
            x = doc.v(rc)
            sat = {
                "odd": x % 2 == 1,
                "even": x % 2 == 0,
                "low": kind == "low" and x <= rule.get("split", 0),
                "high": kind == "high" and x > rule.get("split", 10**9),
            }[kind]
            if sat:
                bad.append(name(rc))
    else:
        raise NotImplementedError
    need(
        not bad,
        "uncovered positions satisfy the clue: "
        + ",".join(bad[:6])
        + (" (+%d)" % (len(bad) - 6) if len(bad) > 6 else ""),
    )


def check_outside_rule(doc, rule):
    t = rule["type"]
    diag_ok = (t == "sum" and rule.get("kind") == "little_killer") or t == "distinct_count"
    err = check_outside(doc, rule, diag_ok)
    need(err is None, "STRUCT: %s" % err)
    cells = [doc.idx(n) for n in rule["cells"]]
    vals = [doc.v(x) for x in cells]
    D = doc.D
    if t == "sandwich":
        need(1 in vals and D in vals, "AMBIG: 1 or D missing from cells")
        i, j = sorted((vals.index(1), vals.index(D)))
        need(sum(vals[i + 1 : j]) == rule["sum"], "sandwich sum wrong")
    elif t == "xsum":
        X = vals[0]
        need(X <= len(vals), "AMBIG: X exceeds number of cells")
        need(sum(vals[:X]) == rule["sum"], "x-sum wrong")
    elif t == "skyscraper":
        cnt, best = 0, None
        for x in vals:
            if best is None or x > best:
                cnt += 1
                best = x
        need(cnt == rule["value"], "visible count %d != %d" % (cnt, rule["value"]))
    elif t == "rossini":
        need(len(vals) == 3, "STRUCT: rossini cells != 3")
        if rule["arrow"] == "in":
            need(vals[0] < vals[1] < vals[2], "not increasing inwards")
        else:
            need(vals[0] > vals[1] > vals[2], "not decreasing inwards")
    elif t == "first_seen":
        first = next((x for x in vals if x in rule["digits"]), None)
        need(first == rule["value"], "first seen digit wrong")
    elif t == "sum":
        need(sum(vals) == rule["sum"], "sum wrong")
    elif t == "distinct_count":
        need(len(set(vals)) == rule["value"], "distinct count wrong")


def check_other(doc, rule):
    t = rule["type"]
    D = doc.D
    if t == "cage":
        vals = [doc.v(n) for n in rule["cells"]]
        need(len(set(vals)) == len(vals), "cage repeat")
        if "sum" in rule:
            need(sum(vals) == rule["sum"], "cage sum wrong")
    elif t == "region":
        vals = [doc.v(n) for n in rule["cells"]]
        need(len(set(vals)) == len(vals), "region repeat")
    elif t == "sum":
        k = rule["kind"]
        if k in ("little_killer", "frame"):
            return check_outside_rule(doc, rule)
        if k == "corner":
            try:
                corner_positions(doc, rule["cells"])
            except ValueError as e:
                raise Fail("STRUCT: " + str(e))
        need(sum(doc.v(n) for n in rule["cells"]) == rule["sum"], "sum wrong")
    elif t == "quadruple":
        vals = Counter(doc.v(n) for n in rule["cells"])
        for d, k in Counter(rule["digits"]).items():
            need(vals[d] >= k, "digit %d appears fewer than %d times" % (d, k))
    elif t == "appears":
        need(doc.v(rule["source"]) in [doc.v(n) for n in rule["cells"]], "source digit absent")
    elif t == "clone":
        regs = rule["regions"]
        for reg in regs[1:]:
            need([doc.v(n) for n in reg] == [doc.v(n) for n in regs[0]], "clone mismatch")
    elif t == "isomorphic":
        a, b = rule["regions"]
        fwd, bwd = {}, {}
        for x, y in zip(a, b):
            p, q = doc.v(x), doc.v(y)
            need(fwd.setdefault(p, q) == q and bwd.setdefault(q, p) == p, "no consistent relabelling")
    elif t == "count":
        vals = Counter(doc.v(n) for n in rule["cells"])
        if rule.get("kind") == "circles":
            need(all(vals[d] == d for d in vals), "circle counts wrong")
        elif "each" in rule:
            need(all(vals[d] == rule["each"] for d in range(1, D + 1)), "count each wrong")
        else:
            need(all(vals[d] == k for d, k in rule["counts"]), "counts wrong")
    elif t == "distinct_count":
        if "side" in rule:
            return check_outside_rule(doc, rule)
        need(len({doc.v(n) for n in rule["cells"]}) == rule["value"], "distinct count wrong")
    elif t == "global_entropy":
        for r, c in doc.all_cells():
            blk = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
            if all(doc.exists(*x) for x in blk):
                thirds = {(doc.v(x) - 1) // (D // 3) for x in blk}
                need(thirds == {0, 1, 2}, "2x2 window at %s lacks a third" % name((r, c)))
    elif t == "equal_sum":
        need(len({sum(doc.v(n) for n in s) for s in rule["segments"]}) == 1, "segment sums differ")
    elif t == "vudoku":
        v, a, b = (doc.v(n) for n in rule["cells"])
        need(v == a + b or v == abs(a - b), "vertex not sum/difference of arms")
    else:
        raise NotImplementedError


def check_table(doc, rule):
    # Not defined by the spec (6.17: reserved and refused). Supplementary reading only: the
    # solution tuple of `cells` should be one of `allowed`.
    tup = [doc.v(n) for n in rule["cells"]]
    need(tup in rule["allowed"], "solution tuple not in allowed list")


def rule_key(rule):
    t = rule["type"]
    if t == "relation":
        return "relation " + rule["op"]
    if t == "negative":
        return "negative " + rule["of"] + (" " + rule["kind"] if "kind" in rule else "")
    if "kind" in rule and t != "neighbors" or t == "neighbors" and "kind" in rule:
        return t + " " + rule["kind"]
    return t


def describe(rule):
    r = {k: v for k, v in rule.items() if k not in ("style", "allowed")}
    s = json.dumps(r, separators=(",", ":"))
    return s if len(s) < 220 else s[:217] + "..."


DISPATCH = {
    "edge": check_edge,
    "corner": check_corner,
    "line": check_line,
    "arrow": check_arrow,
    "cell": check_cell,
    "neighbors": check_neighbours,
    "relation": check_relation,
    "negative": check_negative,
    "sandwich": check_outside_rule,
    "xsum": check_outside_rule,
    "skyscraper": check_outside_rule,
    "rossini": check_outside_rule,
    "first_seen": check_outside_rule,
    "table": check_table,
}


def check_doc(doc, report):
    d = doc.d
    R, C, D = doc.R, doc.C, doc.D
    # envelope / implicit rules
    implicit = []
    if d.get("format") != "pencilmark-puzzle" or d.get("format_version") != 1:
        implicit.append("bad format/version")
    for k in d:
        if k not in (
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
        ):
            implicit.append("unknown top-level key " + k)
    if set(d["board"]) != {"rows", "cols"}:
        implicit.append("board has other keys")
    if not isinstance(D, int):
        implicit.append("digits not an integer")
    if len(doc.givens) != R * C or len(doc.sol) != R * C:
        implicit.append("givens/solution length != R*C")
    for i, (g, s) in enumerate(zip(doc.givens, doc.sol)):
        rc = "r%dc%d" % (i // C + 1, i % C + 1)
        if (g is None) != (s is None):
            implicit.append("null mismatch at " + rc)
        elif g is not None:
            if not (isinstance(s, int) and 1 <= s <= D):
                implicit.append("solution digit out of 1..D at " + rc)
            if g != 0 and g != s:
                implicit.append("given differs from solution at " + rc)
            if not (isinstance(g, int) and 0 <= g <= D):
                implicit.append("given out of range at " + rc)
    for n, lst in (d.get("candidates") or {}).items():
        report.count("candidates", 1)
        if doc.v(n) not in lst:
            implicit.append("solution not in candidates at " + n)
    report.count("implicit (givens/digits/shape)", 1)
    for m in implicit[:10]:
        report.violation("implicit (givens/digits/shape)", m, "")

    # houses
    house_rules = [r for r in d["rules"] if r["type"] in ("grid", "box_grid", "box", "row", "column")]
    house_cells = set()
    seen = set()
    for rule in house_rules:
        key = rule_key(rule)
        report.count(key, 1)
        try:
            hs = houses_of(doc, rule)
        except (ValueError, KeyError) as e:
            report.violation(key, "STRUCT: " + str(e), describe(rule))
            continue
        bad = []
        for kind, cells in hs:
            house_cells |= set(cells)
            fs = frozenset(cells)
            if fs in seen:
                continue
            seen.add(fs)
            vals = [doc.v(x) for x in cells]
            if len(set(vals)) != len(vals):
                bad.append("%s %s..%s repeats" % (kind, name(cells[0]), name(cells[-1])))
        if bad:
            report.violation(key, "; ".join(bad[:5]), describe(rule))

    for rule in d["rules"]:
        t = rule["type"]
        if t in ("grid", "box_grid", "box", "row", "column"):
            continue
        key = rule_key(rule)
        report.count(key, 1)
        unknown = set(rule) - KNOWN_RULE_KEYS - ({"allowed"} if t == "table" else set())
        if unknown:
            report.violation(key, "STRUCT: unknown keys %s" % sorted(unknown), describe(rule))
        if t == "table":
            report.note(key, "type 'table' is reserved and refused by 6.17; checked only as 'tuple in allowed'")
        fn = DISPATCH.get(t, check_other)
        try:
            fn(doc, rule)
            if t == "count":
                inter = [n for n in rule["cells"] if doc.idx(n) in house_cells]
                if inter:
                    raise Fail("STRUCT: count cells also in a house (6.13 MUST NOT): %d cells" % len(inter))
        except Fail as e:
            report.violation(key, str(e), describe(rule))
        except NotImplementedError:
            report.unchecked(key)
        except (KeyError, ValueError, TypeError, IndexError) as e:
            report.violation(key, "ERROR evaluating rule: %r" % (e,), describe(rule))


class Report:
    def __init__(self):
        self.checked = Counter()
        self.viol = defaultdict(list)
        self.unch = Counter()
        self.notes = {}
        self.cur = None

    def count(self, key, n):
        self.checked[key] += n

    def violation(self, key, msg, desc):
        self.viol[key].append((self.cur, msg, desc))

    def unchecked(self, key):
        self.unch[key] += 1
        self.checked[key] -= 1

    def note(self, key, msg):
        self.notes[key] = msg


def main(paths):
    rep = Report()
    skipped = []
    for p in paths:
        corpus = p
        for line in open(p):
            rec = json.loads(line)
            nm = rec.get("name")
            exp = rec.get("export")
            if not exp:
                skipped.append((corpus, nm, "no export"))
                continue
            d = json.loads(exp) if isinstance(exp, str) else exp
            if not d.get("solution"):
                skipped.append((corpus, nm, "no solution"))
                continue
            rep.cur = "%s :: %s" % ("private" if "golden_private" in corpus else "public", nm)
            try:
                check_doc(Doc(d), rep)
            except Exception as e:  # noqa
                rep.violation("document", "ERROR %r" % (e,), "")
    print("== skipped records")
    for s in skipped:
        print("  ", s[1], "(%s)" % s[2])
    print("\n== per rule type: checked / violations")
    for k in sorted(rep.checked, key=lambda k: -rep.checked[k]):
        print("  %-40s %6d  %d" % (k, rep.checked[k], len(rep.viol.get(k, []))))
    if rep.unch:
        print("\n== unchecked (not implemented)")
        for k, v in rep.unch.items():
            print("  ", k, v)
    for k, m in rep.notes.items():
        print("\n== note:", k, ":", m)
    print("\n== violations")
    for k, lst in rep.viol.items():
        for rec, msg, desc in lst:
            print("  [%s] %s :: %s :: %s" % (k, rec, msg, desc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
