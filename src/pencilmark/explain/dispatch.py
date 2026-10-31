"""Handler table and registration, explain(), technique keys, self-checks. (split from explain.py)"""

from __future__ import annotations

import re

from .. import solver as S
from ..metrics import FAMILIES, family_of
from ..model import bit
from .base import ANNOTATION, CONCEPTS, EXTRA_FAMILY, FAMILY_DISPLAY, Ctx, Namer, _an, _generic, rel_label
from .catalog import _LINE_KEY, _REL_KEY, _VARIANT_LESSONS, CATALOG, SW, _confirmed, technique_info
from .chains import _h_als_xywing, _h_als_xz, _h_chain, _h_death_blossom, _h_mental_chain
from .combos import _h_combo, _h_combo_lock, _h_innie, _h_lol
from .grid import Rule, State, _as_state, derived, replay
from .notes import _h_bug, _h_coloring, _h_fish, _h_locked, _h_pairarc, _h_subset, _h_ur, _h_wing
from .records import (
    _h_band_logic,
    _h_chute_rp,
    _h_class_colour,
    _h_class_count,
    _h_clique_house,
    _h_clue_facts,
    _h_colour_classes,
    _h_combo_positions,
    _h_domino,
    _h_empty_rect,
    _h_fireworks,
    _h_forcing,
    _h_line_clues,
    _h_line_sets,
    _h_medusa,
    _h_mental_notes,
    _h_nishio,
    _h_pattern_named,
    _h_rule_intersect,
    _h_snyder,
    _h_sum_algebra,
    _h_sum_bound,
    _h_weighted_sums,
)
from .singles import (
    _h_full_house,
    _h_hidden_direct,
    _h_hidden_notes,
    _h_mental,
    _h_naked_direct,
    _h_naked_notes,
    _h_nary_direct,
    _h_pointing_direct,
    _rule_from_move,
)
from .trial import (
    _h_digit_count,
    _h_either_way,
    _h_equal_digits,
    _h_guess,
    _h_line_class,
    _h_line_scan,
    _h_snyder_marks,
    _h_take_notes,
    _h_trial,
)

HANDLERS = {
    S.FULL_HOUSE: _h_full_house,
    S.NAKED_D: _h_naked_direct,
    S.HIDDEN_D: _h_hidden_direct,
    S.NAKED_DL: _h_pointing_direct,
    S.HIDDEN_DL: _h_pointing_direct,
    S.TAKE_NOTES: _h_take_notes,
    S.SNYDER_MARKS: _h_snyder_marks,
    S.NAKED_N: _h_naked_notes,
    S.HIDDEN_N: _h_hidden_notes,
    S.LOCKED: _h_locked,
    S.NPAIR: _h_subset,
    S.HPAIR: _h_subset,
    S.NTRIPLE: _h_subset,
    S.HTRIPLE: _h_subset,
    S.NQUAD: _h_subset,
    S.HQUAD: _h_subset,
    S.XWING: _h_fish,
    S.SWORDFISH: _h_fish,
    S.JELLYFISH: _h_fish,
    S.FINNED_FISH: _h_fish,
    S.XYWING: _h_wing,
    S.XYZWING: _h_wing,
    S.COLORING: _h_coloring,
    S.PAIRARC: _h_pairarc,
    S.TRIAL: _h_trial,
    S.SHORT_TRIAL: _h_trial,
    S.GUESS: _h_guess,
    S.INNIE_D: _h_innie,
    S.INNIE_N: _h_innie,
    S.INNIE_X: _h_innie,
    S.CAGE_COMBO: _h_combo,
    S.SUM_COMBO: _h_combo,
    S.ARROW_COMBO: _h_combo,
    S.SET_COMBO: _h_combo,
    S.EQSUM_COMBO: _h_combo,
    S.TABLE_COMBO: _h_combo,
    S.SANDWICH_COMBO: _h_combo,
    S.XSUM_COMBO: _h_combo,
    S.SKYLINE_COMBO: _h_combo,
    S.COUNT_COMBO: _h_combo,
    S.LINE_RANGE: _h_combo,
    S.LOL_COMBO: _h_lol,
    S.COMBO_LOCK: _h_combo_lock,
    S.NARY_D: _h_nary_direct,
    S.LINE_D: _h_mental,
    S.MENTAL_D: _h_mental,
    S.X_CHAIN: _h_chain,
    S.XY_CHAIN: _h_chain,
    S.AIC_CHAIN: _h_chain,
    S.NICE_LOOP: _h_chain,
    S.ALS_AIC: _h_chain,
    S.UNIQUE_RECT: _h_ur,
    S.BUG_PLUS1: _h_bug,
    S.ALS_XZ: _h_als_xz,
    S.ALS_XYWING: _h_als_xywing,
    S.DEATH_BLOSSOM: _h_death_blossom,
}


