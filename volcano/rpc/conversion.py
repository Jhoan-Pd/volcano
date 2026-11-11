"""Mapping between the domain (dataclasses, enums, ORM rows) and the protobuf messages.

Keeping every conversion here (Mapper pattern) stops the server and the clients from repeating
`pb.RiskLevel.Value(...)` everywhere. Protobuf enum values carry their type as a prefix
(`RISK_LEVEL_RED`, as the style guide asks); the domain uses the bare name (`RED`).
"""
from volcano.ml.progress import ProgressEvent
from volcano.models.enums import RiskLevel
from volcano.rpc import engine_pb2 as pb
from volcano.shared.epi import label

_RISK_PREFIX = "RISK_LEVEL_"
_STAGE_PREFIX = "STAGE_"
_KIND_PREFIX = "KIND_"


def level_to_pb(level: RiskLevel | str | None) -> int:
    return pb.RiskLevel.Value(_RISK_PREFIX + RiskLevel(level).value) if level else pb.RISK_LEVEL_UNSPECIFIED


def level_from_pb(value: int) -> str | None:
    return None if value == pb.RISK_LEVEL_UNSPECIFIED else pb.RiskLevel.Name(value).removeprefix(_RISK_PREFIX)


def stage_to_pb(stage: str) -> int:
    return pb.TrainingProgress.Stage.Value(_STAGE_PREFIX + stage)


def stage_from_pb(value: int) -> str:
    return pb.TrainingProgress.Stage.Name(value).removeprefix(_STAGE_PREFIX)


def kind_from_pb(value: int) -> str:
    return pb.AlertEvent.Kind.Name(value).removeprefix(_KIND_PREFIX)


def point_to_pb(p) -> pb.ForecastPoint:
    """`p` is a volcano.ml.forecaster.ForecastPoint (duck-typed to keep this module free of pandas)."""
    msg = pb.ForecastPoint(
        year=p.year, epi_week=p.epi_week, label=label(p.year, p.epi_week), horizon=p.horizon,
        expected_cases=p.expected_cases, lower_bound=p.lower_bound, upper_bound=p.upper_bound,
        level=level_to_pb(p.level))
    if p.thresholds is not None:
        msg.thresholds.CopyFrom(pb.Thresholds(yellow=p.thresholds.yellow, orange=p.thresholds.orange,
                                              red=p.thresholds.red))
    return msg


def point_from_pb(p: pb.ForecastPoint) -> dict:
    return {
        "year": p.year, "epi_week": p.epi_week, "label": p.label, "horizon": p.horizon,
        "expected_cases": p.expected_cases, "lower_bound": p.lower_bound, "upper_bound": p.upper_bound,
        "level": level_from_pb(p.level),
        "thresholds": ({"yellow": p.thresholds.yellow, "orange": p.thresholds.orange, "red": p.thresholds.red}
                       if p.HasField("thresholds") else None),
    }


def progress_to_pb(e: ProgressEvent) -> pb.TrainingProgress:
    return pb.TrainingProgress(
        stage=stage_to_pb(e.stage.value), message=e.message, percent=round(100 * e.fraction, 1),
        disease=e.disease, algorithm=e.algorithm, mae=e.mae, baseline_mae=e.baseline_mae)


def progress_from_pb(p: pb.TrainingProgress) -> dict:
    return {
        "stage": stage_from_pb(p.stage), "message": p.message, "percent": p.percent,
        "disease": p.disease or None, "algorithm": p.algorithm or None,
        "mae": p.mae if p.HasField("mae") else None,
        "baseline_mae": p.baseline_mae if p.HasField("baseline_mae") else None,
    }


def alert_from_pb(a: pb.Alert) -> dict:
    return {"id": a.id, "municipality_id": a.municipality_id, "municipality": a.municipality,
            "disease_id": a.disease_id, "disease": a.disease, "week": a.week, "level": level_from_pb(a.level),
            "origin": a.origin, "message": a.message}


def alert_event_from_pb(e: pb.AlertEvent) -> dict:
    return {"kind": kind_from_pb(e.kind), "at": e.at, "alert": alert_from_pb(e.alert)}


def training_status_from_pb(s: pb.TrainingStatus) -> dict:
    return {"running": s.running, "started_at": s.started_at or None, "finished_at": s.finished_at or None,
            "message": s.message or None, "errors": list(s.errors)}


def scenario_result_from_pb(r: pb.ScenarioResult) -> dict:
    return {
        "id": r.id, "municipality_id": r.municipality_id, "disease_id": r.disease_id,
        "baseline": [point_from_pb(x) for x in r.baseline], "scenario": [point_from_pb(x) for x in r.scenario],
        "max_level": level_from_pb(r.max_level), "change_pct": r.change_pct, "summary": r.summary,
        "duration_ms": r.duration_ms, "error": r.error or None,
    }
