#include <pybind11/numpy.h>
#include "portable.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <atomic>
#include <stdexcept>
#include <string>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>

#include "model.hpp"
#include "solver.hpp"

namespace py = pybind11;
using namespace cs;

static const int CMAX = 10;

static Params params_from(const py::dict& P) {
    Params pr;
    py::dict B = P["B"].cast<py::dict>();
    for (auto kv : B) {
        int t = kv.first.cast<int>();
        if (t >= 0 && t < N_TECH) pr.B[t] = kv.second.cast<double>();
    }
    pr.K = P["K"].cast<std::vector<double>>();
    pr.gamma = P["gamma"].cast<double>();
    pr.alpha = P["alpha"].cast<double>();
    if (P.contains("tech_offset") && !P["tech_offset"].is_none())
        for (auto kv : P["tech_offset"].cast<py::dict>()) {
            int t = py::int_(py::reinterpret_borrow<py::object>(kv.first)).cast<int>();
            if (t >= 0 && t < N_TECH) {
                pr.tech_offset[t] = kv.second.cast<double>();
                pr.has_offset[t] = true;
            }
        }
    if (P.contains("cap_tau") && !P["cap_tau"].is_none()) pr.cap_tau = P["cap_tau"].cast<double>();
    if (P.contains("cap_pow") && !P["cap_pow"].is_none()) pr.cap_pow = P["cap_pow"].cast<double>();
    if (P.contains("human_mode") && !P["human_mode"].is_none()) {
        pr.human = true;
        py::dict hm = P["human_mode"].cast<py::dict>();
        if (hm.contains("budget")) {
            auto v = hm["budget"].cast<std::vector<double>>();
            for (size_t j = 0; j < v.size() && j < 8; ++j) pr.hbudget[j] = v[j];
        }
        if (hm.contains("k")) {
            auto v = hm["k"].cast<std::vector<double>>();
            for (size_t j = 0; j < v.size() && j < 8; ++j) pr.hk[j] = v[j];
        }
    }
    if (P.contains("forcing_level") && !P["forcing_level"].is_none()) pr.fc_level = P["forcing_level"].cast<int>();
    if (P.contains("forcing_fallback") && !P["forcing_fallback"].is_none()) pr.fc_fallback = P["forcing_fallback"].cast<pm_long>();
    if (P.contains("exhaust_fallback") && !P["exhaust_fallback"].is_none()) pr.exhaust_fallback = P["exhaust_fallback"].cast<int>();
    if (P.contains("fish_max_n") && !P["fish_max_n"].is_none()) pr.fish_max_n = P["fish_max_n"].cast<int>();
    if (P.contains("band_escalate") && !P["band_escalate"].is_none()) pr.band_escalate = P["band_escalate"].cast<int>();
    if (P.contains("band_wide_cells") && !P["band_wide_cells"].is_none()) pr.band_wide_cells = P["band_wide_cells"].cast<int>();
    if (P.contains("band_wide_max") && !P["band_wide_max"].is_none()) pr.band_wide_max = P["band_wide_max"].cast<int>();
    if (P.contains("band_wide_rules") && !P["band_wide_rules"].is_none()) pr.band_wide_rules = P["band_wide_rules"].cast<int>();
    if (P.contains("band_outies") && !P["band_outies"].is_none()) pr.band_outies = P["band_outies"].cast<int>();
    if (P.contains("colour_partial") && !P["colour_partial"].is_none()) pr.colour_partial = P["colour_partial"].cast<int>();
    if (P.contains("band_wide_factor") && !P["band_wide_factor"].is_none()) pr.band_wide_factor = P["band_wide_factor"].cast<int>();
    if (P.contains("band_escalate_max") && !P["band_escalate_max"].is_none())
        pr.band_escalate_max = P["band_escalate_max"].cast<int>();
    if (P.contains("forcing_fallback_s") && !P["forcing_fallback_s"].is_none())
        pr.fc_fallback_s = P["forcing_fallback_s"].cast<double>();
    if (P.contains("forcing_ceiling") && !P["forcing_ceiling"].is_none())
        pr.fc_ceiling = P["forcing_ceiling"].cast<int>();
    if (P.contains("forcing_kmax") && !P["forcing_kmax"].is_none()) {
        auto v = P["forcing_kmax"].cast<std::vector<int>>();
        for (size_t j = 0; j < v.size() && j < 3; ++j) pr.fc_kmax[j] = v[j];
    }
    if (P.contains("forcing_depth") && !P["forcing_depth"].is_none()) pr.fc_depth = P["forcing_depth"].cast<double>();
    if (P.contains("forcing_work") && !P["forcing_work"].is_none()) pr.fc_work = P["forcing_work"].cast<double>();
    if (P.contains("gurth") && !P["gurth"].is_none()) pr.gurth = P["gurth"].cast<bool>();
    if (P.contains("forcing_branch") && !P["forcing_branch"].is_none())
        pr.fc_branch = P["forcing_branch"].cast<double>();
    auto getd = [&](const char* k, double& dst) {
        if (P.contains(k) && !P[k].is_none()) dst = P[k].cast<double>();
    };
    getd("t0", pr.t0);
    getd("t_mark", pr.t_mark);
    getd("beta", pr.beta);
    getd("c", pr.c_time);
    getd("t_place", pr.t_place);
    getd("t_erase", pr.t_erase);
    getd("tau", pr.tau);
    getd("ref_steps", pr.ref_steps);
    if (P.contains("meta_max_tech") && !P["meta_max_tech"].is_none()) pr.meta_max_tech = P["meta_max_tech"].cast<int>();
    if (P.contains("meta_exclude") && !P["meta_exclude"].is_none())
        for (int t : P["meta_exclude"].cast<std::vector<int>>())
            if (t >= 0 && t < N_TECH) pr.meta_excl[t] = true;
    getd("guess_k", pr.guess_k);
    getd("colour_chain_k", pr.colour_chain_k);
    getd("band_k", pr.band_k);
    getd("k_tab", pr.k_tab);
    if (P.contains("notes_mode") && !P["notes_mode"].is_none()) pr.snyder = P["notes_mode"].cast<std::string>() == "snyder";
    if (P.contains("snyder_max") && !P["snyder_max"].is_none()) pr.snyder_max = std::max(2, std::min(3, P["snyder_max"].cast<int>()));
    if (P.contains("notes_lazy") && !P["notes_lazy"].is_none()) pr.notes_lazy = P["notes_lazy"].cast<bool>();
    if (P.contains("mental_floor") && !P["mental_floor"].is_none()) pr.mental_floor = P["mental_floor"].cast<bool>();
    if (P.contains("theta_full_v2") && !P["theta_full_v2"].is_none()) pr.theta_full_v2 = P["theta_full_v2"].cast<bool>();
    if (P.contains("dc_lines") && !P["dc_lines"].is_none()) pr.dc_lines = P["dc_lines"].cast<bool>();
    if (P.contains("case_rounds") && !P["case_rounds"].is_none()) pr.case_rounds = P["case_rounds"].cast<int>();
    if (P.contains("case_cands") && !P["case_cands"].is_none()) pr.case_cands = P["case_cands"].cast<int>();
    if (P.contains("case_light") && !P["case_light"].is_none()) pr.case_light = P["case_light"].cast<int>();
    if (P.contains("route") && !P["route"].is_none()) pr.sets_first = P["route"].cast<std::string>() == "sets_first";
    if (P.contains("ri_budget") && !P["ri_budget"].is_none()) pr.ri_budget = P["ri_budget"].cast<pm_long>();
    if (P.contains("band_budget") && !P["band_budget"].is_none()) pr.band_budget = P["band_budget"].cast<pm_long>();
    if (P.contains("guess_time_unit") && !P["guess_time_unit"].is_none())
        pr.guess_time_median = P["guess_time_unit"].cast<std::string>() == "median";
    if (P.contains("guess_time_linear") && !P["guess_time_linear"].is_none())
        pr.guess_time_linear = P["guess_time_linear"].cast<double>();
    getd("trial_k", pr.trial_k);
    if (P.contains("guess_deep") && !P["guess_deep"].is_none()) pr.guess_deep = P["guess_deep"].cast<int>();
    if (P.contains("meta_theta_arith_cells") && !P["meta_theta_arith_cells"].is_none())
        pr.theta_ac = P["meta_theta_arith_cells"].cast<double>();
    if (P.contains("meta_theta_full") && !P["meta_theta_full"].is_none())
        pr.theta_full = P["meta_theta_full"].cast<std::vector<double>>();
    if (P.contains("meta_theta_enum") && !P["meta_theta_enum"].is_none()) pr.theta_enum = P["meta_theta_enum"].cast<double>();
    if (P.contains("locality") && !P["locality"].is_none()) pr.locality = P["locality"].cast<double>();
    if (P.contains("meta_theta_interact") && !P["meta_theta_interact"].is_none())
        pr.theta_interact = P["meta_theta_interact"].cast<std::vector<double>>();
    if (P.contains("tech_obscurity") && !P["tech_obscurity"].is_none())
        pr.tech_obsc = P["tech_obscurity"].cast<std::vector<double>>();
    if (P.contains("meta_theta") && !P["meta_theta"].is_none()) {
        pr.theta = P["meta_theta"].cast<std::vector<double>>();
        pr.has_theta = true;
    }
    return pr;
}

