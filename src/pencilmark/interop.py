"""Interop strings and ipuz export (docs/FORMAT.md section 12).

    from_string(s) -> sudoku-puzzle dict        plain classic strings and sudokuwiki.org packed strings (S9B, S6B, X9B, W9B,
                                                C9B, J9B, L9B, M9B, L6C)
    to_string(puzzle, "plain" | "sudokuwiki")   the reverse (refuses what the target cannot express)
    to_ipuz(puzzle) -> dict                     ipuz 2 for classic / Latin square / diagonal / windoku / jigsaw / killer

The sudokuwiki encodings are those of the validated encoder of the research tree (his solutions matched ours
on every validated puzzle, 2026-10-08 / 2026-10-25); the decoder reads exactly what that encoder writes and refuses anything
else (placed digits in plain forms, candidate masks, 6x6 killer operators other than '+').
"""
from __future__ import annotations

import re

from . import puzzle_json as PJ
from .exchange import FORMAT, FORMAT_VERSION, FormatError, NotSupportedError, cell_name, parse_cell

B36 = "0123456789abcdefghijklmnopqrstuvwxyz"
WIDTH = {"S": 2, "X": 2, "W": 2, "C": 2, "J": 3, "L": 4, "M": 5}
WINDOKU_COL = "955596669711172227711172227711172227955596669833384448833384448833384448955596669"
COLOUR_COL = "123123123456456456789789789123123123456456456789789789123123123456456456789789789"


def _b36(n, width):
    s = ""
    while n:
        s = B36[n % 36] + s
        n //= 36
    return s.rjust(width, "0")


def _doc(D, givens, rules, meta=None):
    d = {"format": FORMAT, "format_version": FORMAT_VERSION}
    if meta:
        d["meta"] = meta
    d.update({"grid": {"rows": D, "cols": D}, "digits": D, "givens": givens, "rules": rules})
    return d


def _subgrid(D, box=True):
    r = {"type": "subgrid", "size": D}
    if box:
        r["box"] = list(PJ.BOXES[D])
    r["origin"] = "r1c1"
    return r


# ------------------------------------------------------------------------------------------------------------ reading
_PACKED = re.compile(r"([SXWCJLM])(\d+)([BC])([0-9a-zA-Z]+)")


def from_string(s, symbols=None):
    """plain classic string or sudokuwiki packed string -> sudoku-puzzle dict"""
    t = re.sub(r"\s+", "", s or "")
    m = _PACKED.fullmatch(t)
    if m and len(m.group(4)) == WIDTH[m.group(1)] * int(m.group(2)) ** 2:
        return _from_sudokuwiki(m.group(1), int(m.group(2)), m.group(3), m.group(4).lower())
    return _from_plain(t, symbols)


def _from_plain(t, symbols=None):
    n = len(t)
    D = PJ.SIZES.get(n)
    if D is None:
        raise FormatError(f"a plain string has D*D characters (16, 36, 81, ...); got {n}")
    giv = []
    for ch in t:
        if ch in ".0-_":
            giv.append(0)
        elif symbols:
            if ch not in symbols:
                raise FormatError(f"symbol {ch!r} not in {symbols!r}")
            giv.append(symbols.index(ch) + 1)
        else:
            v = PJ.SYMBOLS.find(ch.upper()) + 1
            if not 1 <= v <= D:
                raise FormatError(f"symbol {ch!r} is not a digit of a {D}x{D} puzzle")
            giv.append(v)
    return _doc(D, giv, [_subgrid(D)])


