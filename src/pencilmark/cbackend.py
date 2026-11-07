"""C++ backend for pencilmark.solver (sources and build script in csolver/).

Drop-in fast paths with behavioural parity to the Python reference:

    from pencilmark import cbackend as CB
    steps, solved = CB.solve(puzzle, params)            # ~ Solver(puzzle, Scorer(params)).solve()
    sols = CB.brute_solve(puzzle, limit=2)               # ~ pencilmark.solver.brute_solve

Steps are real pencilmark.solver.Step / Move objects, so pencilmark.scoring.grade() works unchanged.
"""

from __future__ import annotations

import os as _os
from collections import defaultdict

from . import _csolver as _C  # noqa: E402  (the compiled C++ engine, sources in csrc/)
from . import model as M  # noqa: E402
from . import registry as R  # noqa: E402
from . import solver as S  # noqa: E402
from .engine_records import _explain, _name  # noqa: E402
from .scoring import Scorer  # noqa: E402

# diagnostics: PENCILMARK_SOLVE_STATS=1 sums the engine's per-strategy timings of every solve() call here
SOLVE_STATS = {} if _os.environ.get("PENCILMARK_SOLVE_STATS") == "1" else None

CTYPES = (
    "sum",
    "arrow",
    "equal_sum",
    "set",
    "table",
    "sandwich",
    "xsum",
    "skyscraper",
    "leftovers",
    "count",
    "line",
    "between",
    "counting_circles",
    "first_seen",
    "digit_set",
    "distinct_count",
    "contains",
    "expr",
    "cases",  # NT_CASES: a lemma about hidden structure (fog), one of several cases holds
)
# forcing chains: level (0 static / 1 dynamic / 2 nested), options, unit (0 cell / 1 unit),
# surviving branches, propagation steps over all branches, contradicting branches
_FORCING_KEYS = ("level", "options", "unit", "survivors", "steps", "contradictions")
_COMBO_KEYS = ("ctype", "constraint", "combos", "set_unique", "sum", "distinct", "n_vars", "complete")
_DESC_KEYS = ("log branches", "log depth", "search", "uniqueness", "counting", "contradiction", "held", "coverage")
XMETA_KEYS = {
    S.SUM_COMBO: _COMBO_KEYS,
    S.ARROW_COMBO: _COMBO_KEYS,
    S.SET_COMBO: _COMBO_KEYS,
    S.EQSUM_COMBO: _COMBO_KEYS,
    S.TABLE_COMBO: _COMBO_KEYS,
    # mode 0: digit in every combination, confined to one group -> removed from the group
    # mode 1: a house's candidates for `digit` all inside the scope -> combinations must use it
    S.SANDWICH_COMBO: _COMBO_KEYS,
    S.XSUM_COMBO: _COMBO_KEYS,
    S.SKYLINE_COMBO: _COMBO_KEYS,
    S.LOL_COMBO: _COMBO_KEYS,
    S.COUNT_COMBO: _COMBO_KEYS,
    # direct mental layer: reasons = bitmask (1 relation arc, 2 inequality bound, 4 line, 8 mental subset);
    # depth = inference rounds; line_* = the most distant informing line; subset = mental subset size;
    # inferences = number of mental exclusions used; hidden = hidden-single form
    S.LINE_D: (
        "reasons",
        "depth",
        "line_kind",
        "line_len",
        "line_dist",
        "line_informing",
        "transitive",
        "subset",
        "inferences",
        "hidden",
    ),
    S.MENTAL_D: (
        "reasons",
        "depth",
        "line_kind",
        "line_len",
        "line_dist",
        "line_informing",
        "transitive",
        "subset",
        "inferences",
        "hidden",
    ),
    S.SHORT_TRIAL: ("rounds", "placements"),
    S.EITHER_WAY: ("placements_a", "placements_b", "same_cell_choice", "no_notes"),
    S.LINE_CLASS: ("line_kind", "constraint", "line_len", "classes", "n_elims"),
    S.DIGIT_COUNT: ("units", "base_cells", "n_elims", "digit"),
    S.EQUAL_DIGITS: ("cell_a", "cell_b", "house", "candidates"),
    S.CLASS_SINGLE: ("cell", "anchor", "house", "members", "class_digits"),
    S.ID_PROPAGATE: ("anchor", "members", "class_digits", "digit", "from_anchor"),
    S.CLASS_PAIR: ("extend", "cell", "anchor", "other_anchor", "pair_digits"),
    S.CLASS_TRAP: ("anchor", "other_anchor", "pair_digits", "targets"),
    S.CHAIN_COLOUR: ("cell_a", "cell_b", "via", "candidates"),
    S.COLOUR_CLASH: ("cell", "anchor", "via", "members", "class_digits"),
    S.CLASS_POINTING: ("anchor", "house", "line", "places", "targets", "members"),
    S.CLASS_FISH: ("anchor", "base_a", "base_b", "cover_a", "cover_b", "places", "targets", "members"),
    S.CLASS_COMPLETE: ("colours", "digits", "copies"),
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
    S.BAND_LOGIC: ("lines", "boxes", "rules", "n_elims", "cells", "level", "cases"),
    S.FIREWORKS: ("cell_x", "cell_a", "cell_b", "digit_mask", "n_elims", "region"),
    S.HUMAN_CASE: ("cases", "rounds", "placed", "refutation", "options", "house"),
    S.COMBO_POS: ("cage", "house", "digit_mask", "max_in_cage", "need_outside", "fillings"),
    S.CLIQUE_HOUSE: ("size", "digit_mask", "n_elims", "placement"),
    S.LINE_SETS: ("house", "lines", "options", "n_elims"),
    S.LINE_CLUES: ("house", "clues", "fillings", "n_elims"),
    S.WEIGHTED_SUMS: ("facts", "cells", "max_weight", "n_elims", "total"),
    S.INNIE_X: ("house", "outie", "n_cells", "combos", "n_cages", "distinct", "complete"),
    S.MEDUSA: ("rule", "nodes", "digits", "n_elims", "false_color"),
    # SumBound: allowed range [lo, hi] of the target, triangular bound used, positions, rule type
    S.SUM_BOUND: ("lo", "hi", "triangular", "positions", "ctype"),
    # ClassCount: kind (0 parity, 1 thirds, 2 sum parity), class mask, placed, forced cells, others
    S.CLASS_COUNT: ("kind", "class_mask", "placed", "forced", "others"),
    # ClassColouring: kind (0 low / high, 1 odd / even), why (0 known cell, 1 house count, 2 house quota), cells, links, houses
    S.CLASS_COLOUR: ("kind", "why", "cells", "links", "houses"),
    # ClueFacts / ClueShape: level (1 clue alone, 2 with the shape), cells, eliminations
    S.CLUE_FACTS: ("level", "cells", "n_elims"),
    S.CLUE_SHAPE: ("level", "cells", "n_elims"),
    S.DOMINO: ("dominoes", "digit_or_mask", "cell_a", "cell_b", "fillings"),
    # seed: 0 house argument only, 1 equality rule / case split, 2 human colouring (consistent with the
    # solution), 3 human colouring without a solution to check against (soft hypothesis)
    S.COLOUR_ALGEBRA: ("cells", "digits", "n_elims", "seed", "class_kinds"),
    S.N_WING: ("size", "z", "z_cells", "n_elims"),
    S.SUE_DE_COQ: ("n_inter", "n_line", "n_box", "digit_mask", "n_elims"),
    S.APE: ("cell_a", "cell_b", "n_single", "n_elims", "n_als"),
    S.CHUTE_RP: ("cell_a", "cell_b", "absent", "eliminated", "n_elims"),
    S.POM: ("digit", "templates", "n_elims", "blocker"),
    S.GURTH: ("symmetry", "n_elims"),
    S.NISHIO: ("digit", "rounds", "placements", "empty_house"),
    S.FORCING: _FORCING_KEYS,
    S.DYN_FORCING: _FORCING_KEYS,
    S.NESTED_FORCING: _FORCING_KEYS,
    S.MULTI_COLOR: ("digit", "cells", "n_elims"),
    # Guess (priced as the expected human cost of guessing): candidates, mean / max refutation work of
    # the wrong candidates, how many survive basic propagation (deep bifurcations), expected work x10
    S.GUESS: ("k", "mean_refutation", "max_refutation", "deep", "expected_work_x10"),
    S.WHAT_IF: _FORCING_KEYS,
    S.MENTAL_NOTES: ("via_technique", "via_eliminations", "hidden"),
    S.FINNED_FISH: ("size", "fins", "sashimi", "kind", "n_elims", "digit", "n_base_cells"),
    S.JELLYFISH: ("size", "fins", "sashimi", "kind", "n_elims", "digit", "n_base_cells"),
}
# chains: links, strong links by source (bivalue cell, bilocal digit in a
# group, constraint must-contain, pair relation), weak links by source (same
# cell, peer cells, pair relation), max hop (Chebyshev distance between
# consecutive cells), number of digits
_CHAIN_KEYS = (
    "links",
    "strong_bivalue",
    "strong_bilocal",
    "strong_constraint",
    "strong_relation",
    "weak_cell",
    "weak_house",
    "weak_relation",
    "max_hop",
    "n_digits",
)
for _t in (S.X_CHAIN, S.XY_CHAIN, S.AIC_CHAIN, S.NICE_LOOP, S.MENTAL_CHAIN, S.REMOTE_PAIRS, S.EMPTY_RECT):
    XMETA_KEYS[_t] = _CHAIN_KEYS
