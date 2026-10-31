"""Rule families: what the public format knows about each family, in one place (step 5 of the restructure,
docs/research/rule_families_plan.md). Readers, writers, words, drawing and the generator consult these tables instead
of their own lists; the C++ engine keeps its own table (csrc/nary.hpp), checked against the engine kinds in model.py.

line   the line kinds (rules/line.py)
edge   the edge kinds (rules/edge.py)
cell   the cell kinds (rules/cell.py)
"""

from .cell import CELL  # noqa: F401
from .edge import EDGE  # noqa: F401
from .line import LINE  # noqa: F401
