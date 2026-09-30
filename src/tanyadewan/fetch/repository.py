"""Source 1: the Parliament repository (DSpace), repositori.parlimen.gov.my.

Layout observed on 27 Sep 2026 (Penyata Rasmi Dewan Rakyat, Parlimen 15):

    Parlimen collection  /handle/123456789/1662  links "1. PENGGAL PERTAMA", "2. PENGGAL KEDUA", ...
      Penggal            /handle/123456789/1663  links "MESYUARAT PERTAMA (19 DISEMBER 2022 - 20 DISEMBER 2022)"
        Mesyuarat item   /handle/123456789/3432  bitstreams /bitstream/123456789/3432/1/DR1-19122022.pdf

Covers Dec 2022 to Dec 2024; the Penggal 4 collection was empty. Amended
transcripts ("…PINDAAN…") appear here.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import unquote

from tanyadewan.fetch.records import ORDINALS, DocumentRecord, parse_sitting_filename

_PENGGAL = re.compile(r"^\s*(\d+)\.\s*PENGGAL\b", re.I)
_MESYUARAT = re.compile(r"^\s*MESYUARAT\s+([A-Z]+)\b", re.I)


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def links(page: str) -> list[tuple[str, str]]:
    parser = _Links()
    parser.feed(page)
    return [(html.unescape(h), t) for h, t in parser.links]


@dataclass(frozen=True)
class Child:
    handle: str  # e.g. "123456789/1663"
    title: str
    number: int  # Penggal or Mesyuarat number


def penggal_links(page: str) -> list[Child]:
    out: dict[str, Child] = {}
    for href, text in links(page):
        m = _PENGGAL.match(text)
        if m and href.startswith("/handle/"):
            handle = href.removeprefix("/handle/")
            out[handle] = Child(handle, text, int(m.group(1)))
    return sorted(out.values(), key=lambda c: c.number)


def mesyuarat_links(page: str) -> list[Child]:
    out: dict[str, Child] = {}
    for href, text in links(page):
        m = _MESYUARAT.match(text)
        if m and href.startswith("/handle/") and m.group(1).upper() in ORDINALS:
            handle = href.removeprefix("/handle/")
            out[handle] = Child(handle, text, ORDINALS[m.group(1).upper()])
    return sorted(out.values(), key=lambda c: c.number)


@dataclass(frozen=True)
class Bitstream:
    path: str  # "/bitstream/123456789/3432/1/DR1-19122022.pdf"
    filename: str  # "DR1-19122022.pdf"


def pdf_bitstreams(page: str) -> list[Bitstream]:
    """Sitting files on an item page. Some have no .pdf extension; downloads check the %PDF header."""
    seen: dict[str, Bitstream] = {}
    for href, _ in links(page):
        name = href.split("?")[0].rsplit("/", 1)[-1]
        if href.startswith("/bitstream/") and (name.lower().endswith(".pdf") or "." not in name):
            path = href.split("?")[0]
            seen[path] = Bitstream(path, unquote(path.rsplit("/", 1)[-1]))
    return list(seen.values())


def crawl(
    get: Callable[[str], str], base_url: str, parlimen: int, root_handle: str, say: Callable[[str], None]
) -> tuple[list[DocumentRecord], list[str]]:
    """Every sitting PDF listed under one Parlimen, plus names we couldn't interpret (never guessed)."""
    records: dict[str, DocumentRecord] = {}
    unparsed: list[str] = []
    for penggal in penggal_links(get(f"{base_url}/handle/{root_handle}")):
        say(f"  Penggal {penggal.number}: {penggal.title}")
        for mes in mesyuarat_links(get(f"{base_url}/handle/{penggal.handle}")):
            item_url = f"{base_url}/handle/{mes.handle}"
            bitstreams = pdf_bitstreams(get(item_url))
            say(f"    Mesyuarat {mes.number}: {len(bitstreams):3d} PDFs  ({mes.title})")
            for bs in bitstreams:
                parsed = parse_sitting_filename(bs.filename)
                if not parsed:
                    unparsed.append(f"{base_url}{bs.path}\t{mes.title}")
                    continue
                keep_newest(records, DocumentRecord(
                    doc_id=f"DR-{parsed.sitting_date.isoformat()}", sitting_date=parsed.sitting_date.isoformat(),
                    parlimen=parlimen, penggal=penggal.number, mesyuarat=mes.number, mesyuarat_title=mes.title,
                    bil=parsed.bil, source="repositori", source_url=base_url + bs.path, listing_url=item_url,
                    filename=bs.filename, filename_note=parsed.note,
                    amended_on=parsed.amended_on.isoformat() if parsed.amended_on else None,
                ))  # fmt: skip
    return list(records.values()), unparsed


def keep_newest(records: dict[str, DocumentRecord], rec: DocumentRecord) -> None:
    """One record per sitting: an amended transcript replaces the original, whose URL is kept."""
    old = records.get(rec.doc_id)
    if old is None:
        records[rec.doc_id] = rec
        return
    newer, older = (rec, old) if (rec.amended_on or "") > (old.amended_on or "") else (old, rec)
    newer.superseded_urls = sorted({*newer.superseded_urls, *older.superseded_urls, older.source_url})
    records[rec.doc_id] = newer
