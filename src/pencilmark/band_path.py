"""Band-by-band human solve and technique hints.

The solve uses Very Easy moves until none are left, then Easy, then Medium, and so on, dropping back to the lowest band
after every move. Within a band it takes the simplest technique first (study order, data/codes.csv),
then the cheapest move. Each step is named by its most specific shape (a Skyscraper, not "X-Chain"; a Franken X-Wing,
not "X-Wing"), and its band comes from that shape.

The techniques this solve uses are the puzzle's hints: what a human solving from easy to hard will meet. SUBSET maps
each code to the codes it is a special case of (always true: every X-Wing is a Skyscraper), so a learner who knows
a technique also covers its special cases (covered(), lesson()).

    band_path(puzzle, P) -> {"solved", "band", "steps": [{code, name, band, place, elims}], "profile": {code: uses}}
"""

import copy
import logging
from collections import Counter

from . import cbackend as CB
from . import export as E2
from . import registry as R
from . import solver as S
from .layers import CLASS_COLORS, COLOR_PAIRS, REGION_COLORS

BANDS = E2.BANDS
_log = logging.getLogger(__name__)  # trace (level 5): each technique-list test with its time
# costly techniques late in their band's study order: a listing first runs without their strategies, and runs them only
# when the best move found could still lose to one of theirs (see _late_bound; exact)
LATE = ("CaseAnalysis", "WhatIf", "EitherWay")
FORCING_TECHS = CB.computer_search()  # a forcing step taken as the fallback is Extreme

# most specific shape of an X-Chain move: engine pattern code -> (code, display name, band) (data/patterns.csv)
_X_CHAIN = {
    p.engine_code: (p.code, p.step_name, R.codes()[p.code].shape_band) for p in R.patterns() if p.technique == "X-Chain"
}
_NAMED_CHAINS = {c for c, (code, _, _) in _X_CHAIN.items() if code != "XCL"}  # Skyscraper, 2-String Kite, Turbot, ER
# Phistomefel forms of a law-of-leftovers move: engine pattern code -> (code, display name)
_LEFTOVERS = {p.engine_code: (p.code, p.step_name) for p in R.patterns() if p.technique == "LawOfLeftovers"}

# A -> the codes A is always a special case of (data/codes.csv subset_of; transitive closure below)
SUBSET = {c: list(v.subset_of) for c, v in R.codes().items() if v.subset_of}


def _closure():
    out = {}

    def up(c, seen):
        for s in SUBSET.get(c, ()):
            if s not in seen:
                seen.add(s)
                up(s, seen)
        return seen

    for c in set(SUBSET) | {s for v in SUBSET.values() for s in v}:
        out[c] = up(c, set())
    return out


SUPERSETS = _closure()


def covered(code, known):
    """a learner who knows `known` can do `code`: they know it, or a technique it is always a case of."""
    return code in known or bool(SUPERSETS.get(code, set()) & set(known))


def _order(code):
    """study order inside a band (data/codes.csv): simplest first."""
    c = R.codes().get(code)
    return c.order if c else 99


def _shape_band(code):
    return R.codes()[code].shape_band


def classify(m, p):
    """(code, name, band) of one state_moves move, by its most specific shape."""
    t, n, c = m["tech"], m["name"], m.get("code")
    if n == "X-Chain" and c in _X_CHAIN:
        return _X_CHAIN[c]
    if n == "MentalChain(direct)" and c in _NAMED_CHAINS:  # a short chain seen without notes
        code, name, band = _X_CHAIN[c]
        return code, name + " (in the head)", band
    if n in ("X-Wing", "Swordfish") and c:  # the engine's shape: basic, Franken (a box) or Mutant (rows and columns)
        plain = not any(w in str(c) for w in ("Franken", "Mutant"))
        code = ("XWG" if n == "X-Wing" else "SWF") if plain else "FRK"
        return code, n if plain else str(c), _shape_band(code)
    if n == "LawOfLeftovers" and c in _LEFTOVERS:
        code, name = _LEFTOVERS[c]
        return code, name, _shape_band(code)
    if n == "Jellyfish" and c and "franken" in str(c).lower():
        return "FRK", "Franken Jellyfish", _shape_band("FRK")
    code, band = E2.chip_of(t, str(c) if c and n in E2.SPLIT else None)
    from .card import _code

    name = str(c) if c and n in E2.SPLIT else _code(n)[1]
    return code, name, band if band is not None else 9


# techniques that reason about variant rules: only switched on when the puzzle has such rules (per-variant techniques are only considered for their variants). Fireworks and Gurth's theorem
# are classic techniques and stay on everywhere.
VARIANT_ANY = [t.name for t in R.techniques() if t.gate == "any"]  # data/techniques.csv gate
VARIANT_SUM = [t.name for t in R.techniques() if t.gate == "sum"]
_SUM_WORDS = ("sum", "cage", "killer", "arrow", "sandwich", "little")


def variant_gate(p):
    """engine techniques to switch off for this puzzle: variant techniques without any variant rule, sum techniques
    without a sum rule, law of leftovers without sums or irregular / extra regions."""
    from .usage import element_classes

    rev = {v: k for k, v in S.TECH_NAMES.items()}
    try:
        cls = [c for c in element_classes(p) if not any(c.startswith(b) for b in ("row", "col", "box", "column"))]
    except Exception:
        cls = []
    has_sum = any(g.total is not None for g in p.groups) or any(any(w in c.lower() for w in _SUM_WORDS) for c in cls)
    boxes = [g for g in p.groups if g.kind == "box"]

    def rect(g):
        rs = {p.coords[c][0] for c in g.cells}
        cs = {p.coords[c][1] for c in g.cells}
        return len(rs) * len(cs) == len(g.cells)

    regions = any(not rect(g) for g in boxes) or any(
        g.kind not in ("row", "col", "box") and g.complete for g in p.groups
    )
    # overlapping grids (samurai, twodoku, ...): set theory / implied houses come from the geometry, not a rule
    overlap = any(sum(1 for gi in p.groups_of[c] if p.groups[gi].kind == "box") > 1 for c in range(p.N))
    regions = regions or overlap
    off = set()
    if not cls and not has_sum and not regions:
        off |= {rev[n] for n in VARIANT_ANY if n in rev}
    elif not cls and not has_sum:  # geometry only (irregular / extra regions / overlapping grids): region logic stays
        off |= {
            rev[n] for n in VARIANT_ANY if n in rev and n not in ("ImpliedHouses", "DigitCount", "RuleIntersection")
        }
    if not has_sum:
        off |= {rev[n] for n in VARIANT_SUM if n in rev}
        if not regions:
            off.add(rev["LawOfLeftovers"])
    return off


_CACHE = None  # position -> state_moves, shared by the many routes of one contents() call (same openings)


