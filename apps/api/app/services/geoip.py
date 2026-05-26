"""Simple geo-block via Cloudflare CF-IPCountry header or ipapi fallback."""
from fastapi import Request, HTTPException
from app.config import settings

async def check_not_blocked(request: Request):
    country = request.headers.get("CF-IPCountry", "").upper()
    if country and country in settings.geo_block_countries:
        raise HTTPException(403, f"Service unavailable in your region ({country})")
