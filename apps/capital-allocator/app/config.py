"""Allocator config. All from env. Hard-fails on prod placeholders."""
from typing import List, Literal
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class AllocatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Infra
    database_url: str = "postgresql+asyncpg://echo:echo@localhost:5432/echo"
    redis_url: str = "redis://localhost:6379"

    # Signal subscription
    signal_channel: str = "echo:signals"
    signal_min_sharpe: float = 1.0
    signal_max_age_seconds: int = 60

    # Sizing
    aum_usd: float = 100_000.0                # bootstrap AUM
    kelly_fraction: float = 0.25              # quarter Kelly
    max_position_pct_of_aum: float = 0.10     # 10% per position
    min_trade_usd: float = 50.0

    # Risk
    max_gross_leverage: float = 2.0
    max_net_leverage: float = 1.5
    daily_loss_circuit_breaker_pct: float = 0.05  # halt at -5% intraday
    per_model_capacity_buffer: float = 0.80       # use ≤80% of model's tested capacity

    # Hyperliquid
    hyperliquid_api_url: str = "https://api.hyperliquid.xyz"
    hyperliquid_wallet_address: str = ""
    hyperliquid_private_key: str = ""             # vault wallet, signs orders
    hyperliquid_use_testnet: bool = True

    # Asset universe (perp symbols on Hyperliquid)
    enabled_assets: List[str] = ["BTC", "ETH", "SOL"]

    # Public feed
    publish_channel: str = "echo:capital:feed"

    @field_validator("enabled_assets", mode="before")
    @classmethod
    def _split(cls, v):
        if isinstance(v, str):
            return [x.strip().upper() for x in v.split(",") if x.strip()]
        return v

    @model_validator(mode="after")
    def _check_prod(self):
        if self.environment == "production":
            errs = []
            if not self.hyperliquid_wallet_address:
                errs.append("HYPERLIQUID_WALLET_ADDRESS required")
            if not self.hyperliquid_private_key or self.hyperliquid_private_key == "dev":
                errs.append("HYPERLIQUID_PRIVATE_KEY required")
            if self.hyperliquid_use_testnet:
                errs.append("Production must not use testnet")
            if errs:
                raise ValueError("Allocator prod config:\n - " + "\n - ".join(errs))
        return self

settings = AllocatorSettings()
