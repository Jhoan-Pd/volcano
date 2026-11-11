"""Municipality, disease, pharmacy and volcanic-event schemas."""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from volcano.models.enums import ProductCategory, VolcanicEventType, VolcanoLevel, parse_enum
from volcano.schemas.common import ORMModel

# ── Municipalities ───────────────────────────────────────────────────────────


class MunicipalityBase(BaseModel):
    divipola_code: str = Field(pattern=r"^\d{5}$", description="5-digit DIVIPOLA code")
    name: str = Field(min_length=2, max_length=80)
    department: str = Field(default="Nariño", max_length=60)
    latitude: float = Field(ge=-4.5, le=13.5, description="Latitude inside Colombia")
    longitude: float = Field(ge=-82, le=-66)
    altitude_m: int | None = Field(default=None, ge=0, le=6000)
    population: int = Field(gt=0)
    crater_distance_km: float | None = Field(default=None, ge=0)
    active: bool = True


class MunicipalityCreate(MunicipalityBase):
    pass


class MunicipalityUpdate(BaseModel):
    divipola_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    name: str | None = Field(default=None, min_length=2, max_length=80)
    department: str | None = None
    latitude: float | None = Field(default=None, ge=-4.5, le=13.5)
    longitude: float | None = Field(default=None, ge=-82, le=-66)
    altitude_m: int | None = Field(default=None, ge=0, le=6000)
    population: int | None = Field(default=None, gt=0)
    crater_distance_km: float | None = Field(default=None, ge=0)
    active: bool | None = None


class MunicipalityOut(ORMModel, MunicipalityBase):
    id: int


# ── Diseases ─────────────────────────────────────────────────────────────────


class _ThresholdsMixin(BaseModel):
    @model_validator(mode="after")
    def _ordered_thresholds(self):
        y, o, r = self.yellow_threshold_pct, self.orange_threshold_pct, self.red_threshold_pct
        if None not in (y, o, r) and not (y < o < r):
            raise ValueError("Los umbrales deben cumplir amarillo < naranja < rojo")
        return self


class _CategoriesMixin(BaseModel):
    @field_validator("pharmacy_categories", check_fields=False)
    @classmethod
    def _valid_categories(cls, v: str | None) -> str | None:
        if not v:
            return None
        parsed, invalid = [], []
        for part in (p for p in v.split(",") if p.strip()):
            try:
                parsed.append(parse_enum(ProductCategory, part).value)
            except ValueError:
                invalid.append(part.strip().upper())
        if invalid:
            raise ValueError(f"Categorías inválidas: {', '.join(invalid)}. "
                             f"Válidas: {', '.join(ProductCategory.__members__)}")
        return ",".join(parsed)


class DiseaseBase(_ThresholdsMixin, _CategoriesMixin):
    code: str = Field(pattern=r"^[A-Z0-9_]{2,20}$", description="E.g. IRA, EDA, DENGUE")
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None
    icd10_code: str | None = Field(default=None, max_length=40)
    recommendations: str | None = None
    search_terms: str | None = Field(default=None, max_length=300)
    sivigila_codes: str | None = Field(default=None, pattern=r"^\d{3}(,\d{3})*$", max_length=60,
                                       description="Comma-separated INS event codes, e.g. 210,220")
    pharmacy_categories: str | None = Field(default=None, max_length=200,
                                            description="Comma-separated sales categories, e.g. COLD_FLU")
    color: str = Field(default="#2a78d6", pattern=r"^#[0-9a-fA-F]{6}$")
    yellow_threshold_pct: int = Field(default=50, ge=1, le=99)
    orange_threshold_pct: int = Field(default=75, ge=1, le=99)
    red_threshold_pct: int = Field(default=90, ge=1, le=99)
    active: bool = True


class DiseaseCreate(DiseaseBase):
    pass


class DiseaseUpdate(_ThresholdsMixin, _CategoriesMixin):
    code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{2,20}$")
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    icd10_code: str | None = None
    recommendations: str | None = None
    search_terms: str | None = None
    sivigila_codes: str | None = Field(default=None, pattern=r"^\d{3}(,\d{3})*$", max_length=60)
    pharmacy_categories: str | None = Field(default=None, max_length=200)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    yellow_threshold_pct: int | None = Field(default=None, ge=1, le=99)
    orange_threshold_pct: int | None = Field(default=None, ge=1, le=99)
    red_threshold_pct: int | None = Field(default=None, ge=1, le=99)
    active: bool | None = None


class DiseaseOut(ORMModel, DiseaseBase):
    id: int


# ── Pharmacies ───────────────────────────────────────────────────────────────


class PharmacyBase(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    tax_id: str = Field(pattern=r"^\d{6,12}(-\d)?$", description="Colombian NIT, e.g. 900123456-7")
    address: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, pattern=r"^[0-9 +()-]{7,20}$")
    municipality_id: int
    user_id: int | None = None
    latitude: float | None = Field(default=None, ge=-4.5, le=13.5)
    longitude: float | None = Field(default=None, ge=-82, le=-66)
    active: bool = True


class PharmacyCreate(PharmacyBase):
    pass


class PharmacyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    tax_id: str | None = Field(default=None, pattern=r"^\d{6,12}(-\d)?$")
    address: str | None = None
    phone: str | None = Field(default=None, pattern=r"^[0-9 +()-]{7,20}$")
    municipality_id: int | None = None
    user_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    active: bool | None = None


class PharmacyOut(ORMModel, PharmacyBase):
    id: int


# ── Volcanic events ──────────────────────────────────────────────────────────


class _DatesMixin(BaseModel):
    @model_validator(mode="after")
    def _consistent(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date no puede ser anterior a start_date")
        if getattr(self, "event_type", None) == VolcanicEventType.ASH_FALL:
            if not self.municipality_id:
                raise ValueError("Una caída de ceniza debe indicar el municipio afectado")
            if not self.ash_intensity:
                raise ValueError("Una caída de ceniza debe tener intensidad entre 1 y 3")
        return self


class VolcanicEventBase(_DatesMixin):
    event_type: VolcanicEventType
    activity_level: VolcanoLevel
    start_date: date
    end_date: date | None = None
    municipality_id: int | None = None
    ash_intensity: int = Field(default=0, ge=0, le=3, description="0 none, 1 light, 2 moderate, 3 heavy")
    so2_tons_per_day: float | None = Field(default=None, ge=0)
    description: str | None = None
    bulletin_url: str | None = Field(default=None, max_length=400)


class VolcanicEventCreate(VolcanicEventBase):
    pass


class VolcanicEventUpdate(_DatesMixin):
    event_type: VolcanicEventType | None = None
    activity_level: VolcanoLevel | None = None
    start_date: date | None = None
    end_date: date | None = None
    municipality_id: int | None = None
    ash_intensity: int | None = Field(default=None, ge=0, le=3)
    so2_tons_per_day: float | None = Field(default=None, ge=0)
    description: str | None = None
    bulletin_url: str | None = None


class VolcanicEventOut(ORMModel, VolcanicEventBase):
    id: int
    is_simulated: bool
    created_at: datetime

    # The output does not re-validate business rules (the data is already stored)
    @model_validator(mode="after")
    def _consistent(self):
        return self
