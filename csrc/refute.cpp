// Generic refutation profile technique-free difficulty for any puzzle.
// Propagation = singles (naked + hidden in houses) + pair relations (Solver::place) + generalised arc consistency on every n-ary rule
// (complete enumerations only), to a fixpoint. When stuck: every remaining candidate is assumed and propagated; a contradiction is a
// refutation, its chain length = placements made before it. Only the SHORTEST refutations are applied (a human finds the short ones);
// none -> a 'deep' stuck point (the solution digit of the most constrained cell is placed). Output per stuck point:
// (candidates on the board, number of shortest refutations, shortest chain length, deep flag, placements released afterwards).
#include "solver.hpp"
#include <algorithm>
#include <array>

namespace cs {

bool Solver::basic_propagate(int& placed) {
    for (int it = 0; it < 1000; ++it) {
        bool prog = false;
        for (int x = 0; x < p.N; ++x) {
            if (vals[x]) continue;
            if (!cand[x]) return false;
            if (popc(cand[x]) == 1) {
                place(x, lowdigit(cand[x]));
                ++placed;
                prog = true;
            }
        }
        for (int hi : p.houses) {
            for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
                uint32_t b = mm & (~mm + 1);
                int cnt = 0, last = -1;
                for (int x : p.groups[hi].cells)
                    if (!vals[x] && (cand[x] & b)) {
                        ++cnt;
                        last = x;
                    }
                if (cnt == 0) return false;
                if (cnt == 1) {
                    place(last, lowdigit(b));
                    ++placed;
                    prog = true;
                }
            }
        }
        for (const std::vector<NConstraint>* lst : {&p.nary, &p.cage_nary}) {
            for (const NConstraint& k : *lst) {
                if (k.nv() > 64) continue;
                uint32_t dom[64];
                nary_dom(k, dom);
                const GacOut& o = gac_cached(k, dom);
                if (!o.complete) continue;
                if (!o.any) return false;
                for (int i = 0; i < k.nv(); ++i) {
                    int c = k.vars[i];
                    if (vals[c]) continue;
                    uint32_t nd = cand[c] & o.sup[i];
                    if (nd != cand[c]) {
                        if (!nd) return false;
                        cand[c] = nd;
                        prog = true;
                    }
                }
            }
        }
        if (!prog && refK >= 1) {
            int k = k_step();
            if (k < 0) return false;
            if (k > 0) prog = true;
        }
        if (!prog) break;
    }
    return true;
}

// knowledge ladder: houses = complete groups; overlaps of >= 2 cells precomputed once per solver
void Solver::k_prepare() {
    int H = (int)p.houses.size();
    k_in.assign(H, std::vector<char>(p.N, 0));
    for (int a = 0; a < H; ++a)
        for (int x : p.groups[p.houses[a]].cells) k_in[a][x] = 1;
    // refK >= 10: 'standard geometry' -- only straight lines and rectangular boxes that no other non-line house overlaps
    std::vector<char> ok(H, 1);
    if (refK >= 10) {
        std::vector<char> line(H, 0), rect(H, 0);
        for (int a = 0; a < H; ++a) {
            const auto& cs = p.groups[p.houses[a]].cells;
            int r0 = p.coords[cs[0]].first, c0 = p.coords[cs[0]].second, rmin = r0, rmax = r0, cmin = c0, cmax = c0;
            bool sr = true, sc = true;
            for (int x : cs) {
                int r_ = p.coords[x].first, c_ = p.coords[x].second;
                sr &= r_ == r0; sc &= c_ == c0;
                rmin = std::min(rmin, r_); rmax = std::max(rmax, r_); cmin = std::min(cmin, c_); cmax = std::max(cmax, c_);
            }
            line[a] = sr || sc;
            rect[a] = (rmax - rmin + 1) * (cmax - cmin + 1) == (int)cs.size();
        }
        for (int a = 0; a < H; ++a) {
            if (line[a]) continue;
            if (!rect[a]) { ok[a] = 0; continue; }
            for (int b = 0; b < H && ok[a]; ++b) {
                if (b == a || line[b]) continue;
                for (int x : p.groups[p.houses[a]].cells) if (k_in[b][x]) { ok[a] = 0; break; }
            }
        }
    }
    k_ok = ok;
    k_nbr.assign(H, {});
    for (int a = 0; a < H; ++a)
        for (int b = 0; b < H; ++b) {
            if (a == b || !ok[a] || !ok[b]) continue;
            int n = 0;
            for (int x : p.groups[p.houses[a]].cells) n += k_in[b][x];
            if (n >= 2) k_nbr[a].push_back(b);
        }
}

