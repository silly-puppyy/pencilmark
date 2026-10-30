# pencilmark usage

## Command line

```
pencilmark rate puzzles.txt              # one line per puzzle: band, difficulty, minutes, hardest technique
pencilmark rate puzzles.txt --report     # readable summary
pencilmark rate puzzles.txt --json       # full card (sudoku-grade); add --steps for the step-by-step solve
pencilmark rate - --format '%b|%d|%m|%p|%c' < puzzles.txt
pencilmark solve puzzles.txt             # the solution, or 'not unique' / 'no solution' / 'undecided'
pencilmark json puzzles.txt              # validate + normalise to canonical puzzle JSON
pencilmark export puzzles.txt --pretty   # each puzzle as a sudoku-puzzle file (docs/FORMAT.md), canonical
pencilmark fingerprint puzzles.txt       # content fingerprint "sha256:..." per puzzle
pencilmark describe puzzles.txt          # variant name and rules, e.g. {"type": "Killer Sudoku", "rules": {...}}
```

`python -m pencilmark ...` does the same.

**Input:** one puzzle per line. Each line can be any of these:
- a classic string, with `.` or `0` for blanks, or a [sudokuwiki.org](https://www.sudokuwiki.org/) packed string (`S9B…`, `J9B…`, `L9B…`, …;
  see docs/INTEROP.md);
- a JSON object in the `pencilmark.puzzle_json` format (variants, multi-grids, rules);
- a `sudoku-puzzle` object: the exchange format, format_version 1 (docs/FORMAT.md);
- a sample-pack line `{"puzzle": ..., "grade": ...}`;
- a path to a `.json` file.

Metadata (title, author, source, date, ...) lives in an optional `"meta"` object in both JSON formats. It is never
used for solving or rating; `pencilmark json` and `to_export` keep it.

In the exchange format, whole-board pair rules are `neighbours` rules (`{"type": "neighbours", "kind": "antiknight"}`,
or an operator with `where` and `except`), and "all clues shown" is a `negative` rule (`{"type": "negative", "of": "xv"}`);
see docs/FORMAT.md section 6.

**Format fields:**

| Field | Meaning |
|---|---|
| `%d` | difficulty |
| `%m` | minutes |
| `%p` | 80th-percentile minutes |
| `%b` | band |
| `%h` | hardest technique met |
| `%c` | contents chips, band > 0, with uses |
| `%n` | issue codes |
| `%s` | status |
| `%u` | unique? |
| `%i` | line number |

Other options: `-j N` rates N puzzles in parallel (output stays in input order); `--max-seconds N` caps the contents
search; `--computer` allows computer search (forcing chains, trial); `--allow-guessing` guesses where no technique applies
(band Unknown) instead of proving by full search (Trial and error, Extreme).

## Python

```python
import pencilmark

card  = pencilmark.rate("....4.8.3.6...8..2...")    # classic string, puzzle JSON (dict or str), sudoku-puzzle dict,
                                                    #   a sample-pack line {"puzzle": ...}, or a path to a .json file
card["difficulty"], card["time"], card["band"], card["contains"]
card  = pencilmark.rate(puzzle, steps=True, max_seconds=60, mode="human")   # mode="computer" allows chains / trial
cards = pencilmark.rate_many(puzzles, jobs=4)       # input order kept; a failing puzzle gives {"error": ...}
card  = pencilmark.rate(puzzle, se=True)            # + card["se"] = {"er", "ep", "ed", "scale"}: Sudoku Explainer-style
                                                    #   ratings from our route
sol   = pencilmark.solve(puzzle)                    # digits; raises NotUnique / NoSolution (Undecided if the search
                                                    #   hits its limit and OR-Tools is not installed)
exp   = pencilmark.to_export(puzzle, title="Escargot", author="Arto Inkala", source="example.org", id="42")
                                                    # metadata goes under exp["meta"]; meta={...} takes a dict of any keys;
                                                    #   an empty meta.type / rules_text is filled from describe()
text  = pencilmark.dumps(exp)                       # canonical text (one grid row per line, one rule per line)
fp    = pencilmark.fingerprint(puzzle)              # "sha256:..." of rules + grid + givens (no meta / style / solution)
pencilmark.validate(exp)                            # strict reading checks; raises pencilmark.FormatError
pencilmark.describe(puzzle)                         # {"type": "Killer Sudoku", "rules": {"Sudoku": "...", "Killer": "..."}}
pencilmark.to_ipuz(puzzle)                          # optional other formats (docs/INTEROP.md): ipuz 2 export,
pencilmark.from_string("S9B...")                    #   plain / sudokuwiki.org strings -> sudoku-puzzle dict
pencilmark.to_string(puzzle, "sudokuwiki")          #   ... and back ("plain" for classic strings)
p     = pencilmark.load(puzzle)                     # the engine's Puzzle object
```
`rate` returns the same card as `pencilmark rate --json`.

