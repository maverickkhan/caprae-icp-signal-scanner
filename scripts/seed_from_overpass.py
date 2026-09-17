#!/usr/bin/env python3
"""Seed ~120 leads with websites from OpenStreetMap via Overpass.

One sequential query per industry, identifying User-Agent, 30s backoff on 429/406.
Writes data/seed_leads.csv in SaaSquatch-style columns. Unknown fields stay blank
(no fabricated data). Data © OpenStreetMap contributors, ODbL — see README.

Usage: python3 scripts/seed_from_overpass.py [--per-industry 60] [--bbox S,W,N,E]
Reads SCANNER_USER_AGENT from .env if present (stdlib only, no deps).
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Texas (statewide): enough OSM-tagged trades with websites for ~120 leads.
DEFAULT_BBOX = "25.8,-106.7,36.5,-93.5"

INDUSTRIES = [
    ("HVAC", '["craft"="hvac"]'),
    ("Plumbing", '["craft"="plumber"]'),
]

COLUMNS = ["Company", "Website", "Industry", "City", "State", "Phone", "Employees", "Revenue", "LinkedIn", "Source"]


def load_user_agent() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("SCANNER_USER_AGENT="):
                v = line.split("=", 1)[1].strip().strip('"')
                if v:
                    return v
    return os.environ.get("SCANNER_USER_AGENT", "ICPSignalScanner/0.1 (seed script)")


def overpass(query: str, ua: str, retries: int = 3) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(OVERPASS_URL, data=data, headers={"User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 406, 504) and attempt < retries:
                print(f"  overpass {e.code}; backing off 30s (attempt {attempt + 1}/{retries})", file=sys.stderr)
                time.sleep(30)
                continue
            raise
    raise RuntimeError("overpass: retries exhausted")


def normalize_domain(raw: str) -> str | None:
    s = raw.strip().lower()
    if not s:
        return None
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s):
        s = "http://" + s
    host = urllib.parse.urlsplit(s).hostname or ""
    host = host.strip(".")
    if host.startswith("www."):
        host = host[4:]
    if "." not in host:
        return None
    return host


_SKIP_HOSTS = ("facebook.com", "yelp.com", "instagram.com", "linkedin.com", "google.com", "angi.com", "nextdoor.com")


def rows_for(industry: str, selector: str, bbox: str, limit: int, ua: str, seen: set[str]) -> list[dict]:
    q = f'[out:json][timeout:120];nwr{selector}["website"]({bbox});out center tags;'
    print(f"querying {industry} ...", file=sys.stderr)
    data = overpass(q, ua)
    out: list[dict] = []
    for el in data.get("elements", []):
        t = el.get("tags", {})
        site = t.get("website") or t.get("contact:website") or ""
        dom = normalize_domain(site.split(";")[0])
        if not dom or dom in seen or any(dom.endswith(h) for h in _SKIP_HOSTS):
            continue
        name = (t.get("name") or "").strip()
        if not name:
            continue
        seen.add(dom)
        out.append(
            {
                "Company": name,
                "Website": dom,
                "Industry": industry,
                "City": t.get("addr:city", ""),
                "State": t.get("addr:state", ""),
                "Phone": t.get("phone") or t.get("contact:phone") or "",
                "Employees": "",
                "Revenue": "",
                "LinkedIn": "",
                "Source": f"osm:{el.get('type')}/{el.get('id')}",
            }
        )
        if len(out) >= limit:
            break
    print(f"  {industry}: {len(out)} rows (of {len(data.get('elements', []))} elements)", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-industry", type=int, default=65)
    ap.add_argument("--bbox", default=DEFAULT_BBOX, help="S,W,N,E")
    ap.add_argument("--out", default=str(ROOT / "data" / "seed_leads.csv"))
    args = ap.parse_args()

    ua = load_user_agent()
    seen: set[str] = set()
    rows: list[dict] = []
    for i, (industry, selector) in enumerate(INDUSTRIES):
        if i:
            time.sleep(5)  # be polite between sequential queries
        rows.extend(rows_for(industry, selector, args.bbox, args.per_industry, ua, seen))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