XMETA_KEYS[S.ALS_AIC] = _CHAIN_KEYS[:5] + ("n_als",) + _CHAIN_KEYS[6:]
# pattern codes the engine puts on moves (data/patterns.csv): sudokuwiki-style codes for chain special cases, names
# of uniqueness / ALS / set-theory / forcing / colouring forms
CHAIN_CODES = {p.cpp_code: p.engine_code for p in R.patterns()}
_FISH_SIZE = {2: "X-Wing", 3: "Swordfish", 4: "Jellyfish"}


def code_name(code):
    """Move.code (int from C++) -> short pattern code / fish name."""
    if not code:
        return None
    if 4000 <= code < 4200:  # line rule: kind + flavour
        kind, sub = divmod(code - 4000, 10)
        name = M.LINE_KINDS[kind] if kind < len(M.LINE_KINDS) else f"line{kind}"
        return name + {
            0: "",
            1: " bounds",
            2: " no-5",
            3: " adjacent",
            4: " transitive",
            5: " classes",
            6: " scan",
        }.get(sub, f" {sub}")
    if code == 4200:
        return "relation arc"
    if code == 4300:
        return "inequality chain"
    if code == 4408:
        return "mental subset chain"
    if 6000 <= code < 7000:
        return "named table rule"
    if 7100 <= code < 7200:  # regions to find (chaos_logic.cpp)
        return {7101: "region sealed", 7102: "region's last cells", 7111: "region exclusion",
                7112: "equal digits split regions", 7113: "region exclusion", 7121: "region cannot reach",
                7122: "too small for a region", 7131: "dead end", 7141: "region exit", 7151: "region needs a digit",
                7161: "pocket counting"}.get(code, f"region {code}")  # fmt: skip
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
        return " ".join(
            x
            for x in (("", "Finned", "Sashimi")[fin], ("", "Franken", "Mutant")[kind], _FISH_SIZE.get(n, f"fish{n}"))
            if x
        )
    return CHAIN_CODES.get(code, f"code {code}")


