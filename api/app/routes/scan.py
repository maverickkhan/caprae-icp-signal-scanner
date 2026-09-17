from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.graph.run import ScanError, run_scan, scan_detail
from app.models import Scan

router = APIRouter(prefix="/api", tags=["scan"])


@router.post("/scan/{company_id}")
async def scan_company(company_id: int, icp_id: int, force: bool = False, db: AsyncSession = Depends(get_db)) -> dict:
    """Runs the whole graph synchronously inside this request (<=300s on Vercel). Cached for 7 days per (company, ICP)."""
    try:
        return await run_scan(company_id, icp_id, force=force)
    except ScanError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    scan = await db.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(404, "scan not found")
    return await scan_detail(db, scan)