for _code, _h, _name, _lesson in (
    (
        "DIGIT_COUNT",
        _h_digit_count,
        "Digit counting",
        "Count how many copies of a digit some units must hold and how many the houses covering them can take; "
        "when the numbers match, the digit is pinned to the pattern.",
    ),
    (
        "EQUAL_DIGITS",
        _h_equal_digits,
        "Equal cells",
        "Two cells can be forced to hold the same unknown digit; then each keeps only the candidates both share.",
    ),
    (
        "LINE_SCAN",
        _h_line_scan,
        "Local line scan",
        "On long lines, look at a few consecutive cells at a time; local windows often carry the whole logic.",
    ),
):
    HANDLERS[getattr(S, _code)] = _h
    CONCEPTS.setdefault(getattr(S, _code), (_name, _lesson))
    EXTRA_FAMILY.setdefault(getattr(S, _code), "fish+wings" if _code == "DIGIT_COUNT" else "intersections+combos")
HANDLERS[S.LINE_CLASS] = _h_line_class
CONCEPTS.setdefault(
    S.LINE_CLASS,
    (
        "Line classes",
        "Group digits into classes (low/high, odd/even, thirds) "
        "and reason about the pattern of classes along a line before exact digits.",
    ),
)
HANDLERS[S.EITHER_WAY] = _h_either_way
CONCEPTS.setdefault(
    S.EITHER_WAY,
    (
        "Either way (two-case check)",
        "When something must be one of two things, follow both "
        "options a few steps; whatever happens in both branches is true.",
    ),
)
HANDLERS[S.MENTAL_CHAIN] = _h_mental_chain
CONCEPTS.setdefault(
    S.MENTAL_CHAIN,
    (
        "Chain without notes",
        "A couple of 'if this, then that' steps can "
        "be held in the head: follow what each cell can still be until the "
        "chain forces a digit.",
    ),
)

