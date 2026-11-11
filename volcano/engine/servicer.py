"""Implementation of the `PredictionEngine` gRPC service (see proto/volcano/engine/v1/engine.proto).

Every method reuses the domain services (ForecastingService, PharmacyReportService, retrain…): the
engine changes the transport and how results are delivered (streams), not the business rules.

Dependencies are injected in the constructor (session factory, cache, alert feed) so tests can run
the server against the test database.
"""
import logging
import queue
import threading
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import grpc
from pydantic import ValidationError

from volcano import __version__
from volcano.db.session import SessionLocal
from volcano.engine.alert_feed import AlertFeed
from volcano.engine.model_cache import ModelCache
from volcano.ml.progress import ProgressEvent, Stage
from volcano.ml.scenarios import Adjustments, apply
from volcano.models import User
from volcano.models.enums import RiskLevel
from volcano.rpc import engine_pb2 as pb
from volcano.rpc import engine_pb2_grpc as rpc
from volcano.rpc.client import ACTOR_METADATA
from volcano.rpc.conversion import level_to_pb, point_to_pb, progress_to_pb
from volcano.rpc.errors import abort_on_domain_errors
from volcano.schemas.model import TrainingStatus
from volcano.schemas.pharmacy import ReportItem
from volcano.services.alerts import AlertService
from volcano.services.forecasting import ForecastingService
from volcano.services.pharmacy_reports import PharmacyReportService
from volcano.services.training import control, retrain, start_in_thread
from volcano.shared.epi import label, weeks_in_year
from volcano.shared.errors import BusinessRuleError, NotFoundError, PermissionDeniedError
from volcano.shared.text import format_number_es

logger = logging.getLogger("volcano.engine")
MAX_REPORTED_ERRORS = 100
TRAINING_DONE = {Stage.FINISHED, Stage.FAILED}


