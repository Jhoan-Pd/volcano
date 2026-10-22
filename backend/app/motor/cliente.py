"""Cliente gRPC asíncrono que usa la API REST para hablar con el motor.

Se usa `grpc.aio` porque FastAPI es asíncrono: mientras espera la respuesta del motor (o el
siguiente mensaje de un stream) el event loop sigue atendiendo otras peticiones.

Un canal de gRPC queda atado al event loop donde se crea. En producción hay un solo loop, pero
las pruebas (TestClient) abren uno por petición; por eso se guarda un canal por loop.
"""
import asyncio
import time
import weakref
from collections.abc import AsyncIterator, Iterable
from functools import lru_cache

import grpc

from app.core.config import settings
from app.motor.conversion import alerta_de_pb, nivel_de_pb, progreso_de_pb, punto_de_pb
from app.motor.errores import error_de_grpc
from app.motor.protos import prediccion_pb2 as pb
from app.motor.protos import prediccion_pb2_grpc as rpc
from app.motor.servicio import METADATO_ACTOR
from app.schemas.motor import (
    EscenarioIn,
    EstadoMotorOut,
    EventoAlertaOut,
    FilaCargaIn,
    ProgresoOut,
    PronosticoMotor,
    ResultadoEscenarioOut,
    ResumenCargaOut,
)


def pronostico_de_pb(p: pb.Pronostico) -> PronosticoMotor:
    return PronosticoMotor(
        municipio_id=p.municipio_id, municipio=p.municipio, enfermedad_id=p.enfermedad_id, enfermedad=p.enfermedad,
        algoritmo=p.algoritmo, modelo_id=p.modelo_id, semana_base=p.semana_base, nivel_max=nivel_de_pb(p.nivel_max),
        puntos=[punto_de_pb(x) for x in p.puntos], duracion_ms=p.duracion_ms, desde_cache=p.desde_cache)


def resultado_de_pb(r: pb.ResultadoEscenario) -> ResultadoEscenarioOut:
    return ResultadoEscenarioOut(
        id=r.id, municipio_id=r.municipio_id, enfermedad_id=r.enfermedad_id, base=[punto_de_pb(x) for x in r.base],
        escenario=[punto_de_pb(x) for x in r.escenario], nivel_max=nivel_de_pb(r.nivel_max),
        variacion_pct=r.variacion_pct, resumen=r.resumen, duracion_ms=r.duracion_ms, error=r.error or None)


def escenario_a_pb(e: EscenarioIn) -> pb.Escenario:
    return pb.Escenario(**e.model_dump())


