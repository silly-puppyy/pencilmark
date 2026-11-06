"""The custom rule language (docs/formats/rules/custom.mdx): a rule written in the file as an expression over cell digits,
{"type": "custom", "cells": {name: [cells]}, "holds": "2 * max(c) == sum(c)", "scope"?, "each"?, "label"?}.

This module parses and checks an expression, evaluates it, prints its canonical form, describes it in words and
compiles a rule to the engine's internal rules (pair relations and digit tables, which the C++ engine propagates).
Grammar and semantics: docs/research/custom_rule_language_design.md (user decisions 2026-11-01 / 02).

Syntax (precedence from loose to tight):
    let NAME = expr; expr          let a = 1, b = a + 1; expr          let NAME(a, b) = expr; expr
    x => expr      (a, b) => expr                                        (predicates: scopes, upto, take_while, ...)
    if expr then expr else expr
    expr ?? expr                                                         (a default for an absent value)
    or   and   not
    == != < <= > >=   in   not in                                        (non-associative)
    + -    * / div mod    unary -    **  (right-associative)
    postfix: f(args)   L[i]   L[a..b]
    atoms: numbers, true, false, names, (expr), [a, b], [e for x in L if P], {a, b}, {a..b}
    f(e for x in L if P) is f([e for x in L if P]).

Values: exact rationals, booleans, lists, sets, cells (a cell is its digit in arithmetic; row / col / box give its
position) and ABSENT (an index out of range, a division by zero): arithmetic with ABSENT is ABSENT, a comparison
with ABSENT is false (!= too), `defined(x)` and `x ?? d` handle edges."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from ..errors import FormatError

# ---------------------------------------------------------------------------------------------------- lexer
TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+)|(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<op>=>|\.\.|\?\?|==|!=|<=|>=|\*\*|[-+*/<>()\[\]{},;=]))"
)
KEYWORDS = {"let", "if", "then", "else", "and", "or", "not", "in", "for", "div", "mod", "true", "false"}


class LangError(FormatError):
    """a malformed expression: the message names the position"""


def lex(src):
    out, pos = [], 0
    while pos < len(src):
        if src[pos:].strip() == "":
            break
        m = TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise LangError(f"unexpected character {src[pos:].lstrip()[:1]!r} at {pos}")
        group = m.lastgroup
        val, start = m.group(group), m.start(group)
        kind = "kw" if group == "name" and val in KEYWORDS else group
        out.append((kind, val, start))
        pos = m.end()
    out.append(("end", "", len(src)))
    return out


# ---------------------------------------------------------------------------------------------------- AST
@dataclass(frozen=True)
class N:
    """one node: op names the construct, args its parts (nodes or plain values)"""

    op: str
    args: tuple = ()


# ---------------------------------------------------------------------------------------------------- parser
CMP = {"==", "!=", "<", "<=", ">", ">="}


class Parser:
    def __init__(self, src):
        self.src, self.t, self.i = src, lex(src), 0

    def peek(self, k=0):
        return self.t[self.i + k]

    def at(self, *vals):
        return self.peek()[1] in vals and self.peek()[0] in ("op", "kw")

    def take(self, val=None):
        tok = self.t[self.i]
        if val is not None and (tok[1] != val or tok[0] not in ("op", "kw")):
            raise LangError(f"expected {val!r} at {tok[2]}, found {tok[1] or 'the end'!r}")
        self.i += 1
        return tok

    def parse(self):
        e = self.expr()
        if self.peek()[0] != "end":
            raise LangError(f"unexpected {self.peek()[1]!r} at {self.peek()[2]}")
        return e

    def expr(self):
        if self.at("let"):
            self.take()
            name = self.take()[1]
            params = None
            if self.at("("):
                self.take()
                params = []
                while not self.at(")"):
                    params.append(self.take()[1])
                    if self.at(","):
                        self.take()
                self.take(")")
            self.take("=")
            val = self.expr()
            if params is None and self.at(","):  # let a = 1, b = 2; body: one binding after another
                self.take(",")
                self.i -= 1
                self.t[self.i] = ("kw", "let", self.t[self.i][2])
                return N("let", (name, val, self.expr()))
            self.take(";")
            body = self.expr()
            if params is not None:
                return N("letfn", (name, tuple(params), val, body))
            return N("let", (name, val, body))
        if self.peek()[0] == "name" and self.peek(1)[1] == "=>":
            name = self.take()[1]
            self.take("=>")
            return N("lambda", ((name,), self.expr()))
        if self.at("(") and self._is_lambda_params():
            self.take("(")
            params = []
            while not self.at(")"):
                params.append(self.take()[1])
                if self.at(","):
                    self.take()
            self.take(")")
            self.take("=>")
            return N("lambda", (tuple(params), self.expr()))
        if self.at("if"):
            self.take()
            c = self.expr()
            self.take("then")
            a = self.expr()
            self.take("else")
            return N("if", (c, a, self.expr()))
        return self.default()

    def _is_lambda_params(self):
        j = self.i + 1
        while self.t[j][0] == "name" or self.t[j][1] == ",":
            j += 1
        return self.t[j][1] == ")" and self.t[j + 1][1] == "=>"

    def default(self):
        e = self.disj()
        while self.at("??"):
            self.take()
            e = N("??", (e, self.disj()))
        return e

    def disj(self):
        e = self.conj()
        while self.at("or"):
            self.take()
            e = N("or", (e, self.conj()))
        return e

    def conj(self):
        e = self.neg()
        while self.at("and"):
            self.take()
            e = N("and", (e, self.neg()))
        return e

    def neg(self):
        if self.at("not"):  # prefix not (the infix "not in" is read in cmp)
            self.take()
            return N("not", (self.neg(),))
        return self.cmp()

    def cmp(self):
        e = self.add()
        if self.peek()[1] in CMP and self.peek()[0] == "op":
            op = self.take()[1]
            e = N(op, (e, self.add()))
        elif self.at("in"):
            self.take()
            e = N("in", (e, self.add()))
        elif self.at("not") and self.peek(1)[1] == "in":
            self.take()
            self.take()
            e = N("not in", (e, self.add()))
        if (self.peek()[1] in CMP and self.peek()[0] == "op") or self.at("in"):
            raise LangError(f"comparisons do not chain (at {self.peek()[2]}): use and")
        return e

    def add(self):
        e = self.mul()
        while self.at("+", "-"):
            op = self.take()[1]
            e = N(op, (e, self.mul()))
        return e

    def mul(self):
        e = self.unary()
        while self.at("*", "/", "div", "mod"):
            op = self.take()[1]
            e = N(op, (e, self.unary()))
        return e

    def unary(self):
        if self.at("-"):
            self.take()
            return N("neg", (self.unary(),))
        return self.power()

    def power(self):
        e = self.postfix()
        if self.at("**"):
            self.take()
            return N("**", (e, self.unary()))
        return e

    def postfix(self):
        e = self.atom()
        while True:
            if self.at("(") and e.op == "name":
                self.take()
                args = []
                if not self.at(")"):
                    first = self.expr()
                    if self.at("for"):  # f(e for x in L if P)
                        args = [self.comprehension(first)]
                    else:
                        args = [first]
                        while self.at(","):
                            self.take()
                            args.append(self.expr())
                self.take(")")
                e = N("call", (e.args[0], tuple(args)))
            elif self.at("["):
                self.take()
                a = self.expr()
                if self.at(".."):
                    self.take()
                    e = N("slice", (e, a, self.expr()))
                else:
                    e = N("index", (e, a))
                self.take("]")
            else:
                return e

    def comprehension(self, body):
        self.take("for")
        var = self.take()[1]
        self.take("in")
        src = self.disj()
        cond = None
        if self.at("if"):
            self.take()
            cond = self.disj()
        return N("comp", (body, var, src, cond))

    def atom(self):
        kind, val, pos = self.peek()
        if kind == "num":
            self.take()
            return N("num", (int(val),))
        if kind == "kw" and val in ("true", "false"):
            self.take()
            return N("bool", (val == "true",))
        if kind == "name":
            self.take()
            return N("name", (val,))
        if self.at("("):
            self.take()
            e = self.expr()
            self.take(")")
            return e
        if self.at("["):
            self.take()
            if self.at("]"):
                self.take()
                return N("list", ())
            first = self.expr()
            if self.at("for"):
                e = self.comprehension(first)
                self.take("]")
                return e
            items = [first]
            while self.at(","):
                self.take()
                items.append(self.expr())
            self.take("]")
            return N("list", tuple(items))
        if self.at("{"):
            self.take()
            if self.at("}"):
                self.take()
                return N("set", ())
            first = self.expr()
            if self.at(".."):
                self.take()
                hi = self.expr()
                self.take("}")
                return N("range", (first, hi))
            items = [first]
            while self.at(","):
                self.take()
                items.append(self.expr())
            self.take("}")
            return N("set", tuple(items))
        raise LangError(f"unexpected {val or 'end of expression'!r} at {pos}")


def parse(src):
    return Parser(src).parse()


# ---------------------------------------------------------------------------------------------------- values
class _Absent:
    __slots__ = ()

    def __repr__(self):
        return "ABSENT"


ABSENT = _Absent()


@dataclass(frozen=True)
class Cell:
    name: str  # "r3c4"
    digit: int

    @property
    def rc(self):
        r, c = re.fullmatch(r"r(\d+)c(\d+)", self.name).groups()
        return int(r), int(c)


def num(v):
    """a value as a number (a cell is its digit); ABSENT stays ABSENT"""
    if isinstance(v, Cell):
        return Fraction(v.digit)
    if isinstance(v, bool):
        raise LangError("a boolean where a number is needed (use num(b))")
    if v is ABSENT or isinstance(v, Fraction):
        return v
    if isinstance(v, int):
        return Fraction(v)
    raise LangError(f"a {type(v).__name__} where a number is needed")


def is_prime(n):
    if n.denominator != 1 or n < 2:
        return False
    n = int(n)
    return all(n % k for k in range(2, int(n**0.5) + 1))


# ---------------------------------------------------------------------------------------------------- evaluator
class Env:
    """names: cell lists ({name: [cell names] or lists of lists}), the grid ({cell name: digit}) and the box shape"""

    def __init__(self, cells, grid, box=(3, 3), parent=None, local=None, layers=None, unknowns=None):
        self.cells, self.grid, self.box, self.parent, self.local = cells, grid, box, parent, local or {}
        # board layers beside the digits: {"region": {cell: label}, "shaded": {cell: bool}} and the file's own layers
        # ({"mod": {cell: value}}); unknowns: the file's named unknowns ({"X": value or None})
        self.layers = layers or {}
        self.unknowns = unknowns or {}

    def child(self, **binds):
        return Env(self.cells, self.grid, self.box, self, binds, self.layers, self.unknowns)

    def lookup(self, name):
        e = self
        while e is not None:
            if name in e.local:
                return e.local[name]
            e = e.parent
        if name in self.cells:
            return self._cellvalue(self.cells[name])
        if name in self.unknowns:  # a named unknown of the file: a number (absent while it is not known)
            v = self.unknowns[name]
            return ABSENT if v is None else Fraction(v)
        if re.fullmatch(r"r\d+c\d+", name):
            return Cell(name, self.grid[name])
        raise LangError(f"unknown name {name!r}")

    def _cellvalue(self, v):
        if isinstance(v, str):
            return Cell(v, self.grid[v])
        if isinstance(v, list) and len(v) == 1 and isinstance(v[0], str):
            return Cell(v[0], self.grid[v[0]])  # a single-cell name is a number (revision 1)
        return [self._cellvalue(x) if isinstance(x, list) else Cell(x, self.grid[x]) for x in v]


def _seq(v):
    if v is ABSENT:
        return ABSENT
    if isinstance(v, (list, tuple)):
        return list(v)
    if isinstance(v, (set, frozenset)):
        return sorted(v)
    if isinstance(v, Cell):
        return [v]
    raise LangError(f"a {type(v).__name__} where a list is needed")


def _eq(a, b):
    if a is ABSENT or b is ABSENT:
        return None
    if isinstance(a, bool) or isinstance(b, bool):
        if not (isinstance(a, bool) and isinstance(b, bool)):
            raise LangError("== between a boolean and a number")
        return a == b
    if isinstance(a, list) or isinstance(b, list):
        return [num(x) for x in _seq(a)] == [num(x) for x in _seq(b)]
    return num(a) == num(b)


def call_fn(f, args, env):
    if isinstance(f, tuple) and f[0] == "fn":  # a lambda or a let-bound helper
        _, params, body, fenv = f
        if len(params) != len(args):
            raise LangError(f"the function takes {len(params)} argument(s), got {len(args)}")
        return evaluate(body, fenv.child(**dict(zip(params, args))))
    raise LangError("calling something that is not a function")


def _agg_numbers(xs):
    xs = [num(x) for x in _seq(xs)]
    return xs


BUILTINS = {}


def builtin(name):
    def deco(f):
        BUILTINS[name] = f
        return f

    return deco


@builtin("sum")
def _sum(env, L):
    xs = _agg_numbers(L)
    return ABSENT if any(x is ABSENT for x in xs) else sum(xs, Fraction(0))


@builtin("product")
def _product(env, L):
    p = Fraction(1)
    for x in _agg_numbers(L):
        if x is ABSENT:
            return ABSENT
        p *= x
    return p


@builtin("min")
def _min(env, *a):
    xs = _agg_numbers(a[0]) if len(a) == 1 else [num(x) for x in a]
    xs = [x for x in xs if x is not ABSENT]
    return min(xs) if xs else ABSENT


@builtin("max")
def _max(env, *a):
    xs = _agg_numbers(a[0]) if len(a) == 1 else [num(x) for x in a]
    xs = [x for x in xs if x is not ABSENT]
    return max(xs) if xs else ABSENT


@builtin("count")
def _count(env, L):
    xs = _seq(L)
    return Fraction(len(xs) if all(not isinstance(x, bool) for x in xs) else sum(1 for x in xs if x is True))


BUILTINS["len"] = lambda env, L: Fraction(len(_seq(L)))
BUILTINS["all"] = lambda env, L: all(x is True for x in _seq(L))
BUILTINS["any"] = lambda env, L: any(x is True for x in _seq(L))
BUILTINS["sort"] = lambda env, L: sorted(_agg_numbers(L))
BUILTINS["reverse"] = lambda env, L: list(reversed(_seq(L)))
BUILTINS["abs"] = lambda env, x: ABSENT if num(x) is ABSENT else abs(num(x))
BUILTINS["odd"] = lambda env, x: num(x) is not ABSENT and num(x).denominator == 1 and num(x) % 2 == 1
BUILTINS["even"] = lambda env, x: num(x) is not ABSENT and num(x).denominator == 1 and num(x) % 2 == 0
BUILTINS["prime"] = lambda env, x: num(x) is not ABSENT and is_prime(num(x))
BUILTINS["num"] = lambda env, b: Fraction(1 if b is True else 0)
BUILTINS["defined"] = lambda env, x: x is not ABSENT
BUILTINS["all_different"] = lambda env, L: len({num(x) for x in _seq(L)}) == len(_seq(L))
BUILTINS["count_distinct"] = lambda env, L: Fraction(len({num(x) for x in _seq(L)}))
BUILTINS["concat"] = lambda env, L: Fraction(int("".join(str(int(num(x))) for x in _seq(L)) or 0))


@builtin("median")
def _median(env, L):
    xs = sorted(_agg_numbers(L))
    if not xs or ABSENT in xs:
        return ABSENT
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


@builtin("seen")
def _seen(env, L):
    out, top = [], None
    for x in _seq(L):
        if top is None or num(x) > top:
            out.append(x)
            top = num(x)
    return out


@builtin("upto")
def _upto(env, L, pred):
    out = []
    for x in _seq(L):
        out.append(x)
        if call_fn(pred, [x], env) is True:
            return out
    return ABSENT  # no element meets the condition: the clue cannot be read


@builtin("take_while")
def _take_while(env, L, pred):
    out = []
    for x in _seq(L):
        if call_fn(pred, [x], env) is not True:
            break
        out.append(x)
    return out


@builtin("take")
def _take(env, n, L):
    n, xs = num(n), _seq(L)
    if n is ABSENT or n.denominator != 1 or n < 0 or n > len(xs):
        return ABSENT
    return xs[: int(n)]


@builtin("position")
def _position(env, L, pred):
    for i, x in enumerate(_seq(L), 1):
        if call_fn(pred, [x], env) is True:
            return Fraction(i)
    return ABSENT


def _pos(env, x, k):
    if not isinstance(x, Cell):
        raise LangError(f"{k}() takes a cell")
    r, c = x.rc
    if k == "row":
        return Fraction(r)
    if k == "col":
        return Fraction(c)
    bh, bw = env.box
    return Fraction((r - 1) // bh * bh + (c - 1) // bw + 1)  # boxes per band = box height (n / box width)


for _k in ("row", "col", "box"):
    BUILTINS[_k] = lambda env, x, _k=_k: _pos(env, x, _k)

LAYERS = {"region": "regions to find (chaos)", "shaded": "shading"}  # function -> the board layer it reads


def _layer(env, x, k):
    """a board layer's value at a cell: region(c) its region's number, shaded(c) whether it is shaded"""
    if not isinstance(x, Cell):
        raise LangError(f"{k}() takes a cell")
    if k not in env.layers:
        raise LangError(f"{k}() needs a puzzle with {LAYERS[k]}")
    v = env.layers[k][x.name]
    return bool(v) if k == "shaded" else Fraction(v)


for _k in LAYERS:
    BUILTINS[_k] = lambda env, x, _k=_k: _layer(env, x, _k)


def evaluate(e, env):
    op, a = e.op, e.args
    if op == "num":
        return Fraction(a[0])
    if op == "bool":
        return a[0]
    if op == "name":
        return env.lookup(a[0])
    if op == "list":
        return [evaluate(x, env) for x in a]
    if op == "set":
        c = getattr(e, "_const", None)  # a set of number literals: built once per node (a 64-rule global entropy as
        if c is not None:  # concat(c) in {...} took 27 min at compile, each tuple re-reading every member)
            return c
        out = frozenset(num(evaluate(x, env)) for x in a)
        if all(x.op == "num" for x in a):
            object.__setattr__(e, "_const", out)
        return out
    if op == "range":
        lo, hi = num(evaluate(a[0], env)), num(evaluate(a[1], env))
        if lo is ABSENT or hi is ABSENT:
            return ABSENT
        return [Fraction(k) for k in range(int(lo), int(hi) + 1)]
    if op == "comp":
        body, var, src, cond = a
        out = []
        for x in _seq(evaluate(src, env)):
            sub = env.child(**{var: x})
            if cond is None or evaluate(cond, sub) is True:
                out.append(evaluate(body, sub))
        return out
    if op == "let":
        return evaluate(a[2], env.child(**{a[0]: evaluate(a[1], env)}))
    if op == "letfn":
        name, params, body, rest = a
        fenv = env.child()
        fenv.local[name] = ("fn", params, body, fenv)  # recursion allowed through fenv
        return evaluate(rest, fenv)
    if op == "lambda":
        return ("fn", a[0], a[1], env)
    if op == "if":
        c = evaluate(a[0], env)
        if not isinstance(c, bool):
            raise LangError("if needs a condition (true / false)")
        return evaluate(a[1] if c else a[2], env)
    if op == "??":
        v = evaluate(a[0], env)
        return evaluate(a[1], env) if v is ABSENT else v
    if op in ("and", "or"):
        x = evaluate(a[0], env)
        if not isinstance(x, bool):
            raise LangError(f"{op} needs conditions")
        if (op == "and" and not x) or (op == "or" and x):
            return x
        y = evaluate(a[1], env)
        if not isinstance(y, bool):
            raise LangError(f"{op} needs conditions")
        return y
    if op == "not":
        x = evaluate(a[0], env)
        if not isinstance(x, bool):
            raise LangError("not needs a condition")
        return not x
    if op in ("==", "!="):
        r = _eq(evaluate(a[0], env), evaluate(a[1], env))
        return False if r is None else (r if op == "==" else not r)  # with ABSENT both are false (revision 7)
    if op in ("<", "<=", ">", ">="):
        x, y = num(evaluate(a[0], env)), num(evaluate(a[1], env))
        if x is ABSENT or y is ABSENT:
            return False
        return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]
    if op in ("in", "not in"):
        x, S = evaluate(a[0], env), evaluate(a[1], env)
        if x is ABSENT or S is ABSENT:
            return False
        hit = num(x) in (S if isinstance(S, frozenset) else {num(y) for y in _seq(S)})
        return hit if op == "in" else not hit
    if op in ("+", "-", "*", "/", "div", "mod", "**"):
        x, y = num(evaluate(a[0], env)), num(evaluate(a[1], env))
        if x is ABSENT or y is ABSENT:
            return ABSENT
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "**":
            return x**y if y.denominator == 1 else ABSENT
        if y == 0:
            return ABSENT
        if op == "/":
            return x / y
        if op == "div":
            return Fraction(x // y)
        return x - y * (x // y)  # mod: non-negative for a positive divisor (floor division)
    if op == "neg":
        x = num(evaluate(a[0], env))
        return ABSENT if x is ABSENT else -x
    if op == "index":
        L, i = _seq(evaluate(a[0], env)), num(evaluate(a[1], env))
        if L is ABSENT or i is ABSENT or i.denominator != 1 or not 1 <= i <= len(L):
            return ABSENT
        return L[int(i) - 1]
    if op == "slice":
        L, i, j = _seq(evaluate(a[0], env)), num(evaluate(a[1], env)), num(evaluate(a[2], env))
        if L is ABSENT or i is ABSENT or j is ABSENT:
            return ABSENT
        i, j = max(int(i), 1), min(int(j), len(L))
        return L[i - 1 : j] if i <= j else []
    if op == "call":
        name, args = a
        try:
            f = env.lookup(name)
        except LangError:
            f = None
        if isinstance(f, tuple):
            return call_fn(f, [evaluate(x, env) for x in args], env)
        if name not in BUILTINS and name in env.layers:  # a layer of the file: its value at a cell
            x = evaluate(args[0], env) if len(args) == 1 else None
            if not isinstance(x, Cell):
                raise LangError(f"{name}() takes a cell")
            v = env.layers[name].get(x.name)
            return ABSENT if v is None else Fraction(v)
        if name not in BUILTINS:
            raise LangError(f"unknown function {name!r}")
        vals = [evaluate(x, env) for x in args]
        if name != "defined" and any(v is ABSENT for v in vals):  # an absent argument: absent (false for conditions)
            return False if name in BOOL_FNS else ABSENT
        return BUILTINS[name](env, *vals)
    raise LangError(f"unknown construct {op}")


def holds(expr, cells, grid, box=(3, 3), layers=None, unknowns=None):
    """does the rule hold for this filling? (expr: text or a parsed tree; layers / unknowns: Env.layers / unknowns)"""
    tree = parse(expr) if isinstance(expr, str) else expr
    v = evaluate(tree, Env(cells, grid, box, layers=layers, unknowns=unknowns))
    if not isinstance(v, bool):
        raise LangError("a rule must be a condition (true / false)")
    return v


# ---------------------------------------------------------------------------------------------------- type check
ARITY = {"sum": 1, "product": 1, "count": 1, "len": 1, "all": 1, "any": 1, "sort": 1, "reverse": 1, "median": 1,
         "abs": 1, "odd": 1, "even": 1, "prime": 1, "num": 1, "defined": 1, "all_different": 1, "count_distinct": 1,
         "concat": 1, "seen": 1, "upto": 2, "take_while": 2, "take": 2, "position": 2, "row": 1, "col": 1, "box": 1,
         "region": 1, "shaded": 1, "min": (1, 2), "max": (1, 2)}  # fmt: skip
BOOL_FNS = {"all", "any", "odd", "even", "prime", "defined", "all_different", "shaded"}
LIST_FNS = {"sort", "reverse", "seen", "upto", "take_while", "take"}


def check(tree, names, unknowns=(), layers=()):
    """static checks on load: known names and functions, arities, conditions where conditions are needed, a condition
    at the top. names: the cell list names; unknowns / layers: the file's named unknowns (numbers) and layers
    (functions of one cell). Returns the top type ('bool', 'num', 'list', 'fn')."""

    def t(e, scope):
        op, a = e.op, e.args
        if op in ("num",):
            return "num"
        if op == "bool":
            return "bool"
        if op == "name":
            n = a[0]
            if n in scope:
                return scope[n]
            if n in names:
                return "cells"
            if n in unknowns or re.fullmatch(r"r\d+c\d+", n):
                return "num"
            raise LangError(f"unknown name {n!r}")
        if op in ("list", "set", "range"):
            for x in a:
                t(x, scope)
            return "list"
        if op == "comp":
            body, var, src, cond = a
            t(src, scope)
            sub = dict(scope, **{var: "num"})
            if cond is not None and t(cond, sub) not in ("bool", "any"):
                raise LangError("the if of a comprehension needs a condition")
            t(body, sub)
            return "list"
        if op == "let":
            return t(a[2], dict(scope, **{a[0]: t(a[1], scope)}))
        if op == "letfn":
            name, params, body, rest = a
            inner = dict(scope, **{name: "fn"}, **{p: "any" for p in params})
            t(body, inner)
            return t(rest, dict(scope, **{name: "fn"}))
        if op == "lambda":
            t(a[1], dict(scope, **{p: "any" for p in a[0]}))
            return "fn"
        if op == "if":
            if t(a[0], scope) not in ("bool", "any"):
                raise LangError("if needs a condition")
            x, y = t(a[1], scope), t(a[2], scope)
            return x if x == y else "any"
        if op in ("and", "or", "not"):
            for x in a:
                if t(x, scope) not in ("bool", "any"):
                    raise LangError(f"{op} needs conditions")
            return "bool"
        if op in CMP or op in ("in", "not in"):
            for x in a:
                t(x, scope)
            return "bool"
        if op in ("+", "-", "*", "/", "div", "mod", "**", "neg", "??"):
            for x in a:
                if t(x, scope) == "bool":
                    raise LangError(f"arithmetic ({op}) on a condition: use num(b)")
            return "num"
        if op in ("index",):
            t(a[0], scope)
            t(a[1], scope)
            return "any"
        if op == "slice":
            for x in a:
                t(x, scope)
            return "list"
        if op == "call":
            name, args = a
            for x in args:
                t(x, scope)
            if scope.get(name) == "fn":
                return "any"
            if name in layers and name not in ARITY:
                if len(args) != 1:
                    raise LangError(f"{name}() takes 1 argument(s), got {len(args)}")
                return "num"
            if name in ("all", "any") and args and args[0].op == "comp":
                body, var, src, cond = args[0].args
                if t(body, dict(scope, **{var: "num"})) not in ("bool", "any"):
                    raise LangError(f"{name}() needs a condition per element: {name}(P for x in L)")
            if name not in ARITY:
                raise LangError(f"unknown function {name!r}")
            ar = ARITY[name]
            if len(args) not in (ar if isinstance(ar, tuple) else (ar,)):
                raise LangError(f"{name}() takes {ar} argument(s), got {len(args)}")
            return "bool" if name in BOOL_FNS else "list" if name in LIST_FNS else "num"
        raise LangError(f"unknown construct {op}")

    top = t(tree, {})
    return top


# ---------------------------------------------------------------------------------------------------- canonical form
PREC = {"??": 1, "or": 2, "and": 3, "not": 4, "==": 5, "!=": 5, "<": 5, "<=": 5, ">": 5, ">=": 5, "in": 5,
        "not in": 5, "+": 6, "-": 6, "*": 7, "/": 7, "div": 7, "mod": 7, "neg": 8, "**": 9}  # fmt: skip


def show(e, parent=0, right=False):
    """the canonical text: single spaces around binary operators, minimal parentheses"""
    op, a = e.op, e.args
    if op == "num":
        return str(a[0])
    if op == "bool":
        return "true" if a[0] else "false"
    if op == "name":
        return a[0]
    if op == "list":
        return "[" + ", ".join(show(x) for x in a) + "]"
    if op == "set":
        return "{" + ", ".join(show(x) for x in a) + "}"
    if op == "range":
        return "{" + show(a[0]) + ".." + show(a[1]) + "}"
    if op == "comp":
        body, var, src, cond = a
        s = f"{show(body)} for {var} in {show(src, 2)}" + (f" if {show(cond, 2)}" if cond is not None else "")
        return "[" + s + "]"
    if op in ("let", "letfn", "lambda", "if"):
        if op == "let":
            s = f"let {a[0]} = {show(a[1])}; {show(a[2])}"
        elif op == "letfn":
            s = f"let {a[0]}({', '.join(a[1])}) = {show(a[2])}; {show(a[3])}"
        elif op == "lambda":
            ps = a[0][0] if len(a[0]) == 1 else "(" + ", ".join(a[0]) + ")"
            s = f"{ps} => {show(a[1])}"
        else:
            s = f"if {show(a[0])} then {show(a[1])} else {show(a[2])}"
        return f"({s})" if parent else s
    if op == "not":
        s = "not " + show(a[0], PREC["not"])
        return f"({s})" if parent > PREC["not"] else s
    if op == "neg":
        s = "-" + show(a[0], PREC["neg"])
        return f"({s})" if parent > PREC["neg"] else s
    if op in PREC:
        p = PREC[op]
        rassoc = op == "**"
        s = f"{show(a[0], p + (1 if rassoc or p == 5 else 0))} {op} {show(a[1], p + (0 if rassoc else 1), True)}"
        return f"({s})" if parent > p else s
    if op == "index":
        return f"{show(a[0], 10)}[{show(a[1])}]"
    if op == "slice":
        return f"{show(a[0], 10)}[{show(a[1])}..{show(a[2])}]"
    if op == "call":
        name, args = a
        if len(args) == 1 and args[0].op == "comp":  # f(e for x in L if P)
            return f"{name}({show(args[0])[1:-1]})"
        return f"{name}(" + ", ".join(show(x) for x in args) + ")"
    raise LangError(f"cannot print {op}")


def canonical(src):
    return show(parse(src))


# ---------------------------------------------------------------------------------------------------- describe
WORDS = {"==": "equals", "!=": "differs from", "<": "is less than", "<=": "is at most", ">": "is greater than",
         ">=": "is at least", "in": "is one of", "not in": "is none of", "+": "plus", "-": "minus", "*": "times",
         "/": "divided by", "div": "divided (whole) by", "mod": "modulo", "**": "to the power"}  # fmt: skip
FN_WORDS = {"sum": "the sum of {0}", "product": "the product of {0}", "min": "the smallest of {0}",
            "max": "the largest of {0}", "len": "the number of {0}", "count": "the number of {0}",
            "all_different": "the digits of {0} are all different", "count_distinct": "the number of different digits in {0}",
            "median": "the median of {0}", "abs": "the absolute value of {0}", "odd": "{0} is odd", "even": "{0} is even",
            "prime": "{0} is prime", "seen": "the digits of {0} seen from its start (each higher than all before)",
            "concat": "{0} read as one number", "sort": "{0} in increasing order", "reverse": "{0} reversed",
            "defined": "{0} exists", "all": "all of {0} hold", "any": "at least one of {0} holds",
            "upto": "{0} up to the first cell where {1}", "take_while": "{0} as long as {1}",
            "take": "the first {0} of {1}", "position": "the position in {0} of the first cell where {1}",
            "row": "the row of {0}", "col": "the column of {0}", "box": "the box of {0}", "num": "1 if {0}, else 0",
            "region": "the region of {0}", "shaded": "{0} is shaded"}  # fmt: skip


def describe(e):
    """the rule in words, from the expression itself (decision 4): per-operator phrases"""
    if isinstance(e, str):
        e = parse(e)
    op, a = e.op, e.args
    if op == "num":
        return str(a[0])
    if op == "bool":
        return "true" if a[0] else "false"
    if op == "name":
        return a[0]
    if op == "list":
        return "the list " + ", ".join(describe(x) for x in a)
    if op == "set":
        return "{" + ", ".join(describe(x) for x in a) + "}"
    if op == "range":
        return f"{describe(a[0])} .. {describe(a[1])}"
    if op == "comp":
        body, var, src, cond = a
        what = (
            f"the {var} in {describe(src)}"
            if body == N("name", (var,))
            else f"{describe(body)} for each {var} in {describe(src)}"
        )
        return what + (f" with {describe(cond)}" if cond is not None else "")
    if op == "let":
        return f"with {a[0]} = {describe(a[1])}: {describe(a[2])}"
    if op == "letfn":
        return f"with {a[0]}({', '.join(a[1])}) = {describe(a[2])}: {describe(a[3])}"
    if op == "lambda":
        return describe(a[1])
    if op == "if":
        return f"if {describe(a[0])} then {describe(a[1])}, else {describe(a[2])}"
    if op in ("and", "or"):
        return f"{describe(a[0])} {op} {describe(a[1])}"
    if op == "not":
        return f"it is not the case that {describe(a[0])}"
    if op == "neg":
        return f"minus {describe(a[0])}"
    if op == "??":
        return f"{describe(a[0])} (or {describe(a[1])} where there is none)"
    if op in WORDS:
        p = PREC.get(op, 0)
        sub = lambda x: f"({describe(x)})" if x.op in PREC and PREC[x.op] < p and p >= 6 else describe(x)
        return f"{sub(a[0])} {WORDS[op]} {sub(a[1])}"
    if op == "index":
        i = describe(a[1])
        return f"cell {f'({i})' if a[1].op in PREC else i} of {describe(a[0])}"
    if op == "slice":
        return f"cells {describe(a[1])} to {describe(a[2])} of {describe(a[0])}"
    if op == "call":
        name, args = a
        if name == "abs" and args[0].op == "-":
            return f"the difference between {describe(args[0].args[0])} and {describe(args[0].args[1])}"
        if name in ("all", "any") and args and args[0].op == "comp":
            body, var, src, cond = args[0].args
            q = "every" if name == "all" else "some"
            dom = f"{var} in {describe(src)}" + (f" with {describe(cond)}" if cond is not None else "")
            return f"for {q} {dom}: {describe(body)}"
        if name in FN_WORDS:
            return FN_WORDS[name].format(*[describe(x) for x in args])
        return f"{name}(" + ", ".join(describe(x) for x in args) + ")"
    return show(e)


# ---------------------------------------------------------------------------------------------------- whole rules
STEPS = {
    "orthogonal": ((0, 1), (1, 0)),
    "diagonal": ((1, 1), (1, -1)),
    "king": ((0, 1), (1, 0), (1, 1), (1, -1)),
    "knight": ((1, 2), (2, 1), (1, -2), (2, -1)),
}


def _rc(name):
    r, c = re.fullmatch(r"r(\d+)c(\d+)", name).groups()
    return int(r), int(c)


def _name(r, c):
    return f"r{r}c{c}"


def rule_holds(rule, grid, box=(3, 3), layers=None):
    """does a custom rule {"type": "custom", "cells": {...}, "holds": "...", "scope"?, "each"?} hold for a filled grid?
    scope: {"pairs": kind} (holds is a predicate (a, b)), {"windows": [h, w]} (a predicate over the window's cells in
    reading order), {"cells": name, "neighbours": kind, "within": "box"?} (a predicate (x, N)); each with "except" (cell
    lists to skip). "each": name -> the rule holds for every tuple of that list of lists, bound to the name."""
    cells, tree = dict(rule.get("cells") or {}), parse(rule["holds"])
    scope, skip = rule.get("scope"), {tuple(sorted(x)) for x in (rule.get("scope") or {}).get("except", [])}
    env = Env(cells, grid, box, layers=layers)
    if rule.get("each"):
        name = rule["each"]
        return all(
            rule_holds(dict(rule, each=None, cells=dict(cells, **{name: t})), grid, box, layers) for t in cells[name]
        )
    if not scope:
        return holds(tree, cells, grid, box, layers)
    f = evaluate(tree, env)
    if not (isinstance(f, tuple) and f[0] == "fn"):
        raise LangError("a scoped rule's holds is a predicate: (a, b) => ..., (x, N) => ... or (w) => ...")
    if "pairs" in scope:
        for name in grid:
            r, c = _rc(name)
            for dr, dc in STEPS[scope["pairs"]]:
                other = _name(r + dr, c + dc)
                if other not in grid or tuple(sorted((name, other))) in skip:
                    continue
                if call_fn(f, [Cell(name, grid[name]), Cell(other, grid[other])], env) is not True:
                    return False
        return True
    if "windows" in scope:
        h, w = scope["windows"]
        for name in grid:
            r, c = _rc(name)
            win = [_name(r + i, c + j) for i in range(h) for j in range(w)]
            if not all(x in grid for x in win) or tuple(sorted(win)) in skip:
                continue
            if call_fn(f, [[Cell(x, grid[x]) for x in win]], env) is not True:
                return False
        return True
    if "neighbours" in scope:
        bh, bw = box
        boxof = lambda n: ((_rc(n)[0] - 1) // bh, (_rc(n)[1] - 1) // bw)
        steps = STEPS[scope["neighbours"]]
        for name in cells[scope["cells"]] if "cells" in scope else list(grid):
            r, c = _rc(name)
            nb = [_name(r + s * dr, c + s * dc) for dr, dc in steps for s in (1, -1)]
            nb = [x for x in nb if x in grid and (scope.get("within") != "box" or boxof(x) == boxof(name))]
            if call_fn(f, [Cell(name, grid[name]), [Cell(x, grid[x]) for x in nb]], env) is not True:
                return False
        return True
    raise LangError(f"unknown scope {scope}")


# ---------------------------------------------------------------------------------------------------- engine compile
MAX_TABLE_CELLS = 5  # a table over n cells enumerates D ** n fillings (9 ** 5 = 59,049); larger: an expr constraint


def _positional(tree):
    """does the expression read cell positions (row / col / box, or a cell named in the text)?"""
    if not isinstance(tree, N):
        return False
    if tree.op == "call" and tree.args[0] in ("row", "col", "box"):
        return True
    if tree.op == "name" and re.fullmatch(r"r\d+c\d+", tree.args[0]):
        return True
    return any(_positional(x) for x in tree.args if isinstance(x, N)) or any(
        _positional(y) for x in tree.args if isinstance(x, tuple) for y in x if isinstance(y, N)
    )


def _layered(tree):
    """the board layers an expression reads (region(), shaded()); see _hidden for the file's unknowns and layers"""
    if not isinstance(tree, N):
        return set()
    out = {tree.args[0]} if tree.op == "call" and tree.args[0] in LAYERS else set()
    for x in tree.args:
        if isinstance(x, N):
            out |= _layered(x)
        elif isinstance(x, tuple):
            for y in x:
                out |= _layered(y)
    return out