_X_HANDLERS = {
    "CLUE_FACTS": (
        _h_clue_facts,
        "clue_facts",
        "intersections+combos",
        ("Clue facts", "Some digits are ruled out by the clues alone, before any digit of the grid is used."),
    ),
    "CLUE_SHAPE": (
        _h_clue_facts,
        "clue_shape",
        "intersections+combos",
        (
            "Clue shape",
            "Cells of one rule that share a house need different digits; when the rule leaves too few, some go.",
        ),
    ),
    "CLASS_COLOUR": (
        _h_class_colour,
        "class_colouring",
        "chains",
        (
            "Low / high and odd / even colouring",
            "Rules that always join a low and a high digit (or an odd and an even one) colour cells in two classes; a "
            "known cell or a house's count fixes which colour is which.",
        ),
    ),
    "WEIGHTED_SUMS": (
        _h_weighted_sums,
        "weighted_sums",
        "intersections+combos",
        (
            "Weighted sums",
            "Add and "
            "subtract whole houses and rule totals, counting some cells more than once, until a short sum "
            "remains.",
        ),
    ),
    "LINE_CLUES": (
        _h_line_clues,
        "outside_clues_together",
        "subsets",
        ("Outside clues together", "A line with clues at both ends: its fillings must satisfy every clue at once."),
    ),
    "LINE_SETS": (
        _h_line_sets,
        "renban_sets",
        "subsets",
        (
            "Renban sets",
            "Renbans meeting in a house use different "
            "digits there; their possible runs, taken together, rule digits out.",
        ),
    ),
    "CLIQUE_HOUSE": (
        _h_clique_house,
        "clique_house",
        "subsets",
        (
            "Clique house",
            "Cells that must all differ from "
            "each other act like a house: as many cells as digits means each digit once.",
        ),
    ),
    "COMBO_POS": (
        _h_combo_positions,
        "combo_positions",
        "subsets",
        (
            "Cage combination positions",
            "A cage's possible "
            "combinations limit how many digits of a small set it can hold in a house; the rest must go elsewhere.",
        ),
    ),
    "HUMAN_CASE": (
        _h_forcing,
        "case_analysis",
        "chains",
        (
            "Case analysis",
            "Try a digit (or each option of a cell or "
            "of a digit in a house) and follow it a few steps with singles and the rules; a case that breaks is "
            "false, and what every surviving case agrees on is true.",
        ),
    ),
    "FIREWORKS": (
        _h_fireworks,
        "fireworks",
        "fish+wings",
        (
            "Fireworks",
            "A digit with one spot in a row and one in a "
            "column outside the box where they cross must be in one of those spots or the crossing cell; three "
            "such digits fill the three cells.",
        ),
    ),
    "BAND_LOGIC": (
        _h_band_logic,
        "band_logic",
        "chains",
        (
            "Band logic",
            "Take a band's rows (or columns), its "
            "boxes and the rules inside together: house totals minus the cages fix sums of the other cells, "
            "and only fillings consistent with all of them remain.",
        ),
    ),
    "SNYDER_D": (
        _h_snyder,
        "snyder_single",
        "intersections+combos",
        (
            "Snyder marks",
            "Mark only digits confined "
            "to two cells of a box; coinciding pairs and aligned pairs give placements without full notes.",
        ),
    ),
    "SUM_ALGEBRA": (
        _h_sum_algebra,
        "sum_algebra",
        "intersections+combos",
        (
            "Sum algebra",
            "Add up whole houses (45 each) and compare with the totals of the rules inside them; the "
            "difference bounds the remaining cells or the rules' sums.",
        ),
    ),
    "RULE_INTERSECT": (
        _h_rule_intersect,
        "rule_intersection",
        "intersections+combos",
        (
            "Rules together",
            "Take two overlapping rules (or a rule and a house) together: only digit combinations that "
            "satisfy both remain.",
        ),
    ),
    "MULTI_COLOR": (
        _h_pattern_named(
            "multi-colouring",
            "Two separate colourings of the same digit (each along "
            "conjugate pairs) touch: one colour of the first sees one colour of the second, so they are not both "
            "true and one of their opposites is; cells seeing both opposites lose the digit.",
        ),
        "multi_colouring",
        "chains",
        (
            "Multi-Colouring",
            "Colour two separate conjugate-pair networks of a digit and use how their colours see each other.",
        ),
    ),
    "WHAT_IF": (
        _h_forcing,
        "what_if",
        "trial",
        (
            "What if",
            "Try both options of a two-way choice with simple logic "
            "(singles, rule arithmetic, intersections); a case that breaks drops, a conclusion both share holds.",
        ),
    ),
    "MENTAL_NOTES": (
        _h_mental_notes,
        "notes_in_head",
        "subsets",
        (
            "Notes in your head",
            "Do a pair, pointing or "
            "combination step on the candidates you keep in mind, then place the single it leaves.",
        ),
    ),
    "FORCING": (
        _h_forcing,
        "forcing_chain",
        "trial",
        (
            "Forcing Chain",
            "Try every option of a cell or every place of "
            "a digit in a house; whatever all surviving options agree on is true.",
        ),
    ),
    "DYN_FORCING": (
        _h_forcing,
        "dynamic_forcing_chain",
        "trial",
        (
            "Dynamic Forcing Chain",
            "Case analysis where each case is followed with ordinary techniques, not only singles.",
        ),
    ),
    "NESTED_FORCING": (
        _h_forcing,
        "nested_forcing_chain",
        "trial",
        (
            "Nested Forcing Chain",
            "Case analysis whose cases use further case analyses inside them -- a computer-strength technique.",
        ),
    ),
    "NISHIO": (
        _h_nishio,
        "nishio_forcing_net",
        "trial",
        (
            "Nishio Forcing Net",
            "Assume one digit in a cell and follow "
            "only that digit; if it runs out of places, the assumption was false.",
        ),
    ),
    "MEDUSA": (
        _h_medusa,
        "3d_medusa",
        "chains",
        (
            "3D Medusa",
            "Colouring across several digits: bivalue cells and two-place digits form one two-coloured network.",
        ),
    ),
    "COLOUR_ALGEBRA": (
        _h_colour_classes,
        "colour_algebra",
        "chains",
        (
            "Equal-digit colouring",
            "Cells forced to be equal share one colour; the colour's possible digits are what all its cells allow.",
        ),
    ),
    "SUM_BOUND": (
        _h_sum_bound,
        "sum_bounds",
        "intersections+combos",
        (
            "Min/max bounds",
            "Smallest and largest "
            "possible sums (triangular numbers for different digits) bound each cell of a sum rule.",
        ),
    ),
    "CLASS_COUNT": (
        _h_class_count,
        "class_counting",
        "intersections+combos",
        ("Odd/even counting", "Count digits by class (odd/even, low/high): houses need fixed numbers of each."),
    ),
    "DOMINO": (
        _h_domino,
        "domino_logic",
        "intersections+combos",
        (
            "Domino logic",
            "Reason about pairs of cells "
            "joined by a dot or sum clue: which digit pairs fit, and what they force nearby.",
        ),
    ),
    "N_WING": (
        _h_pattern_named(
            "bent set wing",
            "A wing of several cells holding exactly as many digits: all digits "
            "but one are confined to cells that see each other, so the last one is forced into the wing.",
        ),
        "wxyz_wing",
        "fish+wings",
        ("WXYZ-Wing", "Bent sets of 4+ cells generalising XY- and XYZ-Wings."),
    ),
    "SUE_DE_COQ": (
        _h_pattern_named(
            "Sue de Coq",
            "Box-line intersection cells plus a line group and a box group "
            "with disjoint digits lock as many digits as cells.",
        ),
        "sue_de_coq",
        "fish+wings",
        ("Sue de Coq", "Two-sector disjoint subsets around a box-line intersection."),
    ),
    "APE": (
        _h_pattern_named(
            "aligned pair exclusion",
            "Every combination of the two cells' digits is checked; a "
            "digit with no combination that leaves the cells seeing both alive goes.",
        ),
        "aligned_pair_exclusion",
        "fish+wings",
        ("Aligned Pair Exclusion", "Test the value pairs of two cells against the cells they both see."),
    ),
    "CHUTE_RP": (
        _h_chute_rp,
        "chute_remote_pairs",
        "chains",
        ("Chute Remote Pairs", "Remote pairs inside a band or stack."),
    ),
    "POM": (
        _h_pattern_named(
            "pattern overlay",
            "Every placement pattern of this digit (one per row, column and box) "
            "consistent with the candidates was listed; these candidates are in none of them.",
        ),
        "pattern_overlay",
        "trial",
        ("Pattern Overlay", "List all templates of a digit and keep only cells some template uses."),
    ),
    "GURTH": (
        _h_pattern_named(
            "symmetry",
            "The givens are symmetric under a grid symmetry with a digit swap, so the "
            "unique solution is too; candidates breaking the symmetry go.",
        ),
        "gurth",
        "fish+wings",
        ("Gurth's Theorem", "Symmetric placement: a symmetric puzzle has a symmetric solution."),
    ),
}

