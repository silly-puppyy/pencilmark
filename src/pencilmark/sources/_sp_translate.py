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
import itertools
import logging
import math
import re
from collections import Counter, defaultdict

from .. import model as M

_log = logging.getLogger(__name__)

# mechanics the engine does not model, named in a rules text: the reader refuses the puzzle rather than read its elements
# as something else (an equality cage drawn as a cage would grade as a killer cage). Both readers check these.
UNMODELLED_RULES = (
    ("fog", r"fog"),
    ("all clues true or false", r"all (?:the )?clues are (?:equally )?(?:all )?true or (?:all )?false"),
    ("chaos", r"chaos"),
    ("yin", r"\byin(?:[- ]?yang)?\b"),  # the word: "yin" also sits in "lying", "multiplying", "saying"
    (
        "shading",
        r"\bshade (?:some|any|all|every|the|exactly|a|certain)? ?(?:of the )?cells\b"
        r"|\b(?:colou?r|paint) (?:every|each|all|some)(?: of the)? cells?\b",
    ),
    ("modifier", r"modifier"),
    ("maze path", r"path through the maze|\brat run\b"),  # a route through walls (path genre): no path layer yet
    # mechanics that place or identify unknown clues / objects (LMD top-2000 misreads, classified)
    ("oil and water letters", r"\boily water\b"),
    ("pick-up sticks", r"\bstick (?:which |that )?lies on top|pick-up sticks"),
    ("multi-renban", r"multi[- ]?renban"),  # sets of consecutive digits with repeats: not the renban rule
    ("magic square", r"magic square somewhere|somewhere in the grid lies a 3 ?[x×] ?3 magic square"),
    ("unique dominoes", r"every possible domino\b"),
    ("dice", r"\broll a [^.]{0,30}dic?e\b|fold into (?:legitimate )?dice"),
    (
        "clues to place",
        r"bulbs of the lines need to be deduced|split points'?,? to be located|which line is which"
        r"|which player wins|\(to be found\)|written in invisible ink|influencer cells"
        r"|place \d+ straight (?:and vertical )?thermometers",
    ),
    (
        "digit subset",
        r"\buses? (?:\w+|\d+) of the digits\b|\btake (?:two|three|four|five|six|seven|eight|\d) \(?(?:different|distinct)?\)? ?digits from"
        r"|digit in each (?:row|column|box|house)?[^.]{0,30}does not fit|\bpick (?:two|three|four|five|six|seven|eight|\d) digits from",
    ),
    # a digit used once by all clues of a kind across the grid ("if a cage contained a 1, no other cage can")
    (
        "exclusive",
        r"(?:can ?not|cannot|may not) (?:have|contain) a repeated digit in the (?:whole |entire )?(?:puzzle|grid)"
        r"|(?:may|can|must) contain no repeated digits anywhere in the (?:puzzle|grid)",
    ),
    (
        "cage sums to find",
        r"sums must (?:be guessed|form a)|(?:cage )?sums (?:are|must be) (?:guessed|determined) by the solver",
    ),
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
    # the word, or the mechanic described ("digits in a strip in column N indicate the column in which N appears")
    ("indexing", r"indexing|indicates? (?:the|which) (?:column|row|box|position|cell)s? (?:in which|where|of)"),
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


def fog_of(P, p, idx, inside):
    """SudokuPad fog of war (docs/research/fog_mechanics.md): lit cells from FOGLIGHT cages ("foglight" or
    "foglight: r1c1,r2c1") and puzzle.foglight; triggereffect cellvalue -> foglight effects as triggers (a puzzle with
    triggers has no 3x3 reveal). None when the puzzle has no fog, or fog this reads does not cover."""
    cell_re = re.compile(r"[rR](\d+)[cC](\d+)")
    name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"

    def cells(spec):
        out = []
        for x in spec if isinstance(spec, list) else [spec]:
            if x is None:
                continue
            if isinstance(x, str):
                out += [(int(a) - 1, int(b) - 1) for a, b in cell_re.findall(x)]
            elif isinstance(x, (list, tuple)) and len(x) == 2:
                out.append((int(x[0]), int(x[1])))
        return [name(idx(c)) for c in out if inside(c)]

    lit, have = [], False
    for cg in P.get("cages") or []:
        v = str((cg or {}).get("value", "")) if isinstance(cg, dict) else ""
        if v.lower() == "foglight":
            lit += cells([tuple(x) for x in cg.get("cells") or [] if isinstance(x, (list, tuple))])
            have = True
        elif v.lower().startswith("foglight:"):
            lit += cells(v)
            have = True
    if P.get("foglight"):
        lit += cells(P["foglight"])
        have = True
    triggers = []
    for t in P.get("triggereffect") or []:
        tr, ef = (t or {}).get("trigger") or {}, (t or {}).get("effect") or {}
        if tr.get("type") != "cellvalue" or ef.get("type") != "foglight":
            return None  # another trigger kind: not read
        triggers.append({"when": cells(tr.get("cell")), "light": cells(ef.get("cells"))})
        have = True
    if not have:
        return None
    lit += [name(i) for i in p.givens]  # SudokuPad: a given lights its own cell
    fog = {"lit": sorted(set(lit), key=lambda c: (int(c[1 : c.index("c")]), int(c[c.index("c") + 1 :])))}
    if triggers:  # the setter's reveals replace the 3x3 reveal
        fog["triggers"] = [t for t in triggers if t["when"] and t["light"]]
    return fog


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
    "shifter": [
        r"shifter lines?\s*:"
    ],  # the rule's definition ("Shifter lines: ..."), not a list of the setter's series
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
    "renban": r"renban|(?<!non)(?<!non-)consecutive",
    "region_sum": r"region[- ]sum|\bsegments?\b.*\b(?:sums?|totals?|value)\b|(?:\bsums?\b|\btotal).*\b(?:box|region)|\b(?:box|region).*(?:\bsums?\b|\btotal)",
    "thermo": r"thermo|bulb",
    "dutch": r"dutch|(?:least|minimum difference of|difference of) (?:4|four)\b|\b(?:4|four) or (?:more|greater)",
    "parity": r"parity|\bodd\b.{0,40}\beven\b|\beven\b.{0,40}\bodd\b",
}


def default_evidence(kind, rules):
    """the rules text describes a default-colour meaning: a sentence about a line (or naming the rule) that matches
    DEFAULT_EVIDENCE and says it positively ("nor can it contain any consecutive digits" is no renban)"""
    rx = DEFAULT_EVIDENCE.get(kind)
    if rx is None:
        return False
    for sent in re.split(r"(?<=[.\n;])\s*", (rules or "").lower()):
        if (
            re.search(rx, sent)
            and re.search(r"\b(?:lines?|threads?|thermo\w*|renban|whispers?|zipper|region[- ]sum)\b", sent)
            and not re.search(r"\b(?:not|no|nor|never|cannot)\b|n't\b", sent)
        ):
            return True
    return False


def _alpha(hexcol):
    """the opacity of a colour ("#fff5": 0.33; no alpha: 1)"""
    h = str(hexcol or "").lstrip("#")
    return int(h[3] * 2, 16) / 255 if len(h) == 4 else int(h[6:8], 16) / 255 if len(h) == 8 else 1.0


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


# dots between two cells that the text redefines: wording -> (pattern, condition on the pair a (left / top), b with the
# pattern's groups as {0}, wording of the negative or None, label)
DOT_CUSTOM = {
    "any_operation": (
        r"dots?\b[^.]{0,80}binary operations?[^.]{0,140}result in (?:the number )?(\d+)",
        "a + b == {0} or abs(a - b) == {0} or a * b == {0} or a == {0} * b or b == {0} * a",
        r"if there is no (?:\w+ )?dot[^.]{0,80}(?:cannot|can't|can not)",
        "Operation dot",
    ),
    "square_pair": (
        r"dot means that the digits in the two neighbou?ring cells form a (?:double|two)[- ]digit square",
        "10 * a + b in {{16, 25, 36, 49, 64, 81}}",
        r"all dots are (?:in the grid|given|shown)",
        "Square dot",
    ),
    "odd_even_pair": (
        r"cells divided by a \w+ (?:bar|dot|line) contain one even (?:number |digit )?and one odd",
        "odd(a + b)",
        None,
        "Odd / even bar",
    ),
}

# lexicon: phrasings for supported mechanics that never use the rule's name
DIFF_K = re.compile(
    r"differ(?:ence)?s?\b[^.]{0,50}?(at least|>=|≥|a minimum of|more than|greater than)\s*(?:a\s+)?(\d|five|four|three|two|six|seven|eight)\b"
)
LINE_SUM = re.compile(r"\blines?\b[^.]{0,30}?\bsums? (?:up )?to (\d{1,2})\b")
DIFF_K_APART = re.compile(
    r"at least (\d|five|four|three|two|six|seven) apart|minimum difference of (\d|five|four|three|two|six|seven)\b"
)
DIFF_K_OR_MORE = re.compile(r"differ(?:ence)?s?\b (?:of|by) (\d|five|four|three|two|six|seven) or (?:more|greater)\b")
_NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
SLOW_ALL = re.compile(
    r"slow[- ]?thermo|never decrease|(?:can|may) (?:also )?repeat (?:on|along|in) (?:a |the |each )?thermo"
    r"|increase or stay the same"
)
TYPO_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
NO_BOXES = re.compile(
    r"(?:once|exactly once)(?: each)? in (?:every|each) row and (?:every |each )?column(?![^.]{0,40}(?:box|region|cage|block|nonet))"
    r"|no (?:3x3 )?box(?:es)?\b|(?:there are )?no boxes|without boxes"
)
BATTENBURG_TEXT = re.compile(r"battenburg|checkerboard")
FADED_TEXT = re.compile(r"either\b[^.]{0,80}differ by (?:1|one)\b[^.]{0,100}ratio of (?:2|two)\b")
LIAR_ZONE = re.compile(r"each cage must contain (two|2) of the (three|3) (?:numbers|digits) given")
ZONE_TEXT = re.compile(
    r"(?:numbers|digits) (?:given )?in the (?:top|upper)[- ]left (?:corner )?of (?:each|the|a) cage must appear in"
    r"|(?:numbers|digits) in the cage'?s? (?:corner|clue) must appear in (?:th(?:ose|at|e)|each) cage|\bzone sudoku\b"
    r"|each cage must contain (?:two|2) of the (?:three|3) (?:numbers|digits) given"
)
QUAD_NEG = re.compile(
    r"(?:must not|cannot|can't|may not|do not|don't) appear in (?:any of )?the (?:four|4) (?:surrounding|adjacent)"
)
QUAD_TEXT = re.compile(
    r"quadruple|(?:surrounding|touching|around|adjacent to)(?: the| that| this)? (?:four|4) cells|"
    r"(?:four|4) (?:surrounding|adjacent|touching) cells|(?:four|4) cells (?:surrounding|around) the circle|"
    r"\bquads?\s*:|(?:four|4) cells (?:the|that|this|it) (?:circle )?touch|"  # "Quads: ..." (000RL6, 000QJZ)
    r"(?:digits?|numbers?) (?:in|inside) (?:a|the) circle[^.]{0,60}\bcells? touching|in a cell touching the circle|"
    r"(?:digits?|numbers?) in (?:a|the) circle[^.]{0,40}\b(?:assigned|placed|put) (?:to|in|into) (?:one of )?the (?:surrounding|adjacent|touching) cells"
)


def diff_rule(sent):
    """'adjacent digits differ by at least K' -> whisper key (K=5 whisper, K=4 dutch, else 'whisperK'), or None."""
    if re.search(
        r"\bat most \d", sent
    ):  # a difference with an upper bound too ("at least 1, and at most 2"): no whisper
        return None
    m = DIFF_K.search(sent)
    if not m:
        m = DIFF_K_OR_MORE.search(sent) or DIFF_K_APART.search(sent)  # "a difference of 4 or more", "at least 5 apart"
        if not m:
            return None
        g = next(x for x in m.groups() if x)
        k = int(g) if g.isdigit() else _NUMW[g]
        return {5: "whisper", 4: "dutch"}.get(k, f"whisper{k}")
    k = int(m.group(2)) if m.group(2).isdigit() else _NUMW[m.group(2)]
    k += m.group(1) in ("more than", "greater than")
    return {5: "whisper", 4: "dutch"}.get(k, f"whisper{k}")


