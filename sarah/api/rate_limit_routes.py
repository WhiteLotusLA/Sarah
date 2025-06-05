"""
Rate limiting API routes for monitoring and management.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sarah.api.dependencies import get_current_user
from sarah.services.rate_limiter import rate_limiter
from sarah.sanctuary.permissions import require_permission

router = APIRouter(prefix="/api/rate-limit", tags=["rate-limit"])


class RateLimitStats(BaseModel):
    """Rate limit statistics response."""

    endpoint: str
    used: int
    limit: int
    remaining: int
    window_seconds: int


class RateLimitReset(BaseModel):
    """Rate limit reset request."""

    identifier: str
    endpoint: Optional[str] = None


@router.get("/stats")
async def get_rate_limit_stats(
    identifier: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    """Get rate limit statistics for current user or specified identifier."""
    if not identifier:
        # Use current user's identifier
        identifier = current_user.get("id", current_user.get("username"))

    try:
        stats = await rate_limiter.get_usage_stats(identifier)

        return {
            "identifier": identifier,
            "stats": [
                RateLimitStats(endpoint=endpoint, **endpoint_stats)
                for endpoint, endpoint_stats in stats.items()
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
@require_permission("rate_limit.reset")
async def reset_rate_limits(
    request: RateLimitReset, current_user: dict = Depends(get_current_user)
):
    """Reset rate limits for a specific identifier (admin only)."""
    try:
        await rate_limiter.reset_limits(request.identifier, request.endpoint)

        return {
            "message": "Rate limits reset successfully",
            "identifier": request.identifier,
            "endpoint": request.endpoint or "all",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_rate_limit_config(current_user: dict = Depends(get_current_user)):
    """Get current rate limit configuration."""
    from sarah.services.rate_limiter import RATE_LIMITS, USER_TIERS

    # Get user tier
    user_tier = await rate_limiter._get_user_tier(current_user.get("id"))
    tier_multiplier = USER_TIERS.get(user_tier, 1.0)

    config = {}
    for endpoint, (limit, window) in RATE_LIMITS.items():
        adjusted_limit = int(limit * tier_multiplier)
        config[endpoint] = {
            "base_limit": limit,
            "adjusted_limit": adjusted_limit,
            "window_seconds": window,
            "requests_per_second": round(adjusted_limit / window, 2),
        }

    return {
        "user_tier": user_tier,
        "tier_multiplier": tier_multiplier,
        "endpoints": config,
    }
