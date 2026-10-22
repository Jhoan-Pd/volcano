"""Servidor gRPC del motor de predicción.

    python -m app.motor.servidor            # escucha en MOTOR_GRPC_DIRECCION (127.0.0.1:50051)

En Render corre en el mismo servicio que la API (ver backend/start.sh): primero arranca este
proceso, se espera a que el puerto responda y luego arranca uvicorn. Solo uvicorn queda expuesto
a internet; el motor escucha en 127.0.0.1 y únicamente la API habla con él.

Además del servicio propio registra dos servicios estándar de gRPC:
- grpc.health.v1.Health: chequeo de salud (lo usa start.sh y cualquier balanceador).
- Reflexión: permite explorar el servicio con `grpcurl -plaintext 127.0.0.1:50051 list`.
"""
import logging
import signal
from concurrent import futures
from dataclasses import dataclass

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from app.core.config import settings
from app.db.session import SessionLocal
from app.motor.cache import CacheModelos
from app.motor.difusor import DifusorAlertas
from app.motor.interceptores import InterceptorRegistro, InterceptorToken
from app.motor.protos import prediccion_pb2 as pb
from app.motor.servicio import Metricas, MotorPrediccionServicer, registrar

logger = logging.getLogger("predictor.motor")
NOMBRE_SERVICIO = pb.DESCRIPTOR.services_by_name["MotorPrediccion"].full_name
MB = 1024 * 1024


@dataclass
class Motor:
    servidor: grpc.Server
    puerto: int
    servicer: MotorPrediccionServicer

    def iniciar(self) -> "Motor":
        self.servidor.start()
        return self

    def detener(self, gracia: float | None = 5) -> None:
        self.servicer.difusor.detener()
        self.servidor.stop(grace=gracia).wait()


def crear_servidor(direccion: str | None = None, servicer: MotorPrediccionServicer | None = None,
                   token: str | None = None, hilos: int | None = None) -> Motor:
    """Arma el servidor sin iniciarlo. Con la dirección '127.0.0.1:0' el sistema elige un
    puerto libre (así lo usan las pruebas); el puerto asignado queda en `Motor.puerto`."""
    hilos = hilos or settings.MOTOR_GRPC_HILOS
    servicer = servicer or MotorPrediccionServicer(
        cache=CacheModelos(ttl_s=settings.MOTOR_CACHE_TTL_S),
        difusor=DifusorAlertas(SessionLocal, intervalo_s=settings.MOTOR_INTERVALO_ALERTAS_S),
        metricas=Metricas())
    metricas = servicer.metricas
    servidor = grpc.server(
        futures.ThreadPoolExecutor(max_workers=hilos, thread_name_prefix="motor"),
        interceptors=[InterceptorRegistro(metricas), InterceptorToken(token or settings.MOTOR_GRPC_TOKEN)],
        # Cada stream abierto ocupa un hilo: por encima del límite se responde RESOURCE_EXHAUSTED
        # en lugar de dejar peticiones colgadas.
        maximum_concurrent_rpcs=hilos,
        options=[
            ("grpc.max_receive_message_length", 8 * MB),
            ("grpc.keepalive_time_ms", 30_000),          # ping a los streams largos (alertas)
            ("grpc.keepalive_timeout_ms", 10_000),
            ("grpc.http2.min_ping_interval_without_data_ms", 10_000),
        ])
    registrar(servidor, servicer)

    salud = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(salud, servidor)
    for nombre in ("", NOMBRE_SERVICIO):
        salud.set(nombre, health_pb2.HealthCheckResponse.SERVING)
    reflection.enable_server_reflection((NOMBRE_SERVICIO, reflection.SERVICE_NAME, health.SERVICE_NAME), servidor)

    puerto = servidor.add_insecure_port(direccion or settings.MOTOR_GRPC_DIRECCION)
    return Motor(servidor, puerto, servicer)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    motor = crear_servidor().iniciar()
    logger.info("Motor de predicción gRPC escuchando en %s", settings.MOTOR_GRPC_DIRECCION)

    def apagar(signum, _frame):
        logger.info("Señal %s: cerrando el motor (5 s de gracia para los streams abiertos)", signum)
        motor.servicer.difusor.detener()
        motor.servidor.stop(grace=5)

    signal.signal(signal.SIGTERM, apagar)
    signal.signal(signal.SIGINT, apagar)
    motor.servidor.wait_for_termination()


if __name__ == "__main__":
    main()
