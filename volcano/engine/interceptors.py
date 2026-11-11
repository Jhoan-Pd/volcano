"""gRPC server interceptors (the counterpart of FastAPI middlewares).

- `TokenInterceptor`: the engine only listens on 127.0.0.1, but it still demands the shared token in
  the `authorization` metadata (defence in depth: another process in the container cannot train or
  upload reports without it). The standard health check stays open.
- `LoggingInterceptor`: counts RPCs and logs method, status code and duration. For methods with a
  response stream it measures until the stream ends, not until the first message.

Both wrap the original handler with one of the same kind (unary/stream), so they serve the four RPC
types without repeating logic.
"""
import logging
import secrets
import time
from collections.abc import Callable

import grpc

logger = logging.getLogger("volcano.engine.rpc")
UNAUTHENTICATED_PREFIXES = ("/grpc.health.v1.Health/", "/grpc.reflection.")
HANDLER_KINDS = ("unary_unary", "unary_stream", "stream_unary", "stream_stream")


def _wrap(handler: grpc.RpcMethodHandler | None, decorate: Callable) -> grpc.RpcMethodHandler | None:
    """Apply `decorate(function, streams_response)` to the handler's function, whatever its kind."""
    if handler is None:
        return None
    for kind in HANDLER_KINDS:
        function = getattr(handler, kind)
        if function is not None:
            return handler._replace(**{kind: decorate(function, handler.response_streaming)})
    return handler


class TokenInterceptor(grpc.ServerInterceptor):
    def __init__(self, token: str):
        self._expected = f"Bearer {token}"

    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler_call_details.method.startswith(UNAUTHENTICATED_PREFIXES):
            return handler
        received = dict(handler_call_details.invocation_metadata or ()).get("authorization", "")
        if secrets.compare_digest(received, self._expected):
            return handler

        def reject(_function, _streams):
            def inner(_request, context):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing engine token")
            return inner

        return _wrap(handler, reject)


class LoggingInterceptor(grpc.ServerInterceptor):
    def __init__(self, metrics):
        self.metrics = metrics

    def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method.rsplit("/", 1)[-1]

        def measure(function, streams_response):
            def finish(start: float, context, messages: int | None = None) -> None:
                code = context.code() or grpc.StatusCode.OK
                extra = f" · {messages} messages" if messages is not None else ""
                logger.info("%s → %s in %.0f ms%s", method, getattr(code, "name", code),
                            (time.perf_counter() - start) * 1000, extra)

            def unary(request, context):
                self.metrics.count()
                start = time.perf_counter()
                try:
                    return function(request, context)
                finally:
                    finish(start, context)

            def streaming(request, context):
                self.metrics.count()
                start, sent = time.perf_counter(), 0
                try:
                    for message in function(request, context):
                        sent += 1
                        yield message
                finally:
                    finish(start, context, sent)

            return streaming if streams_response else unary

        return _wrap(continuation(handler_call_details), measure)
