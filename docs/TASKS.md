# Build tasks (work top to bottom)

Budget: **5 hours of coding**. Target times in brackets. After each phase, verify "Done when", tick boxes, and log it in `docs/TIME_LOG.md`.

**Cut order if behind:** Stretch (MCP) → Phase 6 evals down to 3 domains → Wayback first-capture (keep fallback) → editable criteria (presets only) → Phase 7 deploy (demo locally; README still documents Vercel).

---

## Pre-work (human, before the clock — not counted)
- [ ] Keys in `.env`: `GOOGLE_API_KEY`, model IDs from AI Studio, Neon pooled `DATABASE_URL`, LangFuse keys
- [ ] Vercel account linked to GitHub; empty GitHub repo created
- [ ] SaaSquatch free-trial screenshots saved to `docs/screenshots/before-*.png`
- [ ] Review `docs/ICP_PRESETS.md`
- [ ] 5 golden domains + expected facts written into `evals/golden.json`
- [ ] Seed data generated (Claude Code may write `scripts/seed_from_overpass.py` for this; running it is pre-work)

---

## Phase 0 — Scaffold + deploy hello-world [0:00–0:20]
- [x] Monorepo: `/web` (Next.js latest, TS, Tailwind, shadcn/ui), `/api` (uv project, FastAPI), `/data`, `/scripts`, `/evals`
- [x] `GET /api/health` returns `{ok: true, db: true|false}` (checks Neon)
- [x] Next.js home page calls `/api/health` and shows the result
- [x] Dev: Next.js rewrites `/api/*` → `http://localhost:8000` 
- [x] `vercel.json` / project config so Next.js + FastAPI deploy in one Vercel project (check current Vercel docs; fallback: two projects + CORS)
- [x] Deployed to Vercel with env vars set

**Done when:** the live Vercel URL shows `ok: true, db: true`.

## Phase 1 — Data layer + import [0:20–0:40]
- [x] SQLAlchemy async models: `companies, icp_profiles, scans, facts, criterion_results, pages, enrichments` (schema in `docs/PLAN.md`)
- [x] Tables created on startup (no Alembic); `pool_pre_ping=True`
- [x] `scripts/seed_from_overpass.py`: one sequential Overpass query per industry (`craft=hvac` + one more), identifying UA, 30s backoff on 429/406, ~120 rows with a website, writes `data/seed_leads.csv` in SaaSquatch-style columns; ODbL attribution in README
- [x] `POST /api/companies/import` (CSV upload) with dedupe by normalized domain (lowercase, strip scheme, `www.`, path, trailing slash); returns `{inserted, duplicates_skipped}`
- [x] `GET /api/companies`
- [x] Seed the two ICP presets from `docs/ICP_PRESETS.md` (criteria empty until compiled)

**Done when:** importing the seed CSV twice reports duplicates on the second run, and `GET /api/companies` returns the rows.

## Phase 2 — Fetcher + enrichers [0:40–1:10]
- [x] `services/fetcher.py`: `httpx.AsyncClient(follow_redirects=True)`, protego robots check, UA from env, 8s timeout, 500 KB cap, per-host `asyncio.Semaphore(1)` + ~1 rps, trafilatura text capped ~6k chars, `pages` cache with 7-day TTL
- [x] Page planner: home, /about, /team, /careers, /contact (+ sitemap hints), max 6
- [x] Wayback fallback via `https://archive.org/wayback/available` **only** on timeout/5xx/empty text; `via='wayback'`
- [x] Record `reachable` on the company after the first fetch
- [x] `services/enrich.py`: RDAP (`https://rdap.org/domain/{d}`, store registration/expiration dates only) + Wayback first capture; cached in `enrichments`; failures → unknown

**Done when:** a quick script fetching 3 seed domains shows cached pages, a robots-skipped URL is logged, and RDAP dates appear.

