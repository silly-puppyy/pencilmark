"""The replayed grid: implied houses, derived candidates, State / replay, rules, the no-notes view. (split from explain.py)"""

from __future__ import annotations

from itertools import combinations

from .. import solver as S
from ..model import bit, digits_of, popcount
from .base import LINE_NAMES, Namer, _rel_ex, _rel_tables, rel_label


# ---------------------------------------------------------- implied houses --
def implied_houses(p):
    """Derived houses exactly as the engine builds them (csolver model.cpp build_implied): unions of
    k = 2..4 parallel lines minus k-1 disjoint complete houses inside them that leave D cells.
    -> list of (cells, lines, removed group indices or 'implied#')."""
    if getattr(p, "_ximplied", None) is not None:
        return p._ximplied
    known = {frozenset(p.groups[gi].cells) for gi in p.houses}
    newh = []
    for orient in ("row", "col"):
        lines = [gi for gi in p.houses if p.groups[gi].kind == orient and len(p.groups[gi].cells) == p.D]
        if len(lines) > 30:
            continue
        for _ in range(2):
            rem = [(frozenset(p.groups[gi].cells), gi) for gi in p.houses if p.groups[gi].kind != orient]
            rem += [(h, f"implied{j + 1}") for j, (h, _, _) in enumerate(newh)]
            for k in range(2, min(4, len(lines)) + 1):
                for idx in combinations(lines, k):
                    U = frozenset().union(*(p.groups[g].cells for g in idx))
                    inside = [r for r in rem if r[0] <= U]
                    if len(inside) < k - 1:
                        continue

                    def sel(s0, d2, S, used):
                        if d2 == k - 1:
                            if len(S) == p.D and S not in known:
                                known.add(S)
                                newh.append((S, idx, tuple(used)))
                            return
                        for j in range(s0, len(inside)):
                            h, name = inside[j]
                            if h <= S:
                                sel(j + 1, d2 + 1, S - h, used + [name])

                    sel(0, 0, U, [])
    p._ximplied = newh
    return newh


def derived(p):
    """The puzzle the engine actually solves: p plus its implied houses (same group indices, the
    implied ones appended as 'implied1', 'implied2', ...)."""
    if getattr(p, "_xderived", None) is not None:
        return p._xderived
    if not hasattr(p, "groups_of"):
        p.finalize()
    imp = implied_houses(p)
    if not imp:
        p._xderived = p
        return p
    import copy

    from ..model import Group

    q = copy.copy(p)
    q.groups = list(p.groups)
    for k, (cells, lines, removed) in enumerate(imp):
        g = Group(f"implied{k + 1}", tuple(sorted(cells)), "implied", True)
        g.src = (lines, removed)
        q.groups.append(g)
    q._xderived = q
    for attr in ("_xrel", "_xrules", "_xunions", "_xinnie4", "_xinnie9", "_xlol", "_xrects"):
        if hasattr(q, attr):
            delattr(q, attr) if attr in q.__dict__ else None
    q.finalize()
    q._xbase = p
    p._xderived = q
    return q


