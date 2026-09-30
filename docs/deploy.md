# Deploying TanyaDewan

Checked 30 Sep 2026. Free-tier terms change often: re-check each provider's page before relying on a number here.
Steps marked (you) need your own account. Never paste keys into chat or commit them.

## Chosen path: everything on Vercel (two services, one project)

The root `vercel.json` defines two Vercel Services in one project, and `/api/*` goes to the backend, everything else to the frontend:

| Piece | What it is | Where |
|---|---|---|
| Frontend | The Next.js app (what you see at `localhost:3100`) | Vercel service `frontend` (`frontend/`) |
| Backend | FastAPI + the two int8 ONNX models + the LLM call | Vercel service `backend` (`backend/`, Python) |
| Vectors | Qdrant collection (dense + BM25) | Qdrant Cloud free (the backend can't hold them) |
| LLM | Groq, with a free Kilo model as fallback | hosted free tiers |

Because both services share one domain, the frontend calls `/api/...` on its own origin: no `NEXT_PUBLIC_API_BASE`, no CORS.

How the backend service is built (`backend/`):
- `requirements.txt` is the lean runtime set (the root `pyproject.toml` needs Windows-only DirectML plus the PDF and OCR libraries).
- `build.py` runs as the service's build command. It copies `../src` and the configs next to itself (the code finds
  `config.yaml` two levels above the package), copies `seed/` into `data/`, and downloads the four model files (about 1.2 GB).
  It fails with a clear message if the checkout has no `../src`.
- `seed/` holds the small public metadata: the speaker registry, current parties, sitting ids and dates, and the index
  state. No transcript text, PDFs or portraits. Refresh it with `uv run python scripts/export_public_seed.py` and commit it
  after indexing more sittings. Official portraits are not shipped, so the public site shows initials instead of photos.
- `app.py` is the entrypoint: public mode on, CPU models, absolute path to the override config.

**Rehearsed locally on 30 Sep 2026** (not yet on Vercel): `python backend/build.py`, then the backend run from `backend/` in a fresh
Python 3.12 environment with only `requirements.txt`, public mode on, against a local Qdrant. `/api/status`, `/api/speakers` and
`/api/parties` worked, the transcript and photo routes returned 404 as intended, real questions were answered, and two
simultaneous questions both succeeded. The service process peaked at **1,582 MB** (Hobby limit: 2 GB).

