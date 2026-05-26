"""Deterministic snapshot construction.

A *snapshot* is the exact `Inputs` payload handed to a model at a moment in
time. It is:
  - **Deterministic**: same (asset, timestamp) → byte-identical snapshot
  - **Hashable**: sha256 over canonical JSON → snapshot_hash
  - **Archivable**: persisted to snapshot_archive for replay
  - **Cacheable**: Redis 1h TTL so /v1/predict doesn't re-query DB on duplicates

The snapshot_hash is what gets stored on each Prediction row. It is also what
allows quants and external auditors to *prove* a cert was generated from a
specific market state.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import orjson
import redis.asyncio as redis
from sqlalchemy import text

from echo_data.schema import Inputs, OHLCV, OnchainData, OrderbookSnapshot
from echo_data.timescale import connect

log = logging.getLogger("echo_data.snapshot")

# How far back to fetch OHLCV for each interval (in bars)
OHLCV_LOOKBACK = {
    "1h": 168,   # 1 week
    "4h": 90,    # 15 days
    "1d": 60,    # 2 months
}

# How fresh a snapshot in Redis cache can be (seconds)
CACHE_TTL = 300

class SnapshotBuilder:
    """Builds canonical Inputs from the data warehouse.

    Two modes:
      - live(asset)         : current market state, cache-friendly
      - historical(asset, t): specific timestamp, used for backtest export
    """

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._r: Optional[redis.Redis] = None

    def _redis(self) -> redis.Redis:
        if self._r is None:
            self._r = redis.from_url(self._redis_url, decode_responses=False)
        return self._r

    # ───────────────────── Public API ─────────────────────

    async def live(self, asset: str) -> tuple[Inputs, str]:
        """Build a snapshot of the current market for `asset`.

        Cache: 5s TTL keyed by (asset, current_minute) so bursts of
        /v1/predict calls in the same minute share one snapshot.
        """
        asset = asset.upper()
        now = datetime.now(timezone.utc)
        bucket = now.replace(second=0, microsecond=0)  # 1-min bucket
        cache_key = f"snap:live:{asset}:{int(bucket.timestamp())}"

        cached = await self._redis().get(cache_key)
        if cached:
            payload = orjson.loads(cached)
            return Inputs.model_validate(payload), payload["snapshot_hash"]

        snapshot, snap_hash = await self._build(asset, ts=now)

        # Cache + archive (archive runs lazily; don't block the API path)
        await self._redis().setex(
            cache_key,
            CACHE_TTL,
            orjson.dumps(snapshot.model_dump(mode="json") | {"snapshot_hash": snap_hash}),
        )
        # Archive is fire-and-forget
        try:
            await self._archive(snap_hash, snapshot)
        except Exception:
            log.exception("snapshot_archive_failed", extra={"hash": snap_hash})

        return snapshot, snap_hash

    async def historical(self, asset: str, ts: datetime) -> tuple[Inputs, str]:
        """Build a snapshot at a specific historical timestamp.
        Used for dataset export, replay, audit, backtest.
        """
        asset = asset.upper()
        return await self._build(asset, ts=ts)

    async def replay(self, snapshot_hash: str) -> Optional[Inputs]:
        """Retrieve an archived snapshot by hash. Used by `verify-cert` flows."""
        # Try Redis first
        cached = await self._redis().get(f"snap:archive:{snapshot_hash}")
        if cached:
            payload = orjson.loads(cached)
            return Inputs.model_validate(payload)

        # Fall back to DB
        async with connect() as conn:
            row = await conn.execute(
                text("SELECT payload FROM snapshot_archive WHERE snapshot_hash = :h"),
                {"h": snapshot_hash},
            )
            r = row.first()
            if not r:
                return None
            return Inputs.model_validate(r.payload)

    # ───────────────────── Internal ─────────────────────

    async def _build(self, asset: str, ts: datetime) -> tuple[Inputs, str]:
        """Fetch all fields in parallel and assemble an Inputs."""
        t0 = time.time()
        async with connect() as conn:
            # Parallel fetches via gather would require multiple connections;
            # for v0 we keep it sequential within one conn (fast enough since
            # all queries hit indexed hypertables).
            ohlcv_1h = await self._fetch_ohlcv(conn, asset, "1h", ts, OHLCV_LOOKBACK["1h"])
            ohlcv_4h = await self._fetch_ohlcv(conn, asset, "4h", ts, OHLCV_LOOKBACK["4h"])
            funding = await self._fetch_latest_funding(conn, asset, ts)
            oi = await self._fetch_latest_oi(conn, asset, ts)
            orderbook = await self._fetch_orderbook(conn, asset, ts)
            onchain = await self._fetch_onchain(conn, asset, ts)

        # Build (without hash field yet — hash is computed over the canonical
        # form *excluding* snapshot_hash itself; otherwise we'd have a fixpoint).
        snapshot = Inputs(
            asset=asset,
            timestamp=int(ts.timestamp()),
            ohlcv_1h=ohlcv_1h,
            ohlcv_4h=ohlcv_4h,
            funding_rate=funding,
            open_interest_usd=oi,
            orderbook=orderbook,
            onchain=onchain,
        )

        snap_hash = _hash_snapshot(snapshot)
        snapshot.snapshot_hash = snap_hash

        log.info(
            "snapshot_built",
            extra={
                "asset": asset, "hash": snap_hash[:12],
                "ms": int((time.time() - t0) * 1000),
                "n_1h": len(ohlcv_1h), "n_4h": len(ohlcv_4h),
            },
        )
        return snapshot, snap_hash

    async def _fetch_ohlcv(self, conn, asset: str, interval: str,
                            ts: datetime, n: int) -> list[OHLCV]:
        """Most recent N bars at or before `ts`."""
        rows = await conn.execute(
            text("""
                SELECT ts, open, high, low, close, volume
                FROM ohlcv
                WHERE asset = :a AND interval = :i AND ts <= :ts
                  AND source = COALESCE(
                      (SELECT source FROM ohlcv
                       WHERE asset = :a AND interval = :i AND ts <= :ts
                       ORDER BY ts DESC LIMIT 1),
                      'hyperliquid')
                ORDER BY ts DESC
                LIMIT :n
            """),
            {"a": asset, "i": interval, "ts": ts, "n": n},
        )
        out = [
            OHLCV(
                ts=int(r.ts.timestamp()),
                open=r.open, high=r.high, low=r.low,
                close=r.close, volume=r.volume,
            )
            for r in rows.all()
        ]
        out.reverse()  # chronological (oldest → newest)
        return out

    async def _fetch_latest_funding(self, conn, asset: str, ts: datetime) -> Optional[float]:
        # Funding within last 8h (otherwise considered stale)
        cutoff = ts - timedelta(hours=8)
        row = await conn.execute(
            text("""
                SELECT rate FROM funding_rate
                WHERE asset = :a AND ts <= :ts AND ts >= :cutoff
                ORDER BY ts DESC LIMIT 1
            """),
            {"a": asset, "ts": ts, "cutoff": cutoff},
        )
        r = row.first()
        return float(r.rate) if r else None

    async def _fetch_latest_oi(self, conn, asset: str, ts: datetime) -> Optional[float]:
        cutoff = ts - timedelta(minutes=15)
        row = await conn.execute(
            text("""
                SELECT oi_usd FROM open_interest
                WHERE asset = :a AND ts <= :ts AND ts >= :cutoff
                ORDER BY ts DESC LIMIT 1
            """),
            {"a": asset, "ts": ts, "cutoff": cutoff},
        )
        r = row.first()
        return float(r.oi_usd) if r else None

    async def _fetch_orderbook(self, conn, asset: str, ts: datetime) -> Optional[OrderbookSnapshot]:
        cutoff = ts - timedelta(minutes=2)
        row = await conn.execute(
            text("""
                SELECT bid_price, ask_price, bid_size_top10, ask_size_top10, spread_bps
                FROM orderbook
                WHERE asset = :a AND ts <= :ts AND ts >= :cutoff
                ORDER BY ts DESC LIMIT 1
            """),
            {"a": asset, "ts": ts, "cutoff": cutoff},
        )
        r = row.first()
        if not r:
            return None
        return OrderbookSnapshot(
            bid_price=r.bid_price, ask_price=r.ask_price,
            bid_size_top10=r.bid_size_top10, ask_size_top10=r.ask_size_top10,
            spread_bps=r.spread_bps,
        )

    async def _fetch_onchain(self, conn, asset: str, ts: datetime) -> Optional[OnchainData]:
        # Onchain rolls up hourly; tolerate up to 2h staleness
        cutoff = ts - timedelta(hours=2)
        row = await conn.execute(
            text("""
                SELECT netflow_24h_usd, exchange_balance_usd, active_addresses_24h, extra
                FROM onchain_whale
                WHERE asset = :a AND ts <= :ts AND ts >= :cutoff
                ORDER BY ts DESC LIMIT 1
            """),
            {"a": asset, "ts": ts, "cutoff": cutoff},
        )
        r = row.first()
        if not r:
            return None
        return OnchainData(
            whale_netflow_24h_usd=r.netflow_24h_usd,
            exchange_balance_usd=r.exchange_balance_usd,
            active_addresses_24h=r.active_addresses_24h,
            extra=r.extra,
        )

    async def _archive(self, snap_hash: str, snapshot: Inputs):
        """Persist snapshot to long-term storage. Idempotent (ON CONFLICT)."""
        payload = orjson.dumps(snapshot.model_dump(mode="json")).decode()
        async with connect() as conn:
            await conn.execute(
                text("""
                    INSERT INTO snapshot_archive (snapshot_hash, asset, timestamp, payload)
                    VALUES (:h, :a, to_timestamp(:t), :p::jsonb)
                    ON CONFLICT (snapshot_hash) DO NOTHING
                """),
                {
                    "h": snap_hash, "a": snapshot.asset,
                    "t": snapshot.timestamp, "p": payload,
                },
            )
            await conn.commit()
        # Also Redis cache for hot replay
        await self._redis().setex(
            f"snap:archive:{snap_hash}",
            86400,
            orjson.dumps(snapshot.model_dump(mode="json")),
        )

# ─────────────────── Helpers ───────────────────

def _hash_snapshot(snap: Inputs) -> str:
    """Canonical hash. Excludes snapshot_hash field itself."""
    payload = snap.model_dump(mode="json", exclude={"snapshot_hash"})
    canonical = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(canonical).hexdigest()
