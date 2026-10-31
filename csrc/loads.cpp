// Cognitive load of a move (Solver::cog_loads): what a person has to look at or hold in mind to verify it.
#include <algorithm>
#include "portable.hpp"
#include <cmath>
#include "solver.hpp"

namespace cs {

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

}  // namespace cs
