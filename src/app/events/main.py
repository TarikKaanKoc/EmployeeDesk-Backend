from loguru import logger
from sqlalchemy import text

from src.app.core.config import settings
from src.app.core.http import close_http
from src.app.core.redis import REDIS_ERRORS, close_redis, get_redis
from src.app.database.connections import close_engine, get_engine


async def startup_event() -> None:
    settings.assert_production_ready()
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))
    try:
        await get_redis()
    except REDIS_ERRORS as e:
        if not settings.DEBUG:
            raise
        logger.warning(f"Redis not reachable at startup: {e}")
    logger.info(f"{settings.APP_NAME} {settings.APP_VERSION} started")


async def shutdown_event() -> None:
    await close_http()
    await close_redis()
    await close_engine()
