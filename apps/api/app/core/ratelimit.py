"""Token bucket rate limiter using Redis."""
import time
import redis.asyncio as redis
from fastapi import Request, HTTPException
from app.config import settings
from app.core.errors import Errors, raise_error

_redis = None

def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis

class RateLimiter:
    """Token bucket: N requests per window."""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max = max_requests
        self.window = window_seconds
    
    async def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, remaining)."""
        r = get_redis()
        now = int(time.time())
        window_start = now - self.window
        
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self.window)
        results = await pipe.execute()
        
        count = results[1]
        remaining = max(0, self.max - count - 1)
        return count < self.max, remaining

# Different limits per endpoint type
PREDICT_LIMITER = RateLimiter(max_requests=100, window_seconds=60)  # 100/min for paid
AUTH_LIMITER = RateLimiter(max_requests=10, window_seconds=60)  # 10/min for auth

async def enforce_rate_limit(key: str, limiter: RateLimiter = PREDICT_LIMITER):
    allowed, remaining = await limiter.check(f"ratelimit:{key}")
    if not allowed:
        raise_error(Errors.RATE_LIMITED, hint=f"Limit {limiter.max} req per {limiter.window}s")
    return remaining
