import asyncio

from fastapi import FastAPI
from sqlalchemy import text

from app.db import get_engine

app = FastAPI(title="ICP Signal Scanner API", docs_url="/api/docs", openapi_url="/api/openapi.json")


async def _db_ping() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


@app.get("/api/health")
async def health() -> dict:
    try:
        await asyncio.wait_for(_db_ping(), timeout=8)
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": True, "db": db_ok}
