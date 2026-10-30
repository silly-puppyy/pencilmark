"""The "sudoku-spec" generator request (docs/SPEC.md): a puzzle file with blanks.

    validate_spec(doc)                    strict reading of the spec language (unknown keys refused)
    spec_to_gen(doc) -> dict              the part pencilmark.gen can run, as a Spec dict; anything else -> NotSupportedError
    spec_from_gen(spec) -> dict           pencilmark.gen Spec (or dict) -> sudoku-spec
    gen_support(doc) -> (bool, reason)    can pencilmark.gen run it today?

What pencilmark.gen runs today: gap-free D x D boards (4, 6, 8, 9, 10, 12, 16) with the standard box_grid; templates for
cages, thermo / whisper / renban / between lines, arrows, kropki / XV (incl. "all" and "min"), parity cells; givens count;
one symmetry of the givens; where: band, difficulty range, contains (codes), elements max; limits: time, seed. Everything
else in a spec is refused with the reason, never ignored.
"""
from __future__ import annotations

import hashlib

from . import puzzle_json as PJ
from .exchange import FormatError, NotSupportedError, jcs

FORMAT = "sudoku-spec"
FORMAT_VERSION = 1
NS = "io.github.silly-puppyy.pencilmark"
# generator element kind <-> template (type, kind)
GEN_KINDS = {"cage": ("cage", None), "thermo": ("line", "thermo"), "whisper": ("line", "whisper"),
             "renban": ("line", "renban"), "between": ("line", "between"), "arrow": ("arrow", None),
             "kropki": ("edge", "kropki"), "xv": ("edge", "xv"), "parity": ("cell", "parity")}
RULE_KIND = {v: k for k, v in GEN_KINDS.items()}
GEN_SYM = {("rot180", None): "rot180", ("rot90", None): "rot90", ("mirror", "vertical"): "mirror",
           ("mirror", "horizontal"): "mirror_v", ("mirror", "diagonal"): "diagonal", ("mirror", "antidiagonal"): "antidiagonal"}
SYM_GEN = {v: k for k, v in GEN_SYM.items()}
SPEC_KEYS = {"format", "format_version", "$schema", "meta", "board", "digits", "givens", "rules", "symmetry", "where",
             "quality", "limits", "fields"}
WHERE_KEYS = {"band", "difficulty", "time", "contains", "not_contains", "issues", "areas", "elements"}
LIMIT_KEYS = {"results", "attempts", "time", "seed"}
TEMPLATE_KEYS = {"type", "kind", "count", "size", "length", "value", "displaced", "area", "id", "label", "style", "color", "letter"}
COUNT_WORDS = {"auto", "all", "min", "tile"}
DEFAULTS = {"solver": "logic", "seed": 1, "time_limit": 120.0, "grade_seconds": 60.0, "min_givens": 0, "max_givens": None,
            "strict_require": False}


def _is_template(r):
    return "count" in r and not ({"cells", "bulb", "regions", "origin", "source"} & set(r))


def validate_spec(doc):
    """strict reading of a sudoku-spec (SPEC.md); locked rules are checked like puzzle rules"""
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
        if not isinstance(giv, dict) or set(giv) - {"count", "mask", "values"}:
            raise FormatError('givens must be a flat list or {"count", "mask", "values"}')
    for r in doc.get("rules") or []:
        if not isinstance(r, dict) or "type" not in r:
            raise FormatError("a rule must be an object with a type")
        if _is_template(r):
            bad = set(r) - TEMPLATE_KEYS
            if bad:
                raise FormatError(f"template {r['type']}: unknown key(s) {sorted(bad)}")
            c = r["count"]
            if not (isinstance(c, int) or (isinstance(c, str) and c in COUNT_WORDS) or (isinstance(c, list) and len(c) == 2)):
                raise FormatError(f"template {r['type']}: count must be a number, [min, max] or one of {sorted(COUNT_WORDS)}")
        elif "lock" in r and not isinstance(r["lock"], bool):
            raise FormatError("lock must be true / false")
    for s in doc.get("symmetry") or []:
        if not isinstance(s, dict) or s.get("kind") not in ("rot180", "rot90", "mirror") or set(s) - {"kind", "axis", "of"}:
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
        for k in doc.get(blk) or {}:
            if k not in keys:
                raise FormatError(f"unknown {blk} key {k!r}")
    if doc.get("fields") is not None:
        if not isinstance(doc["fields"], list):
            raise FormatError("fields must be a list of card keys")
        from .export import card_fields
        try:
            card_fields(doc["fields"])
        except ValueError as e:
            raise FormatError(str(e)) from None
    return True


def _board_ok(doc):
    D = doc["digits"]
    if doc["board"].get("rows") != D or doc["board"].get("cols") != D:
        return f"the generator makes gap-free {D}x{D} boards (board {doc['board']})"
    if D not in PJ.BOXES:
        return f"no standard boxes for size {D}"
    bh, bw = PJ.BOXES[D]
    locked = [r for r in doc.get("rules") or [] if not _is_template(r)]
    board = ({"type": "box_grid", "origin": "r1c1", "box": [bh, bw]}, {"type": "grid", "origin": "r1c1"})
    for r in locked:
        if {k: v for k, v in r.items() if k not in ("id", "label", "style")} not in board:
            return f"locked rules other than the board's grid / box_grid are not supported by the generator yet ({r.get('type')})"
    return None


