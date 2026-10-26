# Showcase generator specs (`sudoku-spec`)

Written in the spec language of docs/FORMAT.md section 12. "Runs" means `pencilmark.gen` accepts the spec
(`spec_format.gen_support` / `spec_to_gen`); whether a run finds a puzzle within its time limit is not promised (the
16x16 cage count, for one, needs a long CP-SAT search). The others are refused with the reason shown and document
where the generator is going.

| File | What | Runs |
|---|---|---|
| `super_samurai_variants.json` | Super samurai: a variant per row of grids | no: the generator makes gap-free 9x9 boards (grid {'rows': 21, 'cols': 33}) |
| `one_xwing_classic.json` | Classic with exactly one X-Wing | no: contains 'only' / per-code uses are not supported by the generator yet |
| `killer_whispers_2givens.json` | Killer with German whispers and two givens | yes |
| `picture_mask_heart.json` | Givens in the shape of a heart | no: givens masks / locked values are not supported by the generator yet |
| `hardest_0clue_6x6_kropki.json` | Hardest 0-clue 6x6 kropki | no: difficulty 'max' / 'min' (best-so-far search) is not supported by the generator yet |
| `zero_clue_6x6_kropki_today.json` | 0-clue 6x6 kropki | yes |
| `nine_variants_9x9.json` | Nine variants on one 9x9 | yes |
| `giant_16x16_32cages.json` | 16x16 killer with exactly 32 cages | yes |
| `displaced_jigsaw.json` | Displaced jigsaw | no: the generator cannot place box |
