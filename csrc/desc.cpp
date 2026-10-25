// Structural descriptors for every move (CHECKLIST D0): the proof's shape, not the technique's name, so a
// price model can do without per-technique numbers. Exported (not used in pricing):
//   desc[0] log(branches)  cases the argument holds open at once (1 -> 0)
//   desc[1] log(depth)     longest implication chain of the proof (1 -> 0)
//   desc[2] search         log1p(patterns of this kind a human scans at the state) / log(N) (grid-size normalised)
//   desc[3] uniqueness     the proof assumes a unique solution
//   desc[4] counting       global counting / parity / set-equivalence argument
//   desc[5] contradiction  a candidate is assumed and a contradiction derived (forcing, Nishio, trial family,
//                          Medusa / colour wraps, BandLogic levels >= 1); direct implication chains are not
//   desc[6] held           log1p(candidates the move uses that are NOT written down; 0 when notes are written)
//   desc[7] coverage       written share of the candidates the move uses (1 = all annotated, 0 = none)
// Counts are taken over the full state (canonical: symmetry-invariant).
#include <algorithm>
#include "portable.hpp"
#include <cmath>

#include "solver.hpp"

namespace cs {

namespace {
double binom(int n, int k) {
    if (k < 0 || k > n) return 0.0;
    double r = 1.0;
    for (int i = 1; i <= k; ++i) r = r * (n - k + i) / i;
    return r;
}
}  // namespace

void Solver::desc_stats() {
    if (ds_version == version && ds_valid) return;
    ds_valid = true;
    ds_version = version;
    const int N = p.N, D = p.D;
    ds_cands = 0;
    ds_bivalue = 0;
    ds_empty = 0;
    for (int c = 0; c < N; ++c)
        if (!vals[c]) {
            ++ds_empty;
            const int k = popc(cand[c]);
            ds_cands += k;
            ds_bivalue += k == 2;
        }
    ds_open.assign(p.G, 0);
    for (int g = 0; g < p.G; ++g)
        for (int c : p.groups[g].cells) ds_open[g] += !vals[c];
    // per digit and orientation: complete lines still missing the digit (fish base sets)
    ds_lines.assign(2 * (D + 1), 0);
    for (int g : p.houses) {
        if (p.group_line[g] >= 2) continue;
        uint32_t m = 0;
        for (int c : p.groups[g].cells)
            if (!vals[c]) m |= cand[c];
        for (; m; m &= m - 1) ++ds_lines[p.group_line[g] * (D + 1) + lowdigit(m)];
    }
    // box-line intersections with >= 2 empty cells (pointing / claiming candidates)
    ds_inter = 0;
    for (int a : p.houses) {
        if (p.group_line[a] >= 2) continue;
        for (int b : p.houses) {
            if (p.group_line[b] < 2 || !p.group_overlap[(size_t)a * p.G + b]) continue;
            int k = 0;
            for (int c : p.groups[a].cells) k += !vals[c] && tbit(p.gbits(b), c);
            ds_inter += k >= 2;
        }
    }
    // subsets: sum over houses of C(open, n), n = 2..4
    for (int n = 0; n < 5; ++n) ds_subsets[n] = 0.0;
    for (int g : p.houses)
        for (int n = 2; n <= 4; ++n) ds_subsets[n] += binom(ds_open[g], n);
}

// candidates of cell c that are written down in notation context `mode` (0 direct, 1 notes): full notes ->
// all; notes_lazy -> only cells already marked; Snyder marks (direct phase, Snyder mode) -> digits confined to
// <= snyder_max cells of c's box
uint32_t Solver::written_marks(int c, int mode) const {
    if (vals[c]) return 0;
    if (!written_override.empty()) return written_override[c] & cand[c];  // a replay state's own marks
    if (mode == 1) return P.notes_lazy ? (marked[c] ? cand[c] : 0u) : cand[c];
    if (!snyder_on) return 0;
    uint32_t w = 0;
    for (int g : p.groups_of[c]) {
        if (p.group_line[g] != 2 || !p.groups[g].complete) continue;
        for (uint32_t mm = cand[c]; mm; mm &= mm - 1) {
            const int d = lowdigit(mm);
            int n = 0;
            for (int q : p.groups[g].cells) n += !vals[q] && (cand[q] & bit(d));
            if (n <= P.snyder_max) w |= bit(d);
        }
    }
    return w;
}

void Solver::describe(Move& m, const MoveBuf& b) {
    desc_stats();
    const int t = m.tech;
    const double logN = std::log((double)std::max(p.N, 2));
    double branches = 1, depth = 1, search = 0;
    bool uniq = false, counting = false, contra = false;
    const pm_long* xm = m.xm;
    auto meta = [&](int i) { return priced_meta(m) ? (double)m.meta[i] : 0.0; };
    switch (t) {
    case FULL_HOUSE:
        search = 1;
        break;
    case NAKED_D: case NAKED_DL: case NAKED_N:
        search = m.pc >= 0 ? std::max(1, popc(cand[m.pc])) : 1;  // the candidates of the cell
        if (t == NAKED_D || t == NAKED_DL) search = p.D;         // without notes: every digit is checked
        break;
    case HIDDEN_D: case HIDDEN_DL: case HIDDEN_N: {
        int best = p.D;  // empty cells of the smallest house the digit is hidden in
        if (m.pc >= 0)
            for (int g : p.groups_of[m.pc])
                if (p.groups[g].complete) best = std::min(best, ds_open[g]);
        search = std::max(best, 1);
        break;
    }
    case LOCKED:  // each box-line intersection, both directions (pointing, claiming)
        search = std::max(1, 2 * ds_inter);
        break;
    case INNIE_D: case INNIE_N: case INNIE_X: case PAIRARC: case NARY_D: case LINE_SCAN:
        search = std::max(1, (int)meta(0));
        break;
    case NPAIR: case HPAIR: search = ds_subsets[2]; break;
    case NTRIPLE: case HTRIPLE: search = ds_subsets[3]; break;
    case NQUAD: case HQUAD: search = ds_subsets[4]; break;
    case XWING: case SWORDFISH: case JELLYFISH: case FINNED_FISH: {
        const int n = t == XWING ? 2 : t == SWORDFISH ? 3 : t == JELLYFISH ? 4 : std::max(2, std::min(4, (int)meta(1) / 2));
        const int dg = m.pc >= 0 ? m.pv : (m.el_n ? (int)(b.elims[m.el_off] % 32) : 1);
        // base sets of size n among the lines missing the digit, both orientations
        search = binom(ds_lines[dg], n) + binom(ds_lines[(p.D + 1) + dg], n);
        if (t == FINNED_FISH) branches = 2;          // the fish, or a fin
        break;
    }
    case XYWING: branches = 2, depth = 2, search = (double)ds_bivalue * ds_bivalue; break;
    case XYZWING: branches = 3, depth = 2, search = (double)ds_bivalue * ds_bivalue; break;
    case N_WING: branches = std::max(pm_long(2), xm[0]), depth = 2, search = (double)ds_bivalue * ds_empty; break;
    case COLORING: case MULTI_COLOR: case MEDUSA: case COLOUR_ALGEBRA: case EQUAL_DIGITS:
        branches = 2;
        depth = std::max(1.0, meta(3));
        search = ds_cands;
        if (t == MEDUSA && xm[0] >= 1 && xm[0] <= 3) contra = true;  // a colour that contradicts itself
        if (t == COLOUR_ALGEBRA || t == EQUAL_DIGITS) branches = 1;
        break;
    case X_CHAIN: case XY_CHAIN: case AIC_CHAIN: case NICE_LOOP: case MENTAL_CHAIN: case REMOTE_PAIRS: case EMPTY_RECT:
    case ALS_AIC:
        branches = 2;
        depth = std::max(1.0, meta(3));
        search = ds_cands * std::max(1.0, meta(3));
        break;
    case UNIQUE_RECT: case BUG_PLUS1: case GURTH:
        uniq = true;
        branches = 2;
        search = t == BUG_PLUS1 ? 1 : ds_bivalue * ds_bivalue;
        break;
    case ALS_XZ: branches = 2, depth = 2, search = ds_empty * std::max(pm_long(1), xm[0]); break;
    case ALS_XYWING: branches = 3, depth = 2, search = ds_empty * std::max(pm_long(1), xm[0]); break;
    case DEATH_BLOSSOM: branches = std::max(pm_long(2), xm[2]), depth = 2, search = ds_empty * std::max(pm_long(1), xm[0]); break;
    case SUE_DE_COQ: branches = 2, search = ds_empty; break;
    case FIREWORKS: branches = 3, depth = 2, search = (double)ds_empty * 16.0; break;  // A, B or X per digit
    case WEIGHTED_SUMS:  // facts combined (depth), multiplicity as counting
        depth = std::max(pm_long(1), xm[0]);
        counting = xm[2] >= 2;
        search = (double)p.houses.size() * p.houses.size();
        break;
    case LINE_CLUES:  // fillings of the line weighed (cases), the line's clues combined
        branches = std::max(pm_long(1), std::min(xm[2], pm_long(1000000)));
        search = (double)p.houses.size();
        break;
    case LINE_SETS:  // lines' digit-set options weighed jointly in a house
        branches = std::max(pm_long(1), std::min(xm[2], pm_long(100000)));
        search = (double)std::max(pm_long(1), xm[1]) * p.houses.size();
        break;
    case CLIQUE_HOUSE:  // a virtual house: subsets of mutually different cells scanned
        search = ds_subsets[4] + ds_bivalue * ds_bivalue;
        break;
    case COMBO_POS:  // the cage's fillings (cases weighed), digit-set subsets of a house scanned
        branches = std::max(pm_long(1), std::min(xm[5], pm_long(100000)));
        counting = true;
        search = ds_subsets[2] + ds_subsets[3];
        break;
    case HUMAN_CASE:  // refutation: one case, contradiction; forcing: surviving cases agree
        branches = std::max(pm_long(1), xm[0]);
        depth = std::max(pm_long(1), xm[1]);
        contra = m.code == 5501;
        search = m.code == 5501 ? (double)ds_cands : m.code == 5502 ? (double)ds_empty : (double)ds_empty * 4.0;
        break;
    case APE: branches = 2, search = ds_empty * ds_empty / 2.0; break;
    case CHUTE_RP: branches = 2, depth = 2, search = ds_bivalue * ds_bivalue; break;
    case POM: branches = std::max(pm_long(1), xm[1]), search = std::max(pm_long(1), xm[1]); break;
    case SUM_COMBO: case ARROW_COMBO: case SET_COMBO: case EQSUM_COMBO: case TABLE_COMBO: case SANDWICH_COMBO:
    case XSUM_COMBO: case SKYLINE_COMBO: case COUNT_COMBO: case CAGE_COMBO: case COMBO_LOCK:
        branches = std::max(pm_long(1), std::min(xm[2], pm_long(100000)));  // combinations listed
        search = std::max(1, (int)meta(0));
        break;
    case LOL_COMBO:
        counting = true;
        search = std::max(1, (int)meta(0));
        break;
    case LINE_D: case MENTAL_D:
        depth = std::max(pm_long(1), xm[1]);
        search = p.D;
        break;
    case LINE_RANGE: case LINE_CLASS: case SUM_BOUND: case DOMINO:
        search = std::max(1, (int)meta(0));
        break;
    case CLASS_COUNT: case DIGIT_COUNT:
        counting = true;
        search = std::max(1, (int)meta(0));
        break;
    case RULE_INTERSECT:
        branches = std::max(pm_long(1), std::min(xm[3], pm_long(100000)));  // joint combinations enumerated
        search = binom((int)(p.nary.size() + p.houses.size()), (int)std::max(pm_long(2), std::min(xm[2], pm_long(4))));  // unit sets
        break;
    case SUM_ALGEBRA:
        depth = std::max(pm_long(1), xm[3]);
        search = std::max(pm_long(1), xm[1]) * std::max(pm_long(1), xm[0]);
        break;
    case BAND_LOGIC:
        branches = std::max(pm_long(1), std::min(xm[6], pm_long(1000000000)));
        depth = xm[5] + 1;
        contra = xm[5] >= 1;
        search = std::max(pm_long(1), xm[4]);
        break;
    case SHORT_TRIAL:
        contra = true, branches = 2, depth = std::max(pm_long(1), xm[0]), search = ds_bivalue;
        break;
    case EITHER_WAY:
        branches = 2, depth = std::max(pm_long(1), std::max(xm[0], xm[1])), search = ds_bivalue;
        break;
    case FORCING: case DYN_FORCING: case NESTED_FORCING: case WHAT_IF:
        branches = std::max(pm_long(2), xm[1]);
        depth = std::max(1.0, (double)xm[4] / std::max(pm_long(1), xm[1]));  // propagation steps per branch
        contra = xm[5] > 0 || t != WHAT_IF;
        search = (double)ds_empty * std::max(pm_long(2), xm[1]);
        break;
    case NISHIO:
        contra = true, branches = 2, depth = std::max(pm_long(1), xm[1]), search = ds_cands;
        break;
    case TRIAL:
        contra = true, branches = std::max(2, (int)meta(2)), depth = std::max(1.0, meta(3)), search = ds_cands;
        break;
    case GUESS:
        branches = m.pc >= 0 ? std::max(2, popc(cand[m.pc])) : 2, search = ds_empty;
        break;
    case SNYDER_D:
        search = p.D;
        break;
    default:
        search = 1;
        break;
    }
    if (!m.has_meta) {  // export a structural meta for every technique (not priced: meta_synth, see priced_meta)
        std::vector<int> cs(b.pats.begin() + m.pat_off, b.pats.begin() + m.pat_off + m.pat_n);
        uint32_t dg = 0;
        for (int i = 0; i < m.el_n; ++i) {
            const uint32_t e = b.elims[m.el_off + i];
            cs.push_back((int)(e / 32));
            dg |= bit((int)(e % 32));
        }
        if (m.pc >= 0) cs.push_back(m.pc), dg |= bit(m.pv);
        std::sort(cs.begin(), cs.end());
        cs.erase(std::unique(cs.begin(), cs.end()), cs.end());
        int ng = 0;  // houses holding >= 2 of the cells
        for (int g : p.houses) {
            int k = 0;
            for (int c : cs) k += tbit(p.gbits(g), c);
            ng += k >= 2;
        }
        const bool arith = m.nk == NM_NARY || m.nk == NM_INNIE || m.nk == NM_OUTIE;
        m.meta[0] = std::max(1, (int)cs.size());
        m.meta[1] = std::max(1, ng);
        m.meta[2] = std::max(1, popc(dg));
        m.meta[3] = 0;  // links: the chain length is desc[1]
        m.meta[4] = 0;
        m.meta[5] = arith ? 1 : 0;
        m.meta[6] = 0;
        m.meta[7] = is_direct(m.tech) ? 0 : 1;  // notes
        m.spread = 1.0;
        m.has_meta = true;
        m.meta_synth = true;
    }
    {  // notation: candidates the move relies on (pattern + target cells), how many are written down
        const int t = m.tech;
        int mode = desc_mode;
        if (!written_override.empty()) mode = 1;  // marks given explicitly
        else if (mode < 0)  // state_moves: direct-stage techniques use no notes, the others assume full notes
            mode = (is_direct(t) || t == MENTAL_NOTES || t == SNYDER_D || t == HIDDEN_D || t == NAKED_D) ? 0 : 1;
        // case splits: their pattern cells depend on which of several equivalent branchings was kept (not
        // symmetry-invariant) -> footprint = the target cells only
        const bool split = t == EITHER_WAY || t == WHAT_IF || t == SHORT_TRIAL || t == FORCING || t == DYN_FORCING ||
                           t == NESTED_FORCING || t == NISHIO || t == TRIAL || t == GUESS || t == MENTAL_CHAIN;
        std::vector<int> fp;
        if (!split) fp.assign(b.pats.begin() + m.pat_off, b.pats.begin() + m.pat_off + m.pat_n);
        for (int i = 0; i < m.el_n; ++i) fp.push_back((int)(b.elims[m.el_off + i] / 32));
        if (m.pc >= 0) fp.push_back(m.pc);
        std::sort(fp.begin(), fp.end());
        fp.erase(std::unique(fp.begin(), fp.end()), fp.end());
        pm_long tot = 0, wr = 0;
        const bool hidden1 = (t == HIDDEN_D || t == HIDDEN_DL || t == HIDDEN_N) && m.pc >= 0;
        if (hidden1) {  // hidden single: the digit's open places in the house (what the eye scans)
            int g = (m.nk == NM_GROUP && m.na >= 0 && m.na < p.G) ? m.na : -1;
            if (g < 0)
                for (int h : p.groups_of[m.pc])
                    if (p.groups[h].complete && (g < 0 || p.groups[h].cells.size() < p.groups[g].cells.size())) g = h;
            const uint32_t db = bit(m.pv);
            if (g >= 0)
                for (int c : p.groups[g].cells) {
                    if (vals[c] || !(cand[c] & db)) continue;
                    ++tot;
                    wr += (written_marks(c, mode) & db) != 0;
                }
        } else
            for (int c : fp) {
                if (vals[c]) continue;
                tot += popc(cand[c]);
                wr += popc(written_marks(c, mode) & cand[c]);
            }
        m.desc[6] = std::log1p((double)(tot - wr));
        m.desc[7] = tot ? (double)wr / (double)tot : 1.0;
        // D5 enumeration: the sum rules (cages, arrows, sum / x-sum / sandwich / equal-sum lines) whose cells meet the
        // footprint; how many assignments each still allows under the current candidates (GAC count, cached); the
        // largest, log1p. Rule-agnostic: only the instance's own arithmetic, no variant label.
        double best = 0.0;
        auto scan_list = [&](const std::vector<NConstraint>& list) {
            uint32_t dom[64];
            for (const NConstraint& k : list) {
                const bool sumlike = k.type == NT_SUM || k.type == NT_ARROW || k.type == NT_EQSUM || k.type == NT_XSUM ||
                                     k.type == NT_SANDWICH;
                if (!sumlike || k.nv() > 20) continue;
                bool meet = false;
                for (int c : k.vars)
                    if (std::binary_search(fp.begin(), fp.end(), c)) { meet = true; break; }
                if (!meet) continue;
                nary_dom(k, dom);
                const GacOut& o = gac_cached(k, dom);
                best = std::max(best, (double)std::min<pm_long>(o.count, pm_long(1000000000)));
            }
        };
        scan_list(p.nary);
        scan_list(p.cage_nary);
        m.enumv = std::log1p(best);
    }
    m.has_desc = true;
    m.desc[0] = std::log(std::max(1.0, branches));
    m.desc[1] = std::log(std::max(1.0, depth));
    m.scan = std::max(0.0, search);
    m.desc[2] = std::log1p(std::max(0.0, search)) / logN;
    m.desc[3] = uniq ? 1.0 : 0.0;
    m.desc[4] = counting ? 1.0 : 0.0;
    m.desc[5] = contra ? 1.0 : 0.0;
}

}  // namespace cs
