// Exhaustive search (brute_solve): solutions of a puzzle under every rule, for uniqueness and the generator.
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
#include "expr.hpp"
#include "solver.hpp"
#include "solver_util.hpp"

namespace cs {

// ---------------------------------------------------------- brute force --
namespace {
struct Brute {
    const Puzzle& p;
    int limit;
    pm_long node_limit;
    pm_long nodes = 0;
    std::vector<std::vector<int>> sols;
    std::vector<int> cages;
    std::vector<std::vector<uint8_t>> vs;
    std::vector<std::vector<uint32_t>> cs;

    // ---- regions to find (chaos, format 6.3): a region label 1..D per cell of a chaos area, beside its digit ----
    bool chaos_on = false;
    const std::vector<std::vector<int>>& areas;  // each chaos area's cells in reading order (Puzzle::finalize)
    const std::vector<int>& area_of;             // area index per cell, -1 outside every chaos area
    const std::vector<std::vector<int>>& nbr;    // orthogonal neighbours in the same area
    std::vector<std::vector<uint8_t>> ls;    // label per cell, per depth (0: not yet known)
    std::vector<std::vector<uint32_t>> lcs;  // label candidates (bits 1..D), per depth
    // ---- shading (yin-yang, format 6.19): a colour per cell beside its digit (0 unknown, 1 shaded, 2 unshaded) ----
    bool shade_on = false;
    std::vector<std::vector<uint8_t>> ss;  // colour per cell, per depth
    std::vector<int> layered;              // custom rules reading region() / shaded() (indices into p.nary)
    // one-cell rules reading shaded() ("even digits in a cage are shaded"): allowed digits per colour, so a colour
    // removes digits and digits that all imply one colour set it
    struct Coupling { int cell; uint32_t ok[3]; };  // ok[1]: digits allowed shaded, ok[2]: unshaded
    std::vector<Coupling> couplings;
    // ---- aux variables (the file's unknowns and layers): allowed flags per value, per depth ----
    bool aux_on = false;
    std::vector<int> aoff;                  // flag offset per aux variable (values in p.aux_values order)
    std::vector<std::vector<char>> as;      // flags per depth
    std::vector<int> aux_rules;             // custom rules reading aux variables (indices into p.nary)
    std::vector<char> aux_read_any;         // aux variable read by some rule
    std::vector<int> auxv;                  // scratch: value per aux variable (AUX_UNSET when open)

