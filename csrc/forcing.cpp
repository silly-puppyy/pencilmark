// Forcing chains (k-way case analysis), up to Sudoku Snake's "Dynamic Unit Nested Forcing
// Chains II":
//   options: every candidate of a cell (cell forcing) or every position of a digit in a
//   house (unit forcing), 2 <= k <= kmax;
//   each option is assumed and propagated; a contradicting branch drops out; what every
//   surviving branch agrees on (a placement, or a candidate no branch keeps) holds; a single
//   survivor is true.
// Propagation level inside the branches:
//   0 (FORCING): basic propagation (singles, pair relations, rule consistency) to a fixpoint;
//   1 (DYN_FORCING): + the engine's own techniques up to a tier ceiling (dynamic chains);
//   2 (NESTED_FORCING): + level-1 forcing chains inside the branches (nested II).
// Priced by level, branching and propagation size (Params::difficulty) through the soft cap.
#include <algorithm>
#include "portable.hpp"
#include <cstring>
#include <set>
#include <unordered_map>
#include <string>

#include "solver.hpp"

namespace cs {

namespace {
bool fc_skip(const char* n) {
    // never inside a branch: uniqueness arguments, case splits, the forcing tiers themselves
    static const char* bad[] = {"ur", "xur", "bug", "shorttrial", "eitherway", "trial", "forcing", "dynforcing",
                                "nestedforcing", "nishio", "gurth", "pom", "whatif", "humancase"};
    for (const char* b : bad)
        if (!std::strcmp(n, b)) return true;
    return false;
}
}  // namespace

// Propagate the current (hypothetical) state at `level`. Returns 0, or 1 + the iteration of the
// first contradiction. steps: placements + technique applications; log: EV_* events.
int Solver::fc_propagate(int level, int& steps, std::vector<int>* log) {
    for (int it = 0; it < 200; ++it) {
        int placed = 0;
        const int r = prop_rounds(1000, placed, log);
        steps += placed;
        ++version;
        if (r) return it + 1;
        if (level <= 0) return 0;
        MoveBuf b;
        bool found = false;
        const int ceiling = fc_ceiling_now >= 0 ? fc_ceiling_now : P.fc_ceiling;
        if (fc_step_cap && steps > fc_step_cap) return 0;  // bounded (human what-if): stop following
        for (size_t ti = 0; ti < tiers.size() && (int)ti <= ceiling && !found; ++ti) {
            b.clear();
            for (auto& s : tiers[ti])
                if (!fc_skip(s->name())) s->collect(*this, b);
            filter(b);
            found = !b.moves.empty();
        }
        if (!found && level >= 2) {
            b.clear();
            forcing(b, level - 1, true);
            filter(b);
            found = !b.moves.empty();
        }
        if (!found) return 0;
        std::vector<std::pair<int, int>> pl;
        for (const Move& m : b.moves) {
            for (int k = 0; k < m.el_n; ++k) {
                uint32_t e = b.elims[m.el_off + k];
                cand[e / 32] &= ~bit((int)(e % 32));
            }
            if (m.pc >= 0) pl.push_back({m.pc, m.pv});
            if (log) log->insert(log->end(), {EV_TECH, it + 1, m.pc, m.tech, m.el_n});
            ++steps;
        }
        std::sort(pl.begin(), pl.end());
        pl.erase(std::unique(pl.begin(), pl.end()), pl.end());
        for (auto& cv : pl) {
            if (vals[cv.first] == cv.second) continue;
            if (vals[cv.first] || !(cand[cv.first] & bit(cv.second))) {
                if (log) log->insert(log->end(), {EV_X_CLASH, it + 1, cv.first, cv.second, -1});
                ++version;
                return it + 1;
            }
            place(cv.first, cv.second);
        }
        ++version;
    }
    return 0;
}

// one branch: assume (c, v), propagate; final state into ov / oc. Returns the contradiction
// iteration (0: none); state restored.
int Solver::fc_branch(int c, int v, int level, int& steps, std::vector<uint8_t>* ov, std::vector<uint32_t>* oc,
                      std::vector<int>* log) {
    std::vector<uint8_t> sv = vals;
    std::vector<uint32_t> sc = cand, sg = placed_g;
    ++version;
    place(c, v);
    steps = 0;
    const int r = fc_propagate(level, steps, log);
    if (ov) *ov = vals;
    if (oc) *oc = cand;
    vals.swap(sv);
    cand.swap(sc);
    placed_g.swap(sg);
    ++version;
    return r;
}

void Solver::forcing(MoveBuf& out, int level, bool nested) {
    static const int TECH0[3] = {FORCING, DYN_FORCING, NESTED_FORCING};
    if (level < 0 || level > 2) return;
    const int tech = fc_tech_now >= 0 ? fc_tech_now : TECH0[level];
    if (disabled[tech]) return;
    if (!nested && fc_tech_now < 0 && level > (fc_level_now >= 0 ? fc_level_now : P.fc_level)) return;
    const int kmax = fc_kmax_now >= 0 ? fc_kmax_now : P.fc_kmax[level];
    struct Opt { int c, v; };
    std::vector<std::pair<std::vector<Opt>, int>> sets;  // options, unit (0 cell / 1 unit)
    for (int c = 0; c < p.N; ++c) {
        const int k = vals[c] ? 0 : popc(cand[c]);
        if (k < 2 || k > kmax) continue;
        std::vector<Opt> o;
        for (uint32_t m = cand[c]; m; m &= m - 1) o.push_back({c, lowdigit(m)});
        sets.push_back({o, 0});
    }
    for (int hi : p.houses)
        for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
            const int v = lowdigit(mm);
            std::vector<Opt> o;
            for (int c : p.groups[hi].cells)
                if (!vals[c] && (cand[c] & bit(v))) o.push_back({c, v});
            if ((int)o.size() >= 2 && (int)o.size() <= kmax) sets.push_back({o, 1});
        }
    {  // bounded, all-or-none (invariant): skip when the branch work exceeds the budget
        double branches = 0;
        for (auto& st : sets) branches += (double)st.first.size();
        double rules = (double)p.cage_nary.size();  // propagation skips leftover equalities
        for (const NConstraint& k : p.nary) rules += k.type != NT_SAMESET;
        const double per = (double)p.N + 8.0 * rules;
        if (branches * per > P.fc_work) return;
    }
    std::set<std::vector<uint32_t>> seen;
    std::vector<std::vector<uint8_t>> fv;
    std::vector<std::vector<uint32_t>> fcand;
    // every branch starts from this same state, and the same assumption (c, v) appears in a cell set
    // and in up to three house sets: propagate each assumption once (identical result by construction)
    struct Branch { int dead, steps; std::vector<uint8_t> v; std::vector<uint32_t> c; };
    std::unordered_map<uint32_t, Branch> memo;
    for (auto& st : sets) {
        const std::vector<Opt>& opts = st.first;
        const int k = (int)opts.size();
        fv.assign(k, {});
        fcand.assign(k, {});
        std::vector<char> dead(k, 0);
        int steps = 0, nsurv = 0, ncontra = 0;
        for (int i = 0; i < k; ++i) {
            const uint32_t key = (uint32_t)opts[i].c * 32u + (uint32_t)opts[i].v;
            auto it = memo.find(key);
            if (it == memo.end()) {
                Branch b;
                b.steps = 0;
                b.dead = fc_branch(opts[i].c, opts[i].v, level, b.steps, &b.v, &b.c) != 0;
                it = memo.emplace(key, std::move(b)).first;
            }
            dead[i] = (char)it->second.dead;
            fv[i] = it->second.v;
            fcand[i] = it->second.c;
            const int s = it->second.steps;
            steps += s;
            fc_steps_total += s;
            if (fc_abort_at >= 0 && fc_steps_total > fc_abort_at) {  // fallback budget: all-or-none per call
                fc_aborted = true;
                return;
            }
            if (dead[i]) ++ncontra;
            else ++nsurv;
        }
        if (!nsurv) continue;  // inconsistent state (left to the solver's other means)
        std::vector<int> pat;
        for (auto& o : opts)
            if (std::find(pat.begin(), pat.end(), o.c) == pat.end()) pat.push_back(o.c);
        for (int x = 0; x < p.N; ++x) {
            if (vals[x]) continue;
            int d = -1;
            uint32_t keep = 0;
            for (int i = 0; i < k; ++i) {
                if (dead[i]) continue;
                const int dv = fv[i][x];
                if (d == -1) d = dv;
                else if (d != dv) d = 0;
                keep |= dv ? bit(dv) : fcand[i][x];
            }
            if (d < 0) d = 0;
            const uint32_t gone = cand[x] & ~keep;
            if (!d && !gone) continue;
            if (!canon) {
                std::vector<uint32_t> key{(uint32_t)x, (uint32_t)d, d ? 0u : gone, (uint32_t)level};
                if (!seen.insert(key).second) continue;
            }
            Move& m = new_move(out, tech, 1.0, k);
            if (d) {
                m.pc = x;
                m.pv = d;
            } else {
                for (uint32_t g = gone; g; g &= g - 1) {
                    out.elims.push_back((uint32_t)x * 32u + (uint32_t)lowdigit(g));
                    ++m.el_n;
                }
            }
            std::vector<int> pc = pat;
            if (std::find(pc.begin(), pc.end(), x) == pc.end()) pc.push_back(x);
            set_pattern(out, m, pc);
            {
                std::vector<int> rec{fc_view >= 0 ? fc_view : 10 + level, k};
                for (auto& o : opts) {
                    rec.push_back(o.c);
                    rec.push_back(o.v);
                }
                add_expl(out, m, EX_TRIAL, rec);
            }
            m.has_meta = true;
            m.meta[0] = std::min(p.N, (int)pc.size() + steps);  // cells followed over all branches
            m.meta[1] = k;
            m.meta[2] = st.second ? 1 : k;
            m.meta[3] = 2 * (level + 1);  // links: nesting depth (small: linear in the meta-theta exponent);
                                          // the propagation size is in meta[0] (cells) and xm[4] (steps)
            m.meta[4] = st.second;
            m.meta[5] = 0;
            m.meta[6] = 0;
            m.meta[7] = 1;
            m.spread = pspread(pc);
            m.code = tech == WHAT_IF ? 3441 + st.second : 3401 + 10 * level + st.second;
            if (tech == WHAT_IF) m.meta[7] = fc_view == 14 ? 0 : 1;  // no notes in the direct view
            pm_long xm[XM_N] = {level, k, st.second, nsurv, steps, ncontra, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

}  // namespace cs

namespace cs {

// Nishio (single-digit forcing net): assume digit v at cell c and follow only digit v (placements
// remove v from peers; a house with one place left for v takes it); a house left with no place
// for v refutes the assumption.
void Solver::nishio(MoveBuf& out) {
    if (disabled[NISHIO]) return;
    const int N = p.N;
    for (int v = 1; v <= p.D; ++v) {
        const uint32_t b = bit(v);
        std::vector<char> base(N, 0);
        for (int c = 0; c < N; ++c) base[c] = !vals[c] && (cand[c] & b);
        for (int c0 = 0; c0 < N; ++c0) {
            if (!base[c0]) continue;
            std::vector<char> can = base;
            std::vector<char> on(N, 0);
            uint32_t dummy = 0;
            (void)dummy;
            std::vector<int> todo{c0};
            int rounds = 0, placed = 0, bad_house = -1;
            while (!todo.empty() && bad_house < 0 && rounds < 30) {
                ++rounds;
                for (int x : todo) {
                    if (on[x]) continue;
                    on[x] = 1;
                    can[x] = 0;
                    ++placed;
                    for (int q : p.peer_list[x]) can[q] = 0;
                }
                todo.clear();
                for (int hi : p.houses) {
                    if (placed_g[hi] & b) continue;
                    int n = 0, at = -1;
                    bool has = false;
                    for (int x : p.groups[hi].cells) {
                        if (on[x]) has = true;
                        else if (can[x]) ++n, at = x;
                    }
                    if (has) continue;
                    if (n == 0) {
                        bad_house = hi;
                        break;
                    }
                    if (n == 1) todo.push_back(at);
                }
                std::sort(todo.begin(), todo.end());
                todo.erase(std::unique(todo.begin(), todo.end()), todo.end());
                // two placements seeing each other: contradiction
                for (size_t i = 0; i < todo.size() && bad_house < 0; ++i)
                    for (size_t j = i + 1; j < todo.size(); ++j)
                        if (tbit(p.peers(todo[i]), todo[j])) {
                            bad_house = -2;
                            break;
                        }
            }
            if (bad_house == -1) continue;
            Move& m = new_move(out, NISHIO, 1.0, rounds);
            out.elims.push_back((uint32_t)c0 * 32u + (uint32_t)v);
            ++m.el_n;
            std::vector<int> pc{c0};
            for (int x = 0; x < N; ++x)
                if (on[x] && x != c0) pc.push_back(x);
            set_pattern(out, m, pc);
            if (bad_house >= 0) add_expl(out, m, EX_BASE, {bad_house});
            m.has_meta = true;
            m.meta[0] = std::min(N, (int)pc.size() + 1);
            m.meta[1] = 2;
            m.meta[2] = 1;
            m.meta[3] = std::min(rounds, 12);
            m.meta[4] = 1;
            m.meta[5] = 0;
            m.meta[6] = 0;
            m.meta[7] = 1;
            m.spread = pspread(pc);
            m.code = 3431;
            pm_long xm[XM_N] = {v, rounds, placed, bad_house, 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        }
    }
}

}  // namespace cs

namespace cs {

// Human "what if": a two-way choice (bivalue cell or a digit with two places in a house), each case
// followed with light logic (singles, rule arithmetic, intersections: tiers up to "locked") for at
// most 40 steps; a case that breaks drops, otherwise what both cases agree on holds. Direct view:
// on the no-notes mental view.
void Solver::what_if(MoveBuf& out, bool direct_view) {
    if (disabled[WHAT_IF]) return;
    std::vector<uint32_t> saved;
    if (direct_view) {
        compute_mental(3);
        saved = cand;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) cand[c] = md[c];
        ++version;
    }
    fc_ceiling_now = 2;
    fc_kmax_now = 2;
    fc_tech_now = WHAT_IF;
    fc_step_cap = 40;
    fc_view = direct_view ? 14 : 13;
    forcing(out, 1, true);
    fc_ceiling_now = fc_kmax_now = fc_tech_now = fc_view = -1;
    fc_step_cap = 0;
    if (direct_view) {
        cand = saved;
        ++version;
        label_version = -1;
        // direct view: placements only
        size_t w = 0;
        for (size_t i = 0; i < out.moves.size(); ++i)
            if (out.moves[i].tech != WHAT_IF || out.moves[i].pc >= 0) out.moves[w++] = out.moves[i];
        out.moves.resize(w);
    }
}

// Notes logic done in the head: on the no-notes mental view, the notes tiers up to "pairs" (rule
// combinations, intersections, pairs) are applied; a cell / house left with one digit is a single.
void Solver::mental_notes(MoveBuf& out) {
    if (disabled[MENTAL_NOTES]) return;
    compute_mental(3);
    const std::vector<uint32_t> saved = cand;
    for (int c = 0; c < p.N; ++c)
        if (!vals[c]) cand[c] = md[c];
    ++version;
    MoveBuf b;
    for (size_t ti = 1; ti < tiers.size() && ti <= 3; ++ti)
        for (auto& s : tiers[ti])
            if (std::string(s->name()) != "ur" && std::string(s->name()) != "bug" && std::string(s->name()) != "xur" &&
                std::string(s->name()) != "gurth")
                s->collect(*this, b);
    filter(b);
    const std::vector<uint32_t> view = cand;
    cand = saved;
    ++version;
    label_version = -1;
    // each elimination move separately: the singles it enables (Jacobi: independent of the order)
    std::set<std::pair<int, int>> done;
    for (const Move& em : b.moves) {
        if (!em.el_n || em.tech == WHAT_IF) continue;
        std::vector<uint32_t> v2 = view;
        std::vector<int> touched;
        for (int k = 0; k < em.el_n; ++k) {
            const uint32_t e = b.elims[em.el_off + k];
            v2[e / 32] &= ~bit((int)(e % 32));
            touched.push_back((int)(e / 32));
        }
        auto emit = [&](int c, int v, int house) {
            if (!canon && !done.insert({c, v}).second) return;
            Move& m = new_move(out, MENTAL_NOTES, em.shape, em.tech);
            m.pc = c;
            m.pv = v;
            std::vector<int> pc(b.pats.begin() + em.pat_off, b.pats.begin() + em.pat_off + em.pat_n);
            pc.push_back(c);
            set_pattern(out, m, pc);
            if (house >= 0) {
                m.nk = NM_GROUP;
                m.na = house;
            }
            m.has_meta = true;
            std::copy(em.meta, em.meta + 8, m.meta);
            m.meta[0] = std::min(p.N, em.meta[0] + 1);
            m.meta[7] = 0;
            m.spread = em.spread;
            m.code = 3451;
            pm_long xm[XM_N] = {em.tech, em.el_n, house >= 0, 0, 0, 0, 0, 0, 0, 0};
            std::copy(xm, xm + XM_N, m.xm);
        };
        for (int c : touched)
            if (!vals[c] && popc(v2[c]) == 1 && popc(view[c]) > 1) emit(c, lowdigit(v2[c]), -1);
        std::vector<int> hs;
        for (int c : touched)
            for (int gi : p.groups_of[c])
                if (p.groups[gi].complete) hs.push_back(gi);
        std::sort(hs.begin(), hs.end());
        hs.erase(std::unique(hs.begin(), hs.end()), hs.end());
        for (int hi : hs)
            for (uint32_t mm = p.full & ~placed_g[hi]; mm; mm &= mm - 1) {
                const uint32_t bb = mm & (~mm + 1);
                int n1 = 0, n2 = 0, at = -1;
                for (int c : p.groups[hi].cells) {
                    if (vals[c]) continue;
                    n1 += (view[c] & bb) != 0;
                    if (v2[c] & bb) ++n2, at = c;
                }
                if (n2 == 1 && n1 > 1) emit(at, lowdigit(bb), hi);
            }
    }
}

}  // namespace cs
