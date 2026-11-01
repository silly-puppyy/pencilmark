"""The puzzles of the "Generate for learning" guide: a technique ladder (each puzzle needs singles, the earlier rungs'
techniques and exactly one new one) and a killer curriculum (cages covering the board, in four stages). Kept in docs/examples/learning/<name>.json
({"title", "spec", "puzzle", "card", "tries"}) and drawn by tools/gen_swatches.py. Generation takes minutes (the
ladder tries seeds until a card has no other technique), so the results are committed; run this again when the
generator changes.
  python tools/gen_learning_examples.py [name ...] [--jobs N]"""

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_generator_examples import spec  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "examples" / "learning"
SINGLES = {"FHS", "HSI", "NSI"}
# name -> (title, technique code, band)
LADDER = {
    "ladder-1-pointing": ("Pointing / box-line reduction", "PPR", "Easy"),
    "ladder-2-naked-pair": ("Naked pair", "NPR", "Medium"),
    "ladder-3-hidden-pair": ("Hidden pair", "HPR", "Medium"),
    "ladder-4-naked-triple": ("Naked triple", "NTR", "Medium"),
    "ladder-5-x-wing": ("X-Wing", "XWG", "Hard"),
    "ladder-6-swordfish": ("Swordfish", "SWF", "Very Hard"),
}
# the killer curriculum: cages cover every cell that is not a given (a lone cell becomes a given, never a 1-cell cage);
# name -> (title, what it teaches, givens, where)
KILLERS = {
    "killer-1-first-cages": ("First cages", "a mostly filled grid where a cage or two give the last singles",
                             [50, None], {"band": "Very Easy", "difficulty": [0, 3]}),
    "killer-2-more-cages": ("More cages", "fewer givens, so more of the grid is read through cage sums",
                            [28, 40], {"band": "Very Easy", "difficulty": [2, 4.5]}),
    "killer-3-combinations": ("Cage combinations", "a cage's digit sets do the work: a 3 in two cells is 1 and 2",
                              [8, 22], {"band": "Easy", "contains": {"codes": ["CGC"], "strict": True}}),
    "killer-4-no-givens": ("No givens", "the cages alone: no number clue to start from", 0, {"band": "Easy"}),
}  # fmt: skip


KILLER_SEED = {}  # name -> seed, where seed 1 found nothing in the time


def only(card, code, earlier=()):
    """the card's techniques are singles, the earlier rungs' and code, and code is there"""
    codes = {c["code"] for c in card.get("contains") or []}
    return code in codes and codes <= SINGLES | set(earlier) | {code}


def run(name):
    import pencilmark

    if name in LADDER:
        title, code, band = LADDER[name]
        earlier = [c for n, (_t, c, _b) in LADDER.items() if n < name]
        for seed in range(1, 25):
            s = spec(where={"band": band, "contains": {"codes": [code], "strict": True}}, seed=seed, time=120)
            try:
                r = pencilmark.generate(s)
            except pencilmark.GenerationFailed:
                continue
            if only(r["card"], code, earlier):
                return save(name, title, s, r, seed)
        return name, "no seed in 1..24 gave singles, the earlier rungs and that technique alone"
    title, _teaches, giv, where = KILLERS[name]
    s = spec(
        rules=[{"type": "cage", "count": "tile"}],
        givens={"count": giv},
        where=where,
        seed=KILLER_SEED.get(name, list(KILLERS).index(name) + 1),  # a seed per stage: one seed gives one grid
        time=600,
    )
    try:
        r = pencilmark.generate(s)
    except pencilmark.GenerationFailed as e:
        return name, f"failed: {e}"
    return save(name, title, s, r, s["limits"]["seed"])


