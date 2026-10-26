"""C++ backend for pencilmark.solver (sources and build script in csolver/).

Drop-in fast paths with behavioural parity to the Python reference:

    from pencilmark import cbackend as CB
    steps, solved = CB.solve(puzzle, params)            # ~ Solver(puzzle, Scorer(params)).solve()
    raw = CB.featurize_raw(rows, params, threads=16)
    sols = CB.brute_solve(puzzle, limit=2)               # ~ pencilmark.solver.brute_solve

Steps are real pencilmark.solver.Step / Move objects, so pencilmark.scoring.grade(),
predict_time() and quality_metrics() work unchanged. Build first with
csolver/build.sh.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from . import _csolver as _C  # noqa: E402  (the compiled C++ engine, sources in csrc/)

# optional arguments of the loaded build (older builds lack the newer ones): checked once at import
_SOLVE_DOC = (getattr(_C.solve, "__doc__", "") or "")
_SOLVE_HAS = {k: (k + ":") in _SOLVE_DOC or (k + " :") in _SOLVE_DOC for k in ("explain", "colours")}
_HAS_ROLLOUTS = hasattr(_C, "rollouts")
_HAS_INFO = hasattr(_C, "puzzle_info")
_HAS_RAW = hasattr(_C, "make_puzzle_raw")  # featurize builds each state's puzzle inside the workers

from . import model as M  # noqa: E402
from . import solver as S  # noqa: E402
from .model import parse_grid  # noqa: E402
from .scoring import Scorer  # noqa: E402

_NM_NONE, _NM_GROUP, _NM_LOCK, _NM_INNIE, _NM_OUTIE, _NM_NARY = range(6)

# techniques without a Python reference implementation (C++ only); pass as
# `disabled` to reproduce the frozen Python solver exactly
NEW_TECHS = frozenset(S.NEW_TECHS)
CTYPES = ("sum", "arrow", "equal_sum", "set", "table", "sandwich", "xsum", "skyscraper", "leftovers", "count",
          "line", "between", "counting_circles", "first_seen", "digit_set", "distinct_count", "contains")
# forcing chains: level (0 static / 1 dynamic / 2 nested), options, unit (0 cell / 1 unit),
# surviving branches, propagation steps over all branches, contradicting branches
_FORCING_KEYS = ("level", "options", "unit", "survivors", "steps", "contradictions")
_COMBO_KEYS = ("ctype", "constraint", "combos", "set_unique", "sum", "distinct", "n_vars", "complete")
_DESC_KEYS = ("log branches", "log depth", "search", "uniqueness", "counting", "contradiction", "held", "coverage")
XMETA_KEYS = {
    S.SUM_COMBO: _COMBO_KEYS, S.ARROW_COMBO: _COMBO_KEYS, S.SET_COMBO: _COMBO_KEYS,
    S.EQSUM_COMBO: _COMBO_KEYS, S.TABLE_COMBO: _COMBO_KEYS,
    # mode 0: digit in every combination, confined to one group -> removed from the group
    # mode 1: a house's candidates for `digit` all inside the scope -> combinations must use it
    S.SANDWICH_COMBO: _COMBO_KEYS, S.XSUM_COMBO: _COMBO_KEYS, S.SKYLINE_COMBO: _COMBO_KEYS,
    S.LOL_COMBO: _COMBO_KEYS, S.COUNT_COMBO: _COMBO_KEYS,
    # direct mental layer: reasons = bitmask (1 relation arc, 2 inequality bound, 4 line, 8 mental subset);
    # depth = inference rounds; line_* = the most distant informing line; subset = mental subset size;
    # inferences = number of mental exclusions used; hidden = hidden-single form
    S.LINE_D: ("reasons", "depth", "line_kind", "line_len", "line_dist", "line_informing", "transitive",
               "subset", "inferences", "hidden"),
    S.MENTAL_D: ("reasons", "depth", "line_kind", "line_len", "line_dist", "line_informing", "transitive",
                 "subset", "inferences", "hidden"),
    S.SHORT_TRIAL: ("rounds", "placements"),
    S.EITHER_WAY: ("placements_a", "placements_b", "same_cell_choice", "no_notes"),
    S.LINE_CLASS: ("line_kind", "constraint", "line_len", "classes", "n_elims"),
    S.DIGIT_COUNT: ("units", "base_cells", "n_elims", "digit"),
    S.EQUAL_DIGITS: ("cell_a", "cell_b", "house", "candidates"),
    S.LINE_SCAN: ("line_kind", "constraint", "window", "cells"),
    S.LINE_RANGE: ("line_kind", "constraint", "line_len", "cells_changed", "informing", "transitive_depth", "combos"),
    S.UNIQUE_RECT: ("type", "x", "y", "extra_cells", "n_elims"),
    S.BUG_PLUS1: ("unsolved",),
    S.ALS_XZ: ("n_als", "size_a", "size_b", "n_rcc", "n_elims"),
    S.ALS_XYWING: ("n_als", "size_a", "size_b", "size_c", "n_elims"),
    S.DEATH_BLOSSOM: ("n_als", "n_cells", "stem_cands", "n_elims"),
    S.COMBO_LOCK: ("ctype", "constraint", "combos", "mode", "digit", "group", "n_cells", "cage_group"),
    S.NARY_D: ("ctype", "constraint", "n_vars"),
    S.RULE_INTERSECT: ("cells", "n_elims", "rules", "nodes"),
    S.SUM_ALGEBRA: ("houses", "pieces", "n_elims", "rounds"),
    **({S.BAND_LOGIC: ("lines", "boxes", "rules", "n_elims", "cells", "level", "cases")} if hasattr(S, "BAND_LOGIC") else {}),
    **({S.FIREWORKS: ("cell_x", "cell_a", "cell_b", "digit_mask", "n_elims", "region")} if hasattr(S, "FIREWORKS") else {}),
    **({S.HUMAN_CASE: ("cases", "rounds", "placed", "refutation", "options", "house")} if hasattr(S, "HUMAN_CASE") else {}),
    **({S.COMBO_POS: ("cage", "house", "digit_mask", "max_in_cage", "need_outside", "fillings")} if hasattr(S, "COMBO_POS") else {}),
    **({S.CLIQUE_HOUSE: ("size", "digit_mask", "n_elims", "placement")} if hasattr(S, "CLIQUE_HOUSE") else {}),
    **({S.LINE_SETS: ("house", "lines", "options", "n_elims")} if hasattr(S, "LINE_SETS") else {}),
    **({S.LINE_CLUES: ("house", "clues", "fillings", "n_elims")} if hasattr(S, "LINE_CLUES") else {}),
    **({S.WEIGHTED_SUMS: ("facts", "cells", "max_weight", "n_elims", "total")} if hasattr(S, "WEIGHTED_SUMS") else {}),
    S.INNIE_X: ("house", "outie", "n_cells", "combos", "n_cages", "distinct", "complete"),
    S.MEDUSA: ("rule", "nodes", "digits", "n_elims", "false_color"),
    # SumBound: allowed range [lo, hi] of the target, triangular bound used, positions, rule type
    S.SUM_BOUND: ("lo", "hi", "triangular", "positions", "ctype"),
    # ClassCount: kind (0 parity, 1 thirds, 2 sum parity), class mask, placed, forced cells, others
    S.CLASS_COUNT: ("kind", "class_mask", "placed", "forced", "others"),
    S.DOMINO: ("dominoes", "digit_or_mask", "cell_a", "cell_b", "fillings"),
    # seed: 0 house argument only, 1 equality rule / case split, 2 human colouring (consistent with the
    # solution), 3 human colouring without a solution to check against (soft hypothesis)
    S.COLOUR_ALGEBRA: ("cells", "digits", "n_elims", "seed", "class_kinds"),
    S.N_WING: ("size", "z", "z_cells", "n_elims"),
    S.SUE_DE_COQ: ("n_inter", "n_line", "n_box", "digit_mask", "n_elims"),
    S.APE: ("cell_a", "cell_b", "n_witness", "n_elims"),
    S.CHUTE_RP: ("cell_a", "cell_b", "absent", "eliminated", "n_elims"),
    S.POM: ("digit", "templates", "n_elims"),
    S.GURTH: ("symmetry", "n_elims"),
    S.NISHIO: ("digit", "rounds", "placements", "empty_house"),
    S.FORCING: _FORCING_KEYS, S.DYN_FORCING: _FORCING_KEYS, S.NESTED_FORCING: _FORCING_KEYS,
    S.MULTI_COLOR: ("digit", "cells", "n_elims"),
    # Guess (priced as the expected human cost of guessing): candidates, mean / max refutation work of
    # the wrong candidates, how many survive basic propagation (deep bifurcations), expected work x10
    S.GUESS: ("k", "mean_refutation", "max_refutation", "deep", "expected_work_x10"),
    S.WHAT_IF: _FORCING_KEYS, S.MENTAL_NOTES: ("via_technique", "via_eliminations", "hidden"),
    S.FINNED_FISH: ("size", "fins", "sashimi", "kind", "n_elims", "digit", "n_base_cells"),
    S.JELLYFISH: ("size", "fins", "sashimi", "kind", "n_elims", "digit", "n_base_cells"),
}
# chains: links, strong links by source (bivalue cell, bilocal digit in a
# group, constraint must-contain, pair relation), weak links by source (same
# cell, peer cells, pair relation), max hop (Chebyshev distance between
# consecutive cells), number of digits
_CHAIN_KEYS = ("links", "strong_bivalue", "strong_bilocal", "strong_constraint", "strong_relation",
               "weak_cell", "weak_house", "weak_relation", "max_hop", "n_digits")
for _t in (S.X_CHAIN, S.XY_CHAIN, S.AIC_CHAIN, S.NICE_LOOP, S.MENTAL_CHAIN, S.REMOTE_PAIRS, S.EMPTY_RECT):
    XMETA_KEYS[_t] = _CHAIN_KEYS
XMETA_KEYS[S.ALS_AIC] = _CHAIN_KEYS[:5] + ("n_als",) + _CHAIN_KEYS[6:]
# sudokuwiki-style codes for chain special cases
CHAIN_CODES = {1: "SKY", 2: "2SK", 3: "TUR", 4: "XCH", 5: "XYC", 6: "RMP", 7: "WWG", 8: "AIC", 9: "DNL",
               3001: "UR1", 3002: "UR2", 3003: "UR3", 3004: "UR4", 3005: "HUR", 3006: "BUG",
               3101: "AXZ", 3102: "AXZ2", 3103: "AXY", 3104: "DBL", 3105: "ALS",
               3201: "IMH", 3301: "SND", 3302: "XSM", 3303: "SKL", 3304: "LOL", 3305: "SET", 3306: "PHI", 3307: "set theory", 3308: "Phistomefel variant", 3320: "digit set", 3330: "rule and house together", 3331: "two rules together", 3332: "two houses with their dots", 3333: "three rules together", 3341: "sum algebra (house)", 3342: "sum algebra (two houses)", 3343: "sum algebra (three houses)", 3354: "house with its rules", 3355: "line and box with their rules", 3356: "band with its rules", 5201: "Snyder hidden pair", 5401: "fireworks", 5501: "case refutation", 5502: "cell case analysis", 5503: "house case analysis", 3910: "cage combination positions", 3920: "clique house", 3930: "renban digit sets in a house", 3940: "outside clues together", 3950: "weighted sums", 3951: "weighted sums (one cell left)", 5202: "Snyder X-wing", 5203: "Snyder hidden triple",
               10: "GXC", 11: "GAIC", 12: "ER", 3007: "UR5", 3008: "AR1", 3009: "XUR1", 3010: "BUG+2", 3011: "AR2", 3401: "cell forcing", 3402: "unit forcing", 3411: "dynamic cell forcing",
               3412: "dynamic unit forcing", 3431: "Nishio", 3441: "what if (cell)", 3442: "what if (house)",
               3451: "notes in the head", 3421: "nested cell forcing", 3422: "nested unit forcing",
               3501: "medusa trap", 3502: "medusa wrap (cell)", 3503: "medusa wrap (unit)",
               3504: "medusa wrap (emptied cell)", 3505: "medusa",
               3601: "secret", 3602: "rule of 45", 3610: "cage/unit overlap", 3611: "captured candidates",
               3605: "set theory (arrows / little killers)", 3612: "innie region must contain", 3613: "captured by an innie region", 3603: "secret (outie, cage splitting)", 3604: "rule of 45 (outie, cage splitting)",
               3701: "min/max bound", 3702: "triangular bound", 3703: "arrow min/max bound",
               3704: "arrow triangular bound", 3705: "renban span", 3801: "odd/even count", 3802: "sum parity",
               3803: "low/middle/high count", 3804: "rule of parity", 3901: "domino must contain",
               3902: "domino pair lock", 3903: "kropki black chain", 3904: "middle squeeze", 3506: "colour algebra", 3507: "colour must fit every house", 3508: "colour resolved", 3509: "coloured like a solved cell", 3510: "colour class (odd/even/low/high)", 3520: "multi-colouring", 3511: "colour bounds (order / min-max)", 3512: "label break-in (abstract digits)", 3513: "colour disambiguation", 3514: "colour sum", 3515: "colour arithmetic", 4604: "WXYZ-Wing", 4605: "VWXYZ-Wing", 4606: "6-Y-Wing", 4607: "7-Y-Wing", 4608: "8-Y-Wing",
               4609: "9-Y-Wing",
               4701: "Sue de Coq", 4801: "APE", 4901: "chute remote pairs", 5001: "pattern overlay",
               5101: "Gurth rot180", 5102: "Gurth diagonal", 5103: "Gurth anti-diagonal", 5104: "Gurth rot90"}
_FISH_SIZE = {2: "X-Wing", 3: "Swordfish", 4: "Jellyfish"}


def code_name(code):
    """Move.code (int from C++) -> short pattern code / fish name."""
    if not code:
        return None
    if 4000 <= code < 4200:  # line rule: kind + flavour
        kind, sub = divmod(code - 4000, 10)
        name = M.LINE_KINDS[kind] if kind < len(M.LINE_KINDS) else f"line{kind}"
        return name + {0: "", 1: " bounds", 2: " no-5", 3: " adjacent", 4: " transitive",
                       5: " classes", 6: " scan"}.get(sub, f" {sub}")
    if code == 4200:
        return "relation arc"
    if code == 4300:
        return "inequality chain"
    if code == 4408:
        return "mental subset chain"
    if 6000 <= code < 7000:
        return "named table rule"
    if 4500 <= code < 4600:
        t = code - 4500
        return ("cage/sum" if t == 0 else CTYPES[t] if t < len(CTYPES) else f"rule{t}") + " in the head"
    if 4400 <= code < 4500:
        return f"mental subset {code - 4400}"
    if code in CHAIN_CODES:
        return CHAIN_CODES[code]
    if 1000 <= code < 3000:
        n, kind, fin = (code // 100) % 10, (code // 10) % 10, code % 10
        if kind > 2 or fin > 2:
            return f"code {code}"
        return " ".join(x for x in (("", "Finned", "Sashimi")[fin], ("", "Franken", "Mutant")[kind],
                                    _FISH_SIZE.get(n, f"fish{n}")) if x)
    return CHAIN_CODES.get(code, f"code {code}")


class CMove(S.Move):
    """pencilmark.solver.Move plus structured metadata of the C++-only
    techniques: xmeta (dict, see XMETA_KEYS), family, code."""
    __slots__ = ("xmeta", "family", "code", "explain")


def to_cpuzzle(p):
    """Finalized pencilmark.model.Puzzle -> C++ puzzle (structure only; givens are
    passed per solve). Relation tables are taken from p.rel_ex, so any
    relation kind (including ones registered at runtime) works."""
    return _C.make_puzzle(*_cpuzzle_args(p))


def _cpuzzle_args(p):
    """make_puzzle / make_puzzle_raw arguments of a pencilmark.model.Puzzle."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    groups = [(tuple(g.cells), bool(g.complete), g.total, g.name, g.kind) for g in p.groups]
    rels = []
    for rel in p.relations:
        kind, a, b = rel[0], rel[1], rel[2]
        if kind == "neq":
            rels.append((a, b, True, None, None))
        else:
            rels.append((a, b, False, list(p.rel_ex[a][b]), list(p.rel_ex[b][a])))
    cons = []
    for c in getattr(p, "constraints", ()):
        d = {k: v for k, v in c.items() if not k.startswith("_")}
        if d.get("type") == "line" and d.get("kind") not in M.PAIRWISE_LINE_KINDS:
            d = {"type": "line", "kind": d["kind"], "cells": [], "skip": True}  # carried by its n-ary part
        elif d.get("type") == "clone":  # compiled into 'eq' relations; keep the index
            d = {"type": "line", "kind": "palindrome", "cells": [], "skip": True}
        cons.append(d)
    extra = detect_lines(p)
    p._cextra = [f"{d['kind']} line (detected)" for d in extra]
    return (p.D, [tuple(xy) for xy in p.coords], groups, list(p.domains), rels, cons + extra)


