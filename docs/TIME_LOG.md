# Time log (5-hour budget)

| Phase | Start | End | Notes / cuts |
|---|---|---|---|
| 0 Scaffold + deploy | 17:46 | 18:10 | Opus 5 (main) scaffolded web/api, vercel.json (Services), deployed to Vercel; Fable reviewed plan (NullPool on Vercel, pgbouncer statement_cache_size=0, connect timeout, drop `functions` key). `.env` supplied ~18:05; pushed env vars to Vercel via CLI; live health now db:true. Picked model IDs from AI Studio model list: fast=gemini-3.5-flash-lite, smart=gemini-3.8-flash. |
| 1 Data layer + import | 18:10 | 18:32 | Opus 5 (main): 7 SQLAlchemy models, create_all + preset seed on startup/first request, CSV import with normalized-domain dedupe (ON CONFLICT DO NOTHING), Overpass seed script (stdlib). DFW bbox gave 38 rows → widened to Texas: 130 rows (65 HVAC, 65 plumbing). Import twice → 130 inserted / 130 dupes. |
