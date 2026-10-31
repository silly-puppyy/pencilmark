"""Everyday jobs in one place (works wherever Python does; no make needed). Run from the repository root:

python tools/tasks.py test        the quick suite (about 10 s)
python tools/tasks.py slow        the doc examples, run as written (about 20 s)
python tools/tasks.py golden      every output of the golden corpus identical (about a minute)
python tools/tasks.py check       all three: what a change must pass
python tools/tasks.py lint        ruff check and ruff format --check
python tools/tasks.py fixtures    rewrite the snapshot fixtures (only when a change is meant to alter them)
python tools/tasks.py docs        generate the API / techniques / parameters pages and swatches, build the site
python tools/tasks.py serve       build, then serve the site on http://localhost:3000/pencilmark/
python tools/tasks.py release VERSION   check that main is ready to release VERSION (docs/dev/RELEASE.md)
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
FIXTURES = ["test_line_matrix", "test_edge_matrix", "test_cell_matrix", "test_rule_matrix", "test_input_matrix"]
GENERATORS = ["gen_api_md", "gen_techniques_md", "gen_parameters_md", "gen_swatches"]
COPIES = [("README.md", "docs/index.md"), ("ARCHITECTURE.md", "docs/dev/ARCHITECTURE.md"),
          ("CONTRIBUTING.md", "docs/dev/CONTRIBUTING.md")]  # fmt: skip


def run(*cmd, cwd=ROOT):
    print("$", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(list(map(str, cmd)), cwd=cwd).returncode


def test():
    return run(PY, "-m", "pytest", "-q", "-n", "auto", "tests")


def slow():
    return run(PY, "-m", "pytest", "-q", "-n", "auto", "-m", "slow", "tests")


def golden():
    return run(PY, "tools/golden.py", "check")


def check():
    return test() or slow() or golden()


def lint():
    return run("ruff", "check", "src", "tests", "tools") or run("ruff", "format", "--check", "src", "tests", "tools")


def fixtures():
    return max(run(PY, f"tests/{t}.py", "--write") for t in FIXTURES)


def docs(build=True):
    for g in GENERATORS:
        if run(PY, f"tools/{g}.py"):
            return 1
    if shutil.which("doxygen"):  # the C++ engine reference (Doxyfile -> website/static/cpp/)
        run("doxygen")
    else:
        print("doxygen not found: the site is built without the C++ engine reference")
    for src, dst in COPIES:
        shutil.copyfile(ROOT / src, ROOT / dst)
    try:
        return run("npm", "run", "build", cwd=ROOT / "website") if build else 0
    finally:
        (ROOT / "docs/index.md").unlink(missing_ok=True)  # the README copy is for the build only


def serve():
    return docs() or run("npx", "--no-install", "docusaurus", "serve", "--no-open", cwd=ROOT / "website")


def release(version):
    """main is ready to release `version`: the numbers agree, the CHANGELOG has its section, the tree is clean, the
    checks pass. Prints what is wrong; changes nothing."""
    problems = []
    pyproject = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)
    init = re.search(r'__version__ = "([^"]+)"', (ROOT / "src/pencilmark/__init__.py").read_text()).group(1)
    for where, v in (("pyproject.toml", pyproject), ("src/pencilmark/__init__.py", init)):
        if v != version:
            problems.append(f"{where} says {v}, not {version}")
    log = (ROOT / "CHANGELOG.md").read_text()
    if not re.search(rf"^## {re.escape(version)} \(", log, re.M):
        problems.append(f'CHANGELOG.md has no "## {version} (date)" section (rename "## Unreleased")')
    if re.search(r"^## Unreleased\n\n- ", log, re.M):
        problems.append('CHANGELOG.md: "## Unreleased" still lists changes')
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        problems.append("the work tree has uncommitted changes")
    for p in problems:
        print("not ready:", p)
    if problems:
        return 1
    return check() or docs()


TASKS = {"test": test, "slow": slow, "golden": golden, "check": check, "lint": lint, "fixtures": fixtures,
         "docs": docs, "serve": serve}  # fmt: skip


def main(argv):
    if len(argv) == 2 and argv[0] == "release":
        return release(argv[1])
    if len(argv) != 1 or argv[0] not in TASKS:
        print(__doc__)
        return 2
    return TASKS[argv[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
