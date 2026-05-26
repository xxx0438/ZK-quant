"""Funding rate mean-reversion — bet against extreme funding."""
from echo_quant import Model, Inputs, Signal

class FundingRateAnomaly(Model):
    model_id = "funding-rate-anomaly"
    asset = "BTC"
    version = "v1.0.0"
    category = "factor"
    description = (
        "Mean-reversion on perpetual funding extremes. When funding is "
        "very positive (longs overcrowded), short the perp. When very "
        "negative, long."
    )
    expected_capacity_usd = 250_000.0

    @classmethod
    def required_data(cls):
        return ["funding_rate", "open_interest_usd"]

    def predict(self, inputs: Inputs) -> Signal:
        funding = inputs.funding_rate
        oi = inputs.open_interest_usd
        if funding is None or oi is None:
            return Signal(asset=inputs.asset, direction="neutral",
                          edge_bps=0.0, expected_vol_bps=70.0)

        funding_bps = funding * 1e4  # 8h funding in bps

        # Require both extreme funding AND high OI for conviction
        oi_factor = min(oi / 5_000_000_000, 1.5)

        if funding_bps > 5.0:  # > 5 bps / 8h = annualized ~55%
            return Signal(
                asset=inputs.asset, direction="short",
                edge_bps=funding_bps * 0.6 * oi_factor,
                expected_vol_bps=70.0,
                confidence=min(0.5 + funding_bps * 0.03, 0.9),
                horizon_hours=8.0,
                metadata={"funding_bps": funding_bps, "oi_factor": oi_factor},
            )
        elif funding_bps < -5.0:
            return Signal(
                asset=inputs.asset, direction="long",
                edge_bps=abs(funding_bps) * 0.6 * oi_factor,
                expected_vol_bps=70.0,
                confidence=min(0.5 + abs(funding_bps) * 0.03, 0.9),
                horizon_hours=8.0,
                metadata={"funding_bps": funding_bps, "oi_factor": oi_factor},
            )
        return Signal(asset=inputs.asset, direction="neutral",
                      edge_bps=0.0, expected_vol_bps=70.0)
