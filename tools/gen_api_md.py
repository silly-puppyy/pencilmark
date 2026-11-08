"""Write docs/library/python-api.md from the docstrings of pencilmark's public API (read from the source with ast, so the C++ engine
need not be built), grouped by purpose; tools/apidoc.py renders the entries.
  python tools/gen_api_md.py"""

import ast
from pathlib import Path

import apidoc

ROOT = Path(__file__).resolve().parents[1]
API, ERR, RD, WR = (
    "src/pencilmark/api.py",
    "src/pencilmark/errors.py",
    "src/pencilmark/read.py",
    "src/pencilmark/write.py",
)
GROUPS = {  # section -> (file, public name, how it is called), in reading order
    "Grading": [(API, "rate", "rate"), (API, "rate_many", "rate_many"), (API, "describe", "describe")],
    "Solving": [(API, "solve", "solve"), (API, "count_solutions", "count_solutions")],
    "Generating": [(API, "generate", "generate")],
    "Reading (pencilmark.read)": [(RD, n, f"read.{n}") for n in ("auto", "detect", "pencilmark", "plain", "grid",
                                  "pencil_marks", "candidates", "hodoku", "sudokuwiki", "ipuz", "link")],
    "Writing (pencilmark.write)": [(WR, n, f"write.{n}") for n in ("pencilmark", "document", "plain", "grid",
                                   "sudokuwiki", "ipuz")],
    "Checking": [(API, "validate", "validate"), (API, "fingerprint", "fingerprint")],
    "Drawing": [(API, "draw", "draw")],
    "Errors": [(ERR, n, n) for n in ("Error", "FormatError", "NotSupportedError", "FetchError", "ReadingMismatch",
                                     "NotUnique", "NoSolution", "Undecided", "GenerationFailed")],
}  # fmt: skip


def main():
    trees = {}
    for path in {f for names in GROUPS.values() for f, _, _ in names}:
        trees[path] = {
            n.name: n
            for n in ast.parse((ROOT / path).read_text(encoding="utf-8")).body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))
        }
    entries = [(f, trees[f][n], shown) for names in GROUPS.values() for f, n, shown in names]
    anchor = lambda shown: shown.replace(".", "-")  # noqa: E731
    L = [
        "---",
        "title: Python API",
        'description: "Every public function of the pencilmark package: rate, solve, generate, the readers and '
        'writers of every format, the errors."',
        "toc_max_heading_level: 2",
        "---",
        "",
        "# Python API",
        "",
        "`rate`, `solve` and the rest take a puzzle in any format pencilmark reads (detected; `format=` names it); "
        "`pencilmark.read.<format>` reads one format strictly, `pencilmark.write.<format>` writes one. "
        "This page is generated from the docstrings (`tools/gen_api_md.py`).",
        "",
    ]
    L += apidoc.table(
        [(anchor(shown), "class" if isinstance(n, ast.ClassDef) else "def", shown,
          apidoc.summary(ast.get_docstring(n) or "")) for _, n, shown in entries], "../"
    )  # fmt: skip
    for group, names in GROUPS.items():
        L += [f"## {group}", ""]
        for path, name, shown in names:
            n = trees[path][name]
            src = apidoc.source(path, n.lineno)
            if isinstance(n, ast.ClassDef):
                bases = ", ".join(ast.unparse(b) for b in n.bases)
                L.append(apidoc.heading(3, anchor(shown), "class", shown, f"({bases})" if bases else "", src=src))
            else:
                ret = ast.unparse(n.returns) if n.returns else ""
                L.append(apidoc.heading(3, anchor(shown), "def", shown, f"({ast.unparse(n.args)})", ret=ret, src=src))
            L += apidoc.docstring(ast.get_docstring(n) or "", "../")  # the page is in docs/library/
    (ROOT / "docs/library/python-api.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
