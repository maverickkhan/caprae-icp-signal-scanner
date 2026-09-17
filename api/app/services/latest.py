"""Latest finished scan per company for an ICP, with the top-3 met criteria (labels)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CriterionResult, IcpProfile, Scan


async def latest_scans(db: AsyncSession, icp_id: int, company_ids: list[int] | None = None) -> dict[int, dict]:
    """company_id -> {scan_id, status, score, coverage, met_criteria, finished_at, error}."""
    icp = await db.get(IcpProfile, icp_id)
    labels = {c["key"]: (c.get("label") or c["key"]) for c in (icp.criteria if icp else [])}
    weights = {c["key"]: int(c.get("weight") or 1) for c in (icp.criteria if icp else [])}

    ranked = (
        select(Scan, func.row_number().over(partition_by=Scan.company_id, order_by=Scan.finished_at.desc().nulls_last()).label("rn"))
        .where(Scan.icp_id == icp_id, Scan.status.in_(("done", "error")))
    )
    if company_ids is not None:
        ranked = ranked.where(Scan.company_id.in_(company_ids))
    sub = ranked.subquery()
    scans = (await db.execute(select(sub).where(sub.c.rn == 1))).all()
    out: dict[int, dict] = {}
    scan_ids: list[int] = []
    for row in scans:
        out[row.company_id] = {
            "scan_id": row.id,
            "status": row.status,
            "score": row.score,
            "coverage": row.coverage,
            "met_criteria": [],
            "finished_at": row.finished_at,
            "error": row.error,
        }
        scan_ids.append(row.id)
    if scan_ids:
        met = (
            await db.execute(
                select(CriterionResult.scan_id, CriterionResult.criterion_key).where(
                    CriterionResult.scan_id.in_(scan_ids), CriterionResult.verdict == "met"
                )
            )
        ).all()
        by_scan: dict[int, list[str]] = {}
        for scan_id, key in met:
            by_scan.setdefault(scan_id, []).append(key)
        scan_to_company = {v["scan_id"]: k for k, v in out.items()}
        for scan_id, keys in by_scan.items():
            keys.sort(key=lambda k: -weights.get(k, 1))
            out[scan_to_company[scan_id]]["met_criteria"] = [labels.get(k, k) for k in keys[:3]]
    return out
