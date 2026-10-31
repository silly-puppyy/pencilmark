---
title: How we got here
description: The decisions that shaped pencilmark, with the evidence and the alternatives we measured.
draft: true
---

# How we got here

These are the decisions that made pencilmark what it is, in the order we took them. Each one names the evidence and
the alternatives we measured. [Philosophy](PHILOSOPHY.md) states the aims that came out of them, [How a card is
computed](MODEL.mdx) the formulas, and the [benchmark](BENCHMARK.mdx) the current accuracy on the frozen held-out set.

Numbers here are what we measured at the time, on the data of the time: cross-validated or held out by source, but
before the frozen set existed unless the record says otherwise. Correlations are Spearman rank correlations within
groups of comparable puzzles (a difficulty tab, a variant family, a board size), as in the benchmark. Only aggregate
numbers appear; no puzzles or per-player data from any source.

## 1. Write the candidates down, then price the route (2026-10-10)

**Decision.** Difficulty and time are priced on a route that writes candidates: the engine may not make the moves
people do in their head (pairs, short chains and case splits seen without notes).

**Why.** The engine priced in-the-head moves below the written technique they stand for: a pair seen without notes
cost about 2.7 times less than the written pair. With those moves switched off, the gap to Andrew Stuart's grader on
fed-sudoku.eu closed: 0.878 against his 0.843 on solve time and 0.704 against 0.678 on give-up rate (cross-validated),
and 0.68 against 0.67 on the hard tab, where we had been behind.

**Alternatives tried.** A global "notes mode" switch for the whole solve, dropped on mixed evidence in favour of
per-move notation features.

## 2. Measured solve times are the main target (2026-10-10 to 2026-10-16)

**Decision.** Difficulty and time are fitted to how long real people take, after correcting for each player's skill.
Ratings serve only where a source has no times (logic-masters.de stars, sudoku-variants votes).

**Why.** Solve times are a clean signal. On fed-sudoku.eu, 2.59 million classic solves give a split-half reliability
of 0.97 to 0.99 within every difficulty tab. On grandgames.net, about 905,000 leaderboard times give 0.969 over all
puzzles. The rating signals we had either repeat time or add noise:

- sudoku-variants player votes correlate 0.94 with solve time (141 puzzles): casual voters rate by time.
- fed-sudoku.eu's give-up rate adds nothing beyond time: with solve time held fixed, it correlates −0.09 with our
  difficulty and −0.10 with Andrew Stuart's. We dropped it as a target (2026-10-12).
- Expert stars are the exception. logic-masters.de stars correlate only 0.52 with self-reported minutes (119 puzzles),
  and our difficulty predicts them with time held fixed (+0.59). They stay as a target.

Radek Pelánek noted that sudoku metrics published before his work were checked only against newspaper labels, which
are themselves computer ratings.

**Alternatives tried.** A per-player "skill slope" (how much more hard puzzles cost weak players) did not replicate:
split-half reliability 0.24 on grandgames.net against 0.54 on sudoku.coach, and no relation to difficulty on grandgames.

## 3. Every claim holds on at least two independent sources (2026-10-16)

**Decision.** A target is estimated, and a change is accepted, only if the result holds on at least two independent
sources: it must help at least two and hurt none beyond noise.

**Why.** The largest source is the easiest to overfit: grandgames.net is one site, one population and one puzzle pool.
The first transfer test showed it. Our grandgames time formula, unchanged, held on sudoku.coach classics (R² 0.79,
median real / predicted 1.04) but not on sudoku.coach variants (R² 0.19). The sources cannot be tied together through
shared puzzles either: fed-sudoku.eu (3,739 classics), grandgames.net (2,208) and lisudoku (218) share none, even up to
relabelling, transposing and rotating. So they are linked only through the model.

**Alternatives tried.** Many one-source gains failed this rule later: the balance of digits among the givens (+0.02
to +0.03 on fed-sudoku.eu, opposite sign on sudoku.coach), price corrections fitted per variant type on sudoku.today,
and per-technique familiarity measured on fed-sudoku.eu alone (both in record 12).

## 4. Correct player times for skill and era (2026-10-16, settled 2026-10-21)

**Decision.** A puzzle's target is its effect after removing each player's speed and the drift of the player
population over the years.

**Why.** Skill is one multiplier per player. On grandgames.net, time per difficulty point is the same in every skill
quartile (×1.28, 1.27, 1.28, 1.26). Later, the 3,886 sudoku.coach players with at least 40 solves gave a median slope of
1.01 of log time on puzzle effect (2026-10-30). Era matters because players get faster: on fed-sudoku.eu the plain
per-puzzle median trends with the puzzle's date at −0.65, −0.59 and −0.42 (easy, medium, hard tabs), the era-corrected
target at −0.03, −0.05 and +0.14. On grandgames.net, effects estimated within one half-year (so no drift and no era
model) agree 0.875 with the era-corrected target and only 0.806 with the uncorrected one.