_AUTO_KINDS = {"lt": "thermo", "le": "slow_thermo", "parity": "parity"}


def detect_lines(p):
    """Line structure hidden in pair relations (translators emit thermos,
    whispers, kropki dots as pair tables): chains of >= 3 cells become
    {"type":"line"} constraints for the line layer (the pair tables stay)."""
    explicit = {tuple(c["cells"]) for c in getattr(p, "constraints", ()) if c.get("type") == "line"}
    groups = defaultdict(list)
    for rel in p.relations:
        kind, a, b, args = rel[0], rel[1], rel[2], tuple(rel[3:])
        if kind in _AUTO_KINDS:
            groups[(_AUTO_KINDS[kind], True)].append((a, b))
        elif kind == "diffge" and args:
            groups[("whisper" if args[0] >= 5 else "dutch_whisper", False)].append((a, b))
        elif (kind == "diff" and args == (1,)) or (kind == "ratio" and args == (2,)):
            groups[("kropki_chain", False)].append((a, b))
    out = []
    for (kind, directed), edges in sorted(groups.items()):
        succ, pred, nb = defaultdict(set), defaultdict(set), defaultdict(set)
        for a, b in edges:
            if a == b:
                continue
            succ[a].add(b)
            pred[b].add(a)
            nb[a].add(b)
            nb[b].add(a)
        paths = []
        if directed:  # maximal directed paths source -> sink (thermos, branching ones per branch)
            for s0 in sorted(c for c in succ if not pred[c]):
                stack = [[s0]]
                while stack and len(paths) < 400:
                    path = stack.pop()
                    nxt = sorted(succ[path[-1]] - set(path))
                    if not nxt:
                        paths.append(path)
                    for q in reversed(nxt):
                        stack.append(path + [q])
        else:  # undirected: split at branch points / ends
            term = {c for c in nb if len(nb[c]) != 2}
            seen = set()
            for t in sorted(term):
                for q in sorted(nb[t]):
                    if (t, q) in seen:
                        continue
                    path = [t, q]
                    while path[-1] not in term:
                        nxt = [x for x in nb[path[-1]] if x != path[-2]]
                        if not nxt or nxt[0] == path[0]:
                            break
                        path.append(nxt[0])
                    seen.add((path[-1], path[-2]))
                    seen.add((t, q))
                    paths.append(path)
        for path in paths:
            if len(path) >= 3 and tuple(path) not in explicit and tuple(path[::-1]) not in explicit:
                out.append({"type": "line", "kind": kind, "cells": list(path)})
    return out


