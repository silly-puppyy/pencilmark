"""Shared pieces of pencilmark.sources: exception types, a polite HTTP client, Puzzle -> puzzle JSON."""

from __future__ import annotations

import functools
import gzip
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

# Identify the client. Override with the PENCILMARK_UA environment variable (e.g. to add a contact address).
USER_AGENT = os.environ.get(
    "PENCILMARK_UA",
    "pencilmark-sources/1.0 (puzzle importer for a sudoku difficulty grader; python-urllib; "
    "contact 347531506+silly-puppyy@users.noreply.github.com)",
)
TIMEOUT = 30.0

_log = logging.getLogger(__name__)


from ..errors import Error, FetchError, FormatError, NotSupportedError, ReadingMismatch, unsupported  # noqa: E402,F401


def reads(source):
    """decorator for a reader: a crash on malformed data (a missing key, a value of the wrong type, a short list) becomes a
    FormatError naming the source and the problem"""

    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (TypeError, AttributeError, KeyError, IndexError) as e:
                raise FormatError(f"malformed {source} data ({type(e).__name__}: {e})") from e

        return inner

    return wrap


def unsupported_from_reason(reason, source=""):
    """Translator failure reason ('unsupported: a, b' or a plain reason) -> NotSupportedError."""
    r = str(reason)
    if r.startswith("unsupported: "):
        return unsupported([x.strip() for x in r[len("unsupported: ") :].split(", ") if x.strip()], source)
    return unsupported([r], source)


def _read_summary(source, info):
    """log what a reader read: the element counts of its info (internal keys, starting with _, left out)"""
    if isinstance(info, dict):
        parts = [k if v is True else f"{k} {v}" for k, v in info.items() if not k.startswith("_") and v]
        _log.info("%s: read %s", source, ", ".join(parts) or "givens only")


class Http:
    """Sequential, polite HTTP: identifying User-Agent, timeouts, a minimum gap between requests to the same host,
    optional robots.txt checks, at most one retry (after a pause) on 429 / 5xx / network errors."""

    def __init__(self, min_gap=1.0, respect_robots=False, retries=1, user_agent=None, timeout=TIMEOUT):
        self.min_gap, self.respect_robots, self.retries = float(min_gap), respect_robots, int(retries)
        self.user_agent, self.timeout = user_agent or USER_AGENT, timeout
        self._last, self._robots, self._lock = {}, {}, threading.Lock()
        self.requests = 0  # live requests made (incl. robots.txt)

    def _pace(self, host):
        with self._lock:
            dt = time.time() - self._last.get(host, 0.0)
            if dt < self.min_gap:
                time.sleep(self.min_gap - dt)
            self._last[host] = time.time()

    def allowed(self, url):
        if not self.respect_robots:
            return True
        u = urllib.parse.urlsplit(url)
        base = f"{u.scheme}://{u.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(
                    self._raw(base + "/robots.txt", method="GET", check=False).decode("utf-8", "replace").splitlines()
                )
            except FetchError as e:  # robots.txt unreachable: be conservative only on 401/403
                rp.parse(
                    ["User-agent: *", "Disallow: /"]
                    if "HTTP 40" in str(e) and ("401" in str(e) or "403" in str(e))
                    else []
                )
            self._robots[base] = rp
        return self._robots[base].can_fetch(self.user_agent, url)

    def _raw(self, url, method="GET", check=True, follow=True):
        if check and not self.allowed(url):
            raise FetchError(f"robots.txt disallows {url}")
        host = urllib.parse.urlsplit(url).netloc
        last = None
        for attempt in range(self.retries + 1):
            self._pace(host)
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip"}
            )
            try:
                self.requests += 1
                _log.info("%s %s", method, url)
                opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
                with opener.open(req, timeout=self.timeout) as r:
                    if method == "HEAD":
                        return r.headers
                    data = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        data = gzip.decompress(data)
                    return data
            except urllib.error.HTTPError as e:
                if not follow and e.code in (301, 302, 303, 307, 308):
                    return e.headers
                last = f"HTTP {e.code} for {url}"
                if e.code not in (429, 500, 502, 503, 504):
                    break
                if attempt < self.retries:
                    _log.warning("%s; retrying", last)
                time.sleep(min(30.0, 10.0 * (attempt + 1)))
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = f"{type(e).__name__} for {url}: {e}"
                if attempt < self.retries:
                    _log.warning("%s; retrying", last)
                time.sleep(5.0)
        raise FetchError(last)

    def get_text(self, url):
        return self._raw(url).decode("utf-8", errors="replace")

    def redirect_target(self, url):
        """Location header of a redirecting URL (HEAD, not followed) -- resolves TinyURL-style short links."""
        h = self._raw(url, method="HEAD", follow=False)
        return h.get("Location") or h.get("location")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def to_puzzle_json(p, solution=None, meta=None):
    """engine Puzzle (finalized or not) -> puzzle JSON dict (pencilmark.puzzle_json.to_json); a solution string / list is
    attached only when it has one digit per cell."""
    from ..puzzle_json import to_json

    sol = None
    if isinstance(solution, int) and not isinstance(solution, bool):  # all digits: some files store it as a number
        solution = str(solution)
    if solution is not None:
        s = (
            [int(x) for x in solution]
            if not isinstance(solution, str)
            else ([int(ch) for ch in solution] if solution.isdigit() else None)
        )
        if s is not None and len(s) == p.N and all(1 <= v <= p.D for v in s):
            sol = s
    return to_json(p, solution=sol, meta={k: v for k, v in (meta or {}).items() if v not in (None, "")})
