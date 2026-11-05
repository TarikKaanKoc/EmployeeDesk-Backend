"""The only way the API talks to the ERP: HTTP to the mock service.

No import of `erp.purchase_requests` anywhere in `src/app`; the table
belongs to the mock ERP process. A dead ERP is reported as `UPSTREAM_FAILED`,
never papered over with a guess.
"""

from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.app.core.config import settings
from src.app.core.exceptions import UpstreamFailed
from src.app.core.http import get_http


def _url(path: str) -> str:
    return settings.MOCK_ERP_URL.rstrip("/") + path


async def _get(path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
    try:
        return await get_http().get(_url(path), params=params)
    except httpx.HTTPError as e:
        logger.warning(f"ERP unreachable: {e}")
        raise UpstreamFailed(
            "The procurement system is not reachable right now.", code="ERP_UNAVAILABLE"
        ) from e


async def list_for_requester(employee_id: str) -> List[Dict[str, Any]]:
    r = await _get("/purchase-requests", {"requester_id": employee_id})
    if r.status_code != 200:
        raise UpstreamFailed(
            "The procurement system returned an error.", code="ERP_ERROR"
        )
    return r.json()["items"]


async def get(pr_number: str) -> Optional[Dict[str, Any]]:
    r = await _get(f"/purchase-requests/{pr_number}")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise UpstreamFailed(
            "The procurement system returned an error.", code="ERP_ERROR"
        )
    return r.json()
