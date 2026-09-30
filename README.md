# TanyaDewan

> Ask the Dewan Rakyat anything. We read the Hansard so you don't have to. (All of it. Every page. Every `[Tepuk]`.)

A RAG system over the Malaysian **Dewan Rakyat Hansard** (Penyata Rasmi). You can ask in Bahasa Malaysia, English or
both at once, and every answer says who said it, when, and links to the official record.

The humour stays in the wrapper. Answers are neutral, quotes are verbatim, and every claim is cited:
a librarian, not a pundit (see [CLAUDE.md](CLAUDE.md)).

**Status: M1 (fetch + parse).** Crawling, parsing, the speaker registry and the spot-check script work.
Retrieval starts at M2. What the PDFs look like and how each quirk is handled: [docs/parsing-notes.md](docs/parsing-notes.md).

## Source and attribution

Transcripts: **Penyata Rasmi Dewan Rakyat, © Parlimen Malaysia**, from
[repositori.parlimen.gov.my](https://repositori.parlimen.gov.my) and [www.parlimen.gov.my](https://www.parlimen.gov.my).
Non-commercial portfolio use. PDFs are not redistributed: this repo stores no PDFs or transcript text, and every
record links back to the official source.

## Run

```bash
uv sync
uv run python -m tanyadewan.fetch --parlimen 15          # index both sources, download PDFs (polite, ~20 min)
uv run python -m tanyadewan.parse                         # PDFs -> speaker turns + speaker registry
uv run python scripts/spot_check.py --n 20                # verify attribution by eye
uv run pytest && uv run ruff check . && uv run mypy src
```

Chat (M2 baseline: turn-level chunks, bge-m3 dense retrieval, cited answers):

```bash
tools/qdrant/qdrant.exe --config-path tools/qdrant/config.yaml   # local Qdrant server (no Docker needed)
ollama pull bge-m3                                               # embeddings, local
uv run python -m tanyadewan.index                                # newest sittings first, resumable
uv run python -m tanyadewan.speakers.photos                      # MP avatars from the official member list (~15 min)
echo LLM_API_KEY=... > .env                                      # a free Groq key for answers
uv run python -m tanyadewan.api                                  # http://127.0.0.1:8766
npm --prefix frontend install && npm --prefix frontend run dev -- --port 3100   # the web app: http://localhost:3100
```

The crawler obeys robots.txt, waits 4 seconds between requests, caches every listing page, and never downloads
a PDF twice. `--refresh --recheck-drafts` looks for revised transcripts. Tunables are in `config.yaml`.

MP avatars come from Parlimen's member list, which shows each seat's current member. A photo is attached only
when the seat *and* the name match someone in the speaker registry: a by-election winner never lends their face
to the previous member's quotes. Anything unmatched shows initials. Each official photo (~1.7 MB) is fetched once
and kept only as a small gitignored thumbnail; every avatar links to the member's official profile page.

## Outputs (gitignored)

| File | What |
|---|---|
| `data/processed/documents.jsonl` | One record per sitting: source URL, Parlimen/Penggal/Mesyuarat, date, Bil., draft flag, hash, fetch date |
| `data/processed/turns/<doc_id>.jsonl` | Speaker turns: speaker as printed, resolved `speaker_id` and **how** it was resolved, text, stage directions, section, question number, pages, language |
| `data/processed/speakers.json` | Speaker registry: canonical ID, name variants, seats and roles with first/last seen dates |
| `data/processed/parse_report.json` | Per sitting: counts by resolution method, pages without text, unresolved label names for review |
