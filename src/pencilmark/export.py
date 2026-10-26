"""Human-oriented exchange formats: one for the puzzle, one for its grade.

puzzle (format "sudoku-puzzle", format_version 1): specified in docs/FORMAT.md, implemented in pencilmark/exchange.py (strict
  reader, order-preserving writer, canonical text, fingerprint), schema docs/sudoku-puzzle.schema.json. In short: "board",
  "digits", flat "givens" (0 empty, null no cell), optional "solution" / "candidates", and "rules" holding every constraint,
  houses included ({"type": "box_grid", "origin": "r1c1", "box": [3, 3]} for a classic, {"type": "grid", ...} plus "box"
  rules for a jigsaw), cells
  named "r{row}c{col}"; "meta" is free-form information that never changes solving. Unknown keys / rule types are refused.

grade (format "sudoku-grade", format_version 1):
  grader      {"name": "pencilmark", "version": "1.0.0"}: the engine that made the card; a card from another version can differ
  difficulty  what a human feels per cell: continuous, floor 0 (one empty cell), no ceiling; classic medians track Andrew Stuart's
              scale (data/card_score.json "map")
  time        minutes for today's average player (classic units x minutes_per_unit, data/time_model.json); time_p80 = the
              80th percentile (1.53 x)
  band        "Very Easy" … "Extreme" or "Unknown" (not solvable without computer search); band_index 0..5 (null for Unknown)
  contains    what a solver meets going easy -> hard (band path): [{"code", "chip", "name", "band", "uses", "alternatives"}];
              a chip "XWG/KTE/SCL" = each of these alone also gets you through here; singles listed without counts
  notes       publishing notes: [{"code": "spike", "severity": "reject" | "note", "text": "…"}]
  steps       [{"n", "technique", "chip", "placement" ("r2c8=3"), "eliminations" (["r4c5#7"]), "explanation", "detail"}]
"""
from __future__ import annotations

import csv
import io
import json
import math
from collections import Counter
from pathlib import Path

from . import _data, cbackend as CB, solver as S, metrics as MT, puzzle_json as PJ

GRADER_NAME, GRADER_VERSION = "pencilmark", "1.0.0rc1"   # on every card: a grade is only meaningful with the engine that made it
FORMAT_VERSION = 1          # of both formats; bumped only on a breaking change (additive fields don't bump it)
BANDS = ["Very Easy", "Easy", "Medium", "Hard", "Very Hard", "Extreme"]
SITES = {"fed": "fed-sudoku.eu", "lisudoku": "lisudoku.com", "sudoku.coach": "sudoku.coach", "LMD": "logic-masters.de",
         "puzzleduel": "puzzleduel.club", "sudoku-variants": "sudoku-variants.com", "sudoku.one": "sudoku.one",
         "hard set": "sudokuwiki.org"}
# shape names (explainer pattern or technique name) -> chip code; Medium shapes of the SPLIT techniques
X_CHAIN_SHAPES = {"skyscraper": "SKY", "2-string kite": "KTE", "turbot fish": "TUR", "empty rectangle": "ERE"}


def _shape(name, specific):
    """(code, band) of a SPLIT technique step from its most specific name; None if the name doesn't decide."""
    sl = specific.lower()
    if name == "X-Chain":       # Skyscraper / 2-String Kite / Turbot / Empty Rectangle Medium; longer chains Hard
        for k, c in X_CHAIN_SHAPES.items():
            if k in sl:
                return c, 2
        return "XCL", 3
    if name == "X-Wing":        # plain row / column X-Wing Medium; Franken (a box as base or cover) / Mutant Hard
        if "franken" in sl or "mutant" in sl:
            return "FRK", 3
        return "XWG", 2
    if name == "FinnedFish":    # finned / sashimi X-Wing Medium; Franken (box) fish and larger finned fish Hard
        if "franken" in sl or "mutant" in sl:
            return "FRK", 3
        if "jellyfish" in sl:
            return "FJF", 3
        if "swordfish" in sl:
            return "FSW", 3
        if "x-wing" in sl:
            return "FXW", 2
        return None
    if name == "LawOfLeftovers":
        if "phistomefel" in sl:
            return ("PHV" if "variant" in sl else "PHI"), 3
        return "LOL", 2
    return None
_BAND = None


