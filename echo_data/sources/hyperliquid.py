"""Hyperliquid OHLCV / funding / OI / orderbook source.

Two channels:
- REST `info` endpoint for snapshot + backfill
- WebSocket for live OHLCV + funding

Why HL as primary:
- Single source for spot-equivalent perp + funding + OI
- Public API, no auth
- Same venue as our allocator → no basis confusion
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Optional

import httpx
import websockets

from echo_data.sources.base import DataSource, SourceRecord

log = logging.getLogger("echo_data.hl")

REST_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"

class HyperliquidOhlcvSource(DataSource):
    """1h candles via REST polling (no canonical 1h stream on HL)."""

    name = "hyperliquid_ohlcv_1h"
    kind = "ohlcv"

    def __init__(self, assets: list[str], interval: str = "1h"):
        self.assets = [a.upper() for a in assets]
        self.interval = interval
        self._client = httpx.AsyncClient(timeout=10.0)

    async def fetch_latest(self, asset: str) -> Optional[SourceRecord]:
        # Hyperliquid info → candleSnapshot
        now_ms = int(time.time() * 1000)
        # Pull last ~200 bars
        body = {
            "type": "candleSnapshot",
            "req": {
                "coin": asset,
                "interval": self.interval,
                "startTime": now_ms - 200 * 3600 * 1000,
                "endTime": now_ms,
            },
        }
        try:
            r = await self._client.post(REST_URL, json=body)
            r.raise_for_status()
            bars = r.json()
        except Exception:
            log.exception("hl_fetch_failed", extra={"asset": asset})
            return None

        if not bars:
            return None

        # bars: [{"t": ms, "o": ..., "h": ..., "l": ..., "c": ..., "v": ...}, ...]
        normalized = [
            {
                "ts": int(b["t"] // 1000),
                "open": float(b["o"]), "high": float(b["h"]),
                "low": float(b["l"]), "close": float(b["c"]),
                "volume": float(b["v"]),
            }
            for b in bars
        ]
        return SourceRecord(
            source=self.name,
            asset=asset,
            ts=normalized[-1]["ts"],
            kind="ohlcv",
            payload={"interval": self.interval, "bars": normalized},
            ingested_at=int(time.time() * 1000),
        )

    async def stream(self, asset: str) -> AsyncIterator[SourceRecord]:
        """Poll every 60s on bar close. HL's WS has 1m candles but not 1h."""
        while True:
            try:
                rec = await self.fetch_latest(asset)
                if rec:
                    yield rec
            except Exception:
                log.exception("hl_stream_loop_error")
            await asyncio.sleep(60)

class HyperliquidFundingSource(DataSource):
    """Current funding rate per asset."""

    name = "hyperliquid_funding"
    kind = "funding"

    def __init__(self, assets: list[str]):
        self.assets = [a.upper() for a in assets]
        self._client = httpx.AsyncClient(timeout=10.0)

    async def fetch_latest(self, asset: str) -> Optional[SourceRecord]:
        try:
            r = await self._client.post(REST_URL, json={"type": "metaAndAssetCtxs"})
            r.raise_for_status()
            meta, ctxs = r.json()
            universe = meta.get("universe", [])
            idx = next((i for i, u in enumerate(universe) if u["name"] == asset), None)
            if idx is None or idx >= len(ctxs):
                return None
            ctx = ctxs[idx]
            funding = float(ctx.get("funding", 0))
            return SourceRecord(
                source=self.name, asset=asset, ts=int(time.time()),
                kind="funding",
                payload={"funding_rate": funding},
                ingested_at=int(time.time() * 1000),
            )
        except Exception:
            log.exception("hl_funding_failed", extra={"asset": asset})
            return None

    async def stream(self, asset: str):
        while True:
            rec = await self.fetch_latest(asset)
            if rec:
                yield rec
            await asyncio.sleep(30)  # funding updates hourly; 30s polls are plenty

class HyperliquidOpenInterestSource(DataSource):
    """Open interest in USD."""

    name = "hyperliquid_oi"
    kind = "oi"

    def __init__(self, assets: list[str]):
        self.assets = [a.upper() for a in assets]
        self._client = httpx.AsyncClient(timeout=10.0)

    async def fetch_latest(self, asset: str) -> Optional[SourceRecord]:
        try:
            r = await self._client.post(REST_URL, json={"type": "metaAndAssetCtxs"})
            r.raise_for_status()
            meta, ctxs = r.json()
            universe = meta.get("universe", [])
            idx = next((i for i, u in enumerate(universe) if u["name"] == asset), None)
            if idx is None:
                return None
            ctx = ctxs[idx]
            mark = float(ctx.get("markPx", 0))
            oi_coin = float(ctx.get("openInterest", 0))
            oi_usd = mark * oi_coin
            return SourceRecord(
                source=self.name, asset=asset, ts=int(time.time()),
                kind="oi",
                payload={"open_interest_usd": oi_usd, "mark_price": mark},
                ingested_at=int(time.time() * 1000),
            )
        except Exception:
            log.exception("hl_oi_failed", extra={"asset": asset})
            return None

    async def stream(self, asset: str):
        while True:
            rec = await self.fetch_latest(asset)
            if rec:
                yield rec
            await asyncio.sleep(30)

class HyperliquidOrderbookSource(DataSource):
    """L2 orderbook → summarized snapshot.

    We don't store full L2 (too much volume); we extract:
    - bid_price, ask_price
    - cumulative top-10 size on each side
    - spread_bps
    """

    name = "hyperliquid_orderbook"
    kind = "orderbook"

    def __init__(self, assets: list[str]):
        self.assets = [a.upper() for a in assets]
        self._client = httpx.AsyncClient(timeout=10.0)

    async def fetch_latest(self, asset: str) -> Optional[SourceRecord]:
        try:
            r = await self._client.post(REST_URL, json={"type": "l2Book", "coin": asset})
            r.raise_for_status()
            book = r.json()
            # book: {"levels": [bids[], asks[]]}
            levels = book.get("levels", [[], []])
            bids = levels[0][:10] if levels else []
            asks = levels[1][:10] if len(levels) > 1 else []
            if not bids or not asks:
                return None
            bid_price = float(bids[0]["px"])
            ask_price = float(asks[0]["px"])
            bid_size = sum(float(b["sz"]) for b in bids)
            ask_size = sum(float(a["sz"]) for a in asks)
            spread_bps = (ask_price - bid_price) / bid_price * 1e4
            return SourceRecord(
                source=self.name, asset=asset, ts=int(time.time()),
                kind="orderbook",
                payload={
                    "bid_price": bid_price, "ask_price": ask_price,
                    "bid_size_top10": bid_size, "ask_size_top10": ask_size,
                    "spread_bps": spread_bps,
                },
                ingested_at=int(time.time() * 1000),
            )
        except Exception:
            log.exception("hl_book_failed", extra={"asset": asset})
            return None

    async def stream(self, asset: str):
        # Use WS for live book; here we poll for simplicity
        while True:
            rec = await self.fetch_latest(asset)
            if rec:
                yield rec
            await asyncio.sleep(2)
