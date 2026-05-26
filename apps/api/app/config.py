from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Core
    environment: str = "development"  # development | staging | production
    log_level: str = "INFO"
    
    # Database
    database_url: str = "postgresql+asyncpg://echo:echo@localhost:5432/echo"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # JWT / Auth
    jwt_secret: str = "change-me-in-prod-min-32-chars-required-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 168  # 7 days
    
    # CORS / Security
    cors_origins: List[str] = ["http://localhost:3000", "https://echo.ai", "https://*.echo.ai"]
    allowed_hosts: List[str] = ["*"]  # tighten in prod
    
    # External services
    enclave_endpoint: str = "http://localhost:9000"
    models_endpoint: str = "http://localhost:8001"
    intelligence_endpoint: str = "http://localhost:8002"
    
    # TEE
    cert_signing_key_path: str = "./keys/dev_signing_key.pem"
    use_nitro: bool = False
    
    # Blockchain (Base + USDC)
    base_rpc_url: str = "https://mainnet.base.org"
    usdc_address_base: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    echo_treasury_address: str = "0x0000000000000000000000000000000000000000"
    echo_capital_wallet: str = "0x0000000000000000000000000000000000000000"
    
    # Webhooks
    alchemy_webhook_secret: str = "dev"
    coinbase_commerce_webhook_secret: str = "dev"
    coinbase_commerce_api_key: str = ""
    
    # Observability
    sentry_dsn: str = ""
    posthog_key: str = ""
    
    # KYC / Compliance
    kyc_required_above_usd: int = 1000  # KYC tier above this monthly spend
    geo_block_countries: List[str] = ["IR", "KP", "SY", "CU"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
