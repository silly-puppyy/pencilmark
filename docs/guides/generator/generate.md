---
title: Generate a puzzle
description: Ask the generator for a classic or a variant puzzle with a given band, technique or rule set.
---

# Generate a puzzle

pencilmark's generator makes puzzles to order: you say what the board holds and what the grade card must show, and it
returns a unique puzzle that meets the request. This guide generates a Hard classic that needs an X-Wing, then a small variant;
[Write a variant puzzle file](../grader/variant-file.mdx) explains the file the variant comes back as. The examples use
Python; on the command line, `pencilmark generate spec.json` runs a request saved as a file and prints the puzzle
(`--result` prints the puzzle, its card and the run's `info` as one JSON object).

## 1. A request

A request is a `pencilmark-spec`: it looks like a puzzle file, with blanks where the generator decides.

```python
import pencilmark

spec = {
    "format": "pencilmark-spec", "format_version": 1,
    "board": {"rows": 9, "cols": 9},
    "digits": 9,
    "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}],
    "symmetry": [{"kind": "rot180", "of": "givens"}],
    "where": {"band": "Hard", "contains": ["XWG"]},
    "quality": {"preset": "standard"},
    "limits": {"time": 120, "seed": 21},
}
```

- `board`, `digits` and `rules` are as in a puzzle file. Here the only rule is the usual rows, columns and boxes.
- `symmetry` asks for givens that look the same after a half turn of the grid.
- `where` is what the card must show: band Hard, with X-Wing (code `XWG`) in `contains`.
- `quality` turns on the publishing checks: the generator throws away candidates a publisher would refuse
  ([Publishing checks](#publishing-checks) below).
- `limits`: the search stops after `time` seconds (grading the result comes on top: seconds for a classic, minutes for
  a hard variant); `seed` picks which puzzle you get.

## 2. Run it

```python
r = pencilmark.generate(spec)
print(pencilmark.write.plain(r["puzzle"]))
card = r["card"]
print(card["band"], card["difficulty"], card["time"], [c["chip"] for c in card["contains"]])
```

```
..2.987..8.5..7....3.2.5....8..5..4.5.1...6.3.6..1..2....5.1.7....4..3.9..397.5..
Hard 5.9 10.9 ['HSI', 'NSI/MSI', 'XWG/MCH']
```

The run took about a second. The result has three parts:

- `r["puzzle"]`: a `pencilmark-puzzle` with its solution, ready to save as a file;
- `r["card"]`: its grade card, as `pencilmark.rate` would give it;
- `r["info"]`: how the run went, for example `{'givens': 30, 'attempts': 18, 'rejected': {'band too low (logic pre-check)': 17}, ...}`.
  `info.warnings` lists hints about the request: without `where.band` or `where.difficulty` the search is the broadest
  (every technique, up to Extreme) and can be slow on sparse variants, so it suggests aiming it (the command line prints
  these as notes).
  The generator tried 18 puzzles; 17 were too easy.

Change `seed` for a different puzzle. With the same seed and request, the result is the same every time.

### Publishing checks

Checks are opt in: a request without `quality` gets none. `{"preset": "standard"}` turns on five, each refusing a
candidate: a rule family nothing needs (`decorative`), mostly givens (`trivial`), a solve that needs trial or forcing
(`trial`), candidate steps that do little around one hard step (`thin`), and a difficulty outside the published range
for its band (`unusual`). Name a check to change it: with the preset, it adjusts that check and keeps the others;
without the preset, only the checks you name run.

```python
relaxed = {"preset": "standard", "thin": {"limit": 0.2}}         # the preset, thin relaxed
learner = {"preset": "standard", "trivial": {"severity": "off"}}  # the preset, mostly-given puzzles allowed
one = {"trial": {"severity": "reject"}}                           # only this check
```

`info.rejected` counts the candidates each check refused (another seed of the request above found a Hard puzzle whose
X-Wing did too little, `thin`, and searched on). [Grade card](../../formats/grade-card.md), section 4, lists every check
and its limit.

## 3. A variant

Templates ask the generator to place rules. A rule with a `count` and no cells is a template:

```python
spec = {
    "format": "pencilmark-spec", "format_version": 1,
    "board": {"rows": 6, "cols": 6},
    "digits": 6,
    "givens": {"count": [4, 8]},
    "rules": [
        {"type": "box_grid", "box": [2, 3], "count": [3, 2]},
        {"type": "line", "kind": "thermo", "count": 2},
        {"type": "edge", "kind": "kropki", "count": [1, 3]},
    ],
    "where": {"band": "Medium"},
    "quality": {"preset": "standard"},
    "limits": {"time": 300, "seed": 3},
}
r = pencilmark.generate(spec)
print(pencilmark.write.pencilmark(r["puzzle"]))
```

This asks for a 6×6 with exactly two thermometers, one to three Kropki dots and four to eight givens, graded Medium.
The puzzle in [Write a variant puzzle file](../grader/variant-file.mdx) came from a request like this one. `pencilmark.write.pencilmark`
writes the puzzle in the format's canonical layout, one rule per line.

A template can also limit the shape of what it places: `"length": [8, null]` asks for lines of eight cells or more,
`"size": 2` for two-cell cages, `"sum": 10` for cages that add up to 10. The count `"max"` asks for as many as fit,
and `"where": {"difficulty": "max"}` for the hardest puzzle found; both searches use the whole time limit.

[Generator examples](generator-examples.mdx) shows requests of every kind (templates, shapes, counts, targets,
symmetry, board sizes), with the puzzle each produced and how long it took.

## 4. Typical difficulty

Without a difficulty range the generator removes every given it can. A puzzle with few givens takes long to scan even
when it needs only singles, so a Very Easy request comes back at about 4-5, the hard end of published Very Easy
puzzles. For a gentle puzzle, add a range:

```json
"where": {"band": "Very Easy", "difficulty": [3.2, 4.0]}
```

The middle half of published puzzles per band (development set: 7,155 puzzles from seven sources with human data):

| Band | Classic 9×9 | Variants |
|---|---|---|
| Very Easy | up to 4.4 | up to 5.5 |
| Easy | 4.9 to 6.0 | 5.2 to 7.6 |
| Medium | 6.3 to 6.9 | 8.1 to 10.0 |
| Hard | 5.6 to 6.6 | 6.2 to 8.0 |
| Very Hard | 6.9 to 7.7 | 9.8 to 12.5 |
| Expert | 7.8 to 10.1 | 9.8 to 12.9 |
| Extreme | (too few) | (too few) |

A band says which techniques a puzzle needs and the difficulty how hard its steps are to find, so a Hard puzzle (one
X-Wing) is often quicker than a long Medium. For classics, Andrew Stuart's sudokuwiki.org grades read directly on
pencilmark's difficulty (the two scales agree within 0.3 on the same puzzles): Gentle 3 to 4, Moderate 4 to 5, Tough 5
to 7, Diabolical 7 to 9, Extreme 9 and above. With the standard preset the check `unusual` refuses a result outside the
middle 80% of its band (Very Easy has no floor, Extreme no ceiling); `{"unusual": {"severity": "off"}}` lets it through.

## 5. When the generator cannot do it

A request the generator cannot meet in time raises `pencilmark.GenerationFailed` with the reason; it never returns a
puzzle that misses the request:

```python
pencilmark.generate(dict(spec, where={"band": "Extreme"}, limits={"time": 10, "seed": 1}))
```

A message like this one (the counts depend on the machine):

```
pencilmark.errors.GenerationFailed: no puzzle met the spec in 10 s (13 attempts; rejected: band too low (logic pre-check) x12, ...)
```

The message says what went wrong: every puzzle tried was too easy. Parts of the format kept for later versions are
refused at once, with the part named (`pencilmark.NotSupportedError`):

```python
pencilmark.generate(dict(spec, where={"band": "Hard", "not_contains": ["XWG"]}))
```

```
pencilmark.errors.NotSupportedError: where.not_contains is reserved for a later version of the spec (docs/formats/generator-spec.md 7)
```
