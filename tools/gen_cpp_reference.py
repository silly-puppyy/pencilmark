"""Write the C++ engine reference (docs/reference/cpp-*.md) from the comments in csrc/: Doxygen reads them into XML
(build/doxygen-xml), this script turns the XML into pages in the shape of the Python reference (tools/apidoc.py). One
page per header, its classes with their public functions and fields, and a page listing every source file. Without
doxygen (on PATH, or $DOXYGEN) the pages say so and the site builds without them.
  python tools/gen_cpp_reference.py"""

import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import apidoc

ROOT = Path(__file__).resolve().parents[1]
XML = ROOT / "build" / "doxygen-xml"
OUT = ROOT / "docs" / "reference"
# page slug -> (title, description, headers)
PAGES = {
    "cpp-solver": ("The solver", "The techniques, moves, pricing parameters and the Solver class.", ["solver.hpp"]),
    "cpp-model": ("The puzzle model", "Houses, cages, rules and candidates: the puzzle the solver works on.",
                  ["model.hpp"]),
    "cpp-nary": ("N-ary constraints", "Rules over several cells checked by enumeration (lines, sums, relations).",
                 ["nary.hpp"]),
    "cpp-util": ("Utilities", "Deadlines, move helpers, portability and the Python bridge.",
                 ["deadline.hpp", "move_util.hpp", "portable.hpp", "pycompat.hpp", "solver_util.hpp"]),
}  # fmt: skip


def run_doxygen():
    """the XML, fresh; False when doxygen is not installed"""
    exe = os.environ.get("DOXYGEN") or shutil.which("doxygen")
    if not exe:
        return False
    shutil.rmtree(XML, ignore_errors=True)
    XML.mkdir(parents=True)
    subprocess.run([exe, "-"], cwd=ROOT, input=(ROOT / "Doxyfile").read_text(), text=True, check=True)
    return True


def _text(el):
    """an XML description as Markdown-ish text: code spans in backticks, everything else plain"""
    if el is None:
        return ""
    out = [el.text or ""]
    for c in el:
        inner = _text(c)
        if c.tag in ("computeroutput", "ref") and not inner.startswith("`"):
            inner = f"`{inner}`"
        if c.tag in ("parameterlist", "simplesect", "programlisting", "itemizedlist"):
            inner = ""  # handled by _desc
        out += [inner, c.tail or ""]
    return "".join(out)


def _desc(member):
    """(paragraphs, field groups) of a member's brief and detailed description"""
    paras, groups = [], []
    for part in ("briefdescription", "detaileddescription"):
        for para in member.findall(f"{part}/para"):
            t = " ".join(_text(para).split())
            if t:
                paras.append(t)
            params = [
                (" ".join(i.itertext()).strip(), "", " ".join(_text(d).split()))
                for item in para.iter("parameteritem")
                for i in item.iter("parametername")
                for d in item.findall("parameterdescription")
            ]
            if params:
                groups.append(("Parameters", params))
            for sect in para.iter("simplesect"):
                if sect.get("kind") == "return":
                    groups.append(("Returns", [("", "", " ".join(_text(sect).split()))]))
            for lst in para.iter("itemizedlist"):
                paras.append("\n".join("- " + " ".join(_text(li).split()) for li in lst.findall("listitem")))
            for code in para.iter("programlisting"):
                lines = ["".join(line.itertext()) for line in code.findall("codeline")]
                paras.append("```cpp\n" + "\n".join(lines) + "\n```")
    return paras, groups


