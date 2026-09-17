# Final Build Plan: ICP Signal Scanner for SaaSquatch Leads

*v3: all-free stack (Vercel + Neon + Gemini). Replaces the Railway/Claude version.*

> **For Claude Code:** follow `docs/TASKS.md` for build order and `CLAUDE.md` for constraints. The kickoff prompt at the bottom of this file is kept for reference only.

## What we're building

The "AI Web Scanner" that SaaSquatch lists as *Soon*: import leads → describe your ideal customer in plain English → the scanner reads each company's website and public records → scores every lead against your criteria, with a verbatim quote and source link for each point → outreach note + CRM export.

**Differentiator:** user-defined, evidence-grounded criteria. No other public submission has this, and LeadRadar lists fixed weights as a limitation. Two presets: **Search-fund buy-box** (Caprae's core market; lead the demo with it) and **B2B sales ICP** (SaaSquatch's 2,000+ sales teams).

## Stack (total hosting cost: $0)

| Part | Choice | Cost |
|---|---|---|
| Frontend | Next.js (latest, App Router, TS, Tailwind, shadcn/ui, TanStack Table) on **Vercel** | Free (Hobby) |
| Backend | **FastAPI + LangGraph (Python 3.12) on Vercel** Python runtime, same project as the frontend | Free (Hobby) |
| Database / cache | **Neon Postgres** (pooled connection) | Free |
| LLM | **Gemini API free tier** via `langchain-google-genai`: Flash-Lite for extraction and judging, Flash for ICP compile and outreach note | Free |
| Tracing / evals | **LangFuse Cloud** Hobby | Free |
| Data sources | Company websites (robots.txt honored), RDAP, Wayback Machine | Free |

**Vercel constraints we design around:**
- Hobby functions run at most **300s** per request. One company scan (~30–60s) fits.
- **Nothing keeps running after the response**, so there are no background jobs. Each scan is a synchronous request with `maxDuration = 300`, and the browser runs 2–3 scans in parallel with a per-row spinner.
- Hobby is non-commercial use only, which covers a take-home demo.

## Scope

**In**
- CSV import with domain-normalized dedupe + `reachable` flag
- ~120 seed leads across 2 industries (Overpass script, run before the clock, disclosed)
- Plain-English ICP → compiled into 4–8 editable weighted criteria (cached by text hash)
- Fetch ≤6 pages/site (robots.txt honored) → fact extraction → grounding (normalized exact match, then fuzzy) → criteria judging with quotes → deterministic score + coverage %
- Enrichment: RDAP registration date, Wayback first capture; Wayback fallback only on timeout/5xx/empty page
- Leads table, ICP panel, scan drawer with evidence cards, score breakdown, outreach note
- HubSpot-shaped CSV export
- LangFuse traces + 3–5 domain eval script
- Optional: local FastMCP server (stdio) exposing `scan_company`

**Out:** Google News RSS (robots.txt disallows it), Maps reviews, SSE/polling/background jobs, Playwright, auth, MX validation, live discovery in-app, Docker.

## Pre-work (before the 5-hour clock)

- Accounts/keys: **Google AI Studio** (Gemini API key; check your free-tier limits and exact current Flash / Flash-Lite model IDs there), **Neon**, **Vercel**, **LangFuse Cloud**, **GitHub** repo
- Sign up for the SaaSquatch free trial; screenshot the Companies table for the README "before" section
- Write the two preset ICP descriptions
- Pick 5 golden domains and note the facts you expect the scanner to find
- Run the Overpass seed script (one sequential query per industry, identifying User-Agent, 30s backoff on 429)

## Schedule

