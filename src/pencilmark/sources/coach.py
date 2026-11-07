"""sudoku.coach (sudoku.coach/en/s/<id>) puzzles -> pencilmark-puzzle documents, the setter's look kept as `style`.

Forms
    https://sudoku.coach/en/s/<id>     a puzzle page: fetch() reads its embedded record (one GET of the page)
    'SCv7_32_<base32>'                 the payload itself: base32 (alphabet 0-9a-v) of zlib-deflated JSON
    a record dict                      {"sudoku": <payload>, "solution", "name", "author", "description", ...} as the
                                       page embeds it (`mainInitData.specificSudoku`)
Older payloads (SCv2..SCv6, positional) are refused with NotSupportedError.

The JSON: gridSize, givenDigits (one character per cell), regions (missing: standard boxes, [] none, else one region
number per cell), givenConstraints [{type, segments: [{cells, parameters}], settings}], colours + givenColours (cell
colours, several per cell possible). Cells are 0-based indices r * N + c; cosmetic types give [y, x] points in cell
units. Every constraint type maps to a rule family (to_document); a type with no family, a cage sum that is not a
number, rules stated only in the description (`custom_constraints`) are refused, never dropped. Settings that carry
meaning (a whisper's difference, a negative constraint) become rules; the rest is the cosmetic `style` of each rule,
and the cosmetic types and cell colours become `decorations`.

    decode(x) -> {"format": "SCv7", "puzzle": <JSON>, "meta": {...}}     fetch(link_or_id) -> record dict
    to_document(decoded, *, check_solution=True) -> pencilmark-puzzle dict
    read(x, *, fetch=True) -> pencilmark-puzzle dict (decode + to_document; a link is fetched)
"""

from __future__ import annotations

import html
import json
import math
import re
import urllib.parse
import zlib

from ._common import FormatError, Http, NotSupportedError, ReadingMismatch, reads, unsupported

PREFIX = "SCv7_32_"
ALPHABET = "0123456789abcdefghijklmnopqrstuv"
HOST = re.compile(r"(?:^|\.)sudoku\.coach$", re.I)
PAGE = "https://sudoku.coach/en/s/"
HTTP = Http(min_gap=1.0)  # one GET per puzzle page, >= 1 s apart

# the app's light-theme named colors (accessibilityDefaultColours; docs/research style survey 2026-11-07)
NAMED_COLOURS = {
    "white": "#ffffff",
    "grey": "#e2e2e2",
    "lime": "#def7c5",
    "blue": "#c5e4f7",
    "purple": "#d1c5f7",
    "red": "#f7c5c5",
    "green": "#c5f7d3",
    "yellow": "#f7f7c5",
    "orange": "#f7e4c5",
    "cyan": "#c5f7f5",
    "magenta": "#f7c5f5",
}
# box shape [height, width] of the app's default boxes per grid size (sizes without one have no boxes)
DEFAULT_BOXES = {4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3)}
LINE_KINDS = {
    "thermometer": "thermo",
    "whisper": "whisper",
    "renban": "renban",
    "palindromeLine": "palindrome",
    "betweenLine": "between",
    "lockoutLine": "lockout",
    "entropicLine": "entropic",
    "modularLine": "modular",
    "regionSumLine": "region_sum",
}
# cosmetic shape defaults of the app's editor (size in % of a cell, fill color)
SHAPE_SIZE, SHAPE_FILL, TEXT_SIZE = 63, "#d5e2ff", 110
ORTHO = ((0, 1), (1, 0), (0, -1), (-1, 0))


# ------------------------------------------------------------------------------------------------------- decoding
def is_coach_url(s):
    """True for a sudoku.coach link"""
    if not isinstance(s, str) or "://" not in s:
        return False
    return bool(HOST.search(urllib.parse.urlsplit(s.strip()).netloc.split(":")[0]))


def puzzle_id(x):
    """sudoku.coach link or bare id -> the id ('LW4k')"""
    s = x.strip()
    if "://" in s:
        m = re.search(r"/s/([A-Za-z0-9]+)", urllib.parse.urlsplit(s).path)
        if not m:
            raise FormatError(f"no puzzle id in sudoku.coach link {s[:80]!r}")
        return m.group(1)
    if not re.fullmatch(r"[A-Za-z0-9]{1,16}", s):
        raise FormatError(f"not a sudoku.coach puzzle id: {s[:80]!r}")
    return s


def decode_payload(payload):
    """'SCv7_32_...' -> the puzzle JSON dict. Older versions raise NotSupportedError."""
    s = payload.strip()
    m = re.match(r"SCv(\d+)_", s)
    if not m:
        raise FormatError(f"not a sudoku.coach payload: {s[:40]!r}")
    if not s.startswith(PREFIX):
        raise NotSupportedError(
            f"sudoku.coach payload version SCv{m.group(1)} is not supported (only SCv7, '{PREFIX}...')",
            [f"SCv{m.group(1)}"],
        )
    bits = width = 0
    raw = bytearray()
    for ch in s[len(PREFIX) :]:
        v = ALPHABET.find(ch)
        if v < 0:
            raise FormatError(f"sudoku.coach payload has {ch!r}, outside the base32 alphabet 0-9a-v")
        bits, width = ((bits << 5) | v) & 0xFFFF, width + 5
        if width >= 8:  # 5 bits per character, most significant first; trailing bits are padding
            width -= 8
            raw.append((bits >> width) & 0xFF)
    try:
        d = json.loads(zlib.decompress(bytes(raw)))
    except (zlib.error, ValueError) as e:
        raise FormatError(f"undecodable sudoku.coach payload ({type(e).__name__}: {e})") from e
    if not isinstance(d, dict) or not isinstance(d.get("gridSize"), int):
        raise FormatError("sudoku.coach payload has no gridSize")
    return d


