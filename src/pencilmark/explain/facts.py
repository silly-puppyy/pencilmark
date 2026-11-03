"""Rule facts: the one-sentence reasons solvers give for a rule, used as the `why` of explanation sub-steps. Chosen
from the facts Cracking the Cryptic hosts repeat most (docs/research/rule_facts_library.md in the research notes;
each in at least 5 solve videos), in our own words."""

RULE_FACTS = {
    "thermo": "Digits on a thermometer increase from the bulb to the tip, so a cell with k cells before it is at least k + 1.",
    "slow_thermo": "Digits on a slow thermometer never decrease from the bulb to the tip.",
    "whisper": "Neighbours on a German whisper differ by at least 5.",
    "dutch_whisper": "Neighbours on a Dutch whisper differ by at least 4.",
    "renban": "A renban line holds a set of consecutive digits, in any order, with no repeats.",
    "palindrome": "A palindrome line reads the same from both ends, so mirrored cells hold the same digit.",
    "entropic": "Any three neighbouring cells on an entropic line hold one low (1-3), one middle (4-6) and one high (7-9) digit.",
    "modular": "Any three neighbouring cells on a modular line hold digits with different remainders when divided by 3.",
    "kropki_chain": "A white dot joins two consecutive digits; a black dot joins a digit and its double.",
    "region_sum": "A region-sum line has the same total in every box it passes through.",
    "parity": "Neighbours on a parity line alternate between odd and even.",
    "between": "Digits on a between line lie strictly between the two circle digits at its ends.",
    "zipper": "Cells the same distance from the middle of a zipper line add up to the same total; on a line with a "
    "centre cell that total is the centre digit, so the centre is the line's largest digit.",
    "cage": "Digits in a cage don't repeat and add up to its total.",
    "arrow": "The digits on an arrow add up to the digit in its circle.",
}


def _digits(ds):
    ds = list(ds)
    if len(ds) > 2 and ds == list(range(ds[0], ds[-1] + 1)):
        return f"{ds[0]}-{ds[-1]}"
    return ", ".join(map(str, ds[:-1])) + (" and " if len(ds) > 1 else "") + str(ds[-1])


def derived(kind, D, n=None, k=None):
    """consequences of a rule for this digit range, worked out by enumeration rather than written for 9x9: digits a
    whisper can never hold and whether its neighbours alternate low / high, an arrow's shaft and circle bounds, a
    thermometer's bulb and tip, the digits a long renban must hold -> sentence or "" """
    if kind in ("whisper", "dutch_whisper"):
        k = k or (5 if kind == "whisper" else 4)
        never = [d for d in range(1, D + 1) if not any(abs(d - e) >= k for e in range(1, D + 1))]
        ok = [d for d in range(1, D + 1) if d not in never]
        parts = []
        if never:
            parts.append(f"{_digits(never)} can never be on the line")
        for m in range(1, D):
            if all(not (abs(a - b) >= k and (a <= m) == (b <= m)) for a in ok for b in ok):
                lo, hi = [d for d in ok if d <= m], [d for d in ok if d > m]
                if lo and hi:
                    parts.append(f"neighbours alternate between low ({_digits(lo)}) and high ({_digits(hi)}) digits")
                break
        return ("With digits 1-%d, " % D + " and ".join(parts) + ".") if parts else ""
    if kind == "kropki_chain":
        never = [d for d in range(1, D + 1) if 2 * d > D and d % 2]
        verb = "sits" if len(never) == 1 else "sit"
        return f"With digits 1-{D}, {_digits(never)} never {verb} on a black dot." if never else ""
    if kind == "arrow" and n:
        out = []
        if n >= 2:
            high = list(range(D - n + 2, D + 1))
            out.append(f"{_digits(high)} cannot sit on its {n}-cell shaft")
        out.append(f"its circle is at least {n}" if n > 1 else "its circle equals its one shaft digit")
        return "With digits 1-%d, " % D + "; ".join(out) + "."
    if kind == "thermo" and n and n >= 2:
        return f"On a thermometer of {n} cells the bulb is at most {D - n + 1} and the tip at least {n}."
    if kind == "renban" and n and 2 * n > D:
        must = list(range(D - n + 1, n + 1))
        return f"A {n}-cell renban with digits 1-{D} always holds {_digits(must)}."
    return ""


def rule_fact(kind, D, rule=None):
    """the rule's fact for this puzzle: the base sentence, then what follows for its digit range (derived)"""
    con = getattr(rule, "con", None) or {}
    cells = getattr(rule, "cells", None) or []
    n = len(cells) - 1 if kind == "arrow" else len(cells)
    base = RULE_FACTS.get(kind, "")
    if kind in ("whisper", "dutch_whisper") and con.get("k"):
        base = f"Neighbours on a {'German' if kind == 'whisper' else 'Dutch'} whisper differ by at least {con['k']}."
    more = derived(kind, D, n or None, con.get("k"))
    return (base + " " + more).strip()