static NSpec parse_constraint(const py::dict& d) {
    NSpec s;
    std::string t = d["type"].cast<std::string>();
    auto cells = [&](const char* key) { return d[key].cast<std::vector<int>>(); };
    if (t == "sum" && d.contains("total") && py::isinstance<py::list>(d["total"])) {  // unknown total from a set
        s.type = NT_SUM;
        s.a = cells("cells");
        s.totals = d["total"].cast<std::vector<int>>();
        s.total = s.totals.empty() ? 0 : s.totals[0];
        if (d.contains("distinct") && !d["distinct"].is_none()) s.distinct = d["distinct"].cast<bool>() ? 1 : 0;
    } else if (t == "sum") {
        s.type = NT_SUM;
        s.a = cells("cells");
        s.total = d["total"].cast<int>();
        if (d.contains("distinct") && !d["distinct"].is_none()) s.distinct = d["distinct"].cast<bool>() ? 1 : 0;
    } else if (t == "arrow") {
        s.type = NT_ARROW;
        s.a = cells("circle");
        s.segs.push_back(cells("line"));
    } else if (t == "equal_sum") {
        s.type = NT_EQSUM;
        s.segs = d["segments"].cast<std::vector<std::vector<int>>>();
    } else if (t == "set") {
        s.type = NT_SET;
        s.a = cells("cells");
        std::string kind = d.contains("kind") ? d["kind"].cast<std::string>() : "consecutive";
        if (kind != "consecutive") throw std::invalid_argument("unsupported set kind: " + kind);
        s.setkind = 0;
    } else if (t == "little_killer") {  // a sum whose digits may repeat (unless forced by shared groups)
        s.type = NT_SUM;
        s.a = cells("cells");
        s.total = d["total"].cast<int>();
        s.distinct = (d.contains("distinct") && !d["distinct"].is_none() && d["distinct"].cast<bool>()) ? 1 : 0;
    } else if (t == "sandwich" || t == "xsum" || t == "skyscraper") {
        s.type = t == "sandwich" ? NT_SANDWICH : t == "xsum" ? NT_XSUM : NT_SKYLINE;
        s.a = cells("cells");
        s.total = d[t == "skyscraper" ? "count" : "total"].cast<int>();
    } else if (t == "count") {  // each digit (or the listed ones) exactly k times; NOT all-different
        s.type = NT_COUNT;
        s.a = cells("cells");
        int D = 32;
        s.quota.assign(D + 1, -1);
        if (d.contains("each") && !d["each"].is_none()) {
            int kq = d["each"].cast<int>();
            for (int v = 1; v <= D; ++v) s.quota[v] = kq;  // digits beyond the puzzle's D are trimmed later
        }
        if (d.contains("digits") && !d["digits"].is_none())
            for (auto kv : d["digits"].cast<py::dict>()) {
                int v = py::int_(py::reinterpret_borrow<py::object>(kv.first)).cast<int>();
                if (v >= 1 && v <= D) s.quota[v] = kv.second.cast<int>();
            }
    } else if (t == "line") {
        s.type = NT_LINE;
        s.a = cells("cells");
        if (d.contains("skip") && d["skip"].cast<bool>()) s.a.clear();  // carried by its n-ary part
        static const char* kinds[] = {"thermo", "slow_thermo", "whisper", "dutch_whisper", "renban", "palindrome",
                                      "entropic", "kropki_chain", "region_sum", "parity", "between", "modular",
                                      "zipper"};
        std::string kind = d["kind"].cast<std::string>();
        for (int i = 0; i < LK_N; ++i)
            if (kind == kinds[i]) s.line_kind = i;
        if (s.line_kind < 0) throw std::invalid_argument("unknown line kind: " + kind);
    } else if (t == "between") {
        s.type = NT_BETWEEN;
        s.a = cells("cells");
    } else if (t == "counting_circles") {
        s.type = NT_CIRCLES;
        s.a = cells("cells");
    } else if (t == "first_seen") {  // {"cells": [in reading order], "value": X, "digits": [1, 2, 3]}
        s.type = NT_FIRSTSEEN;
        s.a = cells("cells");
        s.total = d["value"].cast<int>();
        std::vector<int> ds = {1, 2, 3};
        if (d.contains("digits") && !d["digits"].is_none()) ds = d["digits"].cast<std::vector<int>>();
        s.setkind = 0;
        for (int v : ds) s.setkind |= 1 << (v - 1);
    } else if (t == "distinct_count") {  // {"cells": [...], "count": k}: exactly k different digits
        s.type = NT_DISTINCT;
        s.a = cells("cells");
        s.total = d["count"].cast<int>();
    } else if (t == "contains") {  // {"cells": [source, target, ...]}: the source digit appears among the targets
        s.type = NT_CONTAINS;
        s.a = cells("cells");
    } else if (t == "digit_set") {  // {"houses": [[cells], ...], "n": N}: one set of N digits in every house
        s.type = NT_DIGITSET;
        for (auto h : d["houses"]) s.segs.push_back(h.cast<std::vector<int>>());
        s.total = d["n"].cast<int>();
    } else if (t == "table") {
        s.type = NT_TABLE;
        s.a = cells("cells");
        s.rows = d["allowed"].cast<std::vector<std::vector<int>>>();
        s.named = d.contains("name") && !d["name"].is_none();
    } else {
        throw std::invalid_argument("unknown constraint type: " + t);
    }
    if (d.contains("offset") && !d["offset"].is_none()) {  // the rule is on (digit - offset): shifted universes
        const int off = d["offset"].cast<int>();
        if (s.type == NT_SUM) {
            s.total += off * (int)s.a.size();
            for (int& t2 : s.totals) t2 += off * (int)s.a.size();
        } else if (s.type == NT_EQSUM) {
            s.offset = off;
        } else if (off) {
            throw std::invalid_argument("offset is supported on sum / little_killer / equal_sum only");
        }
    }
    if (d.contains("line_kind") && !d["line_kind"].is_none() && s.line_kind < 0) {
        static const char* kinds[] = {"thermo", "slow_thermo", "whisper", "dutch_whisper", "renban", "palindrome",
                                      "entropic", "kropki_chain", "region_sum", "parity", "between", "modular",
                                      "zipper"};
        std::string kind = d["line_kind"].cast<std::string>();
        for (int i = 0; i < LK_N; ++i)
            if (kind == kinds[i]) s.line_kind = i;
    }
    return s;
}

