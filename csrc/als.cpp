// Almost locked sets: ALS-XZ, ALS-XY-Wing, Death Blossom, ALS chains (split from extra.cpp).
#include <algorithm>
#include "portable.hpp"
#include <climits>
#include <cstdlib>
#include <cstdio>
#include <chrono>
#include <functional>
#include <map>
#include <set>
#include <unordered_set>

#include "solver.hpp"
#include "move_util.hpp"

namespace cs {

namespace {
enum { CODE_AXZ = 3101, CODE_AXZ2, CODE_AXY, CODE_DBL, CODE_ALSAIC };
}  // namespace

// ------------------------------------------------------------------ ALS --
// n unsolved cells of one AllDiff group (any group: houses, regions,
// diagonals, cages) holding n+1 candidates; any size up to 8 cells (HoDoKu: no limit).
void Solver::build_als() {
    if (als_version == version) return;
    als_version = version;
    als.clear();
    als_seen.clear();
    const int W = p.W;
    std::set<std::vector<uint64_t>> seen;
    std::vector<int> u;
    for (int gi = 0; gi < p.G; ++gi) {
        u.clear();
        for (int c : p.groups[gi].cells)
            if (!vals[c]) u.push_back(c);
        const int nu = (int)u.size();
        std::vector<int> pick;
        std::function<void(int, uint32_t)> rec = [&](int st, uint32_t U) {
            int n = (int)pick.size();
            if (n && popc(U) == n + 1) {
                std::vector<uint64_t> bits(W, 0);
                for (int c : pick) sbit(bits.data(), c);
                if (seen.insert(bits).second) als.push_back({bits, pick, U, gi});
            }
            // any size (HoDoKu: N cells, N+1 digits, one house); the house's unsolved cells all together hold
            // exactly their count of digits, so an ALS leaves one out. 8 cells at most (all of a 9x9 house but one)
            if (n == std::min(nu - 1, 8) || popc(U) > std::min(nu - 1, 8) + 1) return;
            for (int i = st; i < nu; ++i) {
                pick.push_back(u[i]);
                rec(i + 1, U | cand[u[i]]);
                pick.pop_back();
            }
        };
        rec(0, 0);
    }
    als_seen.assign(als.size() * 32 * W, 0);
    for (size_t a = 0; a < als.size(); ++a)
        for (uint32_t dm = als[a].cand; dm; dm &= dm - 1) {
            int d = lowdigit(dm);
            uint64_t* s = &als_seen[((size_t)a * 32 + d) * W];
            std::fill(s, s + W, ~0ULL);
            for (int c : als[a].list)
                if (cand[c] & bit(d)) {
                    const uint64_t* pc = p.peers(c);
                    for (int w = 0; w < W; ++w) s[w] &= pc[w];
                }
        }
}

bool Solver::als_rcc(int a, int b, int x) const {
    if (!(als[a].cand & als[b].cand & bit(x))) return false;
    const uint64_t* s = als_seen_d(a, x);
    for (int c : als[b].list)
        if ((cand[c] & bit(x)) && !tbit(s, c)) return false;
    return true;
}

namespace {
bool disjoint(const std::vector<uint64_t>& a, const std::vector<uint64_t>& b) {
    for (size_t w = 0; w < a.size(); ++w)
        if (a[w] & b[w]) return false;
    return true;
}
}  // namespace

void Solver::als_xz(MoveBuf& out) {
    if (disabled[ALS_XZ]) return;
    build_als();
    const int W = p.W, K = (int)als.size();
    ElimSet es;
    std::vector<uint64_t> tg(W);
    std::vector<uint32_t> el;
    auto targets = [&](const std::vector<int>& as, int z, const std::vector<int>& excl) {
        for (int w = 0; w < W; ++w) tg[w] = ~0ULL;
        for (int a : as) {
            if (!(als[a].cand & bit(z))) continue;
            const uint64_t* s = als_seen_d(a, z);
            for (int w = 0; w < W; ++w) tg[w] &= s[w];
        }
        for (int a : excl)
            for (int w = 0; w < W; ++w) tg[w] &= ~als[a].cells[w];
        for (int q = 0; q < p.N; ++q)
            if (tbit(tg.data(), q) && !vals[q] && (cand[q] & bit(z))) el.push_back((uint32_t)q * 32 + z);
    };
    for (int a = 0; a < K; ++a)
        for (int b = a + 1; b < K; ++b) {
            uint32_t common = als[a].cand & als[b].cand;
            if (popc(common) < 2) continue;
            // the sets may overlap when the restricted common has no candidate there (HoDoKu; als_rcc refuses an
            // x cell in the overlap: a cell does not see itself); overlapping sets are only singly linked
            const bool overlap = !disjoint(als[a].cells, als[b].cells);
            uint32_t rcc = 0;
            for (uint32_t dm = common; dm; dm &= dm - 1)
                if (als_rcc(a, b, lowdigit(dm))) rcc |= dm & (~dm + 1);
            if (!rcc) continue;
            el.clear();
            const std::vector<int> both = {a, b};
            if (popc(rcc) == 1) {
                for (uint32_t dm = common & ~rcc; dm; dm &= dm - 1) targets(both, lowdigit(dm), both);
            } else if (overlap) {  // each restricted common alone, singly linked
                for (uint32_t xm = rcc; xm; xm &= xm - 1)
                    for (uint32_t dm = common & ~(xm & (~xm + 1)); dm; dm &= dm - 1) targets(both, lowdigit(dm), both);
            } else {  // doubly linked: both ALS become locked sets minus the RCCs
                for (uint32_t dm = common & ~rcc; dm; dm &= dm - 1) targets(both, lowdigit(dm), both);
                for (uint32_t dm = rcc; dm; dm &= dm - 1) targets(both, lowdigit(dm), both);
                for (int s : both)  // a digit locked in s leaves the cells outside s seeing all its places (HoDoKu:
                                    // inside the other set too)
                    for (uint32_t dm = als[s].cand & ~rcc; dm; dm &= dm - 1) targets({s}, lowdigit(dm), {s});
            }
            if (el.empty()) continue;
            std::sort(el.begin(), el.end());
            el.erase(std::unique(el.begin(), el.end()), el.end());
            if ((!canon && !es.fresh(el, popc(rcc)))) continue;
            std::vector<int> pc;
            for (int s : both)
                for (int c : als[s].list) pc.push_back(c);
            double shp = pspread(pc);
            int ncell = (int)pc.size();
            Move& m = new_move(out, ALS_XZ, shp, ncell);
            for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
            set_pattern(out, m, pc);
            for (int s : both) add_als_expl(out, m, s, als[s].cand, als[s].list);
            add_expl(out, m, EX_LINKS, {(int)rcc});  // restricted common digits (mask)
            meta9(m, ncell, 2, popc(als[a].cand | als[b].cand), popc(rcc), 0, 0, 0, 1, shp);
            m.code = popc(rcc) == 1 || overlap ? CODE_AXZ : CODE_AXZ2;
            pm_long xm[XM_N] = {2, (pm_long)als[a].list.size(), (pm_long)als[b].list.size(), popc(rcc), (pm_long)el.size(),
                             0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
}

void Solver::als_xywing(MoveBuf& out) {
    if (disabled[ALS_XYWING]) return;
    build_als();
    const int W = p.W, K = (int)als.size();
    ElimSet es;
    std::vector<std::pair<int, int>> link;  // (als, rcc digit)
    std::vector<uint64_t> tg(W);
    for (int cpiv = 0; cpiv < K; ++cpiv) {
        link.clear();
        for (int a = 0; a < K; ++a) {
            if (a == cpiv || !disjoint(als[a].cells, als[cpiv].cells)) continue;
            for (uint32_t dm = als[a].cand & als[cpiv].cand; dm; dm &= dm - 1)
                if (als_rcc(a, cpiv, lowdigit(dm))) link.push_back({a, lowdigit(dm)});
        }
        for (size_t i = 0; i < link.size(); ++i)
            for (size_t j = i + 1; j < link.size(); ++j) {
                int A = link[i].first, B = link[j].first, x = link[i].second, y = link[j].second;
                if (A == B || x == y || !disjoint(als[A].cells, als[B].cells)) continue;
                uint32_t zs = als[A].cand & als[B].cand & ~bit(x) & ~bit(y);
                std::vector<uint32_t> el;
                for (uint32_t dm = zs; dm; dm &= dm - 1) {
                    int z = lowdigit(dm);
                    const uint64_t* sa = als_seen_d(A, z);
                    const uint64_t* sb = als_seen_d(B, z);
                    for (int w = 0; w < W; ++w)
                        tg[w] = sa[w] & sb[w] & ~als[A].cells[w] & ~als[B].cells[w];  // pivot cells too (HoDoKu)
                    for (int q = 0; q < p.N; ++q)
                        if (tbit(tg.data(), q) && !vals[q] && (cand[q] & bit(z))) el.push_back((uint32_t)q * 32 + z);
                }
                if (el.empty() || (!canon && !es.fresh(el, 0))) continue;
                std::vector<int> pc;
                for (int s : {A, B, cpiv})
                    for (int c : als[s].list) pc.push_back(c);
                double shp = pspread(pc);
                int ncell = (int)pc.size();
                Move& m = new_move(out, ALS_XYWING, shp, ncell);
                for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
                set_pattern(out, m, pc);
                for (int s : {A, B, cpiv}) add_als_expl(out, m, s, als[s].cand, als[s].list);
                add_expl(out, m, EX_ROLE, {-1 - cpiv, x, y, (int)zs});  // hinge C, its RCCs x (A) / y (B)
                meta9(m, ncell, 3, popc(als[A].cand | als[B].cand | als[cpiv].cand), 2, 0, 0, 0, 1, shp);
                m.code = CODE_AXY;
                pm_long xm[XM_N] = {3, (pm_long)als[A].list.size(), (pm_long)als[B].list.size(),
                                 (pm_long)als[cpiv].list.size(), (pm_long)el.size(), 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
                if (!canon && out.moves.size() > 4000) return;
            }
    }
}

void Solver::death_blossom(MoveBuf& out) {
    if (disabled[DEATH_BLOSSOM]) return;
    build_als();
    const int W = p.W, K = (int)als.size();
    ElimSet es;
    std::vector<uint64_t> tg(W), used(W);
    for (int S = 0; S < p.N; ++S) {
        if (vals[S] || popc(cand[S]) < 2) continue;  // any stem size (sudokuwiki, HoDoKu, Sudopedia)
        std::vector<int> digs;
        for (uint32_t dm = cand[S]; dm; dm &= dm - 1) digs.push_back(lowdigit(dm));
        std::vector<std::vector<int>> petals(digs.size());
        bool ok = true;
        for (size_t i = 0; i < digs.size(); ++i) {
            for (int a = 0; a < K && (canon || petals[i].size() < 40); ++a) {
                if (tbit(als[a].cells.data(), S) || !(als[a].cand & bit(digs[i]))) continue;
                if (!tbit(als_seen_d(a, digs[i]), S)) continue;
                petals[i].push_back(a);
            }
            if (petals[i].empty()) ok = false;
        }
        if (!ok) continue;
        std::vector<int> ch(digs.size());
        std::function<void(size_t, uint32_t)> rec = [&](size_t i, uint32_t Z) {
            if (!Z) return;
            if (i == digs.size()) {
                std::vector<uint32_t> el;
                for (uint32_t dm = Z; dm; dm &= dm - 1) {
                    int z = lowdigit(dm);
                    for (int w = 0; w < W; ++w) tg[w] = ~0ULL;
                    for (int a : ch) {
                        const uint64_t* s = als_seen_d(a, z);
                        for (int w = 0; w < W; ++w) tg[w] &= s[w] & ~als[a].cells[w];
                    }
                    for (int q = 0; q < p.N; ++q)
                        if (q != S && tbit(tg.data(), q) && !vals[q] && (cand[q] & bit(z)))
                            el.push_back((uint32_t)q * 32 + z);
                }
                if (el.empty() || (!canon && !es.fresh(el, 0))) return;
                std::vector<int> pc{S};
                for (int a : ch)
                    for (int c : als[a].list) pc.push_back(c);
                double shp = pspread(pc);
                int ncell = (int)pc.size();
                Move& m = new_move(out, DEATH_BLOSSOM, shp, (int)digs.size());
                for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
                set_pattern(out, m, pc);
                for (int s : ch) add_als_expl(out, m, s, als[s].cand, als[s].list);
                {  // stem cell, then (stem digit, petal ALS) pairs
                    std::vector<int> role{S};
                    for (size_t i = 0; i < digs.size(); ++i) {
                        role.push_back(digs[i]);
                        role.push_back(-1 - ch[i]);
                    }
                    add_expl(out, m, EX_ROLE, role);
                }
                meta9(m, ncell, (int)digs.size() + 1, popc(cand[S]), (int)digs.size(), 0, 0, 0, 1, shp);
                m.code = CODE_DBL;
                pm_long xm[XM_N] = {(pm_long)digs.size() + 1, ncell, popc(cand[S]), (pm_long)el.size(), 0, 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
                return;
            }
            for (int a : petals[i]) {
                bool dis = true;
                for (size_t j = 0; j < i && dis; ++j) dis = disjoint(als[a].cells, als[ch[j]].cells);
                if (!dis) continue;
                ch[i] = a;
                rec(i + 1, Z & als[a].cand);
                if (out.moves.size() > (canon ? 60000u : 4000u)) return;
            }
        };
        rec(0, p.full & ~cand[S]);
    }
}

// ALS chain A1 -x1- A2 -x2- ... An: consecutive ALS share a restricted common digit x_i (every x_i of one sees
// every x_i of the other), the two digits linking an inner ALS differ, the ALS are pairwise disjoint. If z (in A1
// and An, not x1 in A1, not x_{n-1} in An) were false in A1, A1 would lock x1, so A2 loses x1 and locks x2, ... and An
// locks z: z is in A1 or An, and leaves every cell seeing all of their z cells (HoDoKu's ALS-XY-Chain, sudokuwiki's
// ALS chains). Two and three ALS are ALS-XZ and ALS-XY-Wing; this lists 4 to max_n.
void Solver::als_chain(MoveBuf& out, int max_n) {
    build_als();
    const int W = p.W, K = (int)als.size();
    if (K < 4) return;
    // restricted commons of disjoint pairs
    std::vector<std::vector<std::pair<int, uint32_t>>> adj(K);
    for (int a = 0; a < K; ++a)
        for (int b = a + 1; b < K; ++b) {
            const uint32_t common = als[a].cand & als[b].cand;
            if (!common || !disjoint(als[a].cells, als[b].cells)) continue;
            uint32_t rcc = 0;
            for (uint32_t dm = common; dm; dm &= dm - 1)
                if (als_rcc(a, b, lowdigit(dm))) rcc |= dm & (~dm + 1);
            if (!rcc) continue;
            adj[a].push_back({b, rcc});
            adj[b].push_back({a, rcc});
        }
    ElimSet es;
    std::vector<int> ch, xs;  // chain ALS, linking digits (xs[i] links ch[i] and ch[i + 1])
    std::vector<uint64_t> used(W, 0), tg(W);
    auto emit = [&]() {
        const int A = ch.front(), Z = ch.back(), n = (int)ch.size();
        if (Z < A) return;  // each chain once (its reverse has the same eliminations)
        const uint32_t zs = als[A].cand & als[Z].cand & ~bit(xs.front()) & ~bit(xs.back());
        std::vector<uint32_t> el;
        for (uint32_t dm = zs; dm; dm &= dm - 1) {
            const int z = lowdigit(dm);
            const uint64_t* sa = als_seen_d(A, z);
            const uint64_t* sz = als_seen_d(Z, z);
            for (int w = 0; w < W; ++w) tg[w] = sa[w] & sz[w] & ~als[A].cells[w] & ~als[Z].cells[w];
            for (int q = 0; q < p.N; ++q)
                if (tbit(tg.data(), q) && !vals[q] && (cand[q] & bit(z))) el.push_back((uint32_t)q * 32 + z);
        }
        if (el.empty() || (!canon && !es.fresh(el, n))) return;
        std::vector<int> pc;
        uint32_t digs = 0;
        for (int a : ch) {
            digs |= als[a].cand;
            for (int c : als[a].list) pc.push_back(c);
        }
        const double shp = pspread(pc);
        const int L = 2 * n - 1;
        Move& m = new_move(out, ALS_AIC, shp, L);
        for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
        set_pattern(out, m, pc);
        {  // chain record as the AIC builder writes it: z in A1 = x1 in A1 - x1 in A2 = x2 in A2 - ... = z in An
            const int z0 = lowdigit(zs);
            std::vector<int> lk{-1 - A, z0, 0, -1, -1 - A, xs[0], 5, A};
            for (int i = 1; i < n; ++i) {
                lk.insert(lk.end(), {-1 - ch[i], xs[i - 1], 0, -1});
                lk.insert(lk.end(), {-1 - ch[i], i + 1 < n ? xs[i] : z0, 5, ch[i]});
            }
            add_expl(out, m, EX_CHAIN, lk);
        }
        for (int a : ch) add_als_expl(out, m, a, als[a].cand, als[a].list);
        meta9(m, (int)pc.size(), n - 1, popc(digs), L, 0, 0, 0, 1, shp);
        m.code = 3105;
        pm_long xm[XM_N] = {L, 0, 0, 0, 0, n, n - 1, 0, 0, popc(digs)};
        std::copy(xm, xm + XM_N, m.xm);
    };
    std::function<void(int)> rec = [&](int in) {  // in: the digit that linked the last ALS (-1 at the start)
        const int a = ch.back();
        if ((int)ch.size() >= 4) emit();
        if ((int)ch.size() == max_n) return;
        for (const auto& [b, rcc] : adj[a]) {
            bool clash = false;
            for (int w = 0; w < W && !clash; ++w) clash = used[w] & als[b].cells[w];
            if (clash) continue;
            for (uint32_t dm = rcc & ~(in > 0 ? bit(in) : 0u); dm; dm &= dm - 1) {
                const int x = lowdigit(dm);
                ch.push_back(b);
                xs.push_back(x);
                for (int w = 0; w < W; ++w) used[w] |= als[b].cells[w];
                rec(x);
                for (int w = 0; w < W; ++w) used[w] &= ~als[b].cells[w];
                ch.pop_back();
                xs.pop_back();
            }
        }
    };
    for (int a = 0; a < K; ++a) {
        ch.assign(1, a);
        xs.clear();
        std::fill(used.begin(), used.end(), 0);
        for (int w = 0; w < W; ++w) used[w] = als[a].cells[w];
        rec(-1);
    }
}

void Solver::als_aic(MoveBuf& out, int hi) {
    if (disabled[ALS_AIC]) return;
    als_chain(out, 5);
    build_aic(hi, true);
    for (size_t i = 0; i < aicx_buf.moves.size(); ++i) {
        const Move& a = aicx_buf.moves[i];
        Move m = a;
        m.cov_off = (int)out.covers.size();
        m.el_off = (int)out.elims.size();
        for (int k = 0; k < a.el_n; ++k) out.elims.push_back(aicx_buf.elims[a.el_off + k]);
        copy_extras(aicx_buf, a, out, m);
        out.moves.push_back(m);
    }
}

}  // namespace cs
