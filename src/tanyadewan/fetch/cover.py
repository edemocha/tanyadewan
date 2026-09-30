"""What the first page of a sitting PDF says about itself: Bil. number and draft status."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

_BIL = re.compile(r"\bBil\.\s*(\d{1,3})\b")
# A page of debate has ~2,500+ characters; a header plus page number has ~20.
MIN_PAGE_CHARS = 200
_DRAFT = re.compile(r"naskhah\s+belum\s+disemak", re.I)


@dataclass(frozen=True)
class Cover:
    bil: int | None
    is_draft: bool
    text_page_share: float  # pages with real text / all pages. Broken copies keep only header + page number.


def read_cover(pdf: bytes) -> Cover:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:  # type: ignore[no-untyped-call]
        text = doc[0].get_text("text") if doc.page_count else ""
        with_text = sum(1 for page in doc if len(page.get_text("text").strip()) >= MIN_PAGE_CHARS)
        share = with_text / doc.page_count if doc.page_count else 0.0
    m = _BIL.search(text)
    return Cover(int(m.group(1)) if m else None, bool(_DRAFT.search(text)), round(share, 3))
