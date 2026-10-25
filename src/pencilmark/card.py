"""Human-readable grade card: a label, two numbers, and a row of technique chips.

  card = grade_card(puzzle, P)        # uniqueness-checked (metrics.grade_puzzle_checked)
  print(card_text(card)); html = card_html(card)

  label        family tier of the REQUIRED strategies (metrics.family_tier), with its meaning
  difficulty   level of the hardest insight (+ amount of hard reasoning), the difficulty head
  tediousness  routine work in minutes (scoring.work_time: every move priced as a Hidden Single)
  chips        3-letter technique codes, Stuart's (sudokuwiki solver) where he has the strategy and
               consistent new codes otherwise; shade = family (darker = harder); "x2" = forced
               twice (steps where nothing from an easier family was available)
"""
import math
from collections import Counter

from . import metrics as MT, solver as S

# technique name -> (code, display name); sudokuwiki codes where they exist
CODES = {
    "FullHouse": ("FHS", "Full House"),
    "NakedSingle(direct)": ("NSI", "Naked Single"), "NakedSingle(notes)": ("NSI", "Naked Single"),
    "HiddenSingle(direct)": ("HSI", "Hidden Single"), "HiddenSingle(notes)": ("HSI", "Hidden Single"),
    "NakedSingle+Pointing(direct)": ("PPR", "Pointing Pair (in the head)"),
    "HiddenSingle+Pointing(direct)": ("PPR", "Pointing Pair (in the head)"),
    "LockedCandidates": ("PPR", "Pointing / Box-Line Reduction"),
    "MentalSingle(direct)": ("MSI", "Pair / triple in the head"), "MentalNotesSingle": ("MSI", "Notes in the head"),
    "NakedPair": ("NPR", "Naked Pair"), "HiddenPair": ("HPR", "Hidden Pair"),
    "NakedTriple": ("NTR", "Naked Triple"), "HiddenTriple": ("HTR", "Hidden Triple"),
    "NakedQuad": ("NQD", "Naked Quad"), "HiddenQuad": ("HQD", "Hidden Quad"),
    "X-Wing": ("XWG", "X-Wing"), "Swordfish": ("SWF", "Swordfish"), "Jellyfish": ("JLF", "Jellyfish"),
    "FinnedFish": ("FXW", "Finned X-Wing"), "XY-Wing": ("YWG", "Y-Wing"), "XYZ-Wing": ("XYZ", "XYZ-Wing"),
    "WXYZ-Wing": ("WXZ", "WXYZ-Wing"), "UniqueRectangle": ("URC", "Unique Rectangle"), "BUG+1": ("BUG", "BUG"),
    "GurthSymmetry": ("GSY", "Gurth's Symmetry"),
    "Coloring": ("SCL", "Simple Colouring"), "MultiColouring": ("MCL", "Multi-Colouring"),
    "X-Chain": ("XCL", "X-Chain"), "XY-Chain": ("XYC", "XY-Chain"), "RemotePairs": ("RMP", "Remote Pairs"),
    "EmptyRectangle": ("ERE", "Empty Rectangle"), "AIC": ("AIC", "Alternating Inference Chain"),
    "NiceLoop(discontinuous)": ("NLP", "Nice Loop"), "ChuteRemotePairs": ("CRP", "Chute Remote Pairs"),
    "3DMedusa": ("3DM", "3D Medusa"), "MentalChain(direct)": ("MCH", "Short chain in the head"),
    "ColourAlgebra": ("CAL", "Equal-digit colouring"),
    "ALS-XZ": ("ALS", "ALS-XZ (almost locked sets)"), "ALS-XY-Wing": ("AXY", "ALS-XY-Wing"), "ALS-AIC": ("AAC", "ALS chain"),
    "DeathBlossom": ("DEB", "Death Blossom"), "SueDeCoq": ("SDC", "Sue de Coq"), "AlignedPairExclusion": ("APE", "Aligned Pair Exclusion"),
    "ShortTrial": ("STR", "Short trial"), "EitherWay": ("EWY", "Either way (case split)"), "WhatIf": ("WIF", "What if…"),
    "ForcingChains": ("FCH", "Forcing Chains"), "DynamicForcingChains": ("FNT", "Forcing Nets"),
    "NestedForcingChains": ("NFC", "Nested Forcing Chains"), "NishioForcingNet": ("NIS", "Nishio"),
    "PatternOverlay": ("POM", "Pattern Overlay"), "Trial": ("TRL", "Trial and error"), "Guess": ("GSS", "Guess"),
    # variant logic: named after the rule the solver sees on the grid
    "ConstraintSingle(direct)": ("CSI", "Last cell of a cage / line"),
    "LineSingle(direct)": ("LSI", "Line / dot read without notes"),
    "CageCombination": ("CGC", "Killer cage combinations"), "SumCombination": ("SUM", "Sum clue combinations"),
    "ArrowCombination": ("ARW", "Arrow sums"), "SetCombination": ("RNB", "Renban runs"),
    "EqualSumCombination": ("EQS", "Equal sums (zipper / region-sum lines)"),
    "TableCombination": ("TBL", "Allowed combinations of a rule"),
    "SandwichCombination": ("SWC", "Sandwich sums"), "XSumCombination": ("XSC", "X-Sums"),
    "SkyscraperCombination": ("SKC", "Skyscraper clues"), "CountCombination": ("CNT", "Counting clues"),
    "ComboLock": ("CBL", "Must-contain digits (cage / line)"),
    "PairwiseConstraint": ("PWC", "Pair rules (dots, whispers, anti-knight...)"),
    "Innie/Outie(direct)": ("IOU", "Innies & outies (rule of 45)"),
    "Innie/Outie(notes)": ("IOV", "Innies & outies as a virtual cage"),
    "Innie/Outie(sum)": ("IOM", "Innies & outies over several houses"),
    "LawOfLeftovers": ("LOL", "Set theory (law of leftovers)"),
    "ImpliedHouses": ("IMH", "Hidden regions (implied houses)"),
    "LineRange": ("LNR", "Line ranges (thermo / whisper bounds)"),
    "LineClass": ("LNC", "Line classes (low/high, odd/even)"), "LineScan": ("LNS", "Local line scan"),
    "DigitCount": ("DGC", "Digit counting"), "EqualDigits": ("EQD", "Equal cells (same digit)"),
    "SumBound": ("SBD", "Min/max sum bounds"), "ClassCount": ("CLC", "Odd/even & high/low counting"),
    "Domino": ("DOM", "Domino pairs (dots / XV)"),
    "RuleIntersection": ("RUL", "Two rules together"), "BandLogic": ("BAN", "Band set theory with cages"),
    "Fireworks": ("FIR", "Fireworks"), "SumAlgebra": ("SAL", "Sum algebra (house totals)"),
    "WeightedSums": ("WEI", "Weighted sums"), "ComboPositions": ("CPS", "Cage combination positions"),
    "CliqueHouse": ("CLI", "Clique house (all-different cells)"), "LineSets": ("RNS", "Renban sets in a house"),
    "LineClues": ("OCL", "Outside clues together"),
    "SnyderMarks": ("SNY", "Snyder notation (box pairs)"), "SnyderSingle": ("SNY", "Snyder notation (box pairs)"),
    "CaseAnalysis": ("CAS", "Case analysis"),
}
ICONS = {"difficulty": "◆", "tediousness": "⏱"}


