"""gRPC prediction engine: every RPC type against a real server on a free port."""
import time

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from tests.conftest import ENGINE_TOKEN
from volcano.ml.scenarios import Adjustments, apply
from volcano.models import Alert, Disease, Municipality, Pharmacy, PharmacyReport, Prediction, User
from volcano.rpc import engine_pb2 as pb
from volcano.services.training import control

META = (("authorization", f"Bearer {ENGINE_TOKEN}"),)


def _pasto(db) -> int:
    return db.query(Municipality).filter_by(divipola_code="52001").one().id


# ── security and health ──────────────────────────────────────────────────────
def test_without_a_token_it_answers_unauthenticated(stub):
    for metadata in (None, (("authorization", "Bearer other"),)):
        with pytest.raises(grpc.RpcError) as exc:
            stub.GetStatus(pb.Empty(), metadata=metadata)
        assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_standard_health_check_needs_no_token(grpc_engine):
    with grpc.insecure_channel(f"127.0.0.1:{grpc_engine.port}") as channel:
        r = health_pb2_grpc.HealthStub(channel).Check(
            health_pb2.HealthCheckRequest(service="volcano.engine.v1.PredictionEngine"))
    assert r.status == health_pb2.HealthCheckResponse.SERVING


# ── unary ────────────────────────────────────────────────────────────────────
def test_status(stub):
    s = stub.GetStatus(pb.Empty(), metadata=META)
    assert s.version and s.uptime_s >= 0 and s.rpcs_served >= 1 and not s.training


def test_predict_matches_the_stored_predictions_and_uses_the_cache(stub, db, trained_ira):
    pasto = _pasto(db)
    p = stub.Predict(pb.ForecastRequest(municipality_id=pasto, disease_id=trained_ira), metadata=META)
    assert [x.horizon for x in p.points] == [1, 2, 3, 4]
    assert p.municipality == "Pasto" and p.algorithm and p.base_week
    for x in p.points:
        assert x.lower_bound <= x.expected_cases <= x.upper_bound
        assert x.level != pb.RISK_LEVEL_UNSPECIFIED

    # Same computation as the service that stores the predictions (shared Forecaster)
    stored = {s.horizon: s.expected_cases for s in db.query(Prediction).filter_by(model_id=p.model_id,
                                                                                    municipality_id=pasto)}
    assert {x.horizon: x.expected_cases for x in p.points} == stored

    again = stub.Predict(pb.ForecastRequest(municipality_id=pasto, disease_id=trained_ira), metadata=META)
    assert again.from_cache and again.duration_ms < p.duration_ms + 50


def test_predict_without_model_or_municipality_is_not_found(stub, db, trained_ira):
    no_model = db.query(Disease).filter_by(code="RESP_CENIZA").one().id
    with pytest.raises(grpc.RpcError) as exc:
        stub.Predict(pb.ForecastRequest(municipality_id=1, disease_id=no_model), metadata=META)
    assert exc.value.code() == grpc.StatusCode.NOT_FOUND and "modelo" in exc.value.details()
    with pytest.raises(grpc.RpcError) as exc:
        stub.Predict(pb.ForecastRequest(municipality_id=9999, disease_id=trained_ira), metadata=META)
    assert exc.value.code() == grpc.StatusCode.NOT_FOUND


def test_refresh_forecasts_regenerates_predictions(stub, trained_ira):
    r = stub.RefreshForecasts(pb.RefreshRequest(evaluate_alerts=True, send_email=False), metadata=META)
    assert r.predictions >= 8 and r.emails_sent == 0


def test_training_status_and_start_training_conflict(stub, trained_ira):
    control.reset()
    control.start()  # pretend a run is in progress
    try:
        assert stub.GetTrainingStatus(pb.Empty(), metadata=META).running
        with pytest.raises(grpc.RpcError) as exc:
            stub.StartTraining(pb.TrainingRequest(disease_id=trained_ira), metadata=META)
        assert exc.value.code() == grpc.StatusCode.ABORTED
    finally:
        control.reset()