int Solver::k_step() {
    if (k_in.empty()) k_prepare();
    int H = (int)p.houses.size();
    auto remove = [&](int x, uint32_t m) -> int {
        if (vals[x] || !(cand[x] & m)) return 0;
        cand[x] &= ~m;
        return cand[x] ? 1 : -1;
    };
    // locked candidates: digit confined (within house A) to A n B -> removed from B \ A
    for (int a = 0; a < H; ++a) {
        if (!k_ok[a]) continue;
        int hi = p.houses[a];
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            uint32_t b = mm & (~mm + 1);
            std::vector<int> w;
            for (int x : p.groups[hi].cells)
                if (!vals[x] && (cand[x] & b)) w.push_back(x);
            if (w.size() < 2) continue;
            for (int nb : k_nbr[a]) {
                bool inside = true;
                for (int x : w) if (!k_in[nb][x]) { inside = false; break; }
                if (!inside) continue;
                int got = 0;
                for (int y : p.groups[p.houses[nb]].cells) {
                    if (k_in[a][y]) continue;
                    int r = remove(y, b);
                    if (r < 0) return -1;
                    got |= r;
                }
                if (got) return 1;
            }
        }
    }
    // naked / hidden subsets of size 2 (K1) and 3 (K2) inside each house
    int kmax = (refK % 10) >= 2 ? 3 : 2;
    for (int a = 0; a < H; ++a) {
        if (!k_ok[a]) continue;
        int hi = p.houses[a];
        std::vector<int> fr;
        for (int x : p.groups[hi].cells) if (!vals[x]) fr.push_back(x);
        int n = (int)fr.size();
        for (int k = 2; k <= kmax; ++k) {
            if (n <= k) continue;
            std::vector<int> idx(k);
            for (int i = 0; i < k; ++i) idx[i] = i;
            while (true) {
                uint32_t m = 0;
                for (int i : idx) m |= cand[fr[i]];
                if (popc(m) == k) {                         // naked
                    int got = 0;
                    for (int j = 0; j < n; ++j) {
                        if (std::find(idx.begin(), idx.end(), j) != idx.end()) continue;
                        int r = remove(fr[j], m);
                        if (r < 0) return -1;
                        got |= r;
                    }
                    if (got) return 1;
                }
                int i = k - 1;
                while (i >= 0 && idx[i] == n - k + i) --i;
                if (i < 0) break;
                ++idx[i];
                for (int j = i + 1; j < k; ++j) idx[j] = idx[j - 1] + 1;
            }
            // hidden: k digits whose positions in the house are exactly k cells
            std::vector<uint32_t> digs;
            for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) digs.push_back(mm & (~mm + 1));
            int nd = (int)digs.size();
            if (nd <= k) continue;
            std::vector<int> di(k);
            for (int i = 0; i < k; ++i) di[i] = i;
            while (true) {
                uint32_t m = 0;
                for (int i : di) m |= digs[i];
                std::vector<int> cells;
                for (int x : fr) if (cand[x] & m) cells.push_back(x);
                if ((int)cells.size() == k) {
                    bool all = true;
                    for (int i : di) {
                        bool any = false;
                        for (int x : cells) if (cand[x] & digs[i]) { any = true; break; }
                        if (!any) { all = false; break; }
                    }
                    if (all) {
                        int got = 0;
                        for (int x : cells) if (cand[x] & ~m) { cand[x] &= m; got = 1; }
                        if (got) return 1;
                    }
                }
                int i = k - 1;
                while (i >= 0 && di[i] == nd - k + i) --i;
                if (i < 0) break;
                ++di[i];
                for (int j = i + 1; j < k; ++j) di[j] = di[j - 1] + 1;
            }
        }
    }
    return 0;
}