def _code(name):
    if name in CODES:
        return CODES[name]
    return (("".join(ch for ch in name if ch.isalpha()).upper() + "XXX")[:3], name)


def forced_counts(steps):
    """technique name -> number of steps where it was chosen and nothing from an easier family was available."""
    out = Counter()
    for st in steps:
        t = st.move.feat[0]
        if t in getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,)):
            continue
        fam = MT.family_of(t)
        avail = [MT.family_of(f[0]) for f in st.alts if f[0] != S.TAKE_NOTES]
        if fam > 0 and avail and min(avail) >= fam:
            out[S.TECH_NAMES[t]] += 1
    return out


_V2 = None


_LAST_EFFORT = None


def _score_v2(puzzle):
    """Card score (pencilmark/card_score.py, configured by data/card_score.json); None if unavailable. Also leaves the
    effort L1 (log step-value sum, read by the time model) in _LAST_EFFORT."""
    global _V2, _LAST_EFFORT
    from . import _data
    if _V2 is None:
        _V2 = _data.load_json("card_score.json") if _data.exists("card_score.json") else {}
    if not _V2 or _V2.get("version") != 3:
        return None
    from . import card_score as C3
    r = C3.score_parts(puzzle, _V2)
    _LAST_EFFORT = None if r is None else r[1]
    return None if r is None else r[0]


