# Deploying TanyaDewan for RM0

Stack: **Vercel Hobby** (Next.js) + **Hugging Face Space** (Docker, free CPU: FastAPI, ONNX embedder and reranker)
+ **Qdrant Cloud** free cluster (vectors) + **Groq/Kilo** free tiers (LLM). No credit card is needed for any of them.
Free-tier limits change; check each provider's page before you rely on it.

Steps marked (you) need your own account. Never paste keys into chat or commit them.

## 1. Qdrant Cloud (you)
1. Create a free cluster at cloud.qdrant.io. Copy the cluster URL and create an API key.
2. Push the local index (PowerShell; the keys stay in this shell only):
   ```powershell
   $env:QDRANT_CLOUD_URL = "https://xxxx.cloud.qdrant.io:6333"
   $env:QDRANT_CLOUD_API_KEY = "<key>"
   uv run python scripts/push_qdrant.py --limit 500   # dry run
   uv run python scripts/push_qdrant.py               # everything (safe to re-run)
   ```
   It creates the collection with on-disk vectors and int8 quantisation to fit the free 1 GB.

## 2. Hugging Face Space (you)
1. huggingface.co > New Space > SDK **Docker**, hardware **CPU basic (free)**, name e.g. `tanyadewan`.
2. Build the bundle (code, config, metadata, MP thumbnails; no transcript text):
   ```bash
   uv run python scripts/make_space_bundle.py
   ```
3. Push `deploy/space/` to the Space's git repo (`git init`, add the Space as remote, push). The Dockerfile downloads
   the model weights (about 1.2 GB) at build time.
4. Space > Settings > **Secrets**: `QDRANT_URL`, `QDRANT_API_KEY`, `LLM_API_KEY` (Groq), and
   **Variables**: `ALLOWED_ORIGINS` (your Vercel URL), optionally `RATE_PER_MINUTE` (6) and `DAILY_CAP` (400).
5. Open `https://<you>-tanyadewan.hf.space/api/status`: it should show the chunk count.

## 3. Vercel (you)
1. Import the GitHub repo, **root directory `frontend`**, framework Next.js.
2. Environment variables: `NEXT_PUBLIC_API_BASE` = the Space URL, `NEXT_PUBLIC_PUBLIC_MODE` = `1`.
3. Deploy. Then put the Vercel URL into the Space's `ALLOWED_ORIGINS` (step 2.4).

## 4. Keep-alive
Add the repo variable `SPACE_URL`; `.github/workflows/keepalive.yml` pings `/api/status` every two days.

## Guardrails already in the code
- Per-IP limit (`RATE_PER_MINUTE`) and a site-wide daily cap (`DAILY_CAP`) protect the free LLM quota; both answer HTTP 429
  with a Malay message. In-memory, so they reset when the Space restarts.
- `PUBLIC_MODE=1` removes the full-transcript routes and the "Sidang" pages: the public site shows cited excerpts and
  links to the official PDFs only.
- Off-topic questions return "not found" (reranker gate, threshold uncalibrated until the golden set exists).

## Known limits
- CPU retrieval: 2.4-3.4 s per question on a 12-core PC (5 passages reranked at 192 tokens; English questions cost one
  extra translation call). The free Space has 2 vCPU, so expect slower; measure it and tune `retrieve.rerank_pool`
  and `rerank.max_tokens` in `config.prod.yaml`.
- The int8 CPU embedder is not bit-identical to the Ollama one (cosine about 0.985); top-1 matched on 9 of 9 real probe
  queries. The eval will show whether it matters.
- Free Spaces sleep after inactivity; the first visit after a sleep waits for the models to load.
- Only 68 of 266 sittings are indexed.