def _name(p, nk, na, nb):
    if nk == _NM_GROUP:
        return _gname(p, na)
    if nk == _NM_LOCK:
        return f"{_gname(p, na)}->{_gname(p, nb)}"
    if nk == _NM_INNIE:
        return f"innie {_gname(p, na)}"
    if nk == _NM_OUTIE:
        return f"outie {_gname(p, na)}"
    if nk == _NM_NARY:
        if na >= 0:
            nc = len(getattr(p, "constraints", ()))
            if na < nc:
                c = p.constraints[na]
                return f"{c.get('kind', c['type']) if c['type'] == 'line' else c['type']}#{na}"
            ex = getattr(p, "_cextra", [])
            if na < nc + len(ex):
                return ex[na - nc]
            return f"leftovers#{na - nc - len(ex)}"
        return f"cage {p.groups[nb].name}" if 0 <= nb < len(p.groups) else ""
    return ""


def _colour_list(colours, N):
    """{cell: colour} (any hashable colour labels) -> per-cell colour ids (-1 none) or None."""
    if not colours:
        return None
    ids = {}
    out = [-1] * N
    for c, col in colours.items():
        c = int(c)
        if 0 <= c < N and col is not None:
            out[c] = ids.setdefault(col, len(ids))
    return out


def solve(puzzle, params=None, disabled=(), solution=None, allow_direct=True, max_steps=5000, cpuzzle=None,
          assume_unique=True, all_tiers=False, explain=False, colour_seeds=None, cand=None):
    """Run the C++ solver. Returns (steps, solved) with steps as
    pencilmark.solver.Step objects (alts = feature tuples, move.d set).
    cand = per-cell candidate mask of a mid-solve state (as state_moves(cand=)): pass the original puzzle + a
    cpuzzle built once from it, with puzzle.givens = the filled cells."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    sc = Scorer(params)
    cp = cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle)
    sol = [int(x) for x in solution] if solution is not None else None
    cp_p = no_guess_params(sc.p, params, disabled)
    disabled = [int(t) for t in _extra_disabled(set(disabled) | search_disabled(params))]  # env override, e.g. "58,59,60"
    args = [cp, list(puzzle.givens.items()), cp_p, disabled, sol, bool(allow_direct), int(max_steps),
            bool(assume_unique), bool(all_tiers)]
    if _SOLVE_HAS["explain"]:
        args.append(bool(explain))
        if _SOLVE_HAS["colours"]:
            args.append(_colour_list(colour_seeds, puzzle.N))
    if cand is not None:
        if "cand" not in (_C.solve.__doc__ or ""):
            raise RuntimeError("solve(cand=) needs a csolver build with the candidate mask")
        raw, solved = _C.solve(*args, cand=[int(x) for x in cand])
    else:
        raw, solved = _C.solve(*args)
    info = _C.puzzle_info(cp, disabled) if explain and _HAS_INFO else None
    steps = []
    for row in raw:
        alts, chosen, place, el, nm, d, mode, n_empty, er, nw, xm, code, pats, exs = row[:14]
        n_cands = row[14] if len(row) > 14 else None  # dev74+: candidates before the step
        m = CMove.__new__(CMove)
        m.feat = alts[chosen]
        m.place = place
        m.elim = el
        m.name = _name(puzzle, *nm)
        m.d = d
        tech = m.feat[0]
        keys = XMETA_KEYS.get(tech)
        m.xmeta = dict(zip(keys, xm)) if keys else None
        if len(xm) >= 16:  # structural descriptors (canonical mode): mirrored for explain / debug
            m.xmeta = dict(m.xmeta or {}, **{"desc_" + k.replace(" ", "_"): v for k, v in zip(_DESC_KEYS, xm[10:18])})
        if m.xmeta and "ctype" in m.xmeta:
            m.xmeta["ctype"] = CTYPES[m.xmeta["ctype"]]
        lk_ = m.xmeta.get("line_kind", -1) if m.xmeta else -1
        if lk_ is not None and 0 <= lk_ < len(M.LINE_KINDS):
            m.xmeta["line_kind"] = M.LINE_KINDS[lk_]
        elif lk_ is not None and lk_ >= 100:
            m.xmeta["line_kind"] = CTYPES[lk_ - 100] if lk_ - 100 < len(CTYPES) else lk_
        m.family = S.TECH_NAMES[tech]
        m.code = code_name(code)
        if 6000 <= code < 7000:  # a named table rule (pencilmark.model.add_predicate)
            cons = getattr(puzzle, "constraints", ())
            nm_ = cons[code - 6000].get("name") if code - 6000 < len(cons) else None
            m.code = f"{nm_ or 'table'} rule" + (" in the head" if tech in (S.LINE_D, S.MENTAL_D) else "")
        m.explain = _explain(puzzle, m, nm, pats, exs, info) if explain else None
        steps.append(S.Step(m, alts, "notes" if mode else "direct", n_empty, er, nw, n_cands))
    return steps, solved


def required_techniques(puzzle, scorer):
    """pencilmark.solver.required_techniques on the C++ solver (same algorithm)."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    cp = to_cpuzzle(puzzle)
    B = scorer.p["B"]
    techs = sorted((t for t in S.TECH_NAMES if t != S.GUESS), key=lambda t: (t == S.TRIAL, B.get(t, 99)))
    for k in range(1, len(techs) + 1):
        allowed = set(techs[:k])
        steps, solved = solve(puzzle, scorer.p, disabled=set(S.TECH_NAMES) - allowed, cpuzzle=cp)
        if solved:
            break
    else:
        return None, []
    disabled = set(S.TECH_NAMES) - allowed
    used = sorted({st.move.feat[0] for st in steps}, key=lambda t: -B.get(t, 0))
    for t in used:
        if t == techs[k - 1]:
            continue
        st2, solved2 = solve(puzzle, scorer.p, disabled=disabled | {t}, cpuzzle=cp)
        if solved2:
            disabled |= {t}
            steps = st2
    return sorted({st.move.feat[0] for st in steps}, key=lambda t: B.get(t, 0)), steps


