"""Backtest performance metrics. Pure functions, NumPy-only."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from echo_quant.backtest.runner import Trade

def compute_metrics(trades: list["Trade"]) -> dict:
    """Compute standard quant metrics from a list of trades.

    Returns a dict with:
      sharpe, sortino, win_rate, n_trades, avg_pnl_bps, total_pnl_bps,
      max_drawdown, calmar, profit_factor
    """
    if not trades:
        return {
            "n_trades": 0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "win_rate": 0.0,
            "avg_pnl_bps": 0.0,
            "total_pnl_bps": 0.0,
            "max_drawdown": 0.0,
            "calmar": 0.0,
            "profit_factor": 0.0,
        }

    pnl = np.array([t.pnl_bps_realized for t in trades], dtype=float)
    n = len(pnl)

    # Equity curve in bps
    equity = np.cumsum(pnl)

    # Sharpe (per-trade; we don't have a time grid for now)
    # In production, annualize using avg horizon. Here keep per-trade.
    mean = pnl.mean()
    std = pnl.std(ddof=1) if n > 1 else 0.0
    sharpe_pt = mean / std if std > 0 else 0.0
    # Approximate annual Sharpe assuming ~10 trades/day (tunable)
    sharpe_annual = sharpe_pt * math.sqrt(252 * 10)

    # Sortino
    downside = pnl[pnl < 0]
    dstd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    sortino_pt = mean / dstd if dstd > 0 else 0.0
    sortino_annual = sortino_pt * math.sqrt(252 * 10)

    # Drawdown
    peak = np.maximum.accumulate(equity)
    drawdown_bps = peak - equity
    max_dd_bps = float(drawdown_bps.max()) if len(drawdown_bps) else 0.0
    # As fraction of peak (avoiding div by zero)
    max_dd_pct = float(max_dd_bps / max(peak.max(), 1e-9)) if peak.max() > 0 else 0.0

    # Win rate
    wins = (pnl > 0).sum()
    win_rate = float(wins / n)

    # Profit factor
    gross_profit = float(pnl[pnl > 0].sum())
    gross_loss = float(-pnl[pnl < 0].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Calmar (annual return / max DD)
    total_bps = float(pnl.sum())
    calmar = sharpe_annual  # simplification when no time annualization

    return {
        "n_trades": n,
        "sharpe": round(sharpe_annual, 3),
        "sortino": round(sortino_annual, 3),
        "win_rate": round(win_rate, 4),
        "avg_pnl_bps": round(float(mean), 2),
        "total_pnl_bps": round(total_bps, 2),
        "max_drawdown_bps": round(max_dd_bps, 2),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "calmar": round(calmar, 3),
        "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else None,
        "gross_profit_bps": round(gross_profit, 2),
        "gross_loss_bps": round(gross_loss, 2),
    }
