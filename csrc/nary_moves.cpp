// Moves of the n-ary rules (cages, lines, sums): combinations, combination locks, innie sums, direct reads.
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
#include "solver.hpp"
#include "solver_util.hpp"

namespace cs {

// ------------------------------------------------- n-ary constraints --
static const pm_long GAC_BUDGET = 200000;
static int combo_tech(int type, int line_kind = -1) {
    if (line_kind >= 0) return LINE_RANGE;
    switch (type) {
        case NT_SANDWICH: return SANDWICH_COMBO;
        case NT_XSUM: return XSUM_COMBO;
        case NT_SKYLINE: return SKYLINE_COMBO;
        case NT_SAMESET: return LOL_COMBO;
        case NT_COUNT: return COUNT_COMBO;
        case NT_DIGITSET: return COUNT_COMBO;
        case NT_DISTINCT: return COUNT_COMBO;
        case NT_SUM: return SUM_COMBO;
        case NT_ARROW: return ARROW_COMBO;
        case NT_SET: return SET_COMBO;
        case NT_EQSUM: return EQSUM_COMBO;
        default: return TABLE_COMBO;
    }
}

// plain consistency result, cached per constraint while its domains are unchanged
// cross-call cache: nary_gac is a pure function of (constraint, domains, requirement, D), but every
// state_moves / solve call builds a new Solver whose gcache starts empty -- band_path re-enumerated the same big rules
// hundreds of times per puzzle. Thread-local (featurize threads), keyed by (puzzle uid, constraint, requirement, full
// domains: exact), bounded (cleared when it reaches GAC_XCACHE_MAX entries).
namespace {
struct XKey {
    uint64_t uid; const NConstraint* k; int v; uint64_t mask; std::vector<uint32_t> dom;
    bool operator==(const XKey& o) const { return uid == o.uid && k == o.k && v == o.v && mask == o.mask && dom == o.dom; }
};
struct XKeyHash {
    size_t operator()(const XKey& x) const {
        size_t h = std::hash<uint64_t>()(x.uid) ^ (std::hash<const void*>()(x.k) << 1) ^ (std::hash<uint64_t>()(x.mask * 31 + (uint64_t)x.v) << 2);
        for (uint32_t d : x.dom) h = h * 1000003u ^ d;
        return h;
    }
};
constexpr size_t GAC_XCACHE_MAX = 60000;
thread_local std::unordered_map<XKey, GacOut, XKeyHash> g_xcache;
}  // namespace

const GacOut& Solver::gac_cached(const NConstraint& k, const uint32_t* dom, int req_v, uint64_t req_mask) {
    GacCache& e = gcache[GacKey{&k, req_v, req_mask}];
    if (e.valid && std::equal(dom, dom + k.nv(), e.dom.begin())) return e.out;
    e.dom.assign(dom, dom + k.nv());
    e.valid = true;
    XKey xk{p.uid, &k, req_v, req_mask, e.dom};
    auto it = g_xcache.find(xk);
    if (it != g_xcache.end()) {
        e.out = it->second;
        return e.out;
    }
    std::vector<GacReq> req;
    if (req_v) req.push_back({req_v, req_mask});
    nary_gac(k, dom, req, GAC_BUDGET, p.D, e.out);
    if (g_xcache.size() >= GAC_XCACHE_MAX) g_xcache.clear();
    g_xcache.emplace(std::move(xk), e.out);
    return e.out;
}

void Solver::nary_dom(const NConstraint& k, uint32_t* dom) const {
    for (int i = 0; i < k.nv(); ++i) {
        int c = k.vars[i];
        dom[i] = vals[c] ? bit(vals[c]) : cand[c];
    }
}

// COMBINATION family: generalized arc consistency on one constraint
void Solver::nary_combination(MoveBuf& out, int part) {
    bool all_off = true;
    for (int t : {SUM_COMBO, ARROW_COMBO, SET_COMBO, EQSUM_COMBO, TABLE_COMBO, SANDWICH_COMBO, XSUM_COMBO,
                  SKYLINE_COMBO, LOL_COMBO, COUNT_COMBO, LINE_RANGE})
        all_off &= disabled[t] != 0;
    if (all_off) return;  // pure generator: filtered anyway
    uint32_t dom[64];
    static const std::vector<GacReq> noreq;
    for (const NConstraint& k : p.nary) {
        if ((part == 0 && k.type == NT_SAMESET) || (part == 1 && k.type != NT_SAMESET)) continue;
        int unplaced = 0;
        for (int c : k.vars) unplaced += !vals[c];
        if (!unplaced) continue;
        nary_dom(k, dom);
        const GacOut& o = gac_cached(k, dom);
        int n = 0;
        for (int i = 0; i < k.nv(); ++i)
            if (!vals[k.vars[i]]) n += popc(cand[k.vars[i]] & ~o.sup[i]);
        if (!n) continue;
        Move& m = new_move(out, combo_tech(k.type, k.line_kind), k.shape, unplaced);
        for (int i = 0; i < k.nv(); ++i) {
            int c = k.vars[i];
            if (vals[c]) continue;
            for (uint32_t dm = cand[c] & ~o.sup[i]; dm; dm &= dm - 1) add_elim(out, m, c, lowdigit(dm));
        }
        pm_long combos = std::min<pm_long>(o.count, pm_long(1000000000));
        m.nk = NM_NARY;
        m.na = k.index;
        {
            std::vector<int> pc;
            for (int c : k.vars)
                if (!vals[c]) pc.push_back(c);
            set_pattern(out, m, pc);
        }
        m.code = k.type == NT_SANDWICH ? 3301 : k.type == NT_XSUM ? 3302 : k.type == NT_SKYLINE ? 3303
                 : k.type == NT_TABLE && k.named && k.index >= 0 && k.index < 1000 ? 6000 + k.index
                 : k.type == NT_DIGITSET ? 3320
                 : k.type == NT_SAMESET ? (k.setkind == 4 ? 3308 : k.setkind == 3 ? 3307 : k.setkind == 2 ? 3306 : k.setkind ? 3305 : 3304) : 0;
        if (k.type == NT_TABLE) m.tab_live = table_live(k);
        pm_long line_xm[4] = {0, 0, 0, 0};
        if (k.line_kind >= 0) {  // LineRange: one move per line insight
            int placed = 0, changed = 0, depth = 0, w5 = 1;
            for (int i = 0; i < k.nv(); ++i) placed += vals[k.vars[i]] != 0;
            for (int i = 0; i < k.nv(); ++i) {
                int c = k.vars[i];
                if (vals[c] || !(cand[c] & ~o.sup[i])) continue;
                ++changed;
                if (cand[c] & ~o.sup[i] & ~bit(5)) w5 = 0;
                int best = 1 << 20;
                for (int x = 0; x < k.nv(); ++x)
                    if (vals[k.vars[x]]) best = std::min(best, std::abs(x - i));
                depth = std::max(depth, placed ? best : 0);
            }
            bool whisper = k.line_kind == LK_WHISPER;
            m.code = 4000 + 10 * k.line_kind + (whisper && w5 ? 2 : placed == 0 ? 1 : 0);
            line_xm[0] = changed;
            line_xm[1] = placed;
            line_xm[2] = depth;
            line_xm[3] = k.nv();
        }
        uint32_t involved = 0;  // digits = how many digits are in play (the combination count is in xm[2])
        for (int c : k.vars)
            if (!vals[c]) involved |= cand[c];
        set_meta(m, unplaced, 1, popc(involved), 0, o.set_unique ? 0 : 1, k.arith ? 1 : 0,
                 k.distinct ? 0 : 1, 1, k.shape);
        pm_long xm[XM_N] = {k.type, k.index, combos, o.set_unique, k.arith, k.distinct, k.nv(), o.complete, 0, 0};
        if (k.line_kind >= 0) {
            pm_long lx[XM_N] = {k.line_kind, k.index, line_xm[3], line_xm[0], line_xm[1], line_xm[2], combos, 0, 0, 0};
            std::copy(lx, lx + XM_N, xm);
        }
        std::copy(xm, xm + XM_N, m.xm);
    }
}

// COMBO_LOCK: (a) digit v in every consistent assignment and its candidate
// cells inside the scope share a group -> v leaves the rest of that group;
// (b) a house's candidate cells for v all lie in the scope -> assignments
// must contain v there -> re-run consistency with that requirement.
void Solver::combo_lock(MoveBuf& out) {
    if (disabled[COMBO_LOCK]) return;
    uint32_t dom[64];
    static const std::vector<GacReq> noreq;
    std::vector<GacReq> req(1);
    std::vector<int> U, groupsU;
    for (int pass = 0; pass < 3; ++pass) {
        const std::vector<NConstraint>& list = pass == 0 ? p.nary : pass == 1 ? p.cage_nary : p.innie_nary;
        for (const NConstraint& k : list) {
            if (k.type == NT_SAMESET) continue;  // leftover equalities: no combinations to lock
            int unplaced = 0;
            for (int c : k.vars) unplaced += !vals[c];
            if (!unplaced) continue;
            nary_dom(k, dom);
            const GacOut& o = gac_cached(k, dom);
            pm_long combos = std::min<pm_long>(o.count, pm_long(1000000000));
            const int nv = k.nv();
            auto in_scope = [&](int c) { return std::find(k.vars.begin(), k.vars.end(), c) != k.vars.end(); };
            // (a) must-contain
            if (o.any) {
                for (uint32_t mm = o.must; mm; mm &= mm - 1) {
                    int v = lowdigit(mm);
                    uint32_t b = bit(v);
                    bool placed = false;
                    U.clear();
                    for (int c : k.vars) {
                        if (vals[c] == v) placed = true;
                        if (!vals[c] && (cand[c] & b)) U.push_back(c);
                    }
                    if (placed || U.empty()) continue;
                    groupsU.clear();
                    for (int gi : p.groups_of[U[0]]) {
                        if (gi == k.group) continue;
                        bool all = true;
                        for (int c : U)
                            if (!tbit(p.gbits(gi), c)) all = false;
                        if (all) groupsU.push_back(gi);
                    }
                    int mi = -1;
                    std::vector<char> done(p.N, 0);
                    for (int gi : groupsU)
                        for (int c : p.groups[gi].cells) {
                            if (done[c] || vals[c] || !(cand[c] & b) || in_scope(c)) continue;
                            done[c] = 1;
                            if (mi < 0) {
                                new_move(out, COMBO_LOCK, k.shape, (int)U.size());
                                mi = (int)out.moves.size() - 1;
                            }
                            add_elim(out, out.moves[mi], c, v);
                        }
                    if (mi >= 0) {
                        Move& m = out.moves[mi];
                        m.nk = NM_NARY;
                        m.na = k.index;
                        m.nb = k.group;
                        {
                            std::vector<int> pc;
                            for (int c : k.vars)
                                if (!vals[c]) pc.push_back(c);
                            set_pattern(out, m, pc);
                        }
                        set_meta(m, (int)U.size(), 2, 1, 0, 0, k.arith ? 1 : 0, 0, 1, k.shape);
                        pm_long xm[XM_N] = {k.type, k.index, combos, 0, v, groupsU.empty() ? -1 : groupsU[0],
                                         (pm_long)U.size(), k.group, 0, 0};
                        std::copy(xm, xm + XM_N, m.xm);
                        {
                            std::vector<int> lk{0, v};
                            lk.insert(lk.end(), groupsU.begin(), groupsU.end());
                            add_expl(out, m, EX_LOCK, lk);
                        }
                        // named killer moves: cage/unit overlap (a cage's must-digit confined to a house)
                        if (pass == 1) m.code = 3610;
                        else if (pass == 2) m.code = 3612;  // innie region must contain a digit
                        if (k.innie >= 0) region_expl(out, m, p.big_innies[k.innie]);
                    }
                }
            }
            // (b) house forces v into the scope (not for huge equal-sum rules: no exact engine there)
            if (k.type == NT_EQSUM && k.nv() > 12) continue;
            for (int hi : p.houses) {
                if (hi == k.group) continue;
                for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
                    int v = lowdigit(mm);
                    uint32_t b = bit(v);
                    uint64_t vm = 0;
                    bool inside = true, any = false;
                    for (int c : p.groups[hi].cells) {
                        if (vals[c] || !(cand[c] & b)) continue;
                        any = true;
                        int i = (int)(std::find(k.vars.begin(), k.vars.end(), c) - k.vars.begin());
                        if (i >= nv) {
                            inside = false;
                            break;
                        }
                        vm |= 1ULL << i;
                    }
                    if (!any || !inside) continue;
                    const GacOut& o2 = gac_cached(k, dom, v, vm);
                    int n = 0;
                    for (int i = 0; i < nv; ++i)
                        if (!vals[k.vars[i]]) n += popc(cand[k.vars[i]] & ~o2.sup[i] & o.sup[i]);
                    if (!n) continue;
                    Move& m = new_move(out, COMBO_LOCK, k.shape, __builtin_popcountll(vm));
                    for (int i = 0; i < nv; ++i) {
                        int c = k.vars[i];
                        if (vals[c]) continue;
                        for (uint32_t dm = cand[c] & ~o2.sup[i] & o.sup[i]; dm; dm &= dm - 1)
                            add_elim(out, m, c, lowdigit(dm));
                    }
                    m.nk = NM_NARY;
                    m.na = k.index;
                    m.nb = k.group;
                    {
                        std::vector<int> pc;
                        for (int c : k.vars)
                            if (!vals[c]) pc.push_back(c);
                        set_pattern(out, m, pc);
                    }
                    int nU = __builtin_popcountll(vm);
                    set_meta(m, unplaced, 2, 1, 0, 1,
                             k.arith ? 1 : 0, 0, 1, k.shape);
                    pm_long xm[XM_N] = {k.type, k.index, combos, 1, v, hi, nU, k.group, 0, 0};
                    std::copy(xm, xm + XM_N, m.xm);
                    add_expl(out, m, EX_LOCK, {1, v, hi});
                    // a house's digit captured by a cage (all its places inside the cage): captured candidates
                    if (pass == 1) m.code = 3611;
                    else if (pass == 2) m.code = 3613;
                    if (k.innie >= 0) region_expl(out, m, p.big_innies[k.innie]);
                }
            }
        }
    }
}

