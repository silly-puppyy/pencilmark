---
title: "The generator"
description: "One puzzle for a sudoku-spec request."
toc_max_heading_level: 2
---

# The generator

One puzzle for a sudoku-spec request. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.gen {#pencilmark.gen}

[src/pencilmark/gen/__init__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/__init__.py)

Puzzle generator: one puzzle for a "sudoku-spec" request ([Generator spec](../formats/generator-spec.md)) -- difficulty / band / technique targets, classic and variants, any standard board size.

from pencilmark import generate          # or pencilmark.gen.generate

```
r = generate({"format": "sudoku-spec", "format_version": 1, "board": {"rows": 9, "cols": 9}, "digits": 9,
              "rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}], "where": {"band": "Hard"}})
r["puzzle"]   # sudoku-puzzle (with solution)
r["card"]     # sudoku-grade card (difficulty, time, band, contains)
r["info"]     # mode, givens, element counts, attempts, seconds, rejection reasons, unique_verified
```

The parts of the spec the generator runs are listed in [Generator spec](../formats/generator-spec.md); anything else raises NotSupportedError. Every result is unique (re-checked with CP-SAT when OR-Tools is installed). Multi-grid boards are not supported by the generator.

## pencilmark.gen.api {#pencilmark.gen.api}

[src/pencilmark/gen/api.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py)

generate(spec) -> {"puzzle", "card", "info"}: the public entry point of pencilmark.gen.

| Name | What it does |
|---|---|
| class [`Spec`](#pencilmark.gen.api.Spec) | what to generate. |
| def [`board_of`](#pencilmark.gen.api.board_of) | the Board of a Spec: its size and layout, with the locked rules' all-different units (extra regions,… |
| def [`feasibility`](#pencilmark.gen.api.feasibility) | fast checks before any search; returns a list of problems (empty = go). |
| def [`generate`](#pencilmark.gen.api.generate) | generate one puzzle meeting a sudoku-spec request ([Generator spec](../formats/generator-spec.md); a dict, JSON text or a… |
| def [`is_unique`](#pencilmark.gen.api.is_unique) | CP-SAT: does the puzzle JSON have exactly one solution? |
| def [`uniquify`](#pencilmark.gen.api.uniquify) | make a single-grid puzzle JSON unique by adding givens from its solution (the "solution" field, else the… |

### `class Spec` {#pencilmark.gen.api.Spec}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py#L26)

what to generate.

```
size              board size (4, 6, 8, 9, 10, 12, 16; standard boxes)
layout            None (one size x size grid) or a named multi-grid layout of 9 x 9 grids (samurai, ...)
locked            sudoku-puzzle rules every result carries (all-different ones: diagonals, extra regions, windoku
                  windows, anti-knight, anti-king); the solution respects them
grid_givens       [[min, max], ...] givens per grid of the layout (in its origins' order); None = no bound
quality           None (no filtering), or the publishing checks as rate() takes them ({} = the defaults): a
                  candidate with a reject issue is not returned
elements          {kind or class: N | [min, max] | "auto" | "full" | "min" | "partition"}: N = at least N needed elements
                  (0 / None / "auto" = allowed, not required); [min, max] = between min and max (max None = no cap;
                  [2, 2] = exactly 2). Classes count one colour / letter / parity of a kind: kropki_white, kropki_black,
                  x, v, odd, even ({"kropki_black": [2, 2], "kropki_white": "auto"}); {"kropki": "full"} = zero-given
                  full kropki (no dot = neither relation);
                  {"kropki": "min"} = zero-given minimal dot set; {"cage": "partition"} = killer tiled by cages, few
                  givens; {"cage": N} with max_givens=0 = killer with exactly N cages and no givens (CP-SAT);
                  "max" = as many as fit: the run uses its whole time and keeps the result with the most
shape             {kind: {"length": [lo, hi], "sum": [lo, hi]}}: limits on the placed elements (length: cells of a
                  cage or line, the shaft of an arrow; sum: cages); None = no limit on that side
kinds             shorthand: every listed kind keeps >= 1 needed element (each-kind mode)
target_band       "Very Easy" .. "Extreme" (or 0..6): the card's band must equal it
target_difficulty [lo, hi] on the card's difficulty scale, or "max" / "min": the hardest / easiest result found in
                  the whole time
require           technique codes the card must contain (e.g. ["XWG"]); strict_require = listed as the code itself,
                  not only as an alternative chip
symmetry          None | rot180 | rot90 | mirror | mirror_v | diagonal | antidiagonal (for givens)
min_givens / max_givens   digging floor / upper bound on the result's givens
max_elements      upper bound on the number of rule elements
solver            "logic" (every step solvable by human logic within the band cap: unique by construction) or
                  "cpsat" (uniqueness only; min kropki); cage-count and full kropki always use CP-SAT
seed, time_limit  determinism and the overall budget in seconds
```

#### `def from_any(cls, spec)` {#pencilmark.gen.api.Spec.from_any}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py#L82)

*No docstring.*

### `def board_of(s)` {#pencilmark.gen.api.board_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py#L187)

the Board of a Spec: its size and layout, with the locked rules' all-different units (extra regions, diagonals, windows; anti-knight / anti-king pairs) and their puzzle JSON parts for every candidate

### `def feasibility(spec)` {#pencilmark.gen.api.feasibility}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py#L230)

fast checks before any search; returns a list of problems (empty = go). Includes an information budget: givens and elements together must be able to carry log2(#grids) bits, and classic clue counts can't go below known minimums.

### `def generate(spec, log=None)` {#pencilmark.gen.api.generate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py#L398)

generate one puzzle meeting a sudoku-spec request ([Generator spec](../formats/generator-spec.md); a dict, JSON text or a path). Returns {"puzzle": sudoku-puzzle (with solution; meta.generated_from = the spec's fingerprint), "card": sudoku-grade card, "info": {...}}. Raises NotSupportedError for a part of the spec the generator does not run, GenerationFailed when no puzzle met it in time.

### `def is_unique(puzzle, time_limit=30.0)` {#pencilmark.gen.api.is_unique}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py#L712)

CP-SAT: does the puzzle JSON have exactly one solution? (None = undecided in time / unsupported rule).

### `def uniquify(puzzle, seed=0, time_limit=30.0, minimize=True)` {#pencilmark.gen.api.uniquify}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/api.py#L722)

make a single-grid puzzle JSON unique by adding givens from its solution (the "solution" field, else the first CP-SAT solution); any rule set CP-SAT can express. Each CP-SAT counterexample is cached; the cell the most cached counterexamples disagree on becomes the next given. With minimize, added givens that turn out unnecessary are dropped again. Returns a new puzzle JSON; raises GenerationFailed if there is no solution or CP-SAT can't decide.

## pencilmark.gen.board {#pencilmark.gen.board}

[src/pencilmark/gen/board.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/board.py)

Standard n x n board geometry and random full grids.

| Name | What it does |
|---|---|
| def [`grid_log2`](#pencilmark.gen.board.grid_log2) | log2(number of n x n sudoku grids); a deliberately low estimate for sizes without a known count (safe for a… |
| class [`Board`](#pencilmark.gen.board.Board) | the cells, houses and neighbours of the board being generated: one n x n grid with standard boxes, or a… |

### `def grid_log2(n)` {#pencilmark.gen.board.grid_log2}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/board.py#L21)

log2(number of n x n sudoku grids); a deliberately low estimate for sizes without a known count (safe for a budget bound: underestimating the entropy only lets more specs through).

### `class Board` {#pencilmark.gen.board.Board}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/board.py#L29)

the cells, houses and neighbours of the board being generated: one n x n grid with standard boxes, or a named multi-grid layout of 9 x 9 grids (samurai, super-samurai, ...: puzzle_json's layouts). Cell indices follow puzzle_json's cell order, so a puzzle's numbers string lines up. extra: more all-different units (extra regions, diagonals) that the solution must respect.

#### `def rc(self, i)` {#pencilmark.gen.board.Board.rc}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/board.py#L76)

*No docstring.*

#### `def solution(self, rng, preset=None)` {#pencilmark.gen.board.Board.solution}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/board.py#L80)

random full grid: bitmask backtracking, fewest candidates first. A board the backtracking cannot fill within its step budget (a layout with diagonals and windows) is completed by the engine's search from a few random digits, then relabelled with a random digit permutation. preset {cell: digit}: cells the grid keeps (then no relabelling); None if they cannot be completed.

#### `def orbit(self, i, symmetry)` {#pencilmark.gen.board.Board.orbit}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/board.py#L157)

cells that must be given / empty together with cell i under the symmetry (None = just i).

## pencilmark.gen.elements {#pencilmark.gen.elements}

[src/pencilmark/gen/elements.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py)

Rule elements a generated puzzle can carry, true in a given solution grid.

An element is a tuple (kind, cells, extra): ("cage", sorted cells, total)          killer cage, distinct digits ("thermo", path, None)                 strictly increasing from the bulb (path[0]) ("whisper", path, None)                German whisper, neighbours differ by >= whisper_gap(n) ("renban", path, None)                 a set of consecutive digits, any order ("between", path, None)                interior digits strictly between the two end circles ("arrow", (circle,) + shaft, None)     shaft digits sum to the circle digit ("kropki", (i, j), "white" | "black")  consecutive / 1:2 ratio ("xv", (i, j), "X" | "V")              sum 10 / sum 5 ("parity", (i,), 1 | 0)                odd / even cell (graphical rule, not candidates)

| Name | What it does |
|---|---|
| def [`norm_kind`](#pencilmark.gen.elements.norm_kind) | a kind or an element class name -> its canonical name |
| def [`base_kind`](#pencilmark.gen.elements.base_kind) |  |
| def [`element_class`](#pencilmark.gen.elements.element_class) | the class of an element: its colour / letter / parity class where one exists, else its kind |
| def [`in_class`](#pencilmark.gen.elements.in_class) |  |
| def [`whisper_gap`](#pencilmark.gen.elements.whisper_gap) | German-whisper gap: 5 on 9x9 (standard); about half the digit range otherwise. |
| def [`ncomb`](#pencilmark.gen.elements.ncomb) | number of digit sets of `size` from 1..n summing to `total` (1 = the cage's digit set is fully determined). |
| def [`length_of`](#pencilmark.gen.elements.length_of) | an element's length as a template counts it: cells of a cage or line, the shaft of an arrow |
| def [`fits`](#pencilmark.gen.elements.fits) | does the element meet its template's shape limits? |
| def [`grow`](#pencilmark.gen.elements.grow) | elements of `kind` through cell `start`, disjoint from `taken`, true in the solution and within the… |
| def [`planted_whisper`](#pencilmark.gen.elements.planted_whisper) | (path, {cell: digit}) of a German whisper of `length` cells to build a grid around: a random self-avoiding… |
| def [`satisfies`](#pencilmark.gen.elements.satisfies) | does the full grid g satisfy the givens and every element? |
| def [`to_json`](#pencilmark.gen.elements.to_json) | puzzle JSON (pencilmark/puzzle_json format) for givens {cell: digit} and elements. |
| def [`all_dots`](#pencilmark.gen.elements.all_dots) | every kropki dot true in the solution, and the dot-free pairs (for the full-kropki negative rule). |
| def [`element_bits`](#pencilmark.gen.elements.element_bits) | upper bound (bits) on what one element of `kind` can tell: log2(placements) + log2(values). |

### `def norm_kind(k)` {#pencilmark.gen.elements.norm_kind}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L55)

a kind or an element class name -> its canonical name

### `def base_kind(k)` {#pencilmark.gen.elements.base_kind}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L64)

*No docstring.*

### `def element_class(e)` {#pencilmark.gen.elements.element_class}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L68)

the class of an element: its colour / letter / parity class where one exists, else its kind

### `def in_class(e, k)` {#pencilmark.gen.elements.in_class}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L76)

*No docstring.*

### `def whisper_gap(n)` {#pencilmark.gen.elements.whisper_gap}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L80)

German-whisper gap: 5 on 9x9 (standard); about half the digit range otherwise.

### `def ncomb(n, size, total)` {#pencilmark.gen.elements.ncomb}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L88)

number of digit sets of `size` from 1..n summing to `total` (1 = the cage's digit set is fully determined).

### `def length_of(e)` {#pencilmark.gen.elements.length_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L99)

an element's length as a template counts it: cells of a cage or line, the shaft of an arrow

### `def fits(e, shape)` {#pencilmark.gen.elements.fits}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L104)

does the element meet its template's shape limits? shape {kind: {"length": (lo, hi), "sum": (lo, hi)}}

### `def grow(b, kind, sol, start, taken, rng, n=40, shape=None)` {#pencilmark.gen.elements.grow}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L116)

elements of `kind` through cell `start`, disjoint from `taken`, true in the solution and within the template's shape limits (`fits`); most informative first.

### `def planted_whisper(b, length, rng, tries=200)` {#pencilmark.gen.elements.planted_whisper}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L273)

(path, {cell: digit}) of a German whisper of `length` cells to build a grid around: a random self-avoiding path (fewest onward cells first) and digits alternating low / high, the gap kept, different within each house. Random grids rarely hold a whisper of more than about 20 cells (22 at most in 1,500 9 x 9 grids); a longer one is planted first and the grid completed around it. None if no path or digits were found.

### `def satisfies(b, g, givens, els)` {#pencilmark.gen.elements.satisfies}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L317)

does the full grid g satisfy the givens and every element? (cheap check used against cached alternative solutions; houses always hold because alternatives are valid grids of the same board).

### `def to_json(b, givens, els, sol=None, title=None)` {#pencilmark.gen.elements.to_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L362)

puzzle JSON (pencilmark/puzzle_json format) for givens {cell: digit} and elements.

### `def all_dots(b, sol)` {#pencilmark.gen.elements.all_dots}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L421)

every kropki dot true in the solution, and the dot-free pairs (for the full-kropki negative rule).

### `def element_bits(b, kind)` {#pencilmark.gen.elements.element_bits}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/elements.py#L435)

upper bound (bits) on what one element of `kind` can tell: log2(placements) + log2(values). Loose on purpose: it only rejects specs that cannot possibly be unique.

## pencilmark.gen.checks {#pencilmark.gen.checks}

[src/pencilmark/gen/checks.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py)

Solvability / uniqueness checks used while generating.

Checker  -- band-capped human solve (the engine with only techniques of band &lt;= cap, or an explicit technique set): "solvable" means every cell is placed by logic, which implies a unique solution, so digging needs no separate uniqueness search. Oracle   -- CP-SAT uniqueness with a counterexample cache (CEGAR): every alternative solution CP-SAT finds is kept and refutes later candidates in pure Python; only candidates that refute the whole cache reach CP-SAT.

| Name | What it does |
|---|---|
| def [`params`](#pencilmark.gen.checks.params) | the engine's params with search='human' (loaded once); path: a JSON params file of the same shape instead. |
| def [`logic_techs`](#pencilmark.gen.checks.logic_techs) | engine techniques usable by a human route (no computer search, no guessing, no note-taking pseudo moves). |
| def [`band_techs`](#pencilmark.gen.checks.band_techs) | logic techniques of band cap or lower |
| def [`code_techs`](#pencilmark.gen.checks.code_techs) | engine techniques whose chip is `code` (shape-split techniques included, e.g. |
| class [`Checker`](#pencilmark.gen.checks.Checker) | solvable by logic with techniques in `allowed` (default: band &lt;= cap) -> unique by construction. |
| class [`Oracle`](#pencilmark.gen.checks.Oracle) | CP-SAT uniqueness with a cache of alternative solutions (single worker: deterministic, light on the machine). |

### `def params(path=None)` {#pencilmark.gen.checks.params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L24)

the engine's params with search='human' (loaded once); path: a JSON params file of the same shape instead.

### `def logic_techs(P)` {#pencilmark.gen.checks.logic_techs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L44)

engine techniques usable by a human route (no computer search, no guessing, no note-taking pseudo moves).

### `def band_techs(P, cap)` {#pencilmark.gen.checks.band_techs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L50)

logic techniques of band cap or lower

### `def code_techs(P, code)` {#pencilmark.gen.checks.code_techs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L55)

engine techniques whose chip is `code` (shape-split techniques included, e.g. X-Wing for XWG).

### `class Checker` {#pencilmark.gen.checks.Checker}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L60)

solvable by logic with techniques in `allowed` (default: band &lt;= cap) -> unique by construction.

#### `def left(self, givens, els)` {#pencilmark.gen.checks.Checker.left}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L70)

cells the capped solve leaves unplaced (0 = solvable within the cap).

#### `def ok(self, givens, els)` {#pencilmark.gen.checks.Checker.ok}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L82)

True if the capped solve places every empty cell

### `class Oracle` {#pencilmark.gen.checks.Oracle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L87)

CP-SAT uniqueness with a cache of alternative solutions (single worker: deterministic, light on the machine).

#### `def unique(self, givens, els)` {#pencilmark.gen.checks.Oracle.unique}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L94)

True if CP-SAT proves the candidate (givens, els) has one solution; a cached alternative or a timeout is not unique

#### `def refuted(self, givens, els)` {#pencilmark.gen.checks.Oracle.refuted}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/checks.py#L116)

True if a cached alternative still satisfies the candidate (it cannot be unique).

## pencilmark.gen.search {#pencilmark.gen.search}

[src/pencilmark/gen/search.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/search.py)

Search procedures.

All functions take a Board, a random.Random and return (solution, givens {cell: digit}, elements) or None.

| Name | What it does |
|---|---|
| def [`dig`](#pencilmark.gen.search.dig) | givens-digging with elements added on demand. |
| def [`partition`](#pencilmark.gen.search.partition) | killer covering the board: keep `n_givens` random givens, tile the other cells with 2-cell informative… |
| def [`cage_count`](#pencilmark.gen.search.cage_count) | killer with EXACTLY n_cages cages and no givens: tile with 2-cell cages, then merge neighbouring cages… |
| def [`full_kropki`](#pencilmark.gen.search.full_kropki) | zero-given full kropki (every consecutive pair has a white dot, every 1:2 pair a black one, no dot =… |
| def [`min_kropki`](#pencilmark.gen.search.min_kropki) | zero-given kropki without the negative rule: all true dots, then remove dots while the puzzle stays unique… |
| def [`pull`](#pencilmark.gen.search.pull) | approach the band boundary from above: start from a puzzle the lower-band solve (`low`) can't finish (e.g. |

### `def dig(b, kinds, rng, chk, sol=None, min_givens=0, grid_floors=None, seeds=None, max_els=10 ** 6, symmetry=None, fixed=None, blocked=(), pool_tries=25, caps=None, dense=(), shape=None, most=(), deadline=None, keep=False)` {#pencilmark.gen.search.dig}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/search.py#L14)

givens-digging with elements added on demand.

1. `seeds` {kind: count} elements are placed first (apart from elements of their own kind), then the `most` classes are packed; their cells, then their peers, are emptied first, so they tend to end up required; 2. the remaining givens are removed in random order (whole symmetry orbits at a time) down to `min_givens`; when a removal breaks solvability (chk: band-capped logic), the most informative element of `kinds` through that cell that restores it is added (if any), else the givens stay; 3. prune: every element the puzzle stays solvable without is dropped (no decorative elements). fixed {cell: True (stays given) / False (stays empty)}; blocked cells take no elements. kinds / seeds may name element classes (kropki_black, x, odd, ...); caps {class: max} limits how many of a class are added. dense: 2-cell / 1-cell classes seeded with EVERY instance true in the solution before digging (few-givens targets); pruning then removes the ones the puzzle doesn't need. shape {kind: limits}: the templates' length / sum limits (elements.fits). most: classes packed into the grid after the seeds, as many disjoint ones as a few random packings find, and never pruned. grid_floors [(cells, n)]: no grid of a layout goes below n givens. deadline (time.time()): when it passes, the attempt is given up (None), or with keep the digging stops and the givens still in place stay.

### `def partition(b, rng, chk, n_givens=0, min_els=0, cover=True)` {#pencilmark.gen.search.partition}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/search.py#L207)

killer covering the board: keep `n_givens` random givens, tile the other cells with 2-cell informative cages, then merge neighbouring cages (distinct digits, &lt;= 6 cells) -- or delete cages if cover=False -- while the puzzle stays solvable within the checker's cap. A cell left alone becomes a given (a 1-cell cage is a given in disguise) when there are givens; with none it joins a neighbouring cage.

### `def cage_count(b, n_cages, rng, time_limit=30.0, deadline=None, log=None)` {#pencilmark.gen.search.cage_count}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/search.py#L279)

killer with EXACTLY n_cages cages and no givens: tile with 2-cell cages, then merge neighbouring cages (distinct digits) in batches while the puzzle stays UNIQUE (CP-SAT oracle with a counterexample cache; a failed batch is bisected). No human-solvability cap: the card grades whatever results.

### `def full_kropki(b, rng, time_limit=20.0)` {#pencilmark.gen.search.full_kropki}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/search.py#L370)

zero-given full kropki (every consecutive pair has a white dot, every 1:2 pair a black one, no dot = neither): the grid fixes the whole puzzle, so draw grids until the dot set is unique.

### `def min_kropki(b, rng, time_limit=20.0, chk=None)` {#pencilmark.gen.search.min_kropki}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/search.py#L380)

zero-given kropki without the negative rule: all true dots, then remove dots while the puzzle stays unique (CP-SAT oracle; with `chk`, while it stays solvable within the checker's cap) -> a minimal dot set.

### `def pull(b, sol, givens, els, chk, low, rng, symmetry=None, max_givens=None)` {#pencilmark.gen.search.pull}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/gen/search.py#L398)

approach the band boundary from above: start from a puzzle the lower-band solve (`low`) can't finish (e.g. dug with every technique allowed), then put givens back (random order, whole symmetry orbits), skipping any that would let `low` finish, until the capped solve (`chk`) finishes. The result needs the cap's techniques (by the engine) and solves within the cap. Elements that became unnecessary are dropped. Returns (givens, els) or None.
