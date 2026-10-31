# Changelog

## Unreleased

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
