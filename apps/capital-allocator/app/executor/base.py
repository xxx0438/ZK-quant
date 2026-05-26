"""Executor interface so we can swap venues (Hyperliquid → Aerodrome → CEX → mock)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class OrderResult:
    ok: bool
    venue: str
    order_id: Optional[str]
    fill_id: Optional[str]
    fill_price: float
    fill_size_usd: float
    fee_usd: float
    error: Optional[str] = None

class Executor(ABC):
    @abstractmethod
    async def place_market(
        self,
        asset: str,
        side: str,            # "long" | "short"
        size_usd: float,
        max_slippage_bps: int = 20,
    ) -> OrderResult: ...

    @abstractmethod
    async def close(self, asset: str, side: str, size_usd: float) -> OrderResult: ...

    @abstractmethod
    async def get_mark_price(self, asset: str) -> float: ...