def _from_sudokuwiki(kind, D, ver, body):
    if (kind, D, ver) not in {("S", 9, "B"), ("S", 6, "B"), ("X", 9, "B"), ("W", 9, "B"), ("C", 9, "B"), ("J", 9, "B"),
                              ("L", 9, "B"), ("M", 9, "B"), ("L", 6, "C")}:
        raise NotSupportedError(f"sudokuwiki string {kind}{D}{ver} is not supported")
    w = WIDTH[kind]
    vals = [int(body[i * w:(i + 1) * w], 36) for i in range(D * D)]
    full = (1 << D) - 1
    killer = kind in ("L", "M")
    empty = full + 18 if not (kind == "L" and D == 6) else 75          # the encoder's empty-cell values (S6B 81, L6C 75)
    givens, box_lab, col, clue = [], [], [], []
    for v in vals:
        if kind in ("S", "X", "W", "C"):
            n = v
        elif kind == "J":
            n, box_lab_ = v & 1023, (v >> 10) + 1
            box_lab.append(box_lab_)
        elif kind == "L" and D == 9:
            n, clue_, col_ = v & 1023, (v >> 10) & 63, (v >> 16) + 1
            clue.append(clue_); col.append(col_)
        elif kind == "M":
            n, clue_, col_, box_ = v & 1023, (v >> 10) & 63, ((v >> 16) & 7) + 1, (v >> 19) + 1
            clue.append(clue_); col.append(col_); box_lab.append(box_)
        else:                                       # L6C
            n, clue_, col_ = v & 127, (v >> 7) & 2047, (v >> 18) + 1
            clue.append(clue_); col.append(col_)
        if n == empty:
            givens.append(0)
        elif not killer and 1 <= n <= D:
            givens.append(n)
        elif killer and D < n <= 2 * D:
            givens.append(n - D)
        else:
            raise NotSupportedError(f"sudokuwiki cell value {n} (placed digit or candidate mask) is not supported")
    rules = []
    if kind in ("J", "M"):
        rules.append(_subgrid(D, box=False))
        groups = {}
        for i, lab in enumerate(box_lab):
            groups.setdefault(lab, []).append(i)
        if sorted(len(g) for g in groups.values()) != [D] * D:
            raise FormatError("jigsaw box labels do not make D boxes of D cells")
        for lab, cells in sorted(groups.items(), key=lambda kv: min(kv[1])):
            rules.append({"type": "box", "cells": [cell_name(*divmod(c, D)) for c in cells]})
    else:
        rules.append(_subgrid(D))
    nm = lambda i: cell_name(*divmod(i, D))
    if kind == "X":
        rules += [{"type": "region", "kind": "diagonal", "cells": [nm(i * D + i) for i in range(D)]},
                  {"type": "region", "kind": "diagonal", "cells": [nm(i * D + D - 1 - i) for i in range(D)]}]
    elif kind == "W":
        for wr in (1, 5):
            for wc in (1, 5):
                rules.append({"type": "region", "kind": "window",
                              "cells": [nm((wr + a) * 9 + wc + b) for a in range(3) for b in range(3)]})
    elif kind == "C":
        groups = {}
        for i, ch in enumerate(COLOUR_COL):
            groups.setdefault(ch, []).append(i)
        for ch in sorted(groups, key=lambda k: min(groups[k])):
            rules.append({"type": "region", "kind": "disjoint", "cells": [nm(i) for i in groups[ch]]})
    if killer:
        rules += _cages_from_colours(D, col, clue, kind == "L" and D == 6)
    return _doc(D, givens, rules, meta={"source": "sudokuwiki.org"})


def _cages_from_colours(D, col, clue, ops):
    owner, comps = {}, []
    for s in range(D * D):
        if s in owner:
            continue
        comp, st = [s], [s]
        owner[s] = len(comps)
        while st:
            x = st.pop()
            r, c = divmod(x, D)
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                y = rr * D + cc
                if 0 <= rr < D and 0 <= cc < D and y not in owner and col[y] == col[x]:
                    owner[y] = len(comps); comp.append(y); st.append(y)
        comps.append(sorted(comp))
    rules = []
    for comp in comps:
        first = comp[0]
        total = clue[first]
        r, c = divmod(first, D)
        op_cell = None
        if ops and len(comp) > 1:
            op_cell = first + 1 if c < D - 1 and first + 1 in comp else first + D
        for x in comp[1:]:
            if ops and x == op_cell:
                if clue[x] not in (0, 1):
                    raise NotSupportedError(f"6x6 killer operator code {clue[x]} is not supported (only '+')")
            elif clue[x]:
                raise FormatError("a killer clue outside the cage's first cell")
        if len(comp) == 1 and total == 0:
            continue                               # uncaged cell
        r_ = {"type": "cage"}
        if total:
            r_["sum"] = total
        r_["cells"] = [cell_name(*divmod(x, D)) for x in comp]
        rules.append(r_)
    return rules


# ------------------------------------------------------------------------------------------------------------ writing
def _puzzle(x):
    from .api import load
    return load(x)


def to_string(puzzle, form="plain"):
    """engine Puzzle / any accepted input -> plain classic string or sudokuwiki packed string"""
    p = _puzzle(puzzle)
    kind, info = analyse(p)
    if form == "plain":
        D = p.D
        if kind not in ("classic", "classic6") and not (kind is None and _plain_ok(p)):
            raise NotSupportedError(f"plain strings carry only classic sudoku with standard boxes ({info.get('why') or kind})")
        g = info.get("givens") if kind else {p.coords[i][0] * D + p.coords[i][1]: v for i, v in p.givens.items()}
        return "".join(PJ._sym(g[i]) if i in g else "." for i in range(D * D))
    if form == "sudokuwiki":
        if kind is None:
            raise NotSupportedError(f"sudokuwiki.org has no form for this puzzle: {info.get('why')}")
        return ENCODERS[kind](info)
    raise ValueError(f"unknown string form {form!r} (plain / sudokuwiki)")


