---
title: Experiment log
description: Every substantial experiment behind pencilmark, what we measured and whether it worked, including the ideas we dropped.
draft: true
---

# Experiment log

This page lists the experiments that shaped pencilmark, grouped by theme and in date order within each theme, with
the failures given as much room as the successes. Unless an entry says otherwise, a result is a Spearman rank
correlation with a human target (solve times corrected for player skill, setters' star ratings, player votes),
computed within groups of comparable puzzles and, where the entry says so, held out by source. Most experiments ran
before the frozen benchmark of 2026-10-25, so their numbers are as measured at the time, on the data and engine of the
time; the [benchmark](BENCHMARK.mdx) has the current accuracy. A change was adopted only if it helped at least two
independent sources and hurt none beyond noise, and from 2026-10-21 a gain of about 0.02 or less did not justify a
structural change.

Two terms recur. **Re-solved** means every puzzle was solved again under the changed model before scoring, because
prices change the route and the route changes the score. **Left out** means a weight was chosen on the other sources
and the gain measured on the source left out. Only aggregate numbers appear here. [How a card is computed](MODEL.mdx)
describes the model that came out of these experiments, and [Philosophy](PHILOSOPHY.md) the aims.

## Targets and data

What a puzzle's human target should be, and when more data stopped helping.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-10 to 10-15 | Split-half reliability of skill-corrected puzzle times | fed-sudoku.eu (2.59 million solves), grandgames.net (905,000 times) | 0.97 to 0.99 within every fed-sudoku.eu tab; 0.969 over all grandgames.net puzzles; time per difficulty point the same in every skill quartile (×1.28, 1.27, 1.28, 1.26) | Kept: times are a clean target; one speed multiplier per player |
| 2026-10-15 to 10-18 | More raw data: further grandgames.net pages, larger search budgets for reading SudokuPad links | grandgames.net, logic-masters.de | grandgames.net R² 0.643 with 10 puzzles per type, 0.670 with 60, and new players per tenth of the collection fell from 2,555 to about 70. SudokuPad: 1,038 readings recovered, but only 79 were puzzles not already readable through another link | Stopped collecting at 22,480 of 61,810 pages; recovered readings serve only as confirmations |
| 2026-10-16 | Give-up rates, expert stars, player votes and a per-player skill slope as targets | fed-sudoku.eu, logic-masters.de, sudoku-variants, grandgames.net, sudoku.coach | Give-up against difficulty with time held fixed: −0.09 for us, −0.10 for Andrew Stuart. Stars against self-reported minutes 0.52 (119 puzzles); our difficulty predicts stars with time held fixed (+0.59). Votes against time 0.94 (141). Skill slope split-half reliability 0.24 and 0.54 | Give-up and skill slope dropped; stars kept; votes treated as time |
| 2026-10-16 | Linking sources through shared puzzles | fed-sudoku.eu (3,739), grandgames.net (2,208), lisudoku (218) | No shared classic, even after relabelling, transposing and rotating | Sources linked only through the model; two-source rule adopted |
| 2026-10-16 to 10-21 | Correcting targets for the drift of the player population (era); other target constructions | grandgames.net, fed-sudoku.eu, sudoku.coach | Effects from a single half-year agree 0.875 with the era-corrected target, 0.806 with the uncorrected one. On fed-sudoku.eu the plain median trends with puzzle date −0.65, −0.59, −0.42 (easy, medium, hard tabs), the era-corrected target −0.03, −0.05, +0.14. sudoku.coach (no dates): two-way effect against median 0.985 to 0.990. An item-response model on fed-sudoku.eu gave lower agreement for every grader (our card 0.614, 0.491, 0.532 against 0.758, 0.580, 0.610) | Kept: era-corrected targets where dates exist |
| 2026-10-24 to 10-26 | Inspecting the weakest sudoku.today types before blaming the model | sudoku.today | Greater-than rose from 0.17 to 0.64 once its signs were read from the images; two hybrid types had their rules swapped; failing differences and quotients puzzles were all non-unique translations | Kept: a uniqueness gate on every translation |

## Route: which moves the engine takes

The route decides which moves get priced, so several gains and losses came from the route rather than the prices.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-10 | Switching off moves people make in their head (a pair seen without notes cost about 2.7 times less than the written pair); a global notes mode | fed-sudoku.eu | Written route: solve time 0.878 against Andrew Stuart's 0.843, give-up 0.704 against 0.678, hard tab 0.68 against 0.67 (cross-validated). Notes mode without refitting: time 0.840 to 0.873, but a confounded drop in move prediction | Written route kept; notes mode dropped for per-move notation features |
| 2026-10-17 | Human techniques that replace forcing chains (case analysis and related moves) | logic-masters.de, fed-sudoku.eu, grandgames.net, sudoku.coach | Puzzles needing trial-family steps 9.9% to 3.8%, trial steps 4,366 to 438; stars 0.578 to 0.572; card scores elsewhere unchanged | Kept: more human routes at no accuracy cost |
| 2026-10-18 | A route that prefers moves near the previous one (from measured travel cost); a one-step lookahead route | grandgames.net, sudoku.coach; 38 puzzles | Locality: multi-grid 0.687 to 0.692, sudoku.coach 0.697 to 0.703. Lookahead: card score median −0.05, 2.7 times slower | Locality kept; lookahead dropped |
| 2026-10-19 to 10-30 | Steering the difficulty route toward the techniques people use: blocking exotic techniques, a band-by-band route, a cap at the puzzle's band | five sources, then the development set | Blocking: hard tab 0.610 to 0.624, grandgames.net −0.0001, sudoku.coach −0.006. Band route: hard tab 0.610 to 0.666, but sudoku.coach 9×9 variants −0.014 (interval −0.023 to −0.004); refitted on band routes and re-solved, grandgames.net −0.040. Cap: lower on six of seven sources (fed-sudoku.eu 0.633 to 0.622) | Dropped: the greedy route stays; the band route serves the band and hints |
| 2026-10-11 to 10-23 | Does the engine offer the move people actually made? | expert video solves, sudoku.today replays | Expert placements offered 98.8% after pauses under 5 s, 47.5% after pauses of 300 s or more; with the players' own marks, coverage 86.9% to 89.7%, so about 10% are multi-step reasoning. sudoku.today: 89.9% to 96.9% within the puzzle's band, 99.6% to 100% with any technique | Informative: the technique list says what a puzzle needs, not every move a player uses |
| 2026-10-20 to 10-25 | Predicting the next move: a learned technique-free cell model, and our own ranking | six trace sources (76,062 states), sudoku.today replays (15,315 placements) | Learned model top-1 42.9% against the engine's 38.2% on the same states; distance to the last move is the one big cue (−4.8 points without it); as a difficulty term worse in all 23 groups. Our ranking: top-1 37.7%, top-3 65.8% (random 7.4%); no reading-order bias (0.491, interval 0.476 to 0.506) | Dropped for the card: move choice barely affects difficulty |
| 2026-10-25 | Card invariance under relabelling, transposing, rotating | Wang 2024 (100), sudoku.today variants (259) | Classics: band 100% the same, 94% to 95% identical cards; variants transposed: 55% identical. Canonical cell numbering raised the worst type from 20% to 25-30% identical | Accepted: band stable in 99% to 100%, median shift 0.15 |

## Step prices

How each move is priced, and the many fitting ideas that did not transfer.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-10 to 10-17 | Removing per-technique numbers, first attempts: dropping the family price ladder, prices from 19 measured features, dropping 24 per-technique card adjustments | five sources | No ladder: stars 0.672 to 0.580. 19 shared weights tied the per-technique card (logic-masters.de 0.648 against 0.642, fed-sudoku.eu 0.859 against 0.868). Adjustments dropped at no held-out cost (grandgames.net 0.905 unchanged). Per-technique terms bought only 0.007 to 0.034 on classics and lost on variants | Adjustments dropped; the rest led to the version below |
| 2026-10-16 | Andrew Stuart's hand-set step values against values fitted to people | fed-sudoku.eu (his own solve paths) | His values 0.843, fitted 0.852; every step equal 0.799; random ×0.5 to ×2 noise on his values 0.836 | Informative: the optimum is flat |
| 2026-10-17 | Rarity of a move as a price factor | four sources | Puzzles with rare moves are harder than scored (+0.10 to +0.26); as a step weight sudoku.coach +0.002, logic-masters.de +0.006, carried to another source −0.004 to −0.011; as a fitted feature stars 0.626 to 0.584 | Dropped |
| 2026-10-17 to 10-18 | Counting what a constraint allows: digit combinations of a cage or sum, digit pairs of a border rule | grandgames.net, sudoku.coach, logic-masters.de | With no cage puzzle in training, unseen killers fell 0.585 to 0.438 (controls −0.01 to −0.03). Combinations as a step factor: sudoku.coach cages 0.678 to 0.718, killer time calibration 1.14 to 1.00; inside the joint refit the weight went negative. Pairs: a real residual (+0.18, +0.114), but as a factor logic-masters.de 0.632 to 0.573 | Combinations kept as a card factor; pairs dropped |
| 2026-10-18 | Forbidding "a rule makes a move cheaper"; a direct per-move timing term; open singles in that term | five sources, bootstrap intervals | Rule constraint: sudoku.coach variants +0.029, grandgames.net single grids +0.026, small grids −0.047. Timing term: per-move fit 0.414 to 0.590; at weight 1 already multi-grid +0.034, sudoku.coach classics +0.024. Doubling the open singles makes a gap ×0.87 at equal price on all five trace sources | Kept all three |
| 2026-10-18 | Measured-feature pricing in production, replacing per-technique prices | five sources, 66 killers rated by Andrew Stuart | Variants +0.044 (interval +0.022 to +0.066); grandgames.net single grids −0.010, fed-sudoku.eu −0.015. Killers sit on Andrew Stuart's scale like classics: offset +0.12, against +0.64 before | Kept |
| 2026-10-18 | Free-sign curves per feature; weighting rare puzzles up | five sources | Curves: hard tab 0.223 to 0.356 but stars 0.644 to 0.499. Balanced loss: stars 0.656 to 0.641, votes 0.833 to 0.816 | Dropped: flexibility went to the majority sources |
| 2026-10-18 to 10-19 | Refit behaviour: seeds, convergence, held-out stopping, a card-shaped head, a distance term | five sources, six seeds | Three of six seeds collapsed (card about 0.77 against 0.85 to 0.90); starting from production weights fixed it (0.772 to 0.852). Converged fits improved their heads (stars 0.689 against 0.656) while the card got worse (fed-sudoku.eu 0.811 against 0.860). Distance term: multi-grid −0.018, sudoku.coach classics −0.020 | Warm start and three seeds kept; the rest dropped |
| 2026-10-19 to 10-20 | Fitting the 21 card weights directly to human rankings; later refits with a search-space feature or a worst-group loss | five sources, re-solved and held out | Direct fit with each fed-sudoku.eu tab as a group: sudoku.coach +0.030, fed-sudoku.eu within tabs +0.042, logic-masters.de +0.021, the others within noise; the same prices broke time transfer (sudoku.coach R² 0.763 to 0.684). Search-space refit: grandgames.net −0.020, sudoku-variants −0.028. Worst-group loss: grandgames.net −0.016 to −0.026 | Direct fit kept for difficulty only; later refits dropped |
| 2026-10-19 to 10-25 | Per-technique price offsets: obscurity in four forms, variant corrections fitted on sudoku.today | five sources | Obscurity fitted jointly: fed-sudoku.eu +0.082, grandgames.net −0.014 (diagnostic only); estimated on fed-sudoku.eu and frozen: +0.032 there, −0.001 to −0.006 elsewhere; on three techniques from two sources: hard tab 0.610 to 0.657 on fixed routes, 0.620 re-solved. Variant corrections: sudoku.today 0.593 to 0.614, grandgames.net 0.790 to 0.776, logic-masters.de 0.650 to 0.636 | Dropped: community-specific; a dearer move makes the engine route around it |
| 2026-10-16 to 10-28 | More sources and data in the fit: sudoku.coach and grandgames.net in the joint refit, ten times more sudoku.coach puzzles, targets from experienced players | fed-sudoku.eu, grandgames.net, sudoku.coach, logic-masters.de; Puzzle Duel as a check | Joint refit: fed-sudoku.eu 0.874 to 0.846. Ten times the data: sudoku.coach, fed-sudoku.eu, logic-masters.de up about 0.01, grandgames.net down about 0.01. Experienced targets: +0.11 in the fit's own sources, but on independent data fed-sudoku.eu 0.631 to 0.637 and Puzzle Duel 0.666 to 0.678 | Dropped: the linear card is data-saturated |
| 2026-10-16 to 10-29 | More flexibility or capacity: per-type experts, a per-step network, a 74-feature puzzle model, boosting, a sequence network | up to 23 families, five sources | Per-type experts rank 0.649 against 0.662 shared. Per-step network within a source better (fed-sudoku.eu 0.655 to 0.712), on an unseen source worse than production (fed-sudoku.eu 0.649 against 0.503 to 0.563); a per-source notes offset recovered only about 0.005 of that gain. Puzzle model left out by family: card 0.733, boosting 0.685. Recombining all extracted features: +0.00 to +0.04. Sequence network on an unseen source: sudoku.coach 0.486 to 0.500 against 0.756 | Dropped: the extra structure is source-specific |
| 2026-10-29 | Technique tables (one fitted value per technique) as baselines | frozen benchmark, fitted on development data | The card beats every table by +0.08 to +0.19, and by +0.09 to +0.27 on sources the tables never saw | Kept: confirms per-step pricing from measured features |

## Difficulty: the summary statistic and extra terms

How step prices become one difficulty number, and the terms we tried adding to it.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-11 | Andrew Stuart's form on our routes (step value × candidate density ÷ moves offered); a per-move waiting-time (race) model instead | fed-sudoku.eu, trace data | His form: time 0.878, give-up 0.706 (Andrew Stuart's own grades 0.843, 0.678). Race model: time 0.704, nothing added on top | Form kept as the base of the card; race model dropped |
| 2026-10-12 to 10-30 | Hardest step instead of, or on top of, total effort | fed-sudoku.eu, logic-masters.de, four sources | With total effort held fixed the hardest step adds +0.04 to give-ups and −0.09 to stars, while total effort adds +0.26 and +0.41. Later: per-cell effort beats the hardest step for time (grandgames.net 0.790 against 0.632), ties it on stars (0.666 against 0.660); a hardest-step term lowers ranking by up to 0.08 | Dropped |
| 2026-10-16 to 10-18 | Tail statistics (maximum, top ten, CVaR), then average effort per empty cell | four sources, bootstrap intervals | Mean of the top quarter beat the tails and was least tied to length. Per-cell average beat it: grandgames.net 0.760 to 0.777, sudoku.coach 0.709 to 0.734, stars 0.555 to 0.603; correlation with board size +0.12 (total effort +0.51) | Per-cell average kept |
| 2026-10-19 to 10-25 | Extra puzzle-level terms: stuck moments, options per step, spikes, a second search term, hardest band before the first placement | five sources | Stuck and options: sudoku.coach +0.006 to +0.024, logic-masters.de +0.022, but fed-sudoku.eu −0.006, sudoku-variants −0.022. Spikes and a second search term: best weight 0 on left-out sources. Break-in band: logic-masters.de 0.637 to 0.647, others within 0.001 | Dropped |
| 2026-10-20 | A technique-free search term: how many candidates fail fast when tried at each stuck point | five sources | Hard tab: card 0.597, term alone 0.600, both 0.663 (Andrew Stuart 0.669). logic-masters.de variants: 0.621, 0.623, 0.662. One shared weight, left out: fed-sudoku.eu +0.0125, logic-masters.de +0.033, grandgames.net +0.013, sudoku.coach +0.019, sudoku-variants 0; 18 of 25 groups up, none down | Kept |
| 2026-10-20 to 10-21 | Layout features: balance of digits among the givens, scarcity of singles early on | five sources | Digit balance +0.019 to +0.032 on fed-sudoku.eu, opposite sign on sudoku.coach and sudoku-variants (+0.17). Early scarcity real on three sources, opposite on sudoku.coach; left-out gain about 0 for both | Dropped: artefacts of one generator or community |
| 2026-10-21 | A knowledge ladder: search effort beyond a set of known techniques | five sources, 10,505 puzzles | Classics gain (hard tab +0.287 partial, sudoku.coach classics +0.131), small sudoku.coach grids −0.391; left out sudoku.coach −0.013. It did reproduce a known 2014 step in fed-sudoku.eu's hard puzzles | Dropped as a card term |
| 2026-10-21 | Community signals blended into the one number: a learner profile, a blend toward the curriculum route above 5 | fed-sudoku.eu (split by date), five sources left out | Learner profile: hard tab 0.589 to 0.729 on later puzzles (Andrew Stuart 0.698), but blended in: sudoku.coach −0.0055, grandgames.net −0.0117. Curriculum blend: fed-sudoku.eu +0.024, grandgames.net +0.006, logic-masters.de +0.005, others +0.0015 or less | Dropped; the blend passed the two-source rule but was not worth a discontinuity |
| 2026-10-21 to 10-22 | Cost of finding the one needed move | five sources, 2,953 untouched sudoku.coach puzzles | Passed left-out tests (fed-sudoku.eu +0.033, logic-masters.de +0.008) and an untouched check (sudoku.coach variants +0.016), but those used group-standardised scores. The deployable form: fed-sudoku.eu +0.024, sudoku.coach −0.004, grandgames.net −0.005 | Dropped |

