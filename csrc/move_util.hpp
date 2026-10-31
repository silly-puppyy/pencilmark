// File-local helpers shared by uniqueness.cpp, als.cpp and set_logic.cpp (split from extra.cpp): move descriptors,
// eliminations, and a set that keeps an elimination list from being reported twice. Internal linkage: each file
// that includes this header gets its own copy.
#pragma once
#include <algorithm>
#include <set>
#include <vector>

#include "solver.hpp"

namespace cs {
namespace {
inline void meta9(Move& m, int a, int b, int c, int d, int e, int f, int g, int h, double sp) {
    m.has_meta = true;
    m.meta[0] = a; m.meta[1] = b; m.meta[2] = c; m.meta[3] = d;
    m.meta[4] = e; m.meta[5] = f; m.meta[6] = g; m.meta[7] = h;
    m.spread = sp;
}
inline void add_elim(MoveBuf& b, Move& m, int c, int v) {
    b.elims.push_back((uint32_t)c * 32u + (uint32_t)v);
    ++m.el_n;
}
struct ElimSet {
    std::set<std::vector<uint32_t>> seen;
    bool fresh(std::vector<uint32_t> el, int tag) {
        std::sort(el.begin(), el.end());
        el.push_back((uint32_t)tag);
        return seen.insert(el).second;
    }
};
}  // namespace
}  // namespace cs
