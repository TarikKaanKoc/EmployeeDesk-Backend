"""API -> mock ERP over real HTTP, both in-process: the API's httpx
client is pointed at an ASGI transport wrapping the ERP app. Proves the
contract end to end without a second process."""

import httpx
import pytest

from src.app.core import http as core_http
from src.mock_erp.main import app as erp_app


@pytest.fixture
def erp_over_http(monkeypatch):
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=erp_app), base_url="http://erp"
    )
    monkeypatch.setattr(core_http, "_client", client)
    yield
    monkeypatch.setattr(core_http, "_client", None)


async def test_own_pr_through_real_contract(client, auth, erp_over_http):
    r = await client.get("/api/procurement/requests/PR-260101", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "prNumber": "PR-260101",
        "requesterEmployeeId": "E1001",
        "department": "Bus Operations",
        "businessPurpose": "Workshop diagnostic tools",
        "amountQar": "5000.00",
        "status": "under_review",
        "currentStep": "Budget validation",
        "createdDate": "2026-08-01",
        "lastUpdated": "2026-08-02",
        "reference": "MOCK-ERP-8101",
    }


async def test_others_pr_is_hidden_even_though_erp_returns_it(
    client, auth, erp_over_http
):
    # The ERP answers for PR-260102 (E1002's); the API must not pass it on.
    r = await client.get("/api/procurement/requests/PR-260102", headers=auth)
    assert r.status_code == 404


async def test_list_through_real_contract(client, auth, erp_over_http):
    r = await client.get("/api/procurement/requests", headers=auth)
    assert r.status_code == 200
    assert {x["requesterEmployeeId"] for x in r.json()["requests"]} == {"E1001"}
