NEW = {
    "divipola_code": "52835", "name": "Tumaco", "latitude": 1.8067, "longitude": -78.7647,
    "altitude_m": 2, "population": 260000, "crater_distance_km": 230,
}


def test_public_listing(client):
    r = client.get("/api/v1/municipalities")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 6
    assert any(m["name"] == "Pasto" and m["divipola_code"] == "52001" for m in body["items"])


def test_la_florida_has_the_corrected_divipola(client):
    codes = {m["name"]: m["divipola_code"] for m in client.get("/api/v1/municipalities").json()["items"]}
    assert codes["La Florida"] == "52381"


def test_full_crud_as_admin(client, admin_headers):
    r = client.post("/api/v1/municipalities", json=NEW, headers=admin_headers)
    assert r.status_code == 201, r.text
    mid = r.json()["id"]

    assert client.get(f"/api/v1/municipalities/{mid}").json()["name"] == "Tumaco"

    r = client.patch(f"/api/v1/municipalities/{mid}", json={"population": 270000}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["population"] == 270000

    # duplicated DIVIPOLA code -> 409
    assert client.post("/api/v1/municipalities", json=NEW, headers=admin_headers).status_code == 409

    assert client.delete(f"/api/v1/municipalities/{mid}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/v1/municipalities/{mid}").status_code == 404


def test_validation_errors_name_the_fields(client, admin_headers):
    bad = {**NEW, "divipola_code": "123", "latitude": 40}
    r = client.post("/api/v1/municipalities", json=bad, headers=admin_headers)
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"divipola_code", "latitude"} <= fields


def test_writing_requires_admin(client, citizen_headers):
    assert client.post("/api/v1/municipalities", json=NEW).status_code == 401
    assert client.post("/api/v1/municipalities", json=NEW, headers=citizen_headers).status_code == 403


def test_ash_fall_requires_a_municipality(client, admin_headers):
    r = client.post("/api/v1/volcanic-events", headers=admin_headers, json={
        "event_type": "ASH_FALL", "activity_level": "YELLOW", "start_date": "2026-10-01"})
    assert r.status_code == 422
    r = client.post("/api/v1/volcanic-events", headers=admin_headers, json={
        "event_type": "ASH_FALL", "activity_level": "YELLOW", "start_date": "2026-10-01",
        "municipality_id": 1, "ash_intensity": 2})
    assert r.status_code == 201, r.text