## Generator

```python
import pencilmark
r = pencilmark.generate({"format": "sudoku-spec", "format_version": 1,
                         "board": {"rows": 9, "cols": 9}, "digits": 9,
                         "rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]},
                                   {"type": "cage", "count": "auto"}],
                         "where": {"band": "Hard"}, "limits": {"time": 300, "seed": 1}})
r["puzzle"], r["card"], r["info"]       # sudoku-puzzle (with solution), sudoku-grade card, run details
```

The request is a `sudoku-spec` (docs/SPEC.md): board, rule templates with counts, givens count, symmetry, targets on
the card (`band`, `difficulty`, `contains`, `elements`), `limits` and `fields`. Parts reserved for later versions are
refused with a message naming them, never ignored. Example requests: `docs/examples/specs/`.

## Example
```
$ echo '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......' | pencilmark rate - --report
#1  Medium  -  difficulty 5.9  -  time 10.7 min (80% of players within 16.4 min)
   contains: Naked Pair (or PPR/HPR), X-Wing (or KTE/SCL)
```

## The card
- **difficulty** is how hard the puzzle *feels* to a human, independent of its size (exact definitions of all three
  numbers: [PHILOSOPHY.md](PHILOSOPHY.md)). The scale is continuous: 0 means one empty cell, and there is no ceiling.
  - On classics it follows Andrew Stuart's sudokuwiki.org scale.
  - A typical newspaper medium is about 5; [fed-sudoku](https://www.fed-sudoku.eu/) "hard" is about 6.5.
  - It measures effort and is independent of the band: variants often sit above Andrew Stuart's range for their band, because the same techniques are harder to find there (clues to read, sums to track).
- **time** is the predicted median time in minutes over the people who solve puzzles like it.
  - The median 9x9 classic takes about 12 min.
  - On request, `time_mean` or any percentile `time_pNN` (for example `time_p80`: 80% of players finish within it; `time_p20`: the fastest fifth) over today's players.
  - Typical error: about 20-26%.
- **band** is fixed by the techniques required on the easiest route (Very Easy ... Extreme).
  - Guessing is off by default: where no technique applies, the engine proves an elimination by full search (Trial and error, Extreme).
  - `allow_guessing=True` (CLI `--allow-guessing`) guesses there instead; the band is then **Unknown**.
- Speed: only requested fields are computed. Without `contains` (and `issues`), the card skips the search for the shortest
  technique list entirely, about 3x faster for the same band, difficulty and time: `fields=["difficulty", "time", "band"]`.
  `alternatives=False` (CLI `--no-alternatives`) keeps `contains` but skips the search for interchangeable techniques
  (one code per chip, about 1.2x faster). The generator screens candidates this way and makes the result's card in full.
- **contains** lists what a solver meets going easy to hard.
  - A chip like `XWG/KTE/SCL` means each of those alone also works at that point.
  - Singles are listed without counts.
- **issues** (on request, `fields=[..., "issues", "reject"]`) are publishing checks (`spike`, `decorative`, `barely_used`, `redundant`, `trivial`, `tedious`,
  `uniqueness`, `trial`), severity `reject` or `warning`; rule problems name the offending rules by index in the exported
  puzzle (`"rules": [3, 4]`). **reject** is `true` when any issue is a reject.
- Fields: `difficulty`, `time`, `band`, `contains` by default (`grader`, `format`, `format_version`
  always); `rate(puzzle, fields=[...])` / `pencilmark rate --fields ...` takes key names and adds `issues` / `reject`,
  `band_index`, `time_mean` / `time_pNN`, `steps`, `se`, `describe`, `symmetry`. `explain="short"` / `"teach"` (CLI `--explain`) adds step
  explanations. Every key is listed in docs/GRADE.md.

## Other sites' labels on this scale
Median difficulty, interquartile range in brackets. Each site rates for its own audience and neighbouring levels
overlap a lot, so treat this as a rough conversion.

| Source label | Our difficulty | Notes |
|---|---|---|
| fed-sudoku easy | 3.9 (3.4–4.3) | sudokuwiki 3.9 |
| fed-sudoku medium | 5.1 (4.6–5.9) | sudokuwiki 5.2 |
| fed-sudoku hard | 6.5 (6.2–7.0) | sudokuwiki 6.7 |
| [sudoku.coach](https://sudoku.coach/) level 0 / 1 / 2 | 0.6 / 1.7 / 2.8 | classics |
| sudoku.coach level 3 / 4 / 5 | 3.7 / 5.2 / 5.8 | |
| sudoku.coach level 6 / 7 / 8 | 6.1 / 6.7 / 7.3 | |
| sudoku.coach level 9 / 10 / 11 | 8.7 / 11.5 / 11.9 | |
| [Logic Masters](https://logic-masters.de/) 1 star | 8.8 (6.3–10.1) | variants; LMD's "easy" is already hard |
| Logic Masters 2 stars | 11.1 (10.1–12.6) | |
| Logic Masters 3 stars | 13.0 (11.5–13.7) | |
| Logic Masters 4–5 stars | 13.8 (12.6–14.9) | n 56; stars 4 and 5 overlap |


## Speed
- Classics take 0.04-0.2 s.
- Typical variants take about 0.5-1.5 s.
- A few very hard killers (huge cage algebra) can take 15-30 min while the contents list is minimised.
- `--max-seconds N` (Python: `max_seconds=N`) caps the whole call. The card then says `completed: false`; if the limit
  passed while the contents list was being minimised, the grade stands but the list may not be minimal or may miss joint chips. Without the cap the result is deterministic.

## Uniqueness
Puzzles are checked with the engine's exhaustive search. If that search hits its node limit, [OR-Tools](https://developers.google.com/optimization) [CP-SAT](https://developers.google.com/optimization/cp/cp_solver) is used
when installed (`pip install "pencilmark[verify]"`); otherwise the puzzle counts as undecided.

## Technique codes (the contents chips)
Each chip is a 3-letter code named by the most specific shape found, e.g. SKY, not X-Chain. Read a chip with its subset table:
- If you know a technique listed under "special case of", you can do the chip. For example, an X-Wing (XWG) is a special case of a Skyscraper (SKY).
- A joint chip like `SKY/KTE` means that *either* technique gets you through at that point. Joint chips are only listed for different
  families in the same band.

Machine-readable version: `pencilmark/data/technique_bands.csv` (installed with the package).

| Code | Technique | Band | Special case of |
|---|---|---|---|
| FHS | Full House | Very Easy | HSI, NSI |
| HSI | Hidden Single | Very Easy |  |
| NSI | Naked Single | Very Easy |  |
| LSI | Line / dot read without notes | Very Easy |  |
| CSI | Last cell of a cage / line (variant) | Very Easy |  |
| CFX | Clue facts (no 5 on a whisper) (variant) | Very Easy |  |
| PPR | Pointing / Box-Line Reduction | Easy |  |
| SNY | Snyder notation (box pairs) | Easy |  |
| NPR | Naked Pair | Easy |  |
| HPR | Hidden Pair | Easy |  |
| MSI | Pair / triple in the head | Easy | NPR, NTR |
| CGC | Killer cage combinations (variant) | Easy |  |
| SUM | Sum clue combinations (variant) | Easy |  |
| ARW | Arrow sums (variant) | Easy |  |
| RNB | Renban runs (variant) | Easy |  |
| IOU | Innies & outies (rule of 45) (variant) | Easy |  |
| PWC | Pair rules (dots, whispers, anti-knight...) (variant) | Easy |  |
| TBL | Allowed combinations of a rule (variant) | Easy |  |
| LNR | Line ranges (thermo / whisper bounds) (variant) | Easy |  |
| LNS | Local line scan (variant) | Easy |  |
| LNC | Line classes (low/high, odd/even) (variant) | Easy |  |
| SWC | Sandwich sums (variant) | Easy |  |
| XSC | X-Sums | Easy |  |
| SKC | Skyscraper clues (variant) | Easy |  |
| CNT | Counting clues | Easy |  |
| NTR | Naked Triple | Easy |  |
| HTR | Hidden Triple | Easy |  |
| CSH | Clue shape (a whisper 4 between two 9s) (variant) | Easy |  |
| XWG | X-Wing | Medium | AAC, AIC, FRK, FXW, SKY, SWF, TUR, XCL |
| SKY | Skyscraper | Medium | AAC, AIC, TUR, XCL |
| KTE | 2-String Kite | Medium | AAC, AIC, TUR, XCL |
| TUR | Turbot Fish | Medium | AAC, AIC, XCL |
| ERE | Empty Rectangle | Medium | AAC, AIC, TUR, XCL |
| SCL | Simple Colouring | Medium | AAC, AIC, XCL |
| FXW | Finned X-Wing | Medium | AAC, AIC, XCL |
| EQD | Equal cells (same digit) | Medium |  |
| DGC | Digit counting (variant) | Medium |  |
| LOL | Set theory (law of leftovers) | Medium |  |
| IOV | Innies & outies as a virtual cage | Medium |  |
| IOM | Innies & outies over several houses | Medium |  |
| EQS | Equal sums (zipper / region-sum lines) (variant) | Medium |  |
| CBL | Must-contain digits (cage / line) (variant) | Medium |  |
| XCL | X-Chain | Medium | AAC, AIC |
| RUL | Two rules together | Medium |  |
| IMH | Hidden regions (implied houses) | Medium |  |
| DOM | Domino pairs (dots / XV) (variant) | Medium |  |
| CLC | Odd/even & high/low counting (variant) | Medium |  |
| CCL | High/low & odd/even colouring (variant) | Medium |  |
| SBD | Min/max sum bounds (variant) | Medium |  |
| SWF | Swordfish | Hard |  |
| FSW | Finned Swordfish | Hard |  |
| YWG | Y-Wing | Hard | AAC, AIC, XYC |
| XYZ | XYZ-Wing | Hard | AAC, ALS |
| RMP | Remote Pairs | Hard | AAC, AIC, XYC |
| URC | Unique Rectangle | Hard |  |
| BUG | BUG | Hard |  |
| NQD | Naked Quad | Hard |  |
| HQD | Hidden Quad | Hard |  |
| JLF | Jellyfish | Hard |  |
| FJF | Finned Jellyfish | Hard |  |
| WXZ | WXYZ-Wing | Hard | AAC, ALS |
| XYC | XY-Chain | Hard | AAC, AIC |
| MCL | Multi-Colouring | Hard | AAC, AIC, XCL |
| FRK | Franken / Mutant fish | Hard |  |
| 3DM | 3D Medusa | Hard |  |
| CRP | Chute Remote Pairs | Hard |  |
| MCH | Short chain in the head | Hard |  |
| SAL | Sum algebra (house totals) (variant) | Hard |  |
| PHI | Phistomefel ring | Hard | LOL |
| PHV | Phistomefel variant | Hard | LOL |
| WEI | Weighted sums | Hard |  |
| BAN | Band set theory with cages (variant) | Hard |  |
| FIR | Fireworks | Hard |  |
| GSY | Gurth's Symmetry | Hard |  |
| CAL | Equal-digit colouring | Hard |  |
| CPS | Cage combination positions (variant) | Hard |  |
| CLI | Clique house (all-different cells) | Hard |  |
| RNS | Renban sets in a house (variant) | Hard |  |
| OCL | Outside clues together | Hard |  |
| AIC | Alternating Inference Chain | Very Hard | AAC |
| NLP | Nice Loop | Very Hard | AAC, AIC |
| ALS | ALS-XZ (almost locked sets) | Very Hard | AAC |
| AXY | ALS-XY-Wing | Very Hard | AAC, DEB |
| SDC | Sue de Coq | Very Hard |  |
| APE | Aligned Pair Exclusion | Very Hard |  |
| CAS | Case analysis | Very Hard |  |
| AAC | ALS chain | Very Hard |  |
| DEB | Death Blossom | Very Hard |  |
| EWY | Either way (case split) | Very Hard |  |
| WIF | What if… | Very Hard |  |
| STR | Short trial | Very Hard |  |
| FCH | Forcing Chains | Extreme |  |
| FNT | Forcing Nets | Extreme |  |
| NFC | Nested Forcing Chains | Extreme |  |
| NIS | Nishio | Extreme |  |
| POM | Pattern Overlay | Extreme |  |
| TRL | Trial and error | Extreme |  |
