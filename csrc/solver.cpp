#include <tuple>
#include "portable.hpp"
#include <cmath>
#include <algorithm>
#include <cstring>
#include <chrono>
// Port of grader/solver.py. Function-by-function correspondence is kept on
// purpose (comments name the Python method) so parity can be audited.
#include "solver.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <set>

namespace cs {

// ------------------------------------------------------------- helpers --
// k-combinations of [0,n) in itertools.combinations order; f(idx) -> stop?
template <class F>
static bool for_combos(int n, int k, F&& f) {
    if (k < 0 || k > n) return false;
    int sbuf[64];
    std::vector<int> hbuf;
    int* idx = sbuf;
    if (k > 64) {
        hbuf.resize(k);
        idx = hbuf.data();
    }
    for (int i = 0; i < k; ++i) idx[i] = i;
    while (true) {
        if (f((const int*)idx)) return true;
        int i = k - 1;
        while (i >= 0 && idx[i] == n - k + i) --i;
        if (i < 0) return false;
        ++idx[i];
        for (int j = i + 1; j < k; ++j) idx[j] = idx[j - 1] + 1;
    }
}

static inline uint64_t mkkey(int type, int a, int b, int c) {
    return ((uint64_t)type << 60) | ((uint64_t)(uint32_t)a << 40) | ((uint64_t)(uint32_t)b << 20) | (uint64_t)(uint32_t)c;
}

void meta_vector(const Move& m, double x[10]) {
    x[0] = 1.0;
    x[1] = std::log((double)std::max(m.meta[0], 1));
    x[2] = std::log((double)std::max(m.meta[1], 1));
    x[3] = std::log((double)std::max(m.meta[2], 1));
    for (int i = 3; i < 8; ++i) x[i + 1] = (double)m.meta[i];
    double sp = m.spread;
    x[9] = std::log((1e-6 > sp) ? 1e-6 : sp);
}

double Params::difficulty(const Move& m, const Cover* covers, int D) const {
    if (m.tech == TAKE_NOTES || m.tech == SNYDER_MARKS) return B[m.tech];
    // proof by full search where a guess would go (exhaust(), extra = -1): at least what guessing that cell costs
    if (m.tech == TRIAL && m.extra < 0) return B[GUESS] * size(D) * (1.0 + guess_k * (double)m.meta[0] / 10.0);
    // params mental_floor: a move done in the head (no notes) costs at least its written counterpart -- the same
    // pattern priced with notes (MentalNotesSingle: the notes technique it runs in the head, its 'extra')
    static thread_local bool in_floor = false;
    if (mental_floor && !in_floor && (priced_meta(m) || (!theta_full.empty() && m.has_meta)) && m.meta[7] == 0 &&
        (m.tech == MENTAL_D || m.tech == MENTAL_CHAIN || m.tech == MENTAL_NOTES || m.tech == EITHER_WAY ||
         m.tech == WHAT_IF || m.tech == SHORT_TRIAL)) {
        in_floor = true;
        const double base = difficulty(m, covers, D);
        Move w = m;
        w.meta[7] = 1;
        if (theta_full_v2 && !theta_full.empty() && w.has_desc) w.desc[7] = 1.0;
        if (m.tech == MENTAL_NOTES && m.extra > 0 && m.extra < N_TECH) w.tech = m.extra;
        const double written = difficulty(w, covers, D);
        in_floor = false;
        return std::max(base, written);
    }
    double d;
    // params meta_theta_full: EVERY technique priced by its full structural vector (meta10, 8 descriptors,
    // log1p scan): no per-technique B, family / tech offsets or technique multipliers; direct cover terms, the
    // human-mode load and the guess cap stay
    if (!theta_full.empty() && m.has_meta) {
        double x[10] = {0};
        meta_vector(m, x);
        if (theta_full_v2) x[4] = std::log1p(std::max(0.0, x[4]));
        CompSum s;
        for (int i = 0; i < 10 && i < (int)theta_full.size(); ++i) s.add(theta_full[i] * x[i]);
        for (int i = 0; i < 8 && 10 + i < (int)theta_full.size(); ++i) s.add(theta_full[10 + i] * (m.has_desc ? m.desc[i] : 0.0));
        if (theta_full.size() > 18) s.add(theta_full[18] * std::log1p(std::max(0.0, m.scan)));
        if (theta_enum != 0.0) s.add(theta_enum * m.enumv);   // D5: enumeration size of the sum rules touched
        if (theta_interact.size() >= 3) {   // D6: depth interactions (products of the move's own measured columns)
            const double br = m.has_desc ? m.desc[0] : 0.0, dp = m.has_desc ? m.desc[1] : 0.0;
            s.add(theta_interact[0] * dp * x[1]);
            s.add(theta_interact[1] * dp * x[4]);
            s.add(theta_interact[2] * dp * br);
        }
        if (m.tech >= 0 && m.tech < (int)tech_obsc.size()) s.add(tech_obsc[m.tech]);   // obscurity
        d = std::exp(std::min(s.value(), 6.907755278982137)) * size(D);   // cap log price at log(1000): extreme
        if (is_direct(m.tech))                                              // descriptors overflowed exp() to inf
            for (int i = 0; i < m.cov_n; ++i) {
                const Cover& c = covers[m.cov_off + i];
                double kk = c.kind < (int)K.size() ? K[c.kind] : (c.kind == K_LINE ? 0.35 : 0.45);
                d += kk * py_pow(c.shape, gamma) * (double)c.u;
            }
        if (human && m.has_load) {
            double e = 0.0;
            for (int j = 0; j < LOAD_N; ++j) {
                double over = (double)m.load[j] - hbudget[j];
                if (over > 0.0) e += hk[j] * over;
            }
            d *= std::exp(e);
        }
        const double cap = B[GUESS];
        if (cap != 0.0 && m.tech != GUESS && d > cap)
            d = cap_pow > 0.0 ? cap + py_pow(d - cap, cap_pow) : cap_tau > 0.0 ? cap + cap_tau * std::log1p((d - cap) / cap_tau) : cap;
        return d;
    }
    // the meta-theta model only prices techniques it was fitted on (codes < meta_max_tech); newer ones
    // use their base difficulty B (extrapolating the structural model to them is meaningless)
    // FIREWORKS: a named pattern without an own price (structural model only, whatever meta_max_tech says)
    if (has_theta && priced_meta(m) && (m.tech < meta_max_tech || m.tech == FIREWORKS || m.tech == HUMAN_CASE || m.tech == COMBO_POS ||
         m.tech == CLIQUE_HOUSE || m.tech == LINE_SETS || m.tech == LINE_CLUES ||
         m.tech == WEIGHTED_SUMS) &&
        !meta_excl[m.tech]) {
        double x[10];
        meta_vector(m, x);
        CompSum s;
        size_t n = std::min<size_t>(theta.size(), 10);
        for (size_t i = 0; i < n; ++i) s.add(theta[i] * x[i]);
        double z = s.value();
        if (theta_ac != 0.0) z += theta_ac * (x[6] * x[1]);  // arith x log cells (params meta_theta_arith_cells)
        d = std::exp(z) * size(D);
        if (has_offset[m.tech]) d *= std::exp(tech_offset[m.tech]);
    } else {
        const double b = (m.tech == FIREWORKS && B[m.tech] <= 0.0) ? B[HTRIPLE]
                         : (m.tech == HUMAN_CASE && B[m.tech] <= 0.0) ? B[ALS_XZ]
                         : ((m.tech == COMBO_POS || m.tech == CLIQUE_HOUSE || m.tech == LINE_SETS || m.tech == LINE_CLUES ||
         m.tech == WEIGHTED_SUMS) && B[m.tech] <= 0.0) ? B[HTRIPLE]
                         : B[m.tech];  // no own price
        d = b * py_pow(m.shape, gamma) * size(D);
    }
    if (is_direct(m.tech)) {
        for (int i = 0; i < m.cov_n; ++i) {
            const Cover& c = covers[m.cov_off + i];
            double kk = c.kind < (int)K.size() ? K[c.kind] : (c.kind == K_LINE ? 0.35 : 0.45);
            d += kk * py_pow(c.shape, gamma) * (double)c.u;
        }
    }
    if (m.tech == FORCING || m.tech == DYN_FORCING || m.tech == NESTED_FORCING) {
        // forcing chains: priced by nesting level, branching and propagation size
        const int level = m.tech - FORCING;
        d *= std::exp(fc_depth * level) * py_pow((double)std::max(m.extra, 1), fc_branch) *
             (1.0 + std::log1p((double)std::max(m.meta[0], 0)));
    }
    if (m.tech == COLOUR_ALGEBRA && priced_meta(m) && colour_chain_k != 0.0)  // colours / labels, chain length
        d *= 1.0 + colour_chain_k * (0.1 * (double)std::max(m.meta[1] - 1, 0) + 0.15 * (double)m.meta[3]);
    if (m.tab_live > 1 && priced_meta(m) && k_tab != 0.0 &&
        (m.tech == LINE_D || m.tech == MENTAL_D || m.tech == NARY_D || m.tech == TABLE_COMBO))
        d *= 1.0 + k_tab * std::log((double)m.tab_live);  // case analysis over the table's live tuples
    if (m.tech == SUM_ALGEBRA && priced_meta(m))  // units combined, chain of bounds
        d *= 1.0 + 0.1 * (double)std::max(m.meta[1] - 2, 0) + 0.25 * (double)std::max(m.meta[3] - 1, 0);
    if (m.tech == BAND_LOGIC && priced_meta(m))  // units taken together, open cells; search it needed (cases)
        d *= (1.0 + 0.1 * (double)std::max(m.meta[1] - 3, 0) + 0.02 * (double)std::max(m.meta[0] - 9, 0)) *
             (1.0 + band_k * std::log((double)std::max(m.meta[3], 1)));
    if (m.tech == RULE_INTERSECT && priced_meta(m))  // cells held together, rules combined
        d *= 1.0 + 0.1 * (double)std::max(m.meta[0] - 4, 0) + 0.25 * (double)std::max(m.meta[3] - 2, 0);
    if (m.tech == GUESS && priced_meta(m))  // expected refutation work of the wrong candidates
        d = B[GUESS] * size(D) * (1.0 + guess_k * (double)m.meta[0] / 10.0);
    if ((m.tech == TRIAL || m.tech == SHORT_TRIAL) && priced_meta(m))  // depth the refutation needed
        d *= 1.0 + trial_k * (double)std::max(m.meta[3] - 1, 0);
    if ((m.tech == SHORT_TRIAL || m.tech == EITHER_WAY || m.tech == WHAT_IF) && priced_meta(m)) {
        // short case splits are cheap (sudoku.coach puts 1-3 cell forcing chains next to X-Wing):
        // scale by the cells the branches fill, 1.0 at 10 cells
        d *= (1.0 + std::log1p((double)std::max(m.meta[0], 0))) / (1.0 + std::log1p(10.0));
    }
    if (human && m.has_load) {  // load-priced effort beyond a comfortable budget
        double e = 0.0;
        for (int j = 0; j < LOAD_N; ++j) {
            double over = (double)m.load[j] - hbudget[j];
            if (over > 0.0) e += hk[j] * over;
        }
        d *= std::exp(e);
    }
    // grader.scoring: no single move counts as harder than guessing
    const double cap = B[GUESS];
    if (cap != 0.0 && m.tech != GUESS && d > cap)
        d = cap_pow > 0.0 ? cap + py_pow(d - cap, cap_pow)  // power cap: steeper than log (1 = no cap)
            : cap_tau > 0.0 ? cap + cap_tau * std::log1p((d - cap) / cap_tau) : cap;
    return d;
}

// ------------------------------------------------------------ strategies --
namespace {
struct FnStrategy : Strategy {
    const char* nm;
    std::function<void(Solver&, MoveBuf&)> f;
    FnStrategy(const char* n, std::function<void(Solver&, MoveBuf&)> fn) : nm(n), f(std::move(fn)) {}
    const char* name() const override { return nm; }
    void collect(Solver& s, MoveBuf& out) override { f(s, out); }
};
std::shared_ptr<Strategy> S(const char* n, std::function<void(Solver&, MoveBuf&)> f) {
    return std::make_shared<FnStrategy>(n, std::move(f));
}
}  // namespace

// strategy -> the techniques it can emit (only strategies with an unambiguous output are listed): a strategy whose
// techniques are ALL disabled is skipped instead of computed and filtered (band-limited queries, human-mode races)
static bool strategy_off(const char* name, const std::vector<char>& disabled) {
    static const std::unordered_map<std::string, std::vector<int>> TECHS = {
        {"xwing", {XWING}}, {"swordfish", {SWORDFISH}}, {"jellyfish", {JELLYFISH}},
        {"finned2", {FINNED_FISH}}, {"finned3", {FINNED_FISH}}, {"finned4", {FINNED_FISH}},
        {"xywing", {XYWING}}, {"xyzwing", {XYZWING}}, {"nwing", {N_WING}},
        {"coloring", {COLORING}}, {"medusa", {MEDUSA}}, {"multicolour", {MULTI_COLOR}},
        {"alsxz", {ALS_XZ}}, {"alsxy", {ALS_XYWING}}, {"blossom", {DEATH_BLOSSOM}}, {"alsaic", {ALS_AIC}},
        {"suedecoq", {SUE_DE_COQ}}, {"ape", {APE}}, {"chuterp", {CHUTE_RP}},
        {"ur", {UNIQUE_RECT}}, {"xur", {UNIQUE_RECT}}, {"bug", {BUG_PLUS1}}, {"gurth", {GURTH}},
        {"pairs", {NPAIR, HPAIR}}, {"triples", {NTRIPLE, HTRIPLE}}, {"quads", {NQUAD, HQUAD}},
        {"digitcount", {DIGIT_COUNT}}, {"equaldigits", {EQUAL_DIGITS}}, {"colouralgebra", {COLOUR_ALGEBRA}},
        {"ruleintersect", {RULE_INTERSECT}}, {"shorttrial", {SHORT_TRIAL}}};
    auto it = TECHS.find(name);
    if (it == TECHS.end()) return false;
    for (int t : it->second)
        if (t < (int)disabled.size() && !disabled[t]) return false;
    return true;
}

// NOTES_TIERS
std::vector<Tier> default_notes_tiers() {
    return {
        {S("singles", [](Solver& s, MoveBuf& b) { s.notes_singles(b); })},
        {S("cagecombo", [](Solver& s, MoveBuf& b) { s.cage_combo(b); }),
         S("sumbound", [](Solver& s, MoveBuf& b) { s.sum_bound(b); }),
         S("combination", [](Solver& s, MoveBuf& b) { s.nary_combination(b, 0); }),
         S("lineclass", [](Solver& s, MoveBuf& b) { s.line_classes(b); }),
         S("linescan", [](Solver& s, MoveBuf& b) { s.line_scan(b); })},
        {S("locked", [](Solver& s, MoveBuf& b) { s.locked(b); }),
         // set equivalences (law of leftovers, Phistomefel, set theory) compete on price with pointing / claiming
         // (a one-line-vs-one-box LoL is pointing in disguise)
         S("leftovers", [](Solver& s, MoveBuf& b) { s.nary_combination(b, 1); }),
         S("pairarc", [](Solver& s, MoveBuf& b) { s.pairarc(b); }),
         S("domino", [](Solver& s, MoveBuf& b) { s.domino(b); }),
         S("classcount", [](Solver& s, MoveBuf& b) { s.class_count(b); }),
         S("innie", [](Solver& s, MoveBuf& b) { s.innies(b, true); }),
         S("combolock", [](Solver& s, MoveBuf& b) { s.combo_lock(b); }),
         S("inniesum", [](Solver& s, MoveBuf& b) { s.innie_sum(b); })},
        {S("pairs", [](Solver& s, MoveBuf& b) { s.subsets(b, 2); }),
         S("combopos", [](Solver& s, MoveBuf& b) { s.combo_positions(b); }),
         S("linesets", [](Solver& s, MoveBuf& b) { s.line_sets(b); }),
         S("lineclues", [](Solver& s, MoveBuf& b) { s.line_clues(b); }),
         S("ur", [](Solver& s, MoveBuf& b) { s.unique_rect(b); }),
         S("xur", [](Solver& s, MoveBuf& b) { s.extended_ur(b); }),
         S("bug", [](Solver& s, MoveBuf& b) { s.bug_plus1(b); }),
         S("gurth", [](Solver& s, MoveBuf& b) { s.gurth(b); })},
        {S("triples", [](Solver& s, MoveBuf& b) { s.subsets(b, 3); }),
         S("xwing", [](Solver& s, MoveBuf& b) { s.fish(b, 2); }),
         S("xywing", [](Solver& s, MoveBuf& b) { s.xywing(b, false); }),
         S("chuterp", [](Solver& s, MoveBuf& b) { s.chute_remote_pairs(b); }),
         S("coloring", [](Solver& s, MoveBuf& b) { s.coloring(b); }),
         S("medusa", [](Solver& s, MoveBuf& b) { s.medusa(b); }),
         S("multicolour", [](Solver& s, MoveBuf& b) { s.multi_colouring(b); }),
         S("finned2", [](Solver& s, MoveBuf& b) { s.gfish(b, 2, false, true); }),
         S("digitcount", [](Solver& s, MoveBuf& b) { s.digit_count(b); }),
         S("equaldigits", [](Solver& s, MoveBuf& b) { s.equal_digits(b); }),
         S("colouralgebra", [](Solver& s, MoveBuf& b) { s.colour_algebra(b); }),
         S("chains3-5", [](Solver& s, MoveBuf& b) { s.aic(b, 3, 5); })},
        {S("quads", [](Solver& s, MoveBuf& b) { s.subsets(b, 4); }),
         S("clique", [](Solver& s, MoveBuf& b) { s.clique_house(b); }),
         S("swordfish", [](Solver& s, MoveBuf& b) { s.fish(b, 3); }),
         S("xyzwing", [](Solver& s, MoveBuf& b) { s.xywing(b, true); }),
         S("nwing", [](Solver& s, MoveBuf& b) { s.n_wing(b); }),
         S("suedecoq", [](Solver& s, MoveBuf& b) { s.sue_de_coq(b); }),
         S("ape", [](Solver& s, MoveBuf& b) { s.aligned_pair(b); }),
         S("fireworks", [](Solver& s, MoveBuf& b) { s.fireworks(b); }),
         S("finned3", [](Solver& s, MoveBuf& b) { s.gfish(b, 3, false, true); }),
         S("jellyfish", [](Solver& s, MoveBuf& b) { s.gfish(b, 4, true, false); }),
         S("chains7-9", [](Solver& s, MoveBuf& b) { s.aic(b, 7, 9); }),
         S("alsxz", [](Solver& s, MoveBuf& b) { s.als_xz(b); })},
        {S("finned4", [](Solver& s, MoveBuf& b) { s.gfish(b, 4, false, true); }),
         S("chains11+", [](Solver& s, MoveBuf& b) { s.aic(b, 11, 15); }),
         S("alsxy", [](Solver& s, MoveBuf& b) { s.als_xywing(b); }),
         S("blossom", [](Solver& s, MoveBuf& b) { s.death_blossom(b); })},
        {S("alsaic", [](Solver& s, MoveBuf& b) { s.als_aic(b, 13); })},
        {S("ruleintersect", [](Solver& s, MoveBuf& b) { s.rule_intersect(b); })},
        {S("sumalgebra", [](Solver& s, MoveBuf& b) { s.sum_algebra(b); }),
         S("weightedsums", [](Solver& s, MoveBuf& b) { s.weighted_sums(b); })},
        {S("bandlogic", [](Solver& s, MoveBuf& b) { s.band_logic(b); })},
        {S("humancase", [](Solver& s, MoveBuf& b) { s.human_case(b); })},
        {S("shorttrial", [](Solver& s, MoveBuf& b) { s.short_trial(b); }),
         S("nishio", [](Solver& s, MoveBuf& b) { s.nishio(b); }),
         S("eitherway", [](Solver& s, MoveBuf& b) { s.either_way(b, false); }),
         S("whatif", [](Solver& s, MoveBuf& b) { s.what_if(b, false); }),
         S("forcing", [](Solver& s, MoveBuf& b) { s.forcing(b, 0); })},
        {S("pom", [](Solver& s, MoveBuf& b) { s.pattern_overlay(b); })},
        {S("dynforcing", [](Solver& s, MoveBuf& b) { s.forcing(b, 1); })},
        {S("nestedforcing", [](Solver& s, MoveBuf& b) { s.forcing(b, 2); })},
        {S("trial", [](Solver& s, MoveBuf& b) { s.trial(b); })},
    };
}

// ----------------------------------------------------------------- state --
const Puzzle& Solver::pick_puzzle(const Puzzle& pz, const SolveOptions& o) {
    bool implied = true, canon = true;
    for (int t : o.disabled) {
        if (t == IMPLIED) implied = false;
        if (t == CANONICAL) canon = false;
    }
    const Puzzle& base = (canon && pz.canonical) ? *pz.canonical : pz;
    return (implied && base.implied) ? *base.implied : base;
}

Solver::Solver(const Puzzle& pz, const Params& prm, const SolveOptions& o)
    : p(pick_puzzle(pz, o)), P(prm), opt(o) {
    disabled.assign(N_TECH, 0);
    marked.assign(p.N, 0);
    for (int t : opt.disabled)
        if (t >= 0 && t < N_TECH) {
            disabled[t] = 1;
            any_disabled = true;
        }
    ex.assign(p.N, 0);
    ex2.assign(p.N, 0);
    seen.assign(p.N, 0);
    lock_lst.assign(p.N, {});
    lock_mask.assign(p.N, 0);
    cs_cache.assign(p.G, {});
    tiers = default_notes_tiers();
    if (P.sets_first) {  // human route preference: set arithmetic (rule intersections, sum algebra, band logic)
        // before chains / ALS: those strategies move to new tiers right after "bandlogic" (colouring stays)
        static const std::set<std::string> late = {"chains3-5", "chains7-9", "chains11+", "alsxz", "alsxy", "blossom",
                                                   "alsaic"};
        std::vector<Tier> keep;
        std::vector<Tier> moved;
        for (auto& t : tiers) {
            Tier a, b;
            for (auto& st : t) (late.count(st->name()) ? b : a).push_back(st);
            if (!a.empty()) keep.push_back(a);
            if (!b.empty()) moved.push_back(b);
        }
        std::vector<Tier> out;
        for (auto& t : keep) {
            out.push_back(t);
            bool band = false;
            for (auto& st : t) band |= std::string(st->name()) == "bandlogic";
            if (band) out.insert(out.end(), moved.begin(), moved.end()), moved.clear();
        }
        out.insert(out.end(), moved.begin(), moved.end());
        tiers.swap(out);
    }
    canon = !disabled[CANONICAL];
}

int Solver::roll_pick(const MoveBuf& b) {
    const int n = (int)b.moves.size();
    if (n <= 1) return 0;
    if (!rng_state) rng_state = opt.seed * 0x9E3779B97F4A7C15ULL + 0x632BE59BD9B4E019ULL;
    std::vector<double> lg(n);
    double mx = -1e300;
    const double T = std::max(opt.temperature, 1e-6);
    for (int i = 0; i < n; ++i) {
        const Move& m = b.moves[i];
        double u = -m.d;
        if (m.tech < (int)opt.attract.size()) u += opt.attract[m.tech];
        u += opt.eta * std::log(1.0 + m.el_n + (m.pc >= 0));
        const int tgt = m.pc >= 0 ? m.pc : (m.el_n ? (int)(b.elims[m.el_off] / 32) : -1);
        if (opt.focus && tgt >= 0 && roll_last >= 0) {
            const int dr = std::abs(p.coords[tgt].first - p.coords[roll_last].first);
            const int dc = std::abs(p.coords[tgt].second - p.coords[roll_last].second);
            bool near = false, same_box = false;
            for (int gi : p.groups_of[tgt]) {
                if (!p.groups[gi].complete || !tbit(p.gbits(gi), roll_last)) continue;
                near = true;
                if (p.group_cat[gi] == GC_BOX || p.group_cat[gi] == GC_IRREGULAR) same_box = true;
            }
            u += opt.gfocus[0] * std::log(1.0 + std::max(dr, dc)) + opt.gfocus[1] * (m.pv && m.pv == roll_last_digit) +
                 opt.gfocus[2] * same_box + opt.gfocus[3] * near;
        }
        lg[i] = u / T;
        mx = std::max(mx, lg[i]);
    }
    double z = 0;
    for (double& x : lg) z += (x = std::exp(x - mx));
    // xorshift64*
    rng_state ^= rng_state >> 12;
    rng_state ^= rng_state << 25;
    rng_state ^= rng_state >> 27;
    const double r = (double)((rng_state * 0x2545F4914F6CDD1DULL) >> 11) / 9007199254740992.0 * z;
    double acc = 0;
    for (int i = 0; i < n; ++i)
        if ((acc += lg[i]) >= r) return i;
    return n - 1;
}

void Solver::init_state(const std::vector<std::pair<int, int>>& givens) {
    ++version;
    adv_src.assign((size_t)p.N * 32, -1);
    vals.assign(p.N, 0);
    cand = p.domains;
    placed_g.assign(p.G, 0);
    is_given.assign(p.N, 0);
    for (auto& cv : givens) {
        place(cv.first, cv.second);
        is_given[cv.first] = 1;
    }
}

// _place
int Solver::place(int c, int v) {
    vals[c] = (uint8_t)v;
    cand[c] = 0;
    uint32_t b = bit(v);
    int erased = 0;
    for (int gi : p.groups_of[c]) placed_g[gi] |= b;
    for (int q : p.peer_list[c])
        if (cand[q] & b) {
            cand[q] &= ~b;
            ++erased;
        }
    const int D1 = p.D + 1;
    for (int j : p.rel_sorted_j[c]) {
        int q = p.rel[c][j];
        uint32_t nb = p.rel_out[c][(size_t)j * D1 + v];
        if (cand[q] & nb) {
            erased += popc(cand[q] & nb);
            cand[q] &= ~nb;
        }
    }
    return erased;
}

void Solver::compute_empties() {
    empties.clear();
    for (int c = 0; c < p.N; ++c)
        if (!vals[c]) empties.push_back(c);
}

Move& Solver::new_move(MoveBuf& b, int tech, double shape, int extra) {
    b.moves.emplace_back();
    Move& m = b.moves.back();
    m.tech = tech;
    m.shape = shape;
    m.extra = extra;
    m.cov_off = (int)b.covers.size();
    m.el_off = (int)b.elims.size();
    return m;
}
// region record of an innie / outie set: total, outie, house union, cages, cells
static void region_expl(MoveBuf& out, Move& m, const InnieSet& s) {
    // named: "the secret" (one house: its digits sum to D(D+1)/2), rule of 45 (a house union)
    if (!m.code && (m.tech == INNIE_D || m.tech == INNIE_N || m.tech == INNIE_X))
        m.code = 3601 + (s.houses.size() > 1 ? 1 : 0) + (s.outie ? 2 : 0);
    std::vector<int> r{s.total, s.outie ? 1 : 0, (int)s.houses.size()};
    r.insert(r.end(), s.houses.begin(), s.houses.end());
    r.push_back((int)s.cages.size());
    r.insert(r.end(), s.cages.begin(), s.cages.end());
    r.insert(r.end(), s.cells.begin(), s.cells.end());
    add_expl(out, m, EX_REGION, r);
}
static inline void set_meta(Move& m, int a, int b, int c, int d, int e, int f, int g, int h, double sp) {
    m.has_meta = true;
    m.meta[0] = a; m.meta[1] = b; m.meta[2] = c; m.meta[3] = d;
    m.meta[4] = e; m.meta[5] = f; m.meta[6] = g; m.meta[7] = h;
    m.spread = sp;
}
static inline void add_elim(MoveBuf& b, Move& m, int c, int v) {
    b.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
    ++m.el_n;
}

// -------------------------------------------------------- killer cages --
// _combo_allowed (+ _assign as a subset-DP: union over all valid assignments)
void Solver::combo_allowed(const std::vector<int>& cells, int total, bool distinct, const uint32_t* masks,
                           uint32_t forbid, uint32_t* allowed) {
    const int k = (int)cells.size();
    const int D = p.D;
    uint32_t mk[32];
    for (int i = 0; i < k; ++i) {
        mk[i] = masks ? masks[i] : (p.full & ~forbid);
        allowed[i] = 0;
    }
    if (k == 0) return;
    if (distinct) {
        uint32_t pool = p.full & ~forbid;
        uint32_t need_all = 0;
        for (int i = 0; i < k; ++i) need_all = i ? (need_all & mk[i]) : mk[i];
        std::vector<char> F, Gb;
        int cd[32];
        std::function<void(int, int, int, uint32_t, int)> rec = [&](int d0, int r, int s, uint32_t m, int depth) {
            if (r == 0) {
                if (s != 0) return;
                // assignment union for combo m
                if ((need_all & m) == m) {
                    for (int i = 0; i < k; ++i) allowed[i] |= m;
                    return;
                }
                const int n = 1 << k, ALL = n - 1;
                F.assign(n, 0);
                Gb.assign(n, 0);
                F[0] = Gb[0] = 1;
                for (int S = 1; S < n; ++S) {
                    int pc = __builtin_popcount(S);
                    uint32_t mf = mk[pc - 1], mb = mk[k - pc];
                    for (int t = 0; t < k; ++t) {
                        if (!(S >> t & 1)) continue;
                        uint32_t bt = bit(cd[t]);
                        if (!F[S] && (mf & bt) && F[S ^ (1 << t)]) F[S] = 1;
                        if (!Gb[S] && (mb & bt) && Gb[S ^ (1 << t)]) Gb[S] = 1;
                    }
                }
                for (int S2 = 0; S2 < n; ++S2) {
                    if (!F[S2]) continue;
                    int j = __builtin_popcount(S2);
                    if (j == k) continue;
                    for (int t = 0; t < k; ++t) {
                        if (S2 >> t & 1) continue;
                        uint32_t bt = bit(cd[t]);
                        if ((mk[j] & bt) && Gb[ALL ^ S2 ^ (1 << t)]) allowed[j] |= bt;
                    }
                }
                return;
            }
            for (int d = d0; d <= D; ++d) {
                if (d * r > s) break;
                if (!(pool & bit(d))) continue;
                cd[depth] = d;
                rec(d + 1, r - 1, s - d, m | bit(d), depth + 1);
            }
        };
        if (k <= 20) rec(1, k, total, 0, 0);
    } else {
        if (total < 0) return;
        std::vector<std::vector<char>> reach(k + 1, std::vector<char>(total + 1, 0));
        reach[0][0] = 1;
        for (int i = 0; i < k; ++i)
            for (int s = 0; s <= total; ++s) {
                if (!reach[i][s]) continue;
                for (uint32_t m = mk[i]; m; m &= m - 1) {
                    int d = lowdigit(m);
                    if (s + d <= total) reach[i + 1][s + d] = 1;
                }
            }
        std::vector<char> back(total + 1, 0), ok;
        back[total] = 1;
        for (int i = k - 1; i >= 0; --i) {
            ok.assign(total + 1, 0);
            for (uint32_t m = mk[i]; m; m &= m - 1) {
                int d = lowdigit(m);
                for (int s = 0; s <= total; ++s) {
                    if (!back[s]) continue;
                    int t = s - d;
                    if (t >= 0 && reach[i][t]) {
                        allowed[i] |= bit(d);
                        ok[t] = 1;
                    }
                }
            }
            back.swap(ok);
        }
    }
}

// _cagesum_direct
uint32_t Solver::cagesum_direct(int gi) {
    auto& cache = cs_cache[gi];
    uint32_t key = placed_g[gi];
    auto it = cache.find(key);
    if (it != cache.end()) return it->second;
    const Group& g = p.groups[gi];
    std::vector<int> emp;
    int rem = g.total;
    for (int c : g.cells) {
        if (!vals[c]) emp.push_back(c);
        rem -= vals[c];
    }
    uint32_t allowed = 0;
    if (!emp.empty()) {
        uint32_t al[32];
        combo_allowed(emp, rem, true, nullptr, placed_g[gi], al);
        for (size_t i = 0; i < emp.size(); ++i) allowed |= al[i];
    }
    cache[key] = allowed;
    return allowed;
}

// ---------------------------------------------- direct (no-notes) view --
// _direct_sources
void Solver::direct_sources(int c, std::vector<Src>& out) {
    out.clear();
    for (int gi : p.groups_of[c]) {
        uint32_t m = placed_g[gi];
        if (m) out.push_back({p.groups[gi].complete ? K_HOUSE : K_CAGE, p.groups[gi].shape, m});
    }
    if (!p.neq[c].empty()) {
        uint32_t m = 0;
        for (int q : p.neq[c])
            if (vals[q]) m |= bit(vals[q]);
        if (m) out.push_back({K_NEQ, 1.0, m});
    }
    if (!p.rel[c].empty()) {
        uint32_t m = 0;
        const int D1 = p.D + 1;
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int v = vals[p.rel[c][j]];
            if (v) m |= p.rel_in[c][j * D1 + v];
        }
        if (m) out.push_back({K_NONCONSEC, 1.0, m});
    }
    uint32_t dom_ex = p.full & ~p.domains[c];
    if (dom_ex) out.push_back({K_DOMAIN, 1.0, dom_ex});
    if (p.has_cages) {
        for (int gi : p.groups_of[c]) {
            const Group& g = p.groups[gi];
            if (g.has_total) {
                uint32_t m = p.full & ~cagesum_direct(gi) & ~placed_g[gi];
                if (m) out.push_back({K_CAGESUM, g.shape, m});
            }
        }
    }
}

