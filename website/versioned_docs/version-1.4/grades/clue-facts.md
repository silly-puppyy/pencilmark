---
title: Clue facts
description: The little facts solvers learn for each common rule, and which step of the grader uses each.
---

# Clue facts

Every common rule comes with a few facts that solvers learn once and then use without thinking: "a 5 is never
on a German whisper", "a 5-cell renban always holds a 5". This page lists them, with how many Cracking the
Cryptic solve videos state each one (counted in our research notes; 0 = not counted).

**Applied by** names the grader step that makes the fact's eliminations, with its price. **ClueFacts** and
**ClueShape** read the facts of two-cell rules off the clues before solving and cost the least. Facts about
longer rules come from that rule's own technique, and a few are built into how the rule is modeled. Rules
that aren't on this page, or rules a setter made up, are worked out from the rule text instead.

This page is generated from `pencilmark/explain/clue_facts.py` (`tools/gen_clue_facts_md.py`). Each fact
is checked on a small example: no completed grid breaks it, and the grader makes it.

## German Whispers

| Fact | Videos | Applied by |
|---|---|---|
| A 5 can never be on a German whisper: no digit is 5 or more away from it. | 76 | ClueFacts (0.8) |
| Neighbors on a German whisper alternate between low (1-4) and high (6-9) digits. | 19 | Placing the digit: the rule acts on its neighbor like a sudoku peer |
| A 4 or a 6 cannot sit between two whisper cells that see each other: a 4 needs a 9 on both sides, a 6 a 1. | 9 | ClueShape (1.6) |

## Dutch Whispers

| Fact | Videos | Applied by |
|---|---|---|
| A 5 can sit on a Dutch whisper, but only next to a 1 or a 9, so the low / high alternation can switch at it. | 4 | Placing the digit: the rule acts on its neighbor like a sudoku peer |

## Kropki

| Fact | Videos | Applied by |
|---|---|---|
| A 5, 7 or 9 can never be on a black dot: its double is too big and it has no half. | 59 | ClueFacts (0.8) |
| A black dot holds 1-2, 2-4, 3-6 or 4-8: a 1 pairs only with 2, a 3 with 6, an 8 with 4. | 21 | Placing the digit: the rule acts on its neighbor like a sudoku peer |
| The middle of two black dots whose ends see each other is 2 or 4: a 1, 3, 6 or 8 would need the same partner twice. | 15 | ClueShape (1.6) |
| A 1 on a white dot pairs only with 2 and a 9 only with 8, so the middle of two white dots whose ends see each other is never 1 or 9. | 56 | ClueShape (1.6) |
| A white dot always joins an odd and an even digit. | 14 | Placing the digit: the rule acts on its neighbor like a sudoku peer |

## XV

| Fact | Videos | Applied by |
|---|---|---|
| A 5 can never be on an X: its partner would be another 5. |  | ClueFacts (0.8) |
| A V holds 1-4 or 2-3, so only the digits 1-4. |  | ClueFacts (0.8) |

## Thermo

| Fact | Videos | Applied by |
|---|---|---|
| A thermometer cell with k cells before it is at least k + 1, and with m cells after it at most 9 - m: on a 4-cell thermo the bulb is 1-6 and the tip 4-9. | 72 | ClueFacts (0.8) |
| Branches that share a bulb each count from it: the bulb is low enough for the longest branch. |  | ClueFacts (0.8) |

## Arrow

| Fact | Videos | Applied by |
|---|---|---|
| An arrow's circle is at least the smallest sum of its shaft: 3 for two cells that see each other, 6 for three. | 116 | SumBound (1.9), ArrowCombination (2.5) |
| A shaft digit is smaller than its circle, so 9 is never on a shaft of two or more cells, and 8 and 9 are never on three cells that see each other. | 88 | SumBound (1.9), ArrowCombination (2.5) |

## Killer

| Fact | Videos | Applied by |
|---|---|---|
| A cage of n cells and total s uses one of the sets of n different digits adding to s: a 3-cell 7 is 1, 2, 4 and a 3-cell 24 is 7, 8, 9. | 213 | SumBound (1.6) |
| A 2-cell cage has no middle digit twice: a 10 has no 5, and a 3 is 1 and 2. |  | CageCombination (2.0) |
| A cage's forced digits leave the rest of the house it lies in: a 1-2-4 cage in a box takes 1, 2 and 4 from the other six cells. | 35 | ComboLock (3.0) |
| An 8-cell cage misses one digit, 45 minus its total: an 8-cell 40 has no 5. | 4 | HiddenSingle(direct) (3.4) |

## Renban

| Fact | Videos | Applied by |
|---|---|---|
| A renban of n cells always holds the digits 10 - n to n: a 5-cell renban has a 5, a 7-cell one 3 to 7. | 33 | ComboLock (3.7) |
| Digits on a renban of n cells lie within n - 1 of each other: a 4-cell renban with a 2 holds nothing above 5. | 4 | SumBound (1.9) |

## Entropic Lines

| Fact | Videos | Applied by |
|---|---|---|
| Any three neighboring cells on an entropic line hold one low (1-3), one middle (4-6) and one high (7-9) digit. | 13 | Placing the digit: the rule acts on its neighbor like a sudoku peer |
| Cells three apart on an entropic line hold the same class. | 6 | Placing the digit: the rule acts on its neighbor like a sudoku peer |

## Modular Lines

| Fact | Videos | Applied by |
|---|---|---|
| Cells three apart on a modular line leave the same remainder divided by 3; any three neighbors hold one each of 1-4-7, 2-5-8 and 3-6-9. | 6 | Placing the digit: the rule acts on its neighbor like a sudoku peer |

## Palindrome

| Fact | Videos | Applied by |
|---|---|---|
| Mirrored cells of a palindrome hold the same digit, so a digit one of them cannot hold leaves the other. | 13 | LineRange (2.1) |

## Zipper Lines

| Fact | Videos | Applied by |
|---|---|---|
| The center of a zipper is its largest digit: on three cells the center is at least 3 and the ends are never 9. | 13 | LineRange (2.4) |
| With an odd center, each pair on a zipper adds to an odd total: one digit of every pair is odd, the other even. |  | LineRange (2.4) |

## Between Lines

| Fact | Videos | Applied by |
|---|---|---|
| Digits on a between line lie strictly between its circles, so 1 and 9 are never on it. | 3 | LineRange (2.5) |

## Region Sum Lines

| Fact | Videos | Applied by |
|---|---|---|
| Each box's part of a region-sum line has the same total, so a single cell equals the sum of the two cells across the border: at least 3. | 6 | LineRange (2.4) |

## Sandwich

| Fact | Videos | Applied by |
|---|---|---|
| A sandwich of 35 holds every digit 2-8, so the 1 and 9 are at the ends of the row. | 10 | SandwichCombination (3.9) |
| A sandwich of 0 means the 1 and the 9 are next to each other. | 3 | SandwichCombination (3.9) |

## Skyscraper

| Fact | Videos | Applied by |
|---|---|---|
| A skyscraper clue of 1 sees only the first cell, so it holds the 9. | 4 | SkyscraperCombination (3.9) |
| A skyscraper clue above 1 means the first cell is not the 9. |  | SkyscraperCombination (3.9) |

## Quadruple

| Fact | Videos | Applied by |
|---|---|---|
| Every digit of a quadruple circle is among its four cells, so it leaves the rest of a house that holds all four. | 7 | ComboLock (2.8) |
