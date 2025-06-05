"""
Rate limiting and throttling service for Sarah AI.

Provides API protection with per-user and per-endpoint limits.
"""

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any

import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from sarah.config import Config

# Rate limit configurations
RATE_LIMITS = {
    # Format: (requests, window_seconds)
    "default": (60, 60),  # 60 requests per minute
    "auth": (5, 60),  # 5 auth attempts per minute
    "backup": (10, 3600),  # 10 backup operations per hour
    "memory_search": (30, 60),  # 30 searches per minute
    "agent_action": (100, 60),  # 100 agent actions per minute
    "websocket": (1000, 60),  # 1000 messages per minute
}

# User tier limits multipliers
USER_TIERS = {
    "free": 1.0,
    "pro": 2.0,
    "enterprise": 10.0,
}


class RateLimiter:
    """
    Rate limiter using sliding window algorithm with Redis backend.
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.cache_ttl = 5  # Local cache TTL in seconds

    async def initialize(self):
        """Initialize Redis connection for rate limiting."""
        self.redis_client = await redis.from_url(
            f"redis://localhost:{Config.REDIS_PORT}/1"
        )

    async def shutdown(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()

    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"rate_limit:{identifier}:{endpoint}"

    def _get_bucket_key(self, key: str, timestamp: int, window: int) -> str:
        """Generate bucket key for sliding window."""
        bucket = timestamp // window
        return f"{key}:{bucket}"

    async def _get_user_tier(self, user_id: str) -> str:
        """Get user tier from database or cache."""
        # In a real implementation, this would query the database
        # For now, return default tier
        return "free"

    async def check_rate_limit(
        self, identifier: str, endpoint: str = "default", user_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.

        Returns:
            Tuple of (allowed, info_dict)
            info_dict contains: limit, remaining, reset_time
        """
        # Get rate limit configuration
        limit, window = RATE_LIMITS.get(endpoint, RATE_LIMITS["default"])

        # Apply user tier multiplier if user_id provided
        if user_id:
            tier = await self._get_user_tier(user_id)
            multiplier = USER_TIERS.get(tier, 1.0)
            limit = int(limit * multiplier)

        # Check local cache first (for performance)
        cache_key = f"{identifier}:{endpoint}"
        cached = self.local_cache.get(cache_key)
        if cached and time.time() - cached.get("timestamp", 0) < self.cache_ttl:
            if cached["count"] >= limit:
                return False, {"limit": limit, "remaining": 0, "reset": cached["reset"]}

        # Use Redis for distributed rate limiting
        current_time = int(time.time())
        key = self._get_key(identifier, endpoint)

        # Sliding window algorithm
        pipe = self.redis_client.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, current_time - window)

        # Count current window
        pipe.zcount(key, current_time - window, current_time)

        # Add current request
        pipe.zadd(key, {f"{current_time}:{id(identifier)}": current_time})

        # Set expiry
        pipe.expire(key, window + 1)

        results = await pipe.execute()
        count = results[1] + 1  # Including current request

        # Update local cache
        self.local_cache[cache_key] = {
            "count": count,
            "timestamp": current_time,
            "reset": current_time + window,
        }

        # Check if within limit
        allowed = count <= limit
        remaining = max(0, limit - count)
        reset_time = current_time + window

        return allowed, {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_time,
            "retry_after": window if not allowed else None,
        }

    async def get_usage_stats(self, identifier: str) -> Dict[str, Dict[str, int]]:
        """Get current usage statistics for an identifier."""
        stats = {}
        current_time = int(time.time())

        for endpoint, (limit, window) in RATE_LIMITS.items():
            key = self._get_key(identifier, endpoint)
            count = await self.redis_client.zcount(
                key, current_time - window, current_time
            )

            stats[endpoint] = {
                "used": count,
                "limit": limit,
                "remaining": max(0, limit - count),
                "window_seconds": window,
            }

        return stats

    async def reset_limits(self, identifier: str, endpoint: Optional[str] = None):
        """Reset rate limits for an identifier."""
        if endpoint:
            key = self._get_key(identifier, endpoint)
            await self.redis_client.delete(key)
        else:
            # Reset all endpoints
            pattern = f"rate_limit:{identifier}:*"
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor, match=pattern, count=100
                )
                if keys:
                    await self.redis_client.delete(*keys)
                if cursor == 0:
                    break

        # Clear local cache
        keys_to_remove = []
        for key in self.local_cache:
            if key.startswith(identifier):
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self.local_cache[key]


class ThrottleMiddleware:
    """
    FastAPI middleware for request throttling.
    """

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter

    async def __call__(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Extract identifier (IP address or user ID)
        identifier = self._get_identifier(request)

        # Extract endpoint from path
        endpoint = self._get_endpoint(request.url.path)

        # Extract user_id if authenticated
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.get("id")

        # Check rate limit
        allowed, info = await self.rate_limiter.check_rate_limit(
            identifier, endpoint, user_id
        )

        # Add rate limit headers to response
        response = (
            await call_next(request)
            if allowed
            else JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": info.get("retry_after", 60),
                },
            )
        )

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

        if not allowed:
            response.headers["Retry-After"] = str(info.get("retry_after", 60))

        return response

    def _get_identifier(self, request: Request) -> str:
        """Extract identifier from request."""
        # Try to get real IP from headers (for proxied requests)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client host
        return request.client.host if request.client else "unknown"

    def _get_endpoint(self, path: str) -> str:
        """Map URL path to endpoint category."""
        if path.startswith("/api/auth"):
            return "auth"
        elif path.startswith("/api/backup"):
            return "backup"
        elif path.startswith("/memory"):
            return "memory_search"
        elif path.startswith("/api/agents"):
            return "agent_action"
        elif path == "/ws":
            return "websocket"
        else:
            return "default"


# Decorator for custom rate limits
def rate_limit(endpoint: str, limit: int, window: int):
    """
    Decorator to apply custom rate limits to specific endpoints.

    Usage:
        @rate_limit("custom_endpoint", limit=10, window=60)
        async def my_endpoint():
            ...
    """
    # Register custom limit
    RATE_LIMITS[endpoint] = (limit, window)

    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            # Rate limiting is handled by middleware
            # This is just for registration
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


# Global rate limiter instance
rate_limiter = RateLimiter()


# Utility functions for manual rate limiting
async def check_rate_limit(
    identifier: str, endpoint: str = "default", user_id: Optional[str] = None
) -> None:
    """
    Check rate limit and raise HTTPException if exceeded.

    Usage in endpoints:
        await check_rate_limit(request.client.host, "my_endpoint")
    """
    allowed, info = await rate_limiter.check_rate_limit(identifier, endpoint, user_id)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info["reset"]),
                "Retry-After": str(info.get("retry_after", 60)),
            },
        )
