---
description: "Example requests in the generator spec language; the Generator examples page shows what each produced."
unlisted: true
---

# Example generator specs

Requests in the [generator spec](../../formats/generator-spec.md) language; each runs with `pencilmark generate FILE`
or `pencilmark.generate(spec)`. [Generator examples](../../guides/generator/generator-examples.mdx) shows the puzzle,
card and run time of each.

| File | What |
|---|---|
| `killer_whispers_2givens.json` | Killer with German whispers and two givens |
| `zero_clue_6x6_kropki.json` | 0-clue 6x6 kropki with a minimal set of dots |
| `hardest_0clue_6x6_kropki.json` | The same, the hardest found in the time (`difficulty: "max"`) |
| `nine_variants_9x9.json` | Nine variants on one 9x9 |

`reserved/` holds requests that use parts reserved for later versions of the spec
([Generator spec](../../formats/generator-spec.md), section 7): a classic with exactly one X-Wing (`where.contains` `only` / `uses`), givens in the shape of a heart (`mask`) and a
displaced jigsaw. The generator refuses them today.
