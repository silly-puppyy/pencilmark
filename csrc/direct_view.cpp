// The no-notes view: what a solver sees without pencil marks (direct singles, covers, locks).
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

// key of a (type, a, b, c) record
static inline uint64_t mkkey(int type, int a, int b, int c) {
    return ((uint64_t)type << 60) | ((uint64_t)(uint32_t)a << 40) | ((uint64_t)(uint32_t)b << 20) | (uint64_t)(uint32_t)c;
}

// ---------------------------------------------- direct (no-notes) view --
// _direct_sources
void Solver::direct_sources(int c, std::vector<Src>& out) {
    out.clear();
    for (int gi : p.groups_of[c]) {
        uint32_t m = placed_g[gi];
        if (m) out.push_back({p.groups[gi].complete ? K_HOUSE : K_CAGE, p.groups[gi].shape, m});
    }
    if (!p.neq[c].empty()) {
        uint32_t m = 0;
        for (int q : p.neq[c])
            if (vals[q]) m |= bit(vals[q]);
        if (m) out.push_back({K_NEQ, 1.0, m});
    }
    if (!p.rel[c].empty()) {
        uint32_t m = 0;
        const int D1 = p.D + 1;
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int v = vals[p.rel[c][j]];
            if (v) m |= p.rel_in[c][j * D1 + v];
        }
        if (m) out.push_back({K_NONCONSEC, 1.0, m});
    }
    uint32_t dom_ex = p.full & ~p.domains[c];
    if (dom_ex) out.push_back({K_DOMAIN, 1.0, dom_ex});
    if (p.has_cages) {
        for (int gi : p.groups_of[c]) {
            const Group& g = p.groups[gi];
            if (g.has_total) {
                uint32_t m = p.full & ~cagesum_direct(gi) & ~placed_g[gi];
                if (m) out.push_back({K_CAGESUM, g.shape, m});
            }
        }
    }
}

// _direct_excl (for all current empties, into ex[])
void Solver::direct_excl() {
    const int D1 = p.D + 1;
    for (int c : empties) {
        uint32_t m = p.full & ~p.domains[c];
        for (int gi : p.groups_of[c]) m |= placed_g[gi];
        for (int q : p.neq[c])
            if (vals[q]) m |= bit(vals[q]);
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int v = vals[p.rel[c][j]];
            if (v) m |= p.rel_in[c][j * D1 + v];
        }
        if (p.has_cages)
            for (int gi : p.groups_of[c])
                if (p.groups[gi].has_total) m |= p.full & ~cagesum_direct(gi);
        ex[c] = m;
    }
}

// _naked_cover
bool Solver::naked_cover(std::vector<Src>& srcs, double& base, std::vector<Cover>& cov, const CoverScore* score) {
    const int target = popc(p.full) - 1;
    const int n = (int)srcs.size();
    uint32_t all = 0;
    for (auto& s : srcs) all |= s.mask;
    if (popc(all) < target) return false;
    if (canon && score) {
        // every minimal combination, ordered (coverage, kind, shape); keep the cheapest
        double best_d = 1e300;
        std::vector<Cover> bc, tc;
        double bbase = 0;
        bool any = false;
        std::vector<Src> order;
        for (int k = 1; k <= n && !any; ++k) {
            for_combos(n, k, [&](const int* idx) {
                uint32_t m = 0;
                for (int i = 0; i < k; ++i) m |= srcs[idx[i]].mask;
                if (popc(m) < target) return false;
                order.clear();
                for (int i = 0; i < k; ++i) order.push_back(srcs[idx[i]]);
                // the cheapest order of this combination (u depends on the order)
                std::vector<int> perm(k);
                for (int i = 0; i < k; ++i) perm[i] = i;
                do {
                    tc.clear();
                    uint32_t mm = order[perm[0]].mask;
                    for (int i = 1; i < k; ++i) {
                        tc.push_back({order[perm[i]].kind, order[perm[i]].shape, p.D - popc(mm)});
                        mm |= order[perm[i]].mask;
                    }
                    double d = (*score)(order[perm[0]].shape, tc);
                    if (!any || d < best_d - 1e-12) {
                        best_d = d;
                        bc = tc;
                        bbase = order[perm[0]].shape;
                    }
                    any = true;
                } while (k > 1 && k <= 6 && std::next_permutation(perm.begin(), perm.end()));
                return false;
            });
        }
        if (!any) return false;
        cov = bc;
        base = bbase;
        return true;
    }
    std::vector<int> found;
    for (int k = 1; k <= n && found.empty(); ++k) {
        for_combos(n, k, [&](const int* idx) {
            uint32_t m = 0;
            for (int i = 0; i < k; ++i) m |= srcs[idx[i]].mask;
            if (popc(m) >= target) {
                found.assign(idx, idx + k);
                return true;
            }
            return false;
        });
    }
    if (found.empty()) return false;
    std::vector<Src> order;
    for (int i : found) order.push_back(srcs[i]);
    std::stable_sort(order.begin(), order.end(), [](const Src& a, const Src& b) { return popc(a.mask) > popc(b.mask); });
    cov.clear();
    uint32_t m = order[0].mask;
    for (size_t i = 1; i < order.size(); ++i) {
        cov.push_back({order[i].kind, order[i].shape, p.D - popc(m)});
        m |= order[i].mask;
    }
    base = order[0].shape;
    return true;
}

