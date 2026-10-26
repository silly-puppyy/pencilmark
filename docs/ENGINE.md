# Engine mapping

How pencilmark builds its engine `Puzzle` from a `sudoku-puzzle` file ([FORMAT.md](FORMAT.md)). This is for people
working on pencilmark or adding a rule; it is not part of the format.

The format is a transport layer: the engine `Puzzle` built from a file equals the one the site loaders build (groups
and their order, relations, constraints, domains, givens, coordinates), and each mechanic has **one** engine expansion
whatever its source.

## Expansions

| Rule | Engine |
|---|---|
| `grid` | `row` / `col` groups of its D × D area (rows, then columns; an already present house is skipped) |
| `box_grid` | as `grid`, then the area's `box` groups |
| `box` / `row` / `column` | `box` / `row` / `col` groups |
| `region` | groups of kind `diag` (diagonal), `window` (window), `region` (the other kinds) |
| `cage` | a `cage` group with its total |
| `line` | `{"type": "line", "kind": …}` (whisper `value` → `k`; closed: the first cell repeated at the end); `double_arrow` → `equal_sum` `[[ends], middle]`; `lockout` → `diffge` on the ends plus a 3-cell table per middle cell |
| `arrow` | one `arrow` constraint per shaft |
| `edge` | relations `diff 1` / `ratio 2` (kropki), `sum 10` / `sum 5` (xv), `lt` (less); difference / sum / product / ratio: a 2-cell table of the allowed pairs (normalisation 8) |
| `corner` | battenburg: a 4-cell table; mathrax: a 2-cell table per diagonal pair (TL–BR, then TR–BL), even / odd: a `cell` clue; exclude: a `cell` exclude clue |
| `sum` | `little_killer` / `sum` constraints |
| outside clues | `sandwich` / `xsum` / `skyscraper` / `first_seen` constraints; rossini: `lt` relations and, with its negative, 3-cell tables |
| `neighbours` | `neq` / `nonconsec` / the operator's relations per pair |
| `relation` | one relation per pair |
| `negative` | the complementary relation on every uncovered pair (`nonconsec` for white kropki, `notratio`, `notsum`, `notdiff`, `allowed`), tables for rossini / battenburg, domains for digits |
| `cell`, `candidates` | domain masks (`cell` clues are also kept as cell clues) |
| `contains` / `appears` / `count` / `distinct_count` / `clone` / `isomorphic` / `global_entropy` / `equal_sum` / `vudoku` / `table` | the engine constraints and named rules of the same mechanics |

## Normalisations

Site loaders produce engine structures in several shapes; the writer maps each to one rule, so the same puzzle gives
the same file and the same card whatever its source.

1. Bare `set` consecutive constraints → `line` renban.
2. Bare `between` constraints → `line` between.
3. Bare `equal_sum` constraints that are a zipper or a region-sum line → that `line` kind.
4. `increasing` → `line` thermo; `dutch_whisper` → `line` whisper with value 4; `kropki_chain` lines → kropki edges.
5. Jigsaw pieces stored as `region` groups → `box` groups.
6. Disjoint groups of kind `extra` → kind `region`; explicit-house boards (kinds `house` / `partial`) → `row` / `col` /
   `box` / `region` by shape.
7. "Not consecutive" relations of a white-kropki negative (`notdiff 1`) → `nonconsec` (identical to the solver).
8. Numbered pair clues (edge `difference` / `sum` / `product` / `ratio`) and `corner` `mathrax` clues expand to 2-cell
   tables of the allowed digit pairs (in digit order; equal digits allowed only when the two cells share no house).
   This is the form whose pricing fits players' times. A 2-cell table equal to a clue's digit pairs is written as that
   clue (first match in the order difference, sum, ratio, product: a 7:6 quotient and a ×42 product have the same
   pairs); kropki dots, XV and inequality signs stay pair relations. (`exchange.NUMBERED_PAIR_FORM = "relation"`
   switches to pair relations.)
9. `sum` constraints with distinct digits whose cells share no house → `cage` groups.
10. A house listed twice is one house.
11. Negative and neighbour rules expand in board order (cell by cell).
12. Named multi-grid layouts (puzzle JSON `layout`): cells are numbered in board reading order.
13. Houses are written grid by grid (`grid` / `box_grid`, at the place of the grid's first house) whatever order a
    loader listed them in; reading the file back lists each grid's rows, columns, then boxes.

Mechanics without a named rule (same-parity lines, maximin, minimax, ten-eleven and similar) stay 2-cell tables or
`relation` `allowed` rules.

## Adding a rule

1. Add the rule family or kind to [FORMAT.md](FORMAT.md) section 6 (meaning) and section 7 (default drawing), and to
   `docs/sudoku-puzzle.schema.json`.
2. Read and write it in `src/pencilmark/exchange.py` (strict checks, engine expansion, canonical key order).
3. If the engine needs a new constraint, add it in `csrc/` (all solving logic lives in C++).
4. Name it in `src/pencilmark/variants.py` so `describe()` explains it.
5. Add a round-trip case to `tests/test_format.py`.