# ------------------------------------------------------------------- state --
class State:
    """Grid before a step: placed digits, candidates (the engine's own maintenance: peers + pair
    relations on every placement, eliminations applied), solving mode, and which step last
    removed each candidate (for 'it lost its last alternative to ...' remarks)."""

    def __init__(self, p, vals=None, cand=None, mode="direct"):
        self.p = p
        self.vals = list(vals) if vals is not None else [0] * p.N
        self.cand = list(cand) if cand is not None else list(p.domains)
        self.mode = mode
        self.idx = 0
        self.lost = {}  # (cell, digit) -> (step idx, technique code)

    @classmethod
    def initial(cls, p):
        st = cls(p)
        for c, v in p.givens.items():
            st.place(c, v)
        st.givens = set(p.givens)
        return st

    def copy(self):
        s = State(self.p, self.vals, self.cand, self.mode)
        s.idx, s.lost = self.idx, dict(self.lost)
        s.givens = getattr(self, "givens", set())
        return s

    def placed_g(self, gi):
        m = 0
        for c in self.p.groups[gi].cells:
            if self.vals[c]:
                m |= bit(self.vals[c])
        return m

    def place(self, c, v, tag=None):
        p = self.p
        self.vals[c] = v
        self.cand[c] = 0
        b = bit(v)
        for q in p.peer_list[c]:
            if self.cand[q] & b:
                self.cand[q] &= ~b
                if tag is not None:
                    self.lost[(q, v)] = tag
        for q in p.nonconsec_list[c]:
            nb = p.rel_ex[c][q][v]
            if self.cand[q] & nb:
                if tag is not None:
                    for d in digits_of(self.cand[q] & nb):
                        self.lost[(q, d)] = tag
                self.cand[q] &= ~nb

    def apply(self, step):
        m = step.move
        tag = (self.idx, m.feat[0])
        if m.feat[0] == S.TAKE_NOTES:
            self.mode = "notes"
        if m.place:
            self.place(*m.place, tag=tag)
        for c, v in m.elim:
            if self.cand[c] & bit(v):
                self.lost[(c, v)] = tag
            self.cand[c] &= ~bit(v)
        if step.mode == "notes":
            self.mode = "notes"
        self.idx += 1


