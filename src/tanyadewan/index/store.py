"""The Qdrant collection: embedded (local folder) by default, or a server if qdrant_url is set.

Each point has two named vectors: "dense" (the embedder) and sparse "bm25" (keyword), for hybrid search.
"""

from __future__ import annotations

import os
import uuid
from functools import lru_cache

from qdrant_client import QdrantClient, models

from tanyadewan.config import IndexConfig

_NAMESPACE = uuid.UUID("2f6a1c1e-5b1d-4d0e-9b8e-7a5c3d1e0f42")


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


@lru_cache(maxsize=2)
def get_client(qdrant_url: str, qdrant_path: str) -> QdrantClient:
    if qdrant_url:
        return QdrantClient(url=qdrant_url, api_key=os.environ.get("QDRANT_API_KEY") or None, timeout=30)
    return QdrantClient(path=qdrant_path)


def client(cfg: IndexConfig) -> QdrantClient:
    cfg.qdrant_path.mkdir(parents=True, exist_ok=True)
    return get_client(cfg.qdrant_url, str(cfg.qdrant_path))


DENSE = "dense"  # bge-m3 (or whichever embedder the config names)
SPARSE = "bm25"  # index/sparse.py; Qdrant applies IDF at query time


def ensure_collection(cfg: IndexConfig, dim: int) -> None:
    qc = client(cfg)
    if not qc.collection_exists(cfg.collection):
        qc.create_collection(
            cfg.collection,
            vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        for field, schema in (("sitting_day", models.PayloadSchemaType.INTEGER),
                              ("speaker_id", models.PayloadSchemaType.KEYWORD),
                              ("doc_id", models.PayloadSchemaType.KEYWORD),
                              ("section", models.PayloadSchemaType.KEYWORD)):  # fmt: skip
            qc.create_payload_index(cfg.collection, field, schema)