def _band_table():
    """technique display name -> band index, from the accepted proposal (docs/technique_bands_proposal.csv)."""
    global _BAND
    if _BAND is None:
        _BAND = {}
        if _data.exists("technique_bands.csv"):
            for r in csv.DictReader(io.StringIO(_data.read_text("technique_bands.csv"))):
                b = r["proposed"]
                _BAND[r["technique"]] = BANDS.index(b) if b in BANDS else None
    return _BAND


def chip_of(tech_id, specific=None):
    """(chip code, band index) for a technique, using its most specific pattern name where the band depends on it:
    short X-Chains (Skyscraper / 2-String Kite / Turbot) Medium, longer ones Hard; finned X-Wing Medium, larger Hard."""
    from .card import _code
    name = S.TECH_NAMES.get(tech_id, str(tech_id))
    code, disp = _code(name)
    # base band from the engine-name map (metrics._BAND_BY_NAME, the accepted proposal; it separates forms that share
    # a code, e.g. direct innies/outies Easy vs set-theory forms Medium); computer search stays Unknown (None)
    band = None if _band_table().get(disp, 0) is None else MT._BAND_BY_NAME.get(name, MT.band_of(tech_id))
    if specific and name in SPLIT:
        sh = _shape(name, specific)
        if sh:
            code, band = sh
    return code, band


def _solved(p, P, disabled):
    st, ok = CB.solve(p, P, disabled=disabled)
    filled = len(p.givens) + sum(1 for s in st if s.move.place)
    return filled == p.N and not any(s.move.feat[0] == S.GUESS for s in st), st


# concept families for joint chips (technique map): alternatives inside one concept give ONE chip (the simplest);
# a joint chip only joins different concepts
CONCEPT = {}
for _c, _names in {
    "singles": ["FullHouse", "NakedSingle(direct)", "HiddenSingle(direct)", "NakedSingle(notes)", "HiddenSingle(notes)",
                "ConstraintSingle(direct)", "LineSingle(direct)"],
    "intersections": ["LockedCandidates", "NakedSingle+Pointing(direct)", "HiddenSingle+Pointing(direct)", "SnyderSingle"],
    "subsets": ["NakedPair", "HiddenPair", "NakedTriple", "HiddenTriple", "MentalSingle(direct)", "MentalNotesSingle"],
    "variant combinations": ["CageCombination", "SumCombination", "ArrowCombination", "SetCombination", "Innie/Outie(direct)",
                             "PairwiseConstraint", "TableCombination", "LineRange", "LineScan", "LineClass", "SandwichCombination",
                             "XSumCombination", "SkyscraperCombination", "CountCombination"],
    "single-digit patterns": ["X-Wing", "X-Chain", "EmptyRectangle", "Coloring", "FinnedFish", "MultiColouring"],
    "variant implications": ["EqualDigits", "DigitCount", "LawOfLeftovers", "EqualSumCombination", "ComboLock", "RuleIntersection",
                             "ImpliedHouses", "Domino", "ClassCount", "SumBound", "Innie/Outie(notes)", "Innie/Outie(sum)"],
    "fish": ["Swordfish", "Jellyfish"],
    "wings": ["XYZ-Wing", "WXYZ-Wing"],     # XY-Wing is a 3-cell XY-Chain: subsumed, so it sits with the chains
    "uniqueness": ["UniqueRectangle", "BUG+1", "GurthSymmetry"],
    "multi-digit chains": ["XY-Wing", "XY-Chain", "RemotePairs", "ChuteRemotePairs", "3DMedusa", "MentalChain(direct)", "ColourAlgebra"],
    "quads": ["NakedQuad", "HiddenQuad"],
    "advanced variant logic": ["SumAlgebra", "WeightedSums", "BandLogic", "Fireworks", "ComboPositions", "CliqueHouse", "LineSets", "LineClues"],
    "inference chains": ["AIC", "NiceLoop(discontinuous)"],
    "ALS": ["ALS-XZ", "ALS-XY-Wing", "SueDeCoq", "AlignedPairExclusion", "ALS-AIC", "DeathBlossom"],
    "case work": ["CaseAnalysis", "EitherWay", "WhatIf", "ShortTrial"],
}.items():
    for _n in _names:
        CONCEPT[_n] = _c


def concept_of(t):
    return CONCEPT.get(S.TECH_NAMES.get(t, ""), S.TECH_NAMES.get(t, str(t)))


