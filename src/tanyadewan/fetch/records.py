"""The metadata record kept for every sitting (data/processed/documents.jsonl)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path

SOURCES = ("repositori", "laman_web")  # preference order when both list a sitting

_SITTING_FILE = re.compile(
    # "DR1-19122022.pdf", "DR20-24062024" (no extension), "DR-12112024" (no Bil.), and amended
    # transcripts "DR49-09102023.PINDAAN20032025.pdf" (pindaan = amendment, dated 20 Mar 2025).
    r"^DR(?P<bil>\d{1,3})?-(?P<d>\d{2})(?P<m>\d{2})(?P<y>\d{4})"
    r"(?:\.PINDAAN(?P<ad>\d{2})(?P<am>\d{2})(?P<ay>\d{4}))?(?:\s*\(\d+\))?"
    # a free-text note after the date, kept verbatim: "DR-15102025 - BDR APRIL - DISEMAK.PM.pdf"
    r"(?P<note>\s+-\s+[^/\\]{1,60}?)?(?:\.pdf)?$",
    re.I,
)

ORDINALS = {
    "PERTAMA": 1, "KEDUA": 2, "KETIGA": 3, "KEEMPAT": 4, "KELIMA": 5,
    "KEENAM": 6, "KETUJUH": 7, "KELAPAN": 8, "KESEMBILAN": 9, "KESEPULUH": 10,
}  # fmt: skip


@dataclass(frozen=True)
class SittingFile:
    bil: int | None  # None when the file name omits it; read from the PDF cover instead
    sitting_date: date
    amended_on: date | None = None
    note: str | None = None  # free text after the date in the file name, verbatim


def parse_sitting_filename(filename: str) -> SittingFile | None:
    """'DR1-19122022.pdf' -> Bil. 1 on 2022-12-19. None if the name doesn't follow the pattern."""
    m = _SITTING_FILE.match(filename.strip())
    if not m:
        return None
    try:
        d = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        amended = date(int(m.group("ay")), int(m.group("am")), int(m.group("ad"))) if m.group("ay") else None
    except ValueError:
        return None
    note = m.group("note").strip(" -") if m.group("note") else None
    return SittingFile(int(m.group("bil")) if m.group("bil") else None, d, amended, note)


@dataclass
class DocumentRecord:
    """One sitting of the Dewan Rakyat (one PDF)."""

    doc_id: str  # "DR-2022-12-19" (one sitting per day)
    sitting_date: str  # ISO date
    parlimen: int
    penggal: int
    mesyuarat: int | None  # None for a special meeting ("Mesyuarat Khas")
    mesyuarat_title: str
    bil: int | None  # from the file name, else from the PDF cover
    source: str  # "repositori" or "laman_web"
    source_url: str  # official PDF URL; always link back to this
    listing_url: str  # the page that listed it
    filename: str
    filename_note: str | None = None  # e.g. "BDR APRIL - DISEMAK.PM", verbatim from the file name
    alternate_urls: list[str] = field(default_factory=list)  # same sitting from the other source
    amended_on: str | None = None  # ISO date, for "…PINDAAN<date>" corrected transcripts
    superseded_urls: list[str] = field(default_factory=list)  # older versions this one replaced
    previous_sha256: list[str] = field(default_factory=list)  # hashes of replaced downloads
    is_draft: bool | None = None  # cover says "Naskhah belum disemak"; None until downloaded
    text_page_share: float | None = None  # share of pages with text; low = a broken copy
    source_note: str | None = None  # why the source of record was switched, if it was
    sha256: str | None = None
    fetch_date: str | None = None
    local_path: str | None = None  # relative to the repo root
    bytes: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_records(path: Path) -> dict[str, DocumentRecord]:
    if not path.exists():
        return {}
    known = {f.name for f in fields(DocumentRecord)}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = {k: v for k, v in json.loads(line).items() if k in known}
            if "source" not in raw:  # written before the website source existed
                raw.update(source="repositori", listing_url=raw.pop("item_url", ""))
            rec = DocumentRecord(**{"listing_url": "", **raw})
            out[rec.doc_id] = rec
    return out


def save_records(path: Path, records: dict[str, DocumentRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(records.values(), key=lambda r: r.sitting_date)
    path.write_text(
        "".join(json.dumps(r.to_dict(), ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
