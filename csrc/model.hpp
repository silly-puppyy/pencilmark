// Constraint-agnostic puzzle model (mirror of grader/model.py).
//
// Constraint kinds:
//   AllDiff groups      -- complete (houses: exactly D cells, every digit once)
//                          or partial (cages), optionally carrying a sum
//   pair relations      -- exclusion tables rel_ex[a][b][v] = digits excluded
//                          at b when a == v (non-consecutive, thermo, kropki,
//                          XV, whispers, ... all reduce to this)
//   neq pairs           -- anti-knight / anti-king style "different" links
//   domains             -- per-cell allowed-digit masks
//
// Everything downstream works on these four primitives only; extensions
// (arrow sums, generic AIC link graphs, ...) add new primitives here plus
// strategies that consume them (see strategy.hpp).
#pragma once
#include "portable.hpp"
#include <atomic>
#include <cstdint>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

#include "nary.hpp"
#include "pycompat.hpp"

namespace cs {

inline uint32_t bit(int d) { return 1u << (d - 1); }
inline int popc(uint32_t m) { return __builtin_popcount(m); }
inline int lowdigit(uint32_t m) { return __builtin_ctz(m) + 1; }

double shape_ratio(const std::vector<std::pair<int, int>>& co);
// same quantity from exact integer moments: identical for translated / transposed
// copies of a cell set (canonical mode)
double shape_ratio_exact(const std::vector<std::pair<int, int>>& co);

struct Group {
    std::vector<int> cells;
    bool complete = false;
    bool has_total = false;
    int total = 0;
    double shape = 1.0;
    std::string name;
    std::string kind;  // grader Group.kind ('row' 'col' 'box' 'region' 'diag' 'window' 'cage' ...)
};
// group categories for rich features
enum GroupCat { GC_LINE = 0, GC_BOX = 1, GC_IRREGULAR = 2, GC_DIAG = 3, GC_WINDOW = 4, GC_CAGE = 5, GC_IMPLIED = 6 };

// a == v excludes fwd[v] at b; b == v excludes bwd[v] at a. Tables have D+1
// entries (index 0 unused). neq relations carry no tables.
struct RelSpec {
    int a = 0, b = 0;
    bool neq = false;
    std::vector<uint32_t> fwd, bwd;
};

struct InnieSet {
    int hi;
    std::vector<int> cells;
    int total;
    std::vector<int> cages;
    bool outie;
    std::vector<int> houses;  // the house union defining the region
};

// fixed-width cell bitset helpers (W 64-bit words per set)
inline bool tbit(const uint64_t* b, int i) { return (b[i >> 6] >> (i & 63)) & 1; }
inline void sbit(uint64_t* b, int i) { b[i >> 6] |= 1ULL << (i & 63); }

inline uint64_t next_puzzle_uid() {          // identity for cross-call caches (copies keep it: same content)
    static std::atomic<uint64_t> n{1};
    return n++;
}

struct Puzzle {
    uint64_t uid = next_puzzle_uid();
    // ---- input ----
    int D = 9;
    std::vector<std::pair<int, int>> coords;
    std::vector<Group> groups;
    std::vector<uint32_t> domains;  // empty -> all full
    std::vector<RelSpec> relations;
    std::vector<NSpec> nary_specs;  // n-ary constraints (grader Puzzle.constraints)

