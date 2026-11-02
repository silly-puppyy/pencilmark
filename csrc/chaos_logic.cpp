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

}  // namespace cs
