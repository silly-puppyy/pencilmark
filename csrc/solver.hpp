// Two-phase logical solver: technique ids, moves, pricing parameters and the Solver class (solver.cpp and the
// technique files).
#pragma once
#include "portable.hpp"
#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "model.hpp"
#include "deadline.hpp"

namespace cs {


// technique codes (grader.solver)
enum Tech {
    FULL_HOUSE = 0, NAKED_D = 1, HIDDEN_D = 2, NAKED_DL = 3, HIDDEN_DL = 4,
    TAKE_NOTES = 10, NAKED_N = 11, HIDDEN_N = 12, LOCKED = 13,
    NPAIR = 14, HPAIR = 15, NTRIPLE = 16, HTRIPLE = 17, NQUAD = 18, HQUAD = 19,
    XWING = 20, SWORDFISH = 21, XYWING = 22, XYZWING = 23, COLORING = 24, PAIRARC = 25, TRIAL = 26, GUESS = 27,
    INNIE_D = 28, CAGE_COMBO = 29, INNIE_N = 30,
    // n-ary constraint techniques (no Python reference implementation)
    SUM_COMBO = 31, ARROW_COMBO = 32, SET_COMBO = 33, EQSUM_COMBO = 34, TABLE_COMBO = 35, COMBO_LOCK = 36,
    NARY_D = 37, INNIE_X = 38,
    // generalized fish and chains
    FINNED_FISH = 39, JELLYFISH = 40, X_CHAIN = 41, XY_CHAIN = 42, AIC_CHAIN = 43, NICE_LOOP = 44,
    // line clues, leftovers, implied houses, uniqueness, ALS
    SANDWICH_COMBO = 45, XSUM_COMBO = 46, SKYLINE_COMBO = 47, LOL_COMBO = 48,
    IMPLIED = 49,  // pseudo technique: disabling it solves without implied houses / leftovers
    UNIQUE_RECT = 50, BUG_PLUS1 = 51, ALS_XZ = 52, ALS_XYWING = 53, DEATH_BLOSSOM = 54, ALS_AIC = 55,
    CANONICAL = 56,  // pseudo technique: disabled -> Python-reference (order-dependent) enumeration
    COUNT_COMBO = 57,
    LINE_D = 58, LINE_RANGE = 59, MENTAL_D = 60,
    SHORT_TRIAL = 61,
    MENTAL_CHAIN = 62,
    EITHER_WAY = 63,
    LINE_CLASS = 64,  // line reasoning on digit classes (high/low, parity, thirds, mod 3)
    DIGIT_COUNT = 65,  // positional set logic for one digit: must-contain units vs at-most-once groups
    EQUAL_DIGITS = 66, // abstract colouring: two cells forced to hold the same (unknown) digit
    LINE_SCAN = 67,
    FORCING = 68,         // k-way cell / unit forcing chains, basic propagation in the branches
    DYN_FORCING = 69,     // ... with the engine's techniques (up to a tier ceiling) in the branches
    NESTED_FORCING = 70,  // ... with forcing chains inside the branches (nested II)
    MEDUSA = 71,          // 3D Medusa: multi-digit colouring over bivalue / bilocal strong links
    SUM_BOUND = 72,       // min / max (triangular) bounds of sum rules
    CLASS_COUNT = 73,     // odd / even, low / middle / high counting; sum parity
    DOMINO = 74,          // relation dominoes: must-contain digit, two dominoes locking four digits
    COLOUR_ALGEBRA = 75,  // abstract-digit colour classes (cells holding the same unknown digit)
    N_WING = 76,          // WXYZ / VWXYZ wings (bent sets)
    SUE_DE_COQ = 77,
    APE = 78,             // aligned pair exclusion
    CHUTE_RP = 79,        // chute remote pairs
    POM = 80,             // pattern overlay method (per-digit templates)
    GURTH = 81,           // Gurth's symmetrical placement theorem (uniqueness)
    NISHIO = 82,          // single-digit forcing net
    WHAT_IF = 83,         // human "what if": two-way case split, each case followed with light logic
    MULTI_COLOR = 85,     // multi-colouring: two single-digit colour clusters interacting
    REMOTE_PAIRS = 86,    // XY-chain of identical bivalue pairs (own code: priced apart from XY-Chain)
    EMPTY_RECT = 87,      // empty rectangle (grouped X-chain through a box; own code)
    RULE_INTERSECT = 88,  // two rules / houses taken together (joint digit combinations over their cells)
    SUM_ALGEBRA = 89,     // interval algebra over unit sums in a band / stack (house totals, cages, segments)
    SNYDER_MARKS = 90,    // writing Snyder marks (a digit confined to <= 2 cells of a box), params notes_mode=snyder
    SNYDER_D = 91,        // a placement read from Snyder marks (hidden pair / box-line X-wing from Snyder pairs)
    BAND_LOGIC = 92,      // a band's lines + boxes + the rules inside taken together (sub-puzzle consistency)
    FIREWORKS = 93,       // Andrew Stuart's Fireworks: three digits confined to a cell, one cell of its row, one of its column
    HUMAN_CASE = 94,      // bounded human case analysis: refutation / cell / house forcing, <= case_rounds rule rounds
    COMBO_POS = 95,       // combination-aware positions: a cage's fillings cap how many of a digit set it holds in a house
    CLIQUE_HOUSE = 96,    // clique house: pairwise-different cells (houses, anti-knight, relations) as a virtual house
    LINE_SETS = 97,       // line digit sets across lines: renbans meeting a house choose disjoint digit sets there
    LINE_CLUES = 98,      // outside clues together: a line with >= 2 sandwich / x-sum / skyscraper clues enumerated as one unit
    WEIGHTED_SUMS = 99,   // weighted multi-house sums: integer combinations of sum facts down to 1-3 weighted cells
    CLUE_FACTS = 101,     // facts read off the clues alone (relations on an empty grid): no 5 on a whisper, thermo ranges
    CLUE_SHAPE = 102,     // clue facts with the line's shape: partners in one house needing more digits than allowed (a whisper 4 between two 9s)
    CLASS_COLOUR = 100,   // class colouring: low / high or odd / even links between cells; sides fixed by known cells or house counts
    MENTAL_NOTES = 84,    // single after notes logic done in the head (subset / pointing / combination on the mental view)    // line consistency on 3-cell windows (local scan of a long line)  // both options of a 2-way choice lead to the same placement / elimination  // short chain (<= 5 links) on the no-notes mental view, leading to a single  // bounded case split: bivalue cell, contradiction within a few direct rounds
    N_TECH = 128
};
inline bool is_direct(int t) {
    return t == FULL_HOUSE || t == NAKED_D || t == HIDDEN_D || t == NAKED_DL || t == HIDDEN_DL || t == INNIE_D ||
           t == NARY_D || t == LINE_D || t == MENTAL_D || t == MENTAL_CHAIN;
}
// cover-source kinds
enum Kind { K_HOUSE = 0, K_CAGE = 1, K_NEQ = 2, K_NONCONSEC = 3, K_DOMAIN = 4, K_LOCK = 5, K_CAGESUM = 6,
            K_LINE = 7,     // relation / line / inequality inference without notes
            K_MENTAL = 8 }; // mental subset (pair / triple held in mind)

struct Move;
inline bool priced_meta(const Move& m);
struct Cover {
    int kind;
    double shape;
    int u;
};

// name encodings (strings are built only for chosen moves, on the Python side)
enum NameKind { NM_NONE = 0, NM_GROUP = 1, NM_LOCK = 2, NM_INNIE = 3, NM_OUTIE = 4, NM_NARY = 5 };
// extended structural metadata (new techniques): xm[] slots, meaning per tech
// documented in pencilmark/cbackend.py (XMETA_KEYS); code = short pattern code
enum { XM_N = 10 };

// One move: the feature tuple (tech, base_shape, cover, extra, meta) plus
// placement / eliminations. cover and elims live in the owning buffer.
struct Move {
    int tech = 0;
    double shape = 1.0;
    int cov_off = 0, cov_n = 0;
    int extra = 0;
    bool has_meta = false;
    int meta[8] = {0, 0, 0, 0, 0, 0, 0, 0};  // cells groups digits links hidden arith relation notes
    double spread = 1.0;
    bool meta_synth = false;  // meta[] filled by describe() for export only (the technique is priced by B)
    bool has_desc = false;  // structural descriptors (desc.cpp): log branches, log depth, search, uniqueness,
    double desc[8] = {0, 0, 0, 0, 0, 0, 0, 0};  // counting, contradiction, held, coverage -- exported, not priced
    double scan = 0.0;  // desc.cpp: patterns of this kind a human scans at the state (raw count behind desc[2])
    double enumv = 0.0;  // log1p(max consistent assignments of the SUM rule instances the move touches)
    int pc = -1, pv = 0;  // placement
    int el_off = 0, el_n = 0;
    int nk = NM_NONE, na = 0, nb = -1;  // nb: second group / cage (-1 = none)
    double d = 0.0;
    pm_long xm[XM_N] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    int code = 0;
    pm_long tab_live = 0;  // table-backed move: live tuples of the justifying table (case-analysis burden)
    int pat_off = 0, pat_n = 0;  // pattern cells (cells justifying the move) in MoveBuf::pats
    // cognitive loads (human mode / rich features), see Solver::cog_loads; LOAD_N entries
    float load[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    bool has_load = false;
    int ex_off = 0, ex_n = 0;  // explanation records in MoveBuf::ex: [tag, len, data...]...
};
inline bool priced_meta(const Move& m) { return m.has_meta && !m.meta_synth; }  // the pricing view of has_meta
// explanation record tags (decoded by pencilmark/cbackend.py _explain)
enum {
    EX_BASE = 1,     // [group...]                 base units
    EX_COVER = 2,    // [group...]                 cover units
    EX_LINKS = 3,    // [rcc mask]                 restricted common digits (ALS-XZ)
    EX_ALS = 4,      // [-1-als, cand mask, cell...]
    EX_CHAIN = 5,    // [(cell | -1-als, digit, link type into the node, link source)...]
    EX_REASON = 6,   // [(cell, digit, reason kind, a, b)...]  why a digit / cell is excluded (singles)
    EX_TRIAL = 7,    // [view, n, (cell, digit) x n]  the assumption(s) of a trial / either-way
    EX_BRANCH = 8,   // [cell, digit, contradiction round, (event, round, cell, digit|mask, source)...]
    EX_COLOR = 9,    // [digit, wrap, eliminated side, clash a, clash b, n0, cells0..., cells1...]
    EX_REGION = 10,  // [total, outie, n houses, houses..., n cages, cages..., cells...]
    EX_ROLE = 11,    // ALS-XY-Wing: [hinge als, x, y, z mask]; Death Blossom: [stem, (digit, als)...]
    EX_RULE = 12,    // [constraint index...]      rule units (DigitCount)
    EX_LOCK = 13,    // [mode, digit, group...]    houses of a combination lock
    EX_GNODE = 14,   // [node id (<= -1000000), digit, cells...]  grouped chain node
    EX_DOMINO = 15   // [a, b, ...]                relation dominoes (cell pairs)
};
// reason kinds (EX_REASON)
enum {
    RK_GROUP = 0,     // a = group, b = cell holding the digit
    RK_NEQ = 1,       // a = cell holding the digit
    RK_RELATION = 2,  // a = related cell, b = its digit
    RK_DOMAIN = 3,    // the cell's own domain
    RK_CAGESUM = 4,   // a = cage group (sum arithmetic)
    RK_LOCK = 5,      // a = base house, b = target group (b < 0: relation / neq lock of digit -b-1)
    RK_ARC = 6,       // mental relation arc: a = partner cell (-1 unknown), b = depth
    RK_INEQ = 7,      // inequality bound: a = partner cell (-1: distinct predecessors), b = depth
    RK_LINE = 8,      // line / rule consistency: a = constraint ref, b = depth
    RK_SUBSET = 9,    // mental subset / pointing: a = house (-1 unknown), b = size
    RK_CANDIDATE = 10, // not a candidate (notes)
    RK_MPOINT = 11     // mental pointing: a = house confining the digit to 2-3 cells seen here, b = size
};
// branch events (EX_BRANCH)
enum {
    EV_NAKED = 1, EV_HIDDEN = 2, EV_REL = 3, EV_RULE = 4,
    EV_X_EMPTY = 5, EV_X_HOUSE = 6, EV_X_RULE = 7, EV_X_CLASH = 8,
    EV_TECH = 9  // a technique applied inside a branch: (9, iteration, placement cell | -1, tech, n elims)
};
// constraint refs (link sources, reasons, events): >= 0 nary_specs index, <= -2 cage group -2-ref
inline int cref(int nary_index, int group) { return nary_index >= 0 ? nary_index : -2 - group; }
// load order: cells scanned, log(1 + combos considered), propagation depth, constraints
// involved, search-like flag, pattern cells, chain length, reveal depth (earlier non-single moves
// whose eliminations the pattern's candidates depend on)
enum { LOAD_N = 8 };

struct MoveBuf {
    std::vector<Move> moves;
    std::vector<Cover> covers;
    std::vector<uint32_t> elims;  // c*32 + v
    std::vector<int> pats;        // pattern cells
    std::vector<int> ex;          // explanation records
    void clear() {
        moves.clear();
        covers.clear();
        elims.clear();
        pats.clear();
        ex.clear();
    }
};
inline void add_expl(MoveBuf& b, Move& m, int tag, const std::vector<int>& data) {
    if (!m.ex_n) m.ex_off = (int)b.ex.size();
    b.ex.push_back(tag);
    b.ex.push_back((int)data.size());
    b.ex.insert(b.ex.end(), data.begin(), data.end());
    m.ex_n += 2 + (int)data.size();
}
// ALS record: id, candidate mask, cells
inline void add_als_expl(MoveBuf& b, Move& m, int id, uint32_t cand, const std::vector<int>& cells) {
    std::vector<int> v{-1 - id, (int)cand};
    v.insert(v.end(), cells.begin(), cells.end());
    add_expl(b, m, EX_ALS, v);
}
// append every move of `from` to `to` (elims / patterns / explanations rebased)
inline void append_moves(MoveBuf& to, const MoveBuf& from) {
    for (const Move& a : from.moves) {
        Move m = a;
        m.cov_off = (int)to.covers.size();
        to.covers.insert(to.covers.end(), from.covers.begin() + a.cov_off, from.covers.begin() + a.cov_off + a.cov_n);
        m.el_off = (int)to.elims.size();
        to.elims.insert(to.elims.end(), from.elims.begin() + a.el_off, from.elims.begin() + a.el_off + a.el_n);
        m.pat_off = (int)to.pats.size();
        to.pats.insert(to.pats.end(), from.pats.begin() + a.pat_off, from.pats.begin() + a.pat_off + a.pat_n);
        m.ex_off = (int)to.ex.size();
        to.ex.insert(to.ex.end(), from.ex.begin() + a.ex_off, from.ex.begin() + a.ex_off + a.ex_n);
        to.moves.push_back(m);
    }
}
// copy a move's pattern / explanation from one buffer to another (offsets rebased)
inline void copy_extras(const MoveBuf& from, const Move& a, MoveBuf& to, Move& m) {
    m.pat_off = (int)to.pats.size();
    to.pats.insert(to.pats.end(), from.pats.begin() + a.pat_off, from.pats.begin() + a.pat_off + a.pat_n);
    m.ex_off = (int)to.ex.size();
    to.ex.insert(to.ex.end(), from.ex.begin() + a.ex_off, from.ex.begin() + a.ex_off + a.ex_n);
}
// record the cells that justify a move (rich features)
inline void set_pattern(MoveBuf& b, Move& m, const std::vector<int>& cells) {
    m.pat_off = (int)b.pats.size();
    b.pats.insert(b.pats.end(), cells.begin(), cells.end());
    m.pat_n = (int)cells.size();
}

struct Params {
    double B[N_TECH] = {0};
    std::vector<double> K;
    double gamma = 0.5, alpha = 1.0;
    std::vector<double> theta;  // meta_theta (empty = per-technique B path)
    std::vector<double> theta_full;  // params meta_theta_full: 18-19 weights pricing every technique (empty = off)
    double locality = 0.0;  // params locality: route choice by price x exp(locality x log2(1 + distance to the previous step)); 0 = off
    double theta_enum = 0.0;  // params meta_theta_enum (D5): weight on Move::enumv inside the meta_theta_full price
    std::vector<double> tech_obsc;       // params tech_obscurity: per-technique log-price offset = cultural familiarity /
                                         // obscurity (a property of the technique, measured from human outcomes); indexed by tech code
    std::vector<double> theta_interact;  // params meta_theta_interact 3 weights on log depth x log cells,
                                         // log depth x links, log depth x log branches (added to the meta_theta_full sum)
    bool has_theta = false;
    double theta_ac = 0.0;
    // guessing / trial prices: Guess d = B[Guess] * size * (1 + guess_k * expected refutation work);
    // a wrong candidate that survives basic propagation costs its steps + guess_deep * empty cells;
    // Trial / ShortTrial d *= 1 + trial_k * (rounds - 1)
    double guess_k = 0.02, trial_k = 0.25;
    double colour_chain_k = 0.0;  // ColourAlgebra chain multiplier (0 = off)
    double k_tab = 0.5;
    bool snyder = false;  // params notes_mode = "snyder": Snyder marks before full candidates
    int snyder_max = 2;  // params snyder_max: Snyder marks for digits confined to <= 2 (default) or <= 3 cells of a box
    int case_light = 0;  // params case_light: CaseAnalysis cases also run light techniques (intersections, pairs)
    int case_rounds = 0, case_cands = 4;  // params case_rounds (default 0 = off until a refit prices descriptors; 3 = on), case_cands
    bool dc_lines = true;  // params dc_lines: DigitCount uses line rules' must-contain digits
    bool mental_floor = false;  // params mental_floor: mental moves priced >= their written counterpart
    bool theta_full_v2 = false; // params theta_full_v2: meta_theta_full uses log1p(links); the mental floor's written
                                // counterpart also sets coverage (desc[7]) = 1
    bool notes_lazy = false;  // params notes_lazy: candidates are written only for the cells a notes step uses
    bool sets_first = false;  // params route = "sets_first": chains / ALS tiers after the set-arithmetic tiers
    pm_long band_budget = 400000;  // BandLogic node budget per state (0 = off)
    double band_k = 0.25;       // BandLogic: d *= 1 + band_k * log(cases) (refutation case count / search nodes)
    pm_long ri_budget = 1500000;  // RuleIntersection node budget per state (0 = off; featurize / rollouts may lower)  // table moves: d *= 1 + k_tab * log(live tuples)
    double guess_time_linear = 0.0;
    bool guess_time_median = false;  // params "guess_time_unit": "median" (default mean)  // != 0: Guess / Trial time = expected work x easy-step time
    int guess_deep = 5;  // meta interaction: arith x log(cells) (params "meta_theta_arith_cells")
    int meta_max_tech = 68;  // meta-theta applies to technique codes below this (params "meta_max_tech")
    bool meta_excl[N_TECH] = {false};  // ... and not to these codes (params "meta_exclude": B pricing)
    double tech_offset[N_TECH] = {0};  // optional: meta-path difficulty *= exp(offset[tech])
    bool has_offset[N_TECH] = {false};
    // human mode (params["human_mode"]): every family competes in the race (no tier
    // gating within the direct / notes phase); difficulty *= exp(sum_j k_j * max(0, load_j - budget_j))
    bool human = false;
    // time model (grader.scoring.predict_time / grade) for rollout summaries
    double t0 = 0, t_mark = 0, beta = 1, c_time = 0, t_place = 0, t_erase = 0, tau = 0.15, ref_steps = 55;
    double cap_pow = 0.0;  // > 0: beyond the cap d = cap + (d - cap)^cap_pow (steeper than log1p; 1 = uncapped)
    double cap_tau = 1.0;  // soft guess cap: d > cap -> cap + tau * log1p((d - cap) / tau); 0 = hard cap
    double hbudget[8] = {27, 1.95, 2, 4, 0, 9, 7, 0};
    double hk[8] = {0.02, 0.15, 0.3, 0.08, 0.7, 0.05, 0.1, 0.0};
    // forcing chains: highest level searched by the solver (-1 off, 0 static, 1 dynamic, 2 nested),
    // last notes tier usable inside branches, max options per level; price
    // d *= exp(fc_depth * level) * k^fc_branch * (1 + log1p(propagation steps))
    int fc_level = 0, fc_ceiling = 4;
    int band_escalate = 10, band_escalate_max = 3;
    int band_wide_factor = 3;  // params band_wide_factor: wide-region pass budget = this x band_budget
    int colour_partial = 0;    // params colour_partial: partial structural colouring when the symbol puzzle is not unique
    int band_outies = 1;       // params band_outies: derived house sums may subtract pieces' outie cells
    int band_wide_rules = 3;   // params band_wide_rules: largest subset of sticking-out rules per wide region (2 or 3)
    int band_wide_max = 600;   // params band_wide_max: at most this many wide regions (the smallest)
    int band_wide_cells = 32;  // params band_wide_cells: escalation regions with rules taken whole, <= this many cells (0 = off)  // params band_escalate (budget factor, <= 1 = off), band_escalate_max (per solve)
    pm_long fc_fallback = 50000;    // params forcing_fallback: work budget (branch steps per solve; default 5e4) for dynamic / nested
                                 // forcing tried when a step would otherwise guess (0 = off)
    int fish_max_n = 4;          // params fish_max_n: largest finned fish listed (the band path lists Medium with 2: larger
                                 // finned fish are Hard, so they can't be picked there)
    int exhaust_fallback = 0;    // params exhaust_fallback: 1 = where a step would guess (GUESS disabled), refute one
                                 // candidate by full search instead (tech TRIAL, 'Trial and error', band Extreme)
    double fc_fallback_s = 600.0;  // params forcing_fallback_s: wall-time safety per solve (checked between calls; the
                                   // deterministic work budget is meant to bind first)
    int fc_kmax[3] = {4, 3, 2};
    double fc_depth = 1.0, fc_branch = 1.0;
    bool gurth = false;  // Gurth's symmetry theorem (coordinate symmetries: not transform-invariant)
    double fc_work = 400000;  // budget: branches x (cells + 8 x rules); above it a level is skipped
    double size(int D) const { return py_pow((D - 1) / 8.0, alpha); }
    double difficulty(const Move& m, const Cover* covers, int D) const;
};
void meta_vector(const Move& m, double x[10]);

struct StepRec {
    int alt_off = 0, alt_n = 0, chosen = 0;
    int mode = 0;  // 0 direct, 1 notes
    int n_empty = 0, erasures = 0, notes_written = 0;
    pm_long n_cands = 0;  // candidates left in the empty cells before the step (engine view; Andrew Stuart's C)
    Move move;  // cov/el offsets index into SolveResult pools
};

struct SolveResult {
    std::vector<StepRec> steps;
    std::vector<Move> alts;  // features only (cov offsets into covers)
    std::vector<Cover> covers;
    std::vector<uint32_t> elims;
    bool solved = false;
    std::vector<int> pats, ex;  // pattern cells / explanation records of the chosen moves
    std::vector<float> m_rich;  // one row per alt (rich_names())
    std::vector<float> s_rich;  // one row per step (step_names())
    struct Stat { double ms = 0; pm_long calls = 0, hits = 0; };
    std::map<std::string, Stat> stats;  // SolveOptions::stats: per strategy / direct stage
    // rollout summary (SolveOptions::rollout)
    double r_time = 0.0, r_difficulty = 0.0, r_maxd = 0.0;
    double r_gwork = 0.0, r_gfallback = 0.0, r_easy_sum = 0.0;  // guess_time_linear: work units, easy steps
    pm_long r_easy_n = 0;
    std::vector<double> r_easy;  // easy-step times (median unit)
    std::vector<double> r_ds;
    int r_hardest = -1, r_steps = 0;
    bool r_notes = false;
};

class Solver;

// Strategy interface: a strategy appends every instance it finds to the move
// buffer. Tiers group strategies; the first tier yielding a move wins and the
// minimum-difficulty move of that tier is applied. New generic strategies
// (fish over arbitrary AllDiff families, AIC over a link graph, ALS, sum
// constraints...) plug in here without touching the solve loop.
struct Strategy {
    virtual ~Strategy() = default;
    virtual const char* name() const = 0;
    virtual void collect(Solver& s, MoveBuf& out) = 0;
};
using Tier = std::vector<std::shared_ptr<Strategy>>;
std::vector<Tier> default_notes_tiers();

// the disabled techniques. While a strategy's moves are listed for the listing cache (state_moves), every flag the
// strategy reads is recorded, so its cached moves are reused only where those flags are the same (listing_cache.cpp)
struct Flags {
    std::vector<char> v;
    mutable std::vector<char>* rec = nullptr;
    void assign(size_t n, char x) { v.assign(n, x); }
    size_t size() const { return v.size(); }
    char operator[](size_t i) const {
        if (rec) (*rec)[i] = 1;
        return v[i];
    }
    void set(size_t i, char x) { v[i] = x; }
};
void listing_cache_enable(bool on);  // on by default; off: every listing is computed (tests compare the two)
void listing_cache_clear();
// per-digit memo of single-digit techniques (listing_cache.cpp): tag = the technique and its settings, bits = the cells
// where digit v is still a candidate; get appends the stored moves and returns true on a hit
bool digit_memo_get(const Puzzle& p, uint64_t tag, int v, const std::vector<uint64_t>& bits, MoveBuf& out);
void digit_memo_put(const Puzzle& p, uint64_t tag, int v, const std::vector<uint64_t>& bits, const MoveBuf& out,
                    size_t n0);

struct SolveOptions {
    int max_steps = 5000;
    bool allow_direct = true;
    std::vector<int> disabled;
    // techniques whose strategies are not run in the notes tiers (state_moves(skip=...)): unlike disabled, the flags
    // every other strategy reads stay as they are, so the moves listed are exactly the full listing's minus theirs
    std::vector<int> skip;
    std::vector<int> solution;  // empty = brute force for Guess
    bool assume_unique = true;  // allow uniqueness techniques (UR, BUG+1)
    bool rich = false;          // emit rich per-move / per-step features (featurize)
    bool all_tiers = false;     // emit the moves of every technique family at each state (audit)
    int all_tiers_cap = 40;     // ... at most this many per technique (cheapest first; 0 = all)
    bool explain = false;       // add state-dependent explanation records to the chosen moves
    bool stats = false;         // per-strategy time / calls / hits (SolveResult::stats)
    // skip a tier's expensive case-split strategies when a move found earlier in the tier is already
    // cheaper than anything they can price at (same chosen move; fewer alternatives). Off for featurize.
    bool prune_tiers = false;  // off by default: it drops priced alternatives (predict_time sums over them)
    // human colouring (cell -> colour id, -1 none): a colour = "same digit" hypothesis seeding ColourAlgebra;
    // with a solution it is used only where consistent with it, otherwise it is soft (moves flagged)
    std::vector<int> colours;
    // stochastic rollout (distribution grading): sample the move instead of taking the cheapest,
    // P(m) ∝ exp((-d(m) + attract[tech] + eta log(1+effect) + focus . g) / temperature)
    bool rollout = false;
    double temperature = 1.0;
    uint64_t seed = 1;
    bool focus = true;
    bool all_families = false;  // race over every family of the phase (slow) vs the solver's tier gating
    std::vector<double> attract;  // per technique code (N_TECH), default 0
    double eta = 0.0;
    double gfocus[4] = {0, 0, 0, 0};  // log_dist_last, same_digit_last, same_box_last, near_last
    // rich features: context of the move before the first step (e.g. the human's
    // previous placement when states come from solve traces); -1 = none
    int seed_cell = -1, seed_digit = 0, seed_run = 1;
};
// rich feature names (column order of SolveResult::m_rich / s_rich)
const std::vector<std::string>& rich_names();
const std::vector<std::string>& step_names();

class Solver {
public:
    Solver(const Puzzle& p, const Params& P, const SolveOptions& o);
    // the puzzle actually solved: p.implied (derived houses, leftovers) unless
    // IMPLIED is disabled
    static const Puzzle& pick_puzzle(const Puzzle& pz, const SolveOptions& o);
    void solve(const std::vector<std::pair<int, int>>& givens, SolveResult& out);