# ------------------------------------------------------------ explanations --
_LINK = {0: "weak", 1: "strong (bivalue cell)", 2: "strong (only two places in a group)",
         3: "strong (constraint must contain the digit)", 4: "strong (pair relation)",
         5: "strong (inside an almost locked set)", 6: "equivalence (equality relation)"}
_TRIAL_VIEW = {0: "candidates", 1: "no notes (mental view)", 2: "candidates, singles only",
               10: "candidates, basic propagation", 11: "candidates, dynamic (techniques in the branches)",
               12: "candidates, nested (forcing chains in the branches)",
               13: "candidates, light logic (what if)", 14: "no notes, light logic (what if)"}
_EVENTS = {1: "naked single", 2: "hidden single", 3: "relation", 4: "rule",
           5: "empty cell", 6: "house missing digit", 7: "rule unsatisfiable", 8: "conflicting singles",
           9: "technique"}


_STEP_EVENTS = ("naked single", "hidden single", "relation", "rule", "technique")


def _rc(p, c):
    r, k = p.coords[c]
    return f"r{r + 1}c{k + 1}"


def _digits(mask):
    return [d for d in range(1, 33) if mask >> (d - 1) & 1]


def _group(p, gi, info=None):
    if gi is None or gi < 0:
        return None
    if gi < len(p.groups):
        g = p.groups[gi]
        d = {"name": g.name, "kind": g.kind, "cells": list(g.cells)}
        if g.total is not None:
            d["sum"] = g.total
        return d
    for idx, name, cells in (info or {}).get("implied_groups", ()):
        if idx == gi:
            return {"name": name, "kind": "implied house", "cells": list(cells)}
    return {"name": f"implied{gi - len(p.groups) + 1}", "kind": "implied house", "cells": []}


def _gname(p, gi, info=None):
    g = _group(p, gi, info)
    return g["name"] if g else None


def _constraint(p, idx, info=None):
    cons = getattr(p, "constraints", [])
    if 0 <= idx < len(cons):
        return {k: v for k, v in cons[idx].items() if not k.startswith("_")}
    ex = getattr(p, "_cextra", [])
    if 0 <= idx - len(cons) < len(ex):
        return {"type": "line (detected from pair relations)", "description": ex[idx - len(cons)]}
    for lo in (info or {}).get("leftovers", ()):
        if lo["index"] == idx:
            return {"type": "leftovers", "kind": lo["kind"], "index": idx,
                    "a": list(lo["a"]), "b": list(lo["b"]),
                    "a_rc": [_rc(p, c) for c in lo["a"]], "b_rc": [_rc(p, c) for c in lo["b"]],
                    "lines": [_group(p, g, info) for g in lo["lines"]],
                    "regions": [_group(p, g, info) for g in lo["regions"]]}
    return {"type": "leftovers (derived set equivalence)", "index": idx}


def _cref(p, ref, info=None):
    """constraint ref from the engine: >= 0 constraint index, <= -2 cage group -2-ref"""
    if ref is None or ref == -1:
        return None
    if ref >= 0:
        return _constraint(p, ref, info)
    return _group(p, -2 - ref, info)


