"""The API and the thin web UI.

GET  /                 the chat page (web/)
GET  /api/status       what is indexed, which model answers
GET  /api/speakers     registry names for the speaker filter
GET  /api/photo/{id}   an MP's avatar thumbnail (speakers/photos.py), only for matched speakers
GET  /api/sittings     parsed sittings, newest first (sessions browse)
GET  /api/sittings/{doc_id}  one sitting's turns grouped by section
POST /api/ask          {question, date_from?, date_to?, speaker_id?, party?} -> server-sent events
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Iterator
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tanyadewan.api.sittings import get_sitting, list_sittings
from tanyadewan.config import ROOT, load_config
from tanyadewan.generate.answer import _photos, answer
from tanyadewan.generate.llm import LLMError, get_llm
from tanyadewan.index.store import client
from tanyadewan.retrieve.search import Filters, search
from tanyadewan.speakers.parties import current_parties

WEB = ROOT / "web"
app = FastAPI(title="TanyaDewan", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=WEB), name="static")

# Public deployment (all optional env vars; unset = local behaviour):
#   ALLOWED_ORIGINS   comma-separated browser origins allowed to call the API (the Vercel site)
#   RATE_PER_MINUTE   questions per IP per minute (default 6)
#   DAILY_CAP         questions per day for the whole site, protecting the free LLM quota (default 400)
#   PUBLIC_MODE       "1" hides the full-transcript routes: the public site shows cited excerpts only
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"]
    )
PUBLIC = os.environ.get("PUBLIC_MODE") == "1"
_RATE = int(os.environ.get("RATE_PER_MINUTE", "6"))
_CAP = int(os.environ.get("DAILY_CAP", "400"))
_hits: dict[str, deque[float]] = defaultdict(deque)
_day: dict[str, Any] = {"date": "", "n": 0}
_lock = threading.Lock()


def _limit(request: Request) -> None:
    """Per-IP and per-day question limits, public mode only (in memory: resets on restart, fine for a free tier)."""
    if not PUBLIC:
        return
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[-1].strip() if fwd else (request.client.host if request.client else "?")
    now = time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    with _lock:
        if _day["date"] != today:
            _day.update(date=today, n=0)
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= _RATE:
            raise HTTPException(429, "Terlalu laju. Cuba lagi sebentar lagi.")
        if _day["n"] >= _CAP:
            raise HTTPException(429, "Kuota harian habis. Cuba lagi esok.")
        q.append(now)
        _day["n"] += 1


@app.middleware("http")
async def revalidate_ui(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """The page and its static files are small: make the browser re-check them (ETag) instead of
    showing a stale copy after a design change."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.on_event("startup")
def warm_up() -> None:
    """Public host: load both ONNX models and run one dummy search now, so the first visitor isn't the one waiting."""
    if not PUBLIC:
        return
    try:
        search("apa itu belanjawan", Filters(), 3, translate=False)
    except Exception as e:  # a dead Qdrant must not stop the API from starting; /api/status shows it
        print(f"warm-up skipped: {type(e).__name__}: {e}")


class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    date_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    speaker_id: str | None = Field(default=None, max_length=120)
    party: str | None = Field(default=None, max_length=40)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/status")
def status() -> dict[str, Any]:
    cfg = load_config()
    indexed = json.loads(cfg.index.state.read_text(encoding="utf-8")) if cfg.index.state.exists() else {}
    docs = cfg.paths.documents
    total = (
        sum(1 for ln in docs.read_text(encoding="utf-8").splitlines() if ln.strip()) if docs.exists() else 0
    )
    try:
        points = client(cfg.index).count(cfg.index.collection).count
    except Exception:
        points = 0
    try:
        engine = get_llm(cfg.generate).name
    except LLMError as e:
        engine = f"unavailable: {e}"
    dates = sorted(indexed)
    return {"sittings_indexed": len(indexed), "sittings_total": total, "chunks": points, "engine": engine, "public": PUBLIC,
            "from": dates[0][3:] if dates else None, "to": dates[-1][3:] if dates else None}  # fmt: skip


_MAX_NAME_CHARS = 80  # registry entries longer than this are parse debris (e.g. an attendance list glued into a name)


def _is_junk_name(person: dict[str, Any]) -> bool:
    core = str(person.get("core_name", ""))
    return (
        not core
        or len(core) > _MAX_NAME_CHARS
        or any(ch.isdigit() for ch in core)
        or "�" in str(person.get("name", ""))
    )


@lru_cache(maxsize=1)
def _registry() -> list[dict[str, Any]]:
    path = load_config().parse.speakers
    people: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return people


@lru_cache(maxsize=1)
def _speakers() -> list[dict[str, str]]:
    """The speaker filter's options: people with indexed text, no parse debris, sorted by name (not honorific)."""
    cfg = load_config()
    try:
        facet = client(cfg.index).facet(cfg.index.collection, key="speaker_id", limit=5000)
        indexed: set[str] | None = {str(h.value) for h in facet.hits}
    except Exception:  # embedded Qdrant or an unreachable server: show everyone rather than nobody
        indexed = None
    people = [
        p for p in _registry()
        if not _is_junk_name(p) and (indexed is None or p["speaker_id"] in indexed)
    ]  # fmt: skip
    people.sort(key=lambda p: str(p["core_name"]).lower())
    out = []
    for p in people:
        seat = p["constituencies"][-1]["constituency"] if p["constituencies"] else ""
        out.append({"id": p["speaker_id"], "label": f"{p['name']}" + (f" ({seat})" if seat else "")})
    return out


@app.get("/api/speakers")
def speakers() -> list[dict[str, str]]:
    return _speakers()


@app.get("/api/parties")
def parties() -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for party in current_parties().values():
        counts[party] = counts.get(party, 0) + 1
    return [{"party": p, "members": n} for p, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


@app.get("/api/photo/{speaker_id}.jpg")
def photo(speaker_id: str) -> FileResponse:
    # only ids from the matched list, so the path can't be steered outside thumb_dir
    if speaker_id not in _photos():
        raise HTTPException(404)
    return FileResponse(load_config().photos.thumb_dir / f"{speaker_id}.jpg", media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})  # fmt: skip


@app.get("/api/sittings")
def sittings() -> list[dict[str, Any]]:
    if PUBLIC:
        raise HTTPException(404)
    return list_sittings()


@app.get("/api/sittings/{doc_id}")
def sitting(doc_id: str) -> dict[str, Any]:
    if PUBLIC:
        raise HTTPException(404)
    found = get_sitting(doc_id)
    if found is None:
        raise HTTPException(404, "unknown sitting")
    return found


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/ask")
def ask(body: Ask, request: Request) -> StreamingResponse:
    _limit(request)
    if body.speaker_id and body.speaker_id not in {p["speaker_id"] for p in _registry()}:
        raise HTTPException(400, "unknown speaker")
    members: tuple[str, ...] = ()
    if body.party:
        members = tuple(sid for sid, p in current_parties().items() if p == body.party)
        if not members:
            raise HTTPException(400, "unknown party")
    filters = Filters(date_from=body.date_from, date_to=body.date_to, speaker_id=body.speaker_id or None,
                      speaker_ids=members)  # fmt: skip

    def stream() -> Iterator[str]:
        try:
            for event, data in answer(body.question.strip(), filters):
                yield _sse(event, data)
        except Exception as e:  # show it in the UI instead of a silent broken stream
            yield _sse("error", f"{type(e).__name__}: {e}")
            yield _sse("done", {})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
