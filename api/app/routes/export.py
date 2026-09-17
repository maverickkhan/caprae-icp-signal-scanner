import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Company, CriterionResult, IcpProfile, Scan
from app.services.latest import latest_scans

router = APIRouter(prefix="/api", tags=["export"])

# HubSpot company import headers first, then our fit columns.
HEADERS = [
    "Company name",
    "Company Domain Name",
    "City",
    "State/Region",
    "Industry",
    "Phone Number",
    "Number of Employees",
    "fit_score",
    "coverage",
    "met_criteria",
    "outreach_note",
    "evidence_urls",
]


@router.get("/export.csv")
async def export_csv(icp_id: int, scanned_only: bool = False, db: AsyncSession = Depends(get_db)) -> Response:
    icp = await db.get(IcpProfile, icp_id)
    if icp is None:
        raise HTTPException(404, "ICP not found")
    companies = (await db.scalars(select(Company).order_by(Company.id))).all()
    latest = await latest_scans(db, icp_id)
    scan_ids = [v["scan_id"] for v in latest.values()]
    notes: dict[int, str | None] = {}
    urls: dict[int, list[str]] = {}
    if scan_ids:
        for s in (await db.scalars(select(Scan).where(Scan.id.in_(scan_ids)))).all():
            notes[s.id] = s.outreach_note
        rows = await db.execute(
            select(CriterionResult.scan_id, CriterionResult.source_url).where(
                CriterionResult.scan_id.in_(scan_ids), CriterionResult.verdict.in_(("met", "not_met")), CriterionResult.source_url.isnot(None)
            )
        )
        for sid, url in rows.all():
            lst = urls.setdefault(sid, [])
            if url not in lst:
                lst.append(url)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    # Evidence-aware ranking (same as the UI): score x coverage, score as tiebreak, unscanned last.
    def sort_key(c: Company):
        s = latest.get(c.id)
        score = s["score"] if s and s["score"] is not None else -1
        cov = (s["coverage"] or 0) if s else 0
        rank = score * cov / 100 if score >= 0 else -1
        return (-rank, -score, c.id)

    for c in sorted(companies, key=sort_key):
        s = latest.get(c.id)
        if scanned_only and not s:
            continue
        w.writerow(
            [
                c.name or "",
                c.domain,
                c.city or "",
                c.state or "",
                c.industry or "",
                c.phone or "",
                c.employee_range or "",
                "" if not s or s["score"] is None else s["score"],
                "" if not s or s["coverage"] is None else s["coverage"],
                "; ".join(s["met_criteria"]) if s else "",
                (notes.get(s["scan_id"]) or "") if s else "",
                " ".join(urls.get(s["scan_id"], [])) if s else "",
            ]
        )
    filename = f"icp-scan-{icp.name.lower().replace(' ', '-')}.csv"
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
