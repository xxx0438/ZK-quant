"""Test fixtures for CLI commands — synthetic Inputs for quick validation."""
import math
import time
from echo_quant.model import OHLCV, Inputs, OnchainData, OrderbookSnapshot

def sample_inputs(asset: str = "ETH", n_bars: int = 100) -> Inputs:
    """Generate deterministic synthetic Inputs for validation/dev."""
    now = 1_717_200_000  # fixed: deterministic
    base_price = {"BTC": 65000, "ETH": 3200, "SOL": 145}.get(asset.upper(), 100)
    bars = []
    price = float(base_price)
    for i in range(n_bars):
        ts = now - (n_bars - i - 1) * 3600
        # Sinusoidal walk for variety
        price *= 1 + 0.005 * math.sin(i / 7)
        bars.append(OHLCV(
            ts=ts, open=price * 0.999, high=price * 1.002, low=price * 0.998,
            close=price, volume=1_000_000 / price,
        ))

    return Inputs(
        asset=asset.upper(),
        timestamp=now,
        ohlcv_1h=bars,
        ohlcv_4h=bars[::4],
        orderbook=OrderbookSnapshot(
            bid_price=price * 0.9999, ask_price=price * 1.0001,
            bid_size_top10=500_000, ask_size_top10=500_000, spread_bps=2.0,
        ),
        funding_rate=0.00012,
        open_interest_usd=2_500_000_000,
        onchain=OnchainData(whale_netflow_24h_usd=12_000_000),
        snapshot_hash="fixture_" + asset.lower(),
    )