def replay(p, steps, state=None):
    """Yield (index, step, state BEFORE the step); the state object is copied per step."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    p = derived(p)
    st = state.copy() if state is not None else State.initial(p)
    for i, step in enumerate(steps):
        st.idx = i
        yield i, step, st.copy()
        st.apply(step)


def _as_state(p, state):
    if isinstance(state, State):
        return state
    if isinstance(state, dict):
        return State(p, state.get("vals"), state.get("cand"), state.get("mode", "direct"))
    if isinstance(state, (tuple, list)) and len(state) == 2:
        return State(p, state[0], state[1])
    raise TypeError("state must be explain.State, {'vals','cand'} or (vals, cand)")


# ------------------------------------------------------------ n-ary rules ----
class Rule:
    """One multi-cell rule (cage, line, arrow, sum clue ...) as a checkable predicate."""

    def __init__(
        self,
        kind,
        cells,
        label,
        index=None,
        group=None,
        con=None,
        total=None,
        segs=None,
        line_kind=None,
        distinct=False,
    ):
        self.kind, self.cells, self.label, self.index, self.group = kind, list(cells), label, index, group
        self.con, self.total, self.segs, self.line_kind, self.distinct = con or {}, total, segs, line_kind, distinct

    def check(self, a):
        k, con = self.kind, self.con
        if k in ("sum", "cage", "little_killer", "innie"):
            return sum(a) == self.total
        if k == "arrow":
            nc = len(con["circle"])
            num = int("".join(str(x) for x in a[:nc])) if nc > 1 else a[0]
            return num == sum(a[nc:])
        if k == "equal_sum":
            s, pos = None, 0
            for seg in self.segs:
                t = sum(a[pos : pos + len(seg)])
                pos += len(seg)
                if s is None:
                    s = t
                elif t != s:
                    return False
            return True
        if k == "set":
            return len(set(a)) == len(a) and max(a) - min(a) == len(a) - 1
        if k == "between":
            lo, hi = sorted((a[0], a[-1]))
            return all(lo < x < hi for x in a[1:-1])
        if k == "table":
            return tuple(a) in {tuple(t) for t in con["allowed"]}
        if k == "sandwich":
            D = max(a)
            try:
                i, j = sorted((a.index(1), a.index(D)))
            except ValueError:
                return False
            return sum(a[i + 1 : j]) == self.total
        if k == "xsum":
            return a[0] <= len(a) and sum(a[: a[0]]) == self.total
        if k == "skyscraper":
            seen, top = 0, 0
            for x in a:
                if x > top:
                    seen, top = seen + 1, x
            return seen == con["count"]
        if k == "distinct_count":
            return len(set(a)) == con["count"]
        if k == "contains":
            return a[0] in a[1:]
        if k == "count":
            from collections import Counter

            cnt = Counter(a)
            if "each" in con:
                return all(v == con["each"] for v in cnt.values())
            return all(cnt.get(int(v), 0) == n for v, n in con["digits"].items())
        return True  # pairwise lines: the pair relations do the work

    def partial(self, a, i, dom):
        """Prune a prefix a[0..i]."""
        k = self.kind
        if k in ("sum", "cage", "little_killer", "innie"):
            s = sum(a[: i + 1])
            rest = dom[i + 1 :]
            lo = sum(min(digits_of(m)) for m in rest) if rest else 0
            hi = sum(max(digits_of(m)) for m in rest) if rest else 0
            return s + lo <= self.total <= s + hi
        if k == "set":
            pre = a[: i + 1]
            return len(set(pre)) == len(pre) and max(pre) - min(pre) <= len(self.cells) - 1
        return True


def _con_label(nm, con, idx):
    t = con.get("type")
    lk = con.get("line_kind") or (con.get("kind") if t == "line" else None)
    if lk:
        cells = con.get("cells") or [c for s in con.get("segments", []) for c in s]
        name = LINE_NAMES.get(lk, lk + " line")
        if lk == "thermo" or lk == "slow_thermo":
            return f"the {name} with its bulb at {nm.cell(cells[0])} (running {nm.span(cells)})"
        if lk == "between":
            return f"the between line from {nm.cell(cells[0])} to {nm.cell(cells[-1])}"
        if lk == "zipper":
            segs = con.get("segments")
            mid = segs[-1][0] if segs and len(segs[-1]) == 1 else None
            return f"the zipper line through {nm.cells(cells)}" + (
                f" (centre {nm.cell(mid)})" if mid is not None else ""
            )
        if lk == "region_sum":
            return f"the region-sum line through {nm.cells(cells)}"
        return f"the {name} {nm.span(cells)}"
    if t == "arrow":
        circ = con["circle"]
        cl = nm.cell(circ[0]) if len(circ) == 1 else "the pill " + nm.cells(circ)
        return f"the arrow from {cl} along {nm.cells(con['line'])}"
    if t == "sum":
        return f"the sum clue {con['total']} over {nm.cells(con['cells'])}"
    if t == "little_killer":
        return f"the little-killer clue {con['total']} along {nm.span(con['cells'])}"
    if t == "sandwich":
        return f"the sandwich clue {con['total']} (on {nm.span(con['cells'])})"
    if t == "xsum":
        return f"the X-sum clue {con['total']} (reading {nm.span(con['cells'])})"
    if t == "skyscraper":
        return f"the skyscraper clue {con['count']} (looking along {nm.span(con['cells'])})"
    if t == "equal_sum":
        return "the equal-sum rule over " + "; ".join(nm.cells(s) for s in con["segments"])
    if t == "count":
        return f"the counting rule over {nm.span(con['cells'])}"
    if t == "distinct_count":
        return f"the distinct-count clue {con['count']} (along {nm.span(con['cells'])})"
    if t == "contains":
        return f"the arrow in {nm.cell(con['cells'][0])} (its digit appears along {nm.span(con['cells'][1:])})"
    if t == "between":
        return f"the between line from {nm.cell(con['cells'][0])} to {nm.cell(con['cells'][-1])}"
    if t == "table":
        return f"the combination rule on {nm.cells(con['cells'])}"
    if t == "set":
        return f"the consecutive-set rule on {nm.cells(con['cells'])}"
    return f"rule {idx}"


def rules(p):
    """Every multi-cell rule of the puzzle, keyed like the engine: ('con', index into p.constraints
    then detected lines), ('cage', group index)."""
    if getattr(p, "_xrules", None) is not None:
        return p._xrules
    nm = Namer(p)
    out = {}
    nc = len(p.constraints)
    for i, con in enumerate(p.constraints):
        t = con.get("type")
        if t == "line":
            if con.get("kind") in ("renban", "between", "zipper", "region_sum"):
                continue  # carried by the compiled n-ary entry
            out[("con", i)] = Rule(
                "line", con["cells"], _con_label(nm, con, i), index=i, con=con, line_kind=con["kind"]
            )
            continue
        lk = con.get("line_kind")
        if t == "arrow":
            r = Rule("arrow", list(con["circle"]) + list(con["line"]), _con_label(nm, con, i), index=i, con=con)
        elif t in ("sum", "little_killer"):
            r = Rule(
                t,
                con["cells"],
                _con_label(nm, con, i),
                index=i,
                con=con,
                total=con["total"],
                distinct=bool(con.get("distinct")) and t == "sum",
            )
        elif t == "equal_sum":
            r = Rule(
                "equal_sum",
                [c for s in con["segments"] for c in s],
                _con_label(nm, con, i),
                index=i,
                con=con,
                segs=con["segments"],
                line_kind=lk,
            )
        elif t == "set":
            r = Rule("set", con["cells"], _con_label(nm, con, i), index=i, con=con, line_kind=lk, distinct=True)
        elif t in ("between", "table", "sandwich", "xsum", "skyscraper", "count", "distinct_count", "contains"):
            r = Rule(t, con["cells"], _con_label(nm, con, i), index=i, con=con, total=con.get("total"), line_kind=lk)
        else:
            continue
        out[("con", i)] = r
    _, _, _, linecons = _rel_tables(p)
    for idx, kind, cells in linecons:
        if idx >= nc:
            con = {"type": "line", "kind": kind, "cells": cells}
            out[("con", idx)] = Rule("line", cells, _con_label(nm, con, idx), index=idx, con=con, line_kind=kind)
    for gi, g in enumerate(p.groups):
        if g.total is not None:
            out[("cage", gi)] = Rule("cage", g.cells, nm.cage(gi), group=gi, total=g.total, distinct=True)
    p._xrules = out
    return out


_MENTAL_LINE_MAX = int(__import__("os").environ.get("CSOLVER_MENTAL_LINE_MAX", "50"))


def enum_rule(p, rule, dom, node_limit=150000, keep=400, max_count=None, support=True):
    """All assignments of rule.cells within masks `dom` that satisfy the rule, the pair relations
    and distinctness inside the scope. -> dict(sup, count, sols, complete).
    max_count: stop as soon as more fillings exist (-> complete False, count None); support=False: no witness search
    when the enumeration is incomplete (the direct-mode reading mirrors the engine's cap and skips such rules)."""
    cells = rule.cells
    n = len(cells)
    distinct_all = rule.distinct
    conflicts = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i):
            a, b = cells[j], cells[i]
            same = distinct_all or b in p.peers[a]
            tab = p.rel_ex[a].get(b) if b in p.rel_ex[a] else None
            if same or tab:
                conflicts[i].append((j, same, tab))
    sup = [0] * n
    sols = []
    asg = [0] * n
    st = {"count": 0, "nodes": 0, "complete": True}

    def rec(i):
        if st["nodes"] > node_limit:
            st["complete"] = False
            return
        if i == n:
            if rule.check(asg):
                st["count"] += 1
                if max_count is not None and st["count"] > max_count:
                    st["complete"] = False
                    st["nodes"] = node_limit + 1  # unwinds the recursion at the next node
                    return
                for k in range(n):
                    sup[k] |= bit(asg[k])
                if len(sols) < keep:
                    sols.append(tuple(asg))
            return
        for v in digits_of(dom[i]):
            st["nodes"] += 1
            ok = True
            for j, same, tab in conflicts[i]:
                if (same and asg[j] == v) or (tab and tab[asg[j]] & bit(v)):
                    ok = False
                    break
            if not ok:
                continue
            asg[i] = v
            if rule.partial(asg, i, dom):
                rec(i + 1)
        asg[i] = 0

    rec(0)
    if not st["complete"] and not support:
        return {"sup": sup, "count": None, "sols": sols, "complete": False}
    if not st["complete"]:
        sup2, exact = _support_search(p, rule, dom, conflicts)
        if not exact and n <= 9:
            sup2, exact = _support_search(p, rule, dom, conflicts, node_limit=80000)
        return {"sup": sup2, "count": None, "sols": sols, "complete": exact}
    return {"sup": sup, "count": st["count"], "sols": sols, "complete": st["complete"]}


