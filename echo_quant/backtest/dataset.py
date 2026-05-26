"""Canonical dataset for backtesting.

A dataset is a directory:
  <dataset_dir>/
    manifest.json         { name, asset, hash, period_start, period_end, schema_version }
    snapshots/            one file per timestamp, name = "<unix_ts>.json"
      1717200000.json     {Inputs JSON with snapshot_hash}
      1717203600.json
      ...
    prices/               outcome resolution
      <asset>.csv         ts,open,high,low,close (1m resolution)

Datasets are published by Echo and pulled with `echo-cli dataset pull <name>`.
For local dev, you can build one with `echo-cli dataset build`.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from echo_quant.exceptions import BacktestError
from echo_quant.model import Inputs

@dataclass
class CanonicalDataset:
    """Lazy iterator over a local dataset directory."""

    path: Path
    name: str
    asset: str
    dataset_hash: str
    period_start: int
    period_end: int

    _price_index: Optional[dict[int, float]] = None

    @classmethod
    def load(cls, path: str | Path) -> "CanonicalDataset":
        path = Path(path)
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            raise BacktestError(f"No manifest.json at {path}")
        manifest = json.loads(manifest_path.read_text())

        return cls(
            path=path,
            name=manifest["name"],
            asset=manifest["asset"].upper(),
            dataset_hash=manifest["hash"],
            period_start=manifest["period_start"],
            period_end=manifest["period_end"],
        )

    def iter_inputs(self) -> Iterator[Inputs]:
        snapshot_dir = self.path / "snapshots"
        if not snapshot_dir.exists():
            raise BacktestError(f"No snapshots/ in {self.path}")
        # Chronological order
        files = sorted(snapshot_dir.glob("*.json"), key=lambda p: int(p.stem))
        for f in files:
            data = json.loads(f.read_text())
            yield Inputs.model_validate(data)

    def _ensure_prices(self) -> dict[int, float]:
        if self._price_index is not None:
            return self._price_index
        prices_path = self.path / "prices" / f"{self.asset}.csv"
        if not prices_path.exists():
            raise BacktestError(f"Missing prices file: {prices_path}")
        idx: dict[int, float] = {}
        with prices_path.open() as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                idx[int(row["ts"])] = float(row["close"])
        self._price_index = idx
        return idx

    def resolve_outcome(self, ts: int, horizon_hours: float) -> Optional[tuple[float, float]]:
        """Return (entry_price, exit_price) for a trade opened at ts,
        held for `horizon_hours`. None if dataset doesn't span the exit time."""
        prices = self._ensure_prices()
        # Snap to nearest minute
        entry_ts = (ts // 60) * 60
        exit_ts = entry_ts + int(horizon_hours * 3600)
        entry = prices.get(entry_ts)
        exit_p = prices.get((exit_ts // 60) * 60)
        if entry is None or exit_p is None:
            return None
        return entry, exit_p

def compute_dataset_hash(path: Path) -> str:
    """Hash all snapshot files + prices for integrity check."""
    h = hashlib.sha256()
    for p in sorted((path / "snapshots").rglob("*.json")):
        h.update(p.read_bytes())
    for p in sorted((path / "prices").rglob("*.csv")):
        h.update(p.read_bytes())
    return h.hexdigest()