## The difficulty scale

Where the numbers sit, independent of the ranking.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-11 to 10-22 | Calibrating the ends: the top on Andrew Stuart's ratings of very hard classics, then one continuous curve with a floor at 0 and no ceiling, and a fit to his 2 to 6 range only | 123 hard random classics, fed-sudoku.eu (3,739), logic-masters.de | The top was ranked 0.78 with him but about 1.7 points too low until the map was refitted. The quadratic map went below zero and fell at the top (11.5, 12.1, 11.6 as effort rose); the continuous curve separates 4-star and 5-star puzzles (medians 13.6 and 14.2). Fitting 2 to 6 only: bias −0.99 above 6, against a mean absolute difference of 0.51 and bias +0.01 for the installed curve | Continuous curve kept; the 2-to-6 fit dropped |
| 2026-10-20 to 10-30 | Agreement with other graders' scales | 6,000 random minimal classics (Berthier), 747 frozen classics | Sudoku Explainer 0.923, W-rating 0.927 (they agree 0.933 with each other). Distinct values in the easiest 40%: ours 20, Sudoku Explainer 3, Rangsk 2, Andrew Stuart 16, HoDoKu 75 | Informative |
| 2026-10-25 | Publishing difficulty in steps of 0.5 | fed-sudoku.eu, Wang 2024 | Rank correlation lower by 0.005 to 0.017 | Dropped |
| 2026-10-27 | Anchoring difficulty to bands | fed-sudoku.eu, sudoku.today, logic-masters.de | Variants fall inside band ranges, but the hard tab median drops from 6.4 to 3.5 and the medium tab from 5.1 to 3.1 | Dropped: difficulty stays independent of bands |
| 2026-10-30 | The shape of time against effort, and a gentler curve below 2 | sudoku.coach (2,961 puzzles, 3,886 players), 200 cards below 2 | Log time is linear in log effort (a floor and a bend add nothing); skill slope 1.01. Below 2: 174 of 200 cards rose, none fell, cards reading 0.0 from 108 to 3 | Kept |

