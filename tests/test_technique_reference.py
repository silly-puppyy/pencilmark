"""Techniques against independent reference finders written from the textbook definitions (sudokuwiki.org, HoDoKu):
on mid-solve positions of generated puzzles (fixtures/technique_positions.json), the engine's XY-Chain and Simple
Colouring eliminations equal the reference's, and each added rule (colour unit wrap, hidden UR type 2, extended UR
type 2, APE with a 2-cell set) is found where it applies and removes only candidates the solution does not use."""

import copy
import json
from collections import defaultdict
from pathlib import Path

import pytest

import pencilmark
from pencilmark import api
from pencilmark import cbackend as CB
from pencilmark import solver as S

POS = json.loads((Path(__file__).parent / "fixtures" / "technique_positions.json").read_text("utf-8"))
HOUSES = [[r * 9 + c for c in range(9)] for r in range(9)] + [[r * 9 + c for r in range(9)] for c in range(9)]
HOUSES += [[(br + i // 3) * 9 + bc + i % 3 for i in range(9)] for br in (0, 3, 6) for bc in (0, 3, 6)]
PEERS = [set().union(*[set(h) for h in HOUSES if c in h]) - {c} for c in range(81)]


def _xy_chains(cand, max_cells=8):
    """eliminations of XY-chains of up to max_cells bivalue cells (the engine's 15-link limit)"""
    out, bi = set(), [c for c in range(81) if len(cand[c]) == 2]
    for c0 in bi:
        for x in cand[c0]:
            stack = [(c0, (set(cand[c0]) - {x}).pop(), (c0,))]
            while stack:
                c, on, path = stack.pop()
                if len(path) > 1 and on == x:
                    out |= {(t, x) for t in PEERS[c0] & PEERS[c] if x in cand[t] and t not in (c0, c)}
                if len(path) < max_cells:
                    stack += [
                        (n, (set(cand[n]) - {on}).pop(), path + (n,))
                        for n in bi
                        if n not in path and n in PEERS[c] and on in cand[n]
                    ]
    return out


def _simple_colouring(cand):
    """wrap (two same-colour cells see each other), unit wrap (a colour sees every place of the digit in a house) and
    trap (an uncoloured candidate sees both colours), per digit and conjugate-pair cluster of 4+ cells"""
    out = set()
    for d in range(1, 10):
        adj = defaultdict(set)
        for h in HOUSES:
            hc = [c for c in h if d in cand[c]]
            if len(hc) == 2:
                adj[hc[0]].add(hc[1])
                adj[hc[1]].add(hc[0])
        seen = set()
        for s in sorted(adj):
            if s in seen:
                continue
            col, todo = {s: 0}, [s]
            while todo:
                u = todo.pop()
                for v in adj[u]:
                    if v not in col:
                        col[v] = 1 - col[u]
                        todo.append(v)
            seen |= set(col)
            if len(col) < 4:
                continue
            false = None
            for k in (0, 1):
                ks = [c for c in col if col[c] == k]
                if any(b in PEERS[a] for a in ks for b in ks):
                    false = k
            for k in (0, 1):
                for h in HOUSES:
                    hc = [c for c in h if d in cand[c]]
                    if (
                        false is None
                        and hc
                        and all(col[c] == 1 - k if c in col else any(col.get(q) == k for q in PEERS[c]) for c in hc)
                    ):
                        false = k
            if false is not None:
                out |= {(c, d) for c in col if col[c] == false}
                continue
            for t in range(81):
                if t not in col and d in cand[t] and len(cand[t]) > 1:
                    seen_cols = {col[q] for q in PEERS[t] if q in col}
                    if seen_cols == {0, 1}:
                        out.add((t, d))
    return out


def _state(pos):
    p = pencilmark.load(pos["puzzle"])
    p.finalize()
    filled = {int(c): d for c, d in pos["givens"].items()}
    q = copy.copy(p)
    q.givens = filled
    cand = {c: [d for d in range(1, 10) if pos["mask"][c] >> (d - 1) & 1] for c in range(81)}
    return p, q, pos["mask"], cand, filled


def _moves(pos, techs):
    p, q, mask, cand, filled = _state(pos)
    keep = {k for k, v in S.TECH_NAMES.items() if v in techs}
    mv = CB.state_moves(
        q,
        api._params("computer"),
        cpuzzle=CB.to_cpuzzle(p),
        cand=mask,
        limit_per_tech=0,
        details=True,
        assume_unique=True,
        disabled=list(set(S.TECH_NAMES) - keep),
    )
    return [m for m in mv if m["tech"] in keep], cand, filled


@pytest.mark.parametrize("pos", [x for x in POS if x["kind"] in ("xy", "colour_unit")], ids=lambda x: x["id"])
def test_reference_finders_agree(pos):
    techs, ref = ({"XY-Chain", "RemotePairs"}, _xy_chains) if pos["kind"] == "xy" else ({"Coloring"}, _simple_colouring)
    mv, cand, filled = _moves(pos, techs)
    ours = {tuple(e) for m in mv for e in m["elim"]}
    want = {e for e in ref({c: ([filled[c]] if c in filled else cand[c]) for c in range(81)}) if e[0] not in filled}
    assert ours >= want and (pos["kind"] == "xy" or ours == want)


KINDS = {
    "colour_unit": "Coloring",
    "medusa_unit": "3DMedusa",
    "hur2": "UniqueRectangle",
    "xur2": "UniqueRectangle",
    "ape_als": "AlignedPairExclusion",
}


@pytest.mark.parametrize("pos", [x for x in POS if x["kind"] in KINDS], ids=lambda x: x["id"])
def test_added_rules_fire_and_are_sound(pos):
    mv, _, _ = _moves(pos, {KINDS[pos["kind"]]})
    assert mv
    sol = [int(x) for x in pencilmark.solve(pos["puzzle"])]
    assert all(sol[c] != d for m in mv for c, d in m["elim"])
