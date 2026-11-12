"""Rule lemmas: what a one-off custom rule implies, derived from the rule itself before solving, case by case of its
parameters (the engine's rule analysis, csrc/absint.cpp expr_rule_lemmas), and handed to the engine as lemma rules
(docs/research/rule_lemmas_cas.md). A case that cannot hold removes that digit from the parameter cell; a case decided
by one or two other cells becomes a small table over the parameter and those cells. Each lemma rule carries a lemma
price: its setup the first time a route uses any rule of its content, then the cheaper use. The whole-rule table of a
rule over more than SMALL cells and no unknowns is gated: no human step reads it (the search still checks it), the
lemmas stand in.

A lemma over unknowns or layer values is written as a small custom rule ("P != 6", or the allowed combinations as an
or of ands) and read by AuxRule with the lemma's price.

Off unless ENABLED[0] (experiments: runs/rule_lemmas)."""

import re
from itertools import product

ENABLED = [False]
SMALL = 3  # a rule over at most this many cells is read as a whole (a small table, as hosts do): no lemmas
WEAK = 1.0  # tables allowing more than this share of cases are dropped (1.0: none; usefulness is the route's call)
# prices (placeholders until fitted to host pauses; docs/research/rule_lemmas_cas.md "Lemma difficulty"): setup =
# deriving it, paid once per lemma family -- impossibilities from one rule argument share it (N = 6 with N = 1), a
# table costs by the cases it took to build; use = applying it -- one elimination, one cell's candidates, or pairs
SETUP_IMPOSSIBLE, SETUP_TABLE, SETUP_PER_CASE = 1.0, 1.0, 0.05
USE_IMPOSSIBLE, USE_CELL = 0.5, 0.5
NEGATIVE = (
    1.5  # use price factor of a lemma from an absence (a missing arrow): harder to notice (Simon, Divided Attention)
)


def _aux_domains(p):
    ax = getattr(p, "aux", None)
    if not ax:
        return []
    out = [list(u["values"]) for u in ax["unknowns"]]
    for L in ax["layers"]:
        for c in range(p.N):
            g = L["given"].get(c)
            out.append([g] if g is not None else list(L["values"]))
    return out


def add(p, doc, spans):
    """p: the puzzle being built (groups, givens, aux set); doc: its file dict; spans: (rule, first, end) of each custom
    rule's engine constraints in p.constraints. Appends the lemma rules and gates wide whole-rule tables."""
    from . import cbackend as CB
    from .exchange.board import Board
    from .rules import custom as CU

    D = p.D
    B = Board(p.coords, D)
    B.unknowns, B.layers = doc.get("unknowns") or {}, doc.get("layers") or {}
    houses = [set(g.cells) for g in p.groups if getattr(g, "complete", False) and len(g.cells) == D]
    aux_dom = _aux_domains(p)
    full = (1 << D) - 1
    ids, added = {}, []
    for r, b, e in spans:
        if r.get("scope") or r.get("each"):
            continue
        try:
            ex = CU._expr(r, B)
        except CU.LangError:
            continue
        cells = [B.idx(n) for n in ex["cells"]]
        if len(cells) <= SMALL:
            continue
        dom = [full if c not in p.givens else 1 << (p.givens[c] - 1) for c in cells]
        vh = [[h for h, H in enumerate(houses) if c in H] for c in cells]
        lemmas = CB._C.rule_lemmas(ex, D, dom, vh, aux_dom, cells)
        n = 0
        unk, lay = list(B.unknowns), list(B.layers)

        def term(x):  # a variable of the rule as a term of the custom language
            if x >= 0:
                return B.name(cells[x])
            a = -1 - x
            if a < len(unk):
                return unk[a]
            li, c = divmod(a - len(unk), p.N)
            return f"{lay[li]}({B.name(c)})"

        for L in lemmas:
            aux = L["param"] < 0 or any(x < 0 for x in L["cells"])
            if L["kind"] == 1 and len(L["allowed"]) > WEAK * L["total"]:
                continue  # a weak table (Divided Attention's "no arrow" ends)
            if L["kind"] == 1 and len(L["cells"]) == 1 and 2 * len(L["allowed"]) > L["total"]:
                continue  # what a case forces on one variable, when most of its values stay: costs more than it says
            v = L["value"]
            neg = NEGATIVE if L.get("negative") else 1.0
            shape = (re.sub(r"\d+", "#", r["holds"]), L["conj"], L["param"])  # the same rule in another line: shared
            if aux:  # over unknowns / layer values: a small custom rule, read by AuxRule
                P = term(L["param"])
                if L["kind"] == 0:
                    holds, key, setup, use = f"{P} != {v}", shape + ("impossible",), SETUP_IMPOSSIBLE, USE_IMPOSSIBLE
                else:
                    T = [term(x) for x in L["cells"]]
                    ors = " or ".join(
                        "(" + " and ".join(f"{t} == {a}" for t, a in zip(T, row)) + ")" for row in L["allowed"]
                    )
                    holds = f"{P} != {v} or {ors}"
                    key = shape + (v, tuple(L["cells"]), tuple(map(tuple, sorted(L["allowed"]))))
                    setup = SETUP_TABLE + SETUP_PER_CASE * L["total"]
                    use = USE_CELL * (1 + len(T))
                try:
                    con = CU._expr({"cells": {}, "holds": holds}, B)
                except CU.LangError:
                    continue
                con["cells"] = [B.idx(n_) for n_ in con["cells"]]
                lid = ids.setdefault(key, 9000 + len(ids))
                con["lemma"] = {"id": lid, "setup": setup, "use": use * neg}
                con["lemma_case"] = {"param": L["param"], "value": v, "kind": "impossible" if L["kind"] == 0 else
                                     "table", "cells": L["cells"], "allowed": len(L["allowed"]), "total": L["total"],
                                     "conj": L["conj"], "aux": True}  # fmt: skip
                added.append(con)
                n += 1
                continue
            pc = cells[L["param"]]
            if L["kind"] == 0:  # one argument per rule part and parameter: its impossibilities share the setup
                key, setup, use = shape + ("impossible",), SETUP_IMPOSSIBLE, USE_IMPOSSIBLE
                con = {"type": "table", "cells": [pc], "allowed": [(x,) for x in range(1, D + 1) if x != v]}
            else:
                cs = [cells[i] for i in L["cells"]]
                ok = {tuple(a) for a in L["allowed"]}
                rows = [(x, *t) for x in range(1, D + 1) for t in product(range(1, D + 1), repeat=len(cs))
                        if x != v or t in ok]  # fmt: skip
                key = shape + (v, tuple(L["cells"]), tuple(sorted(ok)))
                setup, use = SETUP_TABLE + SETUP_PER_CASE * L["total"], USE_CELL * (1 + len(cs))
                con = {"type": "table", "cells": [pc, *cs], "allowed": rows}
            lid = ids.setdefault(key, 9000 + len(ids))
            con["lemma"] = {"id": lid, "setup": setup, "use": use * neg}
            con["lemma_case"] = {"param": pc, "value": v, "kind": "impossible" if L["kind"] == 0 else "table",
                                 "cells": [cells[i] for i in L["cells"]], "allowed": len(L["allowed"]),
                                 "total": L["total"], "conj": L["conj"]}  # fmt: skip
            added.append(con)
            n += 1
        if n and not ex.get("aux"):  # a rule over unknowns stays readable (a cage with an unknown total is human)
            for k in range(b, e):
                p.constraints[k]["gated"] = True
    p.constraints += added
    return len(added)