// the puzzle's input structure only (not finalized: no derived / implied / canonical structure); small.
// featurize builds the full puzzle from it inside a worker, per state, and frees it after the solve
static std::shared_ptr<Puzzle> make_puzzle_raw(int D, const std::vector<std::pair<int, int>>& coords,
                                               const py::list& groups, const std::vector<uint32_t>& domains,
                                               const py::list& relations, const py::list& constraints) {
    auto p = std::make_shared<Puzzle>();
    p->D = D;
    p->coords = coords;
    for (auto g : groups) {
        py::tuple t = g.cast<py::tuple>();
        Group gr;
        gr.cells = t[0].cast<std::vector<int>>();
        gr.complete = t[1].cast<bool>();
        if (!t[2].is_none()) {
            gr.has_total = true;
            gr.total = t[2].cast<int>();
        }
        gr.name = t[3].cast<std::string>();
        if (t.size() > 4 && !t[4].is_none()) gr.kind = t[4].cast<std::string>();
        p->groups.push_back(std::move(gr));
    }
    p->domains = domains;
    for (auto r : relations) {
        py::tuple t = r.cast<py::tuple>();
        RelSpec rs;
        rs.a = t[0].cast<int>();
        rs.b = t[1].cast<int>();
        rs.neq = t[2].cast<bool>();
        if (!rs.neq) {
            rs.fwd = t[3].cast<std::vector<uint32_t>>();
            rs.bwd = t[4].cast<std::vector<uint32_t>>();
        }
        p->relations.push_back(std::move(rs));
    }
    for (auto con : constraints) p->nary_specs.push_back(parse_constraint(con.cast<py::dict>()));
    return p;
}

static std::shared_ptr<Puzzle> make_puzzle(int D, const std::vector<std::pair<int, int>>& coords, const py::list& groups,
                                           const std::vector<uint32_t>& domains, const py::list& relations,
                                           const py::list& constraints) {
    auto p = make_puzzle_raw(D, coords, groups, domains, relations, constraints);
    p->finalize();
    return p;
}

static py::object feat_tuple(const Move& m, const std::vector<Cover>& covers, bool with_load = false) {
    py::tuple cov(m.cov_n);
    for (int i = 0; i < m.cov_n; ++i) {
        const Cover& c = covers[m.cov_off + i];
        cov[i] = py::make_tuple(c.kind, c.shape, c.u);
    }
    py::object meta = py::none();
    if (m.has_meta) {
        // meta[0..7], spread, table live tuples, then the structural descriptors (desc.cpp) when present
        py::list ml;
        for (int i = 0; i < 8; ++i) ml.append(m.meta[i]);
        ml.append(m.spread);
        if (m.tab_live > 0 || m.has_desc) ml.append(m.tab_live);
        if (m.has_desc) {
            for (int i = 0; i < 8; ++i) ml.append(m.desc[i]);  // [10..17]
            ml.append(m.meta_synth ? 1 : 0);  // [18]: meta exported for a B-priced technique (not priced by it)
            ml.append(std::log1p(std::max(0.0, m.scan)));  // [19]: log1p(scan), the 19th meta_theta_full column
            ml.append(m.enumv);  // [20]: D5 enumeration (log1p max assignments of the sum rules touched)
        }
        meta = py::tuple(ml);
    }
    if (with_load && m.has_load)
        return py::make_tuple(m.tech, m.shape, cov, m.extra, meta,
                              py::make_tuple(m.load[0], m.load[1], m.load[2], m.load[3], m.load[4], m.load[5],
                                             m.load[6], m.load[7]));
    return py::make_tuple(m.tech, m.shape, cov, m.extra, meta);
}

static py::tuple py_solve(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params,
                          const std::vector<int>& disabled, const py::object& solution, bool allow_direct,
                          int max_steps, bool assume_unique, bool all_tiers, bool explain,
                          const py::object& colours, const py::object& cand) {
    Params P = params_from(params);
    SolveOptions o;
    if (!colours.is_none()) o.colours = colours.cast<std::vector<int>>();
    o.all_tiers = all_tiers;
    o.explain = explain;
    o.max_steps = max_steps;
    o.allow_direct = allow_direct;
    o.assume_unique = assume_unique;
    o.disabled = disabled;
    if (!solution.is_none()) o.solution = solution.cast<std::vector<int>>();
    std::vector<uint32_t> cd;
    if (!cand.is_none()) cd = cand.cast<std::vector<uint32_t>>();
    SolveResult r;
    {
        py::gil_scoped_release rel;
        Solver s(p, P, o);
        if ((int)cd.size() == p.N) s.cand_override = cd;
        s.solve(givens, r);
    }
    py::list steps;
    for (const StepRec& st : r.steps) {
        py::list alts;
        for (int i = 0; i < st.alt_n; ++i) alts.append(feat_tuple(r.alts[st.alt_off + i], r.covers, P.human));
        (void)0;
        py::object place = py::none();
        if (st.move.pc >= 0) place = py::make_tuple(st.move.pc, st.move.pv);
        py::tuple el(st.move.el_n);
        for (int i = 0; i < st.move.el_n; ++i) {
            uint32_t e = r.elims[st.move.el_off + i];
            el[i] = py::make_tuple((int)(e / 32), (int)(e % 32));
        }
        py::tuple xm((size_t)XM_N + (st.move.has_desc ? 8 : 0));  // technique xmeta, then the descriptors
        for (int i = 0; i < XM_N; ++i) xm[i] = st.move.xm[i];
        if (st.move.has_desc)
            for (int i = 0; i < 8; ++i) xm[XM_N + i] = st.move.desc[i];
        py::list pats, exs;
        for (int i = 0; i < st.move.pat_n; ++i) pats.append(r.pats[st.move.pat_off + i]);
        for (int i = 0; i < st.move.ex_n; ++i) exs.append(r.ex[st.move.ex_off + i]);
        steps.append(py::make_tuple(alts, st.chosen, place, el, py::make_tuple(st.move.nk, st.move.na, st.move.nb),
                                    st.move.d, st.mode, st.n_empty, st.erasures, st.notes_written, xm,
                                    st.move.code, pats, exs, st.n_cands));
    }
    return py::make_tuple(steps, r.solved);
}