// rule-of-45 regions larger than the classic innie limit, as derived sum
// constraints (Innie/Outie(sum)): consistency over the region
void Solver::innie_sum(MoveBuf& out) {
    if (disabled[INNIE_X]) return;
    uint32_t dom[64];
    for (const NConstraint& k : p.innie_nary) {
        int unplaced = 0;
        for (int c : k.vars) unplaced += !vals[c];
        if (!unplaced) continue;
        nary_dom(k, dom);
        const GacOut& o = gac_cached(k, dom);
        int n = 0;
        for (int i = 0; i < k.nv(); ++i)
            if (!vals[k.vars[i]]) n += popc(cand[k.vars[i]] & ~o.sup[i]);
        if (!n) continue;
        const Group& H = p.groups[k.house];
        Move& m = new_move(out, INNIE_X, H.shape, k.n_cages);
        for (int i = 0; i < k.nv(); ++i) {
            int c = k.vars[i];
            if (vals[c]) continue;
            for (uint32_t dm = cand[c] & ~o.sup[i]; dm; dm &= dm - 1) add_elim(out, m, c, lowdigit(dm));
        }
        pm_long combos = std::min<pm_long>(o.count, pm_long(1000000000));
        m.nk = k.outie ? NM_OUTIE : NM_INNIE;
        m.na = k.house;
        {
            std::vector<int> pc;
            for (int c : k.vars)
                if (!vals[c]) pc.push_back(c);
            set_pattern(out, m, pc);
        }
        uint32_t involved = 0;
        for (int c : k.vars)
            if (!vals[c]) involved |= cand[c];
        set_meta(m, k.nv(), k.n_cages + 1, popc(involved), 0, 0, 1, 0, 1, H.shape);
        pm_long xm[XM_N] = {k.house, k.outie, k.nv(), combos, k.n_cages, k.distinct, o.complete, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
        if (k.innie >= 0) region_expl(out, m, p.big_innies[k.innie]);
        if (k.set_theory) m.code = 3605;  // set theory with arrows (lines replaced by circles)
    }
}

// direct (no notes): a constraint with one empty cell whose value is forced by
// the arithmetic / set rule alone
void Solver::nary_direct(MoveBuf& out) {
    if (disabled[NARY_D]) return;
    uint32_t dom[64];
    static const std::vector<GacReq> noreq;
    for (const NConstraint& k : p.nary) {
        int u = -1, nu = 0;
        for (int i = 0; i < k.nv(); ++i)
            if (!vals[k.vars[i]]) {
                ++nu;
                u = i;
            }
        if (nu != 1) continue;
        for (int i = 0; i < k.nv(); ++i) dom[i] = vals[k.vars[i]] ? bit(vals[k.vars[i]]) : p.domains[k.vars[i]];
        GacOut o;
        nary_gac(k, dom, noreq, GAC_BUDGET, p.D, o);
        if (popc(o.sup[u]) != 1) continue;
        Move& m = new_move(out, NARY_D, k.shape, 1);
        out.covers.push_back({K_CAGESUM, k.shape, 1});
        m.cov_n = 1;
        m.pc = k.vars[u];
        m.pv = lowdigit(o.sup[u]);
        m.nk = NM_NARY;
        m.na = k.index;
        set_meta(m, k.nv(), 2, 1, 0, 0, k.arith ? 1 : 0, 0, 0, k.shape);
        pm_long xm[XM_N] = {k.type, k.index, k.nv(), 0, 0, 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
        if (k.type == NT_TABLE) {
            m.tab_live = table_live(k);
            if (k.named && k.index >= 0 && k.index < 1000) m.code = 6000 + k.index;
        }
    }
}

// live tuples of a table constraint: rows consistent with the placed digits and the candidates
pm_long Solver::table_live(const NConstraint& k) const {
    if (k.type != NT_TABLE || k.arity <= 0) return 0;
    const int A = k.arity;
    const size_t R = k.rows.size() / (size_t)A;
    pm_long n = 0;
    for (size_t r = 0; r < R; ++r) {
        bool ok = true;
        for (int q = 0; q < A && ok; ++q) {
            const int c = k.vars[k.pvar[q]], v = k.rows[r * A + q];
            ok = vals[c] ? vals[c] == v : (v >= 1 && (cand[c] & bit(v)));
        }
        n += ok;
    }
    return n;
}

// _trial / _contradicts

}  // namespace cs