_ORDER = None


def _order_table():
    """chip code -> order within its band (docs/technique_bands_proposal.csv): simplest first."""
    global _ORDER
    if _ORDER is None:
        _ORDER = {}
        if _data.exists("technique_bands.csv"):
            for r in csv.DictReader(io.StringIO(_data.read_text("technique_bands.csv"))):
                _ORDER.setdefault(r["code"], float(r["order"] or 99))
    return _ORDER


def _specific_in(p, steps, t):
    """most specific pattern name the explainer gives technique t's steps in this solve (e.g. Skyscraper)."""
    from . import explain as E
    c = Counter()
    try:
        for i, step, state in E.replay(p, steps):
            if step.move.feat[0] == t:      # the pattern ("Sashimi Franken X-Wing") is more specific than the name
                ti = E.explain(step, p, state)["technique"]
                nm = ti.get("pattern") or ti.get("name")
                if nm: c[nm] += 1
    except Exception:
        return None
    return c.most_common(1)[0][0] if c else None


# techniques whose band depends on the named shape: plain X-Wing / short X-Chains / finned X-Wing / basic set theory
# Medium; Franken / Mutant X-Wings, long X-Chains, larger finned fish and Phistomefel-type set theory Hard. The engine can't cap the shape it looks for, so
# band-limited solves allow them from Medium on and required_chips checks the shapes actually used.
SPLIT = ("X-Wing", "X-Chain", "FinnedFish", "LawOfLeftovers")   # engine X-Wing includes Franken / Mutant 2-fish


def tech_band(t):
    """band index of an engine technique under the accepted proposal (SPLIT techniques at their lower, Medium level)."""
    if S.TECH_NAMES.get(t) in SPLIT:
        return 2
    code, b = chip_of(t)
    return b if b is not None else 9


def _split_hard(p, steps, techs):
    """SPLIT techniques of `techs` used in `steps` with a Hard shape (by the explainer's pattern name)."""
    out = set()
    for t in techs:
        if S.TECH_NAMES.get(t) in SPLIT and any(s.move.feat[0] == t for s in steps):
            nm = _specific_in(p, steps, t)
            if nm and chip_of(t, nm)[1] == 3:
                out.add(t)
    return out


