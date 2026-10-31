"""Write docs/api.md from the docstrings of pencilmark's public API (read from the source with ast, so the C++ engine
need not be built).
  python tools/gen_api_md.py"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = [
    "rate",
    "rate_many",
    "solve",
    "generate",
    "load",
    "to_export",
    "dumps",
    "fingerprint",
    "validate",
    "describe",
    "from_string",
    "to_string",
    "from_ipuz",
    "to_ipuz",
    "NotUnique",
    "NoSolution",
    "Undecided",
]


def signature(node):
    seg = ast.unparse(node.args)
    if len(node.name) + len(seg) <= 80:
        return f"{node.name}({seg})"
    return f"{node.name}(\n    " + ",\n    ".join(a.strip() for a in seg.split(", ")) + ",\n)"


PAGE_TITLES = {"FORMAT": "Puzzle format", "GRADE": "Grade card", "SPEC": "Generator spec", "INTEROP": "Other formats"}


def _links(text):
    """'docs/FORMAT.md' in a docstring -> a link to that page"""
    return re.sub(r"docs/([A-Z]+)\.md", lambda m: f"[{PAGE_TITLES.get(m.group(1), m.group(1))}]({m.group(1)}.md)", text)


def main():
    src = (ROOT / "src/pencilmark/api.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    L = [
        "# Python API",
        "",
        "Everything below is importable from `pencilmark` directly (`pencilmark.rate`, `pencilmark.to_export`, …). "
        "This page is generated from the docstrings (`tools/gen_api_md.py`).",
        "",
    ]
    for name in NAMES:
        n = defs[name]
        doc = ast.get_docstring(n) or ""
        if isinstance(n, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in n.bases)
            L += [f"## `{name}`", "", f"```python\nclass {name}({bases})\n```", ""]
        else:
            L += [f"## `{name}`", "", f"```python\n{signature(n)}\n```", ""]
        if doc:  # docstring lines are hard-wrapped: join them into flowing paragraphs
            paras = [" ".join(x.split()) for x in doc.split("\n\n")]
            L += [_links(p.replace("*", "\\*")) + "\n" for p in paras if p]
    (ROOT / "docs/api.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
