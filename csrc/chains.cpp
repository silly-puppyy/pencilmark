// Generalized fish and alternating inference chains (no Python reference).
#include <algorithm>
#include "portable.hpp"
#include <cmath>
#include <functional>
#include <set>
#include <unordered_set>

#include "solver.hpp"

namespace cs {

namespace {
inline void set_meta9(Move& m, int a, int b, int c, int d, int e, int f, int g, int h, double sp) {
    m.has_meta = true;
    m.meta[0] = a; m.meta[1] = b; m.meta[2] = c; m.meta[3] = d;
    m.meta[4] = e; m.meta[5] = f; m.meta[6] = g; m.meta[7] = h;
    m.spread = sp;
}
}  // namespace

// ------------------------------------------------------ generalized fish --
// Base sets: n pairwise-disjoint complete groups with >= 2 candidates of v;
// cover sets: n pairwise-disjoint complete groups (not bases) meeting them.
// fins = base candidates outside the covers. Finless: v leaves cover cells
// outside the bases. Finned (1..3 fins): only cover cells (outside bases) that
// see every fin. Kind: basic (lines vs lines), franken (boxes allowed on one
// orientation), mutant (anything; size 2 only).
// code = 1000 + 100*n + 10*kind + fin(0 none, 1 finned, 2 sashimi)
void Solver::gfish(MoveBuf& out, int n, bool finless, bool finned) {
    finless = finless && !disabled[JELLYFISH];
    finned = finned && !disabled[FINNED_FISH];
    if (!finless && !finned) return;
    const int W = p.W, H = (int)p.houses.size();
    std::vector<uint64_t> pos((size_t)H * W);
    std::vector<int> cnt(H), bases, covers;
    std::vector<uint64_t> U(W), CU(W), fins(W), tg(W);
    int combo[4], cov[4];
    std::set<std::vector<uint32_t>> seen_el;
    auto ov = [&](int a, int b) { return p.group_overlap[(size_t)p.houses[a] * p.G + p.houses[b]] != 0; };
    auto line = [&](int h) { return p.group_line[p.houses[h]]; };
    for (int v = 1; v <= p.D; ++v) {
        const uint32_t b = bit(v);
        for (int h = 0; h < H; ++h) {
            uint64_t* ph = &pos[(size_t)h * W];
            std::fill(ph, ph + W, 0);
            int k = 0;
            for (int c : p.groups[p.houses[h]].cells)
                if (!vals[c] && (cand[c] & b)) {
                    sbit(ph, c);
                    ++k;
                }
            cnt[h] = k;
        }
        bases.clear();
        // base houses with at most n + 3 candidates (<= 3 fins in total; a
        // count-based, symmetry-invariant cap that keeps 25x25 tractable)
        for (int h = 0; h < H; ++h)
            if (cnt[h] >= 2 && cnt[h] <= n + 3) bases.push_back(h);
        std::function<void(int, int)> pick_cov, pick_base;
        std::vector<int> cov_suf, take;
        std::vector<std::vector<uint64_t>> CU_part(5, std::vector<uint64_t>(W, 0));
        const int maxfins = finned ? 3 : 0;
        auto cover_take = [&](int h) {
            int t = 0;
            const uint64_t* ph = &pos[(size_t)h * W];
            for (int w = 0; w < W; ++w) t += __builtin_popcountll(ph[w] & U[w]);
            return t;
        };
        int base_types = 0;  // bit0 row, bit1 col, bit2 other
        pick_cov = [&](int start, int depth) {
            if (depth == n) {
                std::fill(CU.begin(), CU.end(), 0);
                for (int i = 0; i < n; ++i) {
                    const uint64_t* gb = p.gbits(p.houses[cov[i]]);
                    for (int w = 0; w < W; ++w) CU[w] |= gb[w];
                }
                int nf = 0;
                for (int w = 0; w < W; ++w) {
                    fins[w] = U[w] & ~CU[w];
                    nf += __builtin_popcountll(fins[w]);
                }
                if (nf == 0 && !finless) return;
                if (nf > 0 && (!finned || nf > 3)) return;
                // targets: cover candidates outside the bases (seeing all fins)
                int cover_types = 0;
                for (int i = 0; i < n; ++i) cover_types |= 1 << line(cov[i]);
                int kind;
                if ((base_types == 1 && cover_types == 2) || (base_types == 2 && cover_types == 1))
                    kind = 0;
                else if (((base_types & 2) == 0 && (cover_types & 1) == 0) ||
                         ((base_types & 1) == 0 && (cover_types & 2) == 0))
                    kind = 1;
                else
                    kind = 2;
                if (kind == 2 && n > 2) return;
                std::fill(tg.begin(), tg.end(), 0);
                for (int i = 0; i < n; ++i) {
                    const uint64_t* ph = &pos[(size_t)cov[i] * W];
                    for (int w = 0; w < W; ++w) tg[w] |= ph[w] & ~U[w];
                }
                if (nf)
                    for (int c = 0; c < p.N; ++c)
                        if (tbit(fins.data(), c)) {
                            const uint64_t* pc = p.peers(c);
                            for (int w = 0; w < W; ++w) tg[w] &= pc[w];
                        }
                std::vector<uint32_t> el;
                for (int c = 0; c < p.N; ++c)
                    if (tbit(tg.data(), c)) el.push_back((uint32_t)c * 32u + v);
                if (el.empty()) return;
                int tech = nf ? FINNED_FISH : JELLYFISH;
                std::vector<uint32_t> key = el;
                key.push_back(tech);
                // reference mode keeps the first fish per elimination set; canonical
                // mode lists all and keeps the cheapest (canon_dedupe)
                if (!canon && !seen_el.insert(key).second) return;
                bool sashimi = false;
                if (nf)
                    for (int i = 0; i < n; ++i) {
                        int left = 0;
                        const uint64_t* ph = &pos[(size_t)combo[i] * W];
                        for (int w = 0; w < W; ++w) left += __builtin_popcountll(ph[w] & ~fins[w]);
                        if (left <= 1) sashimi = true;
                    }
                CompSum s;
                for (int i = 0; i < n; ++i) s.add(p.groups[p.houses[combo[i]]].shape);
                for (int i = 0; i < n; ++i) s.add(p.groups[p.houses[cov[i]]].shape);
                double shp = s.value() / (2 * n);
                int nU = 0;
                for (int w = 0; w < W; ++w) nU += __builtin_popcountll(U[w]);
                Move& m = out.moves.emplace_back();
                m.tech = tech;
                m.shape = shp;
                m.extra = n;
                m.cov_off = (int)out.covers.size();
                m.el_off = (int)out.elims.size();
                for (uint32_t e : el) out.elims.push_back(e);
                m.el_n = (int)el.size();
                {
                    std::vector<int> pc;
                    for (int x = 0; x < p.N; ++x)
                        if (tbit(U.data(), x)) pc.push_back(x);
                    set_pattern(out, m, pc);
                    std::vector<int> bs, cs3;
                    for (int i = 0; i < n; ++i) {
                        bs.push_back(p.houses[combo[i]]);
                        cs3.push_back(p.houses[cov[i]]);
                    }
                    add_expl(out, m, EX_BASE, bs);
                    add_expl(out, m, EX_COVER, cs3);
                }
                set_meta9(m, nU + nf, 2 * n, 1, 0, 1, 0, 0, 1, shp);
                m.code = 1000 + 100 * n + 10 * kind + (nf ? (sashimi ? 2 : 1) : 0);
                pm_long xm[XM_N] = {n, nf, sashimi, kind, (pm_long)el.size(), v, nU, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
                return;
            }
            // bound: base candidates still uncovered minus the most the
            // remaining covers could take must fit the fin allowance
            int unc = 0;
            for (int w = 0; w < W; ++w) unc += __builtin_popcountll(U[w] & ~CU_part[depth][w]);
            for (int i = start; i < (int)covers.size(); ++i) {
                if (unc - (n - depth) * cov_suf[i] > maxfins) break;
                int h = covers[i];
                bool bad = false;
                for (int j = 0; j < depth && !bad; ++j) bad = ov(cov[j], h);
                if (bad) continue;
                cov[depth] = h;
                const uint64_t* gb = p.gbits(p.houses[h]);
                for (int w = 0; w < W; ++w) CU_part[depth + 1][w] = CU_part[depth][w] | gb[w];
                pick_cov(i + 1, depth + 1);
            }
        };
        pick_base = [&](int start, int depth) {
            if (depth == n) {
                std::fill(U.begin(), U.end(), 0);
                base_types = 0;
                for (int i = 0; i < n; ++i) {
                    const uint64_t* ph = &pos[(size_t)combo[i] * W];
                    for (int w = 0; w < W; ++w) U[w] |= ph[w];
                    base_types |= 1 << line(combo[i]);
                }
                if (n > 2 && (base_types & 3) == 3) return;  // would be mutant
                covers.clear();
                for (int h = 0; h < H; ++h) {
                    bool inb = false;
                    for (int i = 0; i < n; ++i) inb |= combo[i] == h;
                    if (inb) continue;
                    const uint64_t* ph = &pos[(size_t)h * W];
                    bool hit = false;
                    for (int w = 0; w < W && !hit; ++w) hit = ph[w] & U[w];
                    if (hit) covers.push_back(h);
                }
                // covers sorted by how many base candidates they take (desc), so
                // the suffix maximum is the bound; order only affects which of
                // equivalent fish is listed first
                take.resize(H);
                for (int h : covers) take[h] = cover_take(h);
                std::stable_sort(covers.begin(), covers.end(), [&](int a, int b2) { return take[a] > take[b2]; });
                cov_suf.assign(covers.size() + 1, 0);
                for (int i = (int)covers.size() - 1; i >= 0; --i)
                    cov_suf[i] = std::max(cov_suf[i + 1], take[covers[i]]);
                std::fill(CU_part[0].begin(), CU_part[0].end(), 0);
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

// --------------------------------------------------------------- chains --
// Link graph over candidates (cell, digit):
//   strong (at least one true): bivalue cell (1); digit with exactly two
//     cells in a complete group (2); digit that a constraint must contain with
//     exactly two scope cells (3); pair-relation table forcing (4): every other
//     candidate of a leaves b only w;
//   weak (not both true): same cell; same digit in peer cells (shared group or
//     neq); pair-relation exclusion.
// BFS over (node, true/false) from every start gives shortest AICs A=..=Z:
// candidates weakly linked to both ends go; A=..=A is a discontinuous nice
// loop (A true).
namespace {
enum { CODE_SKY = 1, CODE_2SK, CODE_TUR, CODE_XCH, CODE_XYC, CODE_RMP, CODE_WWG, CODE_AIC, CODE_DNL, CODE_GXC,
       CODE_GAIC, CODE_ER };
}

void Solver::build_aic(int maxl, bool with_als) {
    pm_long& ver = with_als ? aicx_version : aic_version;
    int& dep = with_als ? aicx_depth : aic_depth;
    MoveBuf& ob = with_als ? aicx_buf : aic_buf;
    std::vector<int>& ol = with_als ? aicx_len : aic_len;
    if (ver == version && dep >= maxl) return;
    ver = version;
    dep = maxl;
    ob.clear();
    ol.clear();
    const int N = p.N, D1 = p.D + 1;
    std::vector<int> nid((size_t)N * 32, -1);
    std::vector<std::pair<int, int>> node;
    for (int c = 0; c < N; ++c)
        if (!vals[c])
            for (uint32_t m = cand[c]; m; m &= m - 1) {
                int v = lowdigit(m);
                nid[(size_t)c * 32 + v] = (int)node.size();
                node.push_back({c, v});
            }
    const int Mc = (int)node.size();  // candidate nodes; ALS nodes (cell = -1 - als) follow
    if (Mc < 4) return;
    std::vector<int> als_first;  // first node of each ALS used as chain node (-1: none)
    if (with_als) {
        build_als();
        als_first.assign(als.size(), -1);
        // ALS of 2 cells always; 3-cell ALS only if the whole size class fits the
        // node budget (all-or-none per size: invariant under symmetry)
        for (size_t sz = 2; sz <= 3; ++sz) {
            size_t need = 0;
            for (auto& a : als)
                if (a.list.size() == sz) need += popc(a.cand);
            if (node.size() + need > (size_t)Mc + 6000) break;
            for (size_t a = 0; a < als.size(); ++a) {
                if (als[a].list.size() != sz) continue;
                als_first[a] = (int)node.size();
                for (uint32_t m = als[a].cand; m; m &= m - 1) node.push_back({-1 - (int)a, lowdigit(m)});
            }
        }
    }
    const int Ma = (int)node.size();  // ALS nodes end; grouped nodes (cell = GRP0 - group) follow
    // grouped nodes: digit v in the 2-3 cells where two houses overlap (box-line segments)
    const int GRP0 = -1000000;
    std::vector<std::vector<int>> gcells;
    {
        std::set<std::pair<int, std::vector<int>>> seen;
        for (size_t a = 0; a < p.houses.size(); ++a)
            for (size_t b = a + 1; b < p.houses.size(); ++b) {
                const int ha = p.houses[a], hb = p.houses[b];
                if (!p.group_overlap[(size_t)ha * p.G + hb]) continue;
                std::vector<int> inter;
                for (int c : p.groups[ha].cells)
                    if (!vals[c] && tbit(p.gbits(hb), c)) inter.push_back(c);
                if (inter.size() < 2) continue;
                for (int v = 1; v <= p.D; ++v) {
                    std::vector<int> g;
                    for (int c : inter)
                        if (cand[c] & bit(v)) g.push_back(c);
                    if (g.size() < 2 || g.size() > 3) continue;
                    if (!seen.insert({v, g}).second) continue;
                    node.push_back({GRP0 - (int)gcells.size(), v});
                    gcells.push_back(g);
                }
            }
    }
    const int M = (int)node.size();
    const int WW = (M + 63) / 64;
    auto is_grp = [&](int i) { return node[i].first <= GRP0; };
    auto is_als = [&](int i) { return node[i].first < 0 && node[i].first > GRP0; };
    auto gc = [&](int i) -> const std::vector<int>& { return gcells[GRP0 - node[i].first]; };
    auto ncell = [&](int i) {
        return node[i].first >= 0 ? node[i].first : is_grp(i) ? gc(i)[0] : als[-1 - node[i].first].list[0];
    };
    std::vector<uint64_t> wk((size_t)M * WW, 0);
    auto setw = [&](int a, int b) {
        wk[(size_t)a * WW + (b >> 6)] |= 1ULL << (b & 63);
        wk[(size_t)b * WW + (a >> 6)] |= 1ULL << (a & 63);
    };
    for (int i = 0; i < Mc; ++i) {
        int c = node[i].first, v = node[i].second;
        for (uint32_t m = cand[c]; m; m &= m - 1) {
            int w = lowdigit(m);
            if (w != v) setw(i, nid[(size_t)c * 32 + w]);
        }
        for (int q : p.peer_list[c])
            if (!vals[q] && (cand[q] & bit(v))) setw(i, nid[(size_t)q * 32 + v]);
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int q = p.rel[c][j];
            if (vals[q]) continue;
            for (uint32_t m = cand[q] & p.rel_out[c][j * D1 + v]; m; m &= m - 1)
                setw(i, nid[(size_t)q * 32 + lowdigit(m)]);
        }
    }
    // ALS nodes: weak to candidates / ALS seeing all their digit-cells
    for (int i = Mc; i < Ma; ++i) {
        int a = -1 - node[i].first, v = node[i].second;
        const uint64_t* sa = als_seen_d(a, v);
        for (int q = 0; q < N; ++q)
            if (!vals[q] && (cand[q] & bit(v)) && tbit(sa, q) && !tbit(als[a].cells.data(), q))
                setw(i, nid[(size_t)q * 32 + v]);
        for (int j = i + 1; j < Ma; ++j) {
            int b = -1 - node[j].first;
            if (node[j].second != v || b == a) continue;
            bool dis = true;
            for (int w = 0; w < p.W && dis; ++w) dis = !(als[a].cells[w] & als[b].cells[w]);
            if (dis && als_rcc(a, b, v)) setw(i, j);
        }
    }
    // grouped nodes: weak to candidates / groups of the digit seeing all their cells
    auto sees_all = [&](int q, const std::vector<int>& cells) {
        for (int c : cells)
            if (c == q || !tbit(p.peers(c), q)) return false;
        return true;
    };
    for (int i = Ma; i < M; ++i) {
        const int v = node[i].second;
        for (int q = 0; q < N; ++q)
            if (!vals[q] && (cand[q] & bit(v)) && sees_all(q, gc(i))) setw(i, nid[(size_t)q * 32 + v]);
        for (int j = i + 1; j < M; ++j) {
            if (node[j].second != v) continue;
            bool ok = true;
            for (int c : gc(j)) ok &= sees_all(c, gc(i));
            if (ok) setw(i, j);
        }
    }
    // strong links
    std::vector<std::vector<std::pair<int, int>>> st(M);
    // link value = type | (source + SRC0) << 4; source: group (bilocal), constraint ref
    // (must-contain), ALS id (inside an ALS), -1 otherwise
    const int SRC0 = 1 << 20;
    auto add_strong = [&](int a, int b, int type, int src = -1) {
        if (a == b) return;
        for (auto& e : st[a])
            if (e.first == b) return;
        const int val = type | ((src + SRC0) << 4);
        st[a].push_back({b, val});
        st[b].push_back({a, val});
    };
    for (int c = 0; c < N; ++c)
        if (!vals[c] && popc(cand[c]) == 2) {
            int v1 = lowdigit(cand[c]), v2 = lowdigit(cand[c] & (cand[c] - 1));
            add_strong(nid[(size_t)c * 32 + v1], nid[(size_t)c * 32 + v2], 1);
        }
    for (int hi : p.houses)
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm), k = 0, cs2[2];
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & bit(v))) {
                    if (k < 2) cs2[k] = c;
                    ++k;
                }
            if (k == 2) add_strong(nid[(size_t)cs2[0] * 32 + v], nid[(size_t)cs2[1] * 32 + v], 2, hi);
        }
    // grouped strong links: a house's cells for v split into a group and one cell / another group
    for (int hi : p.houses)
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            const int v = lowdigit(mm);
            std::vector<int> S;
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & bit(v))) S.push_back(c);
            if (S.size() < 3 || S.size() > 6) continue;
            for (int i = Ma; i < M; ++i) {
                if (node[i].second != v) continue;
                const std::vector<int>& g = gc(i);
                bool sub = true;
                for (int c : g) sub &= tbit(p.gbits(hi), c);
                if (!sub) continue;
                std::vector<int> rest;
                for (int c : S)
                    if (std::find(g.begin(), g.end(), c) == g.end()) rest.push_back(c);
                if (rest.size() == 1) add_strong(i, nid[(size_t)rest[0] * 32 + v], 2, hi);
                else
                    for (int j = Ma; j < M; ++j)
                        if (j != i && node[j].second == v && gc(j) == rest) add_strong(i, j, 2, hi);
            }
        }
    uint32_t dom[64];
    for (int pass = 0; pass < 2; ++pass)
        for (const NConstraint& k : pass ? p.cage_nary : p.nary) {
            nary_dom(k, dom);
            const GacOut& o = gac_cached(k, dom);
            if (!o.any) continue;
            for (uint32_t mm = o.must; mm; mm &= mm - 1) {
                int v = lowdigit(mm), n = 0, cs2[2];
                bool placed = false;
                for (int c : k.vars) {
                    if (vals[c] == v) placed = true;
                    if (!vals[c] && (cand[c] & bit(v))) {
                        if (n < 2) cs2[n] = c;
                        ++n;
                    }
                }
                if (!placed && n == 2)
                    add_strong(nid[(size_t)cs2[0] * 32 + v], nid[(size_t)cs2[1] * 32 + v], 3, cref(k.index, k.group));
            }
        }
    for (int c = 0; c < N; ++c) {
        if (vals[c] || popc(cand[c]) < 2) continue;
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int q = p.rel[c][j];
            if (vals[q]) continue;
            for (uint32_t mx = cand[c]; mx; mx &= mx - 1) {
                int x = lowdigit(mx);
                uint32_t Y = 0;
                for (uint32_t my = cand[c] & ~bit(x); my; my &= my - 1)
                    Y |= cand[q] & ~p.rel_out[c][j * D1 + lowdigit(my)];
                if (popc(Y) == 1) add_strong(nid[(size_t)c * 32 + x], nid[(size_t)q * 32 + lowdigit(Y)], 4);
            }
        }
    }
    // equality relations (palindromes, clones): (a,x) <=> (b,x); a chain may pass
    // through such an equivalence without changing truth value
    std::vector<std::vector<int>> eqv(M);
    for (int c = 0; c < N; ++c) {
        if (vals[c]) continue;
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int q = p.rel[c][j];
            if (vals[q] || q < c) continue;
            const uint32_t* t = &p.rel_out[c][j * D1];
            bool eq = true;
            for (int v = 1; v <= p.D && eq; ++v) eq = t[v] == (p.full & ~bit(v));
            if (!eq) continue;
            for (uint32_t m = cand[c] & cand[q]; m; m &= m - 1) {
                int v = lowdigit(m);
                int a = nid[(size_t)c * 32 + v], b = nid[(size_t)q * 32 + v];
                eqv[a].push_back(b);
                eqv[b].push_back(a);
            }
        }
    }
    for (int i = Mc; i < Ma; ++i)  // inside an ALS: not x -> locked set -> every other digit present
        for (int j = i + 1; j < Ma && node[j].first == node[i].first; ++j) add_strong(i, j, 5, -1 - node[i].first);
    // invariant node labels (canonical mode): candidates by node_label, ALS nodes
    // by their cells' candidate labels for the digit
    std::vector<uint64_t> lab(M, 0);
    if (canon) {
        for (int i = 0; i < M; ++i) {
            if (node[i].first >= 0) {
                lab[i] = node_label(node[i].first, node[i].second);
            } else if (is_grp(i)) {
                std::vector<uint64_t> v;
                for (int c : gc(i)) v.push_back(node_label(c, node[i].second));
                std::sort(v.begin(), v.end());
                uint64_t h = 0x6A0ULL + v.size();
                for (uint64_t x : v) h = (h ^ x) * 0x100000001b3ULL + (h >> 7);
                lab[i] = h;
            } else {
                std::vector<uint64_t> v;
                for (int c : als[-1 - node[i].first].list)
                    v.push_back(cand[c] & bit(node[i].second) ? node_label(c, node[i].second) : cell_label[c]);
                std::sort(v.begin(), v.end());
                uint64_t h = 0xA15ULL + v.size();
                for (uint64_t x : v) h = (h ^ x) * 0x100000001b3ULL + (h >> 7);
                lab[i] = h;
            }
        }
    }
    // BFS from every node
    const int MAXL = maxl;
    std::vector<int> dist(2 * M), par(2 * M), ptype(2 * M), rank_(2 * M, 0);
    std::vector<uint64_t> el(WW);
    auto share_group = [&](int a, int b) {
        for (int gi : p.groups_of[a])
            if (tbit(p.gbits(gi), b)) return gi;
        return -1;
    };
    for (int A = 0; A < Mc; ++A) {
        if (st[A].empty()) continue;
        std::fill(dist.begin(), dist.end(), -1);
        dist[2 * A] = 0;
        par[2 * A] = -1;
        // layered BFS; a layer is expanded in rank order, so every state keeps the
        // smallest-rank parent. Canonical ranks: (parent rank, node label) = the
        // lexicographically smallest label sequence among shortest chains.
        // Reference ranks: discovery order (= plain FIFO BFS).
        std::vector<int> cur{2 * A}, nxt;
        rank_[2 * A] = 0;
        for (int depth = 0; depth < MAXL && !cur.empty(); ++depth) {
            nxt.clear();
            for (int s : cur) {
                int x = s >> 1, t = s & 1;
                for (int y : eqv[x]) {  // equivalence: same truth value
                    int s2 = 2 * y + t;
                    if (dist[s2] >= 0) continue;
                    dist[s2] = dist[s] + 1;
                    par[s2] = s;
                    ptype[s2] = 6;
                    nxt.push_back(s2);
                }
                if (t == 0) {
                    for (auto& e : st[x]) {
                        int s2 = 2 * e.first + 1;
                        if (dist[s2] >= 0) continue;
                        dist[s2] = dist[s] + 1;
                        par[s2] = s;
                        ptype[s2] = e.second;
                        nxt.push_back(s2);
                    }
                } else {
                    const uint64_t* wx = &wk[(size_t)x * WW];
                    for (int w = 0; w < WW; ++w)
                        for (uint64_t m = wx[w]; m; m &= m - 1) {
                            int y = w * 64 + __builtin_ctzll(m);
                            int s2 = 2 * y;
                            if (dist[s2] >= 0) continue;
                            dist[s2] = dist[s] + 1;
                            par[s2] = s;
                            ptype[s2] = 0;
                            nxt.push_back(s2);
                        }
                }
            }
            if (canon)
                std::stable_sort(nxt.begin(), nxt.end(), [&](int a, int b) {
                    if (rank_[par[a]] != rank_[par[b]]) return rank_[par[a]] < rank_[par[b]];
                    return lab[a >> 1] < lab[b >> 1];
                });
            for (size_t i = 0; i < nxt.size(); ++i) rank_[nxt[i]] = (int)i;
            cur.swap(nxt);
        }
        for (int Z = 0; Z < Mc; ++Z) {
            int dz = dist[2 * Z + 1];
            if (dz < 3) continue;
            // each endpoint pair once (the reverse chain has the same length);
            // canonical: start from the smaller invariant label
            if (Z != A) {
                if (!canon && Z < A) continue;
                if (canon && (lab[Z] < lab[A] || (lab[Z] == lab[A] && Z < A))) continue;
            }
            // eliminations
            int nel = 0;
            if (Z == A) {
                nel = 1;  // placement
            } else {
                const uint64_t* wa = &wk[(size_t)A * WW];
                const uint64_t* wz = &wk[(size_t)Z * WW];
                for (int w = 0; w < WW; ++w) {
                    el[w] = wa[w] & wz[w];
                    if (w * 64 + 64 > Mc) el[w] &= w * 64 >= Mc ? 0 : ((1ULL << (Mc - w * 64)) - 1);
                    nel += __builtin_popcountll(el[w]);
                }
                if (!nel) continue;
            }
            // reconstruct chain A .. Z
            std::vector<int> chain, stype, ssrc;
            for (int s = 2 * Z + 1; s >= 0; s = par[s]) {
                chain.push_back(s >> 1);
                // type of the link INTO this node (strong: 1-5, weak: 0, equivalence: 6) and its source
                const int pt = s == 2 * A ? 0 : ptype[s];
                stype.push_back(pt & 15);
                ssrc.push_back(pt > 15 ? (pt >> 4) - SRC0 : -1);
                if (s == 2 * A) break;
            }
            std::reverse(chain.begin(), chain.end());
            std::reverse(stype.begin(), stype.end());
            std::reverse(ssrc.begin(), ssrc.end());
            const int L = (int)chain.size() - 1;
            // link statistics
            int s_cnt[6] = {0, 0, 0, 0, 0, 0}, w_cell = 0, w_house = 0, w_rel = 0, max_hop = 0, n_als = 0, n_grp = 0;
            uint32_t digs = 0;
            std::vector<int> cells;
            for (int i = 0; i <= L; ++i) {
                int v = node[chain[i]].second, c = ncell(chain[i]);
                digs |= bit(v);
                if (is_grp(chain[i])) {
                    ++n_grp;
                    for (int x : gc(chain[i]))
                        if (std::find(cells.begin(), cells.end(), x) == cells.end()) cells.push_back(x);
                } else if (node[chain[i]].first < 0) {
                    ++n_als;
                    for (int x : als[-1 - node[chain[i]].first].list)
                        if (std::find(cells.begin(), cells.end(), x) == cells.end()) cells.push_back(x);
                } else if (std::find(cells.begin(), cells.end(), c) == cells.end()) {
                    cells.push_back(c);
                }
                if (i == 0) continue;
                int v0 = node[chain[i - 1]].second, c0 = ncell(chain[i - 1]);
                max_hop = std::max(max_hop, std::max(std::abs(p.coords[c].first - p.coords[c0].first),
                                                     std::abs(p.coords[c].second - p.coords[c0].second)));
                if (stype[i] == 6) {
                    s_cnt[4]++;  // equivalence through an equality relation (palindrome / clone)
                } else if (stype[i] > 0) {
                    s_cnt[stype[i]]++;
                } else if (node[chain[i]].first < 0 || node[chain[i - 1]].first < 0) {
                    ++w_house;  // weak link to/from an ALS: all its digit-cells are seen
                } else if (c == c0) {
                    ++w_cell;
                } else if (v == v0 && tbit(p.peers(c0), c)) {
                    ++w_house;
                } else {
                    ++w_rel;
                }
            }
            int ndig = popc(digs);
            // classification
            int tech, code;
            if (with_als) {
                if (!n_als) continue;  // plain chains are listed by the plain AIC tiers
                tech = ALS_AIC;
                code = 3105;
            } else if (Z == A) {
                tech = NICE_LOOP;
                code = CODE_DNL;
            } else if (ndig == 1) {
                tech = X_CHAIN;
                code = n_grp ? CODE_GXC : CODE_XCH;
                // empty rectangle: 3 links, a grouped strong link inside a box (the box's digit
                // cells form a row + column cross), the other strong link a conjugate pair
                if (n_grp && L == 3)
                    for (int i = 1; i <= L; ++i)
                        if (stype[i] == 2 && ssrc[i] >= 0 && ssrc[i] < p.G && p.group_line[ssrc[i]] == 2 &&
                            (is_grp(chain[i]) || is_grp(chain[i - 1])))
                            code = CODE_ER, tech = EMPTY_RECT;
                if (L == 3 && s_cnt[2] == 2 && !n_grp) {
                    auto ltype = [&](int a, int b) {
                        int ca = node[a].first, cb = node[b].first;
                        if (p.coords[ca].first == p.coords[cb].first) return 0;
                        if (p.coords[ca].second == p.coords[cb].second) return 1;
                        return 2;
                    };
                    int t1 = ltype(chain[0], chain[1]), t2 = ltype(chain[2], chain[3]);
                    int gw = share_group(node[chain[1]].first, node[chain[2]].first);
                    int tw = gw >= 0 ? p.group_line[gw] : 2;
                    if (t1 == t2 && t1 < 2)
                        code = CODE_SKY;
                    else if (t1 < 2 && t2 < 2 && t1 != t2 && tw == 2)
                        code = CODE_2SK;
                    else
                        code = CODE_TUR;
                }
            } else if (s_cnt[1] == (L + 1) / 2 && w_cell == 0 && w_rel == 0 && !n_grp) {
                tech = XY_CHAIN;
                code = CODE_XYC;
                uint32_t pair0 = cand[node[chain[0]].first];
                bool same = true;
                for (int i = 0; i <= L; ++i) same &= cand[node[chain[i]].first] == pair0;
                if (same) {
                    code = CODE_RMP;
                    tech = REMOTE_PAIRS;
                }
            } else {
                tech = AIC_CHAIN;
                code = n_grp ? CODE_GAIC : CODE_AIC;
                if (!n_grp && L == 5 && stype[1] == 1 && stype[5] == 1 && (stype[3] == 2 || stype[3] == 3) &&
                    cand[node[chain[0]].first] == cand[node[chain[5]].first])
                    code = CODE_WWG;
            }
            double shp = pspread(cells);
            Move& m = ob.moves.emplace_back();
            m.tech = tech;
            m.shape = shp;
            m.extra = L;
            m.cov_off = (int)ob.covers.size();
            m.el_off = (int)ob.elims.size();
            if (Z == A) {
                m.pc = node[A].first;
                m.pv = node[A].second;
            } else {
                for (int w = 0; w < WW; ++w)
                    for (uint64_t mm = el[w]; mm; mm &= mm - 1) {
                        int y = w * 64 + __builtin_ctzll(mm);
                        ob.elims.push_back((uint32_t)node[y].first * 32u + node[y].second);
                        ++m.el_n;
                    }
            }
            // groups = links resting on a group (bilocal / constraint strong links, peer weak links)
            set_pattern(ob, m, cells);
            {  // chain links: (cell or -1-als, digit, type of the link INTO the node, its source)
                std::vector<int> lk;
                for (int i = 0; i <= L; ++i) {
                    lk.push_back(node[chain[i]].first);
                    lk.push_back(node[chain[i]].second);
                    lk.push_back(i ? stype[i] : 0);
                    lk.push_back(i ? ssrc[i] : -1);
                }
                add_expl(ob, m, EX_CHAIN, lk);
                std::vector<int> done;
                for (int i = 0; i <= L; ++i)
                    if (is_grp(chain[i])) {
                        std::vector<int> g{node[chain[i]].first, node[chain[i]].second};
                        g.insert(g.end(), gc(chain[i]).begin(), gc(chain[i]).end());
                        add_expl(ob, m, EX_GNODE, g);
                    } else if (node[chain[i]].first < 0) {
                        const int a = -1 - node[chain[i]].first;
                        if (std::find(done.begin(), done.end(), a) != done.end()) continue;
                        done.push_back(a);
                        add_als_expl(ob, m, a, als[a].cand, als[a].list);
                    }
            }
            set_meta9(m, (int)cells.size(), std::max(1, s_cnt[2] + s_cnt[3] + w_house), ndig, L,
                      s_cnt[2] + s_cnt[3] > 0, s_cnt[3] > 0,
                      s_cnt[4] + w_rel > 0, 1, shp);
            m.code = code;
            pm_long xm[XM_N] = {L, s_cnt[1], s_cnt[2], s_cnt[3], s_cnt[4], w_cell, w_house, w_rel, max_hop, ndig};
            if (with_als) xm[5] = n_als;  // ALS chains: slot 5 = ALS nodes (weak same-cell links cannot occur)
            std::copy(xm, xm + XM_N, m.xm);
            ol.push_back(L);
        }
    }
}

void Solver::aic(MoveBuf& out, int lo, int hi) {
    if (disabled[X_CHAIN] && disabled[XY_CHAIN] && disabled[AIC_CHAIN] && disabled[NICE_LOOP] && disabled[REMOTE_PAIRS] &&
        disabled[EMPTY_RECT])
        return;
    build_aic(hi);
    for (size_t i = 0; i < aic_buf.moves.size(); ++i) {
        if (aic_len[i] < lo || aic_len[i] > hi) continue;
        const Move& a = aic_buf.moves[i];
        Move m = a;
        m.cov_off = (int)out.covers.size();
        m.el_off = (int)out.elims.size();
        for (int k = 0; k < a.el_n; ++k) out.elims.push_back(aic_buf.elims[a.el_off + k]);
        copy_extras(aic_buf, a, out, m);
        out.moves.push_back(m);
    }
}

}  // namespace cs