int Solver::trial_depth(int c, int v) {
    std::vector<uint8_t> sv = vals;
    std::vector<uint32_t> sc = cand, sg = placed_g;
    place(c, v);
    int placed = 0;
    bool ok = basic_propagate(placed);
    vals.swap(sv);
    cand.swap(sc);
    placed_g.swap(sg);
    return ok ? -1 : placed;
}

void Solver::refute_profile(const std::vector<std::pair<int, int>>& givens, const std::vector<int>& sol, int max_stuck,
                            std::vector<std::array<int, 5>>& out) {
    init_state(givens);
    int placed = 0;
    if (!basic_propagate(placed)) return;
    for (int s = 0; s < max_stuck; ++s) {
        bool done = true;
        for (int x = 0; x < p.N; ++x)
            if (!vals[x]) { done = false; break; }
        if (done) break;
        int C = 0;
        for (int x = 0; x < p.N; ++x)
            if (!vals[x]) C += popc(cand[x]);
        std::vector<std::array<int, 3>> refs;
        for (int x = 0; x < p.N; ++x) {
            if (vals[x]) continue;
            for (uint32_t dm = cand[x]; dm; dm &= dm - 1) {
                int v = lowdigit(dm);
                int d = trial_depth(x, v);
                if (d >= 0) refs.push_back({x, v, d});
            }
        }
        if (refs.empty()) {
            if ((int)sol.size() != p.N) break;
            int best = -1, bp = 1 << 30;
            for (int x = 0; x < p.N; ++x)
                if (!vals[x] && popc(cand[x]) < bp) { bp = popc(cand[x]); best = x; }
            if (best < 0 || !(cand[best] & bit(sol[best]))) break;
            place(best, sol[best]);
            out.push_back({C, 0, 30, 1, 0});
        } else {
            int dmin = 1 << 30;
            for (auto& r : refs) dmin = std::min(dmin, r[2]);
            int n = 0;
            for (auto& r : refs)
                if (r[2] == dmin) { cand[r[0]] &= ~bit(r[1]); ++n; }
            out.push_back({C, n, dmin, 0, 0});
        }
        int pl = 0;
        if (!basic_propagate(pl)) break;
        out.back()[4] = pl;
    }
}

