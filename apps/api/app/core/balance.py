"""Atomic balance operations: hold → confirm | release.

Why hold/confirm instead of debit/refund:
- Failed inference doesn't leave phantom charges in DB
- No race condition on refund path (idempotency cache pollution)
- Idempotency keys map cleanly to hold IDs
- Mental model matches Stripe PaymentIntent

Concurrency:
- Per-user distributed lock via redis.asyncio.lock.Lock (proper owner token)
- Hold amounts tracked in Redis with TTL (auto-expire if confirm forgotten)
- Sum of holds + DB balance = total liability per user
"""
import uuid
from typing import Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import Errors, raise_error
from app.db.models import User

# ─── Redis singleton ─────────────────────────────────────────
_redis: Optional[redis.Redis] = None

def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis

# ─── Key helpers ─────────────────────────────────────────────
def _hold_key(user_id: UUID | str, hold_id: str) -> str:
    return f"hold:{user_id}:{hold_id}"

def _hold_scan_pattern(user_id: UUID | str) -> str:
    return f"hold:{user_id}:*"

def _idem_key(idempotency_key: str) -> str:
    return f"idem:{idempotency_key}"

def _confirmed_key(user_id: UUID | str, hold_id: str) -> str:
    return f"hold_confirmed:{user_id}:{hold_id}"

def _lock_key(user_id: UUID | str) -> str:
    return f"balance_lock:{user_id}"

# ─── Sum existing holds for a user ──────────────────────────
async def _sum_existing_holds(r: redis.Redis, user_id: UUID | str) -> int:
    total = 0
    async for key in r.scan_iter(match=_hold_scan_pattern(user_id), count=100):
        val = await r.get(key)
        if val:
            try:
                total += int(val)
            except ValueError:
                pass
    return total

# ─── HOLD ────────────────────────────────────────────────────
async def hold_balance(
    user: User,
    cents: int,
    db: AsyncSession,
    idempotency_key: Optional[str] = None,
    ttl_seconds: int = 60,
) -> tuple[str, int]:
    """
    Reserve `cents` from user's balance. Atomic via per-user lock.

    Returns (hold_id, projected_free_balance_after_hold).
    Raises BALANCE_INSUFFICIENT if free balance (= DB balance − sum(holds)) < cents.

    The hold is tracked in Redis only; persistent DB balance is unchanged
    until confirm_hold() is called. Holds auto-expire after ttl_seconds.
    """
    if cents <= 0:
        return f"hold_zero_{uuid.uuid4().hex[:8]}", user.balance_usd_cents

    r = _get_redis()

    # Idempotency: if we've seen this key, return the prior hold
    if idempotency_key:
        prior = await r.get(_idem_key(idempotency_key))
        if prior:
            prior_amount = await r.get(_hold_key(user.id, prior))
            if prior_amount:
                # Hold still active
                projected = user.balance_usd_cents - int(prior_amount)
                return prior, projected
            # Prior hold expired — check confirmed cache instead
            confirmed = await r.get(_confirmed_key(user.id, prior))
            if confirmed:
                return prior, int(confirmed)
            # else: idempotency key is stale; fall through to new hold

    async with r.lock(
        _lock_key(user.id),
        timeout=15,            # max lock hold time
        blocking_timeout=3,    # max wait to acquire
    ):
        await db.refresh(user)
        current = user.balance_usd_cents
        held = await _sum_existing_holds(r, user.id)
        free = current - held

        if free < cents:
            raise_error(
                Errors.BALANCE_INSUFFICIENT,
                hint=(
                    f"Have {free}¢ free ({current}¢ balance − {held}¢ held), "
                    f"need {cents}¢. Top up via /v1/billing/topup."
                ),
            )

        hold_id = f"hold_{uuid.uuid4().hex[:16]}"
        pipe = r.pipeline()
        pipe.setex(_hold_key(user.id, hold_id), ttl_seconds, str(cents))
        if idempotency_key:
            pipe.setex(_idem_key(idempotency_key), ttl_seconds, hold_id)
        await pipe.execute()

        return hold_id, current - cents

# ─── CONFIRM ─────────────────────────────────────────────────
async def confirm_hold(user: User, hold_id: str, db: AsyncSession) -> int:
    """
    Convert a hold into a real DB debit. Returns new persistent balance.
    Idempotent: confirming twice returns the same final balance.
    """
    r = _get_redis()

    # Zero-amount hold (no-op)
    if hold_id.startswith("hold_zero_"):
        return user.balance_usd_cents

    # Idempotent confirm
    cached = await r.get(_confirmed_key(user.id, hold_id))
    if cached:
        return int(cached)

    amount_str = await r.get(_hold_key(user.id, hold_id))
    if not amount_str:
        raise_error(
            ("hold_expired", "Balance hold expired or invalid. Please retry.", 409)
        )
    amount = int(amount_str)

    async with r.lock(_lock_key(user.id), timeout=10, blocking_timeout=3):
        await db.refresh(user)
        if user.balance_usd_cents < amount:
            # Defense in depth — should not happen if holds were enforced
            await r.delete(_hold_key(user.id, hold_id))
            raise_error(Errors.BALANCE_INSUFFICIENT)

        new_balance = user.balance_usd_cents - amount
        await db.execute(
            update(User).where(User.id == user.id).values(balance_usd_cents=new_balance)
        )
        await db.commit()

        pipe = r.pipeline()
        pipe.delete(_hold_key(user.id, hold_id))
        pipe.setex(_confirmed_key(user.id, hold_id), 3600, str(new_balance))  # 1h idem
        await pipe.execute()

        return new_balance

# ─── RELEASE ─────────────────────────────────────────────────
async def release_hold(
    user_id: UUID | str,
    hold_id: str,
    idempotency_key: Optional[str] = None,
) -> None:
    """Free a held amount without charging (e.g., on inference failure).

    Also clears the idempotency mapping so the client can safely retry
    with the same Idempotency-Key.
    """
    if hold_id.startswith("hold_zero_"):
        return

    r = _get_redis()
    pipe = r.pipeline()
    pipe.delete(_hold_key(user_id, hold_id))
    if idempotency_key:
        pipe.delete(_idem_key(idempotency_key))
    await pipe.execute()

# ─── CREDIT (for topups & refunds) ──────────────────────────
async def credit_balance(
    user_id: UUID | str,
    cents: int,
    db: AsyncSession,
    reason: str = "topup",
) -> int:
    """Add credit to a user's balance. Returns new balance."""
    r = _get_redis()
    async with r.lock(_lock_key(user_id), timeout=10, blocking_timeout=5):
        user = await db.get(User, user_id)
        if not user:
            raise_error(("user_not_found", "User not found.", 404))
        new_balance = user.balance_usd_cents + cents
        await db.execute(
            update(User).where(User.id == user_id).values(balance_usd_cents=new_balance)
        )
        await db.commit()
        return new_balance
