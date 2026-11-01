"""The "sudoku-spec" generator request (docs/formats/generator-spec.md): a puzzle file with blanks.

    validate_spec(doc)                    strict reading of the spec language (unknown keys refused)
    spec_to_gen(doc) -> dict              the part pencilmark.gen can run, as a Spec dict; anything else -> NotSupportedError
    spec_from_gen(spec) -> dict           pencilmark.gen Spec (or dict) -> sudoku-spec
    gen_support(doc) -> (bool, reason)    can pencilmark.gen run it today?

What pencilmark.gen runs today: gap-free D x D boards (4, 6, 8, 9, 10, 12, 16) with the standard box_grid, or a named
layout of 9 x 9 grids (one box_grid per grid); locked rules of different digits; templates for cages, thermo / whisper /
renban / between lines, arrows, kropki / XV, parity cells, with counts (incl. "all", "min", "tile", "max") and shape
limits (size, sum, length); givens count and per grid; one symmetry of the givens; where: band, difficulty range or
"max" / "min", contains (codes), elements max; limits: time, seed. Everything else in a spec is refused with the reason,
never ignored.
"""

from __future__ import annotations

import hashlib

from . import puzzle_json as PJ
from .exchange import FormatError, NotSupportedError, jcs
from .rules.edge import EDGE
from .rules.line import LINE

FORMAT = "sudoku-spec"
FORMAT_VERSION = 1
NS = "io.github.silly-puppyy.pencilmark"
# generator element kind <-> template (type, kind)
GEN_KINDS = {
    "cage": ("cage", None),
    **{k: ("line", k) for k, lk in LINE.items() if lk.generated},  # rules/line.py
    "arrow": ("arrow", None),
    **{k: ("edge", k) for k, ek in EDGE.items() if ek.generated},  # rules/edge.py
    "parity": ("cell", "parity"),
}
RULE_KIND = {v: k for k, v in GEN_KINDS.items()}
RULE_KIND.update({("cell", "odd"): "odd", ("cell", "even"): "even"})  # one parity: its own element class
GEN_SYM = {
    ("rot180", None): "rot180",
    ("rot90", None): "rot90",
    ("mirror", "vertical"): "mirror",
    ("mirror", "horizontal"): "mirror_v",
    ("mirror", "diagonal"): "diagonal",
    ("mirror", "antidiagonal"): "antidiagonal",
}
SYM_GEN = {v: k for k, v in GEN_SYM.items()}
SPEC_KEYS = {
    "format",
    "format_version",
    "$schema",
    "meta",
    "board",
    "digits",
    "givens",
    "rules",
    "symmetry",
    "where",
    "quality",
    "limits",
    "fields",
}
WHERE_KEYS = {"band", "difficulty", "time", "contains", "not_contains", "issues", "areas", "elements"}
LIMIT_KEYS = {"results", "attempts", "time", "seed"}
TEMPLATE_KEYS = {
    "type",
    "kind",
    "count",
    "size",
    "length",
    "sum",
    "value",
    "displaced",
    "area",
    "id",
    "label",
    "style",
    "color",
    "letter",
}
COUNT_WORDS = {"auto", "all", "min", "tile", "max"}
DEFAULTS = {
    "solver": "logic",
    "seed": 1,
    "time_limit": 120.0,
    "grade_seconds": 60.0,
    "min_givens": 0,
    "max_givens": None,
    "strict_require": False,
}


def _is_template(r):
    return "count" in r and not ({"cells", "bulb", "regions", "origin", "source"} & set(r))


def _n_or_range(v, what):
    """n or [min, max] of whole numbers >= 0 (min / max null = open), else a FormatError naming what"""
    num = lambda x: isinstance(x, int) and not isinstance(x, bool) and x >= 0
    if num(v) or (isinstance(v, list) and len(v) == 2 and all(x is None or num(x) for x in v)):
        return
    raise FormatError(f"{what} must be a whole number or [min, max], got {v!r}")


