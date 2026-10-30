"""Group-agnostic puzzle model.

A puzzle is cells (with 2D coordinates, used only for group-shape scoring),
digits 1..D, and constraints. Nothing downstream assumes rows/columns/boxes:

  houses    -- groups of exactly D cells that must contain every digit once
               (rows, cols, boxes, jigsaw regions, full diagonals, windoku
               windows, every sub-grid unit of a samurai...)
  cages     -- all-different groups smaller than D, optionally with a sum
               (killer cages)
  relations -- pairwise constraints between specific cells: 'neq' (anti-knight,
               anti-king, ...), 'nonconsec' (|a-b| != 1)
  domains   -- per-cell allowed-digit masks (odd/even shading, etc.)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def bit(d: int) -> int:
    return 1 << (d - 1)


def popcount(m: int) -> int:
    return bin(m).count("1")


def digits_of(m: int):
    d = 1
    while m:
        if m & 1:
            yield d
        m >>= 1
        d += 1


def shape_ratio(coords) -> float:
    """Radius of gyration of a cell set relative to the most compact (square)
    arrangement of the same number of cells. 1.0 = square, larger = more
    spread out (a 9-cell row is ~2.24). Same formula as the C# pencilmark."""
    n = len(coords)
    if n <= 1:
        return 1.0
    mx = sum(x for x, _ in coords) / n
    my = sum(y for _, y in coords) / n
    sq = sum(x * x + y * y for x, y in coords) / n
    rg = math.sqrt(max(sq - mx * mx - my * my, 0.0))
    min_rg = math.sqrt((n - 1) / 6)
    return rg / min_rg if min_rg else 1.0


@dataclass
class Group:
    name: str
    cells: tuple
    kind: str  # 'row' 'col' 'box' 'region' 'diag' 'window' 'cage' ...
    complete: bool  # True = house (contains every digit exactly once)
    total: int | None = None  # killer cage sum
    shape: float = 1.0


# pairwise rules ok(value_a, value_b, *args) -> allowed?
RELATIONS = {
    "nonconsec": lambda v, w: abs(v - w) != 1,
    "lt": lambda v, w: v < w,  # thermo step, greater-than sign
    "diffge": lambda v, w, k: abs(v - w) >= k,  # German whisper (k=5), Dutch (k=4)
    "diffle": lambda v, w, k: abs(v - w) <= k,  # renban relaxation
    "diff": lambda v, w, k: abs(v - w) == k,  # kropki white dot (k=1)
    "notdiff": lambda v, w, k: abs(v - w) != k,
    "ratio": lambda v, w, k: v == k * w or w == k * v,  # kropki black dot (k=2)
    "notratio": lambda v, w, k: v != k * w and w != k * v,
    "sum": lambda v, w, s: v + w == s,  # XV
    "notsum": lambda v, w, s: v + w != s,
    "eq": lambda v, w: v == w,  # palindrome
    "neqval": lambda v, w: v != w,
    "samegroup3": lambda v, w: (v - 1) // 3 == (w - 1) // 3,  # entropic, 3 apart
    "diffgroup3": lambda v, w: (v - 1) // 3 != (w - 1) // 3,  # entropic, 1-2 apart
    "le": lambda v, w: v <= w,  # slow thermo step
    "parity": lambda v, w: (v - w) % 2 == 1,  # parity line: adjacent digits differ in parity
    "diffmod3": lambda v, w: (v - w) % 3 != 0,  # modular line, 1-2 apart
    "samemod3": lambda v, w: (v - w) % 3 == 0,  # modular line, 3 apart
    # any 2-cell rule given by its allowed digit pairs (a generic 2-cell "table" was solved as costly table logic;
    # as a relation it is read like a dot) -- args = ([[v, w], ...],)
    "allowed": lambda v, w, pairs: [v, w] in pairs,
    # incomplete / ambiguous clue type: any of several pair rules, args = ((kind, *args), ...), e.g. a dot
    # that is white or black: ("anyof", a, b, ("diff", 1), ("ratio", 2))
    "anyof": lambda v, w, *alts: any(RELATIONS[a[0]](v, w, *a[1:]) for a in alts),
    # shifted digit universe (digit_set puzzles store digit k as k + off): a pair rule on the true digits,
    # e.g. a black dot over 0-9 stored +1: ("shift", a, b, 1, ("ratio", 2))
    "shift": lambda v, w, off, rule: RELATIONS[rule[0]](v - off, w - off, *rule[1:]),
}

