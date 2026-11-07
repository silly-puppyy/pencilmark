"""Draw a pencilmark-puzzle file as SVG, following the default drawing of docs/library/drawing-style.md (reference renderer for
the docs; not part of the package).
  python tools/render_svg.py puzzle.json out.svg [--dark] [--cell 48] [--card card.json --position N]
  render(doc, dark=False, cell=48, colours=None, placed=None) -> svg text
--card / --position draw one position of a card's trace (grade-card.md 6): its placed digits and its colour layer."""

import json
import math
import re
import sys
from pathlib import Path

try:  # an installed pencilmark (with its engine) if there is one, else the source tree
    from pencilmark import exchange as X
    from pencilmark.rules import CELL, EDGE, LINE
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from pencilmark import exchange as X  # noqa: E402
    from pencilmark.rules import CELL, EDGE, LINE  # noqa: E402

# board style, in cell units unless noted (docs/library/drawing-style.md; values in docs/palette.json)
_PAL = json.loads((Path(__file__).resolve().parents[1] / "docs/palette.json").read_text(encoding="utf-8"))
STYLE = _PAL["sizes"]
THEMES = {False: _PAL["themes"]["light"], True: _PAL["themes"]["dark"]}
LINE_COLOURS = {k: v for k, v in _PAL["lines"].items() if k != "dutch_whisper"}
DUTCH = _PAL["lines"]["dutch_whisper"]
PALETTE = _PAL["region_palette"]
ANNOTATION = _PAL["annotation"]
OUTSIDE = ("sandwich", "xsum", "skyscraper", "rossini", "first_seen")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(
    doc, dark=False, cell=48, annotate=False, labels=False, background=True, colours=None, placed=None, marks=None
):
    """svg text. annotate: every element drawn for rules[i] carries data-rule="i" (pages link it to the JSON);
    labels: row numbers on the left and column numbers on top, outside the board and its outside clues.
    colours {cell name: [colour names]}: annotation colours over the cells (one fills the cell; n split it into n
    wedges, as SudokuPad draws them); placed {cell name: digit}: digits the solver has written, in the placed ink;
    marks {cell name: {"corner": [...], "centre": [...]}}: the solver's pencil marks (corner marks in the cell's corners
    and edges, centre marks in a row across the middle), in the placed ink."""
    T = THEMES[bool(dark)]
    S = STYLE
    u = float(cell)
    B = X.validate(doc)
    R, C = doc["board"]["rows"], doc["board"]["cols"]
    rules = X.resolve_areas(B, doc["rules"])
    has_out = any(
        r["type"] in OUTSIDE
        or (r["type"] == "sum" and r.get("kind") in ("little_killer", "frame"))
        or (r["type"] == "distinct_count" and "side" in r)
        for r in rules
    )
    m = u if has_out else 0.35 * u
    lab = 0.55 * u if labels else 0.0  # a band for the row / column numbers
    m += lab
    W, H = C * u + 2 * m, R * u + 2 * m
    rc = lambda name: X.parse_cell(name)
    cx = lambda c: m + (c + 0.5) * u
    cy = lambda r: m + (r + 0.5) * u
    ctr = lambda name: (cx(rc(name)[1]), cy(rc(name)[0]))
    exists = {(r, c) for r, c in B.coords}
    layers = {
        k: [] for k in ("shade", "colour", "marks", "lines", "cages", "grid", "clues", "digits", "outside", "over")
    }
    cur = [None]  # the rule being drawn (annotate)
    labelled = set()  # cells with a cage total in their top-left corner (corner marks start elsewhere there)

    palette = (doc.get("style") or {}).get("palette") or []

    def colour_of(v, default=None):
        """a style colour: "#rrggbb", or an index into the top-level style palette"""
        if isinstance(v, int) and not isinstance(v, bool):
            return palette[v] if 0 <= v < len(palette) else default
        return v if isinstance(v, str) and v else default

    def restyle(k, s, st):
        """a rule's own style over its family's look (section 7): colour on strokes, fill on shapes, width on lines,
        opacity on everything; digits and clue text keep their ink"""
        if not st or k == "digits":
            return s
        col, fil = colour_of(st.get("color")), colour_of(st.get("fill"))
        if col:
            s = re.sub(r'stroke="(?!none)[^"]*"', f'stroke="{col}"', s)
        if fil:
            s = re.sub(r'(<(?:rect|circle|ellipse|polygon|path)\b[^>]*?)fill="(?!none)[^"]*"', rf'\1fill="{fil}"', s)
        if k == "lines" and isinstance(st.get("width"), (int, float)):
            s = re.sub(r'stroke-width="[^"]*"', f'stroke-width="{st["width"] * u:.1f}"', s)
        if isinstance(st.get("opacity"), (int, float)):
            s = re.sub(r"<(rect|circle|ellipse|polygon|polyline|path|line)\b", rf'<\1 opacity="{st["opacity"]}"', s)
        return s

    def add(k, s):
        if cur[0] is not None:
            s = restyle(k, s, rules[cur[0]].get("style"))
        if annotate and cur[0] is not None:
            s = re.sub(r"<(\w+)", lambda mt: f'<{mt.group(1)} data-rule="{cur[0]}"', s)
        layers[k].append(s)

    # ---- board, houses
    for r, c in B.coords:
        add("shade", f'<rect x="{m + c * u}" y="{m + r * u}" width="{u}" height="{u}" fill="{T["board"]}"/>')
    # ---- annotation colours, over the board, region shading and cell shapes (they show through) and under every line,
    # arrow, cage, dot, clue and digit (drawn later, so they stay readable). One per cell fills it; several split it into equal wedges from the centre, as
    # SudokuPad draws them: wedge i spans 25 + i * 360 / n to 25 + (i + 1) * 360 / n "degrees", each mapped to a point
    # that far round the cell's outline (clockwise from the top centre; 360 = once round), not to a true angle
    shades, alpha = ANNOTATION["dark" if dark else "light"], ANNOTATION["opacity"]["dark" if dark else "light"]

    def perim(x0, y0, a):
        """the point a / 360 of the way round the cell's outline, clockwise from the top centre"""
        t = (a % 360) / 90  # in sides: 0.5 = top-right corner, 1.5 = bottom-right, 2.5 = bottom-left, 3.5 = top-left
        if t < 0.5:
            return x0 + (0.5 + t) * u, y0
        if t < 1.5:
            return x0 + u, y0 + (t - 0.5) * u
        if t < 2.5:
            return x0 + (2.5 - t) * u, y0 + u
        if t < 3.5:
            return x0, y0 + (3.5 - t) * u
        return x0 + (t - 3.5) * u, y0

    corners = (45, 135, 225, 315)  # the corners, in the same measure

    def cell_colours(name, cols, opacity, pattern="wedges"):
        """one colour fills the cell; k split it into k wedges from the centre (SudokuPad) or k slanted stripes
        (sudoku.coach)"""
        r, c = rc(name)
        x0, y0 = m + c * u, m + r * u
        if len(cols) == 1:
            add(
                "colour",
                f'<rect x="{x0}" y="{y0}" width="{u}" height="{u}" fill="{cols[0]}" fill-opacity="{opacity}"/>',
            )
            return
        if pattern == "stripes":  # parallelograms leaning right, cut to the cell
            lean, w = 0.25 * u, (u + 0.5 * u) / len(cols)
            cid = f"cc{r}_{c}"
            add("colour", f'<clipPath id="{cid}"><rect x="{x0}" y="{y0}" width="{u}" height="{u}"/></clipPath>')
            for i, col in enumerate(cols):
                xa = x0 - lean + i * w
                d = f"{xa + lean:.1f},{y0:.1f} {xa + lean + w:.1f},{y0:.1f} {xa + w:.1f},{y0 + u:.1f} {xa:.1f},{y0 + u:.1f}"
                add("colour", f'<polygon points="{d}" fill="{col}" fill-opacity="{opacity}" clip-path="url(#{cid})"/>')
            return
        for i, col in enumerate(cols):
            a1, a2 = 25 + i * 360 / len(cols), 25 + (i + 1) * 360 / len(cols)
            turn = [k for k in corners for k in (k, k + 360) if a1 < k < a2]
            pts = [(x0 + u / 2, y0 + u / 2)] + [perim(x0, y0, a) for a in (a1, *sorted(turn), a2)]
            d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            add("colour", f'<polygon points="{d}" fill="{col}" fill-opacity="{opacity}"/>')

    for name, cols in (colours or {}).items():
        cell_colours(name, [shades[x] for x in cols], alpha)
    houses, _ = X.read_houses([x for x in rules if x["type"] in ("grid", "box_grid", "box", "row", "column")], B)
    box_of = {}
    for k, (kind, cells, _) in enumerate(houses):
        if kind == "box":
            for c in cells:
                box_of.setdefault(B.coords[c], set()).add(k)

    def thick(a, b):
        if a not in exists or b not in exists:
            return "frame"
        if not box_of:
            return "thin"
        return "box" if not (box_of.get(a, set()) & box_of.get(b, set())) else "thin"

    segs = {"thin": [], "box": [], "frame": []}
    for r, c in exists:
        for dr, dc, x1, y1, x2, y2 in (
            (0, 1, c + 1, r, c + 1, r + 1),
            (1, 0, c, r + 1, c + 1, r + 1),
            (0, -1, c, r, c, r + 1),
            (-1, 0, c, r, c + 1, r),
        ):
            nb = (r + dr, c + dc)
            k = thick((r, c), nb)
            if nb in exists and (dr < 0 or dc < 0):
                continue  # each inner edge once
            segs[k].append((m + x1 * u, m + y1 * u, m + x2 * u, m + y2 * u))
    for k in ("thin", "box", "frame"):
        ww = S["box_dark"] if (dark and k != "thin") else S[k]  # light lines on dark read thinner: thicker boxes there
        w = max(1 if k == "thin" else 2, round(ww * u))  # whole device pixels: no grey anti-aliased hairlines
        off = 0.5 if w % 2 else 0.0  # odd widths sit on pixel centres
        col = T["thin"] if k == "thin" else T["ink"]
        for x1, y1, x2, y2 in segs[k]:
            x1, y1, x2, y2 = (round(v) + off for v in (x1, y1, x2, y2))
            add(
                "grid",
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{w}" '
                f'stroke-linecap="square"/>',  # no crispEdges: scaled down, it dropped whole grid lines
            )

    def outline(cells, inset, dash, col, width):
        """outline of a cell set, inset from the cell edges (cage style)"""
        st = {rc(x) for x in cells}
        o = []
        for r, c in st:
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if (r + dr, c + dc) in st:
                    continue
                x0, y0, x1, y1 = m + c * u, m + r * u, m + (c + 1) * u, m + (r + 1) * u
                i = inset * u
                ext = lambda a, b: i if (r + a, c + b) not in st else -i
                if dr == -1:
                    seg = (x0 + ext(0, -1), y0 + i, x1 - ext(0, 1), y0 + i)
                elif dr == 1:
                    seg = (x0 + ext(0, -1), y1 - i, x1 - ext(0, 1), y1 - i)
                elif dc == -1:
                    seg = (x0 + i, y0 + ext(-1, 0), x0 + i, y1 - ext(1, 0))
                else:
                    seg = (x1 - i, y0 + ext(-1, 0), x1 - i, y1 - ext(1, 0))
                o.append(
                    f'<line x1="{seg[0]:.1f}" y1="{seg[1]:.1f}" x2="{seg[2]:.1f}" y2="{seg[3]:.1f}" stroke="{col}" '
                    f'stroke-width="{width}" stroke-dasharray="{dash}"/>'
                )
        return "".join(o)

    def small_text(x, y, s, size=0.25, anchor="middle", col=None, weight=500):
        return (
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size * u:.1f}" text-anchor="{anchor}" dominant-baseline="central" '
            f'font-family="Inter,Helvetica,Arial,sans-serif" font-weight="{weight}" fill="{col or T["given"]}">{esc(s)}</text>'
        )

    def circle_clue(x, y, s, r=0.15):
        """a numbered clue on an edge or corner: a circle for one or two characters, a pill sized to longer text"""
        n = len(str(s))
        if n <= 2:
            rr = max(r, 0.2 if n == 1 else 0.23)
            return (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr * u:.1f}" fill="{T["clue_bg"]}" stroke="{T["given"]}" '
                f'stroke-width="1"/>' + small_text(x, y, s, size=0.28 if n == 1 else 0.25)
            )
        w, h = (0.15 * n + 0.14) * u, 0.4 * u
        return (
            f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" '
            f'fill="{T["clue_bg"]}" stroke="{T["given"]}" stroke-width="1"/>' + small_text(x, y, s, size=0.24)
        )

    def polyline(cells, col, w, closed=False):
        pts = [ctr(x) for x in cells] + ([ctr(cells[0])] if closed else [])
        return (
            f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="none" stroke="{col}" '
            f'stroke-width="{w * u:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    colour_i = 0
    for ri, r in enumerate(rules):
        cur[0] = ri
        t, k = r["type"], r.get("kind")
        if t == "region":
            if k == "diagonal":
                (x0, y0), (x1, y1) = ctr(r["cells"][0]), ctr(r["cells"][-1])
                dx, dy = (x1 - x0), (y1 - y0)
                L = math.hypot(dx, dy) or 1
                e = u * 0.5 * math.sqrt(2)
                add(
                    "lines",
                    f'<line x1="{x0 - dx / L * e:.1f}" y1="{y0 - dy / L * e:.1f}" x2="{x1 + dx / L * e:.1f}" y2="{y1 + dy / L * e:.1f}" '
                    f'stroke="{T["diag"]}" stroke-width="{0.04 * u:.1f}"/>',
                )
            elif k in ("window", "extra"):
                for x in r["cells"]:
                    rr, cc = rc(x)
                    add(
                        "shade",
                        f'<rect x="{m + cc * u}" y="{m + rr * u}" width="{u}" height="{u}" fill="{T["shade"]}"/>',
                    )
            elif k in ("colour", "disjoint"):
                col = PALETTE[colour_i % len(PALETTE)]
                colour_i += 1
                for x in r["cells"]:
                    rr, cc = rc(x)
                    add(
                        "shade",
                        f'<rect x="{m + cc * u}" y="{m + rr * u}" width="{u}" height="{u}" fill="{col}" opacity="{0.72 if dark else 1}"/>',
                    )
        elif t == "cage" or (t == "sum" and k == "group"):
            add("cages", outline(r["cells"], 0.08, "4 3" if t == "cage" else "1.5 3", T["given"], 1.2))
            if "sum" in r:
                first = min(r["cells"], key=lambda x: rc(x))
                labelled.add(first)
                rr, cc = rc(first)
                add(
                    "cages",
                    f'<rect x="{m + cc * u + 0.05 * u:.1f}" y="{m + rr * u + 0.05 * u:.1f}" width="{0.3 * u:.1f}" height="{0.24 * u:.1f}" fill="{T["board"]}"/>',
                )
                add(
                    "cages",
                    small_text(m + cc * u + 0.09 * u, m + rr * u + 0.17 * u, r["sum"], size=0.22, anchor="start"),
                )
        elif t == "line":  # width and end markers from the line registry (pencilmark/rules/line.py)
            lk = LINE[k]
            col = DUTCH if (k == "whisper" and r.get("value", 5) == 4) else LINE_COLOURS.get(k, "#aaaaaa")
            add(
                "lines",
                polyline(
                    r["cells"], col, S[lk.width] if isinstance(lk.width, str) else lk.width, r.get("closed", False)
                ),
            )
            if lk.ends in ("bulb", "hollow bulb"):
                x, y = ctr(r["cells"][0])
                fill = col if lk.ends == "bulb" else T["board"]
                ring = "" if lk.ends == "bulb" else f' stroke="{col}" stroke-width="{0.12 * u:.1f}"'
                add("lines", f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{S["bulb"] * u:.1f}" fill="{fill}"{ring}/>')
            if lk.ends == "circles":
                for e in (r["cells"][0], r["cells"][-1]):
                    x, y = ctr(e)
                    add(
                        "lines",
                        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.375 * u:.1f}" fill="{T["board"]}" stroke="{col}" stroke-width="{0.05 * u:.1f}"/>',
                    )
            if lk.ends == "diamonds":
                for e in (r["cells"][0], r["cells"][-1]):
                    x, y = ctr(e)
                    d = 0.4 * u
                    add(
                        "lines",
                        f'<polygon points="{x},{y - d} {x + d},{y} {x},{y + d} {x - d},{y}" fill="{T["board"]}" stroke="{col}" stroke-width="{0.05 * u:.1f}"/>',
                    )
            if lk.ends == "centre dot":  # at the line's centre (a cell, or between the two middle cells)
                n = len(r["cells"])
                (xa, ya), (xb, yb) = ctr(r["cells"][(n - 1) // 2]), ctr(r["cells"][n // 2])
                add(
                    "lines",
                    f'<circle cx="{(xa + xb) / 2:.1f}" cy="{(ya + yb) / 2:.1f}" r="{0.09 * u:.1f}" fill="{col}" stroke="{T["board"]}" stroke-width="1"/>',
                )
        elif t == "arrow":
            bulb = r["bulb"]
            pts = [ctr(x) for x in bulb]
            if len(bulb) == 1:
                x, y = pts[0]
                add(
                    "lines",
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.375 * u:.1f}" fill="{T["board"]}" stroke="#aaaaaa" stroke-width="{0.05 * u:.1f}"/>',
                )
            else:
                add("lines", polyline(bulb, "#aaaaaa", 0.8) + polyline(bulb, T["board"], 0.7))
            for sh in r["lines"]:
                # the shaft leaves the bulb at its edge, from the bulb cell next to the shaft's first cell
                s0 = rc(sh[0])
                near = min(
                    bulb, key=lambda b: (rc(b)[0] - s0[0]) ** 2 + (rc(b)[1] - s0[1]) ** 2
                )  # straight-line nearest
                (bx, by), (fx, fy) = ctr(near), ctr(sh[0])
                L = math.hypot(fx - bx, fy - by) or 1
                start = (bx + (fx - bx) / L * 0.375 * u, by + (fy - by) / L * 0.375 * u)
                pts = [start] + [ctr(x) for x in sh]
                add(
                    "lines",
                    f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="none" stroke="#aaaaaa" '
                    f'stroke-width="{0.05 * u:.1f}" stroke-linecap="round" stroke-linejoin="round"/>',
                )
                chain = [near] + list(sh)
                (xa, ya), (xb, yb) = ctr(chain[-2]), ctr(chain[-1])
                L = math.hypot(xb - xa, yb - ya) or 1
                ux, uy = (xb - xa) / L, (yb - ya) / L
                h = 0.2 * u
                add(
                    "lines",
                    f'<polyline points="{xb - ux * h - uy * h:.1f},{yb - uy * h + ux * h:.1f} {xb:.1f},{yb:.1f} {xb - ux * h + uy * h:.1f},{yb - uy * h - ux * h:.1f}" '
                    f'fill="none" stroke="#aaaaaa" stroke-width="{0.05 * u:.1f}" stroke-linecap="round"/>',
                )
        elif t == "edge":
            (x0, y0), (x1, y1) = ctr(r["cells"][0]), ctr(r["cells"][1])
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            mk = EDGE[k].marker
            if mk == "dot":
                black = r["color"] == "black"
                add(
                    "clues",
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.125 * u:.1f}" fill="{"#000000" if black else "#ffffff"}" '
                    f'stroke="{T["ink"] if black and dark else "#000000"}" stroke-width="1.2"/>',
                )
            elif mk in ("letter", "chevron"):
                c = 0.15 * u  # one square chip on the edge midpoint, same for vertical and horizontal edges
                add(
                    "clues",
                    f'<rect x="{x - c:.1f}" y="{y - c:.1f}" width="{2 * c:.1f}" height="{2 * c:.1f}" rx="{0.03 * u:.1f}" fill="{T["clue_bg"]}"/>',
                )
                if mk == "letter":  # cap height ~0.7 em: shift the baseline so the letter's box is centred
                    add(
                        "clues",
                        f'<text x="{x:.1f}" y="{y + 0.35 * 0.3 * u:.1f}" font-size="{0.3 * u:.1f}" text-anchor="middle" '
                        f'font-family="Inter,Helvetica,Arial,sans-serif" font-weight="650" fill="{T["given"]}">{r[EDGE[k].param]}</text>',
                    )
                else:  # chevron pointing at the smaller digit, cells[1], symmetric about the midpoint
                    ux, uy = (x1 - x0), (y1 - y0)
                    L = math.hypot(ux, uy)
                    ux, uy = ux / L, uy / L
                    h = 0.075 * u
                    tip = (x + ux * h, y + uy * h)
                    b1 = (x - ux * h - uy * h * 1.25, y - uy * h + ux * h * 1.25)
                    b2 = (x - ux * h + uy * h * 1.25, y - uy * h - ux * h * 1.25)
                    add(
                        "clues",
                        f'<polyline points="{b1[0]:.1f},{b1[1]:.1f} {tip[0]:.1f},{tip[1]:.1f} {b2[0]:.1f},{b2[1]:.1f}" fill="none" '
                        f'stroke="{T["given"]}" stroke-width="{0.035 * u:.1f}" stroke-linecap="round" stroke-linejoin="round"/>',
                    )
            else:
                add("clues", circle_clue(x, y, EDGE[k].label(r)))
        elif t in ("corner", "contains") or (t == "sum" and k == "corner"):
            pts = [ctr(x) for x in r["cells"]]
            x, y = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            if t == "contains" and len(r["cells"]) != 4:
                first = min(r["cells"], key=lambda q: rc(q))
                rr, cc = rc(first)
                add(
                    "clues",
                    small_text(
                        m + cc * u + 0.08 * u,
                        m + rr * u + 0.15 * u,
                        "".join(map(str, r["digits"])),
                        size=0.2,
                        anchor="start",
                    ),
                )
            elif (
                t == "contains"
            ):  # quadruple: a circle on the shared corner (sudoku.coach): one or two digits as a word,
                # three or four in a compact 2 x 2 grid, bold, well inside the circle
                ds = list(r["digits"])
                add(
                    "clues",
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.3 * u:.1f}" fill="{T["clue_bg"]}" stroke="{T["given"]}" '
                    f'stroke-width="{max(1.0, 0.025 * u):.1f}"/>',
                )
                if len(ds) <= 2:
                    add("clues", small_text(x, y, "".join(map(str, ds)), size=0.22, weight=700))
                else:
                    g = 0.085 * u  # half the spacing of the 2 x 2 grid
                    spots = [(-1, -1), (1, -1), (0, 1)] if len(ds) == 3 else [(-1, -1), (1, -1), (-1, 1), (1, 1)]
                    for d, (dx, dy) in zip(ds, spots):
                        add("clues", small_text(x + dx * g, y + dy * g, d, size=0.17, weight=700))
            elif k == "battenburg":
                s = 0.15 * u
                for i, (dx, dy) in enumerate(((-1, -1), (0, -1), (-1, 0), (0, 0))):
                    add(
                        "clues",
                        f'<rect x="{x + dx * s:.1f}" y="{y + dy * s:.1f}" width="{s:.1f}" height="{s:.1f}" fill="{"#000" if i in (0, 3) else "#fff"}" stroke="#000" stroke-width=".8"/>',
                    )
            else:
                s = (
                    "".join(map(str, r["digits"]))
                    if t == "contains"
                    else (
                        r["sum"]
                        if t == "sum"
                        else (
                            f"{r.get('value', '')}{r.get('op', '')}"
                            if k == "mathrax" and r.get("op") not in ("even", "odd")
                            else ("E" if r.get("op") == "even" else "O")
                            if k == "mathrax"
                            else r.get("value", "")
                        )
                    )
                )
                add("clues", circle_clue(x, y, s, r=0.22 if t == "contains" else 0.15))
        elif t == "cell":
            for x in r["cells"]:
                cxx, cyy = ctr(x)
                mk = CELL[k].mark if k in CELL else "digits"
                # under annotation colours the shape's fill fades: its outline is drawn again above them (readable)
                edge = f'fill="none" stroke="{T["cand"]}" stroke-width="{0.035 * u:.1f}"'
                if colours and x in colours and mk in ("circle", "square", "diamond"):
                    d = 0.42 * u
                    add(
                        "marks",
                        f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{0.4 * u:.1f}" {edge}/>'
                        if mk == "circle"
                        else f'<rect x="{cxx - 0.4 * u:.1f}" y="{cyy - 0.4 * u:.1f}" width="{0.8 * u:.1f}" '
                        f'height="{0.8 * u:.1f}" {edge}/>'
                        if mk == "square"
                        else f'<polygon points="{cxx},{cyy - d} {cxx + d},{cyy} {cxx},{cyy + d} {cxx - d},{cyy}" {edge}/>',
                    )
                if mk == "circle":
                    add("shade", f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{0.4 * u:.1f}" fill="{T["odd"]}"/>')
                elif mk == "square":
                    add(
                        "shade",
                        f'<rect x="{cxx - 0.4 * u:.1f}" y="{cyy - 0.4 * u:.1f}" width="{0.8 * u:.1f}" height="{0.8 * u:.1f}" fill="{T["even"]}"/>',
                    )
                elif mk == "diamond":
                    d = 0.42 * u
                    add(
                        "shade",
                        f'<polygon points="{cxx},{cyy - d} {cxx + d},{cyy} {cxx},{cyy + d} {cxx - d},{cyy}" fill="{T[k]}"/>',
                    )
                else:
                    add(
                        "clues",
                        small_text(
                            cxx, cyy + 0.32 * u, "".join(map(str, r.get("values", []))), size=0.18, col=T["cand"]
                        ),
                    )
        elif (
            t in OUTSIDE or (t == "sum" and k in ("little_killer", "frame")) or (t == "distinct_count" and "side" in r)
        ):
            r0, c0 = rc(r["cells"][0])
            dr, dc = X.SIDES[r["side"]]
            x, y = cx(c0 + dc), cy(r0 + dr)
            if t == "rossini":
                s = "▲" if (r["arrow"] == "in") == (r["side"] == "bottom") else "▼"
                if r["side"] in ("left", "right"):
                    s = "◀" if (r["arrow"] == "in") == (r["side"] == "right") else "▶"
                add("outside", small_text(x, y, s, size=0.32, col=T["given"]))
            else:
                v = r.get("sum", r.get("value"))
                label = f"⟨{v}⟩" if t == "xsum" else str(v)
                add("outside", small_text(x, y, label, size=0.45, weight=500))
                if t == "sum" and k == "little_killer" and len(r["cells"]) > 1:
                    (xa, ya), (xb, yb) = ctr(r["cells"][0]), ctr(r["cells"][1])
                    L = math.hypot(xb - xa, yb - ya)
                    ux, uy = (xb - xa) / L, (yb - ya) / L
                    sx, sy = x + ux * 0.3 * u, y + uy * 0.3 * u
                    add(
                        "outside",
                        f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{sx + ux * 0.18 * u:.1f}" y2="{sy + uy * 0.18 * u:.1f}" stroke="{T["given"]}" stroke-width="1.4"/>',
                    )
        elif t == "relation":
            for a, b in r["pairs"]:
                (x0, y0), (x1, y1) = ctr(a), ctr(b)
                add(
                    "lines",
                    f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#aaaaaa" stroke-width="1"/>',
                )
        elif t == "equal_sum":
            for sgm in r["segments"]:
                add("cages", outline(sgm, 0.12, "3 3", T["cand"], 1))
        elif t == "clone":
            col = PALETTE[colour_i % len(PALETTE)]
            colour_i += 1
            for reg in r["regions"]:
                for x in reg:
                    rr, cc = rc(x)
                    add(
                        "shade",
                        f'<rect x="{m + cc * u}" y="{m + rr * u}" width="{u}" height="{u}" fill="{col}" opacity="{0.72 if dark else 1}"/>',
                    )
        elif t == "vudoku":  # a right-angle corner: elbow inside the vertex cell, arms reaching into the arm cells
            (vr, vc), arms = rc(r["cells"][0]), [rc(x) for x in r["cells"][1:]]
            d = [(ar - vr, ac - vc) for ar, ac in arms]
            if sorted(abs(a) + abs(b) for a, b in d) == [1, 1] and d[0][0] * d[1][0] + d[0][1] * d[1][1] == 0:
                sx, sy = sum(b for _, b in d), sum(a for a, _ in d)  # towards the corner the three cells share
                ex, ey = cx(vc) + sx * 0.2 * u, cy(vr) + sy * 0.2 * u
                pts = [(ex + b * 0.47 * u, ey + a * 0.47 * u) for a, b in d]
                add(
                    "lines",
                    f'<polyline points="{pts[0][0]:.1f},{pts[0][1]:.1f} {ex:.1f},{ey:.1f} {pts[1][0]:.1f},{pts[1][1]:.1f}" '
                    f'fill="none" stroke="#a7abb0" stroke-width="{0.08 * u:.1f}" stroke-linejoin="miter"/>',
                )
            else:  # not an L: a V through the cell centres
                add("lines", polyline([r["cells"][1], r["cells"][0], r["cells"][2]], "#a7abb0", 0.06))

    cur[0] = None
    if labels:  # r1.. down the left, c1.. along the top, in the muted text colour
        for r in range(R):
            add("outside", small_text(lab * 0.55, cy(r), f"r{r + 1}", size=0.26, col=T["cand"], weight=400))
        for c in range(C):
            add("outside", small_text(cx(c), lab * 0.55, f"c{c + 1}", size=0.26, col=T["cand"], weight=400))

    cur[0] = None  # decorations belong to no rule
    # ---- decorations (artwork, no rules; section 7): cell fills with the annotation colours; shapes, lines, text and
    # images under the lines and clues, or over everything with layer "over" (text defaults to over)
    P = lambda yx: (m + yx[1] * u, m + yx[0] * u)  # noqa: E731  [row, col] cell units from the board's corner -> px
    for dec in doc.get("decorations") or []:
        kind, st = dec.get("kind"), dec.get("style") or {}
        lay = "over" if dec.get("layer", "over" if kind == "text" else "under") == "over" else "colour"
        op = st.get("opacity", 1)
        stroke, fill = colour_of(st.get("color"), T["given"]), colour_of(st.get("fill"), "none")
        sw = (st.get("width") or 0.05) * u
        if kind == "fill":
            for name, cols in (dec.get("cells") or {}).items():
                cols = [colour_of(x) for x in (cols if isinstance(cols, list) else [cols])]
                cell_colours(name, [x for x in cols if x], op, st.get("pattern", "wedges"))
        elif kind in ("polygon", "line", "arrow") and dec.get("points"):
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(P, dec["points"]))
            tag = "polygon" if kind == "polygon" else "polyline"
            f = fill if kind == "polygon" else "none"
            add(lay, f'<{tag} points="{pts}" fill="{f}" stroke="{stroke}" stroke-width="{sw:.1f}" opacity="{op}" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')  # fmt: skip
            if kind == "arrow" and len(dec["points"]) >= 2:
                (xa, ya), (xb, yb) = P(dec["points"][-2]), P(dec["points"][-1])
                ang, h = math.atan2(yb - ya, xb - xa), 0.18 * u
                wing = [(xb - h * math.cos(ang + s_), yb - h * math.sin(ang + s_)) for s_ in (0.5, -0.5)]
                d = " ".join(f"{x:.1f},{y:.1f}" for x, y in (wing[0], (xb, yb), wing[1]))
                add(
                    lay,
                    f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{sw:.1f}" opacity="{op}"/>',
                )
        elif kind in ("rect", "circle", "image") and dec.get("center"):
            x, y = P(dec["center"])
            h, w = (dec.get("size") or [1, 1])[0] * u, (dec.get("size") or [1, 1])[-1] * u
            if kind == "rect":
                add(lay, f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" '
                         f'stroke="{stroke}" stroke-width="{sw:.1f}" opacity="{op}"/>')  # fmt: skip
            elif kind == "circle":
                add(lay, f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{w / 2:.1f}" ry="{h / 2:.1f}" fill="{fill}" '
                         f'stroke="{stroke}" stroke-width="{sw:.1f}" opacity="{op}"/>')  # fmt: skip
            elif dec.get("href"):
                add(lay, f'<image href="{esc(dec["href"])}" x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" '
                         f'height="{h:.1f}" opacity="{op}" preserveAspectRatio="none"/>')  # fmt: skip
        elif kind == "text" and dec.get("center") and dec.get("text") is not None:
            x, y = P(dec["center"])
            add(
                lay,
                small_text(
                    x, y, esc(str(dec["text"])), size=st.get("size", 0.3), col=colour_of(st.get("color"), T["given"])
                ),
            )
    # ---- digits and candidates (halo in the board colour)
    halo = (S["halo_dark"] if dark else S["halo_light"]) * u
    for i, v in enumerate(doc["givens"]):
        if not v:
            continue
        r, c = divmod(i, C)
        add(
            "digits",
            f'<text x="{cx(c):.1f}" y="{cy(r):.1f}" dy="0.36em" font-size="{S["digit"] * u:.1f}" text-anchor="middle" '
            f'font-family="Inter,Helvetica,Arial,sans-serif" font-weight="{S["given_w"]}" fill="{T["given"]}" stroke="{T["board"]}" '
            f'stroke-width="{halo:.2f}" paint-order="stroke" stroke-linejoin="round">{v}</text>',
        )
    for name, v in (placed or {}).items():
        r, c = rc(name)
        add(
            "digits",
            f'<text x="{cx(c):.1f}" y="{cy(r):.1f}" dy="0.36em" font-size="{S["digit"] * u:.1f}" text-anchor="middle" '
            f'font-family="Inter,Helvetica,Arial,sans-serif" font-weight="{S.get("placed_w", 500)}" fill="{T["placed"]}" '
            f'stroke="{T["board"]}" stroke-width="{halo:.2f}" paint-order="stroke" stroke-linejoin="round">{v}</text>',
        )
    # pencil marks: corner marks in SudokuPad's spots (corners first, then the edges' middles), centre marks in a row
    spots = [(0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8), (0.5, 0.2), (0.5, 0.8), (0.2, 0.5), (0.8, 0.5)]
    for name, mk in (marks or {}).items():
        if placed and name in placed:
            continue
        r, c = rc(name)
        here = spots[1:] if name in labelled else spots  # the top-left spot holds a cage total
        for d, (fx, fy) in zip(mk.get("corner") or [], here):
            add("digits", small_text(m + (c + fx) * u, m + (r + fy) * u, d, size=0.22, col=T["placed"], weight=400))
        cen = "".join(map(str, mk.get("centre") or []))
        if cen:
            size = 0.22 if len(cen) <= 4 else max(0.13, 0.88 / len(cen))
            add("digits", small_text(cx(c), cy(r), cen, size=size, col=T["placed"], weight=400))
    for name, ds in (doc.get("candidates") or {}).items():
        r, c = rc(name)
        for d in ds:
            x = m + c * u + u * (((d - 1) % 3) + 0.5) / 3
            y = m + r * u + u * (((d - 1) // 3) + 0.5) / 3
            add("digits", small_text(x, y, d, size=0.24, col=T["cand"], weight=400))
    body = "".join(
        "".join(layers[k])
        for k in ("shade", "colour", "marks", "lines", "cages", "grid", "clues", "digits", "outside", "over")
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.1f} {H:.1f}">'
        + (f'<rect width="{W:.1f}" height="{H:.1f}" fill="{T["page"]}"/>' if background else "")
        + f"{body}</svg>"
    )


def trace_position(doc, card, n):
    """(colours, placed, marks) of position n of a card's trace: each colour group's cells take its colour (a cell in
    several groups gets them all), every digit not given is a placed one, and the marks layer as written"""
    pos = card["trace"][n]
    colours = {}
    for g in pos.get("colours") or []:
        for name in g["cells"]:
            colours.setdefault(name, []).append(g["colour"])
    C = doc["board"]["cols"]
    placed = {
        f"r{i // C + 1}c{i % C + 1}": v for i, (v, g) in enumerate(zip(pos["digits"], doc["givens"])) if v and not g
    }
    return colours, placed, pos.get("marks") or {}


if __name__ == "__main__":
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    cell = int(sys.argv[sys.argv.index("--cell") + 1]) if "--cell" in sys.argv else 48
    colours = placed = marks = None
    if "--card" in sys.argv:
        card = json.load(open(sys.argv[sys.argv.index("--card") + 1], encoding="utf-8"))
        n = int(sys.argv[sys.argv.index("--position") + 1]) if "--position" in sys.argv else 0
        colours, placed, marks = trace_position(doc, card, n)
    svg = render(doc, dark="--dark" in sys.argv, cell=cell, colours=colours, placed=placed, marks=marks)
    Path(sys.argv[2]).write_text(svg, encoding="utf-8")
