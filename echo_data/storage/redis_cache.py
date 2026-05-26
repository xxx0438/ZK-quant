"""Hot data cache. Sub-second SLA for /v1/predict.

Strategy:
- Workers continuously update keys: `latest:<asset>:<kind>`
- SnapshotBuilder reads from Redis first; falls back to Timescale on miss
- Snapshot binaries are cached in Redis for 7 days for fast replay
"""
from __future__ import annotations

import logging
from typing import Optional

import orjson
import redis.asyncio as redis

log = logging.getLogger("echo_data.cache")

class RedisCache:
    def __init__(self, redis_url: str):
        self._client = redis.from_url(redis_url, decode_responses=False)

    async def close(self):
        await self._client.close()

    # ─── Latest readings ───

    async def set_latest(self, asset: str, kind: str, payload: dict, ts: int) -> None:
        key = f"latest:{asset}:{kind}"
        body = {"ts": ts, "payload": payload}
        await self._client.set(key, orjson.dumps(body))

    async def get_latest(self, asset: str, kind: str) -> Optional[tuple[int, dict]]:
        key = f"latest:{asset}:{kind}"
        raw = await self._client.get(key)
        if not raw:
            return None
        try:
            body = orjson.loads(raw)
            return int(body["ts"]), body["payload"]
        except Exception:
            return None

    # ─── Recent OHLCV ring buffer ───

    async def push_bar(self, asset: str, interval: str, bar: dict) -> None:
        """Push a bar to a sorted list; keep last 500."""
        key = f"bars:{asset}:{interval}"
        await self._client.zadd(key, {orjson.dumps(bar): bar["ts"]})
        # Trim to last 500
        await self._client.zremrangebyrank(key, 0, -501)

    async def get_recent_bars(self, asset: str, interval: str, n: int = 200) -> list[dict]:
        key = f"bars:{asset}:{interval}"
        raw = await self._client.zrange(key, -n, -1)
        return [orjson.loads(b) for b in raw]

    # ─── Snapshot binary cache ───

    async def cache_snapshot(self, snapshot_hash: str, body: bytes, ttl_s: int = 7 * 86400) -> None:
        await self._client.setex(f"snap:{snapshot_hash}", ttl_s, body)

    async def get_snapshot(self, snapshot_hash: str) -> Optional[bytes]:
        return await self._client.get(f"snap:{snapshot_hash}")
