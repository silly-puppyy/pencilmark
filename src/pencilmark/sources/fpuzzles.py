"""f-puzzles (f-puzzles.com) links and payloads -> puzzle JSON.

Link forms
    https://f-puzzles.com/?load=<lz-string>      the puzzle is in the URL (no network)
    https://f-puzzles.com/?id=<alias>            a TinyURL alias: fetch() resolves tinyurl.com/<alias> (one HEAD request)
    'fpuzzles<lz>' / 'fpuz<lz>' payloads, SudokuPad links carrying them, or the decoded f-puzzles dict itself.
Translation (_fpuz_translate) is exact for typed constraints (killer cages,
thermometers, arrows, whispers, renban, palindromes, between lines, kropki / XV (+ negative), odd / even, diagonals,
anti-knight / anti-king, disjoint groups, nonconsecutive, little killers, sandwiches, quadruples, min / max).
Generic 'line' / 'cage' / 'circle' entries (meaning only in the rules text), fog of war, indexers -> UnsupportedPuzzle,
unless reading= gives the line kinds per colour or infer=True searches them with the solver (slow).

    payload_of(url) -> 'fpuzzles...' | None      decode(x, fetch=False) -> f-puzzles dict
    fetch(short_link) -> f-puzzles dict           translate(x, rules_text=None, reading=None, infer=False) -> (Puzzle, info)
    to_puzzle(x, rules_text=None, reading=None, infer=False, fetch=True) -> puzzle JSON dict
"""

from __future__ import annotations

import re
import urllib.parse

from ._common import DecodeError, Http, to_puzzle_json, unsupported_from_reason

HTTP = Http(min_gap=1.0)


def is_fpuzzles_url(s):
    return isinstance(s, str) and "://" in s and "f-puzzles.com" in urllib.parse.urlsplit(s.strip()).netloc


def payload_of(url):
    """f-puzzles URL (?load=...) -> 'fpuzzles<lz-string>' or None."""
    q = urllib.parse.urlparse(url).query
    m = re.search(r"(?:^|&)load=([^&]+)", q) or re.search(r"load=([^&#]+)", url)
    return ("fpuzzles" + urllib.parse.unquote(m.group(1))) if m else None


def short_id(url):
    m = re.search(r"[?&]id=([0-9A-Za-z_-]+)", url)
    return m.group(1) if m else None


def decode(x, fetch=False):
    """f-puzzles link / payload / dict -> the f-puzzles JSON dict (grid, size, killercage, thermometer, ...)."""
    from ._fpuz_translate import decode_fpuz

    if isinstance(x, dict):
        if "puzzle" in x and x.get("format") == "fpuzzles":
            return x["puzzle"]
        if "grid" in x or "size" in x:
            return x
        raise DecodeError("dict is not an f-puzzles puzzle")
    if not isinstance(x, str) or not x.strip():
        raise DecodeError("empty f-puzzles link / payload")
    s = x.strip()
    if "://" in s:
        if is_fpuzzles_url(s):
            pl = payload_of(s)
            if pl is None:
                if short_id(s):
                    if fetch:
                        return globals()["fetch"](s)
                    raise DecodeError(
                        f"{s!r} is an f-puzzles short link (TinyURL alias); resolve it with fpuzzles.fetch()"
                    )
                raise DecodeError(f"no puzzle in f-puzzles link {s[:80]!r}")
        else:  # e.g. a SudokuPad link carrying an f-puzzles payload
            from .sudokupad import payload_key

            pl = payload_key(s)
    else:
        pl = s if s.startswith(("fpuzzles", "fpuz")) else "fpuzzles" + s
    fp = decode_fpuz(pl) if pl.startswith(("fpuzzles", "fpuz")) else None
    if fp is None:
        raise DecodeError("undecodable f-puzzles payload")
    return fp


def fetch(short_link, http=None):
    """f-puzzles ?id=<alias> -> resolve tinyurl.com/<alias> (one HEAD request, not followed) -> decoded dict."""
    sid = short_id(short_link) if "://" in short_link else short_link
    if not sid or not re.fullmatch(r"[0-9A-Za-z_-]+", sid):
        raise DecodeError(f"not an f-puzzles short link: {short_link[:80]!r}")
    target = (http or HTTP).redirect_target(f"https://tinyurl.com/{sid}")
    if not target or "load=" not in target:
        raise DecodeError(f"TinyURL alias {sid} did not resolve to an f-puzzles ?load= link ({str(target)[:80]})")
    return decode(target)


def translate(x, rules_text=None, reading=None, infer=False, fetch=True):
    """-> (engine Puzzle (not finalized), info). rules_text fills a missing 'ruleset' (it is read for negative
    constraints and line keywords). Raises UnsupportedPuzzle / DecodeError."""
    from . import _fpuz_translate as FT

    fp = dict(decode(x, fetch=fetch))
    if rules_text and not fp.get("ruleset"):
        fp["ruleset"] = rules_text
    if reading:
        p, info = FT.translate(fp, line_kinds=reading)
    elif infer and fp.get("line"):
        p, info = FT.infer_lines(fp)
    else:
        p, info = FT.translate(fp)
    if p is None:
        raise unsupported_from_reason(info, "f-puzzles")
    return p, info


def to_puzzle(x, rules_text=None, reading=None, infer=False, fetch=True, url=None):
    """f-puzzles link / payload / dict -> puzzle JSON dict (title, author, rules_text, source, embedded solution)."""
    from ._fpuz_translate import solution_of

    fp = decode(x, fetch=fetch)
    p, _ = translate(fp, rules_text=rules_text, reading=reading, infer=infer)
    src = url or (x if isinstance(x, str) and "://" in x else None)
    meta = {
        "title": fp.get("title"),
        "author": fp.get("author"),
        "rules_text": fp.get("ruleset") or rules_text,
        "source": src,
    }
    return to_puzzle_json(p, solution=solution_of(fp), meta=meta)


__all__ = ["decode", "fetch", "translate", "to_puzzle", "payload_of", "short_id", "is_fpuzzles_url"]