def _feasible(rule, asg, dom):
    """Bounds check on a partial assignment (dict index -> value) for sum-like rules."""
    k = rule.kind
    if k in ("sum", "cage", "little_killer", "innie"):
        s = sum(asg.values())
        lo = hi = 0
        for i, m in enumerate(dom):
            if i not in asg:
                ds = list(digits_of(m))
                if not ds:
                    return False
                lo += ds[0]
                hi += ds[-1]
        return s + lo <= rule.total <= s + hi
    if k == "set":
        vs = list(asg.values())
        return len(set(vs)) == len(vs) and (not vs or max(vs) - min(vs) <= len(rule.cells) - 1)
    return True


def _support_search(p, rule, dom, conflicts, node_limit=8000):
    """GAC by one witness search per (cell, value): DFS with forward checking and smallest-domain
    ordering. Values whose search runs out of budget are kept (sound). -> (sup, exact)."""
    n = len(rule.cells)
    nbr = [[] for _ in range(n)]  # i -> [(j, same, tab_i_to_j)] both directions
    for i in range(n):
        for j, same, tab in conflicts[i]:
            a, b = rule.cells[j], rule.cells[i]
            nbr[i].append((j, same, p.rel_ex[b].get(a) if a in p.rel_ex[b] else None))
            nbr[j].append((i, same, tab))
    budget = {"n": 0, "hit": False}

    def dfs(d, asg):
        if budget["n"] > node_limit:
            budget["hit"] = True
            return None
        if len(asg) == n:
            return dict(asg) if rule.check([asg[i] for i in range(n)]) else None
        i, best = -1, 99  # the open cell with the fewest candidates, lowest index on ties
        for k in range(n):
            if k not in asg:
                c = d[k].bit_count()
                if c < best:
                    i, best = k, c
        for v in digits_of(d[i]):
            budget["n"] += 1
            nd = list(d)
            nd[i] = bit(v)
            ok = True
            for j, same, tab in nbr[i]:
                if j in asg:
                    continue
                m = nd[j]
                if same:
                    m &= ~bit(v)
                if tab:
                    m &= ~tab[v]
                if not m:
                    ok = False
                    break
                nd[j] = m
            if not ok:
                continue
            asg[i] = v
            if _feasible(rule, asg, nd):
                r = dfs(nd, asg)
                if r is not None:
                    del asg[i]
                    return r
            del asg[i]
        return None

    sup = [0] * n
    exact = True
    for i in range(n):
        for v in digits_of(dom[i]):
            if sup[i] & bit(v):
                continue
            budget["n"], budget["hit"] = 0, False
            d0 = list(dom)
            d0[i] = bit(v)
            ok = True
            for j, same, tab in nbr[i]:
                m = d0[j]
                if same:
                    m &= ~bit(v)
                if tab:
                    m &= ~tab[v]
                if not m:
                    ok = False
                d0[j] = m
            w = dfs(d0, {}) if ok else None
            if w is not None:
                for k, x in w.items():
                    sup[k] |= bit(x)
            elif budget["hit"]:
                sup[i] |= bit(v)
                exact = False
    return sup, exact


