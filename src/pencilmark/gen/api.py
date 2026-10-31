"""generate(spec) -> {"puzzle", "card", "info"}: the public entry point of pencilmark.gen."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field, fields
from typing import Any

from .. import band_path as BP
from .. import export as E2
from .. import puzzle_json as PJ
from .. import solver as S
from . import elements as EL
from . import search as SR
from .board import BOXES, Board, grid_log2
from .checks import Checker, band_techs, code_techs, params

BANDS = list(E2.BANDS)  # "Very Easy" .. "Extreme"
CLASSIC_MIN_GIVENS = {4: 4, 6: 8, 9: 17}  # known minimum clue counts for a unique classic


class GenerationFailed(RuntimeError):
    """no puzzle met the spec within the time limit (or the spec is infeasible); str(e) says why."""

    def __init__(self, reason, stats=None):
        super().__init__(reason)
        self.reason, self.stats = reason, stats or {}


@dataclass
class Spec:
    """what to generate.

    size              board size (4, 6, 8, 9, 10, 12, 16; standard boxes)
    elements          {kind or class: N | [min, max] | "auto" | "full" | "min" | "partition"}: N = at least N needed elements
                      (0 / None / "auto" = allowed, not required); [min, max] = between min and max (max None = no cap;
                      [2, 2] = exactly 2). Classes count one colour / letter / parity of a kind: kropki_white, kropki_black,
                      x, v, odd, even ({"kropki_black": [2, 2], "kropki_white": "auto"}); {"kropki": "full"} = zero-given
                      full kropki (no dot = neither relation);
                      {"kropki": "min"} = zero-given minimal dot set; {"cage": "partition"} = killer tiled by cages, few
                      givens; {"cage": N} with max_givens=0 = killer with exactly N cages and no givens (CP-SAT)
    kinds             shorthand: every listed kind keeps >= 1 needed element (each-kind mode)
    target_band       "Very Easy" .. "Extreme" (or 0..6): the card's band must equal it
    target_difficulty [lo, hi] on the card's difficulty scale
    require           technique codes the card must contain (e.g. ["XWG"]); strict_require = listed as the code itself,
                      not only as an alternative chip
    symmetry          None | rot180 | rot90 | mirror | mirror_v | diagonal | antidiagonal (for givens)
    min_givens / max_givens   digging floor / upper bound on the result's givens
    max_elements      upper bound on the number of rule elements
    solver            "logic" (every step solvable by human logic within the band cap: unique by construction) or
                      "cpsat" (uniqueness only; min kropki); cage-count and full kropki always use CP-SAT
    seed, time_limit  determinism and the overall budget in seconds
    """

    size: int = 9
    elements: dict | None = None
    kinds: list | None = None
    target_band: Any = None
    target_difficulty: Any = None
    require: list = field(default_factory=list)
    strict_require: bool = False
    symmetry: str | None = None
    min_givens: int = 0
    max_givens: int | None = None
    max_elements: int | None = None
    solver: str = "logic"
    seed: int = 1
    time_limit: float = 120.0
    grade_seconds: float | None = 60.0

    @classmethod
    def from_any(cls, spec):
        if isinstance(spec, cls):
            return spec
        spec = dict(spec or {})
        known = {f.name for f in fields(cls)}
        bad = sorted(set(spec) - known)
        if bad:
            raise GenerationFailed(f"unknown spec field(s) {bad}; known: {sorted(known)}")
        return cls(**spec)


# ---------------------------------------------------------------- spec interpretation
def _band_index(b):
    if b is None:
        return None
    if isinstance(b, int):
        if 0 <= b < len(BANDS):
            return b
        raise ValueError(f"band index {b} out of range 0..{len(BANDS) - 1}")
    low = {x.lower(): i for i, x in enumerate(BANDS)}
    key = str(b).strip().lower().replace("_", " ")
    if key not in low:
        raise ValueError(f"unknown band {b!r} (known: {BANDS})")
    return low[key]


def _known_codes():
    """code -> band for every technique code the card can list."""
    out = {}
    for t in S.TECH_NAMES:
        code, b = E2.chip_of(t)
        if b is not None:
            out.setdefault(code, b)
    for code, _name, b in BP._X_CHAIN.values():
        out.setdefault(code, b)
    from .. import registry

    for code, c in registry.codes().items():  # a step named by its shape has the shape's band (a long X-Chain is
        if c.shape_band is not None:  # Very Hard although X-Chain is Hard); the route grades it so
            out[code] = c.shape_band
    return out


def _variant_codes():
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    return {E2.chip_of(rev[n])[0] for n in BP.VARIANT_ANY + BP.VARIANT_SUM if n in rev} - {"LOL", "IMH", "DGC", "RUL"}


def _plan(s):
    """(mode, kinds, seeds, value) from the spec's elements / kinds."""
    els = {}
    for k, v in (s.elements or {}).items():
        els[EL.norm_kind(k)] = v
    for k in s.kinds or []:
        els.setdefault(EL.norm_kind(k), 1)
    if not els:
        return "classic", [], {}, None
    if len(els) == 1:
        ((k, v),) = els.items()
        if isinstance(v, str):
            v = v.lower()
            if k == "kropki" and v in ("full", "min"):
                return f"kropki_{v}", [k], {}, None
            if k == "cage" and v == "partition":
                return "partition", [k], {}, None
            raise ValueError(
                f"element value {v!r} only means something for kropki ('full' / 'min') or cage ('partition')"
            )
        if k == "cage" and s.max_givens == 0 and isinstance(v, int) and v > 0:
            return "cage_count", [k], {}, v
    seeds, caps = {}, {}
    for k, v in els.items():
        if isinstance(v, str) and v.lower() == "auto":
            v = None
        if isinstance(v, str):
            raise ValueError(f"{k}: {v!r} can't be mixed with other kinds (use a count, [min, max] or 'auto')")
        if isinstance(v, (list, tuple)):
            lo, hi = v
            if hi is not None and (lo or 0) > hi:
                raise ValueError(f"{k}: minimum {lo} above maximum {hi}")
            seeds[k] = int(lo or 0)
            if hi is not None:
                caps[k] = hi
        else:
            seeds[k] = int(v or 0)
    return "dig", list(els), seeds, caps


