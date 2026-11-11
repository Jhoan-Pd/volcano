"""Predictive model: no leakage, comparison against the baseline, intervals, explainability and the
predictive traffic-light endpoints."""
import math

import numpy as np
import pandas as pd
import pytest

from volcano.ml.dataset import DatasetBuilder
from volcano.ml.estimators import MovingAverage, RandomForest
from volcano.ml.explainer import contributions
from volcano.ml.features import FEATURE_GROUPS, FEATURES, GROUP_LABELS_ES
from volcano.ml.progress import ProgressEvent, Stage
from volcano.ml.trainer import ARTIFACT_VERSION, IncompatibleArtifactError, InsufficientDataError, Trainer, mae
from volcano.models import Disease, Municipality, OfficialCase, Prediction, TrainedModel
from volcano.services.forecasting import ForecastingService
from volcano.shared.epi import iter_weeks

WEEKS = list(iter_weeks((2023, 1), (2026, 20)))


@pytest.fixture(scope="module")
def eda_with_cases():
    """Synthetic EDA series for 2 municipalities: seasonality + noise (3.4 years of weeks)."""
    from volcano.db.session import SessionLocal

    rng = np.random.default_rng(0)
    with SessionLocal() as db:
        eda = db.query(Disease).filter_by(code="EDA").one()
        if db.query(OfficialCase).filter_by(disease_id=eda.id).count() == 0:
            for code, base in (("52001", 60), ("52683", 4)):
                m = db.query(Municipality).filter_by(divipola_code=code).one()
                for i, (y, w) in enumerate(WEEKS):
                    lam = base * (1 + 0.4 * math.sin(2 * math.pi * w / 52)) * (1 + 0.002 * i)
                    db.add(OfficialCase(municipality_id=m.id, disease_id=eda.id, year=y, epi_week=w,
                                        cases=int(rng.poisson(lam)), is_simulated=True))
            db.commit()
        return eda.id


def test_dataset_has_no_leakage(db, eda_with_cases):
    """Changing FUTURE cases must not change the features of week t."""
    eda = db.get(Disease, eda_with_cases)
    df = DatasetBuilder(db).build(eda)
    row = df[(df["year"] == 2025) & (df["epi_week"] == 10)].iloc[0]
    future = db.query(OfficialCase).filter(OfficialCase.disease_id == eda.id, OfficialCase.year == 2025,
                                           OfficialCase.epi_week.between(11, 14)).all()
    original = [c.cases for c in future]
    for c in future:
        c.cases += 500
    db.commit()
    try:
        df2 = DatasetBuilder(db).build(eda)
        same = (df2["municipality_id"] == row["municipality_id"]) & (df2["year"] == 2025) & (df2["epi_week"] == 10)
        row2 = df2[same].iloc[0]
        pd.testing.assert_series_equal(row[FEATURES], row2[FEATURES], check_names=False)
        assert row2["y_h1"] == row["y_h1"] + 500  # the target does change: it is the future
    finally:
        for c, v in zip(future, original, strict=True):
            c.cases = v
        db.commit()


def test_every_feature_has_a_group_and_every_group_a_spanish_label():
    assert len(FEATURES) == len(set(FEATURES)) == sum(len(v) for v in FEATURE_GROUPS.values())
    assert set(GROUP_LABELS_ES) == set(FEATURE_GROUPS)


def test_moving_average_is_the_baseline():
    X = pd.DataFrame({"y_ma4": [np.log1p(10.0), np.log1p(0.0)]})
    assert MovingAverage().predict(X) == pytest.approx([10.0, 0.0])


def test_insufficient_data():
    with pytest.raises(InsufficientDataError):
        Trainer().train(pd.DataFrame())


