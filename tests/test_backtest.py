import json
from pathlib import Path
import pytest

from echo_quant import Model, Inputs, Signal
from echo_quant.backtest.dataset import CanonicalDataset
from echo_quant.backtest.runner import run_backtest

class AlwaysLong(Model):
    model_id = "always-long"
    asset = "ETH"
    def predict(self, inputs):
        return Signal(asset="ETH", direction="long", edge_bps=10, expected_vol_bps=50)

@pytest.fixture
def fake_dataset(tmp_path: Path) -> Path:
    """Build a minimal dataset directory."""
    ds = tmp_path / "ds"
    (ds / "snapshots").mkdir(parents=True)
    (ds / "prices").mkdir()

    # 10 hourly snapshots, prices rising 0.1% per hour
    base_ts = 1_700_000_000
    for i in range(10):
        ts = base_ts + i * 3600
        snap = {
            "asset": "ETH", "timestamp": ts,
            "ohlcv_1h": [{
                "ts": ts, "open": 3000 + i * 3, "high": 3001 + i * 3,
                "low": 2999 + i * 3, "close": 3000 + i * 3, "volume": 1000,
            }],
            "snapshot_hash": f"snap_{i}",
        }
        (ds / "snapshots" / f"{ts}.json").write_text(json.dumps(snap))

    # 1-min prices spanning the period (so resolve_outcome works)
    prices = ["ts,open,high,low,close"]
    for i in range(11 * 60):
        ts = base_ts + i * 60
        prices.append(f"{ts},0,0,0,{3000 + (i / 60) * 3:.4f}")
    (ds / "prices" / "ETH.csv").write_text("\n".join(prices))

    # Manifest
    (ds / "manifest.json").write_text(json.dumps({
        "name": "test-ds", "asset": "ETH", "hash": "test",
        "period_start": base_ts, "period_end": base_ts + 10 * 3600,
    }))
    return ds

def test_backtest_runs(fake_dataset):
    ds = CanonicalDataset.load(fake_dataset)
    result = run_backtest(AlwaysLong(), ds)
    assert result.n_predictions == 10
    assert result.n_trades > 0
    # Always-long on a rising market → positive PnL
    assert result.metrics["avg_pnl_bps"] > 0