    // ---- state ----
    const Puzzle& p;
    const Params& P;
    SolveOptions opt;
    Flags disabled;
    bool any_disabled = false;
    std::vector<char> skipped;  // opt.skip as flags
    bool lcache = false;  // state_moves: notes-tier strategies go through the listing cache
    uint64_t lcache_params = 0;  // hash of the params the listing was asked with (part of the cache key)
    bool lcache_solve = false;  // the listing cache is used inside solve() (history-dependent strategies bypass it)
    void collect_strategy(Strategy& s, MoveBuf& b);  // s->collect, through the listing cache when lcache is set
    std::vector<uint8_t> vals;
    std::vector<uint32_t> cand, placed_g;
    std::vector<char> is_given;  // cell was a given (avoidable rectangles)

    // ---- techniques (each appends to out) ----
    void direct_moves(MoveBuf& out, bool use_locks, int mental = 0);  // mental: 0 off, 2 relations/lines, 3 + subsets
    bool direct_locks();  // fills lock tables; returns "locks" truthiness
    void innies(MoveBuf& out, bool notes);
    void notes_singles(MoveBuf& out);
    void locked(MoveBuf& out);
    void cage_combo(MoveBuf& out);
    void pairarc(MoveBuf& out);
    void relation_pointing(MoveBuf& out);
    void subsets(MoveBuf& out, int k);
    void fish(MoveBuf& out, int k);
    void xywing(MoveBuf& out, bool xyz);
    void coloring(MoveBuf& out);
    void trial(MoveBuf& out);
    bool guess(MoveBuf& out);
    bool exhaust(MoveBuf& out);
    // n-ary constraints
    void nary_combination(MoveBuf& out, int part = 0);  // part 0: all but set equivalences, 1: only those, 2: all
    void combo_lock(MoveBuf& out);
    void nary_direct(MoveBuf& out);
    void innie_sum(MoveBuf& out);
    // ---- direct-mode mental layer (item 6) ----
    // relation arc consistency over house-restricted digits, inequality bounds
    // (chains / mutually distinct predecessors), line consistency; then mental
    // naked subsets (size 2-3). Exclusions beyond the house view: mex_rel / mex_ment.
    std::vector<uint32_t> mex_rel, mex_ment, md;
    std::vector<uint8_t> rs_type, rs_depth, rs_size;  // per cell*32+digit
    std::vector<int16_t> rs_line;
    pm_long mental_version = -1;
    int mental_level = 0;
    bool compute_mental(int level);
    // generalized fish (any complete groups as base/cover sets): size n,
    // finless (Jellyfish; X-Wing/Swordfish stay with the reference techniques)
    // and/or finned/sashimi; mutant shapes only for size 2
    void gfish(MoveBuf& out, int n, bool finless, bool finned);
    // alternating inference chains over the generic link graph, chain length
    // (links) in [lo, hi]; includes discontinuous nice loops (placements)
    void aic(MoveBuf& out, int lo, int hi);
    // uniqueness (only with opt.assume_unique)
    void unique_rect(MoveBuf& out);
    void bug_plus1(MoveBuf& out);
    void rule_intersect(MoveBuf& out);
    void sum_algebra(MoveBuf& out);
    void band_logic(MoveBuf& out);
    void describe(Move& m, const MoveBuf& b);  // structural descriptors (desc.cpp)
    std::vector<uint32_t> written_override;
    std::vector<uint32_t> cand_override;  // state_moves(cand=...): per cell, the candidates still open at this state  // state_moves(written=...): per cell, the candidates written down
    int desc_mode = -1;  // notation context of describe(): 0 no notes written, 1 notes, -1 unknown (state_moves: by technique)
    uint32_t written_marks(int c, int mode) const;  // candidates of c that are written down
    void desc_stats();
    pm_long ds_version = -1;
    bool ds_valid = false;
    int ds_cands = 0, ds_bivalue = 0, ds_empty = 0, ds_inter = 0;
    std::vector<int> ds_open, ds_lines;
    double ds_subsets[5] = {0, 0, 0, 0, 0};
    struct BandRegion {
        std::vector<int> lines, boxes, rules, cages, cells;
        std::vector<int> supers;  // regions holding all of this one's houses, rules and cages
        std::vector<int> pos;     // cell -> index in the sub-puzzle (-1 outside)
        std::shared_ptr<Puzzle> sub;
    };
    std::vector<int> struct_cls;  // structural colouring (struct_colours): symbol per cell, empty = none
    bool struct_done = false;
    const std::vector<int>& struct_colours();
    void colour_disambiguate(MoveBuf& out);
    std::vector<BandRegion> band_regions;
    bool band_built = false;
    std::vector<BandRegion> band_regions_wide;  // escalation-only regions (rules taken whole)
    bool band_built_wide = false;
    std::vector<char> marked;  // notes_lazy: cells whose candidates have been written
    bool band_wide_now = false;  // escalation pass over the wide regions
    pm_long band_budget_now = 0;  // > 0: band_logic runs once with this budget (fallback escalation)
    int band_escalations = 0;  // escalations used in this solve
    pm_long band_total = 0;  // all BandLogic search nodes in this solve (hard bound 32 x band_budget)
    pm_long band_spent = 0;  // search nodes used by BandLogic in this solve (fruitless calls, capped at 8 x band_budget)
    // exact: (region, region state) -> eliminations (cell*32+digit) with their refutation level / cases
    std::map<std::vector<uint32_t>, std::vector<std::array<pm_long, 3>>> band_cache;
    std::vector<std::vector<std::vector<uint8_t>>> band_sols;  // per region: fillings found (region cells), reused as supports
    std::map<std::vector<uint32_t>, std::vector<std::array<pm_long, 3>>> band_cache_wide;
    std::vector<std::vector<std::vector<uint8_t>>> band_sols_wide;
    std::map<std::vector<uint32_t>, std::pair<std::vector<uint32_t>, pm_long>> ri_cache;  // exact: (pair, union state) -> elims, nodes
    void bug_plus2(MoveBuf& out, int T1, int T2, int G0);
    void extended_ur(MoveBuf& out);
    // almost locked sets over any AllDiff group
    void als_xz(MoveBuf& out);
    void als_xywing(MoveBuf& out);
    void death_blossom(MoveBuf& out);
    void als_aic(MoveBuf& out, int hi);
    // bounded case split (human "what if"): returns rounds to contradiction, 0 = none
    void short_trial(MoveBuf& out);
    void human_case(MoveBuf& out);
    void combo_positions(MoveBuf& out);
    void clique_house(MoveBuf& out);
    void line_sets(MoveBuf& out);
    void line_clues(MoveBuf& out);
    void weighted_sums(MoveBuf& out);
    void mental_chains(MoveBuf& out);
    int case_split(int c, int v, int max_rounds, int& placed, std::vector<uint8_t>* ov = nullptr,
                   std::vector<uint32_t>* oc = nullptr, std::vector<int>* log = nullptr);
    int prop_rounds(int max_rounds, int& placed, std::vector<int>* log = nullptr);
    // explanation records of the chosen move that need the solver state (singles' reasons,
    // trial branches); appended to ex, returns the number of ints added
    int explain_chosen(const Move& m, const MoveBuf& b, std::vector<int>& ex);
    void either_way(MoveBuf& out, bool direct_view);
    void line_classes(MoveBuf& out);
    void digit_count(MoveBuf& out);
    void equal_digits(MoveBuf& out);
    void line_scan(MoveBuf& out);
    void medusa(MoveBuf& out);
    void multi_colouring(MoveBuf& out);
    void colour_algebra(MoveBuf& out, bool direct_view = false);
    void label_shadow(MoveBuf& out);
    pm_long table_live(const NConstraint& k) const;
    void n_wing(MoveBuf& out);
    void sue_de_coq(MoveBuf& out);
    void aligned_pair(MoveBuf& out);
    void fireworks(MoveBuf& out);
    void chute_remote_pairs(MoveBuf& out);
    void pattern_overlay(MoveBuf& out);
    void gurth(MoveBuf& out);
    void sum_bound(MoveBuf& out);
    void class_count(MoveBuf& out);
    void class_colour(MoveBuf& out);
    void clue_facts(MoveBuf& out);
    void domino(MoveBuf& out);
    // forcing chains (forcing.cpp)
    void forcing(MoveBuf& out, int level, bool nested = false);
    void nishio(MoveBuf& out);
    void what_if(MoveBuf& out, bool direct_view);
    void mental_notes(MoveBuf& out);
    int fc_ceiling_now = -1, fc_kmax_now = -1, fc_tech_now = -1, fc_step_cap = 0, fc_view = -1;
    int fc_level_now = -1;  // forcing fallback: level allowed for this call (overrides params forcing_level)
    pm_long fc_steps_total = 0;  // branch propagation steps of forcing() calls (fallback work budget)
    bool fallback_open() const;
    bool forcing_fallback(MoveBuf& fb);
    pm_long fc_abort_at = -1;    // forcing() gives up (fc_aborted) once fc_steps_total passes this (-1 = never)
    bool fc_aborted = false;
    pm_long fb_spent = 0;        // fallback work used in this solve
    double fb_secs = 0.0;     // fallback wall time used in this solve (safety only, checked between calls)
    int fc_propagate(int level, int& steps, std::vector<int>* log = nullptr);
    int fc_branch(int c, int v, int level, int& steps, std::vector<uint8_t>* ov = nullptr,
                  std::vector<uint32_t>* oc = nullptr, std::vector<int>* log = nullptr);
    pm_long version = 0;  // bumped whenever the state changes (chain cache key)
    struct DcCache { bool valid = false; std::vector<uint64_t> key; MoveBuf buf; };
    struct SplitMemo {
        std::vector<uint8_t> vals;
        std::vector<uint32_t> cand;
        int c0, v0, rounds, result, placed;
        std::vector<uint8_t> ov;
        std::vector<uint32_t> oc;
    };
    std::unordered_map<uint64_t, SplitMemo> split_memo;  // case_split results by exact state + assumption
    struct PropGac { bool valid = false; std::vector<uint32_t> dom; GacOut out; };
    std::unordered_map<const void*, PropGac> prop_gac;  // prop_rounds: last consistency result per rule
    void gac_prop(const NConstraint& k, const uint32_t* dom, pm_long budget, GacOut& out);  // nary_moves.cpp
    std::vector<DcCache> dc_cache;  // DigitCount results per digit, keyed on the digit plane + base units
    // ---- canonical (symmetry-invariant) mode, on unless CANONICAL is disabled ----
    bool canon = true;
    // structural spread of a cell pattern: complete groups touched / (2 sqrt(n) + 1)
    // (canonical; invariant under puzzle automorphisms) or the coordinate gyration
    // ratio (reference behaviour)
    double pspread(const std::vector<int>& cells) const;
    // invariant cell / candidate labels of the current state (colour refinement)
    std::vector<uint64_t> cell_label;
    pm_long label_version = -1;
    void compute_labels();
    uint64_t node_label(int c, int v);
    void canon_dedupe(MoveBuf& b);

