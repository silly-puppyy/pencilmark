"""A short run of tools/fuzz.py: random puzzles true of a random solution (refereed by tools/spec_check.py, written from
the rule pages) are accepted, solved to that solution, graded soundly, round-tripped and graded alike when transposed.
Marked `slow` (it needs tools/ on the path; about a second), run with `pytest -m slow`; `python tools/fuzz.py N` runs more."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fuzz  # noqa: E402


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(0, 40, 2))
def test_fuzz_case(seed):
    s, what, detail = fuzz.case_full(seed)
    assert what in ("ok", "skip", "not unique (fine)"), f"seed {s}: {what}: {detail}"
