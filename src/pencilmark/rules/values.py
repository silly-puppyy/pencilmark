"""Values rules (docs/research/values_rule.md): a custom rule of kind "values" says what cells count as -- a modifier's
VALUE ("x * dbl(x)": doublers; "2 * x" on the circled cells) -- and every clue then reads values, not digits. Houses,
givens and the solution stay digits; a clue opts out with "on": "digits". The reader lowers each clue to custom rules
over its cells' values (lower()), in the shapes the engine's readings know: a sum as "sum(f(x) for x in C)", a chain
(thermo, whisper, palindrome) as one two-cell rule per link -- as the same clue written out by hand."""

from __future__ import annotations

import re

from ..errors import FormatError, NotSupportedError

# rules about which digit a cell holds, not about a clue's arithmetic: never read on values
DIGIT_TYPES = {"grid", "chaos", "box_grid", "box", "row", "column", "region", "fog", "custom", "quadruple", "clone",
               "isomorphic", "vudoku", "yin_yang", "region_border", "same_region", "shading_sight", "shaded_count",
               "same_shading", "different_shading", "region_sight", "border_count", "other_region_sum", "table"}  # fmt: skip
DIGIT_NEIGHBORS = {"antiknight", "antiking"}


def is_values_rule(r):
    return isinstance(r, dict) and r.get("type") == "custom" and r.get("kind") == "values"


def reads_values(r):
    """a clue that reads values once the file has a values rule (not a digit rule, not opted out)"""
    if not isinstance(r, dict) or r.get("on", "values") == "digits" or r.get("type") in DIGIT_TYPES:
        return False
    return not (r.get("type") == "neighbors" and r.get("kind") in DIGIT_NEIGHBORS)


def value_map(rules, all_cells):
    """cell name -> (the value rule's cell variable, its value expression), from every values rule; a cell no values
    rule covers is absent (it counts its digit). Raises FormatError for two values rules on one cell."""
    out = {}
    for i, r in enumerate(rules):
        if not is_values_rule(r):
            continue
        cells = r.get("cells") or {}
        name, cs = next(iter(cells.items())) if cells else ("x", all_cells)
        for c in cs:
            if c in out:
                raise FormatError(f"rule {i}: cell {c} already has a value (two values rules cover it)")
            out[c] = (name, r["value"])
    return out


def lower(rules, vmap, box_of):
    """the rules with each clue reading values replaced by the list of custom rules it lowers to (a clue none of whose
    cells has a value is kept: it reads digits as before; the values rules themselves are kept: the reader skips
    them). box_of: cell name -> its box (region-sum lines split by box)."""
    out = []
    for i, r in enumerate(rules):
        if reads_values(r) and any(c in vmap for c in _cells(r)):
            out.append(_lower(i, r, vmap, box_of))
        else:
            out.append(r)
    return out


def _cells(r):
    out = []
    for k in ("cells", "bulb", "lines", "segments"):
        v = r.get(k)
        stack = [v]
        while stack:
            x = stack.pop()
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, list):
                stack.extend(x)
    return out


def _subst(expr, var, name):
    return "(" + re.sub(rf"\b{re.escape(var)}\b(?!\s*\()", name, expr) + ")"


