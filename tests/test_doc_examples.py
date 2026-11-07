"""Every Python example in the README, the usage page, the card and format specs and the guides runs as written.

A page's blocks run in order in one namespace, like a notebook, with a few names the fragments assume
(`pencilmark`, `puzzle`, `puzzles`, `spec`, a `puzzles.txt` file with one good and one non-unique puzzle). A block followed by a block showing an error ("pencilmark....Error: ...")
must raise that error. Blocks with placeholder links ("..." / "…") only show the shape of a call and are skipped.
No network: a block that would fetch fails. Slow (about 30 s): marked `slow`, run with `pytest -m slow`.
"""

import re
import socket
import sys
from pathlib import Path

import pytest

import pencilmark

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ROOT / "README.md",
    ROOT / "docs" / "formats" / "grade-card.md",
    ROOT / "docs" / "formats" / "puzzle-format.md",
]
PAGES += sorted((ROOT / "docs" / "start").glob("*.md*"))
PAGES += sorted((ROOT / "docs" / "guides").glob("grader/*.md*")) + sorted(
    (ROOT / "docs" / "guides").glob("generator/*.md*")
)
PAGES += [ROOT / "docs" / "guides" / "development" / "environment.md"]
CLASSIC = "....4.8.3.6...8..29.86.5..1235.........7..2.........96..2......8.12..7...9......."
FENCE = re.compile(r"```(\w*)[^\n]*\n(.*?)```", re.S)
SHOWN_ERROR = re.compile(r"^[\w.]*?(\w+(?:Error|Failed|Unique|Solution|Undecided)): ", re.M)


def blocks(page):
    """(code, expected exception class name or None) for each python block of a page"""
    found = FENCE.findall(page.read_text(encoding="utf-8"))
    out = []
    for i, (lang, code) in enumerate(found):
        if lang != "python":
            continue
        nxt = found[i + 1] if i + 1 < len(found) else None
        m = SHOWN_ERROR.match(nxt[1]) if nxt and nxt[0] == "" else None
        out.append((code, m.group(1) if m else None))
    return out


@pytest.mark.slow
@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_doc_examples_run(page, tmp_path, monkeypatch):
    def no_network(*a, **k):
        raise OSError("network disabled in test_doc_examples")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").symlink_to(ROOT / "docs")  # pages open docs/examples/...
    (tmp_path / "puzzles.txt").write_text(CLASSIC + "\n" + CLASSIC.replace("4", ".", 1) + "\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(ROOT / "tools"))  # the drawing guide imports tools/render_svg.py
    spec = {  # the generate guide's first request (a classic with an X-Wing, found in about a second)
        "format": "pencilmark-spec",
        "format_version": 1,
        "board": {"rows": 9, "cols": 9},
        "digits": 9,
        "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}],
        "symmetry": [{"kind": "rot180", "of": "givens"}],
        "where": {"band": "Hard", "contains": ["XWG"]},
        "limits": {"seconds": 120, "seed": 21},
    }
    ns = {
        "__name__": "__doc_example__",
        "pencilmark": pencilmark,
        "puzzle": CLASSIC,
        "puzzles": [CLASSIC, CLASSIC],
        "spec": spec,
    }
    ran = 0
    for k, (code, error) in enumerate(blocks(page)):
        if "..." in code.split("#")[0] and "https://" in code or "…" in code:
            continue  # the shape of a call with a placeholder link
        where = f"{page.name} block {k}"
        if error:
            with pytest.raises(Exception) as e:
                exec(compile(code, where, "exec"), ns)
            assert type(e.value).__name__ == error, f"{where}: raised {type(e.value).__name__}, the page shows {error}"
        else:
            try:
                exec(compile(code, where, "exec"), ns)
            except Exception as e:  # noqa: BLE001 -- report which block, with the error
                pytest.fail(f"{where}: {type(e).__name__}: {e}")
        ran += 1
    assert ran or not blocks(page), f"{page.name}: every block skipped"
    sys.modules.pop("render_svg", None)
