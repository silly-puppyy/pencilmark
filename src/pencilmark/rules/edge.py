"""The `edge` rule family (docs/rules/edges-and-corners.mdx): every public kind with its one parameter, its words (the
variant name, the one-sentence rule describe() writes, the noun a card note uses) and how it is drawn; and the
translation between an edge clue and the engine's pair relation, both ways, with the "all clues shown" negatives."""

from dataclasses import dataclass


def _kropki_text(rs):
    cols = {r["color"] for r in rs if r["type"] == "edge"}
    parts = []
    if "white" in cols or not cols:
        parts.append("digits separated by a white dot are consecutive")
    if "black" in cols or not cols:
        parts.append("digits separated by a black dot are in a 1:2 ratio")
    s = "; ".join(parts)
    s = s[0].upper() + s[1:] + "."
    neg = [r for r in rs if r["type"] == "negative"]
    if neg:
        covered = {r.get("color") for r in neg}
        s += (
            " All dots are given."
            if None in covered or covered == {"white", "black"}
            else f" All {'/'.join(sorted(covered))} dots are given."
        )
    return s


def _kropki_name(rs):
    if {r.get("color") for r in rs if r["type"] == "edge"} == {"white"}:
        return "Consecutive"
    return "Kropki" if any(r["type"] == "edge" for r in rs) else "Non-Kropki"


def _xv_text(rs):
    lets = {r["letter"] for r in rs if r["type"] == "edge"}
    neg = [r for r in rs if r["type"] == "negative"]
    if not lets:
        covered = {r.get("letter") for r in neg}
        sums = "10 or 5" if None in covered or covered == {"X", "V"} else ("10" if "X" in covered else "5")
        return f"No two orthogonally adjacent digits sum to {sums}."
    parts = []
    if "X" in lets:
        parts.append("digits separated by an X sum to 10")
    if "V" in lets:
        parts.append("digits separated by a V sum to 5")
    s = "; ".join(parts)
    s = s[0].upper() + s[1:] + "."
    if neg:
        covered = {r.get("letter") for r in neg}
        s += (
            " All X's and V's are given."
            if None in covered or covered == {"X", "V"}
            else f" All {list(covered)[0]}'s are given."
        )
    return s


def _xv_name(rs):
    return "XV" if any(r["type"] == "edge" for r in rs) else "Non-XV"


@dataclass(frozen=True)
class EdgeKind:
    kind: str
    name: str  # the variant name describe() uses
    text: object  # the rule in one sentence, or fn(rules) -> sentence
    noun: str  # one clue, as a card note names it
    param: str = None  # the one parameter key (required)
    choices: tuple = ()  # the values the parameter may take, when they are a fixed set
    negative: bool = True  # {"type": "negative", "of": kind} is defined (all clues of the kind are shown)
    name_fn: object = None  # fn(rules) -> the name for these rules, when it depends on them
    marker: str = "circle"  # drawn on the edge midpoint: "dot", "letter" (a square chip), "chevron", "circle"
    label: object = None  # fn(rule) -> the text in a "circle" marker
    generated: bool = False  # the generator can place it (a sudoku-spec template; pencilmark/gen/elements.py)


EDGE = {
    k.kind: k
    for k in (
        EdgeKind(
            "kropki",
            "Kropki",
            _kropki_text,
            "kropki dot",
            "color",
            ("white", "black"),
            name_fn=_kropki_name,
            marker="dot",
            generated=True,
        ),
        EdgeKind(
            "xv",
            "XV",
            _xv_text,
            "X / V clue",
            "letter",
            ("X", "V"),
            name_fn=_xv_name,
            marker="letter",
            generated=True,
        ),
        EdgeKind(
            "difference",
            "Difference",
            "Digits separated by a numbered circle differ by that number.",
            "difference clue",
            "value",
            label=lambda r: str(r["value"]),
        ),
        EdgeKind(
            "sum",
            "Sum Pairs",
            "Digits separated by a numbered circle sum to that number.",
            "sum clue",
            "sum",
            label=lambda r: str(r["sum"]),
        ),
        EdgeKind(
            "product",
            "Product",
            "Digits separated by a numbered circle multiply to that number.",
            "product clue",
            "value",
            label=lambda r: f"×{r['value']}",
        ),
        EdgeKind(
            "ratio",
            "Ratio",
            "Of two digits separated by a ratio clue k:1, one is k times the other.",
            "ratio clue",
            "value",
            label=lambda r: f"{r['value']}:1",
        ),
        EdgeKind(
            "less",
            "Greater-Than",
            "An inequality sign points to the smaller of the two digits it separates.",
            "inequality sign",
            negative=False,
            marker="chevron",
        ),
    )
}
NEG_SELECTOR = {k: v.param for k, v in EDGE.items() if v.negative}


# edge kinds -> engine relation of one pair
def edge_relation(rule, D):
    from ..exchange import FormatError, product_pairs

    k = rule["kind"]
    if k == "kropki":
        return ("diff", 1) if rule["color"] == "white" else ("ratio", 2)
    if k == "xv":
        return ("sum", 10) if rule["letter"] == "X" else ("sum", 5)
    if k == "difference":
        return ("diff", rule["value"])
    if k == "sum":
        return ("sum", rule["sum"])
    if k == "ratio":
        return ("ratio", rule["value"])
    if k == "product":
        return ("allowed", product_pairs(D, rule["value"]))
    if k == "less":
        return ("lt",)
    raise FormatError(f"unknown edge kind {k!r}")


def edge_family(kind, args, D):
    """(family, value) a pair relation is written as when it is an edge clue, or None"""
    from ..exchange import product_pairs

    if kind == "diff" and args == (1,):
        return ("kropki", "white")
    if kind == "ratio" and args == (2,):
        return ("kropki", "black")
    if kind == "anyof" and set(args) == {("diff", 1), ("ratio", 2)}:
        return None
    if kind == "sum" and args in ((10,), (5,)):
        return ("xv", "X" if args == (10,) else "V")
    if kind == "diff" and len(args) == 1:
        return ("difference", args[0])
    if kind == "sum" and len(args) == 1:
        return ("sum", args[0])
    if kind == "ratio" and len(args) == 1:
        return ("ratio", args[0])
    if kind == "lt" and not args:
        return ("less", None)
    if kind == "allowed" and len(args) == 1:
        A = {tuple(x) for x in args[0]}
        for p in range(1, D * D + 1):
            if A == {tuple(x) for x in product_pairs(D, p)}:
                return ("product", p)
    return None


def edge_rule(family, value, a, b, B):
    r = {"type": "edge", "kind": family}
    if EDGE[family].param:
        r[EDGE[family].param] = value
    r["cells"] = [B.name(a), B.name(b)]
    return r


# negative families: which engine relation an uncovered pair gets
def negative_relation(of, sel, D):
    """-> list of (kind, args) for an uncovered pair, in expansion order"""
    from ..exchange import FormatError

    if of == "kropki":
        cols = [sel] if sel else ["white", "black"]
        return [("nonconsec", ()) if c == "white" else ("notratio", (2,)) for c in cols]
    if of == "xv":
        lets = [sel] if sel else ["X", "V"]
        return [("notsum", (10,)) if l == "X" else ("notsum", (5,)) for l in lets]
    if of == "difference":
        return [("notdiff", (sel,))]
    if of == "sum":
        return [("notsum", (sel,))]
    if of == "ratio":
        return [("notratio", (sel,))]
    if of == "product":
        return [("allowed", ([[u, v] for u in range(1, D + 1) for v in range(1, D + 1) if u * v != sel],))]
    raise FormatError(f"negative of {of!r} has no pair relation")
