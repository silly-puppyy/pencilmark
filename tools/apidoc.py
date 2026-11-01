"""Shared rendering for the generated reference pages (gen_api_md, gen_reference_md, gen_cpp_reference), in the shape of
Sphinx autodoc as numpy and pandas show it. The pages are plain Markdown in a few patterns, readable as they are;
website/src/plugins/api-reference.mjs recognises the patterns and styles them:

  ### `def name(args) -> ret` {#anchor}     an entry: its signature (h4 = a method, indented under its class)
  [source](https://github.com/...#L12)    right after an entry: the source link, drawn in the signature box
  [src/pencilmark/x.py](https://...)      a paragraph that is only a link to a file: the module's file
  **Parameters** + a list                  a field list (Parameters, Returns, Yields, Raises, Fields);
                                           items read "- `name` *type* — description"
  a table with an empty header             a summary table; a word before the first cell's link is its kind
"""

import re
from pathlib import Path

GH = "https://github.com/silly-puppyy/pencilmark/blob/main/"
DOCS = Path(__file__).resolve().parents[1] / "docs"
SECTIONS = ("Parameters", "Returns", "Yields", "Raises", "Examples", "Notes", "See Also")
PAGE_TITLES = {
    "formats/puzzle-format": "Puzzle format",
    "formats/grade-card": "Grade card",
    "formats/generator-spec": "Generator spec",
    "formats/other-formats": "Other formats",
}


def md_esc(text):
    """text for a Markdown paragraph: no stray emphasis or HTML"""
    return text.replace("*", "\\*").replace("<", "&lt;")


def links(text, base):
    """'docs/formats/grade-card.md' in a docstring -> a link to that page (`base` = the path from the page to docs/)"""

    def link(m):
        if not (DOCS / m.group(0)[5:]).exists():  # a note outside the published docs (research/...): left as text
            return m.group(0)
        return f"[{PAGE_TITLES.get(m.group(1), m.group(1).rsplit('/', 1)[-1])}]({base}{m.group(0)[5:]})"

    return re.sub(r"docs/([a-z0-9/_-]+)\.mdx?\b", link, text)


def source(path, line):
    """a link to `path` (from the repository root) at `line` on GitHub"""
    return f"{GH}{path}#L{line}" if line else f"{GH}{path}"


def heading(level, anchor, kind, name, args="", prefix="", ret="", src=None):
    """an entry: its signature as a heading, then its source link"""
    sig = f"{kind} " if kind else ""
    sig += f"{prefix}{name}{args}" + (f" -> {ret}" if ret else "")
    return f"{'#' * level} `{sig}` {{#{anchor}}}\n" + (f"\n[source]({src})\n" if src else "")


def file_link(path):
    """the paragraph naming a module's (or header's) file"""
    return f"[{path}]({source(path, 0)})\n"


def summary(doc, limit=110):
    """the first sentence of a docstring, for a summary table"""
    first = " ".join(re.split(r"\n\s*\n", doc.strip())[0].split()) if doc else ""
    m = re.match(r"(.+?[.!?])(\s|$)", first)
    s = m.group(1) if m else first
    return s if len(s) <= limit else s[: limit - 1].rsplit(" ", 1)[0] + "…"


def table(rows, base="../"):
    """a summary table: rows of (anchor, kind, name, summary text)"""
    if not rows:
        return []
    out = ["| Name | What it does |", "|---|---|"]
    for anchor, kind, name, text in rows:
        cell = links(md_esc(text), base).replace("|", "\\|")
        out.append(f"| {kind + ' ' if kind else ''}[`{name}`](#{anchor}) | {cell} |")
    return out + [""]


def flow(doc, base="../"):
    """a free-form docstring as Markdown paragraphs: hard-wrapped lines joined, indented or column-aligned blocks kept
    as code"""
    out = []
    for para in re.split(r"\n\s*\n", doc.strip()):
        lines = para.split("\n")
        if len(lines) > 1 and all(line.startswith("    ") or not line.strip() for line in lines[1:]):
            out.append(links(md_esc(lines[0].strip()), base))
            out.append("```\n" + "\n".join(x[4:] if x.startswith("    ") else x for x in lines[1:]) + "\n```")
        elif all(line.startswith("  ") for line in lines if line.strip()) or (
            sum(bool(re.match(r"^\s*\S+\s{3,}\S", line)) for line in lines) >= 2
        ):  # an indented block, or terms aligned in columns: keep the layout
            out.append("```\n" + "\n".join(lines) + "\n```")
        else:
            out.append(links(md_esc(" ".join(x.strip() for x in lines)), base))
    return [p + "\n" for p in out]


def fields(groups, base="../"):
    """field lists: [(label, [(name, type, description)])]"""
    out = []
    for label, items in groups:
        out.append(f"**{label}**\n")
        for name, typ, desc in items:
            head = " ".join(x for x in (f"`{name}`" if name else "", f"*{md_esc(typ)}*" if typ else "") if x)
            out.append(f"- {head}" + (" — " if head and desc else "") + links(md_esc(desc), base))
        out[-1] += "\n"
    return out


def docstring(doc, base="../"):
    """a docstring -> Markdown: numpydoc sections (Parameters, Returns, Raises, ...) as a field list and Examples as
    code; anything else as paragraphs"""
    lines = doc.split("\n")
    parts, cur, name = [], [], None
    for i, line in enumerate(lines):
        if line.strip() in SECTIONS and i + 1 < len(lines) and set(lines[i + 1].strip()) == {"-"}:
            parts.append((name, cur))
            name, cur = line.strip(), []
            continue
        if name and cur == [] and set(line.strip()) == {"-"}:
            continue
        cur.append(line)
    parts.append((name, cur))
    out, groups, after = [], [], []
    for name, body in parts:
        text = "\n".join(body).strip("\n")
        if not text:
            continue
        if name is None:
            out += flow(text, base)
        elif name == "Examples":
            code = "\n".join(x[4:] if x.startswith("    ") else x for x in body).strip()
            after += ["**Examples**\n", f"```python\n{code}\n```\n"]
        elif name in ("Notes", "See Also"):
            after += [f"**{name}**\n"] + flow(text, base)
        else:
            items, item = [], None  # "name : type" lines start an item; indented lines describe it
            for line in body:
                if line.strip() and not line.startswith(" "):
                    nm, _, typ = line.strip().partition(" : ")
                    if name in ("Returns", "Yields", "Raises") and not typ:
                        nm, typ = "", nm  # an unnamed return value or an exception: the line is its type
                    item = [nm, typ, []]
                    items.append(item)
                elif item is not None and line.strip():
                    item[2].append(line.strip())
            groups.append((name, [(n, t, " ".join(d)) for n, t, d in items]))
    return out + fields(groups, base) + after