def validate_spec(doc):
    """strict reading of a sudoku-spec (docs/formats/generator-spec.md); locked rules are checked like puzzle rules"""
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise FormatError('not a sudoku-spec ("format" must be "sudoku-spec")')
    fv = doc.get("format_version")
    if not isinstance(fv, int) or fv > FORMAT_VERSION:
        raise FormatError(f"sudoku-spec format_version {fv!r} is not supported")
    for k in doc:
        if k not in SPEC_KEYS:
            raise FormatError(f"unknown key {k!r}")
    g = doc.get("board")
    if not isinstance(g, dict) or set(g) != {"rows", "cols"}:
        raise FormatError('"board" must be {"rows": R, "cols": C}')
    if not isinstance(doc.get("digits"), int):
        raise FormatError("digits must be an integer")
    giv = doc.get("givens")
    if giv is not None and not isinstance(giv, list):
        if not isinstance(giv, dict) or set(giv) - {"count", "grids", "mask", "values"}:
            raise FormatError('givens must be a flat list or {"count", "grids", "mask", "values"}')
        if "count" in giv:
            _n_or_range(giv["count"], "givens.count")
        if "grids" in giv:
            if not isinstance(giv["grids"], list):
                raise FormatError("givens.grids must be a list (one count or [min, max] per grid)")
            for g in giv["grids"]:
                _n_or_range(g, "givens.grids entry")
    if doc.get("meta") is not None and not isinstance(doc["meta"], dict):
        raise FormatError("meta must be an object")
    if doc.get("rules") is not None and not isinstance(doc["rules"], list):
        raise FormatError("rules must be a list")
    for r in doc.get("rules") or []:
        if not isinstance(r, dict) or not isinstance(r.get("type"), str):
            raise FormatError("a rule must be an object with a type")
        if _is_template(r):
            for k in ("kind", "color", "letter"):
                if k in r and not isinstance(r[k], str):
                    raise FormatError(f"template {r['type']}: {k} must be a string, got {r[k]!r}")
            for k in ("size", "length", "sum"):
                if k in r:
                    _n_or_range(r[k], f"template {r['type']}: {k}")
            bad = set(r) - TEMPLATE_KEYS
            if bad:
                raise FormatError(f"template {r['type']}: unknown key(s) {sorted(bad)}")
            c = r["count"]
            if isinstance(c, list) or isinstance(c, int):
                _n_or_range(c, f"template {r['type']}: count")
            elif not (isinstance(c, str) and c in COUNT_WORDS):
                raise FormatError(
                    f"template {r['type']}: count must be a number, [min, max] or one of {sorted(COUNT_WORDS)}"
                )
        elif "lock" in r and not isinstance(r["lock"], bool):
            raise FormatError("lock must be true / false")
    if doc.get("symmetry") is not None and not isinstance(doc["symmetry"], list):
        raise FormatError("symmetry must be a list of entries")
    for s in doc.get("symmetry") or []:
        if (
            not isinstance(s, dict)
            or s.get("kind") not in ("rot180", "rot90", "mirror")
            or set(s) - {"kind", "axis", "of"}
        ):
            raise FormatError('symmetry entries are {"kind": rot180 | rot90 | mirror, "axis"?, "of"}')
        if s["kind"] == "mirror" and s.get("axis") not in ("horizontal", "vertical", "diagonal", "antidiagonal"):
            raise FormatError("mirror symmetry needs axis horizontal / vertical / diagonal / antidiagonal")
    if doc.get("quality") is not None:
        from .publish_flags import quality_limits

        try:
            quality_limits(doc["quality"])
        except ValueError as e:
            raise FormatError(str(e)) from None
    for blk, keys in (("where", WHERE_KEYS), ("limits", LIMIT_KEYS)):
        if doc.get(blk) is not None and not isinstance(doc[blk], dict):
            raise FormatError(f"{blk} must be an object")
        for k in doc.get(blk) or {}:
            if k not in keys:
                raise FormatError(f"unknown {blk} key {k!r}")
    w, lim = doc.get("where") or {}, doc.get("limits") or {}
    if "band" in w and not isinstance(w["band"], (str, list)):
        raise FormatError(f"where.band must be a band name, got {w['band']!r}")
    d = w.get("difficulty")
    real = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
    if d is not None and not (d in ("max", "min") or (isinstance(d, list) and len(d) == 2 and all(map(real, d)))):
        raise FormatError(f'where.difficulty must be [lo, hi], "max" or "min", got {d!r}')
    c = w.get("contains")
    codes = c.get("codes") if isinstance(c, dict) else c
    reserved = isinstance(c, dict) and set(c) - {"codes", "strict"}  # only / uses: spec_to_gen names them as reserved
    if c is not None and not reserved and not (isinstance(codes, list) and all(isinstance(x, str) for x in codes)):
        raise FormatError('where.contains must be a list of technique codes or {"codes": [...], "strict": true}')
    if "elements" in w and not (isinstance(w["elements"], dict) and set(w["elements"]) <= {"max"}):
        raise FormatError('where.elements takes {"max": n}')
    if "elements" in w and "max" in w["elements"]:
        _n_or_range(w["elements"]["max"], "where.elements.max")
    if "time" in lim and not (real(lim["time"]) and lim["time"] > 0):
        raise FormatError(f"limits.time must be a number of seconds > 0, got {lim['time']!r}")
    if "seed" in lim and not (isinstance(lim["seed"], int) and not isinstance(lim["seed"], bool)):
        raise FormatError(f"limits.seed must be a whole number, got {lim['seed']!r}")
    if doc.get("fields") is not None:
        if not isinstance(doc["fields"], list):
            raise FormatError("fields must be a list of card keys")
        from .export import card_fields

        try:
            card_fields(doc["fields"])
        except ValueError as e:
            raise FormatError(str(e)) from None
    return True


