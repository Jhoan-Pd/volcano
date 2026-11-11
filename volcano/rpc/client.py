"""gRPC clients of the prediction engine, shared by the gateway and the realtime hub.

`EngineClient` uses `grpc.aio` because FastAPI is asynchronous: while it waits for the engine (or
the next message of a stream) the event loop keeps serving other requests. A gRPC channel is bound
to the event loop that created it; production has one loop, but tests (TestClient) open one per
request, so one channel is kept per loop.

`EngineSyncClient` covers the two unary calls the daily job makes from a worker thread.
"""
import asyncio
import time
import weakref
from collections.abc import AsyncIterator, Iterable
from functools import lru_cache

import grpc

from volcano.rpc import engine_pb2 as pb
from volcano.rpc import engine_pb2_grpc as rpc
from volcano.rpc.conversion import (
    alert_event_from_pb,
    level_from_pb,
    point_from_pb,
    progress_from_pb,
    training_status_from_pb,
)
from volcano.rpc.errors import from_rpc_error
from volcano.schemas.engine import (
    AlertEventOut,
    EngineForecast,
    EngineStatusOut,
    RefreshResultOut,
    ScenarioIn,
    TrainingProgressOut,
    UploadRowIn,
    UploadSummaryOut,
)
from volcano.schemas.model import TrainingStatus
from volcano.shared.config import settings

ACTOR_METADATA = "x-actor-id"
CHANNEL_OPTIONS = [("grpc.keepalive_time_ms", 30_000), ("grpc.keepalive_permit_without_calls", 1)]


def forecast_from_pb(p: pb.Forecast) -> EngineForecast:
    return EngineForecast(
        municipality_id=p.municipality_id, municipality=p.municipality, disease_id=p.disease_id, disease=p.disease,
        algorithm=p.algorithm, model_id=p.model_id, base_week=p.base_week, max_level=level_from_pb(p.max_level),
        points=[point_from_pb(x) for x in p.points], duration_ms=p.duration_ms, from_cache=p.from_cache)


def scenario_to_pb(s: ScenarioIn) -> pb.Scenario:
    return pb.Scenario(**s.model_dump())


def refresh_from_pb(r: pb.RefreshResult) -> RefreshResultOut:
    return RefreshResultOut(predictions=r.predictions, alerts_new=r.alerts_new, alerts_updated=r.alerts_updated,
                            alerts_closed=r.alerts_closed, alerts_active=r.alerts_active, emails_sent=r.emails_sent)


def _ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000, 2)