    Brute(const Puzzle& pz, int lim, pm_long nl)
        : p(pz), limit(lim), node_limit(nl), areas(pz.chaos), area_of(pz.chaos_of), nbr(pz.chaos_nbr) {
        for (int gi = 0; gi < p.G; ++gi)
            if (p.groups[gi].has_total) cages.push_back(gi);
        chaos_on = !p.chaos.empty();
        shade_on = p.shading;
        for (size_t ki = 0; ki < p.nary.size(); ++ki)
            if (p.nary[ki].type == NT_EXPR && !p.nary[ki].expr->aux_read.empty()) aux_rules.push_back((int)ki);
            else if (p.nary[ki].type == NT_EXPR && p.nary[ki].expr->layered) layered.push_back((int)ki);
        aux_on = !p.aux_values.empty();
        if (aux_on) {
            int off = 0;
            for (const auto& vals : p.aux_values) aoff.push_back(off), off += (int)vals.size();
            aoff.push_back(off);
            aux_read_any.assign(p.aux_values.size(), 0);
            for (int ki : aux_rules)
                for (int a : p.nary[ki].expr->aux_read) aux_read_any[a] = 1;
            auxv.assign(p.aux_values.size(), AUX_UNSET);
        }
        if (shade_on)
            for (int ki : layered) {
                const NConstraint& k = p.nary[ki];
                if (k.nv() != 1) continue;
                Coupling cp{k.vars[0], {0, 0, 0}};
                for (int col = 1; col <= 2; ++col)
                    for (int v = 1; v <= p.D; ++v) {
                        int dg = v, lb = 0, sd = col;
                        if (expr_holds(*k.expr, &dg, &lb, &sd)) cp.ok[col] |= bit(v);
                    }
                couplings.push_back(cp);
            }
    }
    // one-cell couplings between a cell's colour and its digit. false: contradiction
    bool couple(uint8_t* vals, uint32_t* cand, uint8_t* sh, bool& digits_changed) {
        for (const Coupling& cp : couplings) {
            const int c = cp.cell;
            const uint32_t m = vals[c] ? bit(vals[c]) : cand[c];
            if (sh[c]) {
                const uint32_t keep = m & cp.ok[sh[c]];
                if (!keep) return false;
                if (!vals[c] && keep != cand[c]) cand[c] = keep, digits_changed = true;
            } else {
                const bool can1 = (m & cp.ok[1]) != 0, can2 = (m & cp.ok[2]) != 0;
                if (!can1 && !can2) return false;
                if (can1 != can2) sh[c] = can1 ? 1 : 2;
            }
        }
        return true;
    }
    // shading propagation: no 2x2 of one colour (three of a colour force the fourth), each colour's known cells
    // connected through cells that may take it. false: contradiction
    bool shade_prop(uint8_t* sh) {
        for (bool again = true; again;) {
            again = false;
            for (const auto& w : p.windows4) {
                int n1 = 0, n2 = 0, unk = -1;
                for (int c : w) {
                    if (sh[c] == 1) ++n1;
                    else if (sh[c] == 2) ++n2;
                    else unk = c;
                }
                if (n1 == 4 || n2 == 4) return false;
                if (unk >= 0 && (n1 == 3 || n2 == 3)) sh[unk] = n1 == 3 ? 2 : 1, again = true;
            }
        }
        const int N = p.N;
        std::vector<char> seen(N);
        std::vector<int> stack;
        for (int col = 1; col <= 2; ++col) {
            int start = -1, total = 0;
            for (int c = 0; c < N; ++c)
                if (sh[c] == col) ++total, start = start < 0 ? c : start;
            if (start < 0) continue;
            std::fill(seen.begin(), seen.end(), 0);
            stack.assign(1, start);
            seen[start] = 1;
            int got = 0;
            while (!stack.empty()) {
                const int c = stack.back();
                stack.pop_back();
                got += sh[c] == col;
                for (int q : p.grid_nbr[c])
                    if (!seen[q] && sh[q] != 3 - col) seen[q] = 1, stack.push_back(q);
            }
            if (got < total) return false;
        }
        return true;
    }
    // custom rules reading region() / shaded(): each one whose cells' digits (and layers) are all known must hold
    bool layered_ok(const uint8_t* vals, const uint8_t* lab, const uint8_t* sh) {
        for (int ki : layered) {
            const NConstraint& k = p.nary[ki];
            int dg[64], lb[64], sd[64];
            bool ready = true;
            for (int i = 0; i < k.nv() && ready; ++i) {
                const int c = k.vars[i];
                dg[i] = vals[c], lb[i] = lab ? lab[c] : 0, sd[i] = sh ? sh[c] : 0;
                ready = dg[i] && (!sh || sd[i]) && (!lab || lb[i] || area_of[c] < 0);
            }
            if (ready && !expr_holds(*k.expr, dg, lab ? lb : nullptr, sh ? sd : nullptr)) return false;
        }
        return true;
    }
    int aux_count(const char* f, int a) const {
        int n = 0;
        for (int i = aoff[a]; i < aoff[a + 1]; ++i) n += f[i] != 0;
        return n;
    }
    // aux rules: once a rule's digits are fixed, its open aux values are tried (up to 4096 combinations): values no
    // combination supports are removed; a rule with no supported combination fails the node
    bool aux_prop(const uint8_t* vals, uint32_t* cand, char* f, bool& dch) {
        bool again = true;
        while (again) {
            again = false;
            for (size_t a = 0; a < p.aux_values.size(); ++a) {
                auxv[a] = AUX_UNSET;
                if (aux_count(f, (int)a) == 1)
                    for (int i = aoff[a]; i < aoff[a + 1]; ++i)
                        if (f[i]) auxv[a] = p.aux_values[a][i - aoff[a]];
                if (!aux_count(f, (int)a)) return false;
            }
            for (int ki : aux_rules) {
                const NConstraint& k = p.nary[ki];
                int dg[64];
                std::vector<int> fd;  // open digit cells of the rule (variable positions)
                for (int i = 0; i < k.nv(); ++i)
                    if (!(dg[i] = vals[k.vars[i]])) fd.push_back(i);
                if (fd.size() > 2) continue;  // read once at most two of its digits are open
                std::vector<int> fr;
                pm_long combos = 1;
                for (int i : fd) combos *= popc(cand[k.vars[i]]);
                for (int a : k.expr->aux_read)
                    if (auxv[a] == AUX_UNSET) fr.push_back(a), combos *= aux_count(f, a);
                if (combos > 4096) continue;
                std::vector<std::vector<char>> sup(fr.size());
                for (size_t j = 0; j < fr.size(); ++j) sup[j].assign(aoff[fr[j] + 1] - aoff[fr[j]], 0);
                std::vector<uint32_t> dsup(fd.size(), 0);
                bool any = false;
                std::vector<int> pick(fr.size(), 0);
                std::function<void(size_t)> go = [&](size_t j) {
                    if (j < fd.size()) {  // the open digits first
                        const int i = fd[j];
                        for (uint32_t m = cand[k.vars[i]]; m; m &= m - 1) {
                            dg[i] = lowdigit(m);
                            go(j + 1);
                        }
                        dg[i] = 0;
                        return;
                    }
                    const size_t q = j - fd.size();
                    if (q == fr.size()) {
                        if (expr_holds(*k.expr, dg, nullptr, nullptr, auxv.data())) {
                            any = true;
                            for (size_t t = 0; t < fr.size(); ++t) sup[t][pick[t]] = 1;
                            for (size_t t = 0; t < fd.size(); ++t) dsup[t] |= bit(dg[fd[t]]);
                        }
                        return;
                    }
                    const int a = fr[q];
                    for (int i = aoff[a]; i < aoff[a + 1]; ++i)
                        if (f[i]) {
                            pick[q] = i - aoff[a];
                            auxv[a] = p.aux_values[a][pick[q]];
                            go(j + 1);
                        }
                    auxv[a] = AUX_UNSET;
                };
                go(0);
                if (!any) return false;
                for (size_t j = 0; j < fr.size(); ++j)
                    for (int i = aoff[fr[j]]; i < aoff[fr[j] + 1]; ++i)
                        if (f[i] && !sup[j][i - aoff[fr[j]]]) f[i] = 0, again = true;
                for (size_t t = 0; t < fd.size(); ++t) {
                    const int c = k.vars[fd[t]];
                    if ((cand[c] & dsup[t]) != cand[c]) {
                        cand[c] &= dsup[t];
                        dch = true;
                        if (!cand[c]) return false;
                    }
                }
                if (again || dch) break;  // refresh the fixed values / propagate the digits again
            }
        }
        return true;
    }
    // label propagation: given borders, same-region sets, canonical labels (label k first appears before label k + 1,
    // reading order), each (label, digit) pair once, D cells per label, one connected region per label.
    // -1 contradiction, 1 something changed (labels or digit candidates), 0 nothing
    int chaos_prop(const uint8_t* vals, uint32_t* cand, uint8_t* lab, uint32_t* lc) {
        const int D = p.D;
        bool changed = false;
        auto lm = [&](int c) -> uint32_t { return lab[c] ? bit(lab[c]) : lc[c]; };
        auto keep = [&](int c, uint32_t k) -> bool {  // false: no label left
            if (lab[c]) return (bit(lab[c]) & k) != 0;
            const uint32_t n = lc[c] & k;
            if (!n) return false;
            if (n != lc[c]) {
                lc[c] = n;
                changed = true;
                if (!(n & (n - 1))) lab[c] = (uint8_t)lowdigit(n);
            }
            return true;
        };
        for (const auto& e : p.region_border) {
            const int a = e.first, b = e.second;
            if (lab[a] && lab[b] && lab[a] == lab[b]) return -1;
            if (lab[a] && !keep(b, ~bit(lab[a]))) return -1;
            if (lab[b] && !keep(a, ~bit(lab[b]))) return -1;
        }
        for (const auto& s : p.same_region) {
            uint32_t m = p.full;
            for (int c : s) m &= lm(c);
            if (!m) return -1;
            for (int c : s)
                if (!keep(c, m)) return -1;
        }
        std::vector<int> comp(p.N, -1), stack;
        for (const auto& A : areas) {
            int maxlab = 0;
            for (int c : A) {
                const uint32_t allow = maxlab + 1 >= 32 ? p.full : ((1u << (maxlab + 1)) - 1) & p.full;
                if (!keep(c, allow)) return -1;
                maxlab = std::max(maxlab, 32 - __builtin_clz(lm(c)));
            }
            for (int a : A) {
                if (!lab[a] || !vals[a]) continue;
                for (int b : A) {
                    if (b == a) continue;
                    if (vals[b] == vals[a]) {
                        if (lab[b] == lab[a]) return -1;
                        if (!keep(b, ~bit(lab[a]))) return -1;
                    } else if (lab[b] == lab[a] && !vals[b]) {
                        const uint32_t n = cand[b] & ~bit(vals[a]);
                        if (!n) return -1;
                        if (n != cand[b]) cand[b] = n, changed = true;
                    }
                }
            }
            for (int k = 1; k <= D; ++k) {
                const uint32_t kb = bit(k);
                int fixedn = 0, possn = 0;
                for (int c : A) {
                    if (lab[c] == k) ++fixedn;
                    if (lm(c) & kb) ++possn;
                }
                if (fixedn > D || possn < D) return -1;
                if (possn == D) {
                    for (int c : A)
                        if ((lm(c) & kb) && !keep(c, kb)) return -1;
                } else if (fixedn == D) {
                    for (int c : A)
                        if (lab[c] != k && !keep(c, ~kb)) return -1;
                }
                // connectivity: label k's region lies inside one component of the cells that may take k
                for (int c : A) comp[c] = -1;
                int ncomp = 0, fixed_comp = -1;
                std::vector<int> size_of, has_fixed;
                for (int s0 : A) {
                    if (comp[s0] >= 0 || !(lm(s0) & kb)) continue;
                    int sz = 0, fx = 0;
                    stack.assign(1, s0);
                    comp[s0] = ncomp;
                    while (!stack.empty()) {
                        const int c = stack.back();
                        stack.pop_back();
                        ++sz;
                        if (lab[c] == k) ++fx;
                        for (int q : nbr[c])
                            if (comp[q] < 0 && (lm(q) & kb)) comp[q] = ncomp, stack.push_back(q);
                    }
                    size_of.push_back(sz);
                    has_fixed.push_back(fx);
                    if (fx) {
                        if (fixed_comp >= 0) return -1;  // two separate pieces of one region
                        fixed_comp = ncomp;
                    }
                    ++ncomp;
                }
                for (int c : A) {
                    if (comp[c] < 0 || lab[c] == k) continue;
                    const bool out = fixed_comp >= 0 ? comp[c] != fixed_comp : size_of[comp[c]] < D;
                    if (out && !keep(c, ~kb)) return -1;
                }
                if (fixed_comp >= 0 && size_of[fixed_comp] < D) return -1;
            }
        }
        return changed ? 1 : 0;
    }
    // a complete labelling of every chaos area: D connected cells per label, each digit once per label, borders and
    // same-region sets kept
    bool chaos_valid(const uint8_t* vals, const uint8_t* lab) {
        const int D = p.D;
        for (const auto& e : p.region_border)
            if (lab[e.first] == lab[e.second]) return false;
        for (const auto& s : p.same_region)
            for (int c : s)
                if (lab[c] != lab[s[0]]) return false;
        std::vector<int> seen(p.N, 0), stack;
        for (const auto& A : areas) {
            for (int k = 1; k <= D; ++k) {
                uint32_t digits = 0;
                int n = 0, start = -1;
                for (int c : A)
                    if (lab[c] == k) {
                        ++n;
                        if (digits & bit(vals[c])) return false;
                        digits |= bit(vals[c]);
                        if (start < 0) start = c;
                    }
                if (n != D) return false;
                int reached = 0;
                stack.assign(1, start);
                seen[start] = k;
                while (!stack.empty()) {
                    const int c = stack.back();
                    stack.pop_back();
                    ++reached;
                    for (int q : nbr[c])
                        if (lab[q] == k && seen[q] != k) seen[q] = k, stack.push_back(q);
                }
                if (reached != D) return false;
            }
            for (int c : A)
                if (!lab[c]) return false;
        }
        return true;
    }
    void place(uint8_t* vals, uint32_t* cand, int c, int v) {
        vals[c] = (uint8_t)v;
        cand[c] = 0;
        uint32_t b = bit(v);
        for (int q : p.peer_list[c]) cand[q] &= ~b;
        const int D1 = p.D + 1;
        for (int j : p.rel_sorted_j[c]) cand[p.rel[c][j]] &= ~p.rel_out[c][(size_t)j * D1 + v];
    }
    bool rel_dead = false;
    // revise every empty cell against its relation partners; true if anything changed
    bool rel_arcs(const uint8_t* vals, uint32_t* cand) {
        bool changed = false;
        rel_dead = false;
        const int D1 = p.D + 1;
        for (int x = 0; x < p.N; ++x) {
            if (vals[x] || p.rel[x].empty()) continue;
            for (size_t j = 0; j < p.rel[x].size(); ++j) {
                int q = p.rel[x][j];
                uint32_t dq = vals[q] ? bit(vals[q]) : cand[q];
                const uint32_t* tin = &p.rel_in[x][j * D1];
                uint32_t allowed = 0;
                for (uint32_t m = dq; m; m &= m - 1) allowed |= ~tin[lowdigit(m)];
                if (cand[x] & ~allowed) {
                    cand[x] &= allowed;
                    changed = true;
                    if (!cand[x]) {
                        rel_dead = true;
                        return true;
                    }
                }
            }
        }
        return changed;
    }
    bool valid(const uint8_t* vals) {
        const int D1 = p.D + 1;
        for (int c = 0; c < p.N; ++c) {
            if (!vals[c] || !(p.domains[c] & bit(vals[c]))) return false;
            for (int q : p.peer_list[c])
                if (vals[q] == vals[c]) return false;
            for (size_t j = 0; j < p.rel[c].size(); ++j)
                if (p.rel_out[c][j * D1 + vals[c]] & bit(vals[p.rel[c][j]])) return false;
        }
        for (int gi = 0; gi < p.G; ++gi)
            if (p.groups[gi].has_total) {
                int s = 0;
                for (int c : p.groups[gi].cells) s += vals[c];
                if (s != p.groups[gi].total) return false;
            }
        uint32_t dom[64];
        static const std::vector<GacReq> noreq;
        for (const NConstraint& k : p.nary) {
            if (k.type == NT_CASES) continue;  // implied by the puzzle's rules (a fog / CAS lemma)
            if (k.bounds_only) {
                pm_long t = 0;
                if (k.part_sign.empty()) {
                    for (int x : k.vars) t += vals[x];
                } else {
                    for (size_t q = 0; q < k.parts.size(); ++q)
                        for (int x : k.parts[q]) t += k.part_sign[q] * vals[x];
                }
                if (t != k.total) return false;
                continue;
            }
            for (int i = 0; i < k.nv(); ++i) dom[i] = bit(vals[k.vars[i]]);
            GacOut o;
            nary_gac(k, dom, noreq, 1000, p.D, o);
            if (o.complete && !o.any) return false;
        }
        return true;
    }
    bool cages_ok(const uint8_t* vals) {
        for (int gi : cages) {
            const Group& g = p.groups[gi];
            int s = 0;
            bool full = true;
            for (int c : g.cells) {
                s += vals[c];
                if (!vals[c]) full = false;
            }
            if ((full && s != g.total) || (!full && s >= g.total)) return false;
        }
        return true;
    }
    // bounds consistency of a derived sum whose vars fall into parts of pairwise distinct cells: a part's
    // sum lies between its smallest / largest distinct digits (union of its candidates, placed digits fixed)
    static void part_bounds(const std::vector<int>& cells, const uint8_t* vals, const uint32_t* cand, int skip,
                            pm_long& lo, pm_long& hi) {
        uint32_t uni = 0, placed = 0;
        int free = 0;
        lo = hi = 0;
        for (int c : cells) {
            if (c == skip) continue;
            if (vals[c]) lo += vals[c], hi += vals[c], placed |= bit(vals[c]);
            else uni |= cand[c], ++free;
        }
        uni &= ~placed;
        if (popc(uni) < free) {  // inconsistent: per-cell bounds
            for (int c : cells)
                if (c != skip && !vals[c] && cand[c]) lo += __builtin_ctz(cand[c]) + 1, hi += 32 - __builtin_clz(cand[c]);
            return;
        }
        uint32_t m = uni;
        for (int i = 0; i < free; ++i) lo += lowdigit(m), m &= m - 1;
        m = uni;
        for (int i = 0; i < free; ++i) {
            const int top = 32 - __builtin_clz(m);
            hi += top;
            m &= ~bit(top);
        }
    }
    bool sum_bounds_prop(const NConstraint& k, const uint8_t* vals, uint32_t* cand, bool& again) {
        if (k.part.empty()) {
            pm_long lo = 0, hi = 0;
            for (int x : k.vars)
                if (vals[x]) lo += vals[x], hi += vals[x];
                else if (!cand[x]) return false;
                else lo += __builtin_ctz(cand[x]) + 1, hi += 32 - __builtin_clz(cand[x]);
            if (lo > k.total || hi < k.total) return false;
            for (int x : k.vars) {
                if (vals[x]) continue;
                const pm_long mn = __builtin_ctz(cand[x]) + 1, mx = 32 - __builtin_clz(cand[x]);
                uint32_t keep = 0;
                for (uint32_t m = cand[x]; m; m &= m - 1) {
                    const pm_long v = lowdigit(m);
                    if (lo - mn + v <= k.total && hi - mx + v >= k.total) keep |= bit((int)v);
                }
                if (!keep) return false;
                if (keep != cand[x]) cand[x] = keep, again = true;
            }
            return true;
        }
        const auto& parts = k.parts;
        const int np = (int)parts.size();
        pm_long plo_s[64], phi_s[64];
        std::vector<pm_long> plo_v, phi_v;
        pm_long* plo = plo_s;
        pm_long* phi = phi_s;
        if (np > 64) plo_v.resize(np), phi_v.resize(np), plo = plo_v.data(), phi = phi_v.data();
        // signed parts (outie cells subtracted): a part with sign -1 contributes [-hi, -lo]
        auto sg = [&](int q) { return k.part_sign.empty() ? 1 : k.part_sign[q]; };
        pm_long lo = 0, hi = 0;
        for (int q = 0; q < np; ++q) {
            plo[q] = phi[q] = 0;
            if (parts[q].empty()) continue;
            pm_long a, b;
            part_bounds(parts[q], vals, cand, -1, a, b);
            if (sg(q) > 0) plo[q] = a, phi[q] = b;
            else plo[q] = -b, phi[q] = -a;
            lo += plo[q], hi += phi[q];
        }
        if (lo > k.total || hi < k.total) return false;
        for (int q = 0; q < np; ++q)
            for (int x : parts[q]) {
                if (vals[x]) continue;
                pm_long a, b;
                part_bounds(parts[q], vals, cand, x, a, b);  // the part without x
                if (sg(q) < 0) std::swap(a, b), a = -a, b = -b;
                const pm_long olo = lo - plo[q] + a, ohi = hi - phi[q] + b;
                uint32_t keep = 0;
                for (uint32_t m = cand[x]; m; m &= m - 1) {
                    const pm_long v = sg(q) * (pm_long)lowdigit(m);
                    if (olo + v <= k.total && ohi + v >= k.total) keep |= bit(lowdigit(m));
                }
                if (!keep) return false;
                if (keep != cand[x]) cand[x] = keep, again = true;
            }
        return true;
    }
    bool limited = false;
    bool gac_memo = false;  // BandLogic sub-puzzles: skip unchanged rules (see rec)
    pm_long gac_budget = 20000;  // per-rule consistency budget per propagation (BandLogic: smaller)
    pm_long work = 0;            // rule-check work (cells checked), BandLogic accounting
    std::vector<std::vector<uint32_t>> memo_out;
    void rec(int depth) {
        ++nodes;
        if ((int)sols.size() >= limit) return;
        if (nodes > node_limit || ((nodes & 15) == 0 && deadline_passed())) {   // node budget or max_seconds
            limited = true;
            return;
        }
        uint8_t* vals = vs[depth].data();
        uint32_t* cand = cs[depth].data();
        const int N = p.N, D = p.D;
    top:
        bool changed = true;
        while (changed) {
            changed = false;
            for (int c = 0; c < N; ++c) {
                if (!vals[c]) {
                    if (!cand[c]) return;
                    if ((cand[c] & (cand[c] - 1)) == 0) {
                        place(vals, cand, c, 32 - __builtin_clz(cand[c]));
                        changed = true;
                    }
                }
            }
            for (int hi : p.houses) {
                const Group& g = p.groups[hi];
                // Python: for d in 1..D: pos = cells holding/allowing d; place if
                // exactly one empty. Bit-parallel: digits seen once and not
                // placed; after each placement the masks are recomputed and only
                // higher digits are considered, which is exactly the sequential
                // loop's view of the state.
                uint32_t once = 0, twice = 0, placedm = 0;
                auto scan = [&]() {
                    once = twice = placedm = 0;
                    for (int c : g.cells) {
                        uint32_t m = vals[c] ? bit(vals[c]) : cand[c];
                        twice |= once & m;
                        once |= m;
                        if (vals[c]) placedm |= m;
                    }
                };
                scan();
                if (once != p.full) return;
                uint32_t todo = once & ~twice & ~placedm;
                while (todo) {
                    int d = lowdigit(todo);
                    uint32_t b = bit(d);
                    int pc = -1;
                    for (int c : g.cells)
                        if (!vals[c] && (cand[c] & b)) {
                            pc = c;
                            break;
                        }
                    place(vals, cand, pc, d);
                    changed = true;
                    scan();
                    uint32_t higher = d >= 32 ? 0u : ~((1u << d) - 1);
                    todo = once & ~twice & ~placedm & higher;
                }
            }
            (void)D;
        }
        if (rel_arcs(vals, cand)) {  // pair relations: arc consistency (bounds along chains)
            if (rel_dead) return;
            goto top;
        }
        if (!cages.empty()) {
            if (!cages_ok(vals)) return;
            std::vector<int> emp, avail, others;
            for (int gi : cages) {
                const Group& g = p.groups[gi];
                emp.clear();
                int rem = g.total;
                uint32_t used = 0;
                for (int c : g.cells) {
                    if (!vals[c]) emp.push_back(c);
                    rem -= vals[c];
                    if (vals[c]) used |= bit(vals[c]);
                }
                if (emp.empty()) continue;
                int k = (int)emp.size();
                avail.clear();
                for (int d = 1; d <= D; ++d)
                    if (!(used & bit(d))) avail.push_back(d);
                if ((int)avail.size() < k) return;
                for (int c : emp) {
                    uint32_t keep = 0;
                    for (uint32_t dm = cand[c]; dm; dm &= dm - 1) {
                        int d = lowdigit(dm);
                        others.clear();
                        for (int x : avail)
                            if (x != d) others.push_back(x);
                        int m = (int)others.size(), t = k - 1;
                        int lo = 0, hi = 0;
                        for (int i = 0; i < std::min(t, m); ++i) lo += others[i];
                        if (k > 1)
                            for (int i = std::max(0, m - t); i < m; ++i) hi += others[i];
                        if (lo <= rem - d && rem - d <= hi) keep |= bit(d);
                    }
                    if (!keep) return;
                    cand[c] = keep;
                }
            }
        }
        if (!p.nary.empty()) {  // n-ary constraints: consistency propagation
            bool again = false;
            uint32_t dom[64];
            static const std::vector<GacReq> noreq;
            for (size_t ki = 0; ki < p.nary.size(); ++ki) {
                if (deadline_passed()) {     // max_seconds inside one node's propagation: give up (undecided)
                    limited = true;
                    return;
                }
                const NConstraint& k = p.nary[ki];
                if (k.type == NT_LINE || k.type == NT_SAMESET) continue;  // implied by pairs / houses
                if (k.type == NT_CASES) continue;  // a lemma implied by the puzzle's rules: the search does not need it
                if (gac_memo) {  // skip a rule whose domains equal its last propagated output (exact GAC is idempotent)
                    auto& mo = memo_out[ki];
                    bool same = (int)mo.size() == k.nv();
                    for (int i = 0; i < k.nv() && same; ++i)
                        same = mo[i] == (vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]]);
                    if (same) continue;
                }
                if (k.bounds_only) {  // derived sum (cells listed once): bounds over distinct parts
                    work += k.nv();
                    if (!sum_bounds_prop(k, vals, cand, again)) return;
                    continue;
                }
                if (!k.parts.empty()) {  // a sum with house-sharing parts: distinct-digit bounds per part first
                    work += k.nv();
                    if (!sum_bounds_prop(k, vals, cand, again)) return;
                }
                work += 4 * k.nv();
                for (int i = 0; i < k.nv(); ++i) dom[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                GacOut o;
                nary_gac_brute(k, dom, gac_budget, D, o);
                work += 8 * std::min(o.count, gac_budget);  // enumeration effort (assignments found)
                if (o.complete && !o.any) return;
                for (int i = 0; i < k.nv(); ++i) {
                    int x = k.vars[i];
                    if (vals[x]) {
                        if (!(o.sup[i] & bit(vals[x]))) return;
                        continue;
                    }
                    uint32_t nc = cand[x] & o.sup[i];
                    if (!nc) return;
                    if (nc != cand[x]) {
                        cand[x] = nc;
                        again = true;
                    }
                }
                if (gac_memo && o.complete) {
                    auto& mo = memo_out[ki];
                    mo.resize(k.nv());
                    for (int i = 0; i < k.nv(); ++i) mo[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : cand[k.vars[i]];
                }
            }
            if (again) goto top;
        }
        if (chaos_on) {  // regions to find
            const int r = chaos_prop(vals, cand, ls[depth].data(), lcs[depth].data());
            if (r < 0) return;
            if (r > 0) goto top;
        }
        if (shade_on) {
            bool dch = false;
            if (!couple(vals, cand, ss[depth].data(), dch) || !shade_prop(ss[depth].data())) return;
            if (dch) goto top;  // digits narrowed by colours: propagate the digits again
            bool dch2 = false;  // colours set by the shading rules can narrow digits in turn
            if (!couple(vals, cand, ss[depth].data(), dch2)) return;
            if (dch2) goto top;
        }
        if (!layered.empty() &&
            !layered_ok(vals, chaos_on ? ls[depth].data() : nullptr, shade_on ? ss[depth].data() : nullptr))
            return;
        if (aux_on) {
            bool dch = false;
            if (!aux_prop(vals, cand, as[depth].data(), dch)) return;
            if (dch) goto top;  // digits narrowed by aux rules: propagate the digits again
        }
        int c = -1, best = 1 << 30;
        for (int x = 0; x < N; ++x)
            if (!vals[x] && popc(cand[x]) < best) {
                best = popc(cand[x]);
                c = x;
            }
        int lcell = -1, lbest = 1 << 30;  // a region label to branch on when it has fewer options than any digit
        if (chaos_on) {
            const uint8_t* lab = ls[depth].data();
            const uint32_t* lc = lcs[depth].data();
            for (int x = 0; x < N; ++x)
                if (area_of[x] >= 0 && !lab[x] && popc(lc[x]) < lbest) lbest = popc(lc[x]), lcell = x;
        }
        int avar = -1, abest = 1 << 30;  // an aux variable still open (read by a rule), fewest values first
        if (aux_on)
            for (size_t a = 0; a < p.aux_values.size(); ++a)
                if (aux_read_any[a]) {
                    const int n = aux_count(as[depth].data(), (int)a);
                    if (n > 1 && n < abest) abest = n, avar = (int)a;
                }
        int scell = -1;  // a cell whose colour is still open (shading)
        if (shade_on)
            for (int x = 0; x < N && scell < 0; ++x)
                if (!ss[depth][x]) scell = x;
        if (c < 0 && lcell < 0 && scell < 0 && avar < 0) {
            if (!valid(vals)) return;  // a full grid must satisfy every rule
            if (chaos_on && !chaos_valid(vals, ls[depth].data())) return;
            if (shade_on) {  // both colours present (each is connected: shade_prop)
                bool s1 = false, s2 = false;
                for (int x = 0; x < N; ++x) s1 |= ss[depth][x] == 1, s2 |= ss[depth][x] == 2;
                if (!s1 || !s2) return;
            }
            if (chaos_on || shade_on || aux_on)  // another region layout / shading / aux values with the same digits
                for (const auto& s : sols)
                    if (std::equal(s.begin(), s.end(), vals)) return;
            sols.emplace_back(vals, vals + N);
            return;
        }
        if ((int)vs.size() <= depth + 1) {
            vs.emplace_back(N);
            cs.emplace_back(N);
            if (chaos_on) ls.emplace_back(N), lcs.emplace_back(N);
            if (shade_on) ss.emplace_back(N);
            if (aux_on) as.emplace_back(as[0].size());
        }
        auto copy_down = [&]() {
            std::copy(vs[depth].begin(), vs[depth].end(), vs[depth + 1].begin());
            std::copy(cs[depth].begin(), cs[depth].end(), cs[depth + 1].begin());
            if (chaos_on) {
                std::copy(ls[depth].begin(), ls[depth].end(), ls[depth + 1].begin());
                std::copy(lcs[depth].begin(), lcs[depth].end(), lcs[depth + 1].begin());
            }
            if (shade_on) std::copy(ss[depth].begin(), ss[depth].end(), ss[depth + 1].begin());
            if (aux_on) std::copy(as[depth].begin(), as[depth].end(), as[depth + 1].begin());
        };
        if (avar >= 0 && c < 0 && lcell < 0 && scell < 0) {  // digits fixed: one valid set of aux values is enough
            const size_t before = sols.size();
            for (int i = aoff[avar]; i < aoff[avar + 1]; ++i) {
                if (!as[depth][i]) continue;
                copy_down();
                for (int j = aoff[avar]; j < aoff[avar + 1]; ++j) as[depth + 1][j] = j == i;
                rec(depth + 1);
                if ((int)sols.size() >= limit || sols.size() > before) return;
            }
            return;
        }
        // a colour: once the digits are fixed (one valid shading is enough: the others repeat the same digits), or
        // earlier when custom rules read the shading and can prune digits with it
        if (scell >= 0 && lcell < 0 && (c < 0 || (!layered.empty() && best > 2))) {
            const size_t before = sols.size();
            for (uint8_t col = 1; col <= 2; ++col) {
                copy_down();
                ss[depth + 1][scell] = col;
                rec(depth + 1);
                if ((int)sols.size() >= limit || (c < 0 && sols.size() > before)) return;
            }
            return;
        }
        if (lcell >= 0 && (c < 0 || lbest < best)) {
            const uint32_t snapshot = lcs[depth][lcell];
            for (uint32_t m = snapshot; m; m &= m - 1) {
                copy_down();
                ls[depth + 1][lcell] = (uint8_t)lowdigit(m);
                lcs[depth + 1][lcell] = m & (~m + 1);
                rec(depth + 1);
                if ((int)sols.size() >= limit) return;
            }
            return;
        }
        uint32_t snapshot = cand[c];
        for (uint32_t dm = snapshot; dm; dm &= dm - 1) {
            int v = lowdigit(dm);
            copy_down();
            place(vs[depth + 1].data(), cs[depth + 1].data(), c, v);
            rec(depth + 1);
            if ((int)sols.size() >= limit) return;
        }
    }
};
}  // namespace

std::vector<std::vector<int>> brute_solve(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, int limit,
                                          pm_long node_limit, const std::vector<uint8_t>* start_vals,
                                          const std::vector<uint32_t>* start_cand, bool* complete, pm_long* nodes_out,
                                          bool memo) {
    Brute b(p, limit, node_limit);
    b.gac_memo = memo;
    if (memo) b.memo_out.assign(p.nary.size(), {}), b.gac_budget = 1500;
    b.vs.emplace_back(p.N);
    b.cs.emplace_back(p.N);
    if (b.shade_on) b.ss.emplace_back(p.shade_given);
    if (b.aux_on) {  // every value allowed, a given value alone
        b.as.emplace_back(b.aoff.back(), 1);
        for (size_t a = 0; a < p.aux_values.size(); ++a)
            if (p.aux_given[a] != AUX_UNSET)
                for (int i = b.aoff[a]; i < b.aoff[a + 1]; ++i) b.as[0][i] = p.aux_values[a][i - b.aoff[a]] == p.aux_given[a];
    }
    if (b.chaos_on) {
        b.ls.emplace_back(p.N, 0);
        b.lcs.emplace_back(p.N, 0);
        for (int c = 0; c < p.N; ++c)
            if (b.area_of[c] >= 0) b.lcs[0][c] = p.full;
    }
    if (start_vals) {
        b.vs[0] = *start_vals;
        b.cs[0] = *start_cand;
    } else {
        std::fill(b.vs[0].begin(), b.vs[0].end(), 0);
        b.cs[0] = p.domains;
        for (auto& cv : givens) b.place(b.vs[0].data(), b.cs[0].data(), cv.first, cv.second);
    }
    b.rec(0);
    if (complete) *complete = !(b.limited && (int)b.sols.size() < limit);
    if (nodes_out) *nodes_out = b.nodes;  // (b.work: rule-check effort)
    return b.sols;
}

}  // namespace cs
