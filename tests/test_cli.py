"""The command line gives the same cards as the Python API."""

import json
import subprocess
import sys

from conftest import CLASSIC

import pencilmark


def run(args, stdin):
    r = subprocess.run(
        [sys.executable, "-m", "pencilmark", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_cli_json_equals_api(variants):
    puzzles = [CLASSIC] + [json.dumps(v["puzzle"]) for v in variants[:3]]
    lines = run(["rate", "-", "--json"], "\n".join(puzzles) + "\n")
    assert len(lines) == len(puzzles)
    for k, (line, pz) in enumerate(zip(lines, [CLASSIC] + [v["puzzle"] for v in variants[:3]]), 1):
        card = json.loads(line)
        assert card.pop("line") == k
        assert card == pencilmark.rate(pz)


def test_cli_default_format_and_solve():
    out = run(["rate", "-"], CLASSIC + "\n")
    assert out == ["Hard\t5.8\t10.7\tX-Wing"]
    sol = run(["solve", "-"], CLASSIC + "\n" + "." * 81 + "\n" + "123\n{bad\n")  # bad lines are reported, not fatal
    assert sol[0] == "".join(map(str, pencilmark.solve(CLASSIC))) and sol[1] == "not unique"
    assert sol[2].startswith("error\t3\tFormatError: a plain string has 16, 36, 64, 81") and sol[2].endswith("has 3")
    assert sol[3].startswith("error\t4\tFormatError: not JSON")


def test_cli_parallel_same_output(variants):
    puzzles = "\n".join([CLASSIC] + [json.dumps(v["puzzle"]) for v in variants[:3]]) + "\n"
    assert run(["rate", "-", "-j", "2"], puzzles) == run(["rate", "-"], puzzles)


def test_cli_export_keeps_meta():
    exp = pencilmark.write.document(CLASSIC, solution=True, describe=True)
    exp["meta"].update(title="T", author="A")
    out = json.loads(run(["convert", "-"], json.dumps(exp) + "\n")[0])
    assert out["meta"]["title"] == "T" and out["meta"]["author"] == "A"
    assert run(["fingerprint", "-"], json.dumps(exp) + "\n") == [pencilmark.fingerprint(exp)]


def test_cli_parallel_spawn():
    """-j with the spawn start method (Windows, macOS) run as `python -m pencilmark`: the workers must not need
    pencilmark's __main__, which spawn does not re-import"""
    code = (
        "import sys, runpy, multiprocessing as mp\n"
        "import pencilmark.api as A\n"
        "A._mp_context = lambda: mp.get_context('spawn')\n"
        "sys.argv = ['pencilmark', 'rate', '-', '-j', '2']\n"
        "runpy.run_module('pencilmark', run_name='__main__', alter_sys=True)\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        input=CLASSIC + "\n" + CLASSIC + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert r.returncode == 0 and r.stdout.splitlines() == ["Hard\t5.8\t10.7\tX-Wing"] * 2, r.stderr[-2000:]


def test_cli_reads_whole_json_file(tmp_path, variants):
    f = tmp_path / "puzzle.json"
    f.write_text(json.dumps(variants[0]["puzzle"], indent=1))  # pretty-printed: one puzzle over many lines
    card = json.loads(run(["rate", str(f), "--json", "--fields", "band"], "")[0])
    assert card["band"] == pencilmark.rate(variants[0]["puzzle"], fields=["band"])["band"]


def test_cli_reads_ipuz(tmp_path):
    f = tmp_path / "classic.ipuz"
    f.write_text(json.dumps(pencilmark.write.ipuz(CLASSIC)))
    assert run(["solve", str(f)], "") == ["".join(map(str, pencilmark.solve(CLASSIC)))]


def test_cli_count():
    """count: exact counts, ">=N" at the limit, 0 for a grid that breaks the rules"""
    lines = [CLASSIC, "." * 81, "11" + "." * 79]
    assert run(["count", "-", "--limit", "50"], "\n".join(lines) + "\n") == ["1", ">=50", "0"]
    assert pencilmark.count_solutions(CLASSIC) == {"count": 1, "exact": True}


def test_cli_generate():
    spec = {
        "format": "pencilmark-spec",
        "format_version": 1,
        "board": {"rows": 4, "cols": 4},
        "digits": 4,
        "rules": [{"type": "box_grid", "box": [2, 2], "count": [2, 2]}],
        "limits": {"seed": 1},
    }
    out = json.loads(run(["generate", "-", "--result"], json.dumps(spec))[0])
    assert out["puzzle"]["format"] == "pencilmark-puzzle" and out["info"]["seed"] == 1


def test_cli_errors_are_one_line(tmp_path):
    """a missing file, a spec that is not JSON: an error line and exit status 1, never a traceback"""
    bad = tmp_path / "spec.json"
    bad.write_text('{"format": "pencilmark-spec"', encoding="utf-8")
    for args in (["rate", str(tmp_path / "missing.txt")], ["fingerprint", str(tmp_path / "missing.txt")],
                 ["generate", str(bad)]):  # fmt: skip
        r = subprocess.run([sys.executable, "-m", "pencilmark", *args], capture_output=True, text=True)
        assert r.returncode == 1 and "Traceback" not in r.stderr, (args, r.stderr)
        assert r.stderr.startswith(f"pencilmark {args[0]}: "), r.stderr


def test_cli_log():
    """--log debug writes the stage timings to standard error and leaves the output as it was; without it, nothing"""
    r = subprocess.run(
        [sys.executable, "-m", "pencilmark", "rate", "-", "--log", "debug"],
        input=CLASSIC + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == run(["rate", "-"], CLASSIC + "\n")
    assert "pencilmark.cpsat_verify: uniqueness: 1 solution(s)" in r.stderr
    assert "pencilmark.export: band route:" in r.stderr
