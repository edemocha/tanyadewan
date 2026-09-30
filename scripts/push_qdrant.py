"""Copy the local Qdrant collection (vectors + payloads) to Qdrant Cloud. Idempotent: same ids, so re-runs update.

    QDRANT_CLOUD_URL=https://xxxx.cloud.qdrant.io:6333 QDRANT_CLOUD_API_KEY=... \
        uv run python scripts/push_qdrant.py [--limit N]

Keys come from the environment only and are never printed. Dense vectors on disk plus int8 quantisation keep
it inside the free 1 GB cluster: quantised copies stay in RAM, originals on disk.
"""

from __future__ import annotations

import argparse
import os
import sys

from qdrant_client import QdrantClient, models

from tanyadewan.config import load_config
from tanyadewan.index.store import DENSE, SPARSE, get_client

BATCH = 128


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="copy only the first N points (dry run)")
    args = ap.parse_args()
    url, key = os.environ.get("QDRANT_CLOUD_URL", ""), os.environ.get("QDRANT_CLOUD_API_KEY", "")
    if not url or not key:
        print("Set QDRANT_CLOUD_URL and QDRANT_CLOUD_API_KEY (a free cluster at cloud.qdrant.io).")
        return 1
    ic = load_config().index
    src = get_client(ic.qdrant_url, str(ic.qdrant_path))
    dst = QdrantClient(url=url, api_key=key, timeout=60)
    if not dst.collection_exists(ic.collection):
        dst.create_collection(
            ic.collection,
            vectors_config={
                DENSE: models.VectorParams(size=1024, distance=models.Distance.COSINE, on_disk=True)
            },
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, always_ram=True)
            ),
        )
        for field, schema in (
            ("sitting_day", models.PayloadSchemaType.INTEGER),
            ("speaker_id", models.PayloadSchemaType.KEYWORD),
            ("doc_id", models.PayloadSchemaType.KEYWORD),
            ("section", models.PayloadSchemaType.KEYWORD),
        ):
            dst.create_payload_index(ic.collection, field, schema)
    total = src.count(ic.collection).count
    goal = min(total, args.limit) if args.limit else total
    done, offset = 0, None
    while done < goal:
        pts, offset = src.scroll(
            ic.collection, limit=BATCH, offset=offset, with_vectors=True, with_payload=True
        )
        if not pts:
            break
        dst.upsert(
            ic.collection,
            [models.PointStruct(id=p.id, vector=p.vector or {}, payload=p.payload) for p in pts],
        )
        done += len(pts)
        print(f"\r{done}/{goal}", end="", flush=True)
        if offset is None:
            break
    print(f"\nremote count: {dst.count(ic.collection).count} (local {total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
