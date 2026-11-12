// Abstract evaluation of the custom rule language (expr.hpp, expr_may_hold): the evaluator of expr.cpp run over sets
// of values instead of values, so a rule can be read with every cell's candidates and every unknown's open values at
// once. A number is a small exact set of whole numbers, else an interval; a condition is "may be true" / "may be
// false"; a list keeps its elements, each marked when a filter may drop it; anything not modelled is TOP (any value).
// Every operation over-approximates (each concrete result lies in the abstract one), so "the rule cannot hold" is a
// proof: the rule lemma technique (RuleLemma) probes one digit or value at a time with it.
#include <algorithm>
#include <map>
#include <cstdint>
#include <vector>
#include <functional>
#include <memory>
#include <tuple>
#include <string>
#include <unordered_map>

#include "portable.hpp"
#include "expr.hpp"

namespace cs {
namespace {

using i64 = long long;
constexpr i64 BIG = (i64)1 << 50;  ///< beyond this a bound is unbounded (products over many cells)
constexpr size_t CAP = 128;        ///< exact sets up to this many values, then intervals

/// an exact set's values: up to 12 inline, more on the heap -- the evaluator builds millions of small sets (a cell's
/// candidates, a sum's few values) and the heap traffic of std::vector was most of its time (profile, 2026-11-10)
class SVec {
    static constexpr uint32_t K = 12;
    i64 in_[K];
    uint32_t n_ = 0;
    std::vector<i64> big_;  // used only past K values
    bool heap() const { return n_ > K; }

  public:
    SVec() = default;
    SVec(const std::vector<i64>& v) { assign(v.begin(), v.end()); }  // NOLINT (implicit: drop-in for the vector)
    SVec& operator=(const std::vector<i64>& v) {
        assign(v.begin(), v.end());
        return *this;
    }
    template <class It>
    void assign(It b, It e) {
        const size_t m = (size_t)(e - b);
        if (m <= K) {
            big_.clear();
            std::copy(b, e, in_);
        } else {
            big_.assign(b, e);
        }
        n_ = (uint32_t)m;
    }
    operator std::vector<i64>() const { return std::vector<i64>(begin(), end()); }  // NOLINT
    const i64* begin() const { return heap() ? big_.data() : in_; }
    const i64* end() const { return begin() + n_; }
    size_t size() const { return n_; }
    bool empty() const { return n_ == 0; }
    void clear() { n_ = 0, big_.clear(); }
    i64 front() const { return *begin(); }
    i64 back() const { return begin()[n_ - 1]; }
    i64 operator[](size_t i) const { return begin()[i]; }
    void push_back(i64 x) {
        if (n_ < K) {
            in_[n_++] = x;
        } else {
            if (n_ == K) big_.assign(in_, in_ + K);
            big_.push_back(x);
            ++n_;
        }
    }
};

i64 sat(i64 x) { return x > BIG ? BIG : x < -BIG ? -BIG : x; }
i64 smul(i64 a, i64 b) {
    if (a == 0 || b == 0) return 0;
    if ((a > 0 ? a : -a) > BIG / (b > 0 ? b : -b)) return ((a > 0) == (b > 0)) ? BIG : -BIG;
    return a * b;
}

struct AV {
    enum Kind : uint8_t { NUM, BOOL, LIST, FN, TOP } k = TOP;
    // NUM: exact -> vals (sorted, unique, non-empty unless only absent); else [lo, hi]
    bool exact = false;
    SVec vals;
    i64 lo = -BIG, hi = BIG;
    int var = -1;  ///< NUM from one cell of the rule: its variable (row / col / box / layer reads)
    uint64_t deps = 0;  ///< NUM: the rule's cells (variables < 64) its value was computed from (parameters)
    // BOOL
    bool mt = true, mf = true;
    // LIST
    std::shared_ptr<std::vector<AV>> list;
    std::vector<char> opt;  ///< per element: a filter may drop it
    const ExprNode* fn = nullptr;
    bool absent = false;  ///< may be ABSENT (as well as what the rest says); only absent: NUM with no values

    static AV top() { return AV{}; }
    static AV boolean(bool t, bool f) {
        AV a;
        a.k = BOOL, a.mt = t, a.mf = f;
        return a;
    }
    static AV set(std::vector<i64> v) {
        AV a;
        a.k = NUM;
        if (!std::is_sorted(v.begin(), v.end())) std::sort(v.begin(), v.end());  // mostly sorted already
        v.erase(std::unique(v.begin(), v.end()), v.end());
        if (v.size() > CAP) {
            a.exact = false, a.lo = v.front(), a.hi = v.back();
        } else {
            a.exact = true, a.vals = std::move(v);
            if (!a.vals.empty()) a.lo = a.vals.front(), a.hi = a.vals.back();
        }
        return a;
    }
    static AV range(i64 lo, i64 hi) {
        if (hi - lo < (i64)CAP && lo > -BIG && hi < BIG) {
            std::vector<i64> v;
            for (i64 x = lo; x <= hi; ++x) v.push_back(x);
            return set(v);
        }
        AV a;
        a.k = NUM, a.exact = false, a.lo = sat(lo), a.hi = sat(hi);
        return a;
    }
    static AV only_absent() {
        AV a = set({});
        a.absent = true;
        return a;
    }
    static AV of_list(std::vector<AV> xs, std::vector<char> o) {
        AV a;
        a.k = LIST, a.list = std::make_shared<std::vector<AV>>(std::move(xs)), a.opt = std::move(o);
        a.opt.resize(a.list->size(), 0);  // one flag per element (a list built without flags has none optional)
        return a;
    }
    bool num() const { return k == NUM; }
    bool empty_num() const { return k == NUM && exact && vals.empty(); }  ///< no number (only absent, if anything)
};

AV join(const AV& a, const AV& b) {
    if (a.k == AV::NUM && a.empty_num() && !b.absent && b.k != AV::TOP) {
        AV r = b;
        r.absent |= a.absent;
        return r;
    }
    if (b.k == AV::NUM && b.empty_num() && a.k != AV::TOP) {
        AV r = a;
        r.absent |= b.absent;
        return r;
    }
    if (a.k != b.k || a.k == AV::TOP || a.k == AV::FN) return AV::top();
    AV r;
    if (a.k == AV::NUM) {
        if (a.exact && b.exact) {
            std::vector<i64> v = a.vals;
            v.insert(v.end(), b.vals.begin(), b.vals.end());
            r = AV::set(v);
        } else {
            r = AV::range(std::min(a.lo, b.lo), std::max(a.hi, b.hi));
            r.exact = false, r.vals.clear();
            r.lo = std::min(a.lo, b.lo), r.hi = std::max(a.hi, b.hi);
        }
        r.var = a.var == b.var ? a.var : -1;
        r.deps = a.deps | b.deps;
    } else if (a.k == AV::BOOL) {
        r = AV::boolean(a.mt || b.mt, a.mf || b.mf);
    } else {  // LIST: element-wise when the shapes agree
        if (a.list->size() != b.list->size()) return AV::top();
        std::vector<AV> xs;
        std::vector<char> o;
        for (size_t i = 0; i < a.list->size(); ++i) {
            xs.push_back(join((*a.list)[i], (*b.list)[i]));
            o.push_back(a.opt[i] || b.opt[i]);
        }
        r = AV::of_list(std::move(xs), std::move(o));
    }
    r.absent = a.absent || b.absent;
    return r;
}

/// a binary operation on numbers: exact sets pairwise when small, else interval corners (f monotone per argument)
template <class F>
AV arith(const AV& x, const AV& y, F f, bool interval_ok) {
    AV r;
    if (!x.num() || !y.num()) return AV::top();
    if (x.empty_num() || y.empty_num()) return AV::only_absent();
    if (x.exact && y.exact && x.vals.size() * y.vals.size() <= 4096) {
        std::vector<i64> v;
        bool bad = false;
        for (i64 a : x.vals)
            for (i64 b : y.vals) {
                i64 z;
                if (!f(a, b, z)) {
                    bad = true;
                    continue;
                }
                v.push_back(z);
            }
        r = AV::set(v);
        r.absent = x.absent || y.absent || bad;
        r.deps = x.deps | y.deps;
        return r;
    }
    if (!interval_ok) {
        r = AV::top();
        r.k = AV::NUM, r.exact = false;
        r.absent = true;
        return r;
    }
    i64 c[4];
    bool ok = f(x.lo, y.lo, c[0]) & f(x.lo, y.hi, c[1]) & f(x.hi, y.lo, c[2]) & f(x.hi, y.hi, c[3]);
    if (!ok) {
        r.k = AV::NUM, r.exact = false;
        r.absent = true;
        return r;
    }
    r.k = AV::NUM, r.exact = false;
    r.lo = sat(*std::min_element(c, c + 4)), r.hi = sat(*std::max_element(c, c + 4));
    r.absent = x.absent || y.absent;
    r.deps = x.deps | y.deps;
    return r;
}

/// a comparison: may it be true / false (ABSENT on either side: false)
AV compare(int op, const AV& x, const AV& y) {
    if ((op == X_EQ || op == X_NE) && x.k == AV::BOOL && y.k == AV::BOOL) {
        const bool same = (x.mt && y.mt) || (x.mf && y.mf), differ = (x.mt && y.mf) || (x.mf && y.mt);
        return op == X_EQ ? AV::boolean(same, differ) : AV::boolean(differ, same);
    }
    if (!x.num() || !y.num()) {
        if (x.k == AV::TOP || y.k == AV::TOP) return AV::boolean(true, true);
        if (op == X_EQ || op == X_NE) return AV::boolean(true, true);  // lists / booleans: not modelled
        return AV::boolean(false, true);
    }
    bool mt = false, mf = x.absent || y.absent;
    if (x.empty_num() || y.empty_num()) return AV::boolean(false, true);
    auto test = [&](i64 a, i64 b) {
        switch (op) {
            case X_EQ: return a == b;
            case X_NE: return a != b;
            case X_LT: return a < b;
            case X_LE: return a <= b;
            case X_GT: return a > b;
            default: return a >= b;
        }
    };
    if (x.exact && y.exact && x.vals.size() * y.vals.size() <= 4096) {
        for (i64 a : x.vals)
            for (i64 b : y.vals) (test(a, b) ? mt : mf) = true;
        return AV::boolean(mt, mf);
    }
    // intervals
    const i64 a0 = x.lo, a1 = x.hi, b0 = y.lo, b1 = y.hi;
    switch (op) {
        case X_EQ: mt = a0 <= b1 && b0 <= a1; mf |= !(a0 == a1 && b0 == b1 && a0 == b0); break;
        case X_NE: mt = !(a0 == a1 && b0 == b1 && a0 == b0); mf |= a0 <= b1 && b0 <= a1; break;
        case X_LT: mt = a0 < b1; mf |= a1 >= b0; break;
        case X_LE: mt = a0 <= b1; mf |= a1 > b0; break;
        case X_GT: mt = a1 > b0; mf |= a0 <= b1; break;
        default: mt = a1 >= b0; mf |= a0 < b1; break;
    }
    return AV::boolean(mt, mf);
}

struct AEv {
    const ExprProgram& P;
    const uint32_t* dm;                              ///< per variable: its digits
    const std::vector<std::vector<int>>& aux;        ///< per aux variable: its open values (empty: any)
    std::vector<AV> slots;
    int depth = 0;
    const std::vector<std::vector<int>>* vh = nullptr;  ///< per variable: the whole houses (digits all differ) it is in
    /// per house (as in vh): the least / most its cells outside the rule add up to (lo > hi: unknown) -- a part of a sum
    /// holding all the rule's cells of a whole house is the house total minus that
    const std::vector<std::pair<long long, long long>>* hrest = nullptr;
    int D = 9;
    std::vector<int>* params = nullptr;  ///< records variables (>= 0) / unknowns (-1 - a) read in structural places