## Time

How minutes are predicted, and the many terms that did not hold on a second source.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-11 to 10-15 | First time models: scanning one grid's share of a large board, then difficulty plus the number of empty cells | generated samurai, grandgames.net (2,972) | A singles-only samurai went from 84.6 minutes (18 classics) to 23.8 (5.2 classics). The new formula: cross-validated R² 0.80 against 0.58 for the old work-volume time; boosting reached 0.872 against 0.821 for a linear model with route counts, gaining only across types | Linear form kept, later refined |
| 2026-10-16 to 10-17 | Transfer to another site; total effort in place of difficulty; a fixed start-up time | grandgames.net, sudoku.coach | Unchanged formula on sudoku.coach: classics R² 0.79 (median real ÷ predicted 1.04), variants 0.19, small grids 1.5 to 1.8 times slower. Total effort: transfer R² 0.707 to 0.741. Start-up time: 0.741 to 0.770, 4×4 ratio 1.78 to 1.44 | Kept both changes |
| 2026-10-20 | Scanning cost of irregular and extra regions | sudoku.coach, grandgames.net, lisudoku, Puzzle Duel | Held-out R² 0.752 to 0.762, 0.852 to 0.879, 0.802 to 0.814, 0.805 to 0.847; on the full sudoku.coach set 0.749 to 0.760. As a difficulty term it hurt ratings (stars 0.671 to 0.658, votes 0.734 to 0.675) | Kept in time only |
| 2026-10-16 to 10-22 | Further time terms: travel, notes steps, drawn constraints, size, overhead, effort slope, hardest part, learned per-move time, finding cost, number of rule kinds | four time sources | Travel: sudoku.coach 0.733 to 0.726. Notes: sudoku.coach transfer 0.763 to 0.737-0.745. Drawn constraints: sudoku.coach 0.762 to 0.662. Size and overhead weights flip sign between sources. Hardest part: grandgames.net 0.891 to 0.869. Learned time and finding cost: nothing beyond effort. Rule kinds: +0.52 on easy sudoku.coach puzzles, not reproduced on lisudoku or Puzzle Duel | Dropped: sources disagree |
| 2026-10-23 to 10-24 | Slower growth at the top: linear in difficulty above 9, then a monotone compression of long predicted times | grandgames.net (fitted), sudoku.coach, sudoku.today | Above 9: held out sudoku.today R² 0.231 to 0.355, but on 8,439 sudoku.today puzzles within-type time ranking fell 0.57 to 0.42. Compression: sudoku.coach mean log error 0.310 to 0.289, sudoku.today 0.325 to 0.302, ranking unchanged by construction | First form reverted; compression kept |
| 2026-10-23 to 10-30 | Later time terms: an extra size slope, rule-reading cost, additive time, a search term for Hard puzzles | grandgames.net, sudoku.coach, sudoku.today, development set | Size slope: grandgames.net wants +0.06, sudoku.coach −0.30. Reading cost: within-type error 0.286 to 0.291. Additive: R² 0.816 and 0.568 against 0.851 and 0.724 (the current form over-predicts a hard grid glued to an easy one by 1.27 times). Hard search term: ranking +0.005 at most, negative weight for Expert | Dropped; the glued-board flaw is a known limitation |
| 2026-10-26 | Extra growth for boards with more than about 92 empty cells | grandgames.net, samuraisudoku.com (held out) | grandgames.net R² 0.854 to 0.874; samuraisudoku.com 0.554 to 0.599 on 2,762 puzzles, per-layout bias 0.81 to 1.53 narrowed to 0.87 to 1.12 | Kept |
| 2026-10-27 to 10-29 | The spread of times over players | fed-sudoku.eu, sudoku.coach, grandgames.net | A fixed 80th percentile at 1.53 × median is within one person; across players it is 2.23 (fed-sudoku.eu) and 1.81 (sudoku.coach). Log-normal fits within 0.15 of the quantiles (834 puzzles). Rules lower the spread on two sources (−0.195, −0.171); length dependence disagrees in sign | Kept: log-normal, 0.79 for classics and multi-grid layouts, 0.62 with other rules |
| 2026-10-29 | Multi-grid layouts with the same players | grandgames.net (11 layouts) | Within ×0.86 to ×0.98 of the same players' classics for 9 of 11 layouts; the largest (super samurai) ×0.67; first solves ×1.9 to 2.0, after 64 solves ×0.74 | Kept: the gap is practice |

