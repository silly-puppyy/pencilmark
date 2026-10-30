"""The command line gives the same cards as the Python API."""
import json
import subprocess
import sys

import pencilmark
from conftest import CLASSIC


def run(args, stdin):
    r = subprocess.run([sys.executable, "-m", "pencilmark", *args], input=stdin, capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
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
    assert out == ["Hard\t5.9\t10.7\tX-Wing"]
    sol = run(["solve", "-"], CLASSIC + "\n" + "." * 81 + "\n")
    assert sol[0] == "".join(map(str, pencilmark.solve(CLASSIC))) and sol[1] == "not unique"


def test_cli_parallel_same_output(variants):
    puzzles = "\n".join([CLASSIC] + [json.dumps(v["puzzle"]) for v in variants[:3]]) + "\n"
    assert run(["rate", "-", "-j", "2"], puzzles) == run(["rate", "-"], puzzles)


def test_cli_json_keeps_meta():
    exp = pencilmark.to_export(CLASSIC, title="T", author="A")
    out = json.loads(run(["json", "-"], json.dumps(exp) + "\n")[0])
    assert out["meta"]["title"] == "T" and out["meta"]["author"] == "A" and out["hash"]


def test_cli_parallel_spawn():
    """-j with the spawn start method (Windows, macOS) run as `python -m pencilmark`: the workers must not need
    pencilmark's __main__, which spawn does not re-import"""
    code = ("import sys, runpy, multiprocessing as mp\n"
            "import pencilmark.api as A\n"
            "A._mp_context = lambda: mp.get_context('spawn')\n"
            "sys.argv = ['pencilmark', 'rate', '-', '-j', '2']\n"
            "runpy.run_module('pencilmark', run_name='__main__', alter_sys=True)\n")
    r = subprocess.run([sys.executable, "-c", code], input=CLASSIC + "\n" + CLASSIC + "\n", capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert r.returncode == 0 and r.stdout.splitlines() == ["Hard\t5.9\t10.7\tX-Wing"] * 2, r.stderr[-2000:]
