"""SudokuPad (sudokupad.app / app.crackingthecryptic.com) links and payloads -> puzzle JSON.

Link forms
    https://sudokupad.app/<shortid>                     short link: resolved by fetch() via sudokupad.app/api/puzzle/<id>
    https://sudokupad.app/[sudoku/]scl<lz-base64>       SudokuPad compact JSON (also 'ctc' prefix)
    https://sudokupad.app/[sudoku/]fpuzzles<lz-base64>  an f-puzzles payload (also 'fpuz', ?puzzleid=...)
decode() returns {"format": "scl"|"ctc"|"fpuzzles"|"json", "meta": {title, author, rules, solution, ...},
"puzzle": <SudokuPad JSON with expanded keys | f-puzzles JSON>}.

to_puzzle() translates with _sp_translate: line meanings come from the
rules text (colour words, keywords) and SudokuPad's default palette; pass reading= (an inferred reading, e.g. from
data/sudokupad/_inferred.jsonl) to reproduce a stored translation, or infer=True to search readings with the solver
(slow: several CP-SAT runs). Rules the translator cannot model raise UnsupportedPuzzle (never silently dropped).

    decode(link_or_payload, fetch=False) -> dict        fetch(short_link) -> dict (one polite request)
    translate(x, page_text=None, reading=None, infer=False) -> (engine Puzzle, info)
    to_puzzle(x, page_text=None, reading=None, infer=False, fetch=True) -> puzzle JSON dict
"""
from __future__ import annotations

import json
import re
import urllib.parse

from ._common import DecodeError, FetchError, Http, UnsupportedPuzzle, to_puzzle_json, unsupported_from_reason

API = "https://sudokupad.app/api/puzzle/"
HOSTS = re.compile(r"(?:^|\.)(?:sudokupad\.app|crackingthecryptic\.com)$", re.I)
HTTP = Http(min_gap=1.0)          # module-level client: >= 1 s between SudokuPad requests, one retry at most

# SudokuPad PuzzleZipper key abbreviations (compact -> full)
KEYS = {"ce": "cells", "re": "regions", "ca": "cages", "li": "lines", "ar": "arrows", "un": "underlays",
        "ov": "overlays", "so": "solution", "cs": "cellSize", "co": "color", "c": "color", "bc": "backgroundColor",
        "bo": "borderColor", "wd": "width", "w": "width", "hg": "height", "h": "height", "ro": "rounded",
        "tx": "text", "fs": "fontSize", "fc": "fontColor", "wa": "wayPoints", "hl": "highlight", "v": "value",
        "di": "dimensions", "ct": "center", "pv": "pencilMarks", "pe": "pencilMarks", "cl": "cellLines",
        "ta": "target", "th": "thickness", "dl": "dashLength", "sp": "settings", "ga": "gaps", "an": "angle",
        "ty": "type", "st": "style", "op": "opacity", "ff": "fontFamily",
        "o": "overlays", "a": "arrows", "u": "underlays", "l": "lines", "te": "text", "wp": "wayPoints",
        "r": "rounded", "s": "stroke", "f": "fill"}
PAYLOAD_PREFIXES = ("scl", "ctc", "fpuzzles", "fpuz")


def _lz():
    import lzstring
    return lzstring.LZString()


def compact_to_json(s):
    """SudokuPad compact JSON (unquoted keys, t/f, array elisions, bare hex colours) -> standard JSON text."""
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch in "'\"":
            q, j, buf = ch, i + 1, []
            while j < n and s[j] != q:
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j:j + 2])
                    j += 2
                    continue
                buf.append(s[j])
                j += 1
            txt = "".join(buf).replace('"', '\\"') if q == "'" else "".join(buf)
            out.append('"' + txt.replace("\\'", "'") + '"')
            i = j + 1
        elif ch == "#" and i + 1 < n and s[i + 1].isalnum():
            j = i + 1
            while j < n and s[j].isalnum():
                j += 1
            out.append('"' + s[i:j] + '"')
            i = j
        elif ch.isdigit() or (ch in "-." and i + 1 < n and s[i + 1].isdigit()):
            j = i + 1                                   # numbers; a bare token like 67f067 (hex colour) is a string
            while j < n and (s[j].isalnum() or s[j] in ".-+"):
                j += 1
            tok = s[i:j]
            out.append(tok if re.fullmatch(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", tok) else '"' + tok + '"')
            i = j
        elif ch.isalpha() or ch == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] in "_$"):
                j += 1
            word = s[i:j]
            k = j
            while k < n and s[k] == " ":
                k += 1
            if k < n and s[k] == ":":
                out.append('"' + word + '"')
            else:
                out.append({"t": "true", "f": "false", "true": "true", "false": "false", "null": "null",
                            "undefined": "null"}.get(word, '"' + word + '"'))
            i = j
        else:
            if ch in ",]":                              # JS array elisions ([,,,] / [1,,2]) -> explicit nulls
                prev = next((x for x in reversed(out) if x.strip()), "")
                if prev and prev[-1] in "[,":
                    out.append("null")
            out.append(ch)
            i += 1
    return "".join(out)


