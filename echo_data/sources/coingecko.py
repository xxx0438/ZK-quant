"""CoinGecko spot price source. Used to validate HL marks + as fallback."""
import asyncio
import logging
import time
from typing import Optional

import httpx

from echo_data.sources.base import DataSource, SourceRecord

log = logging.getLogger("echo_data.cg")

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

class CoingeckoSpotSource(DataSource):
    name = "coingecko_spot"
    kind = "spot_validation"

    def __init__(self, assets: list[str], api_key: str = ""):
        self.assets = [a.upper() for a in assets]
        self.api_key = api_key
        headers = {"x-cg-pro-api-key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(timeout=10.0, headers=headers)

    async def fetch_latest(self, asset: str) -> Optional[SourceRecord]:
        cg_id = COINGECKO_IDS.get(asset)
        if not cg_id:
            return None
        try:
            r = await self._client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd"},
            )
            r.raise_for_status()
            data = r.json()
            price = data.get(cg_id, {}).get("usd")
            if price is None:
                return None
            return SourceRecord(
                source=self.name, asset=asset, ts=int(time.time()),
                kind="spot_validation",
                payload={"spot_usd": float(price)},
                ingested_at=int(time.time() * 1000),
            )
        except Exception:
            log.exception("cg_spot_failed", extra={"asset": asset})
            return None

    async def stream(self, asset: str):
        while True:
            rec = await self.fetch_latest(asset)
            if rec:
                yield rec
            # Free tier: very rate-limited
            await asyncio.sleep(60)
