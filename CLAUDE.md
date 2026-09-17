# ICP Signal Scanner (Caprae Capital take-home)

## What this is
A 5-hour take-home for Caprae Capital's Full Stack Developer role: add an **"AI Web Scanner"** feature to their lead-gen tool **SaaSquatch Leads** (saasquatchleads.com).

Users import leads, describe their ideal customer (ICP) in plain English, and the app:
1. compiles the ICP into 4–8 weighted, editable criteria
2. reads each company's public website + RDAP + Wayback
3. judges every criterion with a **verbatim, source-linked quote** (ungrounded = "unverified", never scored)
4. ranks leads, writes a grounded outreach note, exports a HubSpot-shaped CSV

Presets: **Search-fund buy-box** (Caprae's core users: acquisition entrepreneurs) and **B2B sales ICP** (SaaSquatch's sales-team users).

## Read first
- `docs/TASKS.md` — ordered build phases with acceptance criteria. **Work phase by phase, tick boxes as you go.**
- `docs/PLAN.md` — full product/architecture plan (source of truth for design decisions)
- `docs/REQUIREMENTS.md` — what Caprae grades and what must be submitted
- `docs/ICP_PRESETS.md` — the two preset ICP descriptions

## Stack (all free tiers — do not add paid services)
- **Web:** latest Next.js App Router, TypeScript, Tailwind, shadcn/ui, TanStack Table → `/web`
- **API:** Python 3.12, FastAPI, LangGraph, langchain-google-genai, httpx, trafilatura, protego, tenacity, rapidfuzz, SQLAlchemy 2 async + asyncpg, pydantic v2, langfuse → `/api` (use `uv`)
- **DB:** Neon Postgres (pooled URL, `pool_pre_ping=True`)
- **LLM:** Gemini free tier. `GEMINI_FAST_MODEL` (Flash-Lite) for extract/judge, `GEMINI_SMART_MODEL` (Flash) for ICP compile + outreach note. Never hard-code model IDs.
- **Hosting:** one Vercel project (Hobby): Next.js + FastAPI on Vercel's Python runtime, same domain. Check current Vercel docs for combining them (Services / Python runtime); fall back to two Vercel projects + CORS if needed.
- **Tracing:** LangFuse Cloud

## Hard constraints
- **Vercel Hobby:** functions max 300s; nothing runs after the response. **No BackgroundTasks, queues, SSE or polling.** A scan is one synchronous request per company; the browser runs ≤3 in parallel.
- **Gemini free tier:** ≤2 concurrent LLM calls per scan; tenacity exponential backoff on 429 / RESOURCE_EXHAUSTED. Send only public website text to the model.
- **Ethics:** honor robots.txt (protego); identifying User-Agent; 1 req/s per host; ≤6 pages per site; never fetch LinkedIn or Google Maps; **no Google News RSS** (robots-disallowed). Wayback fallback **only** on timeout/5xx/empty text — never on 403/429 or robots disallow. Store only RDAP event dates, no registrant data.
- **No fabricated data** anywhere in the UI or seed data. Unknown stays "Unknown".
- Structured output must use a top-level Pydantic object (wrap lists).
- `httpx.AsyncClient(follow_redirects=True)`.
- No Docker, no auth, no Playwright scraping, no MX validation (out of scope).

## Conventions
- Monorepo: `/web`, `/api`, `/data`, `/scripts`, `/evals`, `/docs`
- API routes all under `/api/*`
- Keep the Python bundle lean (Vercel 500 MB limit) — no heavy unused deps
- Small, readable modules: `api/app/services/` (fetcher, enrich, grounding, scoring), `api/app/graph/` (LangGraph nodes), `api/app/routes/`
- Secrets only in `.env` (never committed); keep `.env.example` current
- Prefer deterministic code over LLM calls wherever possible (scoring, dedupe, grounding)

## Commands (keep this section updated as you build)
- Web dev: `cd web && npm run dev`
- API dev: `cd api && uv run uvicorn app.main:app --reload --port 8000` (Next.js proxies `/api` to it in dev)
- CLI scan: `cd api && uv run python -m app.cli scan <domain> --icp buybox`
- Evals: `cd api && uv run python ../evals/run.py`
- Seed: `uv run python scripts/seed_from_overpass.py`

## Working rules for Claude Code
- The human has a **strict 5-hour coding budget**. Stay in scope; if something isn't in `docs/TASKS.md`, ask before adding it.
- If a phase is overrunning, follow the cut order in `docs/TASKS.md` instead of pushing through.
- After each phase: run it, verify the "Done when" checks, tick the boxes, and append a line to `docs/TIME_LOG.md` (phase, what was done, anything cut).
- Deploy a hello-world to Vercel in Phase 0, before building features.
