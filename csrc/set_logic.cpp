// Set and counting logic: digit counting, equal digits, local line scans, rules together, sum algebra, band logic
// (split from extra.cpp).
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

// Positional set logic for one digit v. Base units: cell-disjoint units that must hold v at
// least once (complete houses without v, cages / constraints whose every consistent
// assignment contains v); cover units: cell-disjoint groups (all-different: at most one v).
// k bases, k covers, base candidates inside the covers -> exactly k copies, all in the
// bases -> v leaves the other cells of the covers. At least one base is not a house
// (plain house-vs-house is fish).
void Solver::digit_count(MoveBuf& out) {
    if (disabled[DIGIT_COUNT]) return;
    const int W = p.W;
    uint32_t dom[64];
    struct Unit { std::vector<uint64_t> bits; std::vector<int> cells; bool house; int id; };
    for (int v = 1; v <= p.D; ++v) {
        const uint32_t b = bit(v);
        std::vector<Unit> base;
        for (int gi = 0; gi < p.G; ++gi) {  // houses, and cages that must contain v
            const Group& g = p.groups[gi];
            bool placed = placed_g[gi] & b;
            if (placed) continue;
            bool must = g.complete;
            if (!must && g.has_total) {
                for (const NConstraint& k : p.cage_nary)
                    if (k.group == gi) {
                        nary_dom(k, dom);
                        const GacOut& o = gac_cached(k, dom);
                        must = o.any && (o.must & b);
                    }
            }
            if (!must) continue;
            Unit u{std::vector<uint64_t>(W, 0), {}, g.complete, gi};
            for (int c : g.cells)
                if (!vals[c] && (cand[c] & b)) {
                    sbit(u.bits.data(), c);
                    u.cells.push_back(c);
                }
            if (u.cells.size() >= 1 && u.cells.size() <= 6) base.push_back(u);
        }
        for (size_t ki = 0; ki < p.nary.size(); ++ki) {  // n-ary rules that must contain v
            const NConstraint& k = p.nary[ki];
            // lines join (#4 line digit sets: 'a 3-cell renban holding an 8 must hold a 7') when params dc_lines
            if (k.type == NT_SAMESET || (k.type == NT_LINE && !P.dc_lines)) continue;
            bool placed = false;
            for (int c : k.vars) placed |= vals[c] == v;
            if (placed) continue;
            nary_dom(k, dom);
            const GacOut& o = gac_cached(k, dom);
            if (!o.any || !(o.must & b)) continue;
            Unit u{std::vector<uint64_t>(W, 0), {}, false, -2 - (int)ki};
            for (int c : k.vars)
                if (!vals[c] && (cand[c] & b)) {
                    sbit(u.bits.data(), c);
                    u.cells.push_back(c);
                }
            if (!u.cells.empty() && u.cells.size() <= 6) base.push_back(u);
        }
        // the enumeration below depends only on the digit's plane (cells that can hold v, cells holding v)
        // and the base units: reuse the previous result for this digit when they are unchanged
        std::vector<uint64_t> key((size_t)2 * W, 0);
        for (int c = 0; c < p.N; ++c) {
            if (!vals[c] && (cand[c] & b)) key[c >> 6] |= 1ULL << (c & 63);
            if (vals[c] == v) key[W + (c >> 6)] |= 1ULL << (c & 63);
        }
        for (const Unit& u : base) key.push_back((uint64_t)(int64_t)u.id);
        if ((int)dc_cache.size() <= v) dc_cache.resize(v + 1);
        if (dc_cache[v].valid && dc_cache[v].key == key) {
            append_moves(out, dc_cache[v].buf);
            continue;
        }
        MoveBuf target;
        const int nb = (int)base.size();
        auto disjoint_b = [&](const std::vector<uint64_t>& a, const std::vector<uint64_t>& c) {
            for (int w = 0; w < W; ++w)
                if (a[w] & c[w]) return false;
            return true;
        };
        std::vector<int> pick;
        std::function<void(int)> rec = [&](int st) {
            const int k = (int)pick.size();
            if (k >= 1) {
                bool nonhouse = false;
                std::vector<uint64_t> U(W, 0);
                for (int i : pick) {
                    nonhouse |= !base[i].house;
                    for (int w = 0; w < W; ++w) U[w] |= base[i].bits[w];
                }
                if (nonhouse) {
                    // covers: groups meeting U, k of them, disjoint, covering U
                    std::vector<int> cov;
                    for (int gi = 0; gi < p.G; ++gi) {
                        if (placed_g[gi] & b) continue;
                        bool hit = false;
                        for (int w = 0; w < W && !hit; ++w) hit = p.gbits(gi)[w] & U[w];
                        if (hit) cov.push_back(gi);
                    }
                    std::vector<int> cp;
                    std::function<void(int, std::vector<uint64_t>)> rc = [&](int s2, std::vector<uint64_t> CU) {
                        if ((int)cp.size() == k) {
                            for (int w = 0; w < W; ++w)
                                if (U[w] & ~CU[w]) return;
                            std::vector<uint32_t> el;
                            for (int c = 0; c < p.N; ++c)
                                if (tbit(CU.data(), c) && !tbit(U.data(), c) && !vals[c] && (cand[c] & b))
                                    el.push_back((uint32_t)c * 32 + v);
                            if (el.empty()) return;
                            std::vector<int> pc;
                            for (int c = 0; c < p.N; ++c)
                                if (tbit(U.data(), c)) pc.push_back(c);
                            Move& m = new_move(target, DIGIT_COUNT, pspread(pc), k);
                            for (uint32_t e : el) add_elim(target, m, (int)(e / 32), (int)(e % 32));
                            set_pattern(target, m, pc);
                            std::vector<int> bu, cu;
                            for (int i : pick)
                                if (base[i].id >= 0) bu.push_back(base[i].id);
                            add_expl(target, m, EX_BASE, bu);
                            add_expl(target, m, EX_COVER, cp);
                            for (int i : pick)
                                if (base[i].id <= -2) cu.push_back(p.nary[-2 - base[i].id].index);
                            if (!cu.empty()) add_expl(target, m, EX_RULE, cu);
                            meta9(m, std::min(p.N, (int)pc.size()), 2 * k, 1, 0, 1, 0, 0, 1, m.shape);
                            pm_long xm[XM_N] = {k, (pm_long)pc.size(), (pm_long)el.size(), v, 0, 0, 0, 0, 0, 0};
                            std::copy(xm, xm + XM_N, m.xm);
                            return;
                        }
                        for (int i = s2; i < (int)cov.size(); ++i) {
                            const uint64_t* gb = p.gbits(cov[i]);
                            bool ok = true;
                            for (int w = 0; w < W && ok; ++w) ok = !(gb[w] & CU[w]);
                            if (!ok) continue;
                            std::vector<uint64_t> C2 = CU;
                            for (int w = 0; w < W; ++w) C2[w] |= gb[w];
                            cp.push_back(cov[i]);
                            rc(i + 1, C2);
                            cp.pop_back();
                        }
                    };
                    if ((int)cov.size() <= 30) rc(0, std::vector<uint64_t>(W, 0));
                }
            }
            if (k == 3) return;
            for (int i = st; i < nb; ++i) {
                bool ok = true;
                for (int j : pick) ok &= disjoint_b(base[i].bits, base[j].bits);
                if (!ok) continue;
                pick.push_back(i);
                rec(i + 1);
                pick.pop_back();
            }
        };
        rec(0);
        dc_cache[v].key = key;
        dc_cache[v].buf = target;
        dc_cache[v].valid = true;
        append_moves(out, target);
    }
}

