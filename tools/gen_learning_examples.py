"""The puzzles of the "Generate for learning" guide: a technique ladder (each puzzle needs singles, the earlier rungs'
techniques and exactly one new one) and a killer curriculum (four stages, small cages to cage maths). Kept in docs/examples/learning/<name>.json
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
# the killer curriculum (user 2026-11-07): small cages with givens in them, where a cage's last cell is its total minus
# the digits in it; then bigger cages; then the cages' digit sets (combinations); then cage maths (the rule of 45).
# Early stages keep the totals low (easy mental arithmetic). name -> (title, what it teaches, cage template, givens,
# where); every stage passes the standard publishing checks (the generator's default)
CSI = {"codes": ["CSI"], "strict": True}
KILLERS = {
    "killer-1-last-cell": ("Last cell of a cage", "a cage's last cell is its total minus the digits already in it",
                           {"size": [2, 3], "sum": [3, 15], "count": [8, 14]}, [30, 46],
                           {"band": "Very Easy", "contains": CSI}),
    "killer-2-bigger-cages": ("Bigger cages", "longer cages and fewer givens: add up more digits before the last one",
                              {"size": [3, 5], "sum": [6, 25], "count": [8, 14]}, [24, 36],
                              {"band": "Very Easy", "contains": CSI}),
    "killer-3-combinations": ("Cage combinations", "a cage's digit sets do the work: a 3 in two cells is 1 and 2",
                              {"count": "tile"}, [8, 22], {"band": "Easy", "contains": {"codes": ["CGC"], "strict": True}}),
    "killer-4-cage-maths": ("Cage maths", "the rule of 45: a house's total minus the cages inside it gives the rest",
                            {"count": "tile"}, 0, {"contains": {"codes": ["IOU"], "strict": True}}),
}  # fmt: skip

QUALITY = {}  # name -> a quality object instead of the standard preset
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
    title, _teaches, cage, giv, where = KILLERS[name]
    s = spec(
        rules=[{"type": "cage", **cage}],
        givens={"count": giv},
        where=where,
        seed=KILLER_SEED.get(name, list(KILLERS).index(name) + 1),  # a seed per stage: one seed gives one grid
        time=600,
    )
    if name in QUALITY:
        s["quality"] = QUALITY[name]
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
        spec = {"format": "pencilmark-spec", "format_version": 1, "board": {"rows": 9, "cols": 9}, "digits": 9,
                "rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]}],
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

Killers start with one idea: the digits in a cage add up to its total, so when all but one are known, the last is the
total minus the others. The first stage teaches just that, with small cages, low totals (easy mental arithmetic) and
givens inside the cages; the second makes the cages longer; the third lets the cages' digit sets do the work (a 3 in
two cells is 1 and 2, which acts like a pointing pair); the fourth is cage maths, the rule of 45, on a board of cages
with no givens. Each stage asks for its technique (`"strict": true`) and keeps small totals where the arithmetic is
new:

```json
{"rules": [{"type": "box_grid", "box": [3, 3], "count": [3, 3]},
           {"type": "cage", "size": [2, 3], "sum": [3, 15], "count": [8, 14]}],
 "givens": {"count": [30, 46]}, "where": {"band": "Very Easy", "contains": {"codes": ["CSI"], "strict": true}}}
```

Every stage passes the standard publishing checks (the generator's default), so even the first is not mostly given.
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
    for name, (title, teaches, _c, _g, _w) in KILLERS.items():
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