**Not verified, because it needs your Vercel account** (check these on the first deploy):
1. Services and large functions are **beta and need permission** on your account. The 1.2 GB of models exceeds the 500 MB Python bundle
   limit, so the backend needs [large functions](https://vercel.com/docs/functions/limitations#large-functions-beta) (up to 5 GB);
   set `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` if the project isn't eligible by default.
2. That the backend's build can read `../src` (files outside the service root). If it can't, `build.py` stops with a clear error.
3. That a build can download 1.2 GB, and that memory stays under 2 GB on Vercel's runtime (peak was 1.58 GB here, about 0.4 GB of headroom).
4. On 1 vCPU the retrieval alone takes about 6 s once warm and about 10 to 12 s cold (measured with one CPU thread), before the LLM answers.
5. The in-memory rate limit and daily cap are per function instance, so with several instances running they are looser than configured.

Fallbacks if this doesn't fit: a paid Hugging Face Docker Space, or your own PC behind a tunnel (table below).

## Free-tier limits (measured or read from the provider)

| Service | Limit | Source |
|---|---|---|
| Groq, `qwen/qwen3.8-27b`, free | 30 requests/min, 1,000/day, 8,000 tokens/min, **200,000 tokens/day** | [Groq docs](https://console.groq.com/docs/rate-limits) |
| One question, measured | about 4.1 to 4.2K tokens (3.3 to 3.4K prompt + 0.6 to 0.9K answer) | two real calls |
| So Groq alone allows | about 1 to 2 questions a minute, **about 48 a day**, for the whole site | arithmetic from the two rows above |
| Kilo free models (fallback) | 200 requests/hour **per IP** (your server's IP, shared by all visitors) | [Kilo docs](https://kilo.ai/docs/gateway/models-and-providers) |
| Qdrant Cloud free | 0.5 vCPU, 1 GB RAM, 4 GB disk; suspended after 1 week idle, deleted after 4 weeks | [pricing](https://qdrant.tech/pricing/), [docs](https://qdrant.tech/documentation/cloud/create-cluster/) |
| Vercel Hobby | 100 GB transfer, 1M function invocations a month; **non-commercial use only** (donations are fine) | [fair use](https://vercel.com/docs/limits/fair-use-guidelines) |
| Hugging Face Spaces | **Docker Spaces need a paid plan (PRO, $9/month) to create**; free CPU is 2 vCPU / 16 GB | [docs](https://huggingface.co/docs/hub/spaces-overview) |

`DAILY_CAP` defaults to 400 questions/day. That only holds if the Kilo fallback stays up; on Groq alone the ceiling is about 48.

## Choosing a backend host

| Option | Cost | Notes |
|---|---|---|
| **Your own PC + a tunnel** (for example Cloudflare Tunnel or ngrok) | RM0 | Fastest (uses your GPU), but only while the PC and tunnel are on. A quick tunnel's URL changes each run, and `NEXT_PUBLIC_API_BASE` is baked in at build time, so each new URL means a Vercel redeploy. A stable hostname needs a named tunnel. Run the API with `PUBLIC_MODE=1` and set `ALLOWED_ORIGINS`. Not tested. |
| **Hugging Face Docker Space** | $9/month (PRO) | Always-on and simplest. `deploy/Dockerfile` and `scripts/make_space_bundle.py` are ready. The Docker build is untested. |
| **Vercel Python service** (second service, "large functions" beta) | RM0 | **The chosen path, see above.** Measured: retrieval stack alone peaked at 1,719 MB on one CPU thread; the full service process peaked at 1,582 MB locally. Hobby limit is 2 GB. About 6.4 s of retrieval per question once warm on one thread, before the LLM. Fits only barely and is a beta feature. |
| Oracle Always Free VM | RM0, card needed | Cut in June 2026 from 4 CPU / 24 GB to 2 CPU / 12 GB ([news](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)), not enforced consistently. You run the server and HTTPS. Not tested. |
| Cloud Run | free tier, billing account | Free tier from a search summary: 180,000 vCPU-seconds, 360,000 GiB-seconds, 2M requests/month. Each cold start reloads the models. Whether a card is required was not confirmed. Not tested. |
| Render free | RM0 | 750 hours/month, sleeps after 15 minutes idle, about a 1-minute cold start ([docs](https://render.com/docs/free)). RAM was not stated on the page; the models may not fit. Not tested. |

## Steps

### 1. Qdrant Cloud (you), only for a hosted backend
1. Create a free cluster at cloud.qdrant.io. Copy the cluster URL and create an API key.
2. Push the local index (PowerShell; the keys stay in this shell only). Start with the dry run and check the size:
   ```powershell
   $env:QDRANT_CLOUD_URL = "https://xxxx.cloud.qdrant.io:6333"
   $env:QDRANT_CLOUD_API_KEY = "<key>"
   uv run python scripts/push_qdrant.py --limit 500   # dry run: check the real size per point first
   uv run python scripts/push_qdrant.py               # everything (safe to re-run)
   ```
   It creates the collection with on-disk vectors and int8 quantisation. My local Qdrant folder is 1.5 GB for 69 of 266
   sittings, which extrapolates past the free 4 GB; that folder includes logs and uncompacted data, so check the real size.

### 2. Vercel, both services (you)
1. Commit and push `vercel.json`, `backend/` (app.py, build.py, requirements.txt, seed/) and this change. Review `backend/seed/`
   first: it is metadata only (names, seats, roles, parties, sitting ids), but it is a choice to publish it.
2. On vercel.com import the GitHub repo with **Root Directory = the repository root** (not `frontend`), so the root `vercel.json` and
   its two services apply. Services is a beta: your import screen should show both detected services.
3. Project environment variables (shared by both services):
   - `NEXT_PUBLIC_PUBLIC_MODE` = `1` (frontend, read at build time)
   - `QDRANT_URL` and `QDRANT_API_KEY` (from step 1), `LLM_API_KEY` (your Groq key)
   - optional: `RATE_PER_MINUTE` (default 6), `DAILY_CAP` (default 400; about 48 is what Groq alone can serve), and
     `VERCEL_SUPPORT_LARGE_FUNCTIONS` = `1` if the models make the backend too large.
   - Not needed: `NEXT_PUBLIC_API_BASE`, `ALLOWED_ORIGINS`, `PUBLIC_MODE` and `TANYADEWAN_OVERRIDE` (the entrypoint sets them).
4. Deploy, then open `/api/status` on the deployed URL: it should report 69 sittings and 33,087 chunks. Then ask a question.
A production build of `frontend/` with these settings passes (checked 30 Sep 2026).

### 3. Keep-alive
Set the repo variable `SPACE_URL` to the Vercel URL; `.github/workflows/keepalive.yml` pings `/api/status` every two days,
which also keeps an idle Qdrant Cloud cluster from being suspended.

### Other backend hosts (fallbacks)
`deploy/Dockerfile` and `scripts/make_space_bundle.py` build the same backend as a Docker image (Hugging Face Space or any
container host); set the same env vars plus `PUBLIC_MODE=1`, `ALLOWED_ORIGINS` and `TANYADEWAN_OVERRIDE=config.prod.yaml`.
With a separate host, set `NEXT_PUBLIC_API_BASE` on a frontend-only Vercel project (Root Directory `frontend`, no `vercel.json`).

## Guardrails already in the code
- Per-IP limit (`RATE_PER_MINUTE`) and a site-wide daily cap (`DAILY_CAP`), public mode only. Both answer HTTP 429 with a Malay
  message. In-memory, so they reset when the backend restarts.
- `PUBLIC_MODE=1` removes the full-transcript routes and the "Sidang" pages: the public site shows cited excerpts and
  links to the official PDFs only.
- Off-topic questions return "not found" (reranker gate; the threshold is uncalibrated until the golden set exists).

## Known limits
- CPU retrieval: about 6 s per question on one core, 2.4 to 3.4 s on a 12-core PC (public profile: 5 passages at 192 tokens).
- The int8 CPU embedder is not bit-identical to the Ollama one (cosine about 0.985); top-1 matched on 9 of 9 probe queries.
- Only 69 of 266 sittings are indexed.
