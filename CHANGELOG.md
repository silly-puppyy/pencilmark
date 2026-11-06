# Changelog

## Unreleased

What changes for you (details in the entries below):

- **Difficulty values move.** The search part counts refutations in propagation rounds and the score map is refitted
  (easy puzzles a little higher, hard ones a little lower), and the difficulty is the expected effort of a human-like
  solver (bottleneck rollouts, +0.09 on average). Rank agreement with human times rises (fed +0.040, Wang 2024 +0.028).
- **Some bands and technique lists move.** The band route is the human one (reference cards: 1 of 227 bands).
  Colouring as a solving method is opt in (`rate(colouring=True)`, `--colouring`).
- **Publishing checks.** `thin` replaces `spike`; the `unusual` ranges are re-measured; quality presets
  (`{"preset": "standard"}`) and opt-in checks are new.
- **Breaking, no aliases** (nobody depends on them yet): fingerprints drop the `sha256:` prefix; `box_grid` needs `count`; colouring codes share the prefix C
  (EQD -> CEQ, SCL -> CSM, MCL -> CMU, 3DM -> CMD, identity-layer codes CSG / CFL / CPR / CTR); generated puzzles carry
  `meta.generated_from` only when the spec asks.
- **Breaking, no aliases:** the format names are `pencilmark-puzzle`, `pencilmark-grade` and `pencilmark-spec` (the format is
  called "pencilmark JSON"; were `sudoku-puzzle`, `sudoku-grade`, `sudoku-spec`); the schema files are renamed to match.
- **New in the format:** fog of war, regions to find (chaos), shading (yin-yang), custom-rule unknowns and layers.
  `rate` grades fog under the fog; shading and unknowns give band Unknown with a `reason` for now (they load,
  validate, solve and count). Errors are only for wrong inputs (unreadable, misread, not unique, no solution).