def feasibility(spec):
    """fast checks before any search; returns a list of problems (empty = go). Includes an information budget: givens and
    elements together must be able to carry log2(#grids) bits, and classic clue counts can't go below known minimums."""
    try:
        s = Spec.from_any(spec)
    except GenerationFailed as e:
        return [str(e)]
    except TypeError as e:
        return [f"bad spec: {e}"]
    probs = []
    if s.size not in BOXES:
        return [f"size {s.size} not supported (supported: {sorted(BOXES)})"]
    b = Board(s.size)
    try:
        mode, kinds, seeds, value = _plan(s)
    except ValueError as e:
        return [str(e)]
    try:
        tb = _band_index(s.target_band)
    except ValueError as e:
        probs.append(str(e))
        tb = None
    if s.target_difficulty is not None:
        try:
            lo, hi = s.target_difficulty
            if lo > hi:
                probs.append(f"target_difficulty {s.target_difficulty}: low > high")
        except (TypeError, ValueError):
            probs.append(f"target_difficulty must be [low, high], got {s.target_difficulty!r}")
    if s.symmetry is not None:
        try:
            b.orbit(0, s.symmetry)
        except ValueError as e:
            probs.append(str(e))
        if mode in ("cage_count", "kropki_full", "kropki_min", "partition"):
            probs.append(f"symmetry applies to givens; mode {mode} has none to place")
    if mode in ("cage_count", "kropki_full") or (mode == "kropki_min" and s.solver == "cpsat"):
        from .. import cpsat_verify as V

        if not V.have_ortools():
            probs.append(f"mode {mode} needs the CP-SAT uniqueness oracle; {V.VERIFY_HINT}")
    if s.solver not in ("logic", "cpsat"):
        probs.append(f"solver must be 'logic' or 'cpsat', got {s.solver!r}")
    if s.time_limit is None or s.time_limit <= 0:
        probs.append("time_limit must be > 0")
    codes = _known_codes()
    vcodes = _variant_codes()
    for c in s.require or []:
        if c not in codes:
            probs.append(f"unknown technique code {c!r} (e.g. {', '.join(sorted(codes)[:12])}, ...)")
            continue
        if tb is not None and codes[c] > tb:
            probs.append(f"{c} is a {BANDS[codes[c]]} technique: a {BANDS[tb]} puzzle can't need it")
        if mode == "classic" and c in vcodes:
            probs.append(f"{c} is a variant technique: a classic puzzle can't contain it (add elements)")
    if s.max_givens is not None:
        if s.max_givens < s.min_givens:
            probs.append(f"max_givens {s.max_givens} < min_givens {s.min_givens}")
        if mode == "classic":
            floor = CLASSIC_MIN_GIVENS.get(s.size, s.size - 1)
            if s.max_givens < floor:
                probs.append(
                    f"a unique {s.size}x{s.size} classic needs at least {floor} givens (max_givens={s.max_givens})"
                )
    # information budget for element-only / element-bounded specs
    need = grid_log2(s.size)
    lg_c = lambda n_, k_: (math.lgamma(n_ + 1) - math.lgamma(k_ + 1) - math.lgamma(n_ - k_ + 1)) / math.log(2)
    gmax = s.max_givens if s.max_givens is not None else None
    if mode == "cage_count":
        if value > b.N // 2:
            probs.append(f"{value} cages can't tile {b.N} cells without 1-cell cages (max {b.N // 2})")
        if value < math.ceil(b.N / s.size):
            probs.append(
                f"{value} cages can't cover {b.N} cells with distinct digits (cage <= {s.size} cells; "
                f"need >= {math.ceil(b.N / s.size)})"
            )
        bits = value * EL.element_bits(b, "cage")
        if bits < need:
            probs.append(
                f"information budget: {value} cages carry <= {bits:.0f} bits, a {s.size}x{s.size} grid needs {need:.0f}"
            )
    elif (
        mode == "dig"
        and gmax is not None
        and (s.max_elements is not None or (kinds and all(k in value for k in kinds)))
    ):
        gbits = lg_c(b.N, min(gmax, b.N)) + gmax * math.log2(s.size) if gmax else 0.0
        if s.max_elements is not None:
            n_el = s.max_elements
            ebits = n_el * max(EL.element_bits(b, EL.base_kind(k)) for k in kinds)
        else:  # every element class has a maximum: the caps bound the elements
            n_el = sum(value.values())
            ebits = sum(m * EL.element_bits(b, EL.base_kind(k)) for k, m in value.items())
        if gbits + ebits < need:
            probs.append(
                f"information budget: {gmax} givens + {n_el} elements carry <= {gbits + ebits:.0f} bits, "
                f"a {s.size}x{s.size} grid needs {need:.0f} -- too few for a unique puzzle"
            )
        if s.max_elements is not None and s.max_elements < sum(seeds.values()):
            probs.append(f"max_elements {s.max_elements} < required element count {sum(seeds.values())}")
    if mode in ("kropki_full", "kropki_min", "cage_count") and s.min_givens:
        probs.append(f"mode {mode} has no givens (min_givens={s.min_givens})")
    return probs


