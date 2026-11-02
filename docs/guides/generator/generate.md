---
title: Generate a puzzle
description: Ask the generator for a classic or a variant puzzle with a given band, technique or rule set.
---

# Generate a puzzle

pencilmark's generator makes puzzles to order: you say what the board holds and what the grade card must show, and it
returns a unique puzzle that meets the request. This guide generates a Hard classic that needs an X-Wing, then a small variant;
[Write a variant puzzle file](../grader/variant-file.mdx) explains the file the variant comes back as. The generator is used
from Python.

## 1. A request

A request is a `sudoku-spec`: it looks like a puzzle file, with blanks where the generator decides.

```python
import pencilmark

spec = {
    "format": "sudoku-spec", "format_version": 1,
    "board": {"rows": 9, "cols": 9},
    "digits": 9,
    "rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}],
    "symmetry": [{"kind": "rot180", "of": "givens"}],
    "where": {"band": "Hard", "contains": ["XWG"]},
    "limits": {"time": 120, "seed": 7},
}
```

- `board`, `digits` and `rules` are as in a puzzle file. Here the only rule is the usual rows, columns and boxes.
- `symmetry` asks for givens that look the same after a half turn of the grid.
- `where` is what the card must show: band Hard, with X-Wing (code `XWG`) in `contains`.
- `limits` gives the run 120 seconds at most; `seed` picks which puzzle you get.

## 2. Run it

```python
r = pencilmark.generate(spec)
print(pencilmark.to_string(r["puzzle"], "plain"))
card = r["card"]
print(card["band"], card["difficulty"], card["time"], [c["chip"] for c in card["contains"]])
```

```
.74.1...6........4..24..59....18.9...1.9.2.5...9.64....91..73..8........5...9.82.
Hard 7.1 13.0 ['HSI', 'PPR/MSI', 'XWG/SCL/MCH']
```

The run took under a second. The result has three parts:

- `r["puzzle"]`: a `sudoku-puzzle` with its solution, ready to save as a file;
- `r["card"]`: its grade card, as `pencilmark.rate` would give it;
- `r["info"]`: how the run went, for example `{'givens': 28, 'attempts': 9, 'rejected': {'band too low (logic pre-check)': 8}, ...}`.
  `info.warnings` lists hints about the request: without `where.band` or `where.difficulty` the search is the broadest
  (every technique, up to Extreme) and can be slow on sparse variants, so it suggests aiming it (the command line prints
  these as notes).
  The generator tried nine puzzles; eight were too easy.

Change `seed` for a different puzzle. With the same seed and request, the result is the same every time.

## 3. A variant

Templates ask the generator to place rules. A rule with a `count` and no cells is a template:

```python
spec = {
    "format": "sudoku-spec", "format_version": 1,
    "board": {"rows": 6, "cols": 6},
    "digits": 6,
    "givens": {"count": [4, 8]},
    "rules": [
        {"type": "box_grid", "origin": "r1c1", "box": [2, 3]},
        {"type": "line", "kind": "thermo", "count": 2},
        {"type": "edge", "kind": "kropki", "count": [1, 3]},
    ],
    "where": {"band": "Medium"},
    "limits": {"time": 300, "seed": 3},
}
r = pencilmark.generate(spec)
print(pencilmark.dumps(r["puzzle"]))
```

This asks for a 6×6 with exactly two thermometers, one to three Kropki dots and four to eight givens, graded Medium.
The puzzle in [Write a variant puzzle file](../grader/variant-file.mdx) came from a request like this one. `pencilmark.dumps`
writes the puzzle in the format's canonical layout, one rule per line.

A template can also limit the shape of what it places: `"length": [8, null]` asks for lines of eight cells or more,
`"size": 2` for two-cell cages, `"sum": 10` for cages that add up to 10. The count `"max"` asks for as many as fit,
and `"where": {"difficulty": "max"}` for the hardest puzzle found; both searches use the whole time limit.

[Generator examples](generator-examples.mdx) shows requests of every kind (templates, shapes, counts, targets,
symmetry, board sizes), with the puzzle each produced and how long it took.

## 4. Typical difficulty

Without a difficulty range the generator removes every given it can. A puzzle with few givens takes long to scan even
when it needs only singles, so a Very Easy request comes back at about 4-5, the hard end of published Very Easy
puzzles. For a gentle puzzle, add a range, and the publishing checks (`"quality": {}`, recommended):

```json
"where": {"band": "Very Easy", "difficulty": [2.8, 3.8]}, "quality": {}
```

The middle half of published puzzles per band (development set: 6,452 puzzles from seven sources with human data):

| Band | Classic 9×9 | Variants |
|---|---|---|
| Very Easy | up to 3.8 | up to 4.9 |
| Easy | 4.5 to 5.9 | 4.8 to 7.5 |
| Medium | 6.3 to 7.4 | 8.8 to 11.0 |
| Hard | 5.3 to 6.7 | 5.9 to 8.4 |
| Very Hard | 7.1 to 8.2 | 10.6 to 13.4 |
| Expert | 8.2 to 10.9 | 10.8 to 13.6 |
| Extreme | (too few) | 13.7 and above |

A band says which techniques a puzzle needs and the difficulty how hard its steps are to find, so a Hard puzzle (one
X-Wing) is often quicker than a long Medium. For classics, Andrew Stuart's sudokuwiki.org grades read directly on
pencilmark's difficulty (the two scales agree within 0.3 on the same puzzles): Gentle 3 to 4, Moderate 4 to 5, Tough 5
to 7, Diabolical 7 to 9, Extreme 9 and above. With `"quality": {}` the check `unusual` refuses a result outside the
middle 80% of its band (Very Easy has no floor, Extreme no ceiling); `{"unusual": {"severity": "off"}}` lets it through.

## 5. When the generator cannot do it

A request the generator cannot meet in time raises `pencilmark.GenerationFailed` with the reason; it never returns a
puzzle that misses the request:

```python
pencilmark.generate(dict(spec, where={"band": "Extreme"}, limits={"time": 10, "seed": 1}))
```

A message like this one (the counts depend on the machine):

```
pencilmark.api.GenerationFailed: no puzzle met the spec in 10 s (13 attempts; rejected: band too low (logic pre-check) x12, ...)
```

The message says what went wrong: every puzzle tried was too easy. Parts of the format kept for later versions are
refused at once, with the part named (`pencilmark.NotSupportedError`):

```python
pencilmark.generate(dict(spec, where={"band": "Hard", "not_contains": ["XWG"]}))
```

```
pencilmark.exchange.NotSupportedError: where.not_contains is reserved for a later version of the spec (docs/formats/generator-spec.md 7)
```
