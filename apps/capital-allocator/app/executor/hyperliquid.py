"""Hyperliquid execution.

Uses the official Python SDK (https://github.com/hyperliquid-dex/hyperliquid-python-sdk).
On testnet, set HYPERLIQUID_USE_TESTNET=true and use a testnet wallet.
"""
import asyncio
import logging
from typing import Optional

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from app.config import settings
from app.executor.base import Executor, OrderResult

log = logging.getLogger("allocator.executor.hl")

class HyperliquidExecutor(Executor):
    def __init__(self):
        base_url = (
            constants.TESTNET_API_URL
            if settings.hyperliquid_use_testnet
            else constants.MAINNET_API_URL
        )
        self._info = Info(base_url, skip_ws=True)
        wallet = Account.from_key(settings.hyperliquid_private_key)
        self._exchange = Exchange(
            wallet=wallet,
            base_url=base_url,
            account_address=settings.hyperliquid_wallet_address or wallet.address,
        )

    async def get_mark_price(self, asset: str) -> float:
        # info.all_mids() is sync; run in thread to avoid blocking
        mids = await asyncio.to_thread(self._info.all_mids)
        price = mids.get(asset)
        if price is None:
            raise ValueError(f"No mark for {asset}")
        return float(price)

    async def place_market(
        self,
        asset: str,
        side: str,
        size_usd: float,
        max_slippage_bps: int = 20,
    ) -> OrderResult:
        try:
            mark = await self.get_mark_price(asset)
            sz = size_usd / mark  # size in coin units
            is_buy = side == "long"

            # SDK call is sync
            res = await asyncio.to_thread(
                self._exchange.market_open,
                asset,
                is_buy,
                sz,
                None,                              # price (None = market)
                max_slippage_bps / 1e4,
            )

            if res.get("status") != "ok":
                return OrderResult(
                    ok=False, venue="hyperliquid", order_id=None, fill_id=None,
                    fill_price=0.0, fill_size_usd=0.0, fee_usd=0.0,
                    error=str(res),
                )

            statuses = res["response"]["data"]["statuses"]
            filled = next((s["filled"] for s in statuses if "filled" in s), None)
            if not filled:
                return OrderResult(
                    ok=False, venue="hyperliquid", order_id=None, fill_id=None,
                    fill_price=0.0, fill_size_usd=0.0, fee_usd=0.0,
                    error=f"not_filled: {statuses}",
                )

            fill_price = float(filled["avgPx"])
            fill_sz = float(filled["totalSz"])
            fill_usd = fill_price * fill_sz
            return OrderResult(
                ok=True,
                venue="hyperliquid",
                order_id=str(filled.get("oid")),
                fill_id=str(filled.get("tid", "")),
                fill_price=fill_price,
                fill_size_usd=fill_usd,
                fee_usd=fill_usd * 0.00035,     # Hyperliquid taker fee approx
            )
        except Exception as e:
            log.exception("hyperliquid_place_failed",
                          extra={"asset": asset, "side": side, "size_usd": size_usd})
            return OrderResult(
                ok=False, venue="hyperliquid", order_id=None, fill_id=None,
                fill_price=0.0, fill_size_usd=0.0, fee_usd=0.0,
                error=str(e),
            )

    async def close(self, asset: str, side: str, size_usd: float) -> OrderResult:
        # To close a long, we sell; to close a short, we buy
        closing_side = "short" if side == "long" else "long"
        result = await self.place_market(asset, closing_side, size_usd)
        return result

# Factory for swapping in tests
def get_executor() -> Executor:
    if settings.environment == "development" and not settings.hyperliquid_private_key:
        from app.executor.base import Executor as _Exec

        class MockExecutor(_Exec):
            _prices = {"BTC": 65000.0, "ETH": 3200.0, "SOL": 145.0}
            async def get_mark_price(self, asset): return self._prices.get(asset, 1.0)
            async def place_market(self, asset, side, size_usd, max_slippage_bps=20):
                px = self._prices.get(asset, 1.0)
                return OrderResult(True, "mock", f"mock_{asset}", "mock_fill",
                                   px, size_usd, size_usd * 0.0003)
            async def close(self, asset, side, size_usd):
                return await self.place_market(asset, "short" if side == "long" else "long", size_usd)

        log.warning("using_mock_executor")
        return MockExecutor()
    return HyperliquidExecutor()
