"""Per-client simulator session: a WebSocket conversation bridged to the bidirectional gRPC stream.

The stream opens lazily with the client's first scenario and stays open while the socket lives, so
the engine keeps that conversation's baseline forecasts warm and every later scenario only pays for
the modified prediction. Results flow back as soon as the engine computes them, through the client's
own outbound queue.
"""
import asyncio
import contextlib
import logging

import grpc

from volcano.realtime.hub import Client
from volcano.realtime.protocol import error, message
from volcano.rpc.client import EngineClient, scenario_to_pb
from volcano.rpc.conversion import scenario_result_from_pb
from volcano.rpc.errors import from_rpc_error
from volcano.schemas.engine import ScenarioIn

logger = logging.getLogger("volcano.realtime.simulation")


class SimulationSession:
    def __init__(self, client: Client, engine: EngineClient):
        self.client = client
        self.engine = engine
        self._call: grpc.aio.StreamStreamCall | None = None
        self._reader: asyncio.Task | None = None

    @property
    def open(self) -> bool:
        return self._call is not None and not self._call.done()

    async def submit(self, scenario: ScenarioIn) -> None:
        if not self.open:
            self._call = self.engine.simulate()
            self._reader = asyncio.create_task(self._read(self._call), name=f"simulation-{self.client.id}")
        try:
            await self._call.write(scenario_to_pb(scenario))
        except (grpc.RpcError, asyncio.InvalidStateError) as exc:
            logger.info("Simulation stream of %s broke on write: %s", self.client.id, exc)
            await self.close()
            self.client.send(error("ENGINE_UNAVAILABLE", "El simulador no está disponible; intenta de nuevo."))

    async def _read(self, call: grpc.aio.StreamStreamCall) -> None:
        try:
            async for result in call:
                self.client.send(message("simulation.result", result=scenario_result_from_pb(result)))
        except grpc.RpcError as exc:
            if exc.code() != grpc.StatusCode.CANCELLED:
                failure = from_rpc_error(exc)
                self.client.send(error(failure.code, failure.message))

    async def close(self) -> None:
        call, reader, self._call, self._reader = self._call, self._reader, None, None
        if call is not None:
            with contextlib.suppress(Exception):
                await call.done_writing()
            call.cancel()
        if reader is not None:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await reader
