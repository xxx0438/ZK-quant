"""Billing: Coinbase Commerce hosted checkout + webhook + onchain USDC.

Endpoints:
  POST /v1/billing/topup              — create hosted checkout URL
  POST /v1/billing/coinbase/webhook   — Coinbase confirms charge
  POST /v1/billing/onchain/webhook    — Alchemy notifies of direct USDC transfer
  GET  /v1/billing/balance            — current balance + pending holds
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.balance import credit_balance
from app.db.models import USDCDeposit, User
from app.db.session import get_db
from app.services.coinbase_commerce import create_charge, verify_webhook_signature

router = APIRouter()
logger = logging.getLogger("echo.billing")

# ─── Schemas ─────────────────────────────────────────────────
class TopupRequest(BaseModel):
    amount_usd: float = Field(..., ge=10, le=10000)

# ─── Endpoints ───────────────────────────────────────────────
@router.post("/v1/billing/topup")
async def topup(body: TopupRequest, user: User = Depends(get_current_user)):
    """Create a hosted payment URL via Coinbase Commerce.

    User pays in any supported crypto (USDC, ETH, BTC, etc.);
    Coinbase calls our webhook on confirmation.
    """
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
    """Handle Coinbase Commerce charge confirmation.

    Idempotency: keyed on (source='coinbase_commerce', tx_hash=charge_id).
    Replay-safe — duplicate webhooks return {"ok": True, "note": "already_processed"}.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-cc-webhook-signature", "")

    if not verify_webhook_signature(raw_body, signature):
        logger.warning("coinbase_webhook_bad_signature")
        raise HTTPException(401, "Invalid signature")

    payload = await request.json()
    event_type = payload.get("event", {}).get("type", "")

    if event_type != "charge:confirmed":
        # Ignore other events (created, pending, failed) — only credit on confirmed
        return {"ok": True, "note": f"ignored event: {event_type}"}

    data = payload["event"]["data"]
    user_id = data.get("metadata", {}).get("user_id")
    if not user_id:
        logger.error("coinbase_webhook_no_user_id", extra={"charge_id": data.get("id")})
        return {"ok": True, "note": "no_user_id"}

    try:
        amount_usd = float(data["pricing"]["local"]["amount"])
    except (KeyError, ValueError, TypeError):
        logger.error("coinbase_webhook_bad_amount", extra={"charge_id": data.get("id")})
        return {"ok": True, "note": "bad_amount"}

    amount_cents = int(round(amount_usd * 100))
    charge_id = data["id"]

    # Idempotency check — composite key (source, tx_hash)
    existing = await db.execute(
        select(USDCDeposit).where(
            USDCDeposit.source == "coinbase_commerce",
            USDCDeposit.tx_hash == charge_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True, "note": "already_processed"}

    user = await db.get(User, user_id)
    if not user:
        logger.error("coinbase_webhook_user_not_found", extra={"user_id": user_id})
        return {"ok": True, "note": "user_not_found"}

    # Atomic credit via balance module (shares lock with debit path)
    new_balance = await credit_balance(user.id, amount_cents, db, reason="coinbase_topup")

    deposit = USDCDeposit(
        id=uuid.uuid4(),
        user_id=user.id,
        source="coinbase_commerce",
        tx_hash=charge_id,
        amount_cents=amount_cents,
        from_address="coinbase_commerce",
        block_number=0,
    )
    db.add(deposit)
    await db.commit()

    logger.info(
        "topup_confirmed",
        extra={
            "user_id": str(user.id),
            "source": "coinbase_commerce",
            "amount_usd": amount_usd,
            "charge_id": charge_id,
            "new_balance_cents": new_balance,
        },
    )
    return {"ok": True, "new_balance_cents": new_balance}

@router.post("/v1/billing/onchain/webhook")
async def onchain_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle direct USDC transfers to Echo treasury (Alchemy webhook).

    Idempotency: keyed on (source='onchain', tx_hash=eth_tx_hash).
    """
    # Verify Alchemy HMAC signature (impl in services/alchemy.py, not shown here)
    from app.services.alchemy import verify_alchemy_signature
    raw = await request.body()
    sig = request.headers.get("x-alchemy-signature", "")
    if not verify_alchemy_signature(raw, sig):
        raise HTTPException(401, "Invalid signature")

    payload = await request.json()
    # Alchemy "Address Activity" payload — adapt as needed
    activities = payload.get("event", {}).get("activity", [])

    credited = []
    for act in activities:
        if act.get("category") != "token" or act.get("asset") != "USDC":
            continue
        tx_hash = act["hash"]
        from_addr = act["fromAddress"]
        amount_usd = float(act["value"])
        amount_cents = int(round(amount_usd * 100))

        # Idempotency
        existing = await db.execute(
            select(USDCDeposit).where(
                USDCDeposit.source == "onchain",
                USDCDeposit.tx_hash == tx_hash,
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Match user by wallet_address
        user_q = await db.execute(
            select(User).where(User.wallet_address == from_addr.lower())
        )
        user = user_q.scalar_one_or_none()
        if not user:
            logger.warning("onchain_unknown_sender", extra={"from": from_addr, "tx": tx_hash})
            continue

        await credit_balance(user.id, amount_cents, db, reason="onchain_topup")
        db.add(USDCDeposit(
            id=uuid.uuid4(),
            user_id=user.id,
            source="onchain",
            tx_hash=tx_hash,
            amount_cents=amount_cents,
            from_address=from_addr,
            block_number=act.get("blockNum", 0),
        ))
        credited.append({"user_id": str(user.id), "amount_cents": amount_cents, "tx": tx_hash})

    await db.commit()
    return {"ok": True, "credited": credited}

@router.get("/v1/billing/balance")
async def get_balance(user: User = Depends(get_current_user)):
    """Return current balance + pending holds for the authenticated user."""
    from app.core.balance import _get_redis, _sum_existing_holds
    held = await _sum_existing_holds(_get_redis(), user.id)
    return {
        "balance_usd": user.balance_usd_cents / 100,
        "held_usd": held / 100,
        "available_usd": (user.balance_usd_cents - held) / 100,
    }
