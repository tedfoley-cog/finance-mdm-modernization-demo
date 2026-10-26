def test_list_cost_centers_filters_by_entity(client):
    r = client.get("/api/cost-centers", params={"entity_code": "DE01"})
    assert r.status_code == 200
    rows = r.json()
    assert rows and all(row["entity_code"] == "DE01" for row in rows)
    assert all(6 <= len(row["cost_center_code"]) <= 10 for row in rows)


def test_children_of_division_hq(client):
    r = client.get("/api/cost-centers/US01/200000/children")
    assert r.status_code == 200
    assert all(row["parent_cost_center_code"] == "200000" for row in r.json())


def test_create_request_accepts_ten_digit_s4_code(client):
    body = {"entity_code": "US01", "cost_center_code": "2000001234", "description": "S/4 pilot", "requested_by": "n.patel"}
    r = client.post("/api/cost-centers", json=body)
    assert r.status_code == 202


def test_create_request_rejects_wrong_width(client):
    for code in ["12345", "12345678901", "20000A1234"]:
        body = {"entity_code": "US01", "cost_center_code": code, "description": "bad", "requested_by": "n.patel"}
        assert client.post("/api/cost-centers", json=body).status_code == 422, code


def test_create_then_approve_cost_center(client):
    body = {
        "entity_code": "US01",
        "cost_center_code": "700010",
        "description": "Autonomy Program",
        "parent_cost_center_code": "600000",
        "requested_by": "n.patel",
    }
    r = client.post("/api/cost-centers", json=body)
    assert r.status_code == 202
    cr = r.json()
    assert cr["status"] == "PENDING"

    same_person = client.post(f"/api/change-requests/{cr['id']}/review", json={"reviewer": "n.patel", "decision": "APPROVE"})
    assert same_person.status_code == 409

    ok = client.post(
        f"/api/change-requests/{cr['id']}/review",
        json={"reviewer": "s.okafor", "decision": "APPROVE", "note": "approved in steward review"},
    )
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED"
    got = client.get("/api/cost-centers/US01/700010")
    assert got.status_code == 200 and got.json()["source_system"] == "MDM"
