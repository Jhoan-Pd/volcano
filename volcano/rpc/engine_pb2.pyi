from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RiskLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RISK_LEVEL_UNSPECIFIED: _ClassVar[RiskLevel]
    RISK_LEVEL_GREEN: _ClassVar[RiskLevel]
    RISK_LEVEL_YELLOW: _ClassVar[RiskLevel]
    RISK_LEVEL_ORANGE: _ClassVar[RiskLevel]
    RISK_LEVEL_RED: _ClassVar[RiskLevel]
RISK_LEVEL_UNSPECIFIED: RiskLevel
RISK_LEVEL_GREEN: RiskLevel
RISK_LEVEL_YELLOW: RiskLevel
RISK_LEVEL_ORANGE: RiskLevel
RISK_LEVEL_RED: RiskLevel

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class EngineStatus(_message.Message):
    __slots__ = ("version", "models_in_memory", "training", "uptime_s", "rpcs_served")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    MODELS_IN_MEMORY_FIELD_NUMBER: _ClassVar[int]
    TRAINING_FIELD_NUMBER: _ClassVar[int]
    UPTIME_S_FIELD_NUMBER: _ClassVar[int]
    RPCS_SERVED_FIELD_NUMBER: _ClassVar[int]
    version: str
    models_in_memory: int
    training: bool
    uptime_s: float
    rpcs_served: int
    def __init__(self, version: _Optional[str] = ..., models_in_memory: _Optional[int] = ..., training: _Optional[bool] = ..., uptime_s: _Optional[float] = ..., rpcs_served: _Optional[int] = ...) -> None: ...

class ForecastRequest(_message.Message):
    __slots__ = ("municipality_id", "disease_id")
    MUNICIPALITY_ID_FIELD_NUMBER: _ClassVar[int]
    DISEASE_ID_FIELD_NUMBER: _ClassVar[int]
    municipality_id: int
    disease_id: int
    def __init__(self, municipality_id: _Optional[int] = ..., disease_id: _Optional[int] = ...) -> None: ...

class Thresholds(_message.Message):
    __slots__ = ("yellow", "orange", "red")
    YELLOW_FIELD_NUMBER: _ClassVar[int]
    ORANGE_FIELD_NUMBER: _ClassVar[int]
    RED_FIELD_NUMBER: _ClassVar[int]
    yellow: float
    orange: float
    red: float
    def __init__(self, yellow: _Optional[float] = ..., orange: _Optional[float] = ..., red: _Optional[float] = ...) -> None: ...

class ForecastPoint(_message.Message):
    __slots__ = ("year", "epi_week", "label", "horizon", "expected_cases", "lower_bound", "upper_bound", "level", "thresholds")
    YEAR_FIELD_NUMBER: _ClassVar[int]
    EPI_WEEK_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    HORIZON_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_CASES_FIELD_NUMBER: _ClassVar[int]
    LOWER_BOUND_FIELD_NUMBER: _ClassVar[int]
    UPPER_BOUND_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    THRESHOLDS_FIELD_NUMBER: _ClassVar[int]
    year: int
    epi_week: int
    label: str
    horizon: int
    expected_cases: float
    lower_bound: float
    upper_bound: float
    level: RiskLevel
    thresholds: Thresholds
    def __init__(self, year: _Optional[int] = ..., epi_week: _Optional[int] = ..., label: _Optional[str] = ..., horizon: _Optional[int] = ..., expected_cases: _Optional[float] = ..., lower_bound: _Optional[float] = ..., upper_bound: _Optional[float] = ..., level: _Optional[_Union[RiskLevel, str]] = ..., thresholds: _Optional[_Union[Thresholds, _Mapping]] = ...) -> None: ...

