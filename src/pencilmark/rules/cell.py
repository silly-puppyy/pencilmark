"""The `cell` rule family (docs/rules/cell-clues.mdx): every public kind with its parameter, the variant it belongs to
(odd and even make one variant, low and high another), whether the "every cell of the kind is marked" negative is defined,
and how it is drawn."""

from dataclasses import dataclass


def _vals(rs, key):
    return sorted({r[key] for r in rs if key in r})


def _odd_even_text(rs, c):
    k = {r["kind"] for r in rs if r["type"] == "cell"}
    parts = (["a digit in a grey circle is odd"] if "odd" in k else []) + (
        ["a digit in a grey square is even"] if "even" in k else []
    )
    s = "; ".join(parts) or "shaded cells have a fixed parity"
    s = s[0].upper() + s[1:] + "."
    if any(r["type"] == "negative" for r in rs):
        s += " Every unmarked cell has the other parity."
    return s


def _low_high_text(rs, c):
    sp = (_vals(rs, "split") or [c["D"] // 2])[0]
    s = f"A cell with a light diamond holds 1–{sp}; a cell with a dark diamond holds {sp + 1}–{c['D']}."
    neg = [r for r in rs if r["type"] == "negative"]
    if neg:
        s += f" Every unmarked cell holds {'1–' + str(sp) if neg[0]['kind'] == 'high' else str(sp + 1) + '–' + str(c['D'])}."
    return s


@dataclass(frozen=True)
class CellKind:
    kind: str
    variant: str  # the variant name describe() uses ("Exclusion" also covers the corner exclude, in variants.py)
    param: str = None  # "split" (an integer >= 1) or "values" (digits); required when set
    negative: bool = False  # {"type": "negative", "of": "cell", "kind": kind} is defined
    mark: str = "digits"  # drawn in each cell: "circle", "square", "diamond" (shaded, palette colour = kind), "digits"


CELL = {
    k.kind: k
    for k in (
        CellKind("odd", "Odd-Even", negative=True, mark="circle"),
        CellKind("even", "Odd-Even", negative=True, mark="square"),
        CellKind("low", "Low-High", "split", negative=True, mark="diamond"),
        CellKind("high", "Low-High", "split", negative=True, mark="diamond"),
        CellKind("set", "Digit Class", "values"),
        CellKind("exclude", "Exclusion", "values"),
    )
}
# the rule sentence of each variant made only of cell kinds, in variants order
VARIANT_TEXT = {
    "Odd-Even": _odd_even_text,
    "Low-High": _low_high_text,
    "Digit Class": "A cell marked with small digits contains one of them.",
}
