"""Dominant language of a turn (ms / en / mixed / unknown), for per-language eval breakdowns only.

A stopword count, deliberately simple: turns are never split by language (CLAUDE.md).
"""

from __future__ import annotations

import re

MS = frozenset(
    [
        "yang",
        "dan",
        "ini",
        "itu",
        "untuk",
        "dengan",
        "kepada",
        "tidak",
        "akan",
        "ada",
        "saya",
        "kita",
        "dalam",
        "pada",
        "telah",
        "juga",
        "bagi",
        "oleh",
        "atau",
        "sebagai",
        "adalah",
        "kerana",
        "ia",
        "mereka",
        "boleh",
        "lebih",
        "daripada",
        "apa",
        "jika",
        "sudah",
        "belum",
        "kami",
        "tersebut",
        "iaitu",
        "bahawa",
        "sahaja",
        "lagi",
        "namun",
        "supaya",
        "dia",
        "hendak",
        "mahu",
        "macam",
        "mana",
    ]
)
EN = frozenset(
    [
        "the",
        "and",
        "of",
        "to",
        "is",
        "in",
        "that",
        "for",
        "this",
        "we",
        "are",
        "be",
        "it",
        "with",
        "as",
        "not",
        "on",
        "have",
        "will",
        "our",
        "by",
        "which",
        "you",
        "from",
        "was",
        "there",
        "what",
        "they",
        "can",
        "would",
        "should",
        "been",
        "has",
        "were",
        "their",
        "if",
        "but",
        "about",
        "so",
        "because",
    ]
)


def dominant_language(text: str, min_stopwords: int, mixed_share: float) -> str:
    words = re.findall(r"[a-z]+", text.lower())
    ms = sum(w in MS for w in words)
    en = sum(w in EN for w in words)
    total = ms + en
    if total < min_stopwords:
        return "unknown"
    if min(ms, en) / total >= mixed_share:
        return "mixed"
    return "ms" if ms > en else "en"
