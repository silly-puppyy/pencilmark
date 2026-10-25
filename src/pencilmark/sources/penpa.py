"""penpa-edit / penpa+ links -> raw structure -> puzzle JSON (sudoku-relevant subset, exact or refused).

Format (from the penpa-edit source, github.com/swaroopg92/penpa-edit, docs/js/general.js load() / class_p.js):
  URL  .../penpa-edit/?m=solve|edit&p=<P>[&a=<A>][&l=...]   (also '#m=...&p=...')
  P    base64 of a RAW deflate stream (zlib wbits -15) of UTF-8 text; then the COMPRESS_SUB substitutions are undone
       in reverse order (zQ -> "pu_q", zN -> "number", ..., zO -> null, and finally zZ -> z).
  text lines  0 header 'gridtype,nx,ny,size,theta,reflect0,reflect1,canvasx,canvasy,center_n,center_n0,
                 sudoku0..3,Title: ..,Author: ..,source,rules,border,multisolution[,bg image]'  (%2C = ',', %2D = newline)
              1 space [top, bottom, left, right] (margin rows / columns outside the board)
              2 mode   3 pu_q (problem layer)   4 pu_a (answer layer, edit links)   5 centerlist (delta-coded cells)
              7/8 answer-check settings   10 version   14/15 custom colours   17 genre tags
  A    deflated solution: JSON list per element class; index 4 = ["cell,digit", ...] for number answers
       (with multisolution, a JSON list of such solutions).
Square-grid point indices (nx0 = nx + 4, ny0 = ny + 4, N = nx0 * ny0; cell (i, j) = column i, row j of the padded
grid): cells k = j * nx0 + i in [0, N); vertices N + k (bottom-right corner of cell k); edge midpoints [2N, 4N);
cell corners 4N + 4k + {0 TL, 1 TR, 2 BL, 3 BR}; compass points [8N, 12N).

Mapped to puzzle JSON: the board (centerlist; must be a full D x D square), given digits (normal-size numbers in board
cells), regions from thick borders (lineE styles 2 / 21; the board is flood-filled across them -- D regions of D
cells), killer cages (killercages + their corner sums from numberS / small numbers), thermometers (the thermo tool,
bulb first), arrows (the arrow tool starting in a cell that carries a circle symbol), drawn main diagonals when the
rules text mentions diagonals. Everything else -- generic lines, shading, other symbols, edge / outside / vertex
numbers, pencil marks, free lines, cage outlines without a killer-cage grouping, rules-text keywords for variants
that are not drawn with a supported tool -- raises UnsupportedPuzzle listing the elements. Non-square grid types
(hex, tri, iso, ...) and pre-v2 links are refused.

    decode(link_or_payload) -> dict      to_puzzle(link_or_payload_or_decoded) -> puzzle JSON dict
"""
from __future__ import annotations

import base64
import json
import re
import urllib.parse
import zlib
from collections import Counter, defaultdict

from ._common import DecodeError, UnsupportedPuzzle, to_puzzle_json

COMPRESS_SUB = [
    ["z", "zZ"], ['"qa"', "z9"], ['"pu_q"', "zQ"], ['"pu_a"', "zA"], ['"grid"', "zG"], ['"edit_mode"', "zM"],
    ['"surface"', "zS"], ['"line"', "zL"], ['"lineE"', "zE"], ['"wall"', "zW"], ['"cage"', "zC"], ['"number"', "zN"],
    ['"symbol"', "zY"], ['"special"', "zP"], ['"board"', "zB"], ['"command_redo"', "zR"], ['"command_undo"', "zU"],
    ['"command_replay"', "z8"], ['"numberS"', "z1"], ['"freeline"', "zF"], ['"freelineE"', "z2"], ['"thermo"', "zT"],
    ['"arrows"', "z3"], ['"direction"', "zD"], ['"squareframe"', "z0"], ['"polygon"', "z5"], ['"deletelineE"', "z4"],
    ['"killercages"', "z6"], ['"nobulbthermo"', "z7"], ['"__a"', "z_"], ["null", "zO"]]
HEADER = ["gridtype", "nx", "ny", "size", "theta", "reflect0", "reflect1", "canvasx", "canvasy", "center_n",
          "center_n0", "sudoku0", "sudoku1", "sudoku2", "sudoku3", "title", "author", "source", "rules", "border",
          "multisolution", "bg_image"]
