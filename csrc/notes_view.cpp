// Techniques on written candidates: singles, locked candidates, subsets, fish, wings, colouring, relations, innies,
// cage combinations.
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

// ---------------------------------------------------------- notes view --
void Solver::notes_singles(MoveBuf& out) {
    std::fill(seen.begin(), seen.end(), 0u);
    for (int c = 0; c < p.N; ++c) {
        if (!vals[c] && popc(cand[c]) == 1) {
            int v = lowdigit(cand[c]);
            seen[c] |= bit(v);
            Move& m = new_move(out, NAKED_N, 1.0, 0);
            m.pc = c;
            m.pv = v;
            set_meta(m, 1, 1, 1, 0, 0, 0, 0, 1, 1.0);
        }
    }
    std::vector<int> emp;
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        emp.clear();
        for (int x : g.cells)
            if (!vals[x]) emp.push_back(x);
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            int cnt = 0, c = -1;
            for (int x : emp)
                if (cand[x] & b) {
                    ++cnt;
                    c = x;
                }
            if (cnt == 1 && (canon || !(seen[c] & b))) {
                seen[c] |= b;
                Move& m = new_move(out, HIDDEN_N, g.shape, (int)emp.size());
                m.pc = c;
                m.pv = v;
                m.nk = NM_GROUP;
                m.na = hi;
                set_meta(m, (int)emp.size(), 1, 1, 0, 1, 0, 0, 1, g.shape);
            }
        }
    }
}

void Solver::locked(MoveBuf& out) {
    std::vector<int> poss, common;
    for (int bi : p.houses) {
        const Group& B = p.groups[bi];
        for (uint32_t mm = p.full & ~placed_g[bi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            poss.clear();
            for (int c : B.cells)
                if (!vals[c] && (cand[c] & b)) poss.push_back(c);
            if (poss.size() < 2) continue;
            common_groups(poss, bi, common);
            for (int ai : common) {
                const Group& A = p.groups[ai];
                double shp = py_pow(B.shape * A.shape, 0.5);
                size_t mark = out.elims.size();
                int n = 0;
                for (int c : A.cells)
                    if (!tbit(p.gbits(bi), c) && (cand[c] & b)) {
                        out.elims.push_back((uint32_t)c * 32u + v);
                        ++n;
                    }
                if (!n) continue;
                out.elims.resize(mark);
                Move& m = new_move(out, LOCKED, shp, (int)poss.size());
                for (int c : A.cells)
                    if (!tbit(p.gbits(bi), c) && (cand[c] & b)) add_elim(out, m, c, v);
                m.nk = NM_LOCK;
                m.na = bi;
                m.nb = ai;
                set_pattern(out, m, poss);
                set_meta(m, (int)poss.size(), 2, 1, 0, 1, A.has_total ? 1 : 0, 0, 1, shp);
            }
        }
    }
}

void Solver::subsets(MoveBuf& out, int k) {
    static const int NT[5] = {0, 0, NPAIR, NTRIPLE, NQUAD}, HT[5] = {0, 0, HPAIR, HTRIPLE, HQUAD};
    const int nt = NT[k], ht = HT[k];
    std::vector<int> emp, small, cands;
    uint32_t pos[33];
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        emp.clear();
        for (int x : g.cells)
            if (!vals[x]) emp.push_back(x);
        if ((int)emp.size() <= k) continue;
        small.clear();
        for (int c : emp) {
            int pc = popc(cand[c]);
            if (pc >= 2 && pc <= k) small.push_back(c);
        }
        for_combos((int)small.size(), k, [&](const int* idx) {
            uint32_t u = 0;
            for (int i = 0; i < k; ++i) u |= cand[small[idx[i]]];
            if (popc(u) != k) return false;
            int n = 0;
            for (int c : emp) {
                bool in = false;
                for (int i = 0; i < k; ++i) in |= small[idx[i]] == c;
                if (!in) n += popc(cand[c] & u);
            }
            if (!n) return false;
            Move& m = new_move(out, nt, g.shape, (int)emp.size());
            for (int c : emp) {
                bool in = false;
                for (int i = 0; i < k; ++i) in |= small[idx[i]] == c;
                if (in) continue;
                for (uint32_t dm = cand[c] & u; dm; dm &= dm - 1) add_elim(out, m, c, lowdigit(dm));
            }
            m.nk = NM_GROUP;
            m.na = hi;
            {
                std::vector<int> pc;
                for (int i = 0; i < k; ++i) pc.push_back(small[idx[i]]);
                set_pattern(out, m, pc);
            }
            set_meta(m, k, 1, k, 0, 0, 0, 0, 1, g.shape);
            return false;
        });
        cands.clear();
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int d = lowdigit(mm);
            uint32_t pm = 0;
            for (size_t i = 0; i < emp.size(); ++i)
                if (cand[emp[i]] & bit(d)) pm |= 1u << i;
            pos[d] = pm;
            int n = popc(pm);
            if (n >= 2 && n <= k) cands.push_back(d);
        }
        for_combos((int)cands.size(), k, [&](const int* idx) {
            uint32_t cells = 0, keep = 0;
            for (int i = 0; i < k; ++i) {
                cells |= pos[cands[idx[i]]];
                keep |= bit(cands[idx[i]]);
            }
            if (popc(cells) != k) return false;
            int n = 0;
            for (uint32_t cm = cells; cm; cm &= cm - 1) n += popc(cand[emp[__builtin_ctz(cm)]] & ~keep);
            if (!n) return false;
            Move& m = new_move(out, ht, g.shape, (int)emp.size());
            for (uint32_t cm = cells; cm; cm &= cm - 1) {
                int c = emp[__builtin_ctz(cm)];
                for (uint32_t dm = cand[c] & ~keep; dm; dm &= dm - 1) add_elim(out, m, c, lowdigit(dm));
            }
            m.nk = NM_GROUP;
            m.na = hi;
            {
                std::vector<int> pc;
                for (uint32_t cm = cells; cm; cm &= cm - 1) pc.push_back(emp[__builtin_ctz(cm)]);
                set_pattern(out, m, pc);
            }
            set_meta(m, k, 1, k, 0, 1, 0, 0, 1, g.shape);
            return false;
        });
    }
}

