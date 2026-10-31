"""The "sudoku-puzzle" exchange format, format_version 1 (docs/formats/puzzle-format.md): engine Puzzle <-> exchange dict.

    write(p, meta=None, solution=None) -> dict          engine Puzzle -> canonical sudoku-puzzle dict
    to_internal(doc) -> dict                            sudoku-puzzle dict -> puzzle JSON (pencilmark.puzzle_json)
    read(doc) -> Puzzle                                 sudoku-puzzle dict -> engine Puzzle (not finalized)
    validate(doc)                                       strict reading checks (docs/formats/puzzle-format.md section 4); raises FormatError
    dumps(doc, pretty=True) -> str                      canonical JSON text (docs/formats/puzzle-format.md 8.1)
    fingerprint(doc) -> "sha256:..."                    content fingerprint (docs/formats/puzzle-format.md 8.2)

The format is a transport layer: read(write(p)) builds the same engine structure as p (groups in order, relations and
constraints in order, domains, givens, coordinates), except for the normalisations listed in docs/library/engine-mapping.md (each
mechanic gets ONE engine expansion). The writer therefore works from the engine structure directly and keeps the order of
relations and constraints (the order changes cards).
"""

from __future__ import annotations

from ..rules.edge import NEG_SELECTOR  # noqa: F401  (part of this module's names before the split)
from .board import (  # noqa: F401
    _CACHE,
    _MATHRAX_OK,
    _NUMBERED_OK,
    Board,
    _bat,
    _cb,
    _factor_shapes,
    _pair_clue,
    _rel_pairs,
    _same_set,
    battenburg_table,
    grid_area,
    grid_units,
    product_pairs,
    read_houses,
    subgrid_units,
    vudoku_table,
    window,
)
from .canonical import (  # noqa: F401
    KEY_ORDER,
    RULE_ORDER,
    SET_TYPES,
    _norm_rule,
    _order,
    _rc,
    canonical,
    dumps,
    fingerprint_of_doc,
    jcs,
    semantic_subset,
)
from .common import (  # noqa: F401
    _CELL,
    DIRECTED_OPS,
    FORMAT,
    FORMAT_VERSION,
    KING_DIAG,
    KNIGHT,
    NEIGHBOUR_STEPS,
    NUMBERED_PAIR_FORM,
    OP_KEY,
    OP_PARAM_KEYS,
    OPS,
    ORTHO,
    REL_OP,
    SCHEMA_URL,
    SIDES,
    UNIFY_TABLE_EDGES,
    FormatError,
    NotSupportedError,
    _engine_params_to_op,
    _op_params_to_engine,
    cell_name,
    op_named,
    op_params,
    parse_cell,
)
from .read import _engine_params_json, _ReadCtx, read, to_internal  # noqa: F401
from .validate import (  # noqa: F401
    _RESERVED_OK,
    COMMON,
    EDGE_PARAMS,
    KINDS,
    LINE_PARAMS,
    NEG_OF,
    RESERVED_MSG,
    RULE_KEYS,
    TOP_KEYS,
    _cells,
    _check_op,
    _int,
    _merge_negatives,
    _reserved_ok,
    _validate_rule,
    area_cells,
    resolve_areas,
    validate,
)
from .write import _input_order, _Writer, write  # noqa: F401

# the errors keep their public name in tracebacks (pencilmark.exchange.FormatError, not .common.FormatError)
FormatError.__module__ = NotSupportedError.__module__ = __name__
