"""An HTTP client that is polite by construction.

- obeys robots.txt, per host (a host with no robots.txt allows everything, by convention)
- waits at least `delay_seconds` between any two requests, to any host
- caches every listing page on disk, so re-runs cost the servers nothing
- never re-downloads a PDF that is already on disk (unless asked to re-check it)
- retries transient failures with a growing back-off
- sends a descriptive User-Agent with no personal contact details
"""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import quote, urlsplit

from tanyadewan.config import FetchConfig

log = logging.getLogger("tanyadewan.fetch")


class FetchError(RuntimeError):
    pass


class PoliteClient:
    def __init__(self, cfg: FetchConfig, cache_dir: Path) -> None:
        self.cfg = cfg
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.requests_made = 0

    # ── politeness ─────────────────────────────────────────────────────────
    def _wait_turn(self) -> None:
        gap = time.monotonic() - self._last_request
        if gap < self.cfg.delay_seconds:
            time.sleep(self.cfg.delay_seconds - gap)
        self._last_request = time.monotonic()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                body = self._request(f"{host}/robots.txt", check_robots=False)
                rp.parse(body.decode("utf-8", errors="replace").splitlines())
            except FetchError as e:
                if "HTTP 404" not in str(e):
                    raise
                rp.parse([])  # no robots.txt: nothing is disallowed
            self._robots[host] = rp
        return self._robots[host].can_fetch(self.cfg.user_agent, url)

    def _request(self, url: str, *, check_robots: bool = True) -> bytes:
        if check_robots and not self._allowed(url):
            raise FetchError(f"robots.txt disallows {url}")
        # Some file names contain spaces ("DR-15102025 - BDR APRIL - DISEMAK.PM.pdf"); urllib needs them escaped.
        req = urllib.request.Request(quote(url, safe=":/?&=%#~"), headers={"User-Agent": self.cfg.user_agent})
        err: Exception | None = None
        for attempt in range(1, self.cfg.max_retries + 1):
            self._wait_turn()
            self.requests_made += 1
            try:
                with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds) as resp:
                    data: bytes = resp.read()
                    return data
            except urllib.error.HTTPError as e:
                if e.code < 500 and e.code != 429:
                    raise FetchError(f"HTTP {e.code} for {url}") from e
                err = e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                err = e
            wait = self.cfg.retry_backoff_seconds * attempt
            log.warning("attempt %d for %s failed (%s); waiting %.0fs", attempt, url, err, wait)
            time.sleep(wait)
        raise FetchError(f"giving up on {url} after {self.cfg.max_retries} attempts: {err}")

    # ── public ──────────────────────────────────────────────────────────────
    def get_text(self, url: str, *, refresh: bool = False, encoding: str = "utf-8") -> str:
        """A listing page (HTML or XML), from the disk cache unless refresh=True."""
        cached = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".txt")
        if cached.exists() and not refresh:
            return cached.read_text(encoding="utf-8")
        text = self._request(url).decode(encoding, errors="replace")
        cached.write_text(text, encoding="utf-8")
        return text

    def get_image(self, url: str) -> bytes:
        data = self._request(url)
        if not data.startswith((b"\xff\xd8", b"\x89PNG")):
            raise FetchError(f"{url} did not return a JPEG or PNG")
        return data

    def get_pdf(self, url: str) -> bytes:
        data = self._request(url)
        if not data.startswith(b"%PDF"):
            raise FetchError(f"{url} did not return a PDF")
        return data


def save_atomic(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
