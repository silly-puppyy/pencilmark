"""Write the internal Python reference (docs/reference/*.md) from the package's docstrings, read with ast (the engine
need not be built): one page per area; per module its docstring, a summary table, then each public function and class
(tools/apidoc.py renders them).
  python tools/gen_reference_md.py"""

import ast
import json
from pathlib import Path

import apidoc

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "pencilmark"
OUT = ROOT / "docs" / "reference"
BASE = "../"  # from a reference page to docs/
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
        "Reading, checking, writing and drawing puzzles and generator requests; the rule families and the variant names.",
        ["read", "write", "errors", "exchange/__init__", "exchange/common", "exchange/board", "exchange/validate", "exchange/read",
         "exchange/write", "exchange/canonical", "rules/__init__", "rules/line", "rules/edge", "rules/cell", "rules/custom", "rules/values", "rules/region", "rules/shading",
         "puzzle_json", "interop", "spec_format", "variants", "render"],
    ),
    "engine": (
        "The engine interface",
        "The Python side of the C++ engine: the puzzle model, the calls into the engine, its move records, the "
        "technique registry.",
        ["model", "layers", "cbackend", "engine_records", "solver", "registry", "cpsat_verify", "rule_lemmas", "_data"],
    ),
    "explain": (
        "Explanations",
        "The step explanations: one handler per technique, on a replayed grid.",
        ["explain/__init__", "explain/base", "explain/dispatch", "explain/grid", "explain/catalog", "explain/singles",
         "explain/combos", "explain/notes", "explain/chains", "explain/trial", "explain/records", "explain/facts",
         "explain/clue_facts"],
    ),
    "fog": (
        "Fog of war",
        "The experimental route a solver can take under the fog (what is lit, reveals, no guessing); not yet used by rate.",
        ["fog"],
    ),
    "generator": (
        "The generator",
        "One puzzle for a pencilmark-spec request.",
        ["gen/__init__", "gen/api", "gen/board", "gen/elements", "gen/checks", "gen/search"],
    ),
    "sources": (
        "Puzzle sources",
        "Links and payloads from SudokuPad, f-puzzles, Penpa, Logic Masters and sudoku.coach, read into puzzles.",
        ["sources/__init__", "sources/_common", "sources/sudokupad", "sources/_sp_translate", "sources/_sp_style",
         "sources/fpuzzles",
         "sources/_fpuz_translate", "sources/_fpuz_style", "sources/penpa", "sources/lmd", "sources/coach"],
    ),
    "cli": ("The command line", "`python -m pencilmark` and the `pencilmark` command.", ["__main__"]),
}  # fmt: skip


def _signature(node):
    """(args, return annotation) of a function"""
    return f"({ast.unparse(node.args)})", ast.unparse(node.returns) if node.returns else ""


def _anchor(qualified):
    """a heading id: dunder names lose their underscores (Markdown would read them as bold)"""
    return qualified.replace("__", "")


def _public(body):
    return [n for n in body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")]


def _entry(node, path, qual, level=3):
    """one public function or class (a class with its public methods, nested)"""
    doc = ast.get_docstring(node) or ""
    src, anchor = apidoc.source(path, node.lineno), _anchor(qual + node.name)
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        out = [apidoc.heading(level, anchor, "class", node.name, f"({bases})" if bases else "", src=src)]
    else:
        args, ret = _signature(node)
        out = [apidoc.heading(level, anchor, "def", node.name, args, ret=ret, src=src)]
    out += apidoc.docstring(doc, BASE) if doc else ["*No docstring.*\n"]
    methods = _public(node.body) if isinstance(node, ast.ClassDef) else []
    for m in methods:
        out += _entry(m, path, f"{qual}{node.name}.", level + 1)
    return out


def page(title, description, modules):
    L = [
        "---",
        f"title: {json.dumps(title)}",
        f"description: {json.dumps(description)}",
        "toc_max_heading_level: 2",
        "---",
        "",
        f"# {title}",
        "",
        f"{description} Generated from the docstrings by `tools/gen_reference_md.py`; public names only.",
        "",
    ]
    for mod in modules:
        path = f"src/pencilmark/{mod}.py"
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        name = "pencilmark." + mod.replace("/", ".").removesuffix(".__init__").removesuffix("__init__")
        name = name.rstrip(".")
        L += [f"## {name} {{#{_anchor(name)}}}", "", apidoc.file_link(path)]
        doc = ast.get_docstring(tree)
        L += apidoc.flow(doc, BASE) if doc else []
        nodes = _public(tree.body)
        L += apidoc.table(
            [(_anchor(f"{name}.{n.name}"), "class" if isinstance(n, ast.ClassDef) else "def", n.name,
              apidoc.summary(ast.get_docstring(n) or "")) for n in nodes], BASE
        )  # fmt: skip
        for n in nodes:
            L += _entry(n, path, name + ".")
    return "\n".join(L)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, (title, description, modules) in PAGES.items():
        (OUT / f"{slug}.md").write_text(page(title, description, modules), encoding="utf-8")
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
