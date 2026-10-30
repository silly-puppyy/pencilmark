"""f-puzzles JSON -> engine Puzzle.
Exact: f-puzzles stores constraints by type.

translate(fp) -> (Puzzle, info) or (None, reason). Supported keys: grid (givens,
custom regions), killercage, thermometer, arrow, whispers, renban, palindrome,
betweenline, difference/ratio/xv (+ "negative" list), odd, even, diagonal+/-,
antiknight, antiking, disjointgroups, nonconsecutive, littlekillersum,
sandwichsum, quadruple, minimum, maximum. Generic 'line'/'cage'/'circle'
(meaning only in the rules text), fog of war, indexers and clones -> unsupported.
"""

import itertools
import re

from .. import model as M

BOX = {4: (2, 2), 5: None, 6: (2, 3), 7: None, 8: (2, 4), 9: (3, 3), 10: (2, 5), 12: (3, 4), 16: (4, 4)}
UNSUPPORTED = ("fogofwar", "foglight", "columnindexer", "rowindexer", "boxindexer", "nabner")
COUNTING_CIRCLES = (
    r"counting circle|digit in a circle.{0,40}(appears|number of)|number in a circle.{0,60}circles|"
    r"(circled|circle) digits?.{0,40}(how many|exactly that many|number of)"
)
DECORATIVE = (
    "text",
    "rectangle",
    "disabledlogic",
    "truecandidatesoptions",
    "successMessage",
    "metaData",
    "cellcolor",
    "title",
    "author",
    "ruleset",
    "solution",
    "size",
    "grid",
    "highlightConflicts",
)


def rc(name, n):
    m = re.fullmatch(r"R(\d+)C(\d+)", name, re.I)
    return int(m.group(1)) - 1, int(m.group(2)) - 1


def normalise(fp):
    """Lexicon pass over elements whose meaning lives in the rules text (returns a shallow copy):
    hidden 'msgcorrect' cages (the success message) are dropped; numeric generic cages become killer cages when
    the text says cages sum (sum constraints without distinctness when it says digits may repeat); free text
    'X' / 'V' / '<' / '>' / '^' / 'v' placed between two adjacent cells become XV clues and inequality signs."""
    fp = dict(fp)
    text = (fp.get("ruleset") or "").lower()
    invisible = lambda c: len(str(c.get("outlineC", ""))) == 9 and str(c["outlineC"]).lower().endswith("00")
    cages = [
        c
        for c in fp.get("cage") or []
        if not str(c.get("value", "")).startswith("msgcor")
        and not (invisible(c) and not str(c.get("value", "")).strip().isdigit())
    ]
    if (
        cages
        and all(str(c.get("value", "")).strip().isdigit() for c in cages)
        and re.search(r"cage[^.]{0,80}(?:sum|add up|total)|killer", text)
    ):
        if re.search(
            r"(?:may|can|could) repeat (?:in|within) (?:a |the )?cages?|digits in cages may repeat|cages? (?:may|can) contain repeat",
            text,
        ):
            fp["_sumcage"] = list(fp.get("_sumcage") or []) + cages
        else:
            fp["killercage"] = list(fp.get("killercage") or []) + cages
        cages = []
    fp["cage"] = cages
    xv, ineq, rest = list(fp.get("xv") or []), list(fp.get("_ineq") or []), []
    xv_text = re.search(r"\bxv\b|sum (?:to|of) (?:5|five)|\bv\b[^.]{0,40}\b5\b|\bx\b[^.]{0,40}\b10\b", text)
    for t in fp.get("text") or []:
        v, cs = str(t.get("value", "")).strip(), t.get("cells") or []
        if len(cs) == 2:
            (r1, c1), (r2, c2) = rc(cs[0], 99), rc(cs[1], 99)
            if abs(r1 - r2) + abs(c1 - c2) == 1:
                a, b = sorted([(r1, c1), (r2, c2)])  # a = left / top
                if v.upper() in ("X", "V") and xv_text:
                    xv.append({"cells": cs, "value": v.upper()})
                    continue
                gt = {">": True, "<": False, "v": True, "∨": True, "^": False, "∧": False, "Λ": False}.get(v)
                if v == "V" and r1 != r2 and not xv_text and re.search(r"inequal|greater|less than|smaller", text):
                    gt = True  # a 'V' between stacked cells: points at the lower digit
                if gt is not None and (v in "<>") == (r1 == r2):
                    ineq.append((a, b) if gt else (b, a))  # (larger, smaller)
                    continue
        rest.append(t)
    fp["xv"], fp["_ineq"], fp["text"] = xv, ineq, rest
    return fp


