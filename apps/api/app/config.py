"""Application configuration loaded from env vars / .env file.

Production safety:
- model_validator refuses to start in production with placeholder secrets
- CSV env strings are parsed into lists
- Type-coerced via Pydantic v2
"""
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ─── Core ────────────────────────────────────────────────
    environment: str = "development"              # development | staging | production
    log_level: str = "INFO"

    # ─── Database ────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://echo:echo@localhost:5432/echo"

    # ─── Redis ───────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ─── JWT / Auth ──────────────────────────────────────────
    jwt_secret: str = "dev-only-change-me-to-48-byte-random-secret-pls"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 168                   # 7 days

    # ─── Security ────────────────────────────────────────────
    cors_origins: List[str] = [
        "http://localhost:3000",
        "https://echo.ai",
        "https://*.echo.ai",
    ]
    allowed_hosts: List[str] = ["localhost", "127.0.0.1", "testserver"]

    # ─── External services ───────────────────────────────────
    enclave_endpoint: str = "http://localhost:9000"
    models_endpoint: str = "http://localhost:8001"
    intelligence_endpoint: str = "http://localhost:8002"

    # ─── TEE ─────────────────────────────────────────────────
    cert_signing_key_path: str = "./keys/dev_signing_key.pem"
    use_nitro: bool = False

    # ─── Blockchain ──────────────────────────────────────────
    base_rpc_url: str = "https://mainnet.base.org"
    usdc_address_base: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    echo_treasury_address: str = "0x0000000000000000000000000000000000000000"
    echo_capital_wallet: str = "0x0000000000000000000000000000000000000000"

    # ─── Webhooks ────────────────────────────────────────────
    alchemy_webhook_secret: str = "dev"
    coinbase_commerce_webhook_secret: str = "dev"
    coinbase_commerce_api_key: str = ""

    # ─── Observability ───────────────────────────────────────
    sentry_dsn: str = ""
    posthog_key: str = ""

    # ─── Compliance ──────────────────────────────────────────
    kyc_required_above_usd: int = 1000
    geo_block_countries: List[str] = ["IR", "KP", "SY", "CU"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Parse CSV env vars into lists ──────────────────────
    @field_validator(
        "cors_origins", "allowed_hosts", "geo_block_countries",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    # ─── Production safety enforcement ──────────────────────
    @model_validator(mode="after")
    def _enforce_production_safety(self):
        if self.environment != "production":
            return self

        problems: list[str] = []

        if "change-me" in self.jwt_secret or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be set to a 32+ char random value")

        if self.coinbase_commerce_webhook_secret in ("", "dev"):
            problems.append("COINBASE_COMMERCE_WEBHOOK_SECRET must be set")

        if self.alchemy_webhook_secret in ("", "dev"):
            problems.append("ALCHEMY_WEBHOOK_SECRET must be set")

        zero_addr = "0x" + "0" * 40
        if self.echo_treasury_address.lower() == zero_addr:
            problems.append("ECHO_TREASURY_ADDRESS must be set")
        if self.echo_capital_wallet.lower() == zero_addr:
            problems.append("ECHO_CAPITAL_WALLET must be set")

        if "*" in self.allowed_hosts:
            problems.append("ALLOWED_HOSTS must not contain '*' in production")
        if any(o == "*" for o in self.cors_origins):
            problems.append("CORS_ORIGINS must not contain '*' in production")

        if problems:
            joined = "\n  - ".join(problems)
            raise ValueError(f"Production config errors:\n  - {joined}")

        return self

settings = Settings()