def _cref_name(p, ref, info=None):
    c = _cref(p, ref, info)
    if c is None:
        return None
    if "name" in c:
        return f"cage {c['name']}" if c.get("sum") is not None else c["name"]
    if c.get("type") == "line":
        return f"{c.get('kind', 'line')} line"
    return c.get("description") or c.get("kind") or c.get("type")


def _via(p, a, b, digit_a, digit_b, info=None):
    """which unit / rule links two chain nodes"""
    if a == b:
        return "same cell"
    for gi in p.groups_of[a]:
        if b in p.groups[gi].cells:
            return p.groups[gi].name
    for _, name, cells in (info or {}).get("implied_groups", ()):
        if a in cells and b in cells:
            return name
    if b in p.neq[a]:
        return "neq relation"
    if b in p.nonconsec[a]:
        return "relation " + _relkinds(p, a, b)
    return None


def _relkinds(p, a, b):
    kinds = sorted({r[0] for r in p.relations if {r[1], r[2]} == {a, b}})
    return "/".join(kinds) if kinds else "pair"


def _reason(p, c, v, kind, a, b, info):
    r = {"cell": c, "rc": _rc(p, c), "digit": v}
    if kind == 0:
        r.update(kind="already in group", group=_gname(p, a, info), by=_rc(p, b) if b >= 0 else None)
    elif kind == 1:
        r.update(kind="neq cell", by=_rc(p, a))
    elif kind == 2:
        r.update(kind="relation", by=_rc(p, a), by_digit=b, relation=_relkinds(p, c, a))
    elif kind == 3:
        r.update(kind="domain")
    elif kind == 4:
        g = _group(p, a, info)
        r.update(kind="cage sum", group=g["name"] if g else None, sum=g.get("sum") if g else None)
    elif kind == 5:
        if b >= 0:
            r.update(kind="pointing", house=_gname(p, a, info), group=_gname(p, b, info))
        else:
            r.update(kind="relation lock" if b == -2 else "neq lock", house=_gname(p, a, info))
    elif kind == 6:
        r.update(kind="relation arc", by=_rc(p, a) if a >= 0 else None, depth=b)
    elif kind == 7:
        r.update(kind="inequality bound", by=_rc(p, a) if a >= 0 else None, depth=b)
    elif kind == 8:
        r.update(kind="line / rule", constraint=_cref_name(p, a, info), depth=b)
    elif kind == 9:
        r.update(kind="mental subset", house=_gname(p, a, info) if a >= 0 else None, size=b)
    elif kind == 11:
        r.update(kind="mental pointing", house=_gname(p, a, info) if a >= 0 else None, size=b)
    else:
        r.update(kind=str(kind))
    return r


def _event(p, t, rnd, c, dm, src, info):
    e = {"event": _EVENTS.get(t, str(t)), "round": rnd}
    if c >= 0:
        e.update(cell=c, rc=_rc(p, c))
    if t in (1, 2, 8):
        e["digit"] = dm
        if t == 2:
            e["house"] = _gname(p, src, info)
    elif t in (3, 4):
        e["digits"] = _digits(dm)
        if t == 3:
            e.update(by=_rc(p, src), relation=_relkinds(p, c, src))
        else:
            e["constraint"] = _cref_name(p, src, info)
    elif t == 6:
        e.update(digit=dm, house=_gname(p, src, info))
    elif t == 7:
        e["constraint"] = _cref_name(p, src, info)
        if dm:
            e["digit"] = dm
    elif t == 9:
        e.update(technique=S.TECH_NAMES.get(dm, str(dm)), eliminations=src)
    return e


def _records(exs):
    i = 0
    while i + 1 < len(exs):
        tag, n = exs[i], exs[i + 1]
        yield tag, list(exs[i + 2: i + 2 + n])
        i += 2 + n


