"""Puente REST ↔ gRPC: el navegador usa HTTP, SSE y WebSocket; la API habla gRPC con el motor.

    Tipo de RPC        Endpoint                              Transporte hacia el navegador
    Unary              GET  /motor/estado, /motor/pronostico JSON
    Server streaming   POST /motor/entrenar                  SSE (fetch + ReadableStream; lleva token)
                       GET  /motor/alertas/eventos           SSE (EventSource; público)
    Client streaming   POST /motor/farmacia/carga            JSON → stream de filas hacia el motor
    Bidirectional      WS   /motor/simulador                 WebSocket ↔ stream bidireccional
"""
import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator

import grpc
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from app.core.deps import requiere_roles, solo_admin
from app.core.errors import AppError
from app.models import Usuario
from app.models.enums import RolNombre
from app.motor.cliente import ClienteMotor, cliente_motor, escenario_a_pb, resultado_de_pb
from app.motor.errores import error_de_grpc
from app.schemas.motor import CargaFarmaciaIn, EscenarioIn, EstadoMotorOut, PronosticoMotor, ResumenCargaOut

router = APIRouter(prefix="/motor", tags=["Motor de predicción (gRPC)"])
logger = logging.getLogger("predictor.motor.puente")
farmacia_o_admin = requiere_roles(RolNombre.FARMACIA, RolNombre.ADMIN)

KEEPALIVE_S = 15.0  # comentario SSE periódico para que proxies y Render no corten un stream silencioso
CABECERAS_SSE = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


# ── SSE ──────────────────────────────────────────────────────────────────────
def evento_sse(datos: BaseModel | dict, evento: str | None = None) -> str:
    cuerpo = datos.model_dump_json() if isinstance(datos, BaseModel) else json.dumps(datos, ensure_ascii=False)
    return (f"event: {evento}\n" if evento else "") + f"data: {cuerpo}\n\n"


async def flujo_sse(fuente: AsyncIterator[BaseModel], evento) -> AsyncIterator[str]:
    """Convierte un stream de gRPC en eventos SSE. Si pasan KEEPALIVE_S sin mensajes envía un
    comentario (`: keepalive`) sin cancelar la lectura pendiente del stream."""
    yield "retry: 5000\n\n"  # el navegador reintenta a los 5 s si se cae la conexión
    siguiente = asyncio.ensure_future(anext(fuente))
    try:
        while True:
            listo, _ = await asyncio.wait({siguiente}, timeout=KEEPALIVE_S)
            if not listo:
                yield ": keepalive\n\n"
                continue
            try:
                item = siguiente.result()
            except StopAsyncIteration:
                break
            except AppError as exc:
                yield evento_sse({"mensaje": exc.mensaje, "codigo": exc.codigo}, "error")
                break
            yield evento_sse(item, evento(item))
            siguiente = asyncio.ensure_future(anext(fuente))
    finally:
        siguiente.cancel()
        with contextlib.suppress(Exception):
            await fuente.aclose()


