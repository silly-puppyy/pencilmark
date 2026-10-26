"""Quick check of an installed wheel (cibuildwheel test-command): the C++ core loads, rates, solves and round-trips.
The full suite is tests/ (run by tests.yml)."""
import json
import sys
import time
from pathlib import Path

import pencilmark

t0 = time.time()
CLASSIC = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."
card = pencilmark.rate(CLASSIC)
assert (card["band"], card["difficulty"]) == ("Medium", 5.9), card
assert len(pencilmark.solve(CLASSIC)) == 81
doc = pencilmark.to_export(CLASSIC)
pencilmark.validate(doc)
assert pencilmark.fingerprint(doc) == pencilmark.fingerprint(CLASSIC)
v = json.load(open(Path(__file__).parent / "fixtures" / "variants.json"))[0]
assert pencilmark.rate(v["puzzle"])["band"] == v["card"]["band"], v["name"]
print(f"smoke ok ({time.time() - t0:.1f}s, python {sys.version.split()[0]})")
