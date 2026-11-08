// Shading (yin-yang, format 6.19) in the human solver: the colour state's techniques (docs/research/
// cell_layer_techniques.md, the CtC-mined families). Colours: 0 unknown, 1 shaded, 2 unshaded; a step sets one or more
// cells' colours (AE_SHADE, arg = the colour). Each colour is orthogonally connected and no 2x2 block is one colour.
#include <algorithm>
#include <functional>
#include <vector>
#include "expr.hpp"
#include "portable.hpp"
#include "solver.hpp"
#include "solver_util.hpp"

namespace cs {

namespace {
inline void set_colour(MoveBuf& b, Move& m, int c, int col) { add_aeff(b, m, AE_SHADE, c, col); }
inline int other(int col) { return 3 - col; }
}  // namespace

// local 2x2 logic (ShadeLocal): "three cells of one colour in a 2x2 make the fourth the other" (7301); "no
// checkerboard": a 2x2 with one colour on a diagonal and the other colour on the other diagonal disconnects a colour,
// so with three cells known in that pattern the fourth takes the colour that breaks it (7302)
void Solver::shade_local(MoveBuf& out) {
    if (!has_shading() || disabled[SHADE_LOCAL]) return;
    for (const auto& w : p.windows4) {
        int n[3] = {0, 0, 0}, free = -1, nfree = 0;
        for (int c : w) {
            ++n[shade[c]];
            if (!shade[c]) free = c, ++nfree;
        }
        if (nfree != 1) continue;
        int col = 0, code = 0;
        if (n[1] == 3) col = 2, code = 7301;
        else if (n[2] == 3) col = 1, code = 7301;
        else {  // two of one colour and one of the other: a checkerboard only if the pair is diagonal
            const int fi = (int)(std::find(w.begin(), w.end(), free) - w.begin());
            const int diag = 3 - fi;                    // the cell on the free cell's diagonal
            const int side1 = fi ^ 1, side2 = fi ^ 2;   // the two cells beside the free one
            if (shade[w[side1]] == shade[w[side2]] && shade[w[diag]] != shade[w[side1]])
                col = shade[w[side1]], code = 7302;    // copying its diagonal would make the checkerboard
        }
        if (!col) continue;
        Move& m = new_move(out, SHADE_LOCAL, 1.0, 1);
        set_colour(out, m, free, col);
        std::vector<int> pat;
        for (int c : w)
            if (c != free) pat.push_back(c);
        set_pattern(out, m, pat);
        m.code = code;
    }
}

// connectivity (ShadeConnect): for each colour, its known cells must join through cells that may take it (known of
// that colour or unknown). "Single exit" (7311): a known group of the colour that is not all of the colour and has
// exactly one unknown neighbour takes it. "Cut cell" (7312): an unknown cell without which two known cells of the
// colour could no longer join takes that colour. "Perimeter runs" (7321): with both colours connected, the board's
// border holds at most one run of each colour, so a border cell whose other colour would make a third colour change is
// that colour.
void Solver::shade_connect(MoveBuf& out) {
    if (!has_shading() || disabled[SHADE_CONNECT]) return;
    const int N = p.N;
    std::vector<int> comp(N, -1);
    for (int col = 1; col <= 2; ++col) {
        auto may = [&](int c) { return shade[c] == col || shade[c] == 0; };
        std::vector<int> known;
        for (int c = 0; c < N; ++c)
            if (shade[c] == col) known.push_back(c);
        if (known.size() < 2) continue;
        // known groups of the colour (through known cells only)
        std::fill(comp.begin(), comp.end(), -1);
        std::vector<std::vector<int>> groups;
        for (int s0 : known) {
            if (comp[s0] >= 0) continue;
            const int g = (int)groups.size();
            groups.push_back({s0});
            comp[s0] = g;
            for (size_t h = 0; h < groups[g].size(); ++h)
                for (int nb : p.grid_nbr[groups[g][h]])
                    if (comp[nb] < 0 && shade[nb] == col) comp[nb] = g, groups[g].push_back(nb);
        }
        bool more_cells = false;  // could the colour still have cells beyond the known groups
        for (int c = 0; c < N && !more_cells; ++c) more_cells = !shade[c];
        if (groups.size() > 1) {
            for (const auto& gr : groups) {  // single exit
                int exit = -1, n_exit = 0;
                std::vector<char> seen(N, 0);
                for (int c : gr)
                    for (int nb : p.grid_nbr[c])
                        if (!shade[nb] && !seen[nb]) seen[nb] = 1, exit = nb, ++n_exit;
                if (n_exit != 1) continue;
                Move& m = new_move(out, SHADE_CONNECT, 1.0, 1);
                set_colour(out, m, exit, col);
                set_pattern(out, m, gr);
                m.code = 7311;
            }
            // cut cells: an unknown cell whose removal leaves the known cells of the colour in more than one component
            // of the may-graph
            auto joined_without = [&](int skip) {
                std::vector<char> vis(N, 0);
                std::vector<int> st{known[0]};
                vis[known[0]] = 1;
                size_t reached = 0;
                while (!st.empty()) {
                    const int c = st.back();
                    st.pop_back();
                    if (shade[c] == col) ++reached;
                    for (int nb : p.grid_nbr[c])
                        if (!vis[nb] && nb != skip && may(nb)) vis[nb] = 1, st.push_back(nb);
                }
                return reached == known.size();
            };
            for (int c = 0; c < N; ++c) {
                if (shade[c]) continue;
                bool touches = false;  // only cells next to the may-graph's paths can be cuts; cheap filter
                for (int nb : p.grid_nbr[c]) touches |= may(nb);
                if (!touches || joined_without(c)) continue;
                Move& m = new_move(out, SHADE_CONNECT, 1.0, 1);
                set_colour(out, m, c, col);
                set_pattern(out, m, known);
                m.code = 7312;
            }
        }
        (void)more_cells;
    }
    // perimeter runs: the border cycle of a full rectangular board
    if (p.border_cycle.empty()) return;
    const auto& B = p.border_cycle;
    const int L = (int)B.size();
    auto changes = [&](const std::vector<uint8_t>& colour) {  // fewest colour changes possible around the cycle
        int first = -1;
        for (int i = 0; i < L; ++i)
            if (colour[B[i]]) {
                first = i;
                break;
            }
        if (first < 0) return 0;
        int ch = 0, last = colour[B[first]];
        for (int k = 1; k <= L; ++k) {
            const int c = colour[B[(first + k) % L]];
            if (c && c != last) ++ch, last = c;
        }
        return ch;
    };
    std::vector<uint8_t> trial(shade.begin(), shade.end());
    for (int i = 0; i < L; ++i) {
        const int c = B[i];
        if (shade[c]) continue;
        for (int col = 1; col <= 2; ++col) {
            trial[c] = (uint8_t)col;
            const int ch = changes(trial);
            trial[c] = 0;
            if (ch <= 2) continue;
            Move& m = new_move(out, SHADE_CONNECT, 1.0, 1);
            set_colour(out, m, c, other(col));
            std::vector<int> pat;
            for (int b : B)
                if (shade[b]) pat.push_back(b);
            set_pattern(out, m, pat);
            m.code = 7321;
            break;
        }
    }
}

// ShadeRule: a custom rule reading shaded() (the puzzle's coupling of shading and digits: "shaded cells are odd",
// "a cage's shaded digits sum to ...") read on its own, like RegionRule: the combinations of the digits and colours it
// actually reads that satisfy it, found lazily within a budget; a digit no combination uses is removed, a colour that
// every combination gives is set (7331). Nothing is removed when the budget runs out.
void Solver::shade_rule(MoveBuf& out) {
    if (!has_shading() || disabled[SHADE_RULE]) return;
    constexpr long BUDGET = 20000;
    for (const NConstraint& k : p.nary) {
        if (k.type != NT_EXPR || !k.expr || !k.expr->layered) continue;
        if (!expr_reads_shading(k.expr->root) || expr_reads_regions(k.expr->root)) continue;  // regions: RegionRule
        const int nv = k.nv();
        if (nv > 64) continue;
        int dg[64], sh[64], cellv[64];
        uint32_t dsup[64] = {0};
        uint8_t ssup[64] = {0};
        bool dall[64] = {false}, sall[64] = {false};
        for (int i = 0; i < nv; ++i) {
            const int c = cellv[i] = k.vars[i];
            dg[i] = vals[c] ? vals[c] : -1;
            sh[i] = shade[c] ? shade[c] : -1;
        }
        long budget = BUDGET;
        bool complete = true;
        std::function<void()> go = [&]() {
            if (!complete) return;
            if (--budget < 0) {
                complete = false;
                return;
            }
            int need = -1;
            bool need_shade = false;
            try {
                if (!expr_holds_lazy(*k.expr, dg, nullptr, sh)) return;
            } catch (const ExprNeed& ex) {
                need = ex.var, need_shade = ex.shade;
            }
            if (need < 0) {
                for (int i = 0; i < nv; ++i) {
                    if (dg[i] > 0) dsup[i] |= bit(dg[i]);
                    else dall[i] = true;
                    if (sh[i] > 0) ssup[i] |= (uint8_t)(1 << sh[i]);
                    else sall[i] = true;
                }
                return;
            }
            const int c = cellv[need];
            if (need_shade) {
                for (int col = 1; col <= 2 && complete; ++col) {
                    sh[need] = col;
                    go();
                }
                sh[need] = -1;
            } else {
                for (uint32_t m = cand[c]; m && complete; m &= m - 1) {
                    dg[need] = lowdigit(m);
                    go();
                }
                dg[need] = -1;
            }
        };
        go();
        if (!complete) continue;
        std::vector<std::pair<int, int>> dout;
        std::vector<std::pair<int, int>> sout;
        for (int i = 0; i < nv; ++i) {
            const int c = cellv[i];
            if (!vals[c] && !dall[i])
                for (uint32_t m = cand[c] & ~dsup[i]; m; m &= m - 1) dout.emplace_back(c, lowdigit(m));
            if (!shade[c] && !sall[i] && (ssup[i] == 2 || ssup[i] == 4)) sout.emplace_back(c, ssup[i] == 2 ? 1 : 2);
        }
        std::sort(dout.begin(), dout.end());
        dout.erase(std::unique(dout.begin(), dout.end()), dout.end());
        std::sort(sout.begin(), sout.end());
        sout.erase(std::unique(sout.begin(), sout.end()), sout.end());
        if (dout.empty() && sout.empty()) continue;
        Move& m = new_move(out, SHADE_RULE, 1.0, (int)(dout.size() + sout.size()));
        for (auto& e : dout) add_elim(out, m, e.first, e.second);
        for (auto& e : sout) set_colour(out, m, e.first, e.second);
        set_pattern(out, m, std::vector<int>(cellv, cellv + nv));
        m.nk = NM_NARY;
        m.code = 7331;
    }
}

}  // namespace cs