def _plain(s):
    """a record's classic puzzle stored as N*N digits -> the same JSON an SCv7 payload gives"""
    n = math.isqrt(len(s))
    if n * n != len(s) or not 1 <= n <= 9 or not s.isdigit():
        raise FormatError(f"not a sudoku.coach puzzle string: {s[:40]!r}")
    return {"gridSize": n, "givenDigits": s}


def decode(x):
    """Payload / record dict / the payload's JSON / decoded dict -> {"format": "SCv7", "puzzle": <JSON>, "meta": {id, title, author,
    rules_text, solution, custom_constraints}}. Links need fetch() (or read())."""
    if isinstance(x, dict) and "puzzle" in x and x.get("format") in ("SCv7", "plain"):
        return x
    if isinstance(x, dict) and "gridSize" in x:  # the payload's JSON itself
        return {"format": "SCv7", "puzzle": x, "meta": {}}
    meta = {}
    if isinstance(x, dict):
        if not isinstance(x.get("sudoku"), str):
            raise FormatError('a sudoku.coach record needs its payload under "sudoku"')
        meta = {
            "id": x.get("sudoku_id") or x.get("sudokuHash"),
            "title": x.get("name"),
            "author": x.get("author"),
            "rules_text": x.get("description"),
            "solution": x.get("solution"),
            "custom_constraints": bool(x.get("custom_constraints")),
        }
        x = x["sudoku"]
        if x.strip().isdigit():
            return {"format": "plain", "puzzle": _plain(x.strip()), "meta": meta}
    if not isinstance(x, str) or not x.strip():
        raise FormatError("empty sudoku.coach payload")
    if "://" in x:
        raise FormatError(f"{x[:80]!r} is a sudoku.coach link; read it with coach.fetch() or coach.read()")
    return {"format": "SCv7", "puzzle": decode_payload(x), "meta": meta}


def record_of_page(text):
    """the puzzle record a sudoku.coach page embeds (`mainInitData.specificSudoku`)"""
    m = re.search(r"mainInitData\s*=\s*(\{.*?\})\s*;?\s*</script>", text, re.S)
    try:
        rec = json.loads(m.group(1))["specificSudoku"] if m else None
    except (ValueError, KeyError, TypeError):
        rec = None
    if not isinstance(rec, dict) or not isinstance(rec.get("sudoku"), str):
        raise FormatError("no puzzle record (mainInitData.specificSudoku) in the sudoku.coach page")
    return rec


def fetch(x, http=None):
    """sudoku.coach link or id -> the page's puzzle record (one GET of the page, identifying User-Agent)."""
    pid = puzzle_id(x)
    rec = record_of_page((http or HTTP).get_text(PAGE + pid))
    rec.setdefault("sudoku_id", pid)
    return rec


# ---------------------------------------------------------------------------------------------------------- style
def colour(c):
    """coach colour (a name of the app's palette or '#rrggbb[aa]') -> '#rrggbb', or None"""
    if not isinstance(c, str):
        return None
    if c in NAMED_COLOURS:
        return NAMED_COLOURS[c]
    m = re.fullmatch(r"#([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?", c.strip())
    return "#" + m.group(1).lower() if m else None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _units(v):
    """a percentage of a cell -> cell units"""
    v = _num(v)
    return None if v is None else round(v / 100, 3)


def style_of(settings, shape=False):
    """coach settings -> rule style. Lines: colour is the line, the border its outline (the app draws the line
    lineThickness wide in the border colour, then lineThickness - borderThickness in the line colour). Shapes: colour
    is the fill, the border the shape's colour."""
    s = settings if isinstance(settings, dict) else {}
    out = {}
    if shape:
        out["fill"] = colour(s.get("colour"))
        out["color"] = colour(s.get("borderColour"))
        out["outline_width"] = _units(s.get("borderThickness"))
        out["size"] = _units(s.get("shapeSize"))
        out["angle"] = _num(s.get("shapeRotation"))
    else:
        out["color"] = colour(s.get("colour"))
        line, border = _num(s.get("lineThickness")), _num(s.get("borderThickness")) or 0
        if line is not None:
            out["width"] = round(max(line - border, 0) / 100, 3)
        if border and colour(s.get("borderColour")):
            out["outline"] = colour(s.get("borderColour"))
            out["outline_width"] = round(border / 200, 3)
        out["fill"] = colour(s.get("bulbFillColour"))  # thermometer / arrow / between / lockout bulbs
        out["size"] = _units(s.get("bulbSize"))
    if _num(s.get("opacity")) is not None:
        out["opacity"] = round(s["opacity"] / 255, 3)
    return {k: v for k, v in out.items() if v is not None}


def _with_style(rule, style):
    if style:
        rule["style"] = dict(style)
    return rule


