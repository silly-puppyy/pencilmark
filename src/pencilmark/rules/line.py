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


LINE = {
    k.kind: k
    for k in (
        LineKind("thermo", "Thermo", "Digits strictly increase along a thermometer from the bulb."),
        LineKind("slow_thermo", "Slow Thermo", "Digits increase or stay equal along a thermometer from the bulb."),
        LineKind("whisper", "Whispers", _whisper_text, ("value",), closable=True, name_fn=_whisper_name),
        LineKind(
            "renban",
            "Renban",
            "A renban line holds a set of consecutive digits in any order, without repeats.",
            closable=True,
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
        LineKind("zipper", "Zipper", "Digits equally far from the centre of a zipper line sum to the same total."),
        LineKind(
            "between", "Between Lines", "Digits on a between line lie strictly between the digits in its end circles."
        ),
        LineKind(
            "lockout",
            "Lockout",
            "The ends of a lockout line differ by at least 4 and no digit on the line lies between them.",
            ("value",),
        ),
        LineKind(
            "double_arrow", "Double Arrow", "The two circled ends of a double arrow sum to the digits between them."
        ),
    )
}
