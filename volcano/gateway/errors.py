"""Centralized HTTP error handling.

Every error response has the same shape:
    {"error": {"code": "NOT_FOUND", "message": "...", "details": ...}}
so the frontend shows consistent messages without knowing each endpoint. `code` is stable English
for the client to branch on; `message` is Spanish because the user reads it.
"""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from volcano.shared.errors import AppError, NotAuthenticatedError

logger = logging.getLogger("volcano.gateway")

HTTP_CODES = {401: "NOT_AUTHENTICATED", 403: "PERMISSION_DENIED", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
INVALID_DATA_ES = "Los datos enviados no son válidos"


def error_response(status_code: int, code: str, message: str, details: Any = None, headers=None) -> JSONResponse:
    return JSONResponse(status_code=status_code,
                        content={"error": {"code": code, "message": message, "details": details}},
                        headers=headers)


def _field_errors(errors: list[dict], skip_body: bool) -> list[dict]:
    return [{"field": ".".join(str(p) for p in e["loc"] if not (skip_body and p == "body")),
             "message": e["msg"].removeprefix("Value error, ")}
            for e in errors]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, NotAuthenticatedError) else None
        return error_response(exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError):
        return error_response(422, "VALIDATION", INVALID_DATA_ES, _field_errors(exc.errors(), skip_body=True))

    @app.exception_handler(ValidationError)
    async def _internal_validation(_: Request, exc: ValidationError):
        return error_response(422, "VALIDATION", INVALID_DATA_ES, _field_errors(exc.errors(), skip_body=False))

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        logger.warning("IntegrityError: %s", exc.orig)
        return error_response(409, "CONFLICT", "El registro viola una restricción (duplicado o referencia inválida)")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return error_response(exc.status_code, HTTP_CODES.get(exc.status_code, "HTTP"), str(exc.detail),
                              headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return error_response(500, "INTERNAL_ERROR", "Ocurrió un error inesperado en el servidor")
