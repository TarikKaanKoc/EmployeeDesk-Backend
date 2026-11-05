from tests.conftest import ACTIVE_EMAIL, DEV_PASSWORD, INACTIVE_EMAIL, login


async def test_login_sets_cookies_and_returns_pair(client):
    r = await client.post(
        "/api/auth/login", json={"email": ACTIVE_EMAIL, "password": DEV_PASSWORD}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["accessToken"] and body["refreshToken"]
    assert "access_token" in r.cookies and "refresh_token" in r.cookies
    client.cookies.clear()


async def test_wrong_password_and_unknown_email_look_the_same(client):
    a = await client.post(
        "/api/auth/login", json={"email": ACTIVE_EMAIL, "password": "wrong"}
    )
    b = await client.post(
        "/api/auth/login", json={"email": "nobody@example.test", "password": "wrong"}
    )
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    assert a.json()["errorCode"] == "INVALID_CREDENTIALS"


async def test_inactive_employee_cannot_sign_in(client):
    r = await client.post(
        "/api/auth/login", json={"email": INACTIVE_EMAIL, "password": DEV_PASSWORD}
    )
    assert r.status_code == 401
    assert r.json()["errorCode"] == "ACCOUNT_INACTIVE"


async def test_me_with_bearer(client, auth):
    r = await client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["employeeId"] == "E1001"


async def test_no_token_is_401(client):
    client.cookies.clear()
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


async def test_refresh_rotates_and_refuses_reuse(client):
    pair = await login(client)
    client.cookies.clear()
    first = await client.post(
        "/api/auth/refresh", json={"refreshToken": pair["refreshToken"]}
    )
    assert first.status_code == 200
    assert first.json()["refreshToken"] != pair["refreshToken"]
    client.cookies.clear()
    again = await client.post(
        "/api/auth/refresh", json={"refreshToken": pair["refreshToken"]}
    )
    assert again.status_code == 401
    assert again.json()["errorCode"] == "REFRESH_REUSED"


async def test_logout_revokes_access_token(client):
    pair = await login(client)
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {pair['accessToken']}"}
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 200
    out = await client.post("/api/auth/logout", headers=headers)
    assert out.status_code == 204
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401


async def test_garbage_token_is_401(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
