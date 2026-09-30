"""OCR for pages whose text can't be extracted (the Feb-Mar 2023 copies: the pages render fine, but only
the running header is extractable text).

1. Render at `dpi`, OCR with RapidOCR (line-level boxes with confidence scores).
2. Re-read every low-confidence line from a crop at each of `retry_dpis`; keep the best reading.
   (Different lines fail at different resolutions; a crop re-read recovered every label line we tested.)
3. A line still below `min_score` becomes an UNREADABLE boundary: a turn with no speaker. Text after it is
   never merged into the previous speaker's turn, so an OCR failure can't cause a misattribution.
4. OCR loses bold/italic, so styles are restored from patterns the normal segmenter relies on:
   a label ("Name [Seat]:" at the start of a line, possibly wrapped over two lines) is bold, an all-caps
   line is a bold heading, a written question's "Name [Seat]" before "minta" is bold, and bracketed text
   outside a label is an italic stage direction.
Results are cached per page, keyed by the PDF's hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pymupdf

from tanyadewan.config import OcrConfig
from tanyadewan.parse.labels import LABEL_START

UNREADABLE_LABEL = "OCR tidak dapat dibaca"
_TIME = re.compile(r"^[■▪•\-.]?\s?(\d{4})$")
_QUESTION = re.compile(r"^(.+?\])\s+(minta|meminta|bertanya)\b")
_BRACKETS = re.compile(r"\[[^\[\]]{1,150}\]")


@dataclass(frozen=True)
class OcrLine:
    text: str
    score: float
    x: float
    y: float
    h: float


@lru_cache(maxsize=1)
def _engine() -> Any:
    logging.getLogger("RapidOCR").setLevel(logging.WARNING)
    from rapidocr import RapidOCR

    return RapidOCR()


def _render(page: pymupdf.Page, dpi: int, clip: pymupdf.Rect | None = None) -> Any:
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]


def ocr_page(page: pymupdf.Page, cfg: OcrConfig) -> list[OcrLine]:
    # Options are passed on EVERY call: RapidOCR keeps the last call's options, so after a crop re-read
    # (detection off) a plain call would also skip detection and return nothing.
    res = _engine()(_render(page, cfg.dpi), use_det=True, use_cls=True, use_rec=True)
    k = 72 / cfg.dpi  # pixels -> PDF points
    out = []
    # With no text regions RapidOCR returns a different result type; boxes are a numpy array (no truthiness).
    raw_boxes = getattr(res, "boxes", None)
    boxes = [] if raw_boxes is None else list(raw_boxes)
    txts, scores = getattr(res, "txts", None) or (), getattr(res, "scores", None) or ()
    for box, text, score in zip(boxes, txts, scores, strict=False):
        xs, ys = [float(p[0]) * k for p in box], [float(p[1]) * k for p in box]
        best_text, best = str(text), float(score)
        if best < cfg.min_score:
            clip = pymupdf.Rect(min(xs) - 4, min(ys) - 3, max(xs) + 4, max(ys) + 3)  # type: ignore[no-untyped-call]
            for dpi in cfg.retry_dpis:
                r = _engine()(_render(page, dpi, clip), use_det=False, use_cls=False, use_rec=True)
                if r.txts and float(r.scores[0]) > best:
                    best_text, best = str(r.txts[0]), float(r.scores[0])
        out.append(OcrLine(best_text, round(best, 3), min(xs), min(ys), max(ys) - min(ys)))
    return merge_rows(out)


def merge_rows(lines: list[OcrLine]) -> list[OcrLine]:
    """Boxes on the same printed line (vertical centres within half a line height) become one line."""
    rows: list[list[OcrLine]] = []
    for ln in sorted(lines, key=lambda b: b.y + b.h / 2):
        if rows and abs((rows[-1][0].y + rows[-1][0].h / 2) - (ln.y + ln.h / 2)) < rows[-1][0].h / 2:
            rows[-1].append(ln)
        else:
            rows.append([ln])
    merged = []
    for row in rows:
        row.sort(key=lambda b: b.x)
        merged.append(OcrLine(" ".join(b.text for b in row), min(b.score for b in row), row[0].x, row[0].y,
                              max(b.h for b in row)))  # fmt: skip
    return merged


def looks_blank(page: pymupdf.Page) -> bool:
    """A quick low-resolution render: nothing dark on the page means there is nothing to OCR."""
    # At low resolution thin text blurs to light grey, so count anything that isn't near-white.
    pix = page.get_pixmap(dpi=40, colorspace=pymupdf.csGRAY)
    return sum(1 for v in pix.samples if v < 220) < 40


def cached_ocr(pdf: Path, page_index: int, cfg: OcrConfig) -> list[OcrLine]:
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()[:16]
    cache = (
        cfg.cache_dir / pdf.stem / f"v3-{digest}-p{page_index + 1:04d}.json"
    )  # bump v when OCR logic changes
    if cache.exists():
        return [OcrLine(**d) for d in json.loads(cache.read_text(encoding="utf-8"))]
    with pymupdf.open(pdf) as doc:  # type: ignore[no-untyped-call]
        page = doc[page_index]
        lines = [] if looks_blank(page) else ocr_page(page, cfg)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps([asdict(ln) for ln in lines], ensure_ascii=False), encoding="utf-8")
    return lines


# ── restoring styles ───────────────────────────────────────────────────────

Styled = list[tuple[str, bool, bool]]  # (text, bold, italic)


def _upper_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def _with_stage_italics(text: str) -> Styled:
    out: Styled = []
    last = 0
    for m in _BRACKETS.finditer(text):
        if m.start() > last:
            out.append((text[last : m.start()], False, False))
        out.append((m.group(), False, True))
        last = m.end()
    if last < len(text):
        out.append((text[last:], False, False))
    return out


def _label_prefix(text: str, label_max: int) -> str | None:
    """The 'Name [Seat]' part if the line opens with a speaker label ending in ':', else None."""
    colon = text.find(":")
    if colon <= 1 or colon > label_max:
        return None
    prefix = text[:colon]
    if LABEL_START.match(prefix.strip()) and prefix.count("[") == prefix.count("]"):
        return prefix
    return None


def style_lines(lines: list[OcrLine], min_score: float, label_max: int) -> list[Styled]:
    styled: list[Styled] = []
    i = 0
    while i < len(lines):
        text = lines[i].text.strip()
        nxt = lines[i + 1].text.strip() if i + 1 < len(lines) else ""
        if lines[i].score < min_score:
            styled.append([(UNREADABLE_LABEL + ":", True, False)])  # boundary: never merge across it
        elif m := _TIME.match(text):
            styled.append([("■" + m.group(1), False, False)])
        elif (prefix := _label_prefix(text, label_max)) is not None:
            styled.append([(prefix + ":", True, False), *_with_stage_italics(text[len(prefix) + 1 :])])
        elif (LABEL_START.match(text) and ":" not in text and nxt.find("]:") != -1 and nxt.find("]:") < 120
              and lines[i + 1].score >= min_score):  # fmt: skip
            # a label wrapped over two lines: bold this line and the next up to its ':'
            cut = nxt.find("]:") + 2
            styled.append([(text, True, False)])
            styled.append([(nxt[:cut], True, False), *_with_stage_italics(nxt[cut:])])
            i += 1
        elif (q := _QUESTION.match(text)) and LABEL_START.match(text):
            styled.append([(q.group(1), True, False), *_with_stage_italics(text[len(q.group(1)) :])])
        elif sum(c.isalpha() for c in text) >= 4 and ":" not in text and _upper_ratio(text) >= 0.7:
            styled.append([(text, True, False)])  # heading
        elif text.startswith("[") and text.endswith("]"):
            styled.append([(text, False, True)])
        else:
            styled.append(_with_stage_italics(text))
        i += 1
    return styled
