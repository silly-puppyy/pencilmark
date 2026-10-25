// Rollouts of the human-mode race from one state to the next placement (dwell-model data; coordinator Step B).
// From a trace state (filled cells, candidate view, written marks) each of K rollouts repeatedly enumerates
// every move at the state (as state_moves: priced, described with the state's own marks), picks one by a
// softmax over -d / T (or over rate_w . x / T with a caller's rate model) and applies it, until a placement,
// max_moves or no move. TakeNotes is a move in the direct phase (writes every candidate, switches to notes).
// Eliminations erase written marks; eliminating an unwritten candidate counts as held_mental (kept in mind).
// Visited states are enumerated once (hash of vals, candidates, written marks, phase); every visited
// state's move list can be returned. Deterministic for a given seed (one RNG stream per rollout).
#include <algorithm>
#include "portable.hpp"
#include <cmath>
#include <mutex>
#include <unordered_map>

#include "solver.hpp"

namespace cs {

namespace {
uint64_t mix64(uint64_t h, uint64_t v) {
    h ^= v + 0x9E3779B97F4A7C15ULL + (h << 6) + (h >> 2);
    return h * 0x100000001B3ULL;
}
}  // namespace

// one enumerated state: its move rows live in RollOut's flat arrays [row0, row0 + n)
int Solver::roll_state(int phase, RollOut& out, std::mutex& mu, std::unordered_map<uint64_t, int>& cache,
                       uint64_t& hash_out) {
    uint64_t h = 1469598103934665603ULL ^ (uint64_t)phase;
    for (int c = 0; c < p.N; ++c) {
        h = mix64(h, ((uint64_t)vals[c] << 40) ^ ((uint64_t)cand[c] << 8));
        h = mix64(h, (uint64_t)written_override[c]);
    }
    hash_out = h;
    {
        std::lock_guard<std::mutex> lk(mu);
        auto it = cache.find(h);
        if (it != cache.end()) return it->second;
    }
    ++version;
    compute_empties();
    band_spent = band_total = 0;  // per-solve caps would make a state's list depend on which rollout enumerated it
    band_sols.clear();            // ... as would fillings remembered from earlier states (they change search costs,
    band_sols_wide.clear();       // hence which searches finish within budget)
    band_cache.clear();           // cache hits cost no budget: earlier states would free budget for later regions
    band_cache_wide.clear();
    MoveBuf b;
    collect_all(b, phase == 0);
    filter(b);
    if (p.is_derived) tag_implied(b, 0);
    desc_mode = phase;
    for (Move& m : b.moves) {
        cog_loads(m, b);
        if (canon) describe(m, b);
        m.d = P.difficulty(m, b.covers.data(), p.D);
    }
    if (canon) canon_dedupe(b);
    if (phase == 0 && !disabled[TAKE_NOTES] && !empties.empty()) {  // writing notes is a move too
        Move& m = new_move(b, TAKE_NOTES, 1.0, 0);
        m.d = P.B[TAKE_NOTES];
        pm_long un = 0;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) un += popc(cand[c] & ~written_override[c]);
        m.scan = 1.0;
        m.desc[6] = std::log1p((double)un);  // what would be written
        m.has_desc = true;
    }
    std::lock_guard<std::mutex> lk(mu);
    auto it = cache.find(h);
    if (it != cache.end()) return it->second;
    const int sid = (int)out.st_hash.size();
    out.st_hash.push_back(h);
    out.st_row0.push_back((int)out.mv_tech.size());
    out.st_n.push_back((int)b.moves.size());
    out.st_phase.push_back(phase);
    for (const Move& m : b.moves) {
        out.mv_tech.push_back(m.tech);
        out.mv_code.push_back(m.code);
        out.mv_d.push_back(m.d);
        out.mv_pc.push_back(m.pc);
        out.mv_pv.push_back(m.pv);
        out.mv_nel.push_back(m.el_n);
        out.mv_el0.push_back((int)out.el.size());
        for (int i = 0; i < m.el_n; ++i) out.el.push_back(b.elims[m.el_off + i]);
        double x[10] = {0};
        if (m.has_meta) meta_vector(m, x);
        for (int j = 0; j < 10; ++j) out.mv_x.push_back(x[j]);
        for (int j = 0; j < 8; ++j) out.mv_x.push_back(m.has_desc ? m.desc[j] : 0.0);
        out.mv_x.push_back(std::log1p(std::max(0.0, m.scan)));
    }
    cache.emplace(h, sid);
    return sid;
}

