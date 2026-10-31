"""Rule families: what the public format knows about each family, in one place (step 5 of the restructure,
docs/research/rule_families_plan.md). Readers, writers, words, drawing and the generator consult these tables instead
of their own lists; the C++ engine keeps its own table (csrc/nary.hpp), checked against the engine kinds in model.py.

line   the line kinds (rules/line.py)
"""

from .line import LINE  # noqa: F401