for _code, (_h, _key, _fam, _concept) in _X_HANDLERS.items():
    HANDLERS[getattr(S, _code)] = _h
    CONCEPTS.setdefault(getattr(S, _code), _concept)
    EXTRA_FAMILY.setdefault(getattr(S, _code), _fam)

_FAM_IDX = {"singles": 0, "intersections+combos": 1, "subsets": 2, "fish+wings": 3, "chains": 4, "ALS": 5, "trial": 6}
for _code, (_h, _key, _fam, _concept) in _X_HANDLERS.items():
    CATALOG.setdefault(_key, (_concept[0], {"other": []}, _FAM_IDX[_fam], [], []))
CATALOG["forcing_chain"][1]["sudokuwiki"] = ["Cell Forcing Chains", "Unit Forcing Chains"]
CATALOG["forcing_chain"][3].extend([SW + "Cell_Forcing_Chains", SW + "Unit_Forcing_Chains"])
CATALOG["dynamic_forcing_chain"][1]["HoDoKu"] = ["Dynamic Forcing Chain"]
CATALOG["nested_forcing_chain"][1]["Sudoku Snake"] = ["Dynamic Unit Nested Forcing Chains II"]
CATALOG["nishio_forcing_net"][3].append(SW + "Nishio_Forcing_Chains")
CATALOG["3d_medusa"][1]["sudokuwiki"] = ["3D Medusa"]
CATALOG["3d_medusa"][3].append(SW + "3D_Medusa")
CATALOG["sue_de_coq"][3].append(SW + "Sue_de_Coq")
CATALOG["fireworks"][1]["sudokuwiki"] = ["Fireworks"]
CATALOG["fireworks"][3].append(SW + "Fireworks")
CATALOG["aligned_pair_exclusion"][3].append(SW + "Aligned_Pair_Exclusion")
CATALOG["wxyz_wing"][3].append(SW + "WXYZ_Wing")
CATALOG["pattern_overlay"][3].append(SW + "Pattern_Overlay")
CATALOG["chute_remote_pairs"][3].append(SW + "Chute_Remote_Pairs")
CATALOG["gurth"][3].append(SW + "Gurths_Theorem")
CATALOG["multi_colouring"][1]["sudokuwiki"] = ["Multi-Colouring"]
CATALOG["multi_colouring"][3].append(SW + "Multi_Colouring")

