"""run_scan: one synchronous scan per company × ICP. Persists scan, facts, criterion_results."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session_factory
from app.graph.compile import ensure_compiled
from app.graph.graph import scan_graph
from app.graph.llm import model_versions, new_semaphore
from app.graph.nodes import strip_markers
from app.models import Company, CriterionResult, Fact, IcpProfile, Scan

log = logging.getLogger("icp.run")

FRESH_FOR = timedelta(days=7)
GRAPH_BUDGET_S = 240  # stay well inside Vercel's 300s


class ScanError(Exception):
    pass


async def get_fresh_scan(db: AsyncSession, company_id: int, icp_id: int) -> Scan | None:
    cutoff = datetime.now(timezone.utc) - FRESH_FOR
    stmt = (
        select(Scan)
        .where(Scan.company_id == company_id, Scan.icp_id == icp_id, Scan.status == "done", Scan.finished_at >= cutoff)
        .order_by(Scan.finished_at.desc())
        .limit(1)
    )
    return (await db.scalars(stmt)).first()


async def scan_detail(db: AsyncSession, scan: Scan) -> dict:
    """Full result for the API/CLI: scan + criteria (merged with ICP definitions) + facts + note."""
    icp = await db.get(IcpProfile, scan.icp_id)
    company = await db.get(Company, scan.company_id)
    crit_defs = {c["key"]: c for c in (icp.criteria if icp else [])}
    results = (await db.scalars(select(CriterionResult).where(CriterionResult.scan_id == scan.id).order_by(CriterionResult.id))).all()
    facts = (await db.scalars(select(Fact).where(Fact.scan_id == scan.id).order_by(Fact.id))).all()
    fact_ids = {f.id: i + 1 for i, f in enumerate(facts)}  # stable display ids (1..n)
    criteria = []
    for r in results:
        d = crit_defs.get(r.criterion_key, {})
        criteria.append(
            {
                "key": r.criterion_key,
                "label": d.get("label", r.criterion_key),
                "weight": d.get("weight", 1),
                "polarity": d.get("polarity", "positive"),
                "test": d.get("test", ""),
                "verdict": r.verdict,
                "evidence_quote": r.evidence_quote,
                "source_url": r.source_url,
                "grounding": r.grounding,
                "confidence": r.confidence,
            }
        )
    return {
        "scan_id": scan.id,
        "company_id": scan.company_id,
        "company": {"id": company.id, "name": company.name, "domain": company.domain, "reachable": company.reachable} if company else None,
        "icp_id": scan.icp_id,
        "icp_name": icp.name if icp else None,
        "status": scan.status,
        "score": scan.score,
        "coverage": scan.coverage,
        "outreach_note": scan.outreach_note,
        "model_versions": scan.model_versions,
        "pages_fetched": scan.pages_fetched,
        "fallback_used": scan.fallback_used,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
        "error": scan.error,
        "criteria": criteria,
        "facts": [
            {
                "id": fact_ids[f.id],
                "category": f.category,
                "fact": f.fact,
                "evidence_quote": f.evidence_quote,
                "source_url": f.source_url,
                "confidence": f.confidence,
                "grounding": f.grounding,
            }
            for f in facts
        ],
    }


async def run_scan(company_id: int, icp_id: int, *, force: bool = False, callbacks: list | None = None) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        company = await db.get(Company, company_id)
        icp = await db.get(IcpProfile, icp_id)
        if company is None or icp is None:
            raise ScanError("company or ICP not found")
        if not force:
            fresh = await get_fresh_scan(db, company_id, icp_id)
            if fresh is not None:
                return await scan_detail(db, fresh)
        icp = await ensure_compiled(icp, db)
        scan = Scan(company_id=company_id, icp_id=icp_id, status="running", model_versions=model_versions())
        db.add(scan)
        await db.commit()
        await db.refresh(scan)
        scan_id, domain, name, icp_name, criteria = scan.id, company.domain, company.name, icp.name, list(icp.criteria)

    t0 = time.perf_counter()
    state = {
        "scan_id": scan_id,
        "company_id": company_id,
        "company_name": name,
        "domain": domain,
        "icp_id": icp_id,
        "icp_name": icp_name,
        "criteria": criteria,
        "raw_facts": [],
        "timings": {},
    }
    config = {
        "configurable": {"sem": new_semaphore()},
        "tags": [f"scan_id:{scan_id}", f"domain:{domain}", f"icp_id:{icp_id}"],
        "metadata": {"scan_id": scan_id, "domain": domain, "icp_id": icp_id},
        "callbacks": callbacks or [],
    }
    result: dict = {}
    error: str | None = None
    try:
        async with asyncio.timeout(GRAPH_BUDGET_S):
            result = await scan_graph.ainvoke(state, config=config)
    except TimeoutError:
        error = f"scan exceeded {GRAPH_BUDGET_S}s budget"
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"[:500]
        log.exception("scan %s failed", scan_id)

    # Persist whatever we have (facts from a partial run are still useful), then mark done/error.
    async with factory() as db:
        scan = await db.get(Scan, scan_id)
        for f in result.get("facts") or []:
            db.add(
                Fact(
                    scan_id=scan_id,
                    category=f.get("category"),
                    fact=f["fact"],
                    evidence_quote=f.get("evidence_quote"),
                    source_url=f.get("source_url"),
                    confidence=f.get("confidence"),
                    grounding=f.get("grounding", "none"),
                )
            )
        for j in result.get("judgments") or []:
            db.add(
                CriterionResult(
                    scan_id=scan_id,
                    criterion_key=j["criterion_key"],
                    verdict=j["verdict"],
                    evidence_quote=j.get("evidence_quote"),
                    source_url=j.get("source_url"),
                    grounding=j.get("grounding", "none"),
                    confidence=None,
                )
            )
        sc = result.get("score") or {}
        scan.status = "error" if error else "done"
        scan.error = error
        scan.score = sc.get("score")
        scan.coverage = sc.get("coverage")
        scan.outreach_note = strip_markers(result.get("note"))
        scan.pages_fetched = result.get("pages_fetched")
        scan.fallback_used = result.get("fallback_used")
        scan.finished_at = datetime.now(timezone.utc)
        if result.get("reachable") is not None:
            company = await db.get(Company, company_id)
            if company is not None:
                company.reachable = result["reachable"]
        await db.commit()
        await db.refresh(scan)
        detail = await scan_detail(db, scan)
    detail["timings"] = {**(result.get("timings") or {}), "total": round(time.perf_counter() - t0, 2)}
    detail["note_status"] = result.get("note_status")
    detail["breakdown"] = sc.get("breakdown")
    return detail
