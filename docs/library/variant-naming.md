# Variant names

How `describe()` names a variant and writes its rules from the rules alone. This is library behaviour, not part of
any format: the names appear only in `meta.type` and in `describe()` output.

`describe(puzzle)` names the variant and lists its rules **from the rules alone**, as an ordered map from a short name
to one sentence, like the rule headers on [Logic Masters](https://logic-masters.de/):

```json
{"type": "Variant Sudoku",
 "rules": {"Sudoku": "Place 1–9 in every row, column and 3×3 box.",
           "Argyle": "Digits don't repeat on any of the eight marked diagonals.",
           "Killer": "Digits in a cage sum to its small clue and don't repeat within the cage.",
           "Anti-Knight": "Cells a knight's move apart don't contain the same digit.",
           "XV": "Digits separated by an X sum to 10; digits separated by a V sum to 5. All X's and V's are given."}}
```

It is deterministic, never reads `meta`, and never feeds back into solving. `rules_text(described)` renders it as
"Key: sentence" lines. `to_export` uses both only to fill an **empty** `meta.type` / `meta.rules_text`; it never
overwrites them.

The variant names are **not part of the file format**: they appear only in `meta.type` and in `describe()` output. They
come from a registry in code (`pencilmark/variants.py`), so they generalise across sizes (a 16×16 windoku, a 6×6 X).

## 1. Name

`type` = [size word] + [ONE variant name, or "Variant" when two or more variants are present] + "Sudoku".

- Size word: 4×4 `Tiny`, 6×6 `Mini`, 9×9 none, other sizes `NxN` (`8x8`, `16x16`). There is no "Classic": a plain
  9×9 is `"Sudoku"`, a plain 6×6 `"Mini Sudoku"`.
- The houses of a variant (windoku windows, X diagonals) and its own negative rules belong to that variant and do not
  count as extra variants.
- Boards with several grids use their layout name: "Samurai Sudoku", "Twodoku", "Butterfly Sudoku", … ("Multi-Grid
  Sudoku" for an unknown layout); with one variant it goes in front ("Killer Samurai Sudoku"), with more "Variant
  Samurai Sudoku".
- A board with rows / columns but no boxes and nothing else is a "Latin Square".
- The first key of `rules` is the base: "Sudoku" (with the size word: "Mini Sudoku", "16x16 Sudoku"), or the layout name.

## 2. Recognition

- **Placement variants** are functions of ONE grid area (a `grid` / `box_grid`, or the whole board) that return the rules the variant adds there, or nothing where
  the variant is not defined for that size or box shape. For each grid area of the puzzle, every placement variant is
  run; if all the rules it returns are present in the puzzle (compared as type, kind and cell set; region kinds are
  drawing hints and are ignored), the variant applies and those rules are explained.
- **Rule families** (killer, thermo, kropki, …) are recognised by rule type and kind; a family's negative rules join
  it ("XV" with `{"type": "negative", "of": "xv"}`; a negative alone is "Non-XV").
- `box` rules (boxes that are not a regular tiling) are "Jigsaw".
- Anything left falls back to a generic family name ("Diagonals", "Windows", "Extra Regions", …).
- On a multi-grid board, a variant or family whose rules lie in some grids only says so at the end of its sentence:
  "Only in the top-left grid." Grids are named by position (top-left, centre, …), or by origin ("grid at r7c7") when
  positions would be ambiguous.

## 3. Placement variants (geometric definitions)

For porting: a grid area has size n, boxes bh × bw, local rows and columns 0 … n−1.

| Name (aliases) | Defined for | Rules added to the grid area |
|---|---|---|
| X (Diagonal) | any n | `region` diagonal on (i, i) and on (i, n−1−i), i = 0 … n−1 |
| Windoku (Hyper, NRC) | boxes, n/bh ≥ 2 and n/bw ≥ 2 | a bh × bw `region` window at every (1 + i(bh+1), 1 + j(bw+1)), i < n/bh − 1, j < n/bw − 1, that fits inside the grid's inner border (9×9: 4 windows at r2c2, r2c6, r6c2, r6c6; 16×16: 9) |
| Argyle | n = 9 | `region` diagonals of 8 cells from (0,1), (1,0) going down-right and from (0,7), (1,8) going down-left; of 5 cells from (0,4) going down-left and down-right, from (4,0) down-right and (4,8) down-left |
| Asterisk | n = 9 | one `region`: (1,4) (2,2) (2,6) (4,1) (4,4) (4,7) (6,2) (6,6) (7,4) |
| Centre-dot (Center dot) | boxes with odd bh and bw | one `region`: the centre cell (br + ⌊bh/2⌋, bc + ⌊bw/2⌋) of every box |
| Girandola | n = 9 | one `region`: (0,0) (0,8) (1,4) (4,1) (4,4) (4,7) (7,4) (8,0) (8,8) |
| Disjoint Groups (Colour) | boxes | bh·bw `region`s: for each in-box position (a, b), the cells (br + a, bc + b) of every box |

## 4. Rule families

In registry order (the order of the `rules` keys): Killer (`cage`), Little Killer, Sum Frame, Sum (`sum` group /
corner), Sandwich, X-Sums, Skyscrapers, Rossini (+ its negative), 123 (`first_seen`), Count Different, Arrow, Thermo,
Slow Thermo, Whispers (German Whispers for 5, Dutch Whispers for 4), Renban, Region Sum, Palindrome, Entropic,
Modular, Parity, Zipper, Between Lines, Lockout, Double Arrow, Kropki (white dots only: Consecutive; negative alone:
Non-Kropki), XV (negative alone: Non-XV), Difference, Sum Pairs, Product, Ratio, Greater-Than, Battenburg, Mathrax,
Exclusion, Quadruple (`contains`), Cupid (`appears`), Clone, Twin (`isomorphic`), Odd-Even, Low-High, Digit Class,
Double / Counting Circles / Count (`count`), Distinct Count, Equal Sums, Vudoku, Entropy (`global_entropy`),
Anti-Knight, Anti-King, Non-Consecutive, Neighbours (generic), Relation, Custom (vendor rules), Sukaku
(`candidates`). Each has one sentence, filled from its rules (whisper gap, sandwich digits, scope "within the same box",
"All X's and V's are given." for a negative, …).

## 5. Generator presets

The placement functions double as presets: `variants.preset_rules("windoku", 16)` gives the 9 windows of a 16×16
board.
