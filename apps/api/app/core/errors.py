"""Centralized error envelope. Stripe-style."""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional

class EchoError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, hint: Optional[str] = None):
        self.code = code
        self.message = message
        self.status = status
        self.hint = hint

# Error codes — Stripe-style namespacing
class Errors:
    AUTH_INVALID_KEY = ("auth_invalid_key", "API key is invalid or revoked.", 401)
    AUTH_MISSING = ("auth_missing", "Missing Authorization header.", 401)
    BALANCE_INSUFFICIENT = ("balance_insufficient", "Insufficient balance. Top up via /v1/wallet/deposit.", 402)
    MODEL_NOT_FOUND = ("model_not_found", "Model not available or not listed.", 404)
    RATE_LIMITED = ("rate_limited", "Too many requests. Please slow down.", 429)
    KYC_REQUIRED = ("kyc_required", "This action requires sophistication declaration.", 403)
    INTERNAL = ("internal_error", "Something went wrong on our end.", 500)

def raise_error(code_tuple, hint: Optional[str] = None):
    code, msg, status = code_tuple
    raise EchoError(code, msg, status, hint)

async def echo_error_handler(request: Request, exc: EchoError):
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "hint": exc.hint,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "http_error",
                "message": exc.detail,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )
