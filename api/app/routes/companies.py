import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Company
from app.schemas import CompanyOut, CompanyWithScan, ImportResult, ScanSummary
from app.services.latest import latest_scans
from app.services.dedupe import normalize_domain

router = APIRouter(prefix="/api/companies", tags=["companies"])

# Accept SaaSquatch-style and common CSV headers (matched after lowercasing + stripping non-alnum).
_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("company", "companyname", "name", "business", "businessname"),
    "domain": ("website", "domain", "url", "companydomainname", "companydomain", "site"),
    "industry": ("industry", "category", "sector"),
    "city": ("city", "town"),
    "state": ("state", "stateregion", "region", "province"),
    "employee_range": ("employees", "employeerange", "numberofemployees", "headcount", "companysize"),
    "revenue_estimate": ("revenue", "revenueestimate", "annualrevenue"),
    "phone": ("phone", "phonenumber", "telephone"),
    "linkedin_url": ("linkedin", "linkedinurl", "linkedincompanypage"),
    "source": ("source",),
}


def _norm_header(h: str) -> str:
    return "".join(ch for ch in h.lower() if ch.isalnum())


def _column_map(headers: list[str]) -> dict[str, str]:
    normed = {_norm_header(h): h for h in headers if h}
    out: dict[str, str] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for a in aliases:
            if a in normed:
                out[field] = normed[a]
                break
    return out


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


@router.post("/import", response_model=ImportResult)
async def import_companies(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)) -> ImportResult:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV has no header row")
    cmap = _column_map(list(reader.fieldnames))
    if "domain" not in cmap:
        raise HTTPException(400, f"CSV needs a website/domain column; got {reader.fieldnames}")

    rows: dict[str, dict] = {}
    total = no_domain = dupes_in_file = 0
    for r in reader:
        total += 1
        domain = normalize_domain(r.get(cmap["domain"]))
        if not domain:
            no_domain += 1
            continue
        if domain in rows:
            dupes_in_file += 1
            continue
        rows[domain] = {
            "domain": domain,
            **{f: _clean(r.get(col)) for f, col in cmap.items() if f != "domain"},
        }
        rows[domain].setdefault("source", None)
        rows[domain]["source"] = rows[domain]["source"] or "csv"

    inserted = 0
    if rows:
        stmt = (
            pg_insert(Company)
            .values(list(rows.values()))
            .on_conflict_do_nothing(index_elements=[Company.domain])
            .returning(Company.id)
        )
        inserted = len((await db.execute(stmt)).scalars().all())
        await db.commit()
    dupes_in_db = len(rows) - inserted
    return ImportResult(
        inserted=inserted,
        duplicates_skipped=dupes_in_file + dupes_in_db,
        no_domain_skipped=no_domain,
        total_rows=total,
    )


@router.get("", response_model=list[CompanyWithScan])
async def list_companies(icp_id: int | None = None, db: AsyncSession = Depends(get_db)) -> list[CompanyWithScan]:
    """All companies; with ?icp_id= each row carries its latest scan summary (score, coverage, top-3 met criteria)."""
    rows = (await db.scalars(select(Company).order_by(Company.id))).all()
    scans = await latest_scans(db, icp_id) if icp_id is not None else {}
    out = []
    for c in rows:
        item = CompanyWithScan.model_validate(c)
        if c.id in scans:
            item.scan = ScanSummary(**scans[c.id])
        out.append(item)
    return out