# ---------------------------------------------------------------- generation
def _codes_in(card, strict):
    if strict:
        return {c["code"] for c in card["contains"] if not c.get("alternatives")}
    return {c["code"] for c in card["contains"]} | {x for c in card["contains"] for x in c.get("alternatives", [])}


def _check_card(card, tb, td, req, strict):
    """None if the card meets the targets, else the reason."""
    if card.get("band") == "Unknown" and (tb is not None or td is not None):
        return "band Unknown"
    bi = BANDS.index(card["band"]) if card.get("band") in BANDS else None
    if tb is not None and bi != tb:
        return "band too low" if bi is not None and bi < tb else "band too high"
    if td is not None:
        d = card.get("difficulty")
        if d is None:
            return "no difficulty"
        if d < td[0]:
            return "difficulty too low"
        if d > td[1]:
            return "difficulty too high"
    miss = [c for c in req if c not in _codes_in(card, strict)]
    if miss:
        return f"missing {'/'.join(miss)}"
    return None


def generate(spec, log=None):
    """generate one puzzle meeting a sudoku-spec request (docs/SPEC.md; a dict, JSON text or a path). Returns
    {"puzzle": sudoku-puzzle (with solution; meta.generated_from = the spec's fingerprint), "card": sudoku-grade card,
    "info": {...}}. Raises NotSupportedError for a part of the spec the generator does not run, GenerationFailed when no
    puzzle met it in time."""
    import json as _json
    from pathlib import Path

    from .. import spec_format as SF
    from ..api import to_export

    doc = spec
    if isinstance(spec, Path) or (isinstance(spec, str) and not spec.lstrip().startswith("{")):
        doc = _json.loads(Path(spec).read_text(encoding="utf-8"))
    elif isinstance(spec, str):
        doc = _json.loads(spec)
    if not isinstance(doc, dict) or doc.get("format") != "sudoku-spec":
        raise TypeError(
            'generate takes a "sudoku-spec" request (docs/SPEC.md), e.g. {"format": "sudoku-spec", '
            '"format_version": 1, "board": {"rows": 9, "cols": 9}, "digits": 9, "rules": [{"type": "box_grid", '
            '"origin": "r1c1", "box": [3, 3]}], "where": {"band": "Hard"}}'
        )
    r = _generate(SF.spec_to_gen(doc), log)
    meta = {k: v for k, v in (doc.get("meta") or {}).items() if k != SF.NS}
    meta["generated_from"] = SF.spec_fingerprint(doc)
    puzzle = to_export(r["puzzle"], meta=meta)
    card = r["card"]
    if doc.get("fields") is not None:  # the requested card fields (docs/SPEC.md 5)
        from ..api import rate

        card = rate(puzzle, fields=doc["fields"])
    return {"puzzle": puzzle, "card": card, "info": r["info"]}


