"""The canonical text and the content fingerprint (docs/formats/puzzle-format.md 8)."""

from __future__ import annotations

import hashlib
import json

from .board import Board, read_houses
from .common import DIRECTED_OPS, GRID_TYPES, parse_cell, with_origins
from .validate import resolve_areas

# --------------------------------------------------------------------------------------------- canonical text + hash
KEY_ORDER = [
    "format",
    "format_version",
    "$schema",
    "meta",
    "board",
    "digits",
    "givens",
    "placed",
    "solution",
    "candidates",
    "rules",
    "decorations",
    "style",
]
RULE_ORDER = [
    "type",
    "kind",
    "of",
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
    "count",
    "step",
    "within",
    "area",
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
    "allowed",
    "id",
    "label",
    "style",
]


def _order(d, order):
    pos = {k: i for i, k in enumerate(order)}
    return {k: d[k] for k in sorted(d, key=lambda k: (pos.get(k, len(pos)), k))}


def canonical(doc):
    """key order of docs/formats/puzzle-format.md 8.1 (content unchanged; a default origin left out)"""
    out = _order(doc, KEY_ORDER)
    if isinstance(out.get("board"), dict):
        out["board"] = _order(out["board"], ["rows", "cols"])
    if "rules" in out:
        out["rules"] = [  # a grid / box_grid / chaos origin at r1c1 is the default: left out
            _order(
                {k: v for k, v in r.items() if not (k == "origin" and v == "r1c1" and r.get("type") in GRID_TYPES)},
                RULE_ORDER,
            )
            if isinstance(r, dict)
            else r
            for r in out["rules"]
        ]
        out["rules"] = [dict(r, holds=_holds(r["holds"])) if r.get("type") == "custom" else r for r in out["rules"]]
    if "candidates" in out:

        def rc(k):
            r, c = parse_cell(k)
            return (r, c)

        out["candidates"] = {k: sorted(v) for k, v in sorted(out["candidates"].items(), key=lambda kv: rc(kv[0]))}
    if "placed" in out:
        out["placed"] = dict(sorted(out["placed"].items(), key=lambda kv: parse_cell(kv[0])))
    return out


def dumps(doc, pretty=True):
    """canonical JSON text: fixed key order; pretty: givens / solution one grid row per line, one rule per line."""
    d = canonical(doc)
    if not pretty:
        return json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    C = d.get("board", {}).get("cols") or 1
    j = lambda x: json.dumps(x, ensure_ascii=False, separators=(", ", ": "))
    lines = []
    keys = list(d)
    for n, k in enumerate(keys):
        v = d[k]
        end = "," if n < len(keys) - 1 else "}"
        pre = "{" if n == 0 else " "
        if k in ("givens", "solution") and isinstance(v, list):
            rows = [", ".join("null" if x is None else str(x) for x in v[i : i + C]) for i in range(0, len(v), C)]
            lines.append(f'{pre}"{k}": [\n' + ",\n".join("    " + r for r in rows) + "]" + end)
        elif k == "rules" and isinstance(v, list):
            lines.append(f'{pre}"{k}": [' + ("\n" + ",\n".join("  " + j(r) for r in v) if v else "") + "]" + end)
        else:
            lines.append(f"{pre}{j(k)}: {j(v)}{end}")
    return "\n".join(lines) + "\n"


def jcs(x):
    """RFC 8785 JSON canonicalization for the values the fingerprint covers (integers, strings, lists, objects with ASCII
    keys, booleans, null): sorted keys, no whitespace, UTF-8."""
    if isinstance(x, float):
        if x != int(x):
            raise ValueError("non-integer numbers are not part of a fingerprint")
        x = int(x)
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


SET_TYPES = {"region", "cage", "cell", "quadruple", "appears", "count", "box", "row", "column", "negative",
             "neighbours"}  # fmt: skip


def _rc(name):
    return parse_cell(name)


def _holds(text):
    """a custom rule's expression in its canonical spelling (rules/custom.py); unchanged if it does not parse"""
    from ..rules import custom as CU

    try:
        return CU.canonical(text)
    except CU.LangError:
        return text


def _norm_rule(r, D):
    """spelling-free form of one rule for the fingerprint: cell sets sorted, symmetric pairs sorted"""
    r = {k: v for k, v in r.items() if k not in ("id", "label", "style")}
    srt = lambda xs: sorted((x.lower() for x in xs), key=_rc)
    t = r["type"]
    if (
        t in SET_TYPES
        or (t == "sum" and r.get("kind") in ("group", "corner"))
        or (t == "distinct_count" and "side" not in r)
        or (t == "edge" and r.get("kind") != "greater")
    ):
        if "cells" in r:
            r["cells"] = srt(r["cells"])
    if t == "custom":
        r["holds"] = _holds(r["holds"])
    if t == "equal_sum":
        r["segments"] = sorted((srt(x) for x in r["segments"]), key=lambda x: [_rc(c) for c in x])
    if "except" in r:
        r["except"] = sorted((srt(p) for p in r["except"]), key=lambda x: [_rc(c) for c in x])
    if t == "relation" and r["op"] not in DIRECTED_OPS:
        r["pairs"] = sorted((srt(p) for p in r["pairs"]), key=lambda x: [_rc(c) for c in x])
    return r


def semantic_subset(doc):
    """the fingerprinted content: board, digits, givens, placed digits, candidates and rules, with the houses replaced by the houses they
    state (grid, box_grid, box / row / column rules), so every spelling of the same houses gives
    the same result, and set-like cell lists sorted"""
    doc = with_origins(doc)
    keep = {k: doc[k] for k in ("format", "format_version", "digits", "givens", "placed", "candidates") if k in doc}
    keep["board"] = {"rows": doc["board"]["rows"], "cols": doc["board"]["cols"]}
    D = doc.get("digits")
    B = Board([divmod(k, doc["board"]["cols"]) for k, v in enumerate(doc["givens"]) if v is not None], D)
    HT = ("grid", "box_grid", "box", "row", "column")
    # a chaos rule states its rows / columns (houses) and stays a rule (its regions to find)
    houses, _ = read_houses([r for r in doc.get("rules", []) if r["type"] in HT + ("chaos",)], B)
    B.grid_origins = {r["origin"] for r in doc.get("rules", []) if r["type"] in ("grid", "box_grid", "chaos")}
    rules = [_norm_rule(r, D) for r in resolve_areas(B, doc.get("rules", [])) if r["type"] not in HT]
    hs = {(k, tuple(sorted((B.name(c) for c in cells), key=_rc))) for k, cells, _ in houses}
    rules += [{"type": {"col": "column"}.get(k, k), "cells": list(c)} for k, c in hs]
    keep["rules"] = sorted(rules, key=lambda r: jcs(r))
    return keep


def fingerprint_of_doc(doc, by_meaning=()):
    """SHA-256 of the JCS form of the semantic subset of an already canonical pencilmark-puzzle dict, with the pair
    tables and cell sets that state its pair and cell rules (puzzle-format.md 8.2) among the rules"""
    keep = semantic_subset(doc)
    keep["rules"] = sorted(keep["rules"] + list(by_meaning), key=jcs)
    return hashlib.sha256(jcs(keep).encode("utf-8")).hexdigest()
