# Generator spec: `sudoku-spec`, format_version 1

A request to a puzzle generator. It reuses the vocabulary of the puzzle format ([FORMAT.md](FORMAT.md)) and the keys
of the grade card ([GRADE.md](GRADE.md)). Version 1 contains exactly what pencilmark's generator runs
(`pencilmark.generate(spec)`); the parts planned for later versions are listed in section 7 and refused today. Example
specs: [examples/specs](examples/specs/README.md).

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

`board`, `digits` and the house rules as in the puzzle format, restricted to one gap-free D × D grid with standard
boxes (D = 4, 6, 8, 9, 10, 12, 16): a single `box_grid` rule. It is copied into the result.

## 2. Templates

A rule with `count` and no cells is a **template**: the generator places rules of that family.

| Template | Varieties |
|---|---|
| `{"type": "cage"}` | killer cages |
| `{"type": "line", "kind": "thermo" \| "whisper" \| "renban" \| "between"}` | whisper gap: the default (5 on 9 × 9) |
| `{"type": "arrow"}` | |
| `{"type": "edge", "kind": "kropki"}` | `"color": "white" \| "black"` for one colour |
| `{"type": "edge", "kind": "xv"}` | `"letter": "X" \| "V"` for one letter |
| `{"type": "cell", "kind": "odd" \| "even"}` | |

One template per variety, each with its own `count`:

| `count` | Meaning |
|---|---|
| n | exactly n of them in the result |
| [min, max] | between min and max; `max` `null` = no cap |
| `"auto"` | allowed, as many as the puzzle needs (possibly none) |
| `"all"` | kropki only: every true dot drawn, with the matching `negative` (no dot = neither relation) |
| `"min"` | kropki only: a minimal set of dots |
| `"tile"` | cages only: the grid tiled by cages |

## 3. Givens and symmetry

- `givens`: `{"count": n}` or `{"count": [min, max]}` (`max` may be `null`). Without it, the generator digs as far as
  the targets allow.
- `symmetry`: at most one entry, `{"kind": "rot180" | "rot90" | "mirror", "axis"?: "horizontal" | "vertical" |
  "diagonal" | "antidiagonal", "of": "givens"}`. The same entries are reported by `describe()` and the `symmetry` card
  field.

## 4. Targets: `where`

Conditions on the result's card, using the card's keys ([GRADE.md](GRADE.md)):

| Key | Value |
|---|---|
| `band` | one band name |
| `difficulty` | `[lo, hi]` |
| `contains` | technique codes that must appear in `contains`; `{"codes": [...], "strict": true}` = as the code itself, not only as an alternative in a chip |
| `elements` | `{"max": n}`: at most n placed rule elements in total |

## 5. Limits, fields and program data

- `limits`: `time` (seconds for the whole run, default 120), `seed` (reproducible runs, default 1). The run returns one
  puzzle or fails with the reason after `time`.
- `fields`: which card fields to return with the result ([GRADE.md](GRADE.md)); default fields without it.
- `meta`: free information as in the puzzle format. pencilmark reads its own knobs from
  `meta["io.github.silly-puppyy.pencilmark"]`: `{"solver": "logic" | "cpsat", "grade_seconds": s}`.

A part of a request the generator cannot meet in time is never ignored: the run fails and says why.

## 6. Fingerprint

`sha256:` of the canonical JSON of `board`, `digits`, `givens`, `rules`, `symmetry` and `where` (the parts that decide
which puzzles qualify; `meta`, `limits` and `fields` do not).

## 7. Reserved for later versions

Refused by format_version 1 readers with a message naming the part:

- other boards: multi-grid layouts, jigsaw boxes, locked clue rules (rules with cells), `"lock": false` starting points;
- givens in puzzle form, `mask`, `values` (locked digits);
- template shape limits: `size`, `length`, `displaced`, `area`; other whisper gaps;
- more symmetry entries, symmetry of rules (`of: "all"` or a rule selector);
- targets: a list of bands, `difficulty` `"max"` / `"min"` (best-so-far search), `time`, `issues`, `not_contains`,
  `contains` `only` / `uses`, per-area targets;
- `quality` (the publishing checks applied as targets);
- `limits.results` above 1 and `limits.attempts`.
