"""The technique registry (pencilmark/registry.py; data/techniques.csv, codes.csv, patterns.csv) is complete and agrees
with the engine: every technique has the facts the grader needs, every code a route step can carry has a name, a band
and a Sudoku Explainer rating. Fast: nothing is graded."""

import re
from pathlib import Path

import pytest

from pencilmark import band_path as BP
from pencilmark import export as E2
from pencilmark import registry as R
from pencilmark import solver as S

T = R.techniques()
C = R.codes()
HEADER = Path(__file__).resolve().parents[1] / "csrc" / "solver.hpp"


def test_rows_unique():
    for key in ("id", "const", "name"):
        vals = [getattr(t, key) for t in T]
        assert len(vals) == len(set(vals)), f"techniques.csv: duplicate {key}"
    assert len({p.cpp_code for p in R.patterns()}) == len({p.engine_code for p in R.patterns()}) == len(R.patterns())


def test_python_constants_match():
    assert {t.const: t.id for t in T} == {t.const: getattr(S, t.const) for t in T}


@pytest.mark.skipif(not HEADER.is_file(), reason="needs the source tree (csrc/solver.hpp)")
def test_engine_enum_matches():
    """csrc/solver.hpp enum Tech and is_direct() say what techniques.csv says."""
    src = HEADER.read_text(encoding="utf-8")
    enum = re.search(r"enum Tech \{(.*?)\};", src, re.S).group(1)
    enum = re.sub(r"//[^\n]*", "", enum)
    ids = {k: int(v) for k, v in re.findall(r"\b([A-Z][A-Z0-9_]*)\s*=\s*(\d+)", enum) if k != "N_TECH"}
    assert ids == {t.const: t.id for t in T}
    body = re.search(r"inline bool is_direct\(int t\) \{(.*?)\}", src, re.S).group(1)
    assert set(re.findall(r"t == ([A-Z_]+)", body)) == {t.const for t in T if t.direct}


def test_every_technique_has_its_facts():
    names = R.by_name()
    for t in T:
        if t.role == "logic":
            assert t.code and t.band is not None and t.family, f"{t.name}: logic needs code, band, family"
        else:
            assert not t.family and not t.gate and t.simplicity is None, f"{t.name}: a {t.role} row is not priced"
        if t.code:
            assert t.display or t.code in C, f"{t.name}: code {t.code} has no name (codes.csv) and no display"
        if t.split:
            assert C[t.code].shape_band is not None, f"{t.name}: split, so {t.code} needs a shape_band"
        if t.price_fallback:
            fb = names.get(t.price_fallback)
            assert fb and not fb.price_fallback, f"{t.name}: price_fallback must name a technique with its own price"


def _shape_codes():
    """every code export._shape can give a split technique's step"""
    out = set()
    for name in ("X-Chain", "X-Wing", "FinnedFish", "LawOfLeftovers"):
        for specific in list(E2.X_CHAIN_SHAPES) + [
            "x-chain",
            "franken x-wing",
            "mutant swordfish",
            "finned x-wing",
            "sashimi swordfish",
            "finned jellyfish",
            "phistomefel ring",
            "phistomefel variant",
            "set theory",
        ]:
            sh = E2._shape(name, specific)
            if sh:
                assert sh[1] is not None, (name, specific, sh)
                out.add(sh[0])
    return out


def test_route_codes_complete():
    """the codes a route step can carry: technique chips, pattern codes, shape codes -- each has a name, a band and an
    SE rating (a number, or "-": SE has no such technique), and codes.csv lists nothing else"""
    tech = {t.code: t.band for t in T if t.role == "logic"}
    route = set(tech) | {p.code for p in R.patterns() if p.code} | _shape_codes() | {"SWF", "FRK"}
    assert route == set(C), f"carried but missing: {route - set(C)}; listed but never carried: {set(C) - route}"
    for code, c in C.items():
        assert c.name, code
        assert c.shape_band is not None or tech.get(code) is not None, f"{code}: no band"
        assert all(s in C for s in c.subset_of), f"{code}: subset_of names an unknown code"


def test_patterns_point_at_split_techniques():
    names = R.by_name()
    for p in R.patterns():
        if p.code:
            assert p.code in C and names[p.technique].split and p.step_name, p
    assert {c for c, _, _ in BP._X_CHAIN.values()} <= set(C)


USAGE = Path(__file__).resolve().parents[1] / "docs" / "USAGE.md"


@pytest.mark.skipif(not USAGE.is_file(), reason="needs the source tree (docs/USAGE.md)")
def test_usage_code_table_matches():
    """docs/USAGE.md's code table: every code, with its band and what it is a special case of"""
    tech = {}
    for t in T:
        if t.code and t.band is not None:
            tech.setdefault(t.code, t.band)
    doc = {}
    for line in USAGE.read_text(encoding="utf-8").splitlines():
        f = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(f) == 4 and re.fullmatch(r"[A-Z0-9]{3}", f[0]):
            doc[f[0]] = (f[2], f[3])
    want = {}
    for code, c in C.items():
        band = c.shape_band if c.shape_band is not None else tech[code]
        want[code] = (R.BANDS[band], ", ".join(sorted(BP.SUPERSETS.get(code, ()))))
    assert doc == want


def test_se_rates_the_codes_se_knows():
    """a code Sudoku Explainer rates gets its rating, not the 7.0 of 'SE has no such technique' (se.CLASSIC was once
    keyed by codes no route step carries, so every card's ER was 7.0)"""
    from pencilmark import se as SE

    se_names = "FHS HSI NSI PPR NPR HPR NTR HTR NQD HQD XWG SWF JLF YWG XYZ URC BUG SKY KTE TUR ERE XCL FXW FCH FNT"
    assert [c for c in se_names.split() if c not in SE.CLASSIC] == []
    singles = [{"code": "HSI", "place": (0, 1)}, {"code": "FHS", "place": (1, 2)}]
    assert SE.ratings(singles) == {"er": 1.2, "ep": 1.2, "ed": 1.2, "scale": "classic"}


def test_generator_bands_match_the_route():
    """the generator plans with the same band per code as the route grades (FRK / FSW / FJF / XCL were off by one)"""
    from pencilmark import registry
    from pencilmark.gen import api as G

    known = G._known_codes()
    assert {
        c: k.shape_band
        for c, k in registry.codes().items()
        if k.shape_band is not None and known.get(c) != k.shape_band
    } == {}
