"""add source column to usdc_deposits, switch unique to (source, tx_hash)

Revision ID: 003
Revises: 002
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add source column with default
    op.add_column(
        "usdc_deposits",
        sa.Column(
            "source",
            sa.String(),
            nullable=False,
            server_default="onchain",
        ),
    )
    op.create_index(
        "ix_usdc_deposits_source",
        "usdc_deposits",
        ["source"],
    )

    # 2. Drop old single-column unique constraint (auto-named by Postgres)
    #    Use IF EXISTS via raw SQL because the name varies across deployments
    op.execute("""
        DO $$
        DECLARE constraint_name text;
        BEGIN
            SELECT con.conname INTO constraint_name
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            WHERE rel.relname = 'usdc_deposits'
              AND con.contype = 'u'
              AND pg_get_constraintdef(con.oid) LIKE '%(tx_hash)%';
            IF constraint_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE usdc_deposits DROP CONSTRAINT %I', constraint_name);
            END IF;
        END $$;
    """)

    # 3. Create new composite unique constraint
    op.create_unique_constraint(
        "uq_usdc_deposits_source_tx",
        "usdc_deposits",
        ["source", "tx_hash"],
    )

    # 4. Ensure tx_hash index exists (was auto-created with old unique; recreate explicitly)
    op.create_index(
        "ix_usdc_deposits_tx_hash",
        "usdc_deposits",
        ["tx_hash"],
        if_not_exists=True,
    )

def downgrade():
    op.drop_index("ix_usdc_deposits_tx_hash", table_name="usdc_deposits")
    op.drop_constraint("uq_usdc_deposits_source_tx", "usdc_deposits", type_="unique")
    op.create_unique_constraint(
        "usdc_deposits_tx_hash_key",
        "usdc_deposits",
        ["tx_hash"],
    )
    op.drop_index("ix_usdc_deposits_source", table_name="usdc_deposits")
    op.drop_column("usdc_deposits", "source")