HOST = re.compile(r"penpa", re.I)
THICK = {2, 21}                    # bold black border styles (set_line_style: 2 = width 3, 21 = width 5)
COSMETIC_EDGE = {0, 1, 11, 80}     # transparent / grid / grid dash / grid-like edge lines
HISTORY = ("command_redo", "command_undo", "command_replay")
# rules-text words for variant rules this mapper cannot take from a supported drawing tool
TEXT_RULES = [("anti-knight", r"anti[- ]?knight|chess knight|knight'?s? move|\bknights?\b"),
              ("anti-king", r"anti[- ]?king|chess king|king'?s? move|\bkings?\b"),
              ("toroidal / wrap-around", r"toro|wrap|opposite edges"), ("mountain", r"mountain"), ("doubler", r"doubler"),
              ("remote / pointing clues", r"\bremote\b|points? to"), ("either / both clue", r"either both|both digits"),
              ("nonconsecutive", r"non[- ]?consecutive"), ("disjoint groups", r"disjoint"),
              ("extra regions", r"windoku|hyper[- ]?sudoku|extra regions?|shaded regions?"),
              ("sandwich", r"sandwich"), ("little killer", r"little killer"), ("x-sum", r"x[- ]?sums?"),
              ("skyscraper", r"skyscraper"), ("kropki", r"kropki|white dot|black dot"), ("xv", r"\bxv\b|\bx and v\b"),
              ("odd / even", r"\b(?:odd|even) (?:digits?|numbers?|cells?|squares?|circles?)\b|\bgr[ae]y (?:circles?|squares?)"),
              ("renban", r"renban"), ("whisper", r"whisper"), ("palindrome", r"palindrom"), ("between line", r"between"),
              ("region sum", r"region[- ]sum"), ("entropic", r"entrop"), ("parity line", r"parity"),
              ("zipper", r"zipper"), ("quadruple", r"quadruple"), ("chaos construction", r"chaos"),
              ("slow thermo", r"slow[- ]?thermo|never decrease|may repeat on (?:a |the )?thermo"),
              ("fog of war", r"\bfog\b"), ("clone", r"\bclones?\b"), ("German / Dutch lines", r"german|dutch"),
              ("minimum / maximum", r"\bminim|\bmaxim"), ("inequality", r"inequalit|greater than|less than"),
              ("difference / ratio", r"\bdifference\b|\bratio\b"), ("indexing", r"index"), ("sum lines", r"\blines?\b.{0,40}\bsum\b"),
              ("cage digits may repeat", r"cages?\b[^.]{0,80}\bmay repeat|\brepeat\b[^.]{0,60}\bcages?"),
              ("average", r"\baverage"), ("product", r"\bproduct"), ("rounding", r"\bround(?:ed|ing)?\b(?! the)"),
              ("all or nothing", r"all[- ]or[- ]nothing"), ("multiple", r"\bmultiples? of\b")]
KILLER_TEXT = re.compile(r"\bsum|\btotal|\bkiller|\badd (?:up )?to\b")


def _b64inflate(s):
    s = urllib.parse.unquote(s) if "%" in s else s
    s = s.strip().replace(" ", "+")
    try:
        raw = base64.b64decode(s + "=" * (-len(s) % 4))
        return zlib.decompress(raw, -15).decode("utf-8")
    except Exception as e:  # noqa: BLE001
        raise DecodeError(f"penpa data is not base64 raw-deflate ({type(e).__name__}: {e})") from e


def is_penpa_url(s):
    return isinstance(s, str) and "://" in s and bool(HOST.search(urllib.parse.urlsplit(s.strip()).path + urllib.parse.urlsplit(s.strip()).netloc)) \
        and re.search(r"[?#&]p=", s) is not None


def params(link):
    """'...?m=solve&p=..&a=..' or '#m=..' -> {key: value} (values untouched, like penpa's own split on '&' / '=')."""
    s = link.strip()
    if "://" in s:
        s = re.split(r"[?#]", s, 1)[1] if re.search(r"[?#]", s) else ""
    out = {}
    for item in re.split(r"[&?#]", s):
        if "=" in item:
            k, v = item.split("=", 1)
            out.setdefault(k, v)
    return out


