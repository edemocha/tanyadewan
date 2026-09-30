"""Cross-encoder reranking with BAAI/bge-reranker-v2-m3 (multilingual; handles BM, English and mixed).

The ONNX export runs through onnxruntime-directml: fp16 on the GPU (DirectML), or int8 on CPU; `tokenizers` does the
XLM-RoBERTa pair encoding (<s> query </s></s> passage </s>). The score is sigmoid(logit): a probability-like
relevance in [0, 1], which is also what the "not found in the records" threshold is set on.
"""

from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from tanyadewan.config import RerankConfig


class Reranker:
    def __init__(self, cfg: RerankConfig) -> None:
        if not cfg.model_path.exists():
            raise FileNotFoundError(
                f"reranker model missing: {cfg.model_path}. See README (models/bge-reranker-v2-m3) to download it."
            )
        self.cfg = cfg
        opts = ort.SessionOptions()
        if cfg.threads:
            opts.intra_op_num_threads = cfg.threads
        providers = ["CPUExecutionProvider"]
        if cfg.device == "dml" and "DmlExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "DmlExecutionProvider")
            opts.enable_mem_pattern = False  # both required by DirectML
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(cfg.model_path), opts, providers=providers)
        self._run_lock = threading.Lock()  # overlapping Run() calls crash the DirectML session (access violation)
        self.tokenizer = Tokenizer.from_file(str(cfg.tokenizer_path))
        self.tokenizer.enable_truncation(max_length=cfg.max_tokens, strategy="only_second")
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>") or 1, pad_token="<pad>")

    def scores(self, query: str, passages: list[str]) -> list[float]:
        # batch passages of similar length together so short turns aren't padded to the longest one
        order = sorted(range(len(passages)), key=lambda i: len(passages[i]))
        out = [0.0] * len(passages)
        for start in range(0, len(order), self.cfg.batch_size):
            idx = order[start : start + self.cfg.batch_size]
            batch = self.tokenizer.encode_batch([(query, passages[i]) for i in idx])
            ids = np.array([e.ids for e in batch], dtype=np.int64)
            mask = np.array([e.attention_mask for e in batch], dtype=np.int64)
            with self._run_lock:
                (logits,) = self.session.run(["logits"], {"input_ids": ids, "attention_mask": mask})
            for i, p in zip(idx, 1.0 / (1.0 + np.exp(-logits[:, 0])), strict=True):
                out[i] = float(p)
        return out


@lru_cache(maxsize=1)
def _build(cfg: RerankConfig) -> Reranker:
    return Reranker(cfg)


_build_lock = threading.Lock()


def get_reranker(cfg: RerankConfig) -> Reranker:
    # lru_cache does not serialise concurrent misses: parallel first requests would each load the model
    # (and building a DirectML session while another runs crashes the process)
    with _build_lock:
        return _build(cfg)
