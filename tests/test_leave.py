"""Balances and requests are the caller's own; a submission validates,
writes, and raises pending_days. The write test puts the rows back."""

from datetime import date, timedelta

import pytest
from sqlalchemy import delete, select

from src.app.database.connections import get_session_factory
from src.app.database.enums import LeaveType
from src.app.database.models import LeaveBalance, LeaveRequest
from tests.conftest import ACTIVE_EMPLOYEE, OTHER_EMAIL, login

FAR = date(2030, 6, 10)


@pytest.fixture
async def restore_leave():
    """Snapshot E1001's balance rows; afterwards delete any request created
    by the test and put the balances back."""
    async with get_session_factory()() as s:
        rows = (
            (
                await s.execute(
                    select(LeaveBalance).where(
                        LeaveBalance.employee_id == ACTIVE_EMPLOYEE
                    )
                )
            )
            .scalars()
            .all()
        )
        snapshot = {r.leave_type: r.pending_days for r in rows}
    yield
    async with get_session_factory()() as s:
        async with s.begin():
            await s.execute(
                delete(LeaveRequest).where(
                    LeaveRequest.employee_id == ACTIVE_EMPLOYEE,
                    LeaveRequest.start_date >= FAR,
                )
            )
            rows = (
                (
                    await s.execute(
                        select(LeaveBalance).where(
                            LeaveBalance.employee_id == ACTIVE_EMPLOYEE
                        )
                    )
                )
                .scalars()
                .all()
            )
            for r in rows:
                r.pending_days = snapshot[r.leave_type]


async def test_balances_are_the_callers(client, auth):
    r = await client.get("/api/leave/balances", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["employeeId"] == "E1001"
    by_type = {b["leaveType"]: b for b in body["balances"]}
    assert set(by_type) == {"annual", "sick"}
    a = by_type["annual"]
    assert float(a["availableDays"]) == float(a["entitledDays"]) - float(
        a["usedDays"]
    ) - float(a["pendingDays"])


async def test_requests_list_only_own(client, auth):
    r = await client.get("/api/leave/requests", headers=auth)
    assert r.status_code == 200
    assert {x["employeeId"] for x in r.json()["requests"]} <= {"E1001"}


async def test_someone_elses_request_is_404(client, auth):
    # LR-9002 belongs to E1002 in the pack.
    r = await client.get("/api/leave/requests/LR-9002", headers=auth)
    assert r.status_code == 404
    assert r.json()["errorCode"] == "LEAVE_REQUEST_NOT_FOUND"
    pair = await login(client, OTHER_EMAIL)
    client.cookies.clear()
    r = await client.get(
        "/api/leave/requests/LR-9002",
        headers={"Authorization": f"Bearer {pair['accessToken']}"},
    )
    assert r.status_code == 200
    assert r.json()["employeeId"] == "E1002"


async def test_submit_raises_pending_and_lowers_available(client, auth, restore_leave):
    before = {
        b["leaveType"]: b
        for b in (await client.get("/api/leave/balances", headers=auth)).json()[
            "balances"
        ]
    }
    body = {
        "leaveType": "annual",
        "startDate": FAR.isoformat(),
        "endDate": (FAR + timedelta(days=1)).isoformat(),
        "reasonCategory": "travel",
    }
    r = await client.post("/api/leave/requests", json=body, headers=auth)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["days"] == 2 and created["status"] == "pending"
    assert created["requestId"].startswith("LR-")
    assert created["confirmationRecorded"] is True
    after = {
        b["leaveType"]: b
        for b in (await client.get("/api/leave/balances", headers=auth)).json()[
            "balances"
        ]
    }
    assert (
        float(after["annual"]["pendingDays"])
        == float(before["annual"]["pendingDays"]) + 2
    )
    assert (
        float(after["annual"]["availableDays"])
        == float(before["annual"]["availableDays"]) - 2
    )
    assert after["sick"] == before["sick"]
    got = await client.get(f"/api/leave/requests/{created['requestId']}", headers=auth)
    assert got.status_code == 200


async def test_overlap_is_refused(client, auth, restore_leave):
    body = {
        "leaveType": "annual",
        "startDate": FAR.isoformat(),
        "endDate": FAR.isoformat(),
    }
    assert (
        await client.post("/api/leave/requests", json=body, headers=auth)
    ).status_code == 201
    r = await client.post("/api/leave/requests", json=body, headers=auth)
    assert r.status_code == 409
    assert r.json()["errorCode"] == "OVERLAPPING_REQUEST"


async def test_insufficient_balance_is_refused(client, auth):
    body = {
        "leaveType": "sick",
        "startDate": FAR.isoformat(),
        "endDate": (FAR + timedelta(days=40)).isoformat(),
    }
    r = await client.post("/api/leave/requests", json=body, headers=auth)
    assert r.status_code == 422
    assert r.json()["errorCode"] == "INSUFFICIENT_BALANCE"


async def test_bad_dates_are_422(client, auth):
    body = {
        "leaveType": "annual",
        "startDate": FAR.isoformat(),
        "endDate": (FAR - timedelta(days=1)).isoformat(),
    }
    r = await client.post("/api/leave/requests", json=body, headers=auth)
    assert r.status_code == 422
    assert r.json()["errorCode"] == "VALIDATION_ERROR"


async def test_request_id_sequence_continues_the_pack(client, auth, restore_leave):
    body = {
        "leaveType": "annual",
        "startDate": FAR.isoformat(),
        "endDate": FAR.isoformat(),
    }
    r = await client.post("/api/leave/requests", json=body, headers=auth)
    assert int(r.json()["requestId"].split("-")[1]) > 9120
    assert LeaveType.annual.value == "annual"