// _hidden_sources: insertion-ordered dict ident -> (kind, shape, cells & items)
void Solver::hidden_sources(const std::vector<int>& cells, int v, int house, bool use_locks, std::vector<HSrc>& out) {
    out.clear();
    const uint32_t b = bit(v);
    const int n = (int)cells.size();
    auto local = [&](const uint64_t* bits) {
        uint32_t m = 0;
        for (int i = 0; i < n; ++i)
            if (tbit(bits, cells[i])) m |= 1u << i;
        return m;
    };
    auto find = [&](uint64_t key) -> int {
        for (size_t i = 0; i < out.size(); ++i)
            if (out[i].key == key) return (int)i;
        return -1;
    };
    // d[key] = value: keeps position if present
    auto put = [&](uint64_t key, int kind, double shape, const uint64_t* bits) {
        if (find(key) < 0) out.push_back({key, kind, shape, local(bits)});
    };
    const int D1 = p.D + 1;
    for (int yi = 0; yi < n; ++yi) {
        int y = cells[yi];
        for (int gi : p.groups_of[y]) {
            if (gi == house || !(placed_g[gi] & b)) continue;
            put(mkkey(0, gi, 0, 0), p.groups[gi].complete ? K_HOUSE : K_CAGE, p.groups[gi].shape, p.gbits(gi));
        }
        for (int q : p.neq[y])
            if (vals[q] == v) put(mkkey(1, q, 0, 0), K_NEQ, 1.0, p.neqb(q));
        for (size_t j = 0; j < p.rel[y].size(); ++j) {
            int q = p.rel[y][j];
            if (vals[q] && (p.rel_in[y][j * D1 + vals[q]] & b)) put(mkkey(2, q, 0, 0), K_NONCONSEC, 1.0, p.relb(q));
        }
        if (!(p.domains[y] & b)) {
            if (find(mkkey(3, y, 0, 0)) < 0) out.push_back({mkkey(3, y, 0, 0), K_DOMAIN, 1.0, 1u << yi});
        }
        if (p.has_cages) {
            for (int gi : p.groups_of[y]) {
                const Group& gg = p.groups[gi];
                if (gg.has_total && !(cagesum_direct(gi) & b))
                    put(mkkey(4, gi, 0, 0), K_CAGESUM, gg.shape, p.gbits(gi));
            }
        }
        if (use_locks && !lock_lst[y].empty()) {
            for (const LockEntry& lk : lock_lst[y])
                if (lk.mask & b) put(lk.ident, K_LOCK, lk.shape, &lock_tgt[(size_t)lk.tgt * p.W]);
        }
    }
}

