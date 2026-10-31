"""Write the internal Python reference (docs/dev/reference/*.md) from the package's docstrings, read with ast (the engine
need not be built): one page per area, each module's docstring, then its public functions and classes.
  python tools/gen_reference_md.py"""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "pencilmark"
OUT = ROOT / "docs" / "dev" / "reference"
# page slug -> (title, description, modules in reading order)
PAGES = {
    "card": (
        "The card",
        "How a card is computed: the band route, the technique list, difficulty, time and the publishing checks.",
        ["export", "band_path", "card", "card_score", "scoring", "grader_model", "metrics", "publish_flags", "se",
         "usage"],
    ),
    "formats": (
        "Formats",
        "Reading, checking and writing puzzles and generator requests; the rule families and the variant names.",
        ["inputs", "exchange/__init__", "exchange/common", "exchange/board", "exchange/validate", "exchange/read",
         "exchange/write", "exchange/canonical", "rules/__init__", "rules/line", "rules/edge", "rules/cell",
         "puzzle_json", "interop", "spec_format", "variants"],
    ),
    "engine": (
        "The engine interface",
        "The Python side of the C++ engine: the puzzle model, the calls into the engine, its move records, the "
        "technique registry.",
        ["model", "cbackend", "engine_records", "solver", "registry", "cpsat_verify", "_data"],
    ),
    "explain": (
        "Explanations",
        "The step explanations: one handler per technique, on a replayed grid.",
        ["explain/__init__", "explain/base", "explain/dispatch", "explain/grid", "explain/catalog", "explain/singles",
         "explain/combos", "explain/notes", "explain/chains", "explain/trial", "explain/records"],
    ),
    "generator": (
        "The generator",
        "One puzzle for a sudoku-spec request.",
        ["gen/__init__", "gen/api", "gen/board", "gen/elements", "gen/checks", "gen/search"],
    ),
    "sources": (
        "Puzzle sources",
        "Links and payloads from SudokuPad, f-puzzles, Penpa and Logic Masters, read into puzzles.",
        ["sources/__init__", "sources/_common", "sources/sudokupad", "sources/_sp_translate", "sources/fpuzzles",
         "sources/_fpuz_translate", "sources/penpa", "sources/lmd"],
    ),
    "cli": ("The command line", "`python -m pencilmark` and the `pencilmark` command.", ["__main__"]),
}  # fmt: skip


def _esc(text):
    """MDX-safe text: braces and angle brackets would be read as JSX"""
    return text.replace("{", "\\{").replace("}", "\\}").replace("<", "&lt;")


def _flow(doc):
    """a docstring as markdown paragraphs: hard-wrapped lines joined, indented blocks kept as code"""
    out = []
    for para in re.split(r"\n\s*\n", doc.strip()):
        lines = para.split("\n")
        if len(lines) > 1 and all(line.startswith("    ") or not line.strip() for line in lines[1:]):
            out.append(_esc(lines[0].strip()))
            out.append(
                "```\n" + "\n".join(line[4:] if line.startswith("    ") else line for line in lines[1:]) + "\n```"
            )
        elif all(line.startswith("  ") for line in lines if line.strip()) or (
            sum(bool(re.match(r"^\s*\S+\s{3,}\S", line)) for line in lines) >= 2
        ):  # an indented block, or terms aligned in columns: keep the layout
            out.append("```\n" + "\n".join(lines) + "\n```")
        else:
            out.append(_esc(" ".join(line.strip() for line in lines)))
    return out


def _signature(node):
    args = ast.unparse(node.args)
    return f"{node.name}({args})" if len(node.name) + len(args) <= 100 else f"{node.name}(...)"


def _entry(node, prefix="", level=3):
    """markdown for one public function or class (and a class's public methods)"""
    out = []
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        out.append(f"{'#' * level} `{prefix}{node.name}`\n\n```python\nclass {node.name}({bases})\n```")
    else:
        out.append(f"{'#' * level} `{prefix}{node.name}`\n\n```python\n{_signature(node)}\n```")
    doc = ast.get_docstring(node)
    out += _flow(doc) if doc else ["*No docstring.*"]
    if isinstance(node, ast.ClassDef):
        for m in node.body:
            if isinstance(m, ast.FunctionDef) and not m.name.startswith("_"):
                d = ast.get_docstring(m)
                out.append(f"- `{_signature(m)}`" + (f": {_esc(' '.join(d.split()))}" if d else ""))
    return out


def page(slug, title, description, modules):
    L = [
        "---",
        f"title: {json.dumps(title)}",
        f"description: {json.dumps(description)}",
        "---",
        "",
        f"# {title}",
        "",
        f"{description} Generated from the docstrings (`tools/gen_reference_md.py`); public names only.",
        "",
    ]
    for mod in modules:
        f = SRC / f"{mod}.py"
        tree = ast.parse(f.read_text(encoding="utf-8"))
        name = "pencilmark." + mod.replace("/", ".").removesuffix(".__init__").removesuffix("__init__")
        L += [f"## `{name.rstrip('.')}`", "", f"`src/pencilmark/{mod}.py`", ""]
        doc = ast.get_docstring(tree)
        L += [p + "\n" for p in _flow(doc)] if doc else ["*No module docstring.*\n"]
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                L += [p + "\n" for p in _entry(node)]
    return "\n".join(L)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, (title, description, modules) in PAGES.items():
        (OUT / f"{slug}.md").write_text(page(slug, title, description, modules), encoding="utf-8")
    covered = {m for _, _, ms in PAGES.values() for m in ms}
    left = sorted(
        str(p.relative_to(SRC).with_suffix(""))
        for p in SRC.rglob("*.py")
        if str(p.relative_to(SRC).with_suffix("")) not in covered | {"api", "__init__"}
    )
    if left:
        raise SystemExit(f"modules not on any reference page: {left}")


if __name__ == "__main__":
    main()