# line rules (Puzzle.constraints {"type": "line", "kind": ..., "cells": [ordered], params}); compiled
# by finalize() into pair relations / n-ary constraints, recognised as lines by the C++ core
LINE_KINDS = (
    "thermo",
    "slow_thermo",
    "whisper",
    "dutch_whisper",
    "renban",
    "palindrome",
    "entropic",
    "kropki_chain",
    "region_sum",
    "parity",
    "between",
    "modular",
    "zipper",
)
PAIRWISE_LINE_KINDS = {
    "thermo",
    "slow_thermo",
    "whisper",
    "dutch_whisper",
    "palindrome",
    "entropic",
    "kropki_chain",
    "parity",
    "modular",
}


@dataclass
class Puzzle:
    D: int
    coords: list
    groups: list = field(default_factory=list)
    relations: list = field(default_factory=list)  # (kind, a, b)
    domains: list | None = None
    givens: dict = field(default_factory=dict)
    name: str = ""
    # n-ary constraints (handled by the C++ core, csolver/), dicts:
    #   {"type":"sum", "cells":[..], "total":int, "distinct":bool(optional)}
    #   {"type":"arrow", "circle":[..], "line":[..]}   circle read as a number, left to right
    #   {"type":"equal_sum", "segments":[[..], [..], ...]}
    #   {"type":"set", "cells":[..], "kind":"consecutive"}
    #   {"type":"table", "cells":[..], "allowed":[tuples]}
    #   {"type":"little_killer", "cells":[..], "total":int}   (= sum, digits may repeat)
    #   outside clues, cells listed from the clue inwards:
    #   {"type":"sandwich", "cells":[..], "total":int}   sum strictly between the 1 and the D
    #   {"type":"xsum", "cells":[..], "total":int}       first k cells sum, k = first digit
    #   {"type":"skyscraper", "cells":[..], "count":int} visible (prefix-maximum) digits
    #   {"type":"count", "cells":[..], "each":k}  or  {"type":"count", "cells":[..], "digits":{v: k, ...}}
    #       every digit (or each listed digit) exactly k times (Double Sudoku rows: each=2).
    #       Cells under a count rule must NOT also be put in an all-different Group.
    #   {"type":"line", "kind": one of LINE_KINDS, "cells":[ordered], params}  (thermo: bulb first;
    #       whisper "k" (default 5/4); kropki_chain "dots": ["white"|"black", ...] per adjacent pair)
    #   {"type":"between", "cells":[circle, ..., circle]}  middle digits strictly between the ends
    #   "offset": k on "sum" / "little_killer" / "equal_sum": the rule is on (digit - k) (shifted universes:
    #       a digit_set puzzle over 0-9 stores digit d as d + 1 -> offset 1)
    #   {"type":"distinct_count", "cells":[..], "count":k}  exactly k different digits among the cells
    #   {"type":"contains", "cells":[source, ..]}  the source digit appears in at least one other listed cell
    #   {"type":"digit_set", "houses":[[cells], ...], "n":N}  the solver picks N digits from the universe
    #       1..D (e.g. "select 6 digits from 0-9": D = 10, digit k stored as k + 1); every listed house
    #       holds exactly that set. The houses themselves are all-different Groups with complete=False.
    constraints: list = field(default_factory=list)

    def __post_init__(self):
        self.N = len(self.coords)
        self.full = (1 << self.D) - 1
        if self.domains is None:
            self.domains = [self.full] * self.N

    # ---- derived structure, built once ----
    def _compile_lines(self):
        """{"type":"line"} constraints -> pair relations (kept for correctness)
        and n-ary constraints (renban / region sum / between / zipper)."""
        for con in list(self.constraints):
            if con.get("type") != "line" or con.get("_compiled"):
                continue
            con["_compiled"] = True
            kind, ids = con["kind"], list(con["cells"])
            adj = list(zip(ids, ids[1:]))
            R = self.relations
            if kind == "thermo":
                R += [("lt", a, b) for a, b in adj]
            elif kind == "slow_thermo":
                R += [("le", a, b) for a, b in adj]
            elif kind in ("whisper", "dutch_whisper"):
                k = con.get("k", 5 if kind == "whisper" else 4)
                R += [("diffge", a, b, k) for a, b in adj]
            elif kind == "palindrome":
                R += [("eq", ids[k], ids[-1 - k]) for k in range(len(ids) // 2) if ids[k] != ids[-1 - k]]
            elif kind == "entropic" and self.D != 9 and self.D % 3 == 0:
                # low / middle / high = equal thirds of 1..D (6x6: {1,2} {3,4} {5,6}, as setters state it);
                # the fixed {1-3} {4-6} {7-9} relations below made every 6x6 entropic line unsolvable
                g = lambda v: (v - 1) * 3 // self.D
                for k in range(len(ids)):
                    for j in range(k + 1, min(k + 3, len(ids))):
                        self.constraints.append(
                            {
                                "type": "table",
                                "cells": [ids[k], ids[j]],
                                "allowed": [
                                    (v, w) for v in range(1, self.D + 1) for w in range(1, self.D + 1) if g(v) != g(w)
                                ],
                            }
                        )
            elif kind == "entropic":  # 9x9, and sudoku.coach's fixed classes on sizes not divisible by 3
                for k in range(len(ids)):
                    for j in range(k + 1, min(k + 4, len(ids))):
                        R.append(("samegroup3" if j - k == 3 else "diffgroup3", ids[k], ids[j]))
            elif kind == "modular":
                for k in range(len(ids)):
                    for j in range(k + 1, min(k + 4, len(ids))):
                        R.append(("samemod3" if j - k == 3 else "diffmod3", ids[k], ids[j]))
            elif kind == "parity":
                R += [("parity", a, b) for a, b in adj]
            elif kind == "kropki_chain":
                dots = con.get("dots") or ["white"] * len(adj)
                for (a, b), dt in zip(adj, dots):
                    R.append(("ratio", a, b, 2) if dt == "black" else ("diff", a, b, 1))
            elif kind == "renban":
                self.constraints.append({"type": "set", "cells": ids, "kind": "consecutive", "line_kind": kind})
            elif kind == "between":
                self.constraints.append({"type": "between", "cells": ids, "line_kind": kind})
            elif kind == "zipper":
                n = len(ids)
                segs = [[ids[k], ids[n - 1 - k]] for k in range(n // 2)]
                if n % 2:
                    segs.append([ids[n // 2]])
                self.constraints.append({"type": "equal_sum", "segments": segs, "line_kind": kind})
            elif kind == "region_sum":
                # segments break only at box / region borders (not diagonals, windows, size-D cages)
                box = {
                    c: gi
                    for gi, g in enumerate(self.groups)
                    if g.complete and g.kind in ("box", "region", "jigsaw")
                    for c in g.cells
                }
                segs, cur = [], [ids[0]]
                for c in ids[1:]:
                    if box.get(c) == box.get(cur[-1]):
                        cur.append(c)
                    else:
                        segs.append(cur)
                        cur = [c]
                segs.append(cur)
                if len(segs) > 1:
                    self.constraints.append({"type": "equal_sum", "segments": segs, "line_kind": kind})
            else:
                raise ValueError(f"unknown line kind {kind!r}")

    def _compile_clones(self):
        """{"type": "clone", "regions": [[cells], [cells], ...]} (same shape, corresponding cells in the
        same order): corresponding cells hold equal digits -> 'eq' pair relations."""
        for con in self.constraints:
            if con.get("type") != "clone" or con.get("_compiled"):
                continue
            con["_compiled"] = True
            regs = [list(r) for r in con["regions"]]
            for r in regs[1:]:
                if len(r) != len(regs[0]):
                    raise ValueError("clone regions must have equal sizes")
                for a, b in zip(regs[0], r):
                    if a != b:
                        self.relations.append(("eq", a, b))

    def finalize(self):
        self._compile_clones()
        self._compile_lines()
        for g in self.groups:
            g.shape = shape_ratio([self.coords[c] for c in g.cells])
        self.houses = [i for i, g in enumerate(self.groups) if g.complete]
        self.groups_of = [[] for _ in range(self.N)]
        for gi, g in enumerate(self.groups):
            for c in g.cells:
                self.groups_of[c].append(gi)
        self.neq = [set() for _ in range(self.N)]
        # generic pairwise rules: rel_ex[a][b][v] = mask of digits excluded at
        # b when a == v.  `nonconsec` keeps its name but now holds every
        # non-neq relation partner (non-consecutive, thermo <, whisper, ...).
        self.nonconsec = [set() for _ in range(self.N)]
        self.rel_ex = [dict() for _ in range(self.N)]
        for rel in self.relations:
            kind, a, b = rel[0], rel[1], rel[2]
            if kind == "neq":
                self.neq[a].add(b)
                self.neq[b].add(a)
                continue
            ok = RELATIONS[kind]
            args = rel[3:]
            for x, y, fwd in ((a, b, True), (b, a, False)):
                tab = [0] * (self.D + 1)
                for v in range(1, self.D + 1):
                    allowed = 0
                    for w in range(1, self.D + 1):
                        if ok(v, w, *args) if fwd else ok(w, v, *args):
                            allowed |= 1 << (w - 1)
                    tab[v] = self.full & ~allowed
                old = self.rel_ex[x].get(y)
                self.rel_ex[x][y] = tab if old is None else [o | t for o, t in zip(old, tab)]
                self.nonconsec[x].add(y)
        self.peers = [set() for _ in range(self.N)]
        for gi, g in enumerate(self.groups):
            for c in g.cells:
                self.peers[c].update(g.cells)
        for c in range(self.N):
            self.peers[c] |= self.neq[c]
            self.peers[c].discard(c)
        self.peer_list = [sorted(p) for p in self.peers]
        self.nonconsec_list = [sorted(p) for p in self.nonconsec]
        self.has_cages = any(g.total is not None for g in self.groups)
        for con in self.constraints:
            if con["type"] == "sum" and con.get("distinct") is None:
                # implied when all cells share one group (otherwise digits may repeat)
                cs = con["cells"]
                common = set(self.groups_of[cs[0]]) if cs else set()
                for c in cs[1:]:
                    common &= set(self.groups_of[c])
                con["distinct"] = bool(common)
        return self

    @property
    def n_empty(self):
        return self.N - len(self.givens)


# --------------------------------------------------------------- builders ----


def _grid_coords(size):
    return [(r, c) for r in range(size) for c in range(size)]


def standard(size: int, box_h: int, box_w: int, grid: str = "", name="") -> Puzzle:
    """Classic size x size sudoku with box_h x box_w boxes. grid uses '.'/'0'
    for blanks and 1-9 then A-Z for digits >9 (or space-separated numbers)."""
    p = Puzzle(D=size, coords=_grid_coords(size), name=name)
    for r in range(size):
        p.groups.append(Group(f"r{r + 1}", tuple(r * size + c for c in range(size)), "row", True))
    for c in range(size):
        p.groups.append(Group(f"c{c + 1}", tuple(r * size + c for r in range(size)), "col", True))
    for br in range(0, size, box_h):
        for bc in range(0, size, box_w):
            cells = tuple((br + i) * size + (bc + j) for i in range(box_h) for j in range(box_w))
            p.groups.append(Group(f"b{len([g for g in p.groups if g.kind == 'box']) + 1}", cells, "box", True))
    if grid:
        p.givens = parse_grid(grid, size)
    return p


def parse_grid(grid: str, size: int) -> dict:
    toks = grid.split() if " " in grid.strip() else list(grid.strip())
    out = {}
    for i, t in enumerate(toks[: size * size]):
        if t in ".0-":
            continue
        v = int(t) if t.isdigit() else ord(t.upper()) - ord("A") + 10
        if 1 <= v <= size:
            out[i] = v
    return out


def add_diagonals(p: Puzzle, size: int) -> Puzzle:
    p.groups.append(Group("d1", tuple(i * size + i for i in range(size)), "diag", True))
    p.groups.append(Group("d2", tuple(i * size + (size - 1 - i) for i in range(size)), "diag", True))
    return p


def add_windoku(p: Puzzle) -> Puzzle:
    for wr in (1, 5):
        for wc in (1, 5):
            cells = tuple((wr + i) * 9 + (wc + j) for i in range(3) for j in range(3))
            p.groups.append(Group(f"w{wr}{wc}", cells, "window", True))
    return p


def jigsaw(size: int, regions: str, grid: str = "", name="") -> Puzzle:
    """regions: size*size chars, each a region id; replaces boxes."""
    p = Puzzle(D=size, coords=_grid_coords(size), name=name)
    for r in range(size):
        p.groups.append(Group(f"r{r + 1}", tuple(r * size + c for c in range(size)), "row", True))
    for c in range(size):
        p.groups.append(Group(f"c{c + 1}", tuple(r * size + c for r in range(size)), "col", True))
    reg = {}
    for i, ch in enumerate(regions.strip()[: size * size]):
        reg.setdefault(ch, []).append(i)
    for k, cells in sorted(reg.items()):
        p.groups.append(Group(f"j{k}", tuple(cells), "region", len(cells) == size))
    if grid:
        p.givens = parse_grid(grid, size)
    return p


def add_nonconsecutive(p: Puzzle, size: int) -> Puzzle:
    for r in range(size):
        for c in range(size):
            i = r * size + c
            if c + 1 < size:
                p.relations.append(("nonconsec", i, i + 1))
            if r + 1 < size:
                p.relations.append(("nonconsec", i, i + size))
    return p


def add_antiknight(p: Puzzle, size: int) -> Puzzle:
    for r in range(size):
        for c in range(size):
            for dr, dc in ((1, 2), (2, 1), (2, -1), (1, -2)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < size and 0 <= cc < size:
                    p.relations.append(("neq", r * size + c, rr * size + cc))
    return p


def add_cages(p: Puzzle, cages) -> Puzzle:
    """cages: list of (sum_or_None, [cell indices])"""
    for k, (total, cells) in enumerate(cages):
        p.groups.append(Group(f"k{k + 1}", tuple(cells), "cage", len(cells) == p.D, total))
    return p


def subgrid_ids(p: Puzzle, k: int) -> list:
    """Row-major cell ids of samurai sub-grid k (0=TL,1=TR,2=centre,3=BL,4=BR)."""
    orr, oc = p.origins[k]
    return [p.cell_id[(orr + r, oc + c)] for r in range(9) for c in range(9)]


def apply_variant_to_subgrid(p: Puzzle, k: int, variant: str) -> Puzzle:
    """Add a variant's extra constraints to one 9x9 sub-grid of a samurai --
    the group-agnostic model doesn't care that they overlap other grids."""
    ids = subgrid_ids(p, k)
    tag = "abcde"[k]
    if variant == "x":
        p.groups.append(Group(f"{tag}d1", tuple(ids[i * 9 + i] for i in range(9)), "diag", True))
        p.groups.append(Group(f"{tag}d2", tuple(ids[i * 9 + 8 - i] for i in range(9)), "diag", True))
    elif variant == "windoku":
        for wr in (1, 5):
            for wc in (1, 5):
                p.groups.append(
                    Group(
                        f"{tag}w{wr}{wc}",
                        tuple(ids[(wr + i) * 9 + wc + j] for i in range(3) for j in range(3)),
                        "window",
                        True,
                    )
                )
    elif variant == "nonconsec":
        for r in range(9):
            for c in range(9):
                if c + 1 < 9:
                    p.relations.append(("nonconsec", ids[r * 9 + c], ids[r * 9 + c + 1]))
                if r + 1 < 9:
                    p.relations.append(("nonconsec", ids[r * 9 + c], ids[(r + 1) * 9 + c]))
    elif variant == "antiknight":
        for r in range(9):
            for c in range(9):
                for dr, dc in ((1, 2), (2, 1), (2, -1), (1, -2)):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < 9 and 0 <= cc < 9:
                        p.relations.append(("neq", ids[r * 9 + c], ids[rr * 9 + cc]))
    return p


def samurai(grids: list[str] | None = None, name="") -> Puzzle:
    """Five overlapping 9x9 grids on a 21x21 canvas (corner grids share a box
    with the centre grid). grids: optional 5 x 81-char strings in order
    TL, TR, centre, BL, BR."""
    origins = [(0, 0), (0, 12), (6, 6), (12, 0), (12, 12)]
    cell_id = {}
    coords = []
    for orr, oc in origins:
        for r in range(9):
            for c in range(9):
                key = (orr + r, oc + c)
                if key not in cell_id:
                    cell_id[key] = len(coords)
                    coords.append(key)
    p = Puzzle(D=9, coords=coords, name=name)
    for gi_, (orr, oc) in enumerate(origins):
        tag = "abcde"[gi_]
        for r in range(9):
            p.groups.append(Group(f"{tag}r{r + 1}", tuple(cell_id[(orr + r, oc + c)] for c in range(9)), "row", True))
        for c in range(9):
            p.groups.append(Group(f"{tag}c{c + 1}", tuple(cell_id[(orr + r, oc + c)] for r in range(9)), "col", True))
        for br in range(0, 9, 3):
            for bc in range(0, 9, 3):
                cells = tuple(cell_id[(orr + br + i, oc + bc + j)] for i in range(3) for j in range(3))
                if not any(set(cells) == set(g.cells) for g in p.groups if g.kind == "box"):
                    p.groups.append(Group(f"{tag}b{br // 3 * 3 + bc // 3 + 1}", cells, "box", True))
    p.origins = origins
    p.cell_id = cell_id
    if grids:
        for (orr, oc), g in zip(origins, grids):
            for i, ch in enumerate(g):
                if ch in ".0":
                    continue
                p.givens[cell_id[(orr + i // 9, oc + i % 9)]] = int(ch)
    return p


def add_predicate(p: Puzzle, cells, fn, name="custom", max_tuples=200_000) -> Puzzle:
    """Generic custom rule over a small group of cells: fn(*digits) -> bool, compiled to an n-ary
    table constraint (allowed tuples) by enumerating the cells' domains. Every engine path that
    understands tables (TableCombination, brute force, featurize) and the CP-SAT verifier then
    handle it, with no new solver code. Example (diamond: centre digit divides the sum of its
    four orthogonal neighbours): add_predicate(p, [ctr, n, e, s, w], lambda c, *v: sum(v) % c == 0, "diamond").
    Keep groups small (domain product <= max_tuples); larger sums should use sum constraints."""
    import itertools

    cells = list(cells)
    doms = []
    for c in cells:
        m = p.domains[c] if p.domains else (1 << p.D) - 1
        doms.append([d for d in range(1, p.D + 1) if m >> (d - 1) & 1])
    size = 1
    for d in doms:
        size *= len(d)
    if size > max_tuples:
        raise ValueError(f"predicate {name}: domain product {size} > {max_tuples}")
    allowed = [list(t) for t in itertools.product(*doms) if fn(*t)]
    p.constraints.append({"type": "table", "cells": cells, "allowed": allowed, "name": name})
    return p