def expand(o):
    if isinstance(o, dict):
        return {KEYS.get(k, k): expand(v) for k, v in o.items()}
    if isinstance(o, list):
        return [expand(v) for v in o]
    return o


def is_sudokupad_url(s):
    if not isinstance(s, str) or "://" not in s:
        return False
    return bool(HOSTS.search(urllib.parse.urlsplit(s.strip()).netloc.split(":")[0]))


def payload_key(link):
    """Link or bare string -> the SudokuPad key: a payload ('scl...', 'fpuzzles...') or a short id."""
    s = link.strip()
    if "://" not in s:
        return urllib.parse.unquote(s) if s.startswith(PAYLOAD_PREFIXES) and "%" in s[:40] else s
    u = urllib.parse.urlsplit(s)
    q = urllib.parse.parse_qs(u.query)
    if q.get("puzzleid"):
        return q["puzzleid"][0]
    path = u.path.lstrip("/")
    for pre in ("sudoku/", "puzzle/"):
        if path.startswith(pre):
            path = path[len(pre):]
    return urllib.parse.unquote(path.rstrip("/"))


def decode_payload(payload):
    """'scl...' / 'ctc...' / 'fpuzzles...' / 'fpuz...' / JSON text -> {"format", "meta", "puzzle"} or None"""
    if payload.startswith("scl"):
        d = expand(json.loads(compact_to_json(_lz().decompressFromBase64(payload[3:]))))
        fmt = "scl"
    elif payload.startswith("fpuzzles"):
        d = json.loads(_lz().decompressFromBase64(payload[8:]))
        fmt = "fpuzzles"
    elif payload.startswith("fpuz"):
        from ._fpuz_translate import decode_fpuz
        d = decode_fpuz(payload)
        if d is None:
            return None
        fmt = "fpuzzles"
    elif payload.startswith("ctc"):
        d = expand(json.loads(compact_to_json(_lz().decompressFromBase64(payload[3:]))))
        fmt = "ctc"
    else:
        try:
            d, fmt = json.loads(payload), "json"
        except Exception:
            return None
    return {"format": fmt, "meta": _meta_of(d, fmt), "puzzle": d}


def _meta_of(d, fmt):
    meta = {}
    for cg in d.get("cages", []) if isinstance(d, dict) else []:
        v = cg.get("value") if isinstance(cg, dict) else None
        if isinstance(v, str) and re.match(r"^(title|author|rules|solution|msgcorrect)\s*:", v):
            k, _, val = v.partition(":")
            meta[k.strip()] = val.strip()
    if fmt == "fpuzzles":
        meta.setdefault("title", d.get("title"))
        meta.setdefault("author", d.get("author"))
        meta.setdefault("rules", d.get("ruleset"))
        if d.get("solution"):
            meta.setdefault("solution", "".join(str(x) for x in d["solution"]))
    return meta


def decode(link_or_payload, fetch=False):
    """Link / payload / already-decoded dict -> {"format", "meta", "puzzle"}. Short links need a request: pass
    fetch=True (or call fetch()); otherwise DecodeError."""
    x = link_or_payload
    if isinstance(x, dict):
        if "puzzle" in x and "format" in x:
            return x
        return {"format": "json", "meta": {}, "puzzle": x}
    if not isinstance(x, str) or not x.strip():
        raise DecodeError("empty SudokuPad link / payload")
    key = payload_key(x)
    if "f-puzzles.com" in x:                      # an f-puzzles link handed to the SudokuPad decoder
        from . import fpuzzles
        fp = fpuzzles.decode(x, fetch=fetch)
        return {"format": "fpuzzles", "meta": _meta_of(fp, "fpuzzles"), "puzzle": fp}
    if key.startswith(PAYLOAD_PREFIXES) or key.lstrip().startswith("{"):
        try:
            d = decode_payload(key)
        except Exception as e:  # noqa: BLE001
            raise DecodeError(f"undecodable SudokuPad payload ({type(e).__name__}: {e})") from e
        if d is None:
            raise DecodeError("undecodable SudokuPad payload")
        return d
    if re.fullmatch(r"[A-Za-z0-9_-]{4,}", key):
        if fetch:
            return globals()["fetch"](x)
        raise DecodeError(f"{x!r} is a SudokuPad short link; resolve it with sudokupad.fetch() (one request)")
    raise DecodeError(f"not a SudokuPad link or payload: {x[:80]!r}")