def _unsub(text):
    for a, b in reversed(COMPRESS_SUB):
        text = text.replace(b, a)
    return text


def _field(s):
    return (s or "").replace("%2C", ",").replace("%2D", "\n").replace("%2E", "&").replace("%2F", "=")


def decode(link_or_payload):
    """penpa link (or the bare p= value) -> {"format": "penpa", "mode": "solve"|"edit", "gridtype", "nx", "ny",
    "space", "header", "title", "author", "rules", "source_link", "multisolution", "pu_q", "pu_a", "centerlist" (cell
    indices), "version", "tags", "solution_raw"}."""
    if isinstance(link_or_payload, dict) and link_or_payload.get("format") == "penpa":
        return link_or_payload
    if not isinstance(link_or_payload, str) or not link_or_payload.strip():
        raise DecodeError("empty penpa link")
    s = link_or_payload.strip()
    prm = params(s) if ("://" in s or "p=" in s[:12]) else {"p": s}
    if not prm.get("p"):
        raise DecodeError("penpa link without a p= parameter")
    if prm["p"].startswith("http"):
        raise DecodeError("penpa link imports another URL (puzz.link); not decodable offline")
    text = _unsub(_b64inflate(prm["p"]))
    lines = text.split("\n")
    if lines and lines[0][:1].isdigit():
        raise DecodeError("pre-v2 penpa link format (loadver1) is not supported")
    h = lines[0].split(",")
    head = {k: (h[i] if i < len(h) else "") for i, k in enumerate(HEADER)}

    def js(i, default=None):
        if i < len(lines) and lines[i].strip() not in ("", "x", '"x"', "undefined"):
            try:
                return json.loads(lines[i])
            except ValueError:
                return default
        return default

    cl = js(5, []) or []
    if cl and cl[0] is None:
        cl = []
    for i in range(1, len(cl)):
        cl[i] = cl[i - 1] + cl[i]
    sol_raw = None
    if prm.get("a"):
        try:
            sol_raw = _b64inflate(prm["a"])
        except DecodeError:
            sol_raw = None
    mode = prm.get("m", "edit")
    return {"format": "penpa", "mode": mode, "gridtype": head["gridtype"],
            "nx": int(head["nx"]) if head["nx"].isdigit() else None, "ny": int(head["ny"]) if head["ny"].isdigit() else None,
            "space": js(1, [0, 0, 0, 0]), "header": head,
            "title": re.sub(r"^Title:\s?", "", _field(head["title"])).strip(),
            "author": re.sub(r"^Author:\s?", "", _field(head["author"])).strip(),
            "source_link": _field(head["source"]).strip(), "rules": _field(head["rules"]).strip(),
            "multisolution": head["multisolution"] == "true",
            "pu_q": js(3, {}) or {}, "pu_a": js(4, {}) if mode == "edit" else {},
            "centerlist": cl, "version": js(10), "tags": js(17, []), "solution_raw": sol_raw,
            "url": s if "://" in s else None}


def _solution(d, board, D):
    """digits of the a= solution in board order, or None (missing / multisolution / incomplete)."""
    if not d.get("solution_raw") or d.get("multisolution"):
        return None
    try:
        sol = json.loads(d["solution_raw"])
    except ValueError:
        return None
    nums = sol[4] if isinstance(sol, list) and len(sol) > 4 and isinstance(sol[4], list) else None
    if not nums:
        return None
    val = {}
    for e in nums:
        m = re.fullmatch(r"(\d+),(\d+)", str(e))
        if m:
            val[int(m.group(1))] = int(m.group(2))
    out = [val.get(k) for k in board]
    return out if all(v is not None and 1 <= v <= D for v in out) else None


def _int_text(t):
    t = str(t).strip()
    return int(t) if re.fullmatch(r"\d+", t) else None


def _nonempty(v):
    return bool(v) and not (isinstance(v, list) and all(not x for x in v))