# a line rule described without its name ("a purple line contains a set of consecutive digits"); counted only in a
# sentence about a line or thread, so a cage or dot described the same way does not colour a line
RULE_DESCRIPTIONS = {
    "renban": [r"sets? of (?:non-repeating,? )?consecutive", r"arranged into a consecutive (?:sequence|set|run)", r"consecutive set", r"consecutive and non-repeating",
               r"\(non-repeating\) consecutive",
               r"\b(?:are|be|contains?|form) (?:an? )?(?:non-repeating,? )?consecutive (?:digits|numbers|values|sequence)"],
    "region_sum": [r"segments? (?:that |which )?(?:each )?(?:sum|add)s? (?:up )?to the same", r"segments with the same sum", r"(?:same|equal) (?:sums?|totals?)",
                   r"sum (?:of the digits )?(?:on|along) (?:a|the|each) [a-z ]{0,20}line is (?:equal|the same)",
                   r"is (?:equal|the same) in (?:every|each) box"],
    "thermo": [r"increase from the bulb", r"from the bulb end"],
    "between": [r"(?:numerically|strictly) between", r"between the (?:two )?(?:digits|circles|numbers) (?:in|at) ",
                r"between (?:the )?(?:two )?(?:attached )?circles"],
    "palindrome": [r"reads? the same (?:forwards?|in both)", r"same (?:forwards?|from either end)"],
    "zipper": [r"equidistant from the (?:centre|center)", r"(?:same|equal) distance from the (?:centre|center)"],
    # one-off line rules (GAS), kept as custom rules
    "same_parity": [r"all (?:numbers|digits) must be odd or all (?:numbers|digits) must be even",
                    r"(?:must be|are) (?:either )?all odd or all even", r"(?:three|all) odd digits or (?:three|all) even digits",
                    r"all of the digits on it are odd, or all of them are even", r"\bhave the same parity\b"],
    "sequence": [r"arithmetic (?:series|sequence|progression)", r"evenly spaced sequence"],
    "monotone": [r"either strictly increase or strictly decrease", r"strictly (?:increasing|increase) or strictly (?:decreasing|decrease)"],
    "three_distinct": [r"(?:(?:contains?|has) only|only (?:contains?|has)) three distinct (?:digits|numbers)"],
    "entropic": [r"exactly one low (?:digit|number) \(?1,? ?2,? ?3\)?,? one medium (?:digit|number)",
                 r"one low (?:digit|number) \(1-3\),? one (?:middle|medium) (?:digit|number)",
                 r"one high \(7,? ?8,? ?9\),? one (?:middle|medium) \(4,? ?5,? ?6\)"],
    "parity": [r"alternate in parity", r"alternating parity"],
    "doubling": [r"every (?:digit|number) that appears (?:along|on) [a-z ]{0,20}line must appear exactly twice"],
    "centre_sum": [r"(?:digit|number) in the cent(?:er|re) (?:position|cell) is the sum of the other"],
    "zigzag": [r"alternate between increasing and decreasing", r"alternately (?:increase|rise) and (?:decrease|fall)"],
    "consecutive_line": [r"(?:adjacent|neighbou?ring|next to each other|connected)[^.]{0,50}differ by (?:exactly )?(?:1|one)\b"],
    "same_digit": [r"(?:exactly|only) one distinct (?:number|digit)"],
}  # fmt: skip


# arrows whose text changes the rule (GAS): kind -> (wording, keep the sum rule too, condition on circle c and line L)
ARROW_CUSTOM = {
    "even_arrow": (r"count of even (?:numbers|digits) along the (?:path of (?:each|the) )?arrow", False,
                   "c == count(y for y in {L} if even(y))"),
    "overflowing_arrow": (r"sum of all but one of the (?:numbers|digits) along", False, "any(sum({L}) - y == c for y in {L})"),
    "less_than_arrow": (r"(?:numbers|digits) along the path of each arrow must be strictly less than the (?:number|digit) in "
                        r"the circle", False, "all(y < c for y in {L})"),
    "le_arrow": (r"sum of the (?:numbers|digits) along the path of each arrow must be less than or equal to", False,
                 "sum({L}) <= c"),
    "off_by_one_arrow": (r"must be one less than or one more than the (?:number|digit) in the circle", False,
                         "abs(sum({L}) - c) == 1"),
    "average_arrow": (r"circled cell is equal to the average of (?:all )?(?:the )?(?:numbers|digits) along the arrow", False,
                      "c * len({L}) == sum({L})"),
    "distinct_arrow": (r"(?:number in the bulb of an arrow|numbers in bulbs) indicates? (?:the number of|how many) unique "
                       r"(?:numbers|values|digits) (?:that )?appear along", False, "c == count_distinct({L})"),
    "repeating_arrow": (r"at least one of the (?:numbers|digits) along the path in each arrow must be repeated", True,
                        "count_distinct({L}) < len({L})"),
    "alternating_parity_arrow": (r"along each arrow shape, the (?:numbers|digits) \(including the circled cell\) "
                                 r"alternate in parity", True,
                                 "all(S[i] mod 2 != S[i + 1] mod 2 for i in {{1..{n}}})"),
}  # fmt: skip


def arrow_variants(p, rules, used, unknown):
    """arrows the text redefines (or adds to): custom rules over each arrow's circle c and line L"""
    t = (rules or "").lower()
    got = [k for k, v in ARROW_CUSTOM.items() if re.search(v[0], t)]
    arrows = [c_ for c_ in p.constraints if c_.get("type") == "arrow"]
    if len(got) != 1 or not arrows:
        return
    from .. import puzzle_json as PJ

    variant = got[0]
    keep, holds = ARROW_CUSTOM[variant][1:]
    name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
    for a in arrows:
        if len(a["circle"]) != 1:
            unknown.append(f"{variant} with a pill")
            return
    if not keep:
        p.constraints = [c_ for c_ in p.constraints if c_.get("type") != "arrow"]
    if re.search(r"all arrows coming from (?:that|the|a) bulb", t):  # one rule per bulb over all its arrows
        merged = {}
        for a in arrows:
            m_ = merged.setdefault(a["circle"][0], {"circle": a["circle"], "line": []})
            m_["line"] += [x for x in a["line"] if x not in m_["line"]]
        arrows = list(merged.values())
    for a in arrows:
        L = [name(i) for i in a["line"]]
        cells = {"c": [name(a["circle"][0])], "L": L}
        if "S[" in holds:  # the circle and the line as one sequence
            cells["S"] = cells["c"] + L
        PJ.add_named(p, {"type": "custom", "cells": cells,
                         "holds": holds.format(L="[L]" if len(L) == 1 else "L", n=len(L))})  # fmt: skip
    used[variant] += 1


# custom line rules: (cells per instance, 0 for the whole line; the condition on instance t; label)
LINE_CUSTOM = {
    "sequence": (3, "t[2] - t[1] == t[3] - t[2]", "Sequence line"),
    "zigzag": (3, "(t[2] - t[1]) * (t[3] - t[2]) < 0", "Alternating line"),
    "same_digit": (0, "count_distinct(t) == 1", "One-digit line"),
    "entropic2": (5, "count_distinct((x + 1) div 2 for x in t) == 5", "2-entropic line"),  # one of 12, 34, 56, 78, 9
    "monotone": (
        0,
        lambda n: f"all(t[i] < t[i + 1] for i in {{1..{n - 1}}}) or all(t[i] > t[i + 1] for i in {{1..{n - 1}}})",
        "Increasing or decreasing line",
    ),
    "doubling": (0, "all(count(y for y in t if y == x) == 2 for x in t)", "Doubling line"),
    "three_distinct": (0, "count_distinct(t) == 3", "Three-digit line"),
    "centre_sum": (0, lambda n: f"2 * t[{(n + 1) // 2}] == sum(t)" if n % 2 else "1 == 0", "Centre-sum line"),
    "almost_palindrome": (
        0,
        lambda n: f"count(i for i in {{1..{n // 2}}} if t[i] != t[{n + 1} - i]) == 1",
        "Almost palindrome",
    ),
    "consecutive_palindrome": (
        0,
        lambda n: f"all(abs(t[i] - t[{n + 1} - i]) == 1 for i in {{1..{n // 2}}})",
        "Consecutive palindrome",
    ),
}


def custom_line(p, rule, ids):
    """a line rule with no rule family on cells ids: custom rules (LINE_CUSTOM runs, same parity along the line) or
    difference pairs (neighbours one apart)"""
    from .. import puzzle_json as PJ

    name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
    if rule == "shifter":
        # shifter line: within a box neighbours share parity and polarity (low / high); across a box border exactly one
        # of the two changes; the middle digit (5 on 9x9) never on the line
        box = {c: gi for gi, g in enumerate(p.groups) if g.kind == "box" for c in g.cells}
        mid = (p.D + 1) // 2 if p.D % 2 else None
        low = lambda v: f"num({v} < {mid})" if mid else f"num({v} <= {p.D // 2})"
        same = f"a mod 2 == b mod 2 and {low('a')} == {low('b')}"
        cross = f"num(a mod 2 == b mod 2) + num({low('a')} == {low('b')}) == 1"
        no_mid = f" and a != {mid} and b != {mid}" if mid else ""
        for a, b in zip(ids, ids[1:]):
            PJ.add_named(p, {"type": "custom", "cells": {"a": [name(a)], "b": [name(b)]},
                             "holds": (same if box.get(a) == box.get(b) else cross) + no_mid, "label": "Shifter line"})  # fmt: skip
        return
    if rule == "consecutive_line":
        p.relations += [("diff", a, b, 1) for a, b in zip(ids, ids[1:])]
    elif rule.startswith("linesum"):
        PJ.add_named(p, {"type": "custom", "cells": {"t": [[name(c_) for c_ in ids]]}, "each": "t",
                         "holds": f"sum(t) == {int(rule[7:])}", "label": "Line sum"})  # fmt: skip
    elif rule == "same_parity":
        PJ.add_named(p, {"type": "custom", "cells": {"pair": [[name(a), name(b)] for a, b in zip(ids, ids[1:])]},
                         "each": "pair", "holds": "pair[1] mod 2 == pair[2] mod 2", "label": "Same-parity line"})  # fmt: skip
    else:
        k, holds, label = LINE_CUSTOM[rule]
        holds = holds(len(ids)) if callable(holds) else holds
        runs = (
            [[name(c_) for c_ in ids[i : i + k]] for i in range(len(ids) - k + 1)] if k else [[name(c_) for c_ in ids]]
        )
        if runs:
            PJ.add_named(p, {"type": "custom", "cells": {"t": runs}, "each": "t", "holds": holds, "label": label})


THERMO_PARITY = re.compile(
    r"(?:each|every) therm\w* (?:contains|has|is made of) (?:digits|numbers) of (?:a single|one|the same) parity"
)
LINE_VARIANTS = {  # a line rule the text modifies: (the rule as read, wording) -> the custom rule
    "same_parity": (("parity",), r"(?:equal|same)[- ]parity lines?"),
    "entropic2": (("entropic",), r"\b2-entropic|sets? 12, 34, 56, 78"),
    "almost_palindrome": (("palindrome",), r"palindrome[^.]{0,80}except for (?:a|one) single pair"),
    "consecutive_palindrome": (
        ("palindrome", "zipper"),
        r"equidistant from the cent(?:er|re) of (?:a|the|each) line must "
        r"be (?:1|one) away",
    ),
}

# a region sum stated per box ("the same total in each 3x3 box the line visits"): a line that leaves a box and comes back
# then has one total for both visits, which the segment rule (box borders divide the line) does not model
RS_PER_BOX = re.compile(
    r"(?:in|within) each (?:3x3 )?box|each (?:3x3 )?box (?:it|the line|they|that it) (?:visits|passes)"
)


def _described(sent):
    """line rules one sentence describes without naming them: only a sentence about a line or thread, and a region sum
    only with the boxes or regions in it ("lines of the same colour sum to the same total" is another rule)"""
    diag = not re.search(r"\b(?:lines?|threads?)\b", sent) and re.search(r"\bdiagonals?\b", sent)
    if not re.search(r"\b(?:lines?|threads?)\b", sent) and not diag:
        return []
    got = [k for k, pats in RULE_DESCRIPTIONS.items() if any(re.search(p, sent) for p in pats)]
    ls = LINE_SUM.search(sent)
    if ls and not got and not re.search(r"\bsame\b|\bequal\b|\beach (?:box|region)", sent):
        got = [f"linesum{int(ls.group(1))}"]  # a fixed total for every line of the sentence
    if diag:  # marked diagonals drawn as lines (f-puzzles): only rules about a diagonal's digit count
        got = [k for k in got if k == "three_distinct"]
    return [k for k in got if k != "region_sum" or re.search(r"\bbox(?:es)?\b|3x3|\bregions?\b", sent)]


