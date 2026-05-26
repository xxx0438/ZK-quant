"""Allocator agent main loop.

Two concurrent tasks:
  - signal_consumer:  reacts to predictions, places trades
  - mark_refresher:   every 30s, updates unrealized PnL + checks circuit breaker
"""
import asyncio
import logging
import signal as os_signal
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.attribution import record_trade_and_attribution
from app.config import settings
from app.executor.hyperliquid import get_executor
from app.risk_manager import RiskManager
from app.signal_bus import Signal, SignalBus
from app.sizer import kelly_size
from app.state import ensure_daily_pnl_row, refresh_marks_and_unrealized, upsert_position_after_trade

# ────────── Logging ──────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
log = logging.getLogger("allocator")
logging.basicConfig(level=settings.log_level)

# ────────── DB ──────────
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_shutdown = asyncio.Event()

# ────────── Pipeline ──────────
async def process_signal(signal: Signal, executor):
    ok_trade, reason = signal.is_tradeable(
        settings.signal_min_sharpe, settings.signal_max_age_seconds,
    )
    if not ok_trade:
        log.info("signal_skipped", extra={"signal_id": signal.signal_id, "reason": reason})
        return

    # Compute size
    size = kelly_size(signal.edge_bps, signal.expected_vol_bps, settings.aum_usd)
    if size.size_usd <= 0:
        log.info("size_zero", extra={"signal_id": signal.signal_id, "reason": size.rationale})
        return

    # Risk check
    async with SessionLocal() as db:
        risk = RiskManager(db)
        allowed, why = await risk.allow(
            asset=signal.asset,
            side=signal.direction,
            size_usd=size.size_usd,
            model_id=signal.model_id,
            tested_capacity_usd=signal.tested_capacity_usd,
        )
        if not allowed:
            log.info("risk_denied", extra={"signal_id": signal.signal_id, "why": why})
            return

    # Execute
    log.info(
        "executing",
        extra={
            "signal_id": signal.signal_id,
            "asset": signal.asset,
            "side": signal.direction,
            "size_usd": size.size_usd,
            "kelly_raw": size.kelly_raw,
        },
    )
    result = await executor.place_market(
        asset=signal.asset,
        side=signal.direction,
        size_usd=size.size_usd,
    )
    if not result.ok:
        log.error("execution_failed", extra={"signal_id": signal.signal_id, "err": result.error})
        return

    # Persist + attribute + broadcast
    async with SessionLocal() as db:
        trade = await record_trade_and_attribution(db, signal, signal.direction, result)
        await upsert_position_after_trade(db, signal.asset, signal.direction, trade)

        # Update daily trade count
        today = await ensure_daily_pnl_row(db)
        today.trades_count = (today.trades_count or 0) + 1
        today.fees_usd = (today.fees_usd or 0) + result.fee_usd
        await db.commit()

# ────────── Tasks ──────────
async def signal_consumer(executor):
    bus = SignalBus()
    await bus.connect()
    try:
        async for sig in bus.consume():
            if _shutdown.is_set():
                break
            # Process in background so slow trades don't block the next signal
            asyncio.create_task(_safe_process(sig, executor))
    finally:
        await bus.close()

async def _safe_process(sig: Signal, executor):
    try:
        await process_signal(sig, executor)
    except Exception:
        log.exception("process_signal_crashed", extra={"signal_id": sig.signal_id})

async def mark_refresher(executor):
    while not _shutdown.is_set():
        try:
            async with SessionLocal() as db:
                await refresh_marks_and_unrealized(db, executor)
        except Exception:
            log.exception("mark_refresh_crashed")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            pass

# ────────── Entry ──────────
async def main():
    log.info("allocator_starting", extra={
        "env": settings.environment,
        "aum_usd": settings.aum_usd,
        "kelly_fraction": settings.kelly_fraction,
        "venue": "hyperliquid" + ("(testnet)" if settings.hyperliquid_use_testnet else ""),
        "assets": settings.enabled_assets,
    })

    executor = get_executor()

    # Pre-flight: ensure today's PnL row exists
    async with SessionLocal() as db:
        await ensure_daily_pnl_row(db)

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(os_signal, sig_name), _shutdown.set)
        except NotImplementedError:
            pass  # Windows

    tasks = [
        asyncio.create_task(signal_consumer(executor), name="signal_consumer"),
        asyncio.create_task(mark_refresher(executor), name="mark_refresher"),
    ]

    await _shutdown.wait()
    log.info("allocator_shutting_down")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await engine.dispose()
    log.info("allocator_stopped")

if __name__ == "__main__":
    asyncio.run(main())