// _direct_excl (for all current empties, into ex[])
void Solver::direct_excl() {
    const int D1 = p.D + 1;
    for (int c : empties) {
        uint32_t m = p.full & ~p.domains[c];
        for (int gi : p.groups_of[c]) m |= placed_g[gi];
        for (int q : p.neq[c])
            if (vals[q]) m |= bit(vals[q]);
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            int v = vals[p.rel[c][j]];
            if (v) m |= p.rel_in[c][j * D1 + v];
        }
        if (p.has_cages)
            for (int gi : p.groups_of[c])
                if (p.groups[gi].has_total) m |= p.full & ~cagesum_direct(gi);
        ex[c] = m;
    }
}

// _naked_cover
bool Solver::naked_cover(std::vector<Src>& srcs, double& base, std::vector<Cover>& cov, const CoverScore* score) {
    const int target = popc(p.full) - 1;
    const int n = (int)srcs.size();
    uint32_t all = 0;
    for (auto& s : srcs) all |= s.mask;
    if (popc(all) < target) return false;
    if (canon && score) {
        // every minimal combination, ordered (coverage, kind, shape); keep the cheapest
        double best_d = 1e300;
        std::vector<Cover> bc, tc;
        double bbase = 0;
        bool any = false;
        std::vector<Src> order;
        for (int k = 1; k <= n && !any; ++k) {
            for_combos(n, k, [&](const int* idx) {
                uint32_t m = 0;
                for (int i = 0; i < k; ++i) m |= srcs[idx[i]].mask;
                if (popc(m) < target) return false;
                order.clear();
                for (int i = 0; i < k; ++i) order.push_back(srcs[idx[i]]);
                // the cheapest order of this combination (u depends on the order)
                std::vector<int> perm(k);
                for (int i = 0; i < k; ++i) perm[i] = i;
                do {
                    tc.clear();
                    uint32_t mm = order[perm[0]].mask;
                    for (int i = 1; i < k; ++i) {
                        tc.push_back({order[perm[i]].kind, order[perm[i]].shape, p.D - popc(mm)});
                        mm |= order[perm[i]].mask;
                    }
                    double d = (*score)(order[perm[0]].shape, tc);
                    if (!any || d < best_d - 1e-12) {
                        best_d = d;
                        bc = tc;
                        bbase = order[perm[0]].shape;
                    }
                    any = true;
                } while (k > 1 && k <= 6 && std::next_permutation(perm.begin(), perm.end()));
                return false;
            });
        }
        if (!any) return false;
        cov = bc;
        base = bbase;
        return true;
    }
    std::vector<int> found;
    for (int k = 1; k <= n && found.empty(); ++k) {
        for_combos(n, k, [&](const int* idx) {
            uint32_t m = 0;
            for (int i = 0; i < k; ++i) m |= srcs[idx[i]].mask;
            if (popc(m) >= target) {
                found.assign(idx, idx + k);
                return true;
            }
            return false;
        });
    }
    if (found.empty()) return false;
    std::vector<Src> order;
    for (int i : found) order.push_back(srcs[i]);
    std::stable_sort(order.begin(), order.end(), [](const Src& a, const Src& b) { return popc(a.mask) > popc(b.mask); });
    cov.clear();
    uint32_t m = order[0].mask;
    for (size_t i = 1; i < order.size(); ++i) {
        cov.push_back({order[i].kind, order[i].shape, p.D - popc(m)});
        m |= order[i].mask;
    }
    base = order[0].shape;
    return true;
}

