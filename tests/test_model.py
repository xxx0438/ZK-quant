import pytest
from echo_quant import Model, Inputs, Signal, OHLCV

def test_signal_validation():
    s = Signal(
        asset="eth", direction="long", edge_bps=15.0, expected_vol_bps=80.0,
    )
    assert s.asset == "ETH"
    assert 0 <= s.confidence <= 1

def test_signal_rejects_huge_edge():
    with pytest.raises(ValueError):
        Signal(asset="ETH", direction="long", edge_bps=5000.0, expected_vol_bps=80.0)

def test_signal_rejects_zero_vol():
    with pytest.raises(ValueError):
        Signal(asset="ETH", direction="long", edge_bps=10.0, expected_vol_bps=0)

def test_inputs_asset_normalization():
    ins = Inputs(asset="eth", timestamp=1000)
    assert ins.asset == "ETH"

def test_model_requires_id():
    with pytest.raises(TypeError):
        class Bad(Model):
            asset = "ETH"
            def predict(self, inputs):
                return Signal(asset="ETH", direction="long", edge_bps=1, expected_vol_bps=80)

def test_model_works():
    class Good(Model):
        model_id = "test"
        asset = "ETH"
        def predict(self, inputs):
            return Signal(asset="ETH", direction="long", edge_bps=10, expected_vol_bps=80)

    m = Good()
    out = m.predict(Inputs(asset="ETH", timestamp=1000))
    assert out.direction == "long"