def fetch(short_link, http=None):
    """Resolve a short link / id through the SudokuPad API (one request, identifying User-Agent, 30 s timeout, at
    most one retry) and decode it."""
    key = payload_key(short_link)
    if key.startswith(PAYLOAD_PREFIXES):
        return decode(key)
    key = key.split("?")[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,}", key):
        raise DecodeError(f"not a SudokuPad short id: {key[:80]!r}")
    payload = (http or HTTP).get_text(API + urllib.parse.quote(key)).strip()
    if not payload:
        raise FetchError(f"empty SudokuPad API response for {key}")
    d = decode_payload(payload)
    if d is None:
        raise DecodeError(f"undecodable SudokuPad API response for {key}")
    return d


def _rules_fallback(sp, page_text):
    """Rules text for translation: the decoded meta rules + page_text (as before). New: when both are empty, the
    rules in the puzzle's own 'metadata' block (newer SudokuPad files) are used as the page text."""
    if page_text or (sp.get("meta") or {}).get("rules"):
        return page_text
    md = (sp.get("puzzle") or {}).get("metadata") if isinstance(sp.get("puzzle"), dict) else None
    return (md or {}).get("rules") if isinstance(md, dict) else None


def translate(x, page_text=None, reading=None, infer=False, fetch=True):
    """-> (engine Puzzle (not finalized), info dict). Raises UnsupportedPuzzle / DecodeError."""
    sp = decode(x, fetch=fetch)
    if sp["format"] == "fpuzzles":
        from . import fpuzzles
        return fpuzzles.translate(sp["puzzle"], rules_text=page_text, reading=reading, infer=infer)
    from . import _sp_translate as T
    text = _rules_fallback(sp, page_text)
    if infer and reading is None:
        p, info, ev = T.infer(sp, text, max_combos=60, node_limit=5_000_000)
        if p is None:
            raise unsupported_from_reason(info, "sudokupad")
        info = dict(info, _evidence=ev)
    else:
        p, info = T.translate(sp, text, reading or None)
        if p is None:
            raise unsupported_from_reason(info, "sudokupad")
    return p, info


def metadata(sp):
    """title / author / rules_text / solution of a decoded puzzle (metadata cages, then the 'metadata' block)."""
    meta = dict(sp.get("meta") or {})
    P = sp.get("puzzle") if isinstance(sp.get("puzzle"), dict) else {}
    md = P.get("metadata") if isinstance(P.get("metadata"), dict) else {}
    out = {"title": meta.get("title") or md.get("title"), "author": meta.get("author") or md.get("author"),
           "rules_text": meta.get("rules") or md.get("rules"), "solution": meta.get("solution") or md.get("solution")}
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in out.items()}


def to_puzzle(x, page_text=None, reading=None, infer=False, fetch=True, url=None):
    """SudokuPad link / payload / decoded dict -> puzzle JSON dict (pencilmark.puzzle_json format) with title, author,
    rules_text, source (link) and the embedded solution when it has one digit per cell."""
    sp = decode(x, fetch=fetch)
    p, info = translate(sp, page_text=page_text, reading=reading, infer=infer)
    md = metadata(sp)
    src = url or (x if isinstance(x, str) and "://" in x else (sp.get("url") if isinstance(sp, dict) else None))
    meta = {"title": md["title"], "author": md["author"], "rules_text": md["rules_text"] or page_text,
            "source": src, "id": (sp.get("puzzle") or {}).get("id") if isinstance(sp.get("puzzle"), dict) else None}
    sol = md["solution"]
    if sp["format"] == "fpuzzles":
        from ._fpuz_translate import solution_of
        sol = solution_of(sp["puzzle"]) or sol
    return to_puzzle_json(p, solution=sol, meta=meta)


__all__ = ["decode", "decode_payload", "fetch", "translate", "to_puzzle", "metadata", "payload_key",
           "is_sudokupad_url", "compact_to_json", "expand", "UnsupportedPuzzle"]