## Phase 3 — LangGraph pipeline [1:10–2:15]
- [x] `graph/llm.py`: `ChatGoogleGenerativeAI(temperature=0)` for fast/smart models from env; per-scan `Semaphore(2)`; tenacity backoff on 429/RESOURCE_EXHAUSTED
- [x] `compile_icp`: smart model → 4–8 criteria `{key, label, weight, test, polarity}`; cached by `description_hash`
- [x] `plan_pages` → `Send(fetch_and_extract)` per URL → fast model → `FactList(facts: list[CompanyFact])` with `evidence_quote` ≤200 chars verbatim
- [x] `ground` (`services/grounding.py`): normalize both sides (casefold, collapse whitespace, strip quotes/punctuation) → exact | fuzzy (`rapidfuzz.fuzz.partial_ratio >= 90`) | none
- [x] `merge` → `enrich` → `judge_criteria` (fast model; may only cite grounded facts or return `unknown`)
- [x] `score` (`services/scoring.py`, deterministic): weights of met criteria / weight of known criteria; unknown ≠ 0; return breakdown + coverage %
- [x] `note`: smart model, 4 sentences citing exactly two grounded fact ids; validate ids exist
- [x] Persist scan, facts, criterion_results
- [x] `app/cli.py`: `scan <domain> --icp buybox|sales` prints score, coverage, criteria with quotes

**Done when:** the CLI scan completes in under ~90s on 3 domains, every "met" criterion shows a grounded quote, and nothing ungrounded counts toward the score.

## Phase 4 — API routes [2:15–2:45]
- [x] `GET/POST/PUT /api/icp`, `POST /api/icp/{id}/compile`
- [x] `POST /api/scan/{company_id}?icp_id=` — runs the graph **synchronously** and returns the full result; returns cached result if a scan for (company, icp) exists within 7 days; `maxDuration: 300` for this function
- [x] `GET /api/companies?icp_id=` includes latest score, coverage, top 3 met criteria
- [x] `GET /api/scans/{id}` full detail (criteria, facts, note)
- [x] `GET /api/export.csv?icp_id=` — HubSpot-style company headers (Company name, Company Domain Name, City, State/Region, Industry, Phone Number, Number of Employees) + `fit_score, coverage, met_criteria, outreach_note, evidence_urls`

**Done when:** scanning a company via curl returns criteria with quotes, and the export CSV opens cleanly.

## Phase 5 — Frontend [2:45–3:45]
- [x] `/leads` table (TanStack): name, domain, industry, city, reachable flag, **Fit Score badge**, coverage, criteria chips; sort + filter by score; row checkboxes
- [x] Toolbar: CSV import, ICP selector, **Scan selected** (client-side concurrency 3, per-row spinner → score), Export CSV
- [x] ICP panel: two preset buttons, textarea, **Compile**, editable criteria list with weight inputs, Save
- [x] Right-side drawer: criterion cards (verdict, quote in blockquote, source link, badge **Verified exact / Verified fuzzy / Unverified**), score breakdown bars, facts list, outreach note with Copy
- [x] Empty/loading/error states; no fabricated values ("Unknown" where missing)
- [x] Clean visual hierarchy: consistent badge colors, readable table density

**Done when:** the full flow works in the browser — pick preset → compile → scan 3 rows → open drawer → copy note → export.

## Phase 6 — Observability + evals [3:45–4:10]
- [x] LangFuse LangChain `CallbackHandler` on the graph with tags `scan_id, domain, icp_id`
- [x] `evals/run.py`: scans golden domains; prints grounding rates (exact/fuzzy/none), criterion agreement vs expected, avg latency; writes `evals/results.md`

**Done when:** a trace is visible in LangFuse and `evals/results.md` exists.

## Stretch — MCP server [only if ahead at 4:00]
- [x] `api/app/mcp_server.py` (FastMCP, stdio, local): `scan_company(domain, icp_id)`, `list_icps()`; instructions in README

## Phase 7 — Deploy + pre-warm [4:10–4:30]
- [ ] Redeploy; env vars verified on Vercel
- [ ] Import seed CSV on production; compile both presets; pre-warm ~20 leads per preset (respect Gemini limits)
- [ ] Smoke test the live URL end to end

**Done when:** the live demo loads ranked leads instantly and one fresh scan works.

## Phase 8 — README + submission assets [4:30–5:00]
- [ ] `README.md`: What & why · Live demo + video links · Screenshots (before/after) · Architecture diagram + exact stack · Hosting (serverless on Vercel; why not static/containers) · Data sources & ethics · ICP compilation & scoring formula · Grounding & evals (results table) · Dedupe & validation · Performance & caching · Setup · Deployment steps · Cost & limits (Vercel Hobby, Gemini free tier) · Cut scope & roadmap · Time log
- [ ] After screenshots in `docs/screenshots/`
- [ ] `docs/TIME_LOG.md` complete and honest

**Done when:** a stranger could clone, set `.env`, and run it from the README alone.
