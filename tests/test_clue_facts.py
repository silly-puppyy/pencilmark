"""The clue facts catalog (pencilmark/explain/clue_facts.py) and its page (docs/grades/clue-facts.md)."""

import subprocess
import sys
from pathlib import Path

import pytest

from pencilmark.explain.clue_facts import FACTS

ROOT = Path(__file__).resolve().parents[1]


def test_page_lists_every_fact():
    """every fact is on the page once, ids unique, each probe claims something"""
    page = (ROOT / "docs/grades/clue-facts.md").read_text()
    assert len({f.id for f in FACTS}) == len(FACTS)
    for f in FACTS:
        assert page.count(f"| {f.text} |") == 1, f.id
        assert f.expect and f.probe, f.id


@pytest.mark.slow
def test_clue_facts_hold():
    """every fact's probe eliminations are true (brute force), the grader makes them, and the page is current"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/gen_clue_facts_md.py"), "--check"], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
