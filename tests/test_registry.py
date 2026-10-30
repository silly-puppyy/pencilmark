"""The technique registry (pencilmark/registry.py, data/techniques.csv / codes.csv / patterns.csv): the tables the
modules derive from it equal the literal tables they replace. Fast: nothing is graded."""

from pencilmark import band_path as BP
from pencilmark import card as K
from pencilmark import cbackend as CB
from pencilmark import explain as EX
from pencilmark import export as E2
from pencilmark import metrics as MT
from pencilmark import registry as R
from pencilmark import scoring as SC
from pencilmark import se as SE
from pencilmark import solver as S

T = R.techniques()


def test_solver_tables():
    assert {t.id: t.name for t in T} == S.TECH_NAMES
    assert all(getattr(S, t.const) == t.id for t in T)
    assert {t.id for t in T if t.direct} == S.DIRECT_TECHS
    assert tuple(sorted(t.id for t in T if t.role == "notes")) == S.NOTE_TECHS


def test_metrics_tables():
    fams = [(f, [t.id for t in T if t.family == f]) for f in R.FAMILIES]
    assert fams == MT.FAMILIES  # lists in order: ties in the required-technique search follow it
    assert {t.name: t.simplicity for t in T if t.simplicity is not None} == MT.SIMPLICITY
    assert {t.name: t.band for t in T if t.band is not None} == MT._BAND_BY_NAME
    assert R.BANDS == MT.BANDS == E2.BANDS


def test_card_codes():
    assert {t.name: R.chip(t) for t in T if t.code} == K.CODES


def test_scoring_flags():
    assert {t.id for t in T if t.price_fallback} == SC.STRUCTURAL_ONLY
    trial = tuple(t.id for t in T if t.family == "trial")
    assert trial == SC.TRIAL_FAMILY_META_EXCLUDE


def test_band_path_tables():
    assert sorted(t.name for t in T if t.gate == "any") == sorted(BP.VARIANT_ANY)
    assert sorted(t.name for t in T if t.gate == "sum") == sorted(BP.VARIANT_SUM)
    assert {t.name for t in T if t.split} == set(E2.SPLIT)
    assert {n: R.by_name()[n].band for n in E2.SPLIT} == E2.SPLIT_LOW
    C = R.codes()
    assert {c: C[c].order for c in C} == {c: float(BP._order(c)) for c in C}
    assert {c: list(v.subset_of) for c, v in C.items() if v.subset_of} == BP.SUBSET
    xc = {p.engine_code: (p.code, p.step_name, C[p.code].shape_band) for p in R.patterns() if p.technique == "X-Chain"}
    assert xc == BP._X_CHAIN


def test_export_tables():
    assert {c: v.name for c, v in R.codes().items()} == E2.code_names()
    shapes = {p.step_name.lower(): p.code for p in R.patterns() if p.technique == "X-Chain" and p.code != "XCL"}
    assert list(shapes.items()) == list(E2.X_CHAIN_SHAPES.items())


def test_se_tables():
    C = R.codes()
    classic = {c: v.se_classic for c, v in C.items() if v.se_classic is not None}
    diuf = {c: v.se_diuf if v.se_diuf is not None else v.se_classic for c, v in C.items() if v.se_classic is not None}
    unreachable = set(SE.CLASSIC) - set(C)  # keyed by codes no route step carries: never looked up
    assert unreachable == {"FSH", "JFH", "NET", "UR1", "URX", "WWG", "XCH", "XYW"}
    assert classic == {c: v for c, v in SE.CLASSIC.items() if c in C}
    assert diuf == {c: v for c, v in SE.DIUF.items() if c in C}


def test_pattern_tables():
    assert {p.cpp_code: p.engine_code for p in R.patterns()} == CB.CHAIN_CODES
    assert {p.engine_code: p.explain_name for p in R.patterns() if p.explain_name} == EX._PATTERN_NAMES
    assert {p.engine_code: p.catalog_key for p in R.patterns() if p.catalog_key} == EX._CODE_KEY
