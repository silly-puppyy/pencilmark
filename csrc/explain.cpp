// Explanation records that need the solver state of the chosen move: the reason behind
// every excluded digit / cell of a direct, line or mental single, and the forced steps of
// each branch of a trial / short trial / either-way. Runs once per chosen move, before it
// is applied (SolveOptions::explain), so the move search itself pays nothing.
#include <algorithm>
#include "portable.hpp"

#include "solver.hpp"

namespace cs {

namespace {
struct RSrc {
    int kind, a, b;
    uint32_t mask;  // digits (naked) or local cell indices (hidden) it excludes
};
inline int dlo(uint32_t m) { return m ? __builtin_ctz(m) + 1 : 0; }
inline int dhi(uint32_t m) { return m ? 32 - __builtin_clz(m) : 0; }
}  // namespace

int Solver::explain_chosen(const Move& m, const MoveBuf& b, std::vector<int>& ex) {
    const size_t start = ex.size();
    const int D1 = p.D + 1;
    auto rec = [&](int tag, const std::vector<int>& data) {
        ex.push_back(tag);
        ex.push_back((int)data.size());
        ex.insert(ex.end(), data.begin(), data.end());
    };
    // ---- trial branches ----
    for (int i = m.ex_off; i + 1 < m.ex_off + m.ex_n;) {
        const int tag = b.ex[i], n = b.ex[i + 1];
        const int* d = &b.ex[i + 2];
        i += 2 + n;
        if (tag != EX_TRIAL || n < 2) continue;
        const int view = d[0], nopt = d[1];
        for (int o = 0; o < nopt && 3 + 2 * o < n; ++o) {
            const int c = d[2 + 2 * o], v = d[3 + 2 * o];
            std::vector<int> log;
            int result = 0;
            if (view == 2) {
                if (contradicts(c, v, &log) && !log.empty()) result = log[log.size() - 4];
            } else if (view == 13 || view == 14) {  // human what-if (light logic, bounded)
                std::vector<uint32_t> saved;
                if (view == 14) {
                    compute_mental(3);
                    saved = cand;
                    for (int x = 0; x < p.N; ++x)
                        if (!vals[x]) cand[x] = md[x];
                    ++version;
                }
                fc_ceiling_now = 2;
                fc_step_cap = 40;
                int steps = 0;
                result = fc_branch(c, v, 1, steps, nullptr, nullptr, &log);
                fc_ceiling_now = -1;
                fc_step_cap = 0;
                if (view == 14) {
                    cand = saved;
                    ++version;
                }
            } else if (view >= 10) {  // forcing chains: propagation at level view - 10
                int steps = 0;
                result = fc_branch(c, v, view - 10, steps, nullptr, nullptr, &log);
            } else {
                std::vector<uint32_t> saved;
                if (view == 1) {
                    compute_mental(3);
                    saved = cand;
                    for (int x = 0; x < p.N; ++x)
                        if (!vals[x]) cand[x] = md[x];
                }
                int placed = 0;
                result = case_split(c, v, 4, placed, nullptr, nullptr, &log);
                if (view == 1) cand = saved;
            }
            std::vector<int> r{c, v, result};
            r.insert(r.end(), log.begin(), log.end());
            rec(EX_BRANCH, r);
        }
    }
    // ---- singles: one reason per excluded digit (naked) / cell (hidden) ----
    const int t = m.tech;
    const bool single = t == NAKED_D || t == HIDDEN_D || t == NAKED_DL || t == HIDDEN_DL || t == LINE_D ||
                        t == MENTAL_D;
    if (!single || m.pc < 0) return (int)(ex.size() - start);
    const bool locks = t == NAKED_DL || t == HIDDEN_DL;
    const int level = t == LINE_D ? 2 : t == MENTAL_D ? 3 : 0;
    const bool hidden = t == HIDDEN_D || t == HIDDEN_DL || (level && m.xm[9] == 1);
    compute_empties();
    direct_excl();
    if (locks) direct_locks();
    if (level) compute_mental(level);
    const int c = m.pc, v = m.pv;
    // mental reason of (x, d)
    auto mental_reason = [&](int x, int d, RSrc& s) {
        const size_t i = (size_t)x * 32 + d;
        const int rt = level ? rs_type[i] : 0;
        if (!rt) return false;
        const uint32_t usable = mex_rel[x] | (level >= 3 ? mex_ment[x] : 0u);  // exclusions of this level
        if (!(usable & bit(d))) return false;
        if (rt == 1) {  // relation arc: a partner whose (mental) digits all forbid d
            int q0 = -1;
            for (size_t j = 0; j < p.rel[x].size() && q0 < 0; ++j) {
                int q = p.rel[x][j];
                uint32_t dq = vals[q] ? bit(vals[q]) : md[q], allowed = 0;
                for (uint32_t mm = dq; mm; mm &= mm - 1) allowed |= ~p.rel_in[x][j * D1 + lowdigit(mm)];
                if (!(allowed & bit(d))) q0 = q;
            }
            s = {RK_ARC, q0, rs_depth[i], 0};
        } else if (rt == 2) {  // inequality bound: a smaller / larger neighbour that pins d out
            int q0 = -1;
            for (size_t j = 0; j < p.rel[x].size() && q0 < 0; ++j) {
                int q = p.rel[x][j];
                uint32_t dq = vals[q] ? bit(vals[q]) : md[q];
                if (p.rel_dir[x][j] < 0 && dlo(dq) >= d) q0 = q;
                if (p.rel_dir[x][j] > 0 && dhi(dq) <= d) q0 = q;
            }
            s = {RK_INEQ, q0, rs_depth[i], 0};
        } else if (rt == 3) {
            int li = rs_line[i], r = -1;
            if (li >= 0) {
                const size_t NL = p.nary.size();
                r = (size_t)li < NL ? cref(p.nary[li].index, -1) : cref(-1, p.cage_nary[li - NL].group);
            }
            s = {RK_LINE, r, rs_depth[i], 0};
        } else {  // mental subset (house) / mental pointing (base house)
            const int h = rs_line[i];
            if (h >= 16384) s = {RK_MPOINT, h - 16384, rs_size[i], 0};
            else s = {RK_SUBSET, h, rs_size[i], 0};
        }
        return true;
    };
    auto lock_src = [&](const LockEntry& lk, uint32_t mask) {
        const int type = (int)(lk.ident >> 60), a = (int)((lk.ident >> 40) & 0xFFFFF),
                  bb = (int)((lk.ident >> 20) & 0xFFFFF), cc = (int)(lk.ident & 0xFFFFF);
        // type 5: digit of house a confined to cells also in group bb; type 6: confined to
        // cells that all see (neq, cc = 0) / relate to (cc = 1) the target
        return type == 5 ? RSrc{RK_LOCK, a, bb, mask} : RSrc{RK_LOCK, a, -1 - cc, mask};
    };
    std::vector<RSrc> srcs;
    std::vector<int> out;
    auto greedy = [&](uint32_t need) {
        std::vector<int> pick;
        uint32_t left = need;
        while (left) {
            int best = -1, bc = 0;
            for (size_t k = 0; k < srcs.size(); ++k) {
                int cnt = popc(srcs[k].mask & left);
                if (cnt > bc || (cnt == bc && cnt > 0 && srcs[k].kind < srcs[best].kind)) {
                    bc = cnt;
                    best = (int)k;
                }
            }
            if (best < 0) break;
            pick.push_back(best);
            left &= ~srcs[best].mask;
        }
        return pick;
    };
    if (!hidden) {
        for (int gi : p.groups_of[c])
            if (placed_g[gi]) srcs.push_back({RK_GROUP, gi, -1, placed_g[gi]});
        for (int q : p.neq[c])
            if (vals[q]) srcs.push_back({RK_NEQ, q, -1, bit(vals[q])});
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int q = p.rel[c][j];
            if (vals[q] && p.rel_in[c][j * D1 + vals[q]]) srcs.push_back({RK_RELATION, q, vals[q], p.rel_in[c][j * D1 + vals[q]]});
        }
        if (p.full & ~p.domains[c]) srcs.push_back({RK_DOMAIN, -1, -1, p.full & ~p.domains[c]});
        if (p.has_cages)
            for (int gi : p.groups_of[c])
                if (p.groups[gi].has_total) {
                    uint32_t mm = p.full & ~cagesum_direct(gi) & ~placed_g[gi];
                    if (mm) srcs.push_back({RK_CAGESUM, gi, -1, mm});
                }
        if (locks)
            for (const LockEntry& lk : lock_lst[c]) srcs.push_back(lock_src(lk, lk.mask));
        if (level)
            for (int d = 1; d <= p.D; ++d) {
                RSrc s;
                if (d != v && mental_reason(c, d, s)) {
                    s.mask = bit(d);
                    srcs.push_back(s);
                }
            }
        const uint32_t need = p.full & ~bit(v);
        std::vector<int> pick = greedy(need);
        for (int d = 1; d <= p.D; ++d) {
            if (d == v) continue;
            for (int k : pick) {
                const RSrc& s = srcs[k];
                if (!(s.mask & bit(d))) continue;
                int bb = s.b;
                if (s.kind == RK_GROUP)
                    for (int q : p.groups[s.a].cells)
                        if (vals[q] == d) bb = q;
                out.insert(out.end(), {c, d, s.kind, s.a, bb});
                break;
            }
        }
    } else {
        int hi = m.na;
        if (hi < 0 || hi >= p.G) return (int)(ex.size() - start);
        std::vector<int> others;
        for (int x : p.groups[hi].cells)
            if (!vals[x] && x != c) others.push_back(x);
        const int n = (int)others.size();
        if (n > 31) return (int)(ex.size() - start);
        const uint32_t bv = bit(v);
        auto local = [&](auto pred) {
            uint32_t mm = 0;
            for (int i = 0; i < n; ++i)
                if (pred(others[i])) mm |= 1u << i;
            return mm;
        };
        std::vector<int> gseen;
        for (int y : others) {
            for (int gi : p.groups_of[y]) {
                if (gi == hi || !(placed_g[gi] & bv) || std::count(gseen.begin(), gseen.end(), gi)) continue;
                gseen.push_back(gi);
                int holder = -1;
                for (int q : p.groups[gi].cells)
                    if (vals[q] == v) holder = q;
                srcs.push_back({RK_GROUP, gi, holder, local([&](int x) { return tbit(p.gbits(gi), x); })});
            }
        }
        for (int q = 0; q < p.N; ++q) {
            if (vals[q] != v) continue;
            uint32_t mn = local([&](int x) { return std::count(p.neq[x].begin(), p.neq[x].end(), q) > 0; });
            if (mn) srcs.push_back({RK_NEQ, q, -1, mn});
        }
        {
            std::vector<int> qs;
            for (int y : others)
                for (int q : p.rel[y])
                    if (vals[q] && !std::count(qs.begin(), qs.end(), q)) qs.push_back(q);
            for (int q : qs) {
                uint32_t mr = local([&](int x) {
                    for (size_t j = 0; j < p.rel[x].size(); ++j)
                        if (p.rel[x][j] == q && (p.rel_in[x][j * D1 + vals[q]] & bv)) return true;
                    return false;
                });
                if (mr) srcs.push_back({RK_RELATION, q, vals[q], mr});
            }
        }
        {
            uint32_t md_ = local([&](int x) { return !(p.domains[x] & bv); });
            for (int i = 0; i < n; ++i)
                if (md_ >> i & 1) srcs.push_back({RK_DOMAIN, -1, -1, 1u << i});
        }
        if (p.has_cages) {
            std::vector<int> cs;
            for (int y : others)
                for (int gi : p.groups_of[y])
                    if (p.groups[gi].has_total && !std::count(cs.begin(), cs.end(), gi) && !(cagesum_direct(gi) & bv))
                        cs.push_back(gi);
            for (int gi : cs) srcs.push_back({RK_CAGESUM, gi, -1, local([&](int x) { return tbit(p.gbits(gi), x); })});
        }
        if (locks) {
            std::vector<uint64_t> ids;
            for (int i = 0; i < n; ++i)
                for (const LockEntry& lk : lock_lst[others[i]]) {
                    if (!(lk.mask & bv)) continue;
                    auto it = std::find(ids.begin(), ids.end(), lk.ident);
                    if (it == ids.end()) {
                        ids.push_back(lk.ident);
                        srcs.push_back(lock_src(lk, 1u << i));
                    } else {
                        // same lock: extend its cells (sources were appended in ids order after
                        // the earlier kinds)
                        srcs[srcs.size() - ids.size() + (it - ids.begin())].mask |= 1u << i;
                    }
                }
        }
        if (level)
            for (int i = 0; i < n; ++i) {
                RSrc s;
                if (mental_reason(others[i], v, s)) {
                    s.mask = 1u << i;
                    srcs.push_back(s);
                }
            }
        const uint32_t need = n >= 32 ? 0xffffffffu : ((1u << n) - 1);
        std::vector<int> pick = greedy(need);
        for (int i = 0; i < n; ++i)
            for (int k : pick) {
                const RSrc& s = srcs[k];
                if (!(s.mask >> i & 1)) continue;
                out.insert(out.end(), {others[i], v, s.kind, s.a, s.b});
                break;
            }
    }
    if (!out.empty()) rec(EX_REASON, out);
    return (int)(ex.size() - start);
}

}  // namespace cs
