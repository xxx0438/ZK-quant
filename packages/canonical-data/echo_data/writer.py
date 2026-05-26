"""Buffered writer used by ingestion workers.

Design: workers accumulate rows in memory, flush every N seconds or M rows.
Reduces DB roundtrips dramatically (1k rows / flush vs 1 row / 1k flushes).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import orjson
import redis.asyncio as redis
from sqlalchemy import text

from echo_data.timescale import connect

log = logging.getLogger("echo_data.writer")

@dataclass
class WriterStats:
    rows_written: int = 0
    flushes: int = 0
    last_flush_ts: float = 0
    last_error: str = ""

class DataWriter:
    """Buffered writer. One per worker.

    Usage:
        w = DataWriter(table="ohlcv", redis_url=..., flush_every_s=5)
        await w.start()
        await w.write({"ts": ..., "asset": ..., ...})
        await w.stop()
    """

    def __init__(
        self,
        table: str,
        redis_url: str,
        flush_every_s: float = 5.0,
        max_buffer: int = 1000,
    ):
        self.table = table
        self._buf: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_every = flush_every_s
        self._max_buffer = max_buffer
        self._redis_url = redis_url
        self._r: redis.Redis | None = None
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.stats = WriterStats()

    async def start(self):
        self._r = redis.from_url(self._redis_url, decode_responses=False)
        self._task = asyncio.create_task(self._flush_loop(), name=f"writer:{self.table}")

    async def stop(self):
        self._stop.set()
        if self._task:
            await self._task
        await self._flush()  # final flush
        if self._r:
            await self._r.close()

    async def write(self, row: dict[str, Any], publish_channel: str | None = None):
        async with self._lock:
            self._buf.append(row)
        if publish_channel and self._r:
            try:
                await self._r.publish(publish_channel, orjson.dumps(row))
            except Exception:
                # Pub/sub failures should never block ingestion
                log.warning("publish_failed", extra={"channel": publish_channel})
        if len(self._buf) >= self._max_buffer:
            await self._flush()

    async def heartbeat(self, worker_name: str, status: str, rows_1m: int, error: str = ""):
        async with connect() as conn:
            await conn.execute(
                text("""
                    INSERT INTO ingestion_heartbeat
                      (worker_name, last_seen, last_status, rows_written_1m, error_message)
                    VALUES (:w, now(), :s, :r, :e)
                    ON CONFLICT (worker_name) DO UPDATE SET
                      last_seen = EXCLUDED.last_seen,
                      last_status = EXCLUDED.last_status,
                      rows_written_1m = EXCLUDED.rows_written_1m,
                      error_message = EXCLUDED.error_message
                """),
                {"w": worker_name, "s": status, "r": rows_1m, "e": error},
            )
            await conn.commit()

    # ─── Internal ───

    async def _flush_loop(self):
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._flush_every)
            except asyncio.TimeoutError:
                pass
            await self._flush()

    async def _flush(self):
        async with self._lock:
            if not self._buf:
                return
            batch = self._buf
            self._buf = []

        sql = _INSERT_SQL.get(self.table)
        if not sql:
            log.error("no_insert_sql_for_table", extra={"table": self.table})
            return

        try:
            async with connect() as conn:
                await conn.execute(text(sql), batch)
                await conn.commit()
            self.stats.rows_written += len(batch)
            self.stats.flushes += 1
            self.stats.last_flush_ts = time.time()
            log.debug("flushed", extra={"table": self.table, "rows": len(batch)})
        except Exception as e:
            self.stats.last_error = str(e)
            log.exception("flush_failed", extra={"table": self.table, "rows": len(batch)})
            # Re-buffer for retry (capped to avoid memory bomb)
            async with self._lock:
                self._buf = batch[-self._max_buffer:] + self._buf

# Per-table UPSERT SQL. Using ON CONFLICT DO NOTHING keeps the writer
# idempotent in the face of websocket reconnects / overlapping polls.
_INSERT_SQL: dict[str, str] = {
    "ohlcv": """
        INSERT INTO ohlcv (ts, asset, interval, source, open, high, low, close, volume)
        VALUES (:ts, :asset, :interval, :source, :open, :high, :low, :close, :volume)
        ON CONFLICT (asset, interval, source, ts) DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume
    """,
    "funding_rate": """
        INSERT INTO funding_rate (ts, asset, source, rate)
        VALUES (:ts, :asset, :source, :rate)
        ON CONFLICT (asset, source, ts) DO NOTHING
    """,
    "open_interest": """
        INSERT INTO open_interest (ts, asset, source, oi_usd)
        VALUES (:ts, :asset, :source, :oi_usd)
        ON CONFLICT (asset, source, ts) DO NOTHING
    """,
    "orderbook": """
        INSERT INTO orderbook (ts, asset, source, bid_price, ask_price,
                                bid_size_top10, ask_size_top10, spread_bps)
        VALUES (:ts, :asset, :source, :bid_price, :ask_price,
                :bid_size_top10, :ask_size_top10, :spread_bps)
        ON CONFLICT (asset, source, ts) DO NOTHING
    """,
    "onchain_whale": """
        INSERT INTO onchain_whale (ts, asset, source, netflow_24h_usd,
                                    exchange_balance_usd, active_addresses_24h, extra)
        VALUES (:ts, :asset, :source, :netflow_24h_usd,
                :exchange_balance_usd, :active_addresses_24h, :extra::jsonb)
        ON CONFLICT (asset, source, ts) DO NOTHING
    """,
}
