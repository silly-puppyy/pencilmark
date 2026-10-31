// Listing cache: the moves one notes-tier strategy finds at one state, reused across state_moves calls.
//
// band_path lists the same states again and again: band by band at each step (bands <= 4, then <= 5 relists the
// band-4 strategies), and contents() reruns the whole route with one technique banned at a time, so most of its
// listings repeat a state already seen with a different set of disabled techniques (16 x 16 Expert: 2,723 of 4,467
// calls, 136 of 194 s). Every call builds a new Solver, so nothing carried over.
//
// A strategy's moves depend on the state, the puzzle, the params and the disabled flags it reads. The flags are
// recorded as the strategy reads them (Flags::rec), so an entry is reused only where every flag it read has the same
// value: the replayed moves are exactly what the strategy would find (no hand-kept list of which flags matter).
// Not cached: the direct phase, a listing cut short by the deadline, band logic inside a solve. The ALS strategies stop at a total move count
// (als.cpp: 4000), which depends on the moves listed before them: their entries are reused only where that cap cannot
// be reached, or with the same number of moves before them.
// Thread-local (featurize threads), bounded (Gen2: two generations, the older dropped).
#include <cstring>
#include <functional>
#include <string>
#include <unordered_map>

#include "solver.hpp"

namespace cs {

namespace {
struct LEntry {
    const Puzzle* pz;
    uint64_t uid, params;
    bool canon, assume_unique;
    std::string strat;
    std::vector<uint8_t> vals;
    std::vector<uint32_t> cand, written;
    std::vector<int> solution, colours;
    std::vector<std::pair<int, char>> reads;  // (technique, its disabled flag) for every flag the strategy read
    size_t n0, k;                             // moves in the buffer before the strategy; moves it added
    MoveBuf moves;
};
constexpr size_t ALS_CAP = 4000;  // als.cpp's smaller move-count cap

// Two generations: entries go into the young table; when it holds half the budget, it becomes the old table (the
// previous old one is dropped) and a hit there is copied back into the young one. Clearing everything at the bound
// threw away the working set of a contents() run whenever a card's solves had filled it. Weight of an entry: its
// moves + 1, + its state's size in move-sized units.
template <class E>
struct Gen2 {
    std::unordered_map<uint64_t, std::vector<E>> young, old;
    size_t weight = 0;
    const size_t budget;
    pm_long hits = 0, misses = 0, turns = 0;
    explicit Gen2(size_t b) : budget(b) {}
    void clear() {
        young.clear();
        old.clear();
        weight = 0;
    }
    E* put(uint64_t h, E&& e, size_t w) {
        if (weight + w > budget / 2) {
            old.swap(young);
            young.clear();
            weight = 0;
            ++turns;
        }
        weight += w;
        auto& v = young[h];
        v.push_back(std::move(e));
        return &v.back();
    }
    template <class Match, class Weight>
    const E* find(uint64_t h, Match match, Weight wt) {
        auto it = young.find(h);
        if (it != young.end())
            for (const E& e : it->second)
                if (match(e)) return ++hits, &e;
        auto jt = old.find(h);
        if (jt != old.end())
            for (const E& e : jt->second)
                if (match(e)) {
                    ++hits;
                    E copy = e;
                    return put(h, std::move(copy), wt(e));
                }
        ++misses;
        return nullptr;
    }
};
thread_local Gen2<LEntry> g_lcache(1000000);
thread_local bool g_lcache_on = true;

template <class T>
uint64_t mix(uint64_t h, const std::vector<T>& v) {
    for (const T& x : v) h = (h ^ (uint64_t)x) * 1099511628211ULL;
    return h;
}

// the moves from index n0 on, their side arrays rebased (as append_moves)
void copy_slice(const MoveBuf& b, size_t n0, MoveBuf& to) {
    for (size_t i = n0; i < b.moves.size(); ++i) {
        const Move& a = b.moves[i];
        Move m = a;
        m.cov_off = (int)to.covers.size();
        to.covers.insert(to.covers.end(), b.covers.begin() + a.cov_off, b.covers.begin() + a.cov_off + a.cov_n);
        m.el_off = (int)to.elims.size();
        to.elims.insert(to.elims.end(), b.elims.begin() + a.el_off, b.elims.begin() + a.el_off + a.el_n);
        m.pat_off = (int)to.pats.size();
        to.pats.insert(to.pats.end(), b.pats.begin() + a.pat_off, b.pats.begin() + a.pat_off + a.pat_n);
        m.ex_off = (int)to.ex.size();
        to.ex.insert(to.ex.end(), b.ex.begin() + a.ex_off, b.ex.begin() + a.ex_off + a.ex_n);
        to.moves.push_back(m);
    }
}

// per-digit memo: a single-digit technique's moves for digit v depend only on where v can go (and the puzzle and the
// technique's settings, folded into tag), so a step that leaves v's candidates alone finds the same moves
struct DEntry {
    const Puzzle* pz;
    uint64_t uid, tag;
    int v;
    std::vector<uint64_t> bits;
    MoveBuf moves;
};
thread_local Gen2<DEntry> g_dmemo(300000);

uint64_t dhash(const Puzzle& p, uint64_t tag, int v, const std::vector<uint64_t>& bits) {
    uint64_t h = (p.uid * 0x9E3779B97F4A7C15ULL) ^ (tag * 1315423911ULL) ^ (uint64_t)v;
    return mix(h, bits);
}

bool is_als(const std::string& s) { return s == "alsxz" || s == "alsxy" || s == "blossom" || s == "alsaic"; }

}  // namespace

void listing_cache_enable(bool on) {
    g_lcache_on = on;
    listing_cache_clear();
}

void listing_cache_clear() {
    g_lcache.clear();
    g_dmemo.clear();
}

std::vector<pm_long> listing_cache_stats() {
    return {g_lcache.hits, g_lcache.misses, g_lcache.turns, g_dmemo.hits, g_dmemo.misses, g_dmemo.turns};
}

namespace {
size_t lweight(const LEntry& e) { return e.k + 1 + e.cand.size() / 32; }
size_t dweight(const DEntry& e) { return e.moves.moves.size() + 1 + e.bits.size() / 4; }
}  // namespace

bool digit_memo_get(const Puzzle& p, uint64_t tag, int v, const std::vector<uint64_t>& bits, MoveBuf& out) {
    if (!g_lcache_on) return false;
    const DEntry* e = g_dmemo.find(
        dhash(p, tag, v, bits),
        [&](const DEntry& x) { return x.pz == &p && x.uid == p.uid && x.tag == tag && x.v == v && x.bits == bits; },
        dweight);
    if (!e) return false;
    append_moves(out, e->moves);
    return true;
}

void digit_memo_put(const Puzzle& p, uint64_t tag, int v, const std::vector<uint64_t>& bits, const MoveBuf& out,
                    size_t n0) {
    if (!g_lcache_on || deadline_passed()) return;
    DEntry e{&p, p.uid, tag, v, bits, {}};
    copy_slice(out, n0, e.moves);
    const size_t w = dweight(e);
    g_dmemo.put(dhash(p, tag, v, bits), std::move(e), w);
}

void Solver::collect_strategy(Strategy& s, MoveBuf& b) {
    const std::string name = s.name();
    // band logic spends a per-solve search budget (band_spent / band_total / band_budget_now): within a solve its moves
    // depend on the steps before, so it is cached only in state_moves (a fresh Solver per call)
    if (!lcache || !g_lcache_on || (lcache_solve && name == "bandlogic")) {
        s.collect(*this, b);
        return;
    }
    uint64_t h = std::hash<std::string>()(name) ^ (p.uid * 0x9E3779B97F4A7C15ULL) ^ lcache_params;
    h = mix(mix(mix(h, vals), cand), written_override);
    const size_t n0 = b.moves.size();
    const LEntry* hit = g_lcache.find(
        h,
        [&](const LEntry& e) {
            if (e.pz != &p || e.uid != p.uid || e.params != lcache_params || e.canon != canon ||
                e.assume_unique != opt.assume_unique || e.strat != name || e.vals != vals || e.cand != cand ||
                e.written != written_override || e.solution != opt.solution || e.colours != opt.colours)
                return false;
            for (const auto& r : e.reads)
                if (disabled.v[r.first] != r.second) return false;
            return !(is_als(name) && e.n0 != n0 && !(e.n0 + e.k <= ALS_CAP && n0 + e.k <= ALS_CAP));
        },
        lweight);
    if (hit) {
        append_moves(b, hit->moves);
        return;
    }
    std::vector<char> rec(disabled.size(), 0);
    disabled.rec = &rec;
    s.collect(*this, b);
    disabled.rec = nullptr;
    if (deadline_passed() || b.moves.size() < n0) return;  // cut short, or it removed moves listed before it
    LEntry e{&p, p.uid, lcache_params, canon, opt.assume_unique, name, vals, cand, written_override, opt.solution,
             opt.colours, {}, n0, b.moves.size() - n0, {}};
    for (size_t t = 0; t < rec.size(); ++t)
        if (rec[t]) e.reads.emplace_back((int)t, disabled.v[t]);
    copy_slice(b, n0, e.moves);
    const size_t w = lweight(e);
    g_lcache.put(h, std::move(e), w);
}

}  // namespace cs