# ------------------------------------------------------------------------------------------------------ the board
class _Board:
    """an N x N coach grid: cell names, neighbours"""

    def __init__(self, n, cons=()):
        self.n = n
        self.region = [None] * (n * n)  # box / jigsaw piece of each cell (_houses)
        self.marked = {}  # minimum / maximum: every marked cell (they are not compared with each other)
        for c in cons:
            if c.get("type") in ("minimum", "maximum"):
                cells = {i for seg in c.get("segments") or [] for i in seg.get("cells") or [] if isinstance(i, int)}
                self.marked.setdefault(c["type"], set()).update(cells)

    def name(self, i):
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < self.n * self.n:
            raise FormatError(f"cell index {i!r} is outside the {self.n}x{self.n} grid")
        return f"r{i // self.n + 1}c{i % self.n + 1}"

    def names(self, cells):
        return [self.name(i) for i in cells]

    def adjacent(self, a, b):
        (ra, ca), (rb, cb) = divmod(a, self.n), divmod(b, self.n)
        return abs(ra - rb) + abs(ca - cb) == 1

    def neighbours(self, i):
        r, c = divmod(i, self.n)
        return [(r + dr) * self.n + c + dc for dr, dc in ORTHO if 0 <= r + dr < self.n and 0 <= c + dc < self.n]


def _givens(P, n):
    s = str(P.get("givenDigits") or "")
    if not s:
        return [0] * (n * n)
    if len(s) != n * n:
        raise FormatError(f"givenDigits has {len(s)} characters; a {n}x{n} grid needs {n * n}")
    out = []
    for ch in s:
        v = int(ch, 36) if ch.isalnum() else 0
        if v > n:
            raise FormatError(f"given digit {ch!r} is outside 1..{n}")
        out.append(v)
    return out