| Block | Work |
|---|---|
| 0:00–0:20 | Scaffold via Claude Code; deploy hello-world (Next.js + FastAPI) to Vercel with Neon connected; load seed CSV |
| 0:20–0:55 | Fetcher: httpx (follow_redirects), protego, trafilatura, page cache, restricted Wayback fallback |
| 0:55–1:10 | RDAP + Wayback enrichers, cached |
| 1:10–2:15 | Graph: compile_icp → plan_pages → Send(extract) → ground → merge → enrich → judge_criteria → score → note; CLI test on 3 domains |
| 2:15–2:45 | API routes: import+dedupe, companies, icp, scan (synchronous), export |
| 2:45–3:45 | Frontend: leads table with per-row scan state, ICP panel (textarea + presets + editable criteria), drawer, evidence cards, score bars, note |
| 3:45–4:10 | LangFuse handler, evals/run.py, (optional) FastMCP |
| 4:10–4:30 | Redeploy, pre-warm 20 leads, smoke-test the live URL |
| 4:30–5:00 | README, diagram, ethics section, record video |

**Cut first if behind:** FastMCP → eval script down to 3 domains → Wayback first-capture (keep the fallback) → editable criteria (keep presets only) → skip deployment and demo locally (README still documents the Vercel setup).

## Architecture

```
 Browser
   Leads table / ICP panel / Scan drawer
   (runs 2-3 scans in parallel, one request per company)
        |
        v   same Vercel project, same domain (no CORS)
 +---------------------------------------------------------+
 | Vercel                                                  |
 |  Next.js frontend        FastAPI (Python function,      |
 |                          maxDuration 300s)              |
 |                           /api/companies /api/icp       |
 |                           /api/scan/{id} /api/export    |
 +---------------------------------------------------------+
        |                                  |
        v  LangGraph                       +--> LangFuse (traces, evals)
  compile_icp -> plan_pages -> [fetch+extract xN] -> ground -> merge
             -> enrich -> judge_criteria -> score -> note
        |                                   |
   company site (robots.txt,           RDAP (registration date)
   1 rps/host, 7-day cache)            Wayback (first capture, fallback)
        |
        v
 Neon Postgres (pooled): companies, icp_profiles, scans, facts,
                         criterion_results, pages, enrichments
        ^
 Gemini Flash-Lite (extract, judge)  /  Gemini Flash (compile ICP, outreach note)
```

## Key gotchas

- **Vercel:** no background tasks; scan inside the request. Per-host rate limiting is per instance, which is fine at demo scale. Keep the Python bundle lean.
- **Gemini free tier:** limit LLM concurrency (semaphore of 2 per scan, 2–3 scans at once from the UI); tenacity retry with backoff on 429 / RESOURCE_EXHAUSTED; pre-warm the cache before recording. Free-tier inputs may be used by Google, so send only public website text.
- **Structured output:** use a top-level Pydantic object (wrap lists) with `with_structured_output`.
- `httpx.AsyncClient(follow_redirects=True)`: rdap.org redirects and allows 10 requests per 10s; store only event dates, never registrant data.
- **Grounding:** casefold, collapse whitespace and strip punctuation on both sides; fall back to `rapidfuzz.partial_ratio >= 90`; store the state as exact | fuzzy | none.
- **Wayback:** never use it when a site blocks you (403/429) or robots.txt disallows the page.
- **Neon** suspends after 5 min idle, so use the pooled URL and `pool_pre_ping=True`.
- **Demo:** pre-warm; do one live scan on a known-good domain in the video.

## Video (2 min)

- 0:00–0:15 Problem: opaque AI score, N/A revenue, one-size-fits-all ranking
- 0:15–0:45 Demo: pick "Search-fund buy-box", tweak a criterion, scan, open the top lead's evidence
- 0:45–1:00 Switch to "B2B sales ICP": same leads re-ranked; serves both audiences
- 1:00–1:20 Trust: grounded quotes, unverified states, robots.txt, LangFuse trace
- 1:20–1:40 Workflow: outreach note, HubSpot export (MCP if built)
- 1:40–2:00 Architecture: serverless on Vercel + Neon + Gemini, $0 hosting; what's next

## README outline

