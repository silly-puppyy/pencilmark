"""Everyday jobs in one place (works wherever Python does; no make needed). Run from the repository root:

python tools/tasks.py test        the quick suite (about 10 s)
python tools/tasks.py slow        the doc examples, run as written (about 20 s)
python tools/tasks.py golden      every output of the golden corpus identical (about a minute)
python tools/tasks.py check       all three: what a change must pass
python tools/tasks.py lint        ruff check, ruff format --check and codespell
python tools/tasks.py fixtures    rewrite the snapshot fixtures (only when a change is meant to alter them)
python tools/tasks.py prepare     generate the pages, swatches and copies the site reads (the docs workflow runs it)
python tools/tasks.py docs        prepare, then build the site
python tools/tasks.py serve       build, then serve the site on http://localhost:3000/pencilmark/
python tools/tasks.py release VERSION   check that main is ready to release VERSION (docs/dev/release.md)
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
FIXTURES = ["test_line_matrix", "test_edge_matrix", "test_cell_matrix", "test_rule_matrix", "test_input_matrix"]
GENERATORS = ["gen_api_md", "gen_reference_md", "gen_cpp_reference", "gen_techniques_md", "gen_parameters_md", "gen_page_versions",
              "gen_palette_md", "gen_swatches"]  # fmt: skip
COPIES = [("README.md", "docs/index.md", None),  # the homepage: its link previews show the wide banner (image below)
          ("ARCHITECTURE.md", "docs/guides/development/architecture.md", "How a card is computed in the code, and which file holds each part."),
          ("CONTRIBUTING.md", "docs/dev/contributing.md", "How to set up, prove a change, and the style pencilmark's code and docs follow.")]  # fmt: skip


def run(*cmd, cwd=ROOT):
    print("$", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(list(map(str, cmd)), cwd=cwd).returncode


def test():
    return run(PY, "-m", "pytest", "-q", "-n", "auto", "tests")


def slow():
    return run(PY, "-m", "pytest", "-q", "-n", "auto", "-m", "slow", "tests")


def golden():
    return run(PY, "tools/golden.py", "check")


def smoke():  # the wheels workflow's test of every built wheel (tests/smoke.py)
    return run(PY, "tests/smoke.py")


def check():
    return test() or slow() or golden()


def lint():
    return (run("ruff", "check", "src", "tests", "tools") or run("ruff", "format", "--check", "src", "tests", "tools")
            or run("codespell"))  # fmt: skip


def fixtures():
    return max(run(PY, f"tests/{t}.py", "--write") for t in FIXTURES)


def prepare():
    """the generated pages, the swatches and the copies of the root documents: everything the site build reads"""
    for g in GENERATORS:
        if run(PY, f"tools/{g}.py"):
            return 1
    for src, dst, description in COPIES:  # the copies get a description for search results (the sources have none)
        text = re.sub(r"\n<picture>.*?</picture>\n", "", (ROOT / src).read_text(encoding="utf-8"), flags=re.S)  # banner
        meta = f'description: "{description}"\n' if description else "image: img/social-dark.png\n"  # homepage
        head = f"---\n{meta}---\n\n"
        (ROOT / dst).write_text(head + text, encoding="utf-8")
    shutil.copyfile(ROOT / "src/pencilmark/data/palette.json", ROOT / "docs/palette.json")  # the docs link it
    return 0


def docs(build=True):
    if prepare():
        return 1
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
    if re.search(
        r"^## Unreleased\n\s*\n(?!## )\S", log, re.M
    ):  # anything (bullets, ### headings) before the next release
        problems.append('CHANGELOG.md: "## Unreleased" still lists changes')
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        problems.append("the work tree has uncommitted changes")
    for p in problems:
        print("not ready:", p)
    if problems:
        return 1
    return check() or smoke() or lint() or docs()


TASKS = {"test": test, "slow": slow, "golden": golden, "smoke": smoke, "check": check, "lint": lint, "fixtures": fixtures,
         "docs": docs, "serve": serve, "prepare": prepare}  # fmt: skip


def main(argv):
    if len(argv) == 2 and argv[0] == "release":
        return release(argv[1])
    if len(argv) != 1 or argv[0] not in TASKS:
        print(__doc__)
        return 2
    return TASKS[argv[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
