"""Every self-contained command-line example in the docs (`$ echo '<puzzle>' | pencilmark ...` or `$ printf ...`) prints
what the page shows. The shown lines must appear in the real output in order; a "..." / "…" line on the page stands for
lines left out. A command ending in `2>&1` is compared with standard error too, durations ("0.005 s") as any duration.
Slow (about 10 s): marked `slow`, run with `pytest -m slow`.
"""

import re
import shlex
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
    return [re.sub(r"\d+\.\d+ s\b", "N s", re.sub(r"\s+", " ", x)).strip() for x in lines if x.strip()]


@pytest.mark.slow
@pytest.mark.parametrize("command,shown", examples())
def test_cli_example_output(command, shown):
    # no shell: Windows cmd would pass echo's quotes on, so the piped text is made here as a POSIX shell makes it
    feed, args = command.split("| pencilmark ", 1)
    merged = args.rstrip().endswith("2>&1")
    args = args.rstrip().removesuffix("2>&1")
    word, text = shlex.split(feed)
    text = text + "\n" if word == "echo" else text.encode().decode("unicode_escape")
    run = subprocess.run([sys.executable, "-m", "pencilmark", *shlex.split(args)], input=text, capture_output=True,
                         text=True, timeout=300)  # fmt: skip
    real = norm((run.stderr + run.stdout if merged else run.stdout).split("\n"))
    k = 0
    for want in norm(shown):
        if want in ("...", "…"):
            continue
        while k < len(real) and real[k] != want:
            k += 1
        assert k < len(real), f"{command!r}: the page shows {want!r}, not in the output:\n" + "\n".join(real)
        k += 1
