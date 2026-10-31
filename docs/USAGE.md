# Usage

pencilmark grades, solves, checks, converts and generates sudoku puzzles, from the command line or from Python. Every
command and function accepts the same inputs: a classic string, a puzzle file in the [puzzle format](FORMAT.md), a
site link or another app's format ([Other formats](INTEROP.md)).

## Command line

| Command | Prints, per puzzle |
|---|---|
| `pencilmark rate FILE` | band, difficulty, minutes and the hardest technique |
| `pencilmark solve FILE` | the solution, or `not unique` / `no solution` / `undecided` |
| `pencilmark count FILE` | the number of solutions (`>=1000` when it stops counting; `--limit N` to change) |
| `pencilmark describe FILE` | the variant's name and its rules in words |
| `pencilmark export FILE` | the puzzle as a canonical `sudoku-puzzle` file (`--pretty` for one rule per line) |
| `pencilmark json FILE` | the puzzle in pencilmark's internal JSON |
| `pencilmark fingerprint FILE` | a content fingerprint, `sha256:...` |
| `pencilmark generate SPEC` | a new puzzle for a [generator spec](SPEC.md) |

`FILE` holds one puzzle per line (a classic string, a JSON object, a link, or the path of a `.json` file); `-` reads
standard input. A `.json` or `.ipuz` file that holds one puzzle, or a list of puzzles, is read whole. A line that cannot
be read prints `error`, its line number and the message, and the next line goes on. `python -m pencilmark` works the
same way.

```
$ echo '....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......' | pencilmark rate - --report
#1  Hard  -  difficulty 5.9  -  time 10.7 min
   contains: Naked Pair (or Hidden Pair), X-Wing (or 2-String Kite / Simple Colouring / Short chain in the head)
```

### Options of `rate`

| Option | Effect |
|---|---|
| `--report` | readable text; `-v` adds the steps in solvers' notation, `-vv` plain sentences, `-vvv` short lessons |
| `--json` | the full card as one JSON line; `--steps` adds the steps, `--explain notation,short,teach` their explanations |
| `--fields difficulty,band,...` | only these card fields ([Grade card](GRADE.md) lists them) |
| `--format '%b\|%d\|%m'` | your own columns (below) |
| `-j N` | grade N puzzles at a time; the output keeps the input order |
| `--max-seconds N` | stop each puzzle after N seconds (the card says `completed: false`) |
| `--computer` | allow computer-style search (forcing chains, trial) as well as human techniques |
| `--allow-guessing` | guess where no technique applies (band Unknown), instead of proving by full search (Extreme) |
| `--no-alternatives` | keep `contains` but skip the search for interchangeable techniques (faster) |
| `--quality ...` | tune the publishing checks ([Check a puzzle before publishing](guides/publish-checks.md)) |

| `--format` field | Meaning |
|---|---|
| `%b` `%d` `%m` | band, difficulty, minutes |
| `%p` | minutes within which 80% of players finish |
| `%h` | hardest technique met |
| `%c` | technique chips beyond singles, with uses |
| `%n` | issue codes |
| `%s` `%u` `%i` | status, unique?, line number |

### Options of `generate`

`--seed N` and `--time S` override the spec's `limits`. The puzzle is printed as a `sudoku-puzzle` file and its band,
difficulty and time go to standard error; `--result` prints `{"puzzle", "card", "info"}` as one JSON line instead.

## Python

### Grade

```python
import pencilmark

card = pencilmark.rate("....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9.......")
card["band"], card["difficulty"], card["time"], card["contains"]
```

`rate` takes the same options as the command line: `fields=[...]`, `max_seconds=60`, `explain="short"`,
`mode="computer"` (the default is `"human"`), `allow_guessing=True`, `se=True` for a Sudoku Explainer-style rating,
`quality={...}`. `rate_many(puzzles, jobs=4)` grades a list in parallel and keeps its order; a puzzle that fails gives
`{"error": ...}` in its place.

### Solve and count

```python
solution = pencilmark.solve(puzzle)
n = pencilmark.count_solutions(puzzle)
```

