"""Re-export schema from echo_quant.

Why: Inputs / OHLCV / OrderbookSnapshot / OnchainData are the SAME types
the SDK uses. We must NOT define divergent copies — that's how marketplaces
get into the "looked good in backtest, broke in production" failure mode.

This file exists so consumers can `from echo_data.schema import Inputs`
without depending on the SDK directly. But the source of truth is echo_quant.
"""
from echo_quant.model import (
    Direction,
    Inputs,
    ModelCategory,
    OHLCV,
    OnchainData,
    OrderbookSnapshot,
    Signal,
)

__all__ = [
    "Direction",
    "Inputs",
    "ModelCategory",
    "OHLCV",
    "OnchainData",
    "OrderbookSnapshot",
    "Signal",
]
