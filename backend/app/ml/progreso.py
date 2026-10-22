"""Avance de un entrenamiento, para mostrarlo en vivo.

El entrenador y el servicio de predicción reciben una función `progreso(evento)` opcional
(patrón Observer en su forma más simple: un callback). Sin ella todo funciona igual que antes;
con ella, el motor gRPC reenvía cada evento al navegador como un mensaje de un stream.
"""
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class Etapa(StrEnum):
    INICIO = "INICIO"
    DATASET = "DATASET"
    CANDIDATO = "CANDIDATO"
    MODELO_LISTO = "MODELO_LISTO"
    PREDICCIONES = "PREDICCIONES"
    ALERTAS = "ALERTAS"
    AVISO = "AVISO"
    FIN = "FIN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class EventoProgreso:
    etapa: Etapa
    mensaje: str
    avance: float  # 0 a 1
    enfermedad: str = ""
    algoritmo: str = ""
    mae: float | None = None
    mae_base: float | None = None


Progreso = Callable[[EventoProgreso], None]


def sin_progreso(_: EventoProgreso) -> None:
    """Callback nulo (patrón Null Object): evita preguntar `if progreso is not None` en cada paso."""


def escalar(progreso: Progreso, inicio: float, fin: float, **extra) -> Progreso:
    """Convierte el avance 0-1 de una sub-tarea al tramo [inicio, fin] de la tarea completa."""
    def interno(e: EventoProgreso) -> None:
        datos = {**e.__dict__, **{k: v for k, v in extra.items() if not getattr(e, k)}}
        datos["avance"] = inicio + (fin - inicio) * e.avance
        progreso(EventoProgreso(**datos))
    return interno
