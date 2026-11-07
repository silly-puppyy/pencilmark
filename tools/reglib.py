"""HoDoKu's regression library against pencilmark's techniques (a development check; the library is GPL / FDL and is
never copied into this repository: it ships with HoDoKu, http://hodoku.sourceforge.net, as reglib-1.3.txt).

    python tools/reglib.py run LIB [OUT.jsonl]     every case: exact / superset / union / missing / unsupported, unsound
    python tools/reglib.py show LIB CODE [N]       the first N missing cases of a HoDoKu code (0600 = UR type 1, ...):
                                                   what HoDoKu expects, what our mapped techniques list, and whether
                                                   the case's position is consistent with its solution

Per case: the grid (givens and placed digits apart, as avoidable rectangles need), peer eliminations, then the case's
deleted candidates; only the mapped techniques are switched on (computer params, uniqueness allowed). Every move we
list is checked against the solution. Run it outside the repository root."""

import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

# HoDoKu code -> our technique names (None: not implemented here)
FISH = {"FinnedFish", "X-Wing", "Swordfish", "Jellyfish"}
CHAINS = {"AIC", "NiceLoop(discontinuous)", "X-Chain", "XY-Chain", "RemotePairs"}
MAP = {
    "0000": {"FullHouse"},
    "0002": {"HiddenSingle(notes)"},
    "0003": {"NakedSingle(notes)"},
    "0100": {"LockedCandidates"},
    "0101": {"LockedCandidates"},
    "0110": {"NakedPair", "LockedCandidates"},
    "0111": {"NakedTriple", "LockedCandidates"},
    "0200": {"NakedPair"},
    "0201": {"NakedTriple"},
    "0202": {"NakedQuad"},
    "0210": {"HiddenPair"},
    "0211": {"HiddenTriple"},
    "0212": {"HiddenQuad"},
    "0300": {"X-Wing"},
    "0301": {"Swordfish"},
    "0302": {"Jellyfish"},
    "0400": {"X-Chain"},
    "0401": {"X-Chain"},
    "0402": {"EmptyRectangle"},
    "0403": {"X-Chain"},
    "0404": {"X-Chain"},
    "0405": {"EmptyRectangle"},
    "0500": {"Coloring"},
    "0501": {"Coloring"},
    "0502": {"MultiColouring"},
    "0503": {"MultiColouring"},
    "0504": {"Coloring", "MultiColouring"},
    "0505": {"Coloring", "MultiColouring"},
    "0507": {"3DMedusa"},
    "0610": {"BUG+1"},
    "0701": {"X-Chain"},
    "0702": {"XY-Chain"},
    "0703": {"RemotePairs"},
    "0704": {"X-Chain"},
    "0705": CHAINS,
    "0800": {"XY-Wing"},
    "0801": {"XYZ-Wing"},
    "0802": {"WXYZ-Wing"},
    "0803": CHAINS,
    "0901": {"ALS-XZ"},
    "0902": {"ALS-XY-Wing"},
    "0903": {"ALS-AIC"},
    "0904": {"DeathBlossom"},
    "1000": {"AlignedPairExclusion"},
    "1101": {"SueDeCoq"},
    "1201": {"PatternOverlay"},
    "1202": {"PatternOverlay"},
    "1301": {"ForcingChains", "DynamicForcingChains"},
    "1302": {"ForcingChains", "DynamicForcingChains"},
    "1303": {"DynamicForcingChains", "NestedForcingChains"},
    "1304": {"DynamicForcingChains", "NestedForcingChains"},
}
for c in ("0600", "0601", "0602", "0603", "0604", "0605", "0606", "0607", "0608", "0620"):
    MAP[c] = {"UniqueRectangle"}
for c in ("0706", "0707", "0708", "0709", "0710", "0711"):
    MAP[c] = CHAINS
for base in range(10, 70, 10):  # finned / sashimi / franken / finned franken / mutant / finned mutant, sizes 2-4
    for size in range(3):
        MAP[f"03{base + size:02d}"] = FISH


def parse(line):
    f = line.strip().split(":")
    code, variant = (f[1].split("-") + [""])[:2]
    giv = f[3]
    cells, placed, i = [0] * 81, set(), 0
    j = 0
    while j < len(giv):
        plus = giv[j] == "+"
        if plus:
            j += 1
        ch = giv[j]
        cells[i] = int(ch) if ch.isdigit() else 0
        if plus:
            placed.add(i)
        i += 1
        j += 1
    trip = lambda s: [(int(t[0]), (int(t[1]) - 1) * 9 + int(t[2]) - 1) for t in s.split()]
    return dict(
        code=code,
        variant=variant,
        cand=f[2],
        cells=cells,
        placed=placed,
        deleted=trip(f[4]),
        elims=trip(f[5]),
        places=trip(f[6]),
        raw=line.strip(),
    )


def _rc(x):
    return f"r{x // 9 + 1}c{x % 9 + 1}"


