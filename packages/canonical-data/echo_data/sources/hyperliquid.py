"""Hyperliquid websocket + REST adapter.

What we collect:
  - 1m & 1h OHLCV  (subscribe to candle feed)
  - Funding rate    (REST poll every 60s)
  - Open interest   (REST poll every 60s)
  - L2 orderbook    (subscribe, sample every 1s into TimescaleDB)

Hyperliquid SDK is sync, so we wrap with asyncio.to_thread.
WebSocket is direct: `wss://api.hyperliquid.xyz/ws`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets

from echo_data.sources.base import DataSource, SourceConfig
from echo_data.writer import DataWriter

log = logging.getLogger("echo_data.sources.hyperliquid")

WS_URL = "wss://api.hyperliquid.xyz/ws"
REST_URL = "https://api.hyperliquid.xyz/info"

class HyperliquidCandles(DataSource):
    name = "hyperliquid"
    table = "ohlcv"

    def __init__(self, config: SourceConfig | None = None,
                 intervals: tuple[str, ...] = ("1m", "1h")):
        super().__init__(config or SourceConfig())
        self.intervals = intervals

    async def run(self, writer: DataWriter, assets: list[str]) -> None:
        backoff = self.config.reconnect_backoff_sec
        while True:
            try:
                await self._stream(writer, assets)
                backoff = self.config.reconnect_backoff_sec
            except Exception as e:
                log.warning("hl_candle_disconnect", extra={"error": str(e), "backoff": backoff})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.config.max_reconnect_backoff_sec)

    async def _stream(self, writer: DataWriter, assets: list[str]) -> None:
        async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=10) as ws:
            # Subscribe to all (asset, interval) combos
            for asset in assets:
                for itv in self.intervals:
                    sub = {
                        "method": "subscribe",
                        "subscription": {"type": "candle", "coin": asset, "interval": itv},
                    }
                    await ws.send(json.dumps(sub))

            log.info("hl_candles_subscribed", extra={"assets": assets, "intervals": list(self.intervals)})

            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("channel") != "candle":
                    continue
                d = msg.get("data") or {}
                if not d.get("T"):  # closing time
                    continue
                # HL sends each candle update; we only persist on close
                # by checking if "T" (close ts in ms) <= now
                if d["T"] > int(time.time() * 1000):
                    continue

                await writer.write({
                    "ts": datetime.fromtimestamp(d["t"] / 1000, tz=timezone.utc),
                    "asset": d["s"],
                    "interval": d["i"],
                    "source": self.name,
                    "open": float(d["o"]),
                    "high": float(d["h"]),
                    "low": float(d["l"]),
                    "close": float(d["c"]),
                    "volume": float(d["v"]),
                })

class HyperliquidFundingOI(DataSource):
    """Polls /info for current funding and OI per asset. 60s cadence."""

    name = "hyperliquid"
    table = "funding_rate"  # also writes open_interest

    def __init__(self, config: SourceConfig | None = None, poll_secs: float = 60.0):
        super().__init__(config or SourceConfig())
        self.poll_secs = poll_secs

    async def run(self, writer: DataWriter, assets: list[str]) -> None:
        # writer is funding writer; we need a second one for OI inside main supervisor
        # For simplicity assume caller passes a tuple (funding_writer, oi_writer) via attribute
        oi_writer: DataWriter = getattr(self, "_oi_writer", None)
        if oi_writer is None:
            log.error("hl_funding_no_oi_writer")
            return

        async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
            while True:
                try:
                    r = await client.post(REST_URL, json={"type": "metaAndAssetCtxs"})
                    r.raise_for_status()
                    meta, ctxs = r.json()
                    universe = meta.get("universe", [])
                    now = datetime.now(timezone.utc)

                    for asset_meta, ctx in zip(universe, ctxs):
                        name = asset_meta.get("name", "").upper()
                        if name not in assets:
                            continue
                        funding = ctx.get("funding")
                        oi = ctx.get("openInterest")
                        mark = ctx.get("markPx")
                        if funding is not None:
                            await writer.write({
                                "ts": now, "asset": name, "source": "hyperliquid",
                                "rate": float(funding),
                            })
                        if oi is not None and mark is not None:
                            await oi_writer.write({
                                "ts": now, "asset": name, "source": "hyperliquid",
                                "oi_usd": float(oi) * float(mark),
                            })
                except Exception:
                    log.exception("hl_funding_poll_failed")

                await asyncio.sleep(self.poll_secs)

class HyperliquidOrderbook(DataSource):
    """L2 book stream; sample top-10 cumulative size every 1s."""

    name = "hyperliquid"
    table = "orderbook"

    SAMPLE_EVERY_SECONDS = 1.0

    async def run(self, writer: DataWriter, assets: list[str]) -> None:
        backoff = self.config.reconnect_backoff_sec
        while True:
            try:
                await self._stream(writer, assets)
                backoff = self.config.reconnect_backoff_sec
            except Exception:
                log.exception("hl_ob_disconnect")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.config.max_reconnect_backoff_sec)

    async def _stream(self, writer: DataWriter, assets: list[str]) -> None:
        last_sample: dict[str, float] = {}
        async with websockets.connect(WS_URL, ping_interval=20) as ws:
            for asset in assets:
                await ws.send(json.dumps({
                    "method": "subscribe",
                    "subscription": {"type": "l2Book", "coin": asset},
                }))
            log.info("hl_orderbook_subscribed", extra={"assets": assets})

            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("channel") != "l2Book":
                    continue
                d = msg.get("data") or {}
                coin = d.get("coin", "").upper()
                if not coin:
                    continue

                now = time.time()
                if now - last_sample.get(coin, 0) < self.SAMPLE_EVERY_SECONDS:
                    continue
                last_sample[coin] = now

                # levels: [bids, asks], each = list of {px, sz, n}
                levels = d.get("levels") or [[], []]
                bids, asks = levels[0], levels[1]
                if not bids or not asks:
                    continue

                bid_top = float(bids[0]["px"])
                ask_top = float(asks[0]["px"])
                bid_sz10 = sum(float(x["sz"]) for x in bids[:10])
                ask_sz10 = sum(float(x["sz"]) for x in asks[:10])
                mid = (bid_top + ask_top) / 2
                spread_bps = (ask_top - bid_top) / mid * 1e4 if mid > 0 else 0

                await writer.write({
                    "ts": datetime.fromtimestamp(now, tz=timezone.utc),
                    "asset": coin,
                    "source": "hyperliquid",
                    "bid_price": bid_top,
                    "ask_price": ask_top,
                    "bid_size_top10": bid_sz10,
                    "ask_size_top10": ask_sz10,
                    "spread_bps": spread_bps,
                })