**Alternatives tried.** The uncorrected target ("clean" median minus skill) disagrees with the era-corrected one almost
entirely by year (rank gap against year +0.83 to +0.85 on every fed-sudoku.eu tab). An item-response model fitted to
the 2.59 million fed-sudoku.eu solves gave no cleaner target (2026-10-21).

## 5. No board-type labels and no per-technique constants in the prices (2026-10-16 to 2026-10-18)

**Decision.** A step's price comes only from what the engine measures about the move: cells, houses, digits, links,
notes, spread, search depth and so on. The model is never told the board type, and no technique gets its own fitted
constant.

**Why.** A constant fitted for kropki says nothing about a variant nobody fitted. Dropping the 24 per-technique
adjustments cost nothing held out (grandgames.net 0.905 unchanged, sudoku.coach classics 0.903 to 0.904). Pricing
every move from measured features lifted sudoku.coach variants by +0.044 (95% interval +0.022 to +0.066), at a real
but small cost on classics (−0.010 on grandgames.net single grids, −0.015 on fed-sudoku.eu). It also put killers on
Andrew Stuart's scale like classics: offset +0.12 against his killer ratings, against +0.64 before (66 rated killers).

**Alternatives tried.** Per-technique and per-family coefficients (the earlier production); a mixture of experts per
board type, which won only through per-type levels. Leaving all cage puzzles out of the fit showed what the features
missed: unseen grandgames.net killers fell from 0.585 to 0.438, so we added the number of digit combinations a cage
allows as a feature.

## 6. Difficulty measures hardness, time measures amount (2026-10-17 to 2026-10-18)

**Decision.** Difficulty is the average effort per empty cell, so it does not grow with size or length. Time carries
size and length.

**Why.** A samurai can be very easy and still take about five times as long as a classic; one number cannot say both.
The per-cell average also ranked people better than the statistic it replaced (the mean of the hardest quarter of
steps): grandgames.net 0.760 to 0.777, sudoku.coach 0.709 to 0.734, logic-masters.de stars 0.555 to 0.603. Its
correlation with board size across types is +0.12; total effort would have +0.51.

**Alternatives tried.** Difficulty as the log of the total step effort (it would make big puzzles hard by length).
Time from difficulty plus size, replaced by time from total effort plus size (sudoku.coach transfer R² 0.707 to 0.741,
2026-10-16). A separate "hard part" card field, folded into time because it added nothing there (2026-10-20).

## 7. Fit the card itself to human rankings (2026-10-19)

**Decision.** The 21 price weights that reach the card are fitted directly so that difficulty ranks puzzles like the
human targets, with each fed-sudoku.eu tab as its own ranking group.

**Why.** Our earlier joint fit of many heads (solve time, ratings, give-ups, next-move choice in solve recordings)
improved its heads and made the card worse: fits selected on held-out heads reached 0.69 on logic-masters.de stars but
dropped fed-sudoku.eu from 0.86 to 0.81 on the card. The direct fit, tested with every puzzle re-solved under weights
that never saw it, improved sudoku.coach by +0.030, fed-sudoku.eu within tabs by +0.042 and logic-masters.de by +0.021,
with grandgames.net and sudoku-variants within noise.

**Alternatives tried.** Free-sign curves per feature (helped hard classics, cost logic-masters.de stars 0.644 to
0.499, 2026-10-18); a worst-group loss (shifted gains to logic-masters.de, cost grandgames.net 0.016 to 0.026).

## 8. Add a search term that knows no techniques (2026-10-20)

**Decision.** Difficulty includes one term that knows nothing about techniques: at every point where simple logic is
stuck, how many candidates fail quickly when tried. One shared weight, the same for every rule set.

**Why.** It carries information the technique route lacks, on two hard sources. On the fed-sudoku.eu hard tab the
term alone matched the card (0.600 against 0.597) and the two together reached 0.663, against Andrew Stuart's 0.669.
On logic-masters.de variants: card 0.621, term alone 0.623, together 0.662. With its weight chosen on the other
sources, it gained on each held-out one: fed-sudoku.eu +0.0125, logic-masters.de +0.033, grandgames.net +0.013,
sudoku.coach +0.019, sudoku-variants 0. 18 of 25 groups went up and none down.

**Alternatives tried.** Four search terms in place of one (overfitted); a second technique-free term (no gain under
leave-one-source-out); bottleneck and dependency features of the search (no general gain).

## 9. Judge changes held out, and freeze a benchmark (2026-10-20 and 2026-10-25)