// _hidden_sources: insertion-ordered dict ident -> (kind, shape, cells & items)
void Solver::hidden_sources(const std::vector<int>& cells, int v, int house, bool use_locks, std::vector<HSrc>& out) {
    out.clear();
    const uint32_t b = bit(v);
    const int n = (int)cells.size();
    auto local = [&](const uint64_t* bits) {
        uint32_t m = 0;
        for (int i = 0; i < n; ++i)
            if (tbit(bits, cells[i])) m |= 1u << i;
        return m;
    };
    auto find = [&](uint64_t key) -> int {
        for (size_t i = 0; i < out.size(); ++i)
            if (out[i].key == key) return (int)i;
        return -1;
    };
    // d[key] = value: keeps position if present
    auto put = [&](uint64_t key, int kind, double shape, const uint64_t* bits) {
        if (find(key) < 0) out.push_back({key, kind, shape, local(bits)});
    };
    const int D1 = p.D + 1;
    for (int yi = 0; yi < n; ++yi) {
        int y = cells[yi];
        for (int gi : p.groups_of[y]) {
            if (gi == house || !(placed_g[gi] & b)) continue;
            put(mkkey(0, gi, 0, 0), p.groups[gi].complete ? K_HOUSE : K_CAGE, p.groups[gi].shape, p.gbits(gi));
        }
        for (int q : p.neq[y])
            if (vals[q] == v) put(mkkey(1, q, 0, 0), K_NEQ, 1.0, p.neqb(q));
        for (size_t j = 0; j < p.rel[y].size(); ++j) {
            int q = p.rel[y][j];
            if (vals[q] && (p.rel_in[y][j * D1 + vals[q]] & b)) put(mkkey(2, q, 0, 0), K_NONCONSEC, 1.0, p.relb(q));
        }
        if (!(p.domains[y] & b)) {
            if (find(mkkey(3, y, 0, 0)) < 0) out.push_back({mkkey(3, y, 0, 0), K_DOMAIN, 1.0, 1u << yi});
        }
        if (p.has_cages) {
            for (int gi : p.groups_of[y]) {
                const Group& gg = p.groups[gi];
                if (gg.has_total && !(cagesum_direct(gi) & b))
                    put(mkkey(4, gi, 0, 0), K_CAGESUM, gg.shape, p.gbits(gi));
            }
        }
        if (use_locks && !lock_lst[y].empty()) {
            for (const LockEntry& lk : lock_lst[y])
                if (lk.mask & b) put(lk.ident, K_LOCK, lk.shape, &lock_tgt[(size_t)lk.tgt * p.W]);
        }
    }
}

// _hidden_cover over local item masks
bool Solver::hidden_cover(int n_items, const std::vector<HSrc>& srcs_all, std::vector<Cover>& cov,
                          const CoverScore* score) {
    cov.clear();
    if (n_items == 0) return true;
    const uint32_t ALL = n_items >= 32 ? 0xffffffffu : ((1u << n_items) - 1);
    std::vector<const HSrc*>& srcs = hc_srcs;
    srcs.clear();
    for (auto& s : srcs_all)
        if (s.local & ALL) srcs.push_back(&s);
    std::vector<const HSrc*>& chosen = hc_chosen;
    chosen.clear();
    const int n = (int)srcs.size();
    auto canon_less = [&](const HSrc* a, const HSrc* b) {
        int ca = popc(a->local & ALL), cb = popc(b->local & ALL);
        if (ca != cb) return ca > cb;
        if (a->kind != b->kind) return a->kind < b->kind;
        return a->shape < b->shape;
    };
    if (canon && score) {
        // all minimal covers (bounded search), ordered canonically; keep the cheapest
        double best_d = 1e300;
        std::vector<Cover> bc, tc;
        std::vector<const HSrc*> pick;
        bool any = false;
        pm_long budget = 300000;
        for (int k = 1; k <= n && !any && budget > 0; ++k) {
            for_combos(n, k, [&](const int* idx) {
                if (--budget < 0) return true;
                uint32_t u = 0;
                for (int i = 0; i < k; ++i) u |= srcs[idx[i]]->local;
                if ((u & ALL) != ALL) return false;
                pick.assign(k, nullptr);
                for (int i = 0; i < k; ++i) pick[i] = srcs[idx[i]];
                std::stable_sort(pick.begin(), pick.end(), canon_less);
                // within a combination only the additive cover term depends on the
                // order: pick the order by that, then score the combination once
                std::vector<int> perm(k), bestp;
                for (int i = 0; i < k; ++i) perm[i] = i;
                double bcost = 1e300;
                do {
                    double cost = 0;
                    uint32_t left = ALL;
                    for (int i = 0; i < k; ++i) {
                        const HSrc* sp = pick[perm[i]];
                        cost += P.K[sp->kind] * py_pow(sp->shape, P.gamma) * popc(left);
                        left &= ~sp->local;
                    }
                    if (cost < bcost - 1e-12) {
                        bcost = cost;
                        bestp = perm;
                    }
                } while (k > 1 && k <= 6 && std::next_permutation(perm.begin(), perm.end()));
                tc.clear();
                uint32_t left = ALL;
                for (int i = 0; i < k; ++i) {
                    tc.push_back({pick[bestp[i]]->kind, pick[bestp[i]]->shape, popc(left)});
                    left &= ~pick[bestp[i]]->local;
                }
                double d = (*score)(0.0, tc);
                if (!any || d < best_d - 1e-12) {
                    best_d = d;
                    bc = tc;
                }
                any = true;
                return false;
            });
        }
        if (any) {
            cov = bc;
            return true;
        }
        // fall through: greedy with invariant tie-breaks (coverage, kind, shape)
        if (srcs.empty()) return false;
        uint32_t left = ALL;
        while (left) {
            const HSrc* best = nullptr;
            int bcnt = 0;
            for (const HSrc* sp : srcs) {
                int c = popc(sp->local & left);
                if (c > bcnt || (c == bcnt && c > 0 && best &&
                                 (sp->kind < best->kind || (sp->kind == best->kind && sp->shape < best->shape)))) {
                    bcnt = c;
                    best = sp;
                }
            }
            if (!best) return false;
            chosen.push_back(best);
            left &= ~best->local;
        }
        std::stable_sort(chosen.begin(), chosen.end(), canon_less);
        uint32_t l2 = ALL;
        for (const HSrc* sp : chosen) {
            cov.push_back({sp->kind, sp->shape, popc(l2)});
            l2 &= ~sp->local;
        }
        return true;
    }
    if (n <= 12) {
        for (int k = 1; k <= n && chosen.empty(); ++k) {
            for_combos(n, k, [&](const int* idx) {
                uint32_t u = 0;
                for (int i = 0; i < k; ++i) u |= srcs[idx[i]]->local;
                if ((u & ALL) == ALL) {
                    for (int i = 0; i < k; ++i) chosen.push_back(srcs[idx[i]]);
                    return true;
                }
                return false;
            });
        }
    }
    if (chosen.empty()) {  // greedy
        if (srcs.empty()) return false;
        uint32_t left = ALL;
        while (left) {
            const HSrc* best = srcs[0];
            int bc = popc(best->local & left);
            for (size_t i = 1; i < srcs.size(); ++i) {
                int c = popc(srcs[i]->local & left);
                if (c > bc) {
                    bc = c;
                    best = srcs[i];
                }
            }
            if (!(best->local & left)) return false;
            chosen.push_back(best);
            left &= ~best->local;
        }
    }
    std::stable_sort(chosen.begin(), chosen.end(),
                     [&](const HSrc* a, const HSrc* b) { return popc(a->local & ALL) > popc(b->local & ALL); });
    uint32_t left = ALL;
    for (const HSrc* s : chosen) {
        cov.push_back({s->kind, s->shape, popc(left)});
        left &= ~s->local;
    }
    return true;
}

// common = set(groups_of[poss[0]]); common &= set(groups_of[c]) ...;
// common.discard(x)  -> iteration order as CPython
void Solver::common_groups(const std::vector<int>& poss, int discard, std::vector<int>& out) {
    out.clear();
    for (int gi : p.groups_of[poss[0]]) {
        if (gi == discard) continue;
        bool all = true;
        for (size_t i = 1; i < poss.size() && all; ++i) all = tbit(p.gbits(gi), poss[i]);
        if (all) out.push_back(gi);
    }
    if (out.size() <= 1) return;
    PySet s;
    for (int gi : p.groups_of[poss[0]]) s.add(gi);
    for (size_t i = 1; i < poss.size(); ++i) {
        PySet o;
        for (int gi : p.groups_of[poss[i]]) o.add(gi);
        s = PySet::intersection(s, o);
    }
    s.discard(discard);
    out.clear();
    s.for_each([&](int64_t k) { out.push_back((int)k); });
}

