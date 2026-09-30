"""Embed speaker turns into Qdrant. Newest sittings first; resumable (safe to stop and re-run).

    uv run python -m tanyadewan.index                   # everything not yet indexed
    uv run python -m tanyadewan.index --limit-docs 10   # the 10 newest not yet indexed
    uv run python -m tanyadewan.index --metadata-only   # refresh payloads of indexed sittings; embed nothing
    uv run python -m tanyadewan.index --rebuild         # drop the collection and start again
    uv run python -m tanyadewan.index --migrate         # copy dense vectors from index.migrate_from, add BM25

A sitting is re-indexed when its turns file changed (e.g. after a re-parse).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from qdrant_client import models

from tanyadewan.chunk.turns import Chunk, chunk_turn
from tanyadewan.config import Config, load_config
from tanyadewan.index.embed import get_embedder
from tanyadewan.index.sparse import BM25
from tanyadewan.index.store import DENSE, SPARSE, client, ensure_collection, point_id


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit-docs", type=int, default=0)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--metadata-only", action="store_true", help="only refresh payloads of indexed sittings")
    ap.add_argument(
        "--migrate", action="store_true", help="copy already-embedded sittings from index.migrate_from"
    )
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    cfg = load_config()
    ic = cfg.index
    embedder = get_embedder(ic)
    qc = client(ic)
    state: dict[str, Any] = json.loads(ic.state.read_text(encoding="utf-8")) if ic.state.exists() else {}
    if args.rebuild and qc.collection_exists(ic.collection):
        qc.delete_collection(ic.collection)
        state = {}
    bm25 = BM25(ic.bm25_k1, ic.bm25_b, ic.bm25_avg_len)
    if args.migrate:
        return migrate(cfg, bm25)
    if not qc.collection_exists(ic.collection):  # only then load the model to learn the vector size
        ensure_collection(ic, len(embedder.embed(["uji"])[0]))

    files = sorted(cfg.parse.turns_dir.glob("*.jsonl"), reverse=True)  # newest first
    try:  # points actually in Qdrant per sitting: the state file alone can claim sittings that have none
        held = {str(h.value): h.count for h in qc.facet(ic.collection, key="doc_id", limit=5000).hits}
    except Exception:  # embedded Qdrant has no facet: trust the state file
        held = None
    drifted: list[str] = []
    plans = []
    for f in files:
        chunks = load_chunks(f, cfg)
        text_d, meta_d = digests(chunks)
        old = state.get(f.stem)
        if old is not None and held is not None and held.get(f.stem, 0) != len(chunks):
            drifted.append(f.stem)  # marked indexed, but its points are missing or partial: embed it again
            old = state[f.stem] = None
        if isinstance(old, str):  # written before text/metadata were tracked separately
            old = {"text": text_d, "meta": ""} if old == file_digest(f) else None
            state[f.stem] = old
        if old is None or old.get("text") != text_d:
            plans.append((f, chunks, text_d, meta_d, "embed"))
        elif old.get("meta") != meta_d:
            plans.append((f, chunks, text_d, meta_d, "metadata"))
    state = {k: v for k, v in state.items() if v is not None}
    embeds = [p for p in plans if p[4] == "embed"]
    if drifted:
        print(f"WARNING: {len(drifted)} sittings were marked indexed but their points are missing or partial: {drifted}")
    if args.metadata_only:
        stale = [p[0].stem for p in embeds if p[0].stem in state]
        if stale:
            print(f"WARNING: {len(stale)} indexed sittings have changed text and need embedding: {stale[:5]}")
        plans = [p for p in plans if p[4] == "metadata"]
    if args.limit_docs:
        plans = [p for p in plans if p[4] == "metadata"] + embeds[: args.limit_docs]
    print(f"{len(embeds)} sittings to embed with {embedder.name}, "
          f"{sum(p[4] == 'metadata' for p in plans)} with metadata-only changes. The kettle is on.")  # fmt: skip

    for n, (f, chunks, text_d, meta_d, action) in enumerate(plans, 1):
        t0 = time.time()
        if action == "metadata":  # same text and chunks: update payloads, no re-embedding
            ops: list[models.UpdateOperation] = [
                models.SetPayloadOperation(set_payload=models.SetPayload(
                    payload={**c.payload, "chunk_id": c.chunk_id}, points=[point_id(c.chunk_id)]))
                for c in chunks
            ]  # fmt: skip
            for i in range(0, len(ops), 256):
                qc.batch_update_points(ic.collection, update_operations=ops[i : i + 256])
        else:
            # replace whatever this sitting had before (turn IDs can shift after a re-parse)
            qc.delete(ic.collection, points_selector=models.FilterSelector(filter=models.Filter(
                must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=f.stem))])))  # fmt: skip
            for i in range(0, len(chunks), ic.embed_batch_size):
                batch = chunks[i : i + ic.embed_batch_size]
                vectors = embedder.embed([c.text for c in batch])
                qc.upsert(ic.collection, points=[
                    models.PointStruct(id=point_id(c.chunk_id), vector={DENSE: v, SPARSE: bm25.document(c.text)},
                                       payload={**c.payload, "chunk_id": c.chunk_id})
                    for c, v in zip(batch, vectors, strict=True)])  # fmt: skip
        state[f.stem] = {"text": text_d, "meta": meta_d}
        ic.state.parent.mkdir(parents=True, exist_ok=True)
        ic.state.write_text(json.dumps(state, indent=0), encoding="utf-8")
        print(f"  [{n}/{len(plans)}] {f.stem}: {len(chunks)} chunks, {action}, {time.time() - t0:.0f}s")
    print(f"Done. {len(state)} sittings searchable.")
    qc.close()
    return 0


def migrate(cfg: Config, bm25: BM25) -> int:
    """Copy every point of the dense-only collection into the hybrid one: same id, same payload, same dense
    vector (no re-embedding), plus a BM25 vector from the stored chunk text. The old state file carries over."""
    ic = cfg.index
    qc = client(ic)
    src = ic.migrate_from
    if not src or not qc.collection_exists(src):
        print(f"Nothing to migrate: collection {src!r} not found.")
        return 1
    info = qc.get_collection(src)
    vectors = info.config.params.vectors
    dim = vectors.size if isinstance(vectors, models.VectorParams) else next(iter(vectors.values())).size  # type: ignore[union-attr]
    ensure_collection(ic, dim)
    copied, offset = 0, None
    while True:
        points, offset = qc.scroll(src, limit=256, offset=offset, with_payload=True, with_vectors=True)
        if points:
            qc.upsert(ic.collection, points=[
                models.PointStruct(id=p.id, payload=p.payload,
                                   vector={DENSE: p.vector, SPARSE: bm25.document(str((p.payload or {}).get("text", "")))})  # type: ignore[dict-item]
                for p in points])  # fmt: skip
            copied += len(points)
            print(f"  copied {copied} points", end="\r")
        if offset is None:
            break
    old_state = ic.state.parent / "indexed.json"
    if old_state.exists() and not ic.state.exists():
        ic.state.write_text(old_state.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"\nMigrated {copied} points from {src} to {ic.collection} (dense copied, BM25 added).")
    return 0


def load_chunks(f: Path, cfg: Config) -> list[Chunk]:
    ic = cfg.index
    turns = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [
        c
        for t in turns
        for c in chunk_turn(t, ic.chunk_max_chars, ic.chunk_overlap_chars, ic.chunk_min_chars)
    ]


def digests(chunks: list[Chunk]) -> tuple[str, str]:
    """(what gets embedded, everything stored with it). Only a text change needs re-embedding."""
    text = hashlib.sha256("\n".join(f"{c.chunk_id}\t{c.text}" for c in chunks).encode()).hexdigest()[:16]
    meta = hashlib.sha256(json.dumps([c.payload for c in chunks], sort_keys=True).encode()).hexdigest()[:16]
    return text, meta


def file_digest(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16]


if __name__ == "__main__":
    raise SystemExit(main())
