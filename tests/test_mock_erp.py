"""The mock ERP itself: answers for any PR, filters by requester when
asked, knows nothing about who is signed in."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.mock_erp.main import app as erp_app


@pytest.fixture(scope="session")
async def erp():
    async with AsyncClient(
        transport=ASGITransport(app=erp_app), base_url="http://erp"
    ) as c:
        yield c


async def test_health(erp):
    assert (await erp.get("/health")).json()["status"] == "healthy"
    assert (await erp.get("/health/ready")).status_code == 200


async def test_get_any_pr(erp):
    r = await erp.get("/purchase-requests/PR-260101")
    assert r.status_code == 200
    body = r.json()
    assert body["requester_employee_id"] == "E1001"
    assert body["status"] == "under_review"
    assert body["mock_reference"] == "MOCK-ERP-8101"


async def test_lowercase_pr_number_is_normalised(erp):
    assert (await erp.get("/purchase-requests/pr-260101")).status_code == 200


async def test_unknown_pr_is_404(erp):
    assert (await erp.get("/purchase-requests/PR-000000")).status_code == 404


async def test_list_filters_by_requester(erp):
    r = await erp.get("/purchase-requests", params={"requester_id": "E1001"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == len(body["items"]) >= 1
    assert {i["requester_employee_id"] for i in body["items"]} == {"E1001"}


async def test_list_unfiltered_counts_the_pack(erp):
    r = await erp.get("/purchase-requests", params={"limit": 500})
    assert r.json()["total"] == 100
