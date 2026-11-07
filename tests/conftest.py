import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
CLASSIC = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."


@pytest.fixture(scope="session")
def variants():
    """synthetic variant puzzles (not taken from any website) with their reference cards."""
    return json.loads((FIX / "variants.json").read_text(encoding="utf-8"))


@pytest.fixture
def reserved_ok():
    """read the rules reserved for a later version of the format (shading, regions to find), as internal tooling may"""
    from pencilmark.exchange.validate import _reserved_ok

    with _reserved_ok():
        yield
