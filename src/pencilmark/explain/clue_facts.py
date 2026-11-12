"""Clue facts: the little facts a solver learns for each common rule before solving with it ("a 5 is never on a German
whisper", "a 5-cell renban always holds a 5"). Hand-written from the facts Cracking the Cryptic hosts repeat most
(docs/research/rule_facts_library.md in the research notes; the video count is how many solve videos state the fact),
in our own words. Each fact carries a probe: the rule alone on an empty 9x9 grid (sometimes with a given) and the
eliminations the fact makes there. tools/gen_clue_facts_md.py checks every probe by brute force (the eliminations
are true) and runs the engine on it (which step makes them), and writes docs/grades/clue-facts.md.

`out(n, i, D, args)`: the digits the fact rules out of position i (0-based) of a line of n cells (2 for a dot), args =
the relation's parameters; the ClueFacts explanation names the facts whose `out` covers its eliminations. Rules over more than two cells are applied
by their own techniques (cage and arrow combinations, line ranges); the page says which."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClueFact:
    id: str
    rule: str  # the variant name, as the page groups the facts
    text: str  # the fact, one sentence (9x9 wording)
    videos: int = 0  # CtC solve videos stating it (0: not counted)
    probe: tuple = ()  # (rules, givens {cell: digit}) on an empty 9x9 grid
    expect: dict = field(default_factory=dict)  # cell -> digits the fact rules out there (the probe's claim)
    kind: str = ""  # the engine's rule: a relation kind ("diffge" ...) or a line kind ("thermo" ...)
    out: object = None  # fn(n, i, D, args) -> digits ruled out at position i of n (pair rules)
    note: str = ""  # how the engine knows it, when not by a step (built into the model)


def _line(kind, cells, **k):
    return {"type": "line", "kind": kind, "cells": cells, **k}


def _edge(kind, cells, **k):
    return {"type": "edge", "kind": kind, "cells": cells, **k}


def _row(r, a, b):
    return [f"r{r}c{c}" for c in range(a, b + 1)]


def _all(cells, digits):
    return {c: list(digits) for c in cells}


def _rest(cells, house, digits):
    return {c: list(digits) for c in house if c not in cells}


_BOX1 = ["r1c1", "r1c2", "r1c3", "r2c1", "r2c2", "r2c3", "r3c1", "r3c2", "r3c3"]


def _thermo_out(n, i, D, args):
    return [d for d in range(1, D + 1) if d < i + 1 or d > D - (n - 1 - i)]


FACTS = [
    # ---- German / Dutch whispers
    ClueFact(
        "whisper-no-5",
        "German Whispers",
        "A 5 can never be on a German whisper: no digit is 5 or more away from it.",
        76,
        ([_line("whisper", _row(1, 1, 3), value=5)], {}),
        _all(_row(1, 1, 3), [5]),
        "diffge",
        lambda n, i, D, a: [
            d for d in range(1, D + 1) if a and a[0] == 5 and not any(abs(d - e) >= 5 for e in range(1, D + 1))
        ],
    ),
    ClueFact(
        "whisper-alternate",
        "German Whispers",
        "Neighbors on a German whisper alternate between low (1-4) and high (6-9) digits.",
        19,
        ([_line("whisper", _row(1, 1, 3), value=5)], {"r1c1": 2}),
        {"r1c2": [1, 3, 4]},
        "diffge",
    ),
    ClueFact(
        "whisper-squeeze",
        "German Whispers",
        "A 4 or a 6 cannot sit between two whisper cells that see each other: a 4 needs a 9 on both sides, a 6 a 1.",
        9,
        ([_line("whisper", _row(1, 1, 3), value=5)], {}),
        {"r1c2": [4, 6]},
        "diffge",
    ),
    ClueFact(
        "dutch-5",
        "Dutch Whispers",
        "A 5 can sit on a Dutch whisper, but only next to a 1 or a 9, so the low / high alternation can switch at it.",
        4,
        ([_line("whisper", ["r1c1", "r1c2"], value=4)], {"r1c1": 5}),
        {"r1c2": [2, 3, 4, 6, 7, 8]},
        "diffge",
    ),
    # ---- kropki
    ClueFact(
        "black-no-579",
        "Kropki",
        "A 5, 7 or 9 can never be on a black dot: its double is too big and it has no half.",
        59,
        ([_edge("kropki", ["r1c1", "r1c2"], color="black")], {}),
        _all(["r1c1", "r1c2"], [5, 7, 9]),
        "ratio",
        lambda n, i, D, a: [d for d in range(1, D + 1) if a == (2,) and d % 2 and 2 * d > D],
    ),
    ClueFact(
        "black-pairs",
        "Kropki",
        "A black dot holds 1-2, 2-4, 3-6 or 4-8: a 1 pairs only with 2, a 3 with 6, an 8 with 4.",
        21,
        ([_edge("kropki", ["r1c1", "r1c2"], color="black")], {"r1c1": 3}),
        {"r1c2": [1, 2, 4, 5, 7, 8, 9]},
        "ratio",
    ),
    ClueFact(
        "black-chain",
        "Kropki",
        "The middle of two black dots whose ends see each other is 2 or 4: a 1, 3, 6 or 8 would need the same partner "
        "twice.",
        15,
        ([_edge("kropki", ["r1c1", "r1c2"], color="black"), _edge("kropki", ["r1c2", "r1c3"], color="black")], {}),
        {"r1c2": [1, 3, 6, 8]},
        "ratio",
    ),
    ClueFact(
        "white-ends",
        "Kropki",
        "A 1 on a white dot pairs only with 2 and a 9 only with 8, so the middle of two white "
        "dots whose ends see each other is never 1 or 9.",
        56,
        ([_edge("kropki", ["r1c1", "r1c2"], color="white"), _edge("kropki", ["r1c2", "r1c3"], color="white")], {}),
        {"r1c2": [1, 9]},
        "diff",
    ),
    ClueFact(
        "white-parity",
        "Kropki",
        "A white dot always joins an odd and an even digit.",
        14,
        ([_edge("kropki", ["r1c1", "r1c2"], color="white")], {"r1c1": 4}),
        {"r1c2": [1, 2, 6, 7, 8, 9]},
        "diff",
    ),
    # ---- XV
    ClueFact(
        "x-no-5",
        "XV",
        "A 5 can never be on an X: its partner would be another 5.",
        0,
        ([_edge("xv", ["r1c1", "r1c2"], letter="X")], {}),
        _all(["r1c1", "r1c2"], [5]),
        "sum",
        lambda n, i, D, a: [d for d in range(1, D + 1) if a == (10,) and d == 5],
    ),
    ClueFact(
        "v-low",
        "XV",
        "A V holds 1-4 or 2-3, so only the digits 1-4.",
        0,
        ([_edge("xv", ["r1c1", "r1c2"], letter="V")], {}),
        _all(["r1c1", "r1c2"], range(5, 10)),
        "sum",
        lambda n, i, D, a: [d for d in range(5, D + 1) if a == (5,)],
    ),
    # ---- thermometers
    ClueFact(
        "thermo-range",
        "Thermo",
        "A thermometer cell with k cells before it is at least k + 1, and with m cells after it at most 9 - m: on a "
        "4-cell thermo the bulb is 1-6 and the tip 4-9.",
        72,
        ([_line("thermo", _row(1, 1, 4))], {}),
        {"r1c1": [7, 8, 9], "r1c2": [1, 8, 9], "r1c3": [1, 2, 9], "r1c4": [1, 2, 3]},
        "thermo",
        _thermo_out,
    ),
    ClueFact(
        "thermo-fork",
        "Thermo",
        "Branches that share a bulb each count from it: the bulb is low enough for the longest branch.",
        0,
        ([_line("thermo", ["r5c5", "r5c6", "r5c7"]), _line("thermo", ["r5c5", "r6c5", "r7c5"])], {}),
        {"r5c5": [8, 9], "r5c7": [1, 2]},
        "thermo",
    ),
    # ---- arrows
    ClueFact(
        "arrow-circle-min",
        "Arrow",
        "An arrow's circle is at least the smallest sum of its shaft: 3 for two cells that see "
        "each other, 6 for three.",
        116,
        ([{"type": "arrow", "bulb": ["r1c1"], "lines": [["r2c1", "r3c1", "r4c1"]]}], {}),
        {"r1c1": [1, 2, 3, 4, 5]},
        "arrow",
    ),
    ClueFact(
        "arrow-shaft-max",
        "Arrow",
        "A shaft digit is smaller than its circle, so 9 is never on a shaft of two or more "
        "cells, and 8 and 9 are never on three cells that see each other.",
        88,
        ([{"type": "arrow", "bulb": ["r1c1"], "lines": [["r2c1", "r3c1", "r4c1"]]}], {}),
        _all(["r2c1", "r3c1", "r4c1"], [7, 8, 9]),
        "arrow",
    ),
    # ---- killer cages
    ClueFact(
        "cage-combos",
        "Killer",
        "A cage of n cells and total s uses one of the sets of n different digits adding to s: "
        "a 3-cell 7 is 1, 2, 4 and a 3-cell 24 is 7, 8, 9.",
        213,
        ([{"type": "cage", "cells": ["r1c1", "r1c2", "r2c1"], "sum": 24}], {}),
        _all(["r1c1", "r1c2", "r2c1"], range(1, 7)),
        "cage",
    ),
    ClueFact(
        "cage-pair",
        "Killer",
        "A 2-cell cage has no middle digit twice: a 10 has no 5, and a 3 is 1 and 2.",
        0,
        ([{"type": "cage", "cells": ["r1c1", "r1c2"], "sum": 10}], {}),
        _all(["r1c1", "r1c2"], [5]),
        "cage",
    ),
    ClueFact(
        "cage-house",
        "Killer",
        "A cage's forced digits leave the rest of the house it lies in: a 1-2-4 cage in a box "
        "takes 1, 2 and 4 from the other six cells.",
        35,
        ([{"type": "cage", "cells": ["r1c1", "r1c2", "r2c1"], "sum": 7}], {}),
        _rest(["r1c1", "r1c2", "r2c1"], _BOX1, [1, 2, 4]),
        "cage",
    ),
    ClueFact(
        "cage-missing-digit",
        "Killer",
        "An 8-cell cage misses one digit, 45 minus its total: an 8-cell 40 has no 5.",
        4,
        ([{"type": "cage", "cells": ["r1c1", "r1c2", "r1c3", "r2c1", "r2c2", "r2c3", "r3c1", "r3c2"], "sum": 40}], {}),
        _all(["r1c1", "r1c2", "r1c3", "r2c1", "r2c2", "r2c3", "r3c1", "r3c2"], [5]),
        "cage",
    ),
    # ---- renban
    ClueFact(
        "renban-middle",
        "Renban",
        "A renban of n cells always holds the digits 10 - n to n: a 5-cell renban has a 5, a 7-cell one 3 to 7.",
        33,
        ([_line("renban", _row(1, 1, 5))], {}),
        _rest(_row(1, 1, 5), _row(1, 1, 9), [5]),
        "renban",
    ),
    ClueFact(
        "renban-spread",
        "Renban",
        "Digits on a renban of n cells lie within n - 1 of each other: a 4-cell renban with a 2 holds nothing above 5.",
        4,
        ([_line("renban", _row(1, 1, 4))], {"r1c1": 2}),
        _all(_row(1, 2, 4), [6, 7, 8, 9]),
        "renban",
    ),
    # ---- entropic / modular
    ClueFact(
        "entropic-window",
        "Entropic Lines",
        "Any three neighboring cells on an entropic line hold one low (1-3), one "
        "middle (4-6) and one high (7-9) digit.",
        13,
        ([_line("entropic", _row(1, 1, 3))], {"r1c1": 2}),
        _all(["r1c2", "r1c3"], [1, 3]),
        "entropic",
        note="Built into the model: cells one or two apart on the line have different classes.",
    ),
    ClueFact(
        "entropic-three-apart",
        "Entropic Lines",
        "Cells three apart on an entropic line hold the same class.",
        6,
        ([_line("entropic", _row(1, 1, 4))], {"r1c1": 2}),
        {"r1c4": [4, 5, 6, 7, 8, 9]},
        "entropic",
        note="Built into the model: cells three apart on the line share a class.",
    ),
    ClueFact(
        "modular-three-apart",
        "Modular Lines",
        "Cells three apart on a modular line leave the same remainder divided by "
        "3; any three neighbors hold one each of 1-4-7, 2-5-8 and 3-6-9.",
        6,
        ([_line("modular", _row(1, 1, 4))], {"r1c1": 4}),
        {"r1c4": [2, 3, 5, 6, 8, 9]},
        "modular",
        note="Built into the model: cells three apart share a remainder, one or two apart differ.",
    ),
    # ---- palindrome, zipper, between, region sum
    ClueFact(
        "palindrome-mirror",
        "Palindrome",
        "Mirrored cells of a palindrome hold the same digit, so a digit one of them cannot hold leaves the other.",
        13,
        ([_line("palindrome", ["r3c3", "r4c3", "r4c4"])], {"r3c1": 7}),
        {"r4c4": [7]},
        "palindrome",
    ),
    ClueFact(
        "zipper-centre",
        "Zipper Lines",
        "The center of a zipper is its largest digit: on three cells the center is at "
        "least 3 and the ends are never 9.",
        13,
        ([_line("zipper", _row(1, 1, 3))], {}),
        {"r1c1": [9], "r1c3": [9], "r1c2": [1, 2]},
        "zipper",
    ),
    ClueFact(
        "zipper-parity",
        "Zipper Lines",
        "With an odd center, each pair on a zipper adds to an odd total: one digit of every pair is odd, the other even.",
        0,
        ([_line("zipper", _row(1, 1, 3))], {"r1c1": 2, "r4c2": 4, "r5c2": 6, "r6c2": 8}),
        {"r1c3": [4, 6, 8]},
        "zipper",
    ),
    ClueFact(
        "between-no-ends",
        "Between Lines",
        "Digits on a between line lie strictly between its circles, so 1 and 9 are never on it.",
        3,
        ([_line("between", _row(1, 1, 4))], {}),
        _all(["r1c2", "r1c3"], [1, 9]),
        "between",
    ),
    ClueFact(
        "region-sum-segments",
        "Region Sum Lines",
        "Each box's part of a region-sum line has the same total, so a single "
        "cell equals the sum of the two cells across the border: at least 3.",
        6,
        ([_line("region_sum", _row(1, 3, 5))], {}),
        {"r1c3": [1, 2], "r1c4": [9], "r1c5": [9]},
        "region_sum",
    ),
    # ---- outside clues
    ClueFact(
        "sandwich-35",
        "Sandwich",
        "A sandwich of 35 holds every digit 2-8, so the 1 and 9 are at the ends of the row.",
        10,
        ([{"type": "sandwich", "side": "left", "sum": 35, "cells": _row(1, 1, 9)}], {}),
        _all(_row(1, 2, 8), [1, 9]),
        "sandwich",
    ),
    ClueFact(
        "sandwich-0",
        "Sandwich",
        "A sandwich of 0 means the 1 and the 9 are next to each other.",
        3,
        ([{"type": "sandwich", "side": "left", "sum": 0, "cells": _row(1, 1, 9)}], {"r1c5": 1}),
        _all(["r1c1", "r1c2", "r1c3", "r1c7", "r1c8", "r1c9"], [9]),
        "sandwich",
    ),
    ClueFact(
        "skyscraper-1",
        "Skyscraper",
        "A skyscraper clue of 1 sees only the first cell, so it holds the 9.",
        4,
        ([{"type": "skyscraper", "side": "left", "value": 1, "cells": _row(1, 1, 9)}], {}),
        {"r1c1": list(range(1, 9))},
        "skyscraper",
    ),
    ClueFact(
        "skyscraper-not-9",
        "Skyscraper",
        "A skyscraper clue above 1 means the first cell is not the 9.",
        0,
        ([{"type": "skyscraper", "side": "left", "value": 2, "cells": _row(1, 1, 9)}], {}),
        {"r1c1": [9]},
        "skyscraper",
    ),
    ClueFact(
        "quadruple-inside",
        "Quadruple",
        "Every digit of a quadruple circle is among its four cells, so it leaves the "
        "rest of a house that holds all four.",
        7,
        ([{"type": "quadruple", "cells": ["r1c1", "r1c2", "r2c1", "r2c2"], "digits": [1, 2, 3]}], {}),
        _rest(["r1c1", "r1c2", "r2c1", "r2c2"], _BOX1, [1, 2, 3]),
        "quadruple",
    ),
]

BY_ID = {f.id: f for f in FACTS}


def covering(p, elims):
    """the facts that explain a ClueFacts move: for each elimination (cell, digit), a fact of a pair rule on the cell
    whose `out` holds the digit -> (facts in catalog order, eliminations no fact covers). The texts are worded for
    digits 1-9: other sizes get no facts."""
    if p.D != 9:
        return [], list(elims)
    pos = {}  # cell -> (n, i) on its line rule (thermo ...)
    for con in getattr(p, "constraints", ()):
        if con.get("type") == "line":
            for i, c in enumerate(con["cells"]):
                pos[(con["kind"], c)] = (len(con["cells"]), i)
    rels = {}
    for kind, a, b, *args in getattr(p, "relations", ()):
        line = "thermo" if kind == "lt" else None
        for c in (a, b):
            n, i = pos.get((line, c), (2, 0))
            rels.setdefault(c, []).append((line or kind, n, i, tuple(args)))
    used, left = [], []
    for c, d in elims:
        hit = next(
            (f for kind, n, i, args in rels.get(c, ()) for f in FACTS
             if f.kind == kind and f.out is not None and d in f.out(n, i, p.D, args)),
            None,
        )  # fmt: skip
        if hit is None:
            left.append((c, d))
        elif hit not in used:
            used.append(hit)
    return [f for f in FACTS if f in used], left


def rule_kinds(p, cells):
    """the rules on these cells that have a one-sentence statement (explain.facts.RULE_FACTS), in a fixed order: the
    rule a ClueFacts step over more cells reads"""
    from .facts import RULE_FACTS

    cells, kinds = set(cells), []
    for con in getattr(p, "constraints", ()):
        k = con.get("kind") if con.get("type") == "line" else con.get("type")
        on = set(con.get("cells") or ()) | set(con.get("circle") or ()) | set(con.get("line") or ())
        if k in RULE_FACTS and on & cells and k not in kinds:
            kinds.append(k)
    if any(g.kind == "cage" and set(g.cells) & cells for g in getattr(p, "groups", ())) and "cage" not in kinds:
        kinds.append("cage")
    return kinds