def _generate(spec, log=None):
    """generate one puzzle meeting an internal Spec (or its dict). Returns {"puzzle": puzzle JSON (with solution),
    "card", "info"} or raises GenerationFailed with the reason."""
    s = Spec.from_any(spec)
    probs = feasibility(s)
    if probs:
        raise GenerationFailed("infeasible spec: " + "; ".join(probs))
    t0 = time.time()
    deadline = t0 + s.time_limit
    b = Board(s.size)
    rng = random.Random(s.seed)
    P = params()
    mode, kinds, seeds, value = _plan(s)
    tb = _band_index(s.target_band)
    td = tuple(s.target_difficulty) if s.target_difficulty is not None else None
    req = list(s.require or [])
    codes = _known_codes()

    # band cap of the construction; with a required technique at the cap, only that technique is allowed at the cap
    # (everything easier stays allowed), so the logic route has to go through it
    cap = tb if tb is not None else (max(codes[c] for c in req) if req else len(BANDS) - 1)
    top = [c for c in req if codes[c] == cap]
    if top and cap > 0:
        allowed = band_techs(P, cap - 1) | set().union(*(code_techs(P, c) for c in top))
        if not any(code_techs(P, c) for c in top):  # shape-only code (SKY, FRK...): no technique to single out
            allowed = band_techs(P, cap)
    else:
        allowed = band_techs(P, cap)
    chk = Checker(b, allowed=allowed, P=P)
    low = Checker(b, cap=cap - 1, P=P) if (tb is not None or top) and cap > 0 else None
    full = Checker(b, cap=len(BANDS) - 1, P=P)
    stats = {"attempts": 0, "rejected": {}}

    def reject(why):
        stats["rejected"][why] = stats["rejected"].get(why, 0) + 1

    def build(sol, givens, els):
        nk = {}
        for e in els:
            nk[e[0]] = nk.get(e[0], 0) + 1
        kinds_txt = ", ".join(f"{v} {k}" for k, v in sorted(nk.items()) if k != "notdots") or "classic"
        title = f"generated {s.size}x{s.size} {kinds_txt}, {len(givens)} givens"
        return EL.to_json(b, givens, els, sol, title=title)

    # candidates are screened without the alternatives search (band, difficulty and time don't depend on it) unless a
    # non-strict `require` can be met by an alternative; the result's card is then made in full
    # without `require` the technique list isn't needed at all: band / difficulty / time only
    screen_alts = bool(s.require) and not s.strict_require
    screen_fields = None if s.require else ["difficulty", "time", "band"]

    def grade(d, alternatives=screen_alts, fields=screen_fields):
        p = PJ.from_json(d)
        p.finalize()
        return E2.grade(p, P, with_steps=False, max_seconds=s.grade_seconds, alternatives=alternatives, fields=fields)

    while time.time() < deadline:
        stats["attempts"] += 1
        if mode in ("classic", "dig"):
            few = s.max_givens is not None and s.max_givens < CLASSIC_MIN_GIVENS.get(
                s.size, 0
            )  # elements must carry the puzzle
            dense = (
                [
                    k
                    for k in kinds
                    if mode == "dig"
                    and few
                    and (value or {}).get(k) is None
                    and EL.base_kind(k) in ("kropki", "xv", "parity")
                ]
                if stats["attempts"] % 2
                else []
            )
            r = SR.dig(
                b,
                kinds,
                rng,
                chk,
                min_givens=s.min_givens,
                seeds=seeds,
                max_els=s.max_elements if s.max_elements is not None else 10**6,
                symmetry=s.symmetry,
                caps=value if mode == "dig" else None,
                dense=dense,
            )
        elif mode == "partition":
            r = SR.partition(b, rng, chk, n_givens=s.min_givens)
        elif mode == "cage_count":
            r = SR.cage_count(b, value, rng, deadline=deadline)
        elif mode == "kropki_full":
            r = SR.full_kropki(b, rng)
        else:
            r = SR.min_kropki(b, rng, chk=chk if s.solver == "logic" else None)
        if r is None:
            reject("construction failed")
            continue
        sol, givens, els = r
        if s.max_givens is not None and len(givens) > s.max_givens:
            reject("too many givens")
            continue
        if s.max_elements is not None and len(els) > s.max_elements:
            reject("too many elements")
            continue
        short = [k for k, n in seeds.items() if sum(1 for e in els if EL.in_class(e, k)) < n]
        if short:
            reject(f"kind pruned: {'/'.join(short)}")
            continue
        over = [
            k
            for k, m in ((value or {}) if mode == "dig" else {}).items()
            if m is not None and sum(1 for e in els if EL.in_class(e, k)) > m
        ]
        if over:
            reject(f"too many: {'/'.join(over)}")
            continue
        if low is not None and mode not in ("cage_count", "kropki_full") and low.ok(givens, els):
            got = None
            # too easy: every other attempt, re-dig with every technique and pull back to the cap (search.pull); measured
            # 2026-10-24 on 9x9 classics: ~1 in 4-6 hits for band targets, never for a required technique, ~2 s each
            if mode in ("classic", "dig") and cap < 5 and not top and stats["attempts"] % 2 == 0:
                rf = SR.dig(
                    b,
                    kinds,
                    rng,
                    full,
                    sol=sol,
                    min_givens=s.min_givens,
                    seeds=seeds,
                    max_els=s.max_elements if s.max_elements is not None else 10**6,
                    symmetry=s.symmetry,
                    caps=value if mode == "dig" else None,
                )
                if rf is not None:
                    got = SR.pull(b, sol, rf[1], rf[2], chk, low, rng, symmetry=s.symmetry, max_givens=s.max_givens)
            if got is None:
                reject("band too low (logic pre-check)")
                continue
            givens, els = got
            if any(sum(1 for e in els if EL.in_class(e, k)) < n for k, n in seeds.items()):
                reject("kind pruned")
                continue
        d = build(sol, givens, els)
        card = grade(d)
        why = _check_card(card, tb, td, req, s.strict_require)
        if why == "difficulty too high" and mode in ("classic", "dig"):
            got = _add_back(b, s, sol, givens, els, td, tb, req, grade, build, rng, deadline)
            if got:
                d, card, givens = got
                why = None
        if why:
            reject(why)
            if log:
                log(f"attempt {stats['attempts']}: {why} ({card.get('band')} {card.get('difficulty')})")
            continue
        verified = _verify(d, sol)
        if verified is False:
            reject("not unique (CP-SAT)")
            continue
        if not screen_alts or screen_fields is not None:
            card = grade(d, alternatives=True, fields=None)
        info = {
            "mode": mode,
            "givens": len(givens),
            "elements": {
                k: sum(1 for e in els if EL.element_class(e) == k) for k in sorted({EL.element_class(e) for e in els})
            },
            "attempts": stats["attempts"],
            "seconds": round(time.time() - t0, 1),
            "rejected": stats["rejected"],
            "unique_verified": verified,
            "seed": s.seed,
        }
        return {"puzzle": d, "card": card, "info": info}
    rej = ", ".join(f"{k} x{v}" for k, v in sorted(stats["rejected"].items(), key=lambda x: -x[1])) or "none"
    raise GenerationFailed(
        f"no puzzle met the spec in {s.time_limit:.0f} s ({stats['attempts']} attempts; rejected: {rej})", stats
    )


