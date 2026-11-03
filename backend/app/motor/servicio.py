"""Implementación del servicio gRPC `MotorPrediccion` (ver protos/prediccion.proto).

Cada método reutiliza los servicios de dominio que ya usa la API REST (PrediccionService,
ReporteFarmaciaService, reentrenar…): el motor cambia el transporte y la forma de entregar los
resultados (streams), no las reglas de negocio.

Las dependencias se inyectan en el constructor (fábrica de sesiones, caché, difusor) para que
las pruebas levanten el servidor contra la BD de pruebas.
"""
import logging
import queue
import threading
import time
from collections import defaultdict
from collections.abc import Callable, Iterator

import grpc
from pydantic import ValidationError

from app.core.epi import etiqueta, semanas_del_anio
from app.core.errors import NoEncontradoError, PermisoDenegadoError, ReglaNegocioError
from app.core.texto import numero_es
from app.db.session import SessionLocal
from app.ml.escenarios import Ajustes, aplicar
from app.ml.progreso import Etapa, EventoProgreso
from app.models import Usuario
from app.models.enums import NivelRiesgo
from app.motor.cache import CacheModelos
from app.motor.conversion import nivel_a_pb, progreso_a_pb, punto_a_pb
from app.motor.difusor import DifusorAlertas
from app.motor.errores import traducir_errores
from app.motor.protos import prediccion_pb2 as pb
from app.motor.protos import prediccion_pb2_grpc as rpc
from app.schemas.farmacia import ItemReporte
from app.services.entrenamiento import control, reentrenar
from app.services.reporte_farmacia_service import ReporteFarmaciaService

logger = logging.getLogger("predictor.motor")
VERSION = "1.0.0"
METADATO_ACTOR = "x-actor-id"
MAX_ERRORES = 100
FIN_DE_ENTRENAMIENTO = {Etapa.FIN, Etapa.ERROR}


class Metricas:
    """Contador de RPCs atendidas; lo incrementa el interceptor de registro."""

    def __init__(self) -> None:
        self.inicio = time.monotonic()
        self._rpcs = 0
        self._candado = threading.Lock()

    def contar(self) -> None:
        with self._candado:
            self._rpcs += 1

    @property
    def rpcs(self) -> int:
        return self._rpcs


def _ms(desde: float) -> float:
    return round((time.perf_counter() - desde) * 1000, 2)