**Decision.** Nothing is adopted from cross-validation on fixed routes alone. The test that counts re-solves every
puzzle under the changed model and measures it on a source the change was not fitted on; one clean negative result
drops an idea (2026-10-20). Since 2026-10-25, 15% of every source, chosen by a salted hash of the puzzle, is frozen and
used only to measure releases. A/B tests run on a separate development set of up to 1,200 puzzles per source.

**Why.** Prices change the route, and the route changes the score. Making finned fish and triples dearer raised the
fed-sudoku.eu hard tab from 0.610 to 0.657 on fixed routes, but only to 0.620 once re-solved: the engine took other
moves instead. A curriculum-ordered route plus a refit looked good on fixed routes and lost 0.040 on grandgames.net
when re-solved. A finding-cost term looked like a clean pass until we saw its gains came from standardising within
each group, which needs the board type at grading time; the deployable form helped fed-sudoku.eu (+0.024) and cost
sudoku.coach and grandgames.net slightly (2026-10-22). The frozen set came last: by then most decisions had been tuned
on all the data we had, so the published numbers are clean only from that date on.

**Alternatives tried.** Adoption on in-sample or fixed-route gains, and cross-validated numbers on the full data, as
we used before these rules. The frozen set's size and results are in the [benchmark](BENCHMARK.mdx).

## 10. One difficulty scale, on Andrew Stuart's numbers for classics (2026-10-10 to 2026-10-30)

**Decision.** Difficulty is one scale for every rule set. On classics it follows Andrew Stuart's sudokuwiki.org
ratings; it is one continuous curve with a floor at 0 and no ceiling.

**Why.** The aim is a scale near the popular graders' ([Philosophy](PHILOSOPHY.md)), and ours already tracks his. On
3,739 fed-sudoku.eu classics the mean absolute difference is 0.51 with a bias of +0.01, and medians agree within ±0.2
across his range 3 to 8 (2026-10-22). On 747 frozen classics the median difference is −0.1, the rank correlation 0.91
(2026-10-30). The earlier quadratic map went below zero for easy puzzles and fell at the top (11.5, 12.1, then 11.6 as
effort kept rising), so we replaced it with one smooth formula (2026-10-22). Below 2 the curve turns gentler so easy
puzzles stay apart: in a check sample, 174 of 200 cards below 2 rose, none fell, and cards reading exactly 0.0 went
from 108 to 3 (2026-10-30).

**Alternatives tried.** Fitting the curve to Andrew Stuart's 2 to 6 range only (bias −0.99 above 6). Sudoku
Explainer's scale, which puts 98% of the same classics between 1.2 and 3.3, with 3 distinct values in the easiest 40%
against our 20. Rounding difficulty to 0.5, which lost 0.005 to 0.017 in rank correlation (2026-10-25).

## 11. Time in minutes, with a log-normal spread (2026-10-15 to 2026-10-29)

**Decision.** Time is the predicted median minutes of the people who solve puzzles like this one. It grows with total
effort, the number of empty cells and the scanning cost of irregular regions. Times over players are log-normal around
that median.

**Why.** On sudoku.coach, log time is linear in log effort, with no floor and no bend (2026-10-30). Irregular and extra
regions cost scanning time on four sources: adding that term raised held-out R² on each (sudoku.coach 0.752 to 0.762,
grandgames.net 0.852 to 0.879, lisudoku 0.802 to 0.814, Puzzle Duel 0.805 to 0.847; 2026-10-20). The log-normal shape
fits: on 834 sudoku.coach puzzles with at least 40 timed solves, the quantiles of log time sit within 0.15 of a normal
distribution. The spread over players is about 0.79 on classics and multi-grid layouts and 0.62 with any other rule,
and two sources agree on the difference (2026-10-29). As of 2026-10-22, time was off by a median 20% on grandgames.net
(fitted) and 26% on 13,211 sudoku.coach puzzles it was never fitted on.

**Alternatives tried.** A fixed 80th percentile at 1.53 times the median: that ratio is within one person, while the
population ratio is 2.23 on fed-sudoku.eu and 1.81 on sudoku.coach. A spread that depends on puzzle length (the two
sources disagree in sign). A learned per-move time model (adds nothing to total effort: sudoku.coach R² 0.722 with it,
0.723 without). Size, overhead and drawn-constraint terms (sources disagree), and a bottleneck term for Hard puzzles
(gain at most 0.005, 2026-10-30).

## 12. Ideas we measured and dropped

A gain of about 0.02 on one or two sources does not justify a second regime in the difficulty number or a structural
change (2026-10-21). The table lists ideas that failed that bar or the two-source rule. By 2026-10-25, recombining every
feature the engine extracts bought between 0.00 and 0.04 within type: the card is near the limit of what those features
carry.

