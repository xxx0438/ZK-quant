"""Historical storage in TimescaleDB.

Why Timescale (vs raw Postgres):
- Hypertables auto-partition by time → fast inserts even with billions of rows
- Continuous aggregates → cheap 1h/4h rollups from 1m data
- Native time_bucket() for snapshot construction
- Compression after 7d → 10-20x storage savings

Tables:
  ohlcv_bars             — every candle, all intervals
  funding_history        — 8h funding readings
  oi_history             — periodic OI snapshots
  orderbook_summary      — periodic L2 summaries
  onchain_history        — periodic onchain metrics
  snapshots              — every Inputs we built (the canonical record)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from echo_data.sources.base import SourceRecord
from echo_data.schema import StoredSnapshot

log = logging.getLogger("echo_data.timescale")

class TimescaleStore:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True, pool_size=5)
        self.Session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def close(self):
        await self.engine.dispose()

    # ─── Writes ───

    async def write_source_record(self, rec: SourceRecord) -> None:
        """Route a SourceRecord to the right hypertable."""
        async with self.Session() as s:
            if rec.kind == "ohlcv":
                await self._write_ohlcv(s, rec)
            elif rec.kind == "funding":
                await self._write_funding(s, rec)
            elif rec.kind == "oi":
                await self._write_oi(s, rec)
            elif rec.kind == "orderbook":
                await self._write_orderbook(s, rec)
            elif rec.kind == "onchain":
                await self._write_onchain(s, rec)
            await s.commit()

    async def _write_ohlcv(self, s: AsyncSession, rec: SourceRecord):
        bars = rec.payload.get("bars", [])
        interval = rec.payload.get("interval", "1h")
        # Bulk upsert
        for bar in bars:
            await s.execute(
                text("""
                    INSERT INTO ohlcv_bars (asset, interval, ts, open, high, low, close, volume, source)
                    VALUES (:asset, :interval, to_timestamp(:ts), :open, :high, :low, :close, :volume, :source)
                    ON CONFLICT (asset, interval, ts) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """),
                {
                    "asset": rec.asset, "interval": interval, "ts": bar["ts"],
                    "open": bar["open"], "high": bar["high"], "low": bar["low"],
                    "close": bar["close"], "volume": bar["volume"], "source": rec.source,
                },
            )

    async def _write_funding(self, s: AsyncSession, rec: SourceRecord):
        await s.execute(
            text("""
                INSERT INTO funding_history (asset, ts, funding_rate, source)
                VALUES (:asset, to_timestamp(:ts), :rate, :source)
                ON CONFLICT (asset, ts) DO UPDATE SET funding_rate = EXCLUDED.funding_rate
            """),
            {
                "asset": rec.asset, "ts": rec.ts,
                "rate": rec.payload.get("funding_rate"), "source": rec.source,
            },
        )

    async def _write_oi(self, s: AsyncSession, rec: SourceRecord):
        await s.execute(
            text("""
                INSERT INTO oi_history (asset, ts, open_interest_usd, mark_price, source)
                VALUES (:asset, to_timestamp(:ts), :oi, :mark, :source)
                ON CONFLICT (asset, ts) DO UPDATE SET
                    open_interest_usd = EXCLUDED.open_interest_usd,
                    mark_price = EXCLUDED.mark_price
            """),
            {
                "asset": rec.asset, "ts": rec.ts,
                "oi": rec.payload.get("open_interest_usd"),
                "mark": rec.payload.get("mark_price"),
                "source": rec.source,
            },
        )

    async def _write_orderbook(self, s: AsyncSession, rec: SourceRecord):
        await s.execute(
            text("""
                INSERT INTO orderbook_summary
                    (asset, ts, bid_price, ask_price, bid_size_top10, ask_size_top10, spread_bps, source)
                VALUES
                    (:asset, to_timestamp(:ts), :bid, :ask, :bs, :as_, :spread, :source)
            """),
            {
                "asset": rec.asset, "ts": rec.ts,
                "bid": rec.payload.get("bid_price"), "ask": rec.payload.get("ask_price"),
                "bs": rec.payload.get("bid_size_top10"), "as_": rec.payload.get("ask_size_top10"),
                "spread": rec.payload.get("spread_bps"), "source": rec.source,
            },
        )

    async def _write_onchain(self, s: AsyncSession, rec: SourceRecord):
        await s.execute(
            text("""
                INSERT INTO onchain_history (asset, ts, metric, value, payload, source)
                VALUES (:asset, to_timestamp(:ts), :metric, :value, :payload, :source)
            """),
            {
                "asset": rec.asset, "ts": rec.ts,
                "metric": list(rec.payload.keys())[0] if rec.payload else "",
                "value": next(iter(rec.payload.values()), 0) if rec.payload else 0,
                "payload": _orjson_dumps(rec.payload), "source": rec.source,
            },
        )

    # ─── Snapshots ───

    async def write_snapshot(self, snap: StoredSnapshot) -> None:
        async with self.Session() as s:
            await s.execute(
                text("""
                    INSERT INTO snapshots (snapshot_hash, asset, ts, inputs_json, schema_version, source_versions)
                    VALUES (:hash, :asset, to_timestamp(:ts), :inputs, :schema, :sv)
                    ON CONFLICT (snapshot_hash) DO NOTHING
                """),
                {
                    "hash": snap.snapshot_hash, "asset": snap.asset, "ts": snap.timestamp,
                    "inputs": snap.inputs_json,
                    "schema": snap.schema_version,
                    "sv": _orjson_dumps(snap.source_versions or {}),
                },
            )
            await s.commit()

    async def get_snapshot(self, snapshot_hash: str) -> Optional[StoredSnapshot]:
        async with self.Session() as s:
            r = await s.execute(
                text("""
                    SELECT snapshot_hash, asset, EXTRACT(EPOCH FROM ts)::bigint AS ts,
                           inputs_json, schema_version, source_versions, created_at
                    FROM snapshots WHERE snapshot_hash = :h
                """),
                {"h": snapshot_hash},
            )
            row = r.mappings().first()
            if not row:
                return None
            return StoredSnapshot(
                snapshot_hash=row["snapshot_hash"],
                asset=row["asset"],
                timestamp=row["ts"],
                inputs_json=bytes(row["inputs_json"]),
                schema_version=row["schema_version"],
                created_at=row["created_at"],
                source_versions=row["source_versions"],
            )

    # ─── Reads for snapshot building ───

    async def get_ohlcv(self, asset: str, interval: str, end_ts: int, limit: int = 200) -> list[dict]:
        async with self.Session() as s:
            r = await s.execute(
                text("""
                    SELECT EXTRACT(EPOCH FROM ts)::bigint AS ts,
                           open, high, low, close, volume
                    FROM ohlcv_bars
                    WHERE asset = :asset AND interval = :interval AND ts <= to_timestamp(:end)
                    ORDER BY ts DESC LIMIT :limit
                """),
                {"asset": asset, "interval": interval, "end": end_ts, "limit": limit},
            )
            rows = r.mappings().all()
            return [dict(row) for row in reversed(rows)]  # chronological

    async def get_latest_funding(self, asset: str, end_ts: int) -> Optional[float]:
        async with self.Session() as s:
            r = await s.execute(
                text("""
                    SELECT funding_rate FROM funding_history
                    WHERE asset = :asset AND ts <= to_timestamp(:end)
                    ORDER BY ts DESC LIMIT 1
                """),
                {"asset": asset, "end": end_ts},
            )
            row = r.first()
            return float(row[0]) if row else None

    async def get_latest_oi(self, asset: str, end_ts: int) -> Optional[float]:
        async with self.Session() as s:
            r = await s.execute(
                text("""
                    SELECT open_interest_usd FROM oi_history
                    WHERE asset = :asset AND ts <= to_timestamp(:end)
                    ORDER BY ts DESC LIMIT 1
                """),
                {"asset": asset, "end": end_ts},
            )
            row = r.first()
            return float(row[0]) if row else None

    async def get_latest_orderbook(self, asset: str, end_ts: int) -> Optional[dict]:
        async with self.Session() as s:
            r = await s.execute(
                text("""
                    SELECT bid_price, ask_price, bid_size_top10, ask_size_top10, spread_bps
                    FROM orderbook_summary
                    WHERE asset = :asset AND ts <= to_timestamp(:end)
                    ORDER BY ts DESC LIMIT 1
                """),
                {"asset": asset, "end": end_ts},
            )
            row = r.mappings().first()
            return dict(row) if row else None

    async def get_latest_onchain(self, asset: str, end_ts: int) -> dict:
        async with self.Session() as s:
            r = await s.execute(
                text("""
                    SELECT metric, value, payload
                    FROM onchain_history
                    WHERE asset = :asset AND ts <= to_timestamp(:end)
                    AND ts >= to_timestamp(:start)
                    ORDER BY ts DESC
                """),
                {"asset": asset, "end": end_ts, "start": end_ts - 86400},
            )
            out: dict = {}
            for row in r.mappings():
                metric = row["metric"]
                if metric not in out:  # take latest per metric
                    out[metric] = row["value"]
            return out

def _orjson_dumps(obj):
    import orjson
    return orjson.dumps(obj).decode() if obj is not None else "{}"
