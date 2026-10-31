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
 "style": { … }}
```

| Key | Required | Meaning |
|---|---|---|
| `format` | yes | Always `"sudoku-puzzle"`. |
| `format_version` | yes | Integer, `1`. Bumped only on a breaking change. A reader MUST refuse a file whose `format_version` is higher than it supports. |
| `$schema` | no | URL of the JSON Schema. Ignored by readers. |
| `meta` | no | Information *about* the puzzle (2.1). Never changes how it is solved or graded. |
| `board` | yes | `{"rows": R, "cols": C}`: the bounding rectangle of the board. No other keys. |
| `digits` | yes | Integer D ≥ 1: cells hold the digits 1..D. (Other digit sets and display symbols are reserved for a later version; see [6.17](rules/other.mdx)). |
| `givens` | yes | Flat list of R×C entries in reading order (row by row). `0` = empty cell, `null` = no cell at that position (the gaps of multi-grid boards), otherwise the given digit as a number (so 10..D work). This is the **only** representation: no text rows, no digit strings, no per-cell objects. |
| `solution` | no | Same shape as `givens`, every existing cell filled, `null` exactly where `givens` has `null`. |
| `candidates` | no | Given pencil marks (Sukaku): `{"r1c1": [1, 3, 7], …}`, ascending integer lists. **Semantic**: each listed cell's digit is one of its list; unlisted cells are unrestricted. Graphical cell clues (odd, even, …) are `cell` rules, never candidates. |
| `rules` | yes | Every constraint, houses included (section 6). Nothing is implied: a board without house rules has no houses. |
| `decorations` | no | Cosmetic drawing primitives (section 7). Never semantic. |
| `style` | no | Cosmetic, puzzle-wide drawing hints (section 7). Never semantic. |

There is no uniqueness flag: whether a puzzle has one solution is a property a tool checks, not a field.

### 2.1 meta

Everything a program wants to carry about the puzzle goes here: every key is optional and free-form, and tools keep
keys they do not know, so adding `"author"` is all attribution needs. Text is plain (no HTML, no language maps). Data
for one program goes under a reverse-DNS key, e.g. `"com.example.app": {…}`. The suggested keys, so that programs
agree on the common ones:

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
| `edge` kind `less` and `relation` pairs of `less` / `less_equal` / `any_of`: `[a, b]` in operator order | `corner` cells (written TL, TR, BL, BR = reading order) |
| `vudoku` cells (vertex first), `box` / `row` / `column` `cells` | `area` cell lists, `except` pairs |

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
   these, which are always safe to ignore: `meta`, `style` (top level and per rule), `decorations`, and a rule's `id`
   and `label`.
3. A rule `type` it does not know, or a `kind` it does not know for a known type.
4. A vendor rule type (`"com.example:foo"`: reverse-DNS namespace, colon, name) it does not implement. Core type names
   never contain a colon.
5. `"type": "custom"` (reserved, [6.17](rules/other.mdx)).
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
complete. Ignorable containers never carry rules: no constraint may be derived from `meta`, `style` or
`decorations`.

## 5. Rules: common shape and pair operators

Every rule is an object with a `type` (the mechanic family); many families also have a `kind` (a flavour with its own
semantics and drawing). Every rule MAY carry:

| Key | Meaning |
|---|---|
| `id` | String. Ignorable. |
| `label` | Short plain text. Ignorable. Optional everywhere; for vendor rules it is what a renderer shows. |
| `style` | Cosmetic drawing hints for this rule (section 7). Ignorable. |

**Areas.** A rule that applies to part of the board says where with `area`: the `origin` of a `grid` / `box_grid` rule
in the file (that grid's D × D cells), or a list of cells. The same key means the same thing everywhere it appears
(`neighbours`, `negative`, and the generator spec, [SPEC.md](SPEC.md)).

Number keys: **`sum`** when the clue is a sum of digits (cage, every `sum` kind, sandwich, x-sum, edge kind `sum`),
**`value`** for every other number (difference, ratio, product, whisper gap, skyscraper count, …). Parameters with a
stated default are omitted by canonical writers when they equal the default.

### 5.1 Pair operators

`relation` and `neighbours` use these operator names, with the operator's parameter under its own key, as everywhere
else in the format (`value` for a number, `sum` for a sum):

```json
{"type": "relation", "op": "difference", "value": 3, "pairs": [["r1c1", "r3c3"]]}
{"type": "relation", "op": "any_of", "any_of": [{"op": "sum", "sum": 10}, {"op": "difference", "value": 1}], "pairs": [["r1c1", "r2c3"]]}
```

| `op` | Parameter | The pair `[a, b]` satisfies it when |
|---|---|---|
| `different` | – | a ≠ b |
| `equal` | – | a = b |
| `less` | – | a < b |
| `less_equal` | – | a ≤ b |
| `difference` | `value` k | \|a − b\| = k |
| `not_difference` | `value` k | \|a − b\| ≠ k |
| `not_consecutive` | – | \|a − b\| ≠ 1 |
| `difference_at_least` | `value` k | \|a − b\| ≥ k |
| `difference_at_most` | `value` k | \|a − b\| ≤ k |
| `ratio` | `value` k | a = k·b or b = k·a |
| `not_ratio` | `value` k | neither |
| `sum` | `sum` s | a + b = s |
| `not_sum` | `sum` s | a + b ≠ s |
| `parity_differs` | – | one is odd, the other even |
| `same_third` / `different_third` | – | a and b are / are not in the same third of 1..9 (entropic) |
| `same_mod3` / `different_mod3` | – | a ≡ b / a ≢ b (mod 3) |
| `any_of` | `any_of` [{`op`, parameter}, …] | at least one of the listed operators holds |

`less`, `less_equal` and `any_of` are directional (pair order matters); the others are symmetric.

## 6. Rule families

Each rule family has its own page; the quick reference lists every `type` and `kind` with a link.

- [Houses and regions](rules/houses-and-regions.mdx): 6.1 houses, 6.2 `region`
- [Cages and sums](rules/cages-and-sums.mdx): 6.3 `cage`, 6.8 `sum`
- [Lines and arrows](rules/lines-and-arrows.mdx): 6.4 `line`, 6.5 `arrow`
- [Edges and corners](rules/edges-and-corners.mdx): 6.6 `edge`, 6.7 `corner`
- [Outside clues](rules/outside-clues.mdx): 6.9 `sandwich`, `xsum`, `skyscraper`, `rossini`, `first_seen`
- [Whole-board rules](rules/whole-board-rules.mdx): 6.10 `neighbours`, 6.11 `relation`, 6.14 `negative`
- [Cell clues](rules/cell-clues.mdx): 6.12 `cell`
- [Other rules](rules/other.mdx): 6.13 other families, 6.15 vendor rules, 6.16 what is not a rule, 6.17 reserved
- [Quick reference](rules/quick-reference.mdx): every `type` and `kind` on one page

"Repeats" in the family tables says whether digits may repeat among a rule's cells **because of that rule**; houses still apply.

---

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
  `candidates`, `rules`, `decorations`, `style`.
- Rule key order: `type`, `kind`, then the parameters (`op`, `any_of`, `color`, `letter`, `value`, `sum`, `split`,
  `values`, `digits`, `groups`, `each`, `counts`, `arrow`, `size`, `repeat`, `box`, `where`, `within`, `closed`),
  then `side`, then the cell keys (`origin`, `source`, `bulb`, `lines`, `cells`, `regions`, `segments`, `pairs`,
  `except`), then `id`, `label`, `style`.
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

`solution`, `meta`, `style` and `decorations` never affect it, and neither does the order of rules or of the
engine's houses, so the same puzzle from two importers gets the same fingerprint. It is not symmetry-invariant: a
rotated or relabelled copy has another fingerprint.

### 8.3 Compression for links

For a share link, compress the compact canonical JSON with lz-string `compressToEncodedURIComponent` (as [f-puzzles](https://www.f-puzzles.com/) and
SudokuPad do), or gzip + base64url. Suggested URL parameter: `?pm=<data>`. Compression is transport only: the
decompressed text is a normal `sudoku-puzzle` file.

---

## 9. Examples

Complete example files are on the [examples page](rules/examples.mdx).