void Solver::fish(MoveBuf& out, int k) {
    const int tech = k == 2 ? XWING : SWORDFISH;
    const int W = p.W, H = (int)p.houses.size();
    std::vector<uint64_t> pos((size_t)H * W);
    std::vector<int> cnt(H), bases, covers;
    std::vector<uint64_t> U(W), CU(W);
    int combo[4], cov[4];
    auto ov = [&](int a, int b) { return p.group_overlap[(size_t)p.houses[a] * p.G + p.houses[b]] != 0; };
    for (int v = 1; v <= p.D; ++v) {
        uint32_t b = bit(v);
        for (int h = 0; h < H; ++h) {
            uint64_t* ph = &pos[(size_t)h * W];
            std::fill(ph, ph + W, 0);
            int n = 0;
            for (int c : p.groups[p.houses[h]].cells)
                if (!vals[c] && (cand[c] & b)) {
                    sbit(ph, c);
                    ++n;
                }
            cnt[h] = n;
        }
        bases.clear();
        for (int h = 0; h < H; ++h)
            if (cnt[h] >= 2 && cnt[h] <= k) bases.push_back(h);
        // combinations(bases, k), skipping overlapping (same order, pruned)
        std::function<void(int, int)> pick_base;
        std::function<void(int, int)> pick_cov;
        pick_cov = [&](int start, int depth) {
            if (depth == k) {
                std::fill(CU.begin(), CU.end(), 0);
                for (int i = 0; i < k; ++i) {
                    const uint64_t* gb = p.gbits(p.houses[cov[i]]);
                    for (int w = 0; w < W; ++w) CU[w] |= gb[w];
                }
                for (int w = 0; w < W; ++w)
                    if (U[w] & ~CU[w]) return;
                size_t mark = out.elims.size();
                // el = {(c,v) for h in cov for c in pos[h] if c not in U} (deduped)
                std::vector<uint64_t> elb(W, 0);
                for (int i = 0; i < k; ++i) {
                    const uint64_t* ph = &pos[(size_t)cov[i] * W];
                    for (int w = 0; w < W; ++w) elb[w] |= ph[w] & ~U[w];
                }
                bool any = false;
                for (int w = 0; w < W; ++w) any |= elb[w] != 0;
                if (!any) return;
                CompSum s;
                for (int i = 0; i < k; ++i) s.add(p.groups[p.houses[combo[i]]].shape);
                for (int i = 0; i < k; ++i) s.add(p.groups[p.houses[cov[i]]].shape);
                double shp = s.value() / (2 * k);
                int nU = 0;
                for (int w = 0; w < W; ++w) nU += __builtin_popcountll(U[w]);
                (void)mark;
                Move& m = new_move(out, tech, shp, k);
                for (int c = 0; c < p.N; ++c)
                    if (tbit(elb.data(), c)) add_elim(out, m, c, v);
                {
                    std::vector<int> bs, cs3;
                    for (int i = 0; i < k; ++i) {
                        bs.push_back(p.houses[combo[i]]);
                        cs3.push_back(p.houses[cov[i]]);
                    }
                    add_expl(out, m, EX_BASE, bs);
                    add_expl(out, m, EX_COVER, cs3);
                }
                {
                    std::vector<int> pc;
                    for (int c = 0; c < p.N; ++c)
                        if (tbit(U.data(), c)) pc.push_back(c);
                    set_pattern(out, m, pc);
                }
                set_meta(m, nU, 2 * k, 1, 0, 1, 0, 0, 1, shp);
                return;
            }
            for (int i = start; i < (int)covers.size(); ++i) {
                int h = covers[i];
                bool bad = false;
                for (int j = 0; j < depth && !bad; ++j) bad = ov(cov[j], h);
                if (bad) continue;
                cov[depth] = h;
                pick_cov(i + 1, depth + 1);
            }
        };
        pick_base = [&](int start, int depth) {
            if (depth == k) {
                std::fill(U.begin(), U.end(), 0);
                for (int i = 0; i < k; ++i) {
                    const uint64_t* ph = &pos[(size_t)combo[i] * W];
                    for (int w = 0; w < W; ++w) U[w] |= ph[w];
                }
                covers.clear();
                for (int h = 0; h < H; ++h) {
                    bool inc = false;
                    for (int i = 0; i < k; ++i) inc |= combo[i] == h;
                    if (inc) continue;
                    const uint64_t* ph = &pos[(size_t)h * W];
                    bool hit = false;
                    for (int w = 0; w < W && !hit; ++w) hit = ph[w] & U[w];
                    if (hit) covers.push_back(h);
                }
                pick_cov(0, 0);
                return;
            }
            for (int i = start; i < (int)bases.size(); ++i) {
                int h = bases[i];
                bool bad = false;
                for (int j = 0; j < depth && !bad; ++j) bad = ov(combo[j], h);
                if (bad) continue;
                combo[depth] = h;
                pick_base(i + 1, depth + 1);
            }
        };
        pick_base(0, 0);
    }
}

