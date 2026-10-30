"""Per-move difficulty, race-model time, and puzzle-level grade.

Difficulty of a move (SE-like scale, Full House in a square 9-cell house = 1):

  direct singles:  d = B[tech] * base_shape^gamma * size(D)
                       + sum_i K[kind_i] * shape_i^gamma * uncovered_i
      the set-cover formulation of the C# naked-single code: every extra group
      you have to combine costs K * shape * (items still unexplained), for
      naked singles items = digits, for hidden singles items = cells.
  notes techniques: d = B[tech] * shape^gamma * size(D)
  TakeNotes:        d = B[TAKE_NOTES]  (writing notes is itself a skill gate)

size(D) = ((D-1)/8)^alpha: how many alternatives a basic check discriminates
between; can't be fitted from 9x9-only data, set from first principles.

Time (race model): every available move m is noticed at rate
exp(-beta * d_m) / (c * scan), scan = empty cells. Expected time to the next
move is c * scan / sum_m exp(-beta * d_m); plus writing digits, writing and
erasing notes. Many simultaneous moves -> fast (sudoku.coach's tediousness);
bigger board -> more scan, but also more simultaneous moves.

Grade: soft bottleneck over the chosen steps --
  d_max + tau * log( sum_i exp((d_i - d_max)/tau) * ref_steps / n_steps )
clipped at d_max. Counting hard steps as a DENSITY means a samurai (five
9x9s each needing one X-Wing) grades like one of its 9x9s, while a single
9x9 needing five X-Wings grades higher than one needing one.
"""

from __future__ import annotations

import math

from . import solver as S

TECHS = sorted(S.TECH_NAMES)
TECH_IDX = {t: i for i, t in enumerate(TECHS)}
N_KINDS = 9
CMAX = 10

DEFAULT_PARAMS = {
    "B": {
        S.FULL_HOUSE: 1.0,
        S.NAKED_D: 1.2,
        S.HIDDEN_D: 1.0,
        S.NAKED_DL: 2.2,
        S.HIDDEN_DL: 2.0,
        S.TAKE_NOTES: 2.5,
        S.NAKED_N: 0.8,
        S.HIDDEN_N: 1.0,
        S.LOCKED: 2.6,
        S.NPAIR: 3.0,
        S.HPAIR: 3.6,
        S.NTRIPLE: 4.0,
        S.HTRIPLE: 4.6,
        S.NQUAD: 5.0,
        S.HQUAD: 5.6,
        S.XWING: 4.6,
        S.SWORDFISH: 5.6,
        S.XYWING: 4.8,
        S.XYZWING: 5.2,
        S.COLORING: 5.0,
        S.PAIRARC: 2.6,
        S.TRIAL: 7.0,
        S.GUESS: 10.0,
        S.INNIE_D: 2.5,
        S.CAGE_COMBO: 1.8,
        S.INNIE_N: 2.6,
        S.SUM_COMBO: 1.8,
        S.ARROW_COMBO: 2.0,
        S.SET_COMBO: 2.0,
        S.EQSUM_COMBO: 2.6,
        S.TABLE_COMBO: 2.6,
        S.COMBO_LOCK: 2.8,
        S.NARY_D: 2.0,
        S.INNIE_X: 3.2,
        S.FINNED_FISH: 5.4,
        S.JELLYFISH: 6.4,
        S.X_CHAIN: 5.2,
        S.XY_CHAIN: 5.6,
        S.AIC_CHAIN: 6.4,
        S.NICE_LOOP: 6.8,
        S.SANDWICH_COMBO: 2.6,
        S.XSUM_COMBO: 2.6,
        S.SKYLINE_COMBO: 2.6,
        S.LOL_COMBO: 3.0,
        S.IMPLIED: 3.0,
        S.UNIQUE_RECT: 4.6,
        S.BUG_PLUS1: 5.6,
        S.ALS_XZ: 6.6,
        S.ALS_XYWING: 7.0,
        S.DEATH_BLOSSOM: 7.4,
        S.ALS_AIC: 7.6,
        S.CANONICAL: 1.0,
        S.COUNT_COMBO: 2.0,
        S.LINE_D: 1.6,
        S.LINE_RANGE: 2.0,
        S.MENTAL_D: 2.4,
        S.SHORT_TRIAL: 6.2,
        S.MENTAL_CHAIN: 4.0,
        S.EITHER_WAY: 5.8,
        S.LINE_CLASS: 1.6,
        S.DIGIT_COUNT: 4.6,
        S.EQUAL_DIGITS: 5.0,
        S.LINE_SCAN: 1.8,
        S.FORCING: 6.0,
        S.DYN_FORCING: 6.4,
        S.NESTED_FORCING: 6.6,
        S.MEDUSA: 6.3,
        S.SUM_BOUND: 1.5,
        S.CLASS_COUNT: 2.4,
        S.CLASS_COLOUR: 5.0,
        S.DOMINO: 2.2,
        S.COLOUR_ALGEBRA: 5.4,
        S.N_WING: 6.2,
        S.SUE_DE_COQ: 6.6,
        S.APE: 6.8,
        S.CHUTE_RP: 5.6,
        S.POM: 7.2,
        S.GURTH: 5.0,
        S.NISHIO: 5.6,
        S.WHAT_IF: 5.2,
        S.MENTAL_NOTES: 3.0,
        S.MULTI_COLOR: 5.9,
        S.REMOTE_PAIRS: 4.8,
        S.EMPTY_RECT: 4.6,
        S.RULE_INTERSECT: 5.0,
        S.SUM_ALGEBRA: 6.0,
        S.SNYDER_MARKS: 1.5,
        S.SNYDER_D: 2.3,
        S.BAND_LOGIC: 6.6,
    },
    "K": [0.15, 0.2, 0.25, 0.3, 0.05, 0.4, 0.3, 0.35, 0.45],  # house, cage, neq, nonconsec, domain, lock,
    # cage-sum, line/relation inference, mental subset
    "gamma": 0.5,
    "alpha": 1.0,
    "beta": 1.0,
    "c": 1.0,  # seconds per scanned empty cell (before difficulty)
    "t_place": 1.5,  # seconds to write a digit
    "t_mark": 0.4,  # seconds per pencil mark written
    "t_erase": 0.3,  # seconds per pencil mark erased
    "t0": 10.0,  # fixed overhead
    "tau": 0.15,
    "ref_steps": 55.0,
}

