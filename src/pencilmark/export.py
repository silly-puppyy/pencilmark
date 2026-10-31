"""Human-oriented exchange formats: one for the puzzle, one for its grade.

puzzle (format "sudoku-puzzle", format_version 1): specified in docs/FORMAT.md, implemented in pencilmark/exchange.py (strict
  reader, order-preserving writer, canonical text, fingerprint), schema docs/sudoku-puzzle.schema.json. In short: "board",
  "digits", flat "givens" (0 empty, null no cell), optional "solution" / "candidates", and "rules" holding every constraint,
  houses included ({"type": "box_grid", "origin": "r1c1", "box": [3, 3]} for a classic, {"type": "grid", ...} plus "box"
  rules for a jigsaw), cells
  named "r{row}c{col}"; "meta" is free-form information that never changes solving. Unknown keys / rule types are refused.

grade (format "sudoku-grade", format_version 1):
  grader      {"name": "pencilmark", "version": "1.0.0"}: the engine that made the card; a card from another version can differ
  difficulty  what a human feels per cell: continuous, above 0 (a nearly finished grid ~0.2), no ceiling; classic medians track Andrew Stuart's
              scale (data/card_score.json "map")
  time        minutes for today's median player (classic units x minutes_per_unit, data/time_model.json); on request
              time_pNN = the NN-th percentile over today's players and time_mean = the mean (log-normal, sigma spread_sigma)
  band        "Very Easy" … "Extreme" or "Unknown" (not solvable without computer search); on request band_index 0..6
  contains    what a solver meets going easy -> hard (band path): [{"code", "chip", "name", "band", "uses", "alternatives"}];
              a chip "XWG/KTE/SCL" = each of these alone also gets you through here; singles listed without counts
  notes       publishing notes: [{"code": "spike", "severity": "reject" | "note", "text": "…"}]
  steps       [{"n", "code", "name", "placement" ("r2c8=3"), "eliminations" (["r4c5#7"]), "explanation", "detail"}]
"""

from __future__ import annotations

import functools
import math
import time
from collections import Counter

from . import __version__
from . import metrics as MT
from . import registry as R
from . import solver as S
from .rules.edge import EDGE

GRADER_NAME, GRADER_VERSION = "pencilmark", __version__  # on every card: a grade is only meaningful with its engine
FORMAT_VERSION = 1  # of both formats; bumped only on a breaking change (additive fields don't bump it)
BANDS = R.BANDS
SITES = {
    "fed": "fed-sudoku.eu",
    "lisudoku": "lisudoku.com",
    "sudoku.coach": "sudoku.coach",
    "LMD": "logic-masters.de",
    "puzzleduel": "puzzleduel.club",
    "sudoku-variants": "sudoku-variants.com",
    "sudoku.one": "sudoku.one",
    "hard set": "sudokuwiki.org",
}
# named X-Chain shapes (data/patterns.csv): lower-case step name -> chip code, matched inside explainer pattern names
X_CHAIN_SHAPES = {p.step_name.lower(): p.code for p in R.patterns() if p.technique == "X-Chain" and p.code != "XCL"}


def _shape(name, specific):
    """(code, band) of a SPLIT technique step from its most specific name; None if the name doesn't decide. The band is
    the shape's (data/codes.csv shape_band)."""
    code = _shape_code(name, specific.lower())
    return None if code is None else (code, R.codes()[code].shape_band)


def _shape_code(name, sl):
    if name == "X-Chain":  # Skyscraper / 2-String Kite / Turbot / Empty Rectangle by name, else a long X-Chain
        return next((c for k, c in X_CHAIN_SHAPES.items() if k in sl), "XCL")
    if name == "X-Wing":  # plain row / column X-Wing, or Franken (a box as base or cover) / Mutant
        return "FRK" if "franken" in sl or "mutant" in sl else "XWG"
    if name == "FinnedFish":  # every finned / sashimi fish and Franken (box) fish
        if "franken" in sl or "mutant" in sl:
            return "FRK"
        for size, code in (("jellyfish", "FJF"), ("swordfish", "FSW"), ("x-wing", "FXW")):
            if size in sl:
                return code
        return None
    if name == "LawOfLeftovers":
        if "phistomefel" in sl:
            return "PHV" if "variant" in sl else "PHI"
        return "LOL"
    return None


