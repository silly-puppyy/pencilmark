---
title: "The engine interface"
description: "The Python side of the C++ engine: the puzzle model, the calls into the engine, its move records, the technique registry."
toc_max_heading_level: 2
---

# The engine interface

The Python side of the C++ engine: the puzzle model, the calls into the engine, its move records, the technique registry. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.model {#pencilmark.model}

[src/pencilmark/model.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py)

Group-agnostic puzzle model.

A puzzle is cells (with 2D coordinates, used only for group-shape scoring), digits 1..D, and constraints. Nothing downstream assumes rows/columns/boxes:

```
  houses    -- groups of exactly D cells that must contain every digit once
               (rows, cols, boxes, jigsaw regions, full diagonals, windoku
               windows, every sub-grid unit of a samurai...)
  cages     -- all-different groups smaller than D, optionally with a sum
               (killer cages)
  relations -- pairwise constraints between specific cells: 'neq' (anti-knight,
               anti-king, ...), 'nonconsec' (|a-b| != 1)
  domains   -- per-cell allowed-digit masks (odd/even shading, etc.)
```

| Name | What it does |
|---|---|
| def [`bit`](#pencilmark.model.bit) | digit d (1-based) -> its one-bit candidate mask |
| def [`popcount`](#pencilmark.model.popcount) | number of candidates in the mask m |
| def [`digits_of`](#pencilmark.model.digits_of) | the digits of a candidate mask, smallest first |
| def [`shape_ratio`](#pencilmark.model.shape_ratio) | Radius of gyration of a cell set relative to the most compact (square) arrangement of the same number of… |
| class [`Group`](#pencilmark.model.Group) | cells whose digits never repeat (house, region, diagonal, window, cage) with its kind, cage total and shape |
| class [`Puzzle`](#pencilmark.model.Puzzle) | engine puzzle: D digits, cell coordinates, groups, pair relations, n-ary constraints, domains and givens;… |
| def [`standard`](#pencilmark.model.standard) | Classic size x size sudoku with box_h x box_w boxes. |
| def [`parse_grid`](#pencilmark.model.parse_grid) | grid text (one character per cell or space-separated tokens; . |
| def [`add_diagonals`](#pencilmark.model.add_diagonals) | add the two main diagonals of a size x size grid as groups -> p |
| def [`add_windoku`](#pencilmark.model.add_windoku) | add the four windoku windows of a 9x9 grid as groups -> p |
| def [`jigsaw`](#pencilmark.model.jigsaw) | regions: size\*size chars, each a region id; replaces boxes. |
| def [`add_nonconsecutive`](#pencilmark.model.add_nonconsecutive) | add a nonconsec relation between every orthogonally adjacent pair of a size x size grid -> p |
| def [`add_antiknight`](#pencilmark.model.add_antiknight) | add a neq relation between every pair of cells a knight's move apart in a size x size grid -> p |
| def [`add_cages`](#pencilmark.model.add_cages) | cages: list of (sum_or_None, [cell indices]) |
| def [`subgrid_ids`](#pencilmark.model.subgrid_ids) | Row-major cell ids of samurai sub-grid k (0=TL,1=TR,2=center,3=BL,4=BR). |
| def [`apply_variant_to_subgrid`](#pencilmark.model.apply_variant_to_subgrid) | Add a variant's extra constraints to one 9x9 sub-grid of a samurai -- the group-agnostic model doesn't care… |
| def [`samurai`](#pencilmark.model.samurai) | Five overlapping 9x9 grids on a 21x21 canvas (corner grids share a box with the center grid). |
| def [`add_predicate`](#pencilmark.model.add_predicate) | Generic custom rule over a small group of cells: fn(\*digits) -> bool, compiled to an n-ary table constraint… |

### `def bit(d: int) -> int` {#pencilmark.model.bit}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L22)

digit d (1-based) -> its one-bit candidate mask

### `def popcount(m: int) -> int` {#pencilmark.model.popcount}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L27)

number of candidates in the mask m

### `def digits_of(m: int)` {#pencilmark.model.digits_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L32)

the digits of a candidate mask, smallest first

### `def shape_ratio(coords) -> float` {#pencilmark.model.shape_ratio}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L40)

Radius of gyration of a cell set relative to the most compact (square) arrangement of the same number of cells. 1.0 = square, larger = more spread out (a 9-cell row is ~2.24). Same formula as the C# pencilmark.

### `class Group` {#pencilmark.model.Group}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L56)

cells whose digits never repeat (house, region, diagonal, window, cage) with its kind, cage total and shape

### `class Puzzle` {#pencilmark.model.Puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L130)

engine puzzle: D digits, cell coordinates, groups, pair relations, n-ary constraints, domains and givens; call finalize() before solving

#### `def finalize(self)` {#pencilmark.model.Puzzle.finalize}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L283)

compile lines and clones, then build the derived tables (houses, peers, pair-relation exclusions) -> self

#### `def n_empty(self)` {#pencilmark.model.Puzzle.n_empty}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L340)

number of cells without a given

### `def standard(size: int, box_h: int, box_w: int, grid: str='', name='') -> Puzzle` {#pencilmark.model.standard}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L352)

Classic size x size sudoku with box_h x box_w boxes. grid uses '.'/'0' for blanks and 1-9 then A-Z for digits >9 (or space-separated numbers).

### `def parse_grid(grid: str, size: int) -> dict` {#pencilmark.model.parse_grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L369)

grid text (one character per cell or space-separated tokens; . 0 - empty, A = 10) -> {cell index: digit}

### `def add_diagonals(p: Puzzle, size: int) -> Puzzle` {#pencilmark.model.add_diagonals}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L382)

add the two main diagonals of a size x size grid as groups -> p

### `def add_windoku(p: Puzzle) -> Puzzle` {#pencilmark.model.add_windoku}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L389)

add the four windoku windows of a 9x9 grid as groups -> p

### `def jigsaw(size: int, regions: str, grid: str='', name='') -> Puzzle` {#pencilmark.model.jigsaw}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L398)

regions: size\*size chars, each a region id; replaces boxes.

### `def add_nonconsecutive(p: Puzzle, size: int) -> Puzzle` {#pencilmark.model.add_nonconsecutive}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L415)

add a nonconsec relation between every orthogonally adjacent pair of a size x size grid -> p

### `def add_antiknight(p: Puzzle, size: int) -> Puzzle` {#pencilmark.model.add_antiknight}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L427)

add a neq relation between every pair of cells a knight's move apart in a size x size grid -> p

### `def add_cages(p: Puzzle, cages) -> Puzzle` {#pencilmark.model.add_cages}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L438)

cages: list of (sum_or_None, [cell indices])

### `def subgrid_ids(p: Puzzle, k: int) -> list` {#pencilmark.model.subgrid_ids}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L445)

Row-major cell ids of samurai sub-grid k (0=TL,1=TR,2=center,3=BL,4=BR).

### `def apply_variant_to_subgrid(p: Puzzle, k: int, variant: str) -> Puzzle` {#pencilmark.model.apply_variant_to_subgrid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L451)

Add a variant's extra constraints to one 9x9 sub-grid of a samurai -- the group-agnostic model doesn't care that they overlap other grids.

### `def samurai(grids: list[str] | None=None, name='') -> Puzzle` {#pencilmark.model.samurai}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L487)

Five overlapping 9x9 grids on a 21x21 canvas (corner grids share a box with the center grid). grids: optional 5 x 81-char strings in order TL, TR, center, BL, BR.

### `def add_predicate(p: Puzzle, cells, fn, name='custom', max_tuples=200000) -> Puzzle` {#pencilmark.model.add_predicate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/model.py#L524)

Generic custom rule over a small group of cells: fn(\*digits) -> bool, compiled to an n-ary table constraint (allowed tuples) by enumerating the cells' domains. Every engine path that understands tables (TableCombination, brute force, featurize) and the CP-SAT verifier then handle it, with no new solver code. Example (diamond: center digit divides the sum of its four orthogonal neighbors): add_predicate(p, [ctr, n, e, s, w], lambda c, \*v: sum(v) % c == 0, "diamond"). Keep groups small (domain product &lt;= max_tuples); larger sums should use sum constraints.

## pencilmark.layers {#pencilmark.layers}

[src/pencilmark/layers.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/layers.py)

Board layers: what a puzzle states besides its digits, in one table.

A layer is a second fact per cell that some rules add and others read: regions to find (a chaos construction) give each cell a region, shading (yin-yang) gives each cell shaded or not. The custom rule language reads a layer with a function of the same name (`region(c)`, `shaded(c)`, [custom](../formats/rules/custom.mdx)).

Adding a layer: one LAYERS row here (the reader, the custom rule language and the puzzle builder find it through `layers_of`); the engine, the card and the renderer then say what they do with it.

The identity colors a card draws (regions found, digit classes, pair coloring) are named here too, so every module picks them from one list (data/palette.json gives each name its shade).

| Name | What it does |
|---|---|
| class [`Layer`](#pencilmark.layers.Layer) |  |
| def [`layers_of`](#pencilmark.layers.layers_of) | the keys of the layers a puzzle's rules add (rule dicts with a "type"), in LAYERS order |

### `class Layer` {#pencilmark.layers.Layer}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/layers.py#L19)

*No docstring.*

### `def layers_of(rules)` {#pencilmark.layers.layers_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/layers.py#L32)

the keys of the layers a puzzle's rules add (rule dicts with a "type"), in LAYERS order

## pencilmark.cbackend {#pencilmark.cbackend}

[src/pencilmark/cbackend.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py)

C++ backend for pencilmark.solver (sources and build script in csolver/).

Drop-in fast paths with behavioral parity to the Python reference:

from pencilmark import cbackend as CB

```
steps, solved = CB.solve(puzzle, params)            # ~ Solver(puzzle, Scorer(params)).solve()
sols = CB.brute_solve(puzzle, limit=2)               # ~ pencilmark.solver.brute_solve
```

Steps are real pencilmark.solver.Step / Move objects, so pencilmark.scoring.grade() works unchanged.

| Name | What it does |
|---|---|
| def [`code_name`](#pencilmark.cbackend.code_name) | Move.code (int from C++) -> short pattern code / fish name. |
| class [`CMove`](#pencilmark.cbackend.CMove) | pencilmark.solver.Move plus structured metadata of the C++-only techniques: xmeta (dict, see XMETA_KEYS),… |
| def [`to_cpuzzle`](#pencilmark.cbackend.to_cpuzzle) | Finalized pencilmark.model.Puzzle -> C++ puzzle (structure only; givens are passed per solve). |
| def [`rg_norm`](#pencilmark.cbackend.rg_norm) | region relations in place, as the engine's rg_normalize (csrc/chaos_logic.cpp): rgc = per cell its group's… |
| def [`rg_anchor`](#pencilmark.cbackend.rg_anchor) |  |
| def [`rg_apply`](#pencilmark.cbackend.rg_apply) | apply a move's region relations (as the engine: joins and differences in order) and normalize |
| def [`shade_seed`](#pencilmark.cbackend.shade_seed) | shading: the given colours per cell (0 unknown, 1 shaded, 2 unshaded), or None without a yin_yang rule |
| def [`aux_seed`](#pencilmark.cbackend.aux_seed) | unknowns / layers: a flag per (variable, value), in the engine's order (the unknowns, then each layer's… |
| def [`aux_apply`](#pencilmark.cbackend.aux_apply) | unknowns / layers: a move's value eliminations (AE_AUX) and pair eliminations (AE_JOINT) on the state |
| def [`shade_apply`](#pencilmark.cbackend.shade_apply) | shading: a move's colour effects (AE_SHADE) on the colour state |
| def [`rg_seed`](#pencilmark.cbackend.rg_seed) | the relations a puzzle starts with: its same-region sets joined, its given borders apart (None without… |
| def [`id_joins`](#pencilmark.cbackend.id_joins) | the class joins [(cell, anchor)] among identity effects |
| def [`id_changes`](#pencilmark.cbackend.id_changes) | the move changes the identity state (a join or a difference, not only a use) |
| def [`id_norm`](#pencilmark.cbackend.id_norm) | identity state in place, as the engine's id_normalize (csrc/set_logic.cpp): idc = class per cell (0 none,… |
| def [`id_apply`](#pencilmark.cbackend.id_apply) | apply a move's identity effects (joins, then differences, as the engine) and normalize |
| def [`id_held`](#pencilmark.cbackend.id_held) | identity layer route accounting: which steps cost nothing. |
| def [`detect_lines`](#pencilmark.cbackend.detect_lines) | Line structure hidden in pair relations (translators emit thermos, whispers, kropki dots as pair tables):… |
| def [`solve`](#pencilmark.cbackend.solve) | Run the C++ solver. |
| def [`explain_record`](#pencilmark.cbackend.explain_record) | the engine's structured justification of one state_moves(details=True) move (as solve(explain=True) gives),… |
| def [`state_moves`](#pencilmark.cbackend.state_moves) | Every move available at ONE state (puzzle.givens = filled cells; puzzle.domains = the marks / allowed digits… |
| class [`BruteResult`](#pencilmark.cbackend.BruteResult) | brute_solve result: the solutions found (a list, as before) plus .complete: False when the node limit… |
| def [`brute_solve`](#pencilmark.cbackend.brute_solve) | pencilmark.solver.brute_solve equivalent; start = (vals, cand) or None. |
| def [`computer_search`](#pencilmark.cbackend.computer_search) | Pure computer search: unbounded trial, forcing chains / nets (basic, dynamic, nested), Nishio nets, pattern… |
| def [`search_disabled`](#pencilmark.cbackend.search_disabled) | params['search']: 'human' -> no computer search; bounded human case work stays (ShortTrial = contradiction… |
| def [`no_guess_params`](#pencilmark.cbackend.no_guess_params) | Guessing is off by default. |

### `def code_name(code)` {#pencilmark.cbackend.code_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L186)

Move.code (int from C++) -> short pattern code / fish name.

### `class CMove(S.Move)` {#pencilmark.cbackend.CMove}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L277)

pencilmark.solver.Move plus structured metadata of the C++-only techniques: xmeta (dict, see XMETA_KEYS), family, code.

### `def to_cpuzzle(p)` {#pencilmark.cbackend.to_cpuzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L287)

Finalized pencilmark.model.Puzzle -> C++ puzzle (structure only; givens are passed per solve). Relation tables are taken from p.rel_ex, so any relation kind (including ones registered at runtime) works. Cached on the full arguments, so a puzzle whose rules or domains change gets a new build.

### `def rg_norm(rgc, N)` {#pencilmark.cbackend.rg_norm}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L338)

region relations in place, as the engine's rg_normalize (csrc/chaos_logic.cpp): rgc = per cell its group's anchor + 1 (0: on its own), then the pairs of anchors + 1 known to differ, sorted and flattened

### `def rg_anchor(rgc, c)` {#pencilmark.cbackend.rg_anchor}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L362)

*No docstring.*

### `def rg_apply(rgc, N, fx)` {#pencilmark.cbackend.rg_apply}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L366)

apply a move's region relations (as the engine: joins and differences in order) and normalize

### `def shade_seed(p)` {#pencilmark.cbackend.shade_seed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L385)

shading: the given colours per cell (0 unknown, 1 shaded, 2 unshaded), or None without a yin_yang rule

### `def aux_seed(p)` {#pencilmark.cbackend.aux_seed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L398)

unknowns / layers: a flag per (variable, value), in the engine's order (the unknowns, then each layer's value per board cell; csrc bindings aux_defs), the given layer values alone set -> (flags, offsets, joint), or None without any; joint: per variable the (digit, value) pairs ruled out, as the engine's bits (Solver::jbit)

### `def aux_apply(aux, fx)` {#pencilmark.cbackend.aux_apply}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L417)

unknowns / layers: a move's value eliminations (AE_AUX) and pair eliminations (AE_JOINT) on the state

### `def shade_apply(shade, fx)` {#pencilmark.cbackend.shade_apply}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L426)

shading: a move's colour effects (AE_SHADE) on the colour state

### `def rg_seed(p)` {#pencilmark.cbackend.rg_seed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L433)

the relations a puzzle starts with: its same-region sets joined, its given borders apart (None without regions to find)

### `def id_joins(fx)` {#pencilmark.cbackend.id_joins}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L446)

the class joins [(cell, anchor)] among identity effects

### `def id_changes(fx)` {#pencilmark.cbackend.id_changes}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L451)

the move changes the identity state (a join or a difference, not only a use)

### `def id_norm(idc, vals)` {#pencilmark.cbackend.id_norm}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L456)

identity state in place, as the engine's id_normalize (csrc/set_logic.cpp): idc = class per cell (0 none, else 1 + the class's first cell), then the class differences as sorted (lo, hi) class-id pairs, flattened. A class lives while it has an open member and two members or a difference partner; one with every member placed lives on while a partner has an open member; a pair lives while both its classes do.

### `def id_apply(idc, vals, fx)` {#pencilmark.cbackend.id_apply}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L494)

apply a move's identity effects (joins, then differences, as the engine) and normalize

### `def id_held(N, givens, steps)` {#pencilmark.cbackend.id_held}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L516)

identity layer route accounting: which steps cost nothing. steps = [(place, elims, idfx)] in route order. A step that only changes the identity state (joins / differences, no placement or elimination) is held when made. A step with a placement or elimination is charged, and so is every held step it relies on, transitively: a step that uses class K (AE_ID_USE) relies on each earlier held join whose cells are now in K, and on each earlier held difference whose two cells are now in two classes it uses. Held steps no charged step relies on were never needed: the route without them is the same proof. Returns a list of bools (True = held and never used: priced 0).

### `def detect_lines(p)` {#pencilmark.cbackend.detect_lines}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L634)

Line structure hidden in pair relations (translators emit thermos, whispers, kropki dots as pair tables): chains of >= 3 cells become {"type":"line"} constraints for the line layer (the pair tables stay).

### `def solve(puzzle, params=None, disabled=(), solution=None, allow_direct=True, max_steps=5000, cpuzzle=None, assume_unique=True, all_tiers=False, explain=False, colour_seeds=None, cand=None, labels=None, stop_cells=None)` {#pencilmark.cbackend.solve}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L704)

Run the C++ solver. Returns (steps, solved) with steps as pencilmark.solver.Step objects (alts = feature tuples, move.d set). cand = per-cell candidate mask of a mid-solve state (as state_moves(cand=)): pass the original puzzle + a cpuzzle built once from it, with puzzle.givens = the filled cells.

### `def explain_record(puzzle, move, cpuzzle=None)` {#pencilmark.cbackend.explain_record}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L797)

the engine's structured justification of one state_moves(details=True) move (as solve(explain=True) gives), or None when the move carries no records

### `def state_moves(puzzle, params=None, all_tiers=True, assume_unique=False, limit_per_tech=0, disabled=(), solution=None, cpuzzle=None, written=None, details=False, cand=None, skip=(), labels=None)` {#pencilmark.cbackend.state_moves}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L822)

Every move available at ONE state (puzzle.givens = filled cells; puzzle.domains = the marks / allowed digits per cell), across all technique families (direct and notes; tiers not gated -- all_tiers is accepted for clarity, the enumeration is always ungated). Returns a list of dicts sorted by price: tech (code), name, code (pattern code name or None), place ((cell, digit) or None), elim [(cell, digit), ...], d (the move's priced difficulty, Scorer.difficulty incl. covers and the soft cap). limit_per_tech keeps the cheapest n moves per technique (0 = all). assume_unique: allow uniqueness techniques (proven-unique puzzles only). solution: optional, used by Guess only. dev75+: written = per-cell bitmask of the candidates written down in this state (a replay's marks; sets the held / coverage descriptors; None = by technique: direct techniques use no notes, the others full notes); details=True adds meta (the move's meta tuple incl. descriptors), desc ({name: value}), xmeta, scan (raw count of patterns of the move's kind at this state, behind desc 'search') and pattern (cells). cand = per-cell candidate bitmask of a mid-solve state, applied after the givens: pass the ORIGINAL puzzle (and a cpuzzle built once from it) instead of rewriting puzzle.domains -- fast (no rebuild) and the puzzle's own domains stay what pattern detection expects. skip = techniques whose notes-tier strategies are not run: unlike disabled, every other strategy sees the same disabled flags, so the result is exactly the full listing's moves minus (some of) the skipped techniques'.

### `class BruteResult(list)` {#pencilmark.cbackend.BruteResult}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L930)

brute_solve result: the solutions found (a list, as before) plus .complete: False when the node limit stopped the search before a verdict (then [] does NOT mean "no solution", and one solution does not mean "unique").

### `def brute_solve(puzzle, limit=2, start=None, node_limit=2000000, cpuzzle=None)` {#pencilmark.cbackend.brute_solve}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L938)

pencilmark.solver.brute_solve equivalent; start = (vals, cand) or None. Returns a list of solutions (BruteResult: check .complete -- False = node limit hit, verdict unknown).

### `def computer_search()` {#pencilmark.cbackend.computer_search}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L951)

Pure computer search: unbounded trial, forcing chains / nets (basic, dynamic, nested), Nishio nets, pattern overlay. Humans don't solve this way (CTC hosts: 0 'bifurcate' at 119 engine guess points).

### `def search_disabled(params)` {#pencilmark.cbackend.search_disabled}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L957)

params['search']: 'human' -> no computer search; bounded human case work stays (ShortTrial = contradiction within 4 rounds, i.e. a short Bowman's Bingo; WhatIf, EitherWay, MentalChain, case analysis). 'computer' / absent -> all. params['disabled_techniques']: extra technique ids to switch off.

### `def no_guess_params(sc_p, params, disabled=())` {#pencilmark.cbackend.no_guess_params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cbackend.py#L972)

Guessing is off by default. Human mode without params['allow_guess']: where a step would guess, the solver refutes one candidate by full search instead (Trial and error, band Extreme), so every unique puzzle gets a band. allow_guess=True: the solver guesses there and the card says Unknown. A caller that switches TRIAL off explicitly (a singles-only batch, a one-technique probe) stops where it is stuck.

## pencilmark.engine_records {#pencilmark.engine_records}

[src/pencilmark/engine_records.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/engine_records.py)

Decoding the engine's explanation records: the structured justification of one move (solve(explain=True), cbackend.explain_record) from the integer records the C++ engine writes (csrc/solver.hpp EX_\* tags): its pattern, base and cover units, chains, almost locked sets, the cases tried, the rules used. The explainer (pencilmark/explain) reads these instead of finding the pattern again.

## pencilmark.solver {#pencilmark.solver}

[src/pencilmark/solver.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/solver.py)

Technique codes, names and the Move / Step records shared by the C++ solver's decoder, the scorer and the explainer. (The solver itself lives in csrc/solver.cpp.)

Each move carries a compact feature tuple consumed by scoring.Scorer: (tech, base_shape, cover, extra) cover = tuple of (kind, shape, uncovered_before) -- the set-cover sequence used to find a single (naked: covering digits with groups; hidden: covering cells with crosshatch sources), in the order a human would plausibly add them.

| Name | What it does |
|---|---|
| class [`Move`](#pencilmark.solver.Move) |  |
| class [`Step`](#pencilmark.solver.Step) |  |

### `class Move` {#pencilmark.solver.Move}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/solver.py#L122)

*No docstring.*

### `class Step` {#pencilmark.solver.Step}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/solver.py#L135)

*No docstring.*

## pencilmark.registry {#pencilmark.registry}

[src/pencilmark/registry.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py)

The technique registry: every fact about a technique, a chip code or an engine pattern code, read from three tables in pencilmark/data. Grader, card, generator and explainer modules derive their lookups from here; nothing else holds a copy. The C++ engine keeps its own enum (csrc/solver.hpp), which tests/test_registry.py checks against this table.

```
data/techniques.csv, one row per engine technique (solver.TECH_NAMES):
  id              the engine's technique id (enum Tech in csrc/solver.hpp)
  const           the constant naming it in csrc/solver.hpp and pencilmark/solver.py
  name            the engine name (params, steps, explanations)
  role            logic | notes (writing pencil marks) | guess | pseudo (a switch, not a move: CanonicalEnumeration)
  code            the chip code on the card (codes.csv); blank for TakeNotes and CanonicalEnumeration, which are never
                  shown
  display         the chip's name for this technique; blank = the code's name in codes.csv
  band            the band of a step by this technique (BANDS); for a split technique, its lowest shape's band; blank
                  for steps that have no band (notes, guess, pseudo)
  split           1: the band depends on the shape found (X-Wing vs Franken X-Wing, Skyscraper vs long X-Chain), so the
                  route names the step by its shape (codes.csv shape_band)
  family          the pricing family (FAMILIES): the engine's structural groups for features; blank for the roles
                  other than logic
  gate            any: switched on only for puzzles with some variant rule; sum: only with a sum rule; blank: always
  direct          1: a move made without pencil marks (also csrc/solver.hpp is_direct)
  mental          1: worked out in the head on the no-notes view (a subset, short chain or case split without notes):
                  priced at least as its written form (params mental_floor), left out of the card score's first solve
  price           the starting price B of a step (scoring.DEFAULT_PARAMS): what a model fitted before the technique
                  existed uses; the shipped prices are the fitted ones (data/params.json). Blank: no own price
  price_fallback  blank: the technique has its own fitted price B. Otherwise it has none: it is always priced by the
                  structural meta model and borrows this technique's B when params carry no meta model
```

```
data/codes.csv, one row per chip code a route step can carry:
  code        three-letter chip code, Andrew Stuart's (sudokuwiki.org) where he has the strategy
  name        the code's name (CLI lists, alternatives)
  shape_band  band of a step named by this shape (a Skyscraper is Hard, a long X-Chain Very Hard); blank for codes that
              only name a technique (the technique's band applies)
  order       study order inside a band: the route takes the lowest first; ties go to the cheaper move
  subset_of   the codes this one is always a special case of (every X-Wing is a Skyscraper), space-separated
  se_classic  Sudoku Explainer rating (Juillerat's table, the one expert solvers quote); "-": SE has no such
              technique (se.py rates it 7.0)
  explain     the explanation catalog entry that teaches it (explain.CATALOG: names, aliases, links to explainer
              sites); blank when there is none
  note        why: the reason for a subset_of entry or an order (free text, not read by the code)
```

```
data/patterns.csv, one row per pattern code the engine puts on a move (Move.code, an int):
  cpp_code      the int the engine writes
  engine_code   its name in Python (cbackend.code_name)
  technique     the engine technique whose steps this code renames (blank: the code does not rename the step)
  code          the chip code of a step with this pattern
  step_name     the step's name on the route
  explain_name  the pattern's name in explanations (the explain package; blank = the technique's)
  catalog_key   the explanation catalog entry for this pattern (explain.CATALOG)
```

| Name | What it does |
|---|---|
| class [`Technique`](#pencilmark.registry.Technique) | One row of data/techniques.csv (columns in the module docstring). |
| class [`Code`](#pencilmark.registry.Code) | One row of data/codes.csv (columns in the module docstring). |
| class [`Pattern`](#pencilmark.registry.Pattern) | One row of data/patterns.csv (columns in the module docstring). |
| def [`techniques`](#pencilmark.registry.techniques) | Every engine technique, in file order (data/techniques.csv). |
| def [`codes`](#pencilmark.registry.codes) | Chip code -> its row of data/codes.csv, in file order. |
| def [`patterns`](#pencilmark.registry.patterns) | Every engine pattern code, by cpp_code (data/patterns.csv). |
| def [`by_name`](#pencilmark.registry.by_name) | Engine name -> technique. |
| def [`chip`](#pencilmark.registry.chip) | (chip code, chip name) of a technique that has a code. |

### `class Technique` {#pencilmark.registry.Technique}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L68)

One row of data/techniques.csv (columns in the module docstring).

### `class Code` {#pencilmark.registry.Code}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L88)

One row of data/codes.csv (columns in the module docstring).

### `class Pattern` {#pencilmark.registry.Pattern}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L101)

One row of data/patterns.csv (columns in the module docstring).

### `def techniques() -> tuple[Technique, ...]` {#pencilmark.registry.techniques}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L138)

Every engine technique, in file order (data/techniques.csv).

### `def codes() -> dict[str, Code]` {#pencilmark.registry.codes}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L165)

Chip code -> its row of data/codes.csv, in file order.

### `def patterns() -> tuple[Pattern, ...]` {#pencilmark.registry.patterns}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L186)

Every engine pattern code, by cpp_code (data/patterns.csv).

### `def by_name() -> dict[str, Technique]` {#pencilmark.registry.by_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L203)

Engine name -> technique.

### `def chip(t: Technique) -> tuple[str, str]` {#pencilmark.registry.chip}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/registry.py#L208)

(chip code, chip name) of a technique that has a code.

## pencilmark.cpsat_verify {#pencilmark.cpsat_verify}

[src/pencilmark/cpsat_verify.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py)

Uniqueness checks with OR-Tools CP-SAT when installed (pip install "pencilmark[verify]"), else the engine's exhaustive C++ search.

solutions(p, limit=2, time_limit=60) -> list of solutions (each a list of digits, len p.N), or None if undecided: the puzzle uses a rule the checker does not model, or the search hit its node / time limit. decide() (used by rate, solve and count_solutions) runs the C++ search (cbackend.brute_solve) first, which settles most puzzles in microseconds. With OR-Tools installed that first search gets QUICK_NODES and CP-SAT takes over when it runs out (a sparse killer on a big board: 0.4 s instead of 27 s); without it, or when CP-SAT cannot decide, the C++ search gets the full NODE_LIMIT. CP-SAT is independent of the engine's propagation. Pair relations are encoded generically as allowed-pair tables from model.RELATIONS, so any relation kind works.

| Name | What it does |
|---|---|
| def [`has_shading`](#pencilmark.cpsat_verify.has_shading) | True if the puzzle has a shading layer (yin-yang, [whole-board-rules](../formats/rules/whole-board-rules.mdx)) |
| def [`has_chaos`](#pencilmark.cpsat_verify.has_chaos) | True if the puzzle has regions to find ([houses-and-regions](../formats/rules/houses-and-regions.mdx) 6.3) |
| def [`have_ortools`](#pencilmark.cpsat_verify.have_ortools) | True if OR-Tools CP-SAT can be imported (checked once). |
| def [`supported`](#pencilmark.cpsat_verify.supported) | True if every relation / constraint of the finalized puzzle is one the checker models. |
| def [`build_model`](#pencilmark.cpsat_verify.build_model) |  |
| def [`cpsat_solutions`](#pencilmark.cpsat_verify.cpsat_solutions) | CP-SAT only (needs OR-Tools): solutions, or None if a rule can't be expressed or the time limit is hit. |
| def [`solutions`](#pencilmark.cpsat_verify.solutions) | up to `limit` solutions, or None if undecided. |
| def [`count`](#pencilmark.cpsat_verify.count) |  |
| def [`verified_solutions`](#pencilmark.cpsat_verify.verified_solutions) | Drop-in for cbackend.brute_solve(p, limit, node_limit) when verifying a translation: CP-SAT first when… |
| def [`decide`](#pencilmark.cpsat_verify.decide) | -> (solutions, decided). |

### `def has_shading(p)` {#pencilmark.cpsat_verify.has_shading}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L54)

True if the puzzle has a shading layer (yin-yang, [whole-board-rules](../formats/rules/whole-board-rules.mdx))

### `def has_chaos(p)` {#pencilmark.cpsat_verify.has_chaos}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L104)

True if the puzzle has regions to find ([houses-and-regions](../formats/rules/houses-and-regions.mdx) 6.3)

### `def have_ortools()` {#pencilmark.cpsat_verify.have_ortools}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L707)

True if OR-Tools CP-SAT can be imported (checked once).

### `def supported(p)` {#pencilmark.cpsat_verify.supported}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L721)

True if every relation / constraint of the finalized puzzle is one the checker models.

### `def build_model(p)` {#pencilmark.cpsat_verify.build_model}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L770)

*No docstring.*

### `def cpsat_solutions(p, limit=2, time_limit=60.0, workers=1)` {#pencilmark.cpsat_verify.cpsat_solutions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L1019)

CP-SAT only (needs OR-Tools): solutions, or None if a rule can't be expressed or the time limit is hit.

### `def solutions(p, limit=2, time_limit=60.0, workers=1, node_limit=NODE_LIMIT)` {#pencilmark.cpsat_verify.solutions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L1048)

up to `limit` solutions, or None if undecided. With OR-Tools: CP-SAT (None if a rule can't be expressed or the time limit is hit). Without: the engine's exhaustive search on the rules CP-SAT models (None for others, or if the node or time limit is hit), so both installs reach the same verdicts.

### `def count(p, limit=2, time_limit=60.0)` {#pencilmark.cpsat_verify.count}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L1062)

*No docstring.*

### `def verified_solutions(p, limit=2, node_limit=NODE_LIMIT, time_limit=60.0)` {#pencilmark.cpsat_verify.verified_solutions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L1067)

Drop-in for cbackend.brute_solve(p, limit, node_limit) when verifying a translation: CP-SAT first when OR-Tools is installed, then the engine's exhaustive search (possibly partial if it hits the node or time limit).

### `def decide(p, limit=2, node_limit=NODE_LIMIT, time_limit=60.0)` {#pencilmark.cpsat_verify.decide}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/cpsat_verify.py#L1078)

-> (solutions, decided). decided False: neither search could finish (solutions may be partial).

## pencilmark.rule_lemmas {#pencilmark.rule_lemmas}

[src/pencilmark/rule_lemmas.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rule_lemmas.py)

Rule lemmas: what a one-off custom rule implies, derived from the rule itself before solving, case by case of its parameters (the engine's rule analysis, csrc/absint.cpp expr_rule_lemmas), and handed to the engine as lemma rules (docs/research/rule_lemmas_cas.md). A case that cannot hold removes that digit from the parameter cell; a case decided by one or two other cells becomes a small table over the parameter and those cells. Each lemma rule carries a lemma price: its setup the first time a route uses any rule of its content, then the cheaper use. The whole-rule table of a rule over more than SMALL cells and no unknowns is gated: no human step reads it (the search still checks it), the lemmas stand in.

A lemma over unknowns or layer values is written as a small custom rule ("P != 6", or the allowed combinations as an or of ands) and read by AuxRule with the lemma's price.

Off unless ENABLED[0] (experiments: runs/rule_lemmas).

| Name | What it does |
|---|---|
| def [`add`](#pencilmark.rule_lemmas.add) | p: the puzzle being built (groups, givens, aux set); doc: its file dict; spans: (rule, first, end) of each… |

### `def add(p, doc, spans)` {#pencilmark.rule_lemmas.add}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rule_lemmas.py#L42)

p: the puzzle being built (groups, givens, aux set); doc: its file dict; spans: (rule, first, end) of each custom rule's engine constraints in p.constraints. Appends the lemma rules and gates wide whole-rule tables.

## pencilmark._data {#pencilmark._data}

[src/pencilmark/_data.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/_data.py)

Package data (model parameters and tables shipped with pencilmark).

| Name | What it does |
|---|---|
| def [`path`](#pencilmark._data.path) | a file in pencilmark/data as an importlib Traversable. |
| def [`exists`](#pencilmark._data.exists) | True if pencilmark/data has a file called name |
| def [`read_text`](#pencilmark._data.read_text) | UTF-8 text of a file in pencilmark/data |
| def [`load_json`](#pencilmark._data.load_json) | parsed JSON of a file in pencilmark/data |
| def [`load_params`](#pencilmark._data.load_params) | raw engine parameters (before scoring.complete_params). |

### `def path(name)` {#pencilmark._data.path}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/_data.py#L9)

a file in pencilmark/data as an importlib Traversable.

### `def exists(name)` {#pencilmark._data.exists}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/_data.py#L14)

True if pencilmark/data has a file called name

### `def read_text(name)` {#pencilmark._data.read_text}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/_data.py#L19)

UTF-8 text of a file in pencilmark/data

### `def load_json(name)` {#pencilmark._data.load_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/_data.py#L24)

parsed JSON of a file in pencilmark/data

### `def load_params(name='params.json')` {#pencilmark._data.load_params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/_data.py#L40)

raw engine parameters (before scoring.complete_params).