class CMove(S.Move):
    """pencilmark.solver.Move plus structured metadata of the C++-only
    techniques: xmeta (dict, see XMETA_KEYS), family, code."""

    __slots__ = ("xmeta", "family", "code", "explain", "lplace", "lelim", "idfx")


_CPUZZLES = {}  # repr of the make_puzzle arguments -> C++ puzzle; a card builds the same puzzle about 6 times


def to_cpuzzle(p):
    """Finalized pencilmark.model.Puzzle -> C++ puzzle (structure only; givens are
    passed per solve). Relation tables are taken from p.rel_ex, so any
    relation kind (including ones registered at runtime) works. Cached on the full
    arguments, so a puzzle whose rules or domains change gets a new build."""
    args = _cpuzzle_args(p)
    key = repr(args)
    cp = _CPUZZLES.get(key)
    if cp is None:
        if len(_CPUZZLES) >= 16:  # a few recent puzzles: rate_many and the generator move on quickly
            _CPUZZLES.pop(next(iter(_CPUZZLES)))
        cp = _CPUZZLES[key] = _C.make_puzzle(*args)
    return cp


AE_LABEL_PLACE, AE_LABEL_ELIM, AE_ID_JOIN, AE_ID_NEQ, AE_ID_USE = 1, 2, 3, 4, 5  # csrc/solver.hpp AEffKind


def _label_fx(aeffs):
    """(placement, eliminations) of region labels from a move's annotation effects (kind, cell, arg)."""
    place = next(((c, a) for k, c, a in aeffs if k == AE_LABEL_PLACE), None)
    return place, [(c, a) for k, c, a in aeffs if k == AE_LABEL_ELIM]


