// Regions to find (chaos construction, format 6.3) in the human solver: the label state's upkeep and the region
// techniques (docs/research/chaos_techniques.md). Labels are names of convenience: label k first appears before
// label k + 1 in reading order (the exhaustive search uses the same rule), so a step "r4c5 is in region 3" reads as
// "r4c5 is in the region of the third region's first cell".
#include <algorithm>
#include "portable.hpp"
#include "solver.hpp"
#include "solver_util.hpp"

namespace cs {

namespace {
inline void add_lel(MoveBuf& b, Move& m, int c, int k) {
    b.lels.push_back((uint32_t)(c * 32 + k));
    ++m.lel_n;
}
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
        for (const auto& e : p.region_border) {
            if (lab[e.first]) keep(e.second, ~bit(lab[e.first]));
            if (lab[e.second]) keep(e.first, ~bit(lab[e.second]));
        }
        for (const auto& s : p.same_region) {
            uint32_t m = p.full;
            for (int c : s) m &= lab[c] ? bit(lab[c]) : lcand[c];
            if (m)
                for (int c : s) keep(c, m);
        }
    }
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
                m.lel_off = (int)out.lels.size();
                for (int c : maybe) add_lel(out, m, c, k);
                set_pattern(out, m, known);
                m.code = 7101;
            } else if ((int)(known.size() + maybe.size()) == D && !maybe.empty()) {  // the only cells left take it
                Move& m = new_move(out, REGION_CAP, 1.0, (int)maybe.size());
                m.lel_off = (int)out.lels.size();
                for (int c : maybe)
                    for (uint32_t o = lcand[c] & ~kb; o; o &= o - 1) add_lel(out, m, c, lowdigit(o));
                std::vector<int> pat = known;
                pat.insert(pat.end(), maybe.begin(), maybe.end());
                set_pattern(out, m, pat);
                m.code = 7102;
                if (!m.lel_n) out.moves.pop_back();
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
            m.lel_off = (int)out.lels.size();
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
            m.lpc = exit;
            m.lpv = k;
            for (uint32_t o = lcand[exit] & ~kb; o; o &= o - 1) add_lel(out, m, exit, lowdigit(o));
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
                m.lpc = where;
                m.lpv = k;
                for (uint32_t o = lcand[where] & ~kb; o; o &= o - 1) add_lel(out, m, where, lowdigit(o));
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
            if (!m.lel_n) {
                out.moves.pop_back();
                continue;
            }
            set_pattern(out, m, cells);
            m.code = 7161;
        }
    }
}

}  // namespace cs
