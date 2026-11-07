---
title: Grade many puzzles
description: Grade a file of puzzles in parallel, choose the output columns, and keep full cards as JSON lines.
---

# Grade many puzzles

Put one puzzle per line in a file and pass the file to `pencilmark rate`. Each line can be in any format pencilmark reads
(a classic string, a sudokuwiki string, pencilmark JSON on one line, a link, the path of a `.json` file), detected per
line; lines starting with `#` are skipped.

```
$ cat puzzles.txt
3.76...5..827.3...6..82.7...7....34...........54....2...8.41..6...9.648..1...82.3
9.1..4..8.7.26...9.24.9.....9..87....8.....7....45..9.....3.18.8...16.5.7..8..6.3
....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......
..6...9.2.....4.8..8..1...4..4.857..2..467..9..819.2..4...2..1..6.3.....5.1...3..
```

## Grade in parallel

`-j N` grades N puzzles at a time. The output keeps the input order:

```
$ pencilmark rate puzzles.txt -j 4
Very Easy	3.5	4.5	Hidden Single
Easy	4.1	5.2	Naked Single
Hard	5.8	10.7	X-Wing
Very Hard	6.7	13.7	WXYZ-Wing
```

The columns are band, difficulty, time in minutes and the hardest technique.

## Choose the columns

`--print` takes a template; `%i` is the line number, `%c` the techniques above Very Easy with how often each is used:

```
$ pencilmark rate puzzles.txt -j 4 --print '%i,%b,%d,%m,%c'
1,Very Easy,3.5,4.5,
2,Easy,4.1,5.2,NSI
3,Hard,5.8,10.7,NSI NPR/HPR XWG/KTE/CSM/MCH
4,Very Hard,6.7,13.7,NSI PPRx2 HPR/NQDx2 SKY/KTE/CSM/MCH WXZ
```

[Usage](../../start/usage.mdx#command-line) lists every `%` field.

## Keep the full cards

`--json` prints one complete card per line, with its line number, ready for a JSON-lines file:

```
$ pencilmark rate puzzles.txt -j 4 --json > cards.jsonl
$ head -c 120 cards.jsonl
{"line": 1, "format": "pencilmark-grade", "format_version": 1, "grader": {"name": "pencilmark", "version": "1.1.0"}, "di
```

## Grade faster

Most of the time on a hard puzzle goes into `contains`, the search for the shortest technique list. Ask only for the
fields you need and that search is skipped; band, difficulty and time stay the same:

```
$ pencilmark rate puzzles.txt -j 4 --fields difficulty,time,band
```

`--no-alternatives` keeps `contains` but skips the search for interchangeable techniques. `--max-seconds N` caps the
time per puzzle; a card that hits the cap says `"completed": false` ([Grade card](../../formats/grade-card.md)).

## Bad lines

A line that cannot be read is reported in place and the rest go on:

```
$ printf '123\n' | pencilmark rate -
error	1	FormatError: a plain string has 16, 36, 64, 81, 100, 144, 196, 225, 256, 400, 625 characters; this one has 3
```

A puzzle with more than one solution prints `not unique` in the band column.

## From Python

```python
import pencilmark

puzzles = [line.strip() for line in open("puzzles.txt") if line.strip()]
cards = pencilmark.rate_many(puzzles, jobs=4)       # input order kept
for card in cards:
    if "error" in card:                             # not unique, no solution, unreadable
        print("error:", card["error"])
    else:
        print(card["band"], card["difficulty"], card["time"])
```

`rate_many` takes every option `rate` does; `alternatives=False` is the `--no-alternatives` of the command line.

A puzzle that fails gives `{"error": "..."}` in its place instead of raising, so one bad puzzle does not stop the
batch.