    int place(int c, int v);
    bool grid_valid() const;
    // every move available at the current state (direct and notes families; tiers ungated), priced;
    // at most limit_per_tech per technique (0 = all)
    void state_moves(const std::vector<std::pair<int, int>>& givens, MoveBuf& b, int limit_per_tech);  // every cell filled consistently with every rule
    void init_state(const std::vector<std::pair<int, int>>& givens);

private:
    struct Src {
        int kind;
        double shape;
        uint32_t mask;
    };
    struct HSrc {
        uint64_t key;
        int kind;
        double shape;
        uint32_t local;
    };
    struct LockEntry {
        uint64_t ident;
        double shape;
        uint32_t mask;
        int tgt;  // index into lock_tgt (W words each)
    };
    std::vector<uint32_t> ex, ex2, seen;
    std::vector<const HSrc*> hc_srcs, hc_chosen;
    std::vector<int> empties;
    std::vector<std::vector<LockEntry>> lock_lst;
    std::vector<uint32_t> lock_mask;
    std::vector<int> lock_cells;
    std::vector<uint64_t> lock_tgt;
    std::vector<std::unordered_map<uint32_t, uint32_t>> cs_cache;
    std::unordered_map<int, std::pair<std::vector<uint32_t>, std::vector<uint32_t>>> combo_cache;
    std::vector<Tier> tiers;
    void nary_dom(const NConstraint& k, uint32_t* dom) const;
    struct GacCache {
        bool valid = false;
        std::vector<uint32_t> dom;
        GacOut out;
    };
    struct GacKey {
        const NConstraint* k;
        int v;
        uint64_t mask;
        bool operator==(const GacKey& o) const { return k == o.k && v == o.v && mask == o.mask; }
    };
    struct GacKeyHash {
        size_t operator()(const GacKey& x) const {
            return std::hash<const void*>()(x.k) ^ (std::hash<uint64_t>()(x.mask * 31 + (uint64_t)x.v) << 1);
        }
    };
    std::unordered_map<GacKey, GacCache, GacKeyHash> gcache;
    double loc_r = -1.0, loc_c = -1.0;  // position (board coords) of the previous route step, for params locality
    // consistency result (optionally with one "v somewhere in mask" requirement),
    // cached while the constraint's domains are unchanged
    const GacOut& gac_cached(const NConstraint& k, const uint32_t* dom, int req_v = 0, uint64_t req_mask = 0);
    pm_long aic_version = -1;
    int aic_depth = 0;
    MoveBuf aic_buf;
    std::vector<int> aic_len;
    void build_aic(int maxl, bool with_als = false);
    pm_long aicx_version = -1;
    int aicx_depth = 0;
    MoveBuf aicx_buf;
    std::vector<int> aicx_len;
    struct ALS {
        std::vector<uint64_t> cells;  // W words
        std::vector<int> list;
        uint32_t cand;
        int group;
    };
    pm_long als_version = -1;
    std::vector<ALS> als;
    // per ALS and digit: bitset of cells seeing every cell of the ALS holding that digit
    std::vector<uint64_t> als_seen;  // (als_index * 32 + d) * W
    void build_als();
    const uint64_t* als_seen_d(int a, int d) const { return &als_seen[((size_t)a * 32 + d) * p.W]; }
    bool als_rcc(int a, int b, int x) const;
    void tag_implied(MoveBuf& b, size_t from);
    // rich features
    int rich_last = -1, rich_step_idx = 0;
    int rich_last_digit = 0, rich_digit_run = 0;  // previous placement's digit, run of equal digits
    int rich_tech_used[N_TECH] = {0};
    // provenance: step of the non-single move that eliminated (cell, digit), -1 none (reveal depth)
    std::vector<int> adv_src;
    int roll_pick(const MoveBuf& b);  // sampled move index (rollouts)
    SolveResult* stats_out = nullptr;
    void timed(const char* name, MoveBuf& b, const std::function<void()>& f);
    uint64_t rng_state = 0;
    int roll_last = -1, roll_last_digit = 0;
    int step_fails = 0;        // families searched and found empty before the step's first success
    uint32_t step_fmask = 0;   // ... as a bitmask of their positions in the search order
    std::unordered_map<uint64_t, int> rich_first;
    void rich_rows(const MoveBuf& buf, SolveResult& out, bool notes_event);
    void rich_after(const Move& chosen, bool notes_event);
    void cog_loads(Move& m, const MoveBuf& b);
    void collect_all(MoveBuf& b, bool direct_phase);
    std::vector<std::vector<int>> rich_pats;  // pattern cells per move of the current step
    std::vector<int> rich_prev;               // pattern cells of the previous chosen move
    int rich_best = -1;

