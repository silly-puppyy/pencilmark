---
description: "The pencilmark-spec format: a request to the puzzle generator (board, rules, givens, symmetry, targets)."
---

# Generator spec

The `pencilmark-spec` format, version 1: a request to a puzzle generator. It reuses the vocabulary of the
[puzzle format](puzzle-format.md) and the keys of the [grade card](grade-card.md). Version 1 contains exactly what pencilmark's generator runs
(`pencilmark.generate(spec)`); the parts planned for later versions are listed in section 7 and refused today. Example
specs: [Generator examples](../guides/generator/generator-examples.mdx).

A request **is a puzzle file with blanks**: the same envelope and rule vocabulary, its own `format` (no puzzle reader
mistakes it for a puzzle), plus blocks that say what the result must satisfy and how long to try.

```json
{"format": "pencilmark-spec", "format_version": 1,
 "meta": {"title": "{type:list} #{seed}", "subtitle": "{band}, {difficulty}", "author": "Your name",
          "type": {"scheme": "list"}, "variants": true, "rules_text": true,
          "fingerprint": true, "generated_from": true},
 "board": {"rows": 9, "cols": 9},
 "digits": 9,
 "givens": {"count": 2},
 "rules": [
  {"type": "box_grid", "box": [3, 3], "count": [3, 3]},
  {"type": "cage", "count": [1, null]},
  {"type": "line", "kind": "whisper", "count": [1, null]}],
 "where": {"band": "Hard"},
 "quality": {"preset": "standard"},
 "limits": {"seconds": 900, "seed": 4},
 "fields": ["difficulty", "time", "band", "contains", "issues"]}
```

The result is an ordinary `pencilmark-puzzle` with its `solution`. Its `meta` is the spec's: every key is optional,
copied as written, and a few are requests the generator fills in (section 5.1). This one took about eleven minutes and came back with
`"title": "Killer German Whispers Sudoku #4"`, `"subtitle": "Hard, 9.0"`, `"type": "Killer German Whispers Sudoku"`,
`"variants": ["killer", "german_whispers"]`, the rules in words and both fingerprints; its card has no issues.

## 1. Board

`board`, `digits` and the house rules as in the puzzle format, copied into the result. Either one gap-free D × D grid
with standard boxes (D = 4, 6, 8, 9, 10, 12, 16; a single `box_grid` rule), or a named layout of overlapping 9 × 9
grids: one `box_grid` rule per grid, at the origins of samurai, super-samurai, twodoku, doubledoku, butterfly, sohei,
windmill, flower-4, tridoku, wing-3, sensei, shogun, sumo, twins, clueless-1 or clueless-2 (the board is their extent).

Rules with cells and no `count` are **locked**: every result carries them and its solution respects them. The
generator takes rules of different digits (`region` kinds `diagonal`, `extra` and `window`; `neighbors` kinds
`antiknight` and `antiking`) and pair rules on neighbors: the `neighbors` kind `nonconsecutive`, or any `op` with
`step` (written back in canonical form: "no two orthogonal neighbors sum to 10" is the `negative` rule of X marks). Without a `where.band`, a layout's result is at most Hard, even with `"difficulty": "max"` (digging with every
technique is slow on hundreds of cells); `info.warnings` says so. A super samurai with X diagonals on its top three grids is eight `box_grid` rules and six
`region` `diagonal` rules.

## 2. Templates

A rule with `count` and no cells is a **template**: the generator places rules of that family.

| Template | Varieties |
|---|---|
| `{"type": "cage"}` | killer cages |
| `{"type": "line", "kind": "thermo" \| "slow_thermo" \| "whisper" \| "renban" \| "between" \| "entropic" \| "modular" \| "parity" \| "palindrome" \| "zipper" \| "region_sum" \| "lockout" \| "double_arrow"}` | the default parameters: whisper gap 5 and lockout gap 4 on 9 × 9; entropic groups (boards of 6 × 6 and up); modular mod 3. Palindromes and zippers have an odd length (built from their center); double arrows are 5 cells or more (a shorter one is a zipper) |
| `{"type": "arrow"}` | |
| `{"type": "quadruple"}`, `{"type": "corner", "kind": "mathrax"}` | corner clues on a 2 × 2 block: a quadruple shows all four digits or three of them; a mathrax clue is whichever operator holds on both diagonals (`sum`, `difference`, `product`, `ratio`, or all `even` / `odd`) |
| `{"type": "sandwich" \| "xsum" \| "skyscraper"}`, `{"type": "sum", "kind": "little_killer"}` | outside clues on single grids (not layouts): a whole row or column (a diagonal for little killers) read from either end |
| `{"type": "edge", "kind": "kropki"}` | `"color": "white" \| "black"` for one color |
| `{"type": "edge", "kind": "xv"}` | `"letter": "X" \| "V"` for one letter |
| `{"type": "cell", "kind": "odd" \| "even" \| "parity"}` | `"parity"`: odd or even cells, either kind |