template <class F>
static void parallel_for(size_t n, int threads, F&& f) {
    std::atomic<size_t> next(0);
    auto work = [&]() {
        while (true) {
            size_t i = next.fetch_add(1);
            if (i >= n) break;
            f(i);
        }
    };
    int nt = std::max(1, threads);
    if (nt == 1) {
        work();
        return;
    }
    std::vector<std::thread> th;
    for (int t = 0; t < nt; ++t) th.emplace_back(work);
    for (auto& t : th) t.join();
}

// per-strategy time / calls / hits of one solve: {name: (ms, calls, hits)}
static py::dict py_solve_stats(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params,
                               const std::vector<int>& disabled, const py::object& solution, bool assume_unique,
                               bool allow_direct) {
    Params P = params_from(params);
    SolveOptions o;
    o.disabled = disabled;
    o.assume_unique = assume_unique;
    o.allow_direct = allow_direct;
    o.stats = true;
    if (!solution.is_none()) o.solution = solution.cast<std::vector<int>>();
    SolveResult r;
    double total = 0;
    {
        py::gil_scoped_release rel;
        const auto t0 = std::chrono::steady_clock::now();
        Solver s(p, P, o);
        s.solve(givens, r);
        total = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    }
    py::dict d;
    for (auto& kv : r.stats) d[py::str(kv.first)] = py::make_tuple(kv.second.ms, kv.second.calls, kv.second.hits);
    d["_total_ms"] = total;
    d["_steps"] = (int)r.steps.size();
    return d;
}

static py::list py_finding_profile(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params,
                                   const std::vector<int>& solution, int max_stuck, int K) {
    Params P = params_from(params);
    SolveOptions o;
    std::vector<std::array<int, 5>> out;
    {
        py::gil_scoped_release rel;
        Solver s(p, P, o);
        s.refK = K;
        s.finding_profile(givens, solution, max_stuck, out);
    }
    py::list l;
    for (auto& r : out) l.append(py::make_tuple(r[0], r[1], r[2], r[3], r[4]));
    return l;
}

// every move available at one state (any technique family), priced: (tech, code, place, elims, d)
static py::list py_refute_profile(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params,
                                  const std::vector<int>& solution, int max_stuck, int K) {
    Params P = params_from(params);
    SolveOptions o;
    std::vector<std::array<int, 5>> out;
    {
        py::gil_scoped_release rel;
        Solver s(p, P, o);
        s.refK = K;
        s.refute_profile(givens, solution, max_stuck, out);
    }
    py::list l;
    for (auto& r : out) l.append(py::make_tuple(r[0], r[1], r[2], r[3], r[4]));
    return l;
}

static py::list py_cell_features(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params) {
    Params P = params_from(params);
    SolveOptions o;
    std::vector<std::array<double, 8>> out;
    {
        py::gil_scoped_release rel;
        Solver s(p, P, o);
        s.cell_features(givens, out);
    }
    py::list l;
    for (auto& r : out) l.append(py::make_tuple((int)r[0], (int)r[1], r[2], r[3], (int)r[4], (int)r[5], (int)r[6], r[7]));
    return l;
}

static py::list py_state_moves(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params,
                               const std::vector<int>& disabled, const py::object& solution, bool assume_unique,
                               int limit_per_tech, const py::object& written, bool details, const py::object& cand) {
    Params P = params_from(params);
    SolveOptions o;
    o.disabled = disabled;
    o.assume_unique = assume_unique;
    if (!solution.is_none()) o.solution = solution.cast<std::vector<int>>();
    std::vector<uint32_t> wr, cd;
    if (!written.is_none()) wr = written.cast<std::vector<uint32_t>>();
    if (!cand.is_none()) cd = cand.cast<std::vector<uint32_t>>();
    MoveBuf b;
    {
        py::gil_scoped_release rel;
        Solver s(p, P, o);
        if ((int)wr.size() == p.N) s.written_override = wr;
        if ((int)cd.size() == p.N) s.cand_override = cd;
        s.state_moves(givens, b, limit_per_tech);
    }
    py::list out;
    for (const Move& m : b.moves) {
        py::object place = py::none();
        if (m.pc >= 0) place = py::make_tuple(m.pc, m.pv);
        py::list el;
        for (int i = 0; i < m.el_n; ++i) {
            uint32_t e = b.elims[m.el_off + i];
            el.append(py::make_tuple((int)(e / 32), (int)(e % 32)));
        }
        if (!details) {
            out.append(py::make_tuple(m.tech, m.code, place, el, m.d));
            continue;
        }
        py::tuple xm((size_t)XM_N);
        for (int i = 0; i < XM_N; ++i) xm[i] = m.xm[i];
        py::list pat;
        for (int i = 0; i < m.pat_n; ++i) pat.append(b.pats[m.pat_off + i]);
        py::object ft = feat_tuple(m, b.covers);
        py::object meta = ft.attr("__getitem__")(4);
        out.append(py::make_tuple(m.tech, m.code, place, el, m.d, meta, xm, m.scan, pat));
    }
    return out;
}

