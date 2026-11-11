"""Test set-up: a temporary SQLite database, independent of the development one."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}"
os.environ["JWT_SECRET"] = "test-secret-with-more-than-32-bytes-ok"
os.environ["CRON_SECRET"] = "test-cron"
os.environ["ADMIN_EMAIL"] = "admin@test.co"
os.environ["ADMIN_PASSWORD"] = "Admin1234"
os.environ["DEMO_PASSWORD"] = "Demo12345"
os.environ["TRAIN_ON_STARTUP"] = "false"
os.environ["REALTIME_INTERNAL_URL"] = "http://127.0.0.1:9"  # nothing listens: events are dropped quietly

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from volcano.db.session import SessionLocal, engine  # noqa: E402
from volcano.gateway.app import app  # noqa: E402
from volcano.models import Base  # noqa: E402
from volcano.seed.__main__ import seed_catalogs, seed_roles_and_users  # noqa: E402

ENGINE_TOKEN = "test-engine-token"


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_catalogs(db)
        seed_roles_and_users(db)
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
def citizen_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'ciudadano@demo.co', 'Demo12345')}"}


@pytest.fixture
def pharmacy_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'farmacia@demo.co', 'Demo12345')}"}


# ── gRPC engine ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def trained_ira():
    """IRA with 3.4 years of synthetic cases in 2 municipalities and a trained model.
    IRA is used so it does not interfere with the model tests (EDA) or the alert tests (DENGUE)."""
    import math

    import numpy as np

    from volcano.ml.trainer import Trainer
    from volcano.models import Disease, Municipality, OfficialCase
    from volcano.services.forecasting import ForecastingService
    from volcano.shared.epi import iter_weeks

    rng = np.random.default_rng(1)
    with SessionLocal() as db:
        ira = db.query(Disease).filter_by(code="IRA").one()
        # test_csv_import may already have loaded a few loose IRA weeks (2019): fill per municipality
        recent = db.query(OfficialCase).filter(OfficialCase.disease_id == ira.id, OfficialCase.year >= 2023)
        if recent.count() == 0:
            for code, base in (("52001", 90), ("52207", 6)):
                m = db.query(Municipality).filter_by(divipola_code=code).one()
                for i, (y, w) in enumerate(iter_weeks((2023, 1), (2026, 20))):
                    lam = base * (1 + 0.5 * math.cos(2 * math.pi * w / 52)) * (1 + 0.001 * i)
                    db.add(OfficialCase(municipality_id=m.id, disease_id=ira.id, year=y, epi_week=w,
                                        cases=int(rng.poisson(lam)), is_simulated=True))
            db.commit()
        service = ForecastingService(db, trainer=Trainer(test_weeks=26, permutation_repeats=1))
        _, errors = service.train(ira.id)
        assert not errors, errors
        return ira.id


@pytest.fixture(scope="session")
def grpc_engine():
    """Real gRPC server on a free port, with the test database and a very frequent alert feed."""
    from volcano.engine.alert_feed import AlertFeed
    from volcano.engine.server import build_server
    from volcano.engine.servicer import PredictionEngineServicer

    servicer = PredictionEngineServicer(feed=AlertFeed(SessionLocal, interval_s=0.2))
    engine_ = build_server("127.0.0.1:0", servicer=servicer, token=ENGINE_TOKEN, threads=8).start()
    yield engine_
    engine_.stop(0)


@pytest.fixture
def stub(grpc_engine):
    import grpc

    from volcano.rpc import engine_pb2_grpc

    channel = grpc.insecure_channel(f"127.0.0.1:{grpc_engine.port}")
    yield engine_pb2_grpc.PredictionEngineStub(channel)
    channel.close()


@pytest.fixture
def engine_client_override(grpc_engine):
    """Points the gateway's engine client at the test server."""
    from volcano.rpc.client import EngineClient, engine_client

    app.dependency_overrides[engine_client] = lambda: EngineClient(f"127.0.0.1:{grpc_engine.port}", ENGINE_TOKEN)
    yield
    app.dependency_overrides.pop(engine_client, None)
