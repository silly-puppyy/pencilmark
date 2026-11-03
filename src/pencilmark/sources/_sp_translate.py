"""SudokuPad puzzle JSON -> engine Puzzle.

Element conventions (SudokuPad, coordinates [row, col] in cell units):
  cells[r][c].value      givens        regions        boxes / irregular regions
  cages {cells, value}   killer cages  (metadata cages carry title/rules)
  lines {wayPoints, color, thickness}   thermo / whisper / renban / region-sum /
                                        palindrome / entropic / arrow shafts ...
  underlays/overlays     circles (thermo bulbs, arrow circles, odd), squares (even),
                         small dots on edges (kropki), letters (XV), clue text
  arrows                 arrow heads (arrow sudoku), little-killer arrows
The rules text decides what a coloured line means ("green lines are German
whispers"); hex colours are mapped to colour names; unresolved lines fall
back to SudokuPad's default palette. Rules the grader can't model yet make
the translation fail loudly (reason recorded) instead of guessing.
Output schema: engine Puzzle with relations / groups / domains /
p.constraints (sum, arrow, equal_sum, set, table, line, little_killer,
sandwich, xsum, skyscraper).
Negative constraints are per marker type (white / black kropki, X, V), read
from the rules text by negative_markers(); infer() also tries none / per
family / all.
"""

import colorsys
import logging
import math
import re
from collections import defaultdict

from .. import model as M

_log = logging.getLogger(__name__)

# mechanics the engine does not model, named in a rules text: the reader refuses the puzzle rather than read its elements
# as something else (an equality cage drawn as a cage would grade as a killer cage). Both readers check these.
UNMODELLED_RULES = (
    ("fog", r"fog"),
    ("chaos", r"chaos"),
    ("yin", r"yin"),
    ("modifier", r"modifier"),
    ("doubler", r"doubler"),
    ("minesweeper", r"minesweeper"),
    ("fillomino", r"fillomino"),
    ("clone", r"clone"),
    ("loop", r"loop"),
    ("snake", r"snake"),
    ("slitherlink", r"slitherlink"),
    ("star battle", r"star battle"),
    ("nurikabe", r"nurikabe"),
    ("cave", r"cave"),
    ("indexing", r"indexing"),
    ("ten line", r"ten[- ]line"),
    ("10 line", r"10[- ]line"),
    ("broken zipper", r"broken zipper"),
    (
        "anti line",
        r"\banti[- ](?:renban|german whisper|whisper|palindrom|thermo|zipper|region[- ]sum|entropic|modular|parity)",
    ),
    # the newer entries want the mechanic defined ("equality cages: ..."), not only named: pages list an author's other
    # series and the solvers' names (checked on the 28,333 logic-masters sudoku texts)
    ("look-and-say", r"look[- ]and[- ]say (?:cage|line|clue)"),
    ("equality cage", r"equa(?:lity|lite) cages?\s*(?::|must|have|contain|are)"),
    ("rellik", r"\brellik cage"),
    ("counting cage", r"counting cages?\s*:"),
    ("congruent", r"\bcongruent (?:boxes|regions|cages)"),
    ("camel", r"\b(?:anti-?)?camels?\b"),
    ("pointer", r"\bpointe(?:r|ing) (?:arrows?|thermos?)\s*(?::|constraint)"),
    ("indexer", r"\bindex(?:er)? line|\bindexers?\b"),
    ("cold / hot arrow", r"\b(?:cold|hot) arrows?\s*:"),
    ("pairrow", r"\bpai?rrows?\s*[:-]|(?:all|not all)(?: possible)? pai?rrows"),
    ("screw", r"region sum screws?\s*:"),
    # a puzzle-wide unknown: the digits sorted into sets the solver finds ("sort the digits 1-9 into three sets of three")
    ("digit sets", r"(?:sort|divide|split|partition|separate)s? the digits[^.]{0,40}\binto\b[^.]{0,40}\bsets?\b"),
    ("diagonal kropki", r"diagonal kropki(?: dots?)?\s*:|diagonally connected by an? (?:black|white)"),
)


def unmodelled_rules(text, chaos_ok=False):
    """the mechanics of UNMODELLED_RULES a (lower-case) rules text names, as refusal reasons; chaos_ok: the reader
    models chaos construction itself (SudokuPad, regions to find)"""
    return [
        f"rule '{label}'"
        for label, rx in UNMODELLED_RULES
        if re.search(rx, text) and not (chaos_ok and label == "chaos")
    ]


# chaos construction (format 6.3): the rules say the solver finds the regions; read only when the file draws none
CHAOS_TEXT = re.compile(
    r"chaos construction|divide the grid into (?:\w+ )?(?:orthogonally[- ])?(?:connected )?regions"
    r"|regions?[^.]{0,40}(?:must be|are to be|have to be|to be) (?:determined|located|found|deduced) by the solver"
    r"|the solver (?:must|has to|needs to) (?:determine|locate|find) (?:the )?regions"
)
# element kinds whose cells lie in one region / straddle a border, said explicitly ("digits along a thermometer belong
# to the same region"); counting or seeing rules that merely mention regions are other mechanics and are refused
REGION_VERB = r"(?:belong to|belongs to|lie in|lies in|are in|is in|stay in|stays in|located in)"
REGION_KINDS = (
    ("thermo", r"thermo", ("lt", "le")),
    ("black", r"black (?:dot|kropki|circle)", ("ratio",)),
    ("white", r"white (?:dot|kropki|circle)", ("diff",)),
    ("x", r"\bxs?\b(?! ?-)", ("sum10",)),
    ("v", r"\bvs?\b", ("sum5",)),
    ("cage", r"cage", ("cage",)),
)


def region_statements(text):
    """element kind -> True (its cells share a region) / False (they lie in different regions)"""
    out = {}
    for sent in re.split(r"(?<=[.!\n])\s*", (text or "").lower()):
        if "region" not in sent:
            continue
        diff = re.search(
            rf"{REGION_VERB} (?:two )?different regions|(?:do not|does not|don't|never|cannot|can't) {REGION_VERB} "
            r"(?:the )?same region|cross(?:es)? a region border|separated by a region border",
            sent,
        )
        same = re.search(rf"{REGION_VERB} (?:the )?(?:same|one|a single) region", sent)
        if diff or same:
            for kind, pat, _ in REGION_KINDS:
                if re.search(pat, sent):
                    out[kind] = not diff
    return out


def chaos_rules(P, p, n, rules):
    """the chaos constraint, drawn borders (dark lines along grid lines) and the region statements of the rules text,
    as engine constraints"""
    idx = {rc: i for i, rc in enumerate(p.coords)}
    cons = [{"type": "chaos", "cells": list(range(n * n))}]
    borders = set()
    for ln in P.get("lines") or []:
        wp = [w for w in (ln.get("wayPoints") or []) if w]
        col = str(ln.get("color", "")).lower()
        if not wp or color_name(col) != "black" or any(abs(v - round(v)) > 0.01 for w in wp for v in w):
            continue
        for (y1, x1), (y2, x2) in zip(wp, wp[1:]):
            y1, x1, y2, x2 = map(round, (y1, x1, y2, x2))
            if x1 == x2:
                for y in range(min(y1, y2), max(y1, y2)):
                    if (y, x1 - 1) in idx and (y, x1) in idx:
                        borders.add((idx[(y, x1 - 1)], idx[(y, x1)]))
            elif y1 == y2:
                for x in range(min(x1, x2), max(x1, x2)):
                    if (y1 - 1, x) in idx and (y1, x) in idx:
                        borders.add((idx[(y1 - 1, x)], idx[(y1, x)]))
    same = []
    kinds = {k: rels for k, _, rels in REGION_KINDS}
    for kind, is_same in region_statements(rules).items():
        pairs = []
        for r in p.relations:
            k = r[0] + (str(r[3]) if r[0] == "sum" and len(r) > 3 else "")
            if k in kinds[kind]:
                pairs.append((r[1], r[2]))
        if "cage" in kinds[kind]:
            pairs += [(a, b) for g in p.groups if g.kind == "cage" for a, b in zip(g.cells, g.cells[1:])]
        for a, b in pairs:
            if is_same:
                same.append([a, b])
            elif abs(p.coords[a][0] - p.coords[b][0]) + abs(p.coords[a][1] - p.coords[b][1]) == 1:
                borders.add((min(a, b), max(a, b)))
    cons += [{"type": "region_border", "cells": [a, b]} for a, b in sorted(borders)]
    cons += [{"type": "same_region", "cells": s} for s in same]
    return cons


