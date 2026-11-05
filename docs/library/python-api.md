---
title: Python API
description: "Every public function of the pencilmark package: rate, solve, generate, load, the format helpers, the errors."
toc_max_heading_level: 2
---

# Python API

Everything below is importable from `pencilmark` directly (`pencilmark.rate`, `pencilmark.to_export`, …). This page is generated from the docstrings (`tools/gen_api_md.py`).

| Name | What it does |
|---|---|
| def [`rate`](#rate) | The "sudoku-grade" card of one puzzle ([Grade card](../formats/grade-card.md)), with only the fields you ask for. |
| def [`rate_many`](#rate_many) | Cards for many puzzles, in input order. |
| def [`describe`](#describe) | The variant name and its rules in words, from the rules alone (pencilmark/variants.py). |
| def [`solve`](#solve) | The unique solution of a puzzle. |
| def [`count_solutions`](#count_solutions) | How many solutions a puzzle has, counting up to a limit. |
| def [`generate`](#generate) | One puzzle for a "sudoku-spec" request ([Generator spec](../formats/generator-spec.md)). |
| def [`load`](#load) | Any accepted input -> a finalised engine Puzzle. |
| def [`validate`](#validate) | Strict reading checks of a format_version 1 dict ([Puzzle format](../formats/puzzle-format.md) section 4). |
| def [`fingerprint`](#fingerprint) | Content fingerprint of a puzzle: "sha256:&lt;hex>" of its canonical form. |
| def [`to_export`](#to_export) | The sudoku-puzzle dict of a puzzle (format_version 1, [Puzzle format](../formats/puzzle-format.md)). |
| def [`dumps`](#dumps) | Canonical JSON text of a sudoku-puzzle dict: fixed key order; pretty: one grid row per line, one rule per… |
| def [`from_string`](#from_string) | A puzzle as text -> sudoku-puzzle dict ([Other formats](../formats/other-formats.md)). |
| def [`to_string`](#to_string) | A puzzle as text ([Other formats](../formats/other-formats.md)). |
| def [`from_ipuz`](#from_ipuz) | An ipuz sudoku -> sudoku-puzzle dict ([Other formats](../formats/other-formats.md)). |
| def [`to_ipuz`](#to_ipuz) | A puzzle as an ipuz 2 dict ([Other formats](../formats/other-formats.md)). |
| class [`NotUnique`](#NotUnique) | the puzzle has more than one solution |
| class [`NoSolution`](#NoSolution) | the puzzle has no solution |
| class [`Undecided`](#Undecided) | the exhaustive search hit its node or time limit and OR-Tools (pip install "pencilmark[verify]") is not… |

## Grading

### `def rate(puzzle, steps=False, max_seconds=None, mode='human', se=False, fields=None, allow_guessing=False, explain=None, quality=None, alternatives=True)` {#rate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L132)

The "sudoku-grade" card of one puzzle ([Grade card](../formats/grade-card.md)), with only the fields you ask for.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts: an 81-character string, a sudoku-puzzle dict or JSON text, a .json file, an ipuz file, a SudokuPad / f-puzzles / Penpa / Logic Masters link.
- `steps` *bool* — Shorthand for the `steps` field with every explanation level.
- `max_seconds` *float, optional* — One wall-clock limit for the whole call. When it passes, the card says band "Unknown", difficulty and time are null and `completed` is false.
- `mode` *str* — "human" (default): human techniques only, a proof by full search where they stop; "computer": also forcing chains and nets, Nishio and trial.
- `se` *bool* — Shorthand for the `se` field (Sudoku Explainer-style ratings; classic sudoku only).
- `fields` *list of str, optional* — The top-level fields to return. Default: difficulty, time, band, contains. Optional: band_index, issues, reject, warning (publishing checks), time_mean, time_pNN (any percentile 1-99, e.g. time_p80), time_dist, elapsed (wall seconds of the call), se, steps, trace (the board before and after each step), describe, symmetry. format, format_version and grader are always present.
- `allow_guessing` *bool* — Guess where no technique applies (band "Unknown") instead of proving by full search (Trial and error, Extreme).
- `explain` *str, list of str or bool, optional* — Explanation levels for the steps: "notation", "short", "teach", or True for all three; "substeps" (only by name) tells each step as sub-steps with reasons and drawing annotations ([Grade card](../formats/grade-card.md) 5).
- `quality` *dict, optional* — Settings of the issue checks, e.g. {"trivial": {"limit": 0.5}, "trial": {"severity": "off"}} ([Grade card](../formats/grade-card.md) 4).
- `alternatives` *bool* — False skips the search for interchangeable techniques (each chip in contains lists one code). Band, difficulty and time are the same either way, and the card comes much faster.

**Returns**

- *dict* — The card. Its steps walk the shortest technique list's route when the card asks for contains (or issues, reject or warning), else the full first route ([Grade card](../formats/grade-card.md) 5).

**Raises**

- *NotUnique* — The puzzle has more than one solution.
- *NoSolution* — The puzzle has no solution.
- *Undecided* — The uniqueness search hit its limit without OR-Tools installed, or max_seconds passed first.

### `def rate_many(puzzles, jobs=1, steps=False, max_seconds=None, mode='human', se=False, fields=None, allow_guessing=False, explain=None, quality=None, alternatives=True)` {#rate_many}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L297)

Cards for many puzzles, in input order.

**Parameters**

- `puzzles` *iterable* — Puzzles in any form `rate` accepts.
- `jobs` *int* — Worker processes; 1 rates in this process.
- `steps, max_seconds, mode, se, fields, allow_guessing, explain, quality, alternatives` — As for `rate`.

**Returns**

- *list of dict* — One card per puzzle. A puzzle that cannot be rated (not unique, no solution, unreadable) gives {"error": "..."} instead of raising.

### `def describe(puzzle)` {#describe}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L539)

The variant name and its rules in words, from the rules alone (pencilmark/variants.py).

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts.

**Returns**

- *dict* — {"type": variant name, "rules": {short name: one-sentence rule, ...}}.

## Solving

### `def solve(puzzle, info=False)` {#solve}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L338)

The unique solution of a puzzle.

Uses the engine's exhaustive C++ search; CP-SAT (OR-Tools, optional) only when that search hits its node or time limit.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts.
- `info` *bool* — Return {"solution": [...], "seconds": wall-clock seconds of the search} instead of the bare list.

**Returns**

- *list of int* — The digits in the puzzle's cell order.

**Raises**

- *NotUnique* — More than one solution.
- *NoSolution* — No solution.
- *Undecided* — The search hit its node or time limit and OR-Tools is not installed.

### `def count_solutions(puzzle, limit=1000)` {#count_solutions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L384)

How many solutions a puzzle has, counting up to a limit.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts.
- `limit` *int* — Stop counting here.

**Returns**

- *dict* — {"count": n, "exact": bool}. exact is false when there are at least n: the count reached `limit`, or the search hit its node or time limit without OR-Tools installed.

## Generating

### `def generate(spec)` {#generate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L654)

One puzzle for a "sudoku-spec" request ([Generator spec](../formats/generator-spec.md)).

**Parameters**

- `spec` *dict, str or Path* — The request: a dict, JSON text or a path to a .json file.

**Returns**

- *dict* — {"puzzle": sudoku-puzzle dict, "card": its sudoku-grade card, "info": {...}}.

**Raises**

- *GenerationFailed* — No puzzle met the request in the time it allows.

## Reading and writing

### `def load(puzzle)` {#load}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L94)

Any accepted input -> a finalised engine Puzzle.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — A classic string (81 characters, with or without a trailing comment), a text or pencil-mark grid, a sudokuwiki packed string, a sudoku-puzzle dict or JSON text, an ipuz file, a .json path, a SudokuPad / f-puzzles / Penpa / Logic Masters link, or an engine Puzzle (returned as it is).

**Returns**

- *Puzzle* — The engine's puzzle.

**Raises**

- *FormatError* — A sudoku-puzzle document that breaks the format.
- *TypeError* — An input of no known form.

### `def validate(doc)` {#validate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L515)

Strict reading checks of a format_version 1 dict ([Puzzle format](../formats/puzzle-format.md) section 4).

**Parameters**

- `doc` *dict* — A sudoku-puzzle document.

**Returns**

- *bool* — True.

**Raises**

- *FormatError* — The document breaks the format; the message names the rule and the problem.

### `def fingerprint(puzzle)` {#fingerprint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L494)

Content fingerprint of a puzzle: "sha256:&lt;hex>" of its canonical form.

Covers the rules, grid, givens and candidates; not meta, style or the solution. Two files of the same puzzle get the same fingerprint.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts.

**Returns**

- *str* — "sha256:" followed by 64 hex digits.

### `def to_export(puzzle, meta=None, with_solution=True, describe=True, style=True, **meta_kw)` {#to_export}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L408)

The sudoku-puzzle dict of a puzzle (format_version 1, [Puzzle format](../formats/puzzle-format.md)).

Canonical: houses and rules with "r1c1" cells, keys in a fixed order. Metadata already in a JSON input is kept.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts.
- `meta` *dict, optional* — Metadata for the "meta" object, e.g. {"title": ..., "author": ..., "date": ...}.
- `with_solution` *bool* — Include the solution.
- `describe` *bool* — Fill an empty meta.type / meta.rules_text from `describe`; never overwrites them.
- `style` *bool* — Keep how the source drew each rule (SudokuPad colours, widths, shapes) as the rule's cosmetic `style`.
- `**meta_kw` — Metadata as keywords: title, author, source, id, url, date, rules_text.

**Returns**

- *dict* — The sudoku-puzzle document.

### `def dumps(doc, pretty=True)` {#dumps}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L474)

Canonical JSON text of a sudoku-puzzle dict: fixed key order; pretty: one grid row per line, one rule per line.

**Parameters**

- `doc` *dict* — A sudoku-puzzle document.
- `pretty` *bool* — Readable layout (True) or one line (False).

**Returns**

- *str* — The text.

### `def from_string(s, symbols=None)` {#from_string}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L606)

A puzzle as text -> sudoku-puzzle dict ([Other formats](../formats/other-formats.md)).

Reads plain classic strings (with or without a trailing comment), text grids with separators, pencil-mark grids, 729-character candidate strings, HoDoKu library lines and sudokuwiki.org packed strings.

**Parameters**

- `s` *str* — The text.
- `symbols` *str, optional* — For a plain string, the symbol of each digit in order (e.g. "ABCDEFGHI" reads A as 1); default 1-9, then A-Z.

**Returns**

- *dict* — The sudoku-puzzle document.

### `def to_string(puzzle, form='plain')` {#to_string}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L629)

A puzzle as text ([Other formats](../formats/other-formats.md)).

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts.
- `form` *str* — "plain" (81 characters), "grid" (rows with separators) or "sudokuwiki" (packed string).

**Returns**

- *str* — The text.

**Raises**

- *NotSupportedError* — The form cannot carry the puzzle (e.g. a variant in "plain").

### `def from_ipuz(ipuz)` {#from_ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L588)

An ipuz sudoku -> sudoku-puzzle dict ([Other formats](../formats/other-formats.md)).

**Parameters**

- `ipuz` *dict or str* — The ipuz document, or its JSON text.

**Returns**

- *dict* — The sudoku-puzzle document.

### `def to_ipuz(puzzle)` {#to_ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L563)

A puzzle as an ipuz 2 dict ([Other formats](../formats/other-formats.md)).

ipuz expresses classic, Latin square, diagonal, windoku, jigsaw and killer sudoku.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Anything `load` accepts.

**Returns**

- *dict* — The ipuz document.

**Raises**

- *NotSupportedError* — The puzzle uses rules ipuz cannot express.

## Errors

### `class NotUnique(ValueError)` {#NotUnique}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L50)

the puzzle has more than one solution

### `class NoSolution(ValueError)` {#NoSolution}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L54)

the puzzle has no solution

### `class Undecided(RuntimeError)` {#Undecided}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L334)

the exhaustive search hit its node or time limit and OR-Tools (pip install "pencilmark[verify]") is not available
