"""Liveness and readiness.

`/health/` says the process answers; `/health/ready` says it can do its
job (Postgres and Redis actually answer). Neither carries a rate limit:
the limiter counts in Redis, and a liveness probe that fails when Redis
blinks would have every pod restarted for an outage that is not theirs.
"""

import asyncio
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import text

from src.app.core.config import settings
from src.app.core.redis import get_redis
from src.app.database.connections import get_engine

router = APIRouter()

PROBE_TIMEOUT = 3.0


@router.get("/")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/live")
async def liveness_check():
    return {"status": "alive"}


async def _probe(name: str, coro) -> Dict[str, Any]:
    try:
        await asyncio.wait_for(coro, PROBE_TIMEOUT)
        return {"name": name, "status": "ok"}
    except Exception as e:  # noqa: BLE001 - every failure is a report here
        logger.warning(f"readiness: {name} failed: {e}")
        return {"name": name, "status": "fail"}


async def _postgres() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _redis() -> None:
    await (await get_redis()).ping()


@router.get("/ready")
async def readiness_check():
    checks = [await _probe("postgres", _postgres()), await _probe("redis", _redis())]
    checks.append(
        {
            "name": "azure_openai",
            "status": "configured"
            if settings.embeddings_configured
            else "unconfigured",
        }
    )
    ok = all(c["status"] != "fail" for c in checks)
    body: Dict[str, Any] = {"status": "ready" if ok else "not_ready"}
    if settings.DEBUG:
        body["checks"] = checks
    return JSONResponse(status_code=200 if ok else 503, content=body)
