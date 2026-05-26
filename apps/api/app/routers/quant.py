"""Quant marketplace endpoints.

POST   /v1/quant/register          → upgrade user to quant profile
POST   /v1/quant/models/upload-url → get presigned upload URL
POST   /v1/quant/models/submit     → declare uploaded artifact + trigger review
GET    /v1/quant/models            → list my submissions + listed models
GET    /v1/quant/earnings          → real-time earnings & pending payouts
GET    /v1/quant/payouts           → settlement history
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.errors import raise_error
from app.db.models import (
    Model,
    ModelSubmission,
    QuantProfile,
    RevenueLedger,
    User,
)
from app.db.session import get_db
from app.services.artifact_storage import presigned_put_url
from app.services.model_review import review_submission

router = APIRouter()
logger = logging.getLogger("echo.quant")

# ─────────────────── Schemas ───────────────────

class RegisterRequest(BaseModel):
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=2, max_length=64)
    bio: Optional[str] = Field(default=None, max_length=1000)
    payout_address: str = Field(min_length=42, max_length=42)

    @field_validator("payout_address")
    @classmethod
    def _valid_eth_addr(cls, v):
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("payout_address must be a 0x-prefixed Ethereum address")
        return v.lower()

class UploadURLRequest(BaseModel):
    proposed_model_id: str = Field(pattern=r"^[a-z0-9\-]+$", min_length=3, max_length=64)
    artifact_type: str = Field(default="artifact")  # "artifact" | "kit"

class SubmitRequest(BaseModel):
    proposed_model_id: str
    name: str = Field(min_length=3, max_length=128)
    description: Optional[str] = Field(default=None, max_length=4000)
    category: str = Field(default="factor")
    artifact_url: str
    artifact_sha256: str = Field(min_length=64, max_length=64)
    backtest_kit_url: str
    backtest_kit_sha256: str = Field(min_length=64, max_length=64)

# ─────────────────── Helpers ───────────────────

async def _get_profile_or_404(user: User, db: AsyncSession) -> QuantProfile:
    result = await db.execute(
        select(QuantProfile).where(QuantProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise_error(
            ("quant_profile_required", "Register as a quant first via /v1/quant/register.", 403),
        )
    return profile

# ─────────────────── Endpoints ───────────────────

@router.post("/v1/quant/register")
async def register_quant(
    body: RegisterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade a regular user to a quant profile.

    Sets default revenue share = 70%. Verified tier (75%) requires manual approval.
    """
    existing = await db.execute(
        select(QuantProfile).where(QuantProfile.user_id == user.id)
    )
    if existing.scalar_one_or_none():
        raise_error(("quant_already_registered", "User already has a quant profile.", 400))

    handle_taken = await db.execute(
        select(QuantProfile).where(QuantProfile.handle == body.handle)
    )
    if handle_taken.scalar_one_or_none():
        raise_error(("handle_taken", f"Handle '{body.handle}' is taken.", 400))

    profile = QuantProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        handle=body.handle,
        display_name=body.display_name,
        bio=body.bio,
        payout_address=body.payout_address,
        revenue_share_bps=7000,
    )
    db.add(profile)
    await db.commit()

    return {
        "profile_id": str(profile.id),
        "handle": profile.handle,
        "revenue_share_bps": profile.revenue_share_bps,
        "tier": profile.tier,
        "payout_address": profile.payout_address,
    }

