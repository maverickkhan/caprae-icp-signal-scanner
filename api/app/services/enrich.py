"""Public-record enrichers: RDAP (event dates only) + Wayback first capture. Cached in `enrichments`."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_session_factory
from app.models import Enrichment
from app.services import wayback_gate

log = logging.getLogger("icp.enrich")

OK_TTL = timedelta(days=30)
FAIL_TTL = timedelta(days=1)

# rdap.org allows 10 requests / 10s; keep well under it per process.
_rdap_gate = asyncio.Semaphore(2)
_RDAP_EVENTS = {"registration": "registered", "expiration": "expires", "last changed": "last_changed"}


def registrable_domain(domain: str) -> str:
    """Naive eTLD+1 (handles common 2-level public suffixes like co.uk)."""
    parts = domain.lower().split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "gov", "ac") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain


async def _cached(domain: str, kind: str) -> dict | None:
    async with get_session_factory()() as s:
        row = await s.get(Enrichment, (domain, kind))
        if row is None or row.fetched_at is None:
            return None
        ttl = OK_TTL if row.payload.get("ok") else FAIL_TTL
        if row.fetched_at >= datetime.now(timezone.utc) - ttl:
            return row.payload
    return None


async def _store(domain: str, kind: str, payload: dict) -> None:
    async with get_session_factory()() as s:
        stmt = pg_insert(Enrichment).values(domain=domain, kind=kind, payload=payload, fetched_at=datetime.now(timezone.utc))
        stmt = stmt.on_conflict_do_update(index_elements=[Enrichment.domain, Enrichment.kind], set_={"payload": stmt.excluded.payload, "fetched_at": stmt.excluded.fetched_at})
        await s.execute(stmt)
        await s.commit()


async def rdap(client: httpx.AsyncClient, domain: str) -> dict:
    """{ok, registered, expires, last_changed, domain_age_years} — dates only, never registrant data."""
    cached = await _cached(domain, "rdap")
    if cached is not None:
        return cached
    target = registrable_domain(domain)
    payload: dict = {"ok": False, "source": f"https://rdap.org/domain/{target}"}
    try:
        async with _rdap_gate:
            r = await client.get(f"https://rdap.org/domain/{target}", headers={"Accept": "application/rdap+json"})
            await asyncio.sleep(1.0)
        if r.status_code == 200:
            data = r.json()
            for ev in data.get("events", []):
                key = _RDAP_EVENTS.get(str(ev.get("eventAction", "")).lower())
                if key and ev.get("eventDate"):
                    payload[key] = str(ev["eventDate"])[:10]
            if payload.get("registered"):
                yr = int(payload["registered"][:4])
                payload["domain_age_years"] = datetime.now(timezone.utc).year - yr
                payload["ok"] = True
            else:
                payload["error"] = "no registration event"
        else:
            payload["error"] = f"http {r.status_code}"
    except Exception as e:  # noqa: BLE001
        payload["error"] = type(e).__name__
    await _store(domain, "rdap", payload)
    return payload


async def _cdx_first(client: httpx.AsyncClient, domain: str) -> dict | None:
    r = await client.get(
        "https://web.archive.org/cdx/search/cdx",
        params={"url": domain, "output": "json", "limit": 1, "fl": "timestamp,statuscode", "filter": "statuscode:200", "from": "1996"},
        timeout=6,
    )
    if not wayback_gate.check(r.status_code) or r.status_code != 200:
        return None
    rows = r.json()
    if len(rows) >= 2 and rows[1] and rows[1][0]:
        ts = rows[1][0]
        return {"first_capture": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", "first_capture_year": int(ts[:4])}
    return None


async def _availability_first(client: httpx.AsyncClient, domain: str) -> dict | None:
    # Closest snapshot to 1996 ~= earliest capture. Used when CDX is 503 (common under load).
    r = await client.get("https://archive.org/wayback/available", params={"url": domain, "timestamp": "19960101"}, timeout=6)
    if not wayback_gate.check(r.status_code) or r.status_code != 200:
        return None
    snap = r.json().get("archived_snapshots", {}).get("closest") or {}
    ts = str(snap.get("timestamp", ""))
    if snap.get("available") and len(ts) >= 8:
        return {"first_capture": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", "first_capture_year": int(ts[:4]), "approx": True}
    return None


async def wayback_first_capture(client: httpx.AsyncClient, domain: str) -> dict:
    """{ok, first_capture (YYYY-MM-DD), first_capture_year, source}. Failure => ok False (unknown)."""
    cached = await _cached(domain, "wayback")
    if cached is not None:
        return cached
    payload: dict = {"ok": False, "source": f"https://web.archive.org/web/*/{domain}"}
    if not wayback_gate.available():
        return {**payload, "error": "archive.org cooling down"}  # not cached: retry on a later scan
    cdx, avail = await asyncio.gather(_cdx_first(client, domain), _availability_first(client, domain), return_exceptions=True)
    hit = cdx if isinstance(cdx, dict) else (avail if isinstance(avail, dict) else None)
    if hit:
        payload.update(ok=True, **hit)
    else:
        errs = [type(x).__name__ if isinstance(x, Exception) else "no data" for x in (cdx, avail)]
        payload["error"] = "; ".join(errs)
    await _store(domain, "wayback", payload)
    return payload


async def enrich(client: httpx.AsyncClient, domain: str) -> dict:
    r, w = await asyncio.gather(rdap(client, domain), wayback_first_capture(client, domain))
    return {"rdap": r, "wayback": w}
