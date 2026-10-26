"""Band-by-band human solve and technique hints.

The solve uses Very Easy moves until none are left, then Easy, then Medium, and so on, dropping back to the lowest band
after every move. Within a band it takes the simplest technique first (study order, docs/technique_bands_proposal.csv),
then the cheapest move. Each step is named by its most specific shape (a Skyscraper, not "X-Chain"; a Franken X-Wing,
not "X-Wing"), and its band comes from that shape.

The techniques this solve uses are the puzzle's hints: what a human solving from easy to hard will meet. SUBSET maps
each code to the codes it is a special case of (always true: every X-Wing is a Skyscraper), so a learner who knows
a technique also covers its special cases (covered(), lesson()).

    band_path(puzzle, P) -> {"solved", "band", "steps": [{code, name, band, place, elims}], "profile": {code: uses}}
"""
from collections import Counter
import copy

from . import solver as S, cbackend as CB, export as E2

BANDS = E2.BANDS
FORCING_FALLBACK = True     # R6: when no listed move exists, take the solver's forcing step (Extreme)
FISH_CAP = True            # below Hard, list finned fish of size 2 only (larger are Hard; 2026-10-26 speed)
FORCING_TECHS = {S.FORCING, S.DYN_FORCING, S.NESTED_FORCING, S.NISHIO, S.POM, S.TRIAL}

# most specific shape of an engine move -> (code, display name, band)
_X_CHAIN = {"SKY": ("SKY", "Skyscraper", 2), "2SK": ("KTE", "2-String Kite", 2), "TUR": ("TUR", "Turbot Fish", 2),
            "ER": ("ERE", "Empty Rectangle", 2), "XCH": ("XCL", "X-Chain", 3), "GXC": ("XCL", "Grouped X-Chain", 3)}

# study order inside a band; codes not listed fall back to the proposal csv order
_ORDER = {"FHS": 1, "HSI": 2, "NSI": 3, "LSI": 4, "CSI": 5,
          "PPR": 1, "SNY": 3, "NPR": 4, "HPR": 5, "MSI": 6, "NTR": 21, "HTR": 22,
          "XWG": 1, "SKY": 2.1, "KTE": 2.2, "TUR": 2.3, "ERE": 3, "SCL": 4, "FXW": 5,
          # Hard: shape codes beside their relatives (csv: SWF 1 .. JLF 9, XYC 11, MCL 12, 3DM 13, SUM 16); Franken fish
          # late for its obscurity
          "FSW": 1.5, "FJF": 9.5, "XCL": 10.8, "FRK": 12.5, "PHI": 16.5, "PHV": 16.6}

# A -> the codes A is always a special case of (theory; transitive closure below)
SUBSET = {
    "FHS": ["NSI", "HSI"],
    "XWG": ["SKY", "FXW", "FRK", "SWF"],   # an X-Wing is a Skyscraper whose ends line up; a finless finned X-Wing; a
                                           # Franken X-Wing using two lines; a Swordfish with a degenerate third line
    "SKY": ["TUR"], "KTE": ["TUR"], "ERE": ["TUR"],          # turbot fish = any 3-link single-digit chain
    "TUR": ["XCL"], "SCL": ["XCL"], "MCL": ["XCL"], "FXW": ["XCL"],   # colour traps / wraps, finned fish = (grouped) X-Chains
    "XCL": ["AIC"],
    "YWG": ["XYC"], "RMP": ["XYC"], "XYC": ["AIC"],          # Y-Wing = 3-cell XY-Chain; remote pairs = same-pair XY-Chain
    "XYZ": ["ALS"], "WXZ": ["ALS"],                          # XYZ / WXYZ-Wing are ALS-XZ cases
    "ALS": ["AAC"], "AXY": ["AAC", "DEB"], "AIC": ["AAC"], "NLP": ["AIC"],   # nice loop = AIC as a loop
    "PHI": ["LOL"], "PHV": ["LOL"],                          # Phistomefel is a law-of-leftovers instance (but Hard)
    "MSI": ["NPR", "NTR"],                                   # a subset seen without notes is still the subset
}


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
    return _ORDER.get(code, E2._order_table().get(code, 99))


