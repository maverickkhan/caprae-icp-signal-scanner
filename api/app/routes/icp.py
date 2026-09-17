from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.graph.compile import clean_criteria, ensure_compiled
from app.models import IcpProfile
from app.schemas import IcpCreate, IcpOut, IcpUpdate

router = APIRouter(prefix="/api/icp", tags=["icp"])


@router.get("", response_model=list[IcpOut])
async def list_icps(db: AsyncSession = Depends(get_db)) -> list[IcpOut]:
    rows = (await db.scalars(select(IcpProfile).order_by(IcpProfile.id))).all()
    return [IcpOut.model_validate(r) for r in rows]


@router.post("", response_model=IcpOut, status_code=201)
async def create_icp(body: IcpCreate, db: AsyncSession = Depends(get_db)) -> IcpOut:
    if not body.name.strip():
        raise HTTPException(400, "name is required")
    # description may be empty at creation: the user fills it in the panel, then compiles
    icp = IcpProfile(name=body.name.strip()[:120], description_text=body.description_text.strip(), criteria=[])
    db.add(icp)
    await db.commit()
    await db.refresh(icp)
    return IcpOut.model_validate(icp)


@router.get("/{icp_id}", response_model=IcpOut)
async def get_icp(icp_id: int, db: AsyncSession = Depends(get_db)) -> IcpOut:
    icp = await db.get(IcpProfile, icp_id)
    if icp is None:
        raise HTTPException(404, "ICP not found")
    return IcpOut.model_validate(icp)


@router.put("/{icp_id}", response_model=IcpOut)
async def update_icp(icp_id: int, body: IcpUpdate, db: AsyncSession = Depends(get_db)) -> IcpOut:
    icp = await db.get(IcpProfile, icp_id)
    if icp is None:
        raise HTTPException(404, "ICP not found")
    if body.name is not None:
        icp.name = body.name.strip()[:120]
    if body.description_text is not None and body.description_text.strip() != icp.description_text:
        icp.description_text = body.description_text.strip()
        icp.description_hash = None  # description changed: next compile/scan recompiles unless criteria are edited explicitly
    if body.criteria is not None:
        icp.criteria = clean_criteria([c.model_dump() for c in body.criteria])
        if not icp.criteria:
            raise HTTPException(400, "criteria cannot be empty")
        # user-edited criteria are authoritative for the current description
        from app.graph.compile import description_hash

        icp.description_hash = description_hash(icp.description_text)
    await db.commit()
    await db.refresh(icp)
    return IcpOut.model_validate(icp)


@router.post("/{icp_id}/compile", response_model=IcpOut)
async def compile_icp(icp_id: int, force: bool = True, db: AsyncSession = Depends(get_db)) -> IcpOut:
    icp = await db.get(IcpProfile, icp_id)
    if icp is None:
        raise HTTPException(404, "ICP not found")
    if not icp.description_text.strip():
        raise HTTPException(400, "Describe the ideal customer first, then compile")
    try:
        icp = await ensure_compiled(icp, db, force=force)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"ICP compile failed: {type(e).__name__}: {e}"[:300]) from e
    return IcpOut.model_validate(icp)
