"""The `line` rule family (docs/rules/lines-and-arrows.mdx): every public kind with its parameters and whether it can be
closed. Parameters are REQUIRED when digits != 9 (on 9 x 9 each has a default the reader fills in)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LineKind:
    kind: str
    params: tuple = ()  # optional keys on 9 x 9, required otherwise
    closable: bool = False  # "closed": true allowed (the last cell connects back to the first)


LINE = {
    k.kind: k
    for k in (
        LineKind("thermo"),
        LineKind("slow_thermo"),
        LineKind("whisper", ("value",), closable=True),
        LineKind("renban", closable=True),
        LineKind("region_sum"),
        LineKind("palindrome"),
        LineKind("entropic", ("groups",)),
        LineKind("modular", ("value",)),
        LineKind("parity", closable=True),
        LineKind("zipper"),
        LineKind("between"),
        LineKind("lockout", ("value",)),
        LineKind("double_arrow"),
    )
}
