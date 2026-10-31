"""Every self-contained command-line example in the docs (`$ echo '<puzzle>' | pencilmark ...` or `$ printf ...`) prints
what the page shows. The shown lines must appear in the real output in order; a "..." / "…" line on the page stands for
lines left out. Slow (about 10 s): marked `slow`, run with `pytest -m slow`.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "README.md"] + sorted(p for p in (ROOT / "docs").rglob("*.md*") if "reference" not in p.parts)


def examples():
    out = []
    for page in PAGES:
        for block in re.findall(r"```[a-z]*\n(.*?)```", page.read_text(encoding="utf-8"), re.S):
            lines = block.split("\n")
            for i, line in enumerate(lines):
                if not re.match(r"^\$ (echo|printf) .*\| pencilmark ", line):
                    continue
                shown = []
                for nxt in lines[i + 1 :]:
                    if nxt.startswith("$ ") or not nxt.strip() or re.match(r"^(pencilmark|python) ", nxt):
                        break
                    shown.append(nxt)
                out.append(pytest.param(line[2:], shown, id=f"{page.stem}:{i}"))
    return out


def norm(lines):
    return [re.sub(r"\s+", " ", x).strip() for x in lines if x.strip()]


@pytest.mark.slow
@pytest.mark.parametrize("command,shown", examples())
def test_cli_example_output(command, shown):
    cmd = command.replace("| pencilmark ", f"| {sys.executable} -m pencilmark ")
    real = norm(subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300).stdout.split("\n"))
    k = 0
    for want in norm(shown):
        if want in ("...", "…"):
            continue
        while k < len(real) and real[k] != want:
            k += 1
        assert k < len(real), f"{command!r}: the page shows {want!r}, not in the output:\n" + "\n".join(real)
        k += 1