RULE_WORDS = {
    "slow_thermo": [r"slow[- ]?thermo"],
    "thermo": [r"thermo"],
    "whisper": [r"german whisper", r"whisper"],
    "dutch": [r"dutch whisper"],
    "renban": [r"renban"],
    "region_sum": [r"region[- ]sum"],
    "palindrome": [r"palindrom"],
    "entropic": [r"entrop"],
    "arrow": [r"\barrow"],
    "between": [r"between line"],
    "zipper": [r"zipper"],
    "same_parity": [r"same parity", r"all (?:be )?odd or (?:must )?all (?:be )?even"],  # before parity: alternating
    "parity": [r"parity line"],
    "modular": [r"modular"],
    "nabner": [r"nabner"],
    "lockout": [r"lockout"],
    "ten": [r"10[- ]line", r"ten[- ]line"],
}
COLOR_WORDS = [
    "green",
    "purple",
    "pink",
    "magenta",
    "blue",
    "cyan",
    "teal",
    "red",
    "orange",
    "yellow",
    "grey",
    "gray",
    "black",
    "white",
    "brown",
    "violet",
    "lavender",
    "turquoise",
    "peach",
    "lime",
    "gold",
    "golden",
    "beige",
    "olive",
    "amber",
    "khaki",
    "navy",
    "aqua",
    "salmon",
    "indigo",
    "maroon",
    "crimson",
]
# reference hues for colour words in rules text (lines are matched to the nearest named colour)
COLOR_HUES = {
    "red": 0,
    "orange": 30,
    "peach": 25,
    "yellow": 55,
    "lime": 90,
    "green": 120,
    "teal": 175,
    "turquoise": 175,
    "cyan": 185,
    "blue": 220,
    "purple": 275,
    "violet": 275,
    "lavender": 270,
    "magenta": 300,
    "pink": 320,
    "gold": 48,
    "golden": 48,
    "amber": 42,
    "beige": 40,
    "brown": 28,
    "tan": 34,
    "khaki": 54,
    "olive": 62,
    "navy": 230,
    "aqua": 180,
    "mint": 150,
    "rose": 340,
    "salmon": 8,
    "indigo": 260,
    "maroon": 350,
    "crimson": 350,
}
# empirical setter conventions (709 verified readings): green whisper 98%, pink renban 93%, cyan region sum 80%,
# orange dutch 79%, grey thermo 61% / palindrome 29%, red parity ~50%, purple zipper ~57%
DEFAULT_LINE = {
    "green": "whisper",
    "purple": "zipper",
    "pink": "renban",
    "magenta": "renban",
    "blue": "region_sum",
    "cyan": "region_sum",
    "grey": "thermo",
    "gray": "thermo",
    "orange": "dutch",
    "red": "parity",
}
# what a rules text says when it describes a default meaning without naming it ("a pink line holds consecutive digits");
# a default colour is used only when the text says this much (a line rule the engine does not know, drawn blue, read
# as a region sum: Quiet Room, 000TBF)
DEFAULT_EVIDENCE = {
    "whisper": r"whisper|(?:least|minimum difference of|difference of) (?:5|five)\b|\b(?:5|five) or (?:more|greater)",
    "zipper": r"zipper|equal(?:ly)? (?:distance|distant|far)|equidistant|cent(?:re|er)",
    "renban": r"renban|consecutive",
    "region_sum": r"region[- ]sum|\bsums?\b|\btotal",
    "thermo": r"thermo|increase|bulb",
    "dutch": r"dutch|(?:least|minimum difference of|difference of) (?:4|four)\b|\b(?:4|four) or (?:more|greater)",
    "parity": r"parity|\bodd\b.{0,40}\beven\b|\beven\b.{0,40}\bodd\b",
}


def color_name(hexcol):
    h = str(hexcol or "#000").lstrip("#")  # a colour typed without "#" (777777) can arrive as a JSON number
    if len(h) in (1, 2):  # newer files' grey shorthand: "#F" white, "#0" black, a second digit the alpha
        h = h[0] * 3 + h[1:]
    alpha = int(h[3] * 2, 16) / 255 if len(h) == 4 else int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    if len(h) in (3, 4):
        h = "".join(ch * 2 for ch in h[:3])
    h = h[:6]
    try:
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return "black"
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    hue *= 360
    if light > 0.92:
        return "white"
    if light < 0.12:
        return "grey" if alpha < 0.6 else "black"  # mostly transparent black (#0003) is drawn grey
    if sat < 0.18:
        return "grey"
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 45:
        return "orange"
    if hue < 70:
        return "yellow"
    if hue < 165:
        return "green"
    if hue < 200:
        return "cyan"
    if hue < 255:
        return "blue"
    if hue < 290:
        return "purple"
    return "pink"


# lexicon: phrasings for supported mechanics that never use the rule's name
DIFF_K = re.compile(
    r"differ(?:ence)?s?\b[^.]{0,25}?(at least|>=|≥|a minimum of|more than|greater than)\s*(?:a\s+)?(\d|five|four|three|two|six|seven)\b"
)
_NUMW = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
SLOW_ALL = re.compile(
    r"slow[- ]?thermo|never decrease|(?:can|may) (?:also )?repeat (?:on|along|in) (?:a |the |each )?thermo"
)
NO_BOXES = re.compile(
    r"(?:once|exactly once)(?: each)? in (?:every|each) row and (?:every |each )?column(?![^.]{0,40}(?:box|region|cage|block|nonet))"
    r"|no (?:3x3 )?box(?:es)?\b|(?:there are )?no boxes|without boxes"
)
QUAD_TEXT = re.compile(
    r"quadruple|(?:surrounding|touching|around|adjacent to)(?: the| that| this)? (?:four|4) cells|"
    r"(?:four|4) (?:surrounding|adjacent|touching) cells|"
    r"\bquads?\s*:|(?:four|4) cells (?:the|that|this|it) (?:circle )?touch|"  # "Quads: ..." (000RL6, 000QJZ)
    r"(?:digits?|numbers?) (?:in|inside) (?:a|the) circle[^.]{0,60}\bcells? touching"
)


def diff_rule(sent):
    """'adjacent digits differ by at least K' -> whisper key (K=5 whisper, K=4 dutch, else 'whisperK'), or None."""
    m = DIFF_K.search(sent)
    if not m:
        return None
    k = int(m.group(2)) if m.group(2).isdigit() else _NUMW[m.group(2)]
    k += m.group(1) in ("more than", "greater than")
    return {5: "whisper", 4: "dutch"}.get(k, f"whisper{k}")


# a line rule described without its name ("a purple line contains a set of consecutive digits"); counted only in a
# sentence about a line or thread, so a cage or dot described the same way does not colour a line
RULE_DESCRIPTIONS = {
    "renban": [r"set of (?:non-repeating,? )?consecutive", r"consecutive set",
               r"\b(?:are|be|contains?|form) (?:an? )?(?:non-repeating,? )?consecutive (?:digits|numbers|values|sequence)"],
    "region_sum": [r"segments? (?:that |which )?(?:each )?(?:sum|add)s? (?:up )?to the same", r"(?:same|equal) (?:sums?|totals?)",
                   r"sum (?:of the digits )?(?:on|along) (?:a|the|each) [a-z ]{0,20}line is (?:equal|the same)",
                   r"is (?:equal|the same) in (?:every|each) box"],
    "thermo": [r"increase from the bulb", r"from the bulb end"],
    "between": [r"(?:numerically|strictly) between", r"between the (?:two )?(?:digits|circles|numbers) (?:in|at) ",
                r"between (?:the )?(?:two )?(?:attached )?circles"],
    "palindrome": [r"reads? the same (?:forwards?|in both)", r"same (?:forwards?|from either end)"],
    "zipper": [r"equidistant from the (?:centre|center)", r"(?:same|equal) distance from the (?:centre|center)"],
}  # fmt: skip


# a region sum stated per box ("the same total in each 3x3 box the line visits"): a line that leaves a box and comes back
# then has one total for both visits, which the segment rule (box borders divide the line) does not model
RS_PER_BOX = re.compile(
    r"(?:in|within) each (?:3x3 )?box|each (?:3x3 )?box (?:it|the line|they|that it) (?:visits|passes)"
)


def _described(sent):
    """line rules one sentence describes without naming them: only a sentence about a line or thread, and a region sum
    only with the boxes in it ("lines of the same colour sum to the same total" is another rule)"""
    if not re.search(r"\b(?:lines?|threads?)\b", sent):
        return []
    got = [k for k, pats in RULE_DESCRIPTIONS.items() if any(re.search(p, sent) for p in pats)]
    return [k for k in got if k != "region_sum" or re.search(r"\bbox(?:es)?\b|3x3", sent)]


def described_line_rules(rules):
    """line rules the text describes without naming them, from sentences about a line or thread that name no colour
    (a puzzle with one line colour); empty when any line sentence names a colour"""
    out = set()
    for sent in re.split(r"(?<=[.\n])\s*", (rules or "").lower()):
        if re.search(r"\b(?:lines?|threads?)\b", sent) and any(re.search(rf"\b{c}", sent) for c in COLOR_WORDS):
            return set()
        if not any(re.search(p, sent) for pats in RULE_WORDS.values() for p in pats):
            out |= set(_described(sent))
    return out


def rules_color_map(rules):
    """colour word -> rule key, from sentences mentioning both."""
    out = {}
    text = (rules or "").lower()
    for sent in re.split(r"(?<=[.\n])\s*", text):
        rules_here = [k for k, pats in RULE_WORDS.items() if any(re.search(p, sent) for p in pats)]
        if not rules_here:
            rules_here = _described(sent)
        cols = [c for c in COLOR_WORDS if re.search(rf"\b{c}", sent)]
        dk = diff_rule(sent) if (not rules_here or set(rules_here) & {"whisper", "dutch"}) else None
        if (rules_here or dk) and cols:
            rk = dk or ("dutch" if "dutch" in rules_here else rules_here[0])
            for c in cols:
                out.setdefault({"gray": "grey"}.get(c, c), rk)
    return out


MARKER_TYPES = ("white", "black", "x", "v")
_GIVEN = r"(?:given|shown|marked|present|indicated|drawn|provided|placed|givin|displayed)"


def _marker_types(clause):
    """Edge-marker types a clause talks about: white/black kropki dots, X, V."""
    s = clause
    out = set()
    if re.search(r"\bwhite\s+(?:kropki|dots?|circles?)|\bwhite\b.{0,25}\bkropki", s):
        out.add("white")
    if re.search(r"\bblack\s+(?:kropki|dots?|circles?)|\bblack\b.{0,25}\bkropki", s):
        out.add("black")
    # generic "dots"/"kropki" (no colour qualifier) = both colours
    other_col = re.search(
        r"\b(?:red|gold|golden|yellow|gr[ae]y|blue|green|orange|purple|pink)\s+(?:and\s+\w+\s+)?(?:kropki|dots?)", s
    )
    if not out and not other_col and re.search(r"\b(?:kropkis?|dots?)\b", s):
        out |= {"white", "black"}
    if re.search(r"\bxvs?\b|\bxv[- ]?(?:pairs?|clues?|markings?)|\bv/x\b|\bx/v\b", s):
        out |= {"x", "v"}
    if re.search(r"\bx(?:'?s|-pairs?| pairs?| clues?)?\b(?!-)", s) and not re.search(r"\bx-sums?\b|\bx sums?\b", s):
        out.add("x")
    if re.search(r"\bv(?:'?s|-pairs?| pairs?| clues?)?\b", s):
        out.add("v")
    return out


