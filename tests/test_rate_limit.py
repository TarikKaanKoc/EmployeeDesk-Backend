"""The limiter itself, exercised directly: the suite runs with
RATE_LIMITING off so the login tests can log in freely."""

import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.core.config import settings
from src.app.core.rate_limiter import rate_limit


async def test_limit_trips_after_n_requests():
    app = FastAPI()
    #: Counted in Redis under the path, so each run gets a fresh bucket.
    path = f"/ping-{uuid.uuid4().hex}"

    @app.get(path, dependencies=[rate_limit(3, 60)])
    async def ping():
        return {"ok": True}

    settings.RATE_LIMITING = True
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as c:
            codes = [(await c.get(path)).status_code for _ in range(5)]
    finally:
        settings.RATE_LIMITING = False
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]
