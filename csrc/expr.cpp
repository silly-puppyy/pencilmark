// Evaluator of the custom rule language (expr.hpp): a tree walk over values that mirror pencilmark/rules/custom.py.
#include "expr.hpp"

#include <algorithm>
#include <numeric>
#include <string>

namespace cs {
namespace {

using i64 = long long;
constexpr i64 NEED_N = -(i64(1) << 62);  ///< a cell value whose digit is not known yet (lazy evaluation)

struct Val {
    enum Kind : uint8_t { NUM, BOOL, LIST, ABSENT, FN, CELL } k = ABSENT;
    i64 n = 0, d = 1;  ///< NUM: n / d in lowest terms, d > 0; CELL: n = digit
    bool b = false;
    int var = -1;      ///< CELL: variable index
    std::shared_ptr<std::vector<Val>> list;
    const ExprNode* fn = nullptr;  ///< FN: the letfn / lambda node

    static Val num(i64 n, i64 d = 1) {
        Val v;
        if (d == 0) return v;  // ABSENT
        if (d < 0) n = -n, d = -d;
        i64 g = std::gcd(n < 0 ? -n : n, d);
        if (g > 1) n /= g, d /= g;
        v.k = NUM, v.n = n, v.d = d;
        return v;
    }
    static Val boolean(bool b) {
        Val v;
        v.k = BOOL, v.b = b;
        return v;
    }
    static Val of_list(std::vector<Val> xs) {
        Val v;
        v.k = LIST, v.list = std::make_shared<std::vector<Val>>(std::move(xs));
        return v;
    }
    bool absent() const { return k == ABSENT; }
    bool numeric() const { return k == NUM || k == CELL; }
    i64 nn() const {  ///< numerator (a cell: its digit; an unknown one is asked for)
        if (k == CELL && n == NEED_N) throw ExprNeed{var, false};
        return n;
    }
    i64 dd() const { return k == CELL ? 1 : d; }    ///< denominator
    bool integer() const { return numeric() && dd() == 1; }
};

/// a < b, a == b on rationals, cross-multiplied in 64 bits (digit arithmetic keeps numerators and denominators far
/// below 2^31; no __int128, which MSVC lacks)
inline int cmp(const Val& a, const Val& b) {
    i64 x = a.nn() * b.dd(), y = b.nn() * a.dd();
    return x < y ? -1 : x > y ? 1 : 0;
}

struct Ev {
    const ExprProgram& P;
    const int* dig;
    const int* lab;  ///< region label per variable, or null
    const int* sh;   ///< colour per variable (1 shaded, 2 unshaded, 0 unknown), or null
    const int* aux;  ///< value per aux variable (AUX_UNSET: not known), or null
    bool lazy = false;  ///< expr_holds_lazy: an unknown digit / label is asked for (ExprNeed), not absent
    std::vector<Val> slots;

    Ev(const ExprProgram& p, const int* d, const int* l, const int* s, const int* a = nullptr)
        : P(p), dig(d), lab(l), sh(s), aux(a), slots(p.nslots) {}
    Val aux_value(long long i) {
        if (!aux || i < 0 || aux[i] == AUX_UNSET) return Val();
        return Val::num(aux[i]);
    }

