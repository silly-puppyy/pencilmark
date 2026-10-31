#include "portable.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <stdexcept>
#include <string>
#include <cstdlib>

#include "model.hpp"
#include "solver.hpp"

namespace py = pybind11;
using namespace cs;


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
        std::string kind = d["kind"].cast<std::string>();
        s.line_kind = line_kind_from_name(kind);
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
        s.line_kind = line_kind_from_name(d["line_kind"].cast<std::string>());
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

// every move available at one state (any technique family), priced: (tech, code, place, elims, d)
static py::list py_state_moves(const Puzzle& p, const std::vector<std::pair<int, int>>& givens, const py::dict& params,
                               const std::vector<int>& disabled, const py::object& solution, bool assume_unique,
                               int limit_per_tech, const py::object& written, bool details, const py::object& cand) {
    Params P = params_from(params);
    uint64_t phash = 1469598103934665603ULL;  // the listing cache's params key: every item, by value
    for (auto item : params) phash = (phash ^ (uint64_t)py::hash(py::repr(item.first)) ^ ((uint64_t)py::hash(py::repr(item.second)) << 1)) * 1099511628211ULL;
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
        s.lcache = true;
        s.lcache_params = phash;
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

PYBIND11_MODULE(_csolver, m) {
    m.doc() = "pencilmark's C++ engine (see ARCHITECTURE.md)";
    py::class_<Puzzle, std::shared_ptr<Puzzle>>(m, "Puzzle")
        .def_readonly("N", &Puzzle::N)
        .def_readonly("D", &Puzzle::D)
        .def_readonly("has_cages", &Puzzle::has_cages);
    m.def("make_puzzle", &make_puzzle);
    m.def("set_deadline", [](double seconds) { set_deadline(seconds); }, py::arg("seconds"),
          "wall-clock limit for the following solves in this thread (seconds; <= 0 switches it off)");
    m.def("deadline_hit", []() { return g_deadline_hit; }, "True once the deadline set by set_deadline has passed");
    m.def("listing_cache", [](bool on) { listing_cache_enable(on); }, py::arg("on"),
          "state_moves reuses each strategy's moves at a state it listed before (on by default; off: compute every "
          "listing, for tests). Either way the cache is emptied.");
    m.def("solve", &py_solve, py::arg("puzzle"), py::arg("givens"), py::arg("params"), py::arg("disabled"),
          py::arg("solution"), py::arg("allow_direct"), py::arg("max_steps"), py::arg("assume_unique") = true,
          py::arg("all_tiers") = false, py::arg("explain") = false, py::arg("colours") = py::none(),
          py::arg("cand") = py::none());
    m.def("brute_solve", &py_brute, py::arg("puzzle"), py::arg("givens"), py::arg("limit"), py::arg("node_limit"),
          py::arg("start") = py::none(), py::arg("with_status") = false);
    m.def("puzzle_info", &puzzle_info, py::arg("puzzle"), py::arg("disabled") = std::vector<int>());
    m.def("refute_profile", &py_refute_profile, py::arg("puzzle"), py::arg("givens"), py::arg("params"), py::arg("solution"),
          py::arg("max_stuck") = 400, py::arg("K") = 0);
    m.def("state_moves", &py_state_moves, py::arg("puzzle"), py::arg("givens"), py::arg("params"),
          py::arg("disabled"), py::arg("solution"), py::arg("assume_unique") = false, py::arg("limit_per_tech") = 0,
          py::arg("written") = py::none(), py::arg("details") = false, py::arg("cand") = py::none());
}