def required_chips(p, P, steps=None, specific_by_step=None):
    """Band-limited requirement. B = the lowest band whose techniques solve the puzzle (human mode). Within that limit
    a technique is required if switching it off leaves the puzzle unsolvable; if a technique of ANOTHER family can
    replace it (and switching off both fails) the chip is joint ("XWG/SCL"); interchangeable techniques of the same
    family give one chip for the cheapest used. -> (band index or None, chips)"""
    notes = set(getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,)))
    singles = {t for nm, ts in MT.FAMILIES if nm == "singles" for t in ts}
    ALL = set(S.TECH_NAMES)
    comp = set(CB.search_disabled(dict(P, search="human"))) | {S.GUESS}
    techs = [t for t in ALL if t not in comp and t not in notes]
    def run(allowed):
        return _solved(p, P, ALL - (set(allowed) | notes))
    B, stB, allowedB = None, None, None
    for b in range(6):
        allowed = {t for t in techs if tech_band(t) <= b}
        ok, st = run(allowed)
        while ok and b == 2:   # Medium only if no Hard-shaped X-Chain / finned fish / set theory is needed
            hard = _split_hard(p, st, allowed)
            if not hard:
                break
            allowed -= hard
            ok, st = run(allowed)
        if ok:
            B, stB, allowedB = b, st, allowed
            break
    if B is None:
        return None, []
    uses = Counter(s.move.feat[0] for s in stB if s.move.feat[0] not in notes | singles)
    spec = {}
    if specific_by_step is not None:
        for i, s in enumerate(stB):
            nm = specific_by_step.get(i)
            if nm: spec.setdefault(s.move.feat[0], Counter())[nm] += 1
    if specific_by_step is None:
        for t in uses:
            if S.TECH_NAMES.get(t) in SPLIT:
                nm = _specific_in(p, stB, t)
                if nm: spec[t] = Counter({nm: 1})
    sp = lambda t: spec[t].most_common(1)[0][0] if t in spec else None
    chips, seen = [], set()
    for t in sorted(uses, key=lambda t: -tech_band(t)):
        ok, st2 = run(allowedB - {t})
        if not ok:
            c, b = chip_of(t, sp(t)); chips.append({"chip": c, "band": b, "uses": uses[t]}); continue
        new = {x.move.feat[0] for x in st2 if x.move.feat[0] not in notes | singles} - set(uses)
        cross = {a for a in new if concept_of(a) != concept_of(t)}
        key = frozenset({t} | cross)
        if cross and key not in seen:
            seen.add(key)
            if not run(allowedB - {t} - cross)[0]:
                parts = [chip_of(t, sp(t))] + [chip_of(a) for a in sorted(cross)]
                chips.append({"chip": "/".join(c for c, _ in parts), "band": min(b for _, b in parts if b is not None),
                              "uses": uses[t], "joint": True})
    # the needed band's chip: each band-B technique ALONE (with everything below B), simplest first; different
    # families that each suffice -> joint chip (simplest per family); none alone -> the used ones (fallback below)
    if B > 0:
        order = _order_table()
        lower = {t for t in allowedB if tech_band(t) < B}
        cand = [t for t in allowedB if tech_band(t) == B]
        if B == 3:   # at Hard the SPLIT techniques are candidates in their Hard shapes, not free helpers below
            split = {t for t in lower if S.TECH_NAMES.get(t) in SPLIT}
            lower -= split
            cand += sorted(split)
        cand.sort(key=lambda t: order.get(chip_of(t)[0], 99))
        suff = []
        for t in cand:
            ok, st1 = run(lower | {t})
            if ok and B == 2 and _split_hard(p, st1, {t}):
                ok = False      # solves only with a Hard shape: not a Medium way through
            if ok:
                suff.append((t, st1))
        if suff:
            by_fam = {}
            for t, st1 in suff:
                by_fam.setdefault(concept_of(t), (t, st1))
            parts = []
            for t, st1 in sorted(by_fam.values(), key=lambda x: order.get(chip_of(x[0])[0], 99)):
                nm = None
                if S.TECH_NAMES.get(t) in SPLIT:
                    nm = _specific_in(p, st1, t)
                parts.append(chip_of(t, nm) + (sum(1 for x in st1 if x.move.feat[0] == t),))
            chips = [c for c in chips if c["band"] != B]
            chips.append({"chip": "/".join(c for c, _, _ in parts), "band": B, "uses": parts[0][2],
                          **({"joint": True} if len(parts) > 1 else {})})
    if B > 0 and not any(c["band"] == B for c in chips):     # band needed, but only interchangeable same-family ways
        top = [t for t in uses if tech_band(t) == B or (B == 3 and S.TECH_NAMES.get(t) in SPLIT and chip_of(t, sp(t))[1] == 3)]
        if top:
            t = min(top, key=lambda t: (MT.band_of(t), -uses[t]))
            c, b = chip_of(t, sp(t)); chips.append({"chip": c, "band": B, "uses": uses[t]})
    chips.sort(key=lambda c: (-(c["band"] if c["band"] is not None else -1), c["chip"]))
    return B, chips


META_KEYS = ("title", "author", "source", "id", "url", "date", "rules_text", "type", "license", "tags")


def read_meta(d):
    """metadata from a dict: its "meta" object plus known top-level keys (the keyword form of to_export), empty values dropped."""
    m = {k: d[k] for k in META_KEYS if k in d}
    m.update(d.get("meta") or {})
    order = {k: i for i, k in enumerate(META_KEYS)}         # known keys first, in a fixed order; free-form keys after
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


_TIME = None


def region_geometry(p):
    """type-free region geometry the time model reads : blob_cells = share of cells in 2-D complete
    groups that are not rectangles (jigsaw regions; diagonals are lines, excluded); extra_area_pc = 2-D complete groups per cell beyond
    one (windoku / centre-dot / extra regions). 0 / 0 on a standard grid."""
    from collections import Counter
    if not hasattr(p, "groups_of"): p.finalize()
    co = p.coords if isinstance(p.coords, list) else [p.coords[i] for i in range(p.N)]
    def rect(g):
        rs = [co[c][0] for c in g.cells]; cs = [co[c][1] for c in g.cells]
        return (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1) == len(g.cells)
    def line(g):
        pts = [co[c] for c in g.cells]; (r0, c0), (r1, c1) = pts[0], pts[1]
        return all((r - r0) * (c1 - c0) == (c - c0) * (r1 - r0) for r, c in pts)
    comp = [g for g in p.groups if g.complete and len(g.cells) > 1]
    blob = set(c for g in comp if not rect(g) and not line(g) for c in g.cells)
    area = Counter(c for g in comp if not line(g) for c in g.cells)
    return {"blob_cells": len(blob) / p.N, "extra_area_pc": sum(max(v - 1, 0) for v in area.values()) / p.N}