def classify(m, p):
    """(code, name, band) of one state_moves move, by its most specific shape."""
    t, n, c = m["tech"], m["name"], m.get("code")
    if n == "X-Chain" and c in _X_CHAIN:
        return _X_CHAIN[c]
    if n == "MentalChain(direct)" and c in ("SKY", "2SK", "TUR", "ER"):     # a short chain seen without notes
        code, name, band = _X_CHAIN[c]
        return code, name + " (in the head)", band
    if n in ("X-Wing", "Swordfish") and m.get("pattern"):
        k = 2 if n == "X-Wing" else 3
        rows = {p.coords[x][0] for x in m["pattern"]}
        cols = {p.coords[x][1] for x in m["pattern"]}
        plain = min(len(rows), len(cols)) <= k and max(len(rows), len(cols)) <= k   # base and cover lines only
        if not plain:
            return "FRK", f"Franken {n}", 3
        return ("XWG", "X-Wing", 2) if n == "X-Wing" else ("SWF", "Swordfish", 3)
    if n == "LawOfLeftovers" and c in ("PHI", "Phistomefel variant"):
        return ("PHI", "Phistomefel ring", 3) if c == "PHI" else ("PHV", "Phistomefel variant", 3)
    if n == "Jellyfish" and c and "franken" in str(c).lower():
        return "FRK", "Franken Jellyfish", 3
    code, band = E2.chip_of(t, str(c) if c and n in E2.SPLIT else None)
    from .card import _code
    name = str(c) if c and n in E2.SPLIT else _code(n)[1]
    return code, name, band if band is not None else 9


# techniques that reason about variant rules: only switched on when the puzzle has such rules (user, 2026-10-15:
# "per-variant techniques should only be considered for their respective variants"). Fireworks and Gurth's theorem
# are classic techniques and stay on everywhere.
VARIANT_ANY = ["ConstraintSingle(direct)", "LineSingle(direct)", "PairwiseConstraint", "TableCombination", "LineRange",
               "LineScan", "LineClass", "SandwichCombination", "XSumCombination", "SkyscraperCombination",
               "CountCombination", "SetCombination", "ArrowCombination", "EqualDigits", "DigitCount", "RuleIntersection",
               "ImpliedHouses", "Domino", "ClassCount", "BandLogic", "ColourAlgebra", "CliqueHouse", "LineSets", "LineClues"]
VARIANT_SUM = ["CageCombination", "SumCombination", "Innie/Outie(direct)", "Innie/Outie(notes)", "Innie/Outie(sum)",
               "EqualSumCombination", "ComboLock", "SumBound", "SumAlgebra", "WeightedSums", "ComboPositions"]
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
        rs = {p.coords[c][0] for c in g.cells}; cs = {p.coords[c][1] for c in g.cells}
        return len(rs) * len(cs) == len(g.cells)
    regions = any(not rect(g) for g in boxes) or any(g.kind not in ("row", "col", "box") and g.complete for g in p.groups)
    # overlapping grids (samurai, twodoku, ...): set theory / implied houses come from the geometry, not a rule
    overlap = any(sum(1 for gi in p.groups_of[c] if p.groups[gi].kind == "box") > 1 for c in range(p.N))
    regions = regions or overlap
    off = set()
    if not cls and not has_sum and not regions:
        off |= {rev[n] for n in VARIANT_ANY if n in rev}
    elif not cls and not has_sum:       # geometry only (irregular / extra regions / overlapping grids): region logic stays
        off |= {rev[n] for n in VARIANT_ANY if n in rev and n not in ("ImpliedHouses", "DigitCount", "RuleIntersection")}
    if not has_sum:
        off |= {rev[n] for n in VARIANT_SUM if n in rev}
        if not regions:
            off.add(rev["LawOfLeftovers"])
    return off


