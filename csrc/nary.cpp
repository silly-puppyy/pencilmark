#include <cstdlib>
#include "portable.hpp"
#include "nary.hpp"

#include <algorithm>
#include <climits>
#include <functional>

namespace cs {

namespace {
inline uint32_t bitd(int d) { return 1u << (d - 1); }

struct Enum {
    const NConstraint& k;
    const uint32_t* dom;
    const std::vector<GacReq>& req;
    pm_long budget;
    int D, nv, np;
    int a[64];
    bool asg[64];
    int lo[64], hi[64];
    pm_long nodes = 0;
    bool aborted = false;
    bool stop_first = false;
    bool found = false;
    uint32_t sup[64];
    pm_long count = 0;
    bool set_unique = true;
    uint32_t must = 0, first_set = 0;

    Enum(const NConstraint& kk, const uint32_t* d, const std::vector<GacReq>& r, pm_long b, int DD)
        : k(kk), dom(d), req(r), budget(b), D(DD), nv(kk.nv()), np((int)kk.pvar.size()) {
        for (int i = 0; i < nv; ++i) {
            asg[i] = false;
            sup[i] = 0;
            uint32_t m = dom[i];
            lo[i] = m ? __builtin_ctz(m) + 1 : 0;
            hi[i] = m ? 32 - __builtin_clz(m) : 0;
            order[i] = k.order[i];
        }
    }
    int order[64];
    inline pm_long pmin(int p) const { int v = k.pvar[p]; return asg[v] ? a[v] : lo[v]; }
    inline pm_long pmax(int p) const { int v = k.pvar[p]; return asg[v] ? a[v] : hi[v]; }