    // ---- derived (finalize) ----
    int N = 0, G = 0, W = 1;
    uint32_t full = 0;
    std::vector<int> houses;
    std::vector<std::vector<int>> groups_of;
    std::vector<std::vector<int>> neq;   // CPython set iteration order of p.neq[c]
    std::vector<std::vector<int>> rel;   // CPython set iteration order of p.nonconsec[c]
    // rel_out[c][j*(D+1)+v] = rel_ex[c][rel[c][j]][v]; rel_in = rel_ex[rel[c][j]][c][v]
    std::vector<std::vector<uint32_t>> rel_out, rel_in;
    std::vector<std::vector<int>> rel_sorted_j;  // indices j of rel[c] sorted by partner
    // rel_dir[c][j]: +1 partner rel[c][j] is strictly greater than c, -1 strictly smaller, 0 other
    std::vector<std::vector<int8_t>> rel_dir;
    std::vector<std::vector<int>> peer_list;     // sorted
    std::vector<uint64_t> peer_bits, neq_bits, rel_bits, group_bits;
    std::vector<char> group_overlap;  // G*G, cells shared
    std::vector<int> group_line;      // 0 row, 1 column (same coordinate), 2 other (box/region/diagonal...)
    std::vector<int> group_cat;       // GroupCat
    bool has_cages = false;
    std::vector<int> sum_cages;
    std::vector<InnieSet> innies;
    std::vector<std::vector<int>> house_unions;  // for inspection / tests
    std::vector<NConstraint> nary;      // from nary_specs (same order)
    std::vector<NConstraint> cage_nary; // sum-cage groups as sum constraints (combo-lock)
    std::vector<InnieSet> big_innies;   // rule-of-45 regions of 5..BIG_INNIE_MAX cells
    std::vector<NConstraint> innie_nary; // ... as derived sum constraints
    std::vector<NConstraint> line_windows;  // 3-cell windows of longer pairwise lines (LineScan)
    static const size_t BIG_INNIE_MAX = 7;

    void finalize();

    // ---- derived structure (item 3d) ----
    // Puzzle copy with implied complete houses (unions of parallel lines minus
    // disjoint houses inside them, iterated twice: windoku hidden windows,
    // jigsaw leftover regions) and law-of-leftovers same-multiset constraints
    // appended; null when nothing is implied. Built by finalize().
    std::shared_ptr<Puzzle> implied;
    // copy with exact (integer-moment) shapes for canonical solving; its own
    // `implied` is built too. null on derived copies.
    std::shared_ptr<Puzzle> canonical;
    bool exact_shapes = false;
    int base_G = -1;      // groups [base_G, G) are implied houses (in `implied`)
    int base_nary = -1;   // nary_specs [base_nary, ...) are derived leftovers
    bool is_derived = false;

    // unique-rectangle candidates (structure only), computed once on demand
    struct Rect {
        int c[4];  // A B / C D: A-B and C-D share groups, A-C and B-D share groups
    };
    const std::vector<Rect>& rects() const;

    const uint64_t* peers(int c) const { return &peer_bits[(size_t)c * W]; }
    const uint64_t* neqb(int c) const { return &neq_bits[(size_t)c * W]; }
    const uint64_t* relb(int c) const { return &rel_bits[(size_t)c * W]; }
    const uint64_t* gbits(int g) const { return &group_bits[(size_t)g * W]; }
    // rel_ex[x][y] table (y must be a relation partner of x)
    const uint32_t* rel_ex(int x, int y) const {
        const auto& r = rel[x];
        for (size_t j = 0; j < r.size(); ++j)
            if (r[j] == y) return &rel_out[x][j * (D + 1)];
        return nullptr;
    }

private:
    struct RectCache {
        std::once_flag once;
        std::vector<Rect> rects;
    };
    std::shared_ptr<RectCache> rect_cache;
    void build_implied();
    void build_innies();
    void build_nary();
    void build_set_theory();  // house unions minus cages / little killers, arrow lines replaced by circles
    NConstraint make_nc(int type, const std::vector<int>& positions, bool distinct) const;
};

// ---- builders mirroring grader/model.py (used by native featurize) ----
Puzzle make_standard(int size, int box_h, int box_w);
void add_nonconsecutive(Puzzle& p, int size);
void add_cages(Puzzle& p, const std::vector<std::pair<int, std::vector<int>>>& cages);
// RELATIONS table for a named kind (grader.model.RELATIONS); returns false if unknown
bool relation_tables(const std::string& kind, const std::vector<int>& args, int D, std::vector<uint32_t>& fwd,
                     std::vector<uint32_t>& bwd);

}  // namespace cs