_CACHE = None       # position -> state_moves, shared by the many routes of one contents() call (same openings)


LAZY = False   # REJECTED 2026-10-22 (v3 log): not exact (covers pricing, techniques that need others in the same call)
_SHAPED = set(E2.SPLIT) | {"MentalChain(direct)", "Swordfish", "Jellyfish"}   # classify() may give these a lower shape


def _lb(t, tb):
    """lower bound of the pick key (band, study order) for any move of engine technique t: exact for techniques named by
    their chip, conservative (band <= 2, order 0) for the ones classify() names by shape."""
    if S.TECH_NAMES.get(t) in _SHAPED:
        return (min(tb, 2), 0)
    return (tb, _order(E2.chip_of(t)[0]))


def band_path(p, P, max_steps=500, disabled=(), target=None, rng=None, ban_codes=(), guard=None, prefix=(), max_band=5):
    """solve band by band (see module doc). Moves are taken in full-notes mode: each placement clears its peers.
    target = a cell: stop once it is placed, preferring (within the current band) a move that places it -- "what does
    it take to place this cell from here". max_band: stop (unsolved) where only a harder move would continue -- contents()
    reruns can only count if they stay in the card's band, so they never list above it."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    P = dict(P or {}, search="human")
    notes = set(getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,)))
    comp = set(CB.search_disabled(P)) | {S.GUESS}
    ct = _code_techs(P)                 # whole-technique codes are switched off in the engine (it then reports a
    whole = set(ban_codes) & set(ct)    # placement under another technique); shape codes are filtered below
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
    q = copy.copy(p)                    # the puzzle keeps its own domains; each state's candidates go in as a mask
    cp = getattr(p, "_bp_cpuzzle", None)
    if cp is None:
        cp = CB.to_cpuzzle(p)           # built once per puzzle (the expensive part of a move listing)
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
    counts = Counter()
    aborted = False
    seg = max((st.get("seg", 0) for st in prefix), default=0)   # engine call each step came from
    def record(stp):
        nonlocal aborted
        steps.append(stp)
        counts[stp["code"]] += 1
        if guard is not None and not guard(stp, counts):
            aborted = True
    for stp in prefix:
        steps.append(stp)
        counts[stp["code"]] += 1
        apply({"place": stp["place"], "elim": stp["elims"]})
    for _ in range(max_steps):
        if aborted or all(vals) or (target is not None and vals[target]):
            break
        q.givens = {c: v for c, v in enumerate(vals) if v}
        mask = [cand[c] if not vals[c] else 1 << (vals[c] - 1) for c in range(N)]
        if allowed0 and rng is None:
            # Very Easy phase in ONE engine call: singles until none are left (90%+ of all steps). The engine
            # orders singles by price, not by study order, so only which single gets which label can differ.
            key0 = ("b0", tuple(vals), tuple(cand), frozenset(off0)) if _CACHE is not None else None
            batch = _CACHE.get(key0) if key0 is not None else None
            if batch is None:
                st0, _ = CB.solve(q, P, disabled=off0, cpuzzle=cp, cand=mask, max_steps=N + 5, assume_unique=False)
                batch = [{"tech": x.move.feat[0], "name": S.TECH_NAMES.get(x.move.feat[0], "?"), "code": x.move.code,
                          "place": tuple(x.move.place) if x.move.place else None,
                          "elim": [tuple(e) for e in (x.move.elim or ())], "xmeta": getattr(x.move, "xmeta", None),
                          "d": float(x.move.d) if x.move.d is not None else None}
                         for x in st0 if x.move.feat[0] not in notes and x.move.feat[0] in allowed0]
                if key0 is not None:
                    _CACHE[key0] = batch
            moved = False
            seg += 1
            for m in batch:
                if not (m["place"] or m["elim"]):
                    continue
                if m["place"] and vals[m["place"][0]]:
                    continue
                code, name, mb = classify(m, p)
                apply(m)
                record({"code": code, "name": name, "band": 0, "technique": m["name"], "ecode": m.get("code"),
                        "xmeta": m.get("xmeta"), "tech": m["tech"], "place": m["place"], "elims": list(m["elim"]),
                        "seg": seg, "d": m.get("d")})
                moved = True
                if aborted or (target is not None and vals[target]):
                    break
            if moved:
                continue
        pick = None
        for b in range(1 if allowed0 and rng is None else 0, max_band + 1):
            allowed = {t for t in human if tband[t] <= b}
            if not allowed:
                continue
            # LAZY (2026-10-22, user idea): techniques in lower-bound order of the pick key (band, study order); stop
            # once the best move found beats every technique not yet run -- the expensive ones (RuleIntersection,
            # SumAlgebra ...) only run when nothing simpler exists. rng mode keeps the one-call form.
            if LAZY and rng is None:
                groups = {}
                for t in allowed:
                    groups.setdefault(_lb(t, tband[t]), set()).add(t)
                tiers = sorted(groups)
            else:
                tiers = [None]
            enabled = set()
            cands = []
            mv_all = []
            for k_, lbk in enumerate(tiers):
                run = groups[lbk] if lbk is not None else allowed   # each group runs once; its moves are merged
                enabled |= run
                # below Hard only size-2 finned fish can be picked (larger ones are Hard): don't list them (windoku 2026-10-26:
                # sizes 3-4 were 90% of a listing over 58 houses)
                Pb = dict(P, fish_max_n=2) if b <= 2 and FISH_CAP else P
                key = (tuple(vals), tuple(cand), frozenset(run), b <= 2) if _CACHE is not None else None
                mv = _CACHE.get(key) if key is not None else None
                if mv is None:
                    mv = CB.state_moves(q, Pb, disabled=set(S.TECH_NAMES) - run, limit_per_tech=8, details=True,
                                        cpuzzle=cp, cand=mask)
                    if key is not None:
                        _CACHE[key] = mv
                mv_all.extend(mv)
                cands = []
                for m in mv_all:
                    if m["tech"] not in enabled or not (m["place"] or m["elim"]):
                        continue
                    code, name, mb = classify(m, p)
                    if code in ban_codes:
                        continue
                    if mb <= b:
                        hit = 0 if target is not None and m["place"] and m["place"][0] == target else 1
                        key = (mb, hit, rng.random()) if rng is not None else (mb, hit, _order(code), m["d"])
                        cands.append((key, code, name, mb, m))   # rng: any move of the lowest band (other solvers)
                if cands and lbk is not None and k_ + 1 < len(tiers):
                    best = min(c_[0] for c_ in cands)
                    nb, no = tiers[k_ + 1]
                    if (best[0], best[1], best[2]) < (nb, 0, no):
                        break
            if cands:
                pick = min(cands, key=lambda x: x[0])
                break
        if pick is None and FORCING_FALLBACK and P.get("r6_extreme", True) and rng is None and max_band >= 5:
            # R6 (2026-10-26): nothing listed in any band -> one solver step from this state. The solver's stuck-fallback
            # tries forcing chains / dynamic / nested forcing / Nishio / pattern overlay (state_moves never lists them);
            # such a step is an Extreme move. A guess means really stuck -> Unknown as before.
            st1, _ = CB.solve(q, P, cpuzzle=cp, cand=mask, max_steps=4, assume_unique=False)   # first steps may be notes
            x = next((y for y in st1 if y.move.feat[0] not in notes), None)
            # guessing off (default): the solver's last resort is a proof by full search (TRIAL), an Extreme step too
            stop = (S.GUESS, S.TRIAL) if P.get("allow_guess", False) else (S.GUESS,)
            if x is not None and x.move.feat[0] not in stop and (x.move.place or x.move.elim):
                m = {"tech": x.move.feat[0], "name": S.TECH_NAMES.get(x.move.feat[0], "?"), "code": x.move.code,
                     "place": tuple(x.move.place) if x.move.place else None,
                     "elim": [tuple(e) for e in (x.move.elim or ())], "xmeta": getattr(x.move, "xmeta", None),
                     "d": float(x.move.d) if x.move.d is not None else None}
                code, name, mb = classify(m, p)
                # a forcing step is Extreme; any other human step the move listing missed keeps its own band
                pick = ((mb, 1, 0, m["d"]), code, name, max(mb, 5) if m["tech"] in FORCING_TECHS else mb, m)
        if pick is None:
            break
        _, code, name, mb, m = pick
        apply(m)
        seg += 1
        record({"code": code, "name": name, "band": mb, "technique": m["name"], "ecode": m.get("code"),
                "xmeta": m.get("xmeta"), "tech": m["tech"],
                "place": tuple(m["place"]) if m["place"] else None, "elims": [tuple(e) for e in m["elim"]],
                "seg": seg, "d": m.get("d")})
    if target is not None:
        top = max((s_["band"] for s_ in steps), default=0)
        return {"placed": bool(vals[target]), "band_index": top if vals[target] else None, "steps": steps,
                "codes": dict(Counter(s_["code"] for s_ in steps))}
    solved = all(vals) and not aborted
    prof = Counter(s["code"] for s in steps)
    top = max((s["band"] for s in steps), default=0)
    return {"solved": solved, "band": BANDS[top] if solved else "Unknown", "band_index": top if solved else None,
            "steps": steps, "profile": dict(prof),
            "hints": {BANDS[b]: dict(Counter(s["code"] for s in steps if s["band"] == b))
                      for b in range(0, 6) if any(s["band"] == b for s in steps)}}


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


def _route_ok(bp, alt, code, extra=()):
    """alt (a route with `code` banned) keeps bp's band, uses nothing new except `extra` and special cases of what's
    listed, and moves code's work only to techniques of its band or lower that aren't generalisations of it."""
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
    going to a harder technique or a generalisation of `code` -- counts only grow, so the verdict is final).
    The prefix (base route up to the first banned step) is NOT used by contents(): a whole-technique ban also removes
    composite moves built on it (a "notes in the head" single using innies / outies is labelled MSI), so a banned
    route can differ before the banned code's first use (found 2026-10-15 on LMD x1zh931q9w)."""
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
    if k < len(bp["steps"]):    # resume only where the base route also made a fresh engine call: a batched-singles
        sg = bp["steps"][k].get("seg")      # call carries mode state, so restarting mid-batch could drift
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
    for st in steps:
        q = copy.copy(p)
        q.givens = {c: v for c, v in enumerate(vals) if v}
        q.domains = [cand[c] if not vals[c] else 1 << (vals[c] - 1) for c in range(N)]
        yield q
        if st["place"]:
            c, d = st["place"]
            vals[c], cand[c] = d, 0
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (d - 1))
        for c, d in st["elims"]:
            cand[c] &= ~(1 << (d - 1))


