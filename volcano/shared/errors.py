"""Domain errors and the single JSON shape every error response has.

    {"error": {"code": "NOT_FOUND", "message": "...", "details": ...}}

`code` is a stable English identifier the frontend can branch on; `message` is Spanish
because it is shown to the user as is.

This module has no web framework imports so the engine and the realtime hub can raise the
same errors; the FastAPI handlers live in `volcano.gateway.errors`.
"""
from typing import Any


class AppError(Exception):
    status_code: int = 400
    code: str = "ERROR"

    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class NotAuthenticatedError(AppError):
    status_code = 401
    code = "NOT_AUTHENTICATED"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE"


class ExternalSourceError(AppError):
    status_code = 502
    code = "EXTERNAL_SOURCE"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"


class TimeoutExpiredError(AppError):
    status_code = 504
    code = "TIMEOUT"
