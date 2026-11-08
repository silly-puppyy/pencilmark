# Changelog

## Unreleased

### Format (regions to find; still reserved)

- **`region_sight`** (puzzle-format 6.3), the most common rule that reads the regions (setters' circles, cave,
  sightlines, sightline arrows, internal X-sums, arrows): a clue counts the cells of its own region it sees in its
  `directions` (all four by default), sight stopping at the first cell of another region; `self` counts the clue cell
  (default true), `value` gives the count when it is not the clue's digit. Named in the format so a program can say
  which region rules it supports; the engine reads it as custom rules over `region()`.
- **`border_count`** (6.3): a clue counts the region borders between it and the edge of the board in each of its
  `directions` (`total` adds them up); setters' arrows to borders and passport arrows.
- **Region-sum lines on a board with regions to find** are split by the found regions (they were read as one segment,
  which silently dropped the rule); the engine reads them as a rule over `region()`.

### Grading (regions to find; still reserved)

- **Rules that read the regions are reasoned with** (a new technique, *A rule over regions*, RRU): a custom rule
  calling `region()` is read on its own, trying every way of meeting it with the digits and regions its cells can still
  take; digits and regions no way allows are removed. The search asks only for the values the rule reads (a sight line
  stops at its first border), within a budget, and removes nothing when the budget runs out. Before, such rules were
  only checked once every digit and region was known.

- **What a solver draws as borders**: the engine keeps which cells are known to share a region and which are known to
  lie in different regions, before any region is named (seeded by the given borders and same-region sets). A rule
  that only compares regions (`region_sight`, custom rules with `region(a) == region(b)`) is read over partitions, so
  it teaches such facts while every label is open: a sight clue that sees only itself parts from its four neighbors.
- **Region groups** (a new technique, RGP): cells known to share a region form a group; two neighboring groups with
  more cells than a region holds are different regions, a full group is sealed from its neighbors, a group with one
  way out takes it, and equal digits lie in different regions. A lone cell walled in on all sides but one joins its only neighbor;
  a group's placed digits leave its other cells; a group of D cells is a house. Steps record these facts as
  `same_region` / `different_regions` (grade-card section 5) and explain them in words. Connecting the Dots 6x6
  (Skunkworks pack) grades Medium by logic alone (was Extreme with trial).

- **Counting puzzles with regions to find and rules that read them**: CP-SAT now encodes `region()` and `take_while`
  with a lambda (such puzzles used to fall to the C++ search alone, which often could not finish); the C++ search
  prunes on a region rule as soon as its value is settled (a sight line stops at its first other region), and once
  every digit is fixed it stops after the first valid set of regions (solutions count by digits): a fully given
  jigsaw read as chaos went from "undecided" after 16 s to decided at once. The uniqueness check gives CP-SAT up to eight workers on puzzles with regions
  to find or shading (one sight rule: 103 s on one worker, 4.6 s on eight); other puzzles keep one.

### Reading

