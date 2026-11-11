"""Wait until the engine answers the standard gRPC health check.

    python -m volcano.engine.healthcheck [seconds]     # exits 0 when SERVING, 1 otherwise

Used by the container health check and by local scripts.
"""
import sys
import time

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from volcano.shared.config import settings


def wait_until_serving(address: str, limit_s: float = 60.0) -> bool:
    deadline = time.monotonic() + limit_s
    with grpc.insecure_channel(address) as channel:
        stub = health_pb2_grpc.HealthStub(channel)
        while time.monotonic() < deadline:
            try:
                r = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=2)
                if r.status == health_pb2.HealthCheckResponse.SERVING:
                    return True
            except grpc.RpcError:
                pass
            time.sleep(0.5)
    return False


if __name__ == "__main__":
    limit = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    ok = wait_until_serving(settings.ENGINE_GRPC_ADDRESS, limit)
    print(f"gRPC engine {'ready' if ok else 'NOT answering'} at {settings.ENGINE_GRPC_ADDRESS}")
    sys.exit(0 if ok else 1)
