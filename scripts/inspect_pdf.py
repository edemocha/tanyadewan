"""Dump raw PyMuPDF text from Hansard PDFs, exactly as extracted (no cleaning).

    uv run python scripts/inspect_pdf.py --stats                       # page count, text per page, scanned?
    uv run python scripts/inspect_pdf.py DR1-19122022.pdf --pages 1-3  # raw text of pages 1 to 3
    uv run python scripts/inspect_pdf.py DR1-19122022.pdf --find "Tuan Yang di-Pertua"

Used before writing the parser (CLAUDE.md: inspect real PDFs first, don't assume the format).
Output stays local: Hansard text is copyrighted and is never committed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf

from tanyadewan.config import load_config


def pdf_path(name: str) -> Path:
    p = Path(name)
    return p if p.exists() else load_config().paths.pdf_dir / "parlimen15" / name


def page_range(spec: str, n: int) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), (int(b) if b else int(a)) + 1))
    return [p for p in out if 1 <= p <= n]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--pages", default="1")
    ap.add_argument("--find", help="print pages containing this text")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    files = [pdf_path(f) for f in args.files] or sorted(
        (load_config().paths.pdf_dir / "parlimen15").glob("*.pdf")
    )

    for path in files:
        doc = pymupdf.open(path)
        if args.stats:
            chars = [len(page.get_text("text")) for page in doc]
            empty = sum(1 for c in chars if c < 50)
            images = sum(1 for page in doc if page.get_images())
            print(
                f"{path.name:40} {doc.page_count:4d} pages  median {sorted(chars)[len(chars) // 2]:5d} chars/page  "
                f"{empty} near-empty pages  {images} pages with images"
            )
            continue
        pages = (
            [i + 1 for i, page in enumerate(doc) if args.find in page.get_text("text")]
            if args.find
            else page_range(args.pages, doc.page_count)
        )
        for n in pages:
            print(f"\n===== {path.name} · page {n}/{doc.page_count} =====")
            print(doc[n - 1].get_text("text"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
