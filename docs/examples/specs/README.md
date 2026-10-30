# Example generator specs (`sudoku-spec`)

Requests in the spec language of [SPEC.md](../../SPEC.md); each runs with `pencilmark.generate(spec)`. Whether a run
finds a puzzle within its time limit is not promised (the 16x16 cage count, for one, needs a long
[CP-SAT](https://developers.google.com/optimization/cp/cp_solver) search).

| File | What |
|---|---|
| `killer_whispers_2givens.json` | Killer with German whispers and two givens |
| `zero_clue_6x6_kropki_today.json` | 0-clue 6x6 kropki |
| `nine_variants_9x9.json` | Nine variants on one 9x9 |
| `giant_16x16_32cages.json` | 16x16 killer with exactly 32 cages |

`reserved/` holds requests that use parts reserved for later versions of the spec (SPEC.md section 7): a super samurai
with a variant per grid, a classic with exactly one X-Wing (`where.issues`), givens in the shape of a heart (`mask`),
the hardest 0-clue 6x6 kropki (`difficulty: "max"`) and a displaced jigsaw. Readers refuse them today; they show where
the generator is going.
