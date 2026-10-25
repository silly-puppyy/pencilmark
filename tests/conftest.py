import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
CLASSIC = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."


@pytest.fixture(scope="session")
def variants():
    """synthetic variant puzzles (not taken from any website) with their reference cards."""
    return json.loads((FIX / "variants.json").read_text(encoding="utf-8"))