def test_model_learns_a_signal_the_baseline_cannot_see():
    """When future cases depend on searches, the forest must beat the moving average."""
    rng = np.random.default_rng(1)
    n = 400
    X = pd.DataFrame({f: rng.normal(size=n) for f in FEATURES})
    X["y_ma4"] = np.log1p(20.0)
    y = 20 * np.exp(0.8 * X["search_l0"])
    m = RandomForest().fit(X.iloc[:300], y.iloc[:300])
    assert mae(y.iloc[300:], m.predict(X.iloc[300:])) < 0.6 * mae(y.iloc[300:], MovingAverage().predict(X.iloc[300:]))
    _, contrib = contributions(m, X.iloc[[350]], X.median().to_dict())
    assert max(contrib, key=lambda g: abs(contrib[g])) == "searches"


def test_artifacts_of_another_version_are_refused():
    with pytest.raises(IncompatibleArtifactError):
        Trainer.deserialize(Trainer.serialize({"version": "1", "models": {}}))
    assert Trainer.deserialize(Trainer.serialize({"version": ARTIFACT_VERSION}))["version"] == ARTIFACT_VERSION


def test_train_store_and_predict(db, eda_with_cases):
    service = ForecastingService(db, trainer=Trainer(test_weeks=26, permutation_repeats=1))
    models, errors = service.train(eda_with_cases)
    assert not errors and len(models) == 1
    m = models[0]
    assert m.active and m.artifact and m.algorithm in ("Random Forest", "Gradient Boosting")
    assert m.baseline_mae > 0 and m.model_mae > 0 and m.model_rmse >= m.model_mae
    assert sum(m.importances["groups"].values()) == pytest.approx(100, abs=0.5)

    preds = db.query(Prediction).filter_by(model_id=m.id).all()
    assert len(preds) == 2 * 4  # 2 municipalities × 4 weeks
    for p in preds:
        assert p.lower_bound <= p.expected_cases <= p.upper_bound
        assert p.risk_level in ("GREEN", "YELLOW", "ORANGE", "RED")

    # Retraining deactivates the previous model and frees its binary. Progress is checked on the way:
    # it grows monotonically, ends at 1 and names the winning model.
    events: list[ProgressEvent] = []
    models2, _ = service.train(eda_with_cases, progress=events.append)
    fractions = [e.fraction for e in events]
    assert fractions == sorted(fractions) and fractions[-1] == pytest.approx(1.0)
    assert events[0].stage == Stage.DATASET and events[-1].stage == Stage.PREDICTIONS
    ready = next(e for e in events if e.stage == Stage.MODEL_READY)
    assert ready.algorithm == models2[0].algorithm and ready.disease
    db.refresh(m)
    assert not m.active and m.artifact is None and models2[0].active
    assert db.query(TrainedModel).filter_by(disease_id=eda_with_cases).count() == 2
    assert eda_with_cases not in {d.id for d in service.diseases_needing_training()}


def test_prediction_endpoints(client, eda_with_cases):
    pasto = 1
    r = client.get("/api/v1/dashboard/prediction", params={"municipality_id": pasto, "disease_id": eda_with_cases})
    assert r.status_code == 200, r.text
    data = r.json()
    assert [p["horizon"] for p in data["points"]] == [1, 2, 3, 4]
    assert data["model"]["baseline_mae"] is not None and len(data["backtest"]) > 0

    r = client.get("/api/v1/dashboard/explanation", params={"municipality_id": pasto, "disease_id": eda_with_cases})
    assert r.status_code == 200, r.text
    factors = r.json()["factors"]
    assert {f["group"] for f in factors} == set(FEATURE_GROUPS)
    assert {f["group_label"] for f in factors} == set(GROUP_LABELS_ES.values())

    history = client.get("/api/v1/model/history", params={"disease_id": eda_with_cases}).json()
    assert history[0]["active"] and history[0]["mae_improvement_pct"] is not None


def test_retraining_is_admin_only(client, citizen_headers):
    assert client.post("/api/v1/model/retrain", headers=citizen_headers).status_code == 403
    assert client.get("/api/v1/model/status").status_code == 401
