# Changelog

## Unreleased

- Format docs: the `count` rule's restriction is that an `each` / `counts` rule's cells must not also form a house; it
  read as if no counted cell could be in any house, which would forbid counting circles on a normal grid.
- The generator places every line kind the engine grades: besides thermo, whisper, renban and between, now slow
  thermo, entropic, modular, parity, palindrome, zipper, region-sum, lockout and double-arrow lines, each true in the
  solution with the format's default parameters. Entropic lines need a board of 6 x 6 or more; palindromes and zippers
  have an odd length; double arrows are 5 cells or more (a shorter one is a zipper).
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
- `pencilmark.load` reads JSON text that holds a link (every ipuz text does, in its `version`; a sudoku-puzzle with
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

First stable release: the `sudoku-puzzle`, `sudoku-grade` and `sudoku-spec` formats are format_version 1, and the card's
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
- Generator: one vocabulary. `pencilmark.generate(spec)` (also `pencilmark.gen.generate`) takes a `sudoku-spec` request and
  returns a `sudoku-puzzle` (with `meta.generated_from`), honouring the spec's `fields`; the internal Spec dicts
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

- `rate`, `rate_many`, `solve`, `to_export`, `load`: the "sudoku-grade" card (difficulty, time, band, contents, issues /
  reject; on request time_p80, steps with two explanation levels, Sudoku Explainer-style ratings, describe, symmetry;
  `fields=[...]` computes only the requested fields) for classic and variant sudoku.
- Publishing checks (`issues`) with adjustable limits: `quality={"trivial": 0.5, "trial": False}` / `--quality`, the same
  object the generator spec's `quality` takes.
- Command line: `pencilmark rate | solve | json | export | fingerprint | describe` (also `python -m pencilmark`).
- Exchange format: `sudoku-puzzle` format_version 1, read and written, specified in `docs/FORMAT.md` with a JSON Schema (`docs/sudoku-puzzle.schema.json`):
  every constraint is a rule (houses as `grid` / `box_grid` / `box`, explicit `row` / `column` for bent ones; nothing
  implied), cells named `r1c1`, a rule
  vocabulary of families and kinds with exact semantics and default drawings, outside clues anchored by `side`,
  explicit `negative` rules, strict reading (unknown keys or rule types are refused).
- `sudoku-spec` generator requests (givens, locked rules and templates, symmetry, `where` card targets, quality,
  limits); `spec_to_gen` runs what the generator supports and refuses the rest with the reason; showcase specs in
  `docs/examples/specs/`.
- Format functions: `dumps` (canonical text), `fingerprint` (content hash), `validate`, `describe` / `rules_text` (variant
  name and rules from a registry of placement variants and rule families), optional `to_ipuz`, `from_string` / `to_string`
  (plain and sudokuwiki.org strings), `spec_from_gen` / `spec_to_gen` (the `sudoku-spec` generator request).
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