def time_units(effort_l1, empty_cells, difficulty=None, geometry=None):
    """expected solving time in standard-classic units (1.0 = a median classic) from data/time_model.json:
    exp(const + k_effort * L1 + k_empty * ln(empty cells)), L1 = log of the priced step sum (card "effort_l1"); fitted on
    era-adjusted per-player times. Files with k_difficulty instead of k_effort use the card difficulty.
    None without the file or the inputs."""
    global _TIME
    if _TIME is None:
        _TIME = _data.load_json("time_model.json") if _data.exists("time_model.json") else {}
    import math
    if not _TIME or not empty_cells:
        return None
    if "k_effort" in _TIME:
        if effort_l1 is None:
            return None
        geo = sum(w * (geometry or {}).get(k, 0.0) for k, w in _TIME.get("k_geometry", {}).items())   # scanning cost
        t = math.exp(_TIME["const"] + _TIME["k_effort"] * effort_l1 + _TIME["k_empty"] * math.log(empty_cells) + geo) \
            + _TIME.get("t0", 0.0)                       # t0: per-puzzle start-up overhead
        sat = _TIME.get("saturation")                    # effort grows less per point above difficulty s0 (off:
        if sat and difficulty is not None:               # reversed within-type order where most puzzles score > s0; key disabled)
            t *= math.exp(sat["g"] * max(0.0, difficulty - sat["s0"]))
        cmp_ = _TIME.get("compress")                     # long predicted times grow more slowly (order-preserving)
        if cmp_ and t > 0:
            lt = math.log(t)
            t = math.exp(lt - cmp_["k"] * max(0.0, lt - cmp_["c"]))
        szc = _TIME.get("size_curve")                    # very large boards are slower per cell than the power law
        if szc and t > 0:                                # (3 sources); 0 below ~92 empty cells
            t *= math.exp(szc["q"] * max(0.0, math.log(empty_cells) - szc["c"]) ** 2)
        return round(t, 2)
    if difficulty is None:
        return None
    return round(math.exp(_TIME["const"] + _TIME["k_difficulty"] * difficulty + _TIME["k_empty"] * math.log(empty_cells)), 2)


DEFAULT_FIELDS = ("grader", "format", "format_version", "difficulty", "time", "band", "band_index", "contains", "issues",
                  "reject")
OPTIONAL_FIELDS = ("time.p80", "se", "se.diuf", "steps", "steps.explanation.short", "steps.explanation.teach", "describe",
                   "symmetry")
FIELD_ALIASES = {"time_p80": "time.p80", "notes": "issues"}


def card_fields(fields=None, steps=False, se=False):
    """the field mask (FORMAT.md 11.1): None = the default fields; pencilmark / format / format_version always; a
    steps.explanation.* field implies steps. steps=True / se=True are shorthands."""
    out = set(DEFAULT_FIELDS) if fields is None else {FIELD_ALIASES.get(f, f) for f in fields} | {"grader", "format", "format_version"}
    bad = out - set(DEFAULT_FIELDS) - set(OPTIONAL_FIELDS)
    if bad:
        raise ValueError(f"unknown card field(s) {sorted(bad)}; known: {list(DEFAULT_FIELDS) + list(OPTIONAL_FIELDS)}")
    if steps:
        out |= {"steps", "steps.explanation.short", "steps.explanation.teach"}
    if se:
        out.add("se.diuf" if se == "diuf" else "se")
    if out & {"steps.explanation.short", "steps.explanation.teach"}:
        out.add("steps")
    return out


