// Generic multi-cell ("n-ary") constraints and their consistency engine.
//
// A constraint is a scope of unique cells ("vars") plus a type-specific
// predicate over positions (positions index vars, so a cell may appear more
// than once, e.g. a line crossing itself). The engine enumerates assignments
// consistent with the current domains -- respecting pairwise distinctness
// (shared AllDiff groups / neq links / the constraint's own distinct flag)
// and pair-relation tables between scope cells -- with bound pruning, and
// returns per-var supports (generalized arc consistency), the number of
// consistent assignments, the intersection of their digit sets ("must
// contain") and whether that digit set is unique.
#pragma once
#include "portable.hpp"
#include <cstdint>
#include <vector>

namespace cs {

enum NType {
    NT_SUM = 0, NT_ARROW = 1, NT_EQSUM = 2, NT_SET = 3, NT_TABLE = 4,
    // outside-clue line constraints (cells in line order from the clue)
    NT_SANDWICH = 5,  // sum of digits strictly between the 1 and the D equals total
    NT_XSUM = 6,      // first k cells sum to total, k = first digit
    NT_SKYLINE = 7,   // number of visible (prefix-maximum) digits equals total
    // derived: law of leftovers, digits(segment 0) == digits(segment 1) as multisets
    NT_SAMESET = 8,
    // count (global cardinality): digit v appears exactly quota[v] times (-1: free)
    NT_COUNT = 9,
    // a line whose semantics are its pair relations (thermo, whisper, kropki chain...)
    NT_LINE = 10,
    // between line: digits strictly between the two end circles
    NT_BETWEEN = 11,
    // counting circles: every digit appears 0 or exactly v times among the circle cells
    NT_CIRCLES = 12,
    // first seen (e.g. "123" outside clues): reading the cells in order, the first digit of the set
    // (setkind = digit mask) is total
    NT_FIRSTSEEN = 13,
    // digit set: every house (segment) holds the same set of `total` digits (chosen from the universe 1..D)
    NT_DIGITSET = 14,
    // distinct count ("count different" rule): the cells hold exactly `total` different digits
    NT_DISTINCT = 15,
    // contains ("contains" rule): the digit of position 0 appears in at least one later position
    NT_CONTAINS = 16
};
// line kinds (grader.model.LINE_KINDS order)
enum LineKind { LK_THERMO = 0, LK_SLOW_THERMO, LK_WHISPER, LK_DUTCH, LK_RENBAN, LK_PALINDROME, LK_ENTROPIC,
                LK_KROPKI, LK_REGION_SUM, LK_PARITY, LK_BETWEEN, LK_MODULAR, LK_ZIPPER, LK_N };
inline bool nt_line(int t) { return t == NT_SANDWICH || t == NT_XSUM || t == NT_SKYLINE; }

// input form (from Python dicts)
struct NSpec {
    int type = NT_SUM;
    std::vector<int> a;                  // sum/set/table cells; arrow circle
    std::vector<std::vector<int>> segs;  // arrow: {line}; equal_sum: segments
    int total = 0;
    int distinct = -1;                   // -1 auto
    int setkind = 0;                     // set: 0 = consecutive
    std::vector<std::vector<int>> rows;  // table
    std::vector<int> quota;              // count: index = digit, -1 = unconstrained
    int line_kind = -1;                  // >= 0: a line rule (LineKind)
    std::vector<int> def_lines, def_regs;  // derived leftovers: the defining lines / regions
    std::vector<int> totals;  // sum with an unknown total from this set (incomplete clue); empty = total
    bool named = false;       // table with a rule name (moves coded 6000 + index)
    int offset = 0;           // equal_sum: segment sums of (digit - offset)
    bool bounds_only = false; // sum: derived (BandLogic) -- brute force propagates bounds only
    std::vector<int> seg_sign;  // bounds_only: +1 / -1 per segment (outie cells subtracted); empty = all +1
};

struct NConstraint {
    int type = NT_SUM;
    int index = -1;  // position in Puzzle::nary_specs (-1: derived from a cage group)
    int group = -1;  // cage group it was derived from
    int house = -1;  // derived innie/outie region: first house of the union
    int innie = -1;  // derived innie/outie region: index into Puzzle::big_innies
    bool set_theory = false;  // derived by build_set_theory (arrows / little killers in the region)
    bool outie = false;
    int n_cages = 0;
    std::vector<int> vars;   // unique cells
    std::vector<int> pvar;   // position -> var index
    int total = 0;
    std::vector<int> totals;  // incomplete clue: the total is one of these (empty: total)
    bool distinct = false;
    bool arith = false;
    int ncircle = 0;               // arrow: positions [0, ncircle) are circle digits
    std::vector<int> seg_start;    // equal_sum: segment k = [seg_start[k], seg_start[k+1])
    int setkind = 0;
    int arity = 0;
    bool named = false;  // table with a rule name
    int offset = 0;      // equal_sum: segment sums of (digit - offset)
    bool bounds_only = false;  // derived sum: bounds propagation in brute force
    std::vector<int> part;     // bounds_only: var -> part id (cells of a part are pairwise distinct)
    std::vector<std::vector<int>> parts;  // bounds_only: cells per part
    std::vector<int> part_sign;  // bounds_only: +1 / -1 per part (empty = all +1)
    std::vector<uint8_t> rows;     // table rows over positions
    std::vector<int> quota;        // count
    int line_kind = -1;            // >= 0: line rule (cells in line order = vars)
    std::vector<uint8_t> differ;   // nv*nv
    std::vector<const uint32_t*> rel;  // nv*nv: rel_ex(var i -> var j) or null
    std::vector<int> order;        // DFS order (vars)
    double shape = 1.0;
    int nv() const { return (int)vars.size(); }
};

struct GacReq {
    int v;
    uint64_t varmask;  // some var in mask must take v
};

struct GacOut {
    uint32_t sup[64];
    pm_long count = 0;          // consistent assignments (capped when !complete)
    bool complete = true;    // enumeration finished within budget
    bool set_unique = true;  // all assignments use the same digit set
    uint32_t must = 0;       // digits in every assignment (valid if complete)
    bool any = false;
};

// dom[i]: allowed digits of var i (placed vars: their single digit)
void nary_gac(const NConstraint& k, const uint32_t* dom, const std::vector<GacReq>& req, pm_long budget, int D,
              GacOut& out);
void nary_gac_brute(const NConstraint& k, const uint32_t* dom, pm_long budget, int D, GacOut& out);

}  // namespace cs
