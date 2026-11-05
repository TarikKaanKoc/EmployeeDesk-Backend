"""`rate_limit(times, seconds)` - a sliding window per caller and path,
counted in Redis so every replica shares the same limit.

Rate limiting is a control, not a feature: in development a missing Redis
degrades to per-process counting; in production it refuses to serve,
because a limit nobody shares is not a limit.
"""

from collections import OrderedDict
from time import monotonic
from typing import Awaitable, Callable, Optional

from fastapi import Depends, HTTPException, Request
from loguru import logger
from pyrate_limiter import Duration, InMemoryBucket, Limiter, Rate, RedisBucket

from src.app.core.config import settings
from src.app.core.redis import REDIS_ERRORS, get_redis


def client_ip(request: Request) -> str:
    """`X-Forwarded-For` is honoured only from a proxy we operate, or from
    loopback in development. From anywhere else it is a spoofable header."""
    direct = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if not forwarded:
        return direct
    trusted = settings.trusted_proxy_ips or (
        {"127.0.0.1", "::1"} if settings.DEBUG else set()
    )
    if direct in trusted:
        return forwarded.split(",")[0].strip() or direct
    return direct


IdentityResolver = Callable[[Request], Awaitable[Optional[str]]]
_identity_resolver: Optional[IdentityResolver] = None


def set_identity_resolver(resolver: IdentityResolver) -> None:
    """The API layer registers how a request maps to an account; until then
    (or when it answers None) the limit counts per address."""
    global _identity_resolver
    _identity_resolver = resolver


async def get_user_identifier(request: Request) -> str:
    path = request.scope["path"]
    if _identity_resolver is not None:
        try:
            user_id = await _identity_resolver(request)
        except Exception as e:  # noqa: BLE001 - an identity failure must not refuse the request
            logger.warning(f"Rate limit identity failed, using IP: {e}")
            user_id = None
        if user_id:
            return f"{user_id}:{path}"
    return f"{client_ip(request)}:{path}"


_REPROBE_AFTER = 30.0
_redis_available: bool | None = None
_redis_checked_at: float = 0.0


async def _redis_or_none():
    global _redis_available, _redis_checked_at
    now = monotonic()
    if _redis_available is False and now - _redis_checked_at < _REPROBE_AFTER:
        return None
    try:
        redis = await get_redis()
        if _redis_available is False:
            logger.info("Redis is back; rate limits are shared again.")
        _redis_available = True
        _redis_checked_at = now
        return redis
    except REDIS_ERRORS as exc:
        if not settings.DEBUG:
            logger.error(
                f"Redis unavailable ({type(exc).__name__}); refusing to serve unlimited."
            )
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable."
            ) from exc
        if _redis_available is not False:
            logger.warning(
                f"Redis unavailable ({type(exc).__name__}); rate limits counted per instance."
            )
        _redis_available = False
        _redis_checked_at = now
        return None


def rate_limit(times: int, seconds: int):
    rates = [Rate(times, Duration.SECOND * seconds)]
    limiters: OrderedDict[str, Limiter] = OrderedDict()
    cache_size = 2048

    async def dependency(request: Request) -> None:
        if not settings.RATE_LIMITING:
            return
        identifier = await get_user_identifier(request)
        limiter = limiters.get(identifier)
        if limiter is not None:
            limiters.move_to_end(identifier)
        else:
            redis = await _redis_or_none()
            if redis is None:
                bucket = InMemoryBucket(rates)
            else:
                bucket = await RedisBucket.init(
                    rates, redis, f"ratelimit:{times}:{seconds}:{identifier}"
                )
            limiter = Limiter(bucket)
            limiters[identifier] = limiter
            while len(limiters) > cache_size:
                limiters.popitem(last=False)
        allowed = await limiter.try_acquire_async(identifier, blocking=False)
        if not allowed:
            raise HTTPException(status_code=429, detail="Too Many Requests")

    return Depends(dependency)
