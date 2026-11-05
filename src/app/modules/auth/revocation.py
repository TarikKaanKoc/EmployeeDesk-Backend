"""Token revocation - the "undo" a signed, stateless JWT lacks.

Three Redis records:
- `auth:revoked:{jti}`      one token revoked (logout); TTL = remaining life
- `auth:cutoff:{subject}`   every token issued before this instant is dead
- `auth:refresh:used:{jti}` a refresh token was spent; reuse outside a short
                            grace window means theft and revokes the family

Without Redis: checks are skipped in development, refused in production.
"""

import json
import time
from typing import Any, Dict, Iterable

from loguru import logger

from src.app.core.config import settings
from src.app.core.exceptions import Unavailable
from src.app.core.redis import REDIS_ERRORS, get_redis

REUSE_GRACE_SECONDS = 30


def _cutoff_ttl() -> int:
    return settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600 + 60


async def _redis():
    try:
        return await get_redis()
    except REDIS_ERRORS as exc:
        if settings.DEBUG:
            return None
        logger.error(f"Revocation store unavailable ({type(exc).__name__})")
        raise Unavailable("Service temporarily unavailable.") from exc


def _remaining(payload: Dict[str, Any]) -> int:
    return max(int(payload.get("exp", 0) - time.time()), 1)


async def is_revoked(payload: Dict[str, Any]) -> bool:
    redis = await _redis()
    if redis is None:
        return False
    jti, sub, iat = payload.get("jti"), payload.get("sub"), payload.get("iat")
    if not jti and not (sub and iat is not None):
        return False
    async with redis.pipeline(transaction=False) as pipe:
        if jti:
            pipe.exists(f"auth:revoked:{jti}")
        if sub and iat is not None:
            pipe.get(f"auth:cutoff:{sub}")
        results = list(await pipe.execute())
    if jti and results.pop(0):
        return True
    if sub and iat is not None:
        raw = results.pop(0)
        if raw is not None:
            record = json.loads(raw)
            if float(iat) <= float(record["ts"]) and jti not in record.get("keep", []):
                return True
    return False


async def revoke_token(payload: Dict[str, Any]) -> None:
    redis = await _redis()
    if redis is None or not payload.get("jti"):
        return
    await redis.set(f"auth:revoked:{payload['jti']}", "1", ex=_remaining(payload))


async def revoke_all_for(subject: str, keep: Iterable[str] = ()) -> None:
    redis = await _redis()
    if redis is None:
        return
    record = {"ts": int(time.time()), "keep": list(keep)}
    await redis.set(f"auth:cutoff:{subject}", json.dumps(record), ex=_cutoff_ttl())


async def consume_refresh(payload: Dict[str, Any]) -> bool:
    """Spend a refresh token. False if already spent; outside the grace
    window that is reuse, and the whole family is revoked."""
    redis = await _redis()
    if redis is None or not payload.get("jti"):
        return True
    key = f"auth:refresh:used:{payload['jti']}"
    now = time.time()
    first = await redis.set(key, repr(now), ex=_remaining(payload), nx=True)
    if first:
        return True
    used_at = float(await redis.get(key) or now)
    if now - used_at > REUSE_GRACE_SECONDS and payload.get("sub"):
        logger.warning(
            f"Refresh token reuse for {payload['sub']}: revoking every session"
        )
        await revoke_all_for(payload["sub"])
    return False
