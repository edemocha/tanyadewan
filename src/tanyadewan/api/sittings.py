"""Sessions browse: the list of indexed-or-parsed sittings, and one sitting's turns grouped by section.

Read-only views over data/processed (documents.jsonl + turns/*.jsonl). Speaker labels, photos and initials
come from the same helpers as the answer's source cards, so a sitting reads exactly like a source does.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from tanyadewan.config import load_config
from tanyadewan.generate.answer import _photos, initials
from tanyadewan.generate.prompt import date_ms, speaker_display


@lru_cache(maxsize=1)
def _documents() -> dict[str, dict[str, Any]]:
    cfg = load_config()
    docs: dict[str, dict[str, Any]] = {}
    if cfg.paths.documents.exists():
        for line in cfg.paths.documents.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                docs[d["doc_id"]] = d
    return docs


def _turns_path(doc_id: str) -> Any:
    return load_config().parse.turns_dir / f"{doc_id}.jsonl"


@lru_cache(maxsize=1)
def list_sittings() -> list[dict[str, Any]]:
    """Newest first; only sittings that have been parsed into turns."""
    out = []
    for doc_id, d in _documents().items():
        path = _turns_path(doc_id)
        if not path.exists():
            continue
        n_turns = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        out.append({
            "doc_id": doc_id, "date": d["sitting_date"], "date_display": date_ms(d["sitting_date"]),
            "penggal": d.get("penggal"), "mesyuarat": d.get("mesyuarat"), "mesyuarat_title": d.get("mesyuarat_title"),
            "bil": d.get("bil"), "is_draft": bool(d.get("is_draft")), "n_turns": n_turns, "pdf_url": d.get("source_url"),
        })  # fmt: skip
    return sorted(out, key=lambda s: s["date"], reverse=True)


def get_sitting(doc_id: str) -> dict[str, Any] | None:
    """One sitting as consecutive section blocks; None if the id isn't a parsed sitting."""
    meta = next((s for s in list_sittings() if s["doc_id"] == doc_id), None)
    if meta is None:
        return None
    photos = _photos()
    sections: list[dict[str, Any]] = []
    for line in _turns_path(doc_id).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        heading = (t.get("section_heading") or t.get("section") or "").strip()
        if not sections or sections[-1]["heading"] != heading:
            sections.append({"heading": heading, "section": t.get("section"), "turns": []})
        page = t.get("page_start")
        named = t.get("speaker_id") and not t.get("unattributed")
        sections[-1]["turns"].append({
            "turn_id": t["turn_id"], "speaker": speaker_display(t), "speaker_id": t.get("speaker_id"),
            "role": t.get("role"), "constituency": t.get("constituency"), "resolution": t.get("resolution"),
            "unattributed": bool(t.get("unattributed")), "is_interjection": bool(t.get("is_interjection")),
            "initials": initials(t), "photo_url": f"/api/photo/{t['speaker_id']}.jpg" if named and t["speaker_id"] in photos else None,
            "page_label": t.get("page_label_start"), "ocr": bool(t.get("ocr")),
            "pdf_url": f"{t.get('source_url')}#page={page}" if page else t.get("source_url"), "text": t.get("text"),
        })  # fmt: skip
    return {**meta, "sections": sections}
