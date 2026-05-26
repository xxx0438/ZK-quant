"""Fractional-Kelly position sizing.

f* = edge / variance, in unit of equity. Clipped to:
  - kelly_fraction (e.g. 0.25 = quarter Kelly)
  - max_position_pct_of_aum
  - min_trade_usd floor
"""
import logging
from dataclasses import dataclass

from app.config import settings

log = logging.getLogger("allocator.sizer")

@dataclass
class SizeDecision:
    size_usd: float
    rationale: str
    kelly_raw: float
    kelly_capped: float

def kelly_size(
    edge_bps: float,
    expected_vol_bps: float,
    aum_usd: float,
) -> SizeDecision:
    """Compute target notional in USD.

    Inputs are in basis points (1 bp = 0.0001 = 0.01%).
    """
    if expected_vol_bps <= 0:
        return SizeDecision(0.0, "vol_nonpositive", 0.0, 0.0)
    if edge_bps <= 0:
        return SizeDecision(0.0, "no_edge", 0.0, 0.0)

    edge = edge_bps / 1e4
    vol = expected_vol_bps / 1e4
    variance = vol * vol
    kelly_f = edge / variance                       # fraction of equity
    capped = min(
        kelly_f * settings.kelly_fraction,
        settings.max_position_pct_of_aum,
    )
    size = capped * aum_usd

    if size < settings.min_trade_usd:
        return SizeDecision(0.0, f"below_min_{size:.2f}", kelly_f, capped)

    return SizeDecision(size, "ok", kelly_f, capped)