void Solver::xywing(MoveBuf& out, bool xyz) {
    const int need = xyz ? 3 : 2;
    const int W = p.W;
    std::vector<int> wings;
    std::vector<uint64_t> T(W);
    for (int piv = 0; piv < p.N; ++piv) {
        if (vals[piv] || popc(cand[piv]) != need) continue;
        uint32_t pc = cand[piv];
        wings.clear();
        for (int q : p.peer_list[piv])
            if (!vals[q] && popc(cand[q]) == 2) wings.push_back(q);
        for (size_t i = 0; i < wings.size(); ++i)
            for (size_t j = i + 1; j < wings.size(); ++j) {
                int w1 = wings[i], w2 = wings[j];
                uint32_t a = cand[w1], b2 = cand[w2], z;
                if (xyz) {
                    if (!((a | b2) == pc) || a == b2 || !((a & pc) == a) || !((b2 & pc) == b2)) continue;
                    z = a & b2;
                    if (popc(z) != 1) continue;
                    for (int w = 0; w < W; ++w) T[w] = p.peers(piv)[w] & p.peers(w1)[w] & p.peers(w2)[w];
                } else {
                    if (a == b2 || popc(a & b2) != 1) continue;
                    z = a & b2;
                    if (((a | b2) & ~z) != pc || (pc & z)) continue;
                    for (int w = 0; w < W; ++w) T[w] = p.peers(w1)[w] & p.peers(w2)[w];
                }
                int zd = lowdigit(z);
                int n = 0;
                for (int c = 0; c < p.N; ++c)
                    if (tbit(T.data(), c) && c != piv && c != w1 && c != w2 && !vals[c] && (cand[c] & z)) ++n;
                if (!n) continue;
                double shp = pspread({piv, w1, w2});
                Move& m = new_move(out, xyz ? XYZWING : XYWING, shp, 0);
                for (int c = 0; c < p.N; ++c)
                    if (tbit(T.data(), c) && c != piv && c != w1 && c != w2 && !vals[c] && (cand[c] & z))
                        add_elim(out, m, c, zd);
                set_pattern(out, m, {piv, w1, w2});
                set_meta(m, 3, xyz ? 3 : 2, 3, 2, 0, 0, 0, 1, shp);
            }
    }
}