def _table(test, names, D):
    """digit tuples over the named cells for which test(grid) holds"""
    import itertools

    return [list(ds) for ds in itertools.product(range(1, D + 1), repeat=len(names)) if test(dict(zip(names, ds)))]


def _concat_table(tree, cells, names, D):
    """concat(c) in {n1, n2, ...} over one list of cells (D <= 9): the table's rows are the listed numbers' digits, no
    enumeration needed (the v12 migration writes table rules this way); None for any other shape"""
    if tree.op != "in" or D > 9:
        return None
    lhs, rhs = tree.args
    if lhs.op != "call" or lhs.args[0] != "concat" or len(lhs.args[1]) != 1 or lhs.args[1][0].op != "name":
        return None
    if cells.get(lhs.args[1][0].args[0]) != names or rhs.op != "set" or not all(x.op == "num" for x in rhs.args):
        return None
    digits = "".join(str(d) for d in range(1, D + 1))
    rows = {str(x.args[0]) for x in rhs.args}
    return [[int(ch) for ch in t] for t in sorted(rows) if len(t) == len(names) and all(ch in digits for ch in t)]


def _expr(rule, B):
    """an unscoped rule as the engine's expression constraint (csrc/expr.cpp): checked once its cells are fixed"""
    unk, lay = list(getattr(B, "unknowns", {}) or ()), list(getattr(B, "layers", {}) or ())
    ir, names, lists, nslots = to_ir(rule, unk, lay)
    pos = [[B.coords[B.idx(n)][0] + 1, B.coords[B.idx(n)][1] + 1] for n in names]
    out = {"type": "expr", "cells": names, "ir": ir, "lists": lists, "nslots": nslots, "pos": pos,
           "box": list(B_box(B))}  # fmt: skip
    hid = _hidden(parse(rule["holds"]), dict.fromkeys(unk), dict.fromkeys(lay))
    if hid:  # the aux variables it reads: its unknowns, and each read layer's value at each of its cells
        Nb = len(B.coords)
        read = [unk.index(h) for h in hid if h in unk]
        read += [len(unk) + lay.index(h) * Nb + B.idx(n) for h in hid if h in lay for n in names]
        out["aux"] = {"u": len(unk), "n": Nb, "read": sorted(set(read))}
    return out


