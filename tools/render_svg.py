"""Draw a sudoku-puzzle file as SVG, following the default drawing of docs/STYLE.md (reference renderer for
the docs; not part of the package).
  python tools/render_svg.py puzzle.json out.svg [--dark] [--cell 48]
  render(doc, dark=False, cell=48) -> svg text"""

import json
import math
import sys
from pathlib import Path

try:  # an installed pencilmark (with its engine) if there is one, else the source tree
    from pencilmark import exchange as X
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from pencilmark import exchange as X  # noqa: E402

# board style, in cell units unless noted (docs/STYLE.md; values in docs/palette.json)
_PAL = json.loads((Path(__file__).resolve().parents[1] / "docs/palette.json").read_text(encoding="utf-8"))
STYLE = _PAL["sizes"]
THEMES = {False: _PAL["themes"]["light"], True: _PAL["themes"]["dark"]}
LINE_COLOURS = {k: v for k, v in _PAL["lines"].items() if k != "dutch_whisper"}
DUTCH = _PAL["lines"]["dutch_whisper"]
PALETTE = _PAL["region_palette"]
OUTSIDE = ("sandwich", "xsum", "skyscraper", "rossini", "first_seen")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(doc, dark=False, cell=48):
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
    W, H = C * u + 2 * m, R * u + 2 * m
    rc = lambda name: X.parse_cell(name)
    cx = lambda c: m + (c + 0.5) * u
    cy = lambda r: m + (r + 0.5) * u
    ctr = lambda name: (cx(rc(name)[1]), cy(rc(name)[0]))
    exists = {(r, c) for r, c in B.coords}
    layers = {k: [] for k in ("shade", "lines", "cages", "grid", "clues", "digits", "outside")}
    add = lambda k, s: layers[k].append(s)

    # ---- board, houses
    for r, c in B.coords:
        add("shade", f'<rect x="{m + c * u}" y="{m + r * u}" width="{u}" height="{u}" fill="{T["board"]}"/>')
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
                f'stroke-linecap="square" shape-rendering="crispEdges"/>',
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
                ext = lambda a, b: (i if (r + a, c + b) not in st else -i)
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
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * u:.1f}" fill="{T["clue_bg"]}" stroke="{T["given"]}" stroke-width="1"/>'
            + small_text(x, y, s, size=0.19)
        )

    def polyline(cells, col, w, closed=False):
        pts = [ctr(x) for x in cells] + ([ctr(cells[0])] if closed else [])
        return (
            f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="none" stroke="{col}" '
            f'stroke-width="{w * u:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    colour_i = 0
    for r in rules:
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
            elif k == "colour":
                col = PALETTE[colour_i % len(PALETTE)]
                colour_i += 1
                for x in r["cells"]:
                    rr, cc = rc(x)
                    add(
                        "shade",
                        f'<rect x="{m + cc * u}" y="{m + rr * u}" width="{u}" height="{u}" fill="{col}" opacity="{0.55 if dark else 1}"/>',
                    )
        elif t == "cage" or (t == "sum" and k == "group"):
            add("cages", outline(r["cells"], 0.08, "4 3" if t == "cage" else "1.5 3", T["given"], 1.2))
            if "sum" in r:
                first = min(r["cells"], key=lambda x: rc(x))
                rr, cc = rc(first)
                add(
                    "cages",
                    f'<rect x="{m + cc * u + 0.05 * u:.1f}" y="{m + rr * u + 0.05 * u:.1f}" width="{0.3 * u:.1f}" height="{0.24 * u:.1f}" fill="{T["board"]}"/>',
                )
                add(
                    "cages",
                    small_text(m + cc * u + 0.09 * u, m + rr * u + 0.17 * u, r["sum"], size=0.22, anchor="start"),
                )
        elif t == "line":
            col = DUTCH if (k == "whisper" and r.get("value", 5) == 4) else LINE_COLOURS.get(k, "#aaaaaa")
            w = (
                S["thermo"]
                if k in ("thermo", "slow_thermo")
                else (0.1 if k == "between" else 0.05 if k in ("lockout", "double_arrow") else S["line"])
            )
            add("lines", polyline(r["cells"], col, w, r.get("closed", False)))
            if k == "thermo":
                x, y = ctr(r["cells"][0])
                add("lines", f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{S["bulb"] * u:.1f}" fill="{col}"/>')
            if k == "slow_thermo":
                x, y = ctr(r["cells"][0])
                add(
                    "lines",
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{S["bulb"] * u:.1f}" fill="{T["board"]}" stroke="{col}" stroke-width="{0.12 * u:.1f}"/>',
                )
            if k in ("between", "double_arrow"):
                for e in (r["cells"][0], r["cells"][-1]):
                    x, y = ctr(e)
                    add(
                        "lines",
                        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.375 * u:.1f}" fill="{T["board"]}" stroke="{col}" stroke-width="{0.05 * u:.1f}"/>',
                    )
            if k == "lockout":
                for e in (r["cells"][0], r["cells"][-1]):
                    x, y = ctr(e)
                    d = 0.4 * u
                    add(
                        "lines",
                        f'<polygon points="{x},{y - d} {x + d},{y} {x},{y + d} {x - d},{y}" fill="{T["board"]}" stroke="{col}" stroke-width="{0.05 * u:.1f}"/>',
                    )
            if k == "zipper":  # small dot at the line's centre (a cell, or between the two middle cells)
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
            if k == "kropki":
                black = r["color"] == "black"
                add(
                    "clues",
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.125 * u:.1f}" fill="{"#000000" if black else "#ffffff"}" '
                    f'stroke="{T["ink"] if black and dark else "#000000"}" stroke-width="1.2"/>',
                )
            elif k in ("xv", "less"):
                c = 0.15 * u  # one square chip on the edge midpoint, same for vertical and horizontal edges
                add(
                    "clues",
                    f'<rect x="{x - c:.1f}" y="{y - c:.1f}" width="{2 * c:.1f}" height="{2 * c:.1f}" rx="{0.03 * u:.1f}" fill="{T["clue_bg"]}"/>',
                )
                if k == "xv":  # cap height ~0.7 em: shift the baseline so the letter's box is centred
                    add(
                        "clues",
                        f'<text x="{x:.1f}" y="{y + 0.35 * 0.3 * u:.1f}" font-size="{0.3 * u:.1f}" text-anchor="middle" '
                        f'font-family="Inter,Helvetica,Arial,sans-serif" font-weight="650" fill="{T["given"]}">{r["letter"]}</text>',
                    )
                else:  # chevron pointing at cells[0], symmetric about the midpoint
                    ux, uy = (x0 - x1), (y0 - y1)
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
                v = r.get("value", r.get("sum"))
                s = f"{v}:1" if k == "ratio" else (f"×{v}" if k == "product" else str(v))
                add("clues", circle_clue(x, y, s))
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
                if k == "odd":
                    add("shade", f'<circle cx="{cxx:.1f}" cy="{cyy:.1f}" r="{0.4 * u:.1f}" fill="{T["odd"]}"/>')
                elif k == "even":
                    add(
                        "shade",
                        f'<rect x="{cxx - 0.4 * u:.1f}" y="{cyy - 0.4 * u:.1f}" width="{0.8 * u:.1f}" height="{0.8 * u:.1f}" fill="{T["even"]}"/>',
                    )
                elif k in ("low", "high"):
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
                add("outside", small_text(x, y, label, size=0.36, weight=500))
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
                        f'<rect x="{m + cc * u}" y="{m + rr * u}" width="{u}" height="{u}" fill="{col}" opacity="{0.55 if dark else 1}"/>',
                    )
        elif t == "vudoku":
            add("lines", polyline([r["cells"][1], r["cells"][0], r["cells"][2]], "#aaaaaa", 0.04))

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
    for name, ds in (doc.get("candidates") or {}).items():
        r, c = rc(name)
        for d in ds:
            x = m + c * u + u * (((d - 1) % 3) + 0.5) / 3
            y = m + r * u + u * (((d - 1) // 3) + 0.5) / 3
            add("digits", small_text(x, y, d, size=0.24, col=T["cand"], weight=400))
    body = "".join("".join(layers[k]) for k in ("shade", "lines", "cages", "grid", "clues", "digits", "outside"))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.1f} {H:.1f}">'
        f'<rect width="{W:.1f}" height="{H:.1f}" fill="{T["page"]}"/>{body}</svg>'
    )


if __name__ == "__main__":
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    cell = int(sys.argv[sys.argv.index("--cell") + 1]) if "--cell" in sys.argv else 48
    Path(sys.argv[2]).write_text(render(doc, dark="--dark" in sys.argv, cell=cell), encoding="utf-8")