What & why · Live demo + video · Screenshots (before/after) · Architecture + exact stack · Hosting: serverless on Vercel, why not static/containers · Data sources & ethics · ICP compilation & scoring · Grounding & evals (results) · Dedupe & validation · Performance & caching · Setup · Deployment · Cost & limits (Vercel Hobby, Gemini free tier) · Cut scope & roadmap · Time log

## Kickoff prompt for Claude Code

```
You are scaffolding a 5-hour take-home: "ICP Signal Scanner", an AI Web Scanner feature for a B2B lead-gen tool (SaaSquatch Leads) used by acquisition entrepreneurs and B2B sales teams. Users describe their ideal customer in plain English; the app compiles it into weighted criteria, scans each lead's public website and records, and scores every criterion with a verbatim, source-linked quote.

HOSTING: everything deploys to ONE Vercel project on the free Hobby plan: Next.js frontend + FastAPI backend on Vercel's Python runtime, same domain. Follow Vercel's current docs for combining a Next.js frontend with a FastAPI backend in one project (Vercel "Services" / Python runtime). If that proves problematic, fall back to two Vercel projects (web and api) with CORS. Constraints: functions max 300s, nothing runs after the response is sent (no BackgroundTasks, no queues), no Docker. Database is Neon Postgres. LLM is Google Gemini via langchain-google-genai.

Repo layout:
/web  (latest Next.js App Router, TypeScript, Tailwind, shadcn/ui, TanStack Table)
/api  (Python 3.12, FastAPI, LangGraph, langchain-google-genai, httpx, trafilatura, protego, tenacity, rapidfuzz, SQLAlchemy 2 async + asyncpg, pydantic v2, langfuse)
/data/seed_leads.csv, /scripts/seed_from_overpass.py, /evals/golden.json, /evals/run.py, vercel.json, .env.example, README.md
Optional last: /api/app/mcp_server.py (FastMCP, stdio, run locally) exposing scan_company(domain, icp_id) and list_icps().

DB (DATABASE_URL = Neon pooled URL; create_async_engine(..., pool_pre_ping=True); create tables on first request / startup, no Alembic):
companies(id, domain unique, name, industry, city, state, employee_range, revenue_estimate, phone, linkedin_url, source, reachable bool null, created_at)
icp_profiles(id, name, description_text, description_hash, criteria jsonb)  -- criteria = [{key, label, weight, test, polarity}]
scans(id, company_id, icp_id, status, score, coverage, outreach_note, model_versions jsonb, pages_fetched, fallback_used, started_at, finished_at, error)
facts(id, scan_id, category, fact, evidence_quote, source_url, confidence, grounding)  -- grounding in exact|fuzzy|none
criterion_results(id, scan_id, criterion_key, verdict, evidence_quote, source_url, grounding, confidence)  -- verdict in met|not_met|unknown
pages(url pk, domain, status_code, text, content_hash, fetched_at, via)  -- via in live|wayback
enrichments(domain, kind, payload jsonb, fetched_at, pk(domain,kind))  -- kind in rdap|wayback

Seed two icp_profiles presets: "Search-fund buy-box" (owner-operated, 20+ years in business, succession cues, small team, dated web presence) and "B2B sales ICP" (growing team/hiring, modern tech stack, multiple locations, clear buyer contact).

Models: read GEMINI_FAST_MODEL (default: current Gemini Flash-Lite ID) and GEMINI_SMART_MODEL (default: current Gemini Flash ID) from env; use ChatGoogleGenerativeAI(temperature=0). Structured output must use a top-level Pydantic object (wrap lists). Limit concurrent LLM calls per scan with asyncio.Semaphore(2); tenacity retry with exponential backoff on 429 / RESOURCE_EXHAUSTED.

LangGraph graph in api/app/graph/:
compile_icp -> plan_pages -> Send(fetch_and_extract per URL) -> ground -> merge -> enrich -> judge_criteria -> score -> note
- compile_icp: SMART model turns description_text into 4-8 criteria; cache by description_hash; user edits are saved to criteria.
- plan_pages: max 6 URLs (home, /about, /team, /careers, /contact, plus sitemap hint).
- fetch: httpx.AsyncClient(follow_redirects=True), honor robots.txt via protego, UA "ICPSignalScanner/0.1 (+contact email)", 8s timeout, 500KB cap, per-host asyncio.Semaphore(1), trafilatura text capped at ~6k chars, cache in pages with 7-day TTL. Fall back to https://archive.org/wayback/available ONLY on timeout, 5xx, or empty extracted text; NEVER when robots.txt disallows or on 403/429. Set via='wayback'.
- extract: FAST model, structured output FactList(facts: list[CompanyFact(category, fact, evidence_quote <=200 chars verbatim, source_url, confidence)]).
- ground: normalize both sides (casefold, collapse whitespace, strip quotes/punctuation); exact substring -> 'exact'; else rapidfuzz.fuzz.partial_ratio >= 90 -> 'fuzzy'; else 'none'.
- enrich: RDAP https://rdap.org/domain/{domain} (respect 10 req/10s, store only event dates, no registrant data) and Wayback first capture; cache in enrichments; failures = unknown.
- judge_criteria: FAST model judges each criterion using only grounded facts + enrichments; must cite a grounded fact's quote or return unknown.
- score: deterministic sum of weights over met criteria / total weight of known criteria; unknown is not zero; return breakdown and coverage %.
- note: SMART model writes a 4-sentence outreach note citing exactly two grounded facts by id; validate that the ids exist.
- Wire the langfuse LangChain CallbackHandler with tags scan_id, domain, icp_id.

API (all under /api):
POST /api/companies/import (CSV; dedupe by normalized domain: lowercase, strip scheme, www, path, trailing slash)
GET  /api/companies (latest score, coverage, top 3 met criteria per company for a given icp_id)
GET/POST/PUT /api/icp, POST /api/icp/{id}/compile
POST /api/scan/{company_id}?icp_id=  -> runs the whole graph synchronously inside the request and returns the full result (set maxDuration 300 for this function in vercel.json). If a fresh scan for (company, icp) exists within 7 days, return it from the DB immediately.
GET  /api/export.csv?icp_id=  (HubSpot-style company headers + fit_score, coverage, met_criteria, outreach_note, evidence_urls)

Web: /leads page with table (score badge, coverage, criteria chips, reachable flag, sort/filter, row checkboxes, "Scan selected" that calls POST /api/scan/{id} for each selected company with a client-side concurrency limit of 3, per-row spinner then score, Export), ICP panel (textarea, two preset buttons, editable criteria list with weight inputs, Compile), right-side drawer showing criterion cards (verdict, quote, source link, exact/fuzzy/unverified badge), score breakdown bars, facts list, outreach note with Copy.

Also: scripts/seed_from_overpass.py (single sequential Overpass query per industry, identifying User-Agent, 30s backoff on 429/406, ~120 rows across craft=hvac and one other category, ODbL attribution), evals/run.py (scan golden domains, print fact grounding rates exact/fuzzy/none and criterion agreement), .env.example (GOOGLE_API_KEY, GEMINI_FAST_MODEL, GEMINI_SMART_MODEL, DATABASE_URL, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST), README skeleton with sections: What/Why, Architecture, Hosting (serverless on Vercel), Data sources & ethics, ICP & scoring, Grounding & evals, Dedupe & validation, Setup, Deploy, Cost & limits, Cut scope.

Start by printing the file tree and a 10-line plan. First make a minimal hello-world (Next.js page calling a FastAPI /api/health route) that deploys to Vercel, then implement the api, then the web. Local dev: `npm run dev` for web and `uvicorn app.main:app --reload` for api (proxy /api to it in dev). Ask no questions; make sensible defaults.
```