def negative_markers(rules):
    """Which edge-marker types carry a negative constraint ("all white dots are
    given", "ALL V ARE GIVEN", "negative constraint for black dots", "every
    domino summing to 10 is marked with an X"). Clauses saying "not all ..."
    never add a type; a later affirmative clause can ("Not all white dots and X
    are given, but ALL V ARE GIVEN" -> {v})."""
    t = (rules or "").lower().replace("’", "'")
    neg = set()
    pending = False  # "there is a negative constraint, but it only applies to the V"
    for clause in re.split(r"[.!;\n]|,?\s+but\s+|\(", t):
        c = clause.strip()
        if pending and c:
            pending = False
            if re.search(r"\bonly\b|\bappl", c):
                neg |= _marker_types(c)
                continue
        if c and re.search(r"negative constraint", c) and not _marker_types(c) and not re.search(r"\bno\b", c):
            pending = True
            continue
        if not c or re.search(
            r"\bnot\s+(?:all|every|necessar)|\bnot\b.{0,30}\bnecessarily\b|all but one|\bwithin (?:a|each|the) (?:region|box|row|column)",
            c,
        ):
            continue
        affirm = (
            re.search(
                rf"\ball\b(?: (?:possible|such|applicable|the|of the))*\b.{{0,40}}\b(?:are|is|have been|has been)\s+{_GIVEN}",
                c,
            )
            or re.search(rf"\ball\b.{{0,40}}\b{_GIVEN}\b", c)
            and re.search(r"\ball (?:possible |such )?(?:white |black )?(?:kropkis?|dots?|xs?|vs?|xv|x'?s|v'?s)\b", c)
            or re.search(r"negative constraint", c)
            or re.search(rf"\bevery\b.{{0,60}}\b(?:is|are)\s+{_GIVEN}\b", c)
        )
        if affirm:
            neg |= _marker_types(c)
    if pending:  # a bare "negative constraint(s)" that never says which markers: all of them
        neg |= set(MARKER_TYPES)
    return neg


def rule_flags(rules):
    t = (rules or "").lower()
    neg = negative_markers(rules)
    return {
        "negative_markers": neg,
        "antiknight": bool(re.search(r"anti[- ]?knight|knight'?s move", t)),
        "antiking": bool(
            re.search(
                r"anti[- ]?king|king'?s move|diagonally adjacent cells|\bno[- ]touch\b"
                r"|(?:equal|identical|same) digits?[^.]{0,30}(?:can ?not|may not|must not|never) touch[^.]{0,20}diagonal",
                t,
            )
        ),
        "nonconsec": bool(
            re.search(
                r"non-?consecutive|orthogonally adjacent cells (?:can ?not|may not|must not) (?:contain|be) consecutive",
                t,
            )
        ),
        "diag_pos": bool(
            re.search(
                r"positive diagonal|both (main )?diagonals|marked diagonals|\bdiagonals?\b.*(?:can ?not|may not|must not) repeat",
                t,
            )
        ),
        "diag_neg": bool(
            re.search(
                r"negative diagonal|both (main )?diagonals|marked diagonals|\bdiagonals?\b.*(?:can ?not|may not|must not) repeat",
                t,
            )
        ),
        "kropki_negative": {"white", "black"} <= neg,
        "xv_negative": {"x", "v"} <= neg,
        "killer_distinct": not re.search(r"digits? (may|can) repeat (in|within) (a )?cage", t),
    }


def negative_types(flags, overrides=None):
    """Marker types under a negative constraint: overrides["_negative"] (iterable
    of MARKER_TYPES) > legacy overrides["_kropki_negative"] (bool, both dot
    colours) > the rules text."""
    ov = overrides or {}
    if "_negative" in ov:
        return set(ov["_negative"])
    if "_kropki_negative" in ov:
        return {"white", "black"} if ov["_kropki_negative"] else set()
    return set(flags["negative_markers"])


def hls(hexcol):
    h = str(hexcol or "#000").lstrip("#")
    if len(h) in (3, 4):
        h = "".join(ch * 2 for ch in h[:3])
    try:
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 0.0, 0.0, 0.0
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return hue * 360, light, sat


def line_rule_from_text(hexcol, cmap):
    """Rule for a line colour: exact colour-class match, else the nearest
    colour word in the rules text (hue within 40 degrees)."""
    cname = color_name(hexcol)
    if cname in cmap:
        return cmap[cname]
    hue, light, sat = hls(hexcol)
    if cname in ("white", "black", "grey"):
        return None
    best, bd = None, 41
    for word, rk in cmap.items():
        if word in COLOR_HUES:
            d = abs(hue - COLOR_HUES[word]) % 360
            d = min(d, 360 - d)
            if d < bd:
                best, bd = rk, d
    return best


def is_chevron(wp):
    """A greater-than sign drawn as a line: 3 waypoints spanning < 0.9 cells with the middle (apex) off the ends' line."""
    if len(wp) != 3:
        return False
    span = max(abs(wp[0][0] - wp[2][0]), abs(wp[0][1] - wp[2][1]), abs(wp[0][0] - wp[1][0]), abs(wp[0][1] - wp[1][1]))
    mid = ((wp[0][0] + wp[2][0]) / 2, (wp[0][1] + wp[2][1]) / 2)
    return span < 0.9 and math.dist(mid, wp[1]) > 0.08


def inequality_signs(P, n, rules):
    """Greater-than signs drawn as chevrons (3-point lines) or short arrows across a cell edge -> (smaller, larger)
    cell pairs [(r, c), (r, c)]. A chevron's apex points at the smaller digit; an arrow points at the smaller digit
    unless the rules say it points at the larger one."""
    t = (rules or "").lower()
    to_larger = bool(re.search(r"points? (?:at|to(?:wards)?) the (?:larger|greater|bigger|higher)", t))
    out = []

    def pair(centre, d):
        L = math.hypot(*d) or 1.0
        u = (d[0] / L, d[1] / L)
        small = cell_of((centre[0] + 0.5 * u[0], centre[1] + 0.5 * u[1]))
        big = cell_of((centre[0] - 0.5 * u[0], centre[1] - 0.5 * u[1]))
        if (
            small != big
            and all(0 <= x < n for x in small + big)
            and abs(small[0] - big[0]) + abs(small[1] - big[1]) == 1
        ):
            out.append((small, big))

    for ln in P.get("lines") or []:
        wp = (ln or {}).get("wayPoints") or [] if isinstance(ln, dict) else []
        if is_chevron(wp):
            mid = ((wp[0][0] + wp[2][0]) / 2, (wp[0][1] + wp[2][1]) / 2)
            pair(((mid[0] + wp[1][0]) / 2, (mid[1] + wp[1][1]) / 2), (wp[1][0] - mid[0], wp[1][1] - mid[1]))
    for ar in P.get("arrows") or []:
        wp = (ar or {}).get("wayPoints") or [] if isinstance(ar, dict) else []
        if len(wp) == 2 and math.dist(wp[0], wp[1]) < 0.9:
            d = (wp[1][0] - wp[0][0], wp[1][1] - wp[0][1])
            if to_larger:
                d = (-d[0], -d[1])
            pair(((wp[0][0] + wp[1][0]) / 2, (wp[0][1] + wp[1][1]) / 2), d)
    return out


def line_items(P, n):
    """Cell lines of the puzzle: [(colour class, hex, [cells]), ...], skipping
    decoration: lines drawn along grid lines (all waypoints on cell corners),
    and white/near-white lines that trace another line (the hollow centre of a
    'hollow' line). Full-length corner-to-corner diagonals come back with
    class 'diagonal'."""
    raw = []
    for ln in P.get("lines") or []:
        if not isinstance(ln, dict):
            continue
        wp = ln.get("wayPoints") or []
        if len(wp) < 2 or is_chevron(wp):  # chevrons are greater-than signs, not lines
            continue
        on_corners = all(abs(x - round(x)) < 0.05 and abs(y - round(y)) < 0.05 for x, y in wp)
        if on_corners:
            ends = {tuple(map(round, wp[0])), tuple(map(round, wp[-1]))}
            if ends == {(0, 0), (n, n)}:
                raw.append(("diagonal", "-", [(i, i) for i in range(n)]))
            elif ends == {(0, n), (n, 0)}:
                raw.append(("diagonal", "+", [(i, n - 1 - i) for i in range(n)]))
            continue
        lc = [x for x in line_cells(wp) if 0 <= x[0] < n and 0 <= x[1] < n]
        if len(lc) < 2:
            continue
        raw.append((color_name(ln.get("color")), ln.get("color"), lc))
    coloured = [set(lc) for cn, _, lc in raw if cn not in ("white", "diagonal")]
    out = []
    for cn, hx, lc in raw:
        if cn == "white" and any(set(lc) <= cs for cs in coloured):
            continue
        out.append((cn, hx, lc))
    return out


def cell_of(pt):
    return int(math.floor(pt[0])), int(math.floor(pt[1]))


def line_cells(wp):
    cells = []
    for a, b in zip(wp, wp[1:]):
        steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        n = max(1, int(round(steps)))
        for k in range(n + 1):
            pt = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
            c = cell_of(pt)
            if not cells or cells[-1] != c:
                cells.append(c)
    return cells


EDGE_NUMBER_RULES = ["sum", "diff", "ratio", "prod"]
M.RELATIONS.setdefault("prod", lambda v, w, k: v * w == k)


def edge_number_rule(rules):
    """Meaning of numbers on cell borders from the rules text (None = unknown)."""
    t = rules.lower()
    for kind, pat in (
        ("diff", r"differ|difference"),
        ("ratio", r"ratio|times|multiple|double"),
        ("prod", r"product|multipl"),
        ("sum", r"sum|add up|total"),
    ):
        if re.search(r"(border|edge|between|adjacent|straddl|clue|number)[^.]{0,80}" + pat, t) or re.search(
            pat + r"[^.]{0,80}(border|edge|between|adjacent)", t
        ):
            return kind
    return None


def without_nulls(P):
    """the puzzle's element lists without null entries (SudokuPad skips them; some files carry them, in a list or in an
    element's cells / way points); the cell grid keeps its nulls, where a position matters"""

    def clean(x):
        if isinstance(x, dict):
            return {k: [y for y in v if y is not None] if k in ("cells", "wayPoints") and isinstance(v, list) else v
                    for k, v in x.items()}  # fmt: skip
        return x

    return {
        k: [clean(x) for x in v if x is not None] if isinstance(v, list) and k != "cells" else v for k, v in P.items()
    }


