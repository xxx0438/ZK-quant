"""CoinGecko spot price poller (fallback / cross-check source).

Why CoinGecko:
- Free tier covers our needs
- Aggregates across many spot venues → more robust "true price"
- Useful for cross-checking against Hyperliquid mark price

Cadence: 60s. Pro tier allows higher; not needed for v0.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

from echo_data.sources.base import DataSource, SourceConfig
from echo_data.writer import DataWriter

log = logging.getLogger("echo_data.sources.coingecko")

# Map our asset symbol → CoinGecko ID
COIN_IDS = {
    "BTC": "b
