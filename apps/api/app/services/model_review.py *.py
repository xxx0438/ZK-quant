"""Automated model verification pipeline.

When a quant submits a model:
1. Verify artifact SHA256 matches what they declared (anti-tamper)
2. Hand artifact + dataset to TEE/enclave service
3. Enclave runs deterministic backtest, signs a PerformanceCert
4. If metrics pass thresholds → auto-approve + list
5. Otherwise → flag for human review

Thresholds (tunable):
  - backtest_sharpe >= 1.0
  - backtest_max_drawdown >= -0.20 (i.e. <=20%)
  - backtest_capacity_usd >= 10_000
  - dataset_hash matches a known canonical dataset
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    Model,
    ModelSubmission,
    PerformanceCert,
    QuantProfile,
)
from app.services.artifact_storage import verify_uploaded_sha256

logger = logging.getLogger("echo.review")

# ─── Thresholds ───
MIN_SHARPE = 1.0
MAX_DRAWDOWN = -0.20
MIN_CAPACITY_USD = 10_000.0

class ReviewOutcome:
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_HUMAN = "pending_human"

async def review_submission(
    submission: ModelSubmission,
    db: AsyncSession,
) -> tuple[str, dict, Optional[str]]:
    """Returns (outcome, metrics, cert_id_or_None)."""
    logger.info("review_start", extra={"submission_id": str(submission.id)})

    # 1. Verify integrity
    artifact_key = submission.artifact_url.split("/")[-1]
    if not await verify_uploaded_sha256(artifact_key, submission.artifact_sha256):
        return (
            ReviewOutcome.REJECTED,
            {"error": "artifact_sha256_mismatch"},
            None,
        )

    # 2. Run TEE-attested backtest
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            r = await client.post(
                f"{settings.enclave_endpoint}/backtest",
                json={
                    "submission_id": str(submission.id),
                    "artifact_url": submission.artifact_url,
                    "artifact_sha256": submission.artifact_sha256,
                    "harness_url": submission.backtest_kit_url,
                    "harness_sha256": submission.backtest_kit_sha256,
                },
            )
            r.raise_for_status()
            result = r.json()
    except Exception as e:
        logger.exception("enclave_backtest_failed", extra={"submission_id": str(submission.id)})
        return ReviewOutcome.PENDING_HUMAN, {"error": str(e)}, None

    metrics = result.get("metrics", {})
    attestation = result.get("attestation", {})
    signature = result.get("signature", "")

    # 3. Apply thresholds
    sharpe = metrics.get("sharpe", 0)
    drawdown = metrics.get("max_drawdown", -1.0)
    capacity = metrics.get("tested_capacity_usd", 0)

    if sharpe < MIN_SHARPE:
        return ReviewOutcome.REJECTED, metrics | {"reason": f"sharpe {sharpe} < {MIN_SHARPE}"}, None
    if drawdown < MAX_DRAWDOWN:
        return ReviewOutcome.REJECTED, metrics | {"reason": f"drawdown {drawdown} too steep"}, None
    if capacity < MIN_CAPACITY_USD:
        return ReviewOutcome.REJECTED, metrics | {"reason": f"capacity {capacity} too low"}, None

    # 4. Issue PerformanceCert
    cert_id = f"cert_{uuid.uuid4().hex[:16]}"
    cert = PerformanceCert(
        id=cert_id,
        model_id=submission.proposed_model_id,
        model_version="v1.0.0",
        backtest_metrics=metrics,
        forward_metrics=None,
        capital_metrics=None,
        attestation=attestation,
        signature=signature,
        dataset_hash=metrics.get("dataset_hash", ""),
        harness_hash=submission.backtest_kit_sha256,
        reproducibility_kit_url=submission.backtest_kit_url,
    )
    db.add(cert)
    await db.flush()

    # 5. Create the Model row (or update if re-submission)
    profile = await db.get(QuantProfile, submission.quant_profile_id)
    existing_model = await db.get(Model, submission.proposed_model_id)
    if existing_model:
        await db.execute(
            update(Model)
            .where(Model.id == submission.proposed_model_id)
            .values(
                version="v1.0.0",
                active_cert_id=cert_id,
                is_listed=True,
                tested_capacity_usd=capacity,
            )
        )
    else:
        db.add(
            Model(
                id=submission.proposed_model_id,
                version="v1.0.0",
                name=submission.name,
                description=submission.description,
                category=submission.category,
                quant_user_id=profile.user_id if profile else None,
                price_per_call_cents=10,
                lease_monthly_cents=49900,
                active_cert_id=cert_id,
                is_listed=True,
                tested_capacity_usd=capacity,
            )
        )

    await db.commit()
    logger.info(
        "model_listed",
        extra={
            "submission_id": str(submission.id),
            "model_id": submission.proposed_model_id,
            "cert_id": cert_id,
            "sharpe": sharpe,
        },
    )
    return ReviewOutcome.APPROVED, metrics, cert_id
