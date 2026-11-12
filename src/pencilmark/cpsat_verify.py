"""Uniqueness checks with OR-Tools CP-SAT when installed (pip install "pencilmark[verify]"), else the engine's
exhaustive C++ search.

solutions(p, limit=2, time_limit=60) -> list of solutions (each a list of digits, len p.N),
                                         or None if undecided: the puzzle uses a rule the checker does not model,
                                         or the search hit its node / time limit.
decide() (used by rate, solve and count_solutions) runs the C++ search (cbackend.brute_solve) first, which settles most
puzzles in microseconds. With OR-Tools installed that first search gets QUICK_NODES and CP-SAT takes over when it runs
out (a sparse killer on a big board: 0.4 s instead of 27 s); without it, or when CP-SAT cannot decide, the C++ search
gets the full NODE_LIMIT. CP-SAT is independent of the engine's propagation.
Pair relations are encoded generically as allowed-pair tables from model.RELATIONS, so any relation kind works.
"""

import logging
import os
import time

from . import model as M

_log = logging.getLogger(__name__)
NODE_LIMIT = 20_000_000
QUICK_NODES = 100_000  # the C++ search's share before CP-SAT, when OR-Tools is installed (about 0.3 s)
QUICK_SECONDS = 2.0  # the quick C++ pass's time limit when CP-SAT can take over (2026-11-07: a global-entropy puzzle
# spent 60 s in 100,000 nodes; CP-SAT settles it in 0.5 s)

# constraint types the checker models (the same set the CP-SAT model below encodes); anything else -> undecided
_CON_TYPES = {
    "line",
    "clone",
    "sum",
    "little_killer",
    "arrow",
    "equal_sum",
    "between",
    "table",
    "count",
    "digit_set",
    "counting_circles",
    "distinct_count",
    "contains",
    "first_seen",
    "xsum",
    "skyscraper",
    "sandwich",
    "chaos",
    "region_border",
    "same_region",
    "yin_yang",
    "expr",
}
CHAOS_TYPES = ("chaos", "region_border", "same_region")


def has_shading(p):
    """True if the puzzle has a shading layer (yin-yang, docs/formats/rules/whole-board-rules.mdx)"""
    return any(c.get("type") == "yin_yang" for c in getattr(p, "constraints", ()))


def _add_yin_yang(m, p, shading):
    """yin-yang: a shading Boolean per cell; no 2x2 of one color; each color orthogonally connected (each of its cells
    but its first, in reading order, has a neighbor of its color one step closer to that first cell); given shaded /
    unshaded cells. shading (dict) receives the Boolean per cell, for custom rules reading shaded()."""
    for con in p.constraints:
        if con.get("type") != "yin_yang":
            continue
        cells = sorted(range(p.N), key=lambda c: p.coords[c])
        idx = {p.coords[c]: c for c in cells}
        sh = {c: m.NewBoolVar("") for c in cells}
        shading.update(sh)
        for c in con.get("shaded", ()):
            m.Add(sh[c] == 1)
        for c in con.get("unshaded", ()):
            m.Add(sh[c] == 0)
        for r0, c0 in (p.coords[c] for c in cells):
            win = [idx.get((r0 + dr, c0 + dc)) for dr in (0, 1) for dc in (0, 1)]
            if None not in win:
                m.Add(sum(sh[c] for c in win) >= 1)
                m.Add(sum(sh[c] for c in win) <= 3)
        for colour in (1, 0):
            own = {c: (sh[c] if colour else sh[c].Not()) for c in cells}
            first = {c: m.NewBoolVar("") for c in cells}
            m.AddExactlyOne(first.values())
            for i, c in enumerate(cells):
                m.AddImplication(first[c], own[c])
                for c2 in cells[:i]:
                    m.AddImplication(first[c], own[c2].Not())
            dist = {c: m.NewIntVar(0, len(cells) - 1, "") for c in cells}
            for c in cells:
                r0, c0 = p.coords[c]
                m.Add(dist[c] == 0).OnlyEnforceIf(first[c])
                opts = [first[c], own[c].Not()]
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    j = idx.get((r0 + dr, c0 + dc))
                    if j is None:
                        continue
                    o = m.NewBoolVar("")
                    m.AddImplication(o, own[c])
                    m.AddImplication(o, own[j])
                    m.Add(dist[j] == dist[c] - 1).OnlyEnforceIf(o)
                    opts.append(o)
                m.AddBoolOr(opts)


def has_chaos(p):
    """True if the puzzle has regions to find (docs/formats/rules/houses-and-regions.mdx 6.3)"""
    return any(c.get("type") == "chaos" for c in getattr(p, "constraints", ()))