def _rule_dom(st, rule, mental=None):
    out = []
    for c in rule.cells:
        if st.vals[c]:
            out.append(bit(st.vals[c]))
        else:
            out.append(mental[c] if mental is not None else st.cand[c])
    return out


# ------------------------------------------------------- direct exclusions --
def direct_sources(p, st, c, digit=None):
    """Why each digit is excluded at empty cell c from placed digits alone.
    -> list of (kind, mask, info). kinds: 'house' (gi, {digit: cell}), 'neq' (cell, digit),
    'rel' (cell, digit), 'domain', 'cagesum' (gi)."""
    out = []
    for gi in p.groups_of[c]:
        g = p.groups[gi]
        where = {}
        for q in g.cells:
            if st.vals[q] and q != c:
                where[st.vals[q]] = q
        if where:
            m = 0
            for d in where:
                m |= bit(d)
            out.append(("house", m, (gi, where)))
    for q in p.neq[c]:
        if st.vals[q]:
            out.append(("neq", bit(st.vals[q]), (q, st.vals[q])))
    for q in p.nonconsec[c]:
        v = st.vals[q]
        if v:
            m = p.rel_ex[q][c][v]
            if m:
                out.append(("rel", m, (q, v)))
    dom_ex = p.full & ~p.domains[c]
    if dom_ex:
        out.append(("domain", dom_ex, None))
    for gi in p.groups_of[c]:
        g = p.groups[gi]
        if g.total is not None:
            allowed = _cage_direct(p, st, gi)
            m = p.full & ~allowed & ~st.placed_g(gi)
            if m:
                out.append(("cagesum", m, gi))
    return out


