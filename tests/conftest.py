"""Shared fixtures.

The suite runs against the local docker-compose Postgres and Redis after
`pdm run migrate && pdm run seed && pdm run set-password --all
Synthetic-Pass-1`. Tests read synthetic rows and never change them; the
few that write roll back through their own fixtures.
"""

import os
from typing import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DEBUG", "true")
os.environ["RATE_LIMITING"] = "false"

from src.app.main import app  # noqa: E402

DEV_PASSWORD = "Synthetic-Pass-1"
ACTIVE_EMAIL = "user001@example.test"
ACTIVE_EMPLOYEE = "E1001"
OTHER_EMAIL = "user002@example.test"
INACTIVE_EMAIL = "user080@example.test"


@pytest.fixture(scope="session")
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def login(client: AsyncClient, email: str = ACTIVE_EMAIL) -> dict:
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": DEV_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
async def tokens(client: AsyncClient) -> dict:
    return await login(client)


@pytest.fixture
async def auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['accessToken']}"}
