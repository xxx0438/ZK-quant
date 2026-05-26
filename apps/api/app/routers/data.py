"""Public read-only endpoints for canonical snapshots.

Used by:
- Quant SDK `echo-cli verify` to replay a past prediction
- The forthcoming cert verifier (v4.4)
- Any external auditor
"""
from fastapi import APIRouter, HTTPException

from app.config import settings
from echo_data.client import CanonicalDataClient
from echo_data.replay import SnapshotNotFound, SnapshotIntegrityError

router = APIRouter()

_client: CanonicalDataClient | None = None

def _get_client() -> CanonicalDataClient:
    global _client
    if _client is None:
        _client = CanonicalDataClient(
            database_url=settings.database_url,
            redis_url=settings.redis_url,
        )
    return _client

@router.get("/v1/snapshots/{snapshot_hash}")
async def get_snapshot(snapshot_hash: str):
    """Replay a stored snapshot. Public; signature is the integrity proof."""
    try:
        inputs = await _get_client().replay(snapshot_hash, verify=True)
    except SnapshotNotFound:
        raise HTTPException(404, f"snapshot {snapshot_hash} not found")
    except SnapshotIntegrityError as e:
        raise HTTPException(500, f"snapshot integrity failure: {e}")
    return {
        "snapshot_hash": snapshot_hash,
        "inputs": inputs.model_dump(),
        "verified": True,
    }
