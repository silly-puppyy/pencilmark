"""The technique catalogue: names, aliases and explainer links per technique; shapes; lessons. (split from explain.py)"""

from __future__ import annotations

from ..metrics import FAMILIES
from .base import FAMILY_DISPLAY

# ================================================================ technique names ==
SW, HD, SN = "https://www.sudokuwiki.org/", "https://hodoku.sourceforge.net/en/", "https://www.sudokusnake.com/"
_LINKS_FILE = "explain_links.json"  # in pencilmark/data

# key -> (primary name, {source: [aliases]}, family index (metrics.FAMILIES), [urls], [prerequisite keys])
# sources: sudokuwiki (Andrew Stuart), HoDoKu, Sudoku Explainer (SE), Sudoku Snake, other (common usage)
CATALOG = {
    "full_house": (
        "Full House",
        {"other": ["Last empty cell", "Last digit"], "HoDoKu": ["Full House"], "SE": ["Full House"]},
        0,
        [HD + "tech_singles.php#fh"],
        [],
    ),
    "cross_hatching": (
        "Hidden Single",
        {
            "other": ["Cross-hatching", "Hidden single in a box", "Slicing and dicing"],
            "sudokuwiki": ["Hidden Single"],
            "HoDoKu": ["Hidden Single"],
            "SE": ["Hidden Single"],
            "Sudoku Snake": ["Hidden Singles by Box"],
        },
        0,
        [SN + "hiddensinglesbybox.php", SW + "Getting_Started", HD + "tech_singles.php#h1"],
        [],
    ),
    "hidden_single": (
        "Hidden Single",
        {
            "other": ["Only place in the row/column", "Pinned digit"],
            "sudokubliss": ["Last Possible Number"],
            "sudokuwiki": ["Hidden Single"],
            "HoDoKu": ["Hidden Single"],
            "SE": ["Hidden Single"],
            "Sudoku Snake": ["Hidden Singles"],
        },
        0,
        [SN + "hiddensingles.php", SW + "Getting_Started", HD + "tech_singles.php#h1"],
        ["cross_hatching"],
    ),
    "naked_single": (
        "Naked Single",
        {
            "other": ["Sole candidate", "Last remaining digit"],
            "sudokuwiki": ["Naked Single"],
            "HoDoKu": ["Naked Single"],
            "SE": ["Naked Single"],
            "Sudoku Snake": ["Naked Singles"],
        },
        0,
        [SN + "nakedsingles.php", SW + "Getting_Started", HD + "tech_singles.php#n1"],
        ["full_house"],
    ),
    "single_after_pointing": (
        "Single with Locked Candidates",
        {"other": ["Single using a pointing digit", "Virtual digit"], "SE": ["Hidden Single (with Pointing)"]},
        1,
        [SN + "pointing.php", HD + "tech_intersections.php#lc1"],
        ["hidden_single", "pointing"],
    ),
    "pointing": (
        "Locked Candidates (Pointing)",
        {
            "sudokuwiki": ["Pointing Pairs", "Pointing Triples", "Intersection Removal"],
            "HoDoKu": ["Locked Candidates Type 1 (Pointing)"],
            "SE": ["Pointing"],
            "Sudoku Snake": ["Pointing"],
            "other": ["Pointing pair/triple"],
        },
        1,
        [SW + "Intersection_Removal", HD + "tech_intersections.php#lc1", SN + "pointing.php"],
        ["hidden_single"],
    ),
    "claiming": (
        "Locked Candidates (Claiming)",
        {
            "other": ["Claiming", "Box/line reduction"],
            "sudokuwiki": ["Box/Line Reduction", "Intersection Removal"],
            "HoDoKu": ["Locked Candidates Type 2 (Claiming)"],
            "SE": ["Claiming"],
            "Sudoku Snake": ["Claiming"],
        },
        1,
        [SW + "Intersection_Removal#LBR", HD + "tech_intersections.php#lc2", SN + "claiming.php"],
        ["hidden_single"],
    ),
    "naked_pair": (
        "Naked Pair",
        {
            "sudokuwiki": ["Naked Pair"],
            "HoDoKu": ["Naked Pair", "Locked Pair"],
            "SE": ["Naked Pair"],
            "Sudoku Snake": ["Naked Subsets"],
        },
        2,
        [SW + "Naked_Candidates#NP", HD + "tech_naked.php#n2", SN + "nakedsubsets.php"],
        ["naked_single"],
    ),
    "naked_triple": (
        "Naked Triple",
        {
            "sudokuwiki": ["Naked Triple"],
            "HoDoKu": ["Naked Triple", "Locked Triple"],
            "SE": ["Naked Triplet"],
            "Sudoku Snake": ["Naked Subsets"],
        },
        2,
        [SW + "Naked_Candidates#NT", HD + "tech_naked.php#n3", SN + "nakedsubsets.php"],
        ["naked_pair"],
    ),
    "naked_quad": (
        "Naked Quad",
        {
            "sudokuwiki": ["Naked Quad"],
            "HoDoKu": ["Naked Quadruple"],
            "SE": ["Naked Quad"],
            "Sudoku Snake": ["Naked Subsets"],
        },
        2,
        [SW + "Naked_Candidates#NQ", HD + "tech_naked.php#n4", SN + "nakedsubsets.php"],
        ["naked_triple"],
    ),
    "hidden_pair": (
        "Hidden Pair",
        {
            "sudokuwiki": ["Hidden Pair"],
            "HoDoKu": ["Hidden Pair"],
            "SE": ["Hidden Pair"],
            "Sudoku Snake": ["Hidden Subsets"],
        },
        2,
        [SW + "Hidden_Candidates#HP", HD + "tech_hidden.php#h2", SN + "hiddensubsets.php"],
        ["naked_pair"],
    ),
    "hidden_triple": (
        "Hidden Triple",
        {
            "sudokuwiki": ["Hidden Triple"],
            "HoDoKu": ["Hidden Triple"],
            "SE": ["Hidden Triplet"],
            "Sudoku Snake": ["Hidden Subsets"],
        },
        2,
        [SW + "Hidden_Candidates#HT", HD + "tech_hidden.php#h3", SN + "hiddensubsets.php"],
        ["hidden_pair"],
    ),
    "hidden_quad": (
        "Hidden Quad",
        {
            "sudokuwiki": ["Hidden Quad"],
            "HoDoKu": ["Hidden Quadruple"],
            "SE": ["Hidden Quad"],
            "Sudoku Snake": ["Hidden Subsets"],
        },
        2,
        [SW + "Hidden_Candidates#HQ", HD + "tech_hidden.php#h4", SN + "hiddensubsets.php"],
        ["hidden_triple"],
    ),
    "x_wing": (
        "X-Wing",
        {"sudokuwiki": ["X-Wing"], "HoDoKu": ["X-Wing"], "SE": ["X-Wing"], "Sudoku Snake": ["X-Wings"]},
        3,
        [SW + "X_Wing_Strategy", HD + "tech_fishb.php#bf2", SN + "xwings.php"],
        ["pointing", "claiming"],
    ),
    "swordfish": (
        "Swordfish",
        {"sudokuwiki": ["Swordfish"], "HoDoKu": ["Swordfish"], "SE": ["Swordfish"], "Sudoku Snake": ["Swordfish"]},
        3,
        [SW + "Sword_Fish_Strategy", HD + "tech_fishb.php#bf3", SN + "swordfish.php"],
        ["x_wing"],
    ),
    "jellyfish": (
        "Jellyfish",
        {"sudokuwiki": ["Jellyfish"], "HoDoKu": ["Jellyfish"], "SE": ["Jellyfish"], "Sudoku Snake": ["Jellyfish"]},
        3,
        [SW + "Jelly_Fish_Strategy", HD + "tech_fishb.php#bf4", SN + "jellyfish.php"],
        ["swordfish"],
    ),
    "finned_x_wing": (
        "Finned X-Wing",
        {
            "sudokuwiki": ["Finned X-Wing"],
            "HoDoKu": ["Finned X-Wing", "Sashimi X-Wing"],
            "SE": ["Finned X-Wing"],
            "Sudoku Snake": ["Finned X-Wings"],
        },
        3,
        [SW + "Finned_X_Wing", HD + "tech_fishfs.php#fbf2", SN + "finnedxwings.php"],
        ["x_wing"],
    ),
    "finned_swordfish": (
        "Finned Swordfish",
        {
            "sudokuwiki": ["Finned Swordfish"],
            "HoDoKu": ["Finned Swordfish", "Sashimi Swordfish"],
            "Sudoku Snake": ["Finned Swordfish"],
        },
        3,
        [SW + "Finned_Swordfish", HD + "tech_fishfs.php#fbf3", SN + "finnedswordfish.php"],
        ["swordfish", "finned_x_wing"],
    ),
    "finned_jellyfish": (
        "Finned Jellyfish",
        {"HoDoKu": ["Finned Jellyfish", "Sashimi Jellyfish"], "Sudoku Snake": ["Finned Jellyfish"]},
        3,
        [HD + "tech_fishfs.php#fbf4", SN + "finnedjellyfish.php"],
        ["jellyfish", "finned_swordfish"],
    ),
    "franken_fish": (
        "Franken Fish",
        {
            "sudokuwiki": ["Franken Swordfish"],
            "HoDoKu": ["Franken Fish"],
            "Sudoku Snake": ["Mutant Swordfish", "Mutant Jellyfish"],
        },
        3,
        [SW + "Franken_Sword_Fish", HD + "tech_fishc.php#ff", SN + "mutantswordfish.php"],
        ["swordfish"],
    ),
    "xy_wing": (
        "XY-Wing",
        {
            "sudokuwiki": ["Y-Wing"],
            "HoDoKu": ["XY-Wing"],
            "SE": ["XY-Wing"],
            "Sudoku Snake": ["XY-Wings"],
            "other": ["Y-Wing", "Bent triple"],
        },
        3,
        [SW + "Y_Wing_Strategy", HD + "tech_wings.php#xy", SN + "xywings.php"],
        ["naked_pair"],
    ),
    "xyz_wing": (
        "XYZ-Wing",
        {"sudokuwiki": ["XYZ-Wing"], "HoDoKu": ["XYZ-Wing"], "SE": ["XYZ-Wing"], "Sudoku Snake": ["XYZ-Wings"]},
        3,
        [SW + "XYZ_Wing", HD + "tech_wings.php#xyz", SN + "xyzwings.php"],
        ["xy_wing"],
    ),
    "w_wing": (
        "W-Wing",
        {"sudokuwiki": ["W-Wing"], "HoDoKu": ["W-Wing"]},
        3,
        [SW + "W_Wing_Strategy", HD + "tech_wings.php#w"],
        ["xy_wing"],
    ),
    "simple_colouring": (
        "Simple Coloring",
        {
            "sudokuwiki": ["Simple Colouring", "Singles Chains"],
            "HoDoKu": ["Simple Colors"],
            "Sudoku Snake": ["Coloring"],
            "other": ["Single-digit coloring", "Color wrap", "Color trap"],
        },
        3,
        [SW + "Simple_Colouring", HD + "tech_col.php#sc", SN + "coloring.php"],
        ["x_wing"],
    ),
    "skyscraper": (
        "Skyscraper",
        {
            "HoDoKu": ["Skyscraper"],
            "sudokuwiki": ["Rectangle Elimination"],
            "SE": ["Turbot Fish"],
            "other": ["Single-digit pattern"],
        },
        3,
        [HD + "tech_sdp.php#sk", SW + "Rectangle_Elimination"],
        ["x_wing"],
    ),
    "two_string_kite": (
        "2-String Kite",
        {"HoDoKu": ["2-String Kite"], "sudokuwiki": ["Rectangle Elimination"], "SE": ["Turbot Fish"]},
        3,
        [HD + "tech_sdp.php#t2sk", SW + "Rectangle_Elimination"],
        ["skyscraper"],
    ),
    "turbot_fish": (
        "Turbot Fish",
        {"HoDoKu": ["Turbot Fish"], "SE": ["Turbot Fish"], "other": ["Single-digit chain of length 4"]},
        3,
        [HD + "tech_sdp.php#tf"],
        ["skyscraper", "two_string_kite"],
    ),
    "empty_rectangle": (
        "Empty Rectangle",
        {"HoDoKu": ["Empty Rectangle"], "sudokuwiki": ["Empty Rectangles"]},
        3,
        [HD + "tech_sdp.php#er", SW + "Empty_Rectangles"],
        ["pointing", "skyscraper"],
    ),
    "unique_rectangle": (
        "Unique Rectangle",
        {
            "sudokuwiki": ["Unique Rectangles", "Hidden Unique Rectangles"],
            "HoDoKu": ["Uniqueness Test 1-6", "Hidden Rectangle"],
            "SE": ["Unique Rectangle"],
            "other": ["Deadly pattern"],
        },
        3,
        [SW + "Unique_Rectangles", HD + "tech_ur.php", SW + "Hidden_Unique_Rectangles"],
        ["naked_pair"],
    ),
    "bug_plus_1": (
        "BUG+1",
        {"sudokuwiki": ["BUG"], "HoDoKu": ["Bivalue Universal Grave + 1"], "SE": ["Bivalue Universal Grave"]},
        3,
        [SW + "BUG", HD + "tech_ur.php#bug1"],
        ["unique_rectangle"],
    ),
    "x_chain": (
        "X-Chain",
        {"sudokuwiki": ["X-Cycles"], "HoDoKu": ["X-Chain"], "SE": ["X-Chain"], "other": ["Single-digit chain"]},
        4,
        [SW + "X_Cycles", HD + "tech_chains.php#x"],
        ["simple_colouring", "skyscraper"],
    ),
    "xy_chain": (
        "XY-Chain",
        {"sudokuwiki": ["XY-Chain"], "HoDoKu": ["XY-Chain"], "SE": ["XY-Chain"], "Sudoku Snake": ["Naked XY-Chains"]},
        4,
        [SW + "XY_Chains", HD + "tech_chains.php#xyc", SN + "nakedxychains.php"],
        ["xy_wing"],
    ),
    "remote_pair": (
        "Remote Pair",
        {"sudokuwiki": ["Remote Pairs"], "HoDoKu": ["Remote Pair"], "Sudoku Snake": ["Remote Pairs"]},
        4,
        [SW + "Remote_Pairs", HD + "tech_chains.php#rp", SN + "remotepairs.php"],
        ["xy_chain"],
    ),
    "aic": (
        "Alternating Inference Chain",
        {"other": ["AIC"], "sudokuwiki": ["Alternating Inference Chains"], "HoDoKu": ["AIC"], "SE": ["Forcing Chain"]},
        4,
        [SW + "Alternating_Inference_Chains", HD + "tech_chains.php#in"],
        ["x_chain", "xy_chain"],
    ),
    "nice_loop": (
        "Nice Loop",
        {
            "HoDoKu": ["Discontinuous Nice Loop", "Continuous Nice Loop"],
            "sudokuwiki": ["X-Cycles", "Alternating Inference Chains"],
            "SE": ["Cell/Region Forcing Chains"],
        },
        4,
        [HD + "tech_chains.php#nl", SW + "X_Cycles"],
        ["aic"],
    ),
    "als_xz": (
        "ALS-XZ",
        {
            "sudokuwiki": ["Almost Locked Sets"],
            "HoDoKu": ["Almost Locked Set XZ-Rule"],
            "SE": ["Aligned Pair Exclusion (related)"],
        },
        5,
        [SW + "Almost_Locked_Sets", HD + "tech_als.php#axz"],
        ["naked_triple", "aic"],
    ),
    "als_xy_wing": (
        "ALS-XY-Wing",
        {"HoDoKu": ["Almost Locked Set XY-Wing"], "sudokuwiki": ["Almost Locked Sets"]},
        5,
        [HD + "tech_als.php#axy", SW + "Almost_Locked_Sets"],
        ["als_xz"],
    ),
    "death_blossom": (
        "Death Blossom",
        {"sudokuwiki": ["Death Blossom"], "HoDoKu": ["Death Blossom"], "Sudoku Snake": ["Death Blossom"]},
        5,
        [SW + "Death_Blossom", HD + "tech_als.php#db", SN + "deathblossom.php"],
        ["als_xz"],
    ),
    "als_chain": (
        "ALS-Chain",
        {"sudokuwiki": ["AIC with ALSs"], "HoDoKu": ["ALS-Chain"]},
        5,
        [SW + "AIC_with_ALSs", HD + "tech_als.php#ach"],
        ["als_xz", "aic"],
    ),
    "trial": (
        "Trial and Error",
        {
            "sudokuwiki": ["Nishio Forcing Chains", "Bowman's Bingo"],
            "HoDoKu": ["Trial and Error"],
            "SE": ["Nishio Forcing Chain"],
            "other": ["Contradiction", "Bifurcation"],
        },
        6,
        [SW + "Nishio_Forcing_Chains", HD + "tech_last.php#ts", SW + "Bowmans_Bingo"],
        ["aic"],
    ),
    "short_contradiction": (
        "Nishio Forcing Chain",
        {
            "sudokuwiki": ["Nishio Forcing Chains"],
            "SE": ["Nishio Forcing Chain"],
            "other": ["Short contradiction", "Bivalue test"],
        },
        6,
        [SW + "Nishio_Forcing_Chains"],
        ["naked_single", "hidden_single"],
    ),
    "either_way": (
        "Either Way (two-case check)",
        {
            "other": ["Forcing chain"],
            "sudokuwiki": ["Cell Forcing Chains", "Unit Forcing Chains"],
            "HoDoKu": ["Forcing Chain"],
            "SE": ["Cell Forcing Chains"],
            "Sudoku Snake": ["Forcing Chains", "Unit Forcing Chains"],
        },
        6,
        [SW + "Cell_Forcing_Chains", SW + "Unit_Forcing_Chains", HD + "tech_last.php#fc", SN + "forcingchains.php"],
        ["naked_single", "hidden_single"],
    ),
    "guess": (
        "Brute Force",
        {"HoDoKu": ["Brute Force"], "other": ["Guess", "Bifurcation", "Backtracking"]},
        6,
        [HD + "tech_last.php#bf", SW + "Brute_Force_vs_Logical_Strategies"],
        [],
    ),
    "pencil_marks": ("Pencil marks", {"other": ["Candidates", "Notes", "Snyder notation"]}, 0, [], []),
    "pair_in_head": (
        "Pair in your head",
        {"other": ["Mental naked pair", "Hidden pair without notes"]},
        2,
        [SW + "Naked_Candidates#NP"],
        ["naked_pair"],
    ),
    "triple_in_head": (
        "Triple in your head",
        {"other": ["Mental naked triple"]},
        2,
        [SW + "Naked_Candidates#NT"],
        ["naked_triple"],
    ),
    "pointing_in_head": (
        "Pointing in your head",
        {"other": ["Mental locked candidates"]},
        1,
        [SW + "Intersection_Removal"],
        ["pointing"],
    ),
    "chain_without_notes": (
        "Chain without notes",
        {"other": ["Mental chain", "Short forcing chain"]},
        4,
        [SW + "Alternating_Inference_Chains"],
        ["x_chain", "xy_chain"],
    ),
    "equal_cells": (
        "Two cells with the same digit",
        {"other": ["Abstract colouring", "Equivalent cells"]},
        3,
        [],
        ["hidden_single"],
    ),
    "digit_counting": (
        "Digit counting",
        {"other": ["Generalised fish", "Cage fish"], "HoDoKu": ["Generalized Fish"]},
        3,
        [HD + "tech_fishg.php", SW + "Cage_Unit_Overlap"],
        ["x_wing", "killer_combinations"],
    ),
    "law_of_leftovers": (
        "Law of Leftovers",
        {"sudokuwiki": ["Law of Leftovers"], "other": ["Set equivalence", "Phistomefel ring (special case)"]},
        1,
        [SW + "Law_of_Leftovers"],
        ["claiming"],
    ),
    "phistomefel_ring": (
        "Phistomefel ring",
        {"other": ["Phistomefel's theorem", "Set equivalence"]},
        3,
        [SW + "Law_of_Leftovers"],
        ["law_of_leftovers"],
    ),
    "phistomefel_variant": (
        "Phistomefel variant",
        {"other": ["Set equivalence"]},
        3,
        [SW + "Law_of_Leftovers"],
        ["phistomefel_ring"],
    ),
    "implied_house": (
        "Implied House",
        {"other": ["Hidden window", "Law of leftovers"], "sudokuwiki": ["Windoku Strategy"]},
        1,
        [SW + "Windoku_Strategy", SW + "Law_of_Leftovers"],
        ["full_house"],
    ),
    # variants
    "killer_combinations": (
        "Killer Combinations",
        {"sudokuwiki": ["Killer Combinations"], "other": ["Cage combinations", "Sum combinations"]},
        1,
        [
            SW + "Killer_Combinations",
            SW + "Killer_Cage_Combination_Example",
            "https://en.wikipedia.org/wiki/Killer_sudoku",
        ],
        ["naked_single"],
    ),
    "cage_must_contain": (
        "Cage Unit Overlap",
        {"sudokuwiki": ["Cage/Unit Overlap"], "other": ["Cage must-contain digit", "Killer pointing"]},
        1,
        [SW + "Cage_Unit_Overlap", SW + "Killer_Combinations"],
        ["killer_combinations", "pointing"],
    ),
    "rule_of_45": (
        "Innies and Outies",
        {"sudokuwiki": ["Innies and Outies"], "other": ["Rule of 45", "Secret of 45"]},
        1,
        [SW + "Innies_and_Outies", "https://en.wikipedia.org/wiki/Killer_sudoku"],
        ["killer_combinations"],
    ),
    "cage_arithmetic": (
        "Cage arithmetic",
        {"other": ["Last cell of a cage"]},
        0,
        [SW + "Killer_Combinations"],
        ["full_house"],
    ),
    "thermo": ("Thermo logic", {"other": ["Thermometer counting", "Thermo bulb logic"]}, 1, [], ["naked_single"]),
    "german_whispers": (
        "German whispers",
        {"other": ["Whisper high/low logic", "No 5s on a whisper"]},
        1,
        [],
        ["naked_single"],
    ),
    "dutch_whispers": ("Dutch whispers", {"other": ["Whisper high/low logic"]}, 1, [], ["german_whispers"]),
    "renban": ("Renban runs", {"other": ["Consecutive set line", "Purple line"]}, 1, [], ["naked_single"]),
    "arrow": ("Arrow sums", {"other": ["Arrow arithmetic"]}, 1, [], ["killer_combinations"]),
    "kropki": ("Kropki dots", {"other": ["Consecutive / ratio dots", "White and black dots"]}, 1, [], ["naked_single"]),
    "palindrome": ("Palindrome lines", {"other": ["Mirror line"]}, 1, [], ["naked_single"]),
    "between": ("Between lines", {"other": ["Between-circle logic"]}, 1, [], ["thermo"]),
    "entropic": ("Entropic lines", {"other": ["Low/middle/high triples"]}, 1, [], ["naked_single"]),
    "modular": ("Modular lines", {"other": ["Mod-3 classes"]}, 1, [], ["naked_single"]),
    "parity": ("Parity lines", {"other": ["Odd/even alternation"]}, 1, [], ["naked_single"]),
    "region_sum": ("Region-sum lines", {"other": ["Equal box segments"]}, 1, [], ["killer_combinations"]),
    "zipper": ("Zipper lines", {"other": ["Equal pair sums"]}, 1, [], ["killer_combinations"]),
    "nonconsecutive": (
        "Non-consecutive logic",
        {"other": ["Neighbours can't be consecutive"]},
        1,
        [],
        ["naked_single"],
    ),
    "anti_knight": ("Anti-knight logic", {"other": ["Chess-move constraint"]}, 1, [], ["cross_hatching"]),
    "xv": ("XV sums", {"other": ["X (10) and V (5) pairs"]}, 1, [], ["killer_combinations"]),
    "sandwich": ("Sandwich sums", {"other": ["Sum between 1 and 9"]}, 1, [], ["killer_combinations"]),
    "x_sum": ("X-sums", {"other": ["First-digit count sums"]}, 1, [], ["killer_combinations"]),
    "skyscraper_clue": ("Skyscraper clues", {"other": ["Visible buildings"]}, 1, [], ["naked_single"]),
    "little_killer": ("Little killer sums", {"other": ["Diagonal sums"]}, 1, [], ["killer_combinations"]),
    "line_window": ("Local line scan", {"other": ["Three cells at a time"]}, 1, [], ["naked_single"]),
    "rule_logic": (
        "Rule combinations",
        {"other": ["Checking a rule's possible fillings"]},
        1,
        [],
        ["killer_combinations"],
    ),
    "pair_rule": ("Neighbour-rule logic", {"other": ["Pair constraints"]}, 1, [], ["naked_single"]),
}