def _instance(holds_text, args, B, D, test):
    """one instance of a scoped rule: a digit table when small, else the predicate applied to the instance's cells as
    an expression constraint (let __f = <predicate>; __f(__a0, __a1, ...))"""
    names = [n for a in args for n in (a if isinstance(a, list) else [a])]
    if len(names) <= MAX_TABLE_CELLS:
        return {"type": "table", "cells": names, "allowed": _table(test, names, D)}
    cells = {f"__a{i}": (a if isinstance(a, list) else [a]) for i, a in enumerate(args)}
    call = ", ".join(f"__a{i}" for i in range(len(args)))
    return _expr({"cells": cells, "holds": f"let __f = {holds_text}; __f({call})"}, B)


def _hidden(tree, unknowns, layers):
    """the file's unknowns and layers an expression reads"""
    if not isinstance(tree, N):
        return set()
    out = set()
    if tree.op == "name" and tree.args[0] in unknowns:
        out.add(tree.args[0])
    if tree.op == "call" and tree.args[0] in layers and tree.args[0] not in BUILTINS:
        out.add(tree.args[0])
    for x in tree.args:
        if isinstance(x, N):
            out |= _hidden(x, unknowns, layers)
        elif isinstance(x, tuple):
            for y in x:
                out |= _hidden(y, unknowns, layers)
    return out