void Solver::roll_place(const std::vector<std::pair<int, int>>& givens, const RollSpec& sp, int rollout, RollOut& out,
                        std::mutex& mu, std::unordered_map<uint64_t, int>& cache, std::vector<RollStep>& steps) {
    init_state(givens);
    written_override = sp.written;
    if ((int)written_override.size() != p.N) written_override.assign(p.N, 0u);
    for (int c = 0; c < p.N; ++c) written_override[c] &= vals[c] ? 0u : cand[c];
    int phase = sp.phase;
    if (phase < 0) {
        phase = 0;
        for (int c = 0; c < p.N; ++c) phase |= written_override[c] != 0;
    }
    uint64_t rng = (sp.seed + 0x9E3779B97F4A7C15ULL * (uint64_t)(rollout + 1)) | 1ULL;
    auto uni = [&]() {
        rng ^= rng >> 12, rng ^= rng << 25, rng ^= rng >> 27;
        return (double)((rng * 0x2545F4914F6CDD1DULL) >> 11) / 9007199254740992.0;
    };
    pm_long held_mental = 0;
    const int nx = 19;
    for (int k = 0; k < sp.max_moves; ++k) {
        bool empty_cells = false;
        for (int c = 0; c < p.N && !empty_cells; ++c) empty_cells = !vals[c];
        if (!empty_cells) break;
        uint64_t h = 0;
        const int sid = roll_state(phase, out, mu, cache, h);
        // selection under the lock: other threads may append rows (vector reallocation) meanwhile
        int row, tech, pc, pv;
        std::vector<uint32_t> els;
        {
            std::lock_guard<std::mutex> lk(mu);
            const int r0 = out.st_row0[sid], n = out.st_n[sid];
            if (n == 0) break;
            std::vector<double> lg(n);
            double mx = -1e300;
            const double T = sp.temperature;
            for (int i = 0; i < n; ++i) {
                double u;
                if (!sp.rate_w.empty()) {
                    u = 0;
                    const double* x = &out.mv_x[(size_t)(r0 + i) * nx];
                    for (int j = 0; j < nx && j < (int)sp.rate_w.size(); ++j) u += sp.rate_w[j] * x[j];
                    if ((int)sp.rate_w.size() > nx) u += sp.rate_w[nx];  // optional global intercept
                } else {
                    u = -out.mv_d[r0 + i];
                }
                lg[i] = u;
                mx = std::max(mx, u);
            }
            int pick = 0;
            if (T <= 1e-9) {
                for (int i = 1; i < n; ++i)
                    if (lg[i] > lg[pick]) pick = i;
            } else {
                double z = 0;
                for (double& v : lg) z += (v = std::exp((v - mx) / T));
                const double r = uni() * z;
                double acc = 0;
                pick = n - 1;
                for (int i = 0; i < n; ++i)
                    if ((acc += lg[i]) >= r) {
                        pick = i;
                        break;
                    }
            }
            row = r0 + pick;
            tech = out.mv_tech[row];
            pc = out.mv_pc[row];
            pv = out.mv_pv[row];
            els.assign(out.el.begin() + out.mv_el0[row], out.el.begin() + out.mv_el0[row] + out.mv_nel[row]);
        }
        RollStep rs;
        rs.rollout = rollout;
        rs.k = k;
        rs.state = sid;
        rs.hash = h;
        rs.row = row;
        rs.n_empty = 0;
        rs.n_cands = 0;
        for (int c = 0; c < p.N; ++c)
            if (!vals[c]) ++rs.n_empty, rs.n_cands += popc(cand[c]);
        rs.held_mental = held_mental;
        steps.push_back(rs);
        // apply
        if (tech == TAKE_NOTES) {
            for (int c = 0; c < p.N; ++c) written_override[c] = vals[c] ? 0u : cand[c];
            phase = 1;
            continue;
        }
        ++version;
        for (const uint32_t e : els) {
            const int c = (int)(e / 32), d = (int)(e % 32);
            if (!(cand[c] & bit(d))) continue;
            if (written_override[c] & bit(d)) written_override[c] &= ~bit(d);  // erased mark
            else ++held_mental;                                                // knowledge kept in mind
            cand[c] &= ~bit(d);
        }
        if (pc >= 0) {
            place(pc, pv);
            for (int c = 0; c < p.N; ++c) written_override[c] &= vals[c] ? 0u : cand[c];
            break;  // first placement ends the rollout
        }
    }
    written_override.clear();
}

}  // namespace cs