class Forecast(_message.Message):
    __slots__ = ("municipality_id", "municipality", "disease_id", "disease", "algorithm", "model_id", "base_week", "max_level", "points", "duration_ms", "from_cache")
    MUNICIPALITY_ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPALITY_FIELD_NUMBER: _ClassVar[int]
    DISEASE_ID_FIELD_NUMBER: _ClassVar[int]
    DISEASE_FIELD_NUMBER: _ClassVar[int]
    ALGORITHM_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    BASE_WEEK_FIELD_NUMBER: _ClassVar[int]
    MAX_LEVEL_FIELD_NUMBER: _ClassVar[int]
    POINTS_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    FROM_CACHE_FIELD_NUMBER: _ClassVar[int]
    municipality_id: int
    municipality: str
    disease_id: int
    disease: str
    algorithm: str
    model_id: int
    base_week: str
    max_level: RiskLevel
    points: _containers.RepeatedCompositeFieldContainer[ForecastPoint]
    duration_ms: float
    from_cache: bool
    def __init__(self, municipality_id: _Optional[int] = ..., municipality: _Optional[str] = ..., disease_id: _Optional[int] = ..., disease: _Optional[str] = ..., algorithm: _Optional[str] = ..., model_id: _Optional[int] = ..., base_week: _Optional[str] = ..., max_level: _Optional[_Union[RiskLevel, str]] = ..., points: _Optional[_Iterable[_Union[ForecastPoint, _Mapping]]] = ..., duration_ms: _Optional[float] = ..., from_cache: _Optional[bool] = ...) -> None: ...

class RefreshRequest(_message.Message):
    __slots__ = ("evaluate_alerts", "send_email")
    EVALUATE_ALERTS_FIELD_NUMBER: _ClassVar[int]
    SEND_EMAIL_FIELD_NUMBER: _ClassVar[int]
    evaluate_alerts: bool
    send_email: bool
    def __init__(self, evaluate_alerts: _Optional[bool] = ..., send_email: _Optional[bool] = ...) -> None: ...

class RefreshResult(_message.Message):
    __slots__ = ("predictions", "alerts_new", "alerts_updated", "alerts_closed", "alerts_active", "emails_sent")
    PREDICTIONS_FIELD_NUMBER: _ClassVar[int]
    ALERTS_NEW_FIELD_NUMBER: _ClassVar[int]
    ALERTS_UPDATED_FIELD_NUMBER: _ClassVar[int]
    ALERTS_CLOSED_FIELD_NUMBER: _ClassVar[int]
    ALERTS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    EMAILS_SENT_FIELD_NUMBER: _ClassVar[int]
    predictions: int
    alerts_new: int
    alerts_updated: int
    alerts_closed: int
    alerts_active: int
    emails_sent: int
    def __init__(self, predictions: _Optional[int] = ..., alerts_new: _Optional[int] = ..., alerts_updated: _Optional[int] = ..., alerts_closed: _Optional[int] = ..., alerts_active: _Optional[int] = ..., emails_sent: _Optional[int] = ...) -> None: ...

class TrainingRequest(_message.Message):
    __slots__ = ("disease_id",)
    DISEASE_ID_FIELD_NUMBER: _ClassVar[int]
    disease_id: int
    def __init__(self, disease_id: _Optional[int] = ...) -> None: ...

class TrainingStatus(_message.Message):
    __slots__ = ("running", "started_at", "finished_at", "message", "errors")
    RUNNING_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    running: bool
    started_at: str
    finished_at: str
    message: str
    errors: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, running: _Optional[bool] = ..., started_at: _Optional[str] = ..., finished_at: _Optional[str] = ..., message: _Optional[str] = ..., errors: _Optional[_Iterable[str]] = ...) -> None: ...

