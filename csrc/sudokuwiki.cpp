// Named strategies from Andrew Stuart's inventory not covered by other engines:
//   NWing (76): WXYZ / VWXYZ wings as bent sets: n connected cells holding exactly n digits, every
//     digit but Z confined to cells that see each other -> Z is in one of the set's Z cells;
//   SueDeCoq (77): box-line intersection cells C (2-3) with digits V, a line set L and a box set B
//     (1-2 cells each), digit sets disjoint, |V u VL u VB| = |C|+|L|+|B|;
//   AlignedPairExclusion (78): two cells; a value pair is impossible when a cell seeing both would
//     be left empty; values without a possible partner go;
//   ChuteRemotePairs (79): two bivalue cells {x,y} of one band / stack in different boxes and lines;
//     the third box's cells on the remaining line hold no x -> y leaves the cells seeing both;
//   PatternOverlay (80): per digit, every placement template (one cell per row, every complete
//     house exactly once) consistent with the candidates; candidates in no template go;
//   Gurth (81): Gurth's symmetrical placement theorem (assumes a unique solution): a grid symmetry
//     with a digit permutation mapping the givens onto themselves maps the solution onto itself.
#include <algorithm>
#include "portable.hpp"
#include <functional>
#include <map>
#include <set>

#include "solver.hpp"

