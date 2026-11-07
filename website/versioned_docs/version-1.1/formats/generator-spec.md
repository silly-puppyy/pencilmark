---
description: "The sudoku-spec format: a request to the puzzle generator (board, rules, givens, symmetry, targets)."
---

# Generator spec

The `sudoku-spec` format, version 1: a request to a puzzle generator. It reuses the vocabulary of the
[puzzle format](puzzle-format.md) and the keys of the [grade card](grade-card.md). Version 1 contains exactly what pencilmark's generator runs
(`pencilmark.generate(spec)`); the parts planned for later versions are listed in section 7 and refused today. Example
specs: [Generator examples](../guides/generator/generator-examples.mdx).

A request **is a puzzle file with blanks**: the same envelope and rule vocabulary, its own `format` (no puzzle reader
mistakes it for a puzzle), plus blocks that say what the result must satisfy and how long to try.

```json
{"format": "sudoku-spec", "format_version": 1,
 "meta": {"title": "Killer with whispers"},
 "board": {"rows": 9, "cols": 9},
 "digits": 9,
 "givens": {"count": [0, 2]},
 "rules": [
  {"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
  {"type": "cage", "count": "auto"},
  {"type": "line", "kind": "whisper", "count": [2, null]}],
 "symmetry": [{"kind": "rot180", "of": "givens"}],
 "where": {"band": "Hard", "difficulty": [6.5, 9]},
 "limits": {"time": 300, "seed": 42},
 "fields": ["difficulty", "time", "band", "contains"]}
```

The result is an ordinary `sudoku-puzzle` with its `solution`; `meta.generated_from` carries the spec's fingerprint
(section 6), and `meta` of the spec (title, author, ...) is copied to it.

## 1. Board

`board`, `digits` and the house rules as in the puzzle format, copied into the result. Either one gap-free D × D grid
with standard boxes (D = 4, 6, 8, 9, 10, 12, 16; a single `box_grid` rule), or a named layout of overlapping 9 × 9
grids: one `box_grid` rule per grid, at the origins of samurai, super-samurai, twodoku, doubledoku, butterfly, sohei,
windmill, flower-4, tridoku, wing-3, sensei, shogun, sumo, twins, clueless-1 or clueless-2 (the board is their extent).

Rules with cells and no `count` are **locked**: every result carries them and its solution respects them. The
generator takes rules of different digits: `region` kinds `diagonal`, `extra` and `window`, and `neighbours` kinds
`antiknight` and `antiking`. Without a `where.band`, a layout's result is at most Hard (digging with every technique
is slow on hundreds of cells). A super samurai with X diagonals on its top three grids is eight `box_grid` rules and six
`region` `diagonal` rules.

## 2. Templates

A rule with `count` and no cells is a **template**: the generator places rules of that family.

| Template | Varieties |
|---|---|
| `{"type": "cage"}` | killer cages |
| `{"type": "line", "kind": "thermo" \| "whisper" \| "renban" \| "between"}` | whisper gap: the default (5 on 9 × 9) |
| `{"type": "arrow"}` | |
| `{"type": "edge", "kind": "kropki"}` | `"color": "white" \| "black"` for one colour |
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
| `"max"` | as many as fit: the run uses its whole `limits.time` and returns the result with the most of them |

Elements of one kind never share cells (two cages, two whispers); elements of different kinds may, so the rules
interact (a whisper through a cage, a dot on a thermo). Dots and XV marks may share cells, never an edge.

Shape limits, each a number or `[min, max]` (`max` `null` = no cap):

| Key | Templates | Meaning |
|---|---|---|
| `size` | cage | cells per cage |
| `sum` | cage | the cage total |
| `length` | line, arrow | cells per line; for an arrow, cells in the shaft (the circle not counted) |

```json
{"type": "cage", "sum": 10, "count": "max"}
{"type": "line", "kind": "whisper", "length": [12, null], "count": 1}
```

Shape limits do not combine with `"tile"` or with a zero-given cage count.

## 3. Givens and symmetry

- `givens`: `{"count": n}` or `{"count": [min, max]}` (`max` may be `null`). Without it, the generator digs as far as
  the targets allow. On a layout, `"grids": [...]` bounds each grid's givens (a number or `[min, max]` per grid, the
  grids in reading order of their origins; a shared cell counts for both grids): more givens on one side makes that
  side easier.
- `symmetry`: at most one entry, `{"kind": "rot180" | "rot90" | "mirror", "axis"?: "horizontal" | "vertical" |
  "diagonal" | "antidiagonal", "of": "givens"}`. `rot90` and the diagonal mirrors need square boxes (4×4, 9×9, 16×16);
  on other boards the request is refused. The same entries are reported by `describe()` and the `symmetry` card field.

## 4. Targets: `where`

Conditions on the result's card, using the card's keys ([Grade card](grade-card.md)):

| Key | Value |
|---|---|
| `band` | one band name |
| `difficulty` | `[lo, hi]`, or `"max"` / `"min"`: the hardest / easiest result found in `limits.time` (the run uses all of it) |
| `contains` | technique codes that must appear in `contains`; `{"codes": [...], "strict": true}` = as the code itself, not only as an alternative in a chip |
| `elements` | `{"max": n}`: at most n placed rule elements in total |

`quality` (top level, recommended) filters candidates by the publishing checks of the grade card: one with an issue of
severity reject is not returned, and the run's `info.rejected` counts the candidates refused, by check. `"quality": {}`
applies the default checks; an object adjusts them as [`rate(quality=...)`](grade-card.md) does:
`{"trivial": {"limit": 0.45}}` refuses puzzles with more than 45% of the cells given, `{"spike": {"severity":
"reject"}}` those whose effort sits in a few steps, `{"trivial": {"severity": "off"}}` turns a check off (a learner's
first puzzle may well be mostly given). Without `quality` no candidate is filtered.

## 5. Limits, fields and program data

- `limits`: `time` (seconds for the whole run, default 120), `seed` (reproducible runs, default 1). The run returns one
  puzzle or fails with the reason after `time`; an attempt still digging when the time is up is given up. Grading the
  returned puzzle in full comes on top.
- `fields`: which card fields to return with the result ([Grade card](grade-card.md)); default fields without it.
- `meta`: free information as in the puzzle format. pencilmark reads its own knobs from
  `meta["io.github.silly-puppyy.pencilmark"]`: `{"solver": "logic" | "cpsat", "grade_seconds": s}` (`grade_seconds`:
  how long each candidate may be graded, default 60; the returned puzzle's card is always graded in full).

A part of a request the generator cannot meet in time is never ignored: the run fails and says why.

## 6. Fingerprint

`sha256:` of the canonical JSON of `board`, `digits`, `givens`, `rules`, `symmetry`, `where` and `quality` (the parts that decide
which puzzles qualify; `meta`, `limits` and `fields` do not).

## 7. Reserved for later versions

Refused by format_version 1 readers with a message naming the part:

- other boards: layouts that are not named, jigsaw boxes, locked rules other than those of different digits, `"lock":
  false` starting points;
- givens in puzzle form, `mask`, `values` (locked digits);
- template shape limits `displaced` and `area`; other whisper gaps;
- more symmetry entries, symmetry of rules (`of: "all"` or a rule selector);
- targets: a list of bands, `time`, `issues`, `not_contains`,
  `contains` `only` / `uses`, per-area targets;
- `limits.results` above 1 and `limits.attempts`.