def _cage_direct(p, st, gi):
    g = p.groups[gi]
    emp = [c for c in g.cells if not st.vals[c]]
    rem = g.total - sum(st.vals[c] for c in g.cells)
    used = st.placed_g(gi)
    allowed = 0
    pool = [d for d in range(1, p.D + 1) if not used & bit(d)]
    for combo in combinations(pool, len(emp)):
        if sum(combo) == rem:
            for d in combo:
                allowed |= bit(d)
    return allowed


def direct_excl(p, st, c):
    m = 0
    for _, mm, _ in direct_sources(p, st, c):
        m |= mm
    return m


def _source_text(nm, kind, info, digits, c=None):
    """One exclusion source as a phrase."""
    p = nm.p
    ds = sorted(digits)
    if kind == "house":
        gi, where = info
        ds = [d for d in ds if d in where]
        return f"{nm.unit(gi)} already has {nm.digits(ds, 'and')}"
    if kind == "neq":
        q, v = info
        return f"it is a {rel_label(p, q, c) or 'linked'} step from the {v} in {nm.cell(q)}"
    if kind == "rel":
        q, v = info
        lab = rel_label(p, q, c)
        return f"the {v} in {nm.cell(q)} rules out {nm.digits(ds)} via the {lab}"
    if kind == "domain":
        odd = all(d % 2 == 0 for d in ds)
        even = all(d % 2 == 1 for d in ds)
        return (
            "it is an odd (shaded) cell"
            if odd
            else "it is an even (shaded) cell"
            if even
            else f"its cell rule forbids {nm.digits(ds)}"
        )
    if kind == "cagesum":
        gi = info
        return f"{nm.cage(gi, cells=False)} can't use {nm.digits(ds)} with what's left of its total"
    if kind == "lock":
        return info["text"]
    return ""


# -------------------------------------------------------- direct pointing ----
def direct_locks(p, st):
    """Pointing / claiming done in the head (no notes): digit v's directly-possible cells in house
    B all lie in group A -> v excluded from A minus B. -> list of dicts."""
    empties = [c for c in range(p.N) if not st.vals[c]]
    ex = {c: direct_excl(p, st, c) for c in empties}
    out = []
    for bi in p.houses:
        B = p.groups[bi]
        emp = [c for c in B.cells if not st.vals[c]]
        if len(emp) < 3:
            continue
        for v in digits_of(p.full & ~st.placed_g(bi)):
            b = bit(v)
            poss = [c for c in emp if not ex[c] & b]
            if len(poss) < 2:
                continue
            common = set(p.groups_of[poss[0]])
            for c in poss[1:]:
                common &= set(p.groups_of[c])
            common.discard(bi)
            for ai in common:
                tg = [c for c in p.groups[ai].cells if not st.vals[c] and c not in B.cells and not ex[c] & b]
                if tg:
                    out.append({"B": bi, "A": ai, "v": v, "poss": poss, "targets": tg, "rel": False})
            for rel, generic in ((p.nonconsec, True), (p.neq, False)):
                if not rel[poss[0]]:
                    continue
                cr = set(rel[poss[0]])
                for c in poss[1:]:
                    cr &= set(rel[c])
                for x in cr:
                    if st.vals[x] or x in poss:
                        continue
                    rm = p.full
                    if generic:
                        for c in poss:
                            rm &= p.rel_ex[c][x][v]
                    else:
                        rm = b
                    if rm & ~ex[x]:
                        out.append({"B": bi, "A": None, "v": v, "poss": poss, "targets": [x], "rel": True, "mask": rm})
    return out, ex


