---
title: Generate a puzzle
description: Ask the generator for a classic or a variant puzzle with a given band, technique or rule set.
---

# Generate a puzzle

pencilmark's generator makes puzzles to order: you say what the board holds and what the grade card must show, and it
returns a unique puzzle that meets the request. In this tutorial you generate a Hard classic that needs an X-Wing, then
a small variant. It assumes you have done [Write a variant puzzle file](variant-file.md). The generator is used from
Python.

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
The puzzle in [Write a variant puzzle file](variant-file.md) came from a request like this one. `pencilmark.dumps`
writes the puzzle in the format's canonical layout, one rule per line.

## 4. When the generator cannot do it

A request the generator cannot meet in time raises `pencilmark.GenerationFailed` with the reason; it never returns a
puzzle that misses the request:

```python
pencilmark.generate(dict(spec, where={"band": "Extreme"}, limits={"time": 10, "seed": 1}))
```

```
pencilmark.api.GenerationFailed: no puzzle met the spec in 10 s (7 attempts; rejected: band too low (logic pre-check) x7)
```

The message says what went wrong: every puzzle tried was too easy. Parts of the format kept for later versions are
refused at once, with the part named (`pencilmark.NotSupportedError`):

```python
pencilmark.generate(dict(spec, where={"band": "Hard", "not_contains": ["XWG"]}))
```

```
pencilmark.exchange.NotSupportedError: where.not_contains is reserved for a later version of the spec (docs/SPEC.md 7)
```
