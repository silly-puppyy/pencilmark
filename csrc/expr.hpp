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
    X_NEG, X_INDEX, X_SLICE, X_CALL, X_CALLFN, X_NONE
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
    bool layered = false;         ///< reads region(): decided only with the region labels (a full chaos solution)
};

/// does the rule hold for these digits (one per variable of the constraint, in variable order)? labels: each
/// variable's region label (1..D, regions to find), or null when the rule reads no layer
bool expr_holds(const ExprProgram& prog, const int* digits, const int* labels = nullptr);
/// does the program call region() (or another layer built-in)?
bool expr_layered(const ExprNode& e);

}  // namespace cs
