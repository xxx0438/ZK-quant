"""Lightweight sophistication declaration. KYC vendor integration TODO."""
from app.db.models import User
from app.core.errors import Errors, raise_error

async def require_sophistication(user: User, action: str):
    """For high-value actions, require user has declared sophistication."""
    if not user.is_sophisticated:
        raise_error(
            Errors.KYC_REQUIRED,
            hint=f"Action '{action}' requires sophistication declaration. Visit /dashboard/verify.",
        )
