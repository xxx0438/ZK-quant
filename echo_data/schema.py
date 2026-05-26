"""Re-export SDK schemas + add DB-side models.

The point: quants and the runtime use the SAME pydantic types as the
canonical data layer. No translation, no drift.
"""
from echo_quant.model import (
    Inputs,
    OHLCV,
    OrderbookSnapshot,
    OnchainData,
    Signal,
)

# DB-only types

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class StoredSnapshot:
    """How a snapshot lives in Postgres + Redis."""
    snapshot_hash: str
    asset: str
    timestamp: int                      # unix seconds, snapshot's logical time
    inputs_json: bytes                  # the full Inputs as JSON (orjson)
    schema_version: str = "1.0.0"
    created_at: Optional[datetime] = None
    source_versions: Optional[dict] = None  # {"hyperliquid": "v1", "arkham": "v2"}

__all__ = [
    "Inputs", "OHLCV", "OrderbookSnapshot", "OnchainData", "Signal",
    "StoredSnapshot",
]