def _const_reads(tree, name):
    """the constant indices at which tree reads the list `name`, or None when it uses the list any other way
    (whole: sum(L), position(L, ...), len(L); or at a computed index)"""
    found, whole = set(), False

    def walk(t):
        nonlocal whole
        if not isinstance(t, N):
            return
        if t.op == "index" and isinstance(t.args[0], N) and t.args[0].op == "name" and t.args[0].args[0] == name:
            i = t.args[1]
            if isinstance(i, N) and i.op == "num" and isinstance(i.args[0], int):
                found.add(i.args[0])
            else:
                whole = True
            walk(i)
            return
        if t.op == "name" and t.args[0] == name:
            whole = True
            return
        for x in t.args:
            if isinstance(x, N):
                walk(x)
            elif isinstance(x, tuple):
                for y in x:
                    walk(y)

    walk(tree)
    return None if whole or not found else sorted(found)


def _narrowed(tree, cells):
    """a rule that reads a list only at constant indices reads only those cells ("ray[3] + ray[4] == 3" over a
    9-cell ray): the list shrinks to them and the indices are renumbered, so the table spans 2 cells, not 9"""
    import dataclasses

    keep = {}
    for name, v in cells.items():
        if isinstance(v, list) and len(v) > 1 and all(isinstance(x, str) for x in v):
            ix = _const_reads(tree, name)
            if ix and all(1 <= i <= len(v) for i in ix) and len(ix) < len(v):
                keep[name] = ix
    if not keep:
        return tree, cells

    def re_ix(t):
        if not isinstance(t, N):
            return t
        if t.op == "index" and isinstance(t.args[0], N) and t.args[0].op == "name" and t.args[0].args[0] in keep:
            name = t.args[0].args[0]
            return dataclasses.replace(t, args=(t.args[0], N("num", (keep[name].index(t.args[1].args[0]) + 1,))))
        return dataclasses.replace(
            t,
            args=tuple(
                re_ix(x) if isinstance(x, N) else tuple(re_ix(y) for y in x) if isinstance(x, tuple) else x
                for x in t.args
            ),
        )

    cells = dict(cells, **{n: [cells[n][i - 1] for i in ix] for n, ix in keep.items()})
    return re_ix(tree), cells


