---
title: "The command line"
description: "`python -m pencilmark` and the `pencilmark` command."
toc_max_heading_level: 2
---

# The command line

`python -m pencilmark` and the `pencilmark` command. Generated from the docstrings by `tools/gen_reference_md.py`; public names only.

## pencilmark.__main__ {#pencilmark.main}

[src/pencilmark/__main__.py](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py)

Command-line front end (SE-style).

python -m pencilmark rate [FILE|-] [--format FMT] [--json] [--steps] One puzzle per line: a classic string ('.'/'0' blanks; 16 / 36 / 81 / 256 / 625 symbols), a JSON object in the pencilmark.puzzle_json format or the sudoku-puzzle format (pencilmark.to_export), or a path to a .json file. A FILE ending in .json that holds one JSON value (a puzzle, or a list of puzzles) is read whole. Prints one result line per puzzle. Card "sudoku-grade": FMT fields %d difficulty (continuous, above 0, no ceiling; ~5 = typical medium), %m predicted median solve time in minutes, %p 80th-percentile minutes, %b band, %h hardest technique met, %c contents chips (band > 0, with uses), %n issue codes, %s status ("ok" or the error), %u unique?, %i line number. Default: "%b      %d      %m      %h". --json prints the full card (add --steps for the step list, --explain for its explanations, --fields to choose fields); --report a readable summary. A puzzle without exactly one solution prints its error ({"line", "error"} with --json). python -m pencilmark solve [FILE|-]      the solution (or 'not unique' / 'no solution') per puzzle python -m pencilmark count [FILE|-] [--limit N]   how many solutions per puzzle (">=N" when it stops at N) python -m pencilmark generate [SPEC|-] [--seed N] [--time S] [--result] a puzzle for a "sudoku-spec" request ([Generator spec](../formats/generator-spec.md)), as a sudoku-puzzle file python -m pencilmark json  [FILE|-]      validate + normalise to canonical JSON (adds "hash") python -m pencilmark export [FILE|-] [--pretty] [--no-solution] each puzzle as a "sudoku-puzzle" file (format_version 1, [Puzzle format](../formats/puzzle-format.md)), canonical python -m pencilmark fingerprint [FILE|-]  the content fingerprint ("sha256:...") per puzzle python -m pencilmark describe [FILE|-]     variant name and rules per puzzle (JSON) Inputs may also be sudokuwiki.org packed strings (S9B..., L9B..., J9B...).

| Name | What it does |
|---|---|
| def [`report2`](#pencilmark.main.report2) | Readable summary of the sudoku-grade card. |
| def [`cmd_rate`](#pencilmark.main.cmd_rate) | `rate` command: print one grading line per input puzzle (a worker pool when --jobs > 1) |
| def [`cmd_solve`](#pencilmark.main.cmd_solve) | `solve` command: print each input puzzle's solution, or not unique / undecided / no solution |
| def [`cmd_count`](#pencilmark.main.cmd_count) | `count` command: print each input puzzle's number of solutions (>=N when cut off at --limit) |
| def [`cmd_generate`](#pencilmark.main.cmd_generate) | `generate` command: generate a puzzle from a spec (file or stdin); --result prints the whole result |
| def [`cmd_json`](#pencilmark.main.cmd_json) | `json` command: print each input puzzle as one line of puzzle JSON with its hash |
| def [`cmd_export`](#pencilmark.main.cmd_export) | `export` command: print each input puzzle in the sudoku-puzzle format (--no-solution drops the solution) |
| def [`cmd_fingerprint`](#pencilmark.main.cmd_fingerprint) | `fingerprint` command: print the fingerprint of each input puzzle |
| def [`cmd_describe`](#pencilmark.main.cmd_describe) | `describe` command: print the description of each input puzzle as one line of JSON |
| def [`main`](#pencilmark.main.main) | command-line entry point: parse argv, set UTF-8 on stdin and stdout, run the chosen command |

### `def report2(g, k=None)` {#pencilmark.main.report2}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L131)

Readable summary of the sudoku-grade card.

### `def cmd_rate(a)` {#pencilmark.main.cmd_rate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L243)

`rate` command: print one grading line per input puzzle (a worker pool when --jobs > 1)

### `def cmd_solve(a)` {#pencilmark.main.cmd_solve}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L268)

`solve` command: print each input puzzle's solution, or not unique / undecided / no solution

### `def cmd_count(a)` {#pencilmark.main.cmd_count}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L290)

`count` command: print each input puzzle's number of solutions (>=N when cut off at --limit)

### `def cmd_generate(a)` {#pencilmark.main.cmd_generate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L301)

`generate` command: generate a puzzle from a spec (file or stdin); --result prints the whole result

### `def cmd_json(a)` {#pencilmark.main.cmd_json}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L322)

`json` command: print each input puzzle as one line of puzzle JSON with its hash

### `def cmd_export(a)` {#pencilmark.main.cmd_export}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L334)

`export` command: print each input puzzle in the sudoku-puzzle format (--no-solution drops the solution)

### `def cmd_fingerprint(a)` {#pencilmark.main.cmd_fingerprint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L345)

`fingerprint` command: print the fingerprint of each input puzzle

### `def cmd_describe(a)` {#pencilmark.main.cmd_describe}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L352)

`describe` command: print the description of each input puzzle as one line of JSON

### `def main(argv=None)` {#pencilmark.main.main}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L364)

command-line entry point: parse argv, set UTF-8 on stdin and stdout, run the chosen command