def _id_fx(aeffs):
    """identity layer (params colouring): the move's identity effects [(kind, cell, arg)]: AE_ID_JOIN cell's class merges
    into the class whose first cell is arg; AE_ID_NEQ the classes of cell and arg differ; AE_ID_USE the move relies on
    the class anchored at cell"""
    return [(k, c, a) for k, c, a in aeffs if k in (AE_ID_JOIN, AE_ID_NEQ, AE_ID_USE)]


def id_joins(fx):
    """the class joins [(cell, anchor)] among identity effects"""
    return [(c, a) for k, c, a in fx or () if k == AE_ID_JOIN]


def id_changes(fx):
    """the move changes the identity state (a join or a difference, not only a use)"""
    return any(k in (AE_ID_JOIN, AE_ID_NEQ) for k, _, _ in fx or ())


def id_norm(idc, vals):
    """identity state in place, as the engine's id_normalize (csrc/set_logic.cpp): idc = class per cell (0 none, else 1 +
    the class's first cell), then the class differences as sorted (lo, hi) class-id pairs, flattened. A class lives
    while it has an open member and two members or a difference partner; one with every member placed lives on while a
    partner has an open member; a pair lives while both its classes do."""
    N = len(vals)
    cls = {}
    for c in range(N):
        if idc[c]:
            cls.setdefault(idc[c], []).append(c)
    prs = [(idc[i], idc[i + 1]) for i in range(N, len(idc) - 1, 2)]
    prs = [(a, b) for a, b in prs if a != b and a in cls and b in cls]
    opn = {k: any(not vals[c] for c in ms) for k, ms in cls.items()}
    alive = dict.fromkeys(cls, True)
    ch = True
    while ch:
        ch = False
        for k, ms in cls.items():
            if not alive[k]:
                continue
            part = [b if a == k else a for a, b in prs if k in (a, b) and alive[b if a == k else a]]
            if (len(ms) >= 2 or part) and (opn[k] or any(opn[o] for o in part)):
                continue
            alive[k] = False
            ch = True
    del idc[N:]
    for c in range(N):
        idc[c] = 0
    ren = {}
    for k, ms in cls.items():
        if alive[k]:
            ren[k] = ms[0] + 1
            for c in ms:
                idc[c] = ms[0] + 1
    for a, b in sorted({tuple(sorted((ren[a], ren[b]))) for a, b in prs if alive[a] and alive[b]}):
        idc += [a, b]


def id_apply(idc, vals, fx):
    """apply a move's identity effects (joins, then differences, as the engine) and normalise"""
    N = len(vals)
    for k, c, a in fx or ():
        if k == AE_ID_JOIN and c != a:
            ks = {x for x in (idc[c], idc[a]) if x}
            lo = min([c, a] + [x for x in range(N) if idc[x] in ks])
            for x in range(len(idc)):
                if idc[x] in ks:
                    idc[x] = lo + 1
            idc[c] = idc[a] = lo + 1
            id_norm(idc, vals)
    for k, c, a in fx or ():
        if k == AE_ID_NEQ and c != a:
            for x in (c, a):
                if not idc[x]:
                    idc[x] = x + 1
            idc += [idc[c], idc[a]]
            id_norm(idc, vals)
    id_norm(idc, vals)


def id_held(N, givens, steps):
    """identity layer route accounting: which steps cost nothing. steps = [(place, elims, idfx)] in route order.
    A step that only changes the identity state (joins / differences, no placement or elimination) is held when made.
    A step with a placement or elimination is charged, and so is every held step it relies on, transitively: a step
    that uses class K (AE_ID_USE) relies on each earlier held join whose cells are now in K, and on each earlier held
    difference whose two cells are now in two classes it uses. Held steps no charged step relies on were never needed:
    the route without them is the same proof. Returns a list of bools (True = held and never used: priced 0)."""
    vals = [0] * N
    for c, v in givens.items():
        vals[c] = v
    idc = [0] * N
    deps, digit, built = [], [], []  # per step: earlier steps it relies on; places / eliminates; (kind, x, y) it built
    for place, elims, fx in steps:
        used = {idc[u] for k, u, _ in fx or () if k == AE_ID_USE and u < N and idc[u]}
        d = set()
        if used:
            for j, bj in enumerate(built):
                for k, x, y in bj:
                    if (k == AE_ID_JOIN and idc[x] in used) or (
                        k == AE_ID_NEQ and idc[x] in used and idc[y] in used and idc[x] != idc[y]
                    ):
                        d.add(j)
        deps.append(d)
        digit.append(bool(place) or bool(elims))
        built.append([(k, c, a) for k, c, a in fx or () if k in (AE_ID_JOIN, AE_ID_NEQ)])
        if place:
            vals[place[0]] = place[1]
        id_apply(idc, vals, fx)
    charged = [False] * len(steps)
    todo = [i for i in range(len(steps)) if digit[i]]
    for i in todo:
        charged[i] = True
    while todo:
        for j in deps[todo.pop()]:
            if not charged[j]:
                charged[j] = True
                todo.append(j)
    return [not charged[i] and bool(built[i]) for i in range(len(steps))]


