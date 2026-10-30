# Python API

Everything below is importable from `pencilmark` directly (`pencilmark.rate`, `pencilmark.to_export`, …). This page is generated from the docstrings (`tools/gen_api_md.py`).

## `rate`

```python
rate(
    puzzle,
    steps=False,
    max_seconds=None,
    mode='human',
    se=False,
    fields=None,
    allow_guessing=False,
    explain=None,
    quality=None,
    alternatives=True,
)
```

the "sudoku-grade" card of one puzzle (docs/GRADE.md) with the requested top-level fields only. Default fields: difficulty, time, band, contains (format, format_version, grader always). Optional: band_index, issues, reject, warning (publishing checks), time_mean / time_pNN (any percentile 1-99, e.g. time_p80), time_dist, elapsed (wall seconds of the call), se, steps, describe, symmetry. explain="short" / "teach" / True (both) adds explanations to the steps. steps=True is shorthand for the steps field with both explanation levels; se=True for se. Raises NotUnique / NoSolution / Undecided for a puzzle without exactly one solution. allow_guessing=True: guess where no technique applies (band "Unknown") instead of proving by full search (Trial and error, Extreme). quality: the issue checks, e.g. {"trivial": {"limit": 0.5}, "trial": {"severity": "off"}} (docs/GRADE.md 4). alternatives=False skips the search for interchangeable techniques (each chip in contains lists one code); band, difficulty and time are the same either way, and the card comes much faster.

## `rate_many`

```python
rate_many(
    puzzles,
    jobs=1,
    steps=False,
    max_seconds=None,
    mode='human',
    se=False,
    fields=None,
    allow_guessing=False,
    explain=None,
    quality=None,
)
```

cards for many puzzles, in input order; jobs > 1 uses worker processes. A puzzle that cannot be rated (not unique, no solution, unreadable) gives {"error": "..."}.

## `solve`

```python
solve(puzzle, info=False)
```

the unique solution as a list of digits (cell order of the puzzle); NotUnique / NoSolution otherwise. Uses the engine's exhaustive C++ search; CP-SAT (optional OR-Tools) only if that search hits its node limit. info=True: {"solution": [...], "seconds": wall-clock seconds of the search} instead of the bare list.

## `load`

```python
load(puzzle)
```

any accepted input -> a finalized engine Puzzle.

## `to_export`

```python
to_export(puzzle, meta=None, with_solution=True, describe=True, **meta_kw)
```

the "sudoku-puzzle" exchange dict (format_version 1, docs/FORMAT.md): canonical, houses and rules with "r1c1" cells. Metadata goes in its own optional "meta" object: pass a dict (meta={"title": ..., "author": ..., "date": ...}) and / or keywords (title=..., author=..., source=..., id=..., url=..., date=..., rules_text=...); metadata already in a JSON input is kept. describe=True fills an EMPTY meta.type / meta.rules_text from describe(); it never overwrites them.

## `dumps`

```python
dumps(doc, pretty=True)
```

canonical JSON text of a sudoku-puzzle dict (fixed key order; pretty: one grid row per line, one rule per line)

## `fingerprint`

```python
fingerprint(puzzle)
```

content fingerprint "sha256:<hex>" of the canonical form (rules, grid, givens, candidates; no meta / style / solution)

## `validate`

```python
validate(doc)
```

strict reading checks of a format_version 1 dict (docs/FORMAT.md section 4); raises FormatError

## `describe`

```python
describe(puzzle)
```

{"type": variant name, "rules": {short name: one-sentence rule, ...}} from the rules alone (pencilmark/variants.py)

## `NotUnique`

```python
class NotUnique(ValueError)
```

the puzzle has more than one solution

## `NoSolution`

```python
class NoSolution(ValueError)
```

the puzzle has no solution

## `Undecided`

```python
class Undecided(RuntimeError)
```

the exhaustive search hit its node limit and OR-Tools (pip install "pencilmark[verify]") is not available
