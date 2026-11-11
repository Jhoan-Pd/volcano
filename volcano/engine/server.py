"""gRPC server of the prediction engine.

    python -m volcano.engine.server            # listens on ENGINE_GRPC_ADDRESS (127.0.0.1:50051)

In the container it runs next to the gateway and the realtime hub (see deploy/supervisord.conf).
Only the edge proxy is exposed to the internet; the engine listens on 127.0.0.1 and only the other
two services talk to it.

Besides its own service it registers two standard gRPC services:
- grpc.health.v1.Health: health check (container health check and any load balancer).
- Reflection: lets you explore the service with `grpcurl -plaintext 127.0.0.1:50051 list`.
"""
import logging
import signal
from concurrent import futures
from dataclasses import dataclass

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from volcano.db.session import SessionLocal
from volcano.engine.alert_feed import AlertFeed
from volcano.engine.interceptors import LoggingInterceptor, TokenInterceptor
from volcano.engine.model_cache import ModelCache
from volcano.engine.servicer import Metrics, PredictionEngineServicer, register
from volcano.engine.startup import train_if_needed
from volcano.rpc import engine_pb2 as pb
from volcano.shared.config import settings
from volcano.shared.log_config import configure_logging

logger = logging.getLogger("volcano.engine")
SERVICE_NAME = pb.DESCRIPTOR.services_by_name["PredictionEngine"].full_name
MB = 1024 * 1024


@dataclass
class Engine:
    server: grpc.Server
    port: int
    servicer: PredictionEngineServicer

    def start(self) -> "Engine":
        self.server.start()
        return self

    def stop(self, grace: float | None = 5) -> None:
        self.servicer.feed.stop()
        self.server.stop(grace=grace).wait()


def build_server(address: str | None = None, servicer: PredictionEngineServicer | None = None,
                 token: str | None = None, threads: int | None = None) -> Engine:
    """Build the server without starting it. With the address '127.0.0.1:0' the OS picks a free port
    (tests use it); the assigned port ends up in `Engine.port`."""
    threads = threads or settings.ENGINE_GRPC_THREADS
    servicer = servicer or PredictionEngineServicer(
        cache=ModelCache(ttl_s=settings.ENGINE_CACHE_TTL_S),
        feed=AlertFeed(SessionLocal, interval_s=settings.ENGINE_ALERT_POLL_S),
        metrics=Metrics())
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=threads, thread_name_prefix="engine"),
        interceptors=[LoggingInterceptor(servicer.metrics), TokenInterceptor(token or settings.INTERNAL_TOKEN)],
        # Every open stream holds a thread: above the limit the server answers RESOURCE_EXHAUSTED
        # instead of leaving requests hanging.
        maximum_concurrent_rpcs=threads,
        options=[
            ("grpc.max_receive_message_length", 8 * MB),
            ("grpc.keepalive_time_ms", 30_000),          # pings long-lived streams (alerts)
            ("grpc.keepalive_timeout_ms", 10_000),
            ("grpc.http2.min_ping_interval_without_data_ms", 10_000),
        ])
    register(server, servicer)

    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    for name in ("", SERVICE_NAME):
        health_servicer.set(name, health_pb2.HealthCheckResponse.SERVING)
    reflection.enable_server_reflection((SERVICE_NAME, reflection.SERVICE_NAME, health.SERVICE_NAME), server)

    port = server.add_insecure_port(address or settings.ENGINE_GRPC_ADDRESS)
    return Engine(server, port, servicer)


def main() -> None:
    configure_logging("engine")
    engine = build_server().start()
    logger.info("gRPC prediction engine listening on %s", settings.ENGINE_GRPC_ADDRESS)
    if settings.TRAIN_ON_STARTUP:
        train_if_needed(on_done=engine.servicer.after_training)

    def shutdown(signum, _frame):
        logger.info("Signal %s: closing the engine (5 s grace for open streams)", signum)
        engine.servicer.feed.stop()
        engine.server.stop(grace=5)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    engine.server.wait_for_termination()


if __name__ == "__main__":
    main()