def state(case):
    """(engine puzzle, candidate masks) of a case's position"""
    import pencilmark as pm
    from pencilmark import api

    hs = [[r * 9 + c for c in range(9)] for r in range(9)] + [[r * 9 + c for r in range(9)] for c in range(9)]
    hs += [[(br + i // 3) * 9 + bc + i % 3 for i in range(9)] for br in (0, 3, 6) for bc in (0, 3, 6)]
    peers = [set().union(*[set(h) for h in hs if x in h]) - {x} for x in range(81)]
    mask = []
    for x in range(81):
        v = case["cells"][x]
        seen = {case["cells"][y] for y in peers[x] if case["cells"][y]}  # each digit once
        mask.append(1 << (v - 1) if v else 511 & ~sum(1 << (d - 1) for d in seen))
    for d, x in case["deleted"]:
        mask[x] &= ~(1 << (d - 1))
    doc = pm.read.plain("".join(str(v) for v in case["cells"]))
    doc["givens"] = [0 if x in case["placed"] else v for x, v in enumerate(case["cells"])]
    doc["placed"] = {_rc(x): case["cells"][x] for x in sorted(case["placed"])}
    return api._load(doc), mask


def techniques(case):
    """our technique names for a case (None: no counterpart); grouped chains "with ALS" add ALS-AIC"""
    techs = MAP.get(case["code"])
    if techs is CHAINS and (case["code"], case["variant"]) in {("0709", "2"), ("0710", "3"), ("0710", "4"),
                                                                ("0711", "3"), ("0711", "4")}:  # fmt: skip
        techs = CHAINS | {"ALS-AIC"}
    return techs


def moves(case):
    """(our moves at the case's position: [{"elim": {(cell, digit)}, "place", "code"}], the solution)"""
    import pencilmark as pm
    from pencilmark import api
    from pencilmark import cbackend as CB
    from pencilmark import solver as S

    sol = [int(x) for x in pm.solve("".join(str(v) for v in case["cells"]))]
    p, mask = state(case)
    on = {t for t, n in S.TECH_NAMES.items() if n in techniques(case)}
    mv = CB.state_moves(p, api._params("computer"), cpuzzle=CB.to_cpuzzle(p), cand=mask, limit_per_tech=0,
                        assume_unique=True, disabled=list(set(S.TECH_NAMES) - on))  # fmt: skip
    out = []
    for m in mv:  # a placement also removes the cell's other candidates (HoDoKu lists BUG+1 that way)
        e = {(c, d) for c, d in m["elim"]}
        if m["place"]:
            c, v = m["place"]
            e |= {(c, d) for d in range(1, 10) if d != v and mask[c] >> (d - 1) & 1}
        out.append({"elim": e, "place": tuple(m["place"]) if m["place"] else None, "code": m.get("code")})
    return out, sol


def job(case):
    out = {"code": case["code"], "variant": case["variant"]}
    if not techniques(case):
        return dict(out, status="unsupported")
    try:
        mv, sol = moves(case)
    except Exception as e:  # noqa: BLE001
        return dict(out, status="bad puzzle: " + type(e).__name__)
    out["unsound"] = sum(1 for m in mv for c, d in m["elim"] if sol[c] == d) + sum(
        1 for m in mv if m["place"] and sol[m["place"][0]] != m["place"][1]
    )
    digits = {int(c) for c in case["cand"]} if case["cand"].isdigit() else set()
    if case["variant"] == "x":  # no instance allowed: pass when nothing is found for that digit
        hit = [m for m in mv if any(d in digits for _, d in m["elim"]) or (m["place"] and m["place"][1] in digits)]
        return dict(out, status="fail case FOUND" if hit else "fail case ok")
    if case["elims"]:
        want, sets = {(x, d) for d, x in case["elims"]}, [m["elim"] for m in mv]
        out["status"] = ("exact" if any(s == want for s in sets) else "superset" if any(s >= want for s in sets)
                         else "union" if sets and want <= set().union(*sets) else "missing")  # fmt: skip
    else:
        want = {(x, d) for d, x in case["places"]}
        out["status"] = "exact" if want <= {m["place"] for m in mv if m["place"]} else "missing"
    return out


def main(argv):
    cmd, lib = argv[0], argv[1]
    cases = [parse(line) for line in open(lib, encoding="utf-8") if line.startswith(":")]
    if cmd == "run":
        with ProcessPoolExecutor(6) as ex:
            rows = list(ex.map(job, cases, chunksize=4))
        if len(argv) > 2:
            with open(argv[2], "w", encoding="utf-8") as f:
                f.writelines(json.dumps(r) + "\n" for r in rows)
        print(
            dict(Counter(r["status"] for r in rows).most_common()),
            "unsound moves:",
            sum(r.get("unsound", 0) for r in rows),
        )
    elif cmd == "show":
        code, n = argv[2], int(argv[3]) if len(argv) > 3 else 5
        for case in (c for c in cases if c["code"] == code):
            if n <= 0:
                break
            if job(case)["status"] not in ("missing", "union"):
                continue
            n -= 1
            mv, sol = moves(case)
            want = sorted(f"{_rc(x)}-{d}" for d, x in case["elims"]) or sorted(
                f"{_rc(x)}={d}" for d, x in case["places"]
            )
            p, mask = state(case)
            bad = [f"{_rc(x)}-{sol[x]}" for x in range(81) if not mask[x] >> (sol[x] - 1) & 1]
            print(f"{code}-{case['variant']}: want {want}")
            print(f"  ours: {[(m['code'], sorted(_rc(a) + '-' + str(b) for a, b in m['elim'])[:4]) for m in mv][:4]}")
            if bad:
                print(f"  position inconsistent with the solution: {bad}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
