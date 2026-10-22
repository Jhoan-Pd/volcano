"""Interceptores del servidor gRPC (el equivalente a los middlewares de FastAPI).

- `InterceptorToken`: el motor solo escucha en 127.0.0.1, pero igual exige el token compartido
  en el metadato `authorization` (defensa en profundidad: otro proceso del contenedor no puede
  entrenar ni cargar reportes sin él). El chequeo de salud estándar queda libre.
- `InterceptorRegistro`: cuenta las RPC y registra método, código de estado y duración. En los
  métodos con stream de respuesta mide hasta que el stream termina, no hasta el primer mensaje.

Ambos envuelven el *handler* original con uno del mismo tipo (unary/stream), así sirven para
los cuatro tipos de RPC sin repetir lógica.
"""
import logging
import secrets
import time
from collections.abc import Callable

import grpc

logger = logging.getLogger("predictor.motor.rpc")
SIN_TOKEN = ("/grpc.health.v1.Health/",)
TIPOS = ("unary_unary", "unary_stream", "stream_unary", "stream_stream")


def _envolver(handler: grpc.RpcMethodHandler | None, decorar: Callable) -> grpc.RpcMethodHandler | None:
    """Aplica `decorar(funcion, responde_stream)` a la función del handler, sea del tipo que sea."""
    if handler is None:
        return None
    for tipo in TIPOS:
        funcion = getattr(handler, tipo)
        if funcion is not None:
            return handler._replace(**{tipo: decorar(funcion, handler.response_streaming)})
    return handler


class InterceptorToken(grpc.ServerInterceptor):
    def __init__(self, token: str):
        self._esperado = f"Bearer {token}"

    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler_call_details.method.startswith(SIN_TOKEN):
            return handler
        recibido = dict(handler_call_details.invocation_metadata or ()).get("authorization", "")
        if secrets.compare_digest(recibido, self._esperado):
            return handler

        def rechazar(_funcion, _stream):
            def interno(_peticion, context):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token del motor inválido o ausente")
            return interno

        return _envolver(handler, rechazar)


class InterceptorRegistro(grpc.ServerInterceptor):
    def __init__(self, metricas):
        self.metricas = metricas

    def intercept_service(self, continuation, handler_call_details):
        metodo = handler_call_details.method.rsplit("/", 1)[-1]

        def medir(funcion, responde_stream):
            def terminar(inicio: float, context, mensajes: int | None = None) -> None:
                codigo = context.code() or grpc.StatusCode.OK
                extra = f" · {mensajes} mensajes" if mensajes is not None else ""
                logger.info("%s → %s en %.0f ms%s", metodo, getattr(codigo, "name", codigo),
                            (time.perf_counter() - inicio) * 1000, extra)

            def unaria(peticion, context):
                self.metricas.contar()
                inicio = time.perf_counter()
                try:
                    return funcion(peticion, context)
                finally:
                    terminar(inicio, context)

            def en_stream(peticion, context):
                self.metricas.contar()
                inicio, enviados = time.perf_counter(), 0
                try:
                    for mensaje in funcion(peticion, context):
                        enviados += 1
                        yield mensaje
                finally:
                    terminar(inicio, context, enviados)

            return en_stream if responde_stream else unaria

        return _envolver(continuation(handler_call_details), medir)