`solve` returns the unique solution as a list of digits, or raises `NotUnique` or `NoSolution`.
`count_solutions` returns `{"count": 1, "exact": true}` for a proper puzzle. `count_solutions(puzzle, limit=1000)` counts up to `limit`; `exact` is
false when it stopped there. Both use the engine's exhaustive search; when that search hits its node limit,
[OR-Tools](https://developers.google.com/optimization) [CP-SAT](https://developers.google.com/optimization/cp/cp_solver)
takes over if installed (`pip install "pencilmark[verify]"`), otherwise `solve` raises `Undecided`.

### Convert and check

```python
exp = pencilmark.to_export(puzzle, title="Escargot", author="Arto Inkala")
text = pencilmark.dumps(exp)
pencilmark.validate(exp)
```

`to_export` gives the `sudoku-puzzle` dict, with its solution and with `meta.type` and `meta.rules_text` filled in from
`describe` when they are empty; `dumps` writes it in the canonical layout, one rule per line; `validate` raises
`FormatError` with the exact problem. `describe(puzzle)` names the variant and its rules, `fingerprint(puzzle)` gives
a fingerprint of the rules and grid (not the metadata), and `load(puzzle)` the engine's own object.
`from_string`, `to_string`, `from_ipuz` and `to_ipuz` convert to and from [other formats](INTEROP.md).

### Generate

```python
result = pencilmark.generate(spec)
result["puzzle"], result["card"], result["info"]
```

`spec` is a [generator spec](SPEC.md) (a dict, JSON text or a path). The result is a `sudoku-puzzle` with its solution,
its grade card and how the run went; `GenerationFailed` says why when no puzzle met the spec in time. Example specs are
in `docs/examples/specs/`.

[Python API](api.md) lists every function and argument.

## The card

- **band**: what you need to know, from Very Easy to Extreme: the hardest technique on the easiest route. Guessing is
  off by default: where no technique applies, the engine proves an elimination by full search (Trial and error,
  Extreme).
- **difficulty**: how hard the steps are to find, independent of the puzzle's size, from 0 with no ceiling. A typical
  newspaper medium is about 5, [fed-sudoku](https://www.fed-sudoku.eu/) "hard" about 6.5. Variants often sit above
  classics of the same band, because the same techniques are harder to spot among clues and sums.
- **time**: the predicted median solve time in minutes; the median classic takes about 12. Typical error 20-26%.
  `time_pNN` and `time_mean` spread it over the players.
- **contains**: the techniques beyond singles, easiest first. A chip like `XWG/KTE/SCL` means any one of them works at
  that point; [Techniques](TECHNIQUES.md) lists every code.

Only the requested fields are computed. `contains` is the slow part: without it (`fields=["difficulty", "time",
"band"]`) a card takes about a third of the time, with the same band, difficulty and time. [Philosophy](PHILOSOPHY.md)
says what the numbers mean, [How a card is computed](MODEL.mdx) how they are computed.

## Other sites' labels on this scale
Median difficulty, interquartile range in brackets. Each site rates for its own audience and neighbouring levels
overlap a lot, so treat this as a rough conversion.

| Source label | Our difficulty | Notes |
|---|---|---|
| fed-sudoku easy | 3.9 (3.4–4.3) | |
| fed-sudoku medium | 5.1 (4.6–5.9) | |
| fed-sudoku hard | 6.5 (6.2–7.0) | |
| [sudoku.coach](https://sudoku.coach/) level 0 / 1 / 2 | 0.6 / 1.7 / 2.8 | classics |
| sudoku.coach level 3 / 4 / 5 | 3.7 / 5.2 / 5.8 | |
| sudoku.coach level 6 / 7 / 8 | 6.1 / 6.7 / 7.3 | |
| sudoku.coach level 9 / 10 / 11 | 8.7 / 11.5 / 11.9 | |
| [Logic Masters](https://logic-masters.de/) 1 star | 8.8 (6.3–10.1) | variants; LMD's "easy" is already hard |
| Logic Masters 2 stars | 11.1 (10.1–12.6) | |
| Logic Masters 3 stars | 13.0 (11.5–13.7) | |
| Logic Masters 4–5 stars | 13.8 (12.6–14.9) | n 56; stars 4 and 5 overlap |


## Speed

Classics take 0.04-0.2 s and typical variants 0.5-1.5 s. A few very hard killers can take 15-30 minutes while the
technique list is made minimal; `max_seconds` caps any call. Without the cap the result is the same on every machine.
