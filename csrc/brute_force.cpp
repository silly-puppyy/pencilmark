// Exhaustive search (brute_solve): solutions of a puzzle under every rule, for uniqueness and the generator.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <set>
#include <tuple>
#include "portable.hpp"
#include "solver.hpp"
#include "solver_util.hpp"

namespace cs {

// ---------------------------------------------------------- brute force --
namespace {
struct Brute {
    const Puzzle& p;
    int limit;
    pm_long node_limit;
    pm_long nodes = 0;
    std::vector<std::vector<int>> sols;
    std::vector<int> cages;
    std::vector<std::vector<uint8_t>> vs;
    std::vector<std::vector<uint32_t>> cs;

    Brute(const Puzzle& pz, int lim, pm_long nl) : p(pz), limit(lim), node_limit(nl) {
        for (int gi = 0; gi < p.G; ++gi)
            if (p.groups[gi].has_total) cages.push_back(gi);
    }
    void place(uint8_t* vals, uint32_t* cand, int c, int v) {
        vals[c] = (uint8_t)v;
        cand[c] = 0;
        uint32_t b = bit(v);
        for (int q : p.peer_list[c]) cand[q] &= ~b;
        const int D1 = p.D + 1;
        for (int j : p.rel_sorted_j[c]) cand[p.rel[c][j]] &= ~p.rel_out[c][(size_t)j * D1 + v];
    }
    bool rel_dead = false;
    // revise every empty cell against its relation partners; true if anything changed
    bool rel_arcs(const uint8_t* vals, uint32_t* cand) {
        bool changed = false;
        rel_dead = false;
        const int D1 = p.D + 1;
        for (int x = 0; x < p.N; ++x) {
            if (vals[x] || p.rel[x].empty()) continue;
            for (size_t j = 0; j < p.rel[x].size(); ++j) {
                int q = p.rel[x][j];
                uint32_t dq = vals[q] ? bit(vals[q]) : cand[q];
                const uint32_t* tin = &p.rel_in[x][j * D1];
                uint32_t allowed = 0;
                for (uint32_t m = dq; m; m &= m - 1) allowed |= ~tin[lowdigit(m)];
                if (cand[x] & ~allowed) {
                    cand[x] &= allowed;
                    changed = true;
                    if (!cand[x]) {
                        rel_dead = true;
                        return true;
                    }
                }
            }
        }
        return changed;
    }
    bool valid(const uint8_t* vals) {
        const int D1 = p.D + 1;
        for (int c = 0; c < p.N; ++c) {
            if (!vals[c] || !(p.domains[c] & bit(vals[c]))) return false;
            for (int q : p.peer_list[c])
                if (vals[q] == vals[c]) return false;
            for (size_t j = 0; j < p.rel[c].size(); ++j)
                if (p.rel_out[c][j * D1 + vals[c]] & bit(vals[p.rel[c][j]])) return false;
        }
        for (int gi = 0; gi < p.G; ++gi)
            if (p.groups[gi].has_total) {
                int s = 0;
                for (int c : p.groups[gi].cells) s += vals[c];
                if (s != p.groups[gi].total) return false;
            }
        uint32_t dom[64];
        static const std::vector<GacReq> noreq;
        for (const NConstraint& k : p.nary) {
            if (k.bounds_only) {
                pm_long t = 0;
                if (k.part_sign.empty()) {
                    for (int x : k.vars) t += vals[x];
                } else {
                    for (size_t q = 0; q < k.parts.size(); ++q)
                        for (int x : k.parts[q]) t += k.part_sign[q] * vals[x];
                }
                if (t != k.total) return false;
                continue;
            }
            for (int i = 0; i < k.nv(); ++i) dom[i] = bit(vals[k.vars[i]]);
            GacOut o;
            nary_gac(k, dom, noreq, 1000, p.D, o);
            if (o.complete && !o.any) return false;
        }
        return true;
    }
    bool cages_ok(const uint8_t* vals) {
        for (int gi : cages) {
            const Group& g = p.groups[gi];
            int s = 0;
            bool full = true;
            for (int c : g.cells) {
                s += vals[c];
                if (!vals[c]) full = false;
            }
            if ((full && s != g.total) || (!full && s >= g.total)) return false;
        }
        return true;
    }
    // bounds consistency of a derived sum whose vars fall into parts of pairwise distinct cells: a part's
    // sum lies between its smallest / largest distinct digits (union of its candidates, placed digits fixed)
    static void part_bounds(const std::vector<int>& cells, const uint8_t* vals, const uint32_t* cand, int skip,
                            pm_long& lo, pm_long& hi) {
        uint32_t uni = 0, placed = 0;
        int free = 0;
        lo = hi = 0;
        for (int c : cells) {
            if (c == skip) continue;
            if (vals[c]) lo += vals[c], hi += vals[c], placed |= bit(vals[c]);
            else uni |= cand[c], ++free;
        }
        uni &= ~placed;
        if (popc(uni) < free) {  // inconsistent: per-cell bounds
            for (int c : cells)
                if (c != skip && !vals[c] && cand[c]) lo += __builtin_ctz(cand[c]) + 1, hi += 32 - __builtin_clz(cand[c]);
            return;
        }
        uint32_t m = uni;
        for (int i = 0; i < free; ++i) lo += lowdigit(m), m &= m - 1;
        m = uni;
        for (int i = 0; i < free; ++i) {
            const int top = 32 - __builtin_clz(m);
            hi += top;
            m &= ~bit(top);
        }
    }
    bool sum_bounds_prop(const NConstraint& k, const uint8_t* vals, uint32_t* cand, bool& again) {
        if (k.part.empty()) {
            pm_long lo = 0, hi = 0;
            for (int x : k.vars)
                if (vals[x]) lo += vals[x], hi += vals[x];
                else if (!cand[x]) return false;
                else lo += __builtin_ctz(cand[x]) + 1, hi += 32 - __builtin_clz(cand[x]);
            if (lo > k.total || hi < k.total) return false;
            for (int x : k.vars) {
                if (vals[x]) continue;
                const pm_long mn = __builtin_ctz(cand[x]) + 1, mx = 32 - __builtin_clz(cand[x]);
                uint32_t keep = 0;
                for (uint32_t m = cand[x]; m; m &= m - 1) {
                    const pm_long v = lowdigit(m);
                    if (lo - mn + v <= k.total && hi - mx + v >= k.total) keep |= bit((int)v);
                }
                if (!keep) return false;
                if (keep != cand[x]) cand[x] = keep, again = true;
            }
            return true;
        }
        const auto& parts = k.parts;
        const int np = (int)parts.size();
        pm_long plo_s[64], phi_s[64];
        std::vector<pm_long> plo_v, phi_v;
        pm_long* plo = plo_s;
        pm_long* phi = phi_s;
        if (np > 64) plo_v.resize(np), phi_v.resize(np), plo = plo_v.data(), phi = phi_v.data();
        // signed parts (outie cells subtracted): a part with sign -1 contributes [-hi, -lo]
        auto sg = [&](int q) { return k.part_sign.empty() ? 1 : k.part_sign[q]; };
        pm_long lo = 0, hi = 0;
        for (int q = 0; q < np; ++q) {
            plo[q] = phi[q] = 0;
            if (parts[q].empty()) continue;
            pm_long a, b;
            part_bounds(parts[q], vals, cand, -1, a, b);
            if (sg(q) > 0) plo[q] = a, phi[q] = b;
            else plo[q] = -b, phi[q] = -a;
            lo += plo[q], hi += phi[q];
        }
        if (lo > k.total || hi < k.total) return false;
        for (int q = 0; q < np; ++q)
            for (int x : parts[q]) {
                if (vals[x]) continue;
                pm_long a, b;
                part_bounds(parts[q], vals, cand, x, a, b);  // the part without x
                if (sg(q) < 0) std::swap(a, b), a = -a, b = -b;
                const pm_long olo = lo - plo[q] + a, ohi = hi - phi[q] + b;
                uint32_t keep = 0;
                for (uint32_t m = cand[x]; m; m &= m - 1) {
                    const pm_long v = sg(q) * (pm_long)lowdigit(m);
                    if (olo + v <= k.total && ohi + v >= k.total) keep |= bit(lowdigit(m));
                }
                if (!keep) return false;
                if (keep != cand[x]) cand[x] = keep, again = true;
            }
        return true;
    }
    bool limited = false;
    bool gac_memo = false;  // BandLogic sub-puzzles: skip unchanged rules (see rec)
    pm_long gac_budget = 20000;  // per-rule consistency budget per propagation (BandLogic: smaller)
    pm_long work = 0;            // rule-check work (cells checked), BandLogic accounting
    std::vector<std::vector<uint32_t>> memo_out;
    void rec(int depth) {
        ++nodes;
        if ((int)sols.size() >= limit) return;
        if (nodes > node_limit || ((nodes & 15) == 0 && deadline_passed())) {   // node budget or max_seconds
            limited = true;
            return;
        }
        uint8_t* vals = vs[depth].data();
        uint32_t* cand = cs[depth].data();
        const int N = p.N, D = p.D;
    top:
        bool changed = true;
        while (changed) {
            changed = false;
            for (int c = 0; c < N; ++c) {
                if (!vals[c]) {
                    if (!cand[c]) return;
                    if ((cand[c] & (cand[c] - 1)) == 0) {
                        place(vals, cand, c, 32 - __builtin_clz(cand[c]));
                        changed = true;
                    }
                }
            }
            for (int hi : p.houses) {
                const Group& g = p.groups[hi];
                // Python: for d in 1..D: pos = cells holding/allowing d; place if
                // exactly one empty. Bit-parallel: digits seen once and not
                // placed; after each placement the masks are recomputed and only
                // higher digits are considered, which is exactly the sequential
                // loop's view of the state.
                uint32_t once = 0, twice = 0, placedm = 0;
                auto scan = [&]() {
                    once = twice = placedm = 0;
                    for (int c : g.cells) {
                        uint32_t m = vals[c] ? bit(vals[c]) : cand[c];
                        twice |= once & m;
                        once |= m;
                        if (vals[c]) placedm |= m;
                    }
                };
                scan();
                if (once != p.full) return;
                uint32_t todo = once & ~twice & ~placedm;
                while (todo) {
                    int d = lowdigit(todo);
                    uint32_t b = bit(d);
                    int pc = -1;
                    for (int c : g.cells)
                        if (!vals[c] && (cand[c] & b)) {
                            pc = c;
                            break;
                        }
                    place(vals, cand, pc, d);
                    changed = true;
                    scan();
                    uint32_t higher = d >= 32 ? 0u : ~((1u << d) - 1);
                    todo = once & ~twice & ~placedm & higher;
                }
            }
            (void)D;
        }
        if (rel_arcs(vals, cand)) {  // pair relations: arc consistency (bounds along chains)
            if (rel_dead) return;
            goto top;
        }
        if (!cages.empty()) {
            if (!cages_ok(vals)) return;
            std::vector<int> emp, avail, others;
            for (int gi : cages) {
                const Group& g = p.groups[gi];
                emp.clear();
                int rem = g.total;
                uint32_t used = 0;
                for (int c : g.cells) {
                    if (!vals[c]) emp.push_back(c);
                    rem -= vals[c];
                    if (vals[c]) used |= bit(vals[c]);
                }
                if (emp.empty()) continue;
                int k = (int)emp.size();
                avail.clear();
                for (int d = 1; d <= D; ++d)
                    if (!(used & bit(d))) avail.push_back(d);
                if ((int)avail.size() < k) return;
                for (int c : emp) {
                    uint32_t keep = 0;
                    for (uint32_t dm = cand[c]; dm; dm &= dm - 1) {
                        int d = lowdigit(dm);
                        others.clear();
                        for (int x : avail)
                            if (x != d) others.push_back(x);
                        int m = (int)others.size(), t = k - 1;
                        int lo = 0, hi = 0;
                        for (int i = 0; i < std::min(t, m); ++i) lo += others[i];
                        if (k > 1)
                            for (int i = std::max(0, m - t); i < m; ++i) hi += others[i];
                        if (lo <= rem - d && rem - d <= hi) keep |= bit(d);
                    }
                    if (!keep) return;
                    cand[c] = keep;
                }
            }
        }
        if (!p.nary.empty()) {  // n-ary constraints: consistency propagation
            bool again = false;
            uint32_t dom[64];
            static const std::vector<GacReq> noreq;
            for (size_t ki = 0; ki < p.nary.size(); ++ki) {
                if (deadline_passed()) {     // max_seconds inside one node's propagation: give up (undecided)
                    limited = true;
                    return;
                }
                const NConstraint& k = p.nary[ki];
                if (k.type == NT_LINE || k.type == NT_SAMESET) continue;  // implied by pairs / houses
                if (gac_memo) {  // skip a rule whose domains equal its last propagated output (exact GAC is idempotent)
                    auto& mo = memo_out[ki];
                    bool same = (int)mo.size() == k.nv();
                    for (int i = 0; i < k.nv() && same; ++i)
                        same = mo[i] == (vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]]);
                    if (same) continue;
                }
                if (k.bounds_only) {  // derived sum (cells listed once): bounds over distinct parts
                    work += k.nv();
                    if (!sum_bounds_prop(k, vals, cand, again)) return;
                    continue;
                }
                if (!k.parts.empty()) {  // a sum with house-sharing parts: distinct-digit bounds per part first
                    work += k.nv();
                    if (!sum_bounds_prop(k, vals, cand, again)) return;
                }
                work += 4 * k.nv();
                for (int i = 0; i < k.nv(); ++i) dom[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                GacOut o;
                nary_gac_brute(k, dom, gac_budget, D, o);
                work += 8 * std::min(o.count, gac_budget);  // enumeration effort (assignments found)
                if (o.complete && !o.any) return;
                for (int i = 0; i < k.nv(); ++i) {
                    int x = k.vars[i];
                    if (vals[x]) {
                        if (!(o.sup[i] & bit(vals[x]))) return;
                        continue;
                    }
                    uint32_t nc = cand[x] & o.sup[i];
                    if (!nc) return;
                    if (nc != cand[x]) {
                        cand[x] = nc;
                        again = true;
                    }
                }
                if (gac_memo && o.complete) {
                    auto& mo = memo_out[ki];
                    mo.resize(k.nv());
                    for (int i = 0; i < k.nv(); ++i) mo[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                }
            }
            if (again) goto top;
        }
        int c = -1, best = 1 << 30;
        for (int x = 0; x < N; ++x)
            if (!vals[x] && popc(cand[x]) < best) {
                best = popc(cand[x]);
                c = x;
            }
        if (c < 0) {
            if (!valid(vals)) return;  // a full grid must satisfy every rule
            sols.emplace_back(vals, vals + N);
            return;
        }
        if ((int)vs.size() <= depth + 1) {
            vs.emplace_back(N);
            cs.emplace_back(N);
        }
        uint32_t snapshot = cand[c];
        for (uint32_t dm = snapshot; dm; dm &= dm - 1) {
            int v = lowdigit(dm);
            vals = vs[depth].data();
            cand = cs[depth].data();
            std::copy(vals, vals + N, vs[depth + 1].begin());
            std::copy(cand, cand + N, cs[depth + 1].begin());
            place(vs[depth + 1].data(), cs[depth + 1].data(), c, v);
            rec(depth + 1);
            if ((int)sols.size() >= limit) return;
        }
    }
};
}  // namespace

std::vector<std::vector<int>> brute_solve(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, int limit,
                                          pm_long node_limit, const std::vector<uint8_t>* start_vals,
                                          const std::vector<uint32_t>* start_cand, bool* complete, pm_long* nodes_out,
                                          bool memo) {
    Brute b(p, limit, node_limit);
    b.gac_memo = memo;
    if (memo) b.memo_out.assign(p.nary.size(), {}), b.gac_budget = 1500;
    b.vs.emplace_back(p.N);
    b.cs.emplace_back(p.N);
    if (start_vals) {
        b.vs[0] = *start_vals;
        b.cs[0] = *start_cand;
    } else {
        std::fill(b.vs[0].begin(), b.vs[0].end(), 0);
        b.cs[0] = p.domains;
        for (auto& cv : givens) b.place(b.vs[0].data(), b.cs[0].data(), cv.first, cv.second);
    }
    b.rec(0);
    if (complete) *complete = !(b.limited && (int)b.sols.size() < limit);
    if (nodes_out) *nodes_out = b.nodes;  // (b.work: rule-check effort)
    return b.sols;
}

}  // namespace cs