LOCKED_OK = {
    ("region", "diagonal"),
    ("region", "extra"),
    ("region", "window"),
    ("neighbours", "antiknight"),
    ("neighbours", "antiking"),
}  # locked rules the generator's grids can respect: all-different cells


def _board(doc):
    """(layout name or None, locked rules) of a request, or a NotSupportedError message (str). The board is one
    D x D grid with a single box_grid, or a named multi-grid layout of 9 x 9 grids given by one box_grid per grid
    (puzzle_json's layouts: samurai, super-samurai, twodoku, ...); locked rules are all-different rules."""
    from .gen.board import BOXES as GEN_BOXES

    D = doc["digits"]
    if D not in GEN_BOXES:
        return f"the generator makes boards of size {', '.join(map(str, sorted(GEN_BOXES)))}, not {D}"
    bh, bw = PJ.BOXES[D]
    locked = [{k: v for k, v in r.items() if k not in ("id", "label", "style")} for r in doc.get("rules") or []
              if not _is_template(r)]  # fmt: skip
    grids = [r for r in locked if r.get("type") == "box_grid"]
    other = [r for r in locked if r.get("type") not in ("box_grid", "grid")]
    for r in other:
        if (r.get("type"), r.get("kind")) not in LOCKED_OK:
            return (f"locked {r.get('type')} {r.get('kind') or ''} rules are reserved for a later version of the spec"
                    " (docs/formats/generator-spec.md 7); the generator takes all-different ones: "
                    + ", ".join(f"{t} {k}" for t, k in sorted(LOCKED_OK)))  # fmt: skip
    if any(r.get("box") != [bh, bw] for r in grids):
        return f"box_grid rules need the standard {bh}x{bw} boxes"
    origins = sorted(tuple(x - 1 for x in map(int, r["origin"][1:].split("c"))) for r in grids)
    if origins == [(0, 0)] and doc["board"] == {"rows": D, "cols": D}:
        return None, other
    for name, orig in PJ._layouts().items():
        if D == 9 and sorted(orig) == origins:
            rows = max(r for r, _ in orig) + 9
            cols = max(c for _, c in orig) + 9
            if doc["board"] != {"rows": rows, "cols": cols}:
                return f"layout {name} needs a {rows} x {cols} board, not {doc['board']}"
            return name, other
    return (
        f"the generator makes one {D}x{D} grid or a named layout of 9 x 9 grids ("
        + ", ".join(sorted(PJ._layouts()))
        + "); these box_grid origins match none"
    )