// stochastic rollouts: n sampled solve paths (threads), each summarised like grader.scoring.grade
static py::list py_rollouts(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params,
                            const std::vector<int>& disabled, const py::object& solution, int n, double temperature,
                            uint64_t seed, int threads, bool focus, bool all_families, const std::vector<double>& attract,
                            double eta, const std::vector<double>& gfocus, int max_steps, bool assume_unique) {
    Params P = params_from(params);
    SolveOptions base;
    base.disabled = disabled;
    base.max_steps = max_steps;
    if (!solution.is_none()) base.solution = solution.cast<std::vector<int>>();
    base.rollout = true;
    base.assume_unique = assume_unique;
    base.temperature = temperature;
    base.focus = focus;
    base.all_families = all_families;
    base.attract = attract;
    base.eta = eta;
    for (size_t i = 0; i < gfocus.size() && i < 4; ++i) base.gfocus[i] = gfocus[i];
    struct R { double t, d; int hardest, steps; bool notes, solved; };
    std::vector<R> res(std::max(n, 0));
    {
        py::gil_scoped_release rel;
        parallel_for(res.size(), threads, [&](size_t i) {
            SolveOptions o = base;
            o.seed = seed + 1000003ULL * (uint64_t)i;
            SolveResult r;
            Solver s(p, P, o);
            s.solve(givens, r);
            res[i] = {r.r_time, r.r_difficulty, r.r_hardest, r.r_steps, r.r_notes, r.solved};
        });
    }
    py::list out;
    for (auto& r : res) out.append(py::make_tuple(r.t, r.d, r.hardest, r.notes, r.steps, r.solved));
    return out;
}

// roll_to_placement: K rollouts of the human race from one state to the next placement (rollplace.cpp)
static py::dict py_roll_to_placement(const Puzzle& p, const std::vector<std::pair<int, int>>& givens,
                                     const py::dict& params, const std::vector<int>& disabled, int k,
                                     double temperature, uint64_t seed, int max_moves, int phase,
                                     const py::object& written, const py::object& rate_w, bool all_lists,
                                     int threads) {
    Params P = params_from(params);
    SolveOptions o;
    o.disabled = disabled;
    RollSpec sp;
    sp.k = std::max(k, 1);
    sp.temperature = temperature;
    sp.seed = seed;
    sp.max_moves = std::max(max_moves, 1);
    sp.phase = phase;
    if (!written.is_none()) sp.written = written.cast<std::vector<uint32_t>>();
    if (!rate_w.is_none()) sp.rate_w = rate_w.cast<std::vector<double>>();
    RollOut out;
    std::vector<std::vector<RollStep>> steps(sp.k);
    {
        py::gil_scoped_release rel;
        std::mutex mu;
        std::unordered_map<uint64_t, int> cache;
        parallel_for((size_t)sp.k, threads, [&](size_t i) {
            Solver s(p, P, o);
            s.roll_place(givens, sp, (int)i, out, mu, cache, steps[i]);
        });
    }
    // steps: rollout, k, state, row, n_empty, n_cands, held_mental, hash
    std::vector<RollStep> all;
    for (auto& v : steps) all.insert(all.end(), v.begin(), v.end());
    {  // deterministic numbering: states in order of first visit (rollout, k), rows follow their state
        const int ns = (int)out.st_hash.size();
        std::vector<int> nid(ns, -1), order;
        for (auto& r : all)
            if (nid[r.state] < 0) nid[r.state] = (int)order.size(), order.push_back(r.state);
        for (int sid = 0; sid < ns; ++sid)
            if (nid[sid] < 0) nid[sid] = (int)order.size(), order.push_back(sid);
        RollOut o2;
        std::vector<int> rowmap(out.mv_tech.size(), -1);
        for (int old : order) {
            o2.st_hash.push_back(out.st_hash[old]);
            o2.st_row0.push_back((int)o2.mv_tech.size());
            o2.st_n.push_back(out.st_n[old]);
            o2.st_phase.push_back(out.st_phase[old]);
            for (int i = 0; i < out.st_n[old]; ++i) {
                const int r = out.st_row0[old] + i;
                rowmap[r] = (int)o2.mv_tech.size();
                o2.mv_tech.push_back(out.mv_tech[r]);
                o2.mv_code.push_back(out.mv_code[r]);
                o2.mv_pc.push_back(out.mv_pc[r]);
                o2.mv_pv.push_back(out.mv_pv[r]);
                o2.mv_nel.push_back(out.mv_nel[r]);
                o2.mv_el0.push_back(0);
                o2.mv_d.push_back(out.mv_d[r]);
                o2.mv_x.insert(o2.mv_x.end(), out.mv_x.begin() + (size_t)r * 19, out.mv_x.begin() + (size_t)r * 19 + 19);
            }
        }
        for (auto& r : all) r.state = nid[r.state], r.row = rowmap[r.row];
        for (auto& v : steps)
            for (auto& r : v) r.state = nid[r.state], r.row = rowmap[r.row];
        out = std::move(o2);
    }
    const py::ssize_t S = (py::ssize_t)all.size();
    py::array_t<pm_long> s_roll(S), s_k(S), s_state(S), s_row(S), s_empty(S), s_cands(S), s_held(S);
    py::array_t<uint64_t> s_hash(S);
    for (py::ssize_t i = 0; i < S; ++i) {
        const RollStep& r = all[i];
        s_roll.mutable_data()[i] = r.rollout, s_k.mutable_data()[i] = r.k, s_state.mutable_data()[i] = r.state;
        s_row.mutable_data()[i] = r.row, s_empty.mutable_data()[i] = r.n_empty, s_cands.mutable_data()[i] = r.n_cands;
        s_held.mutable_data()[i] = r.held_mental, s_hash.mutable_data()[i] = r.hash;
    }
    // per rollout: moves taken, ended in a placement
    py::array_t<pm_long> r_n(sp.k);
    py::array_t<bool> r_place(sp.k);
    for (int i = 0; i < sp.k; ++i) {
        r_n.mutable_data()[i] = (pm_long)steps[i].size();
        r_place.mutable_data()[i] = !steps[i].empty() && out.mv_pc[steps[i].back().row] >= 0;
    }
    // states / rows (all visited, or only those of the start states when all_lists is false)
    const py::ssize_t NS = (py::ssize_t)out.st_hash.size(), NR = (py::ssize_t)out.mv_tech.size();
    std::vector<char> keep(NS, all_lists ? 1 : 0);
    if (!all_lists)
        for (auto& r : all)
            if (r.k == 0) keep[r.state] = 1;
    py::array_t<uint64_t> st_hash(NS);
    py::array_t<pm_long> st_row0(NS), st_n(NS), st_phase(NS);
    py::array_t<bool> st_kept(NS);
    for (py::ssize_t i = 0; i < NS; ++i) {
        st_hash.mutable_data()[i] = out.st_hash[i];
        st_row0.mutable_data()[i] = out.st_row0[i];
        st_n.mutable_data()[i] = out.st_n[i];
        st_phase.mutable_data()[i] = out.st_phase[i];
        st_kept.mutable_data()[i] = keep[i];
    }
    py::array_t<pm_long> mv_tech(NR), mv_code(NR), mv_pc(NR), mv_pv(NR), mv_nel(NR);
    py::array_t<double> mv_d(NR), mv_x({NR, (py::ssize_t)19});
    for (py::ssize_t i = 0; i < NR; ++i) {
        mv_tech.mutable_data()[i] = out.mv_tech[i], mv_code.mutable_data()[i] = out.mv_code[i];
        mv_pc.mutable_data()[i] = out.mv_pc[i], mv_pv.mutable_data()[i] = out.mv_pv[i];
        mv_nel.mutable_data()[i] = out.mv_nel[i], mv_d.mutable_data()[i] = out.mv_d[i];
        for (int j = 0; j < 19; ++j) mv_x.mutable_data()[i * 19 + j] = out.mv_x[(size_t)i * 19 + j];
    }
    py::dict d;
    d["s_rollout"] = s_roll; d["s_k"] = s_k; d["s_state"] = s_state; d["s_row"] = s_row;
    d["s_n_empty"] = s_empty; d["s_n_cands"] = s_cands; d["s_held_mental"] = s_held; d["s_hash"] = s_hash;
    d["r_n_moves"] = r_n; d["r_placement"] = r_place;
    d["st_hash"] = st_hash; d["st_row0"] = st_row0; d["st_n"] = st_n; d["st_phase"] = st_phase; d["st_listed"] = st_kept;
    d["mv_tech"] = mv_tech; d["mv_code"] = mv_code; d["mv_place_cell"] = mv_pc; d["mv_place_digit"] = mv_pv;
    d["mv_n_elims"] = mv_nel; d["mv_d"] = mv_d; d["mv_x"] = mv_x;
    return d;
}

