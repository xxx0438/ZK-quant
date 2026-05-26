from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid, httpx, logging
from app.db.session import get_db
from app.db.models import User, Model, Prediction, PerformanceCert
from app.auth import get_current_user
from app.config import settings
from app.core.errors import Errors, raise_error
from app.core.ratelimit import enforce_rate_limit, PREDICT_LIMITER
from app.core.balance import debit_balance

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
    # Rate limit per user
    await enforce_rate_limit(f"user:{user.id}", PREDICT_LIMITER)
    
    model = await db.get(Model, body.model)
    if not model or not model.is_listed:
        raise_error(Errors.MODEL_NOT_FOUND, hint=f"Model '{body.model}'")
    
    # Atomic balance debit BEFORE inference (avoids charging on inference failure later)
    # Use prediction_id as idempotency key fallback
    pred_id = f"pred_{uuid.uuid4().hex[:12]}"
    idem = idempotency_key or pred_id
    
    new_balance = await debit_balance(user, model.price_per_call_cents, db, idempotency_key=idem)
    
    # Call inference service
    output = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{settings.models_endpoint}/infer",
                json={"model": model.id, "version": model.version, "inputs": body.inputs or {}},
            )
            r.raise_for_status()
            output = r.json()
    except Exception as e:
        # Refund on inference failure
        logger.exception("inference_failed", extra={"user_id": str(user.id), "model": model.id, "error": str(e)})
        # Reverse charge
        from sqlalchemy import update
        await db.execute(
            update(User).where(User.id == user.id).values(balance_usd_cents=User.balance_usd_cents + model.price_per_call_cents)
        )
        await db.commit()
        raise_error(Errors.INTERNAL, hint="Inference temporarily unavailable. Charge refunded.")
    
    # Load active cert
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
    
    pred = Prediction(
        id=pred_id, user_id=user.id, model_id=model.id,
        inputs=body.inputs, output=output,
        cost_cents=model.price_per_call_cents,
        cert_id=model.active_cert_id,
    )
    db.add(pred)
    await db.commit()
    
    logger.info("prediction_served", extra={
        "user_id": str(user.id), "model": model.id, "pred_id": pred_id,
        "cost_cents": model.price_per_call_cents,
    })
    
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