| Idea | Date | What we measured |
|---|---|---|
| Flexible (non-linear) step prices | 2026-10-21 | Better within a source (fed-sudoku.eu +0.05, sudoku.coach +0.03), worse on an unseen one (fed-sudoku.eu −0.05 to −0.11, sudoku.coach −0.10) |
| Ten times more sudoku.coach data in the fit | 2026-10-21 | sudoku.coach, fed-sudoku.eu, logic-masters.de up about 0.01; grandgames.net down about 0.01 |
| A learned model of human moves as a difficulty term | 2026-10-20 | Worse alone than the card in all 23 groups; no held-out gain when added |
| Per-technique familiarity measured on fed-sudoku.eu | 2026-10-20 | fed-sudoku.eu +0.032; unseen sources −0.001 to −0.006 |
| Hard-end blend toward the curriculum route above difficulty 5 | 2026-10-21 | fed-sudoku.eu +0.024, grandgames.net +0.006, others +0.005 or less; passed the two-source rule, declined as not worth a discontinuity |
| Hardest band before the first placement | 2026-10-25 | logic-masters.de 0.637 to 0.647; grandgames.net, sudoku.coach, sudoku-variants within 0.001 |
| Price corrections per variant type, fitted on sudoku.today | 2026-10-25 | sudoku.today 0.593 to 0.614; grandgames.net 0.790 to 0.776, sudoku.coach 0.811 to 0.803, logic-masters.de 0.650 to 0.636 |
| Difficulty route capped at the puzzle's band | 2026-10-30 | Lower on six of seven development sources (fed-sudoku.eu 0.633 to 0.622, grandgames.net 0.788 to 0.776) |
| A hardest-step term on top of the per-cell average | 2026-10-30 | Rank correlation down by up to 0.08 everywhere |

## 13. Seven bands of knowledge, separate from difficulty (2026-10-30)

**Decision.** The band is the curriculum step a puzzle needs, in seven bands from Very Easy (scanning) to Extreme
(forcing and trial), with Hard as the first learned patterns. It orders knowledge, not effort, and difficulty is not
anchored to it.

**Why.** The seven bands are the steps of sudoku.coach's technique categories and line up with HoDoKu's levels and
Andrew Stuart's grades; on 747 frozen classics our Very Easy is HoDoKu's Easy in 100% of cases. Regrouping the bands
left every difficulty and time unchanged on the frozen set. People confirm that bands and difficulty measure different
things: in pairs of Medium and Hard puzzles of one type where the two disagree, sudoku.coach solvers sided with the
band only 24% of the time (384 puzzles). Andrew Stuart's own ratings put Hard below Medium on the same classics
(medians 5.3 and 7.0).

**Alternatives tried.** Six bands, with our "Easy" one step harsher than every other curriculum (Andrew Stuart grades
78% of those puzzles Moderate). Renaming the six bands to match the field. Anchoring difficulty to bands, which would
leave Andrew Stuart's scale where we already agree with him. Capping the difficulty route at the band (record 12).

## 14. Solver logic in C++, Python as the interface (2026-10-26)

**Decision.** Everything that searches the grid is in the C++ engine. Python reads puzzles, names, prices and explains
moves, and assembles the card.

**Why.** Profiling showed the time going to Python loops around a fast engine: on Medium windoku and extra-region
puzzles a card took 90 to 150 s, of which the solve was 0.1 s and the technique-list reruns 87 to 147 s. Once the
engine cached its move listings, 99% of a band route's time was the C++ listing itself.

**Alternatives tried.** Porting the band route to C++, dropped after that profile: there was nothing left to gain.
Caches in the engine did the work instead (16×16 technique list 196 to 62 s; a corpus of cards with steps 1,506 to
445 s).

## 15. Formats: small, strict, one meaning per key (2026-10-26 to 2026-10-30)

**Decision.** The puzzle and card formats follow the rules in [Philosophy](PHILOSOPHY.md) section 3: one meaning per
key and per absence, strict reading, a small core with a free `meta`, and removal over deprecation.

**Why.** Formats that lasted did the same. GeoJSON's standard removed rarely implemented features; RFC 9413 argues
that tolerant readers force every other reader to copy their quirks; Hyrum's law says every visible behaviour will be
relied on. An audit of our own formats against these lessons found 15 problems, among them three overlapping
completeness flags and an absence with two meanings. We fixed them before 1.0: legacy reading removed, houses only
from explicit keys, duplicate card fields (`contains_complete`, `time_dist.median`, `se_diuf`) removed.

**Alternatives tried.** Accepting older format names alongside the new ones (2026-10-25), dropped a day later:
deprecation waits until someone relies on a field.
