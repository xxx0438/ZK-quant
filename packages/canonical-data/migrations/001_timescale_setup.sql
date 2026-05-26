-- Echo canonical data: TimescaleDB hypertables.
--
-- Run once against the canonical-data database (can be the same Postgres
-- instance as the main app, but a separate DB is recommended in production
-- so retention policies and storage growth don't affect transactional tables).
--
-- Required extension: timescaledb (Supabase / Timescale Cloud / self-host).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ──────────────────────── OHLCV ────────────────────────
-- One row per (asset, interval, bar_close_ts). Source distinguishes
-- e.g. Hyperliquid perp vs CoinGecko spot composite.
CREATE TABLE IF NOT EXISTS ohlcv (
    ts          TIMESTAMPTZ NOT NULL,
    asset       TEXT NOT NULL,
    interval    TEXT NOT NULL,         -- '1m', '1h', '4h', '1d'
    source      TEXT NOT NULL,         -- 'hyperliquid', 'coingecko'
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (asset, interval, source, ts)
);
SELECT create_hypertable('ohlcv', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_ohlcv_asset_interval_ts
    ON ohlcv (asset, interval, ts DESC);

-- ──────────────────────── Funding rate ────────────────────────
-- Hyperliquid funding updates every hour; we store each update.
CREATE TABLE IF NOT EXISTS funding_rate (
    ts          TIMESTAMPTZ NOT NULL,
    asset       TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'hyperliquid',
    rate        DOUBLE PRECISION NOT NULL,   -- decimal, e.g. 0.0001 = 1bp
    PRIMARY KEY (asset, source, ts)
);
SELECT create_hypertable('funding_rate', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_funding_asset_ts
    ON funding_rate (asset, ts DESC);

-- ──────────────────────── Open interest ────────────────────────
CREATE TABLE IF NOT EXISTS open_interest (
    ts          TIMESTAMPTZ NOT NULL,
    asset       TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'hyperliquid',
    oi_usd      DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (asset, source, ts)
);
SELECT create_hypertable('open_interest', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_oi_asset_ts
    ON open_interest (asset, ts DESC);

-- ──────────────────────── Orderbook snapshots ────────────────────────
-- Sampled every 1s in production. Top-10 cumulative size.
CREATE TABLE IF NOT EXISTS orderbook (
    ts                  TIMESTAMPTZ NOT NULL,
    asset               TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'hyperliquid',
    bid_price           DOUBLE PRECISION NOT NULL,
    ask_price           DOUBLE PRECISION NOT NULL,
    bid_size_top10      DOUBLE PRECISION NOT NULL,
    ask_size_top10      DOUBLE PRECISION NOT NULL,
    spread_bps          DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (asset, source, ts)
);
SELECT create_hypertable('orderbook', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_orderbook_asset_ts
    ON orderbook (asset, ts DESC);

-- ──────────────────────── Onchain whale flows ────────────────────────
-- Rolled-up per hour from Goldsky subgraph.
CREATE TABLE IF NOT EXISTS onchain_whale (
    ts                          TIMESTAMPTZ NOT NULL,
    asset                       TEXT NOT NULL,
    source                      TEXT NOT NULL DEFAULT 'goldsky',
    netflow_24h_usd             DOUBLE PRECISION,
    exchange_balance_usd        DOUBLE PRECISION,
    active_addresses_24h        BIGINT,
    extra                       JSONB,
    PRIMARY KEY (asset, source, ts)
);
SELECT create_hypertable('onchain_whale', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_onchain_asset_ts
    ON onchain_whale (asset, ts DESC);

-- ──────────────────────── Snapshot archive ────────────────────────
-- Every snapshot we hand to a model is archived here for replay/audit.
-- Not a hypertable: this is keyed by hash, not time.
CREATE TABLE IF NOT EXISTS snapshot_archive (
    snapshot_hash       TEXT PRIMARY KEY,
    asset               TEXT NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    payload             JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_snapshot_asset_ts
    ON snapshot_archive (asset, timestamp DESC);

-- Ingestion health: heartbeats from workers
CREATE TABLE IF NOT EXISTS ingestion_heartbeat (
    worker_name     TEXT PRIMARY KEY,
    last_seen       TIMESTAMPTZ NOT NULL,
    last_status     TEXT NOT NULL,         -- 'ok' | 'degraded' | 'error'
    rows_written_1m INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT
);
