---
title: Grade your first puzzle
description: Install pencilmark, grade a classic sudoku from the command line and from Python, and read the card.
---

# Grade your first puzzle

In ten minutes you will install pencilmark, grade one classic sudoku and read what the result means. You need Python
3.10 or newer.

## 1. Install

```
pip install pencilmark
```

The package includes its C++ engine, so there is nothing else to build.

## 2. Grade a puzzle from the command line

A classic puzzle can be written as one line of 81 characters, row by row, with `.` for an empty cell:

```
$ echo '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......' | pencilmark rate -
Hard	5.9	10.7	X-Wing
```

The four columns are the **band**, the **difficulty**, the **time** in minutes and the hardest technique the solve
needs. `-` means "read puzzles from standard input"; you can also pass a file with one puzzle per line.

## 3. Read the card

`--report` gives the same result as readable text:

```
$ echo '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......' | pencilmark rate - --report
#1  Hard  -  difficulty 5.9  -  time 10.7 min
   contains: Naked Pair (or Hidden Pair), X-Wing (or 2-String Kite / Simple Colouring / Short chain in the head)
```

- **Band: Hard.** The band says what you need to know. Hard means the puzzle needs a pattern most people learn after
  the basics; here an X-Wing.
- **Difficulty: 5.9.** How hard the steps are, on a scale with no ceiling. A typical newspaper medium is about 5.
- **Time: 10.7 min.** The predicted median solve time; the median classic takes about 12 minutes.
- **Contains.** The techniques the solve needs beyond singles, easiest first. "X-Wing (or 2-String Kite / …)" means any
  one of those does the job at that point.

## 4. See the steps

Add `-v` to list every step in solvers' notation (`-vv` gives plain sentences). The two steps that set the band are:

```
$ echo '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......' | pencilmark rate - --report -v
...
    25. Naked Pair: 4,8 in r4c48 => r4c5<>8, r4c6<>4
    26. X-Wing: 3 r58 c68 => r679c6<>3
...
```

`r4c48` means row 4, columns 4 and 8; `r4c5<>8` means "8 is removed from row 4, column 5".

## 5. The same in Python

```python
import pencilmark

card = pencilmark.rate("....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......")
print(card["band"], card["difficulty"], card["time"])     # Hard 5.9 10.7
print([c["chip"] for c in card["contains"]])              # ['HSI', 'NSI', 'NPR/HPR', 'XWG/KTE/SCL/MCH']
```

The card is a plain dictionary; [Grade card](../GRADE.md) lists every key. The `contains` entries carry short codes
(`XWG` is X-Wing); [Usage](../USAGE.md#technique-codes-the-contents-chips) lists them.

## 6. When a puzzle has no single answer

pencilmark grades only puzzles with exactly one solution. `pencilmark solve` tells you which case you have; the second
puzzle below is the first with one given removed:

```
$ printf '%s\n' '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......' \
    '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...........' | pencilmark solve -
157942863463178952928635471235469187619783245784521396572394618841256739396817524
not unique
```

From Python, `pencilmark.solve` raises `pencilmark.NotUnique` or `pencilmark.NoSolution` instead.

## Next

- [How a card is computed](../MODEL.mdx): where the three numbers come from.
- [Puzzle format](../FORMAT.md): write variant puzzles (killer cages, thermometers, multi-grid boards) as JSON.
- [Usage](../USAGE.md): every command, option and card field.
