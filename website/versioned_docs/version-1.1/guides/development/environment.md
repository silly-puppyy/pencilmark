---
title: Set up a development environment
description: Clone, build the engine, run the checks, rebuild after a C++ change, and look inside a card while you work.
---

# Set up a development environment

pencilmark is a Python package around a C++ engine. An editable install compiles the engine once and then picks up
every Python change without reinstalling; only a change to `csrc/` needs a rebuild.

## 1. Clone and install

You need Python 3.10 or newer and a C++17 compiler (GCC, Clang or MSVC).

```
git clone https://github.com/silly-puppyy/pencilmark
cd pencilmark
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[test]"
python tools/tasks.py test       # about 10 seconds
```

Add `verify` (`pip install -e ".[test,verify]"`) for OR-Tools, which the uniqueness check falls back on when the engine's search hits its node limit.

## 2. The everyday loop

| You changed | Run |
|---|---|
| Python | `python tools/tasks.py test`, then `python tools/tasks.py golden` before you commit |
| C++ (`csrc/`) | `pip install -e .` to rebuild the engine, then the same checks |
| docs | `python tools/tasks.py slow` (the examples run as written), `python tools/tasks.py serve` to look |

`python tools/tasks.py check` runs the quick suite, the doc examples and the golden check together; `python
tools/tasks.py` lists every job. One test file, or one test by name:

```
python -m pytest -q tests/test_format.py
python -m pytest -q tests -k listing_cache
```

The golden check (`tools/golden.py check`) compares every output of 55 puzzles with `tests/golden/expected.jsonl`. A
change that should alter nothing must keep every record identical; one that should alter output rewrites the records
in a commit of its own ([Contributing](../../dev/contributing.md)).

After a change to the engine or a rule, run the fuzzer: `python tools/fuzz.py 2000 --jobs 8` builds random puzzles
true of a random solution and checks that the engine accepts the solution, finds only it, makes no step against it,
round-trips the file and grades the transposed puzzle alike. Its referee, `tools/spec_check.py`, was written from the
rule pages alone, so it disagrees with the engine wherever one of them is wrong. A failure prints its seed;
`python tools/fuzz.py --seed S` prints that case's file. After a change to the generator, `python
tools/fuzz_generate.py 160 --jobs 8` sends it random requests and checks that every puzzle it returns meets its request.
`python tools/fuzz_inputs.py 2000` (`--specs` for requests, `--fpuzzles` for an f-puzzles document) breaks valid
files at random and checks that every broken one is refused with a message, not a crash.

## 3. The docs site

The site needs Node 20 or newer:

```
cd website && npm ci && cd ..
python tools/tasks.py serve      # http://localhost:3000/pencilmark/
```

`docs` builds without serving; both regenerate the API, techniques and parameters pages and the swatches first, so
never edit those generated files by hand.

## 4. Look inside a card

```python
import pencilmark
from pencilmark import api, band_path, cbackend, _csolver

puzzle = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."
p = pencilmark.load(puzzle)
P = api._params("human")

route = band_path.band_path(p, P)                       # the first route: easy to hard, simplest technique first
[(s["code"], s["band"]) for s in route["steps"][:5]]

steps, solved, stats = _csolver.solve(                  # where a solve spends its time, per strategy
    cbackend.to_cpuzzle(p), list(p.givens.items()), cbackend.Scorer(P).p, [], None, True, 5000, stats=True
)
sorted(stats.items(), key=lambda kv: -kv[1][0])[:5]     # (milliseconds, calls, calls that found moves)
```

`_csolver.listing_cache(False)` turns the engine's caches off, to check that a change gives the same moves with and
without them ([Architecture](architecture.md)).