def _lock_text(nm, lk):
    p = nm.p
    if lk["rel"]:
        x = lk["targets"][0]
        return (
            f"the {lk['v']} of {nm.unit(lk['B'])} must be in {nm.cells(lk['poss'], 'or')}, all of which are "
            f"{rel_label(p, lk['poss'][0], x)}-linked to {nm.cell(x)}"
        )
    return (
        f"the {lk['v']} of {nm.unit(lk['B'])} isn't placed yet but can only go in {nm.cells(lk['poss'], 'or')}, "
        f"so it already occupies {nm.unit(lk['A'])} there"
    )


# ----------------------------------------------------------- mental view -----
def mental_view(p, st, level=3):
    """Direct-mode reasoning without notes: placed-digit exclusions, then relation arcs and
    whole-rule consistency (two rounds), mental pairs/triples and pointing, one more round.
    -> (md masks, reasons {(cell, digit): reason})."""
    N = p.N
    R = rules(p)
    md = [0] * N
    reasons = {}
    empties = [c for c in range(N) if not st.vals[c]]
    for c in range(N):
        md[c] = bit(st.vals[c]) if st.vals[c] else p.full & ~direct_excl(p, st, c)

    def drop(c, keep, why):
        lost = md[c] & ~keep
        if not lost or not md[c] & keep:
            return False
        for d in digits_of(lost):
            reasons.setdefault((c, d), why(d))
        md[c] &= keep
        return True

    def relation_round(depth):
        md0 = list(md)
        changed = False
        for key, rule in R.items():
            if not any(not st.vals[c] for c in rule.cells):
                continue
            dom = [md0[c] for c in rule.cells]
            if any(d == 0 for d in dom):
                continue
            # mirror the engine's direct-mode cap (csolver mental.cpp, CSOLVER_MENTAL_LINE_MAX, default 50): a rule with more
            # consistent fillings (or an unknown number) is not read without notes
            res = enum_rule(p, rule, dom, node_limit=40000, max_count=_MENTAL_LINE_MAX or None, support=False)
            if not res["complete"] or res["count"] == 0:
                continue
            for k, c in enumerate(rule.cells):
                if not st.vals[c]:
                    snap = {q: md0[q] for q in rule.cells if not st.vals[q] and q != c}
                    changed |= drop(
                        c,
                        res["sup"][k],
                        lambda d, rule=rule, snap=snap, res=res: (
                            "rule",
                            key,
                            snap,
                            res["count"],
                            res["sols"][:8],
                            depth,
                        ),
                    )
        for c in empties:
            for q in set(p.nonconsec[c]) | set(p.neq[c]):
                if q == c:
                    continue
                dq = md0[q]
                allowed = 0
                for w in digits_of(dq):
                    allowed |= p.full & ~_rel_ex(p, q, c, w)
                changed |= drop(c, allowed, lambda d, q=q, dq=dq: ("arc", q, dq, depth))
        return changed

    for rnd in range(1, 7):  # the engine does two rounds plus inequality fixpoints; iterate to be safe
        if not relation_round(rnd):
            break
    if level >= 3:
        snap = list(md)
        for hi in p.houses:
            emp = [c for c in p.groups[hi].cells if not st.vals[c] and popcount(snap[c]) <= 3]
            for k in (2, 3):
                for combo in combinations(emp, k):
                    u = 0
                    for c in combo:
                        u |= snap[c]
                    if popcount(u) != k:
                        continue
                    for q in p.groups[hi].cells:
                        if not st.vals[q] and q not in combo:
                            drop(q, p.full & ~u, lambda d, hi=hi, combo=combo, u=u: ("subset", hi, combo, u))
        for bi in p.houses:
            for v in digits_of(p.full & ~st.placed_g(bi)):
                poss = [c for c in p.groups[bi].cells if not st.vals[c] and snap[c] & bit(v)]
                if not 2 <= len(poss) <= 3:
                    continue
                for ai in p.groups_of[poss[0]]:
                    if ai == bi or not all(c in p.groups[ai].cells for c in poss):
                        continue
                    for q in p.groups[ai].cells:
                        if not st.vals[q] and q not in p.groups[bi].cells:
                            drop(
                                q, p.full & ~bit(v), lambda d, bi=bi, ai=ai, poss=poss, v=v: ("point", bi, ai, v, poss)
                            )
        for rnd in range(7, 12):
            if not relation_round(rnd):
                break
    return md, reasons


