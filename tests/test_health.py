async def test_liveness(client):
    r = await client.get("/api/health/")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


async def test_readiness_reports_dependencies(client):
    r = await client.get("/api/health/ready")
    assert r.status_code == 200
    names = {c["name"]: c["status"] for c in r.json()["checks"]}
    assert names["postgres"] == "ok"
    assert names["redis"] == "ok"


async def test_security_headers(client):
    r = await client.get("/api/health/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
