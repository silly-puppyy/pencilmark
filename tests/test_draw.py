"""pencilmark.draw: SVG of any readable input, the trace position layers, and the draw command."""

import json
from pathlib import Path

import pencilmark
from pencilmark.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
CLASSIC = "4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......"
MINI = ROOT / "docs/examples/mini-thermo-kropki.json"


def test_draw_reads_any_input():
    a = pencilmark.draw(CLASSIC)
    b = pencilmark.draw(pencilmark.read.plain(CLASSIC))
    assert a == b and a.startswith("<svg") and a.endswith("</svg>")
    assert pencilmark.draw(MINI, dark=True) != pencilmark.draw(MINI)
    width = lambda s: float(s.split('width="', 1)[1].split('"', 1)[0])
    assert width(pencilmark.draw(CLASSIC, cell=24)) < width(a) / 1.9  # 48-pixel cells by default


def test_draw_trace_position():
    card = pencilmark.rate(CLASSIC, fields=["band", "trace"])
    plain = pencilmark.draw(CLASSIC)
    later = pencilmark.draw(CLASSIC, card=card, position=len(card["trace"]) - 1)
    assert later != plain and later.count("<text") > plain.count("<text")  # the placed digits are drawn


def test_draw_command(tmp_path, capsys):
    out = tmp_path / "mini.svg"
    main(["draw", str(MINI), "-o", str(out), "--dark"])
    assert out.read_text(encoding="utf-8") == pencilmark.draw(json.loads(MINI.read_text(encoding="utf-8")), dark=True)
    main(["draw", str(MINI)])
    assert capsys.readouterr().out.startswith("<svg")
