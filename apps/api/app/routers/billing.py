"""Billing endpoints. Coinbase Commerce + direct USDC on Base."""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, Field
import logging
from app.db.session import get_db
from app.db.models import User, USDCDeposit
from app.auth import get_current_user
from app.services.coinbase_commerce import create_charge, verify_webhook_signature

router = APIRouter()
logger = logging.getLogger("echo.billing")

class TopupRequest(BaseModel):
    amount_usd: float = Field(..., ge=10, le=10000)

@router.post("/v1/billing/topup")
async def topup(
    body: TopupRequest,
    user: User = Depends(get_current_user),
):
    """Create a hosted payment URL via Coinbase Commerce. User pays in any crypto."""
    charge = await create_charge(
        user_id=str(user.id),
        amount_usd=body.amount_usd,
    )
    return {
        "checkout_url": charge["hosted_url"],
        "charge_id": charge["id"],
        "amount_usd": body.amount_usd,
        "expires_at": charge["expires_at"],
    }

@router.post("/v1/billing/coinbase/webhook")
async def coinbase_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Coinbase Commerce charge confirmation."""
    body = await request.body()
    signature = request.headers.get("x-cc-webhook-signature", "")
    
    if not verify_webhook_signature(body, signature):
        raise HTTPException(401, "Invalid signature")
    
    payload = await request.json()
    event_type = payload.get("event", {}).get("type", "")
    
    if event_type == "charge:confirmed":
        data = payload["event"]["data"]
        user_id = data.get("metadata", {}).get("user_id")
        amount_usd = float(data["pricing"]["local"]["amount"])
        amount_cents = int(amount_usd * 100)
        charge_id = data["id"]
        
        # Idempotency: don't double-credit
        existing = await db.execute(
            select(USDCDeposit).where(USDCDeposit.tx_hash == charge_id)
        )
        if existing.scalar_one_or_none():
            return {"ok": True, "note": "already_processed"}
        
        user = await db.get(User, user_id)
        if not user:
            logger.error("webhook_user_not_found", extra={"user_id": user_id})
            return {"ok": True}
        
        await db.execute(
            update(User).where(User.id == user.id)
            .values(balance_usd_cents=User.balance_usd_cents + amount_cents)
        )
        deposit = USDCDeposit(
            user_id=user.id, tx_hash=charge_id, amount_cents=amount_cents,
            from_address="coinbase_commerce", block_number=0,
        )
        db.add(deposit)
        await db.commit()
        logger.info("topup_confirmed", extra={
            "user_id": str(user.id), "amount_usd": amount_usd, "charge_id": charge_id,
        })
    
    return {"ok": True}
