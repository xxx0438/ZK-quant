"""Public-facing capital allocator data. Read-only, no auth required."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()

@router.get("/v1/capital/positions")
async def open_positions(db: AsyncSession = Depends(get_db)):
    """Currently open allocator positions, with attribution to source models."""
    # Allocator tables live in same DB; raw SQL keeps API decoupled from allocator ORM
    rows = await db.execute(
        text("""
            SELECT
              p.id, p.asset, p.side, p.size_usd, p.entry_price, p.mark_price,
              p.unrealized_pnl_usd, p.opened_at,
              array_agg(DISTINCT al.model_id) FILTER (WHERE al.model_id IS NOT NULL) AS contributing_models
            FROM allocator_positions p
            LEFT JOIN allocator_trades t ON t.asset = p.asset AND t.side = p.side
            LEFT JOIN attribution_links al ON al.trade_id = t.id
            WHERE p.is_open = true
            GROUP BY p.id
            ORDER BY p.opened_at DESC
        """)
    )
    positions = [dict(r._mapping) for r in rows.all()]
    return {"positions": positions, "count": len(positions)}

@router.get("/v1/capital/recent-trades")
async def recent_trades(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Last N executed trades with attribution."""
    rows = await db.execute(
        text("""
            SELECT
              t.id, t.asset, t.side, t.size_usd, t.price, t.fee_usd,
              t.venue, t.venue_order_id, t.timestamp,
              al.model_id, al.signal_id, al.expected_edge_bps
            FROM allocator_trades t
            LEFT JOIN attribution_links al ON al.trade_id = t.id
            ORDER BY t.timestamp DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return {"trades": [dict(r._mapping) for r in rows.all()]}

@router.get("/v1/capital/daily-pnl")
async def daily_pnl(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Historical daily PnL for transparency chart."""
    rows = await db.execute(
        text("""
            SELECT date, starting_aum_usd, ending_aum_usd,
                   realized_pnl_usd, unrealized_pnl_usd, fees_usd,
                   trades_count, halted
            FROM allocator_daily_pnl
            ORDER BY date DESC
            LIMIT :limit
        """),
        {"limit": days},
    )
    return {"daily": [dict(r._mapping) for r in rows.all()]}
