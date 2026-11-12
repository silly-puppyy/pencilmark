#pragma once
/// Evaluator of the custom rule language (pencilmark/rules/custom.py, docs/formats/rules/custom.mdx) for NT_EXPR
/// constraints: the expression arrives as nested int lists (custom.to_ir: names resolved to cell variables, cell lists
/// and slots), so the engine needs no parser. Semantics mirror the Python reference exactly (exact rationals, ABSENT
/// for an index out of range or a division by zero, comparisons with ABSENT false); tests compare the two.
#include <cstdint>
#include <memory>
#include <vector>

namespace cs {

/// opcodes: the order of custom.OPS
enum ExprOp {
    X_NUM, X_BOOL, X_CELLS, X_CELL, X_SLOT, X_LIST, X_RANGE, X_COMP, X_LET, X_LETFN, X_LAMBDA, X_IF, X_DEFAULT, X_OR,
    X_AND, X_NOT, X_EQ, X_NE, X_LT, X_LE, X_GT, X_GE, X_IN, X_NOTIN, X_ADD, X_SUB, X_MUL, X_DIV, X_IDIV, X_MOD, X_POW,
    X_NEG, X_INDEX, X_SLICE, X_CALL, X_CALLFN, X_NONE,
    X_AUX,      ///< an unknown of the file: v = its aux variable
    X_AUXCELL   ///< a layer at a cell: v = the layer, kids[0] = the cell
};

struct ExprNode {
    int op = X_NONE;
    long long v = 0;              ///< number, slot, variable, cell-list index or built-in id, by op
    std::vector<int> params;      ///< letfn / lambda parameter slots
    std::vector<ExprNode> kids;
};

/// a cell list of the rule: variable indices, or nested lists of them
struct ExprList {
    int var = -1;                 ///< >= 0: one cell
    std::vector<ExprList> items;  ///< otherwise a list
};

struct ExprProgram {
    ExprNode root;
    std::vector<ExprList> lists;  ///< the rule's named cell lists, by index
    std::vector<int> row, col;    ///< per variable: 1-based position (row / col / box built-ins)
    int box_h = 3, box_w = 3;
    int nslots = 1;
    bool layered = false;         ///< reads region() / shaded(): decided only once those layers are known
    std::vector<int> gcell;       ///< per variable: its board cell (layer reads)
    int aux_u = 0, aux_n = 0;     ///< aux layout: unknowns [0, aux_u), then layer l's cell c at aux_u + l * aux_n + c
    std::vector<int> aux_read;    ///< the aux variables the rule can read (unknowns named, every layer cell of its cells)
    /// "sum of lin_coef[i] * digit(variable i) + lin_const == unknown lin_u" (lin_u -1: not of that shape): AuxHouse
    std::vector<int> lin_coef;
    long long lin_const = 0;
    int lin_u = -1;
};

constexpr int AUX_UNSET = -2147483647 - 1;  ///< an aux variable without a value yet

/// does the rule hold for these digits (one per variable of the constraint, in variable order)? labels: each
/// variable's region label (1..D, regions to find); shading: each variable's colour (1 shaded, 2 unshaded); null when
/// the rule reads no such layer
bool expr_holds(const ExprProgram& prog, const int* digits, const int* labels = nullptr, const int* shading = nullptr,
                const int* aux = nullptr);  ///< aux: value per aux variable (AUX_UNSET: not known -> ABSENT)
/// does the program call region() (or another layer built-in)?
bool expr_layered(const ExprNode& e);

/// does the rule use region() only to compare regions (== / !=)? Then which cells share a region is all it reads, and a
/// search may name regions freely (partitions instead of labels)
bool expr_region_relational(const ExprNode& e);

/// what a lazy evaluation needs next: the digit (label false) or the region label (label true) of a variable
struct ExprNeed {
    int var;
    bool label;
    bool shade = false;  ///< the variable's colour (shading) is needed
};
/// expr_holds with unknowns: digits[v] < 0 / labels[v] < 0 mark an unknown digit / label; reading one throws
/// ExprNeed{v, label} instead of guessing, so a caller can branch on exactly the values the rule reads (cell values
/// used only as cells, e.g. passed to region(), never need their digit)
bool expr_holds_lazy(const ExprProgram& prog, const int* digits, const int* labels, const int* shading = nullptr);
/// a rule "E == U" (or "U == E") with U one unknown: the side holding U (0 / 1), or -1 for any other rule
int expr_eq_unknown(const ExprProgram& prog);
/// the value of E (the side opposite U) for these digits / unknowns: false when it is not a whole number
bool expr_side_value(const ExprProgram& prog, int side, const int* digits, const int* aux, long long& value);
/// a term's value with one comprehension slot bound to a rule cell (variable var): the value of "f(x)" at that cell
bool expr_slot_value(const ExprProgram& prog, const ExprNode& body, int slot, int var, const int* digits, const int* aux,
                     long long& value);
/// abstract evaluation (absint.cpp): may the rule hold when variable v's digit lies in dmask[v] and aux variable a's
/// value in aux_dom[a] (empty: any)? false is a proof that no filling of these domains satisfies it
bool expr_may_hold(const ExprProgram& prog, const uint32_t* dmask, const std::vector<std::vector<int>>& aux_dom);

/// a rule lemma (rule analysis, absint.cpp): in conjunct conj of the rule, with variable param = value, the case is
/// impossible (kind 0), or decided by the digits of cells (kind 1: the allowed digit tuples, of total)
struct RuleLemma {
    int conj = 0, param = -1, value = 0, kind = 0, total = 0;
    bool negative = false;  ///< from a part saying something does NOT hold ("== false", "not ..."): an absence
    std::vector<int> cells;
    std::vector<std::vector<int>> allowed;
};
/// the rule analysis of one custom rule: its parameters (variables read as a count, index, divisor or range end), each
/// value of each tried over full domains with house knowledge (var_houses: per variable the whole houses it is in, so
/// sums over one house use distinct digits and a whole house its total); dom: per variable its digits
std::vector<RuleLemma> expr_rule_lemmas(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                                        const std::vector<std::vector<int>>& var_houses,
                                        const std::vector<std::vector<int>>& aux_dom);

/// a count in a house (absint.cpp): parts "count(P(x) for x in L [if C]) == k" -- each element's P read abstractly over
/// its digits (dom, per variable) and its unknowns / layer values (aux_dom, per aux variable); when k elements are
/// surely P the others lose what would make P true, when only k can be P they lose what would make it false.
/// digits: (variable, digit) removed; aux: (aux variable, value) removed
/// a count part as a house of its predicate: pred = a hash of the predicate (equal across "each H" instances), k, the
/// elements' variables (-1: not a cell of the rule) and whether each is surely / possibly P
struct CountHouse {
    uint64_t pred = 0;
    int k = 0;
    std::vector<int> vars;
    std::vector<char> sure, poss;
    std::vector<int> exclusive;  ///< other houses of this rule over the same cells whose predicate never holds with this
    std::vector<int> avar;               ///< (with `exclusive`) per element: the one aux variable P reads, else -1
    std::vector<std::vector<int>> pvals; ///< ... and its values that make P possible
};
struct CountMoves {
    std::vector<std::pair<int, int>> digits, aux;
    int count_k = -1;
    bool infeasible = false;  ///< a count can no longer be met (more than k surely, or fewer than k possible)
    bool any = false;         ///< the rule has a count part at all
    std::vector<CountHouse> houses;
};
/// clear: make P false at these variables, in the parts counting predicate `pred` (LayerFish's eliminations)
struct CountQuery {
    uint64_t pred = 0;
    std::vector<int> clear;
};
/// check_only: report any / infeasible / houses, no eliminations (LayerTrial's consequence check); q: only q's clearing
CountMoves expr_count_moves(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                            const std::vector<std::vector<int>>& aux_dom, bool check_only = false,
                            const CountQuery* q = nullptr, bool exclusive = false);

/// the parity of the sum of the rule's nv cells when every odd / even pattern its rule allows gives the same one
/// (an inverted cage: the signed total's parity), else -1; nv <= 10 (absint.cpp)
int expr_sum_parity(const ExprProgram& prog, int D, int nv, const std::vector<std::vector<int>>& aux_dom);

/// a rule "E == U" (U one unknown): the bounds of E over these domains, with house knowledge (sums over one house's
/// cells use distinct digits) -- U lies within them; false when E is unbounded or the rule has another shape
/// "cells side == unknowns side" (the unknowns side reads no cell, e.g. "sum(C) == uD * uD"): the cell side's bounds
/// (house-aware) against each value of each unknown the other side reads -> the (unknown, value) pairs no bound
/// reaches ("columns 7-8 whole and four box-8 cells: 100 to 120 -- only 10 * 10 fits"); house_rest (per p.groups
/// index): the bounds of each house's cells outside the rule ("these 8 cells are 45 minus r1c2: 41 or 44"). false: not
/// that shape
bool expr_unknown_side_cut(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                           const std::vector<std::vector<int>>& var_houses, const std::vector<std::vector<int>>& aux_dom,
                           std::vector<std::pair<int, int>>& cut,
                           const std::vector<std::pair<long long, long long>>* house_rest = nullptr);
bool expr_side_bounds(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                      const std::vector<std::vector<int>>& var_houses, const std::vector<std::vector<int>>& aux_dom,
                      long long& lo, long long& hi);

/// a rule "sum(f(x) for x in L) == U", L cells of one house: per digit mask (bit d - 1 = digit d used), the least /
/// most the sum can be with exactly those digits (lo > hi: impossible); false for any other shape (LayerTrial's
/// multi-rule hypotheses)
bool expr_eq_mask_bounds(const ExprProgram& prog, int D, const std::vector<uint32_t>& dom,
                         const std::vector<std::vector<int>>& var_houses, const std::vector<std::vector<int>>& aux_dom,
                         std::vector<long long>& lo, std::vector<long long>& hi);

/// does the program call shaded()?
bool expr_reads_shading(const ExprNode& e);
/// does the program call region()?
bool expr_reads_regions(const ExprNode& e);

}  // namespace cs