def code_names():
    """chip code -> technique name (data/codes.csv)"""
    return {c: v.name for c, v in R.codes().items()}


def chip_of(tech_id, specific=None):
    """(chip code, band index) for a technique, using its most specific pattern name where the band depends on it:
    short X-Chains (Skyscraper / 2-String Kite / Turbot) Hard, longer ones Very Hard; Franken X-Wing Very Hard."""
    from .card import _code

    name = S.TECH_NAMES.get(tech_id, str(tech_id))
    code, _ = _code(name)
    # base band: the technique's (data/techniques.csv; it separates forms that share a code, e.g. direct innies / outies
    # Easy vs set-theory forms Medium)
    band = MT.band_of(tech_id)
    if specific and name in SPLIT:
        sh = _shape(name, specific)
        if sh:
            code, band = sh
    return code, band


# techniques whose band depends on the named shape (SPLIT): plain X-Wing, short X-Chains and basic set theory sit at
# the technique's band; Franken / Mutant X-Wings, long X-Chains and Phistomefel-type set theory at their shape's. The
# engine can't cap the shape it looks for, so band-limited solves allow them from the technique's band on and band_path
# checks the shapes actually used.
SINGLE_CODES = {t.code for t in R.techniques() if t.family == "singles"}  # no use counts on the card (GRADE.md 3)
SPLIT = tuple(t.name for t in R.techniques() if t.split)  # engine X-Wing includes Franken / Mutant 2-fish


def tech_band(t):
    """band index of an engine technique (data/techniques.csv; SPLIT techniques at their lowest shape's band)."""
    return MT.band_of(t)


META_KEYS = ("title", "author", "source", "id", "url", "date", "rules_text", "type", "license", "tags")


def read_meta(d):
    """metadata from a dict: its "meta" object plus known top-level keys (the keyword form of to_export), empty values dropped."""
    m = {k: d[k] for k in META_KEYS if k in d}
    m.update(d.get("meta") or {})
    order = {k: i for i, k in enumerate(META_KEYS)}  # known keys first, in a fixed order; free-form keys after
    return {k: m[k] for k in sorted(m, key=lambda k: (order.get(k, len(order)), k)) if m[k] not in (None, "", [], {})}


def export_puzzle(p, meta=None, solution=None, source=None, title=None, rules_text=None):
    """engine Puzzle -> "sudoku-puzzle" dict (format_version 1, docs/FORMAT.md; pencilmark/exchange.py). meta: free-form metadata
    dict; source / title / rules_text keywords are merged into meta."""
    from . import exchange as X

    m = read_meta({"source": source, "title": title, "rules_text": rules_text, "meta": meta})
    return X.write(p, meta=m, solution=solution)


def import_puzzle(d):
    """sudoku-puzzle (format_version 1, docs/FORMAT.md) -> puzzle JSON (pencilmark.puzzle_json), read strictly by
    pencilmark/exchange.py."""
    from . import exchange as X

    return X.to_internal(d)


def region_geometry(p):
    """type-free region geometry the time model reads : blob_cells = share of cells in 2-D complete
    groups that are not rectangles (jigsaw regions; diagonals are lines, excluded); extra_area_pc = 2-D complete groups per cell beyond
    one (windoku / centre-dot / extra regions). 0 / 0 on a standard grid."""
    from collections import Counter

    if not hasattr(p, "groups_of"):
        p.finalize()
    co = p.coords if isinstance(p.coords, list) else [p.coords[i] for i in range(p.N)]

    def rect(g):
        rs = [co[c][0] for c in g.cells]
        cs = [co[c][1] for c in g.cells]
        return (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1) == len(g.cells)

    def line(g):
        pts = [co[c] for c in g.cells]
        (r0, c0), (r1, c1) = pts[0], pts[1]
        return all((r - r0) * (c1 - c0) == (c - c0) * (r1 - r0) for r, c in pts)

    comp = [g for g in p.groups if g.complete and len(g.cells) > 1]
    blob = set(c for g in comp if not rect(g) and not line(g) for c in g.cells)
    area = Counter(c for g in comp if not line(g) for c in g.cells)
    return {"blob_cells": len(blob) / p.N, "extra_area_pc": sum(max(v - 1, 0) for v in area.values()) / p.N}


