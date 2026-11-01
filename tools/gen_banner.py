"""Draw the README banner (website/static/img/banner-light.png and banner-dark.png, 1280 x 400): the logo, the name, the
tagline and three puzzles the generator made (docs/examples/generated), drawn by tools/render_svg.py. Chromium renders
the page to PNG, so the text uses the same fonts as the docs site.
  python tools/gen_banner.py"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_svg  # noqa: E402

OUT = ROOT / "website" / "static" / "img"
BOARDS = ["classic", "tens", "long-lines"]  # docs/examples/generated/<name>.json, else docs/examples/<name>.json
THEME = {
    False: {"bg": "#fffdf8", "ink": "#1f1b17", "text": "#3d342b", "accent": "#7a5230"},
    True: {"bg": "#1b1b1d", "ink": "#f2efe9", "text": "#d6d0c6", "accent": "#d9a46c"},
}


def board(name):
    f = ROOT / "docs" / "examples" / "generated" / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))["puzzle"]
    return json.loads((ROOT / "docs" / "examples" / f"{name}.json").read_text(encoding="utf-8"))


def page(dark):
    t = THEME[dark]
    logo = (OUT / "favicon.svg").as_uri()
    boards = "".join(
        f'<div class="b" style="transform: rotate({a}deg) translateY({y}px)">{render_svg.render(board(n), dark=dark, cell=30)}</div>'
        for n, a, y in zip(BOARDS, (-6, 0, 6), (14, -6, 14))
    )
    return f"""<html><head><style>
body {{ margin: 0; width: 1280px; height: 400px; background: {t["bg"]}; font-family: 'Inter', 'Helvetica Neue', Arial,
       sans-serif; display: flex; align-items: center; justify-content: space-between; padding: 0 64px;
       box-sizing: border-box; overflow: hidden; }}
.name {{ display: flex; align-items: center; gap: 18px; margin-bottom: 22px; }}
.name span {{ font-size: 64px; font-weight: 700; color: {t["ink"]}; letter-spacing: -1px; }}
.tag {{ font-size: 28px; line-height: 1.3; color: {t["text"]}; max-width: 560px; }}
.sub {{ margin-top: 20px; font-size: 20px; color: {t["accent"]}; }}
.boards {{ display: flex; gap: 0; margin-right: -10px; }}
.b {{ margin-left: -36px; filter: drop-shadow(0 6px 14px rgba(0,0,0,{0.45 if dark else 0.14})); }}
.b svg {{ width: 230px; height: auto; display: block; }}
</style></head><body>
<div><div class="name"><img src="{logo}" width="72"><span>pencilmark</span></div>
<div class="tag">Human-like difficulty grader, solver and generator for classic and variant sudoku</div>
<div class="sub">Difficulty &middot; solve time &middot; band &middot; techniques &middot; explanations</div></div>
<div class="boards">{boards}</div>
</body></html>"""


def main():
    for dark, name in ((False, "banner-light.png"), (True, "banner-dark.png")):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(page(dark))
        subprocess.run(["chromium", "--headless", "--disable-gpu", "--hide-scrollbars", f"--screenshot={OUT / name}",
                        "--window-size=1280,400", Path(f.name).as_uri()], check=True, capture_output=True)  # fmt: skip
        Path(f.name).unlink()
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