One template per variety, each with its own `count`:

| `count` | Meaning |
|---|---|
| n | exactly n of them in the result |
| [min, max] | between min and max; `max` `null` = no cap |
| `"auto"` | allowed, as many as the puzzle needs (possibly none) |
| `"all"` | kropki only: every true dot drawn, with the matching `negative` (no dot = neither relation) |
| `"min"` | kropki only: a minimal set of dots |
| `"tile"` | cages only: every cell that is not a given is in a cage; a cell left alone becomes a given when the request allows givens |
| `"max"` | as many as fit: the run uses its whole `limits.seconds` and returns the result with the most of them |

Elements of one kind never share cells (two cages, two whispers); elements of different kinds may, so the rules
interact (a whisper through a cage, a dot on a thermo). Dots and XV marks may share cells, never an edge.

Shape limits, each a number or `[min, max]` (`max` `null` = no cap):

| Key | Templates | Meaning |
|---|---|---|
| `size` | cage | cells per cage |
| `sum` | cage | the cage total |
| `length` | line, arrow | cells per line; for an arrow, cells in the shaft (the circle not counted) |
| `turns` | line | direction changes along the line (`0` = straight; a diagonal step after an orthogonal one counts). Human-set lines turn at about half their inner cells; the generator draws its lines to match. |

```json
{"type": "cage", "sum": 10, "count": "max"}
{"type": "line", "kind": "whisper", "length": [12, null], "count": 1}
{"type": "line", "kind": "thermo", "length": [4, 6], "turns": [0, 1], "count": 3}
```

With `"tile"` or a zero-given cage count, the tiling keeps to them: no cage is built over a maximum, cages under a
minimum are merged first, and a tiling that leaves one under is drawn again (`{"type": "cage", "count": "tile",
"sum": [null, 20]}` caps every cage at 20). The tiling starts from 2-cell cages, so maxima and sum ranges come about
as fast as no limit (a 9 × 9 Hard tiling: 16 a minute without limits, 38 with `sum` at most 20, 26 with `sum`
`[8, 18]` and `size` `[2, 4]`), and a minimum `size` above 2 tiles at that size and adds givens until the logic solves
it (a few, dug back out where not needed; a request allowing no givens cannot): such killers come out Medium or
easier (Hard size-3+ tilings are not found yet).

## 3. Givens and symmetry

- `givens`: `{"count": n}` or `{"count": [min, max]}` (`max` may be `null`). Without it, the generator digs as far as
  the targets allow. On a layout, `"grids": [...]` bounds each grid's givens (a number or `[min, max]` per grid, the
  grids in reading order of their origins; a shared cell counts for both grids): more givens on one side makes that
  side easier.
- `symmetry`: at most one entry, `{"kind": "rot180" | "rot90" | "mirror", "axis"?: "horizontal" | "vertical" |
  "diagonal" | "antidiagonal", "of"?: "givens"}` (`of` may be left out: `givens` is its default and, in version 1,
  its only value). `rot90` and the diagonal mirrors need square boxes (4×4, 9×9, 16×16);
  on other boards the request is refused. The same entries are reported by `describe()` and the `symmetry` card field.

## 4. Targets: `where`

Conditions on the result's card, using the card's keys ([Grade card](grade-card.md)):

| Key | Value |
|---|---|
| `band` | one band name |
| `difficulty` | `[lo, hi]` (the run aims at a point drawn in the range, `info.aimed_at`, so results spread over it; after half of `limits.seconds` any difficulty in the range will do); or `"max"` / `"min"`: the hardest / easiest result found in `limits.seconds` (the run uses all of it); or `"typical"` (with a band, 9×9): aim at a window drawn from the seed where published puzzles of the band lie, reported in `info.aimed_at`; it is a preference, so with nothing in the window by half of `limits.seconds` any difficulty in the band will do (`info.aim_relaxed`). Without `difficulty` the generator digs as far as the band allows |
| `contains` | technique codes the puzzle needs: each is an entry of the card's `contains` with no `alternatives` (no other technique gets through at that point) |
| `elements` | `{"max": n}`: at most n placed rule elements in total |

### 4.1 Publishing checks: `quality`

