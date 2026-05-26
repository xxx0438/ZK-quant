# echo-quant

> Build, test, and ship quant models to Echo Protocol.

```bash
pip install echo-quant
```

## Hello world

```python
# my_model.py
from echo_quant import Model, Inputs, Signal, zscore

class MyMomentumModel(Model):
    model_id = "my-momentum-eth"
    asset = "ETH"

    def predict(self, inputs: Inputs) -> Signal:
        closes = [bar.close for bar in inputs.ohlcv_1h]
        z = zscore(closes, window=24)
        return Signal(
            asset=inputs.asset,
            direction="long" if z > 1 else "short" if z < -1 else "neutral",
            edge_bps=10 * abs(z),
            expected_vol_bps=80,
            confidence=min(0.5 + abs(z) * 0.1, 0.9),
        )
```

## Workflow

```bash
echo-cli init my-momentum-eth        # scaffold
echo-cli validate ./my_model.py       # interface + determinism checks
echo-cli backtest ./my_model.py       # 90d historical backtest
echo-cli package ./my_model.py        # produces dist/*.onnx + *.kit.tar.gz
echo-cli submit ./my_model.py         # uploads to Echo marketplace
```

## Requirements

- Python 3.11+
- Your `predict()` must be **deterministic** (same inputs → same output)
- Your model must be **ONNX-exportable** (or implement `to_onnx()`)
- No network calls / disk reads inside `predict()` — runtime sandbox forbids it

See `examples/` for three complete reference models.

## License

MIT
