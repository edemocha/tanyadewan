"""Render frontend/src/app/icon.svg into the raster icons browsers and phones still ask for.

    uv run python scripts/make_favicon.py

Writes favicon.ico (16, 32 and 48 px, PNG-compressed entries) and apple-icon.png (180 px) next to the SVG.
PyMuPDF (already a dependency) opens the SVG, so no image library is needed.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pymupdf

APP = Path(__file__).resolve().parents[1] / "frontend" / "src" / "app"
ICO_SIZES = (16, 32, 48)
APPLE_SIZE = 180


def render(svg: Path, size: int) -> bytes:
    page = pymupdf.open(svg)[0]
    zoom = size / page.rect.width
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True).tobytes("png")


def ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        entries += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), offset + len(blobs))
        blobs += png
    return header + entries + blobs


def main() -> None:
    svg = APP / "icon.svg"
    (APP / "favicon.ico").write_bytes(ico([(s, render(svg, s)) for s in ICO_SIZES]))
    (APP / "apple-icon.png").write_bytes(render(svg, APPLE_SIZE))
    for name in ("favicon.ico", "apple-icon.png"):
        print(f"{name}: {(APP / name).stat().st_size} bytes")


if __name__ == "__main__":
    main()
