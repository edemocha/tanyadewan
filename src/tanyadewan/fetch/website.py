"""Source 2: the Parliament website, www.parlimen.gov.my ("Penyata Rasmi" archive).

The archive page loads an XML tree (dhtmlxTree) node by node:

    …&ajx=0           root: one item per Parlimen, e.g. id='0_15'
    …&ajx=1&id=0_15   Penggal:   id='0_15_1' text='Penggal Pertama'
    …&id=0_15_1       Mesyuarat: text='Mesyuarat Pertama (19/12/2022 - 20/12/2022)' or 'Mesyuarat Khas…'
    …&id=0_15_1_1     sittings:  text='19 Disember 2022',
                      userdata myurl="javascript:loadResult('/files/hindex/pdf/DR-19122022.pdf', …)"

Covers the current sittings too (2025 onward), which the repository lacked.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

from tanyadewan.fetch.records import ORDINALS, DocumentRecord, parse_sitting_filename

_PDF = re.compile(r"loadResult\('(?P<path>[^']+\.pdf)'", re.I)
_PENGGAL = re.compile(r"^\s*Penggal\s+([A-Za-z]+)", re.I)
_MESYUARAT = re.compile(r"^\s*Mesyuarat\s+([A-Za-z]+)", re.I)


@dataclass(frozen=True)
class Node:
    id: str
    text: str
    url: str | None  # the PDF path for a sitting, else None


def nodes(xml_text: str) -> list[Node]:
    # The server declares iso-8859-1; ElementTree refuses a declaration on an already-decoded string.
    body = re.sub(r"^\s*<\?xml[^>]*\?>", "", xml_text)
    out = []
    for item in ET.fromstring(body).findall("item"):
        myurl = next((u.text or "" for u in item.findall("userdata") if u.get("name") == "myurl"), "")
        m = _PDF.search(myurl)
        out.append(
            Node(
                item.get("id", ""), " ".join((item.get("text") or "").split()), m.group("path") if m else None
            )
        )
    return out


def ordinal(pattern: re.Pattern[str], text: str) -> int | None:
    m = pattern.match(text)
    return ORDINALS.get(m.group(1).upper()) if m else None


def crawl(
    get: Callable[[str], str], tree_url: str, parlimen: int, base_url: str, say: Callable[[str], None]
) -> tuple[list[DocumentRecord], list[str]]:
    records: list[DocumentRecord] = []
    unparsed: list[str] = []
    for pg in nodes(get(f"{tree_url}&ajx=1&id=0_{parlimen}")):
        penggal = ordinal(_PENGGAL, pg.text)
        if penggal is None:
            unparsed.append(f"penggal?\t{pg.text}")
            continue
        say(f"  Penggal {penggal}: {pg.text}")
        for mes in nodes(get(f"{tree_url}&ajx=1&id={pg.id}")):
            number = ordinal(_MESYUARAT, mes.text)  # None for "Mesyuarat Khas" (special meeting)
            listing = f"{tree_url}&ajx=1&id={mes.id}"
            sittings = [n for n in nodes(get(listing)) if n.url]
            say(f"    Mesyuarat {number if number else 'Khas'}: {len(sittings):3d} PDFs  ({mes.text})")
            for s in sittings:
                assert s.url is not None
                filename = s.url.rsplit("/", 1)[-1]
                parsed = parse_sitting_filename(filename)
                if not parsed:
                    unparsed.append(f"{base_url}{s.url}\t{mes.text}")
                    continue
                records.append(DocumentRecord(
                    doc_id=f"DR-{parsed.sitting_date.isoformat()}", sitting_date=parsed.sitting_date.isoformat(),
                    parlimen=parlimen, penggal=penggal, mesyuarat=number, mesyuarat_title=mes.text,
                    bil=parsed.bil, source="laman_web", source_url=base_url + s.url, listing_url=listing,
                    filename=filename, filename_note=parsed.note,
                    amended_on=parsed.amended_on.isoformat() if parsed.amended_on else None,
                ))  # fmt: skip
    return records, unparsed


# The current meeting is shown on the main (non-archive) page before it reaches the archive tree:
#   <span class="boxMesyuaratTextA"><strong>Mesyuarat Khas, Penggal Kelima Parlimen Kelima Belas (2026)</strong>
#   <a href="javascript:loadResult('/files/hindex/pdf/DR-11082026.pdf','DR-11082026.pdf');">11 Ogos 2026</a>
_CURRENT_TITLE = re.compile(r'class="boxMesyuaratTextA"[^>]*>\s*(?:<strong>)?([^<]+)', re.I)
PARLIMEN_WORDS = {14: "Keempat Belas", 15: "Kelima Belas", 16: "Keenam Belas"}


def current_sittings(
    page: str, parlimen: int, url: str, base_url: str
) -> tuple[list[DocumentRecord], list[str]]:
    m = _CURRENT_TITLE.search(page)
    title = " ".join(m.group(1).split()) if m else ""
    word = PARLIMEN_WORDS.get(parlimen, "")
    if not word or f"Parlimen {word}".lower() not in title.lower():
        return [], []  # the current meeting belongs to another Parlimen (or the page changed)
    pm = re.search(r"Penggal\s+([A-Za-z]+)", title, re.I)
    penggal = ORDINALS.get(pm.group(1).upper()) if pm else None
    if penggal is None:
        return [], [f"penggal?\t{title}"]
    number = ordinal(_MESYUARAT, title)
    records, unparsed = [], []
    for path in dict.fromkeys(_PDF.findall(page)):
        filename = path.rsplit("/", 1)[-1]
        parsed = parse_sitting_filename(filename)
        if not parsed:
            unparsed.append(f"{base_url}{path}\t{title}")
            continue
        records.append(DocumentRecord(
            doc_id=f"DR-{parsed.sitting_date.isoformat()}", sitting_date=parsed.sitting_date.isoformat(),
            parlimen=parlimen, penggal=penggal, mesyuarat=number, mesyuarat_title=title, bil=parsed.bil,
            source="laman_web", source_url=base_url + path, listing_url=url, filename=filename,
            filename_note=parsed.note,
        ))  # fmt: skip
    return records, unparsed
