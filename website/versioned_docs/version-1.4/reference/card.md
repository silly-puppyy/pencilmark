---
title: "The card"
description: "How a card is computed: the band route, the technique list, difficulty, time and the publishing checks."
toc_max_heading_level: 2
---

# The card

How a card is computed: the band route, the technique list, difficulty, time and the publishing checks. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.export {#pencilmark.export}

[src/pencilmark/export.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py)

Human-oriented exchange formats: one for the puzzle, one for its grade.

puzzle (format "pencilmark-puzzle", format_version 1): specified in [Puzzle format](../formats/puzzle-format.md), implemented in pencilmark/exchange/ (strict reader, order-preserving writer, canonical text, fingerprint), schema docs/pencilmark-puzzle.schema.json. In short: "board", "digits", flat "givens" (0 empty, null no cell), optional "solution" / "candidates", and "rules" holding every constraint, houses included ({"type": "box_grid", "box": [3, 3], "count": [3, 3]} for a classic, {"type": "grid", ...} plus "box" rules for a jigsaw), cells named "r{row}c{col}"; "meta" is free-form information that never changes solving. Unknown keys / rule types are refused.

```
grade (format "pencilmark-grade", format_version 1):
  grader      {"name": "pencilmark", "version": "1.2.0"}: the engine that made the card; a card from another version can differ
  difficulty  what a human feels per cell: continuous, above 0 (a nearly finished grid ~0.2), no ceiling; classic medians track Andrew Stuart's
              scale (data/card_score.json "map")
  time        minutes for today's median player (classic units x minutes_per_unit, data/time_model.json); on request
              time_pNN = the NN-th percentile over today's players and time_mean = the mean (log-normal, sigma spread_sigma)
  band        "Very Easy" … "Extreme" or "Unknown" (not solvable without computer search); on request band_index 0..6
  contains    what a solver meets going easy -> hard (band path): [{"code", "chip", "name", "band", "uses", "alternatives"}];
              a chip "XWG/KTE/CSM" = each of these alone also gets you through here; singles listed without counts
  notes       publishing notes: [{"code": "thin", "severity": "reject" | "note", "text": "…"}]
  steps       [{"n", "code", "name", "placement" ("r2c8=3"), "eliminations" (["r4c5#7"]), "explanation", "detail"}]
```

| Name | What it does |
|---|---|
| def [`code_names`](#pencilmark.export.code_names) | chip code -> technique name (data/codes.csv) |
| def [`chip_of`](#pencilmark.export.chip_of) | (chip code, band index) for a technique, using its most specific pattern name where the band depends on it:… |
| def [`tech_band`](#pencilmark.export.tech_band) | band index of an engine technique (data/techniques.csv; SPLIT techniques at their lowest shape's band). |
| def [`read_meta`](#pencilmark.export.read_meta) | metadata from a dict: its "meta" object plus known top-level keys (meta keys at the top level), empty values… |
| def [`export_puzzle`](#pencilmark.export.export_puzzle) | engine Puzzle -> "pencilmark-puzzle" dict (format_version 1, [Puzzle format](../formats/puzzle-format.md);… |
| def [`import_puzzle`](#pencilmark.export.import_puzzle) | pencilmark-puzzle (format_version 1, [Puzzle format](../formats/puzzle-format.md)) -> puzzle JSON (pencilmark.puzzle_json),… |
| def [`region_geometry`](#pencilmark.export.region_geometry) | type-free region geometry the time model reads : blob_cells = share of cells in 2-D complete groups that are… |
| def [`time_units`](#pencilmark.export.time_units) | expected solving time in standard-classic units (1.0 = a median classic) from the grader model's time model… |
| def [`card_fields`](#pencilmark.export.card_fields) | the field mask ([Grade card](../formats/grade-card.md) 2): the requested top-level card keys; None = the default fields. |
| def [`explain_levels`](#pencilmark.export.explain_levels) | explain= option -> the step explanation levels: None / False = none, True = the three text levels,… |
| def [`symmetry_of`](#pencilmark.export.symmetry_of) | symmetries of the givens pattern (and board shape): [{"kind", "axis"?, "of": "givens"}]. |
| def [`grade`](#pencilmark.export.grade) | grade() under max_seconds, stage by stage: the technique list (contains) truncates at the limit as before;… |
| def [`grade_fog`](#pencilmark.export.grade_fog) | the card of a fog puzzle (p loaded and proven unique; source: the input, for its rules text). |
| def [`unknown_card`](#pencilmark.export.unknown_card) | the card of a puzzle whose uniqueness could not be settled: band Unknown, difficulty and time null, no… |

### `def code_names()` {#pencilmark.export.code_names}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L87)

chip code -> technique name (data/codes.csv)

### `def chip_of(tech_id, specific=None)` {#pencilmark.export.chip_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L102)

(chip code, band index) for a technique, using its most specific pattern name where the band depends on it: short X-Chains (Skyscraper / 2-String Kite / Turbot) Hard, longer ones Very Hard; Franken X-Wing Very Hard.

### `def tech_band(t)` {#pencilmark.export.tech_band}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L123)

band index of an engine technique (data/techniques.csv; SPLIT techniques at their lowest shape's band).

### `def read_meta(d)` {#pencilmark.export.read_meta}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L146)

metadata from a dict: its "meta" object plus known top-level keys (meta keys at the top level), empty values dropped.

### `def export_puzzle(p, meta=None, solution=None, source=None, title=None, rules_text=None)` {#pencilmark.export.export_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L154)

engine Puzzle -> "pencilmark-puzzle" dict (format_version 1, [Puzzle format](../formats/puzzle-format.md); pencilmark/exchange/). meta: free-form metadata dict; source / title / rules_text keywords are merged into meta.

### `def import_puzzle(d)` {#pencilmark.export.import_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L163)

pencilmark-puzzle (format_version 1, [Puzzle format](../formats/puzzle-format.md)) -> puzzle JSON (pencilmark.puzzle_json), read strictly by pencilmark/exchange/.

### `def region_geometry(p)` {#pencilmark.export.region_geometry}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L171)

type-free region geometry the time model reads : blob_cells = share of cells in 2-D complete groups that are not rectangles (jigsaw regions; diagonals are lines, excluded); extra_area_pc = 2-D complete groups per cell beyond one (windoku / center-dot / extra regions). 0 / 0 on a standard grid.

### `def time_units(effort_l1, empty_cells, geometry=None)` {#pencilmark.export.time_units}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L197)

expected solving time in standard-classic units (1.0 = a median classic) from the grader model's time model (data/time_model.json): exp(const + k_effort \* L1 + k_empty \* ln(empty cells) + geometry) + t0, L1 = log of the priced step sum (card "effort_l1"); fitted on era-adjusted per-player times. None without the inputs.

### `def card_fields(fields=None, steps=False)` {#pencilmark.export.card_fields}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L276)

the field mask ([Grade card](../formats/grade-card.md) 2): the requested top-level card keys; None = the default fields. format, format_version and grader are always present. steps=True adds the steps (internal callers).

### `def explain_levels(explain)` {#pencilmark.export.explain_levels}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L290)

explain= option -> the step explanation levels: None / False = none, True = the three text levels, "notation" / "short" / "teach" / "substeps" or a list

### `def symmetry_of(p)` {#pencilmark.export.symmetry_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L408)

symmetries of the givens pattern (and board shape): [{"kind", "axis"?, "of": "givens"}]. Rule symmetry ("of": "all") is not detected yet.

### `def grade(p, P, card=None, with_steps=None, max_seconds=None, fields=None, explain=None, alternatives=True)` {#pencilmark.export.grade}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L656)

grade() under max_seconds, stage by stage: the technique list (contains) truncates at the limit as before; the difficulty route stops at its own limit (engine deadline) and the card is then band "Unknown" with difficulty / time null, the techniques found so far in contains and "stopped": "time limit" ([Grade card](../formats/grade-card.md) 1).

### `def grade_fog(p, source, P, fields=None)` {#pencilmark.export.grade_fog}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L794)

the card of a fog puzzle (p loaded and proven unique; source: the input, for its rules text). A route that stalls under the fog gives band Unknown with difficulty / time null and stopped_at_step; the "fog" field tells what the fog route did.

### `def unknown_card(want, reason)` {#pencilmark.export.unknown_card}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/export.py#L856)

the card of a puzzle whose uniqueness could not be settled: band Unknown, difficulty and time null, no techniques, and the reason

## pencilmark.band_path {#pencilmark.band_path}

[src/pencilmark/band_path.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py)

Band-by-band human solve and technique hints.

The solve uses Very Easy moves until none are left, then Easy, then Medium, and so on, dropping back to the lowest band after every move. Within a band it takes the simplest technique first (study order, data/codes.csv), then the cheapest move. Each step is named by its most specific shape (a Skyscraper, not "X-Chain"; a Franken X-Wing, not "X-Wing"), and its band comes from that shape.

The techniques this solve uses are the puzzle's hints: what a human solving from easy to hard will meet. SUBSET maps each code to the codes it is a special case of (always true: every X-Wing is a Skyscraper), so a learner who knows a technique also covers its special cases (covered(), lesson()).

```
    band_path(puzzle, P) -> {"solved", "band", "steps": [{code, name, band, place, elims}], "profile": {code: uses}}
```

| Name | What it does |
|---|---|
| def [`covered`](#pencilmark.band_path.covered) | a learner who knows `known` can do `code`: they know it, or a technique it is always a case of. |
| def [`classify`](#pencilmark.band_path.classify) | (code, name, band) of one state_moves move, by its most specific shape. |
| def [`variant_gate`](#pencilmark.band_path.variant_gate) | engine techniques to switch off for this puzzle: variant techniques without any variant rule, sum techniques… |
| def [`band_path`](#pencilmark.band_path.band_path) | solve band by band (see module doc). |
| def [`contents`](#pencilmark.band_path.contents) | What's in the puzzle, deterministically (same puzzle -> same card). |
| def [`fold`](#pencilmark.band_path.fold) | contents shown to players: a full house is always both a naked and a hidden single and ends nearly every… |
| def [`allowed`](#pencilmark.band_path.allowed) | content filter: no hint is a banned technique or a generalization of one (not ready for Skyscrapers means… |
| def [`lesson`](#pencilmark.band_path.lesson) | is this a lesson puzzle for `target` given `known` techniques: the target itself appears (a Skyscraper… |
| def [`step_notation`](#pencilmark.band_path.step_notation) | one band-path step in the notation solvers and forums share: "X-Wing: 3 r58 c68 => r679c6&lt;>3", "Hidden… |
| def [`explain_steps`](#pencilmark.band_path.explain_steps) | teaching text for band-path steps: rebuild each position, let the engine find that technique's moves there… |
| def [`start_position`](#pencilmark.band_path.start_position) | the route's first position: the givens placed, every other cell its domain minus its peers' givens -> (vals,… |
| def [`apply_step`](#pencilmark.band_path.apply_step) | one route step on (vals, cand) in place: its placement (clearing the digit from the cell's peers), then its… |
| def [`written_marks`](#pencilmark.band_path.written_marks) | the marks a casual classic solver would have on paper at each position (pos = positions(p, steps)),… |
| def [`written_colours`](#pencilmark.band_path.written_colours) | the identity colors an expert would have painted at each position (pos = positions(p, steps); params… |
| def [`positions`](#pencilmark.band_path.positions) | the positions of a route: before its first step, then after each step -> [(vals, cand)] of len(steps) + 1 |

### `def covered(code, known)` {#pencilmark.band_path.covered}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L64)

a learner who knows `known` can do `code`: they know it, or a technique it is always a case of.

### `def classify(m, p)` {#pencilmark.band_path.classify}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L79)

(code, name, band) of one state_moves move, by its most specific shape.

### `def variant_gate(p)` {#pencilmark.band_path.variant_gate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L112)

engine techniques to switch off for this puzzle: variant techniques without any variant rule, sum techniques without a sum rule, law of leftovers without sums or irregular / extra regions.

### `def band_path(p, P, max_steps=None, disabled=(), target=None, rng=None, ban_codes=(), guard=None, prefix=(), max_band=6, keep_held=False, stop_cells=None)` {#pencilmark.band_path.band_path}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L153)

solve band by band (see module doc). Moves are taken in full-notes mode: each placement clears its peers. target = a cell: stop once it is placed, preferring (within the current band) a move that places it -- "what does it take to place this cell from here". max_band: stop (unsolved) where only a harder move would continue -- contents() reruns can only count if they stay in the card's band, so they never list above it. keep_held: keep color-only steps no later step used (the fog route: a color may pay off after the next reveal). stop_cells: stop right after a placement in one of these cells (the fog route: a placement that lights new cells ends the round).

### `def contents(p, P, alternatives=True, deadline=None, base=None)` {#pencilmark.band_path.contents}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L714)

What's in the puzzle, deterministically (same puzzle -> same card). 1. band_path (easy to hard, simplest technique first). 2. Shrink: each listed technique is tried for removal (banned by its exact code), later in the study order first, so the simpler of two interchangeable ones stays; kept only if _route_ok (same band, nothing new but special cases of what's listed, its work not moved to a harder technique or a generalization of it). 3. Alternatives: for each listed technique X, every same-band technique Y that is NOT on X's subset chain (neither is a special case of the other) and was available where X was used, is tested by banning X: if the puzzle then solves with the listed techniques plus Y (_route_ok, Y actually used), X/Y is a joint chip -- "solvable if you know either". Same-chain relations stay out: the player's subset table covers them (a Turbot learner can do Skyscrapers). Full houses fold into the listed single. -> band_path result + "removed", "alternatives" {code: [codes]}. deadline (time.time() value, opt-in; default None = deterministic): shrink / alternatives stop when it passes and the result carries "truncated": True (the base route is always complete; the list may then not be minimal / miss joint chips). base: band_path(p, P) already computed by the caller (it is not computed again).

### `def fold(profile)` {#pencilmark.band_path.fold}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L847)

contents shown to players: a full house is always both a naked and a hidden single and ends nearly every house of every solve, so it carries no information -- its uses count under the listed single (hidden single first, as the simpler; only when no other single is listed does FHS appear itself).

### `def allowed(profile, banned)` {#pencilmark.band_path.allowed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L859)

content filter: no hint is a banned technique or a generalization of one (not ready for Skyscrapers means not ready for Turbot Fish / X-Chains either). Special cases of a banned code stay allowed (an X-Wing is fine when Skyscrapers are banned).

### `def lesson(profile, target, known=())` {#pencilmark.band_path.lesson}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L867)

is this a lesson puzzle for `target` given `known` techniques: the target itself appears (a Skyscraper puzzle is solvable by a Turbot learner but doesn't teach Turbot), and every other hint is covered by known + target.

### `def step_notation(p, st, just=None)` {#pencilmark.band_path.step_notation}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L916)

one band-path step in the notation solvers and forums share: "X-Wing: 3 r58 c68 => r679c6&lt;>3", "Hidden Single: r3c5=6". The pattern part comes from the explainer's justification when there is one.

### `def explain_steps(p, P, steps)` {#pencilmark.band_path.explain_steps}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L1082)

teaching text for band-path steps: rebuild each position, let the engine find that technique's moves there (one short solve with only that technique), take the move with exactly the same placement / eliminations and explain it (pencilmark/explain). -> [{"short", "teach"} or None] aligned with steps.

### `def start_position(p)` {#pencilmark.band_path.start_position}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L1200)

the route's first position: the givens placed, every other cell its domain minus its peers' givens -> (vals, cand), cand a digit bit mask per cell (0 for placed cells)

### `def apply_step(p, vals, cand, st)` {#pencilmark.band_path.apply_step}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L1213)

one route step on (vals, cand) in place: its placement (clearing the digit from the cell's peers), then its eliminations

### `def written_marks(p, steps, pos, P)` {#pencilmark.band_path.written_marks}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L1225)

the marks a casual classic solver would have on paper at each position (pos = positions(p, steps)), following the engine's note model (params notes_live, snyder_max, notes_small, notes_lazy; docs/research/notes_dynamics.md): corner = position notes (a digit with 2..snyder_max places left in a box by the placed digits, noted once, from the start); center = candidate lists, written when notes start (the first step that is neither direct nor worked in the head) in the cells with &lt;= notes_small candidates, then in every cell a step uses. Marks show only digits that are still candidates. -> [{cell index: (corner digits, center digits)}] per position; None when the model is off.

### `def written_colours(p, pos, P)` {#pencilmark.band_path.written_colours}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L1291)

the identity colors an expert would have painted at each position (pos = positions(p, steps); params notes_colours): pair coloring as hosts do it ("color the sevens and nines against each other", CtC solves): for a digit pair {a, b}, the cells whose candidates are exactly {a, b}; two of them in one house hold different digits, so they take opposite colors of a color pair (which color is a and which b is still open). Each color stands for one unknown digit and is tracked further: in a complete house without it, the single open cell that can hold one of its digits and sees none of its cells joins it; cells an equality rule joins (palindromes, clones) share it. A pair colored only in its two seed cells is left out (the center marks show a naked pair). A color pair keeps its names while its first cell stays in it; at most MAX_COLOR_PAIRS pairs, the largest. -> [[{"color", "cells", "digits", "opposite"}]] per position (cell indices); None when the model is off.

### `def positions(p, steps)` {#pencilmark.band_path.positions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/band_path.py#L1380)

the positions of a route: before its first step, then after each step -> [(vals, cand)] of len(steps) + 1

## pencilmark.card {#pencilmark.card}

[src/pencilmark/card.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/card.py)

The card route: difficulty and time effort on the written route, and the publishing notes, for export.grade.

card = grade_card(puzzle, P, band)      # band = (band name, required techniques) from the band path

Returns {"status", "score", "effort_l1", "notes"}: score is the card's difficulty (card_score.score_parts, with the grader model), effort_l1 the log step-value sum the time model reads, notes the publishing checks (publish_flags.notes). score and effort_l1 are None when the route cannot grade the puzzle.

| Name | What it does |
|---|---|
| def [`grade_card`](#pencilmark.card.grade_card) |  |

### `def grade_card(puzzle, P, band, check_rules=True)` {#pencilmark.card.grade_card}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/card.py#L24)

*No docstring.*

## pencilmark.card_score {#pencilmark.card_score}

[src/pencilmark/card_score.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/card_score.py)

Card difficulty score: step value = d^beta x F / avail x exp(delta_tech) on the written human route; difficulty = mapped log of the average step effort per empty cell (+ a technique-free search-effort term). Parameters: the grader model (grader_model.py): price (difficulty), route (time effort, search effort), score.

| Name | What it does |
|---|---|
| def [`steps`](#pencilmark.card_score.steps) | the written route under params P -> ([(technique name, price, F)], cells each step touches) |
| def [`refute_lr_cell`](#pencilmark.card_score.refute_lr_cell) | technique-free search effort of the puzzle: the engine's generic refutation profile (singles + pair… |
| def [`steps_enum`](#pencilmark.card_score.steps_enum) | steps(p, P) plus, per step, the enumeration size of the cages its cells touch (0 without cages). |
| def [`score_parts`](#pencilmark.card_score.score_parts) | (card score, L1 = log of the step-value sum) for one puzzle; None if the engine must guess. |

### `def steps(p, P, solve=None)` {#pencilmark.card_score.steps}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/card_score.py#L21)

the written route under params P -> ([(technique name, price, F)], cells each step touches)

### `def refute_lr_cell(p)` {#pencilmark.card_score.refute_lr_cell}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/card_score.py#L65)

technique-free search effort of the puzzle: the engine's generic refutation profile (singles + pair relations + n-ary consistency; when stuck, every candidate trialled, shortest refutations applied) -> log1p(sum over stuck points of log(candidates / shortest refutations) per empty cell). Puzzle-only: no technique catalog, no prices.

### `def steps_enum(p, P, solve=None)` {#pencilmark.card_score.steps_enum}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/card_score.py#L138)

steps(p, P) plus, per step, the enumeration size of the cages its cells touch (0 without cages).

### `def score_parts(p, model=None, solve=None, overrides=None)` {#pencilmark.card_score.score_parts}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/card_score.py#L280)

(card score, L1 = log of the step-value sum) for one puzzle; None if the engine must guess. The score is priced with the model's difficulty prices, L1 (the effort the time model reads) with its route prices; both on the written route each price set produces. With score time_effort "difficulty", L1 is the difficulty's own log effort per empty cell instead (_finish). overrides: engine params for every route (rate(coloring=True)).

## pencilmark.scoring {#pencilmark.scoring}

[src/pencilmark/scoring.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py)

Per-move difficulty, race-model time, and puzzle-level grade.

Difficulty of a move (SE-like scale, Full House in a square 9-cell house = 1):

```
  direct singles:  d = B[tech] * base_shape^gamma * size(D)
                       + sum_i K[kind_i] * shape_i^gamma * uncovered_i
      the set-cover formulation of the C# naked-single code: every extra group
      you have to combine costs K * shape * (items still unexplained), for
      naked singles items = digits, for hidden singles items = cells.
  notes techniques: d = B[tech] * shape^gamma * size(D)
  TakeNotes:        d = B[TAKE_NOTES]  (writing notes is itself a skill gate)
```

size(D) = ((D-1)/8)^alpha: how many alternatives a basic check discriminates between; can't be fitted from 9x9-only data, set from first principles.

Time (race model): every available move m is noticed at rate exp(-beta \* d_m) / (c \* scan), scan = empty cells. Expected time to the next move is c \* scan / sum_m exp(-beta \* d_m); plus writing digits, writing and erasing notes. Many simultaneous moves -> fast (sudoku.coach's tediousness); bigger board -> more scan, but also more simultaneous moves.

Grade: soft bottleneck over the chosen steps -- d_max + tau \* log( sum_i exp((d_i - d_max)/tau) \* ref_steps / n_steps ) clipped at d_max. Counting hard steps as a DENSITY means a samurai (five 9x9s each needing one X-Wing) grades like one of its 9x9s, while a single 9x9 needing five X-Wings grades higher than one needing one.

| Name | What it does |
|---|---|
| def [`copy_params`](#pencilmark.scoring.copy_params) | copy of the params dict with its dict and list values copied one level deep |
| def [`complete_params`](#pencilmark.scoring.complete_params) | Fill params fitted before a technique/kind existed with defaults. |
| def [`meta_vector`](#pencilmark.scoring.meta_vector) | Meta vector: META_NAMES (the 10 pricing columns) + the 6 structural descriptors DESC_NAMES (csolver… |
| def [`meta_priced`](#pencilmark.scoring.meta_priced) | True when the move is priced by the structural meta model today. |
| class [`Scorer`](#pencilmark.scoring.Scorer) | prices a move from its features under a params dict (structural pricing when meta_theta is set) |
| def [`work_time`](#pencilmark.scoring.work_time) | Tediousness as a time (sudoku.coach's idea): predict_time with every move priced as if it were easy (capped… |
| def [`grade`](#pencilmark.scoring.grade) | {"work_time": seconds of routine work (work_time)}: what the publishing checks' tedious note reads |

### `def copy_params(p)` {#pencilmark.scoring.copy_params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L69)

copy of the params dict with its dict and list values copied one level deep

### `def complete_params(P)` {#pencilmark.scoring.complete_params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L81)

Fill params fitted before a technique/kind existed with defaults.

### `def meta_vector(meta, desc=True)` {#pencilmark.scoring.meta_vector}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L126)

Meta vector: META_NAMES (the 10 pricing columns) + the 6 structural descriptors DESC_NAMES (csolver desc.cpp, meta[10:18]; zeros for moves / older binaries without them) = the 18 columns of C++ featurize m_meta. desc=False: the 10 pricing columns only (what Scorer.difficulty prices with).

### `def meta_priced(meta)` {#pencilmark.scoring.meta_priced}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L158)

True when the move is priced by the structural meta model today. meta[18] = 1: the meta tuple was exported for a technique priced by its own B (desc.cpp, every technique carries a meta in canonical mode).

### `class Scorer` {#pencilmark.scoring.Scorer}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L168)

prices a move from its features under a params dict (structural pricing when meta_theta is set)

#### `def size(self, D)` {#pencilmark.scoring.Scorer.size}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L175)

board-size factor ((D - 1) / 8) \*\* alpha, 1 for 9 digits

#### `def difficulty(self, feat, D)` {#pencilmark.scoring.Scorer.difficulty}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L179)

price of one move from feat = (tech, base_shape, cover, extra[, meta[, load]]) on a D-digit board

### `def work_time(steps, puzzle, params)` {#pencilmark.scoring.work_time}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L312)

Tediousness as a time (sudoku.coach's idea): predict_time with every move priced as if it were easy (capped at the Hidden Single base price), so only the VOLUME of work remains -- scan area (empty cells), how many moves are available, writing / erasing notes. predicted time - work time = think time, the extra cost of hard steps. Decorrelated from difficulty by construction.

### `def grade(steps, puzzle, params=None, solved=True)` {#pencilmark.scoring.grade}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/scoring.py#L351)

{"work_time": seconds of routine work (work_time)}: what the publishing checks' tedious note reads

## pencilmark.grader_model {#pencilmark.grader_model}

[src/pencilmark/grader_model.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py)

The grader model: every fitted parameter the card uses, loaded once (internal; the public API has no model argument).

```
route   engine parameters for the band route, the written route's time prices and the search-effort term
        (data/params.json, completed with scoring defaults)
price   the difficulty prices: route with card_score.json "price_weights" in place of its structural weights (the
        card-fit weights, fitted on human times; everything else is shared with route)
score   the card-score configuration: step-value exponents, enumeration and search-effort weights, difficulty map
        (data/card_score.json)
time    the time model (data/time_model.json)
```

default() is what ships; the golden corpus (tools/golden.py) is pinned to it. Callers that change parameters take a copy (scoring.copy_params) and never edit these dicts.

Research: parameters have names, and a changed model grades through use():

m = default().with_overrides({"score.map.A": "x1.2", "time.k_effort": 0.3})

```
with use(m):
    card = pencilmark.rate(puzzle)
```

Names: "&lt;set>.&lt;key>" for a top-level value of route / price / score / time, "&lt;set>.&lt;key>.&lt;subkey>" inside a mapping ("score.map.A"), "route.price.&lt;Technique>" / "price.price.&lt;Technique>" for a technique's base price (B, by engine name; used only for techniques the structural model does not price). A value is a number, or "x&lt;factor>" to scale the current one. names() lists every name with its value.

| Name | What it does |
|---|---|
| class [`GraderModel`](#pencilmark.grader_model.GraderModel) |  |
| def [`default`](#pencilmark.grader_model.default) | the shipped model, loaded on first use |
| def [`engine_params`](#pencilmark.grader_model.engine_params) | the engine parameters of the model in use (data/params.json for the shipped one), completed with defaults |
| def [`use`](#pencilmark.grader_model.use) | grade with `model` instead of the shipped one inside the block (research; not thread-safe) |

### `class GraderModel` {#pencilmark.grader_model.GraderModel}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L36)

*No docstring.*

#### `def names(self)` {#pencilmark.grader_model.GraderModel.names}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L43)

{name: value} for every scalar parameter (lists are named as a whole)

#### `def get(self, name)` {#pencilmark.grader_model.GraderModel.get}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L60)

*No docstring.*

#### `def with_overrides(self, overrides)` {#pencilmark.grader_model.GraderModel.with_overrides}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L63)

a copy with the named parameters changed (number, or "x&lt;factor>" to scale); unknown names are an error

#### `def load(cls)` {#pencilmark.grader_model.GraderModel.load}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L84)

the shipped model from pencilmark/data

### `def default()` {#pencilmark.grader_model.default}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L93)

the shipped model, loaded on first use

### `def engine_params()` {#pencilmark.grader_model.engine_params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L101)

the engine parameters of the model in use (data/params.json for the shipped one), completed with defaults

### `def use(model)` {#pencilmark.grader_model.use}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/grader_model.py#L109)

grade with `model` instead of the shipped one inside the block (research; not thread-safe)

## pencilmark.metrics {#pencilmark.metrics}

[src/pencilmark/metrics.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/metrics.py)

Grading helpers over the engine's steps: the uniqueness-checked solve (grade_puzzle_checked), the pricing families and the user-facing bands (Very Easy .. Extreme, data/techniques.csv).

| Name | What it does |
|---|---|
| def [`family_of`](#pencilmark.metrics.family_of) |  |
| def [`grade_puzzle_checked`](#pencilmark.metrics.grade_puzzle_checked) | Uniqueness-checked grading entry point (use this for any external input). |
| def [`band_of`](#pencilmark.metrics.band_of) | Band index (0 Very Easy .. |

### `def family_of(tech)` {#pencilmark.metrics.family_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/metrics.py#L16)

*No docstring.*

### `def grade_puzzle_checked(puzzle, P, explain=False, time_limit=60.0)` {#pencilmark.metrics.grade_puzzle_checked}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/metrics.py#L20)

Uniqueness-checked grading entry point (use this for any external input). 1. Independent CP-SAT check: 0 solutions -> {"status": "no solution"}; 2+ -> {"status": "multiple solutions", "solutions": [two examples]}. 2. Unique -> solve and grade with uniqueness techniques allowed (assume_unique=True). 3. Unknown (CP-SAT can't express a rule / timed out) -> grade with assume_unique=False, so no uniqueness reasoning (UR, BUG+1, ...) is applied to an unproven puzzle. Returns {"status", "unique", "grade", "steps"}.

### `def band_of(tech)` {#pencilmark.metrics.band_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/metrics.py#L75)

Band index (0 Very Easy .. 6 Extreme) of a technique code; unknown codes fall back to the family.

## pencilmark.publish_flags {#pencilmark.publish_flags}

[src/pencilmark/publish_flags.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/publish_flags.py)

Common-sense publishing notes ('would not be chosen for publishing'), sudokuwiki-style. Bands never change.

```
Hand-coded rules, each checked against published puzzles (docs/research/quality_metrics.md):
  thin         a Medium+ puzzle whose candidate (non-single) steps carry less than `thin` (0.25 = 25%) of its effort: the
               hard step changes little and the rest is singles (Andrew Stuart's "too few candidates removed using
               candidate strategies"); published Hard puzzles: 10th percentile 0.26 (fed / coach), 0.28 (Stuart); our
               generator's puzzles sit well below unbiased ones (warning)
  decorative   a variant rule class that is neither needed for uniqueness nor used by any solve step
  barely_used  a variant rule class used in fewer than `barely_used` (3) steps of the whole solve (a 'Sudoku X' should use its X)
  redundant    a variant rule class the puzzle is unique without, although the solve uses it (soft note)
  trivial      more than `trivial` (0.6 = 60%) of the cells are given (barely a puzzle)
  tedious      Very Easy / Easy but over `tedious` (60) minutes of work (long and routine)
  uniqueness   needs a uniqueness-based technique (UR, BUG, Gurth): relies on assuming a unique solution
  trial        needs trial / forcing chains: computer-strength logic, not a human-friendly finish
  unusual      a difficulty outside the middle 80% of published puzzles of the same band (classic 9x9 and variants
               apart, TYPICAL; Very Easy has no floor, Extreme no ceiling): a Very Easy puzzle that scans like an Easy
               one, a Medium that plays like a Very Hard (reject)
Opt-in checks (off unless the quality object sets their severity or limit; limits near the edge of published Medium+
puzzles, 1,221 from LMD, sudoku.coach, Puzzle Duel, fed and others, quality study 2026-11-06; share of 165 published
Medium+ dev puzzles flagged: monotone 27%, asymmetric 25%, desert 8%, others 1-4%):
  asymmetric   the givens pattern has no symmetry (62% of published Medium+ classics have one)
  no_interplay a variant with two or more rule families that share fewer than `no_interplay` (1) cells
  winding      lines turn at more than `winding` (0.9) of their inner cells on average (published p90 0.91)
  short_lines  lines average fewer than `short_lines` (3) cells (published p10 3.0)
  repetitive   one technique makes more than `repetitive` (0.75) of a Medium+ solve's candidate steps (at least 4)
  monotone     a Medium+ solve's candidate steps come from fewer than `monotone` (2) technique families
  desert       after the first candidate step, a run of singles longer than `desert` (0.8) of the solve
  late_break   a Medium+ solve's first candidate step comes after `late_break` (0.6) of the solve
Each note is (code, severity, text); severity 'reject' = would not be published, 'note' = informational.
Every check is adjustable with an object (quality_limits): {"limit": n} replaces its limit (checks with one), {"severity":
"reject" | "warning" | "off"} overrides its severity or turns it off.
```

| Name | What it does |
|---|---|
| def [`quality_limits`](#pencilmark.publish_flags.quality_limits) | quality object -> {check: {"limit": number or None, "severity": "reject" \| "warning" \| "off" \| None}} for… |
| def [`spec_quality`](#pencilmark.publish_flags.spec_quality) | a generator spec's quality block -> the quality object its candidates are graded with, or None (no checks). |
| def [`notes`](#pencilmark.publish_flags.notes) | the publishing notes [(code, severity, text, ...)] of a graded puzzle, as the quality object asks |

### `def quality_limits(q=None)` {#pencilmark.publish_flags.quality_limits}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/publish_flags.py#L115)

quality object -> {check: {"limit": number or None, "severity": "reject" | "warning" | "off" | None}} for every check. One meaning everywhere ([Grade card](../formats/grade-card.md) 4): None = the "default" preset (rate() asked for issues without a quality object); {} = no checks; a preset turns on its checks; without a preset only the checks named run. Each entry is an object with "limit" (checks with a limit: a number >= 0) and / or "severity"; severity None = the check's own. Raises ValueError for unknown checks, keys or values.

### `def spec_quality(q)` {#pencilmark.publish_flags.spec_quality}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/publish_flags.py#L154)

a generator spec's quality block -> the quality object its candidates are graded with, or None (no checks). Quality is opt in: no block or {} runs nothing; otherwise the object means what it means in rate() (quality_limits; [Generator spec](../formats/generator-spec.md) 4)

### `def notes(puzzle, P, steps, tier, required, work_min, check_rules=True, difficulty=None)` {#pencilmark.publish_flags.notes}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/publish_flags.py#L397)

the publishing notes [(code, severity, text, ...)] of a graded puzzle, as the quality object asks

## pencilmark.se {#pencilmark.se}

[src/pencilmark/se.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/se.py)

Sudoku Explainer-style ratings from our route. Opt-in on the card: pencilmark.rate(puzzle, fields=[..., "se"]).

ER = the hardest step on our easiest human route (SE's "rating"); EP = hardest before the first placement ("pearl"); ED = the first step's value ("diamond", hardest before the first elimination / placement). Values per technique from the table expert solvers quote (Juillerat's Sudoku Explainer / serate): hidden single 1.2 (box), naked single 2.3, pointing 2.6, naked pair 3.0, X-Wing 3.2, hidden pair 3.4, naked triple 3.6, swordfish 3.8, ... Measured on the 747 classics of the frozen benchmark against the DiufSudoku fork's own rating (2026-10-31): ER within 0.3 for 81%, median gap 0.1; the largest gaps are routes that use a naked single where SE finds a hidden one (1.2-1.3 against 2.3). Approximate by construction: our route is not SE's route. A technique SE has no value for takes the value of the technique it is a special case of (codes.csv subset_of); with none (variant logic), it falls back to 7.0. Classic sudoku only is meaningful.

| Name | What it does |
|---|---|
| def [`ratings`](#pencilmark.se.ratings) | steps: band_path steps (dicts with code / place / elims) -> {"er", "ep", "ed", "scale": "classic"}. |

### `def ratings(steps)` {#pencilmark.se.ratings}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/se.py#L38)

steps: band_path steps (dicts with code / place / elims) -> {"er", "ep", "ed", "scale": "classic"}.

## pencilmark.usage {#pencilmark.usage}

[src/pencilmark/usage.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/usage.py)

Variant usage and balance (card concepts).

rule_usage(puzzle, params): solve with explanations and record, per step, which rule ELEMENTS justified it -- a diagonal, a cage, a dot / pair relation, a line (by kind), an arrow, extra regions, shading -- so a card can say "X-diagonals used 4x". Classic houses (rows, columns, boxes) are not elements.

necessity(puzzle): for each element class, drop every rule of that class and ask CP-SAT whether the puzzle is still unique; a class whose removal keeps the solution unique is not needed for uniqueness (it may still be needed for the logical path).

Both are read-only views over cbackend.solve(explain=True) / pencilmark.cpsat_verify; nothing here changes grading.

| Name | What it does |
|---|---|
| def [`step_elements`](#pencilmark.usage.step_elements) | Set of element classes one explained step uses. |
| def [`rule_usage`](#pencilmark.usage.rule_usage) | -> {"steps": [set of elements per step], "counts": Counter(element -> steps using it), "first_use":… |
| def [`element_classes`](#pencilmark.usage.element_classes) | Element class -> how to remove it from a copy of the puzzle (constraint indices, group names, relations). |
| def [`necessity`](#pencilmark.usage.necessity) | -> {element class: True (needed: the puzzle is not unique without it) / False / None (unknown)}. |

### `def step_elements(p, step, gk=None, rel_lines=None)` {#pencilmark.usage.step_elements}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/usage.py#L73)

Set of element classes one explained step uses. rel_lines (_relation_lines): relations a line generated are credited to that line.

### `def rule_usage(puzzle, params, solution=None)` {#pencilmark.usage.rule_usage}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/usage.py#L127)

-> {"steps": [set of elements per step], "counts": Counter(element -> steps using it), "first_use": {element: step index}, "solved": bool}

### `def element_classes(p)` {#pencilmark.usage.element_classes}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/usage.py#L187)

Element class -> how to remove it from a copy of the puzzle (constraint indices, group names, relations).

### `def necessity(puzzle, time_limit=30.0)` {#pencilmark.usage.necessity}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/usage.py#L257)

-> {element class: True (needed: the puzzle is not unique without it) / False / None (unknown)}. The puzzle is rebuilt from its uncompiled definition: relations generated from lines are dropped and regenerated by finalize, so removing a line class removes its relations too.
