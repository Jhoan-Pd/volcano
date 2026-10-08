"""Manejo centralizado de errores.

Todas las respuestas de error tienen la misma forma:
    {"error": {"codigo": "NO_ENCONTRADO", "mensaje": "...", "detalles": ...}}
Así el frontend muestra mensajes consistentes sin conocer cada endpoint.
"""
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("predictor")


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    codigo: str = "ERROR"

    def __init__(self, mensaje: str, detalles: Any = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles


class NoEncontradoError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    codigo = "NO_ENCONTRADO"


class ConflictoError(AppError):
    status_code = status.HTTP_409_CONFLICT
    codigo = "CONFLICTO"


class NoAutenticadoError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    codigo = "NO_AUTENTICADO"


class PermisoDenegadoError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    codigo = "PERMISO_DENEGADO"


class ReglaNegocioError(AppError):
    status_code = 422
    codigo = "REGLA_DE_NEGOCIO"


class FuenteExternaError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    codigo = "FUENTE_EXTERNA"


def _respuesta(status_code: int, codigo: str, mensaje: str, detalles: Any = None, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"codigo": codigo, "mensaje": mensaje, "detalles": detalles}},
        headers=headers,
    )


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, NoAutenticadoError) else None
        return _respuesta(exc.status_code, exc.codigo, exc.mensaje, exc.detalles, headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError):
        detalles = [
            {"campo": ".".join(str(p) for p in e["loc"] if p != "body"),
             "mensaje": e["msg"].removeprefix("Value error, ")}
            for e in exc.errors()
        ]
        return _respuesta(422, "VALIDACION", "Los datos enviados no son válidos", detalles)

    @app.exception_handler(ValidationError)
    async def _validacion_interna(_: Request, exc: ValidationError):
        detalles = [{"campo": ".".join(str(p) for p in e["loc"]), "mensaje": e["msg"].removeprefix("Value error, ")}
                    for e in exc.errors()]
        return _respuesta(422, "VALIDACION", "Los datos enviados no son válidos", detalles)

    @app.exception_handler(IntegrityError)
    async def _integridad(_: Request, exc: IntegrityError):
        logger.warning("IntegrityError: %s", exc.orig)
        return _respuesta(409, "CONFLICTO", "El registro viola una restricción (duplicado o referencia inválida)")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        codigos = {401: "NO_AUTENTICADO", 403: "PERMISO_DENEGADO", 404: "NO_ENCONTRADO", 405: "METODO_NO_PERMITIDO"}
        return _respuesta(exc.status_code, codigos.get(exc.status_code, "HTTP"), str(exc.detail),
                          headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _generico(_: Request, exc: Exception):
        logger.exception("Error no controlado: %s", exc)
        return _respuesta(500, "ERROR_INTERNO", "Ocurrió un error inesperado en el servidor")
