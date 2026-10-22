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
os.environ["ENTRENAR_AL_INICIO"] = "false"

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


@pytest.fixture
def farmacia_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'farmacia@demo.co', 'Demo12345')}"}


# ── Motor gRPC ───────────────────────────────────────────────────────────────
TOKEN_MOTOR = "token-motor-pruebas"


@pytest.fixture(scope="session")
def ira_entrenada():
    """IRA con 3,4 años de casos sintéticos en 2 municipios y un modelo entrenado.
    Se usa IRA para no interferir con las pruebas del modelo (EDA) ni de alertas (DENGUE)."""
    import math

    import numpy as np

    from app.core.epi import iterar_semanas
    from app.ml.entrenador import Entrenador
    from app.models import CasoOficial, Enfermedad, Municipio
    from app.services.prediccion_service import PrediccionService

    rng = np.random.default_rng(1)
    with SessionLocal() as db:
        ira = db.query(Enfermedad).filter_by(codigo="IRA").one()
        # test_importacion ya pudo cargar algunas semanas sueltas de IRA (2019): se completa por municipio
        recientes = db.query(CasoOficial).filter(CasoOficial.enfermedad_id == ira.id, CasoOficial.anio >= 2023)
        if recientes.count() == 0:
            for codigo, base in (("52001", 90), ("52207", 6)):
                m = db.query(Municipio).filter_by(codigo_divipola=codigo).one()
                for i, (a, s) in enumerate(iterar_semanas((2023, 1), (2026, 20))):
                    lam = base * (1 + 0.5 * math.cos(2 * math.pi * s / 52)) * (1 + 0.001 * i)
                    db.add(CasoOficial(municipio_id=m.id, enfermedad_id=ira.id, anio=a, semana_epi=s,
                                       casos=int(rng.poisson(lam)), es_simulado=True))
            db.commit()
        servicio = PrediccionService(db, entrenador=Entrenador(semanas_prueba=26, repeticiones_permutacion=1))
        _, errores = servicio.entrenar(ira.id)
        assert not errores, errores
        return ira.id


@pytest.fixture(scope="session")
def motor_grpc():
    """Servidor gRPC real en un puerto libre, con la BD de pruebas y el difusor muy frecuente."""
    from app.motor.difusor import DifusorAlertas
    from app.motor.servicio import MotorPrediccionServicer
    from app.motor.servidor import crear_servidor

    servicer = MotorPrediccionServicer(difusor=DifusorAlertas(SessionLocal, intervalo_s=0.2))
    motor = crear_servidor("127.0.0.1:0", servicer=servicer, token=TOKEN_MOTOR, hilos=8).iniciar()
    yield motor
    motor.detener(0)


@pytest.fixture
def stub(motor_grpc):
    import grpc

    from app.motor.protos import prediccion_pb2_grpc

    canal = grpc.insecure_channel(f"127.0.0.1:{motor_grpc.puerto}")
    yield prediccion_pb2_grpc.MotorPrediccionStub(canal)
    canal.close()