def _mental_reason_text(nm, c, d, why, st):
    p = nm.p
    kind = why[0]
    if kind == "arc":
        _, q, dq, _ = why
        lab = rel_label(p, q, c) or "linked"
        if not st.vals[q]:
            opts = nm.digits(digits_of(dq))
            return f"its {lab} partner {nm.cell(q)} can only be {opts} at this point, and none of those allows a {d}"
        return f"the {st.vals[q]} in {nm.cell(q)} rules it out through the {lab}"
    if kind == "rule":
        _, key, snap, count, sols, _ = why
        rule = rules(p)[key]
        lk = rule.line_kind or rule.kind
        if lk in ("thermo", "slow_thermo") and c in rule.cells:
            i = rule.cells.index(c)
            strict = lk == "thermo"
            dm = lambda q: bit(st.vals[q]) if st.vals[q] else snap.get(q, p.full)
            if i > 0:
                q = rule.cells[i - 1]
                lo = min(digits_of(dm(q)))
                if d < lo + strict:
                    return (
                        f"it sits above {nm.cell(q)} on the thermometer, which is at least {lo}"
                        if not st.vals[q]
                        else f"it sits above the {st.vals[q]} in {nm.cell(q)} on the thermometer"
                    )
            if i + 1 < len(rule.cells):
                q = rule.cells[i + 1]
                hi = max(digits_of(dm(q)))
                if d > hi - strict:
                    return (
                        f"it sits below {nm.cell(q)} on the thermometer, which is at most {hi}"
                        if not st.vals[q]
                        else f"it sits below the {st.vals[q]} in {nm.cell(q)} on the thermometer"
                    )
        if lk == "cage" and len(rule.cells) == 2:
            o = rule.cells[0] if rule.cells[1] == c else rule.cells[1]
            need = rule.total - d
            return f"{rule.label} would then need {need} in {nm.cell(o)}, which isn't possible there"
        if count and sols and count <= 3 and len(rule.cells) <= 6:
            fills = "; ".join("-".join(map(str, x)) for x in sols[:3])
            return f"{rule.label} can only be filled as {fills} (in order {nm.span(rule.cells)})"
        return f"no valid way to fill {rule.label} puts a {d} there"
    if kind == "subset":
        _, hi, combo, u = why
        return (
            f"{nm.cells(combo)} can only hold {nm.digits(digits_of(u), 'and')} between them, so the "
            f"{d} of {nm.unit(hi)} is already spoken for"
        )
    if kind == "point":
        _, bi, ai, v, poss = why
        return f"the {v} of {nm.unit(bi)} is stuck in {nm.cells(poss, 'or')}, inside {nm.unit(ai)}"
    return "it is ruled out"