def contents(p, P, alternatives=True, deadline=None):
    """What's in the puzzle, deterministically (same puzzle -> same card).
    1. band_path (easy to hard, simplest technique first).
    2. Shrink: each listed technique is tried for removal (banned by its exact code), later in the study order first,
       so the simpler of two interchangeable ones stays; kept only if _route_ok (same band, nothing new but special
       cases of what's listed, its work not moved to a harder technique or a generalisation of it).
    3. Alternatives: for each listed technique X, every same-band technique Y that is NOT on X's subset chain (neither
       is a special case of the other) and was available where X was used, is tested by banning X: if the puzzle then
       solves with the listed techniques plus Y (_route_ok, Y actually used), X/Y is a joint chip -- "solvable if you
       know either". Same-chain relations stay out: the player's subset table covers them (a Turbot learner can do
       Skyscrapers).
    Full houses fold into the listed single. -> band_path result + "removed", "alternatives" {code: [codes]}.
    deadline (time.time() value, opt-in; default None = deterministic): shrink / alternatives stop when it passes and the
    result carries "truncated": True (the base route is always complete; the list may then not be minimal / miss joint chips)."""
    global _CACHE
    _CACHE = {}
    try:
        return _contents(p, P, alternatives, deadline)
    finally:
        _CACHE = None


