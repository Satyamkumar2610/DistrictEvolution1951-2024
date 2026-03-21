"""
Rate limiting middleware for I-ASCAP API.
Uses in-memory token bucket algorithm.
"""

import time
import asyncio
from typing import Dict, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
logger = get_logger("rate_limit")


class RateLimiter:
    """
    Token bucket rate limiter.
    Each IP gets a bucket that refills at a steady rate.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 20,
        cleanup_interval: int = 300,
    ):
        self.rate = requests_per_minute / 60.0  # Tokens per second
        self.burst_size = burst_size
        self.cleanup_interval = cleanup_interval

        # Bucket storage: {ip: (tokens, last_update_time)}
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()

        # Stats
        self._total_requests = 0
        self._blocked_requests = 0

    async def is_allowed(self, client_ip: str) -> Tuple[bool, Dict]:
        """
        Check if a request from the given IP is allowed.
        Returns (allowed, headers_dict).
        """
        async with self._lock:
            now = time.time()
            self._total_requests += 1

            # Periodic cleanup
            if now - self._last_cleanup > self.cleanup_interval:
                await self._cleanup_old_buckets(now)

            # Get or create bucket
            if client_ip in self._buckets:
                tokens, last_update = self._buckets[client_ip]
            else:
                tokens, last_update = self.burst_size, now

            # Refill tokens based on time passed
            time_passed = now - last_update
            tokens = min(float(self.burst_size), tokens + time_passed * self.rate)

            # Check if request is allowed
            if tokens >= 1:
                tokens -= 1
                self._buckets[client_ip] = (tokens, now)

                return True, {
                    "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                    "X-RateLimit-Remaining": str(int(tokens)),
                    "X-RateLimit-Reset": str(int(now + (self.burst_size - tokens) / self.rate)),
                }
            else:
                self._blocked_requests += 1
                retry_after = int((1 - tokens) / self.rate)

                return False, {
                    "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + retry_after)),
                    "Retry-After": str(retry_after),
                }

        # Fallback return to satisfy static analysis
        return False, {}

    async def _cleanup_old_buckets(self, now: float) -> None:
        """Remove stale bucket entries."""
        stale_threshold = now - 300  # 5 minutes
        stale_keys = [
            ip for ip, (_, last_update) in self._buckets.items()
            if last_update < stale_threshold
        ]
        for key in stale_keys:
            self._buckets.pop(key, None)

        self._last_cleanup = now
        if stale_keys:
            logger.debug(f"Cleaned up {len(stale_keys)} stale rate limit buckets")

    def stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "total_requests": self._total_requests,
            "blocked_requests": self._blocked_requests,
            "block_rate": round(
                float(self._blocked_requests) / self._total_requests * 100.0, 2
            ) if self._total_requests > 0 else 0.0,
            "active_buckets": len(self._buckets),
            "config": {
                "requests_per_minute": settings.rate_limit_per_minute,
                "burst_size": settings.rate_limit_burst,
            }
        }


# Global rate limiter instance
_rate_limiter = RateLimiter(
    requests_per_minute=settings.rate_limit_per_minute,
    burst_size=settings.rate_limit_burst,
)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply rate limiting to all requests.
    """

    # Paths that bypass rate limiting
    EXEMPT_PATHS = {
        "/health",
        "/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        rate_limiter = get_rate_limiter()
        allowed, headers = await rate_limiter.is_allowed(client_ip)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Please retry after {headers.get('Retry-After', 60)} seconds.",
                        "status_code": 429,
                    }},
                headers=headers,
            )

        # Process request and add rate limit headers
        response = await call_next(request)
        for key, value in headers.items():
            response.headers[key] = value

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, accounting for proxies."""
        # Check for forwarded header (Render, Vercel, etc.)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"
