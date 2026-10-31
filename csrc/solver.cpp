#include <tuple>
#include "portable.hpp"
#include <cmath>
#include <algorithm>
#include <cstring>
#include <chrono>
// The solver: strategies and tiers, state, killer-cage combinations, trial / exhaustive fallbacks, move collection
// and the solve loop. Techniques live in direct_view.cpp, notes_view.cpp, nary_moves.cpp and the files named by
// their subject; exhaustive search in brute_force.cpp.
#include "solver.hpp"
#include "solver_util.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <set>

namespace cs {

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
                         : (m.tech == CLASS_COLOUR && B[m.tech] <= 0.0) ? B[COLORING]
                         : (m.tech == CLUE_FACTS && B[m.tech] <= 0.0) ? 0.5 * B[LINE_CLASS]
                         : (m.tech == CLUE_SHAPE && B[m.tech] <= 0.0) ? B[LINE_CLASS]
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
static bool strategy_off(const char* name, const Flags& disabled) {
    static const std::unordered_map<std::string, std::vector<int>> TECHS = {
        {"xwing", {XWING}}, {"swordfish", {SWORDFISH}}, {"jellyfish", {JELLYFISH}},
        {"finned2", {FINNED_FISH}}, {"finned3", {FINNED_FISH}}, {"finned4", {FINNED_FISH}},
        {"xywing", {XYWING}}, {"xyzwing", {XYZWING}}, {"nwing", {N_WING}},
        {"coloring", {COLORING}}, {"medusa", {MEDUSA}}, {"multicolour", {MULTI_COLOR}},
        {"alsxz", {ALS_XZ}}, {"alsxy", {ALS_XYWING}}, {"blossom", {DEATH_BLOSSOM}}, {"alsaic", {ALS_AIC}},
        {"suedecoq", {SUE_DE_COQ}}, {"ape", {APE}}, {"chuterp", {CHUTE_RP}},
        {"ur", {UNIQUE_RECT}}, {"xur", {UNIQUE_RECT}}, {"bug", {BUG_PLUS1}}, {"gurth", {GURTH}},
        {"pairs", {NPAIR, HPAIR}}, {"triples", {NTRIPLE, HTRIPLE}}, {"quads", {NQUAD, HQUAD}},
        {"digitcount", {DIGIT_COUNT}}, {"equaldigits", {EQUAL_DIGITS}}, {"colouralgebra", {COLOUR_ALGEBRA}}, {"classcolour", {CLASS_COLOUR}}, {"cluefacts", {CLUE_FACTS, CLUE_SHAPE}},
        {"ruleintersect", {RULE_INTERSECT}}, {"shorttrial", {SHORT_TRIAL}}, {"humancase", {HUMAN_CASE}},
        {"whatif", {WHAT_IF}}, {"eitherway", {EITHER_WAY}}};
    auto it = TECHS.find(name);
    if (it == TECHS.end()) return false;
    for (int t : it->second)
        if (t < (int)disabled.size() && !disabled[t]) return false;
    return true;
}

// a strategy left out by opt.skip: every technique it can emit is skipped (the same table as strategy_off)
static bool strategy_skipped(const char* name, const std::vector<char>& skipped) {
    if (skipped.empty()) return false;
    Flags f;
    f.v = skipped;
    return strategy_off(name, f);
}

// NOTES_TIERS
std::vector<Tier> default_notes_tiers() {
    return {
        {S("singles", [](Solver& s, MoveBuf& b) { s.notes_singles(b); })},
        {S("cagecombo", [](Solver& s, MoveBuf& b) { s.cage_combo(b); }),
         S("sumbound", [](Solver& s, MoveBuf& b) { s.sum_bound(b); }),
         S("combination", [](Solver& s, MoveBuf& b) { s.nary_combination(b, 0); }),
         S("lineclass", [](Solver& s, MoveBuf& b) { s.line_classes(b); }),
         S("cluefacts", [](Solver& s, MoveBuf& b) { s.clue_facts(b); }),
         S("linescan", [](Solver& s, MoveBuf& b) { s.line_scan(b); })},
        {S("locked", [](Solver& s, MoveBuf& b) { s.locked(b); }),
         // set equivalences (law of leftovers, Phistomefel, set theory) compete on price with pointing / claiming
         // (a one-line-vs-one-box LoL is pointing in disguise)
         S("leftovers", [](Solver& s, MoveBuf& b) { s.nary_combination(b, 1); }),
         S("pairarc", [](Solver& s, MoveBuf& b) { s.pairarc(b); }),
         S("domino", [](Solver& s, MoveBuf& b) { s.domino(b); }),
         S("classcount", [](Solver& s, MoveBuf& b) { s.class_count(b); }),
         S("classcolour", [](Solver& s, MoveBuf& b) { s.class_colour(b); }),
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
            disabled.set(t, 1);
            any_disabled = true;
        }
    for (int t : opt.skip)
        if (t >= 0 && t < N_TECH) {
            if (skipped.empty()) skipped.assign(N_TECH, 0);
            skipped[t] = 1;
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
        for (auto& s : tier) {
            if (deadline_passed()) return;
            if (!strategy_off(s->name(), disabled) && !strategy_skipped(s->name(), skipped))
                timed(s->name(), b, [&] { collect_strategy(*s, b); });
        }
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
        if (deadline_passed()) break;      // max_seconds: stop with the steps so far (reported as band "Unknown")
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

}  // namespace cs