# ── bidirectional ────────────────────────────────────────────────────────────
def test_applying_a_scenario_does_not_modify_the_input():
    import pandas as pd

    X = pd.DataFrame([{"temp_l0": 14.0, "temp_l2": None, "temp_l4_6": 13.0, "rain_l0": 10.0, "rain_l1": 5.0,
                       "rain_l2_6": 8.0, "search_l0": 50.0, "search_change": 1.0, "pharm_l0": None, "ash_l0_1": 0.0}])
    typical = {"temp_l2": 15.0, "pharm_l0": 100.0}
    X2 = apply(X, Adjustments(temperature_delta_c=2, rain_change_pct=50, pharmacy_change_pct=20, ash_fall=True),
               typical)
    assert X.loc[0, "temp_l0"] == 14.0 and pd.isna(X.loc[0, "pharm_l0"])  # the original stays the same
    assert X2.loc[0, "temp_l0"] == 16.0 and X2.loc[0, "temp_l2"] == 17.0  # empty → typical + 2
    assert X2.loc[0, "rain_l0"] == 15.0 and X2.loc[0, "pharm_l0"] == 120.0 and X2.loc[0, "ash_l0_1"] == 2
    assert X2.loc[0, "search_l0"] == 50.0  # what was not asked for does not change
    assert Adjustments(temperature_delta_c=9).errors() and not Adjustments(rain_change_pct=-100).errors()


def test_simulating_scenarios_is_a_conversation(stub, db, trained_ira):
    pasto = _pasto(db)
    sent = [
        pb.Scenario(id="base", municipality_id=pasto, disease_id=trained_ira),
        pb.Scenario(id="more-searches", municipality_id=pasto, disease_id=trained_ira, search_change_pct=200,
                    rain_change_pct=100, temperature_delta_c=3),
        pb.Scenario(id="invalid", municipality_id=pasto, disease_id=trained_ira, temperature_delta_c=40),
        pb.Scenario(id="no-data", municipality_id=9999, disease_id=trained_ira),
        pb.Scenario(id="again", municipality_id=pasto, disease_id=trained_ira, ash_fall=True),
    ]
    answers = list(stub.SimulateScenarios(iter(sent), metadata=META))

    assert [a.id for a in answers] == [s.id for s in sent]  # one answer per scenario, in order
    base, changed, invalid, no_data, last = answers
    assert not base.error and base.change_pct == 0
    assert [p.expected_cases for p in base.scenario] == [p.expected_cases for p in base.baseline]
    assert not changed.error and len(changed.scenario) == 4 and "°C" in changed.summary
    assert [p.expected_cases for p in changed.baseline] == [p.expected_cases for p in base.baseline]
    assert "temperature_delta_c" in invalid.error and not invalid.scenario  # the stream stays alive
    assert no_data.error and not last.error and "ceniza" in last.summary


# ── server streaming ─────────────────────────────────────────────────────────
def test_train_streams_progress_and_refuses_two_runs(stub, trained_ira):
    control.reset()
    stream = stub.Train(pb.TrainingRequest(disease_id=trained_ira), metadata=META)
    first = next(stream)
    assert first.stage == pb.TrainingProgress.STAGE_STARTED

    with pytest.raises(grpc.RpcError) as exc:  # while it runs, a second request is refused
        next(stub.Train(pb.TrainingRequest(disease_id=trained_ira), metadata=META))
    assert exc.value.code() == grpc.StatusCode.ABORTED

    rest = list(stream)
    stages = [pb.TrainingProgress.Stage.Name(m.stage) for m in [first, *rest]]
    percents = [m.percent for m in [first, *rest]]
    assert stages[-1] == "STAGE_FINISHED"
    assert {"STAGE_DATASET", "STAGE_CANDIDATE", "STAGE_MODEL_READY", "STAGE_ALERTS"} <= set(stages)
    assert percents == sorted(percents) and percents[-1] == 100
    assert any(m.HasField("baseline_mae") for m in rest)
    assert not control.status().running


def test_watch_alerts_sends_the_active_ones_a_marker_and_then_the_changes(stub, db, trained_ira):
    consaca = db.query(Municipality).filter_by(divipola_code="52207").one().id

    def alert(week: int, level: str = "ORANGE") -> Alert:
        a = Alert(municipality_id=consaca, disease_id=trained_ira, year=2020, epi_week=week, risk_level=level,
                  origin="OBSERVED", message=f"Prueba S{week}", active=True)
        db.add(a)
        db.commit()
        return a

    previous = alert(1)
    stream = stub.WatchAlerts(pb.AlertFilter(municipality_id=consaca), metadata=META, timeout=20)
    try:
        initial = next(stream)
        assert initial.kind == pb.AlertEvent.KIND_ACTIVE and initial.alert.municipality_id == consaca
        synced = next(e for e in stream if e.kind != pb.AlertEvent.KIND_ACTIVE)
        assert synced.kind == pb.AlertEvent.KIND_SYNCED

        new = alert(2, "RED")
        event = next(e for e in stream if e.alert.id == new.id)
        assert event.kind == pb.AlertEvent.KIND_CREATED and event.alert.level == pb.RISK_LEVEL_RED

        previous.active = False
        db.commit()
        event = next(e for e in stream if e.alert.id == previous.id)
        assert event.kind == pb.AlertEvent.KIND_CLOSED
    finally:
        stream.cancel()
        db.query(Alert).filter(Alert.year == 2020, Alert.municipality_id == consaca).delete()
        db.commit()


