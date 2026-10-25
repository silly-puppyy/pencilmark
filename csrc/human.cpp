// Cheap, named human moves (CTC vocabulary), each a relaxation of a stronger engine technique:
//   SumBound (72): min / max ("triangular number") bounds of sum rules: cages, sums, arrows;
//   ClassCount (73): odd / even (and low / middle / high) counting in houses, sum parity;
//   Domino (74): pair-cell reasoning on relation dominoes (kropki, XV, difference, ...): a digit
//     every allowed pair uses leaves the dominoes' common houses; two dominoes of a house whose
//     allowed fillings use exactly four digits lock them.
#include <cstdlib>
#include "portable.hpp"
#include <algorithm>
#include <cmath>
#include <array>
#include <functional>
#include <set>

#include "solver.hpp"

namespace cs {

namespace {
inline void add_el(MoveBuf& b, Move& m, int c, int v) {
    b.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
    ++m.el_n;
}
inline void meta8(Move& m, int a, int b, int c, int d, int e, int f, int g, int h, double sp) {
    m.has_meta = true;
    m.meta[0] = a; m.meta[1] = b; m.meta[2] = c; m.meta[3] = d;
    m.meta[4] = e; m.meta[5] = f; m.meta[6] = g; m.meta[7] = h;
    m.spread = sp;
}
inline int dmin(uint32_t m) { return m ? __builtin_ctz(m) + 1 : 0; }
inline int dmax(uint32_t m) { return m ? 32 - __builtin_clz(m) : 0; }
}  // namespace

// ------------------------------------------------------------ SumBound --
void Solver::sum_bound(MoveBuf& out) {
    if (disabled[SUM_BOUND]) return;
    const int D = p.D;
    auto run = [&](const NConstraint& k) {
        // linear form sum_i w_i x_i = T over positions; arrows: circle (one digit) = line
        std::vector<int> pos_var, w;
        int T = 0;
        bool distinct = false;
        if (k.type == NT_SUM && !k.totals.empty()) {
            return;  // incomplete clue (unknown total): left to the consistency engine
        } else if (k.type == NT_SUM) {
            for (int v : k.pvar) {
                pos_var.push_back(v);
                w.push_back(1);
            }
            T = k.total;
            distinct = k.distinct;
        } else if (k.type == NT_ARROW && k.ncircle == 1) {
            for (size_t i = 0; i < k.pvar.size(); ++i) {
                pos_var.push_back(k.pvar[i]);
                w.push_back(i == 0 ? -1 : 1);
            }
            T = 0;
        } else {
            return;
        }
        const int n = (int)pos_var.size();
        if (n < 2) return;
        std::vector<uint32_t> dom(n);
        bool any_empty = false;
        for (int i = 0; i < n; ++i) {
            int c = k.vars[pos_var[i]];
            dom[i] = vals[c] ? bit(vals[c]) : cand[c];
            any_empty |= !vals[c];
        }
        if (!any_empty) return;
        // bounds of the rest: per position min / max; distinct sums also by the triangular
        // bound over the digits still available to the empty positions
        auto rest_bounds = [&](int skip, int& lo, int& hi, bool& tri_used) {
            lo = hi = 0;
            tri_used = false;
            int plo = 0, phi = 0, m = 0;
            uint32_t pool = 0, used = 0;
            for (int j = 0; j < n; ++j) {
                if (j == skip) continue;
                if (w[j] > 0) {
                    plo += dmin(dom[j]);
                    phi += dmax(dom[j]);
                } else {
                    plo -= dmax(dom[j]);
                    phi -= dmin(dom[j]);
                }
                const int c = k.vars[pos_var[j]];
                if (vals[c]) used |= bit(vals[c]);
                else {
                    pool |= dom[j];
                    ++m;
                }
            }
            lo = plo;
            hi = phi;
            if (distinct && m > 1) {
                int fixed = 0;
                for (int j = 0; j < n; ++j)
                    if (j != skip && vals[k.vars[pos_var[j]]]) fixed += vals[k.vars[pos_var[j]]];
                pool &= ~used;
                if (popc(pool) < m) return;
                int tlo = fixed, thi = fixed, t = 0;
                for (int d = 1; d <= D && t < m; ++d)
                    if (pool & bit(d)) tlo += d, ++t;
                t = 0;
                for (int d = D; d >= 1 && t < m; --d)
                    if (pool & bit(d)) thi += d, ++t;
                if (tlo > lo) lo = tlo, tri_used = true;
                if (thi < hi) hi = thi, tri_used = true;
            }
            // a sum whose digits may repeat (little killer): cells sharing a house differ -> triangular bounds per
            // such part ("its three cells in box 5 add up to at least 1+2+3")
            if (!distinct && k.type == NT_SUM && !k.parts.empty() && (int)k.part.size() == k.nv()) {
                const int np = (int)k.parts.size();
                std::vector<uint32_t> ppool(np, 0), pused(np, 0);
                std::vector<int> pm(np, 0), pfix(np, 0);
                for (int j = 0; j < n; ++j) {
                    if (j == skip) continue;
                    const int q = k.part[pos_var[j]];
                    const int c = k.vars[pos_var[j]];
                    if (vals[c]) pused[q] |= bit(vals[c]), pfix[q] += vals[c];
                    else ppool[q] |= dom[j], ++pm[q];
                }
                int tlo = 0, thi = 0;
                bool ok = true;
                for (int q = 0; q < np && ok; ++q) {
                    const uint32_t pl = ppool[q] & ~pused[q];
                    if (popc(pl) < pm[q]) { ok = false; break; }
                    int a = pfix[q], b = pfix[q], t = 0;
                    for (int d = 1; d <= D && t < pm[q]; ++d)
                        if (pl & bit(d)) a += d, ++t;
                    t = 0;
                    for (int d = D; d >= 1 && t < pm[q]; --d)
                        if (pl & bit(d)) b += d, ++t;
                    tlo += a, thi += b;
                }
                if (ok) {
                    if (tlo > lo) lo = tlo, tri_used = true;
                    if (thi < hi) hi = thi, tri_used = true;
                }
            }
        };
        for (int i = 0; i < n; ++i) {
            const int c = k.vars[pos_var[i]];
            if (vals[c]) continue;
            int lo, hi;
            bool tri;
            rest_bounds(i, lo, hi, tri);
            // w_i x_i = T - rest  ->  rest in [lo, hi]
            int xlo, xhi;
            if (w[i] > 0) xlo = T - hi, xhi = T - lo;
            else xlo = lo - T, xhi = hi - T;
            uint32_t bad = 0;
            for (uint32_t mm = cand[c]; mm; mm &= mm - 1) {
                int d = lowdigit(mm);
                if (d < xlo || d > xhi) bad |= bit(d);
            }
            if (!bad) continue;
            Move& m = new_move(out, SUM_BOUND, k.shape, n);
            for (uint32_t b2 = bad; b2; b2 &= b2 - 1) add_el(out, m, c, lowdigit(b2));
            std::vector<int> pc;
            for (int v : k.vars)
                if (!vals[v]) pc.push_back(v);
            set_pattern(out, m, pc);
            m.nk = NM_NARY;
            m.na = k.index;
            m.nb = k.group;
            meta8(m, (int)pc.size(), 1, popc(bad), 0, 0, 1, 0, 1, k.shape);
            m.code = 3701 + (tri ? 1 : 0) + (k.type == NT_ARROW ? 2 : 0);
            pm_long xm[XM_N] = {xlo, xhi, tri, n, (pm_long)k.type, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    };
    for (const NConstraint& k : p.cage_nary) run(k);
    for (const NConstraint& k : p.nary) run(k);
    // renban span: a consecutive set of L cells spans L-1 -> every digit lies within L-1 of every other
    // cell's lowest / highest possible digit (the "1 and 9 never together" rule)
    for (const NConstraint& k : p.nary) {
        if (k.type != NT_SET || k.setkind != 0) continue;
        const int L = k.nv();
        if (L < 2 || L >= D) continue;
        int maxlo = 0, minhi = 99;
        for (int c : k.vars) {
            const uint32_t d = vals[c] ? bit(vals[c]) : cand[c];
            maxlo = std::max(maxlo, dmin(d));
            minhi = std::min(minhi, dmax(d));
        }
        const int lo = maxlo - (L - 1), hi = minhi + (L - 1);
        for (int c : k.vars) {
            if (vals[c]) continue;
            uint32_t bad = 0;
            for (uint32_t mm = cand[c]; mm; mm &= mm - 1) {
                const int d = lowdigit(mm);
                if (d < lo || d > hi) bad |= bit(d);
            }
            if (!bad) continue;
            Move& m = new_move(out, SUM_BOUND, k.shape, L);
            for (uint32_t b2 = bad; b2; b2 &= b2 - 1) add_el(out, m, c, lowdigit(b2));
            std::vector<int> pc;
            for (int v : k.vars)
                if (!vals[v]) pc.push_back(v);
            set_pattern(out, m, pc);
            m.nk = NM_NARY;
            m.na = k.index;
            meta8(m, (int)pc.size(), 1, popc(bad), 0, 0, 1, 0, 1, k.shape);
            m.code = 3705;
            pm_long xm[XM_N] = {lo, hi, 0, L, (pm_long)k.type, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

// ----------------------------------------------------------- ClassCount --
void Solver::class_count(MoveBuf& out) {
    if (disabled[CLASS_COUNT]) return;
    const int D = p.D;
    // classes: odd / even; low / middle / high thirds when D % 3 == 0
    std::vector<std::pair<uint32_t, int>> classes;  // mask, kind (0 parity, 1 thirds)
    uint32_t odd = 0;
    for (int d = 1; d <= D; d += 2) odd |= bit(d);
    classes.push_back({odd, 0});
    classes.push_back({p.full & ~odd, 0});
    if (D % 3 == 0 && D >= 6) {
        const int t = D / 3;
        for (int s = 0; s < 3; ++s) {
            uint32_t m = 0;
            for (int d = s * t + 1; d <= (s + 1) * t; ++d) m |= bit(d);
            classes.push_back({m, 1});
        }
    }
    // digit classes only mean something when some rule looks at digit values (sums, relations,
    // lines): on a pure AllDiff puzzle any relabelling is a symmetry, so class counting is off
    bool value_rules = p.has_cages;
    for (int c = 0; c < p.N && !value_rules; ++c) value_rules = !p.rel[c].empty();
    // arithmetic rules only: tables / digit sets are digit-relabelling equivariant, parity / size classes
    // mean nothing for them (and would make the grade depend on the digit names)
    for (const NConstraint& k : p.nary) value_rules |= k.type != NT_SAMESET && k.type != NT_TABLE && k.type != NT_DIGITSET;
    // 2026-10-24 experiment (CSOLVER_TABLE_CLASSES=1): tables written from digit VALUES (sum < 10, product 8, parity checkerboards)
    // are not relabelling-equivariant; humans count parity / size classes on them (battenburg, makodoku, answer-8)
    static const bool table_classes = getenv("CSOLVER_TABLE_CLASSES") && getenv("CSOLVER_TABLE_CLASSES")[0] == '1';
    if (table_classes)
        for (const NConstraint& k : p.nary) value_rules |= k.type == NT_TABLE;
    if (!value_rules) return;
    // (a) a house holds exactly popc(X) digits of class X
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        if ((int)g.cells.size() != D) continue;
        for (auto& cl : classes) {
            const uint32_t X = cl.first;
            int placed = popc(placed_g[hi] & X), forced = 0;
            std::vector<int> fc, rest;
            for (int c : g.cells) {
                if (vals[c]) continue;
                if (!(cand[c] & ~X)) {
                    ++forced;
                    fc.push_back(c);
                } else if (cand[c] & X) {
                    rest.push_back(c);
                }
            }
            if (rest.empty() || placed + forced != popc(X) || forced == 0) continue;
            if (forced <= 1) continue;  // a single cell: naked / hidden singles' business
            Move& m = new_move(out, CLASS_COUNT, g.shape, forced);
            for (int c : rest)
                for (uint32_t b = cand[c] & X; b; b &= b - 1) add_el(out, m, c, lowdigit(b));
            set_pattern(out, m, fc);
            m.nk = NM_GROUP;
            m.na = hi;
            meta8(m, (int)fc.size() + (int)rest.size(), 1, popc(X), 0, 0, 0, 0, 1, g.shape);
            m.code = 3801 + 2 * cl.second;
            pm_long xm[XM_N] = {cl.second, (pm_long)X, placed, forced, (pm_long)rest.size(), 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
    // (b) sum parity: the parities of a sum rule's digits add up to its total's parity
    auto sum_par = [&](const NConstraint& k) {
        if (k.type != NT_SUM || !k.totals.empty()) return;
        int unknown = -1, nunk = 0, par = k.total & 1;
        for (int v : k.pvar) {
            const int c = k.vars[v];
            if (vals[c]) {
                par ^= vals[c] & 1;
                continue;
            }
            if (!(cand[c] & ~odd)) par ^= 1;
            else if (cand[c] & odd) {
                if (unknown != c) ++nunk;
                unknown = c;
            }
        }
        if (nunk != 1) return;
        // unknown must have parity `par`
        const uint32_t bad = cand[unknown] & (par ? ~odd : odd) & p.full;
        if (!bad) return;
        Move& m = new_move(out, CLASS_COUNT, k.shape, (int)k.pvar.size());
        for (uint32_t b = bad; b; b &= b - 1) add_el(out, m, unknown, lowdigit(b));
        std::vector<int> pc;
        for (int v : k.vars)
            if (!vals[v]) pc.push_back(v);
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.na = k.index;
        m.nb = k.group;
        meta8(m, (int)pc.size(), 1, 2, 0, 0, 1, 0, 1, k.shape);
        m.code = 3802;
        pm_long xm[XM_N] = {2, (pm_long)odd, k.total, (pm_long)k.pvar.size(), 1, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    for (const NConstraint& k : p.cage_nary) sum_par(k);
    for (const NConstraint& k : p.nary) sum_par(k);
    // (c) rule of parity: an innie / outie region (rule of 45) has a known total -> its digits'
    // parities add up to the total's parity
    auto region_par = [&](const InnieSet& is) {
        int unknown = -1, nunk = 0, par = ((is.total % 2) + 2) % 2;
        for (int c : is.cells) {
            if (vals[c]) {
                par ^= vals[c] & 1;
                continue;
            }
            if (!(cand[c] & ~odd)) par ^= 1;
            else if (cand[c] & odd) {
                ++nunk;
                unknown = c;
            }
        }
        if (nunk != 1) return;
        const uint32_t bad = cand[unknown] & (par ? ~odd : odd) & p.full;
        if (!bad) return;
        Move& m = new_move(out, CLASS_COUNT, p.groups[is.hi].shape, (int)is.cells.size());
        for (uint32_t b = bad; b; b &= b - 1) add_el(out, m, unknown, lowdigit(b));
        std::vector<int> pc;
        for (int c : is.cells)
            if (!vals[c]) pc.push_back(c);
        set_pattern(out, m, pc);
        m.nk = is.outie ? NM_OUTIE : NM_INNIE;
        m.na = is.hi;
        {
            std::vector<int> r{is.total, is.outie ? 1 : 0, (int)is.houses.size()};
            r.insert(r.end(), is.houses.begin(), is.houses.end());
            r.push_back((int)is.cages.size());
            r.insert(r.end(), is.cages.begin(), is.cages.end());
            r.insert(r.end(), is.cells.begin(), is.cells.end());
            add_expl(out, m, EX_REGION, r);
        }
        meta8(m, (int)is.cells.size(), (int)is.cages.size() + 1, 2, 0, 0, 1, 0, 1, p.groups[is.hi].shape);
        m.code = 3804;
        pm_long xm[XM_N] = {3, (pm_long)odd, is.total, (pm_long)is.cells.size(), 1, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    for (const InnieSet& is : p.innies) region_par(is);
    for (const InnieSet& is : p.big_innies) region_par(is);
}

// --------------------------------------------------------------- Domino --
void Solver::domino(MoveBuf& out) {
    if (disabled[DOMINO]) return;
    const int D1 = p.D + 1;
    struct Dom { int a, b; uint32_t must, digits; std::vector<std::pair<int, int>> pairs; };
    std::vector<Dom> doms;
    for (int a = 0; a < p.N; ++a) {
        if (vals[a]) continue;
        for (size_t j = 0; j < p.rel[a].size(); ++j) {
            const int b = p.rel[a][j];
            if (b < a || vals[b]) continue;
            const bool same = tbit(p.peers(a), b);
            Dom d{a, b, p.full, 0, {}};
            for (uint32_t ma = cand[a]; ma; ma &= ma - 1) {
                const int x = lowdigit(ma);
                for (uint32_t mb = cand[b] & ~p.rel_out[a][j * D1 + x]; mb; mb &= mb - 1) {
                    const int y = lowdigit(mb);
                    if (same && x == y) continue;
                    d.pairs.push_back({x, y});
                    d.must &= bit(x) | bit(y);
                    d.digits |= bit(x) | bit(y);
                }
            }
            if (d.pairs.empty()) continue;
            doms.push_back(d);
        }
    }
    // 2026-10-24 experiment (CSOLVER_TABLE_DOMINO=1): 2-cell table rules are dominoes too (quotient / product / answer-8 clues are
    // written as tables; humans read them as digit pairs: "a quotient >= 5 contains a 1"). Allowed pairs = the table rows.
    static const bool table_domino = getenv("CSOLVER_TABLE_DOMINO") && getenv("CSOLVER_TABLE_DOMINO")[0] == '1';
    if (table_domino)
        for (const NConstraint& k : p.nary) {
            if (k.type != NT_TABLE || k.nv() != 2 || k.arity != 2) continue;
            const int a = k.vars[k.pvar[0]], b = k.vars[k.pvar[1]];
            if (vals[a] || vals[b]) continue;
            const bool same = tbit(p.peers(a), b);
            Dom d{a, b, p.full, 0, {}};
            for (size_t r = 0; r + 1 < k.rows.size(); r += 2) {
                const int x = k.rows[r], y = k.rows[r + 1];
                if (x < 1 || y < 1 || x > p.D || y > p.D || !(cand[a] & bit(x)) || !(cand[b] & bit(y)) || (same && x == y)) continue;
                d.pairs.push_back({x, y});
                d.must &= bit(x) | bit(y);
                d.digits |= bit(x) | bit(y);
            }
            if (!d.pairs.empty()) doms.push_back(d);
        }
    std::vector<int> gs;
    auto common_houses = [&](const std::vector<int>& cells, std::vector<int>& outg) {
        outg.clear();
        for (int gi : p.groups_of[cells[0]]) {
            if (!p.groups[gi].complete) continue;
            bool all = true;
            for (int c : cells) all &= tbit(p.gbits(gi), c);
            if (all) outg.push_back(gi);
        }
    };
    // (i) a digit every allowed filling uses (the two cells see each other: it is in the pair)
    for (const Dom& d : doms) {
        if (!d.must) continue;
        common_houses({d.a, d.b}, gs);
        for (uint32_t mm = d.must; mm; mm &= mm - 1) {
            const int v = lowdigit(mm);
            std::vector<uint32_t> el;  // cells seeing both domino cells
            for (int c : p.peer_list[d.a])
                if (c != d.b && !vals[c] && (cand[c] & bit(v)) && tbit(p.peers(d.b), c))
                    el.push_back((uint32_t)c * 32u + v);
            if (el.empty()) continue;
            Move& m = new_move(out, DOMINO, 1.0, 1);
            for (uint32_t e : el) add_el(out, m, (int)(e / 32), (int)(e % 32));
            set_pattern(out, m, {d.a, d.b});
            add_expl(out, m, EX_BASE, gs);
            add_expl(out, m, EX_DOMINO, {d.a, d.b});
            meta8(m, 2, (int)gs.size() + 1, popc(d.digits), 1, 0, 0, 1, 1, pspread({d.a, d.b}));
            m.code = 3901;
            pm_long xm[XM_N] = {1, v, d.a, d.b, (pm_long)d.pairs.size(), 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
    // (iii) kropki black-dot chains: a cell with two black-dot (ratio 2) partners that see each other
    // (so differ) takes the middle of a 1-2-4 / 2-4-8 / 3-6-12 run: its digit needs both v/2 and 2v
    {
        auto is_black = [&](int a, size_t j) {
            for (int v = 1; v <= p.D; ++v) {
                uint32_t allowed = p.full & ~p.rel_out[a][j * D1 + v], want = 0;
                if (v % 2 == 0) want |= bit(v / 2);
                if (2 * v <= p.D) want |= bit(2 * v);
                if (allowed != want) return false;
            }
            return true;
        };
        for (int b = 0; b < p.N; ++b) {
            if (vals[b]) continue;
            std::vector<int> bl;
            for (size_t j = 0; j < p.rel[b].size(); ++j)
                if (is_black(b, j)) bl.push_back(p.rel[b][j]);
            for (size_t i = 0; i < bl.size(); ++i)
                for (size_t k = i + 1; k < bl.size(); ++k) {
                    const int a = bl[i], c = bl[k];
                    if (!tbit(p.peers(a), c)) continue;
                    uint32_t bad = 0;
                    for (uint32_t m = cand[b]; m; m &= m - 1) {
                        const int v = lowdigit(m);
                        if (v % 2 || 2 * v > p.D) bad |= bit(v);  // needs both neighbours v/2 and 2v
                    }
                    if (!bad) continue;
                    Move& m = new_move(out, DOMINO, 1.0, 3);
                    for (uint32_t x = bad; x; x &= x - 1) add_el(out, m, b, lowdigit(x));
                    std::vector<int> pc{a, b, c};
                    set_pattern(out, m, pc);
                    add_expl(out, m, EX_DOMINO, {a, b, b, c});
                    meta8(m, 3, 2, popc(cand[b]), 2, 0, 0, 1, 1, pspread(pc));
                    m.code = 3903;
                    pm_long xm[XM_N] = {2, (pm_long)bad, a, c, 0, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                }
        }
    }
    // (iv) middle squeeze (whisper 4/6, kropki / XV runs, ...): a cell with two relation partners
    // that see each other needs, for its digit v, two DIFFERENT allowed partner digits
    for (int b = 0; b < p.N; ++b) {
        if (vals[b] || p.rel[b].size() < 2) continue;
        for (size_t i = 0; i < p.rel[b].size(); ++i)
            for (size_t k = i + 1; k < p.rel[b].size(); ++k) {
                const int a = p.rel[b][i], c = p.rel[b][k];
                if (!tbit(p.peers(a), c)) continue;
                const uint32_t da = vals[a] ? bit(vals[a]) : cand[a], dc = vals[c] ? bit(vals[c]) : cand[c];
                uint32_t bad = 0;
                for (uint32_t m = cand[b]; m; m &= m - 1) {
                    const int v = lowdigit(m);
                    const uint32_t A = da & ~p.rel_out[b][i * D1 + v], C = dc & ~p.rel_out[b][k * D1 + v];
                    if (!A || !C) continue;  // plain pair arc (PairArc / relation moves)
                    if (popc(A | C) < 2) bad |= bit(v);
                }
                if (!bad) continue;
                Move& m = new_move(out, DOMINO, 1.0, 3);
                for (uint32_t x = bad; x; x &= x - 1) add_el(out, m, b, lowdigit(x));
                std::vector<int> pc{a, b, c};
                set_pattern(out, m, pc);
                add_expl(out, m, EX_DOMINO, {a, b, b, c});
                meta8(m, 3, 2, popc(cand[b]), 2, 0, 0, 1, 1, pspread(pc));
                m.code = 3904;
                pm_long xm[XM_N] = {2, (pm_long)bad, a, c, 0, 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
            }
    }
    // (ii) two disjoint dominoes of one house: their joint fillings use exactly 4 digits
    for (size_t i = 0; i < doms.size(); ++i)
        for (size_t k = i + 1; k < doms.size(); ++k) {
            const Dom &A = doms[i], &B = doms[k];
            if (A.a == B.a || A.a == B.b || A.b == B.a || A.b == B.b) continue;
            if (popc(A.digits | B.digits) > 6) continue;
            common_houses({A.a, A.b, B.a, B.b}, gs);
            if (gs.empty()) continue;
            uint32_t U = 0;
            for (auto& pa : A.pairs)
                for (auto& pb : B.pairs) {
                    const uint32_t m4 = bit(pa.first) | bit(pa.second) | bit(pb.first) | bit(pb.second);
                    if (popc(m4) == 4) U |= m4;
                }
            if (popc(U) != 4) continue;
            std::vector<uint32_t> el;
            for (int gi : gs)
                for (int c : p.groups[gi].cells)
                    if (c != A.a && c != A.b && c != B.a && c != B.b && !vals[c])
                        for (uint32_t b = cand[c] & U; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            for (int c : {A.a, A.b, B.a, B.b})
                for (uint32_t b = cand[c] & ~U; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            std::sort(el.begin(), el.end());
            el.erase(std::unique(el.begin(), el.end()), el.end());
            if (el.empty()) continue;
            Move& m = new_move(out, DOMINO, 1.0, 2);
            for (uint32_t e : el) add_el(out, m, (int)(e / 32), (int)(e % 32));
            std::vector<int> pc{A.a, A.b, B.a, B.b};
            set_pattern(out, m, pc);
            add_expl(out, m, EX_BASE, gs);
            add_expl(out, m, EX_DOMINO, pc);
            meta8(m, 4, (int)gs.size() + 2, 4, 2, 0, 0, 1, 1, pspread(pc));
            m.code = 3902;
            pm_long xm[XM_N] = {2, (pm_long)U, A.a, B.a, (pm_long)(A.pairs.size() * B.pairs.size()), 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
}

}  // namespace cs

namespace cs {

// Combination-aware positions (tech 95, CTC 'no 16-cage combination holds both 8 and 9, so the other one is
// outside the cage in this row'). For a sum cage K meeting a complete house H and a digit set Q (2-3 digits
// still missing in H): m(Q) = the most digits of Q any valid filling of K puts into K n H. At least |Q| - m(Q)
// digits of Q then lie in H \ K; if exactly that many cells of H \ K can take a digit of Q, those cells hold
// only digits of Q. Bounded enumeration of K's fillings (nothing is emitted when the cap is hit).
void Solver::combo_positions(MoveBuf& out) {
    if (disabled[COMBO_POS] || !p.has_cages) return;
    const int D = p.D;
    std::set<std::vector<uint32_t>> seen;
    for (int kg : p.sum_cages) {
        const auto& K = p.groups[kg].cells;
        if (K.size() < 2 || K.size() > 8) continue;
        bool open = false;
        for (int c : K) open |= !vals[c];
        if (!open) continue;
        for (int hi : p.houses) {
            if (!p.groups[hi].complete || hi == kg) continue;
            std::vector<int> in, outc;
            for (int c : K)
                if (tbit(p.gbits(hi), c)) in.push_back(c);
            if (in.empty()) continue;
            for (int c : p.groups[hi].cells)
                if (!vals[c] && std::find(K.begin(), K.end(), c) == K.end()) outc.push_back(c);
            if (outc.empty()) continue;
            // masks of the digits K puts into K n H, over K's fillings
            std::set<uint32_t> masks;
            std::vector<int> cells(K.begin(), K.end());
            std::vector<char> inH(cells.size());
            for (size_t i = 0; i < cells.size(); ++i) inH[i] = tbit(p.gbits(hi), cells[i]);
            pm_long nodes = 0;
            bool aborted = false;
            const int T = p.groups[kg].total;
            std::function<void(size_t, uint32_t, int, uint32_t)> rec = [&](size_t i, uint32_t used, int sum, uint32_t mH) {
                if (aborted) return;
                if (++nodes > 20000) { aborted = true; return; }
                if (sum > T) return;
                if (i == cells.size()) {
                    if (sum == T) masks.insert(mH);
                    return;
                }
                const int c = cells[i];
                const uint32_t dom = vals[c] ? bit(vals[c]) : cand[c];
                for (uint32_t m = dom & ~used; m; m &= m - 1) {
                    const int v = lowdigit(m);
                    rec(i + 1, used | bit(v), sum + v, inH[i] ? (mH | bit(v)) : mH);
                }
            };
            rec(0, 0, 0, 0);
            if (aborted || masks.empty()) continue;
            const uint32_t missing = p.full & ~placed_g[hi];
            std::vector<int> qd;
            for (uint32_t m = missing; m; m &= m - 1) qd.push_back(lowdigit(m));
            auto try_q = [&](uint32_t Q) {
                int mq = 0;
                for (uint32_t mk : masks) mq = std::max(mq, popc(mk & Q));
                const int need = popc(Q) - mq;
                if (need <= 0) return;
                std::vector<int> X;
                for (int c : outc)
                    if (cand[c] & Q) X.push_back(c);
                if ((int)X.size() != need) return;
                std::vector<uint32_t> el;
                for (int c : X)
                    for (uint32_t b = cand[c] & ~Q; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                if (el.empty()) return;
                std::sort(el.begin(), el.end());
                if (!seen.insert(el).second) return;
                Move& mv = new_move(out, COMBO_POS, 1.0, (int)masks.size());
                for (uint32_t e : el) out.elims.push_back(e), ++mv.el_n;
                std::vector<int> pc(in);
                pc.insert(pc.end(), X.begin(), X.end());
                set_pattern(out, mv, pc);
                add_expl(out, mv, EX_BASE, {hi});
                mv.nk = NM_GROUP;
                mv.na = kg;
                mv.has_meta = true;
                mv.meta[0] = std::min(p.N, (int)(K.size() + X.size()));
                mv.meta[1] = 2;
                mv.meta[2] = popc(Q);
                mv.meta[3] = 0;
                mv.meta[4] = 1;
                mv.meta[5] = 1;
                mv.meta[6] = 0;
                mv.meta[7] = 1;
                mv.spread = pspread(pc);
                mv.code = 3910;
                pm_long xm[XM_N] = {kg, hi, (pm_long)Q, mq, need, (pm_long)masks.size(), 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, mv.xm);
            };
            const int nq = (int)qd.size();
            for (int a = 0; a < nq; ++a)
                for (int b = a + 1; b < nq; ++b) {
                    try_q(bit(qd[a]) | bit(qd[b]));
                    for (int c2 = b + 1; c2 < nq; ++c2) try_q(bit(qd[a]) | bit(qd[b]) | bit(qd[c2]));
                }
        }
    }
    (void)D;
}

}  // namespace cs

namespace cs {

// Clique house (tech 96, CTC 'these four see each other by knight's move, so they are four different digits').
// Cells that must pairwise differ (a shared house, a 'different' relation such as anti-knight, or a pair relation
// that forbids equal digits) form a virtual house. A clique K (4..6 cells, not inside one declared house) whose
// candidates together are exactly |K| digits holds each of them once: cells that must differ from all of K lose
// them, and a digit with one place in K goes there.
void Solver::clique_house(MoveBuf& out) {
    if (disabled[CLIQUE_HOUSE]) return;
    const int N = p.N, D1 = p.D + 1;
    {  // plain row / column / box grids: every clique of peers lies in one house
        bool extra = false;
        for (int c = 0; c < N && !extra; ++c) extra = !p.rel[c].empty();
        for (int g : p.houses) extra |= p.group_cat[g] != GC_LINE && p.group_cat[g] != GC_BOX;
        bool neq = false;
        for (int c = 0; c < N && !neq; ++c) neq = !p.neq[c].empty();
        if (!extra && !neq) return;
    }
    std::vector<int> open;
    for (int c = 0; c < N; ++c)
        if (!vals[c] && popc(cand[c]) <= 5) open.push_back(c);
    if (open.size() < 4) return;
    // must-differ test (houses / neq peers, or a relation forbidding equal digits)
    auto differ = [&](int a, int b) {
        if (tbit(p.peers(a), b)) return true;
        for (size_t j = 0; j < p.rel[a].size(); ++j) {
            if (p.rel[a][j] != b) continue;
            bool all = true;
            for (int v = 1; v < D1 && all; ++v) all = (p.rel_out[a][j * D1 + v] & bit(v)) != 0;
            if (all) return true;
        }
        return false;
    };
    const int n = (int)open.size();
    std::vector<std::vector<char>> adj(n, std::vector<char>(n, 0));
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j) adj[i][j] = adj[j][i] = differ(open[i], open[j]);
    auto in_one_house = [&](const std::vector<int>& K) {
        for (int g : p.houses) {
            bool all = true;
            for (int c : K) all &= tbit(p.gbits(g), c);
            if (all) return true;
        }
        return false;
    };
    std::set<std::vector<uint32_t>> seen;
    std::vector<int> K;
    pm_long nodes = 0;
    std::function<void(int, uint32_t)> rec = [&](int st, uint32_t U) {
        if (++nodes > 200000) return;
        const int k = (int)K.size();
        if (k >= 4 && popc(U) == k) {
            std::vector<int> cells;
            for (int i : K) cells.push_back(open[i]);
            if (!in_one_house(cells)) {
                std::vector<uint32_t> el;
                std::vector<std::pair<int, int>> places;
                for (int c = 0; c < N; ++c) {
                    if (vals[c] || !(cand[c] & U) || std::find(cells.begin(), cells.end(), c) != cells.end()) continue;
                    bool all = true;
                    for (int x : cells) all &= differ(c, x);
                    if (!all) continue;
                    for (uint32_t b = cand[c] & U; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                }
                for (uint32_t b = U; b; b &= b - 1) {
                    const int d = lowdigit(b);
                    int at = -1, cnt = 0;
                    for (int x : cells)
                        if (cand[x] & bit(d)) ++cnt, at = x;
                    if (cnt == 1 && popc(cand[at]) > 1) places.push_back({at, d});
                }
                auto emit = [&](const std::vector<uint32_t>& e, int pc, int pv) {
                    std::vector<uint32_t> key(e);
                    key.push_back((uint32_t)(pc + 1) * 32u + (uint32_t)pv);
                    if (!seen.insert(key).second) return;
                    Move& m = new_move(out, CLIQUE_HOUSE, 1.0, k);
                    if (pc >= 0) m.pc = pc, m.pv = pv;
                    for (uint32_t x : e) out.elims.push_back(x), ++m.el_n;
                    set_pattern(out, m, cells);
                    m.has_meta = true;
                    m.meta[0] = k;
                    m.meta[1] = k;  // groups: the pairwise links taken together
                    m.meta[2] = k;
                    m.meta[3] = 0;
                    m.meta[4] = pc >= 0 ? 1 : 0;
                    m.meta[5] = 0;
                    m.meta[6] = 1;
                    m.meta[7] = 1;
                    m.spread = pspread(cells);
                    m.code = 3920;
                    pm_long xm[XM_N] = {k, (pm_long)U, (pm_long)e.size(), pc >= 0, 0, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                };
                if (!el.empty()) emit(el, -1, 0);
                for (auto& pl : places) emit({}, pl.first, pl.second);
            }
        }
        if (k == 6) return;
        for (int i = st; i < n; ++i) {
            const uint32_t U2 = U | cand[open[i]];
            if (popc(U2) > 6) continue;
            bool ok = true;
            for (int j : K) ok &= adj[i][j] != 0;
            if (!ok) continue;
            K.push_back(i);
            rec(i + 1, U2);
            K.pop_back();
        }
    };
    rec(0, 0);
}

}  // namespace cs

namespace cs {

// Line digit sets across lines (tech 97, CTC 'the two digits private to this renban are 1,2 or 2,3 ... the two in
// common are 3,4 or 4,5'). For a house H and the consecutive-set lines (renbans) meeting it in >= 2 cells: each
// line's options = digit assignments of its H cells over all its consecutive runs that the whole line can fill
// (perfect matching of its cells onto the run). Lines meeting H use different digits inside H, so options are
// chosen jointly (pairwise disjoint on H); a digit no joint choice gives an H cell leaves it.
void Solver::line_sets(MoveBuf& out) {
    if (disabled[LINE_SETS]) return;
    const int D = p.D;
    std::vector<const NConstraint*> lines;
    for (const NConstraint& k : p.nary)
        if (k.type == NT_SET && k.setkind == 0 && k.nv() >= 2 && k.nv() <= 7 && k.nv() < D) lines.push_back(&k);
    if (lines.size() < 2) return;
    std::set<std::vector<uint32_t>> seen;
    for (int hi : p.houses) {
        if (!p.groups[hi].complete) continue;
        struct LO { const NConstraint* k; std::vector<int> hc; std::vector<std::vector<uint8_t>> opts; };
        std::vector<LO> los;
        for (const NConstraint* k : lines) {
            std::vector<int> hc;
            for (int c : k->vars)
                if (tbit(p.gbits(hi), c)) hc.push_back(c);
            if (hc.size() < 2) continue;
            bool open = false;
            for (int c : hc) open |= !vals[c];
            if (!open) continue;
            LO lo{k, hc, {}};
            const int n = k->nv();
            std::set<std::vector<uint8_t>> optset;
            for (int a = 1; a + n - 1 <= D && optset.size() < 2000; ++a) {
                const uint32_t run = ((1u << n) - 1) << (a - 1);
                // all assignments of the line's cells onto the run (distinct), keep the H part
                std::vector<int> asg(n, 0);
                std::function<void(int, uint32_t)> rec = [&](int i, uint32_t used) {
                    if (optset.size() >= 2000) return;
                    if (i == n) {
                        std::vector<uint8_t> o;
                        for (int j = 0; j < n; ++j)
                            if (tbit(p.gbits(hi), k->vars[j])) o.push_back((uint8_t)asg[j]);
                        optset.insert(o);
                        return;
                    }
                    const int c = k->vars[i];
                    const uint32_t dom = (vals[c] ? bit(vals[c]) : cand[c]) & run & ~used;
                    for (uint32_t m = dom; m; m &= m - 1) {
                        asg[i] = lowdigit(m);
                        rec(i + 1, used | bit(asg[i]));
                    }
                };
                rec(0, 0);
            }
            if (optset.size() >= 2000 || optset.empty()) continue;
            lo.opts.assign(optset.begin(), optset.end());
            los.push_back(std::move(lo));
        }
        if (los.size() < 2 || los.size() > 4) continue;
        {  // lines sharing a cell (crossing renbans) would need equal, not different, digits there: skip
            std::vector<int> all;
            for (auto& lo : los) all.insert(all.end(), lo.hc.begin(), lo.hc.end());
            std::sort(all.begin(), all.end());
            if (std::adjacent_find(all.begin(), all.end()) != all.end()) continue;
        }
        // joint choice: H parts pairwise disjoint (and disjoint from H's placed digits outside the lines)
        const int nl = (int)los.size();
        std::vector<std::vector<uint32_t>> sup(nl);
        for (int i = 0; i < nl; ++i) sup[i].assign(los[i].hc.size(), 0);
        std::vector<int> pick(nl, -1);
        pm_long nodes = 0;
        bool aborted = false;
        uint32_t outside_placed = placed_g[hi];
        for (auto& lo : los)
            for (int c : lo.hc)
                if (vals[c]) outside_placed &= ~bit(vals[c]);
        std::vector<int> others;  // open cells of the house on none of the lines
        for (int c : p.groups[hi].cells) {
            if (vals[c]) continue;
            bool on = false;
            for (auto& lo : los) on |= std::find(lo.hc.begin(), lo.hc.end(), c) != lo.hc.end();
            if (!on) others.push_back(c);
        }
        std::function<void(int, uint32_t)> rec2 = [&](int i, uint32_t used) {
            if (aborted) return;
            if (++nodes > 300000) { aborted = true; return; }
            if (i == nl) {
                // the house's other open cells must take every remaining missing digit (pigeonhole: 'one of these
                // overlaps needs to be a 6'): each leftover digit needs a free cell that can hold it, and there
                // must be as many free cells as leftover digits
                const uint32_t left = (p.full & ~placed_g[hi]) & ~used;
                uint32_t can = 0;
                int nfree = 0;
                for (int c : others) can |= cand[c], ++nfree;
                if ((left & ~can) || popc(left) != nfree) return;
                for (int j = 0; j < nl; ++j)
                    for (size_t x = 0; x < los[j].hc.size(); ++x) sup[j][x] |= bit(los[j].opts[pick[j]][x]);
                return;
            }
            for (size_t o = 0; o < los[i].opts.size(); ++o) {
                uint32_t m = 0;
                for (uint8_t d : los[i].opts[o]) m |= bit(d);
                if (m & used) continue;
                pick[i] = (int)o;
                rec2(i + 1, used | m);
            }
        };
        rec2(0, outside_placed);
        if (aborted) continue;
        std::vector<uint32_t> el;
        std::vector<int> pc;
        bool dead = false;
        for (int j = 0; j < nl; ++j)
            for (size_t x = 0; x < los[j].hc.size(); ++x) {
                const int c = los[j].hc[x];
                if (vals[c]) continue;
                dead |= !(cand[c] & sup[j][x]);
                for (uint32_t b = cand[c] & ~sup[j][x]; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
            }
        if (dead || el.empty()) continue;
        std::sort(el.begin(), el.end());
        el.erase(std::unique(el.begin(), el.end()), el.end());
        if (!seen.insert(el).second) continue;
        Move& m = new_move(out, LINE_SETS, 1.0, nl);
        for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
        for (auto& lo : los)
            for (int c : lo.k->vars) pc.push_back(c);
        set_pattern(out, m, pc);
        add_expl(out, m, EX_BASE, {hi});
        m.has_meta = true;
        pm_long nopt = 0;
        for (auto& lo : los) nopt += (pm_long)lo.opts.size();
        m.meta[0] = std::min(p.N, (int)pc.size());
        m.meta[1] = nl + 1;
        m.meta[2] = 0;
        for (auto& lo : los)
            for (int c : lo.hc) m.meta[2] = std::max(m.meta[2], popc(vals[c] ? bit(vals[c]) : cand[c]));
        m.meta[3] = 0;
        m.meta[4] = 1;
        m.meta[5] = 0;
        m.meta[6] = 1;
        m.meta[7] = 1;
        m.spread = pspread(pc);
        m.code = 3930;
        pm_long xm[XM_N] = {hi, nl, nopt, (pm_long)el.size(), 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

}  // namespace cs

namespace cs {

// Outside clues together (tech 98, CTC 'if that was a 5 this would be a 4 -- that would cover all the cells in the
// row, but they don't add up'): a line carrying two or more outside clues (sandwich, x-sum, skyscraper) is
// enumerated as one unit -- its open cells as a permutation of the missing digits, every clue checked at the
// leaves. Digits no filling gives a cell go. Bounded (nothing is emitted when the cap is hit).
void Solver::line_clues(MoveBuf& out) {
    if (disabled[LINE_CLUES]) return;
    static const std::vector<GacReq> noreq;
    for (int hi : p.houses) {
        if (!p.groups[hi].complete || p.group_line[hi] >= 2) continue;
        const auto& cells = p.groups[hi].cells;
        std::vector<const NConstraint*> clues;
        for (const NConstraint& k : p.nary) {
            if (k.type != NT_SANDWICH && k.type != NT_XSUM && k.type != NT_SKYLINE) continue;
            bool inside = true;
            for (int c : k.vars) inside &= tbit(p.gbits(hi), c);
            if (inside) clues.push_back(&k);
        }
        if (clues.size() < 2) continue;
        std::vector<int> open;
        for (int c : cells)
            if (!vals[c]) open.push_back(c);
        if (open.empty() || open.size() > 9) continue;
        std::sort(open.begin(), open.end(), [&](int a, int b) { return popc(cand[a]) < popc(cand[b]); });
        std::vector<uint8_t> grid(vals.begin(), vals.end());
        std::vector<uint32_t> sup(p.N, 0);
        pm_long nodes = 0;
        bool aborted = false;
        uint32_t dm[64];
        std::function<void(size_t, uint32_t)> rec = [&](size_t i, uint32_t used) {
            if (aborted) return;
            if (++nodes > 300000) { aborted = true; return; }
            if (i == open.size()) {
                for (const NConstraint* k : clues) {
                    for (int j = 0; j < k->nv(); ++j) dm[j] = bit(grid[k->vars[j]]);
                    GacOut o;
                    nary_gac(*k, dm, noreq, 1000, p.D, o);
                    if (o.complete && !o.any) return;
                }
                for (int c : open) sup[c] |= bit(grid[c]);
                return;
            }
            const int c = open[i];
            for (uint32_t m = cand[c] & ~used & ~placed_g[hi]; m; m &= m - 1) {
                const int v = lowdigit(m);
                grid[c] = (uint8_t)v;
                rec(i + 1, used | bit(v));
            }
            grid[c] = 0;
        };
        rec(0, 0);
        if (aborted) continue;
        std::vector<uint32_t> el;
        bool dead = false;
        for (int c : open) {
            dead |= !(cand[c] & sup[c]);
            for (uint32_t b = cand[c] & ~sup[c]; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
        }
        if (dead || el.empty()) continue;
        Move& m = new_move(out, LINE_CLUES, 1.0, (int)clues.size());
        for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
        set_pattern(out, m, open);
        add_expl(out, m, EX_BASE, {hi});
        m.nk = NM_GROUP;
        m.na = hi;
        m.has_meta = true;
        m.meta[0] = (int)open.size();
        m.meta[1] = 1 + (int)clues.size();
        m.meta[2] = popc(p.full & ~placed_g[hi]);
        m.meta[3] = 0;
        m.meta[4] = 0;
        m.meta[5] = 1;
        m.meta[6] = 0;
        m.meta[7] = 1;
        m.spread = pspread(open);
        m.code = 3940;
        pm_long xm[XM_N] = {hi, (pm_long)clues.size(), std::min(nodes, pm_long(1000000000)), (pm_long)el.size(), 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

}  // namespace cs

namespace cs {

// Weighted multi-house sums (tech 99, CTC 'these are counted three times ... 34 x 3 = 102, so that's a seven';
// 'all of these add up to two lots of 45'). Linear sum facts -- complete houses (= D(D+1)/2), sum cages, sum
// rules (little killers ...), arrows (line - circle = 0), equal sums (segment differences) -- are combined with
// small integer coefficients (2-3 facts that share open cells, coefficients +-1 / +-2) until only 1-3 open cells
// keep a nonzero weight: sum w_i x_i = K. Those cells are enumerated (cells that see each other differ); digits
// no solution gives a cell go. A combination of only houses and cages with unit weights is left to SumAlgebra.
void Solver::weighted_sums(MoveBuf& out) {
    if (disabled[WEIGHTED_SUMS]) return;
    const int N = p.N, D = p.D;
    struct Fact { std::vector<int> w; pm_long k; bool house; };
    std::vector<Fact> facts;
    // cells forced equal by an equality relation (palindromes, clones, '=' dots) are one variable: their weights
    // add up on the class representative (CTC 'expressed as three times this digit')
    std::vector<int> rep(N);
    for (int c = 0; c < N; ++c) rep[c] = c;
    std::function<int(int)> fr = [&](int x) { return rep[x] == x ? x : rep[x] = fr(rep[x]); };
    for (int c = 0; c < N; ++c)
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            bool eq = true;
            for (int v = 1; v <= D && eq; ++v) eq = p.rel_out[c][j * (D + 1) + v] == (p.full & ~bit(v));
            if (eq) {
                const int a = fr(c), b = fr(p.rel[c][j]);
                if (a != b) rep[std::max(a, b)] = std::min(a, b);
            }
        }
    auto add = [&](const std::vector<std::pair<int, int>>& terms, pm_long k, bool house) {
        Fact f{std::vector<int>(N, 0), k, house};
        for (auto& t : terms) {
            const int c = t.first;
            if (vals[c]) f.k -= (pm_long)t.second * vals[c];
            else f.w[fr(c)] += t.second;  // class representative (it is open too: a class shares one digit)
        }
        for (int c = 0; c < N; ++c)
            if (vals[c] && f.w[c]) f.k -= (pm_long)f.w[c] * vals[c], f.w[c] = 0;
        bool open = false;
        for (int c = 0; c < N; ++c) open |= f.w[c] != 0;
        if (open) facts.push_back(std::move(f));
    };
    const pm_long HT = (pm_long)D * (D + 1) / 2;
    for (int g : p.houses)
        if (p.groups[g].complete && (int)p.groups[g].cells.size() == D) {
            std::vector<std::pair<int, int>> t;
            for (int c : p.groups[g].cells) t.push_back({c, 1});
            add(t, HT, true);
        }
    for (int g : p.sum_cages) {
        std::vector<std::pair<int, int>> t;
        for (int c : p.groups[g].cells) t.push_back({c, 1});
        add(t, p.groups[g].total, true);
    }
    for (const NConstraint& k : p.nary) {
        if (k.type == NT_SUM && k.totals.empty() && k.offset == 0 && !k.bounds_only) {
            std::vector<std::pair<int, int>> t;
            for (int v : k.pvar) t.push_back({k.vars[v], 1});  // positions (a cell may repeat)
            add(t, k.total, false);
        } else if (k.type == NT_ARROW && k.ncircle == 1) {
            std::vector<std::pair<int, int>> t;
            for (size_t i = 0; i < k.pvar.size(); ++i) t.push_back({k.vars[k.pvar[i]], i == 0 ? -1 : 1});
            add(t, 0, false);
        } else if (k.type == NT_EQSUM && k.seg_start.size() >= 3) {
            const int ns = (int)k.seg_start.size() - 1;
            for (int s = 1; s < ns; ++s) {  // seg_s - seg_0 = offset * (|seg_s| - |seg_0|)
                std::vector<std::pair<int, int>> t;
                // seg_start indexes positions; positions map to (deduplicated) vars through pvar
                for (int i = k.seg_start[s]; i < k.seg_start[s + 1]; ++i) t.push_back({k.vars[k.pvar[i]], 1});
                for (int i = k.seg_start[0]; i < k.seg_start[1]; ++i) t.push_back({k.vars[k.pvar[i]], -1});
                const pm_long n0 = k.seg_start[1] - k.seg_start[0], ns_ = k.seg_start[s + 1] - k.seg_start[s];
                add(t, (pm_long)k.offset * (ns_ - n0), false);
            }
        }
    }
    const int nf = (int)facts.size();
    if (nf < 2 || nf > 120) return;
    std::vector<std::vector<int>> opens(nf);
    for (int i = 0; i < nf; ++i)
        for (int c = 0; c < N; ++c)
            if (facts[i].w[c]) opens[i].push_back(c);
    auto shares = [&](const std::vector<int>& w, int j) {
        for (int c : opens[j])
            if (w[c]) return true;
        return false;
    };
    std::set<std::vector<uint32_t>> seen;
    pm_long work = 0;
    const pm_long cap = 400000;
    std::vector<int> W(N);
    auto evaluate = [&](pm_long K, bool any_rule, int maxw, const std::vector<int>& used) {
        std::vector<int> cs;
        for (int c = 0; c < N; ++c)
            if (W[c]) {
                cs.push_back(c);
                if (cs.size() > 3) return;
            }
        if (cs.empty() || (!any_rule && maxw < 2)) return;
        const int n = (int)cs.size();
        std::vector<uint32_t> sup(n, 0);
        std::vector<int> asg(n, 0);
        std::function<void(int, pm_long)> rec = [&](int i, pm_long s) {
            if (i == n) {
                if (s == K)
                    for (int j = 0; j < n; ++j) sup[j] |= bit(asg[j]);
                return;
            }
            for (uint32_t m = cand[cs[i]]; m; m &= m - 1) {
                const int v = lowdigit(m);
                bool ok = true;
                for (int j = 0; j < i && ok; ++j) ok = !(asg[j] == v && tbit(p.peers(cs[i]), cs[j]));
                if (!ok) continue;
                asg[i] = v;
                rec(i + 1, s + (pm_long)W[cs[i]] * v);
            }
        };
        rec(0, 0);
        std::vector<uint32_t> el;
        for (int j = 0; j < n; ++j) {
            if (!sup[j]) return;  // inconsistent: leave it
            for (uint32_t b = cand[cs[j]] & ~sup[j]; b; b &= b - 1) el.push_back((uint32_t)cs[j] * 32u + lowdigit(b));
        }
        if (el.empty()) return;
        std::sort(el.begin(), el.end());
        if (!seen.insert(el).second) return;
        Move& m = new_move(out, WEIGHTED_SUMS, 1.0, (int)used.size());
        for (uint32_t e : el) out.elims.push_back(e), ++m.el_n;
        std::vector<int> pc;
        for (int f : used)
            for (int c : opens[f])
                if (std::find(pc.begin(), pc.end(), c) == pc.end()) pc.push_back(c);
        set_pattern(out, m, pc);
        m.has_meta = true;
        m.meta[0] = std::min(N, (int)pc.size());
        m.meta[1] = (int)used.size();
        m.meta[2] = 0;
        for (int c : cs) m.meta[2] = std::max(m.meta[2], popc(cand[c]));
        m.meta[3] = (int)used.size() - 1;
        m.meta[4] = 0;
        m.meta[5] = 1;
        m.meta[6] = 0;
        m.meta[7] = 1;
        m.spread = pspread(pc);
        m.code = 3950;
        pm_long xm[XM_N] = {(pm_long)used.size(), n, maxw, (pm_long)el.size(), K, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    // any number of facts, one cell left (CTC 'counted four times ... 34 x 3 = 102, that's a seven'): for each
    // open cell c, a combination lambda of ALL facts that cancels every other open cell but not c pins x_c. Found by
    // floating-point elimination, then made exact: lambda rescaled to small integers and the integer combination
    // re-checked (zero off c, divisible total); only a verified identity is used.
    {
        std::vector<int> cells;
        for (int c = 0; c < N; ++c) {
            if (vals[c]) continue;
            bool any = false;
            for (int f = 0; f < nf && !any; ++f) any = facts[f].w[c] != 0;
            if (any) cells.push_back(c);
        }
        const int R = (int)cells.size();
        if (R >= 2 && R <= 81 && nf <= 80) {
            for (int ti = 0; ti < R && work < cap; ++ti) {
                const int tc = cells[ti];
                // rows: equations sum_f lambda_f w_f(c') = 0 for c' != tc; unknowns lambda (nf)
                std::vector<std::vector<long double>> A;
                for (int r = 0; r < R; ++r) {
                    if (r == ti) continue;
                    std::vector<long double> row(nf);
                    bool nz = false;
                    for (int f = 0; f < nf; ++f) row[f] = facts[f].w[cells[r]], nz |= row[f] != 0;
                    if (nz) A.push_back(std::move(row));
                }
                work += (pm_long)A.size() * nf;
                // reduced row echelon form
                std::vector<int> pivcol;
                int rank = 0;
                for (int col = 0; col < nf && rank < (int)A.size(); ++col) {
                    int best = -1;
                    long double bv = 1e-9L;
                    for (int r = rank; r < (int)A.size(); ++r)
                        if (std::fabs(A[r][col]) > bv) bv = std::fabs(A[r][col]), best = r;
                    if (best < 0) continue;
                    std::swap(A[rank], A[best]);
                    const long double pv = A[rank][col];
                    for (int f = 0; f < nf; ++f) A[rank][f] /= pv;
                    for (int r = 0; r < (int)A.size(); ++r) {
                        if (r == rank || std::fabs(A[r][col]) < 1e-15L) continue;
                        const long double m2 = A[r][col];
                        for (int f = 0; f < nf; ++f) A[r][f] -= m2 * A[rank][f];
                    }
                    pivcol.push_back(col);
                    ++rank;
                }
                std::vector<char> isp(nf, 0);
                for (int pcl : pivcol) isp[pcl] = 1;
                for (int free = 0; free < nf; ++free) {  // one null vector per free column
                    if (isp[free]) continue;
                    std::vector<long double> lam(nf, 0);
                    lam[free] = 1;
                    for (int r = 0; r < rank; ++r) lam[pivcol[r]] = -A[r][free];
                    long double s = 0;
                    for (int f = 0; f < nf; ++f) s += lam[f] * facts[f].w[tc];
                    if (std::fabs(s) < 1e-6L) continue;
                    // exact: scale to integers (denominators up to 60)
                    std::vector<pm_long> li(nf);
                    bool okint = false;
                    for (int den = 1; den <= 60 && !okint; ++den) {
                        okint = true;
                        for (int f = 0; f < nf && okint; ++f) {
                            const long double v = lam[f] * den;
                            li[f] = (pm_long)std::llround(v);
                            okint = std::fabs(v - li[f]) < 1e-6L && pm_labs(li[f]) <= 1000;
                        }
                    }
                    if (!okint) continue;
                    pm_long ws = 0, K = 0;
                    bool clean = true;
                    for (int c = 0; c < N && clean; ++c) {
                        pm_long w = 0;
                        for (int f = 0; f < nf; ++f) w += li[f] * facts[f].w[c];
                        if (c == tc) ws = w;
                        else clean = w == 0;
                    }
                    if (!clean || ws == 0) continue;
                    for (int f = 0; f < nf; ++f) K += li[f] * facts[f].k;
                    if (K % ws) continue;  // (would mean an inconsistent state)
                    const pm_long v = K / ws;
                    if (v < 1 || v > D || !(cand[tc] & bit((int)v)) || popc(cand[tc]) == 1) break;
                    std::vector<uint32_t> key{0xFFFFu, (uint32_t)tc, (uint32_t)v};
                    if (!seen.insert(key).second) break;
                    int nused = 0, maxw = (int)pm_labs(ws);
                    std::vector<int> used;
                    for (int f = 0; f < nf; ++f)
                        if (li[f]) ++nused, used.push_back(f);
                    if (nused < 2) break;  // one fact with one open cell: a single / cage completion
                    Move& m = new_move(out, WEIGHTED_SUMS, 1.0, nused);
                    m.pc = tc;
                    m.pv = (int)v;
                    std::vector<int> pc;
                    for (int f : used)
                        for (int c : opens[f])
                            if (std::find(pc.begin(), pc.end(), c) == pc.end()) pc.push_back(c);
                    set_pattern(out, m, pc);
                    m.has_meta = true;
                    m.meta[0] = std::min(N, (int)pc.size());
                    m.meta[1] = nused;
                    m.meta[2] = 1;
                    m.meta[3] = nused - 1;
                    m.meta[4] = 0;
                    m.meta[5] = 1;
                    m.meta[6] = 0;
                    m.meta[7] = 1;
                    m.spread = pspread(pc);
                    m.code = 3951;
                    pm_long xm[XM_N] = {nused, 1, maxw, 0, K, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                    break;
                }
            }
        }
    }
    static const int coefs[4] = {1, -1, 2, -2};
    for (int a = 0; a < nf && work < cap; ++a)
        for (int b = a + 1; b < nf && work < cap; ++b) {
            if (!shares(facts[a].w, b)) continue;
            for (int cb : coefs) {
                ++work;
                bool any_rule = !facts[a].house || !facts[b].house;
                pm_long K = facts[a].k + (pm_long)cb * facts[b].k;
                int maxw = 0, cnt = 0;
                for (int c = 0; c < N; ++c) {
                    W[c] = facts[a].w[c] + cb * facts[b].w[c];
                    if (W[c]) ++cnt, maxw = std::max(maxw, std::abs(W[c]));
                }
                if (cnt <= 3) evaluate(K, any_rule, maxw, {a, b});
                if (cnt > 12) continue;  // triples only from near-cancelling pairs
                const std::vector<int> W2 = W;
                for (int c3 = 0; c3 < nf && work < cap; ++c3) {
                    if (c3 == a || c3 == b || !shares(W2, c3)) continue;
                    for (int cc : coefs) {
                        ++work;
                        int cnt3 = 0, mw = 0;
                        for (int c = 0; c < N; ++c) {
                            W[c] = W2[c] + cc * facts[c3].w[c];
                            if (W[c]) ++cnt3, mw = std::max(mw, std::abs(W[c]));
                        }
                        if (cnt3 <= 3) evaluate(K + (pm_long)cc * facts[c3].k, any_rule || !facts[c3].house, mw, {a, b, c3});
                    }
                }
            }
        }
}

}  // namespace cs