def specific_names(puzzle, steps):
    """engine technique name -> Counter of the explainer's most specific pattern names on its steps
    (only where that name is more specific than the technique's own display name)."""
    from . import explain as E
    out = {}
    hard = {i for i, st in enumerate(steps) if MT.family_of(st.move.feat[0]) > 0 and st.move.feat[0] != S.GUESS}
    if not hard:
        return out
    for i, step, state in E.replay(puzzle, steps):
        if i not in hard:
            continue
        try:
            nm = E.explain(step, puzzle, state)["technique"]["name"]
        except Exception:
            continue
        tn = S.TECH_NAMES[step.move.feat[0]]
        if nm and nm != _code(tn)[1]:
            out.setdefault(tn, Counter())[nm] += 1
    return out


def grade_card(puzzle, P, specific=True, check_rules=True, band=None):
    g = MT.grade_puzzle_checked(puzzle, P, tier_by_family=band is None)   # band given -> no second deletion test in report()
    if g["status"] not in ("ok",) and not g.get("report"):
        return {"status": g["status"]}
    steps = g["steps"]
    if band is not None:     # 2026-10-22 speed: band + techniques from the band path (the user-facing notion) -- skips the
        tier, req = band     # strict-required deletion test (~45% of grading time on variants; dropped as user-facing 2026-10-15)
    else:
        tier, req = MT.band_label(puzzle, P)      # user's six bands (Very Easy .. Extreme) from required techniques
    req = [S.TECH_NAMES.get(t, str(t)) if isinstance(t, int) else t for t in (req or [])]
    forced = forced_counts(steps)
    notes = getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,))
    used = Counter(S.TECH_NAMES[st.move.feat[0]] for st in steps if st.move.feat[0] not in notes)
    rev = {v: k for k, v in S.TECH_NAMES.items()}
    singles = [n for n in used if MT.family_of(rev[n]) == 0]          # the base everyone uses
    names = list(dict.fromkeys((req or []) + singles))
    chips, seen = [], {}
    for n in names:
        code, disp = _code(n)
        fam = MT.band_of(rev.get(n, 0))
        k = (code, fam)
        if k in seen:
            seen[k]["forced"] += forced.get(n, 0)
            continue
        chip = {"code": code, "name": disp, "family": MT.BANDS[fam], "family_i": fam,
                "shade": round(fam / (len(MT.BANDS) - 1), 2), "forced": forced.get(n, 0), "required": n in (req or [])}
        seen[k] = chip
        chips.append(chip)
    chips.sort(key=lambda c: (c["family_i"], c["code"]))
    if specific:   # most specific name of what was actually seen (Skyscraper, W-Wing, Sashimi Swordfish, ...)
        for n, names_ in specific_names(puzzle, steps).items():
            code, _ = _code(n)
            for c in chips:
                if c["code"] == code and names_:
                    c["specific"] = [k for k, _ in names_.most_common()]
    lvl = g["report"]["level"]
    gi = [i for i, st in enumerate(steps) if st.move.feat[0] == S.GUESS]
    if gi:   # a guess is not a grade: report what the engine could do and where it ran out of logic
        pre = steps[:gi[0]]
        band = max((MT.band_of(st.move.feat[0]) for st in pre if st.move.feat[0] not in getattr(S, "NOTE_TECHS", (S.TAKE_NOTES,))), default=0)
        human = (P or {}).get("search") == "human"
        # no available technique can continue: we can't grade it (user: rate what we can't solve as unknown)
        return {"status": "beyond human logic" if human else "beyond engine", "label": "Unknown",
                "meaning": f"no {'human' if human else 'logical'} step found after {len(pre)} of {len(steps)} steps "
                           f"({100 * len(pre) // max(len(steps), 1)}% of the solve); grade unknown",
                "difficulty": None, "tediousness_min": None, "think_min": None,
                "chips": [c for c in chips if c["code"] != "GSS"], "guess_at": len(pre)}
    global _LAST_EFFORT
    _LAST_EFFORT = None
    sc_ = _score_v2(puzzle)          # Stuart-form score on the written route (data/card_score.json)
    effort_ = _LAST_EFFORT
    if sc_ is None:
        sc_ = MT.card_score(MT.size_normalised(MT.difficulty_grade(steps, P, cap=False, head=False), puzzle.D, P))
    sc_ = round(sc_, 1) if sc_ is not None else None
    nf = sum(forced.values())
    # Stuart-style publishing notes, hand-coded common sense (pencilmark/publish_flags.py); bands stay fixed
    from . import publish_flags as PF
    wm = g["grade"]["work_time"] / 60 if g.get("grade") else None
    pnotes = PF.notes(puzzle, P, steps, tier, forced, req, wm, check_rules=check_rules)
    flags = [("would not be chosen for publishing: " if sev == "reject" else "note: ") + txt for code, sev, txt, *_ in pnotes]
    shape = "singles only" if nf == 0 else ("spike" if nf <= 2 else "sustained")   # balance: label resting on 1-2 forced steps
    from .scoring import time_grade
    tg = time_grade(steps, puzzle, P)
    real = [st for st in steps if st.move.feat[0] not in notes]
    hardest = [{"technique": S.TECH_NAMES[st.move.feat[0]], "price": round(st.move.d, 2), "step": i + 1,
                "place": (f"r{puzzle.coords[st.move.place[0]][0] + 1}c{puzzle.coords[st.move.place[0]][1] + 1}={st.move.place[1]}"
                          if st.move.place else None)}
               for i, st in sorted(enumerate(real), key=lambda x: -x[1].move.d)[:3]]
    return {"status": g["status"], "label": tier, "meaning": MT.BAND_MEANING.get(tier, ""), "balance": shape, "forced_total": nf,
            "time_grade": tg, "techniques": dict(used.most_common()), "hardest_steps": hardest, "n_steps": len(real),
            "score": sc_, "effort_l1": round(effort_, 3) if effort_ is not None else None, "score_fit": MT.score_fit(MT.BANDS.index(tier), sc_) if (sc_ is not None and tier in MT.BANDS) else "",
            "flags": flags, "difficulty": round(lvl, 1), "tediousness_min": round(g["grade"]["work_time"] / 60, 1),
            "think_min": round(g["grade"]["think_time"] / 60, 1), "chips": chips, "_notes_raw": pnotes}