- Reading and writing, one function per format (no aliases): `pencilmark.read.plain / grid / pencil_marks /
  candidates / hodoku / sudokuwiki / ipuz / pencilmark / link` each read one format strictly (FormatError otherwise);
  `pencilmark.write.pencilmark / document / plain / grid / sudokuwiki / ipuz` write one. `rate`, `solve`,
  `count_solutions`, `describe`, `fingerprint` and the command line take any of them, detected (`read.detect`,
  `read.auto`), and `rate(format=...)` names it. Gone: `load`, `to_export`, `dumps`, `from_string`, `to_string`,
  `from_ipuz`, `to_ipuz`, `rules_text` (now in `describe`'s result), the CLI `json` command, and the engine's internal
  JSON and sample-pack lines as inputs. A written document is kept as given (no longer rebuilt through the engine;
  fingerprints unchanged). Site links: the host names the reader, no options.
- Command line: every command takes `--from FORMAT` (default: detected per line); `rate --print TEMPLATE` replaces
  `--format` (which read like the input format); `convert --to pencilmark|plain|grid|sudokuwiki|ipuz` replaces
  `export`; `generate --seed / --time` are gone (the spec's `limits` hold them).
- Public functions take their options as keywords only and carry type hints. `rate` gives band Unknown with a `reason`
  (and `completed: false` under `max_seconds`) where it raised `Undecided`: the engine could not settle uniqueness,
  which is not an input mistake; `solve` still raises it. `solve(info=True)` is gone; `solve` and `count_solutions`
  take `format=`.
- `placed` (pencilmark JSON): digits filled in after the start, as on a mid-solve board. Solved and graded like givens
  (the rest of the solve is graded), not clues for the publishing checks and symmetry. The sudokuwiki reader keeps
  Andrew Stuart's placed digits (code d + 9) as placed and the writer writes them back.
- Step notation names houses by position for every input ("X-Wing: 3 r58 c68", "in b5"); pencilmark JSON inputs
  printed group names ("row4 row7 col14").
- One error family: every error is a `pencilmark.Error` (`FormatError`, `NotSupportedError`, `FetchError`,
  `ReadingMismatch`, `NotUnique`, `NoSolution`, `Undecided`, `GenerationFailed`), exported at the top level. The site
  readers' `SourceError`, `DecodeError` (now `FormatError`), `UnsupportedPuzzle` (now `NotSupportedError`, `.elements`
  kept) and `VerificationError` (now `ReadingMismatch`) are gone; a custom-rule `LangError` is a `FormatError`.
- Techniques checked against Andrew Stuart's sudokuwiki.org strategy examples (141 positions, every move sound) and
  independent reference finders; what was missing is added:
  - XY-Chain: a second chain search over bivalue cells only, so an XY-chain is no longer named (and priced) AIC when an
    AIC of the same length joins the same ends.
  - Simple Colouring and 3D Medusa: a colour that would leave a house no place for a digit is false (sudokuwiki's
    rule of July 2026).
  - Hidden Unique Rectangle type 2 (bivalue floor, a strong link from it to the roof) and Extended Unique Rectangle
    type 2 (two cells with the same one extra digit).
  - Aligned Pair Exclusion also counts two cells sharing three digits that see both cells of the pair.
  Bands unchanged on the reference cards; times and difficulties move by up to 0.5 on 32 of 227.
- Gaps the cited sources show, filled: WXYZ-Wing type 2 (every digit restricted: each leaves the cells seeing all its
  wing cells; sudokuwiki); Death Blossom stems of any size (sudokuwiki, HoDoKu, Sudopedia); Aligned Pair Exclusion
  takes any almost locked set seeing both cells as a witness, and non-aligned pairs (sudokuwiki type 2). Reference
  cards: bands unchanged.
- More names checked against every cited source (docs/research, 2026-11-07): a Skyscraper's pairs must share a line at
  their inner ends (else Turbot Fish, HoDoKu / Sudopedia); a chain-found Empty Rectangle needs the box's candidates on
  one row and one column; an XY-Chain has the same digit at both ends (else AIC); Remote Pairs need 4+ cells; basic
  X-Wings and Swordfish carry their shape, so Mutant fish are named Mutant (they were called Franken). Reference cards:
  bands unchanged.
- Names that match the pattern (checked against sudokuwiki.org's examples by their cited page, and against reference
  finders): a finned X-Wing / Swordfish is no longer named a Franken fish when its eliminations have a plain row /
  column spelling (the fish search lists line fish first; equal moves keep the plainer shape); Empty Rectangles are
  found directly (HoDoKu's definition) instead of only when the shortest chain had the ER shape (they were long
  X-Chains or missed when the box's crossing cell held the digit). Skyscraper and 2-String Kite no longer cite
  sudokuwiki's Rectangle Elimination, which is the Empty Rectangle. Reference cards: bands unchanged.
- Pattern Overlay rule 2 (sudokuwiki.org): a template of one digit that meets every template of another digit is not
  the solution's; candidates left in no surviving template go. Bounded (1,000 templates per digit); reference cards
  unchanged.
- Definitions follow the cited sources (docs/grades/techniques.md): WXYZ-Wing is any four cells holding four digits,
  not all in one house, with one digit not confined to cells that see each other (sudokuwiki.org; before: only cells in
  one box and one line); an almost locked set has any size (HoDoKu; before: at most 4 cells). Reference cards: bands
  unchanged, difficulty within 0.1; speed unchanged (60 frozen puzzles, 978 s against 980 s).
- Quality presets: `quality={"preset": "standard"}` (`--quality preset=standard`) turns on decorative, trivial, trial,
  thin and unusual (all reject) and switches the other checks off; checks named next to the preset adjust it.
- Opt-in quality checks (off unless named): `asymmetric`, `no_interplay`, `winding`, `short_lines`, `repetitive`,
  `monotone`, `desert`, `late_break`; limits near the edge of published Medium+ puzzles
  (1-27% of them flagged, per check).
- Fingerprints are the bare SHA-256 digest, 64 lowercase hex digits, without the `sha256:` prefix (puzzle and spec
  fingerprints, `meta.fingerprint`, `meta.generated_from`). The digest itself is unchanged. No alias.
- Engine: `CB.solve(stop_cells=)` stops right after a step that places one of the cells; the fog card's routes stop at
  each reveal inside the engine instead of solving the visible puzzle on (one fog card: over 120 s -> 21 s).
- The fog route ends each round's band route at the first placement that lights new cells instead of solving on and
  discarding the rest: the same routes, up to 125x faster (265 s -> 2 s on one sudoku.coach puzzle).
- `rate` grades fog-of-war puzzles under the fog: the band and techniques of the fog route (the human route on what
  the fog shows, round by round); difficulty and time by the card's own routes run the same way under the fog (the
  same algorithm as every card: a fog rule that lights every cell gives exactly the card without fog). A card field
  `fog` tells what the fog did (lit at the
  start, reveals, rounds, solved); where the fog stops the route, the band is Unknown with `stopped_at_step`, never
  the revealed grade. Errors stay for inputs that are wrong. Fog visibility now includes pair relations and custom
  rules (they were dropped, so a route could stall with nothing fogged).
- Published ranges per band (`unusual`, the generator guide's table) re-measured on the 1.2 engine and the repaired
  development set (7,155 puzzles): variant Easy from 4.7 (was 4.4), variant Hard from 5.2 (was 4.6), variant Very Easy
  up to 5.9 (was 5.6); variant Extreme has too few puzzles for a range now. The guide recommends the standard preset.
- Export: a rule part tagged with its line kind is dropped only when its line is there too; a reader that built only
  the part (an equal sum for a region-sum line) no longer loses the rule on export.
- Custom rules: a set of number literals (`concat(c) in {...}`) is built once, not once per digit tuple: a puzzle
  with 64 such rules (global entropy) loaded in 27 min; now 1.7 s (`concat(c) in {...}` over one list of cells reads
  its table straight from the numbers).
- Colour Algebra (colour the grid as unknown digits) comes before band set theory in the Very Hard study order: the
  route opens with the colouring that solvers describe on zero-given palindrome puzzles; grades unchanged.
- Colouring is opt in: `rate(puzzle, colouring=True)` (CLI `--colouring`, also `rate_many`) puts the identity layer's
  colour techniques on the human route; the default leaves them out. Most solvers do not colour (sudoku.coach
  comments mention it on 4% of classics, 10% overall, mostly palindromes and zero-given puzzles), and with it the
  hardest variants grade 2-3x slower. The CLI's rate now goes through `rate()` (it graded fog, shading and unknowns
  puzzles on its own path).
- Publishing check `thin` replaces `spike`: a Medium or harder puzzle whose candidate steps carry less than 25% of
  its effort (singles around one hard step that changes little; Andrew Stuart: "too few candidates removed using
  candidate strategies"). `spike` flagged most published puzzles (83-92% of human-set Medium / Hard): concentrated
  effort is normal; little candidate work is not. Measured on fed, sudoku.coach and Stuart's daily puzzles.
- Format: `box_grid` states its tiling as a box size and a repetition count, `{"type": "box_grid", "box": [3, 3],
  "count": [3, 3]}` (3×3 boxes, 3×3 times); `count` is required. `origin` of `grid`, `box_grid` and `chaos` is
  optional, `r1c1` by default, and writers and the canonical form leave it out there. Files without `count` are refused
  (no aliases). Fingerprints are unchanged (they hash the houses).
- Generated puzzles no longer carry `meta.generated_from` by default. A spec asks for it in its own `meta`
  (`"meta": {"generated_from": true, "fingerprint": true}`), and the puzzle gets the request's fingerprint and the new
  optional `meta.fingerprint`, its own (`meta` is outside the fingerprint, so a file can carry it).
- Reader: f-puzzles fog written as generic cages, as SudokuPad imports them, is read (a one-cell `FOW` cage lights
  its 3x3, a `FOGLIGHT` cage its cells); an invisible `FOW` cage was dropped and the puzzle refused. Rules that
  describe indexing without the word ("digits in column 1 indicate the column in which the digit 1 appears") are
  refused instead of read without them.
- Colouring techniques share a code prefix C (codes appear in cards' `contains` and steps): Same Colour EQD -> CEQ,
  Simple Colouring SCL -> CSM, Multi-colouring MCL -> CMU, 3D Medusa 3DM -> CMD; the identity-layer codes become CSG
  (Colour Single), CFL (Colour Fill), CPR (Colour Pair), CTR (Colour Trap). Class Colouring CCL and Colour Algebra CAL
  keep theirs. No aliases.
- Bands: Clue Facts are Easy (memorised variant facts), Colour Fill Medium; colouring techniques get short names (Same
  Colour, Colour Single, Colour Fill, Colour Pair, Colour Trap, Simple Colouring, Class Colouring).
- Colour Fish (CFS, Hard) and Complete Colours (CCM, Medium), with `colouring` on: an X-Wing over a colour (two houses
  confine it to two others), and k colours with a cell in every row and k possible digits between them, which use
  those digits up. Colours whose cells see each other count as different. Up to 48 colours are kept (was 16).
- Experimental fog route: colours are kept across reveals, and visible cell rules (parity squares and the like) narrow
  the candidates (they were dropped each round). Restricted Access (CtC) now solves under the fog with colouring on,
  first digit as the host's.
- Colour Pointing (CPT, Medium; with `colouring` on): pointing for a colour. When a colour's places in one house all lie
  in another house, the other cells of that house are not that colour (CtC, Restricted Access: "orange is in one of
  these two positions").
- Two colouring techniques of their own: Chain Colour (CCH, Medium: two cells forced to hold one digit through a third
  tied to both by pair rules, e.g. V dominoes) and Colour Clash (CCX, Hard: a cell that would leave a linked colour no
  digit never has the first colour). Both were reported as Same Colour / Colour Single before, with explanations that
  read their cells wrongly.
- Explanation sub-steps of colouring steps (identity layer): each colour keeps one colour name for the whole solve,
  with a legend the first time it appears ("orange": "an unknown digit (5 or 6)") and its cells drawn in it.
- Fog of war is a rule of the format (6.20): `{"type": "fog", "lit": [...], "triggers": [{"when": [...], "light":
  [...]}]}`. Without triggers a correct digit lights its 3x3; with them only the triggers reveal. `lit` is everything
  visible at the start (givens as the source shows them), and a fog puzzle must carry its solution. The SudokuPad
  reader fills it from FOGLIGHT cages, `foglight` and `triggereffect` (adding each given's own cell); the f-puzzles
  reader from `foglight` / `fogofwar`. Fog puzzles now load, validate, solve, count and
  export with their fog, and `rate` grades them under the fog (entry above). Of the Cracking the Cryptic fog puzzles, 43 now load with their fog (none before).
- Engine rule kind `cases` (one of several cases holds; each case a set of cells with a circle = the sum of the
  others or a total, house peers different): the engine checks every case against the live candidates. The fog route
  uses it for arrows seen in part (the possible hidden shafts, with "arrows move orthogonally / don't share cells"
  from the rules text). Golden gate identical.
- Experimental: `pencilmark.fog.route(puzzle)`, the route a solver can take under the fog (what is lit, reveals on
  correct digits and setter triggers, no guessing); not yet used by `rate`. Hidden-content reasoning (partly seen
  arrows, cage shapes) comes with the engine port (docs/research/fog_engine_port.md in the research repo).
- Links are checked against the setter's embedded solution by default: a reading the solution breaks is refused with
  `VerificationError` ("the reading contradicts the setter's embedded solution"); `sources.load(...,
  check_solution=False)` skips it. On the 1,351 Cracking the Cryptic SudokuPad puzzles: 345 correct readings all
  still load, 107 of 112 misreads (one-off rules worded like standard ones) are now refused; the other 5 have no usable
  embedded solution or an undecided check. The import guide lists what links read and what they don't.
- Custom rules that read a list only at constant indices compile over just those cells: "ray[3] + ray[4] == 3" over a
  9-cell ray is now a 2-cell table, not a 9-cell expression constraint. Results are unchanged (golden gate
  identical). Hand ports that declared whole rays now grade: three GAS ports went from Unknown to Very Easy 5.8 / Easy
  9.0 / Easy 7.5.
- The solve trace follows a human route by default (computer search stays opt-in with `mode="computer"` /
  `--computer`): each step is chosen the way people choose, by a spotting score fitted on casual classic replays (the
  move's price, its technique, and attention to the previous placement: same digit, same box / row / column, distance),
  sampled reproducibly (params `spot_w`, `spot_fam`, `spot_seed`). On held-out sudoku.today replays the trace's
  step-to-step behaviour is about 4x closer to people's than before. The band, the technique list and the publishing
  checks follow the band route, which is now the human one: on the private golden corpus 1 of 227 bands, 15 technique
  lists and some warnings differ.
- Card difficulty is the expected effort of a human-like solver, estimated cheaply (score `route_rollouts`: 2 human
  routes, 4 playthroughs): singles reach the same next bottleneck in any order, so each human route keeps its
  bottleneck steps and the stretches of singles between them are replayed in random human order from the state the
  route reached. Dev set, within-group Spearman vs the old card: fed +0.040, Wang 2024 +0.028, sudoku.coach +0.009,
  grandgames -0.001. Difficulty rises 0.09 on average (more on singles-only puzzles); bands are unchanged. Rating takes
  about 15% longer (1.54 -> 1.77 s on dev puzzles). The time quote still reads the single price-first route (score
  `card_route`).
- Optional: score `route_samples` = K (with `route_rollouts` off) makes the difficulty the mean effort over K full
  sampled human routes (on threads in a single rating): a similar gain for about a third more rating time.
- Note model of casual classic solvers, on by default as bookkeeping: position notes written as you go (`notes_live`:
  a digit with 2-3 places left in a box), candidate lists in the cells with <= 3 candidates when notes start
  (`notes_small`), every other cell written only when a step uses it (`notes_lazy`); the marks are counted on each
  step's `notes_written`. On lisudoku replays its marked cells overlap people's far better on medium puzzles (Jaccard
  0.65 vs 0.39 for full notes). Routes, prices and the card are unchanged (`notes_lazy_view` false; the card prices
  full notes: score `card_notes`). The card's `trace` gains a `marks` layer per position (grade-card.md 6): the corner
  position notes and centre candidate lists such a solver would have written, so a viewer can draw them instead of
  the full candidates.
- Colour model of expert solvers, on by default (`notes_colours`): the card's `trace` gains a `colours` layer per
  position (grade-card.md 6), the identity colours a host would have painted: pair colouring ("colour the sevens and
  nines against each other": two cells of a house with the same two candidates take opposite colours) and each
  colour tracked through houses (one cell left that can hold it) and equality rules, at most three colour pairs, the
  largest. On Cracking the Cryptic solves it covers more of the hosts' own identity colours at the moment they paint
  them (0.45 vs 0.31 from the digits placed alone, 158 groups in 83 videos) while drawing about as many colours at
  once as the hosts keep (about two). Bookkeeping only: routes, prices and the card are unchanged.
- Custom rules: named `unknowns` (a number several clues share, or a 0 / 1 choice) and `layers` (a second value per
  cell, e.g. a -1 / 0 / +1 shift) at the top level of the puzzle file, read by custom rules as `X` and `shift(c)`
  (rules/custom.mdx, unknowns and layers; puzzle-format.md; schema). pencilmark reads, checks, writes and evaluates
  them, and the exhaustive search solves and counts such puzzles: the C++ model carries them as aux variables (a value
  set per unknown and per layer cell), a rule reading them is checked over its open hidden values once at most two of
  its digits are open, and the search branches on them once the digits are fixed (uniqueness by digits). `rate`
  gives band Unknown with a `reason` (no human technique reasons with them yet).
- Engine: lemma rules (internal, for derived facts; docs/research/engine_aux_lemma_design.md in the research notes).
  An internal table constraint may carry `lemma` {id, setup, use}: its moves cost `setup` the first time any rule of
  that lemma is used in a route and `use` afterwards; a constraint marked `gated` makes no human moves (combination
  steps, rule intersections, band logic, rule reads in the head) while the search still checks it. Nothing in the
  puzzle format uses them yet; cards and routes are unchanged.
- New engine param, off by default: `digit_cont` (favour the previous placement's digit).
- Shading (format: `"type": "yin_yang"`, optional given `shaded` / `unshaded` cells; whole-board-rules 6.19): shaded
  and unshaded cells each orthogonally connected, no 2x2 of one colour. Readers, writers, `fingerprint` and
  `describe` handle it; `solve` and `count_solutions` check it (the exhaustive search carries a colour per cell, agreeing with a
  CP-SAT model on 700 random small puzzles); `rate` gives band Unknown with a `reason`
  until the engine has a shading layer.
- Custom rules can read board layers: `region(c)` (regions to find) and `shaded(c)` (shading). `region()` rules are
  checked on chaos boards (uniqueness, solving, the human route's last resort), `shaded()` rules when solving and
  counting shading puzzles.
- Card field `trace`: the board (digits and candidates) before the first step and after each step, so a viewer can
  replay a solve with the steps' `substeps` annotations.
- Rule facts in explanations are worked out for the puzzle's digit range (a whisper on 16x16 has no impossible digit
  and no low / high alternation; a 6x6 black dot excludes only 5), not written for 9x9.
- Reader: coloured lines described without their name ("a purple line contains a set of consecutive digits"),
  generic f-puzzles lines from the rules text, "all lines are X lines", branching arrows, region-sum loops, between
  lines through several circles; refused instead of misread: anti-line rules, broken zippers, rings drawn along grid
  lines, default line colours without a positive description, a line with two rules. Screen of 1,351 Cracking the
  Cryptic puzzles: 281 -> 337 graded.
- Reader, from the GMPuzzles GAS series (286 posts with replays: 136 -> 217 graded): skyscrapers and sum frames
  from their wordings, little killers drawn as arrowheads, fortress cells, clones drawn as coloured shapes, Rossini
  arrows, Battenburg markers (with sums on them), f-puzzles' own X-sum clues, typographic quotes in rules texts;
  one-off line rules as custom rules (sequence lines, alternating lines, one-digit lines; lines whose neighbours
  differ by 1); "along each line"; "a difference of 4 or more"; f-puzzles lines read from the page's wording when the
  payload's own is terser; one-off outside clues as custom rules over the cells seen from the clue (outside, first
  odd / even, neighbours, coast to coast, consecutive count, max + min, median, highball, sum next to nine, position
  of the largest, interval sums, sum before the nine); numbers drawn just beside an edge circle read as that dot's
  number; "the greater number" between two cells; a clue 0
  stored as a number is no longer dropped; one-off whole-grid rules as scoped custom rules (encaged digits, no three
  of a parity in a row, anti-XV, no checkerboard, box triples divisible by three), for f-puzzles payloads too;
  shapes with digit sets by colour (circles / squares / diamonds); clues on marked cells as custom rules (a circled
  digit against its neighbours: sum, distinct count, same-parity count; an X against its diagonal neighbours; a small
  arrow in a cell against the cells it points at: detection, elimination, prime count); arrow variants as custom
  rules (even count, all but one, strictly less, at most, one off, average; repeating and alternating parity on top
  of the sum); clues whose text redefines them (quadruple digits that must not appear, cage numbers listing digits
  in the cage, dots meaning consecutive or double, diagonals with a count of distinct digits; numbered white / black
  dots as difference / ratio by colour; zones listing two of three digits, palindromes with one mismatched pair or
  with consecutive partners, arrows counting distinct digits, cages all even / all odd / half and half; given
  pencil marks as candidates; lines whose digits are all odd or all even); refused
  instead of
  misread: a puzzle that reads
  as plain sudoku while it draws shapes or lines in the grid (15 of 1,500 sampled Logic Masters puzzles, all of
  them misread before).
- Styles: a SudokuPad puzzle's look (line colours and widths, cage colours, dot and shape fills) is exported as each
  rule's cosmetic `style`, for named and custom rules alike; `to_export(..., style=False)` leaves it out.
- Readers write parity and digit-set shapes (SudokuPad) and f-puzzles odd / even cells as `cell` rules, not as
  given candidates; a cell rule drawn as one shape per cell takes the shapes' shared look as its style.
- f-puzzles numbers written as text outside the grid are read like SudokuPad outside clues (from the payload's rules
  text, else the page's), and refused when nothing reads them (they were dropped as decoration: 54 GAS Leak puzzles
  and 5 sampled Logic Masters puzzles read as plain sudoku with two solutions). Numbered rooms are written as the
  custom rule `ray[ray[1]] == X` (they were internal digit tables the format cannot hold).
- f-puzzles one-cell circles and squares (rectangles, dropped as decoration before) are read as shape clues
  (parity, digit sets: "1s, 2s, and 3s are marked with circles").
- f-puzzles generic lines take every line rule the SudokuPad reader knows from a description (custom-rule lines,
  same parity, one apart, palindrome variants), also when the lines are drawn in several shades; new line
  descriptions: increasing or decreasing, every digit twice, centre sum, three distinct digits on a marked diagonal,
  evenly spaced sequences, more same-parity and entropic wordings.
- Reader fixes from the 500 most-solved Logic Masters sudokus (graded 157 -> 165): "[no negative constraints]" no
  longer adds negatives; "If not, they don't" after a marker rule makes it negative; "at least 5 apart" whispers;
  equal-parity lines; thermos of a single parity; cells greater / less than a digit by colour or shape; f-puzzles
  coloured cells read by the shape-clue reader when the text gives them a meaning; "digits in the cage are odd"; cells
  of one colour "are the same number"; refused instead of misread: maze paths (RAT RUN), digit subsets chosen by
  the solver, every clue type exclusive across the puzzle, cage sums to find; line colours the text calls
  decorative ("have no effect") are ignored (graded 165 -> 169).
- Lines: whispers with their own threshold ("differ by at least 3", "minimum difference of 5"), fixed line totals
  ("numbers on blue lines sum to 20"), more decorative wordings, entropic / parity / renban wordings; f-puzzles
  renban and line-total segments drawn in pieces are joined into one line, or kept separate when that is the reading
  with the setter's solution; "chess knight jump" is anti-knight; a difference with an upper bound is not a whisper.
  More wordings: equal cage sums ("every cage has the same sum": the shown total for every cage, else a custom
  rule), counting rings, region-sum "segments with the same sum", quadruple "a cell touching the circle", longer
  whisper sentences and thresholds in words; refused: "one digit in each row that does not fit".
  Whole-grid rules from the text: 180-degree pair sums, 159 indexing (columns 1, 5 and 9), caged digits not next to
  a consecutive digit, no repeats around a digit; f-puzzles payloads read global entropy and Dutch flat mates too.
  Anti-knight stated for marked cells only ("the digit in the yellow cell ... a knight's move away") applies to those
  cells, not the whole grid (refused when the cells are not found).
  Oil and water cages (each cage row one parity, even rows above odd) as custom rules; refused instead of misread:
  pick-up sticks, a magic square somewhere, every domino once, dice, letters for digits, clues or objects the
  solver must place.
  "All possible dots are given" adds negatives only for the dot kinds the text mentions.
  Equality cages (as many low as high and as many even as odd digits per cage) as custom rules; multi-renban lines
  refused.
  Shifter lines and shifter dots (parity and polarity rules) as custom rules; edge dots of a colour no reading takes
  are refused instead of dropped.
  f-puzzles circles with a meaning in the text: anti-quadruples (a pink circle under a quadruple), quadruple digits in
  the circle, pair sums ("cells connected by a pink circle must sum to 11"), decorative circles, counting circles
  in more wordings.
  Arrows drawn inside one cell point along a ray ("each arrow points to the closest 5", Search Nine, arrow X-sums
  "the sum of the first N digits in the direction of the arrow"). f-puzzles cages: factor cages ("multiply to the
  number in the corner") as custom rules; "x + k" cages with one x for all cages (the totals written when the cage
  sizes force x); cages without a total that the text gives a meaning ("digits in cages do not repeat", a killer's
  blank cages); "the cages with no sum given have the same sum"; "regions" for cages in sums and repeats. Line
  colours: a shade the text calls by a neighbouring word (a pinkish line called purple, a dull orange called brown),
  the one line colour the text does not name taking the one rule it names unseen, "numbers on all other lines";
  colours of cells ("the gray cell with arrows") no longer read as line colours; a neighbouring word never takes the
  rule of a colour that is itself drawn. Branching renban lines drawn in pieces are one line. f-puzzles coloured dots
  and diamonds with their meaning in the text ("green dots: a ratio of 3:1", "orange dots: a difference of 3", "red
  dots are NOT consecutive"); a dot with a choice of meanings is refused. Dots the text redefines as custom rules
  (any operation giving 8, a two-digit square in reading direction, one odd and one even), with their negatives;
  180-degree partners that differ; "in all cases where ... consecutive ..., a circle is placed" is a negative;
  "2-entropic" lines; "cells that are orthogonally adjacent cannot contain consecutive digits"; more quadruple and
  cosmetic-thermometer wordings. Misreads fixed: translucent halos over dots read as white dots, quadruple digits read
  as edge clues, negatives scoped to part of the grid applied everywhere, an "all dots are given" negative for a dot
  colour the text never defines; "all clues are true or all false" is refused.
  2,000 most-solved Logic Masters sudokus: 802 -> 912 graded.
- Export keeps SudokuPad thermometers and whispers as `line` rules (they were written as chains of `greater` edges /
  `less` relations and pair rules, with the line's colour on one pair only), and a board-sized background fill as a
  `decorations` rect (section 7). Grades unchanged on the gate; a few line-heavy LMD puzzles grade a band easier now
  that the engine sees the whole line.
- The engine params cache follows in-place changes to the grader model's route / price settings: an experiment that
  switches a parameter between two `rate` calls in one process now gets the new route params for the second (both
  arms used to run on the first arm's route params; only pricing changed).
- Colouring (the identity layer) behind the route parameter `colouring` (0 = off, the default for now; grades
  unchanged): cells known to hold one unknown digit are kept as a colour class even when no candidate goes (Same
  Colour joins), with Colour Single (a class's only place in a house) and Colour Fill (a member loses a digit / is
  placed -> all members). First increment of docs/research/identity_layer_v2_proposal.md; not yet adopted (accuracy
  test pending). Increment 2: class steps that place or eliminate nothing are free unless a later step uses the class;
  two-colour classes (Colour Pair: two cells with the same two candidates that differ start a pair; Colour Trap: a
  cell seeing both colours loses both digits).
- SudokuPad links of the form `sudokupad.app/<author>/<slug>` are fetched (they were refused as not a short id).
- Speed and robustness: the C++ uniqueness search without OR-Tools stops at a time limit, not only a node limit
  (counting-circle puzzles ran for hours); the trial step retries with a larger search before giving up (two unique
  killers ended Unknown) and keeps its result per position (one killer: 558 -> 316 s); a custom rule with a `neighbours`
  scope shares one digit table per neighbour count unless it reads positions (9x9: 15.6 -> 0.5 s to load).
- Docs: the `verify` extra (OR-Tools) is recommended for variants; the benchmark page lists Cracking the Cryptic solve
  times as an outside check (327 puzzles, rank correlation 0.57).

- Regions to find (chaos construction; format: `"type": "chaos"`, `region_border`, `same_region`;
  docs/formats/rules/houses-and-regions.mdx 6.3): a grid whose D connected regions of D cells the solver finds, given
  borders between neighbours, and cells known to share a region. Readers, writers, `fingerprint` and `describe`
  handle them; `solve` and `count_solutions` check them: the engine's exhaustive search carries a region label per
  cell (D cells per label, each digit once per label, connected, canonical labels), agreeing with a CP-SAT model of
  the same rules on 699 of 699 random small puzzles. The grader grades them: the solver keeps a region label per
  cell between steps, and two region techniques are in (region exclusion: a digit leaves the other cells of its
  region and equal digits split regions; region size cap: a region with all its cells is closed, the cells left for
  it take it), plus region cannot reach (cells beyond a region's remaining cells, or in a pocket too small for a
  region), dead end (a cell shares its region with a neighbour) and region exit (a region short of cells with one
  way out takes it), region needs a digit (a missing digit with one reachable place) and pocket counting (a pocket
  too small for a region of its own joins the one unfinished region around it); more from the Cracking the Cryptic
  solves come next, so the routes still lean on the search
  fallback where those would apply (CC Newbie: Extreme, with one trial step). Prices are provisional until calibration.
  Card steps show the region effects: `region` (`"r4c5@3"`) and `region_eliminations` (`["r4c5@!3"]`). The SudokuPad reader reads chaos construction
  when the rules say so and the file draws no regions: drawn borders become `region_border`, and statements such as
  "digits along a thermometer belong to the same region" become `same_region` / `region_border` for that element
  kind. Of the 467 cached logic-masters chaos puzzles most are still refused or have another solution: they add
  rules of their own that read the regions (run sums, counting views), which format_version 1 cannot state.
- Reader fixes from the 500 most-solved logic-masters sudokus (6 more read and graded, 123; each now unique and
  matching its embedded solution; none lost): SudokuPad's newer files write a dot's fill as `c2` and
  greys as one digit (`#F` white, `#0` black), so white dots no longer read as black; a "same parity" line (all odd
  or all even), which has no rule family, becomes a custom rule instead of an alternating parity line; grey
  thermometers beside grey palindromes are told apart by the bulb in the line's colour; "all X and V are given" on a
  grid without any forbids sums of 5 and 10; f-puzzles: "all Vs are given; not all Xs are given" forbids unmarked V
  pairs only (it also forbade sums of 10). Quadruples written as "Quads: ..." or "a digit in a circle must appear in
  one of the four cells the circle touches" are read (2 more, 125); a quadruple whose clue holds letters for the
  solver to find is refused (the letters were dropped). A line whose colour the rules do not name takes SudokuPad's
  default meaning for that colour only when the rules describe that meaning ("consecutive" for a pink renban, "differ
  by 5 or more" for a green whisper): a rule the engine does not know, drawn cyan, read as a region sum. On 1,500
  random cached SudokuPad puzzles this refuses 32 readings, all misread (no solution or several), and keeps every
  reading that was right; on the top 500, 3 misreads refused, none graded lost. A SudokuPad region covering the whole
  grid means no boxes (it read as one region of every cell, which has no solution). Text inside a cell away from its
  centre (a corner clue such as a run sum, a maze marker) is refused instead of dropped: no reading handles it. On
  1,500 random cached SudokuPad puzzles this refuses 19 misread puzzles and 1 read right (lines labelled "GW" / "RN"
  in their cells); on the top 500, 22 misread path puzzles, none graded lost.
- `describe` no longer searches for the solution of a puzzle it is given as anything but a pencilmark-puzzle file: it read
  the rules through `to_export`, which solves to add the solution (a hard Latin square took minutes; now 17 ms).
- Readers refuse puzzles whose rules define a mechanic the engine does not model, instead of reading its elements as
  something else: equality and EquaLite cages, look-and-say cages, Rellik cages, counting cages (all read as killer
  cages before), congruent boxes, anti-camel, pointer arrows and thermos, index lines and indexers, cold and hot
  arrows, pairrows, region-sum screws and diagonal kropki dots. The f-puzzles reader now checks the rules text for
  these and for the words the SudokuPad reader already refused (clones, modifiers, ...). On the 500 most-solved
  logic-masters sudokus: 21 misread puzzles (no solution or several) are now refused with the mechanic named; every
  puzzle graded before still grades. A named mechanic counts only when the rules define it ("equality cages: ..."),
  not when a page lists the author's other series.
- Generator: with publishing checks (`quality` in the request), a found puzzle's checks and its full card are one grading
  instead of two (a checked card has the same difficulty, time, band and contents: 138 of 138 development puzzles).
  The same results, faster: the nine-variants example 135 s -> 121 s.
- Logging: pencilmark writes to the standard Python logger `pencilmark` (silent until switched on): pages fetched,
  what a reader read from a link and the readings it inferred, time limits reached and the generator's result at
  INFO; stage timings, uniqueness checks, each generator attempt and why it was rejected, and the meaning a reader
  gave each line colour at DEBUG. Every command takes `--log info` or `--log debug` (to standard error, also from
  `-j` workers). `pencilmark.gen.api.generate` no longer takes a `log=` callback (its attempts are now DEBUG
  records); `pencilmark.generate` never had one.
- Custom rules (format: `"type": "custom"`, no longer reserved; docs/formats/rules/custom.mdx): a rule written in the
  file as an expression over named cells, `{"type": "custom", "cells": {"c": [...]}, "holds": "2 * max(c) == sum(c)"}`,
  with scopes for every pair of neighbours, every h x w window or every cell with its neighbours, and `each` for a list
  of cell tuples. Readers parse and type-check the expression and name the problem; writers keep the rule, the
  expression in its canonical spelling (also what `fingerprint` reads); `describe` renders it in words. pencilmark
  grades custom rules through its generic rule reading: a rule over up to 5 cells as a table of the digit
  combinations it allows, a larger one through an evaluator of the expression in the C++ engine (tested against the
  Python reference). Grammar validated on 1,000 logic-masters puzzles (docs/research in the source repository).
- Difficulty: the search-effort part of the card counts a refutation's length in propagation rounds (all singles of a
  round placed together) instead of single placements, so a puzzle and its transpose or relabelling grade the same
  (98% identical on 786 development puzzles transposed, was 67%; the largest move 0.6, was 1.1). Its weight and the
  score map are refitted (Andrew Stuart's ratings: fed MAE 0.505, was 0.508; hard set 0.82, was 1.03); ranking against
  human data is unchanged to slightly better (development set: fed +0.02, logic-masters +0.01, sudoku.today -0.01).
  Difficulty values change (easy puzzles a little higher, hard ones a little lower; bands are unchanged), and the
  `unusual` ranges and the typical-difficulty table are recomputed on the new scale.
- A generator request without `where.band` or `where.difficulty` keeps the broadest search and says so: the result's
  `info.warnings` (and a failure message) suggests a band or difficulty range, since the untargeted search uses every
  technique up to Extreme and can be slow on sparse variants. The command line prints it as a note.
- SudokuPad reading: "equal digits must not touch diagonally" and "no touch" are read as anti-king, and a mostly
  transparent black (`#0003`) counts as grey, so rules such as "digits in grey cells are odd" find their cells. Found
  on the 500 most-solved logic-masters sudokus (2 more of them read and graded). A kropki dot drawn without a colour
  is white when the rules mention only white dots (it read as black: 2 more). f-puzzles: numbers written as text
  outside the grid are read as the one outside clue family the rules name (sandwich, x-sum or skyscraper: 1 more).
  "The sum of the digits between 1 and 9" names sandwich clues (the wording wanted "the 1": 1 more).
- Format docs: the `count` rule's restriction is that an `each` / `counts` rule's cells must not also form a house; it
  read as if no counted cell could be in any house, which would forbid counting circles on a normal grid.
- The generator places every line kind the engine grades: besides thermo, whisper, renban and between, now slow
  thermo, entropic, modular, parity, palindrome, zipper, region-sum, lockout and double-arrow lines, each true in the
  solution with the format's default parameters. Entropic lines need a board of 6 x 6 or more; palindromes and zippers
  have an odd length; double arrows are 5 cells or more (a shorter one is a zipper).
- Generator requests may lock a `neighbours` rule with any `op` and `where` too (for example no two orthogonal
  neighbours summing to 10); the result writes it in canonical form (there: the `negative` rule of X marks).
- Generator requests may lock `{"type": "neighbours", "kind": "nonconsecutive"}`: every result's grid has no
  consecutive orthogonal neighbours (the grid fill respects pair rules, not only rules of different digits). Without a
  band target the result is very hard (few givens); a band target keeps it in range.
- The generator places corner clues: quadruples (`{"type": "contains", "count": ...}`, all four digits or three) and
  mathrax clues (`{"type": "corner", "kind": "mathrax", "count": ...}`, whichever operator holds on both diagonals).
- The generator places outside clues on single grids: sandwich, x-sum and skyscraper clues on a row or column, little
  killer clues on a diagonal (`{"type": "sandwich" | "xsum" | "skyscraper", "count": ...}`,
  `{"type": "sum", "kind": "little_killer", "count": ...}`), read from either end.
- The generator keeps to `limits.time` while trying elements to restore a removed given and while pruning: one attempt
  on a 9 x 9 with entropic lines ran 40 s past a 180 s limit.
- `to_export` uses a solution the puzzle already carries (`rate()` and the generator set it) instead of searching again,
  and leaves the solution out when the search ends without a verdict: the generator crashed with `Undecided` on a
  samurai without OR-Tools (found by the generator fuzzer).

## 1.1.0 (2026-11-01)

- The generator's card is the card `rate()` gives the puzzle it returns. A butterfly killer's said 7.9 where `rate()`
  said 8.9: the search-effort part of the card ran a capped search when no solution was at hand and counted 0 when
  it gave up (it now uses the uniqueness search), and multi-grid layouts numbered their cells grid by grid inside the
  generator but row by row when read back.
- Faster cards on long renbans and other all-different rules, same cards: combining rules with houses asks at every
  step of its search whether a rule can still be met, and answers it with a matching search instead of counting
  every assignment (the long-lines example: 26 s to 6 s).
- Faster uniqueness proofs with OR-Tools installed: the engine's search gets a short budget, then CP-SAT (a sparse
  killer on a 12x12 butterfly: 27 s to 0.4 s). Classic puzzles still never reach CP-SAT.
- Malformed generator requests get a format error, not a crash: a `quality` that is not an object, a `box_grid`
  without an `origin` cell, a rule `kind` that is not a string, or `fields` holding something other than names
  (`rate(fields=...)` too, as a ValueError). Found by mutating requests.

- New publishing check `unusual` (reject): a difficulty outside the middle 80% of published puzzles of the same band,
  classic 9x9 and variants apart, Very Easy without a floor and Extreme without a ceiling (ranges measured on the
  development set, 6,452 puzzles from seven sources).
- Generator requests take `quality` (recommended; it was reserved): candidates are filtered by the grade card's
  publishing checks, a candidate with a reject issue is not returned, and `info.rejected` counts the ones refused by
  check. `"quality": {}` applies the defaults; an object adjusts each check as `rate(quality=...)` does. Without it,
  nothing is filtered.
- The generator makes multi-grid puzzles: a request with one `box_grid` per grid at the origins of a named layout
  (samurai, super-samurai, twodoku, butterfly, ...). Requests may lock rules of different digits (diagonals, extra
  regions, windoku windows, anti-knight, anti-king) that every result carries, and bound the givens per grid
  (`givens.grids`). A layout without a band target is generated up to Hard.
- Generated elements of different kinds may share cells (a whisper through a cage, a dot on a thermo), so the rules
  interact; dots and XV marks may share cells. Before, no two elements shared a cell.
- `"count": "tile"` covers the cells that are not givens; a cell left alone becomes a given instead of a 1-cell cage.
- The inequality edge is `"kind": "greater"`, `cells[0] > cells[1]`, after the variant's name (Greater-Than); it was
  `"less"` with the cells the other way round. Files with `"less"` are refused: swap the two cells and rename the
  kind. The `less` / `less_equal` operators of `relation` rules are unchanged.
- SudokuPad files read that crashed the reader (5 of 19,194 stored puzzles): a colour typed without "#" stored as a
  number, an all-digit solution stored as a number, and null entries in element lists or in a cage's cells.
- Chains held in the head (mental chains) are explained when they pass through a group of cells (they crashed into
  the generic sentence), and only with a chain that visibly closes: the engine's record can stop short of the step
  that comes back to the placement, and the text then claimed a return it did not show. A chain that stops short is
  completed by the explainer's own search, or its closing clash is stated ("But r4c7 = 9 and r2c6 = 9 can't both
  hold").
- A malformed SudokuPad, f-puzzles or penpa payload is a `DecodeError` saying so ("malformed f-puzzles data (KeyError:
  'cells')"); a missing key or a value of the wrong type raised KeyError, TypeError, AttributeError or IndexError from
  the translator (over half of 3,000 mutated f-puzzles payloads).
- The generator keeps to `limits.time`: an attempt still digging when the time is up is given up (a 2 s request on a
  thermo puzzle ran 130 s). The returned puzzle's card is graded in full; it was capped at `grade_seconds` and could
  come back with band Unknown and no difficulty.
- A generator request with a part of the wrong type (`where`, `limits`, `meta`, `rules` or `symmetry` not an object /
  list, a count, size or given count that is not a whole number, a template kind that is not a string) is a format
  error; several raised TypeError or AttributeError (found by mutating requests).
- Malformed files get a format error, not a crash: a rule `type` or `kind` that is not a string, a `meta` that is not
  an object (validate accepted it and `load` failed) and `true` in a solution (found by mutating valid files).
- Chains through a group of cells are explained when the group ends the chain too (they fell back to a generic
  sentence: "one of r2c5, r8c5 is 9" now states that end), and grouped chains are named as their step (Grouped
  X-Chain, Empty Rectangle) instead of "Alternating Inference Chain" (6 steps in the private corpus).
- Generator spec: templates take shape limits, `size` and `sum` for cages and `length` for lines and arrows (a number
  or `[min, max]`); a template's count may be `"max"` (as many as fit), and `where.difficulty` may be `"max"` or
  `"min"` (the hardest or easiest puzzle found). These searches use the whole `limits.time` and return the best
  result. Long lines are grown by a backtracking walk, so a request for a 15-cell whisper finds one.
- Vudoku is drawn as a grey right-angle corner, elbow in the vertex cell, arms reaching into the arm
  cells (it was a thin V through the cell centres). The docs' examples use the L of three cells the rule is played on.
- Explanations of chains through a group of cells (grouped AIC, Grouped X-Chain, Empty Rectangle) name the group:
  they described it as "an almost locked set", which the step does not contain (43 steps in the golden corpora).
- Region-sum lines split only at box borders. An extra region overlapping a box split a line inside that box,
  adding a sum equality the rule does not state.
- The generator's renban lines are lines: a cell next to the line's first cell was added at its end, so some
  generated renbans had cells that do not touch and the returned file failed to read. `generate` now validates what it
  returns.
- `rate_many` takes `alternatives` like `rate` (no fast batch mode from Python before).
- The command line reports a missing file, a spec that is not JSON or cannot be met, and format errors in one line
  with exit status 1 (it printed a traceback).
- `se` is null for anything but classic 9×9 sudoku. Variants got numbers on a scale defined only for classics, often
  the 7.0 fallback.
- An unknown `mode` (for example `"Computer"`) is an error; it used to grade silently in human mode.
- Lockout lines imported from SudokuPad or f-puzzles are written back too (the readers built digit tables directly,
  so `to_export` and `fingerprint` failed on those puzzles).
- Stricter reading: a mathrax clue no two digits can make (`+` 30) and entropic `groups` that are not three groups
  splitting 1..D are format errors (they passed and failed later with an engine message). One group may be empty:
  sudoku.coach's fixed thirds on a 4×4 ({1,2,3}, {4}, {}) now read and write back (they never matched before).
- Lockout lines can be written back: `to_export`, `fingerprint` and the canonical text failed on any puzzle with one
  (NotSupportedError). The lockout is now an engine line kind compiled to the same relation and digit tables. Its
  rule text states its own value (it always said 4).
- Explanations name Turbot Fish and Remote Pair as the techniques are named elsewhere (they read "Turbot fish",
  "Remote pair").
- `load({})` (or a dict holding only a title) raised nothing and read an empty 9×9 board; it is now refused like any
  dict that is not a puzzle.
- Two dead technique links fixed: Multi-Colouring's SudokuWiki page (in its explanation) and Simple Colouring's
  KrazyDad page (techniques page).
- Generator specs accept the `odd` and `even` cell templates SPEC.md documents (only an undocumented `parity` worked);
  `parity` (odd or even cells, either kind) is now documented too.
- `se`: a technique Sudoku Explainer has no value for takes the value of the technique it is a special case of
  (Simple Colouring and Multi-Colouring rate as X-Chain, 6.6, instead of the 7.0 fallback). The DiufSudoku scale is
  gone from the code and data as well (the card field went in 1.0.0); `se.scale` is always `"classic"`.
- Step explanations use the engine's own record of each move (units, cages, chains, the cases tried): digit counting,
  killer cage combinations and others now show their reasoning instead of a general description (about 390 -> 56 such
  steps in the test corpora); set-logic explanations name units as "row 4" or "the 25 cage", and a refuted case reads
  "suppose r4c3 is 7 ...".
- Numbered edge clues are checked: a `difference`, `sum`, `product` or `ratio` that no two different digits 1..D make
  (ratio 1, a sum of 40 on 4x4) is refused when the file is read; it used to fail only when the puzzle was written back.
- The chip for facts read off the clues alone is named "Clue Facts" (was "Clue facts (no 5 on a whisper)", an example
  that also showed on puzzles without whispers).
- A closed renban is written back closed (it was written open). Its `fingerprint` now covers `closed`, as the
  canonical form does, so a closed renban's fingerprint differs from the same line open.
- A line's `value` is checked: whisper and lockout take 1..D−1 (a difference between digits), modular a modulus of at
  least 2. A whisper of 5 on a 4x4 board was accepted and made the puzzle unsolvable.
- Error messages for `cell` rules name the rule type (`cell low takes split ...`, was `digits low ...`).
- The technique list (`contains`) no longer loops forever on puzzles that need the forcing fallback, such as Easter
  Monster: a technique already removed could come back through the fallback, and was "removed" again on every pass.
  Easter Monster's default card now takes about 30 s.
- Faster grading, same cards: the engine caches what each technique finds at a position across a card's many
  routes, single-digit techniques per digit, and the costliest late techniques are listed only when they could still
  win, and case analysis follows each assumption once (a 16x16 classic card: about 300 s -> 23 s).
- `pencilmark.load` reads JSON text that holds a link (every ipuz text does, in its `version`; a pencilmark-puzzle with
  a source URL in `meta`). It tried the text as a puzzle link first and failed with "not a puzzle link".
- `pencilmark.to_export("puzzle.json")` keeps the file's `meta` (title, source, ...), as it already did for a dict
  or JSON text. One reader (`pencilmark/inputs.py`) now serves `load`, `to_export` and the command line, so a link
  followed by a comment, or a text grid, reads the same everywhere.
- Step explanations: when an explanation falls back to the technique's general description, it no longer repeats
  the name ("Cage combinations Cage combinations pattern removes ..." -> "Cage combinations removes ...").
- Package data: `price_params.json` is folded into `card_score.json` (`price_weights`, the only two weight vectors
  that differed from `params.json`); `tiers.json` and `card_calibration.json` are gone, with the legacy code that read
  them. All fitted parameters load once through one internal grader model. Cards are unchanged.
- When the difficulty route cannot grade a puzzle, `difficulty` and `time` are null. `time` fell back to an older
  formula that skipped the minutes conversion (about 0.35 for a typical puzzle), and `difficulty` to a retired
  calibration.
- `dumps` (canonical form) writes `board` as `rows`, then `cols`, whatever order the input used; the canonical text
  of one puzzle could differ by that order.
- `pencilmark.count_solutions(puzzle, limit=1000)` and `pencilmark count FILE`: how many solutions a puzzle has (`>=N`
  when counting stops at the limit).
- `pencilmark generate SPEC`: the generator on the command line (`--seed`, `--time`, `--result`).
- Step explanations: Clue facts, Clue shape and low / high and odd / even colouring have their own explanations;
  they read "ClueFacts (code 10102) pattern removes ...". Explanations of the band route now get the engine's pattern
  cells, so "Two rules together" names its cells (it said "over their 0 open cells") and no-notes steps list the cells
  they use (they said "(cells )"). Only explanation texts change (12 of 55 public and 101 of 227 private golden cards).
- `issues`: steps that read a line or rule through the engine's rule reasoning are credited to that rule. They were
  credited to no rule family, so a thermometer, skyscraper or other line clue the solve used throughout could be
  reported as `barely_used` ("used in only 0 steps") and the card rejected. On the golden corpora 3 of 282 cards lose a
  false reject and 13 change a usage count in an issue text; nothing else on the card changes.
- An ipuz sudoku (a dict, or a `.ipuz` / `.json` file on the command line) is read like `from_ipuz`. It was taken
  for internal puzzle JSON with no grid and reported "not unique".
  Any other dict with keys pencilmark does not know is refused ("not a puzzle pencilmark reads: unknown keys [...]")
  instead of being read as an empty grid.
- `rate`, `solve`, `describe`, `fingerprint`, `to_export`, `load` and every command-line command accept a puzzle link
  or payload directly (SudokuPad, f-puzzles, Penpa, Logic Masters, short links: what `pencilmark.sources.load`
  reads). A link was read as a grid of digits and failed with "the grid has 490 symbols". An unrecognised link says so.
  `to_export(link)` keeps the title and source the link carries.
- Generator: the same spec and seed now give the same puzzle in every process. With variant templates the order of
  candidate elements depended on Python's string hashing, so a seed gave a different puzzle from run to run (classics
  were not affected). Variant puzzles for a given seed differ from 1.0.0. A last check also refuses a result whose
  givens fall outside the spec's count.
- `pencilmark.GenerationFailed` is exported, so a failed `generate` can be caught without importing
  `pencilmark.gen`.
- Command line: an input that cannot be read (bad JSON, a format error) is reported on its line as
  `error<TAB>line<TAB>message` and the next input goes on, in every command; `rate`, `solve`, `json`, `fingerprint` and
  `describe` stopped with a traceback. A FILE ending in `.json` that holds one JSON value (a pretty-printed puzzle file,
  or a list of puzzles) is read whole; it was read line by line and failed. A grid with the wrong number of symbols
  says "the grid has 3 symbols; expected 81" (it said "numbers has 3 symbols; expected 81 or 81"). Output piped into
  a reader that stops early (`| head`) ends quietly instead of with a BrokenPipeError traceback.
- `se` (Sudoku Explainer-style rating): every card's ER was 7.0. The rating table was keyed by codes the route never
  gives its steps (XYW, UR1, JFH, XCH, FSH, NET instead of YWG, URC, JLF, XCL, FXW / FSW / FJF, FNT) and lacked the
  full house, so a full house, Y-Wing, Unique Rectangle, Jellyfish, X-Chain, finned fish or forcing net counted as
  "SE has no such technique" (7.0). They now get SE's values (full house as a hidden single, 1.2). Only `se` changes.
- `data/technique_bands.csv` is replaced by the technique registry: `data/techniques.csv` (one row per engine
  technique), `data/codes.csv` (one row per chip code) and `data/patterns.csv` (engine pattern codes), described in
  `pencilmark/registry.py`. Every module reads its technique tables from there. The old file gave X-Chain as Very Hard
  while the grader rates the technique Hard; the registry keeps the technique (Hard, short shapes) apart from the long
  X-Chain chip XCL (Very Hard). Cards are unchanged.
- Class colouring and clue facts (two variant techniques) record their move descriptors in the right slots (cells,
  houses used, digits eliminated, links); the descriptors were shifted, which mispriced those steps. Cards with these
  steps move slightly: time by about 0.1 minutes on typical kropki / XV / thermo puzzles, difficulty by a median 0.01.
- Faster cards: the C++ puzzle is built once per card instead of about six times (classics 25-50% faster).

## 1.0.0

First stable release: the `pencilmark-puzzle`, `pencilmark-grade` and `pencilmark-spec` formats are format_version 1, and the card's
meaning is set out in docs/PHILOSOPHY.md. Changes since 1.0.0rc2:

- Grade card simplified (one meaning per key, docs/PHILOSOPHY.md): `contains_complete` removed (it was band != Unknown;
  `stopped_at_step` still marks where human logic ran out); `time_dist.median` removed (it repeated `time`); steps use
  the same keys as `contains` (`code`, `name`, `band`; `technique` renamed `name`); `alternatives` is `null` when the
  search was skipped (`alternatives=False`) and omitted only when there are none.
- More text formats: text grids with separators (Simple Sudoku / SadMan / forum style; `to_string(puzzle, "grid")`
  writes them), a trailing `# comment` after a plain string, pencil-mark grids and 729-character candidate strings
  (Sukaku). `rate()` and every entry point accept them as one string.
- ipuz import: `from_ipuz` reads ipuz 1 / 2 sudoku (boxes, jigsaw zones, diagonals, windows, cages); `to_ipuz` now refuses
  given candidates instead of dropping them.
- `max_seconds` is now also checked inside the forcing-chain fallback (Easter Monster at `max_seconds=2` returned after
  4.3 s, now 2.0 s); grades without a limit are unchanged.
- Windows / macOS: `pencilmark rate -j N` hung under the spawn start method (the workers looked for their function in
  pencilmark's `__main__`, which spawn does not re-import); it now passes them from the importable module and reads all
  input first and reads / writes UTF-8 on every platform; the test suite runs on Windows and macOS too.
- HoDoKu library lines (`:0901:4:<puzzle>:<removed candidates>:...`) are read by `from_string`.
- `band_index` is no longer a default field (ask for it with `fields=[...]`); `se_diuf` removed (`se` gives the classic
  Sudoku Explainer scale).
- Rules keep the file's order: `to_export` writes a puzzle file's rules back in the order given, with their `id`, `label`
  and `style` (it used to reorder them and drop those keys), and `issues` count rules in the graded file (`rules`), plus
  their `ids` where present.
- Quality checks: every entry of `quality` is an object, `{"limit": n, "severity": "reject" | "warning" | "off"}`
  (CLI `--quality trivial.limit=0.5,trial.severity=reject`), so a check's severity can be changed as well as its limit;
  bare numbers and `true` / `false` are no longer accepted. New optional field `warning` (true when any issue is a
  warning), next to `reject`.
- Format: `ext` removed; data for one program goes in `meta` under a reverse-DNS key, next to the suggested common keys
  (the generator's own knobs too). Reserved items (`"type": "custom"`, `digits` as an object) are refused with a
  message naming them as future work. `neighbours` kinds are documented as exact shortcuts for an operator on a pair
  pattern.
- Pair operators take their parameter under its own key, as the rest of the format: `{"op": "difference", "value": 3}`,
  `{"op": "sum", "sum": 10}`, `any_of` a list of objects; positional `params` lists are refused. Writing an
  `any_of` relation back no longer crashes.
- `"type": "table"` and the `allowed` operator are reserved: explicit digit tables made files large and could not be
  drawn; a custom rule type is planned to replace them. Mechanics without a rule family cannot be written in
  format_version 1. The Rossini test puzzle now uses `rossini` rules and `negative` instead of edges and tables.
- Generator: one vocabulary. `pencilmark.generate(spec)` (also `pencilmark.gen.generate`) takes a `pencilmark-spec` request and
  returns a `pencilmark-puzzle` (with `meta.generated_from`), honouring the spec's `fields`; the internal Spec dicts
  (`target_band`, `max_givens`, ...) and `spec_from_gen` / `spec_to_gen` are no longer public. `SPEC.md` version 1
  describes exactly what the generator runs; the rest is listed as reserved and refused with a message naming it.
  Example specs that use reserved parts moved to `docs/examples/specs/reserved/`.
- **Seven bands**: Very Easy (scanning: full house, hidden singles) / Easy (naked singles, pointing / claiming, one rule's
  combinations) / Medium (pairs, triples, quads; variant implications) / Hard (the first learned patterns: X-Wing,
  Skyscraper, 2-String Kite, Turbot Fish, simple colouring) / Very Hard (Empty Rectangle, finned and larger fish, wings,
  uniqueness) / **Expert** (new: XY-Chain, AIC, Medusa, ALS) / Extreme (forcing, trial). The steps common curricula
  take (docs/PHILOSOPHY.md). `band_index` runs 0..6. Difficulty and time are unchanged
  (all 7,427 graded puzzles of the frozen benchmark identical).
- Step explanations at three levels: `notation` (the solvers' shared form, `X-Wing: 3 r58 c68 => r679c6<>3`), `short`,
  `teach`; `pencilmark rate --report -v / -vv / -vvv` lists the steps at those levels. The report shows time percentiles
  only when asked for (`--fields ...,time_p80`) and names alternatives in full.
- Singles never carry `uses`; alternatives inside a chip are ordered deterministically (the order depended on Python's
  per-process hashing); `max_seconds` also checked in the generalised fish search.
- Difficulty below 2: the score map turns gentler there (about the square root of effort, the same value and slope at 2)
  instead of bending into 0, so very easy puzzles keep apart (an easy 4x4 about 0.1-0.4, a nearly finished grid about
  0.2; most used to read 0.0). Scores of 2 and above, every ranking and every time are unchanged.
- Docs: philosophy page (goals, exact meaning of band / difficulty / time, format rules); README known issues.

## 1.0.0rc2

- `max_seconds` bounds the whole `rate()` call (uniqueness proof, card, technique list). The band and difficulty route
  runs first, the technique list in the time left. If the limit passes in the route, the card says band `Unknown` with
  `difficulty` / `time` null and the techniques found so far; if uniqueness is not proven in time, `rate` raises
  `Undecided`. New `completed` field whenever `max_seconds` is set.
- `contains_truncated` removed: `completed: false` already says the limit passed (when it passed only while the technique
  list was being minimised, the grade stands and the list may not be minimal).
- Optional `elapsed` field (wall-clock seconds for the call); `solve(puzzle, info=True)` returns the solution with its
  seconds; the generator's `info` has `seconds` and `attempts`.
- Optional `time_dist` field (`{"type": "lognormal", "median", "sigma_players", "sigma_model"}`); `time_p50` accepted.
- Three variant techniques from how people solve on video: clue facts (`CFX`, Very Easy: what a clue rules out on an
  empty grid, e.g. no 5 on a whisper), clue shape (`CSH`, Easy: a line's shape inside one house, e.g. a whisper 4
  between two 9s) and high/low & odd/even colouring (`CCL`, Medium). Accuracy on human data is unchanged on average
  (kropki ranks better); solving routes are shorter and closer to human ones.
- Time spread: `time_mean` and any percentile `time_pNN` (e.g. `time_p20`, `time_p80`) on request, over today's players
  (log-normal; sigma 0.79 for classics and multi-grid layouts, 0.62 with any other rule, from two sources' per-player times). `time_p80` was a one-player spread (1.53x) and is now
  the population one (about 1.85x). `time` is the median player.
- Generator: element varieties (kropki colour, XV letter, odd/even) with counts, ranges and caps; the information-budget
  check uses per-class maximums.
- `spike` check: a Medium+ puzzle whose 3 hardest steps carry more than 60% of its effort (adjustable, `quality`), as a
  warning; replaces the old "few band moves in an all-singles solve" rule.
- Cards without `contains` / `issues` skip the technique-list search: about 3x faster for the same band, difficulty and
  time; the generator screens candidates this way.
- `alternatives=False` / `--no-alternatives`: skip the search for interchangeable techniques (faster; band, difficulty and
  time unchanged). The generator screens candidates this way.
- Faster cards: the search-effort profile stops trials past the shortest refutation and skips unchanged rules; the
  solution is found once per card.
- Publishing checks (`issues`, `reject`) are no longer default card fields; ask for them with `fields=[...]`.
- Docs: the puzzle format (`FORMAT.md`), grade card (`GRADE.md`) and generator spec (`SPEC.md`) are separate
  documents, each saying how to implement a subset; drawing conventions moved out of the format into `STYLE.md`, variant
  naming into `NAMING.md`.
- Drawing: `docs/palette.json` with the default sizes, light and dark themes and the community line colours; reference
  SVG renderer `tools/render_svg.py`.

## 1.0.0rc1

First public release.

- `rate`, `rate_many`, `solve`, `to_export`, `load`: the "pencilmark-grade" card (difficulty, time, band, contents, issues /
  reject; on request time_p80, steps with two explanation levels, Sudoku Explainer-style ratings, describe, symmetry;
  `fields=[...]` computes only the requested fields) for classic and variant sudoku.
- Publishing checks (`issues`) with adjustable limits: `quality={"trivial": 0.5, "trial": False}` / `--quality`, the same
  object the generator spec's `quality` takes.
- Command line: `pencilmark rate | solve | json | export | fingerprint | describe` (also `python -m pencilmark`).
- Exchange format: `pencilmark-puzzle` format_version 1, read and written, specified in `docs/FORMAT.md` with a JSON Schema (`docs/pencilmark-puzzle.schema.json`):
  every constraint is a rule (houses as `grid` / `box_grid` / `box`, explicit `row` / `column` for bent ones; nothing
  implied), cells named `r1c1`, a rule
  vocabulary of families and kinds with exact semantics and default drawings, outside clues anchored by `side`,
  explicit `negative` rules, strict reading (unknown keys or rule types are refused).
- `pencilmark-spec` generator requests (givens, locked rules and templates, symmetry, `where` card targets, quality,
  limits); `spec_to_gen` runs what the generator supports and refuses the rest with the reason; showcase specs in
  `docs/examples/specs/`.
- Format functions: `dumps` (canonical text), `fingerprint` (content hash), `validate`, `describe` / `rules_text` (variant
  name and rules from a registry of placement variants and rule families), optional `to_ipuz`, `from_string` / `to_string`
  (plain and sudokuwiki.org strings), `spec_from_gen` / `spec_to_gen` (the `pencilmark-spec` generator request).
- Cards carry `"format_version": 1` and `"grader": {"name": "pencilmark", "version": ...}`.
- One engine form per mechanic: renban / between / zipper / region-sum constraints as lines, jigsaw pieces as boxes,
  numbered pair clues (difference / sum / product / ratio, mathrax) as 2-cell tables, duplicated houses merged, global entropy and quadruple clues as named rules for
  every importer (docs/ENGINE.md).
- Puzzle generator (`pencilmark.gen`) with band, difficulty, technique and rule-element targets.
- Puzzle importers (`pencilmark.sources`) for SudokuPad, f-puzzles, penpa-edit and Logic Masters links.
- C++ engine built with pybind11; OR-Tools is optional (`pencilmark[verify]`).
- No guessing by default: where no technique applies, the engine proves an elimination by full search (Trial and error,
  band Extreme), so every uniquely solvable puzzle gets a band; `allow_guessing=True` / `--allow-guessing` guesses there
  instead (band Unknown).
- Bands: forcing chains / nets, Nishio, pattern overlay and trial and error are Extreme; bounded case splits (either
  way, what if, short trial) and ALS chains / Death Blossom are Very Hard.
