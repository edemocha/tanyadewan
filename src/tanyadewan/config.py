"""Tunables loaded from config.yaml (or the file named by TANYADEWAN_CONFIG)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class FetchConfig:
    user_agent: str
    delay_seconds: float
    timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float
    min_text_page_share: float
    repositori_base_url: str
    repositori_roots: dict[int, str]
    laman_web_base_url: str
    laman_web_tree_url: str
    laman_web_current_url: str
    laman_web_members_url: str


@dataclass(frozen=True)
class PathsConfig:
    cache_dir: Path
    pdf_dir: Path
    superseded_dir: Path
    documents: Path


@dataclass(frozen=True)
class ParseConfig:
    turns_dir: Path
    speakers: Path
    report: Path
    header_scan_lines: int
    interjection_max_chars: int
    label_max_chars: int
    heading_min_upper_ratio: float
    lang_min_stopwords: int
    lang_mixed_share: float


@dataclass(frozen=True)
class IndexConfig:
    qdrant_path: Path
    qdrant_url: str
    collection: str
    state: Path
    embedder_provider: str
    embedder_model: str
    embedder_url: str
    embedder_model_path: Path
    embedder_tokenizer_path: Path
    embedder_max_tokens: int
    embed_batch_size: int
    query_keep_alive: str
    chunk_max_chars: int
    chunk_overlap_chars: int
    chunk_min_chars: int
    migrate_from: str
    bm25_k1: float
    bm25_b: float
    bm25_avg_len: float


@dataclass(frozen=True)
class RetrieveConfig:
    mode: str  # dense | sparse | hybrid
    candidates: int
    rerank: bool
    rerank_pool: int
    translate_query: bool
    min_relevance: float
    top_k: int
    log: Path


@dataclass(frozen=True)
class RerankConfig:
    model_path: Path
    tokenizer_path: Path
    device: str  # dml | cpu
    max_tokens: int
    batch_size: int
    threads: int


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: str  # "openai_compatible" | "ollama"
    base_url: str
    model: str
    api_key_env: str  # "" for keyless free tiers
    reasoning_effort: str


@dataclass(frozen=True)
class GenerateConfig:
    providers: tuple[ProviderConfig, ...]  # tried in order
    temperature: float
    max_tokens: int
    context_chars_per_source: int
    min_quote_words: int


@dataclass(frozen=True)
class OcrConfig:
    enabled: bool
    page_min_chars: int
    dpi: int
    retry_dpis: tuple[int, ...]
    min_score: float
    cache_dir: Path


@dataclass(frozen=True)
class ApiConfig:
    host: str
    port: int


@dataclass(frozen=True)
class PhotosConfig:
    file: Path
    thumb_dir: Path
    thumb_px: int
    jpeg_quality: int


@dataclass(frozen=True)
class Config:
    fetch: FetchConfig
    paths: PathsConfig
    parse: ParseConfig
    index: IndexConfig
    retrieve: RetrieveConfig
    generate: GenerateConfig
    ocr: OcrConfig
    api: ApiConfig
    photos: PhotosConfig
    rerank: RerankConfig


def _path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def parse_config(raw: dict[str, Any]) -> Config:
    f, p = raw["fetch"], raw["paths"]
    return Config(
        fetch=FetchConfig(
            user_agent=str(f["user_agent"]),
            delay_seconds=float(f["delay_seconds"]),
            timeout_seconds=float(f["timeout_seconds"]),
            max_retries=int(f["max_retries"]),
            retry_backoff_seconds=float(f["retry_backoff_seconds"]),
            min_text_page_share=float(f.get("min_text_page_share", 0.9)),
            repositori_base_url=str(f["repositori"]["base_url"]).rstrip("/"),
            repositori_roots={int(k): str(v) for k, v in f["repositori"]["hansard_roots"].items()},
            laman_web_base_url=str(f["laman_web"]["base_url"]).rstrip("/"),
            laman_web_tree_url=str(f["laman_web"]["tree_url"]),
            laman_web_current_url=str(f["laman_web"]["current_url"]),
            laman_web_members_url=str(f["laman_web"]["members_url"]),
        ),
        paths=PathsConfig(
            cache_dir=_path(p["cache_dir"]),
            pdf_dir=_path(p["pdf_dir"]),
            superseded_dir=_path(p["superseded_dir"]),
            documents=_path(p["documents"]),
        ),
        parse=ParseConfig(
            turns_dir=_path(raw["parse"]["turns_dir"]),
            speakers=_path(raw["parse"]["speakers"]),
            report=_path(raw["parse"]["report"]),
            header_scan_lines=int(raw["parse"]["header_scan_lines"]),
            interjection_max_chars=int(raw["parse"]["interjection_max_chars"]),
            label_max_chars=int(raw["parse"]["label_max_chars"]),
            heading_min_upper_ratio=float(raw["parse"]["heading_min_upper_ratio"]),
            lang_min_stopwords=int(raw["parse"]["lang_min_stopwords"]),
            lang_mixed_share=float(raw["parse"]["lang_mixed_share"]),
        ),
        index=IndexConfig(
            qdrant_path=_path(raw["index"]["qdrant_path"]),
            qdrant_url=os.environ.get("QDRANT_URL") or str(raw["index"].get("qdrant_url") or ""),
            collection=str(raw["index"]["collection"]),
            state=_path(raw["index"]["state"]),
            embedder_provider=str(raw["index"]["embedder_provider"]),
            embedder_model=str(raw["index"]["embedder_model"]),
            embedder_url=str(raw["index"]["embedder_url"]).rstrip("/"),
            embedder_model_path=_path(
                raw["index"].get("embedder_model_path") or "models/bge-m3/model_int8.onnx"
            ),
            embedder_tokenizer_path=_path(
                raw["index"].get("embedder_tokenizer_path") or "models/bge-m3/tokenizer.json"
            ),
            embedder_max_tokens=int(raw["index"].get("embedder_max_tokens") or 512),
            embed_batch_size=int(raw["index"]["embed_batch_size"]),
            query_keep_alive=str(raw["index"].get("query_keep_alive", "")),
            chunk_max_chars=int(raw["index"]["chunk_max_chars"]),
            chunk_overlap_chars=int(raw["index"]["chunk_overlap_chars"]),
            chunk_min_chars=int(raw["index"]["chunk_min_chars"]),
            migrate_from=str(raw["index"].get("migrate_from") or ""),
            bm25_k1=float(raw["index"]["bm25_k1"]),
            bm25_b=float(raw["index"]["bm25_b"]),
            bm25_avg_len=float(raw["index"]["bm25_avg_len"]),
        ),
        retrieve=RetrieveConfig(
            mode=str(raw["retrieve"]["mode"]),
            candidates=int(raw["retrieve"]["candidates"]),
            rerank=bool(raw["retrieve"]["rerank"]),
            rerank_pool=int(raw["retrieve"]["rerank_pool"]),
            translate_query=bool(raw["retrieve"]["translate_query"]),
            min_relevance=float(raw["retrieve"]["min_relevance"]),
            top_k=int(raw["retrieve"]["top_k"]),
            log=_path(raw["retrieve"]["log"]),
        ),
        rerank=RerankConfig(
            model_path=_path(raw["rerank"]["model_path"]),
            tokenizer_path=_path(raw["rerank"]["tokenizer_path"]),
            device=str(raw["rerank"].get("device") or "cpu"),
            max_tokens=int(raw["rerank"]["max_tokens"]),
            batch_size=int(raw["rerank"]["batch_size"]),
            threads=int(raw["rerank"]["threads"]),
        ),
        generate=GenerateConfig(
            providers=tuple(
                ProviderConfig(
                    name=str(pr["name"]),
                    kind=str(pr["kind"]),
                    base_url=str(pr["base_url"]).rstrip("/"),
                    model=str(pr["model"]),
                    api_key_env=str(pr.get("api_key_env") or ""),
                    reasoning_effort=str(pr.get("reasoning_effort") or ""),
                )
                for pr in raw["generate"]["providers"]
            ),
            temperature=float(raw["generate"]["temperature"]),
            max_tokens=int(raw["generate"]["max_tokens"]),
            context_chars_per_source=int(raw["generate"]["context_chars_per_source"]),
            min_quote_words=int(raw["generate"]["min_quote_words"]),
        ),
        ocr=OcrConfig(
            enabled=bool(raw["ocr"]["enabled"]),
            page_min_chars=int(raw["ocr"]["page_min_chars"]),
            dpi=int(raw["ocr"]["dpi"]),
            retry_dpis=tuple(int(d) for d in raw["ocr"]["retry_dpis"]),
            min_score=float(raw["ocr"]["min_score"]),
            cache_dir=_path(raw["ocr"]["cache_dir"]),
        ),
        api=ApiConfig(host=str(raw["api"]["host"]), port=int(raw["api"]["port"])),
        photos=PhotosConfig(
            file=_path(raw["photos"]["file"]),
            thumb_dir=_path(raw["photos"]["thumb_dir"]),
            thumb_px=int(raw["photos"]["thumb_px"]),
            jpeg_quality=int(raw["photos"]["jpeg_quality"]),
        ),
    )


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    return {k: _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
            for k, v in {**base, **over}.items()}  # fmt: skip


@lru_cache(maxsize=1)
def load_config() -> Config:
    """config.yaml, with TANYADEWAN_OVERRIDE (a partial YAML, e.g. config.prod.yaml) merged over it."""
    path = Path(os.environ.get("TANYADEWAN_CONFIG", ROOT / "config.yaml"))
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    over = os.environ.get("TANYADEWAN_OVERRIDE")
    if over:
        with Path(over).open(encoding="utf-8") as fh:
            raw = _merge(raw, yaml.safe_load(fh) or {})
    return parse_config(raw)