DIRECT = set(S.DIRECT_TECHS)


# human mode (params["human_mode"] = {"budget": [...], "k": [...]}, any omitted -> these):
# difficulty *= exp(sum_j k_j * max(0, load_j - budget_j)); loads (feature element 5, from
# the C++ core): cells scanned, log(1 + combos considered), propagation depth, constraints
# involved, search-like, pattern cells, chain length
HUMAN_BUDGET = [27.0, 1.95, 2.0, 4.0, 0.0, 9.0, 7.0, 0.0]
HUMAN_K = [0.02, 0.15, 0.3, 0.08, 0.7, 0.05, 0.1, 0.0]


def copy_params(p):
    return {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in p.items()}


TRIAL_FAMILY_META_EXCLUDE = (26, 61, 63, 68, 69, 70, 80, 82, 83)


def complete_params(P):
    """Fill params fitted before a technique/kind existed with defaults."""
    P = copy_params(P)
    for t, v in DEFAULT_PARAMS["B"].items():
        P["B"].setdefault(t, v)
    P["B"].setdefault(
        S.FIREWORKS, P["B"].get(S.HTRIPLE, 3.0)
    )  # no own price: the fallback B (no meta model) is the Hidden Triple's
    P["B"].setdefault(S.HUMAN_CASE, P["B"].get(S.ALS_XZ, 5.0))  # no own price either: fallback = ALS-XZ's B
    P["B"].setdefault(S.COMBO_POS, P["B"].get(S.HTRIPLE, 3.0))
    P["B"].setdefault(S.CLIQUE_HOUSE, P["B"].get(S.HTRIPLE, 3.0))
    P["B"].setdefault(S.LINE_SETS, P["B"].get(S.HTRIPLE, 3.0))
    P["B"].setdefault(S.LINE_CLUES, P["B"].get(S.HTRIPLE, 3.0))
    P["B"].setdefault(S.WEIGHTED_SUMS, P["B"].get(S.HTRIPLE, 3.0))
    K = list(P["K"])
    K += DEFAULT_PARAMS["K"][len(K) :]
    P["K"] = K
    for k, v in DEFAULT_PARAMS.items():
        P.setdefault(k, v)
    # the trial family has no fitted offset yet: priced by B, not by the structural meta model (whose
    # negative cells weight would make big case splits nearly free); the refit replaces this
    P.setdefault("meta_exclude", list(TRIAL_FAMILY_META_EXCLUDE))
    return P