_LINE_KEY = {
    "thermo": "thermo",
    "slow_thermo": "thermo",
    "whisper": "german_whispers",
    "dutch_whisper": "dutch_whispers",
    "renban": "renban",
    "palindrome": "palindrome",
    "kropki_chain": "kropki",
    "between": "between",
    "entropic": "entropic",
    "modular": "modular",
    "parity": "parity",
    "region_sum": "region_sum",
    "zipper": "zipper",
    "arrow": "arrow",
    "cage": "killer_combinations",
    "sum": "killer_combinations",
    "little_killer": "little_killer",
    "sandwich": "sandwich",
    "xsum": "x_sum",
    "skyscraper": "skyscraper_clue",
    "set": "renban",
    "innie": "rule_of_45",
    "equal_sum": "zipper",
    "table": "rule_logic",
    "count": "rule_logic",
}
_REL_KEY = {
    "non-consecutive": "nonconsecutive",
    "anti-knight": "anti_knight",
    "anti-king": "anti_knight",
    "thermometer": "thermo",
    "slow thermometer": "thermo",
    "German whisper": "german_whispers",
    "Dutch whisper": "dutch_whispers",
    "white kropki dot": "kropki",
    "black kropki dot": "kropki",
    "palindrome": "palindrome",
    "entropic line": "entropic",
    "parity line": "parity",
    "modular line": "modular",
    "V (sum 5)": "xv",
    "X (sum 10)": "xv",
}

