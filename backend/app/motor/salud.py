"""Espera a que el motor responda al chequeo de salud estándar de gRPC.

    python -m app.motor.salud [segundos]     # sale con 0 si está SERVING, 1 si no

Lo usa start.sh para arrancar uvicorn solo cuando el motor ya escucha.
"""
import sys
import time

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from app.core.config import settings


def esperar(direccion: str, limite_s: float = 60.0) -> bool:
    fin = time.monotonic() + limite_s
    with grpc.insecure_channel(direccion) as canal:
        stub = health_pb2_grpc.HealthStub(canal)
        while time.monotonic() < fin:
            try:
                r = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=2)
                if r.status == health_pb2.HealthCheckResponse.SERVING:
                    return True
            except grpc.RpcError:
                pass
            time.sleep(0.5)
    return False


if __name__ == "__main__":
    limite = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    ok = esperar(settings.MOTOR_GRPC_DIRECCION, limite)
    print(f"Motor gRPC {'listo' if ok else 'NO respondió'} en {settings.MOTOR_GRPC_DIRECCION}")
    sys.exit(0 if ok else 1)