void Solver::coloring(MoveBuf& out) {
    const int W = p.W;
    std::vector<int> adj_order;
    std::vector<int> adj_idx(p.N, -1);
    std::vector<PySet> adj;
    std::vector<char> color_seen(p.N), in_comp(p.N);
    std::vector<int> comp_order, comp_col(p.N), stack;
    std::vector<uint64_t> g0(W), g1(W);
    for (int v = 1; v <= p.D; ++v) {
        uint32_t b = bit(v);
        for (int c : adj_order) adj_idx[c] = -1;
        adj_order.clear();
        adj.clear();
        auto link = [&](int x, int y) {
            if (adj_idx[x] < 0) {
                adj_idx[x] = (int)adj.size();
                adj.emplace_back();
                adj_order.push_back(x);
            }
            adj[adj_idx[x]].add(y);
        };
        for (int hi : p.houses) {
            int n = 0, cs2[2] = {-1, -1};
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & b)) {
                    if (n < 2) cs2[n] = c;
                    ++n;
                }
            if (n == 2) {
                link(cs2[0], cs2[1]);
                link(cs2[1], cs2[0]);
            }
        }
        std::fill(color_seen.begin(), color_seen.end(), 0);
        for (int start : adj_order) {
            if (color_seen[start]) continue;
            for (int c : comp_order) in_comp[c] = 0;
            comp_order.clear();
            comp_order.push_back(start);
            in_comp[start] = 1;
            comp_col[start] = 0;
            stack.assign(1, start);
            while (!stack.empty()) {
                int x = stack.back();
                stack.pop_back();
                adj[adj_idx[x]].for_each([&](int64_t yy) {
                    int y = (int)yy;
                    if (!in_comp[y]) {
                        in_comp[y] = 1;
                        comp_col[y] = 1 - comp_col[x];
                        comp_order.push_back(y);
                        stack.push_back(y);
                    }
                });
            }
            for (int c : comp_order) color_seen[c] = 1;
            if (comp_order.size() < 4) continue;
            std::vector<int> grp[2];
            std::fill(g0.begin(), g0.end(), 0);
            std::fill(g1.begin(), g1.end(), 0);
            for (int c : comp_order) {
                grp[comp_col[c]].push_back(c);
                sbit(comp_col[c] ? g1.data() : g0.data(), c);
            }
            std::vector<int> el;
            int wrap_side = -1, clash_a = -1, clash_b = -1;
            for (int side = 0; side < 2; ++side) {
                const auto& s = grp[side];
                bool wrap = false;
                for (size_t i = 0; i < s.size() && !wrap; ++i)
                    for (size_t j = i + 1; j < s.size() && !wrap; ++j)
                        if (tbit(p.peers(s[i]), s[j])) {
                            wrap = true;
                            clash_a = s[i];
                            clash_b = s[j];
                        }
                if (wrap) {
                    el = s;
                    wrap_side = side;
                    break;
                }
            }
            if (el.empty()) {
                for (int c = 0; c < p.N; ++c) {
                    if (vals[c] || in_comp[c] || !(cand[c] & b)) continue;
                    const uint64_t* pc = p.peers(c);
                    bool a0 = false, a1 = false;
                    for (int w = 0; w < W; ++w) {
                        a0 |= (pc[w] & g0[w]) != 0;
                        a1 |= (pc[w] & g1[w]) != 0;
                    }
                    if (a0 && a1) el.push_back(c);
                }
            }
            if (!el.empty()) {
                std::vector<std::pair<int, int>> co;
                for (int c : comp_order) co.push_back(p.coords[c]);
                int n = (int)comp_order.size();
                Move& m = new_move(out, COLORING, 1.0, n);
                for (int c : el) add_elim(out, m, c, v);
                set_pattern(out, m, comp_order);
                set_meta(m, n, n - 1, 1, n - 1, 1, 0, 0, 1, pspread(comp_order));
                std::vector<int> rec{v, wrap_side >= 0, wrap_side, clash_a, clash_b, (int)grp[0].size()};
                rec.insert(rec.end(), grp[0].begin(), grp[0].end());
                rec.insert(rec.end(), grp[1].begin(), grp[1].end());
                add_expl(out, m, EX_COLOR, rec);
            }
        }
        for (int c : comp_order) in_comp[c] = 0;
        comp_order.clear();
    }
}

