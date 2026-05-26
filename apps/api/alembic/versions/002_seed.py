"""seed initial models

Revision ID: 002
Revises: 001
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
import json

revision = "002"
down_revision = "001"

def upgrade():
    op.execute("""
        INSERT INTO models (id, version, name, description, category, price_per_call_cents, lease_monthly_cents, is_listed, tested_capacity_usd, live_sharpe_30d, live_sharpe_90d)
        VALUES
        ('whale-netflow-eth', 'v1.0.0', 'Whale Netflow ETH', 'On-chain whale → CEX flow factor for ETH', 'factor', 10, 49900, true, 100000, 1.41, 1.34),
        ('funding-rate-signal', 'v1.0.0', 'Funding Rate Anomaly', 'Mean-reversion on perpetual funding extremes', 'factor', 5, 19900, true, 250000, 1.12, 1.05),
        ('basis-z-btc', 'v1.0.0', 'BTC Basis Z-Score', 'Spot-Perp basis dislocation factor', 'factor', 5, 19900, true, 500000, 0.94, 0.88),
        ('oi-divergence-btc', 'v1.0.0', 'OI Divergence BTC', 'Open interest vs price divergence', 'factor', 5, 19900, true, 250000, 0.88, 0.92),
        ('btc-direction-4h', 'v1.2.0', 'BTC Direction 4h', 'LightGBM model for BTC 4h direction', 'prediction', 10, 49900, true, 50000, 1.18, 1.10);
    """)

def downgrade():
    op.execute("DELETE FROM models;")