def _contents(p, P, alternatives, deadline=None):
    import time
    late = lambda: deadline is not None and time.time() > deadline
    truncated = False
    bp = band_path(p, P)
    if not bp["solved"]:
        return dict(bp, removed=[], alternatives={}, profile=fold(bp["profile"]))
    ban, removed, failed = set(), [], set()
    while True:                         # passes over the list; a code that failed is retried only after a change
        bandof = {st["code"]: st["band"] for st in bp["steps"]}
        changed = False
        for code, _ in sorted(bp["profile"].items(), key=lambda x: (-bandof[x[0]], -_order(x[0]), x[1])):
            if code == "FHS" or code in failed or code not in bp["profile"]:
                continue                # full houses fold in at the end, never removed
            if late():
                truncated = True
                break
            g_, _ = _check(bp, code, ban | {code})
            alt = band_path(p, P, ban_codes=ban | {code}, guard=g_, max_band=bp["band_index"])
            if _route_ok(bp, alt, code):
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
            for st, q in spots[:6]:                 # what else of this band was on offer where X was used
                g = copy.copy(p)
                g.givens = q.givens
                for m in CB.state_moves(g, dict(P, fish_max_n=2) if b <= 2 and FISH_CAP else P,
                                        disabled=set(S.TECH_NAMES) - {t for t in allowed_t if E2.tech_band(t) <= b},
                                        limit_per_tech=8, details=True, cpuzzle=getattr(p, "_bp_cpuzzle", None),
                                        cand=q.domains):
                    c2, _, b2 = classify(m, p)
                    if b2 == b and c2 != code and (m["place"] or m["elim"]):
                        seen.add(c2)
            alt0 = None
            for y in sorted(seen, key=_order):
                if y in bp["profile"] or covered(y, {code}) or covered(code, {y}):
                    continue                        # listed already, or on X's chain: the subset table covers it
                base = (ban - {y}) | {code}         # a technique dropped in the shrink may still be an alternative
                if y not in ban:
                    if alt0 is None:     # no guard: shared by every candidate y (each may differ in what's allowed)
                        alt0 = band_path(p, P, ban_codes=base, max_band=bp["band_index"])
                    if alt0["profile"].get(y) and _route_ok(bp, alt0, code, extra={y}):
                        alts.setdefault(code, []).append(y)
                        continue
                # the route may have taken another candidate first; ban the others to test y alone
                others = seen - {y, code} - set(bp["profile"])
                g_, _ = _check(bp, code, base | others, extra={y})
                alt = band_path(p, P, ban_codes=base | others, guard=g_, max_band=bp["band_index"])
                if alt["profile"].get(y) and _route_ok(bp, alt, code, extra={y}):
                    alts.setdefault(code, []).append(y)
    for code, ys in list(alts.items()):     # keep the most specific: drop an alternative that generalises another
        chip = [code] + ys                  # one in the same chip (a mental subset working implies NPR works)
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
    """content filter: no hint is a banned technique or a generalisation of one (not ready for Skyscrapers means not
    ready for Turbot Fish / X-Chains either). Special cases of a banned code stay allowed (an X-Wing is fine when
    Skyscrapers are banned)."""
    ban = set(banned)
    return not any(c in ban or SUPERSETS.get(b, set()) & {c} for c in profile for b in ban)