class EngineClient:
    def __init__(self, address: str, token: str, timeout_s: float = 15.0):
        self.address = address
        self.timeout_s = timeout_s
        self._metadata = (("authorization", f"Bearer {token}"),)
        self._channels: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, grpc.aio.Channel] = \
            weakref.WeakKeyDictionary()

    def _stub(self) -> rpc.PredictionEngineStub:
        loop = asyncio.get_running_loop()
        channel = self._channels.get(loop)
        if channel is None:
            channel = grpc.aio.insecure_channel(self.address, options=CHANNEL_OPTIONS)
            self._channels[loop] = channel
        return rpc.PredictionEngineStub(channel)

    def _meta(self, *extra: tuple[str, str]) -> tuple[tuple[str, str], ...]:
        return (*self._metadata, *extra)

    async def close(self) -> None:
        channel = self._channels.pop(asyncio.get_running_loop(), None)
        if channel is not None:
            await channel.close()

    # ── unary ────────────────────────────────────────────────────────────────
    async def status(self) -> EngineStatusOut:
        """Never fails: when the engine is down it answers `available: false`."""
        start = time.perf_counter()
        try:
            s = await self._stub().GetStatus(pb.Empty(), metadata=self._meta(), timeout=min(self.timeout_s, 5))
        except grpc.RpcError as exc:
            return EngineStatusOut(available=False, message=from_rpc_error(exc).message)
        return EngineStatusOut(available=True, version=s.version, models_in_memory=s.models_in_memory,
                               training=s.training, uptime_s=s.uptime_s, rpcs_served=s.rpcs_served,
                               latency_ms=_ms(start))

    async def predict(self, municipality_id: int, disease_id: int) -> EngineForecast:
        try:
            p = await self._stub().Predict(pb.ForecastRequest(municipality_id=municipality_id, disease_id=disease_id),
                                           metadata=self._meta(), timeout=self.timeout_s)
        except grpc.RpcError as exc:
            raise from_rpc_error(exc) from None
        return forecast_from_pb(p)

    async def start_training(self, disease_id: int | None = None) -> TrainingStatus:
        try:
            s = await self._stub().StartTraining(pb.TrainingRequest(disease_id=disease_id), metadata=self._meta(),
                                                 timeout=self.timeout_s)
        except grpc.RpcError as exc:
            raise from_rpc_error(exc) from None
        return TrainingStatus(**training_status_from_pb(s))

    async def training_status(self) -> TrainingStatus:
        try:
            s = await self._stub().GetTrainingStatus(pb.Empty(), metadata=self._meta(), timeout=self.timeout_s)
        except grpc.RpcError as exc:
            raise from_rpc_error(exc) from None
        return TrainingStatus(**training_status_from_pb(s))

    async def refresh_forecasts(self, evaluate_alerts: bool = False, send_email: bool = False) -> RefreshResultOut:
        try:
            r = await self._stub().RefreshForecasts(
                pb.RefreshRequest(evaluate_alerts=evaluate_alerts, send_email=send_email),
                metadata=self._meta(), timeout=self.timeout_s * 8)
        except grpc.RpcError as exc:
            raise from_rpc_error(exc) from None
        return refresh_from_pb(r)

    # ── server streaming ─────────────────────────────────────────────────────
    async def train(self, disease_id: int | None = None) -> AsyncIterator[TrainingProgressOut]:
        """Reads the first message before returning the iterator: a 409 (one already running) then
        arrives as a normal HTTP response instead of halfway through an open SSE stream."""
        call = self._stub().Train(pb.TrainingRequest(disease_id=disease_id), metadata=self._meta())  # no deadline
        try:
            first = await call.read()
        except grpc.RpcError as exc:
            raise from_rpc_error(exc) from None

        async def rest() -> AsyncIterator[TrainingProgressOut]:
            # read() was already used: gRPC does not allow mixing it with `async for` on one call
            msg = first
            try:
                while msg is not grpc.aio.EOF:
                    yield TrainingProgressOut(**progress_from_pb(msg))
                    msg = await call.read()
            except grpc.RpcError as exc:
                raise from_rpc_error(exc) from None
            finally:
                call.cancel()  # the browser left: release the stream (training goes on)
        return rest()

    async def watch_alerts(self, municipality_id: int | None = None) -> AsyncIterator[AlertEventOut]:
        call = self._stub().WatchAlerts(pb.AlertFilter(municipality_id=municipality_id), metadata=self._meta())
        try:
            async for event in call:
                yield AlertEventOut(**alert_event_from_pb(event))
        except grpc.RpcError as exc:
            if exc.code() != grpc.StatusCode.CANCELLED:
                raise from_rpc_error(exc) from None
        finally:
            call.cancel()

    # ── client streaming ─────────────────────────────────────────────────────
    async def upload_pharmacy_reports(self, rows: Iterable[UploadRowIn], actor_id: int) -> UploadSummaryOut:
        async def messages() -> AsyncIterator[pb.PharmacyReportRow]:
            for r in rows:
                yield pb.PharmacyReportRow(**r.model_dump())

        start = time.perf_counter()
        try:
            r = await self._stub().UploadPharmacyReports(
                messages(), metadata=self._meta((ACTOR_METADATA, str(actor_id))), timeout=self.timeout_s * 8)
        except grpc.RpcError as exc:
            raise from_rpc_error(exc) from None
        return UploadSummaryOut(
            rows_received=r.rows_received, rows_rejected=r.rows_rejected, weeks_created=r.weeks_created,
            weeks_updated=r.weeks_updated, weeks_rejected=r.weeks_rejected,
            errors=[{"row": e.row, "message": e.message} for e in r.errors], duration_ms=_ms(start))

    # ── bidirectional ────────────────────────────────────────────────────────
    def simulate(self) -> grpc.aio.StreamStreamCall:
        """Open the conversation; the caller writes scenarios with `write()` and reads results."""
        return self._stub().SimulateScenarios(metadata=self._meta())


@lru_cache
def engine_client() -> EngineClient:
    """FastAPI dependency: one instance per process (tests swap it for a client of their own
    server through `app.dependency_overrides`)."""
    return EngineClient(settings.ENGINE_GRPC_ADDRESS, settings.INTERNAL_TOKEN, settings.ENGINE_GRPC_TIMEOUT_S)


class EngineSyncClient:
    """Blocking client for the daily job, which runs in a worker thread."""

    def __init__(self, address: str | None = None, token: str | None = None, timeout_s: float | None = None):
        self.address = address or settings.ENGINE_GRPC_ADDRESS
        self.timeout_s = timeout_s or settings.ENGINE_GRPC_TIMEOUT_S
        self._metadata = (("authorization", f"Bearer {token or settings.INTERNAL_TOKEN}"),)

    def refresh_forecasts(self, evaluate_alerts: bool = True, send_email: bool = True) -> RefreshResultOut:
        with grpc.insecure_channel(self.address) as channel:
            try:
                r = rpc.PredictionEngineStub(channel).RefreshForecasts(
                    pb.RefreshRequest(evaluate_alerts=evaluate_alerts, send_email=send_email),
                    metadata=self._metadata, timeout=self.timeout_s * 8)
            except grpc.RpcError as exc:
                raise from_rpc_error(exc) from None
        return refresh_from_pb(r)

    def start_training(self, disease_id: int | None = None) -> TrainingStatus:
        with grpc.insecure_channel(self.address) as channel:
            try:
                s = rpc.PredictionEngineStub(channel).StartTraining(
                    pb.TrainingRequest(disease_id=disease_id), metadata=self._metadata, timeout=self.timeout_s)
            except grpc.RpcError as exc:
                raise from_rpc_error(exc) from None
        return TrainingStatus(**training_status_from_pb(s))