// _hidden_cover over local item masks
bool Solver::hidden_cover(int n_items, const std::vector<HSrc>& srcs_all, std::vector<Cover>& cov,
                          const CoverScore* score) {
    cov.clear();
    if (n_items == 0) return true;
    const uint32_t ALL = n_items >= 32 ? 0xffffffffu : ((1u << n_items) - 1);
    std::vector<const HSrc*>& srcs = hc_srcs;
    srcs.clear();
    for (auto& s : srcs_all)
        if (s.local & ALL) srcs.push_back(&s);
    std::vector<const HSrc*>& chosen = hc_chosen;
    chosen.clear();
    const int n = (int)srcs.size();
    auto canon_less = [&](const HSrc* a, const HSrc* b) {
        int ca = popc(a->local & ALL), cb = popc(b->local & ALL);
        if (ca != cb) return ca > cb;
        if (a->kind != b->kind) return a->kind < b->kind;
        return a->shape < b->shape;
    };
    if (canon && score) {
        // all minimal covers (bounded search), ordered canonically; keep the cheapest
        double best_d = 1e300;
        std::vector<Cover> bc, tc;
        std::vector<const HSrc*> pick;
        bool any = false;
        pm_long budget = 300000;
        for (int k = 1; k <= n && !any && budget > 0; ++k) {
            for_combos(n, k, [&](const int* idx) {
                if (--budget < 0) return true;
                uint32_t u = 0;
                for (int i = 0; i < k; ++i) u |= srcs[idx[i]]->local;
                if ((u & ALL) != ALL) return false;
                pick.assign(k, nullptr);
                for (int i = 0; i < k; ++i) pick[i] = srcs[idx[i]];
                std::stable_sort(pick.begin(), pick.end(), canon_less);
                // within a combination only the additive cover term depends on the
                // order: pick the order by that, then score the combination once
                std::vector<int> perm(k), bestp;
                for (int i = 0; i < k; ++i) perm[i] = i;
                double bcost = 1e300;
                do {
                    double cost = 0;
                    uint32_t left = ALL;
                    for (int i = 0; i < k; ++i) {
                        const HSrc* sp = pick[perm[i]];
                        cost += P.K[sp->kind] * py_pow(sp->shape, P.gamma) * popc(left);
                        left &= ~sp->local;
                    }
                    if (cost < bcost - 1e-12) {
                        bcost = cost;
                        bestp = perm;
                    }
                } while (k > 1 && k <= 6 && std::next_permutation(perm.begin(), perm.end()));
                tc.clear();
                uint32_t left = ALL;
                for (int i = 0; i < k; ++i) {
                    tc.push_back({pick[bestp[i]]->kind, pick[bestp[i]]->shape, popc(left)});
                    left &= ~pick[bestp[i]]->local;
                }
                double d = (*score)(0.0, tc);
                if (!any || d < best_d - 1e-12) {
                    best_d = d;
                    bc = tc;
                }
                any = true;
                return false;
            });
        }
        if (any) {
            cov = bc;
            return true;
        }
        // fall through: greedy with invariant tie-breaks (coverage, kind, shape)
        if (srcs.empty()) return false;
        uint32_t left = ALL;
        while (left) {
            const HSrc* best = nullptr;
            int bcnt = 0;
            for (const HSrc* sp : srcs) {
                int c = popc(sp->local & left);
                if (c > bcnt || (c == bcnt && c > 0 && best &&
                                 (sp->kind < best->kind || (sp->kind == best->kind && sp->shape < best->shape)))) {
                    bcnt = c;
                    best = sp;
                }
            }
            if (!best) return false;
            chosen.push_back(best);
            left &= ~best->local;
        }
        std::stable_sort(chosen.begin(), chosen.end(), canon_less);
        uint32_t l2 = ALL;
        for (const HSrc* sp : chosen) {
            cov.push_back({sp->kind, sp->shape, popc(l2)});
            l2 &= ~sp->local;
        }
        return true;
    }
    if (n <= 12) {
        for (int k = 1; k <= n && chosen.empty(); ++k) {
            for_combos(n, k, [&](const int* idx) {
                uint32_t u = 0;
                for (int i = 0; i < k; ++i) u |= srcs[idx[i]]->local;
                if ((u & ALL) == ALL) {
                    for (int i = 0; i < k; ++i) chosen.push_back(srcs[idx[i]]);
                    return true;
                }
                return false;
            });
        }
    }
    if (chosen.empty()) {  // greedy
        if (srcs.empty()) return false;
        uint32_t left = ALL;
        while (left) {
            const HSrc* best = srcs[0];
            int bc = popc(best->local & left);
            for (size_t i = 1; i < srcs.size(); ++i) {
                int c = popc(srcs[i]->local & left);
                if (c > bc) {
                    bc = c;
                    best = srcs[i];
                }
            }
            if (!(best->local & left)) return false;
            chosen.push_back(best);
            left &= ~best->local;
        }
    }
    std::stable_sort(chosen.begin(), chosen.end(),
                     [&](const HSrc* a, const HSrc* b) { return popc(a->local & ALL) > popc(b->local & ALL); });
    uint32_t left = ALL;
    for (const HSrc* s : chosen) {
        cov.push_back({s->kind, s->shape, popc(left)});
        left &= ~s->local;
    }
    return true;
}

