// 3D Medusa: two-colouring of candidates over strong links of several digits (bivalue cells,
// digits with two places in a house). One colour is entirely true, the other entirely false.
//   wrap (colour false): two same-coloured candidates in one cell; the same digit twice in one
//     colour seeing each other; an uncoloured cell all of whose candidates see that colour.
//   trap (eliminations): a candidate seeing both colours of its digit; a cell holding both
//     colours loses its other candidates; a candidate seeing colour X of its digit while its
//     cell holds the opposite colour.
// Single-digit clusters are left to Coloring.
#include <algorithm>
#include "portable.hpp"
#include <set>
#include <cstdlib>
#include <cstdio>
#include <array>
#include <functional>
#include <map>

#include "solver.hpp"

namespace cs {
namespace {
inline int dlo(uint32_t m) { return m ? __builtin_ctz(m) + 1 : 0; }
inline int dhi(uint32_t m) { return m ? 32 - __builtin_clz(m) : 0; }
}  // namespace

void Solver::medusa(MoveBuf& out) {
    if (disabled[MEDUSA]) return;
    const int N = p.N;
    std::vector<int> nid((size_t)N * 32, -1);
    std::vector<std::pair<int, int>> node;
    for (int c = 0; c < N; ++c)
        if (!vals[c])
            for (uint32_t m = cand[c]; m; m &= m - 1) {
                nid[(size_t)c * 32 + lowdigit(m)] = (int)node.size();
                node.push_back({c, lowdigit(m)});
            }
    const int M = (int)node.size();
    if (M < 4) return;
    std::vector<std::vector<int>> adj(M);
    auto link = [&](int a, int b) {
        adj[a].push_back(b);
        adj[b].push_back(a);
    };
    for (int c = 0; c < N; ++c)
        if (!vals[c] && popc(cand[c]) == 2) {
            int a = lowdigit(cand[c]), b = lowdigit(cand[c] & (cand[c] - 1));
            link(nid[(size_t)c * 32 + a], nid[(size_t)c * 32 + b]);
        }
    for (int hi : p.houses)
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm), k = 0, cs2[2] = {-1, -1};
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & bit(v))) {
                    if (k < 2) cs2[k] = c;
                    ++k;
                }
            if (k == 2) link(nid[(size_t)cs2[0] * 32 + v], nid[(size_t)cs2[1] * 32 + v]);
        }
    std::vector<int> comp(M, -1), col(M, 0);
    int ncomp = 0;
    for (int s = 0; s < M; ++s) {
        if (comp[s] >= 0 || adj[s].empty()) continue;
        std::vector<int> stack{s}, members{s};
        comp[s] = ncomp;
        col[s] = 0;
        while (!stack.empty()) {
            int x = stack.back();
            stack.pop_back();
            for (int y : adj[x])
                if (comp[y] < 0) {
                    comp[y] = ncomp;
                    col[y] = 1 - col[x];
                    stack.push_back(y);
                    members.push_back(y);
                }
        }
        ++ncomp;
        bool odd = false;  // conjugate links: an odd cycle means an inconsistent state
        for (int x : members)
            for (int y : adj[x]) odd |= col[x] == col[y];
        if (odd) continue;
        uint32_t digs = 0;
        for (int x : members) digs |= bit(node[x].second);
        if (popc(digs) < 2 || members.size() < 4) continue;  // single digit: Coloring
        std::sort(members.begin(), members.end());
        // per cell: colour masks (digits coloured 0 / 1)
        std::vector<uint32_t> cm0(N, 0), cm1(N, 0);
        for (int x : members) (col[x] ? cm1 : cm0)[node[x].first] |= bit(node[x].second);
        auto sees_col = [&](int c, int v, int colour) {  // a peer holds digit v in that colour
            for (int q : p.peer_list[c])
                if (!vals[q] && ((colour ? cm1 : cm0)[q] & bit(v))) return true;
            return false;
        };
        std::vector<int> pat;
        for (int x : members)
            if (pat.empty() || pat.back() != node[x].first) pat.push_back(node[x].first);
        std::sort(pat.begin(), pat.end());
        pat.erase(std::unique(pat.begin(), pat.end()), pat.end());
        auto emit = [&](const std::vector<uint32_t>& el, int rule, int false_col, int wa, int wb) {
            if (el.empty()) return;
            const int n = (int)members.size();
            Move& m = new_move(out, MEDUSA, 1.0, n);
            for (uint32_t e : el) {
                out.elims.push_back(e);
                ++m.el_n;
            }
            set_pattern(out, m, pat);
            std::vector<int> rec{0, false_col >= 0, false_col, wa, wb, 0};
            std::vector<int> c0, c1;
            for (int x : members) (col[x] ? c1 : c0).push_back(node[x].first * 32 + node[x].second);
            rec[5] = (int)c0.size();
            rec.insert(rec.end(), c0.begin(), c0.end());
            rec.insert(rec.end(), c1.begin(), c1.end());
            add_expl(out, m, EX_COLOR, rec);  // digit 0: multi-digit, entries cell*32+digit
            m.has_meta = true;
            m.meta[0] = std::min(N, (int)pat.size());
            m.meta[1] = std::max(1, n - 1);
            m.meta[2] = popc(digs);
            m.meta[3] = std::min(n - 1, 12);  // links, capped: linear in the meta-theta exponent
            m.meta[4] = 1;
            m.meta[5] = 0;
            m.meta[6] = 0;
            m.meta[7] = 1;
            m.spread = pspread(pat);
            m.code = 3501 + rule;
            pm_long xm[XM_N] = {rule, n, popc(digs), (pm_long)el.size(), false_col, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        };
        // wraps: find a false colour
        int false_col = -1, wa = -1, wb = -1, wrule = 0;
        for (int c = 0; c < N && false_col < 0; ++c) {
            if (popc(cm0[c]) >= 2) false_col = 0, wa = wb = c, wrule = 1;
            else if (popc(cm1[c]) >= 2) false_col = 1, wa = wb = c, wrule = 1;
        }
        for (int x : members) {
            if (false_col >= 0) break;
            int c = node[x].first, v = node[x].second;
            for (int q : p.peer_list[c])
                if (q > c && !vals[q] && (((col[x] ? cm1 : cm0)[q]) & bit(v))) {
                    false_col = col[x], wa = c, wb = q, wrule = 2;
                    break;
                }
        }
        for (int c = 0; c < N && false_col < 0; ++c) {
            if (vals[c] || cm0[c] || cm1[c]) continue;
            for (int colour = 0; colour < 2 && false_col < 0; ++colour) {
                bool all = true;
                for (uint32_t m = cand[c]; m && all; m &= m - 1) all = sees_col(c, lowdigit(m), colour);
                if (all) false_col = colour, wa = wb = c, wrule = 3;
            }
        }
        if (false_col >= 0) {
            std::vector<uint32_t> el;
            for (int x : members)
                if (col[x] == false_col) el.push_back((uint32_t)node[x].first * 32u + node[x].second);
            std::sort(el.begin(), el.end());
            emit(el, wrule, false_col, wa, wb);
            continue;
        }
        std::vector<uint32_t> el;
        for (int c = 0; c < N; ++c) {
            if (vals[c]) continue;
            for (uint32_t m = cand[c]; m; m &= m - 1) {
                const int v = lowdigit(m);
                const uint32_t b = bit(v);
                if ((cm0[c] | cm1[c]) & b) continue;  // coloured candidates stay
                bool kill = false;
                if (cm0[c] && cm1[c]) kill = true;  // both colours in this cell
                else if (sees_col(c, v, 0) && sees_col(c, v, 1)) kill = true;
                else if ((cm1[c] && sees_col(c, v, 0)) || (cm0[c] && sees_col(c, v, 1))) kill = true;
                if (kill) el.push_back((uint32_t)c * 32u + v);
            }
        }
        emit(el, 0, -1, -1, -1);
    }
}

}  // namespace cs

