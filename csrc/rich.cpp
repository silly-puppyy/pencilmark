// Rich per-move / per-step metadata for meta-grader feature screens.
// Columns 0-11 / steps 0-2 follow grader/features_rich.py (same definitions).
#include <algorithm>
#include "portable.hpp"
#include <cmath>

#include "solver.hpp"

namespace cs {

const std::vector<std::string>& rich_names() {
    static const std::vector<std::string> n = {
        // --- grader/features_rich.py RICH_NAMES ---
        "log_effect", "log_tcand", "log_house_empty", "log_dist_last", "log_age", "log_tech_used", "near_last",
        "extreme_digit", "log_combos", "unique_combo", "house_fill", "digit_count",
        // --- extensions ---
        "chain_len", "strong_bivalue", "strong_bilocal", "strong_constraint", "strong_relation", "weak_links",
        "max_hop", "pattern_digits", "fish_size", "fish_fins", "fish_franken", "fish_mutant", "als_count",
        "t_house", "t_irregular", "t_diagonal", "t_window", "t_cage", "t_sum", "t_arrow", "t_set", "t_relation",
        "t_neq", "t_outside", "t_implied", "irregularity", "is_placement", "log_n_elims", "log_combos_now",
        "set_unique_now", "pattern_cells",
        // --- pattern geometry / mental-notes load (cells justifying the move) ---
        "pattern_gyration", "pattern_bbox", "gyration_from_last", "pattern_bivalue_frac",
        "pattern_in_subset_frac", "n_pattern_houses",
        // --- habits: digit sweeps / box-by-box (previous placement on the path) ---
        "same_digit_last", "same_box_last", "digit_run_len",
        // --- cognitive load (Solver::cog_loads) and scanning focus ---
        "n_cells_scanned", "n_combos_considered", "propagation_depth", "n_constraints_involved",
        "is_search_like", "digit_step", "box_step",
        // --- provenance: earlier non-single moves the pattern's candidates depend on ---
        "reveal_depth"};
    return n;
}
const std::vector<std::string>& step_names() {
    static const std::vector<std::string> n = {"log_board_cands", "log_n_techs", "frac_solved", "tech_entropy",
                                               "log_n_alts", "failed_families", "failed_mask"};
    return n;
}

namespace {
// digit combinations of an n-cell cage summing to s (D = 9), as features_rich._NCOMB
int ncomb9(int n, int s) {
    static int tab[10][46];
    static bool init = false;
    if (!init) {
        for (int m = 1; m < 512; ++m) {
            int k = __builtin_popcount(m), sum = 0;
            for (int d = 1; d <= 9; ++d)
                if (m >> (d - 1) & 1) sum += d;
            tab[k][sum]++;
        }
        init = true;
    }
    if (n < 1 || n > 9 || s < 0 || s > 45) return 0;
    return tab[n][s];
}
inline uint64_t mix(uint64_t h, uint64_t x) {
    h ^= x + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
    return h;
}
bool is_chain(int t) {
    return t == X_CHAIN || t == XY_CHAIN || t == AIC_CHAIN || t == NICE_LOOP || t == ALS_AIC || t == MENTAL_CHAIN ||
           t == REMOTE_PAIRS || t == EMPTY_RECT;
}
bool is_combo(int t) {
    return (t >= SUM_COMBO && t <= TABLE_COMBO) || (t >= SANDWICH_COMBO && t <= LOL_COMBO) || t == COMBO_LOCK ||
           t == INNIE_X;
}
}  // namespace

void Solver::rich_rows(const MoveBuf& buf, SolveResult& out, bool notes_event) {
    const int R = (int)rich_names().size();
    const int N = p.N, D = p.D;
    // per-step features (state before the move)
    int nb = 0, filled = 0;
    for (int c = 0; c < N; ++c) {
        if (vals[c])
            ++filled;
        else
            nb += popc(cand[c]);
    }
    int tc[N_TECH] = {0}, ntech = 0;
    const int nalt = notes_event ? 1 : (int)buf.moves.size();
    if (notes_event) {
        tc[TAKE_NOTES] = ntech = 1;
    } else {
        for (const Move& m : buf.moves)
            if (!tc[m.tech]++) ++ntech;
    }
    double ent = 0;
    for (int t = 0; t < N_TECH; ++t)
        if (tc[t]) {
            double q = (double)tc[t] / nalt;
            ent -= q * std::log(q);
        }
    out.s_rich.insert(out.s_rich.end(), {(float)std::log(1.0 + nb), (float)std::log(1.0 + ntech),
                                         (float)filled / N, (float)ent, (float)std::log((double)nalt),
                                         notes_event ? 0.0f : (float)step_fails,
                                         notes_event ? 0.0f : (float)step_fmask});
    if (notes_event) {
        out.m_rich.insert(out.m_rich.end(), R, 0.0f);
        return;
    }
    int digit_n[33] = {0};
    for (int c = 0; c < N; ++c) digit_n[vals[c]]++;
    // cells in a locked subset (naked / hidden pair or triple) of the current state
    std::vector<char> in_subset(N, 0);
    {
        std::vector<int> emp;
        for (int hi : p.houses) {
            emp.clear();
            for (int c : p.groups[hi].cells)
                if (!vals[c]) emp.push_back(c);
            const int n = (int)emp.size();
            for (int a = 0; a < n; ++a)
                for (int b = a + 1; b < n; ++b) {
                    uint32_t u = cand[emp[a]] | cand[emp[b]];
                    if (popc(u) == 2) in_subset[emp[a]] = in_subset[emp[b]] = 1;
                    for (int c3 = b + 1; c3 < n; ++c3)
                        if (popc(u | cand[emp[c3]]) == 3) in_subset[emp[a]] = in_subset[emp[b]] = in_subset[emp[c3]] = 1;
                }
            // hidden: k digits confined to the same k cells
            std::vector<uint32_t> pos(33, 0);
            for (int i = 0; i < n; ++i)
                for (uint32_t m = cand[emp[i]]; m; m &= m - 1) pos[lowdigit(m)] |= 1u << i;
            for (int v = 1; v <= D; ++v)
                for (int w = v + 1; w <= D; ++w) {
                    uint32_t u = pos[v] | pos[w];
                    if (pos[v] && pos[w] && popc(u) == 2)
                        for (uint32_t m = u; m; m &= m - 1) in_subset[emp[__builtin_ctz(m)]] = 1;
                    for (int x = w + 1; x <= D; ++x) {
                        uint32_t u3 = u | pos[x];
                        if (pos[v] && pos[w] && pos[x] && popc(u3) == 3)
                            for (uint32_t m = u3; m; m &= m - 1) in_subset[emp[__builtin_ctz(m)]] = 1;
                    }
                }
        }
    }
    rich_pats.assign(buf.moves.size(), {});
    auto houses_has = [&](int a, int b) {
        for (int gi : p.groups_of[a])
            if (p.groups[gi].complete && tbit(p.gbits(gi), b)) return true;
        return false;
    };
    for (size_t mi_ = 0; mi_ < buf.moves.size(); ++mi_) {
        const Move& m = buf.moves[mi_];
        std::vector<float> r(R, 0.0f);
        const uint32_t* el = &buf.elims[m.el_off];
        const int ne = m.el_n;
        const int tgt = m.pc >= 0 ? m.pc : (ne ? (int)(el[0] / 32) : -1);
        r[0] = std::log(1.0 + ne + (m.pc >= 0));
        if (m.pc >= 0) {
            r[1] = vals[m.pc] ? 0.0f : (float)std::log((double)std::max(popc(cand[m.pc]), 1));
        } else if (ne) {
            double s = 0;
            for (int i = 0; i < ne; ++i) s += popc(cand[el[i] / 32]);
            r[1] = (float)std::log(std::max(1.0, s / ne));
        }
        if (tgt >= 0) {
            int best_emp = 1 << 30;
            double fill = -1;
            bool any = false;
            for (int gi : p.groups_of[tgt]) {
                if (!p.groups[gi].complete) continue;
                int e = 0;
                for (int c : p.groups[gi].cells) e += !vals[c];
                best_emp = std::min(best_emp, e);
                fill = std::max(fill, 1.0 - (double)e / p.groups[gi].cells.size());
                any = true;
            }
            if (any) {
                r[2] = (float)std::log(1.0 + best_emp);
                r[10] = (float)fill;
            }
            if (rich_last >= 0) {
                int dr = std::abs(p.coords[tgt].first - p.coords[rich_last].first);
                int dc = std::abs(p.coords[tgt].second - p.coords[rich_last].second);
                r[3] = (float)std::log(1.0 + std::max(dr, dc));
                r[6] = houses_has(tgt, rich_last) ? 1.0f : 0.0f;
            }
            int cage = -1;  // last cage group containing the target (dict overwrite order)
            for (int gi : p.groups_of[tgt])
                if (p.groups[gi].has_total) cage = gi;
            if (cage >= 0) {
                int nc = D == 9 ? ncomb9((int)p.groups[cage].cells.size(), p.groups[cage].total) : 1;
                r[8] = (float)std::log((double)std::max(nc, 1));
                r[9] = nc == 1 ? 1.0f : 0.0f;
            }
        }
        uint64_t key = mix(mix(mix(1469598103934665603ULL, m.tech), (uint64_t)(m.pc + 1)), (uint64_t)m.pv);
        for (int i = 0; i < ne; ++i) key = mix(key, el[i]);
        auto it = rich_first.find(key);
        if (it == rich_first.end()) it = rich_first.emplace(key, rich_step_idx).first;
        r[4] = (float)std::log(1.0 + rich_step_idx - it->second);
        r[5] = (float)std::log(1.0 + rich_tech_used[m.tech]);
        if (m.pc >= 0) {
            r[7] = (m.pv == 1 || m.pv == D) ? 1.0f : 0.0f;
            r[11] = (float)digit_n[m.pv] / D;
        }
        // ---- extensions ----
        const pm_long* x = m.xm;
        if (is_chain(m.tech)) {
            r[12] = x[0];
            r[13] = x[1];
            r[14] = x[2];
            r[15] = x[3];
            r[16] = x[4];
            r[17] = (float)(m.tech == ALS_AIC ? x[6] + x[7] : x[5] + x[6] + x[7]);
            r[18] = x[8];
            r[19] = x[9];
            if (m.tech == ALS_AIC) r[24] = x[5];
        }
        if (m.tech == FINNED_FISH || m.tech == JELLYFISH) {
            r[20] = x[0];
            r[21] = x[1];
            r[22] = x[3] == 1;
            r[23] = x[3] == 2;
        } else if (m.tech == XWING || m.tech == SWORDFISH) {
            r[20] = m.extra;
        }
        if (m.tech == ALS_XZ) r[24] = 2;
        if (m.tech == ALS_XYWING) r[24] = 3;
        if (m.tech == DEATH_BLOSSOM) r[24] = x[0] - 1;
        // involved groups: named groups, else the target's complete groups
        std::vector<int> gs;
        if ((m.nk == NM_GROUP || m.nk == NM_LOCK || m.nk == NM_INNIE || m.nk == NM_OUTIE) && m.na >= 0 && m.na < p.G)
            gs.push_back(m.na);
        if (m.nk == NM_LOCK && m.nb >= 0 && m.nb < p.G) gs.push_back(m.nb);
        if (m.nk == NM_NARY && m.nb >= 0 && m.nb < p.G) gs.push_back(m.nb);
        if (gs.empty() && tgt >= 0)
            for (int gi : p.groups_of[tgt])
                if (p.groups[gi].complete) gs.push_back(gi);
        double shp = 0;
        for (int gi : gs) {
            int cat = p.group_cat[gi];
            if (cat == GC_LINE || cat == GC_BOX) r[25] = 1;
            if (cat == GC_IRREGULAR) r[26] = 1;
            if (cat == GC_DIAG) r[27] = 1;
            if (cat == GC_WINDOW) r[28] = 1;
            if (cat == GC_CAGE || p.groups[gi].has_total) r[29] = 1;
            if (cat == GC_IMPLIED) r[36] = 1;
            shp += p.groups[gi].shape;
        }
        if (!gs.empty()) r[37] = (float)(shp / gs.size());
        if (m.tech == CAGE_COMBO || m.tech == INNIE_D || m.tech == INNIE_N || m.tech == INNIE_X) r[30] = 1;
        for (int i = 0; i < m.cov_n; ++i) {
            int k = buf.covers[m.cov_off + i].kind;
            if (k == K_CAGESUM) r[30] = 1;
            if (k == K_CAGE) r[29] = 1;
            if (k == K_NONCONSEC) r[33] = 1;
            if (k == K_NEQ) r[34] = 1;
        }
        if (m.nk == NM_NARY && m.na >= 0) {
            int type = (int)x[0];
            if (m.tech == NARY_D || is_combo(m.tech)) {
                if (m.tech == INNIE_X) type = NT_SUM;
                if (type == NT_SUM || type == NT_EQSUM) r[30] = 1;
                if (type == NT_ARROW) r[31] = 1;
                if (type == NT_SET) r[32] = 1;
                if (nt_line(type)) r[35] = 1;
                if (type == NT_SAMESET) r[36] = 1;
            }
        }
        if (m.tech == PAIRARC || (is_chain(m.tech) && (x[4] > 0 || x[7] > 0))) r[33] = 1;
        r[38] = m.pc >= 0;
        r[39] = (float)std::log(1.0 + ne);
        if (is_combo(m.tech)) {
            pm_long combos = m.tech == INNIE_X ? x[3] : x[2];
            r[40] = (float)std::log((double)std::max(combos, pm_long(1)));
            r[41] = (m.tech != COMBO_LOCK && m.tech != INNIE_X && x[3]) ? 1.0f : 0.0f;
        }
        if (priced_meta(m)) r[42] = m.meta[0];
        // pattern cells: recorded by the technique, else target + eliminated cells (+ the
        // empty cells of the named group: the house of a hidden single, ...)
        std::vector<int>& pc = rich_pats[mi_];
        if (m.pat_n) {
            pc.assign(buf.pats.begin() + m.pat_off, buf.pats.begin() + m.pat_off + m.pat_n);
        } else {
            if (m.pc >= 0) pc.push_back(m.pc);
            for (int i = 0; i < ne; ++i) pc.push_back((int)(el[i] / 32));
            if (m.nk == NM_GROUP && m.na >= 0 && m.na < p.G)
                for (int c : p.groups[m.na].cells)
                    if (!vals[c]) pc.push_back(c);
            std::sort(pc.begin(), pc.end());
            pc.erase(std::unique(pc.begin(), pc.end()), pc.end());
        }
        if (!pc.empty()) {
            double mx = 0, my = 0;
            int r0 = 1 << 30, r1 = -1, c0 = 1 << 30, c1 = -1;
            for (int c : pc) {
                mx += p.coords[c].first;
                my += p.coords[c].second;
                r0 = std::min(r0, p.coords[c].first);
                r1 = std::max(r1, p.coords[c].first);
                c0 = std::min(c0, p.coords[c].second);
                c1 = std::max(c1, p.coords[c].second);
            }
            mx /= pc.size();
            my /= pc.size();
            double ss = 0;
            for (int c : pc) {
                double dx = p.coords[c].first - mx, dy = p.coords[c].second - my;
                ss += dx * dx + dy * dy;
            }
            r[43] = (float)(std::sqrt(ss / pc.size()) / D);
            r[44] = (float)((double)(r1 - r0 + 1) * (c1 - c0 + 1) / N);
            if (!rich_prev.empty()) {
                double px = 0, py = 0;
                for (int c : rich_prev) {
                    px += p.coords[c].first;
                    py += p.coords[c].second;
                }
                px /= rich_prev.size();
                py /= rich_prev.size();
                double s2 = 0;
                for (int c : pc) {
                    double dx = p.coords[c].first - px, dy = p.coords[c].second - py;
                    s2 += dx * dx + dy * dy;
                }
                r[45] = (float)(std::sqrt(s2 / pc.size()) / D);
            }
            int un = 0, bv = 0, sub = 0;
            std::vector<int> hs;
            for (int c : pc) {
                if (!vals[c]) {
                    ++un;
                    bv += popc(cand[c]) <= 2;
                    sub += in_subset[c] != 0;
                }
                for (int gi : p.groups_of[c])
                    if (p.groups[gi].complete) hs.push_back(gi);
            }
            if (un) {
                r[46] = (float)bv / un;
                r[47] = (float)sub / un;
            }
            std::sort(hs.begin(), hs.end());
            r[48] = (float)(std::unique(hs.begin(), hs.end()) - hs.begin());
        }
        // habits: digit of the move (placement, or the single digit all eliminations share)
        int mdig = m.pc >= 0 ? m.pv : 0;
        if (m.pc < 0 && ne) {
            mdig = (int)(el[0] % 32);
            for (int i = 1; i < ne; ++i)
                if ((int)(el[i] % 32) != mdig) mdig = 0;
        }
        if (mdig && rich_last_digit && mdig == rich_last_digit) {
            r[49] = 1.0f;
            r[51] = (float)std::log(1.0 + rich_digit_run);
        }
        if (tgt >= 0 && rich_last >= 0)
            for (int gi : p.groups_of[tgt])
                if (p.groups[gi].complete && (p.group_cat[gi] == GC_BOX || p.group_cat[gi] == GC_IRREGULAR) &&
                    tbit(p.gbits(gi), rich_last))
                    r[50] = 1.0f;
        // cognitive loads (computed at the choice point)
        r[52] = m.load[0];
        r[53] = m.load[1];
        r[54] = m.load[2];
        r[55] = m.load[3];
        r[56] = m.load[4];
        r[59] = m.load[7];
        // scanning focus relative to the previous placement: digit sweep step
        // ((digit - last digit) mod D, / D) and box sweep step (box-grid distance)
        if (mdig && rich_last_digit) r[57] = (float)(((mdig - rich_last_digit) % D + D) % D) / D;
        if (tgt >= 0 && rich_last >= 0) {
            int bt = -1, bl = -1;
            for (int gi : p.groups_of[tgt])
                if (p.groups[gi].complete && (p.group_cat[gi] == GC_BOX || p.group_cat[gi] == GC_IRREGULAR)) bt = gi;
            for (int gi : p.groups_of[rich_last])
                if (p.groups[gi].complete && (p.group_cat[gi] == GC_BOX || p.group_cat[gi] == GC_IRREGULAR)) bl = gi;
            if (bt >= 0 && bl >= 0) {
                auto ctr = [&](int gi) {
                    double x = 0, y = 0;
                    for (int c : p.groups[gi].cells) {
                        x += p.coords[c].first;
                        y += p.coords[c].second;
                    }
                    return std::make_pair(x / p.groups[gi].cells.size(), y / p.groups[gi].cells.size());
                };
                auto a = ctr(bt), b2 = ctr(bl);
                double side = std::sqrt((double)p.groups[bt].cells.size());
                r[58] = (float)(std::max(std::abs(a.first - b2.first), std::abs(a.second - b2.second)) / side);
            }
        }
        out.m_rich.insert(out.m_rich.end(), r.begin(), r.end());
    }
}

// Cognitive load of a move: what a person has to look at / hold in mind to verify it.
void Solver::cog_loads(Move& m, const MoveBuf& b) {
    const pm_long* x = m.xm;
    std::vector<int> pc;
    if (m.pat_n)
        pc.assign(b.pats.begin() + m.pat_off, b.pats.begin() + m.pat_off + m.pat_n);
    else if (m.pc >= 0)
        pc.push_back(m.pc);
    std::vector<char> seen(p.N, 0);
    int scanned = 0;
    auto add = [&](int c) {
        if (c >= 0 && c < p.N && !seen[c]) {
            seen[c] = 1;
            ++scanned;
        }
    };
    for (int c : pc) add(c);
    if (m.pc >= 0) add(m.pc);
    for (int i = 0; i < m.el_n; ++i) add((int)(b.elims[m.el_off + i] / 32));
    auto add_group = [&](int gi) {
        if (gi >= 0 && gi < p.G)
            for (int c : p.groups[gi].cells) add(c);
    };
    if (m.nk == NM_GROUP || m.nk == NM_INNIE || m.nk == NM_OUTIE) add_group(m.na);
    if (m.nk == NM_LOCK) {
        add_group(m.na);
        add_group(m.nb);
    }
    if (m.nk == NM_NARY) {
        if (m.na >= 0 && m.na < (int)p.nary.size())
            for (int c : p.nary[m.na].vars) add(c);
        add_group(m.nb);
    }
    const bool naked_direct = m.pc >= 0 && m.nk == NM_NONE && is_direct(m.tech);
    if (naked_direct || m.tech == NAKED_N)  // naked single: the target's houses
        for (int gi : p.groups_of[m.pc])
            if (p.groups[gi].complete) add_group(gi);
    const bool chain = m.tech == X_CHAIN || m.tech == XY_CHAIN || m.tech == AIC_CHAIN || m.tech == NICE_LOOP || m.tech == MENTAL_CHAIN ||
                       m.tech == REMOTE_PAIRS || m.tech == EMPTY_RECT ||
                       m.tech == ALS_AIC;
    const bool combo = (m.tech >= SUM_COMBO && m.tech <= TABLE_COMBO) ||
                       (m.tech >= SANDWICH_COMBO && m.tech <= LOL_COMBO) || m.tech == COUNT_COMBO;
    pm_long combos = 0;
    const bool forcing = m.tech == FORCING || m.tech == DYN_FORCING || m.tech == NESTED_FORCING || m.tech == WHAT_IF;
    if (m.tech == EITHER_WAY) combos = 2;  // two branches held in mind
    if (forcing) combos = m.extra;         // k branches
    // case analyses: every cell the branches fill is followed (in the head or on paper)
    if (m.tech == EITHER_WAY) scanned += (int)(x[0] + x[1]);
    if (m.tech == SHORT_TRIAL) scanned += (int)x[1];
    if (forcing) scanned += (int)x[4];
    if (combo) combos = x[2];
    else if (m.tech == LINE_RANGE) combos = x[6];
    else if (m.tech == INNIE_X) combos = x[3];
    else if (m.tech == COMBO_LOCK) combos = x[2];
    else if (m.tech == CAGE_COMBO && m.na >= 0 && m.na < p.G && p.D == 9) {
        const Group& g = p.groups[m.na];
        int tri = 0, k = 0;
        for (int mask = 1; mask < 512; ++mask) {
            if (__builtin_popcount(mask) != (int)g.cells.size()) continue;
            int sum = 0;
            for (int d = 1; d <= 9; ++d)
                if (mask >> (d - 1) & 1) sum += d;
            k += sum == g.total;
        }
        combos = k;
        (void)tri;
    }
    double depth = 0;
    if (m.tech == LINE_D || m.tech == MENTAL_D) depth = (double)x[1];
    else if (m.tech == LINE_RANGE) depth = (double)x[5];
    else if (chain) depth = x[0] / 2.0;
    else if (m.tech == SHORT_TRIAL || m.tech == EITHER_WAY) depth = (double)m.extra;
    else if (m.tech == TRIAL) depth = 4;
    else if (m.tech == WHAT_IF) depth = 4.0;
    else if (forcing) depth = 4.0 * (1 + x[0]);  // nesting level multiplies the depth
    else if (m.tech == MEDUSA) depth = x[1] / 2.0;
    else if (m.tech == LOL_COMBO || (m.tech == COMBO_LOCK && x[3] == 1)) depth = 1;
    int cons = 0;
    if ((m.nk == NM_GROUP || m.nk == NM_INNIE || m.nk == NM_OUTIE) && m.na >= 0) cons += 1;
    if (m.nk == NM_LOCK) cons += 2;
    if (m.nk == NM_NARY) cons += 1;
    if (is_direct(m.tech)) cons += m.cov_n + 1;
    if (chain) cons += (int)(x[1] + x[2] + x[3] + x[4]);
    if (m.tech == FINNED_FISH || m.tech == JELLYFISH) cons += 2 * (int)x[0];
    if (m.tech == XWING || m.tech == SWORDFISH) cons += 2 * m.extra;
    if (m.tech == ALS_XZ) cons += 2;
    if (m.tech == ALS_XYWING) cons += 3;
    if (m.tech == DEATH_BLOSSOM) cons += (int)x[0];
    if (m.tech == UNIQUE_RECT) cons += 4;
    if (m.tech == MEDUSA) cons += (int)x[1];
    if (cons < 1) cons = 1;
    int nvars = m.nk == NM_NARY && m.na >= 0 && m.na < (int)p.nary.size() ? p.nary[m.na].nv() : 0;
    bool search = m.tech == TABLE_COMBO || m.tech == TRIAL || m.tech == SHORT_TRIAL || m.tech == GUESS ||
                  m.tech == EITHER_WAY || forcing ||
                  m.tech == ALS_AIC || (m.tech == LOL_COMBO && nvars > 6) || (m.tech == LINE_RANGE && x[2] > 6) ||
                  (combo && combos > 6) || (m.tech == COMBO_LOCK && x[3] == 1) || (chain && x[0] > 9);
    m.load[0] = (float)scanned;
    m.load[1] = (float)std::log(1.0 + (double)std::max(pm_long(0), combos));
    m.load[2] = (float)depth;
    m.load[3] = (float)cons;
    m.load[4] = search ? 1.0f : 0.0f;
    m.load[5] = (float)pc.size();
    m.load[6] = chain ? (float)x[0] : m.tech == MEDUSA ? (float)x[1] : 0.0f;
    {  // reveal depth: distinct earlier non-single moves that removed candidates of the pattern cells
        int rd = 0;
        if (!adv_src.empty()) {
            std::vector<int> st;
            for (int c : pc) {
                if (c < 0 || c >= p.N || vals[c]) continue;
                for (uint32_t gone = p.full & ~cand[c]; gone; gone &= gone - 1) {
                    const int s0 = adv_src[(size_t)c * 32 + lowdigit(gone)];
                    if (s0 >= 0 && std::find(st.begin(), st.end(), s0) == st.end()) st.push_back(s0);
                }
            }
            rd = (int)st.size();
        }
        m.load[7] = (float)rd;
    }
    m.has_load = true;
}

void Solver::rich_after(const Move& chosen, bool notes_event) {
    ++rich_step_idx;
    if (notes_event) return;
    if (rich_best >= 0 && rich_best < (int)rich_pats.size()) rich_prev = rich_pats[rich_best];
    rich_tech_used[chosen.tech]++;
    if (chosen.pc >= 0) {
        rich_last = chosen.pc;
        rich_digit_run = chosen.pv == rich_last_digit ? rich_digit_run + 1 : 1;
        rich_last_digit = chosen.pv;
    }
}

}  // namespace cs
