"""Write docs/grades/clue-facts.md, the clue facts of the common rules (pencilmark/explain/clue_facts.py), each checked:
its probe's eliminations are true (brute force: no completed grid has that digit there) and the engine makes them (the
step that first does, with its price). Needs the built engine (installed package; sync src first).
  python tools/gen_clue_facts_md.py [--check]      --check: exit 1 if the page is out of date or a fact fails"""

import sys
from pathlib import Path

from pencilmark import api  # the installed package (the engine is compiled there)
from pencilmark import cbackend as CB
from pencilmark.explain.clue_facts import BY_ID, FACTS
from pencilmark.model import RELATIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "grades" / "clue-facts.md"
JOBS = 4


def _cell(s):
    r, c = s[1:].split("c")
    return (int(r) - 1) * 9 + int(c) - 1


def _doc(rules, givens):
    g = [0] * 81
    for k, v in givens.items():
        g[_cell(k)] = v
    return {
        "format": "pencilmark-puzzle",
        "format_version": 1,
        "board": {"rows": 9, "cols": 9},
        "digits": 9,
        "givens": g,
        "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}] + rules,
    }


def _possible(rules, givens, cell, d):
    p = api._load(_doc(rules, {**givens, cell: d}))
    return len(CB.brute_solve(p, limit=1, node_limit=200_000)) >= 1


def _peers(c):
    return {
        x
        for x in range(81)
        if x != c and (x // 9 == c // 9 or x % 9 == c % 9 or (x // 27, x % 9 // 3) == (c // 27, c % 9 // 3))
    }


def _on_placing(p):
    """(cell, digit) the givens remove through the pair rules the moment they are placed (with the notes, no step)"""
    out = set()
    for kind, a, b, *args in p.relations:
        for g, x, fwd in ((a, b, True), (b, a, False)):
            v = p.givens.get(g)
            if v is None or x in p.givens:
                continue
            for w in range(1, p.D + 1):
                if not (RELATIONS[kind](v, w, *args) if fwd else RELATIONS[kind](w, v, *args)):
                    out.add((x, w))
    return out


def check(f):
    """-> (errors, applied): the probe's claims that are false, and how the engine makes the rest ('' none)"""
    rules, givens = f.probe
    claim = {(_cell(c), d) for c, ds in f.expect.items() for d in ds}
    errors = [
        f"r{c // 9 + 1}c{c % 9 + 1}={d} is possible"
        for c, d in sorted(claim)
        if _possible(rules, givens, f"r{c // 9 + 1}c{c % 9 + 1}", d)
    ]
    p = api._load(_doc(rules, givens))
    steps, _ = CB.solve(p, assume_unique=False, max_steps=200)
    first = {}
    for s in steps:
        m = s.move
        if m.family in ("TakeNotes", "Guess"):
            continue
        effs = list(m.elim or [])
        if m.place:
            pc, pd = m.place
            effs += [(pc, d) for d in range(1, 10) if d != pd] + [(x, pd) for x in _peers(pc)]
        for e in effs:
            first.setdefault(e, (m.family, float(m.d)))
    onp = _on_placing(p)
    rest = claim - onp
    got = sorted({first[e] for e in rest if e in first}, key=lambda t: t[1])
    missing = rest - set(first)
    if not rest:
        applied = "Placing the digit: the rule acts on its neighbor like a sudoku peer"
    elif missing and f.note:
        applied = f.note
    elif missing:
        applied = "not derived: the engine needs a guess"
    else:
        applied = ", ".join(f"{n} ({d:.1f})" for n, d in dict(got).items())
    return errors, applied


def _check_id(fid):
    return check(BY_ID[fid])


def page():
    from concurrent.futures import ProcessPoolExecutor

    rows, errors = {}, []
    with ProcessPoolExecutor(max_workers=JOBS) as ex:  # one brute-force check per fact, a few seconds each
        checked = list(ex.map(_check_id, [f.id for f in FACTS]))
    for f, (err, applied) in zip(FACTS, checked):
        errors += [f"{f.id}: {e}" for e in err]
        rows.setdefault(f.rule, []).append((f, applied))
    out = [
        "---",
        "title: Clue facts",
        "description: The little facts solvers learn for each common rule, and which step of the grader uses each.",
        "---",
        "",
        "# Clue facts",
        "",
        'Every common rule comes with a few facts that solvers learn once and then use without thinking: "a 5 is never',
        'on a German whisper", "a 5-cell renban always holds a 5". This page lists them, with how many Cracking the',
        "Cryptic solve videos state each one (counted in our research notes; 0 = not counted).",
        "",
        "**Applied by** names the grader step that makes the fact's eliminations, with its price. **ClueFacts** and",
        "**ClueShape** read the facts of two-cell rules off the clues before solving and cost the least. Facts about",
        "longer rules come from that rule's own technique, and a few are built into how the rule is modeled. Rules",
        "that aren't on this page, or rules a setter made up, are worked out from the rule text instead.",
        "",
        "This page is generated from `pencilmark/explain/clue_facts.py` (`tools/gen_clue_facts_md.py`). Each fact",
        "is checked on a small example: no completed grid breaks it, and the grader makes it.",
        "",
    ]
    for rule, items in rows.items():
        out += [f"## {rule}", "", "| Fact | Videos | Applied by |", "|---|---|---|"]
        out += [f"| {f.text} | {f.videos or ''} | {applied} |" for f, applied in items]
        out.append("")
    return "\n".join(out), errors


def main():
    text, errors = page()
    for e in errors:
        print("FALSE FACT", e)
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text() == text
        if not ok:
            print(f"{OUT} is out of date: run tools/gen_clue_facts_md.py")
        sys.exit(0 if ok and not errors else 1)
    OUT.write_text(text)
    print(f"wrote {OUT}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
