"""Difusión de cambios en las alertas a todos los streams abiertos (publicador/suscriptor).

Las alertas pueden cambiar desde dos procesos: la API (cron diario, botón «Evaluar alertas»)
y el propio motor (al terminar un entrenamiento). Por eso el motor no espera a que le avisen:
un único hilo compara cada `intervalo_s` las alertas activas con la foto anterior y publica
las diferencias (nueva, actualizada, cerrada) en la cola de cada suscriptor.

Un hilo para todos los clientes, no uno por cliente: 30 pestañas abiertas cuestan una consulta
cada 10 s, no 30. El hilo solo consulta mientras haya alguien suscrito.
"""
import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.epi import etiqueta
from app.models import Alerta
from app.motor.conversion import nivel_a_pb
from app.motor.protos import prediccion_pb2 as pb

logger = logging.getLogger("predictor.motor.alertas")
Tipo = pb.EventoAlerta.Tipo


@dataclass(frozen=True)
class FotoAlerta:
    """Lo que el navegador necesita de una alerta; inmutable para comparar fotos con ==."""
    id: int
    municipio_id: int
    municipio: str
    enfermedad_id: int
    enfermedad: str
    semana: str
    nivel: str
    origen: str
    mensaje: str

    def a_pb(self) -> pb.Alerta:
        return pb.Alerta(id=self.id, municipio_id=self.municipio_id, municipio=self.municipio,
                         enfermedad_id=self.enfermedad_id, enfermedad=self.enfermedad, semana=self.semana,
                         nivel=nivel_a_pb(self.nivel), origen=self.origen, mensaje=self.mensaje)


@dataclass(eq=False)
class Suscripcion:
    municipio_id: int | None = None
    cola: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=500))

    def acepta(self, foto: FotoAlerta) -> bool:
        return self.municipio_id is None or foto.municipio_id == self.municipio_id


def evento(tipo: int, foto: FotoAlerta) -> pb.EventoAlerta:
    return pb.EventoAlerta(tipo=tipo, alerta=foto.a_pb(), momento=datetime.now(UTC).isoformat())


class DifusorAlertas:
    def __init__(self, sesiones, intervalo_s: float = 10.0):
        self._sesiones = sesiones
        self.intervalo_s = intervalo_s
        self._foto: dict[int, FotoAlerta] | None = None
        self._suscriptores: set[Suscripcion] = set()
        self._candado = threading.Lock()
        self._despertar = threading.Event()
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None

    # ── lectura ──────────────────────────────────────────────────────────────
    def _leer(self) -> dict[int, FotoAlerta]:
        with self._sesiones() as db:
            return {a.id: FotoAlerta(a.id, a.municipio_id, a.municipio.nombre, a.enfermedad_id, a.enfermedad.nombre,
                                     etiqueta(a.anio, a.semana_epi), a.nivel_riesgo, a.origen, a.mensaje)
                    for a in db.scalars(select(Alerta).where(Alerta.activa.is_(True)))}

    @staticmethod
    def diferencias(antes: dict[int, FotoAlerta], ahora: dict[int, FotoAlerta]) -> list[tuple[int, FotoAlerta]]:
        cambios = [(Tipo.NUEVA if i not in antes else Tipo.ACTUALIZADA, f)
                   for i, f in ahora.items() if antes.get(i) != f]
        cambios += [(Tipo.CERRADA, f) for i, f in antes.items() if i not in ahora]
        return cambios

    # ── suscripciones ────────────────────────────────────────────────────────
    def suscribir(self, municipio_id: int | None = None) -> tuple[Suscripcion, list[pb.EventoAlerta]]:
        """Registra al suscriptor y devuelve las alertas activas en este momento."""
        sus = Suscripcion(municipio_id)
        with self._candado:
            if self._foto is None:
                self._foto = self._leer()
            iniciales = [evento(Tipo.ACTIVA, f) for f in self._foto.values() if sus.acepta(f)]
            self._suscriptores.add(sus)
            self._asegurar_hilo()
        return sus, iniciales

    def cancelar(self, sus: Suscripcion) -> None:
        with self._candado:
            self._suscriptores.discard(sus)

    @property
    def suscriptores(self) -> int:
        return len(self._suscriptores)

    # ── publicación ──────────────────────────────────────────────────────────
    def revisar(self) -> int:
        """Compara con la foto anterior y publica los cambios. Devuelve cuántos hubo."""
        ahora = self._leer()
        with self._candado:
            cambios = self.diferencias(self._foto or {}, ahora) if self._foto is not None else []
            self._foto = ahora
            for tipo, foto in cambios:
                for sus in self._suscriptores:
                    if sus.acepta(foto):
                        try:
                            sus.cola.put_nowait(evento(tipo, foto))
                        except queue.Full:  # un cliente que no lee no frena a los demás
                            logger.warning("Suscriptor saturado; se descarta un evento")
        return len(cambios)

    def revisar_pronto(self) -> None:
        """Pide una revisión inmediata (p. ej. al terminar un entrenamiento) sin esperar el intervalo."""
        self._despertar.set()

    def _asegurar_hilo(self) -> None:
        if self._hilo is None or not self._hilo.is_alive():
            self._hilo = threading.Thread(target=self._bucle, daemon=True, name="difusor-alertas")
            self._hilo.start()

    def _bucle(self) -> None:
        while not self._detener.is_set():
            self._despertar.wait(self.intervalo_s)
            self._despertar.clear()
            if self._detener.is_set():
                break
            if self._suscriptores:
                try:
                    self.revisar()
                except Exception:
                    logger.exception("No se pudieron revisar las alertas")

    def detener(self) -> None:
        self._detener.set()
        self._despertar.set()