HANDLERS[S.REMOTE_PAIRS] = _h_chain
HANDLERS[S.EMPTY_RECT] = _h_empty_rect
CONCEPTS.setdefault(
    S.REMOTE_PAIRS,
    (
        "Remote Pairs",
        "A chain of cells holding the same pair: alternate cells "
        "take alternate digits, so a cell seeing both ends of an odd-length run "
        "loses both digits.",
    ),
)
CONCEPTS.setdefault(
    S.EMPTY_RECT,
    (
        "Empty Rectangle",
        "A box whose candidates for a digit form a cross works "
        "as one end of a strong link; with a conjugate pair it removes the digit "
        "where the two meet.",
    ),
)
EXTRA_FAMILY.setdefault(S.REMOTE_PAIRS, "chains")
EXTRA_FAMILY.setdefault(S.EMPTY_RECT, "chains")


def _engine_override(ctx, out):
    """Attach the engine's justification; its structure fills whatever the reconstruction lacks."""
    if not ctx.raw_engine:
        return out
    J = out["J"]
    J["engine"] = ctx.raw_engine
    if not out["verified"]:
        for k in ("base_units", "cover_units", "als", "rcc", "constraints"):
            if ctx.engine.get(k) and not J.get(k):
                J[k] = ctx.engine[k]
    pc = [c for c in ctx.engine.get("pattern_cells") or () if isinstance(c, int)]
    if pc:
        vis = out["visual"]
        vis["pattern"] = [ctx.nm.cell(c) for c in ctx.nm.sort(pc)]
    out["derived"] = not ctx.used_engine
    return out