// common = set(groups_of[poss[0]]); common &= set(groups_of[c]) ...;
// common.discard(x)  -> iteration order as CPython
void Solver::common_groups(const std::vector<int>& poss, int discard, std::vector<int>& out) {
    out.clear();
    for (int gi : p.groups_of[poss[0]]) {
        if (gi == discard) continue;
        bool all = true;
        for (size_t i = 1; i < poss.size() && all; ++i) all = tbit(p.gbits(gi), poss[i]);
        if (all) out.push_back(gi);
    }
    if (out.size() <= 1) return;
    PySet s;
    for (int gi : p.groups_of[poss[0]]) s.add(gi);
    for (size_t i = 1; i < poss.size(); ++i) {
        PySet o;
        for (int gi : p.groups_of[poss[i]]) o.add(gi);
        s = PySet::intersection(s, o);
    }
    s.discard(discard);
    out.clear();
    s.for_each([&](int64_t k) { out.push_back((int)k); });
}

// _direct_moves
void Solver::direct_moves(MoveBuf& out, bool use_locks, int mental) {
    const int D = p.D;
    if (mental) compute_mental(mental);
    compute_empties();
    direct_excl();
    // exclusions available one level down (a mental single must need its level)
    std::vector<uint32_t> lower(p.N, 0);
    for (int c : empties) {
        uint32_t extra = 0;
        if (mental >= 2) extra |= mex_rel[c];
        if (mental >= 3) extra |= mex_ment[c];
        ex2[c] = ex[c] | (use_locks ? lock_mask[c] : 0u) | extra;
        lower[c] = ex[c] | (mental == 3 ? mex_rel[c] : 0u);
    }
    const int mtech = mental == 2 ? LINE_D : MENTAL_D;
    // reason summary of the mental exclusions a move relies on
    auto mental_info = [&](Move& m, const std::vector<std::pair<int, uint32_t>>& used) {
        pm_long tmask = 0, depth = 0, lk = -1, llen = 0, ldist = 0, linf = 0, size = 0, ninf = 0, trans = 0;
        pm_long tlive = 0;
        int tnamed = -1;
        for (auto& cu : used) {
            for (uint32_t mm = cu.second; mm; mm &= mm - 1) {
                size_t i = (size_t)cu.first * 32 + lowdigit(mm);
                int t = rs_type[i];
                if (!t) continue;
                ++ninf;
                tmask |= pm_long(1) << (t - 1);
                depth = std::max<pm_long>(depth, rs_depth[i]);
                size = std::max<pm_long>(size, rs_size[i]);
                if (t == 2) trans = 1;
                if (t == 3 && rs_line[i] >= 0) {
                    const size_t li = (size_t)rs_line[i];
                    const NConstraint& k = li < p.nary.size() ? p.nary[li] : p.cage_nary[li - p.nary.size()];
                    if (k.type == NT_TABLE) {
                        tlive = std::max(tlive, table_live(k));
                        if (k.named && k.index >= 0 && k.index < 1000) tnamed = k.index;
                    }
                    int pos = -1, best = 1 << 20, placed = 0;
                    for (int x = 0; x < k.nv(); ++x)
                        if (k.vars[x] == cu.first) pos = x;
                    for (int x = 0; x < k.nv(); ++x)
                        if (vals[k.vars[x]]) {
                            ++placed;
                            best = std::min(best, std::abs(x - pos));
                        }
                    pm_long dist = placed ? best : 0;
                    if (lk < 0 || dist > ldist) {
                        // non-line rules: 100 + constraint type (cage = 100 + NT_SUM, arrow = 101, ...)
                        lk = k.line_kind >= 0 ? k.line_kind : 100 + k.type;
                        llen = k.nv();
                        ldist = dist;
                        linf = placed;
                    }
                    if (dist != 1) trans = 1;
                }
            }
        }
        pm_long xm[XM_N] = {tmask, depth, lk, llen, ldist, linf, trans, size, ninf, 0};
        std::copy(xm, xm + XM_N, m.xm);
        if (mental == 3)
            m.code = 4400 + (size ? (int)size : 8);  // 8: relation inference enabled by a mental subset
        else if (lk == 100 + NT_TABLE && tnamed >= 0)
            m.code = 6000 + tnamed;  // a named table rule ("diamond rule in the head")
        else if (lk >= 100)
            m.code = 4500 + (int)(lk - 100);  // arrow / cage / sum / between ... arithmetic in the head
        else if (lk >= 0)
            m.code = 4000 + 10 * (int)lk + (linf == 0 ? 1 : ldist <= 1 ? 3 : 4);
        else
            m.code = (tmask & 2) ? 4300 : 4200;
        m.meta[3] = (int)depth;  // links = inference depth
        m.meta[6] = 1;           // relation
        m.tab_live = tlive;
    };
    std::fill(seen.begin(), seen.end(), 0u);
    std::vector<int> emp;
    if (!use_locks && !mental) {
        for (int hi : p.houses) {
            const Group& g = p.groups[hi];
            int cnt = 0, c = -1;
            for (int x : g.cells)
                if (!vals[x]) {
                    ++cnt;
                    c = x;
                }
            if (cnt != 1) continue;
            uint32_t mm = p.full & ~placed_g[hi];
            if (!mm) continue;
            int v = lowdigit(mm);
            if (ex[c] & bit(v)) continue;  // the missing digit is not a candidate: contradiction, no move
            if (!canon && (seen[c] & bit(v))) continue;
            seen[c] |= bit(v);
            Move& m = new_move(out, FULL_HOUSE, g.shape, 0);
            m.pc = c;
            m.pv = v;
            m.nk = NM_GROUP;
            m.na = hi;
            set_meta(m, (int)g.cells.size(), 1, 1, 0, 0, 0, 0, 0, g.shape);
        }
    }
    std::vector<Src> srcs;
    std::vector<Cover> cov;
    for (int c : empties) {
        uint32_t rem = p.full & ~ex2[c];
        if (popc(rem) != 1) continue;
        if (use_locks && popc(p.full & ~ex[c]) == 1) continue;
        if (mental && popc(p.full & ~lower[c]) == 1) continue;
        int v = lowdigit(rem);
        if (!canon && (seen[c] & bit(v))) continue;
        direct_sources(c, srcs);
        if (use_locks)
            for (const LockEntry& lk : lock_lst[c]) srcs.push_back({K_LOCK, lk.shape, lk.mask});
        if (mental >= 2 && mex_rel[c]) srcs.push_back({K_LINE, 1.0, mex_rel[c]});
        if (mental >= 3 && mex_ment[c]) srcs.push_back({K_MENTAL, 1.0, mex_ment[c]});
        double base;
        const CoverScore nscore = [&](double b0, const std::vector<Cover>& cv) {
            Move t;
            t.tech = mental ? mtech : use_locks ? NAKED_DL : NAKED_D;
            t.shape = b0;
            t.cov_n = (int)cv.size();
            bool ks = false, kr = false;
            for (auto& x : cv) {
                ks |= x.kind == K_CAGESUM;
                kr |= x.kind == K_NEQ || x.kind == K_NONCONSEC;
            }
            set_meta(t, 1, (int)cv.size() + 1, 1, use_locks ? 1 : 0, 0, ks, kr, 0, b0);
            return P.difficulty(t, cv.data(), p.D);
        };
        if (!naked_cover(srcs, base, cov, &nscore)) continue;
        seen[c] |= bit(v);
        bool ks = false, kr = false;
        for (auto& cv : cov) {
            if (cv.kind == K_CAGESUM) ks = true;
            if (cv.kind == K_NEQ || cv.kind == K_NONCONSEC) kr = true;
        }
        Move& m = new_move(out, mental ? mtech : use_locks ? NAKED_DL : NAKED_D, base, 0);
        for (auto& cv : cov) out.covers.push_back(cv);
        m.cov_n = (int)cov.size();
        m.pc = c;
        m.pv = v;
        set_meta(m, 1, (int)cov.size() + 1, 1, use_locks ? 1 : 0, 0, ks, kr, 0, base);
        if (mental) {
            bool usesm = false;
            for (auto& cv : cov) usesm |= cv.kind == K_MENTAL || cv.kind == K_LINE;
            if (!usesm && !(base == 1.0 && (popc(mex_rel[c]) || popc(mex_ment[c])))) {
                // the cover found does not mention the mental source: still a mental single
            }
            mental_info(m, {{c, mex_rel[c] | (mental >= 3 ? mex_ment[c] : 0u)}});
        }
    }
    std::vector<int> others;
    std::vector<HSrc> hs;
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        emp.clear();
        for (int x : g.cells)
            if (!vals[x]) emp.push_back(x);
        if (emp.size() < 2) continue;
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            int cnt = 0, c = -1;
            for (int x : emp)
                if (!(ex2[x] & b)) {
                    ++cnt;
                    c = x;
                }
            if (cnt != 1) continue;
            if (use_locks) {
                int c2 = 0;
                for (int x : emp)
                    if (!(ex[x] & b)) ++c2;
                if (c2 == 1) continue;
            }
            if (mental) {
                int c2 = 0;
                for (int x : emp)
                    if (!(lower[x] & b)) ++c2;
                if (c2 == 1) continue;
            }
            if (!canon && (seen[c] & b)) continue;
            others.clear();
            for (int x : emp)
                if (x != c) others.push_back(x);
            hidden_sources(others, v, hi, use_locks, hs);
            if (mental)
                for (size_t yi = 0; yi < others.size(); ++yi) {
                    int y = others[yi];
                    if (mex_rel[y] & b) hs.push_back({mkkey(7, y, 0, 0), K_LINE, 1.0, 1u << yi});
                    if (mental >= 3 && (mex_ment[y] & b)) hs.push_back({mkkey(8, y, 0, 0), K_MENTAL, 1.0, 1u << yi});
                }
            const CoverScore hscore = [&](double, const std::vector<Cover>& cv) {
                Move t;
                t.tech = mental ? mtech : use_locks ? HIDDEN_DL : HIDDEN_D;
                t.shape = g.shape;
                t.cov_n = (int)cv.size();
                bool ks = false, kr = false;
                for (auto& x : cv) {
                    ks |= x.kind == K_CAGESUM;
                    kr |= x.kind == K_NEQ || x.kind == K_NONCONSEC;
                }
                set_meta(t, 1 + (int)others.size(), 1 + (int)cv.size(), 1, use_locks ? 1 : 0, 1, ks, kr, 0, g.shape);
                return P.difficulty(t, cv.data(), p.D);
            };
            if (!hidden_cover((int)others.size(), hs, cov, &hscore)) continue;
            seen[c] |= b;
            bool ks = false, kr = false;
            for (auto& cv : cov) {
                if (cv.kind == K_CAGESUM) ks = true;
                if (cv.kind == K_NEQ || cv.kind == K_NONCONSEC) kr = true;
            }
            Move& m = new_move(out, mental ? mtech : use_locks ? HIDDEN_DL : HIDDEN_D, g.shape, (int)others.size());
            for (auto& cv : cov) out.covers.push_back(cv);
            m.cov_n = (int)cov.size();
            m.pc = c;
            m.pv = v;
            m.nk = NM_GROUP;
            m.na = hi;
            set_meta(m, 1 + (int)others.size(), 1 + (int)cov.size(), 1, use_locks ? 1 : 0, 1, ks, kr, 0, g.shape);
            if (mental) {
                std::vector<std::pair<int, uint32_t>> used;
                for (int y : others) {
                    uint32_t mm = (mex_rel[y] | (mental >= 3 ? mex_ment[y] : 0u)) & b;
                    if (mm) used.push_back({y, mm});
                }
                mental_info(m, used);
                m.xm[9] = 1;  // hidden
            }
        }
    }
    (void)D;
}