def other_lines_rule(rules):
    """the line rule a sentence gives the lines no other sentence names ("numbers on all other lines are each a set of
    ... consecutive numbers"), or None"""
    for sent in re.split(r"(?<=[.\n])\s*", (rules or "").lower()):
        if re.search(r"\b(?:all (?:the )?other|the other|the remaining|all remaining) lines\b", sent):
            got = {k for k, pats in RULE_WORDS.items() if any(re.search(p, sent) for p in pats)} | set(_described(sent))
            if len(got) == 1:
                return got.pop()
    return None


def every_line_rule(rules):
    """the line rule a sentence gives every line ("all lines are region sum lines", "every line is a renban", "an
    arithmetic series along each line"), or None"""
    for sent in re.split(r"(?<=[.\n])\s*", (rules or "").lower()):
        if re.search(
            r"\b(?:all (?:the )?lines (?:are|act as)|every line (?:is|acts as)|(?:along|on) (?:each|every) line)\b",
            sent,
        ):
            got = {k for k, pats in RULE_WORDS.items() if any(re.search(p, sent) for p in pats)} | set(_described(sent))
            if len(got) == 1:
                return got.pop()
    return None


# yin-yang: the frame (each colour connected, no 2x2 of one colour) and the couplings between shading and digits that
# recur in setters' texts; any other sentence about shading leaves the puzzle refused
YY_WORD = re.compile(r"\byin(?:[- ]?yang)?\b")
YY_BOTH = re.compile(  # both colours connected (nurikabe / heyawake / caves connect one colour only)
    r"shaded (?:cells )?and (?:the |all )?unshaded cells|unshaded cells and (?:the |all )?shaded cells|"
    r"(?:each|both|every) colou?r|cells of (?:the same|each) colou?r|as do (?:all )?(?:the )?unshaded"
)
_YY_PAIR = re.compile(
    r"(odd|even)(?: number)?(?: digits?| numbers?| values?)?[^.,;]*? (?:are|is) (?:always )?(shaded|unshaded)"
)


def yin_yang_reading(rules):
    """the shading couplings a yin-yang rules text states -> [("cage" | "thermo" | "all", "odd" | "even", shaded?),
    ("whisper", k)] (empty: the plain frame), or None (no yin-yang, or a shading sentence not understood)"""
    text = (rules or "").lower()
    if not (YY_WORD.search(text) or (YY_BOTH.search(text) and re.search(r"2 ?x ?2|2 by 2|two by two", text))):
        return None
    if re.search(r"nurikabe|heyawake|\bcaves?\b|star battle|\bloop\b|\bislands?\b|\bpaths?\b|\byong\b", text):
        return None  # another shading genre beside it
    out = []
    for sent in re.split(r"(?<=[.\n;])\s*|\s*[•\u2022]\s*", text):
        if not re.search(
            r"\b(?:un)?shad(?:ed|e|ing)\b|\byin\b|\byang\b|\b(?:same|opposite|other|one|two|each|both|every|its|that)"
            r" colou?rs?\b|\bcolou?r (?:every|each|all|some|the (?:grid|cells))|\b(?:dark|light) cells?\b",
            sent,
        ):
            continue  # not about the shading (clue colours such as "a green line" are not)
        if re.search(r"connected|2 ?x ?2|2 by 2|two by two", sent) and not _YY_PAIR.search(sent):
            continue  # the frame
        if re.fullmatch(r"\W*yin[- ]?yang\W*(?:rules?\W*)?(?:apply\W*)?", sent.strip()):
            continue
        scope = "cage" if re.search(r"\bcages?\b", sent) else "thermo" if re.search(r"\bthermo", sent) else "all"
        pairs = _YY_PAIR.findall(sent)
        m = re.search(r"shaded cells? (?:contain|are|must be|must contain|hold)s? (?:an? |only )?(odd|even)", sent)
        if pairs:
            out += [(scope, par, col == "shaded") for par, col in pairs]
        elif m and scope == "all":
            out.append(("all-shaded", m.group(1), True))
        elif re.search(r"shaded cells? (?:act|acts|behave) as (?:a |an )?german whispers?", sent):
            out.append(("whisper", 5))
        else:
            return None
    return out


def add_yin_yang(p, specs, thermo_cells):
    """the shading frame and its couplings as rules of the puzzle (custom rules reading shaded())"""
    from .. import puzzle_json as PJ

    p.constraints.append({"type": "yin_yang", "shaded": [], "unshaded": []})
    name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
    cage_cells = sorted({c for g in p.groups if g.kind == "cage" for c in g.cells})
    for spec in specs:
        if spec[0] == "whisper":
            at = {p.coords[c]: c for c in range(p.N)}
            for c in range(p.N):
                r0, c0 = p.coords[c]
                for q in (at.get((r0, c0 + 1)), at.get((r0 + 1, c0))):
                    if q is not None:
                        PJ.add_named(p, {"type": "custom", "cells": {"a": [name(c)], "b": [name(q)]},
                                         "holds": f"not (shaded(a) and shaded(b)) or abs(a - b) >= {spec[1]}"})  # fmt: skip
            continue
        scope, par, shaded = spec
        cells = cage_cells if scope == "cage" else thermo_cells if scope == "thermo" else range(p.N)
        holds = (
            f"not shaded(a) or {par}(a)"
            if scope == "all-shaded"
            else f"not {par}(a) or {'' if shaded else 'not '}shaded(a)"
        )
        for c in cells:
            PJ.add_named(p, {"type": "custom", "cells": {"a": [name(c)]}, "holds": holds})


CLONE_TEXT = re.compile(r"\bclones?\b|identical digits in identical positions|same numbers in the same positions")