def _lower(i, r, vmap, box_of):
    t, k = r["type"], r.get("kind")
    cells = _cells(r)
    vals = {vmap.get(c) for c in cells}
    if len(vals) == 1 and None not in vals:  # one value rule over all the clue's cells: the written-out shapes
        var, expr = next(iter(vals))
        V = lambda n: _subst(expr, var, n)
    elif len(vals) == 1:
        V = lambda n: n
    else:
        V = None  # cells of different values rules (or some plain): one variable per cell

    def rule(names, holds, label):
        out = {"type": "custom", "cells": names, "holds": holds, "label": r.get("label") or label}
        for key in ("id", "style"):
            if key in r:
                out[key] = r[key]
        return out

    def val(c, n):  # cell c's value in a rule where c is named n
        if V is not None:
            return V(n)
        return _subst(*vmap[c], n) if c in vmap else n

    def sumv(name, cs):  # the sum of the values of the cells named `name` (a list) -- or, mixed, cell by cell
        if V is not None:
            return f"sum({V('x')} for x in {name})", {name: list(cs)}
        names = {f"{name}{j + 1}": [c] for j, c in enumerate(cs)}
        return " + ".join(val(c, n) for n, (c,) in names.items()), names

    def pair(a, b, f, label):  # a two-cell rule: f(value of a, value of b)
        return rule({"a": [a], "b": [b]}, f(val(a, "a"), val(b, "b")), label)

    links = lambda cs: list(zip(cs, cs[1:]))
    if t == "cage":
        if "sum" not in r:
            return r  # a no-repeat cage: digits
        s, names = sumv("C", r["cells"])
        dist = "all_different(C)" if V is not None else f"all_different([{', '.join(names)}])"
        return rule(names, f"{dist} and {s} == {r['sum']}", "cage on values")
    if t == "sum" and k == "little_killer":
        s, names = sumv("D", r["cells"])
        return rule(names, f"{s} == {r['sum']}", "little killer on values")
    if t == "arrow":
        if len(r["bulb"]) != 1:
            raise NotSupportedError(f"rule {i}: an arrow with a {len(r['bulb'])}-cell bulb is not read on values yet")
        o = r["bulb"][0]
        out = []
        for L in r["lines"]:
            s, names = sumv("L", L)
            out.append(rule({"o": [o], **names}, f"{s} == {val(o, 'o')}", "arrow on values"))
        return out
    if t == "edge":
        a, b = r["cells"]
        if k == "kropki" and r["color"] == "white":
            f = lambda x, y: f"abs({x} - {y}) == 1"
        elif k == "kropki":
            f = lambda x, y: f"{x} == 2 * {y} or {y} == 2 * {x}"
        elif k == "xv":
            f = lambda x, y: f"{x} + {y} == {10 if r['letter'] == 'X' else 5}"
        elif k == "difference":
            f = lambda x, y: f"abs({x} - {y}) == {r['value']}"
        elif k == "sum":
            f = lambda x, y: f"{x} + {y} == {r['sum']}"
        elif k == "product":
            f = lambda x, y: f"{x} * {y} == {r['value']}"
        elif k == "ratio":
            f = lambda x, y: f"{x} == {r['value']} * {y} or {y} == {r['value']} * {x}"
        elif k == "greater":
            f = lambda x, y: f"{x} > {y}"
        else:
            raise NotSupportedError(f'rule {i}: edge {k!r} is not read on values yet ("on": "digits" reads digits)')
        return pair(a, b, f, f"{k} on values")
    if t == "line":
        cs = list(r["cells"])
        if k in ("thermo", "slow_thermo"):
            op = "<" if k == "thermo" else "<="
            return [pair(a, b, lambda x, y: f"{x} {op} {y}", f"{k} on values") for a, b in links(cs)]
        if k == "whisper":
            ring = cs + cs[:1] if r.get("closed") else cs
            n = r.get("value", 5)
            return [pair(a, b, lambda x, y: f"abs({x} - {y}) >= {n}", "whisper on values") for a, b in links(ring)]
        if k == "parity":
            return [pair(a, b, lambda x, y: f"odd({x}) != odd({y})", "parity line on values") for a, b in links(cs)]
        if k == "palindrome":
            h = len(cs) // 2
            return [
                pair(a, b, lambda x, y: f"{x} == {y}", "palindrome on values") for a, b in zip(cs[:h], cs[::-1][:h])
            ]
        if k == "renban":
            if V is not None:
                return rule({"L": cs}, f"let v = [{V('x')} for x in L]; all_different(v) and max(v) - min(v) == len(v) - 1",
                            "renban on values")  # fmt: skip
            names = {f"L{j + 1}": [c] for j, c in enumerate(cs)}
            vs = ", ".join(val(c, n) for n, (c,) in names.items())
            return rule(
                names, f"let v = [{vs}]; all_different(v) and max(v) - min(v) == len(v) - 1", "renban on values"
            )
        if k == "zipper":
            m = len(cs) // 2
            ps = [(cs[j], cs[-1 - j]) for j in range(m)]
            names = {f"z{j + 1}": [c] for j, c in enumerate(cs)}
            nm = {c: n for n, (c,) in names.items()}
            mid = (
                val(cs[m], nm[cs[m]])
                if len(cs) % 2
                else f"{val(ps[0][0], nm[ps[0][0]])} + {val(ps[0][1], nm[ps[0][1]])}"
            )
            h = " and ".join(f"{val(a, nm[a])} + {val(b, nm[b])} == {mid}" for a, b in ps)
            return rule(names, h, "zipper on values")
        if k == "between":
            lo, hi = cs[0], cs[-1]
            out = []
            for c in cs[1:-1]:
                names = {"p": [lo], "q": [hi], "m": [c]}
                vp, vq, vm = val(lo, "p"), val(hi, "q"), val(c, "m")
                out.append(rule(names, f"min({vp}, {vq}) < {vm} and {vm} < max({vp}, {vq})", "between line on values"))
            return out
        if k == "double_arrow":
            se, ne = sumv("e", [cs[0], cs[-1]])
            sm, nmid = sumv("M", cs[1:-1])
            return rule({**ne, **nmid}, f"{sm} == {se}", "double arrow on values")
        if k == "region_sum":
            segs = []
            for c in cs:
                if segs and box_of.get(segs[-1][-1]) == box_of.get(c):
                    segs[-1].append(c)
                else:
                    segs.append([c])
            return _equal(rule, sumv, segs, "region sum line on values")
        raise NotSupportedError(f'rule {i}: line {k!r} is not read on values yet ("on": "digits" reads digits)')
    if t == "equal_sum":
        return _equal(rule, sumv, r["segments"], "equal sums on values")
    raise NotSupportedError(f"rule {i}: {t}{' ' + k if k else ''} is not read on values yet "
                            '("on": "digits" reads digits)')  # fmt: skip


def _equal(rule, sumv, segs, label):
    """segments sharing one sum: "sum(s1) == sum(s2) and sum(s1) == sum(s3) ..." over named segments"""
    if len(segs) < 2:
        return []
    parts = [sumv(f"s{j + 1}", s) for j, s in enumerate(segs)]
    names = {}
    for _, n in parts:
        names.update(n)
    return rule(names, " and ".join(f"{parts[0][0]} == {p[0]}" for p in parts[1:]), label)