@router.post("/v1/quant/models/upload-url")
async def get_upload_url(
    body: UploadURLRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns a presigned PUT URL for uploading an artifact or reproducibility kit."""
    profile = await _get_profile_or_404(user, db)
    suffix = "tar.gz" if body.artifact_type == "kit" else "bin"
    key = f"submissions/{profile.handle}/{body.proposed_model_id}/{body.artifact_type}.{suffix}"
    url = presigned_put_url(key, expires_in=600)
    return {
        "upload_url": url,
        "key": key,
        "expires_in": 600,
        "next": "PUT your file to upload_url, then call /v1/quant/models/submit.",
    }

@router.post("/v1/quant/models/submit")
async def submit_model(
    body: SubmitRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Declare an uploaded artifact + trigger automated TEE review."""
    profile = await _get_profile_or_404(user, db)

    # Reject if model_id already owned by another quant
    existing_model = await db.get(Model, body.proposed_model_id)
    if existing_model and existing_model.quant_user_id and existing_model.quant_user_id != user.id:
        raise_error(("model_id_taken", "Model ID already owned by another quant.", 400))

    submission = ModelSubmission(
        id=uuid.uuid4(),
        quant_profile_id=profile.id,
        proposed_model_id=body.proposed_model_id,
        name=body.name,
        description=body.description,
        category=body.category,
        artifact_url=body.artifact_url,
        artifact_sha256=body.artifact_sha256.lower(),
        backtest_kit_url=body.backtest_kit_url,
        backtest_kit_sha256=body.backtest_kit_sha256.lower(),
        review_status="verifying",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # Background: run TEE backtest + decide
    background_tasks.add_task(_run_review_task, str(submission.id))

    return {
        "submission_id": str(submission.id),
        "status": "verifying",
        "message": "TEE backtest queued. Poll /v1/quant/models for status.",
    }

async def _run_review_task(submission_id: str):
    """Background worker — re-opens its own DB session."""
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        submission = await db.get(ModelSubmission, uuid.UUID(submission_id))
        if not submission:
            return
        outcome, metrics, cert_id = await review_submission(submission, db)
        submission.review_status = outcome
        submission.review_metrics = metrics
        submission.reviewed_at = datetime.utcnow()
        if cert_id:
            submission.cert_id = cert_id
        await db.commit()

@router.get("/v1/quant/models")
async def list_my_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile_or_404(user, db)
    subs = await db.execute(
        select(ModelSubmission)
        .where(ModelSubmission.quant_profile_id == profile.id)
        .order_by(ModelSubmission.submitted_at.desc())
    )
    models = await db.execute(
        select(Model).where(Model.quant_user_id == user.id)
    )
    return {
        "submissions": [
            {
                "id": str(s.id),
                "model_id": s.proposed_model_id,
                "name": s.name,
                "status": s.review_status,
                "metrics": s.review_metrics,
                "submitted_at": s.submitted_at.isoformat(),
                "cert_id": s.cert_id,
            }
            for s in subs.scalars().all()
        ],
        "listed_models": [
            {
                "id": m.id,
                "name": m.name,
                "is_listed": m.is_listed,
                "price_per_call_cents": m.price_per_call_cents,
                "live_sharpe_30d": m.live_sharpe_30d,
            }
            for m in models.scalars().all()
        ],
    }

@router.get("/v1/quant/earnings")
async def my_earnings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Live earnings dashboard."""
    profile = await _get_profile_or_404(user, db)

    pending_q = await db.execute(
        select(func.coalesce(func.sum(RevenueLedger.quant_cents), 0))
        .where(
            RevenueLedger.quant_profile_id == profile.id,
            RevenueLedger.settled_at.is_(None),
        )
    )
    pending_cents = pending_q.scalar_one()

    settled_q = await db.execute(
        select(func.coalesce(func.sum(RevenueLedger.quant_cents), 0))
        .where(
            RevenueLedger.quant_profile_id == profile.id,
            RevenueLedger.settled_at.isnot(None),
        )
    )
    settled_cents = settled_q.scalar_one()

    # Per-model breakdown
    by_model_q = await db.execute(
        select(
            RevenueLedger.model_id,
            func.sum(RevenueLedger.quant_cents).label("earned"),
            func.count(RevenueLedger.id).label("calls"),
        )
        .where(RevenueLedger.quant_profile_id == profile.id)
        .group_by(RevenueLedger.model_id)
    )
    by_model = [
        {"model_id": r.model_id, "earned_cents": int(r.earned), "calls": r.calls}
        for r in by_model_q.all()
    ]

    return {
        "handle": profile.handle,
        "revenue_share_bps": profile.revenue_share_bps,
        "payout_address": profile.payout_address,
        "lifetime_earned_usd": (pending_cents + settled_cents) / 100,
        "pending_usd": pending_cents / 100,
        "settled_usd": settled_cents / 100,
        "next_settlement": "Monday 00:00 UTC",
        "by_model": by_model,
    }