def explain(step, puzzle, state):
    """Explanation dict for one solver step (state = grid before the step; see replay())."""
    if not hasattr(puzzle, "groups_of"):
        puzzle.finalize()
    puzzle = derived(puzzle)
    st = _as_state(puzzle, state)
    if st.p is not puzzle:
        st = State(puzzle, st.vals, st.cand, st.mode)
        st.idx, st.lost = getattr(state, "idx", 0), getattr(state, "lost", {})
    ctx = Ctx(step, puzzle, st)
    h = HANDLERS.get(ctx.tech, _generic)
    try:
        out = h(ctx)
    except Exception as e:  # never let a reconstruction bug break the stream
        out = _generic(ctx)
        out["error"] = f"{type(e).__name__}: {e}"
    out.setdefault("derived", True)
    out = _engine_override(ctx, out)
    name, lesson = CONCEPTS.get(ctx.tech, (S.TECH_NAMES.get(ctx.tech, "?"), ""))
    fam = (
        FAMILIES[family_of(ctx.tech)][0]
        if ctx.tech not in (S.TAKE_NOTES, S.GUESS, S.SNYDER_MARKS)
        else ("trial" if ctx.tech == S.GUESS else "setup")
    )
    if not any(ctx.tech in ts for _, ts in FAMILIES) and ctx.tech in EXTRA_FAMILY:
        fam = EXTRA_FAMILY[ctx.tech]
    try:
        tkey = _technique_key(ctx, out)
    except Exception:
        tkey = "rule_logic"
    tinfo = technique_info(tkey)
    if out["J"].get("pattern"):
        tinfo["pattern"] = out["J"]["pattern"]
        if out["J"].get("pattern_type"):
            tinfo["pattern_type"] = out["J"]["pattern_type"]
    name = tinfo["name"]
    out["short"], out["teach"] = _an(out["short"]), _an(out["teach"])
    res = {
        "step": st.idx,
        "technique": tinfo,
        "engine_technique": S.TECH_NAMES.get(ctx.tech, str(ctx.tech)),
        "mode": step.mode,
        "short": out["short"],
        "teach": out["teach"],
        "concept": {
            "family": fam,
            "family_name": FAMILY_DISPLAY.get(fam, fam),
            "technique": name,
            "lesson": lesson if tkey not in _VARIANT_LESSONS else _VARIANT_LESSONS[tkey],
        },
        "visual": out["visual"],
        "annotation": dict(ANNOTATION),
        "justification": _jsonable(out["J"]),
        "derived": out.get("derived", True),
        "verified": bool(out["verified"]),
    }
    if "error" in out:
        res["error"] = out["error"]
    return res


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in x]
    if isinstance(x, Rule):
        return x.label
    return x


def explain_all(puzzle, steps):
    return [explain(step, puzzle, st) for _, step, st in replay(puzzle, steps)]


def _rule_key(rule):
    if rule is None:
        return "rule_logic"
    return _LINE_KEY.get(rule.line_kind or rule.kind, "rule_logic")


