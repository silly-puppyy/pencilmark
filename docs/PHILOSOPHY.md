# Philosophy

What pencilmark is for, what its numbers mean, and the rules its formats follow. The specifications
([Puzzle format](FORMAT.md), [Grade card](GRADE.md), [Generator spec](SPEC.md)) say *how*; this page says *why*, and is the reference
when a change is in doubt.

## 1. Goals

1. **Grade like a person.** Every number is an estimate of how people experience a puzzle, checked against real solve
   times and ratings from at least two independent sources. A number that tracks people better is better, even if it
   changes old values (section 4).
2. **One file for every program.** The puzzle format is first of all how a solver, a grader and a renderer talk about
   the same puzzle: every rule has one exact meaning, and a renderer can draw it from the rules alone. Anything else a
   program wants to carry (an author, a source, a date) goes in `meta`, which needs no change to the format: adding
   `"author"` to `meta` is enough for attribution to work.
3. **Simple to understand and implement.** A small, strict core; a subset is a valid implementation (classic sudoku is
   the envelope plus two rules). Fields that duplicate others are removed, not deprecated, until someone relies on them.

**Non-goals.** What lies outside the numbers and where we have no interest or data: enjoyment, beauty, theme, how a
puzzle is presented, mistakes and long breaks, solving on paper versus an app. Publishing checks (`issues`) touch on
quality, but the evidence behind them is weak, so they are optional and adjustable, never part of the headline numbers.

## 2. The headline numbers

Each number answers one question. They are meant to disagree sometimes: together they say more than any one of them.

| Number | Question | Kind |
|---|---|---|
| `band` | What do you need to know? | Rule: the hardest technique needed |
| `difficulty` | How hard does it feel? | Estimate of perceived hardness, independent of size |
| `time` | How long will it take? | Estimate of minutes, grows with size and length |

### `band`

**Definition.** The tier of the hardest technique on the easiest human route through the puzzle. The tiers are a
learning path, the steps every curriculum takes (HoDoKu, sudokuwiki.org, sudoku.coach's technique categories):

| Band | What it adds |
|---|---|
| Very Easy | the entry point: scanning without candidates (full house, hidden singles), a rule's obvious consequences |
| Easy | candidates in one cell (naked singles), pointing / claiming, one rule's combinations |
| Medium | subsets: naked and hidden pairs, triples, quads; the implications of each variant rule |
| Hard | the first learned patterns: X-Wing, Skyscraper, 2-String Kite, Turbot Fish, simple colouring |
| Very Hard | Empty Rectangle, finned fish, Swordfish and Jellyfish, wings, uniqueness, longer X-Chains, advanced variant logic |
| Expert | chains and almost locked sets: XY-Chain, AIC, Medusa |
| Extreme | forcing chains and nets, trial and error |

Each technique belongs to one band ([Techniques](TECHNIQUES.md) lists them). The route always prefers an easier technique when one is
available, so the band is the least a solver must know.

- It is a rule, not an estimate: the same route gives the same band, whatever people's solve times say.
- Bands order **knowledge**, not effort. A Hard puzzle needs a learned pattern somewhere; a Medium puzzle never does, but it
  can be long and demanding. So a Hard puzzle is often easier and quicker than a Medium one, and people agree: among
  pairs of puzzles of one type where the two disagree, solvers side with the difficulty number about three times in four
  (sudoku.coach, 384 puzzles; grandgames and Puzzle Duel the same way).
- Where no technique in the catalogue applies, the engine proves the next step by search (Trial and error) and the
  band is Extreme. **Unknown** means the band could not be determined: guessing was allowed and used, or the time
  limit (`max_seconds`) passed first.
- The band depends on the technique catalogue, which can grow; a new technique can lower a puzzle's band.

### `difficulty`

**Definition.** How hard the puzzle feels while solving it. The scale is meant to hover around the scales of the most
popular graders, which run from about 1 to 10 on classics; on classics it follows Andrew Stuart's: a classic sudoku
should get about the number his sudokuwiki.org grader gives it. Past that range it extrapolates: harder puzzles keep
climbing on the same logarithmic curve with no ceiling; below 2 the curve turns gentler so easier puzzles approach 0
without reaching it, and a difficulty is never negative. Equal steps should feel like equal jumps across the whole
range. Continuous.

- **Hardness, not amount.** It measures how hard the steps are, not how many there are: on grandgames, Easy Samurai rate
  4.9 and Easy 9x9 classics 6.3 (medians), while the Samurai take about four times as long. Size and length belong to `time`.
- **One scale for every rule set.** The same difficulty should feel the same on a classic, a killer or a thermo. Rules
  make steps harder to find (clues to read, sums to keep track of), so variants often score above the classic range of
  their band.
- **What a point means.** On classics, one point of difficulty comes with about 25% more solving time (predicted 1.23
  to 1.28 times per point; 1.16 to 1.34 in the human times of three sources). This describes the scale; it does not
  define it.

### `time`

**Definition.** The predicted median solving time in minutes over the people who solve puzzles like this one, solving
without long breaks. A median classic takes about 12 minutes.

- **Population.** Today's players of that kind of puzzle, as they are: the people who try very hard puzzles are mostly
  experienced, and most killer players know killers. The prediction may include these selection effects; it does not
  describe one particular player.
- **Spread.** Times over players are log-normal around the median. `time_dist` gives its parameters, `time_mean` the
  mean and `time_pNN` any percentile. `sigma_players` is the spread over players (0.79 for classics and multi-grid
  layouts, 0.62 with any other rule); `sigma_model` is how far the median itself can be off (0.33 / 0.48).
- **Not personal.** `time` estimates a distribution, not your time. Personal predictions may come later as a separate
  feature.

### Reading them together

| Combination | What it says |
|---|---|
| High band, low difficulty for it | One hard step in an otherwise easy puzzle, or a hard technique in an easy-to-spot form. Often quicker than a long puzzle of a lower band. |
| Low band, high difficulty for it | Only basic techniques, but well hidden or demanding: many candidates to track, clues to read, sums to keep in mind |
| Low difficulty, long time | Easy but big or long (multi-grid layouts, giant boards) |
| High difficulty, short time | Small but sharp |

## 3. Format rules

1. **One meaning per key, one key per meaning, one meaning per absence.** A missing key means exactly one thing,
   stated in the spec.
2. **Strict reading.** A puzzle reader refuses what it does not understand instead of guessing; errors name the key
   or rule. Lenient readers force every other reader to copy their mistakes.
3. **Small core, open edges.** The core (board, givens, rules) is strict and exact. `meta` is free: anything that never
   changes the puzzle's meaning goes there, with no change to the format.
4. **Everything visible is a promise.** Whatever a card or file shows (keys, their absence, defaults, precision) will
   be relied on, so it is specified or not emitted.
5. **Remove rather than deprecate.** A field that duplicates another, or that nobody implements, is removed. Deprecation
   is considered only once someone relies on the field.
6. **Version in every file.** `format` and `format_version` identify a file; `format_version` changes only on a
   breaking change. Cards also carry the grader name and version.
7. **Examples are part of the spec.** Every rule family and card field comes with example files and the expected
   result, so an implementation can be tested, not only read about.

## 4. Change

- **Better estimates win.** A version that tracks people better may change any `difficulty` or `time`. The goals in
  section 1 keep the numbers near a working idea; they do not freeze them.
- **Changes are measured.** A change to the numbers is checked on held-out human data from at least two sources
  before release, and the benchmark is re-run for every release.
- **Cards name their grader.** Compare cards from the same grader version; to compare across versions, grade again.
