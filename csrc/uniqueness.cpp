// Uniqueness techniques (unique rectangles, BUG) and implied-house tagging (split from extra.cpp).
#include <algorithm>
#include "portable.hpp"
#include <climits>
#include <cstdlib>
#include <cstdio>
#include <chrono>
#include <functional>
#include <map>
#include <set>
#include <unordered_set>

#include "solver.hpp"
#include "move_util.hpp"

namespace cs {

namespace {
enum {
    CODE_UR1 = 3001, CODE_UR2, CODE_UR3, CODE_UR4, CODE_HUR, CODE_BUG,
    CODE_IMH = 3201, CODE_UR5 = 3007, CODE_AR1 = 3008
};
}  // namespace

void Solver::tag_implied(MoveBuf& b, size_t from) {
    for (size_t i = from; i < b.moves.size(); ++i) {
        Move& m = b.moves[i];
        if (m.code) continue;
        if ((m.nk == NM_GROUP || m.nk == NM_LOCK || m.nk == NM_INNIE || m.nk == NM_OUTIE) &&
            (m.na >= p.base_G || (m.nk == NM_LOCK && m.nb >= p.base_G)))
            m.code = CODE_IMH;
    }
}

// ------------------------------------------------------------ uniqueness --

void Solver::unique_rect(MoveBuf& out) {
    if (!opt.assume_unique || disabled[UNIQUE_RECT]) return;
    const auto& rects = p.rects();
    if (rects.empty()) return;
    const int D1 = p.D + 1;
    ElimSet es;
    // swapping x<->y in the rectangle must not change any pair-relation outcome
    auto rel_inv = [&](const int* cells, int x, int y) {
        // the swap puts x where y was and vice versa: every cell's domain must allow both (odd/even,
        // restricted cells)
        for (int i = 0; i < 4; ++i)
            if (!(p.domains[cells[i]] & bit(x)) || !(p.domains[cells[i]] & bit(y))) return false;
        for (int i = 0; i < 4; ++i) {
            int c = cells[i];
            for (size_t j = 0; j < p.rel[c].size(); ++j) {
                const uint32_t* to = &p.rel_out[c][j * D1];
                const uint32_t* ti = &p.rel_in[c][j * D1];
                if (to[x] != to[y]) return false;
                for (int w = 1; w <= p.D; ++w)
                    if (((ti[w] >> (x - 1)) & 1) != ((ti[w] >> (y - 1)) & 1)) return false;
            }
        }
        return true;
    };
    auto common_groups2 = [&](int a, int b, bool complete_only, std::vector<int>& gs) {
        gs.clear();
        for (int gi : p.groups_of[a])
            if (tbit(p.gbits(gi), b) && (!complete_only || p.groups[gi].complete)) gs.push_back(gi);
    };
    std::vector<int> gs, others;
    auto emit = [&](int code, std::vector<uint32_t>& el, const int* cells, int x, int y, int extra_cells) {
        if (el.empty() || (!canon && !es.fresh(el, code))) return;
        double shp = pspread({cells[0], cells[1], cells[2], cells[3]});
        Move& m = new_move(out, UNIQUE_RECT, shp, code - CODE_UR1 + 1);
        for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
        set_pattern(out, m, {cells[0], cells[1], cells[2], cells[3]});
        meta9(m, 4 + extra_cells, 2, 2, 0, code == CODE_HUR || code == CODE_UR4, 0, 0, 1, shp);
        m.code = code;
        pm_long xm[XM_N] = {code - CODE_UR1 + 1, x, y, extra_cells, (pm_long)el.size(), 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    // avoidable rectangle type 1: three corners solved (not givens) as x / y / y around the fourth;
    // the fourth taking x would leave a swappable x/y rectangle of non-givens -> it is not x
    for (const auto& r : rects) {
        const int* c = r.c;
        int un = -1, nun = 0;
        for (int i = 0; i < 4; ++i)
            if (!vals[c[i]]) un = i, ++nun;
        if (nun != 1) continue;
        bool given = false;
        for (int i = 0; i < 4; ++i) given |= i != un && is_given[c[i]];
        if (given) continue;
        const int o = 3 - un;                                    // opposite corner holds x
        const int s1 = (un == 0 || un == 3) ? 1 : 0, s2 = (un == 0 || un == 3) ? 2 : 3;  // the sides hold y
        const int x = vals[c[o]], y = vals[c[s1]];
        if (vals[c[s2]] != y || x == y || !(cand[c[un]] & bit(x))) continue;
        if (!rel_inv(c, x, y)) continue;
        std::vector<uint32_t> el{(uint32_t)c[un] * 32 + x};
        emit(CODE_AR1, el, c, x, y, 0);
    }
    // avoidable rectangle type 2 (newer techniques only): two side corners solved (not givens) as x / y; each
    // unsolved corner holds its diagonal partner's digit plus one common extra z. Both taking the partner
    // digit would leave a swappable rectangle of non-givens, so one of them is z: z leaves their common peers
    if (!disabled[COLOUR_ALGEBRA])
        for (const auto& r : rects) {
            const int* c = r.c;
            int un[2], nun = 0, so[2], nso = 0;
            for (int i = 0; i < 4; ++i) {
                if (!vals[c[i]]) {
                    if (nun < 2) un[nun] = i;
                    ++nun;
                } else {
                    if (nso < 2) so[nso] = i;
                    ++nso;
                }
            }
            if (nun != 2 || nso != 2 || so[0] + so[1] == 3) continue;  // solved corners must be a side, not a diagonal
            if (is_given[c[so[0]]] || is_given[c[so[1]]]) continue;
            const int x = vals[c[so[0]]], y = vals[c[so[1]]];
            if (x == y) continue;
            const int r0 = vals[c[3 - un[0]]], r1 = vals[c[3 - un[1]]];
            const uint32_t e0 = cand[c[un[0]]] & ~bit(r0), e1 = cand[c[un[1]]] & ~bit(r1);
            if (!(cand[c[un[0]]] & bit(r0)) || !(cand[c[un[1]]] & bit(r1))) continue;
            if (popc(e0) != 1 || e0 != e1 || (e0 & (bit(x) | bit(y)))) continue;
            if (!rel_inv(c, x, y)) continue;
            const int z = lowdigit(e0);
            std::vector<uint32_t> el;
            for (int q = 0; q < p.N; ++q)
                if (!vals[q] && q != c[un[0]] && q != c[un[1]] && (cand[q] & bit(z)) && tbit(p.peers(q), c[un[0]]) &&
                    tbit(p.peers(q), c[un[1]]))
                    el.push_back((uint32_t)q * 32 + z);
            emit(3011, el, c, x, y, 0);
        }
    for (const auto& r : rects) {
        const int* c = r.c;
        if (vals[c[0]] || vals[c[1]] || vals[c[2]] || vals[c[3]]) continue;
        uint32_t common = cand[c[0]] & cand[c[1]] & cand[c[2]] & cand[c[3]];
        if (popc(common) < 2) continue;
        for (uint32_t mx = common; mx; mx &= mx - 1) {
            int x = lowdigit(mx);
            for (uint32_t my = mx & (mx - 1); my; my &= my - 1) {
                int y = lowdigit(my);
                if (!rel_inv(c, x, y)) continue;
                const uint32_t xy = bit(x) | bit(y);
                unsigned fm = 0;
                for (int i = 0; i < 4; ++i)
                    if (cand[c[i]] == xy) fm |= 1u << i;
                const int nf = __builtin_popcount(fm);
                std::vector<uint32_t> el;
                // type 1
                if (nf == 3) {
                    int t = c[__builtin_ctz(~fm & 15u)];
                    for (uint32_t dm = cand[t] & xy; dm; dm &= dm - 1) el.push_back((uint32_t)t * 32 + lowdigit(dm));
                    emit(CODE_UR1, el, c, x, y, 0);
                }
                if (nf == 2 && (fm == 3 || fm == 12 || fm == 5 || fm == 10)) {
                    unsigned rm = ~fm & 15u;
                    int r1 = c[__builtin_ctz(rm)], r2 = c[31 - __builtin_clz(rm)];
                    uint32_t E = (cand[r1] | cand[r2]) & ~xy;
                    // type 2
                    if (cand[r1] == cand[r2] && popc(cand[r1]) == 3) {
                        el.clear();
                        int z = lowdigit(E);
                        for (int q = 0; q < p.N; ++q)
                            if (q != r1 && q != r2 && !vals[q] && (cand[q] & bit(z)) && tbit(p.peers(r1), q) &&
                                tbit(p.peers(r2), q))
                                el.push_back((uint32_t)q * 32 + z);
                        emit(CODE_UR2, el, c, x, y, 0);
                    }
                    // type 3: roof extras as a virtual cell in a naked subset
                    common_groups2(r1, r2, false, gs);
                    for (int gi : gs) {
                        others.clear();
                        for (int q : p.groups[gi].cells)
                            if (!vals[q] && q != r1 && q != r2) others.push_back(q);
                        const int no = (int)others.size();
                        for (int k = 1; k <= 3 && k < no; ++k) {
                            std::vector<int> idx(k);
                            std::function<void(int, int, uint32_t)> rec = [&](int st, int dep, uint32_t U) {
                                if (popc(U) > k + 1) return;
                                if (dep == k) {
                                    if (popc(U) != k + 1) return;
                                    el.clear();
                                    for (int q : others) {
                                        bool inq = false;
                                        for (int i = 0; i < k; ++i) inq |= others[idx[i]] == q;
                                        if (inq) continue;
                                        for (uint32_t dm = cand[q] & U; dm; dm &= dm - 1)
                                            el.push_back((uint32_t)q * 32 + lowdigit(dm));
                                    }
                                    emit(CODE_UR3, el, c, x, y, k);
                                    return;
                                }
                                for (int i = st; i < no; ++i) {
                                    idx[dep] = i;
                                    rec(i + 1, dep + 1, U | cand[others[i]]);
                                }
                            };
                            rec(0, 0, E);
                        }
                    }
                    // type 4: one of x/y confined to the roof in a complete group
                    common_groups2(r1, r2, true, gs);
                    for (int gi : gs)
                        for (int t = 0; t < 2; ++t) {
                            int a = t ? y : x, b2 = t ? x : y;
                            bool conf = true;
                            for (int q : p.groups[gi].cells)
                                if (q != r1 && q != r2 && !vals[q] && (cand[q] & bit(a))) conf = false;
                            if (!conf) continue;
                            el.clear();
                            for (int rr : {r1, r2})
                                if (cand[rr] & bit(b2)) el.push_back((uint32_t)rr * 32 + b2);
                            emit(CODE_UR4, el, c, x, y, 0);
                        }
                }
                // type 5: the non-floor corners (diagonal pair or three corners) all hold exactly one
                // extra digit z -> z is in one of them -> it leaves the cells seeing all of them
                if (nf >= 1 && nf <= 2 && !(fm == 3 || fm == 12 || fm == 5 || fm == 10)) {
                    uint32_t z = 0;
                    bool ok5 = true;
                    std::vector<int> roof;
                    for (int i = 0; i < 4; ++i) {
                        if (fm >> i & 1) continue;
                        const uint32_t e = cand[c[i]] & ~xy;
                        if (popc(e) != 1 || (z && e != z)) ok5 = false;
                        z = e;
                        roof.push_back(c[i]);
                    }
                    if (ok5 && z) {
                        el.clear();
                        const int zd = lowdigit(z);
                        for (int q = 0; q < p.N; ++q) {
                            if (vals[q] || !(cand[q] & z)) continue;
                            bool all = true;
                            for (int r : roof) all &= r != q && tbit(p.peers(r), q);
                            if (all) el.push_back((uint32_t)q * 32 + zd);
                        }
                        emit(CODE_UR5, el, c, x, y, (int)roof.size());
                    }
                }
                // hidden rectangle: bivalue corner a, opposite o; x strong on both of o's sides
                for (int i = 0; i < 4; ++i) {
                    if (!(fm >> i & 1)) continue;
                    int o = 3 - i;  // opposite corner (A<->D, B<->C)
                    int s1 = (i == 0 || i == 3) ? 1 : 0, s2 = (i == 0 || i == 3) ? 2 : 3;
                    int O = c[o], S1 = c[s1], S2 = c[s2];
                    for (int t = 0; t < 2; ++t) {
                        int a = t ? y : x, b2 = t ? x : y;
                        auto strong_in = [&](int u, int w) {  // a only at u,w in some complete group
                            common_groups2(u, w, true, gs);
                            for (int gi : gs) {
                                bool only = true;
                                for (int q : p.groups[gi].cells)
                                    if (q != u && q != w && !vals[q] && (cand[q] & bit(a))) only = false;
                                if (only) return true;
                            }
                            return false;
                        };
                        if (!(cand[O] & bit(b2)) || !strong_in(O, S1) || !strong_in(O, S2)) continue;
                        el.assign(1, (uint32_t)O * 32 + b2);
                        emit(CODE_HUR, el, c, x, y, 0);
                    }
                }
            }
        }
    }
}

// Extended unique rectangle type 1 (standard 9x9 geometry, houses only): 2 rows of one band x 3
// columns in the band's 3 boxes (or transposed); five cells hold only digits of {x,y,z}, the sixth
// more -> if the sixth took one of x,y,z the six cells could swap within each column -> not unique
void Solver::extended_ur(MoveBuf& out) {
    if (!opt.assume_unique || disabled[UNIQUE_RECT] || p.D != 9 || p.N != 81) return;
    const bool der = p.is_derived && p.base_G >= 0;
    for (const NConstraint& k : p.nary)
        if (!(der && p.base_nary >= 0 && k.index >= p.base_nary)) return;
    for (int c = 0; c < p.N; ++c)
        if (!p.rel[c].empty() || !p.neq[c].empty()) return;
    std::map<std::pair<int, int>, int> at;
    for (int c = 0; c < p.N; ++c) at[p.coords[c]] = c;
    {   // the nine coordinate boxes must be houses
        std::set<std::vector<uint64_t>> hs;
        for (int gi : p.houses) hs.insert(std::vector<uint64_t>(p.gbits(gi), p.gbits(gi) + p.W));
        for (int b = 0; b < 9; ++b) {
            std::vector<uint64_t> bx(p.W, 0);
            for (int r = 0; r < 3; ++r)
                for (int k = 0; k < 3; ++k) {
                    auto it = at.find({b / 3 * 3 + r, b % 3 * 3 + k});
                    if (it == at.end()) return;
                    sbit(bx.data(), it->second);
                }
            if (!hs.count(bx)) return;
        }
    }
    const int G0 = der ? p.base_G : p.G;
    // plain sudoku only: exactly rows, columns and boxes (a diagonal or extra region can break the
    // swap that makes the pattern deadly)
    if (G0 != 27) return;
    for (int gi = 0; gi < G0; ++gi)
        if (!p.groups[gi].complete || p.group_line[gi] > 2) return;
    for (int c = 0; c < p.N; ++c)
        if (p.domains[c] != p.full) return;  // odd/even or other restricted cells
    for (int orient = 0; orient < 2; ++orient)
        for (int band = 0; band < 3; ++band)
            for (int r1 = 0; r1 < 3; ++r1)
                for (int r2 = r1 + 1; r2 < 3; ++r2)
                    for (int c0 = 0; c0 < 3; ++c0)
                        for (int c1 = 3; c1 < 6; ++c1)
                            for (int c2 = 6; c2 < 9; ++c2) {
                                int cells[6], n = 0;
                                for (int rr : {band * 3 + r1, band * 3 + r2})
                                    for (int cc : {c0, c1, c2})
                                        cells[n++] = orient ? at[{cc, rr}] : at[{rr, cc}];
                                bool any_val = false;
                                uint32_t U = 0;
                                for (int i = 0; i < 6; ++i) {
                                    any_val |= vals[cells[i]] != 0;
                                    U |= cand[cells[i]];
                                }
                                if (any_val) continue;
                                // choose the target: the unique cell with digits outside some 3-set
                                for (uint32_t m3 = U; m3; m3 &= m3 - 1) {
                                    (void)m3;
                                }
                                for (int t = 0; t < 6; ++t) {
                                    uint32_t X = 0;
                                    for (int i = 0; i < 6; ++i)
                                        if (i != t) X |= cand[cells[i]];
                                    if (popc(X) != 3 || !(cand[cells[t]] & ~X) || !(cand[cells[t]] & X)) continue;
                                    std::vector<uint32_t> el;
                                    for (uint32_t b = cand[cells[t]] & X; b; b &= b - 1)
                                        el.push_back((uint32_t)cells[t] * 32 + lowdigit(b));
                                    std::vector<int> pc(cells, cells + 6);
                                    Move& m = new_move(out, UNIQUE_RECT, pspread(pc), 7);
                                    for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
                                    set_pattern(out, m, pc);
                                    meta9(m, 6, 3, 3, 0, 0, 0, 0, 1, m.shape);
                                    m.code = 3009;
                                    pm_long xm[XM_N] = {7, (pm_long)X, 0, 6, (pm_long)el.size(), 0, 0, 0, 0, 0};
                                    std::copy(xm, xm + XM_N, m.xm);
                                }
                            }
}

// BUG+2: two tri-value cells T1, T2, every other unsolved cell bivalue. Each tri-cell's extra digit is the
// one counted three times in its houses (every other digit twice); without both extras the grid is a
// deadly BUG (0 or 2 solutions), so T1 = a or T2 = b. Eliminate what all three surviving cases share:
// a == b: a from every cell seeing both; a != b and T1, T2 peers: b from T1 and a from T2.
void Solver::bug_plus2(MoveBuf& out, int T1, int T2, int G0) {
    int found = 0, fa = 0, fb = 0;
    for (uint32_t ma = cand[T1]; ma; ma &= ma - 1)
        for (uint32_t mb = cand[T2]; mb; mb &= mb - 1) {
            const int a = lowdigit(ma), b = lowdigit(mb);
            bool ok = true;
            for (int hi : p.houses) {
                if (hi >= G0) continue;
                const bool h1 = tbit(p.gbits(hi), T1), h2 = tbit(p.gbits(hi), T2);
                for (int v = 1; v <= p.D && ok; ++v) {
                    int n = 0;
                    for (int q : p.groups[hi].cells)
                        if (!vals[q] && (cand[q] & bit(v))) ++n;
                    const int want = 2 + (h1 && v == a) + (h2 && v == b);
                    ok = n == 0 || n == want;
                }
                if (!ok) break;
            }
            if (ok) ++found, fa = a, fb = b;
        }
    if (found != 1) return;
    std::vector<uint32_t> el;
    const bool peers = tbit(p.peers(T1), T2);
    if (fa == fb) {
        for (int c = 0; c < p.N; ++c)
            if (!vals[c] && c != T1 && c != T2 && (cand[c] & bit(fa)) && tbit(p.peers(c), T1) && tbit(p.peers(c), T2))
                el.push_back((uint32_t)c * 32 + fa);
    } else if (peers) {
        if (cand[T1] & bit(fb)) el.push_back((uint32_t)T1 * 32 + fb);
        if (cand[T2] & bit(fa)) el.push_back((uint32_t)T2 * 32 + fa);
    }
    if (el.empty()) return;
    Move& m = new_move(out, BUG_PLUS1, 1.0, 2);
    for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
    set_pattern(out, m, {T1, T2});
    int nun = 0;
    for (int c = 0; c < p.N; ++c) nun += !vals[c];
    meta9(m, nun, (int)p.houses.size(), p.D, 0, 0, 0, 0, 1, 1.0);
    m.code = 3010;
    pm_long xm[XM_N] = {nun, 0, 0, 0, 2, 0, 0, 0, 0, 0};
    std::copy(xm, xm + XM_N, m.xm);
}

// BUG+1: only for puzzles made of complete houses alone
void Solver::bug_plus1(MoveBuf& out) {
    if (!opt.assume_unique || disabled[BUG_PLUS1]) return;
    // derived structure (implied houses, leftover equalities) follows from the original
    // houses: only the original puzzle has to be made of complete houses alone
    const bool der = p.is_derived && p.base_G >= 0;
    for (const NConstraint& k : p.nary)
        if (!(der && p.base_nary >= 0 && k.index >= p.base_nary)) return;
    const int G0 = der ? p.base_G : p.G;
    for (int gi = 0; gi < G0; ++gi)
        if (!p.groups[gi].complete) return;
    int T = -1, T2 = -1;
    for (int c = 0; c < p.N; ++c) {
        if (vals[c]) continue;
        if (!p.rel[c].empty() || !p.neq[c].empty()) return;
        int k = popc(cand[c]);
        if (k == 2) continue;
        if (k != 3 || T2 >= 0) return;
        if (T < 0) T = c;
        else T2 = c;
    }
    if (T < 0) return;
    if (T2 >= 0) {  // BUG+2 (newer techniques only: the frozen reference has BUG+1 alone)
        if (!disabled[COLOUR_ALGEBRA]) bug_plus2(out, T, T2, G0);
        return;
    }
    int digit = 0;
    for (int hi : p.houses) {
        if (hi >= G0) continue;
        bool hasT = tbit(p.gbits(hi), T);
        int three = 0;
        for (int v = 1; v <= p.D; ++v) {
            int n = 0;
            for (int q : p.groups[hi].cells)
                if (!vals[q] && (cand[q] & bit(v))) ++n;
            if (n == 0 || n == 2) continue;
            if (n == 3 && hasT && !three) {
                three = v;
                continue;
            }
            return;
        }
        if (hasT) {
            if (!three || (digit && digit != three)) return;
            digit = three;
        }
    }
    if (!digit || !(cand[T] & bit(digit))) return;
    Move& m = new_move(out, BUG_PLUS1, 1.0, 1);
    m.pc = T;
    m.pv = digit;
    int nun = 0;
    for (int c = 0; c < p.N; ++c) nun += !vals[c];
    meta9(m, nun, (int)p.houses.size(), p.D, 0, 0, 0, 0, 1, 1.0);
    m.code = CODE_BUG;
    pm_long xm[XM_N] = {nun, 0, 0, 0, 1, 0, 0, 0, 0, 0};
    std::copy(xm, xm + XM_N, m.xm);
}

}  // namespace cs
