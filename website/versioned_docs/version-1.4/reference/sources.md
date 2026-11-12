---
title: "Puzzle sources"
description: "Links and payloads from SudokuPad, f-puzzles, Penpa, Logic Masters and sudoku.coach, read into puzzles."
toc_max_heading_level: 2
---

# Puzzle sources

Links and payloads from SudokuPad, f-puzzles, Penpa, Logic Masters and sudoku.coach, read into puzzles. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.sources {#pencilmark.sources}

[src/pencilmark/sources/__init__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py)

Puzzle sources: links / payloads from SudokuPad, f-puzzles, penpa-edit and Logic Masters -> puzzle JSON.

from pencilmark import sources

```
pj = sources.load("https://sudokupad.app/wjgxgaji9a")              # -> puzzle JSON dict (pencilmark.puzzle_json)
p = pencilmark.puzzle_json.from_json(pj)
```

```
load() recognizes
    SudokuPad    sudokupad.app/... , app.crackingthecryptic.com/... (short ids are fetched: one API request),
                 bare 'scl...' / 'ctc...' / 'fpuzzles...' payloads, 'sudokupad:<shortid>'
    f-puzzles    f-puzzles.com/?load=... (offline), ?id=<alias> (one TinyURL HEAD request)
    penpa        any .../penpa-edit/?m=..&p=... (penpa-edit, penpa+, mirrors; offline), 'penpa:<p value>'
    LMD          logic-masters.de/Raetselportal/Raetsel/zeigen.php?id=XXXXXX or 'lmd:XXXXXX' (page fetch, robots.txt
                 obeyed, >= 2.5 s between requests), converting the first linked puzzle that translates
    shorteners   tinyurl / bit.ly / git.io / is.gd links are resolved (one HEAD request) and dispatched
    puzzle JSON  a dict / JSON text already in pencilmark.puzzle_json format is returned as is
Modules: sudokupad, fpuzzles, penpa, lmd (each with decode / to_puzzle; see their docstrings for coverage).
Errors: Error > FormatError (unrecognised / undecodable), FetchError (network, robots.txt), NotSupportedError
(.elements = what could not be mapped exactly; nothing is silently dropped), ReadingMismatch (verify=True).
```

| Name | What it does |
|---|---|
| def [`detect`](#pencilmark.sources.detect) | -> 'puzzle_json' \| 'sudokupad' \| 'fpuzzles' \| 'penpa' \| 'lmd' \| 'coach' \| 'short' \| None. |
| def [`load`](#pencilmark.sources.load) | Link / payload / decoded dict -> puzzle JSON dict. |
| def [`contradicts_solution`](#pencilmark.sources.contradicts_solution) | True when the puzzle embeds a full solution and no grid with those digits satisfies the reading (the… |
| def [`check`](#pencilmark.sources.check) | Unique solution (and equal to pj['solution'] when present) or ReadingMismatch. |

### `def detect(x)` {#pencilmark.sources.detect}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L29)

-> 'puzzle_json' | 'sudokupad' | 'fpuzzles' | 'penpa' | 'lmd' | 'coach' | 'short' | None.

### `def load(x, rules_text=None, infer=False, fetch=True, verify=False, time_limit=30.0, check_solution=True)` {#pencilmark.sources.load}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L79)

Link / payload / decoded dict -> puzzle JSON dict. rules_text: the rules from the page that links the puzzle (used where the puzzle file has none, and for penpa's rule screening). infer=True lets SudokuPad / f-puzzles search line readings with the solver (slow). fetch=False refuses anything that needs a network request. verify=True checks uniqueness (and the embedded solution) with CP-SAT and raises ReadingMismatch otherwise. check_solution=True (default): when the puzzle embeds the setter's solution, a reading that the solution breaks is refused (ReadingMismatch) -- a rule was read differently from what the setter meant (usually a one-off rule worded like a standard one: "digits may repeat in a cage", digits 0-8, rounded cage sums).

### `def contradicts_solution(pj, node_limit=200000)` {#pencilmark.sources.contradicts_solution}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L132)

True when the puzzle embeds a full solution and no grid with those digits satisfies the reading (the engine's exhaustive search, completed within node_limit). False when it fits, when there is no usable solution, or when the search could not decide.

### `def check(pj, time_limit=30.0)` {#pencilmark.sources.check}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L152)

Unique solution (and equal to pj['solution'] when present) or ReadingMismatch. Returns the solution string.

## pencilmark.sources._common {#pencilmark.sources._common}

[src/pencilmark/sources/_common.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py)

Shared pieces of pencilmark.sources: exception types, a polite HTTP client, Puzzle -> puzzle JSON.

| Name | What it does |
|---|---|
| def [`reads`](#pencilmark.sources._common.reads) | decorator for a reader: a crash on malformed data (a missing key, a value of the wrong type, a short list)… |
| def [`unsupported_from_reason`](#pencilmark.sources._common.unsupported_from_reason) | Translator failure reason ('unsupported: a, b' or a plain reason) -> NotSupportedError. |
| class [`Http`](#pencilmark.sources._common.Http) | Sequential, polite HTTP: identifying User-Agent, timeouts, a minimum gap between requests to the same host,… |
| def [`to_puzzle_json`](#pencilmark.sources._common.to_puzzle_json) | engine Puzzle (finalized or not) -> puzzle JSON dict (pencilmark.puzzle_json.to_json); a solution string /… |

### `def reads(source)` {#pencilmark.sources._common.reads}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L30)

decorator for a reader: a crash on malformed data (a missing key, a value of the wrong type, a short list) becomes a FormatError naming the source and the problem

### `def unsupported_from_reason(reason, source='')` {#pencilmark.sources._common.unsupported_from_reason}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L47)

Translator failure reason ('unsupported: a, b' or a plain reason) -> NotSupportedError.

### `class Http` {#pencilmark.sources._common.Http}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L62)

Sequential, polite HTTP: identifying User-Agent, timeouts, a minimum gap between requests to the same host, optional robots.txt checks, at most one retry (after a pause) on 429 / 5xx / network errors.

#### `def allowed(self, url)` {#pencilmark.sources._common.Http.allowed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L79)

*No docstring.*

#### `def get_text(self, url)` {#pencilmark.sources._common.Http.get_text}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L136)

*No docstring.*

#### `def redirect_target(self, url)` {#pencilmark.sources._common.Http.redirect_target}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L139)

Location header of a redirecting URL (HEAD, not followed) -- resolves TinyURL-style short links.

### `def to_puzzle_json(p, solution=None, meta=None)` {#pencilmark.sources._common.to_puzzle_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L150)

engine Puzzle (finalized or not) -> puzzle JSON dict (pencilmark.puzzle_json.to_json); a solution string / list is attached only when it has one digit per cell.

## pencilmark.sources.sudokupad {#pencilmark.sources.sudokupad}

[src/pencilmark/sources/sudokupad.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py)

SudokuPad (sudokupad.app / app.crackingthecryptic.com) links and payloads -> puzzle JSON.

```
Link forms
    https://sudokupad.app/<shortid>                     short link: resolved by fetch() via sudokupad.app/api/puzzle/<id>
    https://sudokupad.app/[sudoku/]scl<lz-base64>       SudokuPad compact JSON (also 'ctc' prefix)
    https://sudokupad.app/[sudoku/]fpuzzles<lz-base64>  an f-puzzles payload (also 'fpuz', ?puzzleid=...)
decode() returns {"format": "scl"|"ctc"|"fpuzzles"|"json", "meta": {title, author, rules, solution, ...},
"puzzle": <SudokuPad JSON with expanded keys | f-puzzles JSON>}.
```

to_puzzle() translates with _sp_translate: line meanings come from the rules text (colour words, keywords) and SudokuPad's default palette; pass reading= (an inferred reading, e.g. from data/sudokupad/_inferred.jsonl) to reproduce a stored translation, or infer=True to search readings with the solver (slow: several CP-SAT runs). Rules the translator cannot model raise NotSupportedError (never silently dropped).

decode(link_or_payload, fetch=False) -> dict        fetch(short_link) -> dict (one polite request)

```
translate(x, page_text=None, reading=None, infer=False) -> (engine Puzzle, info)
to_puzzle(x, page_text=None, reading=None, infer=False, fetch=True) -> puzzle JSON dict
```

| Name | What it does |
|---|---|
| def [`compact_to_json`](#pencilmark.sources.sudokupad.compact_to_json) | SudokuPad compact JSON (unquoted keys, t/f, array elisions, bare hex colours) -> standard JSON text. |
| def [`expand`](#pencilmark.sources.sudokupad.expand) |  |
| def [`is_sudokupad_url`](#pencilmark.sources.sudokupad.is_sudokupad_url) |  |
| def [`payload_key`](#pencilmark.sources.sudokupad.payload_key) | Link or bare string -> the SudokuPad key: a payload ('scl...', 'fpuzzles...') or a short id. |
| def [`decode_payload`](#pencilmark.sources.sudokupad.decode_payload) | 'scl...' / 'ctc...' / 'fpuzzles...' / 'fpuz...' / JSON text -> {"format", "meta", "puzzle"} or None |
| def [`decode`](#pencilmark.sources.sudokupad.decode) | Link / payload / already-decoded dict -> {"format", "meta", "puzzle"}. |
| def [`fetch`](#pencilmark.sources.sudokupad.fetch) | Resolve a short link / id through the SudokuPad API (one request, identifying User-Agent, 30 s timeout, at… |
| def [`translate`](#pencilmark.sources.sudokupad.translate) | -> (engine Puzzle (not finalized), info dict). |
| def [`metadata`](#pencilmark.sources.sudokupad.metadata) | title / author / rules_text / solution of a decoded puzzle (metadata cages, then the 'metadata' block). |
| def [`to_puzzle`](#pencilmark.sources.sudokupad.to_puzzle) | SudokuPad link / payload / decoded dict -> puzzle JSON dict (pencilmark.puzzle_json format) with title,… |

### `def compact_to_json(s)` {#pencilmark.sources.sudokupad.compact_to_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L103)

SudokuPad compact JSON (unquoted keys, t/f, array elisions, bare hex colours) -> standard JSON text.

### `def expand(o)` {#pencilmark.sources.sudokupad.expand}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L169)

*No docstring.*

### `def is_sudokupad_url(s)` {#pencilmark.sources.sudokupad.is_sudokupad_url}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L177)

*No docstring.*

### `def payload_key(link)` {#pencilmark.sources.sudokupad.payload_key}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L183)

Link or bare string -> the SudokuPad key: a payload ('scl...', 'fpuzzles...') or a short id.

### `def decode_payload(payload)` {#pencilmark.sources.sudokupad.decode_payload}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L199)

'scl...' / 'ctc...' / 'fpuzzles...' / 'fpuz...' / JSON text -> {"format", "meta", "puzzle"} or None

### `def decode(link_or_payload, fetch=False)` {#pencilmark.sources.sudokupad.decode}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L241)

Link / payload / already-decoded dict -> {"format", "meta", "puzzle"}. Short links need a request: pass fetch=True (or call fetch()); otherwise FormatError.

### `def fetch(short_link, http=None)` {#pencilmark.sources.sudokupad.fetch}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L272)

Resolve a short link / id through the SudokuPad API (one request, identifying User-Agent, 30 s timeout, at most one retry) and decode it.

### `def translate(x, page_text=None, reading=None, infer=False, fetch=True)` {#pencilmark.sources.sudokupad.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L302)

-> (engine Puzzle (not finalized), info dict). Raises NotSupportedError / FormatError.

### `def metadata(sp)` {#pencilmark.sources.sudokupad.metadata}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L324)

title / author / rules_text / solution of a decoded puzzle (metadata cages, then the 'metadata' block).

### `def to_puzzle(x, page_text=None, reading=None, infer=False, fetch=True, url=None, style=True)` {#pencilmark.sources.sudokupad.to_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L339)

SudokuPad link / payload / decoded dict -> puzzle JSON dict (pencilmark.puzzle_json format) with title, author, rules_text, source (link) and the embedded solution when it has one digit per cell. style: keep how the puzzle draws its elements, which export writes as the rules' `style` (cosmetic).

## pencilmark.sources._sp_translate {#pencilmark.sources._sp_translate}

[src/pencilmark/sources/_sp_translate.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py)

SudokuPad puzzle JSON -> engine Puzzle.

```
Element conventions (SudokuPad, coordinates [row, col] in cell units):
  cells[r][c].value      givens        regions        boxes / irregular regions
  cages {cells, value}   killer cages  (metadata cages carry title/rules)
  lines {wayPoints, color, thickness}   thermo / whisper / renban / region-sum /
                                        palindrome / entropic / arrow shafts ...
  underlays/overlays     circles (thermo bulbs, arrow circles, odd), squares (even),
                         small dots on edges (kropki), letters (XV), clue text
  arrows                 arrow heads (arrow sudoku), little-killer arrows
The rules text decides what a coloured line means ("green lines are German
whispers"); hex colours are mapped to colour names; unresolved lines fall
back to SudokuPad's default palette. Rules the grader can't model yet make
the translation fail loudly (reason recorded) instead of guessing.
Output schema: engine Puzzle with relations / groups / domains /
p.constraints (sum, arrow, equal_sum, set, table, line, little_killer,
sandwich, xsum, skyscraper).
Negative constraints are per marker type (white / black kropki, X, V), read
from the rules text by negative_markers(); infer() also tries none / per
family / all.
```

| Name | What it does |
|---|---|
| def [`fog_of`](#pencilmark.sources._sp_translate.fog_of) | SudokuPad fog of war (docs/research/fog_mechanics.md): lit cells from FOGLIGHT cages ("foglight" or… |
| def [`unmodelled_rules`](#pencilmark.sources._sp_translate.unmodelled_rules) | the mechanics of UNMODELLED_RULES a (lower-case) rules text names, as refusal reasons; chaos_ok: the reader… |
| def [`arrow_sight_counts_itself`](#pencilmark.sources._sp_translate.arrow_sight_counts_itself) | does an arrow's own-region count include the arrow cell? |
| def [`sight_counts_itself`](#pencilmark.sources._sp_translate.sight_counts_itself) | does a region_sight clue count its own cell? |
| def [`region_statements`](#pencilmark.sources._sp_translate.region_statements) | (element kind -> True (its cells share a region) / False (they lie in different regions), the sentences… |
| def [`chaos_rules`](#pencilmark.sources._sp_translate.chaos_rules) | the chaos constraint, drawn borders (dark lines along grid lines) and the region statements of the rules… |
| def [`default_evidence`](#pencilmark.sources._sp_translate.default_evidence) | the rules text describes a default-colour meaning: a sentence about a line (or naming the rule) that matches… |
| def [`color_name`](#pencilmark.sources._sp_translate.color_name) |  |
| def [`dot_color_rules`](#pencilmark.sources._sp_translate.dot_color_rules) | colour -> (holds, label, all given) for dots of colours other than white / black whose sentence says what… |
| def [`diff_rule`](#pencilmark.sources._sp_translate.diff_rule) | 'adjacent digits differ by at least K' -> whisper key (K=5 whisper, K=4 dutch, else 'whisperK'), or None. |
| def [`arrow_variants`](#pencilmark.sources._sp_translate.arrow_variants) | arrows the text redefines (or adds to): custom rules over each arrow's circle c and line L |
| def [`custom_line`](#pencilmark.sources._sp_translate.custom_line) | a line rule with no rule family on cells ids: custom rules (LINE_CUSTOM runs, same parity along the line) or… |
| def [`other_lines_rule`](#pencilmark.sources._sp_translate.other_lines_rule) | the line rule a sentence gives the lines no other sentence names ("numbers on all other lines are each a set… |
| def [`every_line_rule`](#pencilmark.sources._sp_translate.every_line_rule) | the line rule a sentence gives every line ("all lines are region sum lines", "every line is a renban", "an… |
| def [`yin_yang_reading`](#pencilmark.sources._sp_translate.yin_yang_reading) | the shading couplings a yin-yang rules text states -> [("cage" \| "thermo" \| "all", "odd" \| "even", shaded?),… |
| def [`add_yin_yang`](#pencilmark.sources._sp_translate.add_yin_yang) | the shading frame and its couplings as rules of the puzzle (custom rules reading shaded()) |
| def [`clone_groups`](#pencilmark.sources._sp_translate.clone_groups) | clones drawn as coloured shapes: {(r, c): colour} -> per colour with two or more connected shapes, the… |
| def [`described_line_rules`](#pencilmark.sources._sp_translate.described_line_rules) | line rules the text describes without naming them, from sentences about a line or thread that name no colour… |
| def [`rules_color_map`](#pencilmark.sources._sp_translate.rules_color_map) | colour word -> rule key, from sentences mentioning both; None for a colour a line sentence names with a rule… |
| def [`negative_markers`](#pencilmark.sources._sp_translate.negative_markers) | Which edge-marker types carry a negative constraint ("all white dots are given", "ALL V ARE GIVEN",… |
| def [`chess_rule`](#pencilmark.sources._sp_translate.chess_rule) | anti-knight / anti-king over the whole grid (_chess_sentences) |
| def [`chess_other`](#pencilmark.sources._sp_translate.chess_other) | a knight / king move rule the readers do not model: a sentence about the move that is neither the global… |
| def [`anti_sums`](#pencilmark.sources._sp_translate.anti_sums) | totals no two orthogonally adjacent cells may reach, with no marker drawn for them ("No two cells which… |
| def [`rule_flags`](#pencilmark.sources._sp_translate.rule_flags) |  |
| def [`negative_types`](#pencilmark.sources._sp_translate.negative_types) | Marker types under a negative constraint: overrides["_negative"] (iterable of MARKER_TYPES) > legacy… |
| def [`hls`](#pencilmark.sources._sp_translate.hls) |  |
| def [`line_rule_from_text`](#pencilmark.sources._sp_translate.line_rule_from_text) | Rule for a line colour: exact colour-class match, else the nearest colour word in the rules text (hue within… |
| def [`is_chevron`](#pencilmark.sources._sp_translate.is_chevron) | A greater-than sign drawn as a line: 3 waypoints spanning &lt; 0.9 cells with the middle (apex) off the ends'… |
| def [`inequality_signs`](#pencilmark.sources._sp_translate.inequality_signs) | Greater-than signs drawn as chevrons (3-point lines) or short arrows across a cell edge -> (smaller, larger)… |
| def [`join_branches`](#pencilmark.sources._sp_translate.join_branches) | [(colour, cells), ...] of one set rule -> the cell lists of its lines: a piece whose end lies inside another… |
| def [`line_items`](#pencilmark.sources._sp_translate.line_items) | Cell lines of the puzzle: [(colour class, hex, [cells]), ...], skipping decoration: lines drawn along grid… |
| def [`cell_of`](#pencilmark.sources._sp_translate.cell_of) |  |
| def [`line_cells`](#pencilmark.sources._sp_translate.line_cells) |  |
| def [`edge_number_rule`](#pencilmark.sources._sp_translate.edge_number_rule) | Meaning of numbers on cell borders from the rules text (None = unknown). |
| def [`path_points`](#pencilmark.sources._sp_translate.path_points) | an SVG path (M / L / H / V / Q / C / Z, absolute or relative) -> its subpaths as lists of [row, col] points… |
| def [`path_circle`](#pencilmark.sources._sp_translate.path_circle) | a circle drawn as a path ("M x y m r 0 a r r 0 1 0 -2r 0 a r r 0 1 0 2r 0") -> (center [row, col], diameter)… |
| def [`path_lines`](#pencilmark.sources._sp_translate.path_lines) | lines drawn as SVG paths (Sudoku Maker files: `d`, no `wayPoints`) -> ordinary lines, one per subpath; a… |
| def [`without_nulls`](#pencilmark.sources._sp_translate.without_nulls) | the puzzle's element lists without null entries (SudokuPad skips them; some files carry them, in a list or… |
| def [`numbers_on_circles`](#pencilmark.sources._sp_translate.numbers_on_circles) | a number drawn just off an edge circle (its baseline shifted by up to 0.2 cell) is that circle's number:… |
| def [`branch_starts`](#pencilmark.sources._sp_translate.branch_starts) | thermometer branches drawn without a bulb: a line with no circle at either end that starts or ends on the… |
| def [`thermo_network`](#pencilmark.sources._sp_translate.thermo_network) | the board's thermometer strokes [(rule, drawn cells, ids)] read together. |
| def [`emit_line`](#pencilmark.sources._sp_translate.emit_line) | one line read as `rule` (its drawn cells lc, their engine ids) -> the puzzle's constraints / relations /… |
| def [`translate`](#pencilmark.sources._sp_translate.translate) | sp: decoded dict from sudokupad.fetch; page_text: the puzzle page's rules (e.g. |
| def [`plain_sudoku`](#pencilmark.sources._sp_translate.plain_sudoku) | nothing read beyond rows, columns, standard boxes and givens (irregular regions count as read: they are… |
| def [`equality_cages`](#pencilmark.sources._sp_translate.equality_cages) | equality cages: as many low as high digits and as many even as odd digits in each cage (the middle digit of… |
| def [`text_cell_rules`](#pencilmark.sources._sp_translate.text_cell_rules) | rules on caged or coloured cells stated in the text: "digits in the cage are odd" (a parity clue on caged… |
| def [`drawn_in_grid`](#pencilmark.sources._sp_translate.drawn_in_grid) | shapes (cell-sized or smaller, without text) and lines drawn inside the grid |
| def [`outside_clues`](#pencilmark.sources._sp_translate.outside_clues) | Numbers outside the grid: little killer (with a diagonal arrow), else sandwich / x-sum / skyscraper… |
| def [`fortress_cells`](#pencilmark.sources._sp_translate.fortress_cells) | Fortress: a digit in a grey cell is greater than the digits in its orthogonally adjacent white cells (grey… |
| def [`battenburg_corners`](#pencilmark.sources._sp_translate.battenburg_corners) | Battenburg (checkerboard) clues: a square marker on a cell corner -> the 4 cells around it form an odd /… |
| def [`rossini_arrows`](#pencilmark.sources._sp_translate.rossini_arrows) | Rossini: an arrow outside the grid -> the first three cells of that row / column increase in the arrow's… |
| def [`chaos_arrows`](#pencilmark.sources._sp_translate.chaos_arrows) | in-cell arrows of a chaos puzzle: border counts (ARROW_BORDER_TEXT) or own-region sight (ARROW_SIGHT_TEXT)… |
| def [`marked_cells`](#pencilmark.sources._sp_translate.marked_cells) |  |
| def [`shaded_regions`](#pencilmark.sources._sp_translate.shaded_regions) | Extra all-different regions drawn as shading (asterisk, windoku, centre dot, 'grey regions'), only when the… |
| def [`global_custom`](#pencilmark.sources._sp_translate.global_custom) | one-off whole-grid rules (GAS) stated only in the text, as scoped custom rules -> the kinds added |
| def [`global_rules`](#pencilmark.sources._sp_translate.global_rules) | Whole-grid rules stated only in the text. |
| def [`parity_shapes`](#pencilmark.sources._sp_translate.parity_shapes) | Odd / even cells from the rules text: 'a (grey) circle contains an odd digit', 'digits in squares are even'. |
| def [`quadruples`](#pencilmark.sources._sp_translate.quadruples) | Quadruple: digits in a circle on a cell corner all appear (with multiplicity) in the four surrounding cells… |
| def [`translate_explicit`](#pencilmark.sources._sp_translate.translate_explicit) | Boards of any shape whose houses are declared as hidden 'unique' cages (SudokuPad convention for… |
| def [`satisfies`](#pencilmark.sources._sp_translate.satisfies) | Does solution `sol` (list of digits) satisfy every rule of p? |
| def [`best_first`](#pencilmark.sources._sp_translate.best_first) | All combinations (one item per list), in order of increasing total rank (sum of each item's position in its… |
| def [`infer`](#pencilmark.sources._sp_translate.infer) | Infer what each visual element class means. |
| def [`rebuild`](#pencilmark.sources._sp_translate.rebuild) | Rebuild a verified puzzle from a stored inference reading (SudokuPad or f-puzzles payload). |

### `def fog_of(P, p, idx, inside)` {#pencilmark.sources._sp_translate.fog_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L126)

SudokuPad fog of war (docs/research/fog_mechanics.md): lit cells from FOGLIGHT cages ("foglight" or "foglight: r1c1,r2c1") and puzzle.foglight; triggereffect cellvalue -> foglight effects as triggers (a puzzle with triggers has no 3x3 reveal). None when the puzzle has no fog, or fog this reads does not cover.

### `def unmodelled_rules(text, chaos_ok=False)` {#pencilmark.sources._sp_translate.unmodelled_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L172)

the mechanics of UNMODELLED_RULES a (lower-case) rules text names, as refusal reasons; chaos_ok: the reader models chaos construction itself (SudokuPad, regions to find)

### `def arrow_sight_counts_itself(text)` {#pencilmark.sources._sp_translate.arrow_sight_counts_itself}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L262)

does an arrow's own-region count include the arrow cell? ("beyond the arrow", "starting from the next cell": no)

### `def sight_counts_itself(text)` {#pencilmark.sources._sp_translate.sight_counts_itself}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L271)

does a region_sight clue count its own cell? (the rules text says so; most setters' circles do)

### `def region_statements(text)` {#pencilmark.sources._sp_translate.region_statements}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L279)

(element kind -> True (its cells share a region) / False (they lie in different regions), the sentences about regions that say something else)

### `def chaos_rules(P, p, n, rules)` {#pencilmark.sources._sp_translate.chaos_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L313)

the chaos constraint, drawn borders (dark lines along grid lines) and the region statements of the rules text, as engine constraints

### `def default_evidence(kind, rules)` {#pencilmark.sources._sp_translate.default_evidence}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L492)

the rules text describes a default-colour meaning: a sentence about a line (or naming the rule) that matches DEFAULT_EVIDENCE and says it positively ("nor can it contain any consecutive digits" is no renban)

### `def color_name(hexcol)` {#pencilmark.sources._sp_translate.color_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L514)

*No docstring.*

### `def dot_color_rules(rules)` {#pencilmark.sources._sp_translate.dot_color_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L625)

colour -> (holds, label, all given) for dots of colours other than white / black whose sentence says what they mean (the clause naming the colour: one sentence often defines every dot colour); all given: a sentence says every such pair is marked (a negative constraint). Several conditions in one clause ("sum to 10 and differ by at least 4") hold together; alternatives ("either ... or") leave the dot unread.

### `def diff_rule(sent)` {#pencilmark.sources._sp_translate.diff_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L739)

'adjacent digits differ by at least K' -> whisper key (K=5 whisper, K=4 dutch, else 'whisperK'), or None.

### `def arrow_variants(p, rules, used, unknown)` {#pencilmark.sources._sp_translate.arrow_variants}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L814)

arrows the text redefines (or adds to): custom rules over each arrow's circle c and line L

### `def custom_line(p, rule, ids)` {#pencilmark.sources._sp_translate.custom_line}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L875)

a line rule with no rule family on cells ids: custom rules (LINE_CUSTOM runs, same parity along the line) or difference pairs (neighbours one apart)

### `def other_lines_rule(rules)` {#pencilmark.sources._sp_translate.other_lines_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L948)

the line rule a sentence gives the lines no other sentence names ("numbers on all other lines are each a set of ... consecutive numbers"), or None

### `def every_line_rule(rules)` {#pencilmark.sources._sp_translate.every_line_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L959)

the line rule a sentence gives every line ("all lines are region sum lines", "every line is a renban", "an arithmetic series along each line"), or None

### `def yin_yang_reading(rules)` {#pencilmark.sources._sp_translate.yin_yang_reading}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L985)

the shading couplings a yin-yang rules text states -> [("cage" | "thermo" | "all", "odd" | "even", shaded?), ("whisper", k)] (empty: the plain frame), or None (no yin-yang, or a shading sentence not understood)

### `def add_yin_yang(p, specs, thermo_cells)` {#pencilmark.sources._sp_translate.add_yin_yang}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1052)

the shading frame and its couplings as rules of the puzzle (custom rules reading shaded())

### `def clone_groups(colour_of)` {#pencilmark.sources._sp_translate.clone_groups}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1097)

clones drawn as coloured shapes: {(r, c): colour} -> per colour with two or more connected shapes, the shapes' cells in corresponding order ([[cells of shape 1], [cells of shape 2], ...]); None when a colour's shapes differ

### `def described_line_rules(rules)` {#pencilmark.sources._sp_translate.described_line_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1125)

line rules the text describes without naming them, from sentences about a line or thread that name no colour (a puzzle with one line colour); empty when any line sentence names a colour

### `def rules_color_map(rules)` {#pencilmark.sources._sp_translate.rules_color_map}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1137)

colour word -> rule key, from sentences mentioning both; None for a colour a line sentence names with a rule this reading does not know ("brown 3-way lines: ...", 000UR7).

### `def negative_markers(rules)` {#pencilmark.sources._sp_translate.negative_markers}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1205)

Which edge-marker types carry a negative constraint ("all white dots are given", "ALL V ARE GIVEN", "negative constraint for black dots", "every domino summing to 10 is marked with an X"). Clauses saying "not all ..." never add a type; a later affirmative clause can ("Not all white dots and X are given, but ALL V ARE GIVEN" -> {v}).

### `def chess_rule(piece, t)` {#pencilmark.sources._sp_translate.chess_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1293)

anti-knight / anti-king over the whole grid (_chess_sentences)

### `def chess_other(t)` {#pencilmark.sources._sp_translate.chess_other}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1300)

a knight / king move rule the readers do not model: a sentence about the move that is neither the global rule nor a move from marked cells (KNIGHT_FROM, read by text_cell_rules)

### `def anti_sums(t)` {#pencilmark.sources._sp_translate.anti_sums}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1329)

totals no two orthogonally adjacent cells may reach, with no marker drawn for them ("No two cells which share an edge may contain digits adding to 5 or 10"; "No two orthogonally connected cells can sum to 5"). A sentence about unmarked pairs is the markers' negative constraint, read elsewhere.

### `def rule_flags(rules)` {#pencilmark.sources._sp_translate.rule_flags}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1345)

*No docstring.*

### `def negative_types(flags, overrides=None)` {#pencilmark.sources._sp_translate.negative_types}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1386)

Marker types under a negative constraint: overrides["_negative"] (iterable of MARKER_TYPES) > legacy overrides["_kropki_negative"] (bool, both dot colours) > the rules text.

### `def hls(hexcol)` {#pencilmark.sources._sp_translate.hls}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1398)

*No docstring.*

### `def line_rule_from_text(hexcol, cmap, drawn=())` {#pencilmark.sources._sp_translate.line_rule_from_text}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1410)

Rule for a line colour: exact colour-class match, else the nearest colour word in the rules text (hue within 40 degrees), else a neighbouring colour word (COLOR_NEAR) that names no drawn colour class (`drawn`: those lines own that word's rule).

### `def is_chevron(wp)` {#pencilmark.sources._sp_translate.is_chevron}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1451)

A greater-than sign drawn as a line: 3 waypoints spanning &lt; 0.9 cells with the middle (apex) off the ends' line.

### `def inequality_signs(P, n, rules)` {#pencilmark.sources._sp_translate.inequality_signs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1460)

Greater-than signs drawn as chevrons (3-point lines) or short arrows across a cell edge -> (smaller, larger) cell pairs [(r, c), (r, c)]. A chevron's apex points at the smaller digit; an arrow points at the smaller digit unless the rules say it points at the larger one.

### `def join_branches(pieces)` {#pencilmark.sources._sp_translate.join_branches}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1495)

[(colour, cells), ...] of one set rule -> the cell lists of its lines: a piece whose end lies inside another piece of the same colour is a branch of that line (one set); pieces meeting end to end, or crossing, stay separate

### `def line_items(P, n)` {#pencilmark.sources._sp_translate.line_items}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1512)

Cell lines of the puzzle: [(colour class, hex, [cells]), ...], skipping decoration: lines drawn along grid lines (all waypoints on cell corners), and white/near-white lines that trace another line (the hollow centre of a 'hollow' line). Full-length corner-to-corner diagonals come back with class 'diagonal'; lines drawn mostly along grid lines (not on corners only) with class 'offcentre' (refused).

### `def cell_of(pt)` {#pencilmark.sources._sp_translate.cell_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1550)

*No docstring.*

### `def line_cells(wp)` {#pencilmark.sources._sp_translate.line_cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1554)

*No docstring.*

### `def edge_number_rule(rules)` {#pencilmark.sources._sp_translate.edge_number_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1575)

Meaning of numbers on cell borders from the rules text (None = unknown).

### `def path_points(d)` {#pencilmark.sources._sp_translate.path_points}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1597)

an SVG path (M / L / H / V / Q / C / Z, absolute or relative) -> its subpaths as lists of [row, col] points in cell units. A quadratic curve is a rounded corner (Sudoku Maker): its control point is the corner's cell center and its end lies on the straight run to the next point, kept only where the path ends (on a cell edge it would add a cell the line does not pass); a cubic is sampled in quarter steps

### `def path_circle(d)` {#pencilmark.sources._sp_translate.path_circle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1684)

a circle drawn as a path ("M x y m r 0 a r r 0 1 0 -2r 0 a r r 0 1 0 2r 0") -> (center [row, col], diameter) in cell units, or None

### `def path_lines(P)` {#pencilmark.sources._sp_translate.path_lines}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1698)

lines drawn as SVG paths (Sudoku Maker files: `d`, no `wayPoints`) -> ordinary lines, one per subpath; a filled circle drawn as a path (a thermometer's bulb, 000PDY) -> a round overlay; other filled path shapes are no lines

### `def without_nulls(P)` {#pencilmark.sources._sp_translate.without_nulls}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1718)

the puzzle's element lists without null entries (SudokuPad skips them; some files carry them, in a list or in an element's cells / way points); the cell grid keeps its nulls, where a position matters

### `def numbers_on_circles(P)` {#pencilmark.sources._sp_translate.numbers_on_circles}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1733)

a number drawn just off an edge circle (its baseline shifted by up to 0.2 cell) is that circle's number: moved onto it and merged with it, so the pair reads as one numbered dot, not a dot plus a stray cell text

### `def branch_starts(lcs, circles)` {#pencilmark.sources._sp_translate.branch_starts}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1756)

thermometer branches drawn without a bulb: a line with no circle at either end that starts or ends on the cells of a line with a bulb (or of a branch found before) grows from there: {tuple(cells): the end it starts at (0 / -1)} (000MOO: a branch drawn from its tip back to the thermometer was read backwards)

### `def thermo_network(p, pieces, bulb_cells, unknown)` {#pencilmark.sources._sp_translate.thermo_network}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1774)

the board's thermometer strokes [(rule, drawn cells, ids)] read together. A stroke with a bulb at one end runs from it (cells numbered from the bulb). A stroke with no bulb (a branch drawn from its tip, or touching a thermometer mid-stroke: 000MOO) takes its direction from the strokes it joins: numbers spread from the bulbed strokes' cells along the bulbless strokes, every step runs to the higher number, and a stroke is split where its direction turns. Unreached strokes keep the drawn order; a step between two cells with the same number refuses.

### `def emit_line(p, rule, lc, ids, circles, rules, used, unknown, box_of, renban_pieces, thermo_cells, hexcol=None, branches=None, bulbs=None, thermo_net=None)` {#pencilmark.sources._sp_translate.emit_line}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1828)

one line read as `rule` (its drawn cells lc, their engine ids) -> the puzzle's constraints / relations / named rules; refusals go to `unknown`. Shared by the square-grid reader and boards with declared houses. branches: branch_starts() of the board's lines; bulbs: cells with a smaller round marker at their center (a thermometer's bulb drawn half a cell wide, 000GQE)

### `def translate(sp, page_text=None, overrides=None)` {#pencilmark.sources._sp_translate.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1969)

sp: decoded dict from sudokupad.fetch; page_text: the puzzle page's rules (e.g. the Logic Masters text) when the SudokuPad file has none. Returns (Puzzle, info) or (None, reason).

### `def plain_sudoku(p, n, used)` {#pencilmark.sources._sp_translate.plain_sudoku}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L2682)

nothing read beyond rows, columns, standard boxes and givens (irregular regions count as read: they are often drawn as shading)

### `def equality_cages(p, n)` {#pencilmark.sources._sp_translate.equality_cages}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L2708)

equality cages: as many low as high digits and as many even as odd digits in each cage (the middle digit of an odd-sized digit range is neither low nor high, so excluded) -> custom rules, one per cage

### `def text_cell_rules(p, n, rules, colour_cells, used)` {#pencilmark.sources._sp_translate.text_cell_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L2727)

rules on caged or coloured cells stated in the text: "digits in the cage are odd" (a parity clue on caged cells), "the cells shaded orange are the same number" (one digit; the named colour, or the only shading colour)

### `def drawn_in_grid(P, n, inside)` {#pencilmark.sources._sp_translate.drawn_in_grid}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L2816)

shapes (cell-sized or smaller, without text) and lines drawn inside the grid

### `def outside_clues(P, n, p, rules, used, unknown, idx, inside)` {#pencilmark.sources._sp_translate.outside_clues}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L2900)

Numbers outside the grid: little killer (with a diagonal arrow), else sandwich / x-sum / skyscraper row-column clues (whichever one rule the text names). Cells are listed from the clue inwards.

### `def fortress_cells(P, n, p, rules, used, idx, inside)` {#pencilmark.sources._sp_translate.fortress_cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3046)

Fortress: a digit in a grey cell is greater than the digits in its orthogonally adjacent white cells (grey square underlays, when the rules text says so); grey neighbours are not compared

### `def battenburg_corners(P, n, p, rules, used, idx)` {#pencilmark.sources._sp_translate.battenburg_corners}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3072)

Battenburg (checkerboard) clues: a square marker on a cell corner -> the 4 cells around it form an odd / even checkerboard; "all possible ... are given" -> the other windows do not (no inverse when the text says absence means nothing)

### `def rossini_arrows(P, n, p, rules, used)` {#pencilmark.sources._sp_translate.rossini_arrows}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3114)

Rossini: an arrow outside the grid -> the first three cells of that row / column increase in the arrow's direction ("all possible arrows are given": the other edges have none)

### `def chaos_arrows(P, n, p, rules, used, unknown, inside)` {#pencilmark.sources._sp_translate.chaos_arrows}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3217)

in-cell arrows of a chaos puzzle: border counts (ARROW_BORDER_TEXT) or own-region sight (ARROW_SIGHT_TEXT) in the arrows' directions, the arrows of one cell together; a diagonal arrow is refused

### `def marked_cells(P, n, p, rules, used, inside)` {#pencilmark.sources._sp_translate.marked_cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3248)

*No docstring.*

### `def shaded_regions(P, n, p, rules, used)` {#pencilmark.sources._sp_translate.shaded_regions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3273)

Extra all-different regions drawn as shading (asterisk, windoku, centre dot, 'grey regions'), only when the rules text names such regions. Square underlays (>= 0.8 cell) grouped by colour: a rectangle covering exactly n cells is a region; otherwise a colour's cells form one region (n cells) or n-cell connected pieces.

### `def global_custom(n, p, rules, used=None)` {#pencilmark.sources._sp_translate.global_custom}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3352)

one-off whole-grid rules (GAS) stated only in the text, as scoped custom rules -> the kinds added

### `def global_rules(n, p, rules, used)` {#pencilmark.sources._sp_translate.global_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3440)

Whole-grid rules stated only in the text. Global entropy: every 2x2 area holds a low, a middle and a high digit (thirds of 1..n). Dutch flats / flatmates: every A has a B directly above it or a C directly below it ('every 5 ... 1 above ... 9 below').

### `def parity_shapes(P, n, p, rules, used, idx, inside)` {#pencilmark.sources._sp_translate.parity_shapes}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3515)

Odd / even cells from the rules text: 'a (grey) circle contains an odd digit', 'digits in squares are even'. Only cell-centred shapes that no line, arrow or cage uses; a colour word in the sentence restricts the colour.

### `def quadruples(P, n, p, used, unknown, idx, inside)` {#pencilmark.sources._sp_translate.quadruples}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3659)

Quadruple: digits in a circle on a cell corner all appear (with multiplicity) in the four surrounding cells -> table constraint.

### `def translate_explicit(sp, rules, hidden_houses)` {#pencilmark.sources._sp_translate.translate_explicit}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3694)

Boards of any shape whose houses are declared as hidden 'unique' cages (SudokuPad convention for non-standard grids). Active cells = union of those cages; D from the rules text ('digits 1 to N') or the largest house.

### `def satisfies(p, sol)` {#pencilmark.sources._sp_translate.satisfies}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3871)

Does solution `sol` (list of digits) satisfy every rule of p?

### `def best_first(option_lists)` {#pencilmark.sources._sp_translate.best_first}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3931)

All combinations (one item per list), in order of increasing total rank (sum of each item's position in its list): the text's reading first, then readings that deviate from it in as few / as cheap places as possible.

### `def infer(sp, page_text=None, max_combos=120, node_limit=20000000, time_budget=None, solution=None)` {#pencilmark.sources._sp_translate.infer}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L3951)

Infer what each visual element class means. Evidence, strongest first: (1) the embedded solution must satisfy the reading, (2) the reading must give exactly one solution, (3) agreement with the rules text breaks ties. time_budget (s): stop trying further readings after this long and keep the best one found so far. Returns (Puzzle, info, evidence) or (None, reason, None).

### `def rebuild(sp, page_text, reading)` {#pencilmark.sources._sp_translate.rebuild}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L4071)

Rebuild a verified puzzle from a stored inference reading (SudokuPad or f-puzzles payload).

## pencilmark.sources._sp_style {#pencilmark.sources._sp_style}

[src/pencilmark/sources/_sp_style.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_style.py)

How a SudokuPad puzzle draws its rules, kept as the pencilmark-puzzle `style` of each rule ([Puzzle format](../formats/puzzle-format.md) section 7: cosmetic, never read for meaning). Each drawn element gives its cells and its look; on export a rule takes the look of the element whose cells are exactly the rule's cells (a purple renban line stays purple), and none when no element, or elements that disagree, match it.

| Name | What it does |
|---|---|
| def [`elements`](#pencilmark.sources._sp_style.elements) | [{"cells": [...], "style": {...}}] for the drawn elements of a decoded SudokuPad puzzle with a look |
| def [`apply`](#pencilmark.sources._sp_style.apply) | the pencilmark-puzzle document with `style` on each rule whose cells one drawn look matches (two looks on… |

### `def elements(sp)` {#pencilmark.sources._sp_style.elements}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_style.py#L49)

[{"cells": [...], "style": {...}}] for the drawn elements of a decoded SudokuPad puzzle with a look

### `def apply(doc, drawn)` {#pencilmark.sources._sp_style.apply}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_style.py#L165)

the pencilmark-puzzle document with `style` on each rule whose cells one drawn look matches (two looks on the same cells, wide and narrow, are a line and its outline); drawn elements on cells no rule touches become decorations (lines, shapes, words), so the artwork survives without ever being read as a rule

## pencilmark.sources.fpuzzles {#pencilmark.sources.fpuzzles}

[src/pencilmark/sources/fpuzzles.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py)

f-puzzles (f-puzzles.com) links and payloads -> puzzle JSON.

```
Link forms
    https://f-puzzles.com/?load=<lz-string>      the puzzle is in the URL (no network)
    https://f-puzzles.com/?id=<alias>            a TinyURL alias: fetch() resolves tinyurl.com/<alias> (one HEAD request)
    'fpuzzles<lz>' / 'fpuz<lz>' payloads, SudokuPad links carrying them, or the decoded f-puzzles dict itself.
Translation (_fpuz_translate) is exact for typed constraints (killer cages,
thermometers, arrows, whispers, renban, palindromes, between lines, kropki / XV (+ negative), odd / even, diagonals,
anti-knight / anti-king, disjoint groups, nonconsecutive, little killers, sandwiches, quadruples, min / max).
Generic 'line' / 'cage' / 'circle' entries (meaning only in the rules text), fog of war, indexers -> NotSupportedError,
unless reading= gives the line kinds per colour or infer=True searches them with the solver (slow).
```

payload_of(url) -> 'fpuzzles...' | None      decode(x, fetch=False) -> f-puzzles dict

```
fetch(short_link) -> f-puzzles dict           translate(x, rules_text=None, reading=None, infer=False) -> (Puzzle, info)
to_puzzle(x, rules_text=None, reading=None, infer=False, fetch=True) -> puzzle JSON dict
```

| Name | What it does |
|---|---|
| def [`is_fpuzzles_url`](#pencilmark.sources.fpuzzles.is_fpuzzles_url) |  |
| def [`payload_of`](#pencilmark.sources.fpuzzles.payload_of) | f-puzzles URL (?load=...) -> 'fpuzzles&lt;lz-string>' or None. |
| def [`short_id`](#pencilmark.sources.fpuzzles.short_id) |  |
| def [`decode`](#pencilmark.sources.fpuzzles.decode) | f-puzzles link / payload / dict -> the f-puzzles JSON dict (grid, size, killercage, thermometer, ...). |
| def [`fetch`](#pencilmark.sources.fpuzzles.fetch) | f-puzzles ?id=&lt;alias> -> resolve tinyurl.com/&lt;alias> (one HEAD request, not followed) -> decoded dict. |
| def [`translate`](#pencilmark.sources.fpuzzles.translate) | -> (engine Puzzle (not finalized), info). |
| def [`to_puzzle`](#pencilmark.sources.fpuzzles.to_puzzle) | f-puzzles link / payload / dict -> puzzle JSON dict (title, author, rules_text, source, embedded solution). |

### `def is_fpuzzles_url(s)` {#pencilmark.sources.fpuzzles.is_fpuzzles_url}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L28)

*No docstring.*

### `def payload_of(url)` {#pencilmark.sources.fpuzzles.payload_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L32)

f-puzzles URL (?load=...) -> 'fpuzzles&lt;lz-string>' or None.

### `def short_id(url)` {#pencilmark.sources.fpuzzles.short_id}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L39)

*No docstring.*

### `def decode(x, fetch=False)` {#pencilmark.sources.fpuzzles.decode}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L44)

f-puzzles link / payload / dict -> the f-puzzles JSON dict (grid, size, killercage, thermometer, ...).

### `def fetch(short_link, http=None)` {#pencilmark.sources.fpuzzles.fetch}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L80)

f-puzzles ?id=&lt;alias> -> resolve tinyurl.com/&lt;alias> (one HEAD request, not followed) -> decoded dict.

### `def translate(x, rules_text=None, reading=None, infer=False, fetch=True)` {#pencilmark.sources.fpuzzles.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L92)

-> (engine Puzzle (not finalized), info). rules_text fills a missing 'ruleset' (it is read for negative constraints and line keywords), or gives generic lines a second wording. Raises NotSupportedError / FormatError.

### `def to_puzzle(x, rules_text=None, reading=None, infer=False, fetch=True, url=None, style=True)` {#pencilmark.sources.fpuzzles.to_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L118)

f-puzzles link / payload / dict -> puzzle JSON dict (title, author, rules_text, source, embedded solution). style: keep the colors and widths of its generic elements as the rules' `style` (cosmetic).

## pencilmark.sources._fpuz_translate {#pencilmark.sources._fpuz_translate}

[src/pencilmark/sources/_fpuz_translate.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py)

f-puzzles JSON -> engine Puzzle. Exact: f-puzzles stores constraints by type.

translate(fp) -> (Puzzle, info) or (None, reason). Supported keys: grid (givens, custom regions), killercage, thermometer, arrow, whispers, renban, palindrome, betweenline, difference/ratio/xv (+ "negative" list), odd, even, diagonal+/-, antiknight, antiking, disjointgroups, nonconsecutive, littlekillersum, sandwichsum, quadruple, minimum, maximum. Generic 'line'/'cage'/'circle' (meaning only in the rules text), fog of war, indexers and clones -> unsupported.

| Name | What it does |
|---|---|
| def [`rc`](#pencilmark.sources._fpuz_translate.rc) |  |
| def [`normalise`](#pencilmark.sources._fpuz_translate.normalise) | Lexicon pass over elements whose meaning lives in the rules text (returns a shallow copy): hidden… |
| def [`translate`](#pencilmark.sources._fpuz_translate.translate) | line_kinds: {colour: kind} reading for generic 'line' entries (see infer_lines). |
| def [`solution_of`](#pencilmark.sources._fpuz_translate.solution_of) |  |
| def [`decode_fpuz`](#pencilmark.sources._fpuz_translate.decode_fpuz) | 'fpuzzles...' / 'fpuz...' payload -> f-puzzles dict (handles URL-encoding and lz-string's base64 vs URI-safe… |
| def [`text_line_reading`](#pencilmark.sources._fpuz_translate.text_line_reading) | {colour: kind} for generic lines from the rules text: each colour the text names, or the one line rule a… |
| def [`joined_or_separate`](#pencilmark.sources._fpuz_translate.joined_or_separate) | touching segments of a set rule: one line drawn in pieces, or separate lines that meet? |
| def [`infer_lines`](#pencilmark.sources._fpuz_translate.infer_lines) | Generic f-puzzles lines: try line rules per colour, keyword-ranked by the rules text; keep the reading with… |

### `def rc(name, n)` {#pencilmark.sources._fpuz_translate.rc}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L46)

*No docstring.*

### `def normalise(fp)` {#pencilmark.sources._fpuz_translate.normalise}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L59)

Lexicon pass over elements whose meaning lives in the rules text (returns a shallow copy): hidden 'msgcorrect' cages (the success message) are dropped; numeric generic cages become killer cages when the text says cages sum (sum constraints without distinctness when it says digits may repeat); free text 'X' / 'V' / '&lt;' / '>' / '^' / 'v' placed between two adjacent cells become XV clues and inequality signs.

### `def translate(fp, line_kinds=None, join=True)` {#pencilmark.sources._fpuz_translate.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L145)

line_kinds: {colour: kind} reading for generic 'line' entries (see infer_lines). join: same-colour segments of a set rule (renban, line total) that share a cell are one line (info "_joined" when that merged any).

### `def solution_of(fp)` {#pencilmark.sources._fpuz_translate.solution_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L669)

*No docstring.*

### `def decode_fpuz(payload)` {#pencilmark.sources._fpuz_translate.decode_fpuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L677)

'fpuzzles...' / 'fpuz...' payload -> f-puzzles dict (handles URL-encoding and lz-string's base64 vs URI-safe alphabets).

### `def text_line_reading(fp)` {#pencilmark.sources._fpuz_translate.text_line_reading}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L835)

{colour: kind} for generic lines from the rules text: each colour the text names, or the one line rule a single-colour puzzle's text names or describes -> None when a colour stays unread (then the page's wording of the rules, if one was given, is tried)

### `def joined_or_separate(fp, node_limit=2000000)` {#pencilmark.sources._fpuz_translate.joined_or_separate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L900)

touching segments of a set rule: one line drawn in pieces, or separate lines that meet? -> the reading (joined first) with a unique solution, matching the embedded one when there is one; joined when neither decides

### `def infer_lines(fp, node_limit=2000000, max_combos=60)` {#pencilmark.sources._fpuz_translate.infer_lines}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L917)

Generic f-puzzles lines: try line rules per colour, keyword-ranked by the rules text; keep the reading with a unique solution (matching the embedded one). -> (Puzzle, info) or (None, reason).

## pencilmark.sources._fpuz_style {#pencilmark.sources._fpuz_style}

[src/pencilmark/sources/_fpuz_style.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_style.py)

How an f-puzzles puzzle draws its rules, as the drawn elements _sp_style.apply turns into each rule's `style` ([Puzzle format](../formats/puzzle-format.md) section 7: cosmetic, never read for meaning). f-puzzles colors only its generic elements: lines (outlineC, width), cages (outlineC), circles and rectangles (baseC, outlineC, size); the named constraints (thermometers, whispers, killer cages, ...) use the site's own look, which a renderer's defaults give.

| Name | What it does |
|---|---|
| def [`elements`](#pencilmark.sources._fpuz_style.elements) | [{"cells": [...], "style": {...}}] for the colored elements of a decoded f-puzzles dict |

### `def elements(fp)` {#pencilmark.sources._fpuz_style.elements}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_style.py#L22)

[{"cells": [...], "style": {...}}] for the colored elements of a decoded f-puzzles dict

## pencilmark.sources.penpa {#pencilmark.sources.penpa}

[src/pencilmark/sources/penpa.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/penpa.py)

penpa-edit / penpa+ links -> raw structure -> puzzle JSON (sudoku-relevant subset, exact or refused).

```
Format (from the penpa-edit source, github.com/swaroopg92/penpa-edit, docs/js/general.js load() / class_p.js):
  URL  .../penpa-edit/?m=solve|edit&p=<P>[&a=<A>][&l=...]   (also '#m=...&p=...')
  P    base64 of a RAW deflate stream (zlib wbits -15) of UTF-8 text; then the COMPRESS_SUB substitutions are undone
       in reverse order (zQ -> "pu_q", zN -> "number", ..., zO -> null, and finally zZ -> z).
  text lines  0 header 'gridtype,nx,ny,size,theta,reflect0,reflect1,canvasx,canvasy,center_n,center_n0,
                 sudoku0..3,Title: ..,Author: ..,source,rules,border,multisolution[,bg image]'  (%2C = ',', %2D = newline)
              1 space [top, bottom, left, right] (margin rows / columns outside the board)
              2 mode   3 pu_q (problem layer)   4 pu_a (answer layer, edit links)   5 centerlist (delta-coded cells)
              7/8 answer-check settings   10 version   14/15 custom colors   17 genre tags
  A    deflated solution: JSON list per element class; index 4 = ["cell,digit", ...] for number answers
       (with multisolution, a JSON list of such solutions).
Square-grid point indices (nx0 = nx + 4, ny0 = ny + 4, N = nx0 * ny0; cell (i, j) = column i, row j of the padded
grid): cells k = j * nx0 + i in [0, N); vertices N + k (bottom-right corner of cell k); edge midpoints [2N, 4N);
cell corners 4N + 4k + {0 TL, 1 TR, 2 BL, 3 BR}; compass points [8N, 12N).
```

Mapped to puzzle JSON: the board (centerlist; must be a full D x D square), given digits (normal-size numbers in board cells), regions from thick borders (lineE styles 2 / 21; the board is flood-filled across them -- D regions of D cells), killer cages (killercages + their corner sums from numberS / small numbers), thermometers (the thermo tool, bulb first), arrows (the arrow tool starting in a cell that carries a circle symbol), drawn main diagonals when the rules text mentions diagonals. Everything else -- generic lines, shading, other symbols, edge / outside / vertex numbers, pencil marks, free lines, cage outlines without a killer-cage grouping, rules-text keywords for variants that are not drawn with a supported tool -- raises NotSupportedError listing the elements. Non-square grid types (hex, tri, iso, ...) and pre-v2 links are refused.

```
    decode(link_or_payload) -> dict      to_puzzle(link_or_payload_or_decoded) -> puzzle JSON dict
```

| Name | What it does |
|---|---|
| def [`is_penpa_url`](#pencilmark.sources.penpa.is_penpa_url) |  |
| def [`params`](#pencilmark.sources.penpa.params) | '...?m=solve&p=..&a=..' or '#m=..' -> {key: value} (values untouched, like penpa's own split on '&' / '='). |
| def [`decode`](#pencilmark.sources.penpa.decode) | penpa link (or the bare p= value) -> {"format": "penpa", "mode": "solve"\|"edit", "gridtype", "nx", "ny",… |
| def [`translate`](#pencilmark.sources.penpa.translate) | -> (engine Puzzle, info, decoded). |
| def [`to_puzzle`](#pencilmark.sources.penpa.to_puzzle) | penpa link / p= value / decoded dict -> puzzle JSON dict (title, author, rules_text, source, a= solution). |

### `def is_penpa_url(s)` {#pencilmark.sources.penpa.is_penpa_url}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/penpa.py#L160)

*No docstring.*

### `def params(link)` {#pencilmark.sources.penpa.params}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/penpa.py#L169)

'...?m=solve&p=..&a=..' or '#m=..' -> {key: value} (values untouched, like penpa's own split on '&' / '=').

### `def decode(link_or_payload)` {#pencilmark.sources.penpa.decode}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/penpa.py#L192)

penpa link (or the bare p= value) -> {"format": "penpa", "mode": "solve"|"edit", "gridtype", "nx", "ny", "space", "header", "title", "author", "rules", "source_link", "multisolution", "pu_q", "pu_a", "centerlist" (cell indices), "version", "tags", "solution_raw"}.

### `def translate(x, rules_text=None)` {#pencilmark.sources.penpa.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/penpa.py#L286)

-> (engine Puzzle, info, decoded). rules_text: the rules from the page that links the puzzle (used together with the rules stored in the link). A rules text is required (hidden rules cannot be excluded otherwise); killer cages are read as sums only when it speaks of sums / totals / killer. Raises NotSupportedError with every element it cannot map exactly.

### `def to_puzzle(x, rules_text=None, url=None)` {#pencilmark.sources.penpa.to_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/penpa.py#L591)

penpa link / p= value / decoded dict -> puzzle JSON dict (title, author, rules_text, source, a= solution).

## pencilmark.sources.lmd {#pencilmark.sources.lmd}

[src/pencilmark/sources/lmd.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py)

Logic Masters Deutschland (logic-masters.de) puzzle portal: a polite client + parsers + link -> puzzle JSON.

Politeness: robots.txt is fetched first and obeyed (urllib.robotparser; today it disallows /Raetselportal/Benutzer/, /Statistik/ and /Suche/erweitert.php -- this client only reads Raetsel/zeigen.php, Raetsel/loeserliste.php and Suche/einfach.php), one request at a time, >= 2.5 s apart (LMD answers 503 when hit faster), an identifying User-Agent (pencilmark.sources._common.USER_AGENT; override with PENCILMARK_UA), 30 s timeouts, at most one retry.

listing(page=0, sort="oft") -> {"rows": [{rank, id, title, author, date, solved, difficulty, rating}], "last_page"}

```
puzzle(lmd_id, solvers=False) -> {id, title, author, published, difficulty, rating, solved, observed, labels, tags,
                                  text (rules / page text), links: {sudokupad, fpuzzles, penpa, short, other},
                                  comments, is_sudoku[, solvers]}
parse_puzzle(lmd_id, html) / parse_listing(html)   (offline parsers; e.g. on cached pages)
to_puzzle(lmd_id_or_record, resolve_short=True) -> puzzle JSON from the first linked puzzle that converts
                                                   (SudokuPad > f-puzzles > penpa), with the page text as rules.
```

| Name | What it does |
|---|---|
| def [`classify_links`](#pencilmark.sources.lmd.classify_links) | -> {"sudokupad", "fpuzzles", "penpa", "short", "other"} (sorted, de-duplicated). |
| def [`parse_puzzle`](#pencilmark.sources.lmd.parse_puzzle) | Puzzle page HTML -> record (None when the page holds no puzzle). |
| def [`parse_solvers`](#pencilmark.sources.lmd.parse_solvers) | solver-list page HTML -> [(name, time)] |
| def [`parse_listing`](#pencilmark.sources.lmd.parse_listing) | search listing page HTML -> (rows, last_page); last_page is None without paging links |
| def [`listing`](#pencilmark.sources.lmd.listing) | One page (20 puzzles) of the portal's basic search; sort 'oft' = most often solved (LMD's own sort keys). |
| def [`fetch_page`](#pencilmark.sources.lmd.fetch_page) | HTML of a puzzle page; Error for an id that is not an LMD puzzle id |
| def [`puzzle`](#pencilmark.sources.lmd.puzzle) | Fetch and parse one puzzle page (+ the solver list when solvers=True: one more request). |
| def [`lmd_id_of`](#pencilmark.sources.lmd.lmd_id_of) | the 6-character puzzle id in a logic-masters.de puzzle or solver-list URL, else None |
| def [`resolve_short`](#pencilmark.sources.lmd.resolve_short) | URL-shortener link -> its redirect target (one HEAD request, redirect not followed); None on failure. |
| def [`candidate_links`](#pencilmark.sources.lmd.candidate_links) | Puzzle links of a record in conversion order: SudokuPad, f-puzzles, penpa (short links resolved and sorted… |
| def [`to_puzzle`](#pencilmark.sources.lmd.to_puzzle) | LMD id (fetches the page) or a parsed record -> puzzle JSON of the first linked puzzle that converts, with… |

### `def classify_links(urls)` {#pencilmark.sources.lmd.classify_links}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L43)

-> {"sudokupad", "fpuzzles", "penpa", "short", "other"} (sorted, de-duplicated).

### `def parse_puzzle(pid, h)` {#pencilmark.sources.lmd.parse_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L62)

Puzzle page HTML -> record (None when the page holds no puzzle). plus 'links' (all external puzzle links, incl. penpa on any host and URL-shortener links).

### `def parse_solvers(h)` {#pencilmark.sources.lmd.parse_solvers}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L104)

solver-list page HTML -> [(name, time)]

### `def parse_listing(h)` {#pencilmark.sources.lmd.parse_listing}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L114)

search listing page HTML -> (rows, last_page); last_page is None without paging links

### `def listing(page=0, sort='oft', http=None)` {#pencilmark.sources.lmd.listing}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L133)

One page (20 puzzles) of the portal's basic search; sort 'oft' = most often solved (LMD's own sort keys).

### `def fetch_page(lmd_id, http=None)` {#pencilmark.sources.lmd.fetch_page}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L140)

HTML of a puzzle page; Error for an id that is not an LMD puzzle id

### `def puzzle(lmd_id, solvers=False, http=None)` {#pencilmark.sources.lmd.puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L147)

Fetch and parse one puzzle page (+ the solver list when solvers=True: one more request).

### `def lmd_id_of(url)` {#pencilmark.sources.lmd.lmd_id_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L157)

the 6-character puzzle id in a logic-masters.de puzzle or solver-list URL, else None

### `def resolve_short(url, http=None)` {#pencilmark.sources.lmd.resolve_short}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L165)

URL-shortener link -> its redirect target (one HEAD request, redirect not followed); None on failure.

### `def candidate_links(rec, resolve_short_links=True, http=None)` {#pencilmark.sources.lmd.candidate_links}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L173)

Puzzle links of a record in conversion order: SudokuPad, f-puzzles, penpa (short links resolved and sorted in).

### `def to_puzzle(lmd_id_or_record, resolve_short=True, infer=False, http=None)` {#pencilmark.sources.lmd.to_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/lmd.py#L186)

LMD id (fetches the page) or a parsed record -> puzzle JSON of the first linked puzzle that converts, with the page text as the rules text. Raises NotSupportedError with every link's reason when none converts.

## pencilmark.sources.coach {#pencilmark.sources.coach}

[src/pencilmark/sources/coach.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py)

sudoku.coach (sudoku.coach/en/s/&lt;id>) puzzles -> pencilmark-puzzle documents, the setter's look kept as `style`.

```
Forms
    https://sudoku.coach/en/s/<id>     a puzzle page: fetch() reads its embedded record (one GET of the page)
    'SCv7_32_<base32>'                 the payload itself: base32 (alphabet 0-9a-v) of zlib-deflated JSON
    a record dict                      {"sudoku": <payload>, "solution", "name", "author", "description", ...} as the
                                       page embeds it (`mainInitData.specificSudoku`)
Older payloads (SCv2..SCv6, positional) are refused with NotSupportedError.
```

The JSON: gridSize, givenDigits (one character per cell), regions (missing: standard boxes, [] none, else one region number per cell), givenConstraints [{type, segments: [{cells, parameters}], settings}], colours + givenColours (cell colours, several per cell possible). Cells are 0-based indices r \* N + c; cosmetic types give [x, y] points in cell units. Every constraint type maps to a rule family (to_document); a type with no family, a cage sum that is not a number, rules stated only in the description (`custom_constraints`) are refused, never dropped. Settings that carry meaning (a whisper's difference, a negative constraint) become rules; the rest is the cosmetic `style` of each rule, and the cosmetic types and cell colours become `decorations`.

decode(x) -> {"format": "SCv7", "puzzle": &lt;JSON>, "meta": {...}}     fetch(link_or_id) -> record dict

```
to_document(decoded, *, check_solution=True) -> pencilmark-puzzle dict
read(x, *, fetch=True) -> pencilmark-puzzle dict (decode + to_document; a link is fetched)
```

| Name | What it does |
|---|---|
| def [`is_coach_url`](#pencilmark.sources.coach.is_coach_url) | True for a sudoku.coach link |
| def [`puzzle_id`](#pencilmark.sources.coach.puzzle_id) | sudoku.coach link or bare id -> the id ('LW4k') |
| def [`decode_payload`](#pencilmark.sources.coach.decode_payload) | 'SCv7_32_...' -> the puzzle JSON dict. |
| def [`decode`](#pencilmark.sources.coach.decode) | Payload / record dict / the payload's JSON / decoded dict -> {"format": "SCv7", "puzzle": &lt;JSON>, "meta":… |
| def [`record_of_page`](#pencilmark.sources.coach.record_of_page) | the puzzle record a sudoku.coach page embeds (`mainInitData.specificSudoku`) |
| def [`fetch`](#pencilmark.sources.coach.fetch) | sudoku.coach link or id -> the page's puzzle record (one GET of the page, identifying User-Agent). |
| def [`colour`](#pencilmark.sources.coach.colour) | coach colour (a name of the app's palette or '#rrggbb[aa]') -> '#rrggbb', or None |
| def [`style_of`](#pencilmark.sources.coach.style_of) | coach settings -> rule style. |
| def [`outline`](#pencilmark.sources.coach.outline) | the closed outlines (corner points [y, x], clockwise) of a set of cell indices |
| def [`to_document`](#pencilmark.sources.coach.to_document) | Decoded sudoku.coach puzzle (decode()) -> pencilmark-puzzle dict (format_version 1). |
| def [`read`](#pencilmark.sources.coach.read) | sudoku.coach link / id / payload / record -> pencilmark-puzzle dict (a link or id is fetched: one request). |

### `def is_coach_url(s)` {#pencilmark.sources.coach.is_coach_url}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L77)

True for a sudoku.coach link

### `def puzzle_id(x)` {#pencilmark.sources.coach.puzzle_id}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L84)

sudoku.coach link or bare id -> the id ('LW4k')

### `def decode_payload(payload)` {#pencilmark.sources.coach.decode_payload}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L97)

'SCv7_32_...' -> the puzzle JSON dict. Older versions raise NotSupportedError.

### `def decode(x)` {#pencilmark.sources.coach.decode}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L135)

Payload / record dict / the payload's JSON / decoded dict -> {"format": "SCv7", "puzzle": &lt;JSON>, "meta": {id, title, author, rules_text, solution, custom_constraints}}. Links need fetch() (or read()).

### `def record_of_page(text)` {#pencilmark.sources.coach.record_of_page}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L164)

the puzzle record a sudoku.coach page embeds (`mainInitData.specificSudoku`)

### `def fetch(x, http=None)` {#pencilmark.sources.coach.fetch}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L176)

sudoku.coach link or id -> the page's puzzle record (one GET of the page, identifying User-Agent).

### `def colour(c)` {#pencilmark.sources.coach.colour}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L185)

coach colour (a name of the app's palette or '#rrggbb[aa]') -> '#rrggbb', or None

### `def style_of(settings, shape=False)` {#pencilmark.sources.coach.style_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L205)

coach settings -> rule style. Lines: colour is the line, the border its outline (the app draws the line lineThickness wide in the border colour, then lineThickness - borderThickness in the line colour). Shapes: colour is the fill, the border the shape's colour.

### `def outline(cells, n)` {#pencilmark.sources.coach.outline}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L838)

the closed outlines (corner points [y, x], clockwise) of a set of cell indices

### `def to_document(decoded, *, check_solution=True)` {#pencilmark.sources.coach.to_document}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L978)

Decoded sudoku.coach puzzle (decode()) -> pencilmark-puzzle dict (format_version 1).

**Parameters**

- `decoded` *dict* — decode()'s result, or anything decode() takes (a payload, a record dict).
- `check_solution` *bool* — When the record carries the setter's solution, refuse a reading that the solution breaks (ReadingMismatch), as the SudokuPad reader does.

**Raises**

- *NotSupportedError* — A constraint type with no rule family, rules stated only in the description, a non-numeric clue.
- *FormatError* — Malformed data.

### `def read(x, *, fetch=True, check_solution=True)` {#pencilmark.sources.coach.read}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/coach.py#L1052)

sudoku.coach link / id / payload / record -> pencilmark-puzzle dict (a link or id is fetched: one request).
