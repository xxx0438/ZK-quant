"""initial schema

Revision ID: 001
Revises: 
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("wallet_address", sa.String(), nullable=True, index=True),
        sa.Column("balance_usd_cents", sa.Integer(), default=0),
        sa.Column("is_sophisticated", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("key_prefix", sa.String(), nullable=False, index=True),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), default="default"),
        sa.Column("revoked", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "models",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(), default="factor"),
        sa.Column("quant_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("price_per_call_cents", sa.Integer(), default=10),
        sa.Column("lease_monthly_cents", sa.Integer(), default=49900),
        sa.Column("active_cert_id", sa.String(), nullable=True),
        sa.Column("is_listed", sa.Boolean(), default=False),
        sa.Column("capital_allocated_usd", sa.Float(), default=0),
        sa.Column("live_sharpe_30d", sa.Float(), nullable=True),
        sa.Column("live_sharpe_90d", sa.Float(), nullable=True),
        sa.Column("live_sharpe_inception", sa.Float(), nullable=True),
        sa.Column("tested_capacity_usd", sa.Float(), default=10000),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "performance_certs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("model_id", sa.String(), sa.ForeignKey("models.id")),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("backtest_metrics", JSON, nullable=False),
        sa.Column("forward_metrics", JSON, nullable=True),
        sa.Column("capital_metrics", JSON, nullable=True),
        sa.Column("attestation", JSON, nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("dataset_hash", sa.String(), nullable=False),
        sa.Column("harness_hash", sa.String(), nullable=False),
        sa.Column("reproducibility_kit_url", sa.String(), nullable=True),
        sa.Column("signed_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "predictions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("model_id", sa.String(), sa.ForeignKey("models.id")),
        sa.Column("inputs", JSON),
        sa.Column("output", JSON),
        sa.Column("cost_cents", sa.Integer(), default=0),
        sa.Column("cert_id", sa.String(), nullable=True),
        sa.Column("ipfs_cid", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )
    op.create_table(
        "leases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("model_id", sa.String(), sa.ForeignKey("models.id")),
        sa.Column("valid_from", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("daily_quota", sa.Integer(), default=1000),
        sa.Column("active", sa.Boolean(), default=True),
    )
    op.create_table(
        "forward_test_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", sa.String(), sa.ForeignKey("models.id"), index=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("prediction", JSON),
        sa.Column("realized_outcome", JSON, nullable=True),
        sa.Column("realized_pnl_bps", sa.Float(), nullable=True),
        sa.Column("ipfs_cid", sa.String(), nullable=True),
    )
    op.create_table(
        "capital_allocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", sa.String(), sa.ForeignKey("models.id")),
        sa.Column("allocated_usd", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("pnl_usd", sa.Float(), default=0),
        sa.Column("onchain_wallet", sa.String(), nullable=False),
        sa.Column("notes", sa.Text()),
    )
    op.create_table(
        "usdc_deposits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("tx_hash", sa.String(), unique=True, nullable=False, index=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("from_address", sa.String(), nullable=False),
        sa.Column("block_number", sa.Integer(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade():
    for t in ["usdc_deposits", "capital_allocations", "forward_test_records",
              "leases", "predictions", "performance_certs", "models", "api_keys", "users"]:
        op.drop_table(t)
