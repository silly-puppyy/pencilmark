---
title: "Formats"
description: "Reading, checking and writing puzzles and generator requests; the rule families and the variant names."
toc_max_heading_level: 2
---

# Formats

Reading, checking and writing puzzles and generator requests; the rule families and the variant names. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.inputs {#pencilmark.inputs}

[src/pencilmark/inputs.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/inputs.py)

Reading a puzzle: every input form pencilmark accepts, in the order they are tried. load(), to_export() and the command line all read through here.

read(x)              -> a puzzle dict: puzzle JSON, a sudoku-puzzle document, an ipuz file or a sample-pack line

```
to_puzzle_json(obj)  -> puzzle JSON (pencilmark.puzzle_json), whatever read() returned
```

| Name | What it does |
|---|---|
| def [`link`](#pencilmark.inputs.link) | puzzle JSON for a site link or payload (pencilmark.sources: SudokuPad, f-puzzles, Penpa, Logic Masters,… |
| def [`read`](#pencilmark.inputs.read) | any accepted input -> a puzzle dict (see the module docstring); TypeError for an input of no known form |
| def [`to_puzzle_json`](#pencilmark.inputs.to_puzzle_json) | accept puzzle JSON, the sudoku-puzzle exchange format, an ipuz sudoku, or a sample-pack line {"puzzle": ...,… |

### `def link(s)` {#pencilmark.inputs.link}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/inputs.py#L16)

puzzle JSON for a site link or payload (pencilmark.sources: SudokuPad, f-puzzles, Penpa, Logic Masters, short links; some fetch one page), or None when s is not one

### `def read(x)` {#pencilmark.inputs.read}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/inputs.py#L67)

any accepted input -> a puzzle dict (see the module docstring); TypeError for an input of no known form

### `def to_puzzle_json(obj)` {#pencilmark.inputs.to_puzzle_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/inputs.py#L76)

accept puzzle JSON, the sudoku-puzzle exchange format, an ipuz sudoku, or a sample-pack line {"puzzle": ..., "grade": ...}.

## pencilmark.exchange {#pencilmark.exchange}

[src/pencilmark/exchange/__init__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/__init__.py)

The "sudoku-puzzle" exchange format, format_version 1 ([Puzzle format](../formats/puzzle-format.md)): engine Puzzle &lt;-> exchange dict.

write(p, meta=None, solution=None) -> dict          engine Puzzle -> canonical sudoku-puzzle dict

```
to_internal(doc) -> dict                            sudoku-puzzle dict -> puzzle JSON (pencilmark.puzzle_json)
read(doc) -> Puzzle                                 sudoku-puzzle dict -> engine Puzzle (not finalized)
validate(doc)                                       strict reading checks (docs/formats/puzzle-format.md section 4); raises FormatError
dumps(doc, pretty=True) -> str                      canonical JSON text (docs/formats/puzzle-format.md 8.1)
fingerprint(doc) -> "sha256:..."                    content fingerprint (docs/formats/puzzle-format.md 8.2)
```

The format is a transport layer: read(write(p)) builds the same engine structure as p (groups in order, relations and constraints in order, domains, givens, coordinates), except for the normalisations listed in [engine-mapping](../library/engine-mapping.md) (each mechanic gets ONE engine expansion). The writer therefore works from the engine structure directly and keeps the order of relations and constraints (the order changes cards).

## pencilmark.exchange.common {#pencilmark.exchange.common}

[src/pencilmark/exchange/common.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py)

The format's constants, errors, cell names and operator parameters.

| Name | What it does |
|---|---|
| class [`FormatError`](#pencilmark.exchange.common.FormatError) | the file breaks the format (unknown key / rule type, bad cell, failed structural check). |
| class [`NotSupportedError`](#pencilmark.exchange.common.NotSupportedError) | the file is valid, but uses something the pencilmark engine cannot build (or an engine puzzle the format… |
| def [`cell_name`](#pencilmark.exchange.common.cell_name) | 0-based (row, col) -> 'r1c1' |
| def [`parse_cell`](#pencilmark.exchange.common.parse_cell) | 'r1c1' -> 0-based (row, col) |
| def [`op_params`](#pencilmark.exchange.common.op_params) | an operator's named parameter in a rule or an any_of entry -> the positional params list |
| def [`op_named`](#pencilmark.exchange.common.op_named) | positional params -> the named parameter key(s) of a rule or any_of entry |

### `class FormatError(ValueError)` {#pencilmark.exchange.common.FormatError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L23)

the file breaks the format (unknown key / rule type, bad cell, failed structural check).

### `class NotSupportedError(ValueError)` {#pencilmark.exchange.common.NotSupportedError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L27)

the file is valid, but uses something the pencilmark engine cannot build (or an engine puzzle the format cannot express).

### `def cell_name(r, c)` {#pencilmark.exchange.common.cell_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L36)

0-based (row, col) -> 'r1c1'

### `def parse_cell(s)` {#pencilmark.exchange.common.parse_cell}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L41)

'r1c1' -> 0-based (row, col)

### `def op_params(r)` {#pencilmark.exchange.common.op_params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L102)

an operator's named parameter in a rule or an any_of entry -> the positional params list

### `def op_named(op, params)` {#pencilmark.exchange.common.op_named}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/common.py#L111)

positional params -> the named parameter key(s) of a rule or any_of entry

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

forward neighbour pairs in the engine's order (puzzle_json._pairs): by cell, then by step.

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

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/validate.py#L92)

strict reading ([Puzzle format](../formats/puzzle-format.md) section 4) of a format_version 1 dict; raises FormatError. Returns the Board.

### `def area_cells(B, a)` {#pencilmark.exchange.validate.area_cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/validate.py#L190)

an area ([Puzzle format](../formats/puzzle-format.md) 5): the origin of a grid / box_grid rule -> that grid's D x D cells in reading order, or a list of cell names -> those cells; as engine cell ids

### `def resolve_areas(B, rules)` {#pencilmark.exchange.validate.resolve_areas}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/validate.py#L222)

rules with every "area" replaced by its cell list ("cells"), as the engine expansion reads them

## pencilmark.exchange.read {#pencilmark.exchange.read}

[src/pencilmark/exchange/read.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/read.py)

Reading: a sudoku-puzzle dict -> puzzle JSON / engine Puzzle (to_internal, read).

| Name | What it does |
|---|---|
| def [`to_internal`](#pencilmark.exchange.read.to_internal) | sudoku-puzzle (format_version 1) -> puzzle JSON (pencilmark.puzzle_json) that builds the engine Puzzle. |
| def [`read`](#pencilmark.exchange.read.read) | sudoku-puzzle dict -> engine Puzzle (not finalized) |

### `def to_internal(doc)` {#pencilmark.exchange.read.to_internal}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/read.py#L26)

sudoku-puzzle (format_version 1) -> puzzle JSON (pencilmark.puzzle_json) that builds the engine Puzzle.

### `def read(doc)` {#pencilmark.exchange.read.read}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/read.py#L63)

sudoku-puzzle dict -> engine Puzzle (not finalized)

## pencilmark.exchange.write {#pencilmark.exchange.write}

[src/pencilmark/exchange/write.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/write.py)

Writing: an engine Puzzle -> a canonical sudoku-puzzle dict (write).

| Name | What it does |
|---|---|
| def [`write`](#pencilmark.exchange.write.write) | engine Puzzle -> sudoku-puzzle dict (format_version 1). |

### `def write(p, meta=None, solution=None, provenance=False)` {#pencilmark.exchange.write.write}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/write.py#L32)

engine Puzzle -> sudoku-puzzle dict (format_version 1). Raises NotSupportedError for engine structures the format cannot express. provenance=True returns (doc, prov): prov[i] = the engine objects rule i was written from ({"groups", "relations", "constraints", "clues"}: indices into p.groups / p.relations / p.constraints / p.cell_clues).

## pencilmark.exchange.canonical {#pencilmark.exchange.canonical}

[src/pencilmark/exchange/canonical.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py)

The canonical text and the content fingerprint ([Puzzle format](../formats/puzzle-format.md) 8).

| Name | What it does |
|---|---|
| def [`canonical`](#pencilmark.exchange.canonical.canonical) | key order of [Puzzle format](../formats/puzzle-format.md) 8.1 (content unchanged) |
| def [`dumps`](#pencilmark.exchange.canonical.dumps) | canonical JSON text: fixed key order; pretty: givens / solution one grid row per line, one rule per line. |
| def [`jcs`](#pencilmark.exchange.canonical.jcs) | RFC 8785 JSON canonicalization for the values the fingerprint covers (integers, strings, lists, objects with… |
| def [`semantic_subset`](#pencilmark.exchange.canonical.semantic_subset) | the fingerprinted content: board, digits, givens, candidates and rules, with the houses replaced by the… |
| def [`fingerprint_of_doc`](#pencilmark.exchange.canonical.fingerprint_of_doc) | SHA-256 of the JCS form of the semantic subset of an already canonical sudoku-puzzle dict |

### `def canonical(doc)` {#pencilmark.exchange.canonical.canonical}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L73)

key order of [Puzzle format](../formats/puzzle-format.md) 8.1 (content unchanged)

### `def dumps(doc, pretty=True)` {#pencilmark.exchange.canonical.dumps}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L90)

canonical JSON text: fixed key order; pretty: givens / solution one grid row per line, one rule per line.

### `def jcs(x)` {#pencilmark.exchange.canonical.jcs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L113)

RFC 8785 JSON canonicalization for the values the fingerprint covers (integers, strings, lists, objects with ASCII keys, booleans, null): sorted keys, no whitespace, UTF-8.

### `def semantic_subset(doc)` {#pencilmark.exchange.canonical.semantic_subset}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L152)

the fingerprinted content: board, digits, givens, candidates and rules, with the houses replaced by the houses they state (grid, box_grid, box / row / column rules), so every spelling of the same houses gives the same result, and set-like cell lists sorted

### `def fingerprint_of_doc(doc)` {#pencilmark.exchange.canonical.fingerprint_of_doc}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/exchange/canonical.py#L170)

SHA-256 of the JCS form of the semantic subset of an already canonical sudoku-puzzle dict

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

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/line.py#L122)

a public line rule -> the engine's rules (exchange's reader): a line constraint, or for double_arrow an equal sum

### `def line_from_engine(c, B, D)` {#pencilmark.rules.line.line_from_engine}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/rules/line.py#L150)

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

## pencilmark.puzzle_json {#pencilmark.puzzle_json}

[src/pencilmark/puzzle_json.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py)

Puzzle &lt;-> JSON: the storage / exchange format for any sudoku the engine supports.

Minimal (classic, any standard size; boxes implied): {"numbers": "..3.2.6..9..3.5..1..18.64...."}          # '.' or '0' blank, 1-9 then A-Z above 9 Full form (every field optional except what the puzzle needs): { "digits": 9,                                          # D: digits 1..D "shape": ["#########.....", ...],                     # cells on the bounding grid: '#' cell, '.' void #   (omit for a full D x D board) "box": "3x3",                                         # implied rows / columns / boxes of a D x D board "layout": "samurai",                                  # implied regions of a named multi-grid layout "numbers": "...",                                     # givens, row-major over the bounding grid ('#' = void) "solution": "...", "regions": [{"kind": "row|col|box|region|diag|window|cage|extra", "cells": ["r1c1", ...], "sum": 15, "unique": true}, ...],       # explicit no-repeat groups (when not implied) "rules": [{"type": "kropki", "color": "white", "cells": ["r1c1", "r1c2"]}, {"type": "line", "kind": "thermo", "cells": [...]},     # any engine line kind, bulb first {"type": "antiknight"}, {"type": "antiking"}, {"type": "nonconsecutive"}, {"type": "frame", "side": "top", "index": 3, "sum": 12},              # first 3 cells from that edge {"type": "rossini", "arrows": [{"side": "left", "index": 2, "towards": "in"}], "all_given": true}, {"type": "vudoku", "cells": ["r2c2", "r1c2", "r2c3"]},   # vertex = sum or difference of the arms {"type": "lowhigh", "high": ["r1c1", ...], "split": 5},  # marked 6..9, the rest 1..5 {"type": "parity", "parity": "odd", "cells": [...]},    # shaded odd / even cells (graphical) {"type": "digit_class", "digits": "123", "cells": [...]},  # cells marked as holding one of these digits {"type": "exclude", "digit": 5, "cells": [...]},         # a circle: its digit is in none of these cells {"type": "increasing", "cells": [...]}, (Bold X / Snowflake / Argyle / Asterisk ...: their lines or cells as extra "regions") {"type": "pairs", "rel": "notdiff", "params": [1], "cells": [["r1c1", "r1c2"], ...]}, {"type": "pairs", "rel": "notsum", "params": [10], "where": "orthogonal", "except": [["r1c1", "r1c2"]]}, # whole-grid pair rule: every orthogonal / diagonal / king / knight # neighbour pair except those listed (e.g. "no X where not marked") {"type": "&lt;engine constraint>", ...}, ...],               # arrow, sum, little_killer, sandwich ... "candidates": {"r1c1": "137"},                       # given pencil marks (Sukaku); shaded clues are rules above "meta": {"title": "...", "author": "...", "rules_text": "...", "source": "...", "id": "..."}} # optional metadata, never used for solving (top level) Cells are 'r{row}c{col}', 1-based on the bounding grid. Regions are the no-repeat groups (for each sub-grid its rows, columns and boxes); boxes are what a renderer draws with thick lines. Rows / columns / boxes of a D x D board (or a named layout) are implied unless "regions" overrides them. from_json(obj or str) -> Puzzle (not finalized)      to_json(Puzzle) -> dict      canonical_hash(obj) -> md5

| Name | What it does |
|---|---|
| def [`from_json`](#pencilmark.puzzle_json.from_json) | puzzle JSON (dict or str) -> Puzzle, not finalized; ValueError for unknown keys or an unknown layout |
| def [`entropy_table`](#pencilmark.puzzle_json.entropy_table) | 2x2 window (TL, TR, BL, BR) with a low, a middle and a high digit, classes = thirds of 1..D (sudoku.coach's… |
| def [`quadruple_table`](#pencilmark.puzzle_json.quadruple_table) | every n-digit tuple over 1..D that holds each digit of need at least as often as need does |
| def [`add_named`](#pencilmark.puzzle_json.add_named) | apply a named rule (cells as engine indices or "r1c1" names) to an engine Puzzle and remember it (for… |
| def [`to_json`](#pencilmark.puzzle_json.to_json) | Puzzle -> puzzle JSON dict; solution and meta are written when given |
| def [`canonical_hash`](#pencilmark.puzzle_json.canonical_hash) | md5 of the canonical puzzle definition (sorted keys, no metadata) -- the same puzzle from two sources dedupes. |

### `def from_json(obj) -> M.Puzzle` {#pencilmark.puzzle_json.from_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L152)

puzzle JSON (dict or str) -> Puzzle, not finalized; ValueError for unknown keys or an unknown layout

### `def entropy_table(D)` {#pencilmark.puzzle_json.entropy_table}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L426)

2x2 window (TL, TR, BL, BR) with a low, a middle and a high digit, classes = thirds of 1..D (sudoku.coach's rule).

### `def quadruple_table(D, n, need)` {#pencilmark.puzzle_json.quadruple_table}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L434)

every n-digit tuple over 1..D that holds each digit of need at least as often as need does

### `def add_named(p, rule)` {#pencilmark.puzzle_json.add_named}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L443)

apply a named rule (cells as engine indices or "r1c1" names) to an engine Puzzle and remember it (for importers that build Puzzles directly).

### `def to_json(p: M.Puzzle, solution=None, meta=None) -> dict` {#pencilmark.puzzle_json.to_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L496)

Puzzle -> puzzle JSON dict; solution and meta are written when given

### `def canonical_hash(obj) -> str` {#pencilmark.puzzle_json.canonical_hash}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/puzzle_json.py#L671)

md5 of the canonical puzzle definition (sorted keys, no metadata) -- the same puzzle from two sources dedupes.

## pencilmark.interop {#pencilmark.interop}

[src/pencilmark/interop.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py)

Interop strings and ipuz export ([Other formats](../formats/other-formats.md)).

from_string(s) -> sudoku-puzzle dict        plain classic strings (also as text grids with | - + separators, or with a

```
                                            trailing comment), pencil-mark grids, 729-character candidate strings, HoDoKu
                                            library lines, and
                                            sudokuwiki.org packed strings (S9B, S6B, X9B, W9B, C9B, J9B, L9B, M9B, L6C)
to_string(puzzle, "plain" | "grid" | "sudokuwiki")   the reverse (refuses what the target cannot express)
to_ipuz(puzzle) -> dict                     ipuz 2 for classic / Latin square / diagonal / windoku / jigsaw / killer
from_ipuz(ipuz) -> sudoku-puzzle dict       the reverse (boxes, zones, cages); a to_ipuz file returns its embedded puzzle
```

The sudokuwiki encodings are checked against sudokuwiki.org's solver; the decoder reads exactly what the encoder writes and refuses anything else (placed digits in plain forms, candidate masks, 6x6 killer operators other than '+').

| Name | What it does |
|---|---|
| def [`from_string`](#pencilmark.interop.from_string) | plain classic string, text grid, pencil-mark grid, 729-character candidate string or sudokuwiki packed… |
| def [`to_string`](#pencilmark.interop.to_string) | engine Puzzle / any accepted input -> plain classic string or sudokuwiki packed string |
| def [`is_classic9`](#pencilmark.interop.is_classic9) | a classic 9 x 9 sudoku: standard rows, columns and boxes, nothing else (what Sudoku Explainer rates) |
| def [`analyse`](#pencilmark.interop.analyse) | -> (kind or None, info) for the sudokuwiki forms |
| def [`to_ipuz`](#pencilmark.interop.to_ipuz) | sudoku-puzzle (or any accepted input) -> ipuz 2 dict, for classic / Latin square / diagonal / windoku /… |
| def [`from_ipuz`](#pencilmark.interop.from_ipuz) | ipuz sudoku (dict or JSON text) -> sudoku-puzzle dict. |

### `def from_string(s, symbols=None)` {#pencilmark.interop.from_string}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L57)

plain classic string, text grid, pencil-mark grid, 729-character candidate string or sudokuwiki packed string -> sudoku-puzzle dict ([Other formats](../formats/other-formats.md))

### `def to_string(puzzle, form='plain')` {#pencilmark.interop.to_string}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L310)

engine Puzzle / any accepted input -> plain classic string or sudokuwiki packed string

### `def is_classic9(p)` {#pencilmark.interop.is_classic9}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L340)

a classic 9 x 9 sudoku: standard rows, columns and boxes, nothing else (what Sudoku Explainer rates)

### `def analyse(p)` {#pencilmark.interop.analyse}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L373)

-> (kind or None, info) for the sudokuwiki forms

### `def to_ipuz(puzzle)` {#pencilmark.interop.to_ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L545)

sudoku-puzzle (or any accepted input) -> ipuz 2 dict, for classic / Latin square / diagonal / windoku / jigsaw / killer and their combinations; refuses everything else with NotSupportedError.

### `def from_ipuz(ipuz)` {#pencilmark.interop.from_ipuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/interop.py#L644)

ipuz sudoku (dict or JSON text) -> sudoku-puzzle dict. Reads `puzzle`, `solution`, `boxes`, `zones` (jigsaw boxes, diagonals, windows, other regions) and `cages`; a file written by to_ipuz gives back its embedded puzzle unless the grid was edited. Refuses kinds other than sudoku and cells it cannot read.

## pencilmark.spec_format {#pencilmark.spec_format}

[src/pencilmark/spec_format.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py)

The "sudoku-spec" generator request ([Generator spec](../formats/generator-spec.md)): a puzzle file with blanks.

validate_spec(doc)                    strict reading of the spec language (unknown keys refused)

```
spec_to_gen(doc) -> dict              the part pencilmark.gen can run, as a Spec dict; anything else -> NotSupportedError
spec_from_gen(spec) -> dict           pencilmark.gen Spec (or dict) -> sudoku-spec
gen_support(doc) -> (bool, reason)    can pencilmark.gen run it today?
```

What pencilmark.gen runs today: gap-free D x D boards (4, 6, 8, 9, 10, 12, 16) with the standard box_grid, or a named layout of 9 x 9 grids (one box_grid per grid); locked rules of different digits; templates for cages, thermo / whisper / renban / between lines, arrows, kropki / XV, parity cells, with counts (incl. "all", "min", "tile", "max") and shape limits (size, sum, length); givens count and per grid; one symmetry of the givens; where: band, difficulty range or "max" / "min", contains (codes), elements max; limits: time, seed. Everything else in a spec is refused with the reason, never ignored.

| Name | What it does |
|---|---|
| def [`validate_spec`](#pencilmark.spec_format.validate_spec) | strict reading of a sudoku-spec ([Generator spec](../formats/generator-spec.md)); locked rules are checked like puzzle rules |
| def [`spec_to_gen`](#pencilmark.spec_format.spec_to_gen) | sudoku-spec -> pencilmark.gen Spec dict; NotSupportedError naming the first part the generator cannot run |
| def [`gen_support`](#pencilmark.spec_format.gen_support) | (True, "") when pencilmark.gen can run the spec today, else (False, reason) |
| def [`spec_from_gen`](#pencilmark.spec_format.spec_from_gen) | pencilmark.gen Spec (or its dict) -> sudoku-spec dict |
| def [`spec_fingerprint`](#pencilmark.spec_format.spec_fingerprint) |  |

### `def validate_spec(doc)` {#pencilmark.spec_format.validate_spec}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L105)

strict reading of a sudoku-spec ([Generator spec](../formats/generator-spec.md)); locked rules are checked like puzzle rules

### `def spec_to_gen(doc)` {#pencilmark.spec_format.spec_to_gen}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L266)

sudoku-spec -> pencilmark.gen Spec dict; NotSupportedError naming the first part the generator cannot run

### `def gen_support(doc)` {#pencilmark.spec_format.gen_support}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L428)

(True, "") when pencilmark.gen can run the spec today, else (False, reason)

### `def spec_from_gen(spec)` {#pencilmark.spec_format.spec_from_gen}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L437)

pencilmark.gen Spec (or its dict) -> sudoku-spec dict

### `def spec_fingerprint(doc)` {#pencilmark.spec_format.spec_fingerprint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/spec_format.py#L522)

*No docstring.*

## pencilmark.variants {#pencilmark.variants}

[src/pencilmark/variants.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py)

Variant registry: names, rule text and recognition ([variant-naming](../library/variant-naming.md)). Not part of the file format: variant names appear only in meta.type and in describe() output.

describe(puzzle) -> {"type": "Killer Sudoku", "rules": {"Sudoku": "...", "Killer": "...", ...}}

```
rules_text(described) -> "Sudoku: ...\nKiller: ..."
```

Two kinds of entries: @variant(name, aliases=..., text=...)   a PLACEMENT variant: fn(g) -> the rules it adds to ONE grid area g, or None where the variant is not defined for that area (size / box shape). Works for any size: windoku(g) on a 16x16 grid places its 9 windows. @family(name, match=..., text=...)      a RULE-FAMILY variant (killer, thermo, kropki, ...): recognised by rule type / kind; text(rules, ctx) writes its sentence. Recognition: for each grid area, every placement variant's rules are compared with the puzzle's rules as sets of (type, kind, cell set) -- region kinds are drawing hints and are ignored; if all are present the variant applies and those rules are explained. Remaining rules get their family names; anything unknown falls back to a generic name. Generator presets: the placement functions are also the presets a generator can use (preset_rules(name, size)); the current generator (pencilmark.gen) places only its own element kinds, so preset generation of placement variants is a next step.

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
| def [`centre_dot`](#pencilmark.variants.centre_dot) | the centre cell of every box as one region; None unless the boxes have odd sides |
| def [`girandola`](#pencilmark.variants.girandola) | the nine girandola cells as one region; 9x9 only, else None |
| def [`disjoint`](#pencilmark.variants.disjoint) | one region per position inside a box (the cells at that position in every box); None without boxes |
| def [`layout_name`](#pencilmark.variants.layout_name) | name of a multi-grid layout from its subgrid origins (0-based), or None |
| def [`size_word`](#pencilmark.variants.size_word) | title word for a grid size: Tiny (4), Mini (6), nothing (9), else DxD |
| def [`describe`](#pencilmark.variants.describe) | variant name and rules (an ordered key -> sentence map, like Logic Masters rule headers) from the rules alone. |
| def [`grid_names`](#pencilmark.variants.grid_names) | position names of the grids of a multi-grid board ("top-left", "centre", …), or "grid at r7c7" where… |
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

the centre cell of every box as one region; None unless the boxes have odd sides

### `def girandola(g)` {#pencilmark.variants.girandola}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L174)

the nine girandola cells as one region; 9x9 only, else None

### `def disjoint(g)` {#pencilmark.variants.disjoint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L186)

one region per position inside a box (the cells at that position in every box); None without boxes

### `def layout_name(subgrids, extra=0)` {#pencilmark.variants.layout_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L407)

name of a multi-grid layout from its subgrid origins (0-based), or None

### `def size_word(D)` {#pencilmark.variants.size_word}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L426)

title word for a grid size: Tiny (4), Mini (6), nothing (9), else DxD

### `def describe(puzzle)` {#pencilmark.variants.describe}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L446)

variant name and rules (an ordered key -> sentence map, like Logic Masters rule headers) from the rules alone.

### `def grid_names(grids)` {#pencilmark.variants.grid_names}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L620)

position names of the grids of a multi-grid board ("top-left", "centre", …), or "grid at r7c7" where positions would be ambiguous

### `def rules_text(described)` {#pencilmark.variants.rules_text}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L657)

'Key: sentence' lines (used only to fill an empty meta.rules_text)

### `def preset_rules(name, size=9, box=None)` {#pencilmark.variants.preset_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/variants.py#L662)

the rules a placement variant adds to a size x size board with standard boxes (a generator preset); None where the variant is not defined for that size
