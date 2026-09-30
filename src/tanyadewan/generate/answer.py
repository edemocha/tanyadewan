"""Question -> retrieved sources -> streamed, cited answer -> checks.

Events yielded, in order:
  ("sources", [..])   the numbered sources the model sees (with PDF links)
  ("not_found", {..}) instead of an answer, when retrieval found nothing relevant enough (then "done")
  ("engine", name)
  ("token", text)     many
  ("check", {...})    quotes not found verbatim in any source, citations to missing sources
  ("done", {...})     timings
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from tanyadewan.config import load_config
from tanyadewan.generate.llm import LLMError, get_llm
from tanyadewan.generate.prompt import QUESTION_WORDS, build_messages, date_ms, speaker_display
from tanyadewan.retrieve.search import Filters, search
from tanyadewan.speakers.parties import current_parties

_QUOTE = re.compile(r"[\"“”]([^\"“”]{3,600})[\"“”]")
_CITE = re.compile(r"\[(\d{1,2})\]")


def _norm(text: str) -> str:
    return " ".join(text.replace("’", "'").replace("‘", "'").split())


def unverified_quotes(answer: str, sources: list[dict[str, Any]], min_words: int) -> list[str]:
    """Quoted spans (min_words+) that don't appear verbatim in any source. '...' splits a quote into parts."""
    haystack = [_norm(str(s.get("text") or "")) for s in sources]
    bad = []
    for m in _QUOTE.finditer(answer):
        quote = m.group(1)
        if len(quote.split()) < min_words:
            continue
        parts = [_norm(p).strip(" .,") for p in re.split(r"\s*(?:\.\.\.|…)\s*", quote) if p.strip(" .,")]
        if not all(any(p in h for h in haystack) for p in parts):
            bad.append(quote)
    return bad


@lru_cache(maxsize=1)
def _photos() -> dict[str, dict[str, str]]:
    """speaker_id -> official portrait (speakers/photos.py). Missing file = no photos, initials only."""
    cfg = load_config().photos
    if not cfg.file.exists():
        return {}
    photos: dict[str, dict[str, str]] = json.loads(cfg.file.read_text(encoding="utf-8"))
    # only speakers whose thumbnail has been built; the rest show initials
    return {sid: rec for sid, rec in photos.items() if (cfg.thumb_dir / f"{sid}.jpg").exists()}


@lru_cache(maxsize=1)
def _core_names() -> dict[str, str]:
    path = load_config().parse.speakers
    people = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return {person["speaker_id"]: person["core_name"] for person in people}


def initials(p: dict[str, Any]) -> str:
    """Avatar fallback from the registry's title-free core name ("Dato' Sri X bin Y" -> "XY"); "?" if unnamed."""
    words = _core_names().get(str(p.get("speaker_id")), "").split() if not p.get("unattributed") else []
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper() if words else "?"


def highlight_terms(queries: list[str]) -> list[str]:
    """Topic words of the question (and of its Malay version) for highlighting inside verbatim source text."""
    terms: list[str] = []
    for q in queries:
        for w in re.findall(r"[\w'-]+", q.lower()):
            w = w.strip("'-")
            if len(w) >= 3 and w not in QUESTION_WORDS and w not in terms:
                terms.append(w)
    return terms


def source_card(n: int, p: dict[str, Any], score: float, terms: list[str] | None = None) -> dict[str, Any]:
    page = p.get("page_start")
    # a portrait only for a resolved speaker; unattributed or unreadable turns never get a face
    photo = (
        _photos().get(str(p.get("speaker_id"))) if p.get("speaker_id") and not p.get("unattributed") else None
    )
    return {
        "n": n, "turn_id": p.get("turn_id"), "speaker": speaker_display(p), "speaker_id": p.get("speaker_id"),
        "constituency": p.get("constituency"), "role": p.get("role"), "resolution": p.get("resolution"),
        "unattributed": bool(p.get("unattributed")), "date": p.get("sitting_date"),
        "date_display": date_ms(str(p.get("sitting_date"))), "section": p.get("section"),
        "section_heading": p.get("section_heading"), "page_label": p.get("page_label_start"),
        "pdf_url": f"{p.get('source_url')}#page={page}" if page else p.get("source_url"),
        "is_draft": bool(p.get("is_draft")), "ocr": bool(p.get("ocr")), "text": p.get("text"), "part": p.get("part"),
        "n_parts": p.get("n_parts"), "score": round(score, 3),
        "party": current_parties().get(str(p.get("speaker_id"))) if not p.get("unattributed") else None,
        "photo_url": f"/api/photo/{p.get('speaker_id')}.jpg" if photo else None,
        "profile_url": photo["profile_url"] if photo else None, "initials": initials(p), "terms": terms or [],
    }  # fmt: skip


def answer(question: str, filters: Filters) -> Iterator[tuple[str, Any]]:
    cfg = load_config()
    t0 = time.time()
    result = search(question, filters)
    t_retrieve = time.time() - t0
    if result.not_found:
        # No answer beats a confident wrong one: don't let the model write from weak sources.
        yield "sources", []
        yield "not_found", {"best_relevance": result.best_relevance, "threshold": cfg.retrieve.min_relevance,
                            "mode": result.mode, "reranked": result.reranked}  # fmt: skip
        yield "done", {"retrieve_ms": int(t_retrieve * 1000), "generate_ms": 0, "timings": result.ms}
        return
    hits = result.hits
    sources = [h.payload for h in hits]
    terms = highlight_terms(result.queries or [question])
    yield "sources", [source_card(i, h.payload, h.score, terms) for i, h in enumerate(hits, 1)]
    llm = get_llm(cfg.generate)
    parts: list[str] = []
    try:
        for piece in llm.stream(build_messages(question, sources, cfg.generate.context_chars_per_source)):
            parts.append(piece)
            yield "token", piece
    except LLMError as e:
        yield "error", str(e)
    yield "engine", llm.used or "none"  # who actually answered, and why (after a fallback)
    text = re.sub(r"<think>.*?</think>", "", "".join(parts), flags=re.S)
    cited = {int(n) for n in _CITE.findall(text)}
    yield (
        "check",
        {
            "unverified_quotes": unverified_quotes(text, sources, cfg.generate.min_quote_words),
            "missing_sources": sorted(n for n in cited if not 1 <= n <= len(sources)),
            "cited": sorted(n for n in cited if 1 <= n <= len(sources)),
        },
    )
    yield (
        "done",
        {
            "retrieve_ms": int(t_retrieve * 1000),
            "generate_ms": int((time.time() - t0 - t_retrieve) * 1000),
            "timings": result.ms,
        },
    )