def respuesta_sse(flujo: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(flujo, media_type="text/event-stream", headers=CABECERAS_SSE)


# ── Unary ────────────────────────────────────────────────────────────────────
@router.get("/estado", response_model=EstadoMotorOut, summary="Estado del motor gRPC (unary)")
async def estado(motor: ClienteMotor = Depends(cliente_motor)):
    """Nunca falla: si el motor está apagado responde `disponible: false`."""
    return await motor.estado()


@router.get("/pronostico", response_model=PronosticoMotor, summary="Pronóstico calculado al momento (unary)")
async def pronostico(municipio_id: int, enfermedad_id: int, motor: ClienteMotor = Depends(cliente_motor)):
    """A diferencia de `/dashboard/prediccion` (que lee lo guardado en la BD), este endpoint le pide
    al motor que aplique ahora el modelo que tiene en memoria."""
    return await motor.predecir(municipio_id, enfermedad_id)


# ── Server streaming → SSE ───────────────────────────────────────────────────
@router.post("/entrenar", dependencies=[Depends(solo_admin)], response_class=StreamingResponse,
             summary="Reentrenar y recibir el avance en vivo (server streaming → SSE) — solo ADMIN",
             responses={200: {"content": {"text/event-stream": {}}}, 409: {"description": "Ya hay uno en curso"}})
async def entrenar(enfermedad_id: int | None = Query(None, description="Vacío = todas"),
                   motor: ClienteMotor = Depends(cliente_motor)):
    pasos = await motor.entrenar(enfermedad_id)  # 409/503 se responden aquí, antes de abrir el stream
    return respuesta_sse(flujo_sse(pasos, lambda p: "progreso"))


@router.get("/alertas/eventos", response_class=StreamingResponse,
            summary="Alertas en vivo (server streaming → SSE, público)",
            responses={200: {"content": {"text/event-stream": {}}}})
async def alertas_en_vivo(municipio_id: int | None = Query(None), motor: ClienteMotor = Depends(cliente_motor)):
    """Primero un evento `alerta` por cada alerta activa (tipo ACTIVA) y luego uno por cada cambio
    (NUEVA, ACTUALIZADA, CERRADA). Pensado para `new EventSource(url)` en el navegador."""
    return respuesta_sse(flujo_sse(motor.seguir_alertas(municipio_id), lambda e: "alerta"))


# ── Client streaming ─────────────────────────────────────────────────────────
@router.post("/farmacia/carga", response_model=ResumenCargaOut, status_code=status.HTTP_200_OK,
             summary="Carga masiva de reportes de farmacia (client streaming)")
async def cargar_reportes(entrada: CargaFarmaciaIn, usuario: Usuario = Depends(farmacia_o_admin),
                          motor: ClienteMotor = Depends(cliente_motor)):
    """Las filas (ya revisadas en el navegador por un Web Worker) viajan al motor como un stream:
    el motor valida cada una al recibirla, agrupa por semana y aplica las mismas reglas que el
    formulario semanal (una FARMACIA solo carga las últimas 8 semanas de su propia farmacia)."""
    return await motor.cargar_reportes(entrada.filas, usuario.id)


# ── Bidirectional ↔ WebSocket ────────────────────────────────────────────────
@router.websocket("/simulador")
async def simulador(ws: WebSocket, motor: ClienteMotor = Depends(cliente_motor)):
    """Cada mensaje JSON del navegador es un escenario; cada respuesta llega en cuanto el motor la
    calcula. Dos tareas concurrentes: una sube escenarios y otra baja resultados."""
    await ws.accept()
    llamada = motor.simular()

    async def subir() -> None:
        try:
            while True:
                datos = await ws.receive_json()
                try:
                    escenario = EscenarioIn.model_validate(datos)
                except ValidationError as exc:
                    ident = datos.get("id") if isinstance(datos, dict) else None
                    await ws.send_json({"id": ident, "error": exc.errors()[0]["msg"]})
                    continue
                await llamada.write(escenario_a_pb(escenario))
        except WebSocketDisconnect:
            pass
        finally:
            with contextlib.suppress(Exception):
                await llamada.done_writing()

    tarea = asyncio.create_task(subir())
    try:
        async for resultado in llamada:
            await ws.send_json(resultado_de_pb(resultado).model_dump())
    except grpc.RpcError as exc:
        if exc.code() != grpc.StatusCode.CANCELLED:
            error = error_de_grpc(exc)
            with contextlib.suppress(Exception):
                await ws.send_json({"id": None, "error": error.mensaje, "fatal": True})
                await ws.close(code=status.WS_1011_INTERNAL_ERROR)
    except (WebSocketDisconnect, RuntimeError):
        pass  # el navegador cerró mientras se enviaba
    finally:
        tarea.cancel()
        llamada.cancel()
