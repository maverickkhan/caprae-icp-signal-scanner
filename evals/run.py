#!/usr/bin/env python3
"""Scan the golden domains and report grounding rates, expected-fact recall, criterion agreement and latency.

Run from /api:  uv run python ../evals/run.py [--force] [--only domain]
Writes evals/results.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")
EVALS_DIR = Path(__file__).resolve().parent
API_DIR = EVALS_DIR.parent / "api"
sys.path.insert(0, str(API_DIR))


async def scan_case(case: dict, force: bool) -> dict:
    from sqlalchemy import select

    from app.db import get_session_factory
    from app.graph.run import run_scan
    from app.models import Company, IcpProfile
    from app.presets import PRESET_ALIASES
    from app.services.dedupe import normalize_domain

    dom = normalize_domain(case["domain"]) or case["domain"]
    async with get_session_factory()() as db:
        company = (await db.scalars(select(Company).where(Company.domain == dom))).first()
        if company is None:
            company = Company(domain=dom, name=dom, source="evals")
            db.add(company)
            await db.commit()
            await db.refresh(company)
        icp = (await db.scalars(select(IcpProfile).where(IcpProfile.name == PRESET_ALIASES.get(case["icp"], case["icp"])))).first()
        if icp is None:
            raise SystemExit(f"ICP {case['icp']} not found")
        cid, iid = company.id, icp.id
    t0 = time.perf_counter()
    d = await run_scan(cid, iid, force=force)
    d["_latency"] = round(time.perf_counter() - t0, 1)
    d["_cached"] = d["_latency"] < 5
    return d


def evaluate(case: dict, d: dict) -> dict:
    facts = d.get("facts") or []
    g = Counter(f["grounding"] for f in facts)
    verified = [f for f in facts if f["grounding"] != "none"]
    hay = " ".join(f"{f['fact']} {f['evidence_quote'] or ''}" for f in verified).lower()
    fact_hits = [s for s in case.get("expected_facts", []) if s.lower() in hay]
    verdicts = {c["key"]: c["verdict"] for c in d.get("criteria") or []}
    agree = []
    for key, exp in case.get("expected_verdicts", {}).items():
        if key not in verdicts:
            agree.append((key, exp, "missing", None))
        else:
            agree.append((key, exp, verdicts[key], verdicts[key] == exp))
    met_grounded = all(c["grounding"] != "none" and c["evidence_quote"] for c in d.get("criteria") or [] if c["verdict"] in ("met", "not_met"))
    return {
        "domain": case["domain"],
        "icp": case["icp"],
        "status": d.get("status"),
        "score": d.get("score"),
        "coverage": d.get("coverage"),
        "pages": d.get("pages_fetched"),
        "facts": len(facts),
        "exact": g.get("exact", 0),
        "fuzzy": g.get("fuzzy", 0),
        "record": g.get("record", 0),
        "none": g.get("none", 0),
        "fact_hits": len(fact_hits),
        "fact_expected": len(case.get("expected_facts", [])),
        "agree": agree,
        "all_verdicts_grounded": met_grounded,
        "latency": d["_latency"],
        "cached": d["_cached"],
        "note": bool(d.get("outreach_note")),
    }


def write_results(rows: list[dict], path: Path) -> str:
    tot = Counter()
    for r in rows:
        for k in ("facts", "exact", "fuzzy", "record", "none", "fact_hits", "fact_expected"):
            tot[k] += r[k]
    judged = [a for r in rows for a in r["agree"] if a[3] is not None]
    agreed = sum(1 for a in judged if a[3])
    fresh = [r["latency"] for r in rows if not r["cached"]]
    grounded = tot["exact"] + tot["fuzzy"] + tot["record"]
    lines = [
        f"# Eval results — {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
        "",
        f"- Domains: {len(rows)}  ·  facts: {tot['facts']}  ·  grounded: {grounded}/{tot['facts']} "
        f"({100 * grounded / max(tot['facts'], 1):.0f}%) — exact {tot['exact']}, fuzzy {tot['fuzzy']}, record {tot['record']}, none {tot['none']}",
        f"- Expected-fact recall: {tot['fact_hits']}/{tot['fact_expected']}",
        f"- Criterion agreement vs expected: {agreed}/{len(judged)}",
        f"- Every met/not_met verdict carries a verified quote: {'yes' if all(r['all_verdicts_grounded'] for r in rows) else 'NO'}",
        f"- Avg latency (fresh scans): {sum(fresh) / len(fresh):.1f}s over {len(fresh)}" if fresh else "- Avg latency: all results served from the 7-day cache (run with --force for fresh timings)",
        "",
        "| domain | icp | status | score | coverage | pages | facts | exact/fuzzy/record/none | expected facts | agreement | latency |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ag = ", ".join(f"{k}: {exp}→{got}{'' if ok else ' ✗' if ok is not None else ' (missing)'}" for k, exp, got, ok in r["agree"]) or "—"
        lines.append(
            f"| {r['domain']} | {r['icp']} | {r['status']} | {r['score']} | {r['coverage']}% | {r['pages']} | {r['facts']} | "
            f"{r['exact']}/{r['fuzzy']}/{r['record']}/{r['none']} | {r['fact_hits']}/{r['fact_expected']} | {ag} | {r['latency']}s{' (cache)' if r['cached'] else ''} |"
        )
    out = "\n".join(lines) + "\n"
    path.write_text(out)
    return out


async def main_async(args: argparse.Namespace) -> None:
    from app.db import ensure_schema, get_engine

    golden = json.loads((EVALS_DIR / "golden.json").read_text())
    cases = [c for c in golden["cases"] if not args.only or c["domain"] == args.only]
    await ensure_schema()
    rows = []
    try:
        for case in cases:
            print(f"scanning {case['domain']} ({case['icp']}) ...", flush=True)
            try:
                d = await scan_case(case, args.force)
            except Exception as e:  # noqa: BLE001
                print(f"  failed: {e}")
                continue
            rows.append(evaluate(case, d))
            print(f"  score={rows[-1]['score']} coverage={rows[-1]['coverage']} facts={rows[-1]['facts']} {rows[-1]['latency']}s")
    finally:
        await get_engine().dispose()
    print()
    print(write_results(rows, EVALS_DIR / "results.md"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore the 7-day scan cache")
    ap.add_argument("--only", help="run a single domain")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
