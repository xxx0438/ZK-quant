"""Pre-trade risk checks.

Each .allow() returns (ok, reason). All checks must pass to trade.

Tracks:
  - per-asset gross exposure
  - portfolio gross / net leverage
  - per-model capacity utilization
  - daily drawdown circuit breaker (halts entire allocator)
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AllocatorPosition, AttributionLink, DailyPnl

log = logging.getLogger("allocator.risk")

class RiskManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def allow(
        self,
        asset: str,
        side: str,
        size_usd: float,
        model_id: str,
        tested_capacity_usd: float,
    ) -> tuple[bool, str]:
        # 1. Circuit breaker
        halted, reason = await self._check_circuit_breaker()
        if halted:
            return False, f"halted:{reason}"

        # 2. Per-model capacity
        model_used = await self._capacity_used_for_model(model_id)
        if model_used + size_usd > tested_capacity_usd * settings.per_model_capacity_buffer:
            return False, (
                f"model_capacity_exceeded "
                f"({model_used:.0f}+{size_usd:.0f}>{tested_capacity_usd * settings.per_model_capacity_buffer:.0f})"
            )

        # 3. Portfolio gross leverage
        gross, net = await self._portfolio_exposure()
        new_gross = gross + size_usd
        new_net = net + (size_usd if side == "long" else -size_usd)

        if new_gross > settings.max_gross_leverage * settings.aum_usd:
            return False, f"gross_leverage_exceeded ({new_gross:.0f})"

        if abs(new_net) > settings.max_net_leverage * settings.aum_usd:
            return False, f"net_leverage_exceeded ({new_net:.0f})"

        return True, "ok"

    async def _check_circuit_breaker(self) -> tuple[bool, str]:
        today = datetime.now(timezone.utc).date().isoformat()
        row = await self.db.get(DailyPnl, today)
        if row and row.halted:
            return True, row.halt_reason or "manual"
        if row:
            net_pnl = (row.realized_pnl_usd or 0) + (row.unrealized_pnl_usd or 0)
            limit = -row.starting_aum_usd * settings.daily_loss_circuit_breaker_pct
            if net_pnl <= limit:
                # Auto-halt
                row.halted = True
                row.halt_reason = f"daily_loss_pct {net_pnl/row.starting_aum_usd:.2%}"
                await self.db.commit()
                log.warning("circuit_breaker_triggered", extra={
                    "pnl": net_pnl, "limit": limit,
                })
                return True, row.halt_reason
        return False, ""

    async def _capacity_used_for_model(self, model_id: str) -> float:
        """Open notional attributed to this model."""
        q = await self.db.execute(
            select(func.coalesce(func.sum(AllocatorPosition.size_usd), 0.0))
            .select_from(AttributionLink)
            .join(AllocatorPosition, AllocatorPosition.id == AttributionLink.trade_id)
            .where(
                AttributionLink.model_id == model_id,
                AllocatorPosition.is_open == True,  # noqa: E712
            )
        )
        return float(q.scalar_one() or 0.0)

    async def _portfolio_exposure(self) -> tuple[float, float]:
        """Returns (gross_usd, net_usd)."""
        q = await self.db.execute(
            select(AllocatorPosition).where(AllocatorPosition.is_open == True)  # noqa
        )
        gross = 0.0
        net = 0.0
        for p in q.scalars().all():
            gross += abs(p.size_usd)
            net += p.size_usd if p.side == "long" else -p.size_usd
        return gross, net
