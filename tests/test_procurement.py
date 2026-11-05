"""The API reaches the ERP only over HTTP; the scope check happens on
what comes back. The ERP is stubbed here; `test_mock_erp.py` covers the
real service once it exists."""

import pytest

from src.app.core.config import settings
from src.app.modules.procurement import erp_client

OWN = {
    "pr_number": "PR-260101",
    "requester_employee_id": "E1001",
    "department": "Bus Operations",
    "business_purpose": "Workshop diagnostic tools",
    "amount_qar": "5000.00",
    "status": "under_review",
    "current_step": "Budget validation",
    "created_date": "2026-08-01",
    "last_updated": "2026-08-02",
    "mock_reference": "MOCK-ERP-8101",
}
THEIRS = {
    **OWN,
    "pr_number": "PR-260102",
    "requester_employee_id": "E1002",
    "status": "approved",
}


@pytest.fixture
def erp(monkeypatch):
    table = {OWN["pr_number"]: OWN, THEIRS["pr_number"]: THEIRS}

    async def fake_get(pr):
        return table.get(pr)

    async def fake_list(employee_id):
        return [r for r in table.values() if r["requester_employee_id"] == employee_id]

    monkeypatch.setattr(erp_client, "get", fake_get)
    monkeypatch.setattr(erp_client, "list_for_requester", fake_list)


async def test_own_pr_status(client, auth, erp):
    r = await client.get("/api/procurement/requests/PR-260101", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "under_review" and body["requesterEmployeeId"] == "E1001"


async def test_other_requesters_pr_is_404(client, auth, erp):
    r = await client.get("/api/procurement/requests/PR-260102", headers=auth)
    assert r.status_code == 404
    assert r.json()["errorCode"] == "PURCHASE_REQUEST_NOT_FOUND"


async def test_unknown_pr_is_404(client, auth, erp):
    r = await client.get("/api/procurement/requests/PR-999999", headers=auth)
    assert r.status_code == 404


async def test_list_is_filtered_to_caller(client, auth, erp):
    r = await client.get("/api/procurement/requests", headers=auth)
    assert r.status_code == 200
    assert [x["prNumber"] for x in r.json()["requests"]] == ["PR-260101"]


async def test_erp_down_is_reported_not_guessed(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "MOCK_ERP_URL", "http://127.0.0.1:1")
    r = await client.get("/api/procurement/requests/PR-260101", headers=auth)
    assert r.status_code == 502
    assert r.json()["errorCode"] == "ERP_UNAVAILABLE"