def spec_to_gen(doc):
    """sudoku-spec -> pencilmark.gen Spec dict; NotSupportedError naming the first part the generator cannot run"""
    validate_spec(doc)
    bd = _board(doc)
    if isinstance(bd, str):
        raise NotSupportedError(bd)
    D = doc["digits"]
    out = {"size": D}
    if bd[0]:
        out["layout"] = bd[0]
    if bd[1]:
        out["locked"] = bd[1]
    giv = doc.get("givens")
    if isinstance(giv, list):
        if any(v not in (0, None) for v in giv) or any(v is None for v in giv):
            raise NotSupportedError(
                "givens in puzzle form (locked digits / gaps) are reserved for a later version of the spec (docs/formats/generator-spec.md 7)"
            )
    elif isinstance(giv, dict):
        if "mask" in giv or "values" in giv:
            raise NotSupportedError(
                "givens masks / locked values are reserved for a later version of the spec (docs/formats/generator-spec.md 7)"
            )
        if "grids" in giv:  # givens per n x n grid, in the order of the box_grid rules' origins (reading order)
            out["grid_givens"] = [[g, g] if isinstance(g, int) else list(g) for g in giv["grids"]]
        c = giv.get("count")
        if isinstance(c, int):
            out["min_givens"], out["max_givens"] = c, c
        elif isinstance(c, list):
            out["min_givens"], out["max_givens"] = (c[0] or 0), c[1]
    elements, kinds = {}, []
    for r in doc.get("rules") or []:
        if not _is_template(r):
            continue
        key = (r["type"], r.get("kind"))
        if key not in RULE_KIND:
            raise NotSupportedError(f"the generator cannot place {r['type']} {r.get('kind') or ''}".strip())
        for k in ("displaced", "area"):
            if k in r:
                raise NotSupportedError(
                    f"template {r['type']}: {k!r} is reserved for a later version of the spec (docs/formats/generator-spec.md 7)"
                )
        kind = RULE_KIND[key]
        lim = {}
        for k in ("size", "length", "sum"):  # n or [min, max] (max null = open)
            if k not in r:
                continue
            v = r[k]
            if not (isinstance(v, int) or (isinstance(v, list) and len(v) == 2)):
                raise FormatError(f"template {r['type']}: {k} must be a number or [min, max]")
            want = "size" if kind == "cage" else "length"
            if k != "sum" and k != want:
                raise NotSupportedError(
                    f"template {r['type']}: use {want!r} for its {'cells' if want == 'size' else 'length'}"
                )
            if k == "sum" and kind != "cage":
                raise NotSupportedError(f"template {r['type']}: 'sum' applies to cages")
            lim["sum" if k == "sum" else "length"] = [v, v] if isinstance(v, int) else list(v)
        if lim:
            out.setdefault("shape", {})[kind] = lim
        # one colour / letter / parity of a kind is its own element class (counted separately)
        cls = {
            ("kropki", "white"): "kropki_white",
            ("kropki", "black"): "kropki_black",
            ("xv", "X"): "x",
            ("xv", "V"): "v",
        }
        sel = r.get("color") or r.get("letter")
        if sel is not None:
            if (kind, sel) not in cls:
                raise NotSupportedError(f"template {r['type']}: {sel!r} is not a generator element class")
            kind = cls[(kind, sel)]
        if "value" in r:
            from .gen.elements import whisper_gap

            if kind != "whisper" or r["value"] != whisper_gap(D):
                raise NotSupportedError(
                    f"template {r['type']}: value {r['value']} is not supported (generator whisper gap {whisper_gap(D)})"
                )
        c = r["count"]
        if c == "auto":
            elements[kind] = 0
        elif c == "all":
            if kind != "kropki":
                raise NotSupportedError(f"count 'all' is supported for kropki only, not {kind}")
            elements[kind] = "full"
        elif c == "min":
            if kind != "kropki":
                raise NotSupportedError(f"count 'min' is supported for kropki only, not {kind}")
            elements[kind] = "min"
        elif c == "max":
            elements[kind] = "max"
        elif c == "tile":
            if kind != "cage":
                raise NotSupportedError(f"count 'tile' is supported for cages only, not {kind}")
            elements[kind] = "partition"
        elif isinstance(c, list):  # [min, max]; max null = no cap
            elements[kind] = [c[0] or 0, c[1]]
        elif kind == "cage" and out.get("max_givens") == 0:
            elements[kind] = c  # zero-given killer: exactly c cages (CP-SAT form)
        else:  # an exact number
            elements[kind] = [c, c]
    if elements:
        out["elements"] = elements
    if kinds:
        out["kinds"] = kinds
    syms = doc.get("symmetry") or []
    if len(syms) > 1:
        raise NotSupportedError("the generator takes one symmetry")
    if syms:
        s = syms[0]
        if s.get("of", "givens") != "givens":
            raise NotSupportedError("the generator makes only the givens symmetric")
        out["symmetry"] = GEN_SYM[(s["kind"], s.get("axis"))]
    w = doc.get("where") or {}
    for k in ("time", "not_contains", "issues", "areas"):
        if k in w:
            raise NotSupportedError(
                f"where.{k} is reserved for a later version of the spec (docs/formats/generator-spec.md 7)"
            )
    if "band" in w:
        if isinstance(w["band"], list):
            raise NotSupportedError("a list of bands is not supported (one band)")
        out["target_band"] = w["band"]
    if "difficulty" in w:
        dv = w["difficulty"]
        if dv not in ("max", "min") and not (isinstance(dv, list) and len(dv) == 2):
            raise FormatError('where.difficulty must be [lo, hi], "max" or "min"')
        out["target_difficulty"] = dv if isinstance(dv, str) else list(dv)
    if "contains" in w:
        c = w["contains"]
        if isinstance(c, list):
            out["require"] = list(c)
        elif isinstance(c, dict) and set(c) <= {"codes", "strict"}:
            out["require"] = list(c["codes"])
            if c.get("strict"):
                out["strict_require"] = True
        else:
            raise NotSupportedError(
                "contains 'only' / per-code uses are reserved for a later version of the spec (docs/formats/generator-spec.md 7)"
            )
    if "elements" in w:
        if set(w["elements"]) != {"max"}:
            raise NotSupportedError('where.elements takes {"max": n}')
        out["max_elements"] = w["elements"]["max"]
    if doc.get("quality") is not None:  # the publishing checks: a candidate with a reject issue is not returned
        out["quality"] = dict(doc["quality"])
    lim = doc.get("limits") or {}
    if lim.get("results", 1) != 1:
        raise NotSupportedError("the generator returns one puzzle per run (limits.results 1; run several seeds)")
    if "attempts" in lim:
        raise NotSupportedError("limits.attempts is not supported (use limits.time)")
    if "time" in lim:
        out["time_limit"] = lim["time"]
    if "seed" in lim:
        out["seed"] = lim["seed"]
    out.update(
        ((doc.get("meta") or {}).get(NS) or {})
    )  # pencilmark's own generator knobs live in meta (docs/formats/puzzle-format.md 2.1)
    return out


