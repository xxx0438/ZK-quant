"""Authentication: API keys, JWT sessions, and wallet sign-in (SIWE-lite).

Three credential types accepted on Authorization header:
1. `echo_sk_live_<48-char>` — long-lived API key (machine clients)
2. `<JWT>` — short-lived session token (browser/dashboard)
3. (future) `wallet:<addr>:<sig>` — direct wallet auth per request

Token detection is prefix-based to avoid ambiguous parsing.
"""
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from eth_account.messages import encode_defunct
from eth_account import Account

from app.config import settings
from app.db.session import get_db
from app.db.models import User, APIKey
from app.core.errors import Errors, raise_error

# Bcrypt for passwords (cost factor 12 ~250ms, tuned for web)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# auto_error=False so we can produce our own error envelope
security = HTTPBearer(auto_error=False)

API_KEY_PREFIX_LIVE = "echo_sk_live_"
API_KEY_PREFIX_TEST = "echo_sk_test_"

# ───────────────────────── Passwords ─────────────────────────

def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(password, hashed)
    except Exception:
        return False

# ───────────────────────── API Keys ─────────────────────────

def generate_api_key(test_mode: bool = False) -> tuple[str, str, str]:
    """
    Returns (full_key, prefix, sha256_hash).
    Full key shown to user ONCE. We store only prefix (for UX) + hash (for lookup).
    """
    prefix = API_KEY_PREFIX_TEST if test_mode else API_KEY_PREFIX_LIVE
    secret = secrets.token_urlsafe(36)  # ~48 chars
    full = f"{prefix}{secret}"
    # Prefix stored = full first 16 chars, enough to identify, not enough to forge
    stored_prefix = full[:20]
    key_hash = hashlib.sha256(full.encode()).hexdigest()
    return full, stored_prefix, key_hash

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

# ───────────────────────── JWT Sessions ─────────────────────────

def create_jwt(user_id: UUID, extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.jwt_expire_hours)).timestamp()),
        "iss": "echo-api",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_jwt(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )

# ─────────────────────── Wallet Sign-In (SIWE-lite) ───────────────────────

def build_siwe_message(address: str, nonce: str, issued_at: str) -> str:
    """Minimal SIWE-compatible message. Use full eth-siwe lib for prod."""
    return (
        f"echo.ai wants you to sign in with your Ethereum account:\n{address}\n\n"
        f"Sign in to Echo Protocol.\n\n"
        f"URI: https://echo.ai\nVersion: 1\nChain ID: 8453\n"
        f"Nonce: {nonce}\nIssued At: {issued_at}"
    )

def recover_signer(message: str, signature: str) -> Optional[str]:
    """Returns lowercase address that signed `message`, or None on failure."""
    try:
        msg = encode_defunct(text=message)
        addr = Account.recover_message(msg, signature=signature)
        return addr.lower()
    except Exception:
        return None

# ─────────────────────── Dependency: get_current_user ───────────────────────

async def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolves auth token (API key OR JWT) → User row.
    Attaches `user_id` to request.state for downstream logging.
    """
    if not creds or not creds.credentials:
        raise_error(Errors.AUTH_MISSING)

    token = creds.credentials.strip()
    user: Optional[User] = None

    # Branch 1: API key
    if token.startswith(API_KEY_PREFIX_LIVE) or token.startswith(API_KEY_PREFIX_TEST):
        stored_prefix = token[:20]
        key_hash = hash_api_key(token)
        result = await db.execute(
            select(APIKey).where(
                APIKey.key_prefix == stored_prefix,
                APIKey.key_hash == key_hash,
                APIKey.revoked == False,  # noqa: E712
            )
        )
        api_key_row = result.scalar_one_or_none()
        if not api_key_row:
            raise_error(Errors.AUTH_INVALID_KEY)
        user = await db.get(User, api_key_row.user_id)

    # Branch 2: JWT
    else:
        try:
            payload = decode_jwt(token)
            user = await db.get(User, UUID(payload["sub"]))
        except (JWTError, ValueError, KeyError):
            raise_error(Errors.AUTH_INVALID_KEY)

    if not user:
        raise_error(Errors.AUTH_INVALID_KEY)

    # Stash for logging / downstream middleware
    request.state.user_id = str(user.id)
    return user

async def get_current_user_optional(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Same as above but returns None instead of raising. For public-with-perks endpoints."""
    if not creds:
        return None
    try:
        return await get_current_user(request, creds, db)
    except Exception:
        return None