def _flat(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _anchor(qualified):
    return qualified.removeprefix("cs::").replace("::", ".")


def _src(member):
    loc = member.find("location")
    return apidoc.source(loc.get("file"), int(loc.get("line", 0))) if loc is not None else None


def _body(member):
    paras, groups = _desc(member)
    out = [apidoc.md_esc(p) + "\n" if not p.startswith(("```", "- ")) else p + "\n" for p in paras]
    return out + apidoc.fields(groups)


def _functions(members, qual, seen):
    """summary rows and entries for functions"""
    rows, out = [], []
    for m in members:
        name = m.findtext("name")
        anchor = _anchor(f"{qual}::{name}" if qual else name)
        n = seen.get(anchor, 0)
        seen[anchor] = n + 1
        anchor += f"-{n + 1}" if n else ""
        paras, _ = _desc(m)
        rows.append((anchor, "", name, apidoc.summary(paras[0] if paras else "")))
        ret = _flat(m.find("type"))
        static = "static " if m.get("static") == "yes" else ""
        out.append(apidoc.heading(3, anchor, static + ret, name, m.findtext("argsstring") or "", src=_src(m)))
        out += _body(m) or ["*No comment.*\n"]
    return rows, out


def _fields(members):
    """public data members, types, enums and typedefs as one field list"""
    items = []
    for m in members:
        paras, _ = _desc(m)
        kind = m.get("kind")
        typ = _flat(m.find("type")) + (m.findtext("argsstring") or "")
        if kind == "enum":
            values = ", ".join(v.findtext("name") for v in m.findall("enumvalue"))
            typ, paras = "enum", paras + [f"Values: {values}."]
        elif kind == "typedef":
            typ = "= " + typ
        items.append((m.findtext("name"), typ, " ".join(paras)))
    return apidoc.fields([("Fields", items)]) if items else []


def _members(compound, prot=("public",)):
    """(functions, everything else) of a compound, in declaration order"""
    funcs, other = [], []
    for sec in compound.findall("sectiondef"):
        for m in sec.findall("memberdef"):
            if m.get("prot", "public") not in prot or m.get("kind") == "friend":
                continue
            (funcs if m.get("kind") == "function" else other).append(m)
    return funcs, other


def _compound(refid):
    return ET.parse(XML / f"{refid}.xml").getroot().find("compounddef")


def _class(c):
    """one class or struct: its heading, comment, summary table, fields, then each public function"""
    qual = c.findtext("compoundname")
    short = qual.removeprefix("cs::")
    loc = c.find("location")
    out = [f"## {c.get('kind')} {short} {{#{_anchor(qual)}}}\n"]
    out.append(f"[source]({apidoc.source(loc.get('file'), int(loc.get('line', 0)))})\n")
    out += _body(c)
    funcs, other = _members(c)
    rows, entries = _functions(funcs, qual, {})
    out += apidoc.table(rows)
    out += _fields(other)
    return out + entries


def page(title, description, headers):
    L = [
        "---",
        f"title: {json.dumps(title)}",
        f"description: {json.dumps(description)}",
        "toc_max_heading_level: 2",
        "---",
        "",
        f"# {title}",
        "",
        f"{description} Generated from the comments in the headers by Doxygen and `tools/gen_cpp_reference.py`; "
        "public members only.",
        "",
    ]
    for h in headers:
        f = _compound(h.replace("_", "__").replace(".", "_8"))
        path = f"csrc/{h}"
        L += [f"## {h} {{#{h.replace('.', '-')}}}", "", apidoc.file_link(path)]
        L += _body(f)
        funcs, other = _members(f, ("public", "private", "protected"))
        funcs = [m for m in funcs if m.find("location").get("file") == path]
        other = [m for m in other if m.find("location").get("file") == path and m.get("kind") != "define"]
        rows, entries = _functions(funcs, "", {})
        L += apidoc.table(rows) + _fields(other) + entries
        for inner in f.findall("innerclass"):
            L += _class(_compound(inner.get("refid")))
    return "\n".join(L)


def files_page():
    """every source file with its @file comment"""
    L = [
        "---",
        'title: "Source files"',
        'description: "Every file of the C++ engine and what it holds."',
        "---",
        "",
        "# Source files",
        "",
        "Every file in `csrc/` with the comment at its top; the headers have pages of their own.",
        "",
        "| | |",
        "|---|---|",
    ]
    pages = {h: slug for slug, (_, _, hs) in PAGES.items() for h in hs}
    for p in sorted((ROOT / "csrc").glob("*.[ch]pp")):
        f = _compound(p.name.replace("_", "__").replace(".", "_8"))
        paras, _ = _desc(f)
        name = f"[`{p.name}`]({apidoc.source('csrc/' + p.name, 0)})"
        text = apidoc.md_esc(" ".join(paras)).replace("|", "\\|")
        if p.name in pages:
            text += f" ([reference]({pages[p.name]}.md))"
        L.append(f"| {name} | {text} |")
    return "\n".join(L + [""])


def stub(title):
    return f'---\ntitle: "{title}"\n---\n\n# {title}\n\nThis build of the site had no doxygen, so the C++ reference is missing.\n'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ok = run_doxygen()
    for slug, (title, description, headers) in PAGES.items():
        (OUT / f"{slug}.md").write_text(page(title, description, headers) if ok else stub(title), encoding="utf-8")
    (OUT / "cpp-files.md").write_text(files_page() if ok else stub("Source files"), encoding="utf-8")
    if not ok:
        print("doxygen not found: the C++ reference pages are stubs")


if __name__ == "__main__":
    main()