def _technique_key(ctx, out):
    """Which named technique this explanation teaches (sub-pattern / variant aware)."""
    t, p, J = ctx.tech, ctx.p, out["J"]
    if t == S.FULL_HOUSE:
        gi = ctx.gi(ctx.m.name)
        return "implied_house" if gi is not None and p.groups[gi].kind == "implied" else "full_house"
    if t in (S.HIDDEN_D, S.HIDDEN_N):
        gi = ctx.gi(ctx.m.name)
        if gi is not None and p.groups[gi].kind == "implied":
            return "implied_house"
        return (
            "cross_hatching" if t == S.HIDDEN_D and gi is not None and p.groups[gi].kind == "box" else "hidden_single"
        )
    if t in (S.NAKED_D, S.NAKED_N):
        return "naked_single"
    if t in (S.NAKED_DL, S.HIDDEN_DL):
        return "single_after_pointing"
    if t == S.TAKE_NOTES:
        return "pencil_marks"
    if t == S.SNYDER_MARKS:
        return "snyder_marks"
    if t == S.LOCKED:
        bu, cu = J.get("base_units") or [], J.get("cover_units") or []
        if bu and cu and p.groups[cu[0]].kind == "cage":
            return "cage_must_contain"
        if bu and p.groups[bu[0]].kind in ("row", "col"):
            return "claiming"
        return "pointing"
    simple = {
        S.NPAIR: "naked_pair",
        S.NTRIPLE: "naked_triple",
        S.NQUAD: "naked_quad",
        S.HPAIR: "hidden_pair",
        S.HTRIPLE: "hidden_triple",
        S.HQUAD: "hidden_quad",
        S.XYWING: "xy_wing",
        S.XYZWING: "xyz_wing",
        S.COLORING: "simple_colouring",
        S.UNIQUE_RECT: "unique_rectangle",
        S.BUG_PLUS1: "bug_plus_1",
        S.ALS_XZ: "als_xz",
        S.ALS_XYWING: "als_xy_wing",
        S.DEATH_BLOSSOM: "death_blossom",
        S.ALS_AIC: "als_chain",
        S.TRIAL: "trial",
        S.SHORT_TRIAL: "short_contradiction",
        S.GUESS: "guess",
        S.LOL_COMBO: "law_of_leftovers",
        S.INNIE_D: "rule_of_45",
        S.INNIE_N: "rule_of_45",
        S.INNIE_X: "rule_of_45",
        S.CAGE_COMBO: "killer_combinations",
    }
    if t in simple:
        return simple[t]
    if t in (S.XWING, S.SWORDFISH, S.JELLYFISH, S.FINNED_FISH):
        return out.get("pattern_key") or {S.XWING: "x_wing", S.SWORDFISH: "swordfish", S.JELLYFISH: "jellyfish"}.get(
            t, "finned_x_wing"
        )
    if t in (S.X_CHAIN, S.XY_CHAIN, S.AIC_CHAIN, S.NICE_LOOP):
        return out.get("pattern_key") or {S.X_CHAIN: "x_chain", S.XY_CHAIN: "xy_chain", S.NICE_LOOP: "nice_loop"}.get(
            t, "aic"
        )
    if t == S.MENTAL_D:
        sub = ctx.xm.get("subset") or 0
        return "pair_in_head" if sub == 2 else "triple_in_head" if sub == 3 else "pointing_in_head"
    if t in (
        S.LINE_D,
        S.NARY_D,
        S.SUM_COMBO,
        S.ARROW_COMBO,
        S.SET_COMBO,
        S.EQSUM_COMBO,
        S.TABLE_COMBO,
        S.SANDWICH_COMBO,
        S.XSUM_COMBO,
        S.SKYLINE_COMBO,
        S.COUNT_COMBO,
        S.LINE_RANGE,
        S.COMBO_LOCK,
    ):
        if t == S.NARY_D:
            r = _rule_from_move(ctx)
            return "cage_arithmetic" if r is not None and r.kind in ("cage", "sum") else _rule_key(r)
        if t == S.COMBO_LOCK:
            r = _rule_from_move(ctx)
            return "cage_must_contain" if r is None or r.kind in ("cage", "sum", "innie") else _rule_key(r)
        if t == S.LINE_D:
            cons = J.get("constraints") or []
            kinds = [c.get("type") for c in cons if isinstance(c, dict)]
            return _LINE_KEY.get(kinds[0], "rule_logic") if kinds else "pair_rule"
        return _rule_key(_rule_from_move(ctx))
    if t == S.PAIRARC:
        bc = J.get("base_cells") or []
        tg = [c for c, _ in ctx.elims]
        lab = rel_label(p, bc[0], tg[0]) if bc and tg else ""
        return _REL_KEY.get(lab.split(" / ")[0], "pair_rule")
    if t == S.MENTAL_CHAIN:
        return "chain_without_notes"
    if t == S.EITHER_WAY:
        return "either_way"
    if t == S.LINE_CLASS:
        return _rule_key(_rule_from_move(ctx))
    if t == S.DIGIT_COUNT:
        return "digit_counting"
    if t == S.EQUAL_DIGITS:
        return "equal_cells"
    if t == S.LINE_SCAN:
        return _rule_key(_rule_from_move(ctx))
    return "rule_logic"


# ------------------------------------------------------------- self-check ---
_CELL = re.compile(r"\br(\d+)c(\d+)\b")