META_NAMES = [
    "const",
    "log cells",
    "log groups",
    "log digits",
    "links",
    "hidden",
    "arith",
    "relation",
    "notes",
    "log spread",
]


# structural descriptors (csolver desc.cpp; meta[10:16] of canonical-mode moves = featurize m_meta[:, 10:16]):
# exported for refits, not priced here
DESC_NAMES = ["log branches", "log depth", "search", "uniqueness", "counting", "contradiction", "held", "coverage"]


def meta_vector(meta, desc=True):
    """Meta vector: META_NAMES (the 10 pricing columns) + the 6 structural descriptors DESC_NAMES (csolver
    desc.cpp, meta[10:18]; zeros for moves / older binaries without them) = the 18 columns of C++ featurize
    m_meta. desc=False: the 10 pricing columns only (what Scorer.difficulty prices with)."""
    cells, groups, digits, links, hidden, arith, rel, notes, spread = meta[:9]  # meta[9]: table live tuples
    x = [
        1.0,
        math.log(max(cells, 1)),
        math.log(max(groups, 1)),
        math.log(max(digits, 1)),
        float(links),
        float(hidden),
        float(arith),
        float(rel),
        float(notes),
        math.log(max(spread, 1e-6)),
    ]
    if desc:
        nd = len(DESC_NAMES)
        if len(meta) >= 10 + nd:
            x += [float(v) for v in meta[10 : 10 + nd]]
        elif len(meta) >= 16:  # dev68-72 layout: 6 descriptors
            x += [float(v) for v in meta[10:16]] + [0.0] * (nd - 6)
        else:
            x += [0.0] * nd
    return x


# named patterns without an own price: always priced by the structural meta model when params have one
STRUCTURAL_ONLY = {S.FIREWORKS, S.HUMAN_CASE, S.COMBO_POS, S.CLIQUE_HOUSE, S.LINE_SETS, S.LINE_CLUES, S.WEIGHTED_SUMS}


def meta_priced(meta):
    """True when the move is priced by the structural meta model today. meta[18] = 1: the meta tuple was
    exported for a technique priced by its own B (desc.cpp, every technique carries a meta in canonical mode)."""
    if meta is None:
        return False
    if len(meta) >= 19:  # dev75+: 8 descriptors, flag at [18]
        return not meta[18]
    return not (len(meta) == 17 and meta[16])  # dev68-74 layout: 6 descriptors, flag at [16]