// _direct_moves
void Solver::direct_moves(MoveBuf& out, bool use_locks, int mental) {
    const int D = p.D;
    if (mental) compute_mental(mental);
    compute_empties();
    direct_excl();
    // exclusions available one level down (a mental single must need its level)
    std::vector<uint32_t> lower(p.N, 0);
    for (int c : empties) {
        uint32_t extra = 0;
        if (mental >= 2) extra |= mex_rel[c];
        if (mental >= 3) extra |= mex_ment[c];
        ex2[c] = ex[c] | (use_locks ? lock_mask[c] : 0u) | extra;
        lower[c] = ex[c] | (mental == 3 ? mex_rel[c] : 0u);
    }
    const int mtech = mental == 2 ? LINE_D : MENTAL_D;
    // reason summary of the mental exclusions a move relies on
    auto mental_info = [&](Move& m, const std::vector<std::pair<int, uint32_t>>& used) {
        pm_long tmask = 0, depth = 0, lk = -1, llen = 0, ldist = 0, linf = 0, size = 0, ninf = 0, trans = 0;
        pm_long tlive = 0;
        int tnamed = -1;
        for (auto& cu : used) {
            for (uint32_t mm = cu.second; mm; mm &= mm - 1) {
                size_t i = (size_t)cu.first * 32 + lowdigit(mm);
                int t = rs_type[i];
                if (!t) continue;
                ++ninf;
                tmask |= pm_long(1) << (t - 1);
                depth = std::max<pm_long>(depth, rs_depth[i]);
                size = std::max<pm_long>(size, rs_size[i]);
                if (t == 2) trans = 1;
                if (t == 3 && rs_line[i] >= 0) {
                    const size_t li = (size_t)rs_line[i];
                    const NConstraint& k = li < p.nary.size() ? p.nary[li] : p.cage_nary[li - p.nary.size()];
                    if (k.type == NT_TABLE) {
                        tlive = std::max(tlive, table_live(k));
                        if (k.named && k.index >= 0 && k.index < 1000) tnamed = k.index;
                    }
                    int pos = -1, best = 1 << 20, placed = 0;
                    for (int x = 0; x < k.nv(); ++x)
                        if (k.vars[x] == cu.first) pos = x;
                    for (int x = 0; x < k.nv(); ++x)
                        if (vals[k.vars[x]]) {
                            ++placed;
                            best = std::min(best, std::abs(x - pos));
                        }
                    pm_long dist = placed ? best : 0;
                    if (lk < 0 || dist > ldist) {
                        // non-line rules: 100 + constraint type (cage = 100 + NT_SUM, arrow = 101, ...)
                        lk = k.line_kind >= 0 ? k.line_kind : 100 + k.type;
                        llen = k.nv();
                        ldist = dist;
                        linf = placed;
                    }
                    if (dist != 1) trans = 1;
                }
            }
        }
        pm_long xm[XM_N] = {tmask, depth, lk, llen, ldist, linf, trans, size, ninf, 0};
        std::copy(xm, xm + XM_N, m.xm);
        if (mental == 3)
            m.code = 4400 + (size ? (int)size : 8);  // 8: relation inference enabled by a mental subset
        else if (lk == 100 + NT_TABLE && tnamed >= 0)
            m.code = 6000 + tnamed;  // a named table rule ("diamond rule in the head")
        else if (lk >= 100)
            m.code = 4500 + (int)(lk - 100);  // arrow / cage / sum / between ... arithmetic in the head
        else if (lk >= 0)
            m.code = 4000 + 10 * (int)lk + (linf == 0 ? 1 : ldist <= 1 ? 3 : 4);
        else
            m.code = (tmask & 2) ? 4300 : 4200;
        m.meta[3] = (int)depth;  // links = inference depth
        m.meta[6] = 1;           // relation
        m.tab_live = tlive;
    };
    std::fill(seen.begin(), seen.end(), 0u);
    std::vector<int> emp;
    if (!use_locks && !mental) {
        for (int hi : p.houses) {
            const Group& g = p.groups[hi];
            int cnt = 0, c = -1;
            for (int x : g.cells)
                if (!vals[x]) {
                    ++cnt;
                    c = x;
                }
            if (cnt != 1) continue;
            uint32_t mm = p.full & ~placed_g[hi];
            if (!mm) continue;
            int v = lowdigit(mm);
            if (ex[c] & bit(v)) continue;  // the missing digit is not a candidate: contradiction, no move
            if (!canon && (seen[c] & bit(v))) continue;
            seen[c] |= bit(v);
            Move& m = new_move(out, FULL_HOUSE, g.shape, 0);
            m.pc = c;
            m.pv = v;
            m.nk = NM_GROUP;
            m.na = hi;
            set_meta(m, (int)g.cells.size(), 1, 1, 0, 0, 0, 0, 0, g.shape);
        }
    }
    std::vector<Src> srcs;
    std::vector<Cover> cov;
    for (int c : empties) {
        uint32_t rem = p.full & ~ex2[c];
        if (popc(rem) != 1) continue;
        if (use_locks && popc(p.full & ~ex[c]) == 1) continue;
        if (mental && popc(p.full & ~lower[c]) == 1) continue;
        int v = lowdigit(rem);
        if (!canon && (seen[c] & bit(v))) continue;
        direct_sources(c, srcs);
        if (use_locks)
            for (const LockEntry& lk : lock_lst[c]) srcs.push_back({K_LOCK, lk.shape, lk.mask});
        if (mental >= 2 && mex_rel[c]) srcs.push_back({K_LINE, 1.0, mex_rel[c]});
        if (mental >= 3 && mex_ment[c]) srcs.push_back({K_MENTAL, 1.0, mex_ment[c]});
        double base;
        const CoverScore nscore = [&](double b0, const std::vector<Cover>& cv) {
            Move t;
            t.tech = mental ? mtech : use_locks ? NAKED_DL : NAKED_D;
            t.shape = b0;
            t.cov_n = (int)cv.size();
            bool ks = false, kr = false;
            for (auto& x : cv) {
                ks |= x.kind == K_CAGESUM;
                kr |= x.kind == K_NEQ || x.kind == K_NONCONSEC;
            }
            set_meta(t, 1, (int)cv.size() + 1, 1, use_locks ? 1 : 0, 0, ks, kr, 0, b0);
            return P.difficulty(t, cv.data(), p.D);
        };
        if (!naked_cover(srcs, base, cov, &nscore)) continue;
        seen[c] |= bit(v);
        bool ks = false, kr = false;
        for (auto& cv : cov) {
            if (cv.kind == K_CAGESUM) ks = true;
            if (cv.kind == K_NEQ || cv.kind == K_NONCONSEC) kr = true;
        }
        Move& m = new_move(out, mental ? mtech : use_locks ? NAKED_DL : NAKED_D, base, 0);
        for (auto& cv : cov) out.covers.push_back(cv);
        m.cov_n = (int)cov.size();
        m.pc = c;
        m.pv = v;
        set_meta(m, 1, (int)cov.size() + 1, 1, use_locks ? 1 : 0, 0, ks, kr, 0, base);
        if (mental) {
            bool usesm = false;
            for (auto& cv : cov) usesm |= cv.kind == K_MENTAL || cv.kind == K_LINE;
            if (!usesm && !(base == 1.0 && (popc(mex_rel[c]) || popc(mex_ment[c])))) {
                // the cover found does not mention the mental source: still a mental single
            }
            mental_info(m, {{c, mex_rel[c] | (mental >= 3 ? mex_ment[c] : 0u)}});
        }
    }
    std::vector<int> others;
    std::vector<HSrc> hs;
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        emp.clear();
        for (int x : g.cells)
            if (!vals[x]) emp.push_back(x);
        if (emp.size() < 2) continue;
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            int cnt = 0, c = -1;
            for (int x : emp)
                if (!(ex2[x] & b)) {
                    ++cnt;
                    c = x;
                }
            if (cnt != 1) continue;
            if (use_locks) {
                int c2 = 0;
                for (int x : emp)
                    if (!(ex[x] & b)) ++c2;
                if (c2 == 1) continue;
            }
            if (mental) {
                int c2 = 0;
                for (int x : emp)
                    if (!(lower[x] & b)) ++c2;
                if (c2 == 1) continue;
            }
            if (!canon && (seen[c] & b)) continue;
            others.clear();
            for (int x : emp)
                if (x != c) others.push_back(x);
            hidden_sources(others, v, hi, use_locks, hs);
            if (mental)
                for (size_t yi = 0; yi < others.size(); ++yi) {
                    int y = others[yi];
                    if (mex_rel[y] & b) hs.push_back({mkkey(7, y, 0, 0), K_LINE, 1.0, 1u << yi});
                    if (mental >= 3 && (mex_ment[y] & b)) hs.push_back({mkkey(8, y, 0, 0), K_MENTAL, 1.0, 1u << yi});
                }
            const CoverScore hscore = [&](double, const std::vector<Cover>& cv) {
                Move t;
                t.tech = mental ? mtech : use_locks ? HIDDEN_DL : HIDDEN_D;
                t.shape = g.shape;
                t.cov_n = (int)cv.size();
                bool ks = false, kr = false;
                for (auto& x : cv) {
                    ks |= x.kind == K_CAGESUM;
                    kr |= x.kind == K_NEQ || x.kind == K_NONCONSEC;
                }
                set_meta(t, 1 + (int)others.size(), 1 + (int)cv.size(), 1, use_locks ? 1 : 0, 1, ks, kr, 0, g.shape);
                return P.difficulty(t, cv.data(), p.D);
            };
            if (!hidden_cover((int)others.size(), hs, cov, &hscore)) continue;
            seen[c] |= b;
            bool ks = false, kr = false;
            for (auto& cv : cov) {
                if (cv.kind == K_CAGESUM) ks = true;
                if (cv.kind == K_NEQ || cv.kind == K_NONCONSEC) kr = true;
            }
            Move& m = new_move(out, mental ? mtech : use_locks ? HIDDEN_DL : HIDDEN_D, g.shape, (int)others.size());
            for (auto& cv : cov) out.covers.push_back(cv);
            m.cov_n = (int)cov.size();
            m.pc = c;
            m.pv = v;
            m.nk = NM_GROUP;
            m.na = hi;
            set_meta(m, 1 + (int)others.size(), 1 + (int)cov.size(), 1, use_locks ? 1 : 0, 1, ks, kr, 0, g.shape);
            if (mental) {
                std::vector<std::pair<int, uint32_t>> used;
                for (int y : others) {
                    uint32_t mm = (mex_rel[y] | (mental >= 3 ? mex_ment[y] : 0u)) & b;
                    if (mm) used.push_back({y, mm});
                }
                mental_info(m, used);
                m.xm[9] = 1;  // hidden
            }
        }
    }
    (void)D;
}

// _direct_locks
bool Solver::direct_locks() {
    for (int c : lock_cells) {
        lock_lst[c].clear();
        lock_mask[c] = 0;
    }
    lock_cells.clear();
    lock_tgt.clear();
    compute_empties();
    direct_excl();
    const int W = p.W, D1 = p.D + 1;
    auto add_lock = [&](int c, const LockEntry& e) {
        if (lock_lst[c].empty()) lock_cells.push_back(c);
        lock_lst[c].push_back(e);
        lock_mask[c] |= e.mask;
    };
    std::vector<int> emp, poss, common, targets;
    std::vector<std::pair<int, uint32_t>> rms;
    std::vector<uint64_t> cr(W);
    for (int bi : p.houses) {
        const Group& B = p.groups[bi];
        emp.clear();
        for (int x : B.cells)
            if (!vals[x]) emp.push_back(x);
        if (emp.size() < 3) continue;
        for (uint32_t mm = p.full & ~placed_g[bi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            poss.clear();
            for (int c : emp)
                if (!(ex[c] & b)) poss.push_back(c);
            if (poss.size() < 2) continue;
            common_groups(poss, bi, common);
            for (int ai : common) {
                const Group& A = p.groups[ai];
                targets.clear();
                for (int c : A.cells)
                    if (!vals[c] && !tbit(p.gbits(bi), c) && !(ex[c] & b)) targets.push_back(c);
                if (targets.empty()) continue;
                int tgt = (int)(lock_tgt.size() / W);
                lock_tgt.resize(lock_tgt.size() + W, 0);
                for (int c : targets) sbit(&lock_tgt[(size_t)tgt * W], c);
                uint64_t ident = mkkey(5, bi, ai, v);
                for (int c : targets) add_lock(c, {ident, B.shape, b, tgt});
            }
            for (int gen = 1; gen >= 0; --gen) {
                const std::vector<int>& L0 = gen ? p.rel[poss[0]] : p.neq[poss[0]];
                if (L0.empty()) continue;
                const uint64_t* b0 = gen ? p.relb(poss[0]) : p.neqb(poss[0]);
                for (int w = 0; w < W; ++w) cr[w] = b0[w];
                for (size_t i = 1; i < poss.size(); ++i) {
                    const uint64_t* bc = gen ? p.relb(poss[i]) : p.neqb(poss[i]);
                    for (int w = 0; w < W; ++w) cr[w] &= bc[w];
                }
                rms.clear();
                for (int x = 0; x < p.N; ++x) {
                    if (!tbit(cr.data(), x)) continue;
                    if (vals[x] || std::find(poss.begin(), poss.end(), x) != poss.end()) continue;
                    uint32_t rm = p.full;
                    if (gen) {
                        for (int c : poss) rm &= p.rel_ex(c, x)[v];
                    } else {
                        rm = b;
                    }
                    if (rm & ~ex[x]) rms.push_back({x, rm});
                }
                if (rms.empty()) continue;
                int tgt = (int)(lock_tgt.size() / W);
                lock_tgt.resize(lock_tgt.size() + W, 0);
                for (auto& xr : rms) sbit(&lock_tgt[(size_t)tgt * W], xr.first);
                uint64_t ident = mkkey(6, bi, v, gen);
                for (auto& xr : rms) add_lock(xr.first, {ident, B.shape, xr.second, tgt});
            }
        }
    }
    (void)D1;
    return !lock_cells.empty();
}

// ---------------------------------------------------------- notes view --
void Solver::notes_singles(MoveBuf& out) {
    std::fill(seen.begin(), seen.end(), 0u);
    for (int c = 0; c < p.N; ++c) {
        if (!vals[c] && popc(cand[c]) == 1) {
            int v = lowdigit(cand[c]);
            seen[c] |= bit(v);
            Move& m = new_move(out, NAKED_N, 1.0, 0);
            m.pc = c;
            m.pv = v;
            set_meta(m, 1, 1, 1, 0, 0, 0, 0, 1, 1.0);
        }
    }
    std::vector<int> emp;
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        emp.clear();
        for (int x : g.cells)
            if (!vals[x]) emp.push_back(x);
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            int cnt = 0, c = -1;
            for (int x : emp)
                if (cand[x] & b) {
                    ++cnt;
                    c = x;
                }
            if (cnt == 1 && (canon || !(seen[c] & b))) {
                seen[c] |= b;
                Move& m = new_move(out, HIDDEN_N, g.shape, (int)emp.size());
                m.pc = c;
                m.pv = v;
                m.nk = NM_GROUP;
                m.na = hi;
                set_meta(m, (int)emp.size(), 1, 1, 0, 1, 0, 0, 1, g.shape);
            }
        }
    }
}

void Solver::locked(MoveBuf& out) {
    std::vector<int> poss, common;
    for (int bi : p.houses) {
        const Group& B = p.groups[bi];
        for (uint32_t mm = p.full & ~placed_g[bi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            poss.clear();
            for (int c : B.cells)
                if (!vals[c] && (cand[c] & b)) poss.push_back(c);
            if (poss.size() < 2) continue;
            common_groups(poss, bi, common);
            for (int ai : common) {
                const Group& A = p.groups[ai];
                double shp = py_pow(B.shape * A.shape, 0.5);
                size_t mark = out.elims.size();
                int n = 0;
                for (int c : A.cells)
                    if (!tbit(p.gbits(bi), c) && (cand[c] & b)) {
                        out.elims.push_back((uint32_t)c * 32u + v);
                        ++n;
                    }
                if (!n) continue;
                out.elims.resize(mark);
                Move& m = new_move(out, LOCKED, shp, (int)poss.size());
                for (int c : A.cells)
                    if (!tbit(p.gbits(bi), c) && (cand[c] & b)) add_elim(out, m, c, v);
                m.nk = NM_LOCK;
                m.na = bi;
                m.nb = ai;
                set_pattern(out, m, poss);
                set_meta(m, (int)poss.size(), 2, 1, 0, 1, A.has_total ? 1 : 0, 0, 1, shp);
            }
        }
    }
}

void Solver::subsets(MoveBuf& out, int k) {
    static const int NT[5] = {0, 0, NPAIR, NTRIPLE, NQUAD}, HT[5] = {0, 0, HPAIR, HTRIPLE, HQUAD};
    const int nt = NT[k], ht = HT[k];
    std::vector<int> emp, small, cands;
    uint32_t pos[33];
    for (int hi : p.houses) {
        const Group& g = p.groups[hi];
        emp.clear();
        for (int x : g.cells)
            if (!vals[x]) emp.push_back(x);
        if ((int)emp.size() <= k) continue;
        small.clear();
        for (int c : emp) {
            int pc = popc(cand[c]);
            if (pc >= 2 && pc <= k) small.push_back(c);
        }
        for_combos((int)small.size(), k, [&](const int* idx) {
            uint32_t u = 0;
            for (int i = 0; i < k; ++i) u |= cand[small[idx[i]]];
            if (popc(u) != k) return false;
            int n = 0;
            for (int c : emp) {
                bool in = false;
                for (int i = 0; i < k; ++i) in |= small[idx[i]] == c;
                if (!in) n += popc(cand[c] & u);
            }
            if (!n) return false;
            Move& m = new_move(out, nt, g.shape, (int)emp.size());
            for (int c : emp) {
                bool in = false;
                for (int i = 0; i < k; ++i) in |= small[idx[i]] == c;
                if (in) continue;
                for (uint32_t dm = cand[c] & u; dm; dm &= dm - 1) add_elim(out, m, c, lowdigit(dm));
            }
            m.nk = NM_GROUP;
            m.na = hi;
            {
                std::vector<int> pc;
                for (int i = 0; i < k; ++i) pc.push_back(small[idx[i]]);
                set_pattern(out, m, pc);
            }
            set_meta(m, k, 1, k, 0, 0, 0, 0, 1, g.shape);
            return false;
        });
        cands.clear();
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            int d = lowdigit(mm);
            uint32_t pm = 0;
            for (size_t i = 0; i < emp.size(); ++i)
                if (cand[emp[i]] & bit(d)) pm |= 1u << i;
            pos[d] = pm;
            int n = popc(pm);
            if (n >= 2 && n <= k) cands.push_back(d);
        }
        for_combos((int)cands.size(), k, [&](const int* idx) {
            uint32_t cells = 0, keep = 0;
            for (int i = 0; i < k; ++i) {
                cells |= pos[cands[idx[i]]];
                keep |= bit(cands[idx[i]]);
            }
            if (popc(cells) != k) return false;
            int n = 0;
            for (uint32_t cm = cells; cm; cm &= cm - 1) n += popc(cand[emp[__builtin_ctz(cm)]] & ~keep);
            if (!n) return false;
            Move& m = new_move(out, ht, g.shape, (int)emp.size());
            for (uint32_t cm = cells; cm; cm &= cm - 1) {
                int c = emp[__builtin_ctz(cm)];
                for (uint32_t dm = cand[c] & ~keep; dm; dm &= dm - 1) add_elim(out, m, c, lowdigit(dm));
            }
            m.nk = NM_GROUP;
            m.na = hi;
            {
                std::vector<int> pc;
                for (uint32_t cm = cells; cm; cm &= cm - 1) pc.push_back(emp[__builtin_ctz(cm)]);
                set_pattern(out, m, pc);
            }
            set_meta(m, k, 1, k, 0, 1, 0, 0, 1, g.shape);
            return false;
        });
    }
}

