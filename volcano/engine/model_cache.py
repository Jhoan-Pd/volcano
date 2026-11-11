"""Models kept in the engine's memory.

Deserializing an artifact and building the weekly dataset costs hundreds of milliseconds. The
engine is a long-lived process, so it keeps one `Forecaster` per disease and only rebuilds it when:

- the active model changes (someone retrained), or
- `ttl_s` passes (the cron job brought new data even if the model is the same).

Every lookup makes one cheap read (the id of the active model) to know whether the entry is still
valid. A lock per disease stops two threads from building the same thing at once.
"""
import threading
import time
from dataclasses import dataclass

from sqlalchemy import select

from volcano.ml.dataset import DatasetBuilder
from volcano.ml.forecaster import Forecaster
from volcano.ml.trainer import IncompatibleArtifactError, Trainer
from volcano.models import Disease, Municipality, TrainedModel
from volcano.shared.errors import BusinessRuleError, NotFoundError


@dataclass(frozen=True)
class LoadedModel:
    model_id: int
    algorithm: str
    disease: str
    municipalities: dict[int, str]
    forecaster: Forecaster
    loaded_at: float


class ModelCache:
    def __init__(self, ttl_s: float = 900.0, clock=time.monotonic):
        self.ttl_s = ttl_s
        self._clock = clock
        self._entries: dict[int, LoadedModel] = {}
        self._locks: dict[int, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._entries)

    def _lock(self, disease_id: int) -> threading.Lock:
        with self._global_lock:
            return self._locks.setdefault(disease_id, threading.Lock())

    def invalidate(self, disease_id: int | None = None) -> None:
        with self._global_lock:
            if disease_id is None:
                self._entries.clear()
            else:
                self._entries.pop(disease_id, None)

    def _is_fresh(self, entry: LoadedModel | None, model_id: int) -> bool:
        return entry is not None and entry.model_id == model_id and self._clock() - entry.loaded_at < self.ttl_s

    def get(self, db, disease_id: int) -> tuple[LoadedModel, bool]:
        """(loaded model, came from the cache). Raises NotFoundError when there is no active model."""
        row = db.execute(select(TrainedModel.id).where(
            TrainedModel.disease_id == disease_id, TrainedModel.active.is_(True),
            TrainedModel.artifact.is_not(None)).order_by(TrainedModel.id.desc()).limit(1)).first()
        if row is None:
            raise NotFoundError("Esta enfermedad aún no tiene un modelo entrenado")
        model_id = row[0]
        if self._is_fresh(self._entries.get(disease_id), model_id):
            return self._entries[disease_id], True
        with self._lock(disease_id):
            entry = self._entries.get(disease_id)
            if self._is_fresh(entry, model_id):  # another thread loaded it while we waited
                return entry, True
            entry = self._load(db, disease_id, model_id)
            self._entries[disease_id] = entry
            return entry, False

    def _load(self, db, disease_id: int, model_id: int) -> LoadedModel:
        disease = db.get(Disease, disease_id)
        model = db.get(TrainedModel, model_id)
        try:
            artifact = Trainer.deserialize(model.artifact)
        except IncompatibleArtifactError:
            raise BusinessRuleError("El modelo guardado es de una versión anterior; se está reentrenando") from None
        forecaster = Forecaster(disease, artifact, DatasetBuilder(db).build(disease))
        names = dict(db.execute(select(Municipality.id, Municipality.name)).all())
        return LoadedModel(model_id=model_id, algorithm=model.algorithm, disease=disease.name,
                           municipalities={m: names.get(m, str(m)) for m in forecaster.municipalities()},
                           forecaster=forecaster, loaded_at=self._clock())
