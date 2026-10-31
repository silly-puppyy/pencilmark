"""Make the explainer-site icons of docs/TECHNIQUES.md (website/static/img/sites/*.png, 64x64, committed).
Each site's favicon, scaled; HoDoKu has none, so its logo's three syllables (Ho / Do / Ku) are cut from the site's
header image and stacked into a square. Needs network access and Pillow; run it when a site is added or changes its
icon, not in the docs build.
  python tools/site_icons.py"""

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "website" / "static" / "img" / "sites"
UA = {"User-Agent": "pencilmark-docs (+https://github.com/silly-puppyy/pencilmark)"}
FAVICONS = {
    "sudokuwiki": "https://www.sudokuwiki.org/favicon.ico",
    "sudokusnake": "https://www.sudokusnake.com/favicon.ico",
    "wikipedia": "https://en.wikipedia.org/favicon.ico",
}
HODOKU_HEAD = "https://hodoku.sourceforge.net/img/head.png"
HODOKU_SYLLABLES = [(329, 435), (436, 547), (548, 654)]  # x ranges of "Ho", "Do", "Ku" in head.png (980 x 110)


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def favicon(data):
    im = Image.open(io.BytesIO(data))
    if im.info.get("sizes"):
        im.size = max(im.info["sizes"])  # an .ico holds several sizes: take the largest
    return im.convert("RGBA")


def hodoku(data):
    """the logo's syllables, stacked: the letters' rows found as the rows with dark pixels above the grid strip"""
    src = Image.open(io.BytesIO(data)).convert("RGBA")
    grey = src.convert("L")
    x0, x1 = HODOKU_SYLLABLES[0][0], HODOKU_SYLLABLES[-1][1]
    rows = [y for y in range(5, 86) if any(grey.getpixel((x, y)) < 100 for x in range(x0, x1))]
    parts = [src.crop((a, rows[0], b, rows[-1] + 1)) for a, b in HODOKU_SYLLABLES]
    w, h = max(p.width for p in parts), sum(p.height for p in parts)
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (255, 255, 255, 255))
    y = (side - h) // 2
    for p in parts:
        square.paste(p, ((side - p.width) // 2, y))
        y += p.height
    return square


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    icons = {name: favicon(fetch(url)) for name, url in FAVICONS.items()}
    icons["hodoku"] = hodoku(fetch(HODOKU_HEAD))
    for name, im in icons.items():
        im.resize((64, 64), Image.LANCZOS).save(
            OUT / f"{name}.png", optimize=True
        )  # shown at 22 px; 64 keeps them sharp on dense screens
        print(f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
