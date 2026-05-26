"""Portfolio state maintenance: open positions, daily PnL bookkeeping."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AllocatorPosition, AllocatorTrade, DailyPnl
from app.executor.base import Executor

log = logging.getLogger("allocator.state")

async def upsert_position_after_trade(
    db: AsyncSession,
    asset: str,
    side: str,
    trade: AllocatorTrade,
):
    """Increment or open a position for (asset, side)."""
    q = await db.execute(
        select(AllocatorPosition).where(
            AllocatorPosition.asset == asset,
            AllocatorPosition.side == side,
            AllocatorPosition.is_open == True,  # noqa: E712
        )
    )
    pos = q.scalar_one_or_none()

    if pos is None:
        pos = AllocatorPosition(
            id=uuid.uuid4(),
            asset=asset,
            side=side,
            size_usd=trade.size_usd,
            entry_price=trade.price,
            mark_price=trade.price,
        )
        db.add(pos)
    else:
        # Weighted-average entry
        total_size = pos.size_usd + trade.size_usd
        pos.entry_price = (
            (pos.entry_price * pos.size_usd + trade.price * trade.size_usd) / total_size
        )
        pos.size_usd = total_size

    await db.commit()

async def ensure_daily_pnl_row(db: AsyncSession) -> DailyPnl:
    today = datetime.now(timezone.utc).date().isoformat()
    row = await db.get(DailyPnl, today)
    if row is None:
        row = DailyPnl(date=today, starting_aum_usd=settings.aum_usd)
        db.add(row)
        await db.commit()
    return row

async def refresh_marks_and_unrealized(db: AsyncSession, executor: Executor):
    """Periodic task: pull mark prices, update unrealized PnL on all open positions."""
    q = await db.execute(select(AllocatorPosition).where(AllocatorPosition.is_open == True))  # noqa
    positions = q.scalars().all()

    total_unrealized = 0.0
    by_asset: dict[str, float] = {}

    for p in positions:
        try:
            if p.asset not in by_asset:
                by_asset[p.asset] = await executor.get_mark_price(p.asset)
            mark = by_asset[p.asset]
        except Exception:
            log.exception("mark_fetch_failed", extra={"asset": p.asset})
            continue

        pnl_per_unit_pct = (mark - p.entry_price) / p.entry_price
        sign = 1 if p.side == "long" else -1
        pnl_usd = sign * pnl_per_unit_pct * p.size_usd

        await db.execute(
            update(AllocatorPosition)
            .where(AllocatorPosition.id == p.id)
            .values(mark_price=mark, unrealized_pnl_usd=pnl_usd)
        )
        total_unrealized += pnl_usd

    # Update today's row
    today_row = await ensure_daily_pnl_row(db)
    today_row.unrealized_pnl_usd = total_unrealized
    await db.commit()
