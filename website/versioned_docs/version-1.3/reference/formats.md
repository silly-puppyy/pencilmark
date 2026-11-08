---
title: "Formats"
description: "Reading, checking, writing and drawing puzzles and generator requests; the rule families and the variant names."
toc_max_heading_level: 2
---

# Formats

Reading, checking, writing and drawing puzzles and generator requests; the rule families and the variant names. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.read {#pencilmark.read}

[src/pencilmark/read.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py)

Reading puzzles: one function per format, each returning a pencilmark-puzzle document (a dict, [Puzzle format](../formats/puzzle-format.md)). A reader reads its own format only and raises FormatError for anything else; `detect` names the format of an input and `auto` reads any of them (what `rate`, `solve` and the command line do).

pencilmark(x)          pencilmark JSON: a dict, JSON text or a .json path

```
plain(text)            one string of D x D characters, maybe followed by a comment
grid(text)             rows on lines, with or without | - + separators
pencil_marks(text)     a pencil-mark grid, one token of candidates per cell
candidates(text)       a 729-character candidate string
hodoku(line)           a HoDoKu library line
sudokuwiki(text)       a sudokuwiki.org packed string (S9B, J9B, ...)
ipuz(x)                an ipuz sudoku: a dict, JSON text or a .ipuz path
link(url)              a SudokuPad, f-puzzles, Penpa or Logic Masters link (the host names the format)
```

| Name | What it does |
|---|---|
| def [`pencilmark`](#pencilmark.read.pencilmark) | Read pencilmark JSON: a pencilmark-puzzle dict, its JSON text or a path to a .json file. |
| def [`plain`](#pencilmark.read.plain) | Read a plain string: D x D characters ('.' or '0' empty, 1-9 then A-Z), maybe followed by a comment. |
| def [`grid`](#pencilmark.read.grid) | Read a text grid: one row per line, with or without \| - + separators. |
| def [`pencil_marks`](#pencilmark.read.pencil_marks) | Read a pencil-mark grid: one token per cell, the cell's candidates (a single digit: a given). |
| def [`candidates`](#pencilmark.read.candidates) | Read a 729-character candidate string (9 characters per cell, the digit or 0). |
| def [`hodoku`](#pencilmark.read.hodoku) | Read a HoDoKu library line: the puzzle and its removed candidates. |
| def [`sudokuwiki`](#pencilmark.read.sudokuwiki) | Read a sudokuwiki.org packed string (S9B, J9B, X9B, W9B, C9B, L9B, M9B, S6B, L6C). |
| def [`ipuz`](#pencilmark.read.ipuz) | Read an ipuz sudoku: a dict, its JSON text or a path to a .ipuz file. |
| def [`link`](#pencilmark.read.link) | Read a SudokuPad, f-puzzles, Penpa, Logic Masters or sudoku.coach link (or a short link to one; some need… |
| def [`detect`](#pencilmark.read.detect) | Name the format of x (a key of READERS: "pencilmark", "plain", ..., "link"), or None; reads nothing but a… |
| def [`auto`](#pencilmark.read.auto) | Read x in its format (detected, or named by format). |

### `def pencilmark(x: str | dict | Path) -> dict` {#pencilmark.read.pencilmark}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L45)

Read pencilmark JSON: a pencilmark-puzzle dict, its JSON text or a path to a .json file.

### `def plain(text: str, *, symbols: str | None=None) -> dict` {#pencilmark.read.plain}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L55)

Read a plain string: D x D characters ('.' or '0' empty, 1-9 then A-Z), maybe followed by a comment. symbols: the symbol of each digit in order (e.g. "ABCDEFGHI" reads A as 1).

### `def grid(text: str) -> dict` {#pencilmark.read.grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L61)

Read a text grid: one row per line, with or without | - + separators.

### `def pencil_marks(text: str) -> dict` {#pencilmark.read.pencil_marks}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L66)

Read a pencil-mark grid: one token per cell, the cell's candidates (a single digit: a given).

### `def candidates(text: str) -> dict` {#pencilmark.read.candidates}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L71)

Read a 729-character candidate string (9 characters per cell, the digit or 0).

### `def hodoku(line: str) -> dict` {#pencilmark.read.hodoku}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L76)

Read a HoDoKu library line: the puzzle and its removed candidates.

### `def sudokuwiki(text: str) -> dict` {#pencilmark.read.sudokuwiki}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L81)

Read a sudokuwiki.org packed string (S9B, J9B, X9B, W9B, C9B, L9B, M9B, S6B, L6C).

### `def ipuz(x: str | dict | Path) -> dict` {#pencilmark.read.ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L86)

Read an ipuz sudoku: a dict, its JSON text or a path to a .ipuz file.

### `def link(url: str) -> dict` {#pencilmark.read.link}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L91)

Read a SudokuPad, f-puzzles, Penpa, Logic Masters or sudoku.coach link (or a short link to one; some need one request). A reading the setter's embedded solution contradicts raises ReadingMismatch.

### `def detect(x) -> str | None` {#pencilmark.read.detect}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L137)

Name the format of x (a key of READERS: "pencilmark", "plain", ..., "link"), or None; reads nothing but a file named by a path.

### `def auto(x: str | dict | Path, *, format: str | None=None) -> dict` {#pencilmark.read.auto}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/read.py#L160)

Read x in its format (detected, or named by format).

## pencilmark.write {#pencilmark.write}

[src/pencilmark/write.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py)

Writing puzzles: one function per format. Each takes anything `pencilmark.read.auto` reads (pencilmark JSON, a plain string, a link, ...) and raises NotSupportedError when the format cannot carry the puzzle.

pencilmark(x)    pencilmark JSON text (canonical); solution= and describe= fill those fields

```
document(x)      the same as a dict
plain(x)         one string of D x D characters (classic sudoku)
grid(x)          rows on lines with | and -+- separators (classic sudoku)
sudokuwiki(x)    a sudokuwiki.org packed string
ipuz(x)          an ipuz 2 dict
```

| Name | What it does |
|---|---|
| def [`document`](#pencilmark.write.document) | The pencilmark-puzzle dict of x, canonical. |
| def [`pencilmark`](#pencilmark.write.pencilmark) | pencilmark JSON text of x: canonical key order, one line per rule (pretty) or one line. |
| def [`plain`](#pencilmark.write.plain) | One string of D x D characters, '.' for an empty cell (classic sudoku with standard boxes only). |
| def [`grid`](#pencilmark.write.grid) | Rows on lines, boxes separated by \| and -+- lines (classic sudoku with standard boxes only). |
| def [`sudokuwiki`](#pencilmark.write.sudokuwiki) | A sudokuwiki.org packed string (classic, jigsaw, X, windoku, killer and the other forms sudokuwiki has). |
| def [`ipuz`](#pencilmark.write.ipuz) | An ipuz 2 dict (classic, Latin square, diagonal, windoku, jigsaw and killer sudoku). |

### `def document(x: str | dict | Path, *, solution: bool=False, describe: bool=False, style: bool=True) -> dict` {#pencilmark.write.document}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L17)

The pencilmark-puzzle dict of x, canonical. solution: add the solution (when the puzzle has exactly one); describe: fill an empty meta.type / meta.rules_text / meta.variants (never overwritten); style=False: leave out the drawing (the rules' style, the top-level style and decorations).

### `def pencilmark(x: str | dict | Path, *, solution: bool=False, describe: bool=False, style: bool=True, pretty: bool=True) -> str` {#pencilmark.write.pencilmark}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L133)

pencilmark JSON text of x: canonical key order, one line per rule (pretty) or one line.

### `def plain(x: str | dict | Path) -> str` {#pencilmark.write.plain}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L142)

One string of D x D characters, '.' for an empty cell (classic sudoku with standard boxes only).

### `def grid(x: str | dict | Path) -> str` {#pencilmark.write.grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L150)

Rows on lines, boxes separated by | and -+- lines (classic sudoku with standard boxes only).

### `def sudokuwiki(x: str | dict | Path) -> str` {#pencilmark.write.sudokuwiki}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L158)

A sudokuwiki.org packed string (classic, jigsaw, X, windoku, killer and the other forms sudokuwiki has).

### `def ipuz(x: str | dict | Path) -> dict` {#pencilmark.write.ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/write.py#L166)

An ipuz 2 dict (classic, Latin square, diagonal, windoku, jigsaw and killer sudoku).

## pencilmark.errors {#pencilmark.errors}

[src/pencilmark/errors.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py)

Every error pencilmark raises: one family under `Error`. Input mistakes are ValueErrors (the input is wrong as given), a network problem an OSError, the engine giving up a RuntimeError.

| Name | What it does |
|---|---|
| class [`Error`](#pencilmark.errors.Error) | Base class of every pencilmark error. |
| class [`FormatError`](#pencilmark.errors.FormatError) | The input is not valid in its format: unknown key or rule type, bad cell, failed structural check, an… |
| class [`NotSupportedError`](#pencilmark.errors.NotSupportedError) | The input is valid in its format, but uses something pencilmark cannot build or write. |
| class [`FetchError`](#pencilmark.errors.FetchError) | A network request failed, or robots.txt forbids it. |
| class [`ReadingMismatch`](#pencilmark.errors.ReadingMismatch) | A site puzzle read this way contradicts the setter's embedded solution. |
| class [`NotUnique`](#pencilmark.errors.NotUnique) | The puzzle has more than one solution. |
| class [`NoSolution`](#pencilmark.errors.NoSolution) | The puzzle has no solution. |
| class [`Undecided`](#pencilmark.errors.Undecided) | The exhaustive search hit its node or time limit and OR-Tools (pip install "pencilmark[verify]") is not… |
| class [`GenerationFailed`](#pencilmark.errors.GenerationFailed) | No puzzle met the spec within the time limit (or the spec is infeasible); str(e) says why. |
| def [`unsupported`](#pencilmark.errors.unsupported) | A NotSupportedError for elements a reader cannot model exactly. |

### `class Error(Exception)` {#pencilmark.errors.Error}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L5)

Base class of every pencilmark error.

### `class FormatError(Error, ValueError)` {#pencilmark.errors.FormatError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L9)

The input is not valid in its format: unknown key or rule type, bad cell, failed structural check, an unreadable link or payload.

### `class NotSupportedError(Error, ValueError)` {#pencilmark.errors.NotSupportedError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L14)

The input is valid in its format, but uses something pencilmark cannot build or write. `elements` lists what (nothing is dropped silently).

### `class FetchError(Error, OSError)` {#pencilmark.errors.FetchError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L23)

A network request failed, or robots.txt forbids it.

### `class ReadingMismatch(Error, ValueError)` {#pencilmark.errors.ReadingMismatch}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L27)

A site puzzle read this way contradicts the setter's embedded solution.

### `class NotUnique(Error, ValueError)` {#pencilmark.errors.NotUnique}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L31)

The puzzle has more than one solution.

### `class NoSolution(Error, ValueError)` {#pencilmark.errors.NoSolution}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L35)

The puzzle has no solution.

### `class Undecided(Error, RuntimeError)` {#pencilmark.errors.Undecided}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L39)

The exhaustive search hit its node or time limit and OR-Tools (pip install "pencilmark[verify]") is not available.

### `class GenerationFailed(Error, RuntimeError)` {#pencilmark.errors.GenerationFailed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L44)

No puzzle met the spec within the time limit (or the spec is infeasible); str(e) says why.

### `def unsupported(elements, source='')` {#pencilmark.errors.unsupported}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/errors.py#L52)

A NotSupportedError for elements a reader cannot model exactly.

## pencilmark.exchange {#pencilmark.exchange}

[src/pencilmark/exchange/__init__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/__init__.py)

The "pencilmark-puzzle" exchange format, format_version 1 ([Puzzle format](../formats/puzzle-format.md)): engine Puzzle &lt;-> exchange dict.

write(p, meta=None, solution=None) -> dict          engine Puzzle -> canonical pencilmark-puzzle dict

```
to_internal(doc) -> dict                            pencilmark-puzzle dict -> puzzle JSON (pencilmark.puzzle_json)
read(doc) -> Puzzle                                 pencilmark-puzzle dict -> engine Puzzle (not finalized)
validate(doc)                                       strict reading checks (docs/formats/puzzle-format.md section 4); raises FormatError
dumps(doc, pretty=True) -> str                      canonical JSON text (docs/formats/puzzle-format.md 8.1)
fingerprint(doc) -> "<64 hex>"                       content fingerprint (docs/formats/puzzle-format.md 8.2)
prepared(doc) -> dict                               the doc as readers take it (origins filled in, named custom rules
                                                    expanded): use it before reading doc["rules"] yourself
```

The format is a transport layer: read(write(p)) builds the same engine structure as p (groups in order, relations and constraints in order, domains, givens, coordinates), except for the normalizations listed in [engine-mapping](../guides/development/engine-mapping.md) (each mechanic gets ONE engine expansion). The writer therefore works from the engine structure directly and keeps the order of relations and constraints (the order changes cards).

## pencilmark.exchange.common {#pencilmark.exchange.common}

[src/pencilmark/exchange/common.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py)

The format's constants, errors, cell names and operator parameters.

| Name | What it does |
|---|---|
| def [`cell_name`](#pencilmark.exchange.common.cell_name) | 0-based (row, col) -> 'r1c1' |
| def [`parse_cell`](#pencilmark.exchange.common.parse_cell) | 'r1c1' -> 0-based (row, col) |
| def [`op_params`](#pencilmark.exchange.common.op_params) | an operator's named parameter in a rule or an any_of entry -> the positional params list |
| def [`op_named`](#pencilmark.exchange.common.op_named) | positional params -> the named parameter key(s) of a rule or any_of entry |
| def [`with_definitions`](#pencilmark.exchange.common.with_definitions) | the doc with every placement of a named custom rule ({"type": "custom", "use": name, "cells": {...}})… |
| def [`prepared`](#pencilmark.exchange.common.prepared) | a document as readers, validators and the fingerprint take it: grid origins filled in, named custom rules… |
| def [`with_origins`](#pencilmark.exchange.common.with_origins) | the doc with every grid / box_grid / chaos rule's origin filled in: r1c1 when it is left out (6.1) |

### `def cell_name(r, c)` {#pencilmark.exchange.common.cell_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L29)

0-based (row, col) -> 'r1c1'

### `def parse_cell(s)` {#pencilmark.exchange.common.parse_cell}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L34)

'r1c1' -> 0-based (row, col)

### `def op_params(r)` {#pencilmark.exchange.common.op_params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L95)

an operator's named parameter in a rule or an any_of entry -> the positional params list

### `def op_named(op, params)` {#pencilmark.exchange.common.op_named}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L104)

positional params -> the named parameter key(s) of a rule or any_of entry

### `def with_definitions(doc)` {#pencilmark.exchange.common.with_definitions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L137)

the doc with every placement of a named custom rule ({"type": "custom", "use": name, "cells": {...}}) replaced by the rule it places: the definition's keys, then the placement's (a placement's style or label wins); the "definitions" map itself is dropped. Raises FormatError for a bad definition or placement (6.18).

### `def prepared(doc)` {#pencilmark.exchange.common.prepared}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L169)

a document as readers, validators and the fingerprint take it: grid origins filled in, named custom rules expanded. One place for every such normalization: a new one is added here, not at each caller.

### `def with_origins(doc)` {#pencilmark.exchange.common.with_origins}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L175)

the doc with every grid / box_grid / chaos rule's origin filled in: r1c1 when it is left out (6.1)

## pencilmark.exchange.board {#pencilmark.exchange.board}

[src/pencilmark/exchange/board.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py)

The board: cells, houses, areas, and the digit tables some rules expand to.

| Name | What it does |
|---|---|
| class [`Board`](#pencilmark.exchange.board.Board) | coordinates of the existing cells (0-based) and helpers shared by the reader and the writer. |
| def [`subgrid_units`](#pencilmark.exchange.board.subgrid_units) | rows, columns, boxes of an n x n sub-grid given as n\*n engine cells in its reading order (puzzle_json's… |
| def [`window`](#pencilmark.exchange.board.window) | indices of the n x n cells with top-left corner (r0, c0); None if one is missing |
| def [`grid_units`](#pencilmark.exchange.board.grid_units) | houses of a grid at (r0, c0): its D rows (top to bottom), D columns (left to right) and, for a box_grid with… |
| def [`grid_area`](#pencilmark.exchange.board.grid_area) | set of the cell indices in the D x D square with top-left corner (r0, c0) |
| def [`read_houses`](#pencilmark.exchange.board.read_houses) | the house groups a rule list states, in engine order -> (houses [(kind, cells, extra)], areas [cell sets])… |
| def [`battenburg_table`](#pencilmark.exchange.board.battenburg_table) | allowed 2x2 digit tuples (TL, TR, BL, BR) of a battenburg window, marked or unmarked |
| def [`vudoku_table`](#pencilmark.exchange.board.vudoku_table) | allowed (x, y, z) triples: x is y + z or \|y - z\| |
| def [`product_pairs`](#pencilmark.exchange.board.product_pairs) | digit pairs [u, v] in 1..D with u \* v == p |

### `class Board` {#pencilmark.exchange.board.Board}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L13)

coordinates of the existing cells (0-based) and helpers shared by the reader and the writer.

#### `def name(self, i)` {#pencilmark.exchange.board.Board.name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L23)

cell index i -> its name (r1c1)

#### `def idx(self, name)` {#pencilmark.exchange.board.Board.idx}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L27)

cell name -> index; FormatError if it is not a cell of the board

#### `def adjacent(self, a, b)` {#pencilmark.exchange.board.Board.adjacent}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L34)

True if cells a and b share an edge

#### `def touching(self, a, b)` {#pencilmark.exchange.board.Board.touching}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L39)

True if cells a and b touch by an edge or a corner

#### `def pairs(self, steps, cells=None)` {#pencilmark.exchange.board.Board.pairs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L44)

forward neighbor pairs in the engine's order (puzzle_json._pairs): by cell, then by step.

#### `def windows2x2(self)` {#pencilmark.exchange.board.Board.windows2x2}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L57)

2x2 blocks of existing cells (TL, TR, BL, BR) in puzzle_json's global-entropy order (sorted by top-left).

#### `def is_block(self, cells)` {#pencilmark.exchange.board.Board.is_block}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L66)

True if the four cells are a 2x2 block written TL, TR, BL, BR

#### `def outside_side(self, cells)` {#pencilmark.exchange.board.Board.outside_side}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L73)

side of an outside clue whose ordered cells start next to it, or None

#### `def outside_ok(self, side, cells, diagonal_ok=True)` {#pencilmark.exchange.board.Board.outside_ok}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L98)

True if check_outside accepts cells on that side

#### `def check_outside(self, side, cells, diagonal_ok=True, what='outside clue')` {#pencilmark.exchange.board.Board.check_outside}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L106)

raise FormatError unless cells start just outside the grid on side and run away from it (diagonally too when diagonal_ok)

### `def subgrid_units(grid, n, box)` {#pencilmark.exchange.board.subgrid_units}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L136)

rows, columns, boxes of an n x n sub-grid given as n\*n engine cells in its reading order (puzzle_json's _layout_regions / standard order).

### `def window(B, r0, c0, n)` {#pencilmark.exchange.board.window}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L151)

indices of the n x n cells with top-left corner (r0, c0); None if one is missing

### `def grid_units(B, r0, c0, box=None)` {#pencilmark.exchange.board.grid_units}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L162)

houses of a grid at (r0, c0): its D rows (top to bottom), D columns (left to right) and, for a box_grid with box [bh, bw], its D boxes (reading order of their top-left cells). None if a cell of the D x D area is missing.

### `def grid_area(B, r0, c0)` {#pencilmark.exchange.board.grid_area}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L184)

set of the cell indices in the D x D square with top-left corner (r0, c0)

### `def read_houses(rules, B)` {#pencilmark.exchange.board.read_houses}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L189)

the house groups a rule list states, in engine order -> (houses [(kind, cells, extra)], areas [cell sets]) ([houses-and-regions](../formats/rules/houses-and-regions.mdx), 6.1): grid / box_grid / box / row / column rules in file order, a house equal to an earlier one skipped; areas = the grid / box_grid areas.

### `def battenburg_table(D, marked)` {#pencilmark.exchange.board.battenburg_table}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L229)

allowed 2x2 digit tuples (TL, TR, BL, BR) of a battenburg window, marked or unmarked

### `def vudoku_table(D)` {#pencilmark.exchange.board.vudoku_table}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L238)

allowed (x, y, z) triples: x is y + z or |y - z|

### `def product_pairs(D, p)` {#pencilmark.exchange.board.product_pairs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/board.py#L243)

digit pairs [u, v] in 1..D with u \* v == p

## pencilmark.exchange.validate {#pencilmark.exchange.validate}

[src/pencilmark/exchange/validate.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/validate.py)

Strict reading checks ([Puzzle format](../formats/puzzle-format.md) section 4): validate(doc) raises FormatError.

| Name | What it does |
|---|---|
| def [`validate`](#pencilmark.exchange.validate.validate) | strict reading ([Puzzle format](../formats/puzzle-format.md) section 4) of a format_version 1 dict; raises FormatError. |
| def [`area_cells`](#pencilmark.exchange.validate.area_cells) | an area ([Puzzle format](../formats/puzzle-format.md) 5): the origin of a grid / box_grid rule -> that grid's D x D cells… |
| def [`resolve_areas`](#pencilmark.exchange.validate.resolve_areas) | rules with every "area" replaced by its cell list ("cells"), as the engine expansion reads them |

### `def validate(doc)` {#pencilmark.exchange.validate.validate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/validate.py#L106)

strict reading ([Puzzle format](../formats/puzzle-format.md) section 4) of a format_version 1 dict; raises FormatError. Returns the Board.

### `def area_cells(B, a)` {#pencilmark.exchange.validate.area_cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/validate.py#L237)

an area ([Puzzle format](../formats/puzzle-format.md) 5): the origin of a grid / box_grid rule -> that grid's D x D cells in reading order, or a list of cell names -> those cells; as engine cell ids

### `def resolve_areas(B, rules)` {#pencilmark.exchange.validate.resolve_areas}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/validate.py#L276)

rules with every "area" replaced by its cell list ("cells"), as the engine expansion reads them

## pencilmark.exchange.read {#pencilmark.exchange.read}

[src/pencilmark/exchange/read.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/read.py)

Reading: a pencilmark-puzzle dict -> puzzle JSON / engine Puzzle (to_internal, read).

| Name | What it does |
|---|---|
| def [`to_internal`](#pencilmark.exchange.read.to_internal) | pencilmark-puzzle (format_version 1) -> puzzle JSON (pencilmark.puzzle_json) that builds the engine Puzzle. |
| def [`read`](#pencilmark.exchange.read.read) | pencilmark-puzzle dict -> engine Puzzle (not finalized) |

### `def to_internal(doc)` {#pencilmark.exchange.read.to_internal}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/read.py#L28)

pencilmark-puzzle (format_version 1) -> puzzle JSON (pencilmark.puzzle_json) that builds the engine Puzzle.

### `def read(doc)` {#pencilmark.exchange.read.read}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/read.py#L79)

pencilmark-puzzle dict -> engine Puzzle (not finalized)

## pencilmark.exchange.write {#pencilmark.exchange.write}

[src/pencilmark/exchange/write.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/write.py)

Writing: an engine Puzzle -> a canonical pencilmark-puzzle dict (write).

| Name | What it does |
|---|---|
| def [`write`](#pencilmark.exchange.write.write) | engine Puzzle -> pencilmark-puzzle dict (format_version 1). |

### `def write(p, meta=None, solution=None, provenance=False)` {#pencilmark.exchange.write.write}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/write.py#L32)

engine Puzzle -> pencilmark-puzzle dict (format_version 1). Raises NotSupportedError for engine structures the format cannot express. provenance=True returns (doc, prov): prov[i] = the engine objects rule i was written from ({"groups", "relations", "constraints", "clues"}: indices into p.groups / p.relations / p.constraints / p.cell_clues).

## pencilmark.exchange.canonical {#pencilmark.exchange.canonical}

[src/pencilmark/exchange/canonical.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py)

The canonical text and the content fingerprint ([Puzzle format](../formats/puzzle-format.md) 8).

| Name | What it does |
|---|---|
| def [`canonical`](#pencilmark.exchange.canonical.canonical) | key order of [Puzzle format](../formats/puzzle-format.md) 8.1 (content unchanged; a default origin left out) |
| def [`dumps`](#pencilmark.exchange.canonical.dumps) | canonical JSON text: fixed key order; pretty: givens / solution one grid row per line, one rule per line. |
| def [`jcs`](#pencilmark.exchange.canonical.jcs) | RFC 8785 JSON canonicalization for the values the fingerprint covers (integers, strings, lists, objects with… |
| def [`semantic_subset`](#pencilmark.exchange.canonical.semantic_subset) | the fingerprinted content: board, digits, givens, placed digits, candidates and rules, with the houses… |
| def [`fingerprint_of_doc`](#pencilmark.exchange.canonical.fingerprint_of_doc) | SHA-256 of the JCS form of the semantic subset of an already canonical pencilmark-puzzle dict, with the pair… |

### `def canonical(doc)` {#pencilmark.exchange.canonical.canonical}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L78)

key order of [Puzzle format](../formats/puzzle-format.md) 8.1 (content unchanged; a default origin left out)

### `def dumps(doc, pretty=True)` {#pencilmark.exchange.canonical.dumps}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L116)

canonical JSON text: fixed key order; pretty: givens / solution one grid row per line, one rule per line.

### `def jcs(x)` {#pencilmark.exchange.canonical.jcs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L139)

RFC 8785 JSON canonicalization for the values the fingerprint covers (integers, strings, lists, objects with ASCII keys, booleans, null): sorted keys, no whitespace, UTF-8.

### `def semantic_subset(doc)` {#pencilmark.exchange.canonical.semantic_subset}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L191)

the fingerprinted content: board, digits, givens, placed digits, candidates and rules, with the houses replaced by the houses they state (grid, box_grid, box / row / column rules), so every spelling of the same houses gives the same result, and set-like cell lists sorted

### `def fingerprint_of_doc(doc, by_meaning=())` {#pencilmark.exchange.canonical.fingerprint_of_doc}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L211)

SHA-256 of the JCS form of the semantic subset of an already canonical pencilmark-puzzle dict, with the pair tables and cell sets that state its pair and cell rules (puzzle-format.md 8.2) among the rules

## pencilmark.rules {#pencilmark.rules}

[src/pencilmark/rules/__init__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/__init__.py)

Rule families: what the public format knows about each family, in one place (step 5 of the restructure, docs/research/rule_families_plan.md). Readers, writers, words, drawing and the generator consult these tables instead of their own lists; the C++ engine keeps its own table (csrc/nary.hpp), checked against the engine kinds in model.py.

```
line   the line kinds (rules/line.py)
edge   the edge kinds (rules/edge.py)
cell   the cell kinds (rules/cell.py)
```

## pencilmark.rules.line {#pencilmark.rules.line}

[src/pencilmark/rules/line.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/line.py)

The `line` rule family ([lines-and-arrows](../formats/rules/lines-and-arrows.mdx)): every public kind with its parameters, whether it can be closed, and its words (the variant name and the one-sentence rule describe() writes). Parameters are REQUIRED when digits != 9 (on 9 x 9 each has a default the reader fills in).

| Name | What it does |
|---|---|
| class [`LineKind`](#pencilmark.rules.line.LineKind) |  |
| def [`line_to_engine`](#pencilmark.rules.line.line_to_engine) | a public line rule -> the engine's rules (exchange's reader): a line constraint, or for double_arrow an… |
| def [`line_from_engine`](#pencilmark.rules.line.line_from_engine) | an engine line constraint -> public rules (exchange's writer); a kropki chain becomes its kropki edges |

### `class LineKind` {#pencilmark.rules.line.LineKind}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/line.py#L34)

*No docstring.*

### `def line_to_engine(r, D, B, pairs_rule)` {#pencilmark.rules.line.line_to_engine}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/line.py#L139)

a public line rule -> the engine's rules (exchange's reader): a line constraint, or for double_arrow an equal sum

### `def line_from_engine(c, B, D)` {#pencilmark.rules.line.line_from_engine}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/line.py#L167)

an engine line constraint -> public rules (exchange's writer); a kropki chain becomes its kropki edges

## pencilmark.rules.edge {#pencilmark.rules.edge}

[src/pencilmark/rules/edge.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/edge.py)

The `edge` rule family ([edges-and-corners](../formats/rules/edges-and-corners.mdx)): every public kind with its one parameter, its words (the variant name, the one-sentence rule describe() writes, the noun a card note uses) and how it is drawn; and the translation between an edge clue and the engine's pair relation, both ways, with the "all clues shown" negatives.

| Name | What it does |
|---|---|
| class [`EdgeKind`](#pencilmark.rules.edge.EdgeKind) |  |
| def [`edge_value_ok`](#pencilmark.rules.edge.edge_value_ok) | a numbered edge clue (difference / sum / product / ratio) some pair of different digits 1..D satisfies |
| def [`edge_relation`](#pencilmark.rules.edge.edge_relation) |  |
| def [`edge_family`](#pencilmark.rules.edge.edge_family) | (family, value) a pair relation is written as when it is an edge clue, or None |
| def [`edge_rule`](#pencilmark.rules.edge.edge_rule) |  |
| def [`negative_relation`](#pencilmark.rules.edge.negative_relation) | -> list of (kind, args) for an uncovered pair, in expansion order |

### `class EdgeKind` {#pencilmark.rules.edge.EdgeKind}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/edge.py#L63)

*No docstring.*

### `def edge_value_ok(kind, value, D)` {#pencilmark.rules.edge.edge_value_ok}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/edge.py#L154)

a numbered edge clue (difference / sum / product / ratio) some pair of different digits 1..D satisfies

### `def edge_relation(rule, D)` {#pencilmark.rules.edge.edge_relation}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/edge.py#L161)

*No docstring.*

### `def edge_family(kind, args, D)` {#pencilmark.rules.edge.edge_family}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/edge.py#L182)

(family, value) a pair relation is written as when it is an edge clue, or None

### `def edge_rule(family, value, a, b, B)` {#pencilmark.rules.edge.edge_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/edge.py#L210)

*No docstring.*

### `def negative_relation(of, sel, D)` {#pencilmark.rules.edge.negative_relation}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/edge.py#L219)

-> list of (kind, args) for an uncovered pair, in expansion order

## pencilmark.rules.cell {#pencilmark.rules.cell}

[src/pencilmark/rules/cell.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/cell.py)

The `cell` rule family ([cell-clues](../formats/rules/cell-clues.mdx)): every public kind with its parameter, the variant it belongs to (odd and even make one variant, low and high another), whether the "every cell of the kind is marked" negative is defined, and how it is drawn.

| Name | What it does |
|---|---|
| class [`CellKind`](#pencilmark.rules.cell.CellKind) |  |

### `class CellKind` {#pencilmark.rules.cell.CellKind}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/cell.py#L34)

*No docstring.*

## pencilmark.rules.custom {#pencilmark.rules.custom}

[src/pencilmark/rules/custom.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py)

The custom rule language ([custom](../formats/rules/custom.mdx)): a rule written in the file as an expression over cell digits, {"type": "custom", "cells": {name: [cells]}, "holds": "2 \* max(c) == sum(c)", "scope"?, "each"?, "label"?}.

This module parses and checks an expression, evaluates it, prints its canonical form, describes it in words and compiles a rule to the engine's internal rules (pair relations and digit tables, which the C++ engine propagates). Grammar and semantics: docs/research/custom_rule_language_design.md (user decisions 2026-11-01 / 02).

Syntax (precedence from loose to tight):

```
let NAME = expr; expr          let a = 1, b = a + 1; expr          let NAME(a, b) = expr; expr
x => expr      (a, b) => expr                                        (predicates: scopes, upto, take_while, ...)
if expr then expr else expr
expr ?? expr                                                         (a default for an absent value)
or   and   not
== != < <= > >=   in   not in                                        (non-associative)
+ -    * / div mod    unary -    **  (right-associative)
postfix: f(args)   L[i]   L[a..b]
atoms: numbers, true, false, names, (expr), [a, b], [e for x in L if P], {a, b}, {a..b}
f(e for x in L if P) is f([e for x in L if P]).
```

Values: exact rationals, booleans, lists, sets, cells (a cell is its digit in arithmetic; row / col / box give its position) and ABSENT (an index out of range, a division by zero): arithmetic with ABSENT is ABSENT, a comparison with ABSENT is false (!= too), `defined(x)` and `x ?? d` handle edges.

| Name | What it does |
|---|---|
| class [`LangError`](#pencilmark.rules.custom.LangError) | a malformed expression: the message names the position |
| def [`lex`](#pencilmark.rules.custom.lex) |  |
| class [`N`](#pencilmark.rules.custom.N) | one node: op names the construct, args its parts (nodes or plain values) |
| class [`Parser`](#pencilmark.rules.custom.Parser) |  |
| def [`parse`](#pencilmark.rules.custom.parse) |  |
| class [`Cell`](#pencilmark.rules.custom.Cell) |  |
| def [`num`](#pencilmark.rules.custom.num) | a value as a number (a cell is its digit); ABSENT stays ABSENT |
| def [`is_prime`](#pencilmark.rules.custom.is_prime) |  |
| class [`Env`](#pencilmark.rules.custom.Env) | names: cell lists ({name: [cell names] or lists of lists}), the grid ({cell name: digit}) and the box shape |
| def [`call_fn`](#pencilmark.rules.custom.call_fn) |  |
| def [`builtin`](#pencilmark.rules.custom.builtin) |  |
| def [`evaluate`](#pencilmark.rules.custom.evaluate) |  |
| def [`holds`](#pencilmark.rules.custom.holds) | does the rule hold for this filling? |
| def [`check`](#pencilmark.rules.custom.check) | static checks on load: known names and functions, arities, conditions where conditions are needed, a… |
| def [`show`](#pencilmark.rules.custom.show) | the canonical text: single spaces around binary operators, minimal parentheses |
| def [`canonical`](#pencilmark.rules.custom.canonical) |  |
| def [`describe`](#pencilmark.rules.custom.describe) | the rule in words, from the expression itself (decision 4): per-operator phrases |
| def [`rule_holds`](#pencilmark.rules.custom.rule_holds) | does a custom rule {"type": "custom", "cells": {...}, "holds": "...", "scope"?, "each"?} hold for a filled… |
| def [`compile_rule`](#pencilmark.rules.custom.compile_rule) | a custom rule -> internal puzzle rules for the engine: {"type": "pairs", "rel": "allowed", ...} for pair… |
| def [`B_box`](#pencilmark.rules.custom.B_box) | the board's box shape for box(): standard boxes of its size |
| def [`describe_rule`](#pencilmark.rules.custom.describe_rule) | a whole custom rule in words: its scope, then the condition |
| def [`to_ir`](#pencilmark.rules.custom.to_ir) | a custom rule (no scope) -> (ir, cell names, cell lists): ir nested lists of ints; cell names the engine… |

### `class LangError(FormatError)` {#pencilmark.rules.custom.LangError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L40)

a malformed expression: the message names the position

### `def lex(src)` {#pencilmark.rules.custom.lex}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L44)

*No docstring.*

### `class N` {#pencilmark.rules.custom.N}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L63)

one node: op names the construct, args its parts (nodes or plain values)

### `class Parser` {#pencilmark.rules.custom.Parser}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L74)

*No docstring.*

#### `def peek(self, k=0)` {#pencilmark.rules.custom.Parser.peek}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L78)

*No docstring.*

#### `def at(self, *vals)` {#pencilmark.rules.custom.Parser.at}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L81)

*No docstring.*

#### `def take(self, val=None)` {#pencilmark.rules.custom.Parser.take}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L84)

*No docstring.*

#### `def parse(self)` {#pencilmark.rules.custom.Parser.parse}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L91)

*No docstring.*

#### `def expr(self)` {#pencilmark.rules.custom.Parser.expr}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L97)

*No docstring.*

#### `def default(self)` {#pencilmark.rules.custom.Parser.default}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L151)

*No docstring.*

#### `def disj(self)` {#pencilmark.rules.custom.Parser.disj}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L158)

*No docstring.*

#### `def conj(self)` {#pencilmark.rules.custom.Parser.conj}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L165)

*No docstring.*

#### `def neg(self)` {#pencilmark.rules.custom.Parser.neg}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L172)

*No docstring.*

#### `def cmp(self)` {#pencilmark.rules.custom.Parser.cmp}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L178)

*No docstring.*

#### `def add(self)` {#pencilmark.rules.custom.Parser.add}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L194)

*No docstring.*

#### `def mul(self)` {#pencilmark.rules.custom.Parser.mul}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L201)

*No docstring.*

#### `def unary(self)` {#pencilmark.rules.custom.Parser.unary}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L208)

*No docstring.*

#### `def power(self)` {#pencilmark.rules.custom.Parser.power}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L214)

*No docstring.*

#### `def postfix(self)` {#pencilmark.rules.custom.Parser.postfix}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L221)

*No docstring.*

#### `def comprehension(self, body)` {#pencilmark.rules.custom.Parser.comprehension}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L250)

*No docstring.*

#### `def atom(self)` {#pencilmark.rules.custom.Parser.atom}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L261)

*No docstring.*

### `def parse(src)` {#pencilmark.rules.custom.parse}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L313)

*No docstring.*

### `class Cell` {#pencilmark.rules.custom.Cell}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L329)

*No docstring.*

#### `def rc(self)` {#pencilmark.rules.custom.Cell.rc}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L334)

*No docstring.*

### `def num(v)` {#pencilmark.rules.custom.num}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L339)

a value as a number (a cell is its digit); ABSENT stays ABSENT

### `def is_prime(n)` {#pencilmark.rules.custom.is_prime}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L352)

*No docstring.*

### `class Env` {#pencilmark.rules.custom.Env}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L360)

names: cell lists ({name: [cell names] or lists of lists}), the grid ({cell name: digit}) and the box shape

#### `def child(self, **binds)` {#pencilmark.rules.custom.Env.child}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L370)

*No docstring.*

#### `def lookup(self, name)` {#pencilmark.rules.custom.Env.lookup}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L373)

*No docstring.*

### `def call_fn(f, args, env)` {#pencilmark.rules.custom.call_fn}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L420)

*No docstring.*

### `def builtin(name)` {#pencilmark.rules.custom.builtin}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L437)

*No docstring.*

### `def evaluate(e, env)` {#pencilmark.rules.custom.evaluate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L584)

*No docstring.*

### `def holds(expr, cells, grid, box=(3, 3), layers=None, unknowns=None)` {#pencilmark.rules.custom.holds}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L717)

does the rule hold for this filling? (expr: text or a parsed tree; layers / unknowns: Env.layers / unknowns)

### `def check(tree, names, unknowns=(), layers=())` {#pencilmark.rules.custom.check}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L735)

static checks on load: known names and functions, arities, conditions where conditions are needed, a condition at the top. names: the cell list names; unknowns / layers: the file's named unknowns (numbers) and layers (functions of one cell). Returns the top type ('bool', 'num', 'list', 'fn').

### `def show(e, parent=0, right=False)` {#pencilmark.rules.custom.show}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L835)

the canonical text: single spaces around binary operators, minimal parentheses

### `def canonical(src)` {#pencilmark.rules.custom.canonical}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L888)

*No docstring.*

### `def describe(e)` {#pencilmark.rules.custom.describe}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L909)

the rule in words, from the expression itself (decision 4): per-operator phrases

### `def rule_holds(rule, grid, box=(3, 3), layers=None)` {#pencilmark.rules.custom.rule_holds}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L992)

does a custom rule {"type": "custom", "cells": {...}, "holds": "...", "scope"?, "each"?} hold for a filled grid? scope: {"pairs": kind} (holds is a predicate (a, b)), {"windows": [h, w]} (a predicate over the window's cells in reading order), {"cells": name, "neighbors": kind, "within": "box"?} (a predicate (x, N)); each with "except" (cell lists to skip). "each": name -> the rule holds for every tuple of that list of lists, bound to the name.

### `def compile_rule(rule, B, D, layers=())` {#pencilmark.rules.custom.compile_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L1205)

a custom rule -> internal puzzle rules for the engine: {"type": "pairs", "rel": "allowed", ...} for pair scopes, {"type": "table", "cells", "allowed"} otherwise. B: the board helper (exchange.board.Board). Raises LangError when the rule is malformed or too large for a table.

### `def B_box(B)` {#pencilmark.rules.custom.B_box}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L1337)

the board's box shape for box(): standard boxes of its size

### `def describe_rule(rule)` {#pencilmark.rules.custom.describe_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L1344)

a whole custom rule in words: its scope, then the condition

### `def to_ir(rule, unknowns=(), layers=())` {#pencilmark.rules.custom.to_ir}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/custom.py#L1379)

a custom rule (no scope) -> (ir, cell names, cell lists): ir nested lists of ints; cell names the engine variables in order; cell lists the rule's named lists as variable indices (nested for lists of lists). unknowns / layers: the file's names in order; an unknown is read as ["aux", its index], a layer call L(x) as ["auxcell", L's index, x] (the engine's aux variables: unknowns first, then each layer's value per board cell)

## pencilmark.puzzle_json {#pencilmark.puzzle_json}

[src/pencilmark/puzzle_json.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py)

Puzzle &lt;-> JSON: the storage / exchange format for any sudoku the engine supports.

Minimal (classic, any standard size; boxes implied): {"numbers": "..3.2.6..9..3.5..1..18.64...."}          # '.' or '0' blank, 1-9 then A-Z above 9 Full form (every field optional except what the puzzle needs): { "digits": 9,                                          # D: digits 1..D "shape": ["#########.....", ...],                     # cells on the bounding grid: '#' cell, '.' void #   (omit for a full D x D board) "box": "3x3",                                         # implied rows / columns / boxes of a D x D board "layout": "samurai",                                  # implied regions of a named multi-grid layout "numbers": "...",                                     # givens, row-major over the bounding grid ('#' = void) "solution": "...", "regions": [{"kind": "row|col|box|region|diag|window|cage|extra", "cells": ["r1c1", ...], "sum": 15, "unique": true}, ...],       # explicit no-repeat groups (when not implied) "rules": [{"type": "kropki", "color": "white", "cells": ["r1c1", "r1c2"]}, {"type": "line", "kind": "thermo", "cells": [...]},     # any engine line kind, bulb first {"type": "antiknight"}, {"type": "antiking"}, {"type": "nonconsecutive"}, {"type": "frame", "side": "top", "index": 3, "sum": 12},              # first 3 cells from that edge {"type": "rossini", "arrows": [{"side": "left", "index": 2, "towards": "in"}], "all_given": true}, {"type": "vudoku", "cells": ["r2c2", "r1c2", "r2c3"]},   # vertex = sum or difference of the arms {"type": "lowhigh", "high": ["r1c1", ...], "split": 5},  # marked 6..9, the rest 1..5 {"type": "parity", "parity": "odd", "cells": [...]},    # shaded odd / even cells (graphical) {"type": "digit_class", "digits": "123", "cells": [...]},  # cells marked as holding one of these digits {"type": "exclude", "digit": 5, "cells": [...]},         # a circle: its digit is in none of these cells {"type": "increasing", "cells": [...]}, (Bold X / Snowflake / Argyle / Asterisk ...: their lines or cells as extra "regions") {"type": "pairs", "rel": "notdiff", "params": [1], "cells": [["r1c1", "r1c2"], ...]}, {"type": "pairs", "rel": "notsum", "params": [10], "where": "orthogonal", "except": [["r1c1", "r1c2"]]}, # whole-grid pair rule: every orthogonal / diagonal / king / knight # neighbor pair except those listed (e.g. "no X where not marked") {"type": "&lt;engine constraint>", ...}, ...],               # arrow, sum, little_killer, sandwich ... "candidates": {"r1c1": "137"},                       # given pencil marks (Sukaku); shaded clues are rules above "meta": {"title": "...", "author": "...", "rules_text": "...", "source": "...", "id": "..."}} # optional metadata, never used for solving (top level) Cells are 'r{row}c{col}', 1-based on the bounding grid. Regions are the no-repeat groups (for each sub-grid its rows, columns and boxes); boxes are what a renderer draws with thick lines. Rows / columns / boxes of a D x D board (or a named layout) are implied unless "regions" overrides them. from_json(obj or str) -> Puzzle (not finalized)      to_json(Puzzle) -> dict      canonical_hash(obj) -> md5

| Name | What it does |
|---|---|
| def [`from_json`](#pencilmark.puzzle_json.from_json) | puzzle JSON (dict or str) -> Puzzle, not finalized; ValueError for unknown keys or an unknown layout |
| def [`entropy_table`](#pencilmark.puzzle_json.entropy_table) | 2x2 window (TL, TR, BL, BR) with a low, a middle and a high digit, classes = thirds of 1..D (sudoku.coach's… |
| def [`quadruple_table`](#pencilmark.puzzle_json.quadruple_table) | every n-digit tuple over 1..D that holds each digit of need at least as often as need does |
| def [`add_named`](#pencilmark.puzzle_json.add_named) | apply a named rule (cells as engine indices or "r1c1" names) to an engine Puzzle and remember it (for… |
| def [`to_json`](#pencilmark.puzzle_json.to_json) | Puzzle -> puzzle JSON dict; solution and meta are written when given |
| def [`canonical_hash`](#pencilmark.puzzle_json.canonical_hash) | md5 of the canonical puzzle definition (sorted keys, no metadata) -- the same puzzle from two sources dedupes. |

### `def from_json(obj) -> M.Puzzle` {#pencilmark.puzzle_json.from_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L168)

puzzle JSON (dict or str) -> Puzzle, not finalized; ValueError for unknown keys or an unknown layout

### `def entropy_table(D)` {#pencilmark.puzzle_json.entropy_table}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L482)

2x2 window (TL, TR, BL, BR) with a low, a middle and a high digit, classes = thirds of 1..D (sudoku.coach's rule).

### `def quadruple_table(D, n, need)` {#pencilmark.puzzle_json.quadruple_table}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L490)

every n-digit tuple over 1..D that holds each digit of need at least as often as need does

### `def add_named(p, rule)` {#pencilmark.puzzle_json.add_named}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L499)

apply a named rule (cells as engine indices or "r1c1" names) to an engine Puzzle and remember it (for importers that build Puzzles directly).

### `def to_json(p: M.Puzzle, solution=None, meta=None) -> dict` {#pencilmark.puzzle_json.to_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L563)

Puzzle -> puzzle JSON dict; solution and meta are written when given

### `def canonical_hash(obj) -> str` {#pencilmark.puzzle_json.canonical_hash}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L742)

md5 of the canonical puzzle definition (sorted keys, no metadata) -- the same puzzle from two sources dedupes.

## pencilmark.interop {#pencilmark.interop}

[src/pencilmark/interop.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py)

Interop strings and ipuz export ([Other formats](../formats/other-formats.md)).

from_string(s) -> pencilmark-puzzle dict        plain classic strings (also as text grids with | - + separators, or with a

```
                                            trailing comment), pencil-mark grids, 729-character candidate strings, HoDoKu
                                            library lines, and
                                            sudokuwiki.org packed strings (S9B, S6B, X9B, W9B, C9B, J9B, L9B, M9B, L6C)
to_string(puzzle, "plain" | "grid" | "sudokuwiki")   the reverse (refuses what the target cannot express)
to_ipuz(puzzle) -> dict                     ipuz 2 for classic / Latin square / diagonal / windoku / jigsaw / killer
from_ipuz(ipuz) -> pencilmark-puzzle dict       the reverse (boxes, zones, cages); a to_ipuz file returns its embedded puzzle
```

The sudokuwiki encodings are checked against sudokuwiki.org's solver; the decoder reads exactly what the encoder writes and refuses anything else (candidates and placed digits in killer forms, 6x6 killer operators other than '+'). In the non-killer forms a cell is Andrew Stuart's board-state code (sudokuwiki.org makePackedStringVB): a given digit d, a placed digit d + D (read as placed), candidate mask m + 18 (bit i = digit i + 1; read as the cell's candidates), or 0 (nothing stored, an empty cell), so one string carries a whole mid-solve board.

| Name | What it does |
|---|---|
| def [`text_form`](#pencilmark.interop.text_form) | the text form of s: "sudokuwiki", "hodoku", "pencil_marks", "candidates", "grid" (rows on lines), "plain"… |
| def [`read_sudokuwiki`](#pencilmark.interop.read_sudokuwiki) |  |
| def [`read_hodoku`](#pencilmark.interop.read_hodoku) |  |
| def [`read_pencil_marks`](#pencilmark.interop.read_pencil_marks) |  |
| def [`read_candidates`](#pencilmark.interop.read_candidates) |  |
| def [`read_grid`](#pencilmark.interop.read_grid) |  |
| def [`read_plain`](#pencilmark.interop.read_plain) | one string of D x D characters, maybe followed by a comment; symbols: the symbol of each digit in order |
| def [`to_string`](#pencilmark.interop.to_string) | engine Puzzle / any accepted input -> plain classic string or sudokuwiki packed string |
| def [`is_classic9`](#pencilmark.interop.is_classic9) | a classic 9 x 9 sudoku: standard rows, columns and boxes, nothing else (what Sudoku Explainer rates) |
| def [`analyse`](#pencilmark.interop.analyse) | -> (kind or None, info) for the sudokuwiki forms |
| def [`to_ipuz`](#pencilmark.interop.to_ipuz) | pencilmark-puzzle (or any accepted input) -> ipuz 2 dict, for classic / Latin square / diagonal / windoku /… |
| def [`from_ipuz`](#pencilmark.interop.from_ipuz) | ipuz sudoku (dict or JSON text) -> pencilmark-puzzle dict. |

### `def text_form(s)` {#pencilmark.interop.text_form}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L64)

the text form of s: "sudokuwiki", "hodoku", "pencil_marks", "candidates", "grid" (rows on lines), "plain" (one string, maybe followed by a comment), or None

### `def read_sudokuwiki(s)` {#pencilmark.interop.read_sudokuwiki}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L117)

*No docstring.*

### `def read_hodoku(s)` {#pencilmark.interop.read_hodoku}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L123)

*No docstring.*

### `def read_pencil_marks(s)` {#pencilmark.interop.read_pencil_marks}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L128)

*No docstring.*

### `def read_candidates(s)` {#pencilmark.interop.read_candidates}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L133)

*No docstring.*

### `def read_grid(s)` {#pencilmark.interop.read_grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L138)

*No docstring.*

### `def read_plain(s, symbols=None)` {#pencilmark.interop.read_plain}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L143)

one string of D x D characters, maybe followed by a comment; symbols: the symbol of each digit in order

### `def to_string(puzzle, form='plain')` {#pencilmark.interop.to_string}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L379)

engine Puzzle / any accepted input -> plain classic string or sudokuwiki packed string

### `def is_classic9(p)` {#pencilmark.interop.is_classic9}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L409)

a classic 9 x 9 sudoku: standard rows, columns and boxes, nothing else (what Sudoku Explainer rates)

### `def analyse(p)` {#pencilmark.interop.analyse}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L442)

-> (kind or None, info) for the sudokuwiki forms

### `def to_ipuz(puzzle)` {#pencilmark.interop.to_ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L633)

pencilmark-puzzle (or any accepted input) -> ipuz 2 dict, for classic / Latin square / diagonal / windoku / jigsaw / killer and their combinations; refuses everything else with NotSupportedError.

### `def from_ipuz(ipuz)` {#pencilmark.interop.from_ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L734)

ipuz sudoku (dict or JSON text) -> pencilmark-puzzle dict. Reads `puzzle`, `solution`, `boxes`, `zones` (jigsaw boxes, diagonals, windows, other regions) and `cages`; a file written by to_ipuz gives back its embedded puzzle unless the grid was edited. Refuses kinds other than sudoku and cells it cannot read.

## pencilmark.spec_format {#pencilmark.spec_format}

[src/pencilmark/spec_format.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py)

The "pencilmark-spec" generator request ([Generator spec](../formats/generator-spec.md)): a puzzle file with blanks.

validate_spec(doc)                    strict reading of the spec language (unknown keys refused)

```
spec_to_gen(doc) -> dict              the part pencilmark.gen can run, as a Spec dict; anything else -> NotSupportedError
spec_from_gen(spec) -> dict           pencilmark.gen Spec (or dict) -> pencilmark-spec
gen_support(doc) -> (bool, reason)    can pencilmark.gen run it today?
```

What pencilmark.gen runs today: gap-free D x D boards (4, 6, 8, 9, 10, 12, 16) with the standard box_grid, or a named layout of 9 x 9 grids (one box_grid per grid); locked rules of different digits; templates for cages, thermo / whisper / renban / between lines, arrows, kropki / XV, parity cells, with counts (incl. "all", "min", "tile", "max") and shape limits (size, sum, length); givens count and per grid; one symmetry of the givens; where: band, difficulty range or "max" / "min", contains (codes), elements max; limits: time, seed. Everything else in a spec is refused with the reason, never ignored.

| Name | What it does |
|---|---|
| def [`validate_spec`](#pencilmark.spec_format.validate_spec) | strict reading of a pencilmark-spec ([Generator spec](../formats/generator-spec.md)); locked rules are checked like puzzle… |
| def [`spec_to_gen`](#pencilmark.spec_format.spec_to_gen) | pencilmark-spec -> pencilmark.gen Spec dict; NotSupportedError naming the first part the generator cannot run |
| def [`gen_support`](#pencilmark.spec_format.gen_support) | (True, "") when pencilmark.gen can run the spec today, else (False, reason) |
| def [`spec_from_gen`](#pencilmark.spec_format.spec_from_gen) | pencilmark.gen Spec (or its dict) -> pencilmark-spec dict |
| def [`spec_fingerprint`](#pencilmark.spec_format.spec_fingerprint) |  |

### `def validate_spec(doc)` {#pencilmark.spec_format.validate_spec}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L113)

strict reading of a pencilmark-spec ([Generator spec](../formats/generator-spec.md)); locked rules are checked like puzzle rules

### `def spec_to_gen(doc)` {#pencilmark.spec_format.spec_to_gen}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L283)

pencilmark-spec -> pencilmark.gen Spec dict; NotSupportedError naming the first part the generator cannot run

### `def gen_support(doc)` {#pencilmark.spec_format.gen_support}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L437)

(True, "") when pencilmark.gen can run the spec today, else (False, reason)

### `def spec_from_gen(spec)` {#pencilmark.spec_format.spec_from_gen}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L446)

pencilmark.gen Spec (or its dict) -> pencilmark-spec dict

### `def spec_fingerprint(doc)` {#pencilmark.spec_format.spec_fingerprint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L531)

*No docstring.*

## pencilmark.variants {#pencilmark.variants}

[src/pencilmark/variants.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py)

Variant registry: names, rule text and recognition ([variant-naming](../library/variant-naming.md)). Not part of the file format: variant names appear only in meta.type and in describe() output.

describe(puzzle) -> {"type": "Killer Sudoku", "rules": {"Sudoku": "...", "Killer": "...", ...}}

```
rules_text(described) -> "Sudoku: ...\nKiller: ..."
```

Two kinds of entries: @variant(name, aliases=..., text=...)   a PLACEMENT variant: fn(g) -> the rules it adds to ONE grid area g, or None where the variant is not defined for that area (size / box shape). Works for any size: windoku(g) on a 16x16 grid places its 9 windows. @family(name, match=..., text=...)      a RULE-FAMILY variant (killer, thermo, kropki, ...): recognized by rule type / kind; text(rules, ctx) writes its sentence. Recognition: for each grid area, every placement variant's rules are compared with the puzzle's rules as sets of (type, kind, cell set) -- region kinds are drawing hints and are ignored; if all are present the variant applies and those rules are explained. Remaining rules get their family names; anything unknown falls back to a generic name. Generator presets: the placement functions are also the presets a generator can use (preset_rules(name, size)); the current generator (pencilmark.gen) places only its own element kinds, so preset generation of placement variants is a next step.

| Name | What it does |
|---|---|
| class [`Grid`](#pencilmark.variants.Grid) | one grid area (a grid / box_grid, or the whole board): n x n cells, box bh x bw (None for a jigsaw / Latin… |
| class [`Variant`](#pencilmark.variants.Variant) | a registered variant: name, aliases and rule text, with a placement function or a family matcher |
| def [`variant`](#pencilmark.variants.variant) | decorator: register fn as the placement variant name |
| def [`family`](#pencilmark.variants.family) | register a family variant (no placement function) with its matcher, rule text and aliases |
| def [`region`](#pencilmark.variants.region) | region rule dict of the given kind over cells |
| def [`x_sudoku`](#pencilmark.variants.x_sudoku) | the two main diagonals as diagonal regions |
| def [`windoku`](#pencilmark.variants.windoku) | the windoku windows as window regions; None without boxes |
| def [`argyle`](#pencilmark.variants.argyle) | the eight argyle diagonals as regions; 9x9 only, else None |
| def [`asterisk`](#pencilmark.variants.asterisk) | the nine asterisk cells as one region; 9x9 only, else None |
| def [`centre_dot`](#pencilmark.variants.centre_dot) | the center cell of every box as one region; None unless the boxes have odd sides |
| def [`girandola`](#pencilmark.variants.girandola) | the nine girandola cells as one region; 9x9 only, else None |
| def [`disjoint`](#pencilmark.variants.disjoint) | one region per position inside a box (the cells at that position in every box); None without boxes |
| def [`layout_name`](#pencilmark.variants.layout_name) | name of a multi-grid layout from its subgrid origins (0-based), or None |
| def [`size_word`](#pencilmark.variants.size_word) | title word for a grid size: Tiny (4), Mini (6), nothing (9), else DxD |
| def [`describe`](#pencilmark.variants.describe) | variant name and rules (an ordered key -> sentence map, like Logic Masters rule headers) from the rules alone. |
| def [`grid_names`](#pencilmark.variants.grid_names) | position names of the grids of a multi-grid board ("top-left", "center", …), or "grid at r7c7" where… |
| def [`type_name`](#pencilmark.variants.type_name) | the variant name in a naming scheme: "name" = describe's ("Killer Sudoku"; two or more variants: "Variant… |
| def [`variant_ids`](#pencilmark.variants.variant_ids) | the variants as snake_case ids, like tags: ["jigsaw", "killer", "german_whispers"] (multi-grid layouts… |
| def [`format_title`](#pencilmark.variants.format_title) | a title / subtitle template filled in: {type} (scheme after a colon: {type:list}), {variants} (the variant… |
| def [`public`](#pencilmark.variants.public) | describe() as the library shows it (pencilmark.describe, the card's describe field): type, rules,… |
| def [`rules_text`](#pencilmark.variants.rules_text) | 'Key: sentence' lines (used only to fill an empty meta.rules_text) |
| def [`preset_rules`](#pencilmark.variants.preset_rules) | the rules a placement variant adds to a size x size board with standard boxes (a generator preset); None… |

### `class Grid` {#pencilmark.variants.Grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L33)

one grid area (a grid / box_grid, or the whole board): n x n cells, box bh x bw (None for a jigsaw / Latin square). Local coordinates are 0-based.

#### `def cell(self, r, c)` {#pencilmark.variants.Grid.cell}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L43)

name of the cell at local (r, c)

#### `def block(self, r, c, h, w)` {#pencilmark.variants.Grid.block}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L49)

names of the h x w cells with top-left corner (r, c), row by row

#### `def cells_set(self)` {#pencilmark.variants.Grid.cells_set}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L53)

names of all n x n cells, row by row

#### `def diagonal(self)` {#pencilmark.variants.Grid.diagonal}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L57)

names of the cells on the main diagonal

#### `def antidiagonal(self)` {#pencilmark.variants.Grid.antidiagonal}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L61)

names of the cells on the diagonal from top right to bottom left

#### `def boxes(self)` {#pencilmark.variants.Grid.boxes}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L65)

top-left (r, c) of every box; empty for a jigsaw or Latin square

#### `def window_starts(self)` {#pencilmark.variants.Grid.window_starts}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L71)

top-left corners of the windoku windows: box-sized windows one cell in from each box border, spaced one cell apart (9x9: r2c2, r2c6, r6c2, r6c6)

#### `def line(self, r, c, dr, dc, length)` {#pencilmark.variants.Grid.line}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L83)

names of length cells from (r, c) stepping (dr, dc)

### `class Variant` {#pencilmark.variants.Variant}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L89)

a registered variant: name, aliases and rule text, with a placement function or a family matcher

### `def variant(name, aliases=(), text='')` {#pencilmark.variants.variant}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L104)

decorator: register fn as the placement variant name

### `def family(name, match, text, aliases=())` {#pencilmark.variants.family}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L114)

register a family variant (no placement function) with its matcher, rule text and aliases

### `def region(cells, kind='extra')` {#pencilmark.variants.region}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L119)

region rule dict of the given kind over cells

### `def x_sudoku(g)` {#pencilmark.variants.x_sudoku}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L126)

the two main diagonals as diagonal regions

### `def windoku(g)` {#pencilmark.variants.windoku}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L132)

the windoku windows as window regions; None without boxes

### `def argyle(g)` {#pencilmark.variants.argyle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L141)

the eight argyle diagonals as regions; 9x9 only, else None

### `def asterisk(g)` {#pencilmark.variants.asterisk}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L158)

the nine asterisk cells as one region; 9x9 only, else None

### `def centre_dot(g)` {#pencilmark.variants.centre_dot}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L166)

the center cell of every box as one region; None unless the boxes have odd sides

### `def girandola(g)` {#pencilmark.variants.girandola}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L174)

the nine girandola cells as one region; 9x9 only, else None

### `def disjoint(g)` {#pencilmark.variants.disjoint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L186)

one region per position inside a box (the cells at that position in every box); None without boxes

### `def layout_name(subgrids, extra=0)` {#pencilmark.variants.layout_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L444)

name of a multi-grid layout from its subgrid origins (0-based), or None

### `def size_word(D)` {#pencilmark.variants.size_word}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L463)

title word for a grid size: Tiny (4), Mini (6), nothing (9), else DxD

### `def describe(puzzle)` {#pencilmark.variants.describe}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L483)

variant name and rules (an ordered key -> sentence map, like Logic Masters rule headers) from the rules alone.

### `def grid_names(grids)` {#pencilmark.variants.grid_names}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L664)

position names of the grids of a multi-grid board ("top-left", "center", …), or "grid at r7c7" where positions would be ambiguous

### `def type_name(described, scheme='name')` {#pencilmark.variants.type_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L704)

the variant name in a naming scheme: "name" = describe's ("Killer Sudoku"; two or more variants: "Variant Sudoku"), "list" = every variant ("Jigsaw Killer Renban Kropki Sudoku")

### `def variant_ids(described)` {#pencilmark.variants.variant_ids}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L714)

the variants as snake_case ids, like tags: ["jigsaw", "killer", "german_whispers"] (multi-grid layouts first: "samurai"); a plain sudoku has none

### `def format_title(template, described, values=None)` {#pencilmark.variants.format_title}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L738)

a title / subtitle template filled in: {type} (scheme after a colon: {type:list}), {variants} (the variant names, comma-separated), {size} ("9x9"), and from values: {band}, {difficulty}, {time} (minutes), {givens}, {seed}. {{ and }} are literal braces. Raises ValueError for an unknown field or scheme.

### `def public(described)` {#pencilmark.variants.public}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L756)

describe() as the library shows it (pencilmark.describe, the card's describe field): type, rules, rules_text, variants

### `def rules_text(described)` {#pencilmark.variants.rules_text}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L763)

'Key: sentence' lines (used only to fill an empty meta.rules_text)

### `def preset_rules(name, size=9, box=None)` {#pencilmark.variants.preset_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L768)

the rules a placement variant adds to a size x size board with standard boxes (a generator preset); None where the variant is not defined for that size

## pencilmark.render {#pencilmark.render}

[src/pencilmark/render.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/render.py)

Draw a puzzle as SVG, following the default drawing ([drawing-style](../library/drawing-style.md); sizes and colors in data/palette.json).

import pencilmark

```
svg = pencilmark.draw("....4.8.3.6...8..2...")             # any format pencilmark.read reads, or its document
svg = pencilmark.draw(doc, dark=True, cell=36)
svg = pencilmark.draw(doc, card=card, position=38)         # one position of a card's trace (grade-card.md 6)
```

`svg` (pencilmark.draw) reads its input and draws it; `render` draws a pencilmark-puzzle document with every option; `trace_position` turns one position of a card's trace into render's colors / placed / marks.

| Name | What it does |
|---|---|
| def [`esc`](#pencilmark.render.esc) |  |
| def [`render`](#pencilmark.render.render) | svg text. |
| def [`trace_position`](#pencilmark.render.trace_position) | (colors, placed, marks) of position n of a card's trace: each color group's cells take its color (a cell in… |
| def [`svg`](#pencilmark.render.svg) | SVG text of a puzzle in the default drawing. |

### `def esc(s)` {#pencilmark.render.esc}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/render.py#L31)

*No docstring.*

### `def render(doc, dark=False, cell=48, annotate=False, labels=False, background=True, colors=None, placed=None, marks=None, open_sides=())` {#pencilmark.render.render}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/render.py#L35)

svg text. annotate: every element drawn for rules[i] carries data-rule="i" (pages link it to the JSON); labels: row numbers on the left and column numbers on top, outside the board and its outside clues. colors {cell name: [color names]}: annotation colors over the cells (one fills the cell; n split it into n wedges, as SudokuPad draws them); placed {cell name: digit}: digits the solver has written, in the placed ink; marks {cell name: {"corner": [...], "center": [...]}}: the solver's pencil marks (corner marks in the cell's corners and edges, center marks in a row across the middle), in the placed ink. open_sides ("left", "right", "top", "bottom"): leave the outer frame out there, for a cut-out of a larger board (the docs' small pictures).

### `def trace_position(doc, card, n)` {#pencilmark.render.trace_position}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/render.py#L701)

(colors, placed, marks) of position n of a card's trace: each color group's cells take its color (a cell in several groups gets them all), every digit not given is a placed one, and the marks layer as written

### `def svg(puzzle, *, dark=False, cell=48, card=None, position=None, labels=False, background=True, colors=None, placed=None, marks=None)` {#pencilmark.render.svg}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/render.py#L716)

SVG text of a puzzle in the default drawing.

puzzle: any format pencilmark.read reads (detected), or its document. dark: the dark theme. cell: the cell size in pixels. card / position: draw position `position` of the card's trace (a card rated with fields=["trace"]): its placed digits, its pencil marks and its color layer. labels: row and column numbers outside the board. background: False leaves the page transparent around the board. colors {cell name: [color names]}, placed {cell name: digit}, marks {cell name: {"corner": [...], "center": [...]}}: a solver's layers drawn over the puzzle (a card position's layers come first, these on top).