// Per-cell features for a learned human model for any rules: candidates after rule filtering (pair relations via
// place on the givens + n-ary arc consistency, NO placements), naked single, hidden single in a house, tightest digit (min places over its
// houses), and -- only when the board has no single anywhere -- per-cell short-trial refutations (count, shortest chain).
void Solver::cell_features(const std::vector<std::pair<int, int>>& givens, std::vector<std::array<double, 8>>& out) {
    init_state(givens);
    for (int it = 0; it < 200; ++it) {           // filtering only
        bool prog = false;
        for (const std::vector<NConstraint>* lst : {&p.nary, &p.cage_nary})
            for (const NConstraint& k : *lst) {
                if (k.nv() > 64) continue;
                uint32_t dom[64];
                nary_dom(k, dom);
                const GacOut& o = gac_cached(k, dom);
                if (!o.complete || !o.any) continue;
                for (int i = 0; i < k.nv(); ++i) {
                    int c = k.vars[i];
                    if (vals[c]) continue;
                    uint32_t nd = cand[c] & o.sup[i];
                    if (nd && nd != cand[c]) { cand[c] = nd; prog = true; }
                }
            }
        if (!prog) break;
    }
    std::vector<int> hidden(p.N, 0), tight(p.N, 99);
    bool any_single = false;
    for (int hi : p.houses)
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            uint32_t b = mm & (~mm + 1);
            int cnt = 0, last = -1;
            for (int x : p.groups[hi].cells)
                if (!vals[x] && (cand[x] & b)) { ++cnt; last = x; }
            for (int x : p.groups[hi].cells)
                if (!vals[x] && (cand[x] & b)) tight[x] = std::min(tight[x], cnt);
            if (cnt == 1) { hidden[last] = 1; any_single = true; }
        }
    for (int x = 0; x < p.N; ++x)
        if (!vals[x] && popc(cand[x]) == 1) any_single = true;
    std::vector<int> nref(p.N, 0), dref(p.N, -1);
    if (!any_single)
        for (int x = 0; x < p.N; ++x) {
            if (vals[x]) continue;
            for (uint32_t dm = cand[x]; dm; dm &= dm - 1) {
                int d = trial_depth(x, lowdigit(dm));
                if (d >= 0) { ++nref[x]; dref[x] = dref[x] < 0 ? d : std::min(dref[x], d); }
            }
        }
    for (int x = 0; x < p.N; ++x) {
        if (vals[x]) continue;
        out.push_back({(double)x, (double)popc(cand[x]), popc(cand[x]) == 1 ? 1.0 : 0.0, (double)hidden[x],
                       (double)(tight[x] == 99 ? 0 : tight[x]), (double)nref[x], (double)dref[x], any_single ? 0.0 : 1.0});
    }
}


bool Solver::k_has_single() {
    for (int x = 0; x < p.N; ++x)
        if (!vals[x] && popc(cand[x]) == 1) return true;
    for (int hi : p.houses)
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            uint32_t b = mm & (~mm + 1); int cnt = 0;
            for (int x : p.groups[hi].cells) if (!vals[x] && (cand[x] & b)) { if (++cnt > 1) break; }
            if (cnt == 1) return true;
        }
    return false;
}

// all K1 patterns (locked candidates over overlapping houses, naked / hidden pairs) that eliminate something, + the scan space
void Solver::k_patterns(std::vector<std::vector<std::pair<int, uint32_t>>>& pats, int& checks) {
    if (k_in.empty()) k_prepare();
    int H = (int)p.houses.size(); checks = 0;
    for (int a = 0; a < H; ++a) {
        if (!k_ok[a]) continue;
        int hi = p.houses[a];
        std::vector<int> fr;
        int biv = 0;
        for (int x : p.groups[hi].cells) if (!vals[x]) { fr.push_back(x); if (popc(cand[x]) == 2) ++biv; }
        if (biv >= 2) ++checks;
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            uint32_t b = mm & (~mm + 1);
            std::vector<int> w;
            for (int x : fr) if (cand[x] & b) w.push_back(x);
            if (w.size() < 2) continue;
            ++checks;
            for (int nb : k_nbr[a]) {
                bool inside = true;
                for (int x : w) if (!k_in[nb][x]) { inside = false; break; }
                if (!inside) continue;
                std::vector<std::pair<int, uint32_t>> el;
                for (int y : p.groups[p.houses[nb]].cells) if (!k_in[a][y] && !vals[y] && (cand[y] & b)) el.push_back({y, b});
                if (!el.empty()) pats.push_back(el);
            }
        }
        int n = (int)fr.size();
        for (int i = 0; i < n; ++i) for (int j = i + 1; j < n; ++j) {          // naked pairs
            uint32_t m = cand[fr[i]];
            if (popc(m) != 2 || cand[fr[j]] != m) continue;
            std::vector<std::pair<int, uint32_t>> el;
            for (int k = 0; k < n; ++k) if (k != i && k != j && (cand[fr[k]] & m)) el.push_back({fr[k], cand[fr[k]] & m});
            if (!el.empty()) pats.push_back(el);
        }
        std::vector<uint32_t> digs;                                              // hidden pairs
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) digs.push_back(mm & (~mm + 1));
        for (size_t i = 0; i < digs.size(); ++i) for (size_t j = i + 1; j < digs.size(); ++j) {
            uint32_t m = digs[i] | digs[j]; std::vector<int> cells;
            for (int x : fr) if (cand[x] & m) cells.push_back(x);
            if (cells.size() != 2) continue;
            bool both = true;
            for (uint32_t dg : {digs[i], digs[j]}) { bool any = false; for (int x : cells) if (cand[x] & dg) any = true; if (!any) both = false; }
            if (!both) continue;
            std::vector<std::pair<int, uint32_t>> el;
            for (int x : cells) if (cand[x] & ~m) el.push_back({x, cand[x] & ~m});
            if (!el.empty()) pats.push_back(el);
        }
    }
}