def _plain_ok(p):
    D = p.D
    if D not in PJ.BOXES or len(p.coords) != D * D or p.relations or p.constraints:
        return False
    bh, bw = PJ.BOXES[D]
    want = {frozenset(range(r * D, r * D + D)) for r in range(D)} | {frozenset(range(c, D * D, D)) for c in range(D)} | \
           {frozenset((br + i) * D + bc + j for i in range(bh) for j in range(bw)) for br in range(0, D, bh) for bc in range(0, D, bw)}
    idx = lambda i: p.coords[i][0] * D + p.coords[i][1]
    have = {frozenset(idx(c) for c in g.cells) for g in p.groups}
    full = (1 << D) - 1
    return have == want and all(g.complete and g.total is None for g in p.groups) and all(m == full for m in p.domains)


def _sets(labels, n):
    out = {}
    for i, ch in enumerate(labels[:n]):
        out.setdefault(ch, set()).add(i)
    return {frozenset(v) for v in out.values()}


def analyse(p):
    """-> (kind or None, info) for the sudokuwiki forms """
    D = p.D
    if D not in (6, 9) or len(p.coords) != D * D or sorted(p.coords) != [(r, c) for r in range(D) for c in range(D)]:
        return None, {"why": f"board D={D} N={len(p.coords)}"}
    if p.relations or getattr(p, "constraints", None):
        return None, {"why": "extra rules (relations / constraints)"}
    to_rc = lambda i: p.coords[i][0] * D + p.coords[i][1]
    givens = {to_rc(i): v for i, v in p.givens.items()}
    if p.domains and any(m != p.full for i, m in enumerate(p.domains) if i not in p.givens and m not in (None, 0)):
        return None, {"why": "restricted domains"}
    cages, houses = [], set()
    for g in p.groups:
        cells = frozenset(to_rc(i) for i in g.cells)
        if g.total is not None or g.kind == "cage":
            cages.append((g.total, sorted(cells)))
        elif g.complete and len(cells) == D:
            houses.add(cells)
        else:
            return None, {"why": f"non-house group {g.kind} ({len(cells)} cells)"}
    rows = {frozenset(range(r * D, r * D + D)) for r in range(D)}
    cols = {frozenset(range(c, D * D, D)) for c in range(D)}
    if not (rows | cols) <= houses:
        return None, {"why": "rows/cols missing"}
    rest = houses - rows - cols
    bh, bw = (3, 3) if D == 9 else (2, 3)
    std = {frozenset((br + i) * D + bc + j for i in range(bh) for j in range(bw)) for br in range(0, D, bh) for bc in range(0, D, bw)}
    transposed = False
    if D == 6 and not std <= rest:
        T = lambda c: (c % 6) * 6 + c // 6
        if std <= {frozenset(map(T, s)) for s in rest}:
            transposed = True
            rest = {frozenset(map(T, s)) for s in rest}
            givens = {T(c): v for c, v in givens.items()}
            cages = [(t, sorted(map(T, cs))) for t, cs in cages]
    if std <= rest:
        extra = rest - std
        boxlab = "".join(str(1 + (i // D // bh) * (D // bw) + (i % D) // bw) for i in range(D * D))
        irregular = False
    else:
        part = [s for s in rest if all(not (s & t) for t in rest if t is not s)]
        cover = set().union(*part) if part else set()
        if len(part) != D or len(cover) != D * D:
            return None, {"why": "no box partition"}
        lab = {}
        for k, s in enumerate(sorted(part, key=min)):
            for c in s:
                lab[c] = str(k + 1)
        boxlab = "".join(lab[i] for i in range(D * D))
        extra = rest - set(part)
        irregular = True
    diags = {frozenset(i * D + i for i in range(D)), frozenset(i * D + D - 1 - i for i in range(D))}
    win4 = {frozenset((wr + i) * 9 + wc + j for i in range(3) for j in range(3)) for wr in (1, 5) for wc in (1, 5)} if D == 9 else set()
    winall = _sets(WINDOKU_COL, 81) if D == 9 else set()
    colour = _sets(COLOUR_COL, 81) if D == 9 else set()
    info = {"boxes": boxlab, "cages": cages, "givens": givens, "D": D, "transposed": transposed}
    if cages:
        if extra:
            return None, dict(info, why="killer + extra regions")
        cov = [c for _, cs in cages for c in cs]
        if len(cov) != len(set(cov)):
            return None, dict(info, why="overlapping cages")
        if D == 6:
            return ("killer6", info) if not irregular else (None, dict(info, why="6x6 killer jigsaw"))
        return ("killer_jigsaw" if irregular else "killer"), info
    if irregular:
        return ("jigsaw", info) if D == 9 and not extra else (None, dict(info, why=f"jigsaw D={D} extra={len(extra)}"))
    if not extra:
        return ("classic" if D == 9 else "classic6"), info
    if D == 9 and extra == diags:
        return "x", info
    if D == 9 and win4 <= extra <= winall:
        return "windoku", info
    if D == 9 and extra == colour:
        return "colour", info
    return None, dict(info, why=f"extra regions {len(extra)}")


def _plain_packed(info, prefix):
    D = info["D"]
    empty = (1 << D) - 1 + 18
    return prefix + "".join(_b36(info["givens"][i], 2) if i in info["givens"] else _b36(empty, 2) for i in range(D * D))


def _colouring(cages, D):
    covered = {c for _, cells in cages for c in cells}
    cages = list(cages) + [(None, [c]) for c in range(D * D) if c not in covered]
    owner = {c: k for k, (_, cells) in enumerate(cages) for c in cells}
    adj = {k: set() for k in range(len(cages))}
    for c, k in owner.items():
        r, q = divmod(c, D)
        for rr, qq in ((r + 1, q), (r, q + 1), (r - 1, q), (r, q - 1)):
            if 0 <= rr < D and 0 <= qq < D and owner[rr * D + qq] != k:
                adj[k].add(owner[rr * D + qq])
    col = {}
    for k in sorted(adj, key=lambda k: -len(adj[k])):
        col[k] = next(x for x in range(1, 9) if all(col.get(j) != x for j in adj[k]))
    clue = [0] * (D * D)
    for total, cells in cages:
        clue[min(cells)] = total or 0
    return [col[owner[c]] for c in range(D * D)], clue


def _enc_jigsaw(info):
    s = "J9B"
    for i in range(81):
        n = info["givens"][i] if i in info["givens"] else 511 + 18
        s += _b36(((int(info["boxes"][i]) - 1) << 10) + n, 3)
    return s


def _enc_killer(info):
    col, clue = _colouring(info["cages"], 9)
    g = info["givens"]
    return "L9B" + "".join(_b36((((col[i] - 1) << 6) + clue[i] << 10) + (g[i] + 9 if i in g else 529), 4) for i in range(81))


def _enc_killer_jigsaw(info):
    col, clue = _colouring(info["cages"], 9)
    s = "M9B"
    for i in range(81):
        p = (((int(info["boxes"][i]) - 1) << 3) + col[i] - 1 << 6) + clue[i]
        s += _b36((p << 10) + (info["givens"][i] + 9 if i in info["givens"] else 529), 5)
    return s


def _enc_killer6(info):
    col, clue = _colouring(info["cages"], 6)
    store = [0] * 36
    s = "L6C"
    for i in range(36):
        j, q = divmod(i, 6)
        p = (col[i] - 1) << 11
        if clue[i] > 0:
            p += clue[i]
            if q < 5 and col[i] == col[i + 1]:
                store[i + 1] = 1
            elif j < 5 and col[i] == col[i + 6]:
                store[i + 6] = 1
        elif store[i]:
            p += store[i]
        s += _b36((p << 7) + (info["givens"][i] + 6 if i in info["givens"] else 75), 4)
    return s


ENCODERS = {"classic": lambda i: _plain_packed(i, "S9B"), "classic6": lambda i: _plain_packed(i, "S6B"),
            "x": lambda i: _plain_packed(i, "X9B"), "windoku": lambda i: _plain_packed(i, "W9B"),
            "colour": lambda i: _plain_packed(i, "C9B"), "jigsaw": _enc_jigsaw, "killer": _enc_killer,
            "killer_jigsaw": _enc_killer_jigsaw, "killer6": _enc_killer6}


# --------------------------------------------------------------------------------------------------------------- ipuz
IPUZ_NS = "io.github.silly-puppyy.pencilmark"


def to_ipuz(puzzle):
    """sudoku-puzzle (or any accepted input) -> ipuz 2 dict, for classic / Latin square / diagonal / windoku / jigsaw /
    killer and their combinations; refuses everything else with NotSupportedError."""
    from .api import to_export
    doc = puzzle if isinstance(puzzle, dict) and puzzle.get("format") == FORMAT and puzzle.get("format_version") == FORMAT_VERSION \
        else to_export(puzzle)
    from .exchange import validate
    B = validate(doc)
    D = doc["digits"]
    R, C = doc["grid"]["rows"], doc["grid"]["cols"]
    if not (R == C == D) or None in doc["givens"]:
        raise NotSupportedError("ipuz sudoku needs one gap-free D x D grid")
    rules = doc["rules"]
    subs = [r for r in rules if r["type"] == "subgrid"]
    if len(subs) != 1 or subs[0].get("origin") != "r1c1":
        raise NotSupportedError("ipuz sudoku needs exactly one subgrid covering the board")
    sub = subs[0]
    kinds = ["http://ipuz.org/sudoku#1"]
    zones, cages = [], []
    boxes = [r for r in rules if r["type"] == "box"]
    rc = lambda name: [parse_cell(name)[1] + 1, parse_cell(name)[0] + 1]
    diag_main = [cell_name(i, i) for i in range(D)]
    diag_anti = [cell_name(i, D - 1 - i) for i in range(D)]
    diags = []
    for r in rules:
        t = r["type"]
        if t in ("subgrid", "box"):
            continue
        if t == "region" and r["kind"] == "diagonal" and r["cells"] in (diag_main, diag_anti, diag_main[::-1], diag_anti[::-1]):
            diags.append(r)
            zones.append({"cells": [rc(c) for c in r["cells"]], "style": {"highlight": True}})
        elif t == "region" and r["kind"] == "window":
            co = [parse_cell(c) for c in r["cells"]]
            r0, c0 = min(co); r1, c1 = max(co)
            if (r1 - r0 + 1) * (c1 - c0 + 1) != len(co):
                raise NotSupportedError("a window that is not a rectangle")
            zones.append({"rect": [c0 + 1, r0 + 1, c1 + 1, r1 + 1], "style": {"highlight": True}})
        elif t == "cage" and "sum" in r:
            cages.append({"cells": [rc(c) for c in r["cells"]], "value": r["sum"]})
        else:
            raise NotSupportedError(f"ipuz cannot express a {t} rule" + (f" ({r.get('kind')})" if r.get("kind") else ""))
    if len(diags) not in (0, 2):
        raise NotSupportedError("ipuz diagonal sudoku needs both main diagonals")
    if boxes:
        if "box" in sub:
            raise NotSupportedError("extra box rules on a board with standard boxes")
        kinds.append("http://ipuz.org/sudoku/jigsawsudoku#1")
        zones = [{"cells": [rc(c) for c in b["cells"]]} for b in boxes] + zones
    elif "box" not in sub:
        kinds.append("http://ipuz.org/sudoku/latinsquare#1")
    elif list(sub["box"]) != list(PJ.BOXES.get(D, (0, 0))):
        raise NotSupportedError("ipuz infers box shapes; only the standard shape exports")
    if diags:
        kinds.append("http://ipuz.org/sudoku/diagonalsudoku#1")
    if any(r["type"] == "region" and r["kind"] == "window" for r in rules):
        kinds.append("http://ipuz.org/sudoku/hypersudoku#1")
    if cages:
        kinds.append("http://ipuz.org/sudoku/killersudoku#1")
    rows = lambda flat: [[v for v in flat[r * C:(r + 1) * C]] for r in range(R)]
    out = {"version": "http://ipuz.org/v2", "kind": kinds}
    m = doc.get("meta") or {}
    for k, ik in (("title", "title"), ("author", "author"), ("url", "url"), ("id", "uniqueid")):
        if m.get(k):
            out[ik] = m[k]
    if m.get("date") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(m["date"])):
        y, mo, da = m["date"].split("-")
        out["date"] = f"{mo}/{da}/{y}"
    out["boxes"] = "box" in sub
    out["puzzle"] = rows(doc["givens"])
    if doc.get("solution"):
        out["solution"] = rows(doc["solution"])
    if zones:
        out["zones"] = zones
    if cages:
        out["cages"] = cages
        out["showoperators"] = False
        out["cageborder"] = "dashed"
    out[f"{IPUZ_NS}:puzzle"] = doc
    out["volatile"] = {IPUZ_NS: "puzzle,solution,zones,cages"}
    return out