def check(ex, step, puzzle, state):
    """Factual consistency of an explanation with the move and the grid. -> (ok, problems)."""
    p = derived(puzzle)
    st = _as_state(p, state)
    nm = Namer(p)
    probs = []
    cell_of = {nm.cell(c): c for c in range(p.N)}
    m = step.move
    text = ex["short"] + " " + ex["teach"]
    # 1. placement stated exactly in the short line
    if m.place:
        c, v = m.place
        if f"{nm.cell(c)} = {v}" not in ex["short"]:
            probs.append("placement missing from short line")
    for mm in re.finditer(r"\b(r\d+c\d+) = (\d+)", text):
        if not m.place or (cell_of.get(mm.group(1)), int(mm.group(2))) != tuple(m.place):
            if (
                not text[max(0, mm.start() - 40) : mm.start()].count("would")
                and "assum" not in text[max(0, mm.start() - 30) : mm.start()].lower()
            ):
                probs.append(f"stray placement claim {mm.group(0)}")
    # 2. eliminations: '≠' claims in the short line == the move's eliminations
    claimed = set()
    for seg in ex["short"].split(":")[0].split(";"):
        if "≠" in seg:
            cs, ds = seg.split("≠")
            for cn in _CELL.findall(cs):
                for d in ds.strip().split(","):
                    claimed.add((cell_of.get(f"r{cn[0]}c{cn[1]}"), int(d)))
    if set(m.elim) != claimed and m.elim:
        probs.append(f"elimination claims differ ({len(claimed)} vs {len(set(m.elim))})")
    # 3. 'the D in rXcY' -> placed digit claims
    for mm in re.finditer(r"\bthe (\d+) in (r\d+c\d+)", text):
        c = cell_of.get(mm.group(2))
        if c is None or st.vals[c] != int(mm.group(1)):
            probs.append(f"false placed-digit claim '{mm.group(0)}'")
    # 4. 'rXcY {a,b}' -> candidate claims (notes)
    for mm in re.finditer(r"\b(r\d+c\d+) \{([\d,]+)\}", text):
        c = cell_of.get(mm.group(1))
        ds = sum(bit(int(d)) for d in mm.group(2).split(","))
        if c is None or st.cand[c] != ds:
            probs.append(f"false candidate claim '{mm.group(0)}'")
    # 5. every cell mentioned is highlighted (target / pattern / unit cells)
    vis = set(ex["visual"]["cell_ids"])
    for u in ex["visual"]["units"]:
        vis |= set(u["cells"])
    for ln in ex["visual"]["lines"]:
        vis |= set(ln["cell_ids"])
    for gi, g in enumerate(p.groups):
        if g.kind in ("cage", "implied", "extra") and nm.unit(gi) in text:
            vis |= set(g.cells)
    for cn in set(_CELL.findall(text)):
        c = cell_of.get(f"r{cn[0]}c{cn[1]}")
        if c is None:
            probs.append(f"unknown cell r{cn[0]}c{cn[1]}")
        elif c not in vis:
            probs.append(f"cell {nm.cell(c)} mentioned but not in the visual")
    # 6. house names mentioned exist and are in the visual / contain a mentioned cell
    vis_units = {u["name"] for u in ex["visual"]["units"]}
    mentioned_cells = {cell_of.get(f"r{a}c{b}") for a, b in _CELL.findall(text)}
    for mm in re.finditer(r"\b(row|column|box) (\d+)\b", text):
        nmu = f"{mm.group(1)} {mm.group(2)}"
        gi = next((gi for gi in range(len(p.groups)) if nm.unit(gi) == nmu), None)
        if gi is None:
            probs.append(f"unknown unit {nmu}")
        elif nmu not in vis_units and not set(p.groups[gi].cells) & mentioned_cells:
            probs.append(f"unit {nmu} unrelated to the move")
    # 7. technique naming: plain name, confirmed links only, no internal codes in the text
    tinfo = ex.get("technique") or {}
    if not isinstance(tinfo, dict) or not tinfo.get("name"):
        probs.append("technique name missing")
    else:
        bad = [u for u in tinfo.get("learn_more", ()) if u.split("#")[0] not in _confirmed()]
        if bad:
            probs.append(f"unconfirmed links {bad}")
        for code in S.TECH_NAMES.values():
            if re.search(r"[a-z][A-Z(]", code) and code in text:
                probs.append(f"internal technique code '{code}' in the text")
    # 8. all targets named
    tg = {c for c, _ in m.elim} | ({m.place[0]} if m.place else set())
    for c in tg:
        if nm.cell(c) not in text:
            probs.append(f"target {nm.cell(c)} not named")
    return (not probs), probs


_technique_key_base = _technique_key


def _technique_key(ctx, out):  # noqa: F811 -- extended for 68-82 and the new codes
    for _code, (_h, _key, _fam, _concept) in _X_HANDLERS.items():
        if ctx.tech == getattr(S, _code, -99):
            return _key
    if ctx.tech == S.EMPTY_RECT or (ctx.tech == S.X_CHAIN and ctx.code == "ER"):
        return "empty_rectangle"
    if ctx.tech == S.REMOTE_PAIRS:
        return "remote_pair"
    if ctx.tech == S.X_CHAIN and ctx.code == "TUR":
        return "turbot_fish"
    if ctx.tech == S.LOL_COMBO and ctx.code in ("PHI", "Phistomefel variant"):
        return "phistomefel_ring" if ctx.code == "PHI" else "phistomefel_variant"
    return _technique_key_base(ctx, out)
