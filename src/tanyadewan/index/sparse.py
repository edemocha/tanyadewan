"""BM25 keyword vectors for Qdrant's sparse index, so exact terms (bill names, acronyms, "PTPTN", "RM64.1")
are matched even when the dense embedding blurs them.

A document vector holds each term's BM25 term-frequency weight; Qdrant's IDF modifier multiplies in the
inverse document frequency at query time, from its own live counts. The query vector is 1.0 per distinct term.
So score(q, d) = sum over shared terms of idf(t) * tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * |d| / avg|d|)).

No stemming: Malay affixes ("bangun" / "pembangunan") are left to the dense side of the hybrid.
Terms are hashed to stable 31-bit indices (crc32); collisions at this vocabulary size are negligible.
"""

from __future__ import annotations

import re
import unicodedata
import zlib
from collections import Counter
from dataclasses import dataclass

from qdrant_client import models

_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    """Lowercased word pieces; hyphens and apostrophes split ("kanak-kanak" -> kanak, kanak).
    Single letters are dropped, single digits kept (they matter in "Bil. 3", "RM1")."""
    norm = unicodedata.normalize("NFKC", text).lower()
    return [t for t in _TOKEN.findall(norm) if len(t) > 1 or t.isdigit()]


def term_index(term: str) -> int:
    return zlib.crc32(term.encode("utf-8")) & 0x7FFFFFFF


@dataclass(frozen=True)
class BM25:
    k1: float
    b: float
    avg_len: float

    def document(self, text: str) -> models.SparseVector:
        toks = tokens(text)
        if not toks:
            return models.SparseVector(indices=[], values=[])
        norm = self.k1 * (1 - self.b + self.b * len(toks) / self.avg_len)
        weights: dict[int, float] = {}
        for term, tf in Counter(toks).items():
            i = term_index(term)
            weights[i] = weights.get(i, 0.0) + tf * (self.k1 + 1) / (tf + norm)
        return models.SparseVector(indices=list(weights), values=list(weights.values()))

    def query(self, text: str) -> models.SparseVector:
        idx = sorted({term_index(t) for t in tokens(text)})
        return models.SparseVector(indices=idx, values=[1.0] * len(idx))
