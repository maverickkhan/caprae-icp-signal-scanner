import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db import ensure_schema, get_engine
from app.routes import companies

log = logging.getLogger("icp")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Best effort: create tables + seed presets on cold start. get_db() also guards this lazily.
    try:
        await asyncio.wait_for(ensure_schema(), timeout=20)
    except Exception as e:  # noqa: BLE001
        log.warning("schema bootstrap skipped at startup: %s", e)
    yield


app = FastAPI(
    title="ICP Signal Scanner API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(companies.router)


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
