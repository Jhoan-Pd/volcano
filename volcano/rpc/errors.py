"""Domain errors ↔ gRPC status codes ↔ HTTP status codes.

The server turns the services' exceptions (NotFoundError…) into a gRPC code; the clients do the
reverse. The browser therefore gets the same JSON error as from the rest of the API, whether the
answer came from SQLAlchemy or from a gRPC stream:

    NotFoundError ───────── NOT_FOUND ─────────── 404
    ConflictError ───────── ABORTED ───────────── 409
    BusinessRuleError ───── FAILED_PRECONDITION ─ 422
    PermissionDenied ────── PERMISSION_DENIED ─── 403
    (engine down) ───────── UNAVAILABLE ───────── 503
    (too slow) ──────────── DEADLINE_EXCEEDED ─── 504
"""
from contextlib import contextmanager

import grpc

from volcano.shared.errors import (
    AppError,
    BusinessRuleError,
    ConflictError,
    NotAuthenticatedError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    TimeoutExpiredError,
)

TO_GRPC: dict[type[AppError], grpc.StatusCode] = {
    NotFoundError: grpc.StatusCode.NOT_FOUND,
    ConflictError: grpc.StatusCode.ABORTED,
    BusinessRuleError: grpc.StatusCode.FAILED_PRECONDITION,
    PermissionDeniedError: grpc.StatusCode.PERMISSION_DENIED,
    NotAuthenticatedError: grpc.StatusCode.UNAUTHENTICATED,
}

FROM_GRPC: dict[grpc.StatusCode, type[AppError]] = {
    grpc.StatusCode.NOT_FOUND: NotFoundError,
    grpc.StatusCode.ABORTED: ConflictError,
    grpc.StatusCode.ALREADY_EXISTS: ConflictError,
    grpc.StatusCode.FAILED_PRECONDITION: BusinessRuleError,
    grpc.StatusCode.INVALID_ARGUMENT: BusinessRuleError,
    grpc.StatusCode.PERMISSION_DENIED: PermissionDeniedError,
    grpc.StatusCode.DEADLINE_EXCEEDED: TimeoutExpiredError,
}

UNAVAILABLE_ES = "El motor de predicción no está disponible en este momento. Intenta de nuevo en unos segundos."


@contextmanager
def abort_on_domain_errors(context: grpc.ServicerContext):
    """Server side: a domain exception ends the RPC with its matching code."""
    try:
        yield
    except AppError as exc:
        context.abort(TO_GRPC.get(type(exc), grpc.StatusCode.UNKNOWN), exc.message)


def from_rpc_error(exc: grpc.RpcError) -> AppError:
    """Client side: turn the status of a failed RPC into the equivalent HTTP error."""
    code = exc.code()
    if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.RESOURCE_EXHAUSTED):
        # UNAUTHENTICATED here is a configuration error (different tokens), not the user's fault
        return ServiceUnavailableError(UNAVAILABLE_ES, {"grpc": code.name})
    cls = FROM_GRPC.get(code)
    if cls is None:
        return AppError(f"Error del motor de predicción ({code.name}): {exc.details()}")
    return cls(exc.details() or code.name)