RULE_NOUN = {("line", None): "line", ("edge", "kropki"): "kropki dot", ("edge", "xv"): "X / V clue", ("edge", "less"): "inequality sign",
             ("edge", "difference"): "difference clue", ("edge", "sum"): "sum clue", ("edge", "product"): "product clue",
             ("edge", "ratio"): "ratio clue", ("region", "diagonal"): "diagonal", ("region", "window"): "window",
             ("region", "disjoint"): "disjoint group", ("region", "extra"): "extra region", ("region", "colour"): "colour group",
             ("cage", None): "cage", ("arrow", None): "arrow", ("digits", None): "shaded cell", ("neighbours", None): "neighbour rule",
             ("negative", None): "negative constraint", ("table", None): "table rule", ("relation", None): "pair rule",
             ("corner", None): "corner clue", ("sum", None): "sum clue", ("contains", None): "quadruple", ("appears", None): "arrow clue"}


def _noun(rules):
    names = []
    for r in rules:
        t, k = r["type"], r.get("kind")
        n = RULE_NOUN.get((t, k)) or (f"{k.replace('_', ' ')} line" if t == "line" else
                                      {"antiknight": "anti-knight rule", "antiking": "anti-king rule",
                                       "nonconsecutive": "non-consecutive rule"}.get(k) if t == "neighbours" and k else None) \
            or RULE_NOUN.get((t, None)) or t.replace("_", " ")
        if n not in names:
            names.append(n)
    return " / ".join(names) or "rule"


def _issues(p, card, doc, prov):
    """card notes -> issues [{"code", "severity": "reject" | "warning", "text", "rules"?}] (FORMAT.md 11.1). Rule notes
    point at the exported file's rule indices (doc = exchange.write(p) as to_export writes it)."""
    out = []
    raw = card.get("_notes_raw")
    if raw is None:                       # cards made without the raw notes: parse the flags
        raw = [("note", "reject" if f.startswith("would not") else "note", f.split(": ", 1)[-1]) for f in card.get("flags") or []]
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
            idx = [i for i, pr in enumerate(prov) if (pr.get("groups", set()) & gidx) or (pr.get("constraints", set()) & cons)
                   or (pr.get("relations", set()) & rpos) or (c.startswith("shading") and pr.get("clues"))]
            if idx:
                rs = [doc["rules"][i] for i in idx]
                what = _noun(rs) + ("s" if len(idx) > 1 and " / " not in _noun(rs) else "")
                where = f"rule {idx[0]}" if len(idx) == 1 else "rules " + ", ".join(map(str, idx))
                if code == "decorative":
                    e["text"] = f"{what} ({where}): not needed for uniqueness and never used by the solve"
                elif code == "redundant":
                    e["text"] = f"{what} ({where}): used in {used} step{'s' if used != 1 else ''}, but the puzzle is unique without it"
                else:
                    e["text"] = f"{what} ({where}): used in only {used} step{'s' if used != 1 else ''} of the solve"
                e["rules"] = idx
        out.append(e)
    return out


def symmetry_of(p):
    """symmetries of the givens pattern (and board shape): [{"kind", "axis"?, "of": "givens"}]. Rule symmetry ("of": "all")
    is not detected yet."""
    co = [tuple(x) for x in p.coords]
    R = max(r for r, _ in co) + 1; C = max(c for _, c in co) + 1
    cells = set(co)
    giv = {co[i] for i in p.givens}
    tf = {("rot180", None): lambda r, c: (R - 1 - r, C - 1 - c), ("mirror", "vertical"): lambda r, c: (r, C - 1 - c),
          ("mirror", "horizontal"): lambda r, c: (R - 1 - r, c)}
    if R == C:
        tf.update({("rot90", None): lambda r, c: (c, R - 1 - r), ("mirror", "diagonal"): lambda r, c: (c, r),
                   ("mirror", "antidiagonal"): lambda r, c: (C - 1 - c, R - 1 - r)})
    out = []
    for (kind, axis), f in tf.items():
        if all(f(*x) in cells for x in cells) and all(f(*x) in giv for x in giv):
            out.append(dict({"kind": kind}, **({"axis": axis} if axis else {}), of="givens"))
    return out


