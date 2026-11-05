"""Search returns citations in both languages; the unanswerable flag
travels with the hit so the assistant can refuse on it."""


async def test_documents(client, auth):
    r = await client.get("/api/policies", headers=auth)
    assert r.status_code == 200
    docs = {d["documentId"]: d["clauses"] for d in r.json()}
    assert docs == {"hr": 24, "procurement": 24, "information_security": 12}


async def test_english_search_cites_clauses(client, auth):
    r = await client.post(
        "/api/policies/search",
        json={"query": "emergency leave evidence", "language": "en"},
        headers=auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in ("keyword", "hybrid")
    assert body["hits"], "expected at least one hit"
    top = body["hits"][0]["citation"]
    assert top["language"] == "en" and top["documentId"] == "hr"
    assert top["theme"] == "Emergency leave"
    assert top["policyId"].startswith("POL-") and top["section"]


async def test_arabic_search_cites_arabic_clauses(client, auth):
    r = await client.post(
        "/api/policies/search",
        json={"query": "ضوابط Annual leave", "language": "ar"},
        headers=auth,
    )
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert hits and all(h["citation"]["language"] == "ar" for h in hits)
    assert hits[0]["citation"]["theme"] == "Annual leave"


async def test_unanswerable_flag_is_carried(client, auth):
    r = await client.post(
        "/api/policies/search",
        json={"query": "Request justification", "language": "ar", "limit": 20},
        headers=auth,
    )
    flags = {
        h["citation"]["policyId"]: h["citation"]["answerable"] for h in r.json()["hits"]
    }
    assert flags.get("POL-018") is False
    assert flags.get("POL-008") is True


async def test_no_match_is_empty_not_invented(client, auth):
    r = await client.post(
        "/api/policies/search", json={"query": "parking permit bicycle"}, headers=auth
    )
    assert r.status_code == 200
    assert r.json()["hits"] == []


async def test_search_requires_auth(client):
    client.cookies.clear()
    r = await client.post("/api/policies/search", json={"query": "annual leave"})
    assert r.status_code == 401


async def test_paraphrase_is_found_when_embeddings_exist(client, auth):
    r = await client.post(
        "/api/policies/search",
        json={
            "query": "Do I need to show proof if I take urgent time off?",
            "language": "en",
        },
        headers=auth,
    )
    body = r.json()
    if body["mode"] == "keyword":
        return  # no embedding deployment in this environment
    assert body["hits"] and body["hits"][0]["citation"]["theme"] == "Emergency leave"


async def test_arabic_paraphrase_crosses_languages(client, auth):
    r = await client.post(
        "/api/policies/search",
        json={"query": "هل أحتاج إلى تقديم دليل عند طلب إجازة طارئة؟"},
        headers=auth,
    )
    body = r.json()
    if body["mode"] == "keyword":
        return
    assert body["hits"] and body["hits"][0]["citation"]["theme"] == "Emergency leave"
