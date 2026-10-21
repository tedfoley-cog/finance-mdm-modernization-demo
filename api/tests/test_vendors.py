from api.app.validators import normalize_tax_id


def test_normalize_tax_id_vectors():
    assert normalize_tax_id("DE 732 532 297") == "DE732532297"
    assert normalize_tax_id("23-9775973") == "239775973"
    assert normalize_tax_id("15fbdpf4918g1z6") == "15FBDPF4918G1Z6"
    assert normalize_tax_id("12.345.678/0001-90") == "12345678/000190"  # slash survives; see docs/tech-debt.md
    assert normalize_tax_id("   ") is None
    assert normalize_tax_id(None) is None


def test_search_by_formatted_tax_id_hits_normalized_column(client):
    r = client.get("/api/vendors", params={"q": "DE 732 532 297"})
    assert r.status_code == 200
    ids = {v["vendor_id"] for v in r.json()}
    assert {"V1000449", "V1001013"} <= ids


def test_duplicate_groups_share_normalized_tax_id(client):
    r = client.get("/api/vendors/duplicates")
    assert r.status_code == 200
    groups = r.json()
    assert len(groups) >= 4
    for group in groups:
        assert len({v["tax_id_normalized"] for v in group}) == 1
        assert len({v["vendor_id"] for v in group}) == len(group)


def test_publish_writes_jsonl_locally(client):
    r = client.post("/api/publish", json={"entity_type": "vendor", "requested_by": "s.okafor"})
    assert r.status_code == 201
    run = r.json()
    assert run["status"] == "WRITTEN_LOCAL"
    assert run["s3_key"].startswith("golden/vendor/dt=")
    assert run["record_count"] >= 30
    summary = client.get("/api/publish/summary").json()
    assert summary["last_publish"]["id"] == run["id"]