def gen_support(doc):
    """(True, "") when pencilmark.gen can run the spec today, else (False, reason)"""
    try:
        spec_to_gen(doc)
        return True, ""
    except (NotSupportedError, FormatError) as e:
        return False, str(e)


def spec_from_gen(spec):
    """pencilmark.gen Spec (or its dict) -> sudoku-spec dict"""
    from .gen.api import Spec
    from .gen.elements import norm_kind

    s = Spec.from_any(spec)
    D = s.size
    if D not in PJ.BOXES:
        raise NotSupportedError(f"no standard boxes for size {D}")
    bh, bw = PJ.BOXES[D]
    origins = PJ._layouts()[s.layout] if s.layout else [(0, 0)]
    rules = [{"type": "box_grid", "origin": f"r{r + 1}c{c + 1}", "box": [bh, bw]} for r, c in origins]
    rules += [dict(r) for r in s.locked or []]
    from .gen.elements import CLASSES

    def tmpl(kind, count):
        kind = norm_kind(kind)
        base, sel = CLASSES.get(kind, (kind, None))
        t, k = GEN_KINDS[base]
        r = {"type": t}
        if k:
            r["kind"] = k
        if sel is not None and base in ("kropki", "xv"):
            r["color" if base == "kropki" else "letter"] = sel
        if sel is not None and base == "parity":  # odd / even cells: the template names the parity
            r["kind"] = "odd" if sel else "even"
        r["count"] = count
        for key, (lo, hi) in ((s.shape or {}).get(base) or {}).items():
            name = "sum" if key == "sum" else "size" if base == "cage" else "length"
            r[name] = lo if lo == hi else [lo, hi]
        return r

    for kind, n in (s.elements or {}).items():
        if isinstance(n, str) and n.lower() == "auto":
            rules.append(tmpl(kind, "auto"))
        elif isinstance(n, str):
            rules.append(tmpl(kind, {"full": "all", "min": "min", "partition": "tile", "max": "max"}[n.lower()]))
        elif isinstance(n, (list, tuple)):
            rules.append(tmpl(kind, n[0] if n[0] == n[1] else [n[0], n[1]]))
        elif not n:
            rules.append(tmpl(kind, "auto"))
        elif norm_kind(kind) == "cage" and s.max_givens == 0:
            rules.append(tmpl(kind, n))
        else:
            rules.append(tmpl(kind, [n, None]))
    for kind in s.kinds or []:
        rules.append(tmpl(kind, [1, None]))
    rows = max(r for r, _ in origins) + D
    cols = max(c for _, c in origins) + D
    doc = {"format": FORMAT, "format_version": FORMAT_VERSION, "board": {"rows": rows, "cols": cols}, "digits": D}
    if s.min_givens or s.max_givens is not None:
        doc["givens"] = {"count": s.min_givens if s.min_givens == s.max_givens else [s.min_givens, s.max_givens]}
    if s.grid_givens:
        doc.setdefault("givens", {})["grids"] = [g[0] if g[0] == g[1] else list(g) for g in s.grid_givens]
    doc["rules"] = rules
    if s.symmetry:
        k, axis = SYM_GEN[s.symmetry]
        doc["symmetry"] = [dict({"kind": k}, **({"axis": axis} if axis else {}), of="givens")]
    w = {}
    if s.target_band is not None:
        w["band"] = s.target_band
    if s.target_difficulty is not None:
        td = s.target_difficulty
        w["difficulty"] = td if isinstance(td, str) else list(td)
    if s.require:
        w["contains"] = {"codes": list(s.require), "strict": True} if s.strict_require else list(s.require)
    if s.max_elements is not None:
        w["elements"] = {"max": s.max_elements}
    if w:
        doc["where"] = w
    lim = {}
    if s.time_limit != DEFAULTS["time_limit"]:
        lim["time"] = s.time_limit
    if s.seed != DEFAULTS["seed"]:
        lim["seed"] = s.seed
    if lim:
        doc["limits"] = lim
    if s.quality is not None:  # {} = the default checks
        doc["quality"] = dict(s.quality)
    ext = {k: getattr(s, k) for k in ("solver", "grade_seconds") if getattr(s, k) != DEFAULTS[k]}
    if ext:
        doc.setdefault("meta", {})[NS] = ext
    return doc


def spec_fingerprint(doc):
    keep = {k: doc[k] for k in ("board", "digits", "givens", "rules", "symmetry", "where", "quality") if k in doc}
    return "sha256:" + hashlib.sha256(jcs(keep).encode()).hexdigest()