    AEv(const ExprProgram& p, const uint32_t* d, const std::vector<std::vector<int>>& a)
        : P(p), dm(d), aux(a), slots(p.nslots) {}
    void param(const AV& v) {
        if (!params || !v.num()) return;
        if (v.var >= 0) params->push_back(v.var);
        else if (v.deps && __builtin_popcountll(v.deps) <= 2)  // computed from one or two cells: "let X = c * mult(c)"
            for (uint64_t m = v.deps; m; m &= m - 1) params->push_back(__builtin_ctzll(m));
    }
    /// do these variables (all different) share a whole house? Then their digits all differ
    int one_house(const std::vector<int>& vars) {  ///< a whole house holding all of them, or -1
        if (!vh || vars.empty()) return -1;
        for (int h : (*vh)[vars[0]]) {
            bool all = true;
            for (int v : vars) all &= std::find((*vh)[v].begin(), (*vh)[v].end(), h) != (*vh)[v].end();
            if (all) return h;
        }
        return -1;
    }

    AV cell(int var) {
        std::vector<i64> v;
        for (uint32_t m = dm[var]; m; m &= m - 1) v.push_back(__builtin_ctz(m) + 1);
        AV a = AV::set(v);
        a.var = var;
        if (var < 64) a.deps = 1ull << var;
        return a;
    }
    AV aux_value(long long i) {
        if (i < 0 || i >= (long long)aux.size() || aux[i].empty()) return AV::top();
        return AV::set(std::vector<i64>(aux[i].begin(), aux[i].end()));
    }
    AV list_value(const ExprList& L) {
        if (L.var >= 0) return cell(L.var);
        std::vector<AV> xs;
        for (const ExprList& x : L.items) xs.push_back(list_value(x));
        return AV::of_list(std::move(xs), std::vector<char>(L.items.size(), 0));
    }
    /// a value as a sequence (a cell: one element)
    bool seq(const AV& v, std::vector<AV>& xs, std::vector<char>& o) {
        if (v.k == AV::LIST) {
            xs = *v.list, o = v.opt;
            o.resize(xs.size(), 0);  // a list with no optional element carries no flags: one per element, none set
            return true;
        }
        if (v.k == AV::NUM && v.var >= 0) {
            xs = {v}, o = {0};
            return true;
        }
        return false;
    }
    AV call_fn(const AV& f, const std::vector<AV>& args) {
        if (f.k != AV::FN || f.fn->params.size() != args.size() || ++depth > 64) return AV::top();
        const std::vector<int>& ps = f.fn->params;
        std::vector<AV> saved;
        for (int s : ps) saved.push_back(slots[s]);
        for (size_t i = 0; i < ps.size(); ++i) slots[ps[i]] = args[i];
        AV r = eval(f.fn->kids[0]);
        for (size_t i = 0; i < ps.size(); ++i) slots[ps[i]] = saved[i];
        --depth;
        return r;
    }
    AV builtin(int id, const std::vector<AV>& a);
    AV eval(const ExprNode& e);
    AV distinct_sum(const ExprNode& comp);
    std::vector<i64> mlo, mhi;  ///< distinct_sum's last DP: per digit mask, the least / most the sum can be
};

/// does term e read only the comprehension variable `slot` (its digit, its cell's layer values) -- numbers, the
/// variable, a layer of it, arithmetic, comparisons, logic? layers: the layers it reads
bool local_term(const ExprNode& e, long long slot, std::vector<long long>& layers) {
    switch (e.op) {
        case X_NUM: case X_BOOL: return true;
        case X_SLOT: return e.v == slot;
        case X_AUXCELL:
            if (e.kids.size() != 1 || e.kids[0].op != X_SLOT || e.kids[0].v != slot) return false;
            if (std::find(layers.begin(), layers.end(), e.v) == layers.end()) layers.push_back(e.v);
            return true;
        case X_ADD: case X_SUB: case X_MUL: case X_DIV: case X_IDIV: case X_MOD: case X_POW: case X_NEG:
        case X_EQ: case X_NE: case X_LT: case X_LE: case X_GT: case X_GE: case X_AND: case X_OR: case X_NOT: case X_IF:
            for (const ExprNode& k : e.kids)
                if (!local_term(k, slot, layers)) return false;
            return true;
        default: return false;
    }
}
/// such a term's [lo, hi] per (program, term, variable, its layer values, digit); lo > hi: no value
thread_local std::unordered_map<std::string, std::pair<i64, i64>> g_term_rows;

/// sum(f(x) for x in L), L cells of one whole house: per cell and digit the values f takes, then a DP over the digits
/// used (all different) keeping each mask's minimum and maximum -> the sum's bounds; TOP when it does not apply
AV AEv::distinct_sum(const ExprNode& comp) {
    std::vector<AV> src;
    std::vector<char> o;
    if (!seq(eval(comp.kids[0]), src, o) || src.empty() || (int)src.size() > D || D > 12) return AV::top();
    std::vector<int> vars;
    for (size_t i = 0; i < src.size(); ++i) {
        if (o[i] || !src[i].num() || src[i].var < 0) return AV::top();
        vars.push_back(src[i].var);
    }
    std::vector<int> u = vars;
    std::sort(u.begin(), u.end());
    if (std::unique(u.begin(), u.end()) != u.end() || one_house(vars) < 0) return AV::top();
    // per element, per digit: [lo, hi] of f
    std::vector<long long> layers;
    const bool local = local_term(comp.kids[1], comp.v, layers);
    std::vector<std::vector<std::pair<i64, i64>>> val(src.size(), std::vector<std::pair<i64, i64>>(D + 1, {BIG, -BIG}));
    const uint32_t* saved = dm;
    const size_t NV = P.row.size();  // the rule's variables (one position each)
    std::vector<uint32_t> dd(dm, dm + NV);
    for (size_t i = 0; i < src.size(); ++i) {
        const int x = vars[i];
        if (x >= (int)dd.size()) return AV::top();
        // a term reading only its own cell (digit, layer values): its value per digit depends on nothing else, so
        // it is kept across reads (a probe changes one cell's row; the others repeat) -- keyed by exactly what it read
        const bool reuse = local && !params && x < (int)P.gcell.size();
        std::string base;
        if (reuse) {
            auto put = [&](i64 v) { base.append(reinterpret_cast<const char*>(&v), sizeof v); };
            put((i64)(uintptr_t)&P), put((i64)(uintptr_t)&comp), put(x);
            for (long long l : layers) {
                const long long ai = P.aux_u + l * (long long)P.aux_n + P.gcell[x];
                put(-1);
                if (ai >= 0 && ai < (long long)aux.size())
                    for (int w : aux[ai]) put(w);
            }
        }
        for (uint32_t m = saved[x]; m; m &= m - 1) {
            const int d = __builtin_ctz(m) + 1;
            std::string key;
            if (reuse) {
                key = base;
                key.push_back((char)d);
                auto it = g_term_rows.find(key);
                if (it != g_term_rows.end()) {
                    if (it->second.first <= it->second.second) val[i][d] = it->second;
                    continue;
                }
            }
            dd.assign(saved, saved + dd.size());
            dd[x] = 1u << (d - 1);
            dm = dd.data();
            AV xv = cell(x);
            slots[comp.v] = xv;
            AV b = eval(comp.kids[1]);
            dm = saved;
            const bool none = !b.num() || b.empty_num();
            if (reuse) {
                if (g_term_rows.size() > 2000000) g_term_rows.clear();
                g_term_rows[key] = none ? std::make_pair(BIG, -BIG) : std::make_pair(b.lo, b.hi);
            }
            if (none) continue;
            val[i][d] = {b.lo, b.hi};
        }
    }
    // DP over the digits used: per mask, the least and the most the elements so far can add up to
    const size_t M = (size_t)1 << D;
    std::vector<i64> lo(M, BIG), hi(M, -BIG), nlo(M, BIG), nhi(M, -BIG);
    lo[0] = hi[0] = 0;
    // over the reachable masks only (a frontier per element; the full 2^D sweep cost ~50 us per read, and probing
    // reads a rule hundreds of thousands of times: Trouble, 2026-11-10)
    std::vector<size_t> act{0}, nact;
    for (size_t i = 0; i < src.size(); ++i) {
        nact.clear();
        for (size_t mk : act) {
            for (int d = 1; d <= D; ++d) {
                if (mk >> (d - 1) & 1 || val[i][d].first > val[i][d].second) continue;
                const size_t n2 = mk | ((size_t)1 << (d - 1));
                if (nlo[n2] > nhi[n2]) nact.push_back(n2);  // first reached in this layer
                nlo[n2] = std::min(nlo[n2], sat(lo[mk] + val[i][d].first));
                nhi[n2] = std::max(nhi[n2], sat(hi[mk] + val[i][d].second));
            }
        }
        for (size_t mk : act) lo[mk] = BIG, hi[mk] = -BIG;
        for (size_t mk : nact) lo[mk] = nlo[mk], hi[mk] = nhi[mk], nlo[mk] = BIG, nhi[mk] = -BIG;
        act.swap(nact);
    }
    mlo = lo, mhi = hi;
    i64 L = BIG, H = -BIG;
    for (size_t mk = 0; mk < M; ++mk)
        if (lo[mk] <= hi[mk]) L = std::min(L, lo[mk]), H = std::max(H, hi[mk]);
    if (L > H) return AV::only_absent();
    AV r = AV::range(L, H);
    if (r.exact) {  // an interval (sums in between are not all reachable): keep it an interval
        r.exact = false, r.vals.clear();
    }
    r.lo = L, r.hi = H;
    return r;
}

// built-in ids (custom.FNS order, as expr.cpp)
enum Builtin { SUM, PRODUCT, MIN, MAX, COUNT, LEN, ALL, ANY, SORT, REVERSE, ABS, ODD, EVEN, PRIME, NUMF, DEFINED,
               ALL_DIFFERENT, COUNT_DISTINCT, CONCAT, MEDIAN, SEEN, UPTO, TAKE_WHILE, TAKE, POSITION, ROW, COL, BOX,
               REGION, SHADED };

bool prime(i64 n) {
    if (n < 2) return false;
    for (i64 d = 2; d * d <= n; ++d)
        if (n % d == 0) return false;
    return true;
}

AV AEv::builtin(int id, const std::vector<AV>& a) {
    std::vector<AV> xs;
    std::vector<char> o;
    auto num_top = [] {
        AV r;
        r.k = AV::NUM, r.exact = false, r.absent = true;
        return r;
    };
    switch (id) {
        case SUM: case PRODUCT: {
            if (!seq(a[0], xs, o)) return a[0].k == AV::TOP ? num_top() : AV::only_absent();
            if (id == SUM && !xs.empty() && D <= 16) {  // cells of one house: distinct digits (a whole house: its total)
                std::vector<int> vars;
                bool cells = true;
                for (size_t i = 0; i < xs.size(); ++i) {
                    cells &= !o[i] && xs[i].num() && xs[i].var >= 0 && xs[i].exact && !xs[i].absent;
                    if (cells) vars.push_back(xs[i].var);
                }
                std::vector<int> u = vars;
                std::sort(u.begin(), u.end());
                const int H = cells ? one_house(vars) : -1;
                if (cells && std::unique(u.begin(), u.end()) == u.end() && (int)vars.size() <= D && H >= 0) {
                    std::vector<char> reach((size_t)1 << D, 0), nxt;
                    reach[0] = 1;
                    for (const AV& x : xs) {
                        nxt.assign(reach.size(), 0);
                        for (size_t m = 0; m < reach.size(); ++m)
                            if (reach[m])
                                for (i64 dgt : x.vals)
                                    if (dgt >= 1 && dgt <= D && !(m >> (dgt - 1) & 1)) nxt[m | ((size_t)1 << (dgt - 1))] = 1;
                        reach.swap(nxt);
                    }
                    // the SECRET: the rest of the house takes the other digits -- the rule's other cells of that house
                    // with their digits, any further cells of it with any digit
                    std::vector<int> comp;
                    for (int v = 0; v < (int)vh->size(); ++v)
                        if (std::find(vars.begin(), vars.end(), v) == vars.end() &&
                            std::find((*vh)[v].begin(), (*vh)[v].end(), H) != (*vh)[v].end())
                            comp.push_back(v);
                    const int extra = D - (int)vars.size() - (int)comp.size();
                    for (size_t m = 0; m < reach.size(); ++m) {
                        if (!reach[m] || comp.empty()) continue;
                        std::vector<char> r2(reach.size(), 0), n2;
                        r2[m] = 1;
                        for (int v : comp) {
                            n2.assign(r2.size(), 0);
                            for (size_t q = 0; q < r2.size(); ++q)
                                if (r2[q])
                                    for (uint32_t dd = dm[v]; dd; dd &= dd - 1) {
                                        const int dgt = __builtin_ctz(dd);
                                        if (dgt < D && !(q >> dgt & 1)) n2[q | ((size_t)1 << dgt)] = 1;
                                    }
                            r2.swap(n2);
                        }
                        bool ok = false;
                        for (size_t q = 0; q < r2.size() && !ok; ++q) ok = r2[q] && __builtin_popcountll(q) == D - extra;
                        if (!ok) reach[m] = 0;
                    }
                    std::vector<i64> sums;
                    for (size_t m = 0; m < reach.size(); ++m)
                        if (reach[m]) {
                            i64 t = 0;
                            for (int dgt = 1; dgt <= D; ++dgt) t += (m >> (dgt - 1) & 1) ? dgt : 0;
                            sums.push_back(t);
                        }
                    return AV::set(sums);
                }
                // cells over several houses ("columns 7-8 whole and four cells of box 8"): split greedily by the house
                // holding most of the rest; each part's digits differ -> its k smallest / largest open digits
                if (cells && vh && xs.size() > 1) {
                    std::vector<int> uu = vars;
                    std::sort(uu.begin(), uu.end());
                    if (std::adjacent_find(uu.begin(), uu.end()) == uu.end()) {
                        std::vector<size_t> rest(xs.size());
                        for (size_t i = 0; i < xs.size(); ++i) rest[i] = i;
                        i64 glo = 0, ghi = 0;
                        bool ok = true, grouped = false;
                        while (!rest.empty() && ok) {
                            std::map<int, int> cnt;
                            for (size_t i : rest)
                                for (int h : (*vh)[vars[i]]) ++cnt[h];
                            int bh = -1, bc = 1;
                            for (auto [h, c] : cnt)
                                if (c > bc) bh = h, bc = c;
                            std::vector<size_t> grp, keep;
                            for (size_t i : rest) {
                                const bool in = bh < 0 ? grp.empty()
                                                       : std::find((*vh)[vars[i]].begin(), (*vh)[vars[i]].end(), bh) !=
                                                             (*vh)[vars[i]].end();
                                (in ? grp : keep).push_back(i);
                            }
                            uint32_t uni = 0;
                            for (size_t i : grp)
                                for (i64 dgt : xs[i].vals)
                                    if (dgt >= 1 && dgt <= D) uni |= 1u << (dgt - 1);
                            const int k = (int)grp.size();
                            if (__builtin_popcount(uni) < k) { ok = false; break; }
                            i64 plo = 0, phi = 0;
                            int n1 = 0, n2 = 0;
                            for (int dgt = 1; dgt <= D && n1 < k; ++dgt)
                                if (uni >> (dgt - 1) & 1) plo += dgt, ++n1;
                            for (int dgt = D; dgt >= 1 && n2 < k; --dgt)
                                if (uni >> (dgt - 1) & 1) phi += dgt, ++n2;
                            // the part holds all the rule's cells of house bh: the house total minus its other cells
                            if (bh >= 0 && hrest && bh < (int)hrest->size() && (*hrest)[bh].first <= (*hrest)[bh].second) {
                                int in_rule = 0;
                                for (int v : vars)
                                    in_rule += std::find((*vh)[v].begin(), (*vh)[v].end(), bh) != (*vh)[v].end();
                                if (in_rule == k) {
                                    const i64 tot = (i64)D * (D + 1) / 2;
                                    plo = std::max(plo, tot - (i64)(*hrest)[bh].second);
                                    phi = std::min(phi, tot - (i64)(*hrest)[bh].first);
                                }
                            }
                            if (plo > phi) { ok = false; break; }
                            glo += plo, ghi += phi;
                            grouped |= k > 1;
                            rest = keep;
                        }
                        if (ok && grouped) {
                            AV r = AV::range(glo, ghi);
                            r.exact = false, r.vals.clear(), r.lo = glo, r.hi = ghi;
                            return r;
                        }
                    }
                }
            }
            AV acc = AV::set({id == SUM ? 0 : 1});
            const i64 unit = id == SUM ? 0 : 1;
            for (size_t i = 0; i < xs.size(); ++i) {
                AV x = xs[i];
                if (!x.num()) return num_top();
                if (o[i]) x = join(x, AV::set({unit}));
                acc = id == SUM ? arith(acc, x, [](i64 p, i64 q, i64& z) { z = sat(p + q); return true; }, true)
                                : arith(acc, x, [](i64 p, i64 q, i64& z) { z = smul(p, q); return true; }, true);
                if (id == PRODUCT && !acc.exact) {  // corners are not enough for signed factors: widen
                    acc.lo = -BIG, acc.hi = BIG;
                    bool nonneg = true;
                    for (const AV& y : xs) nonneg &= y.num() && y.lo >= 0;
                    if (nonneg) acc.lo = 0;
                }
            }
            return acc;
        }
        case MIN: case MAX: {
            if (a.size() == 2) xs = {a[0], a[1]}, o = {0, 0};
            else if (!seq(a[0], xs, o)) return num_top();
            if (xs.empty()) return AV::only_absent();
            i64 lo = BIG, hi = -BIG, must = id == MIN ? BIG : -BIG;
            bool any_must = false, absent = false;
            for (size_t i = 0; i < xs.size(); ++i) {
                if (!xs[i].num()) return num_top();
                absent |= xs[i].absent;
                if (xs[i].empty_num()) continue;
                lo = std::min(lo, xs[i].lo), hi = std::max(hi, xs[i].hi);
                if (!o[i]) {
                    any_must = true;
                    must = id == MIN ? std::min(must, xs[i].hi) : std::max(must, xs[i].lo);
                }
            }
            if (lo > hi) return AV::only_absent();
            if (any_must) (id == MIN ? hi : lo) = must;  // the min is at most any kept element; the max at least
            AV r = AV::range(lo, hi);
            r.absent = absent || !any_must;
            return r;
        }
        case COUNT: case LEN: {
            if (!seq(a[0], xs, o)) return num_top();
            i64 lo = 0, hi = 0;
            for (size_t i = 0; i < xs.size(); ++i) {
                bool may = true, must = !o[i];
                if (id == COUNT && xs[i].k == AV::BOOL) may = xs[i].mt, must = must && !xs[i].mf;
                else if (id == COUNT && xs[i].k == AV::TOP) must = false;
                hi += may, lo += must;
            }
            return AV::range(lo, hi);
        }
        case ALL: case ANY: {
            if (!seq(a[0], xs, o)) return AV::boolean(true, true);
            bool all_t = true, any_f = false, any_t = false, all_f = true;
            for (size_t i = 0; i < xs.size(); ++i) {
                const bool t = xs[i].k != AV::BOOL || xs[i].mt, f = xs[i].k != AV::BOOL || xs[i].mf;
                all_t &= t || o[i];
                any_f |= f;
                any_t |= t;
                all_f &= f || o[i];
            }
            return id == ALL ? AV::boolean(all_t, any_f) : AV::boolean(any_t, all_f);
        }
        case ABS: {
            if (!a[0].num()) return num_top();
            AV z = AV::set({0});
            return arith(a[0], z, [](i64 p, i64, i64& r) { r = p < 0 ? -p : p; return true; }, false).k == AV::TOP
                       ? num_top()
                       : (a[0].exact ? arith(a[0], z, [](i64 p, i64, i64& r) { r = p < 0 ? -p : p; return true; }, false)
                                     : AV::range(a[0].lo >= 0 ? a[0].lo : a[0].hi <= 0 ? -a[0].hi : 0,
                                                 std::max(a[0].hi, -a[0].lo)));
        }
        case ODD: case EVEN: case PRIME: {
            if (!a[0].num()) return AV::boolean(true, true);
            if (!a[0].exact) return AV::boolean(true, true);
            bool t = false, f = a[0].absent;
            for (i64 v : a[0].vals) {
                const bool h = id == PRIME ? prime(v) : ((v % 2 + 2) % 2 == 1) == (id == ODD);
                (h ? t : f) = true;
            }
            return AV::boolean(t, f);
        }
        case NUMF: {
            if (a[0].k != AV::BOOL) return AV::range(0, 1);
            std::vector<i64> v;
            if (a[0].mt) v.push_back(1);
            if (a[0].mf) v.push_back(0);
            return AV::set(v);
        }
        case DEFINED:
            if (a[0].k == AV::TOP) return AV::boolean(true, true);
            return AV::boolean(!a[0].empty_num(), a[0].absent);
        case ALL_DIFFERENT: case COUNT_DISTINCT: {
            if (!seq(a[0], xs, o)) return id == ALL_DIFFERENT ? AV::boolean(true, true) : num_top();
            for (char x : o)
                if (x) return id == ALL_DIFFERENT ? AV::boolean(true, true) : AV::range(0, (i64)xs.size());
            bool clash_possible = false, clash_sure = false;
            for (size_t i = 0; i < xs.size(); ++i)
                for (size_t j = i + 1; j < xs.size(); ++j) {
                    const AV& p = xs[i];
                    const AV& q = xs[j];
                    if (!p.num() || !q.num() || !p.exact || !q.exact) {
                        clash_possible = true;
                        continue;
                    }
                    bool meet = false;
                    for (i64 v : p.vals) meet |= std::binary_search(q.vals.begin(), q.vals.end(), v);
                    clash_possible |= meet;
                    clash_sure |= p.vals.size() == 1 && q.vals.size() == 1 && p.vals[0] == q.vals[0];
                }
            if (id == ALL_DIFFERENT) {
                // pigeonhole: n elements over fewer values cannot all differ
                std::vector<i64> uni;
                bool all_exact = true;
                for (const AV& x : xs) {
                    if (!x.num() || !x.exact) all_exact = false;
                    else uni.insert(uni.end(), x.vals.begin(), x.vals.end());
                }
                std::sort(uni.begin(), uni.end());
                uni.erase(std::unique(uni.begin(), uni.end()), uni.end());
                if (all_exact && uni.size() < xs.size()) clash_sure = true;
                return AV::boolean(!clash_sure, clash_possible);
            }
            return AV::range(xs.empty() ? 0 : 1, (i64)xs.size());
        }
        case REVERSE: {
            if (!seq(a[0], xs, o)) return AV::top();
            std::reverse(xs.begin(), xs.end());
            std::reverse(o.begin(), o.end());
            return AV::of_list(std::move(xs), std::move(o));
        }
        case SORT: {
            if (!seq(a[0], xs, o)) return AV::top();
            AV hull = AV::only_absent();
            for (const AV& x : xs) {
                if (!x.num()) return AV::top();
                hull = join(hull, x);
            }
            for (AV& x : xs) x = hull, x.var = -1;
            return AV::of_list(std::move(xs), std::move(o));
        }
        case ROW: case COL: case BOX: {
            if (!a[0].num() || a[0].var < 0) return num_top();
            const int r = P.row[a[0].var], c = P.col[a[0].var];
            if (id == ROW) return AV::set({r});
            if (id == COL) return AV::set({c});
            return AV::set({(r - 1) / P.box_h * P.box_h + (c - 1) / P.box_w + 1});
        }
        case TAKE: {  // the first n of a list
            param(a[0]);
            if (!a[0].num() || !seq(a[1], xs, o)) return AV::top();
            for (char x : o)
                if (x) return AV::top();
            AV r;
            bool first = true;
            std::vector<i64> ns = a[0].exact ? std::vector<i64>(a[0].vals) : std::vector<i64>{};
            if (!a[0].exact || ns.size() > 16) return AV::top();
            for (i64 n : ns) {
                AV part = n < 0 || n > (i64)xs.size()
                              ? AV::only_absent()
                              : AV::of_list(std::vector<AV>(xs.begin(), xs.begin() + n), std::vector<char>(n, 0));
                r = first ? part : join(r, part);
                first = false;
            }
            if (a[0].absent) r = join(r, AV::only_absent());
            return first ? AV::only_absent() : r;
        }
        case REGION: return num_top();
        case SHADED: return AV::boolean(true, true);
        default: break;  // concat, median, seen, upto, take_while, take, position: not modelled
    }
    if (id == UPTO || id == TAKE_WHILE || id == SEEN) return AV::top();
    return num_top();
}

AV AEv::eval(const ExprNode& e) {
    const auto& K = e.kids;
    switch (e.op) {
        case X_NUM: return AV::set({e.v});
        case X_BOOL: return AV::boolean(e.v != 0, e.v == 0);
        case X_CELLS: return list_value(P.lists[e.v]);
        case X_CELL: return cell((int)e.v);
        case X_SLOT: return slots[e.v];
        case X_AUX:
            if (params) params->push_back(-1 - (int)e.v);
            return aux_value(e.v);
        case X_AUXCELL: {
            AV c = eval(K[0]);
            if (!c.num() || c.var < 0 || c.var >= (int)P.gcell.size()) return AV::top();
            const long long ai = P.aux_u + e.v * (long long)P.aux_n + P.gcell[c.var];
            if (params) params->push_back(-1 - (int)ai);
            return aux_value(ai);
        }
        case X_LIST: {
            std::vector<AV> xs;
            for (const ExprNode& k : K) xs.push_back(eval(k));
            return AV::of_list(std::move(xs), std::vector<char>(K.size(), 0));
        }
        case X_RANGE: {
            AV lo = eval(K[0]), hi = eval(K[1]);
            param(lo), param(hi);
            if (!lo.num() || !hi.num() || !lo.exact || !hi.exact || lo.vals.size() != 1 || hi.vals.size() != 1)
                return AV::top();
            std::vector<AV> xs;
            for (i64 k = lo.vals[0]; k <= hi.vals[0] && xs.size() <= 1024; ++k) xs.push_back(AV::set({k}));
            return AV::of_list(std::move(xs), std::vector<char>(xs.size(), 0));
        }
        case X_COMP: {
            std::vector<AV> src, out;
            std::vector<char> o, oo;
            AV s = eval(K[0]);
            if (!seq(s, src, o)) return AV::top();
            for (size_t i = 0; i < src.size(); ++i) {
                slots[e.v] = src[i];
                bool maybe_out = o[i];
                if (K[2].op != X_NONE) {
                    AV c = eval(K[2]);
                    const bool t = c.k != AV::BOOL || c.mt, f = c.k != AV::BOOL || c.mf;
                    if (!t) continue;
                    maybe_out |= f;
                }
                out.push_back(eval(K[1]));
                oo.push_back(maybe_out);
            }
            return AV::of_list(std::move(out), std::move(oo));
        }
        case X_LET:
            slots[e.v] = eval(K[0]);
            return eval(K[1]);
        case X_LETFN: {
            AV f;
            f.k = AV::FN, f.fn = &e;
            slots[e.v] = f;
            return eval(K[1]);
        }
        case X_LAMBDA: {
            AV f;
            f.k = AV::FN, f.fn = &e;
            return f;
        }
        case X_IF: {
            AV c = eval(K[0]);
            if (c.k != AV::BOOL) return AV::top();
            if (c.mt && c.mf) return join(eval(K[1]), eval(K[2]));
            if (c.mt) return eval(K[1]);
            if (c.mf) return eval(K[2]);
            return AV::top();
        }
        case X_DEFAULT: {
            AV v = eval(K[0]);
            if (v.k == AV::TOP) return AV::top();
            if (!v.absent) return v;
            AV w = eval(K[1]);
            AV v2 = v;
            v2.absent = false;
            return v.empty_num() ? w : join(v2, w);
        }
        case X_OR: case X_AND: {
            AV x = eval(K[0]);
            const bool xt = x.k != AV::BOOL ? x.k == AV::TOP : x.mt, xf = x.k != AV::BOOL || x.mf;
            // and: true needs x true and y true; false if x false or y false (y only read when x true)
            if (e.op == X_AND && !xt) return AV::boolean(false, true);
            if (e.op == X_OR && !xf) return AV::boolean(true, false);
            AV y = eval(K[1]);
            const bool yt = y.k != AV::BOOL ? y.k == AV::TOP : y.mt, yf = y.k != AV::BOOL || y.mf;
            if (e.op == X_AND) return AV::boolean(xt && yt, xf || yf);
            return AV::boolean(xt || yt, xf && yf);
        }
        case X_NOT: {
            AV x = eval(K[0]);
            if (x.k != AV::BOOL) return AV::boolean(x.k == AV::TOP, true);
            return AV::boolean(x.mf, x.mt);
        }
        case X_EQ: case X_NE: case X_LT: case X_LE: case X_GT: case X_GE:
            return compare(e.op, eval(K[0]), eval(K[1]));
        case X_IN: case X_NOTIN: {
            AV x = eval(K[0]), S = eval(K[1]);
            std::vector<AV> s;
            std::vector<char> o;
            if (x.k == AV::TOP || !seq(S, s, o)) return AV::boolean(true, true);
            bool t = false, f = !x.num();
            if (x.num()) {
                // in: some element equal; not in: every element different (a dropped element counts as different)
                bool all_ne_possible = true, any_eq_possible = false, any_eq_sure = false;
                for (size_t i = 0; i < s.size(); ++i) {
                    AV c = compare(X_EQ, x, s[i]);
                    any_eq_possible |= c.mt;
                    if (!o[i] && c.mt && !c.mf) any_eq_sure = true;
                    all_ne_possible &= c.mf || o[i];
                }
                t = any_eq_possible, f |= !any_eq_sure && all_ne_possible;
                f |= x.absent;
            }
            return e.op == X_IN ? AV::boolean(t, f) : AV::boolean(f, t);
        }
        case X_ADD: return arith(eval(K[0]), eval(K[1]), [](i64 a, i64 b, i64& z) { z = sat(a + b); return true; }, true);
        case X_SUB: return arith(eval(K[0]), eval(K[1]), [](i64 a, i64 b, i64& z) { z = sat(a - b); return true; }, true);
        case X_MUL: {
            AV x = eval(K[0]), y = eval(K[1]);
            return arith(x, y, [](i64 a, i64 b, i64& z) { z = smul(a, b); return true; }, true);
        }
        case X_IDIV: case X_MOD: {
            AV x = eval(K[0]), y = eval(K[1]);
            param(y);
            auto f = [&](i64 a, i64 b, i64& z) {
                if (b == 0) return false;
                i64 q = a / b - ((a % b != 0) && ((a < 0) != (b < 0)) ? 1 : 0);
                z = e.op == X_IDIV ? q : a - b * q;
                return true;
            };
            if (x.num() && y.num() && y.exact && y.vals.size() == 1 && y.vals[0] > 0 && !x.exact && e.op == X_MOD) {
                AV r = AV::range(0, y.vals[0] - 1);
                r.absent = x.absent || y.absent;
                return r;
            }
            return arith(x, y, f, false);
        }
        case X_POW: {
            AV x = eval(K[0]), y = eval(K[1]);
            return arith(x, y, [](i64 a, i64 b, i64& z) {
                if (b < 0 || b > 62) return false;
                i64 n = 1;
                for (i64 k = 0; k < b; ++k) n = smul(n, a);
                z = n;
                return true;
            }, false);
        }
        case X_NEG: {
            AV x = eval(K[0]);
            return arith(AV::set({0}), x, [](i64 a, i64 b, i64& z) { z = a - b; return true; }, true);
        }
        case X_INDEX: {
            AV L = eval(K[0]), i = eval(K[1]);
            param(i);
            std::vector<AV> s;
            std::vector<char> o;
            if (!seq(L, s, o) || !i.num()) return AV::top();
            for (char x : o)
                if (x) return AV::top();  // positions shift when a filter drops elements
            AV r = AV::only_absent();
            r.absent = false;
            bool out = i.absent;
            if (i.exact) {
                for (i64 k : i.vals) {
                    if (k < 1 || k > (i64)s.size()) out = true;
                    else r = join(r, s[k - 1]);
                }
            } else {
                for (i64 k = std::max<i64>(1, i.lo); k <= std::min<i64>((i64)s.size(), i.hi); ++k) r = join(r, s[k - 1]);
                out |= i.lo < 1 || i.hi > (i64)s.size();
            }
            r.absent |= out;
            return r;
        }
        case X_CALL: {
            // sum(f(x) for x in L) over cells of one house: their digits all differ -- each cell's f per digit, and a
            // digit-mask DP for the bounds ("six distinct digits, each at least itself after doubling: at least 21")
            if (e.v == SUM && K.size() == 1 && K[0].op == X_COMP && K[0].kids[2].op == X_NONE && vh) {
                AV r = distinct_sum(K[0]);
                if (r.k == AV::NUM) return r;
            }
            std::vector<AV> args;
            for (const ExprNode& k : K) args.push_back(eval(k));
            return builtin((int)e.v, args);
        }
        case X_CALLFN: {
            std::vector<AV> args;
            for (const ExprNode& k : K) args.push_back(eval(k));
            return call_fn(slots[e.v], args);
        }
        default: break;  // division (rationals), slices: not modelled
    }
    return AV::top();
}

/// the rule's top-level conjuncts (through let / letfn): each with the bindings before it
void conjuncts(const ExprNode& e, std::vector<const ExprNode*>& lets, std::vector<std::pair<std::vector<const ExprNode*>, const ExprNode*>>& out) {
    if (e.op == X_LET || e.op == X_LETFN) {
        lets.push_back(&e);
        conjuncts(e.kids[1], lets, out);
        lets.pop_back();
        return;
    }
    if (e.op == X_AND) {
        conjuncts(e.kids[0], lets, out);
        conjuncts(e.kids[1], lets, out);
        return;
    }
    out.push_back({lets, &e});
}

AV eval_part(AEv& ev, const std::vector<const ExprNode*>& lets, const ExprNode& c) {
    for (const ExprNode* l : lets) {
        if (l->op == X_LET) {
            ev.slots[l->v] = ev.eval(l->kids[0]);
        } else {
            AV f;
            f.k = AV::FN, f.fn = l;
            ev.slots[l->v] = f;
        }
    }
    return ev.eval(c);
}

}  // namespace

std::vector<RuleLemma> expr_rule_lemmas(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                                        const std::vector<std::vector<int>>& var_houses,
                                        const std::vector<std::vector<int>>& aux_dom) {
    std::vector<RuleLemma> out;
    const int nv = (int)dom.size();
    std::vector<const ExprNode*> lets;
    std::vector<std::pair<std::vector<const ExprNode*>, const ExprNode*>> parts;
    conjuncts(prog.root, lets, parts);
    std::vector<std::vector<int>> ad = aux_dom;  // a case fixes one unknown / layer value here
    auto run = [&](const std::vector<uint32_t>& dm, size_t ci, std::vector<int>* params) {
        AEv ev(prog, dm.data(), ad);
        ev.vh = &var_houses, ev.D = D, ev.params = params;
        AV r = ci < parts.size() ? eval_part(ev, parts[ci].first, *parts[ci].second) : ev.eval(prog.root);
        if (r.k != AV::BOOL) return std::make_pair(true, true);
        return std::make_pair(r.mt, r.mf);
    };
    // a variable: a cell (x >= 0, its digits) or an unknown / layer value (x < 0: aux -1 - x, its values)
    std::vector<uint32_t> dm = dom;
    auto values = [&](int x) {
        std::vector<int> v;
        if (x >= 0)
            for (uint32_t m = dm[x]; m; m &= m - 1) v.push_back(__builtin_ctz(m) + 1);
        else
            v = ad[-1 - x];
        return v;
    };
    auto fix = [&](int x, int v) {
        if (x >= 0) dm[x] = 1u << (v - 1);
        else ad[-1 - x] = {v};
    };
    auto reset = [&](int x) {
        if (x >= 0) dm[x] = dom[x];
        else ad[-1 - x] = aux_dom[-1 - x];
    };
    auto open = [&](int x) {
        const size_t n = values(x).size();
        return n >= 2 && n <= 64;
    };
    auto share = [&](int x, int y) {  // two cells of one house: their digits differ
        if (x < 0 || y < 0) return false;
        for (int h : var_houses[x])
            if (std::find(var_houses[y].begin(), var_houses[y].end(), h) != var_houses[y].end()) return true;
        return false;
    };
    // the fewest variables (1, 2, then 3 for a small rule) whose values decide the case: their allowed values, or
    // false when no such set is found
    auto decide = [&](size_t ci, int p, const std::vector<int>& vars, int max_size, RuleLemma& L) {
        std::vector<int> C;
        std::function<bool(size_t, int)> pick = [&](size_t from, int left) -> bool {
            if (left == 0) {
                std::vector<std::vector<int>> allowed;
                std::vector<int> cur;
                size_t total = 0;
                bool decisive = true;
                std::function<void(size_t)> go = [&](size_t i) {
                    if (!decisive) return;
                    if (i == C.size()) {
                        ++total;
                        auto [t, f2] = run(dm, ci, nullptr);
                        if (t && f2) decisive = false;
                        else if (t) allowed.push_back(cur);
                        return;
                    }
                    for (int x : values(C[i])) {
                        bool clash = false;  // cells of one house: digits differ
                        for (size_t j = 0; j < i; ++j) clash |= share(C[i], C[j]) && cur[j] == x;
                        if (clash) continue;
                        fix(C[i], x);
                        cur.push_back(x);
                        go(i + 1);
                        cur.pop_back();
                        reset(C[i]);
                        if (!decisive) return;
                    }
                };
                go(0);
                if (!decisive || allowed.size() == total) return false;
                if (allowed.empty()) {
                    L.kind = 0;  // no value of the deciding variables works: impossible
                } else {
                    L.kind = 1, L.total = (int)total, L.allowed = std::move(allowed), L.cells = C;
                }
                return true;
            }
            for (size_t k = from; k < vars.size(); ++k) {
                if (vars[k] == p || !open(vars[k])) continue;
                C.push_back(vars[k]);
                if (pick(k + 1, left - 1)) return true;
                C.pop_back();
            }
            return false;
        };
        for (int size = 1; size <= max_size; ++size) {
            if (size == 2 && vars.size() > 24) break;
            C.clear();
            if (pick(0, size)) return true;
        }
        return false;
    };
    // a part saying something does not hold: "x == false" / "x != true" / "not x" (a missing arrow, a dot not shown)
    auto negative = [&](size_t ci) {
        if (ci >= parts.size()) return false;
        const ExprNode& e = *parts[ci].second;
        if (e.op == X_NOT) return true;
        if ((e.op == X_EQ || e.op == X_NE) && e.kids.size() == 2)
            for (const ExprNode& k : e.kids)
                if (k.op == X_BOOL) return (e.op == X_EQ) == (k.v == 0);
        return false;
    };
    // each conjunct, then the whole rule (relations between its parts: "arrows for 3 come in pairs")
    const size_t n_parts = parts.size() > 1 ? parts.size() + 1 : parts.size();
    for (size_t ci = 0; ci < n_parts; ++ci) {
        const bool whole = ci == parts.size();
        std::vector<int> ps;
        run(dm, ci, &ps);  // structural reads (and every unknown / layer value read)
        std::sort(ps.begin(), ps.end());
        ps.erase(std::unique(ps.begin(), ps.end()), ps.end());
        // the variables a decisive set may use: the rule's cells and the unknowns / layer values it reads
        std::vector<int> vars;
        for (int x = 0; x < nv; ++x) vars.push_back(x);
        for (int x : ps)
            if (x < 0) vars.push_back(x);
        if (vars.size() > 40) continue;  // a wide rule: left to set theory and the other techniques for now
        // a small rule's part: every variable is a parameter (hosts case-split on digits too: "a 1 on the tip ...");
        // the whole rule: its structural parameters only, deciding sets up to 3
        if (!whole && vars.size() <= 12) ps = vars;  // a thermo of 5 cells with their layer values: 10
        const int max_size = whole && vars.size() <= 8 ? 3 : 2;
        for (int p : ps) {
            if (!open(p)) continue;
            for (int v : values(p)) {
                const std::vector<uint32_t> dm_save = dm;
                const std::vector<std::vector<int>> ad_save = ad;
                fix(p, v);
                auto [mt, mf] = run(dm, ci, nullptr);
                // a small rule: narrow the case by probing -- each other variable keeps the values under which the rule
                // can still hold, to a fixpoint; a chain of comparisons is followed link by link ("a plain 9 on a thermo
                // middle needs a hot 9 above it, and then nothing fits above that")
                if (mt && vars.size() <= 12) {
                    for (bool changed = true; changed && mt;) {
                        changed = false;
                        for (int x : vars) {
                            if (x == p) continue;
                            const std::vector<int> was = values(x);
                            if (was.size() < 2) continue;
                            std::vector<int> keep;
                            for (int w : was) {
                                bool taken = false;  // a cell of a shared house already holds w
                                if (x >= 0)
                                    for (int y = 0; y < nv && !taken; ++y)
                                        taken = y != x && dm[y] == (1u << (w - 1)) && share(x, y);
                                if (taken) continue;
                                fix(x, w);
                                if (run(dm, ci, nullptr).first) keep.push_back(w);
                            }
                            if (x >= 0) {
                                uint32_t m = 0;
                                for (int w : keep) m |= 1u << (w - 1);
                                dm[x] = m;
                            } else {
                                ad[-1 - x] = keep;
                            }
                            if (keep.empty()) { mt = false; break; }
                            if (keep.size() < was.size()) changed = true;
                        }
                    }
                    if (mt) std::tie(mt, mf) = run(dm, ci, nullptr);
                }
                RuleLemma L;
                L.conj = (int)ci, L.param = p, L.value = v, L.negative = negative(ci);
                if (!mt) {
                    L.kind = 0;  // impossible
                    out.push_back(L);
                } else {
                    // what the case forces on each other variable (the narrowing): "r4c4 = 9 -> r4c4 is cold"
                    for (int x : vars) {
                        if (x == p) continue;
                        std::vector<int> now = values(x), was;
                        if (x >= 0)
                            for (uint32_t m = dm_save[x]; m; m &= m - 1) was.push_back(__builtin_ctz(m) + 1);
                        else
                            was = ad_save[-1 - x];
                        if (now.empty() || now.size() >= was.size()) continue;
                        RuleLemma F = L;
                        F.kind = 1, F.cells = {x}, F.total = (int)was.size();
                        for (int w : now) F.allowed.push_back({w});
                        out.push_back(F);
                    }
                    if (mf && decide(ci, p, vars, max_size, L)) out.push_back(L);
                }
                dm = dm_save, ad = ad_save;
            }
        }
    }
    return out;
}

namespace {
/// P(x) of a count part "count(P(x) for x in L [if C])": may it be true / may it be false
std::pair<bool, bool> part_pred(const ExprNode& comp, AEv& e2, const AV& x) {
    e2.slots[comp.v] = x;
    bool t = true, f = false;
    if (comp.kids[2].op != X_NONE) {
        AV cnd = e2.eval(comp.kids[2]);
        if (cnd.k == AV::BOOL) t = cnd.mt, f = cnd.mf;
        else if (cnd.k != AV::TOP) t = false, f = true;
        else f = true;
    }
    AV b = e2.eval(comp.kids[1]);
    const bool bt = b.k != AV::BOOL || b.mt, bf = b.k == AV::BOOL ? b.mf : b.k == AV::TOP;
    return {t && bt, f || bf};
}

/// a structural hash of an expression (op, value, children): two rules' count parts with the same hash count the same
/// predicate ("each H" instances differ only in their cell lists)
uint64_t node_hash(const ExprNode& e) {
    uint64_t h = 1469598103934665603ull ^ (uint64_t)(e.op * 131 + 7);
    h = (h ^ (uint64_t)e.v) * 1099511628211ull;
    for (const ExprNode& k : e.kids) h = (h ^ node_hash(k)) * 1099511628211ull;
    return h;
}
}  // namespace

CountMoves expr_count_moves(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                            const std::vector<std::vector<int>>& aux_dom, bool check_only, const CountQuery* q,
                            bool exclusive) {
    CountMoves out;
    std::vector<const ExprNode*> lets;
    std::vector<std::pair<std::vector<const ExprNode*>, const ExprNode*>> parts;
    conjuncts(prog.root, lets, parts);
    std::vector<uint32_t> dm = dom;
    // the domains are set one value at a time IN PLACE and restored before returning (a copy per call was 40% of a
    // 13-layer puzzle's grade); every caller passes its own non-const vector
    auto& ad = const_cast<std::vector<std::vector<int>>&>(aux_dom);
    // the parts, with "all(Q(d) for d in <constants>)" expanded into one part per value of d (bound in its slot) and
    // "and" split: "each digit doubled once" is nine counts, nine virtual houses
    struct Item {
        std::vector<const ExprNode*> prefix;
        const ExprNode* node;
        std::vector<std::pair<int, AV>> binds;
    };
    std::vector<Item> items;
    auto setup = [&](AEv& ev, const std::vector<const ExprNode*>& prefix, const std::vector<std::pair<int, AV>>& binds) {
        for (const ExprNode* l : prefix) {
            if (l->op == X_LET) {
                ev.slots[l->v] = ev.eval(l->kids[0]);
            } else {
                AV f;
                f.k = AV::FN, f.fn = l;
                ev.slots[l->v] = f;
            }
        }
        for (const auto& [slot, v] : binds) ev.slots[slot] = v;
    };
    std::function<void(const std::vector<const ExprNode*>&, const ExprNode*, std::vector<std::pair<int, AV>>)> expand =
        [&](const std::vector<const ExprNode*>& prefix, const ExprNode* n, std::vector<std::pair<int, AV>> binds) {
            if (n->op == X_AND) {
                expand(prefix, &n->kids[0], binds);
                expand(prefix, &n->kids[1], binds);
                return;
            }
            if (n->op == X_CALL && n->v == ALL && n->kids.size() == 1 && n->kids[0].op == X_COMP &&
                n->kids[0].kids.size() >= 3 && n->kids[0].kids[2].op == X_NONE) {
                const ExprNode& comp = n->kids[0];
                AEv ev(prog, dm.data(), ad);
                ev.D = D;
                setup(ev, prefix, binds);
                std::vector<AV> el;
                std::vector<char> o;
                bool consts = ev.seq(ev.eval(comp.kids[0]), el, o) && el.size() <= 32;
                for (size_t i = 0; consts && i < el.size(); ++i)
                    consts = !o[i] && el[i].num() && el[i].exact && el[i].vals.size() == 1 && el[i].var < 0;
                if (consts) {
                    for (const AV& v : el) {
                        auto b2 = binds;
                        b2.push_back({comp.v, v});
                        expand(prefix, &comp.kids[1], b2);
                    }
                    return;
                }
            }
            items.push_back({prefix, n, binds});
        };
    for (const auto& [prefix, node] : parts) expand(prefix, node, {});
    struct PInfo {
        const ExprNode* comp;
        std::vector<AV> slots;
    };
    std::vector<PInfo> pinfo;  // per reported house: its part, for the exclusivity check below
    for (const Item& it : items) {
        const auto& prefix = it.prefix;
        // count(P(x) for x in L [if C]) == k, either side
        const ExprNode& c = *it.node;
        if (c.op != X_EQ || c.kids.size() != 2) continue;
        int side = -1;
        for (int s2 = 0; s2 < 2; ++s2)
            if (c.kids[s2].op == X_CALL && c.kids[s2].v == COUNT && c.kids[s2].kids.size() == 1 &&
                c.kids[s2].kids[0].op == X_COMP)
                side = s2;
        if (side < 0) continue;
        const ExprNode& comp = c.kids[side].kids[0];
        AEv ev(prog, dm.data(), ad);
        ev.D = D;
        setup(ev, prefix, it.binds);
        AV kv = ev.eval(c.kids[1 - side]);
        if (!kv.num() || !kv.exact || kv.vals.size() != 1) continue;
        const i64 k = kv.vals[0];
        std::vector<AV> src;
        std::vector<char> o;
        if (!ev.seq(ev.eval(comp.kids[0]), src, o)) continue;
        bool bad = false;
        for (char x : o) bad |= x != 0;
        if (bad) continue;
        // P(x) for one element: may it be true / false
        auto pred = [&](AEv& e2, const AV& x) { return part_pred(comp, e2, x); };
        std::vector<char> sure(src.size()), poss(src.size());
        i64 n_sure = 0, n_poss = 0;
        for (size_t i = 0; i < src.size(); ++i) {
            auto [t, f] = pred(ev, src[i]);
            sure[i] = t && !f, poss[i] = t;
            n_sure += sure[i], n_poss += poss[i];
        }
        out.any = true;
        // the part as a house of its predicate (LayerFish): hash of the predicate and its bound values, cells, k
        uint64_t ph = node_hash(comp.kids[1]) ^ (node_hash(comp.kids[2]) << 1);
        for (const auto& [slot, v] : it.binds) ph = (ph ^ (uint64_t)slot ^ ((uint64_t)(v.vals.empty() ? 0 : v.vals[0]) << 20)) * 1099511628211ull;
        {
            CountHouse H;
            H.pred = ph, H.k = (int)k;
            for (size_t i = 0; i < src.size(); ++i) {
                H.vars.push_back(src[i].var);
                H.sure.push_back(sure[i]), H.poss.push_back(poss[i]);
                // the one layer / unknown variable P reads at this element, and the values that make P possible
                int av = -1;
                std::vector<int> pv;
                if (exclusive && src[i].var >= 0) {
                    std::vector<int> reads;
                    AEv e3(prog, dm.data(), ad);
                    e3.D = D, e3.slots = ev.slots, e3.params = &reads;
                    pred(e3, src[i]);
                    for (int r : reads)
                        if (r < 0) { if (av == -1) av = -1 - r; else if (av != -1 - r) av = -2; }
                    if (av >= 0 && ad[av].size() <= 9) {
                        const std::vector<int> was = ad[av];
                        for (int w : was) {
                            ad[av] = {w};
                            AEv e4(prog, dm.data(), ad);
                            e4.D = D, e4.slots = ev.slots;
                            if (pred(e4, e4.cell(src[i].var)).first) pv.push_back(w);
                        }
                        ad[av] = was;
                    } else {
                        av = -1;
                    }
                }
                H.avar.push_back(av), H.pvals.push_back(pv);
            }
            out.houses.push_back(std::move(H));
            pinfo.push_back({&comp, ev.slots});
        }
        bool query_part = false;
        if (q) {  // clear P at the query's cells, in the parts counting its predicate
            if (ph != q->pred) continue;
            query_part = true;
        }
        if (n_sure > k || n_poss < k) {
            out.infeasible = true;
            if (check_only) return out;
            continue;
        }
        if (check_only) continue;
        const bool force_false = query_part || (n_sure == k && n_poss > k), force_true = !query_part && n_poss == k && n_sure < k;
        if (!force_false && !force_true) continue;
        for (size_t i = 0; i < src.size(); ++i) {
            if (sure[i] || !poss[i]) continue;  // decided already
            const int x = src[i].var;
            if (x < 0) continue;  // an element that is not one of the rule's cells
            if (query_part && std::find(q->clear.begin(), q->clear.end(), x) == q->clear.end()) continue;
            // the element's variables: its digit and the unknowns / layer values its P reads
            std::vector<int> reads;
            {
                AEv e3(prog, dm.data(), ad);
                e3.D = D, e3.slots = ev.slots, e3.params = &reads;
                pred(e3, src[i]);
            }
            std::vector<int> vars{x};
            for (int r : reads)
                if (r < 0 && std::find(vars.begin(), vars.end(), r) == vars.end()) vars.push_back(r);
            for (int u : vars) {
                std::vector<int> values;
                if (u >= 0) {
                    for (uint32_t m = dm[u]; m; m &= m - 1) values.push_back(__builtin_ctz(m) + 1);
                } else {
                    values = ad[-1 - u];
                }
                if (values.size() < 2) continue;
                for (int w : values) {
                    if (u >= 0) dm[u] = 1u << (w - 1);
                    else ad[-1 - u] = {w};
                    AEv e4(prog, dm.data(), ad);
                    e4.D = D, e4.slots = ev.slots;
                    auto [t, f] = pred(e4, e4.cell(x));
                    const bool out_w = force_false ? (t && !f) : !t;  // w would make P the wrong way
                    if (u >= 0) dm[u] = dom[u];
                    else ad[-1 - u] = values;
                    if (!out_w) continue;
                    if (u >= 0) out.digits.push_back({u, w});
                    else out.aux.push_back({-1 - u, w});
                }
            }
        }
        out.count_k = (int)k;
    }
    // parts over the same cells whose predicates never hold together for one cell ("doubled" / "tripled"): their counts
    // add up (two special cells per house). Per cell, every combination of the layer values both read (<= 27): one of
    // the two is surely false in each
    if (exclusive)
        for (size_t a = 0; a < out.houses.size(); ++a)
            for (size_t b = a + 1; b < out.houses.size(); ++b) {
                if (out.houses[a].vars != out.houses[b].vars || out.houses[a].pred == out.houses[b].pred) continue;
                bool excl = true;
                for (int x : out.houses[a].vars) {
                    if (x < 0) { excl = false; break; }
                    std::vector<int> reads;
                    for (size_t s2 : {a, b}) {
                        AEv e(prog, dm.data(), ad);
                        e.D = D, e.slots = pinfo[s2].slots, e.params = &reads;
                        part_pred(*pinfo[s2].comp, e, e.cell(x));
                    }
                    std::vector<int> R;
                    for (int r : reads)
                        if (r < 0 && std::find(R.begin(), R.end(), -1 - r) == R.end()) R.push_back(-1 - r);
                    size_t combos = 1;
                    for (int r : R) combos *= std::max<size_t>(1, ad[r].size());
                    if (R.empty() || combos > 27) { excl = false; break; }
                    std::vector<size_t> idx(R.size(), 0);
                    std::vector<std::vector<int>> keep(R.size());  // R's domains, set one value at a time in place
                    for (size_t j = 0; j < R.size(); ++j) {
                        keep[j] = ad[R[j]];
                        if (keep[j].empty()) excl = false;  // (no value: nothing to combine)
                    }
                    for (size_t n = 0; n < combos && excl; ++n) {
                        size_t m = n;
                        for (size_t j = 0; j < R.size(); ++j) idx[j] = m % keep[j].size(), m /= keep[j].size();
                        for (size_t j = 0; j < R.size(); ++j) ad[R[j]] = {keep[j][idx[j]]};
                        bool both = true;
                        for (size_t s2 : {a, b}) {
                            AEv e(prog, dm.data(), ad);
                            e.D = D, e.slots = pinfo[s2].slots;
                            both &= part_pred(*pinfo[s2].comp, e, e.cell(x)).first;
                        }
                        if (both) excl = false;
                    }
                    for (size_t j = 0; j < R.size(); ++j) ad[R[j]] = keep[j];
                    if (!excl) break;
                }
                if (excl) out.houses[a].exclusive.push_back((int)b), out.houses[b].exclusive.push_back((int)a);
            }
    std::sort(out.digits.begin(), out.digits.end());
    out.digits.erase(std::unique(out.digits.begin(), out.digits.end()), out.digits.end());
    std::sort(out.aux.begin(), out.aux.end());
    out.aux.erase(std::unique(out.aux.begin(), out.aux.end()), out.aux.end());
    return out;
}

int expr_sum_parity(const ExprProgram& prog, int D, int nv, const std::vector<std::vector<int>>& aux_dom) {
    if (nv < 1 || nv > 10) return -1;
    uint32_t odd = 0, full = D >= 32 ? 0xffffffffu : (1u << D) - 1;
    for (int d = 1; d <= D; d += 2) odd |= 1u << (d - 1);
    int par = -1;
    std::vector<uint32_t> dm(nv);
    for (int pat = 0; pat < (1 << nv); ++pat) {  // each cell odd (bit set) or even
        for (int i = 0; i < nv; ++i) dm[i] = (pat >> i & 1) ? odd : (full & ~odd);
        if (!expr_may_hold(prog, dm.data(), aux_dom)) continue;
        const int q = __builtin_popcount((unsigned)pat) & 1;
        if (par >= 0 && q != par) return -1;
        par = q;
    }
    return par;
}

bool expr_side_bounds(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                      const std::vector<std::vector<int>>& var_houses, const std::vector<std::vector<int>>& aux_dom,
                      long long& lo, long long& hi) {
    const int side = expr_eq_unknown(prog);
    if (side < 0) return false;
    AEv ev(prog, dom.data(), aux_dom);
    ev.vh = &var_houses, ev.D = D;
    AV r = ev.eval(prog.root.kids[1 - side]);
    if (!r.num() || r.empty_num() || r.lo <= -BIG || r.hi >= BIG) return false;
    lo = r.lo, hi = r.hi;
    return true;
}

bool expr_unknown_side_cut(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                           const std::vector<std::vector<int>>& var_houses, const std::vector<std::vector<int>>& aux_dom,
                           std::vector<std::pair<int, int>>& cut,
                           const std::vector<std::pair<long long, long long>>* house_rest) {
    const ExprNode& r = prog.root;
    if (r.op != X_EQ || r.kids.size() != 2) return false;
    std::function<void(const ExprNode&, bool&, std::vector<int>&)> scan = [&](const ExprNode& e, bool& cells,
                                                                            std::vector<int>& aux) {
        if (e.op == X_CELL || e.op == X_CELLS || e.op == X_SLOT || e.op == X_COMP || e.op == X_AUXCELL) cells = true;
        if (e.op == X_AUX && std::find(aux.begin(), aux.end(), (int)e.v) == aux.end()) aux.push_back((int)e.v);
        for (const ExprNode& k : e.kids) scan(k, cells, aux);
    };
    for (int s = 0; s < 2; ++s) {
        bool uc = false, cc = false;
        std::vector<int> ua, ca;
        scan(r.kids[s], uc, ua);
        scan(r.kids[1 - s], cc, ca);
        if (uc || ua.empty() || !cc) continue;
        AEv ev(prog, dom.data(), aux_dom);
        ev.vh = &var_houses, ev.D = D, ev.hrest = house_rest;
        AV c = ev.eval(r.kids[1 - s]);
        if (!c.num() || c.empty_num() || c.lo <= -BIG || c.hi >= BIG) return false;
        for (int a : ua) {
            if (a < 0 || a >= (int)aux_dom.size() || aux_dom[a].size() > 64) continue;
            for (int w : aux_dom[a]) {
                std::vector<std::vector<int>> ad2 = aux_dom;
                ad2[a] = {w};
                AEv e2(prog, dom.data(), ad2);
                e2.D = D;
                AV u = e2.eval(r.kids[s]);
                if (!u.num()) continue;
                bool reach = !u.empty_num() && u.hi >= c.lo && u.lo <= c.hi;
                if (reach && u.exact) {
                    reach = false;
                    for (i64 v : u.vals) reach |= v >= c.lo && v <= c.hi;
                }
                if (!reach) cut.push_back({a, w});
            }
        }
        return true;
    }
    return false;
}

bool expr_eq_mask_bounds(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                         const std::vector<std::vector<int>>& var_houses, const std::vector<std::vector<int>>& aux_dom,
                         std::vector<long long>& lo, std::vector<long long>& hi) {
    const int side = expr_eq_unknown(prog);
    if (side < 0) return false;
    const ExprNode& E = prog.root.kids[1 - side];
    if (E.op != X_CALL || E.v != SUM || E.kids.size() != 1 || E.kids[0].op != X_COMP || E.kids[0].kids[2].op != X_NONE)
        return false;
    AEv ev(prog, dom.data(), aux_dom);
    ev.vh = &var_houses, ev.D = D;
    AV r = ev.distinct_sum(E.kids[0]);
    if (r.k != AV::NUM || ev.mlo.empty()) return false;
    lo.assign(ev.mlo.begin(), ev.mlo.end());
    hi.assign(ev.mhi.begin(), ev.mhi.end());
    return true;
}

bool expr_may_hold(const ExprProgram& prog, const uint32_t* dmask, const std::vector<std::vector<int>>& aux_dom) {
    AEv ev(prog, dmask, aux_dom);
    AV r = ev.eval(prog.root);
    return r.k != AV::BOOL || r.mt;
}

}  // namespace cs
