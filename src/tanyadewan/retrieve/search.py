"""Retrieval: dense, sparse (BM25) or hybrid (RRF of both), then optional cross-encoder reranking.

    mode "dense"   bge-m3 cosine top-k (the M2 baseline)
    mode "sparse"  BM25 keyword top-k (exact bill names, acronyms, figures)
    mode "hybrid"  both branches (retrieve.candidates each), fused by Qdrant with reciprocal rank fusion

With translate_query on, an English/mixed question also runs as its BM version (retrieve/translate.py):
every branch runs for both versions, and the reranker keeps each passage's better score.

With rerank on, the top retrieve.rerank_pool fused hits are rescored by bge-reranker-v2-m3 and the best
top_k kept. If the best reranker score is below retrieve.min_relevance the result is "not found": the
answer step then says so instead of writing an answer from weak sources (CLAUDE.md: no answer beats a
confident wrong one). Without the reranker there's no calibrated score, so only an empty result is "not found".

Filters (date range, speaker_id, section) apply inside every branch. Every query is logged with the
retrieved turn IDs, speakers and scores (CLAUDE.md), in data/logs/retrieval.jsonl.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from qdrant_client import models

from tanyadewan.config import load_config
from tanyadewan.index.embed import get_embedder
from tanyadewan.index.sparse import BM25
from tanyadewan.index.store import DENSE, SPARSE, client
from tanyadewan.retrieve.rerank import get_reranker
from tanyadewan.retrieve.translate import to_malay

MODES = ("dense", "sparse", "hybrid")


@dataclass(frozen=True)
class Filters:
    date_from: str | None = None  # "2024-01-01"
    date_to: str | None = None
    speaker_id: str | None = None
    speaker_ids: tuple[str, ...] = ()  # any of these (a party resolved to its members)
    section: str | None = None


@dataclass(frozen=True)
class Hit:
    score: float  # reranker probability when reranked, else the retrieval score (cosine / BM25 / RRF)
    payload: dict[str, Any]
    retrieval_score: float = 0.0
    rerank_score: float | None = None


@dataclass
class Result:
    hits: list[Hit]
    not_found: bool
    best_relevance: float | None  # top reranker score, None without the reranker
    mode: str
    reranked: bool
    queries: list[str] = field(default_factory=list)  # the question, plus its BM version when translated
    ms: dict[str, int] = field(default_factory=dict)


def _qdrant_filter(f: Filters) -> models.Filter | None:
    must: list[models.Condition] = []
    if f.date_from or f.date_to:
        must.append(models.FieldCondition(key="sitting_day", range=models.Range(
            gte=int(f.date_from.replace("-", "")) if f.date_from else None,
            lte=int(f.date_to.replace("-", "")) if f.date_to else None)))  # fmt: skip
    if f.speaker_id:
        must.append(models.FieldCondition(key="speaker_id", match=models.MatchValue(value=f.speaker_id)))
    if f.speaker_ids:
        must.append(models.FieldCondition(key="speaker_id", match=models.MatchAny(any=list(f.speaker_ids))))
    if f.section:
        must.append(models.FieldCondition(key="section", match=models.MatchValue(value=f.section)))
    return models.Filter(must=must) if must else None


def search(
    query: str,
    filters: Filters | None = None,
    top_k: int | None = None,
    *,
    mode: str | None = None,
    rerank: bool | None = None,
    translate: bool | None = None,
) -> Result:
    """mode / rerank / translate default to config.retrieve; the eval harness overrides them per experiment."""
    cfg = load_config()
    rc, ic = cfg.retrieve, cfg.index
    f = filters or Filters()
    k = top_k or rc.top_k
    mode = mode or rc.mode
    rerank = rc.rerank if rerank is None else rerank
    translate = rc.translate_query if translate is None else translate
    if mode not in MODES:
        raise ValueError(f"retrieve mode must be one of {MODES}, not {mode!r}")
    flt = _qdrant_filter(f)
    qc = client(ic)
    ms: dict[str, int] = {}
    t0 = time.time()

    queries = [query]
    if translate:
        tt = time.time()
        bm = to_malay(query)
        if bm:
            queries.append(bm)
        ms["translate"] = int((time.time() - tt) * 1000)

    te = time.time()
    bm25 = BM25(ic.bm25_k1, ic.bm25_b, ic.bm25_avg_len)
    sparse = (
        [v for v in (bm25.query(q) for q in queries) if v.indices] if mode in ("sparse", "hybrid") else []
    )
    dense = get_embedder(ic, for_queries=True).embed(queries) if mode in ("dense", "hybrid") else []
    ms["embed"] = int((time.time() - te) * 1000)

    pool = max(k, rc.rerank_pool) if rerank else k
    t1 = time.time()
    branches = [models.Prefetch(query=v, using=DENSE, filter=flt, limit=rc.candidates) for v in dense] + [
        models.Prefetch(query=v, using=SPARSE, filter=flt, limit=rc.candidates) for v in sparse
    ]
    if len(branches) > 1:  # hybrid, or one mode run for two query versions: reciprocal rank fusion
        res = qc.query_points(ic.collection, prefetch=branches, query=models.FusionQuery(fusion=models.Fusion.RRF),
                              limit=pool, with_payload=True)  # fmt: skip
    elif branches:
        b = branches[0]
        res = qc.query_points(
            ic.collection, query=b.query, using=b.using, query_filter=flt, limit=pool, with_payload=True
        )
    else:
        res = None
    hits = [
        Hit(float(p.score), dict(p.payload or {}), retrieval_score=float(p.score))
        for p in (res.points if res else [])
    ]
    ms["retrieve"] = int((time.time() - t1) * 1000)

    best: float | None = None
    if rerank and hits:
        t2 = time.time()
        reranker = get_reranker(cfg.rerank)
        passages = [str(h.payload.get("text") or "") for h in hits]
        per_query = [reranker.scores(q, passages) for q in queries]
        scores = [max(col) for col in zip(*per_query, strict=True)]
        hits = sorted(
            (
                Hit(s, h.payload, retrieval_score=h.retrieval_score, rerank_score=s)
                for h, s in zip(hits, scores, strict=True)
            ),
            key=lambda h: h.score,
            reverse=True,
        )
        best = hits[0].score
        ms["rerank"] = int((time.time() - t2) * 1000)
    hits = hits[:k]
    not_found = not hits or (best is not None and best < rc.min_relevance)
    ms["total"] = int((time.time() - t0) * 1000)

    rc.log.parent.mkdir(parents=True, exist_ok=True)
    with rc.log.open("a", encoding="utf-8") as log:
        log.write(json.dumps({
            "at": datetime.now(UTC).isoformat(timespec="seconds"), "query": query, "filters": f.__dict__,
            "mode": mode, "rerank": rerank, "queries": queries, "ms": ms, "not_found": not_found, "best_relevance": best,
            "hits": [{"turn_id": h.payload.get("turn_id"), "chunk_id": h.payload.get("chunk_id"),
                      "speaker_id": h.payload.get("speaker_id"), "retrieval": round(h.retrieval_score, 4),
                      "rerank": None if h.rerank_score is None else round(h.rerank_score, 4)} for h in hits],
        }, ensure_ascii=False) + "\n")  # fmt: skip
    return Result(hits, not_found, best, mode, bool(rerank), queries, ms)
