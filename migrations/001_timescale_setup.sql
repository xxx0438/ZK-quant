-- Run this once to set up the canonical data tables.
-- Requires: TimescaleDB extension (Supabase / Neon / self-hosted all support).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ─────────── OHLCV bars ───────────
CREATE TABLE IF NOT EXISTS ohlcv_bars (
    asset      TEXT        NOT NULL,
    interval   TEXT        NOT NULL,
    ts         TIMESTAMPTZ NOT NULL,
    open       DOUBLE PRECISION NOT NULL,
    high       DOUBLE PRECISION NOT NULL,
    low        DOUBLE PRECISION NOT NULL,
    close      DOUBLE PRECISION NOT NULL,
    volume     DOUBLE PRECISION NOT NULL,
    source     TEXT        NOT NULL,
    PRIMARY KEY (asset, interval, ts)
);

SELECT create_hypertable('ohlcv_bars', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_ohlcv_asset_int_ts ON ohlcv_bars (asset, interval, ts DESC);

-- ─────────── Funding ───────────
CREATE TABLE IF NOT EXISTS funding_history (
    asset         TEXT NOT NULL,
    ts            TIMESTAMPTZ NOT NULL,
    funding_rate  DOUBLE PRECISION NOT NULL,
    source        TEXT NOT NULL,
    PRIMARY KEY (asset, ts)
);
SELECT create_hypertable('funding_history', 'ts', if_not_exists => TRUE);

-- ─────────── Open interest ───────────
CREATE TABLE IF NOT EXISTS oi_history (
    asset             TEXT NOT NULL,
    ts                TIMESTAMPTZ NOT NULL,
    open_interest_usd DOUBLE PRECISION NOT NULL,
    mark_price        DOUBLE PRECISION,
    source            TEXT NOT NULL,
    PRIMARY KEY (asset, ts)
);
SELECT create_hypertable('oi_history', 'ts', if_not_exists => TRUE);

-- ─────────── Orderbook summary ───────────
CREATE TABLE IF NOT EXISTS orderbook_summary (
    asset            TEXT NOT NULL,
    ts               TIMESTAMPTZ NOT NULL,
    bid_price        DOUBLE PRECISION NOT NULL,
    ask_price        DOUBLE PRECISION NOT NULL,
    bid_size_top10   DOUBLE PRECISION NOT NULL,
    ask_size_top10   DOUBLE PRECISION NOT NULL,
    spread_bps       DOUBLE PRECISION NOT NULL,
    source           TEXT NOT NULL
);
SELECT create_hypertable('orderbook_summary', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_book_asset_ts ON orderbook_summary (asset, ts DESC);

-- ─────────── Onchain metrics ───────────
CREATE TABLE IF NOT EXISTS onchain_history (
    asset    TEXT NOT NULL,
    ts       TIMESTAMPTZ NOT NULL,
    metric   TEXT NOT NULL,
    value    DOUBLE PRECISION NOT NULL,
    payload  JSONB,
    source   TEXT NOT NULL
);
SELECT create_hypertable('onchain_history', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_onchain_asset_metric_ts ON onchain_history (asset, metric, ts DESC);

-- ─────────── Snapshots (the canonical record) ───────────
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_hash    TEXT PRIMARY KEY,
    asset            TEXT NOT NULL,
    ts               TIMESTAMPTZ NOT NULL,
    inputs_json      BYTEA NOT NULL,
    schema_version   TEXT NOT NULL DEFAULT '1.0.0',
    source_versions  JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_snapshots_asset_ts ON snapshots (asset, ts DESC);

-- ─────────── Retention + compression policies ───────────
SELECT add_retention_policy('ohlcv_bars',        INTERVAL '730 days', if_not_exists => TRUE);
SELECT add_retention_policy('orderbook_summary', INTERVAL '30 days',  if_not_exists => TRUE);
SELECT add_retention_policy('snapshots',         INTERVAL '365 days', if_not_exists => TRUE);

ALTER TABLE ohlcv_bars        SET (timescaledb.compress, timescaledb.compress_segmentby = 'asset, interval');
ALTER TABLE orderbook_summary SET (timescaledb.compress, timescaledb.compress_segmentby = 'asset');
SELECT add_compression_policy('ohlcv_bars',        INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('orderbook_summary', INTERVAL '1 day',  if_not_exists => TRUE);
