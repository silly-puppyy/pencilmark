# pencilmark puzzle format: `sudoku-puzzle`, format_version 1

Specification of the exchange format of pencilmark. The JSON Schema is `docs/sudoku-puzzle.schema.json`.

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119.

Contents

1. [Overview](#1-overview)
2. [Envelope](#2-envelope)
3. [Cells, outside clues and ordering](#3-cells-outside-clues-and-ordering)
4. [Strict reading (must-understand)](#4-strict-reading-must-understand)
5. [Rules: common shape and pair operators](#5-rules-common-shape-and-pair-operators)
6. [Rule families](#6-rule-families)
7. [Default drawing](#7-default-drawing)
8. [Cosmetic layers: style and decorations](#8-cosmetic-layers-style-and-decorations)
9. [Canonical form, fingerprint, compression](#9-canonical-form-fingerprint-compression)
10. [Examples](#10-examples)
11. [Grade card: `sudoku-grade`](#11-grade-card-sudoku-grade)
12. [Generator spec: `sudoku-spec`](#12-generator-spec-sudoku-spec)
13. [describe(): variant name and rules](#13-describe-variant-name-and-rules)

---

## 1. Overview

A `sudoku-puzzle` file describes one puzzle completely: the board, the givens, and every rule, houses included.
It is written so that:

- a **renderer** can draw the puzzle from the rules alone, using the default drawing of each rule (section 7);
- a **solver or grader** can rely on every rule having one exact meaning (section 6), with no defaults that depend on
  the board size;
- a reader that meets something it does not understand **refuses** the file instead of silently dropping a rule
  (section 4);
- every puzzle has **one canonical representation** (section 9).

The file is JSON (RFC 8259), UTF-8, conventionally named `*.json` or `*.sudoku.json`, media type `application/json`.
A file is recognised by its `"format"` member, not by its name.
Several puzzles go in a JSON Lines file (`*.jsonl`): one compact `sudoku-puzzle` object per line.

Companion formats sharing the vocabulary:

- `"format": "sudoku-grade"`: a grade card (section 11).
- `"format": "sudoku-spec"`: a request to the generator (section 12).

Python API (package `pencilmark`):

| Function | Purpose |
|---|---|
| `to_export(puzzle, meta=None, **meta_kw)` | any accepted input → `sudoku-puzzle` dict (canonical) |
| `load(puzzle)` | any accepted input (this format, a classic string, a file path) → engine `Puzzle` |
| `dumps(doc, pretty=True)` | canonical JSON text (section 9.1) |
| `fingerprint(puzzle)` | `"sha256:…"` content fingerprint (section 9.2) |
| `validate(doc)` | strict reading checks (section 4); raises `FormatError` |
| `describe(puzzle)` / `rules_text(d)` | `{"type", "rules"}` and its text form (section 13) |
| `spec_from_gen(spec)` / `spec_to_gen(doc)` | `sudoku-spec` ↔ generator spec dict (section 12) |

## 2. Envelope

```json
{"format": "sudoku-puzzle",
 "format_version": 1,
 "$schema": "https://silly-puppyy.github.io/pencilmark/schema/sudoku-puzzle-1.json",
 "meta": {"title": "…", "author": "…"},
 "board": {"rows": 9, "cols": 9},
 "digits": 9,
 "givens": [ …R*C entries… ],
 "solution": [ …R*C entries… ],
 "candidates": {"r1c1": [1, 3, 7]},
 "rules": [ … ],
 "decorations": [ … ],
 "style": { … },
 "ext": {"com.example": { … }}}
```

| Key | Required | Meaning |
|---|---|---|
| `format` | yes | Always `"sudoku-puzzle"`. |
| `format_version` | yes | Integer, `1`. Bumped only on a breaking change. A reader MUST refuse a file whose `format_version` is higher than it supports. |
| `$schema` | no | URL of the JSON Schema. Ignored by readers. |
| `meta` | no | Information *about* the puzzle (2.1). Never changes how it is solved or graded. |
| `board` | yes | `{"rows": R, "cols": C}`: the bounding rectangle of the board. No other keys. |
| `digits` | yes | Integer D ≥ 1: cells hold the digits 1..D. (Other digit sets and display symbols are reserved for a later version; see 6.17.) |
| `givens` | yes | Flat list of R×C entries in reading order (row by row). `0` = empty cell, `null` = no cell at that position (the gaps of multi-grid boards), otherwise the given digit as a number (so 10..D work). This is the **only** representation: no text rows, no digit strings, no per-cell objects. |
| `solution` | no | Same shape as `givens`, every existing cell filled, `null` exactly where `givens` has `null`. |
| `candidates` | no | Given pencil marks (Sukaku): `{"r1c1": [1, 3, 7], …}`, ascending integer lists. **Semantic**: each listed cell's digit is one of its list; unlisted cells are unrestricted. Graphical cell clues (odd, even, …) are `cell` rules, never candidates. |
| `rules` | yes | Every constraint, houses included (section 6). Nothing is implied: a board without house rules has no houses. |
| `decorations` | no | Cosmetic drawing primitives (section 8). Never semantic. |
| `style` | no | Cosmetic, puzzle-wide drawing hints (section 8). Never semantic. |
| `ext` | no | Vendor data, keyed by reverse-DNS namespace (`"com.example"`). Never semantic. |

There is no uniqueness flag: whether a puzzle has one solution is a property a tool checks, not a field.

### 2.1 meta

Every key is optional and free-form, and tools keep keys they do not know. Text is plain (no HTML, no language
maps). Common keys:

| Key | Meaning |
|---|---|
| `title` | Title. |
| `author` | Setter's name. |
| `source` | The website's domain, e.g. `"logic-masters.de"`. |
| `id` | That site's own id. |
| `url` | Link to the puzzle. |
| `date` | ISO 8601 date. |
| `rules_text` | The setter's own wording of the rules. Tools never overwrite it. |
| `type` | Display name of the variant, e.g. `"Killer Sudoku"`. Variant names live **only** here; they never change the rules. `describe()` (section 13) fills it when it is empty. |
| `license` | Licence of the puzzle. |
| `tags` | List of strings. |
| `generated_from` | Fingerprint of the `sudoku-spec` that produced the puzzle (section 12). |

## 3. Cells, outside clues and ordering

### 3.1 Cell names

A cell is named `"r{row}c{col}"`, 1-based on the board, lowercase, no leading zeros: `"r1c1"` is the top-left
position, `"r9c9"` the bottom-right of a classic, `"r21c21"` the bottom-right of a samurai. A cell name anywhere in a
rule or in `candidates` MUST refer to an existing cell, one whose `givens` entry is not `null`. There are no virtual
or outside cell names, and names are always lowercase.

**Reading order** is by row, then by column: `r1c1 < r1c2 < … < r1c9 < r2c1`.

### 3.2 Outside clues: `side`

A clue drawn outside the grid (sandwich, x-sum, skyscraper, frame, little killer, rossini, …) has
`"side": "top" | "bottom" | "left" | "right"` and ordered `cells` that start at the cell next to the clue.
**The clue attaches to `cells[0]`, on `side`.** Where exactly it is drawn (spacing, a gap that is too narrow, two
clues competing for one gap) is the renderer's business; the semantics never depend on it.

- Row and column clues: the cells run straight away from the side (`top`: down the column, `left`: along the row to
  the right, and so on).
- Diagonal clues (little killer, diagonal distinct count): the cells run diagonally away from the side; the
  direction is `cells[0] → cells[1]`. `side` says which edge of `cells[0]` the clue is drawn against (top or left of
  `r1c1`). A 1-cell diagonal clue points straight at its cell.
- The position next to `cells[0]` on `side` MUST NOT be an existing cell: it is beyond the board or a gap
  (`null`).
- Multi-grid boards: `cells[0]` need not be on the board's edge. A clue on the left of board row 10 of a
  samurai (the 4th row of the centre grid) is `"side": "left"` with `cells[0] = "r10c7"`; it attaches to the gap at
  r10c6.

### 3.3 Ordered lists and sets

| Ordered (the order carries meaning) | Sets (readers ignore the order; writers SHOULD use reading order) |
|---|---|
| `line` cells (thermo bulb first; a whisper's order is its path) | `box`, `row`, `column`, `region`, `cage` cells; `sum` kinds `group` / `corner` |
| `arrow` `bulb` (a pill reads as a number in `bulb` order) and each shaft in `lines` (away from the bulb) | `cell`, `contains`, `appears` cells, `count`, `distinct_count` without `side` |
| outside clues (`sandwich`, `xsum`, `skyscraper`, `rossini`, `first_seen`, `sum` kinds `little_killer` / `frame`, `distinct_count` with `side`): from the cell next to the clue outwards | `equal_sum` segments (each a set; the segment list is unordered) |
| `clone` / `isomorphic` regions: corresponding positions | `edge` pairs except `less`, `relation` pairs of symmetric operators |
| `edge` kind `less` and `relation` pairs of `less` / `less_equal` / `allowed` / `any_of`: `[a, b]` in operator order | `corner` cells (written TL, TR, BL, BR = reading order) |
| `vudoku` cells (vertex first), `table` cells (columns of `allowed`), `box` / `row` / `column` `cells` | `area` cell lists, `except` pairs |

The order of the `rules` array carries **no meaning**. Writers SHOULD keep the order they were given (the
fingerprint sorts, section 9.2).

### 3.4 Geometry derived from cells

Edge and corner positions are never named directly. They follow from the cells:

- **Edge clue**: exactly 2 orthogonally adjacent cells. The clue sits at the midpoint of the shared side.
- **Corner clue**: exactly 4 cells forming a 2×2 block, written TL, TR, BL, BR. The clue sits at the shared corner.
- **Outside clue**: `side` plus ordered `cells` along a straight line (row, column or diagonal), contiguous (3.2).
- **Line**: centre-to-centre segments between consecutive cells; consecutive cells MUST touch (side or corner). A
  segment between diagonal neighbours passes straight through their shared corner.

## 4. Strict reading (must-understand)

A reader MUST refuse a file, raising an error that names the offending key or rule and its position, when any of
these holds:

1. `format` is not `"sudoku-puzzle"`, or `format_version` is missing, not an integer, or higher than supported.
2. A key it does not know appears **anywhere**: at the top level, in `board`, or inside a rule. The only exceptions are
   these containers, which are always safe to ignore: `meta`, `style` (top level and per rule), `decorations`,
   `ext`, and a rule's `id` and `label`.
3. A rule `type` it does not know, or a `kind` it does not know for a known type.
4. A vendor rule type (`"com.example:foo"`: reverse-DNS namespace, colon, name) it does not implement. Core type names
   never contain a colon.
5. `"type": "custom"` (reserved, 6.17).
6. A structural check fails: `len(givens) != R*C`; `solution` or `candidates` disagree in shape; a cell name refers to
   a missing cell; an edge pair is not orthogonally adjacent; a corner set is not a 2×2 block; an outside clue's
   cells are not collinear and contiguous, or the position next to `cells[0]` on `side` is a cell; an arrow shaft
   does not start next to a bulb cell; a digit lies outside 1..D; a required parameter is missing (e.g. `whisper`
   without `value` when D ≠ 9); a `grid` / `box_grid` area is not fully made of existing cells; a `box_grid`'s
   `box` does not hold D cells.

pencilmark raises `FormatError` (a `ValueError`) for these. A file can also be valid and still use something the
pencilmark engine cannot build (e.g. a modular line with modulus 4); then it raises `NotSupportedError` (also a
`ValueError`) naming the rule and the reason, never a partial puzzle.

A program that only *draws* MAY draw what it understands and show a warning, but MUST NOT present the puzzle as
complete. Ignorable containers never carry rules: no constraint may be derived from `meta`, `style`, `decorations`
or `ext`.

## 5. Rules: common shape and pair operators

Every rule is an object with a `type` (the mechanic family); many families also have a `kind` (a flavour with its own
semantics and drawing). Every rule MAY carry:

| Key | Meaning |
|---|---|
| `id` | String. Ignorable. |
| `label` | Short plain text. Ignorable. Optional everywhere; for `table` and vendor rules it is what a renderer shows. |
| `style` | Cosmetic override of the default drawing (section 8). Ignorable. |

**Areas.** A rule that applies to part of the board says where with `area`: the `origin` of a `grid` / `box_grid` rule
in the file (that grid's D × D cells), or a list of cells. The same key means the same thing everywhere it appears
(`neighbours`, `negative`, and the generator spec, section 12).

Number keys: **`sum`** when the clue is a sum of digits (cage, every `sum` kind, sandwich, x-sum, edge kind `sum`),
**`value`** for every other number (difference, ratio, product, whisper gap, skyscraper count, …). Parameters with a
stated default are omitted by canonical writers when they equal the default.

### 5.1 Pair operators

`relation`, `neighbours` and `negative` use these operator names. `params` is a list (empty for parameterless ops).

| `op` | `params` | The pair `[a, b]` satisfies it when |
|---|---|---|
| `different` | [] | a ≠ b |
| `equal` | [] | a = b |
| `less` | [] | a < b |
| `less_equal` | [] | a ≤ b |
| `difference` | [k] | \|a − b\| = k |
| `not_difference` | [k] | \|a − b\| ≠ k |
| `not_consecutive` | [] | \|a − b\| ≠ 1 |
| `difference_at_least` | [k] | \|a − b\| ≥ k |
| `difference_at_most` | [k] | \|a − b\| ≤ k |
| `ratio` | [k] | a = k·b or b = k·a |
| `not_ratio` | [k] | neither |
| `sum` | [s] | a + b = s |
| `not_sum` | [s] | a + b ≠ s |
| `parity_differs` | [] | one is odd, the other even |
| `same_third` / `different_third` | [] | a and b are / are not in the same third of 1..9 (entropic) |
| `same_mod3` / `different_mod3` | [] | a ≡ b / a ≢ b (mod 3) |
| `allowed` | [[[v, w], …]] | `[a, b]` is one of the listed digit pairs (escape hatch; also how a product clue is built) |
| `any_of` | [[op, params], …] | at least one of the listed operators holds |

`less`, `less_equal`, `allowed` and `any_of` are directional (pair order matters); the others are symmetric.

## 6. Rule families

"Repeats" says whether digits may repeat among a rule's cells **because of that rule**; houses still apply.

### 6.1 Houses: `grid`, `box_grid`, `box`, `row`, `column`

```json
{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}
{"type": "grid", "origin": "r1c1"}
{"type": "box", "cells": ["r1c1", "r1c2", "r1c3", "r2c1", "r2c2", "r2c3", "r3c1", "r3c2", "r4c1"]}
{"type": "row", "cells": ["r1c1", "r1c2", "…"]}
```

A house holds no repeated digit; a house of exactly D cells holds every digit once. Houses come only from these rules:
nothing is implied, so a board without house rules has no houses.

- **`grid`**: a sudoku grid, the D × D area whose top-left cell is `origin`. It gives the area's D rows (top to bottom)
  and D columns (left to right). Every cell of the area MUST exist.
- **`box_grid`**: a `grid` whose boxes are a regular tiling. `box` = [box height, box width], with box height × box
  width = D (a 6×6 is `box` [2, 3] or [3, 2]). It gives the grid's rows, columns, then its D boxes (reading order of
  their top-left cells). A classic is one `box_grid`; a samurai is five; a super samurai is one per grid.
- **`box`**: one box with explicit `cells`, any shape. A jigsaw is a `grid` plus one `box` per piece.
- **`row`** / **`column`**: explicit houses for rows and columns that are not those of a D × D area (staircase,
  toroidal, sujiken).
- A house with the same cell set as an earlier house is the same house (overlapping grids share boxes and lines).
- Boxes, from any of these rules, are what a renderer draws with thick lines. The `grid` / `box_grid` areas also limit
  negative constraints and battenburg windows to one grid (6.14).

| Board | Houses |
|---|---|
| classic, 6×6, 16×16 | one `box_grid` |
| jigsaw | one `grid` + D `box` rules |
| Latin square | one `grid` |
| samurai, twodoku, butterfly, … | one `box_grid` per grid |
| samurai with a jigsaw corner | four `box_grid` + one `grid` + D `box` rules |
| toroidal, staircase | `row` / `column` / `box` rules |

Canonical writers emit a `box_grid` for every D × D area whose rows, columns and regular boxes are houses, a `grid`
where the area's boxes are irregular or absent, and `box` / `row` / `column` rules for the remaining houses.

### 6.2 `region`

```json
{"type": "region", "kind": "diagonal", "cells": ["r1c1", "r2c2", "r3c3", "r4c4", "r5c5", "r6c6", "r7c7", "r8c8", "r9c9"]}
```

- No digit repeats among the cells. Fewer than D cells is allowed; "contains every digit" follows only when the region
  has exactly D cells.
- `kind`: `diagonal` | `window` | `disjoint` | `colour` | `extra` | `region`. To a solver all kinds mean the same; the
  kind is a drawing and grouping hint: `diagonal` (a straight diagonal: X-sudoku, argyle lines; cells listed from
  the top), `window` (windoku windows), `disjoint` (same position in every box), `colour` (colour groups), `extra`
  (shaded extra regions: asterisk, centre dot, …), `region` (anything else).

### 6.3 `cage`

```json
{"type": "cage", "sum": 15, "cells": ["r1c1", "r1c2", "r2c1"]}
```

- Digits in a cage never repeat. `sum` is optional (a cage without a sum is a no-repeat set with a cage outline).
- A sum over cells where repeats are allowed is a `sum` rule (6.8), not a cage.

### 6.4 `line`

```json
{"type": "line", "kind": "thermo", "cells": ["r5c3", "r4c3", "r3c3", "r3c4"]}
{"type": "line", "kind": "whisper", "value": 5, "cells": ["r7c7", "r7c8", "r8c8"]}
{"type": "line", "kind": "renban", "closed": true, "cells": ["r2c2", "r2c3", "r3c3", "r3c2"]}
```

Common fields: `cells` (ordered, at least 2) and `closed` (default `false`): a loop, the last cell connects back to the
first. `closed` is allowed only for `whisper`, `renban` and `parity`.

| `kind` | Parameters | Meaning |
|---|---|---|
| `thermo` | – | Strictly increasing from `cells[0]` (the bulb). Branching thermos are separate rules sharing `cells[0]`. |
| `slow_thermo` | – | Non-decreasing from `cells[0]`. |
| `whisper` | `value` k: REQUIRED when D ≠ 9; default 5 | Adjacent cells on the line differ by at least k (German whisper = 5, Dutch = 4). |
| `renban` | – | The cells hold a set of consecutive digits, no repeats, any order. |
| `region_sum` | – | Split the line into segments wherever it passes from one box to another; every segment has the same sum. |
| `palindrome` | – | Reads the same from both ends. |
| `entropic` | `groups`: REQUIRED when D ≠ 9; default `[[1,2,3],[4,5,6],[7,8,9]]` | Every run of 3 consecutive cells holds one digit from each group. |
| `modular` | `value` m: REQUIRED when D ≠ 9; default 3 | Every run of m consecutive cells holds one digit of each residue class mod m. |
| `parity` | – | Adjacent cells on the line differ in parity (alternate odd / even). |
| `zipper` | – | Cells equally far from the centre of the line sum to the same total (the centre digit, for an odd length). |
| `between` | – | Digits strictly between those of the two ends `cells[0]` and `cells[-1]`, ends in either order. |
| `lockout` | `value` k: REQUIRED when D ≠ 9; default 4 | The ends differ by at least k; every other digit lies outside the closed range of the ends. |
| `double_arrow` | – | The two ends sum to the total of the cells between them. |

Repeats: allowed on every line (subject to houses), except `renban`.

### 6.5 `arrow`

```json
{"type": "arrow", "bulb": ["r2c2"], "lines": [["r3c3", "r4c4", "r5c5"]]}
{"type": "arrow", "bulb": ["r1c1", "r1c2"], "lines": [["r2c3", "r3c3"], ["r2c1", "r3c1", "r4c1"]]}
```

- `bulb`: 1 or more orthogonally connected cells, read as one number in `bulb` order (a pill `[a, b]` is 10·a + b).
- `lines`: 1 or more shafts, each ordered away from the bulb; the first cell of each shaft touches a bulb cell.
- Each shaft's digits sum to the bulb number. Repeats allowed.

### 6.6 `edge`

Exactly 2 orthogonally adjacent cells.

| `kind` | Fields | Meaning |
|---|---|---|
| `kropki` | `color`: `"white"` \| `"black"` | White: \|a − b\| = 1. Black: one digit is double the other. A 1–2 pair may carry either colour. |
| `xv` | `letter`: `"X"` \| `"V"` | X: a + b = 10. V: a + b = 5. |
| `difference` | `value` k | \|a − b\| = k. |
| `sum` | `sum` s | a + b = s. |
| `product` | `value` p | a · b = p. |
| `ratio` | `value` k | one digit is k times the other. |
| `less` | – | `cells[0] < cells[1]`; the order matters. |

`kropki` white and `difference` 1 mean the same to a solver but draw differently; both exist on purpose (likewise
black / `ratio` 2 and X, V / `sum` 10, 5). Canonical writers that cannot tell them apart write `kropki` and `xv`.

### 6.7 `corner`

Exactly 4 cells forming a 2×2 block, written TL, TR, BL, BR.

| `kind` | Fields | Meaning |
|---|---|---|
| `battenburg` | – | The 4 cells form a parity checkerboard: TL and BR share a parity, TR and BL the other. |
| `mathrax` | `op`: `"+"`, `"-"`, `"x"`, `"/"` with `value`; or `op`: `"even"` / `"odd"` | `+ - x /`: each diagonal pair (TL–BR and TR–BL) combines to `value` (difference and quotient are larger over smaller). `even` / `odd`: all four digits have that parity. |
| `exclude` | `value` | None of the 4 cells holds `value`. |

Digits that must appear around a corner (a quadruple) are a `contains` rule on the 4 cells (6.13); it is drawn as a
corner circle.

### 6.8 `sum`

| `kind` | Fields | Meaning |
|---|---|---|
| `little_killer` | `side`, `cells` (the diagonal, ordered from the clue), `sum` | The cells sum to `sum`. Repeats allowed. The diagonal is exactly the listed cells. |
| `frame` | `side`, `cells` (ordered from the clue), `sum` | The cells (usually the first 3 of a row or column) sum to `sum`. |
| `group` | `cells`, `sum` | Any cell set sums to `sum`; repeats allowed. |
| `corner` | `cells` (a 2×2 block), `sum` | The 4 cells around a corner sum to `sum`; repeats allowed. |

### 6.9 Outside clues: `sandwich`, `xsum`, `skyscraper`, `rossini`, `first_seen`

All take `side` and ordered `cells` starting next to the clue (3.2).

| `type` | Fields | Meaning |
|---|---|---|
| `sandwich` | `sum` | The digits strictly between the 1 and the D in `cells` sum to `sum` (0 when they are adjacent). |
| `xsum` | `sum` | X = the digit in `cells[0]`; the first X cells sum to `sum`. |
| `skyscraper` | `value` | Reading `cells` in order, exactly `value` cells are higher than every earlier cell. |
| `rossini` | `arrow`: `"in"` \| `"out"` | The first 3 cells are monotone: increasing inwards for `in` (the arrow points into the grid, towards the highest digit), decreasing inwards for `out`. `cells` lists those 3 cells. |
| `first_seen` | `value`, `digits` (list) | Reading `cells` in order, the first digit that is in `digits` is `value` (e.g. the "123" clue). |

"Every arrow is shown" for rossini is a `negative` rule (6.14).

### 6.10 `neighbours`

A rule over neighbouring pairs of the whole board.

```json
{"type": "neighbours", "kind": "antiknight"}
{"type": "neighbours", "kind": "antiknight", "within": "box"}
{"type": "neighbours", "kind": "antiknight", "area": "r1c1"}
{"type": "neighbours", "op": "not_sum", "params": [10], "where": "orthogonal", "except": [["r1c1", "r1c2"]]}
```

| Field | Meaning |
|---|---|
| `kind` | `antiknight` (cells a knight's move apart differ), `antiking` (cells a king's move apart differ), `nonconsecutive` (orthogonal neighbours are not consecutive). Or omit `kind` and give `op` + `params` + `where`. |
| `op`, `params` | A symmetric pair operator (5.1). |
| `where` | `orthogonal` \| `diagonal` \| `king` \| `knight`. |
| `within` | Optional scope: `"box"` (only pairs inside one box) or `"region"` (only pairs inside one `region` rule). |
| `area` | Optional scope (5): only pairs with both cells in the area, e.g. one grid of a samurai. |
| `except` | Optional list of exempt pairs. |

Pairs are formed among existing cells of the board, unless a scope narrows them.

### 6.11 `relation`

Explicit pairs under one pair operator (5.1), for clues that are not edge clues (cells not adjacent, an operator no
edge kind has, or a pair rule a site defines):

```json
{"type": "relation", "op": "different", "params": [], "pairs": [["r1c1", "r3c3"], ["r1c1", "r4c4"]]}
```

### 6.12 `cell` (cell clues)

```json
{"type": "cell", "kind": "odd", "cells": ["r1c1", "r5c5"]}
{"type": "cell", "kind": "set", "values": [1, 2, 3], "cells": ["r2c2"]}
{"type": "cell", "kind": "high", "split": 5, "cells": ["r3c3"]}
```

| `kind` | Fields | Each listed cell holds |
|---|---|---|
| `odd` / `even` | – | an odd / even digit |
| `low` / `high` | `split` (REQUIRED) | 1..split / split+1..D |
| `set` | `values` | one of `values` |
| `exclude` | `values` | none of `values` |

"Every unmarked cell is low / even / …" is a `negative` rule over `cell` (6.14).

### 6.13 Other families

```json
{"type": "contains", "digits": [1, 9], "cells": ["r1c1", "r1c2", "r2c1", "r2c2"]}
{"type": "appears", "source": "r5c5", "cells": ["r5c6", "r5c7", "r5c8", "r5c9"]}
{"type": "clone", "regions": [["r1c1", "r1c2"], ["r9c8", "r9c9"]]}
{"type": "isomorphic", "regions": [["r1c1", "…81 cells…"], ["r1c11", "…81 cells…"]]}
{"type": "count", "each": 2, "cells": ["r1c1", "…"]}
{"type": "count", "kind": "circles", "cells": ["r1c1", "r4c7"]}
{"type": "distinct_count", "value": 2, "side": "top", "cells": ["r1c2", "r2c3", "r3c4"]}
{"type": "global_entropy"}
{"type": "equal_sum", "segments": [["r1c1", "r1c2"], ["r2c3"]]}
{"type": "vudoku", "cells": ["r2c2", "r3c1", "r3c3"]}
{"type": "table", "label": "T", "cells": ["r1c1", "r1c2", "r2c1"], "allowed": [[1, 2, 3], [3, 2, 1]]}
```

| `type` | Meaning |
|---|---|
| `contains` | Every listed digit (a multiset) appears among `cells` at least as often as it is listed. On a 2×2 block it is the quadruple clue. |
| `appears` | The digit in `source` appears in at least one of `cells` (e.g. an in-cell arrow whose digit occurs again along its ray). |
| `clone` | ≥ 2 equal-sized ordered `regions`; corresponding cells hold equal digits. |
| `isomorphic` | 2 ordered `regions` (twins): one fixed relabelling of the digits maps every cell of the first region to the corresponding cell of the second. |
| `count` | `each` k: every digit appears exactly k times among `cells` (Double Sudoku rows). Or `counts` `[[digit, times], …]`: those digits appear exactly that often. Kind `circles`: a digit that appears among the cells appears exactly as many times as its own value. Cells under `count` MUST NOT also be in a house. |
| `distinct_count` | Exactly `value` different digits among `cells`. With `side` it is an outside clue (ordered cells). |
| `global_entropy` | Every 2×2 window of existing cells holds a low, a middle and a high digit (thirds of 1..D; D divisible by 3). |
| `equal_sum` | Every segment (a cell set) has the same sum. For lines, use the `line` kinds `zipper`, `region_sum`, `double_arrow`. |
| `vudoku` | `cells` = [vertex, arm, arm]: the vertex digit is the sum or the difference of the two arm digits. |
| `table` | Escape hatch: the ordered `cells` take one of the `allowed` digit tuples. With `where` (a list of `[dr, dc]` offsets) instead of `cells`, the table applies to every placement of that window whose cells all exist, the offsets giving the column order. |

### 6.14 `negative`

States exactly which clues are "all shown".

```json
{"type": "negative", "of": "kropki"}
{"type": "negative", "of": "kropki", "color": "white"}
{"type": "negative", "of": "xv", "letter": "X"}
{"type": "negative", "of": "difference", "value": 5}
{"type": "negative", "of": "rossini"}
{"type": "negative", "of": "battenburg"}
{"type": "negative", "of": "cell", "kind": "high", "split": 5}
```

| `of` | Selector | Positions | An uncovered position … |
|---|---|---|---|
| `kropki` | `color` (omitted = both) | orthogonal pairs | is not consecutive (white covered) and not in a 1:2 ratio (black covered) |
| `xv` | `letter` (omitted = both) | orthogonal pairs | does not sum to 10 (X covered) / 5 (V covered) |
| `difference` / `ratio` / `product` | `value` (REQUIRED) | orthogonal pairs | does not satisfy that clue |
| `sum` | `sum` (REQUIRED) | orthogonal pairs | does not sum to `sum` |
| `rossini` | – | the first 3 cells inwards from each end of every full row and column house | is not monotone |
| `battenburg` | – | every 2×2 block whose cells share a `grid` / `box_grid` area (or of the whole board without one) | is not a parity checkerboard |
| `cell` | `kind` `odd` / `even` / `low` / `high` (+ `split` for low / high) | every cell | does not satisfy that clue (so it is even / odd / high / low) |

- **A negative covers exactly what its selector names.** With a selector it covers a single value:
  `{"of": "xv", "letter": "X"}` says only "pairs without a clue do not sum to 10"; V clues may be partial.
- **Exemption**: a position carrying **any** rule of the same family (any kropki dot of either colour; any X or V;
  any edge clue of that kind; any rossini arrow; any battenburg mark; any `cell` rule of that kind) is exempt.
- **Adjacency is only within one grid**: two cells form a pair only if some `grid` / `box_grid` area contains both (on a
  board without one, all orthogonally adjacent existing cells).
- Optional `area` (5): only positions whose cells are all in the area are covered.
- With no clue of the family in the file at all, the negative still applies (e.g. "no two adjacent digits sum to 10
  or 5").

### 6.15 Vendor rules

`{"type": "com.example:my_rule", …}`: must-understand like every other rule; a reader that does not implement it
refuses the file.

### 6.16 What is not a rule

Variant names (Argyle, Windoku, …) are not rules: they are `meta.type` only. Colours, fonts and artwork are `style`
and `decorations` only.

### 6.17 Reserved

- `"type": "custom"`: reserved for a rule language in a later version; every format_version 1 reader refuses it.
  Mechanics without a named rule use `table` (and `relation` with `allowed`).
- `digits` as an object (`{"values": [0, …, 8], "symbols": {…}}`, with an `empty` sentinel) for digit sets other
  than 1..D, and digit-selection puzzles: reserved; refused in format_version 1.

## 7. Default drawing

A renderer needs nothing beyond the rules. Sizes are in cell units (1 = a cell's side). Colours are defaults that
`style` may override. Draw order, bottom to top: cell shading, lines, cage outlines, grid lines and box borders,
edge / corner clues, digits, outside clues.

| Rule | Default drawing |
|---|---|
| grid | Thin lines between existing cells only; nothing at `null` positions. |
| boxes (`box_grid`, `box`) | Thick line wherever two adjacent existing cells lie in different boxes, and around the outside of the existing cells. |
| rows / columns | Nothing beyond the grid lines. |
| `region` `diagonal` | Thin grey line through the cell centres, extended to the outer corners of the end cells. |
| `region` `window` / `extra` | Light grey shading (`#d8d8d8`). |
| `region` `colour` | Shading by a palette colour per rule, in rule order (`#f4cccc #fce5cd #fff2cc #d9ead3 #d0e0e3 #c9daf8 #d9d2e9 #ead1dc #e6e6e6`, repeating). |
| `region` `disjoint` / `region` | Nothing (listed in the legend). |
| `cage` | Dashed outline inset 0.08 from the cell edges; `sum` in small type (0.25) in the top-left corner of the first cell in reading order. |
| `sum` `group` | Like a cage, dotted. |
| `sum` `corner` | Small white circle (0.3) with the sum at the shared corner. |
| `line` `thermo` | Grey (`#b0b0b0`) line, width 0.3; filled bulb, diameter 0.75, at `cells[0]`. |
| `line` `slow_thermo` | As thermo, bulb hollow. |
| `line` `whisper` | Green (`#3fbf3f`), width 0.2. |
| `line` `renban` | Purple (`#c060f0`), width 0.3. |
| `line` `region_sum` | Blue (`#3080ff`), width 0.2. |
| `line` `palindrome` | Grey (`#909090`), width 0.2. |
| `line` `entropic` | Orange (`#f0a040`), width 0.2. |
| `line` `modular` | Teal (`#20a0a0`), width 0.2. |
| `line` `parity` | Red (`#ff7070`), width 0.2. |
| `line` `zipper` | Lavender (`#9a8cf0`), width 0.2, small dot at the centre. |
| `line` `between` | Grey line, width 0.1; hollow circles (0.75) at both ends. |
| `line` `lockout` | Grey line, width 0.1; hollow diamonds at both ends. |
| `line` `double_arrow` | Grey line, width 0.05; hollow circles at both ends. |
| closed lines | The segment from the last cell back to the first is drawn too. |
| `arrow` | Hollow circle (0.75) on a 1-cell bulb, rounded pill over a longer bulb; each shaft a thin grey line from the bulb's edge with an open arrowhead at its last cell. |
| `edge` `kropki` | Dot (0.25) at the midpoint: white with a black outline, or black. |
| `edge` `xv` | The letter X or V (height 0.3) on a white chip. |
| `edge` `difference` / `sum` / `product` / `ratio` | Small white circle (0.3) with the number; `ratio` shows `k:1`, `product` `×p`. |
| `edge` `less` | Chevron at the midpoint pointing at `cells[0]`. |
| `corner` `battenburg` | Small 2×2 checker square (0.3) at the corner. |
| `corner` `mathrax` | Small white circle at the corner with `value` and `op` (`10+`), or `E` / `O`. |
| `corner` `exclude` | Small white circle at the corner with the digit. |
| `contains` | On a 2×2 block: white circle (0.45) at the corner with the digits. Otherwise the digits in small type in the top-left corner of the first cell. |
| `appears` | A small arrow in the `source` cell pointing along `cells`. |
| `sum` `little_killer` | Small number outside `cells[0]` on `side`, with a short arrow pointing along `cells[0] → cells[1]`. |
| `sum` `frame`, `sandwich`, `skyscraper`, `first_seen`, `distinct_count` with `side` | Plain number outside `cells[0]` on `side`. When kinds are mixed on one side: `xsum` in angle brackets ⟨n⟩, `skyscraper` in a small square, `first_seen` in a small circle. |
| `xsum` | Plain number outside `cells[0]` (⟨n⟩ when mixed). |
| `rossini` | Arrow glyph outside `cells[0]` on `side`, pointing into the grid (`in`) or out of it (`out`). |
| `cell` `odd` / `even` | Grey circle / grey square (0.8) behind the digit. |
| `cell` `low` / `high` | Light / dark grey diamond behind the digit. |
| `cell` `set` / `exclude` | The values in small type along the bottom of the cell; `exclude` struck through. |
| `clone` | The same light shading colour for all regions of one rule (palette as for colour regions). |
| `vudoku` | A thin V through the three cell centres, vertex at `cells[0]`. |
| `equal_sum` | Thin dashed outline around each segment. |
| `isomorphic`, `count`, `global_entropy`, `neighbours`, `negative` | Nothing in the grid (listed in the legend). |
| `relation` | Thin grey connector between the two cell centres. |
| `table`, vendor rules | Light highlight of the cells plus the `label` text in the first cell. |
| givens | Large digit. |
| candidates | Small digits in a 3×3 keypad layout (centred for D > 9). |

## 8. Cosmetic layers: style and decorations

Per-rule `style` (optional, never semantic):
`{"color": "#rrggbb" | palette index, "fill": "#rrggbb" | palette index, "opacity": 0..1, "width": cell units,
"shape": "circle" | "square" | "diamond", "label": "text", "label_cell": "r1c1", "dash": true}`.

Top-level `style`: puzzle-wide hints, e.g. `{"palette": [...], "cell_size": 64}`. Free-form.

`decorations`: artwork that carries no rule.

```json
{"kind": "line" | "arrow" | "rect" | "circle" | "text",
 "points": [[y, x], …], "center": [y, x], "size": [h, w], "text": "…", "style": { … }}
```

Coordinates are cell units `[row, col]` with the origin at the top-left corner of the board, so the centre of
`rRcC` is `[R − 0.5, C − 0.5]` (SudokuPad's convention shifted to the outer corner).

## 9. Canonical form, fingerprint, compression

### 9.1 Canonical writer (`pencilmark.dumps`)

- Top-level key order: `format`, `format_version`, `$schema`, `meta`, `board`, `digits`, `givens`, `solution`,
  `candidates`, `rules`, `decorations`, `style`, `ext`.
- Rule key order: `type`, `kind`, then the parameters (`op`, `params`, `color`, `letter`, `value`, `sum`, `split`,
  `values`, `digits`, `groups`, `each`, `counts`, `arrow`, `size`, `repeat`, `box`, `where`, `within`, `closed`),
  then `side`, then the cell keys (`origin`, `source`, `bulb`, `lines`, `cells`, `regions`, `segments`, `pairs`,
  `except`, `allowed`), then `id`, `label`, `style`.
- Houses as described in 6.1. Rules in the order given (a grader's tie-breaks can depend on it); a `box_grid` expands
  to rows, then columns, then boxes. Candidate lists ascending; `candidates` keys in reading order. Cells of sets as the source listed them (the
  fingerprint sorts them).
- Defaults omitted (`closed: false`; whisper `value` 5, entropic `groups`, modular `value` 3, lockout `value` 4 on
  9×9; they are written when D ≠ 9).
- Pretty form: `givens` and `solution` one grid row per line; one rule per line; LF line endings; UTF-8; no trailing
  spaces. Compact form: no whitespace.

### 9.2 Fingerprint

`pencilmark.fingerprint(puzzle) -> "sha256:<64 hex>"`:

1. Read the puzzle and write it canonically (9.1).
2. Keep only `format`, `format_version`, `board`, `digits`, `givens`, `candidates`, `rules`; in every rule drop `id`,
   `label`, `style`.
3. Replace all house rules (`grid`, `box_grid`, `box`, `row`, `column`) by the houses they state, one
   `{"type": "row" | "column" | "box", "cells": [...]}` per distinct house, so every spelling of the same houses (a
   `box_grid`, a `grid` plus `box` rules, single rules, in any order) gives the same result.
4. Sort the cells of set-like lists (3.3: region, cage, cell, contains, appears, count, sum group / corner,
   edge clues other than `less`, scope and `except` lists, the pairs of symmetric `relation` operators, `equal_sum`
   segments) in reading order.
5. Sort `rules` by their compact canonical JSON text.
6. Serialise with RFC 8785 (JSON Canonicalization Scheme) and hash with SHA-256.

`solution`, `meta`, `style`, `decorations` and `ext` never affect it, and neither does the order of rules or of the
engine's houses, so the same puzzle from two importers gets the same fingerprint. It is not symmetry-invariant: a
rotated or relabelled copy has another fingerprint.

### 9.3 Compression for links

For a share link, compress the compact canonical JSON with lz-string `compressToEncodedURIComponent` (as f-puzzles and
SudokuPad do), or gzip + base64url. Suggested URL parameter: `?pm=<data>`. Compression is transport only: the
decompressed text is a normal `sudoku-puzzle` file.

## 10. Examples

10.1–10.4 are complete files. From 10.5 on only `rules` is shown; the rest is as in 10.1.

### 10.1 Classic

```json
{"format": "sudoku-puzzle", "format_version": 1,
 "meta": {"title": "Example classic", "author": "pencilmark"},
 "board": {"rows": 9, "cols": 9},
 "digits": 9,
 "givens": [
    7, 9, 0, 2, 1, 4, 0, 0, 0,
    8, 0, 6, 7, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0,
    4, 0, 2, 0, 0, 7, 8, 0, 0,
    0, 0, 8, 4, 0, 3, 2, 0, 0,
    0, 0, 1, 6, 0, 0, 5, 0, 3,
    0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 9, 7, 0, 2,
    0, 0, 0, 8, 2, 6, 0, 3, 9],
 "solution": [
    7, 9, 5, 2, 1, 4, 3, 6, 8,
    8, 1, 6, 7, 3, 5, 9, 2, 4,
    3, 2, 4, 9, 6, 8, 1, 5, 7,
    4, 3, 2, 1, 5, 7, 8, 9, 6,
    5, 6, 8, 4, 9, 3, 2, 7, 1,
    9, 7, 1, 6, 8, 2, 5, 4, 3,
    2, 4, 9, 3, 7, 1, 6, 8, 5,
    6, 8, 3, 5, 4, 9, 7, 1, 2,
    1, 5, 7, 8, 2, 6, 4, 3, 9],
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]}]}
```

Made by the pencilmark generator (unique, graded Easy).

### 10.2 Killer (4×4)

```json
{"format": "sudoku-puzzle", "format_version": 1,
 "meta": {"title": "Example 4x4 killer"},
 "board": {"rows": 4, "cols": 4},
 "digits": 4,
 "givens": [
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0],
 "solution": [
    1, 2, 3, 4,
    4, 3, 1, 2,
    2, 1, 4, 3,
    3, 4, 2, 1],
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [2, 2]},
  {"type": "cage", "sum": 3, "cells": ["r1c1", "r1c2"]},
  {"type": "cage", "sum": 4, "cells": ["r1c3", "r2c3"]},
  {"type": "cage", "sum": 6, "cells": ["r1c4", "r2c4"]},
  {"type": "cage", "sum": 6, "cells": ["r2c1", "r3c1"]},
  {"type": "cage", "sum": 4, "cells": ["r2c2", "r3c2"]},
  {"type": "cage", "sum": 10, "cells": ["r3c3", "r3c4", "r4c3", "r4c4"]},
  {"type": "cage", "sum": 7, "cells": ["r4c1", "r4c2"]}]}
```

Made by the generator (zero givens, unique). `describe()` names it "Tiny Killer Sudoku".

### 10.3 Jigsaw (6×6)

```json
{"format": "sudoku-puzzle", "format_version": 1,
 "board": {"rows": 6, "cols": 6},
 "digits": 6,
 "givens": [
    0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0],
 "rules": [
  {"type": "grid", "origin": "r1c1"},
  {"type": "box", "cells": ["r1c1", "r1c2", "r1c3", "r2c1", "r2c2", "r3c1"]},
  {"type": "box", "cells": ["r1c4", "r1c5", "r1c6", "r2c5", "r2c6", "r3c6"]},
  {"type": "box", "cells": ["r2c3", "r2c4", "r3c2", "r3c3", "r3c4", "r4c3"]},
  {"type": "box", "cells": ["r3c5", "r4c4", "r4c5", "r4c6", "r5c5", "r5c6"]},
  {"type": "box", "cells": ["r4c1", "r4c2", "r5c1", "r5c2", "r6c1", "r6c2"]},
  {"type": "box", "cells": ["r5c3", "r5c4", "r6c3", "r6c4", "r6c5", "r6c6"]}]}
```

The `grid` gives the rows and columns; each piece is a `box`. (A shape example, no givens.)

### 10.4 Samurai (structure)

```json
{"format": "sudoku-puzzle", "format_version": 1,
 "board": {"rows": 21, "cols": 21},
 "digits": 9,
 "givens": [
    0, 0, 0, 0, 0, 0, 0, 0, 0, null, null, null, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    …rows 2 to 6 the same…,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    …rows 8 and 9 the same…,
    null, null, null, null, null, null, 0, 0, 0, 0, 0, 0, 0, 0, 0, null, null, null, null, null, null,
    …rows 11 and 12 the same…,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    …rows 14 and 15 the same…,
    0, 0, 0, 0, 0, 0, 0, 0, 0, null, null, null, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    …rows 17 to 21 the same…],
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "box_grid", "origin": "r1c13", "box": [3, 3]},
  {"type": "box_grid", "origin": "r7c7", "box": [3, 3]},
  {"type": "box_grid", "origin": "r13c1", "box": [3, 3]},
  {"type": "box_grid", "origin": "r13c13", "box": [3, 3]}]}
```

(`…` marks rows left out of this document; a real file lists all 441 entries.) The centre grid shares one box with
each corner grid; a shared box is one house. Board row 7 holds three separate 9-cell row houses (c1–c9, c7–c15,
c13–c21).

### 10.5 X-sudoku and argyle

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c1", "r2c2", "r3c3", "r4c4", "r5c5", "r6c6", "r7c7", "r8c8", "r9c9"]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c9", "r2c8", "r3c7", "r4c6", "r5c5", "r6c4", "r7c3", "r8c2", "r9c1"]}]
```

Argyle has 8 shorter diagonals instead, all `region` kind `diagonal`, e.g.
`{"type": "region", "kind": "diagonal", "cells": ["r1c2", "r2c3", "r3c4", "r4c5", "r5c6", "r6c7", "r7c8", "r8c9"]}`.

### 10.6 Thermo, arrow and kropki

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "line", "kind": "thermo", "cells": ["r9c1", "r8c1", "r7c1", "r7c2"]},
  {"type": "line", "kind": "thermo", "cells": ["r9c1", "r9c2", "r9c3"]},
  {"type": "arrow", "bulb": ["r2c2"], "lines": [["r3c3", "r4c4", "r5c5"]]},
  {"type": "arrow", "bulb": ["r1c7", "r1c8"], "lines": [["r2c8", "r3c8"]]},
  {"type": "edge", "kind": "kropki", "color": "white", "cells": ["r5c7", "r5c8"]},
  {"type": "edge", "kind": "kropki", "color": "black", "cells": ["r6c7", "r7c7"]}]
```

The two thermos share the bulb r9c1. The second arrow's pill reads as 10·r1c7 + r1c8.

### 10.7 Negative XV

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r1c2"]},
  {"type": "edge", "kind": "xv", "letter": "V", "cells": ["r4c5", "r5c5"]},
  {"type": "negative", "of": "xv"}]
```

Every pair without a clue sums to neither 10 nor 5. With `{"type": "negative", "of": "xv", "letter": "X"}` instead,
every X is shown but V clues may be partial. With no XV clues at all, the negative alone is "Non-XV".

### 10.8 Sandwich, x-sum and little killer

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "sandwich", "sum": 12, "side": "left", "cells": ["r3c1", "r3c2", "r3c3", "r3c4", "r3c5", "r3c6", "r3c7", "r3c8", "r3c9"]},
  {"type": "xsum", "sum": 24, "side": "top", "cells": ["r1c9", "r2c9", "r3c9", "r4c9", "r5c9", "r6c9", "r7c9", "r8c9", "r9c9"]},
  {"type": "sum", "kind": "little_killer", "sum": 15, "side": "top", "cells": ["r1c4", "r2c5", "r3c6", "r4c7", "r5c8", "r6c9"]},
  {"type": "sum", "kind": "little_killer", "sum": 9, "side": "bottom", "cells": ["r9c2", "r8c1"]}]
```

The x-sum reads down column 9: X = r1c9. The first little killer sits above r1c4 and runs down-right; the second sits
below r9c2 and runs up-left.

### 10.9 Anti-knight within boxes only

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "neighbours", "kind": "antiknight", "within": "box"}]
```

Only knight-move pairs inside one box must differ. Without `within` the rule covers the whole board.

## 11. Grade card: `sudoku-grade`

What `rate()` returns and `pencilmark rate --json` prints: one JSON object per puzzle. JSON Schema:
`docs/sudoku-grade.schema.json`.

```json
{"format": "sudoku-grade", "format_version": 1,
 "grader": {"name": "pencilmark", "version": "1.0.0"},
 "difficulty": 5.9, "time": 10.7, "band": "Medium", "band_index": 2,
 "contains": [{"code": "HSI", "chip": "HSI", "name": "Hidden Single", "band": 0},
              {"code": "NPR", "chip": "NPR/PPR/HPR", "name": "Naked Pair", "band": 2, "uses": 1, "alternatives": ["PPR", "HPR"]},
              {"code": "XWG", "chip": "XWG/KTE/SCL", "name": "X-Wing", "band": 2, "uses": 1, "alternatives": ["KTE", "SCL"]}],
 "contains_complete": true, "contains_truncated": false,
 "issues": [], "reject": false}
```

A card exists only for a puzzle with exactly one solution. For any other puzzle, `rate()` raises `NotUnique`,
`NoSolution` or `Undecided`; `rate_many()` and the command line give `{"error": "…"}` in its place (the command line adds
`"line"`, the input line number, to every object).

### 11.1 Keys

| Key | Field | Type | Meaning |
|---|---|---|---|
| `format`, `format_version` | always | `"sudoku-grade"`, `1` | |
| `grader` | always | `{"name", "version"}` | The engine that made the card. A card is only meaningful with that engine and version. |
| `difficulty` | default | number or null | How hard the steps feel, continuous from 0 (one empty cell), no ceiling; a typical newspaper medium is about 5. Null when the band is `Unknown`. |
| `time` | default | number or null | Expected minutes for an average player. |
| `time_p80` | optional | number or null | Minutes within which 80% of players finish. |
| `band` | default | string | `"Very Easy"`, `"Easy"`, `"Medium"`, `"Hard"`, `"Very Hard"`, `"Extreme"`; `"Unknown"` only when guessing was allowed and used. |
| `band_index` | default | integer or null | 0 (Very Easy) … 5 (Extreme); null for `Unknown`. |
| `contains` | default | list | The techniques met on the easiest route, easiest first (11.3). |
| `contains_complete` | with `contains` | boolean | False when the route stops where human logic ran out (band `Unknown`); `stopped_at_step` then gives the step. |
| `stopped_at_step` | with `contains`, when incomplete | integer | The first step human logic could not make. |
| `contains_truncated` | with `contains` | boolean | True when a `max_seconds` cap stopped the search for the shortest list: the list may not be minimal or may miss alternatives. |
| `issues` | default | list | Publishing checks (11.4). |
| `reject` | default | boolean | True when any issue has severity `reject`. |
| `se`, `se_diuf` | optional | `{"er", "ep", "ed", "scale"}` or null | Sudoku Explainer-style ratings of the route, on the classic scale or the DiufSudoku fork's (`scale` says which). Meaningful for classic sudoku only. |
| `steps` | optional | list | The step-by-step route (11.5). |
| `describe` | optional | object | The `describe()` output (section 13). |
| `symmetry` | optional | list | Symmetries of the givens pattern, entries as in the generator spec (`{"kind", "axis"?, "of": "givens"}`). |

### 11.2 Choosing fields

`rate(puzzle, fields=[...])` and `--fields a,b,c` take a list of the keys above; only those are computed. A field name
is always the key it produces (`contains` also brings `contains_complete`, `contains_truncated` and `stopped_at_step`).
Without `fields`, the default fields are returned. `explain="short"`, `"teach"` or both (CLI `--explain short,teach`)
adds explanations to `steps`. Shorthands: `steps=True` = the `steps` field with both explanation levels; `se=True` /
`se="diuf"` = the `se` / `se_diuf` field.

### 11.3 `contains`

Each entry is one technique on the route:

| Key | Meaning |
|---|---|
| `code` | Three-letter technique code (USAGE.md lists them). |
| `chip` | `code` plus its alternatives, `/`-separated: any one of them gets the solver through at that point. |
| `name` | Technique name. |
| `band` | The technique's band index. |
| `uses` | Times used on the route; omitted for singles (band 0), whose count depends on the route. |
| `alternatives` | Other codes that also work there; omitted when there are none. |

### 11.4 `issues`

`{"code", "severity", "text", "rules"?}`. `severity` is `"reject"` (would not be published) or `"warning"`. `rules`, when
present, lists the offending rules as indices into `rules` of the puzzle as `to_export` writes it.

Each check can be adjusted with a **quality object** keyed by code: `rate(puzzle, quality={"trivial": 0.5, "trial":
false})`, CLI `--quality trivial=0.5,trial=false`, or the generator spec's `quality` (section 12). A check with a limit
takes a number (`true` = the default limit); every check takes `false` to turn it off.

| Code | Severity | Meaning | Limit (default) |
|---|---|---|---|
| `spike` | reject | A Hard or harder puzzle that rests on at most *limit* band-level moves in an otherwise all-singles (95%) solve. | moves (2) |
| `decorative` | reject | A rule that is neither needed for uniqueness nor used by any step. | on / off |
| `barely_used` | reject when never used, else warning | A rule used in fewer than *limit* steps. | steps (3) |
| `redundant` | warning | A rule the puzzle is unique without, although the solve uses it. | on / off |
| `trivial` | reject | More than *limit* of the cells are given (0.6 = 60%). | share (0.6) |
| `tedious` | warning | Very Easy or Easy, but over *limit* minutes of routine work. | minutes (60) |
| `uniqueness` | warning | Needs a uniqueness-based technique (relies on assuming one solution). | on / off |
| `trial` | warning | Needs trial and error or forcing chains. | on / off |

Example: `{"code": "barely_used", "severity": "reject", "text": "thermo lines (rules 3, 4, 5, 6): used in only 0 steps
of the solve", "rules": [3, 4, 5, 6]}`.

### 11.5 `steps`

Each step: `n` (from 1), `technique` (name), `code`, `band`, then `placement` (`"r2c8=3"`) and / or `eliminations`
(`["r4c5#7", …]`: candidate 7 removed from r4c5), and, when requested, `explanation`: `{"short": …, "teach": …}` with
the requested levels.

## 12. Generator spec: `sudoku-spec`

A request to the generator **is a puzzle file with blanks**: the same envelope and rule vocabulary, its own `format` (no
puzzle reader mistakes it for a puzzle), plus four blocks that say what the result must satisfy and how long to try.

```json
{"format": "sudoku-spec", "format_version": 1,
 "meta": {"title": "Whisper showcase"},
 "board": {"rows": 9, "cols": 9},
 "digits": 9,
 "givens": {"count": [0, 6]},
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "line", "kind": "whisper", "value": 5, "cells": ["r1c1", "r2c2", "r3c2", "r4c3"]},
  {"type": "line", "kind": "whisper", "value": 5, "cells": ["r9c1", "r8c2", "r7c2"]},
  {"type": "line", "kind": "whisper", "value": 5, "cells": ["r5c4", "r5c5", "r5c6"]},
  {"type": "cage", "count": "auto", "size": [2, 5]}],
 "symmetry": [{"kind": "rot180", "of": "givens"}],
 "where": {"band": "Hard", "difficulty": [6.5, 8], "contains": ["XWG"], "issues": "no_reject"},
 "quality": {"trivial": 0.4},
 "limits": {"results": 3, "attempts": 2000, "time": 600, "seed": 42},
 "fields": ["difficulty", "band", "contains", "issues"]}
```

**Fixed vs open.** A rule **with cells is locked**: copied into every result exactly as drawn (`"lock": false` = a
starting point the generator may move or drop). A rule **with `count` and no cells** is a template the generator fills;
`count` is a number, `[min, max]` (`max` may be `null`), `"auto"` (as many as needed), `"all"` (every true clue: for
edge kinds this adds the matching `negative`), `"min"` (a minimal set) or `"tile"` (cages / boxes partitioning the
area). Templates take shape limits where meaningful: `size` (cells per cage / box), `length` (cells per line), `value`
(e.g. whisper difference), `displaced` (jigsaw: cells moved out of the regular boxes). Any template or locked rule may
carry `"area"` (section 5: a grid's origin or a cell list), limiting where it lives.

**Givens.** `"givens"` is either the puzzle form (a flat list: digits are locked givens, `0` = must stay empty, `null`
= no cell) or an object: `count` (number or range), `mask` (flat list, `1` = must be given, `0` = must be empty,
`null` = generator decides), `values` (`{"r1c1": 5, …}` locked digits).

**Symmetry** is a list; each entry has `kind` (`rot180`, `rot90`, `mirror` with `axis` `horizontal` | `vertical` |
`diagonal` | `antidiagonal`) and `of`: `"givens"`, `"all"` (givens and every rule), or a rule selector such as
`{"type": "line"}` / `{"type": "line", "kind": "whisper"}`. The same entries are a quality check and are reported by
`describe()`.

**`where`: targets on the card**, using the card's keys (section 11): `band` (value or list), `difficulty`
(`[lo, hi]` or `"max"` / `"min"`), `time` (`{"max": minutes}`), `contains` (codes that must appear; `{"codes": [...],
"strict": true}` = as the code itself, not only as an alternative in a chip; `{"only": [...]}` to allow nothing else, and
per-code `{"uses": n}`), `not_contains`, `issues` (`"none"`, `"no_reject"` (warnings allowed) or a list of allowed codes), `elements` (`{"max": n}`: at most
n placed rule elements in total).
**Per-area targets**: `"areas": [{"area": "r1c13", "where": {"band": "Medium"}}]`, measured on the **joint** solve (the
steps that place or eliminate in that area on the whole-board route), never on the area generated alone.

**`quality`: the checks' limits**, the same object as `rate(..., quality=…)` (11.4): `{"trivial": 0.4, "trial": false}`.
It changes what the card reports as `issues`; `where.issues` chooses which of them a result may have.

**`limits`** bound every run: `results` (puzzles to return), `attempts`, `time` (seconds), `seed` (reproducible runs).
The run stops at the first limit; `"max"` / `"min"` targets are best-so-far and the result reports achieved vs
requested.

**`fields`**: which card fields to return with each result (section 11).

pencilmark's generator implements a subset of this language and refuses the rest with a clear message, never silently
ignoring a part; see [USAGE.md](USAGE.md#generator). Example specs are in `docs/examples/specs/`.

A run's result is an ordinary `sudoku-puzzle`; `meta.generated_from` may carry the spec's fingerprint.

## 13. describe(): variant name and rules

`describe(puzzle)` names the variant and lists its rules **from the rules alone**, as an ordered map from a short name
to one sentence, like the rule headers on Logic Masters:

```json
{"type": "Variant Sudoku",
 "rules": {"Sudoku": "Place 1–9 in every row, column and 3×3 box.",
           "Argyle": "Digits don't repeat on any of the eight marked diagonals.",
           "Killer": "Digits in a cage sum to its small clue and don't repeat within the cage.",
           "Anti-Knight": "Cells a knight's move apart don't contain the same digit.",
           "XV": "Digits separated by an X sum to 10; digits separated by a V sum to 5. All X's and V's are given."}}
```

It is deterministic, never reads `meta`, and never feeds back into solving. `rules_text(described)` renders it as
"Key: sentence" lines. `to_export` uses both only to fill an **empty** `meta.type` / `meta.rules_text`; it never
overwrites them.

The variant names are **not part of the file format**: they appear only in `meta.type` and in `describe()` output. They
come from a registry in code (`pencilmark/variants.py`), so they generalise across sizes (a 16×16 windoku, a 6×6 X).

### 13.1 Name

`type` = [size word] + [ONE variant name, or "Variant" when two or more variants are present] + "Sudoku".

- Size word: 4×4 `Tiny`, 6×6 `Mini`, 9×9 none, other sizes `NxN` (`8x8`, `16x16`). There is no "Classic": a plain
  9×9 is `"Sudoku"`, a plain 6×6 `"Mini Sudoku"`.
- The houses of a variant (windoku windows, X diagonals) and its own negative rules belong to that variant and do not
  count as extra variants.
- Boards with several grids use their layout name: "Samurai Sudoku", "Twodoku", "Butterfly Sudoku", … ("Multi-Grid
  Sudoku" for an unknown layout); with one variant it goes in front ("Killer Samurai Sudoku"), with more "Variant
  Samurai Sudoku".
- A board with rows / columns but no boxes and nothing else is a "Latin Square".
- The first key of `rules` is the base: "Sudoku" (with the size word: "Mini Sudoku", "16x16 Sudoku"), or the layout name.

### 13.2 Recognition

- **Placement variants** are functions of ONE grid area (a `grid` / `box_grid`, or the whole board) that return the rules the variant adds there, or nothing where
  the variant is not defined for that size or box shape. For each grid area of the puzzle, every placement variant is
  run; if all the rules it returns are present in the puzzle (compared as type, kind and cell set; region kinds are
  drawing hints and are ignored), the variant applies and those rules are explained.
- **Rule families** (killer, thermo, kropki, …) are recognised by rule type and kind; a family's negative rules join
  it ("XV" with `{"type": "negative", "of": "xv"}`; a negative alone is "Non-XV").
- `box` rules (boxes that are not a regular tiling) are "Jigsaw".
- Anything left falls back to a generic family name ("Diagonals", "Windows", "Extra Regions", …).
- On a multi-grid board, a variant or family whose rules lie in some grids only says so at the end of its sentence:
  "Only in the top-left grid." Grids are named by position (top-left, centre, …), or by origin ("grid at r7c7") when
  positions would be ambiguous.

### 13.3 Placement variants (geometric definitions)

For porting: a grid area has size n, boxes bh × bw, local rows and columns 0 … n−1.

| Name (aliases) | Defined for | Rules added to the grid area |
|---|---|---|
| X (Diagonal) | any n | `region` diagonal on (i, i) and on (i, n−1−i), i = 0 … n−1 |
| Windoku (Hyper, NRC) | boxes, n/bh ≥ 2 and n/bw ≥ 2 | a bh × bw `region` window at every (1 + i(bh+1), 1 + j(bw+1)), i < n/bh − 1, j < n/bw − 1, that fits inside the grid's inner border (9×9: 4 windows at r2c2, r2c6, r6c2, r6c6; 16×16: 9) |
| Argyle | n = 9 | `region` diagonals of 8 cells from (0,1), (1,0) going down-right and from (0,7), (1,8) going down-left; of 5 cells from (0,4) going down-left and down-right, from (4,0) down-right and (4,8) down-left |
| Asterisk | n = 9 | one `region`: (1,4) (2,2) (2,6) (4,1) (4,4) (4,7) (6,2) (6,6) (7,4) |
| Centre-dot (Center dot) | boxes with odd bh and bw | one `region`: the centre cell (br + ⌊bh/2⌋, bc + ⌊bw/2⌋) of every box |
| Girandola | n = 9 | one `region`: (0,0) (0,8) (1,4) (4,1) (4,4) (4,7) (7,4) (8,0) (8,8) |
| Disjoint Groups (Colour) | boxes | bh·bw `region`s: for each in-box position (a, b), the cells (br + a, bc + b) of every box |

### 13.4 Rule families

In registry order (the order of the `rules` keys): Killer (`cage`), Little Killer, Sum Frame, Sum (`sum` group /
corner), Sandwich, X-Sums, Skyscrapers, Rossini (+ its negative), 123 (`first_seen`), Count Different, Arrow, Thermo,
Slow Thermo, Whispers (German Whispers for 5, Dutch Whispers for 4), Renban, Region Sum, Palindrome, Entropic,
Modular, Parity, Zipper, Between Lines, Lockout, Double Arrow, Kropki (white dots only: Consecutive; negative alone:
Non-Kropki), XV (negative alone: Non-XV), Difference, Sum Pairs, Product, Ratio, Greater-Than, Battenburg, Mathrax,
Exclusion, Quadruple (`contains`), Cupid (`appears`), Clone, Twin (`isomorphic`), Odd-Even, Low-High, Digit Class,
Double / Counting Circles / Count (`count`), Distinct Count, Equal Sums, Vudoku, Entropy (`global_entropy`),
Anti-Knight, Anti-King, Non-Consecutive, Neighbours (generic), Relation, Custom (`table`, vendor rules), Sukaku
(`candidates`). Each has one sentence, filled from its rules (whisper gap, sandwich digits, scope "within the same box",
"All X's and V's are given." for a negative, …).

### 13.5 Generator presets

The placement functions double as presets: `variants.preset_rules("windoku", 16)` gives the 9 windows of a 16×16
board.
