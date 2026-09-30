"""Test helpers. Nothing here is Hansard text: names are placeholders (Lorem, Ipsum, Kawasan_A)."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

FONTS = {"": "helv", "b": "hebo", "i": "heit", "bi": "hebi"}
Line = list[tuple[str, str]]  # [(text, style)], style in "", "b", "i", "bi"


def make_pdf(path: Path, pages: list[list[Line]]) -> Path:
    """A PDF whose lines carry bold/italic spans, like the Hansard layout."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page(width=595, height=842)
        y = 60.0
        for line in lines:
            x = 60.0
            for text, style in line:
                font = FONTS[style]
                page.insert_text((x, y), text, fontname=font, fontsize=11)
                x += pymupdf.get_text_length(text, fontname=font, fontsize=11)
            y += 16
    doc.save(path)
    return path


@pytest.fixture()
def pdf(tmp_path: Path):  # type: ignore[no-untyped-def]
    return lambda pages: make_pdf(tmp_path / "sitting.pdf", pages)