static py::object py_brute(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, int limit, pm_long node_limit,
                           const py::object& start, bool with_status) {
    std::vector<std::vector<int>> sols;
    bool complete = true;
    if (start.is_none()) {
        py::gil_scoped_release rel;
        sols = brute_solve(p, givens, limit, node_limit, nullptr, nullptr, &complete);
    } else {
        py::tuple t = start.cast<py::tuple>();
        auto v = t[0].cast<std::vector<int>>();
        auto c = t[1].cast<std::vector<uint32_t>>();
        std::vector<uint8_t> vv(v.begin(), v.end());
        py::gil_scoped_release rel;
        sols = brute_solve(p, givens, limit, node_limit, &vv, &c, &complete);
    }
    py::list out;
    for (auto& s : sols) out.append(py::cast(s));
    if (with_status) return py::make_tuple(out, complete);
    return out;
}

// derived structure of the puzzle a solve runs on (implied houses, leftover equalities,
// big innie regions): what explanation records refer to beyond the input puzzle
static py::dict puzzle_info(const Puzzle& pz, const std::vector<int>& disabled) {
    SolveOptions o;
    o.disabled = disabled;
    const Puzzle& p = Solver::pick_puzzle(pz, o);
    py::dict d;
    d["G"] = p.G;
    d["base_G"] = p.is_derived ? p.base_G : p.G;
    py::list ig;
    for (int gi = p.is_derived ? p.base_G : p.G; gi < p.G; ++gi)
        ig.append(py::make_tuple(gi, p.groups[gi].name, p.groups[gi].cells));
    d["implied_groups"] = ig;
    const int bn = p.is_derived && p.base_nary >= 0 ? p.base_nary : (int)p.nary_specs.size();
    d["base_nary"] = bn;
    py::list lo;
    for (int i = bn; i < (int)p.nary_specs.size(); ++i) {
        const NSpec& sp = p.nary_specs[i];
        if (sp.type != NT_SAMESET || sp.segs.size() != 2) continue;
        py::dict e;
        e["index"] = i;
        e["a"] = sp.segs[0];
        e["b"] = sp.segs[1];
        e["lines"] = sp.def_lines;
        e["regions"] = sp.def_regs;
        e["kind"] = sp.setkind == 4 ? "Phistomefel variant" : sp.setkind == 3 ? "set theory" : sp.setkind == 2 ? "Phistomefel ring" : sp.setkind ? "set equivalence"
                                                                                                    : "law of leftovers";
        lo.append(e);
    }
    d["leftovers"] = lo;
    py::list bi;
    for (const InnieSet& s : p.big_innies)
        bi.append(py::make_tuple(s.houses, s.cells, s.total, s.cages, s.outie ? "outie" : "innie"));
    d["big_innies"] = bi;
    return d;
}

static py::dict debug_info(const Puzzle& p) {
    py::dict d;
    d["neq"] = p.neq;
    d["rel"] = p.rel;
    std::vector<double> shapes;
    for (auto& g : p.groups) shapes.push_back(g.shape);
    d["shapes"] = shapes;
    d["house_unions"] = p.house_unions;
    py::list inn;
    for (auto& s : p.innies) inn.append(py::make_tuple(s.hi, s.cells, s.total, s.cages, s.outie ? "outie" : "innie"));
    d["innies"] = inn;
    d["peer_list"] = p.peer_list;
    return d;
}

// ------------------------------------------------------------ featurize --
struct Spec {
    std::shared_ptr<Puzzle> pz;  // generic spec ("cpuzzle", cp, givens, solution)
    bool raw = false;            // ("praw", ...): pz is the unfinalized input; built + freed in the worker
    int tab;  // 0 classic, 1 nonc, 2 killer
    std::vector<std::pair<int, int>> givens;
    std::vector<std::pair<int, std::vector<int>>> cages;
    std::vector<int> solution;
    int max_steps = 5000;
    int seed_cell = -1, seed_digit = 0, seed_run = 1;
    bool all_tiers = false;
    std::vector<int> colours;  // per cell colour id (-1 none): human colouring seeds
    bool assume_unique = true;
};
static inline int tech_idx(int t) { return t < 5 ? t : t - 5; }

// classic / nonc share structure: finalized once, read-only across threads
static void solve_spec(const Spec& sp, const Params& P, const Puzzle* tmpl, const std::vector<int>& disabled,
                       bool rich, SolveResult& r) {
    SolveOptions o;
    o.rich = rich;
    o.disabled = disabled;
    o.solution = sp.solution;
    o.max_steps = sp.max_steps;
    o.seed_cell = sp.seed_cell;
    o.seed_digit = sp.seed_digit;
    o.seed_run = sp.seed_run;
    o.all_tiers = sp.all_tiers;
    o.colours = sp.colours;
    o.assume_unique = sp.assume_unique;
    o.prune_tiers = false;  // featurize: every alternative of the tier
    if (sp.pz && sp.raw) {  // build this state's puzzle here, free it when the solve is done
        Puzzle p = *sp.pz;
        p.finalize();
        Solver s(p, P, o);
        s.solve(sp.givens, r);
        return;
    }
    if (sp.pz) {  // generic puzzle (finalized by make_puzzle; read-only, shared across threads)
        Solver s(*sp.pz, P, o);
        s.solve(sp.givens, r);
        return;
    }
    if (sp.tab != 2) {
        Solver s(tmpl[sp.tab], P, o);
        s.solve(sp.givens, r);
        return;
    }
    Puzzle p = make_standard(9, 3, 3);
    add_cages(p, sp.cages);
    p.finalize();
    Solver s(p, P, o);
    s.solve(sp.givens, r);
}


