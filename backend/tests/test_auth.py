def test_login_correcto_devuelve_jwt_y_rol(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin@test.co", "password": "Admin1234"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["usuario"]["rol"] == "ADMIN"
    assert cuerpo["access_token"].count(".") == 2  # formato JWT header.payload.firma


def test_login_con_clave_errada_da_401(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin@test.co", "password": "otra-clave1"})
    assert r.status_code == 401
    assert r.json()["error"]["codigo"] == "NO_AUTENTICADO"


def test_me_requiere_token(client, admin_headers):
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.get("/api/v1/auth/me", headers=admin_headers)
    assert r.status_code == 200 and r.json()["email"] == "admin@test.co"


def test_token_invalido_da_401(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer no.es.valido"})
    assert r.status_code == 401


def test_registro_ciudadano_y_contrasena_hasheada(client, db):
    from sqlalchemy import select

    from app.models import Usuario

    r = client.post("/api/v1/auth/registro",
                    json={"nombre": "Ana Pérez", "email": "Ana@Correo.co", "password": "clave1234"})
    assert r.status_code == 201, r.text
    assert r.json()["rol"] == "CIUDADANO"
    u = db.scalar(select(Usuario).where(Usuario.email == "ana@correo.co"))
    assert u is not None and u.password_hash.startswith("$2") and "clave1234" not in u.password_hash
    # correo duplicado
    r2 = client.post("/api/v1/auth/registro", json={"nombre": "Ana", "email": "ana@correo.co", "password": "clave1234"})
    assert r2.status_code == 409


def test_registro_valida_contrasena_debil(client):
    r = client.post("/api/v1/auth/registro",
                    json={"nombre": "Luis", "email": "luis@correo.co", "password": "soloLetras"})
    assert r.status_code == 422
    assert r.json()["error"]["codigo"] == "VALIDACION"


def test_ciudadano_no_puede_usar_endpoints_admin(client, ciudadano_headers):
    r = client.get("/api/v1/usuarios", headers=ciudadano_headers)
    assert r.status_code == 403
    assert r.json()["error"]["codigo"] == "PERMISO_DENEGADO"


def test_cron_requiere_secreto(client):
    assert client.post("/api/v1/jobs/actualizar-datos").status_code == 401
    assert client.post("/api/v1/jobs/actualizar-datos", headers={"X-Cron-Secret": "malo"}).status_code == 401
