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
        const std::vector<uint32_t>* ref = gac_ref;     // consistent state: unchanged cells / houses hold no single
        for (int x = 0; x < p.N; ++x) {
            if (vals[x] || (ref && cand[x] == (*ref)[x])) continue;
            if (!cand[x]) return false;
            if (popc(cand[x]) == 1) {
                place(x, lowdigit(cand[x]));
                if (++placed > prop_cap) return true;
                prog = true;
            }
        }
        for (int hi : p.houses) {
            if (ref) {
                bool dirty = false;
                for (int x : p.groups[hi].cells) if (cand[x] != (*ref)[x]) { dirty = true; break; }
                if (!dirty) continue;
            }
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
                    if (++placed > prop_cap) return true;
                    prog = true;
                }
            }
        }
        for (const std::vector<NConstraint>* lst : {&p.nary, &p.cage_nary}) {
            for (const NConstraint& k : *lst) {
                if (k.nv() > 64) continue;
                if (gac_ref) {               // unchanged since a consistent state: nothing new to find
                    bool dirty = false;
                    for (int i = 0; i < k.nv() && !dirty; ++i) dirty = cand[k.vars[i]] != (*gac_ref)[k.vars[i]];
                    if (!dirty) continue;
                }
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

// placements until a contradiction, or -1 when there is none within `cap` placements (a deeper refutation counts as none)
int Solver::trial_depth(int c, int v, int cap) {
    std::vector<uint8_t> sv = vals;
    std::vector<uint32_t> sc = cand, sg = placed_g;
    place(c, v);
    int placed = 0;
    const int cap0 = prop_cap;
    prop_cap = cap;
    bool ok = basic_propagate(placed);
    prop_cap = cap0;
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
        if (deadline_passed()) return;             // max_seconds (the caller reports band "Unknown")
        bool done = true;
        for (int x = 0; x < p.N; ++x)
            if (!vals[x]) { done = false; break; }
        if (done) break;
        int C = 0;
        for (int x = 0; x < p.N; ++x)
            if (!vals[x]) C += popc(cand[x]);
        // only the shortest refutations are used: trials stop once they are longer than the shortest found so far, and the
        // most constrained cells go first so short ones turn up early (same output, far fewer propagations)
        std::vector<std::array<int, 3>> refs;
        std::vector<int> order;
        for (int x = 0; x < p.N; ++x)
            if (!vals[x]) order.push_back(x);
        std::stable_sort(order.begin(), order.end(), [&](int a, int b) { return popc(cand[a]) < popc(cand[b]); });
        int best = 1 << 30;
        const std::vector<uint32_t> ref = cand;    // a fixpoint of basic_propagate: every rule is consistent with it
        gac_ref = &ref;
        for (int x : order) {
            if (deadline_passed()) { gac_ref = nullptr; return; }
            for (uint32_t dm = cand[x]; dm; dm &= dm - 1) {
                int v = lowdigit(dm);
                int d = trial_depth(x, v, best);
                if (d >= 0) {
                    refs.push_back({x, v, d});
                    best = std::min(best, d);
                }
            }
        }
        gac_ref = nullptr;
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

}  // namespace cs