class MotorPrediccionServicer(rpc.MotorPrediccionServicer):
    def __init__(self, sesiones: Callable = SessionLocal, cache: CacheModelos | None = None,
                 difusor: DifusorAlertas | None = None, metricas: Metricas | None = None):
        self.sesiones = sesiones
        self.cache = cache or CacheModelos()
        self.difusor = difusor or DifusorAlertas(sesiones)
        self.metricas = metricas or Metricas()

    # ── Unary ────────────────────────────────────────────────────────────────
    def Estado(self, request, context):
        return pb.EstadoMotor(version=VERSION, modelos_en_memoria=len(self.cache),
                              entrenando=control.estado().en_curso,
                              activo_desde_s=round(time.monotonic() - self.metricas.inicio, 1),
                              rpcs_atendidas=self.metricas.rpcs)

    def Predecir(self, request, context):
        inicio = time.perf_counter()
        with traducir_errores(context), self.sesiones() as db:
            cargado, desde_cache = self.cache.obtener(db, request.enfermedad_id)
            pron = cargado.pronosticador
            if not pron.tiene(request.municipio_id):
                raise NoEncontradoError(f"No hay datos del municipio {request.municipio_id} para esta enfermedad")
            puntos = pron.pronosticar(request.municipio_id)
            return pb.Pronostico(
                municipio_id=request.municipio_id, municipio=cargado.municipios[request.municipio_id],
                enfermedad_id=request.enfermedad_id, enfermedad=cargado.enfermedad, algoritmo=cargado.algoritmo,
                modelo_id=cargado.modelo_id, semana_base=etiqueta(*pron.semana_base(request.municipio_id)),
                nivel_max=nivel_a_pb(NivelRiesgo.peor(p.nivel for p in puntos)),
                puntos=[punto_a_pb(p) for p in puntos], duracion_ms=_ms(inicio), desde_cache=desde_cache)

    # ── Server streaming ─────────────────────────────────────────────────────
    def Entrenar(self, request, context) -> Iterator[pb.ProgresoEntrenamiento]:
        """El entrenamiento corre en su propio hilo y deja cada paso en una cola; este generador
        la vacía hacia el stream. Si el cliente se desconecta, el entrenamiento sigue y termina."""
        with traducir_errores(context):
            control.iniciar()  # ConflictoError → ABORTED si ya hay uno en curso
        enfermedad_id = request.enfermedad_id if request.HasField("enfermedad_id") else None
        cola: queue.Queue[EventoProgreso] = queue.Queue()

        def tarea() -> None:
            reentrenar(enfermedad_id, progreso=cola.put)
            self.cache.invalidar()
            self.difusor.revisar_pronto()

        threading.Thread(target=tarea, daemon=True, name="entrenamiento-grpc").start()
        while context.is_active():
            try:
                evento = cola.get(timeout=1.0)
            except queue.Empty:
                continue
            yield progreso_a_pb(evento)
            if evento.etapa in FIN_DE_ENTRENAMIENTO:
                return

    def SeguirAlertas(self, request, context) -> Iterator[pb.EventoAlerta]:
        municipio_id = request.municipio_id if request.HasField("municipio_id") else None
        sus, iniciales = self.difusor.suscribir(municipio_id)
        try:
            yield from iniciales
            while context.is_active():
                try:
                    yield sus.cola.get(timeout=1.0)
                except queue.Empty:
                    continue
        finally:
            self.difusor.cancelar(sus)

    # ── Client streaming ─────────────────────────────────────────────────────
    def _actor(self, db, context) -> Usuario:
        valor = dict(context.invocation_metadata()).get(METADATO_ACTOR, "")
        usuario = db.get(Usuario, int(valor)) if valor.isdigit() else None
        if usuario is None or not usuario.activo:
            raise PermisoDenegadoError("Falta el usuario que hace la carga (metadato x-actor-id)")
        return usuario

    @staticmethod
    def _validar_fila(f: pb.FilaReporteFarmacia) -> ItemReporte:
        if not 1 <= f.semana_epi <= semanas_del_anio(f.anio):
            raise ValueError(f"La semana {f.semana_epi} no existe en {f.anio}")
        return ItemReporte(categoria=f.categoria.strip().upper(), unidades=f.unidades)

    def CargarReportesFarmacia(self, request_iterator, context):
        """Cada fila se valida apenas llega (el error se reporta con su número de fila) y las
        válidas se agrupan por farmacia y semana. Al cerrarse el stream se guarda cada semana."""
        resumen = pb.ResumenCarga()
        semanas: dict[tuple[int | None, int, int], dict[str, ItemReporte]] = defaultdict(dict)
        primera_fila: dict[tuple[int | None, int, int], int] = {}

        def error(fila: int, mensaje: str) -> None:
            if len(resumen.errores) < MAX_ERRORES:
                resumen.errores.append(pb.ErrorFila(fila=fila, mensaje=mensaje))

        with traducir_errores(context), self.sesiones() as db:
            servicio = ReporteFarmaciaService(db, self._actor(db, context))
            for f in request_iterator:
                resumen.filas_recibidas += 1
                try:
                    item = self._validar_fila(f)
                except (ValueError, ValidationError) as exc:
                    resumen.filas_rechazadas += 1
                    error(f.fila, exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc))
                    continue
                clave = (f.farmacia_id if f.HasField("farmacia_id") else None, f.anio, f.semana_epi)
                if item.categoria.value in semanas[clave]:
                    resumen.filas_rechazadas += 1
                    error(f.fila, f"{item.categoria.value} se repite en la semana {etiqueta(f.anio, f.semana_epi)}")
                    continue
                semanas[clave][item.categoria.value] = item
                primera_fila.setdefault(clave, f.fila)

            for clave, items in sorted(semanas.items(), key=lambda x: primera_fila[x[0]]):
                farmacia_id, anio, semana = clave
                try:
                    nueva = servicio.guardar_semana(anio, semana, list(items.values()), farmacia_id)
                except (ReglaNegocioError, PermisoDenegadoError, NoEncontradoError) as exc:
                    db.rollback()
                    resumen.semanas_rechazadas += 1
                    error(primera_fila[clave], f"Semana {etiqueta(anio, semana)}: {exc.mensaje}")
                    continue
                if nueva:
                    resumen.semanas_creadas += 1
                else:
                    resumen.semanas_actualizadas += 1
        logger.info("Carga de farmacia: %d filas, %d semanas nuevas, %d actualizadas, %d rechazadas",
                    resumen.filas_recibidas, resumen.semanas_creadas, resumen.semanas_actualizadas,
                    resumen.semanas_rechazadas)
        return resumen

    # ── Bidirectional ────────────────────────────────────────────────────────
    def SimularEscenarios(self, request_iterator, context) -> Iterator[pb.ResultadoEscenario]:
        """Conversación con estado: el pronóstico base de cada municipio/enfermedad se calcula una
        sola vez por stream; los escenarios siguientes solo pagan la predicción modificada."""
        bases: dict[tuple[int, int, int], list] = {}
        with self.sesiones() as db:
            for esc in request_iterator:
                inicio = time.perf_counter()
                try:
                    yield self._simular(db, esc, bases, inicio)
                except (NoEncontradoError, ReglaNegocioError) as exc:
                    yield pb.ResultadoEscenario(id=esc.id, municipio_id=esc.municipio_id,
                                                enfermedad_id=esc.enfermedad_id, error=exc.mensaje,
                                                duracion_ms=_ms(inicio))

    def _simular(self, db, esc: pb.Escenario, bases: dict, inicio: float) -> pb.ResultadoEscenario:
        ajustes = Ajustes(esc.delta_temperatura_c, esc.cambio_lluvia_pct, esc.cambio_busquedas_pct,
                          esc.cambio_farmacias_pct, esc.ceniza)
        if errores := ajustes.errores():
            raise ReglaNegocioError("; ".join(errores))
        cargado, _ = self.cache.obtener(db, esc.enfermedad_id)
        pron = cargado.pronosticador
        if not pron.tiene(esc.municipio_id):
            raise NoEncontradoError(f"No hay datos del municipio {esc.municipio_id} para esta enfermedad")
        clave = (esc.municipio_id, esc.enfermedad_id, cargado.modelo_id)
        if clave not in bases:
            bases[clave] = pron.pronosticar(esc.municipio_id)
        base = bases[clave]
        X = aplicar(pron.entrada(esc.municipio_id), ajustes, pron.tipicos(esc.municipio_id))
        escenario = base if ajustes.sin_cambios else pron.pronosticar(esc.municipio_id, X)

        total_base = sum(p.casos_esperados for p in base)
        total_esc = sum(p.casos_esperados for p in escenario)
        variacion = (total_esc / total_base - 1) * 100 if total_base else (100.0 if total_esc else 0.0)
        peor = NivelRiesgo.peor(p.nivel for p in escenario)
        municipio, enfermedad = cargado.municipios[esc.municipio_id], cargado.enfermedad.lower()
        if ajustes.sin_cambios:
            resumen = (f"Sin cambios, en {municipio} se esperan {numero_es(total_esc)} casos de {enfermedad} "
                       f"en las próximas 4 semanas. Nivel máximo: {peor.etiqueta.lower()}.")
        else:
            resumen = (f"Con {ajustes.describir()}, en {municipio} se esperarían {numero_es(total_esc)} casos de "
                       f"{enfermedad} en 4 semanas ({variacion:+.0f} % frente a {numero_es(total_base)}). "
                       f"Nivel máximo: {peor.etiqueta.lower()}.")
        return pb.ResultadoEscenario(
            id=esc.id, municipio_id=esc.municipio_id, enfermedad_id=esc.enfermedad_id,
            base=[punto_a_pb(p) for p in base], escenario=[punto_a_pb(p) for p in escenario],
            nivel_max=nivel_a_pb(peor), variacion_pct=round(variacion, 1), resumen=resumen,
            duracion_ms=_ms(inicio))


def registrar(servidor: grpc.Server, servicer: MotorPrediccionServicer) -> None:
    rpc.add_MotorPrediccionServicer_to_server(servicer, servidor)
