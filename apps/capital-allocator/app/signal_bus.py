"""Consume the Echo signal stream from Redis pub/sub.

Each signal is a dict matching the payload published by routers/predict.py.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import redis.asyncio as redis

from app.config import settings

log = logging.getLogger("allocator.signals")

class Signal:
    __slots__ = (
        "signal_id", "model_id", "model_version", "prediction",
        "live_sharpe_30d", "tested_capacity_usd", "cert_id", "ts",
    )

    def __init__(self, raw: dict):
        self.signal_id: str = raw["signal_id"]
        self.model_id: str = raw["model_id"]
        self.model_version: str = raw.get("model_version", "")
        self.prediction: dict = raw.get("prediction") or {}
        self.live_sharpe_30d: Optional[float] = raw.get("live_sharpe_30d")
        self.tested_capacity_usd: float = raw.get("tested_capacity_usd") or 0.0
        self.cert_id: Optional[str] = raw.get("cert_id")
        ts = raw.get("ts")
        self.ts = datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc)

    # Convenience: extract trading signal from prediction payload.
    # Models follow convention: {"asset": "ETH", "direction": "long"|"short",
    #                            "edge_bps": 15, "expected_vol_bps": 80, ...}
    @property
    def asset(self) -> Optional[str]:
        return (self.prediction or {}).get("asset")

    @property
    def direction(self) -> Optional[str]:
        return (self.prediction or {}).get("direction")

    @property
    def edge_bps(self) -> Optional[float]:
        return (self.prediction or {}).get("edge_bps")

    @property
    def expected_vol_bps(self) -> Optional[float]:
        return (self.prediction or {}).get("expected_vol_bps")

    def is_tradeable(self, min_sharpe: float, max_age_s: int) -> tuple[bool, str]:
        if not self.asset or self.direction not in ("long", "short"):
            return False, "no_asset_or_direction"
        if self.asset not in settings.enabled_assets:
            return False, f"asset_{self.asset}_disabled"
        if self.live_sharpe_30d is None or self.live_sharpe_30d < min_sharpe:
            return False, f"sharpe_{self.live_sharpe_30d}<{min_sharpe}"
        if (datetime.now(timezone.utc) - self.ts).total_seconds() > max_age_s:
            return False, "stale"
        if self.edge_bps is None or self.expected_vol_bps is None:
            return False, "missing_edge_or_vol"
        return True, "ok"

class SignalBus:
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pubsub = None

    async def connect(self):
        self._client = redis.from_url(settings.redis_url, decode_responses=True)
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(settings.signal_channel)
        log.info("signal_bus_connected", extra={"channel": settings.signal_channel})

    async def close(self):
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._client:
            await self._client.close()

    async def consume(self) -> AsyncIterator[Signal]:
        if not self._pubsub:
            await self.connect()
        async for msg in self._pubsub.listen():
            if msg.get("type") != "message":
                continue
            try:
                raw = json.loads(msg["data"])
                yield Signal(raw)
            except Exception:
                log.exception("signal_parse_failed")
                continue
