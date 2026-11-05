"""The shared Redis connection: rate limits, token revocation, pending
confirmations. One client per process; every pod shares the same Redis.

`REDIS_URL=memory://` swaps in an in-process store with the same API, for
a single-instance deployment or local development: counters, revocations
and parked confirmations live for the life of the process and are not
shared across replicas, so `assert_production_ready` refuses it when more
than one replica is set.
"""

from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.app.core.config import settings

REDIS_ERRORS = (RedisConnectionError, RedisTimeoutError, OSError)

_client: Optional[Redis] = None


async def get_redis() -> Redis:
    global _client
    if _client is None:
        if settings.REDIS_URL.startswith("memory://"):
            from fakeredis import FakeAsyncRedis

            _client = FakeAsyncRedis(decode_responses=True)
            return _client
        _client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await _client.ping()
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
