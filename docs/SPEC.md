# Generator spec: `sudoku-spec`, format_version 1

A request to a puzzle generator. It reuses the vocabulary of the puzzle format ([FORMAT.md](FORMAT.md)) and the keys
of the grade card ([GRADE.md](GRADE.md)), and is otherwise independent of both. Example specs:
[examples/specs](examples/specs/README.md).

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
 "quality": {"trivial": {"limit": 0.4}},
 "limits": {"results": 3, "attempts": 2000, "time": 600, "seed": 42},
 "fields": ["difficulty", "band", "contains", "issues"]}
```

**Fixed vs open.** A rule **with cells is locked**: copied into every result exactly as drawn (`"lock": false` = a
starting point the generator may move or drop). A rule **with `count` and no cells** is a template the generator fills;
`count` is a number, `[min, max]` (`max` may be `null`), `"auto"` (as many as needed), `"all"` (every true clue: for
edge kinds this adds the matching `negative`), `"min"` (a minimal set) or `"tile"` (cages / boxes partitioning the
area). Templates take shape limits where meaningful: `size` (cells per cage / box), `length` (cells per line), `value`
(e.g. whisper difference), `displaced` (jigsaw: cells moved out of the regular boxes). A template may also name the variety it wants with the rule's own key: `"color": "black"` on a kropki edge, `"letter": "X"` on an XV edge, `kind` `odd` / `even` on a cell rule; one template per variety, each with its own count. Any template or locked rule may
carry `"area"` ([FORMAT.md section 5](FORMAT.md#5-rules-common-shape-and-pair-operators): a grid's origin or a cell list), limiting where it lives.

**Givens.** `"givens"` is either the puzzle form (a flat list: digits are locked givens, `0` = must stay empty, `null`
= no cell) or an object: `count` (number or range), `mask` (flat list, `1` = must be given, `0` = must be empty,
`null` = generator decides), `values` (`{"r1c1": 5, …}` locked digits).

**Symmetry** is a list; each entry has `kind` (`rot180`, `rot90`, `mirror` with `axis` `horizontal` | `vertical` |
`diagonal` | `antidiagonal`) and `of`: `"givens"`, `"all"` (givens and every rule), or a rule selector such as
`{"type": "line"}` / `{"type": "line", "kind": "whisper"}`. The same entries are a quality check and are reported by
`describe()`.

**`where`: targets on the card**, using the card's keys ([GRADE.md](GRADE.md)): `band` (value or list), `difficulty`
(`[lo, hi]` or `"max"` / `"min"`), `time` (`{"max": minutes}`), `contains` (codes that must appear; `{"codes": [...],
"strict": true}` = as the code itself, not only as an alternative in a chip; `{"only": [...]}` to allow nothing else, and
per-code `{"uses": n}`), `not_contains`, `issues` (`"none"`, `"no_reject"` (warnings allowed) or a list of allowed codes), `elements` (`{"max": n}`: at most
n placed rule elements in total).
**Per-area targets**: `"areas": [{"area": "r1c13", "where": {"band": "Medium"}}]`, measured on the **joint** solve (the
steps that place or eliminate in that area on the whole-board route), never on the area generated alone.

**`quality`: the checks' limits**, the same object as `rate(..., quality=…)` ([GRADE.md section 4](GRADE.md#4-issues)): `{"trivial": {"limit": 0.4}, "trial": {"severity": "off"}}`.
It changes what the card reports as `issues`; `where.issues` chooses which of them a result may have.

**`limits`** bound every run: `results` (puzzles to return), `attempts`, `time` (seconds), `seed` (reproducible runs).
The run stops at the first limit; `"max"` / `"min"` targets are best-so-far and the result reports achieved vs
requested.

**`fields`**: which card fields to return with each result ([GRADE.md](GRADE.md)).

pencilmark's generator implements a subset of this language and refuses the rest with a clear message, never silently
ignoring a part; see [USAGE.md](USAGE.md#generator). Example specs are in `docs/examples/specs/`.

A run's result is an ordinary `sudoku-puzzle`; `meta.generated_from` may carry the spec's fingerprint.