def _add_chaos(m, x, p):
    """the regions to find of every chaos constraint: a region label per cell (one Boolean per label); every label
    covers D cells, holds each digit once and is connected (each cell but the region's first, in reading order, has a
    neighbor of its region one step closer to it); label k's first cell precedes label k + 1's (symmetry);
    region_border pairs differ in label, same_region cells share one"""
    D = p.D
    lab = {}
    for con in p.constraints:
        if con.get("type") != "chaos":
            continue
        cells = sorted(con["cells"], key=lambda c: p.coords[c])
        idx = {p.coords[c]: c for c in cells}
        L = {c: [m.NewBoolVar("") for _ in range(D)] for c in cells}
        lab.update(L)
        dig = {c: [m.NewBoolVar("") for _ in range(D)] for c in cells}
        for c in cells:
            m.AddExactlyOne(L[c])
            m.AddExactlyOne(dig[c])
            for v in range(D):
                m.Add(x[c] == v + 1).OnlyEnforceIf(dig[c][v])
        for k in range(D):
            m.Add(sum(L[c][k] for c in cells) == D)
            for v in range(D):
                both = []
                for c in cells:
                    b = m.NewBoolVar("")
                    m.AddBoolAnd([L[c][k], dig[c][v]]).OnlyEnforceIf(b)
                    m.AddBoolOr([L[c][k].Not(), dig[c][v].Not()]).OnlyEnforceIf(b.Not())
                    both.append(b)
                m.AddExactlyOne(both)
        first = {c: [m.NewBoolVar("") for _ in range(D)] for c in cells}
        for k in range(D):
            m.AddExactlyOne(first[c][k] for c in cells)
            for i, c in enumerate(cells):
                m.AddImplication(first[c][k], L[c][k])
                for c2 in cells[:i]:
                    m.AddImplication(first[c][k], L[c2][k].Not())
        order = [m.NewIntVar(0, len(cells) - 1, "") for _ in range(D)]
        for k in range(D):
            m.Add(order[k] == sum(i * first[c][k] for i, c in enumerate(cells)))
            if k:
                m.Add(order[k - 1] < order[k])
        dist = {c: m.NewIntVar(0, D - 1, "") for c in cells}
        for c in cells:
            r0, c0 = p.coords[c]
            root = m.NewBoolVar("")
            m.AddBoolOr([first[c][k] for k in range(D)]).OnlyEnforceIf(root)
            for k in range(D):
                m.AddImplication(first[c][k], root)
            m.Add(dist[c] == 0).OnlyEnforceIf(root)
            m.Add(dist[c] >= 1).OnlyEnforceIf(root.Not())
            opts = [root]
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                j = idx.get((r0 + dr, c0 + dc))
                if j is None:
                    continue
                for k in range(D):
                    o = m.NewBoolVar("")
                    m.AddImplication(o, L[c][k])
                    m.AddImplication(o, L[j][k])
                    m.Add(dist[j] == dist[c] - 1).OnlyEnforceIf(o)
                    opts.append(o)
            m.AddBoolOr(opts)
    for con in p.constraints:
        t = con.get("type")
        if t == "region_border":
            a, b = con["cells"]
            for k in range(D):
                m.AddBoolOr([lab[a][k].Not(), lab[b][k].Not()])
        elif t == "same_region":
            c0 = con["cells"][0]
            for c in con["cells"][1:]:
                for k in range(D):
                    m.Add(lab[c][k] == lab[c0][k])
    return lab


class _Unmodelled(Exception):
    """a custom rule uses a part of the language the CP-SAT model does not encode"""


class _Cell:  # a cell of the rule (its variable index), until it is used as a number or by shaded()
    __slots__ = ("var",)

    def __init__(self, var):
        self.var = var


class _Item:  # an element of a comprehension: its value, and the condition it exists under (None: always)
    __slots__ = ("value", "cond")

    def __init__(self, value, cond):
        self.value, self.cond = value, cond


class _Maybe:  # a number that may be ABSENT (custom.py): its value where defined, and the Boolean "defined"
    __slots__ = ("value", "defined", "lo", "hi")

    def __init__(self, value, defined, lo=None, hi=None):
        self.value, self.defined, self.lo, self.hi = value, defined, lo, hi


class _Fn:  # a lambda: its parameter slots, body and the scope it was made in
    __slots__ = ("params", "body", "scope")

    def __init__(self, params, body, scope):
        self.params, self.body, self.scope = params, body, scope


class _AuxVars:
    """the file's unknowns and layers as CP-SAT variables over their values, made when a rule first reads one (an
    unknown by index; a layer's value at a board cell, fixed where the file gives it)"""

    def __init__(self, m, aux, n_cells):
        self.m, self.aux, self.N, self.v = m, aux, n_cells, {}

    def _make(self, key, values):
        from ortools.sat.python import cp_model

        if key not in self.v:
            self.v[key] = self.m.NewIntVarFromDomain(cp_model.Domain.FromValues(sorted(set(values))), "")
        return self.v[key]

    def var(self, i):
        return self._make(("u", i), self.aux["unknowns"][i]["values"])

    def layer(self, li, cell):
        L = self.aux["layers"][li]
        g = L["given"].get(cell)
        return self._make(("l", li, cell), [g] if g is not None else L["values"])


