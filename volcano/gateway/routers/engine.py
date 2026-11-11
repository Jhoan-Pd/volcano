"""REST ↔ gRPC bridge of the gateway: what the browser reaches over plain HTTP.

    RPC type           Endpoint                         Transport to the browser
    Unary              GET  /engine/status, /forecast   JSON
    Server streaming   POST /engine/training            SSE (fetch + ReadableStream; carries the token)
    Client streaming   POST /engine/pharmacy-upload     JSON → stream of rows to the engine

The WebSocket transports (live alerts and the bidirectional simulator) live in the realtime hub.
"""
import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from volcano.gateway.deps import admin_only, pharmacy_or_admin
from volcano.models import User
from volcano.rpc.client import EngineClient, engine_client
from volcano.schemas.engine import EngineForecast, EngineStatusOut, PharmacyUploadIn, UploadSummaryOut
from volcano.shared.errors import AppError

router = APIRouter(prefix="/engine", tags=["Prediction engine (gRPC)"])

KEEPALIVE_S = 15.0  # periodic SSE comment so proxies and Render do not cut a silent stream
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


# ── SSE ──────────────────────────────────────────────────────────────────────
def sse_event(data: BaseModel | dict, event: str | None = None) -> str:
    body = data.model_dump_json() if isinstance(data, BaseModel) else json.dumps(data, ensure_ascii=False)
    return (f"event: {event}\n" if event else "") + f"data: {body}\n\n"


async def sse_stream(source: AsyncIterator[BaseModel], event_name: Callable[[BaseModel], str]) -> AsyncIterator[str]:
    """Turn a gRPC stream into SSE events. When the engine fails a `failure` event is sent (not `error`,
    which is EventSource's native connection event). After KEEPALIVE_S without messages it sends a
    comment (`: keepalive`) without cancelling the pending read of the stream."""
    yield "retry: 5000\n\n"  # the browser retries after 5 s when the connection drops
    pending = asyncio.ensure_future(anext(source))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=KEEPALIVE_S)
            if not done:
                yield ": keepalive\n\n"
                continue
            try:
                item = pending.result()
            except StopAsyncIteration:
                break
            except AppError as exc:
                yield sse_event({"message": exc.message, "code": exc.code}, "failure")
                break
            yield sse_event(item, event_name(item))
            pending = asyncio.ensure_future(anext(source))
    finally:
        pending.cancel()
        with contextlib.suppress(Exception):
            await source.aclose()


def sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)


# ── unary ────────────────────────────────────────────────────────────────────
@router.get("/status", response_model=EngineStatusOut, summary="gRPC engine status (unary)")
async def engine_status(engine: EngineClient = Depends(engine_client)):
    """Never fails: when the engine is down it answers `available: false`."""
    return await engine.status()


@router.get("/forecast", response_model=EngineForecast, summary="Forecast computed right now (unary)")
async def forecast(municipality_id: int, disease_id: int, engine: EngineClient = Depends(engine_client)):
    """Unlike `/dashboard/prediction` (which reads what is stored), this asks the engine to apply the
    model it holds in memory right now."""
    return await engine.predict(municipality_id, disease_id)


# ── server streaming → SSE ───────────────────────────────────────────────────
@router.post("/training", dependencies=[Depends(admin_only)], response_class=StreamingResponse,
             summary="Retrain and watch the progress live (server streaming → SSE) — ADMIN only",
             responses={200: {"content": {"text/event-stream": {}}}, 409: {"description": "One is already running"}})
async def training(disease_id: int | None = Query(None, description="Empty = every disease"),
                   engine: EngineClient = Depends(engine_client)):
    steps = await engine.train(disease_id)  # 409/503 are answered here, before the stream opens
    return sse_response(sse_stream(steps, lambda _: "progress"))


# ── client streaming ─────────────────────────────────────────────────────────
@router.post("/pharmacy-upload", response_model=UploadSummaryOut, status_code=status.HTTP_200_OK,
             summary="Bulk upload of pharmacy reports (client streaming)")
async def pharmacy_upload(payload: PharmacyUploadIn, user: User = Depends(pharmacy_or_admin),
                          engine: EngineClient = Depends(engine_client)):
    """The rows (already checked in the browser by a Web Worker) travel to the engine as a stream: it
    validates each one on arrival, groups them by week and applies the same rules as the weekly form
    (a PHARMACY user only uploads the last 8 weeks of its own pharmacy)."""
    return await engine.upload_pharmacy_reports(payload.rows, user.id)