def test_cancelling_the_stream_releases_the_subscription(stub, grpc_engine):
    feed = grpc_engine.servicer.feed
    stream = stub.WatchAlerts(pb.AlertFilter(), metadata=META)
    stream.initial_metadata()  # wait until the RPC is open
    time.sleep(0.3)
    assert feed.subscribers >= 1
    stream.cancel()
    for _ in range(30):
        if feed.subscribers == 0:
            break
        time.sleep(0.1)
    assert feed.subscribers == 0


# ── client streaming ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def grpc_pharmacy():
    from volcano.db.session import SessionLocal

    with SessionLocal() as db:
        p = db.query(Pharmacy).filter_by(tax_id="900000999-9").first()
        if p is None:
            pasto = db.query(Municipality).filter_by(divipola_code="52001").one()
            p = Pharmacy(name="Droguería gRPC", tax_id="900000999-9", municipality_id=pasto.id)
            db.add(p)
            db.commit()
        yield p.id
        db.query(PharmacyReport).filter_by(pharmacy_id=p.id).delete()
        db.commit()


def _actor(db, email: str) -> tuple[tuple[str, str], ...]:
    return (*META, ("x-actor-id", str(db.query(User).filter_by(email=email).one().id)))


def test_upload_validates_each_row_and_groups_by_week(stub, db, grpc_pharmacy):
    def row(n, week, category, units):
        return pb.PharmacyReportRow(row=n, pharmacy_id=grpc_pharmacy, year=2024, epi_week=week, category=category,
                                    units=units)

    rows = [row(2, 10, "COLD_FLU", 120), row(3, 10, "tapabocas", 40), row(4, 11, "COLD_FLU", 90),
            row(5, 11, "SYRUPS", 5), row(6, 11, "ANTIGRIPALES", 7), row(7, 54, "COLD_FLU", 1)]
    r = stub.UploadPharmacyReports(iter(rows), metadata=_actor(db, "admin@test.co"))
    assert (r.rows_received, r.rows_rejected) == (6, 3)
    assert (r.weeks_created, r.weeks_updated, r.weeks_rejected) == (2, 0, 0)
    assert {e.row for e in r.errors} == {5, 6, 7}  # 6: COLD_FLU again under its Spanish name
    units = {(x.epi_week, x.category): x.units
             for x in db.query(PharmacyReport).filter_by(pharmacy_id=grpc_pharmacy, year=2024)}
    assert units == {(10, "COLD_FLU"): 120, (10, "FACE_MASKS"): 40, (11, "COLD_FLU"): 90}

    # Uploading the same week again replaces it
    r = stub.UploadPharmacyReports(iter(rows[:1]), metadata=_actor(db, "admin@test.co"))
    assert (r.weeks_created, r.weeks_updated) == (0, 1)


def test_upload_applies_the_pharmacy_rules(stub, db, grpc_pharmacy):
    # A PHARMACY user cannot upload old weeks nor report for another pharmacy
    rows = [pb.PharmacyReportRow(row=2, year=2024, epi_week=5, category="COLD_FLU", units=3),
            pb.PharmacyReportRow(row=3, pharmacy_id=grpc_pharmacy, year=2024, epi_week=6, category="COLD_FLU",
                                 units=3)]
    r = stub.UploadPharmacyReports(iter(rows), metadata=_actor(db, "farmacia@demo.co"))
    assert r.weeks_rejected == 2 and r.weeks_created == 0
    messages = " ".join(e.message for e in r.errors)
    assert "8 semanas" in messages or "asignado" in messages

    with pytest.raises(grpc.RpcError) as exc:  # without x-actor-id
        stub.UploadPharmacyReports(iter(rows), metadata=META)
    assert exc.value.code() == grpc.StatusCode.PERMISSION_DENIED