def _ann_kw(labels):
    """engine keywords of a mid-solve annotation state: labels = (region labels, label candidates[, colour classes]);
    either part may be None"""
    kw = {}
    if labels is None:
        return kw
    if labels[0] is not None:  # regions to find
        kw["labels"] = (list(labels[0]), list(labels[1]))
    if len(labels) > 2 and labels[2] is not None:  # identity layer: class per cell (0 none)
        kw["idc"] = [int(x) for x in labels[2]]
    return kw


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
        elif (
            d.get("type") == "yin_yang"
        ):  # shading: read by the exhaustive search (brute_force.cpp); rate: band Unknown with a reason
            d = {"type": "line", "kind": "palindrome", "cells": [], "skip": True, "shading": d}
        elif d.get("type") in ("chaos", "region_border", "same_region"):  # regions to find: read by the exhaustive
            d = {
                "type": "line",
                "kind": "palindrome",
                "cells": [],
                "skip": True,
                "region": d,
            }  # search (brute_force.cpp)
        cons.append(d)
    aux = getattr(p, "aux", None)
    if aux:  # the file's unknowns and layers: read by the exhaustive search (brute_force.cpp); rate: band Unknown with a reason
        cons.append(
            {
                "type": "line",
                "kind": "palindrome",
                "cells": [],
                "skip": True,
                "aux_defs": {
                    "unknowns": [u["values"] for u in aux["unknowns"]],
                    "layers": [{"values": L["values"], "given": L["given"]} for L in aux["layers"]],
                },
            }
        )
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


def solve(
    puzzle,
    params=None,
    disabled=(),
    solution=None,
    allow_direct=True,
    max_steps=5000,
    cpuzzle=None,
    assume_unique=True,
    all_tiers=False,
    explain=False,
    colour_seeds=None,
    cand=None,
    labels=None,
    stop_cells=None,
):
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
    disabled = [int(t) for t in set(disabled) | search_disabled(params)]  # env override, e.g. "58,59,60"
    args = [
        cp,
        list(puzzle.givens.items()),
        cp_p,
        disabled,
        sol,
        bool(allow_direct),
        int(max_steps),
        bool(assume_unique),
        bool(all_tiers),
    ]
    args.append(bool(explain))
    args.append(_colour_list(colour_seeds, puzzle.N))
    kw = _ann_kw(labels)  # regions to find / colour classes: mid-solve
    if stop_cells:  # stop right after placing one of these cells (the fog route's reveal cells)
        kw["stop_cells"] = sorted(int(c) for c in stop_cells)
    if SOLVE_STATS is not None:  # diagnostics: per-strategy (ms, calls, hits) summed into SOLVE_STATS
        kw["stats"] = True
    if cand is not None:
        out = _C.solve(*args, cand=[int(x) for x in cand], **kw)
    else:
        out = _C.solve(*args, **kw)
    raw, solved = out[0], out[1]
    if SOLVE_STATS is not None:
        for k_, (ms, calls, hits) in out[2].items():
            a_ = SOLVE_STATS.setdefault(k_, [0.0, 0, 0])
            a_[0] += ms
            a_[1] += calls
            a_[2] += hits
    info = _C.puzzle_info(cp, disabled) if explain else None
    steps = []
    for row in raw:
        alts, chosen, place, el, nm, d, mode, n_empty, er, nw, xm, code, pats, exs = row[:14]
        n_cands = row[14] if len(row) > 14 else None  # dev74+: candidates before the step
        m = CMove.__new__(CMove)
        m.feat = alts[chosen]
        m.place = place
        m.elim = el
        m.lplace, m.lelim = _label_fx(row[15]) if len(row) > 15 else (None, ())  # annotations: region labels
        m.idfx = _id_fx(row[15]) if len(row) > 15 else []  # ... and identity effects (colour classes)
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