def _explain(p, m, nm, pats, exs, info=None):
    """Structured justification of a move (schema in csolver/README.md)."""
    nk, na, nb = nm
    tech = m.feat[0]
    out = {
        "technique": S.TECH_NAMES[tech], "code": m.code, "difficulty": m.d,
        "placement": None, "eliminations": [], "digits": [], "targets": [],
        "pattern_cells": [int(c) for c in pats], "base": {"units": [], "cells": []},
        "cover": {"units": [], "cells": []}, "constraints": [], "chain": [], "als": [],
        "xmeta": m.xmeta,
    }
    digits = set()
    if m.place:
        c, v = m.place
        out["placement"] = {"cell": c, "rc": _rc(p, c), "digit": v}
        out["targets"] = [c]
        digits.add(v)
    for c, v in m.elim:
        out["eliminations"].append({"cell": c, "rc": _rc(p, c), "digit": v})
        digits.add(v)
    if not m.place:
        out["targets"] = sorted({c for c, _ in m.elim})
    # units by name kind: group (single / subset / pointing house), lock (base -> cover)
    if nk in (_NM_GROUP, _NM_INNIE, _NM_OUTIE) and na >= 0:
        out["base"]["units"].append(_group(p, na, info))
    if nk == _NM_LOCK:
        out["base"]["units"].append(_group(p, na, info))
        out["cover"]["units"].append(_group(p, nb, info))
    if nk == _NM_NARY:
        if na >= 0:
            out["constraints"].append(_constraint(p, na, info))
        if nb >= 0:
            out["constraints"].append(_group(p, nb, info))
    recs = list(_records(exs))
    als, gnodes = {}, {}
    for tag, data in recs:  # grouped chain nodes: id -> cells
        if tag == 14 and len(data) >= 3:
            gnodes[data[0]] = data[2:]
    for tag, data in recs:  # ALS first: chain nodes refer to them
        if tag == 4 and len(data) >= 2:
            aid = -1 - data[0]
            if aid in als:
                continue
            als[aid] = {"id": aid, "digits": _digits(data[1]), "cells": data[2:],
                        "rc": [_rc(p, c) for c in data[2:]]}
            out["als"].append(als[aid])
    for tag, data in recs:
        n = len(data)
        if tag == 1:
            out["base"]["units"] += [_group(p, g, info) for g in data]
        elif tag == 2:
            out["cover"]["units"] += [_group(p, g, info) for g in data]
        elif tag == 3 and n == 1:
            out["restricted_common"] = _digits(data[0])
        elif tag == 5 and n % 4 == 0:
            prev = None
            for k in range(0, n, 4):
                c, v, t, src = data[k: k + 4]
                node = {"digit": v}
                if c >= 0:
                    node.update(cell=c, rc=_rc(p, c))
                elif c <= -1000000:  # grouped node: the digit in one of 2-3 cells of a box-line segment
                    g = gnodes.get(c, [])
                    node.update(group=g, group_rc=[_rc(p, x) for x in g])
                else:
                    a = als.get(-1 - c, {})
                    node.update(als=-1 - c, als_cells=a.get("cells", []), als_rc=a.get("rc", []),
                                als_digits=a.get("digits", []))
                if prev is not None:
                    node["link_in"] = _LINK.get(t, str(t))
                    via = None
                    if t == 2 and src >= 0:
                        via = _gname(p, src, info)
                    elif t == 3:
                        via = _cref_name(p, src, info)
                        node["via_constraint"] = _cref(p, src, info)
                    elif t == 5:
                        via = f"almost locked set {-1 - c if c < 0 else src}"
                    elif t == 6:
                        via = "equality relation"
                    elif "group" in node or "group" in prev:
                        via = "sees every cell of the group"
                    elif c < 0 or prev.get("cell") is None:
                        via = "sees every ALS cell holding the digit"
                    if via is None and c >= 0 and prev.get("cell") is not None:
                        via = _via(p, prev["cell"], c, prev["digit"], v, info)
                    node["via"] = via
                out["chain"].append(node)
                prev = node
                digits.add(v)
        elif tag == 6 and n % 5 == 0:
            out["reasons"] = [_reason(p, *data[k: k + 5], info) for k in range(0, n, 5)]
        elif tag == 7 and n >= 2:
            view, nopt = data[0], data[1]
            out["trial"] = {"view": _TRIAL_VIEW.get(view, str(view)),
                            "options": [{"cell": data[2 + 2 * i], "rc": _rc(p, data[2 + 2 * i]),
                                         "digit": data[3 + 2 * i]} for i in range(nopt)],
                            "branches": []}
        elif tag == 8 and n >= 3:
            c, v, rnd = data[:3]
            evs = [_event(p, *data[k: k + 5], info) for k in range(3, n - 4, 5)]
            br = {"assume": {"cell": c, "rc": _rc(p, c), "digit": v}, "contradiction_round": rnd or None,
                  "steps": [e for e in evs if e["event"] in _STEP_EVENTS],
                  "contradiction": next((e for e in evs if e["event"] not in _STEP_EVENTS), None)}
            out.setdefault("trial", {"view": None, "options": [], "branches": []})["branches"].append(br)
        elif tag == 9 and n >= 6 and data[0] == 0:  # multi-digit (3D Medusa): entries cell*32+digit
            _, wrap, side, ca, cb, n0 = data[:6]
            cols = [data[6: 6 + n0], data[6 + n0:]]
            out["coloring"] = {"digit": None, "type": "wrap" if wrap else "trap",
                               "colors": [[{"cell": e // 32, "rc": _rc(p, e // 32), "digit": e % 32} for e in col]
                                          for col in cols],
                               "eliminated_color": side if wrap else None,
                               "clash": [ca, cb] if wrap else None}
        elif tag == 9 and n >= 6:
            v, wrap, side, ca, cb, n0 = data[:6]
            cols = [data[6: 6 + n0], data[6 + n0:]]
            out["coloring"] = {"digit": v, "type": "wrap" if wrap else "trap", "colors": cols,
                               "rc": [[_rc(p, c) for c in col] for col in cols],
                               "eliminated_color": side if wrap else None,
                               "clash": [ca, cb] if wrap else None}
        elif tag == 10 and n >= 4:
            total, outie, nh = data[:3]
            houses = data[3: 3 + nh]
            ncg = data[3 + nh]
            cages = data[4 + nh: 4 + nh + ncg]
            cells = data[4 + nh + ncg:]
            out["region"] = {"type": "outie" if outie else "innie", "total": total, "cells": cells,
                             "rc": [_rc(p, c) for c in cells], "houses": [_group(p, g, info) for g in houses],
                             "cages": [_group(p, g, info) for g in cages]}
            hu = [_group(p, g, info) for g in houses]
            names = {h["name"] for h in hu}
            out["base"]["units"] = hu + [u for u in out["base"]["units"] if u and u["name"] not in names]
            out["cover"]["units"] += [_group(p, g, info) for g in cages]
        elif tag == 11 and n >= 1:
            if tech == S.ALS_XYWING and n == 4:
                a = als.get(-1 - data[0], {})
                out["hinge"] = {"als": -1 - data[0], "cells": a.get("cells", []), "rc": a.get("rc", []),
                                "x": data[1], "y": data[2], "z": _digits(data[3])}
            elif tech == S.DEATH_BLOSSOM:
                out["stem"] = {"cell": data[0], "rc": _rc(p, data[0]),
                               "petals": [{"digit": data[k], "als": -1 - data[k + 1],
                                           "cells": als.get(-1 - data[k + 1], {}).get("cells", [])}
                                          for k in range(1, n - 1, 2)]}
        elif tag == 12:
            rules = [_constraint(p, i, info) for i in data]
            out["base"]["rules"] = rules
            out["constraints"] += rules
        elif tag == 15 and n >= 2:
            out["dominoes"] = [{"cells": [data[k], data[k + 1]], "rc": [_rc(p, data[k]), _rc(p, data[k + 1])],
                                "relation": _relkinds(p, data[k], data[k + 1])} for k in range(0, n - 1, 2)]
        elif tag == 13 and n >= 2:
            mode, v = data[:2]
            hs = [_group(p, g, info) for g in data[2:]]
            out["lock"] = {"mode": "must contain" if mode == 0 else "house forces the digit into the rule",
                           "digit": v, "houses": hs}
            out["cover" if mode == 0 else "base"]["units"] += hs
    for side in ("base", "cover"):
        cells = set()
        for u in out[side]["units"]:
            if u:
                cells.update(u["cells"])
        out[side]["cells"] = sorted(cells)
    if nk == _NM_NONE and m.place and not out["base"]["units"]:  # naked single: the cell's houses
        c = m.place[0]
        out["cover"]["units"] = [_group(p, gi, info) for gi in p.groups_of[c] if p.groups[gi].complete]
        out["cover"]["cells"] = sorted({x for u in out["cover"]["units"] for x in u["cells"]})
    out["digits"] = sorted(digits)
    return out


def rollouts(puzzle, params=None, n=200, temperature=1.0, seed=1, focus=True, choice=None, threads=16,
             disabled=(), solution=None, all_families=False, cpuzzle=None, max_steps=5000, assume_unique=False):
    """Stochastic, human-like solve paths for distribution grading. At each step a move is sampled with
    P(m) ∝ exp((-d(m) + attract[technique] + eta·log(1+effect) + focus·g) / temperature)
    (focus: log distance / same digit / same box / same house as the previous placement). choice: one
    population dict of data/choice_fit.pkl ({"attract": {technique name: a}, "eta", "focus": {...}}) or
    None (difficulty race only). all_families=True races every family of the phase (slower); default:
    the solver's tier gating. assume_unique (default False): allow uniqueness techniques -- only for a
    puzzle proven unique (pencilmark.metrics.grade_puzzle_checked). Returns n dicts: time (seconds,
    scoring.predict_time model), difficulty
    (soft bottleneck, scoring.grade), hardest (technique name), notes (bool), steps, solved."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    sc = Scorer(params)
    cp = cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle)
    sol = [int(x) for x in solution] if solution is not None else None
    if sol is None:  # one brute-force solve up front, so Guess steps never search again
        b = brute_solve(puzzle, limit=1, cpuzzle=cp)
        sol = list(b[0]) if b else None
    attract = [0.0] * 128
    eta, gf = 0.0, [0.0] * 4
    if choice:
        code = {v: k for k, v in S.TECH_NAMES.items()}
        for k, v in (choice.get("attract") or {}).items():
            t = code.get(k, k if isinstance(k, int) else None)
            if t is not None and 0 <= t < 128:
                attract[t] = float(v)
        eta = float(choice.get("eta") or 0.0)
        f = choice.get("focus") or {}
        gf = [float(f.get(k, 0.0)) for k in ("log_dist_last", "same_digit_last", "same_box_last", "near_last")]
    rargs = [cp, list(puzzle.givens.items()), sc.p, [int(t) for t in _extra_disabled(disabled)], sol,
             int(n), float(temperature), int(seed), int(threads), bool(focus), bool(all_families),
             attract, eta, gf, int(max_steps)]
    if "assume_unique" in (getattr(_C.rollouts, "__doc__", "") or ""):
        rargs.append(bool(assume_unique))
    raw = _C.rollouts(*rargs)
    return [{"time": t, "difficulty": d, "hardest": S.TECH_NAMES.get(h, str(h)) if h >= 0 else None,
             "notes": bool(nt), "steps": k, "solved": bool(ok)} for t, d, h, nt, k, ok in raw]


def solve_stats(puzzle, params=None, disabled=(), solution=None, assume_unique=False, cpuzzle=None, allow_direct=True):
    """Per-strategy profile of one default solve: {strategy: (ms, calls, hits)} plus "_total_ms", "_steps".
    Strategy names: notes-tier strategies (singles, combination, locked, chains3-5, forcing, ...) and
    direct stages ("d:singles", "d:line", "d:mental", ...); hits = calls that produced a move."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    sc = Scorer(params)
    cp = cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle)
    sol = [int(x) for x in solution] if solution is not None else None
    return dict(_C.solve_stats(cp, list(puzzle.givens.items()), sc.p, [int(t) for t in _extra_disabled(disabled)], sol,
                               bool(assume_unique), bool(allow_direct)))


def state_moves(puzzle, params=None, all_tiers=True, assume_unique=False, limit_per_tech=0, disabled=(),
                solution=None, cpuzzle=None, written=None, details=False, cand=None):
    """Every move available at ONE state (puzzle.givens = filled cells; puzzle.domains = the marks / allowed
    digits per cell), across all technique families (direct and notes; tiers not gated -- all_tiers is
    accepted for clarity, the enumeration is always ungated). Returns a list of dicts sorted by price:
    tech (code), name, code (pattern code name or None), place ((cell, digit) or None),
    elim [(cell, digit), ...], d (the move's priced difficulty, Scorer.difficulty incl. covers and the
    soft cap). limit_per_tech keeps the cheapest n moves per technique (0 = all). assume_unique: allow
    uniqueness techniques (proven-unique puzzles only). solution: optional, used by Guess only.
    dev75+: written = per-cell bitmask of the candidates written down in this state (a replay's marks; sets the
    held / coverage descriptors; None = by technique: direct techniques use no notes, the others full notes);
    details=True adds meta (the move's meta tuple incl. descriptors), desc ({name: value}), xmeta, scan (raw
    count of patterns of the move's kind at this state, behind desc 'search') and pattern (cells).
    cand = per-cell candidate bitmask of a mid-solve state, applied after the givens: pass the ORIGINAL puzzle (and a
    cpuzzle built once from it) instead of rewriting puzzle.domains -- fast (no rebuild) and the puzzle's own domains
    stay what pattern detection expects."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    sc = Scorer(params)
    cp = cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle)
    sol = [int(x) for x in solution] if solution is not None else None
    args = [cp, list(puzzle.givens.items()), sc.p, [int(t) for t in _extra_disabled(disabled)], sol,
            bool(assume_unique), int(limit_per_tech)]
    if cand is not None:        # mid-solve candidates as a mask; cpuzzle keeps the puzzle's own domains (build it once)
        if "cand" not in (_C.state_moves.__doc__ or ""):
            raise RuntimeError("state_moves(cand=) needs a csolver build with the candidate mask")
        raw = _C.state_moves(*args, None if written is None else [int(x) for x in written], bool(details),
                             [int(x) for x in cand])
    elif written is not None or details:
        if "details" not in (_C.state_moves.__doc__ or ""):
            raise RuntimeError("state_moves(written=, details=) needs a dev75+ csolver build")
        raw = _C.state_moves(*args, None if written is None else [int(x) for x in written], bool(details))
    else:
        raw = _C.state_moves(*args)
    out = []
    for r in raw:
        t, code, pl, el, d = r[:5]
        m = {"tech": t, "name": S.TECH_NAMES.get(t, str(t)), "code": code_name(code), "place": pl, "elim": list(el), "d": d}
        if len(r) > 5:
            meta, xm, scan, pat = r[5:9]
            m["meta"] = meta
            m["desc"] = dict(zip(_DESC_KEYS, meta[10:18])) if meta is not None and len(meta) >= 18 else None
            keys = XMETA_KEYS.get(t)
            m["xmeta"] = dict(zip(keys, xm)) if keys else None
            m["scan"] = scan
            m["pattern"] = list(pat)
        out.append(m)
    out.sort(key=lambda m: m["d"])
    return out


ROLL_X_NAMES = None  # filled lazily: META_NAMES + DESC_NAMES + ["log scan"] (the 19 columns of mv_x)


def roll_to_placement(puzzle, params=None, written=None, k=20, temperature=1.0, seed=1, max_moves=40, phase="auto",
                      lists="all", rate_w=None, disabled=(), threads=16, cpuzzle=None):
    """dev83+: K rollouts of the human-mode race from ONE state (puzzle.givens = filled cells, puzzle.domains = the
    candidate view) to the next placement. Each step enumerates every move (as state_moves), picks one by softmax
    over -d / temperature, or over rate_w . x / temperature when rate_w (19 weights over mv_x, + an optional
    intercept) is given, and applies it; TakeNotes is a move in the direct phase. written = per-cell bitmask of the
    marks on the board (sets held / coverage; eliminations erase them; an eliminated unwritten candidate counts in
    s_held_mental). phase: "direct" / "notes" / "auto" (notes if any mark is written). Returns numpy arrays:
    s_* per rollout step (rollout, k, state, row = chosen move row, n_empty, n_cands, held_mental, hash), r_* per
    rollout (n_moves, placement), st_* per visited state (deduplicated; hash, row0, n, phase, listed),
    mv_* per move row (tech, code, place_cell / place_digit, n_elims, d, x = 19 features: ROLL_X_NAMES).
    lists="first" marks only the start state's rows as listed (all rows are returned either way)."""
    global ROLL_X_NAMES
    from .scoring import META_NAMES, DESC_NAMES
    ROLL_X_NAMES = list(META_NAMES) + list(DESC_NAMES) + ["log scan"]
    if not hasattr(_C, "roll_to_placement"):
        raise RuntimeError("roll_to_placement needs a dev83+ csolver build")
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    sc = Scorer(params)
    cp = cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle)
    ph = {"direct": 0, "notes": 1, "auto": -1}[phase] if isinstance(phase, str) else int(phase)
    return _C.roll_to_placement(cp, list(puzzle.givens.items()), sc.p, [int(t) for t in _extra_disabled(disabled)],
                                int(k), float(temperature), int(seed), int(max_moves), ph,
                                None if written is None else [int(x) for x in written],
                                None if rate_w is None else [float(x) for x in rate_w], lists == "all", int(threads))


