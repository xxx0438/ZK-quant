"""Record signal → trade attribution and publish to public feed."""
import json
import logging
import uuid
from datetime import datetime, timezone

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AllocatorTrade, AttributionLink
from app.executor.base import OrderResult
from app.signal_bus import Signal

log = logging.getLogger("allocator.attribution")

_redis: redis.Redis | None = None

def _r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis

async def record_trade_and_attribution(
    db: AsyncSession,
    signal: Signal,
    side: str,
    result: OrderResult,
) -> AllocatorTrade:
    """Persist the trade + its link to the originating signal, then broadcast."""
    trade = AllocatorTrade(
        id=uuid.uuid4(),
        asset=signal.asset,
        side=side,
        size_usd=result.fill_size_usd,
        price=result.fill_price,
        fee_usd=result.fee_usd,
        venue=result.venue,
        venue_order_id=result.order_id,
        venue_fill_id=result.fill_id,
        is_close=False,
    )
    db.add(trade)
    await db.flush()

    link = AttributionLink(
        id=uuid.uuid4(),
        signal_id=signal.signal_id,
        model_id=signal.model_id,
        trade_id=trade.id,
        expected_edge_bps=signal.edge_bps,
    )
    db.add(link)
    await db.commit()

    # Public feed event
    payload = {
        "type": "trade_executed",
        "ts": datetime.now(timezone.utc).isoformat(),
        "trade_id": str(trade.id),
        "asset": signal.asset,
        "side": side,
        "size_usd": result.fill_size_usd,
        "price": result.fill_price,
        "attribution": {
            "model_id": signal.model_id,
            "signal_id": signal.signal_id,
            "expected_edge_bps": signal.edge_bps,
            "cert_id": signal.cert_id,
        },
        "venue": result.venue,
        "venue_order_id": result.order_id,
    }
    try:
        await _r().publish(settings.publish_channel, json.dumps(payload, default=str))
    except Exception:
        log.exception("publish_failed")

    log.info(
        "trade_recorded",
        extra={
            "trade_id": str(trade.id),
            "signal_id": signal.signal_id,
            "model_id": signal.model_id,
            "asset": signal.asset,
            "size_usd": result.fill_size_usd,
        },
    )
    return trade