// grader.features.featurize_raw: solve every spec in worker threads, then
// fill preallocated numpy arrays (also in parallel, at per-puzzle offsets)
static py::dict py_featurize(const py::list& specs_in, const py::dict& params, int threads,
                             const std::vector<int>& disabled, bool rich) {
    Params P = params_from(params);
    std::vector<Spec> specs;
    for (auto o : specs_in) {
        py::tuple t = o.cast<py::tuple>();
        Spec s;
        if (py::isinstance<py::str>(t[0])) {  // ("cpuzzle" | "praw", cp, givens, solution)
            s.raw = t[0].cast<std::string>() == "praw";
            s.pz = t[1].cast<std::shared_ptr<Puzzle>>();
            s.tab = -1;
            s.givens = t[2].cast<std::vector<std::pair<int, int>>>();
            if (!t[3].is_none()) s.solution = t[3].cast<std::vector<int>>();
            if (t.size() > 4 && !t[4].is_none()) s.max_steps = t[4].cast<int>();
            if (t.size() > 5 && !t[5].is_none()) {  // last move: (cell, digit[, run length])
                py::tuple lm = t[5].cast<py::tuple>();
                s.seed_cell = lm[0].cast<int>();
                s.seed_digit = lm[1].cast<int>();
                if (lm.size() > 2) s.seed_run = lm[2].cast<int>();
            }
            if (t.size() > 6 && !t[6].is_none()) s.all_tiers = t[6].cast<bool>();
            if (t.size() > 7 && !t[7].is_none()) s.colours = t[7].cast<std::vector<int>>();
            if (t.size() > 8 && !t[8].is_none()) s.assume_unique = t[8].cast<bool>();
            specs.push_back(std::move(s));
            continue;
        }
        s.tab = t[0].cast<int>();
        s.givens = t[1].cast<std::vector<std::pair<int, int>>>();
        s.cages = t[2].cast<std::vector<std::pair<int, std::vector<int>>>>();
        if (!t[3].is_none()) s.solution = t[3].cast<std::vector<int>>();
        specs.push_back(std::move(s));
    }
    const size_t n = specs.size();
    std::vector<SolveResult> res(n);
    const bool timing = std::getenv("CSOLVER_TIMING") != nullptr;
    auto t0 = std::chrono::steady_clock::now();
    {
        py::gil_scoped_release rel;
        Puzzle tmpl[2] = {make_standard(9, 3, 3), make_standard(9, 3, 3)};
        add_nonconsecutive(tmpl[1], 9);
        tmpl[0].finalize();
        tmpl[1].finalize();
        parallel_for(n, threads, [&](size_t i) { solve_spec(specs[i], P, tmpl, disabled, rich, res[i]); });
    }
    auto t1 = std::chrono::steady_clock::now();
    std::vector<size_t> soff(n + 1, 0), moff(n + 1, 0);
    for (size_t i = 0; i < n; ++i) {
        soff[i + 1] = soff[i] + res[i].steps.size();
        moff[i + 1] = moff[i] + res[i].alts.size();
    }
    const py::ssize_t S = (py::ssize_t)soff[n], M = (py::ssize_t)moff[n];
    py::array_t<pm_long> m_place(M), m_value(M);
    pm_long *pm_place = m_place.mutable_data(), *pm_value = m_value.mutable_data();
    py::array_t<pm_long> m_step(M), m_tech(M), s_puz(S), s_nempty(S), s_place(S), s_erase(S), s_notes(S), s_mode(S),
        s_chosen(S);
    py::array_t<pm_long> m_ck({M, (py::ssize_t)CMAX}), m_cu({M, (py::ssize_t)CMAX});
    py::array_t<double> m_shape(M), m_cs({M, (py::ssize_t)CMAX}), m_meta({M, (py::ssize_t)18}),
        m_desc({M, (py::ssize_t)8});
    py::array_t<bool> m_hasmeta(M), m_metapriced(M), m_hasdesc(M), solved((py::ssize_t)n);
    py::array_t<double> m_enum(M);   // D5 enumeration per move (separate array: m_meta stays 18 columns)
    const py::ssize_t RC = (py::ssize_t)rich_names().size(), SC = (py::ssize_t)step_names().size();
    py::array_t<float> m_rich({rich ? M : 0, RC}), s_rich({rich ? S : 0, SC});
    float* pm_rich = m_rich.mutable_data();
    float* ps_rich = s_rich.mutable_data();
    pm_long *pm_step = m_step.mutable_data(), *pm_tech = m_tech.mutable_data(), *ps_puz = s_puz.mutable_data(),
         *ps_nempty = s_nempty.mutable_data(), *ps_place = s_place.mutable_data(), *ps_erase = s_erase.mutable_data(),
         *ps_notes = s_notes.mutable_data(), *ps_mode = s_mode.mutable_data(), *ps_chosen = s_chosen.mutable_data(),
         *pm_ck = m_ck.mutable_data(), *pm_cu = m_cu.mutable_data();
    double* pm_enum = m_enum.mutable_data();
    std::fill(pm_enum, pm_enum + M, 0.0);
    double *pm_shape = m_shape.mutable_data(), *pm_cs = m_cs.mutable_data(), *pm_meta = m_meta.mutable_data(),
           *pm_desc = m_desc.mutable_data();
    bool *pm_hasmeta = m_hasmeta.mutable_data(), *pm_metapriced = m_metapriced.mutable_data(), *pm_hasdesc = m_hasdesc.mutable_data(), *psolved = solved.mutable_data();
    {
        py::gil_scoped_release rel;
        parallel_for(n, threads, [&](size_t pi) {
            SolveResult& r = res[pi];
            psolved[pi] = r.solved;
            size_t si = soff[pi], mi = moff[pi];
            if (rich) {
                std::copy(r.m_rich.begin(), r.m_rich.end(), pm_rich + mi * RC);
                std::copy(r.s_rich.begin(), r.s_rich.end(), ps_rich + si * SC);
            }
            for (const StepRec& st : r.steps) {
                ps_puz[si] = (pm_long)pi;
                ps_nempty[si] = st.n_empty;
                ps_place[si] = st.move.pc >= 0 ? 1 : 0;
                ps_erase[si] = st.erasures;
                ps_notes[si] = st.notes_written;
                ps_mode[si] = st.mode;
                ps_chosen[si] = (pm_long)(mi + st.chosen);
                for (int i = 0; i < st.alt_n; ++i, ++mi) {
                    const Move& m = r.alts[st.alt_off + i];
                    pm_step[mi] = (pm_long)si;
                    pm_place[mi] = m.pc;
                    pm_value[mi] = m.pc >= 0 ? m.pv : 0;
                    pm_tech[mi] = tech_idx(m.tech);
                    pm_shape[mi] = m.shape;
                    for (int j = 0; j < CMAX; ++j) {
                        if (j < m.cov_n) {
                            const Cover& c = r.covers[m.cov_off + j];
                            pm_ck[mi * CMAX + j] = c.kind;
                            pm_cs[mi * CMAX + j] = c.shape;
                            pm_cu[mi * CMAX + j] = c.u;
                        } else {
                            pm_ck[mi * CMAX + j] = 0;
                            pm_cs[mi * CMAX + j] = 1.0;
                            pm_cu[mi * CMAX + j] = 0;
                        }
                    }
                    double x[10] = {0};
                    if (m.has_meta) meta_vector(m, x);
                    std::copy(x, x + 10, pm_meta + mi * 18);
                    pm_hasmeta[mi] = m.has_meta;  // every technique in canonical mode (meta_synth ones too)
                    pm_metapriced[mi] = priced_meta(m);  // priced by the meta model today (else by B)
                    for (int j = 0; j < 8; ++j) pm_meta[mi * 18 + 10 + j] = m.has_desc ? m.desc[j] : 0.0;
                    pm_enum[mi] = m.has_desc ? m.enumv : 0.0;
                    for (int j = 0; j < 8; ++j) pm_desc[mi * 8 + j] = m.has_desc ? m.desc[j] : 0.0;  // structural
                    pm_hasdesc[mi] = m.has_desc;                                                   // descriptors
                }
                ++si;
            }
            r = SolveResult();  // free early
        });
    }
    py::dict out;
    out["m_step"] = m_step;
    out["m_place"] = m_place;
    out["m_value"] = m_value;
    out["m_tech"] = m_tech;
    out["m_shape"] = m_shape;
    out["m_ck"] = m_ck;
    out["m_cs"] = m_cs;
    out["m_cu"] = m_cu;
    out["m_meta"] = m_meta;
    out["m_enum"] = m_enum;
    out["m_hasmeta"] = m_hasmeta;
    out["m_metapriced"] = m_metapriced;  // has_meta as today's pricing sees it (meta_synth moves: False)
    out["m_desc"] = m_desc;  // log branches, log depth, search, uniqueness, counting, contradiction, held, coverage
    out["m_hasdesc"] = m_hasdesc;
    out["s_puz"] = s_puz;
    out["s_nempty"] = s_nempty;
    out["s_place"] = s_place;
    out["s_erase"] = s_erase;
    out["s_notes"] = s_notes;
    out["s_mode"] = s_mode;
    out["s_chosen"] = s_chosen;
    out["solved"] = solved;
    out["n_puz"] = (pm_long)n;
    if (rich) {
        out["m_rich"] = m_rich;
        out["s_rich"] = s_rich;
        out["rich_names"] = rich_names();
        out["step_names"] = step_names();
    }
    if (timing) {
        auto t2 = std::chrono::steady_clock::now();
        std::fprintf(stderr, "featurize: solve %.3fs fill %.3fs (%ld steps, %ld moves)\n",
                     std::chrono::duration<double>(t1 - t0).count(), std::chrono::duration<double>(t2 - t1).count(),
                     (pm_long)S, (pm_long)M);
    }
    return out;
}