_CONFIRMED = None


def _confirmed():
    """Reference pages confirmed reachable (status 200) when the link table was built."""
    global _CONFIRMED
    if _CONFIRMED is None:
        try:
            from .. import _data

            data = _data.load_json(_LINKS_FILE)
            _CONFIRMED = {u for u, v in data.items() if v.get("status") == 200}
        except Exception:
            _CONFIRMED = set()
    return _CONFIRMED


def candidate_urls():
    return {u for v in CATALOG.values() for u in v[3]}


def technique_info(key):
    from ..metrics import FAMILY_TIERS

    name, aliases, fam, urls, pre = CATALOG.get(key) or (key, {}, 0, [], [])
    ok = _confirmed()
    flat = []
    for src in ("other", "sudokuwiki", "HoDoKu", "SE", "Sudoku Snake"):
        for a in aliases.get(src, ()):
            if a.lower().rstrip("s") != name.lower().rstrip("s") and a not in flat:
                flat.append(a)
    return {
        "key": key,
        "name": name,
        "aliases": flat,
        "aliases_by_source": aliases,
        "family": FAMILY_DISPLAY.get(FAMILIES[fam][0], FAMILIES[fam][0]),
        "tier": FAMILY_TIERS[min(fam, len(FAMILY_TIERS) - 1)],
        "learn_more": [u for u in urls if u.split("#")[0] in ok],
        "prerequisites": [CATALOG[k][0] for k in pre if k in CATALOG],
    }