void Solver::finding_profile(const std::vector<std::pair<int, int>>& givens, const std::vector<int>& sol, int max_stuck,
                             std::vector<std::array<int, 5>>& out) {
    int keepK = refK; refK = 0;                    // singles + relations + GAC between stuck points
    init_state(givens);
    int placed = 0;
    if (!basic_propagate(placed)) { refK = keepK; return; }
    if (keepK >= 10) refK = keepK;                // geometry flag for k_prepare
    k_in.clear(); k_prepare(); refK = 0;
    for (int s = 0; s < max_stuck; ++s) {
        bool done = true;
        for (int x = 0; x < p.N; ++x) if (!vals[x]) { done = false; break; }
        if (done) break;
        std::vector<std::vector<std::pair<int, uint32_t>>> pats; int C = 0;
        k_patterns(pats, C);
        int U = 0, first_u = -1;
        for (size_t i = 0; i < pats.size(); ++i) {
            std::vector<uint32_t> sc = cand; bool bad = false;
            for (auto& e : pats[i]) { cand[e.first] &= ~e.second; if (!cand[e.first]) bad = true; }
            bool un = !bad && k_has_single();
            cand.swap(sc);
            if (un) { ++U; if (first_u < 0) first_u = (int)i; }
        }
        int P = (int)pats.size(), fb = 0;
        int pick = first_u >= 0 ? first_u : (P ? 0 : -1);
        if (pick >= 0) {
            for (auto& e : pats[pick]) cand[e.first] &= ~e.second;
        } else {                                   // beyond K1: shortest refutations (as refute_profile), else the solution digit
            fb = 1;
            std::vector<std::array<int, 3>> refs;
            for (int x = 0; x < p.N; ++x) {
                if (vals[x]) continue;
                for (uint32_t dm = cand[x]; dm; dm &= dm - 1) { int v = lowdigit(dm); int d = trial_depth(x, v); if (d >= 0) refs.push_back({x, v, d}); }
            }
            if (refs.empty()) {
                if ((int)sol.size() != p.N) break;
                int best = -1, bp = 1 << 30;
                for (int x = 0; x < p.N; ++x) if (!vals[x] && popc(cand[x]) < bp) { bp = popc(cand[x]); best = x; }
                if (best < 0 || !(cand[best] & bit(sol[best]))) break;
                place(best, sol[best]);
            } else {
                int dmin = 1 << 30;
                for (auto& rr : refs) dmin = std::min(dmin, rr[2]);
                for (auto& rr : refs) if (rr[2] == dmin) cand[rr[0]] &= ~bit(rr[1]);
            }
        }
        out.push_back({std::max(C, 1), P, U, fb, 0});
        int pl = 0;
        if (!basic_propagate(pl)) break;
        out.back()[4] = pl;
    }
    refK = keepK;
}

}  // namespace cs
