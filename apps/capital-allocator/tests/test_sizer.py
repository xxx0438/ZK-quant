import pytest
from app.sizer import kelly_size
from app.config import settings

def test_no_edge_returns_zero():
    d = kelly_size(edge_bps=0, expected_vol_bps=80, aum_usd=100_000)
    assert d.size_usd == 0
    assert d.rationale == "no_edge"

def test_zero_vol_returns_zero():
    d = kelly_size(edge_bps=15, expected_vol_bps=0, aum_usd=100_000)
    assert d.size_usd == 0
    assert "vol" in d.rationale

def test_kelly_capped_by_max_position_pct():
    """Huge edge → kelly_f explodes → must be capped at max_position_pct_of_aum."""
    d = kelly_size(edge_bps=500, expected_vol_bps=50, aum_usd=100_000)
    # raw kelly_f = 0.05 / (0.005)^2 = 2000 (absurd)
    # After * kelly_fraction (0.25) = 500, still capped
    assert d.size_usd <= settings.max_position_pct_of_aum * 100_000 + 0.01
    assert d.kelly_capped == settings.max_position_pct_of_aum

def test_realistic_size():
    d = kelly_size(edge_bps=15, expected_vol_bps=80, aum_usd=100_000)
    # kelly_f = 0.0015 / 0.0064 ≈ 0.234
    # * 0.25 quarter Kelly ≈ 0.0586
    # cap at 0.10 → not hit
    # size ≈ 5,860 USD
    assert 4000 < d.size_usd < 7000
    assert d.rationale == "ok"

def test_below_min_trade():
    d = kelly_size(edge_bps=1, expected_vol_bps=100, aum_usd=10_000)
    # Tiny edge → tiny size → below $50 floor
    assert d.size_usd == 0
    assert d.rationale.startswith("below_min")
