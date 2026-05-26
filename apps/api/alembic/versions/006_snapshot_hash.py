"""add snapshot_hash to predictions

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("predictions", sa.Column("snapshot_hash", sa.String(), nullable=True))
    op.create_index("ix_predictions_snapshot_hash", "predictions", ["snapshot_hash"])

def downgrade():
    op.drop_index("ix_predictions_snapshot_hash", table_name="predictions")
    op.drop_column("predictions", "snapshot_hash")