PYBIND11_MODULE(_csolver, m) {
    m.doc() = "C++ port of grader.solver (see csolver/README.md)";
    py::class_<Puzzle, std::shared_ptr<Puzzle>>(m, "Puzzle")
        .def_readonly("N", &Puzzle::N)
        .def_readonly("D", &Puzzle::D)
        .def_readonly("has_cages", &Puzzle::has_cages);
    m.def("make_puzzle", &make_puzzle);
    m.def("make_puzzle_raw", &make_puzzle_raw);
    m.def("set_deadline", [](double seconds) { set_deadline(seconds); }, py::arg("seconds"),
          "wall-clock limit for the following solves in this thread (seconds; <= 0 switches it off)");
    m.def("deadline_hit", []() { return g_deadline_hit; }, "True once the deadline set by set_deadline has passed");
    m.def("solve", &py_solve, py::arg("puzzle"), py::arg("givens"), py::arg("params"), py::arg("disabled"),
          py::arg("solution"), py::arg("allow_direct"), py::arg("max_steps"), py::arg("assume_unique") = true,
          py::arg("all_tiers") = false, py::arg("explain") = false, py::arg("colours") = py::none(),
          py::arg("cand") = py::none());
    m.def("brute_solve", &py_brute, py::arg("puzzle"), py::arg("givens"), py::arg("limit"), py::arg("node_limit"),
          py::arg("start") = py::none(), py::arg("with_status") = false);
    m.def("featurize", &py_featurize, py::arg("specs"), py::arg("params"), py::arg("threads"),
          py::arg("disabled") = std::vector<int>(), py::arg("rich") = false);
    m.def("rich_names", &rich_names);
    m.def("step_names", &step_names);
    m.def("debug_info", &debug_info);
    m.def("puzzle_info", &puzzle_info, py::arg("puzzle"), py::arg("disabled") = std::vector<int>());
    m.def("solve_stats", &py_solve_stats, py::arg("puzzle"), py::arg("givens"), py::arg("params"),
          py::arg("disabled"), py::arg("solution"), py::arg("assume_unique") = false, py::arg("allow_direct") = true);
    m.def("roll_to_placement", &py_roll_to_placement, py::arg("puzzle"), py::arg("givens"), py::arg("params"),
          py::arg("disabled"), py::arg("k") = 20, py::arg("temperature") = 1.0, py::arg("seed") = 1,
          py::arg("max_moves") = 40, py::arg("phase") = -1, py::arg("written") = py::none(),
          py::arg("rate_w") = py::none(), py::arg("all_lists") = true, py::arg("threads") = 16);
    m.def("cell_features", &py_cell_features, py::arg("puzzle"), py::arg("givens"), py::arg("params"));
    m.def("finding_profile", &py_finding_profile, py::arg("puzzle"), py::arg("givens"), py::arg("params"), py::arg("solution"),
          py::arg("max_stuck") = 400, py::arg("K") = 0);
    m.def("refute_profile", &py_refute_profile, py::arg("puzzle"), py::arg("givens"), py::arg("params"), py::arg("solution"),
          py::arg("max_stuck") = 400, py::arg("K") = 0);
    m.def("state_moves", &py_state_moves, py::arg("puzzle"), py::arg("givens"), py::arg("params"),
          py::arg("disabled"), py::arg("solution"), py::arg("assume_unique") = false, py::arg("limit_per_tech") = 0,
          py::arg("written") = py::none(), py::arg("details") = false, py::arg("cand") = py::none());
    m.def("rollouts", &py_rollouts, py::arg("puzzle"), py::arg("givens"), py::arg("params"), py::arg("disabled"),
          py::arg("solution"), py::arg("n"), py::arg("temperature"), py::arg("seed"), py::arg("threads"),
          py::arg("focus"), py::arg("all_families"), py::arg("attract"), py::arg("eta"), py::arg("gfocus"),
          py::arg("max_steps") = 5000, py::arg("assume_unique") = false);
}
