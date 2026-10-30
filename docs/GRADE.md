# Grade card: `sudoku-grade`, format_version 1

What a grader reports about one puzzle. The card is separate from the puzzle format ([FORMAT.md](FORMAT.md)): it
refers to a puzzle but does not contain it. The key words MUST, MUST NOT, SHOULD and MAY are used as in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

What `rate()` returns and `pencilmark rate --json` prints: one JSON object per puzzle. [JSON Schema](https://json-schema.org/):
[`sudoku-grade.schema.json`](sudoku-grade.schema.json).

```json
{"format": "sudoku-grade", "format_version": 1,
 "grader": {"name": "pencilmark", "version": "1.0.0"},
 "difficulty": 5.9, "time": 10.7, "band": "Hard",
 "contains": [{"code": "HSI", "chip": "HSI", "name": "Hidden Single", "band": 0},
              {"code": "NPR", "chip": "NPR/HPR", "name": "Naked Pair", "band": 2, "uses": 1, "alternatives": ["HPR"]},
              {"code": "XWG", "chip": "XWG/KTE/SCL", "name": "X-Wing", "band": 3, "uses": 1, "alternatives": ["KTE", "SCL"]}]}
```

A card exists only for a puzzle with exactly one solution. For any other puzzle, `rate()` raises `NotUnique`,
`NoSolution` or `Undecided`; `rate_many()` and the command line give `{"error": "…"}` in its place (the command line adds
`"line"`, the input line number, to every object).

## 1. Keys

| Key | Field | Type | Meaning |
|---|---|---|---|
| `format`, `format_version` | always | `"sudoku-grade"`, `1` | |
| `grader` | always | `{"name", "version"}` | The engine that made the card. A card is only meaningful with that engine and version. |
| `difficulty` | default | number or null | How hard the puzzle feels; continuous from 0 (one empty cell), no ceiling. Hardness, not amount: independent of board size and length, which belong to `time`. Independent of `band`: variants often sit above the classic range for their band. Null when the band is `Unknown`. Exact definition: [PHILOSOPHY.md](PHILOSOPHY.md). |
| `time` | default | number or null | Predicted median solving time in minutes over the people who solve puzzles like this one, without long breaks. Null when the band is `Unknown`. |
| `time_mean`, `time_pNN` | optional | number or null | Spread of solve times over today's players: the mean, or the NN-th percentile (`time_p80` = 80% of players finish within it; NN from 1 to 99). Solves without long pauses; a log-normal fitted on two sources' per-player times. |
| `time_dist` | optional | object or null | The time distribution's parameters: `{"type": "lognormal", "sigma_players": …, "sigma_model": …}`, around the median `time`. `sigma_players` is the spread of log solve time over today's players (0.79 for classics and multi-grid layouts, 0.62 for puzzles with any other rule; measured on grandgames and sudoku.coach), which `time_mean` and `time_pNN` use; `sigma_model` is the typical error of the predicted median itself (0.33 / 0.48). |
| `band` | default | string | `"Very Easy"`, `"Easy"`, `"Medium"`, `"Hard"`, `"Very Hard"`, `"Expert"`, `"Extreme"`; `"Unknown"` when the band could not be determined: guessing was allowed and used, or `max_seconds` passed in the difficulty route. The band orders the knowledge a puzzle needs, not its effort: a Hard puzzle can have a lower `difficulty` than a Medium one (PHILOSOPHY.md). |
| `band_index` | optional | integer or null | 0 (Very Easy) … 6 (Extreme); null for `Unknown`. Handy for sorting, or for mapping the bands to other names. |
| `contains` | default | list | The techniques met on the easiest route, easiest first (section 3). |
| `stopped_at_step` | with `contains`, when human logic ran out | integer | The first step human logic could not make (band `Unknown` with guessing allowed); the `contains` list ends there. |
| `completed` | with `max_seconds` | boolean | True when grading finished within `max_seconds`; absent without a limit (grading then always finishes). False: the limit passed. If it passed in the difficulty route, `band` is `"Unknown"` and `difficulty` / `time` are null, with the techniques found so far in `contains`; if it passed only in the search for the shortest list, the grade stands but the list may not be minimal or may miss alternatives. `max_seconds` bounds the whole call (uniqueness proof, card, technique list); a puzzle whose uniqueness is not proven within it raises `Undecided`. Band `"Unknown"` with `completed` true means human logic ran out (`allow_guessing`). |
| `elapsed` | optional | number | Wall-clock seconds the grader took for this card (for `rate()`: the uniqueness proof plus the card). Machine-dependent; not part of the grade. |
| `issues` | optional | list | Publishing checks (section 4). |
| `reject` | optional | boolean | True when any issue has severity `reject`. |
| `warning` | optional | boolean | True when any issue has severity `warning`. |
| `se` | optional | `{"er", "ep", "ed", "scale"}` or null | Sudoku Explainer-style ratings of the route on the classic SE scale (`scale` is `"classic"`). Meaningful for classic sudoku only. |
| `steps` | optional | list | The step-by-step route (section 5). |
| `describe` | optional | object | The `describe()` output ([NAMING.md](NAMING.md)). |
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
| `code` | Three-letter technique code (USAGE.md lists them). |
| `chip` | `code` plus its alternatives, `/`-separated: any one of them gets the solver through at that point. |
| `name` | Technique name. |
| `band` | The technique's band index. |
| `uses` | Times used on the route; omitted for singles (full house, hidden and naked singles, a rule's last cell), whose count depends on the route. |
| `alternatives` | Other codes that also work there; omitted when there are none; `null` when the producer did not search (pencilmark: `alternatives=False`, CLI `--no-alternatives`; band, difficulty and time are the same). |

## 4. `issues`

`{"code", "severity", "text", "rules"?, "ids"?}`. `severity` is `"reject"` (would not be published) or `"warning"`.
`rules`, when present, lists the offending rules as indices into the `rules` array of the puzzle file that was graded
(0-based; for other inputs, of the puzzle as `to_export` writes it); `ids` lists those rules' `id`s where they have one.

Each check can be adjusted with a **quality object** keyed by code. Every entry is an object with `limit` (checks that
have one) and / or `severity` (`"reject"`, `"warning"`, or `"off"` to turn the check off):

```python
rate(puzzle, fields=["issues", "reject", "warning"],
     quality={"trivial": {"limit": 0.5}, "trial": {"severity": "reject"}, "tedious": {"severity": "off"}})
```

CLI: `--quality trivial.limit=0.5,trial.severity=reject,tedious.severity=off`. The generator spec's `quality`
([SPEC.md](SPEC.md)) is the same object.

| Code | Default severity | Meaning | Limit (default) |
|---|---|---|---|
| `spike` | warning | A Medium or harder puzzle whose 3 hardest steps carry more than *limit* of its effort (effort per step as in `difficulty`). | share (0.6) |
| `decorative` | reject | A rule that is neither needed for uniqueness nor used by any step. | – |
| `barely_used` | reject when never used, else warning | A rule used in fewer than *limit* steps. | steps (3) |
| `redundant` | warning | A rule the puzzle is unique without, although the solve uses it. | – |
| `trivial` | reject | More than *limit* of the cells are given (0.6 = 60%). | share (0.6) |
| `tedious` | warning | Very Easy or Easy, but over *limit* minutes of routine work. | minutes (60) |
| `uniqueness` | warning | Needs a uniqueness-based technique (relies on assuming one solution). | – |
| `trial` | warning | Needs trial and error or forcing chains. | – |

Example: `{"code": "barely_used", "severity": "reject", "text": "thermo lines (rules 3, 4, 5, 6): used in only 0 steps
of the solve", "rules": [3, 4, 5, 6]}`.

## 5. `steps`

Each step: `n` (from 1), `code`, `name`, `band` (the same keys as in `contains`), then `placement` (`"r2c8=3"`) and / or `eliminations`
(`["r4c5#7", …]`: candidate 7 removed from r4c5), and, when requested, `explanation` with the requested levels:

| Level | Example |
|---|---|
| `notation` | `X-Wing: 3 r58 c68 => r679c6<>3`: the notation solvers and forums share (HoDoKu's form: technique, digits, pattern, `=>` result; `<>` = "is not") |
| `short` | `r6c6, r7c6, r9c6 ≠ 3: X-Wing on 3 (row 5 and row 8 / column 6 and column 8)`: one plain sentence, result first |
| `teach` | a few sentences: where to look, why it works, what it achieves |

`notation` is always present for a step; `short` and `teach` are left out of a step the explainer could not reconstruct.

## 6. Implementing a subset

Only `format`, `format_version` and `grader` are required; every other key is present only when it was asked for
(section 2). A producer MAY therefore emit just the headline numbers, for example `difficulty`, `time` and `band`, and a
consumer that needs only those MAY ignore every other key. A consumer MUST NOT compare cards from different `grader`
names or versions as if they were on one scale.
