"""Arkham netflow source.

In production: use Arkham Intel API (whale → exchange flows).
For v0.4.3 dev: implement against a public CEX deposit/withdrawal heuristic
via Etherscan + known exchange addresses.

This file shows the structure; swap the data fetcher to Arkham when keys land.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import httpx

from echo_data.sources.base import DataSource, SourceRecord

log = logging.getLogger("echo_data.arkham")

# Known CEX hot wallets (sample). Real impl: 200+ addresses per chain.
CEX_HOT_WALLETS_ETH = {
    "binance": "0x28C6c06298d514Db089934071355E5743bf21d60",
    "coinbase": "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",
    "kraken": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
}

class WhaleNetflowSource(DataSource):
    """ETH whale netflow to/from CEX over last 24h.

    Positive = net inflow to CEX (bearish)
    Negative = net outflow from CEX (bullish accumulation)
    """

    name = "whale_netflow_eth"
    kind = "onchain"

    def __init__(self, assets: list[str] = None):
        self.assets = ["ETH"]
        self.api_key = os.getenv("ETHERSCAN_API_KEY", "")
        self._client = httpx.AsyncClient(timeout=15.0)

    async def fetch_latest(self, asset: str) -> Optional[SourceRecord]:
        if asset != "ETH":
            return None

        if not self.api_key:
            # Dev mode: return synthetic value for local testing
            return SourceRecord(
                source=self.name, asset="ETH", ts=int(time.time()),
                kind="onchain",
                payload={
                    "whale_netflow_24h_usd": 0.0,
                    "_synthetic": True,
                    "_note": "Set ETHERSCAN_API_KEY for real data",
                },
                ingested_at=int(time.time() * 1000),
            )

        # Real fetch: sum ETH inflows/outflows on each tracked CEX wallet in last 24h
        # For brevity, return synthetic until Arkham integration lands
        try:
            inflow_usd = 0.0
            outflow_usd = 0.0
            # ... real Etherscan calls would go here ...
            netflow = inflow_usd - outflow_usd
            return SourceRecord(
                source=self.name, asset="ETH", ts=int(time.time()),
                kind="onchain",
                payload={
                    "whale_netflow_24h_usd": netflow,
                    "inflow_usd": inflow_usd,
                    "outflow_usd": outflow_usd,
                },
                ingested_at=int(time.time() * 1000),
            )
        except Exception:
            log.exception("arkham_fetch_failed")
            return None

    async def stream(self, asset: str):
        while True:
            rec = await self.fetch_latest(asset)
            if rec:
                yield rec
            await asyncio.sleep(300)  # 5 min cadence
