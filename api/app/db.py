"""Async SQLAlchemy engine for Neon Postgres (pooled URL)."""

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# asyncpg does not accept libpq-style params; SSL is passed via connect_args.
_DROP_QUERY_KEYS = {"sslmode", "channel_binding", "options"}


def normalize_database_url(url: str) -> str:
    """postgresql://... -> postgresql+asyncpg://... with libpq-only params removed."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in _DROP_QUERY_KEYS]
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        kwargs: dict = dict(
            pool_pre_ping=True,
            # Neon's pooled endpoint is pgbouncer in transaction mode: disable asyncpg's
            # prepared-statement cache and bound the connect time so /api/health can't hang.
            connect_args={"ssl": "require", "statement_cache_size": 0, "timeout": 10},
        )
        if os.environ.get("VERCEL"):
            # Serverless: one event loop per invocation is not guaranteed; let Neon pool.
            kwargs["poolclass"] = NullPool
        else:
            kwargs.update(pool_size=2, max_overflow=3, pool_recycle=300)
        _engine = create_async_engine(normalize_database_url(url), **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


# --- schema bootstrap (no Alembic): create tables + seed presets once per process ---
import asyncio
from collections.abc import AsyncIterator

_schema_ready = False
_schema_lock: asyncio.Lock | None = None


async def ensure_schema() -> None:
    global _schema_ready, _schema_lock
    if _schema_ready:
        return
    if _schema_lock is None:
        _schema_lock = asyncio.Lock()
    async with _schema_lock:
        if _schema_ready:
            return
        from sqlalchemy import select

        from app.models import Base, IcpProfile
        from app.presets import PRESETS

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with get_session_factory()() as session:
            existing = set((await session.scalars(select(IcpProfile.name))).all())
            for p in PRESETS:
                if p["name"] not in existing:
                    session.add(IcpProfile(name=p["name"], description_text=p["description_text"], criteria=[]))
            await session.commit()
        _schema_ready = True


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: session with schema guaranteed."""
    await ensure_schema()
    async with get_session_factory()() as session:
        yield session