def band_path(
    p,
    P,
    max_steps=500,
    disabled=(),
    target=None,
    rng=None,
    ban_codes=(),
    guard=None,
    prefix=(),
    max_band=6,
    keep_held=False,
    stop_cells=None,
):
    """solve band by band (see module doc). Moves are taken in full-notes mode: each placement clears its peers.
    target = a cell: stop once it is placed, preferring (within the current band) a move that places it -- "what does
    it take to place this cell from here". max_band: stop (unsolved) where only a harder move would continue -- contents()
    reruns can only count if they stay in the card's band, so they never list above it. keep_held: keep color-only
    steps no later step used (the fog route: a color may pay off after the next reveal). stop_cells: stop right after
    a placement in one of these cells (the fog route: a placement that lights new cells ends the round)."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    P = dict(P or {}, search="human")
    notes = set(S.NOTE_TECHS)
    comp = set(CB.search_disabled(P)) | {S.GUESS}
    ct = _code_techs(P)  # whole-technique codes are switched off in the engine (it then reports a
    whole = set(ban_codes) & set(ct)  # placement under another technique); shape codes are filtered below
    disabled = set(disabled) | {t for c in whole for t in ct[c]} | variant_gate(p)
    ban_codes = set(ban_codes) - whole
    human = {t for t in S.TECH_NAMES if t not in comp and t not in notes and t not in set(disabled)}
    tband = {t: E2.tech_band(t) for t in human}
    D, N = p.D, p.N
    vals = [p.givens.get(c, 0) for c in range(N)]
    dom = getattr(p, "domains", None)
    cand = [0 if vals[c] else (dom[c] if dom else (1 << D) - 1) for c in range(N)]
    for c in range(N):
        if vals[c]:
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (vals[c] - 1))
    # regions to find: label per cell and label candidates (the engine normalizes them on every call)
    chaos = any(c_.get("type") == "chaos" for c_ in getattr(p, "constraints", ()))
    lab = [0] * N if chaos else None
    lcand = [0] * N if chaos else None
    for c_ in getattr(p, "constraints", ()):
        if c_.get("type") == "chaos":
            for x in c_["cells"]:
                lcand[x] = (1 << D) - 1
    # identity layer (params coloring): color class per cell (0 none), canonical ids as the engine keeps them
    ids = bool(P.get("colouring"))
    idc = [0] * N if ids else None
    rgc = CB.rg_seed(p) if chaos else None  # regions to find: the relation layer (cells sharing / not sharing a region)
    shade = CB.shade_seed(p)  # shading: colour per cell (None without a yin_yang rule)
    shading = shade is not None
    labels = lambda: (lab, lcand, idc, rgc, shade) if chaos or ids or shading else None  # noqa: E731
    lkey = lambda: (  # noqa: E731
        (tuple(lab or ()), tuple(lcand or ()), tuple(idc or ()), tuple(rgc or ()), tuple(shade or ()))
        if chaos or ids or shading
        else ()
    )
    q = copy.copy(p)  # the puzzle keeps its own domains; each state's candidates go in as a mask
    cp = getattr(p, "_bp_cpuzzle", None)
    if cp is None:
        cp = CB.to_cpuzzle(p)  # built once per puzzle (the expensive part of a move listing)
        try:
            p._bp_cpuzzle = cp
        except Exception:
            pass
    steps = []
    allowed0 = {t for t in human if tband[t] == 0}
    off0 = set(S.TECH_NAMES) - allowed0 - notes

    def apply(m):
        if m["place"]:
            c, d = m["place"]
            vals[c], cand[c] = d, 0
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (d - 1))
        for c, d in m["elim"]:
            cand[c] &= ~(1 << (d - 1))
        if chaos:  # label effects
            if m.get("lplace"):
                c, k = m["lplace"]
                lab[c], lcand[c] = k, 1 << (k - 1)
            for c, k in m.get("lelim") or ():
                if not lab[c]:
                    lcand[c] &= ~(1 << (k - 1))
                    if lcand[c] and not lcand[c] & (lcand[c] - 1):
                        lab[c] = lcand[c].bit_length()
            CB.rg_apply(rgc, N, m.get("rfx"))
        if shading:  # colour effects travel with the region relations
            CB.shade_apply(shade, m.get("rfx"))
        if ids:  # class joins and differences; a placement may free a class
            CB.id_apply(idc, vals, m.get("idfx"))

    def acts(m):  # the move changes the state (a digit, a region label or a color class)
        return (
            m["place"]
            or m["elim"]
            or (chaos and (m.get("lplace") or m.get("lelim") or m.get("rfx")))
            or (shading and m.get("rfx"))
            or (ids and CB.id_changes(m.get("idfx")))
        )

    counts = Counter()
    aborted = False
    seg = max((st.get("seg", 0) for st in prefix), default=0)  # engine call each step came from

    stopped = [False]

    def record(stp):
        nonlocal aborted
        steps.append(stp)
        if stop_cells and stp["place"] and stp["place"][0] in stop_cells:
            stopped[0] = True
        if ids and not stp["place"] and not stp["elims"]:  # identity only: held until a later step uses it, so
            return  # whether it counts is known only at the end (held steps are dropped there; _route_ok judges)
        counts[stp["code"]] += 1
        if guard is not None and not guard(stp, counts):
            aborted = True

    for stp in prefix:
        steps.append(stp)
        counts[stp["code"]] += 1
        apply(
            {
                "place": stp["place"],
                "elim": stp["elims"],
                "lplace": stp.get("lplace"),
                "lelim": stp.get("lelims"),
                "rfx": stp.get("rfx"),
                "idfx": stp.get("idfx"),
            }
        )
    for _ in range(max_steps):
        if aborted or stopped[0] or all(vals) or (target is not None and vals[target]):
            break
        q.givens = {c: v for c, v in enumerate(vals) if v}
        mask = [cand[c] if not vals[c] else 1 << (vals[c] - 1) for c in range(N)]
        if allowed0 and rng is None:
            # Very Easy phase in ONE engine call: singles until none are left (90%+ of all steps). The engine
            # orders singles by price, not by study order, so only which single gets which label can differ.
            key0 = ("b0", tuple(vals), tuple(cand), frozenset(off0), lkey()) if _CACHE is not None else None
            batch = _CACHE.get(key0) if key0 is not None else None
            if batch is None:
                st0, _ = CB.solve(
                    q, P, disabled=off0, cpuzzle=cp, cand=mask, max_steps=N + 5, assume_unique=False, labels=labels()
                )
                batch = [
                    {
                        "tech": x.move.feat[0],
                        "name": S.TECH_NAMES.get(x.move.feat[0], "?"),
                        "code": x.move.code,
                        "place": tuple(x.move.place) if x.move.place else None,
                        "elim": [tuple(e) for e in (x.move.elim or ())],
                        "xmeta": getattr(x.move, "xmeta", None),
                        "d": float(x.move.d) if x.move.d is not None else None,
                        **(
                            {
                                "lplace": getattr(x.move, "lplace", None),
                                "lelim": list(getattr(x.move, "lelim", ())),
                                "rfx": list(getattr(x.move, "rfx", None) or ()),
                            }
                            if chaos or shading
                            else {}
                        ),
                        **({"idfx": list(getattr(x.move, "idfx", None) or ())} if ids else {}),
                    }
                    for x in st0
                    if x.move.feat[0] not in notes and x.move.feat[0] in allowed0
                ]
                if key0 is not None:
                    _CACHE[key0] = batch
            moved = False
            seg += 1
            for m in batch:
                if not acts(m):
                    continue
                if m["place"] and vals[m["place"][0]]:
                    continue
                code, name, mb = classify(m, p)
                apply(m)
                record(
                    {
                        "code": code,
                        "name": name,
                        "band": mb,
                        "technique": m["name"],
                        "ecode": m.get("code"),
                        "xmeta": m.get("xmeta"),
                        "pattern": m.get("pattern"),
                        "ex": m.get("ex"),
                        "nm": m.get("nm"),
                        "tech": m["tech"],
                        "place": m["place"],
                        "elims": list(m["elim"]),
                        "seg": seg,
                        "d": m.get("d"),
                        **(
                            {
                                "lplace": m.get("lplace"),
                                "lelims": list(m.get("lelim") or ()),
                                "rfx": list(m.get("rfx") or ()),
                            }
                            if chaos or shading
                            else {}
                        ),
                        **({"idfx": list(m.get("idfx") or ())} if ids else {}),
                    }
                )
                moved = True
                if aborted or stopped[0] or (target is not None and vals[target]):
                    break
            if moved:
                continue
        pick = None
        for b in range(1 if allowed0 and rng is None else 0, max_band + 1):
            allowed = {t for t in human if tband[t] <= b}
            if not allowed:
                continue
            # below Hard only size-2 finned fish can be picked (larger ones are Hard): don't list them (windoku:
            # sizes 3-4 were 90% of a listing over 58 houses)
            capped = b <= 3  # up to Hard only fish of size 2 are listed (Swordfish and larger are Very Hard; speed)
            Pb = dict(P, fish_max_n=2) if capped else P

            def listing(skip=()):
                key = (
                    (tuple(vals), tuple(cand), frozenset(allowed), capped, skip, lkey()) if _CACHE is not None else None
                )
                mv = _CACHE.get(key) if key is not None else None
                if mv is None:
                    mv = CB.state_moves(
                        q,
                        Pb,
                        disabled=set(S.TECH_NAMES) - allowed,
                        limit_per_tech=8,
                        details=True,
                        cpuzzle=cp,
                        cand=mask,
                        skip=skip,
                        labels=labels(),
                    )
                    if key is not None:
                        _CACHE[key] = mv
                cands = []
                for m in mv:
                    if m["tech"] not in allowed or not acts(m):
                        continue
                    code, name, mb = classify(m, p)
                    if code in ban_codes:
                        continue
                    if mb <= b:
                        hit = 0 if target is not None and m["place"] and m["place"][0] == target else 1
                        key = (mb, hit, rng.random()) if rng is not None else (mb, hit, _order(code), m["d"])
                        cands.append((key, code, name, mb, m))  # rng: any move of the lowest band (other solvers)
                return min(cands, key=lambda x: x[0]) if cands else None

            # staged: without the LATE strategies first. Their moves are at least _late_bound; an ELIMINATION that
            # beats that stays the pick in the full listing (eliminations are deduplicated per technique, the per-
            # technique limit counts per technique, and the other strategies see the same disabled flags). A
            # placement may be deduplicated against a skipped technique's: then the full listing decides.
            late = (
                tuple(sorted(t for t in allowed if S.TECH_NAMES[t] in LATE)) if rng is None and target is None else ()
            )
            if late:
                pick = listing(late)
                if pick is not None and (pick[4]["place"] or (pick[0][0], pick[0][2]) >= _late_bound(late)):
                    pick = None
            if pick is None:
                pick = listing()
            if pick is not None:
                break
        if pick is None and P.get("r6_extreme", True) and rng is None and max_band >= 6:
            # nothing listed in any band -> one solver step from this state. The solver's stuck-fallback
            # tries forcing chains / dynamic / nested forcing / Nishio / pattern overlay (state_moves never lists them);
            # such a step is an Extreme move. A guess means really stuck -> Unknown.
            # the same state in another contents() route takes the same step: one solver call per state
            key1 = ("ff", tuple(vals), tuple(cand), lkey()) if _CACHE is not None else None
            m = _CACHE.get(key1, False) if key1 is not None else False
            if m is False:
                st1, _ = CB.solve(q, P, cpuzzle=cp, cand=mask, max_steps=4, assume_unique=False, labels=labels())
                x = next((y for y in st1 if y.move.feat[0] not in notes), None)
                # guessing off (default): the solver's last resort is a proof by full search (TRIAL), Extreme too
                stop = (S.GUESS, S.TRIAL) if P.get("allow_guess", False) else (S.GUESS,)
                m = None
                if (
                    x is not None
                    and x.move.feat[0] not in stop
                    and (
                        x.move.place
                        or x.move.elim
                        or (chaos and (x.move.lplace or x.move.lelim or getattr(x.move, "rfx", None)))
                        or (shading and getattr(x.move, "rfx", None))
                        or (ids and CB.id_changes(getattr(x.move, "idfx", None)))
                    )
                ):
                    m = {
                        "tech": x.move.feat[0],
                        "name": S.TECH_NAMES.get(x.move.feat[0], "?"),
                        "code": x.move.code,
                        "place": tuple(x.move.place) if x.move.place else None,
                        "elim": [tuple(e) for e in (x.move.elim or ())],
                        "xmeta": getattr(x.move, "xmeta", None),
                        "d": float(x.move.d) if x.move.d is not None else None,
                        **(
                            {
                                "lplace": x.move.lplace,
                                "lelim": list(x.move.lelim),
                                "rfx": list(getattr(x.move, "rfx", None) or ()),
                            }
                            if chaos or shading
                            else {}
                        ),
                        **({"idfx": list(getattr(x.move, "idfx", None) or ())} if ids else {}),
                    }
                if key1 is not None:
                    _CACHE[key1] = m
            if m is not None:
                code, name, mb = classify(m, p)
                # a forcing step is Extreme; any other human step the move listing missed keeps its own band
                pick = ((mb, 1, 0, m["d"]), code, name, max(mb, 6) if m["tech"] in FORCING_TECHS else mb, m)
        if pick is None:
            break
        _, code, name, mb, m = pick
        apply(m)
        seg += 1
        record(
            {
                "code": code,
                "name": name,
                "band": mb,
                "technique": m["name"],
                "ecode": m.get("code"),
                "xmeta": m.get("xmeta"),
                "pattern": m.get("pattern"),
                "ex": m.get("ex"),  # the engine's explanation records (cbackend.explain_record)
                "nm": m.get("nm"),
                "tech": m["tech"],
                "place": tuple(m["place"]) if m["place"] else None,
                "elims": [tuple(e) for e in m["elim"]],
                "seg": seg,
                "d": m.get("d"),
                **(
                    {"lplace": m.get("lplace"), "lelims": list(m.get("lelim") or ()), "rfx": list(m.get("rfx") or ())}
                    if chaos or shading
                    else {}
                ),
                **({"idfx": list(m.get("idfx") or ())} if ids else {}),
            }
        )
    if (
        ids and steps and not keep_held
    ):  # identity layer: identity-only steps no later step relied on cost nothing -- dropped, the
        # route without them is the same proof (cbackend.id_held)
        held = CB.id_held(N, p.givens, [(st["place"], st["elims"], st.get("idfx")) for st in steps])
        steps[:] = [st for st, h in zip(steps, held) if not h]
    if target is not None:
        top = max((s_["band"] for s_ in steps), default=0)
        return {
            "placed": bool(vals[target]),
            "band_index": top if vals[target] else None,
            "steps": steps,
            "codes": dict(Counter(s_["code"] for s_ in steps)),
        }
    solved = all(vals) and not aborted
    prof = Counter(s["code"] for s in steps)
    top = max((s["band"] for s in steps), default=0)
    return {
        "solved": solved,
        "band": BANDS[top] if solved else "Unknown",
        "band_index": top if solved else None,
        "steps": steps,
        "profile": dict(prof),
        "hints": {
            BANDS[b]: dict(Counter(s["code"] for s in steps if s["band"] == b))
            for b in range(0, 6)
            if any(s["band"] == b for s in steps)
        },
    }


def _code_techs(P):
    """code -> engine techniques that always carry it (codes that depend on the shape -- SKY, FRK, ... -- are left out:
    switching their technique off would remove its other shapes too)."""
    out = {}
    for t in S.TECH_NAMES:
        if S.TECH_NAMES[t] in E2.SPLIT or S.TECH_NAMES[t] in ("Swordfish", "Jellyfish", "MentalChain(direct)"):
            continue
        code, b = E2.chip_of(t)
        if b is not None:
            out.setdefault(code, set()).add(t)
    return out


def _late_bound(techs):
    """the smallest (band, study order) a move of these techniques can have (none is a split / shape-coded one)"""
    out = (99, 99)
    for t in techs:
        code, band = E2.chip_of(t)
        out = min(out, (band if band is not None else 9, _order(code)))
    return out


def _route_ok(bp, alt, code, extra=()):
    """alt (a route with `code` banned) keeps bp's band, uses nothing new except `extra` and special cases of what's
    listed, and moves code's work only to techniques of its band or lower that aren't generalizations of it."""
    if not alt["solved"] or alt["band_index"] != bp["band_index"]:
        return False
    keep = (set(bp["profile"]) - {code}) | set(extra)
    if any(not covered(c, keep) for c in set(alt["profile"]) - set(bp["profile"])):
        return False
    b = max(st["band"] for st in bp["steps"] if st["code"] == code)
    abandof = {st["code"]: st["band"] for st in alt["steps"]}
    gained = [c for c, n in alt["profile"].items() if n > bp["profile"].get(c, 0)]
    return not any(abandof[c] > b or c in SUPERSETS.get(code, set()) for c in gained)


def _check(bp, code, ban, extra=()):
    """(guard, prefix) for the route that bans `ban` to test removing / replacing `code`: the guard stops it at the
    first step that already makes _route_ok fail (a band above the card's, something new not covered, or the work
    going to a harder technique or a generalization of `code` -- counts only grow, so the verdict is final).
    The prefix (base route up to the first banned step) is NOT used by contents(): a whole-technique ban also removes
    composite moves built on it (a "notes in the head" single using innies / outies is labeled MSI), so a banned
    route can differ before the banned code's first use."""
    B = bp["band_index"]
    keep = (set(bp["profile"]) - {code}) | set(extra)
    b = max(st["band"] for st in bp["steps"] if st["code"] == code)
    base = bp["profile"]
    sup = SUPERSETS.get(code, set())

    def guard(st, counts):
        c = st["code"]
        if st["band"] > B:
            return False
        if c not in base and not covered(c, keep):
            return False
        if counts[c] > base.get(c, 0) and (st["band"] > b or c in sup):
            return False
        return True

    k = next((i for i, st in enumerate(bp["steps"]) if st["code"] in ban), len(bp["steps"]))
    if k < len(bp["steps"]):  # resume only where the base route also made a fresh engine call: a batched-singles
        sg = bp["steps"][k].get("seg")  # call carries mode state, so restarting mid-batch could drift
        while k > 0 and bp["steps"][k - 1].get("seg") == sg:
            k -= 1
    return guard, bp["steps"][:k]