def explain_record(puzzle, move, cpuzzle=None):
    """the engine's structured justification of one state_moves(details=True) move (as solve(explain=True) gives),
    or None when the move carries no records"""
    if move.get("ex") is None:
        return None
    from types import SimpleNamespace as NS

    info = getattr(puzzle, "_pm_info", None)
    if info is None:  # implied groups follow the base groups, so one listing of them names every move's units
        info = _C.puzzle_info(cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle), [])
        try:
            puzzle._pm_info = info
        except Exception:
            pass
    m = NS(
        feat=(move["tech"],),
        code=move.get("code"),
        d=move.get("d"),
        place=move.get("place"),
        elim=move.get("elim") or (),
        xmeta=move.get("xmeta"),
    )
    return _explain(puzzle, m, move["nm"], move.get("pattern") or [], move["ex"], info)


def state_moves(
    puzzle,
    params=None,
    all_tiers=True,
    assume_unique=False,
    limit_per_tech=0,
    disabled=(),
    solution=None,
    cpuzzle=None,
    written=None,
    details=False,
    cand=None,
    skip=(),
    labels=None,
):
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
    stay what pattern detection expects.
    skip = techniques whose notes-tier strategies are not run: unlike disabled, every other strategy sees the same
    disabled flags, so the result is exactly the full listing's moves minus (some of) the skipped techniques'."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    sc = Scorer(params)
    cp = cpuzzle if cpuzzle is not None else to_cpuzzle(puzzle)
    sol = [int(x) for x in solution] if solution is not None else None
    args = [
        cp,
        list(puzzle.givens.items()),
        sc.p,
        [int(t) for t in disabled],
        sol,
        bool(assume_unique),
        int(limit_per_tech),
    ]
    kw = _ann_kw(labels)  # regions to find / colour classes: mid-solve
    if cand is not None:  # mid-solve candidates as a mask; cpuzzle keeps the puzzle's own domains (build it once)
        raw = _C.state_moves(
            *args,
            None if written is None else [int(x) for x in written],
            bool(details),
            [int(x) for x in cand],
            skip=[int(t) for t in skip],
            **kw,
        )
    elif written is not None or details:
        raw = _C.state_moves(
            *args,
            None if written is None else [int(x) for x in written],
            bool(details),
            skip=[int(t) for t in skip],
            **kw,
        )
    else:
        raw = _C.state_moves(*args, skip=[int(t) for t in skip], **kw)
    chaos = any(c.get("type") == "chaos" for c in getattr(puzzle, "constraints", ()))
    ann = chaos or bool(sc.p.get("colouring"))  # regions to find / identity layer: annotation effects
    out = []
    for r in raw:
        lfx = None
        if ann:  # the annotation effects come last
            lfx, r = r[-1], r[:-1]
        t, code, pl, el, d = r[:5]
        m = {
            "tech": t,
            "name": S.TECH_NAMES.get(t, str(t)),
            "code": code_name(code),
            "place": pl,
            "elim": list(el),
            "d": d,
        }
        if lfx is not None:
            if chaos:
                m["lplace"], m["lelim"] = _label_fx(lfx)
            ij = _id_fx(lfx)
            if ij:
                m["idfx"] = ij
        if len(r) > 9:  # the engine's explanation records and naming triple (decode with explain_record)
            m["ex"], m["nm"] = list(r[9]), tuple(r[10])
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
    sols, complete = _C.brute_solve(cp, list(puzzle.givens.items()), int(limit), int(node_limit), st, True)
    out = BruteResult(sols)
    out.complete = bool(complete)
    return out


def computer_search():
    """Pure computer search: unbounded trial, forcing chains / nets (basic, dynamic, nested), Nishio nets, pattern
    overlay. Humans don't solve this way (CTC hosts: 0 'bifurcate' at 119 engine guess points)."""
    return {t.id for t in R.techniques() if t.band == R.BANDS.index("Extreme")}  # Extreme is this search, by definition


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
            out.add(S.GUESS)  # guessing off (default): the stuck fallback proves instead (no_guess_params)
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
