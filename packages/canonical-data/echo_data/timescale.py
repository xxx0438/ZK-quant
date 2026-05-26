"""Async SQLAlchemy engine + raw SQL helpers for the canonical data DB.

We use raw SQL (not ORM) for the hot read path because:
- Time-series queries are query-shaped, not row-shaped
- TimescaleDB hyperfunctions (time_bucket, first, last) don't have clean ORM equivalents
- Saves 1-3ms per call which matters at 100 req/s
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    create_async_engine,
)

def _build_engine() -> AsyncEngine:
    url = os.getenv("CANONICAL_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("CANONICAL_DATABASE_URL or DATABASE_URL must be set")
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300,
    )

_engine: AsyncEngine | None = None

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine

@asynccontextmanager
async def connect() -> AsyncIterator[AsyncConnection]:
    """Yield a connection. Caller MUST NOT begin/commit — this is read-only path."""
    eng = get_engine()
    async with eng.connect() as conn:
        yield conn

async def close():
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
