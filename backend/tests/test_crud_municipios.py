NUEVO = {
    "codigo_divipola": "52835", "nombre": "Tumaco", "latitud": 1.8067, "longitud": -78.7647,
    "altitud_m": 2, "poblacion": 260000, "distancia_crater_km": 230,
}


def test_listado_publico(client):
    r = client.get("/api/v1/municipios")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] >= 6
    assert any(m["nombre"] == "Pasto" and m["codigo_divipola"] == "52001" for m in cuerpo["items"])


def test_la_florida_tiene_divipola_corregido(client):
    nombres = {m["nombre"]: m["codigo_divipola"] for m in client.get("/api/v1/municipios").json()["items"]}
    assert nombres["La Florida"] == "52381"


def test_crud_completo_como_admin(client, admin_headers):
    r = client.post("/api/v1/municipios", json=NUEVO, headers=admin_headers)
    assert r.status_code == 201, r.text
    mid = r.json()["id"]

    assert client.get(f"/api/v1/municipios/{mid}").json()["nombre"] == "Tumaco"

    r = client.patch(f"/api/v1/municipios/{mid}", json={"poblacion": 270000}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["poblacion"] == 270000

    # duplicado de código DIVIPOLA -> 409
    r = client.post("/api/v1/municipios", json=NUEVO, headers=admin_headers)
    assert r.status_code == 409

    assert client.delete(f"/api/v1/municipios/{mid}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/v1/municipios/{mid}").status_code == 404


def test_validaciones(client, admin_headers):
    malo = {**NUEVO, "codigo_divipola": "123", "latitud": 40}
    r = client.post("/api/v1/municipios", json=malo, headers=admin_headers)
    assert r.status_code == 422
    campos = {d["campo"] for d in r.json()["error"]["detalles"]}
    assert {"codigo_divipola", "latitud"} <= campos


def test_escritura_requiere_admin(client, ciudadano_headers):
    assert client.post("/api/v1/municipios", json=NUEVO).status_code == 401
    assert client.post("/api/v1/municipios", json=NUEVO, headers=ciudadano_headers).status_code == 403


def test_evento_ceniza_exige_municipio(client, admin_headers):
    r = client.post("/api/v1/eventos-volcanicos", headers=admin_headers, json={
        "tipo": "CAIDA_CENIZA", "nivel_actividad": "AMARILLO", "fecha_inicio": "2026-10-01"})
    assert r.status_code == 422
    r = client.post("/api/v1/eventos-volcanicos", headers=admin_headers, json={
        "tipo": "CAIDA_CENIZA", "nivel_actividad": "AMARILLO", "fecha_inicio": "2026-10-01",
        "municipio_id": 1, "intensidad_ceniza": 2})
    assert r.status_code == 201, r.text
