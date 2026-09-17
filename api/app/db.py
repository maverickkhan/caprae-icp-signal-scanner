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