def _add_back(b, s, sol, givens, els, td, tb, req, grade, build, rng, deadline):
    """card too hard for target_difficulty: put dug givens back (random order, whole symmetry orbits), bisecting on how
    many; adding givens keeps the puzzle unique and within the cap. Returns (puzzle, card, givens) or None."""
    orbits, seen = [], set()
    for i in sorted((c for c in range(b.N) if c not in givens), key=lambda _: rng.random()):
        if i in seen:
            continue
        o = b.orbit(i, s.symmetry)
        seen.update(o)
        orbits.append(o)
    lo_m, hi_m = 0, len(orbits)
    for _ in range(8):
        if lo_m >= hi_m or time.time() > deadline:
            break
        m = (lo_m + hi_m + 1) // 2
        g2 = dict(givens)
        for o in orbits[:m]:
            g2.update({c: sol[c] for c in o})
        if s.max_givens is not None and len(g2) > s.max_givens:
            hi_m = m - 1
            continue
        d = build(sol, g2, els)
        card = grade(d)
        why = _check_card(card, tb, td, req, s.strict_require)
        if why is None:
            return d, card, g2
        if why == "difficulty too high":
            lo_m = m
        else:
            hi_m = m - 1
    return None


def _verify(d, sol, time_limit=30.0):
    """independent uniqueness check (CP-SAT): True / False, or None if undecided in time."""
    from .. import cpsat_verify as V

    p = PJ.from_json(d)
    p.finalize()
    sols = V.solutions(p, limit=2, time_limit=time_limit)
    if sols is None:
        return None
    return len(sols) == 1 and list(sols[0]) == list(sol)