def time_units(effort_l1, empty_cells, geometry=None):
    """expected solving time in standard-classic units (1.0 = a median classic) from the grader model's time model
    (data/time_model.json): exp(const + k_effort * L1 + k_empty * ln(empty cells) + geometry) + t0, L1 = log of the priced
    step sum (card "effort_l1"); fitted on era-adjusted per-player times. None without the inputs."""
    import math

    T = _time_model()
    if not T or not empty_cells or effort_l1 is None:
        return None
    geo = sum(w * (geometry or {}).get(k, 0.0) for k, w in T.get("k_geometry", {}).items())  # scanning cost
    t = math.exp(T["const"] + T["k_effort"] * effort_l1 + T["k_empty"] * math.log(empty_cells) + geo) + T.get("t0", 0.0)
    cmp_ = T.get("compress")  # long predicted times grow more slowly (order-preserving)
    if cmp_ and t > 0:
        lt = math.log(t)
        t = math.exp(lt - cmp_["k"] * max(0.0, lt - cmp_["c"]))
    szc = T.get("size_curve")  # very large boards are slower per cell than the power law
    if szc and t > 0:  # (3 sources); 0 below ~92 empty cells
        t *= math.exp(szc["q"] * max(0.0, math.log(empty_cells) - szc["c"]) ** 2)
    return round(t, 2)


ALWAYS = ("format", "format_version", "grader")
DEFAULT_FIELDS = ("difficulty", "time", "band", "contains")
OPTIONAL_FIELDS = (
    "band_index",
    "time_p80",
    "time_dist",
    "elapsed",
    "issues",
    "reject",
    "warning",
    "se",
    "steps",
    "describe",
    "symmetry",
)  # + time_mean / time_pNN
EXPLAIN_LEVELS = ("notation", "short", "teach")  # terse to verbose: solvers' notation, one plain line, a short lesson


def _time_model():
    """the grader model's time model (data/time_model.json)"""
    from . import grader_model as GM

    return GM.default().time


def _is_variant(p):
    """any rule beyond rows / columns / boxes (multi-grid layouts count as classic)"""
    return (
        bool(getattr(p, "relations", None))
        or bool(getattr(p, "constraints", None))
        or any(getattr(g, "kind", "row") not in ("row", "col", "box") for g in getattr(p, "groups", ()))
    )


def _sigmas(variant):
    """(sigma_players, sigma_model) of the log-normal time distribution (data/time_model.json)"""
    tm = _time_model()
    k = "variant" if variant else "classic"
    return tm.get(f"spread_sigma_{k}"), tm.get(f"model_sigma_{k}")


def _time_stat(field, variant=False):
    """time_mean / time_p1 .. time_p99 -> the log ratio to the median time; None for any other key"""
    import re

    sg = _sigmas(variant)[0]
    if field == "time_mean":
        return sg * sg / 2
    m = re.fullmatch(r"time_p([1-9][0-9]?)", field)
    if not m:
        return None
    from statistics import NormalDist

    return NormalDist().inv_cdf(int(m.group(1)) / 100) * sg or 0.0


def card_fields(fields=None, steps=False, se=False):
    """the field mask (GRADE.md 2): the requested top-level card keys; None = the default fields. format,
    format_version and grader are always present. steps=True / se=True are shorthands."""
    out = set(DEFAULT_FIELDS) if fields is None else set(fields) - set(ALWAYS)
    bad = {f for f in out - set(DEFAULT_FIELDS) - set(OPTIONAL_FIELDS) if _time_stat(f) is None}
    if bad:
        raise ValueError(f"unknown card field(s) {sorted(bad)}; known: {list(DEFAULT_FIELDS) + list(OPTIONAL_FIELDS)}")
    if steps:
        out.add("steps")
    if se:
        out.add("se")
    return out


