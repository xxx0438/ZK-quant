"""Public cert lookup. Returns the full signed cert JSON."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PerformanceCert
from app.db.session import get_db

router = APIRouter()

@router.get("/v1/certs/{cert_id}")
async def get_cert(cert_id: str, db: AsyncSession = Depends(get_db)):
    """Return a signed cert. Public, no auth required."""
    row = await db.get(PerformanceCert, cert_id)
    if not row:
        raise HTTPException(404, {"code": "cert_not_found",
                                  "message": f"no cert with id {cert_id}"})
    # `attestation` JSON is the full signed cert
    return row.attestation