class Metrics:
    """Counter of served RPCs; the logging interceptor increments it."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self._rpcs = 0
        self._lock = threading.Lock()

    def count(self) -> None:
        with self._lock:
            self._rpcs += 1

    @property
    def rpcs(self) -> int:
        return self._rpcs


def _ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000, 2)


def training_status_to_pb(s: TrainingStatus) -> pb.TrainingStatus:
    return pb.TrainingStatus(running=s.running, message=s.message or "", errors=s.errors,
                             started_at=s.started_at.isoformat() if s.started_at else "",
                             finished_at=s.finished_at.isoformat() if s.finished_at else "")


class PredictionEngineServicer(rpc.PredictionEngineServicer):
    def __init__(self, sessions: Callable = SessionLocal, cache: ModelCache | None = None,
                 feed: AlertFeed | None = None, metrics: Metrics | None = None):
        self.sessions = sessions
        self.cache = cache or ModelCache()
        self.feed = feed or AlertFeed(sessions)
        self.metrics = metrics or Metrics()

    def after_training(self) -> None:
        """Called when a background training run ends: drop stale models and push alert changes."""
        self.cache.invalidate()
        self.feed.check_soon()

    # ── unary ────────────────────────────────────────────────────────────────
    def GetStatus(self, request, context):
        return pb.EngineStatus(version=__version__, models_in_memory=len(self.cache),
                               training=control.status().running,
                               uptime_s=round(time.monotonic() - self.metrics.started, 1),
                               rpcs_served=self.metrics.rpcs)

    def Predict(self, request, context):
        start = time.perf_counter()
        with abort_on_domain_errors(context), self.sessions() as db:
            loaded, from_cache = self.cache.get(db, request.disease_id)
            f = loaded.forecaster
            if not f.has(request.municipality_id):
                raise NotFoundError(f"No hay datos del municipio {request.municipality_id} para esta enfermedad")
            points = f.forecast(request.municipality_id)
            return pb.Forecast(
                municipality_id=request.municipality_id, municipality=loaded.municipalities[request.municipality_id],
                disease_id=request.disease_id, disease=loaded.disease, algorithm=loaded.algorithm,
                model_id=loaded.model_id, base_week=label(*f.base_week(request.municipality_id)),
                max_level=level_to_pb(RiskLevel.worst(p.level for p in points)),
                points=[point_to_pb(p) for p in points], duration_ms=_ms(start), from_cache=from_cache)

    def RefreshForecasts(self, request, context):
        with abort_on_domain_errors(context), self.sessions() as db:
            predictions = ForecastingService(db).predict_all()
            result = pb.RefreshResult(predictions=predictions)
            if request.evaluate_alerts:
                r = AlertService(db).evaluate(send_email=request.send_email)
                result.alerts_new, result.alerts_updated, result.alerts_closed = r.new, r.updated, r.closed
                result.alerts_active, result.emails_sent = r.active, r.emails_sent
        self.cache.invalidate()
        self.feed.check_soon()
        return result

    def StartTraining(self, request, context):
        disease_id = request.disease_id if request.HasField("disease_id") else None
        with abort_on_domain_errors(context):
            status = start_in_thread(disease_id, name="training-rpc", on_done=self.after_training)
        return training_status_to_pb(status)

    def GetTrainingStatus(self, request, context):
        return training_status_to_pb(control.status())

    # ── server streaming ─────────────────────────────────────────────────────
    def Train(self, request, context) -> Iterator[pb.TrainingProgress]:
        """Training runs in its own thread and drops every step into a queue; this generator drains
        it into the stream. If the client disconnects, training keeps going until it finishes."""
        with abort_on_domain_errors(context):
            control.start()  # ConflictError → ABORTED when one is already running
        disease_id = request.disease_id if request.HasField("disease_id") else None
        events: queue.Queue[ProgressEvent] = queue.Queue()
        threading.Thread(target=retrain, kwargs={"disease_id": disease_id, "progress": events.put,
                                                 "on_done": self.after_training},
                         daemon=True, name="training-stream").start()
        while context.is_active():
            try:
                e = events.get(timeout=1.0)
            except queue.Empty:
                continue
            yield progress_to_pb(e)
            if e.stage in TRAINING_DONE:
                return

    def WatchAlerts(self, request, context) -> Iterator[pb.AlertEvent]:
        municipality_id = request.municipality_id if request.HasField("municipality_id") else None
        sub, initial = self.feed.subscribe(municipality_id)
        try:
            yield from initial
            yield pb.AlertEvent(kind=pb.AlertEvent.Kind.KIND_SYNCED, at=datetime.now(UTC).isoformat())
            while context.is_active():
                try:
                    yield sub.events.get(timeout=1.0)
                except queue.Empty:
                    continue
        finally:
            self.feed.unsubscribe(sub)

    # ── client streaming ─────────────────────────────────────────────────────
    def _actor(self, db, context) -> User:
        value = dict(context.invocation_metadata()).get(ACTOR_METADATA, "")
        user = db.get(User, int(value)) if value.isdigit() else None
        if user is None or not user.active:
            raise PermissionDeniedError(f"Falta el usuario que hace la carga (metadato {ACTOR_METADATA})")
        return user

    @staticmethod
    def _parse_row(r: pb.PharmacyReportRow) -> ReportItem:
        if not 1 <= r.epi_week <= weeks_in_year(r.year):
            raise ValueError(f"La semana {r.epi_week} no existe en {r.year}")
        return ReportItem(category=r.category, units=r.units)

    def UploadPharmacyReports(self, request_iterator, context):
        """Each row is validated as soon as it arrives (the error is reported with its line number) and
        the valid ones are grouped by pharmacy and week. When the stream closes each week is saved."""
        summary = pb.UploadSummary()
        weeks: dict[tuple[int | None, int, int], dict[str, ReportItem]] = defaultdict(dict)
        first_row: dict[tuple[int | None, int, int], int] = {}

        def error(row: int, message: str) -> None:
            if len(summary.errors) < MAX_REPORTED_ERRORS:
                summary.errors.append(pb.RowError(row=row, message=message))

        with abort_on_domain_errors(context), self.sessions() as db:
            service = PharmacyReportService(db, self._actor(db, context))
            for r in request_iterator:
                summary.rows_received += 1
                try:
                    item = self._parse_row(r)
                except (ValueError, ValidationError) as exc:
                    summary.rows_rejected += 1
                    error(r.row, exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc))
                    continue
                key = (r.pharmacy_id if r.HasField("pharmacy_id") else None, r.year, r.epi_week)
                if item.category.value in weeks[key]:
                    summary.rows_rejected += 1
                    error(r.row, f"{item.category.value} se repite en la semana {label(r.year, r.epi_week)}")
                    continue
                weeks[key][item.category.value] = item
                first_row.setdefault(key, r.row)

            for key, items in sorted(weeks.items(), key=lambda x: first_row[x[0]]):
                pharmacy_id, year, week = key
                try:
                    created = service.save_week(year, week, list(items.values()), pharmacy_id)
                except (BusinessRuleError, PermissionDeniedError, NotFoundError) as exc:
                    db.rollback()
                    summary.weeks_rejected += 1
                    error(first_row[key], f"Semana {label(year, week)}: {exc.message}")
                    continue
                if created:
                    summary.weeks_created += 1
                else:
                    summary.weeks_updated += 1
        logger.info("Pharmacy upload: %d rows, %d new weeks, %d updated, %d rejected", summary.rows_received,
                    summary.weeks_created, summary.weeks_updated, summary.weeks_rejected)
        return summary

    # ── bidirectional ────────────────────────────────────────────────────────
    def SimulateScenarios(self, request_iterator, context) -> Iterator[pb.ScenarioResult]:
        """A stateful conversation: the baseline forecast of each municipality/disease is computed once per
        stream; later scenarios only pay for the modified prediction."""
        baselines: dict[tuple[int, int, int], list] = {}
        with self.sessions() as db:
            for s in request_iterator:
                start = time.perf_counter()
                try:
                    yield self._simulate(db, s, baselines, start)
                except (NotFoundError, BusinessRuleError) as exc:
                    yield pb.ScenarioResult(id=s.id, municipality_id=s.municipality_id, disease_id=s.disease_id,
                                            error=exc.message, duration_ms=_ms(start))

    def _simulate(self, db, s: pb.Scenario, baselines: dict, start: float) -> pb.ScenarioResult:
        adjustments = Adjustments(s.temperature_delta_c, s.rain_change_pct, s.search_change_pct,
                                  s.pharmacy_change_pct, s.ash_fall)
        if errors := adjustments.errors():
            raise BusinessRuleError("; ".join(errors))
        loaded, _ = self.cache.get(db, s.disease_id)
        f = loaded.forecaster
        if not f.has(s.municipality_id):
            raise NotFoundError(f"No hay datos del municipio {s.municipality_id} para esta enfermedad")
        key = (s.municipality_id, s.disease_id, loaded.model_id)
        if key not in baselines:
            baselines[key] = f.forecast(s.municipality_id)
        baseline = baselines[key]
        X = apply(f.inputs(s.municipality_id), adjustments, f.typical(s.municipality_id))
        scenario = baseline if adjustments.unchanged else f.forecast(s.municipality_id, X)

        base_total = sum(p.expected_cases for p in baseline)
        scenario_total = sum(p.expected_cases for p in scenario)
        change = (scenario_total / base_total - 1) * 100 if base_total else (100.0 if scenario_total else 0.0)
        worst = RiskLevel.worst(p.level for p in scenario)
        municipality, disease = loaded.municipalities[s.municipality_id], loaded.disease.lower()
        if adjustments.unchanged:
            summary = (f"Sin cambios, en {municipality} se esperan {format_number_es(scenario_total)} casos de "
                       f"{disease} en las próximas 4 semanas. Nivel máximo: {worst.label_es.lower()}.")
        else:
            summary = (f"Con {adjustments.describe_es()}, en {municipality} se esperarían "
                       f"{format_number_es(scenario_total)} casos de {disease} en 4 semanas ({change:+.0f} % "
                       f"frente a {format_number_es(base_total)}). Nivel máximo: {worst.label_es.lower()}.")
        return pb.ScenarioResult(
            id=s.id, municipality_id=s.municipality_id, disease_id=s.disease_id,
            baseline=[point_to_pb(p) for p in baseline], scenario=[point_to_pb(p) for p in scenario],
            max_level=level_to_pb(worst), change_pct=round(change, 1), summary=summary, duration_ms=_ms(start))


def register(server: grpc.Server, servicer: PredictionEngineServicer) -> None:
    rpc.add_PredictionEngineServicer_to_server(servicer, server)
