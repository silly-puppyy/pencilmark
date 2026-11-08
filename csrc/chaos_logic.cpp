// Regions to find (chaos construction, format 6.3) in the human solver: the label state's upkeep and the region
// techniques (docs/research/chaos_techniques.md). Labels are names of convenience: label k first appears before
// label k + 1 in reading order (the exhaustive search uses the same rule), so a step "r4c5 is in region 3" reads as
// "r4c5 is in the region of the third region's first cell".
#include <algorithm>
#include <functional>
#include <map>
#include <set>
#include "expr.hpp"
#include "portable.hpp"
#include "solver.hpp"
#include "solver_util.hpp"

namespace cs {

namespace {
inline void add_lel(MoveBuf& b, Move& m, int c, int k) { add_aeff(b, m, AE_LABEL_ELIM, c, k); }
inline void place_label(MoveBuf& b, Move& m, int c, int k) { add_aeff(b, m, AE_LABEL_PLACE, c, k); }
}  // namespace

// silent upkeep, like a placed digit erasing its peers: canonical names, given borders, same-region sets, and a label
// fixed once one candidate is left
void Solver::label_normalize() {
    if (!has_regions()) return;
    auto fix = [&](int c) {
        if (!lab[c] && lcand[c] && !(lcand[c] & (lcand[c] - 1))) lab[c] = (uint8_t)lowdigit(lcand[c]);
    };
    for (bool again = true; again;) {
        again = false;
        auto keep = [&](int c, uint32_t k) {
            if (lab[c]) return;
            const uint32_t n = lcand[c] & k;
            if (n && n != lcand[c]) lcand[c] = n, fix(c), again = true;
        };
        for (const auto& A : p.chaos) {
            int maxlab = 0;
            for (int c : A) {
                keep(c, maxlab + 1 >= 32 ? p.full : ((1u << (maxlab + 1)) - 1) & p.full);
                const uint32_t m = lab[c] ? bit(lab[c]) : lcand[c];
                if (m) maxlab = std::max(maxlab, 32 - __builtin_clz(m));
            }
        }
        // the relation layer (rgc): a group shares its label candidates; a cell known to differ from a labelled cell
        // loses that label; two labelled cells are related by their labels
        std::map<int, std::vector<int>> groups;
        for (int c = 0; c < (int)rgc.size() && c < p.N; ++c)
            if (rgc[c]) groups[rgc[c] - 1].push_back(c);
        for (const auto& kv : groups) {
            uint32_t m = p.full;
            for (int c : kv.second) m &= lab[c] ? bit(lab[c]) : lcand[c];
            if (m)
                for (int c : kv.second) keep(c, m);
        }
        for (size_t i = (size_t)p.N; i + 1 < rgc.size(); i += 2) {
            const int a = rgc[i] - 1, b = rgc[i + 1] - 1;
            for (const auto& [x, y] : {std::pair<int, int>{a, b}, {b, a}}) {
                uint32_t known = 0;  // labels fixed somewhere in x's group
                auto it = groups.find(x);
                if (it != groups.end()) {
                    for (int c : it->second)
                        if (lab[c]) known |= bit(lab[c]);
                } else if (lab[x]) {
                    known = bit(lab[x]);
                }
                if (!known) continue;
                auto jt = groups.find(y);
                if (jt != groups.end())
                    for (int c : jt->second) keep(c, ~known);
                else
                    keep(y, ~known);
            }
        }
    }
    for (const auto& A : p.chaos)  // labelled cells side by side: one region or two
        for (int c : A)
            for (int nb : p.chaos_nbr[c])
                if (nb > c && lab[c] && lab[nb]) {
                    if (lab[c] == lab[nb] && rg_anchor(c) != rg_anchor(nb)) rg_join(c, nb);
                    else if (lab[c] != lab[nb] && !rg_differ(c, nb)) rg_neq(c, nb);
                }
}

// ------------------------------------------------------------------------------------------- the region relation layer
void Solver::rg_normalize() {
    if (rgc.empty()) return;
    const int N = p.N;
    std::map<int, int> lo;  // group -> its smallest cell
    for (int c = 0; c < N; ++c)
        if (rgc[c]) lo[rgc[c]] = lo.count(rgc[c]) ? std::min(lo[rgc[c]], c) : c;
    std::vector<int> anc(N);
    for (int c = 0; c < N; ++c) anc[c] = rgc[c] ? lo[rgc[c]] : c;
    std::set<std::pair<int, int>> prs;
    for (size_t i = (size_t)N; i + 1 < rgc.size(); i += 2) {
        int a = rgc[i] - 1, b = rgc[i + 1] - 1;
        a = a >= 0 && a < N ? anc[a] : a, b = b >= 0 && b < N ? anc[b] : b;
        if (a != b) prs.insert({std::min(a, b), std::max(a, b)});
    }
    std::vector<int> cnt(N, 0);
    for (int c = 0; c < N; ++c) cnt[anc[c]]++;
    for (int c = 0; c < N; ++c) rgc[c] = cnt[anc[c]] > 1 ? anc[c] + 1 : 0;
    rgc.resize(N);
    for (const auto& pr : prs) rgc.push_back(pr.first + 1), rgc.push_back(pr.second + 1);
}

void Solver::rg_join(int a, int b) {
    if (rgc.empty() || a == b) return;
    const int ka = rg_anchor(a), kb = rg_anchor(b), nk = std::min(ka, kb) + 1;
    for (int x = 0; x < p.N; ++x)
        if (rg_anchor(x) == ka || rg_anchor(x) == kb) rgc[x] = nk;
    for (size_t i = (size_t)p.N; i < rgc.size(); ++i)  // differences naming either group now name the joined one
        if (rgc[i] - 1 == ka || rgc[i] - 1 == kb) rgc[i] = nk;
    rg_normalize();
}

void Solver::rg_neq(int a, int b) {
    if (rgc.empty() || a == b) return;
    rgc.push_back(rg_anchor(a) + 1);
    rgc.push_back(rg_anchor(b) + 1);
    rg_normalize();
}

bool Solver::rg_differ(int a, int b) const {
    const int ka = rg_anchor(a), kb = rg_anchor(b);
    for (size_t i = (size_t)p.N; i + 1 < rgc.size(); i += 2) {
        const int x = rgc[i] - 1, y = rgc[i + 1] - 1;
        if ((x == ka && y == kb) || (x == kb && y == ka)) return true;
    }
    return false;
}

// "that would be more than nine cells": a region whose D cells are known is sealed (no other cell takes its label);
// the D cells that may still take a label are that region
void Solver::region_cap(MoveBuf& out) {
    if (!has_regions() || disabled[REGION_CAP]) return;
    const int D = p.D;
    for (const auto& A : p.chaos) {
        for (int k = 1; k <= D; ++k) {
            const uint32_t kb = bit(k);
            std::vector<int> known, maybe;
            for (int c : A) {
                if (lab[c] == k) known.push_back(c);
                else if (!lab[c] && (lcand[c] & kb)) maybe.push_back(c);
            }
            if ((int)known.size() == D && !maybe.empty()) {  // sealed: the rest lose the label
                Move& m = new_move(out, REGION_CAP, 1.0, (int)maybe.size());
                for (int c : maybe) add_lel(out, m, c, k);
                set_pattern(out, m, known);
                m.code = 7101;
            } else if ((int)(known.size() + maybe.size()) == D && !maybe.empty()) {  // the only cells left take it
                Move& m = new_move(out, REGION_CAP, 1.0, (int)maybe.size());
                for (int c : maybe)
                    for (uint32_t o = lcand[c] & ~kb; o; o &= o - 1) add_lel(out, m, c, lowdigit(o));
                std::vector<int> pat = known;
                pat.insert(pat.end(), maybe.begin(), maybe.end());
                set_pattern(out, m, pat);
                m.code = 7102;
                if (!m.aeff_n) out.moves.pop_back();
            }
        }
    }
}

// "you'd repeat a digit in a region": a placed digit leaves the other cells known to share its region, and a cell
// holding the same digit cannot join that region
void Solver::region_excl(MoveBuf& out) {
    if (!has_regions() || disabled[REGION_EXCL]) return;
    for (const auto& A : p.chaos) {
        for (int a : A) {
            if (!lab[a] || !vals[a]) continue;
            const int k = lab[a], d = vals[a];
            std::vector<int> digit_off, label_off;
            for (int b : A) {
                if (b == a) continue;
                if (lab[b] == k && !vals[b] && (cand[b] & bit(d))) digit_off.push_back(b);
                if (vals[b] == d && !lab[b] && (lcand[b] & bit(k))) label_off.push_back(b);
            }
            if (digit_off.empty() && label_off.empty()) continue;
            Move& m = new_move(out, REGION_EXCL, 1.0, (int)(digit_off.size() + label_off.size()));
            for (int b : digit_off) add_elim(out, m, b, d);
            for (int b : label_off) add_lel(out, m, b, k);
            set_pattern(out, m, {a});
            m.code = 7110 + (label_off.empty() ? 1 : digit_off.empty() ? 2 : 3);
        }
    }
}

// "it can't get there": for each region, the cells that may still take its label form components; a region with known
// cells lies in their component and within (D - known) steps of them, a region with none needs a component of D cells
void Solver::region_reach(MoveBuf& out) {
    if (!has_regions() || disabled[REGION_REACH]) return;
    const int D = p.D;
    std::vector<int> dist(p.N, -1), stack;
    for (const auto& A : p.chaos) {
        for (int k = 1; k <= D; ++k) {
            const uint32_t kb = bit(k);
            auto may = [&](int c) { return lab[c] == k || (!lab[c] && (lcand[c] & kb)); };
            std::vector<int> known;
            for (int c : A) {
                dist[c] = -1;
                if (lab[c] == k) known.push_back(c);
            }
            std::vector<int> lose;
            if (!known.empty()) {  // breadth-first distance from the known cells through cells that may take k
                std::vector<int> q = known;
                for (int c : known) dist[c] = 0;
                for (size_t h = 0; h < q.size(); ++h)
                    for (int nb : p.chaos_nbr[q[h]])
                        if (dist[nb] < 0 && may(nb)) dist[nb] = dist[q[h]] + 1, q.push_back(nb);
                const int budget = D - (int)known.size();
                for (int c : A)
                    if (!lab[c] && (lcand[c] & kb) && (dist[c] < 0 || dist[c] > budget)) lose.push_back(c);
            } else {  // no known cell: a component of fewer than D cells cannot hold the region
                std::vector<int> comp(p.N, -1);
                for (int s0 : A) {
                    if (comp[s0] >= 0 || !may(s0)) continue;
                    std::vector<int> cells{s0};
                    comp[s0] = s0;
                    for (size_t h = 0; h < cells.size(); ++h)
                        for (int nb : p.chaos_nbr[cells[h]])
                            if (comp[nb] < 0 && may(nb)) comp[nb] = s0, cells.push_back(nb);
                    if ((int)cells.size() < D) lose.insert(lose.end(), cells.begin(), cells.end());
                }
            }
            if (lose.empty()) continue;
            Move& m = new_move(out, REGION_REACH, 1.0, (int)lose.size());
            for (int c : lose) add_lel(out, m, c, k);
            set_pattern(out, m, known);
            m.code = known.empty() ? 7122 : 7121;
        }
    }
}

// "it would have to be its own colour in a one cell region": a cell shares its region with at least one neighbour, so
// it keeps only the labels some neighbour can take
void Solver::dead_end(MoveBuf& out) {
    if (!has_regions() || disabled[DEAD_END] || p.D < 2) return;
    for (const auto& A : p.chaos)
        for (int c : A) {
            if (lab[c]) continue;
            uint32_t nbm = 0;
            for (int nb : p.chaos_nbr[c]) nbm |= lab[nb] ? bit(lab[nb]) : lcand[nb];
            const uint32_t off = lcand[c] & ~nbm;
            if (!off) continue;
            Move& m = new_move(out, DEAD_END, 1.0, popc(off));
            for (uint32_t o = off; o; o &= o - 1) add_lel(out, m, c, lowdigit(o));
            set_pattern(out, m, p.chaos_nbr[c]);
            m.code = 7131;
        }
}

// "yellow has to get out": a region with fewer than D known cells whose known cells have exactly one neighbouring cell
// that may still join it takes that cell
void Solver::region_exit(MoveBuf& out) {
    if (!has_regions() || disabled[REGION_EXIT]) return;
    const int D = p.D;
    for (const auto& A : p.chaos)
        for (int k = 1; k <= D; ++k) {
            const uint32_t kb = bit(k);
            std::vector<int> known;
            for (int c : A)
                if (lab[c] == k) known.push_back(c);
            if (known.empty() || (int)known.size() >= D) continue;
            // the known cells may be in pieces; the region's frontier is every free neighbour of any known cell
            int exit = -1, n_exit = 0;
            std::vector<char> seen(p.N, 0);
            for (int c : known)
                for (int nb : p.chaos_nbr[c])
                    if (!seen[nb] && !lab[nb] && (lcand[nb] & kb)) seen[nb] = 1, exit = nb, ++n_exit;
            if (n_exit != 1) continue;
            Move& m = new_move(out, REGION_EXIT, 1.0, 1);
            for (uint32_t o = lcand[exit] & ~kb; o; o &= o - 1) add_lel(out, m, exit, lowdigit(o));
            place_label(out, m, exit, k);
            set_pattern(out, m, known);
            m.code = 7141;
        }
}

// "orange has to have a five in it": a region holds every digit; when its missing digit d fits only one cell the region
// can still reach (within its remaining cells), that cell is in the region and holds d
void Solver::region_digit(MoveBuf& out) {
    if (!has_regions() || disabled[REGION_DIGIT]) return;
    const int D = p.D;
    std::vector<int> dist(p.N, -1);
    for (const auto& A : p.chaos)
        for (int k = 1; k <= D; ++k) {
            const uint32_t kb = bit(k);
            auto may = [&](int c) { return lab[c] == k || (!lab[c] && (lcand[c] & kb)); };
            std::vector<int> known;
            uint32_t have = 0;
            for (int c : A) {
                dist[c] = -1;
                if (lab[c] == k) known.push_back(c), have |= vals[c] ? bit(vals[c]) : 0;
            }
            if (known.empty() || (int)known.size() >= D) continue;
            std::vector<int> q = known;
            for (int c : known) dist[c] = 0;
            for (size_t h = 0; h < q.size(); ++h)
                for (int nb : p.chaos_nbr[q[h]])
                    if (dist[nb] < 0 && may(nb)) dist[nb] = dist[q[h]] + 1, q.push_back(nb);
            const int budget = D - (int)known.size();
            for (int d = 1; d <= D; ++d) {
                if (have & bit(d)) continue;
                int where = -1, n = 0;
                for (int c : A) {
                    const bool reach = lab[c] == k || (dist[c] > 0 && dist[c] <= budget);
                    if (reach && (vals[c] == d || (!vals[c] && (cand[c] & bit(d))))) where = c, ++n;
                }
                if (n != 1 || lab[where] == k) continue;
                Move& m = new_move(out, REGION_DIGIT, 1.0, 1);
                for (uint32_t o = lcand[where] & ~kb; o; o &= o - 1) add_lel(out, m, where, lowdigit(o));
                place_label(out, m, where, k);
                if (!vals[where]) m.pc = where, m.pv = d;
                set_pattern(out, m, known);
                m.code = 7151;
            }
        }
}

// pocket counting: the undecided cells form pockets (connected through undecided cells); a pocket of fewer than D cells
// cannot hold a region of its own, so its cells belong to the unfinished regions around it; with one such region, the
// whole pocket is that region's
void Solver::pocket(MoveBuf& out) {
    if (!has_regions() || disabled[POCKET]) return;
    const int D = p.D;
    std::vector<int> comp(p.N, -1), count(D + 1, 0);
    for (const auto& A : p.chaos) {
        std::fill(count.begin(), count.end(), 0);
        for (int c : A)
            if (lab[c]) ++count[lab[c]];
        for (int c : A) comp[c] = -1;
        for (int s0 : A) {
            if (lab[s0] || comp[s0] >= 0) continue;
            std::vector<int> cells{s0};
            comp[s0] = s0;
            uint32_t around = 0;  // unfinished regions touching the pocket
            for (size_t h = 0; h < cells.size(); ++h)
                for (int nb : p.chaos_nbr[cells[h]]) {
                    if (lab[nb]) {
                        if (count[lab[nb]] < D) around |= bit(lab[nb]);
                    } else if (comp[nb] < 0) {
                        comp[nb] = s0, cells.push_back(nb);
                    }
                }
            if ((int)cells.size() >= D || popc(around) != 1) continue;
            const int k = lowdigit(around);
            Move& m = new_move(out, POCKET, 1.0, (int)cells.size());
            for (int c : cells)
                for (uint32_t o = lcand[c] & ~bit(k); o; o &= o - 1) add_lel(out, m, c, lowdigit(o));
            if (!m.aeff_n) {
                out.moves.pop_back();
                continue;
            }
            set_pattern(out, m, cells);
            m.code = 7161;
        }
    }
}

// a rule that reads the regions (a custom rule calling region(): sight blocked by other regions, counting the cells of
// its own region, borders crossed, ...) read on its own: the combinations of the digits and labels it actually reads
// that satisfy it, found lazily (expr_holds_lazy asks for the next unknown value it needs, so a sight line stops at its
// first border and cells used only as cells never branch on their digit), within a budget; a candidate digit or label
// that no combination uses is removed. Sound: a satisfying combination that never read a value supports all its
// candidates, extra (non-canonical) label combinations only add support, and nothing is removed when the budget runs out.
void Solver::region_rule(MoveBuf& out) {
    if (!has_regions() || disabled[REGION_RULE]) return;
    constexpr long BUDGET = 20000;  // satisfiability checks per rule and step
    for (const NConstraint& k : p.nary) {
        if (k.type != NT_EXPR || !k.expr || !k.expr->layered) continue;
        const int nv = k.nv();
        if (nv > 64) continue;
        // a rule comparing regions only (==, !=) reads which cells share a region: regions are named freely as the
        // search meets them (partitions), so it learns "same region" / "different regions" while every label is open
        const bool rel = expr_region_relational(k.expr->root);
        int dg[64], lb[64];
        uint32_t dsup[64] = {0}, lsup[64] = {0};
        bool dall[64] = {false}, lall[64] = {false};
        int cellv[64];
        for (int i = 0; i < nv; ++i) {
            const int c = cellv[i] = k.vars[i];
            dg[i] = vals[c] ? vals[c] : -1;
            lb[i] = p.chaos_of[c] < 0 ? 0 : (!rel && lab[c]) ? lab[c] : -1;
        }
        // partitions: symbol per read variable (lb), each symbol's known label (0: none)
        std::vector<int> sym_label(1, 0);
        std::vector<uint64_t> same(nv, 0), diff(nv, 0), unread(nv, 0);  // per pair (i, j): bits of j
        long budget = BUDGET;
        bool complete = true;
        std::function<void()> go = [&]() {
            if (!complete) return;
            if (--budget < 0) {
                complete = false;
                return;
            }
            int need = -1;
            bool need_label = false;
            try {
                if (!expr_holds_lazy(*k.expr, dg, lb)) return;
            } catch (const ExprNeed& ex) {
                need = ex.var, need_label = ex.label;
            }
            if (need < 0) {  // satisfied: supports
                for (int i = 0; i < nv; ++i) {
                    if (dg[i] > 0) dsup[i] |= bit(dg[i]);
                    else dall[i] = true;
                    if (!rel) {
                        if (lb[i] > 0) lsup[i] |= bit(lb[i]);
                        else if (lb[i] < 0) lall[i] = true;
                    }
                }
                if (rel)
                    for (int i = 0; i < nv; ++i)
                        for (int j = i + 1; j < nv; ++j) {
                            if (lb[i] <= 0 || lb[j] <= 0) unread[i] |= 1ull << j;
                            else if (lb[i] == lb[j]) same[i] |= 1ull << j;
                            else diff[i] |= 1ull << j;
                        }
                return;
            }
            const int c = cellv[need];
            if (!need_label) {
                for (uint32_t o = cand[c]; o && complete; o &= o - 1) {
                    dg[need] = lowdigit(o);
                    go();
                }
                dg[need] = -1;
                return;
            }
            if (!rel) {
                for (uint32_t o = lcand[c]; o && complete; o &= o - 1) {
                    lb[need] = lowdigit(o);
                    go();
                }
                lb[need] = -1;
                return;
            }
            // which symbols c may take: a cell of its group already named forces that symbol; otherwise any symbol
            // no recorded difference or known label rules out, or a new one
            const int nsym = (int)sym_label.size();
            std::vector<char> ok(nsym + 1, 1);
            ok[0] = 0;
            int forced = 0;
            for (int j = 0; j < nv; ++j) {
                if (lb[j] <= 0) continue;
                if (rg_anchor(cellv[j]) == rg_anchor(c)) forced = lb[j];
                if (rg_differ(cellv[j], c)) ok[lb[j]] = 0;
            }
            for (int s = 1; s < nsym; ++s) {
                const int L = sym_label[s];
                if (L && (lab[c] ? lab[c] != L : !(lcand[c] & bit(L)))) ok[s] = 0;
                if (lab[c] && L == lab[c] && !forced) forced = s;  // its label is that symbol's
            }
            std::vector<int> opts;
            if (forced) {
                if (ok[forced]) opts.push_back(forced);
            } else {
                for (int s = 1; s < nsym; ++s)
                    if (ok[s]) opts.push_back(s);
                opts.push_back(nsym);  // a region not met yet
            }
            for (int s : opts) {
                const bool fresh = s == nsym;
                if (fresh) sym_label.push_back(lab[c] ? lab[c] : 0);
                const int keep_label = sym_label[s];
                if (!fresh && !sym_label[s] && lab[c]) sym_label[s] = lab[c];
                lb[need] = s;
                go();
                lb[need] = -1;
                sym_label[s] = keep_label;
                if (fresh) sym_label.pop_back();
                if (!complete) break;
            }
        };
        go();
        if (!complete) continue;
        std::vector<std::pair<int, int>> d_off, l_off, joins, neqs;
        for (int i = 0; i < nv; ++i) {
            const int c = cellv[i];
            if (!vals[c] && !dall[i])
                for (uint32_t o = cand[c] & ~dsup[i]; o; o &= o - 1) d_off.push_back({c, lowdigit(o)});
            if (!rel && p.chaos_of[c] >= 0 && !lab[c] && !lall[i])
                for (uint32_t o = lcand[c] & ~lsup[i]; o; o &= o - 1) l_off.push_back({c, lowdigit(o)});
        }
        if (rel)
            for (int i = 0; i < nv; ++i)
                for (int j = i + 1; j < nv; ++j) {
                    const int a = cellv[i], b = cellv[j];
                    const uint64_t bj = 1ull << j;
                    if ((unread[i] & bj) || p.chaos_of[a] < 0 || p.chaos_of[a] != p.chaos_of[b]) continue;
                    if ((same[i] & bj) && !(diff[i] & bj) && rg_anchor(a) != rg_anchor(b)) joins.push_back({a, b});
                    if ((diff[i] & bj) && !(same[i] & bj) && !rg_differ(a, b)) neqs.push_back({a, b});
                }
        const int n = (int)(d_off.size() + l_off.size() + joins.size() + neqs.size());
        if (!n) continue;
        Move& m = new_move(out, REGION_RULE, 1.0, n);
        for (auto [c, d] : d_off) add_elim(out, m, c, d);
        for (auto [c, l] : l_off) add_lel(out, m, c, l);
        for (auto [a, b] : joins) add_aeff(out, m, AE_REG_JOIN, a, b);
        for (auto [a, b] : neqs) add_aeff(out, m, AE_REG_NEQ, a, b);
        set_pattern(out, m, k.vars);
        m.nk = NM_NARY;  // the rule (explanations name it)
        m.na = k.index;
        m.nb = k.group;
        m.code = 7190;
    }
}

// the relation layer's groups (cells known to share a region, named or not), as a solver reasons with drawn borders:
// two neighbouring groups with more than D cells between them are different regions (code 7201); a group of D cells is
// sealed from its neighbours (7202); a group short of D cells with one neighbour not known to differ takes it (7203);
// two cells holding the same digit, side by side or one in a group, lie in different regions (7204)
void Solver::region_group(MoveBuf& out) {
    if (!has_regions() || disabled[REGION_GROUP]) return;
    const int D = p.D;
    std::map<int, std::vector<int>> grp;  // anchor -> members, every chaos cell (a lone cell is its own group)
    for (const auto& A : p.chaos)
        for (int c : A) grp[rg_anchor(c)].push_back(c);
    auto emit = [&](int code, const std::vector<int>& pat, const std::vector<std::pair<int, int>>& neq,
                    const std::vector<std::pair<int, int>>& join) {
        if (neq.empty() && join.empty()) return;
        Move& m = new_move(out, REGION_GROUP, 1.0, (int)(neq.size() + join.size()));
        for (auto [a, b] : neq) add_aeff(out, m, AE_REG_NEQ, a, b);
        for (auto [a, b] : join) add_aeff(out, m, AE_REG_JOIN, a, b);
        set_pattern(out, m, pat);
        m.code = code;
    };
    for (const auto& [a, ms] : grp) {
        std::set<int> nb;  // outside neighbours
        for (int c : ms)
            for (int x : p.chaos_nbr[c])
                if (rg_anchor(x) != a) nb.insert(x);
        const int size = (int)ms.size();
        if (size >= D) {  // sealed
            std::vector<std::pair<int, int>> neq;
            for (int x : nb)
                if (!rg_differ(a, x)) neq.push_back({a, x});
            emit(7202, ms, neq, {});
            continue;
        }
        std::vector<std::pair<int, int>> neq;  // too big together
        std::set<int> seen;
        for (int x : nb) {
            const int b = rg_anchor(x);
            if (!seen.insert(b).second || rg_differ(a, b)) continue;
            if (size + (int)grp[b].size() > D) neq.push_back({a, b});
        }
        emit(7201, ms, neq, {});
        {  // one way out (a lone cell too: with every label open only a join can say it)
            std::vector<int> open;
            std::set<int> anchors;
            for (int x : nb)
                if (!rg_differ(a, x) && anchors.insert(rg_anchor(x)).second) open.push_back(x);
            if (open.size() == 1 && neq.empty()) emit(7203, ms, {}, {{a, open[0]}});
        }
    }
    for (const auto& [a, ms] : grp) {  // a group is part of one region: its digits do not repeat (7205); a whole
        if (ms.size() < 2) continue;    // region is a house: a digit with one place left in it goes there (7206)
        uint32_t placed = 0;
        for (int c : ms)
            if (vals[c]) placed |= bit(vals[c]);
        std::vector<std::pair<int, int>> off;
        for (int c : ms)
            if (!vals[c] && (cand[c] & placed))
                for (uint32_t o = cand[c] & placed; o; o &= o - 1) off.push_back({c, lowdigit(o)});
        if (!off.empty()) {
            Move& m = new_move(out, REGION_GROUP, 1.0, (int)off.size());
            for (auto [c, d] : off) add_elim(out, m, c, d);
            set_pattern(out, m, ms);
            m.code = 7205;
            continue;
        }
        if ((int)ms.size() != D) continue;
        for (int d = 1; d <= D; ++d) {
            if (placed & bit(d)) continue;
            int at = -1, n = 0;
            for (int c : ms)
                if (!vals[c] && (cand[c] & bit(d))) at = c, ++n;
            if (n != 1) continue;
            Move& m = new_move(out, REGION_GROUP, 1.0, 1);
            m.pc = at, m.pv = d;
            set_pattern(out, m, ms);
            m.code = 7206;
        }
    }
    std::vector<std::pair<int, int>> neq;  // equal digits
    for (const auto& A : p.chaos)
        for (size_t i = 0; i < A.size(); ++i)
            for (size_t j = i + 1; j < A.size(); ++j) {
                const int x = A[i], y = A[j];
                if (!vals[x] || vals[x] != vals[y] || rg_differ(x, y) || rg_anchor(x) == rg_anchor(y)) continue;
                const bool near = std::find(p.chaos_nbr[x].begin(), p.chaos_nbr[x].end(), y) != p.chaos_nbr[x].end();
                if (near || grp[rg_anchor(x)].size() > 1 || grp[rg_anchor(y)].size() > 1) neq.push_back({x, y});
            }
    for (auto [x, y] : neq) emit(7204, {x, y}, {{x, y}}, {});
}

}  // namespace cs
