"""Atomic balance debit using Redis + DB write-through."""
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.db.models import User
from app.config import settings
from app.core.errors import Errors, raise_error

_redis = None
def _get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis

async def debit_balance(user: User, cents: int, db: AsyncSession, idempotency_key: str | None = None) -> int:
    """
    Atomically debit user balance. Returns new balance.
    Uses Redis lock to prevent race conditions on parallel requests.
    """
    r = _get_redis()
    lock_key = f"balance_lock:{user.id}"
    idem_key = f"idem:{idempotency_key}" if idempotency_key else None
    
    # Idempotency check
    if idem_key:
        cached = await r.get(idem_key)
        if cached:
            return int(cached)
    
    # Acquire lock (5s timeout)
    lock = await r.set(lock_key, "1", nx=True, ex=5)
    if not lock:
        # Brief retry
        import asyncio
        await asyncio.sleep(0.05)
        lock = await r.set(lock_key, "1", nx=True, ex=5)
        if not lock:
            raise_error(Errors.INTERNAL, hint="Could not acquire balance lock")
    
    try:
        await db.refresh(user)
        if user.balance_usd_cents < cents:
            raise_error(Errors.BALANCE_INSUFFICIENT)
        new_balance = user.balance_usd_cents - cents
        
        await db.execute(
            update(User).where(User.id == user.id).values(balance_usd_cents=new_balance)
        )
        await db.commit()
        
        if idem_key:
            await r.setex(idem_key, 3600, str(new_balance))  # 1h dedup window
        
        return new_balance
    finally:
        await r.delete(lock_key)