def explain_levels(explain):
    """explain= option -> the step explanation levels: None / False = none, True = all, "notation" / "short" / "teach" or a list"""
    if not explain:
        return []
    if explain is True:
        return list(EXPLAIN_LEVELS)
    lv = [explain] if isinstance(explain, str) else list(explain)
    bad = [x for x in lv if x not in EXPLAIN_LEVELS]
    if bad:
        raise ValueError(f"unknown explanation level(s) {bad}; known: {list(EXPLAIN_LEVELS)}")
    return [x for x in EXPLAIN_LEVELS if x in lv]


RULE_NOUN = {
    ("line", None): "line",
    **{("edge", k): v.noun for k, v in EDGE.items()},  # rules/edge.py
    ("region", "diagonal"): "diagonal",
    ("region", "window"): "window",
    ("region", "disjoint"): "disjoint group",
    ("region", "extra"): "extra region",
    ("region", "colour"): "colour group",
    ("cage", None): "cage",
    ("arrow", None): "arrow",
    ("cell", None): "cell clue",
    ("neighbours", None): "neighbour rule",
    ("negative", None): "negative constraint",
    ("table", None): "table rule",
    ("relation", None): "pair rule",
    ("corner", None): "corner clue",
    ("sum", None): "sum clue",
    ("contains", None): "quadruple",
    ("appears", None): "arrow clue",
}


def _noun(rules):
    names = []
    for r in rules:
        t, k = r["type"], r.get("kind")
        n = (
            RULE_NOUN.get((t, k))
            or (
                f"{k.replace('_', ' ')} line"
                if t == "line"
                else {
                    "antiknight": "anti-knight rule",
                    "antiking": "anti-king rule",
                    "nonconsecutive": "non-consecutive rule",
                }.get(k)
                if t == "neighbours" and k
                else None
            )
            or RULE_NOUN.get((t, None))
            or t.replace("_", " ")
        )
        if n not in names:
            names.append(n)
    return " / ".join(names) or "rule"


def _issues(p, card, doc, prov):
    """card notes -> issues [{"code", "severity": "reject" | "warning", "text", "rules"?}] (GRADE.md 4). Rule notes
    point at the exported file's rule indices (doc = exchange.write(p) as to_export writes it)."""
    out = []
    raw = card.get("notes") or []
    cls_map = None
    for n in raw:
        code, sev, text = n[0], n[1], n[2]
        e = {"code": code, "severity": "reject" if sev == "reject" else "warning", "text": text}
        if len(n) >= 5 and doc is not None:
            c, used = n[3], n[4]
            if cls_map is None:
                from . import usage as U

                try:
                    cls_map = U.element_classes(p)
                except Exception:
                    cls_map = {}
            obj = cls_map.get(c) or {}
            gnames = set(obj.get("groups") or [])
            gidx = {k for k, g in enumerate(p.groups) if g.name in gnames}
            cons = set(obj.get("constraints") or [])
            want = Counter(tuple(r) for r in obj.get("relations") or [])
            rpos = set()
            for k, r in enumerate(p.relations):
                if want[tuple(r)] > 0:
                    want[tuple(r)] -= 1
                    rpos.add(k)
            idx = [
                i
                for i, pr in enumerate(prov)
                if (pr.get("groups", set()) & gidx)
                or (pr.get("constraints", set()) & cons)
                or (pr.get("relations", set()) & rpos)
                or (c.startswith("shading") and pr.get("clues"))
            ]
            if idx:
                rs = [doc["rules"][i] for i in idx]
                what = _noun(rs) + ("s" if len(idx) > 1 and " / " not in _noun(rs) else "")
                where = f"rule {idx[0]}" if len(idx) == 1 else "rules " + ", ".join(map(str, idx))
                if code == "decorative":
                    e["text"] = f"{what} ({where}): not needed for uniqueness and never used by the solve"
                elif code == "redundant":
                    e["text"] = (
                        f"{what} ({where}): used in {used} step{'s' if used != 1 else ''}, but the puzzle is unique without it"
                    )
                else:
                    e["text"] = f"{what} ({where}): used in only {used} step{'s' if used != 1 else ''} of the solve"
                e["rules"] = idx
                ids = [doc["rules"][i]["id"] for i in idx if "id" in doc["rules"][i]]
                if ids:
                    e["ids"] = ids
        out.append(e)
    return out


