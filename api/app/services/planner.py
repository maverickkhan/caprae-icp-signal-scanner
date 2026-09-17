"""Pick <=6 URLs per site: home + about/team/careers/contact-style pages found on the home page (or sitemap)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from app.db import get_session_factory
from app.models import Page
from app.services.fetcher import CACHE_TTL, FetchResult, fetch_page, record_reachable, robots_allowed

log = logging.getLogger("icp.planner")

MAX_PAGES = 6

# category -> path keywords (first match wins per category, one URL per category)
_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("about", ("about", "who-we-are", "our-story", "history", "our-company", "company")),
    ("team", ("team", "staff", "our-people", "leadership", "meet-", "owner", "founder")),
    ("careers", ("career", "jobs", "employment", "join-our", "hiring", "now-hiring", "work-with-us")),
    ("contact", ("contact", "locations", "service-area", "areas-we-serve")),
    ("services", ("services", "what-we-do", "financing", "reviews", "testimonials")),
]
_GUESSES = {"about": "/about", "team": "/team", "careers": "/careers", "contact": "/contact"}
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_ASSET_RE = re.compile(r"\.(xml|json|webmanifest|pdf|jpe?g|png|gif|svg|webp|css|js|php|ico|mp4|zip)$|/(wp-|xmlrpc|feed|tag/|category/|page/\d|cdn-cgi)", re.I)


@dataclass
class Plan:
    domain: str
    home: FetchResult
    urls: list[str]  # includes home url first
    home_url: str


def _pick(links: list[str], have: set[str]) -> list[str]:
    picked: list[str] = []
    for cat, kws in _CATEGORIES:
        for u in links:
            path = urlsplit(u).path.lower()
            if path in ("", "/") or u in have or u in picked:
                continue
            if any(k in path for k in kws) and len(path) < 80:
                picked.append(u)
                break
    return picked


async def _cached_urls(domain: str) -> list[str]:
    cutoff = datetime.now(timezone.utc) - CACHE_TTL
    async with get_session_factory()() as s:
        rows = await s.execute(
            select(Page.url).where(Page.domain == domain, Page.fetched_at >= cutoff, Page.text.isnot(None)).order_by(Page.fetched_at)
        )
        return [r[0] for r in rows.all() if r[0]]


async def _sitemap_links(client: httpx.AsyncClient, base: str) -> list[str]:
    url = base.rstrip("/") + "/sitemap.xml"
    try:
        if not await robots_allowed(client, url):
            return []
        r = await client.get(url)
        if r.status_code != 200 or "xml" not in r.headers.get("content-type", "") and "<urlset" not in r.text[:500]:
            return []
        host = urlsplit(base).netloc.removeprefix("www.")
        return [u for u in _LOC_RE.findall(r.text[:300_000]) if urlsplit(u).netloc.removeprefix("www.") == host][:300]
    except Exception:  # noqa: BLE001
        return []


async def plan_pages(client: httpx.AsyncClient, domain: str) -> Plan:
    # 1) Reuse a recent crawl of this domain (cache hit => zero network).
    cached = await _cached_urls(domain)
    home_candidates = [u for u in cached if urlsplit(u).path in ("", "/")]
    if home_candidates and len(cached) >= 2:
        home_url = home_candidates[0]
        home = await fetch_page(client, domain, home_url)
        if home.usable:
            others = [u for u in cached if u != home_url][: MAX_PAGES - 1]
            return Plan(domain=domain, home=home, urls=[home_url, *others], home_url=home_url)

    # 2) Fetch home live: https first, plain http only on connection failure.
    home_url = f"https://{domain}/"
    home = await fetch_page(client, domain, home_url)
    if home.outcome in ("error",) and home.status_code is None:
        alt = f"http://{domain}/"
        alt_res = await fetch_page(client, domain, alt)
        if alt_res.status_code is not None or alt_res.usable:
            home, home_url = alt_res, alt
    await record_reachable(domain, home)

    if not home.usable:
        return Plan(domain=domain, home=home, urls=[home_url], home_url=home_url)
    if home.cached and not home.links:
        # Cache stores text only; one live fetch of the home page recovers the nav links.
        live = await fetch_page(client, domain, home_url, use_cache=False)
        if live.links:
            home.links = live.links

    base = f"{urlsplit(home_url).scheme}://{urlsplit(home_url).netloc}"
    have = {home_url}
    links = [u for u in home.links if not _ASSET_RE.search(u)]
    picked = _pick(links, have)
    if len(picked) < 3:
        picked += [u for u in _pick(await _sitemap_links(client, base), have | set(picked)) if u not in picked]
    if len(picked) < MAX_PAGES - 1:
        # Fill with the site's own first links (nav order) rather than guessing paths that 404.
        for u in links:
            if len(picked) >= MAX_PAGES - 1:
                break
            if u not in have and u not in picked and urlsplit(u).path not in ("", "/"):
                picked.append(u)
    if not picked:
        picked = [base + p for p in _GUESSES.values()]
    urls = [home_url, *picked][:MAX_PAGES]
    log.info("plan %s: %s", domain, urls)
    return Plan(domain=domain, home=home, urls=urls, home_url=home_url)
