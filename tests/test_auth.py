def test_login_returns_jwt_and_role(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin@test.co", "password": "Admin1234"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "ADMIN"
    assert body["access_token"].count(".") == 2  # JWT format header.payload.signature


def test_login_with_wrong_password_is_401(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin@test.co", "password": "other-pass1"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_requires_a_token(client, admin_headers):
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.get("/api/v1/auth/me", headers=admin_headers)
    assert r.status_code == 200 and r.json()["email"] == "admin@test.co"


def test_invalid_token_is_401(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_citizen_signup_stores_a_hashed_password(client, db):
    from sqlalchemy import select

    from volcano.models import User

    signup = {"name": "Ana Pérez", "email": "Ana@Correo.co", "password": "clave1234"}
    r = client.post("/api/v1/auth/signup", json=signup)
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "CITIZEN"
    u = db.scalar(select(User).where(User.email == "ana@correo.co"))
    assert u is not None and u.password_hash.startswith("$2") and "clave1234" not in u.password_hash
    # duplicated e-mail
    r2 = client.post("/api/v1/auth/signup", json={"name": "Ana", "email": "ana@correo.co", "password": "clave1234"})
    assert r2.status_code == 409


def test_signup_rejects_a_weak_password(client):
    r = client.post("/api/v1/auth/signup", json={"name": "Luis", "email": "luis@correo.co", "password": "onlyLetters"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "VALIDATION"
    assert body["details"][0]["field"] == "password"


def test_citizen_cannot_use_admin_endpoints(client, citizen_headers):
    r = client.get("/api/v1/users", headers=citizen_headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PERMISSION_DENIED"


def test_cron_requires_its_secret(client):
    assert client.post("/api/v1/jobs/daily-update").status_code == 401
    assert client.post("/api/v1/jobs/daily-update", headers={"X-Cron-Secret": "wrong"}).status_code == 401
