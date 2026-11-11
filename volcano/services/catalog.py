"""CRUD services for municipalities, diseases, pharmacies and volcanic events."""
from typing import Any

from sqlalchemy import func, select

from volcano.models import Municipality, OfficialCase, Pharmacy, User, VolcanicEvent
from volcano.models.enums import RoleName
from volcano.repositories.domain import (
    DiseaseRepository,
    MunicipalityRepository,
    PharmacyRepository,
    VolcanicEventRepository,
)
from volcano.schemas.catalog import VolcanicEventBase
from volcano.services.crud import CrudService
from volcano.shared.errors import BusinessRuleError, ConflictError, NotFoundError


def _must_exist(db, model, id_: int | None, name: str) -> None:
    if id_ is not None and db.get(model, id_) is None:
        raise NotFoundError(f"{name} {id_} no existe")


class MunicipalityService(CrudService[Municipality]):
    repository_cls = MunicipalityRepository
    entity_name = "Municipio"
    unique_fields = ("divipola_code",)

    def before_delete(self, obj) -> None:
        cases = self.db.scalar(select(func.count()).where(OfficialCase.municipality_id == obj.id))
        pharmacies = self.db.scalar(select(func.count()).where(Pharmacy.municipality_id == obj.id))
        if cases or pharmacies:
            raise ConflictError(
                f"El municipio tiene {cases} registros de casos y {pharmacies} farmacias. "
                "Desactívalo (active=false) en lugar de eliminarlo para conservar el histórico."
            )


class DiseaseService(CrudService):
    repository_cls = DiseaseRepository
    entity_name = "Enfermedad"
    unique_fields = ("code",)

    def validate(self, data: dict[str, Any], current=None) -> dict[str, Any]:
        if current is not None:  # partial edit: check the resulting thresholds
            y = data.get("yellow_threshold_pct", current.yellow_threshold_pct)
            o = data.get("orange_threshold_pct", current.orange_threshold_pct)
            r = data.get("red_threshold_pct", current.red_threshold_pct)
            if not (y < o < r):
                raise BusinessRuleError("Los umbrales deben cumplir amarillo < naranja < rojo")
        return data

    def before_delete(self, obj) -> None:
        cases = self.db.scalar(select(func.count()).where(OfficialCase.disease_id == obj.id))
        if cases:
            raise ConflictError(f"La enfermedad tiene {cases} registros de casos. Desactívala en lugar de eliminarla.")


class PharmacyService(CrudService):
    repository_cls = PharmacyRepository
    entity_name = "Farmacia"
    unique_fields = ("tax_id", "user_id")

    def validate(self, data: dict[str, Any], current=None) -> dict[str, Any]:
        _must_exist(self.db, Municipality, data.get("municipality_id"), "Municipio")
        uid = data.get("user_id")
        if uid is not None:
            user = self.db.get(User, uid)
            if user is None:
                raise NotFoundError(f"Usuario {uid} no existe")
            if user.role_name != RoleName.PHARMACY:
                raise BusinessRuleError("El usuario asignado a una farmacia debe tener rol PHARMACY")
        return data


class VolcanicEventService(CrudService):
    repository_cls = VolcanicEventRepository
    entity_name = "Evento volcánico"

    def order_by(self):
        return VolcanicEvent.start_date.desc()

    def validate(self, data: dict[str, Any], current=None) -> dict[str, Any]:
        _must_exist(self.db, Municipality, data.get("municipality_id"), "Municipio")
        if current is not None:
            # Validate the whole resulting object (ash-fall and date rules)
            fields = VolcanicEventBase.model_fields.keys()
            merged = {f: getattr(current, f) for f in fields} | data
            try:
                VolcanicEventBase.model_validate(merged)
            except ValueError as exc:
                raise BusinessRuleError(str(exc).split("\n")[-1].strip()) from None
        for key in ("event_type", "activity_level"):
            if data.get(key) is not None:
                data[key] = str(getattr(data[key], "value", data[key]))
        return data
