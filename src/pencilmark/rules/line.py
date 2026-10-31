"""The `line` rule family (docs/rules/lines-and-arrows.mdx): every public kind with its parameters, whether it can be
closed, and its words (the variant name and the one-sentence rule describe() writes). Parameters are REQUIRED when
digits != 9 (on 9 x 9 each has a default the reader fills in)."""

from dataclasses import dataclass


def _values(rules, key):
    return sorted({r[key] for r in rules if key in r})


def _whisper_text(rules):
    v = _values(rules, "value")
    if len(v) <= 1:
        return f"Adjacent digits on a whisper line differ by at least {(v or [5])[0]}."
    return "Adjacent digits on a whisper line differ by at least the line's number."


def _whisper_name(rules):
    v = _values(rules, "value") or [5]
    return {5: "German Whispers", 4: "Dutch Whispers"}.get(v[0], "Whispers") if len(v) == 1 else "Whispers"


@dataclass(frozen=True)
class LineKind:
    kind: str
    name: str  # the variant name describe() uses
    text: object  # the rule in one sentence, or fn(rules) -> sentence
    params: tuple = ()  # optional keys on 9 x 9, required otherwise
    closable: bool = False  # "closed": true allowed (the last cell connects back to the first)
    name_fn: object = None  # fn(rules) -> the name for these rules, when it depends on them
    width: object = "line"  # drawn line width: a docs/palette.json size name, or cell units
    ends: str = ""  # end markers: "bulb" (filled, cells[0]), "hollow bulb", "circles", "diamonds", "centre dot"
    generated: bool = False  # the generator can place it (a sudoku-spec template; pencilmark/gen/elements.py)


LINE = {
    k.kind: k
    for k in (
        LineKind(
            "thermo",
            "Thermo",
            "Digits strictly increase along a thermometer from the bulb.",
            width="thermo",
            ends="bulb",
            generated=True,
        ),
        LineKind(
            "slow_thermo",
            "Slow Thermo",
            "Digits increase or stay equal along a thermometer from the bulb.",
            width="thermo",
            ends="hollow bulb",
        ),
        LineKind(
            "whisper", "Whispers", _whisper_text, ("value",), closable=True, name_fn=_whisper_name, generated=True
        ),
        LineKind(
            "renban",
            "Renban",
            "A renban line holds a set of consecutive digits in any order, without repeats.",
            closable=True,
            generated=True,
        ),
        LineKind("region_sum", "Region Sum", "A region sum line has the same sum in every box it passes through."),
        LineKind("palindrome", "Palindrome", "A palindrome line reads the same from either end."),
        LineKind(
            "entropic",
            "Entropic",
            "Any three consecutive cells on an entropic line hold a low, a middle and a high digit.",
            ("groups",),
        ),
        LineKind(
            "modular",
            "Modular",
            "Any three consecutive cells on a modular line hold different remainders modulo 3.",
            ("value",),
        ),
        LineKind("parity", "Parity", "Adjacent digits on a parity line alternate between odd and even.", closable=True),
        LineKind(
            "zipper",
            "Zipper",
            "Digits equally far from the centre of a zipper line sum to the same total.",
            ends="centre dot",
        ),
        LineKind(
            "between",
            "Between Lines",
            "Digits on a between line lie strictly between the digits in its end circles.",
            width=0.1,
            ends="circles",
            generated=True,
        ),
        LineKind(
            "lockout",
            "Lockout",
            "The ends of a lockout line differ by at least 4 and no digit on the line lies between them.",
            ("value",),
            width=0.05,
            ends="diamonds",
        ),
        LineKind(
            "double_arrow",
            "Double Arrow",
            "The two circled ends of a double arrow sum to the digits between them.",
            width=0.05,
            ends="circles",
        ),
    )
}


def line_to_engine(r, D, B, pairs_rule):
    """a public line rule -> the engine's rules (exchange's reader): a line constraint, or for double_arrow an equal
    sum, for lockout a pair rule and digit tables"""
    from ..exchange import NotSupportedError, lockout_table

    k = r["kind"]
    cs = r["cells"]
    if k == "double_arrow":
        return [{"type": "equal_sum", "segments": [[cs[0], cs[-1]], cs[1:-1]]}]
    if k == "lockout":
        kk = r.get("value", 4)
        a, b = B.idx(cs[0]), B.idx(cs[-1])
        out = [pairs_rule("diffge", (kk,), [(a, b)])]
        tab = [list(x) for x in lockout_table(D, kk)]
        out += [{"type": "table", "cells": [cs[0], cs[-1], c], "allowed": tab} for c in cs[1:-1]]
        return out
    con = {
        "type": "line",
        "kind": k,
        "cells": list(cs) + ([cs[0]] if r.get("closed") and k != "renban" else []),
    }
    if k == "whisper" and "value" in r:
        con["k"] = r["value"]
    if k == "modular" and r.get("value", 3) != 3:
        raise NotSupportedError("modular lines with a modulus other than 3 are not supported by the engine")
    if k == "entropic" and "groups" in r:
        third = lambda v: (v - 1) * 3 // D if D % 3 == 0 else (v - 1) // 3
        want = [[v for v in range(1, D + 1) if third(v) == g] for g in range(3)]
        if sorted(sorted(x) for x in r["groups"]) != want:
            raise NotSupportedError(f"entropic groups {r['groups']} are not supported (engine: {want})")
    return [con]


def line_from_engine(c, B, D):
    """an engine line constraint -> public rules (exchange's writer); a kropki chain becomes its kropki edges"""
    from .edge import edge_rule

    kind = c["kind"]
    cells = list(c["cells"])
    if kind == "kropki_chain":  # normalisation 4: kropki edges
        dots = c.get("dots") or ["white"] * (len(cells) - 1)
        return [edge_rule("kropki", d_, a, b, B) for (a, b), d_ in zip(zip(cells, cells[1:]), dots)]
    r = {"type": "line", "kind": "whisper" if kind == "dutch_whisper" else kind}
    if kind in ("whisper", "dutch_whisper"):
        if "k" in c or kind == "dutch_whisper" or D != 9:
            r["value"] = c.get("k", 5 if kind == "whisper" else 4)
    if kind == "modular" and D != 9:
        r["value"] = 3
    if kind == "entropic" and D != 9:
        third = lambda v: (v - 1) * 3 // D if D % 3 == 0 else (v - 1) // 3
        r["groups"] = [[v for v in range(1, D + 1) if third(v) == g] for g in range(3)]
    if len(cells) > 2 and cells[0] == cells[-1] and kind in ("whisper", "dutch_whisper", "parity"):
        r["closed"] = True
        cells = cells[:-1]
    r["cells"] = [B.name(x) for x in cells]
    return [r]