void Solver::fish(MoveBuf& out, int k) {
    const int tech = k == 2 ? XWING : SWORDFISH;
    const int W = p.W, H = (int)p.houses.size();
    std::vector<uint64_t> pos((size_t)H * W);
    std::vector<int> cnt(H), bases, covers;
    std::vector<uint64_t> U(W), CU(W);
    int combo[4], cov[4];
    auto ov = [&](int a, int b) { return p.group_overlap[(size_t)p.houses[a] * p.G + p.houses[b]] != 0; };
    for (int v = 1; v <= p.D; ++v) {
        uint32_t b = bit(v);
        for (int h = 0; h < H; ++h) {
            uint64_t* ph = &pos[(size_t)h * W];
            std::fill(ph, ph + W, 0);
            int n = 0;
            for (int c : p.groups[p.houses[h]].cells)
                if (!vals[c] && (cand[c] & b)) {
                    sbit(ph, c);
                    ++n;
                }
            cnt[h] = n;
        }
        bases.clear();
        for (int h = 0; h < H; ++h)
            if (cnt[h] >= 2 && cnt[h] <= k) bases.push_back(h);
        // combinations(bases, k), skipping overlapping (same order, pruned)
        std::function<void(int, int)> pick_base;
        std::function<void(int, int)> pick_cov;
        pick_cov = [&](int start, int depth) {
            if (depth == k) {
                std::fill(CU.begin(), CU.end(), 0);
                for (int i = 0; i < k; ++i) {
                    const uint64_t* gb = p.gbits(p.houses[cov[i]]);
                    for (int w = 0; w < W; ++w) CU[w] |= gb[w];
                }
                for (int w = 0; w < W; ++w)
                    if (U[w] & ~CU[w]) return;
                size_t mark = out.elims.size();
                // el = {(c,v) for h in cov for c in pos[h] if c not in U} (deduped)
                std::vector<uint64_t> elb(W, 0);
                for (int i = 0; i < k; ++i) {
                    const uint64_t* ph = &pos[(size_t)cov[i] * W];
                    for (int w = 0; w < W; ++w) elb[w] |= ph[w] & ~U[w];
                }
                bool any = false;
                for (int w = 0; w < W; ++w) any |= elb[w] != 0;
                if (!any) return;
                CompSum s;
                for (int i = 0; i < k; ++i) s.add(p.groups[p.houses[combo[i]]].shape);
                for (int i = 0; i < k; ++i) s.add(p.groups[p.houses[cov[i]]].shape);
                double shp = s.value() / (2 * k);
                int nU = 0;
                for (int w = 0; w < W; ++w) nU += __builtin_popcountll(U[w]);
                (void)mark;
                Move& m = new_move(out, tech, shp, k);
                for (int c = 0; c < p.N; ++c)
                    if (tbit(elb.data(), c)) add_elim(out, m, c, v);
                {
                    std::vector<int> bs, cs3;
                    for (int i = 0; i < k; ++i) {
                        bs.push_back(p.houses[combo[i]]);
                        cs3.push_back(p.houses[cov[i]]);
                    }
                    add_expl(out, m, EX_BASE, bs);
                    add_expl(out, m, EX_COVER, cs3);
                }
                {
                    std::vector<int> pc;
                    for (int c = 0; c < p.N; ++c)
                        if (tbit(U.data(), c)) pc.push_back(c);
                    set_pattern(out, m, pc);
                }
                set_meta(m, nU, 2 * k, 1, 0, 1, 0, 0, 1, shp);
                return;
            }
            for (int i = start; i < (int)covers.size(); ++i) {
                int h = covers[i];
                bool bad = false;
                for (int j = 0; j < depth && !bad; ++j) bad = ov(cov[j], h);
                if (bad) continue;
                cov[depth] = h;
                pick_cov(i + 1, depth + 1);
            }
        };
        pick_base = [&](int start, int depth) {
            if (depth == k) {
                std::fill(U.begin(), U.end(), 0);
                for (int i = 0; i < k; ++i) {
                    const uint64_t* ph = &pos[(size_t)combo[i] * W];
                    for (int w = 0; w < W; ++w) U[w] |= ph[w];
                }
                covers.clear();
                for (int h = 0; h < H; ++h) {
                    bool inc = false;
                    for (int i = 0; i < k; ++i) inc |= combo[i] == h;
                    if (inc) continue;
                    const uint64_t* ph = &pos[(size_t)h * W];
                    bool hit = false;
                    for (int w = 0; w < W && !hit; ++w) hit = ph[w] & U[w];
                    if (hit) covers.push_back(h);
                }
                pick_cov(0, 0);
                return;
            }
            for (int i = start; i < (int)bases.size(); ++i) {
                int h = bases[i];
                bool bad = false;
                for (int j = 0; j < depth && !bad; ++j) bad = ov(combo[j], h);
                if (bad) continue;
                combo[depth] = h;
                pick_base(i + 1, depth + 1);
            }
        };
        pick_base(0, 0);
    }
}

void Solver::xywing(MoveBuf& out, bool xyz) {
    const int need = xyz ? 3 : 2;
    const int W = p.W;
    std::vector<int> wings;
    std::vector<uint64_t> T(W);
    for (int piv = 0; piv < p.N; ++piv) {
        if (vals[piv] || popc(cand[piv]) != need) continue;
        uint32_t pc = cand[piv];
        wings.clear();
        for (int q : p.peer_list[piv])
            if (!vals[q] && popc(cand[q]) == 2) wings.push_back(q);
        for (size_t i = 0; i < wings.size(); ++i)
            for (size_t j = i + 1; j < wings.size(); ++j) {
                int w1 = wings[i], w2 = wings[j];
                uint32_t a = cand[w1], b2 = cand[w2], z;
                if (xyz) {
                    if (!((a | b2) == pc) || a == b2 || !((a & pc) == a) || !((b2 & pc) == b2)) continue;
                    z = a & b2;
                    if (popc(z) != 1) continue;
                    for (int w = 0; w < W; ++w) T[w] = p.peers(piv)[w] & p.peers(w1)[w] & p.peers(w2)[w];
                } else {
                    if (a == b2 || popc(a & b2) != 1) continue;
                    z = a & b2;
                    if (((a | b2) & ~z) != pc || (pc & z)) continue;
                    for (int w = 0; w < W; ++w) T[w] = p.peers(w1)[w] & p.peers(w2)[w];
                }
                int zd = lowdigit(z);
                int n = 0;
                for (int c = 0; c < p.N; ++c)
                    if (tbit(T.data(), c) && c != piv && c != w1 && c != w2 && !vals[c] && (cand[c] & z)) ++n;
                if (!n) continue;
                double shp = pspread({piv, w1, w2});
                Move& m = new_move(out, xyz ? XYZWING : XYWING, shp, 0);
                for (int c = 0; c < p.N; ++c)
                    if (tbit(T.data(), c) && c != piv && c != w1 && c != w2 && !vals[c] && (cand[c] & z))
                        add_elim(out, m, c, zd);
                set_pattern(out, m, {piv, w1, w2});
                set_meta(m, 3, xyz ? 3 : 2, 3, 2, 0, 0, 0, 1, shp);
            }
    }
}

void Solver::coloring(MoveBuf& out) {
    const int W = p.W;
    std::vector<int> adj_order;
    std::vector<int> adj_idx(p.N, -1);
    std::vector<PySet> adj;
    std::vector<char> color_seen(p.N), in_comp(p.N);
    std::vector<int> comp_order, comp_col(p.N), stack;
    std::vector<uint64_t> g0(W), g1(W);
    for (int v = 1; v <= p.D; ++v) {
        uint32_t b = bit(v);
        for (int c : adj_order) adj_idx[c] = -1;
        adj_order.clear();
        adj.clear();
        auto link = [&](int x, int y) {
            if (adj_idx[x] < 0) {
                adj_idx[x] = (int)adj.size();
                adj.emplace_back();
                adj_order.push_back(x);
            }
            adj[adj_idx[x]].add(y);
        };
        for (int hi : p.houses) {
            int n = 0, cs2[2] = {-1, -1};
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & b)) {
                    if (n < 2) cs2[n] = c;
                    ++n;
                }
            if (n == 2) {
                link(cs2[0], cs2[1]);
                link(cs2[1], cs2[0]);
            }
        }
        std::fill(color_seen.begin(), color_seen.end(), 0);
        for (int start : adj_order) {
            if (color_seen[start]) continue;
            for (int c : comp_order) in_comp[c] = 0;
            comp_order.clear();
            comp_order.push_back(start);
            in_comp[start] = 1;
            comp_col[start] = 0;
            stack.assign(1, start);
            while (!stack.empty()) {
                int x = stack.back();
                stack.pop_back();
                adj[adj_idx[x]].for_each([&](int64_t yy) {
                    int y = (int)yy;
                    if (!in_comp[y]) {
                        in_comp[y] = 1;
                        comp_col[y] = 1 - comp_col[x];
                        comp_order.push_back(y);
                        stack.push_back(y);
                    }
                });
            }
            for (int c : comp_order) color_seen[c] = 1;
            if (comp_order.size() < 4) continue;
            std::vector<int> grp[2];
            std::fill(g0.begin(), g0.end(), 0);
            std::fill(g1.begin(), g1.end(), 0);
            for (int c : comp_order) {
                grp[comp_col[c]].push_back(c);
                sbit(comp_col[c] ? g1.data() : g0.data(), c);
            }
            std::vector<int> el;
            int wrap_side = -1, clash_a = -1, clash_b = -1;
            for (int side = 0; side < 2; ++side) {
                const auto& s = grp[side];
                bool wrap = false;
                for (size_t i = 0; i < s.size() && !wrap; ++i)
                    for (size_t j = i + 1; j < s.size() && !wrap; ++j)
                        if (tbit(p.peers(s[i]), s[j])) {
                            wrap = true;
                            clash_a = s[i];
                            clash_b = s[j];
                        }
                if (wrap) {
                    el = s;
                    wrap_side = side;
                    break;
                }
            }
            if (el.empty()) {
                for (int c = 0; c < p.N; ++c) {
                    if (vals[c] || in_comp[c] || !(cand[c] & b)) continue;
                    const uint64_t* pc = p.peers(c);
                    bool a0 = false, a1 = false;
                    for (int w = 0; w < W; ++w) {
                        a0 |= (pc[w] & g0[w]) != 0;
                        a1 |= (pc[w] & g1[w]) != 0;
                    }
                    if (a0 && a1) el.push_back(c);
                }
            }
            if (!el.empty()) {
                std::vector<std::pair<int, int>> co;
                for (int c : comp_order) co.push_back(p.coords[c]);
                int n = (int)comp_order.size();
                Move& m = new_move(out, COLORING, 1.0, n);
                for (int c : el) add_elim(out, m, c, v);
                set_pattern(out, m, comp_order);
                set_meta(m, n, n - 1, 1, n - 1, 1, 0, 0, 1, pspread(comp_order));
                std::vector<int> rec{v, wrap_side >= 0, wrap_side, clash_a, clash_b, (int)grp[0].size()};
                rec.insert(rec.end(), grp[0].begin(), grp[0].end());
                rec.insert(rec.end(), grp[1].begin(), grp[1].end());
                add_expl(out, m, EX_COLOR, rec);
            }
        }
        for (int c : comp_order) in_comp[c] = 0;
        comp_order.clear();
    }
}

// _relation_pointing
void Solver::relation_pointing(MoveBuf& out) {
    const int W = p.W;
    std::vector<int> poss;
    std::vector<uint64_t> cr(W);
    for (int bi : p.houses) {
        const Group& B = p.groups[bi];
        for (uint32_t mm = p.full & ~placed_g[bi]; mm; mm &= mm - 1) {
            int v = lowdigit(mm);
            uint32_t b = bit(v);
            poss.clear();
            for (int c : B.cells)
                if (!vals[c] && (cand[c] & b)) poss.push_back(c);
            if (poss.size() < 2) continue;
            for (int gen = 1; gen >= 0; --gen) {
                const std::vector<int>& L0 = gen ? p.rel[poss[0]] : p.neq[poss[0]];
                if (L0.empty()) continue;
                const uint64_t* b0 = gen ? p.relb(poss[0]) : p.neqb(poss[0]);
                for (int w = 0; w < W; ++w) cr[w] = b0[w];
                for (size_t i = 1; i < poss.size(); ++i) {
                    const uint64_t* bc = gen ? p.relb(poss[i]) : p.neqb(poss[i]);
                    for (int w = 0; w < W; ++w) cr[w] &= bc[w];
                }
                int mi = -1;
                for (int x = 0; x < p.N; ++x) {
                    if (!tbit(cr.data(), x)) continue;
                    if (vals[x] || std::find(poss.begin(), poss.end(), x) != poss.end()) continue;
                    uint32_t rm = b;
                    if (gen) {
                        rm = p.full;
                        for (int c : poss) rm &= p.rel_ex(c, x)[v];
                    }
                    uint32_t dm = cand[x] & rm;
                    if (!dm) continue;
                    if (mi < 0) {
                        Move& m0 = new_move(out, PAIRARC, B.shape, (int)poss.size());
                        mi = (int)out.moves.size() - 1;
                        (void)m0;
                    }
                    Move& m = out.moves[mi];
                    for (; dm; dm &= dm - 1) add_elim(out, m, x, lowdigit(dm));
                }
                if (mi >= 0) {
                    Move& m = out.moves[mi];
                    m.nk = NM_GROUP;
                    m.na = bi;
                    set_pattern(out, m, poss);
                    set_meta(m, (int)poss.size() + 1, 2, 1, 0, 1, 0, 1, 1, B.shape);
                }
            }
        }
    }
}

// _pairarc
void Solver::pairarc(MoveBuf& out) {
    relation_pointing(out);
    const int D1 = p.D + 1;
    for (int a = 0; a < p.N; ++a) {
        if (vals[a] || p.rel[a].empty()) continue;
        uint32_t ca = cand[a];
        for (size_t j = 0; j < p.rel[a].size(); ++j) {
            int b_ = p.rel[a][j];
            if (vals[b_]) continue;
            const uint32_t* tab = &p.rel_in[a][j * D1];  // rel_ex[b_][a]
            int mi = -1;
            for (uint32_t dm = cand[b_]; dm; dm &= dm - 1) {
                int v = lowdigit(dm);
                uint32_t nb = tab[v];
                if (ca && (ca & ~nb) == 0) {
                    if (mi < 0) {
                        new_move(out, PAIRARC, 1.0, popc(ca));
                        mi = (int)out.moves.size() - 1;
                    }
                    add_elim(out, out.moves[mi], b_, v);
                }
            }
            if (mi >= 0) set_meta(out.moves[mi], 2, 1, std::min(popc(ca) + 1, p.D), 0, 0, 0, 1, 1, 1.0);
        }
    }
}

// _innies
void Solver::innies(MoveBuf& out, bool notes) {
    std::vector<int> emp, common;
    uint32_t masks[32], allowed[32];
    for (const InnieSet& s : p.innies) {
        emp.clear();
        int rem = s.total;
        for (int c : s.cells) {
            if (!vals[c]) emp.push_back(c);
            rem -= vals[c];
        }
        if (emp.empty()) continue;
        const Group& H = p.groups[s.hi];
        int ncells = 0;
        for (int gi : s.cages) ncells += (int)p.groups[gi].cells.size();
        const int nc = (int)s.cages.size();
        if (!notes) {
            if (emp.size() == 1 && 1 <= rem && rem <= p.D) {
                Move& m = new_move(out, INNIE_D, H.shape, nc);
                for (int i = 0; i < nc; ++i) out.covers.push_back({K_CAGESUM, p.groups[s.cages[i]].shape, i + 1});
                m.cov_n = nc;
                m.pc = emp[0];
                m.pv = rem;
                m.nk = s.outie ? NM_OUTIE : NM_INNIE;
                m.na = s.hi;
                set_meta(m, ncells, nc + 1, 1, 0, 0, 1, 0, 0, H.shape);
                region_expl(out, m, s);
            }
            continue;
        }
        common_groups(emp, -1, common);
        bool distinct = !common.empty();
        for (size_t i = 0; i < emp.size(); ++i) masks[i] = cand[emp[i]];
        combo_allowed(emp, rem, distinct, masks, 0, allowed);
        int n = 0;
        for (size_t i = 0; i < emp.size(); ++i) n += popc(cand[emp[i]] & ~allowed[i]);
        if (!n) continue;
        Move& m = new_move(out, INNIE_N, H.shape, nc);
        for (size_t i = 0; i < emp.size(); ++i)
            for (uint32_t dm = cand[emp[i]] & ~allowed[i]; dm; dm &= dm - 1) add_elim(out, m, emp[i], lowdigit(dm));
        m.nk = s.outie ? NM_OUTIE : NM_INNIE;
        m.na = s.hi;
        set_pattern(out, m, emp);
        set_meta(m, ncells, nc + 1, (int)emp.size(), 0, 0, 1, 0, 1, H.shape);
        region_expl(out, m, s);
    }
}