## Variants on one scale

Whether a difficulty means the same on a variant as on a classic.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-16 to 10-18 | Why variants ranked worse than classics | sudoku.coach (828 9×9 variants), lisudoku (210,000 placements) | Variants 0.61 against classics 0.90; arithmetic rules under-priced (sandwich +1.5 points), simple relations over-priced. On lisudoku people take 2.50 times longer for a line single, the engine prices it 1.32 times | Led to the rule constraint in step prices |
| 2026-10-20 | Offsets between types at equal difficulty | grandgames.net, sudoku.coach, lisudoku, Puzzle Duel, three rating sources | sudoku.coach variants play 2.8 to 4.8 points harder (same players too); grandgames.net offsets mostly within ±1. Ratings disagree on the sign of any variant offset (sudoku.coach's own rating −2.5, logic-masters.de −1.0, sudoku-variants +1.8). Irregular regions play harder on three sources | No difficulty correction; regions went into time |
| 2026-10-23 to 10-24 | Engine changes in rule reading: rules with more than 50 fillings left to the notes phase, the difference of two overlapping sums, native pair encodings, class counting, table dominoes | sudoku.today; grandgames.net, sudoku.coach, logic-masters.de, sudoku-variants as checks | Notes-phase cap: x-sums with greater-than 0.10 to 0.59, skyscrapers 0.25 to 0.59, kropki 0.49 to 0.56; logic-masters.de 0.657 to 0.658. Overlapping sums: group sum 0.37 to 0.48. Native pairs: answer-8 0.52 to 0.57 but differences 0.46 to 0.21. Class counting and dominoes: unchanged | Cap and overlapping sums kept; the rest dropped |
| 2026-10-26 to 10-27 | Three shortcut techniques (colour classes, clue facts, clue shapes) | sudoku.today (14 types), logic-masters.de | Mean +0.004 on sudoku.today, +0.010 on logic-masters.de; kropki +0.069 on sudoku.today; XV disagrees between the two | Kept for more human routes (a whisper route 136 to 105 steps); below the accuracy bar |
| 2026-10-27 | Explaining the variant level: where it sits in the card, rule work hidden in singles, a level per rule family | sudoku.today, sudoku.coach, grandgames.net, Puzzle Duel | The gap sits in the candidate-density factor, not in technique prices; variants at the same band take 1.18 to 1.36 times longer than classics. Pricing hidden rule work closes the gap but destroys ranking (sudoku.coach 0.70 to 0.20). Family models left out by family: structure 1.82 and rarity 1.54 against 1.72 and 1.60 for one constant. Experts on Puzzle Duel show no rule-variant slowdown | Dropped: the level depends on the audience |
| 2026-10-28 to 10-29 | Audiences: learning curves, experienced players, self-reported times | grandgames.net (323,777 solves), sudoku.today replays, logic-masters.de (1,424 times) | Same-player offsets ×0.87 (killer) to ×3.02 (rossini); kropki falls from ×1.90 on first solves to ×0.61 after 64. Experienced players: skyscraper ×2.03, rossini ×2.00, kropki ×0.63, killer ×0.74. Rule-only singles wait 2.5 to 4 times longer in replays. Enthusiasts' self-reported times: family offsets ×0.98 to ×1.12 | Informative: pair rules are learning; outside clues stay under-priced |
| 2026-10-28 | Step and state costs of rule reads: a ×5 price on rule-read singles, a measured read shape, availability (race), locality | four sources, Puzzle Duel held out | ×5: mean +0.031 (21 groups up, 5 down) but logic-masters.de −0.016 and no level effect. Read shape fitted on SudokuPad replays, applied unchanged: grandgames.net +0.011, sudoku.today +0.007. Availability: sudoku.coach 0.753 to 0.708. Locality: sudoku.today 0.563 to 0.464 | Dropped: below 0.02 or not on all sources |
| 2026-10-28 to 10-29 | Mean cage size for killers | grandgames.net, logic-masters.de, sudoku.coach, 242 killers rated by Andrew Stuart | Cross-validated grandgames.net 0.820 to 0.866, logic-masters.de 0.585 to 0.637, sudoku.coach none; carried to other families it costs up to 0.16. Andrew Stuart's ratings miss big cages more (+0.58 against our +0.35) | Dropped: a documented limitation |
| 2026-10-29 | Puzzles with several rule kinds | sudoku.coach | A mixed puzzle costs like the mean of its rules (error 0.383), not their sum (1.097); the card reaches 96% of the noise ceiling on classics but 81%, 68%, 65% with 1, 2, 3 or more rule kinds | Informative |

## Bands

The band is a rule, so these experiments test its stability and its relation to other curricula.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-10 to 10-16 | Stability of the band, and agreement with computer ratings | 3,000 random classics (Berthier); 150 puzzles × 5 random routes; rollouts on 200 | Tier against the W-rating 0.955 (Sudoku Explainer 0.94). Band 100% stable across routes, while which pattern within a band varies; rollouts agree on the band 100% and 96% but wander into unlisted techniques | Band route kept; rollouts dropped |
| 2026-10-25 | Our bands against sudoku.coach's 13 levels | 2,537 sudoku.coach classics | Against median time: sudoku.coach's level 0.841, our band 0.828, our difficulty 0.884; about half of sudoku.coach's adjacent levels do not separate, each of our bands does | Kept; sub-bands rejected (boundaries overlap) |
| 2026-10-26 | Trial and error instead of guessing when logic runs out | six former Unknown puzzles | Three became Extreme, three unchanged | Kept: guessing off by default |
| 2026-10-30 | Seven bands, Hard as the first learned patterns | 7,427 frozen puzzles, 747 frozen classics | Difficulty and time unchanged on every puzzle; Very Easy is HoDoKu's Easy in 100% of cases | Kept |
| 2026-10-30 | When band and difficulty disagree, whom do people side with? | development set: sudoku.coach (279 Medium, 105 Hard), grandgames.net, Puzzle Duel | sudoku.coach solvers sided with the band only 24% of the time (18% to 30%), grandgames.net 0% to 29%, Puzzle Duel 19% | Kept: bands order knowledge, difficulty orders effort |

## Engine speed

Exact speed-ups were kept; anything that changed a card was not.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-22 | Shared move listing, lower search budget, lazy band path | sample pack | Shared listing slower (524 s against 46 s) and changed 11 of 30; lower budget changed 5 of 7; a lazy band path was either exact and 5 to 10 times slower or faster and wrong (bands changed on 2 puzzles) | Dropped |
| 2026-10-15 to 10-31 | Exact speed-ups: batched solves with an early stop, caches for rule checks and sums, move listings, staged listing, a content-keyed puzzle cache | sample pack, public and private golden corpora | Batching: 54 sample cards 2,446 s to 814 s. Caches: 14 slow puzzles 1,201 s to 733 s; 16×16 technique list 196 s to 62 s with listing caches, and from 50 s to 30.5 s with staged listing; cards with steps 1,506 s to 445 s; classic cards 26% to 52% faster; all cards identical | Kept |
| 2026-10-27 | Faster technique-free term: exact pruning against sampling | 241 puzzles | Exact: identical, 1.35 times faster on slow puzzles. Sampling: 2.2 times at best, correlation 0.86 to 0.95 with exact | Exact kept; sampling dropped |
| 2026-10-27 to 10-31 | Reusing a route prefix across technique-list reruns; porting the band route to C++ | 30 puzzles; profile | Prefix reuse: identical cards but 0.95 times the speed, later found unsafe (bans can change the route before the first banned step). Profile: 99% of a band route's time was already the C++ move listing | Dropped |

## Generator

Making puzzles to order, and what limited it.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-22 | Puzzles whose hardest step is exactly one X-Wing | generator runs | Of 2.38 million clue removals, 9,700 kept singles plus X-Wing solvable and 9,695 of those fell to easier techniques. Rewritten in C: 10 puzzles in 45 s against 3 in 18 minutes | Kept; the rarity is in the target, not the search |
| 2026-10-22 | Variant generation: a curriculum for seven rule kinds, a 16×16 killer with 32 cages | 7 kinds × 4 stages; generator runs | Stages 1 and 2: 7 of 7; stage 3 (the kind's own technique required): 4 of 7 within 300 s; zero givens only for killers. The 16×16 stalled at 72 cages: 32 random-ish cages leave about 2^62 solutions | Partly kept; large killers need informative cages by construction |
| 2026-10-22 to 10-23 | Search objective, and joint targets on a multi-grid board | 49-cell picture mask; super samurai | Band as the objective traps the search; difficulty as the objective with the band as a constraint reached Medium 5.9 with jigsaw boxes against Very Easy 2.2. On the super samurai every generation order failed until each grid was generated with all shared cells known; then every grid met its band | Kept: difficulty as objective, shared cells known |
| 2026-10-29 | Five requests against HoDoKu and Sudoku Explainer | 10 puzzles per tool | 18 s to 66 s per kept puzzle against 0.05 s to 2.2 s; none at the hardest band within 120 s | Known issue: speed and the hardest band |

## Other measurements

Quality signals, fog, comments and checks of our own output.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-11 to 10-27 | Quality signals: puzzles resting on one hard step, enjoyment from the profile, compliment words, per-cage necessity | sudoku.coach likes, logic-masters.de ratings and comments, grandgames.net, sudoku-variants | Hard puzzles with at least 95% singles get 38% fewer likes per solve (p 0.025); a top-3 effort share above 60% lowers logic-masters.de ratings (partial −0.082). Enjoyment model: grandgames.net likes 0.08 to 0.26, logic-masters.de 0.46 to 0.44. No usable compliment detector; every cage was individually optional in 196 of 200 killers | Spike kept as a warning, not a rejection; the rest dropped |
| 2026-10-22 | Modelling fog puzzles | 39 fog puzzles | Solvable with full information 85%, with fog and partial element knowledge 33% | Dropped: fog needs a visibility layer, not a term |
| 2026-10-22 | Techniques named in comments against the card | logic-masters.de (415 puzzles) | X-Wing lift 3.2, parity 5.0, colouring 1.7; trial lift 1.0 | Informative: named patterns are recognisable, chains are not |
| 2026-10-27 | A per-puzzle uncertainty signal from card changes under transposition | sudoku.today (900 variants) | Correlation with the error +0.054; averaging orientations 0.645 to 0.646 | Dropped: no signal beyond the band |
| 2026-10-30 to 10-31 | Checks of our formats and output: an audit against formats that lasted, every step of every reference card, an independent rule checker | puzzle and card formats; 23,800 steps; 277 puzzles | 15 format problems, among them three overlapping completeness flags and an absence with two meanings; 0 wrong placements, 0 eliminated solution digits, 0 rule violations | Format problems fixed before 1.0; step checks kept as gates |

## Benchmarks and other graders

Comparisons on the same puzzles, before and after the frozen set.

| Date | Tried | Measured on | Result | Verdict |
|---|---|---|---|---|
| 2026-10-19 to 10-21 | Head to head with Andrew Stuart's grader on two communities | fed-sudoku.eu (3,739), sudoku.coach (150 classics) | fed-sudoku.eu 0.860 against 0.843 (difference +0.007 to +0.026), hard tab 0.614 against 0.672. sudoku.coach 0.827 against 0.835, hardest third 0.408 against 0.419 | His hard-end lead is specific to fed-sudoku.eu |
| 2026-10-25 | A published dataset never used in fitting; other graders on the development split | Wang 2024 (1,533 classics), fed-sudoku.eu, sudoku.today | Wang 2024: 0.603 against average time, 0.673 with at least 20 players; time ×0.98. fed-sudoku.eu ours 0.641, Andrew Stuart 0.622, Sudoku Explainer 0.410, HoDoKu 0.364; variants ours 0.660, Rangsk 0.645, with Rangsk ahead on x-sums | Wang 2024 added to the frozen set; the x-sums gap led to a translation fix |
| 2026-10-29 | Killers against Andrew Stuart's killer grader | grandgames.net (558), sudoku.coach (36), logic-masters.de (26) | 0.836 against 0.825; 0.647 against 0.787; 0.491 against 0.035 | Slightly ahead on the large set |
| 2026-10-29 to 10-30 | The frozen benchmark | 7,623 puzzles, 15% of every source | Development numbers close to frozen ones (fed-sudoku.eu 0.641 development, 0.670 frozen); results in the [benchmark](BENCHMARK.mdx) | Published |