def _states(p, steps):
    """(puzzle at the position before each step, its candidates) along a band-path route."""
    N, D = p.N, p.D
    vals = [p.givens.get(c, 0) for c in range(N)]
    dom = getattr(p, "domains", None)
    cand = [0 if vals[c] else (dom[c] if dom else (1 << D) - 1) for c in range(N)]
    for c in range(N):
        if vals[c]:
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (vals[c] - 1))
    chaos = [c_["cells"] for c_ in getattr(p, "constraints", ()) if c_.get("type") == "chaos"]
    lab, lcand = [0] * N, [0] * N  # regions to find: labels travel with each state (q._pm_labels)
    for cells in chaos:
        for x in cells:
            lcand[x] = (1 << D) - 1
    ids = any("idfx" in st for st in steps)  # identity layer: the route carries its color classes
    idc = [0] * N
    rgc = CB.rg_seed(p) if chaos else None  # regions to find: the relation layer
    shade = CB.shade_seed(p)  # shading: colour per cell
    for st in steps:
        q = copy.copy(p)
        q.givens = {c: v for c, v in enumerate(vals) if v}
        q.domains = [cand[c] if not vals[c] else 1 << (vals[c] - 1) for c in range(N)]
        q._pm_labels = (
            (
                list(lab) if chaos else None,
                list(lcand) if chaos else None,
                list(idc) if ids else None,
                list(rgc) if chaos else None,
                list(shade) if shade is not None else None,
            )
            if chaos or ids or shade is not None
            else None
        )
        yield q
        if st["place"]:
            c, d = st["place"]
            vals[c], cand[c] = d, 0
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (d - 1))
        for c, d in st["elims"]:
            cand[c] &= ~(1 << (d - 1))
        if chaos:
            if st.get("lplace"):
                c, k = st["lplace"]
                lab[c], lcand[c] = k, 1 << (k - 1)
            for c, k in st.get("lelims") or ():
                if not lab[c]:
                    lcand[c] &= ~(1 << (k - 1))
                    if lcand[c] and not lcand[c] & (lcand[c] - 1):
                        lab[c] = lcand[c].bit_length()
            CB.rg_apply(rgc, N, st.get("rfx"))
        if shade is not None:
            CB.shade_apply(shade, st.get("rfx"))
        if ids:
            CB.id_apply(idc, vals, st.get("idfx"))


