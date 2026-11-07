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

```
  python -m pencilmark rate [FILE|-] [--print FMT] [--json] [--steps]
      One puzzle per line, in any format pencilmark reads (pencilmark.read: a plain string, a sudokuwiki packed string,
      a HoDoKu line, pencilmark JSON, an ipuz object, a site link), detected per line. A FILE ending in .json or .ipuz
      that holds one JSON value (a puzzle, or a list of puzzles) is read whole; --from FORMAT names the format instead
      (every command takes it). Prints one
      result line per puzzle. Card "pencilmark-grade": FMT fields %d difficulty (continuous, above 0, no ceiling; ~5 = typical medium),
      %m predicted median solve time in minutes, %p 80th-percentile minutes, %b band, %h hardest technique met,
      %c contents chips (band > 0, with uses), %n issue codes, %s status ("ok" or the error), %u unique?, %i line number.
      Default: "%b      %d      %m      %h". --json prints the full card (add --steps for the step list, --explain for its
      explanations, --fields to choose fields); --report a readable summary. A puzzle without exactly one solution
      prints its error ({"line", "error"} with --json).
  python -m pencilmark solve [FILE|-]      the solution (or 'not unique' / 'no solution' / 'undecided') per puzzle
  python -m pencilmark count-solutions [FILE|-] [--limit N]   how many solutions per puzzle (">=N" at N)
  python -m pencilmark generate [SPEC|-] [--result]
                                       a puzzle for a "pencilmark-spec" request (docs/formats/generator-spec.md), as a pencilmark-puzzle file
  python -m pencilmark convert [FILE|-] [--to pencilmark|plain|grid|sudokuwiki|ipuz] [--pretty] [--no-solution] [--no-style]
                                       each puzzle in another format; pencilmark JSON (docs/formats/puzzle-format.md) by default, canonical
  python -m pencilmark fingerprint [FILE|-]  the content fingerprint (64 hex digits) per puzzle
  python -m pencilmark describe [FILE|-]     variant name and rules per puzzle (JSON)
```

Every command takes --log info (pages fetched, what a reader read, time limits reached, the generator's result) or --log debug (also stage timings, the uniqueness check, each generator attempt and each reading a reader tried), written to standard error.

| Name | What it does |
|---|---|
| def [`report2`](#pencilmark.main.report2) | Readable summary of the pencilmark-grade card. |
| def [`cmd_rate`](#pencilmark.main.cmd_rate) | `rate` command: print one grading line per input puzzle (a worker pool when --jobs > 1) |
| def [`cmd_solve`](#pencilmark.main.cmd_solve) | `solve` command: print each input puzzle's solution, or not unique / undecided / no solution |
| def [`cmd_count`](#pencilmark.main.cmd_count) | `count` command: print each input puzzle's number of solutions (>=N when cut off at --limit) |
| def [`cmd_generate`](#pencilmark.main.cmd_generate) | `generate` command: generate a puzzle from a spec (file or stdin); --result prints the whole result |
| def [`cmd_convert`](#pencilmark.main.cmd_convert) | `convert` command: print each input puzzle in the --to format (pencilmark JSON by default: with its solution… |
| def [`cmd_fingerprint`](#pencilmark.main.cmd_fingerprint) | `fingerprint` command: print the fingerprint of each input puzzle |
| def [`cmd_describe`](#pencilmark.main.cmd_describe) | `describe` command: print the description of each input puzzle as one line of JSON |
| def [`main`](#pencilmark.main.main) | command-line entry point: parse argv, set UTF-8 on stdin and stdout, run the chosen command |

### `def report2(g, k=None)` {#pencilmark.main.report2}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L122)

Readable summary of the pencilmark-grade card.

### `def cmd_rate(a)` {#pencilmark.main.cmd_rate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L247)

`rate` command: print one grading line per input puzzle (a worker pool when --jobs > 1)

### `def cmd_solve(a)` {#pencilmark.main.cmd_solve}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L272)

`solve` command: print each input puzzle's solution, or not unique / undecided / no solution

### `def cmd_count(a)` {#pencilmark.main.cmd_count}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L295)

`count` command: print each input puzzle's number of solutions (>=N when cut off at --limit)

### `def cmd_generate(a)` {#pencilmark.main.cmd_generate}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L306)

`generate` command: generate a puzzle from a spec (file or stdin); --result prints the whole result

### `def cmd_convert(a)` {#pencilmark.main.cmd_convert}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L323)

`convert` command: print each input puzzle in the --to format (pencilmark JSON by default: with its solution unless --no-solution, the rules' drawing styles unless --no-style, one line unless --pretty)

### `def cmd_fingerprint(a)` {#pencilmark.main.cmd_fingerprint}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L343)

`fingerprint` command: print the fingerprint of each input puzzle

### `def cmd_describe(a)` {#pencilmark.main.cmd_describe}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L350)

`describe` command: print the description of each input puzzle as one line of JSON

### `def main(argv=None)` {#pencilmark.main.main}

[source](https://github.com/silly-puppyy/pencilmark/blob/main/src/pencilmark/__main__.py#L357)

command-line entry point: parse argv, set UTF-8 on stdin and stdout, run the chosen command
