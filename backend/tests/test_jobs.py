"""Actualización diaria (cron de GitHub Actions) sin tocar internet."""
from datetime import date

import pytest

from app.services import actualizacion_service as act
from app.services.actualizacion_service import ActualizacionService

CRON = {"X-Cron-Secret": "cron-de-pruebas"}


@pytest.fixture
def fuentes_falsas(monkeypatch):
    """Reemplaza las fuentes externas: clima responde, Trends falla."""
    from app.schemas.clima import ResultadoSincronizacion
    from app.services.clima_service import ClimaService
    from app.services.sivigila_service import SivigilaService
    from app.services.tendencia_service import TendenciaService

    llamadas = []

    def clima(self, dias_pasados=14):
        llamadas.append("clima")
        return ResultadoSincronizacion(municipios=6, registros_guardados=180, errores=[])

    def trends(self, forzar=False, desde=None):
        llamadas.append("tendencias")
        raise RuntimeError("Google respondió 429")

    def sivigila(self, desde_anio=None):
        llamadas.append("sivigila")
        return {"registros_guardados": 0}

    monkeypatch.setattr(ClimaService, "sincronizar", clima)
    monkeypatch.setattr(TendenciaService, "sincronizar", trends)
    monkeypatch.setattr(SivigilaService, "sincronizar", sivigila)
    monkeypatch.setattr(act.threading, "Thread", lambda **kw: type("H", (), {"start": lambda self: llamadas.append("hilo")})())
    return llamadas


def test_cron_requiere_secreto(client):
    assert client.post("/api/v1/jobs/actualizar-datos").status_code == 401
    assert client.post("/api/v1/jobs/actualizar-datos", headers={"X-Cron-Secret": "otro"}).status_code == 401


def test_un_paso_fallido_no_detiene_los_demas(client, fuentes_falsas):
    r = client.post("/api/v1/jobs/actualizar-datos", headers=CRON, params={"sivigila": "no", "reentrenar": "no"})
    assert r.status_code == 200, r.text
    pasos = {p["paso"]: p for p in r.json()["pasos"]}
    assert pasos["clima"]["ok"] and pasos["clima"]["resultado"]["registros_guardados"] == 180
    assert not pasos["tendencias"]["ok"] and "429" in pasos["tendencias"]["error"]
    assert pasos["predicciones"]["ok"] and pasos["alertas"]["ok"]
    assert "sivigila" not in pasos and r.json()["ok"] is False


def test_los_lunes_se_descarga_sivigila_y_se_reentrena(db, fuentes_falsas):
    from app.services import prediccion_service as ps

    lunes = date(2026, 10, 5)
    res = ActualizacionService(db, hoy=lunes).ejecutar()
    pasos = [p["paso"] for p in res["pasos"]]
    assert pasos == ["clima", "tendencias", "sivigila", "reentrenar"]  # las alertas se evalúan al terminar el hilo
    assert "hilo" in fuentes_falsas
    ps._estado = ps.EstadoEntrenamiento(en_curso=False)  # deja libre el candado para otras pruebas

    martes = date(2026, 10, 6)
    pasos = [p["paso"] for p in ActualizacionService(db, hoy=martes).ejecutar(reentrenar="no")["pasos"]]
    assert pasos == ["clima", "tendencias", "predicciones", "alertas"]
