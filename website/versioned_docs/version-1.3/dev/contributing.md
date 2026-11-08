---
description: "How to set up, prove a change, and the style pencilmark's code and docs follow."
---

# Contributing

## Set up

You need Python 3.10 or newer and a C++17 compiler; the engine is built when the package installs.

```
git clone https://github.com/silly-puppyy/pencilmark && cd pencilmark
pip install -e ".[test]"                      # builds the C++ engine and installs pytest, pytest-xdist, jsonschema
python -m pytest -q -n auto tests             # the quick suite: about 10 seconds
```

`pip install -e ".[test,verify]"` adds OR-Tools, which the uniqueness check falls back on when the engine's search hits its node or time limit. After a change to
`csrc/`, run `pip install -e .` again to rebuild the engine.

## Where things live

| Path | What |
|---|---|
| `src/pencilmark/api.py` | the public functions (`rate`, `load`, `solve`, `generate`, ...) |
| `src/pencilmark/export.py`, `band_path.py`, `card.py` | the card: its fields, the band route and technique list, difficulty and time |
| `src/pencilmark/exchange/`, `rules/` | the puzzle format: reading, checking, writing; `rules/` holds the kind registries of lines, edges and cell clues |
| `src/pencilmark/explain/` | step explanations |
| `src/pencilmark/data/` | techniques, codes and fitted parameters (CSV / JSON); every fitted number lives here |
| `csrc/` | the C++ engine: techniques, move listing, the exhaustive search |
| `tests/` | the quick suite, with snapshot fixtures in `tests/fixtures/` |
| `tests/golden/` | the golden corpus: every output for 55 puzzles |
| `tools/` | the golden tool, the docs generators, the drawing |
| `docs/`, `website/` | the documentation site (Docusaurus) |

[Architecture](https://silly-puppyy.github.io/pencilmark/guides/development/architecture/) explains how a card is computed
and which file holds each part of the engine; the [reference](https://silly-puppyy.github.io/pencilmark/reference/)
lists every module, function and class, Python from the docstrings and C++ from the header comments (`///` above a
declaration, `///<` after a member; read by Doxygen, so building it needs `doxygen`).

## Prove a change

```
python -m pytest -q -n auto tests             # about 10 seconds
python -m pytest -q -n auto -m slow tests     # every Python example in the docs runs as written (about 20 s)
python tools/golden.py check                  # every output of 55 puzzles identical (about a minute)
```

`python tools/tasks.py check` runs all three; `python tools/tasks.py` lists the other jobs (lint, docs, serve, fixtures,
release).

The golden check compares each puzzle's full card (with steps at every explanation level), its description, its
export and the engine's input against `tests/golden/expected.jsonl`, and prints every difference.

- **A change that should alter nothing** (a refactor, a speed-up) must report every record identical.
- **A change that should alter output** (a fix, a new technique, a new parameter) gets two commits: the change, with a
  line under "Unreleased" in `CHANGELOG.md`, then the rewritten records (`python tools/golden.py write`) on their own,
  after you have read every difference and agree with it.

- **A change made because of a measurement** (a price, a term, a default), and a measured idea that was dropped,
  gets its row in the [experiment log](https://silly-puppyy.github.io/pencilmark/grades/experiments/) in the same commit: what was tried, on which data,
  the numbers, and the verdict.

Write commit messages that say what changed and why, and what the checks showed.

## Style

Code follows the [code style](https://silly-puppyy.github.io/pencilmark/dev/code-style/) (ruff, line length 120:
`ruff check` and `ruff format`, plus `codespell`; `python tools/tasks.py lint` runs all three, as CI does on every
push, and `pre-commit install` runs them before each commit); text follows the
[writing style](https://silly-puppyy.github.io/pencilmark/dev/writing-style/): result first, plain words, British
spelling. [Add a technique](https://silly-puppyy.github.io/pencilmark/guides/development/add-technique/) lists every place a new solving
technique touches, and [Add a rule kind](https://silly-puppyy.github.io/pencilmark/guides/development/add-rule-kind/) every place a new
line, edge or cell kind touches.

## Conduct and security

Everyone taking part follows the [code of conduct](https://github.com/silly-puppyy/pencilmark/blob/main/CODE_OF_CONDUCT.md). Report a security problem privately, as
[SECURITY.md](https://github.com/silly-puppyy/pencilmark/blob/main/SECURITY.md) says, not in a public issue.
