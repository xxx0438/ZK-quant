"""Protocol that every data source adapter implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SourceConfig:
    enabled: bool = True
    rate_limit_per_sec: float = 10.0
    timeout_sec: float = 10.0
    reconnect_backoff_sec: float = 2.0
    max_reconnect_backoff_sec: float = 60.0

class DataSource(ABC):
    """Base for all data sources.

    Each source produces rows for a specific table via DataWriter.
    Sources own their own connection lifecycle (WS) and rate limiting.
    """

    name: str           # "hyperliquid", "coingecko", "goldsky"
    table: str          # destination hypertable

    def __init__(self, config: SourceConfig):
        self.config = config

    @abstractmethod
    async def run(self, writer, assets: list[str]) -> None:
        """Run forever. On error, log and reconnect with backoff."""
        ...
