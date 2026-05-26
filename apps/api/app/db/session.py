"""Async SQLAlchemy session factory.

Production-tuned:
- pool_pre_ping handles stale connections (cloud Postgres often kills idle conns)
- pool_recycle < typical cloud provider idle timeout (300s safe for Supabase/RDS)
- expire_on_commit=False so we can read attributes after commit without re-query
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from app.config import settings

# Echo SQL in dev, silent in prod
_echo_sql = settings.environment == "development" and settings.log_level == "DEBUG"

engine = create_async_engine(
    settings.database_url,
    echo=_echo_sql,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30,
    # asyncpg-specific: disable statement cache for pgbouncer compatibility
    connect_args={"statement_cache_size": 0} if "pgbouncer" in settings.database_url else {},
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. Yields a session and ensures cleanup."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # commit is explicit per route; we don't auto-commit on exit

async def close_engine():
    """Call on shutdown."""
    await engine.dispose()
