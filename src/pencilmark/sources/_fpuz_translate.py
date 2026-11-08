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
import logging
import re

from .. import model as M

_log = logging.getLogger(__name__)

BOX = {4: (2, 2), 5: None, 6: (2, 3), 7: None, 8: (2, 4), 9: (3, 3), 10: (2, 5), 12: (3, 4), 16: (4, 4)}
UNSUPPORTED = ("columnindexer", "rowindexer", "boxindexer", "nabner")
COUNTING_CIRCLES = (
    r"counting circle|digit in a circle.{0,40}(appears|number of)|number in a circle.{0,60}circles|"
    r"(circled|circle) digits?.{0,40}(how many|exactly that many|number of)|"
    r"number of times (?:a )?digits? appears? in (?:a )?circles?|"
    r"(?:digit|number) (?:in|inside) a circle[^.]{0,40}how many circles"
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


# outside clue families written as plain text outside the grid (f-puzzles 'text'), told apart by the rules text
OUTSIDE_TEXT = (
    ("sandwichsum", r"sandwich|between (?:the )?1 and (?:the )?9"),
    ("_xsum", r"\bx-?sums?\b|sum of the first x\b"),
    ("_skyscraper", r"skyscraper"),
)


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
    val = lambda c: str(c.get("value") or "").strip().lower()
    corner = r"(?:cages?|regions?)[^.]{0,40}(?:sum|add up|total|multiply)[^.]{0,30}(?:number|clue|total) (?:in|at) the (?:top[- ]left )?corner"
    blank_ok = bool(
        re.search(
            corner + r"|(?:digits|numbers) in (?:a |the )?cages? (?:do not|don't|cannot|can't|may not) repeat", text
        )
    )
    if (  # factor cages: the digits multiply to the clue (a plain cage: no repeats)
        cages
        and all(val(c).isdigit() for c in cages)
        and re.search(r"(?:cages?|regions?)[^.]{0,40}(?:multiply to|product (?:of|is|equals))", text)
        and not re.search(r"cage[^.]{0,80}(?:sum|add up)", text)
    ):
        fp["_prodcage"], cages = cages, []
    if (  # x + k cages: one unknown x common to all cages
        cages
        and all(re.fullmatch(r"x(?: ?\+ ?\d+)?", val(c)) for c in cages)
        and re.search(r"\bx is the same (?:for|in) (?:all|every|each) cages?", text)
    ):
        fp["_xcage"], cages = cages, []
    if (
        cages
        and all(val(c).isdigit() or (not val(c) and blank_ok) for c in cages)
        and re.search(r"(?:cage|region)[^.]{0,80}(?:sum|add up|total)|killer", text)
        and not re.search(r"(?:cages?|regions?)[^.]{0,80}sum to (?:either )?\d", text)
        or cages
        and blank_ok
        and all(not val(c) for c in cages)
    ):
        if re.search(
            r"(?:may|can|could) repeat (?:in|within) (?:a |the )?(?:cages?|regions?)|digits in cages may repeat|cages? (?:may|can) contain repeat",
            text,
        ):
            fp["_sumcage"] = list(fp.get("_sumcage") or []) + cages
        else:
            fp["killercage"] = list(fp.get("killercage") or []) + cages
        cages = []
    fp["cage"] = cages
    xv, ineq, rest = list(fp.get("xv") or []), list(fp.get("_ineq") or []), []
    xv_text = re.search(r"\bxv\b|sum (?:to|of) (?:5|five)|\bv\b[^.]{0,40}\b5\b|\bx\b[^.]{0,40}\b10\b", text)
    n = int(fp.get("size") or 9)
    families = [k for k, pat in OUTSIDE_TEXT if re.search(pat, text)]
    if not families and fp.get("_page_rules"):  # the page's wording names it when the payload's own text does not
        families = [k for k, pat in OUTSIDE_TEXT if re.search(pat, fp["_page_rules"].lower())]
    outside = families[0] if len(families) == 1 else None  # numbers outside the grid mean the one clue family named
    for t in fp.get("text") or []:
        if t.get("fromConstraint"):  # the drawing of a constraint listed under its own key (an X-sum's number)
            continue
        v, cs = str(t.get("value", "")).strip(), t.get("cells") or []
        if len(cs) == 1 and outside and v.isdigit():
            r, c = rc(cs[0], 99)
            if (r in (-1, n)) != (c in (-1, n)) and -1 <= r <= n and -1 <= c <= n:
                fp[outside] = list(fp.get(outside) or []) + [{"cell": cs[0], "value": v}]
                continue
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


def translate(fp, line_kinds=None, join=True):
    """line_kinds: {colour: kind} reading for generic 'line' entries (see infer_lines). join: same-colour segments of a
    set rule (renban, line total) that share a cell are one line (info "_joined" when that merged any)."""

    # fog light written as generic cages (as SudokuPad imports them; often drawn invisible, which normalize drops): a
    # FOGLIGHT / "foglight: ..." cage's cells are lit, a one-cell FOW cage lights its 3x3 like a fogofwar cell
    def fog_kind(c):
        return str(c.get("value") or "").strip().lower().split(":")[0]

    fog_cages = [c for c in fp.get("cage") or [] if fog_kind(c) in ("foglight", "fow")]
    if fog_cages:
        fp = dict(fp, cage=[c for c in fp["cage"] if c not in fog_cages])
        for key, kind in (("foglight", "foglight"), ("fogofwar", "fow")):
            fp[key] = list(fp.get(key) or []) + [
                x for c in fog_cages if fog_kind(c) == kind for x in c.get("cells") or []
            ]
    fp = normalise(fp) if "_ineq" not in fp else fp
    n = fp.get("size", 9)
    ix = lambda name: (lambda r, c: r * n + c)(*rc(name, n))
    used = {}
    for k in UNSUPPORTED:
        if fp.get(k):
            return None, f"unsupported: {k}"
    from . import _sp_translate as ST

    if fp.get("ruleset"):  # "king’s move": the patterns spell apostrophes plainly
        fp = dict(fp, ruleset=fp["ruleset"].translate(ST.TYPO_QUOTES))
    text0 = (fp.get("ruleset") or "").lower()

    fog = None
    if fp.get("foglight") or fp.get("fogofwar"):  # fog of war: foglight cells lit; each fogofwar cell lights its 3x3
        lit = set()
        for c in fp.get("foglight") or []:
            lit.add(rc(c, n))
        for c in fp.get("fogofwar") or []:
            r0, c0 = rc(c, n)
            lit |= {(r0 + a, c0 + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if 0 <= r0 + a < n and 0 <= c0 + b < n}
        fog = {"lit": [f"r{r + 1}c{c + 1}" for r, c in sorted(lit) if 0 <= r < n and 0 <= c < n]}
    refused = [
        u
        for u in ST.unmodelled_rules(text0)
        if not (u == "rule 'equality cage'" and ST.EQUALITY_TEXT.search(text0)) and not (u == "rule 'fog'" and fog)
    ]
    refused += [x for x in [ST.chess_other(text0.lower())] if x]  # a knight / king move rule we do not model
    outside_texts = []  # numbers left outside the grid: clues for the SudokuPad reader's outside-clue reading
    for t in fp.get("text") or []:
        cs = t.get("cells") or []
        if len(cs) == 1 and re.search(r"\d", str(t.get("value", ""))) and not t.get("fromConstraint"):
            r, c = rc(cs[0], 99)
            if r in (-1, n) or c in (-1, n):
                outside_texts.append({"center": [r + 0.5, c + 0.5], "text": str(t["value"]).strip()})
    clones = None
    if ST.CLONE_TEXT.search(text0) and not fp.get("clone"):  # clones drawn as colored cells
        colour_of = {
            (r, c): str(cell["c"]).lower()
            for r, row in enumerate(fp.get("grid") or [])
            for c, cell in enumerate(row)
            if isinstance(cell, dict) and cell.get("c")
        }
        clones = ST.clone_groups(colour_of) if colour_of else None
        if not clones and colour_of:  # clones in different colors: one class
            clones = ST.clone_groups(dict.fromkeys(colour_of, "any"))
        if clones:
            refused = [r_ for r_ in refused if r_ != "rule 'clone'"]
    if refused:
        return None, "unsupported: " + ", ".join(refused)
    circles_counting = bool(fp.get("circle")) and bool(re.search(COUNTING_CIRCLES, text0))
    if fp.get("circle") and not circles_counting:  # circles with a meaning in the text: decorative / quads / pair sums
        fp, circle_rules = _text_circles(fp, text0, n)
    else:
        circle_rules = []
    shape_clues = not circles_counting and _shape_cells(fp, n) is not None  # single-cell circles / squares: shapes
    for k in ("cage", "circle"):
        if fp.get(k) and not (k == "circle" and (circles_counting or shape_clues)):
            return None, f"unsupported: generic {k} (meaning in rules text)"
    if fp.get("line") and line_kinds is None:
        line_kinds = text_line_reading(fp)
        if line_kinds is None:
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
            "xsum",
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
            "foglight",  # fog of war: read above (p.fog)
            "fogofwar",
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
    knight = fp.get("antiknight") or ST.chess_rule("knight", text)  # from marked cells only: text_cell_rules
    king = fp.get("antiking") or ST.chess_rule("king", text)
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
    ):  # extra regions (asterisk, windoku, center dot ...): no repeats
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
            p.constraints.append({"type": "line", "kind": "lockout", "cells": cs, "k": k_})  # compiled by finalize
            used["lockout"] = used.get("lockout", 0) + 1
    for cg in fp.get("_sumcage") or []:
        if str(cg.get("value") or "").strip().isdigit():  # a blank cage that may repeat: no constraint
            p.constraints.append(
                {"type": "sum", "cells": sorted(ix(x) for x in cg["cells"]), "total": int(cg["value"])}
            )
            used["sumcage"] = used.get("sumcage", 0) + 1
    if fp.get("_prodcage") or fp.get("_xcage"):
        from .. import puzzle_json as PJ

        name = lambda x: "r{}c{}".format(*(v + 1 for v in rc(x, n)))
    for k, cg in enumerate(fp.get("_prodcage") or []):
        cells = tuple(sorted(ix(x) for x in cg["cells"]))
        p.groups.append(M.Group(f"p{k}", cells, "cage", len(cells) == n))
        PJ.add_named(p, {"type": "custom", "cells": {"K": [name(x) for x in cg["cells"]]},
                         "holds": f"product(K) == {int(cg['value'])}", "label": "Product cage"})  # fmt: skip
        used["product_cage"] = used.get("product_cage", 0) + 1
    if fp.get("_xcage"):  # x + k cages: sum(cage) - k is the same for every cage
        xs = fp["_xcage"]
        offs = [int(re.sub(r"\D", "", str(cg["value"])) or 0) for cg in xs]
        span = lambda m: (m * (m + 1) // 2, m * (2 * n - m + 1) // 2)  # least / greatest sum of m distinct digits
        lo = max(span(len(cg["cells"]))[0] - o for cg, o in zip(xs, offs))
        hi = min(span(len(cg["cells"]))[1] - o for cg, o in zip(xs, offs))
        x_ = lo if lo == hi else None  # the cage sizes force x: the totals follow (exact, and fast for the search)
        for k, (cg, o) in enumerate(zip(xs, offs)):
            cells = tuple(sorted(ix(x) for x in cg["cells"]))
            p.groups.append(M.Group(f"xc{k}", cells, "cage", len(cells) == n, None if x_ is None else x_ + o))
        PJ.add_named(p, {"type": "custom", "cells": {"K": [[name(x) for x in cg["cells"]] for cg in xs]},
                         "holds": f"let O = [{', '.join(map(str, offs))}]; count_distinct(sum(K[i]) - O[i] for i in {{1..{len(xs)}}}) == 1",
                         "label": "Cage sums x + k"})  # fmt: skip
        used["x_cage"] = 1
    for big, small in fp.get("_ineq") or []:
        p.relations.append(("lt", small[0] * n + small[1], big[0] * n + big[1]))
        used["inequality"] = used.get("inequality", 0) + 1
    for comps in clones or []:  # clones drawn as colored cells (clone_groups)
        p.constraints.append({"type": "clone", "regions": [[r * n + c for r, c in comp] for comp in comps]})
        used["clone"] = used.get("clone", 0) + 1
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
    linesum_parts = {}
    for item in fp.get("line") or []:
        kind = (line_kinds or {}).get(_colour(item))
        for line in item.get("lines", []):
            cells = [ix(x) for x in line]
            if kind == "ignore":
                continue
            if kind and re.fullmatch(r"whisper\d", kind):
                p.constraints.append({"type": "line", "kind": "whisper", "cells": cells, "k": int(kind[-1])})
                continue
            if kind and kind.startswith("linesum"):
                linesum_parts.setdefault(kind, []).append(cells)  # joined below: one drawn line may be several segments
                continue
            if kind == "between":
                p.constraints.append({"type": "between", "cells": cells})
            elif kind in ST.LINE_CUSTOM or kind in ("same_parity", "consecutive_line", "shifter"):
                ST.custom_line(p, kind, cells)
            elif kind == "renban":
                linesum_parts.setdefault(kind, []).append(cells)  # a set rule: touching segments are one line
            elif kind:
                p.constraints.append({"type": "line", "kind": kind, "cells": cells})
    for (
        kind,
        parts,
    ) in linesum_parts.items():  # set rules (renban, line totals): segments meeting at a cell are one line
        groups = []
        for cells in parts:
            hit = [g for g in groups if g & set(cells)] if join else []
            merged = set(cells).union(*hit) if hit else set(cells)
            groups = [g for g in groups if g not in hit] + [merged]
        if len(groups) < len(parts):
            used["_joined"] = True
        for g in groups:
            if kind == "renban":
                # a line needs its cells in path order: a lone segment keeps its own, joined ones are walked as one
                # path through touching cells; a branching set that no path covers is a consecutive set (written
                # out it is refused as not a line, never an invalid line)
                own = next((list(c) for c in parts if set(c) == g and len(c) == len(g)), None)
                path = own or _path_through(g, n)
                if path:
                    p.constraints.append({"type": "line", "kind": "renban", "cells": path})
                else:
                    p.constraints.append({"type": "set", "kind": "consecutive", "cells": sorted(g)})
            else:
                ST.custom_line(p, kind, sorted(g))
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
        if fp.get("xv"):  # only the letters the text names ("all Vs are given; not all Xs are given": V only)
            neg |= tn & {"x", "v"}
        white_shapes = any(
            ST.color_name(it.get("baseC") or "") == "white" for k in ("circle", "rectangle") for it in fp.get(k) or []
        )
        if "white" in tn and (fp.get("difference") or (circle_rules and not white_shapes)):
            neg.add("difference")  # all white dots given, none drawn beside the colored dots read: no consecutive pair
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
    allm = set().union(*marked.values()) | {
        tuple(sorted(ix(x) for x in cs)) for _, cs, _ in circle_rules if len(cs) == 2
    }
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
            if "xv" in neg or "x" in neg:  # f-puzzles' own negative "xv" covers both letters
                p.relations.append(("notsum", x, y, 10))
            if "xv" in neg or "v" in neg:
                p.relations.append(("notsum", x, y, 5))
    odd = sum(1 << (v - 1) for v in range(1, n + 1, 2))
    for key, mask in (("odd", odd), ("even", p.full & ~odd)):  # kept as cell rules, not as given candidates
        cells = [ix(o["cell"]) for o in fp.get(key) or []]
        if cells:
            ST._cell_clue(p, {"type": "parity", "parity": key}, cells, mask)
    for key, rel in (("maximum", "lt"), ("minimum", "gt")):
        same = {ix(m["cell"]) for m in fp.get(key) or []}  # fortress: two gray cells side by side are not compared
        for m in fp.get(key) or []:
            x = ix(m["cell"])
            r, c = divmod(x, n)
            for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= rr < n and 0 <= cc < n and rr * n + cc not in same:
                    y = rr * n + cc
                    p.relations.append(("lt", y, x) if key == "maximum" else ("lt", x, y))
    for lk in fp.get("littlekillersum") or []:
        if not str(lk.get("value", "")).strip().isdigit():
            continue
        p.constraints.append(
            {"type": "little_killer", "cells": [ix(x) for x in lk["cells"]], "total": int(lk["value"])}
        )
    for key, typ, field in (("sandwichsum", "sandwich", "total"), ("_xsum", "xsum", "total"), ("xsum", "xsum", "total"),
                            ("_skyscraper", "skyscraper", "count")):  # fmt: skip
        for sw in fp.get(key) or []:
            if not str(sw.get("value", "")).strip().isdigit():
                continue
            r, c = rc(sw["cell"], n)
            if r < 0 or r >= n:  # column clue (above or below), read from the clue inwards
                cells = [rr * n + c for rr in (range(n) if r < 0 else range(n - 1, -1, -1))]
            else:  # row clue (left or right)
                cells = [r * n + cc for cc in (range(n) if c < 0 else range(n - 1, -1, -1))]
            p.constraints.append({"type": typ, "cells": cells, field: int(sw["value"])})
    for kind, cs, ds in circle_rules:
        from .. import puzzle_json as PJ

        cells = [ix(x) for x in cs]
        if kind == "quadruple":
            PJ.add_named(p, {"type": "quadruple", "cells": cells, "digits": ds})
        elif kind == "anti_quadruple":
            names = [f"r{rc(x, n)[0] + 1}c{rc(x, n)[1] + 1}" for x in cs]
            PJ.add_named(p, {"type": "custom", "cells": {"Q": names}, "label": "Anti-quadruple",
                             "holds": " and ".join(f"all(x != {d} for x in Q)" for d in ds)})  # fmt: skip
        else:  # pair sums, colored dots (sum / diff / ratio)
            p.relations.append(("sum" if kind == "pair_sum" else kind, min(cells), max(cells), ds[0]))
        used[kind] = used.get(kind, 0) + 1
    pair_cells = {frozenset(ix(x) for x in cs) for kind, cs, _ in circle_rules if kind == "pair_sum"}
    if pair_cells and re.search(
        r"all (?:possible )?(?:\w+ )?circles are (?:given|shown)", text0 + " " + (fp.get("_page_rules") or "").lower()
    ):
        k_ = next(ds[0] for kind, _, ds in circle_rules if kind == "pair_sum")
        for x in range(n * n):  # the negative: no other orthogonal pair has that sum
            for y in ([x + 1] if (x + 1) % n else []) + ([x + n] if x + n < n * n else []):
                if frozenset((x, y)) not in pair_cells:
                    p.relations.append(("notsum", x, y, k_))
    if shape_clues and (fp.get("circle") or re.search(r"\bsquares?\b", text0)):
        # one-cell circles and squares: the SudokuPad reader's shape clues (parity, digit sets by shape / color)
        from collections import Counter

        shapes = _shape_cells(fp, n)
        u = Counter()
        ST.parity_shapes({"underlays": shapes}, n, p, fp.get("ruleset") or "", u, lambda rc_: rc_[0] * n + rc_[1],
                         lambda rc_: 0 <= rc_[0] < n and 0 <= rc_[1] < n)  # fmt: skip
        if sum(u.values()) < len(shapes):
            return None, "unsupported: generic circle (meaning in rules text)"
        used.update({k: v for k, v in u.items() if v})
    coloured = [{"center": [r_ + 0.5, c_ + 0.5], "width": 1.0, "height": 1.0, "backgroundColor": cell["c"], "_cell": True}
                for r_, row in enumerate(fp.get("grid") or []) for c_, cell in enumerate(row or [])
                if isinstance(cell, dict) and cell.get("c") and not clones]  # fmt: skip
    if coloured and re.search(r"\bcells?\b[^.]{0,40}\b(?:odd|even|greater|less|larger|smaller)\b", text0):
        # colored cells with a meaning in the text ("red cells are greater than 5"): the shape-clue reader
        from collections import Counter

        u = Counter()
        ST.parity_shapes({"underlays": coloured}, n, p, fp.get("ruleset") or "", u, lambda rc_: rc_[0] * n + rc_[1],
                         lambda rc_: 0 <= rc_[0] < n and 0 <= rc_[1] < n)  # fmt: skip
        used.update({k: v for k, v in u.items() if v})
    from collections import defaultdict

    colour_cells = defaultdict(list)  # rules on caged / colored cells stated in the text
    for r_, row in enumerate(fp.get("grid") or []):
        for c_, cell in enumerate(row or []):
            if isinstance(cell, dict) and cell.get("c"):
                colour_cells[ST.color_name(cell["c"])].append(r_ * n + c_)
    if ST.EQUALITY_TEXT.search(text0):
        used["equality_cage"] = ST.equality_cages(p, n)
    unresolved = ST.text_cell_rules(p, n, fp.get("ruleset") or "", colour_cells, used)
    if unresolved:
        return None, "unsupported: " + ", ".join(unresolved)
    # text-only whole-grid rules, after the cages (some read them): custom ones, then global entropy / Dutch flat mates
    custom = ST.global_custom(n, p, fp.get("ruleset")) or ST.global_custom(n, p, fp.get("_page_rules"))
    used.update(dict.fromkeys(custom, True))
    from collections import Counter

    gu = Counter()
    ST.global_rules(n, p, " ".join(x for x in (fp.get("ruleset"), fp.get("_page_rules")) if x), gu)
    used.update({k: v for k, v in gu.items() if v})
    if outside_texts:  # read like SudokuPad outside clues, from the payload's wording, else the page's
        from collections import Counter

        inside = lambda rc_: 0 <= rc_[0] < n and 0 <= rc_[1] < n
        for words in (fp.get("ruleset"), fp.get("_page_rules")):
            if not words:
                continue
            q = M.Puzzle(D=n, coords=M._grid_coords(n))
            u, unknown = Counter(), []
            ST.outside_clues(
                {"overlays": outside_texts}, n, q, words, u, unknown, lambda rc_: rc_[0] * n + rc_[1], inside
            )
            if not unknown and any(u.values()):
                p.constraints += q.constraints
                p.relations += q.relations
                p.named_rules = getattr(p, "named_rules", []) + getattr(q, "named_rules", [])
                used.update({k: v for k, v in u.items() if v})
                break
        else:
            return None, "unsupported: outside clue text"
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
    if fog:  # played in SudokuPad: a given lights its own cell
        fog["lit"] = sorted(
            set(fog["lit"]) | {f"r{i // n + 1}c{i % n + 1}" for i in p.givens},
            key=lambda c: (int(c[1 : c.index("c")]), int(c[c.index("c") + 1 :])),
        )
        p.fog = fog  # rate grades it under the fog
    return p, used


def _path_through(cells, n, limit=20000):
    """the cells in an order where each touches the next (king steps, as lines are drawn), or None"""
    cells = set(cells)
    touch = {c: [d for d in cells if d != c and abs(d // n - c // n) <= 1 and abs(d % n - c % n) <= 1] for c in cells}
    budget = [limit]

    def walk(path, seen):
        if len(path) == len(cells):
            return path
        budget[0] -= 1
        if budget[0] < 0:
            return None
        for d in sorted(touch[path[-1]], key=lambda d: len(touch[d])):  # the most constrained first
            if d not in seen:
                got = walk(path + [d], seen | {d})
                if got:
                    return got
        return None

    for start in sorted(cells, key=lambda c: (len(touch[c]), c)):  # ends of a path have few neighbors
        got = walk([start], {start})
        if got:
            return got
    return None


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


# rule keys of the SudokuPad reader -> generic f-puzzles line kinds (thermos and arrows need a bulb / circle: not read)
TEXT_LINE_KINDS = {"whisper": "whisper", "dutch": "dutch_whisper", "renban": "renban", "region_sum": "region_sum",
                   "palindrome": "palindrome", "entropic": "entropic", "parity": "parity", "modular": "modular",
                   "zipper": "zipper", "between": "between"}  # fmt: skip


def _text_circles(fp, text, n):
    """f-puzzles circles whose meaning the text gives -> (fp without them, [(kind, cells, digits)]): decorative circles
    ("the circles have no effect"), quadruple / anti-quadruple circles (four cells, digits; anti = the colour the text
    names for anti-quadruples, or pink / red), pair-sum circles ("cells connected by a pink circle must sum to 11")"""
    from . import _sp_translate as ST

    words = text + " " + (fp.get("_page_rules") or "").lower()
    if re.search(
        r"\bcircles?\b[^.]{0,60}\b(?:has|have) no effect|\bcircles? (?:is|are) (?:purely )?(?:decorative|cosmetic)",
        words,
    ):
        return dict(fp, circle=[]), []
    quads = {frozenset(q.get("cells") or []): q for q in fp.get("quadruple") or []}
    pair = re.search(r"cells? (?:connected|joined|separated) by an? (?:\w+ )?circle must sum to (\d+)", text)
    anti = re.search(r"anti-?quad\w*[^.]{0,40}\b(\w+) circle", text)
    keep, rules = [], []
    for it in fp.get("circle") or []:
        cs, v = it.get("cells") or [], str(it.get("value", "")).strip()
        col = ST.color_name(it.get("baseC") or "")
        if len(cs) == 4 and not v and frozenset(cs) in quads:  # a circle drawn under an f-puzzles quadruple
            if anti and col in ({anti.group(1)} | {"pink", "red"}) and col != "white":
                q = quads[frozenset(cs)]
                rules.append(("anti_quadruple", cs, [int(x) for x in q.get("values") or [] if str(x).isdigit()]))
                fp = dict(fp, quadruple=[x for x in fp.get("quadruple") or [] if x is not q])
                continue
            if col == "white":  # the quadruple's own circle
                continue
            # another color under a quadruple has its own meaning (bipolar, half correct, ...): left unread
        about = " ".join(x for x in re.split(r"(?<=[.\n])\s*", text) if "circle" in x)  # the sentences on circles
        standard = re.search(r"quadruple|must (?:appear|be placed)", about) and not re.search(
            r"exactly (?:one|two|three) of|\bsum\b|\bproduct\b", about
        )  # the quadruple rule itself, not another rule about the four cells
        if len(cs) == 4 and re.fullmatch(r"[\d ,]+", v) and ST.QUAD_TEXT.search(text) and standard:
            is_anti = bool(anti) and col in ({anti.group(1)} | {"pink", "red"}) and col != "white"
            rules.append(("anti_quadruple" if is_anti else "quadruple", cs, [int(x) for x in re.findall(r"\d", v)]))
        elif len(cs) == 2 and pair and not v:
            rules.append(("pair_sum", cs, [int(pair.group(1))]))
        elif len(cs) == 2 and not v and _dot_meaning(col, text):
            kind, k = _dot_meaning(col, text)
            rules.append((kind, cs, [k]))
        else:
            keep.append(it)
    rects = []
    for it in fp.get("rectangle") or []:  # diamonds / squares between two cells, colored like the circles
        cs, v = it.get("cells") or [], str(it.get("value", "")).strip()
        m = len(cs) == 2 and not v and _dot_meaning(ST.color_name(it.get("baseC") or ""), text)
        if m:
            rules.append((m[0], cs, [m[1]]))
        else:
            rects.append(it)
    return dict(fp, circle=keep, rectangle=rects), rules


def _dot_meaning(col, text):
    """a coloured dot's rule from the sentence naming its colour ("cells joined by green dots have a value ratio of
    3:1", "orange dots have a value difference of 3") -> (kind, k) or None; None too when the text adds a negative or
    a uniqueness rule for dots"""
    if (
        not col
        or col in ("white", "black")
        or re.search(r"(?:only|just) (?:appear|occur|exist) once|can only (?:appear|occur|exist) once", text)
    ):
        return None
    got = None
    for sent in re.split(r"(?<=[.\n])\s*", text):
        if not re.search(rf"\b{col}\w* (?:dots?|circles?|ovals?|diamonds?|squares?)\b", sent):
            continue
        if re.search(r"(?<!not )\ball (?:possible |the )?[\w/ ,]{0,30}?dots (?:are|have been) (?:given|shown)", sent):
            return None  # a negative constraint for these dots: not read
        m = re.search(r"ratio (?:of )?(?:(\d)\s*:\s*1|1\s*:\s*(\d))", sent)
        d = re.search(r"difference (?:of )?(\d)\b(?! or )", sent)
        sm = re.search(r"sum (?:to |of )?(\d{1,2})\b", sent)
        if len(re.findall(r"\bratio\b|\bdifference\b|\bconsecutive\b|\bsum\b|\bdouble\b", sent)) > 1:
            return None  # "either consecutive or a 1:2 ratio": a choice, no one rule
        if not re.search(r"\bratio\b|\bdifference\b|\bconsecutive\b|\bsum\b|\bdouble\b", sent):
            continue  # "not all green / orange dots are given": no meaning here
        if re.search(r"\bnot consecutive\b|\bnon-?consecutive\b", sent):
            cands = [("notdiff", 1)]
            if got and got != cands[0]:
                return None
            got = cands[0]
            continue
        if re.search(r"\bnot\b|n't\b|\bnever\b|\bcannot\b", sent):
            return None  # a negated meaning other than "not consecutive": not read
        cands = [("ratio", int(m.group(1) or m.group(2)))] if m else []
        cands += [("diff", int(d.group(1)))] if d else []
        cands += [("diff", 1)] if re.search(r"\bconsecutive\b", sent) and not (m or d) else []
        cands += [("sum", int(sm.group(1)))] if sm and not (m or d) else []
        if not cands:  # "not all green / orange dots are given": no rule here
            continue
        if len(cands) != 1 or (got and got != cands[0]):
            return None
        got = cands[0]
    return got


def _shape_cells(fp, n):
    """one-cell circles and squares (f-puzzles 'circle' / 'rectangle' without a value) as SudokuPad underlays, or None
    when any circle covers several cells or carries a value"""
    out = []
    for key, rounded in (("circle", True), ("rectangle", False)):
        for it in fp.get(key) or []:
            cs = it.get("cells") or []
            if len(cs) != 1 or str(it.get("value", "")).strip():
                if key == "circle":
                    return None
                continue
            r, c = rc(cs[0], n)
            w = float(it.get("width") or 0.8)
            out.append({"center": [r + 0.5, c + 0.5], "width": w, "height": float(it.get("height") or w),
                        "rounded": rounded, "backgroundColor": it.get("baseC") or it.get("outlineC")})  # fmt: skip
    return out


def text_line_reading(fp):
    """{colour: kind} for generic lines from the rules text: each colour the text names, or the one line rule a
    single-colour puzzle's text names or describes -> None when a colour stays unread (then the page's wording of the
    rules, if one was given, is tried)"""
    reading = _text_line_reading(fp, fp.get("ruleset") or "")
    if reading is None and fp.get("_page_rules"):
        reading = _text_line_reading(fp, fp["_page_rules"])
    return reading


def _text_line_reading(fp, text):
    from . import _sp_translate as ST

    colours = sorted({_colour(it) for it in fp.get("line") or []})
    cmap = ST.rules_color_map(text)
    named = {k for k, pats in ST.RULE_WORDS.items() if any(re.search(p, text.lower()) for p in pats)}
    dk = ST.diff_rule(text.lower())
    # rules drawn by their own f-puzzles element (a between line, a thermometer) are not what generic lines mean
    own = lambda r: (
        bool(r) and any(r.replace("_", "") in k for k, v in fp.items() if v and k != "line" and not k.startswith("_"))
    )
    only = (named | ST.described_line_rules(text) | ({dk} if dk else set())) - {"ten"}
    if any(
        r and not own(r) for r in cmap.values()
    ):  # the text gives its lines colors: an unnamed color is not the one rule
        only = set()
    every = ST.every_line_rule(text)
    drawn = {ST.color_name(c) for c in colours if c.startswith("#")}
    first = {c: ST.line_rule_from_text(c, cmap, drawn) if c.startswith("#") else None for c in colours}
    unread = [c for c in colours if first[c] is None]
    spare = {w for w in cmap if cmap[w] != "ignore" and not any(ST.color_name(c) == w for c in colours)}
    spare = {cmap[w] for w in spare if not own(cmap[w])} - {first[c] for c in colours}
    if len(unread) == 1 and len(spare) == 1 and len(colours) > 1 or len(colours) == 1 == len(unread) == len(spare):
        first[unread[0]] = spare.pop()  # the one line color the text does not name is the one rule it names unseen
    others = ST.other_lines_rule(text) if any(v is None for v in first.values()) else None
    reading = {}
    for c in colours:
        named_c = re.search(rf"\b{ST.color_name(c)}", text.lower()) if c.startswith("#") else None
        rk = first[c] or (others if not named_c else None)  # "all other lines": the colors no sentence names
        if rk is None and len(only) == 1 and (len(colours) == 1 or not cmap):
            rk = next(iter(only))  # the one line rule the text describes (lines drawn in several shades)
        if rk is None and every:
            rk = every
        for var_, (from_, pat_) in ST.LINE_VARIANTS.items():
            if rk in from_ and re.search(pat_, text.lower()):
                rk = var_
        if rk and (re.fullmatch(r"whisper\d", rk) or rk.startswith("linesum")):  # whisper threshold / line total
            reading[c] = rk
            continue
        if rk == "ignore":  # the text says these lines have no effect
            reading[c] = "ignore"
            continue
        if rk in ST.LINE_CUSTOM or rk in ("same_parity", "consecutive_line", "shifter"):
            reading[c] = rk  # custom-rule lines, applied by ST.custom_line
            continue
        if TEXT_LINE_KINDS.get(rk) is None:
            return None
        reading[c] = TEXT_LINE_KINDS[rk]
    return reading


def _colour(item):
    return str(item.get("outlineC") or item.get("color") or "?").lower()


def joined_or_separate(fp, node_limit=2_000_000):
    """touching segments of a set rule: one line drawn in pieces, or separate lines that meet? -> the reading (joined
    first) with a unique solution, matching the embedded one when there is one; joined when neither decides"""
    emb = solution_of(fp)
    wrong = False
    for join in (True, False):
        q, _ = translate(fp, join=join)
        if q is None:
            continue
        q.finalize()
        sols = _verified_solutions(q, limit=2, node_limit=node_limit)
        if len(sols) == 1 and (emb is None or list(sols[0]) == emb):
            return join
        wrong = wrong or (join and emb is not None and len(sols) == 1)  # joined contradicts the setter's solution
    return not wrong


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
            _log.info("inferred line reading %s", reading)
            info = dict(info)
            info["line_reading"] = reading
            info.pop("line", None)
            for k in combo:
                info[k] = True
            return p, info
        _log.debug("line reading %s: %s", reading, "no unique solution" if len(sols) != 1 else "another solution")
    _log.info("none of the %d line readings tried has a unique solution", min(tried, max_combos))
    return None, "no line reading with a unique solution"


def _verified_solutions(p, **kw):
    from .. import cpsat_verify

    return cpsat_verify.verified_solutions(p, **kw)
