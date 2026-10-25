"""Logic Masters Deutschland (logic-masters.de) puzzle portal: a polite client + parsers + link -> puzzle JSON.

Politeness: robots.txt is fetched first and obeyed (urllib.robotparser; today it disallows /Raetselportal/Benutzer/,
/Statistik/ and /Suche/erweitert.php -- this client only reads Raetsel/zeigen.php, Raetsel/loeserliste.php and
Suche/einfach.php), one request at a time, >= 2.5 s apart (LMD answers 503 when hit faster), an identifying
User-Agent (pencilmark.sources._common.USER_AGENT; override with PENCILMARK_UA), 30 s timeouts, at most one retry.

    listing(page=0, sort="oft") -> {"rows": [{rank, id, title, author, date, solved, difficulty, rating}], "last_page"}
    puzzle(lmd_id, solvers=False) -> {id, title, author, published, difficulty, rating, solved, observed, labels, tags,
                                      text (rules / page text), links: {sudokupad, fpuzzles, penpa, short, other},
                                      comments, is_sudoku[, solvers]}
    parse_puzzle(lmd_id, html) / parse_listing(html)   (offline parsers; e.g. on cached pages)
    to_puzzle(lmd_id_or_record, resolve_short=True) -> puzzle JSON from the first linked puzzle that converts
                                                       (SudokuPad > f-puzzles > penpa), with the page text as rules.
"""
from __future__ import annotations

import html as _html
import re
import urllib.parse

from ._common import FetchError, Http, SourceError, UnsupportedPuzzle

BASE = "https://logic-masters.de/Raetselportal"
HTTP = Http(min_gap=2.5, respect_robots=True)
ID_RE = re.compile(r"^[0-9A-Za-z]{6}$")
SHORTENERS = ("tinyurl.com", "bit.ly", "git.io", "is.gd", "tiny.cc", "t.ly", "rb.gy", "shorturl.at")
ROW = re.compile(r'<tr><td style="text-align:right">(\d+)\.<td>.*?zeigen\.php\?id=([0-9A-Za-z]{6})">([^<]*)</a>'
                 r'.*?name=[^"]*">([^<]*)</a> \(on ([^)]*)\)</span><td align="center">(\d+)<td align="center">'
                 r'(?:<img src="/Raetselportal/bilder/level(\d+)\.png"[^>]*>)?(?:<br><span[^>]*>(\d+)&nbsp;%)?', re.S)


def _text(fragment):
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"[ \t]+", " ", _html.unescape(t)).strip()


def classify_links(urls):
    """-> {"sudokupad", "fpuzzles", "penpa", "short", "other"} (sorted, de-duplicated)."""
    out = {"sudokupad": set(), "fpuzzles": set(), "penpa": set(), "short": set(), "other": set()}
    for u in urls:
        u = _html.unescape(u).strip()
        lo = u.lower()
        if "sudokupad.app" in lo or "crackingthecryptic.com" in lo:
            out["sudokupad"].add(u)
        elif "f-puzzles.com" in lo:
            out["fpuzzles"].add(u)
        elif "penpa" in lo and re.search(r"[?#&]p=", u):
            out["penpa"].add(u)
        elif urllib.parse.urlsplit(lo).netloc.removeprefix("www.") in SHORTENERS:
            out["short"].add(u)
        else:
            out["other"].add(u)
    return {k: sorted(v) for k, v in out.items()}


def parse_puzzle(pid, h):
    """Puzzle page HTML -> record (None when the page holds no puzzle).
    plus 'links' (all external puzzle links, incl. penpa on any host and URL-shortener links)."""
    if "Difficulty:" not in h and "Schwierigkeit:" not in h:
        return None
    r = {"id": pid}
    m = re.search(r"<h2[^>]*>(.*?)</h2>", h, flags=re.S)
    r["title"] = _text(m.group(1)) if m else None
    m = re.search(r"\((?:Published|Eingestellt)(?: on| am)? ([^<]*?) (?:by|von)\s*<a[^>]*>([^<]*)</a>", h)
    if m:
        r["published"], r["author"] = m.group(1).strip(), _html.unescape(m.group(2)).strip()
    m = re.search(r"bilder/level(\d+)\.png", h)
    r["difficulty"] = int(m.group(1)) if m else None
    m = re.search(r"(?:Rating|Bewertung):<td><span[^>]*>(\d+)&nbsp;%", h)
    r["rating"] = int(m.group(1)) if m else None
    m = re.search(r"(?:Solved|Gelöst):<td>(\d+)", h)
    r["solved"] = int(m.group(1)) if m else 0
    m = re.search(r"(?:Observed|Beobachtet):<td>(\d+)", h)
    r["observed"] = int(m.group(1)) if m else 0
    r["labels"] = re.findall(r'labels/[^"]+"\s+alt="([^"]+)"', h)
    r["tags"] = [_text(t) for t in re.findall(r'<a href="/Raetselportal/Suche/[^"]*"[^>]*>([^<]+)</a>', h)]
    m = re.search(r'<div class="rp_html">(.*?)</div>\s*(?:<div|<h3|<hr)', h, flags=re.S)
    body = m.group(1) if m else ""
    r["text"] = _text(body)[:20000] if m else None
    hrefs = re.findall(r'href="(https?://[^"]+)"', h)     # whole page, as lmd_scrape (comments can carry links)
    r["links"] = classify_links([u for u in hrefs if "logic-masters.de" not in u])
    r["sudokupad"], r["other_links"] = r["links"]["sudokupad"], r["links"]["fpuzzles"] + r["links"]["penpa"]
    comments = []
    cz = h[h.find("<h3>Comments</h3>"):] if "<h3>Comments</h3>" in h else ""
    for cm in re.finditer(r"<p><b>(?:on )?([^<]*?) by ([^<]*)</b><br>(.*?)</div>", cz, flags=re.S):
        comments.append({"time": cm.group(1).strip(), "user": _html.unescape(cm.group(2)).strip(),
                         "text": _text(cm.group(3))[:2000]})
    r["comments"] = comments
    r["is_sudoku"] = any("udoku" in t for t in r["tags"]) or any("udoku" in (lb or "") for lb in r["labels"])
    return r


