"""Merging the two sources into one record per sitting, downloading, and re-checking drafts.

Rules:
- One record per sitting date. Where both sources list it, "repositori" is the source of record and
  the website URL is kept in alternate_urls.
- If a sitting's source URL changes (an amended transcript appears, or the repository publishes a
  sitting we had from the website), the old URL goes to superseded_urls and the new file is
  downloaded. If its content hash is unchanged, nothing else changes.
- Drafts ("Naskhah belum disemak") are indexed with is_draft=True. --recheck-drafts downloads them
  again; if the content changed, the old file moves to superseded/ and its hash is kept.
- Nothing is ever deleted: a sitting that disappears from the listings keeps its record.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date
from pathlib import Path

from tanyadewan.fetch.client import save_atomic, sha256
from tanyadewan.fetch.cover import read_cover
from tanyadewan.fetch.records import SOURCES, DocumentRecord

log = logging.getLogger("tanyadewan.fetch")

_DOWNLOAD_FIELDS = ("is_draft", "text_page_share", "sha256", "fetch_date", "local_path", "bytes")


def combine_sources(listed: Iterable[DocumentRecord]) -> dict[str, DocumentRecord]:
    """One record per sitting, preferring the source listed first in SOURCES."""
    by_id: dict[str, list[DocumentRecord]] = {}
    for r in listed:
        by_id.setdefault(r.doc_id, []).append(r)
    out = {}
    for doc_id, recs in by_id.items():
        recs.sort(key=lambda r: SOURCES.index(r.source))
        best = recs[0]
        others = {r.source_url for r in recs[1:]} | {u for r in recs for u in r.alternate_urls}
        best.alternate_urls = sorted(others - {best.source_url})
        out[doc_id] = best
    return out


def merge(
    existing: dict[str, DocumentRecord], listed: dict[str, DocumentRecord]
) -> dict[str, DocumentRecord]:
    merged = dict(existing)
    for doc_id, new in listed.items():
        old = existing.get(doc_id)
        if old is None:
            merged[doc_id] = new
            continue
        new.superseded_urls = sorted({*old.superseded_urls, *new.superseded_urls})
        new.previous_sha256 = list(old.previous_sha256)
        if new.bil is None:
            new.bil = old.bil  # read from the cover earlier
        if old.source_note and old.source_url in new.alternate_urls:
            # We switched away from a broken copy earlier: keep that choice on later crawls.
            new.alternate_urls = sorted((set(new.alternate_urls) - {old.source_url}) | {new.source_url})
            new.source_url, new.source, new.filename = old.source_url, old.source, old.filename
            new.source_note = old.source_note
        if old.source_url == new.source_url:
            for f in _DOWNLOAD_FIELDS:
                setattr(new, f, getattr(old, f))
        else:
            # A new version (or the preferred source now has it): download again and compare hashes.
            new.superseded_urls = sorted({*new.superseded_urls, old.source_url} - {new.source_url})
            new.sha256 = old.sha256  # kept only to detect "same content, new URL"
            new.local_path = old.local_path
        merged[doc_id] = new
    return merged


def needs_download(r: DocumentRecord, root: Path) -> bool:
    return r.fetch_date is None or not r.local_path or not (root / r.local_path).exists()


def download(
    r: DocumentRecord,
    get_pdf: Callable[[str], bytes],
    pdf_dir: Path,
    superseded_dir: Path,
    root: Path,
    today: date,
) -> str:
    """Fetch r.source_url into pdf_dir; returns 'new', 'unchanged' or 'revised'."""
    data = get_pdf(r.source_url)
    digest = sha256(data)
    dest = pdf_dir / f"parlimen{r.parlimen}" / f"{r.doc_id}.pdf"
    status = "new"
    if r.sha256 and r.local_path and (root / r.local_path).exists():
        if digest == r.sha256:
            status = "unchanged"
        else:
            status = "revised"
            old = root / r.local_path
            keep = superseded_dir / f"{r.doc_id}.{r.sha256[:12]}.pdf"
            keep.parent.mkdir(parents=True, exist_ok=True)
            old.replace(keep)
            r.previous_sha256 = [*r.previous_sha256, r.sha256]
    if status != "unchanged":
        save_atomic(data, dest)
        r.local_path = dest.relative_to(root).as_posix()
        r.bytes = len(data)
        r.sha256 = digest
    cover = read_cover(data)
    r.is_draft = cover.is_draft
    r.text_page_share = cover.text_page_share
    if r.bil is None:
        r.bil = cover.bil
    r.fetch_date = today.isoformat()
    return status


def source_name(url: str) -> str:
    return "repositori" if "repositori.parlimen.gov.my" in url else "laman_web"


def repair_incomplete(
    r: DocumentRecord,
    get_pdf: Callable[[str], bytes],
    pdf_dir: Path,
    superseded_dir: Path,
    root: Path,
    today: date,
    min_share: float,
) -> str | None:
    """A copy with too many empty pages (seen: repository PDFs of Feb-Mar 2023 whose pages have no
    content at all) is replaced by the other source's copy when that one is more complete.
    Returns a note describing the switch, or None if nothing changed."""
    if r.text_page_share is None or r.text_page_share >= min_share or not r.alternate_urls:
        return None
    best_share, best_url, best_data = r.text_page_share, "", b""
    for url in r.alternate_urls:
        data = get_pdf(url)
        share = read_cover(data).text_page_share
        if share > best_share:
            best_share, best_url, best_data = share, url, data
    if not best_url:
        return None
    note = (f"switched on {today.isoformat()}: {r.source_url} has text on {r.text_page_share:.0%} of pages, "
            f"{best_url} on {best_share:.0%}")  # fmt: skip
    r.alternate_urls = sorted((set(r.alternate_urls) - {best_url}) | {r.source_url})
    r.source_url, r.source, r.filename = best_url, source_name(best_url), best_url.rsplit("/", 1)[-1]
    r.fetch_date = None  # force download() to store it as a new version
    r.sha256 = r.sha256 or ""
    status = download(r, lambda _: best_data, pdf_dir, superseded_dir, root, today)
    r.source_note = note
    log.info("%s: %s (%s)", r.doc_id, note, status)
    return note


def pick_sample(records: Iterable[DocumentRecord], per_year: int) -> list[DocumentRecord]:
    """per_year sittings from each calendar year, spread evenly across that year."""
    by_year: dict[str, list[DocumentRecord]] = {}
    for r in sorted(records, key=lambda r: r.sitting_date):
        by_year.setdefault(r.sitting_date[:4], []).append(r)
    picked = []
    for rows in by_year.values():
        step = max(len(rows) / per_year, 1)
        picked += [rows[int(i * step)] for i in range(min(per_year, len(rows)))]
    return picked


def copy(r: DocumentRecord) -> DocumentRecord:
    return replace(r, alternate_urls=list(r.alternate_urls), superseded_urls=list(r.superseded_urls),
                   previous_sha256=list(r.previous_sha256))  # fmt: skip
