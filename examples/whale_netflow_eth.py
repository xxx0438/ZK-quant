"""Whale Netflow ETH — buy when whales pull from CEX, sell when they push in.

Hypothesis:
- Net outflow from CEX → whales accumulating off-exchange → bullish
- Net inflow to CEX → whales preparing to sell → bearish
- Combined with funding rate to avoid crowded shorts
"""
from echo_quant import Model, Inputs, Signal

class WhaleNetflowEth(Model):
    model_id = "whale-netflow-eth"
    asset = "ETH"
    version = "v1.0.0"
    category = "factor"
    description = (
        "On-chain whale → CEX flow factor for ETH. Combines 24h netflow "
        "with funding rate context. Long when whales are accumulating "
        "off-exchange and funding is not over-extended."
    )
    expected_capacity_usd = 100_000.0

    @classmethod
    def required_data(cls):
        return ["onchain.whale_netflow_24h_usd", "funding_rate", "ohlcv_1h"]

    def predict(self, inputs: Inputs) -> Signal:
        netflow = inputs.onchain.whale_netflow_24h_usd if inputs.onchain else None
        funding = inputs.funding_rate

        if netflow is None or funding is None or not inputs.ohlcv_1h:
            return Signal(
                asset=inputs.asset, direction="neutral",
                edge_bps=0.0, expected_vol_bps=80.0,
            )

        # Scale: significant flow = > $10M
        flow_strength = max(min(netflow / 10_000_000, 3.0), -3.0)

        # Avoid trading with over-extended funding
        funding_bps = funding * 1e4
        funding_extreme = abs(funding_bps) > 5  # > 5 bps per 8h is extreme

        if flow_strength < -1.0 and not funding_extreme:
            # Whales accumulating, funding normal → long
            return Signal(
                asset=inputs.asset,
                direction="long",
                edge_bps=8.0 * abs(flow_strength),
                expected_vol_bps=80.0,
                confidence=min(0.5 + abs(flow_strength) * 0.1, 0.85),
                horizon_hours=4.0,
                metadata={"flow_strength": flow_strength, "funding_bps": funding_bps},
            )
        elif flow_strength > 1.0 and not funding_extreme:
            return Signal(
                asset=inputs.asset,
                direction="short",
                edge_bps=8.0 * abs(flow_strength),
                expected_vol_bps=80.0,
                confidence=min(0.5 + abs(flow_strength) * 0.1, 0.85),
                horizon_hours=4.0,
                metadata={"flow_strength": flow_strength, "funding_bps": funding_bps},
            )

        return Signal(
            asset=inputs.asset, direction="neutral",
            edge_bps=0.0, expected_vol_bps=80.0,
        )
