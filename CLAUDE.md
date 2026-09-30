# CLAUDE.md

## Project: TanyaDewan (working name)

A public RAG system over the **Dewan Rakyat Hansard** (Penyata Rasmi), the official verbatim transcripts of Malaysian parliamentary debates. Users ask questions in Bahasa Malaysia, English, or code-switched mixes and get answers grounded in what was actually said, with speaker, date, and a link to the source PDF.

Example queries:
- "Apa yang MP cakap pasal PTPTN tahun lepas?"
- "Which MPs raised flood mitigation in Kelantan in 2024?"
- "Minister cakap apa bila ditanya pasal harga telur?"

This is a **portfolio project**. The point is not "a chatbot". The point is to prove, with numbers, that retrieval design decisions were tested and measured on messy, real, code-switched data. Every feature should be defensible in an interview.

### Goals, in priority order
1. **Correct attribution.** Who said it, when, in which sitting. Misattributing a quote to the wrong MP is the worst possible failure and is measured explicitly (and a defamation risk, not just a bug).
1b. **Say "not found" when it's not there.** No answer beats a confident wrong answer.
2. **Measured retrieval quality.** Golden eval set + benchmark harness comparing chunking, embeddings, retrieval, and reranking.
3. **Code-switching.** BM, English, and mixed queries all work, and the eval set covers all three. Hansard itself code-switches heavily, so this is real, not forced.
4. **Structured filtering.** Filter by date range, speaker, constituency, sitting.
5. **Agent layer.** Tools for speaker lookup, sitting lookup, topic timelines, side-by-side "what did A vs B say about X".
6. **Publicly deployed** with a live demo and a README showing benchmark results.

### Non-goals
- Auth, RBAC, multi-tenancy.
- Dewan Negara or state assemblies (maybe later, not now).
- Full historical coverage. Start with the **15th Parliament (late 2022 onward)**. Older Hansards are often scanned and need OCR; treat that as a stretch goal.

## Neutrality rules (non-negotiable)

This corpus is political. The system must behave like a librarian, not a pundit.

- Answers report **what was said, by whom, with citations**. Nothing else.
- No judging who was right, no "fact-checking" MPs against outside sources, no summaries that frame one side favourably.
- No sentiment scoring of parties or MPs. No "most controversial MP" features.
- When summarising a debate, represent every side that spoke, proportionally, with citations for each.
- Quotes must be verbatim from the transcript. Never paraphrase inside quotation marks.
- The system prompt for the answering LLM must encode these rules, and the eval set must include questions that try to bait it into taking sides.

## Theme: funny (the wrapper, never the answers)

The product has a playful personality. The humour lives in the **wrapper**, and the neutrality rules above always win.

- Funny: branding, loading and empty states, error pages, CLI progress messages, README asides. Jokes are about the tool, about paperwork, about reading thousands of pages of transcript so you don't have to.
- Never funny: answers, quotes, citations, summaries of debates, anything that names or describes an MP, party, constituency or ministry. Those stay dry, verbatim and cited.
- Never joke at the expense of any MP, party, race, religion, region or the institution itself. No caricatures of real people, no party colours used for laughs.
- Bait-question refusals may be light in tone ("Saya pustakawan, bukan pengulas politik") but must still report positions with citations.
- The eval set covers this: bait questions that try to get a "funny" dig at someone must fail to get one.

## Data source

- Hansard PDFs are published on the Parliament repository: `https://repositori.parlimen.gov.my` (DSpace). Files follow a pattern like `DR-DDMMYYYY.pdf`, grouped by Parlimen / Penggal / Mesyuarat.
- The repository states items are copyrighted, all rights reserved unless otherwise indicated. So:
  - Non-commercial portfolio use only.
  - **Do not redistribute raw PDFs** in the repo or on the demo. Store derived chunks, always link back to the official source URL.
  - Attribute Parlimen Malaysia clearly in the UI and README.