def symmetry_of(p):
    """symmetries of the givens pattern (and board shape): [{"kind", "axis"?, "of": "givens"}]. Rule symmetry ("of": "all")
    is not detected yet."""
    co = [tuple(x) for x in p.coords]
    R = max(r for r, _ in co) + 1
    C = max(c for _, c in co) + 1
    cells = set(co)
    giv = {co[i] for i in p.givens}
    tf = {
        ("rot180", None): lambda r, c: (R - 1 - r, C - 1 - c),
        ("mirror", "vertical"): lambda r, c: (r, C - 1 - c),
        ("mirror", "horizontal"): lambda r, c: (R - 1 - r, c),
    }
    if R == C:
        tf.update(
            {
                ("rot90", None): lambda r, c: (c, R - 1 - r),
                ("mirror", "diagonal"): lambda r, c: (c, r),
                ("mirror", "antidiagonal"): lambda r, c: (C - 1 - c, R - 1 - r),
            }
        )
    out = []
    for (kind, axis), f in tf.items():
        if all(f(*x) in cells for x in cells) and all(f(*x) in giv for x in giv):
            out.append(dict({"kind": kind}, **({"axis": axis} if axis else {}), of="givens"))
    return out


class _CardContext:
    """what the card's fields are built from: the stages' results (card route, technique-list route) and values several
    fields share, computed on first use"""

    def __init__(self, p, P, want, card, bp, alternatives, levels, base=None):
        self.p, self.P, self.want, self.card, self.bp = p, P, want, card, bp
        self.base = base  # the first band route (band_path(p, P)), which the technique list shrinks
        self.alternatives, self.levels = alternatives, levels
        self.unknown = not bp["solved"]

    @functools.cached_property
    def time_units(self):
        return time_units(self.card.get("effort_l1"), self.p.N - len(self.p.givens), geometry=region_geometry(self.p))

    @functools.cached_property
    def variant(self):
        return _is_variant(self.p)

    @functools.cached_property
    def doc(self):
        """(exported file, provenance) for the rule indices issues point at and for describe; (None, None) on failure"""
        try:
            from . import exchange as X

            return X.write(self.p, provenance=True)
        except Exception:
            return None, None


def _f_time(c):
    tm = c.time_units  # minutes for today's median player (classic units x minutes_per_unit, data/time_model.json)
    return {"time": round(tm * _time_model().get("minutes_per_unit", 1.0), 1) if tm is not None else None}


def _f_time_stat(c, f):
    """time_mean / time_pNN: spread over today's players around the median (data/time_model.json)"""
    tm, lr = c.time_units, _time_stat(f, c.variant)
    return (
        round(tm * math.exp(lr) * _time_model().get("minutes_per_unit", 1.0), 1)
        if tm is not None and lr is not None
        else None
    )


def _f_time_dist(c):
    sp, sm = _sigmas(c.variant)  # the distribution's parameters: log-normal around the median time
    return {
        "time_dist": None if c.time_units is None else {"type": "lognormal", "sigma_players": sp, "sigma_model": sm}
    }


