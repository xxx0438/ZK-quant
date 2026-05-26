"""Deterministic local backtest runner.

Design:
- Loads a canonical dataset (one snapshot per timestamp)
- For each snapshot: call model.predict(inputs) → Signal
- Simulate trade: assume execution at next bar's close ± slippage
- Compute realized PnL, accumulate equity curve
- Output metrics + per-trade log

Runs in <1s for typical 90-day datasets so quants can iterate fast.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from echo_quant.backtest.dataset import CanonicalDataset
from echo_quant.backtest.metrics import compute_metrics
from echo_quant.exceptions import BacktestError
from echo_quant.model import Inputs, Model, Signal

log = logging.getLogger("echo_quant.backtest")

@dataclass
class Trade:
    timestamp: int
    asset: str
    direction: str
    entry_price: float
    exit_price: float
    edge_bps_predicted: float
    pnl_bps_realized: float
    horizon_hours: float
    snapshot_hash: Optional[str] = None

@dataclass
class BacktestResult:
    model_id: str
    model_version: str
    dataset_name: str
    dataset_hash: str
    period_start: str
    period_end: str
    n_predictions: int
    n_trades: int
    trades: list[Trade] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    runtime_ms: int = 0

    def to_dict(self) -> dict:
        return {
            **{k: v for k, v in asdict(self).items() if k != "trades"},
            "trades": [asdict(t) for t in self.trades],
        }

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str))

def run_backtest(
    model: Model,
    dataset: CanonicalDataset,
    *,
    slippage_bps: float = 5.0,
    min_edge_bps: float = 2.0,
    fee_bps: float = 3.5,
    max_predictions: Optional[int] = None,
) -> BacktestResult:
    """Run a backtest of `model` over `dataset`.

    Args:
        model: instantiated Echo Model
        dataset: CanonicalDataset providing iter_inputs() and resolve_outcome()
        slippage_bps: assumed slippage on entry+exit (each side)
        min_edge_bps: skip trades with predicted edge below this
        fee_bps: total fees per round trip
        max_predictions: cap for quick iteration

    Returns:
        BacktestResult with metrics, trade log, and metadata.
    """
    if model.asset != dataset.asset:
        raise BacktestError(
            f"Model asset {model.asset!r} != dataset asset {dataset.asset!r}"
        )

    log.info("backtest_start", extra={"model": model.model_id, "dataset": dataset.name})
    t0 = time.time()
    trades: list[Trade] = []
    n_predictions = 0

    model.warmup()

    for inputs in dataset.iter_inputs():
        if max_predictions and n_predictions >= max_predictions:
            break

        signal = model.predict(inputs)
        n_predictions += 1

        # Filter
        if signal.direction == "neutral":
            continue
        if abs(signal.edge_bps) < min_edge_bps:
            continue

        # Resolve future outcome
        outcome = dataset.resolve_outcome(inputs.timestamp, signal.horizon_hours)
        if outcome is None:
            # End of dataset; can't resolve
            continue

        entry_price, exit_price = outcome
        realized_return = (exit_price - entry_price) / entry_price
        if signal.direction == "short":
            realized_return = -realized_return

        # Apply costs
        cost_bps = slippage_bps * 2 + fee_bps
        realized_bps = realized_return * 1e4 - cost_bps

        trades.append(
            Trade(
                timestamp=inputs.timestamp,
                asset=inputs.asset,
                direction=signal.direction,
                entry_price=entry_price,
                exit_price=exit_price,
                edge_bps_predicted=signal.edge_bps,
                pnl_bps_realized=realized_bps,
                horizon_hours=signal.horizon_hours,
                snapshot_hash=inputs.snapshot_hash,
            )
        )

    metrics = compute_metrics(trades)
    duration_ms = int((time.time() - t0) * 1000)

    period_start = (
        datetime.fromtimestamp(min(t.timestamp for t in trades), timezone.utc).isoformat()
        if trades
        else ""
    )
    period_end = (
        datetime.fromtimestamp(max(t.timestamp for t in trades), timezone.utc).isoformat()
        if trades
        else ""
    )

    result = BacktestResult(
        model_id=model.model_id,
        model_version=model.version,
        dataset_name=dataset.name,
        dataset_hash=dataset.dataset_hash,
        period_start=period_start,
        period_end=period_end,
        n_predictions=n_predictions,
        n_trades=len(trades),
        trades=trades,
        metrics=metrics,
        runtime_ms=duration_ms,
    )

    log.info(
        "backtest_complete",
        extra={
            "model": model.model_id,
            "n_trades": len(trades),
            "sharpe": metrics.get("sharpe"),
            "duration_ms": duration_ms,
        },
    )
    return result
