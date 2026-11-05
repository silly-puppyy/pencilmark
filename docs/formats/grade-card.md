---
description: "The sudoku-grade format: every field of a grade card (difficulty, time, band, techniques, steps, issues)."
---

# Grade card

The `sudoku-grade` format, version 1: what a grader reports about one puzzle. The card is separate from the
[puzzle format](puzzle-format.md): it
refers to a puzzle but does not contain it. The key words MUST, MUST NOT, SHOULD and MAY are used as in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

What `rate()` returns and `pencilmark rate --json` prints: one JSON object per puzzle. [JSON Schema](https://json-schema.org/):
[`sudoku-grade.schema.json`](../sudoku-grade.schema.json).

```json
{"format": "sudoku-grade", "format_version": 1,
 "grader": {"name": "pencilmark", "version": "1.1.0"},
 "difficulty": 5.8, "time": 10.7, "band": "Hard",
 "contains": [{"code": "HSI", "chip": "HSI", "name": "Hidden Single", "band": 0},
              {"code": "NSI", "chip": "NSI", "name": "Naked Single", "band": 1},
              {"code": "NPR", "chip": "NPR/HPR", "name": "Naked Pair", "band": 2, "alternatives": ["HPR"], "uses": 1},
              {"code": "XWG", "chip": "XWG/KTE/CSM/MCH", "name": "X-Wing", "band": 3, "alternatives": ["KTE", "CSM", "MCH"], "uses": 1}]}
```

A card exists only for a puzzle with exactly one solution. For any other puzzle, `rate()` raises `NotUnique`,
`NoSolution` or `Undecided`; `rate_many()` and the command line give `{"error": "…"}` in its place (the command line adds
`"line"`, the input line number, to every object).

## 1. Keys

| Key | Field | Type | Meaning |
|---|---|---|---|
| `format`, `format_version` | always | `"sudoku-grade"`, `1` | |
| `grader` | always | `{"name", "version"}` | The engine that made the card. A card is only meaningful with that engine and version. |
| `difficulty` | default | number or null | How hard the puzzle feels; continuous and positive (a nearly finished grid is about 0.2), no ceiling. Hardness, not amount: independent of board size and length, which belong to `time`. Independent of `band`: variants often sit above the classic range for their band. Null when the band is `Unknown`. Exact definition: [Philosophy](../grades/philosophy.md). |
| `time` | default | number or null | Predicted median solving time in minutes over the people who solve puzzles like this one, without long breaks. Null when the band is `Unknown`. |
| `time_mean`, `time_pNN` | optional | number or null | Spread of solve times over today's players: the mean, or the NN-th percentile (`time_p80` = 80% of players finish within it; NN from 1 to 99). Solves without long pauses; a log-normal fitted on two sources' per-player times. |
| `time_dist` | optional | object or null | The time distribution's parameters: `{"type": "lognormal", "sigma_players": …, "sigma_model": …}`, around the median `time`. `sigma_players` is the spread of log solve time over today's players (0.79 for classics and multi-grid layouts, 0.62 for puzzles with any other rule; measured on grandgames and sudoku.coach), which `time_mean` and `time_pNN` use; `sigma_model` is the typical error of the predicted median itself (0.33 / 0.48). |
| `band` | default | string | `"Very Easy"`, `"Easy"`, `"Medium"`, `"Hard"`, `"Very Hard"`, `"Expert"`, `"Extreme"`; `"Unknown"` when the band could not be determined: guessing was allowed and used, or `max_seconds` passed in the difficulty route. The band orders the knowledge a puzzle needs, not its effort: a Hard puzzle can have a lower `difficulty` than a Medium one ([Philosophy](../grades/philosophy.md)). |
| `band_index` | optional | integer or null | 0 (Very Easy) … 6 (Extreme); null for `Unknown`. Handy for sorting, or for mapping the bands to other names. |
| `contains` | default | list | The techniques met on the easiest route, easiest first (section 3). |
| `stopped_at_step` | with `contains`, when human logic ran out | integer | The first step human logic could not make (band `Unknown` with guessing allowed); the `contains` list ends there. |
| `completed` | with `max_seconds` | boolean | True when grading finished within `max_seconds`; absent without a limit (grading then always finishes). False: the limit passed. If it passed in the difficulty route, `band` is `"Unknown"` and `difficulty` / `time` are null, with the techniques found so far in `contains`; if it passed only in the search for the shortest list, the grade stands but the list may not be minimal or may miss alternatives. `max_seconds` bounds the whole call (uniqueness proof, card, technique list); a puzzle whose uniqueness is not proven within it raises `Undecided`. Band `"Unknown"` with `completed` true means human logic ran out (`allow_guessing`). |
| `elapsed` | optional | number | Wall-clock seconds the grader took for this card (for `rate()`: the uniqueness proof plus the card). Machine-dependent; not part of the grade. |
| `issues` | optional | list | Publishing checks (section 4). |
| `reject` | optional | boolean | True when any issue has severity `reject`. |
| `warning` | optional | boolean | True when any issue has severity `warning`. |
| `se` | optional | `{"er", "ep", "ed", "scale"}` or null | Sudoku Explainer-style ratings of the route on the classic SE scale (`scale` is `"classic"`). Null for anything but classic 9×9 sudoku (standard rows, columns and boxes, no other rule), where SE's scale is not defined. |
| `steps` | optional | list | The step-by-step route (section 5). |
| `trace` | optional | list | The route's positions: the board before the first step and after each step (section 6). |
| `describe` | optional | object | The `describe()` output ([How variants are named](../library/variant-naming.md)). |
| `symmetry` | optional | list | Symmetries of the givens pattern, entries as in the generator spec (`{"kind", "axis"?, "of": "givens"}`). |

Numbers are rounded as emitted: `difficulty`, `time`, `time_mean` and `time_pNN` to 1 decimal, the sigmas of
`time_dist` to 2. Two puzzles whose rounded values are equal are not distinguished by the card.

## 2. Choosing fields

`rate(puzzle, fields=[...])` and `--fields a,b,c` take a list of the keys above; only those are computed. A field name
is always the key it produces (`contains` also brings `stopped_at_step`).
Without `fields`, the default fields are returned. `explain=` adds explanations to `steps`, at one or more levels (CLI
`--explain notation,short,teach`; section 5). Shorthands: `steps=True` = the `steps` field with every explanation level;
`se=True` = the `se` field.

## 3. `contains`

Each entry is one technique on the route:

| Key | Meaning |
|---|---|
| `code` | Three-letter technique code ([Techniques](../grades/techniques.md) lists them). |
| `chip` | `code` plus its alternatives, `/`-separated: any one of them gets the solver through at that point. |
| `name` | Technique name. |
| `band` | The technique's band index. |
| `uses` | Times used on the route; omitted for singles (full house, hidden and naked singles, a rule's last cell), whose count depends on the route. |
| `alternatives` | Other codes that also work there; omitted when there are none; `null` when the producer did not search (pencilmark: `alternatives=False`, CLI `--no-alternatives`; band, difficulty and time are the same). |

A full house (`FHS`) is always both a naked and a hidden single, so it is listed under the hidden single (or the naked
single when there is no hidden one) rather than as a chip of its own; `FHS` appears only when no other single is on the
route. Its steps keep the code `FHS`.

## 4. `issues`

The checks run only when the card is asked for `issues` (or `reject`); a default card does not run them.

`{"code", "severity", "text", "rules"?, "ids"?}`. `severity` is `"reject"` (would not be published) or `"warning"`.
`rules`, when present, lists the offending rules as indices into the `rules` array of the puzzle file that was graded
(0-based; for other inputs, of the puzzle as `to_export` writes it); `ids` lists those rules' `id`s where they have one.

Each check can be adjusted with a **quality object** keyed by code. Every entry is an object with `limit` (checks that
have one) and / or `severity` (`"reject"`, `"warning"`, or `"off"` to turn the check off):

```python
pencilmark.rate(puzzle, fields=["issues", "reject", "warning"],
                quality={"trivial": {"limit": 0.5}, "trial": {"severity": "reject"}, "tedious": {"severity": "off"}})
```

CLI: `--quality trivial.limit=0.5,trial.severity=reject,tedious.severity=off`. The generator spec reserves a `quality` block
of the same shape for a later version ([Generator spec](generator-spec.md), section 7).

| Code | Severity when asked for | Meaning | Limit (default) |
|---|---|---|---|
| `spike` | warning | A Medium or harder puzzle whose 3 hardest steps carry more than *limit* of its effort (effort per step as in `difficulty`). | share (0.6) |
| `decorative` | reject | A rule family (for example all the thermometers, or all the white dots) that is neither needed for uniqueness nor used by any step. | – |
| `barely_used` | reject when never used, else warning | A rule family used in fewer than *limit* steps. | steps (3) |
| `redundant` | warning | A rule family the puzzle is unique without, although the solve uses it. | – |
| `trivial` | reject | More than *limit* of the cells are given (0.6 = 60%). | share (0.6) |
| `tedious` | warning | Very Easy or Easy, but over *limit* minutes of routine work. | minutes (60) |
| `uniqueness` | warning | Needs a uniqueness-based technique (relies on assuming one solution). | – |
| `trial` | warning | Needs trial and error or forcing chains. | – |
| `unusual` | reject | A difficulty outside the middle 80% of published puzzles of the same band (classic 9×9 and variants apart; Very Easy has no floor, Extreme no ceiling; [Generate a puzzle](../guides/generator/generate.md#4-typical-difficulty) has the ranges). | – |

The three rule checks look at whole families: one extra dot among needed dots is not reported.

Example: `{"code": "barely_used", "severity": "reject", "text": "thermo lines (rules 3, 4, 5, 6): used in only 0 steps
of the solve", "rules": [3, 4, 5, 6]}`.

## 5. `steps`

Which route the steps walk depends on whether the card asks for the techniques. When it asks for `contains` (or for
`issues`, `reject` or `warning`, which read the technique list), the steps walk the route of the shortest technique list,
so they use exactly the techniques `contains` lists. Without them, the steps walk the full first route: easy to hard,
the simplest technique first, as the band is found. Band, difficulty and time are the same either way.

Each step: `n` (from 1), `code`, `name`, `band` (the same keys as in `contains`), then `placement` (`"r2c8=3"`) and / or `eliminations`
(`["r4c5#7", …]`: candidate 7 removed from r4c5); for regions to find, `region` (`"r4c5@3"`: r4c5 is in region 3) and /
or `region_eliminations` (`["r4c5@!3", …]`: r4c5 is not in region 3), regions numbered so that each region's first
cell in reading order comes before the next region's; and, when requested, `explanation` with the requested levels
(left out on a step that has none of them, such as a step told in one go when only `substeps` was asked for):

| Level | Example |
|---|---|
| `notation` | `X-Wing: 3 r58 c68 => r679c6<>3`: the notation solvers and forums share (HoDoKu's form: technique, digits, pattern, `=>` result; `<>` = "is not") |
| `short` | `r6c6, r7c6, r9c6 ≠ 3: X-Wing on 3 (row 5 and row 8 / column 6 and column 8)`: one plain sentence, result first |
| `teach` | a few sentences: where to look, why it works, what it achieves |

`notation` is always present for a step; `short` and `teach` are left out of a step the explainer could not reconstruct.

A fourth level, `substeps`, is returned only when asked for by name (`explain=["short", "substeps"]`; `explain=True`
gives the three text levels). It tells the step as a list of sub-steps, each a standalone sentence with optional
extras, in the tradition of Sudoku Explainer's and Andrew Stuart's hint pages:

```json
"substeps": [
  {"text": "Colour low digits (1–4) blue and high digits (6–9) yellow.",
   "legend": {"blue": "low (1–4)", "yellow": "high (6–9)"}},
  {"text": "Follow the German whisper from r1c3 (blue): r1c4 yellow, r1c5 blue.",
   "why": "Neighbours on a German whisper differ by at least 5, so a low digit always sits next to a high one (5 can't be on the line).",
   "annotations": [{"id": 1, "cell": "r1c4", "colour": "yellow"}, {"id": 2, "cell": "r1c5", "colour": "blue"}]},
  {"text": "So r1c4 ≠ 1,2,3.",
   "annotations": [{"id": 3, "candidate": "r1c4#1", "colour": "red"}]}
]
```

| Key | Meaning |
|---|---|
| `text` | One sentence that reads on its own, without any drawing. |
| `why` | Optional: the rule fact behind the sentence (given once per step). |
| `legend` | Optional: what a colour name stands for; it holds for the rest of the solve. |
| `annotations` | Optional drawing elements, each with an integer `id`: colour a `cell` or a `candidate` (`colour`), show a `digit` (`"r5c6=7"`), or an `arrow` between two cells or candidates (`line`: `strong`, `weak` or `plain`). A later element on the same target replaces the earlier one. |

Colours are names from a named palette (`yellow`, `blue`, `green`, `purple`, `orange`, `pink`, `cyan`, `grey`, `brown`;
`red` for removals); each renderer picks its own shade for each name. Steps whose technique has no sub-step form yet leave
`substeps` out; so far: locked candidates (pointing, claiming), naked and hidden subsets, line rules (thermo, whispers, renban, ...), low / high and odd / even colouring,
simple colouring, regions to find (each region keeps one colour for the whole solve), killer cage combinations, fish (X-Wing, Swordfish, Jellyfish, finned), XY- and XYZ-Wings, and single chains (X-Chain, XY-Chain, AIC and the
short chains such as Skyscraper and 2-String Kite; strong links drawn as `strong` arrows, weak ones as `weak`).

## 6. `trace`

The positions of the route that `steps` lists, so a viewer can show the board at any step: `trace[0]` is the
position before step 1 and `trace[n]` the position after step n (one more entry than `steps`). Each position is
written as the puzzle file writes a board:

```json
{"digits": [0, 0, 0, 0, 4, 0, 8, 0, 3, …], "candidates": {"r1c1": [1, 5, 7], "r1c2": [1, 2, 5, 7], …}}
```

- `digits`: one entry per cell in reading order, the placed digit or 0 (givens and digits placed so far).
- `candidates`: every empty cell's remaining candidates, ascending, keys in reading order.
- `marks` (optional): what a casual solver would have written down at this position, for the cells that carry marks:
  `corner` = position notes (a digit with 2 or 3 places left in its box, noted once, from the start), `centre` =
  candidate lists (written when the route first needs notes, in the cells with at most 3 candidates, then in each cell
  a step uses). Marks always show a subset of the cell's `candidates`; a viewer may draw them instead of the full
  candidates. Present when the grader's note model is on (the default).
- `colours` (optional): the identity colours an expert would have painted at this position, as a list of
  `{"colour": "green", "cells": ["r3c7", …], "digits": [7, 8], "opposite": "purple"}`. Every cell of one colour holds
  the same digit, one of `digits`; the `opposite` colour holds the other one (which is which is still open). Colours
  start where two cells of one house have exactly the same two candidates and are tracked further: in a house without
  the colour, the one cell left that can hold it joins it; cells a palindrome or clone rule makes equal share it. A
  pair seen only in its two starting cells is left out (the candidates already show it), and at most three colour
  pairs are listed, the largest. A colour keeps its name while it lasts. Present when the grader's colour model is on
  (the default).

The first position is each empty cell's possible digits less those its peers' givens rule out; a step's placement
then clears its digit from the cell's peers and its eliminations remove candidates. Steps that only add a pencil mark
or a region label leave the digits and candidates unchanged. Drawing for a step is in its `substeps` (section 5).

## 7. Implementing a subset

Only `format`, `format_version` and `grader` are required; every other key is present only when it was asked for
(section 2). A producer MAY therefore emit just the headline numbers, for example `difficulty`, `time` and `band`, and a
consumer that needs only those MAY ignore every other key. A consumer MUST NOT compare cards from different `grader`
names or versions as if they were on one scale.