def contents(p, P, alternatives=True, deadline=None, base=None):
    """What's in the puzzle, deterministically (same puzzle -> same card).
    1. band_path (easy to hard, simplest technique first).
    2. Shrink: each listed technique is tried for removal (banned by its exact code), later in the study order first,
       so the simpler of two interchangeable ones stays; kept only if _route_ok (same band, nothing new but special
       cases of what's listed, its work not moved to a harder technique or a generalization of it).
    3. Alternatives: for each listed technique X, every same-band technique Y that is NOT on X's subset chain (neither
       is a special case of the other) and was available where X was used, is tested by banning X: if the puzzle then
       solves with the listed techniques plus Y (_route_ok, Y actually used), X/Y is a joint chip -- "solvable if you
       know either". Same-chain relations stay out: the player's subset table covers them (a Turbot learner can do
       Skyscrapers).
    Full houses fold into the listed single. -> band_path result + "removed", "alternatives" {code: [codes]}.
    deadline (time.time() value, opt-in; default None = deterministic): shrink / alternatives stop when it passes and the
    result carries "truncated": True (the base route is always complete; the list may then not be minimal / miss joint chips).
    base: band_path(p, P) already computed by the caller (it is not computed again)."""
    global _CACHE
    _CACHE = {}
    try:
        return _contents(p, P, alternatives, deadline, base)
    finally:
        _CACHE = None


