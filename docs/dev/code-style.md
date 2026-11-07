---
description: "Rules for pencilmark's Python and C++ code, each with its source."
---

# Code style

Rules for pencilmark's Python and C++. Each names its source. Docs have their own page: [writing style](writing-style.md).

## Where code goes

1. **One fact, one place.** A technique's code, name, band and order, or a rule family's keywords, live in one registry
   that everything else reads. A second copy is a bug waiting to happen.
2. **Solver logic in C++, interface in Python.** Python parses, formats, explains and orchestrates; anything that
   searches a grid belongs in the engine.
3. **One module, one job, named after it.** No `extra`, `misc` or `utils`. I/O functions only do I/O; logic takes and
   returns plain data ([Scientific Python: design](https://learn.scientific-python.org/development/principles/design/)).
4. **Prefer functions over classes**; group values in a dataclass when they travel together
   ([Scientific Python: design](https://learn.scientific-python.org/development/principles/design/)).
5. **No hidden state.** Results come back as return values, never through module globals; a cache is private, keyed
   on its inputs and documented ([Google Python: global state](https://google.github.io/styleguide/pyguide.html)).
6. **src layout; tests run against the installed package**
   ([Packaging guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)).

## Names

7. **Python follows PEP 8**: `lower_with_under` modules and functions, `CapWords` classes, `UPPER_CASE` constants, one
   leading underscore for private names ([PEP 8](https://peps.python.org/pep-0008/#naming-conventions)).
8. **C++ follows the engine's existing convention**: `CamelCase` types, `snake_case` functions and variables,
   `UPPER_CASE` enum values and constants.
9. **Descriptive over short.** Abbreviations only from the glossary (`r1c1`, chip codes such as `XWG`, `D` for the
   digit count) ([Google Python: naming](https://google.github.io/styleguide/pyguide.html)).

## Functions

10. **Small and focused**: past about 40 lines, look for a split that keeps the structure clear
    ([Google Python](https://google.github.io/styleguide/pyguide.html)).
11. **Same kind of return value for every input**; options are keyword-only (after `*`); no `**kwargs` that hide what
    a function accepts ([Scientific Python: design](https://learn.scientific-python.org/development/principles/design/)).
12. **Type hints on the public API**, `X | None` rather than `Optional[X]`
    ([Google Python](https://google.github.io/styleguide/pyguide.html)).
13. **One reader and one writer per format, grouped in a namespace** (`pencilmark.read.sudokuwiki`,
    `pencilmark.write.ipuz`); entry points take any format and detect it, with an argument that names it instead
    (`rate(x, format="sudokuwiki")`), as image, mesh and structure libraries do
    ([Pillow](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open) `Image.open(formats=)`,
    [ASE](https://wiki.fysik.dtu.dk/ase/ase/io/io.html) `ase.io.read(format=)`,
    [meshio](https://github.com/nschloe/meshio) `meshio.read(file_format=)`); a reader reads only its own format and
    raises otherwise ([PEP 20](https://peps.python.org/pep-0020/): "Namespaces are one honking great idea").

## Errors

14. **The library raises; it never prints.** The CLI catches and reports
    ([Scientific Python: design](https://learn.scientific-python.org/development/principles/design/)).
15. **Messages say what was wrong, with which value, and how to fix it**: `givens has 3 entries; a 9x9 puzzle needs 81`
    ([Scientific Python: design](https://learn.scientific-python.org/development/principles/design/)).
16. **Every error is a `pencilmark.Error`** and subclasses the built-in it is (`FormatError` a `ValueError`,
    `FetchError` an `OSError`). No bare `except:`; `assert` only for things that cannot happen, never for checking input
    ([Google Python](https://google.github.io/styleguide/pyguide.html)).

## Comments and docstrings

17. **Comment why, not what.** Fix a comment with the code it describes
    ([Google C++](https://google.github.io/styleguide/cppguide.html), [PEP 8](https://peps.python.org/pep-0008/)).
18. **Every calibrated number says where it came from**: data, fit, date. `# 1.23 per point: fed + Wang human times,
    2026-10-29`.
19. **Every file opens with what it holds and where it sits** ([PEP 257](https://peps.python.org/pep-0257/)).
20. **numpydoc on the public API** (imperative one-line summary, then Parameters / Returns / Raises / Examples); a one-line
    summary on everything else ([numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html)).
21. **C++ documents at the declaration** (header): purpose, inputs, outputs, ownership. Bindings carry `py::arg` names
    and one docstring ([pybind11](https://pybind11.readthedocs.io/en/stable/advanced/functions.html)).

## Tests

22. **Outside in**: public API first, then integration, then units; one behavior per test
    ([Scientific Python: testing](https://learn.scientific-python.org/development/principles/testing/)).
23. **Fast by default, slow on request**: the unit suite runs in seconds; slow suites carry a pytest marker and run
    separately ([pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html),
    [Scientific Python: pytest](https://learn.scientific-python.org/development/guides/pytest/)).
24. **The golden corpus guards every refactor**: `python tools/golden.py check` must report every record identical; a
    deliberate change of output rewrites it in its own commit with the reason.
25. **Check that a new test can fail**: break the code once and watch it go red
    ([Scientific Python: testing](https://learn.scientific-python.org/development/principles/testing/)).
26. **Extension points have a contract, a worked example and a test** that fails until every part exists
    ([scikit-learn](https://scikit-learn.org/stable/developers/develop.html)).

## Tools

27. **ruff** lints and formats Python (line length 120); **clang-format** formats C++. Formatting is never mixed with
    logic changes in one commit ([ruff](https://docs.astral.sh/ruff/rules/),
    [clang-format](https://clang.llvm.org/docs/ClangFormatStyleOptions.html)).
28. **Measure speed before and after** any change meant to be faster, on the same machine and puzzles.
