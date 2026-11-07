---
title: Python API
description: "Every public function of the pencilmark package: rate, solve, generate, the readers and writers of every format, the errors."
toc_max_heading_level: 2
---

# Python API

`rate`, `solve` and the rest take a puzzle in any format pencilmark reads (detected; `format=` names it); `pencilmark.read.<format>` reads one format strictly, `pencilmark.write.<format>` writes one. This page is generated from the docstrings (`tools/gen_api_md.py`).

| Name | What it does |
|---|---|
| def [`rate`](#rate) | The "pencilmark-grade" card of one puzzle ([Grade card](../formats/grade-card.md)), with only the fields you ask for. |
| def [`rate_many`](#rate_many) | Cards for many puzzles, in input order. |
| def [`describe`](#describe) | The variant name and its rules in words, from the rules alone (pencilmark/variants.py). |
| def [`solve`](#solve) | The unique solution of a puzzle. |
| def [`count_solutions`](#count_solutions) | How many solutions a puzzle has, counting up to a limit. |
| def [`generate`](#generate) | One puzzle for a "pencilmark-spec" request ([Generator spec](../formats/generator-spec.md)). |
| def [`read.auto`](#read-auto) | Read x in its format (detected, or named by format). |
| def [`read.detect`](#read-detect) | Name the format of x (a key of READERS: "pencilmark", "plain", ..., "link"), or None; reads nothing but a… |
| def [`read.pencilmark`](#read-pencilmark) | Read pencilmark JSON: a pencilmark-puzzle dict, its JSON text or a path to a .json file. |
| def [`read.plain`](#read-plain) | Read a plain string: D x D characters ('.' or '0' empty, 1-9 then A-Z), maybe followed by a comment. |
| def [`read.grid`](#read-grid) | Read a text grid: one row per line, with or without \| - + separators. |
| def [`read.pencil_marks`](#read-pencil_marks) | Read a pencil-mark grid: one token per cell, the cell's candidates (a single digit: a given). |
| def [`read.candidates`](#read-candidates) | Read a 729-character candidate string (9 characters per cell, the digit or 0). |
| def [`read.hodoku`](#read-hodoku) | Read a HoDoKu library line: the puzzle and its removed candidates. |
| def [`read.sudokuwiki`](#read-sudokuwiki) | Read a sudokuwiki.org packed string (S9B, J9B, X9B, W9B, C9B, L9B, M9B, S6B, L6C). |
| def [`read.ipuz`](#read-ipuz) | Read an ipuz sudoku: a dict, its JSON text or a path to a .ipuz file. |
| def [`read.link`](#read-link) | Read a SudokuPad, f-puzzles, Penpa, Logic Masters or sudoku.coach link (or a short link to one; some need… |
| def [`write.pencilmark`](#write-pencilmark) | pencilmark JSON text of x: canonical key order, one line per rule (pretty) or one line. |
| def [`write.document`](#write-document) | The pencilmark-puzzle dict of x, canonical. |
| def [`write.plain`](#write-plain) | One string of D x D characters, '.' for an empty cell (classic sudoku with standard boxes only). |
| def [`write.grid`](#write-grid) | Rows on lines, boxes separated by \| and -+- lines (classic sudoku with standard boxes only). |
| def [`write.sudokuwiki`](#write-sudokuwiki) | A sudokuwiki.org packed string (classic, jigsaw, X, windoku, killer and the other forms sudokuwiki has). |
| def [`write.ipuz`](#write-ipuz) | An ipuz 2 dict (classic, Latin square, diagonal, windoku, jigsaw and killer sudoku). |
| def [`validate`](#validate) | Strict reading checks of a format_version 1 dict ([Puzzle format](../formats/puzzle-format.md) section 4). |
| def [`fingerprint`](#fingerprint) | Content fingerprint of a puzzle: the SHA-256 of its canonical form, 64 hex digits. |
| class [`Error`](#Error) | Base class of every pencilmark error. |
| class [`FormatError`](#FormatError) | The input is not valid in its format: unknown key or rule type, bad cell, failed structural check, an… |
| class [`NotSupportedError`](#NotSupportedError) | The input is valid in its format, but uses something pencilmark cannot build or write. |
| class [`FetchError`](#FetchError) | A network request failed, or robots.txt forbids it. |
| class [`ReadingMismatch`](#ReadingMismatch) | A site puzzle read this way contradicts the setter's embedded solution. |
| class [`NotUnique`](#NotUnique) | The puzzle has more than one solution. |
| class [`NoSolution`](#NoSolution) | The puzzle has no solution. |
| class [`Undecided`](#Undecided) | The exhaustive search hit its node or time limit and OR-Tools (pip install "pencilmark[verify]") is not… |
| class [`GenerationFailed`](#GenerationFailed) | No puzzle met the spec within the time limit (or the spec is infeasible); str(e) says why. |

## Grading

### `def rate(puzzle: str | dict | Path, *, max_seconds: float | None=None, mode: str='human', fields: list[str] | None=None, allow_guessing: bool=False, explain: bool | str | list[str] | None=None, quality: dict | None=None, alternatives: bool=True, coloring: bool=False, format: str | None=None) -> dict` {#rate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L110)

The "pencilmark-grade" card of one puzzle ([Grade card](../formats/grade-card.md)), with only the fields you ask for.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Any format pencilmark.read reads, detected (an 81-character string, a text grid, a sudokuwiki string, pencilmark JSON as a dict, text or .json path, an ipuz file, a SudokuPad / f-puzzles / Penpa / Logic Masters link).
- `max_seconds` *float, optional* — One wall-clock limit for the whole call. When it passes, the card says band "Unknown", difficulty and time are null and `completed` is false.
- `mode` *str* — "human" (default): human techniques only, a proof by full search where they stop; "computer": also forcing chains and nets, Nishio and trial.
- `fields` *list of str, optional* — The top-level fields to return. Default: difficulty, time, band, contains. Optional: band_index, issues, reject, warning (publishing checks), time_mean, time_pNN (any percentile 1-99, e.g. time_p80), time_dist, elapsed (wall seconds of the call), se (Sudoku Explainer-style ratings; classic sudoku only), steps (with `explain` for their explanations), trace (the board before and after each step), describe, symmetry. format, format_version and grader are always present.
- `allow_guessing` *bool* — Guess where no technique applies (band "Unknown") instead of proving by full search (Trial and error, Extreme).
- `explain` *str, list of str or bool, optional* — Explanation levels for the steps: "notation", "short", "teach", or True for all three; "substeps" (only by name) tells each step as sub-steps with reasons and drawing annotations ([Grade card](../formats/grade-card.md) 5).
- `quality` *dict, optional* — Which issue checks run and how ([Grade card](../formats/grade-card.md) 4): None = every check that is not opt in, at its own severity (the "default" preset); {} = none; {"preset": "standard"}; without a preset only the checks named run, e.g. {"trivial": {"limit": 0.5}, "trial": {"severity": "reject"}}.
- `alternatives` *bool* — False skips the search for interchangeable techniques (each chip in contains lists one code). Band, difficulty and time are the same either way, and the card comes much faster.
- `coloring` *bool* — Opt in to colouring as a solving method: colours kept through the solve (Colour Fill, Colour Single, Colour Pair, ...; [techniques](../grades/techniques.md), Colouring). Off by default: most solvers do not colour, and with it the hardest puzzles take much longer to grade.
- `format` *str, optional* — The input's format (a pencilmark.read reader: "plain", "sudokuwiki", "pencilmark", "link", ...) instead of detecting it.

**Returns**

- *dict* — The card. Its steps walk the shortest technique list's route when the card asks for contains (or issues, reject or warning), else the full first route ([Grade card](../formats/grade-card.md) 5).

**Raises**

- *NotUnique* — The puzzle has more than one solution.
- *NoSolution* — The puzzle has no solution.
- *A puzzle whose uniqueness the engine cannot settle (max_seconds passed first, or the search hit its limit without*
- *OR-Tools) is not an error: its card has band "Unknown" and a `reason`.*

### `def rate_many(puzzles: list, *, jobs: int=1, max_seconds: float | None=None, mode: str='human', fields: list[str] | None=None, allow_guessing: bool=False, explain: bool | str | list[str] | None=None, quality: dict | None=None, alternatives: bool=True, coloring: bool=False) -> list[dict]` {#rate_many}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L296)

Cards for many puzzles, in input order.

**Parameters**

- `puzzles` *iterable* — Puzzles in any form `rate` accepts.
- `jobs` *int* — Worker processes; 1 rates in this process.
- `max_seconds, mode, fields, allow_guessing, explain, quality, alternatives, coloring` — As for `rate`.

**Returns**

- *list of dict* — One card per puzzle. A puzzle that cannot be rated (not unique, no solution, unreadable) gives {"error": "..."} instead of raising.

### `def describe(puzzle: str | dict | Path) -> dict` {#describe}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L444)

The variant name and its rules in words, from the rules alone (pencilmark/variants.py).

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Any format pencilmark.read reads (detected), or its document.

**Returns**

- *dict* — {"type": variant name, "rules": {short name: one-sentence rule, ...}, "rules_text": the rules as one text, "variants": the variants as snake_case ids, like tags (["killer", "german_whispers"])}.

## Solving

### `def solve(puzzle: str | dict | Path, *, format: str | None=None) -> list[int]` {#solve}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L333)

The unique solution of a puzzle.

Uses the engine's exhaustive C++ search; CP-SAT (OR-Tools, optional) only when that search hits its node or time limit.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Any format pencilmark.read reads (detected), or its document.
- `format` *str, optional* — The input's format instead of detecting it.

**Returns**

- *list of int* — The digits in the puzzle's cell order.

**Raises**

- *NotUnique* — More than one solution.
- *NoSolution* — No solution.
- *Undecided* — The search hit its node or time limit and OR-Tools is not installed.

### `def count_solutions(puzzle: str | dict | Path, *, limit: int=1000, format: str | None=None) -> dict` {#count_solutions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L374)

How many solutions a puzzle has, counting up to a limit.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Any format pencilmark.read reads (detected), or its document.
- `limit` *int* — Stop counting here.

**Returns**

- *dict* — {"count": n, "exact": bool}. exact is false when there are at least n: the count reached `limit`, or the search hit its node or time limit without OR-Tools installed.

## Generating

### `def generate(spec: str | dict | Path) -> dict` {#generate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L464)

One puzzle for a "pencilmark-spec" request ([Generator spec](../formats/generator-spec.md)).

**Parameters**

- `spec` *dict, str or Path* — The request: a dict, JSON text or a path to a .json file.

**Returns**

- *dict* — {"puzzle": pencilmark-puzzle dict, "card": its pencilmark-grade card, "info": {...}}.

**Raises**

- *GenerationFailed* — No puzzle met the request in the time it allows.

## Reading (pencilmark.read)

### `def read.auto(x: str | dict | Path, *, format: str | None=None) -> dict` {#read-auto}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L160)

Read x in its format (detected, or named by format).

### `def read.detect(x) -> str | None` {#read-detect}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L137)

Name the format of x (a key of READERS: "pencilmark", "plain", ..., "link"), or None; reads nothing but a file named by a path.

### `def read.pencilmark(x: str | dict | Path) -> dict` {#read-pencilmark}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L45)

Read pencilmark JSON: a pencilmark-puzzle dict, its JSON text or a path to a .json file.

### `def read.plain(text: str, *, symbols: str | None=None) -> dict` {#read-plain}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L55)

Read a plain string: D x D characters ('.' or '0' empty, 1-9 then A-Z), maybe followed by a comment. symbols: the symbol of each digit in order (e.g. "ABCDEFGHI" reads A as 1).

### `def read.grid(text: str) -> dict` {#read-grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L61)

Read a text grid: one row per line, with or without | - + separators.

### `def read.pencil_marks(text: str) -> dict` {#read-pencil_marks}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L66)

Read a pencil-mark grid: one token per cell, the cell's candidates (a single digit: a given).

### `def read.candidates(text: str) -> dict` {#read-candidates}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L71)

Read a 729-character candidate string (9 characters per cell, the digit or 0).

### `def read.hodoku(line: str) -> dict` {#read-hodoku}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L76)

Read a HoDoKu library line: the puzzle and its removed candidates.

### `def read.sudokuwiki(text: str) -> dict` {#read-sudokuwiki}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L81)

Read a sudokuwiki.org packed string (S9B, J9B, X9B, W9B, C9B, L9B, M9B, S6B, L6C).

### `def read.ipuz(x: str | dict | Path) -> dict` {#read-ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L86)

Read an ipuz sudoku: a dict, its JSON text or a path to a .ipuz file.

### `def read.link(url: str) -> dict` {#read-link}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L91)

Read a SudokuPad, f-puzzles, Penpa, Logic Masters or sudoku.coach link (or a short link to one; some need one request). A reading the setter's embedded solution contradicts raises ReadingMismatch.

## Writing (pencilmark.write)

### `def write.pencilmark(x: str | dict | Path, *, solution: bool=False, describe: bool=False, style: bool=True, pretty: bool=True) -> str` {#write-pencilmark}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L76)

pencilmark JSON text of x: canonical key order, one line per rule (pretty) or one line.

### `def write.document(x: str | dict | Path, *, solution: bool=False, describe: bool=False, style: bool=True) -> dict` {#write-document}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L17)

The pencilmark-puzzle dict of x, canonical. solution: add the solution (when the puzzle has exactly one); describe: fill an empty meta.type / meta.rules_text / meta.variants (never overwritten); style=False: leave out the drawing (the rules' style, the top-level style and decorations).

### `def write.plain(x: str | dict | Path) -> str` {#write-plain}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L85)

One string of D x D characters, '.' for an empty cell (classic sudoku with standard boxes only).

### `def write.grid(x: str | dict | Path) -> str` {#write-grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L93)

Rows on lines, boxes separated by | and -+- lines (classic sudoku with standard boxes only).

### `def write.sudokuwiki(x: str | dict | Path) -> str` {#write-sudokuwiki}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L101)

A sudokuwiki.org packed string (classic, jigsaw, X, windoku, killer and the other forms sudokuwiki has).

### `def write.ipuz(x: str | dict | Path) -> dict` {#write-ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L109)

An ipuz 2 dict (classic, Latin square, diagonal, windoku, jigsaw and killer sudoku).

## Checking

### `def validate(doc: dict) -> bool` {#validate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L420)

Strict reading checks of a format_version 1 dict ([Puzzle format](../formats/puzzle-format.md) section 4).

**Parameters**

- `doc` *dict* — A pencilmark-puzzle document.

**Returns**

- *bool* — True.

**Raises**

- *FormatError* — The document breaks the format; the message names the rule and the problem.

### `def fingerprint(puzzle: str | dict | Path) -> str` {#fingerprint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/api.py#L398)

Content fingerprint of a puzzle: the SHA-256 of its canonical form, 64 hex digits.

Covers the rules, grid, givens and candidates; not meta, style or the solution. Two files of the same puzzle get the same fingerprint.

**Parameters**

- `puzzle` *str, dict, Path or Puzzle* — Any format pencilmark.read reads (detected), or its document.

**Returns**

- *str* — 64 lowercase hex digits (SHA-256).

## Errors

### `class Error(Exception)` {#Error}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L5)

Base class of every pencilmark error.

### `class FormatError(Error, ValueError)` {#FormatError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L9)

The input is not valid in its format: unknown key or rule type, bad cell, failed structural check, an unreadable link or payload.

### `class NotSupportedError(Error, ValueError)` {#NotSupportedError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L14)

The input is valid in its format, but uses something pencilmark cannot build or write. `elements` lists what (nothing is dropped silently).

### `class FetchError(Error, OSError)` {#FetchError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L23)

A network request failed, or robots.txt forbids it.

### `class ReadingMismatch(Error, ValueError)` {#ReadingMismatch}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L27)

A site puzzle read this way contradicts the setter's embedded solution.

### `class NotUnique(Error, ValueError)` {#NotUnique}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L31)

The puzzle has more than one solution.

### `class NoSolution(Error, ValueError)` {#NoSolution}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L35)

The puzzle has no solution.

### `class Undecided(Error, RuntimeError)` {#Undecided}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L39)

The exhaustive search hit its node or time limit and OR-Tools (pip install "pencilmark[verify]") is not available.

### `class GenerationFailed(Error, RuntimeError)` {#GenerationFailed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L44)

No puzzle met the spec within the time limit (or the spec is infeasible); str(e) says why.