namespace cs {

// Abstract-digit colour algebra (CTC "two cells hold the same unknown digit"): classes of cells
// that must hold the same digit, closed transitively. Seeds: equality relations (palindromes,
// clones) and the EqualDigits argument, applied to whole classes: if class K has no member in
// house H and none of its possible digits is placed in H, K's digit is in H, in a cell that sees no
// member of K and can hold one of K's digits; a single such cell joins K. Every member keeps only
// the digits common to the class. Moves only where a class of 3+ cells (beyond EqualDigits) or a
// relation-seeded class gives eliminations.
// Structural colouring ("colour the grid first"): the puzzle's digit-permutation-invariant constraints (houses,
// all-different groups, equal / different pair relations such as palindromes, clones, anti-knight) form a puzzle
// on abstract symbols. With one complete house fixed to symbols 1..D (no loss of generality: any solution can
// be relabelled), if that symbol puzzle has exactly one solution, every cell's colour is known: cells of one
// colour hold one (unknown) digit. Computed once per solve (canonical mode only; boards up to 16x16).
const std::vector<int>& Solver::struct_colours() {
    if (struct_done) return struct_cls;
    struct_done = true;
    if (!canon || p.D > 16 || disabled[COLOUR_ALGEBRA]) return struct_cls;
    const int N = p.N, D = p.D;
    auto q = std::make_shared<Puzzle>();
    q->D = D;
    q->coords = p.coords;
    q->domains.assign(N, p.full);
    q->is_derived = true;
    q->exact_shapes = true;
    const int G0 = p.base_G >= 0 ? p.base_G : p.G;
    int anchor = -1;
    for (int g = 0; g < G0; ++g) {
        if (p.groups[g].cells.size() < 2) continue;
        Group gg = p.groups[g];
        gg.has_total = false, gg.total = 0;
        q->groups.push_back(gg);
        if (anchor < 0 && p.groups[g].complete && (int)p.groups[g].cells.size() == D && p.group_cat[g] == GC_BOX)
            anchor = (int)q->groups.size() - 1;
    }
    if (anchor < 0) return struct_cls;
    int n_extra = 0;  // invariant relations beyond the houses
    for (const RelSpec& rs : p.relations) {
        bool eq = true, ne = true, none = true;
        for (int v = 1; v <= D; ++v) {
            const uint32_t f = rs.neq ? bit(v) : (v < (int)rs.fwd.size() ? rs.fwd[v] : 0u);
            eq &= f == (p.full & ~bit(v));
            ne &= f == bit(v);
            none &= f == 0;
        }
        if (none || !(eq || ne)) continue;
        RelSpec r = rs;
        q->relations.push_back(r);
        ++n_extra;
    }
    bool any_eq = false;
    for (const RelSpec& rs : q->relations)
        if (!rs.neq && rs.fwd.size() > 1 && rs.fwd[1] == (p.full & ~bit(1))) any_eq = true;
    if (!any_eq) return struct_cls;  // without equalities the symbols are a plain sudoku (never unique)
    q->finalize();
    std::vector<std::pair<int, int>> giv;
    int sym = 0;
    for (int c : q->groups[anchor].cells) giv.push_back({c, ++sym});
    bool complete = true;
    auto sols = brute_solve(*q, giv, 2, 2000000, nullptr, nullptr, &complete);
    if (std::getenv("COLOUR_DEBUG"))
        fprintf(stderr, "struct colours: %d invariant relations, %zu solutions, complete %d\n", n_extra, sols.size(),
                (int)complete);
    if (sols.size() == 1 && complete) {
        struct_cls.assign(N, -1);
        for (int c = 0; c < N; ++c) struct_cls[c] = sols[0][c];
        return struct_cls;
    }
    if (sols.empty() || !P.colour_partial) return struct_cls;  // partial colouring: params colour_partial (off)
    // several symbol solutions: the cells whose symbol is the same in EVERY solution (singleton consistency over
    // the symbol puzzle, bounded; a symbol is kept when its search is cut off) form a partial colouring
    std::vector<uint32_t> sup(N, 0);
    for (auto& sl : sols)
        for (int c = 0; c < N; ++c) sup[c] |= bit(sl[c]);
    pm_long work = 0;
    const pm_long cap = 3000000;
    std::vector<uint8_t> v0(N, 0);
    std::vector<uint32_t> c0(N, p.full);
    for (auto& g : giv) v0[g.first] = (uint8_t)g.second, c0[g.first] = 0;
    for (int c = 0; c < N && work < cap; ++c) {
        if (v0[c]) continue;
        for (int sy = 1; sy <= D && work < cap; ++sy) {
            if (sup[c] & bit(sy)) continue;
            std::vector<uint8_t> v2 = v0;
            std::vector<uint32_t> c2 = c0;
            c2[c] = bit(sy);
            bool comp = true;
            pm_long cost = 0;
            auto r = brute_solve(*q, {}, 1, 50000, &v2, &c2, &comp, &cost);
            work += cost;
            if (!r.empty())
                for (int x = 0; x < N; ++x) sup[x] |= bit(r[0][x]);
            else if (!comp)
                sup[c] |= bit(sy);  // unknown: kept
        }
    }
    if (work >= cap) return struct_cls;
    int forced = 0;
    std::vector<int> cls(N, -1);
    for (int c = 0; c < N; ++c)
        if (v0[c]) cls[c] = v0[c];
        else if (popc(sup[c]) == 1) cls[c] = lowdigit(sup[c]), ++forced;
    if (std::getenv("COLOUR_DEBUG")) fprintf(stderr, "struct colours: partial, %d forced cells\n", forced);
    if (forced < D) return struct_cls;
    struct_cls = cls;  // -1 = colour unknown
    return struct_cls;
}

// Colour disambiguation (after the structural colouring): every colour is one digit, colours are a permutation
// of the digits. Each permutation consistent with the candidates and the pair relations between colours is
// expanded to a full grid and checked against every rule (cages, sums, lines); digits no consistent permutation
// gives a colour leave all its cells. Bounded (node cap); nothing is emitted when the cap is hit.
void Solver::colour_disambiguate(MoveBuf& out) {
    const std::vector<int>& sc = struct_colours();
    if (sc.empty()) return;
    for (int x : sc)
        if (x < 1) return;  // partial colouring: no full permutation to disambiguate
    const int N = p.N, D = p.D, D1 = D + 1;
    std::vector<std::vector<int>> cells(D + 1);
    for (int c = 0; c < N; ++c)
        if (sc[c] >= 1 && sc[c] <= D) cells[sc[c]].push_back(c);
    std::vector<uint32_t> dom(D + 1, p.full);
    for (int s = 1; s <= D; ++s)
        for (int c : cells[s]) dom[s] &= vals[c] ? bit(vals[c]) : cand[c];
    for (int s = 1; s <= D; ++s)
        if (!dom[s]) return;  // inconsistent state: leave it
    std::vector<int> order;
    for (int s = 1; s <= D; ++s) order.push_back(s);
    std::sort(order.begin(), order.end(), [&](int a, int b) { return popc(dom[a]) < popc(dom[b]); });
    bool any_open = false;
    for (int s = 1; s <= D; ++s) any_open |= popc(dom[s]) > 1;
    if (!any_open) return;
    std::vector<int> dig(D + 1, 0);
    std::vector<uint32_t> sup(D + 1, 0);
    std::vector<uint8_t> grid(N, 0);
    pm_long nodes = 0, leaves = 0;
    const pm_long cap = 200000;
    bool aborted = false;
    static const std::vector<GacReq> noreq;
    auto pair_ok = [&](int s, int d) {  // relations between cells of colour s (digit d) and assigned colours
        for (int c : cells[s])
            for (size_t j = 0; j < p.rel[c].size(); ++j) {
                const int q = p.rel[c][j], t = sc[q];
                if (t < 1 || !dig[t]) continue;
                if (p.rel_out[c][j * D1 + d] & bit(dig[t])) return false;
            }
        return true;
    };
    auto leaf_ok = [&]() {
        for (int c = 0; c < N; ++c) grid[c] = (uint8_t)dig[sc[c]];
        for (int gi = 0; gi < p.G; ++gi)
            if (p.groups[gi].has_total) {
                int t = 0;
                for (int c : p.groups[gi].cells) t += grid[c];
                if (t != p.groups[gi].total) return false;
            }
        uint32_t dm[64];
        for (const NConstraint& k : p.nary) {
            if (k.nv() > 64) continue;
            for (int i = 0; i < k.nv(); ++i) dm[i] = bit(grid[k.vars[i]]);
            GacOut o;
            nary_gac(k, dm, noreq, 1000, D, o);
            if (o.complete && !o.any) return false;
        }
        return true;
    };
    std::function<void(int, uint32_t)> rec = [&](int i, uint32_t used) {
        if (aborted) return;
        if (++nodes > cap) { aborted = true; return; }
        if (i == D) {
            ++leaves;
            if (leaf_ok())
                for (int s = 1; s <= D; ++s) sup[s] |= bit(dig[s]);
            return;
        }
        const int s = order[i];
        for (uint32_t m = dom[s] & ~used; m; m &= m - 1) {
            const int d = lowdigit(m);
            if (!pair_ok(s, d)) continue;
            dig[s] = d;
            rec(i + 1, used | bit(d));
            dig[s] = 0;
            if (aborted) return;
        }
    };
    rec(0, 0);
    if (aborted) return;
    std::vector<uint32_t> el;
    std::vector<int> pc;
    for (int s = 1; s <= D; ++s)
        for (int c : cells[s]) {
            if (vals[c]) continue;
            const uint32_t gone = cand[c] & ~sup[s];
            for (uint32_t b = gone; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            if (gone) pc.push_back(c);
        }
    if (el.empty()) return;
    Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, D);
    for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
    set_pattern(out, m, pc);
    m.has_meta = true;
    m.meta[0] = std::min(N, (int)pc.size());
    m.meta[1] = D;
    m.meta[2] = D;
    m.meta[3] = std::min(D, 12);
    m.meta[4] = 1;
    m.meta[5] = 1;
    m.meta[6] = 1;
    m.meta[7] = 1;
    m.spread = pspread(pc);
    m.code = 3513;
    pm_long xm[XM_N] = {(pm_long)pc.size(), D, (pm_long)el.size(), 4, 0, std::min(leaves, pm_long(1000000000)), 0, 0, 0, 0};
    std::copy(xm, xm + XM_N, m.xm);
}

void Solver::colour_algebra(MoveBuf& out, bool direct_view) {
    if (disabled[COLOUR_ALGEBRA]) return;
    std::vector<uint32_t> saved_cand;
    if (direct_view) {  // on the no-notes mental view
        compute_mental(3);
        saved_cand = cand;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) cand[c] = md[c];
        ++version;
    }
    struct Restore {
        Solver& s;
        std::vector<uint32_t>& saved;
        bool on;
        ~Restore() {
            if (on) {
                s.cand = saved;
                ++s.version;
                s.label_version = -1;
            }
        }
    } restore{*this, saved_cand, direct_view};
    const int N = p.N, D1 = p.D + 1;
    std::vector<int> par(N);
    for (int c = 0; c < N; ++c) par[c] = c;
    std::function<int(int)> find = [&](int x) { return par[x] == x ? x : par[x] = find(par[x]); };
    auto unite = [&](int a, int b) {
        a = find(a), b = find(b);
        if (a == b) return false;
        if (b < a) std::swap(a, b);
        par[b] = a;
        return true;
    };
    // seeds: equality relations
    std::vector<char> rel_seed(N, 0);
    for (int c = 0; c < N; ++c) {
        if (vals[c]) continue;
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int q = p.rel[c][j];
            if (vals[q]) continue;
            const uint32_t* t = &p.rel_out[c][j * D1];
            bool eq = true;
            for (int v = 1; v <= p.D && eq; ++v) eq = t[v] == (p.full & ~bit(v));
            if (eq && unite(c, q)) rel_seed[c] = rel_seed[q] = 1;
        }
    }
    // human colouring seeds: cells of one colour are taken to share a digit (consistent groups only)
    std::vector<char> human_seed(N, 0);
    std::vector<std::pair<int, int>> human_resolved;  // (cell, digit) from a coloured placed cell
    bool soft = false;
    if (!opt.colours.empty()) {
        std::map<int, std::vector<int>> groups;
        for (int c = 0; c < N && c < (int)opt.colours.size(); ++c)
            if (opt.colours[c] >= 0) groups[opt.colours[c]].push_back(c);
        soft = opt.solution.empty();
        for (auto& g : groups) {
            const std::vector<int>& cs = g.second;
            if (cs.size() < 2) continue;
            bool ok = true;
            int placed_v = 0;
            for (size_t i = 0; i < cs.size() && ok; ++i) {
                if (!soft && opt.solution[cs[i]] != opt.solution[cs[0]]) ok = false;
                if (vals[cs[i]]) {
                    if (placed_v && placed_v != vals[cs[i]]) ok = false;
                    placed_v = vals[cs[i]];
                }
                for (size_t j = i + 1; j < cs.size() && ok; ++j)
                    if (tbit(p.peers(cs[i]), cs[j])) ok = false;  // one digit cannot repeat in a house
            }
            if (!ok) continue;  // the colour means something else here (parity, a set, ...)
            int first = -1;
            for (int c : cs) {
                if (vals[c]) continue;
                human_seed[c] = 1;
                if (placed_v) {
                    if (cand[c] & bit(placed_v)) human_resolved.push_back({c, placed_v});
                    continue;
                }
                if (first < 0) first = c;
                else if (unite(first, c)) rel_seed[first] = rel_seed[c] = 1;
            }
        }
    }
    // structural colouring of the grid (symbols forced by the permutation-invariant rules): one colour, one digit
    std::vector<char> struct_seed(N, 0);
    std::vector<std::pair<int, int>> struct_resolved;
    {
        const std::vector<int>& sc = struct_colours();
        if (!sc.empty()) {
            std::map<int, std::vector<int>> groups;
            for (int c = 0; c < N; ++c)
                if (sc[c] >= 1) groups[sc[c]].push_back(c);
            for (auto& g : groups) {
                int placed_v = 0, first = -1;
                for (int c : g.second)
                    if (vals[c]) placed_v = vals[c];
                for (int c : g.second) {
                    if (vals[c]) continue;
                    struct_seed[c] = 1;
                    if (placed_v) {
                        if (cand[c] & bit(placed_v)) struct_resolved.push_back({c, placed_v});
                        continue;
                    }
                    if (first < 0) first = c;
                    else if (unite(first, c)) rel_seed[first] = rel_seed[c] = 1;
                }
            }
        }
    }
    if (!direct_view) colour_disambiguate(out);
    // mixed human colour groups read as a digit class (all odd / even / low / middle / high in the
    // solution): members keep that class (sets are skipped: naming them would leak the solution)
    if (!opt.colours.empty() && !opt.solution.empty()) {
        std::map<int, std::vector<int>> groups;
        for (int c = 0; c < N && c < (int)opt.colours.size(); ++c)
            if (opt.colours[c] >= 0) groups[opt.colours[c]].push_back(c);
        uint32_t odd = 0;
        for (int d = 1; d <= p.D; d += 2) odd |= bit(d);
        std::vector<std::pair<uint32_t, int>> classes{{odd, 0}, {p.full & ~odd, 1}};
        if (p.D == 9)
            for (int t = 0; t < 3; ++t) classes.push_back({(uint32_t)(7u << (3 * t)), 2 + t});
        for (auto& g : groups) {
            const std::vector<int>& cs = g.second;
            if (cs.size() < 2) continue;
            uint32_t sd = 0;
            for (int c : cs) sd |= bit(opt.solution[c]);
            if (popc(sd) < 2) continue;  // one digit: handled as a same-digit colour above
            uint32_t keep = p.full;
            int kinds = 0;
            for (auto& cl : classes)
                if (!(sd & ~cl.first)) {
                    keep &= cl.first;
                    kinds |= 1 << cl.second;
                }
            if (keep == p.full) continue;  // a set or mixed: skipped
            std::vector<uint32_t> el;
            for (int c : cs)
                if (!vals[c])
                    for (uint32_t b = cand[c] & ~keep; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            if (el.empty()) continue;
            std::vector<int> pc;
            for (int c : cs)
                if (!vals[c]) pc.push_back(c);
            if (direct_view) {  // no notes: a member left with one digit of its class
                for (int c : pc) {
                    const uint32_t left = cand[c] & keep;
                    if (popc(left) != 1 || popc(cand[c]) < 2) continue;
                    Move& pm = new_move(out, COLOUR_ALGEBRA, 1.0, (int)cs.size());
                    pm.pc = c;
                    pm.pv = lowdigit(left);
                    set_pattern(out, pm, pc);
                    pm.has_meta = true;
                    pm.meta[0] = std::min(N, (int)pc.size() + 1);
                    pm.meta[1] = 1;
                    pm.meta[2] = popc(keep);
                    pm.meta[3] = 1;
                    pm.meta[4] = 0;
                    pm.meta[5] = 0;
                    pm.meta[6] = 0;
                    pm.meta[7] = 0;
                    pm.spread = pspread(pc);
                    pm.code = 3510;
                    pm_long xm[XM_N] = {(pm_long)cs.size(), popc(keep), 0, 2, kinds, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, pm.xm);
                }
                continue;
            }
            Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, (int)cs.size());
            for (uint32_t e : el) {
                out.elims.push_back(e);
                ++m.el_n;
            }
            set_pattern(out, m, pc);
            m.has_meta = true;
            m.meta[0] = std::min(N, (int)pc.size());
            m.meta[1] = 1;
            m.meta[2] = popc(keep);
            m.meta[3] = 1;
            m.meta[4] = 0;
            m.meta[5] = 0;
            m.meta[6] = 0;
            m.meta[7] = 1;
            m.spread = pspread(pc);
            m.code = 3510;
            pm_long xm[XM_N] = {(pm_long)cs.size(), popc(keep), (pm_long)el.size(), 2, kinds, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
    for (auto& cv : struct_resolved) human_resolved.push_back(cv);
    const size_t n_human_resolved = human_resolved.size() - struct_resolved.size();
    size_t i_res = 0;
    for (auto& cv : human_resolved) {  // a coloured cell already solved gives the colour's digit
        const bool from_struct = i_res++ >= n_human_resolved;
        Move& pm = new_move(out, COLOUR_ALGEBRA, 1.0, 2);
        pm.pc = cv.first;
        pm.pv = cv.second;
        set_pattern(out, pm, {cv.first});
        add_expl(out, pm, EX_COLOR, {0, 0, -1, -1, -1, 1, cv.first * 32});
        pm.has_meta = true;
        pm.meta[0] = 2;
        pm.meta[1] = 1;
        pm.meta[2] = 1;
        pm.meta[3] = 1;
        pm.meta[4] = 0;
        pm.meta[5] = 0;
        pm.meta[6] = 0;
        pm.meta[7] = direct_view ? 0 : 1;
        pm.spread = 1.0;
        pm.code = 3509;
        pm_long xm[XM_N] = {1, 1, 0, from_struct ? 4 : soft ? 3 : 2, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, pm.xm);
    }
    // seeds from short case splits (CTC colouring "if this is x, that is x too; if y, y"): a bivalue
    // cell A = {x, y}; a cell B that becomes x when A = x and y when A = y holds A's digit
    {
        std::vector<int> biv;
        for (int c = 0; c < N; ++c)
            if (!vals[c] && popc(cand[c]) == 2) biv.push_back(c);
        if (biv.size() <= 60) {
            std::vector<uint8_t> va, vb;
            std::vector<std::pair<int, int>> eq;
            for (int a : biv) {
                const int x = lowdigit(cand[a]), y = lowdigit(cand[a] & (cand[a] - 1));
                int pa = 0, pb = 0;
                if (case_split(a, x, 4, pa, &va) || case_split(a, y, 4, pb, &vb)) continue;
                for (int b = 0; b < N; ++b)
                    if (b != a && !vals[b] && va[b] == x && vb[b] == y) eq.push_back({a, b});
            }
            for (auto& e : eq)
                if (unite(e.first, e.second)) rel_seed[e.first] = rel_seed[e.second] = 1;
        }
    }
    // closure (Jacobi rounds: every join of a round uses the classes at its start)
    for (int round = 0; round < 6; ++round) {
        std::vector<std::vector<int>> mem(N);
        for (int c = 0; c < N; ++c)
            if (!vals[c]) mem[find(c)].push_back(c);
        std::vector<std::pair<int, int>> joins;
        for (int r = 0; r < N; ++r) {
            if (mem[r].empty()) continue;
            uint32_t K = p.full;
            for (int c : mem[r]) K &= cand[c];
            if (popc(K) < 2) continue;
            for (int hi : p.houses) {
                bool inside = false;
                for (int c : mem[r]) inside |= tbit(p.gbits(hi), c);
                if (inside || (placed_g[hi] & K)) continue;
                int at = -1, n = 0;
                for (int x : p.groups[hi].cells) {
                    if (vals[x] || !(cand[x] & K)) continue;
                    bool sees = false;
                    for (int c : mem[r]) sees |= tbit(p.peers(c), x);
                    if (sees) continue;
                    ++n;
                    at = x;
                }
                if (n == 1) joins.push_back({r, at});
            }
        }
        bool ch = false;
        for (auto& j : joins) ch |= unite(j.first, j.second);
        if (!ch) break;
    }
    std::vector<std::vector<int>> mem(N);
    for (int c = 0; c < N; ++c)
        if (!vals[c]) mem[find(c)].push_back(c);
    // ---- colour sums (CTC "blue and yellow add up to seven"): a sum rule whose cells include two or more cells
    // of one colour is a sum over colour variables with multiplicities. Enumerate the variables (cells of one
    // colour share a digit; variables whose members see each other differ); a digit no solution gives a colour
    // leaves EVERY member of the colour, also outside the rule. Only notes view; small rules (<= 8 variables).
    if (!direct_view) {
        struct Lin { std::vector<int> cells; int total; };
        std::vector<Lin> lins;
        for (int g : p.sum_cages) lins.push_back({p.groups[g].cells, p.groups[g].total});
        for (const NConstraint& k : p.nary)
            if (k.type == NT_SUM && k.totals.empty() && k.offset == 0 && !k.bounds_only) lins.push_back({k.vars, k.total});
        for (const Lin& L : lins) {
            std::map<int, int> mult;  // root (or -1-cell for a placed cell) -> multiplicity
            int fixed = 0;
            bool tied = false;
            for (int c : L.cells) {
                if (vals[c]) { fixed += vals[c]; continue; }
                const int r = find(c);
                if (++mult[r] >= 2) tied = true;
            }
            if (!tied || mult.size() > 8) continue;
            std::vector<int> roots, w;
            std::vector<uint32_t> dom;
            for (auto& kv : mult) {
                uint32_t K = p.full;
                for (int c : mem[kv.first]) K &= cand[c];
                if (!K) { roots.clear(); break; }
                roots.push_back(kv.first), w.push_back(kv.second), dom.push_back(K);
            }
            if (roots.empty()) continue;
            const int nv = (int)roots.size();
            std::vector<std::vector<char>> diff(nv, std::vector<char>(nv, 0));
            for (int a = 0; a < nv; ++a)
                for (int b = a + 1; b < nv; ++b) {
                    bool sees = false;
                    for (int x : mem[roots[a]])
                        for (int y : mem[roots[b]]) sees |= tbit(p.peers(x), y);
                    diff[a][b] = diff[b][a] = sees;
                }
            std::vector<uint32_t> sup(nv, 0);
            std::vector<int> asg(nv, 0);
            pm_long nodes = 0;
            bool aborted = false;
            const int T = L.total - fixed;
            std::function<void(int, int)> rec = [&](int i, int s) {
                if (aborted) return;
                if (++nodes > 50000) { aborted = true; return; }
                if (i == nv) {
                    if (s == T)
                        for (int j = 0; j < nv; ++j) sup[j] |= bit(asg[j]);
                    return;
                }
                for (uint32_t m = dom[i]; m; m &= m - 1) {
                    const int v = lowdigit(m);
                    if (s + w[i] * v > T) break;  // digits ascend
                    bool ok = true;
                    for (int j = 0; j < i && ok; ++j) ok = !(diff[i][j] && asg[j] == v);
                    if (!ok) continue;
                    asg[i] = v;
                    rec(i + 1, s + w[i] * v);
                }
            };
            rec(0, 0);
            if (aborted) continue;
            std::vector<uint32_t> el;
            std::vector<int> pc;
            bool none = false;
            for (int j = 0; j < nv; ++j) none |= !sup[j];
            if (none) continue;  // inconsistent state: left to other logic
            for (int j = 0; j < nv; ++j) {
                if (!(dom[j] & ~sup[j])) continue;  // the colour lost nothing here
                for (int c : mem[roots[j]]) {
                    const uint32_t g2 = cand[c] & ~sup[j];
                    if (!g2) continue;
                    for (uint32_t b = g2; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                    pc.push_back(c);
                }
            }
            if (el.empty()) continue;
            std::sort(el.begin(), el.end());
            el.erase(std::unique(el.begin(), el.end()), el.end());
            Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, nv);
            for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
            std::vector<int> pat(L.cells.begin(), L.cells.end());
            set_pattern(out, m, pat);
            m.has_meta = true;
            m.meta[0] = std::min(N, (int)(L.cells.size() + pc.size()));
            m.meta[1] = nv;
            m.meta[2] = 0;
            for (uint32_t d : dom) m.meta[2] = std::max(m.meta[2], popc(d));
            m.meta[3] = std::min(nv, 12);
            m.meta[4] = 1;
            m.meta[5] = 1;
            m.meta[6] = 0;
            m.meta[7] = 1;
            m.spread = pspread(pat);
            m.code = 3514;
            pm_long xm[XM_N] = {(pm_long)L.cells.size(), nv, (pm_long)el.size(), 0, 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
        // ---- colour arithmetic (CTC "grey and orange add up to 10, blue and red add up to 10, the spare digit is
        // green, which is 5"): several sum rules and houses over the SAME colour variables solved jointly. A
        // component = rules (sum cages / sums with >= 1 colour of >= 2 cells) linked by shared colours, plus every
        // house whose open cells all belong to the component's variables (total D(D+1)/2 minus its placed digits).
        // Joint enumeration (<= 10 variables, bounded); digits no solution gives a variable leave every member.
        {
            std::vector<Lin> rules;
            for (const Lin& L : lins) {
                bool tied = false;
                for (int c : L.cells)
                    if (!vals[c] && mem[find(c)].size() >= 2) tied = true;
                if (tied) rules.push_back(L);
            }
            const int nr = (int)rules.size();
            std::vector<int> comp(nr, -1);
            int ncomp = 0;
            auto roots_of = [&](const Lin& L) {
                std::set<int> r;
                for (int c : L.cells)
                    if (!vals[c]) r.insert(find(c));
                return r;
            };
            for (int i = 0; i < nr; ++i) {
                if (comp[i] >= 0) continue;
                comp[i] = ncomp;
                std::vector<int> stack{i};
                while (!stack.empty()) {
                    const int a = stack.back();
                    stack.pop_back();
                    auto ra = roots_of(rules[a]);
                    for (int b = 0; b < nr; ++b) {
                        if (comp[b] >= 0) continue;
                        auto rb = roots_of(rules[b]);
                        bool share = false;
                        for (int r : rb) share |= ra.count(r) && mem[r].size() >= 2;
                        if (share) comp[b] = ncomp, stack.push_back(b);
                    }
                }
                ++ncomp;
            }
            for (int ci = 0; ci < ncomp; ++ci) {
                std::vector<Lin> sys;
                std::set<int> var_set;
                for (int i = 0; i < nr; ++i)
                    if (comp[i] == ci) {
                        sys.push_back(rules[i]);
                        for (int r : roots_of(rules[i])) var_set.insert(r);
                    }
                if (var_set.size() > 10) continue;
                for (int hi : p.houses) {  // houses closed over the variables
                    if (!p.groups[hi].complete) continue;
                    bool closed = true, any = false;
                    for (int c : p.groups[hi].cells)
                        if (!vals[c]) any = true, closed &= var_set.count(find(c)) > 0;
                    if (closed && any) sys.push_back({p.groups[hi].cells, p.D * (p.D + 1) / 2});
                }
                if (sys.size() < 2) continue;  // one rule alone: colour sums above
                std::vector<int> roots(var_set.begin(), var_set.end());
                const int nv = (int)roots.size();
                std::map<int, int> vid;
                for (int j = 0; j < nv; ++j) vid[roots[j]] = j;
                std::vector<uint32_t> dom(nv, p.full);
                bool bad0 = false;
                for (int j = 0; j < nv; ++j) {
                    for (int c : mem[roots[j]]) dom[j] &= cand[c];
                    bad0 |= !dom[j];
                }
                if (bad0) continue;
                // each rule: total minus placed digits, multiplicity per variable
                struct Row { std::vector<std::pair<int, int>> w; int t; };
                std::vector<Row> rows;
                for (const Lin& L : sys) {
                    Row r;
                    r.t = L.total;
                    std::map<int, int> mm;
                    for (int c : L.cells) {
                        if (vals[c]) r.t -= vals[c];
                        else ++mm[vid[find(c)]];
                    }
                    for (auto& kv : mm) r.w.push_back(kv);
                    rows.push_back(r);
                }
                std::vector<std::vector<char>> diff(nv, std::vector<char>(nv, 0));
                for (int a = 0; a < nv; ++a)
                    for (int b = a + 1; b < nv; ++b) {
                        bool sees = false;
                        for (int x : mem[roots[a]])
                            for (int y : mem[roots[b]]) sees |= tbit(p.peers(x), y);
                        diff[a][b] = diff[b][a] = sees;
                    }
                std::vector<int> asg(nv, 0);
                std::vector<uint32_t> sup(nv, 0);
                pm_long nodes = 0;
                bool aborted = false;
                auto rows_ok = [&](int upto) {  // bounds check of every row with variables 0..upto assigned
                    for (const Row& r : rows) {
                        pm_long lo = 0, hi = 0;
                        for (auto& wv : r.w) {
                            if (wv.first <= upto) lo += (pm_long)wv.second * asg[wv.first], hi += (pm_long)wv.second * asg[wv.first];
                            else lo += (pm_long)wv.second * lowdigit(dom[wv.first]), hi += (pm_long)wv.second * (32 - __builtin_clz(dom[wv.first]));
                        }
                        if (lo > r.t || hi < r.t) return false;
                    }
                    return true;
                };
                std::function<void(int)> rec = [&](int i) {
                    if (aborted) return;
                    if (++nodes > 200000) { aborted = true; return; }
                    if (i == nv) {
                        for (int j = 0; j < nv; ++j) sup[j] |= bit(asg[j]);
                        return;
                    }
                    for (uint32_t m = dom[i]; m; m &= m - 1) {
                        const int v = lowdigit(m);
                        bool ok = true;
                        for (int j = 0; j < i && ok; ++j) ok = !(diff[i][j] && asg[j] == v);
                        if (!ok) continue;
                        asg[i] = v;
                        if (rows_ok(i)) rec(i + 1);
                    }
                    asg[i] = 0;
                };
                rec(0);
                if (aborted) continue;
                bool none = false;
                for (int j = 0; j < nv; ++j) none |= !sup[j];
                if (none) continue;
                std::vector<uint32_t> el;
                std::vector<int> pc;
                for (int j = 0; j < nv; ++j) {
                    if (!(dom[j] & ~sup[j])) continue;
                    for (int c : mem[roots[j]]) {
                        const uint32_t g2 = cand[c] & ~sup[j];
                        for (uint32_t b = g2; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                        if (g2) pc.push_back(c);
                    }
                }
                if (el.empty()) continue;
                std::sort(el.begin(), el.end());
                el.erase(std::unique(el.begin(), el.end()), el.end());
                Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, nv);
                for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
                std::vector<int> pat;
                for (int r : roots)
                    for (int c : mem[r]) pat.push_back(c);
                set_pattern(out, m, pat);
                m.has_meta = true;
                m.meta[0] = std::min(N, (int)pat.size());
                m.meta[1] = (int)sys.size();
                m.meta[2] = 0;
                for (uint32_t d : dom) m.meta[2] = std::max(m.meta[2], popc(d));
                m.meta[3] = std::min(nv, 12);
                m.meta[4] = 1;
                m.meta[5] = 1;
                m.meta[6] = 0;
                m.meta[7] = 1;
                m.spread = pspread(pat);
                m.code = 3515;
                pm_long xm[XM_N] = {(pm_long)pat.size(), nv, (pm_long)el.size(), 0, (pm_long)sys.size(), 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
            }
        }
    }
    // ---- colour bounds: order and min / max reasoning on whole colours (CTC "orange is a max of 5, so
    // blue is a max of 3 ... purple is 1"). Nodes = colours (classes of >= 2 cells) and the single cells
    // they touch through ordering relations; domain = digits every member allows; edges: a < b from
    // ordering pair relations (thermos, inequalities) between members; colours / cells that see each
    // other are distinct. Bounds propagate along the order edges, mutually distinct predecessors /
    // successors push the bound further (pigeonhole), for a few Jacobi rounds; a colour whose domain
    // shrinks loses those digits in every member (or is placed when one digit is left).
    {
        std::vector<int> node(N, -1);
        std::vector<std::vector<int>> nm;  // node members
        for (int r = 0; r < N; ++r)
            if (mem[r].size() >= 2) {
                for (int c : mem[r]) node[c] = (int)nm.size();
                nm.push_back(mem[r]);
            }
        const int ncol = (int)nm.size();
        if (ncol > 0) {
            // single cells linked by an ordering relation to a colour become nodes too
            for (int k = 0; k < ncol; ++k)
                for (int c : nm[k])
                    for (size_t j = 0; j < p.rel[c].size(); ++j) {
                        const int q = p.rel[c][j];
                        if (vals[q] || node[q] >= 0 || !p.rel_dir[c][j]) continue;
                        node[q] = (int)nm.size();
                        nm.push_back({q});
                    }
            const int K = (int)nm.size();
            std::vector<uint32_t> dom(K, p.full);
            for (int k = 0; k < K; ++k)
                for (int c : nm[k]) dom[k] &= cand[c];
            std::vector<std::vector<int>> less(K), more(K);  // less[k]: nodes known < k
            auto addedge = [&](int a, int b) {  // a < b
                if (a == b) return;
                if (std::find(less[b].begin(), less[b].end(), a) == less[b].end()) less[b].push_back(a);
                if (std::find(more[a].begin(), more[a].end(), b) == more[a].end()) more[a].push_back(b);
            };
            for (int k = 0; k < K; ++k)
                for (int c : nm[k])
                    for (size_t j = 0; j < p.rel[c].size(); ++j) {
                        const int q = p.rel[c][j];
                        if (vals[q] || node[q] < 0 || !p.rel_dir[c][j]) continue;
                        if (p.rel_dir[c][j] > 0) addedge(k, node[q]);  // q greater than c
                        else addedge(node[q], k);
                    }
            auto distinct = [&](int a, int b) {
                for (int x : nm[a])
                    for (int y : nm[b])
                        if (tbit(p.peers(x), y)) return true;
                return false;
            };
            std::vector<uint32_t> d0 = dom;
            int rounds = 0;
            for (int it = 0; it < 9; ++it) {
                std::vector<uint32_t> nd = dom;
                bool ch = false;
                for (int k = 0; k < K; ++k) {
                    if (!dom[k]) continue;
                    int L = dlo(dom[k]), U = dhi(dom[k]);
                    for (int a : less[k]) L = std::max(L, dlo(dom[a]) + 1);
                    for (int b : more[k]) U = std::min(U, dhi(dom[b]) - 1);
                    // mutually distinct predecessors: their lows pushed apart
                    if (less[k].size() > 1) {
                        std::vector<int> lo;
                        bool md = true;
                        for (size_t i = 0; i < less[k].size() && md; ++i)
                            for (size_t j = i + 1; j < less[k].size() && md; ++j) md = distinct(less[k][i], less[k][j]);
                        if (md) {
                            for (int a : less[k]) lo.push_back(dlo(dom[a]));
                            std::sort(lo.begin(), lo.end());
                            int v = 0;
                            for (int l : lo) v = std::max(l, v + 1);
                            L = std::max(L, v + 1);
                        }
                    }
                    if (more[k].size() > 1) {
                        std::vector<int> hi;
                        bool md = true;
                        for (size_t i = 0; i < more[k].size() && md; ++i)
                            for (size_t j = i + 1; j < more[k].size() && md; ++j) md = distinct(more[k][i], more[k][j]);
                        if (md) {
                            for (int b : more[k]) hi.push_back(-dhi(dom[b]));
                            std::sort(hi.begin(), hi.end());
                            int v = p.D + 1;
                            for (int h : hi) v = std::min(-h, v - 1);
                            U = std::min(U, v - 1);
                        }
                    }
                    if (L < 1) L = 1;
                    if (U > p.D) U = p.D;
                    uint32_t keep = 0;
                    for (int d = L; d <= U; ++d) keep |= bit(d);
                    const uint32_t x = dom[k] & keep;
                    if (x != dom[k] && x) {
                        nd[k] = x;
                        ch = true;
                    }
                }
                dom.swap(nd);
                if (!ch) break;
                rounds = it + 1;
            }
            for (int k = 0; k < ncol; ++k) {  // moves on colours only (single cells: inequality logic)
                const uint32_t lost = d0[k] & ~dom[k];
                if (!lost || !dom[k]) continue;
                // the colours that took part: those linked to k by an order edge
                const int ninv = 1 + (int)less[k].size() + (int)more[k].size();
                if (popc(dom[k]) == 1) {
                    const int v = lowdigit(dom[k]);
                    for (int c : nm[k]) {
                        if (popc(cand[c]) < 2) continue;
                        Move& pm = new_move(out, COLOUR_ALGEBRA, 1.0, (int)nm[k].size());
                        pm.pc = c;
                        pm.pv = v;
                        set_pattern(out, pm, nm[k]);
                        pm.has_meta = true;
                        pm.meta[0] = std::min(N, (int)nm[k].size() * 2 + ninv);
                        pm.meta[1] = ninv;
                        pm.meta[2] = popc(d0[k]);
                        pm.meta[3] = std::min(rounds, 12);
                        pm.meta[4] = 1;
                        pm.meta[5] = 0;
                        pm.meta[6] = 1;
                        pm.meta[7] = direct_view ? 0 : 1;
                        pm.spread = pspread(nm[k]);
                        pm.code = 3511;
                        pm_long xm[XM_N] = {(pm_long)nm[k].size(), popc(d0[k]), 0, 0, 0, 0, 0, 0, 0, 0};
                        std::copy(xm, xm + XM_N, pm.xm);
                    }
                    continue;
                }
                if (direct_view) continue;
                Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, (int)nm[k].size());
                for (int c : nm[k])
                    for (uint32_t b2 = cand[c] & lost; b2; b2 &= b2 - 1) {
                        out.elims.push_back((uint32_t)c * 32u + (uint32_t)lowdigit(b2));
                        ++m.el_n;
                    }
                set_pattern(out, m, nm[k]);
                m.has_meta = true;
                m.meta[0] = std::min(N, (int)nm[k].size() * 2 + ninv);
                m.meta[1] = ninv;
                m.meta[2] = popc(d0[k]);
                m.meta[3] = std::min(rounds, 12);
                m.meta[4] = 1;
                m.meta[5] = 0;
                m.meta[6] = 1;
                m.meta[7] = 1;
                m.spread = pspread(nm[k]);
                m.code = 3511;
                pm_long xm[XM_N] = {(pm_long)nm[k].size(), popc(d0[k]), (pm_long)m.el_n, 0, 0, 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
            }
        }
    }
    // a colour appears in every house: for each digit d the class could be and each house H without a
    // member, H must still have a place for d that sees no member (or d already placed in H, not seeing
    // any member); otherwise the colour is not d
    for (int r = 0; r < N; ++r) {
        const auto& M = mem[r];
        if (M.size() < 2) continue;
        uint32_t K = p.full;
        for (int c : M) K &= cand[c];
        uint32_t bad = 0;
        int bad_house = -1;
        for (uint32_t mm = K; mm; mm &= mm - 1) {
            const int d = lowdigit(mm);
            for (int hi : p.houses) {
                bool inside = false;
                for (int c : M) inside |= tbit(p.gbits(hi), c);
                if (inside) continue;
                bool ok = false;
                for (int x : p.groups[hi].cells) {
                    if (!(vals[x] == d || (!vals[x] && (cand[x] & bit(d))))) continue;
                    bool sees = false;
                    for (int c : M) sees |= tbit(p.peers(c), x);
                    if (!sees) {
                        ok = true;
                        break;
                    }
                }
                if (!ok) {
                    bad |= bit(d);
                    if (bad_house < 0) bad_house = hi;
                    break;
                }
            }
        }
        if (!bad || bad == K) continue;  // all digits impossible: inconsistent state, leave it
        if (popc(K & ~bad) == 1) {  // the colour is resolved: every member holds that digit
            const int v = lowdigit(K & ~bad);
            for (int c : M) {
                Move& pm = new_move(out, COLOUR_ALGEBRA, 1.0, (int)M.size());
                pm.pc = c;
                pm.pv = v;
                set_pattern(out, pm, M);
                std::vector<int> rec{0, 0, -1, -1, -1, (int)M.size()};
                for (int x : M) rec.push_back(x * 32);
                add_expl(out, pm, EX_COLOR, rec);
                add_expl(out, pm, EX_BASE, {bad_house});
                pm.has_meta = true;
                pm.meta[0] = std::min(N, (int)M.size() * 3 + (int)p.groups[bad_house].cells.size());
                pm.meta[1] = (int)M.size() + 1;
                pm.meta[2] = popc(K);
                pm.meta[3] = std::min((int)M.size(), 12);
                pm.meta[4] = 1;
                pm.meta[5] = 0;
                pm.meta[6] = 0;
                pm.meta[7] = direct_view ? 0 : 1;
                pm.spread = pspread(M);
                pm.code = 3508;
                bool hs = false, ss = false;
                for (int x : M) hs |= human_seed[x] != 0, ss |= struct_seed[x] != 0;
                pm_long xm[XM_N] = {(pm_long)M.size(), popc(K), 0, hs ? (soft ? 3 : 2) : ss ? 4 : 0, 0, 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, pm.xm);
            }
        }
        if (direct_view) continue;  // no notes: placements only
        Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, (int)M.size());
        for (int c : M)
            for (uint32_t b = cand[c] & bad; b; b &= b - 1) {
                out.elims.push_back((uint32_t)c * 32u + (uint32_t)lowdigit(b));
                ++m.el_n;
            }
        set_pattern(out, m, M);
        {
            std::vector<int> rec{0, 0, -1, -1, -1, (int)M.size()};
            for (int c : M) rec.push_back(c * 32);
            add_expl(out, m, EX_COLOR, rec);
            add_expl(out, m, EX_BASE, {bad_house});
        }
        m.has_meta = true;
        m.meta[0] = std::min(N, (int)M.size() * 3 + (int)p.groups[bad_house].cells.size());
        m.meta[1] = (int)M.size() + 1;
        m.meta[2] = popc(K);
        m.meta[3] = std::min((int)M.size(), 12);
        m.meta[4] = 1;
        m.meta[5] = 0;
        m.meta[6] = 0;
        m.meta[7] = 1;
        m.spread = pspread(M);
        m.code = 3507;
        bool hs = false, ss = false;
        for (int x : M) hs |= human_seed[x] != 0, ss |= struct_seed[x] != 0;
        pm_long xm[XM_N] = {(pm_long)M.size(), popc(K), (pm_long)m.el_n, hs ? (soft ? 3 : 2) : ss ? 4 : 0, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
    for (int r = 0; r < N; ++r) {
        const auto& M = mem[r];
        if (M.size() < 2) continue;
        bool seeded = false;
        for (int c : M) seeded |= rel_seed[c] != 0;
        if (direct_view) break;  // no notes: placements only (above)
        if (M.size() < 3 && !seeded) continue;  // a pair: EqualDigits
        uint32_t K = p.full;
        for (int c : M) K &= cand[c];
        std::vector<uint32_t> el;
        for (int c : M)
            for (uint32_t b = cand[c] & ~K; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
        if (el.empty() || !K) continue;
        Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, (int)M.size());
        for (uint32_t e : el) {
            out.elims.push_back(e);
            ++m.el_n;
        }
        set_pattern(out, m, M);
        {
            std::vector<int> rec{0, 0, -1, -1, -1, (int)M.size()};
            for (int c : M) rec.push_back(c * 32);  // one colour: the class (digit unknown)
            add_expl(out, m, EX_COLOR, rec);
        }
        m.has_meta = true;
        m.meta[0] = std::min(N, (int)M.size() * 3);
        m.meta[1] = (int)M.size();
        m.meta[2] = popc(K);
        m.meta[3] = std::min((int)M.size() - 1, 12);
        m.meta[4] = 1;
        m.meta[5] = 0;
        m.meta[6] = seeded ? 1 : 0;
        m.meta[7] = 1;
        m.spread = pspread(M);
        m.code = 3506;
        bool hs = false, ss = false;
        for (int x : M) hs |= human_seed[x] != 0, ss |= struct_seed[x] != 0;
        pm_long xm[XM_N] = {(pm_long)M.size(), popc(K), (pm_long)el.size(), hs ? (soft ? 3 : 2) : ss ? 4 : (pm_long)seeded, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
    if (!direct_view) label_shadow(out);
}

// Label break-in ("shadow sudoku", CTC "give it a big old A"). Every cell carries an abstract label
// (its digit, unknown); cells proven to hold the same digit share one label (a colour). Nothing is
// assumed: the labels of a complete house are its digits, all different. Labels follow Sudoku: a label
// that must appear in a house but has one cell there that does not see it lands on that cell ("whatever
// goes here must appear in row 1 -- only there"); labels that see each other are different. Labels follow
// the rules: a relation between cells of two labels is a relation between the labels ("A and B not
// consecutive", "A is twice B", "A below B on a thermo"), filtered by arc consistency; in each house the
// labels are a permutation of the digits (a digit only one label can take; coverage: if A = a, every
// other digit must still fit some other label of the house). A label left with digits D keeps every
// member to D. Solved cells are labels too (all 5s are one label). Rounds run until the first
// elimination (one human step), under a deterministic operation budget.
void Solver::label_shadow(MoveBuf& out) {
    const int N = p.N, D = p.D, D1 = D + 1, W = p.W;
    if (D > 16 || N > 400) return;
    int unsolved = 0;
    for (int c = 0; c < N; ++c) unsolved += !vals[c];
    if (unsolved < 4) return;
    pm_long budget = 8000000;
    std::vector<uint32_t> wc(N);
    for (int c = 0; c < N; ++c) wc[c] = vals[c] ? bit(vals[c]) : cand[c];
    std::vector<int> par(N);
    for (int c = 0; c < N; ++c) par[c] = c;
    auto find = [&](int x) {
        while (par[x] != x) x = par[x] = par[par[x]];
        return x;
    };
    auto unite = [&](int a, int b) {
        a = find(a), b = find(b);
        if (a == b) return false;
        if (b < a) std::swap(a, b);
        par[b] = a;
        return true;
    };
    {  // solved cells: one label per digit
        std::vector<int> first(D1, -1);
        for (int c = 0; c < N; ++c)
            if (vals[c]) {
                if (first[vals[c]] < 0) first[vals[c]] = c;
                else unite(first[vals[c]], c);
            }
    }
    std::vector<int> fullh;
    for (int g : p.houses)
        if ((int)p.groups[g].cells.size() == D) fullh.push_back(g);
    // strict order chains (thermos, inequalities): q above c by at least k steps -> q >= c + k; cells on
    // one chain are all different (a label cannot repeat along a thermo)
    std::vector<std::vector<std::pair<int, int>>> above(N);
    std::vector<uint64_t> xp(p.peer_bits.begin(), p.peer_bits.end());
    {
        std::vector<std::vector<int>> up(N);
        std::vector<int> indeg(N, 0);
        bool any = false;
        for (int c = 0; c < N; ++c)
            for (size_t j = 0; j < p.rel[c].size(); ++j)
                if (p.rel_dir[c][j] > 0) up[c].push_back(p.rel[c][j]), ++indeg[p.rel[c][j]], any = true;
        if (any) {
            std::vector<int> topo, st;
            for (int c = 0; c < N; ++c)
                if (!indeg[c]) st.push_back(c);
            while (!st.empty()) {
                const int c = st.back();
                st.pop_back();
                topo.push_back(c);
                for (int q : up[c])
                    if (--indeg[q] == 0) st.push_back(q);
            }
            if ((int)topo.size() == N) {  // acyclic
                std::vector<int> pos(N), dist(N);
                for (int i = 0; i < N; ++i) pos[topo[i]] = i;
                for (int c = 0; c < N; ++c) {
                    if (up[c].empty()) continue;
                    std::fill(dist.begin(), dist.end(), -1);
                    dist[c] = 0;
                    for (int i = pos[c]; i < N; ++i) {
                        const int x = topo[i];
                        if (dist[x] < 0) continue;
                        for (int q : up[x]) dist[q] = std::max(dist[q], dist[x] + 1);
                    }
                    for (int q = 0; q < N; ++q)
                        if (dist[q] > 0) {
                            above[c].push_back({q, dist[q]});
                            sbit(&xp[(size_t)c * W], q);
                            sbit(&xp[(size_t)q * W], c);
                        }
                    budget -= N;
                }
            }
        }
    }
    std::vector<uint32_t> dom(N);
    std::vector<uint64_t> mb((size_t)N * W), pb((size_t)N * W);
    std::vector<int> joins_n(N, 0);
    int rounds = 0, njoin = 0;
    bool found = false, bad = false;
    // pair constraints between labels: (K, K') -> allowed[a] masks (b of K' given K = a)
    std::map<std::pair<int, int>, std::vector<uint32_t>> pc;
    for (int round = 1; round <= 40 && !found && !bad && budget > 0; ++round) {
        bool ch = false;
        // labels: members, sight, domains
        std::fill(mb.begin(), mb.end(), 0);
        std::fill(pb.begin(), pb.end(), 0);
        for (int c = 0; c < N; ++c) dom[c] = p.full;
        for (int c = 0; c < N; ++c) {
            const int r = find(c);
            sbit(&mb[(size_t)r * W], c);
            const uint64_t* pp = &xp[(size_t)c * W];
            for (int w = 0; w < W; ++w) pb[(size_t)r * W + w] |= pp[w];
            dom[r] &= wc[c];
        }
        budget -= (pm_long)N * W;
        auto sees = [&](int r, int s) {  // some member of r sees some member of s
            const uint64_t* a = &pb[(size_t)r * W];
            const uint64_t* b = &mb[(size_t)s * W];
            for (int w = 0; w < W; ++w)
                if (a[w] & b[w]) return true;
            return false;
        };
        for (int c = 0; c < N; ++c)
            if (find(c) == c && (sees(c, c) || !dom[c])) bad = true;  // two members in one house: inconsistent
        if (bad) break;
        // label relations from the rules
        pc.clear();
        for (int c = 0; c < N; ++c)
            for (size_t j = 0; j < p.rel[c].size(); ++j) {
                const int q = p.rel[c][j], r = find(c), s = find(q);
                const uint32_t* t = &p.rel_out[c][j * D1];
                auto& v = pc[{r, s}];
                if (v.empty()) {
                    v.assign(D1, 0);
                    for (int a = 1; a <= D; ++a) v[a] = r == s ? bit(a) : p.full;
                }
                for (int a = 1; a <= D; ++a) v[a] &= ~t[a];
                budget -= D;
            }
        for (int c = 0; c < N; ++c)  // order chains: s >= r + k
            for (auto& qk : above[c]) {
                const int r = find(c), s = find(qk.first), k = qk.second;
                if (r == s) { bad = true; break; }
                auto& v = pc[{r, s}];
                if (v.empty()) v.assign(D1, p.full);
                auto& w = pc[{s, r}];
                if (w.empty()) w.assign(D1, p.full);
                for (int a = 1; a <= D; ++a) {
                    uint32_t ge = 0, le = 0;
                    for (int b = a + k; b <= D; ++b) ge |= bit(b);
                    for (int b = 1; b <= a - k; ++b) le |= bit(b);
                    v[a] &= ge;
                    w[a] &= le;
                }
                budget -= D;
            }
        if (bad) break;
        // arc consistency on label domains
        for (auto& e : pc) {
            const int r = e.first.first, s = e.first.second;
            const bool dist = r != s && sees(r, s);
            uint32_t nd = 0, ns = 0;
            for (uint32_t m = dom[r]; m; m &= m - 1) {
                const int a = lowdigit(m);
                uint32_t bs = e.second[a] & dom[s];
                if (dist) bs &= ~bit(a);
                if (bs) nd |= bit(a), ns |= bs;
            }
            if (nd != dom[r]) dom[r] = nd, ch = true;
            if (r != s && (ns & dom[s]) != dom[s]) dom[s] &= ns, ch = true;
            // equal labels: a relation allowing only equal digits joins them
            if (r != s && !dist && nd) {
                bool eq = true;
                for (uint32_t m = nd; m && eq; m &= m - 1) eq = (e.second[lowdigit(m)] & dom[s]) == bit(lowdigit(m));
                if (eq && unite(r, s)) ch = true, ++njoin;
            }
        }
        budget -= (pm_long)pc.size() * D;
        // houses: the labels of a house are its digits
        for (int g : fullh) {
            const auto& G = p.groups[g].cells;
            std::vector<int> L;
            for (int x : G) L.push_back(find(x));
            for (int d = 1; d <= D; ++d) {  // a digit only one label of the house can take
                int at = -1, n = 0;
                for (int r : L)
                    if (dom[r] & bit(d)) ++n, at = r;
                if (n == 0) bad = true;
                else if (n == 1 && dom[at] != bit(d)) dom[at] = bit(d), ch = true;
            }
            for (int r : L)  // naked: a label fixed to a digit
                if (popc(dom[r]) == 1)
                    for (int s : L)
                        if (s != r && (dom[s] & dom[r])) dom[s] &= ~dom[r], ch = true;
            // coverage with label relations: if r = a, every other digit still fits another label
            for (int r : L) {
                bool related = false;
                for (int s : L) related |= s != r && pc.count({r, s});
                if (!related) continue;
                uint32_t nd = dom[r];
                for (uint32_t m = dom[r]; m; m &= m - 1) {
                    const int a = lowdigit(m);
                    for (int d = 1; d <= D; ++d) {
                        if (d == a) continue;
                        bool cov = false;
                        for (int s : L) {
                            if (s == r || !(dom[s] & bit(d))) continue;
                            auto it = pc.find({r, s});
                            if (it == pc.end() || (it->second[a] & bit(d))) {
                                cov = true;
                                break;
                            }
                        }
                        if (!cov) {
                            nd &= ~bit(a);
                            break;
                        }
                    }
                }
                if (nd != dom[r]) dom[r] = nd, ch = true;
            }
            budget -= (pm_long)D * D * D;
        }
        if (bad) break;
        // hidden labels: a label missing from a house has one cell there it can be
        std::vector<std::pair<int, int>> J;
        for (int r = 0; r < N; ++r) {
            if (find(r) != r) continue;
            bool open = false;  // labels with an unsolved member (others are digits already)
            for (int w = 0; w < W && !open; ++w) {
                uint64_t m = mb[(size_t)r * W + w];
                while (m && !open) {
                    const int c = w * 64 + __builtin_ctzll(m);
                    open = !vals[c];
                    m &= m - 1;
                }
            }
            if (!open) continue;
            for (int g : fullh) {
                const auto& G = p.groups[g].cells;
                bool inside = false;
                for (int x : G) inside |= tbit(&mb[(size_t)r * W], x);
                if (inside) continue;
                int at = -1, n = 0;
                for (int x : G) {
                    const int s = find(x);
                    if (!(dom[s] & dom[r]) || sees(r, s)) continue;
                    ++n, at = s;
                    if (n > 1) break;
                }
                budget -= (pm_long)D * W;
                if (n == 0) bad = true;
                if (n == 1) J.push_back({r, at});
            }
        }
        if (bad) break;
        for (auto& j : J)
            if (unite(j.first, j.second)) ch = true, ++njoin;
        // labels -> cells
        for (int c = 0; c < N; ++c) {
            if (vals[c]) continue;
            const uint32_t x = wc[c] & dom[find(c)];
            if (x != wc[c]) wc[c] = x, ch = true;
            if (!x) bad = true;
        }
        if (bad) break;
        rounds = round;
        for (int c = 0; c < N && !found; ++c) found = !vals[c] && (wc[c] & cand[c]) != cand[c];
        if (!ch) break;
    }
    if (bad || !found) return;
    // the labels in play: those with >= 2 members
    std::vector<int> cnt(N, 0);
    for (int c = 0; c < N; ++c) ++cnt[find(c)];
    int ninv = 0;
    for (int r = 0; r < N; ++r) ninv += find(r) == r && cnt[r] >= 2;
    ninv = std::max(ninv, 1);
    std::vector<int> pcells;  // the eliminated cells' labels
    {
        std::vector<char> lab_used(N, 0);
        for (int c = 0; c < N; ++c)
            if (!vals[c] && (wc[c] & cand[c]) != cand[c]) lab_used[find(c)] = 1;
        for (int c = 0; c < N; ++c)
            if (lab_used[find(c)]) pcells.push_back(c);
    }
    Move& m = new_move(out, COLOUR_ALGEBRA, 1.0, std::min(N, (int)pcells.size()));
    for (int c = 0; c < N; ++c)
        if (!vals[c])
            for (uint32_t b = cand[c] & ~wc[c]; b; b &= b - 1) {
                out.elims.push_back((uint32_t)c * 32u + (uint32_t)lowdigit(b));
                ++m.el_n;
            }
    set_pattern(out, m, pcells);
    {
        std::vector<int> rec{0, 0, -1, -1, -1, (int)pcells.size()};
        for (int c : pcells) rec.push_back(c * 32);
        add_expl(out, m, EX_COLOR, rec);
    }
    m.has_meta = true;
    m.meta[0] = std::min(N, (int)pcells.size() + 2 * ninv);
    m.meta[1] = ninv;
    m.meta[2] = D;
    m.meta[3] = std::min(rounds, 12);
    m.meta[4] = 1;
    m.meta[5] = 0;
    m.meta[6] = 1;
    m.meta[7] = 1;
    m.spread = pspread(pcells);
    m.code = 3512;
    pm_long xm[XM_N] = {(pm_long)pcells.size(), D, (pm_long)m.el_n, 0, 0, 0, 0, 0, 0, 0};
    std::copy(xm, xm + XM_N, m.xm);
}

}  // namespace cs

namespace cs {

// Multi-colouring (sudokuwiki): two single-digit colour clusters of digit v (conjugate pairs).
// If colour a of cluster C sees colour b of cluster D (a v-cell of a and a v-cell of b are peers), a
// and b are not both true, so a' or b' (their opposites) is true: v leaves every cell seeing a cell of
// a' and a cell of b'. If a sees both colours of D, a is false (its v-cells lose v).
void Solver::multi_colouring(MoveBuf& out) {
    if (disabled[MULTI_COLOR]) return;
    const int N = p.N;
    for (int v = 1; v <= p.D; ++v) {
        const uint32_t b = bit(v);
        std::vector<std::vector<int>> adj(N);
        for (int hi : p.houses) {
            int n = 0, cs2[2] = {-1, -1};
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & b)) {
                    if (n < 2) cs2[n] = c;
                    ++n;
                }
            if (n == 2) {
                adj[cs2[0]].push_back(cs2[1]);
                adj[cs2[1]].push_back(cs2[0]);
            }
        }
        std::vector<int> comp(N, -1), col(N, 0);
        std::vector<std::array<std::vector<int>, 2>> cl;
        for (int s = 0; s < N; ++s) {
            if (comp[s] >= 0 || adj[s].empty()) continue;
            const int id = (int)cl.size();
            cl.push_back({});
            std::vector<int> st{s};
            comp[s] = id;
            bool odd = false;
            while (!st.empty()) {
                int x = st.back();
                st.pop_back();
                cl[id][col[x]].push_back(x);
                for (int y : adj[x]) {
                    if (comp[y] < 0) {
                        comp[y] = id;
                        col[y] = 1 - col[x];
                        st.push_back(y);
                    } else if (col[y] == col[x]) {
                        odd = true;
                    }
                }
            }
            if (odd) cl.back() = {};  // inconsistent: drop
        }
        auto sees_any = [&](int c, const std::vector<int>& S) {
            for (int x : S)
                if (x != c && tbit(p.peers(x), c)) return true;
            return false;
        };
        auto sees_set = [&](const std::vector<int>& A, const std::vector<int>& B) {
            for (int x : A)
                if (sees_any(x, B)) return true;
            return false;
        };
        const int K = (int)cl.size();
        for (int i = 0; i < K; ++i)
            for (int j = i + 1; j < K; ++j) {
                if (cl[i][0].empty() || cl[j][0].empty()) continue;
                if (cl[i][0].size() + cl[i][1].size() < 2 || cl[j][0].size() + cl[j][1].size() < 2) continue;
                for (int a = 0; a < 2; ++a)
                    for (int bb = 0; bb < 2; ++bb) {
                        if (!sees_set(cl[i][a], cl[j][bb])) continue;
                        const auto& A2 = cl[i][1 - a];
                        const auto& B2 = cl[j][1 - bb];
                        std::vector<uint32_t> el;
                        for (int c = 0; c < N; ++c) {
                            if (vals[c] || !(cand[c] & b) || comp[c] == i || comp[c] == j) continue;
                            if (sees_any(c, A2) && sees_any(c, B2)) el.push_back((uint32_t)c * 32u + v);
                        }
                        if (el.empty()) continue;
                        std::vector<int> pc;
                        for (int k2 = 0; k2 < 2; ++k2) {
                            pc.insert(pc.end(), cl[i][k2].begin(), cl[i][k2].end());
                            pc.insert(pc.end(), cl[j][k2].begin(), cl[j][k2].end());
                        }
                        std::sort(pc.begin(), pc.end());
                        Move& m = new_move(out, MULTI_COLOR, 1.0, (int)pc.size());
                        for (uint32_t e : el) {
                            out.elims.push_back(e);
                            ++m.el_n;
                        }
                        set_pattern(out, m, pc);
                        {   // colours: cluster i colour a / a', cluster j colour b / b' as two 2-colourings
                            std::vector<int> rec{v, 0, -1, -1, -1, (int)(A2.size() + B2.size())};
                            rec.insert(rec.end(), A2.begin(), A2.end());
                            rec.insert(rec.end(), B2.begin(), B2.end());
                            rec.insert(rec.end(), cl[i][a].begin(), cl[i][a].end());
                            rec.insert(rec.end(), cl[j][bb].begin(), cl[j][bb].end());
                            add_expl(out, m, EX_COLOR, rec);
                        }
                        const int n = (int)pc.size();
                        m.has_meta = true;
                        m.meta[0] = n;
                        m.meta[1] = n - 1;
                        m.meta[2] = 1;
                        m.meta[3] = std::min(n - 1, 12);  // links, capped: linear in the meta-theta exponent
                        m.meta[4] = 1;
                        m.meta[5] = 0;
                        m.meta[6] = 0;
                        m.meta[7] = 1;
                        m.spread = pspread(pc);
                        m.code = 3520;
                        pm_long xm[XM_N] = {v, n, (pm_long)el.size(), 0, 0, 0, 0, 0, 0, 0};
                        std::copy(xm, xm + XM_N, m.xm);
                    }
            }
    }
}

}  // namespace cs