# ----------------------------------------------------------- named sub-patterns --
def chain_shape(p, st, path, place=False):
    """Name the shape of a chain: Skyscraper, 2-String Kite, Turbot fish, Remote pair, W-Wing,
    X-Chain / XY-Chain / AIC. -> catalog key."""
    if any(n[0][0] == "als" for n in path):
        return "als_chain"
    if place:
        return "nice_loop"
    links = [(path[i - 1][0], path[i][0], path[i][1], path[i][2]) for i in range(1, len(path))]
    if any(lk[2] == "equal" for lk in links):
        return "x_chain" if len({n[0][1] for n in path}) == 1 else "aic"
    strong = links[0::2]
    digits = {n[0][1] for n in path}
    srcs = {s for _, _, s, _ in strong}
    if len(digits) == 1 and srcs <= {"bilocal"}:
        if len(strong) == 2:
            kinds = []
            for a, b, _, u in strong:
                ks = [p.groups[g].kind for g in p.houses if a[0] in p.groups[g].cells and b[0] in p.groups[g].cells]
                kinds.append(
                    "box"
                    if "box" in ks and not {"row", "col"} & set(ks)
                    else "row"
                    if "row" in ks
                    else "col"
                    if "col" in ks
                    else "other"
                )
            if kinds[0] == kinds[1] and kinds[0] in ("row", "col"):
                return "skyscraper"
            if {kinds[0], kinds[1]} == {"row", "col"}:
                wa, wb = links[1][0][0], links[1][1][0]
                same_box = any(
                    p.groups[g].kind == "box" and wa in p.groups[g].cells and wb in p.groups[g].cells for g in p.houses
                )
                return "two_string_kite" if same_box else "turbot_fish"
            return "turbot_fish"
        return "x_chain"
    if srcs <= {"bivalue"}:
        cells = [n[0][0] for n in path]
        pairs = {st.cand[c] for c in cells}
        if len(pairs) == 1 and len(strong) >= 3:
            return "remote_pair"
        return "xy_chain"
    if len(strong) == 3 and [s for _, _, s, _ in strong] == ["bivalue", "bilocal", "bivalue"]:
        a, z = path[0][0][0], path[-1][0][0]
        if st.cand[a] == st.cand[z] and path[0][0][1] == path[-1][0][1]:
            return "w_wing"
    return "aic"


