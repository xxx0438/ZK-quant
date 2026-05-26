"""SQLAlchemy ORM models.

Fixes in this file (v4.1.1):
- Bug 6: USDCDeposit gains `source` column ("onchain" | "coinbase_commerce")
         and uniqueness is now (source, tx_hash), not tx_hash alone.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False, default="")
    wallet_address = Column(String, nullable=True, index=True)
    balance_usd_cents = Column(Integer, nullable=False, default=0)
    is_sophisticated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_prefix = Column(String, nullable=False, index=True)
    key_hash = Column(String, nullable=False)
    name = Column(String, default="default")
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class Model(Base):
    __tablename__ = "models"

    id = Column(String, primary_key=True)
    version = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String, default="factor")
    quant_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    price_per_call_cents = Column(Integer, default=10)
    lease_monthly_cents = Column(Integer, default=49900)
    active_cert_id = Column(String, nullable=True)
    is_listed = Column(Boolean, default=False)
    capital_allocated_usd = Column(Float, default=0)
    live_sharpe_30d = Column(Float, nullable=True)
    live_sharpe_90d = Column(Float, nullable=True)
    live_sharpe_inception = Column(Float, nullable=True)
    tested_capacity_usd = Column(Float, default=10000)
    created_at = Column(DateTime, server_default=func.now())

class PerformanceCert(Base):
    __tablename__ = "performance_certs"

    id = Column(String, primary_key=True)
    model_id = Column(String, ForeignKey("models.id"), nullable=False)
    model_version = Column(String, nullable=False)
    backtest_metrics = Column(JSON, nullable=False)
    forward_metrics = Column(JSON, nullable=True)
    capital_metrics = Column(JSON, nullable=True)
    attestation = Column(JSON, nullable=False)
    signature = Column(String, nullable=False)
    dataset_hash = Column(String, nullable=False)
    harness_hash = Column(String, nullable=False)
    reproducibility_kit_url = Column(String, nullable=True)
    signed_at = Column(DateTime, server_default=func.now())

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    model_id = Column(String, ForeignKey("models.id"), nullable=False)
    inputs = Column(JSON)
    output = Column(JSON)
    cost_cents = Column(Integer, default=0)
    cert_id = Column(String, nullable=True)
    ipfs_cid = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

class Lease(Base):
    __tablename__ = "leases"

    id = Column(String, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    model_id = Column(String, ForeignKey("models.id"), nullable=False)
    valid_from = Column(DateTime, server_default=func.now())
    valid_until = Column(DateTime, nullable=False)
    daily_quota = Column(Integer, default=1000)
    active = Column(Boolean, default=True)

class ForwardTestRecord(Base):
    __tablename__ = "forward_test_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(String, ForeignKey("models.id"), index=True, nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    prediction = Column(JSON)
    realized_outcome = Column(JSON, nullable=True)
    realized_pnl_bps = Column(Float, nullable=True)
    ipfs_cid = Column(String, nullable=True)

class CapitalAllocation(Base):
    __tablename__ = "capital_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(String, ForeignKey("models.id"), nullable=False)
    allocated_usd = Column(Float, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    pnl_usd = Column(Float, default=0)
    onchain_wallet = Column(String, nullable=False)
    notes = Column(Text)

class USDCDeposit(Base):
    """Records of credit additions to user balances.

    `source` distinguishes how the deposit arrived:
      - "onchain"           : direct USDC transfer detected via Alchemy webhook
      - "coinbase_commerce" : hosted checkout via Coinbase Commerce
      - "manual"            : admin credit (refund, promo, etc.)

    Uniqueness is (source, tx_hash) — Coinbase charge IDs and real on-chain
    tx hashes live in distinct namespaces.
    """

    __tablename__ = "usdc_deposits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source = Column(String, nullable=False, default="onchain", index=True)
    tx_hash = Column(String, nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    from_address = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False, default=0)
    processed_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source", "tx_hash", name="uq_usdc_deposits_source_tx"),
    )