def translate(sp, page_text=None, overrides=None):
    """sp: decoded dict from sudokupad.fetch; page_text: the puzzle page's
    rules (e.g. the Logic Masters text) when the SudokuPad file has none.
    Returns (Puzzle, info) or (None, reason)."""
    sp = dict(sp, puzzle=without_nulls(sp["puzzle"]))
    P = sp["puzzle"]
    meta = sp.get("meta", {})
    rules = (meta.get("rules") or "") + "\n" + (page_text or "")
    if not rules.strip():
        return None, "no rules text"
    cells = P.get("cells") or []
    hidden_houses = [
        cg
        for cg in (P.get("cages") or [])
        if isinstance(cg, dict)
        and cg.get("unique")
        and cg.get("hidden")
        and cg.get("cells")
        and cg.get("value") in (None, "")
    ]
    if hidden_houses and (len(hidden_houses) >= 6 or any(len(row) != len(cells) for row in cells)):
        return translate_explicit(sp, rules, hidden_houses)
    n = len(cells)
    if n < 4 or any(len(row) != n for row in cells):
        return None, "non-square grid"
    regions = [reg for reg in (P.get("regions") or []) if reg]
    whole = any(len({tuple(x) for x in reg if x}) == n * n for reg in regions)
    if whole:  # one region over the whole grid: no boxes, rows and columns only (Spiraling Circles, 000O94)
        regions = []
    chaos = not regions and bool(CHAOS_TEXT.search(rules.lower()))  # regions to find (format 6.3)
    p = M.Puzzle(D=n, coords=M._grid_coords(n))
    for r in range(n):
        p.groups.append(M.Group(f"r{r + 1}", tuple(r * n + c for c in range(n)), "row", True))
    for c in range(n):
        p.groups.append(M.Group(f"c{c + 1}", tuple(r * n + c for r in range(n)), "col", True))
    boxes = [tuple(sorted(x[0] * n + x[1] for x in reg if x)) for reg in regions]
    if regions:  # one region short (unparsed / implicit cells) and the leftover cells fill it exactly
        left = sorted(set(range(n * n)) - {c for b in boxes for c in b})
        short = [k for k, b in enumerate(boxes) if len(b) < n]
        if len(short) == 1 and len(left) == n - len(boxes[short[0]]):
            boxes[short[0]] = tuple(sorted(boxes[short[0]] + tuple(left)))
        elif not short and len(left) == n and len(boxes) == n - 1:
            boxes.append(tuple(left))
    for k, cs in enumerate(boxes):
        p.groups.append(M.Group(f"b{k + 1}", cs, "box", len(cs) == n))
    if not regions and (whole or chaos or NO_BOXES.search(rules.lower())):
        pass  # rows and columns only ("Latin square"): no implied boxes
    elif not regions:  # SudokuPad implies standard boxes when none are drawn
        bh, bw = {4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3), 12: (3, 4), 16: (4, 4)}.get(n, (0, 0))
        if not bh:
            return None, "no regions"
        for br in range(0, n, bh):
            for bc in range(0, n, bw):
                cs = tuple(sorted((br + i) * n + bc + j for i in range(bh) for j in range(bw)))
                p.groups.append(M.Group(f"b{len(p.groups)}", cs, "box", True))
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            if isinstance(cell, dict) and str(cell.get("value", "")).isdigit():
                p.givens[r * n + c] = int(cell["value"])
    idx = lambda rc: rc[0] * n + rc[1]
    inside = lambda rc: 0 <= rc[0] < n and 0 <= rc[1] < n
    flags = rule_flags(rules)
    cmap = rules_color_map(rules)
    p.constraints = []
    used = defaultdict(int)
    unknown = []
    # killer cages (skip metadata cages)
    for cg in P.get("cages") or []:
        if not isinstance(cg, dict) or not cg.get("cells"):
            continue
        cs = [idx(tuple(x)) for x in cg["cells"] if inside(tuple(x))]
        v = cg.get("value")
        total = int(v) if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()) else None
        if cs:
            p.groups.append(M.Group(f"k{len(p.groups)}", tuple(sorted(cs)), "cage", len(cs) == n, total))
            used["killer"] += 1
    # interior arrows (SudokuPad "arrows" with heads). The shaft starts on the circle's EDGE (e.g. 4.218 for a
    # circle centred at 3.5), so attach it to the nearest circle; a 2-3 cell pill = multi-digit circle.
    rcirc = []
    for lay in (P.get("underlays") or []) + (P.get("overlays") or []):
        if (
            isinstance(lay, dict)
            and lay.get("rounded")
            and "center" in lay
            and max(lay.get("width", 0) or 0, lay.get("height", 0) or 0) >= 0.6
        ):
            cx, cy = lay["center"]
            w = lay.get("width", 0) or 0
            h = lay.get("height", w) or w
            cs_ = sorted(
                {
                    cell_of((cx + dx, cy + dy))
                    for dx in (-(w / 2) + 0.2, 0, w / 2 - 0.2)
                    for dy in (-(h / 2) + 0.2, 0, h / 2 - 0.2)
                }
            )
            cs_ = [c for c in cs_ if inside(c)]
            if cs_:
                rcirc.append(((cx, cy), cs_))
    for ar in P.get("arrows") or []:
        wp = ar.get("wayPoints") if isinstance(ar, dict) else None
        if not wp or len(wp) < 2 or not inside(cell_of(wp[0])):  # outside starts = little killers (below)
            continue
        if (
            len(wp) == 2
            and math.dist(wp[0], wp[1]) < 0.9
            and re.search(r"greater|inequalit|less than|smaller", rules.lower())
        ):
            continue  # a short arrow across an edge = inequality sign
        near = min(rcirc, key=lambda c_: (c_[0][0] - wp[0][0]) ** 2 + (c_[0][1] - wp[0][1]) ** 2, default=None)
        if near is None or (near[0][0] - wp[0][0]) ** 2 + (near[0][1] - wp[0][1]) ** 2 > 0.9**2:
            unknown.append("arrow without circle")
            continue
        shaft = [x for x in line_cells(wp) if inside(x) and x not in near[1]]
        if shaft:
            p.constraints.append(
                {"type": "arrow", "circle": [idx(c_) for c_ in near[1]], "line": [idx(x) for x in shaft]}
            )
            used["arrow"] += 1
    # circles (bulbs / arrow circles) and other shapes
    circles = {}
    quad_corners = (
        [
            tuple(lay["center"])
            for lay in (P.get("underlays") or []) + (P.get("overlays") or [])
            if isinstance(lay, dict)
            and lay.get("rounded")
            and "center" in lay
            and abs(lay["center"][0] - round(lay["center"][0])) < 0.05
            and abs(lay["center"][1] - round(lay["center"][1])) < 0.05
            and 0.4 <= (lay.get("width") or 0) <= 0.9
        ]
        if QUAD_TEXT.search(rules.lower())
        else []
    )
    for lay in (P.get("underlays") or []) + (P.get("overlays") or []):
        if not isinstance(lay, dict) or "center" not in lay:
            continue
        cx, cy = lay["center"]
        if (
            quad_corners
            and str(lay.get("text", "") or "").strip()
            and any(abs(cx - qx) < 0.3 and abs(cy - qy) < 0.3 for qx, qy in quad_corners)
        ):
            continue  # a quadruple clue digit (handled by quadruples())
        w = lay.get("width", 0)
        txt = str(lay.get("text", "") or "").strip()
        on_edge = abs(cx - round(cx)) < 0.05 or abs(cy - round(cy)) < 0.05
        if lay.get("rounded") and w >= 0.6 and not on_edge and inside(cell_of((cx, cy))):
            circles[cell_of((cx, cy))] = color_name(lay.get("backgroundColor") or lay.get("borderColor"))
        elif txt and not on_edge and w < 0.6 and inside(cell_of((cx, cy))):
            # text inside a cell away from its centre is a clue of some kind (run sums in a corner, 000V90): no reading
            # handles it, so refuse rather than drop it; near a cell corner it may be a quadruple digit (quadruples())
            centred = abs(cx - math.floor(cx) - 0.5) < 0.15 and abs(cy - math.floor(cy) - 0.5) < 0.15
            near_corner = abs(cx - round(cx)) < 0.3 and abs(cy - round(cy)) < 0.3
            if not centred and not (near_corner and QUAD_TEXT.search(rules.lower())):
                unknown.append(f"cell text {txt!r}")
        elif on_edge and w < 0.5 and not (abs(cx - round(cx)) < 0.05 and abs(cy - round(cy)) < 0.05):
            # edge marker between two cells: kropki dot or XV letter
            a = (int(math.floor(cx - 0.01)), int(math.floor(cy - 0.01)))
            b = (int(math.floor(cx + 0.01)), int(math.floor(cy + 0.01)))
            if abs(cx - round(cx)) < 0.05:
                a, b = (int(round(cx)) - 1, int(math.floor(cy))), (int(round(cx)), int(math.floor(cy)))
            else:
                a, b = (int(math.floor(cx)), int(round(cy)) - 1), (int(math.floor(cx)), int(round(cy)))
            if not (inside(a) and inside(b)):
                continue
            if txt in ("<", ">", "\u2039", "\u203a", "^", "v") and "greater" in rules.lower() or txt in ("<", ">"):
                # sign between a (left/top) and b (right/bottom): '<' -> a < b
                lo, hi = (a, b) if txt in ("<", "\u2039", "^") else (b, a)
                p.relations.append(("lt", idx(lo), idx(hi)))
                used["greater"] += 1
            elif txt.upper() in ("X", "V"):
                p.relations.append(("sum", idx(a), idx(b), 10 if txt.upper() == "X" else 5))
                used["xv"] += 1
            elif txt == "" and lay.get("rounded"):
                bg = color_name(lay.get("backgroundColor"))
                low = rules.lower()
                if (
                    not lay.get("backgroundColor")
                    and re.search(r"white (?:dot|circle|kropki)", low)
                    and not re.search(r"black (?:dot|circle|kropki)", low)
                ):
                    bg = "white"  # a dot without a colour where the rules know only white dots (Easy Arrows, 000930)
                if bg == "white":
                    p.relations.append(("diff", idx(a), idx(b), 1))
                    used["kropki_white"] += 1
                elif bg in ("black", "grey"):
                    p.relations.append(("ratio", idx(a), idx(b), 2))
                    used["kropki_black"] += 1
            elif re.fullmatch(r"\d{1,2}", txt):
                kind = (overrides or {}).get("_edgenum") or edge_number_rule(rules)
                k_ = int(txt)
                if kind == "sum":
                    p.relations.append(("sum", idx(a), idx(b), k_))
                elif kind == "diff":
                    p.relations.append(("diff", idx(a), idx(b), k_))
                elif kind == "ratio":
                    p.relations.append(("ratio", idx(a), idx(b), k_))
                elif kind == "prod":
                    p.relations.append(("prod", idx(a), idx(b), k_))
                else:
                    unknown.append(f"edge number {txt!r}")
                    continue
                used[f"edge_{kind}"] += 1
            elif txt:
                unknown.append(f"edge text {txt!r}")
    # greater-than signs drawn as chevrons / short arrows
    if re.search(r"greater|inequalit|less than|smaller|<|>", rules.lower()):
        for small, big in inequality_signs(P, n, rules):
            p.relations.append(("lt", idx(small), idx(big)))
            used["greater"] += 1
    # lines
    text_mentions = {k for k, pats in RULE_WORDS.items() if any(re.search(pt, rules.lower()) for pt in pats)}
    if "dutch" in text_mentions and not re.search(r"(?<!dutch )whisper", rules.lower()):
        text_mentions.discard("whisper")
    text_mentions -= {"ten"}
    dk_all = diff_rule(rules.lower())
    if dk_all and dk_all not in ("whisper", "dutch"):  # 'differ by at least 3' (6x6 whisper, Texas hollers ...)
        text_mentions = (text_mentions - {"whisper"}) | {dk_all}
    if "slow_thermo" in text_mentions or (
        SLOW_ALL.search(rules.lower()) and not re.search(r"(?:normal|regular|standard) thermo", rules.lower())
    ):
        text_mentions = (text_mentions - {"thermo", "slow_thermo"}) | {"slow_thermo"}
    if len({cn for cn, _, _ in line_items(P, n)} - {"diagonal"}) == 1:
        text_mentions |= described_line_rules(rules)  # "digits on a line form a consecutive set", one line colour
    box_of = {c: gi for gi, g in enumerate(p.groups) if g.kind == "box" for c in g.cells}
    told = set()  # line colours whose meaning is logged (once per colour and reading)
    for cname, hexcol, lc in line_items(P, n):
        if cname == "diagonal":
            ids = [idx(x) for x in lc]
            if re.search(r"diagonal", rules.lower()) and not any(set(g.cells) == set(ids) for g in p.groups):
                p.groups.append(M.Group(f"d{hexcol}", tuple(ids), "diag", True))
                used["diagonal"] += 1
            continue
        rule = (overrides or {}).get(cname) or line_rule_from_text(hexcol, cmap)
        how = "the rules text naming its colour"
        if (
            re.search(r"double arrow", rules.lower())
            and lc[0] in circles
            and lc[-1] in circles
            and rule in (None, "arrow", "thermo", "between")
        ):
            rule, how = "double_arrow", "circles at both ends and double arrows in the rules text"
        bulb = [x for x in (lc[0], lc[-1]) if circles.get(x) == cname]  # a circle in the line's own colour at one end
        if (
            rule not in (None, "thermo", "slow_thermo", "arrow", "double_arrow", "between")
            and len(bulb) == 1
            and "thermo" in rules.lower()
        ):  # grey thermometers beside grey palindromes (German Beetles, 000JH3): the bulb tells them apart
            rule, how = "thermo", f"a bulb in its colour (the rules text gives {cname} lines without one)"
        if rule is None and lc[0] in circles and lc[-1] in circles and "between" in text_mentions:
            rule, how = "between", "circles at both ends and between lines in the rules text"
        if (
            rule is None
            and len(text_mentions - {"arrow", "thermo"}) == 1
            and not (lc[0] in circles or lc[-1] in circles)
        ):
            rule = next(iter(text_mentions - {"arrow", "thermo"}))  # the only line rule the text names
            how = "the only line rule in the rules text"
        if rule is None and (lc[0] in circles or lc[-1] in circles):
            rule = "thermo" if "thermo" in rules.lower() else ("arrow" if "arrow" in rules.lower() else None)
            how = "a circle at one end and the rules text"
        if rule == "thermo" and "slow_thermo" in text_mentions and "thermo" not in text_mentions:
            rule, how = "slow_thermo", how + " (slow)"
        if rule is None and not cmap and re.search(DEFAULT_EVIDENCE.get(DEFAULT_LINE.get(cname), "^$"), rules.lower()):
            rule, how = DEFAULT_LINE.get(cname), "SudokuPad's default colours (the rules text names none)"
        if overrides is None and (cname, rule) not in told:  # infer() logs its readings instead
            told.add((cname, rule))
            _log.debug("%s line (%s): %s, by %s", cname, hexcol, rule or "unknown", how if rule else "no clue")
        if rule is None:
            unknown.append(f"{cname} line")
            continue
        if rule == "ignore":
            continue
        ids = [idx(x) for x in lc]
        loop = len(ids) > 2 and ids[0] == ids[-1]
        if rule in ("renban", "region_sum") and len(set(ids)) != len(ids):
            ids = list(dict.fromkeys(ids))  # closed loop: the start cell is drawn twice, counted once
        if rule in ("thermo", "slow_thermo"):
            if lc[-1] in circles and lc[0] not in circles:
                ids = ids[::-1]
            p.relations += [("lt" if rule == "thermo" else "le", a, b) for a, b in zip(ids, ids[1:])]
        elif rule.startswith("whisper") and rule[7:].isdigit():
            p.relations += [("diffge", a, b, int(rule[7:])) for a, b in zip(ids, ids[1:])]
        elif rule == "whisper":
            p.relations += [("diffge", a, b, 5) for a, b in zip(ids, ids[1:])]
        elif rule == "dutch":
            p.relations += [("diffge", a, b, 4) for a, b in zip(ids, ids[1:])]
        elif rule == "renban":
            p.constraints.append({"type": "set", "cells": ids, "kind": "consecutive"})
        elif rule == "region_sum":
            segs, cur = [], [ids[0]]
            for c in ids[1:]:
                if box_of.get(c) == box_of.get(cur[-1]):
                    cur.append(c)
                else:
                    segs.append(cur)
                    cur = [c]
            segs.append(cur)
            if loop and len(segs) > 1 and box_of.get(segs[0][0]) == box_of.get(segs[-1][-1]):
                segs[0] = segs.pop() + segs[0]  # a loop's last and first segments join through the closing edge
            if len({box_of.get(sg[0]) for sg in segs}) < len(segs) and RS_PER_BOX.search(rules.lower()):
                unknown.append("region sum line re-entering a box (sum per box)")  # one total per box, not per segment
                continue
            if len(segs) > 1:
                p.constraints.append({"type": "equal_sum", "segments": segs})
        elif rule == "palindrome":
            p.relations += [("eq", ids[k], ids[-1 - k]) for k in range(len(ids) // 2) if ids[k] != ids[-1 - k]]
        elif rule == "entropic":  # model line compile: thirds of 1..D on 6x6 etc., fixed 1-3/4-6/7-9 on 9x9
            p.constraints.append({"type": "line", "kind": "entropic", "cells": ids})
        elif rule == "parity" and len(set(ids)) != len(ids):
            p.relations += [("parity", a, b) for a, b in zip(ids, ids[1:]) if a != b]
        elif rule == "modular" and len(set(ids)) != len(ids):
            for k in range(len(ids)):
                for j in range(k + 1, min(k + 4, len(ids))):
                    if ids[k] != ids[j]:
                        p.relations.append(("samemod3" if j - k == 3 else "diffmod3", ids[k], ids[j]))
        elif rule == "same_parity":  # no rule family: a custom rule, kept by name
            from .. import puzzle_json as PJ

            # neighbours along the line share a parity (the same rule as "all odd or all even", in 2-cell instances: the
            # engine reads small rules as digit tables, which propagate as the cells fill)
            name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
            PJ.add_named(
                p,
                {
                    "type": "custom",
                    "cells": {"pair": [[name(a), name(b)] for a, b in zip(ids, ids[1:])]},
                    "each": "pair",
                    "holds": "pair[1] mod 2 == pair[2] mod 2",
                    "label": "Same-parity line",
                },
            )
        elif rule in ("parity", "modular", "zipper"):
            if len(set(ids)) != len(ids):
                unknown.append(f"self-crossing {rule} line")
                continue
            p.constraints.append({"type": "line", "kind": rule, "cells": ids})
        elif rule == "between":
            if not (lc[0] in circles and lc[-1] in circles) or len(set(ids)) != len(ids):
                unknown.append("between line without end circles")
                continue
            stops = [k for k, x in enumerate(lc) if x in circles]  # a line through several circles: one between line
            for i, j in zip(stops, stops[1:]):  # per stretch from circle to circle
                if j > i + 1:
                    p.constraints.append({"type": "line", "kind": "between", "cells": ids[i : j + 1]})
        elif rule == "nabner":
            u = list(dict.fromkeys(ids))
            for i_ in range(len(u)):
                for j_ in range(i_ + 1, len(u)):
                    p.relations.append(("neq", u[i_], u[j_]))
                    p.relations.append(("nonconsec", u[i_], u[j_]))
        elif rule == "lockout":
            a, b = ids[0], ids[-1]
            if a == b or len(set(ids)) != len(ids):
                unknown.append("malformed lockout line")
                continue
            m_ = re.search(r"lockout.{0,200}?(?:at least|by|difference of) (\d)", rules.lower(), re.S)
            k_ = int(m_.group(1)) if m_ else 4
            p.constraints.append({"type": "line", "kind": "lockout", "cells": ids, "k": k_})  # compiled by finalize
        elif rule == "double_arrow":  # the two circle digits sum to the line's digits between them
            if len(ids) < 3 or ids[0] == ids[-1]:
                unknown.append("malformed double arrow")
                continue
            p.constraints.append({"type": "equal_sum", "segments": [[ids[0], ids[-1]], ids[1:-1]]})
        elif rule == "arrow":
            circ = [x for x in (lc[0], lc[-1]) if x in circles]
            if not circ:
                unknown.append("arrow without circle")
                continue
            if lc[-1] in circles and lc[0] not in circles:
                ids = ids[::-1]
            p.constraints.append({"type": "arrow", "circle": [ids[0]], "line": ids[1:]})
        else:
            unknown.append(f"{rule} line")
            continue
        used[rule] += 1
    # global rules from text
    if flags["antiknight"]:
        M.add_antiknight(p, n)
        used["antiknight"] += 1
    if flags["antiking"]:
        for r in range(n - 1):
            for c in range(n):
                for dc in (-1, 1):
                    if 0 <= c + dc < n:
                        p.relations.append(("neq", r * n + c, (r + 1) * n + c + dc))
        used["antiking"] += 1
    if flags["nonconsec"]:  # not across a dot / X / V (a white dot would contradict it), as in f-puzzles
        dotted = {tuple(sorted(r_[1:3])) for r_ in p.relations if r_[0] in ("diff", "ratio", "sum")}
        q = M.add_nonconsecutive(M.Puzzle(D=n, coords=p.coords), n)
        p.relations += [r_ for r_ in q.relations if tuple(sorted(r_[1:3])) not in dotted]
        used["nonconsec"] += 1
    # a negative rule also binds marker types absent from the grid ("all dots are given" with only white
    # dots drawn -> no 2:1 pairs either), but only within a marker family that is present at all, or, for X / V, that
    # the rules define as a rule although none is drawn ("digits separated by a V sum to 5 ... all X and V are given":
    # no pair sums to 5 or 10; 000STV). Kropki keeps the presence test: series introductions discuss "all possible dots
    # are given" around plain classics (0001TZ)
    neg = negative_types(flags, overrides)
    xv_def = re.search(r"\b(?:an? )?[xv]\b[^.\n]{0,30}\bsums? to (?:10|ten|5|five)\b", rules.lower())
    neg &= ({"white", "black"} if used["kropki_white"] or used["kropki_black"] else set()) | (
        {"x", "v"} if used["xv"] or xv_def else set()
    )
    if neg:
        # a pair carrying any edge marker is exempt from every negative rule
        marked = {frozenset(r_[1:3]) for r_ in p.relations if r_[0] in ("diff", "ratio", "sum")}
        NEG_REL = {"white": ("notdiff", 1), "black": ("notratio", 2), "x": ("notsum", 10), "v": ("notsum", 5)}
        for x in range(n * n):
            r, c = divmod(x, n)
            for y in ([x + 1] if c + 1 < n else []) + ([x + n] if r + 1 < n else []):
                if frozenset((x, y)) not in marked:
                    for t in sorted(neg):
                        p.relations.append((NEG_REL[t][0], x, y, NEG_REL[t][1]))
        used["negative_" + "".join(t[0] for t in MARKER_TYPES if t in neg)] += 1
    text_rules = rules.lower()
    # counting circles: every digit in a circle appears in exactly that many circles (circles not used by lines)
    if circles and re.search(
        r"counting circle|(?:digit|number) in a circle.{0,60}(?:circles|number of)|"
        r"circled digits?.{0,40}(?:how many|exactly that many|number of)",
        text_rules,
    ):
        on_lines = {
            x
            for con in p.constraints
            for x in (con.get("cells") or con.get("line") or []) + list(con.get("circle") or [])
        }
        cc = sorted(idx(rc_) for rc_ in circles if inside(rc_) and idx(rc_) not in on_lines)
        if cc:
            p.constraints.append({"type": "counting_circles", "cells": cc})
            used["counting_circles"] += 1
    parity_shapes(P, n, p, rules, used, idx, inside)
    global_rules(n, p, rules, used)
    shaded_regions(P, n, p, rules, used)
    outside_clues(P, n, p, rules, used, unknown, idx, inside)
    used["_quad_text"] = int(bool(QUAD_TEXT.search(text_rules)))
    quadruples(P, n, p, used, unknown, idx, inside)
    used.pop("_quad_text")
    unknown += unmodelled_rules(text_rules, chaos_ok=chaos)
    if chaos:
        p.constraints += chaos_rules(P, p, n, rules)
        used["chaos"] += 1
    # rules handled above: the text mentions them, so something must have been built for them
    for kw, key in (
        ("little killer", "little_killer"),
        ("sandwich", "sandwich"),
        ("x-sum", "xsum"),
        ("skyscraper", "skyscraper"),
        ("quadruple", "quadruple"),
        ("between line", "between"),
        ("zipper", "zipper"),
        ("parity line", ("parity", "same_parity")),
        ("lockout", "lockout"),
        ("nabner", "nabner"),
    ):
        if kw in text_rules and not any(used[k] for k in ((key,) if isinstance(key, str) else key)):
            unknown.append(f"rule '{kw}'")
    if P.get("foglight") or P.get("triggereffect"):
        unknown.append("fog of war")
    if unknown:
        return None, "unsupported: " + ", ".join(sorted(set(unknown)))
    return p, {k: v for k, v in used.items() if v}


def _num(t):
    t = str(t if t is not None else "").strip()
    return int(t) if re.fullmatch(r"\d{1,3}", t) else None


def _texts(P):
    for lay in (P.get("overlays") or []) + (P.get("underlays") or []):
        if isinstance(lay, dict) and "center" in lay and str(lay.get("text", "") or "").strip():
            yield lay


def outside_clues(P, n, p, rules, used, unknown, idx, inside):
    """Numbers outside the grid: little killer (with a diagonal arrow), else
    sandwich / x-sum / skyscraper row-column clues (whichever one rule the text
    names). Cells are listed from the clue inwards."""
    t = rules.lower()
    outside = {}
    for lay in _texts(P):
        rc = cell_of(lay["center"])
        if not inside(rc):
            outside.setdefault(rc, []).append(lay["text"])
    if not outside:
        return
    for ar in P.get("arrows") or []:
        wp = ar.get("wayPoints") or [] if isinstance(ar, dict) else []
        if len(wp) < 2:
            continue
        st = cell_of(wp[0])
        dr, dc = wp[-1][0] - wp[0][0], wp[-1][1] - wp[0][1]
        if inside(st) or abs(dr) < 1e-6 or abs(dc) < 1e-6 or st not in outside:
            continue
        dr, dc = (1 if dr > 0 else -1), (1 if dc > 0 else -1)
        vals = [_num(x) for x in outside.pop(st)]
        cells, (r, c) = [], (st[0] + dr, st[1] + dc)
        while inside((r, c)):
            cells.append(idx((r, c)))
            r, c = r + dr, c + dc
        if len(vals) != 1 or vals[0] is None or not cells:
            unknown.append("little killer clue")
            continue
        if "little killer" not in t and not re.search(r"diagonal", t):
            unknown.append("diagonal arrow clue")
            continue
        p.constraints.append({"type": "little_killer", "cells": cells, "total": vals[0]})
        used["little_killer"] += 1
    if not outside:
        return
    kinds = [
        k
        for k, pat in (
            ("sandwich", r"sandwich|between (?:the )?1 and (?:the )?9"),
            ("xsum", r"\bx-?sums?\b|sum of the first (?:x|n|k)\b"),
            ("skyscraper", r"skyscraper"),
            ("numbered_room", r"numbered rooms?|digit x (?:in|into) the x-?th cell|in the nth cell"),
            (
                "first_seen",
                r"\b123\b|first (?:of|digit among|one of) (?:the digits )?1, ?2 (?:or|and) 3|"
                r"(?:closest|nearest) (?:1, ?2 or 3|of 1, 2 and 3)",
            ),
        )
        if re.search(pat, t)
    ]
    if len(kinds) != 1:
        unknown.append("outside clues" + (" (ambiguous rule)" if kinds else ""))
        return
    kind = kinds[0]
    for (r, c), txts in outside.items():
        vals = [_num(x) for x in txts]
        if r < 0 and 0 <= c < n:
            cells = [idx((i, c)) for i in range(n)]
        elif r >= n and 0 <= c < n:
            cells = [idx((i, c)) for i in range(n - 1, -1, -1)]
        elif c < 0 and 0 <= r < n:
            cells = [idx((r, j)) for j in range(n)]
        elif c >= n and 0 <= r < n:
            cells = [idx((r, j)) for j in range(n - 1, -1, -1)]
        else:
            unknown.append("corner outside clue")
            continue
        if r < -1 or r > n or c < -1 or c > n or len(vals) != 1 or vals[0] is None:
            unknown.append("outside clue text")
            continue
        if kind == "numbered_room":  # clue X: the digit X sits in the N-th cell, N = the first digit from the clue
            X = vals[0]
            if not 1 <= X <= n:
                unknown.append("numbered room clue")
                continue
            if X != 1:
                p.domains[cells[0]] &= ~(1 << 0)  # first = 1 would put X in the first cell itself
            for k in range(2, n + 1):
                p.constraints.append(
                    {
                        "type": "table",
                        "cells": [cells[0], cells[k - 1]],
                        "allowed": [
                            (a, b) for a in range(1, n + 1) for b in range(1, n + 1) if a != b and (a != k or b == X)
                        ],
                    }
                )
            used["numbered_room"] += 1
            continue
        if kind == "first_seen":
            p.constraints.append({"type": "first_seen", "cells": cells, "value": vals[0], "digits": [1, 2, 3]})
        else:
            p.constraints.append(
                {"type": kind, "cells": cells, ("count" if kind == "skyscraper" else "total"): vals[0]}
            )
        used[kind] += 1


REGION_TEXT = re.compile(
    r"extra regions?|windoku|hyper[- ]?sudoku|\bnrc\b|asterisk|cent(?:er|re) dot|girandola|argyle|"
    r"(?:shaded|grey|gray|coloured|colored|marked|highlighted) (?:regions?|areas?|boxes|cells? (?:form|contain|is a))"
)


def shaded_regions(P, n, p, rules, used):
    """Extra all-different regions drawn as shading (asterisk, windoku, centre dot, 'grey regions'), only when the
    rules text names such regions. Square underlays (>= 0.8 cell) grouped by colour: a rectangle covering exactly n
    cells is a region; otherwise a colour's cells form one region (n cells) or n-cell connected pieces."""
    if not REGION_TEXT.search((rules or "").lower()):
        return
    by = defaultdict(list)
    for lay in P.get("underlays") or []:
        if (
            not isinstance(lay, dict)
            or "center" not in lay
            or lay.get("rounded")
            or str(lay.get("text", "") or "").strip()
        ):
            continue
        w, h = lay.get("width", 0) or 0, lay.get("height", 0) or lay.get("width", 0) or 0
        if w < 0.8 or h < 0.8:
            continue
        col = color_name(lay.get("backgroundColor") or "")
        if col == "white":
            continue
        cy, cx = lay["center"]
        rows = range(int(math.floor(cy - h / 2 + 0.05)), int(math.ceil(cy + h / 2 - 0.05)))
        cols = range(int(math.floor(cx - w / 2 + 0.05)), int(math.ceil(cx + w / 2 - 0.05)))
        cells = [r * n + c for r in rows for c in cols if 0 <= r < n and 0 <= c < n]
        if cells:
            by[col].append(cells)
    have = {frozenset(g.cells) for g in p.groups}

    def add(cs):
        fs = frozenset(cs)
        if len(fs) == n and fs not in have:
            p.groups.append(M.Group(f"x{len(p.groups)}", tuple(sorted(fs)), "region", True))
            have.add(fs)
            used["extra_region"] += 1

    for col, rects in by.items():
        big = [r for r in rects if len(r) == n]
        if big:
            for r in big:
                add(r)
            continue
        allc = sorted({c for r in rects for c in r})
        if len(allc) == n:
            add(allc)
        elif allc and len(allc) % n == 0:
            left = set(allc)
            while left:
                st = [left.pop()]
                comp = set(st)
                while st:
                    x = st.pop()
                    r, c = divmod(x, n)
                    for y in (
                        ([x - n] if r else [])
                        + ([x + n] if r < n - 1 else [])
                        + ([x - 1] if c else [])
                        + ([x + 1] if c < n - 1 else [])
                    ):
                        if y in left:
                            left.discard(y)
                            comp.add(y)
                            st.append(y)
                if len(comp) == n:
                    add(comp)


def global_rules(n, p, rules, used):
    """Whole-grid rules stated only in the text.
    Global entropy: every 2x2 area holds a low, a middle and a high digit (thirds of 1..n).
    Dutch flats / flatmates: every A has a B directly above it or a C directly below it ('every 5 ... 1 above ... 9 below')."""

    t = (rules or "").lower()
    if n % 3 == 0 and re.search(
        r"global entropy|every 2 ?x ?2[^.]{0,80}(?:low|entrop)|each 2 ?x ?2[^.]{0,80}(?:low|entrop)", t
    ):
        from .. import puzzle_json as PJ

        PJ.add_named(p, {"type": "global_entropy"})  # the named rule (one table definition for every source)
        used["global_entropy"] += 1
    m = None
    if re.search(
        r"dutch flat|flat ?mate", t
    ):  # the sentence with every / above / below: its first three digits = A, B, C
        for sent in re.split(r"(?<=[.!;\n])\s*", t):
            if re.search(r"\b(?:every|each|all)\b", sent) and "above" in sent and "below" in sent:
                ds = re.findall(r"\d", sent)
                if len(ds) >= 3:
                    m = ds[:3]
                    break
    if m:
        A, B, C = (int(g) for g in m)
        for c in range(n):
            for r in range(n):
                above = (r - 1) * n + c if r > 0 else None
                below = (r + 1) * n + c if r < n - 1 else None
                x = r * n + c
                if above is None and below is None:
                    continue
                if above is None:
                    p.constraints.append(
                        {
                            "type": "table",
                            "cells": [x, below],
                            "allowed": [
                                (a, b)
                                for a in range(1, n + 1)
                                for b in range(1, n + 1)
                                if a != b and (a != A or b == C)
                            ],
                        }
                    )
                elif below is None:
                    p.constraints.append(
                        {
                            "type": "table",
                            "cells": [above, x],
                            "allowed": [
                                (a, b)
                                for a in range(1, n + 1)
                                for b in range(1, n + 1)
                                if a != b and (b != A or a == B)
                            ],
                        }
                    )
                else:
                    p.constraints.append(
                        {
                            "type": "table",
                            "cells": [above, x, below],
                            "allowed": [
                                (a, b, d)
                                for a in range(1, n + 1)
                                for b in range(1, n + 1)
                                for d in range(1, n + 1)
                                if len({a, b, d}) == 3 and (b != A or a == B or d == C)
                            ],
                        }
                    )
        used["dutch_flats"] += 1


def parity_shapes(P, n, p, rules, used, idx, inside):
    """Odd / even cells from the rules text: 'a (grey) circle contains an odd digit', 'digits in squares are even'.
    Only cell-centred shapes that no line, arrow or cage uses; a colour word in the sentence restricts the colour."""
    t = (rules or "").lower()
    taken = {
        x for con in p.constraints for x in (con.get("cells") or con.get("line") or []) + list(con.get("circle") or [])
    }
    taken |= {x for r_ in p.relations for x in r_[1:3] if r_[0] in ("lt", "le", "diffge", "eq", "parity")}
    shapes = []
    for lay in (P.get("underlays") or []) + (P.get("overlays") or []):
        if not isinstance(lay, dict) or "center" not in lay or str(lay.get("text", "") or "").strip():
            continue
        cx, cy = lay["center"]
        w, h = lay.get("width", 0) or 0, lay.get("height", 0) or lay.get("width", 0) or 0
        if (
            abs(cx - math.floor(cx) - 0.5) > 0.1
            or abs(cy - math.floor(cy) - 0.5) > 0.1
            or not (0.45 <= w <= 1.0 and 0.45 <= h <= 1.0)
        ):
            continue
        rc = cell_of((cx, cy))
        if inside(rc) and idx(rc) not in taken:
            shapes.append(
                (
                    "circle" if lay.get("rounded") else "square",
                    color_name(lay.get("backgroundColor") or lay.get("borderColor")),
                    idx(rc),
                )
            )
    if not shapes or len(shapes) > n * n // 3:
        return
    odd = sum(1 << (v - 1) for v in range(1, n + 1, 2))
    for sent in re.split(r"(?<=[.\n;])\s*", t):
        if re.search(r"count|number of|how many|sum|total|lots", sent):
            continue
        shp = [s_ for s_ in ("circle", "square") if re.search(rf"\b{s_}s?\b", sent)]
        par = [s_ for s_ in ("odd", "even") if re.search(rf"\b{s_}\b", sent)]
        cols = {{"gray": "grey"}.get(c, c) for c in COLOR_WORDS if re.search(rf"\b{c}\b", sent)} & {
            s_[1] for s_ in shapes
        }
        if not shp and cols and re.search(r"\bcells?\b", sent):  # 'digits in grey cells are odd': any shape, by colour
            shp = ["circle", "square"]
        if not shp or len(par) != 1 or (len(shp) > 1 and not cols):
            continue
        for kind, col, c in shapes:
            if kind in shp and (not cols or col in cols):
                p.domains[c] &= odd if par[0] == "odd" else p.full & ~odd
                used[par[0] + "_" + kind] += 1


def quadruples(P, n, p, used, unknown, idx, inside):
    """Quadruple: digits in a circle on a cell corner all appear (with
    multiplicity) in the four surrounding cells -> table constraint."""

    if not re.search(r"quadruple", (P.get("_rules") or "")) and not used.get("_quad_text"):
        return
    corner = defaultdict(str)
    for lay in _texts(P):
        cx, cy = lay["center"]
        rx, ry = round(cx), round(cy)
        if abs(cx - rx) < 0.3 and abs(cy - ry) < 0.3 and 0 < rx < n and 0 < ry < n:
            txt = re.sub(r"[\s,]", "", str(lay["text"]))
            corner[(rx, ry)] += txt if txt.isdigit() else "?"  # letters for digits (f3hfvcu3xz) were dropped silently
    D = n
    for (rx, ry), digs in corner.items():
        if not digs.isdigit():
            unknown.append("quadruple clue")
            continue
        need = [int(ch) for ch in digs]
        if len(need) > 4 or any(not 1 <= d <= D for d in need):
            unknown.append("quadruple clue")
            continue
        cs = [idx((rx - 1, ry - 1)), idx((rx - 1, ry)), idx((rx, ry - 1)), idx((rx, ry))]
        from .. import puzzle_json as PJ

        PJ.add_named(p, {"type": "quadruple", "cells": cs, "digits": need})  # the named rule
        used["quadruple"] += 1


def translate_explicit(sp, rules, hidden_houses):
    """Boards of any shape whose houses are declared as hidden 'unique' cages
    (SudokuPad convention for non-standard grids). Active cells = union of
    those cages; D from the rules text ('digits 1 to N') or the largest house."""
    P = sp["puzzle"]
    houses = []
    seen = set()
    for cg in hidden_houses:
        key = frozenset(tuple(x) for x in cg["cells"])
        if key not in seen:
            seen.add(key)
            houses.append(sorted(key))
    active = sorted({rc for h in houses for rc in h})
    pos = {rc: i for i, rc in enumerate(active)}
    m = re.search(r"digits? (?:from )?1 (?:to|-|through) (\d+)", rules.lower())
    D = int(m.group(1)) if m else max(len(h) for h in houses)
    if D > 25:
        return None, "D > 25"
    p = M.Puzzle(D=D, coords=[tuple(rc) for rc in active])
    for k, h in enumerate(houses):
        p.groups.append(
            M.Group(f"h{k}", tuple(pos[rc] for rc in h), "house" if len(h) == D else "partial", len(h) == D)
        )
    cells = P.get("cells") or []
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            if isinstance(cell, dict) and str(cell.get("value", "")).isdigit() and (r, c) in pos:
                p.givens[pos[(r, c)]] = int(cell["value"])
    p.constraints = []
    used = defaultdict(int)
    unknown = []
    for cg in P.get("cages") or []:  # visible killer cages
        if isinstance(cg, dict) and cg.get("cells") and not cg.get("hidden") and str(cg.get("value", "")).isdigit():
            cs = [pos[tuple(x)] for x in cg["cells"] if tuple(x) in pos]
            p.groups.append(M.Group(f"k{len(p.groups)}", tuple(sorted(cs)), "cage", len(cs) == D, int(cg["value"])))
            used["killer"] += 1
    circles = {
        cell_of(o["center"])
        for o in (P.get("overlays") or []) + (P.get("underlays") or [])
        if isinstance(o, dict) and o.get("rounded") and (o.get("width") or 0) >= 0.6 and "center" in o
    }
    for ar in P.get("arrows") or []:
        wp = ar.get("wayPoints") or []
        if len(wp) < 2:
            continue
        start = cell_of(wp[0])
        if start not in circles:
            continue
        path = [x for x in line_cells(wp) if x in pos and x != start]
        if path and start in pos:
            p.constraints.append({"type": "arrow", "circle": [pos[start]], "line": [pos[x] for x in path]})
            used["arrow"] += 1
    if any(
        isinstance(ln, dict) and ln.get("target") != "overlay" and color_name(ln.get("color")) not in ("white", "black")
        for ln in (P.get("lines") or [])
    ):
        unknown.append("coloured lines on explicit-house board")
    if unknown:
        return None, "unsupported: " + ", ".join(unknown)
    used["explicit_houses"] = len(houses)
    return p, dict(used)


LINE_RULES = [
    "thermo",
    "whisper",
    "dutch",
    "renban",
    "region_sum",
    "palindrome",
    "entropic",
    "arrow",
    "parity",
    "modular",
    "zipper",
    "between",
    "nabner",
    "slow_thermo",
    "ignore",
]


def satisfies(p, sol):
    """Does solution `sol` (list of digits) satisfy every rule of p?"""
    for rel in p.relations:
        kind, a, b = rel[0], rel[1], rel[2]
        if kind == "neq":
            if sol[a] == sol[b]:
                return False
        elif not M.RELATIONS[kind](sol[a], sol[b], *rel[3:]):
            return False
    for g in p.groups:
        vals = [sol[c] for c in g.cells]
        if g.complete and len(set(vals)) != len(vals):
            return False
        if g.total is not None and sum(vals) != g.total:
            return False
    for c in p.constraints:
        t = c["type"]
        if t == "set":
            v = sorted(sol[x] for x in c["cells"])
            if len(set(v)) != len(v) or v[-1] - v[0] != len(v) - 1:
                return False
        elif t == "equal_sum":
            if len({sum(sol[x] for x in seg) for seg in c["segments"]}) != 1:
                return False
        elif t == "arrow":
            circ = int("".join(str(sol[x]) for x in c["circle"]))
            if circ != sum(sol[x] for x in c["line"]):
                return False
        elif t in ("sum", "little_killer"):
            if sum(sol[x] for x in c["cells"]) != c["total"]:
                return False
        elif t == "table":
            if tuple(sol[x] for x in c["cells"]) not in set(map(tuple, c["allowed"])):
                return False
        elif t == "between":
            v = [sol[x] for x in c["cells"]]
            lo, hi = min(v[0], v[-1]), max(v[0], v[-1])
            if any(not lo < x < hi for x in v[1:-1]):
                return False
        elif t == "skyscraper":
            v, m, k = [sol[x] for x in c["cells"]], 0, 0
            for x in v:
                if x > m:
                    m, k = x, k + 1
            if k != c["count"]:
                return False
        elif t == "xsum":
            v = [sol[x] for x in c["cells"]]
            if sum(v[: v[0]]) != c["total"]:
                return False
        elif t == "sandwich":
            v = [sol[x] for x in c["cells"]]
            D = len(v)
            if 1 in v and D in v:
                i, j = sorted((v.index(1), v.index(D)))
                if sum(v[i + 1 : j]) != c["total"]:
                    return False
    return True


def best_first(option_lists):
    """All combinations (one item per list), in order of increasing total
    rank (sum of each item's position in its list): the text's reading first,
    then readings that deviate from it in as few / as cheap places as possible."""
    sizes = [len(o) for o in option_lists]
    for total in range(sum(sizes) - len(sizes) + 1):

        def comps(i, left):
            if i == len(sizes) - 1:
                if left < sizes[i]:
                    yield (left,)
                return
            for r in range(min(left, sizes[i] - 1) + 1):
                for rest in comps(i + 1, left - r):
                    yield (r,) + rest

        for ranks in comps(0, total):
            yield tuple(o[r] for o, r in zip(option_lists, ranks))


def infer(sp, page_text=None, max_combos=120, node_limit=20_000_000, time_budget=None, solution=None):
    """Infer what each visual element class means. Evidence, strongest first:
    (1) the embedded solution must satisfy the reading, (2) the reading must
    give exactly one solution, (3) agreement with the rules text breaks ties.
    time_budget (s): stop trying further readings after this long and keep the
    best one found so far. Returns (Puzzle, info, evidence) or (None, reason, None)."""
    import time

    sp = dict(sp, puzzle=without_nulls(sp["puzzle"]))
    t_end = time.time() + time_budget if time_budget else None
    from .. import cbackend  # noqa: F401

    p0, info0 = translate(sp, page_text)
    rules = (sp.get("meta", {}).get("rules") or "") + "\n" + (page_text or "")
    if (
        p0 is None
        and not str(info0).startswith("unsupported: ")
        or (p0 is None and "rule '" in str(info0))
        or (p0 is None and "fog" in str(info0))
        or (p0 is None and "edge text" in str(info0))
        or (
            p0 is None
            and not any(x.endswith(" line") or x.startswith("edge number") for x in str(info0)[13:].split(", "))
        )
    ):
        return None, info0, None
    P = sp["puzzle"]
    cmap = rules_color_map(rules)
    n_ = len(P.get("cells") or [])
    items = [it for it in line_items(P, n_) if it[0] != "diagonal"]
    classes = sorted({it[0] for it in items})
    hex_of = {it[0]: it[1] for it in items}
    tl = rules.lower()
    text_extra = [r for r in (diff_rule(tl),) if r and r not in ("whisper", "dutch")]
    if SLOW_ALL.search(tl):
        text_extra.append("slow_thermo")

    def prior(cname):
        tr = line_rule_from_text(hex_of[cname], cmap)
        first = [tr] if tr else list(text_extra)
        if cname == "white" and not first:
            first = ["ignore"]
        dflt = [DEFAULT_LINE[cname]] if cname in DEFAULT_LINE and not tr else []
        return first + dflt + [r for r in LINE_RULES + text_extra if r not in first + dflt]

    flags = rule_flags(rules)
    # negative-constraint readings: the rules-text set first, then none, then every marker type present
    present = set()
    if p0 is not None:
        present = ({"white", "black"} if info0.get("kropki_white") or info0.get("kropki_black") else set()) | (
            {"x", "v"} if info0.get("xv") else set()
        )
    else:
        present = {"white", "black", "x", "v"} if re.search(r"kropki|dot|\bx\b|\bv\b|xv", rules.lower()) else set()
    text_neg = frozenset(flags["negative_markers"] & present) if present else frozenset()
    neg_opts = [text_neg]
    for o in (
        frozenset(),
        frozenset(present & {"white", "black"}),
        frozenset(present & {"x", "v"}),
        frozenset(present),
    ):
        if o not in neg_opts:
            neg_opts.append(o)
    sol_s = sp.get("meta", {}).get("solution") or (sp.get("puzzle", {}).get("metadata") or {}).get("solution")
    sol = [int(ch) for ch in sol_s] if sol_s and str(sol_s).isdigit() else None
    if sol is None and solution is not None:  # externally known solution (dataset / completed replay)
        sol = [int(x) for x in solution]
    found = []
    best_possible = sum(1 for c in classes if line_rule_from_text(hex_of[c], cmap)) + 1
    has_edge_num = "edge number" in str(info0) or (
        isinstance(info0, dict) and any(k.startswith("edge_") for k in info0)
    )
    t_edge = edge_number_rule(rules)
    edge_opts = ([t_edge] if t_edge else []) + [k for k in EDGE_NUMBER_RULES if k != t_edge] if has_edge_num else [None]
    combos = best_first([prior(c) for c in classes] + [edge_opts] + [neg_opts])
    tried = 0
    for k, combo in enumerate(combos):
        if k >= max_combos or (t_end and found and time.time() > t_end):
            break
        tried += 1
        ov = dict(zip(classes, combo[: len(classes)]))
        if combo[len(classes)]:
            ov["_edgenum"] = combo[len(classes)]
        ov["_negative"] = sorted(combo[-1])
        p, info = translate(sp, page_text, ov)
        if p is None:
            _log.debug("reading %s: %s", ov, info)
            continue
        p.finalize()
        if sol is not None and len(sol) == p.N and not satisfies(p, sol):
            _log.debug("reading %s: breaks the embedded solution", ov)
            continue
        sols = _verified_solutions(p, limit=2, node_limit=node_limit)
        if len(sols) != 1:
            _log.debug("reading %s: %s solutions", ov, "no" if not sols else "several")
            continue
        if sol is not None and list(sols[0]) != sol[: p.N]:
            _log.debug("reading %s: its solution differs from the embedded one", ov)
            continue
        text_agree = (
            sum(1 for c in classes if line_rule_from_text(hex_of[c], cmap) == ov.get(c))
            + (combo[-1] == text_neg)
            + (has_edge_num and combo[len(classes)] == t_edge)
        )
        found.append((text_agree, -k, p, info, ov))
        if sol is not None or text_agree >= best_possible:
            break  # solution-confirmed or as text-consistent as any reading can be: done
    if not found:
        _log.info("none of the %d readings tried has a unique solution", tried)
        return None, "no reading with a unique solution", None
    found.sort(key=lambda x: (-x[0], -x[1]))
    best = found[0]
    evidence = ("solution" if sol is not None else "unique") + (
        "+text" if best[0] == len(classes) + 1 else (f"+partial text ({len(found)} candidate readings)")
    )
    _log.info("inferred reading %s (evidence: %s)", best[4], evidence)
    return best[2], best[3], {"evidence": evidence, "reading": best[4]}


def rebuild(sp, page_text, reading):
    """Rebuild a verified puzzle from a stored inference reading (SudokuPad or f-puzzles payload)."""
    if sp.get("format") == "fpuzzles":
        from . import _fpuz_translate as FT

        fp = sp["puzzle"]
        if fp.get("line"):
            return FT.translate(fp, reading or None) if reading else FT.infer_lines(fp)
        return FT.translate(fp)
    return translate(sp, page_text, reading)


def _verified_solutions(p, **kw):
    from .. import cpsat_verify

    return cpsat_verify.verified_solutions(p, **kw)
