"""Baseline chunking (M2): one chunk per speaker turn.

A turn longer than max_chars is split into windows at sentence boundaries, with some overlap. Every
window keeps the full speaker metadata in its payload, so a sub-chunk is never separated from who said
it. The embedded text is the speech only; whether prepending "Speaker, seat, date:" helps is an M4
experiment, not an assumption.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<turn_id>#<part>"
    text: str
    payload: dict[str, Any]


def windows(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = _SENTENCE_END.split(text)
    out: list[str] = []
    current = ""
    for s in sentences:
        while len(s) > max_chars:  # a single very long sentence: hard split
            s_head, s = s[:max_chars], s[max_chars - overlap :]
            if current:
                out.append(current)
                current = ""
            out.append(s_head)
        if current and len(current) + 1 + len(s) > max_chars:
            out.append(current)
            tail = current[-overlap:]
            current = tail[tail.find(" ") + 1 :] + " " + s if overlap else s
        else:
            current = f"{current} {s}".strip()
    if current:
        out.append(current)
    return out


PAYLOAD_FIELDS = (
    "turn_id", "doc_id", "sitting_date", "seq", "kind", "speaker_raw", "speaker_name", "constituency", "role",
    "unattributed", "speaker_id", "resolution", "is_interjection", "section", "section_heading", "subheading",
    "question_no", "question_group", "page_start", "page_end", "page_label_start", "lang", "is_draft", "source_url",
    "ocr",
)  # fmt: skip


def chunk_turn(turn: dict[str, Any], max_chars: int, overlap: int, min_chars: int) -> list[Chunk]:
    text = str(turn.get("text") or "")
    if len(text) < min_chars:
        return []
    parts = windows(text, max_chars, overlap)
    base = {k: turn.get(k) for k in PAYLOAD_FIELDS}
    base["sitting_day"] = int(str(turn["sitting_date"]).replace("-", ""))  # for date-range filters
    return [
        Chunk(f"{turn['turn_id']}#{i}", part, {**base, "text": part, "part": i, "n_parts": len(parts)})
        for i, part in enumerate(parts)
    ]