class ClienteMotor:
    def __init__(self, direccion: str, token: str, timeout_s: float = 15.0):
        self.direccion = direccion
        self.timeout_s = timeout_s
        self._metadatos = (("authorization", f"Bearer {token}"),)
        self._canales: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, grpc.aio.Channel] = \
            weakref.WeakKeyDictionary()

    def _stub(self) -> rpc.MotorPrediccionStub:
        loop = asyncio.get_running_loop()
        canal = self._canales.get(loop)
        if canal is None:
            canal = grpc.aio.insecure_channel(self.direccion, options=[("grpc.keepalive_time_ms", 30_000)])
            self._canales[loop] = canal
        return rpc.MotorPrediccionStub(canal)

    def _meta(self, *extra: tuple[str, str]) -> tuple[tuple[str, str], ...]:
        return (*self._metadatos, *extra)

    async def cerrar(self) -> None:
        loop = asyncio.get_running_loop()
        canal = self._canales.pop(loop, None)
        if canal is not None:
            await canal.close()

    # ── Unary ────────────────────────────────────────────────────────────────
    async def estado(self) -> EstadoMotorOut:
        inicio = time.perf_counter()
        try:
            e = await self._stub().Estado(pb.Vacio(), metadata=self._meta(), timeout=min(self.timeout_s, 5))
        except grpc.RpcError as exc:
            return EstadoMotorOut(disponible=False, mensaje=error_de_grpc(exc).mensaje)
        return EstadoMotorOut(disponible=True, version=e.version, modelos_en_memoria=e.modelos_en_memoria,
                              entrenando=e.entrenando, activo_desde_s=e.activo_desde_s, rpcs_atendidas=e.rpcs_atendidas,
                              latencia_ms=round((time.perf_counter() - inicio) * 1000, 2))

    async def predecir(self, municipio_id: int, enfermedad_id: int) -> PronosticoMotor:
        try:
            p = await self._stub().Predecir(pb.SolicitudPrediccion(municipio_id=municipio_id,
                                                                   enfermedad_id=enfermedad_id),
                                            metadata=self._meta(), timeout=self.timeout_s)
        except grpc.RpcError as exc:
            raise error_de_grpc(exc) from None
        return pronostico_de_pb(p)

    # ── Server streaming ─────────────────────────────────────────────────────
    async def entrenar(self, enfermedad_id: int | None = None) -> AsyncIterator[ProgresoOut]:
        """Primer mensaje antes de devolver el iterador: así un 409 (ya hay uno en curso) llega
        como respuesta HTTP normal y no a mitad de un stream SSE ya abierto."""
        solicitud = pb.SolicitudEntrenamiento(enfermedad_id=enfermedad_id)
        llamada = self._stub().Entrenar(solicitud, metadata=self._meta())  # sin timeout: puede tardar minutos
        try:
            primero = await llamada.read()
        except grpc.RpcError as exc:
            raise error_de_grpc(exc) from None

        async def resto() -> AsyncIterator[ProgresoOut]:
            # Ya se usó read(): gRPC no permite mezclarlo con `async for` en la misma llamada
            msg = primero
            try:
                while msg is not grpc.aio.EOF:
                    yield ProgresoOut(**progreso_de_pb(msg))
                    msg = await llamada.read()
            except grpc.RpcError as exc:
                raise error_de_grpc(exc) from None
            finally:
                llamada.cancel()  # el navegador se fue: se suelta el stream (el entrenamiento sigue)
        return resto()

    async def seguir_alertas(self, municipio_id: int | None = None) -> AsyncIterator[EventoAlertaOut]:
        llamada = self._stub().SeguirAlertas(pb.FiltroAlertas(municipio_id=municipio_id), metadata=self._meta())
        try:
            async for ev in llamada:
                yield EventoAlertaOut(tipo=pb.EventoAlerta.Tipo.Name(ev.tipo), momento=ev.momento,
                                      alerta=alerta_de_pb(ev.alerta))
        except grpc.RpcError as exc:
            if exc.code() != grpc.StatusCode.CANCELLED:
                raise error_de_grpc(exc) from None
        finally:
            llamada.cancel()

    # ── Client streaming ─────────────────────────────────────────────────────
    async def cargar_reportes(self, filas: Iterable[FilaCargaIn], actor_id: int) -> ResumenCargaOut:
        async def mensajes() -> AsyncIterator[pb.FilaReporteFarmacia]:
            for f in filas:
                yield pb.FilaReporteFarmacia(**f.model_dump())

        inicio = time.perf_counter()
        try:
            r = await self._stub().CargarReportesFarmacia(
                mensajes(), metadata=self._meta((METADATO_ACTOR, str(actor_id))), timeout=self.timeout_s * 8)
        except grpc.RpcError as exc:
            raise error_de_grpc(exc) from None
        return ResumenCargaOut(
            filas_recibidas=r.filas_recibidas, filas_rechazadas=r.filas_rechazadas,
            semanas_creadas=r.semanas_creadas, semanas_actualizadas=r.semanas_actualizadas,
            semanas_rechazadas=r.semanas_rechazadas,
            errores=[{"fila": e.fila, "mensaje": e.mensaje} for e in r.errores],
            duracion_ms=round((time.perf_counter() - inicio) * 1000, 2))

    # ── Bidirectional ────────────────────────────────────────────────────────
    def simular(self) -> grpc.aio.StreamStreamCall:
        """Abre la conversación; quien llama escribe escenarios con `write()` y lee resultados."""
        return self._stub().SimularEscenarios(metadata=self._meta())


@lru_cache
def cliente_motor() -> ClienteMotor:
    """Dependencia de FastAPI: una sola instancia por proceso (las pruebas la reemplazan por un
    cliente hacia su propio servidor con `app.dependency_overrides`)."""
    return ClienteMotor(settings.MOTOR_GRPC_DIRECCION, settings.MOTOR_GRPC_TOKEN, settings.MOTOR_GRPC_TIMEOUT_S)