- **Regions to find in SudokuPad links** (still reserved for grading): more phrasings of the construction are read
  ("divide the grid into nine orthogonally-connected nine-cell regions", "regions are irregular and orthogonally
  connected" with none drawn); "arrows do not cross region borders" and "part of the same region" become
  `same_region`; any other sentence about regions (regions blocking sight, counting borders, region sums or numbers)
  now refuses the puzzle instead of being dropped, which had read such puzzles with several solutions.

## 1.3.0 (2026-11-08)

### Breaking changes (files, specs and code using the old names need the new ones; no aliases)

- **American English throughout** (format and text): the rule type is `neighbors` (was `neighbours`), the custom
  rule scope key `neighbors`, the palette name `gray` (was `grey`), `draw(colors=...)`, technique names
  (Simple Coloring, Multi-Coloring, ...), explanations, rules text and the docs. Names of other sites' pages keep
  their own spelling.

- **The fingerprint follows meaning, not spelling** (puzzle-format.md 8.2, new step 2): pair rules (edge clues,
  `relation`, `neighbors`, their negatives, thermo / slow thermo / whisper / palindrome / parity lines, mathrax) are
  hashed as one table of allowed digit pairs per cell pair, and cell clues (`cell`, corner `exclude`, `negative` of
  `cell`) as one allowed set per cell. A white kropki dot, a `difference` 1 circle and a `relation` `difference` 1 now
  share a fingerprint; so do a V and an edge `sum` 5, a thermometer and a chain of `less`, an `odd` and a `set` cell.
  Every fingerprint with such a rule changes.

- **Renames (one name per thing, US spelling for keys).** No aliases; files and code using the old names need the
  new ones.
  - The quadruple rule is `{"type": "quadruple", ...}` (was `contains`, the community name is quadruple), so
    `contains` now only means the card's technique list and its `where.contains` target.
  - `color` everywhere in keys and values: region kind `color` (was `colour`), card annotations and trace layers
    `color` / `colors` / `center` (were `colour` / `colours` / `centre`), `rate(coloring=True)` and `--coloring`
    (were `colouring`).
  - The card's `contains` and `steps` entries give `band_index` (was `band`, an integer next to the card's band
    name); trace positions give `grid` (was `digits`).
  - `neighbors` takes `step` for its pairs (`"step": "knight"`; was `where`, which also named the spec's targets).
  - `mathrax` uses the pair-operator names of numbered edges: `"op": "sum"` with `sum`, `"difference"` / `"product"` /
    `"ratio"` with `value` (was `+ - x /`, all with `value`).
  - Spec `limits.seconds` (was `limits.time`, which read like the card's minutes); `grade_seconds` and `solver` move
    from `meta["io.github.silly-puppyy.pencilmark"]` into `limits` and are checked like every other key (the meta
    pass-through is gone).
  - `where.contains` has one shape, a list of codes the puzzle needs (each an entry of the card's `contains` with no
    alternative); the `{"codes": [...], "strict": true}` form is gone, and a lenient "an alternative will do" request
    is no longer offered (nothing used it).

- **`quality` means one thing everywhere** (`rate()`, `--quality`, a generator spec): no object = the new
  `"default"` preset (every check that is not opt in, at its own severity; `rate()` only, a spec runs nothing), `{}` =
  no checks, a preset turns on its set, and without a preset only the checks named run. In 1.2 `rate()` treated
  `{"trial": ...}` as "all checks, trial adjusted" while a spec ran only `trial`. Generated puzzles report what the
  checks found in `info.issues` (1.2 dropped warnings).

- **CLI and Python agree on `convert` / `write` defaults**: the solution is opt in (`--solution`, was on unless
  `--no-solution`), output is one rule per line (`--compact` for one line, was the default), and `write.document` /
  `write.pencilmark` take `style=False` like `--no-style` (which now also drops decorations and the top-level style).

- `--steps` is the same as `steps` in `--fields` (it no longer turns on explanations; `--explain` does).

- **Generator publishing checks are opt in.** A request without `quality`, or with `{}` (dropped when a spec is
  written), runs no checks; `{"preset": "standard"}` turns on the standard set; without a preset only the checks named
  run. 1.2 used the standard preset by default and `{}` meant every check at its own severity. The examples and guides
  now ask for the preset explicitly, and the generator spec's top example shows `quality` and both fingerprint keys.

- **Generator metadata on request.** Everything in a spec's `meta` is optional and copied; nothing is filled unless
  asked (1.2 always added a machine title, `type` and `rules_text`). Requests: `title` / `subtitle` templates
  (`{type}`, `{type:list}`, `{variants}`, `{size}`, `{band}`, `{difficulty}`, `{time}`, `{givens}`, `{seed}`), `"type":
  true` or `{"scheme": "name" | "list"}` ("Jigsaw Killer Renban Kropki Sudoku"), `"variants": true` (snake_case ids
  like tags), `"rules_text": true`; `fingerprint` / `generated_from` now take only `true`. `describe()`, the card's
  `describe` field and `write.*(describe=True)` give `variants` too; `subtitle` and `variants` are suggested meta keys.

### New

- **`{"preset": "relaxed"}`** (rate, `--quality preset=relaxed`, generator specs): the standard five checks, but only
  `decorative`, `trivial` and `trial` reject; `thin` and `unusual` warn. On published development puzzles `standard`
  rejects 14% of classics (nearly all `unusual`, which marks the outer fifth of each band by design) and 17% of
  variants; `relaxed` 0.1% and 4%. Generation is rarely held up by the preset: in 11 standard-preset classic runs it refused one candidate.

- **`pencilmark.draw(puzzle)` and `pencilmark draw FILE`**: the puzzle as SVG in the default drawing, from anything
  `rate` reads; `dark`, `cell`, `labels`, and `card` / `position` for one position of a card's trace with its
  placed digits, pencil marks and colors. The reference renderer moved from `tools/render_svg.py` into the package
  (`pencilmark/render.py`), and the palette with it (`pencilmark/data/palette.json`; the docs keep a copy at
  `docs/palette.json`).

- **f-puzzles style capture**: the colors and widths of f-puzzles' generic lines, cages, circles and rectangles
  become the rules' `style`, as SudokuPad's already did (on 46 LMD f-puzzles, 414 of 905 rules keep their look).

- **Logging you can time and follow**: `--log trace` (and `pencilmark.log("trace")` in Python) writes every step of the
  card's route and every test of the technique-list search; every level's lines carry the milliseconds since start.
  `pencilmark.log(level)` switches the log on from Python.

- **Reusable custom rules**: a top-level `"definitions"` object names a custom rule once (`holds`, optional
  `scope`, `each`, `label`, `style`, `draw`); `{"type": "custom", "use": name, "cells": {...}}` places it, with its own
  style if wanted. A placement means the rule it spells out (same fingerprint and card). Custom rules also take `draw`
  (`line`, `cage`, `cells`, `circle`, `dot`), which the renderer draws in the rule's style.

- **Technique whitelist**: `rate(puzzle, techniques=["XWG", "SKY"])` / `--techniques XWG,SKY` grades for a solver who
  knows only these techniques (and the singles); a puzzle needing more gets band Unknown with the reason. Difficulty
  can be higher than the full card's: a solver with fewer techniques has fewer moves on offer at each step.

- **sudoku.coach reader**: `pencilmark.read.link("https://sudoku.coach/en/s/<id>")` and raw `SCv7_...` payloads, with
  the setter's colors and widths as style and cell colors as a `fill` decoration; the embedded solution is checked.
  Of 16,436 coach puzzles, 13,407 read, 0 crash; refused: extra rules written only in the description (2,293), older
  payload versions SCv3-SCv6 (716), and a few clues the site defines differently.

- **Style format**: rule `style` gains `size`, `angle`, `outline`, `outline_width` and `layer`; new decorations
  `polygon` (any closed shape), `fill` (cell colors, several per cell) and `image`; named top-level style keys. The spec
  says how much of it a renderer needs (13,451 sudoku.coach and 19,074 SudokuPad puzzles measured).

- **Puzzle format wording**: meaning and drawing are split per field (a kropki dot's color is meaning), and the
  fingerprint section says which spellings of one constraint meet.

### Grading (the classic technique pass)

- **One meaning, one grade**: a numbered clue that is exactly a kropki dot or an XV mark (difference 1, ratio 2,
  sum 5 or 10) is graded like the dot or mark (it was a digit table, priced differently). On the 26 development
  puzzles with such clues, the rank correlation with players' times holds or improves.

- **All unique rectangle types.** New type 6 (an X-Wing on one floor digit across a diagonal floor), and every type
  allows corners that miss one of the pair (HoDoKu's "missing candidates": the deadly-pattern argument is about the
  final grid). Avoidable rectangle type 2 is no longer tied to the color-algebra switch, so default cards use it.
  `placed` digits now reach the engine as solved-but-not-given, which avoidable rectangles need. HoDoKu's regression
  library: all 69 uniqueness cases that were missing match now (types 1-6, hidden rectangles, avoidable rectangles 1-2),
  no unsound move anywhere in the library. Explanations name types 5 and 6 (type 5 used the hidden rectangle text).

- **ALS chains of any ALS size** (HoDoKu's ALS-XY-Chain): four or five pairwise-disjoint almost locked sets linked
  by restricted common digits, listed under ALS-AIC.

- **Grouped chain ends**: an AIC, X-chain or ALS chain may end on a box-line group (HoDoKu's grouped AICs and nice
  loops). Speed on 419 classic-source cards: within noise.

- **Multi-Coloring type 2**: a color that sees both colors of another cluster is false.

- **Sue de Coq** with line and box sets of up to 3 cells, without the almost-locked restriction (HoDoKu's form).

- HoDoKu's regression library: missing 193 -> 64 cases over this pass, 0 unsound moves.

### Generator

- **Classic Medium requests succeed far more often**: a candidate that comes out too easy is re-dug with every
  technique and pulled back to the band on every attempt (was every other). Classic Medium in 180 s: 5 of 9 seeds
  (was 1 of 9); Hard unchanged. Medium classics need a written subset (pairs and triples seen in the head are Easy),
  so they remain the slowest classic band to hit.

- **Difficulty ranges spread**: `"difficulty": [lo, hi]` aims at a point drawn in the range for each seed
  (`info.aimed_at`) instead of returning the first puzzle inside it, which sat at the low edge (Very Easy `[2, 4]`:
  median 2.4, 2.2-2.9 before; 2.9, 2.2-4.0 now).

- **Cage limits work with tiled killers**: `{"type": "cage", "count": "tile", "sum": [null, 20]}` (and `size`, and
  a zero-given cage count): the tiling builds no cage over a maximum, merges cages under a minimum first, and draws
  again when one stays under.

- **Line `turns` limit and hand-drawn lines**: line templates take `turns` (`[min, max]`, `0` = straight). Generated
  lines may now step diagonally (never crossing a line of their kind) and are drawn as people draw them: human lines
  (5,520 on the development set) turn at 54% of their inner cells, take 31% of their steps diagonally and are
  straight 30% of the time; 1.2's were orthogonal only and turned at about 67%; now 58%, 34% and 22%.

- A multi-grid layout without `where.band` says in `info.warnings` that it was dug up to Hard.

- **Generator examples and the learning ladder regenerated** with the 1.3 generator.

- **No seed, a new puzzle.** A request without `limits.seed` draws a fresh seed each run (reported in `info.seed`,
  which reproduces it); 1.2 used seed 1, so every unseeded run gave the same puzzle.

- **`"difficulty": "typical"`** (with a band): the seed draws a window from where published puzzles of the band lie
  (a bell curve fitted to them; `info.aimed_at`) and digging stops inside it; classic Very Easy centers on 3.3
  (2.7-3.9), as generated sites' easy tiers do (sudoku.com easy / medium / hard: 2.5 / 3.1 / 3.6). It never fails a
  request: with nothing in the window by half of the time limit, any difficulty in the band will do
  (`info.aim_relaxed`). Opt in; without it a band request digs as far as the band allows, as before.

- Generated lines never cross each other diagonally; tiled killers take a minimum cage `size` above 2 (a few givens
  are added where the logic needs them; Medium or easier for now).

### Fixes

- **The technique list's alternatives search could run for minutes**: the route shared by every candidate alternative
  ran without the guard the other tests use, so banning a single on an Expert puzzle solved the whole puzzle the hard
  way (one sudoku.today thermo: 2.4 s in 1.2, 132 s, now 4.8 s; same card). `--log trace` now also times that route
  and the listing of what else was on offer.

- **Chains worked out in the head with a grouped end** (a box segment as one end) got the generic explanation (19 of
  2,937 classic development puzzles); they now read as the chain and the clash with both ends.

- **An ALS-XY-Wing removing two digits** lost its explanation to the generic text (its digit list held the words "3 and
  8", which broke the step's notation); explained in full now. Every step of the 2,937 classic development puzzles has
  its own explanation.

- **SudokuPad reader fixes** (Cracking the Cryptic screen): bare all-digit hex colors (`c:020202`) no longer break
  decoding, `[null]` regions are skipped, and a 0 digit (digits 0..8) is refused clearly instead of failing as a
  format error.

- **Empty Rectangle on multi-grid boards** matched cells by board coordinates; on a butterfly or samurai that made an
  unsound elimination (a generated butterfly's card lost its difficulty). It now checks the houses. A sweep of every
  development puzzle's routes then found no unsound step.

- **Speed: the quick uniqueness pass under `max_seconds`** took the whole time budget before CP-SAT got its turn: two
  zero-given variants went from 213 s and 121 s to 6 s and 8 s; the classic-source benchmark set from 1,307 s to 868 s,
  every grade unchanged.

- Explanations: the last cell of a cage or line names its rule even when the engine's move does not.

## 1.2.0 (2026-11-07)

### What changes for you

- **Difficulty values move.** The search part of the score counts refutations in propagation rounds, the score map is
  refitted, and the difficulty is the expected effort of a human-like solver. Easy puzzles score a little higher, hard
  ones a little lower. On the frozen benchmark, rank agreement with human solve times: fed 0.670 -> 0.709, grandgames
  0.752 -> 0.766, sudoku.coach 0.799 -> 0.805, sudoku.today 0.608 -> 0.619, Logic Masters 0.721 -> 0.713, Wang 2024
  0.663 -> 0.653; 99.8% of the puzzles get a card (99.5%), and the median card takes 0.15 s (0.49 s).
- **Technique names follow their cited sources** ([Techniques](docs/grades/techniques.md)), and the forms those sources
  describe are found. Some bands move: wider WXYZ-Wings put some Expert puzzles at Very Hard.
- **New in the format:** fog of war, custom rules (expressions over cell digits, with unknowns and layers), and
  `placed` digits for mid-solve boards. Shading and regions to find are reserved for a later version.
- **New reading and writing API**, one function per format, and every error is a `pencilmark.Error`.
- **Faster** on the slowest variants; several puzzles that hit the time limit are graded now.
- **Breaking, no aliases** (nobody depends on them yet): the format names, the reading and writing functions, the
  command line's `json`, `export` and `count` commands and its `--format` and `--computer` options, `rate(steps=, se=)`, the fingerprint prefix, `box_grid` and the
  coloring codes all change. Details under each heading below.

### Format (pencilmark JSON)

- The format is called "pencilmark JSON"; its document names are `pencilmark-puzzle`, `pencilmark-grade` and
  `pencilmark-spec` (were `sudoku-puzzle`, `sudoku-grade`, `sudoku-spec`), and the schema files are renamed to match.
- Fog of war (6.20): `{"type": "fog", "lit": [...], "triggers": [...]}`. Without triggers a correct digit lights its
  3×3; with them only the triggers reveal. A fog puzzle carries its solution. The SudokuPad and f-puzzles readers fill
  it in; 43 of the Cracking the Cryptic fog puzzles load with their fog (none before).
- Custom rules (6.18): a rule written as an expression over named cells, such as
  `{"type": "custom", "cells": {"c": [...]}, "holds": "2 * max(c) == sum(c)"}`, with scopes for every pair of
  neighbors, every window or every cell with its neighbors. Named `unknowns` (a number several clues share) and
  `layers` (a second value per cell) can be read by custom rules; puzzles with them solve and count, and grade as band
  Unknown with a `reason` for now. The grammar was checked on 1,000 Logic Masters puzzles.
- `placed`: digits filled in after the start, as on a mid-solve board. They are solved and graded like givens, but are
  not clues for the publishing checks or symmetry.
- `box_grid` states its tiling as a box size and a count: `{"type": "box_grid", "box": [3, 3], "count": [3, 3]}`;
  `count` is required. `origin` is optional (`r1c1` by default).
- Fingerprints are the bare SHA-256 digest (64 hex digits), without the `sha256:` prefix. The digest is unchanged.
- Generated puzzles carry `meta.generated_from` only when the spec asks for it, and can carry their own
  `meta.fingerprint`.
- Reserved for a later version: shading (`yin_yang`) and regions to find (`chaos`, `region_border`, `same_region`).
  Readers refuse them by name, as they refuse digit tables.

### Reading and writing

- One function per format. `pencilmark.read.plain / grid / pencil_marks / candidates / hodoku / sudokuwiki / ipuz /
  pencilmark / link` each read one format strictly; `pencilmark.write.pencilmark / document / plain / grid /
  sudokuwiki / ipuz` each write one. `rate`, `solve`, `count_solutions`, `describe`, `fingerprint` and the command line
  take any of them and detect the format (`read.detect`, `read.auto`), or take `format=` to name it. Site links pick
  their reader from the host.
- Gone: `load`, `to_export`, `dumps`, `from_string`, `to_string`, `from_ipuz`, `to_ipuz` and `rules_text` (now a
  field of `describe`'s result), and the engine's internal JSON as an input.
- One error family: every error is a `pencilmark.Error` (`FormatError`, `NotSupportedError`, `FetchError`,
  `ReadingMismatch`, `NotUnique`, `NoSolution`, `Undecided`, `GenerationFailed`), at the top level. The site readers'
  `SourceError`, `DecodeError`, `UnsupportedPuzzle` and `VerificationError` are gone.
- Public functions take their options as keywords and carry type hints. `solve(info=True)` is gone, and so are
  `rate(steps=True, se=True)`: ask for the fields (`fields=[..., "steps", "se"]`, with `explain=` for the steps'
  explanations).
- Site links are checked against the setter's embedded solution: a reading the solution breaks is refused with
  `ReadingMismatch`. On 1,351 Cracking the Cryptic SudokuPad puzzles this refuses 107 of 112 misreads and keeps every
  correct reading.
- The site readers read many more rules, from the rules text as well as the drawing: Cracking the Cryptic puzzles
  281 -> 337 graded, the 2,000 most-solved Logic Masters sudokus 802 -> 912, GMPuzzles' GAS series 136 -> 217. One-off
  rules become custom rules. Mechanics pencilmark does not model (equality cages, clones, maze paths, ...) are refused
  by name instead of misread.
- Readers keep a SudokuPad puzzle's look (line colors and widths, cage and dot colors) as each rule's `style`.
- The sudokuwiki reader keeps Andrew Stuart's placed digits as `placed`, and the writer writes them back.

### Command line

- Every command takes `--from FORMAT` (default: detected per line).
- `rate --print TEMPLATE` replaces `--format`, `convert --to pencilmark|plain|grid|sudokuwiki|ipuz` replaces `export`,
  `count-solutions` replaces `count`, `rate --mode computer` replaces `--computer`, and the `json` command is gone. `generate --seed / --time` are gone (the spec's `limits` hold them).
- `--log info` / `--log debug` on every command: pages fetched, what a reader read, time limits, each generator
  attempt, stage timings (the standard Python logger `pencilmark`).

### Grading

- Difficulty: the expected effort of a human-like solver, from human routes whose stretches of singles are replayed in
  human order (singles reach the same next bottleneck in any order). The search part counts a refutation's length in
  propagation rounds, so a puzzle and its transpose grade the same (98% identical, was 67%). The score map is refitted
  on Andrew Stuart's ratings and human times. Rating takes about 15% longer.
- The band, technique list and publishing checks follow the human route: each step chosen the way people choose, by a
  spotting score fitted on casual solvers' replays. On the reference cards 1 of 227 bands moves.
- Technique names follow their cited sources: Skyscraper only when the pairs' inner ends share a line (else Turbot
  Fish); XY-Chain only with the same digit at both ends (else AIC); Remote Pairs from 4 cells; Mutant fish are named
  Mutant (were Franken); Empty Rectangles as HoDoKu defines them (the chain search no longer names grouped X-Chains
  ER).
- Forms the sources describe, now found: WXYZ-Wing over any four cells and type 2 (all digits restricted); Death
  Blossom of any size; almost locked sets of any size, overlapping ALS-XZ, eliminations inside the sets of
  doubly-linked ALS-XZ and ALS-XY-Wing; Aligned Pair Exclusion with any almost locked set as witness; BUG+1 with a
  4+ candidate cell; Unique Rectangle type 3 with subsets of any size; hidden and extended Unique Rectangles type 2;
  XY-Chains up to 12 cells; Pattern Overlay rule 2; coloring that empties a house (sudokuwiki, July 2026).
- How the techniques were checked: Andrew Stuart's strategy examples (132 of 139 found, no wrong move), independent
  reference finders, soundness walks over 391 puzzles (no wrong move), 192 of his curiosities, and Sudoku Explainer
  on 1,672 puzzles (nothing it uses is missing).
- Coloring as a solving method is opt in: `rate(colouring=True)`, `--coloring`. It keeps colors (cells known to
  hold one unknown digit) through the solve, with its own techniques (Color Single, Color Fill, Color Pair, Color
  Trap, Color Pointing, Color Fish, Complete Colors, Chain Color, Color Clash). Codes of coloring techniques
  share the prefix C: EQD -> CEQ, SCL -> CSM, MCL -> CMU, 3DM -> CMD.
- Fog of war is graded under the fog: the band and techniques of the route a solver can take on what the fog shows,
  round by round. Where the fog stops the route, the band is Unknown with `stopped_at_step`; the card's `fog` field
  says what the fog did.
- Band Unknown with a `reason` replaces the `Undecided` error in `rate` when uniqueness can't be settled within the
  engine's limits (`solve` still raises it); errors are only for wrong inputs.
- Clue Facts are Easy; Color Fill is Medium.
- The last cell of a killer cage (its total minus the digits in it) is the Very Easy step "Last cell of a cage" (`CSI`),
  as for other rules; it read as a Naked Single. Reference cards: bands and difficulties unchanged.

### Explanations and the card

- Explanations name the pattern found, with the engine's own cells: hidden and extended Unique Rectangles, Aligned
  Pair Exclusion with its witnesses, WXYZ-Wings (types 1 and 2), Pattern Overlay rules 1 and 2, Death Blossom,
  doubly-linked ALS-XZ, Empty Rectangles, BUG+1.
- Sub-steps (`explain=["short", "substeps"]`): steps told as sub-steps with reasons and drawing annotations, for
  intersections, subsets, line rules, coloring, killer cages, fish (with Franken and Mutant shapes), XY-, XYZ- and
  WXYZ-Wings, and single chains.
- Card field `trace`: the board before the first step and after each step, with the notes a casual solver would have
  written (`marks`) and the colors an expert would have painted (`colors`), so a viewer can replay a solve.
- Step notation names houses by position for every input ("X-Wing: 3 r58 c68").
- Rule facts in explanations are worked out for the puzzle's digit range (a 6×6 black dot excludes only 5).

### Publishing checks

- Quality presets: `quality={"preset": "standard"}` (`--quality preset=standard`) turns on decorative, trivial, trial,
  thin and unusual, all at reject.
- Opt-in checks: `asymmetric`, `no_interplay`, `winding`, `short_lines`, `repetitive`, `monotone`, `desert`,
  `late_break`, with limits near the edge of published puzzles.
- `thin` replaces `spike`: a Medium or harder puzzle whose candidate steps carry less than 25% of its effort.
  `spike` flagged most published puzzles.
- The `unusual` ranges per band are re-measured on this engine (7,155 puzzles). They apply to 9×9 boards only (they were
  measured there).
- Rule use counts the steps where a rule acts without being named: a line's own pair relations, and anti-knight or
  no-touch links erasing notes. Eight false "used in only 0 steps" rejects on the reference cards go.

### Generator

- The learning guide's killer curriculum: the last cell of a cage, bigger cages, combinations, then cage maths.
- Every request passes the standard publishing checks unless its `quality` says otherwise (`{}` gives each check
  its own default severity, as `rate` does).
- Every line kind the engine grades: slow thermo, entropic, modular, parity, palindrome, zipper, region sum, lockout
  and double arrow, besides thermo, whisper, renban and between.
- Corner clues (quadruples, mathrax), outside clues (sandwich, x-sum, skyscraper, little killer), and locked
  `neighbors` rules with any `op` and `where` (for example nonconsecutive).
- A request without a band or difficulty target keeps the broadest search and says so in `info.warnings`.
- A request that keeps many givens (a quarter of the cells or more) may leave givens inside cages (never a whole cage),
  so the last cell of a cage is read as its total minus the digits in it; with fewer givens the cages carry the puzzle.
- With `quality` in the request, a puzzle's checks and card are one grading (the nine-variants example 135 -> 121 s).
- `limits.time` holds while the generator restores givens and prunes.

### Speed

- Long lines (over 12 cells) of neighbor rules, counting circles, and trial refutations on killers: the 18 frozen
  puzzles with long lines 677 -> 32 s; a 15-circle puzzle 232 -> 2.5 s; 331 frozen killers 1,490 -> 1,320 s. Three
  puzzles that hit the 300 s limit are graded now.
- Uniqueness: with OR-Tools installed, CP-SAT takes over after 2 s (one puzzle 197 -> 4.4 s); without it, the C++
  search stops at a time limit too.
- Custom rules: `concat(cells) in {...}` becomes a table at any size (one puzzle 271 -> 0.5 s); a rule's table of
  number literals is built once (64 such rules: 27 min -> 1.7 s to load); a rule reading a list at fixed positions
  covers only those cells.
- `describe` no longer solves the puzzle (a hard Latin square: minutes -> 17 ms).

### Fixes

- SudokuPad thermometers and whispers were exported as chains of pair rules with the line's color on one pair only;
  they are `line` rules again.
- A rule part tagged with its line kind was dropped on export even when its line was missing.
- The engine params cache missed in-place changes between two `rate` calls in one process.
- The generator crashed with `Undecided` on a samurai without OR-Tools.
- SudokuPad links of the form `sudokupad.app/<author>/<slug>` are fetched.
- The `count` rule's docs read as if no counted cell could be in a house.

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
- SudokuPad files read that crashed the reader (5 of 19,194 stored puzzles): a color typed without "#" stored as a
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
- Vudoku is drawn as a gray right-angle corner, elbow in the vertex cell, arms reaching into the arm
  cells (it was a thin V through the cell centers). The docs' examples use the L of three cells the rule is played on.
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
- Two dead technique links fixed: Multi-Colouring's SudokuWiki page (in its explanation) and Simple Coloring's
  KrazyDad page (techniques page).
- Generator specs accept the `odd` and `even` cell templates SPEC.md documents (only an undocumented `parity` worked);
  `parity` (odd or even cells, either kind) is now documented too.
- `se`: a technique Sudoku Explainer has no value for takes the value of the technique it is a special case of
  (Simple Coloring and Multi-Colouring rate as X-Chain, 6.6, instead of the 7.0 fallback). The DiufSudoku scale is
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
- Step explanations: Clue facts, Clue shape and low / high and odd / even coloring have their own explanations;
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
- Class coloring and clue facts (two variant techniques) record their move descriptors in the right slots (cells,
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
  message naming them as future work. `neighbors` kinds are documented as exact shortcuts for an operator on a pair
  pattern.
- Pair operators take their parameter under its own key, as the rest of the format: `{"op": "difference", "value": 3}`,
  `{"op": "sum", "sum": 10}`, `any_of` a list of objects; positional `params` lists are refused. Writing an
  `any_of` relation back no longer crashes.
- `"type": "table"` and the `allowed` operator are reserved: explicit digit tables made files large and could not be
  drawn; a custom rule type is planned to replace them. Mechanics without a rule family cannot be written in
  format_version 1. The Rossini test puzzle now uses `rossini` rules and `negative` instead of edges and tables.
- Generator: one vocabulary. `pencilmark.generate(spec)` (also `pencilmark.gen.generate`) takes a `pencilmark-spec` request and
  returns a `pencilmark-puzzle` (with `meta.generated_from`), honoring the spec's `fields`; the internal Spec dicts
  (`target_band`, `max_givens`, ...) and `spec_from_gen` / `spec_to_gen` are no longer public. `SPEC.md` version 1
  describes exactly what the generator runs; the rest is listed as reserved and refused with a message naming it.
  Example specs that use reserved parts moved to `docs/examples/specs/reserved/`.
- **Seven bands**: Very Easy (scanning: full house, hidden singles) / Easy (naked singles, pointing / claiming, one rule's
  combinations) / Medium (pairs, triples, quads; variant implications) / Hard (the first learned patterns: X-Wing,
  Skyscraper, 2-String Kite, Turbot Fish, simple coloring) / Very Hard (Empty Rectangle, finned and larger fish, wings,
  uniqueness) / **Expert** (new: XY-Chain, AIC, Medusa, ALS) / Extreme (forcing, trial). The steps common curricula
  take (docs/PHILOSOPHY.md). `band_index` runs 0..6. Difficulty and time are unchanged
  (all 7,427 graded puzzles of the frozen benchmark identical).
- Step explanations at three levels: `notation` (the solvers' shared form, `X-Wing: 3 r58 c68 => r679c6<>3`), `short`,
  `teach`; `pencilmark rate --report -v / -vv / -vvv` lists the steps at those levels. The report shows time percentiles
  only when asked for (`--fields ...,time_p80`) and names alternatives in full.
- Singles never carry `uses`; alternatives inside a chip are ordered deterministically (the order depended on Python's
  per-process hashing); `max_seconds` also checked in the generalized fish search.
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
  list was being minimized, the grade stands and the list may not be minimal).
- Optional `elapsed` field (wall-clock seconds for the call); `solve(puzzle, info=True)` returns the solution with its
  seconds; the generator's `info` has `seconds` and `attempts`.
- Optional `time_dist` field (`{"type": "lognormal", "median", "sigma_players", "sigma_model"}`); `time_p50` accepted.
- Three variant techniques from how people solve on video: clue facts (`CFX`, Very Easy: what a clue rules out on an
  empty grid, e.g. no 5 on a whisper), clue shape (`CSH`, Easy: a line's shape inside one house, e.g. a whisper 4
  between two 9s) and high/low & odd/even coloring (`CCL`, Medium). Accuracy on human data is unchanged on average
  (kropki ranks better); solving routes are shorter and closer to human ones.
- Time spread: `time_mean` and any percentile `time_pNN` (e.g. `time_p20`, `time_p80`) on request, over today's players
  (log-normal; sigma 0.79 for classics and multi-grid layouts, 0.62 with any other rule, from two sources' per-player times). `time_p80` was a one-player spread (1.53x) and is now
  the population one (about 1.85x). `time` is the median player.
- Generator: element varieties (kropki color, XV letter, odd/even) with counts, ranges and caps; the information-budget
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
- Drawing: `docs/palette.json` with the default sizes, light and dark themes and the community line colors; reference
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
