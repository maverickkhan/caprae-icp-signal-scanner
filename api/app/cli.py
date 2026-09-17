"""CLI: `uv run python -m app.cli fetch <domain>` (Phase 2) / `scan <domain> --icp buybox|sales` (Phase 3)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time


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


def main() -> None:
    ap = argparse.ArgumentParser(prog="icp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="plan + fetch pages and enrichments for a domain")
    f.add_argument("domains", nargs="+")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    async def _run() -> None:
        if args.cmd == "fetch":
            for d in args.domains:
                await _fetch(d)
        from app.db import get_engine

        await get_engine().dispose()

    asyncio.run(_run())  # one loop for everything: the async engine is bound to it


if __name__ == "__main__":
    main()
