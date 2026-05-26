"""Echo model base class + standardized input/output schemas.

Why standardize:
- Echo's canonical data layer produces Inputs in this exact shape
- The runtime can validate before/after every call
- Backtest, live inference, and cert generation all share the contract
- Quants don't have to think about "what fields am I supposed to use?"
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ─────────────────── Output ───────────────────

Direction = Literal["long", "short", "neutral"]

class Signal(BaseModel):
    """Standard output schema for all Echo models.

    All models — factor, prediction, ensemble — return this shape.
    The allocator and downstream consumers can treat them uniformly.
    """

    asset: str = Field(..., description="Asset symbol, e.g. 'ETH', 'BTC'")
    direction: Direction = Field(..., description="Trade direction")
    edge_bps: float = Field(
        ...,
        description="Expected return in basis points (1 bp = 0.01%)",
    )
    expected_vol_bps: float = Field(
        ...,
        gt=0,
        description="Expected volatility in bps (must be > 0)",
    )
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Model confidence, 0-1",
    )
    horizon_hours: float = Field(
        default=4.0, gt=0,
        description="Prediction horizon in hours",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional debug/diagnostic fields; not used by allocator",
    )

    @field_validator("asset")
    @classmethod
    def _asset_upper(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("edge_bps")
    @classmethod
    def _sane_edge(cls, v: float) -> float:
        if abs(v) > 1000:  # 10% per call is already crazy
            raise ValueError(f"edge_bps {v} is implausibly large")
        return v

# ─────────────────── Input ───────────────────

class OHLCV(BaseModel):
    """Open-high-low-close-volume bar."""

    ts: int                    # unix seconds (bar close)
    open: float
    high: float
    low: float
    close: float
    volume: float              # in base asset units

class OrderbookSnapshot(BaseModel):
    """Snapshot of order book at a point in time."""

    bid_price: float
    ask_price: float
    bid_size_top10: float       # cumulative top-10 bid size in base
    ask_size_top10: float
    spread_bps: float

class OnchainData(BaseModel):
    """On-chain metrics (only populated for assets Echo tracks)."""

    whale_netflow_24h_usd: Optional[float] = None  # CEX inflow - outflow
    exchange_balance_usd: Optional[float] = None
    active_addresses_24h: Optional[int] = None
    extra: Optional[dict[str, Any]] = None

class Inputs(BaseModel):
    """Standard input schema. Built by Echo's canonical data layer."""

    asset: str
    timestamp: int                                  # unix seconds (when snapshot was built)
    ohlcv_1h: list[OHLCV] = Field(default_factory=list)  # most-recent first? no — chronological
    ohlcv_4h: list[OHLCV] = Field(default_factory=list)
    orderbook: Optional[OrderbookSnapshot] = None
    funding_rate: Optional[float] = None            # current funding (perps), as decimal (0.0001 = 0.01%)
    open_interest_usd: Optional[float] = None
    onchain: Optional[OnchainData] = None
    snapshot_hash: Optional[str] = None             # set by canonical data layer; do not write to it

    @field_validator("asset")
    @classmethod
    def _asset_upper(cls, v: str) -> str:
        return v.upper().strip()

# ─────────────────── Model base ───────────────────

ModelCategory = Literal["factor", "prediction", "signal", "ensemble"]

class Model(ABC):
    """Base class for all Echo models.

    Subclasses MUST declare:
      - model_id   (str, immutable identity)
      - asset      (str, primary asset traded)
      - version    (str, semantic version)

    And implement predict(inputs) -> Signal.

    Optional:
      - warmup()           — load weights, prime caches at startup
      - required_data()    — declare canonical-data fields the model needs

    Determinism:
      Your predict() MUST be deterministic given the same inputs.
      Random sampling MUST seed from inputs.snapshot_hash for reproducibility.

    Side effects:
      Your predict() MUST NOT make network calls or read disk during inference.
      All data comes via `inputs`. Echo runs you in a sandboxed container
      with networking disabled — calls will fail loudly.
    """

    # Required class attributes (override in subclass)
    model_id: str = ""
    asset: str = ""
    version: str = "v0.1.0"
    category: ModelCategory = "factor"

    # ─── Optional ───
    description: str = ""
    expected_call_cost_cents: int = 10
    expected_capacity_usd: float = 50_000.0

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Soft validation; full validation lives in `echo-cli validate`.
        if cls.__name__ != "Model" and not getattr(cls, "_skip_check", False):
            if not cls.model_id:
                raise TypeError(f"{cls.__name__} must define a non-empty model_id")
            if not cls.asset:
                raise TypeError(f"{cls.__name__} must define a non-empty asset")

    def warmup(self) -> None:
        """Optional. Called once at sandbox startup before any predict()."""
        pass

    @classmethod
    def required_data(cls) -> list[str]:
        """Declare which Inputs fields this model uses.

        Used by the runtime to skip fetching unnecessary data
        and by `echo-cli validate` to warn on schema mismatches.

        Valid values:
          'ohlcv_1h', 'ohlcv_4h', 'orderbook', 'funding_rate',
          'open_interest_usd', 'onchain.whale_netflow_24h_usd', ...
        """
        return ["ohlcv_1h"]

    @abstractmethod
    def predict(self, inputs: Inputs) -> Signal:
        """Run inference. Must be pure + deterministic."""
        ...

# ─────────────────── Helpers ───────────────────

def zscore(values: list[float], window: int) -> float:
    """Z-score of the most recent value over a trailing window. Pure NumPy."""
    import numpy as np

    if len(values) < window:
        return 0.0
    arr = np.array(values[-window:], dtype=float)
    mean = arr.mean()
    std = arr.std(ddof=1)
    if std == 0:
        return 0.0
    return float((arr[-1] - mean) / std)

def returns(values: list[float], lookback: int = 1) -> float:
    """Simple return over `lookback` bars."""
    if len(values) < lookback + 1:
        return 0.0
    return values[-1] / values[-1 - lookback] - 1
