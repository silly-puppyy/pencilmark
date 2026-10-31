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
    "count_solutions",
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


SECTIONS = ("Parameters", "Returns", "Raises", "Examples", "Notes")


def _flow(text):
    """hard-wrapped docstring lines -> one flowing paragraph (markdown-escaped, docs links)"""
    return _links(" ".join(text.split()).replace("*", "\\*"))


def _render(doc):
    """a numpydoc docstring -> markdown: the summary paragraphs, then each section (Parameters / Raises as lists)"""
    lines = doc.split("\n")
    parts, cur, name = [], [], None
    for i, line in enumerate(lines):
        if line.strip() in SECTIONS and i + 1 < len(lines) and set(lines[i + 1].strip()) == {"-"}:
            parts.append((name, cur))
            name, cur = line.strip(), []
            continue
        if name and set(line.strip()) == {"-"} and cur == []:
            continue
        cur.append(line)
    parts.append((name, cur))
    out = []
    for name, body in parts:
        text = "\n".join(body).strip("\n")
        if not text:
            continue
        if name is None:
            out += [_flow(p) + "\n" for p in text.split("\n\n") if p.strip()]
            continue
        out.append(f"**{name}**\n")
        if name == "Examples":
            out.append(
                "```python\n" + "\n".join(x[4:] if x.startswith("    ") else x for x in body).strip() + "\n```\n"
            )
            continue
        items, item = [], None  # "name : type" lines start an item; indented lines describe it
        for line in body:
            if line and not line.startswith(" "):
                item = [line.strip(), []]
                items.append(item)
            elif item is not None and line.strip():
                item[1].append(line.strip())
        if not items:
            out.append(_flow(text) + "\n")
            continue
        for head, desc in items:
            nm, _, typ = head.partition(" : ")
            label = f"`{nm}`" + (f" ({typ})" if typ else "")
            out.append(f"- {label}: {_flow(' '.join(desc))}" if desc else f"- {label}")
        out.append("")
    return out


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
        if doc:
            L += _render(doc)
    (ROOT / "docs/api.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
