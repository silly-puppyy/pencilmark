// Cheap, named human moves (CTC vocabulary), each a relaxation of a stronger engine technique:
//   SumBound (72): min / max ("triangular number") bounds of sum rules: cages, sums, arrows;
//   ClassCount (73): odd / even (and low / middle / high) counting in houses, sum parity;
//   Domino (74): pair-cell reasoning on relation dominoes (kropki, XV, difference, ...): a digit
//     every allowed pair uses leaves the dominoes' common houses; two dominoes of a house whose
//     allowed fillings use exactly four digits lock them.
#include <cstdlib>
#include <climits>
#include <tuple>
#include "portable.hpp"
#include <algorithm>
#include <cmath>
#include <bitset>
#include <chrono>
#include <array>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <unordered_map>

#include "solver.hpp"
#include "expr.hpp"

namespace cs {

namespace {
inline void add_el(MoveBuf& b, Move& m, int c, int v) {
    b.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
    ++m.el_n;
}
inline void meta8(Move& m, int a, int b, int c, int d, int e, int f, int g, int h, double sp) {
    m.has_meta = true;
    m.meta[0] = a; m.meta[1] = b; m.meta[2] = c; m.meta[3] = d;
    m.meta[4] = e; m.meta[5] = f; m.meta[6] = g; m.meta[7] = h;
    m.spread = sp;
}
inline int dmin(uint32_t m) { return m ? __builtin_ctz(m) + 1 : 0; }
inline int dmax(uint32_t m) { return m ? 32 - __builtin_clz(m) : 0; }
}  // namespace

// ------------------------------------------------------------ SumBound --
void Solver::sum_bound(MoveBuf& out) {
    if (disabled[SUM_BOUND]) return;
    const int D = p.D;
    auto run = [&](const NConstraint& k) {
        // linear form sum_i w_i x_i = T over positions; arrows: circle (one digit) = line
        std::vector<int> pos_var, w;
        int T = 0;
        bool distinct = false;
        if (k.type == NT_SUM && !k.totals.empty()) {
            return;  // incomplete clue (unknown total): left to the consistency engine
        } else if (k.type == NT_SUM) {
            for (int v : k.pvar) {
                pos_var.push_back(v);
                w.push_back(1);
            }
            T = k.total;
            distinct = k.distinct;
        } else if (k.type == NT_ARROW && k.ncircle == 1) {
            for (size_t i = 0; i < k.pvar.size(); ++i) {
                pos_var.push_back(k.pvar[i]);
                w.push_back(i == 0 ? -1 : 1);
            }
            T = 0;
        } else {
            return;
        }
        const int n = (int)pos_var.size();
        if (n < 2) return;
        std::vector<uint32_t> dom(n);
        bool any_empty = false;
        for (int i = 0; i < n; ++i) {
            int c = k.vars[pos_var[i]];
            dom[i] = vals[c] ? bit(vals[c]) : cand[c];
            any_empty |= !vals[c];
        }
        if (!any_empty) return;
        // bounds of the rest: per position min / max; distinct sums also by the triangular
        // bound over the digits still available to the empty positions
        auto rest_bounds = [&](int skip, int& lo, int& hi, bool& tri_used) {
            lo = hi = 0;
            tri_used = false;
            int plo = 0, phi = 0, m = 0;
            uint32_t pool = 0, used = 0;
            for (int j = 0; j < n; ++j) {
                if (j == skip) continue;
                if (w[j] > 0) {
                    plo += dmin(dom[j]);
                    phi += dmax(dom[j]);
                } else {
                    plo -= dmax(dom[j]);
                    phi -= dmin(dom[j]);
                }
                const int c = k.vars[pos_var[j]];
                if (vals[c]) used |= bit(vals[c]);
                else {
                    pool |= dom[j];
                    ++m;
                }
            }
            lo = plo;
            hi = phi;
            if (distinct && m > 1) {
                int fixed = 0;
                for (int j = 0; j < n; ++j)
                    if (j != skip && vals[k.vars[pos_var[j]]]) fixed += vals[k.vars[pos_var[j]]];
                pool &= ~used;
                if (popc(pool) < m) return;
                int tlo = fixed, thi = fixed, t = 0;
                for (int d = 1; d <= D && t < m; ++d)
                    if (pool & bit(d)) tlo += d, ++t;
                t = 0;
                for (int d = D; d >= 1 && t < m; --d)
                    if (pool & bit(d)) thi += d, ++t;
                if (tlo > lo) lo = tlo, tri_used = true;
                if (thi < hi) hi = thi, tri_used = true;
            }
            // a sum whose digits may repeat (little killer): cells sharing a house differ -> triangular bounds per
            // such part ("its three cells in box 5 add up to at least 1+2+3")
            if (!distinct && k.type == NT_SUM && !k.parts.empty() && (int)k.part.size() == k.nv()) {
                const int np = (int)k.parts.size();
                std::vector<uint32_t> ppool(np, 0), pused(np, 0);
                std::vector<int> pm(np, 0), pfix(np, 0);
                for (int j = 0; j < n; ++j) {
                    if (j == skip) continue;
                    const int q = k.part[pos_var[j]];
                    const int c = k.vars[pos_var[j]];
                    if (vals[c]) pused[q] |= bit(vals[c]), pfix[q] += vals[c];
                    else ppool[q] |= dom[j], ++pm[q];
                }
                int tlo = 0, thi = 0;
                bool ok = true;
                for (int q = 0; q < np && ok; ++q) {
                    const uint32_t pl = ppool[q] & ~pused[q];
                    if (popc(pl) < pm[q]) { ok = false; break; }
                    int a = pfix[q], b = pfix[q], t = 0;
                    for (int d = 1; d <= D && t < pm[q]; ++d)
                        if (pl & bit(d)) a += d, ++t;
                    t = 0;
                    for (int d = D; d >= 1 && t < pm[q]; --d)
                        if (pl & bit(d)) b += d, ++t;
                    tlo += a, thi += b;
                }
                if (ok) {
                    if (tlo > lo) lo = tlo, tri_used = true;
                    if (thi < hi) hi = thi, tri_used = true;
                }
            }
        };
        for (int i = 0; i < n; ++i) {
            const int c = k.vars[pos_var[i]];
            if (vals[c]) continue;
            int lo, hi;
            bool tri;
            rest_bounds(i, lo, hi, tri);
            // w_i x_i = T - rest  ->  rest in [lo, hi]
            int xlo, xhi;
            if (w[i] > 0) xlo = T - hi, xhi = T - lo;
            else xlo = lo - T, xhi = hi - T;
            uint32_t bad = 0;
            for (uint32_t mm = cand[c]; mm; mm &= mm - 1) {
                int d = lowdigit(mm);
                if (d < xlo || d > xhi) bad |= bit(d);
            }
            if (!bad) continue;
            Move& m = new_move(out, SUM_BOUND, k.shape, n);
            for (uint32_t b2 = bad; b2; b2 &= b2 - 1) add_el(out, m, c, lowdigit(b2));
            std::vector<int> pc;
            for (int v : k.vars)
                if (!vals[v]) pc.push_back(v);
            set_pattern(out, m, pc);
            m.nk = NM_NARY;
            m.na = k.index;
            m.nb = k.group;
            meta8(m, (int)pc.size(), 1, popc(bad), 0, 0, 1, 0, 1, k.shape);
            m.code = 3701 + (tri ? 1 : 0) + (k.type == NT_ARROW ? 2 : 0);
            pm_long xm[XM_N] = {xlo, xhi, tri, n, (pm_long)k.type, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    };
    for (const NConstraint& k : p.cage_nary) run(k);
    for (const NConstraint& k : p.nary) run(k);
    // renban span: a consecutive set of L cells spans L-1 -> every digit lies within L-1 of every other
    // cell's lowest / highest possible digit (the "1 and 9 never together" rule)
    for (const NConstraint& k : p.nary) {
        if (k.type != NT_SET || k.setkind != 0) continue;
        const int L = k.nv();
        if (L < 2 || L >= D) continue;
        int maxlo = 0, minhi = 99;
        for (int c : k.vars) {
            const uint32_t d = vals[c] ? bit(vals[c]) : cand[c];
            maxlo = std::max(maxlo, dmin(d));
            minhi = std::min(minhi, dmax(d));
        }
        const int lo = maxlo - (L - 1), hi = minhi + (L - 1);
        for (int c : k.vars) {
            if (vals[c]) continue;
            uint32_t bad = 0;
            for (uint32_t mm = cand[c]; mm; mm &= mm - 1) {
                const int d = lowdigit(mm);
                if (d < lo || d > hi) bad |= bit(d);
            }
            if (!bad) continue;
            Move& m = new_move(out, SUM_BOUND, k.shape, L);
            for (uint32_t b2 = bad; b2; b2 &= b2 - 1) add_el(out, m, c, lowdigit(b2));
            std::vector<int> pc;
            for (int v : k.vars)
                if (!vals[v]) pc.push_back(v);
            set_pattern(out, m, pc);
            m.nk = NM_NARY;
            m.na = k.index;
            meta8(m, (int)pc.size(), 1, popc(bad), 0, 0, 1, 0, 1, k.shape);
            m.code = 3705;
            pm_long xm[XM_N] = {lo, hi, 0, L, (pm_long)k.type, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

// ------------------------------------------------- ClassCount with units --
// Odd / even (and low / high) counting with pairs as units (CtC QHlmImQDc8Q: "in rows 3 and 4 there are exactly 8
// even digits; every white dot holds one, every black dot at least one, so at most 2 more ... an X is two evens or
// two odds"). A region -- a house, or 2-3 consecutive rows / columns -- holds exactly k * |X| digits of class X.
// Its open cells are covered by disjoint pair units (two cells a pair rule joins, both in the region) and single
// cells; each unit's count of X lies in [lo, hi] (pairs: over the pairs the rule still allows). Interval tightening:
// a unit holds between total - (sum of the others' hi) and total - (sum of the others' lo); digits / pairs outside
// what the unit can then hold go. Sound; one move per region and class.
void Solver::class_count_units(MoveBuf& out) {
    if (disabled[CLASS_COUNT] || in_branch) return;
    const int D = p.D, N = p.N;
    bool any_rel = false;
    for (int c = 0; c < N && !any_rel; ++c) any_rel = !p.rel[c].empty();
    if (!any_rel || D < 4) return;
    uint32_t odd = 0, lo4 = 0;
    for (int d = 1; d <= D; d += 2) odd |= bit(d);
    for (int d = 1; d <= D / 2; ++d) lo4 |= bit(d);
    const uint32_t classes[2] = {p.full & ~odd, lo4};  // even; low (1..D/2)
    // regions: every house; 2 and 3 consecutive rows / columns
    std::vector<std::vector<int>> regions;
    std::vector<int> rows, cols;
    for (int gi : p.houses) {
        const Group& g = p.groups[gi];
        if ((int)g.cells.size() != D) continue;
        regions.push_back(g.cells);
        if (g.kind == "row") rows.push_back(gi);
        else if (g.kind == "col") cols.push_back(gi);
    }
    auto line_idx = [&](int gi, bool row) { return row ? p.coords[p.groups[gi].cells[0]].first : p.coords[p.groups[gi].cells[0]].second; };
    for (int dir = 0; dir < 2; ++dir) {
        std::vector<int>& L = dir == 0 ? rows : cols;
        std::sort(L.begin(), L.end(), [&](int a, int b) { return line_idx(a, dir == 0) < line_idx(b, dir == 0); });
        for (size_t i = 0; i < L.size(); ++i)
            for (size_t k = 2; k <= 3 && i + k <= L.size(); ++k) {
                bool consec = true;
                for (size_t j = 1; j < k; ++j) consec &= line_idx(L[i + j], dir == 0) == line_idx(L[i], dir == 0) + (int)j;
                if (!consec) continue;
                std::vector<int> cs;
                for (size_t j = 0; j < k; ++j) cs.insert(cs.end(), p.groups[L[i + j]].cells.begin(), p.groups[L[i + j]].cells.end());
                regions.push_back(cs);
            }
    }
    struct Unit { int a, b; size_t j; int lo, hi; unsigned cs; };  // b < 0: a single cell; j: rel index of b in rel[a];
    // cs: the counts of X it can hold (bits 0..2: an X domino holds 0 or 2 evens, never 1)
    for (const uint32_t X : classes) {
        const int per = popc(X);
        for (const auto& reg : regions) {
            const int k = (int)reg.size() / D;
            std::vector<char> in(N, 0);
            int total = k * per;
            for (int c : reg) {
                in[c] = 1;
                if (vals[c] && (bit(vals[c]) & X)) --total;
            }
            // pair units: greedily the tightest relation pairs (lo == hi first)
            std::vector<Unit> pairs;
            for (int a : reg) {
                if (vals[a]) continue;
                for (size_t j = 0; j < p.rel[a].size(); ++j) {
                    const int b = p.rel[a][j];
                    if (b <= a || !in[b] || vals[b]) continue;
                    const bool diff = tbit(p.peers(a), b);
                    int lo = 3, hi = -1;
                    unsigned cs = 0;
                    for (uint32_t m = cand[a]; m; m &= m - 1) {
                        const int va = lowdigit(m);
                        const uint32_t ok = cand[b] & ~p.rel_out[a][j * (D + 1) + va] & ~(diff ? bit(va) : 0u);
                        for (uint32_t n = ok; n; n &= n - 1) {
                            const int c = ((bit(va) & X) ? 1 : 0) + ((bit(lowdigit(n)) & X) ? 1 : 0);
                            lo = std::min(lo, c), hi = std::max(hi, c), cs |= 1u << c;
                        }
                    }
                    if (hi < 0) continue;
                    pairs.push_back({a, b, j, lo, hi, cs});
                }
            }
            std::sort(pairs.begin(), pairs.end(), [](const Unit& x, const Unit& y) { return x.hi - x.lo < y.hi - y.lo; });
            std::vector<char> used(N, 0);
            std::vector<Unit> units;
            for (const Unit& u : pairs) {
                if (used[u.a] || used[u.b] || u.cs == 7u) continue;  // 0, 1 or 2: says nothing two cells don't
                used[u.a] = used[u.b] = 1;
                units.push_back(u);
            }
            if (units.empty()) continue;
            for (int c : reg)
                if (!vals[c] && !used[c]) {
                    const int lo = (cand[c] & ~X) ? 0 : 1, hi = (cand[c] & X) ? 1 : 0;
                    units.push_back({c, -1, 0, lo, hi, (lo == 0 ? 1u : 0u) | (hi == 1 ? 2u : 0u)});
                }
            // achievable totals of the units before / after each one (subset sums over count sets)
            const int nu = (int)units.size();
            std::vector<uint64_t> pre(nu + 1, 0), suf(nu + 1, 0);
            pre[0] = 1, suf[nu] = 1;
            auto add = [](uint64_t s, unsigned cs) {
                uint64_t r = 0;
                for (int c = 0; c < 3; ++c)
                    if (cs >> c & 1u) r |= s << c;
                return r;
            };
            for (int i = 0; i < nu; ++i) pre[i + 1] = add(pre[i], units[i].cs);
            for (int i = nu - 1; i >= 0; --i) suf[i] = add(suf[i + 1], units[i].cs);
            if (total < 0 || total > 63 || !(pre[nu] >> total & 1)) continue;  // a contradiction: other steps' business
            std::vector<std::pair<int, int>> el;
            int forced_units = 0;
            for (int i = 0; i < nu; ++i) {
                const Unit& u = units[i];
                unsigned ok = 0;  // counts this unit can hold with the others reaching the rest
                for (int c = 0; c < 3; ++c) {
                    if (!(u.cs >> c & 1u) || total - c < 0) continue;
                    uint64_t others = 0;  // pre[i] (+) suf[i + 1] reaches total - c?
                    for (int x = 0; x <= total - c && x < 64; ++x)
                        if ((pre[i] >> x & 1) && (suf[i + 1] >> (total - c - x) & 1)) { others = 1; break; }
                    if (others) ok |= 1u << c;
                }
                if (ok == u.cs) continue;
                const int nlo = ok & 1u ? 0 : ok & 2u ? 1 : 2, nhi = ok & 4u ? 2 : ok & 2u ? 1 : 0;
                if (u.b < 0) {
                    if (nlo >= 1)
                        for (uint32_t m = cand[u.a] & ~X; m; m &= m - 1) el.push_back({u.a, lowdigit(m)});
                    if (nhi <= 0)
                        for (uint32_t m = cand[u.a] & X; m; m &= m - 1) el.push_back({u.a, lowdigit(m)});
                    ++forced_units;
                    continue;
                }
                // a pair: keep the digits used by an allowed pair whose count is still possible
                const bool diff = tbit(p.peers(u.a), u.b);
                uint32_t ka = 0, kb = 0;
                for (uint32_t m = cand[u.a]; m; m &= m - 1) {
                    const int va = lowdigit(m);
                    const uint32_t allow = cand[u.b] & ~p.rel_out[u.a][u.j * (D + 1) + va] & ~(diff ? bit(va) : 0u);
                    for (uint32_t n = allow; n; n &= n - 1) {
                        const int vb = lowdigit(n);
                        const int c = ((bit(va) & X) ? 1 : 0) + ((bit(vb) & X) ? 1 : 0);
                        if (ok >> c & 1u) ka |= bit(va), kb |= bit(vb);
                    }
                }
                for (uint32_t m = cand[u.a] & ~ka; m; m &= m - 1) el.push_back({u.a, lowdigit(m)});
                for (uint32_t m = cand[u.b] & ~kb; m; m &= m - 1) el.push_back({u.b, lowdigit(m)});
                ++forced_units;
            }
            if (el.empty()) continue;
            std::sort(el.begin(), el.end());
            el.erase(std::unique(el.begin(), el.end()), el.end());
            Move& m = new_move(out, CLASS_COUNT, 1.0, (int)units.size());
            for (auto& e : el) add_el(out, m, e.first, e.second);
            std::vector<int> pc;
            for (const Unit& u : units) {
                pc.push_back(u.a);
                if (u.b >= 0) pc.push_back(u.b);
            }
            set_pattern(out, m, pc);
            m.code = 3730 + (X == lo4 ? 1 : 0) + (k > 1 ? 2 : 0);
            meta8(m, (int)units.size(), k, 2, 1, 0, 1, 0, 1, pspread(pc));
            pm_long xm[XM_N] = {X == lo4 ? 1 : 0, k, (pm_long)units.size(), total, forced_units, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

// ----------------------------------------------------------- ClassCount --
void Solver::class_count(MoveBuf& out) {
    if (disabled[CLASS_COUNT]) return;
    const int D = p.D;
    // classes: odd / even; low / middle / high thirds when D % 3 == 0
    std::vector<std::pair<uint32_t, int>> classes;  // mask, kind (0 parity, 1 thirds)
    uint32_t odd = 0;
    for (int d = 1; d <= D; d += 2) odd |= bit(d);
    classes.push_back({odd, 0});
    classes.push_back({p.full & ~odd, 0});
    if (D % 3 == 0 && D >= 6) {
        const int t = D / 3;
        for (int s = 0; s < 3; ++s) {
            uint32_t m = 0;
            for (int d = s * t + 1; d <= (s + 1) * t; ++d) m |= bit(d);
            classes.push_back({m, 1});
        }
    }
    // digit classes only mean something when some rule looks at digit values (sums, relations,
    // lines): on a pure AllDiff puzzle any relabelling is a symmetry, so class counting is off
    bool value_rules = p.has_cages;
    for (int c = 0; c < p.N && !value_rules; ++c) value_rules = !p.rel[c].empty();
    // arithmetic rules only: tables / digit sets are digit-relabelling equivariant, parity / size classes
    // mean nothing for them (and would make the grade depend on the digit names)
    for (const NConstraint& k : p.nary) value_rules |= k.type != NT_SAMESET && k.type != NT_TABLE && k.type != NT_DIGITSET;
    if (!value_rules) return;
    // (a) a house holds exactly popc(X) digits of class X
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        if ((int)g.cells.size() != D) continue;
        for (auto& cl : classes) {
            const uint32_t X = cl.first;
            int placed = popc(placed_g[hi] & X), forced = 0;
            std::vector<int> fc, rest;
            for (int c : g.cells) {
                if (vals[c]) continue;
                if (!(cand[c] & ~X)) {
                    ++forced;
                    fc.push_back(c);
                } else if (cand[c] & X) {
                    rest.push_back(c);
                }
            }
            if (rest.empty() || placed + forced != popc(X) || forced == 0) continue;
            if (forced <= 1) continue;  // a single cell: naked / hidden singles' business
            Move& m = new_move(out, CLASS_COUNT, g.shape, forced);
            for (int c : rest)
                for (uint32_t b = cand[c] & X; b; b &= b - 1) add_el(out, m, c, lowdigit(b));
            set_pattern(out, m, fc);
            m.nk = NM_GROUP;
            m.na = hi;
            meta8(m, (int)fc.size() + (int)rest.size(), 1, popc(X), 0, 0, 0, 0, 1, g.shape);
            m.code = 3801 + 2 * cl.second;
            pm_long xm[XM_N] = {cl.second, (pm_long)X, placed, forced, (pm_long)rest.size(), 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
    // (b) sum parity: the parities of a sum rule's digits add up to its total's parity
    auto sum_par = [&](const NConstraint& k) {
        if (k.type != NT_SUM || !k.totals.empty()) return;
        int unknown = -1, nunk = 0, par = k.total & 1;
        for (int v : k.pvar) {
            const int c = k.vars[v];
            if (vals[c]) {
                par ^= vals[c] & 1;
                continue;
            }
            if (!(cand[c] & ~odd)) par ^= 1;
            else if (cand[c] & odd) {
                if (unknown != c) ++nunk;
                unknown = c;
            }
        }
        if (nunk != 1) return;
        // unknown must have parity `par`
        const uint32_t bad = cand[unknown] & (par ? ~odd : odd) & p.full;
        if (!bad) return;
        Move& m = new_move(out, CLASS_COUNT, k.shape, (int)k.pvar.size());
        for (uint32_t b = bad; b; b &= b - 1) add_el(out, m, unknown, lowdigit(b));
        std::vector<int> pc;
        for (int v : k.vars)
            if (!vals[v]) pc.push_back(v);
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.na = k.index;
        m.nb = k.group;
        meta8(m, (int)pc.size(), 1, 2, 0, 0, 1, 0, 1, k.shape);
        m.code = 3802;
        pm_long xm[XM_N] = {2, (pm_long)odd, k.total, (pm_long)k.pvar.size(), 1, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    for (const NConstraint& k : p.cage_nary) sum_par(k);
    for (const NConstraint& k : p.nary) sum_par(k);
    // (c) rule of parity: an innie / outie region (rule of 45) has a known total -> its digits'
    // parities add up to the total's parity
    auto region_par = [&](const InnieSet& is) {
        int unknown = -1, nunk = 0, par = ((is.total % 2) + 2) % 2;
        for (int c : is.cells) {
            if (vals[c]) {
                par ^= vals[c] & 1;
                continue;
            }
            if (!(cand[c] & ~odd)) par ^= 1;
            else if (cand[c] & odd) {
                ++nunk;
                unknown = c;
            }
        }
        if (nunk != 1) return;
        const uint32_t bad = cand[unknown] & (par ? ~odd : odd) & p.full;
        if (!bad) return;
        Move& m = new_move(out, CLASS_COUNT, p.groups[is.hi].shape, (int)is.cells.size());
        for (uint32_t b = bad; b; b &= b - 1) add_el(out, m, unknown, lowdigit(b));
        std::vector<int> pc;
        for (int c : is.cells)
            if (!vals[c]) pc.push_back(c);
        set_pattern(out, m, pc);
        m.nk = is.outie ? NM_OUTIE : NM_INNIE;
        m.na = is.hi;
        {
            std::vector<int> r{is.total, is.outie ? 1 : 0, (int)is.houses.size()};
            r.insert(r.end(), is.houses.begin(), is.houses.end());
            r.push_back((int)is.cages.size());
            r.insert(r.end(), is.cages.begin(), is.cages.end());
            r.insert(r.end(), is.cells.begin(), is.cells.end());
            add_expl(out, m, EX_REGION, r);
        }
        meta8(m, (int)is.cells.size(), (int)is.cages.size() + 1, 2, 0, 0, 1, 0, 1, p.groups[is.hi].shape);
        m.code = 3804;
        pm_long xm[XM_N] = {3, (pm_long)odd, is.total, (pm_long)is.cells.size(), 1, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    for (const InnieSet& is : p.innies) region_par(is);
    for (const InnieSet& is : p.big_innies) region_par(is);
    // (d) a custom rule's parity (its cells' sum has one parity under the rule -- an inverted cage's signed total:
    // absint.cpp expr_sum_parity, read once per puzzle), as a sum's: one cell of unknown parity left gets it
    if (expr_par_uid != p.uid || expr_par.size() != p.nary.size()) {
        expr_par.assign(p.nary.size(), -1);
        expr_par_uid = p.uid;
        std::vector<std::vector<int>> aux_all(p.aux_values.begin(), p.aux_values.end());
        for (size_t i = 0; i < p.nary.size(); ++i) {
            const NConstraint& k = p.nary[i];
            if (k.type == NT_EXPR && k.expr && !k.expr->layered && k.nv() >= 2 && k.nv() <= 10)
                expr_par[i] = expr_sum_parity(*k.expr, D, k.nv(), aux_all);
            const NSpec* sp = k.index >= 0 && k.index < (int)p.nary_specs.size() ? &p.nary_specs[k.index] : nullptr;
            if (k.type == NT_TABLE && sp && sp->type == NT_TABLE && k.nv() >= 2 && (int)sp->a.size() == k.nv() &&
                !sp->rows.empty()) {
                int q = -1;  // a table (a small custom rule): every allowed row's sum has one parity
                for (const auto& row : sp->rows) {
                    int t = 0;
                    for (int x : row) t += x;
                    if (q >= 0 && (t & 1) != q) { q = -2; break; }
                    q = t & 1;
                }
                expr_par[i] = q >= 0 ? q : -1;
            }
        }
    }
    struct PF { std::vector<int> cells; int par; bool custom; };
    std::vector<PF> facts;  // (cells, parity of their sum): sums with a known total and custom rules with a parity
    for (const std::vector<NConstraint>* L : {&p.cage_nary, &p.nary})
        for (const NConstraint& k : *L) {
            if (k.type != NT_SUM || !k.totals.empty() || k.offset) continue;
            std::vector<int> cs;
            for (int v : k.pvar) cs.push_back(k.vars[v]);
            std::vector<int> u = cs;
            std::sort(u.begin(), u.end());
            if (std::unique(u.begin(), u.end()) != u.end()) continue;  // a cell counted twice: not a plain sum
            facts.push_back({cs, k.total & 1, false});
        }
    for (size_t i = 0; i < p.nary.size(); ++i) {
        if (expr_par[i] < 0) continue;
        const NConstraint& k = p.nary[i];
        facts.push_back({k.vars, expr_par[i], true});
        // the rule's own cells: one of unknown parity left
        int unknown = -1, nunk = 0, par = expr_par[i];
        for (int c : k.vars) {
            if (vals[c]) { par ^= vals[c] & 1; continue; }
            if (!(cand[c] & ~odd)) par ^= 1;
            else if (cand[c] & odd) ++nunk, unknown = c;
        }
        if (nunk != 1) continue;
        const uint32_t bad = cand[unknown] & (par ? ~odd : odd) & p.full;
        if (!bad) continue;
        Move& m = new_move(out, CLASS_COUNT, k.shape, k.nv());
        for (uint32_t b = bad; b; b &= b - 1) add_el(out, m, unknown, lowdigit(b));
        std::vector<int> pc;
        for (int v : k.vars)
            if (!vals[v]) pc.push_back(v);
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.na = k.index;
        m.nb = k.group;
        meta8(m, (int)pc.size(), 1, 2, 0, 0, 1, 0, 1, k.shape);
        m.code = 3806;
        pm_long xm[XM_N] = {2, (pm_long)odd, expr_par[i], k.nv(), 1, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
    // (e) a house's parity (a full set of digits) less the facts inside it: the house's other cells' sum parity --
    // one of unknown parity left gets it ("each box's values sum to 45, odd: the cage parities fix the leftover cell")
    if (facts.empty()) return;
    std::vector<char> in(p.N, 0), used(p.N, 0);
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        if (!g.complete || (int)g.cells.size() != D) continue;
        for (int c : g.cells) in[c] = 1;
        int par = (D * (D + 1) / 2) & 1, nf = 0, ncustom = 0;
        std::vector<int> fcells;
        for (const PF& f : facts) {
            bool inside = true, clash = false;
            for (int c : f.cells) inside &= in[c] != 0, clash |= used[c] != 0;
            if (!inside || clash) continue;
            for (int c : f.cells) used[c] = 1, fcells.push_back(c);
            par ^= f.par;
            ++nf, ncustom += f.custom;
        }
        int unknown = -1, nunk = 0;
        std::vector<int> rest;
        for (int c : g.cells) {
            if (used[c]) continue;
            rest.push_back(c);
            if (vals[c]) { par ^= vals[c] & 1; continue; }
            if (!(cand[c] & ~odd)) par ^= 1;
            else if (cand[c] & odd) ++nunk, unknown = c;
        }
        for (int c : g.cells) in[c] = 0, used[c] = 0;
        // a custom rule among them (cages alone: the rule of 45's parity, part (c))
        if (nf == 0 || ncustom == 0 || nunk != 1 || rest.size() == g.cells.size()) continue;
        const uint32_t bad = cand[unknown] & (par ? ~odd : odd) & p.full;
        if (!bad) continue;
        Move& m = new_move(out, CLASS_COUNT, g.shape, (int)g.cells.size());
        for (uint32_t b = bad; b; b &= b - 1) add_el(out, m, unknown, lowdigit(b));
        set_pattern(out, m, fcells);
        m.nk = NM_GROUP;
        m.na = hi;
        meta8(m, (int)g.cells.size(), nf + 1, 2, 0, 0, 1, 0, 1, g.shape);
        m.code = 3808;
        pm_long xm[XM_N] = {4, (pm_long)odd, par, (pm_long)rest.size(), nf, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

// --------------------------------------------------------------- Domino --
void Solver::domino(MoveBuf& out) {
    if (disabled[DOMINO]) return;
    const int D1 = p.D + 1;
    struct Dom { int a, b; uint32_t must, digits; std::vector<std::pair<int, int>> pairs; };
    std::vector<Dom> doms;
    for (int a = 0; a < p.N; ++a) {
        if (vals[a]) continue;
        for (size_t j = 0; j < p.rel[a].size(); ++j) {
            const int b = p.rel[a][j];
            if (b < a || vals[b]) continue;
            const bool same = tbit(p.peers(a), b);
            Dom d{a, b, p.full, 0, {}};
            for (uint32_t ma = cand[a]; ma; ma &= ma - 1) {
                const int x = lowdigit(ma);
                for (uint32_t mb = cand[b] & ~p.rel_out[a][j * D1 + x]; mb; mb &= mb - 1) {
                    const int y = lowdigit(mb);
                    if (same && x == y) continue;
                    d.pairs.push_back({x, y});
                    d.must &= bit(x) | bit(y);
                    d.digits |= bit(x) | bit(y);
                }
            }
            if (d.pairs.empty()) continue;
            doms.push_back(d);
        }
    }
    std::vector<int> gs;
    auto common_houses = [&](const std::vector<int>& cells, std::vector<int>& outg) {
        outg.clear();
        for (int gi : p.groups_of[cells[0]]) {
            if (!p.groups[gi].complete) continue;
            bool all = true;
            for (int c : cells) all &= tbit(p.gbits(gi), c);
            if (all) outg.push_back(gi);
        }
    };
    // (i) a digit every allowed filling uses (the two cells see each other: it is in the pair)
    for (const Dom& d : doms) {
        if (!d.must) continue;
        common_houses({d.a, d.b}, gs);
        for (uint32_t mm = d.must; mm; mm &= mm - 1) {
            const int v = lowdigit(mm);
            std::vector<uint32_t> el;  // cells seeing both domino cells
            for (int c : p.peer_list[d.a])
                if (c != d.b && !vals[c] && (cand[c] & bit(v)) && tbit(p.peers(d.b), c))
                    el.push_back((uint32_t)c * 32u + v);
            if (el.empty()) continue;
            Move& m = new_move(out, DOMINO, 1.0, 1);
            for (uint32_t e : el) add_el(out, m, (int)(e / 32), (int)(e % 32));
            set_pattern(out, m, {d.a, d.b});
            add_expl(out, m, EX_BASE, gs);
            add_expl(out, m, EX_DOMINO, {d.a, d.b});
            meta8(m, 2, (int)gs.size() + 1, popc(d.digits), 1, 0, 0, 1, 1, pspread({d.a, d.b}));
            m.code = 3901;
            pm_long xm[XM_N] = {1, v, d.a, d.b, (pm_long)d.pairs.size(), 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
    // (iii) kropki black-dot chains: a cell with two black-dot (ratio 2) partners that see each other
    // (so differ) takes the middle of a 1-2-4 / 2-4-8 / 3-6-12 run: its digit needs both v/2 and 2v
    {
        auto is_black = [&](int a, size_t j) {
            for (int v = 1; v <= p.D; ++v) {
                uint32_t allowed = p.full & ~p.rel_out[a][j * D1 + v], want = 0;
                if (v % 2 == 0) want |= bit(v / 2);
                if (2 * v <= p.D) want |= bit(2 * v);
                if (allowed != want) return false;
            }
            return true;
        };
        for (int b = 0; b < p.N; ++b) {
            if (vals[b]) continue;
            std::vector<int> bl;
            for (size_t j = 0; j < p.rel[b].size(); ++j)
                if (is_black(b, j)) bl.push_back(p.rel[b][j]);
            for (size_t i = 0; i < bl.size(); ++i)
                for (size_t k = i + 1; k < bl.size(); ++k) {
                    const int a = bl[i], c = bl[k];
                    if (!tbit(p.peers(a), c)) continue;
                    uint32_t bad = 0;
                    for (uint32_t m = cand[b]; m; m &= m - 1) {
                        const int v = lowdigit(m);
                        if (v % 2 || 2 * v > p.D) bad |= bit(v);  // needs both neighbours v/2 and 2v
                    }
                    if (!bad) continue;
                    Move& m = new_move(out, DOMINO, 1.0, 3);
                    for (uint32_t x = bad; x; x &= x - 1) add_el(out, m, b, lowdigit(x));
                    std::vector<int> pc{a, b, c};
                    set_pattern(out, m, pc);
                    add_expl(out, m, EX_DOMINO, {a, b, b, c});
                    meta8(m, 3, 2, popc(cand[b]), 2, 0, 0, 1, 1, pspread(pc));
                    m.code = 3903;
                    pm_long xm[XM_N] = {2, (pm_long)bad, a, c, 0, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                }
        }
    }
    // (iv) middle squeeze (whisper 4/6, kropki / XV runs, ...): a cell with two relation partners
    // that see each other needs, for its digit v, two DIFFERENT allowed partner digits
    for (int b = 0; b < p.N; ++b) {
        if (vals[b] || p.rel[b].size() < 2) continue;
        for (size_t i = 0; i < p.rel[b].size(); ++i)
            for (size_t k = i + 1; k < p.rel[b].size(); ++k) {
                const int a = p.rel[b][i], c = p.rel[b][k];
                if (!tbit(p.peers(a), c)) continue;
                const uint32_t da = vals[a] ? bit(vals[a]) : cand[a], dc = vals[c] ? bit(vals[c]) : cand[c];
                uint32_t bad = 0;
                for (uint32_t m = cand[b]; m; m &= m - 1) {
                    const int v = lowdigit(m);
                    const uint32_t A = da & ~p.rel_out[b][i * D1 + v], C = dc & ~p.rel_out[b][k * D1 + v];
                    if (!A || !C) continue;  // plain pair arc (PairArc / relation moves)
                    if (popc(A | C) < 2) bad |= bit(v);
                }
                if (!bad) continue;
                Move& m = new_move(out, DOMINO, 1.0, 3);
                for (uint32_t x = bad; x; x &= x - 1) add_el(out, m, b, lowdigit(x));
                std::vector<int> pc{a, b, c};
                set_pattern(out, m, pc);
                add_expl(out, m, EX_DOMINO, {a, b, b, c});
                meta8(m, 3, 2, popc(cand[b]), 2, 0, 0, 1, 1, pspread(pc));
                m.code = 3904;
                pm_long xm[XM_N] = {2, (pm_long)bad, a, c, 0, 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
            }
    }
    // (ii) two disjoint dominoes of one house: their joint fillings use exactly 4 digits
    for (size_t i = 0; i < doms.size(); ++i)
        for (size_t k = i + 1; k < doms.size(); ++k) {
            const Dom &A = doms[i], &B = doms[k];
            if (A.a == B.a || A.a == B.b || A.b == B.a || A.b == B.b) continue;
            if (popc(A.digits | B.digits) > 6) continue;
            common_houses({A.a, A.b, B.a, B.b}, gs);
            if (gs.empty()) continue;
            uint32_t U = 0;
            for (auto& pa : A.pairs)
                for (auto& pb : B.pairs) {
                    const uint32_t m4 = bit(pa.first) | bit(pa.second) | bit(pb.first) | bit(pb.second);
                    if (popc(m4) == 4) U |= m4;
                }
            if (popc(U) != 4) continue;
            std::vector<uint32_t> el;
            for (int gi : gs)
                for (int c : p.groups[gi].cells)
                    if (c != A.a && c != A.b && c != B.a && c != B.b && !vals[c])
                        for (uint32_t b = cand[c] & U; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            for (int c : {A.a, A.b, B.a, B.b})
                for (uint32_t b = cand[c] & ~U; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            std::sort(el.begin(), el.end());
            el.erase(std::unique(el.begin(), el.end()), el.end());
            if (el.empty()) continue;
            Move& m = new_move(out, DOMINO, 1.0, 2);
            for (uint32_t e : el) add_el(out, m, (int)(e / 32), (int)(e % 32));
            std::vector<int> pc{A.a, A.b, B.a, B.b};
            set_pattern(out, m, pc);
            add_expl(out, m, EX_BASE, gs);
            add_expl(out, m, EX_DOMINO, pc);
            meta8(m, 4, (int)gs.size() + 2, 4, 2, 0, 0, 1, 1, pspread(pc));
            m.code = 3902;
            pm_long xm[XM_N] = {2, (pm_long)U, A.a, B.a, (pm_long)(A.pairs.size() * B.pairs.size()), 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
}

}  // namespace cs

namespace cs {

// Combination-aware positions (tech 95, CTC 'no 16-cage combination holds both 8 and 9, so the other one is
// outside the cage in this row'). For a sum cage K meeting a complete house H and a digit set Q (2-3 digits
// still missing in H): m(Q) = the most digits of Q any valid filling of K puts into K n H. At least |Q| - m(Q)
// digits of Q then lie in H \ K; if exactly that many cells of H \ K can take a digit of Q, those cells hold
// only digits of Q. Bounded enumeration of K's fillings (nothing is emitted when the cap is hit).
void Solver::combo_positions(MoveBuf& out) {
    if (disabled[COMBO_POS] || !p.has_cages) return;
    const int D = p.D;
    std::set<std::vector<uint32_t>> seen;
    for (int kg : p.sum_cages) {
        const auto& K = p.groups[kg].cells;
        if (K.size() < 2 || K.size() > 8) continue;
        bool open = false;
        for (int c : K) open |= !vals[c];
        if (!open) continue;
        for (int hi : p.houses) {
            if (!p.groups[hi].complete || hi == kg) continue;
            std::vector<int> in, outc;
            for (int c : K)
                if (tbit(p.gbits(hi), c)) in.push_back(c);
            if (in.empty()) continue;
            for (int c : p.groups[hi].cells)
                if (!vals[c] && std::find(K.begin(), K.end(), c) == K.end()) outc.push_back(c);
            if (outc.empty()) continue;
            // masks of the digits K puts into K n H, over K's fillings
            std::set<uint32_t> masks;
            std::vector<int> cells(K.begin(), K.end());
            std::vector<char> inH(cells.size());
            for (size_t i = 0; i < cells.size(); ++i) inH[i] = tbit(p.gbits(hi), cells[i]);
            pm_long nodes = 0;
            bool aborted = false;
            const int T = p.groups[kg].total;
            std::function<void(size_t, uint32_t, int, uint32_t)> rec = [&](size_t i, uint32_t used, int sum, uint32_t mH) {
                if (aborted) return;
                if (++nodes > 20000) { aborted = true; return; }
                if (sum > T) return;
                if (i == cells.size()) {
                    if (sum == T) masks.insert(mH);
                    return;
                }
                const int c = cells[i];
                const uint32_t dom = vals[c] ? bit(vals[c]) : cand[c];
                for (uint32_t m = dom & ~used; m; m &= m - 1) {
                    const int v = lowdigit(m);
                    rec(i + 1, used | bit(v), sum + v, inH[i] ? (mH | bit(v)) : mH);
                }
            };
            rec(0, 0, 0, 0);
            if (aborted || masks.empty()) continue;
            const uint32_t missing = p.full & ~placed_g[hi];
            std::vector<int> qd;
            for (uint32_t m = missing; m; m &= m - 1) qd.push_back(lowdigit(m));
            auto try_q = [&](uint32_t Q) {
                int mq = 0;
                for (uint32_t mk : masks) mq = std::max(mq, popc(mk & Q));
                const int need = popc(Q) - mq;
                if (need <= 0) return;
                std::vector<int> X;
                for (int c : outc)
                    if (cand[c] & Q) X.push_back(c);
                if ((int)X.size() != need) return;
                std::vector<uint32_t> el;
                for (int c : X)
                    for (uint32_t b = cand[c] & ~Q; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                if (el.empty()) return;
                std::sort(el.begin(), el.end());
                if (!seen.insert(el).second) return;
                Move& mv = new_move(out, COMBO_POS, 1.0, (int)masks.size());
                for (uint32_t e : el) out.elims.push_back(e), ++mv.el_n;
                std::vector<int> pc(in);
                pc.insert(pc.end(), X.begin(), X.end());
                set_pattern(out, mv, pc);
                add_expl(out, mv, EX_BASE, {hi});
                mv.nk = NM_GROUP;
                mv.na = kg;
                mv.has_meta = true;
                mv.meta[0] = std::min(p.N, (int)(K.size() + X.size()));
                mv.meta[1] = 2;
                mv.meta[2] = popc(Q);
                mv.meta[3] = 0;
                mv.meta[4] = 1;
                mv.meta[5] = 1;
                mv.meta[6] = 0;
                mv.meta[7] = 1;
                mv.spread = pspread(pc);
                mv.code = 3910;
                pm_long xm[XM_N] = {kg, hi, (pm_long)Q, mq, need, (pm_long)masks.size(), 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, mv.xm);
            };
            const int nq = (int)qd.size();
            for (int a = 0; a < nq; ++a)
                for (int b = a + 1; b < nq; ++b) {
                    try_q(bit(qd[a]) | bit(qd[b]));
                    for (int c2 = b + 1; c2 < nq; ++c2) try_q(bit(qd[a]) | bit(qd[b]) | bit(qd[c2]));
                }
        }
    }
    (void)D;
}

}  // namespace cs

namespace cs {

// Clique house (tech 96, CTC 'these four see each other by knight's move, so they are four different digits').
// Cells that must pairwise differ (a shared house, a 'different' relation such as anti-knight, or a pair relation
// that forbids equal digits) form a virtual house. A clique K (4..6 cells, not inside one declared house) whose
// candidates together are exactly |K| digits holds each of them once: cells that must differ from all of K lose
// them, and a digit with one place in K goes there.
void Solver::clique_house(MoveBuf& out) {
    if (disabled[CLIQUE_HOUSE]) return;
    const int N = p.N, D1 = p.D + 1;
    {  // plain row / column / box grids: every clique of peers lies in one house
        bool extra = false;
        for (int c = 0; c < N && !extra; ++c) extra = !p.rel[c].empty();
        for (int g : p.houses) extra |= p.group_cat[g] != GC_LINE && p.group_cat[g] != GC_BOX;
        bool neq = false;
        for (int c = 0; c < N && !neq; ++c) neq = !p.neq[c].empty();
        if (!extra && !neq) return;
    }
    std::vector<int> open;
    for (int c = 0; c < N; ++c)
        if (!vals[c] && popc(cand[c]) <= 5) open.push_back(c);
    if (open.size() < 4) return;
    // must-differ test (houses / neq peers, or a relation forbidding equal digits)
    auto differ = [&](int a, int b) {
        if (tbit(p.peers(a), b)) return true;
        for (size_t j = 0; j < p.rel[a].size(); ++j) {
            if (p.rel[a][j] != b) continue;
            bool all = true;
            for (int v = 1; v < D1 && all; ++v) all = (p.rel_out[a][j * D1 + v] & bit(v)) != 0;
            if (all) return true;
        }
        return false;
    };
    const int n = (int)open.size();
    std::vector<std::vector<char>> adj(n, std::vector<char>(n, 0));
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j) adj[i][j] = adj[j][i] = differ(open[i], open[j]);
    auto in_one_house = [&](const std::vector<int>& K) {
        for (int g : p.houses) {
            bool all = true;
            for (int c : K) all &= tbit(p.gbits(g), c);
            if (all) return true;
        }
        return false;
    };
    std::set<std::vector<uint32_t>> seen;
    std::vector<int> K;
    pm_long nodes = 0;
    std::function<void(int, uint32_t)> rec = [&](int st, uint32_t U) {
        if (++nodes > 200000) return;
        const int k = (int)K.size();
        if (k >= 4 && popc(U) == k) {
            std::vector<int> cells;
            for (int i : K) cells.push_back(open[i]);
            if (!in_one_house(cells)) {
                std::vector<uint32_t> el;
                std::vector<std::pair<int, int>> places;
                for (int c = 0; c < N; ++c) {
                    if (vals[c] || !(cand[c] & U) || std::find(cells.begin(), cells.end(), c) != cells.end()) continue;
                    bool all = true;
                    for (int x : cells) all &= differ(c, x);
                    if (!all) continue;
                    for (uint32_t b = cand[c] & U; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                }
                for (uint32_t b = U; b; b &= b - 1) {
                    const int d = lowdigit(b);
                    int at = -1, cnt = 0;
                    for (int x : cells)
                        if (cand[x] & bit(d)) ++cnt, at = x;
                    if (cnt == 1 && popc(cand[at]) > 1) places.push_back({at, d});
                }
                auto emit = [&](const std::vector<uint32_t>& e, int pc, int pv) {
                    std::vector<uint32_t> key(e);
                    key.push_back((uint32_t)(pc + 1) * 32u + (uint32_t)pv);
                    if (!seen.insert(key).second) return;
                    Move& m = new_move(out, CLIQUE_HOUSE, 1.0, k);
                    if (pc >= 0) m.pc = pc, m.pv = pv;
                    for (uint32_t x : e) out.elims.push_back(x), ++m.el_n;
                    set_pattern(out, m, cells);
                    m.has_meta = true;
                    m.meta[0] = k;
                    m.meta[1] = k;  // groups: the pairwise links taken together
                    m.meta[2] = k;
                    m.meta[3] = 0;
                    m.meta[4] = pc >= 0 ? 1 : 0;
                    m.meta[5] = 0;
                    m.meta[6] = 1;
                    m.meta[7] = 1;
                    m.spread = pspread(cells);
                    m.code = 3920;
                    pm_long xm[XM_N] = {k, (pm_long)U, (pm_long)e.size(), pc >= 0, 0, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                };
                if (!el.empty()) emit(el, -1, 0);
                for (auto& pl : places) emit({}, pl.first, pl.second);
            }
        }
        if (k == 6) return;
        for (int i = st; i < n; ++i) {
            const uint32_t U2 = U | cand[open[i]];
            if (popc(U2) > 6) continue;
            bool ok = true;
            for (int j : K) ok &= adj[i][j] != 0;
            if (!ok) continue;
            K.push_back(i);
            rec(i + 1, U2);
            K.pop_back();
        }
    };
    rec(0, 0);
}

}  // namespace cs

namespace cs {

// Line digit sets across lines (tech 97, CTC 'the two digits private to this renban are 1,2 or 2,3 ... the two in
// common are 3,4 or 4,5'). For a house H and the consecutive-set lines (renbans) meeting it in >= 2 cells: each
// line's options = digit assignments of its H cells over all its consecutive runs that the whole line can fill
// (perfect matching of its cells onto the run). Lines meeting H use different digits inside H, so options are
// chosen jointly (pairwise disjoint on H); a digit no joint choice gives an H cell leaves it.
void Solver::line_sets(MoveBuf& out) {
    if (disabled[LINE_SETS]) return;
    const int D = p.D;
    std::vector<const NConstraint*> lines;
    for (const NConstraint& k : p.nary)
        if (k.type == NT_SET && k.setkind == 0 && k.nv() >= 2 && k.nv() <= 7 && k.nv() < D) lines.push_back(&k);
    if (lines.size() < 2) return;
    std::set<std::vector<uint32_t>> seen;
    for (int hi : p.houses) {
        if (!p.groups[hi].complete) continue;
        struct LO { const NConstraint* k; std::vector<int> hc; std::vector<std::vector<uint8_t>> opts; };
        std::vector<LO> los;
        for (const NConstraint* k : lines) {
            std::vector<int> hc;
            for (int c : k->vars)
                if (tbit(p.gbits(hi), c)) hc.push_back(c);
            if (hc.size() < 2) continue;
            bool open = false;
            for (int c : hc) open |= !vals[c];
            if (!open) continue;
            LO lo{k, hc, {}};
            const int n = k->nv();
            std::set<std::vector<uint8_t>> optset;
            for (int a = 1; a + n - 1 <= D && optset.size() < 2000; ++a) {
                const uint32_t run = ((1u << n) - 1) << (a - 1);
                // all assignments of the line's cells onto the run (distinct), keep the H part
                std::vector<int> asg(n, 0);
                std::function<void(int, uint32_t)> rec = [&](int i, uint32_t used) {
                    if (optset.size() >= 2000) return;
                    if (i == n) {
                        std::vector<uint8_t> o;
                        for (int j = 0; j < n; ++j)
                            if (tbit(p.gbits(hi), k->vars[j])) o.push_back((uint8_t)asg[j]);
                        optset.insert(o);
                        return;
                    }
                    const int c = k->vars[i];
                    const uint32_t dom = (vals[c] ? bit(vals[c]) : cand[c]) & run & ~used;
                    for (uint32_t m = dom; m; m &= m - 1) {
                        asg[i] = lowdigit(m);
                        rec(i + 1, used | bit(asg[i]));
                    }
                };
                rec(0, 0);
            }
            if (optset.size() >= 2000 || optset.empty()) continue;
            lo.opts.assign(optset.begin(), optset.end());
            los.push_back(std::move(lo));
        }
        if (los.size() < 2 || los.size() > 4) continue;
        {  // lines sharing a cell (crossing renbans) would need equal, not different, digits there: skip
            std::vector<int> all;
            for (auto& lo : los) all.insert(all.end(), lo.hc.begin(), lo.hc.end());
            std::sort(all.begin(), all.end());
            if (std::adjacent_find(all.begin(), all.end()) != all.end()) continue;
        }
        // joint choice: H parts pairwise disjoint (and disjoint from H's placed digits outside the lines)
        const int nl = (int)los.size();
        std::vector<std::vector<uint32_t>> sup(nl);
        for (int i = 0; i < nl; ++i) sup[i].assign(los[i].hc.size(), 0);
        std::vector<int> pick(nl, -1);
        pm_long nodes = 0;
        bool aborted = false;
        uint32_t outside_placed = placed_g[hi];
        for (auto& lo : los)
            for (int c : lo.hc)
                if (vals[c]) outside_placed &= ~bit(vals[c]);
        std::vector<int> others;  // open cells of the house on none of the lines
        for (int c : p.groups[hi].cells) {
            if (vals[c]) continue;
            bool on = false;
            for (auto& lo : los) on |= std::find(lo.hc.begin(), lo.hc.end(), c) != lo.hc.end();
            if (!on) others.push_back(c);
        }
        std::function<void(int, uint32_t)> rec2 = [&](int i, uint32_t used) {
            if (aborted) return;
            if (++nodes > 300000) { aborted = true; return; }
            if (i == nl) {
                // the house's other open cells must take every remaining missing digit (pigeonhole: 'one of these
                // overlaps needs to be a 6'): each leftover digit needs a free cell that can hold it, and there
                // must be as many free cells as leftover digits
                const uint32_t left = (p.full & ~placed_g[hi]) & ~used;
                uint32_t can = 0;
                int nfree = 0;
                for (int c : others) can |= cand[c], ++nfree;
                if ((left & ~can) || popc(left) != nfree) return;
                for (int j = 0; j < nl; ++j)
                    for (size_t x = 0; x < los[j].hc.size(); ++x) sup[j][x] |= bit(los[j].opts[pick[j]][x]);
                return;
            }
            for (size_t o = 0; o < los[i].opts.size(); ++o) {
                uint32_t m = 0;
                for (uint8_t d : los[i].opts[o]) m |= bit(d);
                if (m & used) continue;
                pick[i] = (int)o;
                rec2(i + 1, used | m);
            }
        };
        rec2(0, outside_placed);
        if (aborted) continue;
        std::vector<uint32_t> el;
        std::vector<int> pc;
        bool dead = false;
        for (int j = 0; j < nl; ++j)
            for (size_t x = 0; x < los[j].hc.size(); ++x) {
                const int c = los[j].hc[x];
                if (vals[c]) continue;
                dead |= !(cand[c] & sup[j][x]);
                for (uint32_t b = cand[c] & ~sup[j][x]; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            }
        if (dead || el.empty()) continue;
        std::sort(el.begin(), el.end());
        el.erase(std::unique(el.begin(), el.end()), el.end());
        if (!seen.insert(el).second) continue;
        Move& m = new_move(out, LINE_SETS, 1.0, nl);
        for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
        for (auto& lo : los)
            for (int c : lo.k->vars) pc.push_back(c);
        set_pattern(out, m, pc);
        add_expl(out, m, EX_BASE, {hi});
        m.has_meta = true;
        pm_long nopt = 0;
        for (auto& lo : los) nopt += (pm_long)lo.opts.size();
        m.meta[0] = std::min(p.N, (int)pc.size());
        m.meta[1] = nl + 1;
        m.meta[2] = 0;
        for (auto& lo : los)
            for (int c : lo.hc) m.meta[2] = std::max(m.meta[2], popc(vals[c] ? bit(vals[c]) : cand[c]));
        m.meta[3] = 0;
        m.meta[4] = 1;
        m.meta[5] = 0;
        m.meta[6] = 1;
        m.meta[7] = 1;
        m.spread = pspread(pc);
        m.code = 3930;
        pm_long xm[XM_N] = {hi, nl, nopt, (pm_long)el.size(), 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

}  // namespace cs

namespace cs {

// Outside clues together (tech 98, CTC 'if that was a 5 this would be a 4 -- that would cover all the cells in the
// row, but they don't add up'): a line carrying two or more outside clues (sandwich, x-sum, skyscraper) is
// enumerated as one unit -- its open cells as a permutation of the missing digits, every clue checked at the
// leaves. Digits no filling gives a cell go. Bounded (nothing is emitted when the cap is hit).
void Solver::line_clues(MoveBuf& out) {
    if (disabled[LINE_CLUES]) return;
    static const std::vector<GacReq> noreq;
    for (int hi : p.houses) {
        if (!p.groups[hi].complete || p.group_line[hi] >= 2) continue;
        const auto& cells = p.groups[hi].cells;
        std::vector<const NConstraint*> clues;
        for (const NConstraint& k : p.nary) {
            if (k.type != NT_SANDWICH && k.type != NT_XSUM && k.type != NT_SKYLINE) continue;
            bool inside = true;
            for (int c : k.vars) inside &= tbit(p.gbits(hi), c);
            if (inside) clues.push_back(&k);
        }
        if (clues.size() < 2) continue;
        std::vector<int> open;
        for (int c : cells)
            if (!vals[c]) open.push_back(c);
        if (open.empty() || open.size() > 9) continue;
        std::sort(open.begin(), open.end(), [&](int a, int b) { return popc(cand[a]) < popc(cand[b]); });
        std::vector<uint8_t> grid(vals.begin(), vals.end());
        std::vector<uint32_t> sup(p.N, 0);
        pm_long nodes = 0;
        bool aborted = false;
        uint32_t dm[64];
        std::function<void(size_t, uint32_t)> rec = [&](size_t i, uint32_t used) {
            if (aborted) return;
            if (++nodes > 300000) { aborted = true; return; }
            if (i == open.size()) {
                for (const NConstraint* k : clues) {
                    for (int j = 0; j < k->nv(); ++j) dm[j] = bit(grid[k->vars[j]]);
                    GacOut o;
                    nary_gac(*k, dm, noreq, 1000, p.D, o);
                    if (o.complete && !o.any) return;
                }
                for (int c : open) sup[c] |= bit(grid[c]);
                return;
            }
            const int c = open[i];
            for (uint32_t m = cand[c] & ~used & ~placed_g[hi]; m; m &= m - 1) {
                const int v = lowdigit(m);
                grid[c] = (uint8_t)v;
                rec(i + 1, used | bit(v));
            }
            grid[c] = 0;
        };
        rec(0, 0);
        if (aborted) continue;
        std::vector<uint32_t> el;
        bool dead = false;
        for (int c : open) {
            dead |= !(cand[c] & sup[c]);
            for (uint32_t b = cand[c] & ~sup[c]; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
        }
        if (dead || el.empty()) continue;
        Move& m = new_move(out, LINE_CLUES, 1.0, (int)clues.size());
        for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
        set_pattern(out, m, open);
        add_expl(out, m, EX_BASE, {hi});
        m.nk = NM_GROUP;
        m.na = hi;
        m.has_meta = true;
        m.meta[0] = (int)open.size();
        m.meta[1] = 1 + (int)clues.size();
        m.meta[2] = popc(p.full & ~placed_g[hi]);
        m.meta[3] = 0;
        m.meta[4] = 0;
        m.meta[5] = 1;
        m.meta[6] = 0;
        m.meta[7] = 1;
        m.spread = pspread(open);
        m.code = 3940;
        pm_long xm[XM_N] = {hi, (pm_long)clues.size(), std::min(nodes, pm_long(1000000000)), (pm_long)el.size(), 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

}  // namespace cs

namespace cs {

// Weighted multi-house sums (tech 99, CTC 'these are counted three times ... 34 x 3 = 102, so that's a seven';
// 'all of these add up to two lots of 45'). Linear sum facts -- complete houses (= D(D+1)/2), sum cages, sum
// rules (little killers ...), arrows (line - circle = 0), equal sums (segment differences) -- are combined with
// small integer coefficients (2-3 facts that share open cells, coefficients +-1 / +-2) until only 1-3 open cells
// keep a nonzero weight: sum w_i x_i = K. Those cells are enumerated (cells that see each other differ); digits
// no solution gives a cell go. A combination of only houses and cages with unit weights is left to SumAlgebra.
void Solver::weighted_sums(MoveBuf& out) {
    if (disabled[WEIGHTED_SUMS]) return;
    const int N = p.N, D = p.D;
    struct Fact { std::vector<int> w; pm_long k; bool house; };
    std::vector<Fact> facts;
    // cells forced equal by an equality relation (palindromes, clones, '=' dots) are one variable: their weights
    // add up on the class representative (CTC 'expressed as three times this digit')
    std::vector<int> rep(N);
    for (int c = 0; c < N; ++c) rep[c] = c;
    std::function<int(int)> fr = [&](int x) { return rep[x] == x ? x : rep[x] = fr(rep[x]); };
    for (int c = 0; c < N; ++c)
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            bool eq = true;
            for (int v = 1; v <= D && eq; ++v) eq = p.rel_out[c][j * (D + 1) + v] == (p.full & ~bit(v));
            if (eq) {
                const int a = fr(c), b = fr(p.rel[c][j]);
                if (a != b) rep[std::max(a, b)] = std::min(a, b);
            }
        }
    auto add = [&](const std::vector<std::pair<int, int>>& terms, pm_long k, bool house) {
        Fact f{std::vector<int>(N, 0), k, house};
        for (auto& t : terms) {
            const int c = t.first;
            if (vals[c]) f.k -= (pm_long)t.second * vals[c];
            else f.w[fr(c)] += t.second;  // class representative (it is open too: a class shares one digit)
        }
        for (int c = 0; c < N; ++c)
            if (vals[c] && f.w[c]) f.k -= (pm_long)f.w[c] * vals[c], f.w[c] = 0;
        bool open = false;
        for (int c = 0; c < N; ++c) open |= f.w[c] != 0;
        if (open) facts.push_back(std::move(f));
    };
    const pm_long HT = (pm_long)D * (D + 1) / 2;
    for (int g : p.houses)
        if (p.groups[g].complete && (int)p.groups[g].cells.size() == D) {
            std::vector<std::pair<int, int>> t;
            for (int c : p.groups[g].cells) t.push_back({c, 1});
            add(t, HT, true);
        }
    for (int g : p.sum_cages) {
        std::vector<std::pair<int, int>> t;
        for (int c : p.groups[g].cells) t.push_back({c, 1});
        add(t, p.groups[g].total, true);
    }
    for (const NConstraint& k : p.nary) {
        if (k.type == NT_SUM && k.totals.empty() && k.offset == 0 && !k.bounds_only) {
            std::vector<std::pair<int, int>> t;
            for (int v : k.pvar) t.push_back({k.vars[v], 1});  // positions (a cell may repeat)
            add(t, k.total, false);
        } else if (k.type == NT_ARROW && k.ncircle == 1) {
            std::vector<std::pair<int, int>> t;
            for (size_t i = 0; i < k.pvar.size(); ++i) t.push_back({k.vars[k.pvar[i]], i == 0 ? -1 : 1});
            add(t, 0, false);
        } else if (k.type == NT_EQSUM && k.seg_start.size() >= 3) {
            const int ns = (int)k.seg_start.size() - 1;
            for (int s = 1; s < ns; ++s) {  // seg_s - seg_0 = offset * (|seg_s| - |seg_0|)
                std::vector<std::pair<int, int>> t;
                // seg_start indexes positions; positions map to (deduplicated) vars through pvar
                for (int i = k.seg_start[s]; i < k.seg_start[s + 1]; ++i) t.push_back({k.vars[k.pvar[i]], 1});
                for (int i = k.seg_start[0]; i < k.seg_start[1]; ++i) t.push_back({k.vars[k.pvar[i]], -1});
                const pm_long n0 = k.seg_start[1] - k.seg_start[0], ns_ = k.seg_start[s + 1] - k.seg_start[s];
                add(t, (pm_long)k.offset * (ns_ - n0), false);
            }
        }
    }
    // custom rules "linear in the cells == U" (rules/custom.py lin): two equal to the same unknown give a fact without
    // it, rule_s - rule_0 = k_0 - k_s (as equal-sum segments do), so they join the house totals and the cages here
    {
        std::map<int, std::vector<const NConstraint*>> by_u;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L)
                if (k.type == NT_EXPR && k.expr && k.expr->lin_u >= 0 && (int)k.expr->lin_coef.size() == k.nv())
                    by_u[k.expr->lin_u].push_back(&k);
        for (auto& [u, ks] : by_u)
            for (size_t s = 1; s < ks.size(); ++s) {
                std::vector<std::pair<int, int>> t;
                for (int i = 0; i < ks[s]->nv(); ++i) t.push_back({ks[s]->vars[i], ks[s]->expr->lin_coef[i]});
                for (int i = 0; i < ks[0]->nv(); ++i) t.push_back({ks[0]->vars[i], -ks[0]->expr->lin_coef[i]});
                add(t, (pm_long)(ks[0]->expr->lin_const - ks[s]->expr->lin_const), false);
            }
    }
    const int nf = (int)facts.size();
    if (nf < 2 || nf > 120) return;
    std::vector<std::vector<int>> opens(nf);
    for (int i = 0; i < nf; ++i)
        for (int c = 0; c < N; ++c)
            if (facts[i].w[c]) opens[i].push_back(c);
    auto shares = [&](const std::vector<int>& w, int j) {
        for (int c : opens[j])
            if (w[c]) return true;
        return false;
    };
    std::set<std::vector<uint32_t>> seen;
    pm_long work = 0;
    const pm_long cap = 400000;
    std::vector<int> W(N);
    auto evaluate = [&](pm_long K, bool any_rule, int maxw, const std::vector<int>& used) {
        std::vector<int> cs;
        for (int c = 0; c < N; ++c)
            if (W[c]) {
                cs.push_back(c);
                if (cs.size() > 3) return;
            }
        if (cs.empty() || (!any_rule && maxw < 2)) return;
        const int n = (int)cs.size();
        std::vector<uint32_t> sup(n, 0);
        std::vector<int> asg(n, 0);
        std::function<void(int, pm_long)> rec = [&](int i, pm_long s) {
            if (i == n) {
                if (s == K)
                    for (int j = 0; j < n; ++j) sup[j] |= bit(asg[j]);
                return;
            }
            for (uint32_t m = cand[cs[i]]; m; m &= m - 1) {
                const int v = lowdigit(m);
                bool ok = true;
                for (int j = 0; j < i && ok; ++j) ok = !(asg[j] == v && tbit(p.peers(cs[i]), cs[j]));
                if (!ok) continue;
                asg[i] = v;
                rec(i + 1, s + (pm_long)W[cs[i]] * v);
            }
        };
        rec(0, 0);
        std::vector<uint32_t> el;
        for (int j = 0; j < n; ++j) {
            if (!sup[j]) return;  // inconsistent: leave it
            for (uint32_t b = cand[cs[j]] & ~sup[j]; b; b &= b - 1) el.push_back((uint32_t)cs[j] * 32u + lowdigit(b));
        }
        if (el.empty()) return;
        std::sort(el.begin(), el.end());
        if (!seen.insert(el).second) return;
        Move& m = new_move(out, WEIGHTED_SUMS, 1.0, (int)used.size());
        for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
        std::vector<int> pc;
        for (int f : used)
            for (int c : opens[f])
                if (std::find(pc.begin(), pc.end(), c) == pc.end()) pc.push_back(c);
        set_pattern(out, m, pc);
        m.has_meta = true;
        m.meta[0] = std::min(N, (int)pc.size());
        m.meta[1] = (int)used.size();
        m.meta[2] = 0;
        for (int c : cs) m.meta[2] = std::max(m.meta[2], popc(cand[c]));
        m.meta[3] = (int)used.size() - 1;
        m.meta[4] = 0;
        m.meta[5] = 1;
        m.meta[6] = 0;
        m.meta[7] = 1;
        m.spread = pspread(pc);
        m.code = 3950;
        pm_long xm[XM_N] = {(pm_long)used.size(), n, maxw, (pm_long)el.size(), K, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    // any number of facts, one cell left (CTC 'counted four times ... 34 x 3 = 102, that's a seven'): for each
    // open cell c, a combination lambda of ALL facts that cancels every other open cell but not c pins x_c. Found by
    // floating-point elimination, then made exact: lambda rescaled to small integers and the integer combination
    // re-checked (zero off c, divisible total); only a verified identity is used.
    {
        std::vector<int> cells;
        for (int c = 0; c < N; ++c) {
            if (vals[c]) continue;
            bool any = false;
            for (int f = 0; f < nf && !any; ++f) any = facts[f].w[c] != 0;
            if (any) cells.push_back(c);
        }
        const int R = (int)cells.size();
        if (R >= 2 && R <= 81 && nf <= 80) {
            for (int ti = 0; ti < R && work < cap; ++ti) {
                const int tc = cells[ti];
                // rows: equations sum_f lambda_f w_f(c') = 0 for c' != tc; unknowns lambda (nf)
                std::vector<std::vector<long double>> A;
                for (int r = 0; r < R; ++r) {
                    if (r == ti) continue;
                    std::vector<long double> row(nf);
                    bool nz = false;
                    for (int f = 0; f < nf; ++f) row[f] = facts[f].w[cells[r]], nz |= row[f] != 0;
                    if (nz) A.push_back(std::move(row));
                }
                work += (pm_long)A.size() * nf;
                // reduced row echelon form
                std::vector<int> pivcol;
                int rank = 0;
                for (int col = 0; col < nf && rank < (int)A.size(); ++col) {
                    int best = -1;
                    long double bv = 1e-9L;
                    for (int r = rank; r < (int)A.size(); ++r)
                        if (std::fabs(A[r][col]) > bv) bv = std::fabs(A[r][col]), best = r;
                    if (best < 0) continue;
                    std::swap(A[rank], A[best]);
                    const long double pv = A[rank][col];
                    for (int f = 0; f < nf; ++f) A[rank][f] /= pv;
                    for (int r = 0; r < (int)A.size(); ++r) {
                        if (r == rank || std::fabs(A[r][col]) < 1e-15L) continue;
                        const long double m2 = A[r][col];
                        for (int f = 0; f < nf; ++f) A[r][f] -= m2 * A[rank][f];
                    }
                    pivcol.push_back(col);
                    ++rank;
                }
                std::vector<char> isp(nf, 0);
                for (int pcl : pivcol) isp[pcl] = 1;
                for (int free = 0; free < nf; ++free) {  // one null vector per free column
                    if (isp[free]) continue;
                    std::vector<long double> lam(nf, 0);
                    lam[free] = 1;
                    for (int r = 0; r < rank; ++r) lam[pivcol[r]] = -A[r][free];
                    long double s = 0;
                    for (int f = 0; f < nf; ++f) s += lam[f] * facts[f].w[tc];
                    if (std::fabs(s) < 1e-6L) continue;
                    // exact: scale to integers (denominators up to 60)
                    std::vector<pm_long> li(nf);
                    bool okint = false;
                    for (int den = 1; den <= 60 && !okint; ++den) {
                        okint = true;
                        for (int f = 0; f < nf && okint; ++f) {
                            const long double v = lam[f] * den;
                            li[f] = (pm_long)std::llround(v);
                            okint = std::fabs(v - li[f]) < 1e-6L && pm_labs(li[f]) <= 1000;
                        }
                    }
                    if (!okint) continue;
                    pm_long ws = 0, K = 0;
                    bool clean = true;
                    for (int c = 0; c < N && clean; ++c) {
                        pm_long w = 0;
                        for (int f = 0; f < nf; ++f) w += li[f] * facts[f].w[c];
                        if (c == tc) ws = w;
                        else clean = w == 0;
                    }
                    if (!clean || ws == 0) continue;
                    for (int f = 0; f < nf; ++f) K += li[f] * facts[f].k;
                    if (K % ws) continue;  // (would mean an inconsistent state)
                    const pm_long v = K / ws;
                    if (v < 1 || v > D || !(cand[tc] & bit((int)v)) || popc(cand[tc]) == 1) break;
                    std::vector<uint32_t> key{0xFFFFu, (uint32_t)tc, (uint32_t)v};
                    if (!seen.insert(key).second) break;
                    int nused = 0, maxw = (int)pm_labs(ws);
                    std::vector<int> used;
                    for (int f = 0; f < nf; ++f)
                        if (li[f]) ++nused, used.push_back(f);
                    if (nused < 2) break;  // one fact with one open cell: a single / cage completion
                    Move& m = new_move(out, WEIGHTED_SUMS, 1.0, nused);
                    m.pc = tc;
                    m.pv = (int)v;
                    std::vector<int> pc;
                    for (int f : used)
                        for (int c : opens[f])
                            if (std::find(pc.begin(), pc.end(), c) == pc.end()) pc.push_back(c);
                    set_pattern(out, m, pc);
                    m.has_meta = true;
                    m.meta[0] = std::min(N, (int)pc.size());
                    m.meta[1] = nused;
                    m.meta[2] = 1;
                    m.meta[3] = nused - 1;
                    m.meta[4] = 0;
                    m.meta[5] = 1;
                    m.meta[6] = 0;
                    m.meta[7] = 1;
                    m.spread = pspread(pc);
                    m.code = 3951;
                    pm_long xm[XM_N] = {nused, 1, maxw, 0, K, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                    break;
                }
            }
        }
    }
    static const int coefs[4] = {1, -1, 2, -2};
    for (int a = 0; a < nf && work < cap; ++a)
        for (int b = a + 1; b < nf && work < cap; ++b) {
            if (!shares(facts[a].w, b)) continue;
            for (int cb : coefs) {
                ++work;
                bool any_rule = !facts[a].house || !facts[b].house;
                pm_long K = facts[a].k + (pm_long)cb * facts[b].k;
                int maxw = 0, cnt = 0;
                for (int c = 0; c < N; ++c) {
                    W[c] = facts[a].w[c] + cb * facts[b].w[c];
                    if (W[c]) ++cnt, maxw = std::max(maxw, std::abs(W[c]));
                }
                if (cnt <= 3) evaluate(K, any_rule, maxw, {a, b});
                if (cnt > 12) continue;  // triples only from near-cancelling pairs
                const std::vector<int> W2 = W;
                for (int c3 = 0; c3 < nf && work < cap; ++c3) {
                    if (c3 == a || c3 == b || !shares(W2, c3)) continue;
                    for (int cc : coefs) {
                        ++work;
                        int cnt3 = 0, mw = 0;
                        for (int c = 0; c < N; ++c) {
                            W[c] = W2[c] + cc * facts[c3].w[c];
                            if (W[c]) ++cnt3, mw = std::max(mw, std::abs(W[c]));
                        }
                        if (cnt3 <= 3) evaluate(K + (pm_long)cc * facts[c3].k, any_rule || !facts[c3].house, mw, {a, b, c3});
                    }
                }
            }
        }
}




// ---------------------------------------------------------- ClassColour --
// Class colouring over two-class splits: low / high around the middle digit (1-4 | 6-9 on 9x9; halves for even D) and
// odd / even. A relation whose remaining digit pairs always take opposite (or always the same) classes links its two
// cells; linked cells form components with two sides, one in each class. A side is fixed by a cell of known class or
// by counting (a house holds exactly |A| digits of class A); then its cells lose the other class. When every orientation
// of a component fills a house's quota of a class, the house's other cells lose that class.
void Solver::class_colour(MoveBuf& out) {
    if (disabled[CLASS_COLOUR]) return;
    value_class(out);  // the same over (digit, layer value) options
    const int D = p.D, N = p.N;
    bool any_rel = false;
    for (int c = 0; c < N && !any_rel; ++c) any_rel = !p.rel[c].empty();
    // two-cell tables link their cells too (a small custom rule: an inverted 2-cell cage's parity)
    for (const NConstraint& k : p.nary)
        any_rel |= k.type == NT_TABLE && k.nv() == 2 && k.index >= 0 && k.index < (int)p.nary_specs.size();
    if (!any_rel) return;
    struct Split { uint32_t a, b; int kind; };
    uint32_t lo = 0, hi = 0, odd = 0;
    for (int d = 1; d <= D / 2; ++d) lo |= bit(d);
    for (int d = D - D / 2 + 1; d <= D; ++d) hi |= bit(d);
    for (int d = 1; d <= D; d += 2) odd |= bit(d);
    const Split splits[2] = {{lo, hi, 0}, {odd, p.full & ~odd, 1}};
    std::vector<int> par(N), sd(N);
    for (const Split& S : splits) {
        auto mask = [&](int c) { return vals[c] ? bit(vals[c]) : cand[c]; };
        auto cls = [&](int c) { uint32_t m = mask(c); return !(m & ~S.a) ? 0 : !(m & ~S.b) ? 1 : -1; };
        for (int c = 0; c < N; ++c) { par[c] = c; sd[c] = 0; }
        std::function<int(int)> find = [&](int x) {
            if (par[x] == x) return x;
            int r = find(par[x]);
            sd[x] ^= sd[par[x]];
            par[x] = r;
            return r;
        };
        bool bad = false;
        std::vector<int> nlinks(N, 0);
        std::vector<std::array<int, 3>> tree;  // links that joined two colour groups (explanations)
        // w: 1 opposite classes, 0 the same; rec: what the explanation records (w for a rule link, 2 + w + 2 * house
        // for two colorings joined by counting a house)
        auto link = [&](int c, int b, int w, int rec = -1) {
            int rc = find(c), rb = find(b);
            if (rc == rb) {
                if ((sd[c] ^ sd[b]) != w) bad = true;  // contradiction: other techniques' business
                return;
            }
            par[rb] = rc;
            sd[rb] = sd[c] ^ sd[b] ^ w;
            nlinks[rc] += nlinks[rb] + 1;
            tree.push_back({c, b, rec < 0 ? w : rec});
        };
        for (int c = 0; c < N && !bad; ++c) {
            const uint32_t mc = mask(c);
            if (mc & ~(S.a | S.b)) continue;
            for (size_t j = 0; j < p.rel[c].size(); ++j) {
                const int b = p.rel[c][j];
                if (b < c) continue;
                const uint32_t mb = mask(b);
                if (mb & ~(S.a | S.b)) continue;
                bool opp = true, same = true, any = false;
                for (uint32_t r = mc; r; r &= r - 1) {
                    const int v = lowdigit(r);
                    const uint32_t ok = mb & ~p.rel_out[c][j * (D + 1) + v];
                    if (!ok) continue;
                    any = true;
                    const bool va = bit(v) & S.a;
                    if (ok & (va ? S.a : S.b)) opp = false;
                    if (ok & (va ? S.b : S.a)) same = false;
                }
                if (!any || (!opp && !same)) continue;
                link(c, b, opp ? 1 : 0);
            }
        }
        for (const NConstraint& k : p.nary) {  // two-cell tables: their allowed pairs (within the candidates)
            if (bad) break;
            if (k.type != NT_TABLE || k.nv() != 2 || k.index < 0 || k.index >= (int)p.nary_specs.size()) continue;
            const NSpec& sp = p.nary_specs[k.index];
            if (sp.a.size() != 2 || sp.a[0] == sp.a[1]) continue;
            const int c = sp.a[0], b = sp.a[1];
            const uint32_t mc = mask(c), mb = mask(b);
            if ((mc & ~(S.a | S.b)) || (mb & ~(S.a | S.b))) continue;
            bool opp = true, same = true, any = false;
            for (const auto& row : sp.rows) {
                if (row.size() != 2 || !(mc & bit(row[0])) || !(mb & bit(row[1]))) continue;
                any = true;
                const bool xa = bit(row[0]) & S.a, ya = bit(row[1]) & S.a;
                if (xa == ya) opp = false;
                else same = false;
            }
            if (!any || (!opp && !same)) continue;
            link(c, b, opp ? 1 : 0);
        }
        if (bad) continue;
        // colorings that share houses, joined by counting as hosts do ("the sixth one in its row: it's purple"): when
        // only one way of laying one coloring against another keeps every house within its quotas
        {
            std::vector<int> mark(N, -1);
            // -1 when cells (cell, side) fit orientation o; else the full house that overflows
            auto breaks = [&](const std::vector<std::pair<int, int>>& cells, int o) {
                for (auto& e : cells) {
                    mark[e.first] = e.second;
                    const int k = cls(e.first);
                    if (k >= 0 && k != (e.second ^ o)) {
                        for (auto& f : cells) mark[f.first] = -1;
                        return -2;
                    }
                }
                int res = -1;
                for (int hi : p.houses) {
                    const Group& g = p.groups[hi];
                    if ((int)g.cells.size() != D) continue;
                    int n[2] = {0, 0}, inside = 0;
                    uint32_t U[2] = {0, 0};
                    for (int c : g.cells) {
                        const int k = mark[c] >= 0 ? (mark[c] ^ o) : cls(c);
                        inside += mark[c] >= 0;
                        if (k < 0) continue;
                        ++n[k];
                        U[k] |= mask(c) & (k == 0 ? S.a : S.b);
                    }
                    if (inside && (n[0] > popc(U[0]) || n[1] > popc(U[1]))) { res = hi; break; }
                }
                for (auto& f : cells) mark[f.first] = -1;
                return res;
            };
            for (bool changed = true; changed && !bad;) {
                changed = false;
                std::vector<int> roots;
                std::vector<std::vector<int>> members(N);
                for (int c = 0; c < N; ++c) {
                    const int r = find(c);
                    members[r].push_back(c);
                }
                for (int r = 0; r < N; ++r)
                    if (members[r].size() >= 2 && nlinks[r] > 0) roots.push_back(r);
                for (size_t i = 0; i < roots.size() && !changed; ++i)
                    for (size_t j = i + 1; j < roots.size() && !changed; ++j) {
                        const int r1 = roots[i], r2 = roots[j];
                        bool share = false;
                        for (int c : members[r1]) {
                            for (int b : members[r2])
                                if (tbit(p.peers(c), b)) { share = true; break; }
                            if (share) break;
                        }
                        if (!share) continue;
                        int ok[2], why_h[2];
                        for (int w = 0; w < 2; ++w) {
                            std::vector<std::pair<int, int>> cells;
                            for (int c : members[r1]) cells.push_back({c, sd[c]});
                            for (int b : members[r2]) cells.push_back({b, sd[b] ^ w});
                            const int b0 = breaks(cells, 0), b1 = breaks(cells, 1);
                            ok[w] = b0 == -1 || b1 == -1;
                            why_h[w] = b0 >= 0 ? b0 : b1;
                        }
                        if (ok[0] == ok[1]) continue;
                        const int w = ok[1] ? 1 : 0;
                        // only a house overflow joins them (a known cell's class ruling a way out is the anchored
                        // orientation's business, and the explanation names the house)
                        if (why_h[1 - w] < 0) continue;
                        link(r1, r2, w, 2 + w + 2 * why_h[1 - w]);
                        changed = true;
                    }
            }
        }
        if (bad) continue;
        std::vector<std::vector<int>> comp(N);
        for (int c = 0; c < N; ++c) comp[find(c)].push_back(c);
        std::vector<int> links(N, 0);
        for (int c = 0; c < N; ++c)
            if (find(c) == c) links[c] = nlinks[c];
        for (int r = 0; r < N; ++r) {
            const std::vector<int>& cs = comp[r];
            if (cs.size() < 2 || links[r] == 0) continue;
            for (int c : cs) find(c);
            bool open = false;  // some cell still holds both classes
            for (int c : cs) open |= !vals[c] && cls(c) < 0;
            std::vector<char> inC(N, 0);
            for (int c : cs) inC[c] = 1;
            // orientation o: side 0 holds class A (o == 0) or B (o == 1)
            bool feas[2] = {true, true};
            int why = 0, houses_used = 0, anchor = -1;
            std::vector<int> used_h;
            for (int c : cs) {
                const int k = cls(c);
                if (k < 0) continue;
                feas[sd[c] == 0 ? 1 - k : k] = false;  // side of c must be class k
                if (anchor < 0) anchor = c;
            }
            if (!feas[0] && !feas[1]) continue;
            // a house's quota of a class: its cells of that class need distinct digits from the class's digits they
            // can hold (a difference-6 whisper's low cells hold 1-3 only: three per house, not four)
            std::vector<int> hcs;
            for (int hi : p.houses) {
                const Group& g = p.groups[hi];
                if ((int)g.cells.size() != D) continue;
                bool any = false;
                for (int c : g.cells) any |= inC[c] != 0;
                if (any) hcs.push_back(hi);
            }
            // under orientation o, class k of house hi: (cells, the class digits they can hold)
            auto quota = [&](int hi, int o, int k) {
                const uint32_t X = k == 0 ? S.a : S.b;
                int n = 0;
                uint32_t U = 0;
                for (int c : p.groups[hi].cells) {
                    const bool in = inC[c] ? ((sd[c] == 0) == (o == 0)) == (k == 0) : cls(c) == k;
                    if (!in) continue;
                    ++n;
                    U |= mask(c) & X;
                }
                return std::make_pair(n, U);
            };
            const bool known = !(feas[0] && feas[1]);
            for (int o = 0; o < 2; ++o) {
                if (!feas[o]) continue;
                for (int hi : hcs) {
                    bool over = false;
                    for (int k = 0; k < 2 && !over; ++k) {
                        auto q = quota(hi, o, k);
                        over = q.first > popc(q.second);
                    }
                    if (over) {
                        feas[o] = false;
                        ++houses_used;
                        used_h.push_back(hi);
                        break;
                    }
                }
            }
            if (!feas[0] && !feas[1]) continue;
            std::vector<std::pair<int, int>> el;
            if (feas[0] != feas[1]) {
                why = known ? 0 : 1;
                const int o = feas[0] ? 0 : 1;
                for (int c : cs) {
                    if (vals[c]) continue;
                    const bool isA = (sd[c] == 0) == (o == 0);
                    for (uint32_t b = cand[c] & (isA ? S.b : S.a); b; b &= b - 1) el.push_back({c, lowdigit(b)});
                }
            } else if (open) {
                // both orientations possible: a cell outside the coloring whose houses fill a class's quota either way
                // loses that quota's digits ("sees three greens in its row and three purples in its box: a middle digit")
                why = 2;
                std::vector<std::array<uint32_t, 2>> full(hcs.size());  // per house, per orientation: digits used up
                for (size_t j = 0; j < hcs.size(); ++j)
                    for (int o = 0; o < 2; ++o) {
                        full[j][o] = 0;
                        for (int k = 0; k < 2; ++k) {
                            auto q = quota(hcs[j], o, k);
                            if (q.first && q.first == popc(q.second)) full[j][o] |= q.second;
                        }
                    }
                std::vector<int> hs_used;
                for (int x = 0; x < N; ++x) {
                    if (vals[x] || inC[x]) continue;
                    uint32_t E[2] = {0, 0};
                    for (size_t j = 0; j < hcs.size(); ++j) {
                        const Group& g = p.groups[hcs[j]];
                        if (std::find(g.cells.begin(), g.cells.end(), x) == g.cells.end()) continue;
                        // the quota's own cells keep their digits
                        for (int o = 0; o < 2; ++o) {
                            uint32_t f = full[j][o];
                            if (!f) continue;
                            bool mine = false;
                            for (int k = 0; k < 2; ++k) {
                                auto q = quota(hcs[j], o, k);
                                if (q.first && q.first == popc(q.second) && cls(x) == k) mine = true;
                            }
                            if (!mine) E[o] |= f;
                        }
                    }
                    uint32_t rm = cand[x] & E[0] & E[1];
                    if (!rm) continue;
                    for (size_t j = 0; j < hcs.size(); ++j) {
                        const Group& g = p.groups[hcs[j]];
                        if ((full[j][0] || full[j][1]) && std::find(g.cells.begin(), g.cells.end(), x) != g.cells.end())
                            hs_used.push_back(hcs[j]);
                    }
                    for (uint32_t b = rm; b; b &= b - 1) el.push_back({x, lowdigit(b)});
                }
                std::sort(hs_used.begin(), hs_used.end());
                hs_used.erase(std::unique(hs_used.begin(), hs_used.end()), hs_used.end());
                houses_used += (int)hs_used.size();
                used_h.insert(used_h.end(), hs_used.begin(), hs_used.end());
            }
            if (el.empty()) {
                // a house's quota filled by one color: those cells hold exactly the quota's digits, so a cell joined
                // by rules to all of them must suit every one ("it touches all three highs, one is a 7: it's a 1")
                std::vector<uint32_t> allow(N, 0);
                std::vector<int> hs_used;
                for (int o = 0; o < 2; ++o) {
                    if (!feas[o]) continue;
                    std::vector<uint32_t> ao(N, p.full);
                    for (int hi : hcs)
                        for (int k = 0; k < 2; ++k) {
                            const uint32_t X = k == 0 ? S.a : S.b;
                            std::vector<int> Q;
                            uint32_t U = 0;
                            for (int c : p.groups[hi].cells) {
                                const bool in = inC[c] ? ((sd[c] == 0) == (o == 0)) == (k == 0) : cls(c) == k;
                                if (in) { Q.push_back(c); U |= mask(c) & X; }
                            }
                            if (Q.size() < 2 || (int)Q.size() != popc(U)) continue;
                            for (int x = 0; x < N; ++x) {
                                if (vals[x] || std::find(Q.begin(), Q.end(), x) != Q.end()) continue;
                                bool all = true;
                                for (int q : Q) all = all && tbit(p.relb(q), x);
                                if (!all) continue;
                                uint32_t a = p.full;
                                for (uint32_t u = U; u; u &= u - 1) {
                                    const int d = lowdigit(u);
                                    uint32_t ok = 0;
                                    for (int q : Q)
                                        if (mask(q) & bit(d)) ok |= p.full & ~p.rel_ex(q, x)[d];
                                    a &= ok;
                                }
                                if ((cand[x] & ~a) && (ao[x] & ~a)) hs_used.push_back(hi);
                                ao[x] &= a;
                            }
                        }
                    for (int x = 0; x < N; ++x) allow[x] |= ao[x];
                }
                for (int x = 0; x < N; ++x)
                    if (!vals[x])
                        for (uint32_t b = cand[x] & ~allow[x]; b; b &= b - 1) el.push_back({x, lowdigit(b)});
                if (!el.empty()) {
                    why = 3;
                    std::sort(hs_used.begin(), hs_used.end());
                    hs_used.erase(std::unique(hs_used.begin(), hs_used.end()), hs_used.end());
                    houses_used += (int)hs_used.size();
                    used_h.insert(used_h.end(), hs_used.begin(), hs_used.end());
                }
            }
            if (el.empty()) continue;
            std::sort(el.begin(), el.end());
            el.erase(std::unique(el.begin(), el.end()), el.end());
            Move& m = new_move(out, CLASS_COLOUR, 1.0, (int)cs.size());
            for (auto& e : el) add_el(out, m, e.first, e.second);
            std::vector<int> pc;
            for (int c : cs)
                if (!vals[c]) pc.push_back(c);
            set_pattern(out, m, pc);
            uint32_t dg = 0;
            for (auto& e : el) dg |= bit(e.second);
            // (cells, houses used, digits eliminated, links of the colouring, hidden, arith, relation = rule links, notes)
            meta8(m, (int)cs.size(), std::max(1, houses_used), popc(dg), links[r], 0, 0, 1, 1, pspread(pc));
            m.code = 10001 + 10 * S.kind + why;
            pm_long xm[XM_N] = {S.kind, why, (pm_long)cs.size(), links[r], houses_used, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
            {  // the colouring for explanations: orientation (side 0 holds class A when 0), anchor / houses, links, sides
                std::vector<int> rec{S.kind, why, feas[0] != feas[1] ? (feas[0] ? 0 : 1) : -1, why == 0 ? anchor : -1};
                rec.push_back((int)used_h.size());
                rec.insert(rec.end(), used_h.begin(), used_h.end());
                std::vector<int> te;
                for (auto& e : tree)
                    if (find(e[0]) == r) te.insert(te.end(), {e[0], e[1], e[2]});
                rec.push_back((int)te.size() / 3);
                rec.insert(rec.end(), te.begin(), te.end());
                for (int c : cs) rec.insert(rec.end(), {c, sd[c]});
                add_expl(out, m, EX_CLASS, rec);
            }
        }
    }
}


// ------------------------------------------------------------ ClueFacts --
// Facts a solver reads off the clues before solving, from the clues' allowed digit pairs alone (no givens):
//   level 1 (ClueFacts): arc consistency of the pair relations on an empty grid -- a digit stays only while every
//     relation partner can still hold an allowed digit (a different one when the two cells must differ): no 5 on a
//     German whisper, no 5 / 7 / 9 on a black dot, a thermo's ranges, ...
//   level 2 (ClueShape): a digit whose relation partners inside one all-different group would need more distinct
//     digits than their allowed partners offer (pigeonhole): a whisper 4 needs 9 on both sides -- impossible where those
//     two cells share a box; the middle of a black-dot chain can't be 3 when both 6s would see each other.
//   with params cf_nary, the standard rules over more cells too, each clue alone (every way to fill it on the empty
//     grid): a cage's combinations and an arrow's bounds in level 1; a clue's forced digits whose cells all lie in one
//     house leaving the rest of it in level 2 (a 5-cell renban's 5). docs/grades/clue-facts.md lists the facts.
// Both are properties of the puzzle's structure, so each fires once as one step (the masks are worked out once).
void Solver::clue_facts(MoveBuf& out) {
    if (disabled[CLUE_FACTS] && disabled[CLUE_SHAPE]) return;
    const int D = p.D, N = p.N;
    // the facts are the structure's: worked out once per puzzle (and thread), shared by every solver of it (the band
    // route builds many)
    thread_local std::map<std::pair<uint64_t, bool>, std::pair<std::vector<uint32_t>, std::vector<uint32_t>>> memo;
    if (cf_m1.empty()) {
        auto it = memo.find({p.uid, P.cf_nary});
        if (it != memo.end()) cf_m1 = it->second.first, cf_m2 = it->second.second;
    }
    if (cf_m1.empty()) {
        struct Store {  // on every way out of the block below
            std::map<std::pair<uint64_t, bool>, std::pair<std::vector<uint32_t>, std::vector<uint32_t>>>& memo;
            std::pair<uint64_t, bool> key;
            std::vector<uint32_t>&m1, &m2;
            ~Store() {
                if (memo.size() > 256) memo.clear();
                memo[key] = {m1, m2};
            }
        } store{memo, {p.uid, P.cf_nary}, cf_m1, cf_m2};
        cf_m1.assign(N, p.full);
        cf_m2.assign(N, p.full);
        // the standard rules over more cells (params cf_nary), each clue alone; derived rules (innies, set theory,
        // leftovers) are not clue facts, nor are custom / table rules (one-off rules go through lemmas)
        std::vector<const NConstraint*> clues;
        if (P.cf_nary) {
            const bool der = p.is_derived && p.base_nary >= 0;
            auto standard = [](int t) {
                return t == NT_SUM || t == NT_ARROW || t == NT_EQSUM || t == NT_SET || t == NT_SANDWICH ||
                       t == NT_XSUM || t == NT_SKYLINE || t == NT_LINE || t == NT_BETWEEN;
            };
            for (const std::vector<NConstraint>* L : {&p.nary, &p.cage_nary})
                for (const NConstraint& k : *L) {
                    if (!standard(k.type) || k.set_theory || k.innie >= 0 || k.bounds_only || k.nv() > 64) continue;
                    if (long_tree_line(k) || (der && k.index >= p.base_nary)) continue;
                    clues.push_back(&k);
                }
        }
        bool any_rel = false;
        for (int c = 0; c < N && !any_rel; ++c) any_rel = !p.rel[c].empty();
        if (!any_rel && clues.empty()) return;
        std::vector<uint32_t> m(N, p.full);
        for (int c = 0; c < N; ++c)
            if (!p.domains.empty()) m[c] &= p.domains[c];
        auto allowed = [&](int a, size_t j, int v) {
            const int b = p.rel[a][j];
            uint32_t ok = m[b] & ~p.rel_out[a][j * (D + 1) + v];
            if (tbit(p.peers(a), b)) ok &= ~bit(v);
            return ok;
        };
        auto level1 = [&]() {
            bool ch = true;
            while (ch) {
                ch = false;
                for (int a = 0; a < N; ++a) {
                    if (p.rel[a].empty()) continue;
                    uint32_t keep = m[a];
                    for (size_t j = 0; j < p.rel[a].size(); ++j)
                        for (uint32_t r = keep; r; r &= r - 1) {
                            const int v = lowdigit(r);
                            if (!allowed(a, j, v)) keep &= ~bit(v);
                        }
                    if (keep != m[a]) { m[a] = keep; ch = true; }
                }
            }
        };
        // a clue over more cells: every way to fill it on the empty grid (house peers different) -> the digits each
        // cell can take; with `must`, digits in every way whose cells all lie in one house leave the rest of it
        static const std::vector<GacReq> noreq;
        const pm_long CF_BUDGET = 200000;
        auto nary_pass = [&](bool must) {
            bool ch = false;
            uint32_t dom[64];
            for (const NConstraint* k : clues) {
                for (int i = 0; i < k->nv(); ++i) dom[i] = m[k->vars[i]];
                GacOut o;
                nary_gac(*k, dom, noreq, CF_BUDGET, D, o);
                if (!o.any) continue;  // supports and forced digits are sound past the full enumeration's budget too
                for (int i = 0; i < k->nv() && !must; ++i) {
                    const uint32_t nm = m[k->vars[i]] & o.sup[i];
                    if (nm != m[k->vars[i]]) { m[k->vars[i]] = nm; ch = true; }
                }
                if (!must) continue;
                for (uint32_t mm = o.must; mm; mm &= mm - 1) {
                    const int v = lowdigit(mm);
                    std::vector<int> U;
                    for (int c : k->vars)
                        if (m[c] & bit(v)) U.push_back(c);
                    if (U.empty()) continue;
                    for (int gi : p.groups_of[U[0]]) {
                        if (!p.groups[gi].complete) continue;
                        bool all = true;
                        for (int c : U) all = all && tbit(p.gbits(gi), c);
                        if (!all) continue;
                        for (int c : p.groups[gi].cells)
                            if ((m[c] & bit(v)) && std::find(k->vars.begin(), k->vars.end(), c) == k->vars.end()) {
                                m[c] &= ~bit(v);
                                ch = true;
                            }
                    }
                }
            }
            return ch;
        };
        level1();
        while (nary_pass(false)) level1();
        cf_m1 = m;
        // level 2: pigeonhole over the partners of a that lie in one all-different group, and forced digits of a clue
        // over more cells leaving a house
        bool ch = true;
        while (ch) {
            ch = false;
            for (int a = 0; a < N; ++a) {
                const auto& R = p.rel[a];
                if (R.size() < 2) continue;
                for (uint32_t r = m[a]; r; r &= r - 1) {
                    const int v = lowdigit(r);
                    bool bad = false;
                    for (size_t j = 0; j < R.size() && !bad; ++j)
                        for (int gi : p.groups_of[R[j]]) {
                            if (!p.groups[gi].complete && !p.groups[gi].has_total && p.groups[gi].kind != "cage") continue;
                            uint32_t U = 0;
                            int k = 0;
                            for (size_t q = 0; q < R.size(); ++q)
                                if (tbit(p.gbits(gi), R[q])) { U |= allowed(a, q, v); ++k; }
                            if (k >= 2 && popc(U) < k) { bad = true; break; }
                        }
                    if (bad) { m[a] &= ~bit(v); ch = true; }
                }
            }
            if (nary_pass(true)) ch = true;
            if (ch) {
                level1();
                while (nary_pass(false)) level1();
            }
        }
        cf_m2 = m;
    }
    const std::vector<uint32_t>& m1 = cf_m1;
    const std::vector<uint32_t>& m = cf_m2;
    for (int lvl = 1; lvl <= 2; ++lvl) {
        const int tech = lvl == 1 ? CLUE_FACTS : CLUE_SHAPE;
        if (disabled[tech]) continue;
        std::vector<std::pair<int, int>> el;
        std::vector<int> pc;
        for (int c = 0; c < N; ++c) {
            if (vals[c]) continue;
            const uint32_t gone = cand[c] & (lvl == 1 ? ~m1[c] : (m1[c] & ~m[c])) & p.full;
            for (uint32_t b = gone; b; b &= b - 1) el.push_back({c, lowdigit(b)});
            if (gone) pc.push_back(c);
        }
        if (el.empty()) continue;
        Move& mv = new_move(out, tech, 1.0, (int)pc.size());
        for (auto& e : el) add_el(out, mv, e.first, e.second);
        set_pattern(out, mv, pc);
        uint32_t dg = 0;
        for (auto& e : el) dg |= bit(e.second);
        // (cells changed, houses used: none for a clue alone / its one house for the shape, digits eliminated, links,
        //  hidden, arith, relation = read off rules, notes); the count of eliminations is in xm[2]
        meta8(mv, (int)pc.size(), 1, popc(dg), 0, 0, 0, 1, 1, pspread(pc));
        mv.code = 10101 + lvl;
        pm_long xm[XM_N] = {lvl, (pm_long)pc.size(), (pm_long)el.size(), 0, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, mv.xm);
    }
}


// JointHouses' houses (defined with JointHouses below; AuxRule reads the ones confined to a rule's cells)
namespace {
struct JHouse {
    int layer = 0, digit = 0;  // digit 0: any digit
    uint32_t vmask = 0;        // the literal's values (indices into the layer's values)
    Solver::JMask pmask;       // else: the literal is a set of (digit, value) pairs per cell (Solver::jbit bits)
    std::vector<int> cells;
};
}  // namespace
const std::vector<JHouse>& jhouses_of(const Puzzle& p);

// ------------------------------------------------------------ AuxRule --
// unknowns / layers (the file's `unknowns` and `layers`): a custom rule reading them, on its own -- every combination
// of its open digits and open values (at most AUX_CAP, as the exhaustive search's aux_prop): digits and values no
// combination satisfies go. A rule reading regions or the shading too is left to those layers' techniques.
// "E == U" with U the rule's one open unknown: every combination of E's open digits (at most AUX_CAP), its value E;
// U keeps the values some combination reaches, and a digit stays while one of its combinations reaches a value U can
// still take -- a cage whose total is an unknown, read without trying each total
// a digit of the rule's variable i that another of its cells, in a house with it, already holds (sudoku: they differ)
bool Solver::sees_same(const NConstraint& k, const std::vector<int>& dg, int i) const {
    const int c = k.vars[i];
    for (int t = 0; t < k.nv(); ++t) {
        if (t == i || dg[t] != dg[i] || dg[t] <= 0) continue;
        const int b = k.vars[t];
        if (b != c && ((p.peers(c)[b >> 6] >> (b & 63)) & 1)) return true;
    }
    return false;
}

bool Solver::rule_narrow(const NConstraint& k, std::vector<uint32_t>& dm, std::vector<std::vector<int>>& ad) const {
    if (!expr_may_hold(*k.expr, dm.data(), ad)) return false;
    const int nv = k.nv();
    for (bool changed = true; changed;) {
        changed = false;
        for (int i = 0; i < nv; ++i) {
            const uint32_t was = dm[i];
            if (popc(was) < 2) continue;
            uint32_t keep = 0;
            for (uint32_t m = was; m; m &= m - 1) {
                bool taken = false;  // a cell of a shared house already holds it
                for (int t = 0; t < nv && !taken; ++t)
                    taken = t != i && dm[t] == (m & -m) && k.vars[t] != k.vars[i] &&
                            ((p.peers(k.vars[i])[k.vars[t] >> 6] >> (k.vars[t] & 63)) & 1);
                if (taken) continue;
                dm[i] = m & -m;
                if (expr_may_hold(*k.expr, dm.data(), ad)) keep |= m & -m;
            }
            dm[i] = keep;
            if (!keep) return false;
            changed |= keep != was;
        }
        for (int a : k.expr->aux_read) {
            const std::vector<int> was = ad[a];
            if (was.size() < 2) continue;
            std::vector<int> keep;
            if (was.size() > 16) {
                // a wide unknown (a total of a few hundred values) is read as an interval: its ends move in while the
                // rule cannot hold there ("X1 is at least 21"), the inside is not tried value by value
                size_t lo = 0, hi = was.size();
                auto ok = [&](size_t i) {
                    ad[a] = {was[i]};
                    return expr_may_hold(*k.expr, dm.data(), ad);
                };
                while (lo < hi && !ok(lo)) ++lo;
                while (hi > lo && !ok(hi - 1)) --hi;
                keep.assign(was.begin() + lo, was.begin() + hi);
            } else {
                for (int w : was) {
                    ad[a] = {w};
                    if (expr_may_hold(*k.expr, dm.data(), ad)) keep.push_back(w);
                }
            }
            ad[a] = keep;
            if (keep.empty()) return false;
            changed |= keep.size() != was.size();
        }
    }
    return true;
}

bool Solver::aux_eq(const NConstraint& k, const std::vector<int>& auxv, std::vector<std::pair<int, int>>& dout,
                    std::vector<std::pair<int, int>>& aout) {
    constexpr pm_long AUX_CAP = 4096;
    const int side = expr_eq_unknown(*k.expr);
    if (side < 0) return false;
    const int U = (int)k.expr->root.kids[side].v;
    if (U < 0 || U >= (int)p.aux_values.size() || auxv[U] != AUX_UNSET) return false;
    for (int a : k.expr->aux_read)
        if (a != U && auxv[a] == AUX_UNSET) return false;  // E reads another open unknown
    const int nv = k.nv();
    std::vector<int> dg(nv), fd;
    pm_long combos = 1;
    for (int i = 0; i < nv; ++i)
        if (!(dg[i] = vals[k.vars[i]])) fd.push_back(i), combos = std::min<pm_long>(combos * popc(cand[k.vars[i]]), 1 << 20);
    if (combos > AUX_CAP) return false;
    const std::vector<int>& U_vals = p.aux_values[U];
    std::vector<char> usup(U_vals.size(), 0);
    std::vector<uint32_t> dsup(fd.size(), 0);
    bool any = false;
    std::function<void(size_t)> go = [&](size_t j) {
        if (j < fd.size()) {
            const int i = fd[j];
            for (uint32_t m = cand[k.vars[i]]; m; m &= m - 1) {
                dg[i] = lowdigit(m);
                if (!sees_same(k, dg, i)) go(j + 1);
            }
            dg[i] = 0;
            return;
        }
        long long v;
        if (!expr_side_value(*k.expr, side, dg.data(), auxv.data(), v)) return;
        const auto it = std::lower_bound(U_vals.begin(), U_vals.end(), (int)v);  // values are sorted
        if (it == U_vals.end() || *it != v || !auxf[aux_off[U] + (it - U_vals.begin())]) return;
        any = true;
        usup[it - U_vals.begin()] = 1;
        for (size_t t = 0; t < fd.size(); ++t) dsup[t] |= bit(dg[fd[t]]);
    };
    go(0);
    if (!any) return false;
    for (size_t t = 0; t < fd.size(); ++t) {
        const int c = k.vars[fd[t]];
        for (uint32_t m = cand[c] & ~dsup[t]; m; m &= m - 1) dout.emplace_back(c, lowdigit(m));
    }
    for (size_t i = 0; i < U_vals.size(); ++i)
        if (auxf[aux_off[U] + i] && !usup[i]) aout.emplace_back(U, (int)i);
    return true;
}

// AuxRule's reading of one rule, by what it reads (the puzzle, the rule, its cells' digits / candidates and its unknowns'
// open values): a case split's propagation re-reads every rule each round (thread-local, cleared when large)
namespace {
struct AuxMemo {
    int code = 0;  // 0: nothing to say
    std::vector<std::pair<int, int>> dout, aout;
    std::vector<std::pair<int, int>> jout;  // joint pairs ruled out: (layer variable, digit * 16 + value index)
    std::vector<std::pair<int, int>> eq;    // open cells sharing no house that every combination fills alike
};
thread_local std::unordered_map<std::string, AuxMemo> g_aux_memo;
}  // namespace
// how many variables (cells + unknowns / layer values read) a rule may have for AuxRule's per-case probing
// (diagnostics: PENCILMARK_PROBE_VARS; 12 by default)
static int probe_vars() {
    static const int n = [] {
        const char* e = std::getenv("PENCILMARK_PROBE_VARS");
        return e ? std::atoi(e) : 12;
    }();
    return n;
}
thread_local pm_long g_aux_hits = 0, g_aux_misses = 0;  // aux_memo_stats (diagnostics: stage 0 hit rate)
thread_local double g_aux_ms[5] = {0, 0, 0, 0, 0};       // ... and ms per reading path: capped, bounds, probing,
                                                          // per value, enumeration
struct AuxTimer {
    int i;
    std::chrono::steady_clock::time_point t0 = std::chrono::steady_clock::now();
    explicit AuxTimer(int i_) : i(i_) {}
    ~AuxTimer() { g_aux_ms[i] += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count(); }
};
thread_local double g_lt_ms[5] = {0, 0, 0, 0, 0};  // LayerTrial's parts (ms): setup, multi-rule facts, value
                                                     // trials, layer fish, forced values from digit places
struct LTClock {
    std::chrono::steady_clock::time_point t = std::chrono::steady_clock::now();
    void mark(int i) {
        const auto now = std::chrono::steady_clock::now();
        g_lt_ms[i] += std::chrono::duration<double, std::milli>(now - t).count();
        t = now;
    }
    int last = 0;
    ~LTClock() { mark(last); }
};
std::vector<pm_long> aux_memo_stats() {
    std::vector<pm_long> r{g_aux_hits, g_aux_misses};
    for (double x : g_aux_ms) r.push_back((pm_long)x);
    for (double x : g_lt_ms) r.push_back((pm_long)x);
    return r;
}

void Solver::aux_rule(MoveBuf& out) {
    if (!has_aux() || disabled[AUX_RULE]) return;
    constexpr pm_long AUX_CAP = 4096;
    const int NA = (int)p.aux_values.size();
    std::function<int(int)> count = [&](int a) {
        int n = 0;
        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i) n += auxf[i];
        return n;
    };
    std::vector<int> auxv(NA, AUX_UNSET);  // the values already decided
    for (int a = 0; a < NA; ++a)
        if (count(a) == 1)
            for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                if (auxf[i]) auxv[a] = p.aux_values[a][i - aux_off[a]];
    // the count rules ("one hot cell per row"): two of a rule's layer values they reject together are never combined
    // ("a 14 cage in one row is not hot twice"); per puzzle, which rules count (absint.cpp expr_count_moves)
    std::vector<std::vector<int>> dom0(NA);
    for (int a = 0; a < NA; ++a)
        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
            if (auxf[i]) dom0[a].push_back(p.aux_values[a][i - aux_off[a]]);
    static thread_local std::unordered_map<uint64_t, std::vector<std::pair<int, int>>> count_rules;  // (list, index)
    auto itc = count_rules.find(p.uid);
    if (itc == count_rules.end()) {
        std::vector<std::pair<int, int>> cr;
        for (int li = 0; li < 2; ++li) {
            const std::vector<NConstraint>& L = li ? p.nary_big : p.nary;
            for (size_t ki = 0; ki < L.size(); ++ki) {
                const NConstraint& k = L[ki];
                if (k.type != NT_EXPR || !k.expr || k.expr->aux_read.empty()) continue;
                if (expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;
                // from the structure alone (every digit, every value): which state came first must not matter
                std::vector<uint32_t> dm(k.nv(), p.full);
                std::vector<std::vector<int>> ad(NA);
                for (int y : k.expr->aux_read)
                    if (y >= 0 && y < NA) ad[y] = p.aux_values[y];
                if (expr_count_moves(*k.expr, p.D, dm, ad, true).any) cr.push_back({li, (int)ki});
            }
        }
        if (count_rules.size() > 64) count_rules.clear();
        itc = count_rules.emplace(p.uid, std::move(cr)).first;
    }
    std::vector<const NConstraint*> crules;
    for (auto [li, ki] : itc->second) {
        const std::vector<NConstraint>& L = li ? p.nary_big : p.nary;
        if (ki < (int)L.size()) crules.push_back(&L[ki]);
    }
    // house-sized count rules only: a grid-wide one ("each digit hot once") reads every cell, so a result relying on it
    // would have to be recomputed after any change (checklist H1: read sets with witnesses)
    std::vector<std::vector<const NConstraint*>> counts_of(NA);
    for (const NConstraint* c : crules)
        if (c->nv() <= p.D)
            for (int a : c->expr->aux_read)
                if (a >= 0 && a < NA) counts_of[a].push_back(c);
    // read with every other cell open (all digits, all values): the answer is the count rule's own ("never two hot
    // cells in a row"), the same at every state -- cached per puzzle, nothing for a memo key to track; what other
    // cells' decided values add is LayerCount's
    static thread_local std::map<std::tuple<uint64_t, int, int, int, int>, bool> rejected;
    if (rejected.size() > 200000) rejected.clear();
    auto rejects = [&](int a, int wa, int b, int wb) {  // a count rule reading both rejects a = wa with b = wb
        if (a > b) std::swap(a, b), std::swap(wa, wb);
        const auto key = std::make_tuple(p.uid, a, wa, b, wb);
        if (auto it = rejected.find(key); it != rejected.end()) return it->second;
        bool rej = false;
        for (const NConstraint* c : counts_of[a]) {
            if (std::find(c->expr->aux_read.begin(), c->expr->aux_read.end(), b) == c->expr->aux_read.end()) continue;
            std::vector<uint32_t> dm(c->nv(), p.full);
            std::vector<std::vector<int>> ad(NA);
            for (int y : c->expr->aux_read)
                if (y >= 0 && y < NA) ad[y] = p.aux_values[y];
            ad[a] = {wa}, ad[b] = {wb};
            if (expr_count_moves(*c->expr, p.D, dm, ad, true).infeasible) { rej = true; break; }
        }
        return rejected[key] = rej;
    };
    // jobs (design review stage 2): each rule's last reading sleeps until something it reads changes -- the cells'
    // digits / candidates and the unknowns / layer values it reads -- then it is read again (through the memo). The
    // change set is the difference from the previous call's state, so the same thread may list other states between.
    struct AuxJobs {
        uint64_t uid = 0;
        const Puzzle* pz = nullptr;  // a derived puzzle may share the uid: the object and each slot's rule must match
        // per context (main / inside a branch): the state of that context's previous call -- a slot's reading
        // is compared with the state its own context last saw, never with the other's
        std::vector<uint8_t> vals[2];
        std::vector<uint32_t> cand[2];
        std::vector<char> auxf[2];
        std::vector<Solver::JMask> jx[2];
        std::vector<AuxMemo> last[2];
        std::vector<char> have[2];
        std::vector<const NConstraint*> rule[2];
        // per main-route slot: each probe's witness -- the domains its narrowing reached ((variable i or -1 - aux,
        // value) -> digits per rule variable, values per aux variable read). While all of it is still open, the
        // probe would reach at least that fixpoint again (narrowing is monotone): no need to probe
        using Witness = std::pair<std::vector<uint32_t>, std::vector<std::vector<int>>>;
        std::vector<std::map<std::pair<int, int>, Witness>> wit;
        // per main-route slot: each probe's support TUPLE (design review stage 3) -- one assignment of the rule's
        // cells and layer / unknown values that satisfies it; its read set is those few literals, so it outlives
        // the witness: while each of its digits / values (and joint pairs) is still open, the value is supported
        using Tuple = std::pair<std::vector<int>, std::vector<std::pair<int, int>>>;  // digits, (aux var, value)
        std::vector<std::map<std::pair<int, int>, Tuple>> tup;
    };
    static thread_local AuxJobs jobs;
    const bool jobs_on = !memo_off("jobs");
    std::vector<char> chg_cell(p.N, 1), chg_aux(NA, 1);
    const int ib = in_branch > 0;
    if (jobs_on) {
        if (jobs.uid != p.uid || jobs.pz != &p) {
            jobs = AuxJobs();
            jobs.uid = p.uid, jobs.pz = &p;
        }
        if (jobs.cand[ib].size() == (size_t)p.N && jobs.auxf[ib].size() == auxf.size()) {
            for (int c = 0; c < p.N; ++c) chg_cell[c] = jobs.vals[ib][c] != vals[c] || jobs.cand[ib][c] != cand[c];
            for (int a = 0; a < NA; ++a) {
                chg_aux[a] = 0;
                for (int i = aux_off[a]; i < aux_off[a + 1] && !chg_aux[a]; ++i) chg_aux[a] = jobs.auxf[ib][i] != auxf[i];
                if (jobs.jx[ib].size() == jx.size()) chg_aux[a] |= jobs.jx[ib][a] != jx[a];
            }
        } else {
            jobs.have[ib].assign(jobs.have[ib].size(), 0);
        }
        jobs.vals[ib].assign(vals.begin(), vals.end());
        jobs.cand[ib].assign(cand.begin(), cand.end());
        jobs.auxf[ib].assign(auxf.begin(), auxf.end());
        jobs.jx[ib].assign(jx.begin(), jx.end());
    }
    // facts confined to few cells, read with a small rule ("box 7's 1 is in r7c1-r7c2, and so is its shifted
    // cell"): a complete house's digit d with its open places all in the cells; an exactly-one layer house whose live
    // literals all lie in them. A rule enumerated without them and finding nothing is read again with those inside
    // its cells (code 7425)
    struct DFact { int d; std::vector<int> cells; };
    struct LFact { const JHouse* h; std::vector<int> cells; };
    std::vector<DFact> dfacts;
    std::vector<LFact> lfacts;
    for (int gi : p.houses) {
        const Group& G = p.groups[gi];
        if ((int)G.cells.size() != p.D) continue;
        for (int d = 1; d <= p.D; ++d) {
            std::vector<int> cs;
            bool placed = false;
            for (int c : G.cells) {
                placed |= vals[c] == d;
                if (!vals[c] && (cand[c] & bit(d))) cs.push_back(c);
            }
            if (!placed && cs.size() >= 2 && cs.size() <= 6) dfacts.push_back({d, cs});
        }
    }
    if (jx.size() == p.aux_values.size())
        for (const JHouse& h : jhouses_of(p)) {
            if (h.pmask.any()) continue;
            std::vector<int> cs;
            bool sure = false;
            for (int c : h.cells) {
                const int a = p.aux_u + h.layer * p.N + c;
                bool live = false;
                for (int d = 1; d <= p.D && !live; ++d) {
                    if (h.digit && d != h.digit) continue;
                    if (vals[c] ? vals[c] != d : !(cand[c] & bit(d))) continue;
                    for (uint32_t m = h.vmask; m && !live; m &= m - 1) live = joint_live(a, d, __builtin_ctz(m));
                }
                if (!live) continue;
                cs.push_back(c);
                bool all_in = true;  // decided: its digit and value both inside the literal
                if (h.digit && vals[c] != h.digit) all_in = false;
                if (!vals[c]) all_in = false;
                for (int i = aux_off[a]; i < aux_off[a + 1] && all_in; ++i)
                    if (auxf[i] && !((h.vmask >> (i - aux_off[a])) & 1)) all_in = false;
                sure |= all_in;
                if (cs.size() > 6) break;
            }
            if (!sure && cs.size() >= 2 && cs.size() <= 6) lfacts.push_back({&h, cs});
        }
    auto emit_for = [&](const NConstraint& k, const AuxMemo& r) {
        // cells the rule makes equal (whatever the digit): one identity class, as a host colors them alike -- the
        // class then carries candidates between them and later readings (identity layer; coloring on). Code 7433.
        if (id_on())
            for (auto [x, y] : r.eq) {
                if (vals[x] || vals[y]) continue;
                const int ka = id_anchor(x), kb = id_anchor(y);
                if (ka == kb || id_paired(ka, kb) || !(idc[x] || idc[y] || id_live() < ID_CAP)) continue;
                Move& m = new_move(out, EQUAL_DIGITS, 1.0, popc(cand[x]));
                add_aeff(out, m, AE_ID_JOIN, std::max(ka, kb), std::min(ka, kb));
                for (uint32_t d = cand[x] & ~cand[y]; d; d &= d - 1) add_el(out, m, x, lowdigit(d));
                for (uint32_t d = cand[y] & ~cand[x]; d; d &= d - 1) add_el(out, m, y, lowdigit(d));
                std::vector<int> pc{x, y};
                set_pattern(out, m, pc);
                m.shape = pspread(pc);
                meta8(m, 2 + k.nv() / 3, 2, popc(cand[x]), 1, 1, 0, 0, 1, m.shape);
                m.nk = NM_NARY;
                m.na = k.index;
                m.code = 7433;
            }
        if (!r.code) return;
        // a reading reused from an earlier state: only the effects still open (candidates only shrink, so what it
        // proved still holds; applied effects would repeat a step that changes nothing)
        std::vector<std::pair<int, int>> dl, al;
        for (auto& e : r.dout)
            if (!vals[e.first] && (cand[e.first] & bit(e.second))) dl.push_back(e);
        for (auto& e : r.aout)
            if (auxf[aux_off[e.first] + e.second]) al.push_back(e);
        std::vector<std::pair<int, int>> jl;
        for (auto& e : r.jout)
            if (joint_live(e.first, e.second / 16, e.second % 16)) jl.push_back(e);
        if (dl.empty() && al.empty() && jl.empty()) return;
        Move& m = new_move(out, AUX_RULE, 1.0, (int)(dl.size() + al.size() + jl.size()));
        for (auto& e : dl) add_el(out, m, e.first, e.second);
        for (auto& e : al) add_aeff(out, m, AE_AUX, e.first, e.second);
        for (auto& e : jl) add_aeff(out, m, AE_JOINT, e.first, e.second);
        set_pattern(out, m, k.vars);
        m.nk = NM_NARY;
        m.na = k.index;  // the rule (a lemma rule: priced by its lemma)
        m.nb = k.group;
        m.code = r.code;
    };
    int jn = -1;  // the rule's job slot
    bool would_sleep = false;
    for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
        for (const NConstraint& k : *L) {
            if (k.type != NT_EXPR || !k.expr || k.expr->aux_read.empty()) continue;
            if (expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;  // those layers' techniques
            if (k.index >= 0 && k.index < (int)p.nary_specs.size() && p.nary_specs[k.index].gated) continue;  // lemmas stand in
            ++jn;
            would_sleep = false;
            std::vector<std::pair<int, std::vector<int>>> rd;  // (digit, rule variables) one of which holds it
            std::vector<std::pair<const JHouse*, std::vector<std::pair<int, int>>>> rl;  // (house, (variable, layer var))
            {
                auto var_of = [&](int c) {
                    for (int i = 0; i < k.nv(); ++i)
                        if (k.vars[i] == c) return i;
                    return -1;
                };
                for (const DFact& f : dfacts) {
                    std::vector<int> vs;
                    for (int c : f.cells) {
                        const int i = var_of(c);
                        if (i < 0) { vs.clear(); break; }
                        vs.push_back(i);
                    }
                    if (!vs.empty()) rd.push_back({f.d, vs});
                }
                for (const LFact& f : lfacts) {
                    std::vector<std::pair<int, int>> vs;
                    for (int c : f.cells) {
                        const int i = var_of(c), a = p.aux_u + f.h->layer * p.N + c;
                        if (i < 0 || std::find(k.expr->aux_read.begin(), k.expr->aux_read.end(), a) == k.expr->aux_read.end()) {
                            vs.clear();
                            break;
                        }
                        vs.push_back({i, a});
                    }
                    if (!vs.empty()) rl.push_back({f.h, vs});
                }
            }
            if (jobs_on) {
                if (jobs.last[ib].size() <= (size_t)jn)
                    jobs.last[ib].resize(jn + 1), jobs.have[ib].resize(jn + 1, 0), jobs.rule[ib].resize(jn + 1, nullptr);
                if (jobs.rule[ib][jn] != &k) {
                    jobs.have[ib][jn] = 0, jobs.rule[ib][jn] = &k;
                    if (ib == 0 && jobs.wit.size() > (size_t)jn) jobs.wit[jn].clear();
                    if (ib == 0 && jobs.tup.size() > (size_t)jn) jobs.tup[jn].clear();
                }
                bool asleep = jobs.have[ib][jn] && rd.empty() && rl.empty();  // facts read outside cells
                for (int i = 0; i < k.nv() && asleep; ++i) asleep = !chg_cell[k.vars[i]];
                for (int a : k.expr->aux_read)
                    if (asleep && a >= 0 && a < NA) asleep = !chg_aux[a];
                static const bool check = std::getenv("PENCILMARK_JOBS_CHECK") != nullptr;  // diagnostics
                if (asleep && check) asleep = false, would_sleep = true;
                if (asleep) {
                    emit_for(k, jobs.last[ib][jn]);
                    continue;
                }
            }
            // whatever this rule's reading comes to below, it is the job's result until its inputs change
            struct Keep {
                AuxJobs& j; int ib, jn; bool on; bool ws; int idx; const AuxMemo* res = nullptr;
                ~Keep() {
                    if (!on || deadline_passed()) return;
                    const AuxMemo now = res ? *res : AuxMemo();
                    const AuxMemo& was = j.last[ib][jn];
                    if (ws && (now.code != was.code || now.dout != was.dout || now.aout != was.aout || now.jout != was.jout))
                        fprintf(stderr, "JOBS MISMATCH rule %d branch %d: code %d/%d dout %zu/%zu aout %zu/%zu\n", idx, ib,
                                was.code, now.code, was.dout.size(), now.dout.size(), was.aout.size(), now.aout.size());
                    j.last[ib][jn] = now;
                    j.have[ib][jn] = now.code != 7425;  // read with facts outside its cells: never reused as a job
                }
            } keep{jobs, ib, jn, jobs_on, would_sleep, k.index};
            const int nv = k.nv();
            std::vector<int> dg(nv), fd, fr;
            pm_long combos = 1;  // saturating
            for (int i = 0; i < nv; ++i)
                if (!(dg[i] = vals[k.vars[i]])) fd.push_back(i), combos = std::min<pm_long>(combos * popc(cand[k.vars[i]]), 1 << 20);
            for (int a : k.expr->aux_read)
                if (auxv[a] == AUX_UNSET) fr.push_back(a), combos = std::min<pm_long>(combos * count(a), 1 << 20);
            if (fd.empty() && fr.empty()) continue;
            std::string key;
            {
                auto put = [&](uint64_t x) { key.append(reinterpret_cast<const char*>(&x), sizeof x); };
                put(p.uid), put((uint64_t)(uintptr_t)&k), put((uint64_t)(in_branch > 0));  // a branch reads less
                for (int i = 0; i < nv; ++i) put(vals[k.vars[i]] ? (1ull << 40 | (uint64_t)vals[k.vars[i]]) : cand[k.vars[i]]);
                if (!idc.empty())  // identity classes of the rule's cells (a join changes no candidate)
                    for (int i = 0; i < nv; ++i) put(3000 + (uint64_t)idc[k.vars[i]]);
                for (int a : k.expr->aux_read)
                    for (int i = aux_off[a]; i < aux_off[a + 1]; ++i) key.push_back(auxf[i] ? '1' : '0');
                for (int a : k.expr->aux_read)  // the joint pairs ruled out
                    if (a < (int)jx.size() && jx[a].any()) {
                        put((uint64_t)a);
                        for (int w = 0; w < JW; ++w) put(jword(jx[a], w));
                    }
                for (auto& [d, vs] : rd) {  // the confined facts
                    put(1000 + (uint64_t)d);
                    for (int i : vs) put((uint64_t)i);
                }
                for (auto& [h, vs] : rl) {
                    put(2000), put((uint64_t)(uintptr_t)h);
                    for (auto [i, a] : vs) put((uint64_t)i);
                }
            }
            auto emit = [&](const AuxMemo& r) { emit_for(k, r); };
            if (auto it = memo_off("aux") ? g_aux_memo.end() : g_aux_memo.find(key); it != g_aux_memo.end()) {
                ++g_aux_hits;
                keep.res = &it->second;
                emit(it->second);
                continue;
            }
            if (g_aux_memo.size() > 50000) g_aux_memo.clear();
            ++g_aux_misses;
            AuxMemo& r = g_aux_memo[key];
            r = AuxMemo();  // a fresh reading (PENCILMARK_NO_MEMO skips the lookup, not the entry)
            keep.res = &r;
            if (combos > AUX_CAP) {  // too many with the values: "E == U" is read by E's values alone (as a cage total)
                AuxTimer aux_t0(0);
                if (aux_eq(k, auxv, r.dout, r.aout) && !(r.dout.empty() && r.aout.empty())) r.code = 7402;
                if (!r.code) {  // too many to enumerate: E's bounds (distinct digits over a house) bound U, and a
                    AuxTimer aux_t1(1);
                    // digit whose bounds miss every value U can still take goes ("six different digits, one tripled,
                    // make 24: the tripled digit is 1")
                    const int side = expr_eq_unknown(*k.expr);
                    const int U = side < 0 ? -1 : (int)k.expr->root.kids[side].v;
                    if (U >= 0 && U < NA) {
                        std::vector<uint32_t> dm(nv);
                        std::vector<std::vector<int>> vh(nv), ad(NA);
                        for (int i = 0; i < nv; ++i) {
                            const int c = k.vars[i];
                            dm[i] = vals[c] ? bit(vals[c]) : cand[c];
                            for (int g : p.groups_of[c])
                                if (p.groups[g].complete && (int)p.groups[g].cells.size() == p.D) vh[i].push_back(g);
                        }
                        for (int a = 0; a < NA; ++a)
                            for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                                if (auxf[i]) ad[a].push_back(p.aux_values[a][i - aux_off[a]]);
                        long long lo, hi;
                        if (expr_side_bounds(*k.expr, p.D, dm, vh, ad, lo, hi)) {
                            for (int i = aux_off[U]; i < aux_off[U + 1]; ++i) {
                                const int v = p.aux_values[U][i - aux_off[U]];
                                if (auxf[i] && (v < lo || v > hi)) r.aout.emplace_back(U, i - aux_off[U]);
                            }
                            if (r.aout.empty()) {  // U's values all within reach: per open digit, its own bounds
                                for (int fi : fd) {
                                    const uint32_t keep = dm[fi];
                                    for (uint32_t m = keep; m; m &= m - 1) {
                                        dm[fi] = m & -m;
                                        long long l2, h2;
                                        if (!expr_side_bounds(*k.expr, p.D, dm, vh, ad, l2, h2)) continue;
                                        bool reach = false;
                                        for (int v : ad[U]) reach |= v >= l2 && v <= h2;
                                        if (!reach) r.dout.emplace_back(k.vars[fi], lowdigit(m));
                                    }
                                    dm[fi] = keep;
                                }
                                // a digit every filling uses ("four distinct digits adding to 28 or more hold the 8 and
                                // the 9"): with it gone from every open cell the sum misses all of U's values, so it
                                // is in the rule's cells -- the other cells of a house holding them all lose it
                                std::vector<int> common = nv ? vh[0] : std::vector<int>();
                                for (int i = 1; i < nv && !common.empty(); ++i) {
                                    std::vector<int> keepc;
                                    for (int g2 : common)
                                        if (std::find(vh[i].begin(), vh[i].end(), g2) != vh[i].end()) keepc.push_back(g2);
                                    common = keepc;
                                }
                                for (int d = 1; d <= p.D && !common.empty() && !fd.empty(); ++d) {
                                    bool placed = false, open_d = false;
                                    for (int i = 0; i < nv; ++i) {
                                        placed |= vals[k.vars[i]] == d;
                                        open_d |= !vals[k.vars[i]] && (dm[i] & bit(d));
                                    }
                                    if (placed || !open_d) continue;
                                    std::vector<uint32_t> dm2 = dm;
                                    bool empty = false;
                                    for (int fi : fd) empty |= !(dm2[fi] &= ~bit(d));
                                    if (empty) continue;  // a cell holds nothing but d: other techniques
                                    long long l2, h2;
                                    if (!expr_side_bounds(*k.expr, p.D, dm2, vh, ad, l2, h2)) continue;
                                    bool reach = false;
                                    for (int v : ad[U]) reach |= v >= l2 && v <= h2;
                                    if (reach) continue;
                                    for (int g2 : common)
                                        for (int c : p.groups[g2].cells)
                                            if (!vals[c] && (cand[c] & bit(d)) &&
                                                std::find(k.vars.begin(), k.vars.end(), c) == k.vars.end())
                                                r.dout.emplace_back(c, d);
                                }
                            }
                            if (!r.aout.empty() || !r.dout.empty()) r.code = 7408;
                        }
                    } else if (U < 0) {  // "cells == f(unknowns)": the cell side's bounds against each unknown value
                        std::vector<uint32_t> dm(nv);
                        std::vector<std::vector<int>> vh(nv), ad(NA);
                        for (int i = 0; i < nv; ++i) {
                            const int c = k.vars[i];
                            dm[i] = vals[c] ? bit(vals[c]) : cand[c];
                            for (int g : p.groups_of[c])
                                if (p.groups[g].complete && (int)p.groups[g].cells.size() == p.D) vh[i].push_back(g);
                        }
                        for (int a = 0; a < NA; ++a)
                            for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                                if (auxf[i]) ad[a].push_back(p.aux_values[a][i - aux_off[a]]);
                        // each touched house's cells outside the rule: the least / most they add up to (distinct)
                        std::vector<std::pair<long long, long long>> rest(p.groups.size(), {1, 0});
                        for (int i = 0; i < nv; ++i)
                            for (int g : vh[i]) {
                                if (rest[g].first <= rest[g].second) continue;
                                uint32_t uni = 0;
                                int j = 0;
                                long long fixed = 0;
                                for (int c : p.groups[g].cells) {
                                    if (std::find(k.vars.begin(), k.vars.end(), c) != k.vars.end()) continue;
                                    if (vals[c]) fixed += vals[c];
                                    else uni |= cand[c], ++j;
                                }
                                long long lo = fixed, hi = fixed;
                                int n1 = 0, n2 = 0;
                                for (int d = 1; d <= p.D && n1 < j; ++d)
                                    if (uni & bit(d)) lo += d, ++n1;
                                for (int d = p.D; d >= 1 && n2 < j; --d)
                                    if (uni & bit(d)) hi += d, ++n2;
                                if (n1 == j) rest[g] = {lo, hi};
                            }
                        std::vector<std::pair<int, int>> cut;
                        if (expr_unknown_side_cut(*k.expr, p.D, dm, vh, ad, cut, &rest))
                            for (auto [a, w] : cut) {
                                const auto& vv = p.aux_values[a];
                                const int vi = (int)(std::find(vv.begin(), vv.end(), w) - vv.begin());
                                if (vi < (int)vv.size() && auxf[aux_off[a] + vi]) r.aout.emplace_back(a, vi);
                            }
                        if (!r.aout.empty()) r.code = 7408;
                    }
                }
                if (!r.code && !in_branch && nv + (int)fr.size() <= probe_vars()) {
                    AuxTimer aux_t2(2);
                    // any other shape, few variables (a 5-cell thermo on values with its layer cells: 10), as the rule
                    // lemmas narrow a case: each open digit / value is tried, the others keep the values under which
                    // the rule can still hold (read abstractly), to a fixpoint; a try that leaves a variable nothing
                    // goes -- a chain of comparisons followed link by link ("a 9 on the bulb needs a hot 8 above it,
                    // and then nothing fits above that")
                    std::vector<uint32_t> dm(nv);
                    for (int i = 0; i < nv; ++i) dm[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                    std::vector<std::vector<int>> ad(NA);
                    for (int a : k.expr->aux_read)
                        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                            if (auxf[i]) ad[a].push_back(p.aux_values[a][i - aux_off[a]]);
                    auto narrow = [&](std::vector<uint32_t>& D_, std::vector<std::vector<int>>& A_) { return rule_narrow(k, D_, A_); };
                    std::vector<uint32_t> dmn = dm;
                    std::vector<std::vector<int>> adn = ad;
                    std::map<std::pair<int, int>, AuxJobs::Witness>* W = nullptr;
                    if (jobs_on && ib == 0) {
                        if (jobs.wit.size() <= (size_t)jn) jobs.wit.resize(jn + 1);
                        W = &jobs.wit[jn];
                    }
                    auto still = [&](const AuxJobs::Witness& w) {  // the witness is inside today's domains
                        for (int j = 0; j < nv; ++j)
                            if (w.first[j] & ~dmn[j]) return false;
                        for (int a : k.expr->aux_read)
                            for (int x : w.second[a])
                                if (std::find(adn[a].begin(), adn[a].end(), x) == adn[a].end()) return false;
                        return true;
                    };
                    std::map<std::pair<int, int>, AuxJobs::Tuple>* TT = nullptr;
                    if (W) {
                        if (jobs.tup.size() <= (size_t)jn) jobs.tup.resize(jn + 1);
                        TT = &jobs.tup[jn];
                    }
                    auto vidx = [&](int a, int w) {
                        const auto& vv = p.aux_values[a];
                        return (int)(std::find(vv.begin(), vv.end(), w) - vv.begin());
                    };
                    auto tuple_ok = [&](const AuxJobs::Tuple& t) {  // every literal still open (and its joint pairs)
                        for (int i = 0; i < nv; ++i)
                            if (!(dmn[i] & bit(t.first[i]))) return false;
                        for (auto [a, w] : t.second) {
                            if (std::find(adn[a].begin(), adn[a].end(), w) == adn[a].end()) return false;
                            if (joint_ok(a))
                                for (int i = 0; i < nv; ++i)
                                    if (k.vars[i] == aux_cell(a) && !joint_live(a, t.first[i], vidx(a, w))) return false;
                        }
                        return true;
                    };
                    // a satisfying assignment inside the narrowed domains: digits (cells of a shared house differ),
                    // then the values read; pruned by may_hold once the digits are set; a node budget
                    auto find_tuple = [&](const std::vector<uint32_t>& D_, const std::vector<std::vector<int>>& A_,
                                          AuxJobs::Tuple& out_t) {
                        std::vector<int> dg(nv, 0), av(NA, AUX_UNSET);
                        std::vector<int> ar(k.expr->aux_read.begin(), k.expr->aux_read.end());
                        int budget = 400;
                        std::function<bool(int)> go_v = [&](int j) -> bool {
                            if (--budget < 0) return false;
                            if (j == (int)ar.size()) return expr_holds(*k.expr, dg.data(), nullptr, nullptr, av.data());
                            const int a = ar[j];
                            if (a < 0 || a >= NA) return go_v(j + 1);
                            for (int w : A_[a]) {
                                if (joint_ok(a)) {
                                    bool ok = true;
                                    for (int i = 0; i < nv && ok; ++i)
                                        if (k.vars[i] == aux_cell(a)) ok = joint_live(a, dg[i], vidx(a, w));
                                    if (!ok) continue;
                                }
                                av[a] = w;
                                if (go_v(j + 1)) return true;
                            }
                            av[a] = AUX_UNSET;
                            return false;
                        };
                        std::function<bool(int)> go_d = [&](int i) -> bool {
                            if (--budget < 0) return false;
                            if (i == nv) {
                                std::vector<uint32_t> one(nv);
                                for (int t = 0; t < nv; ++t) one[t] = bit(dg[t]);
                                return expr_may_hold(*k.expr, one.data(), A_) && go_v(0);
                            }
                            for (uint32_t m = D_[i]; m; m &= m - 1) {
                                dg[i] = lowdigit(m);
                                if (!sees_same(k, dg, i) && go_d(i + 1)) return true;
                            }
                            dg[i] = 0;
                            return false;
                        };
                        if (!go_d(0)) return false;
                        out_t.first = dg;
                        out_t.second.clear();
                        for (int a : ar)
                            if (a >= 0 && a < NA && av[a] != AUX_UNSET) out_t.second.push_back({a, av[a]});
                        return true;
                    };
                    auto probe = [&](int key_var, int val, std::vector<uint32_t>& D_, std::vector<std::vector<int>>& A_) {
                        if (TT) {
                            auto it = TT->find({key_var, val});
                            if (it != TT->end() && tuple_ok(it->second)) return true;
                        }
                        if (W) {
                            auto it = W->find({key_var, val});
                            if (it != W->end() && still(it->second)) return true;
                        }
                        if (!narrow(D_, A_)) return false;
                        if (W) {
                            std::vector<std::vector<int>> keep(NA);
                            for (int a : k.expr->aux_read) keep[a] = A_[a];
                            (*W)[{key_var, val}] = {D_, std::move(keep)};
                        }
                        if (TT) {
                            AuxJobs::Tuple t;
                            if (find_tuple(D_, A_, t)) (*TT)[{key_var, val}] = std::move(t);
                        }
                        return true;
                    };
                    if (narrow(dmn, adn)) {  // dead: a contradiction other techniques show
                        for (int i : fd)
                            for (uint32_t m = dmn[i]; m && !deadline_passed(); m &= m - 1) {
                                std::vector<uint32_t> D_ = dmn;
                                std::vector<std::vector<int>> A_ = adn;
                                D_[i] = m & -m;
                                if (!probe(i, lowdigit(m), D_, A_)) dmn[i] &= ~(m & -m);
                            }
                        for (int a : fr)
                            for (int w : std::vector<int>(adn[a].size() <= 16 ? adn[a] : std::vector<int>())) {
                                // (a wide unknown is not tried value by value: its interval is rule_narrow's)
                                if (deadline_passed()) break;
                                std::vector<uint32_t> D_ = dmn;
                                std::vector<std::vector<int>> A_ = adn;
                                A_[a] = {w};
                                if (!probe(-1 - a, w, D_, A_)) adn[a].erase(std::find(adn[a].begin(), adn[a].end(), w));
                            }
                        bool empty = false;
                        for (int i : fd) empty |= !dmn[i];
                        for (int a : fr) empty |= adn[a].empty();
                        if (!empty && !deadline_passed()) {
                            for (int i : fd)
                                for (uint32_t m = dm[i] & ~dmn[i]; m; m &= m - 1) r.dout.emplace_back(k.vars[i], lowdigit(m));
                            for (int a : fr)
                                for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                                    if (auxf[i] && std::find(adn[a].begin(), adn[a].end(), p.aux_values[a][i - aux_off[a]]) == adn[a].end())
                                        r.aout.emplace_back(a, i - aux_off[a]);
                            if (!r.dout.empty() || !r.aout.empty()) r.code = 7401;
                        }
                    }
                }
                // a count rule ("one doubler per house") is LayerCount's: read per value here it cost ~40% of a
                // layer puzzle's grade (PENCILMARK_COUNT_PER_VALUE=1: read it here too, the old way)
                static const bool count_pv = std::getenv("PENCILMARK_COUNT_PER_VALUE") != nullptr;
                const bool is_count = std::find(crules.begin(), crules.end(), &k) != crules.end();
                if (!r.code && !fr.empty() && (count_pv || !is_count || nv == 0)) {  // (a count over unknowns alone: LayerCount reads "== k" only)
                    AuxTimer aux_t3(3);
                    // many variables: each open unknown / layer value stays while the rule, read abstractly with the
                    // others' values, can hold ("22 cells add up to at least 22: D * D is no 1, 4, 9 or 16")
                    std::vector<uint32_t> dm(nv);
                    for (int i = 0; i < nv; ++i) dm[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                    std::vector<std::vector<int>> ad(NA);
                    for (int a : k.expr->aux_read)
                        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                            if (auxf[i]) ad[a].push_back(p.aux_values[a][i - aux_off[a]]);
                    for (int a : fr) {
                        if (ad[a].size() > 64 || deadline_passed()) continue;
                        const std::vector<int> was = ad[a];
                        for (int w : was) {
                            ad[a] = {w};
                            if (!expr_may_hold(*k.expr, dm.data(), ad))
                                for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                                    if (auxf[i] && p.aux_values[a][i - aux_off[a]] == w) r.aout.emplace_back(a, i - aux_off[a]);
                        }
                        ad[a] = was;
                    }
                    if (!r.aout.empty()) r.code = 7408;
                }
                // too wide to probe with a fixpoint (a remote sum reads its row and column: 19 cells): each open digit
                // of a cell, and each (digit, layer value) pair of it, tried once against the rule read abstractly
                // ("a plain 9 at r1c3 points 9 cells away: off the grid every way")
                if (!r.code && !in_branch && !is_count && nv + (int)fr.size() > probe_vars() && nv <= 100) {
                    AuxTimer aux_t3(3);
                    std::vector<uint32_t> dm(nv);
                    for (int i = 0; i < nv; ++i) dm[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                    std::vector<std::vector<int>> ad(NA);
                    for (int a : k.expr->aux_read)
                        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                            if (auxf[i]) ad[a].push_back(p.aux_values[a][i - aux_off[a]]);
                    for (int i : fd) {
                        if (deadline_passed()) break;
                        const uint32_t keep = dm[i];
                        int la = -1;  // the cell's layer variable the rule reads (joint pairs)
                        for (int a : k.expr->aux_read)
                            if (joint_ok(a) && aux_cell(a) == k.vars[i]) la = a;
                        for (uint32_t m = keep; m; m &= m - 1) {
                            const int d = lowdigit(m);
                            dm[i] = bit(d);
                            if (!expr_may_hold(*k.expr, dm.data(), ad)) {
                                r.dout.emplace_back(k.vars[i], d);
                                continue;
                            }
                            if (la < 0) continue;
                            const std::vector<int> was = ad[la];
                            const auto& vv = p.aux_values[la];
                            for (int w : was) {
                                const int vi = (int)(std::find(vv.begin(), vv.end(), w) - vv.begin());
                                if (!joint_live(la, d, vi)) continue;
                                ad[la] = {w};
                                if (!expr_may_hold(*k.expr, dm.data(), ad)) r.jout.emplace_back(la, d * 16 + vi);
                            }
                            ad[la] = was;
                        }
                        dm[i] = keep;
                    }
                    if (!r.dout.empty() || !r.jout.empty()) r.code = 7401;
                }
                if (deadline_passed()) g_aux_memo.erase(key);
                else emit(r);
                continue;
            }
            AuxTimer aux_t4(4);  // diagnostics: the enumeration
            auto facts_hold = [&](const std::vector<int>& dgs, const std::vector<int>& avs) {
                for (auto& [d, vs] : rd) {
                    bool hit = false;
                    for (int i : vs) hit |= dgs[i] == d;
                    if (!hit) return false;
                }
                for (auto& [h, vs] : rl) {
                    int n = 0;
                    for (auto [i, a] : vs) {
                        if (avs[a] == AUX_UNSET) { n = 1; break; }  // not read here: no say
                        if (h->digit && dgs[i] != h->digit) continue;
                        const auto& vv = p.aux_values[a];
                        const int vi = (int)(std::find(vv.begin(), vv.end(), avs[a]) - vv.begin());
                        n += (h->vmask >> vi) & 1;
                    }
                    if (n != 1) return false;
                }
                return true;
            };
            auto enumerate = [&](bool use_facts) -> bool {
            std::vector<std::vector<char>> sup(fr.size());
            for (size_t j = 0; j < fr.size(); ++j) sup[j].assign(aux_off[fr[j] + 1] - aux_off[fr[j]], 0);
            std::vector<uint32_t> dsup(fd.size(), 0);
            std::vector<int> av = auxv, pick(fr.size(), 0);
            // joint candidates: each layer variable of one of the rule's cells pairs with that cell's digit -- a
            // combination using a ruled-out pair is no support; the pairs no combination uses are ruled out
            std::vector<std::pair<int, int>> jvar;  // (layer variable, the rule variable of its cell)
            for (int a : k.expr->aux_read)
                if (joint_ok(a) && a < (int)jx.size())
                    for (int i = 0; i < nv; ++i)
                        if (k.vars[i] == aux_cell(a)) { jvar.push_back({a, i}); break; }
            std::vector<JMask> jsup(jvar.size());
            auto vindex = [&](int a, int val) {
                const auto& vv = p.aux_values[a];
                return (int)(std::find(vv.begin(), vv.end(), val) - vv.begin());
            };
            bool any = false;
            std::vector<char> differ(fd.size() * fd.size(), 0);  // open digit pairs some combination fills differently
            uint64_t always = ~0ull;  // the value indices some open layer value of the rule takes in every combination
            std::function<void(size_t)> go = [&](size_t j) {
                if (j < fd.size()) {  // the open digits first (cells of one house: different digits)
                    const int i = fd[j];
                    for (uint32_t m = cand[k.vars[i]]; m; m &= m - 1) {
                        dg[i] = lowdigit(m);
                        bool same = true;  // identity classes (coloring): cells of one class hold one digit
                        if (!idc.empty() && idc[k.vars[i]])
                            for (size_t s = 0; s < j && same; ++s)
                                same = idc[k.vars[fd[s]]] != idc[k.vars[i]] || dg[fd[s]] == dg[i];
                        if (same && !sees_same(k, dg, i)) go(j + 1);
                    }
                    dg[i] = 0;
                    return;
                }
                const size_t q = j - fd.size();
                if (q == fr.size()) {
                    for (size_t t = 0; t < jvar.size(); ++t) {  // a ruled-out pair: no support
                        const auto [a, i] = jvar[t];
                        if (av[a] == AUX_UNSET || dg[i] <= 0) continue;
                        if (!joint_live(a, dg[i], vindex(a, av[a]))) return;
                    }
                    if ((!use_facts || facts_hold(dg, av)) && expr_holds(*k.expr, dg.data(), nullptr, nullptr, av.data())) {
                        any = true;
                        for (size_t t = 0; t < jvar.size(); ++t) {
                            const auto [a, i] = jvar[t];
                            if (av[a] != AUX_UNSET && dg[i] > 0) jsup[t].set(jbit(dg[i], vindex(a, av[a])));
                        }
                        uint64_t seen = 0;
                        for (size_t t = 0; t < fr.size(); ++t) seen |= 1ull << std::min(pick[t], 63);
                        always &= seen;
                        for (size_t t = 0; t < fr.size(); ++t) sup[t][pick[t]] = 1;
                        for (size_t t = 0; t < fd.size(); ++t) dsup[t] |= bit(dg[fd[t]]);
                        for (size_t s = 0; s < fd.size(); ++s)
                            for (size_t t = s + 1; t < fd.size(); ++t)
                                if (dg[fd[s]] != dg[fd[t]]) differ[s * fd.size() + t] = 1;
                    }
                    return;
                }
                const int a = fr[q];
                for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                    if (auxf[i]) {
                        pick[q] = i - aux_off[a];
                        av[a] = p.aux_values[a][pick[q]];
                        bool clash = false;
                        if (!counts_of[a].empty())
                            for (size_t t = 0; t < q && !clash; ++t)
                                clash = rejects(fr[t], av[fr[t]], a, av[a]);
                        if (!clash) go(j + 1);
                    }
                av[a] = AUX_UNSET;
            };
            go(0);
            if (!any) return false;  // no combination at all: a contradiction other techniques show (memo: nothing)
            for (size_t s = 0; s < fd.size(); ++s)
                for (size_t t = s + 1; t < fd.size(); ++t) {
                    const int x = k.vars[fd[s]], y = k.vars[fd[t]];
                    if (!differ[s * fd.size() + t] && !tbit(p.peers(x), y) && popc(cand[x]) > 1) r.eq.emplace_back(x, y);
                }
            std::vector<std::pair<int, int>>& dout = r.dout;
            std::vector<std::pair<int, int>>& aout = r.aout;
            for (size_t t = 0; t < fd.size(); ++t) {
                const int c = k.vars[fd[t]];
                for (uint32_t m = cand[c] & ~dsup[t]; m; m &= m - 1) dout.emplace_back(c, lowdigit(m));
            }
            for (size_t j = 0; j < fr.size(); ++j)
                for (int i = aux_off[fr[j]]; i < aux_off[fr[j] + 1]; ++i)
                    if (auxf[i] && !sup[j][i - aux_off[fr[j]]]) aout.emplace_back(fr[j], i - aux_off[fr[j]]);
            for (size_t t = 0; t < jvar.size(); ++t) {  // live pairs no combination used (not a whole digit / value)
                const auto [a, i] = jvar[t];
                const int c = k.vars[i];
                const int nvals = (int)p.aux_values[a].size();
                for (int d = 1; d <= p.D; ++d) {
                    if (vals[c] ? vals[c] != d : !(cand[c] & bit(d))) continue;
                    bool dsupported = false;  // the digit survives with some value
                    for (int vi = 0; vi < nvals; ++vi) dsupported |= jsup[t][jbit(d, vi)];
                    if (!dsupported) continue;  // the whole digit goes (dout)
                    for (int vi = 0; vi < nvals; ++vi) {
                        if (!joint_live(a, d, vi) || jsup[t][jbit(d, vi)]) continue;
                        bool vsupported = false;
                        for (int d2 = 1; d2 <= p.D; ++d2) vsupported |= jsup[t][jbit(d2, vi)];
                        if (vsupported) r.jout.emplace_back(a, d * 16 + vi);
                    }
                }
            }
            // a value the rule always puts on one of its open layer cells (one layer; the rule's cells in house G):
            // G's other cells lose it when G's count takes no second cell at it ("6 + 7 makes the 14 cage: one of
            // its cells is hot, so row 4's hot cell is in the cage")
            const int au = k.expr->aux_u, an = k.expr->aux_n;
            bool one_layer = an > 0 && !fr.empty() && fr.size() <= 6;
            for (int a : fr) one_layer &= a >= au && (a - au) / an == (fr[0] - au) / an && p.aux_values[a] == p.aux_values[fr[0]];
            if (one_layer && always && always != ~0ull) {
                std::vector<int> S;
                for (int a : fr) S.push_back((a - au) % an);
                for (int gi : p.houses) {
                    const Group& G = p.groups[gi];
                    bool holds_all = G.complete;
                    for (int c : S) holds_all &= std::find(G.cells.begin(), G.cells.end(), c) != G.cells.end();
                    if (!holds_all) continue;
                    for (uint64_t m = always; m; m &= m - 1) {
                        const int vi = __builtin_ctzll(m);
                        if (vi >= (int)p.aux_values[fr[0]].size()) break;
                        const int v = p.aux_values[fr[0]][vi];
                        for (int o : G.cells) {
                            if (std::find(S.begin(), S.end(), o) != S.end()) continue;
                            const int ao = fr[0] - S[0] + o;  // the same layer at cell o
                            // cells outside the rule are not in the memo key: the reading never looks at their
                            // state (emit drops what is already gone)
                            if (ao < 0 || ao >= NA || p.aux_values[ao] != p.aux_values[fr[0]]) continue;
                            bool rej = true;
                            for (int a : fr) rej &= rejects(a, v, ao, v);
                            if (rej && std::find(aout.begin(), aout.end(), std::make_pair(ao, vi)) == aout.end())
                                aout.emplace_back(ao, vi);
                        }
                    }
                }
            }
            return !(dout.empty() && aout.empty() && r.jout.empty() && r.eq.empty());  // (equal cells alone: kept)
            };
            if (enumerate(false)) r.code = 7401;
            else if ((!rd.empty() || !rl.empty()) && (r = AuxMemo(), enumerate(true))) r.code = 7425;
            if (!r.code) {
                r = AuxMemo();
                continue;
            }
            emit(r);
        }
    chain_rule(out);
    rule_pair(out, false);
}

// ------------------------------------------------------------ RulePair --
// rules read together (designer's fourth pass: "a sum read with a renban on the same cells is stage 3's tuple search
// over two overlapping rules"; the killer step "the cages filling a box need disjoint combinations"): (a) pairs of rule
// expressions sharing >= 2 cells, <= 8 cells together; (b) every rule lying inside one complete house (>= 2 of them):
// its cages, the house's own count rules. Every filling of the union's digits and of the values the rules read (cells
// of a complete house different, joint pairs live), each rule checked once all it reads is filled -- options on no
// filling go. Code 7432 (AuxRule's step).
void Solver::rule_pair(MoveBuf& out, bool houses) {
    if (!has_aux() || disabled[AUX_RULE] || in_branch || p.D > 9) return;
    const int NA = (int)p.aux_values.size();
    struct RP { std::vector<const NConstraint*> ks; std::vector<int> cells; bool house = false; std::vector<char> dig; };
    static thread_local std::unordered_map<uint64_t, std::vector<RP>> cache;
    auto it = cache.find(p.uid);
    if (it == cache.end()) {
        std::vector<const NConstraint*> ks;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L)
                if (k.type == NT_EXPR && k.expr && k.nv() >= 2 && k.nv() <= 9 && !expr_reads_shading(k.expr->root) &&
                    !expr_reads_regions(k.expr->root))
                    ks.push_back(&k);
        std::vector<RP> rps;
        for (size_t i = 0; i < ks.size() && rps.size() < 400; ++i)
            for (size_t j = i + 1; j < ks.size(); ++j) {
                std::vector<int> u = ks[i]->vars;
                int shared = 0;
                for (int c : ks[j]->vars)
                    if (std::find(u.begin(), u.end(), c) != u.end()) ++shared;
                    else u.push_back(c);
                if (shared < 2 || u.size() > 8) continue;
                rps.push_back({{ks[i], ks[j]}, u});
            }
        // a rule reads digits: with its values held, changing its digits changes whether it holds (sampled, fixed seed)
        const int NA0 = (int)p.aux_values.size();
        auto digits = [&](const NConstraint* k) {
            uint64_t s = 0x9E3779B97F4A7C15ull;
            auto rnd = [&](int m) { s ^= s << 13, s ^= s >> 7, s ^= s << 17; return (int)(s % (uint64_t)m); };
            std::vector<int> av(NA0, AUX_UNSET), dv(k->nv());
            for (int t = 0; t < 48; ++t) {
                for (int a : k->expr->aux_read)
                    if (a >= 0 && a < NA0 && !p.aux_values[a].empty())
                        av[a] = p.aux_values[a][rnd((int)p.aux_values[a].size())];
                int seen = -1;
                for (int u = 0; u < 8; ++u) {
                    for (int& d : dv) d = 1 + rnd(p.D);
                    const int h = expr_holds(*k->expr, dv.data(), nullptr, nullptr, av.data()) ? 1 : 0;
                    if (seen >= 0 && h != seen) return true;
                    seen = h;
                }
            }
            return false;
        };
        for (const Group& g : p.groups) {
            if (!g.complete || (int)g.cells.size() != p.D) continue;
            RP rp;
            rp.house = true;
            int nd = 0;
            for (const NConstraint* k : ks) {
                // layer rules only: plain rules have the cage readings, free unknowns AuxHouse
                if (k->expr->aux_read.empty()) continue;
                bool in = true;
                for (int a : k->expr->aux_read) in &= a >= p.aux_u;
                for (int c : k->vars) in &= std::find(g.cells.begin(), g.cells.end(), c) != g.cells.end();
                if (!in) continue;
                rp.ks.push_back(k);
                rp.dig.push_back(digits(k));
                nd += rp.dig.back();
                for (int c : k->vars)
                    if (std::find(rp.cells.begin(), rp.cells.end(), c) == rp.cells.end()) rp.cells.push_back(c);
            }
            // >= 2 rules on digits (cages): layer-only groups are JointHouses' / LayerFish's, and a search with no
            // digit rule only meets the cap
            if (nd >= 2 && rp.ks.size() <= 12) rps.push_back(std::move(rp));
        }
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(rps)).first;
    }
    if (it->second.empty()) return;
    static thread_local std::unordered_map<std::string, std::vector<std::tuple<int, int, int>>> memo;  // removals
    for (const RP& rp : it->second) {
        if (deadline_passed()) return;
        if (rp.house != houses) continue;  // pairs: AuxRule's step; houses: their own strategy beside the innies
        const long long node_cap = rp.house ? 3000 : 20000;  // (house searches read the rules abstractly at each node)
        const std::vector<int>& U = rp.cells;
        const int n = (int)U.size();
        std::vector<int> ar;  // the values the rules read, open
        for (const NConstraint* k : rp.ks)
            for (int a : k->expr->aux_read)
                if (a >= 0 && a < NA && std::find(ar.begin(), ar.end(), a) == ar.end()) ar.push_back(a);
        if (ar.size() > 24) continue;
        bool free_value = false;  // a value not tied to a cell (an unknown: one slot multiplying every filling)
        for (int a : ar) free_value |= a < p.aux_u;
        if (!rp.house && free_value) {  // such a pair: the whole product of its options, at most 20000 (as first built)
            long long combos = 1;
            for (int c : U) combos *= vals[c] ? 1 : popc(cand[c]);
            for (int a : ar) {
                int k2 = 0;
                for (int i = aux_off[a]; i < aux_off[a + 1]; ++i) k2 += auxf[i];
                combos *= std::max(1, k2);
                if (combos > 20000) break;
            }
            if (combos > 20000) continue;
        }
        std::string key;
        auto put = [&](uint64_t x) { key.append(reinterpret_cast<const char*>(&x), sizeof x); };
        put(p.uid), put((uint64_t)(uintptr_t)&rp);
        for (int c : U) put(vals[c] ? (1ull << 40 | (uint64_t)vals[c]) : cand[c]);
        if (!idc.empty())  // identity classes (a join changes no candidate)
            for (int c : U) put(3000 + (uint64_t)idc[c]);
        for (int a : ar) {
            for (int i = aux_off[a]; i < aux_off[a + 1]; ++i) key.push_back(auxf[i] ? '1' : '0');
            if (joint_ok(a))
                for (int w = 0; w < JW; ++w) put(jword(jx[a], w));
        }
        std::vector<std::tuple<int, int, int>> rem;  // (u index or -1 - aux index or -100 - aux index, digit, value)
        auto mf = memo.find(key);
        if (mf != memo.end()) {
            rem = mf->second;
        } else {
            // slots: the free values first, then per cell its digit and the values tied to it
            std::vector<int> acell(ar.size(), -1);  // ar[q] -> union index of its cell, or -1
            for (size_t q = 0; q < ar.size(); ++q)
                if (joint_ok(ar[q])) {
                    const size_t ui = std::find(U.begin(), U.end(), aux_cell(ar[q])) - U.begin();
                    if (ui < U.size()) acell[q] = (int)ui;
                }
            std::vector<int> slot;  // >= 0: union index (digit); < 0: -1 - q (value)
            for (size_t q = 0; q < ar.size(); ++q)
                if (acell[q] < 0) slot.push_back(-1 - (int)q);
            for (int x = 0; x < n; ++x) {
                slot.push_back(x);
                for (size_t q = 0; q < ar.size(); ++q)
                    if (acell[q] == x) slot.push_back(-1 - (int)q);
            }
            std::vector<int> at_u(n), at_a(ar.size());
            for (int s = 0; s < (int)slot.size(); ++s) (slot[s] >= 0 ? at_u[slot[s]] : at_a[-1 - slot[s]]) = s;
            // each rule: checked after the slot filling the last thing it reads; read abstractly (the open cells at
            // their candidates) after each earlier slot it reads
            std::vector<std::vector<int>> check(slot.size()), partial(slot.size());
            std::vector<std::vector<int>> pos(rp.ks.size());
            for (size_t r = 0; r < rp.ks.size(); ++r) {
                const NConstraint* k = rp.ks[r];
                int last = 0;
                for (int i = 0; i < k->nv(); ++i) {
                    const int x = (int)(std::find(U.begin(), U.end(), k->vars[i]) - U.begin());
                    pos[r].push_back(x);
                    last = std::max(last, at_u[x]);
                }
                std::vector<int> reads;  // (a house rule on values only: its digits change nothing)
                if (rp.dig.empty() || rp.dig[r])
                    for (int x : pos[r]) reads.push_back(at_u[x]);
                for (int a : k->expr->aux_read)
                    for (size_t q = 0; q < ar.size(); ++q)
                        if (ar[q] == a) last = std::max(last, at_a[q]), reads.push_back(at_a[q]);
                check[last].push_back((int)r);
                for (int s : reads)
                    if (s < last && (partial[s].empty() || partial[s].back() != (int)r)) partial[s].push_back((int)r);
            }
            std::vector<std::vector<int>> adom(NA);  // the values open now; a filled value slot holds one
            for (int a = 0; a < NA; ++a)
                for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                    if (auxf[i]) adom[a].push_back(p.aux_values[a][i - aux_off[a]]);
            std::vector<uint32_t> dmk;
            // a partial reading per (puzzle, rule, what it reads): a pure function of those, shared by every search
            static thread_local std::unordered_map<std::string, char> pmemo;  // (exact keys: a collision would prune)
            if (pmemo.size() > 2000000) pmemo.clear();
            std::vector<int> dg(n, 0), av(NA, AUX_UNSET);
            for (int a = 0; a < NA; ++a) {
                int k2 = 0, last = 0;
                for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                    if (auxf[i]) ++k2, last = p.aux_values[a][i - aux_off[a]];
                if (k2 == 1) av[a] = last;
            }
            std::vector<std::vector<char>> same(n, std::vector<char>(n, 0));  // cells of one complete house
            for (int x = 0; x < n; ++x)
                for (int y = x + 1; y < n; ++y)
                    for (int g : p.groups_of[U[x]])
                        if (p.groups[g].complete &&
                            std::find(p.groups[g].cells.begin(), p.groups[g].cells.end(), U[y]) != p.groups[g].cells.end())
                            same[x][y] = same[y][x] = 1;
            std::vector<uint32_t> dsup(n, 0);
            std::vector<std::vector<char>> asup(ar.size());
            for (size_t q = 0; q < ar.size(); ++q) asup[q].assign(aux_off[ar[q] + 1] - aux_off[ar[q]], 0);
            std::map<std::pair<int, int>, uint64_t> jsup;  // (aux, digit) -> value indices used together
            std::vector<int> pick(ar.size(), -1), dv;
            long long nodes = 0;
            bool any = false, capped = false;
            auto holds = [&](int r) {
                const NConstraint* k = rp.ks[r];
                dv.resize(k->nv());
                for (int i = 0; i < k->nv(); ++i) dv[i] = dg[pos[r][i]];
                return expr_holds(*k->expr, dv.data(), nullptr, nullptr, av.data());
            };
            std::function<void(int)> go = [&](int s) {
                if (capped) return;
                if (++nodes > node_cap) { capped = true; return; }
                if (s == (int)slot.size()) {
                    any = true;
                    for (int x = 0; x < n; ++x) dsup[x] |= bit(dg[x]);
                    for (size_t q = 0; q < ar.size(); ++q) {
                        asup[q][pick[q]] = 1;
                        if (acell[q] >= 0) jsup[{ar[q], dg[acell[q]]}] |= 1ull << pick[q];
                    }
                    return;
                }
                auto next = [&]() {
                    for (int r : check[s])
                        if (!holds(r)) return;
                    for (int r : partial[s]) {  // (house groups: pairs complete within a few slots)
                        if (!rp.house) break;
                        const NConstraint* k = rp.ks[r];
                        dmk.resize(k->nv());
                        for (int i = 0; i < k->nv(); ++i) {
                            const int x = pos[r][i];
                            dmk[i] = at_u[x] <= s ? bit(dg[x]) : vals[U[x]] ? bit(vals[U[x]]) : cand[U[x]];
                        }
                        std::string h;
                        auto put = [&](uint64_t x) { h.append(reinterpret_cast<const char*>(&x), sizeof x); };
                        put(p.uid), put((uint64_t)(uintptr_t)k);
                        for (uint32_t m : dmk) h.append(reinterpret_cast<const char*>(&m), sizeof m);
                        for (int a : k->expr->aux_read)  // a value slot filled, or the open values (fixed in a search)
                            if (a >= 0 && a < (int)adom.size()) {
                                put(adom[a].size());
                                for (int w : adom[a]) put((uint64_t)(long long)w);
                            }
                        auto pf = pmemo.find(h);
                        const char ok = pf != pmemo.end() ? pf->second : (pmemo[h] = expr_may_hold(*k->expr, dmk.data(), adom));
                        if (!ok) return;
                    }
                    go(s + 1);
                };
                if (slot[s] >= 0) {
                    const int j = slot[s], c = U[j];
                    for (uint32_t m = vals[c] ? bit(vals[c]) : cand[c]; m; m &= m - 1) {
                        const int d = lowdigit(m);
                        bool ok = true;
                        for (int x = 0; x < n && ok; ++x) ok = !(same[x][j] && at_u[x] < s && dg[x] == d);
                        if (!idc.empty() && idc[c])  // identity classes: cells of one class hold one digit
                            for (int x = 0; x < n && ok; ++x)
                                ok = !(at_u[x] < s && idc[U[x]] == idc[c] && dg[x] != d);
                        if (ok) dg[j] = d, next();
                    }
                    return;
                }
                const int q = -1 - slot[s], a = ar[q], keep = av[a];
                const std::vector<int> keepd = adom[a];
                for (int i = aux_off[a]; i < aux_off[a + 1]; ++i) {
                    if (!auxf[i]) continue;
                    const int vi = i - aux_off[a];
                    if (acell[q] >= 0 && !joint_live(a, dg[acell[q]], vi)) continue;
                    av[a] = p.aux_values[a][vi], pick[q] = vi;
                    adom[a].assign(1, av[a]);
                    next();
                }
                av[a] = keep, adom[a] = keepd;
            };
            go(0);
            if (any && !capped) {
                for (int x = 0; x < n; ++x)
                    if (!vals[U[x]])
                        for (uint32_t m = cand[U[x]] & ~dsup[x]; m; m &= m - 1) rem.emplace_back(x, lowdigit(m), -1);
                for (size_t q = 0; q < ar.size(); ++q)
                    for (int i = aux_off[ar[q]]; i < aux_off[ar[q] + 1]; ++i)
                        if (auxf[i] && !asup[q][i - aux_off[ar[q]]]) rem.emplace_back(-1 - (int)q, 0, i - aux_off[ar[q]]);
                for (size_t q = 0; q < ar.size(); ++q) {  // live pairs of a supported digit and value never used together
                    if (acell[q] < 0) continue;
                    const int a = ar[q];
                    for (uint32_t m = dsup[acell[q]]; m; m &= m - 1) {
                        const int d = lowdigit(m);
                        const uint64_t js = jsup[{a, d}];
                        for (int vi = 0; vi < (int)asup[q].size(); ++vi)
                            if (asup[q][vi] && !((js >> vi) & 1) && joint_live(a, d, vi)) rem.emplace_back(-100 - (int)q, d, vi);
                    }
                }
            }
            if (memo.size() > 100000) memo.clear();
            if (!deadline_passed()) memo[key] = rem;
        }
        if (rem.empty()) continue;
        std::vector<std::pair<int, int>> dout, aout;
        std::vector<std::tuple<int, int, int>> jout;
        for (auto& [x, d, vi] : rem) {
            if (x >= 0) dout.emplace_back(U[x], d);
            else if (x > -100) aout.emplace_back(ar[-1 - x], vi);
            else jout.emplace_back(ar[-100 - x], d, vi);
        }
        Move& m = new_move(out, rp.house ? HOUSE_CAGES : AUX_RULE, 1.0, (int)(dout.size() + aout.size() + jout.size()));
        for (auto& e : dout) add_el(out, m, e.first, e.second);
        for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
        for (auto& [a, d, vi] : jout) add_aeff(out, m, AE_JOINT, a, d * 16 + vi);
        set_pattern(out, m, U);
        m.nk = NM_NARY;
        m.code = 7432;
    }
}

// ------------------------------------------------------------ RuleCase --
// designer's fifth pass (D5): "this value has no support in the rule once the houses are checked". A candidate d of a
// rule's cell x: the rule's options with x = d (its cells' digits, at most 8), each followed by HOUSE SINGLES only
// (no other rule inside, no nesting); when every option breaks a house (an empty cell, a house without a place for a
// digit) within the caps -- 4 singles per option, 12 in all, 6 outside cells per option -- d goes. Priced as the
// option list read (a cage's combination positions: Very Hard, the Hidden Triple price). Code 7434.
void Solver::rule_case(MoveBuf& out) {
    if (disabled[RULE_CASE] || in_branch || p.D > 9) return;
    constexpr int MAX_OPTS = 8;
    static int caps[3] = {4, 12, 6};  // singles per option, in all, outside cells per option (designer D5)
    static const bool caps_read = [] {  // PENCILMARK_ROC_CAPS=per,all,cells (experiment: the warning number)
        if (const char* e = getenv("PENCILMARK_ROC_CAPS")) sscanf(e, "%d,%d,%d", &caps[0], &caps[1], &caps[2]);
        return true;
    }();
    (void)caps_read;
    const int STEPS_PER = caps[0], STEPS_ALL = caps[1], CELLS_PER = caps[2];
    const int NA = (int)p.aux_values.size();
    bool capped_last = false;  // the last follow() stopped at a cap (not a standing option)
    static thread_local long long n_steps = 0, n_near = 0;  // the warning number: candidates that missed only by a cap
    std::vector<int> hv;  // house singles on a copy: vals / cand; returns true on a contradiction within `cap` singles
    std::vector<uint32_t> hc;
    auto follow = [&](const std::vector<std::pair<int, int>>& put, int cap, int& steps, int& cells) {
        hv.assign(vals.begin(), vals.end());
        hc.assign(cand.begin(), cand.end());
        steps = 0, cells = 0;
        std::vector<std::pair<int, int>> todo(put.begin(), put.end());
        auto place = [&](int c, int d) -> bool {  // false: a contradiction
            if (hv[c]) return hv[c] == d;
            if (!(hc[c] & bit(d))) return false;
            hv[c] = d, hc[c] = bit(d);
            for (int g : p.groups_of[c]) {
                if (!p.groups[g].complete) continue;
                for (int y : p.groups[g].cells)
                    if (y != c && !hv[y]) {
                        hc[y] &= ~bit(d);
                        if (!hc[y]) return false;
                    }
            }
            return true;
        };
        for (auto [c, d] : todo)
            if (!place(c, d)) return true;
        capped_last = false;
        while (true) {
            if (steps >= cap) { capped_last = true; return false; }
            int sc = -1, sd = 0;
            for (int c = 0; c < p.N && sc < 0; ++c)
                if (!hv[c] && popc(hc[c]) == 1) sc = c, sd = lowdigit(hc[c]);
            if (sc < 0)
                for (int hi : p.houses) {
                    const Group& G = p.groups[hi];
                    if (!G.complete) continue;
                    uint32_t have = 0;
                    for (int y : G.cells) have |= hv[y] ? bit(hv[y]) : 0;
                    for (uint32_t m = p.full & ~have; m && sc < 0; m &= m - 1) {
                        const int d = lowdigit(m);
                        int n = 0, at = -1;
                        for (int y : G.cells)
                            if (!hv[y] && (hc[y] & bit(d))) ++n, at = y;
                        if (n == 0) return true;  // the house has no place for d
                        if (n == 1) sc = at, sd = d;
                    }
                    if (sc >= 0) break;
                }
            if (sc < 0) return false;  // no single: the option stands
            ++steps, ++cells;
            if (cells > CELLS_PER) { capped_last = true; return false; }
            if (!place(sc, sd)) return true;
        }
    };
    auto process = [&](const NConstraint& k, bool cage) {
        std::vector<int> ar;  // the values it reads (enumerated; options are digit tuples)
        if (!cage && k.expr)
            for (int a : k.expr->aux_read)
                if (a >= 0 && a < NA) ar.push_back(a);
        if (ar.size() > 8) return;
        const int nv = k.nv();
        for (int xi = 0; xi < nv; ++xi) {
            const int x = k.vars[xi];
            if (vals[x]) continue;
            for (uint32_t mm = cand[x]; mm; mm &= mm - 1) {
                const int d = lowdigit(mm);
                // the options: digit tuples of the rule's cells with x = d (some values of what it reads hold it)
                std::set<std::vector<int>> opts;
                std::vector<int> dg(nv, 0), av(NA, AUX_UNSET);
                long long work = 0;
                bool over = false;
                std::function<void(int)> vals_go;
                std::function<void(int)> go = [&](int i) {
                    if (over) return;
                    if (++work > 20000 || (int)opts.size() > MAX_OPTS) { over = true; return; }
                    if (i == nv) { vals_go(0); return; }
                    const int c = k.vars[i];
                    uint32_t m = i == xi ? bit(d) : vals[c] ? bit(vals[c]) : cand[c];
                    for (; m; m &= m - 1) {
                        dg[i] = lowdigit(m);
                        if (!sees_same(k, dg, i)) go(i + 1);
                    }
                    dg[i] = 0;
                };
                vals_go = [&](size_t q) {
                    if (over) return;
                    if (q == ar.size()) {
                        if (cage) {
                            int s = 0;
                            uint32_t seen = 0;
                            bool ok = true;
                            for (int v : dg) ok &= !(k.distinct && (seen & bit(v))), seen |= bit(v), s += v;
                            if (ok && s == k.total) opts.insert(dg);
                        } else if (expr_holds(*k.expr, dg.data(), nullptr, nullptr, av.data())) {
                            opts.insert(dg);
                        }
                        return;
                    }
                    const int a = ar[q];
                    for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                        if (auxf[i]) {
                            const int vi = i - aux_off[a];
                            if (joint_ok(a)) {
                                const int ci = (int)(std::find(k.vars.begin(), k.vars.end(), aux_cell(a)) - k.vars.begin());
                                if (ci < nv && !joint_live(a, dg[ci], vi)) continue;
                            }
                            av[a] = p.aux_values[a][vi];
                            vals_go(q + 1);
                            if (!opts.empty() && opts.count(dg)) break;  // this tuple stands: enough
                        }
                    av[a] = AUX_UNSET;
                };
                go(0);
                if (over || opts.empty()) continue;  // too many options, or none (the rule reading's job)
                int total = 0;
                bool all_break = true, near = false;
                for (const auto& o : opts) {
                    std::vector<std::pair<int, int>> put;
                    for (int i = 0; i < nv; ++i)
                        if (!vals[k.vars[i]]) put.emplace_back(k.vars[i], o[i]);
                    int steps = 0, cells = 0;
                    const bool broke = follow(put, std::min(STEPS_PER, STEPS_ALL - total), steps, cells);
                    total += steps;
                    if (!broke && capped_last) near = true;
                    if ((!broke && !capped_last) || total > STEPS_ALL) { all_break = false; break; }
                }
                if (all_break && near) {  // every option broke or met a cap: a near miss (the warning number)
                    ++n_near;
                    if (getenv("PENCILMARK_ROC_STATS")) fprintf(stderr, "ROC near %lld steps %lld\n", n_near, n_steps);
                    continue;
                }
                if (!all_break) continue;
                ++n_steps;
                if (getenv("PENCILMARK_ROC_STATS")) fprintf(stderr, "ROC step %lld near %lld\n", n_steps, n_near);
                Move& m = new_move(out, RULE_CASE, 1.0, (int)opts.size());
                add_el(out, m, x, d);
                set_pattern(out, m, k.vars);
                meta8(m, nv, 1, (int)opts.size(), total, 1, 0, 0, 1, 1.0);
                m.nk = NM_NARY;
                m.na = k.index;
                m.code = 7434;
            }
        }
    };
    for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
        for (const NConstraint& k : *L) {
            if (deadline_passed()) return;
            if (k.type != NT_EXPR || !k.expr || k.nv() < 2 || k.nv() > 6) continue;
            if (expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;
            process(k, false);
        }
    if (getenv("PENCILMARK_ROC_CAGES"))  // killer cages (houses with a total): the calibration case (designer D5)
        for (int gi = 0; gi < (int)p.groups.size(); ++gi) {
            const Group& g = p.groups[gi];
            if (!g.has_total || g.cells.size() < 2 || g.cells.size() > 6 || deadline_passed()) continue;
            NConstraint tmp;
            tmp.type = NT_SUM, tmp.vars = g.cells, tmp.total = g.total, tmp.distinct = true, tmp.group = gi;
            process(tmp, true);
        }
}

// ----------------------------------------------------------- ChainRule --
// a path of two-cell rules (a slow thermometer on values, a line of dots) read as one: an exact DP along the path whose
// state is the last three cells' (digit, layer value) options. A step must satisfy the link's rule, different digits
// for cells sharing a complete house, and no exactly-one layer house (one doubler per house, each digit doubled once)
// with both cells' literals true. Constraints between cells further apart are dropped (a relaxation: what it removes
// is still sound). Options on no full path go. Code 7428 (AuxRule's step).
void Solver::chain_rule(MoveBuf& out) {
    if (!has_aux() || disabled[AUX_RULE] || in_branch || p.D > 9) return;
    const int NA = (int)p.aux_values.size();
    struct Chain { std::vector<int> cells; std::vector<const NConstraint*> links; std::vector<char> flip; int layer; };
    static thread_local std::unordered_map<uint64_t, std::vector<Chain>> cache;
    auto it = cache.find(p.uid);
    if (it == cache.end()) {
        // two-cell rules over one layer (or none): the graph cell -> links
        std::map<int, std::vector<std::pair<const NConstraint*, int>>> adj;  // cell -> (rule, other cell)
        std::map<const NConstraint*, int> lay;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr || k.nv() != 2 || k.vars[0] == k.vars[1]) continue;
                if (expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;
                int layer = -1;
                bool ok = true;
                for (int a : k.expr->aux_read) {
                    if (a < p.aux_u || a >= NA) { ok = false; break; }  // an unknown: not a pure link
                    const int l = (a - p.aux_u) / p.N, c = (a - p.aux_u) % p.N;
                    if ((layer >= 0 && l != layer) || (c != k.vars[0] && c != k.vars[1])) { ok = false; break; }
                    layer = l;
                }
                if (!ok) continue;
                lay[&k] = layer;
                adj[k.vars[0]].push_back({&k, k.vars[1]});
                adj[k.vars[1]].push_back({&k, k.vars[0]});
            }
        std::vector<Chain> chains;
        std::set<int> seen;
        for (auto& [c0, nb] : adj) {
            if (nb.size() != 1 || seen.count(c0)) continue;  // a path starts at a cell with one link
            Chain ch;
            ch.layer = -1;
            int prev = -1, cur = c0;
            bool ok = true;
            while (true) {
                seen.insert(cur);
                ch.cells.push_back(cur);
                const auto& e = adj[cur];
                if (e.size() > 2) { ok = false; break; }  // a branch: not a path
                const std::pair<const NConstraint*, int>* nx = nullptr;
                for (const auto& x : e)
                    if (x.second != prev) nx = &x;
                if (!nx) break;
                if (seen.count(nx->second)) { ok = false; break; }
                const int l = lay[nx->first];
                if (l >= 0 && ch.layer >= 0 && l != ch.layer) { ok = false; break; }
                if (l >= 0) ch.layer = l;
                ch.links.push_back(nx->first);
                ch.flip.push_back(nx->first->vars[0] != cur);
                prev = cur, cur = nx->second;
            }
            if (ok && ch.cells.size() >= 3 && ch.cells.size() <= 81) chains.push_back(std::move(ch));
        }
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(chains)).first;
    }
    if (it->second.empty() || jx.size() != p.aux_values.size()) return;
    const std::vector<JHouse>& JH = jhouses_of(p);
    static thread_local std::unordered_map<std::string, std::vector<std::tuple<int, int, int>>> memo;  // -> removals
    for (const Chain& ch : it->second) {
        if (deadline_passed()) return;
        const int n = (int)ch.cells.size();
        // options per cell: (digit, value index), value index -1 without a layer
        std::vector<std::vector<std::pair<int, int>>> opt(n);
        std::vector<int> avar(n, -1);
        std::string key;
        auto put = [&](uint64_t x) { key.append(reinterpret_cast<const char*>(&x), sizeof x); };
        put(p.uid), put((uint64_t)(uintptr_t)&ch);
        for (int i = 0; i < n; ++i) {
            const int c = ch.cells[i];
            if (ch.layer >= 0) avar[i] = p.aux_u + ch.layer * p.N + c;
            for (int d = 1; d <= p.D; ++d) {
                if (vals[c] ? vals[c] != d : !(cand[c] & bit(d))) continue;
                if (avar[i] < 0) { opt[i].push_back({d, -1}); continue; }
                const int a = avar[i];
                for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi)
                    if (auxf[aux_off[a] + vi] && (!joint_ok(a) || joint_live(a, d, vi))) opt[i].push_back({d, vi});
            }
            if (opt[i].empty() || opt[i].size() > 18) { key.clear(); break; }
            put((uint64_t)opt[i].size());
            for (auto [d, vi] : opt[i]) put((uint64_t)(d * 64 + vi + 1));
        }
        if (key.empty()) continue;
        std::vector<std::tuple<int, int, int>> rem;  // (cell index, digit, value index) unsupported
        auto mit = memo.find(key);
        if (mit != memo.end()) {
            rem = mit->second;
        } else {
            // conflicts between cells i < j (non-link): a shared complete house, an exactly-one layer house
            auto share_house = [&](int a, int b) {
                for (int g : p.groups_of[a])
                    if (p.groups[g].complete && std::find(p.groups[g].cells.begin(), p.groups[g].cells.end(), b) !=
                                                    p.groups[g].cells.end())
                        return true;
                return false;
            };
            std::vector<std::vector<const JHouse*>> jh_pair(n * n);  // layer houses holding both cells (i, j)
            if (ch.layer >= 0)
                for (const JHouse& h : JH) {
                    if (h.pmask.any() || h.layer != ch.layer) continue;
                    std::vector<int> in;
                    for (int i = 0; i < n; ++i)
                        if (std::binary_search(h.cells.begin(), h.cells.end(), ch.cells[i])) in.push_back(i);
                    for (size_t x = 0; x < in.size(); ++x)
                        for (size_t y = x + 1; y < in.size(); ++y)
                            if (in[y] - in[x] <= 2) jh_pair[in[x] * n + in[y]].push_back(&h);
                }
            std::vector<char> hp(n * n, 0);
            for (int i = 0; i < n; ++i)
                for (int j = i + 1; j <= std::min(n - 1, i + 2); ++j) hp[i * n + j] = share_house(ch.cells[i], ch.cells[j]);
            auto compatible = [&](int i, int oi, int j, int oj) {  // i < j, within the window
                const auto [di, vi] = opt[i][oi];
                const auto [dj, vj] = opt[j][oj];
                if (hp[i * n + j] && di == dj) return false;
                for (const JHouse* h : jh_pair[i * n + j]) {
                    const bool li = (!h->digit || di == h->digit) && vi >= 0 && ((h->vmask >> vi) & 1);
                    const bool lj = (!h->digit || dj == h->digit) && vj >= 0 && ((h->vmask >> vj) & 1);
                    if (li && lj) return false;
                }
                return true;
            };
            // the links: allowed option pairs
            std::vector<std::vector<char>> link(n - 1);
            std::vector<int> av(NA, AUX_UNSET);
            for (int i = 0; i + 1 < n; ++i) {
                const NConstraint& k = *ch.links[i];
                link[i].assign(opt[i].size() * opt[i + 1].size(), 0);
                for (size_t a = 0; a < opt[i].size(); ++a)
                    for (size_t b = 0; b < opt[i + 1].size(); ++b) {
                        int dg[2];
                        const int ia = ch.flip[i] ? 1 : 0;
                        dg[ia] = opt[i][a].first, dg[1 - ia] = opt[i + 1][b].first;
                        if (avar[i] >= 0) {
                            av[avar[i]] = p.aux_values[avar[i]][opt[i][a].second];
                            av[avar[i + 1]] = p.aux_values[avar[i + 1]][opt[i + 1][b].second];
                        }
                        link[i][a * opt[i + 1].size() + b] =
                            compatible(i, (int)a, i + 1, (int)b) && expr_holds(*k.expr, dg, nullptr, nullptr, av.data());
                        if (avar[i] >= 0) av[avar[i]] = av[avar[i + 1]] = AUX_UNSET;
                    }
            }
            // the whole chain inside one complete house (an X chain in a box): every cell differs -- an exact DP over
            // (last option, digits used, the house's layer literal used) instead of the window (Off by I: "digits two
            // apart differ by exactly 2 when the chain cannot repeat")
            bool onehouse = false;
            for (int gi : p.groups_of[ch.cells[0]]) {
                const Group& G = p.groups[gi];
                if (!G.complete || (int)G.cells.size() != p.D) continue;
                bool all = true;
                for (int c : ch.cells) all &= std::find(G.cells.begin(), G.cells.end(), c) != G.cells.end();
                onehouse |= all;
            }
            if (onehouse && n <= p.D) {
                uint32_t uv = 0;  // a layer-only exactly-one house holding the chain: its literal once
                if (ch.layer >= 0)
                    for (const JHouse& h : JH) {
                        if (h.pmask.any() || h.digit || h.layer != ch.layer) continue;
                        bool all = true;
                        for (int c : ch.cells) all &= std::binary_search(h.cells.begin(), h.cells.end(), c);
                        if (all) uv |= h.vmask;
                    }
                auto lit = [&](int i, int o) { return opt[i][o].second >= 0 && ((uv >> opt[i][o].second) & 1) ? 1 : 0; };
                auto st = [&](int y, int m, int u) { return ((size_t)y * 512 + m) * 2 + u; };
                std::vector<std::vector<char>> gd(n), rc(n);
                for (int i = 0; i < n; ++i) gd[i].assign(opt[i].size() * 1024, 0), rc[i].assign(opt[i].size() * 1024, 0);
                for (size_t y = 0; y < opt[n - 1].size(); ++y)
                    for (int m = 0; m < 512; ++m)
                        for (int u = 0; u < 2; ++u) gd[n - 1][st((int)y, m, u)] = 1;
                for (int i = n - 2; i >= 0; --i)
                    for (size_t y = 0; y < opt[i].size(); ++y)
                        for (int m = 0; m < 512; ++m) {
                            if (!(m >> (opt[i][y].first - 1) & 1)) continue;  // m holds this cell's digit
                            for (int u = 0; u < 2; ++u) {
                                char g = 0;
                                for (size_t z = 0; z < opt[i + 1].size() && !g; ++z) {
                                    const int dz = opt[i + 1][z].first, lz = lit(i + 1, (int)z);
                                    if (!link[i][y * opt[i + 1].size() + z] || (m >> (dz - 1) & 1) || (lz && u)) continue;
                                    g = gd[i + 1][st((int)z, m | 1 << (dz - 1), u | lz)];
                                }
                                gd[i][st((int)y, m, u)] = g;
                            }
                        }
                std::vector<std::vector<char>> sp(n);
                for (int i = 0; i < n; ++i) sp[i].assign(opt[i].size(), 0);
                for (size_t y = 0; y < opt[0].size(); ++y) {
                    const size_t s0 = st((int)y, 1 << (opt[0][y].first - 1), lit(0, (int)y));
                    if (gd[0][s0]) rc[0][s0] = 1, sp[0][y] = 1;
                }
                for (int i = 0; i + 1 < n; ++i)
                    for (size_t y = 0; y < opt[i].size(); ++y)
                        for (int m = 0; m < 512; ++m)
                            for (int u = 0; u < 2; ++u) {
                                if (!rc[i][st((int)y, m, u)]) continue;
                                for (size_t z = 0; z < opt[i + 1].size(); ++z) {
                                    const int dz = opt[i + 1][z].first, lz = lit(i + 1, (int)z);
                                    if (!link[i][y * opt[i + 1].size() + z] || (m >> (dz - 1) & 1) || (lz && u)) continue;
                                    const size_t s2 = st((int)z, m | 1 << (dz - 1), u | lz);
                                    if (!gd[i + 1][s2]) continue;
                                    rc[i + 1][s2] = 1, sp[i + 1][z] = 1;
                                }
                            }
                bool any0 = false;
                for (size_t y = 0; y < opt[0].size(); ++y) any0 |= sp[0][y];
                if (any0)
                    for (int i = 0; i < n; ++i)
                        for (size_t o = 0; o < opt[i].size(); ++o)
                            if (!sp[i][o]) rem.emplace_back(i, opt[i][o].first, opt[i][o].second);
                if (memo.size() > 100000) memo.clear();
                if (!deadline_passed()) memo[key] = rem;
                goto chain_emit;
            }
            {
            // state at i: (o[i-1], o[i]) -- with the window check o[i-1], o[i] against o[i+1] (i+1 - (i-1) = 2)
            constexpr int S = 19;  // options per cell <= 18, + "none" for the start
            auto code = [&](int x, int y) { return x * S + y; };
            std::vector<std::vector<char>> good(n, std::vector<char>(S * S, 0)), reach(n, std::vector<char>(S * S, 0));
            for (int x = 0; x < S; ++x)
                for (size_t y = 0; y < opt[n - 1].size(); ++y) good[n - 1][code(x, (int)y)] = 1;
            for (int i = n - 2; i >= 0; --i)
                for (int x = 0; x < (i == 0 ? 1 : (int)opt[i - 1].size()); ++x)
                    for (size_t y = 0; y < opt[i].size(); ++y) {
                        const int xs = i == 0 ? S - 1 : x;
                        bool g = false;
                        for (size_t z = 0; z < opt[i + 1].size() && !g; ++z) {
                            if (!link[i][y * opt[i + 1].size() + z]) continue;
                            if (i >= 1 && !compatible(i - 1, x, i + 1, (int)z)) continue;
                            g = good[i + 1][code((int)y, (int)z)];
                        }
                        good[i][code(xs, (int)y)] = g;
                    }
            std::vector<std::vector<char>> sup(n);
            for (int i = 0; i < n; ++i) sup[i].assign(opt[i].size(), 0);
            for (size_t y = 0; y < opt[0].size(); ++y)
                if (good[0][code(S - 1, (int)y)]) reach[0][code(S - 1, (int)y)] = 1, sup[0][y] = 1;
            for (int i = 0; i + 1 < n; ++i)
                for (int xs = 0; xs < S; ++xs)
                    for (size_t y = 0; y < opt[i].size(); ++y) {
                        if (!reach[i][code(xs, (int)y)]) continue;
                        for (size_t z = 0; z < opt[i + 1].size(); ++z) {
                            if (!link[i][y * opt[i + 1].size() + z]) continue;
                            if (xs != S - 1 && !compatible(i - 1, xs, i + 1, (int)z)) continue;
                            if (!good[i + 1][code((int)y, (int)z)]) continue;
                            reach[i + 1][code((int)y, (int)z)] = 1;
                            sup[i + 1][z] = 1;
                        }
                    }
            bool any = false;
            for (size_t y = 0; y < opt[0].size(); ++y) any |= sup[0][y];
            if (any)  // (no full path: a contradiction others show)
                for (int i = 0; i < n; ++i)
                    for (size_t o = 0; o < opt[i].size(); ++o)
                        if (!sup[i][o]) rem.emplace_back(i, opt[i][o].first, opt[i][o].second);
            if (memo.size() > 100000) memo.clear();
            if (!deadline_passed()) memo[key] = rem;
            }
        }
    chain_emit:
        if (rem.empty()) continue;
        // digits with no supported value, values with no supported digit, else joint pairs
        std::vector<std::pair<int, int>> dout, aout;
        std::vector<std::tuple<int, int, int>> jout;
        for (int i = 0; i < n; ++i) {
            const int c = ch.cells[i];
            uint32_t dsup = 0;
            uint64_t vsup = 0;
            for (auto [d, vi] : opt[i]) {
                bool gone = false;
                for (auto& [ri, rd, rv] : rem) gone |= ri == i && rd == d && rv == vi;
                if (!gone) dsup |= bit(d), vsup |= vi >= 0 ? 1ull << vi : 0;
            }
            for (auto [d, vi] : opt[i]) {
                bool gone = false;
                for (auto& [ri, rd, rv] : rem) gone |= ri == i && rd == d && rv == vi;
                if (!gone) continue;
                if (!(dsup & bit(d))) {
                    if (!vals[c] && std::find(dout.begin(), dout.end(), std::make_pair(c, d)) == dout.end()) dout.emplace_back(c, d);
                } else if (vi >= 0 && !((vsup >> vi) & 1)) {
                    if (std::find(aout.begin(), aout.end(), std::make_pair(avar[i], vi)) == aout.end()) aout.emplace_back(avar[i], vi);
                } else if (vi >= 0 && joint_ok(avar[i])) {
                    jout.emplace_back(avar[i], d, vi);
                }
            }
        }
        if (dout.empty() && aout.empty() && jout.empty()) continue;
        Move& m = new_move(out, AUX_RULE, 1.0, (int)(dout.size() + aout.size() + jout.size()));
        for (auto& e : dout) add_el(out, m, e.first, e.second);
        for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
        for (auto& [a, d, vi] : jout) add_aeff(out, m, AE_JOINT, a, d * 16 + vi);
        set_pattern(out, m, ch.cells);
        m.nk = NM_NARY;
        m.code = 7428;
    }
}

// ------------------------------------------------------------ LayerCount --
// a rule "count(P(x) for x in house) == k" over a layer or unknowns ("one doubler per row": count(dbl(x) == 2 for x in
// H) == 1), read like a house: P read abstractly per cell (absint.cpp expr_count_moves); k cells surely P -> the other
// cells lose what would make P true; only k cells can be P -> they lose what would make it false. Code 7406.
void Solver::layer_count(MoveBuf& out) {
    if (!has_aux() || disabled[LAYER_COUNT]) return;
    const int NA = (int)p.aux_values.size();
    std::vector<std::vector<int>> aux_dom(NA);
    for (int a = 0; a < NA; ++a)
        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
            if (auxf[i]) aux_dom[a].push_back(p.aux_values[a][i - aux_off[a]]);
    for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
        for (const NConstraint& k : *L) {
            if (k.type != NT_EXPR || !k.expr || k.expr->aux_read.empty()) continue;
            if (expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;
            // inside a case branch a grid-wide count ("each digit cold once") is JointHouses' to read: re-analysed at
            // every branch step it was 70% of a layer puzzle's grade (layer values are not branch state anyway)
            if (in_branch && k.nv() > p.D) continue;
            std::vector<uint32_t> dom(k.nv());
            for (int i = 0; i < k.nv(); ++i) dom[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
            CountMoves cm = expr_count_moves(*k.expr, p.D, dom, aux_dom);
            std::vector<std::pair<int, int>> dout, aout;
            for (auto [v, d] : cm.digits)
                if (!vals[k.vars[v]] && (cand[k.vars[v]] & bit(d))) dout.emplace_back(k.vars[v], d);
            for (auto [a, w] : cm.aux) {
                const auto& av = p.aux_values[a];
                const auto it = std::find(av.begin(), av.end(), w);
                if (it != av.end() && auxf[aux_off[a] + (it - av.begin())]) aout.emplace_back(a, (int)(it - av.begin()));
            }
            if (dout.empty() && aout.empty()) continue;
            Move& m = new_move(out, LAYER_COUNT, 1.0, (int)(dout.size() + aout.size()));
            for (auto& e : dout) add_el(out, m, e.first, e.second);
            for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
            set_pattern(out, m, k.vars);
            m.nk = NM_NARY;
            m.na = k.index;
            m.nb = k.group;
            m.code = 7406;
        }
    joint_houses(out);
    modifier_equiv(out);
    mod_cage(out);
    equal_products(out);
    equal_sums(out);
    budget_fish(out);
}

// --------------------------------------------------------- UnknownTrial --
// a case split on an unknown's few values ("if the total were 29, the segment would be 5-7-8-9, and column 4 clashes"):
// assume the value and follow it as case analysis follows a digit (fc_propagate: the light tiers, a step cap); a
// contradiction rules the value out. Unknowns (not layer cells) with 2-6 open values. Code 7419.
void Solver::unknown_trial(MoveBuf& out) {
    const int NA = (int)p.aux_values.size();
    if (p.aux_u <= 0) return;
    std::vector<const NConstraint*> rules;
    for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
        for (const NConstraint& k : *L) {
            if (k.type != NT_EXPR || !k.expr || k.expr->aux_read.empty() || k.nv() > 12) continue;
            if (expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;
            rules.push_back(&k);
        }
    std::vector<std::vector<int>> dom0(NA);
    for (int a = 0; a < NA; ++a)
        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
            if (auxf[i]) dom0[a].push_back(p.aux_values[a][i - aux_off[a]]);
    for (int u = 0; u < p.aux_u && u < NA; ++u) {
        if (dom0[u].size() < 2 || dom0[u].size() > 6 || deadline_passed()) continue;
        std::vector<int> gone;
        for (int w : dom0[u]) {
            // the case: the unknown at w, followed as a case analysis follows a digit (the light tiers, a step cap)
            std::vector<uint8_t> sv = vals;
            std::vector<uint32_t> sc = cand, sg = placed_g;
            std::vector<char> sa = auxf;
            std::vector<JMask> sj = jx;
            for (int i = aux_off[u]; i < aux_off[u + 1]; ++i) auxf[i] = p.aux_values[u][i - aux_off[u]] == w;
            const bool aux0 = fc_aux_on;
            fc_aux_on = true;
            ++version;
            const int ceil0 = fc_ceiling_now;
            const pm_long cap0 = fc_step_cap;
            static const int trial_cap = std::getenv("PENCILMARK_UTRIAL_CAP") ? std::atoi(std::getenv("PENCILMARK_UTRIAL_CAP")) : 30;
            fc_ceiling_now = 2, fc_step_cap = trial_cap;
            int steps = 0;
            const int r = fc_propagate(1, steps, nullptr);
            fc_ceiling_now = ceil0, fc_step_cap = cap0;
            fc_aux_on = aux0;
            vals.swap(sv), cand.swap(sc), placed_g.swap(sg), auxf.swap(sa), jx.swap(sj);
            ++version;
            if (r && !deadline_passed()) gone.push_back(w);
        }
        if (gone.empty() || gone.size() == dom0[u].size()) continue;  // all dead: a contradiction others show
        const auto& av = p.aux_values[u];
        Move& m = new_move(out, LAYER_TRIAL, 1.0, (int)gone.size());
        for (int w : gone) add_aeff(out, m, AE_AUX, u, (int)(std::find(av.begin(), av.end(), w) - av.begin()));
        std::vector<int> pc;
        for (const NConstraint* k : rules)
            if (std::find(k->expr->aux_read.begin(), k->expr->aux_read.end(), u) != k->expr->aux_read.end())
                pc.insert(pc.end(), k->vars.begin(), k->vars.end());
        set_pattern(out, m, pc);
        m.code = 7419;
    }
}

// ---------------------------------------------------------- JointHouses --
// joint candidates (design review stage 4): an exactly-one count rule over a layer is a house of literals (cell,
// digit, value) -- "one cold cell per row": (c, any digit, cold) for c in the row; "each digit cold once":
// (c, d, cold) for c in the grid, one house per digit d. A literal is live while its digit is a candidate, its value
// is open and the pair is not ruled out (jx). Sound readings (exactly-one, not "every cell takes one"): a decided
// literal kills the house's others; a lone live literal is true; when all of house A's live literals lie in house B,
// B's others die ("row 1's cold cell is a 5, so no other cell is a cold 5"). Naked subsets do NOT hold here. Every
// digit / value a removed pair leaves without a partner goes in the same move. Codes 7412 (decided), 7413 (lone),
// 7414 (one house inside another); 7415-7417 the same when a house is grid-wide (a digit inventory: "each digit cold
// once") -- registry codes LJH / LIV (data/patterns.csv). A literal's value may be a SET: "shift(x) != 0" (one
// shifted cell per house, either way) is (c, d, value in {-1, +1}); killing it removes the digit with every value of
// the set, and a lone one keeps only the set's values.
namespace {
bool jconst(const ExprNode& e, long long& v) {
    if (e.op == X_NUM) return v = e.v, true;
    if (e.op == X_NEG && e.kids.size() == 1 && e.kids[0].op == X_NUM) return v = -e.kids[0].v, true;
    return false;
}
void jcells(const ExprList& l, std::vector<int>& out) {
    if (l.var >= 0) out.push_back(l.var);
    for (const ExprList& x : l.items) jcells(x, out);
}
// "layer(x) == v" (ne false) or "layer(x) != v" (ne true) over comprehension slot s -> (layer, v)
bool jlayer_eq(const ExprNode& e, long long s, long long& layer, long long& val, bool& ne) {
    if ((e.op != X_EQ && e.op != X_NE) || e.kids.size() != 2) return false;
    ne = e.op == X_NE;
    for (int side = 0; side < 2; ++side) {
        const ExprNode& a = e.kids[side];
        const ExprNode& b = e.kids[1 - side];
        if (a.op == X_AUXCELL && a.kids.size() == 1 && a.kids[0].op == X_SLOT && a.kids[0].v == s && jconst(b, val))
            return layer = a.v, true;
    }
    return false;
}
bool jslot_eq(const ExprNode& e, long long s, long long dslot) {
    return e.op == X_EQ && e.kids.size() == 2 &&
           ((e.kids[0].op == X_SLOT && e.kids[0].v == s && e.kids[1].op == X_SLOT && e.kids[1].v == dslot) ||
            (e.kids[1].op == X_SLOT && e.kids[1].v == s && e.kids[0].op == X_SLOT && e.kids[0].v == dslot));
}
constexpr int JB_COUNT = 4, JB_ALL = 6;  // custom.FNS order (absint.cpp Builtin)
void jcollect(const ExprProgram& P, const ExprNode& e, long long dslot, long long dval,
              std::vector<std::tuple<long long, long long, long long, bool, std::vector<int>>>& out) {
    if (e.op == X_AND) {
        for (const ExprNode& k : e.kids) jcollect(P, k, dslot, dval, out);
        return;
    }
    // coverage: "let V = [L(x) for x in S]; all_different(V) and max(V) - min(V) == len(V) - 1" -- distinct
    // consecutive layer values on S; when the layer has exactly |S| values every value appears once (digit -1: the
    // registration expands it into one house per value)
    if (e.op == X_LET && e.kids.size() == 2 && e.kids[0].op == X_COMP && e.kids[0].kids.size() == 3 &&
        e.kids[0].kids[2].op == X_NONE && e.kids[0].kids[0].op == X_CELLS) {
        const ExprNode& c = e.kids[0];
        const ExprNode& b = c.kids[1];
        const ExprNode& body = e.kids[1];
        bool alldiff = false, span = false;
        std::function<void(const ExprNode&)> scan = [&](const ExprNode& x) {
            if (x.op == X_AND) {
                for (const ExprNode& k : x.kids) scan(k);
                return;
            }
            if (x.op == X_CALL && x.v == 16 /* ALL_DIFFERENT */ && x.kids.size() == 1 && x.kids[0].op == X_SLOT &&
                x.kids[0].v == e.v)
                alldiff = true;
            if (x.op == X_EQ && x.kids.size() == 2 && x.kids[0].op == X_SUB && x.kids[0].kids.size() == 2 &&
                x.kids[0].kids[0].op == X_CALL && x.kids[0].kids[0].v == 3 /* MAX */ &&
                x.kids[0].kids[1].op == X_CALL && x.kids[0].kids[1].v == 2 /* MIN */)
                span = true;
        };
        scan(body);
        // over computed values "x + L(x)": the value t is a set of (digit, layer value) pairs (digit -2)
        if (alldiff && span && b.op == X_ADD && b.kids.size() == 2 && c.kids[0].v >= 0 &&
            c.kids[0].v < (long long)P.lists.size())
            for (int t2 = 0; t2 < 2; ++t2) {
                const ExprNode& x = b.kids[t2];
                const ExprNode& l = b.kids[1 - t2];
                if (x.op == X_SLOT && x.v == c.v && l.op == X_AUXCELL && l.kids.size() == 1 && l.kids[0].op == X_SLOT &&
                    l.kids[0].v == c.v) {
                    std::vector<int> vars, cells;
                    jcells(P.lists[c.kids[0].v], vars);
                    for (int y : vars)
                        if (y >= 0 && y < (int)P.gcell.size()) cells.push_back(P.gcell[y]);
                    out.emplace_back(l.v, 0, -2, false, cells);
                    return;
                }
            }
        if (alldiff && span && b.op == X_AUXCELL && b.kids.size() == 1 && b.kids[0].op == X_SLOT &&
            b.kids[0].v == c.v && c.kids[0].v >= 0 && c.kids[0].v < (long long)P.lists.size()) {
            std::vector<int> vars, cells;
            jcells(P.lists[c.kids[0].v], vars);
            for (int x : vars)
                if (x >= 0 && x < (int)P.gcell.size()) cells.push_back(P.gcell[x]);
            out.emplace_back(b.v, 0, -1, false, cells);
        }
        return;
    }
    if (e.op == X_CALL && e.v == JB_ALL && e.kids.size() == 1 && e.kids[0].op == X_COMP &&
        e.kids[0].kids.size() == 3 && e.kids[0].kids[2].op == X_NONE) {
        const ExprNode& c = e.kids[0];
        const ExprNode& src = c.kids[0];
        std::vector<long long> ds;
        long long lo, hi, x;
        if (src.op == X_RANGE && src.kids.size() == 2 && jconst(src.kids[0], lo) && jconst(src.kids[1], hi))
            for (long long d = lo; d <= hi && d - lo < 64; ++d) ds.push_back(d);
        else if (src.op == X_LIST)
            for (const ExprNode& k : src.kids)
                if (jconst(k, x)) ds.push_back(x);
        for (long long d : ds) jcollect(P, c.kids[1], c.v, d, out);
        return;
    }
    if (e.op != X_EQ || e.kids.size() != 2) return;
    for (int side = 0; side < 2; ++side) {
        const ExprNode& cnt = e.kids[side];
        long long one;
        if (!jconst(e.kids[1 - side], one) || one != 1) continue;
        if (cnt.op != X_CALL || cnt.v != JB_COUNT || cnt.kids.size() != 1 || cnt.kids[0].op != X_COMP) continue;
        const ExprNode& c = cnt.kids[0];
        if (c.kids.size() != 3 || c.kids[2].op != X_NONE || c.kids[0].op != X_CELLS) continue;
        long long layer, val, digit = 0;
        bool ne = false;
        const ExprNode& body = c.kids[1];
        if (!jlayer_eq(body, c.v, layer, val, ne)) {
            if (body.op != X_AND || body.kids.size() != 2 || dslot < 0) continue;
            bool ok = false;
            for (int t = 0; t < 2 && !ok; ++t)
                ok = jlayer_eq(body.kids[t], c.v, layer, val, ne) && jslot_eq(body.kids[1 - t], c.v, dslot);
            if (!ok) continue;
            digit = dval;
        }
        std::vector<int> vars;
        if (c.kids[0].v < 0 || c.kids[0].v >= (long long)P.lists.size()) continue;
        jcells(P.lists[c.kids[0].v], vars);
        std::vector<int> cells;
        for (int x : vars)
            if (x >= 0 && x < (int)P.gcell.size()) cells.push_back(P.gcell[x]);
        out.emplace_back(layer, val, digit, ne, cells);
    }
}
}  // namespace

// the puzzle's joint houses (exactly-one count rules over a layer), cached per puzzle
const std::vector<JHouse>& jhouses_of(const Puzzle& p) {
    static thread_local std::unordered_map<uint64_t, std::vector<JHouse>> cache;  // per puzzle: its houses
    auto it = cache.find(p.uid);
    auto joint_ok = [&](int a) { return a >= p.aux_u && a < (int)p.aux_values.size() && p.D <= 9 &&
                                        p.aux_values[a].size() <= 16; };
    if (it == cache.end()) {
        std::vector<JHouse> hs;
        std::set<std::tuple<int, uint32_t, int, std::vector<int>>> seen;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr) continue;
                std::vector<std::tuple<long long, long long, long long, bool, std::vector<int>>> got;
                jcollect(*k.expr, k.expr->root, -1, 0, got);
                for (auto& [layer, val, digit, ne, cells] : got) {
                    if (layer < 0 || layer >= p.aux_layers || cells.empty()) continue;
                    const int a0 = p.aux_u + (int)layer * p.N + cells[0];
                    if (a0 >= (int)p.aux_values.size()) continue;
                    if (digit == -2) {  // coverage of digit + layer values: one pair-set house per value
                        const auto& av = p.aux_values[a0];
                        if (!joint_ok(a0)) continue;
                        const int tmin = 1 + *std::min_element(av.begin(), av.end());
                        const int tmax = p.D + *std::max_element(av.begin(), av.end());
                        if (tmax - tmin + 1 != (int)cells.size()) continue;
                        std::vector<int> cs = cells;
                        std::sort(cs.begin(), cs.end());
                        for (int t = tmin; t <= tmax; ++t) {
                            JHouse h;
                            h.layer = (int)layer, h.digit = 0, h.cells = cs;
                            for (int d = 1; d <= p.D; ++d)
                                for (size_t vi = 0; vi < av.size(); ++vi)
                                    if (d + av[vi] == t) h.pmask.set(Solver::jbit(d, (int)vi));
                            if (h.pmask.any()) hs.push_back(std::move(h));
                        }
                        continue;
                    }
                    if (digit < 0) {  // coverage: one house per value, when the layer has exactly |cells| values
                        const auto& av = p.aux_values[a0];
                        if (av.size() != cells.size() || av.size() > 32) continue;
                        std::vector<int> cs = cells;
                        std::sort(cs.begin(), cs.end());
                        for (size_t vi = 0; vi < av.size(); ++vi) {
                            JHouse h;
                            h.layer = (int)layer, h.digit = 0, h.vmask = 1u << vi, h.cells = cs;
                            if (seen.insert({h.layer, h.vmask, h.digit, cs}).second) hs.push_back(std::move(h));
                        }
                        continue;
                    }
                    // layer-only houses work on any layer (up to 32 values); digit houses need pair state
                    if (digit ? !joint_ok(a0) : p.aux_values[a0].size() > 32) continue;
                    const auto& av = p.aux_values[a0];
                    const auto f = std::find(av.begin(), av.end(), (int)val);
                    if (f == av.end()) continue;
                    std::vector<int> cs = cells;
                    std::sort(cs.begin(), cs.end());
                    JHouse h;
                    const int vi = (int)(f - av.begin());
                    h.layer = (int)layer, h.digit = (int)digit, h.cells = cs;
                    h.vmask = ne ? (((1u << av.size()) - 1) & ~(1u << vi)) : 1u << vi;
                    if (seen.insert({h.layer, h.vmask, h.digit, cs}).second) hs.push_back(std::move(h));
                }
            }
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(hs)).first;
    }
    return it->second;
}

void Solver::joint_houses(MoveBuf& out) {
    if (!has_aux() || p.aux_layers <= 0 || jx.size() != p.aux_values.size()) return;
    const std::vector<JHouse>& H = jhouses_of(p);
    if (H.empty()) return;
    auto avar = [&](const JHouse& h, int c) { return p.aux_u + h.layer * p.N + c; };
    auto decided = [&](int a, uint32_t vm) {  // the layer variable's open values all lie in the set
        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
            if (auxf[i] && !((vm >> (i - aux_off[a])) & 1)) return false;
        return true;
    };
    auto lit_live = [&](int a, int d, uint32_t vm) {  // the digit with some value of the set
        for (uint32_t m = vm; m; m &= m - 1)
            if (joint_live(a, d, __builtin_ctz(m))) return true;
        return false;
    };
    struct Lit { int c, d; };
    std::vector<std::vector<Lit>> live(H.size());
    std::vector<int> sure(H.size(), 0);
    for (size_t hi = 0; hi < H.size(); ++hi) {
        const JHouse& h = H[hi];
        if (h.pmask.any()) continue;  // pair-set houses: read below
        for (int c : h.cells) {
            const int a = avar(h, c);
            for (int d = 1; d <= p.D; ++d) {
                if (h.digit && d != h.digit) continue;
                if (!lit_live(a, d, h.vmask)) continue;
                live[hi].push_back({c, d});
                if ((vals[c] == d || (!h.digit && vals[c])) && decided(a, h.vmask)) ++sure[hi];
            }
        }
    }
    std::set<std::tuple<int, int, int>> said;  // (aux variable, digit, value index) already removed this call
    // one move removing these pairs (and, for a lone literal, setting it), with the digits / values left without a
    // partner; nothing new -> no move
    auto emit = [&](int code, const std::vector<std::tuple<int, int, int>>& kills, int set_c, int set_d, int set_a,
                    uint32_t set_vm, const std::vector<int>& pattern) {
        std::vector<std::pair<int, int>> del;   // digit eliminations
        std::vector<std::pair<int, int>> aout;  // (aux variable, value index)
        std::vector<std::tuple<int, int, int>> jout;
        std::map<int, JMask> after;  // aux variable -> its removed pairs after this move
        for (auto& [a, d, vi] : kills) {
            if (!joint_live(a, d, vi)) continue;
            if (!joint_ok(a)) {  // no pair state: the literal (any digit) goes as the whole value
                if (std::find(aout.begin(), aout.end(), std::make_pair(a, vi)) == aout.end()) aout.emplace_back(a, vi);
                continue;
            }
            if (!said.insert({a, d, vi}).second) continue;
            jout.emplace_back(a, d, vi);
            auto f = after.find(a);
            if (f == after.end()) f = after.emplace(a, jx[a]).first;
            f->second.set(jbit(d, vi));
        }
        if (set_c >= 0) {  // the literal holds: the layer's value is in the set; digits without such a value go
            for (int i = aux_off[set_a]; i < aux_off[set_a + 1]; ++i)
                if (auxf[i] && !((set_vm >> (i - aux_off[set_a])) & 1)) aout.emplace_back(set_a, i - aux_off[set_a]);
            if (!vals[set_c])
                for (int d = 1; d <= p.D; ++d)
                    if ((cand[set_c] & bit(d)) && d != set_d && (set_d || !lit_live(set_a, d, set_vm)))
                        del.emplace_back(set_c, d);
        }
        for (auto& [a, bits] : after) {  // partners left: a digit with no open value, a value with no digit
            const int c = aux_cell(a);
            const int nvals = (int)p.aux_values[a].size();
            for (int d = 1; d <= p.D; ++d) {
                if (vals[c] ? vals[c] != d : !(cand[c] & bit(d))) continue;
                bool any = false;
                for (int vi = 0; vi < nvals && !any; ++vi) any = auxf[aux_off[a] + vi] && !bits[jbit(d, vi)];
                if (!any && !vals[c]) del.emplace_back(c, d);
            }
            for (int vi = 0; vi < nvals; ++vi) {
                if (!auxf[aux_off[a] + vi]) continue;
                bool any = false;
                for (int d = 1; d <= p.D && !any; ++d)
                    any = (vals[c] ? vals[c] == d : (cand[c] & bit(d))) && !bits[jbit(d, vi)];
                if (!any && std::find(aout.begin(), aout.end(), std::make_pair(a, vi)) == aout.end()) aout.emplace_back(a, vi);
            }
        }
        const bool place = set_c >= 0 && set_d > 0 && !vals[set_c];
        if (jout.empty() && aout.empty() && del.empty() && !place) return;
        Move& m = new_move(out, LAYER_COUNT, 1.0, (int)(jout.size() + aout.size() + del.size() + place));
        if (place) m.pc = set_c, m.pv = set_d;
        for (auto& e : del) add_el(out, m, e.first, e.second);
        for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
        for (auto& [a, d, vi] : jout) add_aeff(out, m, AE_JOINT, a, d * 16 + vi);
        set_pattern(out, m, pattern);
        m.code = code;
    };
    for (size_t hi = 0; hi < H.size(); ++hi) {
        const JHouse& h = H[hi];
        if (live[hi].empty() || sure[hi] > 1) continue;  // empty / two decided: a contradiction others show
        if (sure[hi] == 1 && h.digit) {  // 7412: the decided literal kills the house's others
            std::vector<std::tuple<int, int, int>> kills;
            for (const Lit& l : live[hi])
                if (!(vals[l.c] == l.d && decided(avar(h, l.c), h.vmask)))
                    for (uint32_t m = h.vmask; m; m &= m - 1) kills.emplace_back(avar(h, l.c), l.d, __builtin_ctz(m));
            emit(h.cells.size() > (size_t)p.D ? 7415 : 7412, kills, -1, 0, -1, 0, h.cells);
        } else if (sure[hi] == 0) {
            bool one_cell = true;
            for (const Lit& l : live[hi]) one_cell &= l.c == live[hi][0].c;
            if (one_cell) {  // 7413: a lone cell holds the house's literal
                const int c = live[hi][0].c, a = avar(h, c);
                emit(h.cells.size() > (size_t)p.D ? 7416 : 7413, {}, c, live[hi].size() == 1 ? live[hi][0].d : 0, a, h.vmask,
                     {c});
            }
        }
    }
    // pair-set houses (coverage over digit + layer value): a cell's literal is live while one of its pairs is
    for (const JHouse& h : H) {
        if (h.pmask.none()) continue;
        std::vector<int> lc;
        int nsure = 0, surec = -1;
        for (int c : h.cells) {
            const int a = avar(h, c);
            bool any = false, is_sure = false;
            for (size_t b = h.pmask._Find_first(); b < h.pmask.size(); b = h.pmask._Find_next(b)) {
                const int d = (int)b / 16 + 1, vi = (int)b % 16;
                if (!joint_live(a, d, vi)) continue;
                any = true;
                is_sure |= vals[c] == d && decided(a, 1u << vi);
            }
            if (any) lc.push_back(c);
            if (is_sure) ++nsure, surec = c;
        }
        if (lc.empty() || nsure > 1) continue;
        const bool wide = h.cells.size() > (size_t)p.D;
        if (nsure == 0) {  // its live pairs all inside a regular house B: B's literals elsewhere die ("value 0 on the
            // line is a shifted 1, so the grid's one shifted 1 is on the line")
            std::vector<std::tuple<int, int, int>> pairs;  // (cell, digit, value index)
            for (int c : lc)
                for (size_t b = h.pmask._Find_first(); b < h.pmask.size(); b = h.pmask._Find_next(b)) {
                    const int d = (int)b / 16 + 1, vi = (int)b % 16;
                    if (joint_live(avar(h, c), d, vi)) pairs.emplace_back(c, d, vi);
                }
            for (size_t bi = 0; bi < H.size(); ++bi) {
                const JHouse& B = H[bi];
                if (B.pmask.any() || B.layer != h.layer || sure[bi] > 1) continue;
                bool inside = true;
                for (auto& [c, d, vi] : pairs)
                    inside &= (!B.digit || d == B.digit) && ((B.vmask >> vi) & 1) &&
                              std::binary_search(B.cells.begin(), B.cells.end(), c);
                if (!inside) continue;
                std::vector<std::tuple<int, int, int>> kills;
                for (const Lit& l : live[bi]) {
                    for (uint32_t m = B.vmask; m; m &= m - 1) {
                        const int vi = __builtin_ctz(m);
                        bool inA = false;
                        for (auto& [c, d, wi] : pairs) inA |= c == l.c && d == l.d && wi == vi;
                        if (!inA) kills.emplace_back(avar(B, l.c), l.d, vi);
                    }
                }
                if (!kills.empty()) emit(wide || B.cells.size() > (size_t)p.D ? 7417 : 7414, kills, -1, 0, -1, 0, h.cells);
            }
        }
        std::vector<std::tuple<int, int, int>> kills;
        if (nsure == 1) {  // decided: the house's other cells lose its pairs
            for (int c : lc)
                if (c != surec)
                    for (size_t b = h.pmask._Find_first(); b < h.pmask.size(); b = h.pmask._Find_next(b)) {
                        kills.emplace_back(avar(h, c), (int)b / 16 + 1, (int)b % 16);
                    }
            emit(wide ? 7415 : 7412, kills, -1, 0, -1, 0, h.cells);
        } else if (lc.size() == 1) {  // one cell left: it takes one of the pairs -- its other pairs go
            const int c = lc[0], a = avar(h, c);
            for (int d = 1; d <= p.D; ++d)
                for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi)
                    if (!h.pmask[jbit(d, vi)]) kills.emplace_back(a, d, vi);
            emit(wide ? 7416 : 7413, kills, -1, 0, -1, 0, {c});
        }
    }
    // 7422: two pair-set houses of one coverage (their cells differ: one cell, one value) whose live pairs all lie in
    // two cell-disjoint regular houses: each of those holds one of them, so their other literals die ("values 0 and
    // 10 are on the line; the line is in rows 8-9, one shifted cell each: the rest of rows 8-9 is natural")
    {
        std::vector<size_t> ph;
        std::vector<std::vector<std::tuple<int, int, int>>> pp;  // per pair-set house: its live (cell, digit, value)
        for (size_t hi = 0; hi < H.size(); ++hi) {
            const JHouse& h = H[hi];
            if (h.pmask.none()) continue;
            std::vector<std::tuple<int, int, int>> pairs;
            bool sure_any = false;
            for (int c : h.cells)
                for (size_t b = h.pmask._Find_first(); b < h.pmask.size(); b = h.pmask._Find_next(b)) {
                    const int d = (int)b / 16 + 1, vi = (int)b % 16;
                    if (!joint_live(avar(h, c), d, vi)) continue;
                    pairs.emplace_back(c, d, vi);
                    sure_any |= vals[c] == d && decided(avar(h, c), 1u << vi);
                }
            if (pairs.empty() || sure_any) continue;
            ph.push_back(hi), pp.push_back(std::move(pairs));
        }
        auto in_house = [&](const JHouse& B, int c, int d, int vi) {
            return (!B.digit || d == B.digit) && ((B.vmask >> vi) & 1) &&
                   std::binary_search(B.cells.begin(), B.cells.end(), c);
        };
        auto disjoint = [](const std::vector<int>& x, const std::vector<int>& y) {
            for (size_t i = 0, j = 0; i < x.size() && j < y.size();) {
                if (x[i] == y[j]) return false;
                x[i] < y[j] ? ++i : ++j;
            }
            return true;
        };
        for (size_t i = 0; i < ph.size(); ++i)
            for (size_t j = i + 1; j < ph.size(); ++j) {
                if (H[ph[i]].cells != H[ph[j]].cells || H[ph[i]].layer != H[ph[j]].layer) continue;
                std::vector<std::tuple<int, int, int>> both = pp[i];
                both.insert(both.end(), pp[j].begin(), pp[j].end());
                std::vector<size_t> cov;  // regular houses holding at least one of the pairs
                for (size_t bi = 0; bi < H.size(); ++bi) {
                    const JHouse& B = H[bi];
                    if (B.pmask.any() || B.layer != H[ph[i]].layer || sure[bi]) continue;
                    for (auto& [c, d, vi] : both)
                        if (in_house(B, c, d, vi)) { cov.push_back(bi); break; }
                }
                for (size_t x = 0; x < cov.size(); ++x)
                    for (size_t y = x + 1; y < cov.size(); ++y) {
                        const JHouse &B1 = H[cov[x]], &B2 = H[cov[y]];
                        if (!disjoint(B1.cells, B2.cells)) continue;
                        bool inside = true;
                        for (auto& [c, d, vi] : both) inside &= in_house(B1, c, d, vi) || in_house(B2, c, d, vi);
                        if (!inside) continue;
                        std::vector<std::tuple<int, int, int>> kills;
                        for (size_t bi : {cov[x], cov[y]})
                            for (const Lit& l : live[bi])
                                for (uint32_t m = H[bi].vmask; m; m &= m - 1) {
                                    const int vi = __builtin_ctz(m);
                                    if (std::find(both.begin(), both.end(), std::make_tuple(l.c, l.d, vi)) == both.end())
                                        kills.emplace_back(avar(H[bi], l.c), l.d, vi);
                                }
                        if (kills.empty()) continue;
                        std::vector<int> pat = B1.cells;
                        pat.insert(pat.end(), B2.cells.begin(), B2.cells.end());
                        emit(7422, kills, -1, 0, -1, 0, pat);
                    }
            }
        // 7423: pair-set houses whose live pairs all carry one digit d place a d in their cells (distinct cells for
        // distinct values): n of them inside n disjoint complete houses -> d leaves those houses' other cells ("values
        // 0 and 1 on the line are both 1s; the line is in rows 8-9: their 1s are on the line")
        auto one_digit = [&](size_t k) {
            const int d = std::get<1>(pp[k][0]);
            for (auto& t : pp[k])
                if (std::get<1>(t) != d) return 0;
            return d;
        };
        auto in_group = [&](int g, int c) {
            const auto& cs = p.groups[g].cells;
            return std::find(cs.begin(), cs.end(), c) != cs.end();
        };
        for (size_t i = 0; i < ph.size(); ++i) {
            const int d = one_digit(i);
            if (!d) continue;
            for (size_t j = i; j < ph.size(); ++j) {
                if (j != i && (one_digit(j) != d || H[ph[i]].cells != H[ph[j]].cells)) continue;
                std::vector<int> cells;  // the cells that may hold the bases' d
                for (size_t k : {i, j})
                    for (auto& t : pp[k]) cells.push_back(std::get<0>(t));
                std::sort(cells.begin(), cells.end());
                cells.erase(std::unique(cells.begin(), cells.end()), cells.end());
                std::vector<int> cov;  // complete houses holding one of them
                for (int g : p.houses)
                    for (int c : cells)
                        if (in_group(g, c)) { cov.push_back(g); break; }
                const size_t n = j == i ? 1 : 2;
                for (size_t x = 0; x < cov.size(); ++x)
                    for (size_t y = n == 1 ? x : x + 1; y < (n == 1 ? x + 1 : cov.size()); ++y) {
                        const int g1 = cov[x], g2 = cov[y];
                        if (n == 2 && p.group_overlap[(size_t)g1 * p.G + g2]) continue;
                        bool inside = true;
                        for (int c : cells) inside &= in_group(g1, c) || in_group(g2, c);
                        if (!inside) continue;
                        std::vector<std::tuple<int, int, int>> kills;
                        std::vector<int> pat;
                        for (int g : n == 1 ? std::vector<int>{g1} : std::vector<int>{g1, g2})
                            for (int c : p.groups[g].cells) {
                                pat.push_back(c);
                                if (std::binary_search(cells.begin(), cells.end(), c) || vals[c] || !(cand[c] & bit(d)))
                                    continue;
                                const int a = p.aux_u + H[ph[i]].layer * p.N + c;
                                for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi) kills.emplace_back(a, d, vi);
                            }
                        if (!kills.empty()) emit(7423, kills, -1, 0, -1, 0, pat);
                    }
            }
        }
    }
    // 7414: all of house A's live literals inside house B -> B's others die (same layer and value)
    for (size_t ai = 0; ai < H.size(); ++ai) {
        if (live[ai].empty() || sure[ai]) continue;
        for (size_t bi = 0; bi < H.size(); ++bi) {
            if (bi == ai || H[bi].layer != H[ai].layer || H[bi].vmask != H[ai].vmask || sure[bi] > 1) continue;
            const JHouse& B = H[bi];
            bool inside = true;
            for (const Lit& l : live[ai])
                inside &= (!B.digit || l.d == B.digit) && std::binary_search(B.cells.begin(), B.cells.end(), l.c);
            if (!inside) continue;
            std::vector<std::tuple<int, int, int>> kills;
            for (const Lit& l : live[bi]) {
                bool inA = false;
                for (const Lit& x : live[ai]) inA |= x.c == l.c && x.d == l.d;
                if (!inA)
                    for (uint32_t m = B.vmask; m; m &= m - 1) kills.emplace_back(avar(B, l.c), l.d, __builtin_ctz(m));
            }
            if (kills.empty()) continue;
            std::vector<int> pat = H[ai].cells;
            const bool inv = H[ai].cells.size() > (size_t)p.D || B.cells.size() > (size_t)p.D;
            emit(inv ? 7417 : 7414, kills, -1, 0, -1, 0, pat);
        }
    }
}

// ------------------------------------------------------- ModifierEquiv --
// set equivalence with modifiers (survey principles 2-4; the hosts' "green and blue differ by one set of 1-9"): two
// groups of whole houses (a and b full sets), their shared cells cancelled, whose leftovers are exact unions of cages
// summing modified values ("sum(x * L(x) for x in C) == t", L a multiplier layer {1, k}). Digits differ by 45 (b - a),
// clues by TB - TA, so the modifiers' extra E (k - 1 times each modified digit) on the two leftovers differs by
// K = TB - TA - 45 (b - a). Each side's E is bounded by how many modified cells it can hold (the count rules: one per
// house) and by their digits (distinct when each digit is modified once); the equation narrows both, and a modified
// digit that fits no count / sum is ruled out there as a joint pair ("a doubled 9 in the 39-cage"). Code 7421.
namespace {
bool mcage(const ExprProgram& P, const ExprNode& e, long long& layer, long long& total, std::vector<int>& cells) {
    if (e.op == X_AND) {
        for (const ExprNode& k : e.kids)
            if (mcage(P, k, layer, total, cells)) return true;
        return false;
    }
    if (e.op != X_EQ || e.kids.size() != 2) return false;
    for (int side = 0; side < 2; ++side) {
        const ExprNode& sm = e.kids[side];
        if (!jconst(e.kids[1 - side], total)) continue;
        if (sm.op != X_CALL || sm.v != 0 /* SUM */ || sm.kids.size() != 1 || sm.kids[0].op != X_COMP) continue;
        const ExprNode& c = sm.kids[0];
        if (c.kids.size() != 3 || c.kids[2].op != X_NONE || c.kids[0].op != X_CELLS) continue;
        const ExprNode& b = c.kids[1];
        if (b.op != X_MUL || b.kids.size() != 2) continue;
        for (int t = 0; t < 2; ++t) {
            const ExprNode& x = b.kids[t];
            const ExprNode& l = b.kids[1 - t];
            if (x.op == X_SLOT && x.v == c.v && l.op == X_AUXCELL && l.kids.size() == 1 && l.kids[0].op == X_SLOT &&
                l.kids[0].v == c.v && c.kids[0].v >= 0 && c.kids[0].v < (long long)P.lists.size()) {
                std::vector<int> vars;
                jcells(P.lists[c.kids[0].v], vars);
                cells.clear();
                for (int y : vars)
                    if (y >= 0 && y < (int)P.gcell.size()) cells.push_back(P.gcell[y]);
                layer = l.v;
                return true;
            }
        }
    }
    return false;
}
struct MEq {
    int layer;
    std::vector<int> la, lb;  // the two leftovers' cells
    long long Klo, Khi;       // E(lb) - E(la) in [Klo, Khi] (a cage cover: one value; thermos: a bound)
    std::vector<int> ga, gb;  // the two groups' houses (p.groups indices): count houses on all -> counts differ by
                              // |gb| - |ga| (the shared cells cancel)
    bool exact = true;        // the leftovers are the whole group difference (no known digits cancelled)
};
// a value term "x * L(x)" of one cell (x a named cell of the rule) -> its board cell, or -1
int mvalue_cell(const ExprProgram& P, const ExprNode& e, long long layer) {
    auto cell_of = [&](const ExprNode& x) -> int {
        int var = -1;
        if (x.op == X_CELL) var = (int)x.v;
        else if (x.op == X_CELLS && x.v >= 0 && x.v < (long long)P.lists.size() && P.lists[x.v].items.empty())
            var = P.lists[x.v].var;
        return var >= 0 && var < (int)P.gcell.size() ? P.gcell[var] : -1;
    };
    if (e.op != X_MUL || e.kids.size() != 2) return -1;
    for (int t = 0; t < 2; ++t) {
        const ExprNode& x = e.kids[t];
        const ExprNode& l = e.kids[1 - t];
        if (l.op == X_AUXCELL && l.v == layer && l.kids.size() == 1) {
            const int c = cell_of(x);
            if (c >= 0 && c == cell_of(l.kids[0])) return c;
        }
    }
    return -1;
}
}  // namespace

// this state's extra-value range per leftover (sorted cells), from ModifierEquiv's equations: ModCage reads a cage
// with it ("E(39-cage) = 9: a doubled 9 in it")
thread_local std::map<std::vector<int>, std::pair<long long, long long>> g_side_extra;

void Solver::modifier_equiv(MoveBuf& out) {
    g_side_extra.clear();
    if (!has_aux() || p.aux_layers <= 0 || jx.size() != p.aux_values.size() || p.N > 128) return;
    static thread_local std::unordered_map<uint64_t, std::vector<MEq>> cache;
    auto it = cache.find(p.uid);
    if (it == cache.end()) {
        std::vector<MEq> eqs;
        using Mask = std::bitset<128>;
        std::vector<std::pair<Mask, long long>> cages;
        int layer = -1;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr) continue;
                long long l, t;
                std::vector<int> cells;
                if (!mcage(*k.expr, k.expr->root, l, t, cells) || cells.empty()) continue;
                if (layer >= 0 && l != layer) continue;
                layer = (int)l;
                Mask m;
                for (int c : cells) m.set(c);
                cages.push_back({m, t});
            }
        if (layer >= 0 && !cages.empty()) {
            std::vector<Mask> hs;
            for (int hi : p.houses)
                if ((int)p.groups[hi].cells.size() == p.D) {
                    Mask m;
                    for (int c : p.groups[hi].cells) m.set(c);
                    hs.push_back(m);
                }
            std::vector<int> hid;  // hs[i]'s p.groups index
            for (int hi : p.houses)
                if ((int)p.groups[hi].cells.size() == p.D) hid.push_back(hi);
            struct Grp { Mask m; int n; std::vector<int> g; };
            std::vector<Grp> grp;
            for (size_t a = 0; a < hs.size(); ++a) {
                grp.push_back({hs[a], 1, {hid[a]}});
                for (size_t b = a + 1; b < hs.size(); ++b) {
                    if ((hs[a] & hs[b]).any()) continue;
                    grp.push_back({hs[a] | hs[b], 2, {hid[a], hid[b]}});
                    for (size_t c = b + 1; c < hs.size(); ++c)
                        if (!((hs[a] | hs[b]) & hs[c]).any())
                            grp.push_back({hs[a] | hs[b] | hs[c], 3, {hid[a], hid[b], hid[c]}});
                }
            }
            auto cover = [&](const Mask& left, long long& tot) {
                Mask rest = left;
                tot = 0;
                for (auto& [m, t] : cages)
                    if ((m & ~rest).none() && (m & rest).any()) rest &= ~m, tot += t;
                return rest.none();
            };
            std::set<std::pair<std::string, std::string>> seen;
            for (size_t i = 0; i < grp.size() && eqs.size() < 64; ++i)
                for (size_t j = 0; j < grp.size() && eqs.size() < 64; ++j) {
                    if (grp[i].n >= grp[j].n) continue;
                    const Mask la = grp[i].m & ~grp[j].m, lb = grp[j].m & ~grp[i].m;
                    if (la.none() || lb.none()) continue;
                    long long ta, tb;
                    if (!cover(la, ta) || !cover(lb, tb)) continue;
                    if (!seen.insert({la.to_string(), lb.to_string()}).second) continue;
                    MEq e;
                    e.layer = layer;
                    for (int c = 0; c < p.N; ++c) {
                        if (la.test(c)) e.la.push_back(c);
                        if (lb.test(c)) e.lb.push_back(c);
                    }
                    e.Klo = e.Khi = tb - ta - (long long)p.D * (p.D + 1) / 2 * (grp[j].n - grp[i].n);
                    e.ga = grp[i].g, e.gb = grp[j].g;
                    eqs.push_back(std::move(e));
                }
        }
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(eqs)).first;
    }
    // thermo equations: per puzzle and set of givens (their known digits cancel)
    static thread_local std::unordered_map<uint64_t, std::vector<MEq>> tcache;
    uint64_t gkey = p.uid * 0x9E3779B97F4A7C15ull;
    for (int c = 0; c < p.N && c < (int)is_given.size(); ++c)
        if (is_given[c] && vals[c]) gkey = (gkey ^ (uint64_t)(c * 16 + vals[c])) * 0x100000001B3ull;
    auto tit = tcache.find(gkey);
    if (tit == tcache.end()) {
        std::vector<MEq> eqs;
        using Mask = std::bitset<128>;
        const int layer = it->second.empty() ? -1 : it->second[0].layer;
        // thermos on values ("a * L(a) < b * L(b)"): leftovers (known digits cancelled pairwise) matched bulb to tip
        // along increasing chains -- the tips' values exceed the bulbs' by at least the chains' lengths, the digits
        // are the same multiset, so E(tips) - E(bulbs) >= that sum ("13 bulbs in blue, the same 13 digits on tips in
        // orange: the tips need 13 more")
        int tl = -1;
        std::vector<std::vector<std::pair<int, int>>> lt(p.N);  // u -> (v, w): value(v) >= value(u) + w
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr || p.N > 128) continue;
                const ExprNode& r = k.expr->root;
                if ((r.op != X_LT && r.op != X_LE && r.op != X_GT && r.op != X_GE) || r.kids.size() != 2) continue;
                for (long long l = 0; l < p.aux_layers; ++l) {
                    const int a = mvalue_cell(*k.expr, r.kids[0], l), b = mvalue_cell(*k.expr, r.kids[1], l);
                    if (a < 0 || b < 0 || a == b || (tl >= 0 && tl != l) || (layer >= 0 && layer != l)) continue;
                    tl = (int)l;
                    const int w = r.op == X_LT || r.op == X_GT ? 1 : 0;
                    if (r.op == X_LT || r.op == X_LE) lt[a].push_back({b, w});
                    else lt[b].push_back({a, w});
                }
            }
        if (tl >= 0) {
            // longest chain lengths (a DAG; a cycle: no thermo equations)
            std::vector<std::vector<int>> dist(p.N, std::vector<int>(p.N, -1));
            bool cyc = false;
            for (int s = 0; s < p.N && !cyc; ++s) {
                if (lt[s].empty()) continue;
                std::vector<int> best(p.N, -1);
                // relax in DFS order from s (depth bounded by N: longest paths in a DAG)
                std::function<void(int, int, int)> go = [&](int u, int dd, int depth) {
                    if (depth > p.N) { cyc = true; return; }
                    if (dd <= best[u]) return;
                    best[u] = dd;
                    for (auto [v, w] : lt[u]) go(v, dd + w, depth + 1);
                };
                go(s, 0, 0);
                for (int v = 0; v < p.N; ++v)
                    if (v != s && best[v] >= 0) dist[s][v] = best[v];
            }
            Mask T, Gv;  // thermo cells; given cells
            for (int c = 0; c < p.N; ++c) {
                if (!lt[c].empty()) T.set(c);
                for (auto [v, w] : lt[c]) T.set(v);
                if (c < (int)is_given.size() && is_given[c] && vals[c]) Gv.set(c);
            }
            std::vector<Mask> hs;
            std::vector<int> hid;
            for (int hi : p.houses)
                if ((int)p.groups[hi].cells.size() == p.D) {
                    Mask m;
                    for (int c : p.groups[hi].cells) m.set(c);
                    hs.push_back(m), hid.push_back(hi);
                }
            struct Grp { Mask m; std::vector<int> g; };
            std::vector<Grp> grp;
            for (size_t a = 0; a < hs.size(); ++a) {
                grp.push_back({hs[a], {hid[a]}});
                for (size_t b = a + 1; b < hs.size(); ++b) {
                    if ((hs[a] & hs[b]).any()) continue;
                    grp.push_back({hs[a] | hs[b], {hid[a], hid[b]}});
                    for (size_t c = b + 1; c < hs.size(); ++c)
                        if (!((hs[a] | hs[b]) & hs[c]).any()) grp.push_back({hs[a] | hs[b] | hs[c], {hid[a], hid[b], hid[c]}});
                }
            }
            int nthermo = 0;
            std::set<std::pair<std::string, std::string>> seen;
            for (size_t i = 0; i < grp.size() && nthermo < 32 && !cyc; ++i)
                for (size_t j = i + 1; j < grp.size() && nthermo < 32; ++j) {
                    const Mask la = grp[i].m & ~grp[j].m, lb = grp[j].m & ~grp[i].m;
                    if (la.none() || lb.none() || ((la | lb) & ~T & ~Gv).any()) continue;
                    // known digits cancel pairwise between the two sides
                    std::vector<int> xa, xb, ga, gb;
                    for (int c = 0; c < p.N; ++c) {
                        if (la.test(c)) (Gv.test(c) ? ga : xa).push_back(c);
                        if (lb.test(c)) (Gv.test(c) ? gb : xb).push_back(c);
                    }
                    std::multiset<int> da, db;
                    for (int c : ga) da.insert(vals[c]);
                    for (int c : gb) db.insert(vals[c]);
                    if (da != db || xa.empty() || xa.size() != xb.size()) continue;
                    const long long delta45 = (long long)p.D * (p.D + 1) / 2 * ((long long)grp[j].g.size() - (long long)grp[i].g.size());
                    for (int dir = 0; dir < 2; ++dir) {  // 0: chains from xa up to xb; 1: from xb up to xa
                        const std::vector<int>& U = dir ? xb : xa;
                        const std::vector<int>& V = dir ? xa : xb;
                        std::vector<int> mv(V.size(), -1);
                        std::function<bool(int, std::vector<char>&)> aug = [&](int u, std::vector<char>& vis) {
                            for (size_t v = 0; v < V.size(); ++v) {
                                if (vis[v] || dist[U[u]][V[v]] < 0) continue;
                                vis[v] = 1;
                                if (mv[v] < 0 || aug(mv[v], vis)) { mv[v] = u; return true; }
                            }
                            return false;
                        };
                        bool full = true;
                        for (size_t u = 0; u < U.size() && full; ++u) {
                            std::vector<char> vis(V.size(), 0);
                            full = aug((int)u, vis);
                        }
                        if (!full) continue;
                        long long sum = 0;
                        for (size_t v = 0; v < V.size(); ++v) sum += dist[U[mv[v]]][V[v]];
                        if (sum <= 0) continue;
                        if (!seen.insert({(dir ? "b" : "a") + la.to_string(), lb.to_string()}).second) continue;
                        MEq e;
                        e.layer = tl, e.la = xa, e.lb = xb, e.ga = grp[i].g, e.gb = grp[j].g, e.exact = ga.empty();
                        // values: V - U >= sum; digits: xb - xa = 45 (|gb| - |ga|)
                        if (dir == 0) e.Klo = sum - delta45, e.Khi = LLONG_MAX / 4;
                        else e.Klo = LLONG_MIN / 4, e.Khi = -sum - delta45;
                        eqs.push_back(std::move(e));
                        ++nthermo;
                    }
                }
        }
        if (tcache.size() > 64) tcache.clear();
        tit = tcache.emplace(gkey, std::move(eqs)).first;
    }
    std::vector<MEq> EQ = it->second;
    EQ.insert(EQ.end(), tit->second.begin(), tit->second.end());
    if (EQ.empty()) return;
    const int l = EQ[0].layer;
    const int a0 = p.aux_u + l * p.N;
    if (a0 >= (int)p.aux_values.size() || !joint_ok(a0)) return;
    const auto& vv = p.aux_values[a0];
    if (vv.size() != 2 || std::find(vv.begin(), vv.end(), 1) == vv.end()) return;  // a multiplier {1, k}
    const int vk = vv[0] == 1 ? 1 : 0;  // the modified value's index
    const long long kmul = vv[vk] - 1;    // the extra per digit
    // the count rules: exactly one modified cell per house; doubled digits distinct when each digit is modified once
    std::vector<const JHouse*> one;
    int digit_houses = 0;
    for (const JHouse& h : jhouses_of(p)) {
        if (h.layer != l || h.vmask != (1u << vk)) continue;
        if (h.digit) ++digit_houses;
        else one.push_back(&h);
    }
    const bool distinct = digit_houses >= p.D;
    auto avar = [&](int c) { return p.aux_u + l * p.N + c; };
    auto can_mod = [&](int c, int d) { return joint_live(avar(c), d, vk); };
    auto modifiable = [&](int c) {
        for (int d = 1; d <= p.D; ++d)
            if (can_mod(c, d)) return true;
        return false;
    };
    auto decided_mod = [&](int c) {  // its layer is the modified value
        for (int i = aux_off[avar(c)]; i < aux_off[avar(c) + 1]; ++i)
            if (auxf[i] != (i - aux_off[avar(c)] == vk)) return false;
        return true;
    };
    struct Side { long long elo, ehi; int mlo, mhi; uint32_t avail; };
    auto side_of = [&](const std::vector<int>& S) {
        Side r{0, 0, 0, 0, 0};
        std::vector<int> cand_cells;
        for (int c : S)
            if (modifiable(c)) {
                cand_cells.push_back(c);
                for (int d = 1; d <= p.D; ++d)
                    if (can_mod(c, d)) r.avail |= bit(d);
            }
        // most modified cells: at most one per count house (small search)
        std::vector<char> pick(cand_cells.size(), 0);
        std::function<void(size_t, int)> dfs = [&](size_t j, int n) {
            if (n + (int)(cand_cells.size() - j) <= r.mhi) return;
            if (j == cand_cells.size()) { r.mhi = std::max(r.mhi, n); return; }
            bool ok = true;  // cell j with the picks so far: no count house twice
            for (const JHouse* h : one) {
                if (!std::binary_search(h->cells.begin(), h->cells.end(), cand_cells[j])) continue;
                for (size_t t = 0; t < j && ok; ++t)
                    if (pick[t] && std::binary_search(h->cells.begin(), h->cells.end(), cand_cells[t])) ok = false;
            }
            if (ok) { pick[j] = 1; dfs(j + 1, n + 1); pick[j] = 0; }
            if (!decided_mod(cand_cells[j])) dfs(j + 1, n);
        };
        if (cand_cells.size() <= 24) dfs(0, 0);
        else r.mhi = (int)cand_cells.size();
        // fewest: count houses whose possible modified cells all lie in S, pairwise disjoint -> one each
        std::vector<const JHouse*> inside;
        for (const JHouse* h : one) {
            bool all = true, any = false;
            for (int c : h->cells)
                if (modifiable(c)) {
                    any = true;
                    all &= std::find(S.begin(), S.end(), c) != S.end();
                }
            if (any && all) inside.push_back(h);
        }
        std::function<void(size_t, std::vector<const JHouse*>&)> best = [&](size_t j, std::vector<const JHouse*>& cur) {
            r.mlo = std::max(r.mlo, (int)cur.size());
            for (size_t t = j; t < inside.size(); ++t) {
                bool disj = true;
                for (const JHouse* x : cur)
                    for (int c : x->cells)
                        if (std::binary_search(inside[t]->cells.begin(), inside[t]->cells.end(), c)) disj = false;
                if (!disj) continue;
                cur.push_back(inside[t]);
                best(t + 1, cur);
                cur.pop_back();
            }
        };
        std::vector<const JHouse*> cur;
        if (inside.size() <= 12) best(0, cur);
        // E's range from the counts and the digits
        auto sum_k = [&](int m, bool low) {  // m modified digits, distinct if so
            long long sm = 0;
            int n = 0;
            if (!distinct) {
                const int d = low ? __builtin_ctz(r.avail) + 1 : 32 - __builtin_clz(r.avail);
                return (long long)m * d;
            }
            for (int t = 0; t < p.D && n < m; ++t) {
                const int d = low ? t + 1 : p.D - t;
                if (r.avail & bit(d)) sm += d, ++n;
            }
            return n < m ? -1 : sm;
        };
        if (!r.avail) { r.mhi = 0; return r; }
        r.elo = kmul * sum_k(r.mlo, true);
        long long hi = -1;
        for (int m = r.mhi; m >= r.mlo && hi < 0; --m) hi = kmul * sum_k(m, false);
        r.ehi = hi < 0 ? 0 : hi;
        return r;
    };
    for (const MEq& e : EQ) {
        if (deadline_passed()) return;
        Side A = side_of(e.la), B = side_of(e.lb);
        // every house of both groups a count house (one modified cell each): count(B) = count(A) + |gb| - |ga|; keep
        // the counts that pair up with an extra fitting E(B) - E(A) = K
        auto counted = [&](const std::vector<int>& g) {
            for (int gi : g) {
                std::vector<int> cs = p.groups[gi].cells;
                std::sort(cs.begin(), cs.end());
                bool hit = false;
                for (const JHouse* h : one) hit |= h->cells == cs;
                if (!hit) return false;
            }
            return true;
        };
        long long xlo = LLONG_MIN / 4, xhi = LLONG_MAX / 4;  // E(A)'s range from the counts that pair up
        if (e.exact && counted(e.ga) && counted(e.gb)) {
            const int delta = (int)e.gb.size() - (int)e.ga.size();
            auto erange = [&](const Side& s, int m, long long& lo, long long& hi) {
                if (m == 0) return lo = hi = 0, true;
                if (!s.avail) return false;
                long long a = 0, b = 0;
                int n1 = 0, n2 = 0;
                for (int t = 1; t <= p.D; ++t)
                    if (s.avail & bit(t)) {
                        if (n1 < m) a += t, ++n1;
                    }
                for (int t = p.D; t >= 1; --t)
                    if (s.avail & bit(t)) {
                        if (n2 < m) b += t, ++n2;
                    }
                if (!distinct) {
                    a = (long long)m * (__builtin_ctz(s.avail) + 1), b = (long long)m * (32 - __builtin_clz(s.avail));
                } else if (n1 < m) {
                    return false;
                }
                lo = kmul * a, hi = kmul * b;
                return true;
            };
            int amin = 1 << 20, amax = -1;
            long long ealo = LLONG_MAX, eahi = LLONG_MIN;
            for (int ma = A.mlo; ma <= A.mhi; ++ma) {
                const int mb = ma + delta;
                if (mb < B.mlo || mb > B.mhi) continue;
                long long al, ah, bl, bh;
                if (!erange(A, ma, al, ah) || !erange(B, mb, bl, bh)) continue;
                const long long lo = std::max(al, bl - e.Khi), hi = std::min(ah, bh - e.Klo);
                if (lo > hi) continue;
                amin = std::min(amin, ma), amax = std::max(amax, ma);
                ealo = std::min(ealo, lo), eahi = std::max(eahi, hi);
            }
            if (amax < 0) continue;  // no count fits: a contradiction others show
            A.mlo = amin, A.mhi = amax, B.mlo = amin + delta, B.mhi = amax + delta;
            xlo = ealo, xhi = eahi;
        }
        // E(B) - E(A) in [Klo, Khi]
        const long long alo = std::max({A.elo, B.elo - e.Khi, xlo}), ahi = std::min({A.ehi, B.ehi - e.Klo, xhi});
        const long long blo = std::max({B.elo, A.elo + e.Klo, xlo + e.Klo}), bhi = std::min({B.ehi, A.ehi + e.Khi, xhi + e.Khi});
        if (alo > ahi || blo > bhi) continue;  // a contradiction: others show it
        // the counts the extra ranges allow: m modified cells (distinct digits) make kmul * (1 + .. ) to kmul * (9 + ..)
        for (auto [sd, lo, hi] : {std::make_tuple(&A, alo, ahi), std::make_tuple(&B, blo, bhi)}) {
            auto ext = [&](int m, bool low) {
                long long s = 0;
                int n = 0;
                for (int k2 = 0; k2 < p.D && n < m; ++k2) {
                    const int d = low ? k2 + 1 : p.D - k2;
                    if (sd->avail & bit(d)) s += d, ++n;
                }
                return n < m ? -1 : kmul * s;
            };
            if (!distinct) continue;
            while (sd->mlo < sd->mhi && ext(sd->mlo, false) >= 0 && ext(sd->mlo, false) < lo) ++sd->mlo;
            while (sd->mhi > sd->mlo && (ext(sd->mhi, true) < 0 || ext(sd->mhi, true) > hi)) --sd->mhi;
        }
        for (auto [S, lo, hi] : {std::make_tuple(&e.la, alo, ahi), std::make_tuple(&e.lb, blo, bhi)}) {
            auto f = g_side_extra.emplace(*S, std::make_pair(lo, hi)).first;
            f->second.first = std::max(f->second.first, lo), f->second.second = std::min(f->second.second, hi);
        }
        std::vector<std::tuple<int, int, int>> kills;  // (aux variable, digit, value index)
        auto narrow_side = [&](const std::vector<int>& S, const Side& sd, long long lo, long long hi) {
            if (lo <= sd.elo && hi >= sd.ehi) return;
            for (int d = 1; d <= p.D; ++d) {
                if (!(sd.avail & bit(d))) continue;
                bool fits = false;  // d modified, with m - 1 others (distinct), some m in the count range
                for (int m = std::max(1, sd.mlo); m <= sd.mhi && !fits; ++m) {
                    long long mn = d, mx = d;
                    int n1 = 0, n2 = 0;
                    for (int t = 1; t <= p.D && n1 < m - 1; ++t)
                        if ((sd.avail & bit(t)) && (!distinct || t != d)) mn += t, ++n1;
                    for (int t = p.D; t >= 1 && n2 < m - 1; --t)
                        if ((sd.avail & bit(t)) && (!distinct || t != d)) mx += t, ++n2;
                    if (n1 < m - 1) continue;
                    if (!distinct) mn = (long long)d + (long long)(m - 1) * (__builtin_ctz(sd.avail) + 1),
                                   mx = (long long)d + (long long)(m - 1) * (32 - __builtin_clz(sd.avail));
                    fits = kmul * mn <= hi && kmul * mx >= lo;
                }
                if (fits) continue;
                for (int c : S)
                    if (can_mod(c, d)) kills.emplace_back(avar(c), d, vk);
            }
        };
        narrow_side(e.la, A, alo, ahi);
        narrow_side(e.lb, B, blo, bhi);
        // 7426: a side's count of modified cells against the count houses (a fish over the side): it needs m and m
        // disjoint count houses hold all its modifiable cells -> each of them has its modified cell in the side; it
        // takes at most m and holds m disjoint count houses whole -> its other cells are plain ("exactly two doublers
        // in the 16 cells")
        for (auto [S, sd] : {std::make_pair(&e.la, A), std::make_pair(&e.lb, B)}) {
            std::vector<int> mc;  // the side's modifiable cells
            for (int c : *S)
                if (modifiable(c)) mc.push_back(c);
            if (mc.empty()) continue;
            auto in_side = [&](int c) { return std::find(S->begin(), S->end(), c) != S->end(); };
            auto house_has = [](const JHouse* h, int c) { return std::binary_search(h->cells.begin(), h->cells.end(), c); };
            std::vector<const JHouse*> touch, whole;  // count houses meeting the side's modifiable cells / inside it
            for (const JHouse* h : one) {
                bool meets = false, all = true, any = false;
                for (int c : h->cells)
                    if (modifiable(c)) {
                        any = true;
                        if (in_side(c)) meets = true;
                        else all = false;
                    }
                if (meets) touch.push_back(h);
                if (any && all) whole.push_back(h);
            }
            auto disjoint = [&](const std::vector<const JHouse*>& hs) {
                for (size_t x = 0; x < hs.size(); ++x)
                    for (size_t y = x + 1; y < hs.size(); ++y)
                        for (int c : hs[x]->cells)
                            if (house_has(hs[y], c)) return false;
                return true;
            };
            std::vector<std::pair<int, int>> aout;  // (layer variable, value index)
            std::vector<int> pat = *S;
            // lower bound: mlo houses covering every modifiable cell of the side
            if (sd.mlo >= 1 && sd.mlo <= 3 && touch.size() <= 24) {
                std::vector<const JHouse*> cur;
                std::function<bool(size_t)> pick = [&](size_t j) -> bool {
                    if ((int)cur.size() == sd.mlo) {
                        for (int c : mc) {
                            bool cov = false;
                            for (const JHouse* h : cur) cov |= house_has(h, c);
                            if (!cov) return false;
                        }
                        return disjoint(cur);
                    }
                    for (size_t t = j; t < touch.size(); ++t) {
                        cur.push_back(touch[t]);
                        if (pick(t + 1)) return true;
                        cur.pop_back();
                    }
                    return false;
                };
                if (pick(0))
                    for (const JHouse* h : cur)
                        for (int c : h->cells)
                            if (!in_side(c) && modifiable(c)) aout.emplace_back(avar(c), vk);
            }
            // upper bound: mhi whole houses inside the side
            if (sd.mhi >= 1 && sd.mhi <= 3 && whole.size() <= 24) {
                std::vector<const JHouse*> cur;
                std::function<bool(size_t)> pick = [&](size_t j) -> bool {
                    if ((int)cur.size() == sd.mhi) return disjoint(cur);
                    for (size_t t = j; t < whole.size(); ++t) {
                        cur.push_back(whole[t]);
                        if (pick(t + 1)) return true;
                        cur.pop_back();
                    }
                    return false;
                };
                if (pick(0))
                    for (int c : mc) {
                        bool in_h = false;
                        for (const JHouse* h : cur) in_h |= house_has(h, c);
                        if (!in_h) aout.emplace_back(avar(c), vk);
                    }
            }
            if (sd.mhi == 0)
                for (int c : mc) aout.emplace_back(avar(c), vk);
            std::sort(aout.begin(), aout.end());
            aout.erase(std::unique(aout.begin(), aout.end()), aout.end());
            std::vector<std::pair<int, int>> live_out;
            for (auto [a, vi] : aout)
                if (auxf[aux_off[a] + vi] && !decided_mod(aux_cell(a))) live_out.emplace_back(a, vi);
            if (live_out.empty()) continue;
            Move& m = new_move(out, AUX_HOUSE, 1.0, (int)live_out.size());
            for (auto [a, vi] : live_out) add_aeff(out, m, AE_AUX, a, vi);
            set_pattern(out, m, pat);
            m.nk = NM_NARY;
            m.code = 7426;
        }
        if (kills.empty()) continue;
        Move& m = new_move(out, AUX_HOUSE, 1.0, (int)kills.size());
        for (auto& [a, d, vi] : kills) add_aeff(out, m, AE_JOINT, a, d * 16 + vi);
        std::vector<int> pc = e.la;
        pc.insert(pc.end(), e.lb.begin(), e.lb.end());
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.code = 7421;
    }
}

// --------------------------------------------------------- BudgetFish --
// an exactly-one layer house X (digit d, values V: "one copycatted 9 in the grid") as a budget for complete houses:
// in house G, a FREE place for d can hold it with a value outside V; a COSTLY place (in X) holds d only with a value in
// V, so it spends X's one literal. G with no free place puts X's literal among its costly places; two houses whose
// free places pairwise exclude each other (disjoint, every pair sharing a house: "the two centers share a column")
// cannot both stay free, so X's literal is among their costly places. Either way X's other literals go (every zipper
// box but one keeps its 9 at the center). Code 7430.
void Solver::budget_fish(MoveBuf& out) {
    if (!has_aux() || p.aux_layers <= 0 || jx.size() != p.aux_values.size() || p.D > 9) return;
    const std::vector<JHouse>& H = jhouses_of(p);
    auto share_house = [&](int a, int b) {
        for (int g : p.groups_of[a])
            if (p.groups[g].complete &&
                std::find(p.groups[g].cells.begin(), p.groups[g].cells.end(), b) != p.groups[g].cells.end())
                return true;
        return false;
    };
    std::set<std::tuple<int, int, int>> said;
    for (const JHouse& X : H) {
        if (X.pmask.any() || deadline_passed()) continue;
        const std::vector<int> digits = X.digit ? std::vector<int>{X.digit} : std::vector<int>{};
        for (int d : digits) {
            auto avar = [&](int c) { return p.aux_u + X.layer * p.N + c; };
            auto in_X = [&](int c) { return std::binary_search(X.cells.begin(), X.cells.end(), c); };
            // per complete house: free and costly places of d (a house with d placed is done)
            struct HG { std::vector<int> fr, co; };
            std::vector<HG> hg;
            for (int gi : p.houses) {
                const Group& G = p.groups[gi];
                if ((int)G.cells.size() != p.D) continue;
                HG h;
                bool placed = false;
                for (int c : G.cells) {
                    if (vals[c] == d) placed = true;
                    if (vals[c] ? vals[c] != d : !(cand[c] & bit(d))) continue;
                    const int a = avar(c);
                    bool free = !in_X(c) || !joint_ok(a), costly = false;
                    if (!free)
                        for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi) {
                            if (!joint_live(a, d, vi)) continue;
                            if ((X.vmask >> vi) & 1) costly = true;
                            else free = true;
                        }
                    if (free) h.fr.push_back(c);
                    else if (costly) h.co.push_back(c);
                }
                if (!placed && !h.co.empty()) hg.push_back(std::move(h));
            }
            auto claim = [&](const std::vector<int>& keep, const std::vector<int>& pat) {  // X's literal is in keep
                std::vector<std::tuple<int, int, int>> kills;
                for (int c : X.cells) {
                    if (std::find(keep.begin(), keep.end(), c) != keep.end()) continue;
                    const int a = avar(c);
                    if (!joint_ok(a)) continue;
                    for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi)
                        if (((X.vmask >> vi) & 1) && joint_live(a, d, vi) && said.insert({a, d, vi}).second)
                            kills.emplace_back(a, d, vi);
                }
                if (kills.empty()) return;
                std::vector<std::pair<int, int>> dout;  // a cell left without d
                for (auto& [a, dd, vi] : kills) {
                    const int c = aux_cell(a);
                    bool any = false;
                    for (int v2 = 0; v2 < (int)p.aux_values[a].size() && !any; ++v2)
                        any = joint_live(a, d, v2) && !said.count({a, d, v2});
                    if (!any && !vals[c] && (cand[c] & bit(d))) dout.emplace_back(c, d);
                }
                Move& m = new_move(out, LAYER_COUNT, 1.0, (int)(kills.size() + dout.size()));
                for (auto& e : dout) add_el(out, m, e.first, e.second);
                for (auto& [a, dd, vi] : kills) add_aeff(out, m, AE_JOINT, a, dd * 16 + vi);
                set_pattern(out, m, pat);
                m.code = 7430;
            };
            for (const HG& h : hg)
                if (h.fr.empty()) claim(h.co, h.co);
            for (size_t i = 0; i < hg.size(); ++i)
                for (size_t j = i + 1; j < hg.size(); ++j) {
                    const HG &A = hg[i], &B = hg[j];
                    if (A.fr.empty() || B.fr.empty() || A.fr.size() > 3 || B.fr.size() > 3) continue;
                    bool excl = true;
                    for (int a : A.fr)
                        for (int b : B.fr) excl &= a != b && share_house(a, b);
                    if (!excl) continue;
                    std::vector<int> keep = A.co;
                    keep.insert(keep.end(), B.co.begin(), B.co.end());
                    std::vector<int> pat = keep;
                    pat.insert(pat.end(), A.fr.begin(), A.fr.end());
                    pat.insert(pat.end(), B.fr.begin(), B.fr.end());
                    claim(keep, pat);
                }
        }
    }
}

// ---------------------------------------------------------- EqualSums --
// rules "sum(f(x) for x in A) == sum(f(x) for x in B)" (f the digit or a value x * L(x)): the segments they join (a
// region-sum line's per-box stretches) share one total. Per segment, the exact set of sums it can make (a DP over
// digits used -- distinct when the segment lies in one house -- and the running sum); the class's totals are the
// intersection; a (cell, digit, value) option on no filling reaching a shared total goes. Code 7429.
namespace {
// a value term of one variable: "x", "x + c", "x * L(x)", "(x + c) * L(x)" (c a constant; is_var tells the variable);
// with add: also "x + L(x)" / "x + c + L(x)" (*add set: the value is the digit plus the layer's value)
bool maffine(const ExprNode& b, const std::function<bool(const ExprNode&)>& is_var, long long& layer, long long& off,
             bool* add = nullptr) {
    if (add) *add = false;
    auto lin = [&](const ExprNode& x, long long& c) {  // x or x +- const
        if (is_var(x)) return c = 0, true;
        long long k;
        if ((x.op == X_ADD || x.op == X_SUB) && x.kids.size() == 2 && is_var(x.kids[0]) && jconst(x.kids[1], k))
            return c = x.op == X_ADD ? k : -k, true;
        if (x.op == X_ADD && x.kids.size() == 2 && is_var(x.kids[1]) && jconst(x.kids[0], k)) return c = k, true;
        return false;
    };
    if (lin(b, off)) return layer = -1, true;
    if (b.op == X_MUL && b.kids.size() == 2)
        for (int t = 0; t < 2; ++t) {
            const ExprNode& x = b.kids[t];
            const ExprNode& l = b.kids[1 - t];
            if (l.op == X_AUXCELL && l.kids.size() == 1 && is_var(l.kids[0]) && lin(x, off)) return layer = l.v, true;
        }
    if (add && b.op == X_ADD && b.kids.size() == 2)
        for (int t = 0; t < 2; ++t) {
            const ExprNode& x = b.kids[t];
            const ExprNode& l = b.kids[1 - t];
            if (l.op == X_AUXCELL && l.kids.size() == 1 && is_var(l.kids[0]) && lin(x, off)) return *add = true, layer = l.v, true;
        }
    return false;
}
// a term f(x) of no affine form read cell by cell: the comprehension body, its slot, the rule variables it runs over
struct MGen {
    const ExprProgram* prog = nullptr;
    const ExprNode* body = nullptr;
    int slot = -1;
    std::vector<int> vars;
    uint64_t hash = 0;  // the body's shape (slot numbers left out): segments join only with the same f
};
// f reads only its own cell x (its digit, row / column, one layer at x): -> that layer (-1: none); false otherwise
bool mgen_ok(const ExprNode& e, int slot, long long& layer, uint64_t& h) {
    h = h * 1000003u + (uint64_t)e.op * 31u + (e.op == X_SLOT ? 0u : (uint64_t)e.v);
    if (e.op == X_CELL || e.op == X_CELLS || e.op == X_AUX || e.op == X_COMP || e.op == X_LET || e.op == X_LETFN ||
        e.op == X_LAMBDA)
        return false;
    if (e.op == X_SLOT) return e.v == slot;
    if (e.op == X_AUXCELL) {
        if (e.kids.size() != 1 || e.kids[0].op != X_SLOT || e.kids[0].v != slot || (layer >= 0 && layer != e.v)) return false;
        layer = e.v;
        return true;
    }
    for (const ExprNode& k : e.kids)
        if (!mgen_ok(k, slot, layer, h)) return false;
    return true;
}
// a side "sum(f(x) for x in L)" or "f(o)" for one named cell o, f affine as above -> cells, layer (-1: digits), offset;
// with gen: any f reading only its own cell (gen->body set; the values then come from the expression, per option)
bool msum(const ExprProgram& P, const ExprNode& sm, long long& layer, long long& off, std::vector<int>& cells,
          bool* add = nullptr, MGen* gen = nullptr) {
    if (gen) *gen = MGen();
    cells.clear();
    auto cell_of = [&](const ExprNode& x) -> int {
        int var = -1;
        if (x.op == X_CELL) var = (int)x.v;
        else if (x.op == X_CELLS && x.v >= 0 && x.v < (long long)P.lists.size() && P.lists[x.v].items.empty())
            var = P.lists[x.v].var;
        return var >= 0 && var < (int)P.gcell.size() ? P.gcell[var] : -1;
    };
    if (sm.op == X_CALL && sm.v == 0 /* SUM */ && sm.kids.size() == 1 && sm.kids[0].op == X_COMP) {
        const ExprNode& c = sm.kids[0];
        if (c.kids.size() != 3 || c.kids[2].op != X_NONE || c.kids[0].op != X_CELLS || c.kids[0].v < 0 ||
            c.kids[0].v >= (long long)P.lists.size())
            return false;
        std::vector<int> vars;
        jcells(P.lists[c.kids[0].v], vars);
        if (!maffine(c.kids[1], [&](const ExprNode& x) { return x.op == X_SLOT && x.v == c.v; }, layer, off, add)) {
            if (!gen) return false;
            layer = -1, off = 0;
            uint64_t h = 1469598103934665603ull;
            if (!mgen_ok(c.kids[1], (int)c.v, layer, h)) return false;
            gen->prog = &P, gen->body = &c.kids[1], gen->slot = (int)c.v, gen->vars = vars, gen->hash = h;
        }
        for (int y : vars)
            if (y >= 0 && y < (int)P.gcell.size()) cells.push_back(P.gcell[y]);
        return !cells.empty();
    }
    int one = -1;  // f(o): every variable reference is the same cell
    std::function<void(const ExprNode&)> find = [&](const ExprNode& x) {
        const int c = cell_of(x);
        if (c >= 0) { one = one == -1 || one == c ? c : -2; return; }
        for (const ExprNode& k : x.kids) find(k);
    };
    find(sm);
    if (one < 0) return false;
    if (!maffine(sm, [&](const ExprNode& x) { return cell_of(x) == one; }, layer, off, add)) return false;
    cells.push_back(one);
    return true;
}
}  // namespace

void Solver::equal_sums(MoveBuf& out) {
    if (p.D > 9 || !has_aux() || jx.size() != p.aux_values.size()) return;
    struct Cls {
        int layer;
        bool add = false, gen = false;
        long long off = 0, fixed = -1;
        std::vector<std::vector<int>> segs;
        std::vector<MGen> g;  // gen: per segment its term (cells in segs order <- g.vars via the rule's gcell)
    };
    // segment layer ids: + ADDK for additive values (x + L(x)), + GENK for terms read by evaluation; kinds never join
    constexpr int ADDK = 1000, GENK = 2000;
    static thread_local std::unordered_map<uint64_t, std::vector<Cls>> cache;
    auto it = cache.find(p.uid);
    if (it == cache.end()) {
        std::map<std::vector<int>, int> id;  // segment (sorted cells) -> index
        std::vector<std::vector<int>> segs;
        std::vector<int> seg_layer, par;
        std::map<int, long long> seg_off;    // the value's offset c in (x + c) * L(x)
        std::map<int, long long> seg_fixed;  // "sum(...) == constant": the segment's total
        std::map<int, MGen> seg_gen;         // terms read by evaluation (the first rule's; same shape to join)
        auto get = [&](std::vector<int> cs, int layer) {
            std::sort(cs.begin(), cs.end());
            auto f = id.find(cs);
            if (f != id.end()) return f->second;
            const int i = (int)segs.size();
            id[cs] = i, segs.push_back(cs), seg_layer.push_back(layer), par.push_back(i);
            return i;
        };
        std::function<int(int)> root = [&](int x) { return par[x] == x ? x : par[x] = root(par[x]); };
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr) continue;
                std::vector<const ExprNode*> eqs;  // the root, or the equations of a conjunction
                std::function<void(const ExprNode&)> conj = [&](const ExprNode& x) {
                    if (x.op == X_AND) for (const ExprNode& y : x.kids) conj(y);
                    else if (x.op == X_EQ && x.kids.size() == 2) eqs.push_back(&x);
                    else eqs.push_back(nullptr);
                };
                conj(k.expr->root);
                for (const ExprNode* r : eqs) {
                    if (!r) continue;
                    long long la, lb, oa, ob;
                    bool aa = false, ab = false;
                    MGen ga, gb;
                    std::vector<int> ca, cb;
                    // a generic segment: its id carries the kind; the same cells read by another shape do not join
                    auto gen_ok = [&](int s, const MGen& g) {
                        if (!g.body) return true;
                        auto f = seg_gen.find(s);
                        if (f == seg_gen.end()) return seg_gen[s] = g, true;
                        return f->second.hash == g.hash;
                    };
                    for (int s2 = 0; s2 < 2; ++s2) {  // a segment with a constant total (a little killer on values)
                        long long tot;
                        if (!jconst(r->kids[1 - s2], tot) || !msum(*k.expr, r->kids[s2], la, oa, ca, &aa, &ga) || ca.size() < 2)
                            continue;
                        if (la >= 0 && (la >= p.aux_layers || !has_aux())) continue;
                        if (aa) la += ADDK;
                        if (ga.body) la += GENK;
                        const int a = get(ca, (int)la);
                        if (!gen_ok(a, ga)) continue;
                        if ((seg_off.count(a) && seg_off[a] != oa) || seg_layer[a] != (int)la ||
                            (seg_fixed.count(a) && seg_fixed[a] != tot))
                            continue;
                        seg_off[a] = oa, seg_fixed[a] = tot;
                    }
                    if (!msum(*k.expr, r->kids[0], la, oa, ca, &aa, &ga) || !msum(*k.expr, r->kids[1], lb, ob, cb, &ab, &gb) ||
                        la != lb || aa != ab || oa != ob || (ca.size() == 1 && cb.size() == 1) || !ga.body != !gb.body ||
                        (ga.body && ga.hash != gb.hash))
                        continue;
                    if (la >= 0 && (la >= p.aux_layers || !has_aux())) continue;
                    if (aa) la += ADDK, lb += ADDK;
                    if (ga.body) la += GENK, lb += GENK;
                    const int a = get(ca, (int)la), b = get(cb, (int)lb);
                    if (!gen_ok(a, ga) || !gen_ok(b, gb)) continue;
                    bool clash = false;  // a segment already read with another offset / layer: not one class
                    for (int s2 : {a, b}) clash |= (seg_off.count(s2) && seg_off[s2] != oa) || seg_layer[s2] != (int)la;
                    if (clash) continue;
                    seg_off[a] = seg_off[b] = oa;
                    par[root(a)] = root(b);
                }
            }
        std::map<int, Cls> by;
        for (int i = 0; i < (int)segs.size(); ++i) {
            Cls& c = by[root(i)];
            c.gen = seg_layer[i] >= GENK - 1;
            c.add = !c.gen && seg_layer[i] >= ADDK - 1;
            c.layer = seg_layer[i] - (c.gen ? GENK : c.add ? ADDK : 0), c.off = seg_off.count(i) ? seg_off[i] : 0;
            c.g.push_back(seg_gen.count(i) ? seg_gen[i] : MGen());
            if (seg_fixed.count(i)) c.fixed = c.fixed >= 0 && c.fixed != seg_fixed[i] ? -2 : seg_fixed[i];
            c.segs.push_back(segs[i]);
        }
        std::vector<Cls> cls;
        for (auto& [r, c] : by)
            if ((c.segs.size() >= 2 || c.fixed >= 0) && c.fixed != -2) cls.push_back(std::move(c));
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(cls)).first;
    }
    // a class's reading depends only on its cells' options (digit, value, joint pairs): kept per that state
    struct EqRes { std::vector<std::pair<int, int>> dout, aout; std::vector<std::tuple<int, int, int>> jout; std::vector<int> pat; };
    static thread_local std::unordered_map<std::string, EqRes> memo;
    auto emit_res = [&](const EqRes& r) {
        if (r.dout.empty() && r.aout.empty() && r.jout.empty()) return;
        Move& m = new_move(out, EQSUM_VALUES, 1.0, (int)(r.dout.size() + r.aout.size() + r.jout.size()));
        for (auto& e : r.dout) add_el(out, m, e.first, e.second);
        for (auto& e : r.aout) add_aeff(out, m, AE_AUX, e.first, e.second);
        for (auto& [a, d, vi] : r.jout) add_aeff(out, m, AE_JOINT, a, d * 16 + vi);
        set_pattern(out, m, r.pat);
        m.nk = NM_NARY;
        m.code = 7429;
    };
    for (const Cls& cl : it->second) {
        if (deadline_passed()) return;
        std::string key;
        {
            auto put = [&](uint64_t x) { key.append(reinterpret_cast<const char*>(&x), sizeof x); };
            put(p.uid), put((uint64_t)(uintptr_t)&cl);
            for (const auto& sg : cl.segs)
                for (int c : sg) {
                    put(vals[c] ? (1ull << 40 | (uint64_t)vals[c]) : cand[c]);
                    if (cl.layer >= 0) {
                        const int a = p.aux_u + cl.layer * p.N + c;
                        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i) key.push_back(auxf[i] ? '1' : '0');
                        for (int w = 0; w < JW; ++w) put(jword(jx[a], w));
                    }
                }
        }
        if (!memo_off("eqsums")) {
            auto mf = memo.find(key);
            if (mf != memo.end()) {
                emit_res(mf->second);
                continue;
            }
        }
        if (memo.size() > 100000) memo.clear();
        const int S = 1 << p.D;
        int vmax = 1;  // the largest value a cell can take
        // per segment: options per cell, distinctness, reachable sums with supports
        struct SegDP {
            std::vector<int> cells, avar;
            uint32_t uv = 0;  // a layer house holding the segment: its literal counts once (bit 0 of the DP's mask)
            std::vector<std::vector<std::pair<int, int>>> opt;
            std::vector<std::vector<int>> val;  // each option's value
            bool distinct;
            std::vector<char> sums;
            std::vector<char> fin;  // the forward DP's final (mask, literal, sum) states
        };
        std::vector<SegDP> sd(cl.segs.size());
        int top = 0;
        bool bad = false;
        for (size_t s = 0; s < cl.segs.size() && !bad; ++s) {
            SegDP& g = sd[s];
            g.cells = cl.segs[s];
            if (g.cells.size() > (size_t)p.D) { bad = true; break; }
            g.distinct = false;  // one complete house holds them all
            for (int gi : p.groups_of[g.cells[0]]) {
                if (!p.groups[gi].complete) continue;
                bool all = true;
                for (int c : g.cells)
                    all &= std::find(p.groups[gi].cells.begin(), p.groups[gi].cells.end(), c) != p.groups[gi].cells.end();
                g.distinct |= all;
            }
            if (cl.layer >= 0)
                for (const JHouse& h : jhouses_of(p)) {
                    if (h.pmask.any() || h.digit || h.layer != cl.layer) continue;
                    bool all = true;
                    for (int c : g.cells) all &= std::binary_search(h.cells.begin(), h.cells.end(), c);
                    if (all) g.uv |= h.vmask;
                }
            g.avar.assign(g.cells.size(), -1);
            g.opt.resize(g.cells.size());
            g.val.resize(g.cells.size());
            int smax = 0;
            const MGen& mg = cl.g[s];
            std::vector<int> gd, ga;  // generic terms: the rule's digits / values with this cell's filled in
            if (cl.gen) {
                if (!mg.body) { bad = true; break; }
                gd.assign(mg.prog->gcell.size(), 0), ga.assign(p.aux_values.size(), AUX_UNSET);
            }
            for (size_t i = 0; i < g.cells.size(); ++i) {
                const int c = g.cells[i];
                if (cl.layer >= 0) g.avar[i] = p.aux_u + cl.layer * p.N + c;
                int var = -1;  // generic: the rule variable at this cell
                if (cl.gen)
                    for (int y : mg.vars)
                        if (y >= 0 && y < (int)mg.prog->gcell.size() && mg.prog->gcell[y] == c) var = y;
                if (cl.gen && var < 0) { bad = true; break; }
                auto gv = [&](int d, int vi, int& v) {  // the term's value at this option
                    gd[var] = d;
                    if (vi >= 0) ga[g.avar[i]] = p.aux_values[g.avar[i]][vi];
                    long long x = 0;
                    const bool ok = expr_slot_value(*mg.prog, *mg.body, mg.slot, var, gd.data(), ga.data(), x);
                    if (vi >= 0) ga[g.avar[i]] = AUX_UNSET;
                    v = (int)x;
                    return ok && x >= 0 && x < 400;
                };
                int m = 0;
                for (int d = 1; d <= p.D; ++d) {
                    if (vals[c] ? vals[c] != d : !(cand[c] & bit(d))) continue;
                    if (d + cl.off < 0) { bad = true; break; }  // (sums of negatives: not read)
                    if (g.avar[i] < 0) {
                        int v = d + (int)cl.off;
                        if (cl.gen && !gv(d, -1, v)) { bad = true; break; }
                        g.opt[i].push_back({d, -1}), g.val[i].push_back(v), m = std::max(m, v);
                        continue;
                    }
                    const int a = g.avar[i];
                    for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi) {
                        const int w = p.aux_values[a][vi];
                        int v = cl.add ? d + (int)cl.off + w : (d + (int)cl.off) * w;
                        if (cl.gen ? !gv(d, vi, v) : cl.add ? v < 0 : w < 0) { bad = true; break; }
                        if (auxf[aux_off[a] + vi] && (!joint_ok(a) || joint_live(a, d, vi)))
                            g.opt[i].push_back({d, vi}), g.val[i].push_back(v), m = std::max<int>(m, v);
                    }
                }
                if (g.opt[i].empty()) bad = true;
                smax += m;
            }
            top = std::max(top, smax);
        }
        if (bad || top > 400) {
            memo[key] = EqRes();
            continue;
        }
        (void)vmax;
        auto value = [&](const SegDP& g, size_t i, int o) {
            return g.val[i][o];
        };
        // reachable sums per segment (forward DP over (mask, sum))
        const int T = top + 1;
        std::vector<char> common(T, cl.fixed >= 0 ? 0 : 1);
        if (cl.fixed >= 0 && cl.fixed < T) common[cl.fixed] = 1;
        for (SegDP& g : sd) {
            const int M = (g.distinct ? S : 1) * 2;  // digits used x (the house literal used)
            std::vector<char> cur((size_t)M * T, 0), nxt;
            cur[0] = 1;
            for (size_t i = 0; i < g.cells.size(); ++i) {
                nxt.assign(cur.size(), 0);
                for (int m = 0; m < M; ++m)
                    for (int s = 0; s < T; ++s) {
                        if (!cur[(size_t)m * T + s]) continue;
                        for (size_t o = 0; o < g.opt[i].size(); ++o) {
                            const int d = g.opt[i][o].first;
                            if (g.distinct && ((m >> 1) >> (d - 1) & 1)) continue;
                            const int lit = g.opt[i][o].second >= 0 && ((g.uv >> g.opt[i][o].second) & 1);
                            if (lit && (m & 1)) continue;
                            const int s2 = s + value(g, i, (int)o);
                            if (s2 >= T) continue;
                            nxt[(size_t)((g.distinct ? ((m >> 1) | 1 << (d - 1)) : 0) * 2 + ((m & 1) | lit)) * T + s2] = 1;
                        }
                    }
                cur.swap(nxt);
            }
            g.sums.assign(T, 0);
            for (int m = 0; m < M; ++m)
                for (int s = 0; s < T; ++s)
                    if (cur[(size_t)m * T + s]) g.sums[s] = 1;
            for (int s = 0; s < T; ++s) common[s] &= g.sums[s];
            g.fin.swap(cur);
        }
        // two segments in one complete house: a shared total needs fillings on disjoint digits ("the 3- and 4-cell
        // segments in box 7 hold seven different digits: 2N >= 28 - 1")
        for (size_t a = 0; a < sd.size(); ++a)
            for (size_t b = a + 1; b < sd.size(); ++b) {
                if (!sd[a].distinct || !sd[b].distinct) continue;
                bool one = false;
                for (int gi : p.groups_of[sd[a].cells[0]]) {
                    if (!p.groups[gi].complete) continue;
                    const auto& H = p.groups[gi].cells;
                    bool all = true;
                    for (const SegDP* g : {&sd[a], &sd[b]})
                        for (int c : g->cells) all &= std::find(H.begin(), H.end(), c) != H.end();
                    one |= all;
                }
                if (!one) continue;
                std::vector<char> hb(S);
                for (int s = 0; s < T; ++s) {
                    if (!common[s]) continue;
                    std::fill(hb.begin(), hb.end(), 0);
                    for (int m = 0; m < 2 * S; ++m)
                        if (sd[b].fin[(size_t)m * T + s]) hb[m >> 1] = 1;
                    for (int d = 0; d < p.D; ++d)  // hb[x]: some b-mask inside x
                        for (int x = 0; x < S; ++x)
                            if (x >> d & 1) hb[x] |= hb[x ^ (1 << d)];
                    bool ok = false;
                    for (int m = 0; m < 2 * S && !ok; ++m)
                        if (sd[a].fin[(size_t)m * T + s]) ok = hb[(S - 1) & ~(m >> 1)];
                    common[s] = ok;
                }
            }
        bool anyc = false;
        for (int s = 0; s < T; ++s) anyc |= common[s];
        if (!anyc) {  // no shared total: a contradiction others show
            memo[key] = EqRes();
            continue;
        }
        // per segment: the options on a filling reaching a shared total (backward completion DP, then forward)
        std::vector<std::pair<int, int>> dout, aout;
        std::vector<std::tuple<int, int, int>> jout;
        std::vector<int> pat;
        for (SegDP& g : sd) {
            bool narrows = false;
            for (int s = 0; s < T; ++s) narrows |= g.sums[s] && !common[s];
            if (!narrows) continue;
            const int M = (g.distinct ? S : 1) * 2;  // digits used x (the house literal used)
            const size_t n = g.cells.size();
            std::vector<std::vector<char>> ok(n + 1, std::vector<char>((size_t)M * T, 0));
            for (int m = 0; m < M; ++m)
                for (int s = 0; s < T; ++s) ok[n][(size_t)m * T + s] = common[s];
            for (int i = (int)n - 1; i >= 0; --i)
                for (int m = 0; m < M; ++m)
                    for (int s = 0; s < T; ++s) {
                        char r = 0;
                        for (size_t o = 0; o < g.opt[i].size() && !r; ++o) {
                            const int d = g.opt[i][o].first;
                            if (g.distinct && ((m >> 1) >> (d - 1) & 1)) continue;
                            const int lit = g.opt[i][o].second >= 0 && ((g.uv >> g.opt[i][o].second) & 1);
                            if (lit && (m & 1)) continue;
                            const int s2 = s + value(g, i, (int)o);
                            if (s2 < T) r = ok[i + 1][(size_t)((g.distinct ? ((m >> 1) | 1 << (d - 1)) : 0) * 2 + ((m & 1) | lit)) * T + s2];
                        }
                        ok[i][(size_t)m * T + s] = r;
                    }
            std::vector<char> reach((size_t)M * T, 0), nxt;
            reach[0] = ok[0][0];
            std::vector<std::vector<char>> sup(n);
            for (size_t i = 0; i < n; ++i) {
                sup[i].assign(g.opt[i].size(), 0);
                nxt.assign(reach.size(), 0);
                for (int m = 0; m < M; ++m)
                    for (int s = 0; s < T; ++s) {
                        if (!reach[(size_t)m * T + s]) continue;
                        for (size_t o = 0; o < g.opt[i].size(); ++o) {
                            const int d = g.opt[i][o].first;
                            if (g.distinct && ((m >> 1) >> (d - 1) & 1)) continue;
                            const int lit = g.opt[i][o].second >= 0 && ((g.uv >> g.opt[i][o].second) & 1);
                            if (lit && (m & 1)) continue;
                            const int s2 = s + value(g, i, (int)o);
                            if (s2 >= T) continue;
                            const size_t k2 = (size_t)((g.distinct ? ((m >> 1) | 1 << (d - 1)) : 0) * 2 + ((m & 1) | lit)) * T + s2;
                            if (!ok[i + 1][k2]) continue;
                            sup[i][o] = 1, nxt[k2] = 1;
                        }
                    }
                reach.swap(nxt);
            }
            for (size_t i = 0; i < n; ++i) {
                const int c = g.cells[i];
                uint32_t dsup = 0;
                uint64_t vsup = 0;
                for (size_t o = 0; o < g.opt[i].size(); ++o)
                    if (sup[i][o]) dsup |= bit(g.opt[i][o].first), vsup |= g.opt[i][o].second >= 0 ? 1ull << g.opt[i][o].second : 0;
                for (size_t o = 0; o < g.opt[i].size(); ++o) {
                    if (sup[i][o]) continue;
                    const auto [d, vi] = g.opt[i][o];
                    if (!(dsup & bit(d))) {
                        if (!vals[c] && std::find(dout.begin(), dout.end(), std::make_pair(c, d)) == dout.end()) dout.emplace_back(c, d);
                    } else if (vi >= 0 && !((vsup >> vi) & 1)) {
                        if (std::find(aout.begin(), aout.end(), std::make_pair(g.avar[i], vi)) == aout.end()) aout.emplace_back(g.avar[i], vi);
                    } else if (vi >= 0 && joint_ok(g.avar[i])) {
                        jout.emplace_back(g.avar[i], d, vi);
                    }
                }
            }
            pat.insert(pat.end(), g.cells.begin(), g.cells.end());
        }
        EqRes res{dout, aout, jout, pat};
        if (!deadline_passed()) memo[key] = res;
        emit_res(res);
    }
}

// --------------------------------------------------------- ValueClass --
// class coloring over (digit, layer value) options: an option's class is its VALUE's parity (x * L(x), x + L(x), L(x)
// or x + c, read from the two-cell rules on that layer, which must all agree). A two-cell layered rule whose remaining
// option pairs always take opposite (always the same) classes links its cells; components have two sides. For each
// side assignment and each complete house holding two or more of the component's cells, an exact DP over the house
// (digits all different, its exactly-one layer literal once) with those cells held to their side's class: an
// assignment no house can fill is ruled out, and the component's cells lose the options of that class. Code 7431
// (ClassColour's step; priced as coloring).
namespace {
// a value term of cell variable(s) is_var: L(x) (kind 2), x + L(x) (kind 1), (x + c) * L(x) / x * L(x) (kind 0, off c)
bool mvalue(const ExprNode& e, const std::function<bool(const ExprNode&)>& is_var, int& kind, long long& layer, long long& off) {
    if (e.op == X_AUXCELL && e.kids.size() == 1 && is_var(e.kids[0])) return kind = 2, layer = e.v, off = 0, true;
    if (e.op == X_ADD && e.kids.size() == 2)
        for (int t = 0; t < 2; ++t)
            if (is_var(e.kids[t]) && e.kids[1 - t].op == X_AUXCELL && e.kids[1 - t].kids.size() == 1 &&
                is_var(e.kids[1 - t].kids[0]))
                return kind = 1, layer = e.kids[1 - t].v, off = 0, true;
    long long l2, o2;
    if (maffine(e, is_var, l2, o2) && l2 >= 0) return kind = 0, layer = l2, off = o2, true;
    return false;
}
}  // namespace

void Solver::value_class(MoveBuf& out) {
    if (!has_aux() || p.aux_layers <= 0 || jx.size() != p.aux_values.size() || p.D > 9) return;
    struct Link { const NConstraint* k; };
    struct VC { int layer = -1, kind = 0; long long off = 0; std::vector<const NConstraint*> links; };
    static thread_local std::unordered_map<uint64_t, VC> cache;
    auto it = cache.find(p.uid);
    if (it == cache.end()) {
        VC vc;
        bool ok = true;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr || k.nv() != 2 || k.expr->aux_read.empty()) continue;
                const ExprProgram& P = *k.expr;
                auto cell_of = [&](const ExprNode& x) -> int {
                    int var = -1;
                    if (x.op == X_CELL) var = (int)x.v;
                    else if (x.op == X_CELLS && x.v >= 0 && x.v < (long long)P.lists.size() && P.lists[x.v].items.empty())
                        var = P.lists[x.v].var;
                    return var >= 0 && var < (int)P.gcell.size() ? P.gcell[var] : -1;
                };
                // every term reading a cell must be a value term of one form
                bool rule_ok = true, any = false;
                std::function<void(const ExprNode&)> scan = [&](const ExprNode& e) {
                    if (!rule_ok) return;
                    for (int c : {k.vars[0], k.vars[1]}) {
                        int kind;
                        long long layer, off;
                        if (mvalue(e, [&](const ExprNode& x) { return cell_of(x) == c; }, kind, layer, off)) {
                            if (vc.layer >= 0 && (vc.layer != layer || vc.kind != kind || vc.off != off)) rule_ok = false;
                            vc.layer = (int)layer, vc.kind = kind, vc.off = off, any = true;
                            return;
                        }
                    }
                    if (cell_of(e) >= 0 || e.op == X_AUXCELL) { rule_ok = false; return; }  // a bare digit / layer
                    for (const ExprNode& x : e.kids) scan(x);
                };
                scan(P.root);
                if (!rule_ok) { ok = false; continue; }
                if (any) vc.links.push_back(&k);
            }
        if (!ok || vc.layer < 0 || vc.layer >= p.aux_layers) vc = VC();
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(vc)).first;
    }
    const VC& vc = it->second;
    if (vc.links.empty()) return;
    const int N = p.N, NA = (int)p.aux_values.size();
    auto avar = [&](int c) { return p.aux_u + vc.layer * N + c; };
    auto value = [&](int c, int d, int vi) {
        const long long w = p.aux_values[avar(c)][vi];
        return vc.kind == 2 ? w : vc.kind == 1 ? d + w : (d + vc.off) * w;
    };
    auto cls = [&](int c, int d, int vi) { return (int)(((value(c, d, vi) % 2) + 2) % 2); };  // 1: odd value
    auto opts = [&](int c) {
        std::vector<std::pair<int, int>> o;
        const int a = avar(c);
        if (!joint_ok(a)) return o;
        for (int d = 1; d <= p.D; ++d)
            for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi)
                if (joint_live(a, d, vi)) o.push_back({d, vi});
        return o;
    };
    // links over the remaining option pairs
    std::vector<int> par(N), sd(N);
    for (int c = 0; c < N; ++c) par[c] = c, sd[c] = 0;
    std::function<int(int)> find = [&](int x) {
        if (par[x] == x) return x;
        const int r = find(par[x]);
        sd[x] ^= sd[par[x]];
        return par[x] = r;
    };
    std::vector<int> av(NA, AUX_UNSET);
    int nlink = 0;
    for (const NConstraint* k : vc.links) {
        const int a = k->vars[0], b = k->vars[1];
        const auto oa = opts(a), ob = opts(b);
        if (oa.empty() || ob.empty()) continue;
        int rel = -1;  // 1 opposite, 0 same, -2 mixed
        for (auto [da, va] : oa) {
            for (auto [db, vb] : ob) {
                int dg[2] = {da, db};
                av[avar(a)] = p.aux_values[avar(a)][va], av[avar(b)] = p.aux_values[avar(b)][vb];
                const bool h = expr_holds(*k->expr, dg, nullptr, nullptr, av.data());
                av[avar(a)] = av[avar(b)] = AUX_UNSET;
                if (!h) continue;
                const int r = cls(a, da, va) ^ cls(b, db, vb);
                rel = rel == -1 ? r : rel == r ? r : -2;
            }
            if (rel == -2) break;
        }
        if (rel < 0) continue;
        const int ra = find(a), rb = find(b);
        if (ra == rb) continue;
        par[rb] = ra, sd[rb] = sd[a] ^ sd[b] ^ rel, ++nlink;
    }
    if (!nlink) return;
    std::map<int, std::vector<int>> comp;
    for (int c = 0; c < N; ++c) comp[find(c)].push_back(c);
    const std::vector<JHouse>& JH = jhouses_of(p);
    for (auto& [r, cells] : comp) {
        if (cells.size() < 3 || deadline_passed()) continue;
        bool side_ok[2] = {true, true};
        for (int o = 0; o < 2 && cells.size() >= 3; ++o) {
            // side o: a cell c holds class (sd[c] ^ o)
            auto want = [&](int c) { return sd[c] ^ o; };
            for (int gi : p.houses) {
                const Group& G = p.groups[gi];
                if ((int)G.cells.size() != p.D) continue;
                int inside = 0;
                for (int c : G.cells) inside += find(c) == r;
                if (inside < 2) continue;
                uint32_t uv = 0;  // the house's exactly-one layer literal
                std::vector<int> gs = G.cells;
                std::sort(gs.begin(), gs.end());
                for (const JHouse& h : JH)
                    if (!h.pmask.any() && !h.digit && h.layer == vc.layer && h.cells == gs) uv |= h.vmask;
                // DP over the house: (digits used, literal used)
                std::vector<char> cur(512 * 2, 0), nxt;
                cur[0] = 1;
                bool dead = false;
                for (int c : G.cells) {
                    nxt.assign(cur.size(), 0);
                    const auto oc = opts(c);
                    bool anyo = false;
                    for (int st = 0; st < 1024; ++st) {
                        if (!cur[st]) continue;
                        const int m = st >> 1, u = st & 1;
                        for (auto [d, vi] : oc) {
                            if (m >> (d - 1) & 1) continue;
                            if (find(c) == r && cls(c, d, vi) != want(c)) continue;
                            const int lit = (uv >> vi) & 1;
                            if (lit && u) continue;
                            nxt[((m | 1 << (d - 1)) << 1) | (u | lit)] = 1, anyo = true;
                        }
                    }
                    if (!anyo) { dead = true; break; }
                    cur.swap(nxt);
                }
                if (dead) { side_ok[o] = false; break; }
            }
        }
        if (side_ok[0] == side_ok[1]) continue;  // both possible (nothing) or neither (a contradiction others show)
        const int bad = side_ok[0] ? 1 : 0;  // the impossible assignment: cells lose the class it gave them
        std::vector<std::pair<int, int>> dout, aout;
        std::vector<std::tuple<int, int, int>> jout;
        for (int c : cells) {
            const int a = avar(c), drop = sd[c] ^ bad;
            const auto oc = opts(c);
            uint32_t dsup = 0;
            uint64_t vsup = 0;
            for (auto [d, vi] : oc)
                if (cls(c, d, vi) != drop) dsup |= bit(d), vsup |= 1ull << vi;
            for (auto [d, vi] : oc) {
                if (cls(c, d, vi) != drop) continue;
                if (!(dsup & bit(d))) {
                    if (!vals[c] && std::find(dout.begin(), dout.end(), std::make_pair(c, d)) == dout.end()) dout.emplace_back(c, d);
                } else if (!((vsup >> vi) & 1)) {
                    if (std::find(aout.begin(), aout.end(), std::make_pair(a, vi)) == aout.end()) aout.emplace_back(a, vi);
                } else {
                    jout.emplace_back(a, d, vi);
                }
            }
        }
        if (dout.empty() && aout.empty() && jout.empty()) continue;
        Move& m = new_move(out, CLASS_COLOUR, 1.0, (int)(dout.size() + aout.size() + jout.size()));
        for (auto& e : dout) add_el(out, m, e.first, e.second);
        for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
        for (auto& [a, d, vi] : jout) add_aeff(out, m, AE_JOINT, a, d * 16 + vi);
        set_pattern(out, m, cells);
        m.code = 7431;
    }
}

// ------------------------------------------------------- EqualProducts --
// rules "product(L) == U" sharing one unknown U: the products are equal, so each prime's exponent is. A prime q with
// 2q > D comes only from the digit q, so every line holds the same number k of q's ("a multiple of 5 needs a 5 on
// every line -- but these three lines cannot all have one"). Searched: sets of q-cells, no two in one house, k on
// every line, the placed q's included; a cell in no such set loses q. Code 7427.
void Solver::equal_products(MoveBuf& out) {
    if (!has_aux() || p.D > 9) return;
    static thread_local std::unordered_map<uint64_t, std::vector<std::vector<std::vector<int>>>> cache;  // per U: lines
    auto it = cache.find(p.uid);
    if (it == cache.end()) {
        std::map<long long, std::vector<std::vector<int>>> by_u;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr) continue;
                const ExprNode& r = k.expr->root;
                if (r.op != X_EQ || r.kids.size() != 2) continue;
                for (int s = 0; s < 2; ++s) {
                    const ExprNode& pr = r.kids[s];
                    const ExprNode& u = r.kids[1 - s];
                    if (u.op != X_AUX || pr.op != X_CALL || pr.v != 1 /* PRODUCT */ || pr.kids.size() != 1 ||
                        pr.kids[0].op != X_CELLS || pr.kids[0].v < 0 || pr.kids[0].v >= (long long)k.expr->lists.size())
                        continue;
                    std::vector<int> vars, cells;
                    jcells(k.expr->lists[pr.kids[0].v], vars);
                    for (int y : vars)
                        if (y >= 0 && y < (int)k.expr->gcell.size()) cells.push_back(k.expr->gcell[y]);
                    if (!cells.empty()) by_u[u.v].push_back(cells);
                    break;
                }
            }
        std::vector<std::vector<std::vector<int>>> groups;
        for (auto& [u, lines] : by_u)
            if (lines.size() >= 2) groups.push_back(lines);
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(groups)).first;
    }
    for (const auto& lines : it->second)
        for (int q = 2; q <= p.D; ++q) {
            bool prime = true;
            for (int f = 2; f * f <= q; ++f) prime &= q % f != 0;
            if (!prime || 2 * q <= p.D) continue;
            // the q-cells: placed q's (must be in) and open cells with q (may be)
            std::vector<int> U;
            for (const auto& L : lines)
                for (int c : L)
                    if ((vals[c] == q || (!vals[c] && (cand[c] & bit(q)))) && std::find(U.begin(), U.end(), c) == U.end())
                        U.push_back(c);
            if (U.empty() || U.size() > 48) continue;
            std::vector<std::vector<int>> line_of(U.size());  // per q-cell: the lines it is on (with multiplicity)
            for (size_t li = 0; li < lines.size(); ++li)
                for (int c : lines[li]) {
                    const size_t j = std::find(U.begin(), U.end(), c) - U.begin();
                    if (j < U.size()) line_of[j].push_back((int)li);
                }
            std::vector<int> cnt(lines.size(), 0), rest(lines.size(), 0);  // chosen / still choosable per line
            for (size_t j = 0; j < U.size(); ++j)
                for (int li : line_of[j]) ++rest[li];
            std::vector<char> in(U.size(), 0), can_in(U.size(), 0);
            long budget = 200000;
            bool complete = true;
            int K = 0;
            std::function<void(size_t)> go = [&](size_t j) {
                if (!complete) return;
                if (--budget < 0) { complete = false; return; }
                for (size_t li = 0; li < lines.size(); ++li)
                    if (cnt[li] > K || cnt[li] + rest[li] < K) return;
                if (j == U.size()) {
                    for (size_t t2 = 0; t2 < U.size(); ++t2)
                        if (in[t2]) can_in[t2] = 1;
                    return;
                }
                const int c = U[j];
                for (int li : line_of[j]) --rest[li];
                bool clash = false;  // a chosen q-cell in one of c's houses
                for (size_t t2 = 0; t2 < j && !clash; ++t2)
                    if (in[t2])
                        for (int g : p.groups_of[c])
                            if (p.groups[g].complete &&
                                std::find(p.groups[g].cells.begin(), p.groups[g].cells.end(), U[t2]) != p.groups[g].cells.end()) {
                                clash = true;
                                break;
                            }
                if (!clash) {
                    in[j] = 1;
                    for (int li : line_of[j]) ++cnt[li];
                    go(j + 1);
                    for (int li : line_of[j]) --cnt[li];
                    in[j] = 0;
                }
                if (vals[c] != q) go(j + 1);
                for (int li : line_of[j]) ++rest[li];
            };
            int maxk = 1 << 20;
            for (const auto& L : lines) maxk = std::min<int>(maxk, (int)L.size());
            for (K = 0; K <= maxk && complete; ++K) go(0);
            if (!complete) continue;
            std::vector<std::pair<int, int>> dout;
            for (size_t j = 0; j < U.size(); ++j)
                if (!can_in[j] && !vals[U[j]]) dout.emplace_back(U[j], q);
            if (dout.empty()) continue;
            Move& m = new_move(out, AUX_HOUSE, 1.0, (int)dout.size());
            for (auto& e : dout) add_el(out, m, e.first, e.second);
            std::vector<int> pat;
            for (const auto& L : lines) pat.insert(pat.end(), L.begin(), L.end());
            set_pattern(out, m, pat);
            m.nk = NM_NARY;
            m.code = 7427;
        }
}

// -------------------------------------------------------------- ModCage --
// "all_different(C) and sum(x * L(x) for x in C) == t" read exactly, joint pairs included: a DP over the cells with
// (digits used, sum so far) -- at most 2^D * (t + 1) states a cell, where AuxRule's probing only bounds a cage this wide.
// Pairs (cell, digit, value) on no completion go ("its real digit sum is 39 - 9 = 30: the missing pair is 7 and 8").
// Code 7424.
void Solver::mod_cage(MoveBuf& out) {
    if (!has_aux() || p.aux_layers <= 0 || jx.size() != p.aux_values.size() || p.D > 9) return;
    struct MC { int layer; long long total; std::vector<int> cells; };
    static thread_local std::unordered_map<uint64_t, std::vector<MC>> cache;
    auto it = cache.find(p.uid);
    if (it == cache.end()) {
        std::vector<MC> cs;
        for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
            for (const NConstraint& k : *L) {
                if (k.type != NT_EXPR || !k.expr) continue;
                const ExprNode& r = k.expr->root;
                long long l, t;
                std::vector<int> cells;
                if (!mcage(*k.expr, r, l, t, cells) || cells.empty() || t < 0 || t > 400) continue;
                bool alldiff = false;  // all_different over the same cells, in the same rule
                std::function<void(const ExprNode&)> scan = [&](const ExprNode& x) {
                    if (x.op == X_AND) {
                        for (const ExprNode& y : x.kids) scan(y);
                        return;
                    }
                    if (x.op == X_CALL && x.v == 16 /* ALL_DIFFERENT */ && x.kids.size() == 1 && x.kids[0].op == X_CELLS &&
                        x.kids[0].v >= 0 && x.kids[0].v < (long long)k.expr->lists.size()) {
                        std::vector<int> vars, cc;
                        jcells(k.expr->lists[x.kids[0].v], vars);
                        for (int y : vars)
                            if (y >= 0 && y < (int)k.expr->gcell.size()) cc.push_back(k.expr->gcell[y]);
                        std::vector<int> a = cc, b = cells;
                        std::sort(a.begin(), a.end()), std::sort(b.begin(), b.end());
                        alldiff |= a == b;
                    }
                };
                scan(r);
                if (alldiff && (int)cells.size() <= p.D && l >= 0 && l < p.aux_layers) cs.push_back({(int)l, t, cells});
            }
        if (cache.size() > 64) cache.clear();
        it = cache.emplace(p.uid, std::move(cs)).first;
    }
    for (const MC& mc : it->second) {
        if (deadline_passed()) return;
        const int n = (int)mc.cells.size(), T = (int)mc.total, S = 1 << p.D;
        std::vector<int> av_(n);
        std::vector<std::vector<std::pair<int, int>>> opts(n);  // per cell: live (digit, value index)
        bool neg = false;  // a negative multiplier: partial sums are no bound (not read)
        for (int c : mc.cells)
            for (int w : p.aux_values[p.aux_u + mc.layer * p.N + c]) neg |= w < 0;
        if (neg) continue;
        for (int i = 0; i < n; ++i) {
            const int c = mc.cells[i], a = p.aux_u + mc.layer * p.N + c;
            av_[i] = a;
            for (int d = 1; d <= p.D; ++d) {
                if (vals[c] ? vals[c] != d : !(cand[c] & bit(d))) continue;
                for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi)
                    if (auxf[aux_off[a] + vi] && (!joint_ok(a) || joint_live(a, d, vi))) opts[i].emplace_back(d, vi);
            }
        }
        // the cage's extra (values - digits) as ModifierEquiv bounds it in this state
        long long elo = LLONG_MIN / 4, ehi = LLONG_MAX / 4;
        {
            std::vector<int> sc = mc.cells;
            std::sort(sc.begin(), sc.end());
            auto f = g_side_extra.find(sc);
            if (f != g_side_extra.end()) elo = f->second.first, ehi = f->second.second;
        }
        // a layer house holding the whole cage counts its literal once ("one doubler per box"): u = used
        uint32_t uv = 0;
        for (const JHouse& h : jhouses_of(p)) {
            if (h.pmask.any() || h.digit || h.layer != mc.layer) continue;
            bool all = true;
            for (int c : mc.cells) all &= std::binary_search(h.cells.begin(), h.cells.end(), c);
            if (all) uv |= h.vmask;
        }
        // the reading depends only on the cage's options, its extra bounds and the house literal: kept per that state
        // (it runs inside every case branch's propagation: 59% of a doubler killer's grade before)
        struct McRes { std::vector<std::pair<int, int>> del, aout; std::vector<std::tuple<int, int, int>> jout; };
        static thread_local std::unordered_map<std::string, McRes> memo;
        std::string key;
        {
            auto put = [&](uint64_t x) { key.append(reinterpret_cast<const char*>(&x), sizeof x); };
            put(p.uid), put((uint64_t)(uintptr_t)&mc), put((uint64_t)elo), put((uint64_t)ehi), put(uv);
            for (int i = 0; i < n; ++i) {
                const int c = mc.cells[i], a = av_[i];
                put(vals[c] ? (1ull << 40 | (uint64_t)vals[c]) : cand[c]);
                for (int k = aux_off[a]; k < aux_off[a + 1]; ++k) key.push_back(auxf[k] ? '1' : '0');
                if (joint_ok(a))
                    for (int w = 0; w < JW; ++w) put(jword(jx[a], w));
            }
        }
        auto emit_mc = [&](const McRes& r) {
            if (r.del.empty() && r.aout.empty() && r.jout.empty()) return;
            Move& m = new_move(out, MOD_CAGE, 1.0, (int)(r.del.size() + r.aout.size() + r.jout.size()));
            for (auto& e : r.del) add_el(out, m, e.first, e.second);
            for (auto& e : r.aout) add_aeff(out, m, AE_AUX, e.first, e.second);
            for (auto& [a, d, vi] : r.jout) add_aeff(out, m, AE_JOINT, a, d * 16 + vi);
            set_pattern(out, m, mc.cells);
            m.nk = NM_NARY;
            m.code = 7424;
        };
        if (!memo_off("modcage")) {
            auto mf = memo.find(key);
            if (mf != memo.end()) {
                emit_mc(mf->second);
                continue;
            }
        }
        if (memo.size() > 200000) memo.clear();
        auto idx = [&](int mask, int s, int u) { return ((size_t)mask * (T + 1) + s) * 2 + u; };
        // ok[i][idx]: cells i.. can finish from digits `mask` used, sum s, the house literal used (u)
        std::vector<std::vector<char>> ok(n + 1, std::vector<char>((size_t)S * (T + 1) * 2, 0));
        for (int mask = 0; mask < S; ++mask) {
            long long ds = 0;
            for (int d = 1; d <= p.D; ++d)
                if (mask >> (d - 1) & 1) ds += d;
            ok[n][idx(mask, T, 0)] = ok[n][idx(mask, T, 1)] = T - ds >= elo && T - ds <= ehi;
        }
        for (int i = n - 1; i >= 0; --i)
            for (int mask = 0; mask < S; ++mask)
                for (int s = 0; s <= T; ++s)
                    for (int u = 0; u < 2; ++u) {
                        char r = 0;
                        for (auto [d, vi] : opts[i]) {
                            if (mask >> (d - 1) & 1) continue;
                            const int lit = (uv >> vi) & 1;
                            if (lit && u) continue;
                            const int s2 = s + d * p.aux_values[av_[i]][vi];
                            if (s2 <= T && s2 >= 0 && ok[i + 1][idx(mask | 1 << (d - 1), s2, u | lit)]) { r = 1; break; }
                        }
                        ok[i][idx(mask, s, u)] = r;
                    }
        if (!ok[0][idx(0, 0, 0)]) {  // no filling: a contradiction others show
            if (!deadline_passed()) memo[key] = McRes();
            continue;
        }
        std::vector<char> reach((size_t)S * (T + 1) * 2, 0), nxt;
        reach[idx(0, 0, 0)] = 1;
        std::vector<std::set<std::pair<int, int>>> sup(n);
        for (int i = 0; i < n; ++i) {
            nxt.assign(reach.size(), 0);
            for (int mask = 0; mask < S; ++mask)
                for (int s = 0; s <= T; ++s)
                    for (int u = 0; u < 2; ++u) {
                        if (!reach[idx(mask, s, u)]) continue;
                        for (auto [d, vi] : opts[i]) {
                            if (mask >> (d - 1) & 1) continue;
                            const int lit = (uv >> vi) & 1;
                            if (lit && u) continue;
                            const int s2 = s + d * p.aux_values[av_[i]][vi];
                            if (s2 < 0 || s2 > T) continue;
                            const size_t k2 = idx(mask | 1 << (d - 1), s2, u | lit);
                            if (!ok[i + 1][k2]) continue;
                            sup[i].insert({d, vi});
                            nxt[k2] = 1;
                        }
                    }
            reach.swap(nxt);
        }
        std::vector<std::pair<int, int>> del, aout;
        std::vector<std::tuple<int, int, int>> jout;
        for (int i = 0; i < n; ++i) {
            const int c = mc.cells[i], a = av_[i];
            uint32_t dsup = 0, vsup = 0;
            for (auto [d, vi] : sup[i]) dsup |= bit(d), vsup |= 1u << vi;
            for (auto [d, vi] : opts[i])
                if (!sup[i].count({d, vi}) && (dsup & bit(d)) && (vsup >> vi & 1) && joint_ok(a)) jout.emplace_back(a, d, vi);
            if (!vals[c])
                for (int d = 1; d <= p.D; ++d)
                    if ((cand[c] & bit(d)) && !(dsup & bit(d))) del.emplace_back(c, d);
            for (int vi = 0; vi < (int)p.aux_values[a].size(); ++vi)
                if (auxf[aux_off[a] + vi] && !(vsup >> vi & 1)) aout.emplace_back(a, vi);
        }
        McRes res{del, aout, jout};
        if (!deadline_passed()) memo[key] = res;
        emit_mc(res);
    }
}

// ------------------------------------------------------------ LayerFish --
// fish on a layer: count rules counting the same predicate P ("is special": doubled or tripled) over several houses.
// Base houses B (1-2, disjoint) need nB more P cells, and all their open cells lie in cover houses C (1-2, disjoint)
// that can take only nC = nB more: those nB land in B's open cells inside C, so C's other open cells are not P (the
// star battle's "these two rows fill these two boxes"; an X-wing on cold digits). Code 7410 (LayerTrial's tier).
void Solver::layer_fish(MoveBuf& out, const std::vector<const NConstraint*>& counts,
                        const std::vector<std::vector<int>>& dom0,
                        const std::function<std::vector<uint32_t>(const NConstraint&)>& digits) {
    struct H {
        std::vector<uint64_t> preds;  // the predicate(s) counted: two exclusive ones for a union ("special")
        int need;
        const NConstraint* k;
        std::vector<int> cells, open;  // board cells; open: possibly but not surely P
    };
    std::map<uint64_t, std::vector<H>> groups;
    for (const NConstraint* k : counts) {
        CountMoves cm = expr_count_moves(*k->expr, p.D, digits(*k), dom0, true, nullptr, true);
        if (cm.infeasible) continue;
        std::vector<H> mine(cm.houses.size());
        std::vector<char> okv(cm.houses.size(), 0);
        for (size_t hi2 = 0; hi2 < cm.houses.size(); ++hi2) {
            const CountHouse& ch = cm.houses[hi2];
            H h{{ch.pred}, ch.k, k, {}, {}};
            bool ok = true;
            for (size_t i = 0; i < ch.vars.size(); ++i) {
                if (ch.vars[i] < 0) { ok = false; break; }
                const int c = k->vars[ch.vars[i]];
                h.cells.push_back(c);
                if (ch.sure[i]) --h.need;
                else if (ch.poss[i]) h.open.push_back(c);
            }
            okv[hi2] = ok;
            mine[hi2] = h;
            if (ok && h.need > 0 && !h.open.empty()) groups[ch.pred].push_back(h);
        }
        // unions of two exclusive predicates over the same cells: their counts add up
        for (size_t a = 0; a < cm.houses.size(); ++a)
            for (int b : cm.houses[a].exclusive) {
                if (b <= (int)a || !okv[a] || !okv[b]) continue;
                H u = mine[a];
                u.preds.push_back(cm.houses[b].pred);
                u.need = mine[a].need + mine[b].need;
                for (int c : mine[b].open)
                    if (std::find(u.open.begin(), u.open.end(), c) == u.open.end()) u.open.push_back(c);
                const uint64_t lo = std::min(cm.houses[a].pred, cm.houses[b].pred), hi = std::max(cm.houses[a].pred, cm.houses[b].pred);
                if (u.need > 0 && !u.open.empty()) groups[(lo * 1000003ull) ^ (hi + 0x9e3779b97f4a7c15ull)].push_back(u);
            }
    }
    for (auto& [pred, hs] : groups) {
        if (hs.size() < 2 || hs.size() > 60) continue;
        if (deadline_passed()) return;
        auto disjoint = [](const H& a, const H& b) {
            for (int c : a.cells)
                if (std::find(b.cells.begin(), b.cells.end(), c) != b.cells.end()) return false;
            return true;
        };
        // index sets of 1-2 disjoint houses
        std::vector<std::vector<int>> sets;
        for (size_t i = 0; i < hs.size(); ++i) {
            sets.push_back({(int)i});
            for (size_t j = i + 1; j < hs.size(); ++j)
                if (disjoint(hs[i], hs[j])) sets.push_back({(int)i, (int)j});
        }
        // cell flags (std::sets here were 12% of a layer puzzle's grade): B's cells / open cells, C's cells by stamp
        std::vector<char> bcell(p.N, 0), bopf(p.N, 0);
        std::vector<int> cstamp(p.N, -1);
        int cst = 0;
        for (const auto& Bs : sets) {
            int nB = 0;
            std::fill(bcell.begin(), bcell.end(), 0), std::fill(bopf.begin(), bopf.end(), 0);
            std::vector<int> bopen;
            for (int i : Bs) {
                nB += hs[i].need;
                for (int c : hs[i].cells) bcell[c] = 1;
                for (int c : hs[i].open)
                    if (!bopf[c]) bopf[c] = 1, bopen.push_back(c);
            }
            std::sort(bopen.begin(), bopen.end());
            // cover sets from the houses touching B's open cells only
            std::vector<int> touch;
            for (size_t i = 0; i < hs.size(); ++i) {
                if (std::find(Bs.begin(), Bs.end(), (int)i) != Bs.end()) continue;
                for (int c : hs[i].open)
                    if (bopf[c]) { touch.push_back((int)i); break; }
            }
            std::vector<std::vector<int>> csets;
            for (size_t a = 0; a < touch.size(); ++a) {
                if (Bs.size() == 1) csets.push_back({touch[a]});
                else
                    for (size_t b = a + 1; b < touch.size(); ++b)
                        if (disjoint(hs[touch[a]], hs[touch[b]])) csets.push_back({touch[a], touch[b]});
            }
            for (const auto& Cs : csets) {
                if (Cs.size() != Bs.size()) continue;
                bool overlap = false;
                for (int i : Cs) overlap |= std::find(Bs.begin(), Bs.end(), i) != Bs.end();
                if (overlap) continue;
                int nC = 0;
                ++cst;
                for (int i : Cs) {
                    nC += hs[i].need;
                    for (int c : hs[i].cells) cstamp[c] = cst;
                }
                if (nC != nB) continue;
                bool covered = true;
                for (int c : bopen) covered &= cstamp[c] == cst;
                if (!covered) continue;
                // C's open cells outside B lose P
                std::vector<std::pair<int, int>> dout, aout;
                std::vector<int> pc(bopen.begin(), bopen.end());
                for (int i : Cs) {
                    const H& h = hs[i];
                    std::vector<int> clear;
                    for (int c : h.open)
                        if (!bcell[c])
                            for (int v = 0; v < h.k->nv(); ++v)
                                if (h.k->vars[v] == c) clear.push_back(v);
                    if (clear.empty()) continue;
                    for (uint64_t pr : h.preds) {
                    CountQuery q;
                    q.pred = pr, q.clear = clear;
                    CountMoves cm = expr_count_moves(*h.k->expr, p.D, digits(*h.k), dom0, false, &q);
                    for (auto [v, d] : cm.digits)
                        if (!vals[h.k->vars[v]] && (cand[h.k->vars[v]] & bit(d))) dout.emplace_back(h.k->vars[v], d);
                    for (auto [a, w] : cm.aux) {
                        const auto& av = p.aux_values[a];
                        const auto itv = std::find(av.begin(), av.end(), w);
                        if (itv != av.end() && auxf[aux_off[a] + (itv - av.begin())])
                            aout.emplace_back(a, (int)(itv - av.begin()));
                    }
                    }
                }
                std::sort(dout.begin(), dout.end());
                dout.erase(std::unique(dout.begin(), dout.end()), dout.end());
                std::sort(aout.begin(), aout.end());
                aout.erase(std::unique(aout.begin(), aout.end()), aout.end());
                if (dout.empty() && aout.empty()) continue;
                Move& m = new_move(out, LAYER_TRIAL, 1.0, (int)(dout.size() + aout.size()));
                for (auto& e : dout) add_el(out, m, e.first, e.second);
                for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
                set_pattern(out, m, pc);
                m.code = 7410;
            }
        }
    }
}

// ------------------------------------------------------------ LayerTrial --
// a layer value tried, one round: with variable a = w, the small rules on layers (two cells: "adjusted cells never
// touch") narrow the values of the other variables they read; then every count rule ("one doubler per house") is
// checked -- one that can no longer be met (too many sure, too few possible) rules w out. The hosts' "if this were a
// doubler, its king ring would cover the box" (Trouble). Code 7407.
void Solver::layer_trial(MoveBuf& out) {
    if (!has_aux() || disabled[LAYER_TRIAL]) return;
    const int NA = (int)p.aux_values.size();
    std::vector<std::vector<int>> dom0(NA);
    bool open = false;  // every unknown / layer value decided: nothing to try (a third of Trouble's grade ran here)
    for (int a = 0; a < NA; ++a) {
        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
            if (auxf[i]) dom0[a].push_back(p.aux_values[a][i - aux_off[a]]);
        open |= dom0[a].size() > 1;
    }
    if (!open) return;
    unknown_trial(out);
    LTClock lt;  // diagnostics (aux_memo_stats)
    auto digits = [&](const NConstraint& k) {
        std::vector<uint32_t> d(k.nv());
        for (int i = 0; i < k.nv(); ++i) d[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
        return d;
    };
    std::vector<const NConstraint*> counts, small;
    std::vector<std::vector<const NConstraint*>> by_aux(NA);
    std::vector<std::vector<int>> counts_of(NA);  // per aux variable: the count rules reading it
    for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
        for (const NConstraint& k : *L) {
            if (k.type != NT_EXPR || !k.expr || k.expr->aux_read.empty()) continue;
            if (expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;
            // a grid-wide count ("each digit cold once") is read as joint houses (JointHouses); re-analysed here every
            // listing it was half of a layer puzzle's grade (PENCILMARK_LT_WIDE=1: keep it here too)
            static const bool lt_wide = std::getenv("PENCILMARK_LT_WIDE") != nullptr;
            if (!lt_wide && k.nv() > p.D) continue;
            if (expr_count_moves(*k.expr, p.D, digits(k), dom0, true).any) {
                for (int a : k.expr->aux_read)
                    if (a >= 0 && a < NA) counts_of[a].push_back((int)counts.size());
                counts.push_back(&k);
            }
            else if (k.nv() <= 2) {
                small.push_back(&k);
                for (int a : k.expr->aux_read)
                    if (a >= 0 && a < NA) by_aux[a].push_back(&k);
            }
        }
    if (counts.empty()) return;  // (without small rules the trial below does nothing; the fish still runs)
    lt.mark(0), lt.last = 1;
    // (c) multi-rule hypotheses: rules "sum(f(x) for x in S) == U" lying inside one house and sharing U, with all
    // their cells' layer at one value w -- per rule the sums each digit set allows, disjoint sets, one common U. None:
    // the fact "not all of these are w" ("box 4's segments cannot all be plain: 42+ leaves under 6 for three cells").
    struct NotAll { std::vector<int> avars; int w; std::vector<int> cells; };
    std::vector<NotAll> notall;
    if (counts[0]->expr->aux_n > 0) {
        const int AU0 = counts[0]->expr->aux_u, AN0 = counts[0]->expr->aux_n, NL0 = (NA - AU0) / std::max(AN0, 1);
        for (int hi : p.houses) {
            const Group& g = p.groups[hi];
            if (!g.complete || (int)g.cells.size() != p.D) continue;
            std::map<int, std::vector<const NConstraint*>> by_u;
            for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
                for (const NConstraint& k : *L) {
                    if (k.type != NT_EXPR || !k.expr || k.expr->aux_read.empty()) continue;
                    const int side = expr_eq_unknown(*k.expr);
                    if (side < 0) continue;
                    bool inside = true;
                    for (int c : k.vars) inside &= std::find(g.cells.begin(), g.cells.end(), c) != g.cells.end();
                    if (inside) by_u[(int)k.expr->root.kids[side].v].push_back(&k);
                }
            for (auto& [U, rs] : by_u) {
                if (rs.size() > 3 || U < 0 || U >= NA) continue;
                std::vector<int> cells;
                for (const NConstraint* k : rs) cells.insert(cells.end(), k->vars.begin(), k->vars.end());
                if (cells.size() < 2) continue;
                for (int l = 0; l < NL0; ++l) {
                    std::vector<int> avars;
                    for (int c : cells) avars.push_back(AU0 + l * AN0 + c);
                    bool in_range = true;
                    for (int a : avars) in_range &= a >= 0 && a < NA;
                    if (!in_range) continue;
                    for (int w : dom0[avars[0]]) {
                        std::vector<std::vector<int>> ad = dom0;
                        bool can = true;
                        for (int a : avars) {
                            can &= std::find(dom0[a].begin(), dom0[a].end(), w) != dom0[a].end();
                            ad[a] = {w};
                        }
                        if (!can) continue;
                        // per rule: the digit masks of its cells with their sum bounds
                        std::vector<std::vector<std::tuple<uint32_t, long long, long long>>> opts;
                        bool ok = true;
                        for (const NConstraint* k : rs) {
                            std::vector<std::vector<int>> vh(k->nv());
                            for (int i = 0; i < k->nv(); ++i)
                                for (int gg : p.groups_of[k->vars[i]])
                                    if (p.groups[gg].complete && (int)p.groups[gg].cells.size() == p.D) vh[i].push_back(gg);
                            std::vector<long long> lo, hi2;
                            if (!expr_eq_mask_bounds(*k->expr, p.D, digits(*k), vh, ad, lo, hi2)) { ok = false; break; }
                            std::vector<std::tuple<uint32_t, long long, long long>> o;
                            for (size_t mk = 0; mk < lo.size(); ++mk)
                                if (lo[mk] <= hi2[mk] && __builtin_popcount((unsigned)mk) == k->nv()) o.emplace_back((uint32_t)mk, lo[mk], hi2[mk]);
                            if (o.empty()) { ok = false; break; }
                            opts.push_back(std::move(o));
                        }
                        if (!ok) continue;
                        // disjoint masks with a common U value
                        bool feasible = false;
                        std::function<void(size_t, uint32_t, long long, long long)> go = [&](size_t i, uint32_t used, long long L, long long Hh) {
                            if (feasible || L > Hh) return;
                            if (i == opts.size()) {
                                for (int v : dom0[U]) feasible |= v >= L && v <= Hh;
                                return;
                            }
                            for (auto& [mk, a, b] : opts[i])
                                if (!(mk & used)) go(i + 1, used | mk, std::max(L, a), std::min(Hh, b));
                        };
                        go(0, 0, LLONG_MIN / 4, LLONG_MAX / 4);
                        if (!feasible) notall.push_back({avars, w, cells});
                    }
                }
            }
        }
    }
    // (d) star-battle counting: union houses (two exclusive counts over the same cells: "special") with each cell's
    // special values; two cells conflict when a two-cell rule forbids both special (adjacent specials). A house is
    // infeasible when its sure specials plus the most non-conflicting open cells fall short of its need.
    struct UH { std::vector<int> avars; std::vector<std::vector<int>> spec; int need; };
    std::vector<UH> uhouses;
    for (const NConstraint* k : counts) {
        CountMoves cm = expr_count_moves(*k->expr, p.D, digits(*k), dom0, true, nullptr, true);
        for (size_t a = 0; a < cm.houses.size(); ++a)
            for (int b : cm.houses[a].exclusive) {
                if (b <= (int)a) continue;
                const CountHouse& A = cm.houses[a];
                const CountHouse& B = cm.houses[b];
                UH u{{}, {}, A.k + B.k};
                bool ok = A.avar.size() == A.vars.size() && B.avar.size() == B.vars.size();
                for (size_t i = 0; ok && i < A.vars.size(); ++i) {
                    if (A.avar[i] < 0 || A.avar[i] != B.avar[i]) { ok = false; break; }
                    std::vector<int> sv = A.pvals[i];
                    sv.insert(sv.end(), B.pvals[i].begin(), B.pvals[i].end());
                    std::sort(sv.begin(), sv.end());
                    sv.erase(std::unique(sv.begin(), sv.end()), sv.end());
                    u.avars.push_back(A.avar[i]), u.spec.push_back(sv);
                }
                if (ok && u.avars.size() <= 16) uhouses.push_back(std::move(u));
            }
    }
    std::map<std::pair<int, int>, bool> conflict_cache;
    auto conflict = [&](int a, const std::vector<int>& Sa, int b, const std::vector<int>& Sb) {
        auto key = std::make_pair(std::min(a, b), std::max(a, b));
        auto itc = conflict_cache.find(key);
        if (itc != conflict_cache.end()) return itc->second;
        bool res = false;
        for (const NConstraint* k : by_aux[a]) {
            if (std::find(k->expr->aux_read.begin(), k->expr->aux_read.end(), b) == k->expr->aux_read.end()) continue;
            const std::vector<uint32_t> dm = digits(*k);
            bool any = false;
            std::vector<std::vector<int>> ad = dom0;
            for (int wa : Sa)
                for (int wb : Sb) {
                    if (any) break;
                    ad[a] = {wa}, ad[b] = {wb};
                    any = expr_may_hold(*k->expr, dm.data(), ad);
                }
            if (!any) { res = true; break; }
        }
        conflict_cache[key] = res;
        return res;
    };
    auto union_infeasible = [&](const std::vector<std::vector<int>>& ad) {
        for (const UH& u : uhouses) {
            std::vector<int> sure, open;
            for (size_t i = 0; i < u.avars.size(); ++i) {
                const auto& d = ad[u.avars[i]];
                bool any_s = false, all_s = !d.empty();
                for (int w : d) {
                    const bool sp = std::find(u.spec[i].begin(), u.spec[i].end(), w) != u.spec[i].end();
                    any_s |= sp, all_s &= sp;
                }
                if (all_s) sure.push_back((int)i);
                else if (any_s) open.push_back((int)i);
            }
            if ((int)sure.size() >= u.need) continue;
            for (size_t x = 0; x < sure.size(); ++x)
                for (size_t y = x + 1; y < sure.size(); ++y)
                    if (conflict(u.avars[sure[x]], u.spec[sure[x]], u.avars[sure[y]], u.spec[sure[y]])) return true;
            std::vector<int> cand2;
            for (int o : open) {
                bool clash = false;
                for (int sc : sure) clash |= conflict(u.avars[o], u.spec[o], u.avars[sc], u.spec[sc]);
                if (!clash) cand2.push_back(o);
            }
            const int n = (int)cand2.size();
            if (n > 16) continue;
            int best = 0;
            for (int mask = 0; mask < (1 << n) && best + (int)sure.size() < u.need; ++mask) {
                const int pc = __builtin_popcount((unsigned)mask);
                if (pc <= best) continue;
                bool indep = true;
                for (int x = 0; x < n && indep; ++x)
                    if (mask >> x & 1)
                        for (int y = x + 1; y < n && indep; ++y)
                            if (mask >> y & 1)
                                indep = !conflict(u.avars[cand2[x]], u.spec[cand2[x]], u.avars[cand2[y]], u.spec[cand2[y]]);
                if (indep) best = pc;
            }
            if ((int)sure.size() + best < u.need) return true;
        }
        return false;
    };
    // a fact with one variable left that can differ from w: it does
    for (const NotAll& na : notall) {
        int open = -1, n_open = 0;
        for (int a : na.avars)
            if (dom0[a].size() != 1 || dom0[a][0] != na.w) ++n_open, open = a;
        if (n_open != 1 || std::find(dom0[open].begin(), dom0[open].end(), na.w) == dom0[open].end()) continue;
        const auto& av = p.aux_values[open];
        Move& m = new_move(out, LAYER_TRIAL, 1.0, 1);
        add_aeff(out, m, AE_AUX, open, (int)(std::find(av.begin(), av.end(), na.w) - av.begin()));
        set_pattern(out, m, na.cells);
        m.code = 7411;
    }
    lt.mark(1), lt.last = 2;
    for (int a = 0; a < NA; ++a) {
        // layer-like variables only (a few values: doubled or not); an unknown total's many values are AuxRule's
        if (dom0[a].size() < 2 || dom0[a].size() > 9 || by_aux[a].empty()) continue;
        if (deadline_passed()) return;
        std::vector<int> gone;  // the values of a the trial rules out: one move per variable
        for (int w : dom0[a]) {
            std::vector<std::vector<int>> ad = dom0;
            ad[a] = {w};
            bool dead = false;
            std::vector<int> touched{a};  // the variables the trial changed: only their counts are checked
            // one round of the small rules reading a: the other variables they read keep the values that still fit
            for (const NConstraint* k : by_aux[a]) {
                const std::vector<uint32_t> dm = digits(*k);
                if (!expr_may_hold(*k->expr, dm.data(), ad)) { dead = true; break; }
                for (int b : k->expr->aux_read) {
                    if (b == a || b < 0 || b >= NA || ad[b].size() < 2) continue;
                    std::vector<int> keep;
                    const std::vector<int> was = ad[b];
                    for (int v : was) {
                        ad[b] = {v};
                        if (expr_may_hold(*k->expr, dm.data(), ad)) keep.push_back(v);
                    }
                    ad[b] = keep;
                    if (keep.size() < was.size()) touched.push_back(b);
                    if (keep.empty()) { dead = true; break; }
                }
                if (dead) break;
            }
            if (!dead) dead = union_infeasible(ad);  // star-battle counting
            // a multi-rule fact all at w
            for (size_t i = 0; i < notall.size() && !dead; ++i) {
                bool all_w = true;
                for (int x : notall[i].avars) all_w &= ad[x].size() == 1 && ad[x][0] == notall[i].w;
                dead = all_w;
            }
            // then the counts reading a changed variable
            std::vector<int> ci;
            for (int t : touched) ci.insert(ci.end(), counts_of[t].begin(), counts_of[t].end());
            std::sort(ci.begin(), ci.end());
            ci.erase(std::unique(ci.begin(), ci.end()), ci.end());
            for (size_t i = 0; i < ci.size() && !dead; ++i)
                dead = expr_count_moves(*counts[ci[i]]->expr, p.D, digits(*counts[ci[i]]), ad, true).infeasible;
            if (dead) gone.push_back(w);
        }
        if (gone.empty() || gone.size() == dom0[a].size()) continue;  // nothing, or a contradiction: others show it
        const auto& av = p.aux_values[a];
        Move& m = new_move(out, LAYER_TRIAL, 1.0, (int)gone.size());
        for (int w : gone) add_aeff(out, m, AE_AUX, a, (int)(std::find(av.begin(), av.end(), w) - av.begin()));
        // the cell whose layer value it is (layers: aux_u + l * N + cell), for the pattern
        std::vector<int> pc;
        if (counts[0]->expr->aux_n > 0 && a >= counts[0]->expr->aux_u)
            pc.push_back((a - counts[0]->expr->aux_u) % counts[0]->expr->aux_n);
        set_pattern(out, m, pc);
        m.code = 7407;
    }
    // (b) a digit's place carries a layer value: house H must hold digit d; with d in each of its remaining cells the
    // rules (read link by link) force some layer values -- of that cell or of others. When in every place the same
    // value v lands in house G, G holds v there; when G's count cannot have two cells at v, G's other cells lose v
    // ("box 5's 9 is its cold cell"; "the 9 is cold under a tip, so the tip is a hot 8: row 3's hot cell is one of
    // those tips"). Code 7409.
    lt.mark(2);
    layer_fish(out, counts, dom0, digits);
    lt.mark(3), lt.last = 4;
    if (counts[0]->expr->aux_n <= 0) return;
    const int AU = counts[0]->expr->aux_u, AN = counts[0]->expr->aux_n;
    std::vector<std::vector<const NConstraint*>> rules_of(p.N);
    for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
        for (const NConstraint& k : *L)
            if (k.type == NT_EXPR && k.expr && !k.expr->aux_read.empty() && k.nv() <= 6 &&
                !expr_reads_shading(k.expr->root) && !expr_reads_regions(k.expr->root))
                for (int c : k.vars) rules_of[c].push_back(&k);
    // (cell, digit) -> the layer values (aux variable, value) the rules force with that digit there; {-1, -1}: dead
    std::unordered_map<long, std::vector<std::pair<int, int>>> forced_at;
    auto forced_of = [&](int c, int d) -> const std::vector<std::pair<int, int>>& {
        const long key = (long)c * 64 + d;
        if (auto it = forced_at.find(key); it != forced_at.end()) return it->second;
        std::vector<std::pair<int, int>> F;
        for (const NConstraint* k : rules_of[c]) {
            std::vector<uint32_t> dm = digits(*k);
            for (int i = 0; i < k->nv(); ++i)
                if (k->vars[i] == c) dm[i] = bit(d);
            std::vector<std::vector<int>> ad = dom0;
            if (!rule_narrow(*k, dm, ad)) { F.assign(1, {-1, -1}); break; }
            for (int x : k->expr->aux_read)
                if (x >= AU && x < NA && dom0[x].size() > 1 && ad[x].size() == 1) F.push_back({x, ad[x][0]});
        }
        std::sort(F.begin(), F.end());
        F.erase(std::unique(F.begin(), F.end()), F.end());
        return forced_at[key] = std::move(F);
    };
    auto cell_of = [&](int x) { return (x - AU) % AN; };
    auto layer_of = [&](int x) { return (x - AU) / AN; };
    auto in_group = [&](const Group& G, int c) { return std::find(G.cells.begin(), G.cells.end(), c) != G.cells.end(); };
    // count rules of G read x and o at v together: two cells at v rejected
    auto two_rejected = [&](int x, int o, int v) {
        std::vector<std::vector<int>> ad = dom0;
        ad[x] = {v}, ad[o] = {v};
        for (int ci : counts_of[o]) {
            const NConstraint& k = *counts[ci];
            if (std::find(k.expr->aux_read.begin(), k.expr->aux_read.end(), x) == k.expr->aux_read.end()) continue;
            if (expr_count_moves(*k.expr, p.D, digits(k), ad, true).infeasible) return true;
        }
        return false;
    };
    std::set<std::pair<int, int>> said;  // one move per elimination
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        if (!g.complete || (int)g.cells.size() != p.D) continue;
        for (int d = 1; d <= p.D; ++d) {
            if (deadline_passed()) return;
            std::vector<int> C;
            bool placed = false;
            for (int c : g.cells) {
                if (vals[c] == d) placed = true;
                else if (!vals[c] && (cand[c] & bit(d))) C.push_back(c);
            }
            if (placed || C.size() < 2 || C.size() > 4) continue;
            bool reads = true;
            for (int c : C) reads &= !rules_of[c].empty();
            if (!reads) continue;
            std::vector<const std::vector<std::pair<int, int>>*> Fs;
            bool dead = false;
            for (int c : C) {
                Fs.push_back(&forced_of(c, d));
                dead |= !Fs.back()->empty() && Fs.back()->front().first < 0;
            }
            if (dead) continue;  // d cannot go there: other techniques say so
            {  // a value forced in every place of d holds: its variable loses the others
                std::vector<std::pair<int, int>> aout;
                for (auto [x, v] : *Fs[0]) {
                    bool every = true;
                    for (size_t t = 1; t < C.size() && every; ++t)
                        every = std::binary_search(Fs[t]->begin(), Fs[t]->end(), std::make_pair(x, v));
                    if (!every) continue;
                    const auto& av = p.aux_values[x];
                    for (int w : dom0[x]) {
                        const int vi = (int)(std::find(av.begin(), av.end(), w) - av.begin());
                        if (w != v && said.insert({x, vi}).second) aout.emplace_back(x, vi);
                    }
                }
                if (!aout.empty()) {
                    Move& m = new_move(out, LAYER_TRIAL, 1.0, (int)aout.size());
                    for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
                    set_pattern(out, m, C);
                    m.code = 7409;
                }
            }
            for (auto [x0, v] : *Fs[0])
                for (int gi : p.houses) {
                    const Group& G = p.groups[gi];
                    if (!G.complete || !in_group(G, cell_of(x0))) continue;
                    // in every place of d, v lands on a cell of G in the same layer
                    std::vector<int> X{x0};
                    bool all = true;
                    for (size_t t = 1; t < C.size() && all; ++t) {
                        int hit = -1;
                        for (auto [x, w] : *Fs[t])
                            if (w == v && layer_of(x) == layer_of(x0) && in_group(G, cell_of(x))) { hit = x; break; }
                        if (hit < 0) all = false;
                        else X.push_back(hit);
                    }
                    if (!all) continue;
                    std::vector<std::pair<int, int>> aout;
                    for (int o : G.cells) {
                        const int ao = AU + layer_of(x0) * AN + o;
                        if (ao >= NA || std::find(X.begin(), X.end(), ao) != X.end()) continue;
                        const auto& av = p.aux_values[ao];
                        if (std::find(dom0[ao].begin(), dom0[ao].end(), v) == dom0[ao].end()) continue;
                        bool rej = true;
                        for (int x : X) rej &= two_rejected(x, ao, v);
                        if (!rej) continue;
                        const int vi = (int)(std::find(av.begin(), av.end(), v) - av.begin());
                        if (said.insert({ao, vi}).second) aout.emplace_back(ao, vi);
                    }
                    if (aout.empty()) continue;
                    Move& m = new_move(out, LAYER_TRIAL, 1.0, (int)aout.size());
                    for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
                    set_pattern(out, m, C);
                    m.code = 7409;
                }
        }
    }
}

// ------------------------------------------------------------ AuxHouse --
// unknowns: the rules "sum of a_c * digit(c) + k == U" lying inside one house (or a cage with its total), on disjoint
// cells, added up against the house total (the set-theory step of the hosts' break-ins: four equal domino totals and the
// center make 45). With X = the house's other cells (coefficient -1) and the rules' cells counted a_c - 1 more times:
//   sum of the rules' unknowns = house total + sum of k + sum over X of b_c * digit(c)
// The unknowns keep the value combinations (at most AUX_CAP) some filling of X reaches; X's digits (at most 5 open
// cells, all different: one house) keep those of a filling that meets a remaining combination.
void Solver::aux_house(MoveBuf& out) {
    if (!has_aux() || disabled[AUX_HOUSE]) return;
    constexpr pm_long AUX_CAP = 4096;
    constexpr int X_MAX = 5;
    const int NA = (int)p.aux_values.size(), N = p.N;
    std::vector<const NConstraint*> lin;
    // derived totals: "linear cells == f(unknowns)" (lin_u -2, e.g. "sum(C) == uD * uD"): f evaluated per combination
    // of the unknowns' values in the exact reading (side: the root's side that reads no cell)
    std::vector<std::pair<const NConstraint*, int>> dlin;
    std::function<bool(const ExprNode&)> reads_cell = [&](const ExprNode& e) {
        if (e.op == X_CELL || e.op == X_CELLS || e.op == X_SLOT || e.op == X_COMP || e.op == X_AUXCELL) return true;
        for (const ExprNode& x : e.kids)
            if (reads_cell(x)) return true;
        return false;
    };
    for (const std::vector<NConstraint>* L : {&p.nary, &p.nary_big})
        for (const NConstraint& k : *L) {
            if (k.type != NT_EXPR || !k.expr || (int)k.expr->lin_coef.size() != k.nv()) continue;
            if (k.expr->lin_u >= 0 && k.expr->lin_u < NA) lin.push_back(&k);
            else if (k.expr->lin_u == -2 && k.expr->root.op == X_EQ && k.expr->root.kids.size() == 2)
                for (int s = 0; s < 2; ++s)
                    if (!reads_cell(k.expr->root.kids[s]) && reads_cell(k.expr->root.kids[1 - s])) {
                        dlin.push_back({&k, s});
                        break;
                    }
        }
    if (lin.empty() && dlin.empty()) return;
    std::vector<int> inh(N, 0), coef(N, 0);
    // each house's equation, kept for the pairwise step below: sum of mult * unknown in [lo, hi]
    struct HEq {
        std::vector<std::pair<int, long long>> u;
        long long lo, hi;
        const Group* g;
    };
    std::vector<HEq> heqs;
    for (const Group& g : p.groups) {
        if (!g.complete && !g.has_total) continue;
        const long long total = g.has_total ? g.total : (long long)p.D * (p.D + 1) / 2;
        bool open = false;
        for (int c : g.cells) inh[c] = 1, open |= !vals[c];
        std::vector<int> mult(NA, 0);  // each unknown, how many chosen rules equal it
        std::vector<int> used;         // the chosen rules' cells (nonzero coefficient)
        std::vector<const NConstraint*> pick;
        long long K = total;
        for (const NConstraint* k : lin) {
            bool inside = true, clash = false;
            for (int i = 0; i < k->nv(); ++i)
                if (k->expr->lin_coef[i]) inside &= inh[k->vars[i]] != 0, clash |= coef[k->vars[i]] != 0;
            if (!inside || clash) continue;
            for (int i = 0; i < k->nv(); ++i)
                if (k->expr->lin_coef[i]) {
                    if (!coef[k->vars[i]]) used.push_back(k->vars[i]);
                    coef[k->vars[i]] += k->expr->lin_coef[i];
                }
            ++mult[k->expr->lin_u];
            K += k->expr->lin_const;
            pick.push_back(k);
        }
        std::vector<std::pair<const NConstraint*, int>> dpick;  // derived totals inside the house
        std::vector<char> dread(NA, 0);                       // the unknowns they read
        for (auto [k, side] : dlin) {
            bool inside = true, clash = false;
            for (int i = 0; i < k->nv(); ++i)
                if (k->expr->lin_coef[i]) inside &= inh[k->vars[i]] != 0, clash |= coef[k->vars[i]] != 0;
            if (!inside || clash) continue;
            for (int i = 0; i < k->nv(); ++i)
                if (k->expr->lin_coef[i]) {
                    if (!coef[k->vars[i]]) used.push_back(k->vars[i]);
                    coef[k->vars[i]] += k->expr->lin_coef[i];
                }
            for (int a : k->expr->aux_read)
                if (a >= 0 && a < NA) dread[a] = 1;
            K += k->expr->lin_const;
            dpick.push_back({k, side});
        }
        for (int c : g.cells) inh[c] = 0;
        // X: the house's cells with b_c = coef - 1 != 0 (b = -1 off the rules); fixed digits go into K
        std::vector<int> X, bx;
        for (int c : g.cells) {
            const int b = coef[c] - 1;
            if (!b) continue;
            if (vals[c]) K += (long long)b * vals[c];
            else X.push_back(c), bx.push_back(b);
        }
        for (int c : used) coef[c] = 0;
        if ((pick.empty() && dpick.empty()) || !open) continue;
        // unknown side: every combination of the open unknowns' values
        std::vector<int> us;
        pm_long combos = 1;
        long long fixed_u = 0;
        bool dead = false;
        std::vector<int> uval(NA, AUX_UNSET);  // the derived totals' fixed unknowns (and, below, the combination's)
        for (int a = 0; a < NA; ++a) {
            if (!mult[a] && !dread[a]) continue;
            int n = 0, last = 0;
            for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                if (auxf[i]) ++n, last = p.aux_values[a][i - aux_off[a]];
            if (n == 0) dead = true;
            else if (n == 1) fixed_u += (long long)mult[a] * last, uval[a] = last;
            else us.push_back(a), combos = std::min<pm_long>(combos * n, 1 << 20);
        }
        // too many value combinations (totals of 1..45 each): the same equation read as intervals below
        const bool wide = combos > AUX_CAP;
        if (dead || (us.empty() && X.empty())) continue;
        if (!dpick.empty() && wide) continue;  // derived totals: the exact reading only
        // X side: the reachable sums of b_c * digit (all different: one house), exact when small, else bounds
        const bool exact = (int)X.size() <= X_MAX;
        // the reachable sums as flags over [rbase, rbase + size) (a std::set here was a quarter of a trial's time)
        long long rbase = 0, rtop = 0, rmin = LLONG_MAX, rmax = LLONG_MIN;
        for (size_t t2 = 0; t2 < X.size(); ++t2)
            rbase += std::min<long long>(bx[t2], (long long)bx[t2] * p.D), rtop += std::max<long long>(bx[t2], (long long)bx[t2] * p.D);
        std::vector<char> reachv(exact ? (size_t)(rtop - rbase + 1) : 0, 0);
        auto reach_has = [&](long long s) { return s >= rbase && s <= rtop && reachv[(size_t)(s - rbase)]; };
        long long lo = 0, hi = 0;
        std::vector<int> dg(X.size());
        std::function<void(size_t, uint32_t, long long, const std::set<long long>*, std::vector<uint32_t>*)> walk =
            [&](size_t j, uint32_t usedd, long long s, const std::set<long long>* want, std::vector<uint32_t>* sup) {
                if (j == X.size()) {
                    if (!want) reachv[(size_t)(s - rbase)] = 1, rmin = std::min(rmin, s), rmax = std::max(rmax, s);
                    else if (want->count(s))
                        for (size_t t = 0; t < X.size(); ++t) (*sup)[t] |= bit(dg[t]);
                    return;
                }
                for (uint32_t m = cand[X[j]] & ~usedd; m; m &= m - 1) {
                    dg[j] = lowdigit(m);
                    walk(j + 1, usedd | bit(dg[j]), s + (long long)bx[j] * dg[j], want, sup);
                }
            };
        if (exact) {
            walk(0, 0, 0, nullptr, nullptr);
            if (rmin > rmax) continue;  // no filling at all: left to the other techniques
        } else {
            for (size_t t = 0; t < X.size(); ++t) {
                const uint32_t cm = cand[X[t]];
                if (!cm) break;
                const long long a = (long long)bx[t] * (__builtin_ctz(cm) + 1), b = (long long)bx[t] * (32 - __builtin_clz(cm));
                lo += std::min(a, b), hi += std::max(a, b);
            }
        }
        auto ok = [&](long long su) {
            const long long need = su - K;
            return exact ? reach_has(need) : lo <= need && need <= hi;
        };
        if (dpick.empty()) {  // (a house with derived totals is no linear equation in the unknowns)
            HEq e;
            e.lo = K + (exact ? rmin : lo), e.hi = K + (exact ? rmax : hi), e.g = &g;
            for (int a = 0; a < NA; ++a)
                if (mult[a]) e.u.push_back({a, mult[a]});
            heqs.push_back(std::move(e));
        }
        if (wide) {
            // interval reading ("box 5 is covered by the segments: their totals add to 45"): the unknowns' weighted
            // sum S lies in K + [the X side's least, most]; each unknown keeps the values that fit with the others'
            // extremes, to a fixpoint
            const long long rlo = K + (exact ? rmin : lo), rhi = K + (exact ? rmax : hi);
            std::vector<std::vector<int>> dom(us.size());
            for (size_t j = 0; j < us.size(); ++j)
                for (int i = aux_off[us[j]]; i < aux_off[us[j] + 1]; ++i)
                    if (auxf[i]) dom[j].push_back(i - aux_off[us[j]]);
            auto term = [&](size_t j, int vi) { return (long long)mult[us[j]] * p.aux_values[us[j]][vi]; };
            for (bool changed = true; changed;) {
                changed = false;
                long long smin = fixed_u, smax = fixed_u;
                for (size_t j = 0; j < us.size(); ++j) {
                    long long a = LLONG_MAX, b = LLONG_MIN;
                    for (int vi : dom[j]) a = std::min(a, term(j, vi)), b = std::max(b, term(j, vi));
                    smin += a, smax += b;
                }
                for (size_t j = 0; j < us.size(); ++j) {
                    long long a = LLONG_MAX, b = LLONG_MIN;
                    for (int vi : dom[j]) a = std::min(a, term(j, vi)), b = std::max(b, term(j, vi));
                    const long long olo = smin - a, ohi = smax - b;  // the others' extremes
                    std::vector<int> kept;
                    for (int vi : dom[j])
                        if (olo + term(j, vi) <= rhi && ohi + term(j, vi) >= rlo) kept.push_back(vi);
                    if (kept.size() != dom[j].size()) changed = true, dom[j] = kept;
                    if (kept.empty()) break;
                }
                bool empty = false;
                for (auto& d : dom) empty |= d.empty();
                if (empty) break;
            }
            bool empty = false;
            for (auto& d : dom) empty |= d.empty();
            if (empty) continue;  // contradiction: left to the other techniques
            std::vector<std::pair<int, int>> aout;
            for (size_t j = 0; j < us.size(); ++j)
                for (int i = aux_off[us[j]]; i < aux_off[us[j] + 1]; ++i)
                    if (auxf[i] && std::find(dom[j].begin(), dom[j].end(), i - aux_off[us[j]]) == dom[j].end())
                        aout.emplace_back(us[j], i - aux_off[us[j]]);
            if (aout.empty()) continue;
            std::vector<int> pc(g.cells.begin(), g.cells.end());
            Move& m = new_move(out, AUX_HOUSE, 1.0, (int)aout.size());
            for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
            set_pattern(out, m, pc);
            m.nk = NM_NARY;
            m.code = 7403;
            pm_long xm[XM_N] = {(pm_long)pick.size(), (pm_long)X.size(), (pm_long)aout.size(), 0, 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
            continue;
        }
        // the combinations: values kept per unknown, and the sums of the ones that work
        std::vector<std::vector<char>> keep(us.size());
        for (size_t j = 0; j < us.size(); ++j) keep[j].assign(aux_off[us[j] + 1] - aux_off[us[j]], 0);
        std::vector<int> pickv(us.size());
        std::set<long long> want;
        std::function<void(size_t, long long)> go = [&](size_t j, long long su) {
            if (j == us.size()) {
                for (auto [k, side] : dpick) {  // each derived total at this combination
                    long long v;
                    // (expr_side_value evaluates the side opposite its argument: here the unknowns' side)
                    if (!expr_side_value(*k->expr, 1 - side, nullptr, uval.data(), v)) return;
                    su += v;
                }
                if (!ok(su)) return;
                want.insert(su - K);
                for (size_t t = 0; t < us.size(); ++t) keep[t][pickv[t]] = 1;
                return;
            }
            const int a = us[j];
            for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
                if (auxf[i]) {
                    pickv[j] = i - aux_off[a];
                    uval[a] = p.aux_values[a][pickv[j]];
                    go(j + 1, su + (long long)mult[a] * p.aux_values[a][pickv[j]]);
                }
            uval[a] = AUX_UNSET;
        };
        go(0, fixed_u);
        if (want.empty()) continue;  // contradiction: left to the search / other techniques
        std::vector<std::pair<int, int>> aout, dout;
        for (size_t j = 0; j < us.size(); ++j)
            for (int i = aux_off[us[j]]; i < aux_off[us[j] + 1]; ++i)
                if (auxf[i] && !keep[j][i - aux_off[us[j]]]) aout.emplace_back(us[j], i - aux_off[us[j]]);
        if (exact && !X.empty()) {
            std::vector<uint32_t> sup(X.size(), 0);
            walk(0, 0, 0, &want, &sup);
            for (size_t t = 0; t < X.size(); ++t)
                for (uint32_t m = cand[X[t]] & ~sup[t]; m; m &= m - 1) dout.emplace_back(X[t], lowdigit(m));
        }
        if (aout.empty() && dout.empty()) continue;
        std::vector<int> pc(g.cells.begin(), g.cells.end());
        Move& m = new_move(out, AUX_HOUSE, 1.0, (int)(aout.size() + dout.size()));
        for (auto& e : dout) add_el(out, m, e.first, e.second);
        for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.code = 7403;
        pm_long xm[XM_N] = {(pm_long)pick.size(), (pm_long)X.size(), (pm_long)aout.size(), (pm_long)dout.size(),
                            0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
    // two houses compared (set theory over unknowns): the difference of two house equations that share totals drops
    // them -- "box 9: T7 + T9 + one cell = 45, box 6: T5 + T7 + T9 + two cells = 45, so T5 is at most 6". Each total
    // left keeps the values that fit with the others' extremes. Code 7418.
    auto dom = [&](int a, long long& mn, long long& mx) {
        mn = LLONG_MAX, mx = LLONG_MIN;
        for (int i = aux_off[a]; i < aux_off[a + 1]; ++i)
            if (auxf[i]) mn = std::min<long long>(mn, p.aux_values[a][i - aux_off[a]]),
                         mx = std::max<long long>(mx, p.aux_values[a][i - aux_off[a]]);
        return mn <= mx;
    };
    // groups (the host's "two lines in box 2: seven cells, seven different digits, at least 28"): segments of plain
    // sums lying in one house have distinct digits across them, so their totals add up to between the n smallest and
    // the n largest digits their n cells can hold -- an equation of its own, read alone and against the houses'
    std::vector<HEq> geqs;
    for (const Group& g : p.groups) {
        if (!g.complete || (int)g.cells.size() != p.D) continue;
        std::vector<const NConstraint*> segs;
        for (const NConstraint* k : lin) {
            bool inside = k->expr->lin_const == 0;
            for (int i = 0; i < k->nv() && inside; ++i)
                inside = k->expr->lin_coef[i] == 1 &&
                         std::find(g.cells.begin(), g.cells.end(), k->vars[i]) != g.cells.end();
            if (inside) segs.push_back(k);
        }
        if (segs.size() < 2 || segs.size() > 5) continue;
        for (uint32_t sub = 1; sub < (1u << segs.size()); ++sub) {
            if (__builtin_popcount(sub) < 2) continue;
            std::vector<int> cells;
            std::map<int, long long> mu;
            for (size_t t = 0; t < segs.size(); ++t)
                if (sub >> t & 1) {
                    cells.insert(cells.end(), segs[t]->vars.begin(), segs[t]->vars.end());
                    mu[segs[t]->expr->lin_u] += 1;
                }
            std::sort(cells.begin(), cells.end());
            if (std::adjacent_find(cells.begin(), cells.end()) != cells.end()) continue;  // overlapping segments
            uint32_t uni = 0;
            long long fixed = 0;
            int open = 0;
            uint32_t used = 0;
            for (int c : cells) {
                if (vals[c]) fixed += vals[c], used |= bit(vals[c]);
                else uni |= cand[c], ++open;
            }
            uni &= ~used;
            if (popc(uni) < open) continue;
            long long lo = fixed, hi = fixed;
            int n = 0;
            for (int d = 1; d <= p.D && n < open; ++d)
                if (uni & bit(d)) lo += d, ++n;
            n = 0;
            for (int d = p.D; d >= 1 && n < open; --d)
                if (uni & bit(d)) hi += d, ++n;
            HEq e;
            e.lo = lo, e.hi = hi, e.g = &g;
            for (auto [a, m] : mu) e.u.push_back({a, m});
            geqs.push_back(std::move(e));
        }
    }
    std::set<std::pair<int, int>> said;
    // narrow by one equation sum co[a] * U_a in [L, H]: each U keeps the values that fit with the others' extremes
    auto narrow_eq = [&](const std::map<int, long long>& co, long long L, long long Hh, std::vector<int> pc, int code) {
        std::vector<std::pair<int, int>> aout;
        for (auto [a, c] : co) {
            long long rlo = 0, rhi = 0;
            for (auto [b, cb] : co) {
                if (b == a) continue;
                long long mn, mx;
                if (!dom(b, mn, mx)) return;
                rlo += std::min(cb * mn, cb * mx), rhi += std::max(cb * mn, cb * mx);
            }
            const long long need_lo = L - rhi, need_hi = Hh - rlo;  // c * value in [need_lo, need_hi]
            for (int t = aux_off[a]; t < aux_off[a + 1]; ++t) {
                if (!auxf[t]) continue;
                const long long cv = c * (long long)p.aux_values[a][t - aux_off[a]];
                if ((cv < need_lo || cv > need_hi) && said.insert({a, t - aux_off[a]}).second)
                    aout.emplace_back(a, t - aux_off[a]);
            }
        }
        if (aout.empty()) return;
        Move& m = new_move(out, AUX_HOUSE, 1.0, (int)aout.size());
        for (auto& e : aout) add_aeff(out, m, AE_AUX, e.first, e.second);
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.code = code;
    };
    for (const HEq& e : geqs) {  // a group alone (code 7420)
        std::map<int, long long> co;
        for (auto [a, m] : e.u) co[a] += m;
        narrow_eq(co, e.lo, e.hi, std::vector<int>(e.g->cells.begin(), e.g->cells.end()), 7420);
    }
    const size_t nh = heqs.size();
    heqs.insert(heqs.end(), geqs.begin(), geqs.end());
    for (size_t i = 0; i < heqs.size(); ++i)
        for (size_t j = 0; j < heqs.size(); ++j) {
            if (i == j || (i >= nh && j >= nh) || deadline_passed()) continue;  // a house against a house or a group
            std::map<int, long long> co;
            for (auto [a, m] : heqs[i].u) co[a] += m;
            bool shared = false;
            for (auto [a, m] : heqs[j].u) {
                shared |= co.count(a) && co[a] == m;
                co[a] -= m;
            }
            if (!shared) continue;
            for (auto it = co.begin(); it != co.end();) it = it->second ? std::next(it) : co.erase(it);
            if (co.empty() || co.size() >= heqs[i].u.size() + heqs[j].u.size() - 1) continue;
            std::vector<int> pc(heqs[i].g->cells.begin(), heqs[i].g->cells.end());
            pc.insert(pc.end(), heqs[j].g->cells.begin(), heqs[j].g->cells.end());
            narrow_eq(co, heqs[i].lo - heqs[j].hi, heqs[i].hi - heqs[j].lo, pc, 7418);
        }
}

}  // namespace cs
