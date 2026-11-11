"""Progress of a training run, so it can be shown live.

The trainer and the prediction service accept an optional `progress(event)` callback (the
simplest form of the Observer pattern). Without it everything works the same; with it, the gRPC
engine forwards each event to the browser as a message of a stream.
"""
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    STARTED = "STARTED"
    DATASET = "DATASET"
    CANDIDATE = "CANDIDATE"
    MODEL_READY = "MODEL_READY"
    PREDICTIONS = "PREDICTIONS"
    ALERTS = "ALERTS"
    WARNING = "WARNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ProgressEvent:
    stage: Stage
    message: str  # Spanish, shown in the admin panel
    fraction: float  # 0 to 1
    disease: str = ""
    algorithm: str = ""
    mae: float | None = None
    baseline_mae: float | None = None


Progress = Callable[[ProgressEvent], None]


def no_progress(_: ProgressEvent) -> None:
    """Null callback (Null Object pattern): saves an `if progress is not None` at every step."""


def scaled(progress: Progress, start: float, end: float, **extra) -> Progress:
    """Map the 0-1 progress of a sub-task onto the [start, end] stretch of the whole task."""
    def inner(e: ProgressEvent) -> None:
        data = {**e.__dict__, **{k: v for k, v in extra.items() if not getattr(e, k)}}
        data["fraction"] = start + (end - start) * e.fraction
        progress(ProgressEvent(**data))
    return inner
