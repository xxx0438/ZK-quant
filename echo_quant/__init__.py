"""Echo Protocol Quant SDK.

Usage:
    from echo_quant import Model, Inputs, Signal

    class MyModel(Model):
        model_id = "my-model"
        asset = "ETH"

        def predict(self, inputs: Inputs) -> Signal:
            return Signal(
                asset=inputs.asset,
                direction="long",
                edge_bps=10.0,
                expected_vol_bps=80.0,
            )

Then locally:
    echo-cli validate ./my_model.py
    echo-cli backtest ./my_model.py
    echo-cli package ./my_model.py
    echo-cli submit ./my_model.py
"""
from echo_quant.model import (
    Model,
    Inputs,
    Signal,
    OHLCV,
    OrderbookSnapshot,
    OnchainData,
    Direction,
    ModelCategory,
    zscore,
    returns,
)
from echo_quant.exceptions import (
    EchoError,
    ValidationError,
    BacktestError,
    PackagingError,
    ApiError,
)

__version__ = "0.4.3"

__all__ = [
    "Model",
    "Inputs",
    "Signal",
    "OHLCV",
    "OrderbookSnapshot",
    "OnchainData",
    "Direction",
    "ModelCategory",
    "zscore",
    "returns",
    "EchoError",
    "ValidationError",
    "BacktestError",
    "PackagingError",
    "ApiError",
]
