"""Write docs/library/python-api.md from the docstrings of pencilmark's public API (read from the source with ast, so the C++ engine
need not be built), grouped by purpose; tools/apidoc.py renders the entries.
  python tools/gen_api_md.py"""

import ast
from pathlib import Path

import apidoc

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {  # section -> public names, in reading order
    "Grading": ["rate", "rate_many", "describe"],
    "Solving": ["solve", "count_solutions"],
    "Generating": ["generate"],
    "Reading and writing": ["load", "validate", "fingerprint", "to_export", "dumps", "from_string", "to_string",
                            "from_ipuz", "to_ipuz"],
    "Errors": ["NotUnique", "NoSolution", "Undecided"],
}  # fmt: skip
PATH = "src/pencilmark/api.py"


def main():
    tree = ast.parse((ROOT / PATH).read_text(encoding="utf-8"))
    defs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    L = [
        "---",
        "title: Python API",
        "toc_max_heading_level: 2",
        "---",
        "",
        "# Python API",
        "",
        "Everything below is importable from `pencilmark` directly (`pencilmark.rate`, `pencilmark.to_export`, …). "
        "This page is generated from the docstrings (`tools/gen_api_md.py`).",
        "",
    ]
    L += apidoc.table(
        [(name, "class" if isinstance(defs[name], ast.ClassDef) else "def", name,
          apidoc.summary(ast.get_docstring(defs[name]) or "")) for names in GROUPS.values() for name in names], "../"
    )  # fmt: skip
    for group, names in GROUPS.items():
        L += [f"## {group}", ""]
        for name in names:
            n = defs[name]
            src = apidoc.source(PATH, n.lineno)
            if isinstance(n, ast.ClassDef):
                bases = ", ".join(ast.unparse(b) for b in n.bases)
                L.append(apidoc.heading(3, name, "class", name, f"({bases})" if bases else "", src=src))
            else:
                ret = ast.unparse(n.returns) if n.returns else ""
                L.append(apidoc.heading(3, name, "def", name, f"({ast.unparse(n.args)})", ret=ret, src=src))
            L += apidoc.docstring(ast.get_docstring(n) or "", "../")  # the page is in docs/library/
    (ROOT / "docs/library/python-api.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