    bool bounds_ok() const {
        switch (k.type) {
            case NT_SUM: {
                pm_long mn = 0, mx = 0;
                for (int p = 0; p < np; ++p) {
                    mn += pmin(p);
                    mx += pmax(p);
                }
                if (!k.totals.empty()) {
                    for (int t : k.totals)
                        if (mn <= t && t <= mx) return true;
                    return false;
                }
                return mn <= k.total && k.total <= mx;
            }
            case NT_ARROW: {
                pm_long cmn = 0, cmx = 0, lmn = 0, lmx = 0;
                for (int p = 0; p < k.ncircle; ++p) {
                    cmn = cmn * 10 + pmin(p);
                    cmx = cmx * 10 + pmax(p);
                }
                for (int p = k.ncircle; p < np; ++p) {
                    lmn += pmin(p);
                    lmx += pmax(p);
                }
                return cmn <= lmx && lmn <= cmx;
            }
            case NT_EQSUM: {
                pm_long mlo = LONG_MIN, mhi = LONG_MAX;
                for (size_t s = 0; s + 1 < k.seg_start.size(); ++s) {
                    pm_long mn = 0, mx = 0;
                    for (int p = k.seg_start[s]; p < k.seg_start[s + 1]; ++p) {
                        mn += pmin(p);
                        mx += pmax(p);
                    }
                    const pm_long sh = (pm_long)k.offset * (k.seg_start[s + 1] - k.seg_start[s]);
                    mn -= sh, mx -= sh;
                    mlo = std::max(mlo, mn);
                    mhi = std::min(mhi, mx);
                }
                return mlo <= mhi;
            }
            case NT_SET: {
                int mn = 99, mx = 0;
                for (int i = 0; i < nv; ++i)
                    if (asg[i]) {
                        mn = std::min(mn, a[i]);
                        mx = std::max(mx, a[i]);
                    }
                return mx == 0 || mx - mn <= nv - 1;
            }
        }
        return true;
    }
    bool pair_ok(int i, int v) const {
        for (int j = 0; j < nv; ++j) {
            if (!asg[j] || j == i) continue;
            if (k.differ[i * nv + j] && a[j] == v) return false;
            const uint32_t* r1 = k.rel[j * nv + i];
            if (r1 && (r1[a[j]] & bitd(v))) return false;
            const uint32_t* r2 = k.rel[i * nv + j];
            if (r2 && (r2[v] & bitd(a[j]))) return false;
        }
        return true;
    }
    bool req_ok() const {
        for (const GacReq& r : req) {
            bool all = true, hit = false;
            for (int i = 0; i < nv; ++i) {
                if (!(r.varmask >> i & 1)) continue;
                if (!asg[i])
                    all = false;
                else if (a[i] == r.v)
                    hit = true;
            }
            if (all && !hit) return false;
        }
        return true;
    }
    void leaf() {
        ++count;
        found = true;
        uint32_t set = 0;
        for (int i = 0; i < nv; ++i) {
            sup[i] |= bitd(a[i]);
            set |= bitd(a[i]);
        }
        if (count == 1) {
            first_set = must = set;
        } else {
            if (set != first_set) set_unique = false;
            must &= set;
        }
    }
    // ---- forward-checking DFS over live domains ----
    static inline int dlo(uint32_t m) { return m ? __builtin_ctz(m) + 1 : 0; }
    static inline int dhi(uint32_t m) { return m ? 32 - __builtin_clz(m) : 0; }
    bool fc_bounds(const uint32_t* d) const {
        auto pmn = [&](int p) { return (pm_long)dlo(d[k.pvar[p]]); };
        auto pmx = [&](int p) { return (pm_long)dhi(d[k.pvar[p]]); };
        switch (k.type) {
            case NT_SUM: {
                pm_long mn = 0, mx = 0;
                for (int p = 0; p < np; ++p) {
                    mn += pmn(p);
                    mx += pmx(p);
                }
                if (!k.totals.empty()) {
                    for (int t : k.totals)
                        if (mn <= t && t <= mx) return true;
                    return false;
                }
                return mn <= k.total && k.total <= mx;
            }
            case NT_ARROW: {
                pm_long cmn = 0, cmx = 0, lmn = 0, lmx = 0;
                for (int p = 0; p < k.ncircle; ++p) {
                    cmn = cmn * 10 + pmn(p);
                    cmx = cmx * 10 + pmx(p);
                }
                for (int p = k.ncircle; p < np; ++p) {
                    lmn += pmn(p);
                    lmx += pmx(p);
                }
                return cmn <= lmx && lmn <= cmx;
            }
            case NT_EQSUM: {
                pm_long mlo = LONG_MIN, mhi = LONG_MAX;
                for (size_t s = 0; s + 1 < k.seg_start.size(); ++s) {
                    pm_long mn = 0, mx = 0;
                    for (int p = k.seg_start[s]; p < k.seg_start[s + 1]; ++p) {
                        mn += pmn(p);
                        mx += pmx(p);
                    }
                    const pm_long sh = (pm_long)k.offset * (k.seg_start[s + 1] - k.seg_start[s]);
                    mn -= sh, mx -= sh;
                    mlo = std::max(mlo, mn);
                    mhi = std::min(mhi, mx);
                }
                return mlo <= mhi;
            }
            case NT_SET: {
                int mxlo = 0, mnhi = 99;
                for (int i = 0; i < nv; ++i) {
                    mxlo = std::max(mxlo, dlo(d[i]));
                    mnhi = std::min(mnhi, dhi(d[i]));
                }
                return mxlo - mnhi <= nv - 1;
            }
            case NT_SANDWICH: {
                const uint32_t b1 = 1u, bD = bitd(D);
                for (int p1 = 0; p1 < np; ++p1) {
                    if (!(d[k.pvar[p1]] & b1)) continue;
                    for (int pD = 0; pD < np; ++pD) {
                        if (pD == p1 || !(d[k.pvar[pD]] & bD)) continue;
                        int a = std::min(p1, pD), b = std::max(p1, pD);
                        pm_long mn = 0, mx = 0;
                        for (int p = a + 1; p < b; ++p) {
                            mn += pmn(p);
                            mx += pmx(p);
                        }
                        if (mn <= k.total && k.total <= mx) return true;
                    }
                }
                return false;
            }
            case NT_XSUM: {
                for (uint32_t m = d[k.pvar[0]]; m; m &= m - 1) {
                    int kk = __builtin_ctz(m) + 1;
                    if (kk > np) break;
                    pm_long mn = kk, mx = kk;
                    for (int p = 1; p < kk; ++p) {
                        mn += pmn(p);
                        mx += pmx(p);
                    }
                    if (mn <= k.total && k.total <= mx) return true;
                }
                return false;
            }
            case NT_SKYLINE: {
                int vc = 0, mxv = 0, t = 0;
                for (; t < np; ++t) {
                    uint32_t x = d[k.pvar[t]];
                    if (__builtin_popcount(x) != 1) break;
                    int v = dlo(x);
                    if (v > mxv) {
                        mxv = v;
                        ++vc;
                    }
                }
                if (t == np) return vc == k.total;
                // upper bound: every later position could still be a new maximum
                int upper = vc + std::min(np - t, D - mxv);
                return vc <= k.total && k.total <= upper;
            }
            case NT_LINE:
                return true;  // pair relations (checked on assignment) are the rule
            case NT_BETWEEN: {
                uint32_t e0 = d[k.pvar[0]], e1 = d[k.pvar[np - 1]];
                int lo = std::min(dlo(e0), dlo(e1)), hi = std::max(dhi(e0), dhi(e1));
                if (__builtin_popcount(e0) == 1 && __builtin_popcount(e1) == 1) {
                    lo = std::min(dlo(e0), dlo(e1));
                    hi = std::max(dlo(e0), dlo(e1));
                }
                for (int p = 1; p + 1 < np; ++p) {
                    uint32_t x = d[k.pvar[p]];
                    uint32_t inside = (hi > lo + 1) ? ((((1u << (hi - 1)) - 1) >> lo) << lo) : 0u;
                    if (!(x & inside)) return false;
                }
                return true;
            }
            case NT_COUNT: {
                for (int v = 1; v < (int)k.quota.size(); ++v) {
                    int q = k.quota[v];
                    if (q < 0) continue;
                    uint32_t b = bitd(v);
                    int fixed = 0, poss = 0;
                    for (int i = 0; i < nv; ++i) {
                        fixed += d[i] == b;
                        poss += (d[i] & b) != 0;
                    }
                    if (fixed > q || poss < q) return false;
                }
                return true;
            }
            case NT_CIRCLES: {
                for (int v = 1; v <= D; ++v) {
                    const uint32_t b = bitd(v);
                    int fixed = 0, poss = 0;
                    for (int i = 0; i < nv; ++i) {
                        fixed += d[i] == b;
                        poss += (d[i] & b) != 0;
                    }
                    const bool zero_ok = fixed == 0, v_ok = fixed <= v && v <= poss;
                    if (!zero_ok && !v_ok) return false;
                }
                return true;
            }
            case NT_FIRSTSEEN: {
                const uint32_t S = (uint32_t)k.setkind, X = bitd(k.total);
                for (int p = 0; p < np; ++p) {
                    const uint32_t x = d[k.pvar[p]];
                    if (!(x & S)) continue;   // certainly not a set digit
                    if (x & X) return true;   // can be the target here
                    if (!(x & ~S)) return false;  // certainly a set digit, but not the target
                    // could be outside the set: it has to be, keep reading
                }
                return false;  // no set digit at all
            }
            case NT_DISTINCT: {  // exact once every domain is a single digit
                uint32_t fixed = 0, free_union = 0;
                int nfree = 0;
                bool fresh = false;  // some open cell can reuse none of the fixed digits: one more at least
                for (int i = 0; i < nv; ++i)
                    if (__builtin_popcount(d[i]) == 1) fixed |= d[i];
                for (int i = 0; i < nv; ++i)
                    if (__builtin_popcount(d[i]) != 1) {
                        ++nfree;
                        free_union |= d[i];
                        if (!(d[i] & fixed)) fresh = true;
                    }
                const int m = __builtin_popcount(fixed);
                const int upper = m + std::min(nfree, __builtin_popcount(free_union & ~fixed));
                return m + (fresh ? 1 : 0) <= k.total && k.total <= upper;
            }
            case NT_CONTAINS: {
                uint32_t tgt = 0;
                for (int p = 1; p < np; ++p) tgt |= d[k.pvar[p]];
                return (d[k.pvar[0]] & tgt) != 0;
            }
            case NT_SAMESET: {
                // per digit: fixed copies on one side must be matchable on the other
                const int sa = k.seg_start[1];
                for (int v = 1; v <= D; ++v) {
                    uint32_t b = bitd(v);
                    int fa = 0, pa = 0, fb = 0, pb = 0;
                    for (int p = 0; p < np; ++p) {
                        uint32_t x = d[k.pvar[p]];
                        bool fixed = x == b, poss = x & b;
                        if (p < sa) {
                            fa += fixed;
                            pa += poss;
                        } else {
                            fb += fixed;
                            pb += poss;
                        }
                    }
                    if (fa > pb || fb > pa) return false;
                }
                return true;
            }
        }
        return true;
    }
    bool fc_req(const uint32_t* d) const {
        for (const GacReq& r : req) {
            bool ok = false;
            for (int i = 0; i < nv && !ok; ++i)
                if ((r.varmask >> i & 1) && (d[i] & bitd(r.v))) ok = true;
            if (!ok) return false;
        }
        return true;
    }
    // returns true to stop; d = live domains, done = assigned-var mask
    bool fc(uint32_t* d, uint64_t done, int depth) {
        if (++nodes > budget) {
            aborted = true;
            return true;
        }
        if (depth == nv) {
            for (int i = 0; i < nv; ++i) a[i] = dlo(d[i]);
            leaf();
            return stop_first;
        }
        // fewest live candidates first (arrow: circle digits first)
        int i = -1, best = 1 << 30;
        if (nt_line(k.type) || k.type == NT_FIRSTSEEN) {  // line clues: fill from the clue end (prefix bounds)
            for (int p = 0; p < np && i < 0; ++p)
                if (!(done >> k.pvar[p] & 1)) i = k.pvar[p];
        } else {
            for (int j = 0; j < nv; ++j) {
                if (done >> j & 1) continue;
                int key = __builtin_popcount(d[j]) + (circle_mask >> j & 1 ? 0 : 64);
                if (key < best) {
                    best = key;
                    i = j;
                }
            }
        }
        uint32_t nd[64];
        for (uint32_t m = d[i]; m; m &= m - 1) {
            int v = __builtin_ctz(m) + 1;
            uint32_t b = bitd(v);
            bool ok = true;
            for (int j = 0; j < nv && ok; ++j) {
                uint32_t x = d[j];
                if (j == i)
                    x = b;
                else if (!(done >> j & 1)) {
                    if (k.differ[i * nv + j]) x &= ~b;
                    const uint32_t* r = k.rel[i * nv + j];
                    if (r) x &= ~r[v];
                    if (!x) ok = false;
                }
                nd[j] = x;
            }
            if (!ok || !fc_bounds(nd) || !fc_req(nd)) continue;
            if (fc(nd, done | (1ULL << i), depth + 1)) return true;
        }
        return false;
    }
    uint64_t circle_mask = 0;

