"""DataSource protocol. Every external feed implements this."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

@dataclass
class SourceRecord:
    """A normalized record from any data source.

    Sources translate their wire format into this. The storage layer
    only ever sees SourceRecord shapes.
    """
    source: str                          # "hyperliquid_ohlcv_1h"
    asset: str
    ts: int                              # unix seconds, the data point's time
    kind: str                            # "ohlcv" | "funding" | "oi" | "orderbook" | "onchain"
    payload: dict                        # source-specific shape
    ingested_at: int                     # unix ms, when we received it

class DataSource(ABC):
    """Common interface for all data sources."""

    name: str = ""                       # "hyperliquid_ohlcv"
    kind: str = ""                       # "ohlcv"
    assets: list[str] = []               # supported assets

    @abstractmethod
    async def fetch_latest(self, asset: str) -> Optional[SourceRecord]:
        """Pull the most recent value. Used for backfill + initial state."""

    @abstractmethod
    async def stream(self, asset: str):
        """Async generator yielding SourceRecord as they arrive."""

    async def healthcheck(self) -> bool:
        """Return True if upstream is reachable."""
        try:
            r = await self.fetch_latest(self.assets[0])
            return r is not None
        except Exception:
            return False

@dataclass
class SourceConfig:
    enabled: bool = True
    poll_interval_s: float = 5.0
    assets: list[str] = None
    extra: dict = None
