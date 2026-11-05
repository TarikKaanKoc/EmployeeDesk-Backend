"""Shared outbound HTTP client (the mock ERP). One pool per process."""

from typing import Optional

import httpx

_client: Optional[httpx.AsyncClient] = None


def get_http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))
    return _client


async def close_http() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
