#!/usr/bin/env python3
"""Pre-warm the scan cache on a deployment: scan N companies per ICP with limited concurrency.

Usage: python3 scripts/prewarm.py --base https://caprae-icp-signal-scanner.vercel.app --per-icp 20 --concurrency 2
Respects the Gemini free tier by keeping concurrency low (each scan already caps itself at 2 LLM calls in flight).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=120) as r:
        return json.load(r)


def scan(base: str, company_id: int, icp_id: int) -> tuple[int, int, str, float]:
    t0 = time.time()
    req = urllib.request.Request(f"{base}/api/scan/{company_id}?icp_id={icp_id}", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=310) as r:
            d = json.load(r)
            return company_id, icp_id, f"{d['status']} score={d['score']} cov={d['coverage']}", time.time() - t0
    except urllib.error.HTTPError as e:
        return company_id, icp_id, f"HTTP {e.code}: {e.read()[:120]!r}", time.time() - t0
    except Exception as e:  # noqa: BLE001
        return company_id, icp_id, f"{type(e).__name__}: {e}", time.time() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--per-icp", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=2)
    args = ap.parse_args()
    base = args.base.rstrip("/")

    icps = get(base, "/api/icp")
    companies = get(base, "/api/companies")
    # spread across industries: alternate from the front of each industry group
    by_ind: dict[str, list[dict]] = {}
    for c in companies:
        by_ind.setdefault(c.get("industry") or "?", []).append(c)
    picked: list[dict] = []
    while len(picked) < args.per_icp and any(by_ind.values()):
        for lst in by_ind.values():
            if lst and len(picked) < args.per_icp:
                picked.append(lst.pop(0))
    jobs = [(c["id"], i["id"]) for i in icps for c in picked]
    print(f"{len(jobs)} scans ({len(picked)} companies x {len(icps)} ICPs), concurrency {args.concurrency}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(scan, base, cid, iid) for cid, iid in jobs]
        for n, f in enumerate(as_completed(futs), 1):
            cid, iid, msg, dt = f.result()
            print(f"[{n}/{len(jobs)}] company {cid} icp {iid}: {msg} ({dt:.0f}s)", flush=True)
    print(f"done in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