    Val cell(int var) {
        Val v;
        v.k = Val::CELL, v.n = lazy && dig[var] < 0 ? NEED_N : dig[var], v.var = var;
        return v;
    }
    Val list_value(const ExprList& L) {
        if (L.var >= 0) return cell(L.var);
        std::vector<Val> xs;
        for (const ExprList& x : L.items) xs.push_back(list_value(x));
        return Val::of_list(std::move(xs));
    }
    /// a value as a sequence: a list as is, a cell as a one-element list; empty optional = ABSENT / not a sequence
    bool seq(const Val& v, std::vector<Val>& out) {
        if (v.k == Val::LIST) {
            out = *v.list;
            return true;
        }
        if (v.k == Val::CELL) {
            out = {v};
            return true;
        }
        return false;
    }
    Val call_fn(const Val& f, const std::vector<Val>& args) {
        if (f.k != Val::FN || f.fn->params.size() != args.size()) return Val();
        const std::vector<int>& ps = f.fn->params;
        std::vector<Val> saved;  // recursion: keep the caller's parameter values
        for (int s : ps) saved.push_back(slots[s]);
        for (size_t i = 0; i < ps.size(); ++i) slots[ps[i]] = args[i];
        Val r = eval(f.fn->op == X_LETFN ? f.fn->kids[0] : f.fn->kids[0]);
        for (size_t i = 0; i < ps.size(); ++i) slots[ps[i]] = saved[i];
        return r;
    }
    bool truthy_pred(const Val& f, const Val& x) {
        Val r = call_fn(f, {x});
        return r.k == Val::BOOL && r.b;
    }
    Val eq(const Val& a, const Val& b, bool& known) {
        known = !(a.absent() || b.absent());
        if (!known) return Val::boolean(false);
        if (a.k == Val::BOOL || b.k == Val::BOOL) return Val::boolean(a.k == b.k && a.b == b.b);
        if (a.k == Val::LIST || b.k == Val::LIST) {
            std::vector<Val> x, y;
            if (!seq(a, x) || !seq(b, y) || x.size() != y.size()) return Val::boolean(false);
            for (size_t i = 0; i < x.size(); ++i)
                if (!x[i].numeric() || !y[i].numeric() || cmp(x[i], y[i]) != 0) return Val::boolean(false);
            return Val::boolean(true);
        }
        return Val::boolean(a.numeric() && b.numeric() && cmp(a, b) == 0);
    }
    Val builtin(int id, const std::vector<Val>& a);
    Val eval(const ExprNode& e);
};

bool is_prime(const Val& v) {
    if (!v.integer() || v.nn() < 2) return false;
    i64 n = v.nn();
    for (i64 k = 2; k * k <= n; ++k)
        if (n % k == 0) return false;
    return true;
}

// built-in ids: the order of custom.FNS
enum Builtin { SUM, PRODUCT, MIN, MAX, COUNT, LEN, ALL, ANY, SORT, REVERSE, ABS, ODD, EVEN, PRIME, NUMF, DEFINED,
               ALL_DIFFERENT, COUNT_DISTINCT, CONCAT, MEDIAN, SEEN, UPTO, TAKE_WHILE, TAKE, POSITION, ROW, COL, BOX,
               REGION, SHADED };

Val Ev::builtin(int id, const std::vector<Val>& a) {
    static const bool BOOLEAN[] = {false, false, false, false, false, false, true,  true,  false, false,
                                   false, true,  true,  true,  false, true,  true,  false, false, false,
                                   false, false, false, false, false, false, false, false, false, true};
    if (id != DEFINED)
        for (const Val& x : a)
            if (x.absent()) return BOOLEAN[id] ? Val::boolean(false) : Val();  // an absent argument
    std::vector<Val> xs;
    auto numbers = [&](const Val& v, std::vector<Val>& out) {
        out.clear();
        std::vector<Val> s;
        if (!seq(v, s)) return false;
        for (const Val& x : s) {
            if (x.absent()) {
                out.push_back(x);
                continue;
            }
            if (!x.numeric()) return false;
            out.push_back(Val::num(x.nn(), x.dd()));
        }
        return true;
    };
    switch (id) {
        case SUM: case PRODUCT: {
            if (!numbers(a[0], xs)) return Val();
            i64 n = id == SUM ? 0 : 1, d = 1;
            for (const Val& x : xs) {
                if (x.absent()) return Val();
                Val r = id == SUM ? Val::num(n * x.d + x.n * d, d * x.d) : Val::num(n * x.n, d * x.d);
                n = r.n, d = r.d;
            }
            return Val::num(n, d);
        }
        case MIN: case MAX: {
            if (a.size() == 2) xs = {a[0], a[1]};
            else if (!numbers(a[0], xs)) return Val();
            const Val* best = nullptr;
            for (const Val& x : xs) {
                if (x.absent()) continue;
                if (!best || (id == MIN ? cmp(x, *best) < 0 : cmp(x, *best) > 0)) best = &x;
            }
            return best ? Val::num(best->nn(), best->dd()) : Val();
        }
        case COUNT: {
            std::vector<Val> s;
            if (!seq(a[0], s)) return Val();
            bool any_bool = false;
            for (const Val& x : s) any_bool |= x.k == Val::BOOL;
            if (!any_bool) return Val::num((i64)s.size());
            i64 c = 0;
            for (const Val& x : s) c += x.k == Val::BOOL && x.b;
            return Val::num(c);
        }
        case LEN: {
            std::vector<Val> s;
            return seq(a[0], s) ? Val::num((i64)s.size()) : Val();
        }
        case ALL: case ANY: {
            std::vector<Val> s;
            if (!seq(a[0], s)) return Val::boolean(false);
            bool r = id == ALL;
            for (const Val& x : s) {
                bool t = x.k == Val::BOOL && x.b;
                if (id == ALL && !t) r = false;
                if (id == ANY && t) r = true;
            }
            return Val::boolean(r);
        }
        case SORT: {
            if (!numbers(a[0], xs)) return Val();
            for (const Val& x : xs)
                if (x.absent()) return Val();
            std::sort(xs.begin(), xs.end(), [](const Val& p, const Val& q) { return cmp(p, q) < 0; });
            return Val::of_list(xs);
        }
        case REVERSE: {
            std::vector<Val> s;
            if (!seq(a[0], s)) return Val();
            std::reverse(s.begin(), s.end());
            return Val::of_list(s);
        }
        case ABS: return a[0].numeric() ? Val::num(a[0].nn() < 0 ? -a[0].nn() : a[0].nn(), a[0].dd()) : Val();
        case ODD: return Val::boolean(a[0].integer() && ((a[0].nn() % 2) + 2) % 2 == 1);
        case EVEN: return Val::boolean(a[0].integer() && a[0].nn() % 2 == 0);
        case PRIME: return Val::boolean(is_prime(a[0]));
        case NUMF: return Val::num(a[0].k == Val::BOOL && a[0].b ? 1 : 0);
        case DEFINED: return Val::boolean(!a[0].absent());
        case ALL_DIFFERENT: case COUNT_DISTINCT: {
            if (!numbers(a[0], xs)) return Val();
            std::vector<std::pair<i64, i64>> seen;
            for (const Val& x : xs) {
                std::pair<i64, i64> key{x.absent() ? 0 : x.n, x.absent() ? 0 : x.d};  // ABSENT: a value of its own
                if (std::find(seen.begin(), seen.end(), key) == seen.end()) seen.push_back(key);
            }
            if (id == ALL_DIFFERENT) return Val::boolean(seen.size() == xs.size());
            return Val::num((i64)seen.size());
        }
        case CONCAT: {
            if (!numbers(a[0], xs)) return Val();
            std::string s;
            for (const Val& x : xs) {
                if (x.absent()) return Val();
                s += std::to_string(x.n / x.d);  // a whole number per element (int() in the reference truncates)
            }
            return Val::num(s.empty() ? 0 : std::stoll(s));
        }
        case MEDIAN: {
            if (!numbers(a[0], xs) || xs.empty()) return Val();
            for (const Val& x : xs)
                if (x.absent()) return Val();
            std::sort(xs.begin(), xs.end(), [](const Val& p, const Val& q) { return cmp(p, q) < 0; });
            size_t m = xs.size() / 2;
            if (xs.size() % 2) return xs[m];
            return Val::num(xs[m - 1].n * xs[m].d + xs[m].n * xs[m - 1].d, 2 * xs[m - 1].d * xs[m].d);
        }
        case SEEN: {
            std::vector<Val> s, out;
            if (!seq(a[0], s)) return Val();
            const Val* top = nullptr;
            for (const Val& x : s)
                if (!top || cmp(x, *top) > 0) out.push_back(x), top = &x;
            return Val::of_list(out);
        }
        case UPTO: case TAKE_WHILE: case POSITION: {
            std::vector<Val> s, out;
            if (!seq(a[0], s)) return Val();
            for (size_t i = 0; i < s.size(); ++i) {
                bool hit = truthy_pred(a[1], s[i]);
                if (id == POSITION && hit) return Val::num((i64)i + 1);
                if (id == TAKE_WHILE && !hit) break;
                out.push_back(s[i]);
                if (id == UPTO && hit) return Val::of_list(out);
            }
            if (id == TAKE_WHILE) return Val::of_list(out);
            return Val();  // upto / position: no element meets the condition
        }
        case TAKE: {
            std::vector<Val> s;
            if (!a[0].integer() || !seq(a[1], s)) return Val();
            i64 n = a[0].nn();
            if (n < 0 || n > (i64)s.size()) return Val();
            return Val::of_list(std::vector<Val>(s.begin(), s.begin() + n));
        }
        case ROW: case COL: case BOX: {
            if (a[0].k != Val::CELL) return Val();
            int r = P.row[a[0].var], c = P.col[a[0].var];
            if (id == ROW) return Val::num(r);
            if (id == COL) return Val::num(c);
            return Val::num((r - 1) / P.box_h * P.box_h + (c - 1) / P.box_w + 1);
        }
        case REGION: {  // no labels (or no label yet): absent, so comparisons with it fail and the caller decides later
            if (lazy && a[0].k == Val::CELL && lab && lab[a[0].var] < 0) throw ExprNeed{a[0].var, true};
            if (a[0].k != Val::CELL || !lab || lab[a[0].var] <= 0) return Val();
            return Val::num(lab[a[0].var]);
        }
        case SHADED: {  // no shading (or not known yet): absent, so the rule fails and the caller decides later
            if (lazy && a[0].k == Val::CELL && sh && sh[a[0].var] < 0) throw ExprNeed{a[0].var, false, true};
            if (a[0].k != Val::CELL || !sh || sh[a[0].var] <= 0) return Val();
            return Val::boolean(sh[a[0].var] == 1);
        }
    }
    return Val();
}

Val Ev::eval(const ExprNode& e) {
    const auto& K = e.kids;
    switch (e.op) {
        case X_NUM: return Val::num(e.v);
        case X_BOOL: return Val::boolean(e.v != 0);
        case X_CELLS: return list_value(P.lists[e.v]);
        case X_CELL: return cell((int)e.v);
        case X_SLOT: return slots[e.v];
        case X_AUX: return aux_value(e.v);
        case X_AUXCELL: {  // layer e.v at a cell of the rule
            Val c = eval(K[0]);
            if (c.k != Val::CELL || c.var < 0 || c.var >= (int)P.gcell.size()) return Val();
            return aux_value(P.aux_u + e.v * (long long)P.aux_n + P.gcell[c.var]);
        }
        case X_LIST: {
            std::vector<Val> xs;
            for (const ExprNode& k : K) xs.push_back(eval(k));
            return Val::of_list(std::move(xs));
        }
        case X_RANGE: {
            Val lo = eval(K[0]), hi = eval(K[1]);
            if (!lo.numeric() || !hi.numeric()) return Val();
            std::vector<Val> xs;
            for (i64 k = lo.nn() / lo.dd(); k <= hi.nn() / hi.dd(); ++k) xs.push_back(Val::num(k));
            return Val::of_list(std::move(xs));
        }
        case X_COMP: {
            std::vector<Val> src, out;
            if (!seq(eval(K[0]), src)) return Val();
            for (const Val& x : src) {
                slots[e.v] = x;
                if (K[2].op != X_NONE) {
                    Val c = eval(K[2]);
                    if (!(c.k == Val::BOOL && c.b)) continue;
                }
                out.push_back(eval(K[1]));
            }
            return Val::of_list(std::move(out));
        }
        case X_LET:
            slots[e.v] = eval(K[0]);
            return eval(K[1]);
        case X_LETFN: {
            Val f;
            f.k = Val::FN, f.fn = &e;
            slots[e.v] = f;
            return eval(K[1]);
        }
        case X_LAMBDA: {
            Val f;
            f.k = Val::FN, f.fn = &e;
            return f;
        }
        case X_IF: {
            Val c = eval(K[0]);
            if (c.k != Val::BOOL) return Val();
            return eval(c.b ? K[1] : K[2]);
        }
        case X_DEFAULT: {
            Val v = eval(K[0]);
            return v.absent() ? eval(K[1]) : v;
        }
        case X_OR: case X_AND: {
            Val x = eval(K[0]);
            if (x.k != Val::BOOL) return Val::boolean(false);
            if (e.op == X_AND ? !x.b : x.b) return x;
            Val y = eval(K[1]);
            return y.k == Val::BOOL ? y : Val::boolean(false);
        }
        case X_NOT: {
            Val x = eval(K[0]);
            return x.k == Val::BOOL ? Val::boolean(!x.b) : Val::boolean(false);
        }
        case X_EQ: case X_NE: {
            bool known;
            Val r = eq(eval(K[0]), eval(K[1]), known);
            if (!known) return Val::boolean(false);  // with ABSENT both are false
            return e.op == X_EQ ? r : Val::boolean(!r.b);
        }
        case X_LT: case X_LE: case X_GT: case X_GE: {
            Val x = eval(K[0]), y = eval(K[1]);
            if (!x.numeric() || !y.numeric()) return Val::boolean(false);
            int c = cmp(x, y);
            bool r = e.op == X_LT ? c < 0 : e.op == X_LE ? c <= 0 : e.op == X_GT ? c > 0 : c >= 0;
            return Val::boolean(r);
        }
        case X_IN: case X_NOTIN: {
            Val x = eval(K[0]), S = eval(K[1]);
            std::vector<Val> s;
            if (!x.numeric() || !seq(S, s)) return Val::boolean(false);
            bool hit = false;
            for (const Val& y : s) hit |= y.numeric() && cmp(x, y) == 0;
            return Val::boolean(e.op == X_IN ? hit : !hit);
        }
        case X_ADD: case X_SUB: case X_MUL: case X_DIV: case X_IDIV: case X_MOD: case X_POW: {
            Val x = eval(K[0]), y = eval(K[1]);
            if (!x.numeric() || !y.numeric()) return Val();
            i64 a = x.nn(), b = x.dd(), c = y.nn(), d = y.dd();
            switch (e.op) {
                case X_ADD: return Val::num(a * d + c * b, b * d);
                case X_SUB: return Val::num(a * d - c * b, b * d);
                case X_MUL: return Val::num(a * c, b * d);
                case X_POW: {
                    if (d != 1 || c < 0 || c > 62) return Val();
                    i64 n = 1, m = 1;
                    for (i64 k = 0; k < c; ++k) n *= a, m *= b;
                    return Val::num(n, m);
                }
                default: break;
            }
            if (c == 0) return Val();  // division by zero: absent
            Val q = Val::num(a * d, b * c);
            i64 fl = q.n / q.d - ((q.n % q.d != 0) && ((q.n < 0) != (q.d < 0)) ? 1 : 0);  // floor
            if (e.op == X_DIV) return q;
            if (e.op == X_IDIV) return Val::num(fl);
            return Val::num(a * d - c * b * fl, b * d);  // x - y * floor(x / y)
        }
        case X_NEG: {
            Val x = eval(K[0]);
            return x.numeric() ? Val::num(-x.nn(), x.dd()) : Val();
        }
        case X_INDEX: {
            std::vector<Val> s;
            Val L = eval(K[0]), i = eval(K[1]);
            if (!seq(L, s) || !i.integer() || i.nn() < 1 || i.nn() > (i64)s.size()) return Val();
            return s[i.nn() - 1];
        }
        case X_SLICE: {
            std::vector<Val> s;
            Val L = eval(K[0]), i = eval(K[1]), j = eval(K[2]);
            if (!seq(L, s) || !i.numeric() || !j.numeric()) return Val();
            i64 lo = std::max<i64>(i.nn() / i.dd(), 1), hi = std::min<i64>(j.nn() / j.dd(), (i64)s.size());
            if (lo > hi) return Val::of_list({});
            return Val::of_list(std::vector<Val>(s.begin() + (lo - 1), s.begin() + hi));
        }
        case X_CALL: {
            std::vector<Val> args;
            for (const ExprNode& k : K) args.push_back(eval(k));
            return builtin((int)e.v, args);
        }
        case X_CALLFN: {
            std::vector<Val> args;
            for (const ExprNode& k : K) args.push_back(eval(k));
            return call_fn(slots[e.v], args);
        }
    }
    return Val();
}

bool layered_node(const ExprNode& e) {
    if (e.op == X_CALL && (e.v == REGION || e.v == SHADED)) return true;
    if (e.op == X_AUX || e.op == X_AUXCELL) return true;  // unknowns / layers: decided once their values are known
    for (const ExprNode& k : e.kids)
        if (layered_node(k)) return true;
    return false;
}

}  // namespace

bool expr_holds(const ExprProgram& prog, const int* digits, const int* labels, const int* shading, const int* aux) {
    Ev ev(prog, digits, labels, shading, aux);
    Val r = ev.eval(prog.root);
    return r.k == Val::BOOL && r.b;
}

namespace {
bool relational_node(const ExprNode& e, int parent) {
    if (e.op == X_CALL && e.v == REGION) return parent == X_EQ || parent == X_NE;
    if (e.op == X_AUXCELL) return false;  // a layer read some other way
    for (const ExprNode& k : e.kids)
        if (!relational_node(k, e.op)) return false;
    return true;
}
}  // namespace

bool expr_region_relational(const ExprNode& e) { return relational_node(e, X_NONE); }

bool expr_holds_lazy(const ExprProgram& prog, const int* digits, const int* labels, const int* shading) {
    Ev ev(prog, digits, labels, shading, nullptr);
    ev.lazy = true;
    Val r = ev.eval(prog.root);
    return r.k == Val::BOOL && r.b;
}

bool expr_layered(const ExprNode& e) { return layered_node(e); }

int expr_eq_unknown(const ExprProgram& prog) {
    const ExprNode& r = prog.root;
    if (r.op != X_EQ || r.kids.size() != 2) return -1;
    for (int s = 0; s < 2; ++s)
        if (r.kids[s].op == X_AUX && r.kids[1 - s].op != X_AUX) return s;
    return -1;
}

bool expr_side_value(const ExprProgram& prog, int side, const int* digits, const int* aux, long long& value) {
    Ev ev(prog, digits, nullptr, nullptr, aux);
    Val v = ev.eval(prog.root.kids[1 - side]);
    if (v.k == Val::CELL) v = Val::num(v.n);
    if (v.k != Val::NUM || v.d != 1) return false;
    value = v.n;
    return true;
}

bool expr_slot_value(const ExprProgram& prog, const ExprNode& body, int slot, int var, const int* digits, const int* aux,
                     long long& value) {
    Ev ev(prog, digits, nullptr, nullptr, aux);
    if (slot < 0 || slot >= (int)ev.slots.size()) return false;
    ev.slots[slot] = ev.cell(var);
    Val v = ev.eval(body);
    if (v.k == Val::CELL) v = Val::num(v.n);
    if (v.k != Val::NUM || v.d != 1) return false;
    value = v.n;
    return true;
}

namespace {
bool calls(const ExprNode& e, int fn) {
    if (e.op == X_CALL && e.v == fn) return true;
    for (const ExprNode& k : e.kids)
        if (calls(k, fn)) return true;
    return false;
}
}  // namespace

bool expr_reads_shading(const ExprNode& e) { return calls(e, SHADED); }
bool expr_reads_regions(const ExprNode& e) { return calls(e, REGION); }

}  // namespace cs
