"""Embedders behind one interface, so other models can be benchmarked (M4 experiment 6).

Baseline: BAAI/bge-m3 served by a local Ollama (dense vectors, 1024 dimensions, multilingual incl. BM).
"""

from __future__ import annotations

import json
import threading
import urllib.request
from functools import lru_cache
from typing import Protocol

from tanyadewan.config import IndexConfig


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    def __init__(self, url: str, model: str, timeout: float = 600, keep_alive: str = "") -> None:
        self.url, self.model, self.timeout, self.keep_alive = url, model, timeout, keep_alive
        self.name = f"ollama/{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, object] = {"model": self.model, "input": texts, "truncate": True}
        if self.keep_alive:  # "0" = unload as soon as this request is done
            payload["keep_alive"] = self.keep_alive
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.url}/api/embed", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            vectors: list[list[float]] = json.load(resp)["embeddings"]
        return vectors


class OnnxEmbedder:
    """bge-m3 dense vectors (CLS token, L2-normalised) from an ONNX export on CPU: no Ollama needed to serve."""

    def __init__(self, cfg: IndexConfig) -> None:
        import numpy as np  # local imports: indexing on Ollama shouldn't need them loaded
        import onnxruntime as ort
        from tokenizers import Tokenizer

        if not cfg.embedder_model_path.exists():
            raise FileNotFoundError(f"embedder model missing: {cfg.embedder_model_path}. See README.")
        self._np = np
        self.session = ort.InferenceSession(str(cfg.embedder_model_path), providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(cfg.embedder_tokenizer_path))
        self.tokenizer.enable_truncation(max_length=cfg.embedder_max_tokens)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>") or 1, pad_token="<pad>")
        self.batch_size = cfg.embed_batch_size
        self.name = f"onnx/{cfg.embedder_model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        np = self._np
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            enc = self.tokenizer.encode_batch(texts[i : i + self.batch_size])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            (hidden,) = self.session.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask})
            cls = hidden[:, 0, :]
            cls = cls / np.linalg.norm(cls, axis=1, keepdims=True)
            out.extend(cls.astype(float).tolist())
        return out


@lru_cache(maxsize=1)
def _build_onnx(cfg: IndexConfig) -> OnnxEmbedder:
    return OnnxEmbedder(cfg)


_build_lock = threading.Lock()


def _onnx(cfg: IndexConfig) -> OnnxEmbedder:
    with _build_lock:  # parallel first requests must not each load the model
        return _build_onnx(cfg)


def get_embedder(cfg: IndexConfig, *, for_queries: bool = False) -> Embedder:
    if cfg.embedder_provider == "ollama":
        keep = cfg.query_keep_alive if for_queries else ""
        return OllamaEmbedder(cfg.embedder_url, cfg.embedder_model, keep_alive=keep)
    if cfg.embedder_provider == "onnx":
        return _onnx(cfg)
    raise ValueError(f"unknown embedder provider {cfg.embedder_provider!r}")
