"""Standard n x n board geometry and random full grids."""

from __future__ import annotations

import math

# board size -> box (height, width)
BOXES = {4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3), 10: (2, 5), 12: (3, 4), 16: (4, 4)}

# log2 of the number of valid grids (known enumerations; used by the information-budget pre-check)
GRID_LOG2 = {
    4: math.log2(288),
    6: math.log2(28_200_960),
    8: math.log2(29_136_487_207_403_520),
    9: math.log2(6_670_903_752_021_072_936_960),
    12: math.log2(8.1171437e46),
    16: math.log2(5.96e98),
}


def grid_log2(n):
    """log2(number of n x n sudoku grids); a deliberately low estimate for sizes without a known count (safe for a
    budget bound: underestimating the entropy only lets more specs through)."""
    if n in GRID_LOG2:
        return GRID_LOG2[n]
    return n * math.lgamma(n + 1) / math.log(2) / 2


class Board:
    """the cells, houses and neighbours of the board being generated: one n x n grid with standard boxes, or a named
    multi-grid layout of 9 x 9 grids (samurai, super-samurai, ...: puzzle_json's layouts). Cell indices follow
    puzzle_json's cell order, so a puzzle's numbers string lines up. extra: more all-different units (extra regions,
    diagonals) that the solution must respect."""

    def __init__(self, n, layout=None, extra=()):
        if n not in BOXES:
            raise ValueError(f"unsupported board size {n} (supported: {sorted(BOXES)})")
        self.n, self.layout = n, layout
        self.bh, self.bw = BOXES[n]
        if layout:
            from ..puzzle_json import _layout_origins, _layout_regions

            origins = _layout_origins(layout)
            if origins is None or n != 9:
                raise ValueError(f"unknown layout {layout!r} (layouts are of 9 x 9 grids)")
            self.origins = list(origins)
            self.coords, groups = _layout_regions(self.origins, n, self.bh, self.bw)
            self.units = [list(g.cells) for g in groups]
            boxes = [list(g.cells) for g in groups if g.kind == "box"]
        else:
            self.origins = [(0, 0)]
            self.coords = [(r, c) for r in range(n) for c in range(n)]
            rows = [[r * n + c for c in range(n)] for r in range(n)]
            cols = [[r * n + c for r in range(n)] for c in range(n)]
            boxes = [
                [(br + i) * n + bc + j for i in range(self.bh) for j in range(self.bw)]
                for br in range(0, n, self.bh)
                for bc in range(0, n, self.bw)
            ]
            self.units = rows + cols + boxes
        self.N = len(self.coords)
        self.box_of = {}  # cell -> its box (region-sum lines split at box borders)
        for k, box in enumerate(boxes):
            for c in box:
                self.box_of.setdefault(c, k)
        self.cid = {rc: i for i, rc in enumerate(self.coords)}
        self.rows = max(r for r, _ in self.coords) + 1
        self.cols = max(c for _, c in self.coords) + 1
        self.units += [list(u) for u in extra]
        self.peers = [sorted({j for u in self.units if i in u for j in u} - {i}) for i in range(self.N)]
        self.grid_cells = [  # the cells of each n x n grid, the grids in reading order of their origins
            [self.cid[(o_r + r, o_c + c)] for r in range(n) for c in range(n)] for o_r, o_c in sorted(self.origins)
        ]
        # orthogonal neighbours, and the orthogonal edges (i < j) kropki / xv use
        step = lambda i, dr, dc: self.cid.get((self.coords[i][0] + dr, self.coords[i][1] + dc), -1)
        self.nb = [
            [j for j in (step(i, -1, 0), step(i, 1, 0), step(i, 0, -1), step(i, 0, 1)) if j >= 0] for i in range(self.N)
        ]
        self.edges = sorted({(min(i, j), max(i, j)) for i in range(self.N) for j in self.nb[i]})

    def rc(self, i):
        r, c = self.coords[i]
        return f"r{r + 1}c{c + 1}"

    def solution(self, rng, preset=None):
        """random full grid: bitmask backtracking, fewest candidates first. A board the backtracking cannot fill within
        its step budget (a layout with diagonals and windows) is completed by the engine's search from a few random
        digits, then relabelled with a random digit permutation. preset {cell: digit}: cells the grid keeps (then no
        relabelling); None if they cannot be completed."""
        n, full = self.n, (1 << self.n) - 1
        g = [0] * self.N
        for i, v in (preset or {}).items():
            g[i] = v
        steps = [0]

        def cand(i):
            m = full
            for j in self.peers[i]:
                if g[j]:
                    m &= ~(1 << (g[j] - 1))
            return m

        def bt():
            steps[0] += 1
            if steps[0] > 20_000:  # a plain grid takes a few hundred steps
                raise TimeoutError
            best, bm, bc = -1, 0, 99
            for i in range(self.N):
                if not g[i]:
                    m = cand(i)
                    c = bin(m).count("1")
                    if c == 0:
                        return False
                    if c < bc:
                        best, bm, bc = i, m, c
            if best < 0:
                return True
            ds = [d + 1 for d in range(n) if bm >> d & 1]
            rng.shuffle(ds)
            for d in ds:
                g[best] = d
                if bt():
                    return True
            g[best] = 0
            return False

        try:
            if bt():
                return g
            if preset:
                return None
        except TimeoutError:
            pass
        return self._engine_solution(rng, preset)

    def _engine_solution(self, rng, preset=None):
        from .. import cbackend as CB
        from .. import puzzle_json as PJ
        from .elements import to_json

        for _ in range(50 if not preset else 1):
            seed = dict(preset or {})
            for i in rng.sample(
                range(self.N), 0 if preset else min(12, self.N)
            ):  # a few random digits, consistent with each other
                used = {seed[j] for j in self.peers[i] if j in seed}
                free = [d for d in range(1, self.n + 1) if d not in used]
                if free:
                    seed[i] = rng.choice(free)
            p = PJ.from_json(to_json(self, seed, []))
            p.finalize()
            sols = CB.brute_solve(p, limit=1, node_limit=2_000_000)
            if sols:
                perm = list(range(1, self.n + 1))
                rng.shuffle(perm)
                return list(sols[0]) if preset else [perm[v - 1] for v in sols[0]]
        if preset:
            return None
        raise RuntimeError("no full grid found for this board and its locked rules")

    # ---- symmetry orbits for given placement
    def orbit(self, i, symmetry):
        """cells that must be given / empty together with cell i under the symmetry (None = just i)."""
        if not symmetry:
            return (i,)
        R, C = self.rows, self.cols
        r, c = self.coords[i]
        maps = {
            "rot180": [(R - 1 - r, C - 1 - c)],
            "rot90": [(c, C - 1 - r), (R - 1 - r, C - 1 - c), (C - 1 - c, r)],
            "mirror": [(r, C - 1 - c)],  # left-right
            "mirror_v": [(R - 1 - r, c)],  # top-bottom
            "diagonal": [(c, r)],
            "antidiagonal": [(C - 1 - c, R - 1 - r)],
        }
        if symmetry not in maps:
            raise ValueError(f"unknown symmetry {symmetry!r} (known: {sorted(maps)})")
        if symmetry in ("diagonal", "antidiagonal", "rot90") and (self.bh != self.bw or R != C):
            raise ValueError(f"symmetry {symmetry} needs square boxes and a square board")
        # a layout that is not symmetric itself: cells whose image is no cell keep only themselves
        return tuple(sorted({i} | {self.cid[rc] for rc in maps[symmetry] if rc in self.cid}))


SYMMETRIES = ("rot180", "rot90", "mirror", "mirror_v", "diagonal", "antidiagonal")
