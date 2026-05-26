"""BTC spot-perp basis z-score factor."""
from echo_quant import Model, Inputs, Signal, zscore

class BasisZBtc(Model):
    model_id = "basis-z-btc"
    asset = "BTC"
    version = "v1.0.0"
    category = "factor"
    description = (
        "Spot-Perp basis dislocation factor. When perp trades meaningfully "
        "above spot (positive basis), it usually mean-reverts within 4-8h."
    )
    expected_capacity_usd = 500_000.0

    @classmethod
    def required_data(cls):
        return ["ohlcv_1h", "orderbook"]

    def predict(self, inputs: Inputs) -> Signal:
        if not inputs.orderbook or len(inputs.ohlcv_1h) < 48:
            return Signal(asset=inputs.asset, direction="neutral",
                          edge_bps=0.0, expected_vol_bps=70.0)

        # Use bid-ask midpoint as the "perp price" proxy
        # (in production: actual perp + spot from canonical data)
        perp = (inputs.orderbook.bid_price + inputs.orderbook.ask_price) / 2
        spot_close = inputs.ohlcv_1h[-1].close  # treat 1h spot close
        basis_bps = (perp - spot_close) / spot_close * 1e4

        # Historical basis distribution: compute from last 48 closes vs mids
        # For SDK simplicity here, use closes' own z-score as proxy
        closes = [b.close for b in inputs.ohlcv_1h[-48:]]
        z = zscore(closes, window=48)

        # If basis very positive AND price z-score very high → mean reversion short
        if basis_bps > 8.0 and z > 1.5:
            return Signal(
                asset=inputs.asset, direction="short",
                edge_bps=basis_bps * 0.5,
                expected_vol_bps=70.0,
                confidence=min(0.55 + basis_bps * 0.02, 0.85),
                horizon_hours=6.0,
                metadata={"basis_bps": basis_bps, "z": z},
            )
        elif basis_bps < -8.0 and z < -1.5:
            return Signal(
                asset=inputs.asset, direction="long",
                edge_bps=abs(basis_bps) * 0.5,
                expected_vol_bps=70.0,
                confidence=min(0.55 + abs(basis_bps) * 0.02, 0.85),
                horizon_hours=6.0,
                metadata={"basis_bps": basis_bps, "z": z},
            )
        return Signal(asset=inputs.asset, direction="neutral",
                      edge_bps=0.0, expected_vol_bps=70.0)
