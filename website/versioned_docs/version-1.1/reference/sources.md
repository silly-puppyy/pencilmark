---
title: "Puzzle sources"
description: "Links and payloads from SudokuPad, f-puzzles, Penpa and Logic Masters, read into puzzles."
toc_max_heading_level: 2
---

# Puzzle sources

Links and payloads from SudokuPad, f-puzzles, Penpa and Logic Masters, read into puzzles. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.sources {#pencilmark.sources}

[src/pencilmark/sources/__init__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py)

Puzzle sources: links / payloads from SudokuPad, f-puzzles, penpa-edit and Logic Masters -> puzzle JSON.

from pencilmark import sources

```
pj = sources.load("https://sudokupad.app/wjgxgaji9a")              # -> puzzle JSON dict (pencilmark.puzzle_json)
p = pencilmark.puzzle_json.from_json(pj)
```

```
load() recognises
    SudokuPad    sudokupad.app/... , app.crackingthecryptic.com/... (short ids are fetched: one API request),
                 bare 'scl...' / 'ctc...' / 'fpuzzles...' payloads, 'sudokupad:<shortid>'
    f-puzzles    f-puzzles.com/?load=... (offline), ?id=<alias> (one TinyURL HEAD request)
    penpa        any .../penpa-edit/?m=..&p=... (penpa-edit, penpa+, mirrors; offline), 'penpa:<p value>'
    LMD          logic-masters.de/Raetselportal/Raetsel/zeigen.php?id=XXXXXX or 'lmd:XXXXXX' (page fetch, robots.txt
                 obeyed, >= 2.5 s between requests), converting the first linked puzzle that translates
    shorteners   tinyurl / bit.ly / git.io / is.gd links are resolved (one HEAD request) and dispatched
    puzzle JSON  a dict / JSON text already in pencilmark.puzzle_json format is returned as is
Modules: sudokupad, fpuzzles, penpa, lmd (each with decode / to_puzzle; see their docstrings for coverage).
Errors: SourceError > DecodeError (unrecognised / undecodable), FetchError (network, robots.txt), UnsupportedPuzzle
(.elements = what could not be mapped exactly; nothing is silently dropped), VerificationError (verify=True).
```

| Name | What it does |
|---|---|
| class [`VerificationError`](#pencilmark.sources.VerificationError) | verify=True: the translated puzzle is not unique, or contradicts its embedded solution. |
| def [`detect`](#pencilmark.sources.detect) | -> 'puzzle_json' \| 'sudokupad' \| 'fpuzzles' \| 'penpa' \| 'lmd' \| 'short' \| None. |
| def [`load`](#pencilmark.sources.load) | Link / payload / decoded dict -> puzzle JSON dict. |
| def [`check`](#pencilmark.sources.check) | Unique solution (and equal to pj['solution'] when present) or VerificationError. |

### `class VerificationError(SourceError)` {#pencilmark.sources.VerificationError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L29)

verify=True: the translated puzzle is not unique, or contradicts its embedded solution.

### `def detect(x)` {#pencilmark.sources.detect}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L33)

-> 'puzzle_json' | 'sudokupad' | 'fpuzzles' | 'penpa' | 'lmd' | 'short' | None.

### `def load(x, rules_text=None, infer=False, fetch=True, verify=False, time_limit=30.0)` {#pencilmark.sources.load}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L79)

Link / payload / decoded dict -> puzzle JSON dict. rules_text: the rules from the page that links the puzzle (used where the puzzle file has none, and for penpa's rule screening). infer=True lets SudokuPad / f-puzzles search line readings with the solver (slow). fetch=False refuses anything that needs a network request. verify=True checks uniqueness (and the embedded solution) with CP-SAT and raises VerificationError otherwise.

### `def check(pj, time_limit=30.0)` {#pencilmark.sources.check}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/__init__.py#L119)

Unique solution (and equal to pj['solution'] when present) or VerificationError. Returns the solution string.

## pencilmark.sources._common {#pencilmark.sources._common}

[src/pencilmark/sources/_common.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py)

Shared pieces of pencilmark.sources: exception types, a polite HTTP client, Puzzle -> puzzle JSON.

| Name | What it does |
|---|---|
| class [`SourceError`](#pencilmark.sources._common.SourceError) | Base class for every error raised by pencilmark.sources. |
| class [`DecodeError`](#pencilmark.sources._common.DecodeError) | The link / payload could not be recognised or decoded. |
| def [`reads`](#pencilmark.sources._common.reads) | decorator for a reader: a crash on malformed data (a missing key, a value of the wrong type, a short list)… |
| class [`FetchError`](#pencilmark.sources._common.FetchError) | A network request failed (or robots.txt forbids it). |
| class [`UnsupportedPuzzle`](#pencilmark.sources._common.UnsupportedPuzzle) | The puzzle decoded, but it uses elements / rules the translation cannot model exactly. |
| def [`unsupported_from_reason`](#pencilmark.sources._common.unsupported_from_reason) | Translator failure reason ('unsupported: a, b' or a plain reason) -> UnsupportedPuzzle. |
| class [`Http`](#pencilmark.sources._common.Http) | Sequential, polite HTTP: identifying User-Agent, timeouts, a minimum gap between requests to the same host,… |
| def [`to_puzzle_json`](#pencilmark.sources._common.to_puzzle_json) | engine Puzzle (finalized or not) -> puzzle JSON dict (pencilmark.puzzle_json.to_json); a solution string /… |

### `class SourceError(Exception)` {#pencilmark.sources._common.SourceError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L24)

Base class for every error raised by pencilmark.sources.

### `class DecodeError(SourceError)` {#pencilmark.sources._common.DecodeError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L28)

The link / payload could not be recognised or decoded.

### `def reads(source)` {#pencilmark.sources._common.reads}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L32)

decorator for a reader: a crash on malformed data (a missing key, a value of the wrong type, a short list) becomes a DecodeError naming the source and the problem

### `class FetchError(SourceError)` {#pencilmark.sources._common.FetchError}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L49)

A network request failed (or robots.txt forbids it).

### `class UnsupportedPuzzle(SourceError)` {#pencilmark.sources._common.UnsupportedPuzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L53)

The puzzle decoded, but it uses elements / rules the translation cannot model exactly. .elements lists them (nothing is silently dropped).

### `def unsupported_from_reason(reason, source='')` {#pencilmark.sources._common.unsupported_from_reason}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L63)

Translator failure reason ('unsupported: a, b' or a plain reason) -> UnsupportedPuzzle.

### `class Http` {#pencilmark.sources._common.Http}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L71)

Sequential, polite HTTP: identifying User-Agent, timeouts, a minimum gap between requests to the same host, optional robots.txt checks, at most one retry (after a pause) on 429 / 5xx / network errors.

#### `def allowed(self, url)` {#pencilmark.sources._common.Http.allowed}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L88)

*No docstring.*

#### `def get_text(self, url)` {#pencilmark.sources._common.Http.get_text}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L140)

*No docstring.*

#### `def redirect_target(self, url)` {#pencilmark.sources._common.Http.redirect_target}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L143)

Location header of a redirecting URL (HEAD, not followed) -- resolves TinyURL-style short links.

### `def to_puzzle_json(p, solution=None, meta=None)` {#pencilmark.sources._common.to_puzzle_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_common.py#L154)

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

to_puzzle() translates with _sp_translate: line meanings come from the rules text (colour words, keywords) and SudokuPad's default palette; pass reading= (an inferred reading, e.g. from data/sudokupad/_inferred.jsonl) to reproduce a stored translation, or infer=True to search readings with the solver (slow: several CP-SAT runs). Rules the translator cannot model raise UnsupportedPuzzle (never silently dropped).

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

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L92)

SudokuPad compact JSON (unquoted keys, t/f, array elisions, bare hex colours) -> standard JSON text.

### `def expand(o)` {#pencilmark.sources.sudokupad.expand}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L154)

*No docstring.*

### `def is_sudokupad_url(s)` {#pencilmark.sources.sudokupad.is_sudokupad_url}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L162)

*No docstring.*

### `def payload_key(link)` {#pencilmark.sources.sudokupad.payload_key}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L168)

Link or bare string -> the SudokuPad key: a payload ('scl...', 'fpuzzles...') or a short id.

### `def decode_payload(payload)` {#pencilmark.sources.sudokupad.decode_payload}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L184)

'scl...' / 'ctc...' / 'fpuzzles...' / 'fpuz...' / JSON text -> {"format", "meta", "puzzle"} or None

### `def decode(link_or_payload, fetch=False)` {#pencilmark.sources.sudokupad.decode}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L226)

Link / payload / already-decoded dict -> {"format", "meta", "puzzle"}. Short links need a request: pass fetch=True (or call fetch()); otherwise DecodeError.

### `def fetch(short_link, http=None)` {#pencilmark.sources.sudokupad.fetch}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L257)

Resolve a short link / id through the SudokuPad API (one request, identifying User-Agent, 30 s timeout, at most one retry) and decode it.

### `def translate(x, page_text=None, reading=None, infer=False, fetch=True)` {#pencilmark.sources.sudokupad.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L285)

-> (engine Puzzle (not finalized), info dict). Raises UnsupportedPuzzle / DecodeError.

### `def metadata(sp)` {#pencilmark.sources.sudokupad.metadata}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L307)

title / author / rules_text / solution of a decoded puzzle (metadata cages, then the 'metadata' block).

### `def to_puzzle(x, page_text=None, reading=None, infer=False, fetch=True, url=None)` {#pencilmark.sources.sudokupad.to_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/sudokupad.py#L322)

SudokuPad link / payload / decoded dict -> puzzle JSON dict (pencilmark.puzzle_json format) with title, author, rules_text, source (link) and the embedded solution when it has one digit per cell.

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
| def [`color_name`](#pencilmark.sources._sp_translate.color_name) |  |
| def [`diff_rule`](#pencilmark.sources._sp_translate.diff_rule) | 'adjacent digits differ by at least K' -> whisper key (K=5 whisper, K=4 dutch, else 'whisperK'), or None. |
| def [`rules_color_map`](#pencilmark.sources._sp_translate.rules_color_map) | colour word -> rule key, from sentences mentioning both. |
| def [`negative_markers`](#pencilmark.sources._sp_translate.negative_markers) | Which edge-marker types carry a negative constraint ("all white dots are given", "ALL V ARE GIVEN",… |
| def [`rule_flags`](#pencilmark.sources._sp_translate.rule_flags) |  |
| def [`negative_types`](#pencilmark.sources._sp_translate.negative_types) | Marker types under a negative constraint: overrides["_negative"] (iterable of MARKER_TYPES) > legacy… |
| def [`hls`](#pencilmark.sources._sp_translate.hls) |  |
| def [`line_rule_from_text`](#pencilmark.sources._sp_translate.line_rule_from_text) | Rule for a line colour: exact colour-class match, else the nearest colour word in the rules text (hue within… |
| def [`is_chevron`](#pencilmark.sources._sp_translate.is_chevron) | A greater-than sign drawn as a line: 3 waypoints spanning &lt; 0.9 cells with the middle (apex) off the ends'… |
| def [`inequality_signs`](#pencilmark.sources._sp_translate.inequality_signs) | Greater-than signs drawn as chevrons (3-point lines) or short arrows across a cell edge -> (smaller, larger)… |
| def [`line_items`](#pencilmark.sources._sp_translate.line_items) | Cell lines of the puzzle: [(colour class, hex, [cells]), ...], skipping decoration: lines drawn along grid… |
| def [`cell_of`](#pencilmark.sources._sp_translate.cell_of) |  |
| def [`line_cells`](#pencilmark.sources._sp_translate.line_cells) |  |
| def [`edge_number_rule`](#pencilmark.sources._sp_translate.edge_number_rule) | Meaning of numbers on cell borders from the rules text (None = unknown). |
| def [`without_nulls`](#pencilmark.sources._sp_translate.without_nulls) | the puzzle's element lists without null entries (SudokuPad skips them; some files carry them, in a list or… |
| def [`translate`](#pencilmark.sources._sp_translate.translate) | sp: decoded dict from sudokupad.fetch; page_text: the puzzle page's rules (e.g. |
| def [`outside_clues`](#pencilmark.sources._sp_translate.outside_clues) | Numbers outside the grid: little killer (with a diagonal arrow), else sandwich / x-sum / skyscraper… |
| def [`shaded_regions`](#pencilmark.sources._sp_translate.shaded_regions) | Extra all-different regions drawn as shading (asterisk, windoku, centre dot, 'grey regions'), only when the… |
| def [`global_rules`](#pencilmark.sources._sp_translate.global_rules) | Whole-grid rules stated only in the text. |
| def [`parity_shapes`](#pencilmark.sources._sp_translate.parity_shapes) | Odd / even cells from the rules text: 'a (grey) circle contains an odd digit', 'digits in squares are even'. |
| def [`quadruples`](#pencilmark.sources._sp_translate.quadruples) | Quadruple: digits in a circle on a cell corner all appear (with multiplicity) in the four surrounding cells… |
| def [`translate_explicit`](#pencilmark.sources._sp_translate.translate_explicit) | Boards of any shape whose houses are declared as hidden 'unique' cages (SudokuPad convention for… |
| def [`satisfies`](#pencilmark.sources._sp_translate.satisfies) | Does solution `sol` (list of digits) satisfy every rule of p? |
| def [`best_first`](#pencilmark.sources._sp_translate.best_first) | All combinations (one item per list), in order of increasing total rank (sum of each item's position in its… |
| def [`infer`](#pencilmark.sources._sp_translate.infer) | Infer what each visual element class means. |
| def [`rebuild`](#pencilmark.sources._sp_translate.rebuild) | Rebuild a verified puzzle from a stored inference reading (SudokuPad or f-puzzles payload). |

### `def color_name(hexcol)` {#pencilmark.sources._sp_translate.color_name}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L132)

*No docstring.*

### `def diff_rule(sent)` {#pencilmark.sources._sp_translate.diff_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L184)

'adjacent digits differ by at least K' -> whisper key (K=5 whisper, K=4 dutch, else 'whisperK'), or None.

### `def rules_color_map(rules)` {#pencilmark.sources._sp_translate.rules_color_map}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L194)

colour word -> rule key, from sentences mentioning both.

### `def negative_markers(rules)` {#pencilmark.sources._sp_translate.negative_markers}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L236)

Which edge-marker types carry a negative constraint ("all white dots are given", "ALL V ARE GIVEN", "negative constraint for black dots", "every domino summing to 10 is marked with an X"). Clauses saying "not all ..." never add a type; a later affirmative clause can ("Not all white dots and X are given, but ALL V ARE GIVEN" -> {v}).

### `def rule_flags(rules)` {#pencilmark.sources._sp_translate.rule_flags}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L277)

*No docstring.*

### `def negative_types(flags, overrides=None)` {#pencilmark.sources._sp_translate.negative_types}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L308)

Marker types under a negative constraint: overrides["_negative"] (iterable of MARKER_TYPES) > legacy overrides["_kropki_negative"] (bool, both dot colours) > the rules text.

### `def hls(hexcol)` {#pencilmark.sources._sp_translate.hls}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L320)

*No docstring.*

### `def line_rule_from_text(hexcol, cmap)` {#pencilmark.sources._sp_translate.line_rule_from_text}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L332)

Rule for a line colour: exact colour-class match, else the nearest colour word in the rules text (hue within 40 degrees).

### `def is_chevron(wp)` {#pencilmark.sources._sp_translate.is_chevron}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L351)

A greater-than sign drawn as a line: 3 waypoints spanning &lt; 0.9 cells with the middle (apex) off the ends' line.

### `def inequality_signs(P, n, rules)` {#pencilmark.sources._sp_translate.inequality_signs}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L360)

Greater-than signs drawn as chevrons (3-point lines) or short arrows across a cell edge -> (smaller, larger) cell pairs [(r, c), (r, c)]. A chevron's apex points at the smaller digit; an arrow points at the smaller digit unless the rules say it points at the larger one.

### `def line_items(P, n)` {#pencilmark.sources._sp_translate.line_items}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L395)

Cell lines of the puzzle: [(colour class, hex, [cells]), ...], skipping decoration: lines drawn along grid lines (all waypoints on cell corners), and white/near-white lines that trace another line (the hollow centre of a 'hollow' line). Full-length corner-to-corner diagonals come back with class 'diagonal'.

### `def cell_of(pt)` {#pencilmark.sources._sp_translate.cell_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L429)

*No docstring.*

### `def line_cells(wp)` {#pencilmark.sources._sp_translate.line_cells}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L433)

*No docstring.*

### `def edge_number_rule(rules)` {#pencilmark.sources._sp_translate.edge_number_rule}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L450)

Meaning of numbers on cell borders from the rules text (None = unknown).

### `def without_nulls(P)` {#pencilmark.sources._sp_translate.without_nulls}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L466)

the puzzle's element lists without null entries (SudokuPad skips them; some files carry them, in a list or in an element's cells / way points); the cell grid keeps its nulls, where a position matters

### `def translate(sp, page_text=None, overrides=None)` {#pencilmark.sources._sp_translate.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L481)

sp: decoded dict from sudokupad.fetch; page_text: the puzzle page's rules (e.g. the Logic Masters text) when the SudokuPad file has none. Returns (Puzzle, info) or (None, reason).

### `def outside_clues(P, n, p, rules, used, unknown, idx, inside)` {#pencilmark.sources._sp_translate.outside_clues}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L910)

Numbers outside the grid: little killer (with a diagonal arrow), else sandwich / x-sum / skyscraper row-column clues (whichever one rule the text names). Cells are listed from the clue inwards.

### `def shaded_regions(P, n, p, rules, used)` {#pencilmark.sources._sp_translate.shaded_regions}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1015)

Extra all-different regions drawn as shading (asterisk, windoku, centre dot, 'grey regions'), only when the rules text names such regions. Square underlays (>= 0.8 cell) grouped by colour: a rectangle covering exactly n cells is a region; otherwise a colour's cells form one region (n cells) or n-cell connected pieces.

### `def global_rules(n, p, rules, used)` {#pencilmark.sources._sp_translate.global_rules}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1082)

Whole-grid rules stated only in the text. Global entropy: every 2x2 area holds a low, a middle and a high digit (thirds of 1..n). Dutch flats / flatmates: every A has a B directly above it or a C directly below it ('every 5 ... 1 above ... 9 below').

### `def parity_shapes(P, n, p, rules, used, idx, inside)` {#pencilmark.sources._sp_translate.parity_shapes}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1157)

Odd / even cells from the rules text: 'a (grey) circle contains an odd digit', 'digits in squares are even'. Only cell-centred shapes that no line, arrow or cage uses; a colour word in the sentence restricts the colour.

### `def quadruples(P, n, p, used, unknown, idx, inside)` {#pencilmark.sources._sp_translate.quadruples}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1205)

Quadruple: digits in a circle on a cell corner all appear (with multiplicity) in the four surrounding cells -> table constraint.

### `def translate_explicit(sp, rules, hidden_houses)` {#pencilmark.sources._sp_translate.translate_explicit}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1232)

Boards of any shape whose houses are declared as hidden 'unique' cages (SudokuPad convention for non-standard grids). Active cells = union of those cages; D from the rules text ('digits 1 to N') or the largest house.

### `def satisfies(p, sol)` {#pencilmark.sources._sp_translate.satisfies}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1314)

Does solution `sol` (list of digits) satisfy every rule of p?

### `def best_first(option_lists)` {#pencilmark.sources._sp_translate.best_first}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1374)

All combinations (one item per list), in order of increasing total rank (sum of each item's position in its list): the text's reading first, then readings that deviate from it in as few / as cheap places as possible.

### `def infer(sp, page_text=None, max_combos=120, node_limit=20000000, time_budget=None, solution=None)` {#pencilmark.sources._sp_translate.infer}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1394)

Infer what each visual element class means. Evidence, strongest first: (1) the embedded solution must satisfy the reading, (2) the reading must give exactly one solution, (3) agreement with the rules text breaks ties. time_budget (s): stop trying further readings after this long and keep the best one found so far. Returns (Puzzle, info, evidence) or (None, reason, None).

### `def rebuild(sp, page_text, reading)` {#pencilmark.sources._sp_translate.rebuild}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_sp_translate.py#L1506)

Rebuild a verified puzzle from a stored inference reading (SudokuPad or f-puzzles payload).

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
Generic 'line' / 'cage' / 'circle' entries (meaning only in the rules text), fog of war, indexers -> UnsupportedPuzzle,
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

-> (engine Puzzle (not finalized), info). rules_text fills a missing 'ruleset' (it is read for negative constraints and line keywords). Raises UnsupportedPuzzle / DecodeError.

### `def to_puzzle(x, rules_text=None, reading=None, infer=False, fetch=True, url=None)` {#pencilmark.sources.fpuzzles.to_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/fpuzzles.py#L112)

f-puzzles link / payload / dict -> puzzle JSON dict (title, author, rules_text, source, embedded solution).

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
| def [`infer_lines`](#pencilmark.sources._fpuz_translate.infer_lines) | Generic f-puzzles lines: try line rules per colour, keyword-ranked by the rules text; keep the reading with… |

### `def rc(name, n)` {#pencilmark.sources._fpuz_translate.rc}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L41)

*No docstring.*

### `def normalise(fp)` {#pencilmark.sources._fpuz_translate.normalise}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L46)

Lexicon pass over elements whose meaning lives in the rules text (returns a shallow copy): hidden 'msgcorrect' cages (the success message) are dropped; numeric generic cages become killer cages when the text says cages sum (sum constraints without distinctness when it says digits may repeat); free text 'X' / 'V' / '&lt;' / '>' / '^' / 'v' placed between two adjacent cells become XV clues and inequality signs.

### `def translate(fp, line_kinds=None)` {#pencilmark.sources._fpuz_translate.translate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L96)

line_kinds: {colour: kind} reading for generic 'line' entries (see infer_lines).

### `def solution_of(fp)` {#pencilmark.sources._fpuz_translate.solution_of}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L360)

*No docstring.*

### `def decode_fpuz(payload)` {#pencilmark.sources._fpuz_translate.decode_fpuz}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L368)

'fpuzzles...' / 'fpuz...' payload -> f-puzzles dict (handles URL-encoding and lz-string's base64 vs URI-safe alphabets).

### `def infer_lines(fp, node_limit=2000000, max_combos=60)` {#pencilmark.sources._fpuz_translate.infer_lines}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/_fpuz_translate.py#L410)

Generic f-puzzles lines: try line rules per colour, keyword-ranked by the rules text; keep the reading with a unique solution (matching the embedded one). -> (Puzzle, info) or (None, reason).

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
              7/8 answer-check settings   10 version   14/15 custom colours   17 genre tags
  A    deflated solution: JSON list per element class; index 4 = ["cell,digit", ...] for number answers
       (with multisolution, a JSON list of such solutions).
Square-grid point indices (nx0 = nx + 4, ny0 = ny + 4, N = nx0 * ny0; cell (i, j) = column i, row j of the padded
grid): cells k = j * nx0 + i in [0, N); vertices N + k (bottom-right corner of cell k); edge midpoints [2N, 4N);
cell corners 4N + 4k + {0 TL, 1 TR, 2 BL, 3 BR}; compass points [8N, 12N).
```

Mapped to puzzle JSON: the board (centerlist; must be a full D x D square), given digits (normal-size numbers in board cells), regions from thick borders (lineE styles 2 / 21; the board is flood-filled across them -- D regions of D cells), killer cages (killercages + their corner sums from numberS / small numbers), thermometers (the thermo tool, bulb first), arrows (the arrow tool starting in a cell that carries a circle symbol), drawn main diagonals when the rules text mentions diagonals. Everything else -- generic lines, shading, other symbols, edge / outside / vertex numbers, pencil marks, free lines, cage outlines without a killer-cage grouping, rules-text keywords for variants that are not drawn with a supported tool -- raises UnsupportedPuzzle listing the elements. Non-square grid types (hex, tri, iso, ...) and pre-v2 links are refused.

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

-> (engine Puzzle, info, decoded). rules_text: the rules from the page that links the puzzle (used together with the rules stored in the link). A rules text is required (hidden rules cannot be excluded otherwise); killer cages are read as sums only when it speaks of sums / totals / killer. Raises UnsupportedPuzzle with every element it cannot map exactly.

### `def to_puzzle(x, rules_text=None, url=None)` {#pencilmark.sources.penpa.to_puzzle}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/sources/penpa.py#L593)

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
| def [`fetch_page`](#pencilmark.sources.lmd.fetch_page) | HTML of a puzzle page; SourceError for an id that is not an LMD puzzle id |
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

HTML of a puzzle page; SourceError for an id that is not an LMD puzzle id

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

LMD id (fetches the page) or a parsed record -> puzzle JSON of the first linked puzzle that converts, with the page text as the rules text. Raises UnsupportedPuzzle with every link's reason when none converts.