// _cage_combo
void Solver::cage_combo(MoveBuf& out) {
    std::vector<int> emp;
    uint32_t masks[32], allowed[32];
    for (int gi : p.sum_cages) {
        const Group& g = p.groups[gi];
        emp.clear();
        int rem = g.total;
        for (int c : g.cells) {
            if (!vals[c]) emp.push_back(c);
            rem -= vals[c];
        }
        if (emp.empty()) continue;
        for (size_t i = 0; i < emp.size(); ++i) masks[i] = cand[emp[i]];
        {  // cached while the cage's empty-cell candidates are unchanged
            auto& cc = combo_cache[gi];
            std::vector<uint32_t> key(masks, masks + emp.size());
            key.push_back((uint32_t)rem);
            key.push_back(placed_g[gi]);
            if (cc.first == key) {
                std::copy(cc.second.begin(), cc.second.end(), allowed);
            } else {
                combo_allowed(emp, rem, true, masks, placed_g[gi], allowed);
                cc.first = key;
                cc.second.assign(allowed, allowed + emp.size());
            }
        }
        int n = 0;
        for (size_t i = 0; i < emp.size(); ++i) n += popc(cand[emp[i]] & ~allowed[i]);
        if (!n) continue;
        Move& m = new_move(out, CAGE_COMBO, g.shape, (int)emp.size());
        for (size_t i = 0; i < emp.size(); ++i)
            for (uint32_t dm = cand[emp[i]] & ~allowed[i]; dm; dm &= dm - 1) add_elim(out, m, emp[i], lowdigit(dm));
        m.nk = NM_GROUP;
        m.na = gi;
        set_pattern(out, m, emp);
        set_meta(m, (int)emp.size(), 1, (int)emp.size(), 0, 0, 1, 0, 1, g.shape);
    }
}

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
void Solver::trial(MoveBuf& out) {
    for (int c = 0; c < p.N; ++c) {
        if (vals[c] || popc(cand[c]) != 2) continue;
        for (uint32_t dm = cand[c]; dm; dm &= dm - 1) {
            int v = lowdigit(dm);
            std::vector<int> tlog;
            if (contradicts(c, v, canon ? &tlog : nullptr)) {
                Move& m = new_move(out, TRIAL, 1.0, 0);
                add_elim(out, m, c, v);
                if (canon && !tlog.empty()) {  // priced by the depth the refutation needed
                    const int rounds = tlog[tlog.size() - 4];
                    m.has_meta = true;
                    m.meta[0] = std::min(p.N, (int)(tlog.size() / 5) + 1);  // cells followed
                    m.meta[1] = 1;
                    m.meta[2] = 2;
                    m.meta[3] = rounds;
                    m.meta[4] = 0;
                    m.meta[5] = 0;
                    m.meta[6] = 0;
                    m.meta[7] = 1;
                    m.spread = 1.0;
                }
                add_expl(out, m, EX_TRIAL, {2, 1, c, v});
                if (!canon) return;  // canonical: every contradiction, not the first in cell order
            }
        }
    }
}

bool Solver::contradicts(int c, int v, std::vector<int>* log) {
    std::vector<uint8_t> sv = vals;
    std::vector<uint32_t> sc = cand, sg = placed_g;
    bool result = false;
    place(c, v);
    for (int it = 0; it < 200; ++it) {
        bool progress = false;
        for (int x = 0; x < p.N; ++x) {
            if (!vals[x]) {
                if (!cand[x]) {
                    if (log) log->insert(log->end(), {EV_X_EMPTY, it + 1, x, 0, -1});
                    result = true;
                    goto done;
                }
                if (popc(cand[x]) == 1) {
                    if (log) log->insert(log->end(), {EV_NAKED, it + 1, x, lowdigit(cand[x]), -1});
                    place(x, lowdigit(cand[x]));
                    progress = true;
                }
            }
        }
        for (int hi : p.houses) {
            for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
                uint32_t b = mm & (~mm + 1);
                bool any = false;
                for (int x : p.groups[hi].cells)
                    if (!vals[x] && (cand[x] & b)) {
                        any = true;
                        break;
                    }
                if (!any) {
                    if (log) log->insert(log->end(), {EV_X_HOUSE, it + 1, -1, lowdigit(b), hi});
                    result = true;
                    goto done;
                }
            }
        }
        if (!progress) break;
    }
done:
    vals.swap(sv);
    cand.swap(sc);
    placed_g.swap(sg);
    return result;
}

// Guessing switched off: the last resort is a proof, not a guess. Take the cell a guess would take (fewest candidates)
// and refute one of its wrong candidates by full search from the current state (no solution with it = eliminated).
// Recorded as TRIAL ('Trial and error', band Extreme); the solver never places a value it has not proved.
bool Solver::exhaust(MoveBuf& out) {
    std::vector<int> sol;
    if (!opt.solution.empty()) {
        sol = opt.solution;
    } else {
        auto sols = brute_solve(p, {}, 1, 2000000, &vals, &cand);
        if (sols.empty()) return false;
        sol = sols[0];
    }
    if (canon) compute_labels();
    std::vector<int> order;
    for (int x = 0; x < p.N; ++x)
        if (!vals[x] && popc(cand[x]) > 1) order.push_back(x);
    std::sort(order.begin(), order.end(), [&](int a, int b) {
        const int pa = popc(cand[a]), pb = popc(cand[b]);
        if (pa != pb) return pa < pb;
        return canon ? cell_label[a] < cell_label[b] : a < b;
    });
    for (int c : order) {
        for (uint32_t mm = cand[c]; mm; mm &= mm - 1) {
            const int v = lowdigit(mm);
            if (v == sol[c]) continue;
            std::vector<uint32_t> cc = cand;
            cc[c] = bit(v);
            bool complete = true;
            pm_long nodes = 0;
            auto sols = brute_solve(p, {}, 1, 2000000, &vals, &cc, &complete, &nodes);
            if (!sols.empty() || !complete) continue;  // not refuted (another solution, or the search ran out)
            MoveBuf g;                       // priced as the guess on this cell would be (expected refutation work)
            const bool priced = guess(g) && !g.moves.empty() && g.moves[0].has_meta;
            Move& m = new_move(out, TRIAL, 1.0, -1);
            if (priced) {
                m.has_meta = true;
                std::copy(g.moves[0].meta, g.moves[0].meta + 8, m.meta);
                std::copy(g.moves[0].xm, g.moves[0].xm + XM_N, m.xm);
            }
            add_elim(out, m, c, v);
            add_expl(out, m, EX_TRIAL, {2, 1, c, v});
            return true;
        }
    }
    return false;
}

bool Solver::guess(MoveBuf& out) {
    std::vector<int> sol;
    if (!opt.solution.empty()) {
        sol = opt.solution;
    } else {
        auto sols = brute_solve(p, {}, 1, 2000000, &vals, &cand);
        if (sols.empty()) return false;
        sol = sols[0];
    }
    int c = -1, best = 1 << 30;
    for (int x = 0; x < p.N; ++x)
        if (!vals[x] && popc(cand[x]) < best) {
            best = popc(cand[x]);
            c = x;
        }
    if (c < 0) return false;
    if (canon) {  // fewest candidates, then the smallest invariant label
        compute_labels();
        for (int x = 0; x < p.N; ++x)
            if (!vals[x] && popc(cand[x]) == best && cell_label[x] < cell_label[c]) c = x;
    }
    Move& m = new_move(out, GUESS, 1.0, popc(cand[c]));
    m.pc = c;
    m.pv = sol[c];
    if (canon) {
        // price = expected human cost of guessing: each wrong candidate is tried before the right one
        // with probability 1/2 and must be refuted by propagation (basic propagation to a fixpoint);
        // a wrong candidate that does not break within the budget is a deep bifurcation
        int total = 0, maxd = 0, deep = 0, nwrong = 0;
        double E = 0;
        for (uint32_t mm = cand[c]; mm; mm &= mm - 1) {
            const int v = lowdigit(mm);
            if (v == sol[c]) continue;
            ++nwrong;
            std::vector<uint8_t> fv;
            int steps = 0;
            const int r = fc_branch(c, v, 0, steps, &fv, nullptr);
            int work;
            if (r) {
                work = steps + 1;
            } else {
                int empt = 0;
                for (int x = 0; x < p.N; ++x) empt += !fv[x];
                ++deep;
                work = steps + 1 + P.guess_deep * empt;  // grows with what is left to search
            }
            total += work;
            maxd = std::max(maxd, work);
            E += 0.5 * work;
        }
        m.has_meta = true;
        m.meta[0] = std::min((int)std::lround(E * 10), 1 << 20);  // expected refutation work x10 (priced)
        m.meta[1] = popc(cand[c]);
        m.meta[2] = deep;
        m.meta[3] = 0;
        m.meta[4] = 0;
        m.meta[5] = 0;
        m.meta[6] = 0;
        m.meta[7] = 1;
        m.spread = 1.0;
        pm_long xm[XM_N] = {popc(cand[c]), nwrong ? total / nwrong : 0, maxd, deep, std::lround(E * 10), 0, 0, 0, 0, 0};
        std::copy(xm, xm + XM_N, m.xm);
    }
    return true;
}

void Solver::timed(const char* name, MoveBuf& b, const std::function<void()>& f) {
    if (!stats_out) {
        f();
        return;
    }
    const size_t n0 = b.moves.size();
    const auto t0 = std::chrono::steady_clock::now();
    f();
    auto& st = stats_out->stats[name];
    st.ms += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    st.calls += 1;
    st.hits += b.moves.size() > n0;
}

// every technique family of a phase: direct (no notes) or notes tiers
void Solver::collect_all(MoveBuf& b, bool direct_phase) {
    if (direct_phase) {
        timed("d:singles", b, [&] { direct_moves(b, false); });
        if (p.has_cages || !p.nary.empty()) {
            timed("d:innies", b, [&] { innies(b, false); });
            timed("d:nary", b, [&] { nary_direct(b); });
        }
        if ((!p.relations.empty() || !p.nary.empty()) && !disabled[LINE_D])
            timed("d:line", b, [&] { direct_moves(b, false, 2); });
        timed("d:locks", b, [&] {
            if (direct_locks()) direct_moves(b, true);
        });
        if (!disabled[MENTAL_D]) timed("d:mental", b, [&] { direct_moves(b, false, 3); });
        if (!disabled[MENTAL_CHAIN]) timed("d:mentalchain", b, [&] { mental_chains(b); });
        if (!disabled[EITHER_WAY]) timed("d:eitherway", b, [&] { either_way(b, true); });
        if (!disabled[MENTAL_NOTES]) timed("d:mentalnotes", b, [&] { mental_notes(b); });
        if (!disabled[COLOUR_ALGEBRA]) timed("d:colour", b, [&] { colour_algebra(b, true); });
        if (!disabled[WHAT_IF]) timed("d:whatif", b, [&] { what_if(b, true); });
        return;
    }
    for (auto& tier : tiers)
        for (auto& s : tier)
            if (!strategy_off(s->name(), disabled)) timed(s->name(), b, [&] { s->collect(*this, b); });
}

void Solver::state_moves(const std::vector<std::pair<int, int>>& givens, MoveBuf& b, int limit_per_tech) {
    init_state(givens);
    if ((int)cand_override.size() == p.N)  // a mid-solve state: the puzzle keeps its own domains, the open candidates come here
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) cand[c] &= cand_override[c];
    compute_empties();
    b.clear();
    collect_all(b, true);
    collect_all(b, false);
    filter(b);
    if (p.is_derived) tag_implied(b, 0);
    for (Move& m : b.moves) {
        cog_loads(m, b);
        desc_mode = -1;
        if (canon) describe(m, b);  // descriptors first: params meta_theta_full prices with them
        m.d = P.difficulty(m, b.covers.data(), p.D);
    }
    if (canon) canon_dedupe(b);
    if (limit_per_tech > 0) {  // the cheapest ones per technique
        std::vector<int> idx(b.moves.size());
        for (size_t i = 0; i < idx.size(); ++i) idx[i] = (int)i;
        std::stable_sort(idx.begin(), idx.end(), [&](int x, int y) { return b.moves[x].d < b.moves[y].d; });
        std::vector<int> cnt(N_TECH, 0);
        std::vector<Move> keep;
        for (int i : idx)
            if (cnt[b.moves[i].tech]++ < limit_per_tech) keep.push_back(b.moves[i]);
        b.moves.swap(keep);
    }
}

// --------------------------------------------------------------- run --
void Solver::filter(MoveBuf& b) {
    if (!any_disabled) return;
    size_t w = 0;
    for (size_t i = 0; i < b.moves.size(); ++i)
        if (!disabled[b.moves[i].tech]) b.moves[w++] = b.moves[i];
    b.moves.resize(w);
}

void Solver::take_notes(SolveResult& out, int n_empty) {
    if (opt.rollout) {
        int w = 0;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) w += popc(cand[c]);
        out.r_time += P.notes_lazy ? 0.0 : P.t_mark * w;  // lazy: marks are paid per step, where used
        out.r_ds.push_back(P.B[TAKE_NOTES]);
        out.r_notes = true;
        if (out.r_hardest < 0 || std::min(P.B[TAKE_NOTES], P.B[GUESS]) > out.r_maxd) {
            out.r_maxd = std::min(P.B[TAKE_NOTES], P.B[GUESS]);
            out.r_hardest = TAKE_NOTES;
        }
    }
    if (opt.rich) {
        static const MoveBuf none;
        rich_rows(none, out, true);
        rich_after(Move(), true);
    }
    int written = 0;
    for (int c = 0; c < p.N; ++c)
        if (!vals[c]) written += popc(cand[c]);
    StepRec st;
    st.move.tech = TAKE_NOTES;
    st.move.shape = 1.0;
    st.move.extra = written;
    st.move.d = P.B[TAKE_NOTES];
    st.alt_off = (int)out.alts.size();
    st.alt_n = 1;
    st.chosen = 0;
    st.mode = 1;
    st.n_empty = n_empty;
    st.n_cands = cand_total();
    st.notes_written = P.notes_lazy ? 0 : written;
    st.move.cov_off = (int)out.covers.size();
    st.move.el_off = (int)out.elims.size();
    out.alts.push_back(st.move);
    out.steps.push_back(st);
}

// Snyder marks (corner marks for a digit confined to two cells of a box): the writing step, priced like
// TakeNotes per mark (params t_mark), taken once when scanning dries up (params notes_mode = "snyder")
void Solver::take_snyder(SolveResult& out, int n_empty) {
    compute_mental(1);
    int written = 0;
    for (int g : p.houses) {
        if (p.group_line[g] != 2 || (int)p.groups[g].cells.size() != p.D) continue;
        for (int d = 1; d <= p.D; ++d) {
            int n = 0;
            bool placed = false;
            for (int c : p.groups[g].cells) {
                if (vals[c] == d) placed = true;
                if (!vals[c] && (md[c] & bit(d))) ++n;
            }
            if (!placed && n >= 2 && n <= P.snyder_max) written += n;  // 3-position marks: params snyder_max = 3
        }
    }
    if (opt.rollout) {
        out.r_time += P.t_mark * written;
        out.r_ds.push_back(P.B[SNYDER_MARKS]);
    }
    if (opt.rich) {
        static const MoveBuf none;
        rich_rows(none, out, true);
        rich_after(Move(), true);
    }
    StepRec st;
    st.move.tech = SNYDER_MARKS;
    st.move.shape = 1.0;
    st.move.extra = written;
    st.move.d = P.B[SNYDER_MARKS];
    st.alt_off = (int)out.alts.size();
    st.alt_n = 1;
    st.chosen = 0;
    st.mode = 0;
    st.n_empty = n_empty;
    st.n_cands = cand_total();
    st.notes_written = written;
    st.move.cov_off = (int)out.covers.size();
    st.move.el_off = (int)out.elims.size();
    out.alts.push_back(st.move);
    out.steps.push_back(st);
}

