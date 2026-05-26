"""Critical test: same data → same hash. Always."""
import pytest
from echo_data.schema import Inputs, OHLCV
from echo_data.snapshot import compute_snapshot_hash

def _build_inputs(ts: int = 1_717_200_000) -> Inputs:
    return Inputs(
        asset="ETH",
        timestamp=ts,
        ohlcv_1h=[
            OHLCV(ts=ts - i * 3600, open=3200.0 + i, high=3210.0 + i,
                  low=3190.0 + i, close=3200.0 + i, volume=1000.0)
            for i in range(10, 0, -1)
        ],
        funding_rate=0.00012,
        open_interest_usd=2_500_000_000.0,
    )

def test_identical_inputs_produce_identical_hash():
    a = _build_inputs()
    b = _build_inputs()
    assert compute_snapshot_hash(a) == compute_snapshot_hash(b)

def test_different_inputs_produce_different_hash():
    a = _build_inputs(ts=1_717_200_000)
    b = _build_inputs(ts=1_717_200_001)
    assert compute_snapshot_hash(a) != compute_snapshot_hash(b)

def test_snapshot_hash_excluded_from_self_hash():
    """Setting snapshot_hash should NOT change the computed hash."""
    a = _build_inputs()
    a_hashed = compute_snapshot_hash(a)
    # Set the field to something arbitrary and recompute
    b = a.model_copy(update={"snapshot_hash": "anything_at_all"})
    assert compute_snapshot_hash(b) == a_hashed

def test_floating_point_micro_changes_break_hash_as_designed():
    """6dp prices are stable; below-precision noise still differs by design.
    We round in normalizers before hashing, so end-to-end this is stable."""
    a = _build_inputs()
    bars = list(a.ohlcv_1h)
    bars[0] = bars[0].model_copy(update={"close": bars[0].close + 0.0000001})
    b = a.model_copy(update={"ohlcv_1h": bars})
    # Without normalization, hashes will differ → that's fine, normalizers
    # in SnapshotBuilder enforce precision before this point
    assert compute_snapshot_hash(a) != compute_snapshot_hash(b)
