"""Uniqueness checks with OR-Tools CP-SAT when installed (pip install "pencilmark[verify]"), else the engine's
exhaustive C++ search.

solutions(p, limit=2, time_limit=60) -> list of solutions (each a list of digits, len p.N),
                                         or None if undecided: the puzzle uses a rule the checker does not model,
                                         or the search hit its node / time limit.
decide() (used by pencilmark.solve) runs the C++ search (cbackend.brute_solve) first and CP-SAT only when that search
hits its node limit. CP-SAT is independent of the engine's propagation.
Pair relations are encoded generically as allowed-pair tables from model.RELATIONS, so any relation kind works.
"""
from . import model as M

NODE_LIMIT = 20_000_000

# constraint types the checker models (the same set the CP-SAT model below encodes); anything else -> undecided
_CON_TYPES = {"line", "clone", "sum", "little_killer", "arrow", "equal_sum", "between", "table", "count", "digit_set",
              "counting_circles", "distinct_count", "contains", "first_seen", "xsum", "skyscraper", "sandwich"}


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


def _engine(p, limit, node_limit):
    """the C++ exhaustive search -> (solutions, complete)."""
    from . import cbackend as CB
    r = CB.brute_solve(p, limit=limit, node_limit=node_limit)
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
        if c in p.givens:          # a given outside its cell's domain is a contradiction, not an override
            dom = [v for v in dom if v == p.givens[c]]
        if not dom:                # empty domain: infeasible (0 solutions), not "unsupported"
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
        if not allowed:            # unsatisfiable relation: infeasible, not "unsupported"
            m.AddBoolOr([])
            continue
        m.AddAllowedAssignments([x[a], x[b]], sorted(allowed))
    for con in p.constraints:
        t = con.get("type")
        if t in ("line", "clone"):
            continue                        # compiled into relations / n-ary constraints by finalize()
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
            mx = m.NewIntVar(1, D, ""); mn = m.NewIntVar(1, D, "")
            m.AddMaxEquality(mx, cells); m.AddMinEquality(mn, cells)
            m.Add(mx - mn == len(cells) - 1)
        elif t == "between":
            a, b = cells[0], cells[-1]
            lo = m.NewIntVar(1, D, ""); hi = m.NewIntVar(1, D, "")
            m.AddMinEquality(lo, [a, b]); m.AddMaxEquality(hi, [a, b])
            for c in cells[1:-1]:
                m.Add(c > lo); m.Add(c < hi)
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
                    m.Add(c == v).OnlyEnforceIf(b); m.Add(c != v).OnlyEnforceIf(b.Not())
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
                        m.Add(c == v).OnlyEnforceIf(b); m.Add(c != v).OnlyEnforceIf(b.Not())
                        bs.append(b)
                    m.Add(sum(bs) == used[v])
            m.Add(sum(used[1:]) == int(con["n"]))
        elif t == "counting_circles":  # each digit appears 0 or v times among the circles
            for v in range(1, D + 1):
                bs = []
                for c in cells:
                    b = m.NewBoolVar("")
                    m.Add(c == v).OnlyEnforceIf(b); m.Add(c != v).OnlyEnforceIf(b.Not())
                    bs.append(b)
                z = m.NewBoolVar("")
                m.Add(sum(bs) == v).OnlyEnforceIf(z); m.Add(sum(bs) == 0).OnlyEnforceIf(z.Not())
        elif t == "distinct_count":  # exactly `count` different digits among the cells
            used = []
            for v in range(1, D + 1):
                u = m.NewBoolVar(""); bs = []
                for c in cells:
                    b = m.NewBoolVar("")
                    m.Add(c == v).OnlyEnforceIf(b); m.Add(c != v).OnlyEnforceIf(b.Not())
                    bs.append(b)
                m.AddMaxEquality(u, bs); used.append(u)
            m.Add(sum(used) == int(con["count"]))
        elif t == "contains":  # the first cell's digit appears among the other cells
            hits = []
            for c in cells[1:]:
                b = m.NewBoolVar("")
                m.Add(c == cells[0]).OnlyEnforceIf(b); m.Add(c != cells[0]).OnlyEnforceIf(b.Not())
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
            m.Add(k <= len(cells))         # the first k cells must exist
            terms = []
            for i, c in enumerate(cells):
                inside = m.NewBoolVar("")
                m.Add(k >= i + 1).OnlyEnforceIf(inside); m.Add(k <= i).OnlyEnforceIf(inside.Not())
                y = m.NewIntVar(0, D, "")
                m.Add(y == c).OnlyEnforceIf(inside); m.Add(y == 0).OnlyEnforceIf(inside.Not())
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
                    m.Add(c > prev).OnlyEnforceIf(b); m.Add(c <= prev).OnlyEnforceIf(b.Not())
                    mx = m.NewIntVar(1, D, ""); m.AddMaxEquality(mx, [prev, c])
                vis.append(b); prev = mx
            m.Add(sum(vis) == con["count"])
        elif t == "sandwich":
            n = len(cells)
            p1 = m.NewIntVar(0, n - 1, ""); pD = m.NewIntVar(0, n - 1, "")
            ones, highs = [], []
            for i, c in enumerate(cells):
                b1 = m.NewBoolVar(""); bD = m.NewBoolVar("")
                ones.append(b1); highs.append(bD)
                m.Add(c == 1).OnlyEnforceIf(b1); m.Add(c != 1).OnlyEnforceIf(b1.Not())
                m.Add(c == D).OnlyEnforceIf(bD); m.Add(c != D).OnlyEnforceIf(bD.Not())
                m.Add(p1 == i).OnlyEnforceIf(b1); m.Add(pD == i).OnlyEnforceIf(bD)
            m.Add(sum(ones) == 1); m.Add(sum(highs) == 1)   # exactly one 1 and one D (else p1/pD are free)
            lo = m.NewIntVar(0, n - 1, ""); hi = m.NewIntVar(0, n - 1, "")
            m.AddMinEquality(lo, [p1, pD]); m.AddMaxEquality(hi, [p1, pD])
            terms = []
            for i, c in enumerate(cells):
                bi = m.NewBoolVar("")      # lo < i < hi
                g1 = m.NewBoolVar(""); g2 = m.NewBoolVar("")
                m.Add(lo < i).OnlyEnforceIf(g1); m.Add(lo >= i).OnlyEnforceIf(g1.Not())
                m.Add(hi > i).OnlyEnforceIf(g2); m.Add(hi <= i).OnlyEnforceIf(g2.Not())
                m.AddBoolAnd([g1, g2]).OnlyEnforceIf(bi); m.AddBoolOr([g1.Not(), g2.Not()]).OnlyEnforceIf(bi.Not())
                y = m.NewIntVar(0, D, "")
                m.Add(y == c).OnlyEnforceIf(bi); m.Add(y == 0).OnlyEnforceIf(bi.Not())
                terms.append(y)
            m.Add(sum(terms) == con["total"])
        else:
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
            return None                       # time limit: unknown
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
    the node limit is hit), so both installs reach the same verdicts."""
    if have_ortools():
        return cpsat_solutions(p, limit=limit, time_limit=time_limit, workers=workers)
    if not hasattr(p, "groups_of"):
        p.finalize()
    if not supported(p):
        return None
    sols, complete = _engine(p, limit, node_limit)
    return sols if complete or len(sols) >= limit else None


def count(p, limit=2, time_limit=60.0):
    s = solutions(p, limit, time_limit)
    return None if s is None else len(s)


def verified_solutions(p, limit=2, node_limit=NODE_LIMIT, time_limit=60.0):
    """Drop-in for cbackend.brute_solve(p, limit, node_limit) when verifying a translation: CP-SAT first when OR-Tools
    is installed, then the engine's exhaustive search (possibly partial if it hits the node limit)."""
    if have_ortools():
        s = cpsat_solutions(p, limit=limit, time_limit=time_limit)
        if s is not None:
            return s
    sols, complete = _engine(p, limit, node_limit)
    return sols


def decide(p, limit=2, node_limit=NODE_LIMIT, time_limit=60.0):
    """-> (solutions, decided). decided False: neither search could finish (solutions may be partial)."""
    if not hasattr(p, "groups_of"):
        p.finalize()
    sols, complete = _engine(p, limit, node_limit)
    if complete or len(sols) >= limit:
        return sols, True
    if have_ortools():
        s = cpsat_solutions(p, limit=limit, time_limit=time_limit)
        if s is not None:
            return s, True
    return sols, False


VERIFY_HINT = 'install OR-Tools for the CP-SAT checker: pip install "pencilmark[verify]"'