def _contents(p, P, alternatives, deadline=None, base=None):
    import time

    late = lambda: deadline is not None and time.time() > deadline
    truncated = False
    bp = (
        base if base is not None else band_path(p, P)
    )  # base: the caller's band_path(p, P) (same route, not recomputed)
    if not bp["solved"]:
        return dict(bp, removed=[], alternatives={}, profile=fold(bp["profile"]))
    ban, removed, failed = set(), [], set()
    while True:  # passes over the list; a code that failed is retried only after a change
        bandof = {st["code"]: st["band"] for st in bp["steps"]}
        changed = False
        for code, _ in sorted(bp["profile"].items(), key=lambda x: (-bandof[x[0]], -_order(x[0]), x[1])):
            if code == "FHS" or code in failed or code in ban or code not in bp["profile"]:
                # full houses fold in at the end, never removed; a banned code still on the route came from the
                # forcing fallback (it takes no bans): testing it again gives the same route, and passes forever
                continue
            if late():
                truncated = True
                break
            g_, _ = _check(bp, code, ban | {code})
            t0 = time.perf_counter()
            alt = band_path(p, P, ban_codes=ban | {code}, guard=g_, max_band=bp["band_index"])
            ok = _route_ok(bp, alt, code)
            _log.log(5, "technique list: without %s %s (%.3f s)", code, "still solves: removed" if ok else "needed",
                     time.perf_counter() - t0)  # fmt: skip
            if ok:
                ban.add(code)
                removed.append(code)
                bp, changed = alt, True
                failed = set()
            else:
                failed.add(code)
        if not changed or truncated:
            break
    alts = {}
    if alternatives and not truncated:
        allowed_t = {t for t in S.TECH_NAMES if t not in set(CB.search_disabled(dict(P, search="human"))) | {S.GUESS}}
        steps_at = {}
        for st, q in zip(bp["steps"], _states(p, bp["steps"])):
            if st["code"] != "FHS":
                steps_at.setdefault(st["code"], []).append((st, q))
        for code, spots in steps_at.items():
            if late():
                truncated = True
                break
            b = spots[0][0]["band"]
            seen = set()
            t1 = time.perf_counter()
            for st, q in spots[:6]:  # what else of this band was on offer where X was used
                g = copy.copy(p)
                g.givens = q.givens
                for m in CB.state_moves(
                    g,
                    dict(P, fish_max_n=2) if b <= 3 else P,
                    disabled=set(S.TECH_NAMES) - {t for t in allowed_t if E2.tech_band(t) <= b},
                    limit_per_tech=8,
                    details=True,
                    cpuzzle=getattr(p, "_bp_cpuzzle", None),
                    cand=q.domains,
                    labels=getattr(q, "_pm_labels", None),
                ):
                    c2, _, b2 = classify(m, p)
                    if (
                        b2 == b
                        and c2 != code
                        and (
                            m["place"] or m["elim"] or m.get("lplace") or m.get("lelim") or CB.id_changes(m.get("idfx"))
                        )
                    ):
                        seen.add(c2)
            _log.log(5, "alternatives: listed what else was on offer where %s was used: %s (%.3f s)", code,
                     " ".join(sorted(seen)) or "nothing", time.perf_counter() - t1)  # fmt: skip
            alt0 = None
            for y in sorted(seen, key=lambda c_: (_order(c_), c_)):  # ties by code: deterministic in every process
                if y in bp["profile"] or covered(y, {code}) or covered(code, {y}):
                    continue  # listed already, or on X's chain: the subset table covers it
                base = (ban - {y}) | {code}  # a technique dropped in the shrink may still be an alternative
                if y not in ban:
                    if alt0 is None:  # shared by every candidate y: its guard allows all of them, so it stops only
                        # a route no candidate can pass (a stopped route falls to the per-candidate test below);
                        # unguarded, banning a single on an Expert puzzle took 110 s (1.3 benchmark, 2026-11-08)
                        g0, _ = _check(bp, code, base, extra=seen)
                        t1 = time.perf_counter()
                        alt0 = band_path(p, P, ban_codes=base, guard=g0, max_band=bp["band_index"])
                        _log.log(5, "alternatives: route without %s (%.3f s)", code, time.perf_counter() - t1)
                    if alt0["profile"].get(y) and _route_ok(bp, alt0, code, extra={y}):
                        alts.setdefault(code, []).append(y)
                        continue
                # the route may have taken another candidate first; ban the others to test y alone
                others = seen - {y, code} - set(bp["profile"])
                g_, _ = _check(bp, code, base | others, extra={y})
                t0 = time.perf_counter()
                alt = band_path(p, P, ban_codes=base | others, guard=g_, max_band=bp["band_index"])
                ok = bool(alt["profile"].get(y)) and _route_ok(bp, alt, code, extra={y})
                _log.log(5, "alternatives: %s instead of %s %s (%.3f s)", y, code, "works" if ok else "does not",
                         time.perf_counter() - t0)  # fmt: skip
                if ok:
                    alts.setdefault(code, []).append(y)
    for code, ys in list(alts.items()):  # keep the most specific: drop an alternative that generalizes another
        chip = [code] + ys  # one in the same chip (a mental subset working implies NPR works)
        alts[code] = [y for y in ys if not any(z != y and y in SUPERSETS.get(z, set()) for z in chip)]
    out = dict(bp, removed=removed, alternatives={c: ys for c, ys in alts.items() if ys}, profile=fold(bp["profile"]))
    if truncated:
        out["truncated"] = True
    return out


def fold(profile):
    """contents shown to players: a full house is always both a naked and a hidden single and ends nearly every
    house of every solve, so it carries no information -- its uses count under the listed single (hidden single
    first, as the simpler; only when no other single is listed does FHS appear itself)."""
    prof = dict(profile)
    if "FHS" in prof:
        into = "HSI" if "HSI" in prof else ("NSI" if "NSI" in prof else None)
        if into:
            prof[into] += prof.pop("FHS")
    return prof


def allowed(profile, banned):
    """content filter: no hint is a banned technique or a generalization of one (not ready for Skyscrapers means not
    ready for Turbot Fish / X-Chains either). Special cases of a banned code stay allowed (an X-Wing is fine when
    Skyscrapers are banned)."""
    ban = set(banned)
    return not any(c in ban or SUPERSETS.get(b, set()) & {c} for c in profile for b in ban)


def lesson(profile, target, known=()):
    """is this a lesson puzzle for `target` given `known` techniques: the target itself appears (a Skyscraper puzzle
    is solvable by a Turbot learner but doesn't teach Turbot), and every other hint is covered by known + target."""
    k = set(known)
    return target in profile and not covered(target, k) and all(covered(c, k | {target}) for c in profile)


def _cells_notation(p, cells):
    """compact cell list in the solvers' notation: r679c6 (one column), r4c48 (one row), otherwise rows joined by commas"""
    rc = sorted({(p.coords[c][0] + 1, p.coords[c][1] + 1) for c in cells})
    if not rc:
        return ""
    if p.D > 9 or max(max(r, c) for r, c in rc) > 9:  # two-digit rows / columns: no run-together digits
        return ",".join(f"r{r}c{c}" for r, c in rc)

    def grouped(cells, flip):  # rows sharing the same columns merge (r56c8); flip: the same by columns
        by = {}
        for r, c in cells:
            a, b = (c, r) if flip else (r, c)
            by.setdefault(a, []).append(b)
        merged = {}
        for a, bs in sorted(by.items()):
            merged.setdefault(tuple(sorted(bs)), []).append(a)
        parts = sorted(merged.items(), key=lambda kv: (kv[1][0], kv[0]))
        fmt = lambda xs: "".join(map(str, xs))
        return ",".join((f"r{fmt(bs)}c{fmt(a_)}" if flip else f"r{fmt(a_)}c{fmt(bs)}") for bs, a_ in parts)

    return min((grouped(rc, False), grouped(rc, True)), key=lambda t: (len(t), t.count(",")))


