"""tools/benchmark.py: its statistics (no grading, so it is fast)."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import benchmark as BM  # noqa: E402


def test_spearman_with_ties():
    assert BM.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert BM.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert abs(BM.spearman([1, 2, 2, 3], [1, 2, 3, 4]) - 0.9486832980505138) < 1e-12  # scipy.stats.spearmanr


def test_report(tmp_path, capsys):
    rows = [{"source": "s", "group": g, "key": i, "target": math.log(i + 1), "target_kind": "log minutes",
             "difficulty": i, "time": i + 1, "band": "Easy", "secs": 0.1}
            for g in ("a", "b") for i in range(1, 21)]  # fmt: skip
    rows.append({"source": "s", "group": "a", "key": 99, "target": 1, "error": "NotUnique: more than one", "secs": 0.1})
    f = tmp_path / "grades.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    BM.report(f)
    out = capsys.readouterr().out
    assert "41 puzzles, 40 graded" in out and "NotUnique 1" in out
    assert "s                    40      2          1.000     1.000     0.00 / 0.00" in out