def compile_rule(rule, B, D, layers=()):
    """a custom rule -> internal puzzle rules for the engine: {"type": "pairs", "rel": "allowed", ...} for pair scopes,
    {"type": "table", "cells", "allowed"} otherwise. B: the board helper (exchange.board.Board). Raises LangError when
    the rule is malformed or too large for a table."""
    tree = parse(rule["holds"])
    hid = _hidden(tree, getattr(B, "unknowns", {}), getattr(B, "layers", {}))
    if hid:  # unknowns / layers: an expression constraint over cells and the engine's aux variables
        if rule.get("each"):
            return [
                x
                for t in rule["cells"][rule["each"]]
                for x in compile_rule(
                    dict(rule, each=None, cells=dict(rule["cells"], **{rule["each"]: t})), B, D, layers
                )
            ]
        sc = rule.get("scope") or {}
        if sc and set(sc) - {"pairs", "except"}:
            raise LangError("a scoped rule reading unknowns / layers takes a pairs scope only, for now")
        if sc:  # one expression constraint per pair: the predicate applied to the two cells
            skip = {tuple(sorted(x)) for x in sc.get("except", [])}
            out = []
            for a, b in B.pairs(STEPS[sc["pairs"]]):
                na, nb = B.name(a), B.name(b)
                if tuple(sorted((na, nb))) in skip:
                    continue
                out.append(
                    _expr(
                        {"cells": {"__a0": [na], "__a1": [nb]}, "holds": f"let __f = {rule['holds']}; __f(__a0, __a1)"},
                        B,
                    )
                )
            return out
        return [_expr(rule, B)]
    used = _layered(tree)
    if used - set(layers):
        raise LangError(
            f"{', '.join(sorted(used - set(layers)))}() needs a board with "
            + " and ".join(LAYERS[k] for k in sorted(used - set(layers)))
        )
    if used:  # an expression constraint the search checks with the layers (never a digit table)
        if rule.get("scope") or rule.get("each"):
            raise LangError(f"{', '.join(sorted(used))}() is not supported yet in a scoped or each rule")
        return [_expr(rule, B)]
    cells = dict(rule.get("cells") or {})
    scope = rule.get("scope") or {}
    skip = {tuple(sorted(x)) for x in scope.get("except", [])}
    pos = _positional(tree)
    out = []
    if rule.get("each"):
        name = rule["each"]
        for t in cells[name]:
            out += compile_rule(dict(rule, each=None, cells=dict(cells, **{name: t})), B, D)
        return out
    if not scope:
        tree, cells = _narrowed(tree, cells)
        names = []
        for v in cells.values():
            for x in v if isinstance(v, list) else [v]:
                for y in x if isinstance(x, list) else [x]:
                    if y not in names:
                        names.append(y)
        names += [n for n in dict.fromkeys(re.findall(r"\br\d+c\d+\b", rule["holds"])) if n not in names]
        if len(names) > MAX_TABLE_CELLS:
            return [_expr(rule, B)]
        allowed = _concat_table(tree, cells, names, D)
        if allowed is None:
            allowed = _table(lambda g: holds(tree, cells, g), names, D)
        return [{"type": "table", "cells": names, "allowed": allowed}]
    f = evaluate(tree, Env(cells, {}, B_box(B)))
    if not (isinstance(f, tuple) and f[0] == "fn"):
        raise LangError("a scoped rule's holds is a predicate: (a, b) => ..., w => ... or (x, N) => ...")
    env = Env(cells, {}, B_box(B))
    if "pairs" in scope:
        steps = STEPS[scope["pairs"]]
        groups = {}
        for a, b in B.pairs(steps):
            na, nb = B.name(a), B.name(b)
            if tuple(sorted((na, nb))) in skip:
                continue
            key = (na, nb) if pos else None
            if key not in groups:
                ok = [[u, v] for u in range(1, D + 1) for v in range(1, D + 1)
                      if call_fn(f, [Cell(na, u), Cell(nb, v)], env) is True]  # fmt: skip
                groups[key] = (ok, [])
            groups[key][1].append([na, nb])
        return [{"type": "pairs", "rel": "allowed", "params": [ok], "cells": prs} for ok, prs in groups.values()]
    if "windows" in scope:
        h, w = scope["windows"]
        shared = None
        for r, c in sorted(B.cid):
            win = [(r + i, c + j) for i in range(h) for j in range(w)]
            if not all(x in B.cid for x in win):
                continue
            names = [B.name(B.cid[x]) for x in win]
            if tuple(sorted(names)) in skip:
                continue
            test = lambda g, names=names: call_fn(f, [[Cell(n, g[n]) for n in names]], env) is True
            if len(names) > MAX_TABLE_CELLS:
                out.append(_instance(rule["holds"], [names], B, D, test))
                continue
            if pos or shared is None:
                allowed = _table(test, names, D)
                shared = None if pos else allowed
            out.append({"type": "table", "cells": names, "allowed": allowed if pos else shared})
        return out
    if "neighbours" in scope:
        bh, bw = B_box(B)
        steps = STEPS[scope["neighbours"]]
        targets = cells[scope["cells"]] if scope.get("cells") else [B.name(i) for i in range(len(B.coords))]
        shared_nb = {}
        for name in targets if isinstance(targets, list) else [targets]:
            r, c = B.coords[B.idx(name)]
            nb = [(r + s * dr, c + s * dc) for dr, dc in steps for s in (1, -1)]
            nb = [
                x
                for x in nb
                if x in B.cid and (scope.get("within") != "box" or (x[0] // bh, x[1] // bw) == (r // bh, c // bw))
            ]
            names = [name] + [B.name(B.cid[x]) for x in nb]
            test = lambda g, names=names: (
                call_fn(f, [Cell(names[0], g[names[0]]), [Cell(n, g[n]) for n in names[1:]]], env) is True
            )
            if len(names) <= MAX_TABLE_CELLS and not pos:  # the table depends only on how many neighbours a cell has
                if len(names) not in shared_nb:
                    shared_nb[len(names)] = _table(test, names, D)
                out.append({"type": "table", "cells": names, "allowed": shared_nb[len(names)]})
                continue
            out.append(_instance(rule["holds"], [names[0], names[1:]], B, D, test))
        return out
    raise LangError(f"unknown scope {sorted(scope)}")


def B_box(B):
    """the board's box shape for box(): standard boxes of its size"""
    from ..puzzle_json import BOXES

    return BOXES.get(B.D, (B.D, 1))


def describe_rule(rule):
    """a whole custom rule in words: its scope, then the condition"""
    scope, body = rule.get("scope") or {}, parse(rule["holds"])
    cond = describe(body.args[1] if body.op == "lambda" else body)
    params = body.args[0] if body.op == "lambda" else ()
    skip = " (except the listed ones)" if scope.get("except") else ""
    if "pairs" in scope:
        a, b = (params + ("a", "b"))[:2]
        return f"For every pair of {scope['pairs']} neighbours {a}, {b}{skip}: {cond}."
    if "windows" in scope:
        h, w = scope["windows"]
        return f"For every {h} x {w} block {params[0] if params else 'w'}{skip}: {cond}."
    if "neighbours" in scope:
        x, nb = (params + ("x", "N"))[:2]
        within = " in its box" if scope.get("within") == "box" else ""
        where = f" of {scope['cells']}" if scope.get("cells") else ""
        return f"For every cell {x}{where}, with {nb} its {scope['neighbours']} neighbours{within}{skip}: {cond}."
    if rule.get("each"):
        return f"For every {rule['each']}: {cond}."
    return cond[:1].upper() + cond[1:] + "."


# ---------------------------------------------------------------------------------------------------- C++ IR
# the expression as nested lists of ints for the engine's evaluator (csrc/expr.cpp, NT_EXPR): names resolved to cell
# variables, cell-list indices and slots (one per binding site), built-ins to ids. Keep in step with csrc/expr.hpp.
OPS = ("num", "bool", "cells", "cell", "slot", "list", "range", "comp", "let", "letfn", "lambda", "if", "??", "or",
       "and", "not", "==", "!=", "<", "<=", ">", ">=", "in", "not in", "+", "-", "*", "/", "div", "mod", "**", "neg",
       "index", "slice", "call", "callfn", "none", "aux", "auxcell")  # fmt: skip
OPCODE = {op: i for i, op in enumerate(OPS)}
FNS = ("sum", "product", "min", "max", "count", "len", "all", "any", "sort", "reverse", "abs", "odd", "even", "prime",
       "num", "defined", "all_different", "count_distinct", "concat", "median", "seen", "upto", "take_while", "take",
       "position", "row", "col", "box", "region", "shaded")  # fmt: skip
FNCODE = {f: i for i, f in enumerate(FNS)}


def to_ir(rule, unknowns=(), layers=()):
    """a custom rule (no scope) -> (ir, cell names, cell lists): ir nested lists of ints; cell names the engine variables
    in order; cell lists the rule's named lists as variable indices (nested for lists of lists). unknowns / layers: the
    file's names in order; an unknown is read as ["aux", its index], a layer call L(x) as ["auxcell", L's index, x]
    (the engine's aux variables: unknowns first, then each layer's value per board cell)"""
    tree = parse(rule["holds"])
    unknowns, layers = list(unknowns), list(layers)
    names, lists, list_index = [], [], {}

    def var(c):
        if c not in names:
            names.append(c)
        return names.index(c)

    for k, v in (rule.get("cells") or {}).items():
        list_index[k] = len(lists)
        if len(v) == 1 and isinstance(v[0], str):  # a one-cell name is a number, not a list
            lists.append(var(v[0]))
        else:
            lists.append([[var(c) for c in x] if isinstance(x, list) else var(x) for x in v])
    slots = [0]

    def emit(e, scope):
        op, a = e.op, e.args
        code = OPCODE
        if op == "num":
            return [code["num"], int(a[0])]
        if op == "bool":
            return [code["bool"], 1 if a[0] else 0]
        if op == "name":
            n = a[0]
            if n in scope:
                return [code["slot"], scope[n]]
            if n in list_index:
                return [code["cells"], list_index[n]]
            if n in unknowns:
                return [code["aux"], unknowns.index(n)]
            if re.fullmatch(r"r\d+c\d+", n):
                return [code["cell"], var(n)]
            raise LangError(f"unknown name {n!r}")
        if op in ("list", "set"):
            return [code["list"]] + [emit(x, scope) for x in a]
        if op == "range":
            return [code["range"], emit(a[0], scope), emit(a[1], scope)]
        if op == "comp":
            body, v, src, cond = a
            s = slots[0] = slots[0] + 1
            inner = dict(scope, **{v: s})
            return [code["comp"], s, emit(src, scope), emit(body, inner), emit(cond, inner) if cond else [code["none"]]]
        if op == "let":
            s = slots[0] = slots[0] + 1
            return [code["let"], s, emit(a[1], scope), emit(a[2], dict(scope, **{a[0]: s}))]
        if op == "letfn":
            name, params, body, rest = a
            f = slots[0] = slots[0] + 1
            ps = []
            for _ in params:
                slots[0] += 1
                ps.append(slots[0])
            fscope = dict(scope, **{name: f}, **dict(zip(params, ps)))
            return [code["letfn"], f, ps, emit(body, fscope), emit(rest, dict(scope, **{name: f}))]
        if op == "lambda":
            ps = []
            for _ in a[0]:
                slots[0] += 1
                ps.append(slots[0])
            return [code["lambda"], ps, emit(a[1], dict(scope, **dict(zip(a[0], ps))))]
        if op == "call":
            name, args = a
            if name in scope:
                return [code["callfn"], scope[name]] + [emit(x, scope) for x in args]
            if name in layers and name not in FNCODE:
                return [code["auxcell"], layers.index(name), emit(args[0], scope)]
            if name not in FNCODE:
                raise LangError(f"unknown function {name!r}")
            return [code["call"], FNCODE[name]] + [emit(x, scope) for x in args]
        if op in OPCODE:
            return [code[op]] + [emit(x, scope) for x in a]
        raise LangError(f"cannot compile {op}")

    ir = emit(tree, {})
    return ir, names, lists, slots[0] + 1
