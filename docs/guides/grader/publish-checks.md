---
title: Check a puzzle before publishing
description: Ask for the publishing checks (issues), read what they mean, and tune or switch off each check.
---

# Check a puzzle before publishing

Besides grading, pencilmark can look for the problems an editor would catch: a rule nobody needs, a puzzle that is
mostly given, a solve that is singles around one hard step. Ask for the `issues` and `reject` fields:

```
$ echo '.3.1.78..........91.2.6.3..5...2...4..96.17..8...3...2..8.9.6.53..........68.3.9.' > hard.txt
$ pencilmark rate hard.txt --json --fields band,issues,reject
{"line": 1, "format": "sudoku-grade", "format_version": 1, "grader": {"name": "pencilmark", "version": "1.1.0"}, "band": "Hard", "issues": [{"code": "thin", "severity": "warning", "text": "candidate steps carry only 24% of the effort; the rest is singles"}], "reject": false}
```

A generated classic: 52 singles and one Skyscraper near the end. Each issue has a `code`, a `severity` and a
sentence. `reject` is true when any issue has severity `reject`: a puzzle an
editor would send back. A `warning` is worth a look but may be intended.

## What the checks find

- In the rules: a rule family nobody needs (`decorative`, `redundant`) or that the solve hardly uses (`barely_used`).
- In the givens: too many of them (`trivial`).
- In the solve: candidate steps that do little (`thin`), a long routine solve rated easy (`tedious`), steps that
  rely on uniqueness or on trial and error (`uniqueness`, `trial`), or a difficulty unusual for the band (`unusual`).

The warning above is `thin`: the one hard step carries a quarter of the effort and everything else is singles.
Published Hard puzzles rarely go below that (Andrew Stuart's grader would not publish this one: "too few candidates
removed using candidate strategies").

[Grade card](../../formats/grade-card.md#4-issues) lists every check with its default limit.

## A rule that is not needed

Add a thermometer to a classic, along three cells whose digits happen to increase (1, 5, 7 in the solution):

```python
import pencilmark

doc = pencilmark.to_export("....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......")
doc["rules"].append({"type": "line", "kind": "thermo", "cells": ["r1c1", "r1c2", "r1c3"], "id": "extra-thermo"})
pencilmark.rate(doc, fields=["issues", "reject"])["issues"]
```

```
[{"code": "redundant", "severity": "warning", "text": "thermo line (rule 1): used in 1 step, but the puzzle is unique without it", "rules": [1], "ids": ["extra-thermo"]}]
```

The puzzle is unique without the thermometer, so it is reported. When no step uses such a rule the code is
`decorative` (a reject); when the solve does use it, as here, the code is `redundant` (a warning). `rules` gives the
rule's position in the file and `ids` its `id`, so a tool can point at it.

The rule checks look at whole families: all the thermometers together, all the white dots together. One extra dot
among dots the puzzle needs is not reported.

## Too many givens

A classic with two thirds of its cells given is rejected:

```python
g = ".57.42.6346.17.95.9.86.54.1.35.69.8761.78.24.7.45.13.6.72.94.1884.25.73.3.68.75.4"
pencilmark.rate(g, fields=["band", "issues", "reject"])
# band 'Very Easy', issues [{'code': 'trivial', 'severity': 'reject', 'text': '67% of the cells are given'}], reject True
```

## Tune the checks

Every check takes a `severity` (`reject`, `warning`, or `off`) and, where it has one, a `limit`:

```python
card = pencilmark.rate(puzzle, fields=["issues", "reject"],
                       quality={"trivial": {"limit": 0.7}, "thin": {"severity": "off"}})
```

With `trivial` raised to 70%, the puzzle above passes (`issues` is empty, `reject` false).

On the command line the same settings are `--quality trivial.limit=0.7,thin.severity=off`.