def save(name, title, s, r, tries):
    card = {k: r["card"].get(k) for k in ("band", "difficulty", "time", "contains")}
    d = {"title": title, "spec": s, "puzzle": r["puzzle"], "card": card, "tries": tries}
    (OUT / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return name, f"{card['band']} {card['difficulty']} (seed {tries})"


PAGE = ROOT / "docs" / "guides" / "generator" / "generate-for-learning.mdx"
INTRO = """---
title: Generate for learning
description: "Puzzles for practice: one new technique at a time, and the same kind of puzzle at rising bands."
---

import Swatch from '@site/src/components/Swatch';

# Generate for learning

A learner needs puzzles that ask for one new idea at a time. The generator can target a band and require a technique;
a short loop does the rest. Two recipes: a technique ladder, where each puzzle adds exactly one new technique to what
the earlier rungs taught, and a progression, the same kind of puzzle at rising bands. The puzzles below were made this way by
`tools/gen_learning_examples.py`.

## 1. One new technique at a time

Ask for the technique (`"strict": true`, so it must appear as itself, not only as an alternative) and the band it
belongs to, then keep the first puzzle whose card lists nothing beyond singles and what the learner already knows. The
band caps what the solver may need, but other techniques of the same band can still turn up, hence the check:

```python
import pencilmark

SINGLES = {"FHS", "HSI", "NSI"}

def practice(code, band, known=(), tries=24):
    for seed in range(1, tries + 1):
        spec = {"format": "sudoku-spec", "format_version": 1, "board": {"rows": 9, "cols": 9}, "digits": 9,
                "rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}],
                "where": {"band": band, "contains": {"codes": [code], "strict": True}},
                "limits": {"time": 120, "seed": seed}}
        try:
            result = pencilmark.generate(spec)
        except pencilmark.GenerationFailed:
            continue
        codes = {c["code"] for c in result["card"]["contains"]}
        if code in codes and codes <= SINGLES | set(known) | {code}:
            return result["puzzle"]

# puzzle = practice("XWG", "Hard", known=["PPR", "NPR"])   # an X-Wing, nothing new besides (a few minutes)
```

[Techniques](../../grades/techniques.md) lists every code with its band. A ladder for classic sudoku, easiest first:
"""
MIDDLE = """
## 2. A killer curriculum

Someone starting out with killers first meets a cage or two that are needed for simple singles; then the cages
multiply; then the cages' digit sets do the work (a 3 in two cells is 1 and 2, which acts like a pointing pair); and at
last there are no number clues at all. Each stage below is a killer whose cages cover every cell that is not a given
(a cell left alone becomes a given: a 1-cell cage is a given in disguise), with a given range and a target:

```json
{"rules": [{"type": "box_grid", "origin": "r1c1", "box": [3, 3]}, {"type": "cage", "count": "tile"}],
 "givens": {"count": [28, 40]}, "where": {"band": "Very Easy", "difficulty": [2, 4.5]}}
```

Without a difficulty range the generator removes every given it can, and a grid with few givens takes long to scan
even when it needs only singles: a Very Easy puzzle then scores about 4-5. The range keeps the first stages gentle.
"""


def write_page():
    """the guide, from the kept results"""

    def section(name, heading):
        f = OUT / f"{name}.json"
        if not f.exists():
            return []
        d = json.loads(f.read_text(encoding="utf-8"))
        c = d["card"]
        chips = ", ".join(x.get("name") or x.get("code") for x in c.get("contains") or [])
        tries = f" (seed {d['tries']})" if name in LADDER else ""
        return [f"### {heading}", "", f'<Swatch name="learning-{name}" />', "",
                f"**{c['band']}**, difficulty {c['difficulty']}, about {c['time']} min{tries}. Contains: {chips}.", ""]  # fmt: skip

    L = [INTRO]
    for name, (title, code, band) in LADDER.items():
        L += section(name, f"{title} (`{code}`, {band})")
    L.append(MIDDLE)
    for name, (title, teaches, _g, _w) in KILLERS.items():
        L += section(name, f"{title}: {teaches}")
    PAGE.write_text("\n".join(L), encoding="utf-8")


def main(argv):
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 6
    if "--page" in argv:  # only rewrite the guide from the kept results
        return write_page()
    names = [a for a in argv if a in LADDER or a in KILLERS] or [*LADDER, *KILLERS]
    OUT.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(jobs) as ex:
        for name, result in ex.map(run, names):
            print(f"{name:24s} {result}", flush=True)
    write_page()


if __name__ == "__main__":
    main(sys.argv[1:])
