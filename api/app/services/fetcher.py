"""Polite page fetcher: robots.txt (protego), 1 req/s per host, size cap, pages cache, restricted Wayback fallback."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

import httpx
from protego import Protego
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import get_session_factory
from app.models import Company, Page
from app.services import wayback_gate
from app.services.textextract import content_hash, extract_text

log = logging.getLogger("icp.fetcher")

TIMEOUT_S = 8.0
MAX_BYTES = 500_000
TEXT_CAP = 6000
CACHE_TTL = timedelta(days=7)
MIN_TEXT_CHARS = 80  # below this we treat the page as "empty" (fallback-eligible)

_HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.I)
# Never fetched, regardless of robots.txt (project rule: no LinkedIn, no Google Maps).
DENY_HOSTS = ("linkedin.com", "google.com", "maps.google.com", "goo.gl", "facebook.com", "instagram.com", "x.com", "twitter.com")

# Per-process politeness state (per instance on Vercel, which is fine at demo scale).
_host_locks: dict[str, asyncio.Lock] = {}
_host_last: dict[str, float] = {}
_robots_cache: dict[str, Protego | None] = {}


@dataclass
class FetchResult:
    url: str
    domain: str
    status_code: int | None = None
    text: str = ""
    via: str = "live"  # live | wayback
    outcome: str = "error"  # ok | cached | robots | blocked | not_found | timeout | empty | error
    links: list[str] = field(default_factory=list)
    cached: bool = False

    @property
    def usable(self) -> bool:
        return bool(self.text) and self.outcome in ("ok", "cached")


def _client() -> httpx.AsyncClient:
    ua = get_settings().scanner_user_agent
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(TIMEOUT_S, connect=TIMEOUT_S),
        headers={"User-Agent": ua, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"},
        max_redirects=5,
    )


async def _polite(host: str) -> None:
    """Serialize requests per host and keep >=1s between them."""
    lock = _host_locks.setdefault(host, asyncio.Lock())
    await lock.acquire()
    wait = 1.0 - (time.monotonic() - _host_last.get(host, 0.0))
    if wait > 0:
        await asyncio.sleep(wait)


def _release(host: str) -> None:
    _host_last[host] = time.monotonic()
    _host_locks[host].release()


async def _robots(client: httpx.AsyncClient, url: str) -> Protego | None:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin in _robots_cache:
        return _robots_cache[origin]
    rp: Protego | None = None
    try:
        await _polite(parts.netloc)
        try:
            r = await client.get(origin + "/robots.txt")
        finally:
            _release(parts.netloc)
        if r.status_code == 200 and r.text:
            rp = Protego.parse(r.text[:200_000])
        elif r.status_code in (401, 403):
            # Unreadable robots.txt: be conservative and treat the site as disallowed.
            rp = Protego.parse("User-agent: *\nDisallow: /\n")
    except Exception as e:  # noqa: BLE001 - no robots.txt reachable => allowed
        log.info("robots.txt fetch failed for %s: %s", origin, e)
    _robots_cache[origin] = rp
    return rp


async def robots_allowed(client: httpx.AsyncClient, url: str) -> bool:
    rp = await _robots(client, url)
    if rp is None:
        return True
    ua = get_settings().scanner_user_agent.split("/")[0]
    return rp.can_fetch(url, ua)


async def _get_capped(client: httpx.AsyncClient, url: str) -> tuple[int, str, str]:
    """GET with a byte cap. Returns (status, html, final_url)."""
    host = urlsplit(url).netloc
    await _polite(host)
    try:
        async with client.stream("GET", url) as r:
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and "html" not in ctype and "xml" not in ctype and "text" not in ctype:
                return r.status_code, "", str(r.url)
            chunks: list[bytes] = []
            size = 0
            async for chunk in r.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_BYTES:
                    break
            raw = b"".join(chunks)[:MAX_BYTES]
            enc = r.encoding or "utf-8"
            try:
                html = raw.decode(enc, errors="replace")
            except LookupError:
                html = raw.decode("utf-8", errors="replace")
            return r.status_code, html, str(r.url)
    finally:
        _release(host)


def _internal_links(html: str, base_url: str) -> list[str]:
    base_host = urlsplit(base_url).netloc.lower().removeprefix("www.")
    out: list[str] = []
    seen: set[str] = set()
    for href in _HREF_RE.findall(html):
        href = href.strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absu = urljoin(base_url, href)
        p = urlsplit(absu)
        if p.scheme not in ("http", "https"):
            continue
        if p.netloc.lower().removeprefix("www.") != base_host:
            continue
        path = p.path or "/"
        if len(path) > 1:
            path = path.rstrip("/")
        clean = f"{p.scheme}://{p.netloc}{path}"
        if clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


async def _cached_page(url: str) -> Page | None:
    cutoff = datetime.now(timezone.utc) - CACHE_TTL
    async with get_session_factory()() as s:
        page = await s.get(Page, url)
        if page and page.fetched_at and page.fetched_at >= cutoff:
            return page
    return None


async def _store_page(url: str, domain: str, status: int | None, text: str, via: str) -> None:
    async with get_session_factory()() as s:
        stmt = pg_insert(Page).values(
            url=url,
            domain=domain,
            status_code=status,
            text=text,
            content_hash=content_hash(text) if text else None,
            fetched_at=datetime.now(timezone.utc),
            via=via,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Page.url],
            set_={k: stmt.excluded[k] for k in ("domain", "status_code", "text", "content_hash", "fetched_at", "via")},
        )
        await s.execute(stmt)
        await s.commit()


async def _wayback(client: httpx.AsyncClient, url: str) -> tuple[str, str] | None:
    """Return (archived_url, html) for the closest snapshot, or None."""
    if not wayback_gate.available():
        return None
    try:
        r = await client.get("https://archive.org/wayback/available", params={"url": url}, timeout=6)
        if not wayback_gate.check(r.status_code) or r.status_code != 200:
            return None
        snap = r.json().get("archived_snapshots", {}).get("closest") or {}
        if not snap.get("available") or not snap.get("url"):
            return None
        arch = snap["url"]
        # 'id_' flag returns the original HTML without the Wayback toolbar.
        arch = re.sub(r"(/web/\d{14})/", r"\1id_/", arch, count=1)
        if not await robots_allowed(client, arch):
            return None
        status, html, _ = await _get_capped(client, arch)
        if wayback_gate.check(status) and status == 200 and html:
            return arch, html
    except Exception as e:  # noqa: BLE001
        log.info("wayback fallback failed for %s: %s", url, e)
    return None


async def fetch_page(client: httpx.AsyncClient, domain: str, url: str, *, use_cache: bool = True) -> FetchResult:
    res = FetchResult(url=url, domain=domain)
    if use_cache:
        page = await _cached_page(url)
        if page is not None and page.text:
            res.text, res.status_code, res.via, res.outcome, res.cached = page.text, page.status_code, page.via, "cached", True
            return res

    host = urlsplit(url).netloc.lower()
    if any(host == h or host.endswith("." + h) for h in DENY_HOSTS):
        log.info("deny-listed host %s — skipped", url)
        res.outcome = "robots"
        return res
    if not await robots_allowed(client, url):
        log.info("robots.txt disallows %s — skipped", url)
        res.outcome = "robots"
        return res

    fallback_reason: str | None = None
    html = ""
    try:
        status, html, final_url = await _get_capped(client, url)
        res.status_code = status
        if status in (401, 403, 429):
            res.outcome = "blocked"  # never fall back to Wayback when the site says no
            return res
        if status == 404 or status == 410:
            res.outcome = "not_found"
            return res
        if status >= 500:
            fallback_reason = f"http {status}"
        elif status == 200:
            res.links = _internal_links(html, final_url)
            res.text = extract_text(html, final_url, cap=TEXT_CAP)
            if len(res.text) < MIN_TEXT_CHARS:
                fallback_reason = "empty text"
        else:
            res.outcome = "error"
            return res
    except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
        fallback_reason = f"{type(e).__name__}"
        res.outcome = "timeout" if isinstance(e, httpx.TimeoutException) else "error"
    except Exception as e:  # noqa: BLE001
        log.info("fetch error %s: %s", url, e)
        res.outcome = "error"
        return res

    if fallback_reason:
        log.info("wayback fallback for %s (%s)", url, fallback_reason)
        wb = await _wayback(client, url)
        if wb:
            arch_url, wb_html = wb
            res.text = extract_text(wb_html, url, cap=TEXT_CAP)
            res.links = res.links or _internal_links(wb_html, url)
            res.via = "wayback"
            if len(res.text) >= MIN_TEXT_CHARS:
                res.outcome = "ok"
            else:
                res.text, res.outcome = "", "empty"
        elif res.outcome not in ("timeout", "error"):
            res.outcome = "empty"
    else:
        res.outcome = "ok"

    if res.text:
        await _store_page(url, domain, res.status_code, res.text, res.via)
    return res


async def record_reachable(domain: str, home: FetchResult) -> None:
    """reachable = the site answered HTTP at all (even if it blocked us); None if unknown (robots)."""
    if home.outcome == "robots":
        return
    if home.cached:
        reachable = True
    else:
        reachable = home.status_code is not None
    async with get_session_factory()() as s:
        c = (await s.scalars(select(Company).where(Company.domain == domain))).first()
        if c is not None:
            c.reachable = reachable
            await s.commit()


def make_client() -> httpx.AsyncClient:
    return _client()