def _f_contains(c):
    from . import band_path as BP

    bp = c.bp
    names = {}
    for st in bp["steps"]:
        names.setdefault(st["code"], Counter())[st["name"]] += 1
    uses = Counter(bp["profile"])  # folded: full houses count under the listed single
    bandof = {st["code"]: st["band"] for st in bp["steps"]}
    alts = bp.get("alternatives", {})
    contains = []
    for code, n in sorted(uses.items(), key=lambda x: (bandof.get(x[0], 0), BP._order(x[0]), x[0])):
        e = {
            "code": code,
            "chip": "/".join([code] + alts.get(code, [])),
            "name": names[code].most_common(1)[0][0],
            "band": bandof.get(code, 0),
        }
        if not c.alternatives:
            e["alternatives"] = None  # not searched (alternatives=False); absent = searched, none found
        elif alts.get(code):
            e["alternatives"] = alts[code]  # each of these alone also gets you through (not on code's subset chain)
        if code not in SINGLE_CODES:
            e["uses"] = n  # on the easiest route; singles' counts swing with the route, so omitted
        contains.append(e)
    out = {"contains": contains}
    if c.unknown:
        out["stopped_at_step"] = len(bp["steps"]) + 1
    return out


def _f_issues(c):
    """issues, and the reject / warning flags derived from them (each only when asked for)"""
    doc, prov = c.doc
    issues = _issues(c.p, c.card, doc, prov or [])
    out = {"issues": issues} if "issues" in c.want else {}
    for f in ("reject", "warning"):
        if f in c.want:
            out[f] = any(i["severity"] == f for i in issues)
    return out


def _f_describe(c):
    from .variants import describe as _describe

    doc, _ = c.doc
    return {"describe": _describe(doc) if doc is not None else None}


def _f_se(c):
    from . import band_path as BP
    from . import se as SE

    sb = c.base if c.base is not None else BP.band_path(c.p, c.P)  # the card's first route: not computed again
    return {"se": SE.ratings(sb["steps"], scale="classic") if sb["solved"] else None}


def _f_steps(c):
    from . import band_path as BP

    p, bp, levels = c.p, c.bp, c.levels
    cn = lambda x: f"r{p.coords[x][0] + 1}c{p.coords[x][1] + 1}"
    expl = BP.explain_steps(p, c.P, bp["steps"]) if levels else [None] * len(bp["steps"])
    rows = []
    for i, st in enumerate(bp["steps"]):
        r = {"n": i + 1, "code": st["code"], "name": st["name"], "band": st["band"]}
        if st["place"]:
            r["placement"] = f"{cn(st['place'][0])}={st['place'][1]}"
        if st["elims"]:
            r["eliminations"] = [f"{cn(x)}#{d}" for x, d in st["elims"]]
        if levels and expl[i]:
            r["explanation"] = {x: expl[i][x] for x in levels if expl[i].get(x)}
        rows.append(r)
    return {"steps": rows}


# the card-field registry (GRADE.md 2): field -> builder, in the card's key order. "time_*" stands for time_mean and
# every time_pNN asked for; "issues" also builds reject / warning. format, format_version, grader (always), elapsed
# (rate) and completed (max_seconds) are set outside it.
FIELDS = [
    ("difficulty", lambda c: {"difficulty": c.card.get("score")}),
    ("time", _f_time),
    ("time_*", _f_time_stat),
    ("time_dist", _f_time_dist),
    ("band", lambda c: {"band": "Unknown" if c.unknown else c.bp["band"]}),
    ("band_index", lambda c: {"band_index": None if c.unknown else c.bp["band_index"]}),
    ("contains", _f_contains),
    ("issues", _f_issues),
    ("describe", _f_describe),
    ("symmetry", lambda c: {"symmetry": symmetry_of(c.p)}),
    ("se", _f_se),
    ("steps", _f_steps),
]


