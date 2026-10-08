"""Configuración de pruebas: BD SQLite temporal, independiente de la de desarrollo."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}"
os.environ["JWT_SECRET"] = "secreto-de-pruebas-con-mas-de-32-bytes-ok"
os.environ["CRON_SECRET"] = "cron-de-pruebas"
os.environ["ADMIN_EMAIL"] = "admin@test.co"
os.environ["ADMIN_PASSWORD"] = "Admin1234"
os.environ["DEMO_PASSWORD"] = "Demo12345"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed.__main__ import seed_catalogos, seed_roles_usuarios  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _bd():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_catalogos(db)
        seed_roles_usuarios(db)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    return TestClient(app)


def _token(client, email, password):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def admin_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'admin@test.co', 'Admin1234')}"}


@pytest.fixture
def ciudadano_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'ciudadano@demo.co', 'Demo12345')}"}