def spec_to_gen(doc):
    """sudoku-spec -> pencilmark.gen Spec dict; NotSupportedError naming the first part the generator cannot run"""
    validate_spec(doc)
    why = _board_ok(doc)
    if why:
        raise NotSupportedError(why)
    D = doc["digits"]
    out = {"size": D}
    giv = doc.get("givens")
    if isinstance(giv, list):
        if any(v not in (0, None) for v in giv) or any(v is None for v in giv):
            raise NotSupportedError("givens in puzzle form (locked digits / gaps) are not supported by the generator yet")
    elif isinstance(giv, dict):
        if "mask" in giv or "values" in giv:
            raise NotSupportedError("givens masks / locked values are not supported by the generator yet")
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
        for k in ("size", "length", "displaced", "area"):
            if k in r:
                raise NotSupportedError(f"template {r['type']}: {k!r} is not supported by the generator yet")
        kind = RULE_KIND[key]
        # one colour / letter / parity of a kind is its own element class (counted separately)
        cls = {("kropki", "white"): "kropki_white", ("kropki", "black"): "kropki_black", ("xv", "X"): "x", ("xv", "V"): "v"}
        sel = r.get("color") or r.get("letter")
        if sel is not None:
            if (kind, sel) not in cls:
                raise NotSupportedError(f"template {r['type']}: {sel!r} is not a generator element class")
            kind = cls[(kind, sel)]
        if "value" in r:
            from .gen.elements import whisper_gap
            if kind != "whisper" or r["value"] != whisper_gap(D):
                raise NotSupportedError(f"template {r['type']}: value {r['value']} is not supported (generator whisper gap {whisper_gap(D)})")
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
        elif c == "tile":
            if kind != "cage":
                raise NotSupportedError(f"count 'tile' is supported for cages only, not {kind}")
            elements[kind] = "partition"
        elif isinstance(c, list):                        # [min, max]; max null = no cap
            elements[kind] = [c[0] or 0, c[1]]
        elif kind == "cage" and out.get("max_givens") == 0:
            elements[kind] = c                           # zero-given killer: exactly c cages (CP-SAT form)
        else:                                            # an exact number
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
            raise NotSupportedError(f"where.{k} is not supported by the generator yet")
    if "band" in w:
        if isinstance(w["band"], list):
            raise NotSupportedError("a list of bands is not supported (one band)")
        out["target_band"] = w["band"]
    if "difficulty" in w:
        if not isinstance(w["difficulty"], list):
            raise NotSupportedError("difficulty 'max' / 'min' (best-so-far search) is not supported by the generator yet")
        out["target_difficulty"] = list(w["difficulty"])
    if "contains" in w:
        c = w["contains"]
        if isinstance(c, list):
            out["require"] = list(c)
        elif isinstance(c, dict) and set(c) <= {"codes", "strict"}:
            out["require"] = list(c["codes"])
            if c.get("strict"):
                out["strict_require"] = True
        else:
            raise NotSupportedError("contains 'only' / per-code uses are not supported by the generator yet")
    if "elements" in w:
        if set(w["elements"]) != {"max"}:
            raise NotSupportedError('where.elements takes {"max": n}')
        out["max_elements"] = w["elements"]["max"]
    q = doc.get("quality") or {}
    if q:
        raise NotSupportedError("quality checks are not applied by the generator yet (every result is unique and graded)")
    lim = doc.get("limits") or {}
    if lim.get("results", 1) != 1:
        raise NotSupportedError("the generator returns one puzzle per run (limits.results 1; run several seeds)")
    if "attempts" in lim:
        raise NotSupportedError("limits.attempts is not supported (use limits.time)")
    if "time" in lim:
        out["time_limit"] = lim["time"]
    if "seed" in lim:
        out["seed"] = lim["seed"]
    out.update(((doc.get("meta") or {}).get(NS) or {}))    # pencilmark's own generator knobs live in meta (FORMAT.md 2.1)
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
    rules = [{"type": "box_grid", "origin": "r1c1", "box": [bh, bw]}]
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
        r["count"] = count
        return r
    for kind, n in (s.elements or {}).items():
        if isinstance(n, str) and n.lower() == "auto":
            rules.append(tmpl(kind, "auto"))
        elif isinstance(n, str):
            rules.append(tmpl(kind, {"full": "all", "min": "min", "partition": "tile"}[n.lower()]))
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
    doc = {"format": FORMAT, "format_version": FORMAT_VERSION, "board": {"rows": D, "cols": D}, "digits": D}
    if s.min_givens or s.max_givens is not None:
        doc["givens"] = {"count": s.min_givens if s.min_givens == s.max_givens else [s.min_givens, s.max_givens]}
    doc["rules"] = rules
    if s.symmetry:
        k, axis = SYM_GEN[s.symmetry]
        doc["symmetry"] = [dict({"kind": k}, **({"axis": axis} if axis else {}), of="givens")]
    w = {}
    if s.target_band is not None:
        w["band"] = s.target_band
    if s.target_difficulty is not None:
        w["difficulty"] = list(s.target_difficulty)
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
    ext = {k: getattr(s, k) for k in ("solver", "grade_seconds") if getattr(s, k) != DEFAULTS[k]}
    if ext:
        doc.setdefault("meta", {})[NS] = ext
    return doc


def spec_fingerprint(doc):
    keep = {k: doc[k] for k in ("board", "digits", "givens", "rules", "symmetry", "where", "quality") if k in doc}
    return "sha256:" + hashlib.sha256(jcs(keep).encode()).hexdigest()