def grade(p, P, card=None, with_steps=None, max_seconds=None, fields=None, explain=None, alternatives=True):
    """grade() under max_seconds, stage by stage: the technique list (contains) truncates at the limit as before; the difficulty
    route stops at its own limit (engine deadline) and the card is then band "Unknown" with difficulty / time null, the
    techniques found so far in contains and "stopped": "time limit" (GRADE.md 1)."""
    t0 = time.perf_counter()
    g, expired = _grade(
        p,
        P,
        card=card,
        with_steps=with_steps,
        max_seconds=max_seconds,
        fields=fields,
        explain=explain,
        alternatives=alternatives,
    )
    if expired:
        for k in list(g):
            if k in ("difficulty", "time", "band_index", "time_dist", "time_mean") or k.startswith("time_p"):
                g[k] = None
        if "band" in g:
            g["band"] = "Unknown"
        g["completed"] = False
    if (
        fields is not None and "elapsed" in fields
    ):  # wall-clock seconds of this grading call (rate() adds the uniqueness proof)
        g["elapsed"] = round(time.perf_counter() - t0, 3)
    return g


_OUTER_END = [
    None
]  # rate() sets the shared wall-clock end (time.time() value) for the whole call; grade() alone owns its own


def _grade(p, P, card=None, with_steps=None, max_seconds=None, fields=None, explain=None, alternatives=True):
    """sudoku-grade card (GRADE.md), only the requested fields (card_fields). explain: step explanation levels
    (explain_levels). with_steps=True is shorthand for the steps field with both explanation levels."""
    from . import band_path as BP
    from . import card as K

    want = card_fields(fields, steps=bool(with_steps))
    expired = False
    bp_cut = [False]  # the technique-list stage hit max_seconds (the card itself may still be complete)
    levels = explain_levels(True if with_steps and explain is None else explain)
    P = dict(P, search=P.get("search", "human"))
    import time

    from . import cbackend as CB

    has_dl = hasattr(CB._C, "set_deadline")
    timed = max_seconds is not None and has_dl
    own = (
        timed and _OUTER_END[0] is None
    )  # called directly (CLI): this call owns the deadline; under rate() it is shared
    if own:
        CB._C.set_deadline(float(max_seconds))
    t_end = None if max_seconds is None else (_OUTER_END[0] or time.time() + float(max_seconds))
    hit = lambda: timed and CB._C.deadline_hit()
    need_list = bool(want & {"contains", "issues", "reject", "warning"})
    checks = bool(
        want & {"issues", "reject", "warning"}
    )  # publishing checks read the shortest list's required techniques: list first
    try:
        base = BP.band_path(p, P)  # the band (first route; shrinking keeps it)

        def make_card(route):
            req_b = list(dict.fromkeys(st["technique"] for st in route["steps"] if st["band"] > 0))
            try:
                return K.grade_card(p, P, (route["band"] if route["solved"] else "Unknown", req_b), check_rules=checks)
            except Exception:
                if not hit():
                    raise
                return {}  # max_seconds passed inside the card route

        if card is None and not checks:  # 1) band + difficulty / time first: they get the time they need
            card = make_card(base)
            expired = hit()
        if need_list and not expired:  # 2) the shortest technique list in the time that is left (truncates)
            bp = BP.contents(p, P, alternatives=alternatives, deadline=t_end, base=base)
            if hit():
                bp_cut[0] = True
        else:
            bp = dict(base, removed=[], alternatives={})
        if card is None:  # publishing checks: the card after the list (they read its techniques)
            card = make_card(bp)
            expired = hit()
    finally:
        if own:
            CB._C.set_deadline(0.0)
    c = _CardContext(p, P, want, card, bp, alternatives, levels, base=base)
    g = {
        "format": "sudoku-grade",
        "format_version": FORMAT_VERSION,
        "grader": {"name": GRADER_NAME, "version": GRADER_VERSION},
    }
    for name, build in FIELDS:  # registry order is the card's key order
        if name == "time_*":
            for f in sorted(
                (f for f in want if f.startswith("time_") and f != "time_dist"),
                key=lambda f: (f != "time_mean", len(f), f),
            ):
                g[f] = build(c, f)
        elif name in want or (name == "issues" and want & {"reject", "warning"}):
            g.update(build(c))
    if max_seconds is not None:  # with a limit only (always true without one): every stage finished within it
        g["completed"] = not (expired or bp_cut[0] or bool(bp.get("truncated")))
    return g, expired