- Scrape politely: respect robots.txt, rate-limit (at least a few seconds between requests), cache everything, set a descriptive User-Agent.
- For every document record: source URL, Parlimen number, Penggal, Mesyuarat, sitting date, Bil. number, fetch date.

## Parsing (the hard part, do this carefully)

Before writing the parser, **inspect several real PDFs from different years and show me the raw extracted text.** Do not assume the format.

Things to handle:
- Speaker turns. Speaker lines typically include honorifics, the name, and often a constituency in brackets. Extract `speaker_raw`, `speaker_name` (normalised), `constituency`, and `role` (e.g. Speaker, Timbalan Speaker, Menteri) where present.
- Headers, footers, page numbers, and running titles that break mid-speech. Strip them and rejoin speeches across page breaks.
- Section structure: oral questions (Pertanyaan-pertanyaan Bagi Jawab Lisan), bills, motions, etc. Store the section as metadata.
- Interjections mid-speech (other MPs cutting in). Keep them as separate short turns attributed to the interjecting MP, not merged into the main speaker's turn.
- Mixed language within a single turn. Don't try to split by language. Optionally tag dominant language per turn for eval breakdowns.

Build a **speaker registry** (`data/processed/speakers.json`) mapping name variants to a canonical speaker ID. The same MP appears with different honorifics over time (Datuk becoming Dato' Sri, etc.). Party affiliation changes over time, so if party is stored, it must be stored **per sitting date**, not per person.

Parser output must be spot-checked: write a script that samples random turns and prints them next to the page they came from so I can verify attribution by eye.

## Product spec (merged from tanya-dewan-spec.md, 2026-09-29)

Where this section and the rest of the file differ, the neutrality rules, "the golden set is written by me",
and "ask before adding a dependency" still win.

### Chunk metadata
- Per chunk: date, sitting_id, page_number, pdf_url, speaker_name, speaker_role, constituency, party,
  topic/bill under debate (from headings), `segment_type` (oral question, minister's reply, bill debate, ...).
- Party is stored **per sitting date**, never per person (party changes). Party is a filter, never a score.
- **Q&A pairing:** link each oral question to the minister's reply where possible, stored as a relation between chunks.

### Retrieval
- **Hybrid:** BM25 (keyword) + dense (bge-m3), fused with RRF. Pure vectors miss bill names and acronyms.
- **Reranker** on the hybrid results (bge-reranker-v2-m3 or similar multilingual).
- **Filters at retrieval time:** speaker, party, date range, parliament term, segment type.
- **Cross-lingual:** ask in English, retrieve BM passages, and vice versa. Answer in the language of the question.

### Generation
- Answer only from retrieved chunks; the system prompt forbids outside knowledge for factual claims.
- Every sentence with a claim carries an inline citation number; verbatim quotes are returned with the answer.
- If retrieval confidence is low or nothing relevant is found: an explicit **"not found in the records"** response.
- Show which sittings the answer rests on ("Based on N sittings").
- Stance summaries only when backed by verbatim quotes; no rankings, sentiment scores or judgements.

### UI / UX
- **Answer screen:** search bar on top; filter chips below it (parliament term, + Speaker, + Party, + Date; chips,
  not a settings page); answer with inline citation numbers (tapping one scrolls to its source card); a small
  disclaimer under the answer ("Based on N sittings. AI summary, check the sources."); source cards under the
  answer with number, speaker (official photo when matched), role/constituency, date, verbatim snippet and a
  "View in Hansard, p. X" deep link to the exact PDF page.
- **Other screens:** empty state with starter questions; sessions browse (sittings by date, open one to read it);
  topic timeline (how often a topic came up over time); a clear not-found state.
- **Out of scope for v1:** multi-turn chat threads, accounts / saved history, chatbot persona or mascot,
  fine-tuning, agents, heavy animation. Quiet, clean polish only.

### Evaluation additions
- Question mix also covers **cross-lingual** (English question, BM source).
- Generation metrics: faithfulness, **citation accuracy**, **correct refusal rate** on unanswerable questions.
- One script runs the full eval and writes a results table; results are tracked across changes
  (reranker on/off, chunking variants) for the README.

### README additions
- Screenshots, architecture diagram (ingestion, chunking, hybrid retrieval, reranker, generation), design
  decisions and why, eval table and what changed between versions, known limitations (parsing errors, name
  normalisation edge cases, corpus scope).

## Stack

- **Python 3.12**, managed with **uv**
- **PDF parsing:** PyMuPDF first. Only reach for anything heavier if PyMuPDF genuinely fails, and ask first.
- **FastAPI** for the API, SSE for streaming
- **Qdrant** via Docker: dense + sparse vectors, payload filtering on date/speaker/section
- **Embeddings:** `BAAI/bge-m3` (multilingual, handles BM). Keep behind an interface so others can be benchmarked.
- **Reranker:** `BAAI/bge-reranker-v2-m3`
- **LLM:** pluggable. Ollama locally (qwen2.5 family) plus one hosted provider for the public demo. Never hardcode a provider.
- **Eval:** custom metrics (recall@k, MRR, nDCG, attribution accuracy) + RAGAS for faithfulness
- **Frontend:** Next.js (App Router, TypeScript) + shadcn/ui + Tailwind, in `frontend/`. Mobile-first, search-first (not a ChatGPT clone). FastAPI stays the backend; the frontend only calls `/api/*`. The old plain-HTML page in `web/` stays until the new one replaces it.
- **Infra:** Docker Compose locally, GitHub Actions for CI

## Repo layout

```
tanyadewan/
  src/tanyadewan/
    fetch/         # repository crawler, polite downloader, metadata
    parse/         # PDF -> clean text -> speaker turns -> sections
    speakers/      # speaker registry, name normalisation
    chunk/         # chunking strategies
    index/         # embedding, Qdrant collections
    retrieve/      # dense, sparse, hybrid (RRF), filters, reranking
    generate/      # prompts, LLM clients, citation formatting
    agent/         # tools + tool-calling loop
    api/           # FastAPI app, routes, SSE
    config.py      # tunables loaded from YAML
  eval/
    golden/        # hand-written golden set (jsonl)
    configs/       # one YAML per experiment
    run_eval.py
    results/       # committed result tables
  scripts/
    spot_check.py  # random turn vs source page, for manual verification
  data/
    raw/           # PDFs (gitignored, never committed)
    processed/     # turns, chunks, speakers.json (gitignored)
  frontend/        # Next.js + shadcn/ui (search, sources, sessions, timeline)
  web/             # old plain-HTML chat page (being replaced by frontend/)
  tests/
  docker-compose.yml
  README.md
  CLAUDE.md
```

## Commands

```bash
uv sync
docker compose up -d qdrant
uv run python -m tanyadewan.fetch --parlimen 15          # download + record metadata
uv run python -m tanyadewan.parse                         # PDFs -> speaker turns
uv run python scripts/spot_check.py --n 20                # verify attribution by eye
uv run python -m tanyadewan.index --config eval/configs/baseline.yaml
uv run uvicorn tanyadewan.api.main:app --reload
uv run python eval/run_eval.py --config eval/configs/baseline.yaml
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy src
```

## The eval set (most important part of the repo)

`eval/golden/questions.jsonl`, one per line:
```json
{"id": "q001", "lang": "ms|en|mixed", "type": "factual|speaker|timeline|multi_turn|unanswerable|bait", "question": "...", "filters": {"date_from": null, "date_to": null, "speaker_id": null}, "relevant_turn_ids": ["..."], "expected_speakers": ["..."], "reference_answer": "...", "answerable": true}
```

- Target **at least 100 questions**, roughly a third each BM, English, mixed.
- Question types to cover:
  - **factual**: what was said about a topic
  - **speaker**: what did a specific MP say about X
  - **timeline**: how did discussion of X change across sittings
  - **multi_turn**: answer needs a question AND the minister's reply (Q&A pairs span turns)
  - **unanswerable** (~10%): topic never raised in the indexed range
  - **bait** (~10%): tries to get the system to take a side ("siapa betul pasal isu ni?"). Correct behaviour is to report positions with citations and decline to judge.
- Questions and relevance labels are written **by me**. Claude may suggest candidates in a separate file, but never adds them to the golden set and never writes reference answers without flagging them for review.
- If parsing changes and turn IDs shift, remap labels by (sitting date, speaker, text offset), never regenerate from a model.

## Metrics
- recall@k, MRR, nDCG on retrieved turns
- **attribution accuracy**: of the speakers named in the answer, how many actually said the cited content
- faithfulness (RAGAS)
- refusal accuracy on unanswerable + bait questions
- latency p50/p95
- every metric broken down by query language

## Experiments to run and report

1. Chunking: one chunk per speaker turn vs fixed-size windows vs **question+answer pair** chunks for oral question sections
2. Long turn handling: split long speeches with speaker metadata repeated in each sub-chunk vs not
3. Dense vs sparse vs hybrid (RRF)
4. Reranker on vs off
5. Metadata in the embedded text (prepending "Speaker, constituency, date:" to chunk text) vs metadata only as filters
6. Embedding model comparison (bge-m3 vs at least one other multilingual model)
7. Query rewriting / translation of the query into both BM and English before retrieval, on vs off

Report latency alongside quality. A small gain that triples latency is a finding, not an automatic win.

## Agent tools (M5)
- `search_hansard(query, date_from, date_to, speaker_id, section)`
- `get_speaker(name)`: resolve fuzzy names to canonical speaker IDs
- `get_sitting(date)`: agenda/sections for a given sitting
- `topic_timeline(query, date_from, date_to)`: count of matching turns per sitting, for a chart
- `compare_speakers(query, speaker_ids)`: side-by-side cited excerpts, no judgement

## Coding rules for Claude

- **Ask before adding a dependency.** Explain why and name the lighter alternative.
- All tunables go in config YAML. No magic numbers.
- Type hints everywhere; `mypy` passes.
- Retrieval and parsing must be testable without a running LLM.
- Every parsing, chunking, or retrieval change is followed by an eval run, and the diff is shown to me before moving on.
- Never claim an improvement without eval numbers.
- **Never fabricate Hansard content, quotes, or speaker names** in tests, fixtures, examples, or docs. Use real snippets from `data/processed/` or obviously fake placeholders like "MP_A said LOREM".
- Log retrieved turn IDs, speakers, and scores for every query.
- Secrets via `.env` only; keep `.env.example` current.
- Conventional commits (`feat:`, `fix:`, `eval:`, `parse:`, `docs:`).

## Milestones

1. **M1: Fetch + parse.** Crawl 15th Parliament Hansards, parse into speaker turns, speaker registry, spot-check script. No retrieval yet. Parsing quality gates everything else.
2. **M2: Baseline RAG.** Turn-level chunks, dense retrieval, cited answers via CLI.
3. **M3: Eval harness + golden set.** Baseline numbers committed.
4. **M4: Retrieval experiments.** Hybrid, reranker, chunking variants, per-language results in README.
5. **M5: API + streaming + filters + frontend.**
6. **M6: Agent tools**, including topic timeline chart.
7. **M7: Deploy + README polish.** Live link, architecture diagram, results table, "what didn't work" section.

Status (2026-09-29): M1 and M2 done (OCR for broken PDFs included); indexing paused at 68/266 sittings.
Order chosen by me: **Next.js + shadcn frontend rebuild first** (search-first, per the Product spec), then hybrid
retrieval + reranker + not-found, then the eval harness (M3), then the rest.

## README must eventually include
- One-line pitch, live demo link, clear attribution to Parlimen Malaysia
- Architecture diagram
- Benchmark table split by query language, including attribution accuracy
- Parsing challenges and how they were solved (this is a great interview story)
- What didn't work and why
- Neutrality policy, stated plainly
- Run locally in under 5 commands