def _regular(regions, n):
    """the box shape [h, w] when the region numbers tile the grid with regular boxes, else None"""
    for h in range(1, n + 1):
        if n % h:
            continue
        w = n // h
        if h == 1 or w == 1:
            continue
        ids = {}
        ok = True
        for i, reg in enumerate(regions):
            box = (i // n // h, i % n // w)
            if ids.setdefault(reg, box) != box:
                ok = False
                break
        if ok and len(ids) == n:
            return (h, w)
    return None


def _houses(P, n, B):
    """house rules: standard boxes when regions are missing, none for [], else a jigsaw (or the boxes it equals).
    Sets B.region, the box / jigsaw piece of each cell (None without boxes)."""
    regions = P.get("regions")
    if "regions" not in P:
        hw = DEFAULT_BOXES.get(n)
        regions = [(i // n // hw[0], i % n // hw[1]) for i in range(n * n)] if hw else []
    if not regions:
        B.region = [None] * (n * n)
        return [{"type": "grid"}]
    if not isinstance(regions, list) or len(regions) != n * n:
        raise FormatError(f"regions has {len(regions) if isinstance(regions, list) else '?'} entries; needs {n * n}")
    B.region = [r if not isinstance(r, list) else tuple(r) for r in regions]
    hw = _regular(B.region, n)
    if hw:
        return [_box_grid(n, hw)]
    groups = {}
    for i, reg in enumerate(B.region):
        groups.setdefault(reg, []).append(i)
    full = all(len(g) == n for g in groups.values())
    kind = {"type": "box"} if full else {"type": "region", "kind": "region"}
    return [{"type": "grid"}] + [dict(kind, cells=B.names(g)) for g in groups.values() if len(g) > 1 or full]


def _box_grid(n, hw):
    h, w = hw
    return {"type": "box_grid", "box": [h, w], "count": [n // h, n // w]}


# ---------------------------------------------------------------------------------------------------- rule makers
def _int_param(v, what):
    """a numeric parameter (number or digit string) -> int; text with a meaning only in the rules is refused"""
    if isinstance(v, bool):
        raise NotSupportedError(f"{what} {v!r} is not a number", [what])
    if isinstance(v, (int, float)) and float(v).is_integer():
        return int(v)
    if isinstance(v, str) and re.fullmatch(r"\s*-?\d+\s*", v):
        return int(v)
    raise NotSupportedError(f"{what} {v!r} is not a number (its meaning is only in the rules text)", [what])


def _pair(seg, what):
    cells = seg.get("cells") or []
    if len(cells) != 2:
        raise FormatError(f"a {what} clue needs 2 cells, has {len(cells)}")
    return cells


def _edge(B, a, b, rule, op_rule):
    """an edge clue on adjacent cells; the same pair rule as a relation when they are not adjacent"""
    if B.adjacent(a, b):
        return dict(rule, cells=B.names([a, b]))
    return dict(op_rule, pairs=[B.names([a, b])])


def _dots(ctype, segs, B, style):
    """ratio / difference / twoCellSum / greaterLess segments -> edge rules"""
    out = []
    for seg in segs:
        a, b = _pair(seg, ctype)
        p = seg.get("parameters") or {}
        if ctype == "ratio":
            k = _int_param(p.get("ratio", 2), "ratio")
            rule = (
                {"type": "edge", "kind": "kropki", "color": "black"}
                if k == 2
                else {"type": "edge", "kind": "ratio", "value": k}
            )
            op = {"type": "relation", "op": "ratio", "value": k}
        elif ctype == "difference":
            k = _int_param(p.get("difference", 1), "difference")
            rule = (
                {"type": "edge", "kind": "kropki", "color": "white"}
                if k == 1
                else {"type": "edge", "kind": "difference", "value": k}
            )
            op = {"type": "relation", "op": "difference", "value": k}
        elif ctype == "twoCellSum":
            s = _int_param(p.get("sum"), "two-cell sum")
            letter = {10: "X", 5: "V"}.get(s)
            rule = (
                {"type": "edge", "kind": "xv", "letter": letter}
                if letter
                else {"type": "edge", "kind": "sum", "sum": s}
            )
            op = {"type": "relation", "op": "sum", "sum": s}
        else:  # greaterLess: the first cell is the smaller
            a, b = b, a
            rule, op = {"type": "edge", "kind": "greater"}, {"type": "relation", "op": "less"}
            if not B.adjacent(a, b):
                out.append(_with_style({"type": "relation", "op": "less", "pairs": [B.names([b, a])]}, style))
                continue
        out.append(_with_style(_edge(B, a, b, rule, op), style))
    return out


def _negatives(cons, B):
    """the app's negative constraints: nonconsecutive and a difference negative are both 'no unmarked orthogonal pair
    differs by 1' (a pair with a difference clue is exempt); a ratio negative is 'no unmarked pair is in ratio 2' (a
    pair with a ratio clue is exempt). Other clues exempt nothing (the app's own solver list, 2026-11-07)."""
    types = {c["type"] for c in cons}
    neg = {c["type"] for c in cons if (c.get("settings") or {}).get("negativeConstraint")}
    marked = lambda t: {
        frozenset(s["cells"])
        for c in cons
        if c["type"] == t
        for s in c.get("segments") or []
        if len(s.get("cells") or []) == 2
    }
    out = []
    for when, of, rule in (
        (
            "nonconsecutive" in types or "difference" in neg,
            "difference",
            {"type": "neighbors", "kind": "nonconsecutive"},
        ),
        ("ratio" in neg, "ratio", {"type": "neighbors", "op": "not_ratio", "value": 2, "step": "orthogonal"}),
    ):
        if not when:
            continue
        exempt = sorted(sorted(p) for p in marked(of) if B.adjacent(*p))
        if exempt:
            rule = dict(rule, **{"except": [B.names(p) for p in exempt]})
        out.append(rule)
    return out


def _line_value(kind, ctype, settings, n):
    """the rule's parameters of a line kind (a whisper's difference lives in the app's settings)"""
    if kind == "whisper":
        v = _int_param(settings.get("difference", 5), "whisper difference")
        return {"value": v} if v != 5 or n != 9 else {}
    if kind == "lockout":
        return {"value": 4} if n != 9 else {}
    if kind == "modular":
        return {"value": 3} if n != 9 else {}
    if kind == "entropic" and n != 9:
        if n % 3 == 0:  # the app's classes are 1-3, 4-6, 7-9 at every size; the format's are thirds of 1..D
            raise NotSupportedError(f"entropic line on a {n}x{n} grid (the app's 1-3 / 4-6 / 7-9 classes)", [ctype])
        return {"groups": [[v for v in range(1, n + 1) if (v - 1) // 3 == g] for g in range(3)]}
    return {}


def _groups(segs):
    """the app's grouping of a line constraint's segments: segments sharing a cell form one line, its cells in the
    order they join (first segment, then every touching segment in index order, until nothing joins)"""
    cells_of = [list(seg.get("cells") or []) for seg in segs]
    done, out = set(), []
    for k, first in enumerate(cells_of):
        if k in done:
            continue
        group, members, changed = dict.fromkeys(first), {k}, True
        while changed:
            changed = False
            for j, cs in enumerate(cells_of):
                if j != k and any(c in group for c in cs):
                    members.add(j)
                    new = [c for c in cs if c not in group]
                    group.update(dict.fromkeys(new))
                    changed = changed or bool(new)
        done |= members
        out.append((list(group), [cells_of[j] for j in sorted(members)]))
    return out


def _touch(B, a, b):
    (ra, ca), (rb, cb) = divmod(a, B.n), divmod(b, B.n)
    return max(abs(ra - rb), abs(ca - cb)) == 1


def _path(B, cells, limit=20000):
    """an order of a cell set in which consecutive cells touch (a renban is a set: any path draws it), or None"""
    if all(_touch(B, a, b) for a, b in zip(cells, cells[1:])):
        return cells
    left, budget = set(cells), [limit]

    def walk(path):
        if len(path) == len(cells):
            return path
        budget[0] -= 1
        if budget[0] < 0:
            return None
        for c in sorted(x for x in left if _touch(B, path[-1], x)):
            left.discard(c)
            got = walk(path + [c])
            if got:
                return got
            left.add(c)
        return None

    for start in cells:
        left.discard(start)
        got = walk([start])
        if got:
            return got
        left.add(start)
    return None


def _linked(segs, a, b):
    """True when a and b are neighbours on one of the segments"""
    return any({x, y} == {a, b} for cs in segs for x, y in zip(cs, cs[1:]))


def _region_sum_order(B, cells, segs):
    """the app turns a looped region-sum line so that it starts where it enters a new box"""
    if len(cells) > 2 and _linked(segs, cells[0], cells[-1]):
        for _ in range(len(cells) + 1):
            if B.region[cells[0]] != B.region[cells[-1]]:
                break
            cells = cells[1:] + cells[:1]
    return cells


def _lines(ctype, segs, B, settings, style):
    """line segments -> line rules. Renban, palindrome and region-sum segments that share a cell are one line in the
    app (_groups); the other kinds are one line per segment."""
    kind = LINE_KINDS[ctype]
    params = _line_value(kind, ctype, settings, B.n)
    branched = []  # renban groups no single line covers
    if kind in ("renban", "palindrome", "region_sum"):
        lines = []
        for cells, members in _groups(segs):
            if kind == "renban":
                path = _path(B, cells)
                if path is None:
                    branched.append((cells, members))
                    continue
                cells = path
            elif kind == "region_sum":
                cells = _region_sum_order(B, cells, members)
            lines.append(cells)
    else:
        lines = [list(seg.get("cells") or []) for seg in segs]
    out = []
    for cells in lines:
        if len(cells) < 2:
            raise FormatError(f"a {ctype} needs at least 2 cells, has {len(cells)}")
        if kind == "whisper" and not all(_touch(B, a, b) for a, b in zip(cells, cells[1:])):
            out += _jumping_whisper(B, cells, params.get("value", 5), style)
            continue
        rule = {"type": "line", "kind": kind, **params}
        if kind == "whisper" and len(cells) > 3 and cells[0] == cells[-1]:
            rule["closed"] = True
            cells = cells[:-1]
        rule["cells"] = B.names(cells)
        out.append(_with_style(rule, style))
    return out + [r for cells, members in branched for r in _branched_renban(B, cells, members, style)]


def _centres(B, cells):
    return [[i // B.n + 0.5, i % B.n + 0.5] for i in cells]


def _line_look(style):
    return {k: v for k, v in style.items() if k in ("color", "width", "outline", "outline_width", "opacity")}


def _jumping_whisper(B, cells, k, style):
    """a whisper drawn between cells that do not touch: its meaning as pairs, its drawing as a line decoration"""
    pairs = [B.names(p) for p in zip(cells, cells[1:])]
    rule = {"type": "relation", "op": "difference_at_least", "value": k, "pairs": pairs, "label": "whisper"}
    return [rule, {"_decoration": {"kind": "line", "points": _centres(B, cells), "style": _line_look(style)}}]


def _branched_renban(B, cells, members, style):
    """a renban the app draws as touching segments that no single line covers: the set rule as a custom rule, and
    its segments as line decorations so it still draws as a renban"""
    rule = {
        "type": "custom",
        "cells": {"r": B.names(cells)},
        "holds": "all_different(r) and max(r) - min(r) == len(r) - 1",
        "label": "renban",
    }
    lines = [_centres(B, cs) for cs in members if len(cs) > 1]
    return [rule] + [{"_decoration": {"kind": "line", "points": pts, "style": _line_look(style)}} for pts in lines]


def _consecutive(segs, B, style):
    """the app's consecutive line: no repeats among the cells of segments that share a cell (_groups), and neighbours
    on each segment differ by 1. Over a connected group that is a renban plus the differences."""
    out = []
    for cells, members in _groups(segs):
        if len(cells) < 2:
            raise FormatError(f"a consecutive line needs at least 2 cells, has {len(cells)}")
        path = _path(B, cells)
        if path is None:
            out.append(_with_style({"type": "region", "kind": "region", "cells": B.names(cells)}, style))
        else:
            out.append(_with_style({"type": "line", "kind": "renban", "cells": B.names(path)}, style))
        pairs = [B.names(p) for cs in members for p in zip(cs, cs[1:])]
        out.append({"type": "relation", "op": "difference", "value": 1, "pairs": pairs})
    return out


def _arrows(ctype, segs, B, style):
    pill = 2 if ctype == "pillArrow" else 1
    out = []
    for seg in segs:
        cells = list(seg.get("cells") or [])
        if len(cells) <= pill:
            raise FormatError(f"an {ctype} needs more than {pill} cells, has {len(cells)}")
        bulb = sorted(cells[:pill])  # a pill reads as a number in reading order (the app sorts its cells)
        out.append(_with_style({"type": "arrow", "bulb": B.names(bulb), "lines": [B.names(cells[pill:])]}, style))
    return out


def _outside_line(B, side, index):
    n = B.n
    if not isinstance(index, int) or not 0 <= index < n:
        raise FormatError(f"outside clue index {index!r} is outside 0..{n - 1}")
    cells = {
        "left": [index * n + c for c in range(n)],
        "right": [index * n + c for c in reversed(range(n))],
        "top": [r * n + index for r in range(n)],
        "bottom": [r * n + index for r in reversed(range(n))],
    }.get(side)
    if cells is None:
        raise FormatError(f"outside clue side {side!r} is not left / right / top / bottom")
    return cells


def _sandwiches(segs, B, style):
    out = []
    for seg in segs:
        p = seg.get("parameters") or {}
        cells = _outside_line(B, p.get("side"), p.get("index"))
        rule = {"type": "sandwich", "sum": _int_param(p.get("value"), "sandwich sum"), "side": p["side"]}
        out.append(_with_style(dict(rule, cells=B.names(cells)), style))
    return out


def _little_killers(segs, B, style):
    """the clue sits at [x, y] outside the grid; positive = the / diagonal, else the \\ one, into the grid"""
    n, out = B.n, []
    for seg in segs:
        p = seg.get("parameters") or {}
        if p.get("value") in (None, "", 0, "0"):  # an empty clue: the app gives its solver nothing
            continue
        pos = (seg.get("cells") or [None])[0]
        x, y = pos if isinstance(pos, list) and len(pos) == 2 else (None, None)
        if not (isinstance(x, int) and isinstance(y, int)) or (0 <= x < n and 0 <= y < n):
            raise FormatError(f"little killer position {[x, y]!r} is not outside the grid")
        steps = ((1, -1), (-1, 1)) if p.get("positive") else ((1, 1), (-1, -1))
        cells = []
        for dr, dc in steps:
            r, c = y + dr, x + dc
            while 0 <= r < n and 0 <= c < n:
                cells.append(r * n + c)
                r, c = r + dr, c + dc
            if cells:
                break
        if not cells:
            raise FormatError(f"little killer at {[x, y]!r} points at no cell")
        side = "top" if y < 0 else "bottom" if y >= n else "left" if x < 0 else "right"
        rule = {"type": "sum", "kind": "little_killer", "sum": _int_param(p.get("value"), "little killer sum")}
        out.append(_with_style(dict(rule, side=side, cells=B.names(cells)), style))
    return out


def _cages(segs, B, style):
    out = []
    for seg in segs:
        cells = list(seg.get("cells") or [])
        if not cells:
            continue
        s = (seg.get("parameters") or {}).get("sum")
        rule = {"type": "cage"}
        if s not in (None, "", 0, "0"):
            rule["sum"] = _int_param(s, "cage sum")
        out.append(_with_style(dict(rule, cells=B.names(cells)), style))
    return out


def _quadruples(segs, B, style):
    n, out = B.n, []
    for seg in segs:
        tl = (seg.get("cells") or [None])[0]
        if not isinstance(tl, int) or tl % n == n - 1 or tl // n >= n - 1:
            raise FormatError(f"quadruple corner cell {tl!r} has no 2x2 block")
        digits = [int(ch, 36) for ch in str((seg.get("parameters") or {}).get("digits", "")) if ch.isalnum()]
        if not digits:
            continue
        cells = [tl, tl + 1, tl + n, tl + n + 1]
        out.append(_with_style({"type": "quadruple", "digits": digits, "cells": B.names(cells)}, style))
    return out


def _extremes(ctype, segs, B, style):
    """minimum / maximum: the cell is less / greater than each orthogonal neighbour that is not marked the same way
    (the app compares two adjacent maxima with nothing)"""
    same = {c for seg in segs for c in seg.get("cells") or []} | B.marked.get(ctype, set())
    out = []
    for seg in segs:
        for c in seg.get("cells") or []:
            prs = [[c, m] if ctype == "minimum" else [m, c] for m in B.neighbours(c) if m not in same]
            if prs:
                rule = {"type": "relation", "op": "less", "pairs": [B.names(p) for p in prs]}
                out.append(_with_style(rule, style))
    return out


def _fog(segs, B, givens, solution):
    if not solution:
        raise NotSupportedError("a fog puzzle needs its solution (a correct digit lights the fog)", ["fog"])
    n = B.n
    lit = {c for seg in segs for c in seg.get("cells") or []}
    for i, v in enumerate(givens):  # the app lights the 3x3 around every correct digit, givens included
        if v:
            r, c = divmod(i, n)
            lit |= {
                rr * n + cc for rr in range(r - 1, r + 2) for cc in range(c - 1, c + 2) if 0 <= rr < n and 0 <= cc < n
            }
    return {"type": "fog", "lit": B.names(sorted(lit))}


# ---------------------------------------------------------------------------------------------------- decorations
def _cell_fills(P, n, B):
    """colours + givenColours -> one fill decoration (a cell with several palette indices has several parts)"""
    pal = [colour(c) for c in P.get("colours") or []]
    per = str(P.get("givenColours") or "").split(",")
    cells = {}
    for i, entry in enumerate(per[: n * n]):
        cs = [pal[k] for k in (int(ch, 36) for ch in entry if ch.isalnum()) if k < len(pal) and pal[k]]
        if cs:
            cells[B.name(i)] = cs
    return [{"kind": "fill", "cells": cells, "style": {"opacity": 1}}] if cells else []


def _point(p):
    if not (isinstance(p, (list, tuple)) and len(p) == 2 and all(_num(v) is not None for v in p)):
        raise FormatError(f"cosmetic point {p!r} is not [y, x]")
    return [p[0], p[1]]


def _shape_points(kind, y, x, size, angle):
    """a regular polygon ('polygon-N', first corner up) or a plus sign, centred at (y, x), size wide, turned angle"""
    if kind == "plus":
        a, b = size / 2, size / 6
        pts = [
            (-a, -b),
            (-a, b),
            (-b, b),
            (-b, a),
            (b, a),
            (b, b),
            (a, b),
            (a, -b),
            (b, -b),
            (b, -a),
            (-b, -a),
            (-b, -b),
        ]
    else:
        k = int(kind.split("-")[1])
        pts = [(-math.cos(2 * math.pi * j / k) * size / 2, math.sin(2 * math.pi * j / k) * size / 2) for j in range(k)]
    t = math.radians(angle or 0)
    rot = lambda dy, dx: [
        round(y + dy * math.cos(t) + dx * math.sin(t), 4),
        round(x - dy * math.sin(t) + dx * math.cos(t), 4),
    ]
    return [rot(dy, dx) for dy, dx in pts]


def _shapes(c):
    s = c.get("settings") or {}
    st = style_of(dict({"colour": SHAPE_FILL, "shapeSize": SHAPE_SIZE}, **s), shape=True)
    size = st.pop("size")
    angle = st.pop("angle", None)
    out = []
    for seg in c.get("segments") or []:
        kind = str((seg.get("parameters") or {}).get("shape") or "circle")
        for p in seg.get("cells") or []:
            y, x = _point(p)
            if kind == "circle":
                out.append({"kind": "circle", "center": [y, x], "size": [size, size], "style": dict(st)})
            elif kind == "rect":
                out.append(
                    {
                        "kind": "rect",
                        "center": [y, x],
                        "size": [size, size],
                        "style": dict(st, **({"angle": angle} if angle else {})),
                    }
                )
            elif kind == "plus" or re.fullmatch(r"polygon-[3-9]", kind):
                out.append({"kind": "polygon", "points": _shape_points(kind, y, x, size, angle), "style": dict(st)})
            else:
                raise NotSupportedError(f"cosmetic shape {kind!r}", [f"cosmeticShape {kind}"])
    return out


def _texts(c):
    s = c.get("settings") or {}
    st = {"color": colour(s.get("colour")) or "#000000", "size": _units(s.get("textSize", TEXT_SIZE))}
    if _num(s.get("outlineThickness")):
        st["outline"] = colour(s.get("outlineColour")) or "#ffffff"
        st["outline_width"] = _units(s["outlineThickness"])
    if _num(s.get("opacity")) is not None:
        st["opacity"] = round(s["opacity"] / 255, 3)
    dy = (_units(s.get("positionVerticalOffset")) or 0) * -1  # positive raises the text
    out = []
    for seg in c.get("segments") or []:
        text = str((seg.get("parameters") or {}).get("text", ""))
        for p in seg.get("cells") or []:
            y, x = _point(p)
            if text:
                out.append({"kind": "text", "center": [round(y + dy, 4), x], "text": text, "style": dict(st)})
    return out


def _cosmetic_lines(c):
    st = style_of(c.get("settings") or {})
    st.pop("fill", None)
    st.pop("size", None)
    out = []
    for seg in c.get("segments") or []:
        pts = [_point(p) for p in seg.get("cells") or []]
        if len(pts) >= 2:
            out.append({"kind": "line", "points": pts, "style": dict(st)})
    return out


def outline(cells, n):
    """the closed outlines (corner points [y, x], clockwise) of a set of cell indices"""
    cs = {divmod(i, n) for i in cells}
    nxt = {}
    for r, c in cs:  # each boundary side, directed so the cells lie on its right
        for (dr, dc), a, b in (
            ((-1, 0), (r, c), (r, c + 1)),
            ((0, 1), (r, c + 1), (r + 1, c + 1)),
            ((1, 0), (r + 1, c + 1), (r + 1, c)),
            ((0, -1), (r + 1, c), (r, c)),
        ):
            if (r + dr, c + dc) not in cs:
                nxt.setdefault(a, []).append(b)
    loops = []
    while nxt:
        start = min(nxt)
        pts, p = [start], start
        while True:
            q = nxt[p].pop()
            if not nxt[p]:
                del nxt[p]
            if q == start:
                break
            pts.append(q)
            p = q
        loops.append([[y, x] for y, x in pts])
    return loops


def _cosmetic_cages(c, n):
    s = c.get("settings") or {}
    st = {"dash": True, "color": colour(s.get("colour"))}
    if _num(s.get("opacity")) is not None:
        st["opacity"] = round(s["opacity"] / 255, 3)
    st = {k: v for k, v in st.items() if v is not None}
    out = []
    for seg in c.get("segments") or []:
        cells = [i for i in seg.get("cells") or [] if isinstance(i, int) and 0 <= i < n * n]
        if not cells:
            continue
        out += [{"kind": "polygon", "points": loop, "style": dict(st)} for loop in outline(cells, n)]
        label = (seg.get("parameters") or {}).get("sum")
        if label not in (None, ""):
            r, col = divmod(min(cells), n)
            text_style = {"size": 0.25, **({"color": st["color"]} if "color" in st else {})}
            out.append({"kind": "text", "center": [r + 0.15, col + 0.2], "text": str(label), "style": text_style})
    return out


# -------------------------------------------------------------------------------------------------- the document
SHAPE_TYPES = {"odd", "even", "region", "minimum", "maximum", "quadruple"}


def _rules_of(c, B, givens, solution):
    """one coach constraint -> rules (houses and negatives are made elsewhere)"""
    t, segs, settings = c["type"], c.get("segments") or [], c.get("settings") or {}
    style = style_of(settings, shape=t in SHAPE_TYPES)
    n = B.n
    if t in ("ratio", "difference", "twoCellSum", "greaterLess"):
        return _dots(t, segs, B, style)
    if t in LINE_KINDS:
        return _lines(t, segs, B, settings, style)
    if t == "consecutiveLine":
        return _consecutive(segs, B, style)
    if t in ("arrow", "pillArrow"):
        return _arrows(t, segs, B, style)
    if t == "cage":
        return _cages(segs, B, {k: v for k, v in style.items() if k in ("color", "opacity")})
    if t in ("odd", "even"):
        cells = [i for seg in segs for i in seg.get("cells") or []]
        return [_with_style({"type": "cell", "kind": t, "cells": B.names(cells)}, style)] if cells else []
    if t == "region":
        return [
            _with_style({"type": "region", "kind": "extra", "cells": B.names(seg["cells"])}, style)
            for seg in segs
            if seg.get("cells")
        ]
    if t in ("diagonalPositive", "diagonalNegative"):
        cells = [r * n + (n - 1 - r if t == "diagonalPositive" else r) for r in range(n)]
        return [_with_style({"type": "region", "kind": "diagonal", "cells": B.names(cells)}, style)]
    if t in ("antiKnight", "antiKing"):
        return [{"type": "neighbors", "kind": t.lower()}]
    if t == "quadruple":
        return _quadruples(segs, B, style)
    if t == "sandwich":
        return _sandwiches(
            segs, B, {"color": colour(settings.get("textColour"))} if colour(settings.get("textColour")) else {}
        )
    if t == "littleKiller":
        return _little_killers(
            segs, B, {"color": colour(settings.get("colour"))} if colour(settings.get("colour")) else {}
        )
    if t in ("minimum", "maximum"):
        return _extremes(t, segs, B, style)
    if t == "globalEntropy":
        if n != 9:  # the app's classes are 1-3, 4-6, 7-9 at every size; the format's are thirds of 1..D
            raise NotSupportedError(f"global entropy on a {n}x{n} grid (the app's 1-3 / 4-6 / 7-9 classes)", [t])
        return [{"type": "global_entropy"}]
    if t == "fog":
        return [_fog(segs, B, givens, solution)]
    if t == "nonconsecutive":
        return []  # with the negatives (_negatives)
    raise unsupported([t], "sudoku.coach")


def _decorations(c, n):
    t = c["type"]
    if t == "cosmeticLine":
        return _cosmetic_lines(c)
    if t == "cosmeticShape":
        return _shapes(c)
    if t == "cosmeticText":
        return _texts(c)
    return _cosmetic_cages(c, n)


def _solution(sol, n):
    s = str(sol).strip() if sol not in (None, "") else ""
    if len(s) != n * n or not s.isalnum():
        return None
    out = [int(ch, 36) for ch in s]
    return out if all(1 <= v <= n for v in out) else None


def _meta(m):
    pid = m.get("id")
    meta = {
        "title": (m.get("title") or "").strip() or None,
        "author": (m.get("author") or "").strip() or None,
        "source": "sudoku.coach",
        "id": pid,
        "url": PAGE + pid if pid else None,
        "rules_text": html.unescape(m.get("rules_text") or "").strip() or None,
    }
    return {k: v for k, v in meta.items() if v}


@reads("sudoku.coach")
def to_document(decoded, *, check_solution=True):
    """Decoded sudoku.coach puzzle (decode()) -> pencilmark-puzzle dict (format_version 1).

    Parameters
    ----------
    decoded : dict
        decode()'s result, or anything decode() takes (a payload, a record dict).
    check_solution : bool
        When the record carries the setter's solution, refuse a reading that the solution breaks (ReadingMismatch),
        as the SudokuPad reader does.

    Raises
    ------
    NotSupportedError
        A constraint type with no rule family, rules stated only in the description, a non-numeric clue.
    FormatError
        Malformed data.
    """
    from ..exchange import FORMAT

    d = decode(decoded)
    P, m = d["puzzle"], d.get("meta") or {}
    if m.get("custom_constraints"):
        raise NotSupportedError(
            "sudoku.coach: the setter lists additional custom constraints in the description", ["custom constraints"]
        )
    n = P["gridSize"]
    if not 1 <= n <= 9:
        raise FormatError(f"gridSize {n} is outside 1..9")
    cons = [c for c in P.get("givenConstraints") or [] if isinstance(c, dict)]
    B = _Board(n, cons)
    givens = _givens(P, n)
    solution = _solution(m.get("solution"), n)
    rules = _houses(P, n, B)
    decorations = _cell_fills(P, n, B)
    bad = []
    for c in cons:
        if str(c.get("type", "")).startswith("cosmetic"):
            decorations += _decorations(c, n)
            continue
        try:
            made = _rules_of(c, B, givens, solution)
        except NotSupportedError as e:
            bad.append(e)
            continue
        rules += [r for r in made if "_decoration" not in r]
        decorations += [r["_decoration"] for r in made if "_decoration" in r]
    if bad:  # every constraint that cannot be read, not just the first
        msg = "; ".join(dict.fromkeys(str(e) for e in bad))
        raise NotSupportedError(msg, sorted({x for e in bad for x in e.elements}))
    rules += _negatives(cons, B)
    doc = {"format": FORMAT, "format_version": 1, "meta": _meta(m), "board": {"rows": n, "cols": n}, "digits": n}
    doc["givens"] = givens
    if solution:
        doc["solution"] = solution
    doc["rules"] = rules
    if decorations:
        doc["decorations"] = decorations
    if check_solution and solution:
        _check(doc)
    return doc


def _check(doc):
    """refuse a reading that the setter's solution breaks (sources.contradicts_solution on the engine's JSON)"""
    from ..exchange import to_internal
    from . import contradicts_solution

    if contradicts_solution(to_internal(doc)):
        raise ReadingMismatch(
            "the reading contradicts the setter's embedded solution: some rule was not read as the setter meant"
        )


def read(x, *, fetch=True, check_solution=True):
    """sudoku.coach link / id / payload / record -> pencilmark-puzzle dict (a link or id is fetched: one request)."""
    if isinstance(x, str) and not x.strip().startswith("SCv") and (is_coach_url(x) or "://" not in x):
        if not fetch:
            raise FormatError(f"{x[:80]!r} needs a page request (fetch=True)")
        x = globals()["fetch"](x)
    return to_document(x, check_solution=check_solution)


__all__ = [
    "decode",
    "decode_payload",
    "fetch",
    "to_document",
    "read",
    "is_coach_url",
    "puzzle_id",
    "colour",
    "style_of",
]
