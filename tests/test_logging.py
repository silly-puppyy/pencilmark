"""The "pencilmark" logger: silent by default, stage timings and generator attempts when switched on."""

import logging

from conftest import CLASSIC

import pencilmark


def test_silent_by_default(capsys):
    assert any(isinstance(h, logging.NullHandler) for h in logging.getLogger("pencilmark").handlers)
    pencilmark.rate(CLASSIC)
    assert capsys.readouterr().err == ""


def test_rate_logs_stages(caplog):
    with caplog.at_level(logging.DEBUG, logger="pencilmark"):
        pencilmark.rate(CLASSIC, max_seconds=60)
    got = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("uniqueness: 1 solution(s)") for m in got)
    assert any(m.startswith("band route:") for m in got)
    assert any(m.startswith("graded in") for m in got)


def test_time_limit_logged(caplog):
    with caplog.at_level(logging.INFO, logger="pencilmark"):
        card = pencilmark.rate(CLASSIC, max_seconds=0.001)
    if card["band"] == "Unknown":  # a fast machine may finish even so
        assert any("time limit reached" in r.getMessage() for r in caplog.records)


def test_generator_logs(caplog):
    spec = {
        "format": "pencilmark-spec",
        "format_version": 1,
        "board": {"rows": 4, "cols": 4},
        "digits": 4,
        "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}],
        "where": {"band": "Very Easy"},
        "limits": {"seed": 1, "seconds": 30},
    }
    with caplog.at_level(logging.INFO, logger="pencilmark.gen"):
        pencilmark.generate(spec)
    assert any(r.getMessage().startswith("found: Very Easy") for r in caplog.records)


def test_trace_follows_the_route():
    """pencilmark.log("trace"): every route step and every technique-list test, each line with its ms clock; log(None)
    switches it off (user 2026-11-08: time by the logs, see what happens step by step)"""
    import io
    import re

    buf = io.StringIO()
    pencilmark.log("trace", stream=buf)
    try:
        card = pencilmark.rate(CLASSIC, fields=["steps", "contains"])
    finally:
        pencilmark.log(None)
    lines = buf.getvalue().splitlines()
    assert all(re.match(r"\s*\d+ ms  pencilmark", x) for x in lines)
    steps = [x for x in lines if "pencilmark.export: step " in x]
    assert len(steps) == len(card["steps"]) and "Hidden Single" in steps[0]
    assert any("technique list: without XWG needed" in x for x in lines)
    pencilmark.rate(CLASSIC)
    assert buf.getvalue().splitlines() == lines  # switched off: nothing more
