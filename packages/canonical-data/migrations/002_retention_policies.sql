-- Retention: keep 13 months of OHLCV, 90 days of orderbook (high volume),
-- and unlimited funding/OI (small).
-- Snapshot archive: keep 365 days.

SELECT add_retention_policy('orderbook',       INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('ohlcv',           INTERVAL '395 days', if_not_exists => TRUE);
SELECT add_retention_policy('onchain_whale',   INTERVAL '395 days', if_not_exists => TRUE);

-- Snapshot archive cleanup via job (not a hypertable)
CREATE OR REPLACE FUNCTION cleanup_old_snapshots() RETURNS void AS $$
BEGIN
    DELETE FROM snapshot_archive
    WHERE created_at < now() - INTERVAL '365 days';
END;
$$ LANGUAGE plpgsql;

-- Compression for old data (saves ~10x on storage)
ALTER TABLE ohlcv      SET (timescaledb.compress, timescaledb.compress_segmentby = 'asset, interval');
ALTER TABLE orderbook  SET (timescaledb.compress, timescaledb.compress_segmentby = 'asset');
SELECT add_compression_policy('ohlcv',     INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('orderbook', INTERVAL '1 day',  if_not_exists => TRUE);