def translate(x, rules_text=None):
    """-> (engine Puzzle, info, decoded). rules_text: the rules from the page that links the puzzle (used together
    with the rules stored in the link). A rules text is required (hidden rules cannot be excluded otherwise); killer
    cages are read as sums only when it speaks of sums / totals / killer. Raises UnsupportedPuzzle with every
    element it cannot map exactly."""
    from .. import model as M
    d = decode(x)
    gt = d["gridtype"]
    if gt not in ("square", "sudoku"):
        raise UnsupportedPuzzle([f"grid type {gt!r}"], "penpa")
    nx, ny = d["nx"], d["ny"]
    nx0, ny0 = nx + 4, ny + 4
    N = nx0 * ny0
    q = d["pu_q"] or {}
    board = list(d["centerlist"])
    if not board:
        sp = d["space"] or [0, 0, 0, 0]
        board = [i + j * nx0 for j in range(2 + sp[0], ny0 - 2 - sp[1]) for i in range(2 + sp[2], nx0 - 2 - sp[3])]
    rows = sorted({k // nx0 for k in board})
    cols = sorted({k % nx0 for k in board})
    D = len(rows)
    bad = []
    if len(cols) != D or len(board) != D * D or len(set(board)) != D * D or \
            rows != list(range(rows[0], rows[0] + D)) or cols != list(range(cols[0], cols[0] + D)):
        raise UnsupportedPuzzle([f"board is not a full square ({len(board)} cells in {len(rows)}x{len(cols)})"], "penpa")
    if D < 4 or D > 16:
        raise UnsupportedPuzzle([f"board size {D}"], "penpa")
    r0, c0 = rows[0], cols[0]
    inboard = set(board)
    cid = {k: (k // nx0 - r0) * D + (k % nx0 - c0) for k in board}      # penpa cell index -> our cell id
    p = M.Puzzle(D=D, coords=M._grid_coords(D))
    for r in range(D):
        p.groups.append(M.Group(f"r{r+1}", tuple(r * D + c for c in range(D)), "row", True))
    for c in range(D):
        p.groups.append(M.Group(f"c{c+1}", tuple(r * D + c for r in range(D)), "col", True))
    used, ignored = Counter(), Counter()

    def where(k):
        k = int(k)
        if k < N:
            return "cell" if k in inboard else "outside cell"
        return ["cell", "vertex", "edge", "edge", "corner", "corner", "corner", "corner", "compass", "compass",
                "compass", "compass"][min(k // N, 11)]

    # ---- regions: thick vertex-to-vertex edge lines; diagonals
    blocked, diag_pairs = set(), []
    for key, style in (q.get("lineE") or {}).items():
        try:
            a, b = sorted(int(t) for t in str(key).split(","))
        except ValueError:
            bad.append(f"edge line {key}")
            continue
        if not (N <= a < 2 * N and N <= b < 2 * N):
            bad.append(f"edge line between {where(a)} and {where(b)} (style {style})")
            continue
        va, vb = a - N, b - N
        (ja, ia), (jb, ib) = divmod(va, nx0), divmod(vb, nx0)
        xa, ya, xb, yb = ia + 1, ja + 1, ib + 1, jb + 1               # grid-point coordinates
        if abs(xa - xb) == 1 and abs(ya - yb) == 1:
            diag_pairs.append(((xa, ya), (xb, yb)))
            continue
        if style in COSMETIC_EDGE:
            ignored[f"edge line style {style}"] += 1
            continue
        if style not in THICK:
            bad.append(f"edge line style {style}")
            continue
        if ya == yb and abs(xa - xb) == 1:                              # horizontal: cells above / below
            x = min(xa, xb)
            blocked.add(frozenset({(ya - 1) * nx0 + x, ya * nx0 + x}))
        elif xa == xb and abs(ya - yb) == 1:                            # vertical: cells left / right
            y = min(ya, yb)
            blocked.add(frozenset({y * nx0 + xa - 1, y * nx0 + xa}))
        else:
            bad.append(f"edge line spanning {key}")
    seen, regions = set(), []
    for k in board:
        if k in seen:
            continue
        comp, stack = [], [k]
        seen.add(k)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in (u - 1, u + 1, u - nx0, u + nx0):
                if v in inboard and v not in seen and frozenset({u, v}) not in blocked:
                    seen.add(v)
                    stack.append(v)
        regions.append(sorted(cid[u] for u in comp))
    if len(regions) == 1:
        bad.append("no region borders drawn")
    elif len(regions) != D or any(len(g) != D for g in regions):
        bad.append(f"thick borders do not split the board into {D} regions of {D} cells "
                   f"(sizes {sorted(len(g) for g in regions)})")
    else:
        for k, g in enumerate(sorted(regions)):
            p.groups.append(M.Group(f"b{k+1}", tuple(g), "box", True))
        used["regions"] = D
    rules = "\n".join(t for t in (d.get("rules"), rules_text) if t)
    tl = rules.lower()
    tl_title = (d.get("title") or "").lower()
    if not tl.strip():
        bad.append("no rules text (pass the linking page's rules as rules_text)")
    if diag_pairs:
        segs = {frozenset(pq) for pq in diag_pairs}
        x0, y0 = c0, r0                                                 # board's top-left grid point (x = col, y = row)
        d1 = {frozenset({(x0 + t, y0 + t), (x0 + t + 1, y0 + t + 1)}) for t in range(D)}
        d2 = {frozenset({(x0 + D - t, y0 + t), (x0 + D - t - 1, y0 + t + 1)}) for t in range(D)}
        rest = segs - d1 - d2
        if rest:
            bad.append("diagonal edge lines off the main diagonals")
        if not re.search(r"diagonal", tl):
            bad.append("drawn diagonal lines (rules text does not mention diagonals)")
        else:
            for name, full, cells in (("d1", d1, [i * D + i for i in range(D)]), ("d2", d2, [i * D + D - 1 - i for i in range(D)])):
                if full & segs:
                    if full <= segs:
                        p.groups.append(M.Group(name, tuple(cells), "diag", True))
                        used["diagonal"] += 1
                    else:
                        bad.append("partially drawn diagonal")
    elif re.search(r"diagonal", tl):
        bad.append("diagonal rule in text without drawn diagonals")

    # ---- givens and numbers
    corner_nums = []                                                    # (corner point, text)
    for key, val in (q.get("number") or {}).items():
        k = int(str(key).rstrip("E")) if str(key).rstrip("E").isdigit() else None
        if k is None or not isinstance(val, list) or not val:
            bad.append(f"number at {key}")
            continue
        txt, style = str(val[0]).strip(), str(val[2]) if len(val) > 2 else "1"
        if txt == "":
            continue
        w = where(k)
        if w == "cell" and style == "1" and _int_text(txt) is not None and 1 <= int(txt) <= D:
            p.givens[cid[k]] = int(txt)
            used["givens"] += 1
        elif w == "cell" and style == "7":
            bad.append("pencil-mark candidates")
        elif w == "corner":
            corner_nums.append((k, txt))
        else:
            bad.append(f"{w} number {txt!r}" + (f" (style {style})" if w == "cell" else ""))
    for key, val in (q.get("numberS") or {}).items():
        k = int(key) if str(key).isdigit() else None
        txt = str(val[0]).strip() if isinstance(val, list) and val else ""
        if k is None:
            bad.append(f"small number at {key}")
        elif txt:
            if where(k) == "corner":
                corner_nums.append((k, txt))
            else:
                bad.append(f"small {where(k)} number {txt!r}")

    # ---- killer cages
    cages = [c for c in (q.get("killercages") or []) if c]
    cage_of = {}
    for ci_, cg in enumerate(cages):
        if any(int(k) not in inboard for k in cg):
            bad.append("killer cage outside the board")
            continue
        for k in cg:
            cage_of[int(k)] = ci_
    sums = defaultdict(list)
    for k, txt in corner_nums:
        cell = (k - 4 * N) // 4
        if cell in cage_of:
            sums[cage_of[cell]].append(txt)
        else:
            bad.append(f"corner number {txt!r} outside any killer cage")
    for ci_, cg in enumerate(cages):
        if any(int(k) not in inboard for k in cg):
            continue
        ss = sums.get(ci_, [])
        total = None
        if len(ss) > 1:
            bad.append(f"killer cage with {len(ss)} corner numbers")
        elif ss:
            total = _int_text(ss[0])
            if total is None:
                bad.append(f"killer cage clue {ss[0]!r}")
        cells = tuple(sorted(cid[int(k)] for k in cg))
        if tl.strip() and not KILLER_TEXT.search(tl):
            bad.append("killer cages (rules text does not describe cage sums)")
        p.groups.append(M.Group(f"k{ci_}", cells, "cage", len(cells) == D, total))
        used["killer"] += 1
    if q.get("cage"):
        cells_drawn = {(int(t) - 4 * N) // 4 for key in q["cage"] for t in str(key).split(",") if t.isdigit()
                       and 4 * N <= int(t) < 8 * N}
        orphan = {c for c in cells_drawn if c not in cage_of}
        if orphan:
            bad.append("cage outlines without a killer-cage grouping")
        else:
            ignored["cage outlines (drawn killer cages)"] += 1

    # ---- thermometers, arrows
    circles = {int(k) for k, v in (q.get("symbol") or {}).items() if str(k).isdigit() and isinstance(v, list)
               and len(v) > 1 and str(v[1]).startswith("circle") and int(k) in inboard}
    consumed = set()

    def path_ok(path):
        if len(path) < 2 or any(k not in inboard for k in path) or len(set(path)) != len(path):
            return False
        return all(abs(a // nx0 - b // nx0) <= 1 and abs(a % nx0 - b % nx0) <= 1 for a, b in zip(path, path[1:]))

    for th in q.get("thermo") or []:
        if not th:
            continue
        path = [int(k) for k in th]
        if not path_ok(path):
            bad.append("malformed thermometer")
            continue
        p.constraints.append({"type": "line", "kind": "thermo", "cells": [cid[k] for k in path]})
        consumed.add(path[0])
        used["thermo"] += 1
    for ar in q.get("arrows") or []:
        if not ar:
            continue
        path = [int(k) for k in ar]
        if not path_ok(path):
            bad.append("arrow outside the board / malformed")
            continue
        if path[0] not in circles:
            bad.append("arrow without a circle at its start")
            continue
        p.constraints.append({"type": "arrow", "circle": [cid[path[0]]], "line": [cid[k] for k in path[1:]]})
        consumed.add(path[0])
        used["arrow"] += 1
    for k, v in (q.get("symbol") or {}).items():
        kk = int(k) if str(k).isdigit() else None
        name = str(v[1]) if isinstance(v, list) and len(v) > 1 else str(v)
        if kk is not None and kk in consumed and name.startswith("circle"):
            continue
        bad.append(f"symbol {name} at {where(kk) if kk is not None else k}")

    # ---- elements this mapper never takes
    for key in ("surface", "line", "wall", "freeline", "freelineE", "direction", "squareframe", "polygon", "nobulbthermo"):
        v = q.get(key)
        if _nonempty(v):
            n = len(v) if isinstance(v, (list, dict)) else 1
            bad.append({"surface": "shaded cells", "line": "lines", "nobulbthermo": "thermo without bulb"}.get(key, key)
                       + f" ({n})")
    if _nonempty(q.get("deletelineE")):
        ignored["deleted grid lines"] += 1
    if d["header"].get("bg_image"):
        bad.append("background image")
    for name, rx in TEXT_RULES:
        if re.search(rx, tl) or re.search(rx, tl_title):
            bad.append(f"rule '{name}' (rules text)")
    if bad:
        raise UnsupportedPuzzle(sorted(set(bad)), "penpa")
    info = dict(used)
    if ignored:
        info["_ignored"] = dict(ignored)
    return p, info, d


def to_puzzle(x, rules_text=None, url=None):
    """penpa link / p= value / decoded dict -> puzzle JSON dict (title, author, rules_text, source, a= solution)."""
    p, info, d = translate(x, rules_text=rules_text)
    D = p.D
    nx0 = d["nx"] + 4
    board = sorted(d["centerlist"]) if d["centerlist"] else None
    if board is None:
        sp = d["space"] or [0, 0, 0, 0]
        board = [i + j * nx0 for j in range(2 + sp[0], d["ny"] + 2 - sp[1]) for i in range(2 + sp[2], d["nx"] + 2 - sp[3])]
    board.sort(key=lambda k: (k // nx0, k % nx0))
    sol = _solution(d, board, D)
    meta = {"title": d.get("title"), "author": d.get("author"), "rules_text": d.get("rules") or rules_text,
            "source": url or d.get("url")}
    return to_puzzle_json(p, solution=sol, meta=meta)


__all__ = ["decode", "translate", "to_puzzle", "params", "is_penpa_url", "COMPRESS_SUB"]
