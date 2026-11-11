"""Pharmacy module schemas (weekly sales report)."""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from volcano.models.enums import ProductCategory, parse_enum
from volcano.shared.epi import weeks_in_year

MAX_UNITS = 100_000


class ReportItem(BaseModel):
    category: ProductCategory
    units: int = Field(ge=0, le=MAX_UNITS, description="Units sold during the week")

    @field_validator("category", mode="before")
    @classmethod
    def _legacy_category(cls, v):
        return parse_enum(ProductCategory, v) if isinstance(v, str) else v


class _ItemsMixin(BaseModel):
    items: list[ReportItem] = Field(min_length=1, max_length=len(ProductCategory))

    @field_validator("items")
    @classmethod
    def _no_duplicates(cls, items: list[ReportItem]) -> list[ReportItem]:
        categories = [i.category for i in items]
        repeated = {c.value for c in categories if categories.count(c) > 1}
        if repeated:
            raise ValueError(f"Categoría repetida: {', '.join(sorted(repeated))}")
        return items


class WeeklyReportIn(_ItemsMixin):
    year: int = Field(ge=2015, le=2100)
    epi_week: int = Field(ge=1, le=53)
    pharmacy_id: int | None = Field(default=None, description="ADMIN only: pharmacy reported for")

    @model_validator(mode="after")
    def _week_exists(self):
        if self.epi_week > weeks_in_year(self.year):
            raise ValueError(f"El año {self.year} solo tiene {weeks_in_year(self.year)} semanas epidemiológicas")
        return self


class WeeklyReportUpdate(_ItemsMixin):
    pass


class ReportItemOut(BaseModel):
    category: str
    units: int


class WeeklyReportOut(BaseModel):
    pharmacy_id: int
    pharmacy: str
    year: int
    epi_week: int
    label: str
    start_date: date
    end_date: date
    items: list[ReportItemOut]
    total_units: int
    is_simulated: bool
    updated_at: datetime | None
    reported_by: str | None
    editable: bool


class ReportableWeek(BaseModel):
    year: int
    epi_week: int
    label: str
    start_date: date
    end_date: date
    reported: bool


class MyPharmacy(BaseModel):
    id: int
    name: str
    tax_id: str
    address: str | None
    municipality_id: int
    municipality: str
    active: bool
    reportable_weeks: list[ReportableWeek]
    categories: list[str]


class PharmacySalesIndex(BaseModel):
    year: int
    epi_week: int
    label: str
    category: str
    units: int
    reporting_pharmacies: int
    sales_index: float | None  # 100 = mean of the previous 52 weeks
