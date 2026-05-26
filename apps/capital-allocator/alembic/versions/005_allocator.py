"""allocator tables

Revision ID: 005
Revises: 004
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "allocator_positions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset", sa.String(16), nullable=False, index=True),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("size_usd", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("mark_price", sa.Float()),
        sa.Column("unrealized_pnl_usd", sa.Float(), server_default="0"),
        sa.Column("realized_pnl_usd", sa.Float(), server_default="0"),
        sa.Column("opened_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime()),
        sa.Column("is_open", sa.Boolean(), server_default=sa.text("true"), index=True),
    )

    op.create_table(
        "allocator_trades",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset", sa.String(16), nullable=False, index=True),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("size_usd", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee_usd", sa.Float(), server_default="0"),
        sa.Column("venue", sa.String(32), nullable=False, server_default="hyperliquid"),
        sa.Column("venue_order_id", sa.String()),
        sa.Column("venue_fill_id", sa.String()),
        sa.Column("is_close", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("realized_pnl_usd", sa.Float(), server_default="0"),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "attribution_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("signal_id", sa.String(), nullable=False, index=True),
        sa.Column("model_id", sa.String(), nullable=False, index=True),
        sa.Column("trade_id", UUID(as_uuid=True), sa.ForeignKey("allocator_trades.id"), nullable=False),
        sa.Column("weight", sa.Float(), server_default="1.0"),
        sa.Column("expected_edge_bps", sa.Float()),
        sa.Column("realized_pnl_usd", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "allocator_daily_pnl",
        sa.Column("date", sa.String(10), primary_key=True),
        sa.Column("starting_aum_usd", sa.Float(), nullable=False),
        sa.Column("ending_aum_usd", sa.Float()),
        sa.Column("realized_pnl_usd", sa.Float(), server_default="0"),
        sa.Column("unrealized_pnl_usd", sa.Float(), server_default="0"),
        sa.Column("fees_usd", sa.Float(), server_default="0"),
        sa.Column("trades_count", sa.Integer(), server_default="0"),
        sa.Column("halted", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("halt_reason", sa.String()),
    )

def downgrade():
    for t in ["allocator_daily_pnl", "attribution_links", "allocator_trades", "allocator_positions"]:
        op.drop_table(t)
