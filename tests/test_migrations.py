"""Alembic migrations: an empty database reaches the English schema, the models match the migrations,
and a database written by the Spanish version keeps its data after 0004."""
import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "users", "roles", "municipalities", "diseases", "weather_records", "search_trends", "pharmacies",
    "pharmacy_reports", "official_cases", "volcanic_events", "trained_models", "predictions", "alerts",
}


def _alembic(url: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url}
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                       check=False)
    if check:
        assert r.returncode == 0, r.stdout + r.stderr
    return r


def test_upgrade_head_creates_the_english_tables(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    _alembic(url, "upgrade", "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert tables >= TABLES
    assert not tables & {"usuarios", "municipios", "alertas"}


def test_models_and_migrations_are_in_sync(tmp_path: Path):
    """`alembic check` fails when a model changed and nobody generated its migration."""
    url = f"sqlite:///{tmp_path / 'chk.db'}"
    _alembic(url, "upgrade", "head")
    _alembic(url, "check")


def test_0004_translates_legacy_data(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    _alembic(url, "upgrade", "0003")
    now = "2026-10-01 00:00:00"
    explanation = {"metodo": "oclusión", "prediccion": 12.5, "umbrales": {"amarillo": 1, "naranja": 2, "rojo": 3},
                   "factores": [{"grupo": "Clima", "contribucion": 1.2, "direccion": "sube", "mensaje": "más lluvia"}]}
    parameters = {"clave": "random_forest", "cuantiles": {"1": [-0.1, 0.1]}, "hiperparametros": {},
                  "metricas": {"resumen": {"promedio_movil": {"mae": 2}}, "por_horizonte": {}, "semanas_prueba": 52},
                  "backtest": [{"municipio_id": 1, "anio": 2026, "semana_epi": 3, "real": 4, "predicho": 3.5}]}
    with create_engine(url).begin() as conn:
        conn.execute(text("INSERT INTO roles (id, nombre, descripcion) VALUES (1, 'CIUDADANO', 'x')"))
        conn.execute(text(f"""INSERT INTO municipios (id, codigo_divipola, nombre, departamento, latitud, longitud,
            poblacion, activo, creado_en, actualizado_en) VALUES (1, '52001', 'Pasto', 'Nariño', 1.2, -77.3,
            450000, 1, '{now}', '{now}')"""))
        conn.execute(text(f"""INSERT INTO enfermedades (id, codigo, nombre, color, umbral_amarillo_pct,
            umbral_naranja_pct, umbral_rojo_pct, activo, categorias_farmacia, creado_en, actualizado_en)
            VALUES (1, 'IRA', 'Gripe', '#2a78d6', 50, 75, 90, 1, 'ANTIGRIPALES,ANTIPIRETICOS', '{now}', '{now}')"""))
        conn.execute(text(f"""INSERT INTO modelos_entrenados (id, enfermedad_id, algoritmo, version,
            fecha_entrenamiento, parametros, artefacto, activo, creado_en, actualizado_en) VALUES (1, 1, 'RF', 'v1',
            '{now}', :p, X'00', 1, '{now}', '{now}')"""), {"p": json.dumps(parameters)})
        conn.execute(text(f"""INSERT INTO predicciones (id, modelo_id, municipio_id, enfermedad_id, anio, semana_epi,
            horizonte, casos_esperados, limite_inferior, limite_superior, nivel_riesgo, explicacion, creado_en,
            actualizado_en) VALUES (1, 1, 1, 1, 2026, 4, 1, 12.5, 10, 15, 'NARANJA', :e, '{now}', '{now}')"""),
                     {"e": json.dumps(explanation)})
        conn.execute(text(f"""INSERT INTO alertas (id, municipio_id, enfermedad_id, anio, semana_epi, nivel_riesgo,
            mensaje, origen, activa, notificada_email, creado_en, actualizado_en) VALUES (1, 1, 1, 2026, 4, 'ROJO',
            'Gripe en Pasto', 'OBSERVADO', 1, 0, '{now}', '{now}')"""))

    _alembic(url, "upgrade", "head")

    with create_engine(url).connect() as conn:
        assert conn.execute(text("SELECT name FROM roles")).scalar_one() == "CITIZEN"
        assert conn.execute(text("SELECT pharmacy_categories FROM diseases")).scalar_one() == "COLD_FLU,ANTIPYRETICS"
        assert conn.execute(text("SELECT risk_level, origin, message FROM alerts")).one() == \
            ("RED", "OBSERVED", "Gripe en Pasto")
        model = conn.execute(text("SELECT parameters, artifact, active FROM trained_models")).one()
        assert model.artifact is None and model.active  # the engine retrains it on start-up
        params = json.loads(model.parameters)
        assert params["key"] == "random_forest" and "moving_average" in params["metrics"]["summary"]
        assert params["backtest"][0] == {"municipality_id": 1, "year": 2026, "epi_week": 3, "observed": 4,
                                         "predicted": 3.5}
        risk_level, raw = conn.execute(text("SELECT risk_level, explanation FROM predictions")).one()
        assert risk_level == "ORANGE"
        exp = json.loads(raw)
        assert exp["thresholds"] == {"yellow": 1, "orange": 2, "red": 3}
        assert exp["factors"][0] == {"group": "weather", "contribution": 1.2, "direction": "up",
                                     "message": "más lluvia"}
