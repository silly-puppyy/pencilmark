"""The "sudoku-spec" generator request (docs/FORMAT.md section 13) <-> pencilmark.gen Spec dicts, losslessly.

    spec_from_gen(spec) -> {"format": "sudoku-spec", ...}
    spec_to_gen(doc) -> dict accepted by pencilmark.gen.generate / Spec.from_any
    validate_spec(doc)
"""
from __future__ import annotations

import hashlib

from . import puzzle_json as PJ
from .exchange import FormatError, NotSupportedError, jcs

FORMAT = "sudoku-spec"
FORMAT_VERSION = 1
# generator element kind <-> rule placeholder (type, kind)
GEN_KINDS = {"cage": ("cage", None), "thermo": ("line", "thermo"), "whisper": ("line", "whisper"),
             "renban": ("line", "renban"), "between": ("line", "between"), "arrow": ("arrow", None),
             "kropki": ("edge", "kropki"), "xv": ("edge", "xv"), "parity": ("digits", "parity")}
RULE_KIND = {v: k for k, v in GEN_KINDS.items()}
COUNT_WORDS = {"full": "all", "min": "min", "partition": "partition"}
WORD_COUNT = {v: k for k, v in COUNT_WORDS.items()}
RUN_KEYS = ("solver", "seed", "time_limit", "grade_seconds")
DEFAULTS = {"solver": "logic", "seed": 1, "time_limit": 120.0, "grade_seconds": 60.0, "min_givens": 0, "max_givens": None,
            "strict_require": False}


def _placeholder(kind, count):
    t, k = GEN_KINDS[kind]
    r = {"type": t}
    if k:
        r["kind"] = k
    r["count"] = count
    return r


def spec_from_gen(spec):
    """pencilmark.gen Spec (or its dict) -> sudoku-spec dict"""
    from .gen.api import Spec
    s = Spec.from_any(spec)
    D = s.size
    if D not in PJ.BOXES:
        raise NotSupportedError(f"no standard boxes for size {D}")
    rules = [{"type": "subgrid", "size": D, "box": list(PJ.BOXES[D]), "origin": "r1c1"}]
    from .gen.elements import norm_kind
    for kind, n in (s.elements or {}).items():
        k = norm_kind(kind)
        rules.append(_placeholder(k, COUNT_WORDS.get(n, n) if isinstance(n, str) else (n or 0)))
    target = {}
    if s.target_band is not None:
        target["band"] = s.target_band
    if s.target_difficulty is not None:
        target["difficulty"] = list(s.target_difficulty)
    if s.require:
        target["requires"] = list(s.require)
    if s.strict_require:
        target["requires_strict"] = True
    if s.kinds:
        target["each_kind"] = []
        for kind in s.kinds:
            t, k = GEN_KINDS[norm_kind(kind)]
            target["each_kind"].append({"type": t, **({"kind": k} if k else {})})
    if s.symmetry:
        target["symmetry"] = s.symmetry
    if s.min_givens or s.max_givens is not None:
        target["givens"] = [s.min_givens, s.max_givens]
    if s.max_elements is not None:
        target["max_elements"] = s.max_elements
    doc = {"format": FORMAT, "format_version": FORMAT_VERSION, "grid": {"rows": D, "cols": D}, "digits": D, "rules": rules}
    if target:
        doc["target"] = target
    run = {k: getattr(s, k) for k in RUN_KEYS if getattr(s, k) != DEFAULTS[k]}
    if run:
        doc["run"] = run
    return doc


SPEC_KEYS = {"format", "format_version", "$schema", "meta", "grid", "digits", "rules", "target", "run", "givens", "ext"}
TARGET_KEYS = {"band", "difficulty", "requires", "requires_strict", "each_kind", "symmetry", "givens", "max_elements"}


def validate_spec(doc):
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise FormatError('not a sudoku-spec ("format" must be "sudoku-spec")')
    if not isinstance(doc.get("format_version"), int) or doc["format_version"] > FORMAT_VERSION:
        raise FormatError(f"sudoku-spec format_version {doc.get('format_version')!r} is not supported")
    for k in doc:
        if k not in SPEC_KEYS:
            raise FormatError(f"unknown key {k!r}")
    if "givens" in doc:
        raise NotSupportedError("givens masks are reserved in sudoku-spec format_version 1")
    D = doc.get("digits")
    if doc.get("grid") != {"rows": D, "cols": D}:
        raise NotSupportedError("the generator makes gap-free D x D boards")
    for k in doc.get("target") or {}:
        if k not in TARGET_KEYS:
            raise FormatError(f"unknown target key {k!r}")
    for k in doc.get("run") or {}:
        if k not in RUN_KEYS:
            raise FormatError(f"unknown run key {k!r}")
    subs = [r for r in doc.get("rules") or [] if r.get("type") == "subgrid"]
    if len(subs) != 1 or subs[0].get("origin") != "r1c1" or subs[0].get("size") != D or list(subs[0].get("box") or []) != list(PJ.BOXES.get(D, ())):
        raise NotSupportedError("format_version 1 specs take exactly the board's subgrid with standard boxes")
    for r in doc.get("rules") or []:
        if r.get("type") == "subgrid":
            continue
        if set(r) - {"type", "kind", "count"} or "count" not in r:
            raise NotSupportedError(f"fixed rules other than the board are not supported yet: {r}")
        if (r["type"], r.get("kind")) not in RULE_KIND:
            raise NotSupportedError(f"the generator cannot place {r['type']} {r.get('kind') or ''}".strip())


def spec_to_gen(doc):
    """sudoku-spec dict -> pencilmark.gen Spec dict"""
    validate_spec(doc)
    out = {"size": doc["digits"]}
    elements = {}
    for r in doc["rules"]:
        if r["type"] == "subgrid":
            continue
        kind = RULE_KIND[(r["type"], r.get("kind"))]
        n = r["count"]
        elements[kind] = WORD_COUNT.get(n, n) if isinstance(n, str) else n
    if elements:
        out["elements"] = elements
    t = doc.get("target") or {}
    if "band" in t:
        out["target_band"] = t["band"]
    if "difficulty" in t:
        out["target_difficulty"] = list(t["difficulty"])
    if t.get("requires"):
        out["require"] = list(t["requires"])
    if t.get("requires_strict"):
        out["strict_require"] = True
    if t.get("each_kind"):
        out["kinds"] = [RULE_KIND[(x["type"], x.get("kind"))] for x in t["each_kind"]]
    if t.get("symmetry"):
        out["symmetry"] = t["symmetry"]
    if "givens" in t:
        out["min_givens"], out["max_givens"] = t["givens"][0], t["givens"][1]
    if "max_elements" in t:
        out["max_elements"] = t["max_elements"]
    out.update(doc.get("run") or {})
    return out


def spec_fingerprint(doc):
    keep = {k: doc[k] for k in ("grid", "digits", "rules", "target") if k in doc}
    return "sha256:" + hashlib.sha256(jcs(keep).encode()).hexdigest()