class Scorer:
    def __init__(self, params=None):
        self.p = complete_params(params or DEFAULT_PARAMS)
        self.meta = self.p.get("meta_theta")  # if set: strategies graded by structure, not per-technique

    def size(self, D):
        return ((D - 1) / 8.0) ** self.p["alpha"]

    def difficulty(self, feat, D):
        tech, base_shape, cover, extra = feat[:4]
        P = self.p
        g = P["gamma"]
        if tech in S.NOTE_TECHS:
            return P["B"][tech]
        meta = feat[4] if len(feat) > 4 else None
        # params mental_floor (mirrors csolver Params::difficulty): a move done in the head costs at least its
        # written counterpart -- the same pattern with notes (MentalNotesSingle: the notes technique in 'extra')
        if (
            P.get("mental_floor")
            and not getattr(self, "_in_floor", False)
            and meta is not None
            and (meta_priced(meta) or P.get("meta_theta_full"))
            and meta[7] == 0
            and tech in (S.MENTAL_D, S.MENTAL_CHAIN, S.MENTAL_NOTES, S.EITHER_WAY, S.WHAT_IF, S.SHORT_TRIAL)
        ):
            self._in_floor = True
            try:
                base = self.difficulty(feat, D)
                w = list(meta)
                w[7] = 1
                if P.get("theta_full_v2") and P.get("meta_theta_full") and len(w) >= 18:
                    w[17] = 1.0
                t2 = extra if tech == S.MENTAL_NOTES and 0 < extra < 128 else tech
                written = self.difficulty((t2, base_shape, cover, extra, tuple(w)) + tuple(feat[5:]), D)
            finally:
                self._in_floor = False
            return max(base, written)
        # the meta-theta model prices only the techniques it was fitted on (codes < meta_max_tech, default 68:
        # everything added after the last fit uses its base difficulty B)
        full = P.get("meta_theta_full")  # mirrors csolver: every technique by its full structural vector
        if full and meta is not None:
            x = meta_vector(meta, desc=False)
            if P.get("theta_full_v2"):
                x[4] = math.log1p(max(0.0, x[4]))
            x += [float(v) for v in meta[10:18]] if len(meta) >= 18 else [0.0] * 8
            if len(full) > 18:
                x.append(float(meta[19]) if len(meta) > 19 else 0.0)
            z = sum(a * b for a, b in zip(full, x))
            te = P.get("meta_theta_enum")
            if te:  # D5 mirror: enumeration size of the sum rules the move touches (meta[20])
                z += te * (float(meta[20]) if len(meta) > 20 else 0.0)
            ti = P.get("meta_theta_interact")
            if ti and len(ti) >= 3:  # D6 mirror: log depth x (log cells, links, log branches)
                br, dp = x[10], x[11]
                z += ti[0] * dp * x[1] + ti[1] * dp * x[4] + ti[2] * dp * br
            to = P.get("tech_obscurity")  # obscurity mirror: per-technique log-price offset by tech code
            if to and 0 <= tech < len(to):
                z += to[tech]
            d = math.exp(min(z, 6.907755278982137)) * self.size(D)  # cap log price at log(1000), as C++
        elif (
            self.meta is not None
            and meta_priced(meta)
            and (tech < P.get("meta_max_tech", 68) or tech in STRUCTURAL_ONLY)
            and tech not in (P.get("meta_exclude") or ())
        ):
            x = meta_vector(meta, desc=False)
            z = sum(a * b for a, b in zip(self.meta, x))
            tac = P.get("meta_theta_arith_cells") or 0.0
            if tac:  # arith x log cells interaction (pattern techniques stay monotone in size)
                z += tac * (x[6] * x[1])
            d = math.exp(z) * self.size(D)
            off = P.get("tech_offset")  # optional family offsets on top of the structural meta
            if off and tech in off:
                d *= math.exp(off[tech])
        else:
            d = P["B"][tech] * (base_shape**g if base_shape > 0 or g >= 0 else math.inf) * self.size(D)
        if tech in DIRECT:
            K = P["K"]
            for kind, shape, u in cover:
                d += K[kind] * (shape**g) * u
        pm = meta_priced(meta) and not (full and meta is not None)  # (meta_theta_full: no technique multipliers)
        if tech in (S.FORCING, S.DYN_FORCING, S.NESTED_FORCING) and pm:
            # forcing chains: nesting level, branching (extra = options) and propagation size (links)
            level = tech - S.FORCING
            d *= (
                math.exp(P.get("forcing_depth", 1.0) * level)
                * max(extra, 1) ** P.get("forcing_branch", 1.0)
                * (1.0 + math.log1p(max(meta[0], 0)))
            )
        if tech == S.COLOUR_ALGEBRA and pm and P.get("colour_chain_k", 0.0):
            # colours / labels involved and the relation-chain length (off by default = published build)
            d *= 1.0 + P.get("colour_chain_k", 0.0) * (0.1 * max(meta[1] - 1, 0) + 0.15 * meta[3])
        if (
            pm
            and len(meta) > 9
            and meta[9] > 1
            and P.get("k_tab", 0.5)
            and tech in (S.LINE_D, S.MENTAL_D, S.NARY_D, S.TABLE_COMBO)
        ):
            d *= 1.0 + P.get("k_tab", 0.5) * math.log(meta[9])  # case analysis over the table's live tuples
        if tech == S.SUM_ALGEBRA and pm:  # units combined, chain of bounds
            d *= 1.0 + 0.1 * max(meta[1] - 2, 0) + 0.25 * max(meta[3] - 1, 0)
        if tech == S.BAND_LOGIC and pm:  # units, open cells; search needed (cases)
            d *= (1.0 + 0.1 * max(meta[1] - 3, 0) + 0.02 * max(meta[0] - 9, 0)) * (
                1.0 + P.get("band_k", 0.25) * math.log(max(meta[3], 1))
            )
        if tech == S.RULE_INTERSECT and pm:  # cells held together, rules combined
            d *= 1.0 + 0.1 * max(meta[0] - 4, 0) + 0.25 * max(meta[3] - 2, 0)
        if tech == S.GUESS and pm:  # expected refutation work of the wrong candidates
            d = P["B"][tech] * self.size(D) * (1.0 + P.get("guess_k", 0.02) * meta[0] / 10.0)
        if tech in (S.TRIAL, S.SHORT_TRIAL) and pm:  # depth the refutation needed
            d *= 1.0 + P.get("trial_k", 0.25) * max(meta[3] - 1, 0)
        if tech in (S.SHORT_TRIAL, S.EITHER_WAY, S.WHAT_IF) and pm:
            # short case splits are cheap: scale by the cells the branches fill (1.0 at 10 cells)
            d *= (1.0 + math.log1p(max(meta[0], 0))) / (1.0 + math.log1p(10.0))
        hm = P.get("human_mode")
        if hm is not None and len(feat) > 5 and feat[5] is not None:
            bud = list(hm.get("budget", HUMAN_BUDGET)) + HUMAN_BUDGET[len(hm.get("budget", HUMAN_BUDGET)) :]
            kk = list(hm.get("k", HUMAN_K)) + HUMAN_K[len(hm.get("k", HUMAN_K)) :]
            e = 0.0
            for j, load in enumerate(feat[5][: len(HUMAN_BUDGET)]):
                over = load - bud[j]
                if over > 0.0:
                    e += kk[j] * over
            d *= math.exp(e)
        # no single move counts as harder than guessing: a solver facing it would
        # bifurcate instead (also guards structural extrapolation blow-ups)
        cap = P["B"].get(S.GUESS)
        if cap and tech != S.GUESS and d > cap:
            # soft cap: beyond guessing, difficulty keeps growing (logarithmically), so
            # computer-only techniques extrapolate instead of flattening; cap_tau -> 0 = hard cap
            tau = P.get("cap_tau", 1.0)
            pw = P.get("cap_pow") or 0.0  # > 0: power cap, steeper than log1p (1 = uncapped)
            d = cap + (d - cap) ** pw if pw > 0 else cap + tau * math.log1p((d - cap) / tau) if tau > 0 else cap
        return d