class BruteResult(list):
    """brute_solve result: the solutions found (a list, as before) plus .complete: False when the
    node limit stopped the search before a verdict (then [] does NOT mean "no solution", and
    one solution does not mean "unique")."""
    complete = True


def brute_solve(puzzle, limit=2, start=None, node_limit=2_000_000, cpuzzle=None):
    """pencilmark.solver.brute_solve equivalent; start = (vals, cand) or None. Returns a list of
    solutions (BruteResult: check .complete -- False = node limit hit, verdict unknown)."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    cp = cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle)
    st = None if start is None else (list(start[0]), list(start[1]))
    try:
        sols, complete = _C.brute_solve(cp, list(puzzle.givens.items()), int(limit), int(node_limit), st, True)
    except TypeError:  # older build without the status flag
        sols, complete = _C.brute_solve(cp, list(puzzle.givens.items()), int(limit), int(node_limit), st), True
    out = BruteResult(sols)
    out.complete = bool(complete)
    return out


def _spec(row):
    """a feature-table row as a plain spec for the C++ builder."""
    sol = row.get("solution")
    sol = [int(x) for x in sol] if isinstance(sol, str) and len(sol) == 81 else None
    if row["tab"] == "killer":
        cages = [(int(t), [int(c) for c in cells]) for t, cells in json.loads(row["cages_json"])]
        return (2, [], cages, sol)
    givens = list(parse_grid(row["grid"], 9).items())
    return (1 if row["tab"] == "nonc" else 0, givens, [], sol)


def featurize_puzzles(puzzles, params, threads=16, rich=False, solutions=None, disabled=(), as_lists=False,
                      max_steps=5000, last_moves=None, all_tiers=False, colour_seeds=None, assume_unique=False):
    """featurize_raw for arbitrary finalized pencilmark.model.Puzzle objects (any
    size D, groups, relations, n-ary constraints and lines). solutions: optional
    list (per puzzle) of solution lists used by Guess; same keys as featurize_raw.
    max_steps=1 emits only the first step's alternatives (human-choice fitting).
    Both featurize functions also return m_place / m_value per move (-1 / 0 when
    the move only eliminates). last_moves: optional per-puzzle (cell, digit) or
    (cell, digit, run_length) or None -- the move before the first step (e.g. the
    human's previous placement), seeding the rich "previous placement" features.
    all_tiers=True: at every state the moves of EVERY technique family (direct, line /
    mental, all notes tiers) are emitted, not only the solver's current tier; the
    chosen move and the path are unchanged. colour_seeds: optional per-puzzle {cell: colour} (human
    colouring; a colour = "same digit" hypothesis seeding ColourAlgebra, used where consistent with the
    solution, soft without one). assume_unique (default False; bool or per-puzzle list): allow uniqueness
    techniques only for puzzles proven unique (pencilmark.metrics.grade_puzzle_checked). params["human_mode"] = {"budget", "k"}
    switches the solver to human mode (all families of a phase compete, loads priced)."""
    sc = Scorer(params)
    specs = []
    for i, p in enumerate(puzzles):
        if not hasattr(p, "groups_of"):
            p.finalize()
        sol = solutions[i] if solutions is not None else None
        sol = [int(x) for x in sol] if sol is not None and len(sol) == p.N else None
        lm = last_moves[i] if last_moves is not None else None
        lm = tuple(int(x) for x in lm) if lm is not None and all(x is not None for x in lm[:2]) else None
        cs = _colour_list(colour_seeds[i], p.N) if colour_seeds is not None else None
        au = assume_unique[i] if isinstance(assume_unique, (list, tuple)) else assume_unique
        # newer builds: the C++ puzzle is built (and freed) per state inside the worker threads -- holding
        # every finalized puzzle at once was the transient memory peak of large featurize calls
        cp = _C.make_puzzle_raw(*_cpuzzle_args(p)) if _HAS_RAW else to_cpuzzle(p)
        specs.append(("praw" if _HAS_RAW else "cpuzzle", cp, list(p.givens.items()), sol, int(max_steps), lm,
                      bool(all_tiers), cs, bool(au)))
    out = _C.featurize(specs, sc.p, int(threads), [int(t) for t in _extra_disabled(disabled)], bool(rich))
    if as_lists:
        out = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in out.items()}
    return out


def computer_search():
    """Pure computer search: unbounded trial, forcing chains / nets (basic, dynamic, nested), Nishio nets, pattern
    overlay. Humans don't solve this way (CTC hosts: 0 'bifurcate' at 119 engine guess points)."""
    return {S.TRIAL, S.FORCING, S.DYN_FORCING, S.NESTED_FORCING, S.NISHIO, S.POM}


def search_disabled(params):
    """params['search']: 'human' -> no computer search; bounded human case work stays (ShortTrial = contradiction within
    4 rounds, i.e. a short Bowman's Bingo; WhatIf, EitherWay, MentalChain, case analysis). 'computer' / absent -> all.
    params['disabled_techniques']: extra technique ids to switch off."""
    p = params or {}
    out = set(p.get("disabled_techniques") or ())
    if p.get("search") == "human":
        # forcing chains / nets / nested, Nishio and pattern overlay are borderline-computer HUMAN logic
        # (band Extreme); Unknown is for guessing only, so human mode switches off unbounded trial alone
        out |= {S.TRIAL} if p.get("r6_extreme", True) else computer_search()
        if not p.get("allow_guess", False):
            out.add(S.GUESS)        # guessing off (default): the stuck fallback proves instead (no_guess_params)
    return out


def no_guess_params(sc_p, params, disabled=()):
    """Guessing is off by default. Human mode without params['allow_guess']: where a step would guess,
    the solver refutes one candidate by full search instead (Trial and error, band Extreme), so every unique puzzle gets a
    band. allow_guess=True: the solver guesses there and the card says Unknown.
    A caller that switches TRIAL off explicitly (a singles-only batch, a one-technique probe) stops where it is stuck."""
    p = params or {}
    if p.get("search") == "human" and not p.get("allow_guess", False) and S.TRIAL not in set(disabled):
        return dict(sc_p, exhaust_fallback=1)
    return sc_p


def _extra_disabled(disabled):
    """CSOLVER_EXTRA_DISABLED="62,63" adds techniques to every disabled set"""
    if os.environ.get("CSOLVER_EXTRA_DISABLED"):
        return set(disabled) | {int(x) for x in os.environ["CSOLVER_EXTRA_DISABLED"].split(",") if x}
    return disabled


def featurize_raw(rows, params, threads=16, as_lists=False, disabled=(), rich=False):
    """Feature table computed by C++
    worker threads. Values are numpy arrays (np.array of the Python lists
    gives identical arrays); as_lists=True converts to plain lists.
    rich=True adds m_rich (one row per candidate move, same order as m_step),
    s_rich (one row per step) and their column names rich_names / step_names
    (feature columns)."""
    sc = Scorer(params)
    out = _C.featurize([_spec(r) for r in rows], sc.p, int(threads), [int(t) for t in _extra_disabled(disabled)],
                       bool(rich))
    if as_lists:
        out = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in out.items()}
    return out
