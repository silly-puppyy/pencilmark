"""Puzzle generator with a difficulty / band / technique target (classic and variants, any standard board size).

    from pencilmark.gen import generate, GenerationFailed
    r = generate({"size": 9, "target_band": "Hard", "seed": 1})
    r["puzzle"]   # puzzle JSON (pencilmark/puzzle_json format, with "solution")
    r["card"]     # sudoku-grade card (difficulty, time, band, contains)
    r["info"]     # mode, givens, element counts, attempts, seconds, rejection reasons, unique_verified

Spec fields: see pencilmark.gen.Spec. Modes picked from the spec:
  classic       no elements: dig givens while the band-capped human solve still finishes (unique by construction)
  dig           elements {kind: N} / kinds [...]: the same digging, adding rule elements (cage, thermo, whisper, renban,
                between, arrow, kropki, xv, parity) on demand, then dropping every element not needed
  kropki_full   {"kropki": "full"}: zero givens, every true dot drawn, no dot = neither relation
  kropki_min    {"kropki": "min"}: zero givens, a minimal dot set
  partition     {"cage": "partition"}: killer tiled by cages, merged while still solvable
  cage_count    {"cage": N} + max_givens=0: exactly N cages, no givens (CP-SAT uniqueness)
Every result is re-checked for uniqueness with CP-SAT (pencilmark.cpsat_verify) before it is returned.
Multi-grid boards (samurai etc.) are not supported by the generator.
"""
from .api import Spec, GenerationFailed, generate, feasibility, uniquify, is_unique, BANDS
from .board import Board, BOXES, SYMMETRIES
from .elements import KINDS
from .checks import Checker, Oracle, params

__all__ = ["Spec", "GenerationFailed", "generate", "feasibility", "uniquify", "is_unique", "BANDS", "Board", "BOXES",
           "SYMMETRIES", "KINDS", "Checker", "Oracle", "params"]
