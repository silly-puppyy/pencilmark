"""The version each doc page is "as of": the earliest release whose text of the page is still the page's text (no
release after it changed the page). A page edited since the last release is "as of" the next version. Pages not
tracked in git (generated at build time) get none. Written for the badge (website/src/theme/DocVersionBadge) to
website/src/data/page_versions.json: {"current" | "<version>": {"<path under docs/>": "1.2"}}.

  python tools/gen_page_versions.py"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "website" / "src" / "data" / "page_versions.json"


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def releases():
    """[(version "1.2", tag "v1.2.0")] oldest first, final releases only"""
    tags = [t for t in (git("tag") or b"").decode().split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    tags.sort(key=lambda t: tuple(int(x) for x in t[1:].split(".")))
    return [(".".join(t[1:].split(".")[:2]), t) for t in tags]


def as_of(rel, text, rels, after):
    """the earliest release from which the page's text stayed `text` through the last of rels; `after` if none"""
    found = after
    for version, tag in reversed(rels):
        if git("show", f"{tag}:docs/{rel}") != text:
            break
        found = version
    return found


def main():
    rels = releases()
    tracked = set((git("ls-files", "docs") or b"").decode().split("\n"))
    versions = json.loads((ROOT / "website" / "versions.json").read_text(encoding="utf-8"))
    nxt = rels[-1][0].split(".")
    nxt = f"{nxt[0]}.{int(nxt[1]) + 1}"
    out = {"current": {}}
    for f in sorted((ROOT / "docs").rglob("*.md*")):
        rel = f.relative_to(ROOT / "docs").as_posix()
        if f"docs/{rel}" in tracked:
            out["current"][rel] = as_of(rel, f.read_bytes(), rels, nxt)
    for v in versions:  # a frozen version: its snapshot against the releases up to it
        base = ROOT / "website" / "versioned_docs" / f"version-{v}"
        upto = [r for r in rels if tuple(map(int, r[0].split("."))) <= tuple(map(int, v.split(".")))]
        out[v] = {}
        for f in sorted(base.rglob("*.md*")):
            rel = f.relative_to(base).as_posix()
            if any(git("cat-file", "-e", f"{t}:docs/{rel}") is not None for _, t in upto):
                out[v][rel] = as_of(rel, f.read_bytes(), upto, v)
    for v in out.values():  # keys as the URL path the page is served at: no extension, an index page as its folder
        for rel in list(v):
            key = re.sub(r"\.mdx?$", "", rel)
            v[key.removesuffix("/index") if key.endswith("/index") else key] = v.pop(rel)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({sum(len(v) for v in out.values())} pages)")


if __name__ == "__main__":
    main()
