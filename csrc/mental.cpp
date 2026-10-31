// Direct-mode (no notes) mental layer: what a solver can infer from placed
// digits, house exclusions and the puzzle's relations / lines without
// writing candidates. Bounded: two relation rounds (+ inequality bounds to a
// fixpoint, line consistency), then mental subsets of size <= 3 and one more
// relation round.
#include <algorithm>
#include "portable.hpp"
#include <set>
#include <unordered_map>
#include <cstdio>
#include <cstdlib>

#include "solver.hpp"

namespace cs {

namespace {
enum { RS_ARC = 1, RS_INEQ = 2, RS_LINE = 3, RS_SUBSET = 4 };
inline uint32_t range_mask(int lo, int hi) {
    if (hi < lo) return 0;
    uint32_t up = hi >= 32 ? 0xffffffffu : ((1u << hi) - 1);
    uint32_t dn = (1u << (lo - 1)) - 1;
    return up & ~dn;
}
inline int dlo(uint32_t m) { return m ? __builtin_ctz(m) + 1 : 0; }
inline int dhi(uint32_t m) { return m ? 32 - __builtin_clz(m) : 0; }
}  // namespace

bool Solver::compute_mental(int level) {
    if (mental_version == version && mental_level >= level) return true;
    mental_version = version;
    mental_level = level;
    const int N = p.N, D1 = p.D + 1;
    compute_empties();
    direct_excl();
    md.assign(N, 0);
    for (int c = 0; c < N; ++c) md[c] = vals[c] ? bit(vals[c]) : (p.full & ~ex[c]);
    rs_type.assign((size_t)N * 32, 0);
    rs_depth.assign((size_t)N * 32, 0);
    rs_size.assign((size_t)N * 32, 0);
    rs_line.assign((size_t)N * 32, -1);
    auto drop = [&](int c, uint32_t keep, int type, int depth, int line, int size) {
        uint32_t lost = md[c] & ~keep;
        if (!lost) return false;
        for (uint32_t m = lost; m; m &= m - 1) {
            size_t i = (size_t)c * 32 + lowdigit(m);
            rs_type[i] = (uint8_t)type;
            rs_depth[i] = (uint8_t)depth;
            rs_line[i] = (int16_t)line;
            rs_size[i] = (uint8_t)size;
        }
        md[c] &= keep;
        return true;
    };
    std::vector<int> preds, succs;
    std::vector<int> los;
    uint32_t dom[64];
    // Jacobi rounds: every inference of a round uses the view at its start, and a
    // digit removed by several kinds of reasoning is credited by a fixed priority
    // (line > inequality > arc) -> independent of cell / house scan order
    std::vector<uint32_t> keep_line, keep_ineq, keep_arc;
    auto relation_round = [&](int depth) {
        const std::vector<uint32_t> md0 = md;
        keep_line.assign(N, 0xffffffffu);
        keep_ineq.assign(N, 0xffffffffu);
        keep_arc.assign(N, 0xffffffffu);
        // (1) whole lines (consistency over the line with the digits known so far)
        // every rule over several cells: lines, arrows, sums, killer cages (index >=
        // nary.size() = cage_nary), not the solver-made leftover regions
        const size_t NL = p.nary.size(), NT = NL + p.cage_nary.size();
        for (size_t li = 0; li < NT; ++li) {
            const NConstraint& k = li < NL ? p.nary[li] : p.cage_nary[li - NL];
            if (k.type == NT_SAMESET) continue;
            bool any_empty = false;
            for (int i = 0; i < k.nv(); ++i) {
                dom[i] = md0[k.vars[i]];
                any_empty |= !vals[k.vars[i]];
            }
            if (!any_empty) continue;
            const GacOut& o = gac_cached(k, dom);
            if (!o.any && o.complete) continue;  // inconsistent view: leave it to the notes phase
            // a whole-rule reading without notes is human only while the rule has few consistent fillings;
            // above T = 50 (or unknown) it is left to the notes phase (combination moves priced by size).
            // CSOLVER_MENTAL_LINE_MAX=0: off.
            static const pm_long mental_line_max = getenv("CSOLVER_MENTAL_LINE_MAX") ? atol(getenv("CSOLVER_MENTAL_LINE_MAX")) : 50;
            if (mental_line_max > 0 && (!o.complete || o.count > mental_line_max)) continue;
            for (int i = 0; i < k.nv(); ++i)
                if (!vals[k.vars[i]]) keep_line[k.vars[i]] &= o.sup[i];
        }
        // (2) inequality bounds from the start-of-round view, iterated to a fixpoint
        //     on a private copy (chains of any length)
        {
            std::vector<uint32_t> mi = md0;
            for (int it = 0; it < 9; ++it) {
                bool ch = false;
                std::vector<uint32_t> nxt = mi;
                for (int c : empties) {
                    int L = dlo(mi[c]), U = dhi(mi[c]);
                    if (!L) continue;
                    preds.clear();
                    succs.clear();
                    for (size_t j = 0; j < p.rel[c].size(); ++j) {
                        if (p.rel_dir[c][j] < 0) preds.push_back(p.rel[c][j]);
                        if (p.rel_dir[c][j] > 0) succs.push_back(p.rel[c][j]);
                    }
                    if (preds.empty() && succs.empty()) continue;
                    for (int q : preds) L = std::max(L, dlo(mi[q]) + 1);
                    for (int q : succs) U = std::min(U, dhi(mi[q]) - 1);
                    for (int gi : p.groups_of[c]) {  // mutually distinct predecessors / successors
                        los.clear();
                        for (int q : preds)
                            if (tbit(p.gbits(gi), q)) los.push_back(dlo(mi[q]));
                        if (los.size() > 1) {
                            std::sort(los.begin(), los.end());
                            int v = 0;
                            for (int l : los) v = std::max(l, v + 1);
                            L = std::max(L, v + 1);
                        }
                        los.clear();
                        for (int q : succs)
                            if (tbit(p.gbits(gi), q)) los.push_back(-dhi(mi[q]));
                        if (los.size() > 1) {
                            std::sort(los.begin(), los.end());
                            int v = p.D + 1;
                            for (int l : los) v = std::min(-l, v - 1);
                            U = std::min(U, v - 1);
                        }
                    }
                    uint32_t nm = mi[c] & range_mask(std::max(L, 1), std::min(U, p.D));
                    if (nm != mi[c] && nm) {
                        nxt[c] = nm;
                        ch = true;
                    }
                }
                mi.swap(nxt);
                if (!ch) break;
            }
            for (int c : empties) keep_ineq[c] = mi[c] | ~md0[c];
        }
        // (3) arc consistency on every relation edge (start-of-round view)
        for (int c : empties) {
            for (size_t j = 0; j < p.rel[c].size(); ++j) {
                int q = p.rel[c][j];
                const uint32_t* tin = &p.rel_in[c][j * D1];  // rel_ex[q][c]
                uint32_t allowed = 0;
                for (uint32_t m = md0[q]; m; m &= m - 1) allowed |= ~tin[lowdigit(m)];
                keep_arc[c] &= allowed | ~p.full;
            }
        }
        bool changed = false;
        for (int c : empties) {
            changed |= drop(c, keep_line[c], RS_LINE, depth, -1, 0);
            changed |= drop(c, keep_ineq[c], RS_INEQ, depth, -1, 0);
            changed |= drop(c, keep_arc[c], RS_ARC, depth, -1, 0);
        }
        // line index of line-credited drops: the first line (in constraint order) excluding it
        for (size_t li = 0; li < NT; ++li) {
            const NConstraint& k = li < NL ? p.nary[li] : p.cage_nary[li - NL];
            if (k.type == NT_SAMESET) continue;
            for (int c : k.vars) {
                if (vals[c]) continue;
                for (uint32_t m = md0[c] & ~md[c]; m; m &= m - 1) {
                    size_t i = (size_t)c * 32 + lowdigit(m);
                    if (rs_type[i] == RS_LINE && rs_depth[i] == depth && rs_line[i] < 0) rs_line[i] = (int16_t)li;
                }
            }
        }
        return changed;
    };
    relation_round(1);
    relation_round(2);
    for (int c = 0; c < N; ++c) {
        if (!md[c] && !vals[c]) md[c] = p.full & ~ex[c];  // never let the mental view go empty
    }
    mex_rel.assign(N, 0);
    for (int c : empties) mex_rel[c] = p.full & ~ex[c] & ~md[c];
    mex_ment.assign(N, 0);
    if (level < 3) return true;
    // mental subsets: k cells of a house whose mental digits form a set of size k (k = 2, 3);
    // found on the post-relation view, pairs credited before triples
    std::vector<uint32_t> snap = md;
    std::vector<uint32_t> keep2(N, 0xffffffffu), keep3(N, 0xffffffffu), keepp(N, 0xffffffffu);
    std::vector<int> keeppn(N, 0);
    // explanation only: the house of the subset / pointing that removed (cell, digit) first
    std::vector<int16_t> h2((size_t)N * 32, -1), h3((size_t)N * 32, -1), hp((size_t)N * 32, -1);
    auto note_house = [&](std::vector<int16_t>& h, int q, uint32_t m, int house) {
        for (; m; m &= m - 1) {
            int16_t& x = h[(size_t)q * 32 + lowdigit(m)];
            if (x < 0) x = (int16_t)house;
        }
    };
    std::vector<int> emp;
    for (int hi : p.houses) {
        emp.clear();
        for (int c : p.groups[hi].cells)
            if (!vals[c] && popc(snap[c]) <= 3) emp.push_back(c);
        const int n = (int)emp.size();
        for (int a = 0; a < n; ++a)
            for (int b = a + 1; b < n; ++b) {
                uint32_t u2 = snap[emp[a]] | snap[emp[b]];
                if (popc(u2) == 2) {
                    for (int q : p.groups[hi].cells)
                        if (!vals[q] && q != emp[a] && q != emp[b]) {
                            keep2[q] &= ~u2;
                            note_house(h2, q, u2, hi);
                        }
                }
                for (int c3 = b + 1; c3 < n; ++c3) {
                    uint32_t u3 = u2 | snap[emp[c3]];
                    if (popc(u3) != 3) continue;
                    for (int q : p.groups[hi].cells)
                        if (!vals[q] && q != emp[a] && q != emp[b] && q != emp[c3]) {
                            keep3[q] &= ~u3;
                            note_house(h3, q, u3, hi);
                        }
                }
            }
    }
    // mental pointing on the same view: digit v of house B confined to 2-3 cells that
    // all share another group A -> v leaves A outside B
    for (int bi : p.houses) {
        for (uint32_t mm = p.full & ~placed_g[bi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            std::vector<int> poss;
            for (int c : p.groups[bi].cells)
                if (!vals[c] && (snap[c] & b)) poss.push_back(c);
            if (poss.size() < 2 || poss.size() > 3) continue;
            for (int ai : p.groups_of[poss[0]]) {
                if (ai == bi) continue;
                bool all = true;
                for (int c : poss) all &= tbit(p.gbits(ai), c);
                if (!all) continue;
                for (int q : p.groups[ai].cells)
                    if (!vals[q] && !tbit(p.gbits(bi), q)) {
                        keepp[q] &= ~b;
                        keeppn[q] = std::max(keeppn[q], (int)poss.size());
                        note_house(hp, q, b, 16384 + bi);  // pointing: base house bi
                    }
            }
        }
    }
    for (int c : empties) {
        // rs_line of a subset drop: its house (pointing: 16384 + base house); explanation only
        auto drop_h = [&](uint32_t keep, int size, const std::vector<int16_t>& h) {
            uint32_t lost = md[c] & ~keep;
            drop(c, keep, RS_SUBSET, 3, -1, size);
            for (; lost; lost &= lost - 1) {
                size_t i = (size_t)c * 32 + lowdigit(lost);
                rs_line[i] = h[i];
            }
        };
        drop_h(keep2[c], 2, h2);
        drop_h(keep3[c], 3, h3);
        drop_h(keepp[c], keeppn[c], hp);
    }
    relation_round(4);
    for (int c : empties) {
        if (!md[c]) md[c] = snap[c];
        mex_ment[c] = p.full & ~ex[c] & ~md[c] & ~mex_rel[c];
    }
    if (std::getenv("CSOLVER_MENTALDEBUG")) {
        for (int c = 0; c < N; ++c) std::fprintf(stderr, "%d:%x ", c, md[c]);
        std::fprintf(stderr, "\n");
    }
    return true;
}

}  // namespace cs

namespace cs {

// One assumption, propagated with the reasoning a solver does without notes plus
// constraint consistency: singles, pair-relation arcs, every n-ary constraint
// (cages, lines, arrows, ...). Contradiction = an empty cell, a house missing a
// digit, or an unsatisfiable constraint. Bounded by max_rounds.
// Basic propagation in place (Jacobi rounds): singles, pair-relation arcs, every n-ary
// constraint's consistency. Returns the round of the first contradiction (0: none).
int Solver::prop_rounds(int max_rounds, int& placed, std::vector<int>* log) {
    // log: events (type, round, cell, digit | mask, source), see EV_* in solver.hpp
    auto ev = [&](int type, int round, int cell, int dm, int src) {
        if (log) log->insert(log->end(), {type, round, cell, dm, src});
    };
    const int N = p.N, D1 = p.D + 1;
    int result = 0;
    placed = 0;
    uint32_t dom[64];
    for (int round = 1; round <= max_rounds && !result; ++round) {
        bool progress = false;
        // singles found on the round's snapshot, placed together (scan-order independent)
        std::vector<std::pair<int, int>> todo;
        std::vector<std::pair<std::pair<int, int>, int>> why;  // (cell, digit) -> house (-1 naked); log only
        for (int x = 0; x < N && !result; ++x) {
            if (vals[x]) continue;
            if (!cand[x]) {
                result = round;
                ev(EV_X_EMPTY, round, x, 0, -1);
            } else if (popc(cand[x]) == 1) {
                todo.push_back({x, lowdigit(cand[x])});
                if (log) why.push_back({todo.back(), -1});
            }
        }
        for (int hi : p.houses) {
            if (result) break;
            if (!log) {  // one pass per house: digits seen once / at least twice (same singles, same verdict)
                uint32_t once = 0, twice = 0;
                for (int x : p.groups[hi].cells)
                    if (!vals[x]) {
                        twice |= once & cand[x];
                        once |= cand[x];
                    }
                const uint32_t need = p.full & ~placed_g[hi];
                if (need & ~once) {
                    result = round;
                    break;
                }
                for (uint32_t mm = need & once & ~twice; mm; mm &= mm - 1) {
                    const uint32_t b = mm & (~mm + 1);
                    for (int x : p.groups[hi].cells)
                        if (!vals[x] && (cand[x] & b)) {
                            todo.push_back({x, lowdigit(b)});
                            break;
                        }
                }
                continue;
            }
            for (uint32_t mm = p.full & ~placed_g[hi]; mm && !result; mm &= mm - 1) {
                uint32_t b = mm & (~mm + 1);
                int n = 0, at = -1;
                for (int x : p.groups[hi].cells)
                    if (!vals[x] && (cand[x] & b)) {
                        ++n;
                        at = x;
                    }
                if (n == 0) {
                    result = round;
                    ev(EV_X_HOUSE, round, -1, lowdigit(b), hi);
                } else if (n == 1) {
                    todo.push_back({at, lowdigit(b)});
                    if (log) why.push_back({todo.back(), hi});
                }
            }
        }
        if (result) break;
        std::sort(todo.begin(), todo.end());
        todo.erase(std::unique(todo.begin(), todo.end()), todo.end());
        placed += (int)todo.size();  // counted per round: independent of placement order
        for (auto& cv : todo) {
            if (vals[cv.first]) {  // the same cell twice with different digits
                if (vals[cv.first] != cv.second) {
                    result = round;
                    ev(EV_X_CLASH, round, cv.first, cv.second, -1);
                }
                continue;
            }
            if (!(cand[cv.first] & bit(cv.second))) {  // conflicts with another single of this round
                result = round;
                ev(EV_X_CLASH, round, cv.first, cv.second, -1);
                break;
            }
            if (log) {
                int h = -1;
                bool naked = false;
                for (auto& w : why)
                    if (w.first == cv) {
                        if (w.second < 0) naked = true;
                        else if (h < 0) h = w.second;
                    }
                ev(naked ? EV_NAKED : EV_HIDDEN, round, cv.first, cv.second, naked ? -1 : h);
            }
            place(cv.first, cv.second);
            progress = true;
        }
        if (result) break;
        // pair relations (from the post-placement snapshot)
        const std::vector<uint32_t> c0 = cand;
        for (int x = 0; x < N; ++x) {
            if (vals[x]) continue;
            for (size_t j = 0; j < p.rel[x].size(); ++j) {
                int q = p.rel[x][j];
                uint32_t dq = vals[q] ? bit(vals[q]) : c0[q];
                const uint32_t* tin = &p.rel_in[x][j * D1];
                uint32_t allowed = 0;
                for (uint32_t m = dq; m; m &= m - 1) allowed |= ~tin[lowdigit(m)];
                if (cand[x] & ~allowed) {
                    ev(EV_REL, round, x, (int)(cand[x] & ~allowed), q);
                    cand[x] &= allowed;
                    progress = true;
                }
            }
            if (!cand[x]) {
                if (!result) ev(EV_X_EMPTY, round, x, 0, -1);
                result = round;
            }
        }
        if (result) break;
        // constraints (cages, lines, n-ary rules)
        for (int pass = 0; pass < 2 && !result; ++pass)
            for (const NConstraint& k : pass ? p.cage_nary : p.nary) {
                if (k.type == NT_SAMESET) continue;
                for (int i = 0; i < k.nv(); ++i) dom[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                // same rule, same domains, same budget -> same result: reuse the last one per rule
                auto& lc = prop_gac[&k];
                if (!(lc.valid && std::equal(dom, dom + k.nv(), lc.dom.begin()))) {
                    lc.dom.assign(dom, dom + k.nv());
                    gac_prop(k, dom, 2000, lc.out);  // other assumptions, steps and calls meet the same domains
                    lc.valid = true;
                }
                const GacOut& o = lc.out;
                const int kr = cref(k.index, k.group);
                if (o.complete && !o.any) {
                    result = round;
                    ev(EV_X_RULE, round, -1, 0, kr);
                    break;
                }
                for (int i = 0; i < k.nv(); ++i) {
                    int x = k.vars[i];
                    if (vals[x]) {
                        if (!(o.sup[i] & bit(vals[x]))) {
                            if (!result) ev(EV_X_RULE, round, x, vals[x], kr);
                            result = round;
                        }
                        continue;
                    }
                    if (cand[x] & ~o.sup[i]) {
                        ev(EV_RULE, round, x, (int)(cand[x] & ~o.sup[i]), kr);
                        cand[x] &= o.sup[i];
                        progress = true;
                    }
                    if (!cand[x]) {
                        if (!result) ev(EV_X_EMPTY, round, x, 0, -1);
                        result = round;
                    }
                }
                if (result) break;
            }
        if (!progress) break;
    }
    return result;
}

int Solver::case_split(int c0, int v0, int max_rounds, int& placed, std::vector<uint8_t>* ov,
                       std::vector<uint32_t>* oc, std::vector<int>* log) {
    // memo over the exact state (all values and candidates): EitherWay, ShortTrial and the colour
    // seeds split the same assumptions at the same state within a step
    uint64_t sig = 0;
    if (!log) {
        uint64_t h = 1469598103934665603ULL;
        for (int x = 0; x < p.N; ++x) h = (h ^ ((uint64_t)vals[x] << 32 | cand[x])) * 1099511628211ULL;
        sig = h ^ ((uint64_t)c0 << 8) ^ ((uint64_t)v0 << 20) ^ ((uint64_t)max_rounds << 40);
        auto it = split_memo.find(sig);
        if (it != split_memo.end() && it->second.vals == vals && it->second.cand == cand && it->second.c0 == c0 &&
            it->second.v0 == v0 && it->second.rounds == max_rounds) {
            placed = it->second.placed;
            if (ov) *ov = it->second.ov;
            if (oc) *oc = it->second.oc;
            return it->second.result;
        }
    }
    std::vector<uint8_t> sv = vals;
    std::vector<uint32_t> sc = cand, sg = placed_g;
    place(c0, v0);
    const int result = prop_rounds(max_rounds, placed, log);
    if (ov) *ov = vals;
    if (oc) *oc = cand;
    if (!log) {
        if (split_memo.size() > 4096) split_memo.clear();  // bounded (~4096 x 2 x N words)
        SplitMemo m{sv, sc, c0, v0, max_rounds, result, placed, vals, cand};
        split_memo[sig] = std::move(m);
    }
    vals.swap(sv);
    cand.swap(sc);
    placed_g.swap(sg);
    return result;
}

void Solver::short_trial(MoveBuf& out) {
    if (disabled[SHORT_TRIAL]) return;
    for (int c = 0; c < p.N; ++c) {
        if (vals[c] || popc(cand[c]) != 2) continue;
        for (uint32_t dm = cand[c]; dm; dm &= dm - 1) {
            int v = lowdigit(dm), placed = 0;
            int r = case_split(c, v, 4, placed);
            if (!r) continue;
            Move& m = new_move(out, SHORT_TRIAL, 1.0, r);
            out.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
            ++m.el_n;
            add_expl(out, m, EX_TRIAL, {0, 1, c, v});
            set_pattern(out, m, {c});
            m.has_meta = true;
            m.meta[0] = 1 + placed;  // cells touched by the propagation
            m.meta[1] = 1;
            m.meta[2] = 2;
            m.meta[3] = r;           // links = rounds to the contradiction
            m.meta[4] = 0;
            m.meta[5] = 0;
            m.meta[6] = 0;
            m.meta[7] = 1;
            m.spread = 1.0;
            pm_long xm[XM_N] = {r, placed, 0, 0, 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

}  // namespace cs

namespace cs {

// Short chains reasoned without notes: chains (<= 5 links) over the mental view (digits a
// cell can hold given houses, relations and mental subsets); their eliminations are
// held in mind and pay off as a single.
void Solver::mental_chains(MoveBuf& out) {
    if (disabled[MENTAL_CHAIN]) return;
    compute_mental(3);
    const std::vector<uint32_t> view = md;
    const std::vector<uint32_t> saved = cand;
    for (int c = 0; c < p.N; ++c)
        if (!vals[c]) cand[c] = view[c];
    // private chain build (the notes-mode chain cache stays untouched)
    const pm_long sv = aic_version;
    const int sd = aic_depth;
    MoveBuf sb = aic_buf;
    std::vector<int> sl = aic_len;
    aic_version = -1;
    label_version = -1;  // labels must describe the mental view, not the candidates
    build_aic(5);
    MoveBuf ch = aic_buf;
    std::vector<int> lens = aic_len;
    aic_version = sv;
    aic_depth = sd;
    aic_buf = sb;
    aic_len = sl;
    cand = saved;
    label_version = -1;
    std::vector<uint32_t> md2;
    for (size_t i = 0; i < ch.moves.size(); ++i) {
        const Move& cm = ch.moves[i];
        if (lens[i] > 5) continue;
        std::vector<int> pat(ch.pats.begin() + cm.pat_off, ch.pats.begin() + cm.pat_off + cm.pat_n);
        auto emit = [&](int c, int v) {
            Move& m = new_move(out, MENTAL_CHAIN, cm.shape, lens[i]);
            m.pc = c;
            m.pv = v;
            std::vector<int> pc = pat;
            pc.push_back(c);
            set_pattern(out, m, pc);
            m.ex_off = (int)out.ex.size();  // the chain's links / ALS records
            out.ex.insert(out.ex.end(), ch.ex.begin() + cm.ex_off, ch.ex.begin() + cm.ex_off + cm.ex_n);
            m.ex_n = cm.ex_n;
            m.has_meta = true;
            std::copy(cm.meta, cm.meta + 8, m.meta);
            m.meta[0] = std::min(p.N, cm.meta[0] + 1);
            m.meta[7] = 0;  // no notes
            m.spread = cm.spread;
            std::copy(cm.xm, cm.xm + XM_N, m.xm);
            m.code = cm.code;
        };
        if (cm.pc >= 0) {  // discontinuous nice loop: places directly
            emit(cm.pc, cm.pv);
            continue;
        }
        md2 = view;
        std::vector<int> touched;
        for (int k = 0; k < cm.el_n; ++k) {
            uint32_t e = ch.elims[cm.el_off + k];
            md2[e / 32] &= ~bit((int)(e % 32));
            touched.push_back((int)(e / 32));
        }
        for (int c : touched)  // naked single in the mind
            if (!vals[c] && popc(md2[c]) == 1 && popc(view[c]) > 1) emit(c, lowdigit(md2[c]));
        std::vector<int> hs;
        for (int c : touched)
            for (int gi : p.groups_of[c])
                if (p.groups[gi].complete) hs.push_back(gi);
        std::sort(hs.begin(), hs.end());
        hs.erase(std::unique(hs.begin(), hs.end()), hs.end());
        for (int hi : hs)  // hidden single in the mind
            for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
                uint32_t b = mm & (~mm + 1);
                int n2 = 0, n1 = 0, at = -1;
                for (int c : p.groups[hi].cells) {
                    if (vals[c]) continue;
                    n1 += (view[c] & b) != 0;
                    if (md2[c] & b) {
                        ++n2;
                        at = c;
                    }
                }
                if (n2 == 1 && n1 > 1) emit(at, lowdigit(b));
            }
    }
}

}  // namespace cs

namespace cs {

// "Either way": both options of a two-way choice (a two-candidate cell, or a digit with
// exactly two cells in a house) are followed for a few rounds; what both branches agree
// on holds. direct_view: on the no-notes mental view, placements only.
void Solver::either_way(MoveBuf& out, bool direct_view) {
    if (disabled[EITHER_WAY]) return;
    std::vector<uint32_t> saved;
    if (direct_view) {
        compute_mental(3);
        saved = cand;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) cand[c] = md[c];
    }
    struct Opt { int c, v; };
    std::vector<std::pair<Opt, Opt>> choices;
    for (int c = 0; c < p.N; ++c)
        if (!vals[c] && popc(cand[c]) == 2) {
            int a = lowdigit(cand[c]), b = lowdigit(cand[c] & (cand[c] - 1));
            choices.push_back({{c, a}, {c, b}});
        }
    for (int hi : p.houses)
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm), n = 0, cs2[2];
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & bit(v))) {
                    if (n < 2) cs2[n] = c;
                    ++n;
                }
            if (n == 2) choices.push_back({{cs2[0], v}, {cs2[1], v}});
        }
    std::vector<uint8_t> va, vb;
    std::vector<uint32_t> ca, cb;
    std::set<std::vector<uint32_t>> seen;
    // the same assumption appears in several choices (a bivalue cell and up to three houses):
    // propagate each once (same state, same result)
    struct Br { int r, placed; std::vector<uint8_t> v; std::vector<uint32_t> c; };
    std::unordered_map<uint32_t, Br> memo;
    auto branch = [&](int c, int v, int& placed, std::vector<uint8_t>& ov, std::vector<uint32_t>& oc) {
        const uint32_t key = (uint32_t)c * 32u + (uint32_t)v;
        auto it = memo.find(key);
        if (it == memo.end()) {
            Br b;
            b.r = case_split(c, v, 4, b.placed, &b.v, &b.c);
            it = memo.emplace(key, std::move(b)).first;
        }
        placed = it->second.placed;
        ov = it->second.v;
        oc = it->second.c;
        return it->second.r;
    };
    for (auto& ch : choices) {
        int pa = 0, pb = 0;
        int ra = branch(ch.first.c, ch.first.v, pa, va, ca);
        int rb = branch(ch.second.c, ch.second.v, pb, vb, cb);
        if (ra || rb) continue;  // a contradicting branch is ShortTrial's business
        const int rounds = 4;
        std::vector<int> pat{ch.first.c, ch.second.c};
        for (int x = 0; x < p.N; ++x) {
            if (vals[x]) continue;
            int d = 0;
            if (va[x] && va[x] == vb[x]) d = va[x];
            uint32_t gone = 0;
            if (!direct_view) {
                uint32_t ka = va[x] ? bit(va[x]) : ca[x], kb = vb[x] ? bit(vb[x]) : cb[x];
                gone = cand[x] & ~(ka | kb);
            }
            if (!d && !gone) continue;
            std::vector<uint32_t> key{(uint32_t)x, (uint32_t)d, gone};
            if (!canon && !seen.insert(key).second) continue;  // canonical: cheapest kept by canon_dedupe
            Move& m = new_move(out, EITHER_WAY, 1.0, rounds);
            if (d) {
                m.pc = x;
                m.pv = d;
            } else {
                for (uint32_t g = gone; g; g &= g - 1) {
                    out.elims.push_back((uint32_t)x * 32u + (uint32_t)lowdigit(g));
                    ++m.el_n;
                }
            }
            std::vector<int> pc = pat;
            pc.push_back(x);
            set_pattern(out, m, pc);
            add_expl(out, m, EX_TRIAL, {direct_view ? 1 : 0, 2, ch.first.c, ch.first.v, ch.second.c, ch.second.v});
            m.has_meta = true;
            m.meta[0] = std::min(p.N, 3 + pa + pb);  // cells followed in both branches
            m.meta[1] = 2;
            m.meta[2] = 2;
            m.meta[3] = rounds;
            m.meta[4] = 0;
            m.meta[5] = 0;
            m.meta[6] = 0;
            m.meta[7] = direct_view ? 0 : 1;
            m.spread = pspread(pc);
            pm_long xm[XM_N] = {pa, pb, ch.first.c == ch.second.c, direct_view, 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
    if (direct_view) {
        cand = saved;
        label_version = -1;
    }
}

}  // namespace cs

namespace cs {

// Line reasoning on digit classes: a person tracks "low / high", "odd / even", "which third"
// along a line instead of digits. Classes come from the line kind (whispers: from the rule
// table -- digits that only pair upwards / downwards / both / never). Class-level arc
// consistency over the line's relations removes whole classes (a relaxation of LineRange).
void Solver::line_classes(MoveBuf& out) {
    if (disabled[LINE_CLASS]) return;
    const int D = p.D;
    for (const NConstraint& k : p.nary) {
        if (k.line_kind < 0 || k.type != NT_LINE) continue;
        const int nv = k.nv();
        // digit -> class id
        std::vector<int> cls(D + 1, 0);
        int ncls = 0;
        const int lk = k.line_kind;
        if (lk == LK_ENTROPIC || lk == LK_MODULAR) {
            for (int d = 1; d <= D; ++d) cls[d] = lk == LK_ENTROPIC ? (d - 1) * 3 / D : (d - 1) % 3;
            ncls = 3;
        } else if (lk == LK_PARITY || lk == LK_KROPKI) {
            for (int d = 1; d <= D; ++d) cls[d] = d % 2;
            ncls = 2;
        } else if (lk == LK_WHISPER || lk == LK_DUTCH) {
            const uint32_t* t = nullptr;  // first adjacent relation table of the line
            for (int i = 0; i + 1 < nv && !t; ++i) t = k.rel[i * nv + i + 1];
            if (!t) continue;
            for (int d = 1; d <= D; ++d) {
                uint32_t ok = p.full & ~t[d];
                bool up = (ok >> d) != 0, dn = (ok & ((1u << (d - 1)) - 1)) != 0;
                cls[d] = up && !dn ? 0 : dn && !up ? 1 : up && dn ? 2 : 3;  // low, high, both, never
            }
            ncls = 4;
        } else {
            continue;
        }
        uint32_t cmask[8] = {0};
        for (int d = 1; d <= D; ++d) cmask[cls[d]] |= bit(d);
        // class domains
        std::vector<uint32_t> cd(nv, 0);
        bool any_empty = false;
        for (int i = 0; i < nv; ++i) {
            int c = k.vars[i];
            uint32_t dm = vals[c] ? bit(vals[c]) : cand[c];
            any_empty |= !vals[c];
            for (int q = 0; q < ncls; ++q)
                if (dm & cmask[q]) cd[i] |= 1u << q;
        }
        if (!any_empty) continue;
        // class compatibility per related pair: (A, B) allowed iff some a in A, b in B is allowed
        bool changed = true;
        for (int it = 0; it < 2 * nv && changed; ++it) {
            changed = false;
            for (int i = 0; i < nv; ++i)
                for (int j = 0; j < nv; ++j) {
                    const uint32_t* t = k.rel[i * nv + j];
                    if (!t || i == j) continue;
                    uint32_t keep = 0;
                    for (int a = 0; a < ncls; ++a) {
                        if (!(cd[i] >> a & 1)) continue;
                        for (int b = 0; b < ncls; ++b) {
                            if (!(cd[j] >> b & 1)) continue;
                            bool ok = false;
                            for (uint32_t ma = cmask[a]; ma && !ok; ma &= ma - 1)
                                if (cmask[b] & ~t[lowdigit(ma)]) ok = true;
                            if (ok) keep |= 1u << a;
                        }
                    }
                    if (cd[i] & ~keep) {
                        cd[i] &= keep;
                        changed = true;
                    }
                }
        }
        int n = 0;
        for (int i = 0; i < nv; ++i) {
            int c = k.vars[i];
            if (vals[c]) continue;
            uint32_t allowed = 0;
            for (int q = 0; q < ncls; ++q)
                if (cd[i] >> q & 1) allowed |= cmask[q];
            n += popc(cand[c] & ~allowed);
        }
        if (!n) continue;
        Move& m = new_move(out, LINE_CLASS, k.shape, nv);
        std::vector<int> pc;
        for (int i = 0; i < nv; ++i) {
            int c = k.vars[i];
            if (vals[c]) continue;
            pc.push_back(c);
            uint32_t allowed = 0;
            for (int q = 0; q < ncls; ++q)
                if (cd[i] >> q & 1) allowed |= cmask[q];
            for (uint32_t dm = cand[c] & ~allowed; dm; dm &= dm - 1) {
                out.elims.push_back((uint32_t)c * 32u + (uint32_t)lowdigit(dm));
                ++m.el_n;
            }
        }
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.na = k.index;
        m.has_meta = true;
        m.meta[0] = std::min(p.N, (int)pc.size());
        m.meta[1] = 1;
        m.meta[2] = ncls;  // classes instead of digits
        m.meta[3] = 0;
        m.meta[4] = 0;
        m.meta[5] = 0;
        m.meta[6] = 1;
        m.meta[7] = 1;
        m.spread = k.shape;
        m.code = 4000 + 10 * lk + 5;  // "<kind> classes"
        pm_long xm[XM_N] = {lk, k.index, nv, ncls, n, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

}  // namespace cs

namespace cs {

// Human case analysis (tech 94, CTC 'if this is a 4, this has to be 3 and this 2 ... and now this cell has a
// problem'; 'wherever the 5 goes in this box, that cell is a 7'). Bounded: each case is one assumption followed
// for at most case_rounds rounds of singles, pair relations and rule consistency (cages, lines, n-ary rules).
//   5501 refutation: an assumption (cell = digit, any cell with <= case_cands candidates) breaks -> eliminate it
//   5502 cell forcing: every option of a cell with 2-3 candidates that survives agrees on a consequence
//   5503 house forcing: every place of a digit in a house (2-4 places) that survives agrees on a consequence
// No own price: the structural model prices it from its descriptors (branches, depth = rounds, contradiction).
void Solver::human_case(MoveBuf& out) {
    if (disabled[HUMAN_CASE] || P.case_rounds <= 0) return;
    const int N = p.N, D = p.D, R = P.case_rounds;
    // one case: params case_light = 0 -> singles + pair relations + rule consistency for R rounds;
    // 1 -> also the light techniques (tiers up to intersections / pairs) inside the case, <= 10 x R steps
    auto run_case = [&](int c, int v, int& placed, std::vector<uint8_t>* ov, std::vector<uint32_t>* oc) -> int {
        if (!P.case_light) return case_split(c, v, R, placed, ov, oc);
        fc_ceiling_now = 2;
        fc_step_cap = 10 * R;
        int steps = 0;
        const int r = fc_branch(c, v, 1, steps, ov, oc);
        fc_ceiling_now = -1;
        fc_step_cap = 0;
        placed = steps;
        return r;
    };
    std::set<std::vector<uint32_t>> seen;
    auto meta_case = [&](Move& m, int cells, int branches, int digits, int rounds) {
        m.has_meta = true;
        m.meta[0] = std::max(1, std::min(N, cells));
        m.meta[1] = std::max(1, branches);
        m.meta[2] = std::max(1, std::min(D, digits));
        m.meta[3] = std::max(1, rounds);
        m.meta[4] = 0;
        m.meta[5] = 0;
        m.meta[6] = 0;
        m.meta[7] = 1;
        m.spread = 1.0;
    };
    // 5501: refutations
    for (int c = 0; c < N; ++c) {
        if (vals[c] || popc(cand[c]) < 2 || popc(cand[c]) > P.case_cands) continue;
        for (uint32_t dm = cand[c]; dm; dm &= dm - 1) {
            const int v = lowdigit(dm);
            int placed = 0;
            const int r = run_case(c, v, placed, nullptr, nullptr);
            if (!r) continue;
            Move& m = new_move(out, HUMAN_CASE, 1.0, 1);
            out.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
            ++m.el_n;
            add_expl(out, m, EX_TRIAL, {0, 1, c, v});
            set_pattern(out, m, {c});
            meta_case(m, 1 + placed, 1, popc(cand[c]), r);
            m.code = 5501;
            pm_long xm[XM_N] = {1, r, placed, 1, popc(cand[c]), 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
    // forcing over a set of options: consequences common to every surviving option (>= 2 survivors)
    auto forcing = [&](const std::vector<std::pair<int, int>>& opts, int code, int house) {
        const int k = (int)opts.size();
        std::vector<std::vector<uint8_t>> fv(k);
        std::vector<std::vector<uint32_t>> fc(k);
        std::vector<int> alive;
        int rmax = 0, placed_sum = 0;
        for (int i = 0; i < k; ++i) {
            int placed = 0;
            const int r = run_case(opts[i].first, opts[i].second, placed, &fv[i], &fc[i]);
            if (r) continue;
            alive.push_back(i);
            placed_sum += placed;
        }
        if (alive.size() < 2) return;
        rmax = R;
        std::vector<int> pat;
        for (auto& o : opts)
            if (std::find(pat.begin(), pat.end(), o.first) == pat.end()) pat.push_back(o.first);
        for (int x = 0; x < N; ++x) {
            if (vals[x]) continue;
            int d = -1;
            uint32_t keep = 0;
            for (int i : alive) {
                const int dv = fv[i][x];
                d = d == -1 ? dv : (d == dv ? d : 0);
                keep |= dv ? bit(dv) : fc[i][x];
            }
            if (d < 0) d = 0;
            const uint32_t gone = cand[x] & ~keep;
            if (!d && !gone) continue;
            if (d && !(cand[x] & bit(d))) continue;
            std::vector<uint32_t> key{(uint32_t)code, (uint32_t)x, (uint32_t)d, d ? 0u : gone};
            for (auto& o : opts) key.push_back((uint32_t)(o.first * 32 + o.second));
            if (!seen.insert(key).second) continue;
            Move& m = new_move(out, HUMAN_CASE, 1.0, (int)alive.size());
            if (d) {
                m.pc = x;
                m.pv = d;
            } else {
                for (uint32_t g = gone; g; g &= g - 1) out.elims.push_back((uint32_t)x * 32u + lowdigit(g)), ++m.el_n;
            }
            std::vector<int> rec{0, k};
            for (auto& o : opts) rec.push_back(o.first), rec.push_back(o.second);
            add_expl(out, m, EX_TRIAL, rec);
            if (house >= 0) add_expl(out, m, EX_BASE, {house});
            std::vector<int> pc = pat;
            if (std::find(pc.begin(), pc.end(), x) == pc.end()) pc.push_back(x);
            set_pattern(out, m, pc);
            uint32_t dg = 0;
            for (auto& o : opts) dg |= bit(o.second);
            meta_case(m, (int)pc.size() + placed_sum / std::max(1, (int)alive.size()), (int)alive.size(), popc(dg), rmax);
            m.code = code;
            pm_long xm[XM_N] = {(pm_long)alive.size(), rmax, placed_sum, 0, k, house, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    };
    for (int c = 0; c < N; ++c) {  // 5502: cells with 2-3 candidates
        if (vals[c] || popc(cand[c]) < 2 || popc(cand[c]) > 3) continue;
        std::vector<std::pair<int, int>> opts;
        for (uint32_t dm = cand[c]; dm; dm &= dm - 1) opts.push_back({c, lowdigit(dm)});
        forcing(opts, 5502, -1);
    }
    for (int hi : p.houses) {  // 5503: a digit's 2-4 places in a house
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            const int v = lowdigit(mm);
            std::vector<std::pair<int, int>> opts;
            for (int x : p.groups[hi].cells)
                if (!vals[x] && (cand[x] & bit(v))) opts.push_back({x, v});
            if (opts.size() < 2 || opts.size() > 4) continue;
            forcing(opts, 5503, hi);
        }
    }
}

}  // namespace cs
