"""
Hybrid caching system for I-ASCAP API.
Supports Redis (persistent) with automatic fallback to in-memory cache.

Cache backend selection:
  - "redis"  : Redis only (fails if unavailable)
  - "memory" : In-memory only
  - "auto"   : Try Redis first, fall back to in-memory (default)
"""

import hashlib
import inspect
import json
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger("cache")


# ==========================================================================
# In-Memory Cache Backend
# ==========================================================================

class InMemoryCache:
    """
    Simple in-memory cache with TTL-based expiration.
    Suitable for development and single-process deployments.
    """

    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}
        self._default_ttl = 3600

    async def get(self, key: str) -> Any | None:
        """Get a value from cache."""
        if key not in self._store:
            return None
        item = self._store[key]
        if item["expires_at"] < time.time():
            self._store.pop(key, None)
            return None
        return item["value"]

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in cache."""
        expires_at = time.time() + (ttl or self._default_ttl)
        self._store[key] = {"value": value, "expires_at": expires_at}

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        if key in self._store:
            self._store.pop(key, None)
            return True
        return False

    async def clear(self) -> None:
        """Clear all cached data."""
        self._store.clear()

    async def stats(self) -> dict[str, Any]:
        """Get cache stats."""
        now = time.time()
        active = sum(1 for v in self._store.values() if v["expires_at"] > now)
        return {
            "type": "in-memory",
            "total_keys": len(self._store),
            "active_keys": active,
            "status": "ok",
        }


# ==========================================================================
# Redis Cache Backend
# ==========================================================================

class RedisCache:
    """
    Redis-backed persistent cache.
    Survives restarts and works across multiple workers/containers.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._redis_url = redis_url
        self._client = None
        self._default_ttl = 3600

    async def _get_client(self) -> Any:
        """Lazy-initialize Redis client."""
        if self._client is None:
            import redis.asyncio as aioredis  # type: ignore[import]
            self._client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get a value from Redis."""
        client = await self._get_client()
        raw = await client.get(f"iascap:{key}")
        if raw is None:
            return None
        try:
            assert raw is not None  # Guarded by check on line 105
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in Redis with TTL."""
        client = await self._get_client()
        serialized = json.dumps(_normalize_cache_value(value), default=str)
        await client.set(f"iascap:{key}", serialized, ex=(ttl or self._default_ttl))

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        client = await self._get_client()
        result = await client.delete(f"iascap:{key}")
        return result > 0

    async def clear(self) -> None:
        """Clear all I-ASCAP keys from Redis."""
        client = await self._get_client()
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match="iascap:*", count=100)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break

    async def stats(self) -> dict[str, Any]:
        """Get Redis cache stats."""
        try:
            client = await self._get_client()
            info = await client.info("keyspace")
            db_info = info.get("db0", {})
            return {
                "type": "redis",
                "url": self._redis_url.split("@")[-1] if "@" in self._redis_url else self._redis_url,
                "keys": db_info.get("keys", 0) if isinstance(db_info, dict) else 0,
                "status": "ok",
            }
        except Exception as e:
            return {"type": "redis", "status": "error", "error": str(e)}


# ==========================================================================
# Cache Factory
# ==========================================================================

_cache = None


