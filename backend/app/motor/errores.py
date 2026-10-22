"""Errores de dominio ↔ códigos de estado de gRPC ↔ códigos HTTP.

El servidor convierte las excepciones de los servicios (NoEncontradoError…) en un código de
gRPC; el cliente hace el camino inverso. Así el navegador recibe el mismo JSON de error que
en el resto de la API, venga la respuesta de SQLAlchemy o de un stream de gRPC:

    NoEncontradoError ── NOT_FOUND ─────────── 404
    ConflictoError ───── ABORTED ───────────── 409
    ReglaNegocioError ── FAILED_PRECONDITION ─ 422
    PermisoDenegado ──── PERMISSION_DENIED ─── 403
    (motor apagado) ──── UNAVAILABLE ───────── 503
    (muy lento) ──────── DEADLINE_EXCEEDED ─── 504
"""
from contextlib import contextmanager

import grpc

from app.core.errors import (
    AppError,
    ConflictoError,
    NoAutenticadoError,
    NoEncontradoError,
    PermisoDenegadoError,
    ReglaNegocioError,
    ServicioNoDisponibleError,
    TiempoAgotadoError,
)

A_GRPC: dict[type[AppError], grpc.StatusCode] = {
    NoEncontradoError: grpc.StatusCode.NOT_FOUND,
    ConflictoError: grpc.StatusCode.ABORTED,
    ReglaNegocioError: grpc.StatusCode.FAILED_PRECONDITION,
    PermisoDenegadoError: grpc.StatusCode.PERMISSION_DENIED,
    NoAutenticadoError: grpc.StatusCode.UNAUTHENTICATED,
}

DESDE_GRPC: dict[grpc.StatusCode, type[AppError]] = {
    grpc.StatusCode.NOT_FOUND: NoEncontradoError,
    grpc.StatusCode.ABORTED: ConflictoError,
    grpc.StatusCode.ALREADY_EXISTS: ConflictoError,
    grpc.StatusCode.FAILED_PRECONDITION: ReglaNegocioError,
    grpc.StatusCode.INVALID_ARGUMENT: ReglaNegocioError,
    grpc.StatusCode.PERMISSION_DENIED: PermisoDenegadoError,
    grpc.StatusCode.DEADLINE_EXCEEDED: TiempoAgotadoError,
}

NO_DISPONIBLE = "El motor de predicción no está disponible en este momento. Intenta de nuevo en unos segundos."


@contextmanager
def traducir_errores(context: grpc.ServicerContext):
    """En el servidor: una excepción de dominio termina la RPC con el código que le corresponde."""
    try:
        yield
    except AppError as exc:
        context.abort(A_GRPC.get(type(exc), grpc.StatusCode.UNKNOWN), exc.mensaje)


def error_de_grpc(exc: grpc.RpcError) -> AppError:
    """En el cliente: convierte el estado de una RPC fallida en el error HTTP equivalente."""
    codigo = exc.code()
    if codigo in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.RESOURCE_EXHAUSTED):
        # UNAUTHENTICATED aquí es un error de configuración (token distinto), no del usuario
        return ServicioNoDisponibleError(NO_DISPONIBLE, {"grpc": codigo.name})
    cls = DESDE_GRPC.get(codigo)
    if cls is None:
        return AppError(f"Error del motor de predicción ({codigo.name}): {exc.details()}")
    return cls(exc.details() or codigo.name)