def translate(fp, line_kinds=None):
    """line_kinds: {colour: kind} reading for generic 'line' entries (see infer_lines)."""
    fp = normalise(fp) if "_ineq" not in fp else fp
    n = fp.get("size", 9)
    ix = lambda name: (lambda r, c: r * n + c)(*rc(name, n))
    used = {}
    for k in UNSUPPORTED:
        if fp.get(k):
            return None, f"unsupported: {k}"
    text0 = (fp.get("ruleset") or "").lower()
    circles_counting = bool(fp.get("circle")) and bool(re.search(COUNTING_CIRCLES, text0))
    for k in ("cage", "circle"):
        if fp.get(k) and not (k == "circle" and circles_counting):
            return None, f"unsupported: generic {k} (meaning in rules text)"
    if fp.get("line") and line_kinds is None:
        return None, "unsupported: generic line (meaning in rules text)"
    unknown = [
        k
        for k, v in fp.items()
        if v
        and not k.startswith("_")
        and k not in DECORATIVE
        and k
        not in (
            "killercage",
            "thermometer",
            "arrow",
            "whispers",
            "renban",
            "palindrome",
            "betweenline",
            "difference",
            "ratio",
            "xv",
            "negative",
            "odd",
            "even",
            "diagonal+",
            "diagonal-",
            "antiknight",
            "antiking",
            "disjointgroups",
            "nonconsecutive",
            "littlekillersum",
            "sandwichsum",
            "quadruple",
            "minimum",
            "maximum",
            "line",
            "regionsumline",
            "clone",
            "entropicline",
            "modularline",
            "zipperline",
            "circle",
            "extraregion",
            "doublearrow",
            "lockout",
        )
    ]
    if unknown:
        return None, "unsupported: " + ", ".join(unknown)
    p = M.Puzzle(D=n, coords=M._grid_coords(n))
    for r in range(n):
        p.groups.append(M.Group(f"r{r + 1}", tuple(r * n + c for c in range(n)), "row", True))
    for c in range(n):
        p.groups.append(M.Group(f"c{c + 1}", tuple(r * n + c for r in range(n)), "col", True))
    grid = fp.get("grid") or [[{} for _ in range(n)] for _ in range(n)]
    regions = {}
    custom = any("region" in (grid[r][c] or {}) for r in range(n) for c in range(n))
    for r in range(n):
        for c in range(n):
            cell = grid[r][c] or {}
            if "region" in cell:  # explicit (None / -1 = cell in no region)
                reg = cell.get("region")
            else:  # f-puzzles omits the key for default-box cells
                if BOX.get(n) is None:
                    return None, f"no default regions for size {n}"
                bh, bw = BOX[n]
                reg = (r // bh) * (n // bw) + c // bw
            if reg is not None and reg >= 0:
                regions.setdefault(reg, []).append(r * n + c)
            if cell.get("given") and cell.get("value"):
                p.givens[r * n + c] = int(cell["value"])
    for k, cells in sorted(regions.items()):
        p.groups.append(M.Group(f"b{k}", tuple(cells), "box" if not custom else "region", len(cells) == n))
    if fp.get("diagonal-"):
        p.groups.append(M.Group("d1", tuple(i * n + i for i in range(n)), "diag", True))
    if fp.get("diagonal+"):
        p.groups.append(M.Group("d2", tuple(i * n + (n - 1 - i) for i in range(n)), "diag", True))
    if fp.get("disjointgroups") and BOX.get(n):
        bh, bw = BOX[n]
        for i in range(bh):
            for j in range(bw):
                cells = tuple(r * n + c for r in range(n) for c in range(n) if r % bh == i and c % bw == j)
                p.groups.append(M.Group(f"dj{i}{j}", cells, "extra", True))
    text = (fp.get("ruleset") or "").lower()
    knight = fp.get("antiknight") or bool(re.search(r"anti[- ]?knight|knight'?s move", text))
    king = fp.get("antiking") or bool(re.search(r"anti[- ]?king|king'?s move", text))
    if fp.get("nonconsecutive") is None and re.search(r"non[- ]?consecutive", text) and not fp.get("difference"):
        fp = dict(fp, nonconsecutive=True)
    used.update({k: True for k, v in (("antiknight", knight), ("antiking", king)) if v})
    steps = ([(1, 2), (2, 1), (2, -1), (1, -2)] if knight else []) + ([(1, 1), (1, -1)] if king else [])
    for r in range(n):
        for c in range(n):
            for dr, dc in steps:
                if 0 <= r + dr < n and 0 <= c + dc < n:
                    p.relations.append(("neq", r * n + c, (r + dr) * n + c + dc))
    for k, cg in enumerate(fp.get("killercage") or []):
        cells = tuple(sorted(ix(x) for x in cg["cells"]))
        tot = int(cg["value"]) if str(cg.get("value", "")).strip().isdigit() else None
        p.groups.append(M.Group(f"k{k}", cells, "cage", len(cells) == n, tot))
    for k, er in enumerate(
        fp.get("extraregion") or []
    ):  # extra regions (asterisk, windoku, centre dot ...): no repeats
        cells = tuple(sorted(ix(x) for x in er.get("cells", [])))
        if len(cells) >= 2:
            p.groups.append(M.Group(f"x{k}", cells, "region", len(cells) == n))
            used["extraregion"] = used.get("extraregion", 0) + 1
    for item in fp.get("doublearrow") or []:  # the two end circles sum to the digits between them
        for line in item.get("lines", []):
            cs = [ix(x) for x in line]
            if len(cs) >= 3 and cs[0] != cs[-1]:
                p.constraints.append({"type": "equal_sum", "segments": [[cs[0], cs[-1]], cs[1:-1]]})
                used["doublearrow"] = used.get("doublearrow", 0) + 1
    lk = re.search(r"lockout.{0,200}?(?:at least|by|difference of) (\d)", (fp.get("ruleset") or "").lower(), re.S)
    for item in fp.get("lockout") or []:  # ends differ by >= k; middle digits lie outside the ends' range
        k_ = int(lk.group(1)) if lk else int(item.get("value") or 4)
        for line in item.get("lines", []):
            cs = [ix(x) for x in line]
            if len(cs) < 2 or cs[0] == cs[-1]:
                continue
            a, b = cs[0], cs[-1]
            p.relations.append(("diffge", a, b, k_))
            for c in cs[1:-1]:
                allowed = [
                    (x, y, z)
                    for x in range(1, n + 1)
                    for y in range(1, n + 1)
                    if abs(x - y) >= k_
                    for z in range(1, n + 1)
                    if z < min(x, y) or z > max(x, y)
                ]
                p.constraints.append({"type": "table", "cells": [a, b, c], "allowed": allowed})
            used["lockout"] = used.get("lockout", 0) + 1
    for cg in fp.get("_sumcage") or []:
        p.constraints.append({"type": "sum", "cells": sorted(ix(x) for x in cg["cells"]), "total": int(cg["value"])})
        used["sumcage"] = used.get("sumcage", 0) + 1
    for big, small in fp.get("_ineq") or []:
        p.relations.append(("lt", small[0] * n + small[1], big[0] * n + big[1]))
        used["inequality"] = used.get("inequality", 0) + 1
    for item in fp.get("clone") or []:  # f-puzzles: {"cells": [...], "cloneCells": [...]} in matching order
        a, b = [ix(x) for x in item.get("cells", [])], [ix(x) for x in item.get("cloneCells", [])]
        if a and len(a) == len(b):
            p.constraints.append({"type": "clone", "regions": [a, b]})
            used["clone"] = used.get("clone", 0) + 1
    if circles_counting:
        cells = sorted({ix(x) for it in fp.get("circle") or [] for x in it.get("cells", [])})
        p.constraints.append({"type": "counting_circles", "cells": cells})
        used["counting_circles"] = True
    for kind, key in (
        ("thermo", "thermometer"),
        ("whisper", "whispers"),
        ("renban", "renban"),
        ("palindrome", "palindrome"),
        ("region_sum", "regionsumline"),
        ("entropic", "entropicline"),
        ("modular", "modularline"),
        ("zipper", "zipperline"),
    ):
        for item in fp.get(key) or []:
            for line in item.get("lines", []):
                con = {"type": "line", "kind": kind, "cells": [ix(x) for x in line]}
                if kind == "whisper" and item.get("value"):
                    con["k"] = int(item["value"])
                p.constraints.append(con)
                used[key] = used.get(key, 0) + 1
    for item in fp.get("line") or []:
        kind = (line_kinds or {}).get(_colour(item))
        for line in item.get("lines", []):
            cells = [ix(x) for x in line]
            if kind == "between":
                p.constraints.append({"type": "between", "cells": cells})
            elif kind:
                p.constraints.append({"type": "line", "kind": kind, "cells": cells})
    for item in fp.get("betweenline") or []:
        for line in item.get("lines", []):
            p.constraints.append({"type": "between", "cells": [ix(x) for x in line]})
    for item in fp.get("arrow") or []:
        circle = sorted(ix(x) for x in item["cells"])  # multi-cell circles (pills) read in reading order
        for line in item.get("lines", []):
            lc = [ix(x) for x in line if ix(x) not in circle]
            p.constraints.append({"type": "arrow", "circle": circle, "line": lc})
    neg = set(fp.get("negative") or [])
    if fp.get("ruleset"):  # 'ALL POSSIBLE X AND V ARE GIVEN' stated only in the text
        from . import _sp_translate as ST

        tn = ST.negative_markers(fp["ruleset"])
        if tn & {"x", "v"} and fp.get("xv"):
            neg.add("xv")
        if "white" in tn and fp.get("difference"):
            neg.add("difference")
        if "black" in tn and fp.get("ratio"):
            neg.add("ratio")
    marked = {"difference": set(), "ratio": set(), "xv": set()}
    for d in fp.get("difference") or []:
        a, b = sorted(ix(x) for x in d["cells"])
        p.relations.append(("diff", a, b, int(d.get("value") or 1)))
        marked["difference"].add((a, b))
    for d in fp.get("ratio") or []:
        a, b = sorted(ix(x) for x in d["cells"])
        p.relations.append(("ratio", a, b, int(d.get("value") or 2)))
        marked["ratio"].add((a, b))
    for d in fp.get("xv") or []:
        a, b = sorted(ix(x) for x in d["cells"])
        p.relations.append(("sum", a, b, 10 if str(d.get("value")).upper() == "X" else 5))
        marked["xv"].add((a, b))
    allm = set().union(*marked.values())
    for x in range(n * n):
        r, c = divmod(x, n)
        for y in ([x + 1] if c + 1 < n else []) + ([x + n] if r + 1 < n else []):
            # f-puzzles' global nonconsecutive skips dotted pairs (kropki 'all dots given' setups); applying it to
            # white-dot pairs made them contradictory (18 of 20 such zero-solution LMD puzzles verify with this)
            if fp.get("nonconsecutive") and (x, y) not in allm:
                p.relations.append(("nonconsec", x, y))
            if (x, y) in allm:
                continue
            if "difference" in neg:
                p.relations.append(("notdiff", x, y, 1))
            if "ratio" in neg:
                p.relations.append(("notratio", x, y, 2))
            if "xv" in neg:
                p.relations += [("notsum", x, y, 10), ("notsum", x, y, 5)]
    odd = sum(1 << (v - 1) for v in range(1, n + 1, 2))
    for o in fp.get("odd") or []:
        p.domains[ix(o["cell"])] &= odd
    for e in fp.get("even") or []:
        p.domains[ix(e["cell"])] &= p.full & ~odd
    for key, rel in (("maximum", "lt"), ("minimum", "gt")):
        for m in fp.get(key) or []:
            x = ix(m["cell"])
            r, c = divmod(x, n)
            for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= rr < n and 0 <= cc < n:
                    y = rr * n + cc
                    p.relations.append(("lt", y, x) if key == "maximum" else ("lt", x, y))
    for lk in fp.get("littlekillersum") or []:
        if not str(lk.get("value", "")).strip().isdigit():
            continue
        p.constraints.append(
            {"type": "little_killer", "cells": [ix(x) for x in lk["cells"]], "total": int(lk["value"])}
        )
    for sw in fp.get("sandwichsum") or []:
        if not str(sw.get("value", "")).strip().isdigit():
            continue
        r, c = rc(sw["cell"], n)
        if r < 0 or r >= n:  # column clue (above or below)
            cells = [rr * n + c for rr in (range(n) if r < 0 else range(n - 1, -1, -1))]
        else:  # row clue (left or right)
            cells = [r * n + cc for cc in (range(n) if c < 0 else range(n - 1, -1, -1))]
        p.constraints.append({"type": "sandwich", "cells": cells, "total": int(sw["value"])})
    for q in fp.get("quadruple") or []:
        cells = [ix(x) for x in q["cells"]]
        if not all(str(v).strip().isdigit() for v in q.get("values", [])):
            return None, "unsupported: quadruple with non-digit values"
        need = [int(v) for v in q.get("values", [])]
        from .. import puzzle_json as PJ

        PJ.add_named(p, {"type": "quadruple", "cells": cells, "digits": need})
    for k, v in fp.items():
        if v and k not in DECORATIVE and k != "negative" and not k.startswith("_"):
            used.setdefault(k, len(v) if isinstance(v, list) else True)
    return p, used


def solution_of(fp):
    s = fp.get("solution")
    if not s:
        return None
    s = [int(x) for x in s if str(x).strip().isdigit()]
    return s if len(s) == fp.get("size", 9) ** 2 else None


def decode_fpuz(payload):
    """'fpuzzles...' / 'fpuz...' payload -> f-puzzles dict (handles URL-encoding and
    lz-string's base64 vs URI-safe alphabets)."""
    import json
    import urllib.parse

    import lzstring

    L = lzstring.LZString()
    s = payload[8:] if payload.startswith("fpuzzles") else payload[4:] if payload.startswith("fpuz") else payload
    s = urllib.parse.unquote(s)
    for f in (L.decompressFromBase64, L.decompressFromEncodedURIComponent):
        for cand in (s, s.replace(" ", "+")):
            try:
                txt = f(cand)
                if txt:
                    return json.loads(txt)
            except Exception:
                continue
    return None


LINE_WORDS = [
    ("whisper", r"german whisper|differ by (at least )?5|at least 5"),
    ("dutch_whisper", r"dutch whisper|differ by (at least )?4|at least 4"),
    ("renban", r"renban|consecutive.{0,30}any order|set of consecutive"),
    ("region_sum", r"region sum|same sum in each|each box.{0,40}sum"),
    ("palindrome", r"palindrome|read the same"),
    ("parity", r"parity|alternate between odd and even|odd and even"),
    ("entropic", r"entropic|low.{0,10}middle.{0,10}high"),
    ("modular", r"modular|different mod|mod(ulo)? 3"),
    ("between", r"between line|strictly between|circles at"),
    ("zipper", r"zipper|equidistant"),
    ("slow_thermo", r"slow thermo"),
    ("kropki_chain", r"\bnope\b"),
]


def _colour(item):
    return str(item.get("outlineC") or item.get("color") or "?").lower()


def infer_lines(fp, node_limit=2_000_000, max_combos=60):
    """Generic f-puzzles lines: try line rules per colour, keyword-ranked by the rules
    text; keep the reading with a unique solution (matching the embedded one).
    -> (Puzzle, info) or (None, reason)."""
    from .. import cbackend as CB  # noqa: F401

    text = (fp.get("ruleset") or "").lower()
    colours = sorted({_colour(it) for it in fp.get("line") or []})
    hits = [k for k, rx in LINE_WORDS if re.search(rx, text)]
    cands = hits + [k for k, _ in LINE_WORDS if k not in hits and k != "kropki_chain"]
    emb = solution_of(fp)
    tried = 0
    for combo in itertools.product(cands, repeat=len(colours)):
        if len(colours) > 1 and len(set(combo)) < len(colours) and len(hits) >= len(colours):
            continue
        tried += 1
        if tried > max_combos:
            break
        reading = dict(zip(colours, combo))
        p, info = translate(fp, reading)
        if p is None:
            return None, info
        p.finalize()
        sols = _verified_solutions(p, limit=2, node_limit=node_limit)
        if len(sols) == 1 and (emb is None or list(sols[0]) == emb):
            info = dict(info)
            info["line_reading"] = reading
            info.pop("line", None)
            for k in combo:
                info[k] = True
            return p, info
    return None, "no line reading with a unique solution"


def _verified_solutions(p, **kw):
    from .. import cpsat_verify

    return cpsat_verify.verified_solutions(p, **kw)
