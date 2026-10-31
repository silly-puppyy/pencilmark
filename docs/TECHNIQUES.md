---
title: Techniques
description: Every technique code on the card, by family, with its band and links to explainer sites.
---

# Techniques

The `contains` field of a card lists techniques by three-letter code, Andrew Stuart's
([sudokuwiki.org](https://www.sudokuwiki.org)) where he has the strategy. A step is named by the most specific
shape found: a Skyscraper is `SKY`, not X-Chain. **Special case of** names the next more general technique: an
X-Wing is a special case of a Skyscraper, so if you know Skyscrapers you can solve an X-Wing step. Each family is
sorted by band. The links go to explanations on other sites.

This page is generated from `pencilmark/data/codes.csv` and `techniques.csv` (`tools/gen_techniques_md.py`).

## Singles

| Code | Technique | Band | Special case of | Learn |
|---|---|---|---|---|
| `FHS` | Full House | Very Easy | `HSI`, `NSI` | <a href="https://hodoku.sourceforge.net/en/tech_singles.php#fh" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `HSI` | Hidden Single | Very Easy |  | <a href="https://www.sudokuwiki.org/Getting_Started" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_singles.php#h1" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/hiddensinglesbybox.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `LSI` | Line / dot read without notes *(variant)* | Very Easy |  |  |
| `CSI` | Last cell of a cage / line *(variant)* | Very Easy |  |  |
| `NSI` | Naked Single | Easy |  | <a href="https://www.sudokuwiki.org/Getting_Started" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_singles.php#n1" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/nakedsingles.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |

## Intersections and rule combinations

| Code | Technique | Band | Special case of | Learn |
|---|---|---|---|---|
| `CFX` | Clue Facts *(variant)* | Very Easy |  |  |
| `PPR` | Pointing / Box-Line Reduction | Easy |  | <a href="https://www.sudokuwiki.org/Intersection_Removal" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_intersections.php#lc1" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/pointing.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `SNY` | Snyder notation (box pairs) | Easy |  |  |
| `CGC` | Killer cage combinations *(variant)* | Easy |  | <a href="https://www.sudokuwiki.org/Killer_Combinations" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://www.sudokuwiki.org/Killer_Cage_Combination_Example" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://en.wikipedia.org/wiki/Killer_sudoku" title="Wikipedia"><img src="/pencilmark/img/sites/wikipedia.png" alt="Wikipedia" class="pm-site"/></a> |
| `SUM` | Sum clue combinations *(variant)* | Easy |  | <a href="https://www.sudokuwiki.org/Killer_Combinations" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `ARW` | Arrow sums *(variant)* | Easy |  |  |
| `RNB` | Renban runs *(variant)* | Easy |  |  |
| `IOU` | Innies & outies (rule of 45) *(variant)* | Easy |  | <a href="https://www.sudokuwiki.org/Innies_and_Outies" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://en.wikipedia.org/wiki/Killer_sudoku" title="Wikipedia"><img src="/pencilmark/img/sites/wikipedia.png" alt="Wikipedia" class="pm-site"/></a> |
| `PWC` | Pair rules (dots, whispers, anti-knight...) *(variant)* | Easy |  |  |
| `TBL` | Allowed combinations of a rule *(variant)* | Easy |  |  |
| `LNR` | Line ranges (thermo / whisper bounds) *(variant)* | Easy |  |  |
| `LNS` | Local line scan *(variant)* | Easy |  |  |
| `LNC` | Line classes (low/high, odd/even) *(variant)* | Easy |  |  |
| `SWC` | Sandwich sums *(variant)* | Easy |  |  |
| `XSC` | X-Sums *(variant)* | Easy |  |  |
| `SKC` | Skyscraper clues *(variant)* | Easy |  |  |
| `CNT` | Counting clues *(variant)* | Easy |  | <a href="https://www.sudokuwiki.org/Cage_Unit_Overlap" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishg.php" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `CSH` | Clue Shape *(variant)* | Easy |  |  |
| `EQD` | Equal cells (same digit) *(variant)* | Medium |  |  |
| `DGC` | Digit counting *(variant)* | Medium |  | <a href="https://www.sudokuwiki.org/Cage_Unit_Overlap" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishg.php" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `LOL` | Set theory (law of leftovers) | Medium |  | <a href="https://www.sudokuwiki.org/Law_of_Leftovers" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `IOV` | Innies & outies as a virtual cage *(variant)* | Medium |  | <a href="https://www.sudokuwiki.org/Innies_and_Outies" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://en.wikipedia.org/wiki/Killer_sudoku" title="Wikipedia"><img src="/pencilmark/img/sites/wikipedia.png" alt="Wikipedia" class="pm-site"/></a> |
| `IOM` | Innies & outies over several houses *(variant)* | Medium |  | <a href="https://www.sudokuwiki.org/Innies_and_Outies" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://en.wikipedia.org/wiki/Killer_sudoku" title="Wikipedia"><img src="/pencilmark/img/sites/wikipedia.png" alt="Wikipedia" class="pm-site"/></a> |
| `EQS` | Equal sums (zipper / region-sum lines) *(variant)* | Medium |  |  |
| `CBL` | Must-contain digits (cage / line) *(variant)* | Medium |  | <a href="https://www.sudokuwiki.org/Cage_Unit_Overlap" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://www.sudokuwiki.org/Killer_Combinations" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `RUL` | Two rules together *(variant)* | Medium |  |  |
| `IMH` | Hidden regions (implied houses) *(variant)* | Medium |  | <a href="https://www.sudokuwiki.org/Windoku_Strategy" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://www.sudokuwiki.org/Law_of_Leftovers" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `DOM` | Domino pairs (dots / XV) *(variant)* | Medium |  |  |
| `CLC` | Odd/even & high/low counting *(variant)* | Medium |  |  |
| `SBD` | Min/max sum bounds *(variant)* | Medium |  |  |
| `PHI` | Phistomefel Ring | Hard | `LOL` | <a href="https://www.sudokuwiki.org/Law_of_Leftovers" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `PHV` | Phistomefel Variant | Hard | `LOL` | <a href="https://www.sudokuwiki.org/Law_of_Leftovers" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `SAL` | Sum algebra (house totals) *(variant)* | Very Hard |  |  |
| `WEI` | Weighted sums *(variant)* | Very Hard |  |  |

## Subsets

| Code | Technique | Band | Special case of | Learn |
|---|---|---|---|---|
| `MSI` | Pair / triple in the head | Easy | `NPR`, `NTR` | <a href="https://www.sudokuwiki.org/Naked_Candidates#NP" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `NPR` | Naked Pair | Medium |  | <a href="https://www.sudokuwiki.org/Naked_Candidates#NP" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_naked.php#n2" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/nakedsubsets.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `HPR` | Hidden Pair | Medium |  | <a href="https://www.sudokuwiki.org/Hidden_Candidates#HP" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_hidden.php#h2" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/hiddensubsets.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `NQD` | Naked Quad | Medium |  | <a href="https://www.sudokuwiki.org/Naked_Candidates#NQ" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_naked.php#n4" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/nakedsubsets.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `HQD` | Hidden Quad | Medium |  | <a href="https://www.sudokuwiki.org/Hidden_Candidates#HQ" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_hidden.php#h4" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/hiddensubsets.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `NTR` | Naked Triple | Medium |  | <a href="https://www.sudokuwiki.org/Naked_Candidates#NT" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_naked.php#n3" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/nakedsubsets.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `HTR` | Hidden Triple | Medium |  | <a href="https://www.sudokuwiki.org/Hidden_Candidates#HT" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_hidden.php#h3" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/hiddensubsets.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `CPS` | Cage combination positions *(variant)* | Very Hard |  |  |
| `CLI` | Clique house (all-different cells) *(variant)* | Very Hard |  |  |
| `RNS` | Renban sets in a house *(variant)* | Very Hard |  |  |
| `OCL` | Outside clues together *(variant)* | Very Hard |  |  |

## Fish and wings

| Code | Technique | Band | Special case of | Learn |
|---|---|---|---|---|
| `XWG` | X-Wing | Hard | `FRK`, `FXW`, `SKY`, `SWF` | <a href="https://www.sudokuwiki.org/X_Wing_Strategy" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishb.php#bf2" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/xwings.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `SWF` | Swordfish | Very Hard |  | <a href="https://www.sudokuwiki.org/Sword_Fish_Strategy" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishb.php#bf3" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/swordfish.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `FXW` | Finned X-Wing | Very Hard | `XCL` | <a href="https://www.sudokuwiki.org/Finned_X_Wing" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishfs.php#fbf2" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/finnedxwings.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `FSW` | Finned Swordfish | Very Hard |  | <a href="https://www.sudokuwiki.org/Finned_Swordfish" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishfs.php#fbf3" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/finnedswordfish.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `YWG` | Y-Wing | Very Hard | `XYC` | <a href="https://www.sudokuwiki.org/Y_Wing_Strategy" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_wings.php#xy" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/xywings.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `XYZ` | XYZ-Wing | Very Hard | `ALS` | <a href="https://www.sudokuwiki.org/XYZ_Wing" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_wings.php#xyz" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/xyzwings.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `URC` | Unique Rectangle | Very Hard |  | <a href="https://www.sudokuwiki.org/Unique_Rectangles" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://www.sudokuwiki.org/Hidden_Unique_Rectangles" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_ur.php" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `BUG` | BUG | Very Hard |  | <a href="https://www.sudokuwiki.org/BUG" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_ur.php#bug1" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `JLF` | Jellyfish | Very Hard |  | <a href="https://www.sudokuwiki.org/Jelly_Fish_Strategy" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishb.php#bf4" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/jellyfish.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `FJF` | Finned Jellyfish | Very Hard |  | <a href="https://hodoku.sourceforge.net/en/tech_fishfs.php#fbf4" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/finnedjellyfish.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `WXZ` | WXYZ-Wing | Very Hard | `ALS` | <a href="https://www.sudokuwiki.org/WXYZ_Wing" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `FRK` | Franken Fish | Very Hard |  | <a href="https://www.sudokuwiki.org/Franken_Sword_Fish" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_fishc.php#ff" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/mutantswordfish.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `FIR` | Fireworks | Very Hard |  | <a href="https://www.sudokuwiki.org/Fireworks" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `GSY` | Gurth's Symmetry | Very Hard |  | <a href="https://www.sudokuwiki.org/Gurths_Theorem" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |

## Chains and colouring

| Code | Technique | Band | Special case of | Learn |
|---|---|---|---|---|
| `CCL` | High / Low and Odd / Even Colouring *(variant)* | Medium |  |  |
| `SKY` | Skyscraper | Hard | `TUR` | <a href="https://www.sudokuwiki.org/Rectangle_Elimination" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_sdp.php#sk" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `KTE` | 2-String Kite | Hard | `TUR` | <a href="https://www.sudokuwiki.org/Rectangle_Elimination" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_sdp.php#t2sk" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `TUR` | Turbot Fish | Hard | `XCL` | <a href="https://www.sudokuwiki.org/Rectangle_Elimination" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_sdp.php#sk" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `SCL` | Simple Colouring | Hard | `XCL` | <a href="https://www.sudokuwiki.org/Simple_Colouring" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_col.php#sc" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/coloring.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `MCH` | Short chain in the head | Hard |  | <a href="https://www.sudokuwiki.org/Alternating_Inference_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `ERE` | Empty Rectangle | Very Hard | `TUR` | <a href="https://www.sudokuwiki.org/Empty_Rectangles" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_sdp.php#er" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `RMP` | Remote Pairs | Very Hard | `XYC` | <a href="https://www.sudokuwiki.org/Remote_Pairs" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_chains.php#rp" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/remotepairs.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `XCL` | X-Chain | Very Hard | `AIC` | <a href="https://www.sudokuwiki.org/X_Cycles" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_chains.php#x" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `CRP` | Chute Remote Pairs | Very Hard |  | <a href="https://www.sudokuwiki.org/Chute_Remote_Pairs" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `BAN` | Band set theory with cages *(variant)* | Very Hard |  |  |
| `CAL` | Equal-digit colouring *(variant)* | Very Hard |  |  |
| `AIC` | Alternating Inference Chain | Expert | `AAC` | <a href="https://www.sudokuwiki.org/Alternating_Inference_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_chains.php#in" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `NLP` | Nice Loop | Expert | `AIC` | <a href="https://www.sudokuwiki.org/X_Cycles" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_chains.php#nl" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `CAS` | Case analysis | Expert |  |  |
| `XYC` | XY-Chain | Expert | `AIC` | <a href="https://www.sudokuwiki.org/XY_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_chains.php#xyc" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/nakedxychains.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `MCL` | Multi-Colouring | Expert | `XCL` | <a href="https://www.sudokuwiki.org/Multi_Colouring" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `3DM` | 3D Medusa | Expert |  | <a href="https://www.sudokuwiki.org/3D_Medusa" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |

## Almost locked sets

| Code | Technique | Band | Special case of | Learn |
|---|---|---|---|---|
| `ALS` | ALS-XZ (almost locked sets) | Expert | `AAC` | <a href="https://www.sudokuwiki.org/Almost_Locked_Sets" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_als.php#axz" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `AXY` | ALS-XY-Wing | Expert | `AAC`, `DEB` | <a href="https://www.sudokuwiki.org/Almost_Locked_Sets" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_als.php#axy" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `SDC` | Sue de Coq | Expert |  | <a href="https://www.sudokuwiki.org/Sue_de_Coq" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `APE` | Aligned Pair Exclusion | Expert |  | <a href="https://www.sudokuwiki.org/Aligned_Pair_Exclusion" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `AAC` | ALS chain | Expert |  | <a href="https://www.sudokuwiki.org/AIC_with_ALSs" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_als.php#ach" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
| `DEB` | Death Blossom | Expert |  | <a href="https://www.sudokuwiki.org/Death_Blossom" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_als.php#db" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/deathblossom.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |

## Trial and forcing

| Code | Technique | Band | Special case of | Learn |
|---|---|---|---|---|
| `EWY` | Either way (case split) | Expert |  | <a href="https://www.sudokuwiki.org/Cell_Forcing_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://www.sudokuwiki.org/Unit_Forcing_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_last.php#fc" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/forcingchains.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `WIF` | What if… | Expert |  |  |
| `STR` | Short trial | Expert |  | <a href="https://www.sudokuwiki.org/Nishio_Forcing_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `FCH` | Forcing Chains | Extreme |  | <a href="https://www.sudokuwiki.org/Cell_Forcing_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://www.sudokuwiki.org/Unit_Forcing_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_last.php#fc" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> <a href="https://www.sudokusnake.com/forcingchains.php" title="Sudoku Snake"><img src="/pencilmark/img/sites/sudokusnake.png" alt="Sudoku Snake" class="pm-site"/></a> |
| `FNT` | Forcing Nets | Extreme |  |  |
| `NFC` | Nested Forcing Chains | Extreme |  |  |
| `NIS` | Nishio | Extreme |  | <a href="https://www.sudokuwiki.org/Nishio_Forcing_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `POM` | Pattern Overlay | Extreme |  | <a href="https://www.sudokuwiki.org/Pattern_Overlay" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> |
| `TRL` | Trial and error | Extreme |  | <a href="https://www.sudokuwiki.org/Nishio_Forcing_Chains" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://www.sudokuwiki.org/Bowmans_Bingo" title="sudokuwiki.org"><img src="/pencilmark/img/sites/sudokuwiki.png" alt="sudokuwiki.org" class="pm-site"/></a> <a href="https://hodoku.sourceforge.net/en/tech_last.php#ts" title="HoDoKu"><img src="/pencilmark/img/sites/hodoku.png" alt="HoDoKu" class="pm-site"/></a> |
