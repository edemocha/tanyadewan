"""Assemble the Hugging Face Space repo folder: code, config, metadata and MP thumbnails. No transcript text.

uv run python scripts/make_space_bundle.py [out_dir]      # default: deploy/space (gitignored)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "deploy" / "space"

CODE = ["src", "web"]  # web/ only because api/main.py mounts it; the public UI is the Vercel site
FILES = ["config.yaml", "config.prod.yaml"]
DATA = ["documents.jsonl", "speakers.json", "photos.json", "parties.json"]  # metadata only; turns/ (text) stays home


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for d in CODE:
        shutil.copytree(ROOT / d, OUT / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in FILES:
        shutil.copy(ROOT / f, OUT / f)
    shutil.copy(ROOT / "deploy" / "Dockerfile", OUT / "Dockerfile")
    shutil.copy(ROOT / "deploy" / "requirements.txt", OUT / "requirements.txt")
    shutil.copy(ROOT / "deploy" / "SPACE_README.md", OUT / "README.md")
    proc = OUT / "data" / "processed"
    proc.mkdir(parents=True)
    for f in DATA:
        shutil.copy(ROOT / "data" / "processed" / f, proc / f)
    shutil.copytree(ROOT / "data" / "processed" / "photos", proc / "photos")
    idx = OUT / "data" / "index"
    idx.mkdir(parents=True)
    shutil.copy(ROOT / "data" / "index" / "turns_hybrid_v1.json", idx / "turns_hybrid_v1.json")
    (OUT / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    files = [p for p in OUT.rglob("*") if p.is_file()]
    print(f"Space bundle: {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
