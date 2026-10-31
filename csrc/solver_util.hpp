// File-local helpers shared by the solver's source files (solver.cpp, direct_view.cpp, notes_view.cpp,
// nary_moves.cpp): k-combinations, innie / outie region records, move descriptors, eliminations. Internal linkage: each
// file that includes this header gets its own copy.
#pragma once
#include <cstdint>
#include <vector>

#include "solver.hpp"

namespace cs {
namespace {
// k-combinations of [0,n) in itertools.combinations order; f(idx) -> stop?
template <class F>
bool for_combos(int n, int k, F&& f) {
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
// region record of an innie / outie set: total, outie, house union, cages, cells
void region_expl(MoveBuf& out, Move& m, const InnieSet& s) {
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
inline void set_meta(Move& m, int a, int b, int c, int d, int e, int f, int g, int h, double sp) {
    m.has_meta = true;
    m.meta[0] = a; m.meta[1] = b; m.meta[2] = c; m.meta[3] = d;
    m.meta[4] = e; m.meta[5] = f; m.meta[6] = g; m.meta[7] = h;
    m.spread = sp;
}
inline void add_elim(MoveBuf& b, Move& m, int c, int v) {
    b.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
    ++m.el_n;
}
}  // namespace
}  // namespace cs