def _unit_notation(p, gis):
    """houses in the solvers' notation: r58, c68, b9 (boxes numbered in reading order); other regions by name"""
    boxes = [i for i, g in enumerate(p.groups) if g.kind == "box"]
    out, rows, cols = [], [], []
    for gi in gis:
        g = p.groups[gi]
        rc = {p.coords[c] for c in g.cells}
        if g.kind == "row" and len({r for r, _ in rc}) == 1:
            rows.append(next(iter(rc))[0] + 1)
        elif g.kind == "col" and len({c for _, c in rc}) == 1:
            cols.append(next(iter(rc))[1] + 1)
        elif gi in boxes:
            out.append(f"b{boxes.index(gi) + 1}")
        else:
            out.append(str(g.name))
    join = lambda xs: "".join(map(str, sorted(xs))) if p.D <= 9 else ",".join(map(str, sorted(xs)))
    return " ".join(([f"r{join(rows)}"] if rows else []) + ([f"c{join(cols)}"] if cols else []) + out)


def step_notation(p, st, just=None):
    """one band-path step in the notation solvers and forums share: "X-Wing: 3 r58 c68 => r679c6<>3",
    "Hidden Single: r3c5=6". The pattern part comes from the explainer's justification when there is one."""
    if st.get("place"):
        c, d = st["place"]
        res = f"{_cells_notation(p, [c])}={d}"
    else:
        by_d = {}
        for c, d in sorted(st["elims"], key=lambda x: (p.coords[x[0]], x[1])):
            by_d.setdefault(d, []).append(c)
        res = ", ".join(f"{_cells_notation(p, cs)}<>{d}" for d, cs in by_d.items())
    pat = ""
    j = just or {}
    if not st.get("place") or st.get("band", 0) > 1:
        digs = j.get("digits") or []
        units = list(j.get("base_units") or []) + list(j.get("cover_units") or [])
        cells = j.get("base_cells") or []
        parts = []
        if digs:
            parts.append(",".join(str(d) for d in sorted(set(digs))))
        fish = j.get("base_units") and j.get("cover_units")
        if cells and not fish:  # subsets, wings, patterns: the cells (HoDoKu: "4,8 in r4c48")
            parts.append(f"in {_cells_notation(p, cells)}")
        elif units:  # fish: base and cover houses ("3 r58 c68")
            parts.append(_unit_notation(p, units))
        if j.get("fins"):
            parts.append(f"fins {_cells_notation(p, j['fins'])}")
        pat = " ".join(parts)
    name = st["name"]
    if st.get("code") == "PPR" and j.get("base_units"):  # one step is pointing (box -> line) or claiming (line -> box)
        boxes = {i for i, g in enumerate(p.groups) if g.kind == "box"}
        bu = j["base_units"][0]
        name = "Locked Candidates Type 1 (Pointing)" if bu in boxes else "Locked Candidates Type 2 (Claiming)"
        digs = j.get("digits") or []
        pat = (",".join(str(d) for d in sorted(set(digs))) + " " if digs else "") + "in " + _unit_notation(p, [bu])
    return f"{name}: {pat + ' => ' if pat else ''}{res}"


def _region_substeps(p, st, ex, lab, region_colour):
    """regions to find: the step as sub-steps; each region keeps one color for the whole solve (a legend the first
    time), every cell known to be in the step's region drawn in it; updates lab (cell -> label) in place"""
    from .explain.base import Namer

    nm = Namer(p)
    if (
        not lab
    ):  # regions are numbered by their first cell in reading order: region 1 holds the first cell from the start
        lab[min(range(p.N), key=lambda x: p.coords[x])] = 1
    text = ex.get("short") or ""
    if not text or text.startswith(":"):  # no digit result: the reason (teach's first sentence) reads on its own
        text = (ex.get("teach") or ex.get("notation") or "").split(". So ")[0]
    sub = {"text": text[:1].upper() + text[1:] + ("" if text.endswith(".") else ".")}
    if st.get("lplace"):
        c, k = st["lplace"]
        lab[c] = k
        if k not in region_colour:
            region_colour[k] = REGION_COLORS[len(region_colour) % len(REGION_COLORS)]
            sub["legend"] = {region_colour[k]: f"region {k}"}
        cells = sorted((x for x, kk in lab.items() if kk == k), key=lambda x: p.coords[x])
        sub["annotations"] = [{"id": i + 1, "cell": nm.cell(x), "color": region_colour[k]} for i, x in enumerate(cells)]
    out = [sub]
    placed = st["lplace"][0] if st.get("lplace") else None
    if placed is not None:
        k = st["lplace"][1]
        out.append({"text": f"So {nm.cell(placed)} joins the {region_colour[k]} region."})
    if st.get("lelims"):
        by = {}
        for c, k in st["lelims"]:
            if c != placed:  # the placed cell's other labels go with it
                by.setdefault(k, []).append(c)
        parts, ann, legend = [], [], {}
        nid = len(sub.get("annotations", []))
        for k, cs in sorted(by.items()):
            cs = sorted(cs, key=lambda x: p.coords[x])
            known = sorted((x for x, kk in lab.items() if kk == k), key=lambda x: p.coords[x])
            if k not in region_colour and known:  # first mention of a region with a known cell: its color from now on
                region_colour[k] = REGION_COLORS[len(region_colour) % len(REGION_COLORS)]
                legend[region_colour[k]] = f"region {k}"
            where = f"the {region_colour[k]} region" if k in region_colour else f"region {k}"
            parts.append(f"{nm.cells(cs)} {'is' if len(cs) == 1 else 'are'} not in {where}")
            if placed is None:  # the region as known so far, and the cells ruled out of it
                if k in region_colour:
                    ann += [{"cell": nm.cell(x), "color": region_colour[k]} for x in known]
                ann += [{"cell": nm.cell(x), "color": "red"} for x in cs]
        if parts:
            last = {"text": "So " + "; ".join(parts) + "."}
            if legend:
                last["legend"] = legend
            if ann:
                last["annotations"] = [dict(a, id=nid + i + 1) for i, a in enumerate(ann)]
            out.append(last)
    return out