// Placements read from Snyder marks: (a) two digits whose marks in a box sit on the same two cells -> those
// cells hold just that pair (hidden pair); (b) a digit's mark pairs in two boxes of a band (stack) on the
// same two rows (columns) -> the digit leaves those rows (columns) in the third box. A move is emitted when
// the restricted view gives a single the plain view did not.
void Solver::snyder_moves(MoveBuf& out) {
    compute_mental(1);
    const int N = p.N, D = p.D;
    struct Pair { int g, d, x, y; };
    std::vector<Pair> pairs;
    for (int g : p.houses) {
        if (p.group_line[g] != 2 || (int)p.groups[g].cells.size() != D) continue;
        for (int d = 1; d <= D; ++d) {
            int x = -1, y = -1, n = 0;
            bool placed = false;
            for (int c : p.groups[g].cells) {
                if (vals[c] == d) placed = true;
                if (!vals[c] && (md[c] & bit(d))) {
                    if (n == 0) x = c; else y = c;
                    ++n;
                }
            }
            if (!placed && n == 2) pairs.push_back({g, d, x, y});
        }
    }
    if (pairs.empty() && P.snyder_max < 3) return;
    std::set<std::pair<int, int>> done;
    auto singles = [&](const std::vector<uint32_t>& v, const std::vector<int>& pat, int code, int nmarks) {
        // naked singles
        for (int c = 0; c < N; ++c) {
            if (vals[c] || popc(v[c]) != 1 || popc(md[c]) == 1) continue;
            const int d = lowdigit(v[c]);
            if (!done.insert({c, d}).second) continue;
            Move& m = new_move(out, SNYDER_D, 1.0, nmarks);
            m.pc = c, m.pv = d;
            set_pattern(out, m, pat);
            set_meta(m, (int)pat.size(), 1, 2, 1, 0, 0, 0, 0, pspread(pat));
            m.code = code;
            pm_long xm[XM_N] = {nmarks, 0, 0, 0, 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
        // hidden singles in a house
        for (int g : p.houses)
            for (int d = 1; d <= D; ++d) {
                if (placed_g[g] & bit(d)) continue;
                int at = -1, n = 0, n0 = 0;
                for (int c : p.groups[g].cells) {
                    if (vals[c]) continue;
                    if (v[c] & bit(d)) ++n, at = c;
                    if (md[c] & bit(d)) ++n0;
                }
                if (n != 1 || n0 == 1 || !done.insert({at, d}).second) continue;
                Move& m = new_move(out, SNYDER_D, 1.0, nmarks);
                m.pc = at, m.pv = d;
                set_pattern(out, m, pat);
                add_expl(out, m, EX_BASE, {g});
                set_meta(m, (int)pat.size(), 2, 2, 1, 1, 0, 0, 0, pspread(pat));
                m.code = code;
                pm_long xm[XM_N] = {nmarks, 1, 0, 0, 0, 0, 0, 0, 0, 0};
                std::copy(xm, xm + XM_N, m.xm);
            }
    };
    // (a) hidden pairs from coinciding Snyder pairs
    for (size_t i = 0; i < pairs.size(); ++i)
        for (size_t j = i + 1; j < pairs.size(); ++j) {
            const Pair &a = pairs[i], &b = pairs[j];
            if (a.g != b.g || a.x != b.x || a.y != b.y) continue;
            std::vector<uint32_t> v = md;
            const uint32_t keep = bit(a.d) | bit(b.d);
            if ((v[a.x] & ~keep) == 0 && (v[a.y] & ~keep) == 0) continue;
            v[a.x] &= keep, v[a.y] &= keep;
            singles(v, {a.x, a.y}, 5201, 4);
        }
    // (c) params snyder_max = 3: three digits whose 2- / 3-position marks in a box lie inside the same three
    // cells -> those cells hold just these digits (hidden triple read from the marks)
    if (P.snyder_max >= 3) {
        for (int g : p.houses) {
            if (p.group_line[g] != 2 || (int)p.groups[g].cells.size() != D) continue;
            std::vector<std::pair<int, std::vector<int>>> mk;  // digit, cells
            for (int d = 1; d <= D; ++d) {
                if (placed_g[g] & bit(d)) continue;
                std::vector<int> cs;
                for (int c : p.groups[g].cells)
                    if (!vals[c] && (md[c] & bit(d))) cs.push_back(c);
                if (cs.size() >= 2 && cs.size() <= 3) mk.push_back({d, cs});
            }
            for (size_t i = 0; i < mk.size(); ++i)
                for (size_t j = i + 1; j < mk.size(); ++j)
                    for (size_t k = j + 1; k < mk.size(); ++k) {
                        std::vector<int> u;
                        for (size_t t : {i, j, k}) u.insert(u.end(), mk[t].second.begin(), mk[t].second.end());
                        std::sort(u.begin(), u.end());
                        u.erase(std::unique(u.begin(), u.end()), u.end());
                        if (u.size() != 3) continue;
                        const uint32_t keep = bit(mk[i].first) | bit(mk[j].first) | bit(mk[k].first);
                        std::vector<uint32_t> v = md;
                        bool any = false;
                        for (int c : u)
                            if (v[c] & ~keep) v[c] &= keep, any = true;
                        if (any) singles(v, u, 5203, 6);
                    }
        }
    }
    // (b) box-line X-wing from Snyder pairs: same digit, two boxes, the same two rows (columns)
    for (size_t i = 0; i < pairs.size(); ++i)
        for (size_t j = i + 1; j < pairs.size(); ++j) {
            const Pair &a = pairs[i], &b = pairs[j];
            if (a.d != b.d || a.g == b.g) continue;
            for (int orient = 0; orient < 2; ++orient) {
                auto line_of = [&](int c) { return orient == 0 ? p.coords[c].first : p.coords[c].second; };
                const int a1 = line_of(a.x), a2 = line_of(a.y), b1 = line_of(b.x), b2 = line_of(b.y);
                if (a1 == a2 || !((a1 == b1 && a2 == b2) || (a1 == b2 && a2 == b1))) continue;
                std::vector<uint32_t> v = md;
                bool any = false;
                for (int c = 0; c < N; ++c) {
                    if (vals[c] || !(v[c] & bit(a.d))) continue;
                    const int l = line_of(c);
                    if ((l != a1 && l != a2) || tbit(p.gbits(a.g), c) || tbit(p.gbits(b.g), c)) continue;
                    v[c] &= ~bit(a.d);
                    any = true;
                }
                if (any) singles(v, {a.x, a.y, b.x, b.y}, 5202, 4);
            }
        }
}

// forcing fallback (params forcing_fallback): dynamic, then nested forcing chains when a step would otherwise
// guess (its cheapest move is Trial / ShortTrial / Guess, or no move exists), within a deterministic work budget
// per solve (a call that would pass it yields nothing); boards up to 9x9 (on 25x25 killers a forcing call costs
// minutes beyond its counted branch steps)
bool Solver::fallback_open() const {
    return P.fc_fallback > 0 && p.D <= 9 && fb_spent < P.fc_fallback && fb_secs < P.fc_fallback_s;
}

bool Solver::forcing_fallback(MoveBuf& fb) {
    const auto t0 = std::chrono::steady_clock::now();
    // first: BandLogic once more with a larger budget (the break-in searches its regular budget cut short)
    if (P.band_escalate > 1 && P.band_budget > 0 && !disabled[BAND_LOGIC] && band_escalations < P.band_escalate_max &&
        p.D <= 16) {
        ++band_escalations;
        band_budget_now = P.band_budget * (pm_long)P.band_escalate;
        band_logic(fb);
        filter(fb);
        if (fb.moves.empty() && P.band_wide_cells > 0) {  // then regions with the rules that meet them taken whole
            fb.clear();
            band_wide_now = true;
            band_budget_now = P.band_budget * (pm_long)std::max(1, P.band_wide_factor);
            band_logic(fb);
            band_wide_now = false;
            filter(fb);
        }
        band_budget_now = 0;
        if (!fb.moves.empty()) {
            if (p.is_derived) tag_implied(fb, 0);
            fb_secs += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
            return true;
        }
        fb.clear();
    }
    const pm_long s0 = fc_steps_total;
    fc_abort_at = s0 + (P.fc_fallback - fb_spent);
    for (int lv = std::max(1, P.fc_level + 1); lv <= 2 && fb.moves.empty(); ++lv) {
        if (disabled[lv == 1 ? DYN_FORCING : NESTED_FORCING]) continue;
        fc_level_now = lv;
        fc_aborted = false;
        forcing(fb, lv, false);
        fc_level_now = -1;
        if (fc_aborted) {
            fb.clear();
            break;
        }
        filter(fb);
    }
    fc_abort_at = -1;
    fc_aborted = false;
    fb_spent += fc_steps_total - s0;
    fb_secs += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    if (fb.moves.empty()) return false;
    if (p.is_derived) tag_implied(fb, 0);
    return true;
}

void Solver::solve(const std::vector<std::pair<int, int>>& givens, SolveResult& out) {
    stats_out = opt.stats ? &out : nullptr;
    init_state(givens);
    if ((int)cand_override.size() == p.N)  // solve on from a mid-solve state (same mask as state_moves(cand=))
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) cand[c] &= cand_override[c];
    if (opt.seed_cell >= 0 && opt.seed_cell < p.N) {  // context of the move before step 1
        rich_last = opt.seed_cell;
        rich_last_digit = opt.seed_digit;
        rich_digit_run = std::max(1, opt.seed_run);
        rich_prev = {opt.seed_cell};
    }
    MoveBuf buf;
    int mode = opt.allow_direct ? 0 : 1;
    if (mode == 1) {
        compute_empties();
        take_notes(out, (int)empties.size());
    }
    for (int it = 0; it < opt.max_steps; ++it) {
        compute_empties();
        if (empties.empty()) break;
        const int n_empty = (int)empties.size();
        buf.clear();
        std::vector<int> entered;  // search order: stages tried this step (search-policy cost)
        if (P.human || (opt.rollout && opt.all_families)) {  // every family of the phase competes in the race
            collect_all(buf, mode == 0);
            filter(buf);
            if (buf.moves.empty() && mode == 0) {
                if (disabled[TAKE_NOTES]) break;
                mode = 1;
                compute_empties();
                take_notes(out, (int)empties.size());
                continue;
            }
            if (buf.moves.empty()) {
                MoveBuf fb;
                if (fallback_open() && forcing_fallback(fb)) {
                    std::swap(buf, fb);
                } else if (disabled[GUESS] && P.exhaust_fallback) {
                    if (!exhaust(buf)) break;
                } else {
                    if (disabled[GUESS]) break;
                    if (!guess(buf)) break;
                }
            }
        } else if (mode == 0) {
            entered.push_back(0);
            timed("d:singles", buf, [&] { direct_moves(buf, false); });
            filter(buf);
            if (buf.moves.empty() && (p.has_cages || !p.nary.empty())) {
                buf.clear();
                entered.push_back(1);
                timed("d:innies", buf, [&] { innies(buf, false); });
                timed("d:nary", buf, [&] { nary_direct(buf); });
                filter(buf);
            }
            const bool has_rel = !p.relations.empty() || !p.nary.empty();
            if (buf.moves.empty() && has_rel && !disabled[LINE_D]) {
                buf.clear();
                entered.push_back(2);
                timed("d:line", buf, [&] { direct_moves(buf, false, 2); });
                filter(buf);
            }
            if (buf.moves.empty()) {
                buf.clear();
                entered.push_back(3);
                timed("d:locks", buf, [&] {
                    if (direct_locks()) direct_moves(buf, true);
                });
                filter(buf);
            }
            if (buf.moves.empty() && P.snyder && !disabled[SNYDER_D]) {  // Snyder marks before deeper work
                if (!snyder_on) {
                    snyder_on = true;
                    compute_empties();
                    take_snyder(out, (int)empties.size());
                    continue;
                }
                buf.clear();
                entered.push_back(7);
                timed("d:snyder", buf, [&] { snyder_moves(buf); });
                filter(buf);
            }
            if (buf.moves.empty() && !disabled[MENTAL_D] && !P.snyder) {  // Snyder mode: deeper head-work -> notes
                buf.clear();
                entered.push_back(4);
                timed("d:mental", buf, [&] { direct_moves(buf, false, 3); });
                filter(buf);
            }
            if (buf.moves.empty() && !disabled[MENTAL_CHAIN] && !P.snyder) {
                buf.clear();
                entered.push_back(5);
                timed("d:mentalchain", buf, [&] { mental_chains(buf); });
                filter(buf);
            }
            if (buf.moves.empty() && !disabled[EITHER_WAY] && !P.snyder) {
                buf.clear();
                entered.push_back(6);
                timed("d:eitherway", buf, [&] { either_way(buf, true); });
                filter(buf);
            }

            if (buf.moves.empty()) {
                if (disabled[TAKE_NOTES]) break;
                mode = 1;
                compute_empties();
                take_notes(out, (int)empties.size());
                continue;
            }
        } else {
            for (size_t ti = 0; ti < tiers.size(); ++ti) {
                auto& tier = tiers[ti];
                buf.clear();
                entered.push_back(8 + (int)ti);
                for (auto& s : tier) {
                    if (strategy_off(s->name(), disabled)) continue;
                    if (opt.prune_tiers && !opt.rollout && !buf.moves.empty()) {
                        // lower bound of what the strategy can price at (B-priced case splits only)
                        const char* nm = s->name();
                        double lb = -1;
                        const bool bpriced_f = !P.has_theta || P.meta_excl[FORCING];
                        const bool bpriced_w = !P.has_theta || P.meta_excl[WHAT_IF];
                        if (!std::strcmp(nm, "forcing") && bpriced_f) lb = P.B[GUESS];  // >= the soft cap
                        if (!std::strcmp(nm, "whatif") && bpriced_w)
                            lb = P.B[WHAT_IF] * P.size(p.D) * (1.0 + std::log1p(2.0)) / (1.0 + std::log1p(10.0));
                        if (lb > 0) {
                            double best = 1e300;
                            for (Move& m : buf.moves) {
                                m.d = P.difficulty(m, buf.covers.data(), p.D);
                                best = std::min(best, m.d);
                            }
                            if (best < lb - 1e-9) continue;
                        }
                    }
                    timed(s->name(), buf, [&] { s->collect(*this, buf); });
                }
                filter(buf);
                if (!buf.moves.empty()) break;
            }
            if (buf.moves.empty()) {
                MoveBuf fb;
                if (fallback_open() && forcing_fallback(fb)) {
                    std::swap(buf, fb);
                } else if (disabled[GUESS] && P.exhaust_fallback) {
                    buf.clear();
                    if (!exhaust(buf)) break;
                } else {
                    if (disabled[GUESS]) break;
                    buf.clear();
                    if (!guess(buf)) break;
                }
            }
        }
        step_fails = entered.empty() ? 0 : (int)entered.size() - 1;
        step_fmask = 0;
        for (size_t i = 0; i + 1 < entered.size(); ++i) step_fmask |= 1u << std::min(entered[i], 31);
        // canonical choice: min difficulty (rounded to 1e-9, so last-bit float
        // noise can't decide), then technique, placement, smallest elimination
        auto key = [&](const Move& m) {
            uint32_t emin = 0xffffffffu;
            for (int k = 0; k < m.el_n; ++k) emin = std::min(emin, buf.elims[m.el_off + k]);
            return std::make_tuple(std::llround(m.d * 1e9), m.tech, m.pc < 0 ? (1 << 30) : m.pc, m.pv, emin, m.el_n);
        };
        if (p.is_derived) tag_implied(buf, 0);
#ifdef CSOLVER_DEBUG
        for (const Move& m : buf.moves)
            if (m.has_meta && (m.meta[2] > p.D || m.meta[2] < 0 || m.meta[0] > p.N || m.meta[0] < 0)) {
                std::fprintf(stderr, "csolver: bad meta tech %d cells %d digits %d\n", m.tech, m.meta[0], m.meta[2]);
                std::abort();
            }
#endif
        // forcing fallback (params forcing_fallback): when the cheapest move of this step would be a guess
        // (Trial / ShortTrial / Guess), first try dynamic, then nested forcing chains within a per-solve budget
        // (boards up to 9x9: on 25x25 killers a forcing call costs minutes beyond its counted branch steps)
        if (fallback_open() && !buf.moves.empty()) {
            int bi = 0;
            double bd = 1e300;
            for (size_t i = 0; i < buf.moves.size(); ++i) {
                const double d = P.difficulty(buf.moves[i], buf.covers.data(), p.D);
                if (d < bd - 1e-12) bd = d, bi = (int)i;
            }
            const int bt = buf.moves[bi].tech;
            if (bt == TRIAL || bt == SHORT_TRIAL) {  // (Guess moves only come after the empty-step fallback failed)
                MoveBuf fb;
                if (forcing_fallback(fb)) std::swap(buf, fb);
            }
        }
        int best = 0;
        const bool loads = P.human || opt.rich || opt.all_tiers;
        for (size_t i = 0; i < buf.moves.size(); ++i) {
            Move& m = buf.moves[i];
            if (loads) cog_loads(m, buf);
            desc_mode = mode;
            if (canon) describe(m, buf);  // canonical mode only (the Python-reference mode stays bit-identical)
            m.d = P.difficulty(m, buf.covers.data(), p.D);
        }
        if (canon) {
            canon_dedupe(buf);
            // invariant primary key; ties broken by invariant candidate labels,
            // index order only as the very last resort
            auto pkey = [&](const Move& m) {
                return std::make_tuple(std::llround(m.d * 1e9), m.tech, -(m.el_n + (m.pc >= 0 ? 1 : 0)));
            };
            std::vector<int> tied{0};
            for (size_t i = 1; i < buf.moves.size(); ++i) {
                auto a = pkey(buf.moves[i]), b2 = pkey(buf.moves[tied[0]]);
                if (a < b2)
                    tied.assign(1, (int)i);
                else if (a == b2)
                    tied.push_back((int)i);
            }
            best = tied[0];
            if (tied.size() > 1) {  // cheap invariant key first (no refinement)
                auto r0 = [&](int c, int v) {
                    uint64_t h = (uint64_t)popc(cand[c]) * 1000003ULL;
                    std::vector<int> cnt;
                    for (int gi : p.groups_of[c]) {
                        int k = 0, e = 0;
                        for (int q : p.groups[gi].cells) {
                            k += !vals[q] && (cand[q] & bit(v));
                            e += !vals[q];
                        }
                        cnt.push_back(p.group_cat[gi] * 4096 + k * 64 + e);
                    }
                    std::sort(cnt.begin(), cnt.end());
                    for (int x : cnt) h = h * 1315423911ULL + (uint64_t)x;
                    return h;
                };
                auto ckey = [&](const Move& m) {
                    std::vector<uint64_t> v;
                    if (m.pc >= 0) v.push_back(r0(m.pc, m.pv));
                    for (int k = 0; k < m.el_n; ++k) {
                        uint32_t e = buf.elims[m.el_off + k];
                        v.push_back(r0((int)(e / 32), (int)(e % 32)));
                    }
                    std::sort(v.begin(), v.end());
                    return v;
                };
                std::vector<std::vector<uint64_t>> ck(tied.size());
                for (size_t t = 0; t < tied.size(); ++t) ck[t] = ckey(buf.moves[tied[t]]);
                std::vector<int> t2;
                size_t bi = 0;
                for (size_t t = 1; t < tied.size(); ++t)
                    if (ck[t] < ck[bi]) bi = t;
                for (size_t t = 0; t < tied.size(); ++t)
                    if (ck[t] == ck[bi]) t2.push_back(tied[t]);
                tied.swap(t2);
                best = tied[0];
            }
            if (tied.size() > 1) {
                auto lkey = [&](const Move& m) {
                    std::vector<uint64_t> v;
                    if (m.pc >= 0) v.push_back(node_label(m.pc, m.pv));
                    for (int k = 0; k < m.el_n; ++k) {
                        uint32_t e = buf.elims[m.el_off + k];
                        v.push_back(node_label((int)(e / 32), (int)(e % 32)));
                    }
                    std::sort(v.begin(), v.end());
                    return v;
                };
                auto bl = lkey(buf.moves[best]);
                if (std::getenv("CSOLVER_TIEDEBUG")) {
                    std::fprintf(stderr, "tie step %d n=%zu:", (int)out.steps.size(), tied.size());
                    for (int t : tied) {
                        auto l = lkey(buf.moves[t]);
                        std::fprintf(stderr, " [tech %d d %.12f lab %016llx]", buf.moves[t].tech, buf.moves[t].d,
                                     (unsigned long long)(l.empty() ? 0 : l[0]));
                    }
                    std::fprintf(stderr, "\n");
                }
                for (size_t t = 1; t < tied.size(); ++t) {
                    auto l = lkey(buf.moves[tied[t]]);
                    if (l < bl || (l == bl && key(buf.moves[tied[t]]) < key(buf.moves[best]))) {
                        bl = l;
                        best = tied[t];
                    }
                }
            }
        } else {
            for (size_t i = 1; i < buf.moves.size(); ++i)
                if (key(buf.moves[i]) < key(buf.moves[best])) best = (int)i;
        }
        // params locality: a human stays near the last step while it pays; route choice by
        // price x exp(locality x log2(1 + Chebyshev distance)), distance in board coordinates (multi-grid aware); the
        // recorded step price is unchanged. locality = 0: the deterministic path above, untouched.
        auto mpos = [&](const Move& m, double& r, double& c) {
            double sr = 0, sc = 0; int n = 0;
            if (m.pc >= 0) { sr += p.coords[m.pc].first; sc += p.coords[m.pc].second; ++n; }
            for (int k = 0; k < m.el_n; ++k) { int cc = (int)(buf.elims[m.el_off + k] / 32); sr += p.coords[cc].first; sc += p.coords[cc].second; ++n; }
            if (!n) return false;
            r = sr / n; c = sc / n; return true;
        };
        if (P.locality > 0 && loc_r >= 0 && !(opt.rollout && opt.temperature > 1e-9)) {
            double bestv = 0; int bi = -1;
            for (size_t i = 0; i < buf.moves.size(); ++i) {
                double r, c, f = 1.0;
                if (mpos(buf.moves[i], r, c)) f = std::exp(P.locality * std::log2(1.0 + std::max(std::fabs(r - loc_r), std::fabs(c - loc_c))));
                const double v = buf.moves[i].d * f;
                if (bi < 0 || v < bestv - 1e-12 || ((int)i == best && std::fabs(v - bestv) <= 1e-12)) { bestv = v; bi = (int)i; }
            }
            if (bi >= 0) best = bi;
        }
        if (opt.rollout && opt.temperature > 1e-9) best = roll_pick(buf);  // T = 0: the deterministic path
        { double r, c; if (mpos(buf.moves[best], r, c)) { loc_r = r; loc_c = c; } }
        if (opt.all_tiers) {  // audit: append every other family's moves (not chosen)
            const size_t n0 = buf.moves.size();
            std::set<std::vector<uint32_t>> have;
            auto mkey = [&](const Move& m) {
                std::vector<uint32_t> k{(uint32_t)m.tech, (uint32_t)(m.pc + 1), (uint32_t)m.pv};
                std::vector<uint32_t> e(buf.elims.begin() + m.el_off, buf.elims.begin() + m.el_off + m.el_n);
                std::sort(e.begin(), e.end());
                k.insert(k.end(), e.begin(), e.end());
                return k;
            };
            for (size_t i = 0; i < n0; ++i) have.insert(mkey(buf.moves[i]));
            collect_all(buf, true);
            collect_all(buf, false);
            size_t w = n0;
            for (size_t i = n0; i < buf.moves.size(); ++i) {
                if (disabled[buf.moves[i].tech]) continue;
                if (!have.insert(mkey(buf.moves[i])).second) continue;
                buf.moves[w++] = buf.moves[i];
            }
            buf.moves.resize(w);
            if (p.is_derived) tag_implied(buf, n0);
            for (size_t i = n0; i < buf.moves.size(); ++i) {
                Move& m = buf.moves[i];
                cog_loads(m, buf);
                desc_mode = mode;
                if (canon) describe(m, buf);
                m.d = P.difficulty(m, buf.covers.data(), p.D);
            }
            // bounded audit: at most all_tiers_cap of the other families' moves per technique (the
            // cheapest; ties by the candidates they touch, so the kept set does not depend on discovery
            // order) -- one state cannot blow up the alternatives
            if (opt.all_tiers_cap > 0 && buf.moves.size() > n0) {
                std::vector<size_t> idx;
                for (size_t i = n0; i < buf.moves.size(); ++i) idx.push_back(i);
                auto mkey2 = [&](size_t i) {
                    const Move& m = buf.moves[i];
                    std::vector<uint32_t> e(buf.elims.begin() + m.el_off, buf.elims.begin() + m.el_off + m.el_n);
                    std::sort(e.begin(), e.end());
                    e.insert(e.begin(), (uint32_t)(m.pc + 1) * 32u + (uint32_t)m.pv);
                    return e;
                };
                std::stable_sort(idx.begin(), idx.end(), [&](size_t a, size_t b2) {
                    const pm_long da = std::llround(buf.moves[a].d * 1e9), db = std::llround(buf.moves[b2].d * 1e9);
                    if (da != db) return da < db;
                    return mkey2(a) < mkey2(b2);
                });
                std::vector<int> cnt(N_TECH, 0);
                std::vector<Move> keep(buf.moves.begin(), buf.moves.begin() + n0);
                for (size_t i : idx)
                    if (cnt[buf.moves[i].tech]++ < opt.all_tiers_cap) keep.push_back(buf.moves[i]);
                buf.moves.swap(keep);
            }
        }
        StepRec st;
        st.alt_off = (int)out.alts.size();
        st.alt_n = (int)buf.moves.size();
        st.chosen = best;
        st.mode = mode;
        st.n_empty = n_empty;
        st.n_cands = cand_total();
        for (const Move& m : buf.moves) {
            Move a = m;
            if (canon && !a.has_desc) {  // every exported move carries its descriptors (some audit paths skip them)
                desc_mode = mode;
                describe(a, buf);
            }
            a.cov_off = (int)out.covers.size();
            for (int i = 0; i < m.cov_n; ++i) out.covers.push_back(buf.covers[m.cov_off + i]);
            a.el_off = 0;
            a.el_n = 0;
            out.alts.push_back(a);
        }
        const Move& bm = buf.moves[best];
        if (opt.rich) {
            rich_best = best;
            rich_rows(buf, out, false);
            rich_after(bm, false);
        }
        st.move = out.alts[st.alt_off + best];
        st.move.pat_off = (int)out.pats.size();
        st.move.pat_n = bm.pat_n;
        out.pats.insert(out.pats.end(), buf.pats.begin() + bm.pat_off, buf.pats.begin() + bm.pat_off + bm.pat_n);
        st.move.ex_off = (int)out.ex.size();
        st.move.ex_n = bm.ex_n;
        out.ex.insert(out.ex.end(), buf.ex.begin() + bm.ex_off, buf.ex.begin() + bm.ex_off + bm.ex_n);
        if (opt.explain) st.move.ex_n += explain_chosen(bm, buf, out.ex);
        st.move.el_off = (int)out.elims.size();
        st.move.el_n = bm.el_n;
        for (int i = 0; i < bm.el_n; ++i) out.elims.push_back(buf.elims[bm.el_off + i]);
        if (opt.rollout) {  // time model + difficulty inputs (grader.scoring.predict_time / grade)
            const bool guessy = bm.tech == GUESS || bm.tech == TRIAL || bm.tech == SHORT_TRIAL;
            double den = 0;  // work_time's step time here: alternatives priced at most d_ref (Hidden Single)
            for (const Move& m : buf.moves) den += std::exp(-P.beta * std::min(m.d, P.B[2]));
            const double easy = P.c_time * n_empty / std::max(den, 1e-300);
            if (P.guess_time_linear != 0.0 && guessy && priced_meta(bm)) {  // linear in the expected work: work
                // units x the path's mean easy-step time (added when the path ends)
                const double w = bm.tech == GUESS ? std::max(bm.meta[0] / 10.0, 1.0) : (double)std::max(bm.meta[0], 1);
                out.r_gwork += w;
                out.r_gfallback += easy * w;
            } else {
                double denom = 0;
                for (const Move& m : buf.moves) denom += std::exp(-P.beta * m.d);
                out.r_time += P.c_time * n_empty / std::max(denom, 1e-300);
                if (!guessy) {
                    out.r_easy_sum += easy, ++out.r_easy_n;
                    if (P.guess_time_median) out.r_easy.push_back(easy);
                }
            }
            if (bm.pc >= 0) out.r_time += P.t_place;
            out.r_ds.push_back(bm.d);
            if (out.r_hardest < 0 || std::min(bm.d, P.B[GUESS]) > out.r_maxd) {
                out.r_maxd = std::min(bm.d, P.B[GUESS]);
                out.r_hardest = bm.tech;
            }
            if (bm.pc >= 0) {
                roll_last = bm.pc;
                roll_last_digit = bm.pv;
            }
        }
        int lazy_written = 0;
        if (P.notes_lazy && mode == 1) {  // write the candidates of the cells this step uses (once per cell)
            auto mark = [&](int c) {
                if (c < 0 || vals[c] || marked[c]) return;
                marked[c] = 1;
                lazy_written += popc(cand[c]);
            };
            for (int i = 0; i < bm.pat_n; ++i) mark(buf.pats[bm.pat_off + i]);
            for (int i = 0; i < bm.el_n; ++i) mark((int)(buf.elims[bm.el_off + i] / 32));
            mark(bm.pc);
            st.notes_written = lazy_written;
            if (opt.rollout) out.r_time += P.t_mark * lazy_written;
        }
        pm_long lazy_before = 0;
        auto marked_sum = [&]() {  // candidates written in the placed cell's peers / relation partners
            pm_long n = 0;
            for (int q : p.peer_list[bm.pc])
                if (marked[q] && !vals[q]) n += popc(cand[q]);
            for (int q : p.rel[bm.pc])
                if (marked[q] && !vals[q]) n += popc(cand[q]);
            return n;
        };
        if (P.notes_lazy && bm.pc >= 0) lazy_before = marked_sum();
        int erasures = 0;
        ++version;
        if (bm.pc >= 0) erasures = place(bm.pc, bm.pv);
        if (P.notes_lazy && bm.pc >= 0) erasures = (int)(lazy_before - marked_sum());  // only written marks are erased
        const bool single_move = bm.tech == NAKED_N || bm.tech == HIDDEN_N || is_direct(bm.tech);
        for (int i = 0; i < bm.el_n; ++i) {
            uint32_t e = buf.elims[bm.el_off + i];
            if (!single_move && (cand[e / 32] & bit((int)(e % 32)))) adv_src[e] = (int)out.steps.size();
            cand[e / 32] &= ~bit((int)(e % 32));
        }
        st.erasures = mode == 1 ? erasures : 0;
        if (opt.rollout) out.r_time += P.t_erase * st.erasures;
        out.steps.push_back(st);
    }
    bool solved = true;
    for (int c = 0; c < p.N; ++c)
        if (!vals[c]) solved = false;
    out.solved = solved && grid_valid();  // a filled grid must satisfy every rule
    if (opt.rollout) {  // grade(): soft bottleneck over the step difficulties
        out.r_time += P.t0;
        if (out.r_gwork > 0) {
            if (!out.r_easy_n) {
                out.r_time += out.r_gfallback;
            } else if (P.guess_time_median && !out.r_easy.empty()) {
                std::vector<double> e = out.r_easy;
                std::sort(e.begin(), e.end());
                const size_t h = e.size() / 2;
                out.r_time += out.r_gwork * (e.size() % 2 ? e[h] : 0.5 * (e[h - 1] + e[h]));
            } else {
                out.r_time += out.r_gwork * out.r_easy_sum / out.r_easy_n;
            }
        }
        out.r_steps = (int)out.r_ds.size();
        if (!out.r_ds.empty()) {
            double dmax = *std::max_element(out.r_ds.begin(), out.r_ds.end()), w = 0;
            for (double d : out.r_ds) w += std::exp((d - dmax) / P.tau);
            const double dens = w * P.ref_steps / std::max<size_t>(out.r_ds.size(), 1);
            out.r_difficulty = dmax + P.tau * std::log(std::max(dens, 1.0));
        }
    }
}

bool Solver::grid_valid() const {
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
        for (int i = 0; i < k.nv(); ++i) dom[i] = bit(vals[k.vars[i]]);
        GacOut o;
        nary_gac(k, dom, noreq, 1000, p.D, o);
        if (o.complete && !o.any) return false;
    }
    return true;
}

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

    Brute(const Puzzle& pz, int lim, pm_long nl) : p(pz), limit(lim), node_limit(nl) {
        for (int gi = 0; gi < p.G; ++gi)
            if (p.groups[gi].has_total) cages.push_back(gi);
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
        if (nodes > node_limit) {
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
                const NConstraint& k = p.nary[ki];
                if (k.type == NT_LINE || k.type == NT_SAMESET) continue;  // implied by pairs / houses
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
        int c = -1, best = 1 << 30;
        for (int x = 0; x < N; ++x)
            if (!vals[x] && popc(cand[x]) < best) {
                best = popc(cand[x]);
                c = x;
            }
        if (c < 0) {
            if (!valid(vals)) return;  // a full grid must satisfy every rule
            sols.emplace_back(vals, vals + N);
            return;
        }
        if ((int)vs.size() <= depth + 1) {
            vs.emplace_back(N);
            cs.emplace_back(N);
        }
        uint32_t snapshot = cand[c];
        for (uint32_t dm = snapshot; dm; dm &= dm - 1) {
            int v = lowdigit(dm);
            vals = vs[depth].data();
            cand = cs[depth].data();
            std::copy(vals, vals + N, vs[depth + 1].begin());
            std::copy(cand, cand + N, cs[depth + 1].begin());
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