// Abstract colouring: A outside house H; for every candidate d of A the only cell of H
// that can hold d without seeing A is the same cell B (d not yet placed in H) -> A and B
// hold the same digit (whatever it is) -> each keeps only the other's candidates.
void Solver::equal_digits(MoveBuf& out) {
    if (disabled[EQUAL_DIGITS]) return;
    for (int A = 0; A < p.N; ++A) {
        if (vals[A] || popc(cand[A]) < 2) continue;
        for (int hi : p.houses) {
            if (tbit(p.gbits(hi), A) || (placed_g[hi] & cand[A])) continue;
            int B = -1;
            bool ok = true;
            for (uint32_t m = cand[A]; m && ok; m &= m - 1) {
                uint32_t b = m & (~m + 1);
                int at = -1, n = 0;
                for (int c : p.groups[hi].cells)
                    if (!vals[c] && (cand[c] & b) && !tbit(p.peers(A), c)) {
                        ++n;
                        at = c;
                    }
                if (n != 1 || (B >= 0 && at != B)) ok = false;
                B = at;
            }
            if (!ok || B < 0) continue;
            uint32_t ea = cand[A] & ~cand[B], eb = cand[B] & ~cand[A];
            if (!ea && !eb) continue;
            Move& m = new_move(out, EQUAL_DIGITS, 1.0, popc(cand[A]));
            for (uint32_t x = ea; x; x &= x - 1) add_elim(out, m, A, lowdigit(x));
            for (uint32_t x = eb; x; x &= x - 1) add_elim(out, m, B, lowdigit(x));
            std::vector<int> pc{A, B};
            set_pattern(out, m, pc);
            add_expl(out, m, EX_BASE, {hi});
            m.shape = pspread(pc);
            meta9(m, 2 + (int)p.groups[hi].cells.size() / 3, 2, popc(cand[A]), 1, 1, 0, 0, 1, m.shape);
            pm_long xm[XM_N] = {A, B, hi, popc(cand[A]), 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

// Local scan of a long line: consistency over each window of 3 consecutive cells.
void Solver::line_scan(MoveBuf& out) {
    if (disabled[LINE_SCAN]) return;
    uint32_t dom[64];
    for (const NConstraint& w : p.line_windows) {
        int unplaced = 0;
        for (int c : w.vars) unplaced += !vals[c];
        if (!unplaced) continue;
        nary_dom(w, dom);
        const GacOut& o = gac_cached(w, dom);
        if (!o.any) continue;
        int n = 0;
        for (int i = 0; i < 3; ++i)
            if (!vals[w.vars[i]]) n += popc(cand[w.vars[i]] & ~o.sup[i]);
        if (!n) continue;
        Move& m = new_move(out, LINE_SCAN, w.shape, 3);
        std::vector<int> pc;
        for (int i = 0; i < 3; ++i) {
            int c = w.vars[i];
            if (vals[c]) continue;
            pc.push_back(c);
            for (uint32_t x = cand[c] & ~o.sup[i]; x; x &= x - 1) add_elim(out, m, c, lowdigit(x));
        }
        set_pattern(out, m, pc);
        m.nk = NM_NARY;
        m.na = w.index;
        meta9(m, (int)pc.size(), 1, popc(dom[0] | dom[1] | dom[2]), 0, 0, 0, 1, 1, w.shape);
        m.code = 4000 + 10 * w.line_kind + 6;  // "<kind> scan"
        pm_long xm[XM_N] = {w.line_kind, w.index, 3, (pm_long)pc.size(), 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
}

// Rules taken together (CTC break-ins: "this cage and this row together", "the line inside this box"):
// two units (n-ary rules incl. sum cages, complete houses; two houses only when pair relations lie inside
// them) sharing cells; every joint assignment of their free cells consistent with both, with sight
// (peers differ), pair relations inside the union and, for a house, the digits it must hold there, is
// enumerated (bounded); a candidate in no joint assignment is eliminated. Sound: a digit kept only on
// budget exhaustion.
static std::map<std::vector<uint32_t>, std::pair<std::vector<uint32_t>, pm_long>>& ri_xcache() {
    thread_local std::map<std::vector<uint32_t>, std::pair<std::vector<uint32_t>, pm_long>> m;
    return m;
}

void Solver::rule_intersect(MoveBuf& out) {
    if (disabled[RULE_INTERSECT]) return;
    const int N = p.N, D = p.D, D1 = D + 1;
    struct Unit {
        int kind;  // 0 house, 1 rule
        int g = -1;
        const NConstraint* k = nullptr;
        std::vector<int> cells;
    };
    std::vector<Unit> units;
    for (int g : p.houses)
        if ((int)p.groups[g].cells.size() == D) units.push_back({0, g, nullptr, p.groups[g].cells});
    auto add_rule = [&](const NConstraint& k) {
        // rules a human combines by listing combinations: sums / cages, equal sums, arrows, sets, small tables
        // (counting / visibility rules are left to their own techniques: their consistency checks are costly)
        const bool kind_ok = k.type == NT_SUM || k.type == NT_EQSUM || k.type == NT_ARROW || k.type == NT_SET ||
                             k.type == NT_BETWEEN || k.type == NT_XSUM || k.type == NT_SANDWICH ||
                             (k.type == NT_TABLE && k.rows.size() <= 4000);
        if (!kind_ok || k.nv() > 20) return;
        units.push_back({1, k.group, &k, k.vars});
    };
    for (const NConstraint& k : p.nary) add_rule(k);
    for (const NConstraint& k : p.cage_nary) add_rule(k);
    bool any_rule = false;
    for (auto& u : units) any_rule |= u.kind == 1;
    bool any_rel = false;
    for (int c = 0; c < N && !any_rel; ++c) any_rel = !p.rel[c].empty();
    if (!any_rule && !any_rel) return;
    pm_long budget = P.ri_budget;
    if (budget <= 0) return;
    const pm_long set_cap = std::getenv("RI_SETCAP") ? std::atol(std::getenv("RI_SETCAP")) : 50000;
    if (std::getenv("RI_BUDGET")) budget = std::atol(std::getenv("RI_BUDGET"));
    std::vector<int> inU(N, -1);
    std::set<std::vector<uint32_t>> seen_el;
    const int nu = (int)units.size();
    std::vector<std::vector<char>> share(nu, std::vector<char>(nu, 0));
    {
        std::vector<std::vector<int>> of(N);
        for (int i = 0; i < nu; ++i)
            for (int c : units[i].cells) of[c].push_back(i);
        for (int c = 0; c < N; ++c)
            for (int x : of[c])
                for (int y : of[c]) share[x][y] = 1;
    }
    // joint enumeration of a set of units: eliminations (empty: none / aborted / inconsistent)
    auto joint = [&](const std::vector<int>& ids, std::vector<int>& F, pm_long& nodes, bool& aborted) {
        std::vector<uint32_t> el;
        std::vector<int> U;
        for (int id : ids)
            for (int c : units[id].cells)
                if (std::find(U.begin(), U.end(), c) == U.end()) U.push_back(c);
        std::sort(U.begin(), U.end());
        F.clear();
        for (int c : U)
            if (!vals[c]) F.push_back(c);
        nodes = 0;
        aborted = false;
        std::vector<uint32_t> ckey(ids.begin(), ids.end());
        ckey.push_back(0xFFFFFFFFu);
        for (int c : U) ckey.push_back(vals[c] ? (0x80000000u | (uint32_t)vals[c]) : cand[c]);
        auto hit = ri_cache.find(ckey);
        if (hit != ri_cache.end()) {
            nodes = hit->second.second;
            aborted = nodes < 0;
            return hit->second.first;
        }
        // cross-call cache ri_cache dies with each Solver; the joint enumeration is a pure function of
        // (puzzle, unit ids, union state, budget, set cap) -> thread-local, exact, bounded
        std::vector<uint32_t> xkey(ckey);
        xkey.push_back((uint32_t)(p.uid & 0xFFFFFFFFu)); xkey.push_back((uint32_t)(p.uid >> 32));
        xkey.push_back((uint32_t)budget); xkey.push_back((uint32_t)set_cap);
        {
            auto xh = ri_xcache().find(xkey);
            if (xh != ri_xcache().end()) {
                if (ri_cache.size() < 20000) ri_cache[ckey] = xh->second;
                nodes = xh->second.second;
                aborted = nodes < 0;
                return xh->second.first;
            }
        }
        std::sort(F.begin(), F.end(), [&](int x, int y) {
            const int px = popc(cand[x]), py = popc(cand[y]);
            return px != py ? px < py : x < y;
        });
        const int nf = (int)F.size();
        for (int i = 0; i < nf; ++i) inU[F[i]] = i;
        std::vector<std::pair<int, uint32_t>> reqs;  // house group, digits it must hold among the free cells
        std::vector<const NConstraint*> rules;
        for (int id : ids) {
            const Unit& u = units[id];
            if (u.kind == 1) {
                rules.push_back(u.k);
                continue;
            }
            uint32_t need = p.full & ~placed_g[u.g], outside = 0;
            for (int c : p.groups[u.g].cells)
                if (!vals[c] && inU[c] < 0) outside |= cand[c];
            need &= ~outside;
            if (need) reqs.push_back({u.g, need});
        }
        std::vector<int> asg(nf, 0);
        std::vector<uint32_t> sup(nf, 0);
        uint32_t dom[64];
        // memo (exact): the check is a pure function of (rule, its cells' domains); node counting unchanged
        std::map<std::vector<uint32_t>, bool> rok_memo;
        auto rule_ok = [&](const NConstraint& k) {
            std::vector<uint32_t> key;
            key.reserve(k.nv() + 2);
            key.push_back((uint32_t)((uintptr_t)&k & 0xFFFFFFFFu));
            key.push_back((uint32_t)((uintptr_t)&k >> 32));
            for (int i = 0; i < k.nv(); ++i) {
                const int x = k.vars[i];
                dom[i] = vals[x] ? bit(vals[x]) : (inU[x] >= 0 && asg[inU[x]]) ? bit(asg[inU[x]]) : cand[x];
                key.push_back(dom[i]);
            }
            auto mh = rok_memo.find(key);
            if (mh != rok_memo.end()) return mh->second;
            GacOut o;
            static const std::vector<GacReq> noreq;
            nary_gac(k, dom, noreq, 3000, D, o);
            const bool r = !(o.complete && !o.any);
            if (rok_memo.size() < 200000) rok_memo.emplace(std::move(key), r);
            return r;
        };
        bool done = false;
        std::function<void(int)> rec = [&](int i) {
            if (done || aborted) return;
            if (++nodes > set_cap) {
                aborted = true;
                return;
            }
            if (i == nf) {
                for (auto& rq : reqs) {
                    uint32_t have = 0;
                    for (int c : p.groups[rq.first].cells)
                        if (inU[c] >= 0) have |= bit(asg[inU[c]]);
                    if ((have & rq.second) != rq.second) return;
                }
                bool all = true;
                for (int j = 0; j < nf; ++j) {
                    sup[j] |= bit(asg[j]);
                    all &= (cand[F[j]] & ~sup[j]) == 0;
                }
                if (all) done = true;
                return;
            }
            const int c = F[i];
            for (uint32_t m = cand[c]; m; m &= m - 1) {
                const int v = lowdigit(m);
                bool ok = true;
                for (int j = 0; j < i && ok; ++j)
                    if (asg[j] == v && tbit(p.peers(c), F[j])) ok = false;
                for (size_t j = 0; j < p.rel[c].size() && ok; ++j) {
                    const int q = p.rel[c][j];
                    const int qv = vals[q] ? vals[q] : (inU[q] >= 0 && inU[q] < i) ? asg[inU[q]] : 0;
                    if (qv && (p.rel_out[c][j * D1 + v] & bit(qv))) ok = false;
                }
                if (!ok) continue;
                asg[i] = v;
                bool rok = true;
                for (const NConstraint* k : rules) {
                    bool touches = false;
                    for (int x : k->vars) touches |= x == c;
                    if (touches && !rule_ok(*k)) {
                        rok = false;
                        break;
                    }
                }
                if (rok) rec(i + 1);
                asg[i] = 0;
                if (done || aborted) return;
            }
        };
        rec(0);
        for (int c : F) inU[c] = -1;
        bool none = true;
        for (int i = 0; i < nf; ++i) none &= sup[i] == 0;
        if (!aborted && !done && !none)  // none: no joint assignment (inconsistent state): leave it
            for (int i = 0; i < nf; ++i)
                for (uint32_t m = cand[F[i]] & ~sup[i]; m; m &= m - 1) el.push_back((uint32_t)F[i] * 32 + lowdigit(m));
        std::sort(el.begin(), el.end());
        if (ri_cache.size() < 20000) ri_cache[ckey] = {el, aborted ? -nodes - 1 : nodes};
        if (ri_xcache().size() >= 40000) ri_xcache().clear();
        ri_xcache()[xkey] = {el, aborted ? -nodes - 1 : nodes};
        return el;
    };
    auto free_of = [&](const std::vector<int>& ids) {
        std::vector<char> in(N, 0);
        int n = 0;
        for (int id : ids)
            for (int c : units[id].cells)
                if (!vals[c] && !in[c]) in[c] = 1, ++n;
        return n;
    };
    auto rel_inside = [&](const std::vector<int>& ids) {
        std::vector<char> in(N, 0);
        for (int id : ids)
            for (int c : units[id].cells) in[c] = 1;
        for (int c = 0; c < N; ++c)
            if (in[c])
                for (int q : p.rel[c])
                    if (in[q]) return true;
        return false;
    };
    auto emit = [&](const std::vector<int>& ids, const std::vector<int>& F, const std::vector<uint32_t>& el, pm_long nodes) {
        if (el.empty() || !seen_el.insert(el).second) return;
        Move& m = new_move(out, RULE_INTERSECT, 1.0, (int)ids.size());
        for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
        set_pattern(out, m, F);
        std::vector<int> gs, rs;
        int nrule = 0;
        bool arith = false;
        for (int id : ids) {
            const Unit& u = units[id];
            nrule += u.kind;
            if (u.kind == 1) arith |= u.k->arith;
            if (u.kind == 0 || (u.k && u.k->index < 0 && u.g >= 0)) gs.push_back(u.g);
            else if (u.k && u.k->index >= 0) rs.push_back(u.k->index);
        }
        if (!gs.empty()) add_expl(out, m, EX_BASE, gs);
        if (!rs.empty()) add_expl(out, m, EX_RULE, rs);
        uint32_t dm = 0;
        for (int c : F) dm |= cand[c];
        meta9(m, (int)F.size(), (int)ids.size(), popc(dm), (int)ids.size(), 0, arith ? 1 : 0, any_rel ? 1 : 0, 1,
              pspread(F));
        m.code = ids.size() > 2 ? 3333 : nrule == 0 ? 3332 : nrule == 2 ? 3331 : 3330;
        pm_long xm[XM_N] = {(pm_long)F.size(), (pm_long)el.size(), nrule, nodes, (pm_long)ids.size(), 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    std::vector<std::vector<int>> quiet;  // pairs fully enumerated without eliminations: triple seeds
    std::vector<int> F;
    pm_long nodes = 0;
    bool aborted = false;
    // pairs smallest first (open cells); a size class that yields moves ends the search (a human takes the
    // simplest combination that works; classes are symmetry-invariant)
    std::vector<std::pair<int, std::pair<int, int>>> pairs;
    for (int a = 0; a < nu; ++a)
        for (int b = a + 1; b < nu; ++b) {
            if (!share[a][b]) continue;
            const std::vector<int> ids{a, b};
            const int nf = free_of(ids);
            if (nf < 2 || nf > 14) continue;
            if (units[a].kind == 0 && units[b].kind == 0 && !rel_inside(ids)) continue;
            pairs.push_back({nf, {a, b}});
        }
    std::stable_sort(pairs.begin(), pairs.end(), [](const auto& x, const auto& y) { return x.first < y.first; });
    int found_nf = -1;
    for (const auto& pr : pairs) {
        if (budget <= 0) break;
        const int nf = pr.first;
        if (found_nf >= 0 && nf > found_nf) break;
        const std::vector<int> ids{pr.second.first, pr.second.second};
        const auto el = joint(ids, F, nodes, aborted);
        budget -= std::max(nodes, -nodes);
        if (!el.empty()) {
            const size_t before = out.moves.size();
            emit(ids, F, el, nodes);
            if (out.moves.size() > before) found_nf = nf;
        } else if (!aborted && nf <= 10) {
            quiet.push_back(ids);
        }
    }
    if (!out.moves.empty()) {  // pairs found something: triples are a later, dearer step
        bool mine = false;
        for (const Move& m : out.moves) mine |= m.tech == RULE_INTERSECT;
        if (mine) return;
    }
    for (const auto& q : quiet) {
        if (budget <= 0) break;
        for (int c = q[1] + 1; c < nu && budget > 0; ++c) {
            if (!share[q[0]][c] && !share[q[1]][c]) continue;
            if (units[c].kind == 0 && units[q[0]].kind == 0 && units[q[1]].kind == 0) continue;
            const std::vector<int> ids{q[0], q[1], c};
            const int nf = free_of(ids);
            if (nf > 12) continue;
            const auto el = joint(ids, F, nodes, aborted);
            budget -= std::max(nodes, -nodes);
            if (!el.empty()) emit(ids, F, el, nodes);
        }
    }
}

// Sum algebra over a band / stack (CTC "the maths": "rows 1 and 2 add up to 90, so red and purple add up
// to 34"; "these six cells of a row must include a 6"): regions of known total (a complete house = the sum
// of all digits; 2-3 parallel houses of one band / stack) hold pieces whose sums are tied to rule
// quantities (cage / sum totals, the common sum of an equal-sum line's segments, an arrow's circle digit)
// and residual cells, bounded per house by the smallest / largest distinct digits they can hold. Interval
// tightening to a fixpoint; a piece or a residual whose sum interval shrank loses the digits no sum in the
// interval can use (bounded enumeration with distinct peers). Sound; first round with eliminations = one
// step.
static std::map<std::vector<uint32_t>, std::pair<bool, std::vector<uint32_t>>>& sa_xcache() {
    thread_local std::map<std::vector<uint32_t>, std::pair<bool, std::vector<uint32_t>>> m;
    return m;
}

void Solver::sum_algebra(MoveBuf& out) {
    if (disabled[SUM_ALGEBRA]) return;
    const int N = p.N, D = p.D;
    for (const NConstraint& k : p.nary)
        if (k.type == NT_DIGITSET) return;  // house totals unknown
    struct Var { pm_long lo, hi, lo0, hi0; int src; const NConstraint* arrow = nullptr; };  // arrow: 1-digit circle
    struct Piece { std::vector<int> cells; int var; pm_long shift; int rule; };
    std::vector<Var> vars;
    std::vector<Piece> pieces;
    auto dmin = [&](int c) -> pm_long { return vals[c] ? vals[c] : (cand[c] ? __builtin_ctz(cand[c]) + 1 : 0); };
    auto dmax = [&](int c) -> pm_long { return vals[c] ? vals[c] : (cand[c] ? 32 - __builtin_clz(cand[c]) : 0); };
    auto all_peers = [&](const std::vector<int>& cs) {
        for (size_t i = 0; i < cs.size(); ++i)
            for (size_t j = i + 1; j < cs.size(); ++j)
                if (!tbit(p.peers(cs[i]), cs[j])) return false;
        return true;
    };
    // sum bounds of cells: distinct (pairwise peers) -> smallest / largest distinct digits of their union
    auto bounds = [&](const std::vector<int>& cs, pm_long& lo, pm_long& hi) {
        lo = hi = 0;
        if (cs.empty()) return;
        if (!all_peers(cs)) {
            for (int c : cs) lo += dmin(c), hi += dmax(c);
            return;
        }
        uint32_t uni = 0, placed = 0;
        int free = 0;
        for (int c : cs) {
            if (vals[c]) lo += vals[c], hi += vals[c], placed |= bit(vals[c]);
            else uni |= cand[c], ++free;
        }
        uni &= ~placed;
        std::vector<int> ds;
        for (uint32_t m = uni; m; m &= m - 1) ds.push_back(lowdigit(m));
        if ((int)ds.size() < free) {  // inconsistent: fall back to per-cell bounds
            for (int c : cs)
                if (!vals[c]) lo += dmin(c), hi += dmax(c);
            return;
        }
        for (int i = 0; i < free; ++i) lo += ds[i], hi += ds[ds.size() - 1 - i];
    };
    for (const NConstraint& k : p.nary) {
        if (k.type == NT_SUM && k.totals.empty() && (int)k.pvar.size() == k.nv()) {
            vars.push_back({k.total, k.total, k.total, k.total, k.index});
            pieces.push_back({k.vars, (int)vars.size() - 1, 0, k.index});
        } else if (k.type == NT_EQSUM && !k.seg_start.empty() && (int)k.pvar.size() == k.nv()) {
            pm_long lo = LONG_MIN / 4, hi = LONG_MAX / 4;
            std::vector<std::vector<int>> segs;
            for (size_t sg = 0; sg + 1 < k.seg_start.size(); ++sg) {
                std::vector<int> cs;
                for (int q = k.seg_start[sg]; q < k.seg_start[sg + 1]; ++q) cs.push_back(k.vars[k.pvar[q]]);
                pm_long a, b;
                bounds(cs, a, b);
                const pm_long sh = (pm_long)k.offset * (pm_long)cs.size();
                lo = std::max(lo, a - sh), hi = std::min(hi, b - sh);
                segs.push_back(cs);
            }
            vars.push_back({lo, hi, lo, hi, k.index});
            for (auto& cs : segs) pieces.push_back({cs, (int)vars.size() - 1, (pm_long)k.offset * (pm_long)cs.size(), k.index});
        } else if (k.type == NT_ARROW && k.ncircle == 2) {  // two-digit circle: the line sums to 10a + b
            const int c1 = k.vars[k.pvar[0]], c2 = k.vars[k.pvar[1]];
            std::vector<int> line;
            for (size_t q = 2; q < k.pvar.size(); ++q) line.push_back(k.vars[k.pvar[q]]);
            std::sort(line.begin(), line.end());
            if (std::adjacent_find(line.begin(), line.end()) != line.end()) continue;
            const pm_long lo = 10 * dmin(c1) + dmin(c2), hi = 10 * dmax(c1) + dmax(c2);
            vars.push_back({lo, hi, lo, hi, -2 - k.index});  // src < -1: not a cage, no circle trimming
            pieces.push_back({line, (int)vars.size() - 1, 0, k.index});
        } else if (k.type == NT_ARROW && k.ncircle == 1) {
            const int circ = k.vars[k.pvar[0]];
            std::vector<int> line;
            for (size_t q = 1; q < k.pvar.size(); ++q) line.push_back(k.vars[k.pvar[q]]);
            std::sort(line.begin(), line.end());
            if (std::adjacent_find(line.begin(), line.end()) != line.end()) continue;  // repeated cell
            vars.push_back({dmin(circ), dmax(circ), dmin(circ), dmax(circ), k.index, &k});
            pieces.push_back({line, (int)vars.size() - 1, 0, k.index});
        }
    }
    for (const NConstraint& k : p.cage_nary)
        if (k.type == NT_SUM && k.totals.empty()) {
            vars.push_back({k.total, k.total, k.total, k.total, -1 - k.group});
            pieces.push_back({k.vars, (int)vars.size() - 1, 0, -1});
        }
    if (pieces.empty()) return;
    // regions: complete houses of D cells, and unions of 2-3 parallel ones linked by a crossing house
    const pm_long HT = (pm_long)D * (D + 1) / 2;
    std::vector<std::vector<int>> regions;  // house lists
    std::vector<int> hs;
    for (int g : p.houses)
        if ((int)p.groups[g].cells.size() == D && g < (p.base_G >= 0 ? p.base_G : p.G)) hs.push_back(g);
    for (int g : hs) regions.push_back({g});
    auto cross = [&](int a, int b) {  // some complete house meets both
        for (int g : hs) {
            if (g == a || g == b) continue;
            bool x = false, y = false;
            for (int c : p.groups[g].cells) x |= tbit(p.gbits(a), c), y |= tbit(p.gbits(b), c);
            if (x && y) return true;
        }
        return false;
    };
    auto disjoint = [&](int a, int b) {
        for (int c : p.groups[a].cells)
            if (tbit(p.gbits(b), c)) return false;
        return true;
    };
    for (size_t i = 0; i < hs.size(); ++i)
        for (size_t j = i + 1; j < hs.size(); ++j) {
            const int a = hs[i], b = hs[j];
            if (p.group_line[a] != p.group_line[b] || !disjoint(a, b) || !cross(a, b)) continue;
            // same band: a box (or line) crossing both also crosses every member -> require a crossing house
            regions.push_back({a, b});
            for (size_t l = j + 1; l < hs.size(); ++l) {
                const int c = hs[l];
                if (p.group_line[c] != p.group_line[a] || !disjoint(a, c) || !disjoint(b, c) || !cross(a, c) || !cross(b, c))
                    continue;
                regions.push_back({a, b, c});
            }
        }
    if (regions.size() > 400) regions.resize(400);
    // per region: pieces fully inside (disjoint, greedy in order), residual cells per house
    struct Reg { std::vector<int> hs, pcs, outs; std::vector<std::vector<int>> res; pm_long total; };  // outs: piece cells outside
    std::vector<Reg> R;
    {
        std::vector<char> in(N), used(N);
        for (auto& hl : regions) {
            std::fill(in.begin(), in.end(), 0);
            std::fill(used.begin(), used.end(), 0);
            for (int g : hl)
                for (int c : p.groups[g].cells) in[c] = 1;
            Reg r;
            r.hs = hl;
            r.total = HT * (pm_long)hl.size();
            for (int pi = 0; pi < (int)pieces.size(); ++pi) {
                bool ok = !pieces[pi].cells.empty();
                for (int c : pieces[pi].cells) ok &= in[c] && !used[c];
                if (!ok) continue;
                for (int c : pieces[pi].cells) used[c] = 1;
                r.pcs.push_back(pi);
            }
            auto push = [&](Reg& rr, const std::vector<char>& usedc) {
                if (rr.pcs.empty()) return;
                rr.res.clear();
                for (int g : hl) {
                    std::vector<int> rc;
                    for (int c : p.groups[g].cells)
                        if (!usedc[c]) rc.push_back(c);
                    rr.res.push_back(rc);
                }
                R.push_back(rr);
            };
            push(r, used);  // whole pieces only (keeps the distinct bounds of the other cells)
            // pieces sticking out by <= 3 cells (outies): the outside cells are subtracted (a second equation)
            const size_t npc = r.pcs.size();
            std::vector<char> uo(N, 0);
            for (int pi = 0; pi < (int)pieces.size(); ++pi) {
                int nin = 0, nout = 0;
                bool ok = true;
                for (int c : pieces[pi].cells) {
                    if (in[c]) { ++nin; ok &= !used[c]; }
                    else { ++nout; ok &= !uo[c]; }
                }
                if (!ok || nin == 0 || nout == 0 || nout > 3) continue;
                for (int c : pieces[pi].cells) {
                    if (in[c]) used[c] = 1;
                    else uo[c] = 1, r.outs.push_back(c);
                }
                r.pcs.push_back(pi);
            }
            if (r.pcs.size() > npc) push(r, used);
        }
    }
    if (R.empty()) return;
    // residual sum bounds (natural) per region
    std::vector<pm_long> rlo0(R.size()), rhi0(R.size());
    for (size_t i = 0; i < R.size(); ++i) {
        pm_long lo = 0, hi = 0;
        for (auto& rc : R[i].res) {
            pm_long a, b;
            bounds(rc, a, b);
            lo += a, hi += b;
        }
        rlo0[i] = lo, rhi0[i] = hi;
    }
    std::vector<pm_long> rlo = rlo0, rhi = rhi0;
    std::vector<pm_long> olo0(R.size(), 0), ohi0(R.size(), 0);
    for (size_t i = 0; i < R.size(); ++i)
        for (int c : R[i].outs) olo0[i] += dmin(c), ohi0[i] += dmax(c);
    std::vector<pm_long> olo = olo0, ohi = ohi0;
    // the pieces' own distinct bounds (a cage / segment cannot sum below its smallest distinct digits)
    for (auto& pc : pieces) {
        pm_long a, b;
        bounds(pc.cells, a, b);
        Var& v = vars[pc.var];
        v.lo = std::max(v.lo, a - pc.shift), v.hi = std::min(v.hi, b - pc.shift);
    }
    for (auto& v : vars) v.lo0 = v.lo, v.hi0 = v.hi;
    std::vector<int> touched_by(vars.size(), -1), rround(vars.size(), 0);
    int rounds = 0;
    for (int round = 1; round <= 8; ++round) {
        bool ch = false;
        for (size_t i = 0; i < R.size(); ++i) {
            const Reg& r = R[i];
            // sum over pieces: sum_j m_j S_j + shifts + residual = total
            std::map<int, int> mult;
            pm_long sh = 0;
            for (int pi : r.pcs) ++mult[pieces[pi].var], sh += pieces[pi].shift;
            pm_long smin = sh + rlo[i] - ohi[i], smax = sh + rhi[i] - olo[i];
            for (auto& mv : mult) smin += mv.second * vars[mv.first].lo, smax += mv.second * vars[mv.first].hi;
            for (auto& mv : mult) {
                Var& v = vars[mv.first];
                const pm_long m = mv.second;
                const pm_long other_min = smin - m * v.lo, other_max = smax - m * v.hi;
                auto fdiv = [](pm_long x, pm_long y) { return x >= 0 ? x / y : -((-x + y - 1) / y); };
                const pm_long nlo = -fdiv(-(r.total - other_max), m);  // ceil
                const pm_long nhi = fdiv(r.total - other_min, m);      // floor
                if (nlo > v.lo || nhi < v.hi) {
                    v.lo = std::max(v.lo, nlo), v.hi = std::min(v.hi, nhi);
                    touched_by[mv.first] = (int)i;
                    rround[mv.first] = round;
                    ch = true;
                }
            }
            pm_long pmin = sh, pmax = sh;
            for (auto& mv : mult) pmin += mv.second * vars[mv.first].lo, pmax += mv.second * vars[mv.first].hi;
            const pm_long nlo = r.total - (pmax - olo[i]), nhi = r.total - (pmin - ohi[i]);
            if (nlo > rlo[i] || nhi < rhi[i]) {
                rlo[i] = std::max(rlo[i], nlo), rhi[i] = std::min(rhi[i], nhi);
                ch = true;
            }
            if (!r.outs.empty()) {  // outies: O = pieces + residual - total
                const pm_long a = pmin + rlo[i] - r.total, b = pmax + rhi[i] - r.total;
                if (a > olo[i] || b < ohi[i]) {
                    olo[i] = std::max(olo[i], a), ohi[i] = std::min(ohi[i], b);
                    ch = true;
                }
            }
        }
        rounds = round;
        if (!ch) break;
    }
    // eliminations: bounded enumeration of cells under a sum interval (distinct peers)
    auto enum_sum_raw = [&](const std::vector<int>& cs, pm_long lo, pm_long hi, std::vector<uint32_t>& sup) -> bool {
        std::vector<int> F;
        pm_long fixed = 0;
        for (int c : cs)
            if (vals[c]) fixed += vals[c];
            else F.push_back(c);
        sup.assign(F.size(), 0);
        if (F.size() > 12) return false;
        std::vector<int> a(F.size(), 0);
        pm_long nodes = 0;
        bool abort = false;
        std::vector<pm_long> sufmin(F.size() + 1, 0), sufmax(F.size() + 1, 0);
        for (int i = (int)F.size() - 1; i >= 0; --i) sufmin[i] = sufmin[i + 1] + dmin(F[i]), sufmax[i] = sufmax[i + 1] + dmax(F[i]);
        std::function<void(int, pm_long)> rec = [&](int i, pm_long s) {
            if (abort) return;
            if (++nodes > 100000) { abort = true; return; }
            if (s + sufmin[i] > hi || s + sufmax[i] < lo) return;
            if (i == (int)F.size()) {
                for (size_t j = 0; j < F.size(); ++j) sup[j] |= bit(a[j]);
                return;
            }
            for (uint32_t m = cand[F[i]]; m; m &= m - 1) {
                const int v = lowdigit(m);
                bool ok = true;
                for (int j = 0; j < i && ok; ++j) ok = !(a[j] == v && tbit(p.peers(F[i]), F[j]));
                for (int c : cs)
                    if (vals[c] == v && tbit(p.peers(F[i]), c)) ok = false;
                if (!ok) continue;
                a[i] = v;
                rec(i + 1, s + v);
                a[i] = 0;
            }
        };
        rec(0, fixed);
        if (abort) return false;
        bool any = false;
        for (uint32_t x : sup) any |= x != 0;
        return any || F.empty();
    };
    // cross-call cache (exact): enum_sum is a pure function of (puzzle, cells, their states, interval)
    auto enum_sum = [&](const std::vector<int>& cs, pm_long lo, pm_long hi, std::vector<uint32_t>& sup) -> bool {
        std::vector<uint32_t> xkey;
        xkey.reserve(cs.size() * 2 + 4);
        xkey.push_back((uint32_t)(p.uid & 0xFFFFFFFFu)); xkey.push_back((uint32_t)(p.uid >> 32));
        xkey.push_back((uint32_t)lo); xkey.push_back((uint32_t)hi);
        for (int c : cs) { xkey.push_back((uint32_t)c); xkey.push_back(vals[c] ? (0x80000000u | (uint32_t)vals[c]) : cand[c]); }
        auto xh = sa_xcache().find(xkey);
        if (xh != sa_xcache().end()) { sup = xh->second.second; return xh->second.first; }
        const bool r_ = enum_sum_raw(cs, lo, hi, sup);
        if (sa_xcache().size() >= 40000) sa_xcache().clear();
        sa_xcache()[xkey] = {r_, sup};
        return r_;
    };
    std::set<std::vector<uint32_t>> seen;
    auto emit = [&](const std::vector<int>& cs, const std::vector<uint32_t>& sup, const Reg& r, int nunits) {
        std::vector<int> F;
        for (int c : cs)
            if (!vals[c]) F.push_back(c);
        std::vector<uint32_t> el;
        for (size_t j = 0; j < F.size(); ++j)
            for (uint32_t m = cand[F[j]] & ~sup[j]; m; m &= m - 1) el.push_back((uint32_t)F[j] * 32 + lowdigit(m));
        if (el.empty() || !seen.insert(el).second) return;
        Move& m = new_move(out, SUM_ALGEBRA, 1.0, nunits);
        for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
        std::vector<int> pc;
        for (int g : r.hs)
            for (int c : p.groups[g].cells)
                if (!vals[c]) pc.push_back(c);
        set_pattern(out, m, pc);
        add_expl(out, m, EX_BASE, r.hs);
        std::vector<int> rs;
        for (int pi : r.pcs)
            if (pieces[pi].rule >= 0 && std::find(rs.begin(), rs.end(), pieces[pi].rule) == rs.end()) rs.push_back(pieces[pi].rule);
        if (!rs.empty()) add_expl(out, m, EX_RULE, rs);
        meta9(m, std::min(N, (int)pc.size()), nunits, D, rounds, 0, 1, 0, 1, pspread(pc));
        m.code = 3340 + (int)r.hs.size();
        pm_long xm[XM_N] = {(pm_long)r.hs.size(), (pm_long)r.pcs.size(), (pm_long)el.size(), rounds, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    };
    std::vector<uint32_t> sup;
    for (size_t vi = 0; vi < vars.size(); ++vi) {
        const Var& v = vars[vi];
        if (touched_by[vi] < 0 || (v.lo <= v.lo0 && v.hi >= v.hi0) || v.lo > v.hi) continue;
        const Reg& r = R[touched_by[vi]];
        for (const Piece& pc : pieces)
            if (pc.var == (int)vi && enum_sum(pc.cells, v.lo + pc.shift, v.hi + pc.shift, sup))
                emit(pc.cells, sup, r, (int)r.pcs.size() + (int)r.hs.size());
        if (v.arrow) {  // the circle digit itself
            const NConstraint& k = *v.arrow;
            const int circ = k.vars[k.pvar[0]];
            if (!vals[circ]) {
                uint32_t keep = 0;
                for (pm_long d = std::max(pm_long(1), v.lo); d <= std::min((pm_long)D, v.hi); ++d) keep |= bit((int)d);
                std::vector<uint32_t> s1{cand[circ] & keep};
                if (s1[0]) emit({circ}, s1, r, (int)r.pcs.size() + (int)r.hs.size());
            }
        }
    }
    for (size_t i = 0; i < R.size(); ++i) {
        if (rlo[i] <= rlo0[i] && rhi[i] >= rhi0[i]) continue;
        if (rlo[i] > rhi[i]) continue;
        std::vector<int> cs;
        for (auto& rc : R[i].res) cs.insert(cs.end(), rc.begin(), rc.end());
        if (enum_sum(cs, rlo[i], rhi[i], sup)) emit(cs, sup, R[i], (int)R[i].pcs.size() + (int)R[i].hs.size());
    }
    for (size_t i = 0; i < R.size(); ++i) {
        if (R[i].outs.empty() || (olo[i] <= olo0[i] && ohi[i] >= ohi0[i]) || olo[i] > ohi[i]) continue;
        if (enum_sum(R[i].outs, olo[i], ohi[i], sup)) emit(R[i].outs, sup, R[i], (int)R[i].pcs.size() + (int)R[i].hs.size());
    }
}


// Band logic (CTC break-ins that combine a band's lines, its boxes and the rules inside: "rows 2 and 3
// with the two 10-cages and box 2"): a region of 1-3 parallel lines of one band, the complete houses
// lying inside that band which meet them, and every rule (cage, sum, arrow, line, ...) whose cells lie in
// the region's cells plus at most 3 more, taken together as one small puzzle. A candidate is removed when
// no filling of that sub-puzzle uses it (singleton consistency by bounded brute force on the sub-puzzle;
// cells outside it are unconstrained there). Sound: the sub-puzzle holds a subset of the puzzle's
// constraints; a candidate is kept whenever the search hits its node budget. Smallest regions first; a
// size class with moves ends the search.
// rule kinds whose consistency check is cheap in a search (as RuleIntersection; outside clues such as
// skyscrapers / sandwiches and counting rules made the sub-puzzle searches cost minutes)
static bool band_cheap(const NConstraint& k) {
    return k.type == NT_SUM || k.type == NT_EQSUM || k.type == NT_ARROW || k.type == NT_SET || k.type == NT_BETWEEN ||
           k.type == NT_LINE || (k.type == NT_TABLE && k.rows.size() <= 4000);
}
static thread_local double band_t_sac = 0, band_t_level = 0;
void Solver::band_logic(MoveBuf& out) {
    if (disabled[BAND_LOGIC] || P.band_budget <= 0) return;
    static const bool force_wide = std::getenv("BAND_FORCE_WIDE") != nullptr;  // soundness fuzz: wide regions everywhere
    const bool escalated = band_budget_now > 0 || force_wide;  // forcing fallback: one larger search at a step that would guess
    const pm_long BB = band_budget_now > 0 ? band_budget_now : P.band_budget;
    const int N = p.N, D = p.D;
    if (D > 16) return;  // 25x25: sub-puzzle searches cost minutes and did not unstick (test_25)
    if (!escalated && band_spent > 8 * P.band_budget) return;  // per-solve cap on fruitless calls
    if (!escalated && band_total > 32 * P.band_budget) return;  // hard per-solve bound incl. productive calls
    for (const NConstraint& k : p.nary)
        if (k.type == NT_DIGITSET) return;  // house totals unknown (derived sums would be wrong)
    const int G0 = p.base_G >= 0 ? p.base_G : p.G;
    // escalation (fallback before guessing): wide regions -- the same house sets with every cheap rule that meets
    // them taken whole (no stick-out limit; params band_wide_cells caps the region), searched only there
    const bool wide = escalated && (band_wide_now || force_wide) && P.band_wide_cells > 0;
    std::vector<BandRegion>& regs = wide ? band_regions_wide : band_regions;
    auto& bcache = wide ? band_cache_wide : band_cache;
    auto& bsols = wide ? band_sols_wide : band_sols;
    bool& built = wide ? band_built_wide : band_built;
    if (regs.empty() && !built) {
        built = true;
        std::vector<int> lines, boxes;
        for (int g : p.houses) {
            if (g >= G0 || (int)p.groups[g].cells.size() != D) continue;
            (p.group_line[g] < 2 ? lines : boxes).push_back(g);
        }
        auto inter = [&](int a, int b) {
            for (int c : p.groups[a].cells)
                if (tbit(p.gbits(b), c)) return true;
            return false;
        };
        auto crosses = [&](int a, int b) {  // a box meets both parallel lines
            for (int x : boxes)
                if (inter(x, a) && inter(x, b)) return true;
            return false;
        };
        bool any_rule = !p.nary.empty() || p.has_cages;
        for (int g = 0; g < G0 && !any_rule; ++g) any_rule = !p.groups[g].complete && p.groups[g].cells.size() > 1;
        bool any_rel = false;
        for (int c = 0; c < N && !any_rel; ++c) any_rel = !p.rel[c].empty();
        if (!any_rule && !any_rel) return;
        std::set<std::vector<int>> seen;
        // house sets, smallest first: one house; a line with a box it meets; a whole band (its parallel lines
        // linked by boxes, and the boxes inside it)
        std::vector<std::pair<std::vector<int>, std::vector<int>>> hsets;  // (lines, boxes)
        for (int l : lines) hsets.push_back({{l}, {}});
        for (int x : boxes) hsets.push_back({{}, {x}});
        for (int l : lines)
            for (int x : boxes)
                if (inter(l, x)) hsets.push_back({{l}, {x}});
        for (size_t i = 0; i < lines.size(); ++i)  // a row and a column crossing (with the box at the crossing)
            for (size_t j = i + 1; j < lines.size(); ++j) {
                const int a = lines[i], b = lines[j];
                if (p.group_line[a] == p.group_line[b] || !inter(a, b)) continue;
                hsets.push_back({{a, b}, {}});
                for (int x : boxes) {
                    bool hit = false;
                    for (int c : p.groups[x].cells) hit |= tbit(p.gbits(a), c) && tbit(p.gbits(b), c);
                    if (hit) hsets.push_back({{a, b}, {x}});
                }
            }
        {  // two houses a rule (cage / n-ary rule) touches together, e.g. two boxes joined by equal-sum lines
            std::set<std::pair<int, int>> have;
            for (auto& h : hsets)
                if (h.first.size() + h.second.size() == 2) {
                    std::vector<int> v(h.first);
                    v.insert(v.end(), h.second.begin(), h.second.end());
                    have.insert({std::min(v[0], v[1]), std::max(v[0], v[1])});
                }
            std::vector<std::vector<int>> rule_cells;
            for (const NConstraint& k : p.nary)
                if (k.index >= 0 && (p.base_nary < 0 || k.index < p.base_nary) && k.nv() <= 16) rule_cells.push_back(k.vars);
            for (int g = 0; g < G0; ++g)
                if (!p.groups[g].complete && p.groups[g].cells.size() > 1) rule_cells.push_back(p.groups[g].cells);
            std::vector<int> allh(lines);
            allh.insert(allh.end(), boxes.begin(), boxes.end());
            for (auto& rc : rule_cells) {
                std::vector<int> touch;
                for (int h : allh)
                    for (int c : rc)
                        if (tbit(p.gbits(h), c)) { touch.push_back(h); break; }
                for (size_t i = 0; i < touch.size(); ++i)
                    for (size_t j = i + 1; j < touch.size(); ++j) {
                        const int a = std::min(touch[i], touch[j]), b = std::max(touch[i], touch[j]);
                        if (!have.insert({a, b}).second) continue;
                        std::vector<int> L, X;
                        (p.group_line[a] < 2 ? L : X).push_back(a);
                        (p.group_line[b] < 2 ? L : X).push_back(b);
                        hsets.push_back({L, X});
                    }
            }
        }
        for (int l : lines) {
            std::vector<char> band(N, 0);
            std::vector<int> bl;
            for (int m : lines) {
                if (p.group_line[m] != p.group_line[l] || (m != l && (inter(m, l) || !crosses(m, l)))) continue;
                bl.push_back(m);
                for (int c : p.groups[m].cells) band[c] = 1;
            }
            std::vector<int> bb;
            for (int x : boxes) {
                bool meet = false, inside = true;
                for (int c : p.groups[x].cells) meet |= tbit(p.gbits(l), c), inside &= band[c] != 0;
                if (meet && inside) bb.push_back(x);
            }
            if (bl.size() >= 2 && !bb.empty()) hsets.push_back({bl, bb});
        }
        auto build_one = [&](const std::pair<std::vector<int>, std::vector<int>>& hsx, const std::vector<int>* pick) {
            const std::vector<int>& L = hsx.first;
            BandRegion R;
            R.lines = L;
            R.boxes = hsx.second;
            std::vector<char> in(N, 0);
            for (int l : R.lines)
                for (int c : p.groups[l].cells) in[c] = 1;
            for (int x : R.boxes)
                for (int c : p.groups[x].cells) in[c] = 1;
            // rules: cells inside, or at most 3 outside (those cells join the region)
            std::vector<char> in0 = in;
            static const int small_out = std::getenv("BAND_SMALL_OUT") ? std::atoi(std::getenv("BAND_SMALL_OUT")) : 3;  // dev64's 6: slower, no gain
            static const size_t small_units = std::getenv("BAND_SMALL_UNITS") ? std::atoi(std::getenv("BAND_SMALL_UNITS")) : 2;
            const int max_out = wide ? 1 << 20 : R.lines.size() + R.boxes.size() <= small_units ? small_out : 3;
            bool beyond = false;  // wide: some rule sticks out further than a regular region allows
            auto take = [&](const std::vector<int>& cs, int id) {
                int out_n = 0;
                for (int c : cs) out_n += !in0[c];
                if (out_n > max_out || out_n == (int)cs.size()) return false;
                if (out_n > 3 && pick && std::find(pick->begin(), pick->end(), id) == pick->end()) return false;
                beyond |= out_n > 3;
                for (int c : cs) in[c] = 1;
                return true;
            };
            // rule kinds whose consistency check is cheap in a search (as RuleIntersection; outside clues such as
            // skyscrapers / sandwiches and counting rules made the sub-puzzle searches cost minutes)
            for (const NConstraint& k : p.nary)
                if (k.index >= 0 && (p.base_nary < 0 || k.index < p.base_nary) && band_cheap(k) && k.nv() <= 16 &&
                    take(k.vars, k.index))
                    R.rules.push_back(k.index);
            for (int g = 0; g < G0; ++g)
                if (!p.groups[g].complete && p.groups[g].cells.size() > 1 && take(p.groups[g].cells, -1 - g))
                    R.cages.push_back(g);
            for (int c = 0; c < N; ++c)
                if (in[c]) R.cells.push_back(c);
            if (wide && (!beyond || (int)R.cells.size() > P.band_wide_cells)) return;
            if ((wide && std::getenv("BAND_DEBUG")) || std::getenv("BAND_DUMP")) {
                fprintf(stderr, "wide region: houses");
                for (int g : R.lines) fprintf(stderr, " %s", p.groups[g].name.c_str());
                for (int g : R.boxes) fprintf(stderr, " %s", p.groups[g].name.c_str());
                fprintf(stderr, " rules");
                for (int r : R.rules) fprintf(stderr, " %d", r);
                fprintf(stderr, " cages %zu cells %zu\n", R.cages.size(), R.cells.size());
            }
            bool rel = false;
            for (int c : R.cells)
                for (int q : p.rel[c]) rel |= in[q] != 0;
            if (R.rules.empty() && R.cages.empty() && !rel) return;
            std::vector<int> key = R.cells;
            key.push_back(-1);
            key.insert(key.end(), R.rules.begin(), R.rules.end());
            key.push_back(-2);
            key.insert(key.end(), R.cages.begin(), R.cages.end());
            if (!seen.insert(key).second) return;
            // the sub-puzzle (structure only)
            auto q = std::make_shared<Puzzle>();
            q->D = D;
            q->coords = p.coords;
            q->domains = p.domains;
            q->is_derived = true;
            q->exact_shapes = true;
            for (int g : R.lines) q->groups.push_back(p.groups[g]);
            for (int g : R.boxes) q->groups.push_back(p.groups[g]);
            for (int g : R.cages) q->groups.push_back(p.groups[g]);
            for (int r : R.rules) q->nary_specs.push_back(p.nary_specs[r]);
            for (const RelSpec& rs : p.relations)
                if (in[rs.a] && in[rs.b]) q->relations.push_back(rs);
            // derived house sums ("rows 2 and 3 add up to 90"): for unions of 1-3 band lines (parallel to L)
            // and of 1-3 band boxes, the cells left after removing the sum cages / fixed sums inside add up to
            // k * D(D+1)/2 minus their totals (redundant, but they give the search the arithmetic a human uses)
            {
                std::vector<int> bl = R.lines, bb = R.boxes;  // all their cells are in the sub-puzzle
                std::vector<std::pair<std::vector<int>, int>> pieces;  // fixed-total cell sets
                for (int g : R.cages)
                    if (p.groups[g].has_total) pieces.push_back({p.groups[g].cells, p.groups[g].total});
                for (int r : R.rules) {
                    const NSpec& sp = p.nary_specs[r];
                    if (sp.type == NT_SUM && sp.totals.empty() && sp.offset == 0) {
                        std::vector<int> cs = sp.a;
                        std::sort(cs.begin(), cs.end());
                        if (std::adjacent_find(cs.begin(), cs.end()) == cs.end()) pieces.push_back({cs, sp.total});
                    }
                }
                const pm_long HT = (pm_long)D * (D + 1) / 2;
                auto add_sums = [&](const std::vector<int>& hs) {
                    const int n = (int)hs.size();
                    for (int mask = 1; mask < (1 << n); ++mask) {
                        std::vector<char> u(N, 0);
                        int k = 0;
                        bool overlap = false;
                        for (int i = 0; i < n; ++i)
                            if (mask >> i & 1) {
                                ++k;
                                for (int c : p.groups[hs[i]].cells) overlap |= u[c] != 0, u[c] = 1;
                            }
                        if (overlap) continue;  // only pairwise disjoint houses add up to k totals
                        pm_long tot = HT * k;
                        std::vector<char> used(N, 0), out_used(N, 0);
                        int removed = 0;
                        std::vector<int> outies;  // cells of pieces sticking out of the houses (subtracted)
                        for (auto& pc : pieces) {
                            bool ok = true;
                            for (int c : pc.first) ok &= u[c] && !used[c];
                            if (!ok) continue;
                            for (int c : pc.first) used[c] = 1;
                            tot -= pc.second;
                            ++removed;
                        }
                        if (P.band_outies)  // pieces partly inside (outie cells in the region): sum(rest) - sum(outies) = tot
                            for (auto& pc : pieces) {
                                int inside = 0, outside = 0;
                                bool ok = true;
                                for (int c : pc.first) {
                                    if (u[c]) ok &= !used[c], ++inside;
                                    else ok &= in[c] && !out_used[c], ++outside;
                                }
                                if (!ok || !inside || !outside || outside > 4) continue;
                                for (int c : pc.first) (u[c] ? used : out_used)[c] = 1;
                                for (int c : pc.first)
                                    if (!u[c]) outies.push_back(c);
                                tot -= pc.second;
                                ++removed;
                            }
                        if (!removed) continue;
                        NSpec sp;
                        sp.type = NT_SUM;
                        for (int c = 0; c < N; ++c)
                            if (u[c] && !used[c]) sp.a.push_back(c);
                        for (int i = 0; i < n; ++i)  // parts: the residual cells of each house
                            if (mask >> i & 1) {
                                std::vector<int> pc;
                                for (int c : p.groups[hs[i]].cells)
                                    if (!used[c]) pc.push_back(c);
                                sp.segs.push_back(pc);
                                sp.seg_sign.push_back(1);
                            }
                        for (int c : outies) {  // each outie cell its own subtracted part
                            sp.a.push_back(c);
                            sp.segs.push_back({c});
                            sp.seg_sign.push_back(-1);
                        }
                        if (outies.empty()) sp.seg_sign.clear();
                        if (sp.a.empty() || sp.a.size() > 60) continue;
                        sp.total = (int)tot;
                        sp.distinct = (k == 1 && outies.empty()) ? 1 : 0;
                        sp.bounds_only = true;
                        q->nary_specs.push_back(sp);
                    }
                };
                // only disjoint houses add up to k totals: lines of one orientation, boxes (disjoint by design)
                std::vector<int> rows_, cols_;
                for (int l : bl) (p.group_line[l] == 0 ? rows_ : cols_).push_back(l);
                if (rows_.size() <= 4) add_sums(rows_);
                if (cols_.size() <= 4) add_sums(cols_);
                if (bb.size() <= 4) add_sums(bb);
            }
            // renumber to the region's cells only (the search scans every cell of its puzzle)
            {
                std::vector<int> pos(N, -1);
                for (size_t i = 0; i < R.cells.size(); ++i) pos[R.cells[i]] = (int)i;
                auto mapv = [&](std::vector<int>& v) {
                    for (int& c : v) c = pos[c];
                };
                std::vector<std::pair<int, int>> co;
                std::vector<uint32_t> dm;
                for (int c : R.cells) co.push_back(p.coords[c]), dm.push_back(p.domains[c]);
                q->coords = co;
                q->domains = dm;
                for (auto& g : q->groups) mapv(g.cells);
                for (auto& sp : q->nary_specs) {
                    mapv(sp.a);
                    for (auto& sg : sp.segs) mapv(sg);
                }
                for (auto& rs : q->relations) rs.a = pos[rs.a], rs.b = pos[rs.b];
                bool okmap = true;
                for (auto& g : q->groups)
                    for (int c : g.cells) okmap &= c >= 0;
                for (auto& sp : q->nary_specs) {
                    for (int c : sp.a) okmap &= c >= 0;
                    for (auto& sg : sp.segs)
                        for (int c : sg) okmap &= c >= 0;
                }
                for (auto& rs : q->relations) okmap &= rs.a >= 0 && rs.b >= 0;
                if (!okmap) return;  // a rule reaching outside the region (cannot happen by construction)
                R.pos = pos;
            }
            q->finalize();
            R.sub = q;
            regs.push_back(std::move(R));
        };
        for (auto& hsx : hsets) {
            if (!wide) {
                build_one(hsx, nullptr);
                continue;
            }
            if (hsx.first.size() + hsx.second.size() > 3) continue;
            // rules sticking out of the house set by more than a regular region allows: taken in subsets of <= 2
            std::vector<char> inh(N, 0);
            for (int g : hsx.first)
                for (int c : p.groups[g].cells) inh[c] = 1;
            for (int g : hsx.second)
                for (int c : p.groups[g].cells) inh[c] = 1;
            std::vector<int> far;  // ids: nary index, or -1 - cage group
            auto meets = [&](const std::vector<int>& cs) {
                int o = 0;
                for (int c : cs) o += !inh[c];
                return o > 3 && o < (int)cs.size();
            };
            for (const NConstraint& k : p.nary)
                if (k.index >= 0 && (p.base_nary < 0 || k.index < p.base_nary) && band_cheap(k) && k.nv() <= 16 &&
                    meets(k.vars))
                    far.push_back(k.index);
            for (int g = 0; g < G0; ++g)
                if (!p.groups[g].complete && p.groups[g].cells.size() > 1 && meets(p.groups[g].cells)) far.push_back(-1 - g);
            if (far.size() > 8) far.resize(8);
            for (size_t i = 0; i < far.size(); ++i) {
                std::vector<int> one{far[i]};
                build_one(hsx, &one);
                for (size_t j = i + 1; j < far.size(); ++j) {
                    std::vector<int> two{far[i], far[j]};
                    build_one(hsx, &two);
                    for (size_t k = j + 1; k < far.size() && k < 6 && P.band_wide_rules >= 3; ++k) {
                        std::vector<int> three{far[i], far[j], far[k]};  // e.g. three little killers through two boxes
                        build_one(hsx, &three);
                    }
                }
            }
        }
        std::stable_sort(regs.begin(), regs.end(), [](const BandRegion& a, const BandRegion& b) {
            const size_t ha = a.lines.size() + a.boxes.size(), hb = b.lines.size() + b.boxes.size();
            return ha != hb ? ha < hb : a.cells.size() < b.cells.size();
        });
        if (wide && (int)regs.size() > P.band_wide_max) {  // the smallest wide regions (by cells; ties by order)
            std::stable_sort(regs.begin(), regs.end(),
                             [](const BandRegion& a, const BandRegion& b) { return a.cells.size() < b.cells.size(); });
            regs.resize(std::max(0, P.band_wide_max));
            std::stable_sort(regs.begin(), regs.end(), [](const BandRegion& a, const BandRegion& b) {
                const size_t ha = a.lines.size() + a.boxes.size(), hb = b.lines.size() + b.boxes.size();
                return ha != hb ? ha < hb : a.cells.size() < b.cells.size();
            });
        }
        // supersets: every house, rule and cage of region i is in region j (then j's constraints imply i's,
        // including i's derived sums)
        auto subset = [](std::vector<int> a, std::vector<int> b) {
            std::sort(a.begin(), a.end());
            std::sort(b.begin(), b.end());
            return std::includes(b.begin(), b.end(), a.begin(), a.end());
        };
        for (size_t i = 0; i < regs.size(); ++i)
            for (size_t j = 0; j < regs.size(); ++j) {
                if (i == j) continue;
                const BandRegion &A = regs[i], &B = regs[j];
                std::vector<int> ha(A.lines), hb(B.lines);
                ha.insert(ha.end(), A.boxes.begin(), A.boxes.end());
                hb.insert(hb.end(), B.boxes.begin(), B.boxes.end());
                if (A.cells.size() <= B.cells.size() && subset(A.cells, B.cells) && subset(ha, hb) &&
                    subset(A.rules, B.rules) && subset(A.cages, B.cages))
                    regs[i].supers.push_back((int)j);
            }
    }
    static const bool dbg = std::getenv("BAND_DEBUG") != nullptr;
    if (dbg) fprintf(stderr, "band: %zu regions\n", regs.size());
    if (regs.empty()) return;
    pm_long budget = BB;
    // per-solve cap: fruitless calls count in full, calls that find moves count prod_w of their work (they pay
    // off, but a puzzle that keeps reaching this tier must stay bounded)
    static const double prod_w = std::getenv("BAND_PROD_W") ? std::atof(std::getenv("BAND_PROD_W")) : 0.0;
    struct Spent {
        pm_long& total; const pm_long& bud; pm_long start; MoveBuf& out; size_t n0; double w; pm_long& all;
        ~Spent() {
            bool found = false;
            for (size_t i = n0; i < out.moves.size(); ++i) found |= out.moves[i].tech == BAND_LOGIC;
            total += found ? (pm_long)(w * (double)(start - bud)) : start - bud;
            all += start - bud;
        }
    } spent_guard{band_spent, budget, budget, out, out.moves.size(), prod_w, band_total};
    std::set<std::vector<uint32_t>> seen_el;
    size_t found_class = 0;
    pm_long n_calls = 0, n_regions = 0;
    const auto t_start = std::chrono::steady_clock::now();
    struct DbgOut {
        bool on; pm_long& calls; pm_long& regs; pm_long& bud; pm_long start_bud; std::chrono::steady_clock::time_point t0;
        ~DbgOut() {
            if (on) fprintf(stderr, "band call: regions %ld brute calls %ld nodes %ld ms %.1f sac_ms %.1f level_ms %.1f\n", regs, calls, start_bud - bud,
                            std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count(), band_t_sac, band_t_level);
            band_t_sac = band_t_level = 0;
        }
    } dbg_out{dbg, n_calls, n_regions, budget, BB, t_start};
    // per call: region -> eliminations (status: -1 not evaluated / aborted, 0 none, 1 some)
    std::vector<int> status(regs.size(), -1);
    std::vector<std::vector<std::array<pm_long, 3>>> results(regs.size());
    auto evaluate = [&](size_t ri) {
        const BandRegion& R = regs[ri];
        if (budget <= 0) return;
        std::vector<int> F;
        for (int c : R.cells)
            if (!vals[c]) F.push_back(c);
        if (F.empty()) { status[ri] = 0; return; }
        std::vector<uint32_t> ckey{(uint32_t)ri, 0xFFFFFFFFu};
        for (int c : R.cells) ckey.push_back(vals[c] ? (0x80000000u | (uint32_t)vals[c]) : cand[c]);
        std::vector<std::array<pm_long, 3>> els;  // (cell*32+digit, level, cases)
        pm_long nodes_used = 0;
        bool done = false;
        auto hit = bcache.find(ckey);
        if (hit != bcache.end()) {
            els = hit->second;
            done = true;
        } else {
            // start state: the region's cells as in the grid (sub-puzzle numbering)
            const int n = (int)R.cells.size();
            std::vector<uint8_t> sv(n);
            std::vector<uint32_t> sc(n);
            for (int i = 0; i < n; ++i) sv[i] = vals[R.cells[i]], sc[i] = vals[R.cells[i]] ? 0 : cand[R.cells[i]];
            const std::vector<int>& pos = R.pos;
            std::vector<uint32_t> sup(N, 0);
            if (bsols.size() < regs.size()) bsols.resize(regs.size());
            auto& known = bsols[ri];
            for (const auto& sl : known) {  // earlier fillings still consistent with the grid support their digits
                bool ok = true;
                for (size_t i = 0; i < R.cells.size() && ok; ++i) {
                    const int c = R.cells[i];
                    ok = vals[c] ? vals[c] == sl[i] : (cand[c] & bit(sl[i])) != 0;
                }
                if (ok)
                    for (size_t i = 0; i < R.cells.size(); ++i) sup[R.cells[i]] |= bit(sl[i]);
            }
            bool aborted = false, dead = false;
            // search work is charged per node x (1 + rule cells / 6): rule consistency checks dominate a node's cost
            pm_long rule_cells = 0;
            for (const NConstraint& k : R.sub->nary) rule_cells += k.bounds_only ? 0 : k.nv();
            const pm_long wgt = 1 + rule_cells / 6;
            const pm_long per = std::max(pm_long(2000), BB / 40) / wgt + 1;
            const pm_long region_end = budget - std::max(per, BB / 8);  // one region takes <= 1/8 of it
            std::map<uint32_t, pm_long> refute_nodes;
            // propagation-only test of a set of forced digits: true = refuted without branching
            auto refuted0 = [&](const std::vector<std::pair<int, int>>& force) {
                std::vector<uint8_t> v2 = sv;
                std::vector<uint32_t> c2 = sc;
                for (auto& f : force) c2[pos[f.first]] &= bit(f.second);
                for (auto& f : force)
                    if (!c2[pos[f.first]]) return true;
                bool complete = true;
                pm_long cost = 0;
                ++n_calls;
                const auto tb0 = std::chrono::steady_clock::now();
                auto sols = brute_solve(*R.sub, {}, 1, 1, &v2, &c2, &complete, &cost, true);
                band_t_level += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - tb0).count();
                budget -= cost * wgt;
                return sols.empty() && complete;
            };
            for (int c : F) {
                for (uint32_t m = cand[c] & ~sup[c]; m && !aborted; m &= m - 1) {
                    const int v = lowdigit(m);
                    if (sup[c] & bit(v)) continue;
                    std::vector<uint8_t> v2 = sv;
                    std::vector<uint32_t> c2 = sc;
                    c2[pos[c]] = bit(v);
                    bool complete = true;
                    pm_long cost = 0;
                    ++n_calls;
                    const auto tb0 = std::chrono::steady_clock::now();
                    auto sols = brute_solve(*R.sub, {}, 1, std::min(per, std::max((budget - region_end) / wgt, pm_long(1))), &v2,
                                            &c2, &complete, &cost, true);
                    band_t_sac += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - tb0).count();
                    budget -= cost * wgt;
                    nodes_used += cost;
                    if (!sols.empty()) {
                        for (int x : F) sup[x] |= bit(sols[0][pos[x]]);
                        if (known.size() < 256) {
                            std::vector<uint8_t> sl(R.cells.size());
                            for (size_t i = 0; i < R.cells.size(); ++i) sl[i] = (uint8_t)sols[0][i];
                            known.push_back(std::move(sl));
                        }
                    } else if (!complete) {
                        sup[c] |= bit(v);  // unknown: kept
                    } else {
                        refute_nodes[(uint32_t)c * 32 + v] = cost;
                    }
                    if (budget <= 0 || budget <= region_end) aborted = true;
                }
                if (aborted) break;
            }
            for (int c : F) dead |= (cand[c] & sup[c]) == 0;
            if (!aborted && !dead) {
                // refutation level (search-order independent): 0 = propagation alone (the house sums, cage
                // combinations, singles); 1 = one case split on a cell, every case dies by propagation (cases =
                // the smallest such split); 2 = deeper search (cases = search nodes)
                for (int c : F)
                    for (uint32_t m = cand[c] & ~sup[c]; m; m &= m - 1) {
                        const int v = lowdigit(m);
                        const uint32_t e = (uint32_t)c * 32 + v;
                        pm_long level = 2, cases = std::max(pm_long(2), refute_nodes.count(e) ? refute_nodes[e] : pm_long(2));
                        static const bool nolevel = std::getenv("BAND_NOLEVEL") != nullptr;
                        if (nolevel) {
                        } else if (refuted0({{c, v}})) {
                            level = 0, cases = 1;
                        } else {
                            pm_long best = 0;
                            std::vector<int> order(F);  // fewest candidates first; stop at a 2-way split
                            std::stable_sort(order.begin(), order.end(), [&](int x, int y) { return popc(cand[x]) < popc(cand[y]); });
                            for (int x : order) {
                                if (x == c) continue;
                                const int k = popc(cand[x]);
                                if (k < 2 || (best && k >= best)) continue;
                                bool all = true;
                                for (uint32_t w = cand[x]; w && all; w &= w - 1) all = refuted0({{c, v}, {x, lowdigit(w)}});
                                if (all) {
                                    best = k;
                                    if (k == 2) break;
                                }
                            }
                            if (best) level = 1, cases = best;
                        }
                        els.push_back({(pm_long)e, level, cases});
                    }
            }
            done = !aborted;
            if (!aborted && bcache.size() < 5000) bcache[ckey] = els;
        }
        ++n_regions;
        if ((wide && dbg && R.cells.size() >= 20) || std::getenv("BAND_DUMP"))
            fprintf(stderr, "wide eval: %zu houses %zu rules %zu cells done %d els %zu nodes %ld budget %ld\n",
                    R.lines.size() + R.boxes.size(), R.rules.size(), R.cells.size(), (int)done, els.size(), nodes_used,
                    budget);
        (void)nodes_used;
        if (done) {
            status[ri] = els.empty() ? 0 : 1;
            results[ri] = std::move(els);
        }
    };
    // smallest regions first; a region whose superset (more houses / rules, same or more cells) is known to
    // have no elimination in this state has none either (skipped)
    auto cached_none = [&](int j) {  // a superset already known (this state) to have no elimination
        if (status[j] >= 0) return status[j] == 0;
        std::vector<uint32_t> key{(uint32_t)j, 0xFFFFFFFFu};
        for (int c : regs[j].cells) key.push_back(vals[c] ? (0x80000000u | (uint32_t)vals[c]) : cand[c]);
        auto it = bcache.find(key);
        if (it == bcache.end()) return false;
        status[j] = it->second.empty() ? 0 : 1;
        results[j] = it->second;
        return status[j] == 0;
    };
    // moves of one region, one per refutation level; true if one was found without deep search
    auto emit_region = [&](size_t ri, const std::vector<std::array<pm_long, 3>>& els) {
        const BandRegion& R = regs[ri];
        std::vector<int> F;
        for (int c : R.cells)
            if (!vals[c]) F.push_back(c);
        bool any = false;
        for (int lv = 0; lv <= 2; ++lv) {
            std::vector<uint32_t> el;
            pm_long cases = 1;
            for (auto& t : els)
                if (t[1] == lv) el.push_back((uint32_t)t[0]), cases = std::max(cases, t[2]);
            if (el.empty() || !seen_el.insert(el).second) continue;
            any = any || lv <= 1;
            Move& m = new_move(out, BAND_LOGIC, 1.0, (int)(R.lines.size() + R.boxes.size() + R.rules.size() + R.cages.size()));
            for (uint32_t e : el) add_elim(out, m, (int)(e / 32), (int)(e % 32));
            set_pattern(out, m, F);
            std::vector<int> gs(R.lines);
            gs.insert(gs.end(), R.boxes.begin(), R.boxes.end());
            add_expl(out, m, EX_BASE, gs);
            if (!R.cages.empty()) add_expl(out, m, EX_COVER, R.cages);
            if (!R.rules.empty()) add_expl(out, m, EX_RULE, R.rules);
            const int nunits = (int)(R.lines.size() + R.boxes.size() + R.rules.size() + R.cages.size());
            uint32_t dm = 0;
            for (int c : F) dm |= cand[c];
            const int cases_i = (int)std::min(cases, pm_long(1000000000));
            meta9(m, std::min(N, (int)F.size()), nunits, popc(dm), cases_i, lv, 1, 1, 1, pspread(F));
            m.code = R.lines.size() + R.boxes.size() == 1 ? 3354 : R.lines.size() + R.boxes.size() == 2 ? 3355 : 3356;
            pm_long xm[XM_N] = {(pm_long)R.lines.size(), (pm_long)R.boxes.size(), (pm_long)(R.rules.size() + R.cages.size()),
                             (pm_long)el.size(), (pm_long)F.size(), lv, cases, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
        return any;
    };
    // phase 1: refutations by propagation alone (the derived house sums, cage combinations, singles of the
    // sub-puzzle: "the maths", no cases), all regions smallest first; a size class with such moves ends it
    static const bool phase1 = std::getenv("BAND_PHASE1") != nullptr;  // enables the phase-1 pass
    if (phase1) {
        size_t a_class = 0;
        bool a_any = false;
        if (bsols.size() < regs.size()) bsols.resize(regs.size());
        for (size_t ri = 0; ri < regs.size(); ++ri) {
            const BandRegion& R = regs[ri];
            if (a_class && R.lines.size() + R.boxes.size() > a_class) break;
            std::vector<uint32_t> key{(uint32_t)ri, 0xFFFFFFFEu};
            for (int c : R.cells) key.push_back(vals[c] ? (0x80000000u | (uint32_t)vals[c]) : cand[c]);
            std::vector<std::array<pm_long, 3>> els;
            auto hit = bcache.find(key);
            if (hit != bcache.end()) {
                els = hit->second;
            } else {
                const int n = (int)R.cells.size();
                std::vector<uint8_t> sv(n);
                std::vector<uint32_t> sc(n);
                for (int i = 0; i < n; ++i) sv[i] = vals[R.cells[i]], sc[i] = vals[R.cells[i]] ? 0 : cand[R.cells[i]];
                std::vector<uint32_t> sup(n, 0);
                for (const auto& sl : bsols[ri]) {  // digits of a known filling cannot be refuted
                    bool ok = true;
                    for (int i = 0; i < n && ok; ++i) ok = sv[i] ? sv[i] == sl[i] : (sc[i] & bit(sl[i])) != 0;
                    if (ok)
                        for (int i = 0; i < n; ++i) sup[i] |= bit(sl[i]);
                }
                bool dead = false;
                for (int i = 0; i < n && !dead; ++i) {
                    if (sv[i]) continue;
                    uint32_t lost = 0;
                    for (uint32_t m = sc[i] & ~sup[i]; m; m &= m - 1) {
                        const int v = lowdigit(m);
                        std::vector<uint8_t> v2 = sv;
                        std::vector<uint32_t> c2 = sc;
                        c2[i] = bit(v);
                        bool complete = true;
                        pm_long cost = 0;
                        ++n_calls;
                        auto sols = brute_solve(*R.sub, {}, 1, 1, &v2, &c2, &complete, &cost, true);
                        budget -= cost;
                        if (sols.empty() && complete) {
                            lost |= bit(v);
                            els.push_back({(pm_long)R.cells[i] * 32 + v, 0, 1});
                        } else if (!sols.empty() && bsols[ri].size() < 256) {
                            std::vector<uint8_t> sl(n);
                            for (int k = 0; k < n; ++k) sl[k] = (uint8_t)sols[0][k];
                            for (int k = 0; k < n; ++k) sup[k] |= bit(sl[k]);
                            bsols[ri].push_back(std::move(sl));
                        }
                    }
                    dead = lost == sc[i];  // inconsistent state: leave it
                }
                if (dead) els.clear();
                std::sort(els.begin(), els.end());
                if (bcache.size() < 20000) bcache[key] = els;
            }
            ++n_regions;
            if (!els.empty() && emit_region(ri, els)) a_class = R.lines.size() + R.boxes.size(), a_any = true;
        }
        if (a_any) return;
    }
    // phase 2: singleton consistency by bounded search (levels 1 / 2)
    for (size_t ri = 0; ri < regs.size(); ++ri) {
        const BandRegion& R = regs[ri];
        if (found_class && R.lines.size() + R.boxes.size() > found_class) break;
        if (status[ri] < 0) {
            bool skip = false;
            for (int j : R.supers) skip = skip || cached_none(j);
            if (skip) continue;
            evaluate(ri);
        }
        if (status[ri] != 1) continue;
        if (emit_region(ri, results[ri])) found_class = R.lines.size() + R.boxes.size();
    }
}

}  // namespace cs