def _class_substeps(p, st, ex, idc, vals, cand, class_colour):
    """identity layer: a step's color work as sub-steps. Each color class (cells holding one unknown digit) keeps one
    color for the whole solve, with a legend the first time it appears ("orange: an unknown digit (3, 5 or 6)"); two
    classes that merge keep the older color. Updates idc (class per cell) and class_colour (class id -> color) in
    place; None for a step without joins or differences."""
    from .explain.base import Namer

    fx = st.get("idfx") or ()
    if not any(k in (CB.AE_ID_JOIN, CB.AE_ID_NEQ) for k, _, _ in fx):
        CB.id_apply(idc, vals, fx)
        return None
    nm = Namer(p)
    before = list(idc[: p.N])
    CB.id_apply(idc, vals, fx)
    N = p.N
    cls = {}
    for c in range(N):
        if idc[c]:
            cls.setdefault(idc[c], []).append(c)
    for k, ms in cls.items():  # a class inherits the color of the oldest colored class it absorbed
        olds = sorted({before[c] for c in ms if before[c] and before[c] in class_colour})
        if k not in class_colour and olds:
            class_colour[k] = class_colour[olds[0]]
    text = ex.get("short") or ex.get("notation") or ""
    if text[:1] != "r":  # a sentence, not a cell name first ("r3c9 ≠ 3: ...")
        text = text[:1].upper() + text[1:]
    sub = {"text": text + ("" if text.endswith(".") else ".")}
    gone = {}
    for c, d in st["elims"]:
        gone[c] = gone.get(c, 0) | (1 << (d - 1))
    legend, ann, parts = {}, [], []
    touched = []
    for k, c, a in fx:
        for x in (c, a) if k in (CB.AE_ID_JOIN, CB.AE_ID_NEQ) else ():
            if idc[x] and idc[x] not in touched:
                touched.append(idc[x])
    used = set(class_colour.values())
    for k in touched:
        if k not in class_colour:
            free = [x for x in CLASS_COLORS if x not in used] or list(CLASS_COLORS)
            class_colour[k] = free[0]
            used.add(free[0])
            m = (1 << p.D) - 1  # the class's digits: what every open member can still be
            for c in cls[k]:
                if not vals[c]:
                    m &= cand[c] & ~gone.get(c, 0)
            digs = [str(d) for d in range(1, p.D + 1) if m >> (d - 1) & 1]
            one = ", ".join(digs[:-1]) + " or " + digs[-1] if len(digs) > 1 else "".join(digs)
            legend[class_colour[k]] = f"an unknown digit ({one})" if digs else "an unknown digit"
        ann += [{"cell": nm.cell(c), "color": class_colour[k]} for c in sorted(cls[k], key=lambda x: p.coords[x])]
    for k, c, a in fx:
        if k == CB.AE_ID_JOIN and idc[c] in class_colour:
            col = class_colour[idc[c]]
            if col in legend:  # a new color: both cells start it
                parts.append(f"{nm.cell(c)} and {nm.cell(a)} are {col}")
            else:
                new = [x for x in (c, a) if before[x] != idc[x] and not (before[x] and before[x] in class_colour)]
                parts.append(f"{nm.cells(new) if new else nm.cell(c)} {'joins' if len(new) < 2 else 'join'} {col}")
        elif k == CB.AE_ID_NEQ and idc[c] in class_colour and idc[a] in class_colour:
            parts.append(f"{class_colour[idc[c]]} and {class_colour[idc[a]]} hold different digits")
    if legend:
        sub["legend"] = legend
    if ann:
        sub["annotations"] = [dict(x, id=i + 1) for i, x in enumerate(ann)]
    out = list(ex.get("substeps") or ()) or [sub]
    if out[0] is not sub:
        out.append({k: v for k, v in sub.items() if k != "text"} | {"text": "Colors: " + "; ".join(parts) + "."})
    elif parts:
        out.append({"text": "So " + "; ".join(parts) + "."})
    return out


def explain_steps(p, P, steps):
    """teaching text for band-path steps: rebuild each position, let the engine find that technique's moves there
    (one short solve with only that technique), take the move with exactly the same placement / eliminations and
    explain it (pencilmark/explain). -> [{"short", "teach"} or None] aligned with steps."""
    from . import explain as E

    E.derived(p)  # build the explainer's derived puzzle from the ORIGINAL p (its domains are rules); each step's copy
    # inherits it -- otherwise a copy builds it from its candidate masks and reads them as cell rules
    P = dict(P or {}, search="human")
    notes = set(S.NOTE_TECHS)
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    N = p.N
    vals, cand = start_position(p)
    out = []
    lab, region_colour = {}, {}  # regions to find: cell -> region label known so far; label -> color name (fixed)
    ids = any("idfx" in st for st in steps)  # identity layer: color classes, one color each for the whole solve
    idc, class_colour = [0] * N, {}
    for st in steps:
        q = copy.copy(p)
        q.givens = {c: v for c, v in enumerate(vals) if v}
        q.domains = [cand[c] if not vals[c] else 1 << (vals[c] - 1) for c in range(N)]
        want = (tuple(st["place"]) if st["place"] else None, frozenset(map(tuple, st["elims"])))
        t = rev.get(st["technique"])
        ex = None
        try:  # the band path's own move, explained directly (the explainer rebuilds the pattern itself)
            from types import SimpleNamespace as NS

            mv = NS(
                feat=(t,),
                place=tuple(st["place"]) if st["place"] else None,
                elim=tuple(map(tuple, st["elims"])),
                code=st.get("ecode"),
                lplace=st.get("lplace"),  # regions to find: label and relation effects (explained when nothing else is)
                lelim=list(st.get("lelims") or ()),
                rfx=list(st.get("rfx") or ()),
                # the engine's justification of this very move (units, chains, ALS, ...), else its pattern cells
                explain=CB.explain_record(
                    p,
                    {
                        "tech": t,
                        "code": st.get("ecode"),
                        "d": st.get("d"),
                        "place": st["place"],
                        "elim": st["elims"],
                        "xmeta": st.get("xmeta"),
                        "pattern": st.get("pattern"),
                        "ex": st.get("ex"),
                        "nm": st.get("nm"),
                    },
                    getattr(p, "_bp_cpuzzle", None),
                )
                or {"pattern_cells": list(st.get("pattern") or [])},
                xmeta=st.get("xmeta") or {},
                # the move's unit / cage / rule name, as solve() names it (the handlers find their rule by it)
                name=CB._name(p, *st["nm"]) if st.get("nm") else st["technique"],
                d=0.0,
                family=0,
            )
            mode = "direct" if "(direct)" in st["technique"] else "notes"
            e = E.explain(
                NS(move=mv, alts=[], mode=mode, n_empty=sum(1 for v in vals if not v)),
                q,
                E.State(q, vals, q.domains, mode),
            )
            if e.get("short") and not e.get("error") and e.get("derived", True) is not None:
                ex = {
                    "short": e.get("short"),
                    "teach": e.get("teach"),
                    "notation": step_notation(p, st, e.get("justification")),
                    "substeps": e.get("substeps"),
                }
        except Exception:
            ex = None
        if ex is None and t is not None:
            try:
                st1, _ = CB.solve(
                    q,
                    P,
                    disabled=set(S.TECH_NAMES) - {t} - notes,
                    max_steps=81 if st["band"] == 0 else 30,
                    labels=getattr(q, "_pm_labels", None),
                )
                for _, step, state in E.replay(q, st1):
                    mv = step.move
                    if mv.feat[0] != t:
                        continue
                    got = (tuple(mv.place) if mv.place else None, frozenset(map(tuple, mv.elim or ())))
                    mc = CB.code_name(mv.code) if isinstance(mv.code, int) else mv.code
                    if got != want or mc != st.get("ecode"):
                        continue  # same eliminations from another pattern would explain the wrong thing
                    e = E.explain(step, q, state)
                    tn = str((e.get("technique") or {}).get("pattern") or (e.get("technique") or {}).get("name") or "")
                    if (st["code"] == "FRK") != ("franken" in tn.lower() or "mutant" in tn.lower()) and st[
                        "technique"
                    ] in ("X-Wing", "Swordfish", "Jellyfish", "FinnedFish"):
                        continue
                    ex = {
                        "short": e.get("short"),
                        "teach": e.get("teach"),
                        "notation": step_notation(p, st, e.get("justification")),
                        "substeps": e.get("substeps"),
                    }
                    break
            except Exception:
                ex = None
        if ex is None:
            ex = {"notation": step_notation(p, st)}  # the notation needs no pattern: technique and result
        if st.get("lplace") or st.get("lelims"):
            ex["substeps"] = _region_substeps(p, st, ex, lab, region_colour)
        if ids:
            sub = _class_substeps(p, st, ex, idc, vals, cand, class_colour)
            if sub:
                ex["substeps"] = sub
        out.append(ex)
        apply_step(p, vals, cand, st)
    return out


def start_position(p):
    """the route's first position: the givens placed, every other cell its domain minus its peers' givens -> (vals,
    cand), cand a digit bit mask per cell (0 for placed cells)"""
    vals = [p.givens.get(c, 0) for c in range(p.N)]
    dom = getattr(p, "domains", None)
    cand = [0 if vals[c] else (dom[c] if dom else (1 << p.D) - 1) for c in range(p.N)]
    for c in range(p.N):
        if vals[c]:
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (vals[c] - 1))
    return vals, cand