`quality` (top level) is opt in: without it, or with `{}`, no check runs (a canonical writer drops `{}`). With it, a
candidate that gets an issue of severity `reject` is not returned, the run's `info.rejected` counts the candidates
each check refused, and `info.issues` lists what the checks found on the returned puzzle (warnings). The object means
what it means in `rate()`: the checks, their limits and the presets are those of the grade card
([Grade card](grade-card.md), section 4).

- `"preset": "standard"` turns on the standard set, each at severity `reject`: `decorative`, `trivial`, `trial`,
  `thin` and `unusual`. The preset is the only thing that turns on checks you do not name.
- `"preset": "relaxed"` turns on the same five, but only `decorative`, `trivial` and `trial` reject; `thin` and
  `unusual` become warnings in `info.issues`. Published puzzles fail `unusual` by design about one time in five
  (it marks the outer fifth of each band), so `standard` refuses some puzzles a setter would publish; `relaxed`
  refuses 0.1% of published classics and 4% of variants (`standard`: 14% and 17%).
- A check named next to the preset adjusts it: `{"preset": "standard", "thin": {"limit": 0.2}}` relaxes `thin`,
  `{"preset": "standard", "trivial": {"severity": "off"}}` drops `trivial` (a learner's first puzzle may well be
  mostly given).
- Without a preset, only the checks named run: `{"trial": {"severity": "reject"}}` refuses puzzles that need trial
  or forcing and nothing else. A named check without a `severity` runs at its own (grade card, section 4).

## 5. Limits, fields and program data

- `limits`: `seconds` (for the whole run, default 120), `seed` (the same seed and request give the same puzzle;
  without one each run draws a fresh seed, reported in `info.seed`), `grade_seconds` (how long each candidate may be
  graded, default 60; the returned puzzle's card is always graded in full) and `solver` (`"logic"`, the default: every
  step is solvable by human logic within the band, so the puzzle is unique by construction; or `"cpsat"`: uniqueness
  only, for minimal kropki). The run returns one puzzle or fails with the reason after
  `seconds`; an attempt still digging when the time is up is given up. Grading the returned puzzle in full comes on
  top.
- `fields`: which card fields to return with the result ([Grade card](grade-card.md)); default fields without it.
- `meta`: copied to the puzzle, with the requests of 5.1 filled in.

A part of a request the generator cannot meet in time is never ignored: the run fails and says why.

### 5.1 Metadata: `meta`

Everything in `meta` is optional and copied to the puzzle ([Puzzle format](puzzle-format.md) 2.1 lists the common
keys). These keys are requests, filled in from the result; nothing is filled unless asked:

| Key | Request | Filled with |
|---|---|---|
| `title`, `subtitle` | a text, with fields in braces | the text with its fields filled: `{type}` (the variant name; `{type:list}` in the `list` scheme), `{variants}` (the variant names, comma-separated), `{size}` (`9x9`), `{band}`, `{difficulty}`, `{time}` (minutes), `{givens}` (their count), `{seed}`. `{{` and `}}` are literal braces; a text without fields is copied |
| `type` | `true`, or `{"scheme": "name" \| "list"}` | the variant name ([How variants are named](../library/variant-naming.md)): `name` (the default) is one variant's name or "Variant" for two or more (`"Variant Sudoku"`); `list` names every variant (`"Jigsaw Killer Renban Kropki Sudoku"`). A text is copied |
| `variants` | `true` | the variants as snake_case ids, like tags (`["killer", "german_whispers"]`). A list is copied |
| `rules_text` | `true` | the rules in words, one line per variant. A text (the setter's own) is copied |
| `fingerprint` | `true` | the puzzle's [fingerprint](puzzle-format.md#82-fingerprint) |
| `generated_from` | `true` | the spec's fingerprint (section 6) |

An unknown field or scheme fails the request before the run.

## 6. Fingerprint

The SHA-256 (64 lowercase hex digits) of the canonical JSON of `board`, `digits`, `givens`, `rules`, `symmetry`, `where` and `quality` (the parts that decide
which puzzles qualify; `meta`, `limits` and `fields` do not).

## 7. Reserved for later versions

Refused by format_version 1 readers with a message naming the part:

- other boards: layouts that are not named, jigsaw boxes, locked rules other than those of different digits, `"lock":
  false` starting points;
- givens in puzzle form, `mask`, `values` (locked digits);
- template shape limits `displaced` and `area`; other whisper gaps;
- more symmetry entries, symmetry of rules (`of: "all"` or a rule selector);
- targets: a list of bands, `time`, `issues`, `not_contains`, per-area targets;
- `limits.results` above 1 and `limits.attempts`.
