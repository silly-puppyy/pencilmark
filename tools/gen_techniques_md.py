"""Write docs/TECHNIQUES.md, the technique codes by family, from the technique registry (data/techniques.csv,
data/codes.csv) and the explanation catalogue's links (explain.CATALOG). Reads the source tree; the C++ engine need not
be built.
  python tools/gen_techniques_md.py [--check]      --check: exit 1 if docs/TECHNIQUES.md is out of date"""

import csv
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pencilmark import explain as E  # noqa: E402
from pencilmark import registry as R  # noqa: E402

FAMILY_TITLES = {
    "singles": "Singles",
    "intersections+combos": "Intersections and rule combinations",
    "subsets": "Subsets",
    "fish+wings": "Fish and wings",
    "chains": "Chains and colouring",
    "ALS": "Almost locked sets",
    "trial": "Trial and forcing",
}
# link icon per site (website/static/img/sites, made by tools/site_icons.py); a site without one gets a text badge
SITES = {
    "www.sudokuwiki.org": ("sudokuwiki.org", "sudokuwiki.png"),
    "hodoku.sourceforge.net": ("HoDoKu", "hodoku.png"),
    "sudoku.coach": ("sudoku.coach", "sudokucoach.png"),
    "sudoku.com": ("sudoku.com", "sudokucom.png"),
    "www.sudokusnake.com": ("Sudoku Snake", "sudokusnake.png"),
    "krazydad.com": ("KrazyDad", "krazydad.png"),
    "en.wikipedia.org": ("Wikipedia", "wikipedia.png"),
}
LINKS = ROOT / "docs" / "technique_links.csv"  # more explainer pages per code, beside the explanation catalogue's


# fish shapes the engine names by size and kind, not by a pattern code: they take the family of a related code
SHAPE_OF = {"FSW": "FXW", "FJF": "FXW", "FRK": "XWG"}


def immediate(code, codes):
    """the codes `code` is a special case of, without those reachable through another of them"""

    def closure(c, seen=None):
        seen = set() if seen is None else seen
        for s in codes[c].subset_of:
            if s not in seen:
                seen.add(s)
                closure(s, seen)
        return seen

    sup = closure(code)
    return sorted(s for s in sup if not any(s in closure(t) for t in sup if t != s))


def _site_rank(url):
    """links in the order of SITES (the same order in every row)"""
    hosts = list(SITES)
    host = urlparse(url).netloc
    return hosts.index(host) if host in hosts else len(hosts)


def link(url):
    """a site icon (or a text badge) linking out, marked as external"""
    title, icon = SITES.get(urlparse(url).netloc, (urlparse(url).netloc, None))
    if icon:
        img = f'<img src="/pencilmark/img/sites/{icon}" alt="{title}" class="pm-site"/>'
        return f'<a href="{url}" title="{title}" class="pm-site-link">{img}</a>'
    return f'<a href="{url}" title="{title}" class="pm-site-link pm-site-text">{title}</a>'


def page():
    codes = R.codes()
    tech_of = {}
    for t in R.techniques():
        if t.code and t.role == "logic":
            tech_of.setdefault(t.code, t)
    by_name = {t.name: t for t in R.techniques()}
    for pt in R.patterns():  # shape codes of a split technique (Skyscraper of X-Chain, Phistomefel of leftovers)
        if pt.code not in tech_of and pt.technique in by_name:
            tech_of[pt.code] = by_name[pt.technique]
    for code, like in SHAPE_OF.items():
        tech_of.setdefault(code, tech_of[like])
    extra = {}
    for r in csv.DictReader(LINKS.open(encoding="utf-8")):
        extra.setdefault(r["code"], []).append(r["url"])
    rows = {f: [] for f in FAMILY_TITLES}
    for code, c in codes.items():
        t = tech_of.get(code)
        if t is None:
            continue
        band = c.shape_band if c.shape_band is not None else t.band
        urls = list(dict.fromkeys((E.CATALOG[c.explain][3] if c.explain else []) + extra.get(code, [])))
        name = c.name + (" *(variant)*" if t.gate else "")
        sub = ", ".join(f"`{s}`" for s in immediate(code, codes))
        rows[t.family].append(
            (
                band,
                c.order,
                f"| `{code}` | {name} | {R.BANDS[band].replace(' ', '&nbsp;')} | {sub} | {' '.join(map(link, sorted(urls, key=_site_rank)))} |",
            )
        )
    L = [
        "---",
        "title: Techniques",
        "description: Every technique code on the card, by family, with its band and links to explainer sites.",
        "---",
        "",
        "# Techniques",
        "",
        "The `contains` field of a card lists techniques by three-letter code, Andrew Stuart's",
        "([sudokuwiki.org](https://www.sudokuwiki.org)) where he has the strategy. A step is named by the most specific",
        "shape found: a Skyscraper is `SKY`, not X-Chain. **Special case of** names the next more general technique: an",
        "X-Wing is a special case of a Skyscraper, so if you know Skyscrapers you can solve an X-Wing step. Each family is",
        "sorted by band. The links go to explanations on other sites.",
        "",
        "This page is generated from `pencilmark/data/codes.csv`, `techniques.csv` and `docs/technique_links.csv`\n(`tools/gen_techniques_md.py`).",
        "",
    ]
    for fam, title in FAMILY_TITLES.items():
        if not rows[fam]:
            continue
        L += [f"## {title}", "", "| Code | Technique | Band | Special case of | Learn |", "|---|---|---|---|---|"]
        L += [r for _, _, r in sorted(rows[fam], key=lambda x: (x[0], x[1]))]
        L.append("")
    return "\n".join(L)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = ROOT / "docs" / "TECHNIQUES.md"
    text = page()
    if "--check" in argv:
        ok = out.is_file() and out.read_text(encoding="utf-8") == text
        print(
            "docs/TECHNIQUES.md is up to date"
            if ok
            else "docs/TECHNIQUES.md is out of date: run tools/gen_techniques_md.py"
        )
        return 0 if ok else 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
