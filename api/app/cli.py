"""CLI: `uv run python -m app.cli scan <domain> --icp buybox|sales [--force]` / `fetch <domain...>`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import warnings

warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")


async def _fetch(domain: str) -> None:
    from app.db import ensure_schema
    from app.services.enrich import enrich
    from app.services.fetcher import fetch_page, make_client
    from app.services.planner import plan_pages

    await ensure_schema()
    t0 = time.perf_counter()
    async with make_client() as client:
        plan = await plan_pages(client, domain)
        print(f"\n== {domain}  home: {plan.home.outcome} status={plan.home.status_code} via={plan.home.via} cached={plan.home.cached}")
        for url in plan.urls:
            r = plan.home if url == plan.home_url else await fetch_page(client, domain, url)
            print(f"  [{r.outcome:9}] {r.status_code!s:4} via={r.via:7} cached={r.cached!s:5} {len(r.text):5} chars  {url}")
        e = await enrich(client, domain)
        print(f"  rdap: {e['rdap']}")
        print(f"  wayback: {e['wayback']}")
    print(f"  took {time.perf_counter() - t0:.1f}s")


async def _scan(domain: str, icp_alias: str, force: bool) -> None:
    from sqlalchemy import select

    from app.db import ensure_schema, get_session_factory
    from app.graph.run import run_scan
    from app.models import Company, IcpProfile
    from app.presets import PRESET_ALIASES
    from app.services.dedupe import normalize_domain

    await ensure_schema()
    dom = normalize_domain(domain) or domain
    async with get_session_factory()() as db:
        company = (await db.scalars(select(Company).where(Company.domain == dom))).first()
        if company is None:
            company = Company(domain=dom, name=dom, source="cli")
            db.add(company)
            await db.commit()
            await db.refresh(company)
        icp_name = PRESET_ALIASES.get(icp_alias, icp_alias)
        icp = (await db.scalars(select(IcpProfile).where(IcpProfile.name == icp_name))).first()
        if icp is None:
            raise SystemExit(f"unknown ICP {icp_alias!r}; use buybox|sales or a profile name")
        company_id, icp_id = company.id, icp.id

    t0 = time.perf_counter()
    d = await run_scan(company_id, icp_id, force=force)
    took = time.perf_counter() - t0
    print(f"\n== {dom}  ICP: {d['icp_name']}  status={d['status']}  score={d['score']}  coverage={d['coverage']}%  pages={d['pages_fetched']}  wayback_fallback={d['fallback_used']}  {took:.1f}s")
    if d.get("error"):
        print(f"  ERROR: {d['error']}")
    for c in d["criteria"]:
        mark = {"met": "MET    ", "not_met": "NOT MET", "unknown": "UNKNOWN"}[c["verdict"]]
        print(f"  [{mark}] w{c['weight']} {c['polarity'][:3]} {c['label']}")
        if c["evidence_quote"]:
            print(f"           {c['grounding']:6} \"{c['evidence_quote'][:110]}\"  <{c['source_url']}>")
    print(f"  facts: {len(d['facts'])} ({sum(1 for f in d['facts'] if f['grounding'] != 'none')} verified)")
    for f in d["facts"][:12]:
        print(f"    {f['id']:2} {f['grounding']:6} [{f['category']}] {f['fact'][:90]}")
    print(f"  note ({d.get('note_status')}): {d['outreach_note']}")
    print(f"  timings: {d.get('timings')}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="icp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="plan + fetch pages and enrichments for a domain")
    f.add_argument("domains", nargs="+")
    s = sub.add_parser("scan", help="run the full scan graph for a domain")
    s.add_argument("domains", nargs="+")
    s.add_argument("--icp", default="buybox", help="buybox | sales | <profile name>")
    s.add_argument("--force", action="store_true", help="ignore the 7-day cached scan")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "trafilatura", "google_genai", "langchain"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    async def _run() -> None:
        try:
            if args.cmd == "fetch":
                for d in args.domains:
                    await _fetch(d)
            elif args.cmd == "scan":
                for d in args.domains:
                    await _scan(d, args.icp, args.force)
        finally:
            from app.db import get_engine

            await get_engine().dispose()

    asyncio.run(_run())  # one loop for everything: the async engine is bound to it


if __name__ == "__main__":
    main()
