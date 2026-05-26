"""marketplace: quant profiles, revenue ledger, model submissions

Revision ID: 004
Revises: 003
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

def upgrade():
    # ─── Quant profiles ───
    op.create_table(
        "quant_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("handle", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("bio", sa.Text()),
        sa.Column("payout_address", sa.String(42), nullable=False),
        sa.Column("payout_chain", sa.String(16), nullable=False, server_default="base"),
        sa.Column("revenue_share_bps", sa.Integer(), nullable=False, server_default="7000"),
        sa.Column("tier", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_earned_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_paid_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_quant_profiles_handle", "quant_profiles", ["handle"])

    # ─── Revenue ledger (append-only) ───
    op.create_table(
        "revenue_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "prediction_id",
            sa.String(),
            sa.ForeignKey("predictions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("model_id", sa.String(), sa.ForeignKey("models.id"), nullable=False),
        sa.Column(
            "quant_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("quant_profiles.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("gross_cents", sa.Integer(), nullable=False),
        sa.Column("quant_cents", sa.Integer(), nullable=False),
        sa.Column("capital_cents", sa.Integer(), nullable=False),
        sa.Column("protocol_cents", sa.Integer(), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("settlement_tx", sa.String(), nullable=True),
        sa.Column("settlement_batch_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # ─── Settlement batches (one row per weekly run) ───
    op.create_table(
        "settlement_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        # pending | submitted | confirmed | failed
        sa.Column("total_payouts_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tx_hash", sa.String(), nullable=True),
        sa.Column("block_number", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    # ─── Model submissions (review queue) ───
    op.create_table(
        "model_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "quant_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("quant_profiles.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("proposed_model_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(32), nullable=False, server_default="factor"),
        sa.Column("artifact_url", sa.String(), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("backtest_kit_url", sa.String(), nullable=False),
        sa.Column("backtest_kit_sha256", sa.String(64), nullable=False),
        sa.Column(
            "review_status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),  # pending | verifying | approved | rejected
        sa.Column("review_metrics", JSON, nullable=True),
        sa.Column("reviewer_notes", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("cert_id", sa.String(), nullable=True),
    )

    # ─── Model authorship link (extend models.quant_user_id) ───
    # Already present in 001_initial; no change needed.

def downgrade():
    for t in [
        "model_submissions",
        "settlement_batches",
        "revenue_ledger",
        "quant_profiles",
    ]:
        op.drop_table(t)
