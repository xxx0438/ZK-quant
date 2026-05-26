"""Prediction endpoint.

Flow:
  1. Rate limit
  2. Load model
  3. HOLD balance (Redis-only; DB untouched)
  4. Run inference
     ├─ Success → CONFIRM hold (atomic DB debit)
     └─ Failure → RELEASE hold (user not charged, idempotency cleared)
  5. Persist Prediction row
  6. Return result + balance + cert + disclaimer
"""
import logging
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.core.balance import confirm_hold, hold_balance, release_hold
from app.core.errors import Errors, raise_error
from app.core.ratelimit import PREDICT_LIMITER, enforce_rate_limit
from app.db.models import Model, PerformanceCert, Prediction, User
from app.db.session import get_db

router = APIRouter()
logger = logging.getLogger("echo.predict")

class PredictRequest(BaseModel):
    model: str = Field(..., description="Model ID (e.g. 'whale-netflow-eth')")
    inputs: Optional[Dict[str, Any]] = Field(default_factory=dict)

@router.post("/v1/predict")
async def predict(
    body: PredictRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Per-user rate limit
    await enforce_rate_limit(f"user:{user.id}", PREDICT_LIMITER)

    # 2. Load model
    model = await db.get(Model, body.model)
    if not model or not model.is_listed:
        raise_error(Errors.MODEL_NOT_FOUND, hint=f"Model '{body.model}'")

    pred_id = f"pred_{uuid.uuid4().hex[:12]}"
    idem = idempotency_key or pred_id

    # 3. HOLD balance — DB untouched until inference succeeds
    hold_id, _projected_free = await hold_balance(
        user,
        cents=model.price_per_call_cents,
        db=db,
        idempotency_key=idem,
        ttl_seconds=60,
    )

    # 4. Inference (with refund-on-failure)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{settings.models_endpoint}/infer",
                json={
                    "model": model.id,
                    "version": model.version,
                    "inputs": body.inputs or {},
                },
            )
            r.raise_for_status()
            output = r.json()
    except Exception as e:
        # Release hold — user is NOT charged
        await release_hold(user.id, hold_id, idempotency_key=idem)
        logger.exception(
            "inference_failed",
            extra={
                "user_id": str(user.id),
                "model": model.id,
                "error": str(e),
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise_error(
            Errors.INTERNAL,
            hint="Inference temporarily unavailable. Your balance was not charged.",
        )

    # 5. CONFIRM hold — atomic DB debit
    new_balance = await confirm_hold(user, hold_id, db)

    # 6. Load active cert (best-effort)
    cert_data = None
    if model.active_cert_id:
        cert = await db.get(PerformanceCert, model.active_cert_id)
        if cert:
            cert_data = {
                "cert_id": cert.id,
                "backtest_metrics": cert.backtest_metrics,
                "live_metrics": {
                    "sharpe_30d": model.live_sharpe_30d,
                    "sharpe_90d": model.live_sharpe_90d,
                    "sharpe_inception": model.live_sharpe_inception,
                },
                "tested_capacity_usd": model.tested_capacity_usd,
                "verified_by": cert.attestation.get("source", "aws-nitro-enclave"),
                "attestation_url": f"https://api.echo.ai/v1/certs/{cert.id}",
                "echo_capital_wallet": settings.echo_capital_wallet,
                "reproducibility_kit": cert.reproducibility_kit_url,
            }

    # 7. Persist prediction row
    pred = Prediction(
        id=pred_id,
        user_id=user.id,
        model_id=model.id,
        inputs=body.inputs,
        output=output,
        cost_cents=model.price_per_call_cents,
        cert_id=model.active_cert_id,
    )
    db.add(pred)
    await db.commit()

    logger.info(
        "prediction_served",
        extra={
            "user_id": str(user.id),
            "model": model.id,
            "pred_id": pred_id,
            "cost_cents": model.price_per_call_cents,
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    return {
        "id": pred_id,
        "model": model.id,
        "model_version": model.version,
        "prediction": output,
        "performance_cert": cert_data,
        "cost_usd": model.price_per_call_cents / 100,
        "balance_usd": new_balance / 100,
        "disclaimer": (
            "Quantitative output only. NOT investment advice. "
            "Past performance does not guarantee future results. "
            "Use at your own risk."
        ),
    }

# 8. Write revenue split (marketplace v4.2)
    from app.services.payout_settlement import record_revenue_split

    await record_revenue_split(
        db=db,
        prediction_id=pred_id,
        model=model,
        gross_cents=model.price_per_call_cents,
    )