// _direct_locks
bool Solver::direct_locks() {
    for (int c : lock_cells) {
        lock_lst[c].clear();
        lock_mask[c] = 0;
    }
    lock_cells.clear();
    lock_tgt.clear();
    compute_empties();
    direct_excl();
    const int W = p.W, D1 = p.D + 1;
    auto add_lock = [&](int c, const LockEntry& e) {
        if (lock_lst[c].empty()) lock_cells.push_back(c);
        lock_lst[c].push_back(e);
        lock_mask[c] |= e.mask;
    };
    std::vector<int> emp, poss, common, targets;
    std::vector<std::pair<int, uint32_t>> rms;
    std::vector<uint64_t> cr(W);
    for (int bi : p.houses) {
        const Group& B = p.groups[bi];
        emp.clear();
        for (int x : B.cells)
            if (!vals[x]) emp.push_back(x);
        if (emp.size() < 3) continue;
        for (uint32_t mm = p.full & ~placed_g[bi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            poss.clear();
            for (int c : emp)
                if (!(ex[c] & b)) poss.push_back(c);
            if (poss.size() < 2) continue;
            common_groups(poss, bi, common);
            for (int ai : common) {
                const Group& A = p.groups[ai];
                targets.clear();
                for (int c : A.cells)
                    if (!vals[c] && !tbit(p.gbits(bi), c) && !(ex[c] & b)) targets.push_back(c);
                if (targets.empty()) continue;
                int tgt = (int)(lock_tgt.size() / W);
                lock_tgt.resize(lock_tgt.size() + W, 0);
                for (int c : targets) sbit(&lock_tgt[(size_t)tgt * W], c);
                uint64_t ident = mkkey(5, bi, ai, v);
                for (int c : targets) add_lock(c, {ident, B.shape, b, tgt});
            }
            for (int gen = 1; gen >= 0; --gen) {
                const std::vector<int>& L0 = gen ? p.rel[poss[0]] : p.neq[poss[0]];
                if (L0.empty()) continue;
                const uint64_t* b0 = gen ? p.relb(poss[0]) : p.neqb(poss[0]);
                for (int w = 0; w < W; ++w) cr[w] = b0[w];
                for (size_t i = 1; i < poss.size(); ++i) {
                    const uint64_t* bc = gen ? p.relb(poss[i]) : p.neqb(poss[i]);
                    for (int w = 0; w < W; ++w) cr[w] &= bc[w];
                }
                rms.clear();
                for (int x = 0; x < p.N; ++x) {
                    if (!tbit(cr.data(), x)) continue;
                    if (vals[x] || std::find(poss.begin(), poss.end(), x) != poss.end()) continue;
                    uint32_t rm = p.full;
                    if (gen) {
                        for (int c : poss) rm &= p.rel_ex(c, x)[v];
                    } else {
                        rm = b;
                    }
                    if (rm & ~ex[x]) rms.push_back({x, rm});
                }
                if (rms.empty()) continue;
                int tgt = (int)(lock_tgt.size() / W);
                lock_tgt.resize(lock_tgt.size() + W, 0);
                for (auto& xr : rms) sbit(&lock_tgt[(size_t)tgt * W], xr.first);
                uint64_t ident = mkkey(6, bi, v, gen);
                for (auto& xr : rms) add_lock(xr.first, {ident, B.shape, xr.second, tgt});
            }
        }
    }
    (void)D1;
    return !lock_cells.empty();
}

}  // namespace cs
