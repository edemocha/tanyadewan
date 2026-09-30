"""PDF -> lines of styled text, with page furniture removed.

Observed layout (docs/parsing-notes.md):
- every page starts with a running header ("DR.14.03.2023", "DR. 2.7.2024", "DR 22.10.2025")
  and a page number (roman in the front matter, arabic in the debate), in either order
- time marks "■1040" sit on their own line
- speaker labels are bold, stage directions are italic
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from tanyadewan.config import OcrConfig
from tanyadewan.parse.ocr import cached_ocr, style_lines

HEADER = re.compile(r"^DR\.?\s?\d{1,2}\.\d{1,2}\.\d{4}$")
ARABIC = re.compile(r"^\d{1,4}$")
ROMAN = re.compile(r"^(?=[ivxlc]+$)c{0,3}(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$", re.I)
TIME_MARK = re.compile(r"^■\s?(\d{4})$")
# OCR reads the running header and page number as one line: "DR.28.02.2023 31" or "31 DR.28.02.2023".
HEADER_AND_NUMBER = re.compile(
    r"^(?:DR\.?\s?\d{1,2}\.\d{1,2}\.\d{4}\s+(\d{1,4})|(\d{1,4})\s+DR\.?\s?\d{1,2}\.\d{1,2}\.\d{4})$"
)


@dataclass(frozen=True)
class Span:
    text: str
    bold: bool
    italic: bool


@dataclass
class Line:
    page: int  # 1-based PDF page index
    spans: list[Span]
    time_mark: str | None = None  # "1040" for a "■1040" line

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class Page:
    number: int  # 1-based PDF page index
    label: str | None  # printed page number ("8", "v"), None on the cover or if not found
    lines: list[Line] = field(default_factory=list)
    ocr: bool = False  # text came from OCR, not the PDF's text layer


def debate_start(pages: list[Page]) -> int:
    """Index of the first page numbered in arabic. Everything before is front matter; everything
    from there on is debate, even a page whose number wasn't found (never drop debate pages)."""
    return next((i for i, p in enumerate(pages) if p.label and ARABIC.match(p.label)), len(pages))


def _spans(line: dict) -> list[Span]:  # type: ignore[type-arg]
    out: list[Span] = []
    for s in line["spans"]:
        text = s["text"].replace("’", "'").replace("‘", "'").replace(" ", " ")
        if not text:
            continue
        bold = bool(s["flags"] & 16) or "Bold" in s["font"]
        italic = bool(s["flags"] & 2) or "Italic" in s["font"] or "Oblique" in s["font"]
        if out and out[-1].bold == bold and out[-1].italic == italic:
            out[-1] = Span(out[-1].text + text, bold, italic)
        else:
            out.append(Span(text, bold, italic))
    return out


def extract_pages(
    path: Path, header_scan_lines: int, ocr: OcrConfig | None = None, label_max: int = 220
) -> list[Page]:
    """Pages of styled lines. With `ocr`, a page with almost no extractable text is OCR'd (see ocr.py)."""
    pages: list[Page] = []
    with pymupdf.open(path) as doc:  # type: ignore[no-untyped-call]
        for i, pdf_page in enumerate(doc, 1):
            raw: list[Line] = []
            for block in pdf_page.get_text("dict", sort=True)["blocks"]:
                for line in block.get("lines", []):
                    spans = _spans(line)
                    if spans and "".join(s.text for s in spans).strip():
                        raw.append(Line(i, spans))
            page = Page(i, None)
            if ocr and ocr.enabled and sum(len(ln.text.strip()) for ln in raw) < ocr.page_min_chars:
                ocr_lines = cached_ocr(path, i - 1, ocr)
                if sum(len(ln.text) for ln in ocr_lines) >= ocr.page_min_chars:  # really a page of text
                    styled = style_lines(ocr_lines, ocr.min_score, label_max)
                    raw = [Line(i, [Span(t, b, it) for t, b, it in row]) for row in styled if row]
                    page.ocr = True
            for n, line in enumerate(raw):
                t = line.text.strip()
                if n < header_scan_lines and HEADER.match(t):
                    continue
                if n < header_scan_lines and (hn := HEADER_AND_NUMBER.match(t)):
                    page.label = page.label or hn.group(1) or hn.group(2)
                    continue
                if n < header_scan_lines and page.label is None and (ARABIC.match(t) or ROMAN.match(t)):
                    page.label = t
                    continue
                if m := TIME_MARK.match(t):
                    line.time_mark = m.group(1)
                page.lines.append(line)
            pages.append(page)
    return pages