def fish_shape(p, base, cover, fins, U):
    k = len(base)
    size = {2: "x_wing", 3: "swordfish", 4: "jellyfish"}.get(k, "jellyfish")
    lines = lambda hs: {p.groups[h].kind for h in hs}
    franken = not (
        lines(base) <= {"row"} and lines(cover) <= {"col"} or lines(base) <= {"col"} and lines(cover) <= {"row"}
    )
    if franken:  # mutant: rows and columns mixed inside the base or the cover set
        if {"row", "col"} <= lines(base) or {"row", "col"} <= lines(cover):
            return "franken_fish", "Mutant"
        return "franken_fish", "Franken"
    if not fins:
        return size, ""
    sashimi = any(len([c for c in U if c in p.groups[h].cells and c not in fins]) <= 1 for h in base)
    return {"x_wing": "finned_x_wing", "swordfish": "finned_swordfish", "jellyfish": "finned_jellyfish"}[size], (
        "Sashimi" if sashimi else "Finned"
    )


_VARIANT_LESSONS = {
    "german_whispers": "On a German whisper neighbours differ by at least 5: 5 can never appear, and digits "
    "alternate between low (1-4) and high (6-9) along the line.",
    "dutch_whispers": "Dutch whisper neighbours differ by at least 4; 5 can only sit next to 1 or 9.",
    "thermo": "Digits rise from the bulb: a cell n steps along is at least n+1, and one with m cells after it is "
    "at most 9-m. Bulbs are low, tips are high.",
    "renban": "A renban line holds a run of consecutive digits in any order: no repeats, and the length decides "
    "which runs fit.",
    "killer_combinations": "Learn the unique cage sums (3 = 1+2, 4 = 1+3, 16 = 7+9, 17 = 8+9 ...) and list a "
    "cage's possible digit sets before placing anything.",
    "rule_of_45": "Every row, column and box adds to 45: compare it with the cages inside it to find the cells "
    "poking in or out.",
    "cage_must_contain": "If every combination of a cage uses a digit and its spots in the cage share a house, the "
    "digit leaves the rest of that house.",
    "arrow": "The digits on an arrow sum to its circle: bound the circle by the smallest and largest possible "
    "arrow totals.",
    "kropki": "White dots join consecutive digits, black dots a digit and its double; a cell between two dots is "
    "very restricted.",
    "palindrome": "A palindrome line reads the same from both ends: mirrored cells hold the same digit.",
    "between": "Digits on a between line lie strictly between the two circle digits.",
    "nonconsecutive": "Orthogonal neighbours can't be consecutive, so every placed digit removes two candidates "
    "from each neighbour.",
}

SHAPE_NOTES = {
    "skyscraper": "This shape is a Skyscraper: two parallel strong links on the same digit whose ends share a "
    "line, so one of the two 'roof' cells must be the digit.",
    "two_string_kite": "This shape is a 2-String Kite: a strong link in a row and one in a column, tied together "
    "inside a box -- one of the two free ends must be the digit.",
    "turbot_fish": "This shape is a Turbot fish: a four-cell single-digit chain (strong-weak-strong).",
    "remote_pair": "This shape is a Remote pair: a chain of cells all holding the same two candidates, which "
    "alternate along the chain.",
    "w_wing": "This shape is a W-Wing: two identical two-candidate cells joined by a strong link on one of their "
    "digits, so one of them must be the other digit.",
    "xy_chain": "This is an XY-Chain: every link runs through a two-candidate cell.",
    "x_chain": "This is an X-Chain: a single digit followed through houses where it has only two places.",
    "nice_loop": "This is a discontinuous Nice Loop: the chain returns to its start with two strong links.",
}
