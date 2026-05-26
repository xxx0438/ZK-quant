"""
Coinbase Commerce integration — accepts USDC, ETH, BTC payments.
Why Coinbase Commerce instead of Stripe for crypto-native users:
- No KYC barrier for small payments
- Native crypto rails
- Works globally without geo-restrictions
"""
import httpx, hmac, hashlib
from typing import Optional
from app.config import settings

BASE_URL = "https://api.commerce.coinbase.com"

async def create_charge(
    user_id: str,
    amount_usd: float,
    name: str = "Echo API Credit",
    description: Optional[str] = None,
) -> dict:
    """Creates a Coinbase Commerce charge. Returns hosted_url for user to pay."""
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(
            f"{BASE_URL}/charges",
            json={
                "name": name,
                "description": description or f"Top up Echo balance",
                "pricing_type": "fixed_price",
                "local_price": {"amount": str(amount_usd), "currency": "USD"},
                "metadata": {"user_id": user_id},
                "redirect_url": "https://echo.ai/dashboard?topup=success",
                "cancel_url": "https://echo.ai/dashboard?topup=cancel",
            },
            headers={
                "X-CC-Api-Key": settings.coinbase_commerce_api_key,
                "X-CC-Version": "2018-03-22",
            },
        )
        r.raise_for_status()
        return r.json()["data"]

def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Verify webhook signature from Coinbase Commerce."""
    expected = hmac.new(
        settings.coinbase_commerce_webhook_secret.encode(),
        raw_body, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
