"""Verifica que las migraciones de Alembic crean las 13 tablas en una BD vacía."""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

TABLAS = {
    "usuarios", "roles", "municipios", "enfermedades", "registros_clima", "tendencias_busqueda", "farmacias",
    "reportes_farmacia", "casos_oficiales", "eventos_volcanicos", "modelos_entrenados", "predicciones", "alertas",
}


def test_alembic_upgrade_head(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    env = {**os.environ, "DATABASE_URL": url}
    raiz = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=raiz, env=env,
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    tablas = set(inspect(create_engine(url)).get_table_names())
    assert tablas >= TABLAS


def test_modelos_y_migraciones_sincronizados(tmp_path: Path):
    """`alembic check` falla si un modelo cambió y nadie generó la migración correspondiente."""
    url = f"sqlite:///{tmp_path / 'chk.db'}"
    env = {**os.environ, "DATABASE_URL": url}
    raiz = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=raiz, env=env, check=True,
                   capture_output=True)
    r = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=raiz, env=env, capture_output=True,
                       text=True, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
