"""The technique registry: every fact about a technique, a chip code or an engine pattern code, read from three tables
in pencilmark/data. Grader, card, generator and explainer modules derive their lookups from here; nothing else holds a
copy. The C++ engine keeps its own enum (csrc/solver.hpp), which tests/test_registry.py checks against this table.

data/techniques.csv, one row per engine technique (solver.TECH_NAMES):
  id              the engine's technique id (enum Tech in csrc/solver.hpp)
  const           the constant naming it in csrc/solver.hpp and pencilmark/solver.py
  name            the engine name (params, steps, explanations)
  role            logic | notes (writing pencil marks) | guess | pseudo (a switch, not a move: CanonicalEnumeration)
  code            the chip code on the card (codes.csv); blank for TakeNotes and CanonicalEnumeration, which are never
                  shown
  display         the chip's name for this technique; blank = the code's name in codes.csv
  band            the band of a step by this technique (BANDS); for a split technique, its lowest shape's band; blank
                  for steps that have no band (notes, guess, pseudo)
  split           1: the band depends on the shape found (X-Wing vs Franken X-Wing, Skyscraper vs long X-Chain), so the
                  route names the step by its shape (codes.csv shape_band)
  family          the pricing family (FAMILIES): the engine's structural groups for features; blank for the roles
                  other than logic
  simplicity      textbook order inside the family (pattern size: Y-Wing before WXYZ-Wing); not read by the
                  grader since the family-ordered search was removed (to be dropped with the other dead data)
  gate            any: switched on only for puzzles with some variant rule; sum: only with a sum rule; blank: always
  direct          1: a move made without pencil marks (also csrc/solver.hpp is_direct)
  mental          1: worked out in the head on the no-notes view (a subset, short chain or case split without notes):
                  priced at least as its written form (params mental_floor), left out of the card score's first solve
  price_fallback  blank: the technique has its own fitted price B. Otherwise it has none: it is always priced by the
                  structural meta model and borrows this technique's B when params carry no meta model

data/codes.csv, one row per chip code a route step can carry:
  code        three-letter chip code, Andrew Stuart's (sudokuwiki.org) where he has the strategy
  name        the code's name (CLI lists, alternatives)
  shape_band  band of a step named by this shape (a Skyscraper is Hard, a long X-Chain Very Hard); blank for codes that
              only name a technique (the technique's band applies)
  order       study order inside a band: the route takes the lowest first; ties go to the cheaper move
  subset_of   the codes this one is always a special case of (every X-Wing is a Skyscraper), space-separated
  se_classic  Sudoku Explainer rating (Juillerat's table, the one expert solvers quote); "-": SE has no such
              technique (se.py rates it 7.0)
  se_diuf     the DiufSudoku fork's rating where it differs from se_classic; blank = the same
  explain     the explanation catalogue entry that teaches it (explain.CATALOG: names, aliases, links to explainer
              sites); blank when there is none
  note        why: the reason for a subset_of entry or an order (free text, not read by the code)

data/patterns.csv, one row per pattern code the engine puts on a move (Move.code, an int):
  cpp_code      the int the engine writes
  engine_code   its name in Python (cbackend.code_name)
  technique     the engine technique whose steps this code renames (blank: the code does not rename the step)
  code          the chip code of a step with this pattern
  step_name     the step's name on the route
  explain_name  the pattern's name in explanations (explain.py; blank = the technique's)
  catalog_key   the explanation catalogue entry for this pattern (explain.CATALOG)
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from functools import cache

from . import _data

BANDS = ["Very Easy", "Easy", "Medium", "Hard", "Very Hard", "Expert", "Extreme"]
# pricing families, simplest first (metrics.family_of gives the index)
FAMILIES = ("singles", "intersections+combos", "subsets", "fish+wings", "chains", "ALS", "trial")
ROLES = ("logic", "notes", "guess", "pseudo")
GATES = ("", "any", "sum")


@dataclass(frozen=True)
class Technique:
    """One row of data/techniques.csv (columns in the module docstring)."""

    id: int
    const: str
    name: str
    role: str
    code: str
    display: str
    band: int | None
    split: bool
    family: str
    simplicity: int | None
    gate: str
    direct: bool
    mental: bool
    price_fallback: str


@dataclass(frozen=True)
class Code:
    """One row of data/codes.csv (columns in the module docstring)."""

    code: str
    name: str
    shape_band: int | None
    order: float
    subset_of: tuple[str, ...]
    se_classic: float | None
    se_diuf: float | None
    explain: str


@dataclass(frozen=True)
class Pattern:
    """One row of data/patterns.csv (columns in the module docstring)."""

    cpp_code: int
    engine_code: str
    technique: str
    code: str
    step_name: str
    explain_name: str
    catalog_key: str


def _rows(name):
    return list(csv.DictReader(io.StringIO(_data.read_text(name))))


def _band(s, where):
    if not s:
        return None
    if s not in BANDS:
        raise ValueError(f"{where}: band {s!r} is not one of {BANDS}")
    return BANDS.index(s)


def _flag(s, where):
    if s not in ("0", "1"):
        raise ValueError(f"{where}: flag {s!r} must be 0 or 1")
    return s == "1"


def _choice(s, allowed, where):
    if s not in allowed:
        raise ValueError(f"{where}: {s!r} is not one of {allowed}")
    return s


@cache
def techniques() -> tuple[Technique, ...]:
    """Every engine technique, in file order (data/techniques.csv)."""
    out = []
    for r in _rows("techniques.csv"):
        w = f"techniques.csv {r['name']}"
        out.append(
            Technique(
                id=int(r["id"]),
                const=r["const"],
                name=r["name"],
                role=_choice(r["role"], ROLES, w),
                code=r["code"],
                display=r["display"],
                band=_band(r["band"], w),
                split=_flag(r["split"], w),
                family=_choice(r["family"], ("",) + FAMILIES, w),
                simplicity=int(r["simplicity"]) if r["simplicity"] else None,
                gate=_choice(r["gate"], GATES, w),
                direct=_flag(r["direct"], w),
                mental=_flag(r["mental"], w),
                price_fallback=r["price_fallback"],
            )
        )
    return tuple(out)


@cache
def codes() -> dict[str, Code]:
    """Chip code -> its row of data/codes.csv, in file order."""
    out = {}
    for r in _rows("codes.csv"):
        w = f"codes.csv {r['code']}"
        se = r["se_classic"]
        if not se:
            raise ValueError(f"{w}: se_classic is empty; give Sudoku Explainer's rating, or '-' when SE has none")
        out[r["code"]] = Code(
            code=r["code"],
            name=r["name"],
            shape_band=_band(r["shape_band"], w),
            order=float(r["order"]),
            subset_of=tuple(r["subset_of"].split()),
            se_classic=None if se == "-" else float(se),
            se_diuf=float(r["se_diuf"]) if r["se_diuf"] else None,
            explain=r["explain"],
        )
    return out


@cache
def patterns() -> tuple[Pattern, ...]:
    """Every engine pattern code, by cpp_code (data/patterns.csv)."""
    return tuple(
        Pattern(
            cpp_code=int(r["cpp_code"]),
            engine_code=r["engine_code"],
            technique=r["technique"],
            code=r["code"],
            step_name=r["step_name"],
            explain_name=r["explain_name"],
            catalog_key=r["catalog_key"],
        )
        for r in _rows("patterns.csv")
    )


@cache
def by_name() -> dict[str, Technique]:
    """Engine name -> technique."""
    return {t.name: t for t in techniques()}


def chip(t: Technique) -> tuple[str, str]:
    """(chip code, chip name) of a technique that has a code."""
    return t.code, t.display or codes()[t.code].name
