"""Teachable explanations for grader moves.

    from pencilmark import cbackend as CB, explain as E
    steps, ok = CB.solve(p, P, solution=sol)
    for i, step, state in E.replay(p, steps):        # state = grid BEFORE the step
        ex = E.explain(step, p, state)
        print(ex["short"]); print(ex["teach"])

explain(step, puzzle, state) -> dict
    short       one line: "r4c7 = 3: the only place for a 3 in box 6"
    teach       2-5 sentences: where to look, why it works, what it achieves
    concept     {"family", "technique", "name", "lesson"} (reusable across puzzles)
    visual      cells / units / lines / chain links to highlight in a UI
    annotation  placeholders for human annotation
    justification   the structured reason the text was rendered from (schema below)
    derived     True when the justification was reconstructed here (not supplied by the engine)
    verified    True when the reconstructed pattern reproduces the move's placement / eliminations

Justification schema (the same keys are read from the engine's step.move.explain dict when the
engine exports one -- engine fields override derived ones, so richer data plugs straight in):
    technique, digits, placement (cell, digit), eliminations [(cell, digit)],
    base_units / cover_units [group index], base_cells / cover_cells / fins [cell],
    constraints [{"type", "index", "cells", "params"}], links [{"a": (c, d), "b": (c, d),
    "strong": bool, "source": "bivalue|bilocal|constraint|relation|cell|house", "unit": gi}],
    als [{"cells", "digits"}], rcc [digit], z digit, trial {"assume", "events", "contradiction"}.

The reconstruction works on the replayed grid (placed digits + candidates, the C++ engine's own
candidate maintenance), so it needs nothing but the step stream.
"""

from .base import ANNOTATION, CONCEPTS, EXTRA_FAMILY, FAMILY_DISPLAY, LINE_NAMES, Ctx, Namer, fmt_elims, rel_label  # noqa: F401
from .catalog import CATALOG, HD, SHAPE_NOTES, SN, SW, candidate_urls, chain_shape, fish_shape, technique_info  # noqa: F401
from .dispatch import HANDLERS, check, explain, explain_all  # noqa: F401
from .grid import (  # noqa: F401
    Rule,
    State,
    derived,
    direct_excl,
    direct_locks,
    direct_sources,
    enum_rule,
    implied_houses,
    mental_view,
    replay,
    rules,
)