def apply_step(p, vals, cand, st):
    """one route step on (vals, cand) in place: its placement (clearing the digit from the cell's peers), then its
    eliminations"""
    if st["place"]:
        c, d = st["place"]
        vals[c], cand[c] = d, 0
        for x in p.peer_list[c]:
            cand[x] &= ~(1 << (d - 1))
    for c, d in st["elims"]:
        cand[c] &= ~(1 << (d - 1))


def written_marks(p, steps, pos, P):
    """the marks a casual classic solver would have on paper at each position (pos = positions(p, steps)), following
    the engine's note model (params notes_live, snyder_max, notes_small, notes_lazy; docs/research/notes_dynamics.md):
    corner = position notes (a digit with 2..snyder_max places left in a box by the placed digits, noted once, from the
    start); center = candidate lists, written when notes start (the first step that is neither direct nor worked in the
    head) in the cells with <= notes_small candidates, then in every cell a step uses. Marks show only digits that are
    still candidates. -> [{cell index: (corner digits, center digits)}] per position; None when the model is off."""
    from .scoring import MENTAL

    live, lazy = bool(P.get("notes_live")), bool(P.get("notes_lazy"))
    if not (live or lazy):
        return None
    K, small = int(P.get("snyder_max", 2)), int(P.get("notes_small", 0) or 0)
    boxes = [g.cells for g in p.groups if getattr(g, "kind", "") == "box" and len(g.cells) == p.D]
    corner, centre, noted = {}, set(), set()
    notes_on = False

    def scan(vals):
        for i, cells in enumerate(boxes):
            present = {vals[c] for c in cells}
            for d in range(1, p.D + 1):
                if d in present or (i, d) in noted:
                    continue
                places = [c for c in cells if not vals[c] and not any(vals[q] == d for q in p.peer_list[c])]
                if 2 <= len(places) <= K:
                    noted.add((i, d))
                    for c in places:
                        corner.setdefault(c, set()).add(d)

    def snap(vals, cand):
        out = {}
        for c in range(p.N):
            if vals[c]:
                continue
            cs = sorted(d for d in corner.get(c, ()) if cand[c] >> (d - 1) & 1)
            ce = sorted(d for d in range(1, p.D + 1) if cand[c] >> (d - 1) & 1) if c in centre else []
            if cs or ce:
                out[c] = (cs, ce)
        return out

    if live:
        scan(pos[0][0])
    res = [snap(*pos[0])]
    for st, (vals0, cand0), (vals, cand) in zip(steps, pos[:-1], pos[1:]):
        name = st.get("name") or S.TECH_NAMES.get(st.get("tech"), "")
        if (
            lazy
            and not notes_on
            and st.get("tech") not in MENTAL
            and name != "FullHouse"
            and not name.endswith("(direct)")
        ):
            notes_on = True
            centre.update(c for c in range(p.N) if not vals0[c] and 0 < bin(cand0[c]).count("1") <= small)
        if notes_on:
            used = [st["place"][0]] if st.get("place") else []
            centre.update(used + [c for c, _ in st.get("elims") or ()])
        if live:
            scan(vals)
        res.append(snap(vals, cand))
    return res


MAX_COLOR_PAIRS = 3


def written_colours(p, pos, P):
    """the identity colors an expert would have painted at each position (pos = positions(p, steps); params
    notes_colours): pair coloring as hosts do it ("color the sevens and nines against each other", CtC solves):
    for a digit pair {a, b}, the cells whose candidates are exactly {a, b}; two of them in one house hold different
    digits, so they take opposite colors of a color pair (which color is a and which b is still open). Each color
    stands for one unknown digit and is tracked further: in a complete house without it, the single open cell that
    can hold one of its digits and sees none of its cells joins it; cells an equality rule joins (palindromes,
    clones) share it. A pair colored only in its two seed cells is left out (the center marks show a naked pair). A
    color pair keeps its names while its first cell stays in it; at most MAX_COLOR_PAIRS pairs, the largest.
    -> [[{"color", "cells", "digits", "opposite"}]] per position (cell indices); None when the model is off."""
    if not P.get("notes_colours"):
        return None
    houses = [g.cells for g in p.groups if g.complete and len(g.cells) == p.D]  # holds every digit exactly once
    eq = {}
    for r in getattr(p, "relations", ()):
        if r[0] == "eq":
            eq.setdefault(r[1], set()).add(r[2])
            eq.setdefault(r[2], set()).add(r[1])
    names = {}  # (pair mask, first cell) -> color pair, kept while it lasts

    def grow(col, m, vals, cand):
        changed = True
        while changed:
            changed = False
            for x in list(col):
                for y in eq.get(x, ()):
                    if y not in col and not vals[y]:
                        col.add(y)
                        changed = True
            for h in houses:
                if any(x in col for x in h) or any(vals[x] and (1 << (vals[x] - 1)) & m for x in h):
                    continue  # the color is already here, or its digit may be one placed here
                opts = [x for x in h if not vals[x] and cand[x] & m and not any(y in col for y in p.peer_list[x])]
                if len(opts) == 1:
                    col.add(opts[0])
                    changed = True

    out = []
    for vals, cand in pos:
        pairs = {}
        for c in range(p.N):
            if not vals[c] and bin(cand[c]).count("1") == 2:
                pairs.setdefault(cand[c], []).append(c)
        layer = []
        for m, cells in sorted(pairs.items()):
            adj = {x: [y for y in cells if y != x and y in p.peer_list[x]] for x in cells}
            side = {}
            for st in cells:
                if st in side or not adj[st]:
                    continue
                side[st], comp, todo = 0, [st], [st]
                while todo:
                    x = todo.pop()
                    for y in adj[x]:
                        if y not in side:
                            side[y] = 1 - side[x]
                            comp.append(y)
                            todo.append(y)
                cols = []
                for s in (0, 1):
                    col = {x for x in comp if side[x] == (s if side[min(comp)] == 0 else 1 - s)}
                    grow(col, m, vals, cand)
                    cols.append(col)
                if len(cols[0]) + len(cols[1]) < 3:
                    continue  # a bare naked pair: the center marks already show it, nobody colors it
                layer.append(((m, min(comp)), m, cols))
        # hosts keep about two colors on the board, rarely more than four to six (CtC action logs): the largest pairs
        layer.sort(key=lambda e: -(len(e[2][0]) + len(e[2][1])))
        taken, shown = set(), []
        for key, m, cols in layer[:MAX_COLOR_PAIRS]:
            pair = names.get(key)
            if pair is None or pair in taken:  # a color keeps its names unless another pair on the board has them
                pair = next(x for x in COLOR_PAIRS if x not in taken)
                names[key] = pair
            taken.add(pair)
            digits = [d for d in range(1, p.D + 1) if m >> (d - 1) & 1]
            shown += [
                {
                    "color": pair[s],
                    "cells": sorted(cols[s], key=lambda x: p.coords[x]),
                    "digits": digits,
                    "opposite": pair[1 - s],
                }
                for s in (0, 1)
            ]
        out.append(shown)
    return out


def positions(p, steps):
    """the positions of a route: before its first step, then after each step -> [(vals, cand)] of len(steps) + 1"""
    vals, cand = start_position(p)
    out = [(list(vals), list(cand))]
    for st in steps:
        apply_step(p, vals, cand, st)
        out.append((list(vals), list(cand)))
    return out