# ---------------------------------------------------------------- grading --


def _d_ref(P):
    return P["B"].get(S.HIDDEN_D, 1.0)


def guess_work(feat, P):
    """Expected work (in easy steps) of a Guess / Trial / ShortTrial step for the time model, or None (normal
    step, or params["guess_time_linear"] off = the published behaviour). Guess: meta[0] = expected refutation
    work x10 (wrong candidates' refutation steps, weighted 1/2 each); Trial / ShortTrial: meta[0] = cells the
    refuting branch fills."""
    if not P.get("guess_time_linear"):
        return None
    tech = feat[0]
    meta = feat[4] if len(feat) > 4 else None
    if tech not in (S.GUESS, S.TRIAL, S.SHORT_TRIAL) or not meta_priced(meta):
        return None
    return max(meta[0] / 10.0, 1.0) if tech == S.GUESS else float(max(meta[0], 1))


def predict_time(steps, puzzle, params):
    P = params
    total = P["t0"]
    sc = Scorer(P)
    dr = _d_ref(P)
    gwork = gfall = easy_sum = 0.0
    easy_n = 0
    easy_all = []
    for st in steps:
        tech = st.move.feat[0]
        if tech in S.NOTE_TECHS:
            total += P["t_mark"] * st.notes_written
            continue
        total += P["t_mark"] * (getattr(st, "notes_written", 0) or 0)  # params notes_lazy: marks written where used
        w = guess_work(st.move.feat, P)
        # work_time's step time here (alternatives priced at most the Hidden Single base)
        easy = None
        if w is not None or (P.get("guess_time_linear") and tech not in (S.GUESS, S.TRIAL, S.SHORT_TRIAL)):
            den = max(sum(math.exp(-P["beta"] * min(sc.difficulty(f, puzzle.D), dr)) for f in st.alts), 1e-300)
            easy = P["c"] * st.n_empty / den
        if w is not None:  # Guess / Trial: linear in the expected refutation work, each unit the solve's mean
            gwork += w  # easy-step time (a refutation branch is easy propagation steps)
            gfall += easy * w
        else:
            if easy is not None and tech not in (S.GUESS, S.TRIAL, S.SHORT_TRIAL):
                easy_sum += easy
                easy_n += 1
                easy_all.append(easy)
            denom = max(sum(math.exp(-P["beta"] * sc.difficulty(f, puzzle.D)) for f in st.alts), 1e-300)
            total += P["c"] * st.n_empty / denom
        if st.move.place:
            total += P["t_place"]
        total += P["t_erase"] * st.erasures
    if gwork > 0:  # params "guess_time_unit": "mean" (default) or "median" of the solve's easy-step times
        if not easy_n:
            total += gfall
        elif P.get("guess_time_unit") == "median":
            e = sorted(easy_all)
            total += gwork * (e[len(e) // 2] if len(e) % 2 else 0.5 * (e[len(e) // 2 - 1] + e[len(e) // 2]))
        else:
            total += gwork * easy_sum / easy_n
    return total


def work_time(steps, puzzle, params):
    """Tediousness as a time (sudoku.coach's idea): predict_time with every move priced as if it were
    easy (capped at the Hidden Single base price), so only the VOLUME of work remains -- scan area
    (empty cells), how many moves are available, writing / erasing notes. predicted time - work time
    = think time, the extra cost of hard steps. Decorrelated from difficulty by construction."""
    P = params
    sc = Scorer(P)
    d_ref = P["B"].get(S.HIDDEN_D, 1.0)
    # grid-size scaling of scanning (sudokuleader 4x4..25x25 + lisudoku): humans take
    # far longer on big grids than the 9x9-fitted model predicts -> scan term x (D/9)^gamma, rectangular boxes x e^k
    # (2x3, 3x4 boxes are slower to scan). 9x9 classics are unchanged by construction.
    rect = any(
        len({c // puzzle.D for c in g.cells}) != len({c % puzzle.D for c in g.cells})
        for g in getattr(puzzle, "groups", [])
        if g.kind == "box"
    )
    # composite boards (samurai, twins: more cells than one D x D grid): a solver scans one region at a time, so the
    # scan area per step is one D x D grid's share of the empty cells, not the whole board (else time grows quadratically)
    local = min(1.0, puzzle.D * puzzle.D / max(puzzle.N, 1))
    size_scan = (puzzle.D / 9.0) ** P.get("time_size_gamma", 2.79) * (
        math.exp(P.get("time_rect_k", 0.72)) if rect else 1.0
    )
    total = P["t0"]
    for st in steps:
        if st.move.feat[0] in S.NOTE_TECHS:
            total += P["t_mark"] * st.notes_written
            continue
        total += P["t_mark"] * (getattr(st, "notes_written", 0) or 0)  # params notes_lazy
        denom = max(sum(math.exp(-P["beta"] * min(sc.difficulty(f, puzzle.D), d_ref)) for f in st.alts), 1e-300)
        total += P["c"] * st.n_empty * local / denom * size_scan
        if st.move.place:
            total += P["t_place"]
        total += P["t_erase"] * st.erasures
    return total


VOLUME_REF = 881.3  # median work volume of a 9x9 classic (fed, 700 puzzles) -> time grade 5.0


def work_volume(steps, puzzle, params):
    """Length of the solve at constant difficulty: every step scans the empty cells of the grid the solver works in
    (one D x D grid's share on composite boards), scaled by how hard a grid of that size / box shape is to scan;
    move prices are left out (they are difficulty). The route length adds the most human-time information
    beyond difficulty and correlates only 0.26 with it on 9x9 classics."""
    P = params
    rect = any(
        len({c // puzzle.D for c in g.cells}) != len({c % puzzle.D for c in g.cells})
        for g in getattr(puzzle, "groups", [])
        if g.kind == "box"
    )
    local = min(1.0, puzzle.D * puzzle.D / max(puzzle.N, 1))
    size_scan = (puzzle.D / 9.0) ** P.get("time_size_gamma", 2.79) * (
        math.exp(P.get("time_rect_k", 0.72)) if rect else 1.0
    )
    d_ref = P["B"].get(S.HIDDEN_D, 1.0)
    unit = P["c"] * math.exp(P["beta"] * d_ref)
    return sum(unit * st.n_empty * local * size_scan for st in steps if st.move.feat[0] not in S.NOTE_TECHS)


def time_grade(steps, puzzle, params):
    """sudokuwiki-style log scale of the work volume: 5.0 = a typical 9x9 classic, +1 per doubling of the work."""
    v = work_volume(steps, puzzle, params)
    return round(5.0 + math.log2(max(v, 1e-9) / VOLUME_REF), 1) if v > 0 else None


def grade(steps, puzzle, params=None, solved=True):
    P = params or DEFAULT_PARAMS
    cap = P["B"].get(S.GUESS, float("inf"))
    ds = [
        st.move.d if (P.get("cap_tau", 1.0) > 0 or P.get("cap_pow")) else min(st.move.d, cap) for st in steps
    ]  # soft cap lives in d
    if not ds:
        return {"difficulty": 0.0, "time": P["t0"], "tediousness": 0.0}
    dmax = max(ds)
    tau = P["tau"]
    w = sum(math.exp((d - dmax) / tau) for d in ds)
    dens = w * P["ref_steps"] / max(len(ds), 1)
    difficulty = dmax + tau * math.log(max(dens, 1.0))
    t = predict_time(steps, puzzle, P)
    sc = Scorer(P)
    # tediousness (sudoku.coach idea, as a probability): chance the move you
    # find is THE move you needed -- 1.0 when only one move exists each step
    ted = []
    for st in steps:
        if st.move.feat[0] in S.NOTE_TECHS:
            continue
        ws = [math.exp(-P["beta"] * sc.difficulty(f, puzzle.D)) for f in st.alts]
        ted.append(max(ws) / sum(ws) if sum(ws) > 0 else 1.0)
    # techniques you HAD to know: the chosen technique at steps where no
    # cheaper technique type was available, plus TakeNotes if notes needed
    required = {}
    for st in steps:
        name = S.TECH_NAMES[st.move.feat[0]]
        techs_avail = {f[0] for f in st.alts}
        if len(techs_avail) == 1 or st.move.feat[0] in S.NOTE_TECHS:
            required[name] = max(required.get(name, 0), st.move.d)
    hardest = max(steps, key=lambda st: min(st.move.d, cap))
    return {
        "difficulty": difficulty,
        "max_step": dmax,
        "time": t,
        "work_time": (wt := work_time(steps, puzzle, P)),
        "think_time": max(t - wt, 0.0),
        "tediousness": sum(ted) / len(ted) if ted else 0.0,
        "notes_needed": any(st.move.feat[0] == S.TAKE_NOTES for st in steps),
        "snyder_needed": any(st.move.feat[0] == S.SNYDER_MARKS for st in steps),
        "required": dict(sorted(required.items(), key=lambda kv: kv[1])),
        "hardest": S.TECH_NAMES[hardest.move.feat[0]],
        "n_steps": len(steps),
        "solved": solved,
    }


def quality_metrics(steps, puzzle, params=None):
    """Puzzle-quality descriptors that fall out of the step trace for free."""
    P = params or DEFAULT_PARAMS
    sc = Scorer(P)
    real = [st for st in steps if st.move.feat[0] not in S.NOTE_TECHS]
    if not real:
        return {}
    cap = P["B"].get(S.GUESS, float("inf"))
    ds = [st.move.d if (P.get("cap_tau", 1.0) > 0 or P.get("cap_pow")) else min(st.move.d, cap) for st in real]
    n = len(ds)
    dmax = max(ds)
    mean = sum(ds) / n
    srt = sorted(ds)
    median = srt[n // 2]
    var = sum((d - mean) ** 2 for d in ds) / n
    tau = P["tau"]
    bottlenecks = sum(1 for d in ds if d >= dmax - 2 * tau)
    # peaks: local maxima clearly above their neighbours (difficulty "waves")
    peaks = sum(1 for i in range(1, n - 1) if ds[i] > ds[i - 1] + 0.5 and ds[i] > ds[i + 1] + 0.5)
    # forced stretches: steps where exactly one move existed
    forced = [len(st.alts) == 1 for st in real]
    longest, cur = 0, 0
    for f in forced:
        cur = cur + 1 if f else 0
        longest = max(longest, cur)
    alts = [len(st.alts) for st in real]
    hardest_at = ds.index(dmax) / max(n - 1, 1)
    first_half = sum(ds[: n // 2]) / max(n // 2, 1)
    second_half = sum(ds[n // 2 :]) / max(n - n // 2, 1)
    notes_idx = next((i for i, st in enumerate(steps) if st.move.feat[0] == S.TAKE_NOTES), None)
    placed_before_notes = sum(1 for st in steps[:notes_idx] if st.move.place) if notes_idx is not None else None
    total_empty = sum(1 for st in steps if st.move.place) or 1
    import math as _m
    from collections import Counter

    tc = Counter(S.TECH_NAMES[st.move.feat[0]] for st in real)
    ent = -sum((c / n) * _m.log2(c / n) for c in tc.values())
    # time breakdown
    search = write = notes_t = 0.0
    for st in steps:
        if st.move.feat[0] in S.NOTE_TECHS:
            notes_t += P["t_mark"] * st.notes_written
            continue
        denom = max(sum(_m.exp(-P["beta"] * sc.difficulty(f, puzzle.D)) for f in st.alts), 1e-300)
        c = P.get("c_notes", P["c"]) if st.mode == "notes" else P["c"]
        search += c * st.n_empty / denom
        write += P["t_place"] * (1 if st.move.place else 0)
        notes_t += P["t_erase"] * st.erasures + P["t_mark"] * (getattr(st, "notes_written", 0) or 0)
    # givens symmetry (180-degree rotation, the classic "published" convention)
    g = puzzle.givens
    coords = puzzle.coords
    if coords:
        rmax = max(r for r, _ in coords)
        cmax = max(c for _, c in coords)
        pos = {xy: i for i, xy in enumerate(coords)}
        sym_ok = sum(1 for c in g if pos.get((rmax - coords[c][0], cmax - coords[c][1])) in g)
        symmetry = sym_ok / max(len(g), 1)
    else:
        symmetry = 0.0
    return {
        "max_step": dmax,
        "mean_step": mean,
        "median_step": median,
        "spikiness": dmax / mean if mean else 0.0,  # one hard step in an easy solve -> high
        "step_sd": var**0.5,
        "bottlenecks": bottlenecks,  # near-max steps ("stuck points")
        "difficulty_peaks": peaks,
        "forced_steps_frac": sum(forced) / n,  # only one move available
        "longest_forced_run": longest,
        "mean_alternatives": sum(alts) / n,
        "min_alternatives": min(alts),
        "hardest_at": hardest_at,  # 0 = opening, 1 = endgame
        "back_loading": second_half - first_half,  # >0: harder late
        "direct_progress": (placed_before_notes / total_empty) if placed_before_notes is not None else 1.0,
        "n_techniques": len(tc),
        "technique_entropy": ent,
        "time_search": search,
        "time_writing": write,
        "time_notes": notes_t,
        "givens": len(g),
        "givens_symmetry": symmetry,
    }
