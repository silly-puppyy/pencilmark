"""Interop strings and ipuz export (docs/INTEROP.md).

    from_string(s) -> sudoku-puzzle dict        plain classic strings (also as text grids with | - + separators, or with a
                                                trailing comment), pencil-mark grids, 729-character candidate strings, HoDoKu
                                                library lines, and
                                                sudokuwiki.org packed strings (S9B, S6B, X9B, W9B, C9B, J9B, L9B, M9B, L6C)
    to_string(puzzle, "plain" | "grid" | "sudokuwiki")   the reverse (refuses what the target cannot express)
    to_ipuz(puzzle) -> dict                     ipuz 2 for classic / Latin square / diagonal / windoku / jigsaw / killer
    from_ipuz(ipuz) -> sudoku-puzzle dict       the reverse (boxes, zones, cages); a to_ipuz file returns its embedded puzzle

The sudokuwiki encodings are checked against sudokuwiki.org's solver; the decoder reads exactly what the encoder writes
and refuses anything else (placed digits in plain forms, candidate masks, 6x6 killer operators other than '+').
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
    d.update({"board": {"rows": D, "cols": D}, "digits": D, "givens": givens, "rules": rules})
    return d


def _box_grid(D):
    bh, bw = PJ.BOXES[D]
    return {"type": "box_grid", "origin": "r1c1", "box": [bh, bw]}


# ------------------------------------------------------------------------------------------------------------ reading
_PACKED = re.compile(r"([SXWCJLM])(\d+)([BC])([0-9a-zA-Z]+)")


_SEPARATOR_LINE = re.compile(r"[\s|*]*[\-+=][\s\-+=|*]*")  # needs a - + or =: "*********" is a row of empties
_COMMENT = re.compile(r"\s*[#;].*$")


def from_string(s, symbols=None):
    """plain classic string, text grid, pencil-mark grid, 729-character candidate string or sudokuwiki packed string ->
    sudoku-puzzle dict (docs/INTEROP.md)"""
    s = s or ""
    t = re.sub(r"\s+", "", s)
    m = _PACKED.fullmatch(t)
    if m and len(m.group(4)) == WIDTH[m.group(1)] * int(m.group(2)) ** 2:
        return _from_sudokuwiki(m.group(1), int(m.group(2)), m.group(3), m.group(4).lower())
    if symbols is None and s.lstrip().startswith(":") and s.count(":") >= 4:
        return _from_hodoku_library(s.strip())
    if symbols is None:
        lines = [_COMMENT.sub("", ln) for ln in s.splitlines()]
        rows = [ln for ln in lines if ln.strip() and not _SEPARATOR_LINE.fullmatch(ln)]
        tokens = [tok for ln in rows for tok in ln.replace("|", " ").split()]
        if len(tokens) in PJ.SIZES and any(len(tok) > 1 for tok in tokens) and all(tok.isalnum() for tok in tokens):
            return _from_pencilmarks(tokens)
        body = "".join(re.sub(r"[\s|]+", "", ln) for ln in rows)
        if (
            len(body) not in PJ.SIZES and len(body) != 729
        ):  # a row of '-' empties looks like a separator: keep bare dash rows
            rows = [
                ln for ln in lines if ln.strip() and not (_SEPARATOR_LINE.fullmatch(ln) and re.search(r"[+=|*]", ln))
            ]
            body = "".join(re.sub(r"[\s|]+", "", ln) for ln in rows)
        if len(body) == 729 and re.fullmatch(r"[0-9.]+", body):
            return _from_candidate_string(body)
        if len(body) in PJ.SIZES:
            return _from_plain(body.replace("*", "."))
        first = s.split()[0] if s.split() else ""
        if len(first) in PJ.SIZES and len(first) >= 16 and len(s.splitlines()) == 1:  # "<81 chars> rating / comment"
            return _from_plain(first)
    return _from_plain(t, symbols)


def _from_hodoku_library(line):
    """HoDoKu library line ':<technique code>:<letter>:<puzzle>:<removed candidates>:...': the puzzle (81 characters, '.' or
    '0' empty) and its removed candidates (tokens 'drc': digit d is not a candidate of row r, column c); the remaining
    fields describe the step the line was collected for and are ignored"""
    f = line.split(":")
    d = _from_plain(re.sub(r"\s+", "", f[3]))
    D = d["digits"]
    removed = {}
    for tok in f[4].split() if len(f) > 4 else []:
        if not re.fullmatch(r"[1-9]{3}", tok) or D != 9:
            raise FormatError(f"HoDoKu library line: removed candidate {tok!r} is not 'digit row column'")
        removed.setdefault(cell_name(int(tok[1]) - 1, int(tok[2]) - 1), set()).add(int(tok[0]))
    cands = {
        c: [v for v in range(1, D + 1) if v not in rm]
        for c, rm in removed.items()
        if not d["givens"][parse_cell(c)[0] * D + parse_cell(c)[1]]
    }
    if cands:
        d["candidates"] = dict(sorted(cands.items(), key=lambda kv: parse_cell(kv[0])))
    return d


def _from_pencilmarks(tokens):
    """D*D tokens, one per cell in reading order: one digit = a placed digit (given), several = that cell's candidates"""
    D = PJ.SIZES[len(tokens)]
    givens, cands = [], {}
    for i, tok in enumerate(tokens):
        vals = sorted({PJ.SYMBOLS.find(ch.upper()) + 1 for ch in tok})
        if not all(1 <= v <= D for v in vals) or len(vals) != len(tok):
            raise FormatError(f"pencil-mark grid: cell {i + 1} ({tok!r}) is not a set of digits 1..{D}")
        if len(vals) == 1:
            givens.append(vals[0])
        else:
            givens.append(0)
            if len(vals) < D:
                cands[cell_name(i // D, i % D)] = vals
    d = _doc(D, givens, [_box_grid(D)])
    if cands:
        d["candidates"] = cands
    return d


def _from_candidate_string(body):
    """729 characters: 9 per cell, position k holds digit k+1 when it is a candidate ('.' or '0' otherwise); a cell with
    one candidate is a given"""
    givens, cands = [], {}
    for i in range(81):
        chunk = body[9 * i : 9 * i + 9]
        vals = [k + 1 for k, ch in enumerate(chunk) if ch not in ".0"]
        if any(ch not in ".0" and ch != str(k + 1) for k, ch in enumerate(chunk)):
            raise FormatError(f"candidate string: cell {i + 1} ({chunk!r}) has a digit out of place")
        if not vals:
            raise FormatError(f"candidate string: cell {i + 1} has no candidate")
        if len(vals) == 1:
            givens.append(vals[0])
        else:
            givens.append(0)
            if len(vals) < 9:
                cands[cell_name(i // 9, i % 9)] = vals
    d = _doc(9, givens, [_box_grid(9)])
    if cands:
        d["candidates"] = cands
    return d


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
    return _doc(D, giv, [_box_grid(D)])


def _from_sudokuwiki(kind, D, ver, body):
    if (kind, D, ver) not in {
        ("S", 9, "B"),
        ("S", 6, "B"),
        ("X", 9, "B"),
        ("W", 9, "B"),
        ("C", 9, "B"),
        ("J", 9, "B"),
        ("L", 9, "B"),
        ("M", 9, "B"),
        ("L", 6, "C"),
    }:
        raise NotSupportedError(f"sudokuwiki string {kind}{D}{ver} is not supported")
    w = WIDTH[kind]
    vals = [int(body[i * w : (i + 1) * w], 36) for i in range(D * D)]
    full = (1 << D) - 1
    killer = kind in ("L", "M")
    empty = full + 18 if not (kind == "L" and D == 6) else 75  # the encoder's empty-cell values (S6B 81, L6C 75)
    givens, box_lab, col, clue = [], [], [], []
    for v in vals:
        if kind in ("S", "X", "W", "C"):
            n = v
        elif kind == "J":
            n, box_lab_ = v & 1023, (v >> 10) + 1
            box_lab.append(box_lab_)
        elif kind == "L" and D == 9:
            n, clue_, col_ = v & 1023, (v >> 10) & 63, (v >> 16) + 1
            clue.append(clue_)
            col.append(col_)
        elif kind == "M":
            n, clue_, col_, box_ = v & 1023, (v >> 10) & 63, ((v >> 16) & 7) + 1, (v >> 19) + 1
            clue.append(clue_)
            col.append(col_)
            box_lab.append(box_)
        else:  # L6C
            n, clue_, col_ = v & 127, (v >> 7) & 2047, (v >> 18) + 1
            clue.append(clue_)
            col.append(col_)
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
        rules.append({"type": "grid", "origin": "r1c1"})
        groups = {}
        for i, lab in enumerate(box_lab):
            groups.setdefault(lab, []).append(i)
        if sorted(len(g) for g in groups.values()) != [D] * D:
            raise FormatError("jigsaw box labels do not make D boxes of D cells")
        for lab, cells in sorted(groups.items(), key=lambda kv: min(kv[1])):
            rules.append({"type": "box", "cells": [cell_name(*divmod(c, D)) for c in cells]})
    else:
        rules.append(_box_grid(D))
    nm = lambda i: cell_name(*divmod(i, D))
    if kind == "X":
        rules += [
            {"type": "region", "kind": "diagonal", "cells": [nm(i * D + i) for i in range(D)]},
            {"type": "region", "kind": "diagonal", "cells": [nm(i * D + D - 1 - i) for i in range(D)]},
        ]
    elif kind == "W":
        for wr in (1, 5):
            for wc in (1, 5):
                rules.append(
                    {
                        "type": "region",
                        "kind": "window",
                        "cells": [nm((wr + a) * 9 + wc + b) for a in range(3) for b in range(3)],
                    }
                )
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
                    owner[y] = len(comps)
                    comp.append(y)
                    st.append(y)
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
            continue  # uncaged cell
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
            raise NotSupportedError(
                f"plain strings carry only classic sudoku with standard boxes ({info.get('why') or kind})"
            )
        g = info.get("givens") if kind else {p.coords[i][0] * D + p.coords[i][1]: v for i, v in p.givens.items()}
        return "".join(PJ._sym(g[i]) if i in g else "." for i in range(D * D))
    if form == "grid":  # text grid: rows on lines, boxes separated by | and ------+------ lines
        flat = to_string(p, "plain")
        D = p.D
        bh, bw = PJ.BOXES[D]
        rows = []
        for r in range(D):
            cells = flat[r * D : (r + 1) * D]
            rows.append(" | ".join(" ".join(cells[c : c + bw]) for c in range(0, D, bw)))
            if (r + 1) % bh == 0 and r + 1 < D:
                rows.append("-+-".join("-" * (2 * bw - 1) for _ in range(0, D, bw)))
        return "\n".join(rows)
    if form == "sudokuwiki":
        if kind is None:
            raise NotSupportedError(f"sudokuwiki.org has no form for this puzzle: {info.get('why')}")
        return ENCODERS[kind](info)
    raise ValueError(f"unknown string form {form!r} (plain / grid / sudokuwiki)")


def _plain_ok(p):
    D = p.D
    if D not in PJ.BOXES or len(p.coords) != D * D or p.relations or p.constraints:
        return False
    bh, bw = PJ.BOXES[D]
    want = (
        {frozenset(range(r * D, r * D + D)) for r in range(D)}
        | {frozenset(range(c, D * D, D)) for c in range(D)}
        | {
            frozenset((br + i) * D + bc + j for i in range(bh) for j in range(bw))
            for br in range(0, D, bh)
            for bc in range(0, D, bw)
        }
    )
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
    """-> (kind or None, info) for the sudokuwiki forms"""
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
    std = {
        frozenset((br + i) * D + bc + j for i in range(bh) for j in range(bw))
        for br in range(0, D, bh)
        for bc in range(0, D, bw)
    }
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
    win4 = (
        {frozenset((wr + i) * 9 + wc + j for i in range(3) for j in range(3)) for wr in (1, 5) for wc in (1, 5)}
        if D == 9
        else set()
    )
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
    return "L9B" + "".join(
        _b36((((col[i] - 1) << 6) + clue[i] << 10) + (g[i] + 9 if i in g else 529), 4) for i in range(81)
    )


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


ENCODERS = {
    "classic": lambda i: _plain_packed(i, "S9B"),
    "classic6": lambda i: _plain_packed(i, "S6B"),
    "x": lambda i: _plain_packed(i, "X9B"),
    "windoku": lambda i: _plain_packed(i, "W9B"),
    "colour": lambda i: _plain_packed(i, "C9B"),
    "jigsaw": _enc_jigsaw,
    "killer": _enc_killer,
    "killer_jigsaw": _enc_killer_jigsaw,
    "killer6": _enc_killer6,
}


# --------------------------------------------------------------------------------------------------------------- ipuz
IPUZ_NS = "io.github.silly-puppyy.pencilmark"


def to_ipuz(puzzle):
    """sudoku-puzzle (or any accepted input) -> ipuz 2 dict, for classic / Latin square / diagonal / windoku / jigsaw /
    killer and their combinations; refuses everything else with NotSupportedError."""
    from .api import to_export

    doc = (
        puzzle
        if isinstance(puzzle, dict)
        and puzzle.get("format") == FORMAT
        and puzzle.get("format_version") == FORMAT_VERSION
        else to_export(puzzle)
    )
    from .exchange import validate

    B = validate(doc)
    D = doc["digits"]
    R, C = doc["board"]["rows"], doc["board"]["cols"]
    if not (R == C == D) or None in doc["givens"]:
        raise NotSupportedError("ipuz sudoku needs one gap-free D x D grid")
    if doc.get("candidates"):
        raise NotSupportedError("ipuz sudoku cannot carry given candidates (Sukaku)")
    rules = doc["rules"]
    grids = [r for r in rules if r["type"] in ("grid", "box_grid")]
    if len(grids) != 1 or any(r["type"] in ("row", "column") for r in rules):
        raise NotSupportedError("ipuz sudoku needs one grid with plain rows and columns")
    std = PJ.BOXES.get(D)
    standard = grids[0]["type"] == "box_grid" and std and list(grids[0]["box"]) == list(std)
    if grids[0]["type"] == "box_grid" and not standard:
        raise NotSupportedError("ipuz infers box shapes; only a box_grid of the standard shape exports")
    kinds = ["http://ipuz.org/sudoku#1"]
    zones, cages = [], []
    boxes = [r for r in rules if r["type"] == "box"]
    rc = lambda name: [parse_cell(name)[1] + 1, parse_cell(name)[0] + 1]
    diag_main = [cell_name(i, i) for i in range(D)]
    diag_anti = [cell_name(i, D - 1 - i) for i in range(D)]
    diags = []
    for r in rules:
        t = r["type"]
        if t in ("grid", "box_grid", "box"):
            continue
        if (
            t == "region"
            and r["kind"] == "diagonal"
            and r["cells"] in (diag_main, diag_anti, diag_main[::-1], diag_anti[::-1])
        ):
            diags.append(r)
            zones.append({"cells": [rc(c) for c in r["cells"]], "style": {"highlight": True}})
        elif t == "region" and r["kind"] == "window":
            co = [parse_cell(c) for c in r["cells"]]
            r0, c0 = min(co)
            r1, c1 = max(co)
            if (r1 - r0 + 1) * (c1 - c0 + 1) != len(co):
                raise NotSupportedError("a window that is not a rectangle")
            zones.append({"rect": [c0 + 1, r0 + 1, c1 + 1, r1 + 1], "style": {"highlight": True}})
        elif t == "cage" and "sum" in r:
            cages.append({"cells": [rc(c) for c in r["cells"]], "value": r["sum"]})
        else:
            raise NotSupportedError(
                f"ipuz cannot express a {t} rule" + (f" ({r.get('kind')})" if r.get("kind") else "")
            )
    if len(diags) not in (0, 2):
        raise NotSupportedError("ipuz diagonal sudoku needs both main diagonals")
    if boxes:
        if standard:
            raise NotSupportedError("extra box rules on a board with standard boxes")
        kinds.append("http://ipuz.org/sudoku/jigsawsudoku#1")
        zones = [{"cells": [rc(c) for c in b["cells"]]} for b in boxes] + zones
    elif not standard:
        kinds.append("http://ipuz.org/sudoku/latinsquare#1")
    if diags:
        kinds.append("http://ipuz.org/sudoku/diagonalsudoku#1")
    if any(r["type"] == "region" and r["kind"] == "window" for r in rules):
        kinds.append("http://ipuz.org/sudoku/hypersudoku#1")
    if cages:
        kinds.append("http://ipuz.org/sudoku/killersudoku#1")
    rows = lambda flat: [[v for v in flat[r * C : (r + 1) * C]] for r in range(R)]
    out = {"version": "http://ipuz.org/v2", "kind": kinds}
    m = doc.get("meta") or {}
    for k, ik in (("title", "title"), ("author", "author"), ("url", "url"), ("id", "uniqueid")):
        if m.get(k):
            out[ik] = m[k]
    if m.get("date") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(m["date"])):
        y, mo, da = m["date"].split("-")
        out["date"] = f"{mo}/{da}/{y}"
    out["boxes"] = bool(standard)
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


def from_ipuz(ipuz):
    """ipuz sudoku (dict or JSON text) -> sudoku-puzzle dict. Reads `puzzle`, `solution`, `boxes`, `zones` (jigsaw boxes,
    diagonals, windows, other regions) and `cages`; a file written by to_ipuz gives back its embedded puzzle unless the
    grid was edited. Refuses kinds other than sudoku and cells it cannot read."""
    import json

    d = json.loads(ipuz) if isinstance(ipuz, str) else ipuz
    kinds = d.get("kind") or []
    if not str(d.get("version", "")).startswith("http://ipuz.org/v") or not any("ipuz.org/sudoku" in k for k in kinds):
        raise FormatError("not an ipuz sudoku (version http://ipuz.org/v1 or v2, kind http://ipuz.org/sudoku...)")
    empty, block = d.get("empty", 0), d.get("block", "#")

    def value(x):
        if isinstance(x, dict):
            x = x.get("cell", x.get("value", 0))
        if x is None or x == block:
            raise NotSupportedError("ipuz sudoku with omitted or block cells")
        if x == empty or str(x) == str(empty) or x in ("", 0, "0"):
            return 0
        try:
            return int(x)
        except (TypeError, ValueError):
            raise FormatError(f"ipuz cell value {x!r} is not a digit")

    grid = d.get("puzzle")
    if not isinstance(grid, list) or not grid:
        raise FormatError("ipuz sudoku without a puzzle grid")
    D = len(grid)
    if any(not isinstance(row, list) or len(row) != D for row in grid):
        raise NotSupportedError("ipuz sudoku needs a square D x D puzzle grid")
    givens = [value(x) for row in grid for x in row]
    emb = d.get(f"{IPUZ_NS}:puzzle")
    if isinstance(emb, dict) and emb.get("givens") == givens:
        return emb
    name = lambda cr: cell_name(int(cr[1]) - 1, int(cr[0]) - 1)  # ipuz coordinates are [col, row], 1-based
    rules, boxes = [], []
    diag_main = [cell_name(i, i) for i in range(D)]
    diag_anti = [cell_name(i, D - 1 - i) for i in range(D)]
    jigsaw = any("jigsawsudoku" in k for k in kinds)
    for z in d.get("zones") or []:
        if "rect" in z:
            c0, r0, c1, r1 = z["rect"]
            cells = [cell_name(r, c) for r in range(r0 - 1, r1) for c in range(c0 - 1, c1)]
            kind = "window"
        else:
            cells = [name(cr) for cr in z.get("cells") or []]
            srt = sorted(cells, key=lambda c: parse_cell(c))
            kind = "diagonal" if srt in (diag_main, sorted(diag_anti, key=lambda c: parse_cell(c))) else "region"
            if kind == "diagonal":
                cells = diag_main if srt == diag_main else diag_anti
        if not cells:
            raise FormatError("ipuz zone without cells")
        if jigsaw and kind == "region" and len(cells) == D:
            boxes.append(sorted(cells, key=lambda c: parse_cell(c)))
        else:
            rules.append(
                {
                    "type": "region",
                    "kind": kind,
                    "cells": sorted(cells, key=lambda c: parse_cell(c)) if kind != "diagonal" else cells,
                }
            )
    for cg in d.get("cages") or []:
        cells = sorted((name(cr) for cr in cg.get("cells") or []), key=lambda c: parse_cell(c))
        if "value" not in cg or not cells:
            raise NotSupportedError("ipuz cage without a sum")
        rules.append({"type": "cage", "cells": cells, "sum": int(cg["value"])})
    if boxes:
        houses = [{"type": "grid", "origin": "r1c1"}] + [{"type": "box", "cells": b} for b in boxes]
    elif d.get("boxes", True) and D in PJ.BOXES:
        houses = [_box_grid(D)]
    else:
        houses = [{"type": "grid", "origin": "r1c1"}]
    meta = {}
    for ik, k in (("title", "title"), ("author", "author"), ("url", "url"), ("uniqueid", "id")):
        if d.get(ik):
            meta[k] = d[ik]
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", str(d.get("date", ""))):
        mo, da, y = d["date"].split("/")
        meta["date"] = f"{y}-{mo}-{da}"
    doc = _doc(D, givens, houses + rules, meta or None)
    if isinstance(d.get("solution"), list) and len(d["solution"]) == D:
        doc["solution"] = [value(x) for row in d["solution"] for x in row]
    from .exchange import validate

    validate(doc)
    return doc
