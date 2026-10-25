// Canonical (symmetry-invariant) helpers: structural spread, invariant labels
// by colour refinement, dedupe-by-cheapest.
#include <algorithm>
#include <cmath>
#include <map>

#include "solver.hpp"

namespace cs {

namespace {
inline uint64_t mixh(uint64_t h, uint64_t x) {
    x *= 0x9e3779b97f4a7c15ULL;
    x ^= x >> 29;
    h ^= x + 0x7f4a7c159e3779b9ULL + (h << 6) + (h >> 2);
    return h;
}
uint64_t hash_sorted(std::vector<uint64_t>& v, uint64_t seed) {
    std::sort(v.begin(), v.end());
    uint64_t h = seed;
    for (uint64_t x : v) h = mixh(h, x);
    return mixh(h, v.size());
}
}  // namespace

double Solver::pspread(const std::vector<int>& cells) const {
    if (!canon) {
        std::vector<std::pair<int, int>> co;
        for (int c : cells) co.push_back(p.coords[c]);
        return shape_ratio(co);
    }
    if (cells.empty()) return 1.0;
    std::vector<int> gs;
    for (int c : cells)
        for (int gi : p.groups_of[c])
            if (p.groups[gi].complete) gs.push_back(gi);
    std::sort(gs.begin(), gs.end());
    gs.erase(std::unique(gs.begin(), gs.end()), gs.end());
    if (gs.empty()) return 1.0;  // no complete house touched (digit-set grids): neutral, not 0 (0^-g = inf)
    return (double)gs.size() / (2.0 * std::sqrt((double)cells.size()) + 1.0);
}

void Solver::compute_labels() {
    if (label_version == version) return;
    label_version = version;
    const int N = p.N;
    std::vector<int> placed_n(33, 0);
    for (int c = 0; c < N; ++c) placed_n[vals[c]]++;
    std::vector<uint64_t> lab(N), nl(N), tmp, inner;
    for (int c = 0; c < N; ++c) {
        if (vals[c]) {
            lab[c] = mixh(0xA11CEULL, (uint64_t)placed_n[vals[c]]);
            continue;
        }
        tmp.clear();
        for (uint32_t m = cand[c]; m; m &= m - 1) {
            int v = lowdigit(m);
            inner.clear();
            for (int gi : p.groups_of[c]) {
                int k = 0;
                for (int q : p.groups[gi].cells) k += !vals[q] && (cand[q] & bit(v));
                inner.push_back(mixh((uint64_t)p.group_cat[gi], (uint64_t)k));
            }
            inner.push_back(mixh(0xD161ULL, (uint64_t)placed_n[v]));
            tmp.push_back(hash_sorted(inner, 0x5EEDULL));
        }
        lab[c] = hash_sorted(tmp, mixh(0xCE11ULL, (uint64_t)popc(cand[c])));
    }
    // structure beyond the groups, digit-relabelling invariant: pair relations (by how many digit
    // pairs they exclude, per direction) and n-ary rules (type, line kind, the cell's role)
    const int D1 = p.D + 1;
    std::vector<std::vector<std::pair<uint64_t, int>>> rel_sig(N);
    for (int c = 0; c < N; ++c)
        for (size_t j = 0; j < p.rel[c].size(); ++j) {
            uint64_t a = 0, b = 0;
            for (int v = 1; v <= p.D; ++v) {
                a += (uint64_t)popc(p.rel_out[c][j * D1 + v]);
                b += (uint64_t)popc(p.rel_in[c][j * D1 + v]);
            }
            rel_sig[c].push_back({mixh(0x4E1ULL + a, b), p.rel[c][j]});
        }
    std::vector<std::vector<std::pair<uint64_t, const NConstraint*>>> nsig(N);
    for (const NConstraint& k : p.nary) {
        const int np = (int)k.pvar.size();
        for (int pos = 0; pos < np; ++pos) {
            uint64_t role = 0;
            if (k.type == NT_ARROW) role = pos < k.ncircle ? 1 : 2;
            if ((k.type == NT_EQSUM || k.type == NT_SAMESET) && !k.seg_start.empty())
                for (size_t sg = 0; sg + 1 < k.seg_start.size(); ++sg)
                    if (pos >= k.seg_start[sg] && pos < k.seg_start[sg + 1])
                        role = 16 + (uint64_t)(k.seg_start[sg + 1] - k.seg_start[sg]) * 64 + (k.seg_start.size() - 1);
            // outside clues read from the clue end: the position matters (x-sum count cell, sandwich ends)
            if (nt_line(k.type) || k.type == NT_FIRSTSEEN) role = 1000 + (uint64_t)pos;
            if (k.type == NT_CONTAINS) role = pos == 0 ? 3 : 4;  // the source cell differs from its targets
            if (k.type == NT_TABLE && k.arity > 0 && pos < k.arity) {  // the column's value histogram (relabel-invariant)
                std::vector<uint64_t> freq(p.D + 1, 0);
                for (size_t r = 0; r * k.arity < k.rows.size(); ++r) {
                    const int v = k.rows[r * k.arity + pos];
                    if (v >= 0 && v <= p.D) ++freq[v];
                }
                role = hash_sorted(freq, 0x7AB1EULL);
            }
            // the clue value, complement-invariant where the fuzzer complements (sums: t <-> n(D+1) - t)
            uint64_t tot = 0;
            if (k.type == NT_SUM && k.totals.empty()) tot = 1 + (uint64_t)std::min(k.total, np * (p.D + 1) - k.total);
            else if (nt_line(k.type)) tot = 1 + (uint64_t)k.total;
            else if (k.type == NT_DISTINCT) tot = 1 + (uint64_t)k.total;
            const uint64_t sig = mixh(mixh(mixh(0xA7ULL + (uint64_t)k.type, (uint64_t)(k.line_kind + 2)),
                                           mixh(role, (uint64_t)np)), tot);
            nsig[k.vars[k.pvar[pos]]].push_back({sig, &k});
        }
    }
    for (int round = 0; round < 3; ++round) {
        for (int c = 0; c < N; ++c) {
            tmp.clear();
            for (int gi : p.groups_of[c]) {
                inner.clear();
                for (int q : p.groups[gi].cells)
                    if (q != c) inner.push_back(lab[q]);
                tmp.push_back(hash_sorted(inner, (uint64_t)p.group_cat[gi] + 77));
            }
            for (auto& rs : rel_sig[c]) tmp.push_back(mixh(rs.first, lab[rs.second]));
            for (auto& ns : nsig[c]) {
                inner.clear();
                for (int q : ns.second->vars)
                    if (q != c) inner.push_back(lab[q]);
                tmp.push_back(hash_sorted(inner, ns.first));
            }
            nl[c] = hash_sorted(tmp, lab[c]);
        }
        lab.swap(nl);
    }
    cell_label = lab;
}

uint64_t Solver::node_label(int c, int v) {
    compute_labels();
    std::vector<uint64_t> gl, inner;
    for (int gi : p.groups_of[c]) {
        inner.clear();
        for (int q : p.groups[gi].cells)
            if (q != c && !vals[q] && (cand[q] & bit(v))) inner.push_back(cell_label[q]);
        gl.push_back(hash_sorted(inner, (uint64_t)p.group_cat[gi] + 1000));
    }
    int placed = 0;
    for (int q = 0; q < p.N; ++q) placed += vals[q] == v;
    return hash_sorted(gl, mixh(cell_label[c], (uint64_t)placed + 31));
}

// one move per placement (any technique) and per (technique, elimination set):
// the cheapest one, so the alternatives do not depend on discovery order
void Solver::canon_dedupe(MoveBuf& b) {
    std::map<std::vector<uint32_t>, size_t> best;
    std::vector<char> keep(b.moves.size(), 0);
    std::vector<uint32_t> key;
    for (size_t i = 0; i < b.moves.size(); ++i) {
        const Move& m = b.moves[i];
        key.clear();
        if (m.pc >= 0) {
            key = {0u, (uint32_t)m.pc, (uint32_t)m.pv};
        } else {
            key.assign(b.elims.begin() + m.el_off, b.elims.begin() + m.el_off + m.el_n);
            std::sort(key.begin(), key.end());
            key.insert(key.begin(), {1u, (uint32_t)m.tech});
        }
        auto it = best.find(key);
        if (it == best.end()) {
            best.emplace(key, i);
            keep[i] = 1;
        } else if (m.d < b.moves[it->second].d - 1e-12) {
            keep[it->second] = 0;
            it->second = i;
            keep[i] = 1;
        }
    }
    size_t w = 0;
    for (size_t i = 0; i < b.moves.size(); ++i)
        if (keep[i]) b.moves[w++] = b.moves[i];
    b.moves.resize(w);
}

}  // namespace cs