class _ExprCP:
    """a custom rule's expression (its IR, custom.to_ir) as CP-SAT constraints: constants, linear expressions and
    Booleans; comprehensions over cell lists (with an optional condition), if-then-else, comparisons, and / or / not,
    + - and products with a constant, sum, count, len, abs, odd, even, num, all, any, shaded(), region() (the label
    Booleans of the regions to find), take_while with a lambda, L[i] with a variable i, position(L, f), defined(x),
    ranges with variable ends (over known bounds). A value that may be ABSENT is a _Maybe: comparisons with it hold
    only where it is defined, arithmetic carries the definedness. Anything else raises _Unmodelled (the model is then
    unsupported and the C++ search decides)."""

    BIG = 10_000

    def __init__(self, m, con, x, shading, labels=None, aux=None, D=9):
        from .rules import custom as CU

        self.m, self.x, self.sh, self.CU = m, x, shading, CU
        self.aux = aux  # the file's unknowns / layers (_AuxVars), or None
        self.lab = labels or {}  # cell -> its D label Booleans (regions to find)
        self.cells, self.lists, self.ir = con["cells"], con["lists"], con["ir"]
        self.pos, self.box = con.get("pos") or [], con.get("box") or (3, 3)  # per variable [row, col]; box size
        self.op = {i: o for o, i in CU.OPCODE.items()}
        self.fn = {i: f for f, i in CU.FNCODE.items()}
        self.D = D

    def holds(self):
        v = self.ev(self.ir, {})
        if isinstance(v, bool):
            return int(v)
        return v

    # values: int, bool, a CP-SAT linear expression / Boolean, _Cell, or a list of values / _Item
    def num(self, v):
        if isinstance(v, _Cell):
            return self.x[self.cells[v.var]]
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, _Maybe):
            raise _Unmodelled("a value that may be absent, here")
        return v

    def split(self, *vs):
        """values that may be absent -> (plain values, the Boolean "all defined": True when none may be absent)"""
        out, defs = [], []
        for v in vs:
            if isinstance(v, _Maybe):
                defs.append(v.defined)
                v = v.value
            out.append(v)
        return out, (self.logic("and", defs) if defs else True)

    def bounds(self, v):
        """constant bounds of a value, where known: a constant, a cell (1..D), a _Maybe made with bounds, +- constant"""
        if isinstance(v, bool):
            return int(v), int(v)
        if isinstance(v, int):
            return v, v
        if isinstance(v, _Cell):
            return 1, self.D
        if isinstance(v, _Maybe) and v.lo is not None:
            return v.lo, v.hi
        return None

    def member(self, v, values):
        """a Boolean: the expression v takes one of the constant values (v within -BIG..BIG)"""
        from ortools.sat.python import cp_model

        w = self.m.NewIntVar(-self.BIG, self.BIG, "")
        self.m.Add(w == v)
        dom = cp_model.Domain.FromValues(sorted(set(values)))
        b = self.m.NewBoolVar("")
        self.m.AddLinearExpressionInDomain(w, dom).OnlyEnforceIf(b)
        self.m.AddLinearExpressionInDomain(w, dom.complement().intersection_with(
            cp_model.Domain(-self.BIG, self.BIG))).OnlyEnforceIf(b.Not())  # fmt: skip
        return b

    @staticmethod
    def is_cond(v):
        """a condition (a Python or CP-SAT Boolean), not a number or a cell"""
        return isinstance(v, bool) or getattr(v, "is_boolean", None) is True or type(v).__name__ == "NotBooleanVariable"

    def boolean(self, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, _Cell, list)):
            raise _Unmodelled("a number where a condition is needed")
        return v

    def compare(self, o, a, b):
        (a, b), d = self.split(a, b)
        if d is not True:  # with ABSENT a comparison is false (!= too)
            return self.logic("and", [d, self.compare(o, a, b)])
        a, b = self.num(a), self.num(b)
        if isinstance(a, int) and isinstance(b, int):
            return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[o]
        t = self.m.NewBoolVar("")
        yes = {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[o]
        no = {"==": a != b, "!=": a == b, "<": a >= b, "<=": a > b, ">": a <= b, ">=": a < b}[o]
        self.m.Add(yes).OnlyEnforceIf(t)
        self.m.Add(no).OnlyEnforceIf(t.Not())
        return t

    def ite(self, c, a, b):
        c = self.boolean(c)
        if isinstance(c, bool):
            return a if c else b
        a, b = self.num(a), self.num(b)
        v = self.m.NewIntVar(-self.BIG, self.BIG, "")
        self.m.Add(v == a).OnlyEnforceIf(c)
        self.m.Add(v == b).OnlyEnforceIf(c.Not())
        return v

    def logic(self, o, vals):
        vals = [self.boolean(v) for v in vals]
        if o == "not":
            v = vals[0]
            return (not v) if isinstance(v, bool) else v.Not()
        const = [v for v in vals if isinstance(v, bool)]
        if o == "and" and False in const or o == "or" and True in const:
            return o == "or"
        vs = [v for v in vals if not isinstance(v, bool)]
        if not vs:
            return o == "and"
        t = self.m.NewBoolVar("")
        if o == "and":
            self.m.AddBoolAnd(vs).OnlyEnforceIf(t)
            self.m.AddBoolOr([v.Not() for v in vs]).OnlyEnforceIf(t.Not())
        else:
            self.m.AddBoolOr(vs).OnlyEnforceIf(t)
            self.m.AddBoolAnd([v.Not() for v in vs]).OnlyEnforceIf(t.Not())
        return t

    def items(self, v):  # a list value -> [_Item]
        if isinstance(v, list):
            return [it if isinstance(it, _Item) else _Item(it, None) for it in v]
        if isinstance(v, _Cell):
            return [_Item(v, None)]
        raise _Unmodelled("a list was expected")

    def ev(self, e, scope):
        o = self.op[e[0]]
        a = e[1:]
        if o == "num":
            return a[0]
        if o == "bool":
            return bool(a[0])
        if o == "cell":
            return _Cell(a[0])
        if o == "cells":
            L = self.lists[a[0]]
            nest = lambda y: [nest(z) for z in y] if isinstance(y, list) else _Cell(y)
            return nest(L)
        if o == "slot":
            if a[0] not in scope:
                raise _Unmodelled("a function value")
            return scope[a[0]]
        if o == "list":
            return [self.ev(y, scope) for y in a]
        if o == "index":  # L[i] (1-based); a variable i picks under indicators, outside the list the value is absent
            its = self.items(self.ev(a[0], scope))
            (i,), di = self.split(self.ev(a[1], scope))
            i = self.num(i)
            if isinstance(i, int) and di is True:
                if not 1 <= i <= len(its):
                    return _Maybe(0, False, 0, 0)  # outside the list: ABSENT
                if its[i - 1].cond is not None:
                    raise _Unmodelled("index")
                return its[i - 1].value
            if not its or any(it.cond is not None for it in its):
                raise _Unmodelled("a variable index into a filtered list")
            vals = [self.num(it.value) for it in its]
            v = self.m.NewIntVar(-self.BIG, self.BIG, "")
            ins = []
            for k, w in enumerate(vals, 1):
                e = self.compare("==", i, k)
                if e is False:
                    continue
                if e is True:
                    return its[k - 1].value if di is True else _Maybe(its[k - 1].value, di)
                self.m.Add(v == w).OnlyEnforceIf(e)
                ins.append(e)
            if not ins:
                raise _Unmodelled("index")
            d = self.logic("or", ins)
            if di is not True:
                d = self.logic("and", [d, di])
            lo = [self.bounds(it.value) for it in its]
            return _Maybe(v, d, *((min(x[0] for x in lo), max(x[1] for x in lo)) if all(lo) else (None, None)))
        if o == "range":  # {a..b}: constant ends, or ends of known bounds (each element under "lo <= k <= hi")
            ends = [self.ev(a[0], scope), self.ev(a[1], scope)]
            (lo, hi), d = self.split(*ends)
            lo, hi = self.num(lo), self.num(hi)
            if isinstance(lo, int) and isinstance(hi, int) and d is True:
                return list(range(lo, hi + 1))
            bl, bh = self.bounds(ends[0]), self.bounds(ends[1])
            if bl is None or bh is None or bh[1] - bl[0] > 200:
                raise _Unmodelled("a range with a variable end")
            out = []
            for k in range(bl[0], bh[1] + 1):
                c = self.logic("and", [d, self.compare("<=", lo, k), self.compare("<=", k, hi)])
                if c is not False:
                    out.append(_Item(k, None if c is True else c))
            return out
        if o == "comp":
            slot, src, body, cond = a
            out = []
            for item in self.items(self.ev(src, scope)):
                it, c0 = item.value, item.cond
                inner = {**scope, slot: it}
                c = None if self.op[cond[0]] == "none" else self.boolean(self.ev(cond, inner))
                if c is False:
                    continue
                c = None if c is True else c
                if c0 is not None:
                    c = c0 if c is None else self.logic("and", [c0, c])
                out.append(_Item(self.ev(body, inner), c))
            return out
        if o == "let":
            return self.ev(a[2], {**scope, a[0]: self.ev(a[1], scope)})
        if o == "letfn":  # let f(a, b) = body; rest
            fslot, ps, body, rest = a
            fn = _Fn(ps, body, dict(scope))
            fn.scope[fslot] = fn
            return self.ev(rest, {**scope, fslot: fn})
        if o == "callfn":
            fn = scope.get(a[0])
            if not isinstance(fn, _Fn) or len(fn.params) != len(a) - 1:
                raise _Unmodelled("callfn")
            args = [self.ev(y, scope) for y in a[1:]]
            return self.ev(fn.body, {**fn.scope, **dict(zip(fn.params, args))})
        if o == "slice":  # L[i:j] with constant ends (1-based, clamped as the language does)
            its = self.items(self.ev(a[0], scope))
            i, j = self.num(self.ev(a[1], scope)), self.num(self.ev(a[2], scope))
            if not (isinstance(i, int) and isinstance(j, int)):
                raise _Unmodelled("slice")
            i, j = max(i, 1), min(j, len(its))
            return its[i - 1 : j] if i <= j else []
        if o in ("div", "mod"):  # by a positive constant: v = k * q + r, 0 <= r < k (floor division)
            v, k = self.num(self.ev(a[0], scope)), self.num(self.ev(a[1], scope))
            if isinstance(v, int) and isinstance(k, int) and k:
                return v // k if o == "div" else v % k
            if not (isinstance(k, int) and k > 0):
                raise _Unmodelled(o)
            q, r = self.m.NewIntVar(-self.BIG, self.BIG, ""), self.m.NewIntVar(0, k - 1, "")
            self.m.Add(v == k * q + r)
            return q if o == "div" else r
        if o == "if":
            return self.ite(self.ev(a[0], scope), self.ev(a[1], scope), self.ev(a[2], scope))
        if o in ("and", "or", "not"):
            return self.logic(o, [self.ev(y, scope) for y in a])
        if o in ("==", "!=", "<", "<=", ">", ">="):
            return self.compare(o, self.ev(a[0], scope), self.ev(a[1], scope))
        if o in ("in", "not in"):  # membership: a domain for constant lists, else one of the equalities
            v, its = self.num(self.ev(a[0], scope)), self.items(self.ev(a[1], scope))
            if any(it.cond is not None for it in its):
                raise _Unmodelled("in over a filtered list")
            vals = [self.num(it.value) for it in its]
            if all(isinstance(w, int) for w in vals):
                b = v in vals if isinstance(v, int) else self.member(v, vals)
            else:
                b = self.logic("or", [self.compare("==", v, w) for w in vals]) if vals else False
            return self.logic("not", [b]) if o == "not in" else b
        if o in ("+", "-", "*", "neg"):  # a value that may be absent carries its definedness
            vs = [self.ev(y, scope) for y in a]
            if any(isinstance(v, _Maybe) for v in vs):
                bs = [self.bounds(v) for v in vs]
                plain, d = self.split(*vs)
                v = self.arith(o, [self.num(w) for w in plain])
                lo = hi = None
                if all(bs) and o in ("+", "-", "neg"):
                    if o == "neg":
                        lo, hi = -bs[0][1], -bs[0][0]
                    else:
                        lo = bs[0][0] + (bs[1][0] if o == "+" else -bs[1][1])
                        hi = bs[0][1] + (bs[1][1] if o == "+" else -bs[1][0])
                return _Maybe(v, d, lo, hi)
            return self.arith(o, [self.num(v) for v in vs])
        if o == "aux":  # an unknown: one CP variable per model over its values
            if self.aux is None:
                raise _Unmodelled("aux")
            return self.aux.var(a[0])
        if o == "auxcell":  # a layer's value at a cell
            v = self.ev(a[1], scope)
            if self.aux is None or not isinstance(v, _Cell):
                raise _Unmodelled("auxcell")
            return self.aux.layer(a[0], self.cells[v.var])
        if o == "lambda":
            return _Fn(a[0], a[1], scope)
        if o == "call":
            return self.call(self.fn[a[0]], [self.ev(y, scope) for y in a[1:]])
        raise _Unmodelled(o)

    def arith(self, o, vs):
        if o == "neg":
            return -vs[0]
        l, r = vs
        if o == "+":
            return l + r
        if o == "-":
            return l - r
        if not (isinstance(l, int) or isinstance(r, int)):  # two variables: a product variable
            t = self.m.NewIntVar(-(10**12), 10**12, "")
            self.m.AddMultiplicationEquality(t, [l, r])
            return t
        return l * r

    def take_while(self, L, f):
        """the leading elements meeting f: each kept under "every element so far met f" (a Boolean chain)"""
        if not isinstance(f, _Fn) or len(f.params) != 1:
            raise _Unmodelled("take_while without a one-parameter lambda")
        out, running = [], True
        for item in self.items(L):
            if item.cond is not None:
                raise _Unmodelled("take_while over a filtered list")
            ok = self.boolean(self.ev(f.body, {**f.scope, f.params[0]: item.value}))
            running = self.logic("and", [running, ok])
            if running is False:
                break
            out.append(_Item(item.value, None if running is True else running))
        return out

    def call(self, f, args):
        if f == "region":
            v = args[0]
            if not isinstance(v, _Cell) or self.cells[v.var] not in self.lab:
                raise _Unmodelled("region() without regions to find")
            return sum((k + 1) * b for k, b in enumerate(self.lab[self.cells[v.var]]))
        if f == "take_while":
            return self.take_while(args[0], args[1])
        if f == "defined":
            return args[0].defined if isinstance(args[0], _Maybe) else True
        if f == "position":  # the first element meeting f (1-based), absent if none: "first k" Booleans
            fn = args[1]
            if not isinstance(fn, _Fn) or len(fn.params) != 1:
                raise _Unmodelled("position without a one-parameter lambda")
            its = self.items(args[0])
            if any(it.cond is not None for it in its):
                raise _Unmodelled("position over a filtered list")
            none_yet, terms, firsts = True, 0, []
            for k, it in enumerate(its, 1):
                b = self.boolean(self.ev(fn.body, {**fn.scope, fn.params[0]: it.value}))
                first = self.logic("and", [none_yet, b])
                if first is True:
                    return k if not firsts else _Maybe(terms + k, True, 1, len(its))
                if first is not False:
                    firsts.append(first)
                    terms = terms + k * first
                none_yet = self.logic("and", [none_yet, self.logic("not", [b])])
                if none_yet is False:
                    break
            if not firsts:
                raise _Unmodelled("position: never found")
            return _Maybe(terms, self.logic("or", firsts), 1, len(its))
        if f == "shaded":
            v = args[0]
            if not isinstance(v, _Cell) or self.cells[v.var] not in self.sh:
                raise _Unmodelled("shaded() without shading")
            return self.sh[self.cells[v.var]]
        if f == "count" and not any(self.is_cond(it.value) for it in self.items(args[0])):
            # numbers / cells: count() counts the elements (custom.py), each under its condition
            return sum(1 if it.cond is None else self.ite(it.cond, 1, 0) for it in self.items(args[0]))
        if f == "reverse":  # of an unconditional list
            its = self.items(args[0])
            if any(it.cond is not None for it in its):
                raise _Unmodelled("reverse over a filtered list")
            return [it.value for it in reversed(its)]
        if f == "sum" and any(isinstance(it.value, _Maybe) for it in self.items(args[0])):
            # an element that may be ABSENT: the sum is absent where a present element (its condition holds) is
            total, defs = 0, []
            for item in self.items(args[0]):
                (val,), d = self.split(item.value)
                term = self.num(val)
                if item.cond is not None:
                    term = self.ite(item.cond, term, 0)
                    d = d if d is True else self.logic("or", [self.logic("not", [item.cond]), d])
                total = total + term
                defs.append(d)
            d = self.logic("and", defs)
            return total if d is True else _Maybe(total, d)
        if f in ("sum", "count", "len"):
            total = 0
            for item in self.items(args[0]):
                val, c = item.value, item.cond
                term = 1 if f in ("count", "len") else self.num(val)
                if f == "count":
                    term = int(self.boolean(val)) if isinstance(self.boolean(val), bool) else self.boolean(val)
                if c is not None:
                    term = self.ite(c, term, 0)
                total = total + term
            return total
        if f in ("all", "any"):
            vals = []
            for item in self.items(args[0]):
                val, c = item.value, item.cond
                b = self.boolean(val)
                if c is not None:  # all: c -> b ; any: c and b
                    b = self.logic("or", [self.logic("not", [c]), b]) if f == "all" else self.logic("and", [c, b])
                vals.append(b)
            return self.logic("and" if f == "all" else "or", vals) if vals else f == "all"
        if f in ("odd", "even"):
            v = self.num(args[0])
            if isinstance(v, int):
                return (v % 2 == 1) == (f == "odd")
            r = self.m.NewIntVar(0, 1, "")
            q = self.m.NewIntVar(-self.BIG, self.BIG, "")
            self.m.Add(v == 2 * q + r)
            return self.compare("==", r, 1 if f == "odd" else 0)
        if f == "abs":
            v = self.num(args[0])
            if isinstance(v, int):
                return abs(v)
            t = self.m.NewIntVar(0, self.BIG, "")
            w = self.m.NewIntVar(-self.BIG, self.BIG, "")
            self.m.Add(w == v)
            self.m.AddAbsEquality(t, w)
            return t
        if f == "num":
            b = self.boolean(args[0])
            return int(b) if isinstance(b, bool) else b
        if f in ("row", "col", "box"):  # a cell's position: constants of the rule (custom.py, 1-based)
            v = args[0]
            if not isinstance(v, _Cell):
                raise _Unmodelled(f + "() of a value")
            r, c = self.pos[v.var]
            bh, bw = self.box
            return {"row": r, "col": c, "box": (r - 1) // bh * bh + (c - 1) // bw + 1}[f]
        if f in ("min", "max"):  # of an unconditional list, or of several arguments
            its = self.items(args[0]) if len(args) == 1 else [_Item(x, None) for x in args]
            if not its or any(it.cond is not None for it in its):
                raise _Unmodelled(f + " over a filtered list")
            vals = [self.num(it.value) for it in its]
            if all(isinstance(w, int) for w in vals):
                return min(vals) if f == "min" else max(vals)
            t = self.m.NewIntVar(-self.BIG, self.BIG, "")
            (self.m.AddMinEquality if f == "min" else self.m.AddMaxEquality)(t, vals)
            return t
        if f == "prime":  # membership in the primes up to BIG
            v = self.num(args[0])
            if isinstance(v, int):
                return self.CU.is_prime(v)
            return self.member(v, [n for n in range(2, self.BIG + 1) if self.CU.is_prime(n)])
        if f == "all_different":  # pairwise different (an unconditional list)
            its = self.items(args[0])
            if any(it.cond is not None for it in its):
                raise _Unmodelled("all_different over a filtered list")
            vs = [it.value for it in its]
            return self.logic("and", [self.compare("!=", vs[i], vs[j]) for i in range(len(vs))
                                      for j in range(i + 1, len(vs))]) if len(vs) > 1 else True  # fmt: skip
        if f == "product":  # of an unconditional list: constants fold, two unknown factors make a product variable
            its = self.items(args[0])
            if any(it.cond is not None for it in its):
                raise _Unmodelled("product over a filtered list")
            acc = 1
            for it in its:
                v = self.num(it.value)
                if isinstance(v, int) or isinstance(acc, int):
                    acc = acc * v
                    continue
                t = self.m.NewIntVar(-(10**12), 10**12, "")
                self.m.AddMultiplicationEquality(t, [acc, v])
                acc = t
            return acc
        raise _Unmodelled(f)


_HAVE = None


def have_ortools():
    """True if OR-Tools CP-SAT can be imported (checked once)."""
    global _HAVE
    if _HAVE is not None:
        return _HAVE
    try:
        import ortools.sat.python.cp_model  # noqa: F401

        _HAVE = True
    except ImportError:
        _HAVE = False
    return _HAVE


def supported(p):
    """True if every relation / constraint of the finalized puzzle is one the checker models."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    for rel in p.relations:
        if rel[0] != "neq" and M.RELATIONS.get(rel[0]) is None:
            return False
    for con in p.constraints:
        t = con.get("type")
        if t == "set":
            if con.get("kind") != "consecutive":
                return False
        elif t not in _CON_TYPES:
            return False
    return True


def _engine(p, limit, node_limit, time_limit=None):
    """the C++ exhaustive search -> (solutions, complete). time_limit bounds it when no caller deadline (rate()'s
    max_seconds) is in force: nodes of counting rules cost milliseconds, so the node limit alone took hours"""
    import time

    from . import cbackend as CB
    from .export import _OUTER_END

    has = time_limit is not None and hasattr(CB._C, "deadline_on")
    own = has and not CB._C.deadline_on()
    # under a caller's deadline (rate(max_seconds=...)) the pass still keeps to its own limit, then the caller's
    # deadline is put back (2026-11-08: the quick pass took the whole 600 s budget on a zero-given global-entropy
    # puzzle that CP-SAT settles in half a second)
    outer = _OUTER_END[0] if has and not own else None
    if own:
        CB._C.set_deadline(float(time_limit))
    elif outer is not None:
        CB._C.set_deadline(max(1e-3, min(float(time_limit), outer - time.time())))
    try:
        r = CB.brute_solve(p, limit=limit, node_limit=node_limit)
    finally:
        if own:
            CB._C.set_deadline(0.0)
        elif outer is not None:
            CB._C.set_deadline(max(1e-3, outer - time.time()))
    return [list(x) for x in r], r.complete


def _digits(mask, D):
    return [v for v in range(1, D + 1) if mask >> (v - 1) & 1]


def build_model(p):
    from ortools.sat.python import cp_model

    if not hasattr(p, "groups_of"):
        p.finalize()
    D, N = p.D, p.N
    m = cp_model.CpModel()
    x = []
    for c in range(N):
        dom = _digits(p.domains[c], D)
        if c in p.givens:  # a given outside its cell's domain is a contradiction, not an override
            dom = [v for v in dom if v == p.givens[c]]
        if not dom:  # empty domain: infeasible (0 solutions), not "unsupported"
            m.AddBoolOr([])
            dom = [1]
        x.append(m.NewIntVarFromDomain(cp_model.Domain.FromValues(dom), f"x{c}"))
    for g in p.groups:
        cells = [x[c] for c in g.cells]
        # every Group is all-different (model docstring; the engine puts all group cells in peers),
        # including incomplete non-cage groups such as irregular jigsaw regions
        if len(cells) > 1:
            m.AddAllDifferent(cells)
        if g.total is not None:
            m.Add(sum(cells) == g.total)
    # pair relations -> allowed tables (generic), merged per ordered pair
    tables = {}
    for rel in p.relations:
        kind, a, b, args = rel[0], rel[1], rel[2], rel[3:]
        if kind == "neq":
            m.Add(x[a] != x[b])
            continue
        f = M.RELATIONS.get(kind)
        if f is None:
            return None, None
        allowed = {(v, w) for v in range(1, D + 1) for w in range(1, D + 1) if f(v, w, *args)}
        key = (a, b)
        tables[key] = tables[key] & allowed if key in tables else allowed
    for (a, b), allowed in tables.items():
        if not allowed:  # unsatisfiable relation: infeasible, not "unsupported"
            m.AddBoolOr([])
            continue
        m.AddAllowedAssignments([x[a], x[b]], sorted(allowed))
    for con in p.constraints:
        t = con.get("type")
        if t in ("line", "clone", "yin_yang", "expr") or t in CHAOS_TYPES:
            continue  # compiled into relations / n-ary constraints by finalize(); chaos: _add_chaos below
        cells = [x[c] for c in con.get("cells", [])]
        off = int(con.get("offset") or 0)
        if off and t in ("sum", "little_killer", "equal_sum"):
            cells = [c - off for c in cells]
        if t in ("sum", "little_killer"):
            tot = con["total"]
            if isinstance(tot, (list, tuple)):  # incomplete clue: the total is one of these
                m.AddLinearExpressionInDomain(sum(cells), cp_model.Domain.FromValues(sorted(set(int(v) for v in tot))))
            else:
                m.Add(sum(cells) == tot)
            if con.get("distinct"):
                m.AddAllDifferent(cells)
        elif t == "arrow":
            circ = con["circle"]
            num = sum(x[c] * (10 ** (len(circ) - 1 - i)) for i, c in enumerate(circ))
            m.Add(num == sum(x[c] for c in con["line"]))
        elif t == "equal_sum":
            segs = [sum(x[c] - off for c in s) for s in con["segments"]]
            for s in segs[1:]:
                m.Add(s == segs[0])
        elif t == "set" and con.get("kind") == "consecutive":
            m.AddAllDifferent(cells)
            mx = m.NewIntVar(1, D, "")
            mn = m.NewIntVar(1, D, "")
            m.AddMaxEquality(mx, cells)
            m.AddMinEquality(mn, cells)
            m.Add(mx - mn == len(cells) - 1)
        elif t == "between":
            a, b = cells[0], cells[-1]
            lo = m.NewIntVar(1, D, "")
            hi = m.NewIntVar(1, D, "")
            m.AddMinEquality(lo, [a, b])
            m.AddMaxEquality(hi, [a, b])
            for c in cells[1:-1]:
                m.Add(c > lo)
                m.Add(c < hi)
        elif t == "table":
            m.AddAllowedAssignments(cells, [tuple(r) for r in con["allowed"]])
        elif t == "count":
            for v in range(1, D + 1):
                k = con["each"] if "each" in con else con.get("digits", {}).get(v, con.get("digits", {}).get(str(v)))
                if k is None:
                    continue
                bs = []
                for c in cells:
                    b = m.NewBoolVar("")
                    m.Add(c == v).OnlyEnforceIf(b)
                    m.Add(c != v).OnlyEnforceIf(b.Not())
                    bs.append(b)
                m.Add(sum(bs) == int(k))
        elif t == "digit_set":  # one set of n digits, the same in every listed house
            used = [m.NewBoolVar("") for _ in range(D + 1)]
            for h in con["houses"]:
                hv = [x[c] for c in h] if isinstance(h[0], int) else h
                for v in range(1, D + 1):
                    bs = []
                    for c in hv:
                        b = m.NewBoolVar("")
                        m.Add(c == v).OnlyEnforceIf(b)
                        m.Add(c != v).OnlyEnforceIf(b.Not())
                        bs.append(b)
                    m.Add(sum(bs) == used[v])
            m.Add(sum(used[1:]) == int(con["n"]))
        elif t == "counting_circles":  # each digit appears 0 or v times among the circles
            for v in range(1, D + 1):
                bs = []
                for c in cells:
                    b = m.NewBoolVar("")
                    m.Add(c == v).OnlyEnforceIf(b)
                    m.Add(c != v).OnlyEnforceIf(b.Not())
                    bs.append(b)
                z = m.NewBoolVar("")
                m.Add(sum(bs) == v).OnlyEnforceIf(z)
                m.Add(sum(bs) == 0).OnlyEnforceIf(z.Not())
        elif t == "distinct_count":  # exactly `count` different digits among the cells
            used = []
            for v in range(1, D + 1):
                u = m.NewBoolVar("")
                bs = []
                for c in cells:
                    b = m.NewBoolVar("")
                    m.Add(c == v).OnlyEnforceIf(b)
                    m.Add(c != v).OnlyEnforceIf(b.Not())
                    bs.append(b)
                m.AddMaxEquality(u, bs)
                used.append(u)
            m.Add(sum(used) == int(con["count"]))
        elif t == "contains":  # the first cell's digit appears among the other cells
            hits = []
            for c in cells[1:]:
                b = m.NewBoolVar("")
                m.Add(c == cells[0]).OnlyEnforceIf(b)
                m.Add(c != cells[0]).OnlyEnforceIf(b.Not())
                hits.append(b)
            m.AddBoolOr(hits)
        elif t == "first_seen":  # reading in order, the first digit of the set is `value`
            S = set(con.get("digits") or (1, 2, 3))
            X = int(con["value"])
            none_before = None
            for c in cells:
                ins = m.NewBoolVar("")
                m.AddAllowedAssignments([c], [(v,) for v in S]).OnlyEnforceIf(ins)
                m.AddForbiddenAssignments([c], [(v,) for v in S]).OnlyEnforceIf(ins.Not())
                first = m.NewBoolVar("")
                if none_before is None:
                    m.Add(first == ins)
                else:
                    m.AddBoolAnd([ins, none_before]).OnlyEnforceIf(first)
                    m.AddBoolOr([ins.Not(), none_before.Not()]).OnlyEnforceIf(first.Not())
                m.Add(c == X).OnlyEnforceIf(first)
                nb = m.NewBoolVar("")
                if none_before is None:
                    m.Add(nb == ins.Not())
                else:
                    m.AddBoolAnd([none_before, ins.Not()]).OnlyEnforceIf(nb)
                    m.AddBoolOr([none_before.Not(), ins]).OnlyEnforceIf(nb.Not())
                none_before = nb
            if none_before is not None:
                m.Add(none_before == 0)  # some set digit is seen
        elif t == "xsum":
            k = cells[0]
            m.Add(k <= len(cells))  # the first k cells must exist
            terms = []
            for i, c in enumerate(cells):
                inside = m.NewBoolVar("")
                m.Add(k >= i + 1).OnlyEnforceIf(inside)
                m.Add(k <= i).OnlyEnforceIf(inside.Not())
                y = m.NewIntVar(0, D, "")
                m.Add(y == c).OnlyEnforceIf(inside)
                m.Add(y == 0).OnlyEnforceIf(inside.Not())
                terms.append(y)
            m.Add(sum(terms) == con["total"])
        elif t == "skyscraper":
            vis, prev = [], None
            for i, c in enumerate(cells):
                b = m.NewBoolVar("")
                if prev is None:
                    m.Add(b == 1)
                    mx = c
                else:
                    m.Add(c > prev).OnlyEnforceIf(b)
                    m.Add(c <= prev).OnlyEnforceIf(b.Not())
                    mx = m.NewIntVar(1, D, "")
                    m.AddMaxEquality(mx, [prev, c])
                vis.append(b)
                prev = mx
            m.Add(sum(vis) == con["count"])
        elif t == "sandwich":
            n = len(cells)
            p1 = m.NewIntVar(0, n - 1, "")
            pD = m.NewIntVar(0, n - 1, "")
            ones, highs = [], []
            for i, c in enumerate(cells):
                b1 = m.NewBoolVar("")
                bD = m.NewBoolVar("")
                ones.append(b1)
                highs.append(bD)
                m.Add(c == 1).OnlyEnforceIf(b1)
                m.Add(c != 1).OnlyEnforceIf(b1.Not())
                m.Add(c == D).OnlyEnforceIf(bD)
                m.Add(c != D).OnlyEnforceIf(bD.Not())
                m.Add(p1 == i).OnlyEnforceIf(b1)
                m.Add(pD == i).OnlyEnforceIf(bD)
            m.Add(sum(ones) == 1)
            m.Add(sum(highs) == 1)  # exactly one 1 and one D (else p1/pD are free)
            lo = m.NewIntVar(0, n - 1, "")
            hi = m.NewIntVar(0, n - 1, "")
            m.AddMinEquality(lo, [p1, pD])
            m.AddMaxEquality(hi, [p1, pD])
            terms = []
            for i, c in enumerate(cells):
                bi = m.NewBoolVar("")  # lo < i < hi
                g1 = m.NewBoolVar("")
                g2 = m.NewBoolVar("")
                m.Add(lo < i).OnlyEnforceIf(g1)
                m.Add(lo >= i).OnlyEnforceIf(g1.Not())
                m.Add(hi > i).OnlyEnforceIf(g2)
                m.Add(hi <= i).OnlyEnforceIf(g2.Not())
                m.AddBoolAnd([g1, g2]).OnlyEnforceIf(bi)
                m.AddBoolOr([g1.Not(), g2.Not()]).OnlyEnforceIf(bi.Not())
                y = m.NewIntVar(0, D, "")
                m.Add(y == c).OnlyEnforceIf(bi)
                m.Add(y == 0).OnlyEnforceIf(bi.Not())
                terms.append(y)
            m.Add(sum(terms) == con["total"])
        else:
            return None, None
    labels = _add_chaos(m, x, p) if has_chaos(p) else {}
    m.pm_labels = labels  # regions to find: cell -> its label Booleans (tools read the solution's regions)
    shading = {}
    if has_shading(p):
        _add_yin_yang(m, p, shading)
    aux = _AuxVars(m, p.aux, p.N) if getattr(p, "aux", None) else None
    m.pm_aux = aux  # unknowns / layers: their variables (tools read the solution's values)
    for con in p.constraints:
        if con.get("type") == "expr":
            try:
                m.Add(_ExprCP(m, con, x, shading, labels, aux, p.D).holds() == 1)
            except _Unmodelled:
                return None, None
    return m, x


def cpsat_solutions(p, limit=2, time_limit=60.0, workers=1):
    """CP-SAT only (needs OR-Tools): solutions, or None if a rule can't be expressed or the time limit is hit."""
    from ortools.sat.python import cp_model

    m, x = build_model(p)
    if m is None:
        return None
    out = []
    for _ in range(limit):
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = time_limit
        s.parameters.num_workers = workers
        st = s.Solve(m)
        if st == cp_model.INFEASIBLE:
            break
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None  # time limit: unknown
        sol = [s.Value(v) for v in x]
        out.append(sol)
        # exclude this solution: at least one cell differs
        bs = []
        for c, v in enumerate(sol):
            b = m.NewBoolVar("")
            m.Add(x[c] != v).OnlyEnforceIf(b)
            bs.append(b)
        m.AddBoolOr(bs)
    return out


def solutions(p, limit=2, time_limit=60.0, workers=1, node_limit=NODE_LIMIT):
    """up to `limit` solutions, or None if undecided. With OR-Tools: CP-SAT (None if a rule can't be expressed or the
    time limit is hit). Without: the engine's exhaustive search on the rules CP-SAT models (None for others, or if
    the node or time limit is hit), so both installs reach the same verdicts."""
    if have_ortools():
        return cpsat_solutions(p, limit=limit, time_limit=time_limit, workers=workers)
    if not hasattr(p, "groups_of"):
        p.finalize()
    if not supported(p):
        return None
    sols, complete = _engine(p, limit, node_limit, time_limit)
    return sols if complete or len(sols) >= limit else None


def count(p, limit=2, time_limit=60.0):
    s = solutions(p, limit, time_limit)
    return None if s is None else len(s)


def verified_solutions(p, limit=2, node_limit=NODE_LIMIT, time_limit=60.0):
    """Drop-in for cbackend.brute_solve(p, limit, node_limit) when verifying a translation: CP-SAT first when OR-Tools
    is installed, then the engine's exhaustive search (possibly partial if it hits the node or time limit)."""
    if have_ortools():
        s = cpsat_solutions(p, limit=limit, time_limit=time_limit)
        if s is not None:
            return s
    sols, complete = _engine(p, limit, node_limit, time_limit)
    return sols


def decide(p, limit=2, node_limit=NODE_LIMIT, time_limit=60.0):
    """-> (solutions, decided). decided False: neither search could finish (solutions may be partial)."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    t = time.perf_counter()
    sols, decided, by = _decide(p, limit, node_limit, time_limit)
    _log.debug(
        "uniqueness: %d solution(s)%s, by %s, %.3f s",
        len(sols),
        "" if decided else " (undecided)",
        by,
        time.perf_counter() - t,
    )
    return sols, decided


def _decide(p, limit, node_limit, time_limit):
    """decide() and the search that settled it"""
    ortools = have_ortools()
    first = min(node_limit, QUICK_NODES) if ortools else node_limit
    # the quick pass is quick in time too: where each node is costly (global rules, zero givens) its node budget could
    # take the whole time limit before CP-SAT (often under a second) gets a turn
    sols, complete = _engine(p, limit, first, min(time_limit, QUICK_SECONDS) if ortools else time_limit)
    if complete or len(sols) >= limit:
        return sols, True, "the C++ search"
    if ortools:
        # regions to find / shading: large label models where CP-SAT's portfolio pays (a chaos puzzle with one sight
        # rule: 103 s on one worker, 4.6 s on eight); everything else stays on one worker (rate_many runs processes)
        heavy = has_chaos(p) or has_shading(p) or bool(getattr(p, "aux", None))  # unknowns / layers: label-like too
        workers = min(8, os.cpu_count() or 1) if heavy else 1
        s = cpsat_solutions(p, limit=limit, time_limit=time_limit, workers=workers)
        if s is not None:
            return s, True, "CP-SAT"
        if first < node_limit:  # a rule CP-SAT does not model, or its time ran out: the full C++ search
            sols, complete = _engine(p, limit, node_limit, time_limit)
            if complete or len(sols) >= limit:
                return sols, True, "the full C++ search"
    return sols, False, "neither search"


VERIFY_HINT = 'install OR-Tools for the CP-SAT checker: pip install "pencilmark[verify]"'
