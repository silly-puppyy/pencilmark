#include <cstdio>
#include "portable.hpp"
#include "model.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <array>
#include <functional>
#include <map>
#include <set>
#include <unordered_map>

namespace cs {

double shape_ratio(const std::vector<std::pair<int, int>>& co) {
    // grader.model.shape_ratio; integer sums then true division, as Python
    pm_long n = (pm_long)co.size();
    if (n <= 1) return 1.0;
    pm_long sx = 0, sy = 0, sq = 0;
    for (auto& xy : co) {
        sx += xy.first;
        sy += xy.second;
        sq += (pm_long)xy.first * xy.first + (pm_long)xy.second * xy.second;
    }
    double mx = (double)sx / (double)n, my = (double)sy / (double)n, q = (double)sq / (double)n;
    double v = q - mx * mx - my * my;
    double rg = std::sqrt((0.0 > v) ? 0.0 : v);  // max(v, 0.0)
    double min_rg = std::sqrt((double)(n - 1) / 6.0);
    return min_rg != 0.0 ? rg / min_rg : 1.0;
}

double shape_ratio_exact(const std::vector<std::pair<int, int>>& co) {
    pm_long n = (pm_long)co.size();
    if (n <= 1) return 1.0;
    pm_long sx = 0, sy = 0, sq = 0;
    for (auto& xy : co) {
        sx += xy.first;
        sy += xy.second;
        sq += (pm_long)xy.first * xy.first + (pm_long)xy.second * xy.second;
    }
    pm_long num = n * sq - sx * sx - sy * sy;  // n^2 * variance, exact
    double rg = std::sqrt((double)std::max(num, pm_long(0))) / (double)n;
    double min_rg = std::sqrt((double)(n - 1) / 6.0);
    return rg / min_rg;
}

void Puzzle::finalize() {
    N = (int)coords.size();
    G = (int)groups.size();
    W = (N + 63) / 64;
    full = D >= 32 ? 0xffffffffu : ((1u << D) - 1);
    if ((int)domains.size() != N) domains.assign(N, full);
    for (auto& g : groups) {
        std::vector<std::pair<int, int>> co;
        for (int c : g.cells) co.push_back(coords[c]);
        g.shape = exact_shapes ? shape_ratio_exact(co) : shape_ratio(co);
    }
    houses.clear();
    for (int i = 0; i < G; ++i)
        if (groups[i].complete) houses.push_back(i);
    groups_of.assign(N, {});
    for (int gi = 0; gi < G; ++gi)
        for (int c : groups[gi].cells) groups_of[c].push_back(gi);

    // neq / relation partner sets, in CPython set order
    std::vector<PySet> neqS(N), relS(N);
    std::map<std::pair<int, int>, std::vector<uint32_t>> tabs;
    for (const auto& r : relations) {
        if (r.neq) {
            neqS[r.a].add(r.b);
            neqS[r.b].add(r.a);
            continue;
        }
        const int xs[2] = {r.a, r.b}, ys[2] = {r.b, r.a};
        const std::vector<uint32_t>* ts[2] = {&r.fwd, &r.bwd};
        for (int k = 0; k < 2; ++k) {
            auto& t = tabs[{xs[k], ys[k]}];
            if (t.empty()) t.assign(D + 1, 0);
            for (int v = 0; v <= D && v < (int)ts[k]->size(); ++v) t[v] |= (*ts[k])[v];
            relS[xs[k]].add(ys[k]);
        }
    }
    neq.assign(N, {});
    rel.assign(N, {});
    rel_out.assign(N, {});
    rel_in.assign(N, {});
    rel_sorted_j.assign(N, {});
    neq_bits.assign((size_t)N * W, 0);
    rel_bits.assign((size_t)N * W, 0);
    for (int c = 0; c < N; ++c) {
        for (int64_t q : neqS[c].items()) {
            neq[c].push_back((int)q);
            sbit(&neq_bits[(size_t)c * W], (int)q);
        }
        for (int64_t q : relS[c].items()) {
            rel[c].push_back((int)q);
            sbit(&rel_bits[(size_t)c * W], (int)q);
            const auto& to = tabs[{c, (int)q}];
            const auto& ti = tabs[{(int)q, c}];
            rel_out[c].insert(rel_out[c].end(), to.begin(), to.end());
            rel_in[c].insert(rel_in[c].end(), ti.begin(), ti.end());
        }
        auto& sj = rel_sorted_j[c];
        for (size_t j = 0; j < rel[c].size(); ++j) sj.push_back((int)j);
        std::sort(sj.begin(), sj.end(), [&](int a, int b) { return rel[c][a] < rel[c][b]; });
    }
    rel_dir.assign(N, {});
    for (int c = 0; c < N; ++c)
        for (size_t j = 0; j < rel[c].size(); ++j) {
            const uint32_t* t = &rel_out[c][j * (D + 1)];
            bool gt = true, lt = true;  // partner > c  /  partner < c
            for (int v = 1; v <= D; ++v) {
                uint32_t le = (v >= 32) ? 0xffffffffu : ((1u << v) - 1);  // digits 1..v
                uint32_t ge = full & ~((1u << (v - 1)) - 1);              // digits v..D
                gt &= t[v] == (le & full);
                lt &= t[v] == ge;
            }
            rel_dir[c].push_back(gt ? 1 : lt ? -1 : 0);
        }
    group_bits.assign((size_t)G * W, 0);
    for (int gi = 0; gi < G; ++gi)
        for (int c : groups[gi].cells) sbit(&group_bits[(size_t)gi * W], c);
    peer_bits.assign((size_t)N * W, 0);
    peer_list.assign(N, {});
    for (int c = 0; c < N; ++c) {
        uint64_t* pb = &peer_bits[(size_t)c * W];
        for (int gi : groups_of[c])
            for (int w = 0; w < W; ++w) pb[w] |= group_bits[(size_t)gi * W + w];
        for (int w = 0; w < W; ++w) pb[w] |= neq_bits[(size_t)c * W + w];
        pb[c >> 6] &= ~(1ULL << (c & 63));
        for (int q = 0; q < N; ++q)
            if (tbit(pb, q)) peer_list[c].push_back(q);
    }
    group_overlap.assign((size_t)G * G, 0);
    for (int a = 0; a < G; ++a)
        for (int b = 0; b < G; ++b) {
            bool ov = false;
            for (int w = 0; w < W && !ov; ++w) ov = group_bits[(size_t)a * W + w] & group_bits[(size_t)b * W + w];
            group_overlap[(size_t)a * G + b] = ov;
        }
    group_line.assign(G, 2);
    for (int gi = 0; gi < G; ++gi) {
        const auto& cl = groups[gi].cells;
        if (cl.size() < 2) continue;
        bool same_r = true, same_c = true;
        for (int c : cl) {
            same_r &= coords[c].first == coords[cl[0]].first;
            same_c &= coords[c].second == coords[cl[0]].second;
        }
        group_line[gi] = same_r ? 0 : same_c ? 1 : 2;
    }
    group_cat.assign(G, GC_IRREGULAR);
    for (int gi = 0; gi < G; ++gi) {
        const std::string& k = groups[gi].kind;
        int cat;
        if (k == "row" || k == "col") cat = GC_LINE;
        else if (k == "box") cat = GC_BOX;
        else if (k == "diag") cat = GC_DIAG;
        else if (k == "window" || k == "center") cat = GC_WINDOW;
        else if (k == "cage") cat = GC_CAGE;
        else if (k == "implied") cat = GC_IMPLIED;
        else if (k == "region" || k == "extra") cat = GC_IRREGULAR;
        else cat = groups[gi].has_total || !groups[gi].complete ? GC_CAGE : group_line[gi] < 2 ? GC_LINE : GC_IRREGULAR;
        group_cat[gi] = cat;
    }
    has_cages = false;
    sum_cages.clear();
    for (int gi = 0; gi < G; ++gi)
        if (groups[gi].has_total) {
            has_cages = true;
            sum_cages.push_back(gi);
        }
    innies.clear();
    big_innies.clear();
    house_unions.clear();
    if (!sum_cages.empty()) build_innies();
    build_nary();
    build_set_theory();
    rect_cache = std::make_shared<RectCache>();
    implied.reset();
    if (!is_derived) build_implied();
    canonical.reset();
    if (!is_derived && !exact_shapes) {
        auto q = std::make_shared<Puzzle>();
        q->D = D;
        q->coords = coords;
        q->groups = groups;
        q->domains = domains;
        q->relations = relations;
        q->nary_specs = nary_specs;
        q->exact_shapes = true;
        q->finalize();
        canonical = q;
    }
}

// ------------------------------------------------- implied structure (3d) --
void Puzzle::build_implied() {
    std::vector<std::vector<uint64_t>> newh;  // derived houses as bitsets
    std::set<std::vector<uint64_t>> known;
    for (int gi = 0; gi < G; ++gi)
        if (groups[gi].complete) known.insert(std::vector<uint64_t>(gbits(gi), gbits(gi) + W));
    auto popc64 = [&](const std::vector<uint64_t>& b) {
        int n = 0;
        for (uint64_t w : b) n += __builtin_popcountll(w);
        return n;
    };
    // rounds outermost, both orientations per round, each round seeing only the houses derived in
    // earlier rounds (Jacobi): rows and columns are treated alike (invariant under transposition)
    for (int round = 0; round < 2; ++round) {
        const std::vector<std::vector<uint64_t>> prev = newh;
      for (int orient = 0; orient < 2; ++orient) {
        std::vector<int> lines;
        for (int gi : houses)
            if (group_line[gi] == orient && (int)groups[gi].cells.size() == D) lines.push_back(gi);
        if (lines.size() > 30) continue;  // keep it cheap on huge boards
        {
            // removable houses: complete non-generator houses (+ derived in earlier rounds)
            std::vector<std::vector<uint64_t>> rem;
            for (int gi : houses)
                if (group_line[gi] != orient) rem.push_back(std::vector<uint64_t>(gbits(gi), gbits(gi) + W));
            for (auto& h : prev) rem.push_back(h);
            const int L = (int)lines.size();
            // 2026-10-25 (adopted): at most 3 lines combined (was 4; CSOLVER_IMPLIED_KMAX overrides). Overlap boards (duodoku)
            // gave 1,102 derived houses scanned by every technique at every step (card score 18 s -> 0.4 s with 3); no loss
            // of agreement with human data in A/B tests.
            static const int kmax = getenv("CSOLVER_IMPLIED_KMAX") ? atoi(getenv("CSOLVER_IMPLIED_KMAX")) : 3;
            for (int k = 2; k <= std::min(kmax, L); ++k) {
                std::vector<int> idx(k);
                std::function<void(int, int)> pick = [&](int st, int dep) {
                    if (dep == k) {
                        std::vector<uint64_t> U(W, 0);
                        for (int i : idx)
                            for (int w = 0; w < W; ++w) U[w] |= group_bits[(size_t)lines[i] * W + w];
                        std::vector<int> inside;
                        for (int r = 0; r < (int)rem.size(); ++r) {
                            bool in = true;
                            for (int w = 0; w < W && in; ++w) in = (rem[r][w] & ~U[w]) == 0;
                            if (in) inside.push_back(r);
                        }
                        if ((int)inside.size() < k - 1) return;
                        std::vector<int> ch(k - 1);
                        std::function<void(int, int, std::vector<uint64_t>)> sel = [&](int s0, int d2,
                                                                                         std::vector<uint64_t> S) {
                            if (d2 == k - 1) {
                                if (popc64(S) != D || known.count(S)) return;
                                known.insert(S);
                                newh.push_back(S);
                                return;
                            }
                            for (int j = s0; j < (int)inside.size(); ++j) {
                                const auto& h = rem[inside[j]];
                                bool sub = true;  // must lie in what is left (pairwise disjoint)
                                for (int w = 0; w < W && sub; ++w) sub = (h[w] & ~S[w]) == 0;
                                if (!sub) continue;
                                std::vector<uint64_t> S2(S);
                                for (int w = 0; w < W; ++w) S2[w] &= ~h[w];
                                sel(j + 1, d2 + 1, S2);
                            }
                        };
                        sel(0, 0, U);
                        return;
                    }
                    for (int i = st; i < L; ++i) {
                        idx[dep] = i;
                        pick(i + 1, dep + 1);
                    }
                };
                pick(0, 0);
            }
        }
      }
    }
    // law of leftovers: k parallel lines vs k disjoint non-line houses
    std::vector<NSpec> lol;
    // a set equivalence that is one line against one regular box in disguise (A = box \ line, B = line \ box or
    // the reverse) says no more than pointing / claiming: LockedCandidates names and prices it
    auto claiming_dup = [&](const std::vector<int>& A, const std::vector<int>& B) {
        if (A.size() != B.size() || A.empty()) return false;
        for (int l = 0; l < G; ++l) {
            if (!groups[l].complete || group_line[l] >= 2) continue;
            for (int x = 0; x < G; ++x) {
                if (group_cat[x] != GC_BOX || !groups[x].complete) continue;
                std::vector<int> lx, xl;
                for (int c : groups[l].cells)
                    if (!tbit(gbits(x), c)) lx.push_back(c);
                for (int c : groups[x].cells)
                    if (!tbit(gbits(l), c)) xl.push_back(c);
                if (lx.size() != A.size()) continue;
                std::sort(lx.begin(), lx.end());
                std::sort(xl.begin(), xl.end());
                if ((lx == A && xl == B) || (lx == B && xl == A)) return true;
            }
        }
        return false;
    };
    std::set<std::pair<std::vector<int>, std::vector<int>>> seen_lol;
    for (int orient = 0; orient < 2; ++orient) {
        std::vector<int> lines;
        for (int gi : houses)
            if (group_line[gi] == orient && (int)groups[gi].cells.size() == D) lines.push_back(gi);
        std::sort(lines.begin(), lines.end(), [&](int a, int b) {
            return orient == 0 ? coords[groups[a].cells[0]].first < coords[groups[b].cells[0]].first
                               : coords[groups[a].cells[0]].second < coords[groups[b].cells[0]].second;
        });
        std::vector<int> regs;
        for (int gi : houses)
            if (group_line[gi] == 2 && (int)groups[gi].cells.size() == D) regs.push_back(gi);
        const int L = (int)lines.size();
        // line sets: any k parallel lines (k <= 4; k <= 3 on boards with > 12 lines),
        // leftovers <= 6 cells; symmetric under line permutations (no "consecutive" test)
        std::vector<std::vector<int>> line_sets;
        const int kmax = std::min(L <= 12 ? 4 : 3, L);
        for (int k = 1; k <= kmax; ++k) {
            std::vector<int> idx(k);
            std::function<void(int, int)> pick = [&](int st, int dep) {
                if (dep == k) {
                    line_sets.push_back(idx);
                    return;
                }
                for (int i = st; i < L; ++i) {
                    idx[dep] = i;
                    pick(i + 1, dep + 1);
                }
            };
            pick(0, 0);
        }
        for (const auto& ls : line_sets) {
            {
                const int k = (int)ls.size();
                const size_t maxleft = 6;
                std::vector<uint64_t> U(W, 0);
                for (int i : ls)
                    for (int w = 0; w < W; ++w) U[w] |= group_bits[(size_t)lines[i] * W + w];
                // leftovers <= maxleft on both sides => the k regions overlap U in >= |U| - maxleft
                // cells, so each region overlaps U in >= D - maxleft cells (exact pruning)
                std::vector<int> touch, overl(G, 0);
                for (int r : regs) {
                    int ov = 0;
                    for (int w = 0; w < W; ++w) ov += __builtin_popcountll(group_bits[(size_t)r * W + w] & U[w]);
                    overl[r] = ov;
                    if (ov > 0 && ov >= D - (int)maxleft) touch.push_back(r);
                }
                if ((int)touch.size() < k || touch.size() > 12) continue;
                const int need = k * D - (int)maxleft;
                std::vector<int> ch;
                std::function<void(int)> sel = [&](int st) {
                    if ((int)ch.size() == k) {
                        std::vector<uint64_t> V(W, 0);
                        for (int r : ch)
                            for (int w = 0; w < W; ++w) V[w] |= group_bits[(size_t)r * W + w];
                        std::vector<int> A, B;
                        for (int c = 0; c < N; ++c) {
                            if (tbit(U.data(), c) && !tbit(V.data(), c)) A.push_back(c);
                            if (tbit(V.data(), c) && !tbit(U.data(), c)) B.push_back(c);
                        }
                        if (A.empty() || A.size() > maxleft || A.size() != B.size()) return;
                        // one line vs one regular box meeting it in a mini-line: exactly pointing / claiming,
                        // which LockedCandidates already names and prices (LoL stays for jigsaw regions and
                        // several houses per side)
                        if (k == 1 && group_cat[ch[0]] == GC_BOX) return;
                        if (claiming_dup(A, B)) return;
                        if (!seen_lol.insert({A, B}).second) return;
                        NSpec sp;
                        sp.type = NT_SAMESET;
                        sp.segs = {A, B};
                        bool irregular = false;  // jigsaw-style regions: law of leftovers (LOL), else SET
                        for (int r : ch) irregular |= group_cat[r] == GC_IRREGULAR;
                        sp.setkind = irregular ? 0 : 1;
                        for (int i : ls) sp.def_lines.push_back(lines[i]);
                        sp.def_regs = ch;
                        lol.push_back(sp);
                        return;
                    }
                    int got = 0;
                    for (int r : ch) got += overl[r];
                    if (got + (k - (int)ch.size()) * D < need) return;  // cannot reach the overlap
                    for (int i = st; i < (int)touch.size(); ++i) {
                        bool ok = true;
                        for (int r : ch) ok &= !group_overlap[(size_t)r * G + touch[i]];
                        if (!ok) continue;
                        ch.push_back(touch[i]);
                        sel(i + 1);
                        ch.pop_back();
                    }
                };
                sel(0);
            }
        }
    }
    // generalised set theory (Phistomefel family): rows R and columns C against |R|+|C| regions X;
    // every cell weighs (#rows of R through it) + (#columns of C) - (#regions of X); weights in {-1,0,1}:
    // the digits on the +1 cells equal (as a multiset) the digits on the -1 cells. Only with digit-value
    // rules (killers, sums, lines, relations: otherwise nothing uses it) and lines of D cells.
    {
        bool value_rules = has_cages || !nary_specs.empty();
        for (int c = 0; c < N && !value_rules; ++c) value_rules = !rel[c].empty();
        std::vector<int> rows, cols, regs;
        for (int gi : houses) {
            if ((int)groups[gi].cells.size() != D) continue;
            if (group_line[gi] == 0) rows.push_back(gi);
            else if (group_line[gi] == 1) cols.push_back(gi);
            else regs.push_back(gi);
        }
        const int nr = (int)rows.size(), nc = (int)cols.size(), ng = (int)regs.size();
        if (value_rules && nr == D && nc == D && ng == D && D <= 9 && N == D * D) {
            std::vector<int> rowof(N, -1), colof(N, -1), regof(N, -1);
            for (int i = 0; i < D; ++i) {
                for (int c : groups[rows[i]].cells) rowof[c] = i;
                for (int c : groups[cols[i]].cells) colof[c] = i;
                for (int c : groups[regs[i]].cells) regof[c] = i;
            }
            const size_t maxside = 12;
            std::vector<NSpec> found;
            // one (R, C) choice -> the equality (A = B as digit multisets) or none; side <= ms
            auto try_rc = [&](int R, int C, size_t ms, NSpec& sp) -> bool {
                const int k = __builtin_popcount(R) + __builtin_popcount(C);
                if (k == 0 || k > D) return false;
                std::vector<int> w(N);
                for (int c = 0; c < N; ++c) w[c] = ((R >> rowof[c]) & 1) + ((C >> colof[c]) & 1);
                std::vector<int> forced, freeb;
                std::vector<int> c1(D, 0), c0(D, 0);
                for (int g = 0; g < D; ++g) {
                    bool two = false;
                    for (int c : groups[regs[g]].cells) {
                        two |= w[c] == 2;
                        c1[g] += w[c] == 0;
                        c0[g] += w[c] == 1;
                    }
                    if (two) forced.push_back(g);
                    else freeb.push_back(g);
                }
                const int need = k - (int)forced.size();
                if (need < 0 || need > (int)freeb.size()) return false;
                std::vector<std::pair<int, int>> gain;
                for (int g : freeb) gain.push_back({c1[g] - c0[g], g});
                std::sort(gain.begin(), gain.end());
                if (need > 0 && need < (int)gain.size() && gain[need - 1].first == gain[need].first) return false;
                int X = 0;
                for (int g : forced) X |= 1 << g;
                for (int t = 0; t < need; ++t) X |= 1 << gain[t].second;
                std::vector<int> A, B;
                for (int c = 0; c < N; ++c) {
                    const int ww = w[c] - ((X >> regof[c]) & 1);
                    if (ww == 1) A.push_back(c);
                    else if (ww == -1) B.push_back(c);
                    else if (ww != 0) return false;
                }
                if (A.empty() || A.size() != B.size() || A.size() > ms) return false;
                sp = NSpec();
                sp.type = NT_SAMESET;
                sp.segs = {A, B};
                for (int i = 0; i < D; ++i) {
                    if ((R >> i) & 1) sp.def_lines.push_back(rows[i]);
                    if ((C >> i) & 1) sp.def_lines.push_back(cols[i]);
                    if ((X >> i) & 1) sp.def_regs.push_back(regs[i]);
                }
                return true;
            };
            // named Phistomefel family on the standard 3x3 boxes, outside the size cap: rows = columns =
            // a mirror-symmetric set of lines (one or two of the line pairs {i, D-1-i}: the ring of the
            // 2x2 corners, the 3x3-corner / edge variants), plus the same rows (or columns) alone
            if (D == 9) {
                bool std_boxes = true;
                for (int c = 0; c < N && std_boxes; ++c) {
                    const int br = coords[c].first / 3, bc = coords[c].second / 3;
                    for (int c2 = 0; c2 < c && std_boxes; ++c2)
                        if ((regof[c] == regof[c2]) != (coords[c2].first / 3 == br && coords[c2].second / 3 == bc))
                            std_boxes = false;
                }
                std::vector<int> sym;
                for (int i = 0; i < 4; ++i) sym.push_back((1 << i) | (1 << (8 - i)));
                for (int i = 0; i < 4; ++i)
                    for (int j = i + 1; j < 4; ++j) sym.push_back(sym[i] | sym[j]);
                for (int S : std_boxes ? sym : std::vector<int>{})
                    for (int v = 0; v < 3; ++v) {
                        const int R = v == 2 ? 0 : S, C = v == 1 ? 0 : S;
                        NSpec sp;
                        if (!try_rc(R, C, 20, sp)) continue;
                        sp.setkind = (R == 0b110000011 && C == 0b110000011) ? 2 : 4;  // the ring / a variant
                        if (seen_lol.insert({sp.segs[0], sp.segs[1]}).second) lol.push_back(sp);
                    }
            }
            for (int R = 0; R < (1 << D); ++R) {
                if (__builtin_popcount(R) > 4) continue;
                for (int C = 0; C < (1 << D); ++C) {
                    const int k = __builtin_popcount(R) + __builtin_popcount(C);
                    if (__builtin_popcount(C) > 4 || k == 0 || k > D) continue;
                    // per region: forced (has a weight-2 cell), cost if chosen (cells of weight 0 -> -1)
                    // vs not chosen (cells of weight 1 stay +1)
                    std::vector<int> w(N);
                    for (int c = 0; c < N; ++c) w[c] = ((R >> rowof[c]) & 1) + ((C >> colof[c]) & 1);
                    std::vector<int> forced, freeb;
                    std::vector<int> c1(D, 0), c0(D, 0);
                    for (int g = 0; g < D; ++g) {
                        bool two = false;
                        for (int c : groups[regs[g]].cells) {
                            two |= w[c] == 2;
                            c1[g] += w[c] == 0;  // chosen: weight-0 cells become -1
                            c0[g] += w[c] == 1;  // not chosen: weight-1 cells stay +1
                        }
                        if (two) forced.push_back(g);
                        else freeb.push_back(g);
                    }
                    const int need = k - (int)forced.size();
                    if (need < 0 || need > (int)freeb.size()) continue;
                    std::vector<std::pair<int, int>> gain;  // (c1 - c0, region): choose the smallest
                    for (int g : freeb) gain.push_back({c1[g] - c0[g], g});
                    std::sort(gain.begin(), gain.end());
                    if (need > 0 && need < (int)gain.size() && gain[need - 1].first == gain[need].first) continue;  // tie
                    int X = 0;
                    for (int g : forced) X |= 1 << g;
                    for (int t = 0; t < need; ++t) X |= 1 << gain[t].second;
                    std::vector<int> A, B;
                    bool bad = false;
                    for (int c = 0; c < N && !bad; ++c) {
                        const int ww = w[c] - ((X >> regof[c]) & 1);
                        if (ww == 1) A.push_back(c);
                        else if (ww == -1) B.push_back(c);
                        else if (ww != 0) bad = true;
                    }
                    if (bad || A.empty() || A.size() != B.size() || A.size() > maxside) continue;
                    if (seen_lol.count({A, B})) continue;
                    bool dup = false;
                    for (auto& f : found) dup |= f.segs[0] == A && f.segs[1] == B;
                    if (dup) continue;
                    NSpec sp;
                    sp.type = NT_SAMESET;
                    sp.segs = {A, B};
                    sp.setkind = 3;  // generalised set theory
                    for (int i = 0; i < D; ++i) {
                        if ((R >> i) & 1) sp.def_lines.push_back(rows[i]);
                        if ((C >> i) & 1) sp.def_lines.push_back(cols[i]);
                        if ((X >> i) & 1) sp.def_regs.push_back(regs[i]);
                    }
                    found.push_back(sp);
                }
            }
            // keep the smallest ones: all of size <= t for the largest t with <= 24 of them (a size
            // threshold, so the kept set does not depend on the enumeration order; bounded memory / work)
            size_t t = maxside;
            auto count_le = [&](size_t z) {
                size_t n = 0;
                for (auto& f : found) n += f.segs[0].size() <= z;
                return n;
            };
            while (t > 0 && count_le(t) > 24) --t;
            for (auto& f : found)
                if (f.segs[0].size() <= t && !claiming_dup(f.segs[0], f.segs[1]) &&  // = pointing / claiming
                    seen_lol.insert({f.segs[0], f.segs[1]}).second)
                    lol.push_back(f);
        }
    }
    // Phistomefel ring (standard 9x9 with digit-value rules: killers, variants): the four corner
    // 2x2 blocks hold the same digits as the ring of 16 cells around the centre box
    if (D == 9 && N == 81) {
        std::map<std::pair<int, int>, int> at;
        for (int c = 0; c < N; ++c) at[coords[c]] = c;
        bool standard = at.size() == 81;
        for (int br = 0; br < 3 && standard; ++br)
            for (int bc = 0; bc < 3 && standard; ++bc) {
                std::vector<uint64_t> bx(W, 0);
                for (int r = 0; r < 3; ++r)
                    for (int k = 0; k < 3; ++k) {
                        auto it = at.find({br * 3 + r, bc * 3 + k});
                        if (it == at.end()) standard = false;
                        else sbit(bx.data(), it->second);
                    }
                standard = standard && known.count(bx) > 0;
            }
        bool value_rules = has_cages || !nary_specs.empty();
        for (int c = 0; c < N && !value_rules; ++c) value_rules = !rel[c].empty();
        if (standard && value_rules) {
            NSpec sp;
            sp.type = NT_SAMESET;
            std::vector<int> A, B;
            for (int r : {0, 1, 7, 8})
                for (int k : {0, 1, 7, 8}) A.push_back(at[{r, k}]);
            for (int r = 2; r <= 6; ++r)
                for (int k = 2; k <= 6; ++k)
                    if (r == 2 || r == 6 || k == 2 || k == 6) B.push_back(at[{r, k}]);
            std::sort(A.begin(), A.end());
            std::sort(B.begin(), B.end());
            sp.segs = {A, B};
            sp.setkind = 2;  // Phistomefel
            if (seen_lol.insert({A, B}).second) lol.push_back(sp);
        }
    }
    if (newh.empty() && lol.empty()) return;
    auto q = std::make_shared<Puzzle>();
    q->D = D;
    q->coords = coords;
    q->groups = groups;
    q->domains = domains;
    q->relations = relations;
    q->nary_specs = nary_specs;
    q->is_derived = true;
    q->exact_shapes = exact_shapes;
    q->base_G = G;
    q->base_nary = (int)nary_specs.size();
    int k = 0;
    for (auto& h : newh) {
        Group g;
        g.name = "implied" + std::to_string(++k);
        g.kind = "implied";
        g.complete = true;
        for (int c = 0; c < N; ++c)
            if (tbit(h.data(), c)) g.cells.push_back(c);
        q->groups.push_back(g);
    }
    for (auto& sp : lol) q->nary_specs.push_back(sp);
    if (getenv("CSOLVER_IMPLIED_DEBUG"))   // 2026-10-25 speed diagnosis: how much the implied puzzle adds
        fprintf(stderr, "implied: %zu derived houses, %zu leftover rules, %zu set-theory rules\n", newh.size(), lol.size(), q->nary_specs.size() - lol.size() - nary_specs.size());
    q->finalize();
    implied = q;
}

// unique rectangles: A,B,C,D with every group touching them containing
// exactly {A,B}, {C,D}, {A,C} or {B,D}; no neq link to outside cells; n-ary
// scopes touching them only sums/sets/same-segment sums containing such a pair
const std::vector<Puzzle::Rect>& Puzzle::rects() const {
    std::call_once(rect_cache->once, [&]() {
        auto& out = rect_cache->rects;
        if (N > 400) return;  // enumeration cost; uniqueness patterns skipped on huge boards
        auto share = [&](int a, int b) {
            for (int gi : groups_of[a])
                if (tbit(gbits(gi), b)) return true;
            return false;
        };
        std::set<std::array<int, 4>> seen;
        for (int A = 0; A < N; ++A) {
            if (!neq[A].empty()) continue;
            for (int gi : groups_of[A])
                for (int B : groups[gi].cells) {
                    if (B <= A || !neq[B].empty()) continue;
                    for (int gj : groups_of[A])
                        for (int C : groups[gj].cells) {
                            if (C <= A || C == B || share(B, C) || !neq[C].empty()) continue;
                            for (int gk : groups_of[B])
                                for (int Dd : groups[gk].cells) {
                                    if (Dd == A || Dd == B || Dd == C || share(A, Dd) || !share(C, Dd) ||
                                        !neq[Dd].empty())
                                        continue;
                                    std::array<int, 4> key = {A, B, C, Dd};
                                    std::array<int, 4> srt = key;
                                    std::sort(srt.begin(), srt.end());
                                    if (!seen.insert(srt).second) continue;
                                    const int r[4] = {A, B, C, Dd};
                                    bool ok = true;
                                    auto pair_ok = [&](unsigned m) {
                                        return m == 0 || m == 3 || m == 12 || m == 5 || m == 10;  // AB CD AC BD
                                    };
                                    std::set<int> gs;
                                    for (int i = 0; i < 4; ++i)
                                        for (int g2 : groups_of[r[i]]) gs.insert(g2);
                                    for (int g2 : gs) {
                                        // implied houses follow from the original houses: a swap
                                        // keeping those valid keeps them valid
                                        if (is_derived && base_G >= 0 && g2 >= base_G) continue;
                                        unsigned m = 0;
                                        for (int i = 0; i < 4; ++i)
                                            if (tbit(gbits(g2), r[i])) m |= 1u << i;
                                        if (!pair_ok(m)) ok = false;
                                    }
                                    for (const NConstraint& k : nary) {
                                        if (!ok) break;
                                        if (k.type == NT_LINE) continue;  // its pair relations are checked per digit pair
                                        if (is_derived && base_nary >= 0 && k.index >= base_nary)
                                            continue;  // derived leftovers: implied by the houses
                                        unsigned m = 0;
                                        for (int i = 0; i < 4; ++i)
                                            for (size_t p = 0; p < k.pvar.size(); ++p)
                                                if (k.vars[k.pvar[p]] == r[i]) m |= 1u << i;
                                        if (!m) continue;
                                        if (!pair_ok(m) || (k.pvar.size() != k.vars.size())) {
                                            ok = false;
                                            continue;
                                        }
                                        if (k.type == NT_SUM || k.type == NT_SET) continue;
                                        if (k.type == NT_EQSUM || k.type == NT_SAMESET) {
                                            int segs = 0;  // both cells in one segment
                                            for (size_t s = 0; s + 1 < k.seg_start.size(); ++s) {
                                                int in = 0;
                                                for (int p = k.seg_start[s]; p < k.seg_start[s + 1]; ++p)
                                                    for (int i = 0; i < 4; ++i)
                                                        if ((m >> i & 1) && k.vars[k.pvar[p]] == r[i]) ++in;
                                                if (in) ++segs;
                                            }
                                            if (segs == 1) continue;
                                        }
                                        ok = false;
                                    }
                                    if (ok) out.push_back(Rect{{A, B, C, Dd}});
                                }
                        }
                }
        }
    });
    return rect_cache->rects;
}

NConstraint Puzzle::make_nc(int type, const std::vector<int>& positions, bool distinct) const {
    NConstraint k;
    k.type = type;
    for (int c : positions) {
        auto it = std::find(k.vars.begin(), k.vars.end(), c);
        if (it == k.vars.end()) {
            k.pvar.push_back((int)k.vars.size());
            k.vars.push_back(c);
        } else {
            k.pvar.push_back((int)(it - k.vars.begin()));
        }
    }
    const int nv = (int)k.vars.size();
    k.distinct = distinct;
    k.arith = type == NT_SUM || type == NT_ARROW || type == NT_EQSUM || type == NT_SANDWICH || type == NT_XSUM;
    k.differ.assign((size_t)nv * nv, 0);
    k.rel.assign((size_t)nv * nv, nullptr);
    for (int i = 0; i < nv; ++i)
        for (int j = 0; j < nv; ++j) {
            if (i == j) continue;
            int ci = k.vars[i], cj = k.vars[j];
            k.differ[i * nv + j] = distinct || tbit(peers(ci), cj);
            if (tbit(relb(ci), cj)) k.rel[i * nv + j] = rel_ex(ci, cj);
        }
    for (int i = 0; i < nv; ++i) k.order.push_back(i);  // position order (arrow: circle first)
    std::vector<std::pair<int, int>> co;
    for (int c : k.vars) co.push_back(coords[c]);
    k.shape = exact_shapes ? shape_ratio_exact(co) : shape_ratio(co);
    if (type == NT_SAMESET && exact_shapes) {
        // derived (solver-made) region: structural spread, invariant under the
        // puzzle's symmetries: complete groups touched / (2 sqrt(n) + 1)
        std::set<int> gs;
        for (int c : k.vars)
            for (int gi : groups_of[c])
                if (groups[gi].complete) gs.insert(gi);
        k.shape = (double)gs.size() / (2.0 * std::sqrt((double)nv) + 1.0);
    }
    return k;
}

void Puzzle::build_nary() {
    nary.clear();
    cage_nary.clear();
    for (size_t idx = 0; idx < nary_specs.size(); ++idx) {
        const NSpec& s = nary_specs[idx];
        std::vector<int> pos = s.a;
        bool distinct = false;
        if (s.type == NT_SUM) {
            if (s.distinct >= 0) {
                distinct = s.distinct;
            } else {  // auto: all cells share a group
                distinct = false;
                if (!pos.empty())
                    for (int gi : groups_of[pos[0]]) {
                        bool all = true;
                        for (int c : pos)
                            if (!tbit(gbits(gi), c)) all = false;
                        if (all) distinct = true;
                    }
            }
        } else if (s.type == NT_SET) {
            distinct = true;
        }
        if (s.type == NT_SAMESET) {
            pos.clear();
        }
        std::vector<int> seg_start;
        if (s.type == NT_ARROW) {
            for (auto& seg : s.segs) pos.insert(pos.end(), seg.begin(), seg.end());
        } else if (s.type == NT_EQSUM || s.type == NT_SAMESET || s.type == NT_DIGITSET) {
            pos.clear();
            for (auto& seg : s.segs) {
                seg_start.push_back((int)pos.size());
                pos.insert(pos.end(), seg.begin(), seg.end());
            }
            seg_start.push_back((int)pos.size());
        }
        NConstraint k = make_nc(s.type, pos, distinct);
        k.index = (int)idx;
        k.total = s.total;
        k.totals = s.totals;
        k.ncircle = s.type == NT_ARROW ? (int)s.a.size() : 0;
        k.seg_start = seg_start;
        k.setkind = s.setkind;
        k.named = s.named;
        k.offset = s.offset;
        k.bounds_only = s.bounds_only;
        if (s.bounds_only && !s.segs.empty()) {  // parts: segs (pairwise distinct cell sets)
            k.part.assign(k.nv(), -1);
            for (size_t sg = 0; sg < s.segs.size(); ++sg)
                for (int c : s.segs[sg])
                    for (int i = 0; i < k.nv(); ++i)
                        if (k.vars[i] == c) k.part[i] = (int)sg;
            for (int i = 0; i < k.nv(); ++i)
                if (k.part[i] < 0) k.part[i] = (int)s.segs.size() + i;  // own part
            int np = 0;
            for (int q : k.part) np = std::max(np, q + 1);
            k.parts.assign(np, {});
            for (int i = 0; i < k.nv(); ++i) k.parts[k.part[i]].push_back(k.vars[i]);
            if (!s.seg_sign.empty()) {
                k.part_sign.assign(np, 1);
                for (size_t sg = 0; sg < s.segs.size() && sg < s.seg_sign.size(); ++sg) k.part_sign[sg] = s.seg_sign[sg];
            }
        }
        // a sum over cells that need not differ (little killers, long sums): split into parts of cells that share
        // a house (pairwise different digits) -- brute force / sub-puzzle searches then bound each part by distinct
        // digits ("the three cells in box 5 add up to at least 6")
        if (s.type == NT_SUM && !distinct && !s.bounds_only && s.offset == 0 && s.totals.empty() && k.nv() >= 3) {
            auto share = [&](int a, int b) {
                if (a == b) return false;
                for (int gi : groups_of[a])
                    if (groups[gi].complete && tbit(gbits(gi), b)) return true;
                return false;
            };
            std::vector<std::vector<int>> pp;
            std::vector<int> pi(k.nv(), -1);
            for (int i = 0; i < k.nv(); ++i) {
                const int c = k.vars[i];
                for (size_t q = 0; q < pp.size() && pi[i] < 0; ++q) {
                    bool ok = true;
                    for (int x : pp[q]) ok &= share(c, x);
                    if (ok) pp[q].push_back(c), pi[i] = (int)q;
                }
                if (pi[i] < 0) pi[i] = (int)pp.size(), pp.push_back({c});
            }
            if (pp.size() < (size_t)k.nv()) {  // some cells must differ: worth the part bounds
                k.part = pi;
                k.parts = pp;
            }
        }
        k.quota = s.quota;
        k.line_kind = s.line_kind;
        if (!k.quota.empty()) k.quota.resize(D + 1, -1);
        if (s.type == NT_TABLE) {
            k.arity = (int)s.a.size();
            for (auto& r : s.rows)
                for (int p = 0; p < k.arity; ++p) k.rows.push_back((uint8_t)(p < (int)r.size() ? r[p] : 0));
        }
        if (k.nv() > 64 || k.nv() == 0) continue;  // unsupported (kept out of the engine)
        nary.push_back(std::move(k));
    }
    // 2026-10-24 (adopted; CSOLVER_OVERLAP_DIFF=0 disables): overlapping sum clues -- two sums sharing >= 2 cells, each with a
    // small own part: sum(own part of A) - sum(own part of B) = total A - total B, as a derived rule over the own parts (<= 4
    // cells). Killer cages (groups) never trigger it.
    static const bool overlap_diff = !(getenv("CSOLVER_OVERLAP_DIFF") && getenv("CSOLVER_OVERLAP_DIFF")[0] == '0');
    if (overlap_diff) {
        std::vector<NConstraint> derived;
        const size_t n0 = nary.size();
        for (size_t x = 0; x < n0; ++x)
            for (size_t y = x + 1; y < n0; ++y) {
                const NConstraint& A = nary[x];
                const NConstraint& B = nary[y];
                if (A.type != NT_SUM || B.type != NT_SUM || !A.totals.empty() || !B.totals.empty() || A.bounds_only || B.bounds_only) continue;
                if ((int)A.pvar.size() != A.nv() || (int)B.pvar.size() != B.nv()) continue;   // cells counted once
                std::vector<int> a, b;
                int shared = 0;
                for (int c : A.vars) (std::find(B.vars.begin(), B.vars.end(), c) != B.vars.end() ? shared++ : (a.push_back(c), 0));
                for (int c : B.vars)
                    if (std::find(A.vars.begin(), A.vars.end(), c) == A.vars.end()) b.push_back(c);
                // >= 2 shared cells: a single shared corner (sum-frame clues) made the rule hurt (0.69 -> 0.61), humans use it where
                // neighbouring sums share a pair (group-sum 2x2 circles)
                if (shared < 2 || a.empty() || b.empty() || a.size() + b.size() > 4) continue;
                const int k = A.total - B.total, na = (int)a.size(), nb = (int)b.size();
                std::vector<int> pos = a;
                pos.insert(pos.end(), b.begin(), b.end());
                NConstraint t = make_nc(NT_TABLE, pos, false);
                t.arity = na + nb;
                std::vector<int> v(t.arity, 1);
                while (true) {                                  // every digit tuple with the right difference
                    int sa = 0, sb = 0;
                    for (int i = 0; i < na; ++i) sa += v[i];
                    for (int i = 0; i < nb; ++i) sb += v[na + i];
                    if (sa - sb == k)
                        for (int i = 0; i < t.arity; ++i) t.rows.push_back((uint8_t)v[i]);
                    int i = 0;
                    while (i < t.arity && ++v[i] > D) v[i++] = 1;
                    if (i == t.arity) break;
                }
                if (!t.rows.empty()) derived.push_back(std::move(t));   // index -1: derived
            }
        for (auto& t : derived) nary.push_back(std::move(t));
    }
    innie_nary.clear();
    for (const InnieSet& is : big_innies) {
        const int innie_idx = (int)(&is - big_innies.data());
        bool distinct = false;
        for (int gi : groups_of[is.cells[0]]) {
            bool all = true;
            for (int c : is.cells)
                if (!tbit(gbits(gi), c)) all = false;
            if (all) distinct = true;
        }
        NConstraint k = make_nc(NT_SUM, is.cells, distinct);
        k.total = is.total;
        k.house = is.hi;
        k.outie = is.outie;
        k.n_cages = (int)is.cages.size();
        k.innie = innie_idx;
        innie_nary.push_back(std::move(k));
    }
    line_windows.clear();
    for (const NConstraint& k : nary) {
        if (k.type != NT_LINE || k.nv() <= 3 || (int)k.pvar.size() != k.nv()) continue;
        for (int s = 0; s + 3 <= k.nv(); ++s) {
            NConstraint w = make_nc(NT_LINE, {k.vars[s], k.vars[s + 1], k.vars[s + 2]}, false);
            w.line_kind = k.line_kind;
            w.index = k.index;
            line_windows.push_back(std::move(w));
        }
    }
    for (int gi : sum_cages) {
        NConstraint k = make_nc(NT_SUM, groups[gi].cells, true);
        k.total = groups[gi].total;
        k.group = gi;
        if (k.nv() <= 64) cage_nary.push_back(std::move(k));
    }
}

// Solver._house_unions + Solver._innie_sets, with CPython set-of-tuple order
void Puzzle::build_innies() {
    const std::vector<int>& hs = houses;
    std::map<std::pair<int, int>, int> pos;
    for (int i = 0; i < N; ++i) pos[coords[i]] = i;
    auto disjoint = [&](int a, int b) { return !group_overlap[(size_t)a * G + b]; };
    std::unordered_map<int, PySet> nb;
    for (int h : hs) {
        std::vector<uint64_t> border(W, 0);
        for (int c : groups[h].cells) {
            int r = coords[c].first, cc = coords[c].second;
            const int dd[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
            for (auto& d : dd) {
                auto it = pos.find({r + d[0], cc + d[1]});
                if (it != pos.end() && !tbit(gbits(h), it->second)) sbit(border.data(), it->second);
            }
        }
        PySet s;
        for (int h2 : hs) {
            if (h2 == h || !disjoint(h, h2)) continue;
            bool touch = false;
            for (int w = 0; w < W && !touch; ++w) touch = group_bits[(size_t)h2 * W + w] & border[w];
            if (touch) s.add(h2);
        }
        nb[h] = s;
    }
    // interned tuples
    std::map<std::vector<int>, int64_t> intern;
    std::vector<std::vector<int>> tup;
    std::vector<int64_t> thash;
    auto get = [&](const std::vector<int>& v) -> int64_t {
        auto it = intern.find(v);
        if (it != intern.end()) return it->second;
        int64_t id = (int64_t)tup.size();
        intern[v] = id;
        tup.push_back(v);
        thash.push_back(py_tuple_hash(v.data(), (int)v.size()));
        return id;
    };
    PySet out;
    for (int h : hs) {
        int64_t id = get({h});
        out.add(id, thash[id]);
    }
    PySet frontier;
    frontier.merge(out);
    const int max_k = 3;
    for (int it = 0; it < max_k - 1; ++it) {
        PySet nxt;
        for (int64_t uid : frontier.items()) {
            std::vector<int> u = tup[uid];
            for (int h : u) {
                for (int64_t h2l : nb[h].items()) {
                    int h2 = (int)h2l;
                    bool skip = std::find(u.begin(), u.end(), h2) != u.end();
                    for (int x : u)
                        if (!skip && !disjoint(h2, x)) skip = true;
                    if (skip) continue;
                    std::vector<int> v = u;
                    v.push_back(h2);
                    std::sort(v.begin(), v.end());
                    int64_t id = get(v);
                    nxt.add(id, thash[id]);
                }
            }
        }
        out.merge(nxt);
        frontier = nxt;
    }
    std::vector<int64_t> order = out.items();
    std::stable_sort(order.begin(), order.end(),
                     [&](int64_t a, int64_t b) { return tup[a].size() < tup[b].size(); });
    const int tri = D * (D + 1) / 2;
    for (int64_t uid : order) {
        const std::vector<int>& un = tup[uid];
        house_unions.push_back(un);
        std::vector<uint64_t> H(W, 0);
        for (int h : un)
            for (int w = 0; w < W; ++w) H[w] |= group_bits[(size_t)h * W + w];
        int hi = un[0];
        int tri_u = tri * (int)un.size();
        std::vector<int> inside, touching;
        for (int gi : sum_cages) {
            bool sub = true, any = false;
            for (int c : groups[gi].cells) {
                if (tbit(H.data(), c))
                    any = true;
                else
                    sub = false;
            }
            if (sub)
                inside.push_back(gi);
            else if (any)
                touching.push_back(gi);
        }
        // the rule of 45 adds cage totals, so the cages used must be pairwise
        // disjoint (overlapping cage sets, e.g. twin killers): keep a disjoint
        // subset in group order (identical for ordinary killers)
        auto disjoint_subset = [&](const std::vector<int>& in, std::vector<uint64_t>& acc) {
            std::vector<int> outv;
            for (int gi : in) {
                bool ok = true;
                for (int w = 0; w < W && ok; ++w) ok = !(acc[w] & group_bits[(size_t)gi * W + w]);
                if (!ok) continue;
                outv.push_back(gi);
                for (int w = 0; w < W; ++w) acc[w] |= group_bits[(size_t)gi * W + w];
            }
            return outv;
        };
        std::vector<uint64_t> covered(W, 0);
        inside = disjoint_subset(inside, covered);
        std::vector<int> R;
        for (int c = 0; c < N; ++c)
            if (tbit(H.data(), c) && !tbit(covered.data(), c)) R.push_back(c);
        if (!R.empty() && R.size() <= 4 && !inside.empty()) {
            int total = tri_u;
            for (int gi : inside) total -= groups[gi].total;
            innies.push_back({hi, R, total, inside, false, un});
        } else if (R.size() > 4 && R.size() <= BIG_INNIE_MAX && !inside.empty()) {
            int total = tri_u;
            for (int gi : inside) total -= groups[gi].total;
            big_innies.push_back({hi, R, total, inside, false, un});
        }
        std::vector<uint64_t> cov_all = covered;
        touching = disjoint_subset(touching, cov_all);
        std::vector<int> allc = inside;
        allc.insert(allc.end(), touching.begin(), touching.end());
        bool Hsub = true;
        for (int w = 0; w < W; ++w)
            if (H[w] & ~cov_all[w]) Hsub = false;
        if (Hsub && !touching.empty()) {
            std::vector<int> O;
            for (int c = 0; c < N; ++c)
                if (tbit(cov_all.data(), c) && !tbit(H.data(), c)) O.push_back(c);
            if (O.size() <= 4) {
                int total = -tri_u;
                for (int gi : allc) total += groups[gi].total;
                innies.push_back({hi, O, total, allc, true, un});
            } else if (O.size() <= BIG_INNIE_MAX) {
                int total = -tri_u;
                for (int gi : allc) total += groups[gi].total;
                big_innies.push_back({hi, O, total, allc, true, un});
            }
        }
    }
}

// ------------------------------------------------------------- builders --
Puzzle make_standard(int size, int box_h, int box_w) {
    Puzzle p;
    p.D = size;
    for (int r = 0; r < size; ++r)
        for (int c = 0; c < size; ++c) p.coords.push_back({r, c});
    for (int r = 0; r < size; ++r) {
        Group g;
        g.name = "r" + std::to_string(r + 1);
        g.kind = "row";
        g.complete = true;
        for (int c = 0; c < size; ++c) g.cells.push_back(r * size + c);
        p.groups.push_back(g);
    }
    for (int c = 0; c < size; ++c) {
        Group g;
        g.name = "c" + std::to_string(c + 1);
        g.kind = "col";
        g.complete = true;
        for (int r = 0; r < size; ++r) g.cells.push_back(r * size + c);
        p.groups.push_back(g);
    }
    int nb = 0;
    for (int br = 0; br < size; br += box_h)
        for (int bc = 0; bc < size; bc += box_w) {
            Group g;
            g.name = "b" + std::to_string(++nb);
            g.kind = "box";
            g.complete = true;
            for (int i = 0; i < box_h; ++i)
                for (int j = 0; j < box_w; ++j) g.cells.push_back((br + i) * size + (bc + j));
            p.groups.push_back(g);
        }
    return p;
}

bool relation_tables(const std::string& kind, const std::vector<int>& args, int D, std::vector<uint32_t>& fwd,
                     std::vector<uint32_t>& bwd) {
    int k = args.empty() ? 0 : args[0];
    auto ok = [&](int v, int w, bool& known) -> bool {
        known = true;
        if (kind == "nonconsec") return std::abs(v - w) != 1;
        if (kind == "lt") return v < w;
        if (kind == "diffge") return std::abs(v - w) >= k;
        if (kind == "diffle") return std::abs(v - w) <= k;
        if (kind == "diff") return std::abs(v - w) == k;
        if (kind == "notdiff") return std::abs(v - w) != k;
        if (kind == "ratio") return v == k * w || w == k * v;
        if (kind == "notratio") return v != k * w && w != k * v;
        if (kind == "sum") return v + w == k;
        if (kind == "notsum") return v + w != k;
        if (kind == "eq") return v == w;
        if (kind == "neqval") return v != w;
        if (kind == "samegroup3") return (v - 1) / 3 == (w - 1) / 3;
        if (kind == "diffgroup3") return (v - 1) / 3 != (w - 1) / 3;
        known = false;
        return true;
    };
    uint32_t full = D >= 32 ? 0xffffffffu : ((1u << D) - 1);
    fwd.assign(D + 1, 0);
    bwd.assign(D + 1, 0);
    bool known = true;
    for (int v = 1; v <= D; ++v) {
        uint32_t af = 0, ab = 0;
        for (int w = 1; w <= D; ++w) {
            if (ok(v, w, known)) af |= bit(w);
            if (!known) return false;
            if (ok(w, v, known)) ab |= bit(w);
        }
        fwd[v] = full & ~af;
        bwd[v] = full & ~ab;
    }
    return true;
}

void add_nonconsecutive(Puzzle& p, int size) {
    std::vector<uint32_t> f, b;
    relation_tables("nonconsec", {}, p.D, f, b);
    for (int r = 0; r < size; ++r)
        for (int c = 0; c < size; ++c) {
            int i = r * size + c;
            if (c + 1 < size) p.relations.push_back({i, i + 1, false, f, b});
            if (r + 1 < size) p.relations.push_back({i, i + size, false, f, b});
        }
}

void add_cages(Puzzle& p, const std::vector<std::pair<int, std::vector<int>>>& cages) {
    int k = 0;
    for (auto& cg : cages) {
        Group g;
        g.name = "k" + std::to_string(++k);
        g.kind = "cage";
        g.cells = cg.second;
        g.complete = (int)cg.second.size() == p.D;
        g.has_total = true;
        g.total = cg.first;
        p.groups.push_back(g);
    }
}

}  // namespace cs

namespace cs {

// Set theory with arrows and little killers: a union of 1-3 houses sums to tri * k; subtract disjoint
// sum rules lying inside it (cages, little-killer diagonals, non-distinct sums) and replace every arrow
// line lying inside by its (single-digit) circle. What is left is a weighted sum of a few cells with a
// known total -- a derived sum constraint (cells counted with multiplicity), used by Innie/Outie(sum).
void Puzzle::build_set_theory() {
    if (D > 16) return;
    bool any_arrow = false, any_sum = false;
    for (const NConstraint& k : nary) {
        any_arrow |= k.type == NT_ARROW && k.ncircle == 1;
        any_sum |= k.type == NT_SUM;
    }
    if (!any_arrow && !any_sum) return;
    // house unions: reuse the innie enumeration if it ran, else unions of 1-3 parallel lines / boxes
    std::vector<std::vector<int>> unions = house_unions;
    if (unions.empty()) {
        for (int h : houses) unions.push_back({h});
        for (size_t i = 0; i < houses.size(); ++i)
            for (size_t j = i + 1; j < houses.size(); ++j)
                if (group_line[houses[i]] == group_line[houses[j]] && !group_overlap[(size_t)houses[i] * G + houses[j]])
                    unions.push_back({houses[i], houses[j]});
    }
    const int tri = D * (D + 1) / 2;
    std::set<std::vector<int>> seen;
    for (const auto& k : innie_nary) {
        std::vector<int> v = k.vars;
        std::sort(v.begin(), v.end());
        seen.insert(v);
    }
    for (const auto& un : unions) {
        std::vector<int> mult(N, 0);
        for (int h : un)
            for (int c : groups[h].cells) mult[c] += 1;
        bool overlap = false;
        for (int c = 0; c < N; ++c) overlap |= mult[c] > 1;
        if (overlap) continue;
        pm_long total = (pm_long)tri * (pm_long)un.size();
        int used_rules = 0;
        // subtract disjoint sum rules fully inside (cages first, then n-ary sums)
        auto inside = [&](const std::vector<int>& cells) {
            for (int c : cells)
                if (mult[c] < 1) return false;
            return true;
        };
        for (int gi : sum_cages) {
            const auto& cells = groups[gi].cells;
            if (!inside(cells)) continue;
            for (int c : cells) mult[c] -= 1;
            total -= groups[gi].total;
            ++used_rules;
        }
        for (const NConstraint& k : nary) {
            if (k.type != NT_SUM || (int)k.pvar.size() != k.nv() || !k.totals.empty()) continue;
            if (!inside(k.vars)) continue;
            for (int c : k.vars) mult[c] -= 1;
            total -= k.total;
            ++used_rules;
        }
        int arrows = 0;
        for (const NConstraint& k : nary) {  // arrow line inside -> replaced by its circle
            if (k.type != NT_ARROW || k.ncircle != 1 || (int)k.pvar.size() != k.nv()) continue;
            std::vector<int> line;
            for (size_t p = 1; p < k.pvar.size(); ++p) line.push_back(k.vars[k.pvar[p]]);
            if (line.empty() || !inside(line)) continue;
            for (int c : line) mult[c] -= 1;
            mult[k.vars[k.pvar[0]]] += 1;
            ++arrows;
        }
        if (!arrows && used_rules == 0) continue;
        std::vector<int> pos;
        bool neg = false;
        for (int c = 0; c < N; ++c) {
            if (mult[c] < 0) neg = true;
            for (int t = 0; t < mult[c]; ++t) pos.push_back(c);
        }
        if (neg || pos.empty() || pos.size() > 7 || !arrows) continue;  // plain cage innies: build_innies
        std::vector<int> key = pos;
        std::sort(key.begin(), key.end());
        if (!seen.insert(key).second) continue;
        bool distinct = false;
        {
            std::vector<int> u = key;
            u.erase(std::unique(u.begin(), u.end()), u.end());
            if (u.size() == key.size())
                for (int gi : groups_of[key[0]]) {
                    bool all = true;
                    for (int c : u) all &= tbit(gbits(gi), c);
                    distinct |= all;
                }
        }
        NConstraint k = make_nc(NT_SUM, pos, distinct);
        k.total = (int)total;
        k.house = un[0];
        k.outie = false;
        k.n_cages = used_rules + arrows;
        k.set_theory = true;
        innie_nary.push_back(std::move(k));
    }
}

}  // namespace cs
