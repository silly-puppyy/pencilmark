---
title: Add a technique
description: Every place a new solving technique touches, from the C++ engine to the card, the explanation and the tests.
---

# Add a technique

A technique lives in the C++ engine; Python names it, prices it and explains it. Adding one touches the places below,
in this order. `tests/test_registry.py` fails until the engine, the registry and the explainer agree, so run it after
each step. The restructure planned in [Architecture](https://github.com/silly-puppyy/pencilmark/blob/main/ARCHITECTURE.md)
will shorten this list.

## 1. The engine (`csrc/`)

1. **The id.** Add the technique to `enum Tech` in `csrc/solver.hpp`, with the next free number and a one-line
   comment.
2. **The search.** Write `void Solver::your_technique(MoveBuf& out)` (declared in `solver.hpp`) in the file that holds
   its kind of logic ([Architecture](https://github.com/silly-puppyy/pencilmark/blob/main/ARCHITECTURE.md) lists them).
   For each move it finds, as the techniques already in that file do:
   - `new_move(out, YOUR_TECH, 1.0, n_cells)`, then one call of the file's elimination helper (`add_el` in
     `human.cpp`, `add_elim` in `extra.cpp` and `solver.cpp`) per elimination, or a placement;
   - `set_pattern(out, m, cells)` with the cells that make the pattern: explanations and the cells an app highlights
     come from it;
   - the move's descriptors in `m.meta` (cells, houses, digits, links, hidden, arith, relation, notes; see `struct Move`
     in `solver.hpp`, and the `meta8` helper in `human.cpp`): the pricing reads them;
   - optionally `m.code` (a pattern code, see step 2.4) and `m.xm` (up to 10 extra numbers for the explanation).
3. **The tier.** Register it in `default_notes_tiers()` in `csrc/solver.cpp` with a short strategy name, in the tier
   of techniques of similar difficulty, and add the name to the `strategy_off` table so a band-limited search can skip
   it.

## 2. The registry (`src/pencilmark/data/`)

1. **`solver.py`.** Add the constant with the same number (`YOUR_TECH = 103`).
2. **`techniques.csv`.** One row: id, constant, engine name, role `logic`, chip code, band, family, gate and the
   flags the file's header in `registry.py` explains. Put it after the techniques it should be tried after: inside a
   family, the order of the rows matters.
3. **`codes.csv`.** A new chip code needs a row: a three-letter code (Andrew Stuart's, from
   [sudokuwiki.org](https://www.sudokuwiki.org), where he has the strategy), its name, its study order inside the band,
   and its Sudoku Explainer rating (`-` if SE has none).
4. **`patterns.csv`.** Only if the move sets `m.code`: one row per code, naming the shape.

## 3. Price and descriptors

- **The price.** A new technique has no fitted price. Either give it a starting price in `DEFAULT_PARAMS["B"]` in
  `scoring.py`, with a comment saying where the number comes from, or set `price_fallback` in `techniques.csv` so the
  structural model prices it. Refitting the prices on human solve times is a separate job; say in the pull request
  that the price is not fitted.
- **Extra move fields.** If the move sets `m.xm`, name the fields in `cbackend.XMETA_KEYS`, in the order the engine
  writes them.

## 4. The explanation (`explain.py`)

Write a handler `_h_your_technique(ctx)` that returns `_result(...)` with a short line and a teaching paragraph, and
add it to `_X_HANDLERS` with its catalogue key, family and a one-sentence concept. Read the pattern cells from
`ctx.raw_engine["pattern_cells"]` and the extra fields from `ctx.xm`. `test_every_move_technique_has_an_explanation`
fails until the handler exists. Follow the [writing style](WRITING_STYLE.md): result first, plain words.

## 5. Check and record

```
python -m pytest -q -n auto tests           # the quick suite, about 10 s
python tools/golden.py check                # which cards changed, and how
```

A new technique usually changes some cards: steps found earlier, a different band, a different time. Read the
differences; if they are what the technique should do, rewrite the golden records (`tools/golden.py write`) in their
own commit, add a line under "Unreleased" in `CHANGELOG.md`, and add a puzzle that needs the technique to
`tests/golden/inputs.jsonl` so the corpus covers it.