def parse_solvers(h):
    return [(_html.unescape(n).strip(), t.strip()) for n, t in
            re.findall(r'<td><a href="/Raetselportal/Benutzer/allgemein\.php\?name=[^"]*">([^<]+)</a><td>on ([^<]+)', h)]


def parse_listing(h):
    rows = [{"rank": int(rank), "id": pid, "title": _html.unescape(title), "author": _html.unescape(author),
             "date": date, "solved": int(solved), "difficulty": int(level) if level else None,
             "rating": int(rating) if rating else None}
            for rank, pid, title, author, date, solved, level, rating in ROW.findall(h)]
    starts = [int(x) for x in re.findall(r"einfach\.php\?start=(\d+)&amp;sort=", h)]
    return rows, (max(starts) // 20 if starts else None)


def listing(page=0, sort="oft", http=None):
    """One page (20 puzzles) of the portal's basic search; sort 'oft' = most often solved (LMD's own sort keys)."""
    h = (http or HTTP).get_text(f"{BASE}/Suche/einfach.php?start={int(page) * 20}&sort={sort}&chlang=en")
    rows, last = parse_listing(h)
    return {"rows": rows, "last_page": last}


def fetch_page(lmd_id, http=None):
    if not ID_RE.match(str(lmd_id)):
        raise SourceError(f"not an LMD puzzle id: {lmd_id!r}")
    return (http or HTTP).get_text(f"{BASE}/Raetsel/zeigen.php?id={lmd_id}&chlang=en")


def puzzle(lmd_id, solvers=False, http=None):
    """Fetch and parse one puzzle page (+ the solver list when solvers=True: one more request)."""
    r = parse_puzzle(lmd_id, fetch_page(lmd_id, http))
    if r is None:
        raise SourceError(f"LMD {lmd_id}: no puzzle on this page")
    if solvers and r["solved"]:
        r["solvers"] = parse_solvers((http or HTTP).get_text(f"{BASE}/Raetsel/loeserliste.php?id={lmd_id}&chlang=en"))
    return r


def lmd_id_of(url):
    m = re.search(r"logic-masters\.de/Raetselportal/Raetsel/(?:zeigen|loeserliste)\.php\?(?:[^#]*&)?id=([0-9A-Za-z]{6})", url)
    return m.group(1) if m else None


def resolve_short(url, http=None):
    """URL-shortener link -> its redirect target (one HEAD request, redirect not followed); None on failure."""
    try:
        return (http or Http(min_gap=1.0)).redirect_target(url)
    except FetchError:
        return None


def candidate_links(rec, resolve_short_links=True, http=None):
    """Puzzle links of a record in conversion order: SudokuPad, f-puzzles, penpa (short links resolved and sorted in)."""
    links = rec.get("links") or classify_links((rec.get("sudokupad") or []) + (rec.get("other_links") or []))
    extra = []
    if resolve_short_links:
        for u in links.get("short", []):
            t = resolve_short(u, http)
            if t:
                extra.append(t)
    links2 = classify_links(sum((links.get(k, []) for k in ("sudokupad", "fpuzzles", "penpa")), []) + extra)
    return links2["sudokupad"] + links2["fpuzzles"] + links2["penpa"]


def to_puzzle(lmd_id_or_record, resolve_short=True, infer=False, http=None):
    """LMD id (fetches the page) or a parsed record -> puzzle JSON of the first linked puzzle that converts, with the
    page text as the rules text. Raises UnsupportedPuzzle with every link's reason when none converts."""
    from . import load
    rec = lmd_id_or_record if isinstance(lmd_id_or_record, dict) else puzzle(lmd_id_or_record, http=http)
    cands = candidate_links(rec, resolve_short, http)
    if not cands:
        raise UnsupportedPuzzle(["no SudokuPad / f-puzzles / penpa link on the page"], f"LMD {rec.get('id')}")
    reasons = []
    for u in cands:
        try:
            pj = load(u, rules_text=rec.get("text") or None, infer=infer)
        except SourceError as e:
            reasons.append(f"{u[:60]}: {e}")
            continue
        m = pj.setdefault("meta", {})
        if rec.get("title"):
            m.setdefault("title", rec["title"])
        if rec.get("author"):
            m.setdefault("author", rec["author"])
        m["id"] = f"lmd:{rec.get('id')}"
        if rec.get("published"):
            m.setdefault("date", rec["published"])
        m["lmd"] = {k: rec.get(k) for k in ("id", "difficulty", "rating", "solved", "published")}
        return pj
    raise UnsupportedPuzzle(reasons, f"LMD {rec.get('id')}")


__all__ = ["listing", "puzzle", "parse_puzzle", "parse_listing", "parse_solvers", "to_puzzle", "classify_links",
           "candidate_links", "resolve_short", "lmd_id_of", "fetch_page"]
