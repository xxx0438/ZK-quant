"""add signed-cert fields

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

def upgrade():
    # The full signed cert JSON lives in `attestation` (already JSON);
    # add explicit columns for fast lookup.
    op.add_column("performance_certs", sa.Column("cert_version", sa.String(), nullable=True))
    op.add_column("performance_certs", sa.Column("issuer_key_id", sa.String(), nullable=True))
    op.add_column("performance_certs", sa.Column("expires_at", sa.BigInteger(), nullable=True))
    op.create_index("ix_certs_model_id", "performance_certs", ["model_id"])

def downgrade():
    op.drop_index("ix_certs_model_id", table_name="performance_certs")
    op.drop_column("performance_certs", "expires_at")
    op.drop_column("performance_certs", "issuer_key_id")
    op.drop_column("performance_certs", "cert_version")
