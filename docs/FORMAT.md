# Puzzle format: `sudoku-puzzle`, format_version 1

Specification of the transport format for sudoku puzzles, classic and variant. It says what a file means, not how to
draw it or how hard the puzzle is: those are separate documents ([STYLE.md](STYLE.md) for drawing, [GRADE.md](GRADE.md)
for the grade card, [SPEC.md](SPEC.md) for generator requests). The [JSON Schema](https://json-schema.org/) is
[`sudoku-puzzle.schema.json`](sudoku-puzzle.schema.json); [pencilmark](https://github.com/silly-puppyy/pencilmark) is the
reference implementation.

The key words MUST, MUST NOT, SHOULD and MAY are used as in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

Contents

1. [Overview](#1-overview)
2. [Envelope](#2-envelope)
3. [Cells, outside clues and ordering](#3-cells-outside-clues-and-ordering)
4. [Strict reading (must-understand)](#4-strict-reading-must-understand)
5. [Rules: common shape and pair operators](#5-rules-common-shape-and-pair-operators)
6. [Rule families](#6-rule-families)
7. [Cosmetic layers: style and decorations](#7-cosmetic-layers-style-and-decorations)
8. [Canonical form, fingerprint, compression](#8-canonical-form-fingerprint-compression)
9. [Examples](#9-examples)

---

## 1. Overview

A `sudoku-puzzle` file describes one puzzle completely: the board, the givens, and every rule, houses included.
It is written so that:

- a **solver or grader** can rely on every rule having one exact meaning (section 6), with no defaults that depend on
  the board size;
- a **renderer** can draw the puzzle from the rules alone (how is up to the renderer; [STYLE.md](STYLE.md) lists
  common practice);
- a reader that meets something it does not understand **refuses** the file instead of silently dropping a rule
  (section 4);
- every puzzle has **one canonical representation** (section 8).

The file is JSON ([RFC 8259](https://www.rfc-editor.org/rfc/rfc8259)), UTF-8, conventionally named `*.json` or
`*.sudoku.json`, media type `application/json`. A file is recognised by its `"format"` member, not by its name.
Several puzzles go in a [JSON Lines](https://jsonlines.org/) file (`*.jsonl`): one compact `sudoku-puzzle` object per
line.

### 1.1 What each reader needs

Meaning and drawing are kept apart, so different programs read different parts of a file:

- a **renderer** needs the board, the givens, and each rule's family, kind and cells (plus any number it shows, such as
  a cage sum); it never needs to know what a rule means arithmetically. It MAY use `style` and `decorations`.
- a **solver or grader** needs the board, the givens and the rules; it MUST NOT depend on `meta`, `style` or
  `decorations`, which never change a puzzle's meaning.

### 1.2 Implementing a subset

Nothing obliges a reader to support every rule family. A reader MAY implement any subset of section 6, as long as it
**refuses** a file that uses a family or kind outside it (section 4) instead of reading it without that rule. The
smallest useful reader understands the envelope, `grid` and `box_grid`: that is every classic puzzle. Each further
family can be added on its own; the families do not depend on each other except through the shared shapes of
section 5. A writer SHOULD use only the families the puzzle needs. Sections 7 (cosmetic layers) and 8 (canonical form)
are optional for readers: cosmetic layers may be ignored, and only a writer that produces fingerprints needs section 8.

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
| `decorations` | no | Cosmetic drawing primitives (section 7). Never semantic. |
| `style` | no | Cosmetic, puzzle-wide drawing hints (section 7). Never semantic. |
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
| `type` | Display name of the variant, e.g. `"Killer Sudoku"`. Variant names live **only** here; they never change the rules. `describe()` ([NAMING.md](NAMING.md)) fills it when it is empty. |
| `license` | Licence of the puzzle. |
| `tags` | List of strings. |
| `generated_from` | Fingerprint of the `sudoku-spec` that produced the puzzle ([SPEC.md](SPEC.md)). |

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
fingerprint sorts, section 8.2).

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
| `style` | Cosmetic drawing hints for this rule (section 7). Ignorable. |

**Areas.** A rule that applies to part of the board says where with `area`: the `origin` of a `grid` / `box_grid` rule
in the file (that grid's D × D cells), or a list of cells. The same key means the same thing everywhere it appears
(`neighbours`, `negative`, and the generator spec, [SPEC.md](SPEC.md)).

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

## 7. Cosmetic layers: style and decorations

Per-rule `style` (optional, never semantic):
`{"color": "#rrggbb" | palette index, "fill": "#rrggbb" | palette index, "opacity": 0..1, "width": cell units,
"shape": "circle" | "square" | "diamond", "label_cell": "r1c1", "dash": true}`. The text a rule shows is its
`label` (section 5); `label_cell` only says where to draw it.

Top-level `style`: puzzle-wide hints, e.g. `{"palette": [...], "cell_size": 64}`. Free-form.

`decorations`: artwork that carries no rule.

```json
{"kind": "line" | "arrow" | "rect" | "circle" | "text",
 "points": [[y, x], …], "center": [y, x], "size": [h, w], "text": "…", "style": { … }}
```

Coordinates are cell units `[row, col]` with the origin at the top-left corner of the board, so the centre of
`rRcC` is `[R − 0.5, C − 0.5]` ([SudokuPad](https://sudokupad.app/)'s convention shifted to the outer corner).

## 8. Canonical form, fingerprint, compression

### 8.1 Canonical writer (`pencilmark.dumps`)

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

### 8.2 Fingerprint

`pencilmark.fingerprint(puzzle) -> "sha256:<64 hex>"`:

1. Read the puzzle and write it canonically (8.1).
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

### 8.3 Compression for links

For a share link, compress the compact canonical JSON with lz-string `compressToEncodedURIComponent` (as [f-puzzles](https://www.f-puzzles.com/) and
SudokuPad do), or gzip + base64url. Suggested URL parameter: `?pm=<data>`. Compression is transport only: the
decompressed text is a normal `sudoku-puzzle` file.

## 9. Examples

10.1–10.4 are complete files. From 10.5 on only `rules` is shown; the rest is as in 10.1.

### 9.1 Classic

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

### 9.2 Killer (4×4)

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

### 9.3 Jigsaw (6×6)

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

### 9.4 Samurai (structure)

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

### 9.5 X-sudoku and argyle

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c1", "r2c2", "r3c3", "r4c4", "r5c5", "r6c6", "r7c7", "r8c8", "r9c9"]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c9", "r2c8", "r3c7", "r4c6", "r5c5", "r6c4", "r7c3", "r8c2", "r9c1"]}]
```

Argyle has 8 shorter diagonals instead, all `region` kind `diagonal`:

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c2", "r2c3", "r3c4", "r4c5", "r5c6", "r6c7", "r7c8", "r8c9"]},
  {"type": "region", "kind": "diagonal", "cells": ["r2c1", "r3c2", "r4c3", "r5c4", "r6c5", "r7c6", "r8c7", "r9c8"]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c8", "r2c7", "r3c6", "r4c5", "r5c4", "r6c3", "r7c2", "r8c1"]},
  {"type": "region", "kind": "diagonal", "cells": ["r2c9", "r3c8", "r4c7", "r5c6", "r6c5", "r7c4", "r8c3", "r9c2"]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c5", "r2c4", "r3c3", "r4c2", "r5c1"]},
  {"type": "region", "kind": "diagonal", "cells": ["r1c5", "r2c6", "r3c7", "r4c8", "r5c9"]},
  {"type": "region", "kind": "diagonal", "cells": ["r5c1", "r6c2", "r7c3", "r8c4", "r9c5"]},
  {"type": "region", "kind": "diagonal", "cells": ["r5c9", "r6c8", "r7c7", "r8c6", "r9c5"]}]
```

### 9.6 Thermo, arrow and kropki

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

### 9.7 Negative XV

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "edge", "kind": "xv", "letter": "X", "cells": ["r1c1", "r1c2"]},
  {"type": "edge", "kind": "xv", "letter": "V", "cells": ["r4c5", "r5c5"]},
  {"type": "negative", "of": "xv"}]
```

Every pair without a clue sums to neither 10 nor 5. With `{"type": "negative", "of": "xv", "letter": "X"}` instead,
every X is shown but V clues may be partial. With no XV clues at all, the negative alone is "Non-XV".

### 9.8 Sandwich, x-sum and little killer

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

### 9.9 Anti-knight within boxes only

```json
"rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "neighbours", "kind": "antiknight", "within": "box"}]
```

Only knight-move pairs inside one box must differ. Without `within` the rule covers the whole board.
