"""Standard n x n board geometry and random full grids."""
from __future__ import annotations

import math

# board size -> box (height, width)
BOXES = {4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3), 10: (2, 5), 12: (3, 4), 16: (4, 4)}

# log2 of the number of valid grids (known enumerations; used by the information-budget pre-check)
GRID_LOG2 = {4: math.log2(288), 6: math.log2(28_200_960), 8: math.log2(29_136_487_207_403_520),
             9: math.log2(6_670_903_752_021_072_936_960), 12: math.log2(8.1171437e46), 16: math.log2(5.96e98)}


def grid_log2(n):
    """log2(number of n x n sudoku grids); a deliberately low estimate for sizes without a known count (safe for a
    budget bound: underestimating the entropy only lets more specs through)."""
    if n in GRID_LOG2:
        return GRID_LOG2[n]
    return n * math.lgamma(n + 1) / math.log(2) / 2


class Board:
    def __init__(self, n):
        if n not in BOXES:
            raise ValueError(f"unsupported board size {n} (supported: {sorted(BOXES)})")
        self.n = n
        self.N = n * n
        self.bh, self.bw = BOXES[n]
        rows = [[r * n + c for c in range(n)] for r in range(n)]
        cols = [[r * n + c for r in range(n)] for c in range(n)]
        boxes = [[(br + i) * n + bc + j for i in range(self.bh) for j in range(self.bw)]
                 for br in range(0, n, self.bh) for bc in range(0, n, self.bw)]
        self.units = rows + cols + boxes
        self.peers = [sorted({j for u in self.units if i in u for j in u} - {i}) for i in range(self.N)]
        # orthogonal neighbours
        self.nb = [[j for j in (i - n, i + n, i - 1 if i % n else -1, i + 1 if i % n < n - 1 else -1) if 0 <= j < self.N]
                   for i in range(self.N)]
        # orthogonal edges (i < j), used by kropki / xv
        self.edges = [(i, j) for i in range(self.N) for j in (i + 1, i + n)
                      if j < self.N and not (j == i + 1 and j % n == 0)]

    def rc(self, i):
        return f"r{i // self.n + 1}c{i % self.n + 1}"

    def solution(self, rng):
        """random full grid: bitmask backtracking, fewest candidates first."""
        n, full = self.n, (1 << self.n) - 1
        g = [0] * self.N

        def cand(i):
            m = full
            for j in self.peers[i]:
                if g[j]:
                    m &= ~(1 << (g[j] - 1))
            return m

        def bt():
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

        bt()
        return g

    # ---- symmetry orbits for given placement
    def orbit(self, i, symmetry):
        """cells that must be given / empty together with cell i under the symmetry (None = just i)."""
        if not symmetry:
            return (i,)
        n = self.n
        r, c = divmod(i, n)
        maps = {
            "rot180": [(n - 1 - r, n - 1 - c)],
            "rot90": [(c, n - 1 - r), (n - 1 - r, n - 1 - c), (n - 1 - c, r)],
            "mirror": [(r, n - 1 - c)],          # left-right
            "mirror_v": [(n - 1 - r, c)],        # top-bottom
            "diagonal": [(c, r)],
            "antidiagonal": [(n - 1 - c, n - 1 - r)],
        }
        if symmetry not in maps:
            raise ValueError(f"unknown symmetry {symmetry!r} (known: {sorted(maps)})")
        if symmetry in ("diagonal", "antidiagonal", "rot90") and self.bh != self.bw:
            raise ValueError(f"symmetry {symmetry} needs square boxes")
        return tuple(sorted({i} | {rr * n + cc for rr, cc in maps[symmetry]}))


SYMMETRIES = ("rot180", "rot90", "mirror", "mirror_v", "diagonal", "antidiagonal")
