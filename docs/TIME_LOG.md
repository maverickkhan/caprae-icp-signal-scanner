# Time log (5-hour budget)

| Phase | Start | End | Notes / cuts |
|---|---|---|---|
| 0 Scaffold + deploy | 17:46 | 17:56 | Opus 5 (main) scaffolded web/api, vercel.json (Services), deployed to Vercel; Fable reviewed plan (NullPool on Vercel, pgbouncer statement_cache_size=0, connect timeout, drop `functions` key). Live health shows db:false — blocked on `.env` (pre-work) for DATABASE_URL. |