def card_text(card):
    if "label" not in card:
        return f"[{card.get('status')}]"
    chips = " ".join(c["code"] + (f"×{c['forced']}" if c["forced"] > 1 else "") for c in card["chips"])
    if card.get("status") == "beyond engine":
        return f"{card['label']:10s} ? (beyond engine at step {card['guess_at']})   {chips}"
    sc = card.get("score")
    return (f"{card['label']:9s} {ICONS['difficulty']} {sc if sc is not None else card['difficulty']:4.1f}  {ICONS['tediousness']} {card['tediousness_min']:5.1f} min  "
            f"[{card.get('balance', '')}{', ' + card['score_fit'] if card.get('score_fit') else ''}]  {chips}"
            + ("".join(f"\n   ! {x}" for x in card.get("flags", []))))


def card_html(card):
    """Inline HTML snippet: label, two metrics, shaded chips (darker = harder family)."""
    if "label" not in card:
        return f"<span class='card'>{card.get('status')}</span>"
    def chip(c):
        light = 92 - int(62 * c["shade"])
        fg = "#fff" if light < 55 else "#222"
        x = f"<sub>×{c['forced']}</sub>" if c["forced"] > 1 else ""
        return (f"<span title='{c['name']} ({c['family']})' style='background:hsl(215,35%,{light}%);color:{fg};"
                f"font:600 11px ui-monospace,monospace;padding:2px 5px;border-radius:4px;margin-right:3px'>{c['code']}{x}</span>")
    return (f"<span class='card'><b>{card['label']}</b> &nbsp;{ICONS['difficulty']} {card.get('score') if card.get('score') is not None else card['difficulty']} &nbsp;"
            f"{ICONS['tediousness']} {card['tediousness_min']} min &nbsp;" + "".join(chip(c) for c in card["chips"]) + "</span>")
