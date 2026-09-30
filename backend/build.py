"""Build step for the backend service (Vercel runs it with this folder as the working directory).

Assembles, next to this file, the layout the code expects (config.py finds config.yaml two levels above the package):

    src/tanyadewan/        copy of ../src/tanyadewan
    config.yaml, config.prod.yaml
    data/processed/        speakers.json, parties.json, documents.jsonl   from seed/
    data/index/            turns_hybrid_v1.json                           from seed/
    models/                the four CPU model files (about 1.2 GB)

Everything above is generated and gitignored. Models are hard-linked or copied from ../models when they exist
(a local run) and downloaded otherwise (Vercel). Run locally with: python backend/build.py
"""

from __future__ import annotations

import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

HF = "https://huggingface.co"
MODELS = {
    "models/bge-m3/model_int8.onnx": f"{HF}/Xenova/bge-m3/resolve/main/onnx/model_int8.onnx",
    "models/bge-m3/tokenizer.json": f"{HF}/Xenova/bge-m3/resolve/main/tokenizer.json",
    "models/bge-reranker-v2-m3/model_int8.onnx": f"{HF}/onnx-community/bge-reranker-v2-m3-ONNX/resolve/main/onnx/model_int8.onnx",
    "models/bge-reranker-v2-m3/tokenizer.json": f"{HF}/onnx-community/bge-reranker-v2-m3-ONNX/resolve/main/tokenizer.json",
}
SEED = {
    "seed/speakers.json": "data/processed/speakers.json",
    "seed/parties.json": "data/processed/parties.json",
    "seed/documents.jsonl": "data/processed/documents.jsonl",
    "seed/index_state.json": "data/index/turns_hybrid_v1.json",
}
CHUNK = 1 << 20
ATTEMPTS = 3


def fail(msg: str) -> None:
    print(f"build.py: {msg}", file=sys.stderr)
    raise SystemExit(1)


def assemble() -> None:
    src = REPO / "src" / "tanyadewan"
    if not src.is_dir():
        fail(f"{src} not found: the build needs the repository checkout, not only backend/")
    dst = HERE / "src" / "tanyadewan"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("config.yaml", "config.prod.yaml"):
        shutil.copy(REPO / name, HERE / name)
    for seed, dest in SEED.items():
        if not (HERE / seed).is_file():
            fail(f"{seed} is missing: run scripts/export_public_seed.py and commit backend/seed/")
        (HERE / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / seed, HERE / dest)
    print("assembled src/, config and seed data")


def download(url: str, dest: Path) -> None:
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        part = dest.with_suffix(dest.suffix + ".part")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TanyaDewan-build/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp, part.open("wb") as out:
                expected = int(resp.headers.get("Content-Length") or 0)
                done = 0
                while chunk := resp.read(CHUNK):
                    out.write(chunk)
                    done += len(chunk)
            if expected and done != expected:
                raise OSError(f"got {done} of {expected} bytes")
            part.replace(dest)
            return
        except OSError as e:
            last = e
            print(f"  attempt {attempt}/{ATTEMPTS} failed for {dest.name}: {e}")
            time.sleep(5 * attempt)
    fail(f"could not download {url}: {last}")


def fetch_models() -> None:
    for rel, url in MODELS.items():
        dest = HERE / rel
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        local = REPO / rel
        if local.is_file():
            try:
                os.link(local, dest)  # same volume: no extra disk
            except OSError:
                shutil.copy(local, dest)
            print(f"models: reused {rel}")
        else:
            t0 = time.time()
            download(url, dest)
            print(f"models: downloaded {rel} ({dest.stat().st_size / 1e6:.0f} MB, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    assemble()
    fetch_models()
    print("backend build done")
