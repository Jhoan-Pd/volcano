"""Reentrenamiento en segundo plano y su estado.

En el plan gratis de Render (0,1 CPU) entrenar los 4 modelos tarda minutos: la petición HTTP
responde de inmediato (202) y el panel consulta el estado cada pocos segundos.

Antes el estado vivía en variables globales del módulo de predicción modificadas con `global`.
Ahora `ControlEntrenamiento` encapsula ese estado compartido entre hilos (un candado protege
cada cambio) y expone una interfaz pequeña: iniciar, terminar, fallar y consultar.
Este módulo orquesta predicción + alertas, así `prediccion_service` ya no necesita importar
`alerta_service` dentro de una función para evitar un import circular.
"""
import logging
import threading
from datetime import datetime, timezone

from app.core.errors import ConflictoError
from app.db.session import SessionLocal
from app.schemas.modelo import EstadoEntrenamiento
from app.services.alerta_service import AlertaService
from app.services.prediccion_service import PrediccionService

logger = logging.getLogger("predictor.entrenamiento")


class ControlEntrenamiento:
    """Estado del último reentrenamiento; garantiza que no corran dos a la vez."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._estado = EstadoEntrenamiento(en_curso=False)

    def estado(self) -> EstadoEntrenamiento:
        with self._lock:
            return self._estado.model_copy()

    def iniciar(self) -> EstadoEntrenamiento:
        with self._lock:
            if self._estado.en_curso:
                raise ConflictoError("Ya hay un entrenamiento en curso. Espera a que termine.")
            self._estado = EstadoEntrenamiento(en_curso=True, inicio=datetime.now(timezone.utc), mensaje="Entrenando…")
            return self._estado.model_copy()

    def terminar(self, mensaje: str, errores: list[str] | None = None) -> None:
        with self._lock:
            self._estado = EstadoEntrenamiento(en_curso=False, inicio=self._estado.inicio,
                                               fin=datetime.now(timezone.utc), mensaje=mensaje, errores=errores or [])

    def reiniciar(self) -> None:
        """Vuelve al estado inicial (útil en pruebas)."""
        with self._lock:
            self._estado = EstadoEntrenamiento(en_curso=False)


control = ControlEntrenamiento()


def reentrenar(enfermedad_id: int | None = None) -> None:
    """Entrena, regenera predicciones y recalcula alertas. Pensado para correr en segundo plano:
    nunca lanza excepciones; el resultado (o el error) queda en `control.estado()`."""
    try:
        with SessionLocal() as db:
            modelos, errores = PrediccionService(db).entrenar(enfermedad_id)
            alertas = AlertaService(db).evaluar()
        control.terminar(f"{len(modelos)} modelo(s) entrenado(s) y predicciones actualizadas; "
                         f"{alertas.activas} alerta(s) activa(s), {alertas.nuevas} nueva(s)", errores)
    except Exception as exc:  # noqa: BLE001 - se informa al panel en lugar de perderse en el log
        logger.exception("Falló el reentrenamiento")
        control.terminar("El entrenamiento falló", [str(exc)])


def lanzar_en_hilo(enfermedad_id: int | None = None, nombre: str = "reentrenamiento") -> EstadoEntrenamiento:
    """Marca el inicio (falla con 409 si ya hay uno) y entrena en un hilo aparte."""
    estado = control.iniciar()
    threading.Thread(target=reentrenar, args=(enfermedad_id,), daemon=True, name=nombre).start()
    return estado