def lesson(profile, target, known=()):
    """is this a lesson puzzle for `target` given `known` techniques: the target itself appears (a Skyscraper puzzle
    is solvable by a Turbot learner but doesn't teach Turbot), and every other hint is covered by known + target."""
    k = set(known)
    return target in profile and not covered(target, k) and all(covered(c, k | {target}) for c in profile)


def explain_steps(p, P, steps):
    """teaching text for band-path steps: rebuild each position, let the engine find that technique's moves there
    (one short solve with only that technique), take the move with exactly the same placement / eliminations and
    explain it (pencilmark/explain). -> [{"short", "teach"} or None] aligned with steps."""
    from . import explain as E
    E.derived(p)        # build the explainer's derived puzzle from the ORIGINAL p (its domains are rules); each step's copy
                        # inherits it -- otherwise a copy builds it from its candidate masks and reads them as cell rules
                        # (found 2026-10-22: explanations were right only when card.specific_names had run first)
    P = dict(P or {}, search="human")
    notes = set(getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,)))
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    N, D = p.N, p.D
    vals = [p.givens.get(c, 0) for c in range(N)]
    dom = getattr(p, "domains", None)
    cand = [0 if vals[c] else (dom[c] if dom else (1 << D) - 1) for c in range(N)]
    for c in range(N):
        if vals[c]:
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (vals[c] - 1))
    out = []
    for st in steps:
        q = copy.copy(p)
        q.givens = {c: v for c, v in enumerate(vals) if v}
        q.domains = [cand[c] if not vals[c] else 1 << (vals[c] - 1) for c in range(N)]
        want = (tuple(st["place"]) if st["place"] else None, frozenset(map(tuple, st["elims"])))
        t = rev.get(st["technique"])
        ex = None
        try:        # the band path's own move, explained directly (the explainer rebuilds the pattern itself)
            from types import SimpleNamespace as NS
            mv = NS(feat=(t,), place=tuple(st["place"]) if st["place"] else None, elim=tuple(map(tuple, st["elims"])),
                    code=st.get("ecode"), explain={}, xmeta=st.get("xmeta") or {}, name=st["technique"], d=0.0, family=0)
            mode = "direct" if "(direct)" in st["technique"] else "notes"
            e = E.explain(NS(move=mv, alts=[], mode=mode, n_empty=sum(1 for v in vals if not v)), q,
                          E.State(q, vals, q.domains, mode))
            if e.get("short") and not e.get("error") and e.get("derived", True) is not None:
                ex = {"short": e.get("short"), "teach": e.get("teach")}
        except Exception:
            ex = None
        if ex is None and t is not None:
            try:
                st1, _ = CB.solve(q, P, disabled=set(S.TECH_NAMES) - {t} - notes, max_steps=81 if st["band"] == 0 else 30)
                for _, step, state in E.replay(q, st1):
                    mv = step.move
                    if mv.feat[0] != t:
                        continue
                    got = (tuple(mv.place) if mv.place else None, frozenset(map(tuple, mv.elim or ())))
                    mc = CB.code_name(mv.code) if isinstance(mv.code, int) else mv.code
                    if got != want or mc != st.get("ecode"):
                        continue        # same eliminations from another pattern would explain the wrong thing
                    e = E.explain(step, q, state)
                    tn = str((e.get("technique") or {}).get("pattern") or (e.get("technique") or {}).get("name") or "")
                    if (st["code"] == "FRK") != ("franken" in tn.lower() or "mutant" in tn.lower()) and \
                            st["technique"] in ("X-Wing", "Swordfish", "Jellyfish", "FinnedFish"):
                        continue
                    ex = {"short": e.get("short"), "teach": e.get("teach")}
                    break
            except Exception:
                ex = None
        out.append(ex)
        if st["place"]:
            c, d = st["place"]
            vals[c], cand[c] = d, 0
            for x in p.peer_list[c]:
                cand[x] &= ~(1 << (d - 1))
        for c, d in st["elims"]:
            cand[c] &= ~(1 << (d - 1))
    return out