class TrainingProgress(_message.Message):
    __slots__ = ("stage", "message", "percent", "disease", "algorithm", "mae", "baseline_mae")
    class Stage(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STAGE_UNSPECIFIED: _ClassVar[TrainingProgress.Stage]
        STAGE_STARTED: _ClassVar[TrainingProgress.Stage]
        STAGE_DATASET: _ClassVar[TrainingProgress.Stage]
        STAGE_CANDIDATE: _ClassVar[TrainingProgress.Stage]
        STAGE_MODEL_READY: _ClassVar[TrainingProgress.Stage]
        STAGE_PREDICTIONS: _ClassVar[TrainingProgress.Stage]
        STAGE_ALERTS: _ClassVar[TrainingProgress.Stage]
        STAGE_WARNING: _ClassVar[TrainingProgress.Stage]
        STAGE_FINISHED: _ClassVar[TrainingProgress.Stage]
        STAGE_FAILED: _ClassVar[TrainingProgress.Stage]
    STAGE_UNSPECIFIED: TrainingProgress.Stage
    STAGE_STARTED: TrainingProgress.Stage
    STAGE_DATASET: TrainingProgress.Stage
    STAGE_CANDIDATE: TrainingProgress.Stage
    STAGE_MODEL_READY: TrainingProgress.Stage
    STAGE_PREDICTIONS: TrainingProgress.Stage
    STAGE_ALERTS: TrainingProgress.Stage
    STAGE_WARNING: TrainingProgress.Stage
    STAGE_FINISHED: TrainingProgress.Stage
    STAGE_FAILED: TrainingProgress.Stage
    STAGE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PERCENT_FIELD_NUMBER: _ClassVar[int]
    DISEASE_FIELD_NUMBER: _ClassVar[int]
    ALGORITHM_FIELD_NUMBER: _ClassVar[int]
    MAE_FIELD_NUMBER: _ClassVar[int]
    BASELINE_MAE_FIELD_NUMBER: _ClassVar[int]
    stage: TrainingProgress.Stage
    message: str
    percent: float
    disease: str
    algorithm: str
    mae: float
    baseline_mae: float
    def __init__(self, stage: _Optional[_Union[TrainingProgress.Stage, str]] = ..., message: _Optional[str] = ..., percent: _Optional[float] = ..., disease: _Optional[str] = ..., algorithm: _Optional[str] = ..., mae: _Optional[float] = ..., baseline_mae: _Optional[float] = ...) -> None: ...

class AlertFilter(_message.Message):
    __slots__ = ("municipality_id",)
    MUNICIPALITY_ID_FIELD_NUMBER: _ClassVar[int]
    municipality_id: int
    def __init__(self, municipality_id: _Optional[int] = ...) -> None: ...

class Alert(_message.Message):
    __slots__ = ("id", "municipality_id", "municipality", "disease_id", "disease", "week", "level", "origin", "message")
    ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPALITY_ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPALITY_FIELD_NUMBER: _ClassVar[int]
    DISEASE_ID_FIELD_NUMBER: _ClassVar[int]
    DISEASE_FIELD_NUMBER: _ClassVar[int]
    WEEK_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    ORIGIN_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    id: int
    municipality_id: int
    municipality: str
    disease_id: int
    disease: str
    week: str
    level: RiskLevel
    origin: str
    message: str
    def __init__(self, id: _Optional[int] = ..., municipality_id: _Optional[int] = ..., municipality: _Optional[str] = ..., disease_id: _Optional[int] = ..., disease: _Optional[str] = ..., week: _Optional[str] = ..., level: _Optional[_Union[RiskLevel, str]] = ..., origin: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class AlertEvent(_message.Message):
    __slots__ = ("kind", "alert", "at")
    class Kind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        KIND_UNSPECIFIED: _ClassVar[AlertEvent.Kind]
        KIND_ACTIVE: _ClassVar[AlertEvent.Kind]
        KIND_CREATED: _ClassVar[AlertEvent.Kind]
        KIND_UPDATED: _ClassVar[AlertEvent.Kind]
        KIND_CLOSED: _ClassVar[AlertEvent.Kind]
        KIND_SYNCED: _ClassVar[AlertEvent.Kind]
    KIND_UNSPECIFIED: AlertEvent.Kind
    KIND_ACTIVE: AlertEvent.Kind
    KIND_CREATED: AlertEvent.Kind
    KIND_UPDATED: AlertEvent.Kind
    KIND_CLOSED: AlertEvent.Kind
    KIND_SYNCED: AlertEvent.Kind
    KIND_FIELD_NUMBER: _ClassVar[int]
    ALERT_FIELD_NUMBER: _ClassVar[int]
    AT_FIELD_NUMBER: _ClassVar[int]
    kind: AlertEvent.Kind
    alert: Alert
    at: str
    def __init__(self, kind: _Optional[_Union[AlertEvent.Kind, str]] = ..., alert: _Optional[_Union[Alert, _Mapping]] = ..., at: _Optional[str] = ...) -> None: ...

class PharmacyReportRow(_message.Message):
    __slots__ = ("row", "pharmacy_id", "year", "epi_week", "category", "units")
    ROW_FIELD_NUMBER: _ClassVar[int]
    PHARMACY_ID_FIELD_NUMBER: _ClassVar[int]
    YEAR_FIELD_NUMBER: _ClassVar[int]
    EPI_WEEK_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    row: int
    pharmacy_id: int
    year: int
    epi_week: int
    category: str
    units: int
    def __init__(self, row: _Optional[int] = ..., pharmacy_id: _Optional[int] = ..., year: _Optional[int] = ..., epi_week: _Optional[int] = ..., category: _Optional[str] = ..., units: _Optional[int] = ...) -> None: ...

class RowError(_message.Message):
    __slots__ = ("row", "message")
    ROW_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    row: int
    message: str
    def __init__(self, row: _Optional[int] = ..., message: _Optional[str] = ...) -> None: ...

class UploadSummary(_message.Message):
    __slots__ = ("rows_received", "rows_rejected", "weeks_created", "weeks_updated", "weeks_rejected", "errors")
    ROWS_RECEIVED_FIELD_NUMBER: _ClassVar[int]
    ROWS_REJECTED_FIELD_NUMBER: _ClassVar[int]
    WEEKS_CREATED_FIELD_NUMBER: _ClassVar[int]
    WEEKS_UPDATED_FIELD_NUMBER: _ClassVar[int]
    WEEKS_REJECTED_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    rows_received: int
    rows_rejected: int
    weeks_created: int
    weeks_updated: int
    weeks_rejected: int
    errors: _containers.RepeatedCompositeFieldContainer[RowError]
    def __init__(self, rows_received: _Optional[int] = ..., rows_rejected: _Optional[int] = ..., weeks_created: _Optional[int] = ..., weeks_updated: _Optional[int] = ..., weeks_rejected: _Optional[int] = ..., errors: _Optional[_Iterable[_Union[RowError, _Mapping]]] = ...) -> None: ...

class Scenario(_message.Message):
    __slots__ = ("id", "municipality_id", "disease_id", "temperature_delta_c", "rain_change_pct", "search_change_pct", "pharmacy_change_pct", "ash_fall")
    ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPALITY_ID_FIELD_NUMBER: _ClassVar[int]
    DISEASE_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_DELTA_C_FIELD_NUMBER: _ClassVar[int]
    RAIN_CHANGE_PCT_FIELD_NUMBER: _ClassVar[int]
    SEARCH_CHANGE_PCT_FIELD_NUMBER: _ClassVar[int]
    PHARMACY_CHANGE_PCT_FIELD_NUMBER: _ClassVar[int]
    ASH_FALL_FIELD_NUMBER: _ClassVar[int]
    id: str
    municipality_id: int
    disease_id: int
    temperature_delta_c: float
    rain_change_pct: float
    search_change_pct: float
    pharmacy_change_pct: float
    ash_fall: bool
    def __init__(self, id: _Optional[str] = ..., municipality_id: _Optional[int] = ..., disease_id: _Optional[int] = ..., temperature_delta_c: _Optional[float] = ..., rain_change_pct: _Optional[float] = ..., search_change_pct: _Optional[float] = ..., pharmacy_change_pct: _Optional[float] = ..., ash_fall: _Optional[bool] = ...) -> None: ...

class ScenarioResult(_message.Message):
    __slots__ = ("id", "municipality_id", "disease_id", "baseline", "scenario", "max_level", "change_pct", "summary", "duration_ms", "error")
    ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPALITY_ID_FIELD_NUMBER: _ClassVar[int]
    DISEASE_ID_FIELD_NUMBER: _ClassVar[int]
    BASELINE_FIELD_NUMBER: _ClassVar[int]
    SCENARIO_FIELD_NUMBER: _ClassVar[int]
    MAX_LEVEL_FIELD_NUMBER: _ClassVar[int]
    CHANGE_PCT_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    id: str
    municipality_id: int
    disease_id: int
    baseline: _containers.RepeatedCompositeFieldContainer[ForecastPoint]
    scenario: _containers.RepeatedCompositeFieldContainer[ForecastPoint]
    max_level: RiskLevel
    change_pct: float
    summary: str
    duration_ms: float
    error: str
    def __init__(self, id: _Optional[str] = ..., municipality_id: _Optional[int] = ..., disease_id: _Optional[int] = ..., baseline: _Optional[_Iterable[_Union[ForecastPoint, _Mapping]]] = ..., scenario: _Optional[_Iterable[_Union[ForecastPoint, _Mapping]]] = ..., max_level: _Optional[_Union[RiskLevel, str]] = ..., change_pct: _Optional[float] = ..., summary: _Optional[str] = ..., duration_ms: _Optional[float] = ..., error: _Optional[str] = ...) -> None: ...