namespace cs {

namespace {
inline void addel(MoveBuf& b, Move& m, int c, int v) {
    b.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
    ++m.el_n;
}
inline void meta_set(Move& m, int a, int b, int c, int d, int e, int f, int g, int h, double sp) {
    m.has_meta = true;
    m.meta[0] = a; m.meta[1] = b; m.meta[2] = c; m.meta[3] = d;
    m.meta[4] = e; m.meta[5] = f; m.meta[6] = g; m.meta[7] = h;
    m.spread = sp;
}
}  // namespace

// ---------------------------------------------------------------- NWing --
void Solver::n_wing(MoveBuf& out) {
    if (disabled[N_WING]) return;
    const int N = p.N;
    std::set<std::vector<int>> seen;
    // bent sets: n cells inside the union of two intersecting houses (a box and a line), n digits
    std::vector<std::pair<int, int>> pairs;
    for (size_t i = 0; i < p.houses.size(); ++i)
        for (size_t j = i + 1; j < p.houses.size(); ++j) {
            const int a = p.houses[i], b = p.houses[j];
            if (p.group_overlap[(size_t)a * p.G + b] && (p.group_line[a] == 2) != (p.group_line[b] == 2))
                pairs.push_back({a, b});
        }
    for (int n = 4; n <= 5; ++n) {
        for (auto& hb : pairs) {
            std::vector<int> pool;
            for (int h : {hb.first, hb.second})
                for (int c : p.groups[h].cells)
                    if (!vals[c] && popc(cand[c]) >= 2 && popc(cand[c]) <= n &&
                        std::find(pool.begin(), pool.end(), c) == pool.end())
                        pool.push_back(c);
            std::sort(pool.begin(), pool.end());
            const int m = (int)pool.size();
            if (m < n) continue;
            std::vector<int> set;
            std::function<void(int, uint32_t)> rec = [&](int st, uint32_t U) {
                if ((int)set.size() == n) {
                    if (popc(U) != n) return;
                    std::vector<int> key = set;
                    if (!seen.insert(key).second) return;
                    int z = 0, nz = 0;
                    for (uint32_t mm = U; mm; mm &= mm - 1) {
                        const int d = lowdigit(mm);
                        std::vector<int> h;
                        for (int c : set)
                            if (cand[c] & bit(d)) h.push_back(c);
                        bool restricted = true;
                        for (size_t i = 0; i < h.size() && restricted; ++i)
                            for (size_t j = i + 1; j < h.size() && restricted; ++j) restricted = tbit(p.peers(h[i]), h[j]);
                        if (!restricted) z = d, ++nz;
                    }
                    if (nz != 1) return;
                    std::vector<int> zc;
                    for (int c : set)
                        if (cand[c] & bit(z)) zc.push_back(c);
                    std::vector<uint32_t> el;
                    for (int q = 0; q < N; ++q) {
                        if (vals[q] || !(cand[q] & bit(z)) || std::find(set.begin(), set.end(), q) != set.end()) continue;
                        bool all = true;
                        for (int c : zc) all &= tbit(p.peers(c), q);
                        if (all) el.push_back((uint32_t)q * 32u + z);
                    }
                    if (el.empty()) return;
                    Move& mv = new_move(out, N_WING, pspread(key), n);
                    for (uint32_t e : el) addel(out, mv, (int)(e / 32), (int)(e % 32));
                    set_pattern(out, mv, key);
                    meta_set(mv, n, n, n, n - 1, 0, 0, 0, 1, mv.shape);
                    mv.code = 4600 + n;
                    pm_long xm[XM_N] = {n, z, (pm_long)zc.size(), (pm_long)el.size(), 0, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, mv.xm);
                    return;
                }
                if (m - st < n - (int)set.size()) return;
                for (int i = st; i < m; ++i) {
                    const uint32_t U2 = U | cand[pool[i]];
                    if (popc(U2) > n) continue;
                    set.push_back(pool[i]);
                    rec(i + 1, U2);
                    set.pop_back();
                }
            };
            rec(0, 0);
        }
    }
    // n-Y-wings, n = 6..9: a pivot with k = n-1 digits, one bivalue pincer {a_i, z} seeing it for
    // each pivot digit a_i -> z (not a pivot digit) is in some pincer -> it leaves the cells seeing
    // every pincer
    for (int P0 = 0; P0 < N; ++P0) {
        if (vals[P0]) continue;
        const int k = popc(cand[P0]);
        if (k < 5 || k > 8) continue;
        for (int z = 1; z <= p.D; ++z) {
            if (cand[P0] & bit(z)) continue;
            std::vector<std::vector<int>> pin;
            bool ok = true;
            for (uint32_t m = cand[P0]; m && ok; m &= m - 1) {
                const uint32_t want = (m & (~m + 1)) | bit(z);
                std::vector<int> qs;
                for (int q : p.peer_list[P0])
                    if (!vals[q] && cand[q] == want) qs.push_back(q);
                if (qs.empty()) ok = false;
                pin.push_back(qs);
            }
            if (!ok) continue;
            pm_long combos = 1;
            for (auto& v : pin) combos *= (pm_long)v.size();
            if (combos > 64) continue;  // bounded (all-or-none per pivot / digit)
            std::vector<int> ch(pin.size());
            std::function<void(size_t)> rec = [&](size_t i) {
                if (i == pin.size()) {
                    std::vector<int> key = ch;
                    std::sort(key.begin(), key.end());
                    if (std::unique(key.begin(), key.end()) != key.end()) return;
                    std::vector<uint32_t> el;
                    for (int q = 0; q < N; ++q) {
                        if (vals[q] || q == P0 || !(cand[q] & bit(z))) continue;
                        bool all = true;
                        for (int c : ch) all &= c != q && tbit(p.peers(c), q);
                        if (all) el.push_back((uint32_t)q * 32u + z);
                    }
                    if (el.empty()) return;
                    std::vector<int> pc{P0};
                    pc.insert(pc.end(), ch.begin(), ch.end());
                    const int n = (int)pc.size();
                    Move& m = new_move(out, N_WING, pspread(pc), n);
                    for (uint32_t e : el) addel(out, m, (int)(e / 32), (int)(e % 32));
                    set_pattern(out, m, pc);
                    meta_set(m, n, n, n, n - 1, 0, 0, 0, 1, m.shape);
                    m.code = 4600 + n;
                    pm_long xm[XM_N] = {n, z, (pm_long)ch.size(), (pm_long)el.size(), 0, 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                    return;
                }
                for (int q : pin[i]) {
                    ch[i] = q;
                    rec(i + 1);
                }
            };
            rec(0);
        }
    }
}

// ------------------------------------------------------------- SueDeCoq --
void Solver::sue_de_coq(MoveBuf& out) {
    if (disabled[SUE_DE_COQ]) return;
    for (size_t ia = 0; ia < p.houses.size(); ++ia)
        for (size_t ib = 0; ib < p.houses.size(); ++ib) {
            const int line = p.houses[ia], box = p.houses[ib];
            if (line == box || p.group_line[line] > 1 || p.group_line[box] != 2) continue;
            if (!p.group_overlap[(size_t)line * p.G + box]) continue;
            std::vector<int> inter, lrest, brest;
            for (int c : p.groups[line].cells) {
                if (vals[c]) continue;
                if (tbit(p.gbits(box), c)) inter.push_back(c);
                else lrest.push_back(c);
            }
            for (int c : p.groups[box].cells)
                if (!vals[c] && !tbit(p.gbits(line), c)) brest.push_back(c);
            if (inter.size() < 2) continue;
            // C: every subset of the intersection of size >= 2
            const int ni = (int)inter.size();
            for (int cm = 1; cm < (1 << ni); ++cm) {
                if (__builtin_popcount(cm) < 2) continue;
                std::vector<int> C;
                uint32_t V = 0;
                for (int i = 0; i < ni; ++i)
                    if (cm >> i & 1) C.push_back(inter[i]), V |= cand[inter[i]];
                if (popc(V) < (int)C.size() + 2) continue;
                auto subsets = [&](const std::vector<int>& from, std::vector<std::pair<std::vector<int>, uint32_t>>& outs) {
                    const int n = (int)from.size();
                    for (int a = 0; a < n; ++a) {
                        if (!(cand[from[a]] & V)) continue;
                        outs.push_back({{from[a]}, cand[from[a]]});
                        for (int b = a + 1; b < n; ++b)
                            if (cand[from[b]] & V) outs.push_back({{from[a], from[b]}, cand[from[a]] | cand[from[b]]});
                    }
                };
                std::vector<std::pair<std::vector<int>, uint32_t>> Ls, Bs;
                subsets(lrest, Ls);
                subsets(brest, Bs);
                for (auto& L : Ls) {
                    // L must be "almost locked" around V: |VL| = |L| + 1 at most -> keep classic sizes
                    if (popc(L.second) > (int)L.first.size() + 1) continue;
                    for (auto& B : Bs) {
                        if (popc(B.second) > (int)B.first.size() + 1) continue;
                        if (L.second & B.second) continue;
                        const uint32_t U = V | L.second | B.second;
                        const int n = (int)(C.size() + L.first.size() + B.first.size());
                        if (popc(U) != n) continue;
                        std::vector<uint32_t> el;
                        const uint32_t lineX = (L.second | V) & ~B.second, boxX = (B.second | V) & ~L.second;
                        for (int c : lrest)
                            if (std::find(L.first.begin(), L.first.end(), c) == L.first.end())
                                for (uint32_t b = cand[c] & lineX; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                        for (int c : brest)
                            if (std::find(B.first.begin(), B.first.end(), c) == B.first.end())
                                for (uint32_t b = cand[c] & boxX; b; b &= b - 1) el.push_back((uint32_t)c * 32u + lowdigit(b));
                        for (int c : inter)  // intersection cells outside C: both houses
                            if (std::find(C.begin(), C.end(), c) == C.end())
                                for (uint32_t b = cand[c] & (lineX | boxX); b; b &= b - 1)
                                    el.push_back((uint32_t)c * 32u + lowdigit(b));
                        std::sort(el.begin(), el.end());
                        el.erase(std::unique(el.begin(), el.end()), el.end());
                        if (el.empty()) continue;
                        std::vector<int> pc = C;
                        pc.insert(pc.end(), L.first.begin(), L.first.end());
                        pc.insert(pc.end(), B.first.begin(), B.first.end());
                        Move& m = new_move(out, SUE_DE_COQ, pspread(pc), n);
                        for (uint32_t e : el) addel(out, m, (int)(e / 32), (int)(e % 32));
                        set_pattern(out, m, pc);
                        add_expl(out, m, EX_BASE, {line, box});
                        meta_set(m, n, 2, popc(U), 2, 0, 0, 0, 1, m.shape);
                        m.code = 4701;
                        pm_long xm[XM_N] = {(pm_long)C.size(), (pm_long)L.first.size(), (pm_long)B.first.size(), (pm_long)U,
                                         (pm_long)el.size(), 0, 0, 0, 0, 0};
                        std::copy(xm, xm + XM_N, m.xm);
                    }
                }
            }
        }
}

// ------------------------------------------------ AlignedPairExclusion --
void Solver::aligned_pair(MoveBuf& out) {
    if (disabled[APE]) return;
    const int N = p.N;
    for (int X = 0; X < N; ++X) {
        if (vals[X] || popc(cand[X]) < 2) continue;
        for (int Y : p.peer_list[X]) {
            if (Y <= X || vals[Y] || popc(cand[Y]) < 2) continue;
            // cells seeing both, with few candidates
            std::vector<int> Z;
            for (int q : p.peer_list[X])
                if (q != Y && !vals[q] && popc(cand[q]) <= 2 && tbit(p.peers(Y), q)) Z.push_back(q);
            if (Z.empty()) continue;
            uint32_t okX = 0, okY = 0;
            for (uint32_t mx = cand[X]; mx; mx &= mx - 1) {
                const int x = lowdigit(mx);
                for (uint32_t my = cand[Y]; my; my &= my - 1) {
                    const int y = lowdigit(my);
                    if (x == y) continue;  // X and Y see each other
                    bool dead = false;
                    for (int q : Z) dead |= !(cand[q] & ~(bit(x) | bit(y)));
                    if (!dead) okX |= bit(x), okY |= bit(y);
                }
            }
            const uint32_t ex = cand[X] & ~okX, ey = cand[Y] & ~okY;
            if (!ex && !ey) continue;
            if (!okX || !okY) continue;  // inconsistent state
            Move& m = new_move(out, APE, pspread({X, Y}), (int)Z.size());
            for (uint32_t b = ex; b; b &= b - 1) addel(out, m, X, lowdigit(b));
            for (uint32_t b = ey; b; b &= b - 1) addel(out, m, Y, lowdigit(b));
            std::vector<int> pc{X, Y};
            pc.insert(pc.end(), Z.begin(), Z.end());
            set_pattern(out, m, pc);
            meta_set(m, (int)pc.size(), 2, popc(cand[X] | cand[Y]), 1, 0, 0, 0, 1, m.shape);
            m.code = 4801;
            pm_long xm[XM_N] = {X, Y, (pm_long)Z.size(), popc(ex) + popc(ey), 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

// --------------------------------------------------- ChuteRemotePairs --
void Solver::chute_remote_pairs(MoveBuf& out) {
    if (disabled[CHUTE_RP]) return;
    if (p.D != 9) return;
    // standard geometry: rows / cols / 3x3 boxes by coordinates
    // the nine coordinate 3x3 boxes must be houses (not jigsaw regions)
    {
        std::set<std::vector<uint64_t>> hs;
        for (int gi : p.houses) hs.insert(std::vector<uint64_t>(p.gbits(gi), p.gbits(gi) + p.W));
        for (int b = 0; b < 9; ++b) {
            std::vector<uint64_t> bx(p.W, 0);
            int n = 0;
            for (int c = 0; c < p.N; ++c)
                if (p.coords[c].first / 3 == b / 3 && p.coords[c].second / 3 == b % 3 && p.coords[c].first < 9 &&
                    p.coords[c].second < 9)
                    sbit(bx.data(), c), ++n;
            if (n != 9 || !hs.count(bx)) return;
        }
    }
    auto box_of = [&](int c) { return (p.coords[c].first / 3) * 3 + p.coords[c].second / 3; };
    for (int A = 0; A < p.N; ++A) {
        if (vals[A] || popc(cand[A]) != 2) continue;
        for (int B = A + 1; B < p.N; ++B) {
            if (vals[B] || cand[B] != cand[A] || tbit(p.peers(A), B)) continue;
            const int ra = p.coords[A].first, ca = p.coords[A].second, rb = p.coords[B].first, cb = p.coords[B].second;
            for (int orient = 0; orient < 2; ++orient) {
                // orient 0: same band (rows), different rows; 1: same stack (cols)
                const int la = orient ? ca : ra, lb = orient ? cb : rb, ka = orient ? ra : ca, kb = orient ? rb : cb;
                if (la / 3 != lb / 3 || la == lb || ka / 3 == kb / 3) continue;
                const int line3 = (la / 3) * 3 + (3 - la % 3 - lb % 3);  // remaining line of the chute
                const int seg3 = 3 - ka / 3 - kb / 3;                    // the third box's position
                std::vector<int> cells3;
                for (int t = 0; t < 3; ++t) {
                    int r = orient ? seg3 * 3 + t : line3, c = orient ? line3 : seg3 * 3 + t;
                    for (int q = 0; q < p.N; ++q)
                        if (p.coords[q].first == r && p.coords[q].second == c) cells3.push_back(q);
                }
                if (cells3.size() != 3) continue;
                const int x = lowdigit(cand[A]), y = lowdigit(cand[A] & (cand[A] - 1));
                for (int t = 0; t < 2; ++t) {
                    const int absent = t ? y : x, other = t ? x : y;
                    bool present = false;
                    for (int q : cells3) present |= vals[q] == absent || (!vals[q] && (cand[q] & bit(absent)));
                    if (present) continue;
                    std::vector<uint32_t> el;
                    for (int q = 0; q < p.N; ++q)
                        if (q != A && q != B && !vals[q] && (cand[q] & bit(other)) && tbit(p.peers(A), q) &&
                            tbit(p.peers(B), q))
                            el.push_back((uint32_t)q * 32u + other);
                    if (el.empty()) continue;
                    std::vector<int> pc{A, B};
                    pc.insert(pc.end(), cells3.begin(), cells3.end());
                    Move& m = new_move(out, CHUTE_RP, pspread(pc), 2);
                    for (uint32_t e : el) addel(out, m, (int)(e / 32), (int)(e % 32));
                    set_pattern(out, m, pc);
                    meta_set(m, 5, 3, 2, 2, 0, 0, 0, 1, m.shape);
                    m.code = 4901;
                    pm_long xm[XM_N] = {A, B, absent, other, (pm_long)el.size(), 0, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                }
                (void)box_of;
            }
        }
    }
}

// ------------------------------------------------------- PatternOverlay --
void Solver::pattern_overlay(MoveBuf& out) {
    if (disabled[POM]) return;
    // rows: complete groups of one orientation partitioning the board
    // lines: complete groups of one orientation partitioning the board (rows, else columns: the
    // template set is the same either way, so the choice does not depend on the orientation)
    std::vector<int> rows;
    for (int orient = 0; orient < 2 && (int)rows.size() != p.D; ++orient) {
        rows.clear();
        for (int gi : p.houses)
            if (p.group_line[gi] == orient && (int)p.groups[gi].cells.size() == p.D) rows.push_back(gi);
    }
    if ((int)rows.size() != p.D || p.D * p.D != p.N || p.D > 16) return;
    const pm_long CAP = 50000;  // templates per digit (all-or-none: the template set is invariant)
    const int R = (int)rows.size();
    // per-digit memo: the templates of v depend only on where v is placed or still a candidate
    const uint64_t memo_tag = 0x50AAULL;
    std::vector<uint64_t> vb(p.W);
    for (int v = 1; v <= p.D; ++v) {
        const uint32_t b = bit(v);
        std::fill(vb.begin(), vb.end(), 0);
        for (int c = 0; c < p.N; ++c)
            if (vals[c] == v || (!vals[c] && (cand[c] & b))) sbit(vb.data(), c);
        if (digit_memo_get(p, memo_tag, v, vb, out)) continue;
        const size_t memo_n0 = out.moves.size();
        struct Put {  // store this digit's moves on every way out of the loop body
            Solver& s; uint64_t tag; int v; const std::vector<uint64_t>& vb; MoveBuf& out; size_t n0;
            ~Put() { digit_memo_put(s.p, tag, v, vb, out, n0); }
        } put{*this, memo_tag, v, vb, out, memo_n0};
        std::vector<std::vector<int>> opts(R);
        for (int r = 0; r < R; ++r)
            for (int c : p.groups[rows[r]].cells)
                if (vals[c] == v || (!vals[c] && (cand[c] & b))) opts[r].push_back(c);
        std::vector<char> cover(p.N, 0);
        std::vector<int> pick;
        pm_long n = 0;
        bool abort = false;
        // forward checking: live options per row (bitmask over opts[r]); rows chosen most
        // constrained first
        std::vector<uint64_t> live(R);
        for (int r = 0; r < R; ++r) live[r] = opts[r].size() >= 64 ? ~0ULL : ((1ULL << opts[r].size()) - 1);
        std::vector<char> done(R, 0);
        std::function<void(int)> rec = [&](int depth) {
            if (abort) return;
            if (depth == R) {
                for (int gi : p.houses) {  // every complete group exactly once
                    int k = 0;
                    for (int c : pick) k += tbit(p.gbits(gi), c);
                    if (k != 1) return;
                }
                for (int c : pick) cover[c] = 1;
                if (++n > CAP) abort = true;
                return;
            }
            int r = -1, best = 99;
            for (int i = 0; i < R; ++i)
                if (!done[i] && __builtin_popcountll(live[i]) < best) best = __builtin_popcountll(live[i]), r = i;
            if (best == 0) return;
            done[r] = 1;
            for (uint64_t m = live[r]; m; m &= m - 1) {
                const int c = opts[r][__builtin_ctzll(m)];
                std::vector<uint64_t> save = live;
                bool dead = false;
                for (int i = 0; i < R && !dead; ++i) {
                    if (done[i]) continue;
                    for (uint64_t mm = live[i]; mm; mm &= mm - 1) {
                        const int j = __builtin_ctzll(mm);
                        if (tbit(p.peers(c), opts[i][j])) live[i] &= ~(1ULL << j);
                    }
                    dead = !live[i];
                }
                if (!dead) {
                    pick.push_back(c);
                    rec(depth + 1);
                    pick.pop_back();
                }
                live = save;
                if (abort) break;
            }
            done[r] = 0;
        };
        rec(0);
        if (abort || n == 0) continue;
        std::vector<uint32_t> el;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c] && (cand[c] & b) && !cover[c]) el.push_back((uint32_t)c * 32u + v);
        if (el.empty()) continue;
        Move& m = new_move(out, POM, 1.0, (int)std::min<pm_long>(n, 100000));
        for (uint32_t e : el) addel(out, m, (int)(e / 32), (int)(e % 32));
        std::vector<int> pc;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c] && (cand[c] & b)) pc.push_back(c);
        set_pattern(out, m, pc);
        meta_set(m, std::min(p.N, (int)pc.size()), p.D, 1, p.D, 0, 0, 0, 1, pspread(pc));
        m.code = 5001;
        pm_long xm[XM_N] = {v, n, (pm_long)el.size(), 0, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

// ---------------------------------------------------------------- Gurth --
void Solver::gurth(MoveBuf& out) {
    // grid symmetries are tested on coordinates (rot180 / transposes / rot90), which a relabelling
    // of rows within bands does not preserve: not symmetry-invariant -> opt-in (params "gurth")
    if (disabled[GURTH] || !opt.assume_unique || !P.gurth) return;
    if (!p.relations.empty() || !p.nary_specs.empty()) {
        // only the derived leftovers (consequences of the houses) are allowed
        if (!p.is_derived || p.base_nary != 0 || !p.relations.empty()) return;
    }
    for (int c = 0; c < p.N; ++c)
        if (p.domains[c] != p.full) return;
    // grid symmetries by coordinates (square boards): rot180, transpose, anti-transpose, rot90
    int R = 0, C = 0;
    for (int c = 0; c < p.N; ++c) R = std::max(R, p.coords[c].first + 1), C = std::max(C, p.coords[c].second + 1);
    if (R != C || R * C != p.N) return;
    std::map<std::pair<int, int>, int> at;
    for (int c = 0; c < p.N; ++c) at[p.coords[c]] = c;
    const int G0 = p.is_derived && p.base_G >= 0 ? p.base_G : p.G;
    std::vector<std::vector<uint64_t>> gsets;
    std::set<std::vector<uint64_t>> gs;
    for (int gi = 0; gi < G0; ++gi) gs.insert(std::vector<uint64_t>(p.gbits(gi), p.gbits(gi) + p.W));
    for (int t = 0; t < 4; ++t) {
        std::vector<int> sig(p.N);
        for (int c = 0; c < p.N; ++c) {
            const int r = p.coords[c].first, k = p.coords[c].second;
            std::pair<int, int> q = t == 0 ? std::make_pair(R - 1 - r, C - 1 - k)
                                  : t == 1 ? std::make_pair(k, r)
                                  : t == 2 ? std::make_pair(C - 1 - k, R - 1 - r)
                                           : std::make_pair(k, R - 1 - r);
            sig[c] = at[q];
        }
        // the groups map onto groups (with their totals)
        bool ok = true;
        for (int gi = 0; gi < G0 && ok; ++gi) {
            std::vector<uint64_t> img(p.W, 0);
            for (int c : p.groups[gi].cells) sbit(img.data(), sig[c]);
            ok = gs.count(img) > 0 && !p.groups[gi].has_total;
        }
        if (!ok) continue;
        // digit permutation from the givens (placed digits of the original clues = vals at start are
        // not tracked; use the current placed digits: a symmetric solution maps them consistently)
        std::vector<int> pi(p.D + 1, 0), inv(p.D + 1, 0);
        for (int c = 0; c < p.N && ok; ++c) {
            if (!vals[c]) continue;
            const int d = sig[c];
            if (!vals[d]) {
                ok = false;
                break;
            }
            const int a = vals[c], b2 = vals[d];
            if ((pi[a] && pi[a] != b2) || (inv[b2] && inv[b2] != a)) ok = false;
            pi[a] = b2;
            inv[b2] = a;
        }
        if (!ok) continue;
        // complete the permutation only if it is fully determined
        int known = 0;
        for (int v = 1; v <= p.D; ++v) known += pi[v] != 0;
        if (known < p.D - 1) continue;
        if (known == p.D - 1) {
            int a = 0, b2 = 0;
            for (int v = 1; v <= p.D; ++v) {
                if (!pi[v]) a = v;
                if (!inv[v]) b2 = v;
            }
            pi[a] = b2;
            inv[b2] = a;
        }
        // candidates must be symmetric: d at c <-> pi(d) at sig(c)
        std::vector<uint32_t> el;
        for (int c = 0; c < p.N; ++c) {
            if (vals[c]) continue;
            const int q = sig[c];
            if (vals[q]) continue;
            for (uint32_t m = cand[c]; m; m &= m - 1) {
                const int d = lowdigit(m);
                if (!(cand[q] & bit(pi[d]))) el.push_back((uint32_t)c * 32u + d);
            }
        }
        std::sort(el.begin(), el.end());
        el.erase(std::unique(el.begin(), el.end()), el.end());
        if (el.empty()) continue;
        Move& m = new_move(out, GURTH, 1.0, t);
        for (uint32_t e : el) addel(out, m, (int)(e / 32), (int)(e % 32));
        std::vector<int> pc;
        for (uint32_t e : el) pc.push_back((int)(e / 32));
        std::sort(pc.begin(), pc.end());
        pc.erase(std::unique(pc.begin(), pc.end()), pc.end());
        set_pattern(out, m, pc);
        meta_set(m, std::min(p.N, (int)pc.size() * 2), 2, p.D, 1, 0, 0, 0, 1, 1.0);
        m.code = 5101 + t;
        pm_long xm[XM_N] = {t, (pm_long)el.size(), 0, 0, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
        (void)gsets;
    }
}

}  // namespace cs

namespace cs {

// ------------------------------------------------------------ Fireworks --
// (sudokuwiki, Diabolical tier) A cell X, its row R, its column C and a region Bx holding X (complete houses).
// A digit d that is unplaced in R, C and Bx and whose candidates in R outside Bx are only A (or none) and in
// C outside Bx only B (or none) must sit in A, B or X: not in A -> R's d lies in Bx n R; not in B -> C's d lies
// in Bx n C; the region holds one d, so it is at (Bx n R) n (Bx n C) = X. Three digits confined like that to
// the same three cells {A, B, X} fill them (one digit per cell) -> every other candidate of A, B, X goes.
// Named pattern, no own price: priced by the structural meta model (Params::difficulty), descriptors in desc.cpp.
void Solver::fireworks(MoveBuf& out) {
    if (disabled[FIREWORKS]) return;
    const int D = p.D;
    std::vector<int> rows_of(p.N, -1), cols_of(p.N, -1);
    std::vector<std::vector<int>> regs_of(p.N);
    for (int g : p.houses) {
        if (!p.groups[g].complete || (int)p.groups[g].cells.size() != D) continue;
        for (int c : p.groups[g].cells) {
            if (p.group_line[g] == 0) rows_of[c] = g;
            else if (p.group_line[g] == 1) cols_of[c] = g;
            else regs_of[c].push_back(g);
        }
    }
    std::set<std::vector<uint32_t>> seen;
    for (int x = 0; x < p.N; ++x) {
        if (vals[x] || rows_of[x] < 0 || cols_of[x] < 0) continue;
        const int R = rows_of[x], C = cols_of[x];
        for (int bx : regs_of[x]) {
            const uint32_t placed = placed_g[R] | placed_g[C] | placed_g[bx];
            // per digit: the single candidate cell of R / C outside Bx (-1 none, -2 more than one)
            std::vector<int> ra(D + 1, -1), cb(D + 1, -1);
            auto scan = [&](int line, std::vector<int>& at) {
                for (int c : p.groups[line].cells) {
                    if (vals[c] || tbit(p.gbits(bx), c)) continue;
                    for (uint32_t m = cand[c] & ~placed; m; m &= m - 1) {
                        const int d = lowdigit(m);
                        at[d] = at[d] == -1 ? c : -2;
                    }
                }
            };
            scan(R, ra);
            scan(C, cb);
            // only digits with at most one place on each ray can take part; A / B must be such places
            int ndig = 0;
            std::vector<int> rowc, colc;
            for (int d = 1; d <= D; ++d) {
                if ((placed & bit(d)) || ra[d] == -2 || cb[d] == -2) continue;
                ++ndig;
                if (ra[d] >= 0 && std::find(rowc.begin(), rowc.end(), ra[d]) == rowc.end()) rowc.push_back(ra[d]);
                if (cb[d] >= 0 && std::find(colc.begin(), colc.end(), cb[d]) == colc.end()) colc.push_back(cb[d]);
            }
            if (ndig < 3 || rowc.empty() || colc.empty()) continue;
            std::sort(rowc.begin(), rowc.end());
            std::sort(colc.begin(), colc.end());
            for (int a : rowc)
                for (int b : colc) {
                    uint32_t ds = 0;
                    int n = 0;
                    for (int d = 1; d <= D; ++d) {
                        if (placed & bit(d)) continue;
                        if ((ra[d] == -1 || ra[d] == a) && (cb[d] == -1 || cb[d] == b)) {
                            // d must be at a, b or x: at least one of them must still allow it
                            if (!((cand[a] | cand[b] | cand[x]) & bit(d))) { n = 99; break; }
                            ds |= bit(d);
                            ++n;
                        }
                    }
                    if (n != 3) continue;  // > 3 digits in 3 cells: contradiction, left to other logic
                    std::vector<uint32_t> el;
                    for (int c : {a, b, x})
                        for (uint32_t m = cand[c] & ~ds; m; m &= m - 1) el.push_back((uint32_t)c * 32u + lowdigit(m));
                    if (el.empty()) continue;
                    std::sort(el.begin(), el.end());
                    if (!seen.insert(el).second) continue;
                    Move& m = new_move(out, FIREWORKS, 3.0, 3);
                    for (uint32_t e : el) addel(out, m, (int)(e / 32), (int)(e % 32));
                    meta_set(m, 3, 3, 3, 0, 1, 0, 0, 1, 1.0);
                    m.code = 5401;
                    m.nk = NM_GROUP;
                    m.na = bx;
                    set_pattern(out, m, {a, b, x});
                    pm_long xm[XM_N] = {x, a, b, (pm_long)ds, (pm_long)el.size(), bx, 0, 0, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                }
        }
    }
}

}  // namespace cs