    void compute_empties();
    void direct_excl();
    uint32_t cagesum_direct(int gi);
    void direct_sources(int c, std::vector<Src>& out);
    using CoverScore = std::function<double(double, const std::vector<Cover>&)>;
    bool naked_cover(std::vector<Src>& srcs, double& base, std::vector<Cover>& cov, const CoverScore* score = nullptr);
    void hidden_sources(const std::vector<int>& cells, int v, int house, bool use_locks, std::vector<HSrc>& out);
    bool hidden_cover(int n_items, const std::vector<HSrc>& srcs, std::vector<Cover>& cov,
                      const CoverScore* score = nullptr);
    void common_groups(const std::vector<int>& poss, int discard, std::vector<int>& out);
    bool contradicts(int c, int v, std::vector<int>* log = nullptr);
  public:
    // generic refutation profile (refute.cpp): technique-free difficulty
    void refute_profile(const std::vector<std::pair<int, int>>& givens, const std::vector<int>& sol, int max_stuck,
                        std::vector<std::array<int, 5>>& out);
    bool basic_propagate(int& placed);
    int trial_depth(int c, int v, int cap = 1 << 30);
    int prop_cap = 1 << 30;      // basic_propagate stops (no contradiction) once it has made more placements than this
    const std::vector<uint32_t>* gac_ref = nullptr;  // a consistent state: rules none of whose cells differ from it are skipped
    int refK = 0;                                   // knowledge ladder: 0 singles+relations+GAC, 1 + locked candidates + pairs,
    std::vector<std::vector<int>> k_nbr;            // 2 + triples (over all houses); houses sharing >= 2 cells
    std::vector<std::vector<char>> k_in;            // house membership per cell
    std::vector<char> k_ok;                         // houses the ladder may use (refK >= 10: standard geometry only)
    void k_prepare();
    int k_step();                                   // -1 contradiction, 0 nothing, 1 progress
    // finding-cost profile per singles-stuck point (scan space, productive K1 patterns, unlocking patterns,
    // fallback flag, placements released)
    void finding_profile(const std::vector<std::pair<int, int>>& givens, const std::vector<int>& sol, int max_stuck,
                         std::vector<std::array<int, 5>>& out);
    bool k_has_single();
    void k_patterns(std::vector<std::vector<std::pair<int, uint32_t>>>& pats, int& checks);
    void cell_features(const std::vector<std::pair<int, int>>& givens, std::vector<std::array<double, 8>>& out);
  private:
    void take_notes(SolveResult& out, int n_empty);
    void take_snyder(SolveResult& out, int n_empty);
    void snyder_moves(MoveBuf& out);
    pm_long cand_total() const {  // candidates over the empty cells
        pm_long t = 0;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) t += popc(cand[c]);
        return t;
    }
    bool snyder_on = false;
    void filter(MoveBuf& b);
    void combo_allowed(const std::vector<int>& cells, int total, bool distinct, const uint32_t* masks, uint32_t forbid,
                       uint32_t* allowed);

    Move& new_move(MoveBuf& b, int tech, double shape, int extra);
};

// brute force (grader.solver.brute_solve); start_* empty -> from givens
std::vector<std::vector<int>> brute_solve(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, int limit,
                                          pm_long node_limit, const std::vector<uint8_t>* start_vals = nullptr,
                                          const std::vector<uint32_t>* start_cand = nullptr,
                                          bool* complete = nullptr,  // false: node limit hit before a verdict
                                          pm_long* nodes_out = nullptr,
                                          bool memo = false);  // memo: skip rules whose domains are unchanged

}  // namespace cs
