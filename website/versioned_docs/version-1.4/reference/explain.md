---
title: "Explanations"
description: "The step explanations: one handler per technique, on a replayed grid."
toc_max_heading_level: 2
---

# Explanations

The step explanations: one handler per technique, on a replayed grid. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.explain {#pencilmark.explain}

[src/pencilmark/explain/__init__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/__init__.py)

Teachable explanations for grader moves.

from pencilmark import cbackend as CB, explain as E

```
steps, ok = CB.solve(p, P, solution=sol)
for i, step, state in E.replay(p, steps):        # state = grid BEFORE the step
    ex = E.explain(step, p, state)
    print(ex["short"]); print(ex["teach"])
```

explain(step, puzzle, state) -> dict

```
short       one line: "r4c7 = 3: the only place for a 3 in box 6"
teach       2-5 sentences: where to look, why it works, what it achieves
concept     {"family", "technique", "name", "lesson"} (reusable across puzzles)
visual      cells / units / lines / chain links to highlight in a UI
annotation  placeholders for human annotation
justification   the structured reason the text was rendered from (schema below)
derived     True when the justification was reconstructed here (not supplied by the engine)
verified    True when the reconstructed pattern reproduces the move's placement / eliminations
```

Justification schema (the same keys are read from the engine's step.move.explain dict when the engine exports one -- engine fields override derived ones, so richer data plugs straight in): technique, digits, placement (cell, digit), eliminations [(cell, digit)], base_units / cover_units [group index], base_cells / cover_cells / fins [cell], constraints [{"type", "index", "cells", "params"}], links [{"a": (c, d), "b": (c, d), "strong": bool, "source": "bivalue|bilocal|constraint|relation|cell|house", "unit": gi}], als [{"cells", "digits"}], rcc [digit], z digit, trial {"assume", "events", "contradiction"}.

The reconstruction works on the replayed grid (placed digits + candidates, the C++ engine's own candidate maintenance), so it needs nothing but the step stream.

## pencilmark.explain.base {#pencilmark.explain.base}

[src/pencilmark/explain/base.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py)

Shared vocabulary of the explainer: tables, naming (Namer), contexts (Ctx), result helpers. (split from explain.py)

| Name | What it does |
|---|---|
| class [`Namer`](#pencilmark.explain.base.Namer) | names cells, digits and groups in step text (r1c1, row 3, box 2, ...) |
| def [`rel_label`](#pencilmark.explain.base.rel_label) | Human name of the rule(s) linking cells a and b ('' if none). |
| class [`Ctx`](#pencilmark.explain.base.Ctx) | what the explainers need about one step: its move, technique, engine explanation, namer and phrasing key |
| def [`fmt_elims`](#pencilmark.explain.base.fmt_elims) | 'r4c1, r4c2 ≠ 3; r5c5 ≠ 1,2'. |

### `class Namer` {#pencilmark.explain.base.Namer}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L288)

names cells, digits and groups in step text (r1c1, row 3, box 2, ...)

#### `def cell(self, c)` {#pencilmark.explain.base.Namer.cell}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L304)

cell index -> r1c1 (1-based)

#### `def sort(self, cs)` {#pencilmark.explain.base.Namer.sort}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L309)

unique cells in board order

#### `def cells(self, cs, conj='and')` {#pencilmark.explain.base.Namer.cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L313)

cell names in board order, joined with conj

#### `def span(self, cs)` {#pencilmark.explain.base.Namer.span}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L317)

Ordered line cells: 'r1c1-r1c4' (first to last).

#### `def digits(ds, conj='or')` {#pencilmark.explain.base.Namer.digits}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L323)

unique digits sorted, joined with conj

#### `def cset(mask)` {#pencilmark.explain.base.Namer.cset}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L328)

candidate mask -> {1,2,3}

#### `def unit(self, gi, the=False)` {#pencilmark.explain.base.Namer.unit}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L332)

phrase naming group gi (row 3, box 2, the main diagonal, a cage, ...)

#### `def cage(self, gi, cells=True)` {#pencilmark.explain.base.Namer.cage}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L366)

phrase naming cage gi (the 12 cage), with its cells when cells is True

### `def rel_label(p, a, b)` {#pencilmark.explain.base.rel_label}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L416)

Human name of the rule(s) linking cells a and b ('' if none).

### `class Ctx` {#pencilmark.explain.base.Ctx}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L546)

what the explainers need about one step: its move, technique, engine explanation, namer and phrasing key

#### `def pick(self, options, salt='')` {#pencilmark.explain.base.Ctx.pick}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L563)

one of options, always the same for the same move and salt

#### `def gi(self, name)` {#pencilmark.explain.base.Ctx.gi}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L567)

index of the group called name, or None

### `def fmt_elims(nm, elims)` {#pencilmark.explain.base.fmt_elims}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/base.py#L576)

'r4c1, r4c2 ≠ 3; r5c5 ≠ 1,2'.

## pencilmark.explain.dispatch {#pencilmark.explain.dispatch}

[src/pencilmark/explain/dispatch.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/dispatch.py)

Handler table and registration, explain(), technique keys, self-checks. (split from explain.py)

| Name | What it does |
|---|---|
| def [`explain`](#pencilmark.explain.dispatch.explain) | Explanation dict for one solver step (state = grid before the step; see replay()). |
| def [`explain_all`](#pencilmark.explain.dispatch.explain_all) |  |
| def [`check`](#pencilmark.explain.dispatch.check) | Factual consistency of an explanation with the move and the grid. |

### `def explain(step, puzzle, state)` {#pencilmark.explain.dispatch.explain}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/dispatch.py#L771)

Explanation dict for one solver step (state = grid before the step; see replay()).

### `def explain_all(puzzle, steps)` {#pencilmark.explain.dispatch.explain_all}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/dispatch.py#L842)

*No docstring.*

### `def check(ex, step, puzzle, state)` {#pencilmark.explain.dispatch.check}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/dispatch.py#L968)

Factual consistency of an explanation with the move and the grid. -> (ok, problems).

## pencilmark.explain.grid {#pencilmark.explain.grid}

[src/pencilmark/explain/grid.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py)

The replayed grid: implied houses, derived candidates, State / replay, rules, the no-notes view. (split from explain.py)

| Name | What it does |
|---|---|
| def [`implied_houses`](#pencilmark.explain.grid.implied_houses) | Derived houses exactly as the engine builds them (csolver model.cpp build_implied): unions of k = 2..4… |
| def [`derived`](#pencilmark.explain.grid.derived) | The puzzle the engine actually solves: p plus its implied houses (same group indices, the implied ones… |
| class [`State`](#pencilmark.explain.grid.State) | Grid before a step: placed digits, candidates (the engine's own maintenance: peers + pair relations on every… |
| def [`replay`](#pencilmark.explain.grid.replay) | Yield (index, step, state BEFORE the step); the state object is copied per step. |
| class [`Rule`](#pencilmark.explain.grid.Rule) | One multi-cell rule (cage, line, arrow, sum clue ...) as a checkable predicate. |
| def [`rules`](#pencilmark.explain.grid.rules) | Every multi-cell rule of the puzzle, keyed like the engine: ('con', index into p.constraints then detected… |
| def [`enum_rule`](#pencilmark.explain.grid.enum_rule) | All assignments of rule.cells within masks `dom` that satisfy the rule, the pair relations and distinctness… |
| def [`direct_sources`](#pencilmark.explain.grid.direct_sources) | Why each digit is excluded at empty cell c from placed digits alone. |
| def [`direct_excl`](#pencilmark.explain.grid.direct_excl) | mask of the digits excluded at cell c by the placed digits alone |
| def [`direct_locks`](#pencilmark.explain.grid.direct_locks) | Pointing / claiming done in the head (no notes): digit v's directly-possible cells in house B all lie in… |
| def [`mental_view`](#pencilmark.explain.grid.mental_view) | Direct-mode reasoning without notes: placed-digit exclusions, then relation arcs and whole-rule consistency… |

### `def implied_houses(p)` {#pencilmark.explain.grid.implied_houses}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L13)

Derived houses exactly as the engine builds them (csolver model.cpp build_implied): unions of k = 2..4 parallel lines minus k-1 disjoint complete houses inside them that leave D cells. -> list of (cells, lines, removed group indices or 'implied#').

### `def derived(p)` {#pencilmark.explain.grid.derived}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L51)

The puzzle the engine actually solves: p plus its implied houses (same group indices, the implied ones appended as 'implied1', 'implied2', ...).

### `class State` {#pencilmark.explain.grid.State}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L83)

Grid before a step: placed digits, candidates (the engine's own maintenance: peers + pair relations on every placement, eliminations applied), solving mode, and which step last removed each candidate (for 'it lost its last alternative to ...' remarks).

#### `def initial(cls, p)` {#pencilmark.explain.grid.State.initial}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L97)

State of puzzle p with its givens placed

#### `def copy(self)` {#pencilmark.explain.grid.State.copy}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L105)

independent copy of this state

#### `def placed_g(self, gi)` {#pencilmark.explain.grid.State.placed_g}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L112)

mask of the digits placed in group gi

#### `def place(self, c, v, tag=None)` {#pencilmark.explain.grid.State.place}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L120)

put digit v in cell c and remove its candidates from the peers and related cells (tag is kept in lost)

#### `def apply(self, step)` {#pencilmark.explain.grid.State.apply}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L139)

apply a step's placement and eliminations (recorded in lost), update the mode, advance idx

### `def replay(p, steps, state=None)` {#pencilmark.explain.grid.replay}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L156)

Yield (index, step, state BEFORE the step); the state object is copied per step.

### `class Rule` {#pencilmark.explain.grid.Rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L179)

One multi-cell rule (cage, line, arrow, sum clue ...) as a checkable predicate.

#### `def check(self, a)` {#pencilmark.explain.grid.Rule.check}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L198)

True if the digits a, one per cell of the rule, satisfy it

#### `def partial(self, a, i, dom)` {#pencilmark.explain.grid.Rule.partial}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L252)

Prune a prefix a[0..i].

### `def rules(p)` {#pencilmark.explain.grid.rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L317)

Every multi-cell rule of the puzzle, keyed like the engine: ('con', index into p.constraints then detected lines), ('cage', group index).

### `def enum_rule(p, rule, dom, node_limit=150000, keep=400, max_count=None, support=True)` {#pencilmark.explain.grid.enum_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L379)

All assignments of rule.cells within masks `dom` that satisfy the rule, the pair relations and distinctness inside the scope. -> dict(sup, count, sols, complete). max_count: stop as soon as more fillings exist (-> complete False, count None); support=False: no witness search when the enumeration is incomplete (the direct-mode reading mirrors the engine's cap and skips such rules).

### `def direct_sources(p, st, c, digit=None)` {#pencilmark.explain.grid.direct_sources}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L568)

Why each digit is excluded at empty cell c from placed digits alone. -> list of (kind, mask, info). kinds: 'house' (gi, {digit: cell}), 'neq' (cell, digit), 'rel' (cell, digit), 'domain', 'cagesum' (gi).

### `def direct_excl(p, st, c)` {#pencilmark.explain.grid.direct_excl}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L620)

mask of the digits excluded at cell c by the placed digits alone

### `def direct_locks(p, st)` {#pencilmark.explain.grid.direct_locks}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L662)

Pointing / claiming done in the head (no notes): digit v's directly-possible cells in house B all lie in group A -> v excluded from A minus B. -> list of dicts.

### `def mental_view(p, st, level=3)` {#pencilmark.explain.grid.mental_view}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/grid.py#L721)

Direct-mode reasoning without notes: placed-digit exclusions, then relation arcs and whole-rule consistency (two rounds), mental pairs/triples and pointing, one more round. -> (md masks, reasons {(cell, digit): reason}).

## pencilmark.explain.catalog {#pencilmark.explain.catalog}

[src/pencilmark/explain/catalog.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/catalog.py)

The technique catalog: names, aliases and explainer links per technique; shapes; lessons. (split from explain.py)

| Name | What it does |
|---|---|
| def [`candidate_urls`](#pencilmark.explain.catalog.candidate_urls) |  |
| def [`technique_info`](#pencilmark.explain.catalog.technique_info) |  |
| def [`chain_shape`](#pencilmark.explain.catalog.chain_shape) | Name the shape of a chain: Skyscraper, 2-String Kite, Turbot Fish, Remote Pair, W-Wing, X-Chain / XY-Chain /… |
| def [`fish_shape`](#pencilmark.explain.catalog.fish_shape) |  |

### `def candidate_urls()` {#pencilmark.explain.catalog.candidate_urls}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/catalog.py#L654)

*No docstring.*

### `def technique_info(key)` {#pencilmark.explain.catalog.technique_info}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/catalog.py#L658)

*No docstring.*

### `def chain_shape(p, st, path, place=False)` {#pencilmark.explain.catalog.chain_shape}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/catalog.py#L681)

Name the shape of a chain: Skyscraper, 2-String Kite, Turbot Fish, Remote Pair, W-Wing, X-Chain / XY-Chain / AIC. -> catalog key.

### `def fish_shape(p, base, cover, fins, U)` {#pencilmark.explain.catalog.fish_shape}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/catalog.py#L733)

*No docstring.*

## pencilmark.explain.singles {#pencilmark.explain.singles}

[src/pencilmark/explain/singles.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/singles.py)

Explanations of singles, the no-notes layer and n-ary rule steps. (split from explain.py)

| Name | What it does |
|---|---|
| def [`rule_for_move`](#pencilmark.explain.singles.rule_for_move) | the rule that explains a move when the move does not name it (F1, 2026-11-08: two thirds of the generic… |

### `def rule_for_move(ctx)` {#pencilmark.explain.singles.rule_for_move}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/singles.py#L512)

the rule that explains a move when the move does not name it (F1, 2026-11-08: two thirds of the generic explanations): the smallest rule holding every cell the move touches whose digits, with the candidates as they stand, leave the placed digit alone in its cell or none of the eliminated ones

## pencilmark.explain.combos {#pencilmark.explain.combos}

[src/pencilmark/explain/combos.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/combos.py)

Innies / outies, combinations, lines, combination locks and leftovers. (split from explain.py)

## pencilmark.explain.notes {#pencilmark.explain.notes}

[src/pencilmark/explain/notes.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/notes.py)

Pencil-mark techniques: locked candidates, subsets, fish, wings, coloring; uniqueness. (split from explain.py)

## pencilmark.explain.chains {#pencilmark.explain.chains}

[src/pencilmark/explain/chains.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/chains.py)

Chains, almost locked sets, death blossom, chains in the head. (split from explain.py)

## pencilmark.explain.trial {#pencilmark.explain.trial}

[src/pencilmark/explain/trial.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/trial.py)

Trial, forcing and case splits; the remaining variant handlers. (split from explain.py)

## pencilmark.explain.records {#pencilmark.explain.records}

[src/pencilmark/explain/records.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/records.py)

Techniques that explain from the engine's records (68-82 and later), empty rectangles. (split from explain.py)

## pencilmark.explain.facts {#pencilmark.explain.facts}

[src/pencilmark/explain/facts.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/facts.py)

Rule facts: the one-sentence reasons solvers give for a rule, used as the `why` of explanation sub-steps. Chosen from the facts Cracking the Cryptic hosts repeat most (docs/research/rule_facts_library.md in the research notes; each in at least 5 solve videos), in our own words.

| Name | What it does |
|---|---|
| def [`derived`](#pencilmark.explain.facts.derived) | consequences of a rule for this digit range, worked out by enumeration rather than written for 9x9: digits a… |
| def [`rule_fact`](#pencilmark.explain.facts.rule_fact) | the rule's fact for this puzzle: the base sentence, then what follows for its digit range (derived) |

### `def derived(kind, D, n=None, k=None)` {#pencilmark.explain.facts.derived}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/facts.py#L32)

consequences of a rule for this digit range, worked out by enumeration rather than written for 9x9: digits a whisper can never hold and whether its neighbors alternate low / high, an arrow's shaft and circle bounds, a thermometer's bulb and tip, the digits a long renban must hold -> sentence or ""

### `def rule_fact(kind, D, rule=None)` {#pencilmark.explain.facts.rule_fact}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/facts.py#L69)

the rule's fact for this puzzle: the base sentence, then what follows for its digit range (derived)

## pencilmark.explain.clue_facts {#pencilmark.explain.clue_facts}

[src/pencilmark/explain/clue_facts.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/clue_facts.py)

Clue facts: the little facts a solver learns for each common rule before solving with it ("a 5 is never on a German whisper", "a 5-cell renban always holds a 5"). Hand-written from the facts Cracking the Cryptic hosts repeat most (docs/research/rule_facts_library.md in the research notes; the video count is how many solve videos state the fact), in our own words. Each fact carries a probe: the rule alone on an empty 9x9 grid (sometimes with a given) and the eliminations the fact makes there. tools/gen_clue_facts_md.py checks every probe by brute force (the eliminations are true) and runs the engine on it (which step makes them), and writes [clue-facts](../grades/clue-facts.md).

`out(n, i, D, args)`: the digits the fact rules out of position i (0-based) of a line of n cells (2 for a dot), args = the relation's parameters; the ClueFacts explanation names the facts whose `out` covers its eliminations. Rules over more than two cells are applied by their own techniques (cage and arrow combinations, line ranges); the page says which.

| Name | What it does |
|---|---|
| class [`ClueFact`](#pencilmark.explain.clue_facts.ClueFact) |  |
| def [`covering`](#pencilmark.explain.clue_facts.covering) | the facts that explain a ClueFacts move: for each elimination (cell, digit), a fact of a pair rule on the… |
| def [`rule_kinds`](#pencilmark.explain.clue_facts.rule_kinds) | the rules on these cells that have a one-sentence statement (explain.facts.RULE_FACTS), in a fixed order:… |

### `class ClueFact` {#pencilmark.explain.clue_facts.ClueFact}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/clue_facts.py#L16)

*No docstring.*

### `def covering(p, elims)` {#pencilmark.explain.clue_facts.covering}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/clue_facts.py#L399)

the facts that explain a ClueFacts move: for each elimination (cell, digit), a fact of a pair rule on the cell whose `out` holds the digit -> (facts in catalog order, eliminations no fact covers). The texts are worded for digits 1-9: other sizes get no facts.

### `def rule_kinds(p, cells)` {#pencilmark.explain.clue_facts.rule_kinds}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/explain/clue_facts.py#L430)

the rules on these cells that have a one-sentence statement (explain.facts.RULE_FACTS), in a fixed order: the rule a ClueFacts step over more cells reads