def grade(p, P, card=None, with_steps=None, max_seconds=None, fields=None):
    """sudoku-grade card (FORMAT.md 11.1), only the requested fields: difficulty, time, band, contains, issues / reject by
    default; time.p80, steps (+ steps.explanation.short / .teach), describe, symmetry on request (se is added by api.rate).
    with_steps=True is shorthand for fields + steps with both explanation levels."""
    from . import card as K, band_path as BP
    want = card_fields(fields, steps=bool(with_steps))
    P = dict(P, search=P.get("search", "human"))
    import time
    bp = BP.contents(p, P, deadline=None if max_seconds is None else time.time() + max_seconds)
    if card is None:        # band / required from the band path (skips the deletion test inside grade_card)
        req_b = list(dict.fromkeys(st["technique"] for st in bp["steps"] if st["band"] > 0))
        card = K.grade_card(p, P, specific=False, check_rules=bool(want & {"issues", "reject"}),     # specific names are not used by this card
                            band=(bp["band"] if bp["solved"] else "Unknown", req_b))
    unknown = not bp["solved"]
    names = {}
    for st in bp["steps"]:
        names.setdefault(st["code"], Counter())[st["name"]] += 1
    uses = Counter(bp["profile"])                  # folded: full houses count under the listed single
    bandof = {st["code"]: st["band"] for st in bp["steps"]}
    alts = bp.get("alternatives", {})
    contains = []
    for c, n in sorted(uses.items(), key=lambda x: (bandof.get(x[0], 0), BP._order(x[0]), x[0])):
        e = {"code": c, "chip": "/".join([c] + alts.get(c, [])), "name": names[c].most_common(1)[0][0],
             "band": bandof.get(c, 0)}
        if alts.get(c):
            e["alternatives"] = alts[c]     # each of these alone also gets you through (not on c's subset chain)
        if e["band"] > 0:
            e["uses"] = n                   # on the easiest route; singles' counts swing with the route, so omitted
        contains.append(e)
    tg = card.get("time_grade")
    tm = time_units(card.get("effort_l1"), p.N - len(p.givens), difficulty=card.get("score"), geometry=region_geometry(p))
    g = {"format": "sudoku-grade", "format_version": FORMAT_VERSION,
         "grader": {"name": GRADER_NAME, "version": GRADER_VERSION}}
    if "difficulty" in want:
        g["difficulty"] = card.get("score")
    if "time" in want:
        # time in MINUTES for today's average player (classic units x minutes_per_unit, data/time_model.json)
        g["time"] = round(tm * _TIME.get("minutes_per_unit", 1.0), 1) if tm is not None else (round(2 ** (tg - 5), 2) if tg is not None else None)
    if "time.p80" in want:
        g["time_p80"] = round(tm * _TIME.get("p80_factor", 1.53) * _TIME.get("minutes_per_unit", 1.0), 1) if tm is not None else None
    if "band" in want:
        g["band"] = "Unknown" if unknown else bp["band"]
    if "band_index" in want:
        g["band_index"] = None if unknown else bp["band_index"]
    if "contains" in want:
        g["contains"] = contains
        if bp.get("truncated"):     # opt-in time cap hit: route complete, the list may not be minimal / may miss alternatives
            g["contents_truncated"] = True
        if unknown:     # what's in it up to where human logic ran out; the rest is unknown
            g["contains_complete"] = False
            g["stopped_at_step"] = len(bp["steps"]) + 1
    doc = prov = None
    if want & {"issues", "reject", "describe"}:
        try:
            from . import exchange as X
            doc, prov = X.write(p, provenance=True)
        except Exception:
            doc = prov = None
    if want & {"issues", "reject"}:
        issues = _issues(p, card, doc, prov or [])
        if "issues" in want:
            g["issues"] = issues
        if "reject" in want:
            g["reject"] = any(i["severity"] == "reject" for i in issues)
    if "describe" in want:
        from .variants import describe as _describe
        g["describe"] = _describe(doc) if doc is not None else None
    if "symmetry" in want:
        g["symmetry"] = symmetry_of(p)
    if "steps" in want:
        cn = lambda c: f"r{p.coords[c][0] + 1}c{p.coords[c][1] + 1}"
        levels = [x for x in ("short", "teach") if f"steps.explanation.{x}" in want]
        expl = BP.explain_steps(p, P, bp["steps"]) if levels else [None] * len(bp["steps"])
        rows = []
        for i, st in enumerate(bp["steps"]):
            r = {"n": i + 1, "technique": st["name"], "code": st["code"], "band": st["band"]}
            if st["place"]:
                r["placement"] = f"{cn(st['place'][0])}={st['place'][1]}"
            if st["elims"]:
                r["eliminations"] = [f"{cn(c)}#{d}" for c, d in st["elims"]]
            if levels and expl[i]:
                r["explanation"] = {x: expl[i][x] for x in levels}
            rows.append(r)
        g["steps"] = rows
    return g