// _relation_pointing
void Solver::relation_pointing(MoveBuf& out) {
    const int W = p.W;
    std::vector<int> poss;
    std::vector<uint64_t> cr(W);
    for (int bi : p.houses) {
        const Group& B = p.groups[bi];
        for (uint32_t mm = p.full & ~placed_g[bi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            poss.clear();
            for (int c : B.cells)
                if (!vals[c] && (cand[c] & b)) poss.push_back(c);
            if (poss.size() < 2) continue;
            for (int gen = 1; gen >= 0; --gen) {
                const std::vector<int>& L0 = gen ? p.rel[poss[0]] : p.neq[poss[0]];
                if (L0.empty()) continue;
                const uint64_t* b0 = gen ? p.relb(poss[0]) : p.neqb(poss[0]);
                for (int w = 0; w < W; ++w) cr[w] = b0[w];
                for (size_t i = 1; i < poss.size(); ++i) {
                    const uint64_t* bc = gen ? p.relb(poss[i]) : p.neqb(poss[i]);
                    for (int w = 0; w < W; ++w) cr[w] &= bc[w];
                }
                int mi = -1;
                for (int x = 0; x < p.N; ++x) {
                    if (!tbit(cr.data(), x)) continue;
                    if (vals[x] || std::find(poss.begin(), poss.end(), x) != poss.end()) continue;
                    uint32_t rm = b;
                    if (gen) {
                        rm = p.full;
                        for (int c : poss) rm &= p.rel_ex(c, x)[v];
                    }
                    uint32_t dm = cand[x] & rm;
                    if (!dm) continue;
                    if (mi < 0) {
                        Move& m0 = new_move(out, PAIRARC, B.shape, (int)poss.size());
                        mi = (int)out.moves.size() - 1;
                        (void)m0;
                    }
                    Move& m = out.moves[mi];
                    for (; dm; dm &= dm - 1) add_elim(out, m, x, lowdigit(dm));
                }
                if (mi >= 0) {
                    Move& m = out.moves[mi];
                    m.nk = NM_GROUP;
                    m.na = bi;
                    set_pattern(out, m, poss);
                    set_meta(m, (int)poss.size() + 1, 2, 1, 0, 1, 0, 1, 1, B.shape);
                }
            }
        }
    }
}

// _pairarc
void Solver::pairarc(MoveBuf& out) {
    relation_pointing(out);
    const int D1 = p.D + 1;
    for (int a = 0; a < p.N; ++a) {
        if (vals[a] || p.rel[a].empty()) continue;
        uint32_t ca = cand[a];
        for (size_t j = 0; j < p.rel[a].size(); ++j) {
            int b_ = p.rel[a][j];
            if (vals[b_]) continue;
            const uint32_t* tab = &p.rel_in[a][j * D1];  // rel_ex[b_][a]
            int mi = -1;
            for (uint32_t dm = cand[b_]; dm; dm &= dm - 1) {
                int v = lowdigit(dm);
                uint32_t nb = tab[v];
                if (ca && (ca & ~nb) == 0) {
                    if (mi < 0) {
                        new_move(out, PAIRARC, 1.0, popc(ca));
                        mi = (int)out.moves.size() - 1;
                    }
                    add_elim(out, out.moves[mi], b_, v);
                }
            }
            if (mi >= 0) set_meta(out.moves[mi], 2, 1, std::min(popc(ca) + 1, p.D), 0, 0, 0, 1, 1, 1.0);
        }
    }
}

// _innies
void Solver::innies(MoveBuf& out, bool notes) {
    std::vector<int> emp, common;
    uint32_t masks[32], allowed[32];
    for (const InnieSet& s : p.innies) {
        emp.clear();
        int rem = s.total;
        for (int c : s.cells) {
            if (!vals[c]) emp.push_back(c);
            rem -= vals[c];
        }
        if (emp.empty()) continue;
        const Group& H = p.groups[s.hi];
        int ncells = 0;
        for (int gi : s.cages) ncells += (int)p.groups[gi].cells.size();
        const int nc = (int)s.cages.size();
        if (!notes) {
            if (emp.size() == 1 && 1 <= rem && rem <= p.D) {
                Move& m = new_move(out, INNIE_D, H.shape, nc);
                for (int i = 0; i < nc; ++i) out.covers.push_back({K_CAGESUM, p.groups[s.cages[i]].shape, i + 1});
                m.cov_n = nc;
                m.pc = emp[0];
                m.pv = rem;
                m.nk = s.outie ? NM_OUTIE : NM_INNIE;
                m.na = s.hi;
                set_meta(m, ncells, nc + 1, 1, 0, 0, 1, 0, 0, H.shape);
                region_expl(out, m, s);
            }
            continue;
        }
        common_groups(emp, -1, common);
        bool distinct = !common.empty();
        for (size_t i = 0; i < emp.size(); ++i) masks[i] = cand[emp[i]];
        combo_allowed(emp, rem, distinct, masks, 0, allowed);
        int n = 0;
        for (size_t i = 0; i < emp.size(); ++i) n += popc(cand[emp[i]] & ~allowed[i]);
        if (!n) continue;
        Move& m = new_move(out, INNIE_N, H.shape, nc);
        for (size_t i = 0; i < emp.size(); ++i)
            for (uint32_t dm = cand[emp[i]] & ~allowed[i]; dm; dm &= dm - 1) add_elim(out, m, emp[i], lowdigit(dm));
        m.nk = s.outie ? NM_OUTIE : NM_INNIE;
        m.na = s.hi;
        set_pattern(out, m, emp);
        set_meta(m, ncells, nc + 1, (int)emp.size(), 0, 0, 1, 0, 1, H.shape);
        region_expl(out, m, s);
    }
}

// _cage_combo
void Solver::cage_combo(MoveBuf& out) {
    std::vector<int> emp;
    uint32_t masks[32], allowed[32];
    for (int gi : p.sum_cages) {
        const Group& g = p.groups[gi];
        emp.clear();
        int rem = g.total;
        for (int c : g.cells) {
            if (!vals[c]) emp.push_back(c);
            rem -= vals[c];
        }
        if (emp.empty()) continue;
        for (size_t i = 0; i < emp.size(); ++i) masks[i] = cand[emp[i]];
        {  // cached while the cage's empty-cell candidates are unchanged
            auto& cc = combo_cache[gi];
            std::vector<uint32_t> key(masks, masks + emp.size());
            key.push_back((uint32_t)rem);
            key.push_back(placed_g[gi]);
            if (cc.first == key) {
                std::copy(cc.second.begin(), cc.second.end(), allowed);
            } else {
                combo_allowed(emp, rem, true, masks, placed_g[gi], allowed);
                cc.first = key;
                cc.second.assign(allowed, allowed + emp.size());
            }
        }
        int n = 0;
        for (size_t i = 0; i < emp.size(); ++i) n += popc(cand[emp[i]] & ~allowed[i]);
        if (!n) continue;
        Move& m = new_move(out, CAGE_COMBO, g.shape, (int)emp.size());
        for (size_t i = 0; i < emp.size(); ++i)
            for (uint32_t dm = cand[emp[i]] & ~allowed[i]; dm; dm &= dm - 1) add_elim(out, m, emp[i], lowdigit(dm));
        m.nk = NM_GROUP;
        m.na = gi;
        set_pattern(out, m, emp);
        set_meta(m, (int)emp.size(), 1, (int)emp.size(), 0, 0, 1, 0, 1, g.shape);
    }
}

}  // namespace cs
