"""The directory is not browsable: a caller sees exactly one employee,
and there is no route that takes an employee id."""

from tests.conftest import OTHER_EMAIL, login


async def test_me_is_the_caller(client, auth):
    r = await client.get("/api/employees/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["employeeId"] == "E1001"


async def test_another_caller_sees_only_themselves(client):
    pair = await login(client, OTHER_EMAIL)
    client.cookies.clear()
    r = await client.get(
        "/api/employees/me", headers={"Authorization": f"Bearer {pair['accessToken']}"}
    )
    assert r.json()["employeeId"] == "E1002"


async def test_no_route_takes_an_employee_id(client, auth):
    for path in ("/api/employees/E1002", "/api/employees", "/api/employees/"):
        r = await client.get(path, headers=auth)
        assert r.status_code in (404, 405, 307), path
        if r.status_code == 307:
            r = await client.get(r.headers["location"], headers=auth)
            assert r.status_code in (404, 405)