def clone_groups(colour_of):
    """clones drawn as coloured shapes: {(r, c): colour} -> per colour with two or more connected shapes, the shapes'
    cells in corresponding order ([[cells of shape 1], [cells of shape 2], ...]); None when a colour's shapes differ"""
    by = defaultdict(set)
    for rc, col in colour_of.items():
        by[col].add(rc)
    out = []
    for col, cells in by.items():
        comps, left = [], set(cells)
        while left:
            stack, comp = [left.pop()], []
            while stack:
                r, c = stack.pop()
                comp.append((r, c))
                for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if q in left:
                        left.remove(q)
                        stack.append(q)
            comps.append(sorted(comp))
        if len(comps) < 2:
            continue
        shape = lambda comp: [(r - comp[0][0], c - comp[0][1]) for r, c in comp]
        if any(shape(x) != shape(comps[0]) for x in comps[1:]):
            return None
        out.append(comps)
    return out


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
        if not re.search(r"\blines?\b", sent):  # "the gray cell with arrows pointing outward": not a line colour
            cols = [
                c
                for c in cols
                if not re.search(rf"\b{c}\w* (?:cells?|dots?|circles?|squares?|boxe?s?|cages?|regions?)\b", sent)
            ]
        if cols and re.search(
            r"lines?\b[^.]{0,40}\b(?:have|has) no (?:effect|meaning)|lines?\b[^.]{0,20}\b(?:are|is) (?:purely )?(?:decorative|cosmetic)"
            r"|lines?\b[^.]{0,60}\bdo(?:es)? not affect the puzzle|line\b[^.]{0,30}\bis for [^.]{0,60}\bonly\b|\(\w+ line\) is cosmetic"
            r"|thermo(?:meter)?s?\b[^.]{0,20}\b(?:is|are) (?:purely )?(?:cosmetic|decorative)",
            sent,
        ):
            for c in cols:  # "Blue lines have no effect on the puzzle"
                out.setdefault({"gray": "grey"}.get(c, c), "ignore")
            continue
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
    prev = ""
    for clause in re.split(r"[.!;\n]|,?\s+but\s+|\(", t):
        c = clause.strip()
        if re.search(r"\bno negative constraints?\b|\bwithout (?:any )?negative constraints?\b", c):
            continue  # "[no negative constraints]": the opposite of a negative constraint
        if re.fullmatch(r"if not,? (?:they|it) (?:don't|do not|doesn't|does not)(?: \w+)?", c):
            neg |= _marker_types(prev)  # "If two digits have an X between them, they sum to 10. If not, they don't."
            continue
        if c:
            prev = c
        if pending and c:
            pending = False
            if re.search(r"\bonly\b|\bappl", c):
                neg |= _marker_types(c)
                continue
        if c and re.search(r"negative constraint", c) and not _marker_types(c) and not re.search(r"\bno\b", c):
            pending = True
            continue
        if (
            not c
            or re.search(
                r"\bnot\s+(?:all|every|necessar)|\bnot\b.{0,30}\bnecessarily\b|all but one|\bwithin (?:a|each|the) (?:region|box|row|column)"
                r"|\b(?:inside|within|in) (?:the )?(?:odd|even|\w+[- ]numbered|marked|shaded|gr[ae]y|colou?red|highlighted)\b",  # a part only
                c,
            )
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
        if re.search(
            r"\bin (?:all|every) cases? where\b[^.]{0,60}\bconsecutive\b[^.]{0,40}\b(?:circle|dot)s? (?:is|are) (?:placed|drawn|given)",
            c,
        ):
            neg.add(
                "white"
            )  # "in all cases where two neighbouring cells contain consecutive digits, a circle is placed"
    if pending:  # a bare "negative constraint(s)" that never says which markers: all of them
        neg |= set(MARKER_TYPES)
    # "all possible dots are given" covers only dot kinds the text talks about (a black-dot puzzle has no white rule)
    if "white" in neg and not re.search(r"\bwhite\b|consecutive|differ by (?:1|one)\b", t):
        neg.discard("white")
    if "black" in neg and not re.search(r"\bblack\b|ratio|double|1 ?: ?2|2 ?: ?1", t):
        neg.discard("black")
    return neg


def rule_flags(rules):
    t = (rules or "").lower()
    neg = negative_markers(rules)
    return {
        "negative_markers": neg,
        "antiknight": bool(re.search(r"anti[- ]?knight|knight'?s move|(?:chess )?knight(?:'s)? jump", t))
        and not KNIGHT_FROM.search(t),  # "the digit in the yellow cell ... a knight's move away": not every cell
        "antiking": bool(
            re.search(
                r"anti[- ]?king|king'?s move|diagonally adjacent cells|\bno[- ]touch\b"
                r"|(?:equal|identical|same) digits?[^.]{0,30}(?:can ?not|may not|must not|never) touch[^.]{0,20}diagonal",
                t,
            )
        ),
        "nonconsec": bool(
            re.search(
                r"non-?consecutive|orthogonally adjacent cells (?:can ?not|may not|must not) (?:contain|be) consecutive"
                r"|cells that are orthogonally adjacent (?:can ?not|may not|must not) (?:contain|be) consecutive",
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


def line_rule_from_text(hexcol, cmap, drawn=()):
    """Rule for a line colour: exact colour-class match, else the nearest
    colour word in the rules text (hue within 40 degrees), else a neighbouring colour word (COLOR_NEAR) that names no
    drawn colour class (`drawn`: those lines own that word's rule)."""
    cname = color_name(hexcol)
    hue, light, sat = hls(hexcol)
    if cname == "orange" and "brown" in cmap and ("orange" not in cmap or (light < 0.55 and sat < 0.75)):
        return cmap["brown"]  # a dull dark orange is the text's brown
    if cname in cmap:
        return cmap[cname]
    if cname in ("white", "black", "grey"):
        return None
    best, bd = None, 41
    for word, rk in cmap.items():
        if word in COLOR_HUES:
            d = abs(hue - COLOR_HUES[word]) % 360
            d = min(d, 360 - d)
            if d < bd:
                best, bd = rk, d
    if best is None:  # a shade the text names by a neighbouring word (a pinkish line called purple): one such word only
        near = [cmap[w] for w in COLOR_NEAR.get(cname, ()) if w in cmap and w not in drawn]
        if len(set(near)) == 1:
            best = near[0]
    return best


# colour words a drawn colour class is also called by
COLOR_NEAR = {
    "pink": ("purple", "magenta", "violet", "red", "salmon"),
    "purple": ("pink", "magenta", "violet", "lavender"),
    "red": ("pink", "crimson", "maroon", "salmon"),
    "orange": ("brown", "peach", "amber", "gold"),
    "cyan": ("blue", "teal", "turquoise", "aqua"),
    "blue": ("cyan", "navy", "aqua", "turquoise"),
}


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


def join_branches(pieces):
    """[(colour, cells), ...] of one set rule -> the cell lists of its lines: a piece whose end lies inside another piece
    of the same colour is a branch of that line (one set); pieces meeting end to end, or crossing, stay separate"""
    lines = [[col, list(ids)] for col, ids in pieces]
    merged = True
    while merged:
        merged = False
        for i, j in itertools.permutations(range(len(lines)), 2):
            (ci, a), (cj, b) = lines[i], lines[j]
            if ci == cj and (a[0] in b[1:-1] or a[-1] in b[1:-1]):
                lines[j][1] = b + [x for x in a if x not in b]
                del lines[i]
                merged = True
                break
    return [ids for _, ids in lines]


def line_items(P, n):
    """Cell lines of the puzzle: [(colour class, hex, [cells]), ...], skipping
    decoration: lines drawn along grid lines (all waypoints on cell corners),
    and white/near-white lines that trace another line (the hollow centre of a
    'hollow' line). Full-length corner-to-corner diagonals come back with
    class 'diagonal'; lines drawn mostly along grid lines (not on corners only) with class 'offcentre' (refused)."""
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
        on_grid = sum(min(x % 1, -x % 1) < 0.1 or min(y % 1, -y % 1) < 0.1 for x, y in wp)
        if 2 * on_grid > len(wp):  # mostly on grid lines (rings drawn around clues): no cells it is read along; lines
            raw.append(("offcentre", ln.get("color"), lc))  # offset inside their cells (overlapping renbans) are lines
            continue
        raw.append((color_name(ln.get("color")), ln.get("color"), lc))
    coloured = [set(lc) for cn, _, lc in raw if cn not in ("white", "diagonal", "offcentre")]
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
    if re.search(r"\b(?:tens|units|ones|last) digit of", t):  # a digit of the product / sum: no plain reading
        return None
    for kind, pat in (
        ("max", r"(?:indicate|is|gives?) the greater (?:number|digit|value)"),
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


def numbers_on_circles(P):
    """a number drawn just off an edge circle (its baseline shifted by up to 0.2 cell) is that circle's number: moved
    onto it and merged with it, so the pair reads as one numbered dot, not a dot plus a stray cell text"""
    ov = list(P.get("overlays") or [])
    circles = [o for o in ov if isinstance(o, dict) and o.get("rounded") and "center" in o and not _text_of(o).strip()]
    near = lambda v: abs(v - round(v)) < 0.05
    drop = set()
    for o in ov:
        if not (isinstance(o, dict) and "center" in o and re.fullmatch(r"\d{1,2}", _text_of(o).strip())):
            continue
        (y, x) = o["center"]
        mid = lambda v: abs(v - math.floor(v) - 0.5) < 0.05
        if near(y) and mid(x) or mid(y) and near(x):
            continue  # at an edge's midpoint already
        for c in circles:
            cy, cx = c["center"]
            if (near(cy) != near(cx)) and abs(cy - y) <= 0.2 and abs(cx - x) <= 0.2 and id(c) not in drop:
                o.update(center=[cy, cx], rounded=True, backgroundColor=c.get("backgroundColor"))
                drop.add(id(c))
                break
    return dict(P, overlays=[o for o in ov if id(o) not in drop]) if drop else P


def translate(sp, page_text=None, overrides=None):
    """sp: decoded dict from sudokupad.fetch; page_text: the puzzle page's
    rules (e.g. the Logic Masters text) when the SudokuPad file has none.
    Returns (Puzzle, info) or (None, reason)."""
    sp = dict(sp, puzzle=numbers_on_circles(without_nulls(sp["puzzle"])))
    P = sp["puzzle"]
    meta = sp.get("meta", {})
    rules = (meta.get("rules") or "") + "\n" + (page_text or "")
    rules = rules.translate(TYPO_QUOTES)  # "king’s move": the patterns spell apostrophes plainly
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
    thermo_cells = []  # cells on thermometers (shading couplings name them)
    # killer cages (skip metadata cages)
    for cg in P.get("cages") or []:
        if not isinstance(cg, dict) or not any(isinstance(x, (list, tuple)) for x in cg.get("cells") or ()):
            continue  # no cells, or a metadata cage (`cells: [null]`, its value "title: ...")
        if str(cg.get("value", "")).lower().startswith("foglight"):
            continue  # fog of war's lit cells (read by fog_of())
        cs = [idx(tuple(x)) for x in cg["cells"] if isinstance(x, (list, tuple)) and inside(tuple(x))]
        v = cg.get("value")
        total = int(v) if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()) else None
        if cs and total is not None and ZONE_TEXT.search(rules.lower()):  # zone: the cage's number lists digits in it
            from .. import puzzle_json as PJ

            name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
            need = Counter(int(ch) for ch in str(total))
            if LIAR_ZONE.search(rules.lower()):  # two of the three listed digits appear in the cage
                ds_ = sorted(need)
                p.groups.append(M.Group(f"k{len(p.groups)}", tuple(sorted(cs)), "cage", len(cs) == n, None))
                PJ.add_named(p, {"type": "custom", "cells": {"K": [name(c_) for c_ in cs]},
                                 "holds": f"count(d for d in {ds_} if any(x == d for x in K)) == 2"})  # fmt: skip
                used["liar_zone"] += 1
                continue
            p.groups.append(M.Group(f"k{len(p.groups)}", tuple(sorted(cs)), "cage", len(cs) == n, None))
            PJ.add_named(p, {"type": "custom", "cells": {"K": [name(c_) for c_ in cs]},
                             "holds": " and ".join(f"count(x for x in K if x == {d}) >= {k}" for d, k in sorted(need.items()))})  # fmt: skip
            used["zone"] += 1
            continue
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
    attached, branches = [], []  # (circle cells, shaft cells); waypoints of arrows starting away from a circle
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
            branches.append(wp)
            continue
        shaft = [x for x in line_cells(wp) if inside(x) and x not in near[1]]
        if shaft:
            attached.append((near[1], shaft))
    # a branch starts on another arrow's shaft: each path from the circle to a tip is an arrow (the stem's cells up to
    # the fork, then the branch)
    while branches:
        left = []
        for wp in branches:
            start = cell_of(wp[0])
            stem = next(((cc, sh) for cc, sh in attached if start in sh), None)
            if stem is None:
                left.append(wp)
                continue
            own = [x for x in line_cells(wp) if inside(x) and x != start]
            attached.append((stem[0], stem[1][: stem[1].index(start) + 1] + [x for x in own if x not in stem[1]]))
        if len(left) == len(branches):
            marker_arrows = any(v[1] == "arrow" and re.search(v[0], rules.lower()) for v in MARKED_CUSTOM.values())
            in_cell = lambda w: len({cell_of(pt) for pt in w}) == 1
            unknown.extend(["arrow without circle"] * sum(1 for w in left if not (marker_arrows and in_cell(w))))
            break
        branches = left
    for cc, shaft in attached:
        p.constraints.append({"type": "arrow", "circle": [idx(c_) for c_ in cc], "line": [idx(x) for x in shaft]})
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
    dot_t = next(((k, m) for k, v in DOT_CUSTOM.items() if (m := re.search(v[0], rules.lower()))), None)
    dot_pairs = []
    layers = [
        x for x in (P.get("underlays") or []) + (P.get("overlays") or []) if isinstance(x, dict) and "center" in x
    ]
    seen_at = Counter(tuple(round(v, 2) for v in x["center"]) for x in layers)
    for lay in layers:
        cx, cy = lay["center"]
        if (
            not lay.get("borderColor")
            and _alpha(lay.get("backgroundColor")) < 0.5
            and seen_at[(round(cx, 2), round(cy, 2))] > 1
        ):
            continue  # a translucent halo drawn over another marker (a highlight, 000GSU), not a marker itself
        if (
            quad_corners
            and _text_of(lay).strip()
            and any(abs(cx - qx) < 0.3 and abs(cy - qy) < 0.3 for qx, qy in quad_corners)
        ):
            continue  # a quadruple clue digit (handled by quadruples())
        w = lay.get("width", 0)
        txt = _text_of(lay).strip()
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
        elif (
            txt and BATTENBURG_TEXT.search(rules.lower()) and abs(cx - round(cx)) < 0.15 and abs(cy - round(cy)) < 0.15
        ):
            continue  # a sum on a Battenburg marker (battenburg_corners)
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
            elif txt == "" and dot_t:  # dots the text redefines (DOT_CUSTOM): a custom rule per dotted pair
                dot_pairs.append((idx(a), idx(b)))
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
                elif re.search(r"shifter dots?\s*:", low):  # one of parity / polarity shared, never both; never 5
                    from .. import puzzle_json as PJ

                    nm = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
                    mid = (n + 1) // 2 if n % 2 else None
                    lo_ = (lambda v: f"num({v} < {mid})") if mid else (lambda v: f"num({v} <= {n // 2})")
                    holds = f"num(a mod 2 == b mod 2) + num({lo_('a')} == {lo_('b')}) == 1"
                    holds += f" and a != {mid} and b != {mid}" if mid else ""
                    PJ.add_named(p, {"type": "custom", "cells": {"a": [nm(idx(a))], "b": [nm(idx(b))]}, "holds": holds,
                                     "label": "Shifter dot"})  # fmt: skip
                    used["shifter_dot"] += 1
                else:  # a dot of another colour: its meaning is in the text, which no reading took
                    unknown.append(f"{bg} dot")
            elif re.fullmatch(r"\d{1,2}", txt):
                kind = (overrides or {}).get("_edgenum") or edge_number_rule(rules)
                low_ = rules.lower()
                if (
                    lay.get("rounded")
                    and re.search(r"white (?:dot|circle)[^.]{0,80}differen", low_)
                    and re.search(r"black (?:dot|circle)[^.]{0,80}ratio", low_)
                ):  # difference / ratio pairs: the dot's colour says which
                    kind = "ratio" if color_name(lay.get("backgroundColor")) in ("black", "grey") else "diff"
                k_ = int(txt)
                if kind == "sum":
                    p.relations.append(("sum", idx(a), idx(b), k_))
                elif kind == "diff":
                    p.relations.append(("diff", idx(a), idx(b), k_))
                elif kind == "ratio":
                    p.relations.append(("ratio", idx(a), idx(b), k_))
                elif kind == "prod":
                    p.relations.append(("prod", idx(a), idx(b), k_))
                elif kind == "max":  # the greater of the two digits: a custom rule (no rule family)
                    from .. import puzzle_json as PJ

                    nm = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
                    PJ.add_named(p, {"type": "custom", "cells": {"a": [nm(idx(a))], "b": [nm(idx(b))]},
                                     "holds": f"max(a, b) == {k_}"})  # fmt: skip
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
    if len({cn for cn, _, _ in line_items(P, n)} - {"diagonal", "offcentre"}) == 1:
        text_mentions |= described_line_rules(rules)  # "digits on a line form a consecutive set", one line colour
    all_lines = every_line_rule(rules)
    box_of = {c: gi for gi, g in enumerate(p.groups) if g.kind == "box" for c in g.cells}
    told = set()  # line colours whose meaning is logged (once per colour and reading)
    drawn_classes = {ci for ci, _, _ in line_items(P, n)}
    renban_pieces = []
    for cname, hexcol, lc in line_items(P, n):
        if cname == "offcentre":
            unknown.append("line drawn along grid lines")
            continue
        if cname == "diagonal":
            ids = [idx(x) for x in lc]
            k_ = re.search(
                r"exactly (\w+) different (?:numbers|digits) (?:will |must )?appear (?:along|on) each (?:marked )?diagonal",
                rules.lower(),
            )
            if k_ and (
                k_.group(1).isdigit() or k_.group(1) in _DIGIT_WORDS
            ):  # anti-diagonal: a count of digits, not a house
                from .. import puzzle_json as PJ

                kk = int(k_.group(1)) if k_.group(1).isdigit() else _DIGIT_WORDS[k_.group(1)]
                PJ.add_named(p, {"type": "custom", "cells": {"D": [f"r{x[0] + 1}c{x[1] + 1}" for x in lc]},
                                 "holds": f"count_distinct(D) == {kk}"})  # fmt: skip
                used["anti_diagonal"] += 1
                continue
            if re.search(r"diagonal", rules.lower()) and not any(set(g.cells) == set(ids) for g in p.groups):
                p.groups.append(M.Group(f"d{hexcol}", tuple(ids), "diag", True))
                used["diagonal"] += 1
            continue
        rule = (overrides or {}).get(cname) or line_rule_from_text(hexcol, cmap, drawn_classes)
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
        if rule is None and not cmap and default_evidence(DEFAULT_LINE.get(cname), rules):
            rule, how = DEFAULT_LINE.get(cname), "SudokuPad's default colours (the rules text names none)"
        if all_lines and cname != "diagonal" and overrides is None:
            if rule is None:
                rule, how = all_lines, "the rules text giving every line that rule"
            elif rule != all_lines:  # "all lines are region sum lines; orange lines are Dutch whispers": two rules
                unknown.append(f"{cname} line with two rules")
                continue
        if overrides is None and (cname, rule) not in told:  # infer() logs its readings instead
            told.add((cname, rule))
            _log.debug("%s line (%s): %s, by %s", cname, hexcol, rule or "unknown", how if rule else "no clue")
        if rule is None:
            unknown.append(f"{cname} line")
            continue
        if rule == "ignore":
            continue
        for var_, (from_, pat_) in LINE_VARIANTS.items():
            if rule in from_ and re.search(pat_, rules.lower()):
                rule = var_
        ids = [idx(x) for x in lc]
        loop = len(ids) > 2 and ids[0] == ids[-1]
        if rule in ("renban", "region_sum") and len(set(ids)) != len(ids):
            ids = list(dict.fromkeys(ids))  # closed loop: the start cell is drawn twice, counted once
        if rule in ("thermo", "slow_thermo"):
            thermo_cells += [c_ for c_ in ids if c_ not in thermo_cells]
            if THERMO_PARITY.search(rules.lower()):  # "each thermometer contains digits of a single parity"
                custom_line(p, "same_parity", ids)
                used["thermo_parity"] += 1
            if lc[-1] in circles and lc[0] not in circles:
                ids = ids[::-1]
            p.constraints.append({"type": "line", "kind": rule, "cells": ids})  # compiled by finalize (lt / le pairs)
        elif rule.startswith("whisper") and rule[7:].isdigit():  # "differ by at least 3": its own threshold
            p.constraints.append({"type": "line", "kind": "whisper", "cells": ids, "k": int(rule[7:])})
        elif rule == "whisper":
            p.constraints.append({"type": "line", "kind": "whisper", "cells": ids})
        elif rule == "dutch":
            p.constraints.append({"type": "line", "kind": "dutch_whisper", "cells": ids})
        elif rule == "renban":
            renban_pieces.append((hexcol, ids))
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
        elif rule == "consecutive_line":  # neighbours along the line differ by 1 (repeats allowed off the houses)
            p.relations += [("diff", a, b, 1) for a, b in zip(ids, ids[1:])]
        elif rule.startswith("linesum") or rule == "shifter":  # "numbers on blue lines sum to 20"; shifter lines
            custom_line(p, rule, ids)
        elif rule in LINE_CUSTOM:  # no rule family: custom rules over each run of cells along the line
            from .. import puzzle_json as PJ

            name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
            k, holds, label = LINE_CUSTOM[rule]
            holds = holds(len(ids)) if callable(holds) else holds
            runs = (
                [[name(c_) for c_ in ids[i : i + k]] for i in range(len(ids) - k + 1)]
                if k
                else [[name(c_) for c_ in ids]]
            )
            if runs:
                PJ.add_named(p, {"type": "custom", "cells": {"t": runs}, "each": "t", "holds": holds, "label": label})
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
    for ids in join_branches(renban_pieces):
        p.constraints.append({"type": "set", "cells": ids, "kind": "consecutive"})
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
    if dot_pairs:
        from .. import puzzle_json as PJ

        nm = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
        k_, m_ = dot_t
        pat, holds, neg_pat, label = DOT_CUSTOM[k_]
        holds = holds.format(*(m_.groups() or ()))
        pairs_ = [sorted((x, y)) for x, y in dict.fromkeys(dot_pairs)]
        PJ.add_named(p, {"type": "custom", "cells": {"P": [[nm(x), nm(y)] for x, y in pairs_]}, "each": "P",
                         "holds": f"let a = P[1], b = P[2]; {holds}", "label": label})  # fmt: skip
        if neg_pat and re.search(neg_pat, rules.lower()):  # the negative: no other orthogonal pair meets it
            PJ.add_named(p, {"type": "custom", "holds": f"(a, b) => not ({holds})", "label": label + " (negative)",
                             "scope": {"pairs": "orthogonal", "except": [[nm(x), nm(y)] for x, y in pairs_]}})  # fmt: skip
        used["dot_custom"] += 1
    neg = negative_types(flags, overrides)
    xv_def = re.search(r"\b(?:an? )?[xv]\b[^.\n]{0,30}\bsums? to (?:10|ten|5|five)\b", rules.lower())
    neg &= ({"white", "black"} if used["kropki_white"] or used["kropki_black"] else set()) | (
        {"x", "v"} if used["xv"] or xv_def else set()
    )
    # ... but a dot colour neither drawn nor defined by the text is not meant ("KROPKI: cells separated by a black dot
    # are a 1:2 ratio. ALL dots are given!": no white negative; 000MXK)
    if (
        "white" in neg
        and not used["kropki_white"]
        and not re.search(r"white (?:dot|kropki|circle)|(?:dots?|kropki)\b[^.]{0,40}consecutive", rules.lower())
    ):
        neg.discard("white")
    if (
        "black" in neg
        and not used["kropki_black"]
        and not re.search(
            r"black (?:dot|kropki|circle)|(?:dots?|kropki)\b[^.]{0,40}(?:ratio|double|twice|half)", rules.lower()
        )
    ):
        neg.discard("black")
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
        r"circled digits?.{0,40}(?:how many|exactly that many|number of)|(?:digit|number) in a ring.{0,40}how many rings|"
        r"number of times (?:a )?digits? appears? in (?:a )?circles?|(?:digit|number) n in a circle[^.]{0,40}\bappears? exactly n times",
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
    global_custom(n, p, rules, used)
    shaded_regions(P, n, p, rules, used)
    fortress_cells(P, n, p, rules, used, idx, inside)
    battenburg_corners(P, n, p, rules, used, idx)
    rossini_arrows(P, n, p, rules, used)
    marked_cells(P, n, p, rules, used, inside)
    outside_clues(P, n, p, rules, used, unknown, idx, inside)
    used["_quad_text"] = int(bool(QUAD_TEXT.search(text_rules)))
    used["_quad_neg"] = int(bool(QUAD_NEG.search(text_rules.lower())))
    quadruples(P, n, p, used, unknown, idx, inside)
    used.pop("_quad_text")
    used.pop("_quad_neg")
    unknown += [u for u in unmodelled_rules(text_rules, chaos_ok=chaos)
                if not (u == "rule 'equality cage'" and EQUALITY_TEXT.search(text_rules))]  # fmt: skip
    if EQUALITY_TEXT.search(text_rules):
        used["equality_cage"] += equality_cages(p, n)
    if CLONE_TEXT.search(text_rules):  # clones drawn as coloured shapes
        colour_of = {}
        for lay in P.get("underlays") or []:
            if not isinstance(lay, dict) or "center" not in lay or lay.get("rounded"):
                continue
            col = str(lay.get("backgroundColor") or "")
            if not col or col.lower().endswith("00") and len(col) == 9 or color_name(col) == "white":
                continue  # transparent or white: not a clone colour
            (cy, cx), w, h = lay["center"], lay.get("width", 1) or 1, lay.get("height", 1) or 1
            for r in range(int(round(cy - h / 2)), int(round(cy + h / 2))):
                for c in range(int(round(cx - w / 2)), int(round(cx + w / 2))):
                    if inside((r, c)):
                        colour_of[(r, c)] = col.lower()
        groups = clone_groups(colour_of) if colour_of else None
        if not groups and colour_of:  # clones in different colours ("each coloured shape"): one class
            groups = clone_groups(dict.fromkeys(colour_of, "any"))
        if groups:
            for comps in groups:
                p.constraints.append({"type": "clone", "regions": [[idx(rc) for rc in comp] for comp in comps]})
            unknown = [u for u in unknown if u != "rule 'clone'"]
            used["clone"] += 1
    yy = yin_yang_reading(text_rules)
    if yy is not None:  # shading read: the frame and every coupling sentence understood
        unknown = [u for u in unknown if u not in ("rule 'yin'", "rule 'shading'")]
        add_yin_yang(p, yy, thermo_cells)
        used["yin_yang"] += 1
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
    fog = fog_of(P, p, idx, inside)
    if fog is not None:  # fog of war: kept as the puzzle's fog rule (rate grades under it)
        p.fog = fog
        unknown[:] = [u for u in unknown if u != "rule 'fog'"]
    elif P.get("foglight") or P.get("triggereffect"):
        unknown.append("fog of war")
    arrow_variants(p, rules, used, unknown)
    if re.search(
        r"(?:given )?pencil ?marks? (?:represent|show|are|give) the only (?:numbers|digits|values)", text_rules.lower()
    ):
        for r_, row in enumerate(P.get("cells") or []):
            for c_, cell in enumerate(row or []):
                marks = (cell or {}).get("centremarks") if isinstance(cell, dict) else None
                if marks and inside((r_, c_)):
                    p.domains[idx((r_, c_))] &= sum(
                        1 << (int(d) - 1) for d in marks if str(d).isdigit() and 1 <= int(d) <= n
                    )
                    used["pencilmarks"] += 1
                    i_, shown = idx((r_, c_)), "".join(sorted(str(d) for d in marks))
                    # the same digits drawn as a one-cell cage's number: a label, not a cage sum
                    p.groups = [g for g in p.groups if not (g.kind == "cage" and g.cells == (i_,)
                                                            and "".join(sorted(str(g.total))) == shown)]  # fmt: skip
    colour_cells = defaultdict(list)
    for lay in P.get("underlays") or []:
        if isinstance(lay, dict) and "center" in lay and not lay.get("rounded") and (lay.get("width") or 0) >= 0.9:
            rc_ = cell_of(lay["center"])
            if inside(rc_):
                colour_cells[color_name(lay.get("backgroundColor"))].append(idx(rc_))
    unknown += text_cell_rules(p, n, text_rules, colour_cells, used)
    if re.search(
        r"cages must contain either all even (?:numbers|digits), all odd (?:numbers|digits), or exactly half",
        text_rules.lower(),
    ):
        from .. import puzzle_json as PJ

        cages = [g for g in p.groups if g.kind == "cage" and g.total is None]
        p.groups = [g for g in p.groups if g not in cages]  # areas for the rule: digits may repeat in them
        for g in cages:
            K = [f"r{p.coords[c_][0] + 1}c{p.coords[c_][1] + 1}" for c_ in g.cells]
            PJ.add_named(p, {"type": "custom", "cells": {"K": K}, "holds":
                             "let e = count(x for x in K if even(x)); e == 0 or e == len(K) or 2 * e == len(K)"})  # fmt: skip
            used["full_or_half"] += 1
    if FADED_TEXT.search(text_rules.lower()):  # a dot is consecutive OR double, whatever its colour
        from .. import puzzle_json as PJ

        dots = [
            r_
            for r_ in p.relations
            if r_[:1] == ("diff",) and r_[3:] == (1,) or r_[:1] == ("ratio",) and r_[3:] == (2,)
        ]
        p.relations = [r_ for r_ in p.relations if r_ not in dots]
        name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
        if dots:
            PJ.add_named(p, {"type": "custom", "cells": {"d": [[name(r_[1]), name(r_[2])] for r_ in dots]}, "each": "d",
                             "holds": "abs(d[1] - d[2]) == 1 or d[1] == 2 * d[2] or d[2] == 2 * d[1]",
                             "label": "Faded dot"})  # fmt: skip
            used["faded_kropki"] += 1
    if not unknown and plain_sudoku(p, n, used) and drawn_in_grid(P, n, inside) >= 3:
        unknown.append("drawn elements no rule reads")  # read as a plain sudoku, the drawing silently dropped
    if unknown:
        return None, "unsupported: " + ", ".join(sorted(set(unknown)))
    return p, {k: v for k, v in used.items() if v}


def plain_sudoku(p, n, used):
    """nothing read beyond rows, columns, standard boxes and givens (irregular regions count as read: they are often
    drawn as shading)"""
    from ..puzzle_json import BOXES

    std = {frozenset(g.cells) for g in M.standard(n, *BOXES[n]).groups if g.kind == "box"} if n in BOXES else set()
    return (
        not any(used.values())
        and not p.relations
        and not p.constraints
        and all(g.kind in ("row", "col") or (g.kind == "box" and frozenset(g.cells) in std) for g in p.groups)
        and all(d == p.full for d in p.domains)
    )


KNIGHT_FROM = re.compile(
    r"(?:digit|number)s? in the (\w+) cells? (?:may|can|must) not (?:repeat|appear)[^.]{0,40}knight'?s move"
    r"|knight'?s move away from (?:a|an|the) (?!cell\b|same\b|other\b|it\b)\w+"
)


EQUALITY_TEXT = re.compile(
    r"cages must have an equal number of low [^.]{0,60} and high [^.]{0,60}(?:and|as well as) an equal number of even"
)


def equality_cages(p, n):
    """equality cages: as many low as high digits and as many even as odd digits in each cage (the middle digit of an
    odd-sized digit range is neither low nor high, so excluded) -> custom rules, one per cage"""
    from .. import puzzle_json as PJ

    lo, hi = (n // 2, n // 2 + 1) if n % 2 == 0 else ((n - 1) // 2, (n + 3) // 2)  # 6: 1-3 / 4-6; 9: 1-4 / 6-9
    holds = (f"count(x for x in K if x <= {lo}) == count(x for x in K if x >= {hi}) and "
             "count(x for x in K if even(x)) == count(x for x in K if odd(x))")  # fmt: skip
    if n % 2:
        holds += f" and all(x != {(n + 1) // 2} for x in K)"
    k = 0
    for g in p.groups:
        if g.kind == "cage":
            PJ.add_named(p, {"type": "custom", "cells": {"K": [f"r{p.coords[c][0] + 1}c{p.coords[c][1] + 1}" for c in g.cells]},
                             "holds": holds, "label": "Equality cage"})  # fmt: skip
            k += 1
    return k


def text_cell_rules(p, n, rules, colour_cells, used):
    """rules on caged or coloured cells stated in the text: "digits in the cage are odd" (a parity clue on caged cells),
    "the cells shaded orange are the same number" (one digit; the named colour, or the only shading colour)"""
    t = (rules or "").lower()
    unresolved = []
    m = KNIGHT_FROM.search(t)
    if m:  # anti-knight from marked cells only
        want = {"gray": "grey"}.get(m.group(1) or "", m.group(1) or "")
        cells = colour_cells.get(want) or []
        if not cells:
            unresolved.append("anti-knight from marked cells")
        at = {p.coords[i]: i for i in range(p.N)}
        for i in cells:
            r, c = p.coords[i]
            for dr, dc in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
                q = at.get((r + dr, c + dc))
                if q is not None:
                    p.relations.append(("neq", min(i, q), max(i, q)))
        if cells:
            used["knight_from_cells"] = used.get("knight_from_cells", 0) + 1
    if re.search(r"full of \W?oil\W?[^.]{0,40}full of \W?water", t):  # oil and water cages
        from .. import puzzle_json as PJ

        for g in [g for g in p.groups if g.kind == "cage"]:
            by_row = {}
            for c in g.cells:
                by_row.setdefault(p.coords[c][0], []).append(f"r{p.coords[c][0] + 1}c{p.coords[c][1] + 1}")
            rows = [by_row[r] for r in sorted(by_row)]
            k = len(rows)
            holds = "all(count_distinct(x mod 2 for x in r) == 1 for r in R)"  # each row of the cage: one type
            if k > 1:  # oil (even) floats on water (odd): never an odd row above an even row
                holds += f" and all(R[i][1] mod 2 <= R[i + 1][1] mod 2 for i in {{1..{k - 1}}})"
            PJ.add_named(p, {"type": "custom", "cells": {"R": rows}, "holds": holds, "label": "Oil and water"})
        used["oil_water"] = used.get("oil_water", 0) + 1
    m = re.search(r"(?:digits|numbers) in (?:the |each |all |every )?cages? (?:are|must be) (?:all )?(odd|even)\b", t)
    if m:
        odd_m = sum(1 << (v - 1) for v in range(1, n + 1, 2))
        cells = sorted({c for g in p.groups if g.kind == "cage" for c in g.cells})
        if cells:
            _cell_clue(
                p, {"type": "parity", "parity": m.group(1)}, cells, odd_m if m.group(1) == "odd" else p.full & ~odd_m
            )
            used["cage_parity"] = used.get("cage_parity", 0) + 1
    if re.search(
        r"(?:all (?:the )?(?:killer )?cages|every (?:killer )?cage) (?:must )?(?:have|has|sums? to) the same (?:sum|total)"
        r"|sum of the (?:numbers|digits) in all (?:the )?cages (?:are|is) the same",
        t,
    ):
        from .. import puzzle_json as PJ

        totals = {g.total for g in p.groups if g.kind == "cage" and g.total is not None}
        if len(totals) == 1:  # a cage shows the common total: every cage has it (exact, and fast for the search)
            k = next(iter(totals))
            p.groups = [M.Group(g.name, g.cells, g.kind, g.complete, k) if g.kind == "cage" else g for g in p.groups]
            used["equal_cage_sums"] = used.get("equal_cage_sums", 0) + 1
        cages = [[f"r{p.coords[c][0] + 1}c{p.coords[c][1] + 1}" for c in g.cells] for g in p.groups if g.kind == "cage"]
        if len(totals) != 1 and len(cages) >= 2:  # "All killer cages must have the same sum", no total shown
            PJ.add_named(p, {"type": "custom", "cells": {"K": cages}, "holds": "count_distinct(sum(k) for k in K) == 1",
                             "label": "Equal cage sums"})  # fmt: skip
            used["equal_cage_sums"] = used.get("equal_cage_sums", 0) + 1
    if re.search(
        r"cages (?:with|without) no (?:sum|total)s?(?: given)?,? (?:have|has|must have) the same (?:sum|total)", t
    ):
        from .. import puzzle_json as PJ

        bare = [
            [f"r{p.coords[c][0] + 1}c{p.coords[c][1] + 1}" for c in g.cells]
            for g in p.groups
            if g.kind == "cage" and g.total is None
        ]
        if len(bare) >= 2:
            PJ.add_named(p, {"type": "custom", "cells": {"K": bare}, "holds": "count_distinct(sum(k) for k in K) == 1",
                             "label": "Equal sums of the cages without a total"})  # fmt: skip
            used["equal_bare_cage_sums"] = 1
        else:
            unresolved.append("cages without a total")
    m = re.search(r"cells (?:shaded|coloured|colored|marked) (\w+) (?:are|contain) the same (?:number|digit)", t)
    if m:
        from .. import puzzle_json as PJ

        want = {"gray": "grey"}.get(m.group(1), m.group(1))
        same = colour_cells.get(want) or (next(iter(colour_cells.values())) if len(colour_cells) == 1 else [])
        if len(same) >= 2:
            PJ.add_named(p, {"type": "custom", "cells": {"S": [f"r{p.coords[c][0] + 1}c{p.coords[c][1] + 1}" for c in same]},
                             "holds": "count_distinct(S) == 1", "label": f"Same digit in {want} cells"})  # fmt: skip
            used["same_colour_equal"] = used.get("same_colour_equal", 0) + 1
    return unresolved


def drawn_in_grid(P, n, inside):
    """shapes (cell-sized or smaller, without text) and lines drawn inside the grid"""
    k = 0
    for lay in (P.get("underlays") or []) + (P.get("overlays") or []):
        if (
            isinstance(lay, dict)
            and "center" in lay
            and not _text_of(lay).strip()
            and lay.get("class") != "board-position"
        ):
            w = lay.get("width") or 0
            if 0.2 <= w <= 1.0 and inside(cell_of(lay["center"])):
                k += 1
    for ln in (P.get("lines") or []) + (P.get("arrows") or []):
        wp = ln.get("wayPoints") if isinstance(ln, dict) else None
        if wp and len(wp) >= 2 and all(inside(cell_of(pt)) for pt in wp):
            k += 1
    return k


def _text_of(lay):
    """an element's text; a clue 0 stored as the number 0 is "0", not empty"""
    t = lay.get("text")
    return "" if t is None or t is False else str(t)


def _num(t):
    t = str(t if t is not None else "").strip()
    return int(t) if re.fullmatch(r"\d{1,3}", t) else None


def _texts(P):
    for lay in (P.get("overlays") or []) + (P.get("underlays") or []):
        if isinstance(lay, dict) and "center" in lay and _text_of(lay).strip():
            yield lay


def _pairs_adjacent(ds, n, ordered):
    if len(ds) != 2:
        return None
    a, b = ds
    either = "" if ordered else f" or (ray[i] == {b} and ray[i + 1] == {a})"
    return [f"any((ray[i] == {a} and ray[i + 1] == {b}){either} for i in {{1..{n - 1}}})"]


def _coast(ds, n):
    if len(ds) != 2:
        return None
    a, b = ds
    return [
        f"any((ray[j] == {a} and ray[{n + 1} - j] == {b}) or (ray[j] == {b} and ray[{n + 1} - j] == {a}) for j in {{1..3}})"
    ]


# one-off outside clues (GAS) as custom rules over the cells seen from the clue ("ray", from the clue inwards):
# kind -> (wording, the clue's digits and the row length -> conditions, or None for a clue it cannot read). Digits:
# each digit of the clue text ("12" is 1 and 2) where `split`, else the clue as one number.
OUTSIDE_CUSTOM = {
    "outside": (r"(?:must|will) appear in the first three cells|standard outside sudoku", True,
                lambda ds, n: [f"any(x == {d} for x in take(3, ray))" for d in ds]),
    "first_parity": (r"first odd or even (?:value|number|digit)", True,
                     lambda ds, n: [f"ray[position(ray, x => {'odd' if d % 2 else 'even'}(x))] == {d}" for d in ds]),
    "neighbours_ordered": (r"immediately adjacent to each other in the given order", True,
                           lambda ds, n: _pairs_adjacent(ds, n, True)),
    "neighbours": (r"immediately adjacent to each other", True, lambda ds, n: _pairs_adjacent(ds, n, False)),
    "coast": (r"first and last three cells in that (?:row|column|row or column) in symmetric", True, _coast),
    "consecutive_count": (r"number of pairs of adjacent consecutive", False,
                          lambda ds, n: [f"count(i for i in {{1..{n - 1}}} if abs(ray[i + 1] - ray[i]) == 1) == {ds[0]}"]),
    "max_min": (r"sum of the largest and (?:the )?smallest numbers? of the first three", False,
                lambda ds, n: [f"max(take(3, ray)) + min(take(3, ray)) == {ds[0]}"]),
    "median": (r"\bmedian\b", False, lambda ds, n: [f"median(take(3, ray)) == {ds[0]}"]),
    "highball": (r"either the first and second (?:numbers|digits) or the second and third", False,
                 lambda ds, n: [f"ray[1] + ray[2] == {ds[0]} or ray[2] + ray[3] == {ds[0]}"]),
    "position_max": (r"position of the largest (?:number|digit) in the first three cells", False,
                     lambda ds, n: [f"position(take(3, ray), x => x == max(take(3, ray))) == {ds[0]}"]),
    "interval_sum": (r"sum of the (?:numbers|digits) from position a to position b", False,
                     lambda ds, n: [f"let a = min(ray[1], ray[2]), b = max(ray[1], ray[2]); sum(ray[a..b]) == {ds[0]}"]),
    "sum_before_nine": (r"sum of all (?:numbers|digits) that appear before the 9", False,
                        lambda ds, n: [f"sum(take(position(ray, x => x == 9) - 1, ray)) == {ds[0]}"]),
    "next_to_nine": (r"immediately adjacent to the 9", False,
                     lambda ds, n: [f"let q = position(ray, x => x == 9); (ray[q - 1] ?? 0) + (ray[q + 1] ?? 0) == {ds[0]}"]),
}  # fmt: skip


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
    # diagonal arrows: SudokuPad arrows, or arrowheads drawn as a short line beside the clue (its first segment points)
    heads = [
        {"wayPoints": ln["wayPoints"][:2]}
        for ln in P.get("lines") or []
        if isinstance(ln, dict)
        and len(ln.get("wayPoints") or []) >= 2
        and not inside(cell_of(ln["wayPoints"][0]))
        and max(abs(x - y) for pt in ln["wayPoints"] for x, y in zip(pt, ln["wayPoints"][0])) < 0.5
    ]
    for ar in (P.get("arrows") or []) + heads:
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
            ("skyscraper", r"skyscraper|buildings? (?:can be )?\W?seen|taller buildings block"),
            (
                "frame",
                r"sum of the (?:values|digits|numbers) in the first (?:three|3|two|2|four|4) cells"
                r"|sum of the first (?:three|3|two|2|four|4) (?:numbers|digits) seen",
            ),
            ("numbered_room", r"numbered rooms?|digit x (?:in|into) the x-?th cell|in the nth cell"),
            (
                "first_seen",
                r"\b123\b|first (?:of|digit among|one of) (?:the digits )?1, ?2 (?:or|and) 3|"
                r"(?:closest|nearest) (?:1, ?2 or 3|of 1, 2 and 3)",
            ),
        )
        if re.search(pat, t)
    ]
    custom = [k for k, (pat, _, _) in OUTSIDE_CUSTOM.items() if re.search(pat, t)]
    kinds += custom[:1]  # the first that matches: "adjacent ... in the given order" before "adjacent"
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
        if kind in OUTSIDE_CUSTOM and not (r < -1 or r > n or c < -1 or c > n):
            from .. import puzzle_json as PJ

            _, split, build = OUTSIDE_CUSTOM[kind]
            text = " ".join(str(x) for x in txts)
            ds = (
                [int(ch) for ch in text if ch.isdigit()]
                if split
                else ([vals[0]] if len(vals) == 1 and vals[0] is not None else [])
            )
            conds = build(ds, n) if ds and re.fullmatch(r"[\d ]+", text) else None
            if not conds:
                unknown.append("outside clue text")
                continue
            ray = [f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}" for i in cells]
            for h in conds:
                PJ.add_named(p, {"type": "custom", "cells": {"ray": ray}, "holds": h})
            used[kind] += 1
            continue
        if r < -1 or r > n or c < -1 or c > n or len(vals) != 1 or vals[0] is None:
            unknown.append("outside clue text")
            continue
        if kind == "numbered_room":  # clue X: the digit X sits in the N-th cell, N = the first digit from the clue
            X = vals[0]
            if not 1 <= X <= n:
                unknown.append("numbered room clue")
                continue
            from .. import puzzle_json as PJ

            ray = [f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}" for i in cells]
            PJ.add_named(p, {"type": "custom", "cells": {"ray": ray}, "holds": f"ray[ray[1]] == {X}",
                             "label": "Numbered room"})  # fmt: skip
            used["numbered_room"] += 1
            continue
        if kind == "frame":  # sum frame: the first k cells seen from the clue
            k = {"two": 2, "2": 2, "three": 3, "3": 3, "four": 4, "4": 4}[
                re.search(r"first (three|3|two|2|four|4) (?:cells|numbers|digits)", t).group(1)
            ]
            p.constraints.append({"type": "sum", "cells": cells[:k], "total": vals[0]})
            used["sum_frame"] += 1
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


FORTRESS_TEXT = re.compile(
    r"fortress|(?:gr[ae]y|shaded) cells? (?:must be|is|are) (?:larger|greater|bigger|higher) than"
    r"|number in a gr[ae]y cell must be (?:larger|greater)"
)


def fortress_cells(P, n, p, rules, used, idx, inside):
    """Fortress: a digit in a grey cell is greater than the digits in its orthogonally adjacent white cells (grey
    square underlays, when the rules text says so); grey neighbours are not compared"""
    if not FORTRESS_TEXT.search((rules or "").lower()):
        return
    grey = set()
    for lay in P.get("underlays") or []:
        if not isinstance(lay, dict) or "center" not in lay or lay.get("rounded"):
            continue
        if min(lay.get("width", 0) or 0, lay.get("height", 0) or 0) < 0.8:
            continue
        if color_name(lay.get("backgroundColor") or lay.get("color") or "") == "grey" and inside(
            cell_of(lay["center"])
        ):
            grey.add(cell_of(lay["center"]))
    for r, c in grey:
        for q in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if inside(q) and q not in grey:
                p.relations.append(("lt", idx(q), idx((r, c))))
    if grey:
        used["fortress"] += 1


_NO_INVERSE = re.compile(r"absence of an? [^.]{0,40}(?:clue|arrow|marker)[^.]{0,20}(?:has no meaning|means nothing)")


def battenburg_corners(P, n, p, rules, used, idx):
    """Battenburg (checkerboard) clues: a square marker on a cell corner -> the 4 cells around it form an odd / even
    checkerboard; "all possible ... are given" -> the other windows do not (no inverse when the text says absence
    means nothing)"""
    t = (rules or "").lower()
    if not BATTENBURG_TEXT.search(t):
        return
    from ..exchange.board import battenburg_table

    marks = set()
    for lay in P.get("overlays") or []:
        if not isinstance(lay, dict) or "center" not in lay or lay.get("rounded") or lay.get("text"):
            continue
        (y, x), w = lay["center"], lay.get("width") or 0
        if (
            0.45 <= w <= 0.8
            and abs(y - round(y)) < 0.05
            and abs(x - round(x)) < 0.05
            and 0 < round(y) < n
            and 0 < round(x) < n
        ):
            marks.add((round(y), round(x)))
    if not marks:
        return
    win = lambda r, c: [idx((r - 1, c - 1)), idx((r - 1, c)), idx((r, c - 1)), idx((r, c))]
    T, F = battenburg_table(p.D, True), battenburg_table(p.D, False)
    every = bool(
        re.search(r"all (?:possible )?[a-z ]{0,25}clues? (?:have been|are) given|if there is no such mark", t)
    ) and not _NO_INVERSE.search(t)
    for r in range(1, n):
        for c in range(1, n):
            if (r, c) in marks or every:
                p.constraints.append({"type": "table", "cells": win(r, c), "allowed": T if (r, c) in marks else F})
    for lay in P.get("overlays") or []:  # "a number on a marking is the sum of its 4 cells"
        txt = str(lay.get("text", "")).strip() if isinstance(lay, dict) else ""
        if re.fullmatch(r"\d{1,2}", txt) and "center" in lay:
            y, x = lay["center"]
            if (round(y), round(x)) in marks and abs(y - round(y)) < 0.15 and abs(x - round(x)) < 0.15:
                p.constraints.append({"type": "sum", "cells": win(round(y), round(x)), "total": int(txt)})
    used["battenburg"] += 1


def rossini_arrows(P, n, p, rules, used):
    """Rossini: an arrow outside the grid -> the first three cells of that row / column increase in the arrow's
    direction ("all possible arrows are given": the other edges have none)"""
    t = (rules or "").lower()
    if not re.search(
        r"rossini|first three (?:numbers|digits|cells)[^.]{0,60}increase in the direction of the arrow", t
    ):
        return
    arrows = []
    for ln in P.get("lines") or []:
        wp = (ln or {}).get("wayPoints") or [] if isinstance(ln, dict) else []
        if len(wp) < 2:
            continue
        (y0, x0), (y1, x1) = wp[0], wp[1]
        r, c = math.floor(y0), math.floor(x0)
        dy, dx = y1 - y0, x1 - x0
        if r < 0 and 0 <= c < n and abs(dx) < 1e-6:
            arrows.append({"side": "top", "index": c + 1, "towards": "in" if dy > 0 else "out"})
        elif r >= n and 0 <= c < n and abs(dx) < 1e-6:
            arrows.append({"side": "bottom", "index": c + 1, "towards": "in" if dy < 0 else "out"})
        elif c < 0 and 0 <= r < n and abs(dy) < 1e-6:
            arrows.append({"side": "left", "index": r + 1, "towards": "in" if dx > 0 else "out"})
        elif c >= n and 0 <= r < n and abs(dy) < 1e-6:
            arrows.append({"side": "right", "index": r + 1, "towards": "in" if dx < 0 else "out"})
    if not arrows:
        return
    from .. import puzzle_json as PJ

    every = bool(re.search(r"all (?:possible )?[a-z ]{0,20}(?:arrows|clues) (?:have been|are) given", t))
    PJ.add_named(p, {"type": "rossini", "arrows": arrows, "all_given": every and not _NO_INVERSE.search(t)})
    used["rossini"] += 1


# one-off clues on marked cells (GAS): the marked cell's digit x against the cells N around it, as custom rules.
# kind -> (wording, marker, which cells: "orth" / "king" / "diag" neighbours or "ray" in the arrow's direction,
# condition; {N} is N, or [N] when N is a single cell)
MARKED_CUSTOM = {
    "sum_adjacent": (r"circled number[^.]{0,40}equal the sum of (?:all )?(?:the )?orthogonally adjacent", "circle", "orth",
                     "x == sum({N})"),
    "circle_distinct": (r"number in each circle indicates how many (?:unique|different) values appear in the (?:8|eight) "
                        r"surrounding", "circle", "king", "x == count_distinct({N})"),
    "parity_sweeper": (r"circled number indicates the total count of surrounding cells[^.]{0,40}same parity", "circle",
                       "king", "x == count(y for y in {N} if y mod 2 == x mod 2)"),
    "x_distinct": (r"marked with an x indicate how many different (?:numbers|digits) are in the four cells diagonally",
                   "x", "diag", "x == count_distinct({N})"),
    "detection": (r"arrows must appear at least once in the indicated direction", "arrow", "ray", "any(y == x for y in {N})"),
    "elimination": (r"arrows must not appear in any other cell in the indicated direction", "arrow", "ray",
                    "all(y != x for y in {N})"),
    "search_five": (r"arrow points to the closest (?:5|five)\b", "arrow", "ray", "{N}[x] == 5 and all(y != 5 for y in take(x - 1, {N}))"),
    "search_nine": (r"(?:every|each) arrow (?:is pointing|points) at (?:the )?(?:number|digit) 9|arrow points to the closest (?:9|nine)\b",
                    "arrow", "ray", "{N}[x] == 9 and all(y != 9 for y in take(x - 1, {N}))"),
    "arrow_xsum": (r"sum of the first n (?:digits|numbers) in the direction of the arrow", "arrow", "ray",
                   "x == sum(take({N}[1], {N}))"),
    "primesweeper": (r"count of cells with prime numbers[^.]{0,40}direction the arrow points", "arrow", "ray",
                     "x == count(y for y in {N} if prime(y))"),
}  # fmt: skip
_STEPS = {"orth": [(0, 1), (1, 0), (0, -1), (-1, 0)], "diag": [(1, 1), (1, -1), (-1, 1), (-1, -1)]}
_STEPS["king"] = _STEPS["orth"] + _STEPS["diag"]


def _cell_markers(P, n, inside):
    """{"circle" | "arrow" | "x": [(cell, direction or None)]}: white circles centred in cells, and small drawings
    inside one cell: an X (points out in three or more quadrants) or an arrow (pointing at its farthest point; a closed
    outline at its head)"""
    out = defaultdict(list)
    for lay in (P.get("underlays") or []) + (P.get("overlays") or []):
        if isinstance(lay, dict) and lay.get("rounded") and "center" in lay and not _text_of(lay).strip():
            (cy, cx), w = lay["center"], lay.get("width") or 0
            if 0.6 <= w <= 1.0 and abs(cy % 1 - 0.5) < 0.1 and abs(cx % 1 - 0.5) < 0.1 and inside(cell_of((cy, cx))):
                out["circle"].append((cell_of((cy, cx)), None))
    for ar in P.get("arrows") or []:  # an arrow (with a head) drawn inside one cell points from its tail to its tip
        wp = ar.get("wayPoints") if isinstance(ar, dict) else None
        if wp and len(wp) >= 2 and len({cell_of(pt) for pt in wp}) == 1 and inside(cell_of(wp[0])):
            dy, dx = wp[-1][0] - wp[0][0], wp[-1][1] - wp[0][1]
            if math.hypot(dy, dx) > 0.1:
                ang = round(math.atan2(dy, dx) / (math.pi / 4)) % 8
                out["arrow"].append(
                    (cell_of(wp[0]), [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)][ang])
                )
    for ln in P.get("lines") or []:
        wp = ln.get("wayPoints") if isinstance(ln, dict) else None
        if not wp or len(wp) < 2 or len({cell_of(pt) for pt in wp}) != 1 or not inside(cell_of(wp[0])):
            continue
        r, c = cell_of(wp[0])
        off = [(y - r - 0.5, x - c - 0.5) for y, x in wp]
        far = [(dy, dx) for dy, dx in off if math.hypot(dy, dx) > 0.25]
        if not far:
            continue
        closed = len(wp) >= 6 and math.dist(wp[0], wp[-1]) < 1e-6
        if closed:  # a filled arrow outline: the head is the vertex between the two longest edges (the head's sides)
            pts = off[:-1]
            edge = lambda i: math.dist(pts[i], pts[(i + 1) % len(pts)])
            dy, dx = pts[max(range(len(pts)), key=lambda i: edge(i - 1) + edge(i))]
        elif len({(dy > 0, dx > 0) for dy, dx in far}) >= 3:
            out["x"].append(((r, c), None))
            continue
        else:
            dy, dx = max(off, key=lambda v: math.hypot(*v))
        ang = round(math.atan2(dy, dx) / (math.pi / 4)) % 8
        out["arrow"].append(((r, c), [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)][ang]))
    return out


def marked_cells(P, n, p, rules, used, inside):
    t = (rules or "").lower()
    kinds = [k for k, v in MARKED_CUSTOM.items() if re.search(v[0], t)]
    if len(kinds) != 1:
        return
    from .. import puzzle_json as PJ

    kind = kinds[0]
    _, marker, which, holds = MARKED_CUSTOM[kind]
    name = lambda rc: f"r{rc[0] + 1}c{rc[1] + 1}"
    for (r, c), d in _cell_markers(P, n, inside).get(marker, []):
        if which == "ray":
            N, (y, x) = [], (r + d[0], c + d[1])
            while inside((y, x)):
                N.append(name((y, x)))
                y, x = y + d[0], x + d[1]
        else:
            N = [name((r + dy, c + dx)) for dy, dx in _STEPS[which] if inside((r + dy, c + dx))]
        if not N:
            continue
        PJ.add_named(p, {"type": "custom", "cells": {"x": [name((r, c))], "N": N},
                         "holds": holds.format(N="[N]" if len(N) == 1 else "N")})  # fmt: skip
        used[kind] += 1


def shaded_regions(P, n, p, rules, used):
    """Extra all-different regions drawn as shading (asterisk, windoku, centre dot, 'grey regions'), only when the
    rules text names such regions. Square underlays (>= 0.8 cell) grouped by colour: a rectangle covering exactly n
    cells is a region; otherwise a colour's cells form one region (n cells) or n-cell connected pieces."""
    if not REGION_TEXT.search((rules or "").lower()):
        return
    by = defaultdict(list)
    for lay in P.get("underlays") or []:
        if not isinstance(lay, dict) or "center" not in lay or lay.get("rounded") or _text_of(lay).strip():
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


_DIGIT_WORDS = {w: i + 1 for i, w in enumerate("one two three four five six seven eight nine".split())}
_DIGIT_WORDS.update(
    {"ones": 1, "twos": 2, "threes": 3, "fours": 4, "fives": 5, "sixes": 6, "sevens": 7, "eights": 8, "nines": 9}
)


def _box_triples(n):
    """the three-cell rows and columns inside each 3x3 box (9x9)"""
    nm = lambda r, c: f"r{r + 1}c{c + 1}"
    out = []
    for br in range(0, n, 3):
        for bc in range(0, n, 3):
            out += [[nm(br + i, bc + j) for j in range(3)] for i in range(3)]
            out += [[nm(br + i, bc + j) for i in range(3)] for j in range(3)]
    return out


def global_custom(n, p, rules, used=None):
    """one-off whole-grid rules (GAS) stated only in the text, as scoped custom rules -> the kinds added"""
    from .. import puzzle_json as PJ

    t = (rules or "").lower()
    found = []
    m = re.search(r"all (\w+) are encaged by (odd|even) (?:numbers|digits)", t)
    if m and m.group(1) in _DIGIT_WORDS:
        d, par = _DIGIT_WORDS[m.group(1)], m.group(2)
        found.append(
            (
                "encaged",
                {
                    "holds": f"(a, b) => (a != {d} or {par}(b)) and (b != {d} or {par}(a))",
                    "scope": {"pairs": "orthogonal"},
                },
            )
        )  # as pairs: a neighbours table is 9^5 rows a cell
    if re.search(
        r"(?:may not|cannot|can't|must not) (?:exist )?(?:be )?a run of three or more cells[^.]{0,120}same parity", t
    ):
        same = "w => not (all(odd(x) for x in w) or all(even(x) for x in w))"
        found += [("no_three_parity", {"holds": same, "scope": {"windows": [1, 3]}}),
                  ("no_three_parity", {"holds": same, "scope": {"windows": [3, 1]}})]  # fmt: skip
    if re.search(r"no two (?:numbers|digits) in adjacent cells can sum to (?:exactly )?10 or 5", t):
        found.append(("anti_xv", {"holds": "(a, b) => a + b != 10 and a + b != 5", "scope": {"pairs": "orthogonal"}}))
    if re.search(
        r"(?:no|cannot be any) four[- ]cell intersections? where the (?:numbers|digits) form a\W{0,2}checkerboard", t
    ):
        chk = "w => not (w[1] mod 2 == w[4] mod 2 and w[2] mod 2 == w[3] mod 2 and w[1] mod 2 != w[2] mod 2)"
        found.append(("anti_battenburg", {"holds": chk, "scope": {"windows": [2, 2]}}))
    if n == 9 and re.search(r"three (?:horizontally|vertically) adjacent cells[^.]{0,80}divisible by three", t):
        found.append(("box_triples_mod3", {"cells": {"t": _box_triples(n)}, "each": "t", "holds": "sum(t) mod 3 == 0"}))
    nm = lambda r, c: f"r{r + 1}c{c + 1}"
    m = re.search(r"180[- ]degrees?[^.]{0,60}\bsum to (\d+)", t)
    if m:  # "cells 180 degree rotation apart sum to 10"
        prs = [
            [nm(r, c), nm(n - 1 - r, n - 1 - c)] for r in range(n) for c in range(n) if (r, c) < (n - 1 - r, n - 1 - c)
        ]
        found.append(("rotational_sum", {"cells": {"d": prs}, "each": "d", "holds": f"d[1] + d[2] == {m.group(1)}"}))
    if re.search(
        r"(?:180[- ]?(?:°|degrees?)|rotational(?:ly)?) symmetric(?:al)?[^.]{0,40}(?:cannot|can't|may not|must not) (?:have|contain) the same digit",
        t,
    ):
        prs = [  # "cells that are 180° symmetric to each other cannot have the same digits"
            [nm(r, c), nm(n - 1 - r, n - 1 - c)] for r in range(n) for c in range(n) if (r, c) < (n - 1 - r, n - 1 - c)
        ]
        found.append(("rotational_neq", {"cells": {"d": prs}, "each": "d", "holds": "d[1] != d[2]"}))
    if (
        n == 9
        and re.search(r"\b159\b", t)
        and re.search(r"columns? 1,? 5,? and 9|column 1 (?:indicates|gives|shows)", t)
    ):
        # 159: the digit in column 1 / 5 / 9 of a row is the column of the 1 / 5 / 9 in that row
        rows = [[nm(r, c) for c in range(n)] for r in range(n)]
        found.append(
            ("159", {"cells": {"R": rows}, "each": "R", "holds": "R[R[1]] == 1 and R[R[5]] == 5 and R[R[9]] == 9"})
        )
    if re.search(
        r"(?:digits?|cells?) (?:inside|in) a cage can ?not be orthogonally adjacent (?:with|to) a consecutive digit", t
    ):
        caged = {c for g in p.groups if g.kind == "cage" for c in g.cells}
        at = {p.coords[i]: i for i in range(p.N)}
        for i in sorted(caged):  # a caged digit and its orthogonal neighbours are not consecutive
            r, c = p.coords[i]
            for q in (at.get((r, c + 1)), at.get((r + 1, c)), at.get((r, c - 1)), at.get((r - 1, c))):
                if q is not None and (q not in caged or q > i):
                    p.relations.append(("nonconsec", min(i, q), max(i, q)))
        found.append(("cage_nonconsecutive", None))
    m = re.search(
        r"(?:digits|numbers) may not repeat in any 3 ?x ?3 area centred on (?:a|an) (\d)|centered on (?:a|an) (\d)", t
    )
    if m and re.search(r"may not repeat in any 3 ?x ?3 area", t):
        d = int(m.group(1) or m.group(2))
        found.append(
            ("no_repeat_around", {"holds": f"(x, N) => x != {d} or all_different(N)", "scope": {"neighbours": "king"}})
        )
    for kind, rule in found:
        if rule is None:
            if used is not None:
                used[kind] += 1
            continue
        PJ.add_named(p, {"type": "custom", **rule})
        if used is not None:
            used[kind] += 1
    return [k for k, _ in found]


def global_rules(n, p, rules, used):
    """Whole-grid rules stated only in the text.
    Global entropy: every 2x2 area holds a low, a middle and a high digit (thirds of 1..n).
    Dutch flats / flatmates: every A has a B directly above it or a C directly below it ('every 5 ... 1 above ... 9 below')."""

    t = (rules or "").lower()
    if n % 3 == 0 and re.search(
        r"global entropy|every 2 ?[x×] ?2[^.]{0,140}(?:low|entrop)|each 2 ?[x×] ?2[^.]{0,140}(?:low|entrop)", t
    ):
        from .. import puzzle_json as PJ

        PJ.add_named(p, {"type": "global_entropy"})  # the named rule (one table definition for every source)
        used["global_entropy"] += 1
    m = None
    if re.search(
        r"dutch flat|flat ?mate", t
    ):  # the sentence with every / above / below: its first three digits = A, B, C
        for sent in re.split(r"(?<=[.!\n])\s*", t):  # not at ';': "All 5's must have EITHER; a '1' directly above"
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
        if not isinstance(lay, dict) or "center" not in lay or _text_of(lay).strip():
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
                    "cell"
                    if lay.get("_cell")
                    else "circle"
                    if lay.get("rounded")
                    else "diamond"
                    if lay.get("angle") == 45
                    else "square",
                    color_name(lay.get("backgroundColor") or lay.get("borderColor")),
                    idx(rc),
                )
            )
    if not shapes or len(shapes) > n * n * 3 // 4:  # more is decorative shading
        return
    odd = sum(1 << (v - 1) for v in range(1, n + 1, 2))
    # clauses: sentences, then ", (and)" outside braces ("orange circles contain {1, 2, 3}, blue squares {4, 5, 6}")
    clauses = [
        c_
        for sent in re.split(r"(?<=[.\n;])\s*", t)
        for c_ in re.split(r",(?!\s*(?:and\s+|or\s+)?\d)\s*(?:and\s+)?(?![^{]*\})", sent)
    ]
    for sent in clauses:
        if re.search(r"count|number of|how many|sum|total|lots", sent):
            continue
        shp = [s_ for s_ in ("circle", "square", "diamond") if re.search(rf"\b{s_}s?\b", sent)]
        dset = re.search(r"\{\s*(\d(?:\s*,\s*\d)+)\s*\}", sent) or re.search(
            r"\b(\d'?s(?:,? (?:and |or )?\d'?s)+) (?:are|is) (?:marked|shown|placed|drawn) (?:with|in|by)", sent
        )  # "1s, 2s, and 3s are marked with circles"
        gt = re.search(
            r"\b(?:are|must be|contain (?:digits|numbers)) (greater|larger|higher|bigger|less|smaller|lower) than (\d)",
            sent,
        )
        if gt and not dset:  # "red cells are greater than 5": a digit set by colour or shape
            k_ = int(gt.group(2))
            ds_ = [
                v
                for v in range(1, n + 1)
                if (v > k_ if gt.group(1) in ("greater", "larger", "higher", "bigger") else v < k_)
            ]
            col_ = {{"gray": "grey"}.get(c, c) for c in COLOR_WORDS if re.search(rf"\b{c}\b", sent)}
            got = [c for kind, col, c in shapes if (not shp or kind in shp) and (not col_ or col in col_)]
            if ds_ and got and (shp or col_):
                _cell_clue(p, {"type": "digit_class", "digits": "".join(map(str, ds_))}, got,
                           sum(1 << (v - 1) for v in ds_))  # fmt: skip
                used["digit_set_cells"] += len(got)
                continue
        if shp and dset and len(shp) == 1:  # "blue squares contain numbers from {4, 5, 6}"
            ds = [int(x) for x in re.findall(r"\d", dset.group(1))]
            col_ = {{"gray": "grey"}.get(c, c) for c in COLOR_WORDS if re.search(rf"\b{c}\b", sent)}
            m_ = sum(1 << (v - 1) for v in ds if 1 <= v <= n)
            got = [c for kind, col, c in shapes if kind == shp[0] and (not col_ or col in col_)]
            if got:
                _cell_clue(p, {"type": "digit_class", "digits": "".join(map(str, ds))}, got, m_)
                used["digit_set_" + shp[0]] += len(got)
            continue
        par = [s_ for s_ in ("odd", "even") if re.search(rf"\b{s_}\b", sent)]
        cols = {{"gray": "grey"}.get(c, c) for c in COLOR_WORDS if re.search(rf"\b{c}\b", sent)} & {
            s_[1] for s_ in shapes
        }
        if not shp and cols and re.search(r"\bcells?\b", sent):  # 'digits in grey cells are odd': any shape, by colour
            shp = ["circle", "square", "cell"]
        if not shp or len(par) != 1 or (len(shp) > 1 and not cols):
            continue
        for kind in shp:
            got = [c for k_, col, c in shapes if k_ == kind and (not cols or col in cols)]
            if got:
                _cell_clue(p, {"type": "parity", "parity": par[0]}, got, odd if par[0] == "odd" else p.full & ~odd)
                used[par[0] + "_" + kind] += len(got)


def _cell_clue(p, rule, cells, mask):
    """a graphical cell clue (parity, digit class): the cells' candidates narrowed and the clue kept as a rule, so it
    is written as a cell rule, not as given candidates"""
    for c in cells:
        p.domains[c] &= mask
    p.cell_clues = getattr(p, "cell_clues", []) + [(dict(rule, cells=list(cells)), {c: mask for c in cells})]


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

        if used.get("_quad_neg"):  # exclusion: the circle's digits appear in none of the four cells (custom rule)
            name = lambda i: f"r{p.coords[i][0] + 1}c{p.coords[i][1] + 1}"
            PJ.add_named(p, {"type": "custom", "cells": {"Q": [name(c_) for c_ in cs]},
                             "holds": " and ".join(f"all(x != {d} for x in Q)" for d in need)})  # fmt: skip
            used["exclusion"] += 1
            continue
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
