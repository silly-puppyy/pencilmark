# Grade card: `sudoku-grade`, format_version 1

What a grader reports about one puzzle. The card is separate from the puzzle format ([FORMAT.md](FORMAT.md)): it
refers to a puzzle but does not contain it. The key words MUST, MUST NOT, SHOULD and MAY are used as in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

What `rate()` returns and `pencilmark rate --json` prints: one JSON object per puzzle. [JSON Schema](https://json-schema.org/):
[`sudoku-grade.schema.json`](sudoku-grade.schema.json).

```json
{"format": "sudoku-grade", "format_version": 1,
 "grader": {"name": "pencilmark", "version": "1.0.0"},
 "difficulty": 5.9, "time": 10.7, "band": "Medium", "band_index": 2,
 "contains": [{"code": "HSI", "chip": "HSI", "name": "Hidden Single", "band": 0},
              {"code": "NPR", "chip": "NPR/PPR/HPR", "name": "Naked Pair", "band": 2, "uses": 1, "alternatives": ["PPR", "HPR"]},
              {"code": "XWG", "chip": "XWG/KTE/SCL", "name": "X-Wing", "band": 2, "uses": 1, "alternatives": ["KTE", "SCL"]}],
 "contains_complete": true, "contains_truncated": false}
```

A card exists only for a puzzle with exactly one solution. For any other puzzle, `rate()` raises `NotUnique`,
`NoSolution` or `Undecided`; `rate_many()` and the command line give `{"error": "…"}` in its place (the command line adds
`"line"`, the input line number, to every object).

## 1. Keys

| Key | Field | Type | Meaning |
|---|---|---|---|
| `format`, `format_version` | always | `"sudoku-grade"`, `1` | |
| `grader` | always | `{"name", "version"}` | The engine that made the card. A card is only meaningful with that engine and version. |
| `difficulty` | default | number or null | How hard the steps feel, continuous from 0 (one empty cell), no ceiling; a typical newspaper medium is about 5. Measures effort, independent of `band`: variants often sit above Andrew Stuart's range for their band. Null when the band is `Unknown`. |
| `time` | default | number or null | Expected minutes for today's median player. |
| `time_mean`, `time_pNN` | optional | number or null | Spread of solve times over today's players: the mean, or the NN-th percentile (`time_p80` = 80% of players finish within it; NN from 1 to 99). Solves without long pauses; a log-normal fitted on two sources' per-player times. |
| `band` | default | string | `"Very Easy"`, `"Easy"`, `"Medium"`, `"Hard"`, `"Very Hard"`, `"Extreme"`; `"Unknown"` only when guessing was allowed and used. |
| `band_index` | default | integer or null | 0 (Very Easy) … 5 (Extreme); null for `Unknown`. |
| `contains` | default | list | The techniques met on the easiest route, easiest first (section 3). |
| `contains_complete` | with `contains` | boolean | False when the route stops where human logic ran out (band `Unknown`); `stopped_at_step` then gives the step. |
| `stopped_at_step` | with `contains`, when incomplete | integer | The first step human logic could not make. |
| `contains_truncated` | with `contains` | boolean | True when a `max_seconds` cap stopped the search for the shortest list: the list may not be minimal or may miss alternatives. |
| `issues` | optional | list | Publishing checks (section 4). |
| `reject` | optional | boolean | True when any issue has severity `reject`. |
| `se`, `se_diuf` | optional | `{"er", "ep", "ed", "scale"}` or null | Sudoku Explainer-style ratings of the route, on the classic scale or the DiufSudoku fork's (`scale` says which). Meaningful for classic sudoku only. |
| `steps` | optional | list | The step-by-step route (section 5). |
| `describe` | optional | object | The `describe()` output ([NAMING.md](NAMING.md)). |
| `symmetry` | optional | list | Symmetries of the givens pattern, entries as in the generator spec (`{"kind", "axis"?, "of": "givens"}`). |

## 2. Choosing fields

`rate(puzzle, fields=[...])` and `--fields a,b,c` take a list of the keys above; only those are computed. A field name
is always the key it produces (`contains` also brings `contains_complete`, `contains_truncated` and `stopped_at_step`).
Without `fields`, the default fields are returned. `explain="short"`, `"teach"` or both (CLI `--explain short,teach`)
adds explanations to `steps`. Shorthands: `steps=True` = the `steps` field with both explanation levels; `se=True` /
`se="diuf"` = the `se` / `se_diuf` field.

## 3. `contains`

Each entry is one technique on the route:

| Key | Meaning |
|---|---|
| `code` | Three-letter technique code (USAGE.md lists them). |
| `chip` | `code` plus its alternatives, `/`-separated: any one of them gets the solver through at that point. |
| `name` | Technique name. |
| `band` | The technique's band index. |
| `uses` | Times used on the route; omitted for singles (band 0), whose count depends on the route. |
| `alternatives` | Other codes that also work there; omitted when there are none, or when the producer skipped that search (pencilmark: `alternatives=False`, CLI `--no-alternatives`; band, difficulty and time are the same). |

## 4. `issues`

`{"code", "severity", "text", "rules"?}`. `severity` is `"reject"` (would not be published) or `"warning"`. `rules`, when
present, lists the offending rules as indices into `rules` of the puzzle as `to_export` writes it.

Each check can be adjusted with a **quality object** keyed by code: `rate(puzzle, quality={"trivial": 0.5, "trial":
false})`, CLI `--quality trivial=0.5,trial=false`, or the generator spec's `quality` ([SPEC.md](SPEC.md)). A check with a limit
takes a number (`true` = the default limit); every check takes `false` to turn it off.

| Code | Severity | Meaning | Limit (default) |
|---|---|---|---|
| `spike` | warning | A Medium or harder puzzle whose 3 hardest steps carry more than *limit* of its effort (effort per step as in `difficulty`). | share (0.6) |
| `decorative` | reject | A rule that is neither needed for uniqueness nor used by any step. | on / off |
| `barely_used` | reject when never used, else warning | A rule used in fewer than *limit* steps. | steps (3) |
| `redundant` | warning | A rule the puzzle is unique without, although the solve uses it. | on / off |
| `trivial` | reject | More than *limit* of the cells are given (0.6 = 60%). | share (0.6) |
| `tedious` | warning | Very Easy or Easy, but over *limit* minutes of routine work. | minutes (60) |
| `uniqueness` | warning | Needs a uniqueness-based technique (relies on assuming one solution). | on / off |
| `trial` | warning | Needs trial and error or forcing chains. | on / off |

Example: `{"code": "barely_used", "severity": "reject", "text": "thermo lines (rules 3, 4, 5, 6): used in only 0 steps
of the solve", "rules": [3, 4, 5, 6]}`.

## 5. `steps`

Each step: `n` (from 1), `technique` (name), `code`, `band`, then `placement` (`"r2c8=3"`) and / or `eliminations`
(`["r4c5#7", …]`: candidate 7 removed from r4c5), and, when requested, `explanation`: `{"short": …, "teach": …}` with
the requested levels.

## 6. Implementing a subset

Only `format`, `format_version` and `grader` are required; every other key is present only when it was asked for
(section 2). A producer MAY therefore emit just the headline numbers, for example `difficulty`, `time` and `band`, and a
consumer that needs only those MAY ignore every other key. A consumer MUST NOT compare cards from different `grader`
names or versions as if they were on one scale.
