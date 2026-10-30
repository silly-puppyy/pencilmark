# Drawing and style

How pencilmark draws puzzles, and the conventions most sudoku software shares. **None of this is part of a format**: a
`sudoku-puzzle` file says what each rule means, and a renderer may draw it any way that shows that meaning. The
per-puzzle `style` and `decorations` keys ([STYLE.md](FORMAT.md#7-cosmetic-layers-style-and-decorations))
carry a setter's own choices.

The line colours below are the community defaults, as measured on 6,217 published puzzles drawn in
[SudokuPad](https://sudokupad.app/). All values, with a dark theme, are in [`palette.json`](palette.json);
`tools/render_svg.py` is a reference renderer that follows this page.

A renderer needs nothing beyond the rules. Sizes are in cell units (1 = a cell's side). Colours are defaults that
`style` may override; the line colours are the community defaults (as measured on 6,217 published puzzles), and all
values, with a dark theme, are in [`docs/palette.json`](palette.json). Grid lines 0.031, box borders and frame 0.055. Draw order, bottom to top: cell shading, lines, cage outlines, grid lines and box borders,
edge / corner clues, digits, outside clues.

| Rule | Default drawing |
|---|---|
| grid | Thin lines between existing cells only; nothing at `null` positions. |
| boxes (`box_grid`, `box`) | Thick line wherever two adjacent existing cells lie in different boxes, and around the outside of the existing cells. |
| rows / columns | Nothing beyond the grid lines. |
| `region` `diagonal` | Thin grey line through the cell centres, extended to the outer corners of the end cells. |
| `region` `window` / `extra` | Light grey shading (`#d8d8d8`). |
| `region` `colour` | Shading by a palette colour per rule, in rule order (`#f4cccc #fce5cd #fff2cc #d9ead3 #d0e0e3 #c9daf8 #d9d2e9 #ead1dc #e6e6e6`, repeating). |
| `region` `disjoint` / `region` | Nothing (listed in the legend). |
| `cage` | Dashed outline inset 0.08 from the cell edges; `sum` in small type (0.25) in the top-left corner of the first cell in reading order. |
| `sum` `group` | Like a cage, dotted. |
| `sum` `corner` | Small white circle (0.3) with the sum at the shared corner. |
| `line` `thermo` | Grey (`#cccccc`) line, width 0.3; filled bulb, diameter 0.75, at `cells[0]`. |
| `line` `slow_thermo` | As thermo, bulb hollow. |
| `line` `whisper` | Green (`#67f067`), width 0.15; Dutch whisper (`value` 4) orange (`#ffa600`). |
| `line` `renban` | Pink (`#f067f0`), width 0.15. |
| `line` `region_sum` | Blue (`#2ecbff`), width 0.15. |
| `line` `palindrome` | Grey (`#aaaaaa`), width 0.15. |
| `line` `entropic` | Peach (`#ffccaa`), width 0.15. |
| `line` `modular` | Teal (`#33bbaa`), width 0.15. |
| `line` `parity` | Red (`#ff6666`), width 0.15. |
| `line` `zipper` | Lavender (`#c8adeb`), width 0.15, small dot at the centre. |
| `line` `between` | Grey line, width 0.1; hollow circles (0.75) at both ends. |
| `line` `lockout` | Grey line, width 0.1; hollow diamonds at both ends. |
| `line` `double_arrow` | Grey line, width 0.05; hollow circles at both ends. |
| closed lines | The segment from the last cell back to the first is drawn too. |
| `arrow` | Hollow circle (0.75) on a 1-cell bulb, rounded pill over a longer bulb; each shaft a thin grey line from the bulb's edge with an open arrowhead at its last cell. |
| `edge` `kropki` | Dot (0.25) at the midpoint: white with a black outline, or black. |
| `edge` `xv` | The letter X or V (height 0.3) on a white chip. |
| `edge` `difference` / `sum` / `product` / `ratio` | Small white circle (0.3) with the number; `ratio` shows `k:1`, `product` `×p`. |
| `edge` `less` | Chevron at the midpoint pointing at `cells[0]`. |
| `corner` `battenburg` | Small 2×2 checker square (0.3) at the corner. |
| `corner` `mathrax` | Small white circle at the corner with `value` and `op` (`10+`), or `E` / `O`. |
| `corner` `exclude` | Small white circle at the corner with the digit. |
| `contains` | On a 2×2 block: white circle (0.45) at the corner with the digits. Otherwise the digits in small type in the top-left corner of the first cell. |
| `appears` | A small arrow in the `source` cell pointing along `cells`. |
| `sum` `little_killer` | Small number outside `cells[0]` on `side`, with a short arrow pointing along `cells[0] → cells[1]`. |
| `sum` `frame`, `sandwich`, `skyscraper`, `first_seen`, `distinct_count` with `side` | Plain number outside `cells[0]` on `side`. When kinds are mixed on one side: `xsum` in angle brackets ⟨n⟩, `skyscraper` in a small square, `first_seen` in a small circle. |
| `xsum` | Plain number outside `cells[0]` (⟨n⟩ when mixed). |
| `rossini` | Arrow glyph outside `cells[0]` on `side`, pointing into the grid (`in`) or out of it (`out`). |
| `cell` `odd` / `even` | Grey circle / grey square (0.8) behind the digit. |
| `cell` `low` / `high` | Light / dark grey diamond behind the digit. |
| `cell` `set` / `exclude` | The values in small type along the bottom of the cell; `exclude` struck through. |
| `clone` | The same light shading colour for all regions of one rule (palette as for colour regions). |
| `vudoku` | A thin V through the three cell centres, vertex at `cells[0]`. |
| `equal_sum` | Thin dashed outline around each segment. |
| `isomorphic`, `count`, `global_entropy`, `neighbours`, `negative` | Nothing in the grid (listed in the legend). |
| `relation` | Thin grey connector between the two cell centres. |
| Vendor rules | Light highlight of the cells plus the `label` text in the first cell. |
| givens | Large digit. |
| candidates | Small digits in a 3×3 keypad layout (centred for D > 9). |