def is_unique(puzzle, time_limit=30.0):
    """CP-SAT: does the puzzle JSON have exactly one solution? (None = undecided in time / unsupported rule)."""
    from .. import cpsat_verify as V

    p = PJ.from_json(puzzle)
    p.finalize()
    sols = V.solutions(p, limit=2, time_limit=time_limit)
    return None if sols is None else len(sols) == 1


def uniquify(puzzle, seed=0, time_limit=30.0, minimize=True):
    """make a single-grid puzzle JSON unique by adding givens from its solution (the "solution" field, else the first
    CP-SAT solution); any rule set CP-SAT can express. Each CP-SAT counterexample is cached; the cell the most cached
    counterexamples disagree on becomes the next given. With minimize, added givens that turn out unnecessary are
    dropped again. Returns a new puzzle JSON; raises GenerationFailed if there is no solution or CP-SAT can't decide."""
    from .. import cpsat_verify as V

    d = dict(puzzle)
    if d.get("layout") or d.get("shape"):
        raise GenerationFailed("uniquify supports single-grid puzzles only")
    p = PJ.from_json(d)
    p.finalize()
    if d.get("solution"):
        sol = [PJ._val(ch) for ch in d["solution"]]
    else:
        sols = V.solutions(p, limit=1, time_limit=time_limit)
        if not sols:
            raise GenerationFailed("puzzle has no solution (or CP-SAT timed out)")
        sol = list(sols[0])
    pool = []

    def js(givens):
        return dict(d, numbers="".join(PJ._sym(givens[c]) if c in givens else "." for c in range(p.N)))

    def unique(givens):
        if any(all(alt[c] == v for c, v in givens.items()) for alt in pool):
            return False
        q = PJ.from_json(js(givens))
        q.finalize()
        sols = V.solutions(q, limit=2, time_limit=time_limit)
        if sols is None:
            raise GenerationFailed(
                "uniqueness could not be decided" + ("" if V.have_ortools() else "; " + V.VERIFY_HINT)
            )
        if not sols:
            raise GenerationFailed("puzzle has no solution")
        alts = [list(x) for x in sols if list(x) != sol]
        if alts:
            pool.insert(0, alts[0])
        return not alts

    rng = random.Random(seed)
    givens, added = dict(p.givens), []
    while not unique(givens):
        votes = {}
        for alt in pool:
            if all(alt[c] == v for c, v in givens.items()):
                for c in range(p.N):
                    if c not in givens and alt[c] != sol[c]:
                        votes[c] = votes.get(c, 0) + 1
        best = max(votes.values())
        c = rng.choice(sorted(k for k, v in votes.items() if v == best))
        givens[c] = sol[c]
        added.append(c)
    if minimize:
        for c in added[:-1]:
            trial = {k: v for k, v in givens.items() if k != c}
            if unique(trial):
                givens = trial
    out = js(givens)
    out["solution"] = "".join(PJ._sym(v) for v in sol)
    return out