def _create_cache(
        backend: str = "auto",
        redis_url: str = "redis://localhost:6379/0"):
    """
    Create the appropriate cache backend.

    Args:
        backend: "redis", "memory", or "auto"
        redis_url: Redis connection URL
    """
    if backend == "memory":
        logger.info("Using in-memory cache (configured)")
        return InMemoryCache()

    if backend in ("redis", "auto"):
        try:
            import redis.asyncio  # noqa: F401  # type: ignore[import]
            cache = RedisCache(redis_url)
            logger.info(f"Using Redis cache: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
            return cache
        except ImportError as exc:
            if backend == "redis":
                raise RuntimeError(
                    "Redis cache requested but redis package not installed. "
                    "Install with: pip install redis[hiredis]>=5.0.0"
                ) from exc
            logger.info("redis package not installed, using in-memory cache")
            return InMemoryCache()
        except Exception as e:
            if backend == "redis":
                raise
            logger.warning(f"Redis unavailable ({e}), using in-memory cache")
            return InMemoryCache()

    logger.warning(f"Unknown cache backend '{backend}', using in-memory")
    return InMemoryCache()


def get_cache():
    """Get the singleton cache instance."""
    global _cache
    if _cache is None:
        try:
            from app.config import get_settings  # type: ignore[import]
            settings = get_settings()
            _cache = _create_cache(
                backend=getattr(
                    settings, "cache_backend", "auto"), redis_url=getattr(
                    settings, "redis_url", "redis://localhost:6379/0"), )
        except Exception:
            _cache = InMemoryCache()
    return _cache


def _normalize_cache_value(value: Any) -> Any:
    """Normalize values into stable JSON-serializable cache key components."""
    if isinstance(value, dict):
        return {str(k): _normalize_cache_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize_cache_value(v) for v in value]
    if isinstance(value, set):
        return sorted(_normalize_cache_value(v) for v in value)
    if hasattr(value, "model_dump"):
        return _normalize_cache_value(value.model_dump(mode="json"))
    if hasattr(value, "dict"):
        return _normalize_cache_value(value.dict())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _build_cache_payload(func: Callable[..., Any], *args, **kwargs) -> dict[str, Any]:
    """Bind call arguments and drop instance/class references from cache keys."""
    try:
        signature = inspect.signature(func)
        bound = signature.bind_partial(*args, **kwargs)
        arguments = dict(bound.arguments)
    except Exception:
        arguments = {
            "args": list(args),
            "kwargs": kwargs,
        }

    arguments.pop("self", None)
    arguments.pop("cls", None)

    return {
        key: _normalize_cache_value(value)
        for key, value in sorted(arguments.items())
    }


def _generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate a cache key from function arguments."""
    try:
        args_json = json.dumps(args, sort_keys=True, default=str)
        kwargs_json = json.dumps(kwargs, sort_keys=True, default=str)
        key_data = f"{prefix}:{args_json}:{kwargs_json}"
    except Exception:
        key_data = f"{prefix}:{str(args)}:{str(kwargs)}"
    return hashlib.sha256(key_data.encode()).hexdigest()


# ==========================================================================
# Caching Decorator
# ==========================================================================

def cached(ttl: int = 3600, prefix: str = ""):
    """
    Decorator to cache async function results.

    Usage:
        @cached(ttl=300, prefix="metrics")
        async def get_metrics(year: int, crop: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            key_prefix = prefix or func.__name__
            cache_payload = _build_cache_payload(func, *args, **kwargs)
            cache_key = _generate_cache_key(key_prefix, cache_payload)

            # Try cache
            try:
                cached_value: Any = await cache.get(cache_key)  # type: ignore[misc]
                if cached_value is not None:
                    logger.debug(f"Cache hit for {key_prefix}")
                    return cached_value
            except Exception as e:
                logger.warning(f"Cache get failed: {e}")

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                await cache.set(cache_key, result, ttl)
                logger.debug(f"Cached result for {key_prefix}")
            except Exception as e:
                logger.warning(f"Cache set failed: {e}")

            return result
        return wrapper
    return decorator


# ==========================================================================
# Standard TTL Constants
# ==========================================================================

class CacheTTL:
    """Standard cache TTL values in seconds."""

    # Static/rarely changing data
    DISTRICTS = 86400  # 24 hours
    STATES = 86400     # 24 hours
    LINEAGE = 86400    # 24 hours

    # Analytics results
    SUMMARY = 3600     # 1 hour
    SPLIT_EVENTS = 3600  # 1 hour
    ANALYSIS = 1800    # 30 minutes

    # Time-sensitive data
    METRICS = 300      # 5 minutes
    HEALTH = 60        # 1 minute