    void run_table() {
        const int ar = k.arity;
        const size_t nrows = ar ? k.rows.size() / ar : 0;
        for (size_t r = 0; r < nrows; ++r) {
            // 2026-10-22 fix: rows that do not fit the domains are skipped WITHOUT spending budget -- a large table (6+ cells,
            // tens of thousands of rows) used to abort before reaching the matching row, so a full assignment violating the
            // rule was accepted as 'possibly consistent' (brute force reported wrong solutions; CP-SAT was right)
            const uint8_t* row = &k.rows[r * ar];
            bool fits = true;
            for (int p = 0; p < ar && fits; ++p) {
                int i = k.pvar[p], v = row[p];
                if (v < 1 || v > D || !(dom[i] & bitd(v))) fits = false;
            }
            if (!fits) continue;
            if (++nodes > budget) {
                aborted = true;
                return;
            }
            bool ok = true;
            for (int i = 0; i < nv; ++i) asg[i] = false;
            for (int p = 0; p < ar && ok; ++p) {
                int i = k.pvar[p], v = row[p];
                if (v < 1 || v > D || !(dom[i] & bitd(v))) ok = false;
                else if (asg[i] && a[i] != v) ok = false;
                else if (!asg[i]) {
                    if (!pair_ok(i, v)) ok = false;
                    a[i] = v;
                    asg[i] = true;
                }
            }
            if (!ok || !req_ok()) continue;
            leaf();
            if (stop_first) return;
        }
    }
    void run() {
        if (k.type == NT_TABLE) {
            run_table();
            return;
        }
        if (k.type == NT_ARROW)
            for (int p = 0; p < k.ncircle; ++p) circle_mask |= 1ULL << k.pvar[p];
        uint32_t d[64];
        for (int i = 0; i < nv; ++i) d[i] = dom[i];
        // initial consistency of placed/singleton values with each other
        for (int i = 0; i < nv; ++i)
            if (__builtin_popcount(d[i]) == 1)
                for (int j = 0; j < nv; ++j) {
                    if (j == i) continue;
                    int v = dlo(d[i]);
                    if (k.differ[i * nv + j] && __builtin_popcount(d[j]) > 1) d[j] &= ~bitd(v);
                }
        for (int i = 0; i < nv; ++i)
            if (!d[i]) return;
        if (!fc_bounds(d) || !fc_req(d)) return;
        fc(d, 0, 0);
    }
};
}  // namespace

// All-different path (sum with distinct digits, consecutive sets): enumerate
// the digit SETS allowed by the rule, then count/support perfect matchings
// vars <-> set digits with a subset DP. Polynomial in practice where the
// assignment DFS is factorial (9-cell cages, long renbans).
static bool alldiff_path_ok(const NConstraint& k) {
    if (!(k.type == NT_SUM || k.type == NT_SET) || !k.distinct) return false;
    if ((int)k.pvar.size() != k.nv() || k.nv() > 16) return false;
    for (auto* r : k.rel)
        if (r) return false;
    return true;
}

static void alldiff_gac(const NConstraint& k, const uint32_t* dom0, const std::vector<GacReq>& req, int D,
                        GacOut& out) {
    const int nv = k.nv();
    uint32_t dom[64], need = 0, uni = 0;
    for (int i = 0; i < nv; ++i) dom[i] = dom0[i];
    for (const GacReq& r : req) {  // v must sit in a var of the mask
        need |= bitd(r.v);
        for (int i = 0; i < nv; ++i)
            if (!(r.varmask >> i & 1)) dom[i] &= ~bitd(r.v);
    }
    for (int i = 0; i < nv; ++i) {
        out.sup[i] = 0;
        uni |= dom[i];
    }
    out.count = 0;
    out.complete = true;
    out.set_unique = true;
    out.must = 0;
    out.any = false;
    int nsets = 0;
    std::vector<pm_long> F(1u << nv), G(1u << nv);
    int cd[32];
    auto do_set = [&](uint32_t set) {
        if ((set & need) != need) return;
        int n = 0;
        for (uint32_t m = set; m; m &= m - 1) cd[n++] = __builtin_ctz(m) + 1;
        const int N = 1 << nv, ALL = N - 1;
        // F[S]: vars 0..|S|-1 matched to digits indexed by S (subset of set positions)
        std::fill(F.begin(), F.end(), 0);
        std::fill(G.begin(), G.end(), 0);
        F[0] = G[0] = 1;
        for (int S = 1; S < N; ++S) {
            int pc = __builtin_popcount(S);
            uint32_t mf = dom[pc - 1], mb = dom[nv - pc];
            pm_long f = 0, g = 0;
            for (int t = 0; t < nv; ++t) {
                if (!(S >> t & 1)) continue;
                uint32_t bt = bitd(cd[t]);
                if (mf & bt) f += F[S ^ (1 << t)];
                if (mb & bt) g += G[S ^ (1 << t)];
            }
            F[S] = f;
            G[S] = g;
        }
        if (!F[ALL]) return;
        out.count += F[ALL];
        if (nsets++ == 0)
            out.must = set;
        else {
            out.set_unique = false;
            out.must &= set;
        }
        out.any = true;
        for (int S = 0; S < N; ++S) {
            if (!F[S]) continue;
            int j = __builtin_popcount(S);
            if (j == nv) continue;
            for (int t = 0; t < nv; ++t) {
                if (S >> t & 1) continue;
                uint32_t bt = bitd(cd[t]);
                if ((dom[j] & bt) && G[ALL ^ S ^ (1 << t)]) out.sup[j] |= bt;
            }
        }
    };
    if (k.type == NT_SET) {
        for (int lo = 1; lo + nv - 1 <= D; ++lo) {
            uint32_t set = 0;
            for (int d = lo; d < lo + nv; ++d) set |= bitd(d);
            if ((set & uni) == set) do_set(set);
        }
    } else {
        // digit sets of size nv from uni summing to total
        std::vector<int> digs;
        for (uint32_t m = uni; m; m &= m - 1) digs.push_back(__builtin_ctz(m) + 1);
        const int nd = (int)digs.size();
        std::vector<int> suf(nd + 1, 0);
        std::function<void(int, int, int, uint32_t)> rec = [&](int s, int r, int rem, uint32_t set) {
            if (r == 0) {
                if (rem == 0) do_set(set);
                return;
            }
            for (int i = s; i <= nd - r; ++i) {
                int d = digs[i];
                if (d * r > rem) break;  // digits ascending: min sum of r more >= d*r
                // max achievable with r digits from the top of the list
                int mx = 0;
                for (int j = nd - r; j < nd; ++j) mx += digs[j];
                if (mx < rem) return;
                rec(i + 1, r - 1, rem - d, set | bitd(d));
            }
        };
        if (k.totals.empty()) rec(0, nv, k.total, 0);
        else
            for (int t : k.totals) rec(0, nv, t, 0);
    }
    if (!out.any) out.must = 0;
}

// leftovers / set equivalence: digits(A) == digits(B) as multisets. Propagation
// a human uses ("whatever is here must also fit over there"): a digit stays in a
// side only if the other side can hold as many copies as are fixed here.
static void sameset_gac(const NConstraint& k, const uint32_t* dom, GacOut& out) {
    const int nv = k.nv(), np = (int)k.pvar.size(), sa = k.seg_start[1];
    std::vector<uint32_t> d(dom, dom + nv);
    for (int it = 0; it < 8; ++it) {
        bool ch = false;
        for (int side = 0; side < 2; ++side) {
            uint32_t other = 0;
            for (int p = (side ? 0 : sa); p < (side ? sa : np); ++p) other |= d[k.pvar[p]];
            for (int p = (side ? sa : 0); p < (side ? np : sa); ++p) {
                uint32_t& x = d[k.pvar[p]];
                if ((x & other) != x) {
                    x &= other;
                    ch = true;
                }
            }
        }
        // a digit fixed in m cells of one side needs m cells allowing it on the other
        for (int side = 0; side < 2; ++side)
            for (uint32_t m = 0xffffffffu; m; m = 0) {
                for (int v = 1; v <= 32; ++v) {
                    uint32_t b = 1u << (v - 1);
                    int fixed = 0, poss = 0;
                    for (int p = (side ? sa : 0); p < (side ? np : sa); ++p) fixed += d[k.pvar[p]] == b;
                    if (!fixed) continue;
                    for (int p = (side ? 0 : sa); p < (side ? sa : np); ++p) poss += (d[k.pvar[p]] & b) != 0;
                    if (poss < fixed) {  // inconsistent
                        for (int i = 0; i < nv; ++i) d[i] = 0;
                        ch = false;
                    }
                }
            }
        if (!ch) break;
    }
    bool any = true;
    for (int i = 0; i < nv; ++i) {
        out.sup[i] = d[i];
        any &= d[i] != 0;
    }
    out.count = any ? 2 : 0;  // not enumerated
    out.complete = true;
    out.set_unique = false;
    out.must = 0;
    out.any = any;
}

// large equal-sum constraints: per-segment sums (exact enumeration with in-segment
// distinctness, DP relaxation past a budget) intersected across segments; a value is
// kept if its segment can reach a common sum with it (sound: cross-segment links ignored)
static void eqsum_decomp(const NConstraint& k, const uint32_t* dom, int D, GacOut& out) {
    const int nv = k.nv(), nseg = (int)k.seg_start.size() - 1;
    const int SMAX = 64 * 32 + 1;
    std::vector<std::vector<std::vector<uint32_t>>> supmap(nseg);  // seg -> sum -> per-position masks
    std::vector<std::vector<char>> sums(nseg, std::vector<char>(SMAX, 0));
    for (int sg = 0; sg < nseg; ++sg) {
        const int a = k.seg_start[sg], b = k.seg_start[sg + 1], n = b - a;
        auto& sm = supmap[sg];
        sm.assign(SMAX, std::vector<uint32_t>(n, 0));
        // exact DFS with distinctness inside the segment
        std::vector<int> val(n, 0);
        pm_long nodes = 0;
        bool aborted = false;
        std::function<void(int, int)> rec = [&](int i, int sum) {
            if (aborted) return;
            if (++nodes > 300000) {
                aborted = true;
                return;
            }
            if (i == n) {
                sums[sg][sum] = 1;
                for (int j = 0; j < n; ++j) sm[sum][j] |= 1u << (val[j] - 1);
                return;
            }
            const int vi = k.pvar[a + i];
            for (uint32_t m = dom[vi]; m; m &= m - 1) {
                int v = __builtin_ctz(m) + 1;
                bool ok = true;
                for (int j = 0; j < i && ok; ++j)
                    if (val[j] == v && k.differ[k.pvar[a + j] * nv + vi]) ok = false;
                if (!ok) continue;
                val[i] = v;
                rec(i + 1, sum + v);
            }
        };
        rec(0, 0);
        if (aborted) {  // DP relaxation (no distinctness): reach sets forward / backward
            for (auto& v : sm) std::fill(v.begin(), v.end(), 0u);
            std::fill(sums[sg].begin(), sums[sg].end(), 0);
            std::vector<std::vector<char>> fw(n + 1, std::vector<char>(SMAX, 0)), bw(n + 1, std::vector<char>(SMAX, 0));
            fw[0][0] = 1;
            for (int i = 0; i < n; ++i)
                for (int t = 0; t < SMAX; ++t)
                    if (fw[i][t])
                        for (uint32_t m = dom[k.pvar[a + i]]; m; m &= m - 1) {
                            int v = __builtin_ctz(m) + 1;
                            if (t + v < SMAX) fw[i + 1][t + v] = 1;
                        }
            for (int t = 0; t < SMAX; ++t) sums[sg][t] = fw[n][t];
            // supports per final sum: value v at i reachable with prefix sum t1 and suffix t2
            bw[n][0] = 1;
            for (int i = n - 1; i >= 0; --i)
                for (int t = 0; t < SMAX; ++t)
                    if (bw[i + 1][t])
                        for (uint32_t m = dom[k.pvar[a + i]]; m; m &= m - 1) {
                            int v = __builtin_ctz(m) + 1;
                            if (t + v < SMAX) bw[i][t + v] = 1;
                        }
            for (int i = 0; i < n; ++i)
                for (int t1 = 0; t1 < SMAX; ++t1) {
                    if (!fw[i][t1]) continue;
                    for (uint32_t m = dom[k.pvar[a + i]]; m; m &= m - 1) {
                        int v = __builtin_ctz(m) + 1;
                        for (int t2 = 0; t1 + v + t2 < SMAX; ++t2)
                            if (bw[i + 1][t2]) sm[t1 + v + t2][i] |= 1u << (v - 1);
                    }
                }
        }
    }
    if (k.offset) {  // compare sums of (digit - offset): segment sg's raw sum t is t - offset * len(sg)
        int maxlen = 0;
        for (int sg = 0; sg < nseg; ++sg) maxlen = std::max(maxlen, k.seg_start[sg + 1] - k.seg_start[sg]);
        for (int sg = 0; sg < nseg; ++sg) {
            const int sh = k.offset * (maxlen - (k.seg_start[sg + 1] - k.seg_start[sg]));  // align to the longest
            if (!sh) continue;
            std::vector<char> s2(SMAX, 0);
            std::vector<std::vector<uint32_t>> m2(SMAX, std::vector<uint32_t>(supmap[sg][0].size(), 0));
            for (int t = 0; t < SMAX; ++t) {
                const int u = t + sh;
                if (u < 0 || u >= SMAX) continue;
                s2[u] = sums[sg][t];
                m2[u] = supmap[sg][t];
            }
            sums[sg].swap(s2);
            supmap[sg].swap(m2);
        }
    }
    std::vector<char> common(SMAX, 1);
    for (int sg = 0; sg < nseg; ++sg)
        for (int t = 0; t < SMAX; ++t) common[t] &= sums[sg][t];
    for (int i = 0; i < nv; ++i) out.sup[i] = 0;
    bool any = false;
    for (int t = 0; t < SMAX; ++t) {
        if (!common[t]) continue;
        any = true;
        for (int sg = 0; sg < nseg; ++sg) {
            const int a = k.seg_start[sg], b = k.seg_start[sg + 1];
            for (int j = 0; j < b - a; ++j) out.sup[k.pvar[a + j]] |= supmap[sg][t][j];
        }
    }
    out.any = any;
    out.count = any ? 2 : 0;  // not enumerated
    out.complete = true;
    out.set_unique = false;
    out.must = 0;
    (void)D;
}

// Long linear rules (arrows with a 1-3 digit circle, non-distinct sums) over many cells: exact
// support of the relaxation where every position is independent (no distinctness, a repeated cell
// counted per position), by reachable-sum DP. Sound (keeps a superset); polynomial in the length.
static void linear_dp_gac(const NConstraint& k, const uint32_t* dom, const std::vector<GacReq>& req, GacOut& out) {
    const int nv = k.nv(), np = (int)k.pvar.size();
    for (int i = 0; i < nv; ++i) out.sup[i] = 0;
    out.count = 2;
    out.complete = false;
    out.set_unique = false;
    out.must = 0;
    if (!req.empty()) {  // requirement searches: no information (sound)
        for (int i = 0; i < nv; ++i) out.sup[i] = dom[i];
        out.any = true;
        return;
    }
    const int nc = k.type == NT_ARROW ? k.ncircle : 0;
    int maxsum = 0;  // sums beyond the line's largest possible total never matter
    for (int p = nc; p < np; ++p) {
        const uint32_t d = dom[k.pvar[p]];
        maxsum += d ? 32 - __builtin_clz(d) : 0;
    }
    const int MAXS = maxsum + 1;
    using Bits = std::vector<char>;
    // targets: circle values (arrow) or the total (sum)
    Bits target(MAXS, 0);
    std::vector<std::pair<pm_long, std::vector<int>>> circ;  // circle value, digits
    if (k.type == NT_ARROW) {
        std::vector<int> dg(nc, 0);
        std::function<void(int, pm_long)> rec = [&](int p, pm_long val) {
            if (p == nc) {
                if (val >= 0 && val < MAXS) {
                    target[val] = 1;
                    circ.push_back({val, dg});
                }
                return;
            }
            for (uint32_t m = dom[k.pvar[p]]; m; m &= m - 1) {
                dg[p] = __builtin_ctz(m) + 1;
                rec(p + 1, val * 10 + dg[p]);
            }
        };
        rec(0, 0);
    } else if (!k.totals.empty()) {
        for (int t : k.totals)
            if (t >= 0 && t < MAXS) target[t] = 1;
    } else if (k.total >= 0 && k.total < MAXS) {
        target[k.total] = 1;
    }
    const int L = np - nc;
    std::vector<Bits> F(L + 1, Bits(MAXS, 0)), B(L + 1, Bits(MAXS, 0));
    F[0][0] = 1;
    for (int i = 0; i < L; ++i) {
        const uint32_t d = dom[k.pvar[nc + i]];
        for (int s0 = 0; s0 < MAXS; ++s0)
            if (F[i][s0])
                for (uint32_t m = d; m; m &= m - 1) {
                    int s1 = s0 + __builtin_ctz(m) + 1;
                    if (s1 < MAXS) F[i + 1][s1] = 1;
                }
    }
    B[L][0] = 1;
    for (int i = L - 1; i >= 0; --i) {
        const uint32_t d = dom[k.pvar[nc + i]];
        for (int s0 = 0; s0 < MAXS; ++s0)
            if (B[i + 1][s0])
                for (uint32_t m = d; m; m &= m - 1) {
                    int s1 = s0 + __builtin_ctz(m) + 1;
                    if (s1 < MAXS) B[i][s1] = 1;
                }
    }
    // line totals that meet a target
    Bits ok(MAXS, 0);
    bool any = false;
    for (int s = 0; s < MAXS; ++s)
        if (F[L][s] && target[s]) ok[s] = 1, any = true;
    out.any = any;
    if (!any) {
        out.complete = true;  // the relaxation is infeasible -> so is the rule
        out.count = 0;
        return;
    }
    // circle digits: a circle value whose line total is reachable
    for (auto& cv : circ)
        if (ok[cv.first])
            for (int p = 0; p < nc; ++p) out.sup[k.pvar[p]] |= 1u << (cv.second[p] - 1);
    // line digit v at position i: some prefix + v + suffix lands on an ok total. need[t] = 1 if a
    // suffix total s2 with ok[t + s2] exists (t = prefix + v); computed per position in O(MAXS^2)
    const int WS = (MAXS + 63) / 64;
    std::vector<uint64_t> okb(WS, 0), nb(WS);
    for (int t = 0; t < MAXS; ++t)
        if (ok[t]) okb[t >> 6] |= 1ULL << (t & 63);
    std::vector<char> need(MAXS, 0);
    for (int i = 0; i < L; ++i) {
        const int var = k.pvar[nc + i];
        std::fill(nb.begin(), nb.end(), 0);
        for (int s2 = 0; s2 < MAXS; ++s2) {  // nb |= okb >> s2
            if (!B[i + 1][s2]) continue;
            const int ws = s2 >> 6, bs = s2 & 63;
            for (int w = 0; w + ws < WS; ++w) {
                uint64_t x = okb[w + ws] >> bs;
                if (bs && w + ws + 1 < WS) x |= okb[w + ws + 1] << (64 - bs);
                nb[w] |= x;
            }
        }
        for (int t = 0; t < MAXS; ++t) need[t] = (nb[t >> 6] >> (t & 63)) & 1;
        for (uint32_t m = dom[var]; m; m &= m - 1) {
            const int v = __builtin_ctz(m) + 1;
            bool sup = false;
            for (int s1 = 0; s1 + v < MAXS && !sup; ++s1)
                if (F[i][s1] && need[s1 + v]) sup = true;
            if (sup) out.sup[var] |= 1u << (v - 1);
        }
    }
    // a cell at several positions keeps the union of its per-position supports (a superset)
}

// digit set (same N digits in every house): S must fit every house (can), contains every placed digit (must);
// supports = digits of can (only must when |must| = N or |can| = N); a digit of S with one place in a house
// goes there. Infeasible -> no support (brute force / contradiction).
static void digitset_gac(const NConstraint& k, const uint32_t* dom, int D, GacOut& out) {
    const int nv = k.nv(), H = (int)k.seg_start.size() - 1, n = k.total;
    uint32_t sup[64];
    for (int i = 0; i < nv; ++i) sup[i] = dom[i];
    bool ok = H > 0;
    for (int round = 0; round < 4 && ok; ++round) {
        uint32_t can = (D >= 32) ? 0xffffffffu : ((1u << D) - 1), must = 0;
        for (int h = 0; h < H; ++h) {
            uint32_t hd = 0;
            for (int q = k.seg_start[h]; q < k.seg_start[h + 1]; ++q) hd |= sup[k.pvar[q]];
            can &= hd;
        }
        for (int i = 0; i < nv; ++i)
            if (sup[i] && !(sup[i] & (sup[i] - 1))) must |= sup[i];
        if ((must & ~can) || __builtin_popcount(must) > n || __builtin_popcount(can) < n) {
            ok = false;
            break;
        }
        if (__builtin_popcount(can) == n) must = can;
        if (__builtin_popcount(must) == n) can = must;
        bool ch = false;
        for (int i = 0; i < nv; ++i) {
            const uint32_t x = sup[i] & can;
            if (x != sup[i]) sup[i] = x, ch = true;
            if (!x) ok = false;
        }
        for (int h = 0; h < H && ok; ++h)
            for (uint32_t m = must; m; m &= m - 1) {
                const uint32_t b = m & (~m + 1);
                int at = -1, cnt = 0;
                for (int q = k.seg_start[h]; q < k.seg_start[h + 1]; ++q)
                    if (sup[k.pvar[q]] & b) ++cnt, at = k.pvar[q];
                if (cnt == 0) ok = false;
                else if (cnt == 1 && sup[at] != b) sup[at] = b, ch = true;
            }
        if (!ch) break;
    }
    for (int i = 0; i < nv; ++i) out.sup[i] = ok ? sup[i] : 0;
    out.count = ok ? 1 : 0;
    out.complete = true;
    out.set_unique = false;
    out.must = 0;
    out.any = ok;
}

// sandwich relaxation for brute force: for each placement of the 1 and the D, the cells between reach the
// total (reachable-sum DP, distinctness ignored) and every other cell has a non-1 / non-D digit. Sound
// superset of the exact supports; polynomial in the line length.
static bool sandwich_dp(const NConstraint& k, const uint32_t* dom, int D, uint32_t* sup) {
    const int nv = k.nv(), np = (int)k.pvar.size();
    for (int i = 0; i < nv; ++i) sup[i] = 0;
    const uint32_t b1 = 1u, bD = bitd(D), mid = ~(b1 | bD);
    const int T = k.total;
    if (T < 0 || T > 1000) return true;  // out of range: no information
    bool any = false;
    std::vector<std::vector<char>> fw, bw;
    for (int p1 = 0; p1 < np; ++p1) {
        if (!(dom[k.pvar[p1]] & b1)) continue;
        for (int pD = 0; pD < np; ++pD) {
            if (pD == p1 || !(dom[k.pvar[pD]] & bD)) continue;
            const int a = std::min(p1, pD), b = std::max(p1, pD), n = b - a - 1;
            bool ok = true;
            for (int q = 0; q < np && ok; ++q)
                if (q != p1 && q != pD && !(dom[k.pvar[q]] & mid)) ok = false;
            if (!ok) continue;
            fw.assign(n + 1, std::vector<char>(T + 1, 0));
            bw.assign(n + 1, std::vector<char>(T + 1, 0));
            fw[0][0] = 1;
            for (int i = 0; i < n; ++i)
                for (int t = 0; t <= T; ++t)
                    if (fw[i][t])
                        for (uint32_t m = dom[k.pvar[a + 1 + i]] & mid; m; m &= m - 1) {
                            const int v = __builtin_ctz(m) + 1;
                            if (t + v <= T) fw[i + 1][t + v] = 1;
                        }
            if (!fw[n][T]) continue;
            bw[n][0] = 1;
            for (int i = n - 1; i >= 0; --i)
                for (int t = 0; t <= T; ++t)
                    if (bw[i + 1][t])
                        for (uint32_t m = dom[k.pvar[a + 1 + i]] & mid; m; m &= m - 1) {
                            const int v = __builtin_ctz(m) + 1;
                            if (t + v <= T) bw[i][t + v] = 1;
                        }
            any = true;
            sup[k.pvar[p1]] |= b1;
            sup[k.pvar[pD]] |= bD;
            for (int q = 0; q < np; ++q)
                if (q < a || q > b) sup[k.pvar[q]] |= dom[k.pvar[q]] & mid;
            for (int i = 0; i < n; ++i)
                for (int t1 = 0; t1 <= T; ++t1) {
                    if (!fw[i][t1]) continue;
                    for (uint32_t m = dom[k.pvar[a + 1 + i]] & mid; m; m &= m - 1) {
                        const int v = __builtin_ctz(m) + 1;
                        if (t1 + v <= T && bw[i + 1][T - t1 - v]) sup[k.pvar[a + 1 + i]] |= 1u << (v - 1);
                    }
                }
        }
    }
    return any;
}

// brute-force propagation: as nary_gac, but long sandwiches use a small exact budget and then the DP
// relaxation (the support-driven searches cost far more per node than they save in nodes)
void nary_gac_brute(const NConstraint& k, const uint32_t* dom, pm_long budget, int D, GacOut& out) {
    static const std::vector<GacReq> noreq;
    if (k.type == NT_SANDWICH) {
        Enum e(k, dom, noreq, 2000, D);
        e.run();
        if (!e.aborted) {
            for (int i = 0; i < k.nv(); ++i) out.sup[i] = e.sup[i];
            out.count = e.count;
            out.complete = true;
            out.any = e.count > 0;
            out.set_unique = e.set_unique;
            out.must = e.count ? e.must : 0;
            return;
        }
        uint32_t dsup[64];
        const bool any = sandwich_dp(k, dom, D, dsup);
        out.count = any ? 2 : 0;
        out.complete = !any;  // infeasible relaxation -> infeasible; otherwise supports only
        out.any = any;
        out.set_unique = false;
        out.must = 0;
        if (!any) {
            for (int i = 0; i < k.nv(); ++i) out.sup[i] = 0;
            return;
        }
        // values the relaxation allows: confirm each by a bounded single-solution search (as nary_gac's
        // support stage, with a smaller budget); an exhausted search without a solution drops the value
        const int nv = k.nv();
        int open = 0;  // unconfirmed (var, value) pairs: many of them = a wide-open line, searches cost more
        for (int i = 0; i < nv; ++i) open += __builtin_popcount(dsup[i] & ~e.sup[i]);  // than they prune
        if (open > 16) {
            for (int i = 0; i < nv; ++i) out.sup[i] = dsup[i];
            return;
        }
        for (int i = 0; i < nv; ++i) out.sup[i] = e.sup[i];
        std::vector<uint32_t> d2(dom, dom + nv);
        for (int i = 0; i < nv; ++i)
            for (uint32_t m = dsup[i] & ~out.sup[i]; m; m &= m - 1) {
                const uint32_t b = m & (~m + 1);
                if (out.sup[i] & b) continue;
                d2[i] = b;
                Enum f(k, d2.data(), noreq, 2000, D);
                f.stop_first = true;
                f.run();
                if (f.found)
                    for (int j = 0; j < nv; ++j) out.sup[j] |= f.sup[j] & dsup[j];
                else if (f.aborted)
                    out.sup[i] |= b;
                d2[i] = dom[i];
            }
        bool anys = false;
        for (int i = 0; i < nv; ++i) anys |= out.sup[i] != 0;
        if (!anys) out.complete = true, out.any = false;
        return;
    }
    nary_gac(k, dom, noreq, budget, D, out);
}

void nary_gac(const NConstraint& k, const uint32_t* dom, const std::vector<GacReq>& req, pm_long budget, int D,
              GacOut& out) {
    const int nv = k.nv();
    if (((k.type == NT_ARROW && k.ncircle >= 1 && k.ncircle <= 3) || (k.type == NT_SUM && !k.distinct)) &&
        (int)k.pvar.size() > 12) {
        linear_dp_gac(k, dom, req, out);
        return;
    }
    if (k.type == NT_EQSUM && nv > 12 && req.empty() && (int)k.pvar.size() == nv) {
        eqsum_decomp(k, dom, D, out);
        return;
    }
    if (k.type == NT_SAMESET && req.empty()) {
        sameset_gac(k, dom, out);
        return;
    }
    if (k.type == NT_DIGITSET) {
        digitset_gac(k, dom, D, out);
        return;
    }
    if (alldiff_path_ok(k)) {
        alldiff_gac(k, dom, req, D, out);
        return;
    }
    // 1) full enumeration (exact count / digit sets) under a small budget
    Enum e(k, dom, req, std::min(budget, pm_long(2000)), D);
    e.run();
    for (int i = 0; i < nv; ++i) out.sup[i] = e.sup[i];
    out.count = e.count;
    out.complete = !e.aborted;
    out.set_unique = e.set_unique;
    out.any = e.count > 0;
    if (out.complete) {
        out.must = e.count ? e.must : 0;
        return;
    }
    // 2) support-driven: one single-solution search per still-unsupported
    //    (var, value); each found solution supports all its values. A value
    //    whose search exhausts the budget is kept (sound).
    out.set_unique = false;
    std::vector<uint32_t> d2(dom, dom + nv);
    for (int i = 0; i < nv; ++i) {
        for (uint32_t m = dom[i] & ~out.sup[i]; m; m &= m - 1) {
            uint32_t b = m & (~m + 1);
            if (out.sup[i] & b) continue;
            d2[i] = b;
            Enum f(k, d2.data(), req, budget, D);
            f.stop_first = true;
            f.run();
            if (f.found) {
                for (int j = 0; j < nv; ++j) out.sup[j] |= f.sup[j];
                out.any = true;
            } else if (f.aborted) {
                out.sup[i] |= b;
                out.any = true;  // unknown: treat as possibly consistent
            }
            d2[i] = dom[i];
        }
    }
    // 3) must-contain: v is in every solution iff no solution avoids it
    out.must = 0;
    if (!out.any) return;
    uint32_t uni = 0;
    for (int i = 0; i < nv; ++i) uni |= out.sup[i];
    for (uint32_t m = uni; m; m &= m - 1) {
        uint32_t b = m & (~m + 1);
        bool possible = true;
        for (int i = 0; i < nv; ++i) {
            d2[i] = dom[i] & ~b;
            if (!d2[i]) possible = false;
        }
        bool avoid = true;  // assume avoidable unless proven otherwise
        if (!possible) {
            avoid = false;
        } else {
            Enum f(k, d2.data(), req, budget, D);
            f.stop_first = true;
            f.run();
            avoid = f.found || f.aborted;
        }
        if (!avoid) out.must |= b;
    }
    for (int i = 0; i < nv; ++i) d2[i] = dom[i];
}

}  // namespace cs
