"""Export a canonical dataset folder for SDK backtests.

Output layout matches what echo_quant.backtest.dataset.CanonicalDataset expects:

    <out>/
      manifest.json
      snapshots/<unix_ts>.json
      prices/<ASSET>.csv

Snapshots are built at the hourly grid, so a 90-day export for one asset
produces ~2160 snapshot files. At ~5 KB each that's ~10 MB → fine to ship.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import orjson
from sqlalchemy import text

from echo_data.snapshot import SnapshotBuilder
from echo_data.timescale import connect

log = logging.getLogger("echo_data.dataset")

class DatasetBuilder:
    """Build a portable dataset folder from canonical data warehouse."""

    def __init__(self, redis_url: str):
        self._builder = SnapshotBuilder(redis_url=redis_url)

    async def export(
        self,
        *,
        asset: str,
        start: datetime,
        end: datetime,
        out_dir: str | Path,
        step_minutes: int = 60,
        name: str | None = None,
    ) -> Path:
        out = Path(out_dir).resolve()
        snap_dir = out / "snapshots"
        prices_dir = out / "prices"
        snap_dir.mkdir(parents=True, exist_ok=True)
        prices_dir.mkdir(exist_ok=True)

        asset = asset.upper()
        log.info("dataset_export_start", extra={
            "asset": asset, "start": start.isoformat(), "end": end.isoformat(),
        })

        # Snapshots
        cursor = start
        n = 0
        while cursor <= end:
            try:
                snap, _ = await self._builder.historical(asset, cursor)
                fpath = snap_dir / f"{int(cursor.timestamp())}.json"
                fpath.write_bytes(orjson.dumps(snap.model_dump(mode="json")))
                n += 1
            except Exception:
                log.exception("snap_failed", extra={"ts": cursor.isoformat()})
            cursor += timedelta(minutes=step_minutes)

        # Prices CSV for outcome resolution (1-min granularity)
        await self._export_prices(asset, start, end, prices_dir / f"{asset}.csv")

        # Manifest + hash
        ds_hash = _hash_dataset_dir(out)
        manifest = {
            "name": name or f"{asset.lower()}-{start.date()}-to-{end.date()}",
            "asset": asset,
            "hash": ds_hash,
            "period_start": int(start.timestamp()),
            "period_end": int(end.timestamp()),
            "step_minutes": step_minutes,
            "n_snapshots": n,
            "schema_version": "1.0",
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        log.info("dataset_export_done", extra={"path": str(out), "n": n, "hash": ds_hash[:12]})
        return out

    async def _export_prices(self, asset: str, start: datetime, end: datetime, path: Path):
        """1-min OHLCV for the period. Backtest uses this to resolve trade outcomes."""
        async with connect() as conn:
            rows = await conn.execute(
                text("""
                    SELECT ts, open, high, low, close
                    FROM ohlcv
                    WHERE asset = :a AND interval = '1m'
                      AND ts >= :s AND ts <= :e
                    ORDER BY ts ASC
                """),
                {"a": asset, "s": start, "e": end},
            )
            with path.open("w") as f:
                f.write("ts,open,high,low,close\n")
                for r in rows.all():
                    f.write(f"{int(r.ts.timestamp())},{r.open},{r.high},{r.low},{r.close}\n")

def _hash_dataset_dir(path: Path) -> str:
    """SHA256 over all snapshot files + prices CSVs, sorted."""
    h = hashlib.sha256()
    for sub in ("snapshots", "prices"):
        for p in sorted((path / sub).rglob("*")):
            if p.is_file():
                with p.open("rb") as f:
                    h.update(f.read())
    return h.hexdigest()
