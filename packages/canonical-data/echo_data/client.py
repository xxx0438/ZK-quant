"""High-level client for consumers (API, runtime, allocator).

Thin wrapper around SnapshotBuilder. Future home of:
- request coalescing (already happens via Redis bucket key)
- multi-asset batching
- circuit breaker for degraded data sources
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from echo_data.schema import Inputs
from echo_data.snapshot import SnapshotBuilder

log = logging.getLogger("echo_data.client")

class CanonicalDataClient:
    """Used by apps/api and apps/model-runtime."""

    def __init__(self, redis_url: Optional[str] = None):
        self._builder = SnapshotBuilder(
            redis_url=redis_url or os.getenv("REDIS_URL", "redis://localhost:6379"),
        )

    async def build_live(self, asset: str) -> tuple[Inputs, str]:
        """Snapshot of current market. Returns (inputs, snapshot_hash)."""
        return await self._builder.live(asset)

    async def build_historical(self, asset: str, ts: datetime) -> tuple[Inputs, str]:
        """Snapshot at a specific historical timestamp."""
        return await self._builder.historical(asset, ts)

    async def replay(self, snapshot_hash: str) -> Optional[Inputs]:
        """Fetch an archived snapshot by hash."""
        return await self._builder.replay(snapshot_hash)
