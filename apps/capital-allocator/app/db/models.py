"""Allocator-owned tables. Shares the same DB as the API."""
import uuid
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class AllocatorPosition(Base):
    """Current open position per (asset, side). Materialized view of fills."""
    __tablename__ = "allocator_positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset = Column(String(16), nullable=False, index=True)
    side = Column(String(8), nullable=False)              # "long" | "short"
    size_usd = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    mark_price = Column(Float, nullable=True)
    unrealized_pnl_usd = Column(Float, default=0)
    realized_pnl_usd = Column(Float, default=0)
    opened_at = Column(DateTime, server_default=func.now())
    closed_at = Column(DateTime, nullable=True)
    is_open = Column(Boolean, default=True, index=True)

class AllocatorTrade(Base):
    """Every fill that the allocator executed."""
    __tablename__ = "allocator_trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset = Column(String(16), nullable=False, index=True)
    side = Column(String(8), nullable=False)
    size_usd = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee_usd = Column(Float, default=0)
    venue = Column(String(32), nullable=False, default="hyperliquid")
    venue_order_id = Column(String, nullable=True)
    venue_fill_id = Column(String, nullable=True)
    is_close = Column(Boolean, default=False)
    realized_pnl_usd = Column(Float, default=0)
    timestamp = Column(DateTime, server_default=func.now(), index=True)

class AttributionLink(Base):
    """Link a model signal → an executed trade. Publicly verifiable."""
    __tablename__ = "attribution_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(String, nullable=False, index=True)   # prediction_id from Echo API
    model_id = Column(String, nullable=False, index=True)
    trade_id = Column(UUID(as_uuid=True), ForeignKey("allocator_trades.id"), nullable=False)
    weight = Column(Float, default=1.0)                       # in case multiple signals combine
    expected_edge_bps = Column(Float, nullable=True)
    realized_pnl_usd = Column(Float, default=0)               # updated post-close
    created_at = Column(DateTime, server_default=func.now())

class DailyPnl(Base):
    """One row per UTC day. For circuit breaker + public chart."""
    __tablename__ = "allocator_daily_pnl"

    date = Column(String(10), primary_key=True)               # "2026-05-26"
    starting_aum_usd = Column(Float, nullable=False)
    ending_aum_usd = Column(Float, nullable=True)
    realized_pnl_usd = Column(Float, default=0)
    unrealized_pnl_usd = Column(Float, default=0)
    fees_usd = Column(Float, default=0)
    trades_count = Column(Integer, default=0)
    halted = Column(Boolean, default=False)
    halt_reason = Column(String, nullable=True)
