"""Actualización diaria de datos (la dispara GitHub Actions con un cron).

Pasos, cada uno aislado: si una fuente externa falla, se registra el error y se sigue con
las demás (una caída de Google Trends no debe impedir actualizar el clima ni las alertas).

    1. Clima: últimos 14 días observados + pronóstico de 16 días (Open-Meteo).
    2. Búsquedas: Google Trends (respeta la caché en BD; respaldo CSV).
    3. Casos oficiales: SIVIGILA en datos.gov.co (solo los lunes o si se pide; el dataset
       se publica con meses de rezago y es pesado de descargar).
    4. Modelo: los lunes (o si no hay modelos) se reentrena en segundo plano; los demás días
       solo se regeneran las predicciones con los modelos vigentes.
    5. Alertas: se recalculan y se envían por correo las nuevas.
"""
import logging
import time
from datetime import date, datetime, timezone
from typing import Callable, Literal

from sqlalchemy import func, select

from app.models import ModeloEntrenado
from app.services.alerta_service import AlertaService
from app.services.clima_service import ClimaService
from app.services.entrenamiento import lanzar_en_hilo
from app.services.prediccion_service import PrediccionService
from app.services.sivigila_service import SivigilaService
from app.services.tendencia_service import TendenciaService

logger = logging.getLogger("predictor.cron")

Modo = Literal["auto", "si", "no"]


def _paso(nombre: str, fn: Callable[[], object]) -> dict:
    t0 = time.perf_counter()
    try:
        resultado = fn()
        if hasattr(resultado, "model_dump"):
            resultado = resultado.model_dump()
        return {"paso": nombre, "ok": True, "segundos": round(time.perf_counter() - t0, 1), "resultado": resultado}
    except Exception as exc:  # noqa: BLE001 - un paso fallido no detiene la actualización
        logger.exception("Paso %s falló", nombre)
        return {"paso": nombre, "ok": False, "segundos": round(time.perf_counter() - t0, 1), "error": str(exc)}


class ActualizacionService:
    def __init__(self, db, hoy: date | None = None):
        self.db = db
        self.hoy = hoy or date.today()

    def _toca(self, modo: Modo) -> bool:
        return modo == "si" or (modo == "auto" and self.hoy.weekday() == 0)  # lunes

    def ejecutar(self, sivigila: Modo = "auto", reentrenar: Modo = "auto") -> dict:
        inicio = datetime.now(timezone.utc)
        pasos = [
            _paso("clima", lambda: ClimaService(self.db).sincronizar(dias_pasados=14)),
            _paso("tendencias", lambda: TendenciaService(self.db).sincronizar()),
        ]
        if self._toca(sivigila):
            pasos.append(_paso("sivigila", lambda: SivigilaService(self.db).sincronizar()))

        sin_modelos = (self.db.scalar(select(func.count()).select_from(ModeloEntrenado)) or 0) == 0
        en_segundo_plano = False
        if self._toca(reentrenar) or (reentrenar != "no" and sin_modelos):
            def lanzar():
                lanzar_en_hilo(nombre="reentrenamiento-cron")
                return {"mensaje": "Reentrenamiento iniciado en segundo plano; al terminar se evalúan las alertas"}
            paso = _paso("reentrenar", lanzar)
            if not paso["ok"] and "en curso" in paso.get("error", ""):
                paso["ok"] = True  # ya había uno corriendo: no es un error
            en_segundo_plano = paso["ok"]
            pasos.append(paso)
        else:
            pasos.append(_paso("predicciones", lambda: {"predicciones": PrediccionService(self.db).predecir()}))

        if not en_segundo_plano:
            pasos.append(_paso("alertas", lambda: AlertaService(self.db).evaluar()))

        return {
            "inicio": inicio.isoformat(),
            "fin": datetime.now(timezone.utc).isoformat(),
            "ok": all(p["ok"] for p in pasos),
            "pasos": pasos,
        }
